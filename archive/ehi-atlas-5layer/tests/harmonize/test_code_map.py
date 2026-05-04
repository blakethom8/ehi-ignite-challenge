"""Tests for ehi_atlas.harmonize.code_map — Layer 3 code-mapping module.

Covers:
  - resolve_coding() for SNOMED/ICD-10 hits and unknown codes
  - codings_equivalent() cross-system, unknown, and different-concept cases
  - codeable_concepts_equivalent() via any coding pair
  - annotate_codeable_concept_with_cui() — extension addition and idempotency
  - annotate_resource_codings() — Condition and MedicationRequest
  - collect_concept_groups() — grouping and exclusion of unmapped resources
"""

from __future__ import annotations

import pytest

from ehi_atlas.harmonize.code_map import (
    SYS_ICD10_CM,
    SYS_SNOMED,
    CodingRef,
    annotate_codeable_concept_with_cui,
    annotate_resource_codings,
    codeable_concepts_equivalent,
    codings_equivalent,
    collect_concept_groups,
    resolve_coding,
)
from ehi_atlas.harmonize.provenance import EXT_UMLS_CUI

# ---------------------------------------------------------------------------
# Fixtures — representative crosswalk values
# ---------------------------------------------------------------------------

# Hypertension
SNOMED_HTN = CodingRef(system=SYS_SNOMED, code="38341003", display="Hypertensive disorder")
ICD10_HTN = CodingRef(system=SYS_ICD10_CM, code="I10", display="Essential hypertension")
CUI_HTN = "C0020538"

# Type 2 diabetes
SNOMED_T2DM = CodingRef(system=SYS_SNOMED, code="44054006", display="Diabetes mellitus type 2")
CUI_T2DM = "C0011860"

# Unknown / garbage code
UNKNOWN = CodingRef(system=SYS_SNOMED, code="00000000", display="Unknown")


# ---------------------------------------------------------------------------
# 1. resolve_coding — SNOMED hit
# ---------------------------------------------------------------------------

def test_resolve_coding_snomed_hit():
    res = resolve_coding(SNOMED_HTN)
    assert res.found_in_crosswalk is True
    assert res.umls_cui == CUI_HTN
    assert res.crosswalk_label is not None
    assert "Hypertensive" in res.crosswalk_label


# ---------------------------------------------------------------------------
# 2. resolve_coding — ICD-10 hit, same CUI as SNOMED 38341003
# ---------------------------------------------------------------------------

def test_resolve_coding_icd10_hit():
    res = resolve_coding(ICD10_HTN)
    assert res.found_in_crosswalk is True
    assert res.umls_cui == CUI_HTN  # same CUI as SNOMED 38341003


# ---------------------------------------------------------------------------
# 3. resolve_coding — unknown code returns found_in_crosswalk=False
# ---------------------------------------------------------------------------

def test_resolve_coding_unknown_returns_no_cui():
    res = resolve_coding(UNKNOWN)
    assert res.found_in_crosswalk is False
    assert res.umls_cui is None
    assert res.crosswalk_label is None


# ---------------------------------------------------------------------------
# 4. codings_equivalent — cross-system (SNOMED HTN ≡ ICD-10 I10)
# ---------------------------------------------------------------------------

def test_codings_equivalent_cross_system():
    assert codings_equivalent(SNOMED_HTN, ICD10_HTN) is True


# ---------------------------------------------------------------------------
# 5. codings_equivalent — unknown codes always return False
# ---------------------------------------------------------------------------

def test_codings_equivalent_unknown_codes_return_false():
    # Unknown vs known
    assert codings_equivalent(UNKNOWN, SNOMED_HTN) is False
    # Both unknown
    other_unknown = CodingRef(system=SYS_SNOMED, code="99999999")
    assert codings_equivalent(UNKNOWN, other_unknown) is False


# ---------------------------------------------------------------------------
# 6. codings_equivalent — different concepts return False
# ---------------------------------------------------------------------------

def test_codings_not_equivalent_when_different_concepts():
    # HTN SNOMED vs T2DM SNOMED — distinct CUIs
    assert codings_equivalent(SNOMED_HTN, SNOMED_T2DM) is False


# ---------------------------------------------------------------------------
# 7. codeable_concepts_equivalent — match via any coding pair
# ---------------------------------------------------------------------------

def test_codeable_concepts_equivalent_via_any_coding():
    # Concept A has SNOMED HTN + display-only entry
    concept_a = {
        "coding": [
            {"system": SYS_SNOMED, "code": "38341003", "display": "HTN"},
            {"system": "http://example.com/local", "code": "HT-01"},
        ],
        "text": "Hypertension",
    }
    # Concept B has only ICD-10 I10
    concept_b = {
        "coding": [
            {"system": SYS_ICD10_CM, "code": "I10", "display": "Essential hypertension"},
        ]
    }
    assert codeable_concepts_equivalent(concept_a, concept_b) is True


# ---------------------------------------------------------------------------
# 8. annotate_codeable_concept_adds_cui_extension
# ---------------------------------------------------------------------------

