"""
Harmonization response models — cross-source merge surface
(Observations, Conditions, Medications, Allergies, Immunizations,
Clinical Notes / Artifacts), Provenance walks, extract-job lifecycle
events, run summaries, review decisions, published-chart snapshots, and
the guest-harmonization (unauthenticated demo) variants.

Consumed by `api/routers/harmonize.py` and
`api/routers/guest_harmonization.py`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Guest harmonization (unauthenticated demo run)
# ---------------------------------------------------------------------------

class GuestHarmonizationUploadedFile(BaseModel):
    file_id: str
    file_name: str
    content_type: str
    size_bytes: int
    uploaded_at: datetime
    storage_path: str
    status: Literal["uploaded"] = "uploaded"


class GuestHarmonizationOutput(BaseModel):
    output_id: str
    file_name: str
    content_type: str
    size_bytes: int
    created_at: datetime
    storage_path: str


class GuestHarmonizationProgressEvent(BaseModel):
    event_id: str
    event_type: str
    created_at: datetime
    stage: str | None = None
    message: str
    source_id: str | None = None
    source_label: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    page_count: int | None = None
    processed_pages: int | None = None
    total_pages: int | None = None
    processed_files: int | None = None
    total_files: int | None = None
    progress_basis: str | None = None
    is_estimate: bool | None = None


class GuestHarmonizationProgress(BaseModel):
    """Mirror of the authenticated ExtractJob shape so the same React
    components (PdfPageProgressMap, PdfExtractionEventTimeline) can render
    both surfaces."""

    status: Literal["pending", "running", "complete", "failed"] = "pending"
    stage: str = "Queued"
    total_files: int = 0
    processed_files: int = 0
    total_pages: int = 0
    processed_pages: int = 0
    estimated_processed_pages: int = 0
    current_source_label: str | None = None
    progress_mode: Literal["lifecycle", "reported"] = "lifecycle"
    progress_percent: int = 0
    started_at: datetime | None = None
    completed_at: datetime | None = None
    events: list[GuestHarmonizationProgressEvent] = Field(default_factory=list)


class GuestHarmonizationRunResponse(BaseModel):
    run_id: str
    mode: Literal["guest"] = "guest"
    created_at: datetime
    expires_at: datetime
    uploaded_files: list[GuestHarmonizationUploadedFile] = Field(default_factory=list)
    outputs: list[GuestHarmonizationOutput] = Field(default_factory=list)
    status: Literal["ready", "processing", "completed", "expired", "failed"]
    disclosure: str
    patient_voice: str | None = None
    audience: str | None = None
    progress: GuestHarmonizationProgress | None = None


class GuestHarmonizationDeleteResponse(BaseModel):
    deleted: bool
    run_id: str


class GuestHarmonizationContextRequest(BaseModel):
    patient_voice: str | None = None
    audience: Literal[
        "patient-summary", "clinician-handoff", "second-opinion", "preop-review", ""
    ] | None = None


# ---------------------------------------------------------------------------
# Harmonize endpoints (cross-source merge + Provenance)
# ---------------------------------------------------------------------------


class HarmonizeCollection(BaseModel):
    id: str
    name: str
    description: str
    source_count: int


class HarmonizeSource(BaseModel):
    id: str
    label: str
    kind: str  # "fhir-pull" | "extracted-pdf" | "ccda-xml"
    available: bool
    document_reference: str | None = None
    resource_counts: dict[str, int]
    total_resources: int
    status: Literal[
        "structured",
        "unparsed_structured",
        "pending_extraction",
        "extracted",
        "empty_extraction",
        "identity_mismatch",
        "missing",
    ] = "missing"
    status_label: str = ""


class HarmonizeCollectionsResponse(BaseModel):
    collections: list[HarmonizeCollection]


class HarmonizeSourceManifestResponse(BaseModel):
    collection_id: str
    sources: list[HarmonizeSource]


class HarmonizeObservationSource(BaseModel):
    source_label: str
    source_observation_ref: str
    value: float | None
    unit: str | None
    raw_value: float | None
    raw_unit: str | None
    effective_date: str | None
    document_reference: str | None
    reference_low: float | None = None
    reference_high: float | None = None
    reference_unit: str | None = None


class HarmonizeLatestObservation(BaseModel):
    value: float | None
    unit: str | None
    source_label: str
    effective_date: str | None


class HarmonizeMergedObservation(BaseModel):
    merged_ref: str | None
    canonical_name: str
    loinc_code: str | None
    canonical_unit: str | None
    source_count: int
    measurement_count: int
    has_conflict: bool
    latest: HarmonizeLatestObservation | None
    sources: list[HarmonizeObservationSource]


class HarmonizeObservationsResponse(BaseModel):
    collection_id: str
    total: int
    cross_source: int
    merged: list[HarmonizeMergedObservation]


class HarmonizeConditionSource(BaseModel):
    source_label: str
    source_condition_ref: str
    display: str
    snomed: str | None
    icd10: str | None
    icd9: str | None
    clinical_status: str | None
    onset_date: str | None
    document_reference: str | None


class HarmonizeMergedCondition(BaseModel):
    merged_ref: str | None
    canonical_name: str
    snomed: str | None
    icd10: str | None
    icd9: str | None
    is_active: bool
    source_count: int
    occurrence_count: int
    sources: list[HarmonizeConditionSource]


class HarmonizeConditionsResponse(BaseModel):
    collection_id: str
    total: int
    cross_source: int
    merged: list[HarmonizeMergedCondition]


class HarmonizeProvenanceResponse(BaseModel):
    """Pass-through of the FHIR Provenance dict — shape varies, so it's free-form."""

    collection_id: str
    merged_ref: str
    provenance: dict
    canonical_selection: dict[str, Any] | None = None


