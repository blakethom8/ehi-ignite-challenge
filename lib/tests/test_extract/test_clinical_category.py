"""Tests for the clinical-category lookup + post-pass.

Verifies that resolved LOINC codes get categorized (Metabolic / Kidney /
Liver / Blood / etc.) via the curated table, and that the FHIR Observation
carries the category as a meta.extension.
"""

from __future__ import annotations

from lib.extract.pipelines.multipass_fhir import (
    DocumentContext,
    LabObservationEntry,
    LabObservationExtraction,
    MultiPassFHIRPipeline,
)
from lib.extract.terminology import lookup_clinical_category


def _new_pipeline() -> MultiPassFHIRPipeline:
    return MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)


def test_lookup_glucose_is_metabolic() -> None:
    assert lookup_clinical_category("2345-7") == "Metabolic"


def test_lookup_creatinine_is_kidney() -> None:
    assert lookup_clinical_category("2160-0") == "Kidney"


def test_lookup_alt_is_liver() -> None:
    assert lookup_clinical_category("1742-6") == "Liver"


def test_lookup_hemoglobin_is_blood() -> None:
    assert lookup_clinical_category("718-7") == "Blood"


def test_lookup_apob_is_heart() -> None:
    assert lookup_clinical_category("1884-6") == "Heart"


def test_lookup_unknown_code_returns_none() -> None:
    assert lookup_clinical_category("9999-9") is None


def test_lookup_empty_returns_none() -> None:
    assert lookup_clinical_category("") is None


def test_post_pass_categorizes_observations_with_loinc() -> None:
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(test_name="Glucose", loinc_code="2345-7"),
            LabObservationEntry(test_name="BUN", loinc_code="3094-0"),
            LabObservationEntry(test_name="ALT", loinc_code="1742-6"),
        ]
    )
    categories = pipeline._lookup_clinical_categories(extraction)
    assert categories[id(extraction.observations[0])] == "Metabolic"
    assert categories[id(extraction.observations[1])] == "Kidney"
    assert categories[id(extraction.observations[2])] == "Liver"


def test_post_pass_skips_observations_without_loinc() -> None:
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[LabObservationEntry(test_name="xyzzy", loinc_code=None)]
    )
    categories = pipeline._lookup_clinical_categories(extraction)
    assert id(extraction.observations[0]) not in categories


def test_fhir_observation_carries_clinical_category_extension() -> None:
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"

    entry = LabObservationEntry(
        test_name="Glucose",
        value_quantity=115.0,
        unit="mg/dL",
        loinc_code="2345-7",
    )
    common_meta = {"source": "extracted://lab-report/test", "extension": []}
    doc_context = DocumentContext(document_type="lab-report")
    resource = pipeline._lab_observation_to_fhir(
        entry,
        common_meta,
        layout=None,
        doc_context=doc_context,
        clinical_category="Metabolic",
    )

    meta_exts = resource["meta"]["extension"]
    cat_ext = next(
        (e for e in meta_exts if "clinical-category" in e.get("url", "")),
        None,
    )
    assert cat_ext is not None
    assert cat_ext["valueString"] == "Metabolic"
