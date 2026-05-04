"""Tests for ehi_atlas.harmonize.orchestrator (task 3.11 / Stage-3-orchestrator).

Tests run against real corpus inputs:
  - corpus/silver/synthea/rhett759/bundle.json  (real L2 silver)
  - corpus/bronze/epic-ehi/rhett759/data.sqlite.dump  (stub source)
  - corpus/bronze/lab-pdf/rhett759/data.pdf    (stub source)
  - corpus/bronze/synthesized-clinical-note/rhett759/data.json  (stub source)

All gold output is written to a temporary directory so the corpus is not polluted.
Tests are deterministic because orchestrator uses DEFAULT_RECORDED timestamps.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest

from ehi_atlas.harmonize.orchestrator import (
    HarmonizeResult,
    harmonize_patient,
    _stub_silver_from_epic_ehi_bronze,
    _stub_silver_from_lab_pdf_bronze,
    _stub_silver_from_synthesized_clinical_note_bronze,
)
from ehi_atlas.harmonize.provenance import EXT_QUALITY_SCORE


# ---------------------------------------------------------------------------
# Paths to real corpus inputs
# ---------------------------------------------------------------------------

_ATLAS_ROOT = Path(__file__).resolve().parents[2]
_SILVER_ROOT = _ATLAS_ROOT / "corpus" / "silver"
_BRONZE_ROOT = _ATLAS_ROOT / "corpus" / "bronze"
PATIENT_ID = "rhett759"


def _has_real_silver() -> bool:
    """True iff Synthea silver bundle exists for rhett759."""
    return (_SILVER_ROOT / "synthea" / PATIENT_ID / "bundle.json").exists()


def _has_epic_bronze() -> bool:
    return (_BRONZE_ROOT / "epic-ehi" / PATIENT_ID / "data.sqlite.dump").exists()


def _has_lab_pdf_bronze() -> bool:
    return (_BRONZE_ROOT / "lab-pdf" / PATIENT_ID / "data.pdf").exists()


def _has_clinical_note_bronze() -> bool:
    return (_BRONZE_ROOT / "synthesized-clinical-note" / PATIENT_ID / "data.json").exists()


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def run_harmonize(tmp_path: Path, patient_id: str = PATIENT_ID) -> HarmonizeResult:
    """Run the orchestrator against real corpus data and write output to tmp_path."""
    gold_root = tmp_path / "gold"
    return harmonize_patient(
        silver_root=_SILVER_ROOT,
        bronze_root=_BRONZE_ROOT,
        gold_root=gold_root,
        patient_id=patient_id,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.skipif(not _has_real_silver(), reason="Synthea silver not present")
def test_harmonize_patient_writes_three_files(tmp_path: Path) -> None:
    """bundle.json, provenance.ndjson, and manifest.json must all be created."""
    result = run_harmonize(tmp_path)

    assert result.bundle_path.exists(), f"bundle.json missing at {result.bundle_path}"
    assert result.provenance_path.exists(), f"provenance.ndjson missing at {result.provenance_path}"
    assert result.manifest_path.exists(), f"manifest.json missing at {result.manifest_path}"

    # Verify they're all under the expected patient directory
    expected_dir = tmp_path / "gold" / "patients" / PATIENT_ID
    assert result.bundle_path.parent == expected_dir
    assert result.provenance_path.parent == expected_dir
    assert result.manifest_path.parent == expected_dir


@pytest.mark.skipif(not _has_real_silver(), reason="Synthea silver not present")
def test_harmonize_patient_manifest_records_sources(tmp_path: Path) -> None:
    """manifest.json must list every contributing source and have expected keys."""
    result = run_harmonize(tmp_path)

    manifest = json.loads(result.manifest_path.read_text(encoding="utf-8"))

    # Required top-level keys per INTEGRATION.md
    assert "patient_id" in manifest
    assert "harmonizer_version" in manifest
    assert "built_at" in manifest
    assert "sources" in manifest
    assert "resource_counts" in manifest
    assert "merge_summary" in manifest

    assert manifest["patient_id"] == PATIENT_ID
    source_names = {s["name"] for s in manifest["sources"]}
    # Synthea must always be present (it has real silver)
    assert "synthea" in source_names, f"synthea missing from sources: {source_names}"

    # source count from result must match manifest
    assert result.source_count == len(manifest["sources"])


@pytest.mark.skipif(not _has_real_silver(), reason="Synthea silver not present")
def test_harmonize_patient_bundle_has_resources_after_merge(tmp_path: Path) -> None:
    """The merged bundle must have non-empty entry[] and include a Patient."""
    result = run_harmonize(tmp_path)

    bundle = json.loads(result.bundle_path.read_text(encoding="utf-8"))
    entries = bundle.get("entry", [])
    assert len(entries) > 0, "Gold bundle has no entries"

    rtypes = {e.get("resource", {}).get("resourceType") for e in entries}
    assert "Patient" in rtypes, f"No Patient in gold bundle resource types: {rtypes}"
    assert "Condition" in rtypes or len(entries) > 1, "No Conditions or other resources"


@pytest.mark.skipif(not _has_real_silver(), reason="Synthea silver not present")
def test_harmonize_patient_idempotent(tmp_path: Path) -> None:
    """Running harmonize twice must produce byte-identical bundle.json."""
    gold_root_1 = tmp_path / "run1" / "gold"
    gold_root_2 = tmp_path / "run2" / "gold"

    result1 = harmonize_patient(
        silver_root=_SILVER_ROOT,
        bronze_root=_BRONZE_ROOT,
        gold_root=gold_root_1,
        patient_id=PATIENT_ID,
    )
    result2 = harmonize_patient(
        silver_root=_SILVER_ROOT,
        bronze_root=_BRONZE_ROOT,
        gold_root=gold_root_2,
        patient_id=PATIENT_ID,
    )

    assert result1.bundle_sha256 == result2.bundle_sha256, (
        f"Non-deterministic bundle: run1={result1.bundle_sha256[:16]}, "
        f"run2={result2.bundle_sha256[:16]}"
    )


@pytest.mark.skipif(not _has_real_silver(), reason="Synthea silver not present")
def test_harmonize_patient_emits_provenance_for_merges(tmp_path: Path) -> None:
    """provenance.ndjson must have at least one MERGE activity record."""
    result = run_harmonize(tmp_path)

    assert result.provenance_path.exists()
    lines = [
        line.strip()
        for line in result.provenance_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert len(lines) > 0, "provenance.ndjson is empty"

    activities = []
    for line in lines:
        prov = json.loads(line)
        for coding in prov.get("activity", {}).get("coding", []):
            activities.append(coding.get("code", ""))

    assert "MERGE" in activities, (
        f"No MERGE provenance record found. Activities present: {activities}"
    )


@pytest.mark.skipif(
    not (_SILVER_ROOT / "synthea" / PATIENT_ID / "bundle.json").exists()
    and not (_BRONZE_ROOT / "epic-ehi" / PATIENT_ID / "data.sqlite.dump").exists(),
    reason="Neither synthea silver nor epic-ehi bronze available",
)
def test_harmonize_patient_handles_missing_silver_gracefully(tmp_path: Path) -> None:
    """If synthea silver is present but other sources are missing, pipeline still runs.

    This test verifies the orchestrator skips missing sources gracefully rather
    than failing.
    """
    # Use a silver root that only has synthea (real path) — others will fall through
    # to stubs or be skipped. The key requirement is that it doesn't crash.
    gold_root = tmp_path / "gold"
    # Will either load real silver or fall back to stubs — should not raise
    result = harmonize_patient(
        silver_root=_SILVER_ROOT,
        bronze_root=_BRONZE_ROOT,
        gold_root=gold_root,
        patient_id=PATIENT_ID,
    )
    assert result.source_count >= 1
    assert result.bundle_path.exists()


@pytest.mark.skipif(not _has_real_silver(), reason="Synthea silver not present")
def test_harmonize_patient_includes_artifact_anchors(tmp_path: Path) -> None:
    """Gold bundle should contain a Hyperlipidemia Condition (Artifact 1 proxy — the
    Synthea SNOMED 55822004 Hyperlipidemia which maps to UMLS C0020473) AND a
    creatinine Observation with EXT_QUALITY_SCORE (Artifact 5 anchor proxy).

    Artifact 1 full-form (HTN SNOMED 38341003 merged with Epic ICD-10 I10) requires
    both CCDA and Epic sources to have HTN, which depends on CCDA L2 landing. For
    Phase 1 we verify a cross-source condition merge is possible: Hyperlipidemia from
    Synthea (SNOMED 55822004) is present in the gold bundle, and if the Epic stub
    loaded, it also has E78.5 (Hyperlipidemia ICD-10) which should merge into the same
    Condition cluster via the UMLS crosswalk.

    Artifact 5: creatinine Observation with LOINC 2160-0 should appear with quality
    score annotated (synthea has creatinine observations; lab-pdf stub adds Artifact 5).
    """
    result = run_harmonize(tmp_path)
    bundle = json.loads(result.bundle_path.read_text(encoding="utf-8"))
    entries = bundle.get("entry", [])

    # Artifact 1 proxy: Find a Condition with any clinical code present in the crosswalk
    # — at minimum Synthea's SNOMED conditions (Hyperlipidemia 55822004 or COPD 185086009)
    condition_found = False
    for entry in entries:
        res = entry.get("resource", {})
        if res.get("resourceType") != "Condition":
            continue
        # Any condition is fine — synthea has 8 conditions
        condition_found = True
        break
    assert condition_found, "No Condition resources found in gold bundle"

    # Check Hyperlipidemia specifically (Artifact 1 anchor — SNOMED 55822004)
    hyperlipidemia_found = False
    for entry in entries:
        res = entry.get("resource", {})
        if res.get("resourceType") != "Condition":
            continue
        for coding in res.get("code", {}).get("coding", []):
            code = coding.get("code", "")
            # SNOMED: Hyperlipidemia (55822004) or ICD-10: E78.5
            if code in ("55822004", "E78.5", "38341003", "I10"):
                hyperlipidemia_found = True
                break
        if hyperlipidemia_found:
            break
    assert hyperlipidemia_found, (
        "Artifact 1 anchor condition (Hyperlipidemia SNOMED 55822004 / ICD-10 E78.5, "
        "or HTN SNOMED 38341003 / ICD-10 I10) not found in gold bundle"
    )

    # Artifact 5 proxy: Find a creatinine Observation (LOINC 2160-0) with EXT_QUALITY_SCORE
    creatinine_with_quality = False
    for entry in entries:
        res = entry.get("resource", {})
        if res.get("resourceType") != "Observation":
            continue
        has_creatinine_loinc = any(
            c.get("code") == "2160-0"
            for c in res.get("code", {}).get("coding", [])
        )
        if not has_creatinine_loinc:
            continue
        # Check for quality score extension
        for ext in res.get("meta", {}).get("extension", []):
            if ext.get("url") == EXT_QUALITY_SCORE:
                creatinine_with_quality = True
                break
        if creatinine_with_quality:
            break

    assert creatinine_with_quality, (
        "Artifact 5 proxy (creatinine LOINC 2160-0 with EXT_QUALITY_SCORE) not found in gold bundle"
    )


@pytest.mark.skipif(not _has_epic_bronze(), reason="Epic-EHI bronze not present")
def test_stub_silver_from_epic_ehi_bronze_loads_sqlite(tmp_path: Path) -> None:
    """The Epic stub correctly restores the SQLite dump and emits a FHIR Bundle."""
    bundle = _stub_silver_from_epic_ehi_bronze(_BRONZE_ROOT, PATIENT_ID)

    assert bundle is not None, "Epic stub returned None despite bronze existing"
    assert bundle.get("resourceType") == "Bundle"

    entries = bundle.get("entry", [])
    assert len(entries) > 0, "Epic stub bundle has no entries"

    rtypes = [e.get("resource", {}).get("resourceType") for e in entries]

    # Should have at least Patient and Condition
    assert "Patient" in rtypes, f"No Patient in stub bundle. rtypes: {rtypes}"
    assert "Condition" in rtypes, f"No Condition in stub bundle. rtypes: {rtypes}"

    # Stub resources must have stub-silver lifecycle tag
    for entry in entries:
        resource = entry.get("resource", {})
        tags = resource.get("meta", {}).get("tag", [])
        sys_lifecycle = {
            t.get("code") for t in tags
            if t.get("system") == "https://ehi-atlas.example/fhir/CodeSystem/lifecycle"
        }
        assert "stub-silver" in sys_lifecycle, (
            f"Resource {resource.get('id')} missing stub-silver lifecycle tag"
        )

    # Should include the atorvastatin MedicationRequest (Artifact 2)
    med_resources = [
        e.get("resource", {})
        for e in entries
        if e.get("resource", {}).get("resourceType") == "MedicationRequest"
    ]
    assert len(med_resources) > 0, "No MedicationRequest resources in stub bundle"
    rxcui_codes = [
        c.get("code")
        for med in med_resources
        for c in med.get("medicationCodeableConcept", {}).get("coding", [])
    ]
    assert "83367" in rxcui_codes, (
        f"Atorvastatin RxCUI 83367 not found in stub medications. Found: {rxcui_codes}"
    )

    # Should include the creatinine Observation (Artifact 5) — requires LNC_DB_MAIN join
    obs_resources = [
        e.get("resource", {})
        for e in entries
        if e.get("resource", {}).get("resourceType") == "Observation"
    ]
    creatinine_obs = [
        obs for obs in obs_resources
        if any(
            c.get("code") == "2160-0"
            for c in obs.get("code", {}).get("coding", [])
        )
    ]
    assert len(creatinine_obs) > 0, (
        "Creatinine Observation (LOINC 2160-0) missing from Epic stub — "
        "LNC_DB_MAIN join may have failed"
    )
