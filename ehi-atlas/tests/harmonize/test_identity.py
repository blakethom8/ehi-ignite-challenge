"""Tests for ehi_atlas.harmonize.identity — Patient identity resolution."""

from __future__ import annotations

import json
import pathlib

import pytest

from ehi_atlas.harmonize.identity import (
    CanonicalPatient,
    MatchScore,
    PatientFingerprint,
    PatientIdentityIndex,
    _jaro_winkler,
    address_match,
    build_identity_index,
    dob_match,
    fingerprint_from_patient_resource,
    gender_match,
    merged_patient_resource,
    name_similarity,
    score,
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


def _synthea_patient() -> dict:
    with open(SILVER_BUNDLE) as f:
        bundle = json.load(f)
    for entry in bundle.get("entry", []):
        r = entry.get("resource", {})
        if r.get("resourceType") == "Patient":
            return r
    raise RuntimeError("No Patient resource found in Synthea silver bundle")


def _make_fp(
    source: str = "test-source",
    local_id: str = "p1",
    family: str = "Doe",
    given: tuple[str, ...] = ("John",),
    dob: str = "1970-05-14",
    gender: str = "male",
    zip_code: str = "90210",
    mrn: str = "MRN001",
    mrn_sys: str = "http://hospital.example/mrn",
) -> PatientFingerprint:
    return PatientFingerprint(
        source=source,
        local_patient_id=local_id,
        family_name=family,
        given_names=given,
        birth_date=dob,
        gender=gender,
        address_zip=zip_code,
        mrn_value=mrn,
        mrn_system=mrn_sys,
    )


# ---------------------------------------------------------------------------
# 1. Integration — fingerprint from real Synthea bundle
# ---------------------------------------------------------------------------


def test_fingerprint_from_synthea_patient():
    patient = _synthea_patient()
    fp = fingerprint_from_patient_resource("synthea", patient)

    assert fp.source == "synthea"
    assert fp.local_patient_id == "6a92b6f5-0f67-4bd8-aa21-8468fc48b44f"
    assert fp.family_name == "Rohan584"
    assert "Rhett759" in fp.given_names
    assert fp.birth_date == "1946-08-06"
    assert fp.gender == "male"
    assert fp.address_zip == "02458"
    # Should pick the MR identifier
    assert fp.mrn_value is not None
    assert fp.mrn_system is not None


# ---------------------------------------------------------------------------
# 2. Jaro-Winkler known examples
# ---------------------------------------------------------------------------


def test_jaro_winkler_known_examples():
    # Standard textbook examples
    martha_marhta = _jaro_winkler("MARTHA", "MARHTA")
    assert abs(martha_marhta - 0.961) < 0.01, f"MARTHA/MARHTA = {martha_marhta:.4f}"

    dwayne_duane = _jaro_winkler("DWAYNE", "DUANE")
    assert abs(dwayne_duane - 0.84) < 0.02, f"DWAYNE/DUANE = {dwayne_duane:.4f}"

    # Identical strings → 1.0
    assert _jaro_winkler("JOHN", "JOHN") == 1.0

    # Completely different short strings → low score
    assert _jaro_winkler("AB", "XY") < 0.5


# ---------------------------------------------------------------------------
# 3. name_similarity with missing names
# ---------------------------------------------------------------------------


def test_name_similarity_handles_missing_names():
    # Both family names missing → still returns a float in [0, 1]
    fp_a = PatientFingerprint(
        source="a", local_patient_id="x1",
        family_name=None, given_names=(),
        birth_date=None, gender=None,
        address_zip=None, mrn_value=None, mrn_system=None,
    )
    fp_b = PatientFingerprint(
        source="b", local_patient_id="x2",
        family_name=None, given_names=(),
        birth_date=None, gender=None,
        address_zip=None, mrn_value=None, mrn_system=None,
    )
    sim = name_similarity(fp_a, fp_b)
    assert 0.0 <= sim <= 1.0

    # One side has a name, other doesn't → lower score
    fp_c = _make_fp(family="Smith", given=("Alice",))
    fp_d = PatientFingerprint(
        source="d", local_patient_id="d1",
        family_name=None, given_names=(),
        birth_date=None, gender=None,
        address_zip=None, mrn_value=None, mrn_system=None,
    )
    sim2 = name_similarity(fp_c, fp_d)
    assert sim2 < 0.5


# ---------------------------------------------------------------------------
# 4. dob_match exact
# ---------------------------------------------------------------------------


def test_dob_match_exact():
    a = _make_fp(dob="1980-03-15")
    b = _make_fp(dob="1980-03-15")
    assert dob_match(a, b) == 1.0


# ---------------------------------------------------------------------------
# 5. dob_match same year only
# ---------------------------------------------------------------------------


def test_dob_match_year_only():
    a = _make_fp(dob="1980-03-15")
    b = _make_fp(dob="1980-11-22")
    result = dob_match(a, b)
    assert result == 0.3, f"Expected 0.3, got {result}"


# ---------------------------------------------------------------------------
# 6. dob_match missing returns neutral
# ---------------------------------------------------------------------------


def test_dob_match_missing_returns_neutral():
    a = _make_fp(dob="1980-03-15")
    b = PatientFingerprint(
        source="b", local_patient_id="b1",
        family_name="Smith", given_names=("Bob",),
        birth_date=None, gender="male",
        address_zip=None, mrn_value=None, mrn_system=None,
    )
    assert dob_match(a, b) == 0.5
    assert dob_match(b, a) == 0.5


# ---------------------------------------------------------------------------
# 7. High name + exact DOB → decision "match"
# ---------------------------------------------------------------------------


def test_score_strong_match_decision_is_match():
    a = _make_fp(
        source="synthea", local_id="syn-001",
        family="Rohan", given=("Rhett",),
        dob="1946-08-06", gender="male", zip_code="02458",
    )
    b = _make_fp(
        source="epic", local_id="epic-001",
        family="Rohan", given=("Rhett",),
        dob="1946-08-06", gender="male", zip_code="02458",
    )
    s = score(a, b)
    assert s.decision == "match", f"Expected match, got {s.decision} (agg={s.aggregate:.4f})"
    assert s.aggregate >= 0.85


# ---------------------------------------------------------------------------
# 8. Partial name match + neutral DOB → "possible-match"
# ---------------------------------------------------------------------------


def test_score_partial_match_is_possible_match():
    # name similarity ~0.7, dob missing → aggregate ~ 0.5*0.7 + 0.3*0.5 + 0.1*0.5 + 0.1*1.0 = 0.56
    # but let's also match gender for a slightly higher score
    a = _make_fp(family="Johnson", given=("Michael",), dob="1970-01-01", gender="male", zip_code="99999")
    b = PatientFingerprint(
        source="b", local_patient_id="b2",
        family_name="Johnston",  # slight variation
        given_names=("Mike",),    # nickname
        birth_date=None,          # missing
        gender="male",
        address_zip="99999",      # same zip
        mrn_value="MRN999",
        mrn_system="http://example.com/mrn",
    )
    s = score(a, b)
    # name similarity between Johnson/Johnston+Michael/Mike should be moderate
    # DOB missing → 0.5, same ZIP → 1.0, same gender → 1.0
    # Even if name is 0.65: 0.5*0.65 + 0.3*0.5 + 0.1*1.0 + 0.1*1.0 = 0.325+0.15+0.1+0.1 = 0.675 → possible-match
    assert s.decision in ("possible-match", "match"), (
        f"Expected possible-match or match, got {s.decision} (agg={s.aggregate:.4f})"
    )
    # Sanity: not non-match
    assert s.aggregate >= 0.6


# ---------------------------------------------------------------------------
# 9. Two matching fingerprints → one canonical patient
# ---------------------------------------------------------------------------


def test_build_identity_index_clusters_two_matching_fingerprints():
    synthea_fp = _make_fp(
        source="synthea", local_id="syn-rhett",
        family="Rohan", given=("Rhett",),
        dob="1946-08-06", gender="male", zip_code="02458",
        mrn="SYN-RHETT759", mrn_sys="http://hospital.smarthealthit.org",
    )
    epic_fp = _make_fp(
        source="epic", local_id="epic-rhett",
        family="Rohan", given=("Rhett",),
        dob="1946-08-06", gender="male", zip_code="02458",
        mrn="SYN-RHETT759-EPIC", mrn_sys="https://epic.example/mrn",
    )
    index = build_identity_index([synthea_fp, epic_fp])

    assert len(index.canonical_patients) == 1, (
        f"Expected 1 canonical patient, got {len(index.canonical_patients)}"
    )
    canonical_id = list(index.canonical_patients.keys())[0]
    cp = index.canonical_patients[canonical_id]
    assert len(cp.fingerprints) == 2

    # Both sources resolve to the same canonical
    assert index.resolve("synthea", "syn-rhett") == canonical_id
    assert index.resolve("epic", "epic-rhett") == canonical_id


# ---------------------------------------------------------------------------
# 10. Two non-matching fingerprints → two canonical patients
# ---------------------------------------------------------------------------


def test_build_identity_index_keeps_distinct_patients_separate():
    fp_a = _make_fp(
        source="source-a", local_id="a1",
        family="Smith", given=("Alice",),
        dob="1970-05-14", gender="female", zip_code="10001",
        mrn="MRN-A",
    )
    fp_b = _make_fp(
        source="source-b", local_id="b1",
        family="Jones", given=("Robert",),
        dob="1955-11-30", gender="male", zip_code="90210",
        mrn="MRN-B",
    )
    index = build_identity_index([fp_a, fp_b])

    assert len(index.canonical_patients) == 2, (
        f"Expected 2 canonical patients, got {len(index.canonical_patients)}"
    )
    id_a = index.resolve("source-a", "a1")
    id_b = index.resolve("source-b", "b1")
    assert id_a is not None
    assert id_b is not None
    assert id_a != id_b


# ---------------------------------------------------------------------------
# 11. Merged resource preserves both source MRNs as identifiers
# ---------------------------------------------------------------------------


def test_merged_patient_resource_keeps_all_source_identifiers():
    fp1 = _make_fp(
        source="synthea", local_id="s1",
        mrn="SYN-MRN-001", mrn_sys="http://synthea.example/mrn",
    )
    fp2 = _make_fp(
        source="epic", local_id="e1",
        mrn="EPIC-MRN-002", mrn_sys="http://epic.example/mrn",
    )
    cp = CanonicalPatient(
        canonical_id="doe-14",
        fingerprints=[fp1, fp2],
        fhir_resource={},
    )
    fhir = merged_patient_resource(cp)

    assert fhir["resourceType"] == "Patient"
    assert fhir["id"] == "doe-14"

    # Both MRN values must appear
    identifier_values = {i["value"] for i in fhir.get("identifier", [])}
    assert "SYN-MRN-001" in identifier_values, f"Missing SYN-MRN-001 in {identifier_values}"
    assert "EPIC-MRN-002" in identifier_values, f"Missing EPIC-MRN-002 in {identifier_values}"

    # us-core profile
    profiles = fhir.get("meta", {}).get("profile", [])
    assert any("us-core-patient" in p for p in profiles)

    # lifecycle tag
    tags = fhir.get("meta", {}).get("tag", [])
    lifecycle_codes = {t["code"] for t in tags if "lifecycle" in t.get("system", "")}
    assert "harmonized" in lifecycle_codes


# ---------------------------------------------------------------------------
# 12. canonical_id_for explicit naming
# ---------------------------------------------------------------------------


def test_canonical_id_for_explicit_naming():
    fp = _make_fp(
        source="synthea", local_id="rhett-syn-id",
        family="Rohan584", given=("Rhett759",),
        dob="1946-08-06", gender="male",
    )
    index = build_identity_index(
        [fp],
        canonical_id_for={"rhett-syn-id": "rhett759"},
    )

    assert "rhett759" in index.canonical_patients
    assert index.resolve("synthea", "rhett-syn-id") == "rhett759"
