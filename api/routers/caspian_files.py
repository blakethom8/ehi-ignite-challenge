"""
/api/caspian/files — per-patient file workspace for Caspian.

The Files pane on the Caspian workspace consumes these endpoints. The same
backend module powers the in-process tool layer that the agent uses to read
and write files (see caspian_tools.py / slice 3+4).
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from api.core.access_policy import capabilities_for
from api.core.auth import authorize_patient_access, require_access_session
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