class HarmonizeExtractItem(BaseModel):
    source_id: str
    label: str
    extracted_path: str
    cache_hit: bool
    entry_count: int
    elapsed_seconds: float


class HarmonizeExtractJobEvent(BaseModel):
    event_id: str
    event_type: Literal[
        "job_queued",
        "file_queued",
        "job_started",
        "file_started",
        "file_completed",
        "job_completed",
        "job_failed",
    ]
    created_at: datetime
    stage: str
    message: str
    source_id: str | None = None
    source_label: str | None = None
    page_start: int | None = None
    page_end: int | None = None
    page_count: int | None = None
    processed_pages: int = 0
    total_pages: int | None = None
    processed_files: int = 0
    total_files: int = 0
    progress_basis: Literal["lifecycle", "metadata", "reported", "estimated"] = "lifecycle"
    is_estimate: bool = False


class HarmonizeExtractResponse(BaseModel):
    collection_id: str
    extracted: list[HarmonizeExtractItem]


class HarmonizeMedicationSource(BaseModel):
    source_label: str
    source_request_ref: str
    display: str
    rxnorm_codes: list[str]
    status: str | None
    authored_on: str | None
    document_reference: str | None


class HarmonizeMergedMedication(BaseModel):
    merged_ref: str | None
    canonical_name: str
    rxnorm_codes: list[str]
    is_active: bool
    source_count: int
    occurrence_count: int
    sources: list[HarmonizeMedicationSource]


class HarmonizeMedicationsResponse(BaseModel):
    collection_id: str
    total: int
    cross_source: int
    merged: list[HarmonizeMergedMedication]


class HarmonizeAllergySource(BaseModel):
    source_label: str
    source_allergy_ref: str
    display: str
    snomed: str | None
    rxnorm: str | None
    criticality: str | None
    clinical_status: str | None
    recorded_date: str | None
    document_reference: str | None


class HarmonizeMergedAllergy(BaseModel):
    merged_ref: str | None
    canonical_name: str
    snomed: str | None
    rxnorm: str | None
    is_active: bool
    highest_criticality: str | None
    source_count: int
    occurrence_count: int
    sources: list[HarmonizeAllergySource]


class HarmonizeAllergiesResponse(BaseModel):
    collection_id: str
    total: int
    cross_source: int
    merged: list[HarmonizeMergedAllergy]


class HarmonizeImmunizationSource(BaseModel):
    source_label: str
    source_immunization_ref: str
    display: str
    cvx: str | None
    ndc: str | None
    occurrence_date: str | None
    status: str | None
    document_reference: str | None


class HarmonizeMergedImmunization(BaseModel):
    merged_ref: str | None
    canonical_name: str
    cvx: str | None
    ndc: str | None
    occurrence_date: str | None
    source_count: int
    occurrence_count: int
    sources: list[HarmonizeImmunizationSource]


class HarmonizeImmunizationsResponse(BaseModel):
    collection_id: str
    total: int
    cross_source: int
    merged: list[HarmonizeMergedImmunization]


