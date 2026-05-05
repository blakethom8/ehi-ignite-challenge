"""
/api/patients — patient listing and detail endpoints.
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from datetime import date, datetime
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException

from api.core.loader import (
    list_patient_files,
    patient_display_name,
    patient_id_from_path,
    path_from_patient_id,
    load_patient,
    data_dir,
)
from api.core.aggregation import list_upload_workspaces
from api.models import (
    PatientListItem,
    PatientOverview,
    ConditionRow,
    MedRow,
    ResourceTypeCount,
    EncounterTypeSummary,
    CareTeamSummaryItem,
    SiteOfServiceSummaryItem,
    TimelineResponse,
    EncounterEvent,
    EncounterDetail,
    ObservationDetail,
    ConditionDetail,
    ProcedureDetail,
    MedicationDetail,
    LabHistoryPoint,
    LabValue,
    LabAlertFlag,
    KeyLabsResponse,
    TimelineEvent,
    TimelineMonth,
    SafetyMedication,
    SafetyFlag,
    SafetyResponse,
    SurgicalRiskComponent,
    SurgicalRiskResponse,
    ImmunizationItem,
    ImmunizationResponse,
    RankedConditionItem,
    ConditionAcuityResponse,
    ProcedureItem,
    ProceduresResponse,
    PatientRiskSummary,
    PatientRiskSummaryResponse,
    InteractionResult,
    InteractionResponse,
    MedicationEpisodeItem,
    ConditionEpisodeItem,
    EncounterMarker,
    ProcedureMarker,
    DiagnosticReportItem,
    CareJourneyResponse,
)
from api.core.interaction_checker import check_interactions

# ---------------------------------------------------------------------------
# Condition ranker
# ---------------------------------------------------------------------------

from api.core.condition_ranker import ConditionRanker

_condition_ranker = ConditionRanker()

# ---------------------------------------------------------------------------
# Drug classifier
# ---------------------------------------------------------------------------

from lib.clinical.drug_classifier import DrugClassifier, SafetyFlag as _SafetyFlag

_REPO_ROOT = Path(__file__).parent.parent.parent
_DRUG_MAPPING = _REPO_ROOT / "lib" / "clinical" / "drug_classes.json"
_classifier = DrugClassifier(mapping_path=_DRUG_MAPPING)

router = APIRouter(prefix="/patients", tags=["patients"])

BILLING_TYPES = {"Claim", "ExplanationOfBenefit"}
ADMIN_TYPES = {"Organization", "Practitioner", "PractitionerRole", "Location"}
DEMO_PATIENT_LIMIT = max(1, int(os.getenv("EHI_DEMO_PATIENT_LIMIT", "20")))
DEMO_PATIENT_IDS = (
    # Current working demo patient and early aggregation fixture.
    "763b6101-133a-44bb-ac60-3c097d6c0ba1",
    "5cbc121b-cd71-4428-b8b7-31e53eba8184",
    # Curated high-signal Synthea records for development and demos.
    "eec393be-2569-46db-a974-33d7c853d690",
    "8143897c-e650-4e55-b08d-8306e2f424bb",
    "0718123b-5034-4965-a145-3d8d71b11389",
    "8055d1ca-46b7-44a3-a033-b918e4c3ecfb",
    "86017b61-3171-45b6-9bd7-b6ca6a946604",
    "4b5e42a8-b3e6-411b-b32d-585f71bca118",
    "8e674838-e3da-4bc9-b9e3-7d726b07291d",
    "fc863fc4-dbe2-430b-b213-ce400f6e47a8",
    "81e1b4cb-6817-4bdc-97cd-c1f3ac960345",
    "86337f98-0d8d-40ee-ad5d-68811024c886",
    "2d75e3a4-f0f6-45dd-8b57-75fb2f303c9e",
    "f636829a-4277-4392-a9a2-1050ef6eceed",
    "afafca2f-b97d-4fc9-b3b6-984e46d4c0b8",
    "b0f49c80-b59b-4df6-8292-40ce8b8f8612",
    "8937b6dc-4484-49c1-9bef-5700688d5f90",
    "df121e33-f3dc-4d02-a523-3bbd89c8fa5b",
    "6e965c83-1c3f-42bb-9604-f809c18bad6b",
    "fa7e100a-ff60-4edb-9fc6-9574a42784aa",
)


def _encounter_date_sort(value: datetime | None) -> int:
    return value.toordinal() if value else 0


def _care_network_summary(record) -> tuple[list[CareTeamSummaryItem], list[SiteOfServiceSummaryItem]]:
    provider_rows: dict[str, dict] = {}
    site_rows: dict[str, dict] = {}

    for enc in record.encounters:
        class_code = enc.class_code or "Unknown"
        start = enc.period.start
        provider_name = enc.practitioner_name or "Unknown provider"
        site_name = enc.provider_org or "Unknown organization"

        provider = provider_rows.setdefault(
            provider_name,
            {
                "organizations": set(),
                "encounter_count": 0,
                "latest_encounter_dt": None,
                "class_breakdown": defaultdict(int),
            },
        )
        provider["organizations"].add(site_name)
        provider["encounter_count"] += 1
        provider["class_breakdown"][class_code] += 1
        if start and (provider["latest_encounter_dt"] is None or start > provider["latest_encounter_dt"]):
            provider["latest_encounter_dt"] = start

        site = site_rows.setdefault(
            site_name,
            {
                "providers": set(),
                "encounter_count": 0,
                "latest_encounter_dt": None,
                "class_breakdown": defaultdict(int),
            },
        )
        site["providers"].add(provider_name)
        site["encounter_count"] += 1
        site["class_breakdown"][class_code] += 1
        if start and (site["latest_encounter_dt"] is None or start > site["latest_encounter_dt"]):
            site["latest_encounter_dt"] = start

    care_team = [
        CareTeamSummaryItem(
            name=name,
            organizations=sorted(row["organizations"]),
            encounter_count=row["encounter_count"],
            latest_encounter_dt=row["latest_encounter_dt"],
            class_breakdown=dict(row["class_breakdown"]),
        )
        for name, row in provider_rows.items()
    ]
    care_team.sort(
        key=lambda item: (
            item.name == "Unknown provider",
            -item.encounter_count,
            -_encounter_date_sort(item.latest_encounter_dt),
            item.name,
        )
    )

    sites_of_service = [
        SiteOfServiceSummaryItem(
            name=name,
            provider_count=len(row["providers"]),
            encounter_count=row["encounter_count"],
            latest_encounter_dt=row["latest_encounter_dt"],
            class_breakdown=dict(row["class_breakdown"]),
        )
        for name, row in site_rows.items()
    ]
    sites_of_service.sort(
        key=lambda item: (
            item.name == "Unknown organization",
            -item.encounter_count,
            -_encounter_date_sort(item.latest_encounter_dt),
            item.name,
        )
    )

    return care_team[:8], sites_of_service[:8]

# ---------------------------------------------------------------------------
# Pre-operative hold/bridge protocol notes — keyed by drug class
# ---------------------------------------------------------------------------

PROTOCOL_NOTES: dict[str, str] = {
    "anticoagulants": (
        "Hold warfarin 5 days pre-op; check INR day of surgery (target <1.5). "
        "Bridge with LMWH (enoxaparin 1 mg/kg SQ BID) for high-thromboembolic-risk patients "
        "(mechanical heart valve, AF with CHA\u2082DS\u2082-VASc \u22654, recent VTE <3 months). "
        "Last LMWH dose 24h pre-op. Resume warfarin evening of surgery if hemostasis adequate."
    ),
    "antiplatelets": (
        "Hold aspirin 7 days pre-op (or continue low-dose 81mg if cardiac stent within 12 months \u2014 "
        "discuss with cardiologist). Hold clopidogrel/ticagrelor 5\u20137 days pre-op. "
        "Do NOT hold if drug-eluting stent placed within 12 months without cardiology sign-off."
    ),
    "jak_inhibitors": (
        "Hold 1\u20132 weeks pre-op per ACR guidelines (tofacitinib: 3 days minimum; "
        "baricitinib/upadacitinib: 3 days minimum). Restart after wound healing confirmed, "
        "typically 2 weeks post-op. Increased infection risk; ensure prophylactic antibiotics given."
    ),
    "immunosuppressants": (
        "Do NOT abruptly discontinue. Consult with prescribing specialist (transplant/rheumatology). "
        "Tacrolimus/cyclosporine: continue at reduced dose, monitor levels day of surgery. "
        "Mycophenolate: typically held 1 week pre-op for elective cases. "
        "Perioperative stress-dose steroids may be needed."
    ),
    "nsaids": (
        "Hold NSAIDs (ibuprofen, naproxen, indomethacin) 3\u20135 days pre-op due to platelet "
        "dysfunction and renal effects. COX-2 inhibitors (celecoxib) may be continued if needed "
        "for pain control \u2014 consult surgeon. Post-op: restart only after renal function confirmed stable."
    ),
    "opioids": (
        "Continue chronic opioids up to day of surgery to avoid withdrawal. "
        "Inform anesthesia team \u2014 increased intraoperative and post-op opioid requirements expected. "
        "Consider multimodal analgesia plan. Buprenorphine: consult pain management \u2014 "
        "may need dose adjustment or conversion."
    ),
    "anticonvulsants": (
        "Continue anticonvulsants without interruption. Do not hold pre-op. "
        "Ensure IV formulation available if patient unable to take PO post-op. "
        "Phenytoin/carbamazepine: CYP450 inducers \u2014 may alter anesthetic metabolism. "
        "Inform anesthesia team."
    ),
    "corticosteroids": (
        "Do NOT abruptly discontinue. Patients on chronic steroids (>5mg prednisone/day for >3 weeks) "
        "may have HPA axis suppression. Administer stress-dose steroids: hydrocortisone 50mg IV "
        "at induction + 25mg q8h x24h for major surgery. Taper back to baseline dose post-op."
    ),
    "maois": (
        "Ideally hold MAOIs 14 days pre-op due to risk of hypertensive crisis and serotonin syndrome "
        "with anesthetic agents. Discuss with psychiatry before stopping. "
        "If surgery cannot be delayed: avoid meperidine, indirect sympathomimetics, and serotonergic agents. "
        "Use direct-acting vasopressors only."
    ),
    "antidiabetics": (
        "Hold metformin 24\u201348h pre-op (lactic acidosis risk with contrast/renal changes). "
        "Sulfonylureas: hold morning of surgery (hypoglycemia risk). "
        "Insulin: give 50\u201380% of basal dose morning of surgery; hold mealtime insulin. "
        "Monitor glucose q1\u20132h intraoperatively; target 140\u2013180 mg/dL. "
        "GLP-1 agonists (semaglutide): hold 1 week pre-op due to gastroparesis risk."
    ),
}

HIGH_RISK_CONDITION_CATEGORIES = {"CARDIAC", "PULMONARY"}
MODERATE_RISK_CONDITION_CATEGORIES = {"RENAL", "HEPATIC", "HEMATOLOGIC", "VASCULAR"}
REVIEW_RISK_CONDITION_CATEGORIES = {"METABOLIC", "NEUROLOGIC", "IMMUNOLOGIC", "ONCOLOGIC"}
COAGULATION_LOINC_CODES = {"6301-6", "34714-6", "5902-2", "3173-2"}


def _component_status(score: int, flagged: bool = False, review: bool = False) -> str:
    if flagged:
        return "FLAGGED"
    if review or score > 0:
        return "REVIEW"
    return "CLEARED"


def _limit_evidence(items: list[str], limit: int = 5) -> list[str]:
    if len(items) <= limit:
        return items
    return items[:limit] + [f"+{len(items) - limit} more"]


@router.get("", response_model=list[PatientListItem])
def list_patients() -> list[PatientListItem]:
    all_synthea_items = _cached_patient_list()
    synthea_items = _curated_demo_patients(all_synthea_items)
    all_synthea_ids = {patient.id for patient in all_synthea_items}
    upload_items = [
        item for item in list_upload_workspaces()
        if item.id not in all_synthea_ids
    ]
    return upload_items + synthea_items


def _curated_demo_patients(items: list[PatientListItem]) -> list[PatientListItem]:
    """Return the intentionally small patient registry shown in the selector.

    The Synthea corpus remains available for benchmarks and backend tests, but
    the application demo should feel like a managed patient workspace list, not
    a 1,180-patient file browser.
    """
    by_id = {item.id: item for item in items}
    curated = [by_id[patient_id] for patient_id in DEMO_PATIENT_IDS if patient_id in by_id]
    seen = {item.id for item in curated}
    if len(curated) < DEMO_PATIENT_LIMIT:
        fillers = sorted(
            (item for item in items if item.id not in seen),
            key=lambda item: (-item.complexity_score, item.name),
        )
        curated.extend(fillers[: DEMO_PATIENT_LIMIT - len(curated)])
    return curated[:DEMO_PATIENT_LIMIT]


@lru_cache(maxsize=1)
def _cached_patient_list() -> list[PatientListItem]:
    """
    Return a lightweight list of all patients with pre-computed stats.
    Uses the corpus cache (instant if already built, ~5-10s first time).
    """
    try:
        from lib.patient_catalog.corpus import load_corpus
        catalog = load_corpus(data_dir())
        return [
            PatientListItem(
                id=idx.patient_id,
                name=idx.patient_name,
                age_years=idx.age_years,
                gender=idx.gender,
                complexity_tier=idx.complexity_tier,
                complexity_score=idx.complexity_score,
                total_resources=idx.total_resources,
                encounter_count=idx.encounter_count,
                active_condition_count=idx.active_condition_count,
                active_med_count=idx.active_med_count,
                workspace_type="synthea",
            )
            for idx in catalog.patients
        ]
    except Exception:
        # Fallback to filename-only list if corpus cache fails
        files = list_patient_files()
        return [
            PatientListItem(
                id=patient_id_from_path(path),
                name=patient_display_name(path),
                age_years=0.0,
                gender="",
                complexity_tier="",
                complexity_score=0.0,
                total_resources=0,
                encounter_count=0,
                active_condition_count=0,
                active_med_count=0,
                workspace_type="synthea",
            )
            for path in files
        ]


@router.get("/risk-summary", response_model=PatientRiskSummaryResponse)
def patient_risk_summary() -> PatientRiskSummaryResponse:
    return _cached_patient_risk_summary()


@lru_cache(maxsize=1)
def _cached_patient_risk_summary() -> PatientRiskSummaryResponse:
    """
    Return all patients enriched with risk tier and critical safety flags.

    NOTE: This iterates all 1,180 patient files and calls the drug classifier
    for each. First call is slow (~30-60s). Subsequent calls per patient are
    instant because load_patient() is LRU-cached.
    """
    files = list_patient_files()
    results: list[PatientRiskSummary] = []

    for path in files:
        patient_id = patient_id_from_path(path)
        result = load_patient(patient_id)
        if result is None:
            continue

        record, stats = result

        # Classify medications to find active critical-severity drug classes
        raw_flags = _classifier.generate_safety_flags(record.medications)
        active_critical_classes: list[str] = [
            flag.class_key
            for flag in raw_flags
            if flag.status == "ACTIVE" and flag.severity == "critical"
        ]

        results.append(PatientRiskSummary(
            id=patient_id,
            name=stats.name,
            complexity_tier=stats.complexity_tier,
            has_critical_flag=len(active_critical_classes) > 0,
            active_critical_classes=active_critical_classes,
        ))

    return PatientRiskSummaryResponse(patients=results)


@router.get("/loaded", response_model=list[PatientListItem])
def list_patients_with_stats() -> list[PatientListItem]:
    """
    Return patient list WITH stats computed. Loads all bundles — slow for
    large corpora. Use sparingly (corpus view, sorting/filtering).
    """
    files = list_patient_files()
    items: list[PatientListItem] = []
    for path in files:
        result = load_patient(patient_id_from_path(path))
        if result is None:
            continue
        _, stats = result
        items.append(PatientListItem(
            id=patient_id_from_path(path),
            name=stats.name,
            age_years=stats.age_years,
            gender=stats.gender,
            complexity_tier=stats.complexity_tier,
            complexity_score=stats.complexity_score,
            total_resources=stats.total_resources,
            encounter_count=stats.encounter_count,
            active_condition_count=stats.active_condition_count,
            active_med_count=stats.active_med_count,
        ))
    return items


@router.get("/{patient_id}/overview", response_model=PatientOverview)
def patient_overview(patient_id: str) -> PatientOverview:
    """Full patient overview — demographics, resource counts, conditions, meds."""
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result
    s = record.summary

    # Resource type breakdown with categories
    resource_type_counts: list[ResourceTypeCount] = []
    for rtype, count in sorted(record.resource_type_counts.items(), key=lambda x: -x[1]):
        if rtype in BILLING_TYPES:
            category = "Billing"
        elif rtype in ADMIN_TYPES:
            category = "Administrative"
        else:
            category = "Clinical"
        resource_type_counts.append(ResourceTypeCount(
            resource_type=rtype,
            count=count,
            category=category,
        ))

    conditions = [
        ConditionRow(
            condition_id=c.condition_id,
            display=c.display,
            clinical_status=c.clinical_status,
            is_active=c.is_active,
            onset_dt=c.onset_dt,
            abatement_dt=c.abatement_dt,
        )
        for c in stats.condition_catalog
    ]

    medications = [
        MedRow(
            med_id=m.med_id,
            display=m.display,
            status=m.status,
            authored_on=m.authored_on,
            is_active=m.is_active,
        )
        for m in stats.med_catalog
    ]

    enc_type_breakdown = [
        EncounterTypeSummary(encounter_type=e.encounter_type, count=e.count)
        for e in stats.encounter_type_breakdown
    ]
    care_team, sites_of_service = _care_network_summary(record)

    return PatientOverview(
        id=patient_id,
        name=stats.name,
        age_years=stats.age_years,
        gender=stats.gender,
        birth_date=str(s.birth_date) if s.birth_date else None,
        is_deceased=stats.is_deceased,
        race=stats.race or "",
        ethnicity=s.ethnicity or "",
        city=stats.city or "",
        state=stats.state or "",
        language=s.language or "",
        marital_status=s.marital_status or "",
        daly=s.daly,
        qaly=s.qaly,
        earliest_encounter_dt=stats.earliest_encounter_dt,
        latest_encounter_dt=stats.latest_encounter_dt,
        years_of_history=stats.years_of_history,
        total_resources=stats.total_resources,
        clinical_resource_count=stats.clinical_resource_count,
        billing_resource_count=stats.billing_resource_count,
        billing_pct=stats.billing_pct,
        resource_type_counts=resource_type_counts,
        complexity_score=stats.complexity_score,
        complexity_tier=stats.complexity_tier,
        active_condition_count=stats.active_condition_count,
        resolved_condition_count=stats.resolved_condition_count,
        conditions=conditions,
        active_med_count=stats.active_med_count,
        total_med_count=stats.total_med_count,
        medications=medications,
        unique_loinc_count=stats.unique_loinc_count,
        obs_category_breakdown=stats.obs_category_breakdown,
        encounter_count=stats.encounter_count,
        encounter_class_breakdown=stats.encounter_class_breakdown,
        encounter_type_breakdown=enc_type_breakdown,
        avg_resources_per_encounter=stats.avg_resources_per_encounter,
        care_team=care_team,
        sites_of_service=sites_of_service,
        allergy_count=stats.allergy_count,
        allergy_labels=stats.allergy_labels,
        immunization_count=stats.immunization_count,
        unique_vaccines=stats.unique_vaccines,
        parse_warning_count=stats.parse_warning_count,
    )


@router.get("/{patient_id}/timeline", response_model=TimelineResponse)
def patient_timeline(patient_id: str) -> TimelineResponse:
    """Encounter timeline — chronological list with linked resource counts."""
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result

    encounters_sorted = sorted(
        record.encounters,
        key=lambda e: e.period.start or datetime.min,
    )

    year_counts: dict[str, int] = defaultdict(int)
    events: list[EncounterEvent] = []

    for enc in encounters_sorted:
        if enc.period.start:
            year_counts[str(enc.period.start.year)] += 1

        events.append(EncounterEvent(
            encounter_id=enc.encounter_id,
            class_code=enc.class_code or "",
            encounter_type=enc.encounter_type or "",
            reason_display=enc.reason_display or "",
            start=enc.period.start,
            end=enc.period.end,
            provider_org=enc.provider_org or "",
            practitioner_name=enc.practitioner_name or "",
            linked_observation_count=len(enc.linked_observations),
            linked_condition_count=len(enc.linked_conditions),
            linked_procedure_count=len(enc.linked_procedures),
            linked_medication_count=len(enc.linked_medications),
        ))

    return TimelineResponse(
        patient_id=patient_id,
        name=stats.name,
        encounters=events,
        year_counts=dict(year_counts),
    )


@router.get("/{patient_id}/encounters/{encounter_id}", response_model=EncounterDetail)
def encounter_detail(patient_id: str, encounter_id: str) -> EncounterDetail:
    """Full detail for a single encounter — all linked resources."""
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, _ = result
    enc = record.encounter_index.get(encounter_id)
    if enc is None:
        raise HTTPException(status_code=404, detail=f"Encounter not found: {encounter_id}")

    # Duration
    duration_hours: float | None = None
    if enc.period.start and enc.period.end:
        duration_hours = (enc.period.end - enc.period.start).total_seconds() / 3600

    # Linked observations
    observations = [
        ObservationDetail(
            obs_id=obs.obs_id,
            category=obs.category or "",
            display=obs.display or "",
            loinc_code=obs.loinc_code or "",
            effective_dt=obs.effective_dt,
            value_type=obs.value_type or "",
            value_quantity=obs.value_quantity,
            value_unit=obs.value_unit or "",
            value_concept_display=obs.value_concept_display,
        )
        for obs_id in enc.linked_observations
        if (obs := record.obs_index.get(obs_id)) is not None
    ]

    # Linked conditions
    cond_index = {c.condition_id: c for c in record.conditions}
    conditions = [
        ConditionDetail(
            condition_id=c.condition_id,
            display=c.code.label(),
            clinical_status=c.clinical_status,
            is_active=c.is_active,
            onset_dt=c.onset_dt,
        )
        for cid in enc.linked_conditions
        if (c := cond_index.get(cid)) is not None
    ]

    # Linked procedures
    proc_index = {p.procedure_id: p for p in record.procedures}
    procedures = [
        ProcedureDetail(
            procedure_id=p.procedure_id,
            display=p.code.label(),
            status=p.status,
            performed_start=p.performed_period.start if p.performed_period else None,
            reason_display=p.reason_display or "",
        )
        for pid in enc.linked_procedures
        if (p := proc_index.get(pid)) is not None
    ]

    # Linked medications
    med_index = {m.med_id: m for m in record.medications}
    medications = [
        MedicationDetail(
            med_id=m.med_id,
            display=m.display,
            status=m.status,
            authored_on=m.authored_on,
            dosage_text=m.dosage_text or "",
            reason_display=m.reason_display or "",
        )
        for mid in enc.linked_medications
        if (m := med_index.get(mid)) is not None
    ]

    return EncounterDetail(
        encounter_id=enc.encounter_id,
        class_code=enc.class_code or "",
        encounter_type=enc.encounter_type or "",
        reason_display=enc.reason_display or "",
        start=enc.period.start,
        end=enc.period.end,
        duration_hours=duration_hours,
        provider_org=enc.provider_org or "",
        practitioner_name=enc.practitioner_name or "",
        observations=observations,
        conditions=conditions,
        procedures=procedures,
        medications=medications,
        diagnostic_report_count=len(enc.linked_diagnostic_reports),
        imaging_study_count=len(enc.linked_imaging_studies),
    )


# ---------------------------------------------------------------------------
# Lab alert thresholds
# (loinc_code): (display_name, low_critical, low_warning, high_warning, high_critical, unit)
# None = threshold not applicable for that direction
# ---------------------------------------------------------------------------

ALERT_THRESHOLDS: dict[str, tuple[str, float | None, float | None, float | None, float | None, str]] = {
    "718-7":  ("Hemoglobin",  6.0,  8.0,   17.5, 20.0,  "g/dL"),
    "4544-3": ("Hematocrit",  18.0, 24.0,  52.0, 60.0,  "%"),
    "777-3":  ("Platelets",   50.0, 100.0, 400.0, 1000.0, "K/uL"),
    "6301-6": ("INR",         None, None,  3.0,  5.0,   ""),
    "2160-0": ("Creatinine",  None, None,  1.5,  3.0,   "mg/dL"),
    "2823-3": ("Potassium",   3.0,  3.5,   5.5,  6.5,   "mEq/L"),
    "2951-2": ("Sodium",      125.0, 130.0, 148.0, 155.0, "mEq/L"),
    "2345-7": ("Glucose",     50.0, 70.0,  200.0, 400.0, "mg/dL"),
    "1751-7": ("Albumin",     None, 2.5,   None, None,  "g/dL"),
    "6768-6": ("Alk Phos",    None, None,  120.0, 300.0, "U/L"),
}


def _obs_date_to_date(obs_dt: datetime | None) -> date | None:
    """Extract a date from an observation's effective_dt (datetime or date)."""
    if obs_dt is None:
        return None
    if isinstance(obs_dt, datetime):
        return obs_dt.date()
    return obs_dt  # already a date


