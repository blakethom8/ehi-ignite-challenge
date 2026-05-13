"""
/api/patients — core listing, overview, and chart-summary endpoints.

This sub-router is mounted by ``api.routers.patients`` (the orchestrator)
which provides the ``/patients`` prefix and ``patients`` tag.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from functools import lru_cache

from fastapi import APIRouter, HTTPException, Request

from api.core.aggregation import list_upload_workspaces
from api.core.auth import (
    DEMO_PATIENTS,
    authorize_patient_access,
    demo_patient_label,
    require_access_session,
)
from api.core.condition_ranker import ConditionRanker
from api.core.loader import (
    data_dir,
    list_patient_files,
    load_patient,
    patient_display_name,
    patient_id_from_path,
)
from api.models import (
    CareTeamSummaryItem,
    ConditionAcuityResponse,
    ConditionRow,
    EncounterTypeSummary,
    ImmunizationItem,
    ImmunizationResponse,
    MedRow,
    PatientListItem,
    PatientOverview,
    ProcedureItem,
    ProceduresResponse,
    RankedConditionItem,
    ResourceTypeCount,
    SiteOfServiceSummaryItem,
)
from api.routers._patients_shared import (
    ADMIN_TYPES,
    BILLING_TYPES,
    DEMO_PATIENT_IDS,
    DEMO_PATIENT_LIMIT,
    _authorized_patient_id,
    _clean_network_label,
    _encounter_date_sort,
    _fallback_provider_label,
    _network_specialty,
    logger,
)

router = APIRouter(prefix="/patients", tags=["patients"])

_condition_ranker = ConditionRanker()


def _care_network_summary(record) -> tuple[list[CareTeamSummaryItem], list[SiteOfServiceSummaryItem]]:
    provider_rows: dict[str, dict] = {}
    site_rows: dict[str, dict] = {}

    for enc in record.encounters:
        class_code = enc.class_code or "Unknown"
        start = enc.period.start
        site_name = _clean_network_label(enc.provider_org) or "Unknown organization"
        provider_name = _clean_network_label(enc.practitioner_name) or _fallback_provider_label(
            site_name,
            enc.encounter_type or "",
        )

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
            specialty=_network_specialty(name, sorted(row["organizations"]), dict(row["class_breakdown"])),
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
            specialty=_network_specialty(name, sorted(row["providers"]), dict(row["class_breakdown"])),
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


@router.get("", response_model=list[PatientListItem])
def list_patients(request: Request) -> list[PatientListItem]:
    session = require_access_session(request)
    all_synthea_items = _cached_patient_list()
    if session.is_demo:
        return _demo_patient_items(all_synthea_items)
    return list_upload_workspaces(user_id=session.user_id)


def _demo_patient_items(items: list[PatientListItem]) -> list[PatientListItem]:
    by_id = {item.id: item for item in items}
    demo_items: list[PatientListItem] = []
    for demo in DEMO_PATIENTS:
        base = by_id.get(demo.actual_patient_id)
        if base is None:
            continue
        demo_items.append(
            base.model_copy(
                update={
                    "id": demo.alias_id,
                    "name": demo.name,
                    "workspace_type": "demo",
                }
            )
        )
    return demo_items


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
        logger.exception("patients: corpus catalog load failed; using filename fallback")
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


@router.get("/loaded", response_model=list[PatientListItem])
def list_patients_with_stats(request: Request) -> list[PatientListItem]:
    """
    Return patient list WITH stats computed. Loads all bundles — slow for
    large corpora. Use sparingly (corpus view, sorting/filtering).
    """
    session = require_access_session(request)
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
    if session.is_demo:
        return _demo_patient_items(items)
    return items


@router.get("/{patient_id}/overview", response_model=PatientOverview)
def patient_overview(patient_id: str, request: Request) -> PatientOverview:
    """Full patient overview — demographics, resource counts, conditions, meds."""
    requested_patient_id = patient_id
    patient_id = authorize_patient_access(require_access_session(request), patient_id)
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {requested_patient_id}")

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
        id=requested_patient_id,
        name=demo_patient_label(requested_patient_id) if requested_patient_id != patient_id else stats.name,
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


@router.get("/{patient_id}/immunizations", response_model=ImmunizationResponse)
def patient_immunizations(patient_id: str, request: Request) -> ImmunizationResponse:
    """Immunization history — all vaccines with dates."""
    requested_patient_id = patient_id
    patient_id = _authorized_patient_id(request, patient_id)
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
        patient_id=requested_patient_id,
        name=stats.name,
        total_count=len(items),
        immunizations=items,
        unique_vaccines=unique_vaccines,
    )


@router.get("/{patient_id}/condition-acuity", response_model=ConditionAcuityResponse)
def condition_acuity(patient_id: str, request: Request) -> ConditionAcuityResponse:
    """Active conditions ranked by surgical risk category."""
    requested_patient_id = patient_id
    patient_id = _authorized_patient_id(request, patient_id)
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
        patient_id=requested_patient_id,
        name=stats.name,
        active_count=len(ranked_active),
        resolved_count=len(ranked_resolved),
        ranked_active=[to_item(r) for r in ranked_active],
        ranked_resolved=[to_item(r) for r in ranked_resolved],
    )


@router.get("/{patient_id}/procedures", response_model=ProceduresResponse)
def patient_procedures(patient_id: str, request: Request) -> ProceduresResponse:
    """Full procedure history sorted by date descending."""
    requested_patient_id = patient_id
    patient_id = _authorized_patient_id(request, patient_id)
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
        patient_id=requested_patient_id,
        name=stats.name,
        total_count=len(items),
        procedures=items,
    )
