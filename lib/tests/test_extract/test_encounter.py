"""Tests for the encounter extraction pass in MultiPassFHIRPipeline.

Verifies schema validation (class_code Literal), FHIR shape, period emission,
participant/provider rendering, stable-ID determinism, and provided-ID passthrough.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lib.extract.pipelines.multipass_fhir import (
    DocumentContext,
    EncounterEntry,
    EncounterExtraction,
    MultiPassFHIRPipeline,
    _stable_encounter_id,
)


def _new_pipeline() -> MultiPassFHIRPipeline:
    """Construct a pipeline without invoking any LLM backend."""
    p = MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)
    p._patient_id = "test-patient"
    return p


def _common_meta() -> dict:
    return {"source": "extracted://clinical-note/test", "extension": []}


def _doc_context() -> DocumentContext:
    return DocumentContext(document_type="clinical-note")


# ---------------------------------------------------------------------------
# 1. Schema validation — valid class_codes
# ---------------------------------------------------------------------------


def test_encounter_entry_validates_class_codes() -> None:
    """Each of the supported HL7 v3 ActCode class_code literals must pass validation."""
    valid_codes = ["AMB", "EMER", "IMP", "ACUTE", "NONAC", "OBSENC", "PRENC", "SS", "VR"]
    for code in valid_codes:
        entry = EncounterEntry(class_code=code)
        assert entry.class_code == code


# ---------------------------------------------------------------------------
# 2. Schema validation — invalid class_code rejected
# ---------------------------------------------------------------------------


def test_encounter_entry_rejects_invalid_class_code() -> None:
    """An unrecognized class_code string must raise a pydantic ValidationError."""
    with pytest.raises(ValidationError):
        EncounterEntry(class_code="ZZZ")


# ---------------------------------------------------------------------------
# 3. Minimum resource shape
# ---------------------------------------------------------------------------


def test_encounter_to_fhir_emits_minimum_resource() -> None:
    """With only default fields, the emitted resource must have the required keys."""
    pipeline = _new_pipeline()
    entry = EncounterEntry()  # all optional fields default to None / "finished"
    resource = pipeline._encounter_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert resource["resourceType"] == "Encounter"
    assert resource["status"] == "finished"
    assert "subject" in resource
    assert resource["subject"]["reference"] == "Patient/test-patient"
    assert "id" in resource


# ---------------------------------------------------------------------------
# 4. class_code emitted correctly
# ---------------------------------------------------------------------------


def test_encounter_to_fhir_emits_class_when_provided() -> None:
    """class_code='AMB' → resource['class']['code'] == 'AMB' with HL7 v3 system."""
    pipeline = _new_pipeline()
    entry = EncounterEntry(class_code="AMB")
    resource = pipeline._encounter_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "class" in resource
    assert resource["class"]["code"] == "AMB"
    assert resource["class"]["system"] == "http://terminology.hl7.org/CodeSystem/v3-ActCode"


# ---------------------------------------------------------------------------
# 5. Period emission
# ---------------------------------------------------------------------------


def test_encounter_to_fhir_emits_period() -> None:
    """period_start + period_end both populated → resource.period.start and .end present."""
    pipeline = _new_pipeline()
    entry = EncounterEntry(
        period_start="2026-04-22T14:15:00-07:00",
        period_end="2026-04-22T15:30:00-07:00",
    )
    resource = pipeline._encounter_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "period" in resource
    assert resource["period"]["start"] == "2026-04-22T14:15:00-07:00"
    assert resource["period"]["end"] == "2026-04-22T15:30:00-07:00"


# ---------------------------------------------------------------------------
# 6. Participant and service provider emission
# ---------------------------------------------------------------------------


def test_encounter_to_fhir_emits_participant_and_provider() -> None:
    """participant_display and service_provider_display both rendered as display-only references."""
    pipeline = _new_pipeline()
    entry = EncounterEntry(
        participant_display="Ani Shirvanian, NP",
        service_provider_display="Beverly Hills Allergy",
    )
    resource = pipeline._encounter_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    # Participant
    assert "participant" in resource
    assert len(resource["participant"]) == 1
    assert resource["participant"][0]["individual"]["display"] == "Ani Shirvanian, NP"

    # Service provider
    assert "serviceProvider" in resource
    assert resource["serviceProvider"]["display"] == "Beverly Hills Allergy"


# ---------------------------------------------------------------------------
# 7. Stable encounter ID — deterministic and content-addressed
# ---------------------------------------------------------------------------


def test_stable_encounter_id_is_deterministic() -> None:
    """Same inputs must produce the same ID; different inputs must produce a different ID."""
    doc_ctx = DocumentContext(document_type="clinical-note", encounter_date="2026-04-22")

    entry_a = EncounterEntry(
        period_start="2026-04-22",
        participant_display="Ani Shirvanian, NP",
        service_provider_display="Beverly Hills Allergy",
        type_display="Office Visit",
    )
    entry_b = EncounterEntry(
        period_start="2026-04-22",
        participant_display="Ani Shirvanian, NP",
        service_provider_display="Beverly Hills Allergy",
        type_display="Office Visit",
    )
    entry_c = EncounterEntry(
        period_start="2026-04-22",
        participant_display="Steven Krems, MD",
        service_provider_display="Beverly Hills Allergy",
        type_display="Follow-up",
    )

    id_a = _stable_encounter_id(entry_a, doc_ctx)
    id_b = _stable_encounter_id(entry_b, doc_ctx)
    id_c = _stable_encounter_id(entry_c, doc_ctx)

    assert id_a == id_b, "Same inputs must produce the same stable ID"
    assert id_a != id_c, "Different inputs must produce different stable IDs"
    assert id_a.startswith("enc-"), "Stable IDs must use the 'enc-' prefix"


# ---------------------------------------------------------------------------
# 8. Provided encounter_id is preserved; missing one uses stable synthesized ID
# ---------------------------------------------------------------------------


def test_encounter_to_fhir_uses_provided_id_when_present() -> None:
    """encounter_id set → resource.id matches; not set → synthesized ID is used."""
    pipeline = _new_pipeline()
    doc_ctx = _doc_context()

    # Case A: provided ID
    entry_with_id = EncounterEntry(encounter_id="explicit-enc-001")
    resource_a = pipeline._encounter_to_fhir(entry_with_id, _common_meta(), layout=None, doc_context=doc_ctx)
    assert resource_a["id"] == "explicit-enc-001"

    # Case B: no provided ID → synthesized
    entry_no_id = EncounterEntry(
        participant_display="Test Provider, MD",
        service_provider_display="Test Clinic",
        period_start="2026-01-01",
    )
    resource_b = pipeline._encounter_to_fhir(entry_no_id, _common_meta(), layout=None, doc_context=doc_ctx)
    assert resource_b["id"].startswith("enc-")
    # Re-running yields the same ID
    resource_b2 = pipeline._encounter_to_fhir(entry_no_id, _common_meta(), layout=None, doc_context=doc_ctx)
    assert resource_b["id"] == resource_b2["id"]
