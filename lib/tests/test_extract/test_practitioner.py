"""Tests for the practitioner extraction pass in MultiPassFHIRPipeline.

Verifies schema validation, FHIR shape, NPI identifier emission, name
decomposition, display-name text fallback, telecom/address rendering,
specialty/role extensions, and stable-ID determinism.
"""

from __future__ import annotations

from lib.extract.pipelines.multipass_fhir import (
    DocumentContext,
    PractitionerEntry,
    PractitionerExtraction,
    MultiPassFHIRPipeline,
    _stable_practitioner_id,
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
# 1. Minimal entry — only display_name set
# ---------------------------------------------------------------------------


def test_practitioner_entry_minimal_validates() -> None:
    """A PractitionerEntry with only display_name set must construct without error."""
    entry = PractitionerEntry(display_name="Steven Krems, MD")
    assert entry.display_name == "Steven Krems, MD"
    assert entry.npi is None
    assert entry.given_names == []


# ---------------------------------------------------------------------------
# 2. Full entry — all fields populated
# ---------------------------------------------------------------------------


def test_practitioner_entry_full_validates() -> None:
    """A PractitionerEntry with all fields populated must construct without error."""
    entry = PractitionerEntry(
        practitioner_id="prac-001",
        npi="1972605020",
        display_name="Steven Krems, MD",
        family_name="Krems",
        given_names=["Steven"],
        prefix="Dr.",
        suffix="MD",
        specialty="Allergy & Immunology",
        role="PCP",
        phone="310-306-6966",
        address_line="4676 ADMIRALTY WAY SUITE 400",
        city="MARINA DEL REY",
        state="CA",
        postal_code="90292",
        page=1,
        source_text="Steven Krems, MD — Primary Care Physician",
    )
    assert entry.npi == "1972605020"
    assert entry.family_name == "Krems"
    assert entry.given_names == ["Steven"]
    assert entry.specialty == "Allergy & Immunology"
    assert entry.role == "PCP"


# ---------------------------------------------------------------------------
# 3. NPI identifier emission
# ---------------------------------------------------------------------------


def test_practitioner_to_fhir_emits_npi_identifier() -> None:
    """npi='1972605020' → resource.identifier[0].system == us-npi and value matches."""
    pipeline = _new_pipeline()
    entry = PractitionerEntry(npi="1972605020", family_name="Krems", given_names=["Steven"])
    resource = pipeline._practitioner_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert resource["resourceType"] == "Practitioner"
    assert "identifier" in resource
    assert len(resource["identifier"]) == 1
    assert resource["identifier"][0]["system"] == "http://hl7.org/fhir/sid/us-npi"
    assert resource["identifier"][0]["value"] == "1972605020"


# ---------------------------------------------------------------------------
# 4. Decomposed name — family / given / prefix / suffix
# ---------------------------------------------------------------------------


def test_practitioner_to_fhir_emits_decomposed_name() -> None:
    """family_name + given_names + prefix + suffix → name[0] has all parts populated."""
    pipeline = _new_pipeline()
    entry = PractitionerEntry(
        family_name="Krems",
        given_names=["Steven"],
        prefix="Dr.",
        suffix="MD",
        display_name="Steven Krems, MD",
    )
    resource = pipeline._practitioner_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "name" in resource
    name = resource["name"][0]
    assert name["family"] == "Krems"
    assert name["given"] == ["Steven"]
    assert name["prefix"] == ["Dr."]
    assert name["suffix"] == ["MD"]


# ---------------------------------------------------------------------------
# 5. Display-name text fallback (no decomposed parts)
# ---------------------------------------------------------------------------


def test_practitioner_to_fhir_uses_display_name_text_fallback() -> None:
    """Only display_name set → name[0].text == display_name (no family/given/prefix/suffix)."""
    pipeline = _new_pipeline()
    entry = PractitionerEntry(display_name="Nathan Razbannia MD")
    resource = pipeline._practitioner_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "name" in resource
    name = resource["name"][0]
    assert name.get("text") == "Nathan Razbannia MD"
    assert "family" not in name
    assert "given" not in name


# ---------------------------------------------------------------------------
# 6. Telecom and address emission
# ---------------------------------------------------------------------------


def test_practitioner_to_fhir_emits_telecom_and_address() -> None:
    """phone + city/state populated → resource has telecom and address entries."""
    pipeline = _new_pipeline()
    entry = PractitionerEntry(
        display_name="Dr. Sherwin Hariri",
        phone="310-123-4567",
        city="Los Angeles",
        state="CA",
    )
    resource = pipeline._practitioner_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "telecom" in resource
    assert resource["telecom"][0]["system"] == "phone"
    assert resource["telecom"][0]["value"] == "310-123-4567"
    assert resource["telecom"][0]["use"] == "work"

    assert "address" in resource
    addr = resource["address"][0]
    assert addr["city"] == "Los Angeles"
    assert addr["state"] == "CA"


# ---------------------------------------------------------------------------
# 7. Specialty and role extensions
# ---------------------------------------------------------------------------


def test_practitioner_to_fhir_emits_specialty_and_role_extensions() -> None:
    """specialty + role set → resource.meta.extension contains both with documented URLs."""
    pipeline = _new_pipeline()
    entry = PractitionerEntry(
        display_name="Ani Shirvanian, NP",
        specialty="Allergy & Immunology",
        role="Attending",
    )
    resource = pipeline._practitioner_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    extensions = resource["meta"]["extension"]
    ext_urls = {ext["url"]: ext["valueString"] for ext in extensions}

    assert (
        "https://ehi-atlas.example/fhir/StructureDefinition/practitioner-specialty" in ext_urls
    )
    assert ext_urls["https://ehi-atlas.example/fhir/StructureDefinition/practitioner-specialty"] == "Allergy & Immunology"

    assert (
        "https://ehi-atlas.example/fhir/StructureDefinition/practitioner-role" in ext_urls
    )
    assert ext_urls["https://ehi-atlas.example/fhir/StructureDefinition/practitioner-role"] == "Attending"


# ---------------------------------------------------------------------------
# 8. Stable ID — NPI-derived vs SHA1-derived
# ---------------------------------------------------------------------------


def test_stable_practitioner_id_prefers_npi() -> None:
    """Entry with NPI → id == 'prac-npi-{npi}'; without NPI → id == 'prac-{12-char-hex}'."""
    entry_with_npi = PractitionerEntry(npi="1972605020", family_name="Krems")
    id_npi = _stable_practitioner_id(entry_with_npi)
    assert id_npi == "prac-npi-1972605020"

    entry_no_npi = PractitionerEntry(display_name="Dr. Sherwin Hariri")
    id_hash = _stable_practitioner_id(entry_no_npi)
    assert id_hash.startswith("prac-")
    # Strip prefix and check 12-char hex
    suffix = id_hash[len("prac-"):]
    assert len(suffix) == 12
    assert all(c in "0123456789abcdef" for c in suffix)


# ---------------------------------------------------------------------------
# 9. Stable ID is deterministic (no NPI path)
# ---------------------------------------------------------------------------


def test_stable_practitioner_id_is_deterministic() -> None:
    """Same inputs (no NPI) always produce the same id; different inputs produce different ids."""
    entry_a = PractitionerEntry(
        display_name="Dr. Brandon Cohen",
        family_name="Cohen",
        given_names=["Brandon"],
        prefix="Dr.",
        suffix="MD",
    )
    entry_b = PractitionerEntry(
        display_name="Dr. Brandon Cohen",
        family_name="Cohen",
        given_names=["Brandon"],
        prefix="Dr.",
        suffix="MD",
    )
    entry_c = PractitionerEntry(
        display_name="Ani Shirvanian, NP",
        family_name="Shirvanian",
        given_names=["Ani"],
        suffix="NP",
    )

    id_a = _stable_practitioner_id(entry_a)
    id_b = _stable_practitioner_id(entry_b)
    id_c = _stable_practitioner_id(entry_c)

    assert id_a == id_b, "Same inputs must produce the same stable ID"
    assert id_a != id_c, "Different inputs must produce different stable IDs"
    assert id_a.startswith("prac-"), "Stable IDs must use the 'prac-' prefix"
