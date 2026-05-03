"""Tests for ehi_atlas.harmonize.condition — Condition merge for Layer 3.

Coverage:
  1.  test_cluster_conditions_groups_htn_across_systems
  2.  test_cluster_conditions_keeps_distinct_conditions_separate
  3.  test_cluster_conditions_unmapped_codes_in_unmapped_group
  4.  test_merge_conditions_artifact_1_anchor
  5.  test_merge_conditions_picks_highest_quality_clinicalStatus
  6.  test_merge_conditions_takes_earliest_onset
  7.  test_merge_conditions_attaches_quality_score_extension
  8.  test_merge_conditions_attaches_umls_cui_to_codings
  9.  test_merge_conditions_emits_provenance_with_two_sources
  10. test_merge_conditions_rationale_includes_cui
  11. test_merge_conditions_singleton_flows_through_unchanged_in_bulk
  12. test_merge_all_conditions_handles_empty_input
  13. test_merge_all_conditions_groups_correctly_across_three_sources
"""

from __future__ import annotations

import pytest

from ehi_atlas.harmonize.condition import (
    ConditionMergeResult,
    cluster_conditions_by_cui,
    merge_all_conditions,
    merge_conditions,
)
from ehi_atlas.harmonize.provenance import (
    EXT_MERGE_RATIONALE,
    EXT_QUALITY_SCORE,
    EXT_UMLS_CUI,
    SYS_LIFECYCLE,
    SYS_SOURCE_TAG,
)


# ---------------------------------------------------------------------------
# FHIR coding constants (Artifact 1 anchor)
# ---------------------------------------------------------------------------

SNOMED_SYSTEM = "http://snomed.info/sct"
ICD10_SYSTEM = "http://hl7.org/fhir/sid/icd-10-cm"

# HTN codes
HTN_SNOMED_CODE = "38341003"
HTN_ICD10_CODE = "I10"
HTN_CUI = "C0020538"

# Diabetes codes (used to verify distinct grouping)
T2DM_SNOMED_CODE = "44054006"
T2DM_CUI = "C0011860"

# Clinical status CodeableConcept helpers
_CS_ACTIVE = {
    "coding": [
        {
            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
            "code": "active",
        }
    ]
}
_CS_INACTIVE = {
    "coding": [
        {
            "system": "http://terminology.hl7.org/CodeSystem/condition-clinical",
            "code": "inactive",
        }
    ]
}
_VS_CONFIRMED = {
    "coding": [
        {
            "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
            "code": "confirmed",
        }
    ]
}


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------


def _synthea_htn(id_suffix: str = "001", onset: str = "2018-03-04") -> dict:
    """Minimal Synthea-sourced HTN Condition using SNOMED code."""
    return {
        "resourceType": "Condition",
        "id": f"synthea-htn-{id_suffix}",
        "meta": {
            "tag": [
                {"system": SYS_SOURCE_TAG, "code": "synthea"},
            ],
            "extension": [
                # Pre-scored with synthea authority (completeness=full → 0.94)
                {"url": EXT_QUALITY_SCORE, "valueDecimal": 0.94},
            ],
        },
        "clinicalStatus": _CS_ACTIVE,
        "verificationStatus": _VS_CONFIRMED,
        "code": {
            "coding": [
                {
                    "system": SNOMED_SYSTEM,
                    "code": HTN_SNOMED_CODE,
                    "display": "Hypertensive disorder, systemic arterial",
                }
            ],
            "text": "Hypertension",
        },
        "subject": {"reference": "Patient/rhett759-merged"},
        "onsetDateTime": onset,
    }


def _epic_htn(id_suffix: str = "row42", onset: str = "2020-06-15") -> dict:
    """Minimal Epic-EHI–sourced HTN Condition using ICD-10 code."""
    return {
        "resourceType": "Condition",
        "id": f"epic-htn-{id_suffix}",
        "meta": {
            "tag": [
                {"system": SYS_SOURCE_TAG, "code": "epic-ehi"},
            ],
            "extension": [
                # Pre-scored with epic-ehi authority (completeness=full → 0.94)
                {"url": EXT_QUALITY_SCORE, "valueDecimal": 0.87},
            ],
        },
        "clinicalStatus": _CS_ACTIVE,
        "verificationStatus": _VS_CONFIRMED,
        "code": {
            "coding": [
                {
                    "system": ICD10_SYSTEM,
                    "code": HTN_ICD10_CODE,
                    "display": "Essential (primary) hypertension",
                }
            ],
            "text": "Essential hypertension",
        },
        "subject": {"reference": "Patient/rhett759-merged"},
        "onsetDateTime": onset,
    }


