"""Tests for ehi_atlas.harmonize.quality — deterministic quality scoring."""

from __future__ import annotations

import pytest
from datetime import date

from ehi_atlas.harmonize.quality import (
    REFERENCE_DATE,
    recency_score,
    authority_score,
    completeness_score,
    quality_score,
    quality_components,
    annotate_quality,
)
from ehi_atlas.harmonize.provenance import EXT_QUALITY_SCORE, SYS_SOURCE_TAG


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _obs(effective_date: str | None = None, source_tag: str | None = None, **extra_fields) -> dict:
    """Build a minimal Observation dict."""
    resource: dict = {"resourceType": "Observation"}
    if effective_date is not None:
        resource["effectiveDateTime"] = effective_date
    if source_tag is not None:
        resource.setdefault("meta", {})["tag"] = [
            {"system": SYS_SOURCE_TAG, "code": source_tag}
        ]
    resource.update(extra_fields)
    return resource


def _full_obs(effective_date: str, source_tag: str) -> dict:
    """Observation with all 4 COMPLETENESS_FIELDS present."""
    return {
        "resourceType": "Observation",
        "effectiveDateTime": effective_date,
        "code": {"coding": [{"code": "1234"}]},
        "subject": {"reference": "Patient/p1"},
        "valueQuantity": {"value": 98.6, "unit": "F"},
        "meta": {
            "tag": [{"system": SYS_SOURCE_TAG, "code": source_tag}]
        },
    }


# ---------------------------------------------------------------------------
# Recency score tests
# ---------------------------------------------------------------------------

def test_recency_score_within_one_year():
    """Clinical date 2026-01-01 is within 1y of ref 2026-04-29 -> 1.0."""
    resource = _obs("2026-01-01")
    assert recency_score(resource) == 1.0


def test_recency_score_one_to_three_years():
    """Clinical date 2024-04-29 is exactly 1y from ref -> 0.8 bracket."""
    resource = _obs("2024-04-29")
    # 2 years before ref -> 1-3y bracket -> 0.8
    score = recency_score(resource)
    assert score == 0.8


def test_recency_score_three_to_five_years():
    """Clinical date 2022-04-29 is ~4y before ref -> 0.5 bracket."""
    resource = _obs("2022-04-29")
    score = recency_score(resource)
    assert score == 0.5


def test_recency_score_five_plus_years():
    """Clinical date 2018-01-01 is >5y before ref -> 0.3."""
    resource = _obs("2018-01-01")
    score = recency_score(resource)
    assert score == 0.3


def test_recency_score_no_clinical_time_returns_neutral():
    """No effectiveDateTime on an Observation -> neutral score 0.5."""
    resource = {"resourceType": "Observation"}
    assert recency_score(resource) == 0.5


# ---------------------------------------------------------------------------
# Authority score tests
# ---------------------------------------------------------------------------

def test_authority_score_synthea():
    """source-tag=synthea -> 0.85."""
    resource = _obs(source_tag="synthea")
    assert authority_score(resource) == 0.85


def test_authority_score_lab_pdf():
    """source-tag=lab-pdf -> 0.65."""
    resource = _obs(source_tag="lab-pdf")
    assert authority_score(resource) == 0.65


def test_authority_score_unknown_source_falls_back_to_default():
    """source-tag with unrecognised code -> _default -> 0.5."""
    resource = {
        "resourceType": "Observation",
        "meta": {"tag": [{"system": SYS_SOURCE_TAG, "code": "totally-unknown-vendor"}]},
    }
    assert authority_score(resource) == 0.5


def test_authority_score_no_tag_falls_back_to_default():
    """No meta.tag at all -> _default -> 0.5."""
    resource = {"resourceType": "Observation"}
    assert authority_score(resource) == 0.5


# ---------------------------------------------------------------------------
# Completeness score tests
# ---------------------------------------------------------------------------

def test_completeness_score_observation_full():
    """Observation with all 4 expected fields (code, subject, valueQuantity,
    effectiveDateTime) -> 1.0."""
    resource = {
        "resourceType": "Observation",
        "code": {"coding": [{"code": "1234"}]},
        "subject": {"reference": "Patient/p1"},
        "valueQuantity": {"value": 98.6, "unit": "F"},
        "effectiveDateTime": "2025-09-12",
    }
    assert completeness_score(resource) == 1.0


