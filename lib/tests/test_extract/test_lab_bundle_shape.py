"""Tests for lib/extract/lab/bundle_shape.py.

Constructs synthetic Bundle dicts with known shapes; asserts metrics.
No pipeline involvement — pure unit tests over the scoring logic.
"""

from __future__ import annotations

from dataclasses import asdict

import pytest

from lib.extract.lab.bundle_shape import BundleShapeReport, score_bundle_shape


# ---------------------------------------------------------------------------
# Helpers to build minimal synthetic FHIR resources
# ---------------------------------------------------------------------------


def _patient(id_: str = "pat-1") -> dict:
    return {"resourceType": "Patient", "id": id_}


def _encounter(id_: str = "enc-1") -> dict:
    return {"resourceType": "Encounter", "id": id_}


def _observation(
    id_: str = "obs-1",
    *,
    patient_id: str = "pat-1",
    encounter_id: str | None = None,
    loinc_code: str | None = None,
    value_quantity: dict | None = None,
    reference_range: list | None = None,
    interpretation: list | None = None,
    clinical_category_ext: bool = False,
) -> dict:
    resource: dict = {
        "resourceType": "Observation",
        "id": id_,
        "subject": {"reference": f"Patient/{patient_id}"},
    }
    if encounter_id is not None:
        resource["encounter"] = {"reference": f"Encounter/{encounter_id}"}
    coding = []
    if loinc_code:
        coding.append({"system": "http://loinc.org", "code": loinc_code})
    resource["code"] = {"coding": coding}
    if value_quantity is not None:
        resource["valueQuantity"] = value_quantity
    if reference_range is not None:
        resource["referenceRange"] = reference_range
    if interpretation is not None:
        resource["interpretation"] = interpretation
    if clinical_category_ext:
        resource["meta"] = {
            "extension": [
                {"url": "https://ehi-atlas.example/fhir/StructureDefinition/clinical-category", "valueString": "lab"}
            ]
        }
    return resource


def _practitioner(id_: str = "prac-1", npi: str | None = None) -> dict:
    resource: dict = {"resourceType": "Practitioner", "id": id_}
    if npi:
        resource["identifier"] = [
            {"system": "http://hl7.org/fhir/sid/us-npi", "value": npi}
        ]
    else:
        resource["identifier"] = []
    return resource


def _document_reference(
    id_: str = "doc-1",
    *,
    patient_id: str = "pat-1",
    encounter_id: str | None = None,
) -> dict:
    resource: dict = {
        "resourceType": "DocumentReference",
        "id": id_,
        "subject": {"reference": f"Patient/{patient_id}"},
    }
    if encounter_id is not None:
        resource["context"] = {
            "encounter": [{"reference": f"Encounter/{encounter_id}"}]
        }
    else:
        resource["context"] = {}
    return resource


def _bundle(*resources: dict) -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in resources],
    }


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_patient_count_one_for_normal_bundle():
    bundle = _bundle(_patient("pat-1"))
    report = score_bundle_shape(bundle)
    assert report.patient_count == 1
    assert report.multiple_patients_warning is False


def test_patient_count_zero_when_no_patient():
    obs = _observation()
    bundle = _bundle(obs)
    report = score_bundle_shape(bundle)
    assert report.patient_count == 0


def test_multiple_patients_warning_triggers_at_two():
    bundle = _bundle(_patient("pat-1"), _patient("pat-2"))
    report = score_bundle_shape(bundle)
    assert report.patient_count == 2
    assert report.multiple_patients_warning is True


def test_encounter_link_rate_fully_linked():
    enc = _encounter("enc-1")
    obs1 = _observation("obs-1", encounter_id="enc-1")
    obs2 = _observation("obs-2", encounter_id="enc-1")
    obs3 = _observation("obs-3", encounter_id="enc-1")
    obs4 = _observation("obs-4", encounter_id="enc-1")
    obs5 = _observation("obs-5", encounter_id="enc-1")
    bundle = _bundle(enc, obs1, obs2, obs3, obs4, obs5)
    report = score_bundle_shape(bundle)
    assert report.encounter_link_rate == 1.0


def test_encounter_link_rate_zero_when_no_links():
    obs1 = _observation("obs-1")
    obs2 = _observation("obs-2")
    bundle = _bundle(obs1, obs2)
    report = score_bundle_shape(bundle)
    assert report.encounter_link_rate == 0.0


def test_practitioner_npi_rate():
    p1 = _practitioner("prac-1", npi="1234567890")
    p2 = _practitioner("prac-2", npi="9876543210")
    p3 = _practitioner("prac-3")  # no NPI
    bundle = _bundle(p1, p2, p3)
    report = score_bundle_shape(bundle)
    assert abs(report.practitioner_npi_rate - 2 / 3) < 1e-4


def test_loinc_resolution_rate():
    obs_with = _observation("obs-1", loinc_code="2160-0")
    obs_without: dict = {
        "resourceType": "Observation",
        "id": "obs-2",
        "subject": {"reference": "Patient/pat-1"},
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "12345"}]},
    }
    bundle = _bundle(obs_with, obs_without)
    report = score_bundle_shape(bundle)
    assert report.loinc_resolution_rate == 0.5


