"""
Single-patient statistics and catalog generation.

Entry point: compute_patient_stats(record) -> PatientStats
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from collections import defaultdict

from ..fhir_parser.models import PatientRecord, ObservationRecord


# ---------------------------------------------------------------------------
# Output models
# ---------------------------------------------------------------------------

@dataclass
class ConditionSummary:
    condition_id: str
    display: str
    clinical_status: str
    is_active: bool
    onset_dt: datetime | None
    abatement_dt: datetime | None


@dataclass
class MedSummary:
    med_id: str
    display: str
    status: str
    authored_on: datetime | None
    is_active: bool


@dataclass
class LOINCEntry:
    code: str
    display: str
    category: str
    count: int
    first_dt: datetime | None
    last_dt: datetime | None
    # For quantity observations
    min_value: float | None = None
    max_value: float | None = None
    last_value: float | None = None
    unit: str = ""
    # For coded observations
    value_counts: dict[str, int] = field(default_factory=dict)


@dataclass
class EncounterTypeSummary:
    encounter_type: str
    count: int


@dataclass
class PatientStats:
    # --- Demographics ---
    name: str
    age_years: float
    gender: str
    is_deceased: bool
    race: str
    city: str
    state: str

    # --- Data span ---
    earliest_encounter_dt: datetime | None
    latest_encounter_dt: datetime | None
    years_of_history: float

    # --- Resource summary ---
    resource_type_counts: dict[str, int]
    total_resources: int
    clinical_resource_count: int
    billing_resource_count: int
    billing_pct: float

    # --- Conditions ---
    active_condition_count: int
    resolved_condition_count: int
    condition_catalog: list[ConditionSummary]

    # --- Medications ---
    active_med_count: int
    total_med_count: int
    med_catalog: list[MedSummary]

    # --- Observations ---
    unique_loinc_count: int
    obs_category_breakdown: dict[str, int]
    loinc_catalog: list[LOINCEntry]

    # --- Encounters ---
    encounter_count: int
    encounter_class_breakdown: dict[str, int]
    encounter_type_breakdown: list[EncounterTypeSummary]
    avg_resources_per_encounter: float

    # --- Allergies ---
    allergy_count: int
    allergy_labels: list[str]

    # --- Immunizations ---
    immunization_count: int
    unique_vaccines: list[str]

    # --- Complexity ---
    complexity_score: float
    complexity_tier: str   # simple | moderate | complex | highly_complex

    # --- Parse quality ---
    parse_warning_count: int


# ---------------------------------------------------------------------------
# Main function
# ---------------------------------------------------------------------------

def compute_patient_stats(record: PatientRecord) -> PatientStats:
    s = record.summary

    # --- Data span ---
    encounter_dates = [
        enc.period.start
        for enc in record.encounters
        if enc.period.start is not None
    ]
    earliest_dt = min(encounter_dates) if encounter_dates else None
    latest_dt = max(encounter_dates) if encounter_dates else None
    years_of_history = 0.0
    if earliest_dt and latest_dt:
        years_of_history = (latest_dt - earliest_dt).days / 365.25

    # --- Resource counts ---
    total = sum(record.resource_type_counts.values())
    billing_types = {"Claim", "ExplanationOfBenefit"}
    admin_types = {"Organization", "Practitioner", "PractitionerRole", "Location"}
    billing_count = sum(
        count for rtype, count in record.resource_type_counts.items()
        if rtype in billing_types
    )
    admin_count = sum(
        count for rtype, count in record.resource_type_counts.items()
        if rtype in admin_types
    )
    clinical_count = total - billing_count - admin_count
    billing_pct = (billing_count / total * 100) if total > 0 else 0.0

    # --- Conditions ---
    active_conditions = [c for c in record.conditions if c.is_active]
    resolved_conditions = [c for c in record.conditions if not c.is_active]
    condition_catalog = [
        ConditionSummary(
            condition_id=c.condition_id,
            display=c.code.label(),
            clinical_status=c.clinical_status,
            is_active=c.is_active,
            onset_dt=c.onset_dt,
            abatement_dt=c.abatement_dt,
        )
        for c in sorted(record.conditions, key=lambda x: x.onset_dt or datetime.min.replace(tzinfo=timezone.utc))
    ]

    # --- Medications ---
    active_meds = [m for m in record.medications if m.status in ("active", "on-hold")]
    med_catalog = [
        MedSummary(
            med_id=m.med_id,
            display=m.display,
            status=m.status,
            authored_on=m.authored_on,
            is_active=m.status in ("active", "on-hold"),
        )
        for m in sorted(record.medications, key=lambda x: x.authored_on or datetime.min.replace(tzinfo=timezone.utc))
    ]

    # --- Observations ---
    obs_category_breakdown: dict[str, int] = defaultdict(int)
    loinc_map: dict[str, dict] = {}

    for obs in record.observations:
        cat = obs.category or "unknown"
        obs_category_breakdown[cat] += 1

        if obs.loinc_code:
            if obs.loinc_code not in loinc_map:
                loinc_map[obs.loinc_code] = {
                    "display": obs.display,
                    "category": obs.category,
                    "count": 0,
                    "first_dt": None,
                    "last_dt": None,
                    "values": [],
                    "unit": obs.value_unit or "",
                    "value_concepts": defaultdict(int),
                }
            entry = loinc_map[obs.loinc_code]
            entry["count"] += 1

            if obs.effective_dt:
                if entry["first_dt"] is None or obs.effective_dt < entry["first_dt"]:
                    entry["first_dt"] = obs.effective_dt
                if entry["last_dt"] is None or obs.effective_dt > entry["last_dt"]:
                    entry["last_dt"] = obs.effective_dt

            if obs.value_type == "quantity" and obs.value_quantity is not None:
                entry["values"].append((obs.effective_dt, obs.value_quantity))
                if not entry["unit"] and obs.value_unit:
                    entry["unit"] = obs.value_unit

            elif obs.value_type == "codeable_concept" and obs.value_concept_display:
                entry["value_concepts"][obs.value_concept_display] += 1

    loinc_catalog: list[LOINCEntry] = []
    for code, e in sorted(loinc_map.items(), key=lambda x: -x[1]["count"]):
        values = sorted(e["values"], key=lambda x: x[0] or datetime.min.replace(tzinfo=timezone.utc))
        min_val = min(v for _, v in values) if values else None
        max_val = max(v for _, v in values) if values else None
        last_val = values[-1][1] if values else None

        loinc_catalog.append(LOINCEntry(
            code=code,
            display=e["display"],
            category=e["category"],
            count=e["count"],
            first_dt=e["first_dt"],
            last_dt=e["last_dt"],
            min_value=min_val,
            max_value=max_val,
            last_value=last_val,
            unit=e["unit"],
            value_counts=dict(e["value_concepts"]),
        ))

    # --- Encounters ---
    enc_class_breakdown: dict[str, int] = defaultdict(int)
    enc_type_counter: dict[str, int] = defaultdict(int)
    total_linked = 0

    for enc in record.encounters:
        enc_class_breakdown[enc.class_code or "unknown"] += 1
        enc_type_counter[enc.encounter_type or "unknown"] += 1
        total_linked += (
            len(enc.linked_observations)
            + len(enc.linked_conditions)
            + len(enc.linked_procedures)
            + len(enc.linked_medications)
            + len(enc.linked_diagnostic_reports)
            + len(enc.linked_immunizations)
        )

    avg_resources = (total_linked / len(record.encounters)) if record.encounters else 0.0
    enc_type_breakdown = [
        EncounterTypeSummary(etype, cnt)
        for etype, cnt in sorted(enc_type_counter.items(), key=lambda x: -x[1])
    ]

    # --- Allergies ---
    allergy_labels = [a.code.label() for a in record.allergies]

    # --- Immunizations ---
    unique_vaccines = list(dict.fromkeys(
        imm.display for imm in record.immunizations if imm.display
    ))

    # --- Complexity score ---
    score = (
        min(len(record.conditions), 30) * 2.0
        + min(len(active_meds), 20) * 1.5
        + min(years_of_history / 5, 20) * 1.0
        + min(len(record.encounters) / 10, 20) * 0.5
    )
    score = min(score, 100.0)
    if score < 20:
        tier = "simple"
    elif score < 40:
        tier = "moderate"
    elif score < 70:
        tier = "complex"
    else:
        tier = "highly_complex"

    return PatientStats(
        name=s.name,
        age_years=s.age_years,
        gender=s.gender,
        is_deceased=s.deceased,
        race=s.race,
        city=s.city,
        state=s.state,
        earliest_encounter_dt=earliest_dt,
        latest_encounter_dt=latest_dt,
        years_of_history=years_of_history,
        resource_type_counts=record.resource_type_counts,
        total_resources=total,
        clinical_resource_count=clinical_count,
        billing_resource_count=billing_count,
        billing_pct=billing_pct,
        active_condition_count=len(active_conditions),
        resolved_condition_count=len(resolved_conditions),
        condition_catalog=condition_catalog,
        active_med_count=len(active_meds),
        total_med_count=len(record.medications),
        med_catalog=med_catalog,
        unique_loinc_count=len(loinc_map),
        obs_category_breakdown=dict(obs_category_breakdown),
        loinc_catalog=loinc_catalog,
        encounter_count=len(record.encounters),
        encounter_class_breakdown=dict(enc_class_breakdown),
        encounter_type_breakdown=enc_type_breakdown,
        avg_resources_per_encounter=avg_resources,
        allergy_count=len(record.allergies),
        allergy_labels=allergy_labels,
        immunization_count=len(record.immunizations),
        unique_vaccines=unique_vaccines,
        complexity_score=score,
        complexity_tier=tier,
        parse_warning_count=len(record.parse_warnings),
    )
