"""Temporal alignment for Layer 3 harmonization.

Different FHIR resource types have different "clinical time" fields. Some
fields look like clinical time but are actually metadata (notably
DocumentReference.date — that's index-time, not care-time). This module
provides the precedence rules for extracting the canonical clinical
timestamp from any FHIR R4 resource, normalized to UTC.

Per Mandel's SKILL.md: never use docRef.date as clinical time. Walk:
    docRef.context.period.start → linked Encounter.period.start → uncertain
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Literal


# ---------------------------------------------------------------------------
# Extension URL constants
# ---------------------------------------------------------------------------

EXT_BASE = "https://ehi-atlas.example/fhir/StructureDefinition"
EXT_CLINICAL_TIME = f"{EXT_BASE}/clinical-time"
EXT_CLINICAL_TIME_CONFIDENCE = f"{EXT_BASE}/clinical-time-confidence"
EXT_CLINICAL_TIME_SOURCE = f"{EXT_BASE}/clinical-time-source-field"


# ---------------------------------------------------------------------------
# Types
# ---------------------------------------------------------------------------

# Confidence in the recovered timestamp:
# - "high": resource has a primary timing field that's clearly clinical
# - "medium": fell back to a secondary field (e.g. context.period.start on a DocRef)
# - "low": no strong timing signal; we used a metadata field as a last resort
# - "uncertain": no timing recoverable
TimingConfidence = Literal["high", "medium", "low", "uncertain"]


@dataclass(frozen=True)
class ClinicalTime:
    """A timestamp with its confidence and the field path it was recovered from."""

    timestamp: datetime | None  # always UTC tz-aware; None if uncertain
    confidence: TimingConfidence
    source_field: str  # e.g. "Observation.effectiveDateTime"


# ---------------------------------------------------------------------------
# UTC normalization
# ---------------------------------------------------------------------------


def normalize_to_utc(value: str | datetime) -> datetime:
    """Parse FHIR-style ISO 8601 dates/datetimes into UTC tz-aware datetime.

    Accepts:
      - "2025-09-12"                    → 2025-09-12T00:00:00+00:00
      - "2025-09-12T14:30:00Z"          → 2025-09-12T14:30:00+00:00
      - "2025-09-12T14:30:00-04:00"     → 2025-09-12T18:30:00+00:00
      - tz-naive datetimes              → assumed UTC
    """
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # Assume UTC for tz-naive datetime inputs.
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    # String path — handle FHIR date-only "YYYY-MM-DD" before trying fromisoformat
    s = value.strip()
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        # Date-only: midnight UTC
        return datetime(int(s[0:4]), int(s[5:7]), int(s[8:10]), tzinfo=timezone.utc)

    # Normalize "Z" suffix for Python < 3.11 where fromisoformat doesn't accept it
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _try_field(resource: dict, *field_path: str) -> str | None:
    """Walk a nested dict path; return the string value or None."""
    node = resource
    for key in field_path:
        if not isinstance(node, dict):
            return None
        node = node.get(key)
        if node is None:
            return None
    return node if isinstance(node, str) else None


def _make(raw: str | None, confidence: TimingConfidence, field: str) -> ClinicalTime:
    """Build a ClinicalTime from a raw string (may be None → uncertain)."""
    if raw is None:
        return ClinicalTime(None, "uncertain", field)
    try:
        ts = normalize_to_utc(raw)
        return ClinicalTime(ts, confidence, field)
    except (ValueError, TypeError):
        return ClinicalTime(None, "uncertain", field)


# ---------------------------------------------------------------------------
# Per-resource extractors
# ---------------------------------------------------------------------------


def clinical_time_for_observation(resource: dict) -> ClinicalTime:
    """Observation: effectiveDateTime (high) → effectivePeriod.start (high) → uncertain."""
    edt = _try_field(resource, "effectiveDateTime")
    if edt:
        return _make(edt, "high", "Observation.effectiveDateTime")

    eps = _try_field(resource, "effectivePeriod", "start")
    if eps:
        return _make(eps, "high", "Observation.effectivePeriod.start")

    return ClinicalTime(None, "uncertain", "Observation (no effective timing)")


def clinical_time_for_condition(resource: dict) -> ClinicalTime:
    """Condition: onsetDateTime (high) → onsetPeriod.start (high) → recordedDate (low) → uncertain.

    recordedDate is when the condition was *recorded* (metadata), not onset.
    """
    odt = _try_field(resource, "onsetDateTime")
    if odt:
        return _make(odt, "high", "Condition.onsetDateTime")

    ops = _try_field(resource, "onsetPeriod", "start")
    if ops:
        return _make(ops, "high", "Condition.onsetPeriod.start")

    # recordedDate is metadata time; only use as last resort with low confidence
    rd = _try_field(resource, "recordedDate")
    if rd:
        return _make(rd, "low", "Condition.recordedDate (metadata; onset preferred)")

    return ClinicalTime(None, "uncertain", "Condition (no onset or recordedDate)")


def clinical_time_for_encounter(resource: dict) -> ClinicalTime:
    """Encounter: period.start (high) → period.end (medium) → uncertain."""
    ps = _try_field(resource, "period", "start")
    if ps:
        return _make(ps, "high", "Encounter.period.start")

    pe = _try_field(resource, "period", "end")
    if pe:
        return _make(pe, "medium", "Encounter.period.end")

    return ClinicalTime(None, "uncertain", "Encounter (no period)")


def clinical_time_for_diagnostic_report(resource: dict) -> ClinicalTime:
    """DiagnosticReport: effectiveDateTime (high) → effectivePeriod.start (high) → issued (low)."""
    edt = _try_field(resource, "effectiveDateTime")
    if edt:
        return _make(edt, "high", "DiagnosticReport.effectiveDateTime")

    eps = _try_field(resource, "effectivePeriod", "start")
    if eps:
        return _make(eps, "high", "DiagnosticReport.effectivePeriod.start")

    # issued = when the report was released; clinical time still, but secondary
    issued = _try_field(resource, "issued")
    if issued:
        return _make(issued, "low", "DiagnosticReport.issued (release time, not observation time)")

    return ClinicalTime(None, "uncertain", "DiagnosticReport (no effective timing)")


def clinical_time_for_procedure(resource: dict) -> ClinicalTime:
    """Procedure: performedDateTime (high) → performedPeriod.start (high) → uncertain."""
    pdt = _try_field(resource, "performedDateTime")
    if pdt:
        return _make(pdt, "high", "Procedure.performedDateTime")

    pps = _try_field(resource, "performedPeriod", "start")
    if pps:
        return _make(pps, "high", "Procedure.performedPeriod.start")

    return ClinicalTime(None, "uncertain", "Procedure (no performed timing)")


def clinical_time_for_medication_request(resource: dict) -> ClinicalTime:
    """MedicationRequest: authoredOn is "when prescribed" (high for prescription time).

    NOTE: authoredOn is the prescription date, not the administration date.
    For "when the patient took it," prefer MedicationAdministration.effective*.
    Here we return authoredOn as high-confidence prescription time, which is
    the closest clinical timestamp available on MedicationRequest itself.
    """
    aon = _try_field(resource, "authoredOn")
    if aon:
        return _make(aon, "high", "MedicationRequest.authoredOn (prescription time)")

    return ClinicalTime(None, "uncertain", "MedicationRequest (no authoredOn)")


def clinical_time_for_allergy_intolerance(resource: dict) -> ClinicalTime:
    """AllergyIntolerance: onsetDateTime (high) → recordedDate (low) → uncertain.

    recordedDate is metadata (when recorded in system); clinical onset is onsetDateTime.
    """
    odt = _try_field(resource, "onsetDateTime")
    if odt:
        return _make(odt, "high", "AllergyIntolerance.onsetDateTime")

    ops = _try_field(resource, "onsetPeriod", "start")
    if ops:
        return _make(ops, "high", "AllergyIntolerance.onsetPeriod.start")

    # recordedDate is metadata time (admin); use with low confidence as last resort
    rd = _try_field(resource, "recordedDate")
    if rd:
        return _make(rd, "low", "AllergyIntolerance.recordedDate (metadata; onset preferred)")

    return ClinicalTime(None, "uncertain", "AllergyIntolerance (no onset or recordedDate)")


def clinical_time_for_immunization(resource: dict) -> ClinicalTime:
    """Immunization: occurrenceDateTime (high) → occurrenceString best-effort → uncertain."""
    odt = _try_field(resource, "occurrenceDateTime")
    if odt:
        return _make(odt, "high", "Immunization.occurrenceDateTime")

    # occurrenceString is a free-text date; we can't reliably parse it → skip
    return ClinicalTime(None, "uncertain", "Immunization (no occurrenceDateTime)")


def clinical_time_for_document_reference(
    resource: dict,
    encounter_lookup: dict[str, dict] | None = None,
) -> ClinicalTime:
    """Apply the Mandel precedence rule for DocumentReference clinical time.

    NEVER use docRef.date — that is index/import time, not clinical time.

    Precedence:
        1. context.period.start          (medium: contextually supplied clinical time)
        2. linked Encounter.period.start (medium: inferred from encounter)
        3. uncertain                     (NEVER docRef.date)
    """
    # 1. context.period.start
    cps = _try_field(resource, "context", "period", "start")
    if cps:
        return _make(cps, "medium", "DocumentReference.context.period.start")

    # 2. Walk linked Encounter
    if encounter_lookup:
        enc_refs: list = resource.get("context", {}).get("encounter", []) or []
        for enc_ref_obj in enc_refs:
            ref_str = enc_ref_obj.get("reference") if isinstance(enc_ref_obj, dict) else None
            if ref_str and ref_str in encounter_lookup:
                enc = encounter_lookup[ref_str]
                enc_ps = _try_field(enc, "period", "start")
                if enc_ps:
                    return _make(
                        enc_ps,
                        "medium",
                        f"DocumentReference → linked {ref_str} Encounter.period.start",
                    )

    # 3. Uncertain — NEVER fall through to docRef.date
    return ClinicalTime(
        None,
        "uncertain",
        "DocumentReference (no context.period.start or linked Encounter; docRef.date intentionally excluded)",
    )


# ---------------------------------------------------------------------------
# Dispatch table
# ---------------------------------------------------------------------------

_DISPATCH: dict = {
    "Observation": clinical_time_for_observation,
    "Condition": clinical_time_for_condition,
    "Encounter": clinical_time_for_encounter,
    "DiagnosticReport": clinical_time_for_diagnostic_report,
    "Procedure": clinical_time_for_procedure,
    "MedicationRequest": clinical_time_for_medication_request,
    "AllergyIntolerance": clinical_time_for_allergy_intolerance,
    "Immunization": clinical_time_for_immunization,
    "DocumentReference": clinical_time_for_document_reference,
}


def clinical_time(resource: dict, encounter_lookup: dict | None = None) -> ClinicalTime:
    """Dispatch on resource.resourceType and return the canonical clinical timestamp."""
    rt = resource.get("resourceType")
    handler = _DISPATCH.get(rt)
    if handler is None:
        return ClinicalTime(None, "uncertain", f"{rt} (no temporal handler)")
    if rt == "DocumentReference":
        return handler(resource, encounter_lookup or {})
    return handler(resource)


# ---------------------------------------------------------------------------
# Bulk normalization
# ---------------------------------------------------------------------------


def _ensure_meta(resource: dict) -> dict:
    """Return (and populate if missing) the meta dict on a resource."""
    if "meta" not in resource:
        resource["meta"] = {}
    return resource["meta"]


def _find_existing_clinical_time_ext(extensions: list) -> int | None:
    """Return the index of the first clinical-time extension block, or None."""
    for i, ext in enumerate(extensions):
        if isinstance(ext, dict) and ext.get("url") == EXT_CLINICAL_TIME:
            return i
    return None


def normalize_bundle_temporal(bundle: dict) -> dict:
    """Walk every entry, compute clinical_time(), attach as meta extensions.

    Adds (or replaces if already present) three extensions in resource.meta.extension:
        {"url": EXT_CLINICAL_TIME,            "valueDateTime": "<UTC ISO 8601>"}
        {"url": EXT_CLINICAL_TIME_CONFIDENCE, "valueCode": "high|medium|low|uncertain"}
        {"url": EXT_CLINICAL_TIME_SOURCE,     "valueString": "Observation.effectiveDateTime"}

    When confidence is "uncertain" the valueDateTime extension is omitted (no timestamp
    to store), but the confidence and source-field extensions are always written.

    Pre-builds an encounter_lookup from the bundle entries for DocumentReference resolution.

    Returns the modified bundle (also mutates in place).
    """
    entries: list = bundle.get("entry", []) or []

    # Build encounter lookup keyed by "Encounter/<id>"
    encounter_lookup: dict[str, dict] = {}
    for entry in entries:
        resource = entry.get("resource") if isinstance(entry, dict) else None
        if resource and resource.get("resourceType") == "Encounter":
            rid = resource.get("id")
            if rid:
                encounter_lookup[f"Encounter/{rid}"] = resource

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if not isinstance(resource, dict):
            continue

        ct = clinical_time(resource, encounter_lookup)
        meta = _ensure_meta(resource)
        extensions: list = meta.setdefault("extension", [])

        # Remove any previous clinical-time extensions (idempotency)
        meta["extension"] = [
            ext
            for ext in extensions
            if isinstance(ext, dict)
            and ext.get("url") not in {
                EXT_CLINICAL_TIME,
                EXT_CLINICAL_TIME_CONFIDENCE,
                EXT_CLINICAL_TIME_SOURCE,
            }
        ]

        # Append the three clinical-time extensions
        if ct.timestamp is not None:
            meta["extension"].append(
                {
                    "url": EXT_CLINICAL_TIME,
                    "valueDateTime": ct.timestamp.strftime("%Y-%m-%dT%H:%M:%S+00:00"),
                }
            )

        meta["extension"].append(
            {"url": EXT_CLINICAL_TIME_CONFIDENCE, "valueCode": ct.confidence}
        )
        meta["extension"].append(
            {"url": EXT_CLINICAL_TIME_SOURCE, "valueString": ct.source_field}
        )

    return bundle
