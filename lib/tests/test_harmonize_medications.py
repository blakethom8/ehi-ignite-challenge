"""Tests for lib.harmonize Medications merge."""

from __future__ import annotations

from lib.harmonize import (
    SourceBundle,
    canonical_drug_name,
    merge_medications,
    mint_provenance,
)


def _ehr_med(med_id: str, display: str, *rxnorms: str) -> dict:
    """A Cedars-style FHIR Medication resource (the one MedicationRequest references)."""
    coding = [
        {"system": "http://www.nlm.nih.gov/research/umls/rxnorm", "code": rx}
        for rx in rxnorms
    ]
    return {
        "resourceType": "Medication",
        "id": med_id,
        "code": {"text": display, "coding": coding},
    }


def _ehr_request(med_id: str, status: str = "active", authored: str | None = None) -> dict:
    mr: dict = {
        "resourceType": "MedicationRequest",
        "status": status,
        "intent": "order",
        "medicationReference": {"reference": f"Medication/{med_id}"},
    }
    if authored:
        mr["authoredOn"] = authored
    return mr


def _pdf_request(text: str, status: str = "active") -> dict:
    return {
        "resourceType": "MedicationRequest",
        "status": status,
        "medicationCodeableConcept": {"text": text},
    }


# ---------------------------------------------------------------------------
# Drug-name canonicalization
# ---------------------------------------------------------------------------


def test_canonical_drug_name_strips_brand_paren_and_dose():
    assert (
        canonical_drug_name("fluticasone propionate (FLONASE) 50 mcg/actuation nasal spray")
        == "fluticasone propionate"
    )
    assert canonical_drug_name("cetirizine (ZyrTEC) 10 mg tablet") == "cetirizine"
    assert canonical_drug_name("methylPREDNISolone (Medrol Pak) 4 mg tablet") == "methylprednisolone"


def test_canonical_drug_name_handles_no_paren_no_dose():
    assert canonical_drug_name("Aspirin") == "aspirin"
    assert canonical_drug_name("") == ""


# ---------------------------------------------------------------------------
# Merge tests
# ---------------------------------------------------------------------------


def test_rxnorm_match_across_sources():
    """Two FHIR sources with overlapping RxNorm sets merge into one record."""
    a = SourceBundle(
        "EHR-A",
        [
            _ehr_med("med-1", "cetirizine 10 mg tablet", "20610", "865258"),
            _ehr_request("med-1"),
        ],
    )
    b = SourceBundle(
        "EHR-B",
        [
            _ehr_med("med-2", "cetirizine 10 mg tablet", "865258", "1086791"),
            _ehr_request("med-2"),
        ],
    )
    merged = merge_medications([a, b])
    assert len(merged) == 1
    m = merged[0]
    assert "865258" in m.rxnorm_codes
    assert {s.source_label for s in m.sources} == {"EHR-A", "EHR-B"}


def test_drug_name_bridge_merges_pdf_into_ehr_record():
    """A FHIR source with RxNorm + a PDF source with text-only display
    (same generic name) merge into one record via the drug-name bridge."""
    ehr = SourceBundle(
        "Cedars",
        [
            _ehr_med("med-1", "cetirizine 10 mg tablet", "20610"),
            _ehr_request("med-1", authored="2025-12-03"),
        ],
    )
    pdf = SourceBundle(
        "Cedars-PDF",
        [_pdf_request("cetirizine (ZyrTEC) 10 mg tablet")],
    )
    merged = merge_medications([ehr, pdf])
    assert len(merged) == 1
    m = merged[0]
    assert m.canonical_name == "cetirizine"
    assert "20610" in m.rxnorm_codes
    activities = {e.activity for e in m.provenance}
    assert "rxnorm-match" in activities
    assert "drug-name-bridge" in activities


def test_distinct_drugs_dont_collapse():
    a = SourceBundle("A", [_pdf_request("fluticasone propionate (FLONASE) 50 mcg/actuation nasal spray")])
    b = SourceBundle("B", [_pdf_request("loratadine (Claritin) 10 mg tablet")])
    merged = merge_medications([a, b])
    assert len(merged) == 2
    names = {m.canonical_name for m in merged}
    assert names == {"fluticasone propionate", "loratadine"}


def test_rxnorm_codes_union_across_sources():
    """When RxNorm-keyed records merge, the union of codes ends up on the merged record."""
    a = SourceBundle(
        "A",
        [
            _ehr_med("m1", "cetirizine", "20610", "203150"),
            _ehr_request("m1"),
        ],
    )
    b = SourceBundle(
        "B",
        [
            _ehr_med("m2", "cetirizine", "20610", "865258", "1086791"),
            _ehr_request("m2"),
        ],
    )
    merged = merge_medications([a, b])
    assert len(merged) == 1
    assert set(merged[0].rxnorm_codes) == {"20610", "203150", "865258", "1086791"}


def test_resourcetype_filter_skips_non_medication_requests():
    """The bundle's `observations` list is shared across resource types — matcher filters."""
    a = SourceBundle(
        "Mixed",
        [
            _pdf_request("aspirin 81 mg tablet"),
            {"resourceType": "Observation", "code": {"text": "Glucose"}},
        ],
    )
    merged = merge_medications([a])
    assert len(merged) == 1
    assert merged[0].canonical_name == "aspirin"


def test_is_active_rolls_up_status():
    a = SourceBundle("A", [_ehr_med("m1", "aspirin", "1191"), _ehr_request("m1", status="completed")])
    merged = merge_medications([a])
    assert merged[0].is_active is False

    b = SourceBundle("B", [_pdf_request("ibuprofen 200 mg")])  # no status → assume active
    merged = merge_medications([b])
    assert merged[0].is_active is True


# ---------------------------------------------------------------------------
# Provenance for medications
# ---------------------------------------------------------------------------


def test_mint_provenance_on_merged_medication():
    a = SourceBundle("A", [_ehr_med("m1", "cetirizine", "20610"), _ehr_request("m1")])
    merged = merge_medications([a])
    prov = mint_provenance(merged[0])
    assert prov["resourceType"] == "Provenance"
    assert prov["target"][0]["reference"] == "MedicationRequest/merged-rxnorm-20610"
    assert prov["activity"]["coding"][0]["code"] == "rxnorm-match"


def test_provenance_records_drug_name_bridge_when_applicable():
    a = SourceBundle("A", [_ehr_med("m1", "cetirizine", "20610"), _ehr_request("m1")])
    b = SourceBundle("B", [_pdf_request("cetirizine 10 mg tablet")])
    merged = merge_medications([a, b])
    prov = mint_provenance(merged[0])
    # Top activity is rxnorm-match (rank 5) but the per-edge breakdown
    # should contain both rxnorm-match and drug-name-bridge.
    activities = {
        next(e["valueString"] for e in entity["extension"] if e["url"].endswith("harmonize-activity"))
        for entity in prov["entity"]
    }
    assert "rxnorm-match" in activities
    assert "drug-name-bridge" in activities


def test_empty_sources_returns_empty():
    assert merge_medications([]) == []
