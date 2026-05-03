"""
Data models for parsed FHIR R4 patient bundles.

All models use stdlib dataclasses — no external dependencies.
These are the internal representations produced by bundle_parser.py
and consumed by the catalog and view layers.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

@dataclass
class CodeableConcept:
    """A coded clinical concept with a human-readable display."""
    system: str = ""
    code: str = ""
    display: str = ""
    text: str = ""  # .text on the parent CodeableConcept, often same as display

    def label(self) -> str:
        """Best human-readable label available."""
        return self.display or self.text or self.code or "Unknown"


@dataclass
class Period:
    start: datetime | None = None
    end: datetime | None = None

    def duration_days(self) -> float | None:
        if self.start and self.end:
            return (self.end - self.start).total_seconds() / 86400
        return None


# ---------------------------------------------------------------------------
# Patient demographics
# ---------------------------------------------------------------------------

@dataclass
class PatientSummary:
    patient_id: str = ""
    file_path: str = ""
    file_size_bytes: int = 0

    # Core demographics
    name: str = ""
    gender: str = ""
    birth_date: date | None = None
    deceased: bool = False
    deceased_date: date | None = None

    # Derived
    age_years: float = 0.0

    # US Core extensions
    race: str = ""
    ethnicity: str = ""
    birth_sex: str = ""
    birth_place: str = ""
    mothers_maiden_name: str = ""

    # Contact
    language: str = ""
    marital_status: str = ""
    phone: str = ""

    # Address
    city: str = ""
    state: str = ""
    country: str = ""
    postal_code: str = ""
    lat: float | None = None
    lon: float | None = None

    # Synthea-specific extensions
    daly: float | None = None   # Disability-Adjusted Life Years
    qaly: float | None = None   # Quality-Adjusted Life Years

    # Identifiers
    mrn: str = ""
    ssn: str = ""


# ---------------------------------------------------------------------------
# Clinical resources
# ---------------------------------------------------------------------------

@dataclass
class ObservationComponent:
    """Sub-observation within a component observation (e.g., blood pressure)."""
    loinc_code: str = ""
    display: str = ""
    value: float | None = None
    unit: str = ""
    value_concept_display: str | None = None  # for coded component values


@dataclass
class ObservationRecord:
    obs_id: str = ""
    patient_id: str = ""
    encounter_id: str | None = None
    status: str = ""

    # Category: "vital-signs", "laboratory", "survey", "social-history", etc.
    category: str = ""

    # Code
    loinc_code: str = ""
    display: str = ""

    effective_dt: datetime | None = None

    # Value — exactly one of these will be populated
    value_type: str = ""  # "quantity" | "codeable_concept" | "component" | "none"
    value_quantity: float | None = None
    value_unit: str = ""
    value_concept_display: str | None = None
    components: list[ObservationComponent] = field(default_factory=list)


@dataclass
class EncounterRecord:
    encounter_id: str = ""
    patient_id: str = ""
    status: str = ""

    # "AMB" (ambulatory), "IMP" (inpatient), "EMER" (emergency), etc.
    class_code: str = ""

    # Human-readable encounter type
    encounter_type: str = ""
    reason_display: str = ""

    period: Period = field(default_factory=Period)

    # Provider info
    provider_org: str = ""
    practitioner_name: str = ""

    # Populated during post-processing by bundle_parser
    linked_observations: list[str] = field(default_factory=list)
    linked_conditions: list[str] = field(default_factory=list)
    linked_procedures: list[str] = field(default_factory=list)
    linked_medications: list[str] = field(default_factory=list)
    linked_diagnostic_reports: list[str] = field(default_factory=list)
    linked_immunizations: list[str] = field(default_factory=list)
    linked_imaging_studies: list[str] = field(default_factory=list)


@dataclass
class ConditionRecord:
    condition_id: str = ""
    patient_id: str = ""
    encounter_id: str | None = None

    clinical_status: str = ""       # active, resolved, inactive, remission
    verification_status: str = ""   # confirmed, unconfirmed, refuted

    code: CodeableConcept = field(default_factory=CodeableConcept)

    onset_dt: datetime | None = None
    abatement_dt: datetime | None = None
    recorded_dt: datetime | None = None

    # Derived: clinicalStatus == "active" AND no abatementDateTime
    is_active: bool = False


@dataclass
class MedicationRecord:
    med_id: str = ""
    patient_id: str = ""
    encounter_id: str | None = None

    status: str = ""    # active, stopped, completed, cancelled, on-hold

    rxnorm_code: str = ""
    display: str = ""

    authored_on: datetime | None = None
    requester: str = ""

    as_needed: bool = False
    dosage_text: str = ""
    reason_display: str = ""


@dataclass
class ProcedureRecord:
    procedure_id: str = ""
    patient_id: str = ""
    encounter_id: str | None = None

    status: str = ""
    code: CodeableConcept = field(default_factory=CodeableConcept)
    performed_period: Period | None = None
    reason_display: str = ""


@dataclass
class DiagnosticReportRecord:
    report_id: str = ""
    patient_id: str = ""
    encounter_id: str | None = None

    category: str = ""
    code: CodeableConcept = field(default_factory=CodeableConcept)
    status: str = ""

    effective_dt: datetime | None = None

    # UUIDs of Observation resources this report groups
    result_refs: list[str] = field(default_factory=list)

    # Base64 clinical note (absent in Synthea, present in real EHR exports)
    has_presented_form: bool = False
    presented_form_text: str = ""


@dataclass
class ImmunizationRecord:
    imm_id: str = ""
    patient_id: str = ""
    encounter_id: str | None = None

    status: str = ""

    cvx_code: str = ""
    display: str = ""

    occurrence_dt: datetime | None = None


@dataclass
class AllergyRecord:
    allergy_id: str = ""
    patient_id: str = ""

    clinical_status: str = ""
    allergy_type: str = ""
    categories: list[str] = field(default_factory=list)
    criticality: str = ""

    code: CodeableConcept = field(default_factory=CodeableConcept)

    onset_dt: datetime | None = None
    recorded_date: datetime | None = None


@dataclass
class ClaimRecord:
    claim_id: str = ""
    patient_id: str = ""
    encounter_id: str | None = None

    insurer: str = ""
    billable_period: Period = field(default_factory=Period)

    total_billed: float | None = None
    total_paid: float | None = None

    claim_type: str = ""


@dataclass
class ImagingStudyRecord:
    study_id: str = ""
    patient_id: str = ""
    encounter_id: str | None = None

    status: str = ""
    started: datetime | None = None
    modality: str = ""
    description: str = ""
    series_count: int = 0
    instance_count: int = 0


# ---------------------------------------------------------------------------
# Top-level container
# ---------------------------------------------------------------------------

@dataclass
class PatientRecord:
    """
    Complete parsed representation of a single patient FHIR bundle.
    Produced by bundle_parser.parse_bundle() and consumed by all
    catalog and view modules.
    """

    summary: PatientSummary = field(default_factory=PatientSummary)

    encounters: list[EncounterRecord] = field(default_factory=list)
    observations: list[ObservationRecord] = field(default_factory=list)
    conditions: list[ConditionRecord] = field(default_factory=list)
    medications: list[MedicationRecord] = field(default_factory=list)
    procedures: list[ProcedureRecord] = field(default_factory=list)
    diagnostic_reports: list[DiagnosticReportRecord] = field(default_factory=list)
    immunizations: list[ImmunizationRecord] = field(default_factory=list)
    allergies: list[AllergyRecord] = field(default_factory=list)
    claims: list[ClaimRecord] = field(default_factory=list)
    imaging_studies: list[ImagingStudyRecord] = field(default_factory=list)

    # Lower-priority resources kept as raw dicts
    care_plans_raw: list[dict] = field(default_factory=list)
    care_teams_raw: list[dict] = field(default_factory=list)
    goals_raw: list[dict] = field(default_factory=list)
    devices_raw: list[dict] = field(default_factory=list)

    # --- Index structures built during parsing ---

    # encounter_id -> EncounterRecord
    encounter_index: dict[str, EncounterRecord] = field(default_factory=dict)

    # encounter_id -> list of obs_ids
    obs_by_encounter: dict[str, list[str]] = field(default_factory=dict)

    # loinc_code -> list of obs_ids (for trend queries)
    obs_by_loinc: dict[str, list[str]] = field(default_factory=dict)

    # obs_id -> ObservationRecord
    obs_index: dict[str, ObservationRecord] = field(default_factory=dict)

    # Raw counts straight from the bundle
    resource_type_counts: dict[str, int] = field(default_factory=dict)

    # Any issues encountered during parsing
    parse_warnings: list[str] = field(default_factory=list)