def _compute_alert_flags(record, today_dt: date) -> list[LabAlertFlag]:
    """
    Scan all observations within the last 30 days against ALERT_THRESHOLDS.
    Returns deduplicated (most recent per LOINC), sorted critical-first then by days_ago.
    """
    cutoff = today_dt.toordinal() - 30

    # Collect all recent, matchable observations grouped by loinc_code
    # Structure: loinc_code → list of (obs, value_float, days_ago)
    candidates: dict[str, list[tuple]] = defaultdict(list)

    for obs in record.observations:
        if obs.loinc_code not in ALERT_THRESHOLDS:
            continue
        if obs.value_type != "quantity" or obs.value_quantity is None:
            continue
        obs_date = _obs_date_to_date(obs.effective_dt)
        if obs_date is None:
            continue
        days_ago = today_dt.toordinal() - obs_date.toordinal()
        if days_ago > 30 or days_ago < 0:
            continue
        candidates[obs.loinc_code].append((obs, obs.value_quantity, days_ago))

    # For trend detection, also gather all historical readings per LOINC (sorted newest-first)
    all_by_loinc: dict[str, list] = defaultdict(list)
    for obs in record.observations:
        if obs.loinc_code in ALERT_THRESHOLDS and obs.value_type == "quantity" and obs.value_quantity is not None:
            all_by_loinc[obs.loinc_code].append(obs)

    for loinc_code in all_by_loinc:
        all_by_loinc[loinc_code].sort(
            key=lambda o: o.effective_dt or datetime.min, reverse=True
        )

    flags: list[LabAlertFlag] = []

    for loinc_code, obs_list in candidates.items():
        # Take the most recent observation for this LOINC (smallest days_ago)
        obs_list.sort(key=lambda t: t[2])  # sort by days_ago ascending
        most_recent_obs, value, days_ago = obs_list[0]

        display_name, low_crit, low_warn, high_warn, high_crit, unit = ALERT_THRESHOLDS[loinc_code]

        severity: str | None = None
        direction: str | None = None

        # Check critical first (harder threshold)
        if low_crit is not None and value < low_crit:
            severity = "critical"
            direction = "low"
        elif high_crit is not None and value > high_crit:
            severity = "critical"
            direction = "high"
        elif low_warn is not None and value < low_warn:
            severity = "warning"
            direction = "low"
        elif high_warn is not None and value > high_warn:
            severity = "warning"
            direction = "high"

        # Check trend (only if no harder flag already set, or to augment a warning)
        if severity is None or severity == "warning":
            history = all_by_loinc.get(loinc_code, [])
            if len(history) >= 3:
                last3_vals = [h.value_quantity for h in history[:3] if h.value_quantity is not None]
                if len(last3_vals) == 3:
                    v0, v1, v2 = last3_vals[0], last3_vals[1], last3_vals[2]
                    # Trending up: each successive reading increases by >5%
                    if v2 != 0 and v1 != 0:
                        r1 = (v1 - v2) / abs(v2)  # v1 vs v2 (older)
                        r2 = (v0 - v1) / abs(v1)  # v0 vs v1 (newer)
                        if r1 > 0.05 and r2 > 0.05 and severity is None:
                            severity = "warning"
                            direction = "trending_up"
                        elif r1 < -0.05 and r2 < -0.05 and severity is None:
                            severity = "warning"
                            direction = "trending_down"

        if severity is None or direction is None:
            continue

        # Build message
        unit_str = f" {unit}" if unit else ""
        if direction == "low":
            msg = f"{display_name} {value}{unit_str} — critically low" if severity == "critical" else f"{display_name} {value}{unit_str} — below normal"
        elif direction == "high":
            msg = f"{display_name} {value}{unit_str} — critically high" if severity == "critical" else f"{display_name} {value}{unit_str} — above normal"
        elif direction == "trending_up":
            msg = f"{display_name} {value}{unit_str} — trending upward over last 3 readings"
        else:
            msg = f"{display_name} {value}{unit_str} — trending downward over last 3 readings"

        flags.append(LabAlertFlag(
            lab_name=display_name,
            loinc_code=loinc_code,
            value=value,
            unit=unit,
            severity=severity,
            direction=direction,
            message=msg,
            days_ago=days_ago,
        ))

    # Sort: critical first, then warning; within severity, sort by days_ago ascending
    flags.sort(key=lambda f: (0 if f.severity == "critical" else 1, f.days_ago))
    return flags


