"""
/api/patients — timeline, encounter, clinical-notes, and care-journey endpoints.

This sub-router is mounted by ``api.routers.patients`` (the orchestrator)
which provides the ``/patients`` prefix and ``patients`` tag.
"""

from __future__ import annotations

import re
from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request

from api.core.auth import (
    authorize_patient_access,
    demo_patient_label,
    require_access_session,
)
from api.core.loader import (
    load_active_published_run,
    load_patient,
    load_raw_bundle,
)
from api.models import (
    ClinicalNoteItem,
    ClinicalNotesResponse,
    ConditionDetail,
    EncounterDetail,
    EncounterEvent,
    MedicationDetail,
    ObservationDetail,
    ProcedureDetail,
    TimelineResponse,
)
from api.routers._patients_shared import (
    _authorized_patient_id,
    _encounter_semantics,
)

router = APIRouter(prefix="/patients", tags=["patients"])


def _dt_to_iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


# ---------------------------------------------------------------------------
# Published-chart artifact helpers
# ---------------------------------------------------------------------------

def _published_safe_id(prefix: str, value: object, index: int) -> str:
    raw = str(value or "").strip() or f"{prefix}-{index}"
    return re.sub(r"[^A-Za-z0-9_.-]+", "-", raw).strip(".-")[:160] or f"{prefix}-{index}"


def _active_published_artifacts(patient_id: str) -> dict:
    run = load_active_published_run(patient_id)
    if not isinstance(run, dict):
        return {}
    candidate = run.get("candidate_record")
    if not isinstance(candidate, dict):
        return {}
    artifacts = candidate.get("clinical_artifacts")
    return artifacts if isinstance(artifacts, dict) else {}


def _note_preview(text: str, limit: int = 280) -> str:
    compact = " ".join(str(text or "").split())
    if len(compact) > limit:
        return f"{compact[:limit].rstrip()}..."
    return compact


def _note_document_type(note: dict) -> str:
    section = str(note.get("section_title") or "").strip()
    if section:
        return section
    resource_type = str(note.get("resource_type") or "").strip()
    content_type = str(note.get("attachment_content_type") or "").strip()
    if resource_type == "DiagnosticReport":
        return "Diagnostic report narrative"
    if resource_type == "Composition":
        return "Clinical document section"
    if resource_type == "DocumentReference":
        return "Source document description"
    if content_type:
        return content_type
    return f"{resource_type} note" if resource_type else "Clinical note"


def _clinical_notes_for_patient(patient_id: str, record) -> list[ClinicalNoteItem]:
    artifacts = _active_published_artifacts(patient_id)
    raw_notes = [note for note in artifacts.get("clinical_notes") or [] if isinstance(note, dict)]
    if not raw_notes:
        return []

    encounter_lookup: dict[tuple[str, str], str] = {}
    for idx, enc in enumerate(artifacts.get("encounters") or []):
        if not isinstance(enc, dict):
            continue
        source_id = str(enc.get("source_id") or "")
        raw_id = str(enc.get("id") or "")
        if source_id and raw_id:
            encounter_lookup[(source_id, raw_id)] = _published_safe_id("enc", f"{source_id}-{raw_id}", idx)

    notes: list[ClinicalNoteItem] = []
    for idx, note in enumerate(raw_notes):
        source_id = str(note.get("source_id") or "")
        raw_encounter_id = str(note.get("encounter_id") or "")
        linked_encounter_id = encounter_lookup.get((source_id, raw_encounter_id)) if raw_encounter_id else None
        linked_encounter = record.encounter_index.get(linked_encounter_id) if linked_encounter_id else None
        text = str(note.get("text") or "")
        organization = str(
            note.get("organization")
            or note.get("author_organization")
            or (linked_encounter.provider_org if linked_encounter else "")
            or note.get("source_label")
            or ""
        )
        provider = str(note.get("author") or (linked_encounter.practitioner_name if linked_encounter else "") or "")
        note_id = _published_safe_id(
            "note",
            f"{source_id}-{note.get('resource_type')}-{note.get('resource_id')}-{note.get('note_index', idx)}",
            idx,
        )
        notes.append(
            ClinicalNoteItem(
                note_id=note_id,
                source_id=source_id,
                source_label=str(note.get("source_label") or source_id or "Published chart"),
                resource_type=str(note.get("resource_type") or ""),
                resource_id=str(note.get("resource_id") or ""),
                note_index=int(note.get("note_index") or 0),
                date=note.get("date") if isinstance(note.get("date"), str) else None,
                author=provider,
                organization=organization,
                document_type=str(note.get("document_type") or _note_document_type(note)),
                category=str(note.get("category") or note.get("resource_type") or ""),
                encounter_id=raw_encounter_id or None,
                linked_encounter_id=linked_encounter_id,
                linked_encounter_type=linked_encounter.encounter_type if linked_encounter else "",
                linked_encounter_start=_dt_to_iso(linked_encounter.period.start) if linked_encounter else None,
                provider=provider,
                site=linked_encounter.provider_org if linked_encounter else organization,
                section_title=str(note.get("section_title") or ""),
                attachment_content_type=str(note.get("attachment_content_type") or ""),
                preview=_note_preview(text),
                text=text,
            )
        )

    notes.sort(key=lambda item: item.date or item.linked_encounter_start or "", reverse=True)
    return notes


