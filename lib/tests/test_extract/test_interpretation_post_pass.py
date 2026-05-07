"""Tests for the interpretation post-pass in MultiPassFHIRPipeline.

Verifies derivation of FHIR v3-ObservationInterpretation codes (H / L / N)
from numeric value vs reference range. No LLM, deterministic comparison.
"""

from __future__ import annotations

from lib.extract.pipelines.multipass_fhir import (
    DocumentContext,
    LabObservationEntry,
    LabObservationExtraction,
    MultiPassFHIRPipeline,
)


def _new_pipeline() -> MultiPassFHIRPipeline:
    return MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)


def test_high_value_above_range() -> None:
    """Glucose 115 with range 65-99 → H."""
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(
                test_name="Glucose",
                value_quantity=115.0,
                reference_range_low=65.0,
                reference_range_high=99.0,
            ),
        ]
    )
    sources = pipeline._apply_interpretation_post_pass(extraction)
    assert extraction.observations[0].flag == "H"
    assert sources[id(extraction.observations[0])] == "computed"


def test_low_value_below_range() -> None:
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(
                test_name="Glucose",
                value_quantity=50.0,
                reference_range_low=65.0,
                reference_range_high=99.0,
            ),
        ]
    )
    pipeline._apply_interpretation_post_pass(extraction)
    assert extraction.observations[0].flag == "L"


def test_normal_value_within_range() -> None:
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(
                test_name="Glucose",
                value_quantity=80.0,
                reference_range_low=65.0,
                reference_range_high=99.0,
            ),
        ]
    )
    pipeline._apply_interpretation_post_pass(extraction)
    assert extraction.observations[0].flag == "N"


def test_extraction_emitted_flag_preserved() -> None:
    """If extraction already populated o.flag, the post-pass must not overwrite it."""
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(
                test_name="Glucose",
                value_quantity=115.0,
                reference_range_low=65.0,
                reference_range_high=99.0,
                flag="HH",  # extraction-emitted "very high"
            ),
        ]
    )
    sources = pipeline._apply_interpretation_post_pass(extraction)
    assert extraction.observations[0].flag == "HH"
    assert sources[id(extraction.observations[0])] == "printed"


def test_no_value_no_interpretation() -> None:
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(test_name="Color", value_string="Yellow"),
        ]
    )
    sources = pipeline._apply_interpretation_post_pass(extraction)
    assert extraction.observations[0].flag is None
    assert sources[id(extraction.observations[0])] == "unknown"


def test_no_range_no_interpretation() -> None:
    """Numeric value without a range → no computation possible."""
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[LabObservationEntry(test_name="Globulin", value_quantity=2.1)]
    )
    sources = pipeline._apply_interpretation_post_pass(extraction)
    assert extraction.observations[0].flag is None
    assert sources[id(extraction.observations[0])] == "unknown"


def test_one_sided_range_high_only() -> None:
    """eGFR has only a lower bound (>=60); above 60 → N."""
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(
                test_name="eGFR",
                value_quantity=99.0,
                reference_range_low=60.0,
                reference_range_high=None,
            ),
        ]
    )
    pipeline._apply_interpretation_post_pass(extraction)
    assert extraction.observations[0].flag == "N"


def test_one_sided_range_low_only() -> None:
    """ApoB has only an upper bound (<90); above 90 → H."""
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(
                test_name="Apolipoprotein B",
                value_quantity=103.0,
                reference_range_low=None,
                reference_range_high=90.0,
            ),
        ]
    )
    pipeline._apply_interpretation_post_pass(extraction)
    assert extraction.observations[0].flag == "H"


def test_fhir_observation_carries_interpretation_extension() -> None:
    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"

    entry = LabObservationEntry(
        test_name="Glucose",
        value_quantity=115.0,
        unit="mg/dL",
        reference_range_low=65.0,
        reference_range_high=99.0,
    )
    extraction = LabObservationExtraction(observations=[entry])
    interp_sources = pipeline._apply_interpretation_post_pass(extraction)

    common_meta = {"source": "extracted://lab-report/test", "extension": []}
    doc_context = DocumentContext(document_type="lab-report")
    resource = pipeline._lab_observation_to_fhir(
        entry,
        common_meta,
        layout=None,
        doc_context=doc_context,
        interpretation_source=interp_sources[id(entry)],
    )

    # Has interpretation coding H
    interp = resource["interpretation"]
    assert interp[0]["coding"][0]["code"] == "H"

    # Has interpretation-source extension marked "computed"
    meta_exts = resource["meta"]["extension"]
    src_ext = next(
        (e for e in meta_exts if "interpretation-source" in e.get("url", "")),
        None,
    )
    assert src_ext is not None
    assert src_ext["valueString"] == "computed"