class HarmonizeContributionTotals(BaseModel):
    observations: int
    conditions: int
    medications: int
    allergies: int
    immunizations: int
    encounters: int = 0
    procedures: int = 0
    diagnostic_reports: int = 0
    clinical_notes: int = 0
    all: int


class HarmonizeClinicalNote(BaseModel):
    source_id: str
    source_label: str
    resource_type: str
    resource_id: str
    note_index: int
    encounter_id: str | None = None
    date: str | None = None
    author: str | None = None
    organization: str | None = None
    document_type: str | None = None
    category: str | None = None
    time: str | None = None
    section_title: str | None = None
    attachment_content_type: str | None = None
    text: str


class HarmonizeClinicalArtifact(BaseModel):
    source_id: str
    source_label: str
    id: str
    status: str = ""
    display: str = ""
    type: str = ""
    reason: str = ""
    category: str = ""
    class_code: str = ""
    period_start: str | None = None
    period_end: str | None = None
    performed_start: str | None = None
    performed_end: str | None = None
    effective_date: str | None = None
    encounter_id: str | None = None
    provider: str = ""
    site: str = ""
    service_provider: str = ""
    performer_labels: list[str] = Field(default_factory=list)
    performer_organization_labels: list[str] = Field(default_factory=list)
    performer_practitioner_labels: list[str] = Field(default_factory=list)
    specialty_labels: list[str] = Field(default_factory=list)
    result_refs: list[str] = Field(default_factory=list)
    has_presented_form: bool = False
    note_preview: str = ""


class HarmonizeContributionsResponse(BaseModel):
    """Reverse Provenance walk: what did this DocumentReference contribute?"""

    collection_id: str
    document_reference: str
    label: str | None
    kind: str | None
    observations: list[HarmonizeMergedObservation]
    conditions: list[HarmonizeMergedCondition]
    medications: list[HarmonizeMergedMedication]
    allergies: list[HarmonizeMergedAllergy]
    immunizations: list[HarmonizeMergedImmunization]
    encounters: list[HarmonizeClinicalArtifact] = Field(default_factory=list)
    procedures: list[HarmonizeClinicalArtifact] = Field(default_factory=list)
    diagnostic_reports: list[HarmonizeClinicalArtifact] = Field(default_factory=list)
    clinical_notes: list[HarmonizeClinicalNote] = Field(default_factory=list)
    totals: HarmonizeContributionTotals


class HarmonizeSourceDiffSourceTotals(BaseModel):
    unique: HarmonizeContributionTotals
    shared: HarmonizeContributionTotals


class HarmonizeSourceDiffUniqueFacts(BaseModel):
    observations: list[HarmonizeMergedObservation]
    conditions: list[HarmonizeMergedCondition]
    medications: list[HarmonizeMergedMedication]
    allergies: list[HarmonizeMergedAllergy]
    immunizations: list[HarmonizeMergedImmunization]


class HarmonizeSourceDiffSource(BaseModel):
    id: str
    label: str
    kind: str
    document_reference: str | None
    totals: HarmonizeSourceDiffSourceTotals
    unique_facts: HarmonizeSourceDiffUniqueFacts


class HarmonizeSourceDiffResponse(BaseModel):
    collection_id: str
    sources: list[HarmonizeSourceDiffSource]


class HarmonizeExtractJobResponse(BaseModel):
    job_id: str
    collection_id: str
    status: Literal["pending", "running", "complete", "failed"]
    results: list[HarmonizeExtractItem]
    error: str | None
    started_at: datetime
    completed_at: datetime | None
    progress_percent: int = 0
    stage: str = "Queued"
    detail: str | None = None
    total_files: int = 0
    processed_files: int = 0
    total_pages: int | None = None
    processed_pages: int = 0
    estimated_processed_pages: int = 0
    current_source_label: str | None = None
    estimated_seconds: int | None = None
    progress_mode: Literal["reported", "estimated", "lifecycle"] = "lifecycle"
    events: list[HarmonizeExtractJobEvent] = Field(default_factory=list)


class HarmonizeRunFactCounts(BaseModel):
    observations: int = 0
    conditions: int = 0
    medications: int = 0
    allergies: int = 0
    immunizations: int = 0
    procedures: int = 0
    diagnostic_reports: int = 0
    clinical_documents: int = 0
    clinical_notes: int = 0


