"""Tests for ehi_atlas.harmonize.observation — Observation deduplication.

Coverage:
  1.  test_normalize_unit_lowercase
  2.  test_extract_observation_key_for_creatinine
  3.  test_extract_observation_key_no_loinc_returns_none_loinc
  4.  test_observations_equivalent_exact_match
  5.  test_observations_equivalent_value_within_tolerance
  6.  test_observations_equivalent_value_outside_tolerance
  7.  test_observations_equivalent_different_units_returns_false
  8.  test_observations_near_match_finds_value_difference
  9.  test_observations_near_match_returns_false_on_exact_match
  10. test_merge_observations_combines_two_creatinines
  11. test_merge_observations_uses_max_quality_score
  12. test_merge_observations_attaches_merge_rationale
  13. test_dedup_observations_empty_list
  14. test_dedup_observations_passthrough_when_no_dups
  15. test_dedup_observations_merges_artifact_5_creatinine
"""

from __future__ import annotations

import pytest

from ehi_atlas.harmonize.observation import (
    ObservationKey,
    ObservationMergeResult,
    dedup_observations,
    extract_observation_key,
    merge_observations,
    normalize_unit,
    observations_equivalent,
    observations_near_match,
)
from ehi_atlas.harmonize.provenance import (
    EXT_MERGE_RATIONALE,
    EXT_QUALITY_SCORE,
    SYS_LIFECYCLE,
    SYS_SOURCE_TAG,
)


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

LOINC_CREATININE = "2160-0"
LOINC_SYSTEM = "http://loinc.org"
SNOMED_SYSTEM = "http://snomed.info/sct"


def _creatinine_obs(
    obs_id: str,
    value: float = 1.4,
    unit: str = "mg/dL",
    date: str = "2025-09-12",
    source_tag: str | None = None,
    quality_score: float | None = None,
) -> dict:
    """Build a minimal FHIR R4 Observation for creatinine."""
    obs: dict = {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": LOINC_SYSTEM,
                    "code": LOINC_CREATININE,
                    "display": "Creatinine [Mass/volume] in Serum or Plasma",
                }
            ]
        },
        "effectiveDateTime": date,
        "valueQuantity": {
            "value": value,
            "unit": unit,
            "code": unit,
        },
        "meta": {
            "tag": [],
            "extension": [],
        },
    }
    if source_tag is not None:
        obs["meta"]["tag"].append({"system": SYS_SOURCE_TAG, "code": source_tag})
    if quality_score is not None:
        obs["meta"]["extension"].append(
            {"url": EXT_QUALITY_SCORE, "valueDecimal": quality_score}
        )
    return obs


def _snomed_only_obs(obs_id: str, date: str = "2025-09-12") -> dict:
    """Observation with SNOMED code only — no LOINC."""
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": SNOMED_SYSTEM,
                    "code": "271510001",
                    "display": "Renal impairment",
                }
            ]
        },
        "effectiveDateTime": date,
        "valueQuantity": {"value": 2.0, "unit": "mg/dL", "code": "mg/dL"},
    }


def _sodium_obs(obs_id: str, date: str = "2025-09-12") -> dict:
    """Observation for sodium (LOINC 2951-2) — distinct from creatinine."""
    return {
        "resourceType": "Observation",
        "id": obs_id,
        "status": "final",
        "code": {
            "coding": [
                {
                    "system": LOINC_SYSTEM,
                    "code": "2951-2",
                    "display": "Sodium [Moles/volume] in Serum or Plasma",
                }
            ]
        },
        "effectiveDateTime": date,
        "valueQuantity": {"value": 140.0, "unit": "mmol/L", "code": "mmol/L"},
    }


# ---------------------------------------------------------------------------
# 1. normalize_unit
# ---------------------------------------------------------------------------


def test_normalize_unit_lowercase():
    """'MG/DL' should normalize to 'mg/dl'."""
    assert normalize_unit("MG/DL") == "mg/dl"


