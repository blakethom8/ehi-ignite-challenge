"""
/api/caspian/workflows — run a prepared Caspian workflow packet against a chart.

A workflow run returns a structured artifact (banner, fact rail, sections) that
the workbench renders. It is the workbench-facing counterpart to /assistant/chat:
chat is the conversational steering surface; this endpoint produces packets.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from api.core.auth import authorize_patient_access, require_access_session
from api.core.workflow_runner import (
    WorkflowNotFoundError,
    WorkflowRunError,
    run_workflow,
)
from api.routers.assistant import _build_trace_detail
from api.workspace.events import WORKSPACE_CASPIAN, record_event_for_session
from api.models import WorkflowRunRequest, WorkflowRunResponse

router = APIRouter(prefix="/caspian/workflows", tags=["caspian-workflows"])


@router.post("/run", response_model=WorkflowRunResponse)
def caspian_run_workflow(payload: WorkflowRunRequest, request: Request) -> WorkflowRunResponse:
    """Execute a prepared workflow packet against a patient chart.

    The workflow's packet (data/workflows/<id>.json) supplies the prompt body
    and the artifact schema; the patient context is built the same way as the
    chat path; the structured artifact comes back ready for the workbench.
    """
    session = require_access_session(request)
    resolved_patient_id = authorize_patient_access(
        session,
        payload.patient_id,
        event_type="caspian.workflow.run",
    )
    record_event_for_session(
        session,
        workspace_kind=WORKSPACE_CASPIAN,
        event_type="workflow.run",
        target_id=resolved_patient_id,
        payload={"workflow_id": payload.workflow_id},
    )

    try:
        artifact, citations = run_workflow(
            patient_id=resolved_patient_id,
            workflow_id=payload.workflow_id,
            session=session,
        )
    except WorkflowNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except WorkflowRunError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc

    trace_detail = _build_trace_detail()

    return WorkflowRunResponse(
        patient_id=payload.patient_id,
        artifact=artifact,
        citations=citations,
        trace=trace_detail,
    )
