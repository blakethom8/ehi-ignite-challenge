"""Per-episode narrative generator (T5).

Builds a FHIR ``Composition`` per ``EpisodeOfCare`` using an LLM-authored
prose draft grounded in the harmonized chart and the patient-voice
bundle. Citations of the form ``[[ref:Resource/id]]`` and
``[[ref:turn-<id>]]`` are validated post-hoc against an explicit
allowed-ID set; a single retry is attempted on bad refs, after which
offending markers are stripped (the surrounding prose is preserved).

Two backends ship:

- :class:`FakeNarrativeGenerator` — deterministic, no LLM call. Used
  in tests and as a fallback when the API is unavailable.
- :class:`SonnetNarrativeGenerator` — calls Claude Sonnet via the
  anthropic SDK. Default for production.

Per plan §10, every Sonnet call emits a tracing span
``narrative.generate`` with model, prompt_version, patient_id,
episode_slug, cited_ids_count, invalid_refs_count, retry_count, and
token/cost attributes.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Mapping, Protocol

from .prompts import (
    EPISODE_NARRATIVE_PROMPT_VERSION,
    render_episode_narrative_prompt,
)
from .storage import episode_slug_for, write_current_narrative


_logger = logging.getLogger(__name__)

ATLAS_BASE = "http://atlas.healthcaredataai.com/fhir"
COMPOSITION_TYPE_SYSTEM = f"{ATLAS_BASE}/CodeSystem/composition-type"
EPISODE_REF_URL = f"{ATLAS_BASE}/StructureDefinition/episode-ref"

NARRATIVE_SECTION_TITLES = (
    ("summary", "Summary"),
    ("timeline", "Timeline"),
    ("key_facts", "Key facts"),
    ("patient_words", "Patient's own words"),
    ("open_questions", "Open questions"),
)


_REF_PATTERN = re.compile(r"\[\[ref:([^\]\s]+)\]\]")


# ---------------------------------------------------------------------------
# Public protocols + dataclasses
# ---------------------------------------------------------------------------


@dataclass
class _Sections:
    summary: str
    timeline: str
    key_facts: str
    patient_words: str
    open_questions: str


class EpisodeNarrativeGenerator(Protocol):
    """Backend protocol: produce narrative section text for one episode."""

    def draft(self, *, prompt: str, allowed_ids: set[str]) -> _Sections: ...


# ---------------------------------------------------------------------------
# Fake backend — tests
# ---------------------------------------------------------------------------


@dataclass
class FakeNarrativeGenerator:
    """Deterministic generator. Returns canned sections per episode-id.

    ``by_episode_id`` lets tests assert specific outputs; ``default``
    is used when the episode id isn't in the map.
    """

    by_episode_id: dict[str, _Sections] = None  # type: ignore[assignment]
    default: _Sections | None = None

    def draft(self, *, prompt: str, allowed_ids: set[str]) -> _Sections:
        if self.default is None and not self.by_episode_id:
            return _Sections(
                summary="Demo narrative.",
                timeline="- Demo bullet",
                key_facts="Demo key facts.",
                patient_words="",
                open_questions="",
            )
        return self.default or _Sections(
            summary="Demo.", timeline="", key_facts="", patient_words="", open_questions=""
        )


# ---------------------------------------------------------------------------
# Sonnet backend — production
# ---------------------------------------------------------------------------


@dataclass
class SonnetNarrativeGenerator:
    """Production generator. Calls Claude Sonnet via the anthropic SDK.

    Retries once on bad-ref validation failure with a tighter prompt.
    On a second failure, returns the sections with the bad markers
    stripped — the surrounding prose survives.
    """

    api_key: str | None = None
    model: str = "claude-sonnet-4-6"
    enable_tracing: bool = True

    def draft(self, *, prompt: str, allowed_ids: set[str]) -> _Sections:
        text, usage, retries, invalid_after = self._call_with_retry(
            prompt=prompt, allowed_ids=allowed_ids
        )
        payload = _parse_narrative_json(text)
        sections = _sections_from_payload(payload)
        sections = _strip_invalid_refs(sections, allowed_ids)
        self._emit_span(
            usage=usage,
            retries=retries,
            invalid_refs_count=invalid_after,
            sections=sections,
        )
        return sections

    def _call_with_retry(
        self, *, prompt: str, allowed_ids: set[str]
    ) -> tuple[str, dict[str, int], int, int]:
        # First attempt
        text, usage = self._call_llm(prompt)
        invalid = _invalid_refs(text, allowed_ids)
        if not invalid:
            return text, usage, 0, 0
        # One retry with bad-ref list
        retry_prompt = prompt + (
            "\n\nYour previous draft cited IDs that are not in the allowed list. "
            f"Bad refs: {', '.join(sorted(invalid))}. "
            "Rewrite the JSON using ONLY the allowed IDs above."
        )
        text2, usage2 = self._call_llm(retry_prompt)
        invalid2 = _invalid_refs(text2, allowed_ids)
        merged_usage = {
            "input_tokens": usage.get("input_tokens", 0) + usage2.get("input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0) + usage2.get("output_tokens", 0),
        }
        return text2, merged_usage, 1, len(invalid2)

    def _call_llm(self, prompt: str) -> tuple[str, dict[str, int]]:
        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY required for SonnetNarrativeGenerator")

        import anthropic  # type: ignore[import-not-found]

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=1800,
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
        usage: dict[str, int],
        retries: int,
        invalid_refs_count: int,
        sections: _Sections,
    ) -> None:
        if not self.enable_tracing:
            return
        try:
            from lib.observability.tracing import SpanKind, start_span
        except Exception:
            return
        attrs = {
            "model": self.model,
            "prompt_version": EPISODE_NARRATIVE_PROMPT_VERSION,
            "retry_count": retries,
            "invalid_refs_count": invalid_refs_count,
        }
        with start_span(SpanKind.LLM, "narrative.generate", input_data=attrs) as span:
            if span is None:
                return
            span.input_tokens = usage.get("input_tokens")
            span.output_tokens = usage.get("output_tokens")
            cited = _count_refs("\n".join(_section_text_iter(sections)))
            span.output_data = json.dumps(
                {"cited_ids_count": cited, "retry_count": retries},
                default=str,
            )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def generate_episode_narrative(
    *,
    patient_id: str,
    episode: Mapping[str, Any],
    harmonized_record: Mapping[str, Any],
    patient_voice_bundle: Mapping[str, Any] | None = None,
    generator: EpisodeNarrativeGenerator | None = None,
) -> dict[str, Any]:
    """Generate a FHIR ``Composition`` for one episode.

    ``harmonized_record`` is a FHIR Bundle of merged resources
    (Observations, Conditions, MedicationRequests, Encounters).
    ``patient_voice_bundle`` is optional — if present, its turn ids
    enter the allowed-cite list and the prompt's "Patient's own words"
    block.

    Returns the new Composition dict (NOT persisted — caller decides
    when to call :func:`~lib.narratives.storage.write_current_narrative`).
    """
    backend = generator or FakeNarrativeGenerator()
    slug = episode_slug_for(dict(episode))

    cite_index = _build_cite_index(
        harmonized_record=harmonized_record,
        patient_voice_bundle=patient_voice_bundle,
    )

    prompt = render_episode_narrative_prompt(
        episode=dict(episode),
        condition_ids=sorted(cite_index["Condition"]),
        medication_ids=sorted(cite_index["MedicationRequest"]),
        observation_ids=sorted(cite_index["Observation"]),
        encounter_ids=sorted(cite_index["Encounter"]),
        patient_turn_ids=sorted(cite_index["turn"]),
        fact_table=_render_fact_table(harmonized_record),
        patient_turns_block=_render_patient_turns(patient_voice_bundle),
    )

    allowed_ids = _allowed_id_set(cite_index)
    sections = backend.draft(prompt=prompt, allowed_ids=allowed_ids)
    return _composition_from_sections(
        patient_id=patient_id,
        episode_id=str(episode.get("id") or f"episode-{slug}"),
        episode_slug=slug,
        sections=sections,
    )


# ---------------------------------------------------------------------------
# Cite index + fact-table rendering
# ---------------------------------------------------------------------------


def _build_cite_index(
    *,
    harmonized_record: Mapping[str, Any],
    patient_voice_bundle: Mapping[str, Any] | None,
) -> dict[str, set[str]]:
    """Group cite-eligible resource ids by resourceType, plus patient turn ids."""
    index: dict[str, set[str]] = {
        "Condition": set(),
        "MedicationRequest": set(),
        "Observation": set(),
        "Encounter": set(),
        "turn": set(),
    }
    for entry in harmonized_record.get("entry") or []:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource") or {}
        rtype = resource.get("resourceType")
        rid = resource.get("id")
        if rtype in index and rid:
            index[rtype].add(str(rid))
    if patient_voice_bundle:
        for entry in patient_voice_bundle.get("entry") or []:
            resource = (entry or {}).get("resource") or {}
            for ext in (resource.get("meta") or {}).get("extension") or []:
                if (
                    isinstance(ext, dict)
                    and ext.get("url", "").endswith("/source-locator")
                ):
                    locator = ext.get("valueString", "")
                    for fragment in locator.split(";"):
                        if fragment.startswith("turn="):
                            index["turn"].add(f"turn-{fragment.split('=', 1)[1]}")
    return index


def _allowed_id_set(cite_index: Mapping[str, set[str]]) -> set[str]:
    out: set[str] = set()
    for rtype, ids in cite_index.items():
        if rtype == "turn":
            out.update(ids)  # already prefixed with turn-
        else:
            out.update(f"{rtype}/{rid}" for rid in ids)
    return out


def _render_fact_table(harmonized_record: Mapping[str, Any]) -> str:
    """Compact, oldest-first per-resource table for the prompt."""
    lines: list[str] = []
    by_type: dict[str, list[dict[str, Any]]] = {
        "Condition": [],
        "MedicationRequest": [],
        "Observation": [],
        "Encounter": [],
    }
    for entry in harmonized_record.get("entry") or []:
        resource = (entry or {}).get("resource") or {}
        rtype = resource.get("resourceType")
        if rtype in by_type:
            by_type[rtype].append(resource)

    if by_type["Condition"]:
        lines.append("Conditions:")
        for r in by_type["Condition"]:
            label = _label_of(r)
            date = _date_of(r) or "?"
            status = (
                (r.get("clinicalStatus") or {}).get("coding") or [{}]
            )[0].get("code") or "?"
            lines.append(
                f"  - [{date}] [{status}] {label} [[ref:Condition/{r.get('id')}]]"
            )
    if by_type["MedicationRequest"]:
        lines.append("Medications:")
        for r in by_type["MedicationRequest"]:
            label = _label_of(r)
            date = _date_of(r) or "?"
            status = r.get("status") or "?"
            lines.append(
                f"  - [{date}] [{status}] {label} [[ref:MedicationRequest/{r.get('id')}]]"
            )
    if by_type["Observation"]:
        lines.append("Observations:")
        for r in by_type["Observation"]:
            label = _label_of(r)
            date = _date_of(r) or "?"
            value = r.get("valueString") or (
                (r.get("valueQuantity") or {}).get("value")
            )
            lines.append(
                f"  - [{date}] {label} = {value} [[ref:Observation/{r.get('id')}]]"
            )
    if by_type["Encounter"]:
        lines.append("Encounters:")
        for r in by_type["Encounter"]:
            date = _date_of(r) or "?"
            label = (r.get("type") or [{}])[0].get("text") or "?"
            lines.append(f"  - [{date}] {label} [[ref:Encounter/{r.get('id')}]]")
    return "\n".join(lines)


def _render_patient_turns(bundle: Mapping[str, Any] | None) -> str:
    if not bundle:
        return ""
    lines: list[str] = []
    for entry in bundle.get("entry") or []:
        resource = (entry or {}).get("resource") or {}
        note = resource.get("note")
        text = ""
        if isinstance(note, list) and note:
            text = (note[0] or {}).get("text", "")
        if not text and resource.get("valueString"):
            text = resource["valueString"]
        if not text:
            continue
        turn_id = ""
        for ext in (resource.get("meta") or {}).get("extension") or []:
            if isinstance(ext, dict) and ext.get("url", "").endswith("/source-locator"):
                for frag in ext.get("valueString", "").split(";"):
                    if frag.startswith("turn="):
                        turn_id = frag.split("=", 1)[1]
        if turn_id:
            lines.append(f'  - [[ref:turn-{turn_id}]] "{text}"')
        else:
            lines.append(f'  - "{text}"')
    return "\n".join(lines)


def _label_of(resource: Mapping[str, Any]) -> str:
    code = resource.get("code") or resource.get("medicationCodeableConcept") or {}
    if isinstance(code, dict):
        if t := code.get("text"):
            return t
        coding = code.get("coding") or [{}]
        if coding and isinstance(coding[0], dict):
            return coding[0].get("display") or coding[0].get("code") or "(unknown)"
    return "(unknown)"


def _date_of(resource: Mapping[str, Any]) -> str | None:
    for key in ("onsetDateTime", "authoredOn", "effectiveDateTime", "occurrenceDateTime", "period"):
        v = resource.get(key)
        if isinstance(v, str) and v:
            return v[:10]
        if isinstance(v, dict) and v.get("start"):
            return str(v["start"])[:10]
    return None


# ---------------------------------------------------------------------------
# JSON parsing + citation validation
# ---------------------------------------------------------------------------


def _parse_narrative_json(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, re.DOTALL)
    if fenced:
        cleaned = fenced.group(1)
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start < 0 or end <= start:
            raise ValueError(f"narrative JSON parse failed: {text[:200]}")
        return json.loads(cleaned[start : end + 1])


def _sections_from_payload(payload: Mapping[str, Any]) -> _Sections:
    return _Sections(
        summary=str(payload.get("summary") or "").strip(),
        timeline=str(payload.get("timeline") or "").strip(),
        key_facts=str(payload.get("key_facts") or "").strip(),
        patient_words=str(payload.get("patient_words") or "").strip(),
        open_questions=str(payload.get("open_questions") or "").strip(),
    )


def _invalid_refs(text: str, allowed_ids: set[str]) -> set[str]:
    return {m for m in _REF_PATTERN.findall(text) if m not in allowed_ids}


def _strip_invalid_refs(sections: _Sections, allowed_ids: set[str]) -> _Sections:
    """Remove [[ref:...]] markers whose targets aren't in the allowed set.

    Surrounding prose is preserved. The marker AND a single trailing
    whitespace character are removed so we don't leave double-spaces.
    """

    def clean(s: str) -> str:
        def repl(match: re.Match[str]) -> str:
            ref = match.group(1)
            return match.group(0) if ref in allowed_ids else ""

        out = _REF_PATTERN.sub(repl, s)
        return re.sub(r"  +", " ", out).strip()

    return _Sections(
        summary=clean(sections.summary),
        timeline=clean(sections.timeline),
        key_facts=clean(sections.key_facts),
        patient_words=clean(sections.patient_words),
        open_questions=clean(sections.open_questions),
    )


def _count_refs(text: str) -> int:
    return len(_REF_PATTERN.findall(text or ""))


def _section_text_iter(sections: _Sections) -> Iterable[str]:
    yield sections.summary
    yield sections.timeline
    yield sections.key_facts
    yield sections.patient_words
    yield sections.open_questions


# ---------------------------------------------------------------------------
# Composition assembly
# ---------------------------------------------------------------------------


def _composition_from_sections(
    *,
    patient_id: str,
    episode_id: str,
    episode_slug: str,
    sections: _Sections,
) -> dict[str, Any]:
    timestamp = datetime.now(timezone.utc).isoformat()
    composition_id = f"narrative-{episode_slug}-{_timestamp_for_id(timestamp)}"

    section_array: list[dict[str, Any]] = []
    for key, title in NARRATIVE_SECTION_TITLES:
        text = getattr(sections, key)
        if not text:
            text = ""  # keep section visible but mark empty
        section_array.append(
            {
                "title": title,
                "text": {
                    "status": "additional",
                    "div": f"<div xmlns=\"http://www.w3.org/1999/xhtml\">{_html_escape(text)}</div>",
                },
            }
        )

    return {
        "resourceType": "Composition",
        "id": composition_id,
        "status": "final",
        "type": {
            "coding": [
                {
                    "system": COMPOSITION_TYPE_SYSTEM,
                    "code": "episode-narrative",
                    "display": "Episode narrative",
                }
            ]
        },
        "subject": {"reference": f"Patient/{patient_id}"},
        "date": timestamp,
        "extension": [
            {
                "url": EPISODE_REF_URL,
                "valueReference": {"reference": f"EpisodeOfCare/{episode_id}"},
            }
        ],
        "section": section_array,
    }


def _timestamp_for_id(iso: str) -> str:
    return re.sub(r"[^0-9A-Za-z]+", "-", iso).strip("-")[:32] or "now"


def _html_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
