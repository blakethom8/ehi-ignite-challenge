"""
Anthropic Claude Agent SDK-backed provider assistant runtime.

This module keeps the existing API contract intact while enabling an agentic
execution path backed by Claude Agent SDK + scoped MCP tools.
"""

from __future__ import annotations

import asyncio
import json
import os
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from claude_agent_sdk import (
    AssistantMessage,
    CLINotFoundError,
    ClaudeAgentOptions,
    ClaudeSDKError,
    ResultMessage,
    TextBlock,
    create_sdk_mcp_server,
    query,
    tool,
)
from dotenv import dotenv_values

from api.core.provider_assistant import (
    AssistantCitationPayload,
    AssistantResult,
    get_relevant_provider_evidence,
)
from api.core.tracing import SpanKind, start_span


_AGENT_PROFILE_DIR = Path(__file__).parent.parent / "agents" / "provider-assistant"
_REPO_ENV_PATH = Path(__file__).resolve().parent.parent.parent / ".env"


class AgentConfigurationError(RuntimeError):
    """Raised when Anthropic agent mode is misconfigured."""


class AgentExecutionError(RuntimeError):
    """Raised when Anthropic agent execution fails."""


@dataclass
class AgentSDKConfig:
    model: str
    max_turns: int
    max_budget_usd: float | None
    enable_web_search: bool
    enable_web_fetch: bool


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _resolve_anthropic_api_key() -> str:
    """
    Resolve Anthropic key with safe fallback to repo .env.

    This prevents stale shell placeholders (e.g. sk-ant-YOUR_KEY_HERE) from
    masking a valid key in .env when dotenv loading uses override=False.
    """
    env_key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
    if env_key and "YOUR_KEY_HERE" not in env_key:
        return env_key

    if _REPO_ENV_PATH.exists():
        file_key = (dotenv_values(_REPO_ENV_PATH).get("ANTHROPIC_API_KEY") or "").strip()
        if file_key and "YOUR_KEY_HERE" not in file_key:
            return file_key

    return env_key


def _load_config() -> AgentSDKConfig:
    max_budget_raw = os.getenv("PROVIDER_ASSISTANT_MAX_BUDGET_USD")
    max_budget = None
    if max_budget_raw:
        try:
            max_budget = float(max_budget_raw)
        except ValueError:
            max_budget = None

    return AgentSDKConfig(
        model=os.getenv("PROVIDER_ASSISTANT_MODEL", "claude-sonnet-4-5"),
        max_turns=max(2, int(os.getenv("PROVIDER_ASSISTANT_MAX_TURNS", "6"))),
        max_budget_usd=max_budget,
        enable_web_search=_env_bool("PROVIDER_ASSISTANT_ENABLE_WEB_SEARCH", False),
        enable_web_fetch=_env_bool("PROVIDER_ASSISTANT_ENABLE_WEB_FETCH", False),
    )


def _conversation_excerpt(history: list[dict[str, str]] | None) -> str:
    if not history:
        return "(no prior turns)"
    lines: list[str] = []
    for turn in history[-6:]:
        role = turn.get("role", "user").strip().lower()
        content = turn.get("content", "").strip()
        if not content:
            continue
        speaker = "Provider" if role == "user" else "Assistant"
        lines.append(f"{speaker}: {content}")
    return "\n".join(lines) if lines else "(no prior turns)"