def test_interpretation_rate_only_counts_eligible():
    # Eligible: has valueQuantity + referenceRange, has interpretation
    obs_eligible_with_interp = _observation(
        "obs-1",
        value_quantity={"value": 7.5, "unit": "mg/dL"},
        reference_range=[{"low": {"value": 5.0}, "high": {"value": 10.0}}],
        interpretation=[{"text": "Normal"}],
    )
    # Eligible: has valueQuantity + referenceRange, NO interpretation
    obs_eligible_no_interp = _observation(
        "obs-2",
        value_quantity={"value": 7.5, "unit": "mg/dL"},
        reference_range=[{"low": {"value": 5.0}, "high": {"value": 10.0}}],
    )
    # Not eligible: has valueQuantity but no referenceRange
    obs_not_eligible = _observation(
        "obs-3",
        value_quantity={"value": 7.5, "unit": "mg/dL"},
    )
    bundle = _bundle(obs_eligible_with_interp, obs_eligible_no_interp, obs_not_eligible)
    report = score_bundle_shape(bundle)
    # Only 2 eligible; 1 has interpretation -> 0.5
    assert report.interpretation_rate == 0.5


def test_clinical_category_rate_via_extension_url():
    obs_with = _observation("obs-1", clinical_category_ext=True)
    obs_without = _observation("obs-2")
    bundle = _bundle(obs_with, obs_without)
    report = score_bundle_shape(bundle)
    assert report.clinical_category_rate == 0.5


def test_duplicate_practitioner_npis_detected():
    p1 = _practitioner("prac-1", npi="1234567890")
    p2 = _practitioner("prac-2", npi="1234567890")  # same NPI — duplicate
    bundle = _bundle(p1, p2)
    report = score_bundle_shape(bundle)
    assert report.duplicate_practitioner_npis == ["1234567890"]


def test_orphaned_subject_reference_detected():
    # Observation references Patient/nonexistent — should be flagged
    obs: dict = {
        "resourceType": "Observation",
        "id": "obs-1",
        "subject": {"reference": "Patient/nonexistent-id"},
        "code": {"coding": []},
    }
    pat = _patient("pat-1")  # real patient with different id
    bundle = _bundle(pat, obs)
    report = score_bundle_shape(bundle)
    assert "Patient/nonexistent-id" in report.orphaned_subject_references


def test_orphaned_subject_reference_does_not_flag_unknown_placeholder():
    # Patient/unknown is the pre-rewrite placeholder; should NOT be flagged
    obs: dict = {
        "resourceType": "Observation",
        "id": "obs-1",
        "subject": {"reference": "Patient/unknown"},
        "code": {"coding": []},
    }
    pat = _patient("pat-1")
    bundle = _bundle(pat, obs)
    report = score_bundle_shape(bundle)
    assert "Patient/unknown" not in report.orphaned_subject_references


def test_orphaned_encounter_reference_detected():
    # Observation references Encounter/ghost — should be flagged
    obs: dict = {
        "resourceType": "Observation",
        "id": "obs-1",
        "subject": {"reference": "Patient/pat-1"},
        "encounter": {"reference": "Encounter/ghost-enc"},
        "code": {"coding": []},
    }
    pat = _patient("pat-1")
    enc = _encounter("real-enc-1")
    bundle = _bundle(pat, enc, obs)
    report = score_bundle_shape(bundle)
    assert "Encounter/ghost-enc" in report.orphaned_encounter_references


def test_note_encounter_link_rate_uses_context_encounter():
    enc = _encounter("enc-1")
    doc_with_enc = _document_reference("doc-1", encounter_id="enc-1")
    doc_without_enc = _document_reference("doc-2")
    bundle = _bundle(enc, doc_with_enc, doc_without_enc)
    report = score_bundle_shape(bundle)
    assert report.note_encounter_link_rate == 0.5


def test_score_bundle_shape_returns_dataclass():
    report = score_bundle_shape({"entry": []})
    assert isinstance(report, BundleShapeReport)
    d = asdict(report)
    # All count fields should be 0
    assert d["total_entries"] == 0
    assert d["patient_count"] == 0
    assert d["encounter_count"] == 0
    assert d["practitioner_count"] == 0
    assert d["organization_count"] == 0
    assert d["document_reference_count"] == 0
    assert d["composition_count"] == 0
    # All rate fields should be 0.0
    assert d["encounter_link_rate"] == 0.0
    assert d["patient_link_rate"] == 0.0
    assert d["practitioner_npi_rate"] == 0.0
    assert d["loinc_resolution_rate"] == 0.0
    assert d["interpretation_rate"] == 0.0
    assert d["clinical_category_rate"] == 0.0
    assert d["note_encounter_link_rate"] == 0.0
    # Anomaly lists should be empty
    assert d["duplicate_practitioner_npis"] == []
    assert d["orphaned_subject_references"] == []
    assert d["orphaned_encounter_references"] == []
    assert d["multiple_patients_warning"] is False