def test_annotate_codeable_concept_adds_cui_extension():
    concept = {
        "coding": [
            {"system": SYS_SNOMED, "code": "38341003", "display": "HTN"},
        ]
    }
    result = annotate_codeable_concept_with_cui(concept)
    coding = result["coding"][0]
    assert "extension" in coding
    ext_urls = [e["url"] for e in coding["extension"]]
    assert EXT_UMLS_CUI in ext_urls
    # Value should be the HTN CUI
    cui_ext = next(e for e in coding["extension"] if e["url"] == EXT_UMLS_CUI)
    assert cui_ext["valueString"] == CUI_HTN


# ---------------------------------------------------------------------------
# 9. annotate_codeable_concept_is_idempotent
# ---------------------------------------------------------------------------

def test_annotate_codeable_concept_is_idempotent():
    concept = {
        "coding": [
            {"system": SYS_SNOMED, "code": "38341003", "display": "HTN"},
        ]
    }
    annotate_codeable_concept_with_cui(concept)
    annotate_codeable_concept_with_cui(concept)  # second call

    coding = concept["coding"][0]
    cui_exts = [e for e in coding.get("extension", []) if e["url"] == EXT_UMLS_CUI]
    # Must not duplicate
    assert len(cui_exts) == 1
    assert cui_exts[0]["valueString"] == CUI_HTN


# ---------------------------------------------------------------------------
# 10. annotate_resource_codings — Condition
# ---------------------------------------------------------------------------

def test_annotate_resource_codings_handles_condition():
    resource = {
        "resourceType": "Condition",
        "id": "cond-htn-001",
        "code": {
            "coding": [
                {"system": SYS_SNOMED, "code": "38341003", "display": "Hypertensive disorder"},
            ],
            "text": "Hypertension",
        },
    }
    result = annotate_resource_codings(resource)
    coding = result["code"]["coding"][0]
    assert "extension" in coding
    cui_exts = [e for e in coding["extension"] if e["url"] == EXT_UMLS_CUI]
    assert len(cui_exts) == 1
    assert cui_exts[0]["valueString"] == CUI_HTN


# ---------------------------------------------------------------------------
# 11. annotate_resource_codings — MedicationRequest
# ---------------------------------------------------------------------------

def test_annotate_resource_codings_handles_medication_request():
    # Simvastatin RxCUI 36567
    resource = {
        "resourceType": "MedicationRequest",
        "id": "medrx-simva-001",
        "medicationCodeableConcept": {
            "coding": [
                {
                    "system": "http://www.nlm.nih.gov/research/umls/rxnorm",
                    "code": "36567",
                    "display": "Simvastatin",
                }
            ]
        },
    }
    result = annotate_resource_codings(resource)
    coding = result["medicationCodeableConcept"]["coding"][0]
    assert "extension" in coding
    cui_exts = [e for e in coding["extension"] if e["url"] == EXT_UMLS_CUI]
    assert len(cui_exts) == 1
    assert cui_exts[0]["valueString"] == "C0074554"  # Simvastatin CUI


# ---------------------------------------------------------------------------
# 12. collect_concept_groups — clusters synonymous codes
# ---------------------------------------------------------------------------

def test_collect_concept_groups_clusters_synonymous_codes():
    cond_snomed_htn = {
        "resourceType": "Condition",
        "id": "c1",
        "code": {
            "coding": [{"system": SYS_SNOMED, "code": "38341003"}]
        },
    }
    cond_icd10_htn = {
        "resourceType": "Condition",
        "id": "c2",
        "code": {
            "coding": [{"system": SYS_ICD10_CM, "code": "I10"}]
        },
    }
    cond_t2dm = {
        "resourceType": "Condition",
        "id": "c3",
        "code": {
            "coding": [{"system": SYS_SNOMED, "code": "44054006"}]
        },
    }

    groups = collect_concept_groups([cond_snomed_htn, cond_icd10_htn, cond_t2dm])

    assert CUI_HTN in groups
    assert len(groups[CUI_HTN]) == 2
    assert cond_snomed_htn in groups[CUI_HTN]
    assert cond_icd10_htn in groups[CUI_HTN]

    assert CUI_T2DM in groups
    assert len(groups[CUI_T2DM]) == 1
    assert cond_t2dm in groups[CUI_T2DM]


# ---------------------------------------------------------------------------
# 13. collect_concept_groups — excludes unmapped resources
# ---------------------------------------------------------------------------

def test_collect_concept_groups_excludes_unmapped_resources():
    known_cond = {
        "resourceType": "Condition",
        "id": "known",
        "code": {
            "coding": [{"system": SYS_SNOMED, "code": "38341003"}]
        },
    }
    unknown_cond = {
        "resourceType": "Condition",
        "id": "unknown",
        "code": {
            "coding": [{"system": SYS_SNOMED, "code": "00000000"}]
        },
    }

    groups = collect_concept_groups([known_cond, unknown_cond])

    # Known resource appears under the HTN CUI
    assert CUI_HTN in groups
    assert known_cond in groups[CUI_HTN]

    # Unknown resource does not appear in any group
    all_resources = [r for rs in groups.values() for r in rs]
    assert unknown_cond not in all_resources
