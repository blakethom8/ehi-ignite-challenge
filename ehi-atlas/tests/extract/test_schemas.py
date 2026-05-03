"""
tests.extract.test_schemas
~~~~~~~~~~~~~~~~~~~~~~~~~~

Tests for the Pydantic extraction schemas (Layer 2-B contract).

These tests validate that:
 - Realistic payloads matching the synthesized lab PDF parse cleanly
 - BBox.to_locator_string() produces the expected string format
 - ExtractionResult.extraction_confidence enforces [0.0, 1.0]
 - The discriminated union routes document payloads to the correct type
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from ehi_atlas.extract.schemas import (
    BBox,
    ExtractedClinicalNote,
    ExtractedCondition,
    ExtractedLabReport,
    ExtractedLabResult,
    ExtractionResult,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _creatinine_result() -> dict:
    """Minimal creatinine row matching the synthesized lab PDF expected output."""
    return {
        "test_name": "Creatinine",
        "loinc_code": "2160-0",
        "value_quantity": 1.4,
        "value_string": None,
        "unit": "mg/dL",
        "reference_range_low": 0.6,
        "reference_range_high": 1.3,
        "flag": "H",
        "effective_date": "2025-09-12",
        "bbox": {"page": 2, "x1": 72, "y1": 574, "x2": 540, "y2": 590},
    }


def _full_lab_report_payload() -> dict:
    """A full ExtractionResult payload for the synthesized lab PDF."""
    return {
        "document": {
            "document_type": "lab-report",
            "document_date": "2025-09-12",
            "ordering_provider": "Dr. Smith",
            "lab_name": "Quest Diagnostics",
            "patient_name_seen": "Rhett759 Rohan584",
            "results": [
                _creatinine_result(),
                {
                    "test_name": "Glucose",
                    "loinc_code": "2345-7",
                    "value_quantity": 102.0,
                    "value_string": None,
                    "unit": "mg/dL",
                    "reference_range_low": 70.0,
                    "reference_range_high": 99.0,
                    "flag": "H",
                    "effective_date": "2025-09-12",
                    "bbox": {"page": 2, "x1": 72, "y1": 610, "x2": 540, "y2": 626},
                },
            ],
        },
        "extraction_confidence": 0.97,
        "extraction_model": "claude-opus-4-7",
        "extraction_prompt_version": "v0.1.0",
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_extracted_lab_report_validates_realistic_payload():
    """A payload matching the synthesized lab PDF expected output validates cleanly."""
    result = ExtractionResult.model_validate(_full_lab_report_payload())

    assert isinstance(result.document, ExtractedLabReport)
    assert result.document.document_type == "lab-report"
    assert result.document.lab_name == "Quest Diagnostics"
    assert len(result.document.results) == 2

    creatinine = result.document.results[0]
    assert creatinine.test_name == "Creatinine"
    assert creatinine.loinc_code == "2160-0"
    assert creatinine.value_quantity == 1.4
    assert creatinine.unit == "mg/dL"
    assert creatinine.flag == "H"
    assert creatinine.reference_range_low == 0.6
    assert creatinine.reference_range_high == 1.3
    assert creatinine.effective_date == "2025-09-12"
    assert creatinine.bbox.page == 2
    assert creatinine.bbox.x1 == 72
    assert creatinine.bbox.y2 == 590

    assert result.extraction_confidence == 0.97
    assert result.extraction_model == "claude-opus-4-7"
    assert result.extraction_prompt_version == "v0.1.0"


def test_bbox_locator_string_format():
    """BBox.to_locator_string() produces the expected source-locator format."""
    bbox = BBox(page=2, x1=72, y1=574, x2=540, y2=590)
    assert bbox.to_locator_string() == "page=2;bbox=72,574,540,590"


def test_bbox_locator_string_rounds_floats():
    """Floats are formatted with zero decimal places in the locator string."""
    bbox = BBox(page=1, x1=72.4, y1=574.6, x2=540.0, y2=590.1)
    assert bbox.to_locator_string() == "page=1;bbox=72,575,540,590"


def test_extraction_confidence_must_be_in_range():
    """extraction_confidence values outside [0.0, 1.0] raise ValidationError."""
    base = _full_lab_report_payload()

    # too high
    base["extraction_confidence"] = 1.1
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(base)

    # too low
    base["extraction_confidence"] = -0.1
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate(base)

    # boundary values are accepted
    base["extraction_confidence"] = 0.0
    ExtractionResult.model_validate(base)  # no error

    base["extraction_confidence"] = 1.0
    ExtractionResult.model_validate(base)  # no error


def test_discriminated_union_routes_correctly():
    """document_type=lab-report routes to ExtractedLabReport; clinical-note routes to ExtractedClinicalNote."""
    lab_payload = _full_lab_report_payload()
    lab_result = ExtractionResult.model_validate(lab_payload)
    assert isinstance(lab_result.document, ExtractedLabReport)

    note_payload = {
        "document": {
            "document_type": "clinical-note",
            "note_date": "2026-01-15",
            "author": "Dr. Patel",
            "extracted_conditions": [
                {
                    "label": "Chest tightness on exertion",
                    "snomed_ct_code": "23924001",
                    "source_text": (
                        "occasional chest tightness on exertion since "
                        "approximately November of last year"
                    ),
                }
            ],
            "extracted_symptoms": [],
        },
        "extraction_confidence": 0.88,
        "extraction_model": "claude-sonnet-4-6",
        "extraction_prompt_version": "v0.1.0",
    }
    note_result = ExtractionResult.model_validate(note_payload)
    assert isinstance(note_result.document, ExtractedClinicalNote)
    assert note_result.document.document_type == "clinical-note"
    assert len(note_result.document.extracted_conditions) == 1
    cond = note_result.document.extracted_conditions[0]
    assert cond.snomed_ct_code == "23924001"


def test_lab_result_null_loinc_accepted():
    """loinc_code=None is valid — not every test will be in the showcase subset."""
    payload = _full_lab_report_payload()
    payload["document"]["results"][0]["loinc_code"] = None
    result = ExtractionResult.model_validate(payload)
    assert result.document.results[0].loinc_code is None


def test_lab_result_requires_bbox():
    """bbox is required on ExtractedLabResult; omitting it raises ValidationError."""
    row = _creatinine_result()
    del row["bbox"]
    with pytest.raises(ValidationError):
        ExtractedLabResult.model_validate(row)


def test_bbox_page_must_be_positive():
    """BBox.page must be >= 1."""
    with pytest.raises(ValidationError):
        BBox(page=0, x1=0, y1=0, x2=100, y2=100)


def test_extracted_condition_requires_source_text():
    """ExtractedCondition.source_text is required."""
    with pytest.raises(ValidationError):
        ExtractedCondition.model_validate({"label": "Hypertension"})
