"""Token-cost estimation per model.

Anthropic and Google AI Studio publish per-token rates. This module
captures known rates as a lookup table; unknown models get a
conservative default. Used by LAB-T02 to populate usage.cost_usd in
RunRecorder traces.
"""

from __future__ import annotations


# Per-million-token rates in USD. Updated 2026-05-07.
# (input_per_mtok, output_per_mtok)
_COST_TABLE: dict[str, tuple[float, float]] = {
    # Anthropic Claude family
    "claude-opus-4-7": (15.0, 75.0),
    "claude-sonnet-4-6": (3.0, 15.0),
    "claude-haiku-4-5": (0.80, 4.0),
    # Google AI Studio
    "gemma-4-31b-it": (0.0, 0.0),  # free tier; placeholder
    "gemini-2.5-pro": (1.25, 5.0),
    "gemini-2.5-flash": (0.075, 0.30),
}

# Conservative default if model isn't in the table.
_DEFAULT_RATES = (5.0, 25.0)  # treat unknown as Sonnet-ish


def estimate_cost(
    *,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
) -> float:
    """Return estimated USD cost for a single model call.

    Args:
        model: model identifier (e.g. "claude-sonnet-4-6"). None → default.
        input_tokens: input/prompt tokens consumed.
        output_tokens: output/completion tokens generated.

    Returns:
        Estimated cost in USD. Conservative default for unknown models.
    """
    if not model:
        in_rate, out_rate = _DEFAULT_RATES
    else:
        # Strip "<backend>/" prefix if present (the pipeline uses
        # "anthropic/claude-sonnet-4-6" style identifiers).
        key = model.split("/")[-1] if "/" in model else model
        in_rate, out_rate = _COST_TABLE.get(key, _DEFAULT_RATES)
    return (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate
