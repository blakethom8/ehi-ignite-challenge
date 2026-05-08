"""Tests for LAB-T02 — RunRecorder integration in MultiPassFHIRPipeline.extract().

Tests use monkeypatch (Approach A) to stub _run_pass and _invoke_pass_0 so
no real LLM is invoked. We exercise the recorder hook-up only.

All tests write to tmp_path so data/pdf-lab/ is never touched.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest

from lib.extract.lab.cost import estimate_cost
from lib.extract.lab.recorder import RunRecorder
from lib.extract.pipelines.multipass_fhir import (
    ConditionExtraction,
    DocumentContext,
    MultiPassFHIRPipeline,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture()
def fake_pdf(tmp_path: Path) -> Path:
    """Minimal fake PDF file."""
    p = tmp_path / "sample.pdf"
    p.write_bytes(b"%PDF-1.4 fake content for testing")
    return p


@pytest.fixture()
def lab_root(tmp_path: Path) -> Path:
    """Isolated lab root — never touches data/pdf-lab/."""
    return tmp_path / "pdf-lab"


@pytest.fixture()
def recorder(fake_pdf: Path, lab_root: Path) -> RunRecorder:
    """A started RunRecorder backed by tmp_path."""
    return RunRecorder.start(
        pipeline_name="multipass-fhir",
        pdf_path=fake_pdf,
        root=lab_root,
    )


def _make_doc_context() -> DocumentContext:
    return DocumentContext(
        document_type="lab-report",
        patient_name="Test Patient",
        patient_dob="1980-01-01",
        encounter_date="2026-01-01",
        ordering_provider="Dr. Test",
        facility_name="Test Lab",
    )


def _stub_invoke_pass_0(pipeline: MultiPassFHIRPipeline, monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch _invoke_pass_0 to return a deterministic DocumentContext."""
    ctx = _make_doc_context()
    monkeypatch.setattr(pipeline, "_invoke_pass_0", lambda **kwargs: ctx)


def _stub_run_pass_conditions(pipeline: MultiPassFHIRPipeline, monkeypatch: pytest.MonkeyPatch) -> None:
    """Monkeypatch _run_pass to return a ConditionExtraction with one entry."""
    from lib.extract.pipelines.multipass_fhir import ConditionEntry

    result = ConditionExtraction(
        conditions=[
            ConditionEntry(display="Hypertension", clinical_status="active")
        ]
    )

    original_run_pass = pipeline._run_pass

    def fake_run_pass(*, pass_name: str, schema: Any, **kwargs: Any) -> Any:
        return result if "condition" in pass_name else schema()

    monkeypatch.setattr(pipeline, "_run_pass", fake_run_pass)