def test_normalize_unit_strips_whitespace():
    assert normalize_unit("  mg/dL  ") == "mg/dl"


def test_normalize_unit_none_passthrough():
    assert normalize_unit(None) is None


# ---------------------------------------------------------------------------
# 2. extract_observation_key — creatinine
# ---------------------------------------------------------------------------


def test_extract_observation_key_for_creatinine():
    """Key for a standard creatinine Observation: LOINC 2160-0, 2025-09-12, 1.4, mg/dl."""
    obs = _creatinine_obs("synthea-creat-001")
    key = extract_observation_key(obs)
    assert key.loinc_code == LOINC_CREATININE
    assert key.clinical_date == "2025-09-12"
    assert key.value == pytest.approx(1.4)
    assert key.unit == "mg/dl"  # normalized


# ---------------------------------------------------------------------------
# 3. extract_observation_key — SNOMED-only → loinc_code=None
# ---------------------------------------------------------------------------


def test_extract_observation_key_no_loinc_returns_none_loinc():
    """An Observation coded only with SNOMED yields loinc_code=None."""
    obs = _snomed_only_obs("snomed-obs-001")
    key = extract_observation_key(obs)
    assert key.loinc_code is None


# ---------------------------------------------------------------------------
# 4. observations_equivalent — exact match
# ---------------------------------------------------------------------------


def test_observations_equivalent_exact_match():
    """Two creatinine Observations on the same date with the same value/unit are equivalent."""
    a = _creatinine_obs("obs-a", value=1.4, unit="mg/dL", date="2025-09-12")
    b = _creatinine_obs("obs-b", value=1.4, unit="mg/dL", date="2025-09-12")
    assert observations_equivalent(a, b) is True


# ---------------------------------------------------------------------------
# 5. observations_equivalent — value within tolerance
# ---------------------------------------------------------------------------


def test_observations_equivalent_value_within_tolerance():
    """1.4 vs 1.4001 is within VALUE_TOLERANCE (0.001) and should be equivalent."""
    a = _creatinine_obs("obs-a", value=1.4)
    b = _creatinine_obs("obs-b", value=1.4001)
    assert observations_equivalent(a, b) is True


# ---------------------------------------------------------------------------
# 6. observations_equivalent — value outside tolerance
# ---------------------------------------------------------------------------


def test_observations_equivalent_value_outside_tolerance():
    """1.4 vs 1.5 exceeds VALUE_TOLERANCE and must NOT be equivalent."""
    a = _creatinine_obs("obs-a", value=1.4)
    b = _creatinine_obs("obs-b", value=1.5)
    assert observations_equivalent(a, b) is False


# ---------------------------------------------------------------------------
# 7. observations_equivalent — different units → False (Phase 1 no UCUM conversion)
# ---------------------------------------------------------------------------


def test_observations_equivalent_different_units_returns_false():
    """1.4 mg/dl vs 1.4 mmol/l — different unit strings → not equivalent (no UCUM in Phase 1)."""
    a = _creatinine_obs("obs-a", value=1.4, unit="mg/dL")
    b = _creatinine_obs("obs-b", value=1.4, unit="mmol/L")
    assert observations_equivalent(a, b) is False


# ---------------------------------------------------------------------------
# 8. observations_near_match — value difference on same LOINC + date
# ---------------------------------------------------------------------------


def test_observations_near_match_finds_value_difference():
    """Same LOINC + date, different value → near-match (conflict candidate for 3.8)."""
    a = _creatinine_obs("obs-a", value=1.4, date="2025-09-12")
    b = _creatinine_obs("obs-b", value=1.8, date="2025-09-12")
    assert observations_near_match(a, b) is True


# ---------------------------------------------------------------------------
# 9. observations_near_match — exact match is NOT a near-match
# ---------------------------------------------------------------------------


