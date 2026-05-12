"""
Pydantic response models for the EHI Ignite API.

These are the shapes returned to the React frontend. They are derived from
the Python dataclasses in fhir_explorer/parser/models.py and
fhir_explorer/catalog/single_patient.py but are separate to keep the API
contract stable independent of internal parsing model changes.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from typing_extensions import Annotated
from pydantic import Discriminator


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
    workspace_type: Literal["synthea", "upload", "profile", "demo"] = "synthea"
    source_count: int = 0
    prepared_source_count: int = 0


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
    specialty: str = ""
    organizations: list[str]
    encounter_count: int
    latest_encounter_dt: datetime | None
    class_breakdown: dict[str, int]


class SiteOfServiceSummaryItem(BaseModel):
    name: str
    specialty: str = ""
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
    specialty: str = ""
    source_category: str = ""
    provenance_label: str = ""
    linked_observation_count: int
    linked_condition_count: int
    linked_procedure_count: int
    linked_medication_count: int
    linked_clinical_note_count: int = 0


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
    specialty: str = ""
    source_category: str = ""
    provenance_label: str = ""
    # Linked resources
    observations: list[ObservationDetail]
    conditions: list[ConditionDetail]
    procedures: list[ProcedureDetail]
    medications: list[MedicationDetail]
    diagnostic_report_count: int
    imaging_study_count: int
    clinical_notes: list["ClinicalNoteItem"] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Key Labs Panel
# ---------------------------------------------------------------------------

class LabHistoryPoint(BaseModel):
    effective_dt: datetime | None
    value: float
    abnormality: Literal["low", "high", "normal", "unknown"] = "unknown"
    alert_severity: Literal["critical", "warning"] | None = None


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
    abnormality: Literal["low", "high", "normal", "unknown"] = "unknown"
    alert_severity: Literal["critical", "warning"] | None = None
    reference_low: float | None = None
    reference_high: float | None = None
    reference_unit: str = ""
    reference_range_label: str = ""
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
    has_presented_form: bool = False
    note_preview: str = ""


class ClinicalNoteItem(BaseModel):
    note_id: str
    source_id: str
    source_label: str
    resource_type: str
    resource_id: str
    note_index: int
    date: str | None = None
    author: str = ""
    organization: str = ""
    document_type: str = ""
    category: str = ""
    encounter_id: str | None = None
    linked_encounter_id: str | None = None
    linked_encounter_type: str = ""
    linked_encounter_start: str | None = None
    provider: str = ""
    site: str = ""
    section_title: str = ""
    attachment_content_type: str = ""
    preview: str = ""
    text: str = ""


class ClinicalNotesResponse(BaseModel):
    patient_id: str
    name: str
    total_count: int
    notes: list[ClinicalNoteItem] = Field(default_factory=list)


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
    clinical_notes: list[ClinicalNoteItem] = Field(default_factory=list)
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
    # Relative workspace paths the agent wrote during this turn (slice 3+4).
    # Frontend renders them as chips under the message.
    files_created: list[str] = Field(default_factory=list)


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


# ---------------------------------------------------------------------------
# Guest harmonization
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


class GuestHarmonizationRunResponse(BaseModel):
    run_id: str
    mode: Literal["guest"] = "guest"
    created_at: datetime
    expires_at: datetime
    uploaded_files: list[GuestHarmonizationUploadedFile] = Field(default_factory=list)
    outputs: list[GuestHarmonizationOutput] = Field(default_factory=list)
    status: Literal["ready", "processing", "completed", "expired", "failed"]
    disclosure: str


class GuestHarmonizationDeleteResponse(BaseModel):
    deleted: bool
    run_id: str


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


# ---------------------------------------------------------------------------
# Caspian workflow runs — pre-packaged review packets that produce a
# structured artifact rendered in the workbench rather than a chat reply.
# See data/workflows/*.json for the prompt packets that drive these.
# ---------------------------------------------------------------------------


class WorkflowBanner(BaseModel):
    """Disposition banner shown at the top of the artifact."""
    status: Literal[
        "clear",
        "review",
        "hold",
        "critical",
        "stable",
        "evolving",
        "deteriorating",
    ]
    label: str = Field(min_length=1, max_length=80)
    headline: str = Field(min_length=1, max_length=240)
    action_label: str | None = Field(default=None, max_length=40)


class WorkflowFactCell(BaseModel):
    label: str = Field(min_length=1, max_length=40)
    value: str = Field(min_length=1, max_length=80)
    tone: Literal["default", "tier", "caution"] = "default"


class WorkflowTableSection(BaseModel):
    kind: Literal["table"] = "table"
    title: str = Field(min_length=1, max_length=120)
    columns: list[str] = Field(min_length=1, max_length=8)
    # Each row is the same length as `columns`. Cells are strings; citation
    # IDs are encoded inline as `c_<id>` and the frontend renders them as
    # clickable chips that route to the inspector.
    rows: list[list[str]] = Field(default_factory=list)
    empty_note: str | None = Field(default=None, max_length=200)


class WorkflowNarrativeSection(BaseModel):
    kind: Literal["narrative"] = "narrative"
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(min_length=1, max_length=4000)


WorkflowSection = Annotated[
    WorkflowTableSection | WorkflowNarrativeSection,
    Discriminator("kind"),
]


class WorkflowArtifact(BaseModel):
    """The structured packet returned by a workflow run."""
    workflow_id: str = Field(min_length=1, max_length=80)
    workflow_title: str = Field(min_length=1, max_length=120)
    workflow_type: str = Field(min_length=1, max_length=80)
    artifact_id: str = Field(min_length=1, max_length=120)
    generated_at: datetime
    banner: WorkflowBanner
    fact_rail: list[WorkflowFactCell] = Field(default_factory=list, max_length=8)
    sections: list[WorkflowSection] = Field(default_factory=list, max_length=12)
    chat_narration: str = Field(min_length=1, max_length=400)
    # Set to the relative workspace path (e.g. "workflow-runs/2026-05-12-pre-op-…")
    # once the runner persists the artifact to the Caspian file workspace.
    file_path: str | None = Field(default=None, max_length=240)


class WorkflowRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=200)
    workflow_id: Literal[
        "preop_review_v1",
        "medication_safety_v1",
        "longitudinal_synthesis_v1",
    ]


class WorkflowRunResponse(BaseModel):
    patient_id: str
    artifact: WorkflowArtifact
    citations: list[ProviderAssistantCitation] = Field(default_factory=list)
    trace: TraceDetail | None = None


# ---------------------------------------------------------------------------
# Caspian file workspace — per-patient on-disk working directory.
# See api/core/caspian_workspace.py.
# ---------------------------------------------------------------------------


class CaspianFileListResponse(BaseModel):
    """Tree of files under (session, patient). Tree is freeform JSON because the
    server enforces the FileTreeNode shape; the frontend has its own typed union."""
    workspace_key: str
    tree: list[dict]


class CaspianFileReadResponse(BaseModel):
    path: str
    content: str
    mtime: datetime | None
    editable: bool
    kind: Literal["markdown", "json", "text"]


class CaspianFileWriteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    patient_id: str = Field(min_length=1, max_length=200)
    path: str = Field(min_length=1, max_length=200)
    content: str = Field(default="", max_length=200_000)


class CaspianFileWriteResponse(BaseModel):
    path: str
    bytes: int
    mtime: datetime