class HarmonizeRunSummary(BaseModel):
    source_count: int
    prepared_source_count: int
    needs_preparation_count: int
    candidate_counts: HarmonizeRunFactCounts
    cross_source_counts: HarmonizeRunFactCounts
    total_candidate_facts: int
    cross_source_facts: int
    conflict_count: int
    review_item_count: int
    publishable: bool


class HarmonizeRunSource(BaseModel):
    id: str
    label: str
    kind: str
    document_reference: str | None = None
    path: str
    exists: bool
    size_bytes: int | None = None
    modified_at: str | None = None
    sha256: str | None = None
    status: str
    status_label: str
    total_resources: int
    resource_counts: dict[str, int] = Field(default_factory=dict)


class HarmonizeRunReviewItem(BaseModel):
    id: str
    category: str
    severity: Literal["low", "medium", "high"]
    title: str
    body: str
    source_id: str | None = None
    resource_type: str | None = None
    merged_ref: str | None = None
    resolved: bool = False
    decision: str | None = None
    decision_notes: str = ""
    selected_source_ref: str | None = None
    resolved_at: datetime | None = None


class HarmonizeReviewEvent(BaseModel):
    event_id: str
    event_type: Literal["review_decision"] = "review_decision"
    collection_id: str | None = None
    run_id: str | None = None
    item_id: str
    category: str | None = None
    severity: str | None = None
    source_id: str | None = None
    resource_type: str | None = None
    merged_ref: str | None = None
    decision: str
    notes: str = ""
    selected_source_ref: str | None = None
    resolved: bool = False
    resolved_at: datetime | None = None
    created_at: datetime
    actor: str = "local-reviewer"
    previous_decision: str | None = None
    previous_resolved: bool = False
    previous_selected_source_ref: str | None = None


class HarmonizeReviewDecisionSummary(BaseModel):
    event_count: int = 0
    resolved_item_count: int = 0
    open_item_count: int = 0
    latest_event_at: datetime | None = None
    decisions: dict[str, int] = Field(default_factory=dict)


class HarmonizeReviewDecisionRequest(BaseModel):
    item_id: str
    decision: Literal[
        "accepted",
        "dismissed",
        "source_fixed",
        "overridden",
        "kept_separate",
        "deferred",
    ]
    notes: str = ""
    selected_source_ref: str | None = None


class HarmonizeRunResponse(BaseModel):
    run_id: str
    collection_id: str
    collection_name: str
    status: Literal["complete", "failed"]
    rule_version: str
    started_at: datetime
    completed_at: datetime
    duration_seconds: float
    sources: list[HarmonizeRunSource]
    summary: HarmonizeRunSummary
    review_items: list[HarmonizeRunReviewItem]
    review_events: list[HarmonizeReviewEvent] = Field(default_factory=list)
    review_decision_summary: HarmonizeReviewDecisionSummary = Field(
        default_factory=HarmonizeReviewDecisionSummary
    )
    artifact_path: str


class HarmonizeRunStateResponse(BaseModel):
    collection_id: str
    latest_run: HarmonizeRunResponse | None = None


class PublishedChartChangeSummary(BaseModel):
    previous_snapshot_id: str | None = None
    previous_run_id: str | None = None
    fact_delta: int = 0
    source_delta: int = 0
    review_item_delta: int = 0
    candidate_count_delta: HarmonizeRunFactCounts = Field(default_factory=HarmonizeRunFactCounts)
    headline: str = "Initial published chart snapshot."


class PublishedChartSnapshot(BaseModel):
    snapshot_id: str
    collection_id: str
    run_id: str
    collection_name: str
    published_at: datetime
    run_completed_at: datetime
    rule_version: str
    artifact_path: str
    summary: HarmonizeRunSummary
    source_count: int
    candidate_fact_count: int
    review_item_count: int
    review_decision_summary: HarmonizeReviewDecisionSummary = Field(
        default_factory=HarmonizeReviewDecisionSummary
    )
    activated_at: datetime | None = None
    activated_from_snapshot_id: str | None = None
    change_summary: PublishedChartChangeSummary = Field(default_factory=PublishedChartChangeSummary)
    is_active: bool = False


class PublishedChartStateResponse(BaseModel):
    collection_id: str
    active_snapshot: PublishedChartSnapshot | None = None
    snapshots: list[PublishedChartSnapshot] = Field(default_factory=list)
