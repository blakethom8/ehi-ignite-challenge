"""
Internal HTTP tools for the Cursor sidecar (future MCP / HTTP MCP transport).

Secured with ``X-EHI-Cursor-Tool-Secret`` matching ``CURSOR_INTERNAL_TOOL_SECRET``.
These wrap the same Python surfaces as the Anthropic Agent SDK MCP tools.
"""

from __future__ import annotations

import os
from typing import Annotated, Any

from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, ConfigDict, Field

from api.core.provider_assistant import get_relevant_provider_evidence
from api.core.sof_tools import run_sql as sof_run_sql
from api.core.sof_tools import tool_result_payload as sof_tool_result_payload

router = APIRouter(prefix="/internal/cursor-tools", tags=["cursor-internal-tools"])


def require_cursor_tool_secret(
    x_ehi_cursor_tool_secret: Annotated[str | None, Header(alias="X-EHI-Cursor-Tool-Secret")] = None,
) -> None:
    expected = (os.getenv("CURSOR_INTERNAL_TOOL_SECRET") or "").strip()
    if not expected:
        raise HTTPException(status_code=503, detail="CURSOR_INTERNAL_TOOL_SECRET is not configured")
    if not x_ehi_cursor_tool_secret or x_ehi_cursor_tool_secret.strip() != expected:
        raise HTTPException(status_code=401, detail="invalid or missing X-EHI-Cursor-Tool-Secret")


class HistoryTurn(BaseModel):
    model_config = ConfigDict(extra="ignore")

    role: str = "user"
    content: str = ""


class PatientQueryBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1)
    query: str = Field(min_length=1)
    max_facts: int = Field(default=8, ge=3, le=12)
    history: list[HistoryTurn] = Field(default_factory=list)


class PatientSnapshotBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1)
    history: list[HistoryTurn] = Field(default_factory=list)


class RunSqlBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(min_length=1)
    limit: int = Field(default=50, ge=1, le=500)


def _history_as_dicts(turns: list[HistoryTurn]) -> list[dict[str, str]] | None:
    if not turns:
        return None
    return [{"role": t.role, "content": t.content} for t in turns]


@router.post("/query-chart-evidence")
def query_chart_evidence(
    body: PatientQueryBody,
    _: None = Depends(require_cursor_tool_secret),
) -> dict[str, Any]:
    hist = _history_as_dicts(body.history)
    return get_relevant_provider_evidence(
        patient_id=body.patient_id.strip(),
        query=body.query.strip(),
        history=hist,
        max_facts=body.max_facts,
        max_citations=8,
    )


@router.post("/patient-snapshot")
def patient_snapshot(
    body: PatientSnapshotBody,
    _: None = Depends(require_cursor_tool_secret),
) -> dict[str, Any]:
    hist = _history_as_dicts(body.history)
    return get_relevant_provider_evidence(
        patient_id=body.patient_id.strip(),
        query="Summarize the current peri-operative risk picture and major active safety signals.",
        history=hist,
        max_facts=10,
        max_citations=8,
    )


@router.post("/run-sql")
def run_sql_endpoint(
    body: RunSqlBody,
    _: None = Depends(require_cursor_tool_secret),
) -> dict[str, Any]:
    result = sof_run_sql(body.query.strip(), limit=body.limit)
    return sof_tool_result_payload(result)
