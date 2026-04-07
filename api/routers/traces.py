"""
Traces API — read-only endpoints for querying LLM call traces.

Provides list, detail, and summary views for debugging and monitoring
the Provider Assistant's Anthropic SDK calls.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query

from api.core.tracing import (
    TRACING_ENABLED,
    get_trace_detail,
    get_traces_summary,
    query_traces,
)

router = APIRouter(prefix="/traces", tags=["traces"])
_TRACES_API_ENABLED = os.getenv(
    "TRACES_API_ENABLED",
    "true" if TRACING_ENABLED else "false",
).strip().lower() in {"1", "true", "yes", "on"}


def _assert_traces_api_enabled() -> None:
    if not _TRACES_API_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Traces API is disabled. Set TRACES_API_ENABLED=true to enable.",
        )


@router.get("/")
def list_traces(
    patient_id: str | None = Query(None, description="Filter by patient ID"),
    engine: str | None = Query(None, description="Filter by engine (e.g. anthropic-agent-sdk)"),
    status: str | None = Query(None, description="Filter by status (ok, error, fallback)"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> dict:
    """List traces with optional filters, sorted by most recent first."""
    _assert_traces_api_enabled()
    if not TRACING_ENABLED:
        return {
            "traces": [],
            "count": 0,
            "tracing_enabled": False,
            "message": "Tracing is disabled. Set TRACING_ENABLED=true to enable.",
        }

    traces = query_traces(
        patient_id=patient_id,
        engine=engine,
        status=status,
        limit=limit,
        offset=offset,
    )
    return {
        "traces": traces,
        "count": len(traces),
        "tracing_enabled": True,
    }


@router.get("/summary")
def traces_summary() -> dict:
    """Aggregate statistics across all traces — costs, tokens, latency, breakdowns."""
    _assert_traces_api_enabled()
    if not TRACING_ENABLED:
        return {
            "tracing_enabled": False,
            "message": "Tracing is disabled. Set TRACING_ENABLED=true to enable.",
        }

    summary = get_traces_summary()
    return {
        **summary,
        "tracing_enabled": True,
    }


@router.get("/{trace_id}")
def trace_detail(trace_id: str) -> dict:
    """Get a single trace with all spans — full prompt, response, and tool call data."""
    _assert_traces_api_enabled()
    if not TRACING_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Tracing is disabled. Set TRACING_ENABLED=true to enable.",
        )

    result = get_trace_detail(trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    return result
