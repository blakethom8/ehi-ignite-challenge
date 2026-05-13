"""Patient-voice summarizer (T8a).

Produces a ≤200-char third-person summary of the patient's own
self-described state, citing the specific turn ids it drew from. The
output drives the first sentence of Caspian's system prompt ("In the
patient's own words: ..."), so the surgeon feels the patient before
the structured tables load.

Two backends mirror the T1 classifier pattern:

- :class:`FakeVoiceSummarizer` — deterministic test fixture.
- :class:`HaikuVoiceSummarizer` — production. Caches the result on disk
  by sha256(turn ids + content + prompt_version + model).

Per plan §10, every Haiku call emits a tracing span
``patient_voice.summarize`` with model, prompt_version, patient_id,
turn_count, output_chars, input/output_tokens, cost_usd.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Protocol


VOICE_SUMMARIZER_PROMPT_VERSION = "v1"


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_CACHE_ROOT = Path(
    os.getenv(
        "PATIENT_VOICE_CACHE_PATH",
        REPO_ROOT / "data" / ".cache" / "patient-voice",
    )
)
DEFAULT_STORE_ROOT = Path(
    os.getenv("PATIENT_CONTEXT_STORE_PATH", REPO_ROOT / "data" / "patient-context")
)


_logger = logging.getLogger(__name__)


VOICE_SUMMARIZER_PROMPT_V1 = """\
You are summarizing a patient's own self-described facts for a surgeon
about to review their chart. Produce a single ≤200-char sentence in
third person ("Patient reports..." or "Patient stopped...").

Patient turns (verbatim):
{turns_block}

Rules
-----
- ≤200 characters total. Strictly count.
- Third person, no quotation marks.
- Cite specific facts (medication names, durations, dates) when
  available. Drop anything that's already in the structured chart.
- DO NOT speculate. If the turn is unclear, omit it.