def _ccda_htn(id_suffix: str = "ccda-001", onset: str = "2015-01-01") -> dict:
    """Minimal CCDA-sourced HTN Condition using SNOMED code."""
    return {
        "resourceType": "Condition",
        "id": f"ccda-htn-{id_suffix}",
        "meta": {
            "tag": [
                {"system": SYS_SOURCE_TAG, "code": "ccda"},
            ],
            "extension": [
                {"url": EXT_QUALITY_SCORE, "valueDecimal": 0.80},
            ],
        },
        "clinicalStatus": _CS_ACTIVE,
        "verificationStatus": _VS_CONFIRMED,
        "code": {
            "coding": [
                {
                    "system": SNOMED_SYSTEM,
                    "code": HTN_SNOMED_CODE,
                    "display": "Hypertensive disorder, systemic arterial",
                }
            ],
        },
        "subject": {"reference": "Patient/rhett759-merged"},
        "onsetDateTime": onset,
    }


def _synthea_t2dm(id_suffix: str = "001") -> dict:
    """Minimal Synthea-sourced Type 2 Diabetes Condition using SNOMED code."""
    return {
        "resourceType": "Condition",
        "id": f"synthea-t2dm-{id_suffix}",
        "meta": {
            "tag": [
                {"system": SYS_SOURCE_TAG, "code": "synthea"},
            ],
        },
        "clinicalStatus": _CS_ACTIVE,
        "code": {
            "coding": [
                {
                    "system": SNOMED_SYSTEM,
                    "code": T2DM_SNOMED_CODE,
                    "display": "Diabetes mellitus type 2",
                }
            ]
        },
        "subject": {"reference": "Patient/rhett759-merged"},
        "onsetDateTime": "2019-01-01",
    }


def _unknown_condition(cond_id: str) -> dict:
    """Condition with a code not in the crosswalk → will be unmapped."""
    return {
        "resourceType": "Condition",
        "id": cond_id,
        "meta": {"tag": [{"system": SYS_SOURCE_TAG, "code": "synthea"}]},
        "code": {
            "coding": [
                {
                    "system": SNOMED_SYSTEM,
                    "code": "999999999",  # not in the Phase 1 crosswalk
                    "display": "Made-up condition",
                }
            ]
        },
        "subject": {"reference": "Patient/rhett759-merged"},
    }


# ---------------------------------------------------------------------------
# 1. Clustering: HTN across two systems → same CUI group
# ---------------------------------------------------------------------------


def test_cluster_conditions_groups_htn_across_systems():
    """Synthea HTN (SNOMED) and Epic HTN (ICD-10) must land in the same CUI group."""
    synthea = _synthea_htn()
    epic = _epic_htn()

    clusters = cluster_conditions_by_cui([synthea, epic])

    assert HTN_CUI in clusters, f"Expected CUI {HTN_CUI} in clusters; got keys: {list(clusters)}"
    ids_in_cluster = {c["id"] for c in clusters[HTN_CUI]}
    assert synthea["id"] in ids_in_cluster
    assert epic["id"] in ids_in_cluster


# ---------------------------------------------------------------------------
# 2. Clustering: HTN and T2DM land in separate clusters
# ---------------------------------------------------------------------------


def test_cluster_conditions_keeps_distinct_conditions_separate():
    """HTN cluster must not contain the T2DM Condition, and vice versa."""
    synthea_htn = _synthea_htn()
    synthea_t2dm = _synthea_t2dm()
    epic_htn = _epic_htn()

    clusters = cluster_conditions_by_cui([synthea_htn, synthea_t2dm, epic_htn])

    assert HTN_CUI in clusters
    assert T2DM_CUI in clusters

    htn_ids = {c["id"] for c in clusters[HTN_CUI]}
    t2dm_ids = {c["id"] for c in clusters[T2DM_CUI]}

    assert synthea_htn["id"] in htn_ids
    assert epic_htn["id"] in htn_ids
    assert synthea_t2dm["id"] in t2dm_ids
    assert synthea_t2dm["id"] not in htn_ids
    assert synthea_htn["id"] not in t2dm_ids


