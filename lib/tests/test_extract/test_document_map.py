"""Tests for DocumentMap and ResourcePresence schemas (SCOUT-T01).

These schemas are dormant — not yet wired into any registered pipeline.
SCOUT-T02 builds the dispatcher that consumes their output.
"""

import pytest
from pydantic import ValidationError


def test_document_map_inherits_context_fields() -> None:
    """DocumentMap accepts and round-trips all DocumentContext fields."""
    from lib.extract.pipelines.multipass_fhir import DocumentMap

    dm = DocumentMap(
        document_type="lab-report",
        patient_name="Blake",
        patient_dob="1993-06-16",
    )
    assert dm.document_type == "lab-report"
    assert dm.patient_name == "Blake"
    assert dm.patient_dob == "1993-06-16"
    assert dm.encounter_date is None
    assert dm.ordering_provider is None
    assert dm.facility_name is None
    # inherited fields round-trip via JSON
    data = dm.model_dump()
    dm2 = DocumentMap.model_validate(data)
    assert dm2.patient_name == "Blake"
    assert dm2.patient_dob == "1993-06-16"


def test_document_map_presence_dict_validates_keys() -> None:
    """Valid presence keys are accepted; unknown keys raise ValidationError."""
    from lib.extract.pipelines.multipass_fhir import DocumentMap, ResourcePresence

    # valid key succeeds
    dm = DocumentMap(
        document_type="other",
        presence={"conditions": ResourcePresence(present=True)},
    )
    assert dm.presence["conditions"].present is True

    # unknown key raises
    with pytest.raises(ValidationError):
        DocumentMap(
            document_type="other",
            presence={"random_pass": ResourcePresence(present=True)},
        )


def test_document_map_resource_presence_defaults() -> None:
    """ResourcePresence() defaults: present=False, pages=[], section_hint=None."""
    from lib.extract.pipelines.multipass_fhir import ResourcePresence

    rp = ResourcePresence()
    assert rp.present is False
    assert rp.pages == []
    assert rp.section_hint is None


def test_document_map_full_serialization() -> None:
    """Populate DocumentMap with presence entries + sections; JSON round-trip preserves all."""
    from lib.extract.pipelines.multipass_fhir import DocumentMap, ResourcePresence

    dm = DocumentMap(
        document_type="patient-summary",
        patient_name="Jane Doe",
        patient_dob="1980-03-15",
        presence={
            "vital_signs": ResourcePresence(present=True, pages=[2], section_hint="Last Filed Vital Signs"),
            "lab_observations": ResourcePresence(present=True, pages=[5, 6, 7], section_hint="Comprehensive Metabolic Panel"),
            "clinical_notes": ResourcePresence(present=True, pages=[22, 23, 24], section_hint="Allergy & Immunology Progress Note"),
        },
        sections=["Patient Demographics", "Vital Signs", "Results", "Progress Notes"],
    )

    json_str = dm.model_dump_json()
    dm2 = DocumentMap.model_validate_json(json_str)

    assert dm2.patient_name == "Jane Doe"
    assert dm2.patient_dob == "1980-03-15"
    assert dm2.presence["vital_signs"].present is True
    assert dm2.presence["vital_signs"].pages == [2]
    assert dm2.presence["vital_signs"].section_hint == "Last Filed Vital Signs"
    assert dm2.presence["lab_observations"].pages == [5, 6, 7]
    assert dm2.presence["clinical_notes"].pages == [22, 23, 24]
    assert dm2.sections == ["Patient Demographics", "Vital Signs", "Results", "Progress Notes"]


def test_resource_presence_pages_default_empty_list() -> None:
    """default_factory for pages means instances are independent; mutating one does not affect another."""
    from lib.extract.pipelines.multipass_fhir import ResourcePresence

    rp1 = ResourcePresence()
    rp2 = ResourcePresence()

    rp1.pages.append(3)

    assert rp1.pages == [3]
    assert rp2.pages == [], "mutating rp1.pages must not affect rp2.pages"


def test_document_map_imports_from_pipeline_module() -> None:
    """Public surface: DocumentMap and ResourcePresence are importable from multipass_fhir."""
    from lib.extract.pipelines.multipass_fhir import DocumentMap, ResourcePresence  # noqa: F401

    assert DocumentMap is not None
    assert ResourcePresence is not None
