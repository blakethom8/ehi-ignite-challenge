"""Tests for EVAL-T01 — score_against_ground_truth + CLI auto-load.

All tests use synthetic FHIR Bundles (no real PDFs, no real LLMs).
CLI integration tests monkeypatch pipeline.extract() using the same
pattern as test_lab_cli.py.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

import pytest

from lib.extract.lab.eval_against_gt import score_against_ground_truth
from lib.extract.lab.cli import main
from lib.extract.lab.recorder import RunRecorder
from lib.extract.lab.ground_truth import save_ground_truth


# ---------------------------------------------------------------------------
# Bundle construction helpers
# ---------------------------------------------------------------------------


def _condition_entry(display: str, code: str, system: str = "http://snomed.info/sct") -> dict:
    return {
        "resource": {
            "resourceType": "Condition",
            "id": f"cond-{code}",
            "code": {
                "coding": [{"system": system, "code": code, "display": display}],
                "text": display,
            },
        }
    }


def _observation_entry(display: str, loinc_code: str) -> dict:
    return {
        "resource": {
            "resourceType": "Observation",
            "id": f"obs-{loinc_code}",
            "code": {
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": loinc_code,
                        "display": display,
                    }
                ],
                "text": display,
            },
        }
    }


def _bundle(*entries: dict) -> dict:
    return {"resourceType": "Bundle", "entry": list(entries)}


# ---------------------------------------------------------------------------
# 1. Identical bundles → F1 == 1.0
# ---------------------------------------------------------------------------


def test_score_identical_bundles_f1_one() -> None:
    """GT and extracted are identical → weighted F1 == 1.0, per-resource F1 == 1.0,
    overlap == count for every resource type."""
    gt = _bundle(
        _condition_entry("Hypertension", "38341003"),
        _condition_entry("Diabetes mellitus", "73211009"),
        _observation_entry("Hemoglobin A1c", "4548-4"),
    )
    result = score_against_ground_truth(gt, gt)

    assert result.weighted_f1 == 1.0, f"Expected 1.0, got {result.weighted_f1}"
    for rt, score in result.per_resource.items():
        assert score.f1 == 1.0, f"{rt}: expected F1=1.0, got {score.f1}"
        assert score.overlap == score.truth_count == score.extracted_count


# ---------------------------------------------------------------------------
# 2. Zero overlap → F1 == 0, overlap == 0
# ---------------------------------------------------------------------------


def test_score_zero_overlap_zero_f1() -> None:
    """Completely disjoint bundles → F1 == 0 for every resource type, overlap == 0."""
    gt = _bundle(
        _condition_entry("Hypertension", "38341003"),
    )
    extracted = _bundle(
        _condition_entry("Diabetes mellitus", "73211009"),
    )
    result = score_against_ground_truth(extracted, gt)

    assert result.weighted_f1 == 0.0, f"Expected 0.0, got {result.weighted_f1}"
    assert result.total_overlap == 0
    for score in result.per_resource.values():
        assert score.f1 == 0.0
        assert score.overlap == 0


# ---------------------------------------------------------------------------
# 3. Partial overlap — correct F1 arithmetic
# ---------------------------------------------------------------------------


def test_score_partial_overlap_correct_arithmetic() -> None:
    """GT has 4 conditions, extracted has 5, 3 overlap.
    precision=3/5=0.6, recall=3/4=0.75, F1=2*0.6*0.75/(0.6+0.75)≈0.6667."""
    gt = _bundle(
        _condition_entry("Cond A", "A001"),
        _condition_entry("Cond B", "A002"),
        _condition_entry("Cond C", "A003"),
        _condition_entry("Cond D", "A004"),
    )
    extracted = _bundle(
        _condition_entry("Cond A", "A001"),   # overlap
        _condition_entry("Cond B", "A002"),   # overlap
        _condition_entry("Cond C", "A003"),   # overlap
        _condition_entry("Cond E", "A005"),   # extra
        _condition_entry("Cond F", "A006"),   # extra
    )
    result = score_against_ground_truth(extracted, gt)

    score = result.per_resource["Condition"]
    assert score.truth_count == 4
    assert score.extracted_count == 5
    assert score.overlap == 3
    assert abs(score.precision - 0.6) < 1e-3, f"precision={score.precision}"
    assert abs(score.recall - 0.75) < 1e-3, f"recall={score.recall}"
    expected_f1 = 2 * 0.6 * 0.75 / (0.6 + 0.75)
    assert abs(score.f1 - expected_f1) < 1e-3, f"f1={score.f1}, expected {expected_f1:.4f}"


# ---------------------------------------------------------------------------
# 4. Per-resource-type independence — obs vs conds
# ---------------------------------------------------------------------------


def test_score_per_resource_type_independent() -> None:
    """GT has obs+conds, extracted has obs only.
    Conditions get F1=0 (zero overlap, zero extracted = precision=0, recall=0)."""
    gt = _bundle(
        _condition_entry("Hypertension", "38341003"),
        _condition_entry("Diabetes mellitus", "73211009"),
        _observation_entry("HbA1c", "4548-4"),
    )
    extracted = _bundle(
        _observation_entry("HbA1c", "4548-4"),
    )
    result = score_against_ground_truth(extracted, gt)

    # Condition: GT has 2, extracted has 0 → recall=0, precision=undefined→0, F1=0
    cond_score = result.per_resource.get("Condition")
    assert cond_score is not None, "Condition should be in per_resource"
    assert cond_score.f1 == 0.0
    assert cond_score.overlap == 0
    assert cond_score.truth_count == 2
    assert cond_score.extracted_count == 0

    # Observation: identical → F1=1.0
    obs_score = result.per_resource.get("Observation")
    assert obs_score is not None, "Observation should be in per_resource"
    assert obs_score.f1 == 1.0
    assert obs_score.overlap == 1


# ---------------------------------------------------------------------------
# 5. truth_only samples capped at fact_sample_cap
# ---------------------------------------------------------------------------


def test_score_truth_only_samples_capped_at_cap() -> None:
    """GT has 20 unique conditions, extracted has 0 → truth_only['Condition']
    has at most fact_sample_cap entries."""
    cap = 5
    gt_entries = [_condition_entry(f"Cond {i}", f"X{i:03d}") for i in range(20)]
    gt = _bundle(*gt_entries)
    extracted = _bundle()

    result = score_against_ground_truth(extracted, gt, fact_sample_cap=cap)

    assert "Condition" in result.truth_only, "Condition should appear in truth_only"
    assert len(result.truth_only["Condition"]) <= cap, (
        f"truth_only samples should be capped at {cap}, "
        f"got {len(result.truth_only['Condition'])}"
    )
    # extracted_only should be empty since nothing was extracted
    assert "Condition" not in result.extracted_only


# ---------------------------------------------------------------------------
# 6. Weighted F1 weights by truth_count
# ---------------------------------------------------------------------------


def test_score_returns_weighted_f1_across_types() -> None:
    """Multiple resource types with different truth_counts → weighted F1 weights
    by truth_count. Here: conditions perfect (F1=1, n=3), obs zero (F1=0, n=1).
    Weighted F1 = (1.0*3 + 0.0*1) / (3+1) = 3/4 = 0.75."""
    gt = _bundle(
        _condition_entry("Cond A", "A001"),
        _condition_entry("Cond B", "A002"),
        _condition_entry("Cond C", "A003"),
        _observation_entry("HbA1c", "4548-4"),  # in GT but not in extracted
    )
    extracted = _bundle(
        _condition_entry("Cond A", "A001"),
        _condition_entry("Cond B", "A002"),
        _condition_entry("Cond C", "A003"),
        # Observation absent
    )
    result = score_against_ground_truth(extracted, gt)

    expected_wf1 = (1.0 * 3 + 0.0 * 1) / (3 + 1)  # 0.75
    assert abs(result.weighted_f1 - expected_wf1) < 1e-3, (
        f"weighted_f1={result.weighted_f1}, expected {expected_wf1:.4f}"
    )


# ---------------------------------------------------------------------------
# CLI integration fixtures + helpers (shared)
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_pdf(tmp_path: Path) -> Path:
    p = tmp_path / "sample.pdf"
    p.write_bytes(b"%PDF-1.4 fake content for testing")
    return p


@pytest.fixture()
def lab_root(tmp_path: Path) -> Path:
    return tmp_path / "pdf-lab"


def _stub_extract_known_bundle(
    bundle_to_return: dict,
) -> Any:
    """Return a monkeypatch-compatible extract() that emits a known bundle."""

    def _extract(self: Any, pdf_path: Path, *, recorder: RunRecorder | None = None, **kwargs: Any) -> dict:
        if recorder is not None:
            recorder.log_pass(
                pass_name="document_context",
                prompt="stub prompt",
                response={},
                usage={"input_tokens": 10, "output_tokens": 5, "latency_ms": 100, "cost_usd": 0.001},
                extraction={"document_type": "lab-report"},
            )
            recorder.finish(bundle=bundle_to_return, status="succeeded")
        return bundle_to_return

    return _extract


def _patch_all_pipelines(monkeypatch: pytest.MonkeyPatch, bundle: dict) -> None:
    from lib.extract.pipelines.base import _REGISTRY
    stub = _stub_extract_known_bundle(bundle)
    for pipeline_cls in _REGISTRY._pipelines.values():
        monkeypatch.setattr(pipeline_cls, "extract", stub)


def _get_single_run_dir(lab_root: Path) -> Path:
    runs_dir = lab_root / "runs"
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1, f"Expected 1 run dir, found {len(run_dirs)}"
    return run_dirs[0]


# ---------------------------------------------------------------------------
# 7. CLI auto-loads ground truth when present
# ---------------------------------------------------------------------------


def test_cli_run_auto_loads_ground_truth_when_present(
    fake_pdf: Path,
    lab_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When a ground-truth file exists for the PDF's sha256, lab run auto-loads
    it and writes eval.json with weighted_f1 field."""
    # Build a known bundle with one condition
    known_bundle = _bundle(_condition_entry("Hypertension", "38341003"))

    _patch_all_pipelines(monkeypatch, known_bundle)

    # Compute the pdf sha256 so we can pre-populate GT
    import hashlib
    pdf_sha256 = hashlib.sha256(fake_pdf.read_bytes()).hexdigest()

    # Save GT (same bundle → identical → F1 should be 1.0)
    save_ground_truth(
        pdf_sha256=pdf_sha256,
        pdf_path=str(fake_pdf),
        bundle=known_bundle,
        reviewer="test-reviewer",
        lab_root=lab_root,
    )

    exit_code = main([
        "run",
        "--pipeline", "multipass-fhir",
        "--pdf", str(fake_pdf),
        "--root", str(lab_root),
    ])
    assert exit_code == 0, f"Expected exit 0, got {exit_code}"

    run_dir = _get_single_run_dir(lab_root)
    eval_path = run_dir / "eval.json"
    assert eval_path.exists(), "eval.json should be written when GT is auto-loaded"

    eval_data = json.loads(eval_path.read_text())
    assert "weighted_f1" in eval_data, "eval.json should contain weighted_f1"
    # Identical bundle → F1 == 1.0
    assert eval_data["weighted_f1"] == 1.0, (
        f"Expected weighted_f1=1.0 for identical bundles, got {eval_data['weighted_f1']}"
    )