Return JSON ONLY:
{{
  "summary": "<one sentence, ≤200 chars>",
  "citations": ["turn-<id>", "turn-<id>"]
}}
"""


# ---------------------------------------------------------------------------
# Public dataclass
# ---------------------------------------------------------------------------


@dataclass
class PatientVoiceSummary:
    """A short first-person summary citing the turn ids it drew from."""

    summary: str
    citations: list[str] = field(default_factory=list)
    generated_at: str = ""

    def to_jsonable(self) -> dict[str, Any]:
        return asdict(self)


class VoiceSummarizer(Protocol):
    def summarize(
        self,
        *,
        turns: list[Mapping[str, Any]],
        patient_id: str,
    ) -> PatientVoiceSummary: ...


# ---------------------------------------------------------------------------
# Fake — test fixture
# ---------------------------------------------------------------------------


@dataclass
class FakeVoiceSummarizer:
    summary: str = "Patient demo summary."
    citations: list[str] = field(default_factory=list)

    def summarize(
        self, *, turns: list[Mapping[str, Any]], patient_id: str
    ) -> PatientVoiceSummary:
        return PatientVoiceSummary(
            summary=self.summary,
            citations=self.citations or [f"turn-{t.get('id', '?')}" for t in turns],
            generated_at=datetime.now(timezone.utc).isoformat(),
        )


# ---------------------------------------------------------------------------
# Haiku — production
# ---------------------------------------------------------------------------


@dataclass
class HaikuVoiceSummarizer:
    api_key: str | None = None
    model: str = "claude-haiku-4-5"
    cache_root: Path = DEFAULT_CACHE_ROOT
    enable_tracing: bool = True

    def _cache_key(self, turns: list[Mapping[str, Any]]) -> str:
        joined = "|".join(
            f"{t.get('id', '?')}::{(t.get('content') or '').strip()}" for t in turns
        )
        return hashlib.sha256(
            f"{joined}|{VOICE_SUMMARIZER_PROMPT_VERSION}|{self.model}".encode("utf-8")
        ).hexdigest()

    def _cache_path(self, turns: list[Mapping[str, Any]]) -> Path:
        return self.cache_root / "summary" / f"{self._cache_key(turns)}.json"

    def _load_cache(self, path: Path) -> PatientVoiceSummary | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(payload, dict):
            return None
        return PatientVoiceSummary(
            summary=str(payload.get("summary", "")),
            citations=list(payload.get("citations") or []),
            generated_at=str(payload.get("generated_at") or ""),
        )

    def _save_cache(self, path: Path, summary: PatientVoiceSummary) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary.to_jsonable(), indent=2), encoding="utf-8")

    def summarize(
        self, *, turns: list[Mapping[str, Any]], patient_id: str
    ) -> PatientVoiceSummary:
        if not turns:
            return PatientVoiceSummary(
                summary="", citations=[], generated_at=datetime.now(timezone.utc).isoformat()
            )
        cache_path = self._cache_path(turns)
        cached = self._load_cache(cache_path)
        if cached is not None:
            self._emit_span(
                patient_id=patient_id,
                turns=turns,
                summary=cached,
                cached=True,
                usage=None,
            )
            return cached

        prompt = _render_summarizer_prompt(turns)
        try:
            text, usage = self._call_llm(prompt)
            payload = _parse_summarizer_json(text)
            summary = PatientVoiceSummary(
                summary=str(payload.get("summary", "")).strip()[:200],
                citations=[str(c) for c in (payload.get("citations") or [])],
                generated_at=datetime.now(timezone.utc).isoformat(),
            )
        except Exception as exc:  # noqa: BLE001 — fall back without raising
            _logger.warning("patient_voice.summarize failed: %s", exc)
            summary = PatientVoiceSummary(
                summary="",
                citations=[],
                generated_at=datetime.now(timezone.utc).isoformat(),
            )
            usage = None

        self._save_cache(cache_path, summary)
        self._emit_span(
            patient_id=patient_id,
            turns=turns,
            summary=summary,
            cached=False,
            usage=usage,
        )
        return summary

    def _call_llm(self, prompt: str) -> tuple[str, dict[str, int]]:
        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY required for HaikuVoiceSummarizer")

        import anthropic  # type: ignore[import-not-found]

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=250,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text if response.content else ""
        usage_obj = getattr(response, "usage", None)
        return text, {
            "input_tokens": int(getattr(usage_obj, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage_obj, "output_tokens", 0) or 0),
        }

    def _emit_span(
        self,
        *,
        patient_id: str,
        turns: list[Mapping[str, Any]],
        summary: PatientVoiceSummary,
        cached: bool,
        usage: dict[str, int] | None,
    ) -> None:
        if not self.enable_tracing:
            return
        try:
            from lib.observability.tracing import SpanKind, start_span
        except Exception:
            return
        attrs = {
            "model": self.model,
            "prompt_version": VOICE_SUMMARIZER_PROMPT_VERSION,
            "patient_id": patient_id,
            "turn_count": len(turns),
            "output_chars": len(summary.summary),
            "cached": cached,
        }
        with start_span(SpanKind.LLM, "patient_voice.summarize", input_data=attrs) as span:
            if span is None:
                return
            if usage is not None:
                span.input_tokens = usage.get("input_tokens")
                span.output_tokens = usage.get("output_tokens")
            span.output_data = json.dumps(
                {"summary_chars": len(summary.summary), "cited": len(summary.citations)},
                default=str,
            )


# ---------------------------------------------------------------------------
# Orchestration helpers
# ---------------------------------------------------------------------------


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return safe[:120] or "patient"


def summary_path_for(patient_id: str, *, store_root: Path | None = None) -> Path:
    return (store_root or DEFAULT_STORE_ROOT) / _safe_id(patient_id) / "voice_summary.json"


def load_summary(patient_id: str, *, store_root: Path | None = None) -> PatientVoiceSummary | None:
    path = summary_path_for(patient_id, store_root=store_root)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return PatientVoiceSummary(
        summary=str(payload.get("summary", "")),
        citations=list(payload.get("citations") or []),
        generated_at=str(payload.get("generated_at") or ""),
    )


def write_summary(
    patient_id: str,
    summary: PatientVoiceSummary,
    *,
    store_root: Path | None = None,
) -> Path:
    path = summary_path_for(patient_id, store_root=store_root)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(summary.to_jsonable(), indent=2), encoding="utf-8")
    return path


def regenerate_voice_summary(
    patient_id: str,
    *,
    summarizer: VoiceSummarizer | None = None,
    store_root: Path | None = None,
) -> PatientVoiceSummary | None:
    """Load every patient-voice bundle from disk, summarise, write to ``voice_summary.json``.

    Returns the summary (or ``None`` if there are no turns on disk).
    """
    root = (store_root or DEFAULT_STORE_ROOT) / _safe_id(patient_id) / "fhir"
    if not root.exists():
        return None
    turns: list[Mapping[str, Any]] = []
    for bundle_path in sorted(root.glob("*.json")):
        try:
            bundle = json.loads(bundle_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for entry in bundle.get("entry") or []:
            resource = (entry or {}).get("resource") or {}
            text = ""
            note = resource.get("note")
            if isinstance(note, list) and note:
                text = (note[0] or {}).get("text", "")
            if not text and resource.get("valueString"):
                text = resource["valueString"]
            if not text:
                continue
            turn_id = ""
            for ext in (resource.get("meta") or {}).get("extension") or []:
                if (
                    isinstance(ext, dict)
                    and ext.get("url", "").endswith("/source-locator")
                ):
                    for frag in ext.get("valueString", "").split(";"):
                        if frag.startswith("turn="):
                            turn_id = frag.split("=", 1)[1]
            turns.append({"id": turn_id or resource.get("id", ""), "content": text})
    if not turns:
        return None
    backend = summarizer or HaikuVoiceSummarizer()
    summary = backend.summarize(turns=turns, patient_id=patient_id)
    write_summary(patient_id, summary, store_root=store_root)
    return summary


def _render_summarizer_prompt(turns: list[Mapping[str, Any]]) -> str:
    block = "\n".join(
        f'  - [{t.get("id", "?")}] "{(t.get("content") or "").strip()}"'
        for t in turns
    )
    return VOICE_SUMMARIZER_PROMPT_V1.format(turns_block=block)


def _parse_summarizer_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError(f"summarizer returned non-JSON: {text[:200]}")
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("summarizer JSON is not an object")
    return parsed
