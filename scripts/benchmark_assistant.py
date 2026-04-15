#!/usr/bin/env python3
"""
Assistant benchmarking harness.

Tests all three assistant modes (deterministic, context, anthropic) against
a fixed set of clinical questions across representative patients, measuring:
  - Latency (wall-clock ms)
  - Token usage (input/output)
  - Cost (estimated USD)
  - Response quality (answer length, citation count, confidence)
  - Follow-up relevance

Usage:
    # Run all modes (requires ANTHROPIC_API_KEY):
    python scripts/benchmark_assistant.py

    # Run only deterministic + context modes:
    python scripts/benchmark_assistant.py --modes deterministic context

    # Run with a specific patient:
    python scripts/benchmark_assistant.py --patient-id <id>

    # Output JSON for programmatic analysis:
    python scripts/benchmark_assistant.py --json
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path

# Ensure project root is importable
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

os.environ.setdefault("SOF_AUTO_MATERIALIZE", "false")


# ── Test cases ────────────────────────────────────────────────────────────────

# Representative patients across complexity tiers
TEST_PATIENTS = [
    {
        "id": "Shelly431_Corwin846_9da0dcfc-05e3-4e8e-95ff-b04b56f748be",
        "name": "Shelly431 Corwin846",
        "category": "high_surgical_risk",
        "tier": "highly_complex",
    },
    {
        "id": "Jose871_Williamson769_5919de03-6363-41a7-b251-f5be75149adc",
        "name": "Jose871 Williamson769",
        "category": "polypharmacy",
        "tier": "highly_complex",
    },
    {
        "id": "Wanita14_Ondricka197_1967373d-0925-4a5f-a0b7-4ac5932a8433",
        "name": "Wanita14 Ondricka197",
        "category": "potential_drug_interactions",
        "tier": "complex",
    },
    {
        "id": "Harrison106_Schuster709_775e3aae-d63d-43b7-bf3e-9d852fe61cb0",
        "name": "Harrison106 Schuster709",
        "category": "elderly_complex",
        "tier": "complex",
    },
]

TEST_QUESTIONS = [
    {
        "question": "Is this patient safe for surgery this week?",
        "intent": "preop_safety",
        "expects_citations": True,
    },
    {
        "question": "Any active blood thinner or interaction risk?",
        "intent": "anticoag",
        "expects_citations": True,
    },
    {
        "question": "Summarize the active problem list.",
        "intent": "general",
        "expects_citations": True,
    },
    {
        "question": "What medications could cause issues with anesthesia?",
        "intent": "anesthesia",
        "expects_citations": True,
    },
]


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class RunResult:
    mode: str
    patient_id: str
    patient_name: str
    patient_tier: str
    question: str
    intent: str

    # Timing
    latency_ms: float = 0.0

    # Response quality
    answer_length: int = 0
    answer_preview: str = ""
    confidence: str = ""
    engine: str = ""
    citation_count: int = 0
    follow_up_count: int = 0

    # Token usage (LLM modes only)
    input_tokens: int = 0
    output_tokens: int = 0
    cost_usd: float = 0.0

    # Error tracking
    error: str | None = None
    fell_back: bool = False


@dataclass
class BenchmarkReport:
    timestamp: str = ""
    total_runs: int = 0
    results: list[RunResult] = field(default_factory=list)
    summary: dict = field(default_factory=dict)


# ── Runner ────────────────────────────────────────────────────────────────────

def run_single(
    mode: str,
    patient: dict,
    question_spec: dict,
) -> RunResult:
    """Run a single assistant call and measure everything."""
    result = RunResult(
        mode=mode,
        patient_id=patient["id"],
        patient_name=patient["name"],
        patient_tier=patient["tier"],
        question=question_spec["question"],
        intent=question_spec["intent"],
    )

    # Override the mode for this call
    original_mode = os.environ.get("PROVIDER_ASSISTANT_MODE", "")
    os.environ["PROVIDER_ASSISTANT_MODE"] = mode

    try:
        from api.core.provider_assistant_service import answer_provider_question

        t0 = time.perf_counter()
        answer = answer_provider_question(
            patient_id=patient["id"],
            question=question_spec["question"],
            history=None,
            stance="opinionated",
        )
        t1 = time.perf_counter()

        result.latency_ms = round((t1 - t0) * 1000, 1)
        result.answer_length = len(answer.answer)
        result.answer_preview = answer.answer[:200]
        result.confidence = answer.confidence
        result.engine = answer.engine
        result.citation_count = len(answer.citations) if answer.citations else 0
        result.follow_up_count = len(answer.follow_ups) if answer.follow_ups else 0
        result.fell_back = "fallback" in (answer.engine or "")

        # Extract token/cost info from trace if available
        if hasattr(answer, "trace") and answer.trace:
            trace = answer.trace
            result.input_tokens = getattr(trace, "input_tokens", 0) or 0
            result.output_tokens = getattr(trace, "output_tokens", 0) or 0
            result.cost_usd = getattr(trace, "total_cost_usd", 0.0) or 0.0

    except Exception as exc:
        result.error = str(exc)
        result.latency_ms = round((time.perf_counter() - t0) * 1000, 1) if "t0" in dir() else 0
    finally:
        # Restore original mode
        if original_mode:
            os.environ["PROVIDER_ASSISTANT_MODE"] = original_mode
        else:
            os.environ.pop("PROVIDER_ASSISTANT_MODE", None)

    return result


def build_summary(results: list[RunResult]) -> dict:
    """Compute aggregate statistics by mode."""
    from collections import defaultdict

    by_mode: dict[str, list[RunResult]] = defaultdict(list)
    for r in results:
        by_mode[r.mode].append(r)

    summary = {}
    for mode, runs in by_mode.items():
        successful = [r for r in runs if r.error is None]
        failed = [r for r in runs if r.error is not None]
        fallbacks = [r for r in runs if r.fell_back]

        latencies = [r.latency_ms for r in successful]
        answer_lengths = [r.answer_length for r in successful]
        citations = [r.citation_count for r in successful]

        summary[mode] = {
            "total_runs": len(runs),
            "successful": len(successful),
            "failed": len(failed),
            "fallbacks": len(fallbacks),
            "latency_ms": {
                "min": round(min(latencies), 1) if latencies else 0,
                "max": round(max(latencies), 1) if latencies else 0,
                "avg": round(sum(latencies) / len(latencies), 1) if latencies else 0,
                "p50": round(sorted(latencies)[len(latencies) // 2], 1) if latencies else 0,
            },
            "answer_length": {
                "min": min(answer_lengths) if answer_lengths else 0,
                "max": max(answer_lengths) if answer_lengths else 0,
                "avg": round(sum(answer_lengths) / len(answer_lengths)) if answer_lengths else 0,
            },
            "citations": {
                "min": min(citations) if citations else 0,
                "max": max(citations) if citations else 0,
                "avg": round(sum(citations) / len(citations), 1) if citations else 0,
            },
            "total_input_tokens": sum(r.input_tokens for r in successful),
            "total_output_tokens": sum(r.output_tokens for r in successful),
            "total_cost_usd": round(sum(r.cost_usd for r in successful), 4),
            "confidence_distribution": {
                "high": sum(1 for r in successful if r.confidence == "high"),
                "medium": sum(1 for r in successful if r.confidence == "medium"),
                "low": sum(1 for r in successful if r.confidence == "low"),
            },
        }

    return summary


# ── CLI ───────────────────────────────────────────────────────────────────────

def print_table(results: list[RunResult], summary: dict) -> None:
    """Print a human-readable results table."""

    print("\n" + "=" * 90)
    print("  ASSISTANT BENCHMARK RESULTS")
    print("=" * 90)

    # Per-mode summary
    for mode, stats in summary.items():
        print(f"\n{'─' * 90}")
        print(f"  MODE: {mode.upper()}")
        print(f"{'─' * 90}")
        print(f"  Runs: {stats['successful']}/{stats['total_runs']} successful"
              f"  |  Fallbacks: {stats['fallbacks']}")
        print(f"  Latency:  avg={stats['latency_ms']['avg']}ms"
              f"  min={stats['latency_ms']['min']}ms"
              f"  max={stats['latency_ms']['max']}ms"
              f"  p50={stats['latency_ms']['p50']}ms")
        print(f"  Answers:  avg={stats['answer_length']['avg']} chars"
              f"  |  Citations: avg={stats['citations']['avg']}")
        print(f"  Tokens:   {stats['total_input_tokens']:,} in / {stats['total_output_tokens']:,} out"
              f"  |  Cost: ${stats['total_cost_usd']:.4f}")
        conf = stats["confidence_distribution"]
        print(f"  Confidence: {conf['high']} high / {conf['medium']} medium / {conf['low']} low")

    # Detailed results
    print(f"\n{'─' * 90}")
    print("  DETAILED RESULTS")
    print(f"{'─' * 90}")
    print(f"{'Mode':<15} {'Patient':<20} {'Question':<35} {'ms':>7} {'Len':>5} {'Cite':>4} {'Conf':>6} {'Err':>4}")
    print(f"{'─' * 15} {'─' * 20} {'─' * 35} {'─' * 7} {'─' * 5} {'─' * 4} {'─' * 6} {'─' * 4}")

    for r in results:
        q_short = r.question[:33] + ".." if len(r.question) > 35 else r.question
        p_short = r.patient_name[:18] + ".." if len(r.patient_name) > 20 else r.patient_name
        err = "ERR" if r.error else ("FB" if r.fell_back else "")
        print(f"{r.mode:<15} {p_short:<20} {q_short:<35} {r.latency_ms:>7.0f} {r.answer_length:>5} {r.citation_count:>4} {r.confidence:>6} {err:>4}")

    print(f"\n{'=' * 90}\n")


def main():
    parser = argparse.ArgumentParser(description="Benchmark the provider assistant")
    parser.add_argument(
        "--modes",
        nargs="+",
        default=["deterministic", "context", "anthropic"],
        help="Modes to test (default: all three)",
    )
    parser.add_argument(
        "--patient-id",
        help="Test a specific patient instead of the default set",
    )
    parser.add_argument(
        "--questions",
        nargs="+",
        help="Custom questions (overrides default test set)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of table",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Save results to file",
    )
    args = parser.parse_args()

    # Select patients
    if args.patient_id:
        patients = [{"id": args.patient_id, "name": "custom", "category": "custom", "tier": "unknown"}]
    else:
        patients = TEST_PATIENTS

    # Select questions
    if args.questions:
        questions = [{"question": q, "intent": "custom", "expects_citations": True} for q in args.questions]
    else:
        questions = TEST_QUESTIONS

    # Check API key for LLM modes
    llm_modes = {"context", "anthropic", "agent_sdk", "anthropic_agent"}
    needs_key = bool(set(args.modes) & llm_modes)
    if needs_key and not os.environ.get("ANTHROPIC_API_KEY"):
        print("WARNING: ANTHROPIC_API_KEY not set. LLM modes will fail/fallback.\n")

    total = len(args.modes) * len(patients) * len(questions)
    print(f"Running {total} benchmark calls ({len(args.modes)} modes x {len(patients)} patients x {len(questions)} questions)")
    print(f"Modes: {', '.join(args.modes)}")
    print()

    results: list[RunResult] = []
    done = 0

    for mode in args.modes:
        for patient in patients:
            for q in questions:
                done += 1
                label = f"[{done}/{total}] {mode} | {patient['name'][:20]} | {q['question'][:40]}"
                print(f"  {label}...", end=" ", flush=True)

                r = run_single(mode, patient, q)
                results.append(r)

                status = f"{r.latency_ms:.0f}ms"
                if r.error:
                    status = f"ERROR: {r.error[:50]}"
                elif r.fell_back:
                    status = f"{r.latency_ms:.0f}ms (fallback)"
                print(status)

    # Build summary
    report = BenchmarkReport(
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%S"),
        total_runs=len(results),
        results=results,
        summary=build_summary(results),
    )

    if args.json:
        output = json.dumps(asdict(report), indent=2)
        if args.output:
            Path(args.output).write_text(output)
            print(f"\nResults saved to {args.output}")
        else:
            print(output)
    else:
        print_table(results, report.summary)
        if args.output:
            Path(args.output).write_text(json.dumps(asdict(report), indent=2))
            print(f"JSON results saved to {args.output}")


if __name__ == "__main__":
    main()
