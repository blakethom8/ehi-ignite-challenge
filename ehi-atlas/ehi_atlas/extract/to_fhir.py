"""
ehi_atlas.extract.to_fhir
~~~~~~~~~~~~~~~~~~~~~~~~~

Converters from the extraction intermediate format (``schemas.py``) to FHIR
resource dicts.

These functions are **deterministic** — same extraction input always produces the
same FHIR dict.  They do not call the LLM, do not hit the network, and have no
side effects.

Layer 2 finalize wraps the dicts into a Bundle and applies profile validation
(BundleValidator).  These functions do not validate — they produce well-shaped
FHIR that will pass validation.

Extension URL base (matches PROVENANCE-SPEC.md):
  https://ehi-atlas.example/fhir/StructureDefinition/
"""

from __future__ import annotations

from typing import Any

from .schemas import BBox, ExtractedCondition, ExtractedLabResult

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_EXT_BASE = "https://ehi-atlas.example/fhir/StructureDefinition"
_TAG_SOURCE_SYSTEM = "https://ehi-atlas.example/fhir/CodeSystem/source-tag"
_TAG_LIFECYCLE_SYSTEM = "https://ehi-atlas.example/fhir/CodeSystem/lifecycle"
_LLM_MODEL_SYSTEM = "https://ehi-atlas.example/fhir/CodeSystem/llm-model"

_PROFILE_LAB = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab"
)
_PROFILE_CONDITION = (
    "http://hl7.org/fhir/us/core/StructureDefinition/us-core-condition"
)

_INTERP_DISPLAY: dict[str, str] = {
    "H": "High",
    "L": "Low",
    "N": "Normal",
    "HH": "Critical High",
    "LL": "Critical Low",
    "A": "Abnormal",
}


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _extraction_extensions(
    model: str,
    confidence: float,
    prompt_version: str,
    source_attachment_id: str,
    bbox: BBox | None,
) -> list[dict[str, Any]]:
    """Build the four-to-five extraction meta.extension entries."""
    exts: list[dict[str, Any]] = [
        {
            "url": f"{_EXT_BASE}/extraction-model",
            "valueCoding": {
                "system": _LLM_MODEL_SYSTEM,
                "code": model,
            },
        },
        {
            "url": f"{_EXT_BASE}/extraction-confidence",
            "valueDecimal": confidence,
        },
        {
            "url": f"{_EXT_BASE}/extraction-prompt-version",
            "valueString": prompt_version,
        },
        {
            "url": f"{_EXT_BASE}/source-attachment",
            "valueReference": {"reference": f"Binary/{source_attachment_id}"},
        },
    ]
    if bbox is not None:
        exts.append(
            {
                "url": f"{_EXT_BASE}/source-locator",
                "valueString": bbox.to_locator_string(),
            }
        )
    return exts


def _meta(
    profile: str,
    source_uri: str,
    source_tag_code: str,
    model: str,
    confidence: float,
    prompt_version: str,
    source_attachment_id: str,
    bbox: BBox | None,
) -> dict[str, Any]:
    return {
        "profile": [profile],
        "source": source_uri,
        "tag": [
            {"system": _TAG_SOURCE_SYSTEM, "code": source_tag_code},
            {"system": _TAG_LIFECYCLE_SYSTEM, "code": "extracted"},
        ],
        "extension": _extraction_extensions(
            model=model,
            confidence=confidence,
            prompt_version=prompt_version,
            source_attachment_id=source_attachment_id,
            bbox=bbox,
        ),
    }


# ---------------------------------------------------------------------------
# Public converters
# ---------------------------------------------------------------------------