# ---------------------------------------------------------------------------
# 3. Clustering: unmapped code → _unmapped group
# ---------------------------------------------------------------------------


def test_cluster_conditions_unmapped_codes_in_unmapped_group():
    """A condition with an unknown code must land in the '_unmapped' group."""
    known = _synthea_htn()
    unknown = _unknown_condition("cond-unknown-001")

    clusters = cluster_conditions_by_cui([known, unknown])

    assert "_unmapped" in clusters, "Expected '_unmapped' key in clusters"
    unmapped_ids = {c["id"] for c in clusters["_unmapped"]}
    assert unknown["id"] in unmapped_ids
    assert known["id"] not in unmapped_ids


# ---------------------------------------------------------------------------
# 4. THE ARTIFACT 1 ANCHOR TEST
# ---------------------------------------------------------------------------


def test_merge_conditions_artifact_1_anchor():
    """Synthea SNOMED 38341003 + Epic ICD-10 I10 → ONE Condition with BOTH codings.

    This is the Artifact 1 canonical test: two sources describing HTN with
    different coding systems merge into one gold-tier Condition preserving
    both codings, both identifiers, and both source-tags.
    """
    synthea = _synthea_htn(id_suffix="001", onset="2018-03-04")
    epic = _epic_htn(id_suffix="row42", onset="2020-06-15")

    result = merge_conditions([synthea, epic], canonical_id="harmonized-htn-rhett759")

    merged = result.merged

    # --- Resource identity ---
    assert merged["resourceType"] == "Condition"
    assert merged["id"] == "harmonized-htn-rhett759"

    # --- Profile ---
    profiles = merged.get("meta", {}).get("profile", [])
    assert any("us-core-condition" in p for p in profiles), f"Expected us-core-condition profile, got {profiles}"

    # --- BOTH codings preserved ---
    codings = merged["code"]["coding"]
    assert len(codings) == 2, f"Expected exactly 2 codings, got {len(codings)}"
    coding_tuples = {(c["system"], c["code"]) for c in codings}
    assert (SNOMED_SYSTEM, HTN_SNOMED_CODE) in coding_tuples, "SNOMED HTN coding missing"
    assert (ICD10_SYSTEM, HTN_ICD10_CODE) in coding_tuples, "ICD-10 HTN coding missing"

    # --- BOTH source-tags present ---
    tags = merged["meta"]["tag"]
    source_codes = {t["code"] for t in tags if t.get("system") == SYS_SOURCE_TAG}
    assert "synthea" in source_codes, "synthea source-tag missing"
    assert "epic-ehi" in source_codes, "epic-ehi source-tag missing"

    # --- lifecycle=harmonized ---
    lifecycle_codes = {t["code"] for t in tags if t.get("system") == SYS_LIFECYCLE}
    assert "harmonized" in lifecycle_codes, "lifecycle=harmonized tag missing"

    # --- BOTH identifiers preserved ---
    identifier_values = {i.get("value") for i in merged.get("identifier", [])}
    assert synthea["id"] in identifier_values, f"Synthea id {synthea['id']} not in identifiers"
    assert epic["id"] in identifier_values, f"Epic id {epic['id']} not in identifiers"

    # --- Temporal envelope: 2018 wins over 2020 ---
    assert merged.get("onsetDateTime", "").startswith("2018"), (
        f"Expected earliest onset 2018, got {merged.get('onsetDateTime')}"
    )


# ---------------------------------------------------------------------------
# 5. Picks clinicalStatus from highest-quality input
# ---------------------------------------------------------------------------


def test_merge_conditions_picks_highest_quality_clinicalStatus():
    """The merged clinicalStatus must come from the highest-quality input."""
    # High-quality: clinicalStatus=active (synthea, score 0.94)
    high_quality = _synthea_htn()
    high_quality["clinicalStatus"] = _CS_ACTIVE

    # Low-quality: clinicalStatus=inactive (epic with lower pre-score)
    low_quality = _epic_htn()
    low_quality["clinicalStatus"] = _CS_INACTIVE
    low_quality["meta"]["extension"] = [{"url": EXT_QUALITY_SCORE, "valueDecimal": 0.65}]

    result = merge_conditions([high_quality, low_quality], canonical_id="test-htn-status")
    merged = result.merged

    # Should take the active status from the high-quality source
    cs_codes = {
        c.get("code")
        for c in merged.get("clinicalStatus", {}).get("coding", [])
    }
    assert "active" in cs_codes, f"Expected active clinicalStatus, got {cs_codes}"


