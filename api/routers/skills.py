"""/api/skills — skill marketplace + run lifecycle endpoints.

Surfaces:
- `GET  /api/skills` — list registered skills.
- `GET  /api/skills/{name}` — skill manifest detail.
- `POST /api/skills/{name}/runs` — start a run for a patient.
- `GET  /api/skills/{name}/runs/{run_id}` — run status + brief.
- `GET  /api/skills/{name}/runs/{run_id}/workspace` — current workspace.md.
- `GET  /api/skills/{name}/runs/{run_id}/transcript` — transcript events.
- `GET  /api/skills/{name}/runs/{run_id}/citations` — citation list.
- `GET  /api/skills/{name}/runs/{run_id}/output` — finalized artifact.
- `POST /api/skills/{name}/runs/{run_id}/escalations/{approval_id}` — resolve.
- `POST /api/skills/{name}/runs/{run_id}/save` — save destination (run / patient / package).

- `GET  /api/skills/patients/{patient_id}/runs` — list a patient's runs.
- `GET  /api/skills/patients/{patient_id}/memory` — patient memory layer.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any, AsyncIterator, Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from api.core.auth import current_session
from api.core.skills import workspace as workspace_module
from api.workspace.events import WORKSPACE_SKILL, record_event_for_session
from api.core.skills.event_hub import EventHub
from api.core.skills.loader import (
    Skill,
    SkillManifestError,
    load_all_skills,
)
from api.core.skills.patient_memory import PatientMemory
from api.core.skills.trial_pursuits import TrialPursuitStore
from api.core.skills.workspace import (
    WorkspaceContractError,
    list_runs,
    load_workspace,
)
from api.core.skills.worker import get_pool, get_skill
from api.core.skills.agent_loop import TOOL_REGISTRY, assemble_system_prompt


# Tuned for FastAPI behind nginx — keepalive bytes every ~15s prevent any
# upstream proxy from killing an idle SSE connection. See
# docs/architecture/skill-runtime/STREAMING-AND-GATEWAY.md §5.2 for the contract.
SSE_KEEPALIVE_INTERVAL_S = 15.0


router = APIRouter(prefix="/skills", tags=["skills"])


# ── Response/request models ────────────────────────────────────────────────


class EscalationManifestEntry(BaseModel):
    condition: str
    description: str
    action: str
    prompt: str


class SkillSummary(BaseModel):
    name: str
    version: str
    audience: str
    shape: str
    description: str
    required_tools: list[str]
    optional_tools: list[str]
    context_packages: list[str]
    is_live_eligible: bool


class SkillDetail(SkillSummary):
    body: str
    escalation: list[EscalationManifestEntry]
    output_schema: dict[str, Any]
    workspace_template: str | None


class RunStartRequest(BaseModel):
    patient_id: str = Field(..., min_length=1)
    brief: dict[str, Any] = Field(default_factory=dict)


class RunStartResponse(BaseModel):
    run_id: str
    skill_name: str
    patient_id: str
    status: str


class RunStateResponse(BaseModel):
    run_id: str
    skill_name: str
    patient_id: str
    status: str
    brief: dict[str, Any]
    pending_escalations: list[dict[str, Any]]
    failure_reason: str | None = None


class WorkspaceResponse(BaseModel):
    run_id: str
    markdown: str
    citations: list[dict[str, Any]]


class CitationListResponse(BaseModel):
    run_id: str
    citations: list[dict[str, Any]]


class TranscriptResponse(BaseModel):
    run_id: str
    events: list[dict[str, Any]]


class CanvasNodeModel(BaseModel):
    node_id: str
    kind: str
    title: str
    status: str = "active"
    summary: str = ""
    data: dict[str, Any]
    selected: bool
    created_at: str
    updated_at: str


class CanvasResponse(BaseModel):
    run_id: str
    version: int
    updated_at: str
    nodes: list[CanvasNodeModel]


class CanvasSelectionRequest(BaseModel):
    selected: bool
    actor: str = "clinician"


class RunMessageModel(BaseModel):
    message_id: str
    actor: str
    message: str
    canvas_ref: dict[str, Any] | None = None
    consumed: bool
    consumed_at: str | None = None
    created_at: str


class RunMessagesResponse(BaseModel):
    run_id: str
    messages: list[RunMessageModel]


class RunMessageRequest(BaseModel):
    actor: Literal["clinician", "patient", "system"] = "clinician"
    message: str = Field(..., min_length=1)
    canvas_ref: dict[str, Any] | None = None


class EscalationResolutionRequest(BaseModel):
    choice: str = Field(..., min_length=1)
    notes: str = ""
    actor: str = "clinician"


class SaveRequest(BaseModel):
    destination: Literal["run", "patient", "package"]
    actor: str = "clinician"
    # Per-destination payload (only one applies, validated below)
    edits_markdown: str | None = None
    facts: list[dict[str, Any]] | None = None
    package_name: str | None = None
    package_content: str | None = None


class SaveResponse(BaseModel):
    destination: str
    written_path: str


class RunListItem(BaseModel):
    run_id: str
    skill_name: str
    patient_id: str
    status: str
    started_at: str | None = None
    finished_at: str | None = None


class PatientMemoryResponse(BaseModel):
    patient_id: str
    pinned: str
    context_packages: dict[str, str]
    notes: list[dict[str, Any]]


class TrialPursuitTaskModel(BaseModel):
    task_id: str
    title: str
    status: str
    due_at: str | None = None
    created_at: str
    completed_at: str | None = None


class TrialPursuitEventModel(BaseModel):
    event_id: str
    kind: str
    note: str
    actor: str
    data: dict[str, Any]
    created_at: str


class TrialPursuitModel(BaseModel):
    pursuit_id: str
    patient_id: str
    nct_id: str
    title: str
    status: str
    sponsor: str | None = None
    trial_status: str | None = None
    source_url: str | None = None
    source_kind: str
    source_updated_at: str | None = None
    fit_score: float | None = None
    next_step: str
    notes: str
    tags: list[str]
    created_from_run_id: str | None = None
    created_from_canvas_node_id: str | None = None
    evidence_snapshot: dict[str, Any]
    tasks: list[TrialPursuitTaskModel]
    events: list[TrialPursuitEventModel]
    created_at: str
    updated_at: str


class TrialPursuitListResponse(BaseModel):
    patient_id: str
    pursuits: list[TrialPursuitModel]


class TrialPursuitUpsertRequest(BaseModel):
    nct_id: str = Field(..., pattern=r"^NCT\d{8}$")
    title: str = Field(..., min_length=1)
    status: str = "interested"
    sponsor: str | None = None
    trial_status: str | None = None
    source_url: str | None = None
    source_kind: str = "clinicaltrials.gov"
    source_updated_at: str | None = None
    fit_score: float | None = None
    next_step: str | None = None
    notes: str | None = None
    tags: list[str] = Field(default_factory=list)
    created_from_run_id: str | None = None
    created_from_canvas_node_id: str | None = None
    evidence_snapshot: dict[str, Any] = Field(default_factory=dict)
    actor: str = "clinician"


class TrialPursuitUpdateRequest(BaseModel):
    status: str | None = None
    next_step: str | None = None
    notes: str | None = None
    tags: list[str] | None = None
    event_note: str | None = None
    actor: str = "clinician"


class TrialPursuitEventRequest(BaseModel):
    kind: str = Field(..., min_length=1)
    note: str = Field(..., min_length=1)
    actor: str = "clinician"
    data: dict[str, Any] = Field(default_factory=dict)


class TrialPursuitTaskRequest(BaseModel):
    title: str = Field(..., min_length=1)
    due_at: str | None = None
    actor: str = "clinician"


class InspectorFileModel(BaseModel):
    path: str
    kind: str
    size_bytes: int
    content: str | None = None


class InspectorToolModel(BaseModel):
    alias: str
    name: str
    description: str
    input_schema: dict[str, Any]
    kind: str
    permission: str
    declared: bool = True
    available: bool = True


class RunInspectorResponse(BaseModel):
    run: dict[str, Any]
    skill: dict[str, Any]
    instructions: dict[str, Any]
    context: dict[str, Any]
    tools: list[InspectorToolModel]
    permissions: dict[str, Any]
    transcript: dict[str, Any]
    artifacts: dict[str, Any]


# ── Skill catalog ──────────────────────────────────────────────────────────


def _summary_from_skill(skill: Skill) -> SkillSummary:
    return SkillSummary(
        name=skill.manifest.name,
        version=skill.manifest.version,
        audience=skill.manifest.audience,
        shape=skill.manifest.shape,
        description=skill.manifest.description,
        required_tools=list(skill.manifest.required_tools),
        optional_tools=list(skill.manifest.optional_tools),
        context_packages=list(skill.manifest.context_packages),
        is_live_eligible=skill.is_live_eligible,
    )


@router.get("", response_model=list[SkillSummary])
def list_skills() -> list[SkillSummary]:
    try:
        skills = load_all_skills()
    except SkillManifestError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    return [_summary_from_skill(s) for s in skills]


@router.get("/{skill_name}", response_model=SkillDetail)
def get_skill_detail(skill_name: str) -> SkillDetail:
    skill = _resolve_skill(skill_name)
    summary = _summary_from_skill(skill)
    return SkillDetail(
        **summary.model_dump(),
        body=skill.body,
        escalation=[
            EscalationManifestEntry(
                condition=t.condition,
                description=t.description,
                action=t.action,
                prompt=t.prompt,
            )
            for t in skill.manifest.escalation
        ],
        output_schema=skill.output_schema,
        workspace_template=skill.workspace_template,
    )


# ── Run lifecycle ──────────────────────────────────────────────────────────


@router.post("/{skill_name}/runs", response_model=RunStartResponse)
async def start_run(
    skill_name: str, payload: RunStartRequest, request: Request
) -> RunStartResponse:
    skill = _resolve_skill(skill_name)
    pool = get_pool()
    run_id, _task = await pool.submit(
        skill=skill, patient_id=payload.patient_id, brief=payload.brief
    )
    # Best-effort audit event — current_session is None for unauthenticated
    # callers, in which case record_event_for_session is a no-op.
    record_event_for_session(
        current_session(request),
        workspace_kind=WORKSPACE_SKILL,
        event_type="run.started",
        target_id=run_id,
        payload={
            "skill_name": skill.name,
            "patient_id": payload.patient_id,
            "brief": (payload.brief or "")[:200],
        },
    )
    # Don't block on run completion — the client polls the GET endpoint.
    return RunStartResponse(
        run_id=run_id,
        skill_name=skill.name,
        patient_id=payload.patient_id,
        status="created",
    )


@router.get("/{skill_name}/runs/{run_id}", response_model=RunStateResponse)
async def get_run_state(
    skill_name: str, run_id: str, patient_id: str
) -> RunStateResponse:
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    pending = workspace.pending_escalations()
    return RunStateResponse(
        run_id=run_id,
        skill_name=skill.name,
        patient_id=patient_id,
        status=workspace.status,
        brief=workspace.brief,
        pending_escalations=[
            {
                "approval_id": e.approval_id,
                "condition": e.condition,
                "prompt": e.prompt,
                "context": e.context,
                "raised_at": e.raised_at,
            }
            for e in pending
        ],
        failure_reason=workspace.failure_reason,
    )


@router.get("/{skill_name}/runs/{run_id}/workspace", response_model=WorkspaceResponse)
async def get_workspace_markdown(
    skill_name: str, run_id: str, patient_id: str
) -> WorkspaceResponse:
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    md = (
        workspace.workspace_md_path.read_text("utf-8")
        if workspace.workspace_md_path.is_file()
        else ""
    )
    return WorkspaceResponse(
        run_id=run_id,
        markdown=md,
        citations=[c.__dict__ for c in workspace.citations()],
    )


@router.get(
    "/{skill_name}/runs/{run_id}/citations", response_model=CitationListResponse
)
async def get_citations(
    skill_name: str, run_id: str, patient_id: str
) -> CitationListResponse:
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    return CitationListResponse(
        run_id=run_id, citations=[c.__dict__ for c in workspace.citations()]
    )


@router.get(
    "/{skill_name}/runs/{run_id}/transcript", response_model=TranscriptResponse
)
async def get_transcript(
    skill_name: str, run_id: str, patient_id: str
) -> TranscriptResponse:
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    return TranscriptResponse(
        run_id=run_id, events=list(workspace.transcript_events())
    )


@router.get("/{skill_name}/runs/{run_id}/canvas", response_model=CanvasResponse)
async def get_canvas(
    skill_name: str, run_id: str, patient_id: str
) -> CanvasResponse:
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    state = workspace.canvas_state()
    return CanvasResponse(
        run_id=run_id,
        version=int(state.get("version") or 1),
        updated_at=str(state.get("updated_at") or ""),
        nodes=[CanvasNodeModel(**node) for node in state.get("nodes", [])],
    )


@router.post(
    "/{skill_name}/runs/{run_id}/canvas/nodes/{node_id}/selection",
    response_model=CanvasNodeModel,
)
async def set_canvas_node_selection(
    skill_name: str,
    run_id: str,
    node_id: str,
    patient_id: str,
    payload: CanvasSelectionRequest,
) -> CanvasNodeModel:
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    pool = get_pool()
    hub = await pool.hub_for(patient_id, skill.name, run_id)
    if hub is not None and not hub.closed:
        workspace.event_hub = hub
    try:
        node = workspace.set_canvas_selection(
            node_id,
            selected=payload.selected,
            actor=payload.actor,
        )
    except WorkspaceContractError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return CanvasNodeModel(**node.__dict__)


@router.get(
    "/{skill_name}/runs/{run_id}/messages", response_model=RunMessagesResponse
)
async def get_run_messages(
    skill_name: str, run_id: str, patient_id: str
) -> RunMessagesResponse:
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    return RunMessagesResponse(
        run_id=run_id,
        messages=[RunMessageModel(**m.__dict__) for m in workspace.messages()],
    )


@router.get(
    "/{skill_name}/runs/{run_id}/inspector",
    response_model=RunInspectorResponse,
)
async def get_run_inspector(
    skill_name: str, run_id: str, patient_id: str
) -> RunInspectorResponse:
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    memory = PatientMemory(patient_id)
    transcript_events = list(workspace.transcript_events())
    canvas_state = workspace.canvas_state()
    output_path = workspace.run_dir / "output.json"
    status_path = workspace.run_dir / "status.json"
    status_payload = (
        json.loads(status_path.read_text("utf-8")) if status_path.is_file() else {}
    )
    workspace_markdown = (
        workspace.workspace_md_path.read_text("utf-8")
        if workspace.workspace_md_path.is_file()
        else ""
    )
    output = json.loads(output_path.read_text("utf-8")) if output_path.is_file() else None
    public_brief = {k: v for k, v in workspace.brief.items() if not k.startswith("_")}
    assembled_prompt = assemble_system_prompt(
        skill_body=skill.body,
        patient_memory=memory.session_context(
            requested_packages=list(skill.manifest.context_packages)
        ),
        brief=workspace.brief,
        skill_name=skill.name,
        skill_version=skill.manifest.version,
    )

    return RunInspectorResponse(
        run={
            "run_id": run_id,
            "skill_name": skill.name,
            "patient_id": patient_id,
            "status": workspace.status,
            "failure_reason": workspace.failure_reason,
            "started_at": status_payload.get("started_at")
            or public_brief.get("started_at"),
            "finished_at": status_payload.get("finished_at"),
            "run_dir": str(workspace.run_dir),
        },
        skill={
            "name": skill.name,
            "version": skill.manifest.version,
            "audience": skill.manifest.audience,
            "shape": skill.manifest.shape,
            "description": skill.manifest.description,
            "required_tools": list(skill.manifest.required_tools),
            "optional_tools": list(skill.manifest.optional_tools),
            "context_packages": list(skill.manifest.context_packages),
            "is_live_eligible": skill.is_live_eligible,
        },
        instructions={
            "skill_md": skill.body,
            "workspace_template": skill.workspace_template,
            "output_schema": skill.output_schema,
            "escalation": [trigger.__dict__ for trigger in skill.manifest.escalation],
            "assembled_prompt": assembled_prompt,
            "files": _skill_inspector_files(skill),
        },
        context={
            "brief": public_brief,
            "patient_memory": {
                "pinned": memory.pinned(),
                "context_packages": memory.context_packages(),
                "notes": memory.notes(),
            },
            "messages": [m.__dict__ for m in workspace.messages()],
            "canvas": canvas_state,
            "citations": [c.__dict__ for c in workspace.citations()],
        },
        tools=_inspector_tools(skill),
        permissions=_inspector_permissions(skill),
        transcript={
            "events": transcript_events,
            "summary": _transcript_summary(transcript_events),
        },
        artifacts={
            "workspace_markdown": workspace_markdown,
            "canvas": canvas_state,
            "output": output,
            "citations": [c.__dict__ for c in workspace.citations()],
            "files": _run_inspector_files(workspace.run_dir),
        },
    )


@router.post(
    "/{skill_name}/runs/{run_id}/messages", response_model=RunMessageModel
)
async def add_run_message(
    skill_name: str,
    run_id: str,
    patient_id: str,
    payload: RunMessageRequest,
) -> RunMessageModel:
    """Add a clinician/patient steering message to an active run.

    REST is the uplink; SSE remains the downlink. If the run is active, attach
    the current EventHub before appending so `message_added` broadcasts live.
    """
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    pool = get_pool()
    hub = await pool.hub_for(patient_id, skill.name, run_id)
    if hub is not None and not hub.closed:
        workspace.event_hub = hub
    try:
        message = workspace.append_message(
            payload.message,
            actor=payload.actor,
            canvas_ref=payload.canvas_ref,
        )
    except WorkspaceContractError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return RunMessageModel(**message.__dict__)


@router.get("/{skill_name}/runs/{run_id}/events")
async def stream_run_events(
    skill_name: str, run_id: str, patient_id: str
) -> StreamingResponse:
    """SSE feed for a run.

    Replays every event in `transcript.jsonl` first (so a late subscriber
    sees the full history), then attaches to the in-memory `EventHub` for
    live updates. Closes when the run terminates and the hub publishes
    its close sentinel.

    Sent as `text/event-stream`. See
    `docs/architecture/skill-runtime/STREAMING-AND-GATEWAY.md` for the design rationale.
    """
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    pool = get_pool()
    hub = await pool.hub_for(patient_id, skill.name, run_id)

    async def event_stream() -> AsyncIterator[bytes]:
        # 1. Replay history. Disk is the source of truth — every connected
        #    client gets the complete record before joining the live tail.
        for event in workspace.transcript_events():
            yield _format_sse(event)

        # 2. Subscribe to live events if the run is still active. If the
        #    run already finished (hub closed or absent), emit a close
        #    sentinel and end.
        if hub is not None and not hub.closed:
            keepalive_task: asyncio.Task[None] | None = None
            keepalive_queue: asyncio.Queue[bytes] = asyncio.Queue()

            async def emit_keepalives() -> None:
                while True:
                    await asyncio.sleep(SSE_KEEPALIVE_INTERVAL_S)
                    await keepalive_queue.put(b": keepalive\n\n")

            keepalive_task = asyncio.create_task(emit_keepalives())
            try:
                async def merge() -> AsyncIterator[bytes]:
                    sub_iter = hub.subscribe().__aiter__()
                    sub_task: asyncio.Task[Any] = asyncio.create_task(
                        sub_iter.__anext__()
                    )
                    keep_task: asyncio.Task[bytes] = asyncio.create_task(
                        keepalive_queue.get()
                    )
                    try:
                        while True:
                            done, _ = await asyncio.wait(
                                {sub_task, keep_task},
                                return_when=asyncio.FIRST_COMPLETED,
                            )
                            if sub_task in done:
                                try:
                                    event = sub_task.result()
                                except StopAsyncIteration:
                                    return
                                yield _format_sse(event)
                                sub_task = asyncio.create_task(
                                    sub_iter.__anext__()
                                )
                            if keep_task in done:
                                yield keep_task.result()
                                keep_task = asyncio.create_task(
                                    keepalive_queue.get()
                                )
                    finally:
                        for t in (sub_task, keep_task):
                            if not t.done():
                                t.cancel()
                async for chunk in merge():
                    yield chunk
            finally:
                if keepalive_task is not None:
                    keepalive_task.cancel()

        # 3. Terminal sentinel — clients use this to stop reading cleanly.
        yield _format_sse({"kind": "stream_closed"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # nginx — disable response buffering so events flush in real time
            "X-Accel-Buffering": "no",
        },
    )


def _format_sse(event: dict[str, Any]) -> bytes:
    """Render a JSON event as one SSE record."""
    return f"data: {json.dumps(event, default=str)}\n\n".encode("utf-8")


@router.get("/{skill_name}/runs/{run_id}/output")
async def get_output(skill_name: str, run_id: str, patient_id: str) -> dict[str, Any]:
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    output_path = workspace.run_dir / "output.json"
    if not output_path.is_file():
        raise HTTPException(status_code=404, detail="run has not finalized yet")
    return json.loads(output_path.read_text("utf-8"))


@router.post(
    "/{skill_name}/runs/{run_id}/escalations/{approval_id}", response_model=RunStateResponse
)
async def resolve_escalation(
    skill_name: str,
    run_id: str,
    approval_id: str,
    patient_id: str,
    payload: EscalationResolutionRequest,
) -> RunStateResponse:
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)
    try:
        workspace.resolve_escalation(
            approval_id=approval_id,
            choice=payload.choice,
            notes=payload.notes,
            actor=payload.actor,
        )
    except WorkspaceContractError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    if not workspace.pending_escalations():
        # Resume the run.
        pool = get_pool()
        await pool.resume(patient_id=patient_id, skill=skill, run_id=run_id)

    return await get_run_state(skill_name=skill_name, run_id=run_id, patient_id=patient_id)


# ── Save destinations ──────────────────────────────────────────────────────


@router.post("/{skill_name}/runs/{run_id}/save", response_model=SaveResponse)
async def save_run(
    skill_name: str,
    run_id: str,
    patient_id: str,
    payload: SaveRequest,
) -> SaveResponse:
    skill = _resolve_skill(skill_name)
    workspace = _resolve_workspace(skill, patient_id, run_id)

    try:
        if payload.destination == "run":
            if not (payload.edits_markdown or "").strip():
                raise HTTPException(
                    status_code=400, detail="edits_markdown is required for destination=run"
                )
            written = workspace.save_run_edits(payload.edits_markdown, actor=payload.actor)
        elif payload.destination == "patient":
            if not payload.facts:
                raise HTTPException(
                    status_code=400, detail="facts is required for destination=patient"
                )
            written = workspace.pin_to_patient(payload.facts, actor=payload.actor)
        elif payload.destination == "package":
            if not (payload.package_name or "").strip() or not (
                payload.package_content or ""
            ).strip():
                raise HTTPException(
                    status_code=400,
                    detail="package_name and package_content are required for destination=package",
                )
            written = workspace.save_as_context_package(
                payload.package_name, payload.package_content, actor=payload.actor
            )
        else:  # pragma: no cover — Pydantic validates the literal
            raise HTTPException(status_code=400, detail="unknown destination")
    except WorkspaceContractError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return SaveResponse(destination=payload.destination, written_path=str(written))


# ── Patient-level views ────────────────────────────────────────────────────


@router.get("/patients/{patient_id}/runs", response_model=list[RunListItem])
async def list_patient_runs(
    patient_id: str, skill_name: str | None = None
) -> list[RunListItem]:
    items = list_runs(patient_id, skill_name)
    return [RunListItem(**item) for item in items]


@router.get(
    "/patients/{patient_id}/memory", response_model=PatientMemoryResponse
)
async def get_patient_memory(patient_id: str) -> PatientMemoryResponse:
    memory = PatientMemory(patient_id)
    return PatientMemoryResponse(
        patient_id=patient_id,
        pinned=memory.pinned(),
        context_packages=memory.context_packages(),
        notes=memory.notes(),
    )


@router.get(
    "/patients/{patient_id}/trial-pursuits",
    response_model=TrialPursuitListResponse,
)
async def list_trial_pursuits(patient_id: str) -> TrialPursuitListResponse:
    pursuits = TrialPursuitStore(patient_id).list()
    return TrialPursuitListResponse(
        patient_id=patient_id,
        pursuits=[_trial_pursuit_model(pursuit) for pursuit in pursuits],
    )


@router.post(
    "/patients/{patient_id}/trial-pursuits",
    response_model=TrialPursuitModel,
)
async def upsert_trial_pursuit(
    patient_id: str,
    payload: TrialPursuitUpsertRequest,
) -> TrialPursuitModel:
    store = TrialPursuitStore(patient_id)
    try:
        pursuit = store.upsert(payload.model_dump(exclude={"actor"}), actor=payload.actor)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _trial_pursuit_model(pursuit)


@router.patch(
    "/patients/{patient_id}/trial-pursuits/{pursuit_id}",
    response_model=TrialPursuitModel,
)
async def update_trial_pursuit(
    patient_id: str,
    pursuit_id: str,
    payload: TrialPursuitUpdateRequest,
) -> TrialPursuitModel:
    store = TrialPursuitStore(patient_id)
    try:
        pursuit = store.update(
            pursuit_id,
            payload.model_dump(exclude={"actor"}, exclude_none=True),
            actor=payload.actor,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="trial pursuit not found")
    return _trial_pursuit_model(pursuit)


@router.post(
    "/patients/{patient_id}/trial-pursuits/{pursuit_id}/events",
    response_model=TrialPursuitModel,
)
async def add_trial_pursuit_event(
    patient_id: str,
    pursuit_id: str,
    payload: TrialPursuitEventRequest,
) -> TrialPursuitModel:
    store = TrialPursuitStore(patient_id)
    try:
        pursuit = store.add_event(
            pursuit_id,
            kind=payload.kind,
            note=payload.note,
            actor=payload.actor,
            data_payload=payload.data,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="trial pursuit not found")
    return _trial_pursuit_model(pursuit)


@router.post(
    "/patients/{patient_id}/trial-pursuits/{pursuit_id}/tasks",
    response_model=TrialPursuitModel,
)
async def add_trial_pursuit_task(
    patient_id: str,
    pursuit_id: str,
    payload: TrialPursuitTaskRequest,
) -> TrialPursuitModel:
    store = TrialPursuitStore(patient_id)
    try:
        pursuit = store.add_task(
            pursuit_id,
            title=payload.title,
            due_at=payload.due_at,
            actor=payload.actor,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="trial pursuit not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return _trial_pursuit_model(pursuit)


# ── Internal helpers ───────────────────────────────────────────────────────


def _trial_pursuit_model(pursuit: Any) -> TrialPursuitModel:
    return TrialPursuitModel(
        pursuit_id=pursuit.pursuit_id,
        patient_id=pursuit.patient_id,
        nct_id=pursuit.nct_id,
        title=pursuit.title,
        status=pursuit.status,
        sponsor=pursuit.sponsor,
        trial_status=pursuit.trial_status,
        source_url=pursuit.source_url,
        source_kind=pursuit.source_kind,
        source_updated_at=pursuit.source_updated_at,
        fit_score=pursuit.fit_score,
        next_step=pursuit.next_step,
        notes=pursuit.notes,
        tags=pursuit.tags,
        created_from_run_id=pursuit.created_from_run_id,
        created_from_canvas_node_id=pursuit.created_from_canvas_node_id,
        evidence_snapshot=pursuit.evidence_snapshot,
        tasks=[TrialPursuitTaskModel(**task.__dict__) for task in pursuit.tasks],
        events=[TrialPursuitEventModel(**event.__dict__) for event in pursuit.events],
        created_at=pursuit.created_at,
        updated_at=pursuit.updated_at,
    )


def _skill_inspector_files(skill: Skill) -> list[InspectorFileModel]:
    files: list[InspectorFileModel] = []
    for relative, kind in [
        ("SKILL.md", "skill"),
        ("workspace.template.md", "template"),
        (skill.manifest.output_schema_path, "schema"),
    ]:
        path = skill.skill_dir / relative
        if path.is_file():
            files.append(_inspector_file(path, skill.skill_dir, kind, include_content=True))
    for directory, kind in [("references", "reference"), ("scripts", "script")]:
        root = skill.skill_dir / directory
        if not root.is_dir():
            continue
        for path in sorted(p for p in root.rglob("*") if p.is_file()):
            files.append(_inspector_file(path, skill.skill_dir, kind, include_content=True))
    return files


def _run_inspector_files(run_dir: Path) -> list[InspectorFileModel]:
    files: list[InspectorFileModel] = []
    for path in sorted(p for p in run_dir.iterdir() if p.is_file()):
        files.append(_inspector_file(path, run_dir, _run_file_kind(path), include_content=False))
    return files


def _inspector_file(
    path: Path,
    root: Path,
    kind: str,
    *,
    include_content: bool,
) -> InspectorFileModel:
    content: str | None = None
    if include_content:
        try:
            text = path.read_text("utf-8")
        except UnicodeDecodeError:
            text = ""
        content = text if len(text) <= 20000 else text[:20000] + "\n\n[truncated]"
    return InspectorFileModel(
        path=str(path.relative_to(root)),
        kind=kind,
        size_bytes=path.stat().st_size,
        content=content,
    )


def _run_file_kind(path: Path) -> str:
    if path.name == "workspace.md":
        return "workspace"
    if path.name in {"canvas.json", "output.json", "brief.json", "status.json"}:
        return "state"
    if path.name.endswith(".jsonl"):
        return "log"
    if path.name.endswith(".md"):
        return "markdown"
    return "artifact"


def _inspector_tools(skill: Skill) -> list[InspectorToolModel]:
    aliases = list(skill.manifest.required_tools) + list(skill.manifest.optional_tools)
    out: list[InspectorToolModel] = []
    seen: set[str] = set()
    for alias in aliases + ["submit_final_artifact"]:
        if alias in seen:
            continue
        seen.add(alias)
        spec = TOOL_REGISTRY.get(alias)
        if spec is None:
            out.append(
                InspectorToolModel(
                    alias=alias,
                    name=alias,
                    description="Declared by the skill manifest, but not registered in this runtime.",
                    input_schema={},
                    kind="unknown",
                    permission="unavailable",
                    declared=alias in aliases,
                    available=False,
                )
            )
            continue
        out.append(
            InspectorToolModel(
                alias=alias,
                name=spec.name,
                description=spec.description,
                input_schema=spec.input_schema,
                kind=_tool_kind(alias),
                permission=_tool_permission(alias),
                declared=alias in aliases,
                available=True,
            )
        )
    return out


def _tool_kind(alias: str) -> str:
    if alias.startswith("workspace."):
        return "workspace"
    if alias.startswith("trial_pursuit."):
        return "pursuit_board"
    if alias == "submit_final_artifact":
        return "lifecycle"
    if alias.startswith("mcp."):
        return "external_api"
    if alias in {"get_patient_snapshot", "query_chart_evidence"}:
        return "chart"
    if alias == "run_sql":
        return "sql"
    return "local"


def _tool_permission(alias: str) -> str:
    if alias == "workspace.write":
        return "writes workspace markdown"
    if alias == "workspace.cite":
        return "writes citation registry"
    if alias == "workspace.escalate":
        return "pauses run for human decision"
    if alias == "workspace.canvas.upsert":
        return "writes side-canvas state"
    if alias.startswith("trial_pursuit."):
        return "writes patient-level trial pursuit board"
    if alias == "submit_final_artifact":
        return "submits schema-validated final output"
    if alias.startswith("mcp."):
        return "external network via registered API only"
    if alias == "run_sql":
        return "read-only SELECT/WITH SQL, capped at 500 rows"
    if alias in {"get_patient_snapshot", "query_chart_evidence"}:
        return "read-only selected-patient chart evidence"
    return "runtime mediated"


def _inspector_permissions(skill: Skill) -> dict[str, Any]:
    required = set(skill.manifest.required_tools)
    optional = set(skill.manifest.optional_tools)
    all_tools = required | optional
    return {
        "filesystem": "no general file read/write tools; agent writes only through workspace primitives",
        "shell": "no shell or raw CLI access",
        "network": "only registered external API tools are available",
        "chart_access": "read-only chart evidence tools when declared by the skill",
        "sql": "read-only SQL-on-FHIR SELECT/WITH through run_sql when declared",
        "human_approval": "workspace.escalate pauses the run for clinician decision",
        "enabled_capabilities": {
            "workspace_writes": "workspace.write" in all_tools,
            "canvas_writes": "workspace.canvas.upsert" in all_tools,
            "pursuit_board_writes": any(
                alias.startswith("trial_pursuit.") for alias in all_tools
            ),
            "chart_evidence": bool({"get_patient_snapshot", "query_chart_evidence"} & all_tools),
            "read_only_sql": "run_sql" in all_tools,
            "external_registry": any(alias.startswith("mcp.") for alias in all_tools),
            "web_search": "web.search" in all_tools,
            "web_fetch": "web.fetch" in all_tools,
            "shell": False,
        },
    }


def _transcript_summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    counts: dict[str, int] = {}
    tool_counts: dict[str, int] = {}
    total_tool_duration_ms = 0
    for event in events:
        kind = str(event.get("kind") or "")
        counts[kind] = counts.get(kind, 0) + 1
        if kind in {"agent_tool_call", "agent_tool_result", "agent_tool_error"}:
            tool = str(event.get("tool") or "unknown")
            tool_counts[tool] = tool_counts.get(tool, 0) + 1
        duration = event.get("duration_ms")
        if isinstance(duration, int | float):
            total_tool_duration_ms += int(duration)
    return {
        "event_count": len(events),
        "by_kind": counts,
        "by_tool": tool_counts,
        "total_tool_duration_ms": total_tool_duration_ms,
    }


def _resolve_skill(skill_name: str) -> Skill:
    try:
        return get_skill(skill_name)
    except SkillManifestError as exc:
        raise HTTPException(status_code=500, detail=str(exc))
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=404, detail=f"skill '{skill_name}' not found: {exc}")


def _resolve_workspace(skill: Skill, patient_id: str, run_id: str):
    try:
        return load_workspace(skill, patient_id, run_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