def lab_result_to_observation(
    result: ExtractedLabResult,
    patient_id: str,
    source_attachment_id: str,
    model: str,
    confidence: float,
    prompt_version: str,
    source_tag: str = "lab-pdf",
) -> dict[str, Any]:
    """Convert an ``ExtractedLabResult`` to a FHIR Observation dict.

    Args:
        result:               The extracted lab result.
        patient_id:           FHIR Patient resource ID (no ``Patient/`` prefix).
        source_attachment_id: ID of the Binary resource holding the source PDF.
        model:                LLM model identifier (e.g. ``"claude-opus-4-7"``).
        confidence:           Overall extraction confidence 0–1.
        prompt_version:       Frozen prompt version (e.g. ``"v0.1.0"``).
        source_tag:           source-tag code for meta.tag (default ``"lab-pdf"``).

    Returns:
        A FHIR Observation dict (no ``id`` — caller assigns IDs).
    """
    obs: dict[str, Any] = {
        "resourceType": "Observation",
        "status": "final",
        "category": [
            {
                "coding": [
                    {
                        "system": (
                            "http://terminology.hl7.org/CodeSystem/"
                            "observation-category"
                        ),
                        "code": "laboratory",
                        "display": "Laboratory",
                    }
                ]
            }
        ],
        "subject": {"reference": f"Patient/{patient_id}"},
        "meta": _meta(
            profile=_PROFILE_LAB,
            source_uri=f"extracted://lab-report/{source_attachment_id}",
            source_tag_code=source_tag,
            model=model,
            confidence=confidence,
            prompt_version=prompt_version,
            source_attachment_id=source_attachment_id,
            bbox=result.bbox,
        ),
    }

    # --- code ---
    code_block: dict[str, Any] = {"text": result.test_name}
    if result.loinc_code:
        code_block["coding"] = [
            {
                "system": "http://loinc.org",
                "code": result.loinc_code,
            }
        ]
    obs["code"] = code_block

    # --- effective date ---
    if result.effective_date:
        obs["effectiveDateTime"] = result.effective_date

    # --- value ---
    if result.value_quantity is not None:
        vq: dict[str, Any] = {"value": result.value_quantity}
        if result.unit:
            vq["unit"] = result.unit
            vq["system"] = "http://unitsofmeasure.org"
            vq["code"] = result.unit
        obs["valueQuantity"] = vq
    elif result.value_string is not None:
        obs["valueString"] = result.value_string

    # --- reference range ---
    if result.reference_range_low is not None or result.reference_range_high is not None:
        rr: dict[str, Any] = {}
        if result.reference_range_low is not None:
            low: dict[str, Any] = {"value": result.reference_range_low}
            if result.unit:
                low.update(
                    {
                        "unit": result.unit,
                        "system": "http://unitsofmeasure.org",
                        "code": result.unit,
                    }
                )
            rr["low"] = low
        if result.reference_range_high is not None:
            high: dict[str, Any] = {"value": result.reference_range_high}
            if result.unit:
                high.update(
                    {
                        "unit": result.unit,
                        "system": "http://unitsofmeasure.org",
                        "code": result.unit,
                    }
                )
            rr["high"] = high
        obs["referenceRange"] = [rr]

    # --- interpretation flag ---
    if result.flag:
        obs["interpretation"] = [
            {
                "coding": [
                    {
                        "system": (
                            "http://terminology.hl7.org/CodeSystem/"
                            "v3-ObservationInterpretation"
                        ),
                        "code": result.flag,
                        "display": _INTERP_DISPLAY.get(result.flag, result.flag),
                    }
                ]
            }
        ]

    return obs


def condition_to_fhir(
    extracted: ExtractedCondition,
    patient_id: str,
    source_attachment_id: str,
    model: str,
    confidence: float,
    prompt_version: str,
    source_tag: str = "synthesized-clinical-note",
) -> dict[str, Any]:
    """Convert an ``ExtractedCondition`` to a FHIR Condition dict.

    Args:
        extracted:            The extracted condition.
        patient_id:           FHIR Patient resource ID (no ``Condition/`` prefix).
        source_attachment_id: ID of the Binary resource holding the source note.
        model:                LLM model identifier.
        confidence:           Overall extraction confidence 0–1.
        prompt_version:       Frozen prompt version.
        source_tag:           source-tag code (default ``"synthesized-clinical-note"``).

    Returns:
        A FHIR Condition dict (no ``id`` — caller assigns IDs).
    """
    condition: dict[str, Any] = {
        "resourceType": "Condition",
        "subject": {"reference": f"Patient/{patient_id}"},
        "clinicalStatus": {
            "coding": [
                {
                    "system": (
                        "http://terminology.hl7.org/CodeSystem/"
                        "condition-clinical"
                    ),
                    "code": "active",
                }
            ]
        },
        "verificationStatus": {
            "coding": [
                {
                    "system": (
                        "http://terminology.hl7.org/CodeSystem/"
                        "condition-ver-status"
                    ),
                    "code": "unconfirmed",
                    "display": "Unconfirmed",
                }
            ]
        },
        "meta": _meta(
            profile=_PROFILE_CONDITION,
            source_uri=f"extracted://clinical-note/{source_attachment_id}",
            source_tag_code=source_tag,
            model=model,
            confidence=confidence,
            prompt_version=prompt_version,
            source_attachment_id=source_attachment_id,
            bbox=extracted.bbox,
        ),
    }

    # --- code ---
    code_block: dict[str, Any] = {"text": extracted.label}
    codings: list[dict[str, Any]] = []
    if extracted.snomed_ct_code:
        codings.append(
            {
                "system": "http://snomed.info/sct",
                "code": extracted.snomed_ct_code,
            }
        )
    if extracted.icd_10_cm_code:
        codings.append(
            {
                "system": "http://hl7.org/fhir/sid/icd-10-cm",
                "code": extracted.icd_10_cm_code,
            }
        )
    if codings:
        code_block["coding"] = codings
    condition["code"] = code_block

    # --- onset ---
    if extracted.onset_date:
        condition["onsetDateTime"] = extracted.onset_date

    # --- preserve source text as a note ---
    condition["note"] = [{"text": extracted.source_text}]

    return condition