def test_completeness_score_observation_partial():
    """Observation with 2 of 4 expected fields -> 0.5."""
    resource = {
        "resourceType": "Observation",
        "code": {"coding": [{"code": "1234"}]},
        "subject": {"reference": "Patient/p1"},
        # valueQuantity and effectiveDateTime absent
    }
    assert completeness_score(resource) == 0.5


def test_completeness_score_unknown_resource_type():
    """Unknown resource type -> neutral floor 0.5."""
    resource = {"resourceType": "SomeFantasyResource", "field": "value"}
    assert completeness_score(resource) == 0.5


# ---------------------------------------------------------------------------
# Aggregate quality_score tests
# ---------------------------------------------------------------------------

def test_quality_score_high_authority_recent_complete():
    """synthea Observation, 2025-09-12 (within 1y), all fields present.

    Expected: 0.40*1.0 + 0.40*0.85 + 0.20*1.0 = 0.40 + 0.34 + 0.20 = 0.94
    """
    resource = _full_obs("2025-09-12", "synthea")
    score = quality_score(resource)
    assert abs(score - 0.94) < 1e-9


def test_quality_score_low_quality_extracted():
    """lab-pdf Observation, 2018-01-01 (>5y), 2 of 4 fields.

    Expected: 0.40*0.3 + 0.40*0.65 + 0.20*0.5 = 0.12 + 0.26 + 0.10 = 0.48
    """
    resource = {
        "resourceType": "Observation",
        "effectiveDateTime": "2018-01-01",
        "code": {"coding": [{"code": "1234"}]},
        "subject": {"reference": "Patient/p1"},
        # valueQuantity absent; effectiveDateTime present
        "meta": {"tag": [{"system": SYS_SOURCE_TAG, "code": "lab-pdf"}]},
    }
    # effectiveDateTime is counted as a completeness field -> 3/4 present
    # Re-check: code, subject, effectiveDateTime present; valueQuantity absent -> 3/4 = 0.75
    # Use a resource that has exactly 2/4 fields present:
    resource2 = {
        "resourceType": "Observation",
        "effectiveDateTime": "2018-01-01",
        "code": {"coding": [{"code": "1234"}]},
        # subject and valueQuantity absent
        "meta": {"tag": [{"system": SYS_SOURCE_TAG, "code": "lab-pdf"}]},
    }
    # completeness: code + effectiveDateTime = 2/4 = 0.5
    # recency: 2018-01-01 -> >5y -> 0.3
    # authority: lab-pdf -> 0.65
    # aggregate: 0.40*0.3 + 0.40*0.65 + 0.20*0.5 = 0.12 + 0.26 + 0.10 = 0.48
    score = quality_score(resource2)
    assert abs(score - 0.48) < 1e-9


def test_quality_score_clamped_to_zero_one():
    """quality_score always returns a value in [0, 1]."""
    # Pathological inputs: resource with no fields
    for res in [
        {},
        {"resourceType": "Observation"},
        {"resourceType": "Unknown"},
    ]:
        s = quality_score(res)
        assert 0.0 <= s <= 1.0, f"score {s} out of bounds for {res}"


# ---------------------------------------------------------------------------
# annotate_quality tests
# ---------------------------------------------------------------------------

def test_annotate_quality_attaches_extension():
    """annotate_quality should add EXT_QUALITY_SCORE to resource.meta.extension."""
    resource = _full_obs("2025-09-12", "synthea")
    result = annotate_quality(resource)

    # The resource is mutated and returned
    assert result is resource

    extensions = resource.get("meta", {}).get("extension", [])
    quality_exts = [e for e in extensions if e.get("url") == EXT_QUALITY_SCORE]
    assert len(quality_exts) == 1
    score = quality_exts[0]["valueDecimal"]
    assert isinstance(score, float)
    assert 0.0 <= score <= 1.0


def test_annotate_quality_is_idempotent():
    """Running annotate_quality twice does not duplicate the extension."""
    resource = _full_obs("2025-09-12", "synthea")
    annotate_quality(resource)
    annotate_quality(resource)

    extensions = resource.get("meta", {}).get("extension", [])
    quality_exts = [e for e in extensions if e.get("url") == EXT_QUALITY_SCORE]
    assert len(quality_exts) == 1
