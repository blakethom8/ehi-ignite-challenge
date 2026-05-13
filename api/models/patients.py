"""
Patient-facing response models — list, overview, timeline, encounter detail,
key labs, safety, surgical risk, immunizations, conditions, procedures,
risk summary, drug-drug interactions, allergies, and the care-journey
multi-lane Gantt timeline.

These models cover the response shapes for `api/routers/patients_core.py`,
`api/routers/patients_timeline.py`, `api/routers/patients_risk.py`, and the
care-journey endpoints in `api/routers/patients.py`. They live together
because they share dense forward references (PatientOverview ↔ AllergyRow,
EncounterDetail ↔ ClinicalNoteItem, CareJourneyResponse ↔ ClinicalNoteItem)
that would force model_rebuild() gymnastics if split across modules.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

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
    workspace_type: Literal["synthea", "upload", "profile", "demo"] = "synthea"
    source_count: int = 0
    prepared_source_count: int = 0


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
# Allergy detail (per-patient overview enhancement)
# ---------------------------------------------------------------------------

class AllergyRow(BaseModel):
    substance: str
    criticality: str | None   # "high" | "low" | "unable-to-assess" | None
    category: list[str]       # ["medication"] | ["food"] | [] etc.
    reactions: list[str]      # empty — AllergyRecord has no reaction field
    severity: str | None      # not available in AllergyRecord — always None


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
