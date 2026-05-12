"""Conflict adjudicator (T7).

Scans a harmonized record for cross-source disagreements and emits a
list of FHIR caveat resources (``Observation`` with
``code.system=atlas:harmonization-caveat``) the UI surfaces under
"Conflicts to review."

Two adjudication paths:

1. **Patient-voice status overrides** — when T2's source-weight rule
   fired on ``MergedMedication.canonical_status``, T7 emits a
   deterministic caveat describing the resolution (no LLM call
   needed). This is the path the §6 demo arc beat 6 relies on.

2. **Other cross-source disagreements** — dose, frequency, condition
   severity, allergy criticality, lab unit. For each, we call Claude
   Sonnet to produce ``{verdict, confidence, rationale,
   dissenting_sources}``. Phase 1 implements the scan and the LLM
   stub; non-status disagreements are detected but only adjudicated
   when an Anthropic key is present (and only with a `--enable-llm`
   opt-in).

Per plan §10, each LLM adjudication emits a ``harmonize.adjudicate``
tracing span with model, prompt_version, patient_id, fact_path,
dissent_count, confidence, and token attributes.
"""

from __future__ import annotations

import json
import logging
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Protocol

from .models import MergedAllergy, MergedMedication, MergedObservation
from .source_weights import is_patient_voice


_logger = logging.getLogger(__name__)

ATLAS_BASE = "http://atlas.healthcaredataai.com/fhir"
CAVEAT_CODE_SYSTEM = f"{ATLAS_BASE}/CodeSystem/harmonization-caveat"
CAVEAT_BLOCKER_URL = f"{ATLAS_BASE}/StructureDefinition/caveat-blocker"

REPO_ROOT = Path(__file__).resolve().parents[2]
PATIENT_CONTEXT_STORE_ROOT = Path(
    os.getenv("PATIENT_CONTEXT_STORE_PATH", REPO_ROOT / "data" / "patient-context")
)


ADJUDICATOR_PROMPT_VERSION = "v1"

ADJUDICATOR_PROMPT_V1 = """\
Two or more sources disagree on a clinical fact. Adjudicate.

Fact path: {fact_path}

Sources:
{sources_block}

Return JSON ONLY:
{{
  "verdict": "<one of the source values, verbatim>",
  "confidence": "high|medium|low",
  "rationale": "<one sentence>",
  "dissenting_sources": ["<source reference>", ...]
}}

If confidence is "low" the UI surfaces this as a clinician-resolvable
blocker, so use "low" when the disagreement is genuinely ambiguous.
"""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass
class Caveat:
    """One structured conflict resolution. Persists as a FHIR Observation."""

    fact_path: str
    verdict: str
    confidence: str  # "high" | "medium" | "low"
    rationale: str
    dissenting_sources: list[str] = field(default_factory=list)
    blocker: bool = False

    def to_fhir(self) -> dict[str, Any]:
        """Serialize as a FHIR Observation per plan §3.4."""
        safe = re.sub(r"[^A-Za-z0-9]+", "-", self.fact_path).strip("-")[:64]
        return {
            "resourceType": "Observation",
            "id": f"caveat-{safe}" if safe else "caveat-unknown",
            "status": "final",
            "code": {
                "coding": [
                    {"system": CAVEAT_CODE_SYSTEM, "code": "merge-judgment"}
                ]
            },
            "effectiveDateTime": datetime.now(timezone.utc).isoformat(),
            "component": [
                {"code": {"text": "fact_path"}, "valueString": self.fact_path},
                {"code": {"text": "verdict"}, "valueString": self.verdict},
                {"code": {"text": "confidence"}, "valueString": self.confidence},
                {"code": {"text": "rationale"}, "valueString": self.rationale},
                {
                    "code": {"text": "dissenting_sources"},
                    "valueString": ";".join(self.dissenting_sources),
                },
            ],
            "extension": [
                {"url": CAVEAT_BLOCKER_URL, "valueBoolean": bool(self.blocker)}
            ],
        }