@router.get("/{patient_id}/timeline", response_model=TimelineResponse)
def patient_timeline(patient_id: str, request: Request) -> TimelineResponse:
    """Encounter timeline — chronological list with linked resource counts."""
    requested_patient_id = patient_id
    patient_id = authorize_patient_access(require_access_session(request), patient_id)
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {requested_patient_id}")

    record, stats = result

    encounters_sorted = sorted(
        record.encounters,
        key=lambda e: e.period.start or datetime.min,
    )

    year_counts: dict[str, int] = defaultdict(int)
    events: list[EncounterEvent] = []
    notes_by_encounter: dict[str, int] = defaultdict(int)
    for note in _clinical_notes_for_patient(patient_id, record):
        if note.linked_encounter_id:
            notes_by_encounter[note.linked_encounter_id] += 1

    for enc in encounters_sorted:
        if enc.period.start:
            year_counts[str(enc.period.start.year)] += 1
        specialty, source_category, provenance_label = _encounter_semantics(enc)

        events.append(EncounterEvent(
            encounter_id=enc.encounter_id,
            class_code=enc.class_code or "",
            encounter_type=enc.encounter_type or "",
            reason_display=enc.reason_display or "",
            start=enc.period.start,
            end=enc.period.end,
            provider_org=enc.provider_org or "",
            practitioner_name=enc.practitioner_name or "",
            specialty=specialty,
            source_category=source_category,
            provenance_label=provenance_label,
            linked_observation_count=len(enc.linked_observations),
            linked_condition_count=len(enc.linked_conditions),
            linked_procedure_count=len(enc.linked_procedures),
            linked_medication_count=len(enc.linked_medications),
            linked_clinical_note_count=notes_by_encounter.get(enc.encounter_id, 0),
        ))

    return TimelineResponse(
        patient_id=requested_patient_id,
        name=demo_patient_label(requested_patient_id) if requested_patient_id != patient_id else stats.name,
        encounters=events,
        year_counts=dict(year_counts),
    )


@router.get("/{patient_id}/encounters/{encounter_id}", response_model=EncounterDetail)
def encounter_detail(patient_id: str, encounter_id: str, request: Request) -> EncounterDetail:
    """Full detail for a single encounter — all linked resources."""
    patient_id = _authorized_patient_id(request, patient_id)
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    record, _ = result
    enc = record.encounter_index.get(encounter_id)
    if enc is None:
        raise HTTPException(status_code=404, detail=f"Encounter not found: {encounter_id}")
    specialty, source_category, provenance_label = _encounter_semantics(enc)
    clinical_notes = [
        note for note in _clinical_notes_for_patient(patient_id, record)
        if note.linked_encounter_id == encounter_id
    ]

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
        specialty=specialty,
        source_category=source_category,
        provenance_label=provenance_label,
        observations=observations,
        conditions=conditions,
        procedures=procedures,
        medications=medications,
        diagnostic_report_count=len(enc.linked_diagnostic_reports),
        imaging_study_count=len(enc.linked_imaging_studies),
        clinical_notes=clinical_notes,
    )


@router.get("/{patient_id}/clinical-notes", response_model=ClinicalNotesResponse)
def patient_clinical_notes(patient_id: str, request: Request) -> ClinicalNotesResponse:
    """Return narrative note artifacts from the active published chart snapshot."""
    requested_patient_id = patient_id
    patient_id = _authorized_patient_id(request, patient_id)
    result = load_patient(patient_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")
    record, stats = result
    notes = _clinical_notes_for_patient(patient_id, record)
    return ClinicalNotesResponse(
        patient_id=requested_patient_id,
        name=stats.name,
        total_count=len(notes),
        notes=notes,
    )


@router.get("/{patient_id}/encounters/{encounter_id}/raw")
def encounter_raw(patient_id: str, encounter_id: str, request: Request) -> dict:
    """Return the raw FHIR Encounter resource JSON from the bundle file."""
    patient_id = _authorized_patient_id(request, patient_id)
    bundle = load_raw_bundle(patient_id)
    if bundle is None:
        raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")

    for entry in bundle.get("entry", []):
        resource = entry.get("resource", {})
        if resource.get("resourceType") == "Encounter":
            resource_id = resource.get("id", "")
            full_url = entry.get("fullUrl", "")
            if resource_id == encounter_id or full_url.endswith(encounter_id):
                return resource

    raise HTTPException(status_code=404, detail=f"Encounter not found: {encounter_id}")


# The /care-journey handler lives on the orchestrator (api.routers.patients)
# rather than this sub-router because existing tests monkeypatch
# ``api.routers.patients.load_patient`` (and friends) before invoking
# ``get_care_journey`` directly. Keeping the function defined in that module
# preserves the patch surface.