# ---------------------------------------------------------------------------
# 6. Takes the earliest onset (temporal envelope)
# ---------------------------------------------------------------------------


def test_merge_conditions_takes_earliest_onset():
    """Merged onsetDateTime must be the earliest onset across all inputs."""
    earlier = _synthea_htn(onset="2018-03-04")
    later = _epic_htn(onset="2020-06-15")

    result = merge_conditions([earlier, later], canonical_id="test-earliest-onset")
    onset = result.merged.get("onsetDateTime", "")
    assert onset.startswith("2018"), f"Expected 2018 onset, got {onset}"

    # Reversed order — should still get 2018
    result2 = merge_conditions([later, earlier], canonical_id="test-earliest-onset-rev")
    onset2 = result2.merged.get("onsetDateTime", "")
    assert onset2.startswith("2018"), f"Expected 2018 onset (reversed), got {onset2}"


# ---------------------------------------------------------------------------
# 7. Attaches EXT_QUALITY_SCORE to merged meta
# ---------------------------------------------------------------------------


def test_merge_conditions_attaches_quality_score_extension():
    """Merged Condition must carry EXT_QUALITY_SCORE in meta.extension."""
    synthea = _synthea_htn()  # pre-scored 0.94
    epic = _epic_htn()        # pre-scored 0.87

    result = merge_conditions([synthea, epic], canonical_id="test-quality-ext")
    meta_exts = result.merged.get("meta", {}).get("extension", [])

    quality_exts = [e for e in meta_exts if e.get("url") == EXT_QUALITY_SCORE]
    assert len(quality_exts) == 1, f"Expected 1 quality-score extension, got {len(quality_exts)}"
    score = quality_exts[0].get("valueDecimal")
    assert score is not None, "quality-score valueDecimal is None"
    # Max of 0.94 and 0.87 → 0.94
    assert abs(score - 0.94) < 0.001, f"Expected max quality score ~0.94, got {score}"


# ---------------------------------------------------------------------------
# 8. EXT_UMLS_CUI attached to codings
# ---------------------------------------------------------------------------


def test_merge_conditions_attaches_umls_cui_to_codings():
    """Each coding in the merged code must carry the EXT_UMLS_CUI extension."""
    synthea = _synthea_htn()
    epic = _epic_htn()

    result = merge_conditions([synthea, epic], canonical_id="test-cui-codings")
    codings = result.merged["code"]["coding"]

    for coding in codings:
        cui_exts = [
            e for e in coding.get("extension", [])
            if e.get("url") == EXT_UMLS_CUI
        ]
        assert len(cui_exts) >= 1, (
            f"Coding {coding.get('system')}|{coding.get('code')} "
            f"missing EXT_UMLS_CUI extension"
        )
        assert cui_exts[0].get("valueString") == HTN_CUI, (
            f"Expected CUI {HTN_CUI}, got {cui_exts[0].get('valueString')}"
        )


# ---------------------------------------------------------------------------
# 9. Provenance emitted with two source entities
# ---------------------------------------------------------------------------


def test_merge_conditions_emits_provenance_with_two_sources():
    """merge_conditions must emit a Provenance with activity=MERGE and 2 source entities."""
    synthea = _synthea_htn()
    epic = _epic_htn()

    result = merge_conditions([synthea, epic], canonical_id="test-provenance")
    prov = result.provenance

    assert prov is not None
    assert prov.activity == "MERGE"
    assert len(prov.sources) == 2

    source_refs = {s.reference for s in prov.sources}
    assert f"Condition/{synthea['id']}" in source_refs
    assert f"Condition/{epic['id']}" in source_refs

    # to_fhir() must include the expected shape
    fhir_prov = prov.to_fhir()
    assert fhir_prov["resourceType"] == "Provenance"
    assert len(fhir_prov["entity"]) == 2


# ---------------------------------------------------------------------------
# 10. Rationale includes the UMLS CUI
# ---------------------------------------------------------------------------


