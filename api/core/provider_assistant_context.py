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
    _collect_citations,
    _rank_relevant_facts,
)
from api.core.tracing import SpanKind, start_span
from api.core import caspian_tools, caspian_workspace
from api.core.auth import SessionPrincipal
from api.settings import get_settings

LOGGER = logging.getLogger(__name__)

_REPO_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


def _resolve_api_key() -> str:
    """Resolve Anthropic API key from env or .env file."""
    env_key = (get_settings().anthropic_api_key or "").strip()
    if env_key and "YOUR_KEY_HERE" not in env_key:
        return env_key
    if _REPO_ENV_PATH.exists():
        file_key = (dotenv_values(_REPO_ENV_PATH).get("ANTHROPIC_API_KEY") or "").strip()
        if file_key and "YOUR_KEY_HERE" not in file_key:
            return file_key
    return env_key


_SYSTEM_TEMPLATE = """You are a clinical chart assistant helping a clinician review a patient's published chart.

CHART SCOPE:
- The selected patient workspace is already loaded in PATIENT CHART CONTEXT below.
- Do not say no chart is loaded unless PATIENT CHART CONTEXT has no patient summary and no clinical facts.
- Attached context packages are additive review instructions. They do not replace the selected patient's chart.
- Answer chart-data questions from patient facts first, then mention gaps or missing data if relevant.

INSTRUCTIONS:
- Answer the question directly and concisely based ONLY on the patient data below.
- Lead with the most safety-critical information.
- If the data supports a clear clinical recommendation, state it.
- If the evidence is weak or conflicting, explicitly say so. Push back on unsafe assumptions.
- Cite specific data points (medication names, lab values, dates) in your answer.
- Do not assume the workflow is surgical or pre-operative unless the user asks or an attached context package narrows the task.
- Use the stance: {stance}. If "opinionated", give a direct recommendation. If "balanced", present both sides.
- Format your response as plain text, not JSON. Use bullet points for lists.
- At the end, suggest 2-3 follow-up questions the clinician or patient should consider.

FILE TOOLS:
- You have access to `write_file`, `read_file`, and `list_files` for this patient's working directory.
- Use `write_file` ONLY when the clinician explicitly asks you to save, create, draft, or add a file. Don't volunteer writes.
- Default the path to `notes/<descriptive-kebab-name>.md` unless the clinician specifies otherwise. The `system-context/` folder is read-only — writes there will fail.
- After writing, briefly tell the clinician the filename so they can open it from the Files pane.

PATIENT CHART CONTEXT:
{context}

{context_packages}

{user_overrides}
"""

_USER_OVERRIDES_HEADER = """USER OVERRIDES (from this workspace's user-instructions.md):
The clinician has set the following standing instructions for this patient's
chats. Honor them unless they conflict with safety guidance above.

"""


def _format_context_packages(context_packages: list[dict[str, str]] | None) -> str:
    if not context_packages:
        return ""

    sections = [
        "ATTACHED CONTEXT PACKAGES:",
        "The clinician attached the following reusable context packages for this chat session. Use them as review instructions and workflow guidance, but do not treat them as patient-specific chart facts.",
    ]
    for package in context_packages[:8]:
        title = str(package.get("title") or "Untitled package").strip()
        package_type = str(package.get("type") or "Context").strip()
        summary = str(package.get("summary") or "").strip()
        instructions = str(package.get("instructions") or "").strip()
        sections.append(
            f"\n## {title}\n"
            f"Type: {package_type}\n"
            f"Summary: {summary}\n"
            f"Instructions:\n{instructions}"
        )
    return "\n".join(sections).strip()


def _load_user_overrides(
    session: SessionPrincipal | None,
    resolved_patient_id: str | None,
) -> str:
    """Read user-instructions.md from the patient's workspace, if any."""
    if session is None or not resolved_patient_id:
        return ""
    try:
        result = caspian_workspace.read_workspace_file(
            session, resolved_patient_id, caspian_workspace.USER_INSTRUCTIONS_PATH
        )
    except Exception:  # pragma: no cover - defensive
        return ""
    body = (result.content or "").strip()
    if not body:
        return ""
    return _USER_OVERRIDES_HEADER + body


