"""/api/patient-context — patient-facing guided context intake."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.core.auth import authorize_patient_access, require_access_session
from api.core.patient_context import (
    PatientContextConfigurationError,
    add_turn,
    create_session,
    export_markdown,
    get_session,
    private_cedars_available,
)
from api.models import (
    PatientContextExportResponse,
    PatientContextSessionCreateRequest,
    PatientContextSessionResponse,
    PatientContextTurnRequest,
    PatientContextTurnResponse,
)


router = APIRouter(prefix="/patient-context", tags=["patient-context"])


@router.get("/status")
def patient_context_status() -> dict:
    return {
        "private_blake_cedars_available": private_cedars_available(),
        "storage": "local-files",
    }


@router.post("/sessions", response_model=PatientContextSessionResponse)
def create_patient_context_session(
    payload: PatientContextSessionCreateRequest,
    request: Request,
) -> PatientContextSessionResponse:
    resolved_patient_id = authorize_patient_access(
        require_access_session(request),
        payload.patient_id,
        event_type="patient_context.session_created",
    )
    return create_session(resolved_patient_id, payload.source_mode)


@router.get("/sessions/{session_id}", response_model=PatientContextSessionResponse)
def get_patient_context_session(session_id: str, request: Request) -> PatientContextSessionResponse:
    require_access_session(request)
    try:
        return get_session(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/turn", response_model=PatientContextTurnResponse)
def patient_context_turn(
    session_id: str,
    payload: PatientContextTurnRequest,
    request: Request,
) -> PatientContextTurnResponse:
    require_access_session(request)
    try:
        return add_turn(session_id, payload.message, payload.selected_gap_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except PatientContextConfigurationError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc


@router.post("/sessions/{session_id}/export", response_model=PatientContextExportResponse)
def export_patient_context(session_id: str, request: Request) -> PatientContextExportResponse:
    require_access_session(request)
    try:
        return export_markdown(session_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


# ---------------------------------------------------------------------------
# T8c read endpoints — drive the merged-record UI panels
# ---------------------------------------------------------------------------


@router.get("/{patient_id}/augmentation")
def patient_context_augmentation(patient_id: str, request: Request) -> dict:
    """Bundle the three T8 augmentation artifacts for the merged-record UI.

    Returns a single payload so the React panel can fetch in one round
    trip:

    - ``patient_voice``: ``{summary, citations, generated_at}`` or null.
    - ``episode_briefs``: list of ``{episode_id, type, period_start,
      period_end, one_liner}`` derived from ``episodes.json`` + each
      episode's ``current.json`` Summary section.
    - ``caveats``: list of ``{fact_path, verdict, confidence,
      rationale, dissenting_sources, blocker}`` parsed from
      ``caveats.json``.

    All three default to empty-but-shaped responses when their
    on-disk artifact is missing, so the UI renders a single shape.
    """
    require_access_session(request)
    from api.core.context_builder import (
        _load_caveats,
        _load_episode_briefs,
        _load_patient_voice_context,
    )

    voice = _load_patient_voice_context(patient_id)
    briefs = _load_episode_briefs(patient_id)
    caveats = _load_caveats(patient_id)
    return {
        "patient_voice": (
            {"summary": voice.summary, "citations": list(voice.citations)}
            if voice is not None
            else None
        ),
        "episode_briefs": [
            {
                "episode_id": b.episode_id,
                "type": b.type,
                "period_start": b.period_start,
                "period_end": b.period_end,
                "one_liner": b.one_liner,
            }
            for b in briefs
        ],
        "caveats": [
            {
                "fact_path": c.fact_path,
                "verdict": c.verdict,
                "confidence": c.confidence,
                "rationale": c.rationale,
                "dissenting_sources": list(c.dissenting_sources),
            }
            for c in caveats
        ],
    }


@router.get("/{patient_id}/narratives/{episode_slug}")
def patient_context_narrative(
    patient_id: str, episode_slug: str, request: Request
) -> dict:
    """Return the FHIR Composition for one episode's narrative.

    Reads ``data/narratives/<patient>/<slug>/current.json``. 404 if
    not yet generated.
    """
    require_access_session(request)
    from lib.narratives import load_current_narrative

    composition = load_current_narrative(patient_id, episode_slug)
    if composition is None:
        raise HTTPException(
            status_code=404,
            detail=f"narrative for {patient_id}/{episode_slug} not yet generated",
        )
    return composition


@router.get("/{patient_id}/narratives/{episode_slug}/history")
def patient_context_narrative_history(
    patient_id: str, episode_slug: str, request: Request
) -> dict:
    """List archived prior versions of an episode's narrative.

    Walks ``data/narratives/<patient>/<slug>/history/*.json`` (written
    by ``lib.narratives.storage.write_current_narrative`` whenever a new
    Composition replaces the prior). Each entry has the archive
    timestamp, the FHIR Composition id, and the resource it replaces.
    Newest-first.
    """
    require_access_session(request)
    from api.core.narrative_history import list_history

    return {
        "patient_id": patient_id,
        "episode_slug": episode_slug,
        "versions": list_history(patient_id, episode_slug),
    }


@router.get("/{patient_id}/narratives/{episode_slug}/history/{timestamp}")
def patient_context_narrative_archived(
    patient_id: str, episode_slug: str, timestamp: str, request: Request
) -> dict:
    """Return the archived FHIR Composition for one prior version."""
    require_access_session(request)
    from api.core.narrative_history import load_archived

    archived = load_archived(patient_id, episode_slug, timestamp)
    if archived is None:
        raise HTTPException(
            status_code=404,
            detail=f"archived narrative {patient_id}/{episode_slug}/{timestamp} not found",
        )
    return archived
