"""Tests for the Epic EHI adapter (Layer 1, task 2.3).

Covers both Flow A (josh-fixture, parser validation) and Flow B (rhett759,
Synthea → Epic-EHI projection), including the three showcase artifact anchors.

Tests use the real source files (josh dump + Rhett759 Synthea bundle) via
pytest fixtures that are skipped when the source files are absent.
"""

from __future__ import annotations

import json
import shutil
import sqlite3
from pathlib import Path

import pytest

from ehi_atlas.adapters.epic_ehi import (
    ACQUISITION_TS,
    EpicEhiAdapter,
    _ATORVASTATIN_RXCUI,
    _CREATININE_DATE,
    _CREATININE_LOINC,
    _CREATININE_VALUE,
)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_ATLAS_ROOT = Path(__file__).resolve().parent.parent.parent
_SOURCES_ROOT = _ATLAS_ROOT / "corpus" / "_sources"
_JOSH_DUMP = _SOURCES_ROOT / "josh-epic-ehi" / "raw" / "db.sqlite.dump"
_RHETT_BUNDLE = (
    _SOURCES_ROOT
    / "synthea"
    / "raw"
    / "Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61.json"
)

# Skip markers
_JOSH_MISSING = pytest.mark.skipif(
    not _JOSH_DUMP.exists(), reason="Josh Epic dump not found; run corpus acquisition"
)
_RHETT_MISSING = pytest.mark.skipif(
    not _RHETT_BUNDLE.exists(), reason="Rhett759 bundle not found; run corpus acquisition"
)
_BOTH_MISSING = pytest.mark.skipif(
    not (_JOSH_DUMP.exists() or _RHETT_BUNDLE.exists()),
    reason="Neither source file found",
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_adapter(tmp_path: Path) -> EpicEhiAdapter:
    """Instantiate EpicEhiAdapter with a tmp bronze root."""
    return EpicEhiAdapter(
        source_root=_SOURCES_ROOT / "josh-epic-ehi" / "raw",
        bronze_root=tmp_path / "bronze" / "epic-ehi",
    )


def _restore_dump(dump_path: Path) -> sqlite3.Connection:
    """Restore a .sqlite.dump to an in-memory Connection."""
    conn = sqlite3.connect(":memory:")
    conn.executescript(dump_path.read_text(encoding="utf-8"))
    return conn


def _get_tables(conn: sqlite3.Connection) -> set[str]:
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
    return {row[0] for row in cursor.fetchall()}


# ---------------------------------------------------------------------------
# Test 1: list_patients includes both flows
# ---------------------------------------------------------------------------


def test_list_patients_includes_both_flows(tmp_path: Path) -> None:
    """list_patients() returns the patients whose source files exist."""
    adapter = _make_adapter(tmp_path)
    patients = adapter.list_patients()

    # At least the flows whose inputs exist should be listed
    if _JOSH_DUMP.exists():
        assert "josh-fixture" in patients, "josh-fixture should be listed when dump exists"
    if _RHETT_BUNDLE.exists():
        assert "rhett759" in patients, "rhett759 should be listed when bundle exists"

    # Returned list should be sorted
    assert patients == sorted(patients)


# ---------------------------------------------------------------------------
# Test 2: josh-fixture ingest produces bronze with dump
# ---------------------------------------------------------------------------


@_JOSH_MISSING
def test_ingest_josh_fixture_produces_bronze_with_dump(tmp_path: Path) -> None:
    """Flow A: ingest('josh-fixture') writes data.sqlite.dump + metadata.json."""
    adapter = _make_adapter(tmp_path)
    meta = adapter.ingest("josh-fixture")

    bronze_dir = adapter.bronze_dir("josh-fixture")
    dump_path = bronze_dir / "data.sqlite.dump"
    meta_path = bronze_dir / "metadata.json"

    # Files exist
    assert dump_path.exists(), "data.sqlite.dump should exist"
    assert meta_path.exists(), "metadata.json should exist"

    # Metadata fields
    assert meta.source == "epic-ehi"
    assert meta.patient_id == "josh-fixture"
    assert meta.fetched_at == ACQUISITION_TS
    assert meta.consent == "open"
    assert meta.document_type == "epic-ehi-export-sqlite"
    assert len(meta.sha256) == 64

    # Dump should be non-empty SQL text
    dump_text = dump_path.read_text(encoding="utf-8")
    assert "CREATE TABLE" in dump_text or "BEGIN TRANSACTION" in dump_text

    # Validate returns no errors
    errors = adapter.validate("josh-fixture")
    assert errors == [], f"Validation errors: {errors}"


# ---------------------------------------------------------------------------
# Test 3: rhett759 projection includes required tables
# ---------------------------------------------------------------------------


@_RHETT_MISSING
def test_ingest_rhett759_projection_includes_required_tables(tmp_path: Path) -> None:
    """Flow B: rhett759 dump restores with all 6 required Epic-shape tables."""
    adapter = _make_adapter(tmp_path)
    meta = adapter.ingest("rhett759")

    bronze_dir = adapter.bronze_dir("rhett759")
    dump_path = bronze_dir / "data.sqlite.dump"

    assert dump_path.exists(), "data.sqlite.dump should exist for rhett759"
    assert meta.consent == "constructed"

    conn = _restore_dump(dump_path)
    tables = _get_tables(conn)
    conn.close()

    required = {
        "PAT_PATIENT",
        "PAT_ENC",
        "PROBLEM_LIST",
        "ORDER_MED",
        "ORDER_RESULTS",
        "LNC_DB_MAIN",
    }
    missing = required - tables
    assert not missing, f"Tables missing from rhett759 dump: {sorted(missing)}"

    # Sanity row counts
    conn = _restore_dump(dump_path)
    assert conn.execute("SELECT COUNT(*) FROM PAT_PATIENT").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM PAT_ENC").fetchone()[0] >= 1
    assert conn.execute("SELECT COUNT(*) FROM PROBLEM_LIST").fetchone()[0] >= 1
    assert conn.execute("SELECT COUNT(*) FROM ORDER_RESULTS").fetchone()[0] >= 1
    assert conn.execute("SELECT COUNT(*) FROM LNC_DB_MAIN").fetchone()[0] >= 1
    conn.close()


# ---------------------------------------------------------------------------
# Test 4: Artifact 2 anchor — atorvastatin discontinued Q3 2025
# ---------------------------------------------------------------------------


@_RHETT_MISSING
def test_ingest_rhett759_projection_anchors_artifact_2(tmp_path: Path) -> None:
    """Artifact 2: ORDER_MED has atorvastatin row that is discontinued in Q3 2025."""
    adapter = _make_adapter(tmp_path)
    adapter.ingest("rhett759")

    dump_path = adapter.bronze_dir("rhett759") / "data.sqlite.dump"
    conn = _restore_dump(dump_path)

    # Query for atorvastatin row
    rows = conn.execute(
        """
        SELECT RXNORM_CODE, MED_DISPLAY, ORDER_STATUS_C_NAME, END_DATE
        FROM ORDER_MED
        WHERE RXNORM_CODE = ? OR LOWER(MED_DISPLAY) LIKE '%atorvastatin%'
        """,
        (_ATORVASTATIN_RXCUI,),
    ).fetchall()
    conn.close()

    assert len(rows) >= 1, "Expected at least one atorvastatin row in ORDER_MED"

    atorva_row = rows[0]
    rxcui, display, status, end_date = atorva_row

    assert rxcui == _ATORVASTATIN_RXCUI, f"Expected RxCUI {_ATORVASTATIN_RXCUI}, got {rxcui}"
    assert status == "Discontinued", f"Expected status=Discontinued, got {status!r}"

    # End date should be in Q3 2025 (July–September 2025)
    assert end_date, "END_DATE should be set for discontinued atorvastatin"
    assert end_date.startswith("2025-0") or end_date.startswith("2025-1"), (
        f"END_DATE {end_date!r} should be in 2025"
    )
    year, month = end_date[:7].split("-")
    assert int(month) in (7, 8, 9), f"Q3 2025 = months 7-9; got month {month}"

    # Verify simvastatin is NOT present (should have been swapped)
    conn2 = _restore_dump(dump_path)
    simva_rows = conn2.execute(
        "SELECT COUNT(*) FROM ORDER_MED WHERE RXNORM_CODE = '36567' OR LOWER(MED_DISPLAY) LIKE '%simvastatin%'"
    ).fetchone()[0]
    conn2.close()
    assert simva_rows == 0, f"Simvastatin should have been swapped out; found {simva_rows} rows"


# ---------------------------------------------------------------------------
# Test 5: Artifact 5 anchor — creatinine 1.4 mg/dL on 2025-09-12
# ---------------------------------------------------------------------------


@_RHETT_MISSING
def test_ingest_rhett759_projection_anchors_artifact_5(tmp_path: Path) -> None:
    """Artifact 5: creatinine 1.4 mg/dL on 2025-09-12 via ORDER_RESULTS + LNC_DB_MAIN join."""
    adapter = _make_adapter(tmp_path)
    adapter.ingest("rhett759")

    dump_path = adapter.bronze_dir("rhett759") / "data.sqlite.dump"
    conn = _restore_dump(dump_path)

    # Verify COMPON_LNC_ID is NULL on ORDER_RESULTS (per INSPECTION finding)
    null_loinc_rows = conn.execute(
        "SELECT COUNT(*) FROM ORDER_RESULTS WHERE COMPON_LNC_ID IS NULL"
    ).fetchone()[0]
    total_rows = conn.execute("SELECT COUNT(*) FROM ORDER_RESULTS").fetchone()[0]
    assert null_loinc_rows == total_rows, (
        "All ORDER_RESULTS rows should have NULL COMPON_LNC_ID "
        "(LOINC resolved via LNC_DB_MAIN join)"
    )

    # The creatinine result should be found via the LNC_DB_MAIN join
    creatinine_rows = conn.execute(
        """
        SELECT r.RESULT_DATE, r.ORD_VALUE, r.REFERENCE_UNIT, l.LNC_CODE
        FROM ORDER_RESULTS r
        JOIN LNC_DB_MAIN l ON r.COMPONENT_ID = l.COMPONENT_ID
        WHERE l.LNC_CODE = ?
        """,
        (_CREATININE_LOINC,),
    ).fetchall()
    conn.close()

    assert len(creatinine_rows) >= 1, (
        f"Expected creatinine row with LOINC {_CREATININE_LOINC} via LNC_DB_MAIN join"
    )

    result_date, ord_value, unit, lnc_code = creatinine_rows[0]
    assert result_date == _CREATININE_DATE, (
        f"Creatinine date should be {_CREATININE_DATE}, got {result_date!r}"
    )
    assert float(ord_value) == _CREATININE_VALUE, (
        f"Creatinine value should be {_CREATININE_VALUE} mg/dL, got {ord_value!r}"
    )
    assert lnc_code == _CREATININE_LOINC, f"LOINC code mismatch: {lnc_code!r}"


# ---------------------------------------------------------------------------
# Test 6: Idempotency — two runs produce byte-identical dumps
# ---------------------------------------------------------------------------


@_RHETT_MISSING
def test_ingest_is_idempotent(tmp_path: Path) -> None:
    """Running ingest() twice on rhett759 produces byte-identical dumps."""
    adapter = _make_adapter(tmp_path)

    meta1 = adapter.ingest("rhett759")
    dump1 = (adapter.bronze_dir("rhett759") / "data.sqlite.dump").read_bytes()

    meta2 = adapter.ingest("rhett759")
    dump2 = (adapter.bronze_dir("rhett759") / "data.sqlite.dump").read_bytes()

    assert meta1.sha256 == meta2.sha256, (
        "SHA-256 should be identical across runs (idempotency)"
    )
    assert dump1 == dump2, "Raw dump bytes should be identical across runs"


# ---------------------------------------------------------------------------
# Test 7: Unknown patient raises ValueError
# ---------------------------------------------------------------------------


def test_ingest_unknown_patient_raises(tmp_path: Path) -> None:
    """ingest() raises ValueError for an unknown patient_id."""
    adapter = _make_adapter(tmp_path)
    with pytest.raises(ValueError, match="Unknown Epic EHI patient"):
        adapter.ingest("unknown-patient-xyz")


# ---------------------------------------------------------------------------
# Test 8: validate() on missing bronze returns errors
# ---------------------------------------------------------------------------


def test_validate_missing_bronze_returns_errors(tmp_path: Path) -> None:
    """validate() returns a non-empty error list when bronze record is absent."""
    adapter = _make_adapter(tmp_path)
    errors = adapter.validate("josh-fixture")
    assert len(errors) > 0, "Should report errors when bronze record is absent"
    assert any("missing" in e.lower() for e in errors)


# ---------------------------------------------------------------------------
# Test 9: Artifact 1 anchor — PROBLEM_LIST has ICD-10 codes, no SNOMED
# ---------------------------------------------------------------------------


@_RHETT_MISSING
def test_ingest_rhett759_projection_anchors_artifact_1(tmp_path: Path) -> None:
    """Artifact 1: PROBLEM_LIST uses ICD-10 codes only (no SNOMED coding)."""
    adapter = _make_adapter(tmp_path)
    adapter.ingest("rhett759")

    dump_path = adapter.bronze_dir("rhett759") / "data.sqlite.dump"
    conn = _restore_dump(dump_path)

    # PROBLEM_LIST should have at least one row
    rows = conn.execute(
        "SELECT PROBLEM_LIST_ID, DX_NAME, ICD10_CODE FROM PROBLEM_LIST"
    ).fetchall()
    conn.close()

    assert len(rows) >= 1, "PROBLEM_LIST should have at least one condition"

    # At least some conditions should have ICD-10 codes resolved from crosswalk
    icd10_coded = [r for r in rows if r[2] and r[2].strip()]
    assert len(icd10_coded) >= 1, (
        "At least one PROBLEM_LIST row should have an ICD-10 code "
        "(resolved via handcrafted crosswalk)"
    )

    # No SNOMED codes should appear in any column (ICD-10 codes are alphanumeric like E78.5)
    # SNOMED codes are pure numeric 6-9 digit strings
    for prob_id, dx_name, icd10_code in rows:
        if icd10_code:
            # ICD-10 codes start with a letter (e.g. E78.5, J44.1, C34.10, D64.9)
            assert icd10_code[0].isalpha() or icd10_code == "", (
                f"ICD-10 code should start with a letter, got {icd10_code!r} for {dx_name}"
            )