def test_observations_near_match_returns_false_on_exact_match():
    """Exact equivalents should NOT trigger near-match; use observations_equivalent for that."""
    a = _creatinine_obs("obs-a", value=1.4)
    b = _creatinine_obs("obs-b", value=1.4)
    assert observations_near_match(a, b) is False


# ---------------------------------------------------------------------------
# 10. merge_observations — combines two creatinine Observations
# ---------------------------------------------------------------------------


def test_merge_observations_combines_two_creatinines():
    """Merging a Synthea + lab-PDF creatinine Observation preserves both source-tags
    and both identifier entries in the merged resource."""
    synthea_obs = _creatinine_obs(
        "synthea-creat-001", source_tag="synthea", quality_score=0.75
    )
    pdf_obs = _creatinine_obs(
        "lab-pdf-creat-001", source_tag="lab-pdf", quality_score=0.94
    )

    result = merge_observations([synthea_obs, pdf_obs], canonical_id="merged-creat-0")

    merged = result.merged
    assert merged["id"] == "merged-creat-0"
    assert merged["resourceType"] == "Observation"

    # Both source tags present
    tags = merged["meta"]["tag"]
    source_codes = {t["code"] for t in tags if t.get("system") == SYS_SOURCE_TAG}
    assert "synthea" in source_codes
    assert "lab-pdf" in source_codes

    # lifecycle=harmonized tag present
    lifecycle_codes = {t["code"] for t in tags if t.get("system") == SYS_LIFECYCLE}
    assert "harmonized" in lifecycle_codes

    # Both identifiers preserved
    identifiers = merged.get("identifier", [])
    id_values = {ident.get("value") for ident in identifiers}
    assert "synthea-creat-001" in id_values
    assert "lab-pdf-creat-001" in id_values

    # Sources list in result
    assert "Observation/synthea-creat-001" in result.sources
    assert "Observation/lab-pdf-creat-001" in result.sources


# ---------------------------------------------------------------------------
# 11. merge_observations — uses max quality score
# ---------------------------------------------------------------------------


def test_merge_observations_uses_max_quality_score():
    """When input qualities are 0.7 and 0.94, merged resource should have score 0.94."""
    a = _creatinine_obs("obs-a", quality_score=0.7)
    b = _creatinine_obs("obs-b", quality_score=0.94)

    result = merge_observations([a, b], canonical_id="merged-q")
    merged = result.merged

    # EXT_QUALITY_SCORE in meta.extension
    quality_exts = [
        ext
        for ext in merged.get("meta", {}).get("extension", [])
        if isinstance(ext, dict) and ext.get("url") == EXT_QUALITY_SCORE
    ]
    assert len(quality_exts) == 1
    assert quality_exts[0]["valueDecimal"] == pytest.approx(0.94)


# ---------------------------------------------------------------------------
# 12. merge_observations — attaches merge rationale
# ---------------------------------------------------------------------------


def test_merge_observations_attaches_merge_rationale():
    """Merged resource must carry EXT_MERGE_RATIONALE in top-level extension."""
    a = _creatinine_obs("obs-a")
    b = _creatinine_obs("obs-b")

    result = merge_observations([a, b], canonical_id="merged-r")
    merged = result.merged

    rationale_exts = [
        ext
        for ext in merged.get("extension", [])
        if isinstance(ext, dict) and ext.get("url") == EXT_MERGE_RATIONALE
    ]
    assert len(rationale_exts) == 1
    assert isinstance(rationale_exts[0].get("valueString"), str)
    assert len(rationale_exts[0]["valueString"]) > 0


# ---------------------------------------------------------------------------
# 13. dedup_observations — empty list
# ---------------------------------------------------------------------------


def test_dedup_observations_empty_list():
    """Empty input yields empty output with no merges."""
    result_obs, merges = dedup_observations([])
    assert result_obs == []
    assert merges == []


# ---------------------------------------------------------------------------
# 14. dedup_observations — passthrough when no dups
# ---------------------------------------------------------------------------