def _compute_timeline_events(record, today_dt: date) -> list[TimelineMonth]:
    """
    Build 6-month monthly buckets of LOINC observations for ALERT_THRESHOLDS codes.

    For each calendar month in the last 6 months (oldest → newest):
    - Find all observations matching any tracked LOINC code
    - For each code with a value in that month, record change_direction vs prior month
    - Only include months with at least one event
    """
    # Build a list of (year, month) tuples covering the last 6 months, oldest first
    months: list[tuple[int, int]] = []
    y, m = today_dt.year, today_dt.month
    for _ in range(6):
        months.append((y, m))
        m -= 1
        if m == 0:
            m = 12
            y -= 1
    months.reverse()  # oldest first

    # Collect all observations for tracked LOINC codes with quantity values
    # Keyed by (loinc_code, year, month) → list of (date, value, display, unit)
    obs_by_code_month: dict[tuple[str, int, int], list[tuple[date, float, str, str]]] = defaultdict(list)

    for obs in record.observations:
        if obs.loinc_code not in ALERT_THRESHOLDS:
            continue
        if obs.value_type != "quantity" or obs.value_quantity is None:
            continue
        obs_date = _obs_date_to_date(obs.effective_dt)
        if obs_date is None:
            continue
        obs_by_code_month[(obs.loinc_code, obs_date.year, obs_date.month)].append(
            (obs_date, obs.value_quantity, obs.display or ALERT_THRESHOLDS[obs.loinc_code][0], obs.value_unit or ALERT_THRESHOLDS[obs.loinc_code][5])
        )

    result_months: list[TimelineMonth] = []

    # Track prior month value per loinc_code for change_direction
    prior_month_values: dict[str, float] = {}

    for yr, mo in months:
        events: list[TimelineEvent] = []

        for loinc_code, (display_name, _lc, _lw, _hw, _hc, unit) in ALERT_THRESHOLDS.items():
            bucket = obs_by_code_month.get((loinc_code, yr, mo))
            if not bucket:
                continue

            # Use the most recent observation in that month
            bucket.sort(key=lambda t: t[0], reverse=True)
            obs_date, value, obs_display, obs_unit = bucket[0]

            # Compute change_direction vs prior month
            prior = prior_month_values.get(loinc_code)
            if prior is None:
                change_direction = "stable"
            else:
                pct = (value - prior) / abs(prior) if prior != 0 else 0.0
                if pct > 0.05:
                    change_direction = "up"
                elif pct < -0.05:
                    change_direction = "down"
                else:
                    change_direction = "stable"

            events.append(TimelineEvent(
                loinc_code=loinc_code,
                display_name=obs_display if obs_display else display_name,
                value=value,
                unit=obs_unit if obs_unit else unit,
                date=obs_date.isoformat(),
                change_direction=change_direction,
            ))

            # Update prior for next month's comparison
            prior_month_values[loinc_code] = value

        if events:
            import calendar as _cal
            label = f"{_cal.month_abbr[mo]} {yr}"
            result_months.append(TimelineMonth(
                month=f"{yr:04d}-{mo:02d}",
                label=label,
                events=events,
            ))

    return result_months