def test_merge_conditions_rationale_includes_cui():
    """The merge rationale must contain the UMLS CUI for HTN."""
    synthea = _synthea_htn()
    epic = _epic_htn()

    result = merge_conditions([synthea, epic], canonical_id="test-rationale")

    # Rationale on the result
    assert HTN_CUI in result.rationale, f"CUI {HTN_CUI} not found in rationale: {result.rationale!r}"

    # Rationale also attached as extension on the merged resource
    top_exts = result.merged.get("extension", [])
    rationale_exts = [e for e in top_exts if e.get("url") == EXT_MERGE_RATIONALE]
    assert len(rationale_exts) == 1, f"Expected 1 merge-rationale extension, got {len(rationale_exts)}"
    assert HTN_CUI in rationale_exts[0].get("valueString", ""), (
        f"CUI not in rationale extension: {rationale_exts[0].get('valueString')!r}"
    )


# ---------------------------------------------------------------------------
# 11. Singleton cluster flows through unchanged in bulk
# ---------------------------------------------------------------------------


def test_merge_conditions_singleton_flows_through_unchanged_in_bulk():
    """A single-source cluster from merge_all_conditions must not be over-merged."""
    # One synthea HTN condition — no other source has an HTN condition
    synthea_htn = _synthea_htn()
    synthea_t2dm = _synthea_t2dm()

    conditions_by_source = {
        "synthea": [synthea_htn, synthea_t2dm],
    }

    result_conditions, merge_results = merge_all_conditions(conditions_by_source)

    # No merge results because there's only one source
    assert len(merge_results) == 0, f"Expected 0 merge results, got {len(merge_results)}"

    # Both conditions pass through
    result_ids = {c["id"] for c in result_conditions}
    assert synthea_htn["id"] in result_ids
    assert synthea_t2dm["id"] in result_ids


# ---------------------------------------------------------------------------
# 12. Empty input
# ---------------------------------------------------------------------------


def test_merge_all_conditions_handles_empty_input():
    """merge_all_conditions with empty input returns empty lists."""
    result_conditions, merge_results = merge_all_conditions({})
    assert result_conditions == []
    assert merge_results == []

    result_conditions2, merge_results2 = merge_all_conditions({"synthea": []})
    assert result_conditions2 == []
    assert merge_results2 == []


# ---------------------------------------------------------------------------
# 13. Three-source merge: Synthea + Epic + CCDA all have HTN
# ---------------------------------------------------------------------------


def test_merge_all_conditions_groups_correctly_across_three_sources():
    """Synthea + Epic + CCDA all having HTN → one merged Condition with all three sources."""
    synthea_htn = _synthea_htn(id_suffix="001", onset="2018-03-04")
    epic_htn = _epic_htn(id_suffix="row42", onset="2020-06-15")
    ccda_htn = _ccda_htn(id_suffix="ccda-001", onset="2015-01-01")

    # Each source also has a unique non-HTN condition (unmapped) to verify isolation
    synthea_unique = _unknown_condition("synthea-unique-001")
    synthea_t2dm = _synthea_t2dm()

    conditions_by_source = {
        "synthea": [synthea_htn, synthea_unique, synthea_t2dm],
        "epic-ehi": [epic_htn],
        "ccda": [ccda_htn],
    }

    result_conditions, merge_results = merge_all_conditions(conditions_by_source)

    # Exactly one merge result: the HTN cluster
    # (T2DM is singleton from synthea only → passes through)
    assert len(merge_results) == 1, f"Expected 1 merge result, got {len(merge_results)}: {merge_results}"

    htn_result = merge_results[0]
    merged = htn_result.merged

    # --- All three sources contributed ---
    assert len(htn_result.sources) == 3, f"Expected 3 source refs, got {htn_result.sources}"

    # --- All three source-tags present ---
    tags = merged["meta"]["tag"]
    source_codes = {t["code"] for t in tags if t.get("system") == SYS_SOURCE_TAG}
    assert "synthea" in source_codes
    assert "epic-ehi" in source_codes
    assert "ccda" in source_codes

    # --- Temporal envelope: CCDA 2015 is the earliest ---
    onset = merged.get("onsetDateTime", "")
    assert onset.startswith("2015"), f"Expected earliest onset 2015 (CCDA), got {onset}"

    # --- CUI in rationale ---
    assert HTN_CUI in htn_result.rationale

    # --- Unmapped condition flows through unchanged ---
    result_ids = {c["id"] for c in result_conditions}
    assert synthea_unique["id"] in result_ids

    # --- T2DM singleton flows through unchanged (no merge result for it) ---
    assert synthea_t2dm["id"] in result_ids
