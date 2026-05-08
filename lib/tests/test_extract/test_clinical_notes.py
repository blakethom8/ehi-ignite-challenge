"""Tests for the clinical_notes extraction pass — DocumentReference + Composition.

T07: clinical-notes extraction pass. Each ClinicalNoteEntry produces exactly two
FHIR resources: a DocumentReference (narrative container) and a Composition
(sectioned structure). Both share a stable note_id-derived id suffix.
"""

from __future__ import annotations

import base64

import pytest
from pydantic import ValidationError

from lib.extract.pipelines.multipass_fhir import (
    ClinicalNoteEntry,
    ClinicalNoteExtraction,
    ClinicalNoteSection,
    DocumentContext,
    MultiPassFHIRPipeline,
    _stable_clinical_note_id,
)


def _new_pipeline() -> MultiPassFHIRPipeline:
    """Construct a pipeline without invoking any LLM backend."""
    p = MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)
    p._patient_id = "test-patient"
    p._backend_name = "anthropic"
    p._model = None
    return p


def _minimal_doc_context() -> DocumentContext:
    return DocumentContext(
        document_type="clinical-note",
        encounter_date="2024-03-15",
    )


def _common_meta() -> dict:
    return {
        "source": "extracted://clinical-note/test-doc",
        "extension": [],
    }


# ---------------------------------------------------------------------------
# 1. Schema validation — ClinicalNoteSection requires title and text
# ---------------------------------------------------------------------------


def test_clinical_note_section_requires_title_and_text() -> None:
    """ClinicalNoteSection without title or without narrative_text → ValidationError."""
    # Missing title
    with pytest.raises(ValidationError):
        ClinicalNoteSection(narrative_text="Some text")  # type: ignore[call-arg]

    # Missing narrative_text
    with pytest.raises(ValidationError):
        ClinicalNoteSection(title="Subjective")  # type: ignore[call-arg]

    # Both present → no error
    section = ClinicalNoteSection(title="Subjective", narrative_text="Patient reports headache.")
    assert section.title == "Subjective"
    assert section.narrative_text == "Patient reports headache."


# ---------------------------------------------------------------------------
# 2. Schema validation — ClinicalNoteEntry validates all note_type literals
# ---------------------------------------------------------------------------


def test_clinical_note_entry_validates_note_types() -> None:
    """Each valid note_type literal instantiates without error."""
    valid_types = [
        "progress-note",
        "consult-note",
        "discharge-summary",
        "procedure-note",
        "history-and-physical",
        "patient-education",
        "telephone-encounter",
        "other",
    ]
    for note_type in valid_types:
        entry = ClinicalNoteEntry(note_type=note_type)
        assert entry.note_type == note_type

    # Invalid type → ValidationError
    with pytest.raises(ValidationError):
        ClinicalNoteEntry(note_type="made-up-type")  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# 3. _clinical_note_to_fhir_resources returns exactly 2 resources
# ---------------------------------------------------------------------------


def test_clinical_note_to_fhir_emits_two_resources() -> None:
    """Minimal ClinicalNoteEntry → list of 2 resources with correct resourceTypes."""
    pipeline = _new_pipeline()
    entry = ClinicalNoteEntry(
        note_type="progress-note",
        title="Progress Note",
        author_name="Jane Smith",
        author_role="MD",
        encounter_date="2024-03-15",
    )
    doc_context = _minimal_doc_context()
    resources = pipeline._clinical_note_to_fhir_resources(entry, _common_meta(), None, doc_context)

    assert len(resources) == 2
    resource_types = {r["resourceType"] for r in resources}
    assert resource_types == {"DocumentReference", "Composition"}


# ---------------------------------------------------------------------------
# 4. DocumentReference carries base64 narrative
# ---------------------------------------------------------------------------


