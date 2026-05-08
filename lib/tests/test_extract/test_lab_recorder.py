"""Tests for lib.extract.lab.recorder — RunRecorder lifecycle.

All tests use pytest's tmp_path fixture as root so they don't write to
data/pdf-lab/.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict
from pathlib import Path

import pytest

from lib.extract.lab.recorder import RunRecorder, RunManifest


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_pdf(tmp_path: Path) -> Path:
    """A small synthetic PDF stand-in (just bytes, not a real PDF)."""
    p = tmp_path / "sample.pdf"
    p.write_bytes(b"%PDF-1.4 fake content for testing")
    return p


@pytest.fixture()
def fake_ground_truth(tmp_path: Path) -> Path:
    """A minimal FHIR Bundle JSON file as ground truth."""
    p = tmp_path / "ground-truth.json"
    p.write_text(json.dumps({"resourceType": "Bundle", "entry": []}), encoding="utf-8")
    return p


@pytest.fixture()
def lab_root(tmp_path: Path) -> Path:
    """Isolated lab root so each test gets a clean slate."""
    return tmp_path / "pdf-lab"


@pytest.fixture()
def started_recorder(fake_pdf: Path, lab_root: Path) -> RunRecorder:
    """A recorder that has been started but not yet logged any passes."""
    return RunRecorder.start(
        pipeline_name="test-pipeline",
        pdf_path=fake_pdf,
        root=lab_root,
    )


# ---------------------------------------------------------------------------
# 1. start() creates the run directory and manifest.json
# ---------------------------------------------------------------------------


def test_recorder_start_creates_run_dir(fake_pdf: Path, lab_root: Path) -> None:
    recorder = RunRecorder.start(
        pipeline_name="test-pipeline",
        pdf_path=fake_pdf,
        root=lab_root,
    )
    run_dir = lab_root / "runs" / recorder.run_id
    assert run_dir.exists(), "run directory should exist after start()"
    manifest_path = run_dir / "manifest.json"
    assert manifest_path.exists(), "manifest.json should be written by start()"

    manifest = json.loads(manifest_path.read_text())
    assert manifest["status"] == "running"
    assert manifest["started_at"] is not None
    assert manifest["finished_at"] is None


# ---------------------------------------------------------------------------
# 2. run_id matches expected format
# ---------------------------------------------------------------------------


def test_recorder_run_id_format(fake_pdf: Path, lab_root: Path) -> None:
    recorder = RunRecorder.start(
        pipeline_name="multipass-fhir",
        pdf_path=fake_pdf,
        root=lab_root,
    )
    # Format: YYYY-MM-DDThh-mm-ss_<6 hex chars>_<pipeline-name>
    pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}-\d{2}-\d{2}_[0-9a-f]{6}_multipass-fhir$'
    assert re.match(pattern, recorder.run_id), (
        f"run_id {recorder.run_id!r} does not match expected pattern"
    )


# ---------------------------------------------------------------------------
# 3. start() copies the PDF to source.pdf
# ---------------------------------------------------------------------------


def test_recorder_start_copies_pdf(fake_pdf: Path, lab_root: Path) -> None:
    recorder = RunRecorder.start(
        pipeline_name="test-pipeline",
        pdf_path=fake_pdf,
        root=lab_root,
    )
    source_pdf = recorder.root / "source.pdf"
    assert source_pdf.exists(), "source.pdf should be copied into the run dir"
    assert source_pdf.read_bytes() == fake_pdf.read_bytes()


# ---------------------------------------------------------------------------
# 4. start() copies ground_truth_path when provided
# ---------------------------------------------------------------------------


def test_recorder_start_copies_ground_truth_when_provided(
    fake_pdf: Path, fake_ground_truth: Path, lab_root: Path
) -> None:
    recorder = RunRecorder.start(
        pipeline_name="test-pipeline",
        pdf_path=fake_pdf,
        ground_truth_path=fake_ground_truth,
        root=lab_root,
    )
    gt_file = recorder.root / "ground-truth.json"
    assert gt_file.exists(), "ground-truth.json should be copied when ground_truth_path provided"
    assert json.loads(gt_file.read_text()) == json.loads(fake_ground_truth.read_text())


# ---------------------------------------------------------------------------
# 5. start() without ground_truth does not create ground-truth.json
# ---------------------------------------------------------------------------


def test_recorder_start_no_ground_truth(fake_pdf: Path, lab_root: Path) -> None:
    recorder = RunRecorder.start(
        pipeline_name="test-pipeline",
        pdf_path=fake_pdf,
        root=lab_root,
    )
    gt_file = recorder.root / "ground-truth.json"
    assert not gt_file.exists(), "ground-truth.json should NOT exist when ground_truth_path omitted"


# ---------------------------------------------------------------------------
# 6. log_pass() persists all four files
# ---------------------------------------------------------------------------


def test_log_pass_persists_all_four_files(started_recorder: RunRecorder) -> None:
    started_recorder.log_pass(
        pass_name="conditions",
        prompt="System: extract conditions...",
        response={"id": "msg_abc", "content": [{"type": "text", "text": "..."}]},
        usage={"input_tokens": 100, "output_tokens": 50, "latency_ms": 1200, "cost_usd": 0.05},
        extraction={"conditions": [{"display": "Hypertension"}]},
    )

    trace_dir = started_recorder.root / "traces" / "conditions"
    assert (trace_dir / "prompt.txt").exists()
    assert (trace_dir / "response.json").exists()
    assert (trace_dir / "usage.json").exists()
    assert (trace_dir / "extraction.json").exists()

    assert (trace_dir / "prompt.txt").read_text() == "System: extract conditions..."
    assert json.loads((trace_dir / "extraction.json").read_text()) == {"conditions": [{"display": "Hypertension"}]}


# ---------------------------------------------------------------------------
# 7. log_pass() with extraction=None — no extraction.json created
# ---------------------------------------------------------------------------


def test_log_pass_extraction_optional(started_recorder: RunRecorder) -> None:
    started_recorder.log_pass(
        pass_name="document_context",
        prompt="Extract document context...",
        response={"id": "msg_xyz"},
        usage={"input_tokens": 80, "output_tokens": 30, "latency_ms": 900, "cost_usd": 0.03},
        extraction=None,
    )
    trace_dir = started_recorder.root / "traces" / "document_context"
    assert (trace_dir / "prompt.txt").exists()
    assert (trace_dir / "response.json").exists()
    assert (trace_dir / "usage.json").exists()
    assert not (trace_dir / "extraction.json").exists(), (
        "extraction.json should NOT be written when extraction=None"
    )


# ---------------------------------------------------------------------------
# 8. log_pass() updates running cost and latency on manifest
# ---------------------------------------------------------------------------


def test_log_pass_accumulates_running_cost(started_recorder: RunRecorder) -> None:
    """log_pass() accumulates cost; per-pass latencies go to
    sum_pass_latency_ms (so we can compute parallelism factor later).
    The headline `latency_ms` is wall-clock and is set in finish()."""
    started_recorder.log_pass(
        pass_name="pass_one",
        prompt="...",
        response={},
        usage={"input_tokens": 100, "output_tokens": 50, "latency_ms": 1500, "cost_usd": 0.05},
    )
    started_recorder.log_pass(
        pass_name="pass_two",
        prompt="...",
        response={},
        usage={"input_tokens": 200, "output_tokens": 100, "latency_ms": 2500, "cost_usd": 0.10},
    )

    # Cost accumulates (genuinely sum across passes)
    assert abs(started_recorder.manifest.cost_usd - 0.15) < 1e-9
    # Per-pass latency sum accumulates separately
    assert started_recorder.manifest.sum_pass_latency_ms == 4000
    # Wall-clock latency is NOT set yet (finish() hasn't been called)
    assert started_recorder.manifest.latency_ms == 0

    # Also verify that manifest.json on disk reflects the running totals
    manifest_on_disk = json.loads(
        (started_recorder.root / "manifest.json").read_text()
    )
    assert abs(manifest_on_disk["cost_usd"] - 0.15) < 1e-9
    assert manifest_on_disk["sum_pass_latency_ms"] == 4000
    assert manifest_on_disk["latency_ms"] == 0


def test_finish_sets_wall_clock_latency_from_timestamps(
    started_recorder: RunRecorder,
) -> None:
    """latency_ms is computed from started_at → finished_at when finish()
    runs. Even when per-pass latencies sum to a much larger number (parallel
    dispatch), the wall-clock time on the manifest reflects actual elapsed."""
    import time

    # Log two passes whose per-pass latencies sum to 4 seconds
    started_recorder.log_pass(
        pass_name="pass_one",
        prompt="...",
        response={},
        usage={"latency_ms": 1500, "cost_usd": 0.05},
    )
    started_recorder.log_pass(
        pass_name="pass_two",
        prompt="...",
        response={},
        usage={"latency_ms": 2500, "cost_usd": 0.10},
    )
    # Real elapsed will be a tiny fraction of a second — much less than 4000ms.
    time.sleep(0.05)
    started_recorder.finish(bundle={"resourceType": "Bundle", "entry": []})

    # latency_ms now reflects WALL CLOCK (much less than 4000ms)
    assert started_recorder.manifest.latency_ms < 4000
    assert started_recorder.manifest.latency_ms >= 0
    # sum_pass_latency_ms preserves the per-pass total
    assert started_recorder.manifest.sum_pass_latency_ms == 4000


# ---------------------------------------------------------------------------
# 9. log_pass() sanitizes / rejects invalid pass names
# ---------------------------------------------------------------------------


def test_log_pass_sanitizes_pass_name(started_recorder: RunRecorder) -> None:
    """Pass names with dots or slashes should raise ValueError."""
    with pytest.raises(ValueError, match="invalid characters"):
        started_recorder.log_pass(
            pass_name="pass.name",
            prompt="...",
            response={},
            usage={},
        )

    with pytest.raises(ValueError, match="invalid characters"):
        started_recorder.log_pass(
            pass_name="pass/name",
            prompt="...",
            response={},
            usage={},
        )


# ---------------------------------------------------------------------------
# 10. finish() writes bundle.json + eval.json + bundle_shape.json
# ---------------------------------------------------------------------------


def test_finish_writes_bundle_and_eval_and_bundle_shape(started_recorder: RunRecorder) -> None:
    bundle = {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Patient"}}]}
    eval_result = {"weighted_f1": 0.87, "conditions_f1": 0.92}
    bundle_shape = {"patient_count": 1, "encounter_count": 3}

    started_recorder.finish(
        bundle=bundle,
        eval_result=eval_result,
        bundle_shape=bundle_shape,
    )

    run_dir = started_recorder.root
    assert (run_dir / "bundle.json").exists()
    assert (run_dir / "eval.json").exists()
    assert (run_dir / "bundle_shape.json").exists()

    assert json.loads((run_dir / "bundle.json").read_text()) == bundle
    assert json.loads((run_dir / "eval.json").read_text()) == eval_result
    assert json.loads((run_dir / "bundle_shape.json").read_text()) == bundle_shape


# ---------------------------------------------------------------------------
# 11. finish() appends exactly one line per run to runs.jsonl
# ---------------------------------------------------------------------------


def test_finish_appends_to_runs_jsonl(fake_pdf: Path, lab_root: Path) -> None:
    rec1 = RunRecorder.start(pipeline_name="pipe-a", pdf_path=fake_pdf, root=lab_root)
    rec1.finish(bundle={"resourceType": "Bundle", "entry": []})

    rec2 = RunRecorder.start(pipeline_name="pipe-b", pdf_path=fake_pdf, root=lab_root)
    rec2.finish(bundle={"resourceType": "Bundle", "entry": []})

    runs_jsonl = lab_root / "runs.jsonl"
    assert runs_jsonl.exists()
    lines = [l for l in runs_jsonl.read_text().splitlines() if l.strip()]
    assert len(lines) == 2, f"Expected 2 lines in runs.jsonl, got {len(lines)}"

    entry1 = json.loads(lines[0])
    entry2 = json.loads(lines[1])

    assert entry1["run_id"] == rec1.run_id
    assert entry2["run_id"] == rec2.run_id
    assert entry1["pipeline_name"] == "pipe-a"
    assert entry2["pipeline_name"] == "pipe-b"


# ---------------------------------------------------------------------------
# 12. finish() marks status as "succeeded" and sets finished_at
# ---------------------------------------------------------------------------


def test_finish_marks_status_succeeded(started_recorder: RunRecorder) -> None:
    started_recorder.finish(bundle={"resourceType": "Bundle", "entry": []})

    assert started_recorder.manifest.status == "succeeded"
    assert started_recorder.manifest.finished_at is not None

    manifest_on_disk = json.loads(
        (started_recorder.root / "manifest.json").read_text()
    )
    assert manifest_on_disk["status"] == "succeeded"
    assert manifest_on_disk["finished_at"] is not None


# ---------------------------------------------------------------------------
# 13. finish() with status="failed" captures error string
# ---------------------------------------------------------------------------


def test_finish_with_failure(started_recorder: RunRecorder) -> None:
    started_recorder.finish(
        bundle={},
        status="failed",
        error="LLM timeout after 60s",
    )

    assert started_recorder.manifest.status == "failed"
    assert started_recorder.manifest.error == "LLM timeout after 60s"

    manifest_on_disk = json.loads(
        (started_recorder.root / "manifest.json").read_text()
    )
    assert manifest_on_disk["status"] == "failed"
    assert manifest_on_disk["error"] == "LLM timeout after 60s"


# ---------------------------------------------------------------------------
# 14. finish() is not idempotent — second call raises RuntimeError
# ---------------------------------------------------------------------------


def test_finish_idempotent_on_duplicate_call(
    started_recorder: RunRecorder, lab_root: Path
) -> None:
    """Calling finish() a second time should raise RuntimeError so we never
    double-append to runs.jsonl or silently overwrite final artifacts."""
    started_recorder.finish(bundle={"resourceType": "Bundle", "entry": []})

    with pytest.raises(RuntimeError, match="already in status"):
        started_recorder.finish(bundle={"resourceType": "Bundle", "entry": []})

    # runs.jsonl should have exactly one entry — not two
    runs_jsonl = lab_root / "runs.jsonl"
    lines = [l for l in runs_jsonl.read_text().splitlines() if l.strip()]
    assert len(lines) == 1, "runs.jsonl should have exactly 1 line after two finish() calls"
