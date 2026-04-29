"""
Traces API — read-only endpoints for querying LLM call traces.

Provides list, detail, and summary views for debugging and monitoring
the Provider Assistant's Anthropic SDK calls.
"""

from __future__ import annotations

import os
import secrets

from fastapi import APIRouter, HTTPException, Query, Request, status

from api.core.tracing import (
    TRACING_ENABLED,
    get_trace_detail,
    get_traces_summary,
    query_traces,
)

router = APIRouter(prefix="/traces", tags=["traces"])
_TRACES_API_ENABLED = os.getenv("TRACES_API_ENABLED", "false").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
_TRACES_API_TOKEN = os.getenv("TRACES_API_TOKEN", "").strip()
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()


def _assert_traces_api_enabled(request: Request) -> None:
    if not _TRACES_API_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Traces API is disabled. Set TRACES_API_ENABLED=true to enable.",
        )
    if _ENVIRONMENT in {"prod", "production"} and not _TRACES_API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Traces API requires TRACES_API_TOKEN in production.",
        )
    if _TRACES_API_TOKEN:
        expected = f"Bearer {_TRACES_API_TOKEN}"
        provided = request.headers.get("Authorization", "")
        if not secrets.compare_digest(provided, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid traces API token.",
            )


@router.get("/")
def list_traces(
    request: Request,
    patient_id: str | None = Query(None, description="Filter by patient ID"),
    engine: str | None = Query(None, description="Filter by engine (e.g. anthropic-agent-sdk)"),
    status: str | None = Query(None, description="Filter by status (ok, error, fallback)"),
    limit: int = Query(50, ge=1, le=500, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
) -> dict:
    """List traces with optional filters, sorted by most recent first."""
    _assert_traces_api_enabled(request)
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
def traces_summary(request: Request) -> dict:
    """Aggregate statistics across all traces — costs, tokens, latency, breakdowns."""
    _assert_traces_api_enabled(request)
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
def trace_detail(request: Request, trace_id: str) -> dict:
    """Get a single trace with all spans — full prompt, response, and tool call data."""
    _assert_traces_api_enabled(request)
    if not TRACING_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="Tracing is disabled. Set TRACING_ENABLED=true to enable.",
        )

    result = get_trace_detail(trace_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Trace {trace_id} not found")
    return result
