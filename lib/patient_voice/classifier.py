"""Turn classifier: map one patient turn to a structured classification.

The classifier returns a :class:`TurnClassification` describing what kind
of FHIR resource the turn should mint. The caller (``to_fhir.py``)
materialises the actual FHIR resource from the classification.

Two implementations ship:

- :class:`HaikuTurnClassifier` — production. Calls Claude Haiku and
  caches the result on disk by ``sha256(turn_id + content + prompt_version + model)``.
- :class:`FakeTurnClassifier` — test fixture. Returns canned
  classifications from an ``id -> TurnClassification`` mapping.

Per the plan §10, every live classification emits a tracing span
``patient_voice.classify`` with model, prompt_version, kind, cached, and
token/cost attributes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Literal, Protocol

from .prompts import TURN_CLASSIFIER_PROMPT_VERSION, render_turn_classifier_prompt


DEFAULT_CACHE_ROOT = Path(
    os.getenv(
        "PATIENT_VOICE_CACHE_PATH",
        Path(__file__).resolve().parents[2] / "data" / ".cache" / "patient-voice",
    )
)


TurnKind = Literal["med_statement", "condition", "goal", "generic"]


@dataclass(frozen=True)
class TurnClassification:
    """Structured classification of one patient turn.

    Field semantics depend on ``kind``:

    - ``med_statement`` populates ``status``, ``drug_text``,
      and optionally ``effective_end_iso``.
    - ``condition`` populates ``condition_text`` and ``onset_period``.
    - ``goal`` populates ``goal_text``.
    - ``generic`` populates nothing — the raw turn text becomes the
      observation ``valueString`` downstream.

    Unused fields are ``None`` / empty.
    """

    kind: TurnKind
    status: Literal["active", "stopped"] | None = None
    drug_text: str | None = None
    effective_end_iso: str | None = None
    condition_text: str | None = None
    onset_period: tuple[str, str] | None = None
    goal_text: str | None = None
    # Diagnostic: which model/prompt produced this. Useful for cache
    # debugging and for the FakeTurnClassifier to mirror real shape.
    model: str = ""
    prompt_version: str = TURN_CLASSIFIER_PROMPT_VERSION

    def to_jsonable(self) -> dict[str, Any]:
        d = asdict(self)
        if self.onset_period is not None:
            d["onset_period"] = list(self.onset_period)
        return d


class TurnClassifier(Protocol):
    """Protocol for any classifier that maps one turn to a classification."""

    def classify(
        self,
        *,
        turn_id: str,
        turn_content: str,
        gap_title: str,
        gap_prompt: str,
        today_iso: str,
    ) -> TurnClassification: ...


# ---------------------------------------------------------------------------
# Fake classifier — test fixture
# ---------------------------------------------------------------------------


@dataclass
class FakeTurnClassifier:
    """Test fixture: return a canned classification per ``turn_id``.

    Usage::

        fake = FakeTurnClassifier(
            by_turn_id={
                "t_lisinopril": TurnClassification(
                    kind="med_statement", status="stopped",
                    drug_text="lisinopril", effective_end_iso="2026-04-20",
                ),
            },
            default=TurnClassification(kind="generic"),
        )
    """

    by_turn_id: dict[str, TurnClassification] = field(default_factory=dict)
    default: TurnClassification = field(default_factory=lambda: TurnClassification(kind="generic"))

    def classify(
        self,
        *,
        turn_id: str,
        turn_content: str,
        gap_title: str,
        gap_prompt: str,
        today_iso: str,
    ) -> TurnClassification:
        return self.by_turn_id.get(turn_id, self.default)


# ---------------------------------------------------------------------------
# Haiku classifier — production
# ---------------------------------------------------------------------------


@dataclass
class HaikuTurnClassifier:
    """Default classifier — Claude Haiku, JSON-only output, disk cached.

    Cache key: sha256 of (turn_id + turn_content + prompt_version + model).
    Cache path: ``$PATIENT_VOICE_CACHE_PATH`` or ``data/.cache/patient-voice/<sha>.json``.
    """

    api_key: str | None = None
    model: str = "claude-haiku-4-5"
    cache_root: Path = DEFAULT_CACHE_ROOT
    # Tracing hook (optional, lazy-imported). If None, fall back to a no-op
    # so this module can be tested without the api.* stack on the path.
    enable_tracing: bool = True

    def _cache_path(self, turn_id: str, turn_content: str) -> Path:
        key = hashlib.sha256(
            (
                f"{turn_id}|{turn_content}|{TURN_CLASSIFIER_PROMPT_VERSION}|{self.model}"
            ).encode("utf-8")
        ).hexdigest()
        return self.cache_root / f"{key}.json"

    def _load_cached(self, path: Path) -> TurnClassification | None:
        if not path.exists():
            return None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        kind = payload.get("kind")
        if kind not in {"med_statement", "condition", "goal", "generic"}:
            return None
        onset = payload.get("onset_period")
        return TurnClassification(
            kind=kind,
            status=payload.get("status"),
            drug_text=payload.get("drug_text"),
            effective_end_iso=payload.get("effective_end_iso"),
            condition_text=payload.get("condition_text"),
            onset_period=tuple(onset) if isinstance(onset, list) and len(onset) == 2 else None,
            goal_text=payload.get("goal_text"),
            model=payload.get("model", self.model),
            prompt_version=payload.get("prompt_version", TURN_CLASSIFIER_PROMPT_VERSION),
        )

    def _save_cache(self, path: Path, classification: TurnClassification) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(classification.to_jsonable(), indent=2), encoding="utf-8")

    def classify(
        self,
        *,
        turn_id: str,
        turn_content: str,
        gap_title: str,
        gap_prompt: str,
        today_iso: str,
    ) -> TurnClassification:
        cache_path = self._cache_path(turn_id, turn_content)
        cached = self._load_cached(cache_path)
        if cached is not None:
            self._emit_span(turn_id=turn_id, classification=cached, cached=True, usage=None)
            return cached

        prompt = render_turn_classifier_prompt(
            turn_content=turn_content,
            gap_title=gap_title,
            gap_prompt=gap_prompt,
            today_iso=today_iso,
        )

        # Two attempts: first the natural prompt, then a JSON-only reminder.
        last_error: str | None = None
        usage: dict[str, int] | None = None
        for attempt in (1, 2):
            try:
                text, usage = self._call_llm(prompt, json_only_retry=(attempt == 2))
                payload = _parse_classifier_json(text)
                classification = _classification_from_payload(payload, model=self.model)
                self._save_cache(cache_path, classification)
                self._emit_span(
                    turn_id=turn_id,
                    classification=classification,
                    cached=False,
                    usage=usage,
                )
                return classification
            except (ValueError, RuntimeError) as exc:
                last_error = str(exc)
                continue

        # Both attempts failed — fall back to "generic" so we still preserve the turn.
        fallback = TurnClassification(kind="generic", model=self.model)
        self._save_cache(cache_path, fallback)
        self._emit_span(
            turn_id=turn_id,
            classification=fallback,
            cached=False,
            usage=usage,
            error=last_error,
        )
        return fallback

    def _call_llm(self, prompt: str, *, json_only_retry: bool) -> tuple[str, dict[str, int]]:
        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY required for HaikuTurnClassifier")

        import anthropic  # type: ignore[import-not-found]

        client = anthropic.Anthropic(api_key=api_key)
        user_content = prompt
        if json_only_retry:
            user_content += (
                "\n\nReturn ONLY a JSON object. No prose, no markdown fence. "
                "Start your response with { and end with }."
            )
        response = client.messages.create(
            model=self.model,
            max_tokens=400,
            messages=[{"role": "user", "content": user_content}],
        )
        text = response.content[0].text if response.content else ""
        usage_obj = getattr(response, "usage", None)
        usage = {
            "input_tokens": int(getattr(usage_obj, "input_tokens", 0) or 0),
            "output_tokens": int(getattr(usage_obj, "output_tokens", 0) or 0),
        }
        return text, usage

    def _emit_span(
        self,
        *,
        turn_id: str,
        classification: TurnClassification,
        cached: bool,
        usage: dict[str, int] | None,
        error: str | None = None,
    ) -> None:
        if not self.enable_tracing:
            return
        try:
            from lib.observability.tracing import SpanKind, start_span
        except Exception:
            return
        attrs = {
            "model": self.model,
            "prompt_version": TURN_CLASSIFIER_PROMPT_VERSION,
            "turn_id": turn_id,
            "cached": cached,
            "kind": classification.kind,
        }
        with start_span(SpanKind.LLM, "patient_voice.classify", input_data=attrs) as span:
            if span is None:
                return
            if usage is not None:
                span.input_tokens = usage.get("input_tokens")
                span.output_tokens = usage.get("output_tokens")
            span.output_data = json.dumps(
                {"kind": classification.kind, "cached": cached, "error": error},
                default=str,
            )
            if error:
                span.error = error[:1000]


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------


_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*\})\s*```", re.DOTALL)


def _parse_classifier_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = _FENCE_RE.search(cleaned)
    if fenced:
        cleaned = fenced.group(1)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError(f"classifier returned non-JSON: {text[:200]}")
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError(f"classifier JSON is not an object: {parsed!r}")
    return parsed


def _classification_from_payload(
    payload: dict[str, Any],
    *,
    model: str,
) -> TurnClassification:
    kind = payload.get("kind")
    if kind not in {"med_statement", "condition", "goal", "generic"}:
        raise ValueError(f"classifier returned unknown kind: {kind!r}")
    onset_raw = payload.get("onset_period")
    onset: tuple[str, str] | None = None
    if isinstance(onset_raw, list) and len(onset_raw) == 2:
        onset = (str(onset_raw[0]), str(onset_raw[1]))
    status_raw = payload.get("status")
    status: Literal["active", "stopped"] | None
    if status_raw in {"active", "stopped"}:
        status = status_raw  # type: ignore[assignment]
    else:
        status = None
    return TurnClassification(
        kind=kind,
        status=status,
        drug_text=_clean_text(payload.get("drug_text")),
        effective_end_iso=_clean_text(payload.get("effective_end_iso")),
        condition_text=_clean_text(payload.get("condition_text")),
        onset_period=onset,
        goal_text=_clean_text(payload.get("goal_text")),
        model=model,
    )


def _clean_text(value: Any) -> str | None:
    if value is None:
        return None
    s = str(value).strip()
    return s or None
