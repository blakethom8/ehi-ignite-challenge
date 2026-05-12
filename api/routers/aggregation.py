"""/api/aggregation — patient data assembly workflow endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile

from api.core.auth import authorize_patient_access, require_access_session, require_authenticated_session
from api.core.aggregation import (
    cleaning_queue,
    create_profile,
    delete_profile,
    delete_upload,
    readiness,
    save_upload,
    source_inventory,
    update_profile,
    upload_prepared_json,
    upload_preview,
)
from api.models import (
    AggregationCleaningQueueResponse,
    AggregationCreateProfileRequest,
    AggregationCreateProfileResponse,
    AggregationDeleteResponse,
    AggregationEnvironmentResponse,
    AggregationPreparedPreviewResponse,
    AggregationReadinessResponse,
    AggregationUpdateProfileRequest,
    AggregationUploadResponse,
)


router = APIRouter(prefix="/aggregation", tags=["aggregation"])


@router.get("/sources/{patient_id}", response_model=AggregationEnvironmentResponse)
def get_source_inventory(patient_id: str, request: Request) -> AggregationEnvironmentResponse:
    session = require_access_session(request)
    resolved_patient_id = authorize_patient_access(
        session,
        patient_id,
        event_type="aggregation.sources",
    )
    return source_inventory(resolved_patient_id, session_user_id=session.user_id)


@router.get("/cleaning-queue/{patient_id}", response_model=AggregationCleaningQueueResponse)
def get_cleaning_queue(patient_id: str, request: Request) -> AggregationCleaningQueueResponse:
    session = require_access_session(request)
    resolved_patient_id = authorize_patient_access(
        session,
        patient_id,
        event_type="aggregation.cleaning_queue",
    )
    return cleaning_queue(resolved_patient_id, session_user_id=session.user_id)


@router.get("/readiness/{patient_id}", response_model=AggregationReadinessResponse)
def get_readiness(patient_id: str, request: Request) -> AggregationReadinessResponse:
    session = require_access_session(request)
    resolved_patient_id = authorize_patient_access(
        session,
        patient_id,
        event_type="aggregation.readiness",
    )
    return readiness(resolved_patient_id, session_user_id=session.user_id)


@router.post("/profiles", response_model=AggregationCreateProfileResponse)
def create_patient_profile(payload: AggregationCreateProfileRequest, request: Request) -> AggregationCreateProfileResponse:
    session = require_authenticated_session(request)
    return create_profile(payload, owner_user_id=session.user_id)


@router.patch("/profiles/{patient_id}", response_model=AggregationCreateProfileResponse)
def update_patient_profile(patient_id: str, payload: AggregationUpdateProfileRequest, request: Request) -> AggregationCreateProfileResponse:
    session = require_authenticated_session(request)
    resolved_patient_id = authorize_patient_access(
        session,
        patient_id,
        event_type="aggregation.profile_updated",
    )
    try:
        return update_profile(resolved_patient_id, payload, session_user_id=session.user_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.delete("/profiles/{patient_id}", response_model=AggregationDeleteResponse)
def delete_patient_profile(patient_id: str, request: Request) -> AggregationDeleteResponse:
    session = require_authenticated_session(request)
    resolved_patient_id = authorize_patient_access(
        session,
        patient_id,
        event_type="aggregation.profile_deleted",
    )
    try:
        return delete_profile(resolved_patient_id, session_user_id=session.user_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/uploads/{patient_id}/{file_id}/preview", response_model=AggregationPreparedPreviewResponse)
def get_upload_preview(patient_id: str, file_id: str, request: Request) -> AggregationPreparedPreviewResponse:
    session = require_access_session(request)
    resolved_patient_id = authorize_patient_access(
        session,
        patient_id,
        event_type="aggregation.upload_preview",
    )
    try:
        return upload_preview(resolved_patient_id, file_id, session_user_id=session.user_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/uploads/{patient_id}/{file_id}/prepared-json")
def get_upload_prepared_json(patient_id: str, file_id: str, request: Request) -> dict:
    session = require_access_session(request)
    resolved_patient_id = authorize_patient_access(
        session,
        patient_id,
        event_type="aggregation.prepared_json",
    )
    try:
        return upload_prepared_json(resolved_patient_id, file_id, session_user_id=session.user_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/uploads/{patient_id}", response_model=AggregationUploadResponse)
async def upload_source_file(
    patient_id: str,
    request: Request,
    file: UploadFile = File(...),
    data_type: str = Form("Not classified"),
    source_name: str = Form(""),
    date_range: str = Form(""),
    contains: str = Form("[]"),
    description: str = Form(""),
    context_notes: str = Form(""),
) -> AggregationUploadResponse:
    session = require_authenticated_session(request)
    resolved_patient_id = authorize_patient_access(
        session,
        patient_id,
        event_type="aggregation.upload_created",
    )
    try:
        parsed_contains = json.loads(contains)
        contains_items = [str(item).strip() for item in parsed_contains if str(item).strip()] if isinstance(parsed_contains, list) else []
    except json.JSONDecodeError:
        contains_items = [item.strip() for item in contains.split(",") if item.strip()]
    try:
        return save_upload(
            resolved_patient_id,
            file.filename or "upload.bin",
            file.content_type,
            file.file,
            data_type=data_type,
            source_name=source_name,
            date_range=date_range,
            contains=contains_items,
            description=description,
            context_notes=context_notes,
            session_user_id=session.user_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc


@router.delete("/uploads/{patient_id}/{file_id}", response_model=AggregationDeleteResponse)
def delete_source_file(patient_id: str, file_id: str, request: Request) -> AggregationDeleteResponse:
    session = require_authenticated_session(request)
    resolved_patient_id = authorize_patient_access(
        session,
        patient_id,
        event_type="aggregation.upload_deleted",
    )
    try:
        return delete_upload(resolved_patient_id, file_id, session_user_id=session.user_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
