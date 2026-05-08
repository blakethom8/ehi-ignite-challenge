"""Tests for the organization extraction pass in MultiPassFHIRPipeline.

Verifies schema validation (type_code Literal), FHIR shape, type coding,
telecom emission, address emission, and stable-ID determinism.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lib.extract.pipelines.multipass_fhir import (
    DocumentContext,
    OrganizationEntry,
    OrganizationExtraction,
    MultiPassFHIRPipeline,
    _stable_organization_id,
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
# 1. OrganizationEntry requires name
# ---------------------------------------------------------------------------


def test_organization_entry_requires_name() -> None:
    """Instantiating OrganizationEntry without name must raise a pydantic ValidationError."""
    with pytest.raises(ValidationError):
        OrganizationEntry()  # type: ignore[call-arg]


# ---------------------------------------------------------------------------
# 2. Valid type_codes accepted
# ---------------------------------------------------------------------------


def test_organization_entry_validates_type_codes() -> None:
    """Each of the supported HL7 organization-type codes must pass validation."""
    valid_codes = ["prov", "dept", "team", "ins", "pay", "edu", "reli", "crs", "cg", "bus", "other"]
    for code in valid_codes:
        entry = OrganizationEntry(name="Test Org", type_code=code)
        assert entry.type_code == code


# ---------------------------------------------------------------------------
# 3. Invalid type_code rejected
# ---------------------------------------------------------------------------


def test_organization_entry_rejects_invalid_type_code() -> None:
    """An unrecognized type_code string must raise a pydantic ValidationError."""
    with pytest.raises(ValidationError):
        OrganizationEntry(name="Test Org", type_code="HOSPITAL")


# ---------------------------------------------------------------------------
# 4. Minimum resource shape
# ---------------------------------------------------------------------------


def test_organization_to_fhir_emits_minimum_resource() -> None:
    """With only name set, the emitted resource must have required keys and correct values."""
    pipeline = _new_pipeline()
    entry = OrganizationEntry(name="Beverly Hills Allergy")
    resource = pipeline._organization_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert resource["resourceType"] == "Organization"
    assert resource["name"] == "Beverly Hills Allergy"
    assert "id" in resource
    assert resource["id"]  # non-empty
    assert resource["active"] is True


# ---------------------------------------------------------------------------
# 5. type with code and display
# ---------------------------------------------------------------------------


def test_organization_to_fhir_emits_type_with_code_and_display() -> None:
    """type_code='prov' + type_display='Allergy Clinic' → coding code 'prov' and type text."""
    pipeline = _new_pipeline()
    entry = OrganizationEntry(
        name="Beverly Hills Allergy",
        type_code="prov",
        type_display="Allergy Clinic",
    )
    resource = pipeline._organization_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "type" in resource
    assert len(resource["type"]) == 1
    type_entry = resource["type"][0]
    assert "coding" in type_entry
    assert type_entry["coding"][0]["code"] == "prov"
    assert type_entry["coding"][0]["system"] == "http://terminology.hl7.org/CodeSystem/organization-type"
    assert type_entry["text"] == "Allergy Clinic"


# ---------------------------------------------------------------------------
# 6. type text only when no code
# ---------------------------------------------------------------------------


def test_organization_to_fhir_emits_type_text_only_when_no_code() -> None:
    """type_display set but type_code=None → resource.type[0].text populated, no coding array."""
    pipeline = _new_pipeline()
    entry = OrganizationEntry(
        name="Quest Diagnostics",
        type_code=None,
        type_display="Diagnostic Lab",
    )
    resource = pipeline._organization_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "type" in resource
    type_entry = resource["type"][0]
    assert type_entry.get("text") == "Diagnostic Lab"
    assert "coding" not in type_entry


# ---------------------------------------------------------------------------
# 7. Telecom — phone and fax
# ---------------------------------------------------------------------------


def test_organization_to_fhir_emits_telecom_phone_and_fax() -> None:
    """phone + fax set → telecom list has 2 entries with correct system values."""
    pipeline = _new_pipeline()
    entry = OrganizationEntry(
        name="Cedars-Sinai Health System",
        phone="3104238000",
        fax="3104238001",
    )
    resource = pipeline._organization_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "telecom" in resource
    telecom = resource["telecom"]
    assert len(telecom) == 2
    systems = {t["system"] for t in telecom}
    assert systems == {"phone", "fax"}
    phone_entry = next(t for t in telecom if t["system"] == "phone")
    fax_entry = next(t for t in telecom if t["system"] == "fax")
    assert phone_entry["value"] == "3104238000"
    assert fax_entry["value"] == "3104238001"
    assert phone_entry["use"] == "work"
    assert fax_entry["use"] == "work"


# ---------------------------------------------------------------------------
# 8. Address emission
# ---------------------------------------------------------------------------


def test_organization_to_fhir_emits_address() -> None:
    """address_line / city / state / postal_code set → resource.address[0] populated."""
    pipeline = _new_pipeline()
    entry = OrganizationEntry(
        name="MORTON HOSPITAL",
        address_line="88 WASHINGTON STREET",
        city="TAUNTON",
        state="MA",
        postal_code="02780",
    )
    resource = pipeline._organization_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "address" in resource
    addr = resource["address"][0]
    assert addr["line"] == ["88 WASHINGTON STREET"]
    assert addr["city"] == "TAUNTON"
    assert addr["state"] == "MA"
    assert addr["postalCode"] == "02780"


# ---------------------------------------------------------------------------
# 9. Stable organization ID — deterministic
# ---------------------------------------------------------------------------


def test_stable_organization_id_is_deterministic() -> None:
    """Same name + city + state → same ID; different state → different ID."""
    entry_a = OrganizationEntry(name="Quest Diagnostics", city="West Hills", state="CA")
    entry_b = OrganizationEntry(name="Quest Diagnostics", city="West Hills", state="CA")
    entry_c = OrganizationEntry(name="Quest Diagnostics", city="West Hills", state="TX")

    id_a = _stable_organization_id(entry_a)
    id_b = _stable_organization_id(entry_b)
    id_c = _stable_organization_id(entry_c)

    assert id_a == id_b, "Same inputs must produce the same stable ID"
    assert id_a != id_c, "Different state must produce a different stable ID"
    assert id_a.startswith("org-"), "Stable IDs must use the 'org-' prefix"
