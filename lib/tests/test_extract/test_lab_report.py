"""Tests for LAB-T06 — markdown report generators + CLI show/list/report.

All tests use tmp_path for isolation. No real LLM is invoked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lib.extract.lab.report import (
    read_runs_index,
    render_comparison,
    render_run_summary,
    render_runs_list,
)
from lib.extract.lab.compare import RunComparison, FactSample
from lib.extract.lab.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_run_dir(
    root: Path,
    run_id: str,
    *,
    pipeline: str = "test-pipeline",
    status: str = "succeeded",
    cost: float = 0.05,
    latency: int = 1500,
    error: str | None = None,
    bundle: dict | None = None,
    bundle_shape: dict | None = None,
) -> Path:
    """Create a synthetic run directory with manifest.json and optional files."""
    run_dir = root / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "run_id": run_id,
        "pipeline_name": pipeline,
        "pdf_path": "/some/path/test.pdf",
        "pdf_sha256": "abc123",
        "ground_truth_path": None,
        "started_at": "2026-05-07T10:00:00Z",
        "finished_at": "2026-05-07T10:00:01Z",
        "cost_usd": cost,
        "latency_ms": latency,
        "status": status,
        "error": error,
    }
    (run_dir / "manifest.json").write_text(json.dumps(manifest))

    if bundle is not None:
        (run_dir / "bundle.json").write_text(json.dumps(bundle))

    if bundle_shape is not None:
        (run_dir / "bundle_shape.json").write_text(json.dumps(bundle_shape))

    return run_dir


def _make_runs_jsonl(root: Path, runs: list[dict]) -> None:
    """Write a runs.jsonl index file."""
    root.mkdir(parents=True, exist_ok=True)
    lines = [json.dumps(r) for r in runs]
    (root / "runs.jsonl").write_text("\n".join(lines) + "\n")


# ---------------------------------------------------------------------------
# 1. render_run_summary includes pipeline name AND cost
# ---------------------------------------------------------------------------


def test_render_run_summary_includes_pipeline_and_cost(tmp_path: Path) -> None:
    _make_run_dir(tmp_path, "run-001", pipeline="multipass-fhir", cost=0.1234)
    output = render_run_summary("run-001", root=tmp_path)
    assert "multipass-fhir" in output
    assert "0.1234" in output


# ---------------------------------------------------------------------------
# 2. render_run_summary includes resource-count table with specific types
# ---------------------------------------------------------------------------


def test_render_run_summary_includes_resource_counts_table(tmp_path: Path) -> None:
    bundle = {
        "resourceType": "Bundle",
        "entry": [
            {"resource": {"resourceType": "Condition"}},
            {"resource": {"resourceType": "Condition"}},
            {"resource": {"resourceType": "Observation"}},
            {"resource": {"resourceType": "Observation"}},
            {"resource": {"resourceType": "Observation"}},
            {"resource": {"resourceType": "Observation"}},
            {"resource": {"resourceType": "Observation"}},
        ],
    }
    _make_run_dir(tmp_path, "run-002", bundle=bundle)
    output = render_run_summary("run-002", root=tmp_path)
    assert "| Condition | 2 |" in output
    assert "| Observation | 5 |" in output


# ---------------------------------------------------------------------------
# 3. render_run_summary warns on multiple patients
# ---------------------------------------------------------------------------


def test_render_run_summary_warns_on_multiple_patients(tmp_path: Path) -> None:
    bundle_shape = {
        "patient_count": 2,
        "encounter_count": 1,
        "encounter_link_rate": 0.5,
        "patient_link_rate": 0.8,
        "practitioner_npi_rate": 1.0,
        "loinc_resolution_rate": 0.9,
        "interpretation_rate": 0.0,
        "clinical_category_rate": 0.0,
        "note_encounter_link_rate": 0.0,
        "multiple_patients_warning": True,
        "duplicate_practitioner_npis": [],
        "orphaned_subject_references": [],
        "orphaned_encounter_references": [],
    }
    _make_run_dir(tmp_path, "run-003", bundle_shape=bundle_shape)
    output = render_run_summary("run-003", root=tmp_path)
    assert "multiple_patients_warning" in output


# ---------------------------------------------------------------------------
# 4. render_run_summary handles missing bundle.json gracefully
# ---------------------------------------------------------------------------


def test_render_run_summary_handles_missing_files(tmp_path: Path) -> None:
    """A run dir without bundle.json should not crash; renders with empty resource counts."""
    _make_run_dir(tmp_path, "run-004", bundle=None)
    # Verify bundle.json does NOT exist
    assert not (tmp_path / "runs" / "run-004" / "bundle.json").exists()
    output = render_run_summary("run-004", root=tmp_path)
    # Should still render (no crash) and include the header
    assert "# Run:" in output
    # Resource counts section should not appear (no entries)
    assert "## Resource counts" not in output


# ---------------------------------------------------------------------------
# 5. render_runs_list filters by pipeline
# ---------------------------------------------------------------------------


def test_render_runs_list_filters_by_pipeline(tmp_path: Path) -> None:
    runs = [
        {"run_id": "run-a", "pipeline_name": "pipeline-x", "status": "succeeded", "cost_usd": 0.01, "latency_ms": 1000},
        {"run_id": "run-b", "pipeline_name": "pipeline-x", "status": "succeeded", "cost_usd": 0.02, "latency_ms": 2000},
        {"run_id": "run-c", "pipeline_name": "pipeline-y", "status": "succeeded", "cost_usd": 0.03, "latency_ms": 3000},
    ]
    output = render_runs_list(runs, pipeline_filter="pipeline-x")
    assert "run-a" in output
    assert "run-b" in output
    assert "run-c" not in output


# ---------------------------------------------------------------------------
# 6. render_runs_list empty returns "No runs found"
# ---------------------------------------------------------------------------


def test_render_runs_list_empty_returns_no_runs_message() -> None:
    output = render_runs_list([])
    assert "No runs found" in output


# ---------------------------------------------------------------------------
# 7. render_comparison includes resource-count table with delta
# ---------------------------------------------------------------------------


def test_render_comparison_includes_resource_count_table() -> None:
    comparison = RunComparison(
        run_a_id="run-a",
        run_b_id="run-b",
        pipeline_a="pipeline-a",
        pipeline_b="pipeline-b",
        cost_delta_usd=0.05,
        latency_delta_ms=500,
        resource_counts_a={"Condition": 2, "Observation": 5},
        resource_counts_b={"Condition": 5, "Observation": 5},
        counts_delta={"Condition": 3, "Observation": 0},
        fact_overlap={"Condition": 2},
        fact_only_in_a={},
        fact_only_in_b={"Condition": [
            FactSample(resource_type="Condition", display="Diabetes", code="E11", value=None),
            FactSample(resource_type="Condition", display="Hypertension", code="I10", value=None),
            FactSample(resource_type="Condition", display="Asthma", code="J45", value=None),
        ]},
        bundle_shape_a={},
        bundle_shape_b={},
    )
    output = render_comparison(comparison)
    # Condition row with delta +3
    assert "| Condition | 2 | 5 | +3 |" in output


# ---------------------------------------------------------------------------
# 8. render_comparison renders disagreement samples
# ---------------------------------------------------------------------------


def test_render_comparison_renders_disagreement_samples() -> None:
    comparison = RunComparison(
        run_a_id="run-a",
        run_b_id="run-b",
        pipeline_a="pipe-a",
        pipeline_b="pipe-b",
        cost_delta_usd=0.0,
        latency_delta_ms=0,
        resource_counts_a={"Condition": 3},
        resource_counts_b={"Condition": 2},
        counts_delta={"Condition": -1},
        fact_overlap={"Condition": 2},
        fact_only_in_a={"Condition": [
            FactSample(resource_type="Condition", display="Migraine", code="G43", value=None),
        ]},
        fact_only_in_b={},
        bundle_shape_a={},
        bundle_shape_b={},
    )
    output = render_comparison(comparison)
    assert "Only in A" in output
    assert "Migraine" in output


# ---------------------------------------------------------------------------
# 9. read_runs_index sorts newest first
# ---------------------------------------------------------------------------


def test_read_runs_index_sorts_newest_first(tmp_path: Path) -> None:
    runs = [
        {"run_id": "run-old", "pipeline_name": "p", "status": "succeeded", "cost_usd": 0.0, "latency_ms": 0, "started_at": "2026-05-01T10:00:00Z"},
        {"run_id": "run-mid", "pipeline_name": "p", "status": "succeeded", "cost_usd": 0.0, "latency_ms": 0, "started_at": "2026-05-05T10:00:00Z"},
        {"run_id": "run-new", "pipeline_name": "p", "status": "succeeded", "cost_usd": 0.0, "latency_ms": 0, "started_at": "2026-05-07T10:00:00Z"},
    ]
    _make_runs_jsonl(tmp_path, runs)
    result = read_runs_index(root=tmp_path)
    assert len(result) == 3
    assert result[0]["run_id"] == "run-new"
    assert result[1]["run_id"] == "run-mid"
    assert result[2]["run_id"] == "run-old"


# ---------------------------------------------------------------------------
# 10. CLI show prints markdown
# ---------------------------------------------------------------------------


def test_cli_show_prints_markdown(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _make_run_dir(tmp_path, "run-show-001", pipeline="test-pipe")
    exit_code = main(["show", "--run", "run-show-001", "--root", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "# Run:" in captured.out


# ---------------------------------------------------------------------------
# 11. CLI list prints table
# ---------------------------------------------------------------------------


def test_cli_list_prints_table(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    runs = [
        {"run_id": "run-list-001", "pipeline_name": "p", "status": "succeeded", "cost_usd": 0.01, "latency_ms": 1000, "started_at": "2026-05-07T10:00:00Z"},
    ]
    _make_runs_jsonl(tmp_path, runs)
    exit_code = main(["list", "--root", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "run_id" in captured.out


# ---------------------------------------------------------------------------
# 12. CLI report --run emits markdown
# ---------------------------------------------------------------------------


def test_cli_report_run_emits_markdown(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    _make_run_dir(tmp_path, "run-report-001", pipeline="test-pipe")
    exit_code = main(["report", "--run", "run-report-001", "--root", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "# Run:" in captured.out


# ---------------------------------------------------------------------------
# 13. CLI report --compare emits markdown comparison
# ---------------------------------------------------------------------------


def test_cli_report_compare_emits_markdown(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    bundle_a = {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Condition"}}]}
    bundle_b = {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Condition"}}, {"resource": {"resourceType": "Condition"}}]}
    _make_run_dir(tmp_path, "run-cmp-a", pipeline="pipe-a", bundle=bundle_a)
    _make_run_dir(tmp_path, "run-cmp-b", pipeline="pipe-b", bundle=bundle_b)
    exit_code = main(["report", "--compare", "run-cmp-a", "run-cmp-b", "--root", str(tmp_path)])
    assert exit_code == 0
    captured = capsys.readouterr()
    assert "Comparison:" in captured.out


# ---------------------------------------------------------------------------
# 14. CLI report requires --run or --compare (argparse mutex enforcement)
# ---------------------------------------------------------------------------


def test_cli_report_requires_run_or_compare(tmp_path: Path) -> None:
    with pytest.raises(SystemExit) as exc_info:
        main(["report", "--root", str(tmp_path)])
    assert exc_info.value.code != 0


# ---------------------------------------------------------------------------
# 15. CLI show with unknown run exits 2
# ---------------------------------------------------------------------------


def test_cli_show_unknown_run_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    exit_code = main(["show", "--run", "nonexistent-run-id", "--root", str(tmp_path)])
    assert exit_code == 2
    captured = capsys.readouterr()
    assert "error" in captured.err.lower()
