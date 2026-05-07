"""Tests for the LOINC post-pass wired into MultiPassFHIRPipeline.

Verifies that after extraction emits LabObservationEntry items with no
loinc_code, the post-pass resolves them via the matcher and the resulting
FHIR Observations carry both the LOINC coding AND a meta.extension
indicating the resolution source.
"""

from __future__ import annotations

from lib.extract.pipelines.multipass_fhir import (
    LabObservationEntry,
    LabObservationExtraction,
    MultiPassFHIRPipeline,
)


def _new_pipeline() -> MultiPassFHIRPipeline:
    """Construct a pipeline without invoking any LLM backend."""
    return MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)


def test_post_pass_resolves_missing_loinc_codes() -> None:
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(test_name="Glucose", value_quantity=115.0, unit="mg/dL"),
            LabObservationEntry(test_name="BUN", value_quantity=16.0, unit="mg/dL"),
            LabObservationEntry(test_name="eGFR", value_quantity=99.0),
        ]
    )

    sources = pipeline._apply_loinc_post_pass(extraction)

    assert extraction.observations[0].loinc_code == "2345-7"
    assert extraction.observations[1].loinc_code == "3094-0"
    assert extraction.observations[2].loinc_code == "33914-3"

    for obs in extraction.observations:
        src = sources[id(obs)]
        assert src.startswith("lookup-table-")


def test_post_pass_preserves_manually_set_codes() -> None:
    """Extraction-emitted codes must NOT be overwritten."""
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(
                test_name="Glucose",
                loinc_code="9999-9",  # bogus, but should not be overwritten
                value_quantity=115.0,
                unit="mg/dL",
            ),
        ]
    )

    sources = pipeline._apply_loinc_post_pass(extraction)

    obs = extraction.observations[0]
    assert obs.loinc_code == "9999-9"
    assert sources[id(obs)] == "manual"


def test_post_pass_marks_unmatched_entries() -> None:
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[
            LabObservationEntry(test_name="xyzzy nonsense"),
        ]
    )

    sources = pipeline._apply_loinc_post_pass(extraction)

    obs = extraction.observations[0]
    assert obs.loinc_code is None
    assert sources[id(obs)] == "unmatched"


def test_post_pass_idempotent() -> None:
    """Calling twice in a row produces the same result; manual after lookup stays manual-ish."""
    pipeline = _new_pipeline()
    extraction = LabObservationExtraction(
        observations=[LabObservationEntry(test_name="Glucose", value_quantity=115.0, unit="mg/dL")]
    )

    sources_1 = pipeline._apply_loinc_post_pass(extraction)
    code_after_first = extraction.observations[0].loinc_code

    sources_2 = pipeline._apply_loinc_post_pass(extraction)
    code_after_second = extraction.observations[0].loinc_code

    assert code_after_first == code_after_second
    # First pass: lookup-table; second pass: now manual since code is populated
    assert sources_1[id(extraction.observations[0])].startswith("lookup-table-")
    assert sources_2[id(extraction.observations[0])] == "manual"


def test_fhir_observation_carries_loinc_resolution_extension() -> None:
    """End-to-end: post-pass + FHIR builder → Observation resource has the
    loinc-resolution meta.extension."""
    from lib.extract.pipelines.multipass_fhir import DocumentContext

    pipeline = _new_pipeline()
    pipeline._patient_id = "test-patient"

    entry = LabObservationEntry(test_name="Glucose", value_quantity=115.0, unit="mg/dL")
    extraction = LabObservationExtraction(observations=[entry])
    sources = pipeline._apply_loinc_post_pass(extraction)
    source = sources[id(entry)]

    common_meta = {
        "source": "extracted://lab-report/test",
        "extension": [],
    }
    doc_context = DocumentContext(document_type="lab-report")
    resource = pipeline._lab_observation_to_fhir(
        entry,
        common_meta,
        layout=None,
        doc_context=doc_context,
        loinc_resolution_source=source,
    )

    # Has LOINC coding
    codings = resource["code"].get("coding", [])
    assert any(c.get("system") == "http://loinc.org" and c.get("code") == "2345-7" for c in codings)

    # Has resolution-source extension
    meta_exts = resource["meta"]["extension"]
    res_ext = next(
        (e for e in meta_exts if "loinc-resolution" in e.get("url", "")),
        None,
    )
    assert res_ext is not None
    assert res_ext["valueString"].startswith("lookup-table-")