@router.get("/{patient_id}/key-labs", response_model=KeyLabsResponse)
def patient_key_labs(patient_id: str) -> KeyLabsResponse:
    """
    Return the most recent value + trend for clinically important lab panels.

    Panels covered:
    - Hematology: CBC labs (Hemoglobin, Hematocrit, Platelets, WBC)
    - Metabolic: BMP/CMP (Sodium, Potassium, Creatinine, BUN, Glucose)
    - Coagulation: INR, PT, PTT
    - Cardiac: Troponin, BNP, proBNP
    """
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, _ = result

    # LOINC code → (panel name, display label)
    PANEL_LOINC: dict[str, tuple[str, str]] = {
        # Hematology
        "718-7":   ("Hematology", "Hemoglobin"),
        "20570-8": ("Hematology", "Hematocrit"),
        "777-3":   ("Hematology", "Platelets"),
        "6690-2":  ("Hematology", "WBC"),
        # Metabolic
        "2951-2":  ("Metabolic", "Sodium"),
        "2823-3":  ("Metabolic", "Potassium"),
        "2160-0":  ("Metabolic", "Creatinine"),
        "3094-0":  ("Metabolic", "BUN"),
        "2345-7":  ("Metabolic", "Glucose"),
        # Coagulation
        "34714-6": ("Coagulation", "INR"),
        "5902-2":  ("Coagulation", "PT"),
        "3173-2":  ("Coagulation", "PTT"),
        # Cardiac
        "10839-9": ("Cardiac", "Troponin"),
        "42637-9": ("Cardiac", "BNP"),
        "33762-6": ("Cardiac", "proBNP"),
    }

    # Group observations by LOINC code, keeping only quantity observations
    obs_by_loinc: dict[str, list] = defaultdict(list)
    for obs in record.observations:
        if obs.loinc_code in PANEL_LOINC and obs.value_type == "quantity" and obs.value_quantity is not None:
            obs_by_loinc[obs.loinc_code].append(obs)

    # Build panels dict: panel_name → list[LabValue]
    panels: dict[str, list[LabValue]] = {}

    for loinc_code, (panel_name, default_display) in PANEL_LOINC.items():
        observations = obs_by_loinc.get(loinc_code)
        if not observations:
            continue

        # Sort by effective_dt descending (most recent first); None dates go last
        observations_sorted = sorted(
            observations,
            key=lambda o: o.effective_dt or datetime.min,
            reverse=True,
        )

        most_recent = observations_sorted[0]

        # Compute trend by comparing the two most recent readings
        trend: str | None = None
        if len(observations_sorted) >= 2:
            v0 = most_recent.value_quantity          # most recent
            v1 = observations_sorted[1].value_quantity  # previous
            if v0 is not None and v1 is not None and v1 != 0:
                pct_change = (v0 - v1) / abs(v1)
                if pct_change > 0.05:
                    trend = "up"
                elif pct_change < -0.05:
                    trend = "down"
                else:
                    trend = "stable"

        # Build history: take up to 10 readings, oldest first
        history_obs = observations_sorted[:10]
        history_obs.reverse()  # oldest first for sparkline
        history = [
            LabHistoryPoint(
                effective_dt=obs.effective_dt,
                value=obs.value_quantity,
            )
            for obs in history_obs
            if obs.value_quantity is not None
        ]

        lab = LabValue(
            loinc_code=loinc_code,
            display=most_recent.display or default_display,
            value=most_recent.value_quantity,
            unit=most_recent.value_unit or "",
            effective_dt=most_recent.effective_dt,
            trend=trend,
            is_abnormal=None,  # No reference range data available in Synthea
            history=history,
        )

        if panel_name not in panels:
            panels[panel_name] = []
        panels[panel_name].append(lab)

    # Compute alert flags for recent labs (last 30 days)
    today = datetime.now().date()
    alert_flags = _compute_alert_flags(record, today)

    # Compute 6-month timeline events
    timeline_events = _compute_timeline_events(record, today)

    return KeyLabsResponse(
        patient_id=patient_id,
        panels=panels,
        alert_flags=alert_flags,
        timeline_events=timeline_events,
    )