@dataclass(frozen=True)
class Disagreement:
    """A detected cross-source disagreement awaiting adjudication."""

    fact_path: str
    field_label: str        # human-readable: "dose", "unit", etc.
    sources: list[dict[str, Any]]  # [{label, ref, value, date}]


class ConflictAdjudicator(Protocol):
    """LLM (or fake) backend that turns a Disagreement into a Caveat."""

    def adjudicate(self, disagreement: Disagreement) -> Caveat: ...


# ---------------------------------------------------------------------------
# Backends — Fake + Sonnet
# ---------------------------------------------------------------------------


@dataclass
class FakeConflictAdjudicator:
    """Deterministic adjudicator used by tests and as a no-LLM fallback.

    Picks the source with the latest ``date`` as the verdict (or the
    first source when dates are missing). Confidence is always
    ``"medium"``.
    """

    rationale_template: str = "Most recent source wins (fake adjudicator)."

    def adjudicate(self, disagreement: Disagreement) -> Caveat:
        sources = list(disagreement.sources)
        if not sources:
            return Caveat(
                fact_path=disagreement.fact_path,
                verdict="",
                confidence="low",
                rationale="No sources to adjudicate.",
            )
        sources.sort(key=lambda s: s.get("date") or "", reverse=True)
        winner = sources[0]
        dissenting = [s["ref"] for s in sources[1:] if s.get("value") != winner.get("value")]
        return Caveat(
            fact_path=disagreement.fact_path,
            verdict=str(winner.get("value", "")),
            confidence="medium",
            rationale=self.rationale_template,
            dissenting_sources=dissenting,
        )


@dataclass
class SonnetConflictAdjudicator:
    """Production: Claude Sonnet adjudicates each disagreement."""

    api_key: str | None = None
    model: str = "claude-sonnet-4-6"
    enable_tracing: bool = True

    def adjudicate(self, disagreement: Disagreement) -> Caveat:
        prompt = _render_adjudicator_prompt(disagreement)
        try:
            text, usage = self._call_llm(prompt)
            payload = _parse_adjudicator_json(text)
        except Exception as exc:  # noqa: BLE001
            _logger.warning("adjudicator LLM failed for %s: %s", disagreement.fact_path, exc)
            self._emit_span(disagreement=disagreement, caveat=None, usage=None, error=str(exc))
            # Fallback: low-confidence caveat citing the failure.
            return Caveat(
                fact_path=disagreement.fact_path,
                verdict="(adjudication failed)",
                confidence="low",
                rationale=f"Adjudicator unavailable: {exc}",
                blocker=True,
            )
        verdict = str(payload.get("verdict", "")).strip()
        confidence = str(payload.get("confidence", "medium")).strip().lower()
        if confidence not in {"high", "medium", "low"}:
            confidence = "medium"
        rationale = str(payload.get("rationale", "")).strip()
        dissenting = [
            str(s) for s in (payload.get("dissenting_sources") or []) if str(s).strip()
        ]
        caveat = Caveat(
            fact_path=disagreement.fact_path,
            verdict=verdict,
            confidence=confidence,
            rationale=rationale,
            dissenting_sources=dissenting,
            blocker=(confidence == "low"),
        )
        self._emit_span(disagreement=disagreement, caveat=caveat, usage=usage)
        return caveat

    def _call_llm(self, prompt: str) -> tuple[str, dict[str, int]]:
        api_key = self.api_key or os.environ.get("ANTHROPIC_API_KEY", "")
        if not api_key:
            raise RuntimeError("ANTHROPIC_API_KEY required for SonnetConflictAdjudicator")

        import anthropic  # type: ignore[import-not-found]

        client = anthropic.Anthropic(api_key=api_key)
        response = client.messages.create(
            model=self.model,
            max_tokens=400,
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
        disagreement: Disagreement,
        caveat: Caveat | None,
        usage: dict[str, int] | None,
        error: str | None = None,
    ) -> None:
        if not self.enable_tracing:
            return
        try:
            from api.core.tracing import SpanKind, start_span  # type: ignore
        except Exception:
            return
        attrs = {
            "model": self.model,
            "prompt_version": ADJUDICATOR_PROMPT_VERSION,
            "fact_path": disagreement.fact_path,
            "dissent_count": len(disagreement.sources),
            "confidence": caveat.confidence if caveat else "error",
        }
        with start_span(SpanKind.LLM, "harmonize.adjudicate", input_data=attrs) as span:
            if span is None:
                return
            if usage is not None:
                span.input_tokens = usage.get("input_tokens")
                span.output_tokens = usage.get("output_tokens")
            if error:
                span.error = error[:1000]