def test_clinical_note_documentreference_carries_base64_narrative() -> None:
    """Entry with title + 2 sections → DocumentReference.content[0].attachment.data
    decodes to a string containing the title and both section titles+narratives."""
    pipeline = _new_pipeline()
    entry = ClinicalNoteEntry(
        note_type="progress-note",
        title="Allergy Progress Note",
        sections=[
            ClinicalNoteSection(title="Subjective", narrative_text="Patient has nasal congestion."),
            ClinicalNoteSection(title="Assessment", narrative_text="Allergic rhinitis, seasonal."),
        ],
        encounter_date="2024-03-15",
    )
    doc_context = _minimal_doc_context()
    resources = pipeline._clinical_note_to_fhir_resources(entry, _common_meta(), None, doc_context)

    doc_ref = next(r for r in resources if r["resourceType"] == "DocumentReference")
    encoded = doc_ref["content"][0]["attachment"]["data"]
    decoded = base64.b64decode(encoded).decode("utf-8")

    assert "Allergy Progress Note" in decoded
    assert "Subjective" in decoded
    assert "Patient has nasal congestion." in decoded
    assert "Assessment" in decoded
    assert "Allergic rhinitis, seasonal." in decoded


# ---------------------------------------------------------------------------
# 5. Composition preserves section structure
# ---------------------------------------------------------------------------


def test_clinical_note_composition_preserves_section_structure() -> None:
    """Entry with 3 sections → Composition.section has 3 entries, each with title
    and text.div containing the narrative wrapped in xhtml div."""
    pipeline = _new_pipeline()
    entry = ClinicalNoteEntry(
        note_type="history-and-physical",
        title="H&P",
        sections=[
            ClinicalNoteSection(title="Chief Complaint", narrative_text="Chest pain for 2 days."),
            ClinicalNoteSection(title="Physical Exam", narrative_text="Heart rate regular, no murmurs."),
            ClinicalNoteSection(title="Plan", narrative_text="EKG ordered. Follow up in 1 week."),
        ],
        encounter_date="2024-03-15",
    )
    doc_context = _minimal_doc_context()
    resources = pipeline._clinical_note_to_fhir_resources(entry, _common_meta(), None, doc_context)

    composition = next(r for r in resources if r["resourceType"] == "Composition")
    sections = composition["section"]
    assert len(sections) == 3

    titles = [s["title"] for s in sections]
    assert titles == ["Chief Complaint", "Physical Exam", "Plan"]

    for section, expected_text in zip(sections, [
        "Chest pain for 2 days.",
        "Heart rate regular, no murmurs.",
        "EKG ordered. Follow up in 1 week.",
    ]):
        div = section["text"]["div"]
        assert expected_text in div
        assert '<div xmlns="http://www.w3.org/1999/xhtml">' in div


# ---------------------------------------------------------------------------
# 6. Default LOINC for progress-note when note_type_loinc is None
# ---------------------------------------------------------------------------


def test_clinical_note_uses_default_loinc_for_progress_note() -> None:
    """note_type='progress-note', note_type_loinc=None → both resources have
    type.coding[0].code == '11506-3'."""
    pipeline = _new_pipeline()
    entry = ClinicalNoteEntry(
        note_type="progress-note",
        note_type_loinc=None,
        title="Progress Note",
        encounter_date="2024-03-15",
    )
    doc_context = _minimal_doc_context()
    resources = pipeline._clinical_note_to_fhir_resources(entry, _common_meta(), None, doc_context)

    for resource in resources:
        code = resource["type"]["coding"][0]["code"]
        assert code == "11506-3", f"{resource['resourceType']} had unexpected LOINC: {code}"


# ---------------------------------------------------------------------------
# 7. Section LOINC code emitted when provided
# ---------------------------------------------------------------------------


def test_clinical_note_section_loinc_emitted_when_provided() -> None:
    """Section with loinc_code='29545-1' → that section in Composition has
    code.coding[0].code == '29545-1'."""
    pipeline = _new_pipeline()
    entry = ClinicalNoteEntry(
        note_type="progress-note",
        title="SOAP Note",
        sections=[
            ClinicalNoteSection(
                title="Physical Exam",
                narrative_text="No acute distress.",
                loinc_code="29545-1",
            ),
        ],
        encounter_date="2024-03-15",
    )
    doc_context = _minimal_doc_context()
    resources = pipeline._clinical_note_to_fhir_resources(entry, _common_meta(), None, doc_context)

    composition = next(r for r in resources if r["resourceType"] == "Composition")
    section = composition["section"][0]
    assert section["code"]["coding"][0]["code"] == "29545-1"
    assert section["code"]["coding"][0]["system"] == "http://loinc.org"