def _parse_result_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip()

    fenced = re.search(r"```(?:json)?\s*(\{.*\})\s*```", cleaned, flags=re.DOTALL)
    if fenced:
        cleaned = fenced.group(1).strip()

    try:
        parsed = json.loads(cleaned)
        if isinstance(parsed, dict):
            return parsed
    except json.JSONDecodeError:
        pass

    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start >= 0 and end > start:
        try:
            parsed = json.loads(cleaned[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError as exc:
            raise AgentExecutionError("Agent returned invalid JSON") from exc

    raise AgentExecutionError("Agent did not return a JSON object")


def _citation_from_dict(raw: dict[str, Any]) -> AssistantCitationPayload | None:
    source_type = str(raw.get("source_type", "")).strip()
    resource_id = str(raw.get("resource_id", "")).strip()
    if not source_type or not resource_id:
        return None

    event_date_raw = raw.get("event_date")
    event_date: datetime | None = None
    if isinstance(event_date_raw, str) and event_date_raw.strip():
        try:
            event_date = datetime.fromisoformat(event_date_raw)
        except ValueError:
            event_date = None

    return AssistantCitationPayload(
        source_type=source_type,
        resource_id=resource_id,
        label=str(raw.get("label", "")).strip() or resource_id,
        detail=str(raw.get("detail", "")).strip() or "No detail provided.",
        event_date=event_date,
    )


def _extract_assistant_text(message: AssistantMessage) -> str:
    chunks: list[str] = []
    for block in message.content:
        if isinstance(block, TextBlock):
            chunks.append(block.text)
        elif hasattr(block, "text") and isinstance(block.text, str):
            chunks.append(block.text)
    return "\n".join(chunk for chunk in chunks if chunk.strip())


async def _run_agent(
    *,
    patient_id: str,
    question: str,
    history: list[dict[str, str]] | None,
    stance: str,
    config: AgentSDKConfig,
) -> AssistantResult:
    with start_span(SpanKind.RETRIEVAL, "baseline_evidence", input_data={"patient_id": patient_id, "question": question}) as _baseline_span:
        baseline = get_relevant_provider_evidence(
            patient_id=patient_id,
            query=question,
            history=history,
            max_facts=8,
            max_citations=6,
        )
        if _baseline_span:
            _baseline_span.output_data = json.dumps({"intent": baseline.get("intent"), "fact_count": len(baseline.get("evidence_lines", []))}, default=str)

    retrieved_citations: dict[tuple[str, str], AssistantCitationPayload] = {}

    def remember_citations(items: list[dict[str, Any]]) -> None:
        for item in items:
            citation = _citation_from_dict(item)
            if citation is None:
                continue
            retrieved_citations[(citation.source_type, citation.resource_id)] = citation

    remember_citations(baseline.get("citations", []))

    @tool(
        "get_patient_snapshot",
        "Return a high-signal chart snapshot focused on safety, interactions, and active burden.",
        {},
    )
    async def get_patient_snapshot(_args: dict[str, Any]) -> dict[str, Any]:
        with start_span(SpanKind.TOOL, "get_patient_snapshot") as _snap_span:
            snapshot = get_relevant_provider_evidence(
                patient_id=patient_id,
                query="Summarize the current peri-operative risk picture and major active safety signals.",
                history=history,
                max_facts=10,
                max_citations=8,
            )
            remember_citations(snapshot.get("citations", []))
            result = {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(snapshot),
                    }
                ]
            }
            if _snap_span:
                _snap_span.output_data = json.dumps({"fact_count": len(snapshot.get("evidence_lines", [])), "citation_count": len(snapshot.get("citations", []))}, default=str)
            return result

    @tool(
        "query_chart_evidence",
        "Retrieve chart-grounded evidence and citations for a specific clinical question.",
        {
            "query": str,
            "max_facts": int,
        },
    )
    async def query_chart_evidence(args: dict[str, Any]) -> dict[str, Any]:
        query_text = str(args.get("query", "")).strip()
        if not query_text:
            return {
                "content": [{"type": "text", "text": "query is required"}],
                "is_error": True,
            }

        max_facts = args.get("max_facts", 8)
        try:
            max_facts_int = int(max_facts)
        except (TypeError, ValueError):
            max_facts_int = 8
        max_facts_int = max(3, min(max_facts_int, 12))

        with start_span(SpanKind.TOOL, "query_chart_evidence", input_data={"query": query_text, "max_facts": max_facts_int}) as _ev_span:
            evidence = get_relevant_provider_evidence(
                patient_id=patient_id,
                query=query_text,
                history=history,
                max_facts=max_facts_int,
                max_citations=8,
            )
            remember_citations(evidence.get("citations", []))
            if _ev_span:
                _ev_span.output_data = json.dumps({"fact_count": len(evidence.get("evidence_lines", [])), "citation_count": len(evidence.get("citations", []))}, default=str)

        return {
            "content": [
                {
                    "type": "text",
                    "text": json.dumps(evidence),
                }
            ]
        }

    mcp_server = create_sdk_mcp_server(
        name="fhir_chart",
        version="1.0.0",
        tools=[get_patient_snapshot, query_chart_evidence],
    )

    built_in_tools: list[str] = []
    if config.enable_web_search:
        built_in_tools.append("WebSearch")
    if config.enable_web_fetch:
        built_in_tools.append("WebFetch")

    allowed_tools = [
        "mcp__fhir_chart__get_patient_snapshot",
        "mcp__fhir_chart__query_chart_evidence",
    ]
    allowed_tools.extend(built_in_tools)

    options = ClaudeAgentOptions(
        model=config.model,
        cwd=_AGENT_PROFILE_DIR,
        setting_sources=["project"],
        system_prompt={"type": "preset", "preset": "claude_code"},
        permission_mode="dontAsk",
        tools=built_in_tools,
        allowed_tools=allowed_tools,
        mcp_servers={"fhir_chart": mcp_server},
        max_turns=config.max_turns,
        max_budget_usd=config.max_budget_usd,
    )

    prompt = (
        "You are handling a provider chart question for a single patient.\n"
        "Task: answer the provider directly, using chart-grounded evidence and explicit pushback when confidence is limited.\n"
        "\n"
        f"patient_id: {patient_id}\n"
        f"stance: {stance}\n"
        f"provider_question: {question}\n"
        "\n"
        "Recent conversation context:\n"
        f"{_conversation_excerpt(history)}\n"
        "\n"
        "Baseline evidence snapshot (already retrieved):\n"
        f"{json.dumps(baseline)}\n"
        "\n"
        "Execution rules:\n"
        "1) Use MCP tools to verify and deepen evidence before final answer.\n"
        "2) Do not invent citations; only cite evidence returned by tools.\n"
        "3) Keep answer concise and direct.\n"
        "4) If data quality is weak, push back explicitly.\n"
        "\n"
        "Return ONLY JSON with this schema:\n"
        "{\n"
        '  "answer": "string",\n'
        '  "confidence": "high|medium|low",\n'
        '  "citations": [\n'
        "    {\n"
        '      "source_type": "string",\n'
        '      "resource_id": "string",\n'
        '      "label": "string",\n'
        '      "detail": "string",\n'
        '      "event_date": "ISO-8601 string or null"\n'
        "    }\n"
        "  ],\n"
        '  "follow_ups": ["string", "string", "string"]\n'
        "}"
    )

    result_text = ""
    last_assistant_text = ""
    structured_output: Any = None
    result_stop_reason: str | None = None
    result_num_turns: int | None = None
    result_duration_api_ms: int | None = None

    # Trace the full SDK query/parse block so any downstream parse failures are captured.
    with start_span(
        SpanKind.LLM,
        "agent_query",
        input_data={"model": config.model, "stance": stance, "prompt": prompt},
    ) as llm_span:
        try:
            async for message in query(prompt=prompt, options=options):
                if isinstance(message, AssistantMessage):
                    text = _extract_assistant_text(message)
                    if text.strip():
                        last_assistant_text = text
                    continue

                if isinstance(message, ResultMessage):
                    if message.is_error:
                        details = "; ".join(message.errors or [])
                        raise AgentExecutionError(details or "Agent SDK returned an error result.")
                    if message.structured_output is not None:
                        structured_output = message.structured_output
                    if message.result and message.result.strip():
                        result_text = message.result

                    result_stop_reason = getattr(message, "stop_reason", None)
                    result_num_turns = getattr(message, "num_turns", None)
                    result_duration_api_ms = getattr(message, "duration_api_ms", None)

                    if llm_span:
                        usage = getattr(message, "usage", None)
                        if isinstance(usage, dict):
                            llm_span.input_tokens = usage.get("input_tokens")
                            llm_span.output_tokens = usage.get("output_tokens")
                            llm_span.cache_read_tokens = usage.get("cache_read_input_tokens")
                        llm_span.total_cost_usd = getattr(message, "total_cost_usd", None)
                        llm_span.num_turns = result_num_turns
        except CLINotFoundError as exc:
            if llm_span:
                llm_span.error = str(exc)
            raise AgentConfigurationError(
                "Claude CLI runtime not found. Install/repair claude-agent-sdk runtime before enabling anthropic mode."
            ) from exc
        except ClaudeSDKError as exc:
            if llm_span:
                llm_span.error = str(exc)
            raise AgentExecutionError(str(exc)) from exc

    parsed: dict[str, Any]
    if isinstance(structured_output, dict):
        parsed = structured_output
    elif result_text.strip():
        parsed = _parse_result_json(result_text)
    elif last_assistant_text.strip():
        parsed = _parse_result_json(last_assistant_text)
    else:
        raise AgentExecutionError("No parseable model output returned.")

    answer = str(parsed.get("answer", "")).strip()
    if not answer:
        answer = "Short answer: I could not produce a defensible answer from the available chart evidence."

    confidence = str(parsed.get("confidence", "medium")).strip().lower()
    if confidence not in {"high", "medium", "low"}:
        confidence = "medium"

    follow_ups_raw = parsed.get("follow_ups", [])
    follow_ups: list[str] = []
    if isinstance(follow_ups_raw, list):
        for item in follow_ups_raw:
            text = str(item).strip()
            if text and text not in follow_ups:
                follow_ups.append(text)
    if not follow_ups:
        fallback = baseline.get("follow_ups", [])
        if isinstance(fallback, list):
            follow_ups = [str(item).strip() for item in fallback if str(item).strip()][:3]

    citations: list[AssistantCitationPayload] = []
    citations_raw = parsed.get("citations", [])
    if isinstance(citations_raw, list):
        for item in citations_raw:
            if not isinstance(item, dict):
                continue
            key = (
                str(item.get("source_type", "")).strip(),
                str(item.get("resource_id", "")).strip(),
            )
            citation = retrieved_citations.get(key)
            if citation and all(
                (existing.source_type, existing.resource_id) != key for existing in citations
            ):
                citations.append(citation)

    if not citations:
        citations = list(retrieved_citations.values())[:6]

    if llm_span:
        llm_span.output_data = json.dumps(
            {
                "result_text": result_text or last_assistant_text,
                "stop_reason": result_stop_reason,
                "num_turns": result_num_turns,
                "duration_api_ms": result_duration_api_ms,
                "structured_output_present": isinstance(structured_output, dict),
            },
            default=str,
        )

    return AssistantResult(
        answer=answer,
        confidence=confidence,
        citations=citations,
        follow_ups=follow_ups[:3],
        engine="anthropic-agent-sdk",
    )


def answer_provider_question_with_agent_sdk(
    *,
    patient_id: str,
    question: str,
    history: list[dict[str, str]] | None,
    stance: str,
) -> AssistantResult:
    """Entry point for Anthropic Agent SDK mode."""
    api_key = _resolve_anthropic_api_key()
    if not api_key or "YOUR_KEY_HERE" in api_key:
        raise AgentConfigurationError("ANTHROPIC_API_KEY is required for anthropic assistant mode.")
    os.environ["ANTHROPIC_API_KEY"] = api_key

    if not _AGENT_PROFILE_DIR.exists():
        raise AgentConfigurationError(f"Agent profile directory not found: {_AGENT_PROFILE_DIR}")

    config = _load_config()

    try:
        return asyncio.run(
            _run_agent(
                patient_id=patient_id,
                question=question,
                history=history,
                stance=stance,
                config=config,
            )
        )
    except RuntimeError as exc:
        if "asyncio.run() cannot be called from a running event loop" in str(exc):
            loop = asyncio.new_event_loop()
            try:
                return loop.run_until_complete(
                    _run_agent(
                        patient_id=patient_id,
                        question=question,
                        history=history,
                        stance=stance,
                        config=config,
                    )
                )
            finally:
                loop.close()
        raise
