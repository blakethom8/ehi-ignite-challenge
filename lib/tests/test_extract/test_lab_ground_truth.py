"""Tests for lib.extract.lab.ground_truth — versioned ground-truth storage.

All tests use pytest's tmp_path as lab_root so they never write to
data/pdf-lab/. Tests are hermetic and do not require LLM calls.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.extract.lab.ground_truth import (
    GroundTruthVersion,
    gt_dir_for_pdf,
    has_ground_truth,
    list_ground_truth_versions,
    load_ground_truth_version,
    load_latest_ground_truth,
    save_ground_truth,
)


# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

FAKE_SHA = "511b7036abcdef1234567890abcdef1234567890abcdef1234567890abcdef12"
MINIMAL_BUNDLE: dict = {"resourceType": "Bundle", "type": "collection", "entry": []}


def _save(tmp_path: Path, **kwargs) -> GroundTruthVersion:
    """Helper — call save_ground_truth with sensible defaults."""
    defaults = dict(
        pdf_sha256=FAKE_SHA,
        pdf_path="/tmp/sample.pdf",
        bundle=MINIMAL_BUNDLE,
        lab_root=tmp_path,
    )
    defaults.update(kwargs)
    return save_ground_truth(**defaults)


# ---------------------------------------------------------------------------
# Test 1: first save creates v1.json + meta file
# ---------------------------------------------------------------------------


def test_save_ground_truth_creates_v1_when_none_exists(tmp_path: Path) -> None:
    gtv = _save(tmp_path)

    gt_dir = gt_dir_for_pdf(FAKE_SHA, lab_root=tmp_path)
    assert (gt_dir / "v1.json").exists(), "v1.json should be created"
    assert gtv.version == 1

    prefix = FAKE_SHA[:8]
    meta_path = gt_dir / f"{prefix}.meta.json"
    assert meta_path.exists(), "meta.json should be created"
    meta = json.loads(meta_path.read_text())
    assert meta["latest_version"] == 1


# ---------------------------------------------------------------------------
# Test 2: second save auto-increments to v2; both files persist; meta updated
# ---------------------------------------------------------------------------


def test_save_ground_truth_auto_increments_version(tmp_path: Path) -> None:
    v1 = _save(tmp_path)
    v2 = _save(tmp_path)

    assert v1.version == 1
    assert v2.version == 2

    gt_dir = gt_dir_for_pdf(FAKE_SHA, lab_root=tmp_path)
    assert (gt_dir / "v1.json").exists()
    assert (gt_dir / "v2.json").exists()

    prefix = FAKE_SHA[:8]
    meta = json.loads((gt_dir / f"{prefix}.meta.json").read_text())
    assert meta["latest_version"] == 2
    assert len(meta["versions_created"]) == 2


# ---------------------------------------------------------------------------
# Test 3: old versions are immutable after a second save
# ---------------------------------------------------------------------------


def test_save_ground_truth_immutable_old_versions(tmp_path: Path) -> None:
    _save(tmp_path, notes="version-one")
    gt_dir = gt_dir_for_pdf(FAKE_SHA, lab_root=tmp_path)
    v1_content_before = (gt_dir / "v1.json").read_text()

    _save(tmp_path, notes="version-two")

    v1_content_after = (gt_dir / "v1.json").read_text()
    assert v1_content_before == v1_content_after, "v1.json must not change after second save"


# ---------------------------------------------------------------------------
# Test 4: decisions list round-trips intact
# ---------------------------------------------------------------------------


def test_save_ground_truth_persists_decisions_list(tmp_path: Path) -> None:
    decisions = [
        {
            "resource_id": "obs-1",
            "resource_type": "Observation",
            "decision": "accept",
            "edited_fields": {},
            "note": "looks good",
        },
        {
            "resource_id": "obs-2",
            "resource_type": "Observation",
            "decision": "reject",
            "edited_fields": {},
            "note": "wrong value",
        },
    ]
    _save(tmp_path, decisions=decisions)
    loaded = load_latest_ground_truth(FAKE_SHA, lab_root=tmp_path)
    assert loaded is not None
    assert loaded.decisions == decisions


# ---------------------------------------------------------------------------
# Test 5: reviewer and notes are preserved
# ---------------------------------------------------------------------------


def test_save_ground_truth_persists_reviewer_and_notes(tmp_path: Path) -> None:
    _save(tmp_path, reviewer="blake", notes="initial review pass")
    loaded = load_latest_ground_truth(FAKE_SHA, lab_root=tmp_path)
    assert loaded is not None
    assert loaded.reviewer == "blake"
    assert loaded.notes == "initial review pass"


# ---------------------------------------------------------------------------
# Test 6: source_run_id is preserved
# ---------------------------------------------------------------------------


def test_save_ground_truth_records_source_run_id(tmp_path: Path) -> None:
    _save(tmp_path, source_run_id="run-abc-123")
    loaded = load_latest_ground_truth(FAKE_SHA, lab_root=tmp_path)
    assert loaded is not None
    assert loaded.source_run_id == "run-abc-123"


# ---------------------------------------------------------------------------
# Test 7: load_latest returns highest version
# ---------------------------------------------------------------------------


def test_load_latest_ground_truth_returns_highest_version(tmp_path: Path) -> None:
    _save(tmp_path, notes="v1")
    _save(tmp_path, notes="v2")
    _save(tmp_path, notes="v3")

    loaded = load_latest_ground_truth(FAKE_SHA, lab_root=tmp_path)
    assert loaded is not None
    assert loaded.version == 3
    assert loaded.notes == "v3"


# ---------------------------------------------------------------------------
# Test 8: load_latest returns None when no ground truth exists
# ---------------------------------------------------------------------------


def test_load_latest_ground_truth_returns_none_when_missing(tmp_path: Path) -> None:
    result = load_latest_ground_truth(FAKE_SHA, lab_root=tmp_path)
    assert result is None


# ---------------------------------------------------------------------------
# Test 9: load_ground_truth_version returns a specific version
# ---------------------------------------------------------------------------


def test_load_ground_truth_version_specific(tmp_path: Path) -> None:
    _save(tmp_path, notes="first")
    _save(tmp_path, notes="second")

    v1 = load_ground_truth_version(FAKE_SHA, 1, lab_root=tmp_path)
    assert v1 is not None
    assert v1.version == 1
    assert v1.notes == "first"

    v2 = load_ground_truth_version(FAKE_SHA, 2, lab_root=tmp_path)
    assert v2 is not None
    assert v2.version == 2
    assert v2.notes == "second"


# ---------------------------------------------------------------------------
# Test 10: load_ground_truth_version returns None for a missing version
# ---------------------------------------------------------------------------


def test_load_ground_truth_version_returns_none_when_missing_version(tmp_path: Path) -> None:
    _save(tmp_path)  # only v1 exists
    result = load_ground_truth_version(FAKE_SHA, 2, lab_root=tmp_path)
    assert result is None


# ---------------------------------------------------------------------------
# Test 11: list_ground_truth_versions returns sorted ints (gaps allowed)
# ---------------------------------------------------------------------------


def test_list_ground_truth_versions_returns_sorted_ints(tmp_path: Path) -> None:
    _save(tmp_path, notes="v1")

    # Manually write v3.json (simulating a gap — v2 skipped)
    gt_dir = gt_dir_for_pdf(FAKE_SHA, lab_root=tmp_path)
    v3_data = {
        "version": 3,
        "pdf_sha256": FAKE_SHA,
        "pdf_path": "/tmp/sample.pdf",
        "bundle": MINIMAL_BUNDLE,
        "decisions": [],
        "reviewer": "unknown",
        "created_at": "2026-01-01T00:00:00Z",
        "source_run_id": None,
        "notes": "v3 manual",
    }
    (gt_dir / "v3.json").write_text(json.dumps(v3_data, indent=2))

    versions = list_ground_truth_versions(FAKE_SHA, lab_root=tmp_path)
    assert versions == [1, 3]


# ---------------------------------------------------------------------------
# Test 12: has_ground_truth returns True when at least one version exists
# ---------------------------------------------------------------------------


def test_has_ground_truth_returns_true_when_any_version_exists(tmp_path: Path) -> None:
    _save(tmp_path)
    assert has_ground_truth(FAKE_SHA, lab_root=tmp_path) is True


# ---------------------------------------------------------------------------
# Test 13: has_ground_truth returns False when no directory exists
# ---------------------------------------------------------------------------


def test_has_ground_truth_returns_false_when_directory_missing(tmp_path: Path) -> None:
    fresh_sha = "a" * 64
    assert has_ground_truth(fresh_sha, lab_root=tmp_path) is False


# ---------------------------------------------------------------------------
# Test 14: meta file round-trips pdf_path
# ---------------------------------------------------------------------------


def test_save_ground_truth_meta_file_contains_pdf_path(tmp_path: Path) -> None:
    expected_path = "/data/patients/patient-records/report.pdf"
    _save(tmp_path, pdf_path=expected_path)

    gt_dir = gt_dir_for_pdf(FAKE_SHA, lab_root=tmp_path)
    prefix = FAKE_SHA[:8]
    meta = json.loads((gt_dir / f"{prefix}.meta.json").read_text())
    assert meta["pdf_path"] == expected_path


# ---------------------------------------------------------------------------
# Test 15: gt_dir_for_pdf uses the 8-character sha prefix
# ---------------------------------------------------------------------------


def test_gt_dir_uses_sha_prefix(tmp_path: Path) -> None:
    gt_dir = gt_dir_for_pdf(FAKE_SHA, lab_root=tmp_path)
    # Directory name must be exactly the first 8 chars of the SHA
    assert gt_dir.name == FAKE_SHA[:8]
    # Parent must be the ground-truth root under lab_root
    assert gt_dir.parent == tmp_path / "ground-truth"
