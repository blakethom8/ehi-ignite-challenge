"""
Data Aggregator workspace / canonical-patient response models — patient
workspaces, uploaded files, cleaning queue, readiness checklist, and the
canonical-patient summary shapes used by the canonical router.

Consumed by `api/routers/aggregation.py`, `api/routers/canonical.py`,
`api/core/aggregation.py`, `api/core/canonical_service.py`, and
`api/core/demo_aggregate_seed.py`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Aggregation profiles (patient workspaces)
# ---------------------------------------------------------------------------

class AggregationProfile(BaseModel):
    id: str
    display_name: str
    created_at: datetime
    updated_at: datetime
    notes: str = ""
    storage_mode: str = "server-local-workspace"
    owner_user_id: str | None = None


class AggregationCreateProfileRequest(BaseModel):
    display_name: str = "New patient workspace"
    notes: str = ""


class AggregationUpdateProfileRequest(BaseModel):
    display_name: str
    notes: str = ""


class AggregationCreateProfileResponse(BaseModel):
    profile: AggregationProfile
    storage_posture: str


# ---------------------------------------------------------------------------
# Canonical patient summary (used by /canonical and patient lists)
# ---------------------------------------------------------------------------

class CanonicalSourceSummary(BaseModel):
    id: str
    label: str
    kind: str
    status: str
    status_label: str
    total_resources: int


class CanonicalPatientSummary(BaseModel):
    patient_id: str
    patient_name: str
    workspace_id: str
    source_count: int
    prepared_source_count: int
    needs_preparation_count: int
    total_resources: int
    canonical_observation_count: int
    canonical_condition_count: int
    canonical_medication_count: int
    canonical_allergy_count: int
    canonical_immunization_count: int
    encounter_count: int
    review_item_count: int
    date_start: str | None = None
    date_end: str | None = None
    storage_mode: str
    storage_description: str
    sources: list[CanonicalSourceSummary] = Field(default_factory=list)
    fallback_modes: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Data Aggregator workflow
# ---------------------------------------------------------------------------

class AggregationUploadedFile(BaseModel):
    file_id: str
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    status: Literal["uploaded", "needs_processing", "unsupported"] = "uploaded"
    data_type: str = "Not classified"
    source_name: str = ""
    date_range: str = ""
    contains: list[str] = Field(default_factory=list)
    description: str = ""
    context_notes: str = ""
    extraction_confidence: Literal["high", "medium", "low", "unknown"] = "unknown"
    storage_path: str = ""
    parse_status: Literal[
        "stored",
        "ready_to_extract",
        "extracted",
        "structured",
        "unsupported",
    ] = "stored"
    next_step: str = ""
    derived_artifacts: list[str] = Field(default_factory=list)


class AggregationPreparedPreviewItem(BaseModel):
    resource_type: str
    label: str
    value: str = ""
    date: str = ""
    status: str = ""


class AggregationPreparedPreviewResponse(BaseModel):
    patient_id: str
    file_id: str
    file_name: str
    parse_status: Literal[
        "stored",
        "ready_to_extract",
        "extracted",
        "structured",
        "unsupported",
    ]
    output_type: str
    total_resources: int = 0
    resource_counts: dict[str, int] = Field(default_factory=dict)
    artifact_paths: list[str] = Field(default_factory=list)
    date_start: str = ""
    date_end: str = ""
    json_preview: dict[str, Any] | None = None
    preview_items: list[AggregationPreparedPreviewItem] = Field(default_factory=list)
    message: str = ""


class AggregationSourceCard(BaseModel):
    id: str
    name: str
    category: Literal[
        "synthetic_fhir",
        "private_ehi",
        "portal",
        "file_upload",
        "lab",
        "pharmacy",
        "payer",
        "wearable",
        "planned_adapter",
    ]
    mode: Literal["available", "missing", "planned", "uploaded", "private"]
    status_label: str
    record_count: int = 0
    last_updated: datetime | None = None
    confidence: Literal["high", "medium", "low", "not_started"] = "not_started"
    posture: str
    next_action: str
    help_title: str
    help_body: str
    evidence: list[str] = Field(default_factory=list)


class AggregationEnvironmentResponse(BaseModel):
    patient_id: str
    patient_label: str
    environment_label: str
    source_posture: str
    private_blake_cedars_available: bool
    synthetic_resource_counts: dict[str, int]
    uploaded_files: list[AggregationUploadedFile]
    source_cards: list[AggregationSourceCard]
    guidance: list[str]


class AggregationCleaningIssue(BaseModel):
    id: str
    category: Literal[
        "source_gap",
        "medication_reality",
        "timeline_gap",
        "duplicate_candidate",
        "uncoded_file",
        "provenance_gap",
        "patient_context",
    ]
    severity: Literal["high", "medium", "low"]
    status: Literal["open", "ready_for_review", "planned", "resolved"] = "open"
    title: str
    body: str
    recommended_action: str
    source_ids: list[str] = Field(default_factory=list)
    evidence: list[str] = Field(default_factory=list)
    help_title: str
    help_body: str


class AggregationCleaningQueueResponse(BaseModel):
    patient_id: str
    patient_label: str
    issue_counts: dict[str, int]
    issues: list[AggregationCleaningIssue]
    guidance: list[str]


class AggregationReadinessItem(BaseModel):
    id: str
    label: str
    status: Literal["ready", "needs_review", "missing", "planned"]
    score: int = Field(ge=0, le=100)
    body: str
    next_action: str


class AggregationReadinessResponse(BaseModel):
    patient_id: str
    patient_label: str
    readiness_score: int = Field(ge=0, le=100)
    posture: str
    checklist: list[AggregationReadinessItem]
    blockers: list[str]
    export_targets: list[str]


class AggregationUploadResponse(BaseModel):
    file: AggregationUploadedFile
    storage_posture: str
    source_card: AggregationSourceCard


class AggregationDeleteResponse(BaseModel):
    deleted: bool
    file_id: str
