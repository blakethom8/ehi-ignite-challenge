"""Tests for MultiPassFHIRGoldPipeline (GOLD-T01).

Covers:
1. test_gold_pipeline_registered          — "multipass-fhir-gold" in list_pipelines()
2. test_gold_pipeline_metadata_distinct   — name, architecture, backends, cost
3. test_gold_pipeline_inherits_specialist_passes — _specialist_passes returns full _PASSES set
4. test_gold_pipeline_uses_opus_for_every_pass   — every pass resolves to claude-opus-4-7
5. test_gold_pipeline_enables_thinking_for_every_pass — every pass has thinking_budget_tokens > 0
6. test_anthropic_backend_thinking_param_optional — thinking kwarg present/absent based on flag
7. test_anthropic_backend_skips_thinking_blocks_in_response — thinking block skipped, text block kept
8. test_estimate_cost_opus_known_model    — Opus rate ($15/1M in, $75/1M out) applied correctly
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock, patch


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _new_gold() -> "MultiPassFHIRGoldPipeline":
    """Instantiate without calling __init__ (avoids cache/backend setup)."""
    from lib.extract.pipelines.multipass_fhir import MultiPassFHIRGoldPipeline

    return MultiPassFHIRGoldPipeline.__new__(MultiPassFHIRGoldPipeline)


def _new_gold_init() -> "MultiPassFHIRGoldPipeline":
    """Instantiate via normal __init__ to verify override plumbing."""
    from lib.extract.pipelines.multipass_fhir import MultiPassFHIRGoldPipeline

    return MultiPassFHIRGoldPipeline()


# ---------------------------------------------------------------------------
# Test 1 — registration
# ---------------------------------------------------------------------------


def test_gold_pipeline_registered() -> None:
    """multipass-fhir-gold must appear in the global pipeline registry."""
    from lib.extract.pipelines import list_pipelines

    # Import the pipeline module to trigger registration
    import lib.extract.pipelines.multipass_fhir  # noqa: F401

    names = [p.name for p in list_pipelines()]
    assert "multipass-fhir-gold" in names, (
        f"multipass-fhir-gold not found in registry. Known: {names}"
    )


# ---------------------------------------------------------------------------
# Test 2 — metadata distinctness
# ---------------------------------------------------------------------------


def test_gold_pipeline_metadata_distinct() -> None:
    """Gold pipeline metadata must have correct name, architecture, backends, cost."""
    from lib.extract.pipelines.multipass_fhir import MultiPassFHIRGoldPipeline

    meta = MultiPassFHIRGoldPipeline.metadata
    assert meta.name == "multipass-fhir-gold"
    assert meta.architecture == "gold-standard"
    assert meta.primary_backends == ["anthropic"]
    assert meta.estimated_cost_per_pdf_usd is not None
    assert meta.estimated_cost_per_pdf_usd >= 1.0, (
        f"Expected cost >= $1 for gold pipeline, got {meta.estimated_cost_per_pdf_usd}"
    )


# ---------------------------------------------------------------------------
# Test 3 — specialist passes inherit full _PASSES set
# ---------------------------------------------------------------------------


def test_gold_pipeline_inherits_specialist_passes() -> None:
    """_specialist_passes on the gold pipeline returns the same set of
    pass names as _PASSES (gold doesn't skip any pass).

    The pipeline's _doc_map is None (no scout), so _specialist_passes()
    falls through to the base MultiPassFHIRPipeline._specialist_passes(),
    which returns _PASSES unchanged.
    """
    from lib.extract.pipelines.multipass_fhir import (
        _PASSES,
        DocumentContext,
        MultiPassFHIRGoldPipeline,
    )

    pipeline = _new_gold()
    # _specialist_passes on the base pipeline returns _PASSES regardless of
    # doc_context, so we can pass any DocumentContext here.
    ctx = DocumentContext(document_type="other")
    result = pipeline._specialist_passes(ctx)

    expected_names = {p.name for p in _PASSES}
    actual_names = {p.name for p in result}
    assert actual_names == expected_names, (
        f"Expected passes: {expected_names}, got: {actual_names}"
    )


# ---------------------------------------------------------------------------
# Test 4 — every pass resolves to Opus 4.7
# ---------------------------------------------------------------------------


def test_gold_pipeline_uses_opus_for_every_pass() -> None:
    """After __init__, every entry in _pass_overrides (and the pipeline-level
    default model) points to claude-opus-4-7."""
    from lib.extract.pipelines.multipass_fhir import _PASSES, MultiPassFHIRGoldPipeline

    pipeline = _new_gold_init()

    # Pipeline-level default model
    assert pipeline._model == "claude-opus-4-7", (
        f"Expected pipeline._model='claude-opus-4-7', got {pipeline._model!r}"
    )

    # Every specialist pass must have an override pointing to Opus
    for p in _PASSES:
        override = pipeline._pass_overrides.get(p.name)
        assert override is not None, (
            f"Pass {p.name!r} has no override in _pass_overrides"
        )
        assert override.get("model") == "claude-opus-4-7", (
            f"Pass {p.name!r} override model is {override.get('model')!r}, "
            f"expected 'claude-opus-4-7'"
        )


# ---------------------------------------------------------------------------
# Test 5 — every pass enables thinking
# ---------------------------------------------------------------------------


def test_gold_pipeline_enables_thinking_for_every_pass() -> None:
    """After __init__, every entry in _pass_overrides has a positive
    thinking_budget_tokens value."""
    from lib.extract.pipelines.multipass_fhir import _PASSES, MultiPassFHIRGoldPipeline

    pipeline = _new_gold_init()

    for p in _PASSES:
        override = pipeline._pass_overrides.get(p.name)
        assert override is not None, (
            f"Pass {p.name!r} has no override"
        )
        tbt = override.get("thinking_budget_tokens")
        assert tbt is not None, (
            f"Pass {p.name!r} override missing thinking_budget_tokens"
        )
        assert isinstance(tbt, int) and tbt > 0, (
            f"Pass {p.name!r} thinking_budget_tokens must be a positive int, got {tbt!r}"
        )


# ---------------------------------------------------------------------------
# Test 6 — AnthropicBackend thinking param optional
# ---------------------------------------------------------------------------


def test_anthropic_backend_thinking_param_optional() -> None:
    """AnthropicBackend(thinking_budget_tokens=None) does NOT pass 'thinking'
    to messages.create; AnthropicBackend(thinking_budget_tokens=16000) does."""
    from lib.extract.pdf import AnthropicBackend

    # --- Case A: None (default) — no thinking kwarg ---
    mock_client_a = MagicMock()
    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.input = {"conditions": []}
    mock_client_a.messages.create.return_value = MagicMock(
        content=[tool_use_block],
        stop_reason="tool_use",
    )

    backend_no_thinking = AnthropicBackend(
        model="claude-opus-4-7",
        client=mock_client_a,
        thinking_budget_tokens=None,
    )
    backend_no_thinking.extract(
        pdf_bytes=b"fake",
        system_prompt="sys",
        schema_json={"type": "object", "properties": {}},
    )

    call_kwargs_a = mock_client_a.messages.create.call_args.kwargs
    assert "thinking" not in call_kwargs_a, (
        f"Expected no 'thinking' kwarg when thinking_budget_tokens=None, "
        f"got call kwargs: {call_kwargs_a}"
    )

    # --- Case B: 16000 — thinking kwarg must be present ---
    mock_client_b = MagicMock()
    mock_client_b.messages.create.return_value = MagicMock(
        content=[tool_use_block],
        stop_reason="tool_use",
    )

    backend_with_thinking = AnthropicBackend(
        model="claude-opus-4-7",
        client=mock_client_b,
        thinking_budget_tokens=16000,
    )
    backend_with_thinking.extract(
        pdf_bytes=b"fake",
        system_prompt="sys",
        schema_json={"type": "object", "properties": {}},
    )

    call_kwargs_b = mock_client_b.messages.create.call_args.kwargs
    assert "thinking" in call_kwargs_b, (
        f"Expected 'thinking' kwarg when thinking_budget_tokens=16000, "
        f"got call kwargs: {call_kwargs_b}"
    )
    assert call_kwargs_b["thinking"] == {
        "type": "enabled",
        "budget_tokens": 16000,
    }, f"Unexpected thinking value: {call_kwargs_b['thinking']!r}"


# ---------------------------------------------------------------------------
# Test 7 — AnthropicBackend skips thinking blocks in response
# ---------------------------------------------------------------------------


def test_anthropic_backend_skips_thinking_blocks_in_response() -> None:
    """When the response content includes a thinking block before the tool_use
    block, the thinking block is silently skipped and the tool_use block is
    returned as the result."""
    from lib.extract.pdf import AnthropicBackend

    # Build mock blocks
    thinking_block = MagicMock()
    thinking_block.type = "thinking"
    thinking_block.thinking = "Let me think step by step..."

    tool_use_block = MagicMock()
    tool_use_block.type = "tool_use"
    tool_use_block.input = {"conditions": [{"display": "Hypertension"}]}

    mock_client = MagicMock()
    mock_client.messages.create.return_value = MagicMock(
        content=[thinking_block, tool_use_block],
        stop_reason="tool_use",
    )

    backend = AnthropicBackend(
        model="claude-opus-4-7",
        client=mock_client,
        thinking_budget_tokens=16000,
    )

    result = backend.extract(
        pdf_bytes=b"fake",
        system_prompt="sys",
        schema_json={"type": "object", "properties": {}},
    )

    # Must have returned the tool_use block's input, not the thinking content
    assert result == {"conditions": [{"display": "Hypertension"}]}, (
        f"Expected tool_use input, got: {result!r}"
    )


# ---------------------------------------------------------------------------
# Test 8 — estimate_cost Opus known model
# ---------------------------------------------------------------------------


def test_estimate_cost_opus_known_model() -> None:
    """estimate_cost for claude-opus-4-7 uses $15/1M input + $75/1M output."""
    from lib.extract.lab.cost import estimate_cost

    cost = estimate_cost(
        model="claude-opus-4-7",
        input_tokens=1000,
        output_tokens=500,
    )
    # 15/1_000_000 * 1000 + 75/1_000_000 * 500 = 0.015 + 0.0375 = 0.0525
    expected = 0.0525
    assert abs(cost - expected) < 1e-6, (
        f"Expected cost {expected}, got {cost}"
    )
