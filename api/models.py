"""
Pydantic response models for the EHI Ignite API.

These are the shapes returned to the React frontend. They are derived from
the Python dataclasses in fhir_explorer/parser/models.py and
fhir_explorer/catalog/single_patient.py but are separate to keep the API
contract stable independent of internal parsing model changes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Patient list
# ---------------------------------------------------------------------------

class PatientListItem(BaseModel):
    id: str
    name: str
    age_years: float
    gender: str
    complexity_tier: str
    complexity_score: float
    total_resources: int
    encounter_count: int
    active_condition_count: int
    active_med_count: int


# ---------------------------------------------------------------------------
# Overview detail
# ---------------------------------------------------------------------------

class ConditionRow(BaseModel):
    condition_id: str
    display: str
    clinical_status: str
    is_active: bool
    onset_dt: datetime | None
    abatement_dt: datetime | None


class MedRow(BaseModel):
    med_id: str
    display: str
    status: str
    authored_on: datetime | None
    is_active: bool


class ResourceTypeCount(BaseModel):
    resource_type: str
    count: int
    category: str  # "Clinical" | "Billing" | "Administrative"


class EncounterTypeSummary(BaseModel):
    encounter_type: str
    count: int


class CareTeamSummaryItem(BaseModel):
    name: str
    organizations: list[str]
    encounter_count: int
    latest_encounter_dt: datetime | None
    class_breakdown: dict[str, int]


class SiteOfServiceSummaryItem(BaseModel):
    name: str
    provider_count: int
    encounter_count: int
    latest_encounter_dt: datetime | None
    class_breakdown: dict[str, int]


class PatientOverview(BaseModel):
    # Identity
    id: str
    name: str

    # Demographics
    age_years: float
    gender: str
    birth_date: str | None
    is_deceased: bool
    race: str
    ethnicity: str
    city: str
    state: str
    language: str
    marital_status: str
    daly: float | None
    qaly: float | None

    # Data span
    earliest_encounter_dt: datetime | None
    latest_encounter_dt: datetime | None
    years_of_history: float

    # Resource summary
    total_resources: int
    clinical_resource_count: int
    billing_resource_count: int
    billing_pct: float
    resource_type_counts: list[ResourceTypeCount]

    # Complexity
    complexity_score: float
    complexity_tier: str

    # Conditions
    active_condition_count: int
    resolved_condition_count: int
    conditions: list[ConditionRow]

    # Medications
    active_med_count: int
    total_med_count: int
    medications: list[MedRow]

    # Observations
    unique_loinc_count: int
    obs_category_breakdown: dict[str, int]

    # Encounters
    encounter_count: int
    encounter_class_breakdown: dict[str, int]
    encounter_type_breakdown: list[EncounterTypeSummary]
    avg_resources_per_encounter: float
    care_team: list[CareTeamSummaryItem]
    sites_of_service: list[SiteOfServiceSummaryItem]

    # Allergies
    allergy_count: int
    allergy_labels: list[str]
    allergies: list["AllergyRow"] = []

    # Immunizations
    immunization_count: int
    unique_vaccines: list[str]

    # Parse quality
    parse_warning_count: int


# ---------------------------------------------------------------------------
# Timeline (encounters)
# ---------------------------------------------------------------------------

class EncounterEvent(BaseModel):
    encounter_id: str
    class_code: str
    encounter_type: str
    reason_display: str
    start: datetime | None
    end: datetime | None
    provider_org: str
    practitioner_name: str
    linked_observation_count: int
    linked_condition_count: int
    linked_procedure_count: int
    linked_medication_count: int


class TimelineResponse(BaseModel):
    patient_id: str
    name: str
    encounters: list[EncounterEvent]
    year_counts: dict[str, int]  # str key for JSON safety


# ---------------------------------------------------------------------------
# Encounter detail (for preview pane)
# ---------------------------------------------------------------------------

class ObservationDetail(BaseModel):
    obs_id: str
    category: str
    display: str
    loinc_code: str
    effective_dt: datetime | None
    value_type: str
    value_quantity: float | None
    value_unit: str
    value_concept_display: str | None


class ConditionDetail(BaseModel):
    condition_id: str
    display: str
    clinical_status: str
    is_active: bool
    onset_dt: datetime | None


class ProcedureDetail(BaseModel):
    procedure_id: str
    display: str
    status: str
    performed_start: datetime | None
    reason_display: str


class MedicationDetail(BaseModel):
    med_id: str
    display: str
    status: str
    authored_on: datetime | None
    dosage_text: str
    reason_display: str


class EncounterDetail(BaseModel):
    encounter_id: str
    class_code: str
    encounter_type: str
    reason_display: str
    start: datetime | None
    end: datetime | None
    duration_hours: float | None
    provider_org: str
    practitioner_name: str
    # Linked resources
    observations: list[ObservationDetail]
    conditions: list[ConditionDetail]
    procedures: list[ProcedureDetail]
    medications: list[MedicationDetail]
    diagnostic_report_count: int
    imaging_study_count: int


# ---------------------------------------------------------------------------
# Key Labs Panel
# ---------------------------------------------------------------------------

class LabHistoryPoint(BaseModel):
    effective_dt: datetime | None
    value: float


class LabValue(BaseModel):
    loinc_code: str
    display: str
    value: float | None
    unit: str
    effective_dt: datetime | None
    # trend: compare last 2 readings — "up", "down", "stable", or None
    trend: str | None
    # reference range flag if value is present
    is_abnormal: bool | None  # None = unknown (no reference range data)
    # historical readings for sparkline (oldest first, up to 10)
    history: list[LabHistoryPoint]


class LabAlertFlag(BaseModel):
    lab_name: str          # e.g. "Hemoglobin"
    loinc_code: str        # e.g. "718-7"
    value: float
    unit: str
    severity: str          # "critical" | "warning"
    direction: str         # "high" | "low" | "trending_up" | "trending_down"
    message: str           # e.g. "Hemoglobin 7.2 g/dL — critically low"
    days_ago: int          # how many days since this observation


class TimelineEvent(BaseModel):
    loinc_code: str
    display_name: str
    value: float
    unit: str
    date: str           # ISO date string "YYYY-MM-DD"
    change_direction: str  # "up" | "down" | "stable"


class TimelineMonth(BaseModel):
    month: str          # "2026-03"
    label: str          # "Mar 2026"
    events: list[TimelineEvent]


class KeyLabsResponse(BaseModel):
    patient_id: str
    panels: dict[str, list[LabValue]]  # panel name → list of labs
    alert_flags: list[LabAlertFlag] = []
    timeline_events: list[TimelineMonth] = []


# ---------------------------------------------------------------------------
# Safety flags (pre-op drug classification)
# ---------------------------------------------------------------------------

class SafetyMedication(BaseModel):
    med_id: str
    display: str
    status: str        # "active" | "stopped" | etc.
    authored_on: datetime | None
    is_active: bool


class SafetyFlag(BaseModel):
    class_key: str
    label: str
    severity: str      # "critical" | "warning" | "info"
    surgical_note: str
    status: str        # "ACTIVE" | "HISTORICAL" | "NONE"
    medications: list[SafetyMedication]
    protocol_note: str | None = None


class SafetyResponse(BaseModel):
    patient_id: str
    name: str
    flags: list[SafetyFlag]          # sorted: critical first, ACTIVE first
    active_flag_count: int
    historical_flag_count: int


# ---------------------------------------------------------------------------
# Surgical Risk Score (deterministic pre-op clearance method)
# ---------------------------------------------------------------------------

class SurgicalRiskComponent(BaseModel):
    key: str
    label: str
    score: int
    max_score: int
    status: str       # "CLEARED" | "REVIEW" | "FLAGGED"
    rationale: str
    evidence: list[str]


class SurgicalRiskResponse(BaseModel):
    patient_id: str
    name: str
    score: int
    max_score: int
    tier: str         # "LOW" | "MODERATE" | "HIGH"
    disposition: str  # "CLEARED" | "REVIEW" | "HOLD"
    rule_version: str
    components: list[SurgicalRiskComponent]
    methodology_notes: list[str]


# ---------------------------------------------------------------------------
# Immunizations
# ---------------------------------------------------------------------------

class ImmunizationItem(BaseModel):
    imm_id: str
    display: str
    cvx_code: str
    status: str
    occurrence_dt: datetime | None


class ImmunizationResponse(BaseModel):
    patient_id: str
    name: str
    total_count: int
    immunizations: list[ImmunizationItem]  # sorted by occurrence_dt descending
    unique_vaccines: list[str]             # deduplicated display names


# ---------------------------------------------------------------------------
# Condition Acuity (surgical risk ranking)
# ---------------------------------------------------------------------------

class RankedConditionItem(BaseModel):
    condition_id: str
    display: str
    clinical_status: str
    onset_dt: datetime | None
    risk_category: str
    risk_rank: int
    risk_label: str
    is_active: bool


class ConditionAcuityResponse(BaseModel):
    patient_id: str
    name: str
    active_count: int
    resolved_count: int
    ranked_active: list[RankedConditionItem]    # active conditions, ranked
    ranked_resolved: list[RankedConditionItem]  # resolved, ranked (for context)


# ---------------------------------------------------------------------------
# Procedures
# ---------------------------------------------------------------------------

class ProcedureItem(BaseModel):
    procedure_id: str
    display: str
    status: str
    performed_start: datetime | None
    performed_end: datetime | None
    reason_display: str
    body_site: str  # always "" — ProcedureRecord has no body_site field


class ProceduresResponse(BaseModel):
    patient_id: str
    name: str
    total_count: int
    procedures: list[ProcedureItem]  # sorted by performed_start descending, nulls last


# ---------------------------------------------------------------------------
# Corpus Stats
# ---------------------------------------------------------------------------

class CorpusStats(BaseModel):
    total_patients: int
    gender_breakdown: dict[str, int]
    complexity_tier_breakdown: dict[str, int]
    avg_age: float
    avg_encounter_count: float
    avg_active_condition_count: float
    avg_active_med_count: float
    total_encounters: int
    total_resources: int


# ---------------------------------------------------------------------------
# Patient Risk Summary (sidebar filter)
# ---------------------------------------------------------------------------

class PatientRiskSummary(BaseModel):
    id: str
    name: str
    complexity_tier: str          # "simple" | "moderate" | "complex" | "highly_complex"
    has_critical_flag: bool       # True if any ACTIVE critical-severity drug class
    active_critical_classes: list[str]  # e.g. ["anticoagulants", "antiplatelets"]


class PatientRiskSummaryResponse(BaseModel):
    patients: list[PatientRiskSummary]


# ---------------------------------------------------------------------------
# Observation Distributions (corpus-level lab value distributions)
# ---------------------------------------------------------------------------

class ObservationDistribution(BaseModel):
    loinc_code: str
    display_name: str
    unit: str
    count: int
    patient_count: int
    min: float
    max: float
    mean: float
    median: float
    p10: float
    p25: float
    p75: float
    p90: float
    histogram: list[int]
    bucket_labels: list[str]


class ObservationDistributionsResponse(BaseModel):
    distributions: list[ObservationDistribution]
    total_loinc_codes_found: int
    loinc_codes_shown: int


# ---------------------------------------------------------------------------
# Drug-Drug Interactions
# ---------------------------------------------------------------------------

class InteractionResult(BaseModel):
    drug_a: str
    drug_a_label: str       # human-readable label e.g. "Anticoagulants"
    drug_b: str
    drug_b_label: str
    severity: str           # "contraindicated" | "major" | "moderate"
    mechanism: str
    clinical_effect: str
    management: str
    drug_a_meds: list[str]  # actual med names from patient's record
    drug_b_meds: list[str]


class InteractionResponse(BaseModel):
    patient_id: str
    active_class_keys: list[str]
    interactions: list[InteractionResult]
    contraindicated_count: int
    major_count: int
    moderate_count: int
    has_interactions: bool


# ---------------------------------------------------------------------------
# Allergy Criticality Breakdown (corpus-level)
# ---------------------------------------------------------------------------

class AllergySubstanceEntry(BaseModel):
    substance: str
    count: int
    criticality: str  # most severe criticality seen for this substance


class AllergyCriticalityBreakdown(BaseModel):
    criticality_counts: dict[str, int]    # {"high": 45, "low": 120, ...}
    category_counts: dict[str, int]       # {"medication": 234, "food": 45, ...}
    total_allergy_records: int
    patients_with_allergies: int
    patients_with_high_criticality: int   # at least one "high" allergy
    top_substances: list[AllergySubstanceEntry]  # top 10 by count


# ---------------------------------------------------------------------------
# Allergy detail (per-patient overview enhancement)
# ---------------------------------------------------------------------------

class AllergyRow(BaseModel):
    substance: str
    criticality: str | None   # "high" | "low" | "unable-to-assess" | None
    category: list[str]       # ["medication"] | ["food"] | [] etc.
    reactions: list[str]      # empty — AllergyRecord has no reaction field
    severity: str | None      # not available in AllergyRecord — always None


# ---------------------------------------------------------------------------
# Field Coverage Profiler
# ---------------------------------------------------------------------------

class FieldCoverageItem(BaseModel):
    field_path: str          # e.g. "patient.birth_date", "condition.onset_dt"
    resource_type: str       # e.g. "Patient", "Condition"
    present_count: int       # how many patients have this field non-null/non-empty
    total_count: int         # total patients checked
    coverage_pct: float      # present_count / total_count * 100
    coverage_label: str      # "Always" (>=95%), "Usually" (70-94%), "Sometimes" (30-69%), "Rarely" (<30%)


class FieldCoverageResponse(BaseModel):
    total_patients: int
    fields: list[FieldCoverageItem]  # sorted by resource_type, then coverage_pct descending


# ---------------------------------------------------------------------------
# Provider Assistant (chat)
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Care Journey (multi-lane Gantt timeline)
# ---------------------------------------------------------------------------

class MedicationEpisodeItem(BaseModel):
    episode_id: str
    display: str
    drug_class: str | None
    status: str
    is_active: bool
    start_date: str | None
    end_date: str | None
    duration_days: float | None
    request_count: int
    reason: str | None = None      # resolved from reasonReference → Condition


class ConditionEpisodeItem(BaseModel):
    condition_id: str
    display: str
    clinical_status: str
    onset_date: str | None
    end_date: str | None       # recorded_date for resolved; None for active
    is_active: bool


class EncounterMarker(BaseModel):
    encounter_id: str
    class_code: str
    type_text: str
    start: str | None
    reason_display: str
    diagnoses: list[str] = []       # linked condition display names


class ProcedureMarker(BaseModel):
    procedure_id: str
    display: str
    start: str | None
    end: str | None
    reason_display: str            # from reasonReference → Condition display


class DiagnosticReportItem(BaseModel):
    report_id: str
    display: str
    category: str
    date: str | None
    result_count: int


class CareJourneyResponse(BaseModel):
    patient_id: str
    name: str
    earliest_date: str | None
    latest_date: str | None
    medication_episodes: list[MedicationEpisodeItem]
    conditions: list[ConditionEpisodeItem]
    encounters: list[EncounterMarker]
    procedures: list[ProcedureMarker]
    diagnostic_reports: list[DiagnosticReportItem]
    drug_classes_present: list[str]


class ProviderAssistantTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)

    @field_validator("content")
    @classmethod
    def _content_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("content is required")
        return stripped


class ProviderAssistantCitation(BaseModel):
    source_type: str      # "MedicationRequest" | "Condition" | ...
    resource_id: str
    label: str
    detail: str
    event_date: datetime | None = None


class ProviderAssistantContextPackage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str = Field(min_length=1, max_length=80)
    title: str = Field(min_length=1, max_length=120)
    type: str = Field(min_length=1, max_length=80)
    summary: str = Field(min_length=1, max_length=500)
    instructions: str = Field(min_length=1, max_length=1500)


class ProviderAssistantRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=200)
    question: str = Field(min_length=1, max_length=4000)
    history: list[ProviderAssistantTurn] = Field(default_factory=list, max_length=12)
    context_packages: list[ProviderAssistantContextPackage] = Field(default_factory=list, max_length=8)
    stance: Literal["opinionated", "balanced"] = "opinionated"
    # Per-request overrides (optional — falls back to env config)
    model: Literal[
        "claude-haiku-4-5",
        "claude-sonnet-4-5",
        "claude-sonnet-4-6",
        "claude-opus-4-5",
    ] | None = None
    mode: Literal[
        "deterministic",
        "context",
        "context_single_turn",
        "single_turn",
        "anthropic",
        "anthropic_agent",
        "agent_sdk",
        "anthropic_sdk",
        "cursor",
        "cursor_sdk",
    ] | None = None
    max_tokens: int | None = Field(default=None, ge=128, le=4000)
    # Cursor sidecar model id (e.g. composer-2). Validated against CURSOR_SIDECAR_MODEL_ALLOWLIST when set.
    cursor_model: str | None = Field(default=None, max_length=120)

    @field_validator("cursor_model", mode="before")
    @classmethod
    def _normalize_cursor_model(cls, value: object) -> str | None:
        if value is None:
            return None
        s = str(value).strip()
        return s or None

    @field_validator("question")
    @classmethod
    def _question_not_blank(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("question is required")
        return stripped


class ToolCallDetail(BaseModel):
    tool_name: str                 # "run_sql" | "query_chart_evidence" | "get_patient_snapshot"
    input_summary: str             # human-readable input (e.g. the SQL query)
    output_summary: str            # human-readable output (e.g. "12 rows returned")
    duration_ms: float | None = None
    error: str | None = None


class TraceDetail(BaseModel):
    trace_id: str
    duration_ms: float | None = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_cost_usd: float | None = None
    tool_calls: list[ToolCallDetail] = []
    system_prompt_preview: str = ""   # system prompt the agent received
    retrieved_facts: list[str] = []   # actual fact texts used in the response
    # Transparency metadata
    model_used: str | None = None
    mode_used: str | None = None
    max_tokens_used: int | None = None
    context_token_estimate: int | None = None
    history_turns_sent: int | None = None


class ProviderAssistantResponse(BaseModel):
    patient_id: str
    answer: str
    confidence: str                # "high" | "medium" | "low"
    stance: str
    engine: str = "deterministic"  # "deterministic" | "anthropic-agent-sdk" | "deterministic-fallback"
    citations: list[ProviderAssistantCitation]
    follow_ups: list[str]
    trace: TraceDetail | None = None  # tool calls + context transparency


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
    kind: str  # "fhir-pull" | "extracted-pdf"
    available: bool
    document_reference: str | None = None
    resource_counts: dict[str, int]
    total_resources: int


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


class HarmonizeExtractItem(BaseModel):
    source_id: str
    label: str
    extracted_path: str
    cache_hit: bool
    entry_count: int
    elapsed_seconds: float


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
    all: int


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
    totals: HarmonizeContributionTotals
