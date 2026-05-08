"""Tests for lib.harmonize.organizations — Organization cross-source matcher."""

from __future__ import annotations

import pytest

from lib.harmonize.organizations import (
    OrganizationKey,
    is_same_organization,
    organization_key,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _org(
    name: str | None = "Cedars-Sinai Health System",
    city: str | None = None,
    state: str | None = None,
    identifiers: list[dict] | None = None,
) -> dict:
    resource: dict = {"resourceType": "Organization"}
    if name is not None:
        resource["name"] = name
    if identifiers is not None:
        resource["identifier"] = identifiers
    address: dict = {}
    if city is not None:
        address["city"] = city
    if state is not None:
        address["state"] = state
    if address:
        resource["address"] = [address]
    return resource


# ---------------------------------------------------------------------------
# organization_key tests
# ---------------------------------------------------------------------------


def test_organization_key_normalizes_name() -> None:
    resource = _org(name="Cedars-Sinai Health System")
    key = organization_key(resource)
    assert key is not None
    assert key.normalized_name == "cedars sinai health system"


def test_organization_key_returns_none_for_no_name() -> None:
    resource = {"resourceType": "Organization"}
    assert organization_key(resource) is None


def test_organization_key_returns_none_for_wrong_resource_type() -> None:
    resource = {"resourceType": "Patient", "name": "Cedars-Sinai Health System"}
    assert organization_key(resource) is None


def test_organization_key_extracts_first_identifier() -> None:
    identifiers = [
        {"system": "http://example.com/npi", "value": "1234567890"},
        {"system": "http://example.com/other", "value": "ABCDEFGH"},
    ]
    resource = _org(identifiers=identifiers)
    key = organization_key(resource)
    assert key is not None
    assert key.identifier_value == "1234567890"
    assert key.identifier_system == "http://example.com/npi"


def test_organization_key_extracts_city_and_state_uppercase() -> None:
    resource = _org(city="los angeles", state="ca")
    key = organization_key(resource)
    assert key is not None
    assert key.city == "LOS ANGELES"
    assert key.state == "CA"


# ---------------------------------------------------------------------------
# is_same_organization tests
# ---------------------------------------------------------------------------


def test_is_same_organization_identifier_match() -> None:
    a = _org(
        name="Cedars-Sinai Health System",
        identifiers=[{"system": "http://hl7.org/fhir/sid/us-npi", "value": "1234567890"}],
    )
    b = _org(
        name="Cedars Sinai",  # different display name
        identifiers=[{"system": "http://hl7.org/fhir/sid/us-npi", "value": "1234567890"}],
    )
    assert is_same_organization(a, b) is True


def test_is_same_organization_identifier_mismatch_decisive() -> None:
    # Even though names could match, different identifiers means different org.
    a = _org(
        name="Cedars-Sinai Health System",
        identifiers=[{"system": "http://hl7.org/fhir/sid/us-npi", "value": "1111111111"}],
    )
    b = _org(
        name="Cedars-Sinai Health System",
        identifiers=[{"system": "http://hl7.org/fhir/sid/us-npi", "value": "9999999999"}],
    )
    assert is_same_organization(a, b) is False


def test_is_same_organization_name_city_state_match() -> None:
    a = _org(name="Valley Medical Center", city="San Jose", state="CA")
    b = _org(name="Valley Medical Center", city="San Jose", state="CA")
    assert is_same_organization(a, b) is True


def test_is_same_organization_same_name_different_state() -> None:
    # A chain with same name in different states = different locations.
    a = _org(name="Community Health Network", city="Indianapolis", state="IN")
    b = _org(name="Community Health Network", city="Phoenix", state="AZ")
    assert is_same_organization(a, b) is False


def test_is_same_organization_same_name_one_missing_city() -> None:
    # When one record has no city/state, accept the name match (lenient).
    a = _org(name="Sunrise Hospital")
    b = _org(name="Sunrise Hospital", city="Las Vegas", state="NV")
    assert is_same_organization(a, b) is True
