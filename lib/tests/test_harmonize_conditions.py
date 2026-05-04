"""Tests for lib.harmonize Conditions merge."""

from __future__ import annotations

import pytest

from lib.harmonize import (
    MergedCondition,
    SourceBundle,
    merge_conditions,
    mint_provenance,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _cedars_cond(snomed: str, icd10: str, icd9: str | None, display: str, onset: str = "2025-01-01") -> dict:
    """A Cedars-style Condition: triple-coded SNOMED + ICD-10 + ICD-9."""
    coding = [
        {"system": "http://snomed.info/sct", "code": snomed, "display": display},
        {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": icd10, "display": display},
    ]
    if icd9:
        coding.append({"system": "http://hl7.org/fhir/sid/icd-9-cm", "code": icd9, "display": display})
    return {
        "resourceType": "Condition",
        "code": {"coding": coding, "text": display},
        "clinicalStatus": {
            "coding": [{"system": "http://terminology.hl7.org/CodeSystem/condition-clinical", "code": "active"}]
        },
        "onsetDateTime": onset,
    }


def _pdf_cond(display: str, onset: str | None = None) -> dict:
    """A vision-extracted Condition: text label only, no codes."""
    cond: dict = {
        "resourceType": "Condition",
        "code": {"text": display},
    }
    if onset:
        cond["onsetDateTime"] = onset
    return cond


# ---------------------------------------------------------------------------
# SNOMED + ICD merge
# ---------------------------------------------------------------------------


def test_snomed_match_across_sources():
    a = SourceBundle("Cedars", [_cedars_cond("21719001", "J30.1", "477.0", "Allergic rhinitis due to pollen")])
    b = SourceBundle("Other", [_cedars_cond("21719001", "J30.1", None, "Allergic rhinitis due to pollen", onset="2025-06-01")])
    merged = merge_conditions([a, b])
    assert len(merged) == 1
    m = merged[0]
    assert m.snomed == "21719001"
    assert m.icd10 == "J30.1"
    assert len(m.sources) == 2


def test_pdf_text_only_bridges_onto_cedars_via_display_text():
    """Text-only Condition + SNOMED-coded Condition with same display → one merged record.

    The name-bridge fallback: when a later Condition has no codes and its
    normalized display text matches an already-merged coded Condition,
    the matcher attaches it to that record (activity ``name-bridge``)
    rather than creating a duplicate text-keyed record.
    """
    a = SourceBundle("Cedars", [_cedars_cond("82297005", "R09.81", "478.19", "Sinus congestion")])
    b = SourceBundle("Cedars-PDF", [_pdf_cond("Sinus congestion")])
    merged = merge_conditions([a, b])
    assert len(merged) == 1
    m = merged[0]
    # Coded record retains its codes; the text-only source is added with
    # activity = name-bridge.
    assert m.snomed == "82297005"
    assert {s.source_label for s in m.sources} == {"Cedars", "Cedars-PDF"}
    activities = {e.activity for e in m.provenance}
    assert "name-bridge" in activities


def test_icd10_match_when_snomed_missing():
    """A source with only ICD-10 still merges with another ICD-10 source."""
    a = SourceBundle("A", [{
        "resourceType": "Condition",
        "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "J30.1"}], "text": "Allergic rhinitis"},
    }])
    b = SourceBundle("B", [{
        "resourceType": "Condition",
        "code": {"coding": [{"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "J30.1"}], "text": "Allergic rhinitis"},
    }])
    merged = merge_conditions([a, b])
    assert len(merged) == 1
    assert merged[0].icd10 == "J30.1"


def test_codes_promote_when_later_source_has_them():
    """SNOMED-only source + ICD10-only source for same fact → both codes filled in.

    Specifically: if both sources have SNOMED, the matcher keys on SNOMED.
    Then if the second source ALSO has ICD-10 that the first lacked, the
    merged record absorbs the ICD-10 too.
    """
    a = SourceBundle("A", [{
        "resourceType": "Condition",
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "21719001"}], "text": "Allergic rhinitis"},
    }])
    b = SourceBundle("B", [{
        "resourceType": "Condition",
        "code": {
            "coding": [
                {"system": "http://snomed.info/sct", "code": "21719001"},
                {"system": "http://hl7.org/fhir/sid/icd-10-cm", "code": "J30.1"},
            ],
            "text": "Allergic rhinitis",
        },
    }])
    merged = merge_conditions([a, b])
    assert len(merged) == 1
    m = merged[0]
    assert m.snomed == "21719001"
    assert m.icd10 == "J30.1"  # Promoted from source B


def test_text_only_sources_merge_by_name():
    a = SourceBundle("PDF-A", [_pdf_cond("Bilateral inferior turbinate hypertrophy")])
    b = SourceBundle("PDF-B", [_pdf_cond("Bilateral Inferior Turbinate Hypertrophy")])
    merged = merge_conditions([a, b])
    assert len(merged) == 1
    assert merged[0].snomed is None


def test_resourcetype_filter_skips_non_conditions():
    """The bundle field is shared with Observations; matcher filters by resourceType."""
    a = SourceBundle("Mixed", [
        _cedars_cond("21719001", "J30.1", None, "Allergic rhinitis"),
        {"resourceType": "Observation", "code": {"text": "Glucose"}, "valueQuantity": {"value": 90, "unit": "mg/dL"}},
    ])
    merged = merge_conditions([a])
    assert len(merged) == 1
    assert merged[0].canonical_name == "Allergic rhinitis"


# ---------------------------------------------------------------------------
# is_active rollup
# ---------------------------------------------------------------------------


def test_is_active_true_when_any_source_active():
    cond = _cedars_cond("21719001", "J30.1", None, "Allergic rhinitis")
    a = SourceBundle("A", [cond])
    merged = merge_conditions([a])
    assert merged[0].is_active is True


def test_is_active_false_when_all_resolved():
    a = SourceBundle("A", [{
        "resourceType": "Condition",
        "code": {"coding": [{"system": "http://snomed.info/sct", "code": "21719001"}], "text": "Allergic rhinitis"},
        "clinicalStatus": {"coding": [{"code": "resolved"}]},
    }])
    merged = merge_conditions([a])
    assert merged[0].is_active is False


def test_is_active_true_when_no_status_recorded():
    """PDF-extracted conditions usually lack clinicalStatus; treat as active."""
    a = SourceBundle("PDF", [_pdf_cond("Allergic rhinitis")])
    merged = merge_conditions([a])
    assert merged[0].is_active is True


# ---------------------------------------------------------------------------
# Provenance for Conditions
# ---------------------------------------------------------------------------


def test_mint_provenance_on_merged_condition():
    a = SourceBundle("Cedars", [_cedars_cond("21719001", "J30.1", "477.0", "Allergic rhinitis")])
    merged = merge_conditions([a])
    prov = mint_provenance(merged[0])
    assert prov["resourceType"] == "Provenance"
    assert prov["target"][0]["reference"] == "Condition/merged-snomed-21719001"
    assert prov["activity"]["coding"][0]["code"] == "snomed-match"


def test_provenance_activity_ranks_snomed_above_name():
    a = SourceBundle("Cedars", [_cedars_cond("21719001", "J30.1", None, "Allergic rhinitis")])
    b = SourceBundle("Same-as-snomed-source", [_cedars_cond("21719001", "J30.1", None, "Allergic rhinitis")])
    merged = merge_conditions([a, b])
    prov = mint_provenance(merged[0])
    # All edges are snomed-match here, so rollup is snomed-match.
    assert prov["activity"]["coding"][0]["code"] == "snomed-match"