def _stub_specialist_passes_conditions_only(
    pipeline: MultiPassFHIRPipeline, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Monkeypatch _specialist_passes to return only the conditions pass."""
    from lib.extract.pipelines.multipass_fhir import _PASSES

    conditions_pass = next(p for p in _PASSES if p.name == "conditions")
    monkeypatch.setattr(pipeline, "_specialist_passes", lambda ctx: [conditions_pass])


def _make_pipeline() -> MultiPassFHIRPipeline:
    """Pipeline with a known model name for cost assertions."""
    return MultiPassFHIRPipeline(model="claude-sonnet-4-6")


# ---------------------------------------------------------------------------
# Test 1: recorder writes traces/<pass-name>/ for each pass that ran
# ---------------------------------------------------------------------------


def test_extract_with_recorder_writes_traces_for_each_pass(
    fake_pdf: Path,
    recorder: RunRecorder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running extract() with a recorder produces a traces/<pass-name>/
    directory for each pass that ran, including document_context (Pass 0)
    and every specialist pass.
    """
    pipeline = _make_pipeline()
    _stub_invoke_pass_0(pipeline, monkeypatch)
    _stub_specialist_passes_conditions_only(pipeline, monkeypatch)
    _stub_run_pass_conditions(pipeline, monkeypatch)

    # Also stub _merge_to_bundle to avoid real FHIR conversion
    monkeypatch.setattr(
        pipeline,
        "_merge_to_bundle",
        lambda **kwargs: {"resourceType": "Bundle", "entry": []},
    )
    monkeypatch.setattr(pipeline, "_safe_extract_layout", lambda pdf_path: None)

    pipeline.extract(fake_pdf, recorder=recorder)

    traces_dir = recorder.root / "traces"
    assert (traces_dir / "document_context").is_dir(), (
        "Pass 0 should write traces/document_context/"
    )
    assert (traces_dir / "conditions").is_dir(), (
        "Conditions specialist pass should write traces/conditions/"
    )


# ---------------------------------------------------------------------------
# Test 2: no recorder → no traces directory created, no manifest changes
# ---------------------------------------------------------------------------


def test_extract_without_recorder_unchanged_behavior(
    fake_pdf: Path,
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Calling extract(pdf) without recorder kwarg works exactly as before —
    no side effects, no traces dir, no RunRecorder involved.
    """
    pipeline = _make_pipeline()
    _stub_invoke_pass_0(pipeline, monkeypatch)
    _stub_specialist_passes_conditions_only(pipeline, monkeypatch)
    _stub_run_pass_conditions(pipeline, monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "_merge_to_bundle",
        lambda **kwargs: {"resourceType": "Bundle", "entry": []},
    )
    monkeypatch.setattr(pipeline, "_safe_extract_layout", lambda pdf_path: None)

    # No recorder argument — this is the production calling convention
    result = pipeline.extract(fake_pdf)

    assert result == {"resourceType": "Bundle", "entry": []}
    # No pdf-lab directory should exist in tmp_path
    lab_runs = tmp_path / "pdf-lab" / "runs"
    assert not lab_runs.exists(), "No lab run directory should be created without a recorder"


# ---------------------------------------------------------------------------
# Test 3: recorder captures the actual prompt text for Pass 0
# ---------------------------------------------------------------------------


def test_recorder_captures_prompt_text(
    fake_pdf: Path,
    recorder: RunRecorder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The recorded prompt.txt for Pass 0 matches _pass_0_prompt()."""
    pipeline = _make_pipeline()
    expected_prompt = pipeline._pass_0_prompt()

    _stub_invoke_pass_0(pipeline, monkeypatch)
    _stub_specialist_passes_conditions_only(pipeline, monkeypatch)
    _stub_run_pass_conditions(pipeline, monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "_merge_to_bundle",
        lambda **kwargs: {"resourceType": "Bundle", "entry": []},
    )
    monkeypatch.setattr(pipeline, "_safe_extract_layout", lambda pdf_path: None)

    pipeline.extract(fake_pdf, recorder=recorder)

    prompt_txt = (recorder.root / "traces" / "document_context" / "prompt.txt").read_text()
    assert prompt_txt == expected_prompt, (
        f"Recorded prompt does not match _pass_0_prompt(). "
        f"Got: {prompt_txt[:120]!r}"
    )


# ---------------------------------------------------------------------------
# Test 4: usage.json has the expected keys populated
# ---------------------------------------------------------------------------


def test_recorder_captures_token_usage_per_pass(
    fake_pdf: Path,
    recorder: RunRecorder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """usage.json for each pass contains input_tokens, output_tokens,
    latency_ms, cost_usd, and estimated=True (since backends don't expose
    raw token counts).
    """
    pipeline = _make_pipeline()
    _stub_invoke_pass_0(pipeline, monkeypatch)
    _stub_specialist_passes_conditions_only(pipeline, monkeypatch)
    _stub_run_pass_conditions(pipeline, monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "_merge_to_bundle",
        lambda **kwargs: {"resourceType": "Bundle", "entry": []},
    )
    monkeypatch.setattr(pipeline, "_safe_extract_layout", lambda pdf_path: None)

    pipeline.extract(fake_pdf, recorder=recorder)

    for pass_name in ("document_context", "conditions"):
        usage_path = recorder.root / "traces" / pass_name / "usage.json"
        assert usage_path.exists(), f"usage.json missing for pass {pass_name!r}"
        usage = json.loads(usage_path.read_text())
        assert "input_tokens" in usage, f"input_tokens missing in {pass_name} usage"
        assert "output_tokens" in usage, f"output_tokens missing in {pass_name} usage"
        assert "latency_ms" in usage, f"latency_ms missing in {pass_name} usage"
        assert "cost_usd" in usage, f"cost_usd missing in {pass_name} usage"
        assert usage.get("estimated") is True, (
            f"estimated flag should be True in {pass_name} usage (backend doesn't expose token counts)"
        )
        assert usage["input_tokens"] > 0, f"input_tokens should be > 0 for {pass_name}"
        assert usage["output_tokens"] > 0, f"output_tokens should be > 0 for {pass_name}"
        assert usage["cost_usd"] >= 0.0, f"cost_usd should be non-negative for {pass_name}"


# ---------------------------------------------------------------------------
# Test 5: extraction.json round-trips back to the expected pydantic shape
# ---------------------------------------------------------------------------


def test_recorder_captures_extraction_pydantic_dump(
    fake_pdf: Path,
    recorder: RunRecorder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """extraction.json for the conditions pass contains a 'conditions' key
    with the expected resource list.
    """
    pipeline = _make_pipeline()
    _stub_invoke_pass_0(pipeline, monkeypatch)
    _stub_specialist_passes_conditions_only(pipeline, monkeypatch)
    _stub_run_pass_conditions(pipeline, monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "_merge_to_bundle",
        lambda **kwargs: {"resourceType": "Bundle", "entry": []},
    )
    monkeypatch.setattr(pipeline, "_safe_extract_layout", lambda pdf_path: None)

    pipeline.extract(fake_pdf, recorder=recorder)

    extraction_path = recorder.root / "traces" / "conditions" / "extraction.json"
    assert extraction_path.exists(), "extraction.json missing for conditions pass"
    extraction = json.loads(extraction_path.read_text())
    assert "conditions" in extraction, (
        f"extraction.json for conditions pass should have 'conditions' key. "
        f"Got keys: {list(extraction.keys())}"
    )
    conditions = extraction["conditions"]
    assert isinstance(conditions, list) and len(conditions) == 1
    assert conditions[0]["display"] == "Hypertension"


# ---------------------------------------------------------------------------
# Test 6: recorder.finish() is called with the bundle after success
# ---------------------------------------------------------------------------


def test_recorder_finalizes_bundle_on_success(
    fake_pdf: Path,
    recorder: RunRecorder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """After extract() returns, bundle.json exists in the run dir with the
    same content as the return value from extract().
    """
    expected_bundle = {"resourceType": "Bundle", "entry": [{"resource": {"resourceType": "Patient"}}]}

    pipeline = _make_pipeline()
    _stub_invoke_pass_0(pipeline, monkeypatch)
    _stub_specialist_passes_conditions_only(pipeline, monkeypatch)
    _stub_run_pass_conditions(pipeline, monkeypatch)
    monkeypatch.setattr(
        pipeline,
        "_merge_to_bundle",
        lambda **kwargs: expected_bundle,
    )
    monkeypatch.setattr(pipeline, "_safe_extract_layout", lambda pdf_path: None)

    returned_bundle = pipeline.extract(fake_pdf, recorder=recorder)

    bundle_path = recorder.root / "bundle.json"
    assert bundle_path.exists(), "bundle.json should exist after extract() succeeds"
    on_disk = json.loads(bundle_path.read_text())
    assert on_disk == expected_bundle, "bundle.json should match the returned bundle"
    assert returned_bundle == expected_bundle


# ---------------------------------------------------------------------------
# Test 7: recorder records failure when a pass raises
# ---------------------------------------------------------------------------


def test_recorder_records_failure(
    fake_pdf: Path,
    recorder: RunRecorder,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When _invoke_pass_0 raises, recorder.finish() is called with
    status='failed' and the error message; the exception re-propagates.
    """
    pipeline = _make_pipeline()

    def _failing_invoke_pass_0(**kwargs: Any) -> DocumentContext:
        raise RuntimeError("LLM timeout after 60s")

    monkeypatch.setattr(pipeline, "_invoke_pass_0", _failing_invoke_pass_0)

    with pytest.raises(RuntimeError, match="LLM timeout after 60s"):
        pipeline.extract(fake_pdf, recorder=recorder)

    # Recorder should have called finish(status="failed")
    assert recorder.manifest.status == "failed", (
        f"Expected status='failed', got {recorder.manifest.status!r}"
    )
    assert "LLM timeout after 60s" in (recorder.manifest.error or ""), (
        f"Expected error message to contain the exception text, got: {recorder.manifest.error!r}"
    )

    # bundle.json should still exist (written by finish() with empty dict)
    bundle_path = recorder.root / "bundle.json"
    assert bundle_path.exists(), "bundle.json should be written by finish() even on failure"
    assert json.loads(bundle_path.read_text()) == {}


# ---------------------------------------------------------------------------
# Test 8: estimate_cost direct unit tests
# ---------------------------------------------------------------------------


def test_estimate_cost_known_models() -> None:
    """estimate_cost() returns correct values for known models and falls
    back to the conservative default for unknown models.
    """
    # claude-sonnet-4-6: $3/M input, $15/M output
    cost = estimate_cost(model="claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=1_000_000)
    assert abs(cost - 18.0) < 1e-6, f"Expected $18.0 for sonnet-4-6, got {cost}"

    # claude-opus-4-7: $15/M input, $75/M output
    cost = estimate_cost(model="claude-opus-4-7", input_tokens=1_000_000, output_tokens=1_000_000)
    assert abs(cost - 90.0) < 1e-6, f"Expected $90.0 for opus-4-7, got {cost}"

    # Unknown model → conservative default: $5/M input, $25/M output
    cost = estimate_cost(model="unknown-model-xyz", input_tokens=1_000_000, output_tokens=1_000_000)
    assert abs(cost - 30.0) < 1e-6, f"Expected $30.0 for unknown model, got {cost}"

    # None model → same conservative default
    cost = estimate_cost(model=None, input_tokens=1_000_000, output_tokens=1_000_000)
    assert abs(cost - 30.0) < 1e-6, f"Expected $30.0 for model=None, got {cost}"

    # Zero tokens → zero cost
    cost = estimate_cost(model="claude-sonnet-4-6", input_tokens=0, output_tokens=0)
    assert cost == 0.0, f"Expected $0.0 for zero tokens, got {cost}"

    # Backend-prefixed model ID should strip the prefix
    cost_prefixed = estimate_cost(
        model="anthropic/claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    cost_bare = estimate_cost(
        model="claude-sonnet-4-6",
        input_tokens=1_000_000,
        output_tokens=1_000_000,
    )
    assert abs(cost_prefixed - cost_bare) < 1e-9, (
        "Prefixed and bare model IDs should yield the same cost"
    )

    # gemma-4-31b-it: free tier — both rates are 0
    cost = estimate_cost(model="gemma-4-31b-it", input_tokens=1_000_000, output_tokens=1_000_000)
    assert cost == 0.0, f"Expected $0.0 for gemma free tier, got {cost}"
