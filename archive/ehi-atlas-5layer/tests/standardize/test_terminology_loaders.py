"""
Tests for ehi_atlas.terminology loaders.

Validates:
  - LOINC showcase has >= 15 entries
  - Crosswalk has a Hypertension entry with both SNOMED and ICD-10
  - lookup_cross resolves SNOMED 38341003 to an entry with umls_cui

These tests are fast and fully offline (no network calls, no file downloads).
"""

import pytest

from ehi_atlas.terminology import (
    load_handcrafted_crosswalk,
    load_loinc_showcase,
    lookup_cross,
)


class TestLoincShowcase:
    def test_loads_without_error(self):
        data = load_loinc_showcase()
        assert isinstance(data, dict)

    def test_has_codes_key(self):
        data = load_loinc_showcase()
        assert "codes" in data, "Expected 'codes' key in LOINC showcase JSON"

    def test_at_least_15_entries(self):
        data = load_loinc_showcase()
        codes = data["codes"]
        assert len(codes) >= 15, (
            f"Expected >= 15 LOINC codes in showcase, got {len(codes)}"
        )

    def test_creatinine_code_present(self):
        """Artifact 5 anchor code must be present."""
        data = load_loinc_showcase()
        code_values = {row["code"] for row in data["codes"]}
        assert "2160-0" in code_values, "Creatinine LOINC 2160-0 not found in showcase"

    def test_all_entries_have_required_fields(self):
        data = load_loinc_showcase()
        required = {"code", "display", "system", "category"}
        for row in data["codes"]:
            missing = required - row.keys()
            assert not missing, (
                f"LOINC entry {row.get('code')} missing fields: {missing}"
            )

    def test_all_use_loinc_system_uri(self):
        data = load_loinc_showcase()
        for row in data["codes"]:
            assert row["system"] == "http://loinc.org", (
                f"Expected http://loinc.org, got {row['system']} for code {row['code']}"
            )

    def test_hemoglobin_present(self):
        """Rhett759 has anemia — hemoglobin code 718-7 must be present."""
        data = load_loinc_showcase()
        code_values = {row["code"] for row in data["codes"]}
        assert "718-7" in code_values, "Hemoglobin LOINC 718-7 not found (anemia indicator)"

    def test_progress_note_document_code_present(self):
        """Artifact 4 planted note type must be present."""
        data = load_loinc_showcase()
        code_values = {row["code"] for row in data["codes"]}
        assert "11506-3" in code_values, "Progress note LOINC 11506-3 not found"


class TestHandcraftedCrosswalk:
    def test_loads_without_error(self):
        data = load_handcrafted_crosswalk()
        assert isinstance(data, dict)

    def test_has_codes_key(self):
        data = load_handcrafted_crosswalk()
        assert "codes" in data

    def test_at_least_10_entries(self):
        data = load_handcrafted_crosswalk()
        codes = data["codes"]
        assert len(codes) >= 10, (
            f"Expected >= 10 crosswalk entries, got {len(codes)}"
        )

    def test_hypertension_entry_exists(self):
        data = load_handcrafted_crosswalk()
        htn_entries = [
            row for row in data["codes"]
            if "hypertens" in row["concept_label"].lower()
        ]
        assert htn_entries, "No Hypertension entry found in crosswalk"

    def test_hypertension_has_snomed_and_icd10(self):
        """Artifact 1 anchor — must have both SNOMED and ICD-10 codes."""
        data = load_handcrafted_crosswalk()
        htn = next(
            (row for row in data["codes"] if "hypertens" in row["concept_label"].lower()),
            None,
        )
        assert htn is not None, "Hypertension entry not found"
        assert htn.get("snomed_ct") and htn["snomed_ct"].get("code"), (
            "Hypertension entry is missing SNOMED CT code"
        )
        assert htn.get("icd_10_cm") and htn["icd_10_cm"].get("code"), (
            "Hypertension entry is missing ICD-10-CM code"
        )

    def test_hypertension_icd10_is_i10(self):
        data = load_handcrafted_crosswalk()
        htn = next(
            row for row in data["codes"]
            if "hypertens" in row["concept_label"].lower()
        )
        assert htn["icd_10_cm"]["code"] == "I10", (
            f"Expected I10 for HTN, got {htn['icd_10_cm']['code']}"
        )

    def test_all_entries_have_concept_label(self):
        data = load_handcrafted_crosswalk()
        for row in data["codes"]:
            assert row.get("concept_label"), "Entry missing concept_label"

    def test_simvastatin_has_rxnorm(self):
        data = load_handcrafted_crosswalk()
        sim = next(
            (row for row in data["codes"] if "simvastatin" in row["concept_label"].lower()),
            None,
        )
        assert sim is not None, "Simvastatin entry not found"
        assert sim.get("rxnorm") and sim["rxnorm"].get("rxcui"), (
            "Simvastatin entry missing RxNorm RxCUI"
        )

    def test_nsclc_present(self):
        data = load_handcrafted_crosswalk()
        nsclc = next(
            (row for row in data["codes"] if "non-small cell" in row["concept_label"].lower()),
            None,
        )
        assert nsclc is not None, "NSCLC entry not found in crosswalk"


class TestLookupCross:
    def test_snomed_lookup_returns_entry(self):
        """Core test: SNOMED 38341003 (HTN) resolves to an entry."""
        row = lookup_cross("http://snomed.info/sct", "38341003")
        assert row is not None, "lookup_cross returned None for SNOMED 38341003 (HTN)"

    def test_snomed_lookup_has_umls_cui(self):
        row = lookup_cross("http://snomed.info/sct", "38341003")
        assert row is not None
        assert row.get("umls_cui"), (
            f"Expected umls_cui on HTN entry, got: {row}"
        )

    def test_snomed_lookup_correct_concept(self):
        row = lookup_cross("http://snomed.info/sct", "38341003")
        assert row is not None
        assert "hypertens" in row["concept_label"].lower()

    def test_snomed_shortname_lookup(self):
        """Short name 'snomed' should also resolve."""
        row = lookup_cross("snomed", "38341003")
        assert row is not None

    def test_icd10_lookup(self):
        row = lookup_cross("http://hl7.org/fhir/sid/icd-10-cm", "I10")
        assert row is not None, "ICD-10-CM I10 lookup failed"
        assert "hypertens" in row["concept_label"].lower()

    def test_icd10_shortname_lookup(self):
        row = lookup_cross("icd-10-cm", "I10")
        assert row is not None

    def test_rxnorm_lookup(self):
        row = lookup_cross("http://www.nlm.nih.gov/research/umls/rxnorm", "36567")
        assert row is not None, "RxNorm 36567 (simvastatin) lookup failed"
        assert "simvastatin" in row["concept_label"].lower()

    def test_umls_cui_lookup(self):
        row = lookup_cross("umls", "C0020538")
        assert row is not None, "UMLS CUI C0020538 (HTN) lookup failed"

    def test_missing_code_returns_none(self):
        row = lookup_cross("http://snomed.info/sct", "99999999")
        assert row is None

    def test_unknown_system_returns_none(self):
        row = lookup_cross("http://unknown.example.org/system", "38341003")
        assert row is None

    def test_chest_tightness_snomed_present(self):
        """Artifact 4 target SNOMED code must be resolvable."""
        row = lookup_cross("snomed", "23924001")
        assert row is not None, (
            "SNOMED 23924001 (chest tightness) not found — Artifact 4 extraction target missing"
        )
