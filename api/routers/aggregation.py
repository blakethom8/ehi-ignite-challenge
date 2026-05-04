"""/api/aggregation — patient data assembly workflow endpoints."""

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, UploadFile

from api.core.aggregation import (
    cleaning_queue,
    create_profile,
    delete_upload,
    readiness,
    save_upload,
    source_inventory,
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
    AggregationUploadResponse,
)


router = APIRouter(prefix="/aggregation", tags=["aggregation"])


@router.get("/sources/{patient_id}", response_model=AggregationEnvironmentResponse)
def get_source_inventory(patient_id: str) -> AggregationEnvironmentResponse:
    return source_inventory(patient_id)


@router.get("/cleaning-queue/{patient_id}", response_model=AggregationCleaningQueueResponse)
def get_cleaning_queue(patient_id: str) -> AggregationCleaningQueueResponse:
    return cleaning_queue(patient_id)


@router.get("/readiness/{patient_id}", response_model=AggregationReadinessResponse)
def get_readiness(patient_id: str) -> AggregationReadinessResponse:
    return readiness(patient_id)


@router.post("/profiles", response_model=AggregationCreateProfileResponse)
def create_patient_profile(payload: AggregationCreateProfileRequest) -> AggregationCreateProfileResponse:
    return create_profile(payload)


@router.get("/uploads/{patient_id}/{file_id}/preview", response_model=AggregationPreparedPreviewResponse)
def get_upload_preview(patient_id: str, file_id: str) -> AggregationPreparedPreviewResponse:
    try:
        return upload_preview(patient_id, file_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/uploads/{patient_id}/{file_id}/prepared-json")
def get_upload_prepared_json(patient_id: str, file_id: str) -> dict:
    try:
        return upload_prepared_json(patient_id, file_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/uploads/{patient_id}", response_model=AggregationUploadResponse)
async def upload_source_file(
    patient_id: str,
    file: UploadFile = File(...),
    data_type: str = Form("Not classified"),
    source_name: str = Form(""),
    date_range: str = Form(""),
    contains: str = Form("[]"),
    description: str = Form(""),
    context_notes: str = Form(""),
) -> AggregationUploadResponse:
    try:
        parsed_contains = json.loads(contains)
        contains_items = [str(item).strip() for item in parsed_contains if str(item).strip()] if isinstance(parsed_contains, list) else []
    except json.JSONDecodeError:
        contains_items = [item.strip() for item in contains.split(",") if item.strip()]
    try:
        return save_upload(
            patient_id,
            file.filename or "upload.bin",
            file.content_type,
            file.file,
            data_type=data_type,
            source_name=source_name,
            date_range=date_range,
            contains=contains_items,
            description=description,
            context_notes=context_notes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc


@router.delete("/uploads/{patient_id}/{file_id}", response_model=AggregationDeleteResponse)
def delete_source_file(patient_id: str, file_id: str) -> AggregationDeleteResponse:
    try:
        return delete_upload(patient_id, file_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
