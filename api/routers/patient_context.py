"""/api/patient-context — patient-facing guided context intake."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException

from api.core.patient_context import (
    PatientContextConfigurationError,
    add_turn,
    create_session,
    export_markdown,
    get_session,
    private_cedars_available,
)
from api.models import (
    PatientContextExportResponse,
    PatientContextSessionCreateRequest,
    PatientContextSessionResponse,
    PatientContextTurnRequest,
    PatientContextTurnResponse,
)


router = APIRouter(prefix="/patient-context", tags=["patient-context"])


@router.get("/status")
def patient_context_status() -> dict:
    return {
        "private_blake_cedars_available": private_cedars_available(),
        "storage": "local-files",
    }


@router.post("/sessions", response_model=PatientContextSessionResponse)
def create_patient_context_session(
    payload: PatientContextSessionCreateRequest,
) -> PatientContextSessionResponse:
    return create_session(payload.patient_id, payload.source_mode)


@router.get("/sessions/{session_id}", response_model=PatientContextSessionResponse)
def get_patient_context_session(session_id: str) -> PatientContextSessionResponse:
    try:
        return get_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/turn", response_model=PatientContextTurnResponse)
def patient_context_turn(
    session_id: str,
    payload: PatientContextTurnRequest,
) -> PatientContextTurnResponse:
    try:
        return add_turn(session_id, payload.message, payload.selected_gap_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PatientContextConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/export", response_model=PatientContextExportResponse)
def export_patient_context(session_id: str) -> PatientContextExportResponse:
    try:
        return export_markdown(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
