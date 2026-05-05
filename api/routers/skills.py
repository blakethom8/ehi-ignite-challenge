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
from typing import Any, Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from api.core.skills import workspace as workspace_module
from api.core.skills.loader import (
    Skill,
    SkillManifestError,
    load_all_skills,
)
from api.core.skills.patient_memory import PatientMemory
from api.core.skills.workspace import (
    WorkspaceContractError,
    list_runs,
    load_workspace,
)
from api.core.skills.worker import get_pool, get_skill


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
async def start_run(skill_name: str, payload: RunStartRequest) -> RunStartResponse:
    skill = _resolve_skill(skill_name)
    pool = get_pool()
    run_id, _task = await pool.submit(
        skill=skill, patient_id=payload.patient_id, brief=payload.brief
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


# ── Internal helpers ───────────────────────────────────────────────────────


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
