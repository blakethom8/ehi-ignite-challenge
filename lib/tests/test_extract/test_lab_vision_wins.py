"""Tests for lib.extract.lab.vision_wins — vision-wins triage workflow.

All tests use pytest's tmp_path as lab_root so they never write to
data/pdf-lab/. Tests are hermetic: input_fn / output_fn are injected
via parameters. No LLM calls, no real PDFs required.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from lib.extract.lab.vision_wins import (
    TriageSession,
    load_triage_session,
    run_triage,
)


# ---------------------------------------------------------------------------
# Shared test data helpers
# ---------------------------------------------------------------------------

FAKE_SHA = "deadbeef1234567890abcdef1234567890abcdef1234567890abcdef12345678"
FAKE_PDF_PATH = "/tmp/test-vision.pdf"


def _make_observation_resource(
    resource_id: str = "obs-1",
    text: str = "Glucose",
    loinc: str = "15074-8",
) -> dict:
    return {
        "resourceType": "Observation",
        "id": resource_id,
        "code": {
            "coding": [{"system": "http://loinc.org", "code": loinc, "display": text}],
            "text": text,
        },
    }


def _make_condition_resource(resource_id: str = "cond-1", text: str = "Hypertension") -> dict:
    return {
        "resourceType": "Condition",
        "id": resource_id,
        "code": {"text": text},
    }


def _make_bundle(*resources: dict) -> dict:
    return {
        "resourceType": "Bundle",
        "type": "collection",
        "entry": [{"resource": r} for r in resources],
    }


def _make_manifest(run_id: str = "run-001", pdf_sha: str = FAKE_SHA, pdf_path: str = FAKE_PDF_PATH) -> dict:
    return {
        "run_id": run_id,
        "pipeline_name": "test-pipeline",
        "pdf_path": pdf_path,
        "pdf_sha256": pdf_sha,
        "ground_truth_path": None,
        "started_at": "2026-05-07T10:00:00Z",
        "finished_at": "2026-05-07T10:00:05Z",
        "cost_usd": 0.01,
        "latency_ms": 5000,
        "sum_pass_latency_ms": 5000,
        "status": "succeeded",
        "error": None,
    }


def _make_eval(extracted_only: dict) -> dict:
    return {
        "weighted_f1": 0.5,
        "per_resource": {},
        "truth_only": {},
        "extracted_only": extracted_only,
        "total_truth": 5,
        "total_extracted": 7,
        "total_overlap": 4,
    }


def _make_run_dir(
    tmp_path: Path,
    *,
    run_id: str = "run-001",
    bundle: dict | None = None,
    eval_data: dict | None = None,
    write_eval: bool = True,
) -> Path:
    run_dir = tmp_path / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    (run_dir / "manifest.json").write_text(json.dumps(_make_manifest(run_id)))
    b = bundle or _make_bundle(
        _make_observation_resource("obs-1", "Glucose", "15074-8"),
        _make_condition_resource("cond-1", "Hypertension"),
    )
    (run_dir / "bundle.json").write_text(json.dumps(b))
    if write_eval:
        ev = eval_data or _make_eval({})
        (run_dir / "eval.json").write_text(json.dumps(ev))
    return run_dir


def _make_input_queue(*responses: str):
    queue = list(responses)

    def _input(prompt: str) -> str:
        if queue:
            return queue.pop(0)
        raise EOFError("input queue exhausted")

    return _input


def _collect_output():
    lines: list[str] = []

    def _output(msg: str) -> None:
        lines.append(msg)

    def get_lines() -> list[str]:
        return lines

    return _output, get_lines


def _make_gt_v1(tmp_path: Path, pdf_sha: str = FAKE_SHA, bundle: dict | None = None) -> None:
    """Create a v1 ground truth for the given PDF SHA."""
    from lib.extract.lab.ground_truth import save_ground_truth
    save_ground_truth(
        pdf_sha256=pdf_sha,
        pdf_path=FAKE_PDF_PATH,
        bundle=bundle or _make_bundle(_make_condition_resource("cond-gt-1", "Diabetes")),
        reviewer="tester",
        lab_root=tmp_path,
    )


# ---------------------------------------------------------------------------
# Test 1: load_triage_session reads eval.json and bundle.json
# ---------------------------------------------------------------------------


def test_load_triage_session_reads_eval_and_bundle(tmp_path: Path) -> None:
    extracted_only = {
        "Observation": [{"display": "Glucose", "code": "15074-8"}],
        "Condition": [{"display": "Hypertension", "code": None}],
    }
    bundle = _make_bundle(
        _make_observation_resource("obs-1", "Glucose", "15074-8"),
        _make_condition_resource("cond-1", "Hypertension"),
    )
    _make_run_dir(tmp_path, run_id="run-001", bundle=bundle, eval_data=_make_eval(extracted_only))

    session = load_triage_session("run-001", lab_root=tmp_path)

    assert session.run_id == "run-001"
    assert "Observation" in session.extracted_only
    assert len(session.extracted_only["Observation"]) == 1
    assert session.extracted_only["Observation"][0]["display"] == "Glucose"
    assert "Condition" in session.extracted_only
    # extracted_resources should contain both the obs and the condition
    resource_types = {r.get("resourceType") for r in session.extracted_resources}
    assert "Observation" in resource_types
    assert "Condition" in resource_types
    assert session.pdf_sha256 == FAKE_SHA
    assert session.next_index == 0
    assert session.verdicts == []


# ---------------------------------------------------------------------------
# Test 2: load_triage_session raises for unknown run
# ---------------------------------------------------------------------------


def test_load_triage_session_unknown_run_raises(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError, match="run not found"):
        load_triage_session("no-such-run", lab_root=tmp_path)


# ---------------------------------------------------------------------------
# Test 3: load_triage_session raises when eval.json is missing
# ---------------------------------------------------------------------------


def test_load_triage_session_no_eval_json_raises(tmp_path: Path) -> None:
    _make_run_dir(tmp_path, run_id="run-noeval", write_eval=False)
    with pytest.raises(FileNotFoundError, match="no eval.json"):
        load_triage_session("run-noeval", lab_root=tmp_path)


# ---------------------------------------------------------------------------
# Test 4: valid_extra marks incorporate into a new GT version
# ---------------------------------------------------------------------------


def test_run_triage_valid_extra_incorporates_into_new_gt_version(tmp_path: Path) -> None:
    extracted_only = {
        "Observation": [
            {"display": "Glucose", "code": "15074-8"},
            {"display": "HbA1c", "code": "4548-4"},
        ],
    }
    bundle = _make_bundle(
        _make_observation_resource("obs-1", "Glucose", "15074-8"),
        _make_observation_resource("obs-2", "HbA1c", "4548-4"),
    )
    _make_run_dir(tmp_path, run_id="run-001", bundle=bundle, eval_data=_make_eval(extracted_only))
    _make_gt_v1(tmp_path)  # creates v1 GT

    output_fn, get_lines = _collect_output()

    # mark both as valid_extra
    status, version = run_triage(
        load_triage_session("run-001", lab_root=tmp_path),
        reviewer="tester",
        input_fn=_make_input_queue("v", "v"),
        output_fn=output_fn,
        auto_save_every=0,
        lab_root=tmp_path,
    )

    assert status == "completed"
    assert version == 2  # new GT version

    from lib.extract.lab.ground_truth import load_latest_ground_truth
    gtv = load_latest_ground_truth(FAKE_SHA, lab_root=tmp_path)
    assert gtv is not None
    assert gtv.version == 2
    # v1 had 1 entry (Diabetes), v2 should have 1 + 2 = 3
    assert len(gtv.bundle["entry"]) == 3


# ---------------------------------------------------------------------------
# Test 5: hallucination does not modify GT
# ---------------------------------------------------------------------------


def test_run_triage_hallucination_does_not_modify_gt(tmp_path: Path) -> None:
    extracted_only = {
        "Observation": [{"display": "Glucose", "code": "15074-8"}],
    }
    _make_run_dir(tmp_path, run_id="run-001", eval_data=_make_eval(extracted_only))
    _make_gt_v1(tmp_path)

    output_fn, _ = _collect_output()

    status, version = run_triage(
        load_triage_session("run-001", lab_root=tmp_path),
        reviewer="tester",
        input_fn=_make_input_queue("h"),
        output_fn=output_fn,
        auto_save_every=0,
        lab_root=tmp_path,
    )

    assert status == "completed"
    assert version is None  # no new GT

    from lib.extract.lab.ground_truth import list_ground_truth_versions
    versions = list_ground_truth_versions(FAKE_SHA, lab_root=tmp_path)
    assert versions == [1]  # v1 unchanged


# ---------------------------------------------------------------------------
# Test 6: out_of_scope does not modify GT
# ---------------------------------------------------------------------------


def test_run_triage_out_of_scope_does_not_modify_gt(tmp_path: Path) -> None:
    extracted_only = {
        "Condition": [{"display": "Some free text condition", "code": None}],
    }
    _make_run_dir(tmp_path, run_id="run-001", eval_data=_make_eval(extracted_only))
    _make_gt_v1(tmp_path)

    output_fn, _ = _collect_output()

    status, version = run_triage(
        load_triage_session("run-001", lab_root=tmp_path),
        reviewer="tester",
        input_fn=_make_input_queue("o"),
        output_fn=output_fn,
        auto_save_every=0,
        lab_root=tmp_path,
    )

    assert status == "completed"
    assert version is None

    from lib.extract.lab.ground_truth import list_ground_truth_versions
    assert list_ground_truth_versions(FAKE_SHA, lab_root=tmp_path) == [1]


# ---------------------------------------------------------------------------
# Test 7: completion writes vision_wins_verdicts.json
# ---------------------------------------------------------------------------


def test_run_triage_writes_verdicts_file(tmp_path: Path) -> None:
    extracted_only = {
        "Observation": [{"display": "Glucose", "code": "15074-8"}],
    }
    _make_run_dir(tmp_path, run_id="run-001", eval_data=_make_eval(extracted_only))
    _make_gt_v1(tmp_path)

    output_fn, _ = _collect_output()

    session = load_triage_session("run-001", lab_root=tmp_path)
    run_triage(
        session,
        reviewer="tester",
        input_fn=_make_input_queue("h"),
        output_fn=output_fn,
        auto_save_every=0,
        lab_root=tmp_path,
    )

    verdicts_path = session.run_dir / "vision_wins_verdicts.json"
    assert verdicts_path.exists(), "vision_wins_verdicts.json must be written on completion"

    data = json.loads(verdicts_path.read_text())
    assert data["run_id"] == "run-001"
    assert data["reviewer"] == "tester"
    assert len(data["verdicts"]) == 1
    assert data["verdicts"][0]["verdict"] == "hallucination"
    assert "completed_at" in data


# ---------------------------------------------------------------------------
# Test 8: quit-and-save writes sidecar, no completion file
# ---------------------------------------------------------------------------


def test_run_triage_quit_and_save_writes_sidecar(tmp_path: Path) -> None:
    extracted_only = {
        "Observation": [
            {"display": "Glucose", "code": "15074-8"},
            {"display": "HbA1c", "code": "4548-4"},
        ],
    }
    _make_run_dir(tmp_path, run_id="run-001", eval_data=_make_eval(extracted_only))

    output_fn, _ = _collect_output()

    session = load_triage_session("run-001", lab_root=tmp_path)

    # verdict on first, then quit
    status, version = run_triage(
        session,
        reviewer="tester",
        input_fn=_make_input_queue("h", "q"),
        output_fn=output_fn,
        auto_save_every=0,
        lab_root=tmp_path,
    )

    assert status == "saved-partial"
    assert version is None

    sidecar = session.run_dir / "vision_wins_in_progress.json"
    assert sidecar.exists(), "sidecar must exist after quit-and-save"
    progress = json.loads(sidecar.read_text())
    assert progress["next_index"] == 1
    assert len(progress["verdicts"]) == 1

    verdicts_path = session.run_dir / "vision_wins_verdicts.json"
    assert not verdicts_path.exists(), "completion file must NOT exist after partial save"


# ---------------------------------------------------------------------------
# Test 9: resumes from sidecar with correct next_index
# ---------------------------------------------------------------------------


def test_run_triage_resumes_from_sidecar(tmp_path: Path) -> None:
    extracted_only = {
        "Observation": [
            {"display": "Glucose", "code": "15074-8"},
            {"display": "HbA1c", "code": "4548-4"},
            {"display": "Sodium", "code": "2951-2"},
        ],
    }
    run_dir = _make_run_dir(tmp_path, run_id="run-001", eval_data=_make_eval(extracted_only))

    # Write a sidecar showing 2 verdicts already done, cursor at 2
    sidecar_data = {
        "run_id": "run-001",
        "verdicts": [
            {
                "resource_type": "Observation", "fact_display": "Glucose", "fact_code": "15074-8",
                "verdict": "hallucination", "reviewer": "tester", "reviewed_at": "2026-05-07T10:00:00Z",
            },
            {
                "resource_type": "Observation", "fact_display": "HbA1c", "fact_code": "4548-4",
                "verdict": "out_of_scope", "reviewer": "tester", "reviewed_at": "2026-05-07T10:00:01Z",
            },
        ],
        "next_index": 2,
    }
    (run_dir / "vision_wins_in_progress.json").write_text(json.dumps(sidecar_data))

    session = load_triage_session("run-001", lab_root=tmp_path)
    assert session.next_index == 2
    assert len(session.verdicts) == 2

    output_fn, get_lines = _collect_output()

    # Only one fact remains
    status, _ = run_triage(
        session,
        reviewer="tester",
        input_fn=_make_input_queue("h"),
        output_fn=output_fn,
        auto_save_every=0,
        lab_root=tmp_path,
    )

    assert status == "completed"
    all_output = "\n".join(get_lines())
    assert "Resuming at fact #3" in all_output


# ---------------------------------------------------------------------------
# Test 10: skip does not modify GT
# ---------------------------------------------------------------------------


def test_run_triage_skip_does_not_modify_gt(tmp_path: Path) -> None:
    extracted_only = {
        "Condition": [{"display": "Obesity", "code": None}],
    }
    _make_run_dir(tmp_path, run_id="run-001", eval_data=_make_eval(extracted_only))
    _make_gt_v1(tmp_path)

    output_fn, _ = _collect_output()

    status, version = run_triage(
        load_triage_session("run-001", lab_root=tmp_path),
        reviewer="tester",
        input_fn=_make_input_queue("s"),
        output_fn=output_fn,
        auto_save_every=0,
        lab_root=tmp_path,
    )

    assert status == "completed"
    assert version is None

    from lib.extract.lab.ground_truth import list_ground_truth_versions
    assert list_ground_truth_versions(FAKE_SHA, lab_root=tmp_path) == [1]


# ---------------------------------------------------------------------------
# Test 11: unknown command re-prompts, then v is accepted
# ---------------------------------------------------------------------------


def test_run_triage_unknown_command_re_prompts(tmp_path: Path) -> None:
    extracted_only = {
        "Observation": [{"display": "Glucose", "code": "15074-8"}],
    }
    _make_run_dir(tmp_path, run_id="run-001", eval_data=_make_eval(extracted_only))
    _make_gt_v1(tmp_path)

    output_fn, get_lines = _collect_output()

    # "zzz" is unknown, then "v" accepts as valid_extra
    status, version = run_triage(
        load_triage_session("run-001", lab_root=tmp_path),
        reviewer="tester",
        input_fn=_make_input_queue("zzz", "v"),
        output_fn=output_fn,
        auto_save_every=0,
        lab_root=tmp_path,
    )

    assert status == "completed"
    all_output = "\n".join(get_lines())
    assert "Unknown command" in all_output
    # valid_extra → new GT should exist
    assert version == 2


# ---------------------------------------------------------------------------
# Test 12: no existing GT warns for valid_extra but still saves verdicts
# ---------------------------------------------------------------------------


def test_run_triage_no_existing_gt_warns_for_valid_extra(tmp_path: Path) -> None:
    extracted_only = {
        "Observation": [{"display": "Glucose", "code": "15074-8"}],
    }
    bundle = _make_bundle(_make_observation_resource("obs-1", "Glucose", "15074-8"))
    _make_run_dir(tmp_path, run_id="run-001", bundle=bundle, eval_data=_make_eval(extracted_only))
    # Intentionally do NOT create a GT for this PDF sha

    output_fn, get_lines = _collect_output()

    status, version = run_triage(
        load_triage_session("run-001", lab_root=tmp_path),
        reviewer="tester",
        input_fn=_make_input_queue("v"),
        output_fn=output_fn,
        auto_save_every=0,
        lab_root=tmp_path,
    )

    assert status == "completed"
    assert version is None  # no GT created

    # Warning should appear in output
    all_output = "\n".join(get_lines())
    assert "Warning" in all_output or "warning" in all_output.lower()

    # Verdicts still saved
    run_dir = tmp_path / "runs" / "run-001"
    verdicts_path = run_dir / "vision_wins_verdicts.json"
    assert verdicts_path.exists()
    data = json.loads(verdicts_path.read_text())
    assert len(data["verdicts"]) == 1
    assert data["verdicts"][0]["verdict"] == "valid_extra"


# ---------------------------------------------------------------------------
# Test 13: CLI triage unknown run exits 2
# ---------------------------------------------------------------------------


def test_cli_triage_unknown_run_exits_2(tmp_path: Path) -> None:
    from lib.extract.lab.cli import main

    result = main(["triage", "--run", "nonexistent-run", "--reviewer", "tester", "--root", str(tmp_path)])
    assert result == 2


# ---------------------------------------------------------------------------
# Test 14: CLI triage completes returns 0
# ---------------------------------------------------------------------------


def test_cli_triage_completes_returns_0(tmp_path: Path) -> None:
    from unittest.mock import patch
    from lib.extract.lab.cli import main

    extracted_only = {
        "Observation": [{"display": "Glucose", "code": "15074-8"}],
    }
    bundle = _make_bundle(_make_observation_resource("obs-1", "Glucose", "15074-8"))
    _make_run_dir(tmp_path, run_id="run-cli", bundle=bundle, eval_data=_make_eval(extracted_only))
    _make_gt_v1(tmp_path)

    # Patch run_triage inside the vision_wins module to avoid interactive input
    with patch("lib.extract.lab.vision_wins.run_triage") as mock_triage:
        mock_triage.return_value = ("completed", None)
        result = main([
            "triage",
            "--run", "run-cli",
            "--reviewer", "cli-tester",
            "--root", str(tmp_path),
        ])

    assert result == 0
    assert mock_triage.called