@router.get("/{patient_id}/safety", response_model=SafetyResponse)
def patient_safety(patient_id: str) -> SafetyResponse:
    """Pre-op safety flags — drug class risk classification."""
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result

    raw_flags = _classifier.generate_safety_flags(record.medications)

    flags: list[SafetyFlag] = []
    for rf in raw_flags:
        medications = [
            SafetyMedication(
                med_id=cm.medication.med_id,
                display=cm.medication.display,
                status=cm.medication.status,
                authored_on=cm.medication.authored_on,
                is_active=cm.is_active,
            )
            for cm in rf.medications
        ]
        flags.append(SafetyFlag(
            class_key=rf.class_key,
            label=rf.label,
            severity=rf.severity,
            surgical_note=rf.surgical_note,
            status=rf.status,
            medications=medications,
            protocol_note=PROTOCOL_NOTES.get(rf.class_key),
        ))

    active_flag_count = sum(1 for f in flags if f.status == "ACTIVE")
    historical_flag_count = sum(1 for f in flags if f.status == "HISTORICAL")

    return SafetyResponse(
        patient_id=patient_id,
        name=stats.name,
        flags=flags,
        active_flag_count=active_flag_count,
        historical_flag_count=historical_flag_count,
    )


@router.get("/{patient_id}/interactions", response_model=InteractionResponse)
def patient_interactions(patient_id: str) -> InteractionResponse:
    """Drug-drug interaction checker — flags known dangerous interactions between active medications."""
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result

    # Get safety flags to find active classes and their med names
    flags = _classifier.generate_safety_flags(record.medications)
    active_flags = [f for f in flags if f.status == "ACTIVE"]
    active_keys = [f.class_key for f in active_flags]

    # Build label map and med name map from flags
    label_map = {f.class_key: f.label for f in flags}
    med_map = {
        f.class_key: [cm.medication.display for cm in f.medications if cm.is_active]
        for f in active_flags
    }

    interactions = check_interactions(active_keys)

    results = [
        InteractionResult(
            drug_a=i.drug_a,
            drug_a_label=label_map.get(i.drug_a, i.drug_a),
            drug_b=i.drug_b,
            drug_b_label=label_map.get(i.drug_b, i.drug_b),
            severity=i.severity,
            mechanism=i.mechanism,
            clinical_effect=i.clinical_effect,
            management=i.management,
            drug_a_meds=med_map.get(i.drug_a, []),
            drug_b_meds=med_map.get(i.drug_b, []),
        )
        for i in interactions
    ]

    return InteractionResponse(
        patient_id=patient_id,
        active_class_keys=active_keys,
        interactions=results,
        contraindicated_count=sum(1 for r in results if r.severity == "contraindicated"),
        major_count=sum(1 for r in results if r.severity == "major"),
        moderate_count=sum(1 for r in results if r.severity == "moderate"),
        has_interactions=len(results) > 0,
    )


