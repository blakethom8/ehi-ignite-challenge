"""Tests for the Synthea Layer-2 standardizer.

All tests run against the real bronze rhett759 record at:
    corpus/bronze/synthea/rhett759/data.json

This is the authoritative smoke test that proves the bronze → silver pipeline
works end-to-end on the simplest possible source.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ehi_atlas.standardize.synthea import SyntheaStandardizer
from ehi_atlas.standardize.validators import BundleValidator

# ---------------------------------------------------------------------------
# Fixture paths
# ---------------------------------------------------------------------------

_REPO_ROOT = Path(__file__).resolve().parents[2]
_BRONZE_ROOT = _REPO_ROOT / "corpus" / "bronze" / "synthea"
_SILVER_ROOT = _REPO_ROOT / "corpus" / "silver" / "synthea"
_PATIENT_ID = "rhett759"
_BRONZE_BUNDLE = _BRONZE_ROOT / _PATIENT_ID / "data.json"

# Skip all tests when the bronze record is absent (shouldn't happen in normal
# development; use `make corpus` to reproduce if needed).
pytestmark = pytest.mark.skipif(
    not _BRONZE_BUNDLE.exists(),
    reason=(
        f"Bronze bundle not found at {_BRONZE_BUNDLE}. "
        "Run `make corpus` or `uv run ehi-atlas ingest --source synthea` first."
    ),
)


# ---------------------------------------------------------------------------
# Shared fixture: run standardize once per test session for speed
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module")
def standardizer() -> SyntheaStandardizer:
    return SyntheaStandardizer(bronze_root=_BRONZE_ROOT, silver_root=_SILVER_ROOT)


@pytest.fixture(scope="module")
def silver_result(standardizer):
    """Run standardize once and cache the result for this module."""
    return standardizer.standardize(_PATIENT_ID)


@pytest.fixture(scope="module")
def silver_bundle(silver_result) -> dict:
    return json.loads(Path(silver_result.silver_path).read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def silver_resources(silver_bundle) -> list[dict]:
    return [
        entry["resource"]
        for entry in silver_bundle.get("entry", [])
        if isinstance(entry.get("resource"), dict)
    ]


# ---------------------------------------------------------------------------
# Test 1: silver bundle.json is written to the expected path
# ---------------------------------------------------------------------------

def test_standardize_writes_silver_bundle(silver_result):
    """standardize() produces corpus/silver/synthea/rhett759/bundle.json."""
    silver_path = Path(silver_result.silver_path)
    assert silver_path.exists(), f"Expected silver bundle at {silver_path}"
    assert silver_path.name == "bundle.json"
    assert "silver" in str(silver_path)
    assert "synthea" in str(silver_path)
    assert _PATIENT_ID in str(silver_path)

    # Must be valid JSON and a FHIR Bundle
    data = json.loads(silver_path.read_text(encoding="utf-8"))
    assert data.get("resourceType") == "Bundle"
    assert len(data.get("entry", [])) > 0


# ---------------------------------------------------------------------------
# Test 2: source-tag added to every resource
# ---------------------------------------------------------------------------

def test_standardize_adds_source_tag_to_every_resource(silver_resources):
    """Every resource in the silver bundle has the synthea source-tag."""
    SOURCE_TAG_SYSTEM = SyntheaStandardizer.SOURCE_TAG_SYSTEM
    missing: list[str] = []
    for resource in silver_resources:
        tags = resource.get("meta", {}).get("tag", [])
        systems = {t.get("system") for t in tags}
        if SOURCE_TAG_SYSTEM not in systems:
            missing.append(resource.get("resourceType", "Unknown"))
    assert not missing, (
        f"Resources missing source-tag ({SOURCE_TAG_SYSTEM}): {missing}"
    )


# ---------------------------------------------------------------------------
# Test 3: lifecycle=standardized added to every resource
# ---------------------------------------------------------------------------

def test_standardize_adds_lifecycle_tag_to_every_resource(silver_resources):
    """Every resource has lifecycle=standardized in meta.tag."""
    LIFECYCLE_SYSTEM = SyntheaStandardizer.LIFECYCLE_SYSTEM
    missing: list[str] = []
    for resource in silver_resources:
        tags = resource.get("meta", {}).get("tag", [])
        lifecycle_codes = [
            t.get("code")
            for t in tags
            if t.get("system") == LIFECYCLE_SYSTEM
        ]
        if "standardized" not in lifecycle_codes:
            missing.append(resource.get("resourceType", "Unknown"))
    assert not missing, (
        f"Resources missing lifecycle=standardized: {missing}"
    )


# ---------------------------------------------------------------------------
# Test 4: USCDI profiles added to known resource types
# ---------------------------------------------------------------------------

def test_standardize_adds_uscdi_profiles_to_known_resource_types(silver_resources):
    """Patient has us-core-patient; Condition has us-core-condition in meta.profile."""
    PROFILE_MAP = SyntheaStandardizer.PROFILE_MAP

    # Spot-check the two most important types
    for resource_type, expected_profile in [
        ("Patient", PROFILE_MAP["Patient"]),
        ("Condition", PROFILE_MAP["Condition"]),
    ]:
        typed_resources = [r for r in silver_resources if r.get("resourceType") == resource_type]
        assert typed_resources, f"No {resource_type} resources found in silver bundle"
        for resource in typed_resources:
            profiles = resource.get("meta", {}).get("profile", [])
            assert expected_profile in profiles, (
                f"{resource_type}/{resource.get('id')} missing profile {expected_profile!r}; "
                f"has: {profiles}"
            )


# ---------------------------------------------------------------------------
# Test 5: idempotency — two runs produce byte-identical output
# ---------------------------------------------------------------------------

def test_standardize_is_idempotent(standardizer):
    """Running standardize twice produces byte-identical silver bundle.json."""
    result1 = standardizer.standardize(_PATIENT_ID)
    result2 = standardizer.standardize(_PATIENT_ID)

    # SHA256 hashes must match
    assert result1.sha256 == result2.sha256, (
        f"Idempotency failure: first run sha256={result1.sha256}, "
        f"second run sha256={result2.sha256}"
    )

    # Byte-level content must also match
    content1 = Path(result1.silver_path).read_text(encoding="utf-8")
    content2 = Path(result2.silver_path).read_text(encoding="utf-8")
    assert content1 == content2, "Silver bundle content differs between runs"


# ---------------------------------------------------------------------------
# Test 6: BundleValidator returns no provenance/profile errors on silver bundle
# ---------------------------------------------------------------------------

def test_standardize_passes_validator(silver_bundle, silver_result):
    """BundleValidator on the silver bundle returns no provenance or profile errors.

    Note on the structural check: fhir.resources 8.x (Pydantic v2 strict mode)
    rejects certain valid FHIR R4 fields that Synthea emits (e.g. Encounter.class
    as a single Coding rather than a list, Procedure.reasonReference, etc.).
    This is a known compatibility gap between fhir.resources strict schema and
    real-world Synthea output.  The structural error is expected and is out of
    scope for our Layer-2 work — we verify that our provenance annotations do not
    introduce *additional* errors beyond the structural compat issue.

    What we assert:
      - Any errors are ONLY "structural:" ones from fhir.resources compat.
      - There are NO meta.tag / meta.profile errors (i.e. our annotations work).
    """
    messages = BundleValidator(strict=False).validate(silver_bundle)

    # Separate structural compat errors from provenance/profile errors
    structural_errors = [m for m in messages if m.startswith("structural:")]
    provenance_errors = [
        m for m in messages
        if not m.startswith("warning:") and not m.startswith("structural:")
    ]
    profile_warnings = [m for m in messages if m.startswith("warning:")]

    # Our annotations must produce zero provenance/tag errors
    assert not provenance_errors, (
        f"Silver bundle has provenance/tag errors (our fault):\n"
        + "\n".join(f"  {e}" for e in provenance_errors)
    )

    # If there's a structural error it must be the known fhir.resources compat issue
    for err in structural_errors:
        assert "validation errors for Bundle" in err or "fhir" in err.lower(), (
            f"Unexpected structural error (not the known fhir.resources compat issue): {err}"
        )

    # Profile warnings are acceptable (non-fatal) — just document them
    # (Synthea includes resource types not in PROFILE_MAP → no profile → no warning,
    #  but resource types we don't map like ImagingStudy won't get a profile URL
    #  so no unknown-profile warning either.  Zero profile warnings expected.)
    assert not profile_warnings, (
        f"Unexpected profile warnings on silver bundle:\n"
        + "\n".join(f"  {w}" for w in profile_warnings)
    )

    # The result's own errors list mirrors the validator's non-warning messages
    # (may include structural compat error — that's expected for real Synthea data)
    # The key invariant: no provenance errors in the result either.
    result_provenance_errors = [
        e for e in silver_result.validation_errors
        if not e.startswith("structural:")
    ]
    assert not result_provenance_errors, (
        "StandardizeResult.validation_errors has unexpected non-structural errors; "
        f"got: {result_provenance_errors}"
    )
