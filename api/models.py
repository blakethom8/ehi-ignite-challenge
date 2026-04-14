"""
Pydantic response models for the EHI Ignite API.

These are the shapes returned to the React frontend. They are derived from
the Python dataclasses in fhir_explorer/parser/models.py and
fhir_explorer/catalog/single_patient.py but are separate to keep the API
contract stable independent of internal parsing model changes.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


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
    role: str    # "user" | "assistant"
    content: str


class ProviderAssistantCitation(BaseModel):
    source_type: str      # "MedicationRequest" | "Condition" | ...
    resource_id: str
    label: str
    detail: str
    event_date: datetime | None = None


class ProviderAssistantRequest(BaseModel):
    patient_id: str
    question: str
    history: list[ProviderAssistantTurn] = Field(default_factory=list)
    stance: str = "opinionated"    # "opinionated" | "balanced"


class ProviderAssistantResponse(BaseModel):
    patient_id: str
    answer: str
    confidence: str                # "high" | "medium" | "low"
    stance: str
    engine: str = "deterministic"  # "deterministic" | "anthropic-agent-sdk" | "deterministic-fallback"
    citations: list[ProviderAssistantCitation]
    follow_ups: list[str]