def answer_with_context(
    *,
    patient_id: str,
    question: str,
    history: list[dict[str, str]] | None = None,
    context_packages: list[dict[str, str]] | None = None,
    stance: str = "opinionated",
    model_override: str | None = None,
    max_tokens_override: int | None = None,
    session: SessionPrincipal | None = None,
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
    user_overrides = _load_user_overrides(session, patient_id)
    system_prompt = _SYSTEM_TEMPLATE.format(
        stance=stance,
        context=context_prompt,
        context_packages=_format_context_packages(context_packages),
        user_overrides=user_overrides,
    )

    messages: list[dict] = []

    # Include conversation history
    if history:
        for turn in history[-6:]:
            role = turn.get("role", "user")
            content = turn.get("content", "").strip()
            if content:
                messages.append({"role": role, "content": content})

    messages.append({"role": "user", "content": question})

    # Step 3: bounded tool loop
    model = model_override or get_settings().provider_assistant_model
    max_tokens = max_tokens_override or 1500
    tools_enabled = session is not None  # tools require a workspace key

    import anthropic

    client = anthropic.Anthropic(api_key=api_key)
    answer_text = ""
    files_created: list[str] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0

    # Per-session tool surface: authenticated gets list/read/write, demo gets
    # list/read only, guest/anonymous gets nothing. ``offer_tools`` only flips
    # whether we attach the (possibly empty) list to the request.
    session_tools = caspian_tools.caspian_chat_tools_for(session)
    tools_enabled = tools_enabled and bool(session_tools)

    MAX_TOOL_ITERATIONS = 4
    for iteration in range(MAX_TOOL_ITERATIONS + 1):
        # On the final iteration, drop tools so Claude must finalize the answer.
        offer_tools = tools_enabled and iteration < MAX_TOOL_ITERATIONS

        with start_span(
            SpanKind.LLM,
            "claude_chat_turn" if iteration > 0 else "claude_single_turn",
            input_data={
                "model": model,
                "stance": stance,
                "system_prompt": system_prompt if iteration == 0 else None,
                "question": question if iteration == 0 else None,
                "iteration": iteration,
            },
        ) as llm_span:
            start_time = time.time()
            request_kwargs: dict = {
                "model": model,
                "max_tokens": max_tokens,
                "system": system_prompt,
                "messages": messages,
            }
            if offer_tools:
                request_kwargs["tools"] = session_tools
            response = client.messages.create(**request_kwargs)
            duration_ms = (time.time() - start_time) * 1000

            input_tokens = getattr(response.usage, "input_tokens", 0) or 0
            output_tokens = getattr(response.usage, "output_tokens", 0) or 0
            total_input_tokens += input_tokens
            total_output_tokens += output_tokens
            input_cost = input_tokens * 3.0 / 1_000_000
            output_cost = output_tokens * 15.0 / 1_000_000
            total_cost += input_cost + output_cost

            if llm_span:
                llm_span.input_tokens = input_tokens
                llm_span.output_tokens = output_tokens
                llm_span.duration_ms = duration_ms
                llm_span.total_cost_usd = input_cost + output_cost
                llm_span.output_data = json.dumps({
                    "stop_reason": response.stop_reason,
                    "model": response.model,
                    "iteration": iteration,
                })

        # Collect text + tool_use blocks from the assistant message.
        assistant_content_blocks: list[dict | object] = []
        tool_uses: list[object] = []
        text_chunks: list[str] = []
        for block in response.content or []:
            assistant_content_blocks.append(block)
            btype = getattr(block, "type", None)
            if btype == "text":
                text_chunks.append(getattr(block, "text", ""))
            elif btype == "tool_use":
                tool_uses.append(block)

        if text_chunks:
            answer_text = "\n".join(c for c in text_chunks if c).strip()

        if not tool_uses or not offer_tools:
            # No tool calls (or tools disabled on final pass) — we're done.
            break

        # Append the assistant's tool_use to the message history, then execute
        # each tool and append a tool_result block.
        messages.append({"role": "assistant", "content": assistant_content_blocks})
        tool_result_blocks: list[dict] = []
        for tool_use in tool_uses:
            name = getattr(tool_use, "name", "") or ""
            args = getattr(tool_use, "input", None) or {}
            tool_use_id = getattr(tool_use, "id", "")
            with start_span(
                SpanKind.TOOL,
                name or "tool_use",
                input_data=args if isinstance(args, dict) else {"raw": str(args)},
            ) as tool_span:
                payload, is_error = caspian_tools.execute_tool(
                    name,
                    args if isinstance(args, dict) else {},
                    session,  # type: ignore[arg-type] — guarded by tools_enabled
                    patient_id,
                )
                if tool_span:
                    tool_span.output_data = json.dumps(payload, default=str)[:2000]
                    if is_error:
                        tool_span.error = str(payload.get("error", ""))[:500]
            if name == "write_file" and not is_error and payload.get("path"):
                files_created.append(payload["path"])
            result_block = caspian_tools.tool_result_payload(payload, is_error)
            result_block["tool_use_id"] = tool_use_id
            tool_result_blocks.append(result_block)
        messages.append({"role": "user", "content": tool_result_blocks})

    # Step 4: Extract follow-ups from the answer
    follow_ups = _extract_follow_ups(answer_text)

    # Step 5: Build citations from the context (deterministic)
    _intent, relevant_facts, _summary = _rank_relevant_facts(
        patient_id=patient_id,
        question=question,
        history=history,
        max_items=8,
    )
    citations = _collect_citations(relevant_facts, max_items=6)

    history_count = len([t for t in (history or []) if t.get("content", "").strip()])

    return AssistantResult(
        answer=answer_text,
        confidence="high",  # Single-turn with full context is inherently high confidence
        citations=citations,
        follow_ups=follow_ups,
        engine="context-single-turn",
        retrieved_facts=[
            *[f"[Evidence] {fact.text}" for fact in relevant_facts[:6]],
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
        files_created=files_created or None,
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
