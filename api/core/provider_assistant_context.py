"""
Single-turn context-driven provider assistant.

Uses the context_builder to assemble a clean clinical context, then makes
ONE Claude API call with that context as the system prompt. No multi-turn
agent loop, no tool calls — just pre-built context → single LLM call → answer.

This is the recommended mode for the EHI Ignite pitch:
- ~3-5s latency (vs 15-30s for the agent SDK multi-turn loop)
- Deterministic context (same data every time, auditable)
- Full transparency (the exact context is visible to the user)
- No hallucinated SQL queries or tool call errors

Set PROVIDER_ASSISTANT_MODE=context to enable.
"""

from __future__ import annotations

import json
import logging
import os
import time
from pathlib import Path

try:
    from dotenv import dotenv_values
except ImportError:
    def dotenv_values(path: str | Path) -> dict:  # type: ignore[misc]
        return {}

from api.core.context_builder import build_clinical_context
from api.core.provider_assistant import (
    AssistantCitationPayload,
    AssistantResult,
    _build_facts,
    _collect_citations,
)
from api.core.tracing import SpanKind, start_span

LOGGER = logging.getLogger(__name__)

_REPO_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def _resolve_api_key() -> str:
    """Resolve Anthropic API key from env or .env file."""
    env_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if env_key and "YOUR_KEY_HERE" not in env_key:
        return env_key
    if _REPO_ENV_PATH.exists():
        file_key = (dotenv_values(_REPO_ENV_PATH).get("ANTHROPIC_API_KEY") or "").strip()
        if file_key and "YOUR_KEY_HERE" not in file_key:
            return file_key
    return env_key


_SYSTEM_TEMPLATE = """You are a clinical chart assistant helping a surgeon review a patient before a procedure.

INSTRUCTIONS:
- Answer the question directly and concisely based ONLY on the patient data below.
- Lead with the most safety-critical information.
- If the data supports a clear clinical recommendation, state it.
- If the evidence is weak or conflicting, explicitly say so. Push back on unsafe assumptions.
- Cite specific data points (medication names, lab values, dates) in your answer.
- Use the stance: {stance}. If "opinionated", give a direct recommendation. If "balanced", present both sides.
- Format your response as plain text, not JSON. Use bullet points for lists.
- At the end, suggest 2-3 follow-up questions the surgeon should consider.

{context}
"""


def answer_with_context(
    *,
    patient_id: str,
    question: str,
    history: list[dict[str, str]] | None = None,
    stance: str = "opinionated",
    model_override: str | None = None,
    max_tokens_override: int | None = None,
) -> AssistantResult:
    """
    Single-turn context-driven answer.

    1. Build clean clinical context (deterministic, fast)
    2. Send context + question to Claude in ONE API call
    3. Return structured answer with citations
    """
    api_key = _resolve_api_key()
    if not api_key:
        raise RuntimeError(
            "ANTHROPIC_API_KEY not set. Set it in .env or environment to use context mode."
        )

    # Step 1: Build context (deterministic, ~150ms)
    with start_span(SpanKind.RETRIEVAL, "build_clinical_context", input_data={"patient_id": patient_id}) as ctx_span:
        clinical_ctx = build_clinical_context(patient_id)
        context_prompt = clinical_ctx.to_prompt()
        if ctx_span:
            ctx_span.output_data = json.dumps({
                "fact_count": clinical_ctx.fact_count,
                "token_estimate": clinical_ctx.total_tokens_estimate,
                "sections": {
                    "safety_flags": len(clinical_ctx.safety_flags),
                    "active_medications": len(clinical_ctx.active_medications),
                    "active_conditions": len(clinical_ctx.active_conditions),
                    "key_labs": len(clinical_ctx.key_labs),
                    "recent_encounters": len(clinical_ctx.recent_encounters),
                },
            })

    # Step 2: Build messages
    system_prompt = _SYSTEM_TEMPLATE.format(
        stance=stance,
        context=context_prompt,
    )

    messages = []

    # Include conversation history
    if history:
        for turn in history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "").strip()
            if content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})

    # Step 3: Single Claude API call
    model = model_override or os.getenv("PROVIDER_ASSISTANT_MODEL", "claude-sonnet-4-5")
    max_tokens = max_tokens_override or 1500

    with start_span(SpanKind.LLM, "claude_single_turn", input_data={
        "model": model,
        "stance": stance,
        "system_prompt": system_prompt,
        "question": question,
    }) as llm_span:
        import anthropic

        client = anthropic.Anthropic(api_key=api_key)
        start_time = time.time()

        response = client.messages.create(
            model=model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=messages,
        )

        duration_ms = (time.time() - start_time) * 1000
        answer_text = response.content[0].text if response.content else ""

        if llm_span:
            llm_span.input_tokens = response.usage.input_tokens
            llm_span.output_tokens = response.usage.output_tokens
            llm_span.duration_ms = duration_ms
            llm_span.output_data = json.dumps({
                "result_length": len(answer_text),
                "stop_reason": response.stop_reason,
                "model": response.model,
                "duration_api_ms": round(duration_ms),
            })
            # Estimate cost (Sonnet pricing)
            input_cost = response.usage.input_tokens * 3.0 / 1_000_000
            output_cost = response.usage.output_tokens * 15.0 / 1_000_000
            llm_span.total_cost_usd = input_cost + output_cost

    # Step 4: Extract follow-ups from the answer
    follow_ups = _extract_follow_ups(answer_text)

    # Step 5: Build citations from the context (deterministic)
    facts_list, _ = _build_facts(patient_id)
    citations = _collect_citations(facts_list[:8], max_items=6)

    history_count = len([t for t in (history or []) if t.get("content", "").strip()])

    return AssistantResult(
        answer=answer_text,
        confidence="high",  # Single-turn with full context is inherently high confidence
        citations=citations,
        follow_ups=follow_ups,
        engine="context-single-turn",
        retrieved_facts=[
            *[f"[Safety] {s}" for s in clinical_ctx.safety_flags[:4]],
            *[f"[Med] {m}" for m in clinical_ctx.active_medications[:5]],
            *[f"[Lab] {l}" for l in clinical_ctx.key_labs[:5]],
            *[f"[Condition] {c}" for c in clinical_ctx.active_conditions[:5]],
        ],
        # Full transparency
        system_prompt=system_prompt,
        model_used=model,
        mode_used="context-single-turn",
        max_tokens_used=max_tokens,
        context_token_estimate=clinical_ctx.total_tokens_estimate,
        history_turns_sent=history_count,
    )


def _extract_follow_ups(answer: str) -> list[str]:
    """Extract suggested follow-up questions from the answer text."""
    follow_ups: list[str] = []
    lines = answer.split("\n")
    in_follow_up = False

    for line in lines:
        stripped = line.strip()
        if any(phrase in stripped.lower() for phrase in ["follow-up", "follow up", "consider asking", "next question", "you should also"]):
            in_follow_up = True
            continue
        if in_follow_up and stripped.startswith(("-", "•", "*", "1", "2", "3")):
            # Clean the bullet
            clean = stripped.lstrip("-•*0123456789. ").strip()
            if clean and len(clean) > 10:
                follow_ups.append(clean)

    return follow_ups[:3]
