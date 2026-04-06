"""
Pydantic response models for the EHI Ignite API.

These are the shapes returned to the React frontend. They are derived from
the Python dataclasses in fhir_explorer/parser/models.py and
fhir_explorer/catalog/single_patient.py but are separate to keep the API
contract stable independent of internal parsing model changes.
"""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


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


class KeyLabsResponse(BaseModel):
    patient_id: str
    panels: dict[str, list[LabValue]]  # panel name → list of labs


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