# ---------------------------------------------------------------------------
# Public scan API
# ---------------------------------------------------------------------------


def adjudicate_merged_record(
    patient_id: str,
    *,
    merged_medications: Iterable[MergedMedication] = (),
    merged_observations: Iterable[MergedObservation] = (),
    merged_allergies: Iterable[MergedAllergy] = (),
    adjudicator: ConflictAdjudicator | None = None,
) -> list[Caveat]:
    """Scan a harmonized record for conflicts; return a list of Caveats.

    Emits two kinds of caveats:

    1. **Patient-voice status overrides** (deterministic, no LLM
       call). When T2's weight rule fired on a MergedMedication, we
       surface the resolution as a caveat so the UI can render it
       alongside LLM-adjudicated ones.
    2. **Cross-source disagreements** on other fields (dose, allergy
       criticality, observation unit). Each is routed through
       ``adjudicator`` (default: ``FakeConflictAdjudicator``).
    """
    backend = adjudicator or FakeConflictAdjudicator()
    caveats: list[Caveat] = []

    for merged in merged_medications:
        # (1) Patient-voice status override — deterministic.
        override = _patient_voice_status_caveat(merged)
        if override is not None:
            caveats.append(override)
        # (2) Dose disagreement (display-string mismatch across
        #     non-patient sources). Phase 1 deliberately scopes
        #     narrowly — dose detection is fuzzy enough that we only
        #     fire when display strings differ and at least 2 sources
        #     carry text.
        dose = _medication_dose_disagreement(merged)
        if dose is not None:
            caveats.append(backend.adjudicate(dose))

    for merged in merged_observations:
        unit = _observation_unit_disagreement(merged)
        if unit is not None:
            caveats.append(backend.adjudicate(unit))

    for merged in merged_allergies:
        crit = _allergy_criticality_disagreement(merged)
        if crit is not None:
            caveats.append(backend.adjudicate(crit))

    return caveats


def write_caveats(
    patient_id: str,
    caveats: list[Caveat],
    *,
    store_root: Path | None = None,
) -> Path:
    """Persist caveats as a FHIR Bundle (collection)."""
    root = (store_root or PATIENT_CONTEXT_STORE_ROOT) / _safe_id(patient_id)
    root.mkdir(parents=True, exist_ok=True)
    bundle = {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": c.to_fhir()} for c in caveats],
    }
    path = root / "caveats.json"
    path.write_text(json.dumps(bundle, indent=2), encoding="utf-8")
    return path


# ---------------------------------------------------------------------------
# Disagreement detectors
# ---------------------------------------------------------------------------


