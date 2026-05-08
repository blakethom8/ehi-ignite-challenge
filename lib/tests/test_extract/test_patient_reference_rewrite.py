"""Tests for _rewrite_patient_references — the deterministic post-pass that
rewrites every resource's Patient/<old> reference to Patient/<actual> once a
Patient resource has been emitted by the patient_demographics pass (T09/T10).

All tests exercise the helper directly on hand-crafted entry lists; no LLM
backend is involved.
"""

from __future__ import annotations

from lib.extract.pipelines.multipass_fhir import MultiPassFHIRPipeline


def _new_pipeline() -> MultiPassFHIRPipeline:
    """Construct a pipeline without invoking any LLM backend."""
    p = MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)
    p._patient_id = "unknown"
    return p


def _make_entries(*resources: dict) -> list[dict]:
    return [{"resource": r} for r in resources]


# ---------------------------------------------------------------------------
# 1. No Patient resource — references unchanged
# ---------------------------------------------------------------------------


def test_no_patient_no_rewrite() -> None:
    """Entries with Observation referencing Patient/unknown but NO Patient
    resource → reference is left unchanged."""
    pipeline = _new_pipeline()
    obs = {
        "resourceType": "Observation",
        "subject": {"reference": "Patient/unknown"},
    }
    entries = _make_entries(obs)

    pipeline._rewrite_patient_references(entries)

    assert obs["subject"]["reference"] == "Patient/unknown"


# ---------------------------------------------------------------------------
# 2. Single Patient + Observation
# ---------------------------------------------------------------------------


def test_single_patient_rewrites_observation_subject() -> None:
    """1 Patient (id=pat-abc) + 1 Observation (subject=Patient/unknown)
    → Observation.subject.reference is rewritten to Patient/pat-abc."""
    pipeline = _new_pipeline()
    patient = {"resourceType": "Patient", "id": "pat-abc"}
    obs = {
        "resourceType": "Observation",
        "subject": {"reference": "Patient/unknown"},
    }
    entries = _make_entries(patient, obs)

    pipeline._rewrite_patient_references(entries)

    assert obs["subject"]["reference"] == "Patient/pat-abc"


# ---------------------------------------------------------------------------
# 3. Single Patient + mixed resource types
# ---------------------------------------------------------------------------


def test_single_patient_rewrites_condition_and_medication() -> None:
    """1 Patient + mixed Condition + MedicationRequest → all subject references
    are rewritten to the real Patient.id."""
    pipeline = _new_pipeline()
    patient = {"resourceType": "Patient", "id": "pat-xyz"}
    condition = {
        "resourceType": "Condition",
        "subject": {"reference": "Patient/unknown"},
    }
    med = {
        "resourceType": "MedicationRequest",
        "subject": {"reference": "Patient/unknown"},
    }
    entries = _make_entries(patient, condition, med)

    pipeline._rewrite_patient_references(entries)

    assert condition["subject"]["reference"] == "Patient/pat-xyz"
    assert med["subject"]["reference"] == "Patient/pat-xyz"


# ---------------------------------------------------------------------------
# 4. Immunization uses ``patient`` field (not ``subject``)
# ---------------------------------------------------------------------------


def test_immunization_uses_correct_field_name() -> None:
    """Immunization carries a ``patient`` reference (not ``subject``).
    Confirm the rewrite targets that field, matching _immunization_to_fhir."""
    pipeline = _new_pipeline()
    patient = {"resourceType": "Patient", "id": "pat-imm"}
    imm = {
        "resourceType": "Immunization",
        "patient": {"reference": "Patient/unknown"},
        "status": "completed",
    }
    entries = _make_entries(patient, imm)

    pipeline._rewrite_patient_references(entries)

    assert imm["patient"]["reference"] == "Patient/pat-imm"


# ---------------------------------------------------------------------------
# 5. Coverage uses ``beneficiary`` field
# ---------------------------------------------------------------------------


def test_coverage_beneficiary_rewritten() -> None:
    """Coverage uses ``beneficiary`` (not ``subject``). Confirm rewrite."""
    pipeline = _new_pipeline()
    patient = {"resourceType": "Patient", "id": "pat-cov"}
    coverage = {
        "resourceType": "Coverage",
        "beneficiary": {"reference": "Patient/unknown"},
        "status": "active",
    }
    entries = _make_entries(patient, coverage)

    pipeline._rewrite_patient_references(entries)

    assert coverage["beneficiary"]["reference"] == "Patient/pat-cov"


# ---------------------------------------------------------------------------
# 6. DocumentReference subject rewritten
# ---------------------------------------------------------------------------