@router.get("/{patient_id}/surgical-risk", response_model=SurgicalRiskResponse)
def patient_surgical_risk(patient_id: str) -> SurgicalRiskResponse:
    """
    Deterministic surgical risk score for pre-op clearance review.

    This is intentionally rules-based and transparent. It is not a prediction
    model; it summarizes chart signals that should trigger surgeon/anesthesia
    review before proceeding.
    """
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result

    raw_flags = _classifier.generate_safety_flags(record.medications)
    active_flags = [f for f in raw_flags if f.status == "ACTIVE"]
    historical_flags = [f for f in raw_flags if f.status == "HISTORICAL"]
    active_critical = [f for f in active_flags if f.severity == "critical"]
    active_warning = [f for f in active_flags if f.severity == "warning"]
    historical_critical = [f for f in historical_flags if f.severity == "critical"]
    historical_warning = [f for f in historical_flags if f.severity == "warning"]

    if active_critical:
        medication_score = 35
    elif active_warning:
        medication_score = 22
    elif historical_critical:
        medication_score = 10
    elif historical_warning:
        medication_score = 5
    else:
        medication_score = 0

    medication_evidence: list[str] = []
    for flag in [*active_critical, *active_warning, *historical_critical, *historical_warning]:
        med_names = [
            cm.medication.display
            for cm in flag.medications
            if cm.is_active or flag.status == "HISTORICAL"
        ]
        suffix = f": {', '.join(med_names[:3])}" if med_names else ""
        medication_evidence.append(f"{flag.status.title()} {flag.label}{suffix}")

    medication_component = SurgicalRiskComponent(
        key="medications",
        label="Medication holds",
        score=medication_score,
        max_score=35,
        status=_component_status(
            medication_score,
            flagged=bool(active_critical),
            review=bool(active_warning or historical_critical or historical_warning),
        ),
        rationale=(
            "Active critical medication classes create a hold-level signal; "
            "active warning classes or relevant historical exposure create review-level signals."
        ),
        evidence=_limit_evidence(medication_evidence),
    )

    ranked_conditions = [r for r in _condition_ranker.rank_all(stats.condition_catalog) if r.is_active]
    high_conditions = [r for r in ranked_conditions if r.risk_category in HIGH_RISK_CONDITION_CATEGORIES]
    moderate_conditions = [r for r in ranked_conditions if r.risk_category in MODERATE_RISK_CONDITION_CATEGORIES]
    review_conditions = [r for r in ranked_conditions if r.risk_category in REVIEW_RISK_CONDITION_CATEGORIES]
    condition_score = min(
        30,
        len(high_conditions) * 12 + len(moderate_conditions) * 8 + len(review_conditions) * 4,
    )
    condition_component = SurgicalRiskComponent(
        key="conditions",
        label="Active condition burden",
        score=condition_score,
        max_score=30,
        status=_component_status(
            condition_score,
            flagged=bool(high_conditions),
            review=bool(moderate_conditions or review_conditions),
        ),
        rationale=(
            "Active cardiac or pulmonary conditions are hold-level; renal, hepatic, "
            "hematologic, vascular, metabolic, neurologic, immunologic, and oncologic "
            "conditions add review weight."
        ),
        evidence=_limit_evidence([
            f"{r.risk_label}: {r.display}"
            for r in [*high_conditions, *moderate_conditions, *review_conditions]
        ]),
    )

    today = datetime.now().date()
    lab_alerts = _compute_alert_flags(record, today)
    critical_labs = [flag for flag in lab_alerts if flag.severity == "critical"]
    warning_labs = [flag for flag in lab_alerts if flag.severity == "warning"]
    has_coagulation_data = any(obs.loinc_code in COAGULATION_LOINC_CODES for obs in record.observations)
    has_active_anticoagulant = any(flag.class_key == "anticoagulants" for flag in active_flags)

    if critical_labs:
        lab_score = 15
    elif warning_labs:
        lab_score = 10
    elif has_active_anticoagulant and not has_coagulation_data:
        lab_score = 8
    else:
        lab_score = 0

    lab_evidence = [flag.message for flag in [*critical_labs, *warning_labs]]
    if has_active_anticoagulant and not has_coagulation_data:
        lab_evidence.append("Active anticoagulant with no INR/PT/PTT observation found in the FHIR bundle")

    lab_component = SurgicalRiskComponent(
        key="labs",
        label="Lab readiness",
        score=lab_score,
        max_score=15,
        status=_component_status(
            lab_score,
            flagged=bool(critical_labs),
            review=bool(warning_labs or (has_active_anticoagulant and not has_coagulation_data)),
        ),
        rationale=(
            "Recent critical lab alerts are hold-level. Warning alerts or missing "
            "coagulation data for an active anticoagulant require review."
        ),
        evidence=_limit_evidence(lab_evidence),
    )

    high_allergies = [
        allergy for allergy in record.allergies if (allergy.criticality or "").lower() == "high"
    ]
    med_allergies = [
        allergy for allergy in record.allergies if "medication" in [c.lower() for c in allergy.categories]
    ]
    if high_allergies and med_allergies:
        allergy_score = 10
    elif high_allergies:
        allergy_score = 6
    elif record.allergies:
        allergy_score = 4
    else:
        allergy_score = 0

    allergy_component = SurgicalRiskComponent(
        key="allergies",
        label="Allergy criticality",
        score=allergy_score,
        max_score=10,
        status=_component_status(
            allergy_score,
            flagged=bool(high_allergies and med_allergies),
            review=bool(record.allergies),
        ),
        rationale=(
            "High-criticality medication allergies are hold-level; other documented "
            "allergies are review-level perioperative context."
        ),
        evidence=_limit_evidence([
            f"{allergy.code.label() or 'Allergy'} ({allergy.criticality or 'unknown criticality'})"
            for allergy in record.allergies
        ]),
    )

    interactions = check_interactions([f.class_key for f in active_flags])
    major_interactions = [
        interaction
        for interaction in interactions
        if interaction.severity in {"contraindicated", "major"}
    ]
    moderate_interactions = [interaction for interaction in interactions if interaction.severity == "moderate"]
    if major_interactions:
        interaction_score = 10
    elif moderate_interactions:
        interaction_score = 6
    else:
        interaction_score = 0

    interaction_component = SurgicalRiskComponent(
        key="interactions",
        label="Drug interaction screen",
        score=interaction_score,
        max_score=10,
        status=_component_status(
            interaction_score,
            flagged=bool(major_interactions),
            review=bool(moderate_interactions),
        ),
        rationale=(
            "Known active drug-class interactions add hold or review weight based "
            "on severity."
        ),
        evidence=_limit_evidence([
            f"{interaction.drug_a} + {interaction.drug_b}: {interaction.clinical_effect}"
            for interaction in [*major_interactions, *moderate_interactions]
        ]),
    )

    components = [
        medication_component,
        condition_component,
        lab_component,
        allergy_component,
        interaction_component,
    ]
    total_score = min(100, sum(component.score for component in components))

    if total_score >= 50:
        tier = "HIGH"
        disposition = "HOLD"
    elif total_score >= 25:
        tier = "MODERATE"
        disposition = "REVIEW"
    else:
        tier = "LOW"
        disposition = "CLEARED"

    return SurgicalRiskResponse(
        patient_id=patient_id,
        name=stats.name,
        score=total_score,
        max_score=100,
        tier=tier,
        disposition=disposition,
        rule_version="preop-rules-v1",
        components=components,
        methodology_notes=[
            "Score is deterministic and derived only from parsed FHIR bundle fields.",
            "Medication holds contribute up to 35 points; active critical classes dominate this component.",
            "Active surgical condition categories contribute up to 30 points using the static condition ranker.",
            "Labs, allergies, and known drug-class interactions add readiness and anesthesia review signals.",
            "This is a briefing and triage aid, not an autonomous clearance decision.",
        ],
    )


