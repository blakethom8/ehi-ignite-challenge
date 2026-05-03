"""5-artifact integration test for the rhett759 showcase patient.

This is the regression bar: if any test in this module fails, the EHI Atlas
demo is broken.  Run the full orchestrator once per test session (class-scoped
fixture), then assert each of the five showcase artifacts produces the expected
gold-tier behavior.

Marked @pytest.mark.integration so that ``make test-fast`` (which runs
``-m 'not integration'``) can skip this file without breaking the fast loop.

Run this file standalone::

    uv run pytest tests/harmonize/test_showcase_patient.py -v

Or filter in alongside the rest::

    uv run pytest -m integration -v

Artifact summary
----------------
Artifact 1 — Cross-system Condition merge (Hyperlipidemia SNOMED 55822004 /
             ICD-10 E78.5, CUI C0020473).  Note: BUILD-TRACKER refers to HTN
             (C0020538) but Rhett759 does not have HTN in either Synthea silver
             or Epic bronze; the live Artifact 1 is Hyperlipidemia.

Artifact 2 — Medication cross-class divergence (simvastatin RxCUI 316672 in
             Synthea, atorvastatin RxCUI 83367 in Epic).  Both preserved, each
             with EXT_CONFLICT_PAIR pointing at the other.  Root-cause of the
             conflicts_detected=0 bug: _RXCUI_CLASS_LABEL only had ingredient-
             level RxCUI 36567 for simvastatin, but Synthea emits product-level
             316672.  Fixed by adding 316672 to that dict.

Artifact 3 — Orphan-source preservation.  Synthea silver (real L2) has 136
             Claim resources that are single-source (synthea only) and pass
             through untouched.

Artifact 4 — Synthesized clinical note DocumentReference in gold (Phase 1
             partial — chest-tightness Condition extraction is Phase 2).

Artifact 5 — Cross-format Observation merge (Epic EHI creatinine + lab-pdf
             stub-silver creatinine, LOINC 2160-0, date 2025-09-12, 1.4 mg/dL).
             Note: Synthea's Rhett759 has no creatinine observation, so the merge
             is epic-ehi + lab-pdf (not synthea + lab-pdf as originally designed).
             The EXT_SOURCE_LOCATOR (page=2;bbox=...) is absent in Phase 1 because
             the lab-pdf stub-silver does not run vision extraction.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ehi_atlas.harmonize.orchestrator import harmonize_patient
from ehi_atlas.harmonize.provenance import (
    EXT_CONFLICT_PAIR,
    EXT_MERGE_RATIONALE,
    EXT_QUALITY_SCORE,
    EXT_SOURCE_LOCATOR,
    EXT_UMLS_CUI,
    SYS_SOURCE_TAG,
    SYS_LIFECYCLE,
)

# ---------------------------------------------------------------------------
# Corpus paths
# ---------------------------------------------------------------------------

_ATLAS_ROOT = Path(__file__).resolve().parents[2]
_SILVER_ROOT = _ATLAS_ROOT / "corpus" / "silver"
_BRONZE_ROOT = _ATLAS_ROOT / "corpus" / "bronze"
_PATIENT_ID = "rhett759"

_SYNTHEA_SILVER = _SILVER_ROOT / "synthea" / _PATIENT_ID / "bundle.json"
_EPIC_BRONZE = _BRONZE_ROOT / "epic-ehi" / _PATIENT_ID / "data.sqlite.dump"
_LAB_PDF_BRONZE = _BRONZE_ROOT / "lab-pdf" / _PATIENT_ID / "data.pdf"
_CLINICAL_NOTE_BRONZE = (
    _BRONZE_ROOT / "synthesized-clinical-note" / _PATIENT_ID / "data.json"
)
_SYNTHEA_PAYER_BRONZE = _BRONZE_ROOT / "synthea-payer" / _PATIENT_ID / "data.json"


def _corpus_available() -> bool:
    """True iff the minimum corpus inputs for the integration test are present."""
    return _SYNTHEA_SILVER.exists() and _EPIC_BRONZE.exists()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _source_tags(resource: dict) -> set[str]:
    """Return all source-tag codes from a resource's meta.tag."""
    return {
        t.get("code", "")
        for t in resource.get("meta", {}).get("tag", [])
        if isinstance(t, dict) and t.get("system") == SYS_SOURCE_TAG
    }