def test_documentreference_subject_rewritten() -> None:
    """DocumentReference.subject should be rewritten to the real Patient.id."""
    pipeline = _new_pipeline()
    patient = {"resourceType": "Patient", "id": "pat-doc"}
    doc_ref = {
        "resourceType": "DocumentReference",
        "subject": {"reference": "Patient/unknown"},
        "status": "current",
    }
    entries = _make_entries(patient, doc_ref)

    pipeline._rewrite_patient_references(entries)

    assert doc_ref["subject"]["reference"] == "Patient/pat-doc"


# ---------------------------------------------------------------------------
# 7. Composition subject rewritten
# ---------------------------------------------------------------------------


def test_composition_subject_rewritten() -> None:
    """Composition.subject should be rewritten to the real Patient.id."""
    pipeline = _new_pipeline()
    patient = {"resourceType": "Patient", "id": "pat-comp"}
    composition = {
        "resourceType": "Composition",
        "subject": {"reference": "Patient/unknown"},
        "status": "final",
    }
    entries = _make_entries(patient, composition)

    pipeline._rewrite_patient_references(entries)

    assert composition["subject"]["reference"] == "Patient/pat-comp"


# ---------------------------------------------------------------------------
# 8. Idempotent — calling twice produces the same result
# ---------------------------------------------------------------------------


def test_idempotent() -> None:
    """Calling _rewrite_patient_references twice on the same entries list
    should produce identical results on the second call (no errors, no
    double-rewrite)."""
    pipeline = _new_pipeline()
    patient = {"resourceType": "Patient", "id": "pat-idem"}
    obs = {
        "resourceType": "Observation",
        "subject": {"reference": "Patient/unknown"},
    }
    entries = _make_entries(patient, obs)

    pipeline._rewrite_patient_references(entries)
    assert obs["subject"]["reference"] == "Patient/pat-idem"

    # Second call — must be a no-op
    pipeline._rewrite_patient_references(entries)
    assert obs["subject"]["reference"] == "Patient/pat-idem"


# ---------------------------------------------------------------------------
# 9. Multiple Patient resources — ambiguous, no rewriting
# ---------------------------------------------------------------------------


def test_multiple_patients_no_rewrite() -> None:
    """When two Patient resources exist, the helper cannot pick one; it must
    leave all references untouched."""
    pipeline = _new_pipeline()
    patient_a = {"resourceType": "Patient", "id": "pat-a"}
    patient_b = {"resourceType": "Patient", "id": "pat-b"}
    obs = {
        "resourceType": "Observation",
        "subject": {"reference": "Patient/unknown"},
    }
    entries = _make_entries(patient_a, patient_b, obs)

    pipeline._rewrite_patient_references(entries)

    assert obs["subject"]["reference"] == "Patient/unknown"


# ---------------------------------------------------------------------------
# 10. Patient.id itself is preserved, not accidentally rewritten
# ---------------------------------------------------------------------------


def test_patient_resource_itself_not_rewritten() -> None:
    """The Patient resource's own ``id`` field must not be touched by the
    rewriter."""
    pipeline = _new_pipeline()
    patient = {"resourceType": "Patient", "id": "pat-self"}
    obs = {
        "resourceType": "Observation",
        "subject": {"reference": "Patient/unknown"},
    }
    entries = _make_entries(patient, obs)

    pipeline._rewrite_patient_references(entries)

    # Patient.id unchanged
    assert patient["id"] == "pat-self"
    # Observation rewritten
    assert obs["subject"]["reference"] == "Patient/pat-self"


# ---------------------------------------------------------------------------
# 11. Practitioner / Organization are not touched
# ---------------------------------------------------------------------------


def test_practitioner_organization_not_touched() -> None:
    """Practitioner and Organization have no patient reference; the helper
    should skip them silently without raising an exception."""
    pipeline = _new_pipeline()
    patient = {"resourceType": "Patient", "id": "pat-org"}
    practitioner = {
        "resourceType": "Practitioner",
        "id": "prac-001",
        "name": [{"family": "Smith"}],
    }
    organization = {
        "resourceType": "Organization",
        "id": "org-001",
        "name": "General Hospital",
    }
    obs = {
        "resourceType": "Observation",
        "subject": {"reference": "Patient/unknown"},
    }
    entries = _make_entries(patient, practitioner, organization, obs)

    pipeline._rewrite_patient_references(entries)

    # Practitioner and Organization are untouched
    assert practitioner["id"] == "prac-001"
    assert organization["id"] == "org-001"
    # Observation was rewritten
    assert obs["subject"]["reference"] == "Patient/pat-org"
