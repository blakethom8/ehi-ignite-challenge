"""Tests for ehi_atlas.harmonize.provider_identity — Provider identity resolution."""

from __future__ import annotations

import json
import pathlib

import pytest

from ehi_atlas.harmonize.provider_identity import (
    CanonicalProvider,
    ProviderFingerprint,
    ProviderIdentityIndex,
    ProviderMatchScore,
    NPI_SYSTEM,
    NAME_THRESHOLD,
    build_provider_identity_index,
    fingerprint_from_practitioner_resource,
    merged_practitioner_resource,
    score_providers,
)

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

SILVER_BUNDLE = (
    pathlib.Path(__file__).parent.parent.parent
    / "corpus"
    / "silver"
    / "synthea"
    / "rhett759"
    / "bundle.json"
)


def _make_practitioner(
    pid: str = "prac-001",
    npi: str | None = "1234567890",
    family: str = "Smith",
    given: list[str] | None = None,
    specialty_codes: list[str] | None = None,
) -> dict:
    """Build a minimal FHIR Practitioner dict for testing."""
    resource: dict = {
        "resourceType": "Practitioner",
        "id": pid,
        "name": [
            {
                "family": family,
                "given": given or ["John"],
                "use": "official",
            }
        ],
    }
    if npi is not None:
        resource["identifier"] = [{"system": NPI_SYSTEM, "value": npi}]
    else:
        resource["identifier"] = []

    if specialty_codes:
        resource["qualification"] = [
            {
                "code": {
                    "coding": [{"code": code, "system": "http://nucc.org/provider-taxonomy"}]
                }
            }
            for code in specialty_codes
        ]
    return resource


def _make_fp(
    source: str = "test-source",
    local_id: str = "prac-001",
    npi: str | None = "1234567890",
    family: str = "Smith",
    given: tuple[str, ...] = ("John",),
    specialty_codes: tuple[str, ...] = (),
    organization: str | None = None,
) -> ProviderFingerprint:
    return ProviderFingerprint(
        source=source,
        local_practitioner_id=local_id,
        npi=npi,
        family_name=family,
        given_names=given,
        specialty_codes=specialty_codes,
        organization=organization,
    )


# ---------------------------------------------------------------------------
# 1. fingerprint_from_practitioner_resource — NPI present
# ---------------------------------------------------------------------------


def test_fingerprint_extracts_npi_when_present():
    """Practitioner with identifier system=NPI_SYSTEM → fingerprint.npi populated."""
    prac = _make_practitioner(pid="doc-001", npi="1234567890")
    fp = fingerprint_from_practitioner_resource("synthea", prac)

    assert fp.npi == "1234567890"
    assert fp.source == "synthea"
    assert fp.local_practitioner_id == "doc-001"
    assert fp.family_name == "Smith"
    assert "John" in fp.given_names


# ---------------------------------------------------------------------------
# 2. fingerprint_from_practitioner_resource — NPI absent
# ---------------------------------------------------------------------------


def test_fingerprint_handles_missing_npi():
    """Practitioner with no NPI identifier → fingerprint.npi is None."""
    prac = _make_practitioner(pid="doc-002", npi=None)
    fp = fingerprint_from_practitioner_resource("ccda", prac)

    assert fp.npi is None
    assert fp.source == "ccda"
    assert fp.family_name == "Smith"


# ---------------------------------------------------------------------------
# 3. score_providers — same NPI → decision="match" regardless of name
# ---------------------------------------------------------------------------


def test_score_providers_npi_match_decisive():
    """Same NPI always produces decision='match', even if names differ somewhat."""
    a = _make_fp(source="synthea", local_id="s1", npi="1234567890", family="Heathcote", given=("Lyman",))
    b = _make_fp(source="epic",    local_id="e1", npi="1234567890", family="Heathcote539", given=("Lyman173",))

    result = score_providers(a, b)
    assert result.npi_match is True
    assert result.decision == "match"


# ---------------------------------------------------------------------------
# 4. score_providers — different NPIs → "non-match" (different people)
# ---------------------------------------------------------------------------


def test_score_providers_different_npis_means_non_match():
    """Two practitioners with different NPIs are definitely different people."""
    a = _make_fp(source="source-a", npi="1234567890", family="Jones", given=("Alice",))
    b = _make_fp(source="source-b", npi="9876543210", family="Jones", given=("Alice",))

    result = score_providers(a, b)
    assert result.npi_match is False
    assert result.decision == "non-match"


