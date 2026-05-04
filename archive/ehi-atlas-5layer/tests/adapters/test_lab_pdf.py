"""Tests for the Lab PDF Layer-1 adapter.

Integration tests use the actual synthesized lab PDF at:
  corpus/_sources/synthesized-lab-pdf/raw/lab-report-2025-09-12-quest.pdf

This is a 3-page Quest-style CMP (9.6 KB) generated deterministically by
generator.py. It is small enough to include in direct test I/O without
copying into a separate fixtures dir.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest

from ehi_atlas.adapters.base import SourceMetadata
from ehi_atlas.adapters.lab_pdf import ACQUISITION_TS, LabPDFAdapter

# ---------------------------------------------------------------------------
# Path to the actual synthesized PDF (used for integration tests)
# ---------------------------------------------------------------------------

ATLAS_ROOT = Path(__file__).resolve().parent.parent.parent
REAL_PDF = (
    ATLAS_ROOT
    / "corpus"
    / "_sources"
    / "synthesized-lab-pdf"
    / "raw"
    / "lab-report-2025-09-12-quest.pdf"
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def make_adapter(
    tmp_path: Path,
    *,
    copy_real_pdf: bool = True,
    patient_id: str = "rhett759",
) -> LabPDFAdapter:
    """Build a LabPDFAdapter pointing at a tmp corpus layout.

    Uses the canonical synthesized-lab-pdf directory name (not "lab-pdf") so
    that the CLI path-remap logic in LabPDFAdapter.__init__ does not trigger
    during tests.  This mirrors the layout used by scripts/stage-bronze.py.

    If copy_real_pdf is True, copies the actual synthesized PDF into
    source_root so that ingest() can run end-to-end.
    """
    # Use the canonical source dir name ("synthesized-lab-pdf") to avoid
    # triggering the CLI remap that converts "lab-pdf/raw" → "synthesized-lab-pdf/raw".
    source_root = tmp_path / "_sources" / "synthesized-lab-pdf" / "raw"
    bronze_root = tmp_path / "bronze" / "lab-pdf"
    source_root.mkdir(parents=True, exist_ok=True)
    bronze_root.mkdir(parents=True, exist_ok=True)

    if copy_real_pdf:
        filename = LabPDFAdapter.PATIENT_FILE_MAP[patient_id]
        shutil.copyfile(REAL_PDF, source_root / filename)

    return LabPDFAdapter(source_root=source_root, bronze_root=bronze_root)


# ---------------------------------------------------------------------------
# Test 1: list_patients returns known patients when file exists
# ---------------------------------------------------------------------------


def test_list_patients_returns_known_patients(tmp_path: Path) -> None:
    """list_patients() returns rhett759 when its file is present."""
    adapter = make_adapter(tmp_path, copy_real_pdf=True)
    patients = adapter.list_patients()
    assert patients == ["rhett759"], f"Expected ['rhett759'], got {patients}"


def test_list_patients_excludes_missing_files(tmp_path: Path) -> None:
    """list_patients() returns [] when no source PDF is on disk."""
    adapter = make_adapter(tmp_path, copy_real_pdf=False)
    assert adapter.list_patients() == []


# ---------------------------------------------------------------------------
# Test 2: ingest writes bronze PDF byte-identical to source
# ---------------------------------------------------------------------------


def test_ingest_writes_bronze_pdf_byte_identical(tmp_path: Path) -> None:
    """bronze/<patient>/data.pdf is byte-identical to the source PDF."""
    adapter = make_adapter(tmp_path)
    adapter.ingest("rhett759")

    bronze_pdf = adapter.bronze_dir("rhett759") / "data.pdf"
    assert bronze_pdf.exists(), "data.pdf not written to bronze"

    source_pdf = adapter.source_root / LabPDFAdapter.PATIENT_FILE_MAP["rhett759"]
    assert bronze_pdf.read_bytes() == source_pdf.read_bytes(), (
        "bronze data.pdf is not byte-identical to source PDF"
    )


# ---------------------------------------------------------------------------
# Test 3: ingest writes pages/ with one PNG and JSON per page (3-page PDF)
# ---------------------------------------------------------------------------


def test_ingest_writes_pages_directory_with_one_png_and_json_per_page(
    tmp_path: Path,
) -> None:
    """For the 3-page synthesized PDF, pages/ contains 001-003 PNG+JSON pairs."""
    adapter = make_adapter(tmp_path)
    adapter.ingest("rhett759")

    pages_dir = adapter.bronze_dir("rhett759") / "pages"
    assert pages_dir.exists(), "pages/ directory not created"

    expected_files = [
        "001.png",
        "001.text.json",
        "002.png",
        "002.text.json",
        "003.png",
        "003.text.json",
    ]
    for fname in expected_files:
        fpath = pages_dir / fname
        assert fpath.exists(), f"pages/{fname} missing"
        assert fpath.stat().st_size > 0, f"pages/{fname} is empty"

    # No extra files beyond the expected pairs
    actual_names = sorted(p.name for p in pages_dir.iterdir())
    assert actual_names == sorted(expected_files), (
        f"Unexpected files in pages/: {actual_names}"
    )


# ---------------------------------------------------------------------------
# Test 4: ingest writes valid metadata.json
# ---------------------------------------------------------------------------


def test_ingest_writes_valid_metadata_json(tmp_path: Path) -> None:
    """metadata.json parses as SourceMetadata with all required fields correct."""
    adapter = make_adapter(tmp_path)
    returned_meta = adapter.ingest("rhett759")

    meta_path = adapter.bronze_dir("rhett759") / "metadata.json"
    assert meta_path.exists(), "metadata.json not written"

    raw = json.loads(meta_path.read_text())
    parsed = SourceMetadata(**raw)

    assert parsed.source == "lab-pdf"
    assert parsed.patient_id == "rhett759"
    assert parsed.fetched_at == ACQUISITION_TS
    assert parsed.document_type == "lab-report-pdf"
    assert parsed.license == "MIT"
    assert parsed.consent == "constructed"
    assert len(parsed.sha256) == 64, "sha256 should be 64-char hex"
    assert parsed.notes is not None and "Creatinine" in parsed.notes, (
        "notes should mention Creatinine bbox"
    )

    # sha256 on disk matches sha256 of bronze data.pdf
    bronze_pdf = adapter.bronze_dir("rhett759") / "data.pdf"
    direct_hash = hashlib.sha256(bronze_pdf.read_bytes()).hexdigest()
    assert parsed.sha256 == direct_hash, (
        f"metadata sha256 {parsed.sha256} != direct hash {direct_hash}"
    )

    # Returned metadata matches what was written to disk
    assert returned_meta.sha256 == parsed.sha256


# ---------------------------------------------------------------------------
# Test 5: ingest is idempotent — same sha256 on second run
# ---------------------------------------------------------------------------


def test_ingest_is_idempotent_on_pdf(tmp_path: Path) -> None:
    """Running ingest() twice produces byte-identical bronze data.pdf."""
    adapter = make_adapter(tmp_path)

    meta1 = adapter.ingest("rhett759")
    meta2 = adapter.ingest("rhett759")

    assert meta1.sha256 == meta2.sha256, (
        f"sha256 changed between runs: {meta1.sha256} != {meta2.sha256}"
    )

    # Also verify the file bytes are identical
    pdf_path = adapter.bronze_dir("rhett759") / "data.pdf"
    direct_hash = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
    assert direct_hash == meta2.sha256


# ---------------------------------------------------------------------------
# Test 6: validate returns [] for a valid record
# ---------------------------------------------------------------------------


def test_validate_returns_empty_for_valid_record(tmp_path: Path) -> None:
    """After ingest(), validate() returns [] (no errors)."""
    adapter = make_adapter(tmp_path)
    adapter.ingest("rhett759")

    errors = adapter.validate("rhett759")
    assert errors == [], f"Expected no validation errors, got: {errors}"


# ---------------------------------------------------------------------------
# Test 7: validate catches missing pages/ directory
# ---------------------------------------------------------------------------


def test_validate_catches_missing_pages_dir(tmp_path: Path) -> None:
    """validate() returns a descriptive error when pages/ has been removed."""
    adapter = make_adapter(tmp_path)
    adapter.ingest("rhett759")

    # Manually delete the pages/ directory
    pages_dir = adapter.bronze_dir("rhett759") / "pages"
    shutil.rmtree(pages_dir)

    errors = adapter.validate("rhett759")
    assert len(errors) > 0, "Expected validation errors after removing pages/"
    # At least one error should mention "pages/"
    assert any("pages" in e for e in errors), (
        f"Expected error mentioning 'pages/', got: {errors}"
    )