# ---------------------------------------------------------------------------
# 8. Author renders with role
# ---------------------------------------------------------------------------


def test_clinical_note_author_renders_with_role() -> None:
    """author_name='Ani Shirvanian', author_role='NP' →
    DocumentReference.author[0].display == 'Ani Shirvanian, NP'."""
    pipeline = _new_pipeline()
    entry = ClinicalNoteEntry(
        note_type="consult-note",
        author_name="Ani Shirvanian",
        author_role="NP",
        encounter_date="2024-03-15",
    )
    doc_context = _minimal_doc_context()
    resources = pipeline._clinical_note_to_fhir_resources(entry, _common_meta(), None, doc_context)

    doc_ref = next(r for r in resources if r["resourceType"] == "DocumentReference")
    assert doc_ref["author"][0]["display"] == "Ani Shirvanian, NP"

    composition = next(r for r in resources if r["resourceType"] == "Composition")
    assert composition["author"][0]["display"] == "Ani Shirvanian, NP"


# ---------------------------------------------------------------------------
# 9. Note ID is stable and shared across both resources
# ---------------------------------------------------------------------------


def test_clinical_note_id_is_stable() -> None:
    """Same inputs → same note_id; both resources use the same id-derived suffix."""
    entry = ClinicalNoteEntry(
        note_type="progress-note",
        title="Allergy & Immunology Progress Note",
        author_name="Ani Shirvanian",
        encounter_date="2024-03-15",
        page_start=22,
    )
    doc_context = _minimal_doc_context()

    # Call twice — should be identical
    id1 = _stable_clinical_note_id(entry, doc_context)
    id2 = _stable_clinical_note_id(entry, doc_context)
    assert id1 == id2
    assert id1.startswith("note-")

    # Both resources use the same suffix
    pipeline = _new_pipeline()
    resources = pipeline._clinical_note_to_fhir_resources(entry, _common_meta(), None, doc_context)
    doc_ref = next(r for r in resources if r["resourceType"] == "DocumentReference")
    composition = next(r for r in resources if r["resourceType"] == "Composition")

    suffix = id1[len("note-"):]
    assert doc_ref["id"] == f"docref-note-{suffix}"
    assert composition["id"] == f"comp-note-{suffix}"


# ---------------------------------------------------------------------------
# 10. Encounter linkage now covers DocumentReference and Composition (T08)
# ---------------------------------------------------------------------------


def test_encounter_linkage_links_clinical_notes() -> None:
    """Entries with one Encounter + DocumentReference + Composition →
    after _assign_encounter_references (T08), both are linked to the encounter.
    DocumentReference uses context.encounter[], Composition uses encounter."""
    pipeline = _new_pipeline()
    enc = {
        "resourceType": "Encounter",
        "id": "enc-abc123",
        "period": {"start": "2024-03-15"},
    }
    doc_ref = {
        "resourceType": "DocumentReference",
        "id": "docref-note-abc",
        "status": "current",
    }
    composition = {
        "resourceType": "Composition",
        "id": "comp-note-abc",
        "status": "final",
    }
    entries = [
        {"resource": enc},
        {"resource": doc_ref},
        {"resource": composition},
    ]

    pipeline._assign_encounter_references(entries)

    # DocumentReference uses FHIR R4 context.encounter[] (a list)
    ctx = doc_ref.get("context") or {}
    enc_refs = ctx.get("encounter") or []
    assert len(enc_refs) == 1
    assert enc_refs[0]["reference"] == "Encounter/enc-abc123"

    # Composition uses FHIR R4 encounter (singular)
    assert composition["encounter"]["reference"] == "Encounter/enc-abc123"
