"""Tests for lib.harmonize.practitioners — NPI-based Practitioner matcher."""

from __future__ import annotations

import pytest

from lib.harmonize.practitioners import (
    PractitionerKey,
    is_same_practitioner,
    practitioner_key,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _practitioner(
    npi: str | None = None,
    family: str | None = None,
    given: list[str] | None = None,
    prefix: str | None = None,
    suffix: str | None = None,
    name_text: str | None = None,
    resource_type: str = "Practitioner",
) -> dict:
    """Build a minimal FHIR Practitioner resource for testing."""
    resource: dict = {"resourceType": resource_type}

    if npi:
        resource["identifier"] = [
            {
                "system": "http://hl7.org/fhir/sid/us-npi",
                "value": npi,
            }
        ]

    name_entry: dict = {}
    if family:
        name_entry["family"] = family
    if given:
        name_entry["given"] = given
    if prefix:
        name_entry["prefix"] = [prefix]
    if suffix:
        name_entry["suffix"] = [suffix]
    if name_text:
        name_entry["text"] = name_text
    if name_entry:
        resource["name"] = [name_entry]

    return resource


# ---------------------------------------------------------------------------
# practitioner_key() tests
# ---------------------------------------------------------------------------


def test_practitioner_key_extracts_npi() -> None:
    """Practitioner with us-npi identifier → key.npi is populated."""
    p = _practitioner(npi="1234567890", family="Smith", given=["John"])
    key = practitioner_key(p)
    assert key is not None
    assert key.npi == "1234567890"


def test_practitioner_key_extracts_normalized_name() -> None:
    """Name with family + given + prefix + suffix → lowercased, punctuation-stripped."""
    p = _practitioner(
        family="O'Brien",
        given=["Mary", "Jane"],
        prefix="Dr.",
        suffix="M.D.",
    )
    key = practitioner_key(p)
    assert key is not None
    # Punctuation stripped, lowercased, whitespace normalized.
    # Order: prefix given... family suffix → "dr mary jane o brien m d"
    assert key.normalized_name == "dr mary jane o brien m d"


def test_practitioner_key_returns_none_when_no_identity() -> None:
    """Empty Practitioner (no NPI, no name) → returns None."""
    p: dict = {"resourceType": "Practitioner"}
    key = practitioner_key(p)
    assert key is None


def test_practitioner_key_returns_none_for_wrong_resource_type() -> None:
    """Non-Practitioner resource → returns None."""
    patient = {
        "resourceType": "Patient",
        "identifier": [{"system": "http://hl7.org/fhir/sid/us-npi", "value": "9999999999"}],
        "name": [{"family": "Doe", "given": ["Jane"]}],
    }
    key = practitioner_key(patient)
    assert key is None


def test_practitioner_key_uses_text_fallback() -> None:
    """Practitioner with name.text but no family/given → key uses normalized text."""
    p = _practitioner(name_text="Dr. Alice Nguyen, M.D.")
    key = practitioner_key(p)
    assert key is not None
    # text field normalized: punctuation stripped, lowercased
    assert key.normalized_name == "dr alice nguyen m d"


# ---------------------------------------------------------------------------
# is_same_practitioner() tests
# ---------------------------------------------------------------------------


def test_is_same_practitioner_npi_match() -> None:
    """Two Practitioners with the same NPI but different names → True."""
    a = _practitioner(npi="1234567890", family="Smith", given=["John"])
    b = _practitioner(npi="1234567890", family="Smyth", given=["Jon"])
    assert is_same_practitioner(a, b) is True


def test_is_same_practitioner_npi_mismatch() -> None:
    """Two Practitioners with different NPIs → False, even if names match."""
    a = _practitioner(npi="1111111111", family="Smith", given=["John"])
    b = _practitioner(npi="2222222222", family="Smith", given=["John"])
    assert is_same_practitioner(a, b) is False


def test_is_same_practitioner_name_match_when_no_npi() -> None:
    """Both lack NPI but normalized names match → True."""
    a = _practitioner(family="Garcia", given=["Luis"])
    b = _practitioner(family="Garcia", given=["Luis"])
    assert is_same_practitioner(a, b) is True


def test_is_same_practitioner_no_match() -> None:
    """Different names and no NPI → False."""
    a = _practitioner(family="Garcia", given=["Luis"])
    b = _practitioner(family="Chen", given=["Wei"])
    assert is_same_practitioner(a, b) is False


def test_is_same_practitioner_one_has_npi_other_doesnt() -> None:
    """One has NPI, the other doesn't, but names match → True (falls back to name)."""
    a = _practitioner(npi="1234567890", family="Patel", given=["Ravi"])
    b = _practitioner(family="Patel", given=["Ravi"])
    assert is_same_practitioner(a, b) is True
