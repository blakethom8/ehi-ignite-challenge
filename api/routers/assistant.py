"""
/api/assistant — provider-facing conversational chart assistant.
"""

import json

from fastapi import APIRouter, HTTPException

from api.core.provider_assistant_cursor import CursorSidecarConfigurationError, CursorSidecarExecutionError
from api.core.provider_assistant_service import answer_provider_question
from api.core.tracing import get_current_trace, SpanKind
from api.models import (
    ProviderAssistantRequest,
    ProviderAssistantResponse,
    ProviderAssistantCitation,
    ToolCallDetail,
    TraceDetail,
)

import os

router = APIRouter(prefix="/assistant", tags=["assistant"])


def _env_bool(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


def _client_overrides_enabled() -> bool:
    default = os.getenv("ENVIRONMENT", "development").strip().lower() not in {"prod", "production"}
    return _env_bool("PROVIDER_ASSISTANT_ALLOW_CLIENT_OVERRIDES", default)


def _max_response_tokens() -> int:
    raw = os.getenv("PROVIDER_ASSISTANT_MAX_RESPONSE_TOKENS", "2000")
    try:
        value = int(raw)
    except ValueError:
        return 2000
    return min(max(value, 128), 4000)


def _cursor_sidecar_model_options() -> list[dict[str, str]]:
    raw = (os.getenv("CURSOR_SIDECAR_MODEL_ALLOWLIST") or "").strip()
    if raw:
        return [
            {
                "id": m.strip(),
                "label": m.strip(),
                "description": "Allowlisted Cursor sidecar model",
            }
            for m in raw.split(",")
            if m.strip()
        ]
    dm = (os.getenv("CURSOR_SIDECAR_MODEL") or "composer-2").strip() or "composer-2"
    seeds = ["composer-2", "auto", dm]
    seen: set[str] = set()
    out: list[dict[str, str]] = []
    for m in seeds:
        if m not in seen:
            seen.add(m)
            out.append({"id": m, "label": m, "description": "Cursor @cursor/sdk model id"})
    return out


@router.get("/settings")
def get_assistant_settings() -> dict:
    """Return current assistant configuration and available options."""
    return {
        "current": {
            "mode": os.getenv("PROVIDER_ASSISTANT_MODE", "deterministic"),
            "model": os.getenv("PROVIDER_ASSISTANT_MODEL", "claude-sonnet-4-5"),
            "max_tokens": _max_response_tokens(),
        },
        "client_overrides_enabled": _client_overrides_enabled(),
        "max_tokens_limit": _max_response_tokens(),
        "available_modes": [
            {"id": "deterministic", "label": "Deterministic", "description": "Rule-based, instant (<100ms), no LLM cost"},
            {"id": "context", "label": "Context (Recommended)", "description": "Single Claude call with pre-built clinical context"},
            {"id": "anthropic", "label": "Agent SDK", "description": "Multi-turn agentic loop with tool calls (slowest)"},
            {"id": "cursor", "label": "Cursor sidecar", "description": "Cursor @cursor/sdk local agent via Node sidecar"},
        ],
        "available_models": [
            {"id": "claude-haiku-4-5", "label": "Haiku 4.5", "description": "Fastest, good for quick Q&A", "speed": "fast"},
            {"id": "claude-sonnet-4-5", "label": "Sonnet 4.5", "description": "Balanced speed and quality", "speed": "medium"},
            {"id": "claude-sonnet-4-6", "label": "Sonnet 4.6", "description": "Latest Sonnet, best quality/speed ratio", "speed": "medium"},
            {"id": "claude-opus-4-5", "label": "Opus 4.5", "description": "Most capable, slowest", "speed": "slow"},
        ],
        "cursor_sidecar": {
            "sidecar_url_configured": bool((os.getenv("CURSOR_SIDECAR_URL") or "").strip()),
            "default_model": (os.getenv("CURSOR_SIDECAR_MODEL") or "composer-2").strip() or "composer-2",
            "available_models": _cursor_sidecar_model_options(),
        },
    }


def _build_trace_detail() -> TraceDetail | None:
    """Extract tool calls and context from the current trace (if tracing is active)."""
    trace = get_current_trace()
    if trace is None:
        return None

    tool_calls: list[ToolCallDetail] = []
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0
    system_prompt = ""

    for span in trace.spans:
        # Accumulate token counts from LLM spans
        if span.kind == SpanKind.LLM:
            total_input_tokens += span.input_tokens or 0
            total_output_tokens += span.output_tokens or 0
            total_cost += span.total_cost_usd or 0.0
            # Extract system prompt preview from LLM span input_data
            if span.input_data and not system_prompt:
                try:
                    data = json.loads(span.input_data)
                    prompt = data.get("system_prompt", "")
                    if prompt:
                        system_prompt = prompt[:12000]
                except (json.JSONDecodeError, AttributeError):
                    pass

        # Capture tool, retrieval, and Cursor sidecar LLM invoke spans
        if span.kind in (SpanKind.TOOL, SpanKind.RETRIEVAL) or (
            span.kind == SpanKind.LLM and span.name == "cursor_sidecar_invoke"
        ):
            # Build human-readable input summary
            input_summary = ""
            if span.input_data:
                try:
                    data = json.loads(span.input_data)
                    if span.name == "run_sql":
                        input_summary = data.get("query", "")
                    elif span.name == "query_chart_evidence":
                        input_summary = f"Query: {data.get('query', '')}"
                    elif span.name == "get_patient_snapshot":
                        input_summary = "Fetching patient safety + chart snapshot"
                    elif span.name == "baseline_evidence":
                        input_summary = f"Building baseline for: {data.get('question', '')}"
                    elif span.name == "cursor_baseline_evidence":
                        input_summary = f"Cursor baseline for: {data.get('question', '')}"
                    elif span.name == "cursor_sidecar_invoke":
                        input_summary = (
                            f"model={data.get('model', '')} patient={data.get('patient_id', '')}"
                        )
                    else:
                        input_summary = json.dumps(data)[:200]
                except (json.JSONDecodeError, AttributeError):
                    input_summary = str(span.input_data)[:200]

            # Build human-readable output summary
            output_summary = ""
            if span.output_data:
                try:
                    data = json.loads(span.output_data)
                    if span.name == "run_sql":
                        rc = data.get("row_count", "?")
                        trunc = " (truncated)" if data.get("truncated") else ""
                        err = data.get("error")
                        output_summary = f"Error: {err}" if err else f"{rc} rows returned{trunc}"
                    elif span.name in (
                        "query_chart_evidence",
                        "get_patient_snapshot",
                        "baseline_evidence",
                        "cursor_baseline_evidence",
                    ):
                        fc = data.get("fact_count", "?")
                        cc = data.get("citation_count", "?")
                        output_summary = f"{fc} facts, {cc} citations"
                    elif span.name == "cursor_sidecar_invoke":
                        output_summary = json.dumps(data)[:240]
                    else:
                        output_summary = json.dumps(data)[:200]
                except (json.JSONDecodeError, AttributeError):
                    output_summary = str(span.output_data)[:200]

            tool_calls.append(ToolCallDetail(
                tool_name=span.name,
                input_summary=input_summary,
                output_summary=output_summary,
                duration_ms=span.duration_ms,
                error=span.error,
            ))

    return TraceDetail(
        trace_id=trace.trace_id,
        duration_ms=trace.duration_ms,
        input_tokens=total_input_tokens,
        output_tokens=total_output_tokens,
        total_cost_usd=total_cost if total_cost > 0 else None,
        tool_calls=tool_calls,
        system_prompt_preview=system_prompt,
    )


@router.post("/chat", response_model=ProviderAssistantResponse)
def provider_chat(payload: ProviderAssistantRequest) -> ProviderAssistantResponse:
    """
    Chat endpoint for provider Q&A over a single patient's chart.
    """
    if not payload.patient_id:
        raise HTTPException(status_code=422, detail="patient_id is required")
    if not payload.question.strip():
        raise HTTPException(status_code=422, detail="question is required")

    try:
        result = answer_provider_question(
            patient_id=payload.patient_id,
            question=payload.question,
            history=[turn.model_dump() for turn in payload.history],
            context_packages=[package.model_dump() for package in payload.context_packages],
            stance=payload.stance,
            model_override=payload.model,
            mode_override=payload.mode,
            max_tokens_override=payload.max_tokens,
            cursor_model=payload.cursor_model,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except CursorSidecarConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except CursorSidecarExecutionError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Capture trace detail for transparency
    trace_detail = _build_trace_detail()

    # If tracing didn't produce a trace, build one from the result's transparency fields
    if trace_detail is None:
        if result.system_prompt:
            # LLM mode without tracing — use the result's captured system prompt
            trace_detail = TraceDetail(
                trace_id=f"{result.engine or 'unknown'}-{payload.patient_id[:8]}",
                system_prompt_preview=result.system_prompt,
            )
        else:
            # Deterministic engine — describe the approach
            trace_detail = TraceDetail(
                trace_id="deterministic",
                system_prompt_preview=(
                    f"Engine: deterministic (rule-based fact ranking)\n"
                    f"Patient: {payload.patient_id}\n"
                    f"Question: {payload.question}\n"
                    f"Stance: {payload.stance}\n\n"
                    f"The deterministic engine builds a fact corpus from the patient's FHIR bundle, "
                    f"ranks facts by keyword relevance to the question, and synthesizes a direct answer "
                    f"from the top-ranked facts. No LLM is involved."
                ),
            )

    # Enrich trace with transparency metadata from the result (always available)
    if result.system_prompt and not trace_detail.system_prompt_preview:
        trace_detail.system_prompt_preview = result.system_prompt
    if result.model_used:
        trace_detail.model_used = result.model_used
    if result.mode_used:
        trace_detail.mode_used = result.mode_used
    if result.max_tokens_used:
        trace_detail.max_tokens_used = result.max_tokens_used
    if result.context_token_estimate:
        trace_detail.context_token_estimate = result.context_token_estimate
    if result.history_turns_sent is not None:
        trace_detail.history_turns_sent = result.history_turns_sent

    # Include retrieved facts from the engine
    if result.retrieved_facts:
        trace_detail.retrieved_facts = result.retrieved_facts

    return ProviderAssistantResponse(
        patient_id=payload.patient_id,
        answer=result.answer,
        confidence=result.confidence,
        stance=payload.stance,
        engine=result.engine,
        citations=[
            ProviderAssistantCitation(
                source_type=c.source_type,
                resource_id=c.resource_id,
                label=c.label,
                detail=c.detail,
                event_date=c.event_date,
            )
            for c in result.citations
        ],
        follow_ups=result.follow_ups,
        trace=trace_detail,
    )
