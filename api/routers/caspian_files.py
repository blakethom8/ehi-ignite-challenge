"""
/api/caspian/files — per-patient file workspace for Caspian.

The Files pane on the Caspian workspace consumes these endpoints. The same
backend module powers the in-process tool layer that the agent uses to read
and write files (see caspian_tools.py / slice 3+4).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from api.core.access_policy import capabilities_for
from api.core.auth import audit_event, authorize_patient_access, require_access_session
from api.core import caspian_workspace
from api.core.caspian_workspace import (
    WorkspaceForbiddenError,
    WorkspaceNotFoundError,
    WorkspacePathError,
)
from api.models import (
    CaspianFileListResponse,
    CaspianFileReadResponse,
    CaspianFileWriteRequest,
    CaspianFileWriteResponse,
    SaveAsNoteRequest,
)

router = APIRouter(prefix="/caspian/files", tags=["caspian-files"])


@router.get("/list", response_model=CaspianFileListResponse)
def list_files(request: Request, patient_id: str = Query(min_length=1, max_length=200)) -> CaspianFileListResponse:
    session = require_access_session(request)
    resolved = authorize_patient_access(session, patient_id, event_type="caspian.file.list")
    data = caspian_workspace.list_workspace(session, resolved)
    return CaspianFileListResponse(
        workspace_key=data["workspace_key"],
        tree=data["tree"],
        capabilities=capabilities_for(session),
    )


@router.get("/read", response_model=CaspianFileReadResponse)
def read_file(
    request: Request,
    patient_id: str = Query(min_length=1, max_length=200),
    path: str = Query(min_length=1, max_length=200),
) -> CaspianFileReadResponse:
    session = require_access_session(request)
    resolved = authorize_patient_access(session, patient_id, event_type="caspian.file.read")
    try:
        result = caspian_workspace.read_workspace_file(session, resolved, path)
    except WorkspacePathError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return CaspianFileReadResponse(
        path=result.path,
        content=result.content,
        mtime=result.mtime,
        editable=result.editable,
        kind=result.kind,
        file_kind=result.file_kind,
    )


@router.put("/write", response_model=CaspianFileWriteResponse)
def write_file(payload: CaspianFileWriteRequest, request: Request) -> CaspianFileWriteResponse:
    session = require_access_session(request)
    # Defense in depth: reject demo + guest at the route boundary before we
    # even touch the workspace layer. The workspace layer also gates this,
    # but this gives the API a clear 403 with a stable error message.
    if session.is_demo or session.is_guest:
        raise HTTPException(
            status_code=403,
            detail="Workspace writes require an authenticated session.",
        )
    resolved = authorize_patient_access(session, payload.patient_id, event_type="caspian.file.write")
    try:
        result = caspian_workspace.write_workspace_file(session, resolved, payload.path, payload.content)
    except WorkspaceForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except WorkspacePathError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return CaspianFileWriteResponse(path=result.path, bytes=result.bytes, mtime=result.mtime)


# ---------------------------------------------------------------------------
# /save-as-note
# ---------------------------------------------------------------------------

# Subtree we accept as a copy source. Generated workflow-run artifacts are
# the only thing that needs the "save as note" affordance — system + user
# files are already either editable or duplicated by the user manually.
_SAVE_AS_NOTE_SOURCE_PREFIX = "workflow-runs/"

# Hard cap on the auto-rename loop to avoid running away if something
# pathological happens to the notes/ folder.
_SAVE_AS_NOTE_MAX_SUFFIX = 50


def _next_notes_path(
    session,
    resolved_patient_id: str,
    source_filename: str,
) -> str:
    """Return a ``notes/<…>`` path that does not collide with an existing file.

    Probes ``notes/<name>``, ``notes/<stem>-2.<ext>``, ``notes/<stem>-3.<ext>``,
    … via ``read_workspace_file``. Returns the first one that 404s.
    """
    base = source_filename
    candidate = f"notes/{base}"
    for attempt in range(_SAVE_AS_NOTE_MAX_SUFFIX):
        try:
            caspian_workspace.read_workspace_file(session, resolved_patient_id, candidate)
        except WorkspaceNotFoundError:
            return candidate
        # Build the next suffixed candidate.
        next_index = attempt + 2  # first retry = -2, then -3, …
        if "." in base:
            stem, ext = base.rsplit(".", 1)
            candidate = f"notes/{stem}-{next_index}.{ext}"
        else:
            candidate = f"notes/{base}-{next_index}"
    # If we still haven't found a free name after MAX_SUFFIX probes, fall
    # through with the last candidate — the workspace write may still
    # overwrite, but the audit trail and the URL will at least be sensible.
    return candidate


@router.post("/save-as-note", response_model=CaspianFileWriteResponse)
def save_as_note(payload: SaveAsNoteRequest, request: Request) -> CaspianFileWriteResponse:
    """Copy a generated workflow-run artifact into the user's ``notes/`` folder.

    - Authenticated sessions only. Demo + guest get 403.
    - ``source_path`` must live under ``workflow-runs/``. 422 otherwise.
    - Filename collisions in ``notes/`` are resolved with a ``-2``, ``-3``, …
      suffix on the stem.
    - Audits as ``caspian.file.save_as_note`` (``target_id`` = resolved patient).
    """
    session = require_access_session(request)
    if session.is_demo or session.is_guest or not session.is_authenticated:
        raise HTTPException(
            status_code=403,
            detail="Saving generated artifacts as notes requires an authenticated session.",
        )

    if not payload.source_path.startswith(_SAVE_AS_NOTE_SOURCE_PREFIX):
        raise HTTPException(
            status_code=422,
            detail=(
                "source_path must be a generated workflow-run path "
                "(e.g. 'workflow-runs/2026-05-12-preop-review-….md')."
            ),
        )

    resolved = authorize_patient_access(
        session, payload.patient_id, event_type="caspian.file.save_as_note.read"
    )

    try:
        source = caspian_workspace.read_workspace_file(session, resolved, payload.source_path)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkspacePathError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    # Defense in depth: even if a future code path lets a non-generated path
    # slip past the prefix check, refuse anything that isn't tagged as
    # generated by the workspace layer.
    if source.file_kind != "generated":
        raise HTTPException(
            status_code=422,
            detail="source_path must resolve to a generated artifact.",
        )

    source_filename = payload.source_path.rsplit("/", 1)[-1]
    target_path = _next_notes_path(session, resolved, source_filename)

    try:
        result = caspian_workspace.write_workspace_file(
            session, resolved, target_path, source.content
        )
    except WorkspaceForbiddenError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except WorkspacePathError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    audit_event(
        event_type="caspian.file.save_as_note",
        session=session,
        patient_id=resolved,
        payload={
            "source_path": payload.source_path,
            "target_path": result.path,
            "bytes": result.bytes,
        },
    )

    return CaspianFileWriteResponse(path=result.path, bytes=result.bytes, mtime=result.mtime)
