"""Tests for ehi_atlas.standardize.validators.BundleValidator.

All fixtures are built inline — no corpus files required.  Each fixture
targets a specific validation path so failures are easy to diagnose.
"""

from __future__ import annotations

import copy

import pytest

from ehi_atlas.standardize.validators import (
    EXTRACTION_CONFIDENCE_URL,
    EXTRACTION_MODEL_URL,
    SOURCE_ATTACHMENT_URL,
    BundleValidator,
    validate_bundle,
)

# ---------------------------------------------------------------------------
# Shared constants
# ---------------------------------------------------------------------------

_SOURCE_TAG_SYSTEM = "https://ehi-atlas.example/fhir/CodeSystem/source-tag"
_LIFECYCLE_SYSTEM = "https://ehi-atlas.example/fhir/CodeSystem/lifecycle"


# ---------------------------------------------------------------------------
# Minimal valid Bundle fixtures (inline helpers)
# ---------------------------------------------------------------------------


def _patient_entry(
    patient_id: str = "rhett759",
    *,
    profile: str = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
    source_tag_code: str = "synthea",
    lifecycle_code: str = "standardized",
    meta_extensions: list[dict] | None = None,
) -> dict:
    """Return a minimal Patient BundleEntry dict."""
    meta: dict = {
        "profile": [profile],
        "tag": [
            {"system": _SOURCE_TAG_SYSTEM, "code": source_tag_code},
            {"system": _LIFECYCLE_SYSTEM, "code": lifecycle_code},
        ],
    }
    if meta_extensions:
        meta["extension"] = meta_extensions
    return {
        "resource": {
            "resourceType": "Patient",
            "id": patient_id,
            "name": [{"family": "Rohan", "given": ["Rhett759"]}],
            "birthDate": "1966-01-01",
            "gender": "male",
            "meta": meta,
        }
    }


def _observation_entry(
    obs_id: str = "obs-creatinine",
    *,
    lifecycle_code: str = "standardized",
    meta_extensions: list[dict] | None = None,
    profile: str = "http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab",
) -> dict:
    """Return a minimal Observation BundleEntry dict."""
    meta: dict = {
        "profile": [profile],
        "tag": [
            {"system": _SOURCE_TAG_SYSTEM, "code": "lab-pdf"},
            {"system": _LIFECYCLE_SYSTEM, "code": lifecycle_code},
        ],
    }
    if meta_extensions:
        meta["extension"] = meta_extensions
    return {
        "resource": {
            "resourceType": "Observation",
            "id": obs_id,
            "status": "final",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": "2160-0",
                        "display": "Creatinine [Mass/volume] in Serum or Plasma",
                    }
                ]
            },
            "subject": {"reference": "Patient/rhett759"},
            "meta": meta,
        }
    }


def _valid_bundle(entries: list[dict] | None = None) -> dict:
    """Return a minimal structurally-valid Bundle with optional entries."""
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": entries or [_patient_entry()],
    }


def _extraction_extensions() -> list[dict]:
    """Return the three required extraction Extensions."""
    return [
        {
            "url": EXTRACTION_MODEL_URL,
            "valueCoding": {
                "system": "https://ehi-atlas.example/fhir/CodeSystem/llm-model",
                "code": "claude-opus-4-7",
            },
        },
        {"url": EXTRACTION_CONFIDENCE_URL, "valueDecimal": 0.97},
        {
            "url": SOURCE_ATTACHMENT_URL,
            "valueReference": {"reference": "Binary/quest-2025-09-12"},
        },
    ]


# ===========================================================================
# Tests
# ===========================================================================


class TestStructuralValidation:
    """Check 1: bundle must parse as valid FHIR R4."""

    def test_valid_empty_bundle_passes(self) -> None:
        bundle = {"resourceType": "Bundle", "type": "collection", "entry": []}
        errors = validate_bundle(bundle)
        assert errors == []

    def test_missing_type_field_raises_structural_error(self) -> None:
        """A Bundle missing the required ``type`` field must return a
        structural error and no further messages."""
        bundle = {"resourceType": "Bundle", "entry": []}
        errors = validate_bundle(bundle)
        assert len(errors) == 1
        assert errors[0].startswith("structural:")

    def test_structural_error_blocks_subsequent_checks(self) -> None:
        """When structural validation fails we return exactly one error and
        stop — no spurious profile/provenance messages."""
        bundle = {"resourceType": "Bundle"}  # missing type and entry
        errors = validate_bundle(bundle)
        # Only one error; no meta.tag or profile messages
        assert len(errors) == 1
        assert errors[0].startswith("structural:")

    def test_not_a_bundle_resource_type(self) -> None:
        """A dict whose resourceType is not Bundle must fail structurally."""
        not_bundle = {"resourceType": "Patient", "id": "p1", "gender": "male"}
        errors = validate_bundle(not_bundle)
        assert any(e.startswith("structural:") for e in errors)


