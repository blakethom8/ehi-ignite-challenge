"""
/api/assistant — provider-facing conversational chart assistant.
"""

import json

from fastapi import APIRouter, HTTPException

from api.core.provider_assistant_service import answer_provider_question
from api.core.tracing import get_current_trace, SpanKind
from api.models import (
    ProviderAssistantRequest,
    ProviderAssistantResponse,
    ProviderAssistantCitation,
    ToolCallDetail,
    TraceDetail,
)

router = APIRouter(prefix="/assistant", tags=["assistant"])


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
                        system_prompt = prompt[:2000]
                except (json.JSONDecodeError, AttributeError):
                    pass

        # Capture tool and retrieval spans
        if span.kind in (SpanKind.TOOL, SpanKind.RETRIEVAL):
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
                    elif span.name in ("query_chart_evidence", "get_patient_snapshot", "baseline_evidence"):
                        fc = data.get("fact_count", "?")
                        cc = data.get("citation_count", "?")
                        output_summary = f"{fc} facts, {cc} citations"
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
            stance=payload.stance,
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    # Capture trace detail for transparency
    trace_detail = _build_trace_detail()

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