def _patient_voice_status_caveat(merged: MergedMedication) -> Caveat | None:
    """If the T2 patient-voice override fired, mint a caveat for it."""
    patient_sources = [s for s in merged.sources if is_patient_voice(s.meta_source) and s.status]
    if not patient_sources:
        return None
    patient_status = patient_sources[0].status
    dissent = [
        s for s in merged.sources
        if (not is_patient_voice(s.meta_source)) and s.status and s.status != patient_status
    ]
    if not dissent:
        return None
    merged_ref = getattr(merged, "_merged_ref", None) or f"MedicationRequest/merged-{merged.canonical_name.lower().replace(' ', '-')}"
    rationale = (
        f"Patient asserted {patient_status} most recently "
        f"({patient_sources[0].authored_on.date() if patient_sources[0].authored_on else 'today'}); "
        f"{len(dissent)} EHR source(s) carry a different status."
    )
    return Caveat(
        fact_path=f"{merged_ref}.status",
        verdict=patient_status,
        confidence="high",
        rationale=rationale,
        dissenting_sources=[s.source_request_ref for s in dissent],
        blocker=False,
    )


def _medication_dose_disagreement(merged: MergedMedication) -> Disagreement | None:
    """Detect display-string disagreement (a coarse proxy for dose)."""
    # Skip if only the patient-voice source has a display — no EHR-side conflict.
    ehr_sources = [s for s in merged.sources if not is_patient_voice(s.meta_source)]
    if len(ehr_sources) < 2:
        return None
    displays = {s.display.strip() for s in ehr_sources if s.display}
    if len(displays) <= 1:
        return None
    merged_ref = getattr(merged, "_merged_ref", None) or f"MedicationRequest/merged-{merged.canonical_name.lower().replace(' ', '-')}"
    return Disagreement(
        fact_path=f"{merged_ref}.dose",
        field_label="dose / display",
        sources=[
            {
                "label": s.source_label,
                "ref": s.source_request_ref,
                "value": s.display,
                "date": s.authored_on.isoformat() if s.authored_on else None,
            }
            for s in ehr_sources
        ],
    )


def _observation_unit_disagreement(merged: MergedObservation) -> Disagreement | None:
    """Detect unit mismatch across cross-source observations of the same LOINC."""
    units = {s.unit for s in merged.sources if s.unit}
    if len(units) <= 1:
        return None
    merged_ref = getattr(merged, "_merged_ref", None) or f"Observation/merged-{merged.canonical_name.lower().replace(' ', '-')}"
    return Disagreement(
        fact_path=f"{merged_ref}.unit",
        field_label="unit",
        sources=[
            {
                "label": s.source_label,
                "ref": s.source_observation_ref,
                "value": s.unit,
                "date": s.effective_date.isoformat() if s.effective_date else None,
            }
            for s in merged.sources
            if s.unit
        ],
    )


def _allergy_criticality_disagreement(merged: MergedAllergy) -> Disagreement | None:
    """Detect criticality mismatch (low vs high) across sources."""
    crits = {s.criticality for s in merged.sources if s.criticality}
    if len(crits) <= 1:
        return None
    merged_ref = getattr(merged, "_merged_ref", None) or f"AllergyIntolerance/merged-{merged.canonical_name.lower().replace(' ', '-')}"
    return Disagreement(
        fact_path=f"{merged_ref}.criticality",
        field_label="criticality",
        sources=[
            {
                "label": s.source_label,
                "ref": s.source_allergy_ref,
                "value": s.criticality,
                "date": s.recorded_date.isoformat() if s.recorded_date else None,
            }
            for s in merged.sources
            if s.criticality
        ],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _render_adjudicator_prompt(disagreement: Disagreement) -> str:
    sources_block = "\n".join(
        f"  - {s.get('label', '?')} [{s.get('ref', '?')}]: {s.get('value', '?')}"
        f" (recorded {s.get('date') or 'unknown'})"
        for s in disagreement.sources
    )
    return ADJUDICATOR_PROMPT_V1.format(
        fact_path=disagreement.fact_path,
        sources_block=sources_block,
    )


def _parse_adjudicator_json(text: str) -> dict[str, Any]:
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
            raise ValueError(f"adjudicator returned non-JSON: {text[:200]}")
        return json.loads(cleaned[start : end + 1])


def _safe_id(value: str) -> str:
    safe = re.sub(r"[^A-Za-z0-9_.-]+", "-", value).strip(".-")
    return safe[:120] or "patient"