class TestProfileValidation:
    """Check 2: declared profiles must be in KNOWN_PROFILES."""

    def test_known_profile_passes(self) -> None:
        bundle = _valid_bundle([_patient_entry()])
        errors = validate_bundle(bundle)
        assert errors == []

    def test_unknown_profile_warning_in_non_strict_mode(self) -> None:
        entry = _patient_entry(
            profile="http://example.com/fhir/StructureDefinition/custom-patient"
        )
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle, strict=False)
        # Exactly one warning; no hard errors
        assert len(errors) == 1
        assert errors[0].startswith("warning:")
        assert "unknown URL" in errors[0]

    def test_unknown_profile_error_in_strict_mode(self) -> None:
        entry = _patient_entry(
            profile="http://example.com/fhir/StructureDefinition/custom-patient"
        )
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle, strict=True)
        # In strict mode it must be a hard error (not a warning)
        assert len(errors) == 1
        assert not errors[0].startswith("warning:")
        assert "unknown URL" in errors[0]

    def test_multiple_profiles_one_unknown(self) -> None:
        """One known + one unknown profile → exactly one warning."""
        entry = copy.deepcopy(_patient_entry())
        entry["resource"]["meta"]["profile"] = [
            "http://hl7.org/fhir/us/core/StructureDefinition/us-core-patient",
            "http://unknown-vendor.example/SomeProfile",
        ]
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle, strict=False)
        assert len(errors) == 1
        assert errors[0].startswith("warning:")

    def test_all_known_profiles_are_accepted(self) -> None:
        """Smoke-test every URL in KNOWN_PROFILES: building the validator with
        each one should yield no profile errors."""
        validator = BundleValidator()
        for url in validator.KNOWN_PROFILES:
            entry = _patient_entry(profile=url)
            bundle = _valid_bundle([entry])
            msgs = validator.validate(bundle)
            profile_errors = [m for m in msgs if "unknown URL" in m]
            assert profile_errors == [], f"Profile flagged as unknown: {url}"


class TestProvenanceTagValidation:
    """Check 3a: required meta.tag systems must be present."""

    def test_both_required_tags_present_passes(self) -> None:
        bundle = _valid_bundle([_patient_entry()])
        errors = validate_bundle(bundle)
        assert errors == []

    def test_missing_source_tag_system(self) -> None:
        entry = copy.deepcopy(_patient_entry())
        # Remove source-tag, keep lifecycle
        entry["resource"]["meta"]["tag"] = [
            {"system": _LIFECYCLE_SYSTEM, "code": "standardized"}
        ]
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle)
        missing = [e for e in errors if _SOURCE_TAG_SYSTEM in e]
        assert len(missing) == 1
        assert "missing required system" in missing[0]

    def test_missing_lifecycle_system(self) -> None:
        entry = copy.deepcopy(_patient_entry())
        entry["resource"]["meta"]["tag"] = [
            {"system": _SOURCE_TAG_SYSTEM, "code": "synthea"}
        ]
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle)
        missing = [e for e in errors if _LIFECYCLE_SYSTEM in e]
        assert len(missing) == 1
        assert "missing required system" in missing[0]

    def test_both_tags_missing(self) -> None:
        entry = copy.deepcopy(_patient_entry())
        entry["resource"]["meta"]["tag"] = []
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle)
        missing = [e for e in errors if "missing required system" in e]
        assert len(missing) == 2

    def test_no_meta_at_all(self) -> None:
        entry = copy.deepcopy(_patient_entry())
        del entry["resource"]["meta"]
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle)
        # Both required tag systems should be flagged
        missing = [e for e in errors if "missing required system" in e]
        assert len(missing) == 2


