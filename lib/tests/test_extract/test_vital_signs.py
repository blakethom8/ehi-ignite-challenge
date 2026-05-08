"""Tests for the vital-signs extraction pass in MultiPassFHIRPipeline.

Verifies schema validation, LOINC mapping correctness, FHIR category,
valueQuantity emission, the BP two-entry pattern, and doc-context date
fallback.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lib.extract.pipelines.multipass_fhir import (
    DocumentContext,
    MultiPassFHIRPipeline,
    VitalSignEntry,
    VitalSignExtraction,
    _VITAL_LOINC_MAP,
)


def _new_pipeline() -> MultiPassFHIRPipeline:
    """Construct a pipeline without invoking any LLM backend."""
    return MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)


# ---------------------------------------------------------------------------
# 1. Schema validation — known types
# ---------------------------------------------------------------------------


def test_vital_sign_entry_validates_known_types() -> None:
    """Each of the 9 vital_type literals should pass validation."""
    known_types = [
        "blood-pressure-systolic",
        "blood-pressure-diastolic",
        "heart-rate",
        "body-temperature",
        "respiratory-rate",
        "oxygen-saturation",
        "body-weight",
        "body-height",
        "bmi",
    ]
    for vtype in known_types:
        entry = VitalSignEntry(vital_type=vtype)
        assert entry.vital_type == vtype


# ---------------------------------------------------------------------------
# 2. Schema validation — unknown type rejected
# ---------------------------------------------------------------------------


def test_vital_sign_entry_rejects_unknown_type() -> None:
    """An unrecognized vital_type string must raise a pydantic ValidationError."""
    with pytest.raises(ValidationError):
        VitalSignEntry(vital_type="random-thing")


# ---------------------------------------------------------------------------
# 3. LOINC mapping correctness for all 9 vital types
# ---------------------------------------------------------------------------

_EXPECTED_LOINC = {
    "blood-pressure-systolic": "8480-6",
    "blood-pressure-diastolic": "8462-4",
    "heart-rate": "8867-4",
    "body-temperature": "8310-5",
    "respiratory-rate": "9279-1",
    "oxygen-saturation": "2708-6",
    "body-weight": "29463-7",
    "body-height": "8302-2",
    "bmi": "39156-5",
}


def test_vital_sign_to_fhir_emits_correct_loinc() -> None:
    """For each vital_type, the emitted Observation carries the correct LOINC code."""
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"
    common_meta = {"source": "extracted://patient-summary/test", "extension": []}
    doc_context = DocumentContext(document_type="patient-summary")

    for vtype, expected_code in _EXPECTED_LOINC.items():
        entry = VitalSignEntry(vital_type=vtype, value=1.0, unit="unit")
        resource = pipeline._vital_sign_to_fhir(entry, common_meta, layout=None, doc_context=doc_context)
        codings = resource["code"]["coding"]
        loinc_codes = [c["code"] for c in codings if c.get("system") == "http://loinc.org"]
        assert loinc_codes == [expected_code], (
            f"vital_type={vtype!r}: expected LOINC {expected_code!r}, got {loinc_codes!r}"
        )


# ---------------------------------------------------------------------------
# 4. Category is vital-signs
# ---------------------------------------------------------------------------


def test_vital_sign_to_fhir_uses_vital_signs_category() -> None:
    """Emitted Observation must have category code 'vital-signs'."""
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"
    common_meta = {"source": "extracted://patient-summary/test", "extension": []}
    doc_context = DocumentContext(document_type="patient-summary")

    entry = VitalSignEntry(vital_type="heart-rate", value=72.0, unit="/min")
    resource = pipeline._vital_sign_to_fhir(entry, common_meta, layout=None, doc_context=doc_context)

    category_codings = resource["category"][0]["coding"]
    codes = [c["code"] for c in category_codings]
    assert "vital-signs" in codes


# ---------------------------------------------------------------------------
# 5. valueQuantity emission
# ---------------------------------------------------------------------------


def test_vital_sign_to_fhir_emits_value_quantity() -> None:
    """value=119, unit='mm[Hg]' → resource has valueQuantity with value=119, code='mm[Hg]'."""
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"
    common_meta = {"source": "extracted://patient-summary/test", "extension": []}
    doc_context = DocumentContext(document_type="patient-summary")

    entry = VitalSignEntry(vital_type="blood-pressure-systolic", value=119.0, unit="mm[Hg]")
    resource = pipeline._vital_sign_to_fhir(entry, common_meta, layout=None, doc_context=doc_context)

    vq = resource["valueQuantity"]
    assert vq["value"] == 119.0
    assert vq["code"] == "mm[Hg]"
    assert vq["system"] == "http://unitsofmeasure.org"


# ---------------------------------------------------------------------------
# 6. Blood pressure two-entry pattern
# ---------------------------------------------------------------------------


def test_blood_pressure_two_entries_pattern() -> None:
    """Systolic + diastolic entries convert to two Observations with correct LOINC codes."""
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"
    common_meta = {"source": "extracted://patient-summary/test", "extension": []}
    doc_context = DocumentContext(document_type="patient-summary")

    systolic = VitalSignEntry(vital_type="blood-pressure-systolic", value=119.0, unit="mm[Hg]")
    diastolic = VitalSignEntry(vital_type="blood-pressure-diastolic", value=71.0, unit="mm[Hg]")
    extraction = VitalSignExtraction(vital_signs=[systolic, diastolic])

    resources = [
        pipeline._vital_sign_to_fhir(vs, common_meta, layout=None, doc_context=doc_context)
        for vs in extraction.vital_signs
    ]

    assert len(resources) == 2

    sys_codings = resources[0]["code"]["coding"]
    sys_codes = [c["code"] for c in sys_codings if c.get("system") == "http://loinc.org"]
    assert sys_codes == ["8480-6"]

    dia_codings = resources[1]["code"]["coding"]
    dia_codes = [c["code"] for c in dia_codings if c.get("system") == "http://loinc.org"]
    assert dia_codes == ["8462-4"]


# ---------------------------------------------------------------------------
# 7. Doc-context date fallback
# ---------------------------------------------------------------------------


def test_vital_sign_emits_effective_date_from_doc_context_fallback() -> None:
    """VitalSignEntry without effective_date but with DocumentContext.encounter_date
    should pick up the encounter_date as effectiveDateTime."""
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"
    common_meta = {"source": "extracted://patient-summary/test", "extension": []}
    doc_context = DocumentContext(document_type="patient-summary", encounter_date="2025-12-12")

    entry = VitalSignEntry(vital_type="body-weight", value=95.7, unit="kg")
    # No effective_date set on entry
    assert entry.effective_date is None

    resource = pipeline._vital_sign_to_fhir(entry, common_meta, layout=None, doc_context=doc_context)

    assert resource.get("effectiveDateTime") == "2025-12-12"
