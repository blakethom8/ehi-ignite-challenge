"""Tests for lib.harmonize Allergies + Immunizations matchers."""

from __future__ import annotations

from lib.harmonize import (
    SourceBundle,
    merge_allergies,
    merge_immunizations,
    mint_provenance,
)


# ---------------------------------------------------------------------------
# Allergies
# ---------------------------------------------------------------------------


def _ehr_allergy(snomed: str, display: str, criticality: str | None = "high") -> dict:
    return {
        "resourceType": "AllergyIntolerance",
        "code": {
            "coding": [{"system": "http://snomed.info/sct", "code": snomed, "display": display}],
            "text": display,
        },
        "criticality": criticality,
        "clinicalStatus": {"coding": [{"code": "active"}]},
    }


def _pdf_allergy(display: str) -> dict:
    return {"resourceType": "AllergyIntolerance", "code": {"text": display}}


def test_allergy_snomed_match():
    a = SourceBundle("EHR", [_ehr_allergy("716186003", "No known allergy")])
    b = SourceBundle("EHR-2", [_ehr_allergy("716186003", "No known allergy")])
    merged = merge_allergies([a, b])
    assert len(merged) == 1
    assert merged[0].snomed == "716186003"
    assert len(merged[0].sources) == 2


def test_allergy_pdf_text_only_bridges_onto_snomed():
    """SNOMED-coded EHR allergy + text-only PDF → one merged record."""
    a = SourceBundle("EHR", [_ehr_allergy("91930004", "Allergy to peanut")])
    b = SourceBundle("PDF", [_pdf_allergy("Allergy to peanut")])
    merged = merge_allergies([a, b])
    assert len(merged) == 1
    assert merged[0].snomed == "91930004"
    activities = {e.activity for e in merged[0].provenance}
    assert "snomed-match" in activities
    assert "name-bridge" in activities


def test_allergy_highest_criticality_rolls_up():
    a = SourceBundle("EHR-low", [_ehr_allergy("91930004", "Peanut", criticality="low")])
    b = SourceBundle("EHR-high", [_ehr_allergy("91930004", "Peanut", criticality="high")])
    merged = merge_allergies([a, b])
    assert merged[0].highest_criticality == "high"


def test_allergy_provenance_minted():
    a = SourceBundle("EHR", [_ehr_allergy("716186003", "No known allergy")])
    merged = merge_allergies([a])
    prov = mint_provenance(merged[0])
    assert prov["resourceType"] == "Provenance"
    assert prov["target"][0]["reference"] == "AllergyIntolerance/merged-snomed-716186003"


# ---------------------------------------------------------------------------
# Immunizations
# ---------------------------------------------------------------------------


def _ehr_im(cvx: str, display: str, date: str) -> dict:
    return {
        "resourceType": "Immunization",
        "vaccineCode": {
            "coding": [{"system": "http://hl7.org/fhir/sid/cvx", "code": cvx, "display": display}],
            "text": display,
        },
        "occurrenceDateTime": date,
        "status": "completed",
    }


def _pdf_im(display: str, date: str) -> dict:
    return {
        "resourceType": "Immunization",
        "vaccineCode": {"text": display},
        "occurrenceDateTime": date,
    }


def test_im_cvx_date_match_collapses_same_shot():
    """Same CVX + same date across sources = one merged record (strict).

    Real-world Cedars data uses the same display text in both FHIR and
    the extracted PDF, so the strict-name-match handles same-day pairs
    via the name-bridge fallback path. We test both that path
    (test_im_text_only_with_date_matches) and the CVX-driven path here.
    """
    a = SourceBundle("EHR", [_ehr_im("150", "Influenza, QUAD, Preservative Free", "2023-10-26")])
    b = SourceBundle("PDF", [_pdf_im("Influenza, QUAD, Preservative Free", "2023-10-26")])
    merged = merge_immunizations([a, b])
    assert len(merged) == 1
    assert merged[0].cvx == "150"
    assert {s.source_label for s in merged[0].sources} == {"EHR", "PDF"}


def test_im_same_cvx_different_dates_stay_separate():
    """Same vaccine, different dates = separate events."""
    a = SourceBundle("EHR", [_ehr_im("150", "Influenza QUAD", "2023-10-26")])
    b = SourceBundle("EHR-2", [_ehr_im("150", "Influenza QUAD", "2024-10-09")])
    merged = merge_immunizations([a, b])
    assert len(merged) == 2
    dates = sorted(m.occurrence_date.date().isoformat() for m in merged)
    assert dates == ["2023-10-26", "2024-10-09"]


def test_im_text_only_with_date_matches():
    """Two PDFs that both lack CVX but agree on display + date collapse."""
    a = SourceBundle("PDF-A", [_pdf_im("MMR", "1994-09-21")])
    b = SourceBundle("PDF-B", [_pdf_im("MMR", "1994-09-21")])
    merged = merge_immunizations([a, b])
    assert len(merged) == 1


def test_im_chronological_order():
    a = SourceBundle("EHR", [
        _ehr_im("03", "MMR", "1999-04-29"),
        _ehr_im("03", "MMR", "1994-09-21"),
        _ehr_im("150", "Flu QUAD", "2023-10-26"),
    ])
    merged = merge_immunizations([a])
    dates = [m.occurrence_date.date().isoformat() for m in merged]
    assert dates == ["1994-09-21", "1999-04-29", "2023-10-26"]


def test_im_provenance():
    a = SourceBundle("EHR", [_ehr_im("150", "Influenza QUAD", "2023-10-26")])
    merged = merge_immunizations([a])
    prov = mint_provenance(merged[0])
    assert prov["resourceType"] == "Provenance"
    assert prov["activity"]["coding"][0]["code"] == "cvx-match"


def test_im_resourcetype_filter():
    a = SourceBundle("Mixed", [
        _ehr_im("150", "Flu", "2023-10-26"),
        {"resourceType": "Observation", "code": {"text": "Glucose"}},
    ])
    merged = merge_immunizations([a])
    assert len(merged) == 1
