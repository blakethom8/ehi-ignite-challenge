"""Tests for LAB-T03 — PDF Lab CLI entry point + `run` subcommand.

All tests use tmp_path for the lab root. The pipeline's extract() method
is monkeypatched so no real LLM is invoked.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from lib.extract.lab.cli import main
from lib.extract.lab.recorder import RunRecorder
import lib.extract.pipelines as _pipeline_pkg


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_pdf(tmp_path: Path) -> Path:
    """Minimal fake PDF (bytes, not a real PDF — extract is mocked)."""
    p = tmp_path / "sample.pdf"
    p.write_bytes(b"%PDF-1.4 fake content for testing")
    return p


@pytest.fixture()
def fake_ground_truth(tmp_path: Path) -> Path:
    """Minimal FHIR Bundle JSON for use as ground-truth."""
    p = tmp_path / "ground-truth.json"
    p.write_text(
        json.dumps({"resourceType": "Bundle", "entry": []}),
        encoding="utf-8",
    )
    return p


@pytest.fixture()
def lab_root(tmp_path: Path) -> Path:
    """Isolated lab root — never touches data/pdf-lab/."""
    return tmp_path / "pdf-lab"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _stub_extract(self: Any, pdf_path: Path, *, recorder: RunRecorder | None = None, **kwargs: Any) -> dict:
    """Drop-in replacement for a pipeline's extract(). Simulates a successful
    run with one trace + final bundle so RunRecorder.finish() is reached."""
    if recorder is not None:
        recorder.log_pass(
            pass_name="document_context",
            prompt="stub prompt",
            response={},
            usage={
                "input_tokens": 100,
                "output_tokens": 50,
                "latency_ms": 1000,
                "cost_usd": 0.01,
            },
            extraction={"document_type": "lab-report"},
        )
        recorder.finish(
            bundle={"resourceType": "Bundle", "entry": []},
            status="succeeded",
        )
    return {"resourceType": "Bundle", "entry": []}


def _patch_all_pipelines(monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch extract() on every registered pipeline class so tests
    never hit a real LLM."""
    from lib.extract.pipelines.base import _REGISTRY

    for pipeline_cls in _REGISTRY._pipelines.values():
        monkeypatch.setattr(pipeline_cls, "extract", _stub_extract)


# ---------------------------------------------------------------------------
# 1. Single pipeline creates a run directory
# ---------------------------------------------------------------------------


