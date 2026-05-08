"""Tests for LAB-T04 — compare_runs() library function and `compare` CLI subcommand.

All tests use tmp_path for the lab root. No real LLM is invoked.
"""

from __future__ import annotations

import json
from pathlib import Path
from io import StringIO

import pytest

from lib.extract.lab.compare import compare_runs, FactSample, RunComparison
from lib.extract.lab.cli import main


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_run(
    root: Path,
    run_id: str,
    pipeline_name: str,
    bundle: dict,
    cost: float = 0.10,
    latency_ms: int = 15000,
) -> None:
    """Construct a minimal run directory with manifest.json and bundle.json."""
    run_dir = root / "runs" / run_id
    run_dir.mkdir(parents=True)
    (run_dir / "manifest.json").write_text(
        json.dumps({
            "run_id": run_id,
            "pipeline_name": pipeline_name,
            "pdf_path": "/test.pdf",
            "pdf_sha256": "abc",
            "ground_truth_path": None,
            "started_at": "2026-05-07T18-00-00",
            "finished_at": "2026-05-07T18-00-30",
            "cost_usd": cost,
            "latency_ms": latency_ms,
            "status": "succeeded",
            "error": None,
        })
    )
    (run_dir / "bundle.json").write_text(json.dumps(bundle))


def _condition_entry(display: str, snomed_code: str) -> dict:
    return {
        "resource": {
            "resourceType": "Condition",
            "code": {
                "text": display,
                "coding": [
                    {
                        "system": "http://snomed.info/sct",
                        "code": snomed_code,
                        "display": display,
                    }
                ],
            },
        }
    }


def _observation_entry(display: str, loinc_code: str, value: float, unit: str = "mg/dL") -> dict:
    return {
        "resource": {
            "resourceType": "Observation",
            "code": {
                "text": display,
                "coding": [
                    {
                        "system": "http://loinc.org",
                        "code": loinc_code,
                        "display": display,
                    }
                ],
            },
            "valueQuantity": {"value": value, "unit": unit},
        }
    }


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------


def test_compare_identical_runs(tmp_path: Path) -> None:
    """Same bundle in both runs → counts_delta all zero; fact_overlap == counts; only lists empty."""
    bundle = {
        "entry": [
            _condition_entry("Hypertension", "38341003"),
            _condition_entry("Diabetes", "73211009"),
        ]
    }
    _make_run(tmp_path, "run-a", "pipeline-x", bundle)
    _make_run(tmp_path, "run-b", "pipeline-x", bundle)

    result = compare_runs("run-a", "run-b", root=tmp_path)

    # All deltas should be zero
    for rt, delta in result.counts_delta.items():
        assert delta == 0, f"Expected zero delta for {rt}, got {delta}"

    # fact_overlap should match counts since facts are identical
    assert result.fact_overlap.get("Condition", 0) == 2

    # No facts unique to either side
    assert result.fact_only_in_a == {}
    assert result.fact_only_in_b == {}


def test_compare_b_extracted_more_conditions(tmp_path: Path) -> None:
    """A has 1 condition, B has 4 → counts_delta['Condition'] == 3; only_in_b has 3."""
    bundle_a = {"entry": [_condition_entry("Hypertension", "38341003")]}
    bundle_b = {
        "entry": [
            _condition_entry("Hypertension", "38341003"),
            _condition_entry("Diabetes", "73211009"),
            _condition_entry("Asthma", "195967001"),
            _condition_entry("Migraine", "37796009"),
        ]
    }
    _make_run(tmp_path, "run-a", "pipeline-x", bundle_a)
    _make_run(tmp_path, "run-b", "pipeline-y", bundle_b)

    result = compare_runs("run-a", "run-b", root=tmp_path)

    assert result.counts_delta["Condition"] == 3
    assert len(result.fact_only_in_b.get("Condition", [])) == 3
    assert result.fact_only_in_a.get("Condition") is None or len(result.fact_only_in_a.get("Condition", [])) == 0