# ---------------------------------------------------------------------------
# 5. score_providers — same name + overlapping specialty, no NPI → "match"
# ---------------------------------------------------------------------------


def test_score_providers_name_match_without_npi():
    """Same name (≥ NAME_THRESHOLD similarity) + overlapping specialty codes → 'match'."""
    a = _make_fp(
        source="source-a", npi=None,
        family="Johnson", given=("Robert",),
        specialty_codes=("207Q00000X", "207R00000X"),
    )
    b = _make_fp(
        source="source-b", npi=None,
        family="Johnson", given=("Robert",),
        specialty_codes=("207Q00000X",),
    )

    result = score_providers(a, b)
    assert result.npi_match is False
    assert result.name_similarity >= NAME_THRESHOLD, (
        f"Expected name_similarity ≥ {NAME_THRESHOLD}, got {result.name_similarity:.4f}"
    )
    assert result.specialty_overlap > 0
    assert result.decision == "match"


# ---------------------------------------------------------------------------
# 6. score_providers — partial name match → "possible-match"
# ---------------------------------------------------------------------------


def test_score_providers_partial_name_returns_possible_match():
    """Name similarity in [0.75, NAME_THRESHOLD) with no NPI → 'possible-match'."""
    # "Johnson Robert" vs "Johnston Bob" — moderate similarity, no NPI
    a = _make_fp(source="a", npi=None, family="Johnson", given=("Robert",), specialty_codes=())
    b = _make_fp(source="b", npi=None, family="Johnston", given=("Bob",), specialty_codes=())

    result = score_providers(a, b)
    assert result.npi_match is False
    # name similarity between these should be in [0.75, NAME_THRESHOLD)
    assert 0.75 <= result.name_similarity < NAME_THRESHOLD, (
        f"Expected name_similarity in [0.75, {NAME_THRESHOLD}), got {result.name_similarity:.4f}"
    )
    assert result.decision == "possible-match"


# ---------------------------------------------------------------------------
# 7. score_providers — low similarity → "non-match"
# ---------------------------------------------------------------------------


def test_score_providers_low_similarity_returns_non_match():
    """Completely different names, no NPI → 'non-match'."""
    a = _make_fp(source="a", npi=None, family="Abramowitz", given=("David",))
    b = _make_fp(source="b", npi=None, family="Nguyen", given=("Thi",))

    result = score_providers(a, b)
    assert result.npi_match is False
    assert result.decision == "non-match"
    assert result.name_similarity < 0.75


# ---------------------------------------------------------------------------
# 8. build_provider_identity_index — clusters by NPI
# ---------------------------------------------------------------------------


def test_build_provider_identity_index_clusters_by_npi():
    """Three Practitioners: 2 with NPI=A, 1 with NPI=B → 2 canonicals."""
    npi_a = "1111111111"
    npi_b = "2222222222"

    fp1 = _make_fp(source="synthea", local_id="s1", npi=npi_a, family="Heathcote")
    fp2 = _make_fp(source="epic",    local_id="e1", npi=npi_a, family="Heathcote539")
    fp3 = _make_fp(source="ccda",    local_id="c1", npi=npi_b, family="Valentin")

    index = build_provider_identity_index([fp1, fp2, fp3])

    assert len(index.canonical_providers) == 2, (
        f"Expected 2 canonical providers, got {len(index.canonical_providers)}"
    )

    # fp1 and fp2 should resolve to the same canonical
    id1 = index.resolve("synthea", "s1")
    id2 = index.resolve("epic", "e1")
    id3 = index.resolve("ccda", "c1")

    assert id1 is not None
    assert id2 is not None
    assert id3 is not None
    assert id1 == id2, "fp1 and fp2 share NPI → same canonical"
    assert id1 != id3, "fp1 and fp3 have different NPIs → different canonicals"


# ---------------------------------------------------------------------------
# 9. build_provider_identity_index — clusters by name fallback (no NPI)
# ---------------------------------------------------------------------------


def test_build_provider_identity_index_clusters_by_name_fallback():
    """Two Practitioners with no NPI but identical names + same specialty → 1 canonical."""
    fp1 = _make_fp(
        source="source-a", local_id="a1", npi=None,
        family="Park", given=("Soo",),
        specialty_codes=("207RE0101X",),
    )
    fp2 = _make_fp(
        source="source-b", local_id="b1", npi=None,
        family="Park", given=("Soo",),
        specialty_codes=("207RE0101X",),
    )

    index = build_provider_identity_index([fp1, fp2])

    assert len(index.canonical_providers) == 1, (
        f"Expected 1 canonical provider, got {len(index.canonical_providers)}"
    )
    id_a = index.resolve("source-a", "a1")
    id_b = index.resolve("source-b", "b1")
    assert id_a == id_b