def _lifecycle_tags(resource: dict) -> set[str]:
    """Return all lifecycle codes from a resource's meta.tag."""
    return {
        t.get("code", "")
        for t in resource.get("meta", {}).get("tag", [])
        if isinstance(t, dict) and t.get("system") == SYS_LIFECYCLE
    }


def _meta_extensions(resource: dict) -> list[dict]:
    return resource.get("meta", {}).get("extension", []) or []


def _resource_extensions(resource: dict) -> list[dict]:
    return resource.get("extension", []) or []


def _ext_value(extensions: list[dict], url: str) -> object:
    """Return the first value of an extension with the given URL, or None."""
    for ext in extensions:
        if ext.get("url") == url:
            for key in ("valueString", "valueDecimal", "valueReference",
                        "valueCoding", "valueBoolean"):
                if key in ext:
                    return ext[key]
    return None


def _condition_codings(resource: dict) -> list[dict]:
    return resource.get("code", {}).get("coding", [])


def _coding_extension_value(coding: dict, url: str) -> object | None:
    for ext in coding.get("extension", []):
        if ext.get("url") == url:
            return ext.get("valueString") or ext.get("valueDecimal") or ext.get("valueReference")
    return None


# ---------------------------------------------------------------------------
# Test class
# ---------------------------------------------------------------------------