@router.get("/{patient_id}/immunizations", response_model=ImmunizationResponse)
def patient_immunizations(patient_id: str) -> ImmunizationResponse:
    """Immunization history — all vaccines with dates."""
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result

    # Sort by occurrence_dt descending, nulls last
    immunizations_sorted = sorted(
        record.immunizations,
        key=lambda imm: imm.occurrence_dt or datetime.min,
        reverse=True,
    )

    items: list[ImmunizationItem] = [
        ImmunizationItem(
            imm_id=imm.imm_id,
            display=imm.display or "",
            cvx_code=imm.cvx_code or "",
            status=imm.status or "",
            occurrence_dt=imm.occurrence_dt,
        )
        for imm in immunizations_sorted
    ]

    # Unique vaccines — dedup by display name, sorted alphabetically
    seen: set[str] = set()
    unique_vaccines: list[str] = []
    for imm in immunizations_sorted:
        name = imm.display or ""
        if name and name not in seen:
            seen.add(name)
            unique_vaccines.append(name)
    unique_vaccines.sort()

    return ImmunizationResponse(
        patient_id=patient_id,
        name=stats.name,
        total_count=len(items),
        immunizations=items,
        unique_vaccines=unique_vaccines,
    )


@router.get("/{patient_id}/condition-acuity", response_model=ConditionAcuityResponse)
def condition_acuity(patient_id: str) -> ConditionAcuityResponse:
    """Active conditions ranked by surgical risk category."""
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result

    all_ranked = _condition_ranker.rank_all(stats.condition_catalog)

    ranked_active = [r for r in all_ranked if r.is_active]
    ranked_resolved = [r for r in all_ranked if not r.is_active]

    def to_item(r: "RankedCondition") -> RankedConditionItem:  # noqa: F821
        from datetime import datetime
        onset_dt: datetime | None = None
        if r.onset_dt is not None:
            try:
                onset_dt = datetime.fromisoformat(r.onset_dt)
            except ValueError:
                onset_dt = None
        return RankedConditionItem(
            condition_id=r.condition_id,
            display=r.display,
            clinical_status=r.clinical_status,
            onset_dt=onset_dt,
            risk_category=r.risk_category,
            risk_rank=r.risk_rank,
            risk_label=r.risk_label,
            is_active=r.is_active,
        )

    return ConditionAcuityResponse(
        patient_id=patient_id,
        name=stats.name,
        active_count=len(ranked_active),
        resolved_count=len(ranked_resolved),
        ranked_active=[to_item(r) for r in ranked_active],
        ranked_resolved=[to_item(r) for r in ranked_resolved],
    )


@router.get("/{patient_id}/procedures", response_model=ProceduresResponse)
def patient_procedures(patient_id: str) -> ProceduresResponse:
    """Full procedure history sorted by date descending."""
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result

    # Sort by performed_start descending; procedures with no date go last
    procedures_sorted = sorted(
        record.procedures,
        key=lambda p: p.performed_period.start if (p.performed_period and p.performed_period.start) else datetime.min,
        reverse=True,
    )

    items: list[ProcedureItem] = [
        ProcedureItem(
            procedure_id=p.procedure_id,
            display=p.code.label(),
            status=p.status or "",
            performed_start=p.performed_period.start if p.performed_period else None,
            performed_end=p.performed_period.end if p.performed_period else None,
            reason_display=p.reason_display or "",
            body_site="",
        )
        for p in procedures_sorted
    ]

    return ProceduresResponse(
        patient_id=patient_id,
        name=stats.name,
        total_count=len(items),
        procedures=items,
    )


@router.get("/{patient_id}/encounters/{encounter_id}/raw")
def encounter_raw(patient_id: str, encounter_id: str) -> dict:
    """Return the raw FHIR Encounter resource JSON from the bundle file."""
    path = path_from_patient_id(patient_id)
    if path is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    with open(path) as f:
        bundle = json.load(f)

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Encounter":
            resource_id = resource.get("id", "")
            full_url = entry.get("fullUrl", "")
            if resource_id == encounter_id or full_url.endswith(encounter_id):
                return resource

    raise HTTPException(status_code=404, detail=f"Encounter not found: {encounter_id}")


# ---------------------------------------------------------------------------
# Care Journey (multi-lane Gantt timeline from SOF warehouse)
# ---------------------------------------------------------------------------

def _patient_fhir_uuid(patient_id: str) -> str | None:
    """Look up the FHIR patient resource UUID from the bundle file.

    The filename stem UUID is the *bundle* ID, not the patient resource ID.
    We must open the bundle and find the Patient entry's fullUrl.
    """
    path = path_from_patient_id(patient_id)
    if path is None:
        return None
    with open(path) as f:
        bundle = json.load(f)
    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Patient":
            full_url = entry.get("fullUrl", "")
            # fullUrl is like "urn:uuid:<uuid>"
            if full_url.startswith("urn:uuid:"):
                return full_url.removeprefix("urn:uuid:")
            return resource.get("id", "")
    return None


def _sof_db_path() -> Path:
    from api.core.sof_tools import DEFAULT_SOF_DB
    return DEFAULT_SOF_DB


def _dt_to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def _dt_sort_key(value: datetime | None) -> str:
    return value.isoformat() if value else ""