def test_compare_cost_and_latency_delta(tmp_path: Path) -> None:
    """cost_delta_usd and latency_delta_ms computed correctly."""
    bundle = {"entry": []}
    _make_run(tmp_path, "run-a", "pipeline-x", bundle, cost=0.10, latency_ms=10000)
    _make_run(tmp_path, "run-b", "pipeline-y", bundle, cost=0.30, latency_ms=25000)

    result = compare_runs("run-a", "run-b", root=tmp_path)

    assert abs(result.cost_delta_usd - 0.20) < 1e-9
    assert result.latency_delta_ms == 15000


def test_compare_unknown_run_id_raises(tmp_path: Path) -> None:
    """compare_runs with a non-existent run_id raises FileNotFoundError."""
    # Neither run directory exists
    with pytest.raises(FileNotFoundError):
        compare_runs("nonexistent", "x", root=tmp_path)


def test_compare_observation_loinc_match_overlap(tmp_path: Path) -> None:
    """A and B both have a Glucose Observation with LOINC 2345-7 but different values
    → fact_overlap['Observation'] >= 1 (same code key matches despite different value)."""
    bundle_a = {"entry": [_observation_entry("Glucose", "2345-7", 95.0)]}
    bundle_b = {"entry": [_observation_entry("Glucose", "2345-7", 110.0)]}

    _make_run(tmp_path, "run-a", "pipeline-x", bundle_a)
    _make_run(tmp_path, "run-b", "pipeline-y", bundle_b)

    result = compare_runs("run-a", "run-b", root=tmp_path)

    # The fact key is (display.lower(), loinc_code.lower()) — value is not part of key
    assert result.fact_overlap.get("Observation", 0) >= 1
    # Neither side has unique observations
    assert result.fact_only_in_a.get("Observation") is None or len(result.fact_only_in_a.get("Observation", [])) == 0
    assert result.fact_only_in_b.get("Observation") is None or len(result.fact_only_in_b.get("Observation", [])) == 0


def test_compare_handles_missing_bundle_shape(tmp_path: Path) -> None:
    """Neither run has bundle_shape.json → bundle_shape_a / bundle_shape_b == {}."""
    bundle = {"entry": []}
    _make_run(tmp_path, "run-a", "pipeline-x", bundle)
    _make_run(tmp_path, "run-b", "pipeline-y", bundle)

    result = compare_runs("run-a", "run-b", root=tmp_path)

    assert result.bundle_shape_a == {}
    assert result.bundle_shape_b == {}


def test_compare_reads_bundle_shape_when_present(tmp_path: Path) -> None:
    """Write bundle_shape.json into run-a's directory → bundle_shape_a populated."""
    bundle = {"entry": []}
    _make_run(tmp_path, "run-a", "pipeline-x", bundle)
    _make_run(tmp_path, "run-b", "pipeline-y", bundle)

    shape_data = {"resource_type_counts": {"Condition": 2, "Observation": 5}, "total_entries": 7}
    (tmp_path / "runs" / "run-a" / "bundle_shape.json").write_text(json.dumps(shape_data))

    result = compare_runs("run-a", "run-b", root=tmp_path)

    assert result.bundle_shape_a == shape_data
    assert result.bundle_shape_b == {}


