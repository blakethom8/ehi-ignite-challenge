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

from .models import MergedCondition, MergedMedication, MergedObservation


SOURCE_LABEL_URL = (
    "http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-label"
)
HARMONIZE_ACTIVITY_URL = (
    "http://atlas.healthcaredataai.com/fhir/StructureDefinition/harmonize-activity"
)


def mint_provenance(
    merged: MergedObservation | MergedCondition | MergedMedication,
) -> dict[str, Any]:
    """Produce a FHIR Provenance resource for one merged record.

    Accepts ``MergedObservation``, ``MergedCondition``, or ``MergedMedication``.

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

    entities = []
    for edge in merged.provenance:
        entities.append(
            {
                "role": "source",
                "what": {"reference": edge.source_ref},
                "extension": [
                    {"url": SOURCE_LABEL_URL, "valueString": edge.source_label},
                    {"url": HARMONIZE_ACTIVITY_URL, "valueString": edge.activity},
                ],
            }
        )

    # Activity: roll up the strongest activity across edges. Coded matches
    # beat name matches; unit-normalize beats passthrough.
    rank = {
        "loinc-match": 5,
        "snomed-match": 5,
        "rxnorm-match": 5,
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


def mint_provenance_bundle(
    merged_list: list[MergedObservation] | list[MergedCondition] | list[MergedMedication],
) -> list[dict[str, Any]]:
    """Mint Provenance resources for a list of merged records.

    Accepts a list of either ``MergedObservation`` or ``MergedCondition``.
    Returns a flat list of FHIR Provenance dicts. Wrap them into a
    ``Bundle`` of type ``collection`` if you need a transmissible package.
    """
    return [mint_provenance(m) for m in merged_list]
