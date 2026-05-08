"""Tests for the patient_demographics extraction pass in MultiPassFHIRPipeline.

Verifies schema validation, FHIR shape, US Core extension emission (race,
ethnicity, birthsex), MRN identifier, name decomposition with nickname,
address, telecom, communication/language, maritalStatus, and stable ID
determinism.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from lib.extract.pipelines.multipass_fhir import (
    DocumentContext,
    PatientEntry,
    PatientExtraction,
    MultiPassFHIRPipeline,
    _stable_patient_id,
)


def _new_pipeline() -> MultiPassFHIRPipeline:
    """Construct a pipeline without invoking any LLM backend."""
    p = MultiPassFHIRPipeline.__new__(MultiPassFHIRPipeline)
    p._patient_id = "test-patient"
    return p


def _common_meta() -> dict:
    return {"source": "extracted://clinical-note/test", "extension": []}


def _doc_context() -> DocumentContext:
    return DocumentContext(document_type="patient-summary")


# ---------------------------------------------------------------------------
# 1. Minimal entry — only family_name set
# ---------------------------------------------------------------------------


def test_patient_entry_minimal_validates() -> None:
    """A PatientEntry with only family_name set must construct without error."""
    entry = PatientEntry(family_name="Thomson")
    assert entry.family_name == "Thomson"
    assert entry.given_names == []
    assert entry.patient_id is None
    assert entry.birth_sex is None


# ---------------------------------------------------------------------------
# 2. birth_sex — valid codes M / F / UNK / OTH
# ---------------------------------------------------------------------------


def test_patient_entry_validates_birth_sex_codes() -> None:
    """birth_sex accepts all valid US Core codes: M, F, UNK, OTH."""
    for code in ("M", "F", "UNK", "OTH"):
        entry = PatientEntry(family_name="Test", birth_sex=code)
        assert entry.birth_sex == code


# ---------------------------------------------------------------------------
# 3. birth_sex — rejects invalid value
# ---------------------------------------------------------------------------


def test_patient_entry_rejects_invalid_birth_sex() -> None:
    """birth_sex='MALE' (not a valid literal) → ValidationError."""
    with pytest.raises(ValidationError):
        PatientEntry(family_name="Test", birth_sex="MALE")


# ---------------------------------------------------------------------------
# 4. Minimum resource shape
# ---------------------------------------------------------------------------


def test_patient_to_fhir_minimum_resource() -> None:
    """Only family_name + given_names → resource has correct resourceType, id,
    active=True, and name[0].family + given populated."""
    pipeline = _new_pipeline()
    entry = PatientEntry(family_name="Thomson", given_names=["Blake"])
    resource = pipeline._patient_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert resource["resourceType"] == "Patient"
    assert "id" in resource
    assert resource["active"] is True
    assert "name" in resource
    assert resource["name"][0]["family"] == "Thomson"
    assert resource["name"][0]["given"] == ["Blake"]


# ---------------------------------------------------------------------------
# 5. US Core race extension
# ---------------------------------------------------------------------------


def test_patient_to_fhir_us_core_race_extension() -> None:
    """race_omb_code='2106-3' + race_text='White' → extension contains
    us-core-race with ombCategory.valueCoding.code=='2106-3' AND text='White'."""
    pipeline = _new_pipeline()
    entry = PatientEntry(
        family_name="Thomson",
        race_omb_code="2106-3",
        race_text="White",
    )
    resource = pipeline._patient_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "extension" in resource
    race_ext = next(
        e for e in resource["extension"]
        if e["url"] == "http://hl7.org/fhir/us/core/StructureDefinition/us-core-race"
    )
    inner = {e["url"]: e for e in race_ext["extension"]}
    assert "ombCategory" in inner
    assert inner["ombCategory"]["valueCoding"]["code"] == "2106-3"
    assert inner["ombCategory"]["valueCoding"]["display"] == "White"
    assert "text" in inner
    assert inner["text"]["valueString"] == "White"


# ---------------------------------------------------------------------------
# 6. US Core ethnicity extension
# ---------------------------------------------------------------------------


def test_patient_to_fhir_us_core_ethnicity_extension() -> None:
    """ethnicity_omb_code='2186-5' + ethnicity_text='Not Hispanic or Latino'
    → extension contains us-core-ethnicity with ombCategory.valueCoding.code=='2186-5'
    and text entry."""
    pipeline = _new_pipeline()
    entry = PatientEntry(
        family_name="Thomson",
        ethnicity_omb_code="2186-5",
        ethnicity_text="Not Hispanic or Latino",
    )
    resource = pipeline._patient_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "extension" in resource
    eth_ext = next(
        e for e in resource["extension"]
        if e["url"] == "http://hl7.org/fhir/us/core/StructureDefinition/us-core-ethnicity"
    )
    inner = {e["url"]: e for e in eth_ext["extension"]}
    assert "ombCategory" in inner
    assert inner["ombCategory"]["valueCoding"]["code"] == "2186-5"
    assert inner["ombCategory"]["valueCoding"]["display"] == "Not Hispanic or Latino"
    assert "text" in inner
    assert inner["text"]["valueString"] == "Not Hispanic or Latino"


# ---------------------------------------------------------------------------
# 7. US Core birthsex extension
# ---------------------------------------------------------------------------


def test_patient_to_fhir_us_core_birthsex_extension() -> None:
    """birth_sex='M' → resource.extension has us-core-birthsex with valueCode='M'."""
    pipeline = _new_pipeline()
    entry = PatientEntry(family_name="Thomson", birth_sex="M")
    resource = pipeline._patient_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "extension" in resource
    birthsex_ext = next(
        e for e in resource["extension"]
        if e["url"] == "http://hl7.org/fhir/us/core/StructureDefinition/us-core-birthsex"
    )
    assert birthsex_ext["valueCode"] == "M"


# ---------------------------------------------------------------------------
# 8. MRN identifier emission
# ---------------------------------------------------------------------------


def test_patient_to_fhir_emits_mrn_identifier() -> None:
    """patient_id='33224600' → resource.identifier[0].type.coding[0].code=='MR',
    value=='33224600'."""
    pipeline = _new_pipeline()
    entry = PatientEntry(family_name="Thomson", patient_id="33224600")
    resource = pipeline._patient_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "identifier" in resource
    identifier = resource["identifier"][0]
    assert identifier["type"]["coding"][0]["code"] == "MR"
    assert identifier["value"] == "33224600"


# ---------------------------------------------------------------------------
# 9. Telecom — phones and email
# ---------------------------------------------------------------------------


def test_patient_to_fhir_emits_telecom_phones_and_email() -> None:
    """phone_home + phone_mobile + email → telecom has 3 entries with correct `use` values."""
    pipeline = _new_pipeline()
    entry = PatientEntry(
        family_name="Thomson",
        phone_home="310-555-0001",
        phone_mobile="615-720-2002",
        email="blakethomson8@gmail.com",
    )
    resource = pipeline._patient_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "telecom" in resource
    telecom = resource["telecom"]
    assert len(telecom) == 3

    uses = {t["use"] if "use" in t else t["system"]: t for t in telecom}
    assert uses["home"]["value"] == "310-555-0001"
    assert uses["home"]["system"] == "phone"
    assert uses["mobile"]["value"] == "615-720-2002"
    assert uses["mobile"]["system"] == "phone"
    # email entry has no `use` key
    email_entry = next(t for t in telecom if t["system"] == "email")
    assert email_entry["value"] == "blakethomson8@gmail.com"


# ---------------------------------------------------------------------------
# 10. Address with use=home
# ---------------------------------------------------------------------------


def test_patient_to_fhir_emits_address_with_use_home() -> None:
    """address_line + city + state → resource.address[0] has use='home'."""
    pipeline = _new_pipeline()
    entry = PatientEntry(
        family_name="Thomson",
        address_line="231 BAY ST APT 5",
        city="SANTA MONICA",
        state="CA",
    )
    resource = pipeline._patient_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "address" in resource
    addr = resource["address"][0]
    assert addr["use"] == "home"
    assert addr["line"] == ["231 BAY ST APT 5"]
    assert addr["city"] == "SANTA MONICA"
    assert addr["state"] == "CA"


# ---------------------------------------------------------------------------
# 11. Communication language
# ---------------------------------------------------------------------------


def test_patient_to_fhir_emits_communication_language() -> None:
    """language='English' → resource.communication[0].language.text=='English',
    preferred=True."""
    pipeline = _new_pipeline()
    entry = PatientEntry(family_name="Thomson", language="English")
    resource = pipeline._patient_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "communication" in resource
    comm = resource["communication"][0]
    assert comm["language"]["text"] == "English"
    assert comm["preferred"] is True


# ---------------------------------------------------------------------------
# 12. Marital status text
# ---------------------------------------------------------------------------


def test_patient_to_fhir_emits_marital_status_text() -> None:
    """marital_status='Domestic Partner' → resource.maritalStatus.text=='Domestic Partner'."""
    pipeline = _new_pipeline()
    entry = PatientEntry(family_name="Thomson", marital_status="Domestic Partner")
    resource = pipeline._patient_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "maritalStatus" in resource
    assert resource["maritalStatus"]["text"] == "Domestic Partner"


# ---------------------------------------------------------------------------
# 13. Nickname emitted as usual name
# ---------------------------------------------------------------------------


def test_patient_to_fhir_emits_nickname_as_usual_name() -> None:
    """family_name='Thomson' + given_names=['Blake'] + nickname='Blake'
    → resource.name has 2 entries, second with use='usual'."""
    pipeline = _new_pipeline()
    entry = PatientEntry(
        family_name="Thomson",
        given_names=["Blake"],
        nickname="Blake",
    )
    resource = pipeline._patient_to_fhir(entry, _common_meta(), layout=None, doc_context=_doc_context())

    assert "name" in resource
    assert len(resource["name"]) == 2
    usual_name = resource["name"][1]
    assert usual_name["use"] == "usual"
    assert usual_name["given"] == ["Blake"]


# ---------------------------------------------------------------------------
# 14. Stable ID — prefers MRN
# ---------------------------------------------------------------------------


def test_stable_patient_id_prefers_mrn() -> None:
    """patient_id='33224600' → id starts with 'pat-mrn-'."""
    entry = PatientEntry(family_name="Thomson", patient_id="33224600")
    doc_ctx = _doc_context()
    patient_id = _stable_patient_id(entry, doc_ctx)
    assert patient_id.startswith("pat-mrn-")
    assert "33224600" in patient_id


# ---------------------------------------------------------------------------
# 15. Stable ID — falls back to hash
# ---------------------------------------------------------------------------


def test_stable_patient_id_falls_back_to_hash() -> None:
    """No patient_id but family_name + birth_date → id starts with 'pat-' + 12-char hex."""
    entry = PatientEntry(family_name="Thomson", given_names=["Blake"], birth_date="1993-06-16")
    doc_ctx = _doc_context()
    patient_id = _stable_patient_id(entry, doc_ctx)
    assert patient_id.startswith("pat-")
    suffix = patient_id[len("pat-"):]
    assert len(suffix) == 12
    assert all(c in "0123456789abcdef" for c in suffix)