# ---------------------------------------------------------------------------
# 10. merged_practitioner_resource — all source identifiers preserved
# ---------------------------------------------------------------------------


def test_merged_practitioner_resource_preserves_all_source_identifiers():
    """Merged Practitioner carries NPI + all source local identifiers."""
    fp1 = _make_fp(source="synthea", local_id="syn-001", npi="1111111111")
    fp2 = _make_fp(source="epic",    local_id="epi-999", npi="2222222222")

    cp = CanonicalProvider(
        canonical_id="smith-111",
        fingerprints=[fp1, fp2],
        fhir_resource={},
    )
    fhir = merged_practitioner_resource(cp)

    assert fhir["resourceType"] == "Practitioner"
    assert fhir["id"] == "smith-111"

    identifier_values = {ident["value"] for ident in fhir.get("identifier", [])}
    assert "1111111111" in identifier_values, f"NPI 1111111111 missing from {identifier_values}"
    assert "2222222222" in identifier_values, f"NPI 2222222222 missing from {identifier_values}"
    assert "syn-001" in identifier_values, f"Local ID syn-001 missing from {identifier_values}"
    assert "epi-999" in identifier_values, f"Local ID epi-999 missing from {identifier_values}"

    # us-core-practitioner profile
    profiles = fhir.get("meta", {}).get("profile", [])
    assert any("us-core-practitioner" in p for p in profiles)

    # lifecycle=harmonized tag
    tags = fhir.get("meta", {}).get("tag", [])
    lifecycle_codes = {t["code"] for t in tags if "lifecycle" in t.get("system", "")}
    assert "harmonized" in lifecycle_codes


# ---------------------------------------------------------------------------
# 11. canonical_id_for — explicit naming override
# ---------------------------------------------------------------------------


def test_canonical_id_for_explicit_naming():
    """Pass canonical_id_for={'local-1': 'dr-smith-001'} → canonical_id='dr-smith-001'."""
    fp = _make_fp(source="synthea", local_id="local-1", npi="1234567890", family="Smith")

    index = build_provider_identity_index(
        [fp],
        canonical_id_for={"local-1": "dr-smith-001"},
    )

    assert "dr-smith-001" in index.canonical_providers
    assert index.resolve("synthea", "local-1") == "dr-smith-001"


# ---------------------------------------------------------------------------
# 12. resolve — returns expected canonical_id
# ---------------------------------------------------------------------------


def test_resolve_returns_canonical_id():
    """index.resolve(source, local_id) returns the right canonical_id."""
    fp_a = _make_fp(source="source-a", local_id="a1", npi="1111111111")
    fp_b = _make_fp(source="source-b", local_id="b1", npi="2222222222")

    index = build_provider_identity_index([fp_a, fp_b])

    id_a = index.resolve("source-a", "a1")
    id_b = index.resolve("source-b", "b1")

    assert id_a is not None
    assert id_b is not None
    assert id_a != id_b
    # Non-existent lookup returns None
    assert index.resolve("unknown-source", "x99") is None


# ---------------------------------------------------------------------------
# Integration: fingerprint from real Synthea silver bundle Practitioners
# ---------------------------------------------------------------------------


def test_fingerprint_from_real_synthea_practitioner():
    """Integration: parse all 3 Practitioners from the real silver bundle."""
    with open(SILVER_BUNDLE) as f:
        bundle = json.load(f)

    practitioners = [
        e["resource"]
        for e in bundle.get("entry", [])
        if e.get("resource", {}).get("resourceType") == "Practitioner"
    ]
    assert len(practitioners) == 3, f"Expected 3 Practitioners, got {len(practitioners)}"

    fps = [
        fingerprint_from_practitioner_resource("synthea", p)
        for p in practitioners
    ]

    # All have NPIs (Synthea always includes NPI)
    for fp in fps:
        assert fp.npi is not None, f"Expected NPI for {fp.local_practitioner_id}"
        assert fp.family_name is not None

    # All 3 have different NPIs → 3 separate canonical providers
    index = build_provider_identity_index(fps)
    assert len(index.canonical_providers) == 3, (
        f"Expected 3 canonical providers (all distinct NPIs), "
        f"got {len(index.canonical_providers)}"
    )
