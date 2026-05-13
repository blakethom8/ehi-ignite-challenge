"""
/api/patients — patient listing and detail endpoints.

This module is a thin orchestrator. The bulk of the handlers live in three
focused sub-routers:

- ``patients_core``    — list/loaded/overview/immunizations/conditions/procedures
- ``patients_timeline`` — timeline, encounter detail, clinical notes, raw
                          encounter
- ``patients_risk``    — risk-summary, key-labs, safety, interactions,
                          surgical-risk

Shared constants and small helpers live in ``_patients_shared``.

The ``/care-journey`` handler is defined here (rather than in the timeline
sub-router) because existing tests monkeypatch
``api.routers.patients.load_patient`` and related globals before calling
``get_care_journey`` directly — keeping the function defined in this module
preserves that patch surface without modifying the tests.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request

from api.core.loader import load_active_published_run, load_patient
from api.models import (
    CareJourneyResponse,
    ConditionEpisodeItem,
    DiagnosticReportItem,
    EncounterMarker,
    MedicationEpisodeItem,
    ProcedureMarker,
)
from api.routers._patients_shared import (
    ADMIN_TYPES,
    BILLING_TYPES,
    DEMO_PATIENT_IDS,
    DEMO_PATIENT_LIMIT,
    _authorized_patient_id,
    _classifier,
)
from api.routers.patients_core import (
    _cached_patient_list,
    _curated_demo_patients,
    _demo_patient_items,
    router as _core_router,
)
from api.routers.patients_risk import (
    _cached_patient_risk_summary,
    # ``_interpret_lab_value`` is re-exported because
    # ``api/tests/test_key_labs.py`` imports it from this module.
    _interpret_lab_value,
    router as _risk_router,
)
from api.routers.patients_timeline import (
    _clinical_notes_for_patient,
    router as _timeline_router,
)


# ---------------------------------------------------------------------------
# Care Journey (multi-lane Gantt timeline from SOF warehouse)
# ---------------------------------------------------------------------------

def _patient_fhir_uuid(patient_id: str) -> str | None:
    """Look up the FHIR patient resource UUID from the bundle file.

    The filename stem UUID is the *bundle* ID, not the patient resource ID.
    We must open the bundle and find the Patient entry's fullUrl.
    """
    from api.core.loader import load_raw_bundle
    bundle = load_raw_bundle(patient_id)
    if bundle is None:
        return None
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
    def note_preview(text: str) -> str:
        compact = " ".join(text.split())
        if len(compact) > 260:
            return f"{compact[:260].rstrip()}..."
        return compact

    return [
        DiagnosticReportItem(
            report_id=report.report_id,
            display=report.code.label(),
            category=report.category or "",
            date=_dt_to_iso(report.effective_dt),
            result_count=len(report.result_refs),
            has_presented_form=report.has_presented_form,
            note_preview=note_preview(report.presented_form_text),
        )
        for report in sorted(record.diagnostic_reports, key=lambda r: _dt_sort_key(r.effective_dt))
    ]


# ---------------------------------------------------------------------------
# Router assembly
# ---------------------------------------------------------------------------

router = APIRouter()
router.include_router(_core_router)
router.include_router(_timeline_router)
router.include_router(_risk_router)


@router.get("/patients/{patient_id}/care-journey", response_model=CareJourneyResponse, tags=["patients"])
def get_care_journey(patient_id: str, request: Request) -> CareJourneyResponse:
    """Return medication episodes, conditions, and encounters for the Gantt timeline."""
    import sqlite3

    requested_patient_id = patient_id
    patient_id = _authorized_patient_id(request, patient_id)
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {requested_patient_id}")

    record, stats = result

    active_published_run = load_active_published_run(patient_id)
    fhir_uuid = None if active_published_run is not None else _patient_fhir_uuid(patient_id)
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
    clinical_notes = _clinical_notes_for_patient(patient_id, record)

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
    for note in clinical_notes:
        if note.date:
            all_dates.append(note.date)

    earliest = min(all_dates) if all_dates else None
    latest = max(all_dates) if all_dates else None

    drug_classes = sorted({
        m.drug_class for m in medication_episodes if m.drug_class
    })

    return CareJourneyResponse(
        patient_id=requested_patient_id,
        name=name,
        earliest_date=earliest,
        latest_date=latest,
        medication_episodes=medication_episodes,
        conditions=conditions,
        encounters=encounters,
        procedures=procedures,
        diagnostic_reports=diagnostic_reports,
        clinical_notes=clinical_notes,
        drug_classes_present=drug_classes,
    )


__all__ = [
    "router",
    "get_care_journey",
    "BILLING_TYPES",
    "ADMIN_TYPES",
    "DEMO_PATIENT_LIMIT",
    "DEMO_PATIENT_IDS",
    "_authorized_patient_id",
    "_cached_patient_list",
    "_cached_patient_risk_summary",
    "_curated_demo_patients",
    "_demo_patient_items",
    "_interpret_lab_value",
    "_patient_fhir_uuid",
    "_sof_db_path",
    "load_active_published_run",
    "load_patient",
]