class TestExtractionExtensionValidation:
    """Check 3b: lifecycle=extracted requires three specific Extensions."""

    def test_extracted_with_all_extensions_passes(self) -> None:
        entry = _observation_entry(
            lifecycle_code="extracted",
            meta_extensions=_extraction_extensions(),
        )
        bundle = _valid_bundle([entry])
        errors = [e for e in validate_bundle(bundle) if not e.startswith("warning:")]
        assert errors == []

    def test_extracted_missing_all_three_extensions(self) -> None:
        entry = _observation_entry(lifecycle_code="extracted")
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle)
        extraction_errors = [e for e in errors if "lifecycle=extracted" in e]
        # All three missing
        assert len(extraction_errors) == 3

    def test_extracted_missing_confidence_only(self) -> None:
        exts = [e for e in _extraction_extensions() if e["url"] != EXTRACTION_CONFIDENCE_URL]
        entry = _observation_entry(lifecycle_code="extracted", meta_extensions=exts)
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle)
        extraction_errors = [e for e in errors if "lifecycle=extracted" in e]
        assert len(extraction_errors) == 1
        assert "extraction-confidence" in extraction_errors[0]

    def test_extracted_missing_model_only(self) -> None:
        exts = [e for e in _extraction_extensions() if e["url"] != EXTRACTION_MODEL_URL]
        entry = _observation_entry(lifecycle_code="extracted", meta_extensions=exts)
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle)
        extraction_errors = [e for e in errors if "lifecycle=extracted" in e]
        assert len(extraction_errors) == 1
        assert "extraction-model" in extraction_errors[0]

    def test_extracted_missing_attachment_only(self) -> None:
        exts = [e for e in _extraction_extensions() if e["url"] != SOURCE_ATTACHMENT_URL]
        entry = _observation_entry(lifecycle_code="extracted", meta_extensions=exts)
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle)
        extraction_errors = [e for e in errors if "lifecycle=extracted" in e]
        assert len(extraction_errors) == 1
        assert "source-attachment" in extraction_errors[0]

    def test_non_extracted_lifecycle_skips_extension_check(self) -> None:
        """A resource with lifecycle=standardized (not extracted) must NOT
        be flagged for missing extraction Extensions."""
        entry = _observation_entry(lifecycle_code="standardized")
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle)
        extraction_errors = [e for e in errors if "lifecycle=extracted" in e]
        assert extraction_errors == []


class TestMultiResourceBundle:
    """Mixed bundles with multiple resource types."""

    def test_valid_multi_resource_bundle(self) -> None:
        patient = _patient_entry()
        obs = _observation_entry(
            lifecycle_code="extracted",
            meta_extensions=_extraction_extensions(),
        )
        bundle = _valid_bundle([patient, obs])
        errors = [e for e in validate_bundle(bundle) if not e.startswith("warning:")]
        assert errors == []

    def test_errors_report_correct_resource_label(self) -> None:
        """Error messages must name the offending resource."""
        entry = _observation_entry(obs_id="obs-abc", lifecycle_code="extracted")
        bundle = _valid_bundle([entry])
        errors = validate_bundle(bundle)
        # Every extraction-related error should mention the resource ID
        for e in errors:
            if "lifecycle=extracted" in e:
                assert "obs-abc" in e, f"Expected resource ID in: {e}"

    def test_entry_without_resource_is_skipped(self) -> None:
        """A link-only BundleEntry (no resource key) must not cause errors."""
        link_entry = {"link": [{"relation": "self", "url": "http://example.com"}]}
        patient = _patient_entry()
        bundle = {"resourceType": "Bundle", "type": "collection", "entry": [link_entry, patient]}
        errors = validate_bundle(bundle)
        assert errors == []


class TestBundleValidatorInit:
    """BundleValidator constructor and convenience wrapper."""

    def test_default_strict_is_false(self) -> None:
        v = BundleValidator()
        assert v.strict is False

    def test_strict_true(self) -> None:
        v = BundleValidator(strict=True)
        assert v.strict is True

    def test_validate_bundle_convenience(self) -> None:
        bundle = _valid_bundle()
        assert validate_bundle(bundle) == []

    def test_validate_bundle_strict_param(self) -> None:
        entry = _patient_entry(profile="http://unknown.example/profile")
        bundle = _valid_bundle([entry])
        warnings = validate_bundle(bundle, strict=False)
        errors = validate_bundle(bundle, strict=True)
        assert all(w.startswith("warning:") for w in warnings)
        assert all(not e.startswith("warning:") for e in errors)