def test_main_run_single_pipeline_creates_run_dir(
    fake_pdf: Path,
    lab_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running with one pipeline creates exactly one run dir under lab_root."""
    _patch_all_pipelines(monkeypatch)

    exit_code = main([
        "run",
        "--pipeline", "multipass-fhir",
        "--pdf", str(fake_pdf),
        "--root", str(lab_root),
    ])

    assert exit_code == 0, f"Expected exit code 0, got {exit_code}"
    runs_dir = lab_root / "runs"
    assert runs_dir.is_dir(), "runs/ directory should exist"
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1, f"Expected 1 run dir, got {len(run_dirs)}"
    assert (run_dirs[0] / "manifest.json").exists(), "manifest.json should exist"


# ---------------------------------------------------------------------------
# 2. Multiple pipelines create separate run directories
# ---------------------------------------------------------------------------


def test_main_run_multiple_pipelines_creates_separate_runs(
    fake_pdf: Path,
    lab_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passing --pipeline twice creates two distinct run directories."""
    _patch_all_pipelines(monkeypatch)

    exit_code = main([
        "run",
        "--pipeline", "multipass-fhir",
        "--pipeline", "single-pass-vision",
        "--pdf", str(fake_pdf),
        "--root", str(lab_root),
    ])

    assert exit_code == 0, f"Expected exit code 0, got {exit_code}"
    runs_dir = lab_root / "runs"
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 2, f"Expected 2 run dirs, got {len(run_dirs)}"

    # Verify the two runs belong to different pipelines
    manifests = []
    for rd in run_dirs:
        manifest_path = rd / "manifest.json"
        assert manifest_path.exists()
        manifests.append(json.loads(manifest_path.read_text()))

    pipeline_names = {m["pipeline_name"] for m in manifests}
    assert "multipass-fhir" in pipeline_names
    assert "single-pass-vision" in pipeline_names


# ---------------------------------------------------------------------------
# 3. Unknown pipeline name errors cleanly
# ---------------------------------------------------------------------------


def test_main_run_unknown_pipeline_errors_cleanly(
    fake_pdf: Path,
    lab_root: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    """Passing an unknown --pipeline name exits non-zero and names the pipeline."""
    exit_code = main([
        "run",
        "--pipeline", "xyzzy",
        "--pdf", str(fake_pdf),
        "--root", str(lab_root),
    ])

    assert exit_code != 0, "Expected non-zero exit for unknown pipeline"
    captured = capsys.readouterr()
    assert "unknown pipeline" in captured.err.lower() or "xyzzy" in captured.err, (
        f"stderr should mention the unknown pipeline name. Got: {captured.err!r}"
    )


# ---------------------------------------------------------------------------
# 4. Missing PDF errors cleanly
# ---------------------------------------------------------------------------


def test_main_run_missing_pdf_errors_cleanly(
    lab_root: Path,
    tmp_path: Path,
    capsys: pytest.CaptureFixture,
) -> None:
    """If the --pdf path doesn't exist, exit non-zero with a clear message."""
    missing = tmp_path / "nonexistent.pdf"

    exit_code = main([
        "run",
        "--pipeline", "multipass-fhir",
        "--pdf", str(missing),
        "--root", str(lab_root),
    ])

    assert exit_code != 0, "Expected non-zero exit for missing PDF"
    captured = capsys.readouterr()
    assert "not found" in captured.err.lower() or "pdf" in captured.err.lower(), (
        f"stderr should mention the missing file. Got: {captured.err!r}"
    )


# ---------------------------------------------------------------------------
# 5. --ground-truth is persisted in the run dir
# ---------------------------------------------------------------------------


def test_main_run_with_ground_truth_persists_it(
    fake_pdf: Path,
    fake_ground_truth: Path,
    lab_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Providing --ground-truth copies ground-truth.json into the run directory."""
    _patch_all_pipelines(monkeypatch)

    exit_code = main([
        "run",
        "--pipeline", "multipass-fhir",
        "--pdf", str(fake_pdf),
        "--ground-truth", str(fake_ground_truth),
        "--root", str(lab_root),
    ])

    assert exit_code == 0, f"Expected exit code 0, got {exit_code}"
    runs_dir = lab_root / "runs"
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1
    gt_file = run_dirs[0] / "ground-truth.json"
    assert gt_file.exists(), "ground-truth.json should be copied into the run dir"
    content = json.loads(gt_file.read_text())
    assert content["resourceType"] == "Bundle"


# ---------------------------------------------------------------------------
# 6. --list-pipelines prints registry and exits 0
# ---------------------------------------------------------------------------


def test_main_list_pipelines_prints_registry_and_exits(
    capsys: pytest.CaptureFixture,
) -> None:
    """--list-pipelines flag prints all registered pipelines and returns 0."""
    exit_code = main(["run", "--list-pipelines"])

    assert exit_code == 0, f"Expected exit code 0, got {exit_code}"
    captured = capsys.readouterr()
    assert "multipass-fhir" in captured.out, (
        f"Output should include 'multipass-fhir'. Got: {captured.out!r}"
    )


# ---------------------------------------------------------------------------
# 7. --help shows all subcommands
# ---------------------------------------------------------------------------


def test_main_help_shows_subcommands(capsys: pytest.CaptureFixture) -> None:
    """main(['--help']) raises SystemExit; the output lists all subcommands."""
    with pytest.raises(SystemExit) as exc_info:
        main(["--help"])

    # argparse exits 0 for --help
    assert exc_info.value.code == 0
    captured = capsys.readouterr()
    help_text = captured.out

    for subcommand in ("run", "compare", "show", "list", "report"):
        assert subcommand in help_text, (
            f"--help output should mention '{subcommand}'. Got: {help_text!r}"
        )


# ---------------------------------------------------------------------------
# 8. `compare` stub returns 2 with a helpful message
# ---------------------------------------------------------------------------


def test_main_compare_stub_returns_2_with_helpful_message(
    capsys: pytest.CaptureFixture,
) -> None:
    """`compare` subcommand is now implemented (LAB-T04). Calling it without
    required args exits 2 (argparse error for missing --run-a / --run-b)."""
    with pytest.raises(SystemExit) as exc_info:
        main(["compare"])

    assert exc_info.value.code == 2


# ---------------------------------------------------------------------------
# 9. No args errors
# ---------------------------------------------------------------------------


def test_main_no_args_errors() -> None:
    """main([]) should exit non-zero (argparse 'required=True' on subparsers)."""
    with pytest.raises(SystemExit) as exc_info:
        main([])

    assert exc_info.value.code != 0, "Empty args should produce a non-zero exit"


# ---------------------------------------------------------------------------
# 10. De-duplicates --pipeline names
# ---------------------------------------------------------------------------


def test_main_run_de_duplicates_pipeline_names(
    fake_pdf: Path,
    lab_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Passing the same --pipeline twice is treated as one run (de-duped)."""
    _patch_all_pipelines(monkeypatch)

    exit_code = main([
        "run",
        "--pipeline", "multipass-fhir",
        "--pipeline", "multipass-fhir",  # duplicate
        "--pdf", str(fake_pdf),
        "--root", str(lab_root),
    ])

    assert exit_code == 0, f"Expected exit code 0, got {exit_code}"
    runs_dir = lab_root / "runs"
    run_dirs = list(runs_dir.iterdir())
    assert len(run_dirs) == 1, (
        f"Duplicate --pipeline should produce only 1 run dir, got {len(run_dirs)}"
    )