# ---------------------------------------------------------------------------
# 8. No eval.json when no ground truth
# ---------------------------------------------------------------------------


def test_cli_run_no_eval_when_no_ground_truth(
    fake_pdf: Path,
    lab_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When no GT exists for the PDF, eval.json is NOT written."""
    known_bundle = _bundle(_condition_entry("Hypertension", "38341003"))
    _patch_all_pipelines(monkeypatch, known_bundle)

    exit_code = main([
        "run",
        "--pipeline", "multipass-fhir",
        "--pdf", str(fake_pdf),
        "--root", str(lab_root),
    ])
    assert exit_code == 0

    run_dir = _get_single_run_dir(lab_root)
    eval_path = run_dir / "eval.json"
    assert not eval_path.exists(), "eval.json should NOT exist when no ground truth"


# ---------------------------------------------------------------------------
# 9. Manual --ground-truth overrides auto-loaded
# ---------------------------------------------------------------------------


def test_cli_run_manual_ground_truth_overrides_auto_loaded(
    fake_pdf: Path,
    lab_root: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When both --ground-truth AND an auto-loadable GT exist, the manual
    flag wins (eval is scored against the manually-provided file)."""
    import hashlib

    # Auto-loadable GT: one condition
    auto_gt_bundle = _bundle(_condition_entry("Hypertension", "38341003"))
    pdf_sha256 = hashlib.sha256(fake_pdf.read_bytes()).hexdigest()
    save_ground_truth(
        pdf_sha256=pdf_sha256,
        pdf_path=str(fake_pdf),
        bundle=auto_gt_bundle,
        reviewer="test-reviewer",
        lab_root=lab_root,
    )

    # Manual GT: completely different condition — causes zero overlap
    manual_gt_bundle = _bundle(_condition_entry("Diabetes mellitus", "73211009"))
    manual_gt_path = tmp_path / "manual-gt.json"
    manual_gt_path.write_text(json.dumps(manual_gt_bundle), encoding="utf-8")

    # Pipeline extracts the hypertension bundle
    extracted_bundle = _bundle(_condition_entry("Hypertension", "38341003"))
    _patch_all_pipelines(monkeypatch, extracted_bundle)

    exit_code = main([
        "run",
        "--pipeline", "multipass-fhir",
        "--pdf", str(fake_pdf),
        "--ground-truth", str(manual_gt_path),
        "--root", str(lab_root),
    ])
    assert exit_code == 0

    run_dir = _get_single_run_dir(lab_root)
    eval_path = run_dir / "eval.json"
    assert eval_path.exists(), "eval.json should be written when --ground-truth is provided"

    eval_data = json.loads(eval_path.read_text())
    # Manual GT has Diabetes, extracted has Hypertension → zero overlap → F1=0
    assert eval_data["weighted_f1"] == 0.0, (
        f"Manual GT should override auto-loaded GT. Expected F1=0.0 (disjoint), "
        f"got {eval_data['weighted_f1']}"
    )