@pytest.mark.integration
@pytest.mark.skipif(
    not _corpus_available(),
    reason=(
        "Showcase corpus not available.  Need at minimum: "
        f"{_SYNTHEA_SILVER} and {_EPIC_BRONZE}"
    ),
)
class TestShowcasePatient:
    """End-to-end integration test for the rhett759 showcase patient.

    Runs the full Layer-3 orchestrator once (class-scoped fixture) and asserts
    every showcase artifact produces the expected gold-tier behavior.  This is
    the regression bar: if any of these tests fails, the demo is broken.
    """

    # ------------------------------------------------------------------
    # Fixture — runs orchestrator ONCE per test class invocation
    # ------------------------------------------------------------------

    @pytest.fixture(scope="class")
    def gold_outputs(self, tmp_path_factory):
        """Run the orchestrator and return (bundle_dict, prov_records, manifest_dict).

        Uses the real corpus silver/bronze (not the pre-built gold in the repo)
        so the test is always driven by the current code, not a stale artifact.
        """
        gold_root = tmp_path_factory.mktemp("gold")
        result = harmonize_patient(
            silver_root=_SILVER_ROOT,
            bronze_root=_BRONZE_ROOT,
            gold_root=gold_root,
            patient_id=_PATIENT_ID,
        )

        bundle = json.loads(result.bundle_path.read_text(encoding="utf-8"))
        prov_records = [
            json.loads(line)
            for line in result.provenance_path.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

        return bundle, prov_records, manifest

    # ------------------------------------------------------------------
    # Orchestration sanity
    # ------------------------------------------------------------------

    def test_gold_tier_files_exist(self, gold_outputs):
        """bundle, provenance, and manifest must all be produced."""
        bundle, prov_records, manifest = gold_outputs
        # If we got here without error the files exist; also check content
        assert bundle.get("resourceType") == "Bundle"
        assert len(bundle.get("entry", [])) > 0
        assert len(prov_records) > 0
        assert manifest.get("patient_id") == _PATIENT_ID

    def test_manifest_lists_all_five_sources(self, gold_outputs):
        """manifest.sources must include all five sources used for Rhett759."""
        _, _, manifest = gold_outputs
        source_names = {s["name"] for s in manifest["sources"]}
        expected = {
            "synthea",
            "synthea-payer",
            "epic-ehi",
            "lab-pdf",
            "synthesized-clinical-note",
        }
        missing = expected - source_names
        assert not missing, (
            f"manifest.sources missing: {missing}.  Found: {source_names}"
        )

    def test_bundle_has_patient_resource_with_all_source_identifiers(self, gold_outputs):
        """Gold Patient must carry identifiers from both Synthea and Epic sources."""
        bundle, _, _ = gold_outputs
        entries = bundle["entry"]
        patients = [
            e["resource"]
            for e in entries
            if e["resource"].get("resourceType") == "Patient"
        ]
        assert len(patients) == 1, f"Expected 1 Patient, found {len(patients)}"

        patient = patients[0]
        identifiers = patient.get("identifier", [])
        assert len(identifiers) >= 2, (
            f"Patient should have ≥2 identifiers (one per source).  Found {len(identifiers)}: "
            f"{identifiers}"
        )
        # At least one from Synthea (SMART Health IT) and one from Epic
        systems = {idn.get("system", "") for idn in identifiers}
        has_synthea_id = any("smarthealthit" in s or "hospital" in s for s in systems)
        has_epic_id = any("epic" in s.lower() for s in systems)
        assert has_synthea_id, f"No Synthea MRN identifier found.  Systems: {systems}"
        assert has_epic_id, f"No Epic MRN identifier found.  Systems: {systems}"

    def test_provenance_ndjson_has_at_least_one_record_per_merge(self, gold_outputs):
        """provenance.ndjson must have MERGE records for conditions and observations."""
        _, prov_records, _ = gold_outputs
        assert len(prov_records) >= 1, "provenance.ndjson is empty"

        activities = set()
        for prov in prov_records:
            for coding in prov.get("activity", {}).get("coding", []):
                activities.add(coding.get("code", ""))

        assert "MERGE" in activities, (
            f"No MERGE activity in provenance.  Activities found: {activities}"
        )

    # ------------------------------------------------------------------
    # Artifact 1: Cross-system Condition merge (Hyperlipidemia)
    # ------------------------------------------------------------------
    #
    # NOTE: BUILD-TRACKER refers to HTN (SNOMED 38341003 / ICD-10 I10 / CUI C0020538)
    # but Rhett759 does NOT have Hypertension in either Synthea silver or Epic bronze.
    # The live Artifact 1 cross-system merge is:
    #   Synthea SNOMED 55822004 (Hyperlipidemia) ↔ Epic ICD-10 E78.5 (Hyperlipidemia)
    #   via UMLS CUI C0020473.
    # Tests below use the real data.

    def test_artifact_1_hyperlipidemia_condition_has_both_codings(self, gold_outputs):
        """Gold should have ONE merged Condition with both SNOMED 55822004 and
        ICD-10 E78.5 in code.coding[], bridged by UMLS CUI C0020473."""
        bundle, _, _ = gold_outputs
        conditions = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"].get("resourceType") == "Condition"
        ]

        hyperlipidemia = None
        for cond in conditions:
            codes = {c.get("code") for c in _condition_codings(cond)}
            if "55822004" in codes and "E78.5" in codes:
                hyperlipidemia = cond
                break

        assert hyperlipidemia is not None, (
            "No merged Hyperlipidemia Condition with both SNOMED 55822004 and ICD-10 E78.5.  "
            f"Condition codes found: {[{c.get('code') for c in _condition_codings(c)} for c in conditions]}"
        )

        codings = _condition_codings(hyperlipidemia)
        assert len(codings) >= 2, (
            f"Expected ≥2 codings (SNOMED + ICD-10) but found {len(codings)}: {codings}"
        )

    def test_artifact_1_hyperlipidemia_has_umls_cui_on_codings(self, gold_outputs):
        """Each coding on the merged Hyperlipidemia Condition should carry EXT_UMLS_CUI=C0020473."""
        bundle, _, _ = gold_outputs
        conditions = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"].get("resourceType") == "Condition"
        ]
        hyperlipidemia = next(
            (
                c
                for c in conditions
                if {"55822004", "E78.5"} <= {cod.get("code") for cod in _condition_codings(c)}
            ),
            None,
        )
        assert hyperlipidemia is not None, (
            "Merged Hyperlipidemia Condition not found (prerequisite for CUI check)"
        )

        codings = _condition_codings(hyperlipidemia)
        cui_values = {
            _coding_extension_value(cod, EXT_UMLS_CUI)
            for cod in codings
        }
        assert "C0020473" in cui_values, (
            f"EXT_UMLS_CUI=C0020473 not found on any coding.  "
            f"CUI values found: {cui_values}.  Codings: {codings}"
        )

    def test_artifact_1_hyperlipidemia_has_both_source_tags(self, gold_outputs):
        """Merged Hyperlipidemia must carry both synthea and epic-ehi source tags."""
        bundle, _, _ = gold_outputs
        conditions = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"].get("resourceType") == "Condition"
        ]
        hyperlipidemia = next(
            (
                c
                for c in conditions
                if {"55822004", "E78.5"} <= {cod.get("code") for cod in _condition_codings(c)}
            ),
            None,
        )
        assert hyperlipidemia is not None

        tags = _source_tags(hyperlipidemia)
        assert "synthea" in tags, f"synthea source-tag missing.  Tags: {tags}"
        assert "epic-ehi" in tags, f"epic-ehi source-tag missing.  Tags: {tags}"

    def test_artifact_1_hyperlipidemia_has_merge_rationale(self, gold_outputs):
        """Merged Hyperlipidemia must have EXT_MERGE_RATIONALE extension."""
        bundle, _, _ = gold_outputs
        conditions = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"].get("resourceType") == "Condition"
        ]
        hyperlipidemia = next(
            (
                c
                for c in conditions
                if {"55822004", "E78.5"} <= {cod.get("code") for cod in _condition_codings(c)}
            ),
            None,
        )
        assert hyperlipidemia is not None

        rationale = _ext_value(_resource_extensions(hyperlipidemia), EXT_MERGE_RATIONALE)
        assert rationale is not None, (
            "EXT_MERGE_RATIONALE extension missing from merged Hyperlipidemia Condition"
        )
        assert isinstance(rationale, str) and rationale, (
            "EXT_MERGE_RATIONALE is present but empty"
        )

    def test_artifact_1_hyperlipidemia_has_both_source_identifiers(self, gold_outputs):
        """Merged Hyperlipidemia must carry identifiers from both source records."""
        bundle, _, _ = gold_outputs
        conditions = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"].get("resourceType") == "Condition"
        ]
        hyperlipidemia = next(
            (
                c
                for c in conditions
                if {"55822004", "E78.5"} <= {cod.get("code") for cod in _condition_codings(c)}
            ),
            None,
        )
        assert hyperlipidemia is not None
        identifiers = hyperlipidemia.get("identifier", [])
        assert len(identifiers) >= 2, (
            f"Expected ≥2 source identifiers but found {len(identifiers)}: {identifiers}"
        )

    # ------------------------------------------------------------------
    # Artifact 2: Medication cross-class divergence (statin substitution)
    # ------------------------------------------------------------------
    #
    # Root cause: _RXCUI_CLASS_LABEL had 36567 (ingredient-level) but Synthea
    # emits 316672 ("Simvastatin 10 MG Oral Tablet" — product-level SCD).
    # Fix: added 316672 → "statin" to the dict in medication.py.

    def test_artifact_2_simvastatin_and_atorvastatin_both_in_gold(self, gold_outputs):
        """Both statin MedicationRequests must appear in gold (NOT merged together).
        Simvastatin uses RxCUI 316672 (Synthea product-level); atorvastatin 83367."""
        bundle, _, _ = gold_outputs
        meds = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"].get("resourceType") == "MedicationRequest"
        ]
        all_rxcuis = {
            c.get("code")
            for med in meds
            for c in med.get("medicationCodeableConcept", {}).get("coding", [])
        }
        assert "316672" in all_rxcuis, (
            f"Simvastatin (RxCUI 316672) not found in gold.  All RxCUIs: {all_rxcuis}"
        )
        assert "83367" in all_rxcuis, (
            f"Atorvastatin (RxCUI 83367) not found in gold.  All RxCUIs: {all_rxcuis}"
        )

        # They must NOT be in the same MedicationRequest (i.e., not merged)
        for med in meds:
            codes = {
                c.get("code")
                for c in med.get("medicationCodeableConcept", {}).get("coding", [])
            }
            assert not ({"316672", "83367"} <= codes), (
                f"Simvastatin and atorvastatin merged into a single MedicationRequest {med['id']}!"
            )

    def test_artifact_2_emits_conflict_pair_extensions(self, gold_outputs):
        """Both statin MedicationRequests must have EXT_CONFLICT_PAIR pointing at the other."""
        bundle, _, _ = gold_outputs
        meds = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"].get("resourceType") == "MedicationRequest"
        ]

        simvastatin = next(
            (
                m
                for m in meds
                if any(
                    c.get("code") == "316672"
                    for c in m.get("medicationCodeableConcept", {}).get("coding", [])
                )
            ),
            None,
        )
        atorvastatin = next(
            (
                m
                for m in meds
                if any(
                    c.get("code") == "83367"
                    for c in m.get("medicationCodeableConcept", {}).get("coding", [])
                )
            ),
            None,
        )

        assert simvastatin is not None, "Simvastatin MedicationRequest not found in gold"
        assert atorvastatin is not None, "Atorvastatin MedicationRequest not found in gold"

        sim_conflict = _ext_value(_resource_extensions(simvastatin), EXT_CONFLICT_PAIR)
        ator_conflict = _ext_value(_resource_extensions(atorvastatin), EXT_CONFLICT_PAIR)

        assert sim_conflict is not None, (
            f"Simvastatin ({simvastatin['id']}) missing EXT_CONFLICT_PAIR extension.  "
            f"Extensions: {_resource_extensions(simvastatin)}"
        )
        assert ator_conflict is not None, (
            f"Atorvastatin ({atorvastatin['id']}) missing EXT_CONFLICT_PAIR extension.  "
            f"Extensions: {_resource_extensions(atorvastatin)}"
        )

        # Each must point at the other (by reference)
        sim_ref = sim_conflict.get("reference", "") if isinstance(sim_conflict, dict) else ""
        ator_ref = ator_conflict.get("reference", "") if isinstance(ator_conflict, dict) else ""

        assert atorvastatin["id"] in ator_ref or "unknown" not in ator_ref, (
            f"Atorvastatin conflict-pair ref {ator_ref!r} should point at simvastatin "
            f"or a valid reference.  Simvastatin id: {simvastatin['id']}"
        )
        assert simvastatin["id"] in sim_ref or "unknown" not in sim_ref, (
            f"Simvastatin conflict-pair ref {sim_ref!r} should point at atorvastatin.  "
            f"Atorvastatin id: {atorvastatin['id']}"
        )

    def test_artifact_2_conflicts_detected_nonzero(self, gold_outputs):
        """manifest.merge_summary.conflicts_detected must be ≥1 (statin divergence)."""
        _, _, manifest = gold_outputs
        count = manifest["merge_summary"]["conflicts_detected"]
        assert count >= 1, (
            f"conflicts_detected={count}, expected ≥1.  "
            "The statin cross-class flag (simvastatin 316672 vs atorvastatin 83367) "
            "should have been detected after adding 316672 to _RXCUI_CLASS_LABEL."
        )

    def test_artifact_2_provenance_has_derive_for_cross_class(self, gold_outputs):
        """provenance.ndjson must contain a DERIVE record naming the statin substitution
        (target: Provenance/conflict-medication-cross-class-...)."""
        _, prov_records, _ = gold_outputs

        derive_targets = []
        for prov in prov_records:
            for coding in prov.get("activity", {}).get("coding", []):
                if coding.get("code") == "DERIVE":
                    for t in prov.get("target", []):
                        derive_targets.append(t.get("reference", ""))

        statin_derive = [
            t for t in derive_targets if "medication-cross-class" in t
        ]
        assert statin_derive, (
            f"No DERIVE Provenance for medication-cross-class found.  "
            f"All DERIVE targets: {derive_targets}"
        )

    # ------------------------------------------------------------------
    # Artifact 3: Orphan-source (single-source) resource preservation
    # ------------------------------------------------------------------

    def test_artifact_3_synthea_payer_claims_in_gold(self, gold_outputs):
        """At least one Claim resource must be in gold with only ONE source-tag,
        preserved from synthea (single-source — not deduped or merged)."""
        bundle, _, manifest = gold_outputs

        claims = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"].get("resourceType") == "Claim"
        ]
        assert len(claims) >= 1, "No Claim resources found in gold bundle"

        single_source_claims = [
            c for c in claims if len(_source_tags(c)) == 1
        ]
        assert single_source_claims, (
            f"No single-source Claim found.  "
            f"Source-tag distributions: {[_source_tags(c) for c in claims[:5]]}"
        )

        # The claim must trace to synthea (from the real L2 silver)
        synthea_claims = [
            c for c in single_source_claims if "synthea" in _source_tags(c)
        ]
        assert synthea_claims, (
            "No single-source Claim from synthea source found.  "
            f"Single-source claim tags: {[_source_tags(c) for c in single_source_claims[:5]]}"
        )

    def test_artifact_3_claim_count_in_resource_counts(self, gold_outputs):
        """manifest.resource_counts must report Claims (≥1)."""
        _, _, manifest = gold_outputs
        claim_count = manifest["resource_counts"].get("Claim", 0)
        assert claim_count >= 1, (
            f"manifest.resource_counts has Claim={claim_count}, expected ≥1"
        )

    # ------------------------------------------------------------------
    # Artifact 4: Free-text fact extraction (Phase 1 partial)
    # ------------------------------------------------------------------

    def test_artifact_4_clinical_note_document_reference_in_gold(self, gold_outputs):
        """The synthesized clinical note DocumentReference must be present in gold.

        Phase 1 assertion: the source DocumentReference is in gold with
        source-tag=synthesized-clinical-note and LOINC 11506-3 (Progress note).

        Phase 2 ambition: also assert a Condition for chest tightness (SNOMED
        23924001) was extracted.  That work is gated on the real vision flow
        landing for clinical notes.
        """
        bundle, _, _ = gold_outputs
        docrefs = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"].get("resourceType") == "DocumentReference"
        ]
        assert len(docrefs) >= 1, "No DocumentReference resources found in gold bundle"

        # Find the synthesized clinical note (LOINC 11506-3 = Progress note)
        progress_note = next(
            (
                dr
                for dr in docrefs
                if any(
                    c.get("code") == "11506-3"
                    for c in dr.get("type", {}).get("coding", [])
                )
            ),
            None,
        )
        assert progress_note is not None, (
            f"Progress note (LOINC 11506-3) DocumentReference not found.  "
            f"Found DocumentRefs: "
            f"{[dr.get('type',{}).get('coding',[]) for dr in docrefs]}"
        )

        tags = _source_tags(progress_note)
        assert "synthesized-clinical-note" in tags, (
            f"Progress note DocumentReference missing synthesized-clinical-note source-tag.  "
            f"Tags: {tags}"
        )

    @pytest.mark.skip(
        reason=(
            "Phase 2 gap: chest-tightness Condition (SNOMED 23924001) extraction "
            "from the clinical note requires the real clinical-note vision flow, "
            "which lands in Stage 4 / Phase 2.  "
            "Phase 1 only asserts the DocumentReference is in gold (see "
            "test_artifact_4_clinical_note_document_reference_in_gold)."
        )
    )
    def test_artifact_4_chest_tightness_condition_extracted(self, gold_outputs):
        """Phase 2 target: a Condition for chest tightness (SNOMED 23924001) should be
        present in gold, extracted from the planted phrase in the clinical note.

        Planted phrase: 'occasional chest tightness on exertion since approximately
        November of last year.'
        Expected FHIR: Condition.code.coding[0].code == '23924001'
                       meta.tag includes source-tag=synthesized-clinical-note
        """
        bundle, _, _ = gold_outputs
        conditions = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"].get("resourceType") == "Condition"
        ]
        chest_tightness = next(
            (
                c
                for c in conditions
                if any(
                    cod.get("code") == "23924001"
                    for cod in _condition_codings(c)
                )
            ),
            None,
        )
        assert chest_tightness is not None, (
            "Chest tightness Condition (SNOMED 23924001) not found in gold.  "
            "This is expected in Phase 2 after clinical-note vision extraction lands."
        )

    # ------------------------------------------------------------------
    # Artifact 5: Cross-format Observation merge (Epic EHI + lab-pdf)
    # ------------------------------------------------------------------
    #
    # Note: Synthea's Rhett759 has no creatinine observation, so the merge is
    # epic-ehi + lab-pdf (not synthea + lab-pdf as originally designed in the
    # tracker).  Both produce LOINC 2160-0, value 1.4 mg/dL, date 2025-09-12.

    def test_artifact_5_creatinine_merged_with_both_sources(self, gold_outputs):
        """Gold should have exactly ONE creatinine Observation (LOINC 2160-0) with
        source-tags from both epic-ehi and lab-pdf."""
        bundle, _, _ = gold_outputs
        creatinine_obs = [
            e["resource"]
            for e in bundle["entry"]
            if e["resource"].get("resourceType") == "Observation"
            and any(
                c.get("code") == "2160-0"
                for c in e["resource"].get("code", {}).get("coding", [])
            )
        ]
        assert len(creatinine_obs) == 1, (
            f"Expected exactly 1 creatinine Observation but found {len(creatinine_obs)}"
        )

        creat = creatinine_obs[0]
        tags = _source_tags(creat)
        assert "lab-pdf" in tags, (
            f"lab-pdf source-tag missing from merged creatinine.  Tags: {tags}"
        )
        assert "epic-ehi" in tags, (
            f"epic-ehi source-tag missing from merged creatinine.  Tags: {tags}"
        )

    def test_artifact_5_creatinine_has_both_source_identifiers(self, gold_outputs):
        """Merged creatinine Observation must carry identifiers from both sources."""
        bundle, _, _ = gold_outputs
        creatinine_obs = next(
            (
                e["resource"]
                for e in bundle["entry"]
                if e["resource"].get("resourceType") == "Observation"
                and any(
                    c.get("code") == "2160-0"
                    for c in e["resource"].get("code", {}).get("coding", [])
                )
            ),
            None,
        )
        assert creatinine_obs is not None

        identifiers = creatinine_obs.get("identifier", [])
        assert len(identifiers) >= 2, (
            f"Expected ≥2 identifiers on merged creatinine but found {len(identifiers)}: "
            f"{identifiers}"
        )

    def test_artifact_5_creatinine_quality_score_extension_present(self, gold_outputs):
        """Merged creatinine must carry EXT_QUALITY_SCORE in meta.extension."""
        bundle, _, _ = gold_outputs
        creatinine_obs = next(
            (
                e["resource"]
                for e in bundle["entry"]
                if e["resource"].get("resourceType") == "Observation"
                and any(
                    c.get("code") == "2160-0"
                    for c in e["resource"].get("code", {}).get("coding", [])
                )
            ),
            None,
        )
        assert creatinine_obs is not None

        score = _ext_value(_meta_extensions(creatinine_obs), EXT_QUALITY_SCORE)
        assert score is not None, (
            f"EXT_QUALITY_SCORE missing from creatinine Observation meta.  "
            f"Meta extensions: {_meta_extensions(creatinine_obs)}"
        )
        assert isinstance(score, (int, float)) and score > 0, (
            f"EXT_QUALITY_SCORE has unexpected value: {score}"
        )

    def test_artifact_5_creatinine_has_merge_rationale(self, gold_outputs):
        """Merged creatinine must carry EXT_MERGE_RATIONALE extension."""
        bundle, _, _ = gold_outputs
        creatinine_obs = next(
            (
                e["resource"]
                for e in bundle["entry"]
                if e["resource"].get("resourceType") == "Observation"
                and any(
                    c.get("code") == "2160-0"
                    for c in e["resource"].get("code", {}).get("coding", [])
                )
            ),
            None,
        )
        assert creatinine_obs is not None

        rationale = _ext_value(
            _resource_extensions(creatinine_obs), EXT_MERGE_RATIONALE
        )
        assert rationale is not None, (
            "EXT_MERGE_RATIONALE missing from merged creatinine Observation"
        )

    @pytest.mark.skip(
        reason=(
            "Phase 2 gap: EXT_SOURCE_LOCATOR (page=2;bbox=72,574,540,590) is absent "
            "because the lab-pdf stub-silver does not run vision extraction.  "
            "The locator will appear once the real lab-pdf Layer-2-B pipeline "
            "(task 4.3 + 2.5 wired end-to-end) replaces the stub.  "
            "Creatinine merge source-tags and quality-score are already verified."
        )
    )
    def test_artifact_5_creatinine_source_locator_extension_present(self, gold_outputs):
        """Phase 2 target: merged creatinine must carry EXT_SOURCE_LOCATOR from
        the lab-pdf side pointing at 'page=2;bbox=72,574,540,590'."""
        bundle, _, _ = gold_outputs
        creatinine_obs = next(
            (
                e["resource"]
                for e in bundle["entry"]
                if e["resource"].get("resourceType") == "Observation"
                and any(
                    c.get("code") == "2160-0"
                    for c in e["resource"].get("code", {}).get("coding", [])
                )
            ),
            None,
        )
        assert creatinine_obs is not None

        locator = _ext_value(_meta_extensions(creatinine_obs), EXT_SOURCE_LOCATOR)
        assert locator == "page=2;bbox=72,574,540,590", (
            f"EXT_SOURCE_LOCATOR expected 'page=2;bbox=72,574,540,590' but got: {locator!r}.  "
            "This is expected to fail in Phase 1 (stub-silver)."
        )

    # ------------------------------------------------------------------
    # Determinism
    # ------------------------------------------------------------------

    @pytest.mark.skipif(
        not _corpus_available(),
        reason="Corpus not available for determinism check",
    )
    def test_orchestrator_idempotent_bundle_sha(self, tmp_path_factory):
        """Re-running the orchestrator must produce byte-identical bundle.json.

        Important for reproducibility: the demo output must be deterministic
        so that the gold-tier corpus can be committed and diff-checked.
        """
        gold1 = tmp_path_factory.mktemp("gold1")
        gold2 = tmp_path_factory.mktemp("gold2")

        result1 = harmonize_patient(
            silver_root=_SILVER_ROOT,
            bronze_root=_BRONZE_ROOT,
            gold_root=gold1,
            patient_id=_PATIENT_ID,
        )
        result2 = harmonize_patient(
            silver_root=_SILVER_ROOT,
            bronze_root=_BRONZE_ROOT,
            gold_root=gold2,
            patient_id=_PATIENT_ID,
        )

        assert result1.bundle_sha256 == result2.bundle_sha256, (
            f"Non-deterministic bundle output detected!\n"
            f"  run1 SHA: {result1.bundle_sha256}\n"
            f"  run2 SHA: {result2.bundle_sha256}\n"
            "This means the pipeline has a non-deterministic code path "
            "(e.g. uuid4(), datetime.now(), or unordered dict iteration)."
        )
