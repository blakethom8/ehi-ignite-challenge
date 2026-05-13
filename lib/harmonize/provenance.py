"""FHIR Provenance resource minter.

Each merged Observation produces one FHIR Provenance resource recording
the sources that backed it. The Provenance graph (across all merged
facts) is the Atlas wedge — every clinical fact in the canonical record
links back to the source(s) it came from.

Atlas-canonical Provenance Extension URLs (frozen in v1):

- ``http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-label``
  Human-readable source name (e.g. ``"Cedars-Sinai"``).
- ``http://atlas.healthcaredataai.com/fhir/StructureDefinition/harmonize-activity``
  What harmonization step produced this edge (``loinc-match`` |
  ``name-match`` | ``unit-normalize`` | ``passthrough``).

These URLs are part of the public Atlas vocabulary; downstream consumers
(clinician UI, agent assistant) read these extensions to render lineage.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from .models import (
    MergedAllergy,
    MergedCondition,
    MergedImmunization,
    MergedMedication,
    MergedObservation,
)


SOURCE_LABEL_URL = (
    "http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-label"
)
HARMONIZE_ACTIVITY_URL = (
    "http://atlas.healthcaredataai.com/fhir/StructureDefinition/harmonize-activity"
)
# Phase 1 only mints this extension on MergedMedication Provenance, on
# the entity for the patient-voice source, when the patient-voice
# status assertion overrode at least one disagreeing EHR source. See
# lib.harmonize.source_weights for the rule code vocabulary and
# docs/architecture/context/LLM-CONTEXT-AUGMENTATION-PLAN.md §3.5.
RESOLUTION_RULE_URL = (
    "http://atlas.healthcaredataai.com/fhir/StructureDefinition/resolution-rule"
)


def mint_provenance(
    merged: (
        MergedObservation
        | MergedCondition
        | MergedMedication
        | MergedAllergy
        | MergedImmunization
    ),
) -> dict[str, Any]:
    """Produce a FHIR Provenance resource for one merged record.

    Accepts every ``Merged*`` model in ``lib.harmonize.models``.

    The resource follows FHIR R4 ``Provenance``:

    - ``target``: the merged Observation reference.
    - ``recorded``: when the harmonizer ran.
    - ``entity``: one entry per source observation, with role ``source``.
    - ``activity``: a CodeableConcept naming the harmonization step.
    - Custom Atlas extensions on each ``entity`` carry source label +
      harmonize-activity for fast UI rendering.
    """
    target_ref = getattr(merged, "_merged_ref", None) or (
        f"Observation/merged-{merged.canonical_name.lower().replace(' ', '-')}"
    )

    # Use the most-recent edge's recorded time as the resource's recorded.
    if merged.provenance:
        recorded = max(e.recorded for e in merged.provenance).isoformat()
    else:
        recorded = datetime.now().isoformat()

    # Compute which source_refs (if any) get the patient-voice status
    # override extension. Phase 1: MergedMedication only; the rule fires
    # when a patient-voice source asserted a status and at least one
    # non-patient source asserted a different status.
    override_source_refs = _patient_voice_status_override_refs(merged)

    entities = []
    for edge in merged.provenance:
        ext = [
            {"url": SOURCE_LABEL_URL, "valueString": edge.source_label},
            {"url": HARMONIZE_ACTIVITY_URL, "valueString": edge.activity},
        ]
        if edge.source_ref in override_source_refs:
            ext.append(
                {
                    "url": RESOLUTION_RULE_URL,
                    "valueString": "patient-voice-status-override",
                }
            )
        entities.append(
            {
                "role": "source",
                "what": {"reference": edge.source_ref},
                "extension": ext,
            }
        )

    # Activity: roll up the strongest activity across edges. Coded matches
    # beat name matches; unit-normalize beats passthrough.
    rank = {
        "loinc-match": 5,
        "snomed-match": 5,
        "rxnorm-match": 5,
        "cvx-match": 5,
        "icd10-match": 4,
        "icd9-match": 3,
        "name-match": 3,
        "name-bridge": 3,
        "drug-name-match": 3,
        "drug-name-bridge": 3,
        "unit-normalize": 2,
        "passthrough": 1,
    }
    if merged.provenance:
        top = max(merged.provenance, key=lambda e: rank.get(e.activity, 0)).activity
    else:
        top = "passthrough"

    return {
        "resourceType": "Provenance",
        "target": [{"reference": target_ref}],
        "recorded": recorded,
        "activity": {
            "coding": [
                {
                    "system": "http://atlas.healthcaredataai.com/fhir/CodeSystem/harmonize-activity",
                    "code": top,
                    "display": top.replace("-", " ").title(),
                }
            ]
        },
        "agent": [
            {
                "type": {
                    "coding": [
                        {
                            "system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                            "code": "assembler",
                            "display": "Assembler",
                        }
                    ]
                },
                "who": {"display": "EHI Atlas Harmonizer v1"},
            }
        ],
        "entity": entities,
    }


def _patient_voice_status_override_refs(merged: Any) -> set[str]:
    """Return the set of ``source_ref`` strings on which to attach the
    ``patient-voice-status-override`` resolution-rule extension.

    Phase 1 fires the rule when **all** of the following hold for a
    ``MergedMedication``:

    1. At least one source is patient-voice (``meta_source`` prefix
       matches ``patient-context://``) and has a non-empty ``status``.
    2. At least one non-patient source has a status different from the
       patient-voice status.

    The set is empty for every other merged type or whenever the
    conditions don't hold, so this function is safe to call
    unconditionally from :func:`mint_provenance`.
    """
    if not isinstance(merged, MergedMedication):
        return set()
    from .source_weights import is_patient_voice

    patient_sources = [
        s for s in merged.sources if is_patient_voice(s.meta_source) and s.status
    ]
    if not patient_sources:
        return set()
    patient_status = patient_sources[0].status
    others_disagree = any(
        (not is_patient_voice(s.meta_source))
        and s.status
        and s.status != patient_status
        for s in merged.sources
    )
    if not others_disagree:
        return set()
    return {s.source_request_ref for s in patient_sources}


def mint_provenance_bundle(
    merged_list: (
        list[MergedObservation]
        | list[MergedCondition]
        | list[MergedMedication]
        | list[MergedAllergy]
        | list[MergedImmunization]
    ),
) -> list[dict[str, Any]]:
    """Mint Provenance resources for a list of merged records.

    Accepts a list of either ``MergedObservation`` or ``MergedCondition``.
    Returns a flat list of FHIR Provenance dicts. Wrap them into a
    ``Bundle`` of type ``collection`` if you need a transmissible package.
    """
    return [mint_provenance(m) for m in merged_list]