def test_dedup_observations_passthrough_when_no_dups():
    """Three distinct observations (different LOINC codes / dates) pass through unchanged."""
    obs1 = _creatinine_obs("creat-1", date="2025-09-12")
    obs2 = _creatinine_obs("creat-2", date="2025-10-01")  # different date
    obs3 = _sodium_obs("sodium-1", date="2025-09-12")  # different LOINC

    result_obs, merges = dedup_observations([obs1, obs2, obs3])

    assert len(result_obs) == 3
    assert merges == []

    result_ids = {obs.get("id") for obs in result_obs}
    assert "creat-1" in result_ids
    assert "creat-2" in result_ids
    assert "sodium-1" in result_ids


# ---------------------------------------------------------------------------
# 15. ARTIFACT 5 ANCHOR TEST — Synthea FHIR + lab-PDF creatinine dedup
# ---------------------------------------------------------------------------


def test_dedup_observations_merges_artifact_5_creatinine():
    """ARTIFACT 5 anchor: Synthea Observation + lab-PDF Observation both show
    creatinine 1.4 mg/dL on 2025-09-12. dedup_observations should produce
    exactly one merged Observation and one ObservationMergeResult.

    This is the canonical showcase of the FHIR↔PDF dedup flow.
    """
    # Synthea source: a FHIR Observation with provenance from the clinical bundle
    synthea_obs = _creatinine_obs(
        obs_id="synthea-rhett759-creatinine-20250912",
        value=1.4,
        unit="mg/dL",
        date="2025-09-12",
        source_tag="synthea",
        quality_score=0.80,
    )

    # Lab-PDF source: extracted from Quest PDF page 2 bbox 72,574,540,590
    lab_pdf_obs = _creatinine_obs(
        obs_id="lab-pdf-quest-creatinine-20250912",
        value=1.4,
        unit="mg/dL",
        date="2025-09-12",
        source_tag="lab-pdf",
        quality_score=0.94,
    )

    result_obs, merges = dedup_observations(
        [synthea_obs, lab_pdf_obs],
        canonical_id_prefix="artifact5",
    )

    # Exactly one merged Observation (no duplicate raw records in output)
    assert len(result_obs) == 1, (
        f"Expected 1 merged observation, got {len(result_obs)}: "
        f"{[o.get('id') for o in result_obs]}"
    )

    # Exactly one merge result
    assert len(merges) == 1

    merge: ObservationMergeResult = merges[0]

    # Merged resource sanity checks
    merged = result_obs[0]
    assert merged["resourceType"] == "Observation"
    assert merged.get("id", "").startswith("artifact5")

    # Both source-tags in meta.tag
    tags = merged["meta"]["tag"]
    source_codes = {t["code"] for t in tags if t.get("system") == SYS_SOURCE_TAG}
    assert source_codes == {"synthea", "lab-pdf"}

    # lifecycle=harmonized
    lifecycle_codes = {t["code"] for t in tags if t.get("system") == SYS_LIFECYCLE}
    assert "harmonized" in lifecycle_codes

    # Both original IDs preserved as identifiers
    id_values = {ident.get("value") for ident in merged.get("identifier", [])}
    assert "synthea-rhett759-creatinine-20250912" in id_values
    assert "lab-pdf-quest-creatinine-20250912" in id_values

    # Max quality score = 0.94 (lab-pdf wins)
    quality_exts = [
        ext
        for ext in merged.get("meta", {}).get("extension", [])
        if isinstance(ext, dict) and ext.get("url") == EXT_QUALITY_SCORE
    ]
    assert len(quality_exts) == 1
    assert quality_exts[0]["valueDecimal"] == pytest.approx(0.94)

    # Provenance sources list includes both
    assert any("synthea" in src for src in merge.sources)
    assert any("lab-pdf" in src for src in merge.sources)

    # Rationale is non-empty
    assert merge.rationale
    assert LOINC_CREATININE in merge.rationale or "2160-0" in merge.rationale
