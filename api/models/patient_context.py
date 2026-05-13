"""
Patient Context guided-intake models — drive the guided gap-filling
conversation captured under `data/patient-context/`.

Consumed by `api/routers/patient_context.py` and
`api/core/patient_context.py`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Patient Context guided intake
# ---------------------------------------------------------------------------

class PatientContextSessionCreateRequest(BaseModel):
    patient_id: str = Field(..., min_length=1, max_length=300)
    source_mode: Literal["synthetic", "private_blake_cedars", "selected_patient"] = "selected_patient"


class PatientContextTurnRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    selected_gap_id: str | None = Field(default=None, max_length=80)


class PatientContextGapCard(BaseModel):
    id: str
    category: Literal[
        "missing_sources",
        "medication_reality",
        "timeline_gap",
        "uncertain_fact",
        "qualitative_context",
    ]
    title: str
    prompt: str
    why_it_matters: str
    status: Literal["open", "answered", "skipped"] = "open"
    priority: int = Field(ge=1, le=5)
    evidence: list[str] = Field(default_factory=list)


class PatientContextTurn(BaseModel):
    id: str
    role: Literal["patient", "assistant"]
    content: str
    created_at: datetime
    linked_gap_id: str | None = None


class PatientContextFact(BaseModel):
    id: str
    source: Literal["patient-reported"] = "patient-reported"
    linked_gap_id: str | None = None
    statement: str
    summary: str
    confidence: Literal["high", "medium", "low"] = "medium"
    created_at: datetime


class PatientContextExportStatus(BaseModel):
    generated: bool = False
    files: list[str] = Field(default_factory=list)
    generated_at: datetime | None = None


class PatientContextSessionResponse(BaseModel):
    session_id: str
    patient_id: str
    patient_label: str
    source_mode: Literal["synthetic", "private_blake_cedars", "selected_patient"]
    source_posture: str
    gap_cards: list[PatientContextGapCard]
    turns: list[PatientContextTurn]
    facts: list[PatientContextFact]
    export_status: PatientContextExportStatus


class PatientContextTurnResponse(PatientContextSessionResponse):
    assistant_message: PatientContextTurn


class PatientContextExportResponse(BaseModel):
    session_id: str
    generated_at: datetime
    files: list[str]
    preview: str