def test_cli_compare_text_format_succeeds(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """CLI compare subcommand with --format text exits 0 and stdout contains 'Resource counts'."""
    bundle_a = {"entry": [_condition_entry("Hypertension", "38341003")]}
    bundle_b = {
        "entry": [
            _condition_entry("Hypertension", "38341003"),
            _condition_entry("Diabetes", "73211009"),
        ]
    }
    _make_run(tmp_path, "run-a", "pipeline-x", bundle_a)
    _make_run(tmp_path, "run-b", "pipeline-y", bundle_b)

    exit_code = main(["compare", "--run-a", "run-a", "--run-b", "run-b", "--root", str(tmp_path)])
    captured = capsys.readouterr()

    assert exit_code == 0
    assert "Resource counts" in captured.out


def test_cli_compare_json_format_emits_valid_json(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """--format json emits valid JSON with expected top-level keys."""
    bundle = {"entry": [_condition_entry("Hypertension", "38341003")]}
    _make_run(tmp_path, "run-a", "pipeline-x", bundle)
    _make_run(tmp_path, "run-b", "pipeline-y", bundle)

    exit_code = main([
        "compare",
        "--run-a", "run-a",
        "--run-b", "run-b",
        "--root", str(tmp_path),
        "--format", "json",
    ])
    captured = capsys.readouterr()

    assert exit_code == 0
    data = json.loads(captured.out)
    for key in ("run_a_id", "run_b_id", "pipeline_a", "pipeline_b",
                "cost_delta_usd", "latency_delta_ms", "resource_counts_a",
                "resource_counts_b", "counts_delta", "fact_overlap",
                "fact_only_in_a", "fact_only_in_b", "bundle_shape_a", "bundle_shape_b"):
        assert key in data, f"Missing key in JSON output: {key}"


def test_cli_compare_unknown_run_exits_2(tmp_path: Path, capsys: pytest.CaptureFixture) -> None:
    """Passing a nonexistent run id → exit code 2; stderr contains 'error'."""
    exit_code = main([
        "compare",
        "--run-a", "nonexistent-run",
        "--run-b", "also-nonexistent",
        "--root", str(tmp_path),
    ])
    captured = capsys.readouterr()

    assert exit_code == 2
    assert "error" in captured.err.lower()


def test_fact_only_lists_capped_at_sample_cap(tmp_path: Path) -> None:
    """A has 20 unique conditions B doesn't → fact_only_in_a['Condition'] capped at fact_sample_cap."""
    # Build 20 unique conditions in A
    conditions_a = [_condition_entry(f"Condition {i}", f"100000{i:03d}") for i in range(20)]
    bundle_a = {"entry": conditions_a}
    bundle_b = {"entry": []}  # B has nothing

    _make_run(tmp_path, "run-a", "pipeline-x", bundle_a)
    _make_run(tmp_path, "run-b", "pipeline-y", bundle_b)

    # Use default sample cap (10)
    result = compare_runs("run-a", "run-b", root=tmp_path, fact_sample_cap=10)

    only_a_conditions = result.fact_only_in_a.get("Condition", [])
    assert len(only_a_conditions) <= 10
    # All counts are still correct
    assert result.resource_counts_a.get("Condition", 0) == 20
    assert result.resource_counts_b.get("Condition", 0) == 0
    assert result.counts_delta.get("Condition", 0) == -20


# ---------------------------------------------------------------------------
# PERF-T01 extensions: fuzzy-match integration in compare_runs
# ---------------------------------------------------------------------------


def _composition_entry(title: str) -> dict:
    return {
        "resource": {
            "resourceType": "Composition",
            "id": f"comp-{title[:8]}",
            "title": title,
        }
    }


def test_compare_runs_uses_fuzzy_match_for_display_variants(tmp_path: Path) -> None:
    """A has Composition titled 'Progress Note', B has 'Allergy Progress Note'.
    Fuzzy match should find these as overlap rather than false negatives."""
    bundle_a = {"entry": [_composition_entry("Progress Note")]}
    bundle_b = {"entry": [_composition_entry("Allergy Progress Note")]}

    _make_run(tmp_path, "run-a", "pipeline-x", bundle_a)
    _make_run(tmp_path, "run-b", "pipeline-y", bundle_b)

    result = compare_runs("run-a", "run-b", root=tmp_path)

    # The display variants should match via Stage 2 fuzzy — overlap >= 1
    assert result.fact_overlap.get("Composition", 0) >= 1
    # Not counted in either only list
    assert result.fact_only_in_a.get("Composition") is None or len(result.fact_only_in_a.get("Composition", [])) == 0
    assert result.fact_only_in_b.get("Composition") is None or len(result.fact_only_in_b.get("Composition", [])) == 0


def test_compare_runs_exposes_fuzzy_match_count_field(tmp_path: Path) -> None:
    """RunComparison has a fuzzy_match_count attribute populated when fuzzy matches occurred."""
    bundle_a = {"entry": [_composition_entry("Progress Note")]}
    bundle_b = {"entry": [_composition_entry("Allergy Progress Note")]}

    _make_run(tmp_path, "run-a", "pipeline-x", bundle_a)
    _make_run(tmp_path, "run-b", "pipeline-y", bundle_b)

    result = compare_runs("run-a", "run-b", root=tmp_path)

    assert hasattr(result, "fuzzy_match_count"), "RunComparison must have fuzzy_match_count"
    assert isinstance(result.fuzzy_match_count, dict)
    assert result.fuzzy_match_count.get("Composition", 0) >= 1