def _record_medication_episodes(record) -> list[MedicationEpisodeItem]:
    """Build point-in-time medication episodes from the parsed FHIR bundle.

    The SOF-derived ``medication_episode`` table has better longitudinal
    grouping when the patient is present in the warehouse. For patients outside
    that materialized subset, use only fields present in the bundle rather than
    leaving the patient-level journey blank.
    """
    items: list[MedicationEpisodeItem] = []
    for med in sorted(record.medications, key=lambda m: _dt_sort_key(m.authored_on)):
        classes = _classifier.classify_medication(med)
        is_active = med.status in ("active", "on-hold")
        authored_on = _dt_to_iso(med.authored_on)
        items.append(MedicationEpisodeItem(
            episode_id=med.med_id,
            display=med.display or "Medication request",
            drug_class=classes[0] if classes else None,
            status=med.status or "",
            is_active=is_active,
            start_date=authored_on,
            end_date=None if is_active else authored_on,
            duration_days=None,
            request_count=1,
            reason=med.reason_display or None,
        ))
    return items


def _record_condition_episodes(record) -> list[ConditionEpisodeItem]:
    items: list[ConditionEpisodeItem] = []
    for condition in sorted(record.conditions, key=lambda c: _dt_sort_key(c.onset_dt)):
        end_dt = condition.abatement_dt
        if end_dt is None and not condition.is_active:
            end_dt = condition.recorded_dt
        items.append(ConditionEpisodeItem(
            condition_id=condition.condition_id,
            display=condition.code.label(),
            clinical_status=condition.clinical_status or "",
            onset_date=_dt_to_iso(condition.onset_dt),
            end_date=_dt_to_iso(end_dt),
            is_active=condition.is_active,
        ))
    return items


def _record_encounter_markers(record) -> list[EncounterMarker]:
    cond_index = {c.condition_id: c for c in record.conditions}
    markers: list[EncounterMarker] = []
    for encounter in sorted(record.encounters, key=lambda e: _dt_sort_key(e.period.start)):
        diagnoses = [
            condition.code.label()
            for condition_id in encounter.linked_conditions
            if (condition := cond_index.get(condition_id)) is not None
        ]
        markers.append(EncounterMarker(
            encounter_id=encounter.encounter_id,
            class_code=encounter.class_code or "",
            type_text=encounter.encounter_type or "",
            start=_dt_to_iso(encounter.period.start),
            reason_display=encounter.reason_display or "",
            diagnoses=diagnoses,
        ))
    return markers


def _record_procedure_markers(record) -> list[ProcedureMarker]:
    markers: list[ProcedureMarker] = []
    for procedure in sorted(
        record.procedures,
        key=lambda p: _dt_sort_key(p.performed_period.start if p.performed_period else None),
    ):
        period = procedure.performed_period
        markers.append(ProcedureMarker(
            procedure_id=procedure.procedure_id,
            display=procedure.code.label(),
            start=_dt_to_iso(period.start if period else None),
            end=_dt_to_iso(period.end if period else None),
            reason_display=procedure.reason_display or "",
        ))
    return markers


def _record_diagnostic_reports(record) -> list[DiagnosticReportItem]:
    return [
        DiagnosticReportItem(
            report_id=report.report_id,
            display=report.code.label(),
            category=report.category or "",
            date=_dt_to_iso(report.effective_dt),
            result_count=len(report.result_refs),
        )
        for report in sorted(record.diagnostic_reports, key=lambda r: _dt_sort_key(r.effective_dt))
    ]


@router.get("/{patient_id}/care-journey", response_model=CareJourneyResponse)
def get_care_journey(patient_id: str) -> CareJourneyResponse:
    """Return medication episodes, conditions, and encounters for the Gantt timeline."""
    import sqlite3

    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, stats = result

    fhir_uuid = _patient_fhir_uuid(patient_id)
    patient_ref = f"urn:uuid:{fhir_uuid}" if fhir_uuid else None
    name = stats.name

    medication_episodes: list[MedicationEpisodeItem] = []
    conditions: list[ConditionEpisodeItem] = []
    encounters: list[EncounterMarker] = []

    db_path = _sof_db_path()
    if patient_ref and db_path.exists():
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        conn.row_factory = sqlite3.Row
        try:
            # Medication episodes
            med_rows = conn.execute(
                """SELECT episode_id, display, drug_class, latest_status, is_active,
                          start_date, end_date, duration_days, request_count
                   FROM medication_episode
                   WHERE patient_ref = ?
                   ORDER BY start_date""",
                (patient_ref,),
            ).fetchall()

            medication_episodes = [
                MedicationEpisodeItem(
                    episode_id=r["episode_id"],
                    display=r["display"],
                    drug_class=r["drug_class"],
                    status=r["latest_status"],
                    is_active=bool(r["is_active"]),
                    start_date=r["start_date"],
                    end_date=r["end_date"],
                    duration_days=r["duration_days"],
                    request_count=r["request_count"],
                )
                for r in med_rows
            ]

            # Conditions with onset dates
            cond_rows = conn.execute(
                """SELECT id, display, clinical_status, onset_date,
                          CASE WHEN clinical_status NOT IN ('active', 'recurrence', 'relapse')
                               THEN recorded_date END AS proxy_end_date
                   FROM condition
                   WHERE patient_ref = ? AND onset_date IS NOT NULL
                   ORDER BY onset_date""",
                (patient_ref,),
            ).fetchall()

            conditions = [
                ConditionEpisodeItem(
                    condition_id=r["id"],
                    display=r["display"],
                    clinical_status=r["clinical_status"],
                    onset_date=r["onset_date"],
                    end_date=r["proxy_end_date"],
                    is_active=r["clinical_status"] in ("active", "recurrence", "relapse"),
                )
                for r in cond_rows
            ]

            # Encounters with linked diagnoses
            enc_rows = conn.execute(
                """SELECT e.id, e.class_code, e.type_text, e.period_start, e.reason_text,
                          GROUP_CONCAT(c.display, '||') AS dx_list
                   FROM encounter e
                   LEFT JOIN condition c ON c.encounter_ref = 'urn:uuid:' || e.id
                   WHERE e.patient_ref = ?
                   GROUP BY e.id
                   ORDER BY e.period_start""",
                (patient_ref,),
            ).fetchall()

            encounters = [
                EncounterMarker(
                    encounter_id=r["id"],
                    class_code=r["class_code"] or "",
                    type_text=r["type_text"] or "",
                    start=r["period_start"],
                    reason_display=r["reason_text"] or "",
                    diagnoses=[d.strip() for d in r["dx_list"].split("||") if d.strip()] if r["dx_list"] else [],
                )
                for r in enc_rows
            ]

        finally:
            conn.close()

    if not medication_episodes:
        medication_episodes = _record_medication_episodes(record)
    if not conditions:
        conditions = _record_condition_episodes(record)
    if not encounters:
        encounters = _record_encounter_markers(record)

    procedures = _record_procedure_markers(record)
    diagnostic_reports = _record_diagnostic_reports(record)

    # Compute date bounds and distinct drug classes
    all_dates: list[str] = []
    for m in medication_episodes:
        if m.start_date:
            all_dates.append(m.start_date)
        if m.end_date:
            all_dates.append(m.end_date)
    for c in conditions:
        if c.onset_date:
            all_dates.append(c.onset_date)
    for e in encounters:
        if e.start:
            all_dates.append(e.start)
    for p in procedures:
        if p.start:
            all_dates.append(p.start)
    for dr in diagnostic_reports:
        if dr.date:
            all_dates.append(dr.date)

    earliest = min(all_dates) if all_dates else None
    latest = max(all_dates) if all_dates else None

    drug_classes = sorted({
        m.drug_class for m in medication_episodes if m.drug_class
    })

    return CareJourneyResponse(
        patient_id=patient_id,
        name=name,
        earliest_date=earliest,
        latest_date=latest,
        medication_episodes=medication_episodes,
        conditions=conditions,
        encounters=encounters,
        procedures=procedures,
        diagnostic_reports=diagnostic_reports,
        drug_classes_present=drug_classes,
    )
