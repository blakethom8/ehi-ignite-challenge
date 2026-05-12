"""Source-weight table for resolving cross-source disagreements.

Phase 1 supports exactly one weighted field: ``medication.status``.
Patient-voice sources (``meta.source`` starting with ``patient-context://``)
win over EHR sources because EHR active/stopped flags are frequently
stale — patients know what they actually take.

Other fields (dose, frequency, codes, dates) use default weight 1.0
across all sources, so the existing harmonizer behavior is preserved.

Phase 2 (P7 in the plan) widens this to a per-(resource-type, field,
source-kind) matrix. Keep this surface narrow until then.
"""

from __future__ import annotations

from typing import Final


PATIENT_VOICE_SOURCE_PREFIX: Final[str] = "patient-context://"


# Atlas extension URL attached to a Provenance entity when a non-default
# source-weight rule fired during merge. Phase 1 has exactly one rule
# code ("patient-voice-status-override") on exactly one field
# ("medication.status"); Phase 2 grows this vocabulary.
RESOLUTION_RULE_URL: Final[str] = (
    "http://atlas.healthcaredataai.com/fhir/StructureDefinition/resolution-rule"
)
RESOLUTION_RULE_PATIENT_VOICE_STATUS_OVERRIDE: Final[str] = "patient-voice-status-override"


# Single weighted field in Phase 1.
MEDICATION_STATUS_FIELD: Final[str] = "medication.status"


# Mapping of (source prefix → weight) for ``medication.status``. The
# special key ``"*"`` is the default weight applied to any source whose
# meta.source doesn't match a more specific prefix.
MEDICATION_STATUS_WEIGHTS: Final[dict[str, float]] = {
    PATIENT_VOICE_SOURCE_PREFIX: 5.0,
    "*": 1.0,
}


def is_patient_voice(meta_source: str | None) -> bool:
    """True iff ``meta_source`` originates from a patient-context session."""
    return bool(meta_source) and meta_source.startswith(PATIENT_VOICE_SOURCE_PREFIX)


def weight_for_source(meta_source: str | None, field: str) -> float:
    """Return the merge weight for a (source, field) pair.

    Defaults to 1.0. Phase 1 only differentiates ``medication.status``.
    """
    if field != MEDICATION_STATUS_FIELD:
        return MEDICATION_STATUS_WEIGHTS["*"]
    if is_patient_voice(meta_source):
        return MEDICATION_STATUS_WEIGHTS[PATIENT_VOICE_SOURCE_PREFIX]
    return MEDICATION_STATUS_WEIGHTS["*"]
