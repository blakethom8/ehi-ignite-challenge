"""HTTP surface for the plugin runtime.

Endpoints mirror PLUGIN-RUNTIME.md §9.3. All write endpoints accept a
``user`` body field; v1 trusts the caller (no auth layer). v2 wires
this to the real session principal.
"""

from __future__ import annotations

import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.plugins import provenance as prov_log
from api.plugins import runtime as rt
from api.plugins.anchors import AnchorError, AnchorExpired, OutOfScope
from api.plugins.connectors import UndeclaredConnector
from api.plugins.consent import ConsentError, ConsentExpired, ConsentRequired
from api.plugins.manifest import (
    PluginManifestError,
    discover_installed,
    load_manifest,
)
from api.plugins.tools import ApprovalRequired, PermissionDenied, UnknownTool
from api.trust.models import UserIdentity


router = APIRouter(prefix="/plugins", tags=["plugins"])


# ============================================================
# Helpers
# ============================================================


def _coerce_user(body: dict) -> UserIdentity:
    raw = body.get("user") or body.get("approver") or {
        "id": "demo-clinician",
        "name": "Demo Clinician",
        "role": "clinician",
    }
    return UserIdentity.model_validate(raw)


def _wrap_runtime_error(exc: Exception) -> HTTPException:
    """Map a runtime exception to a typed HTTP error the frontend can parse."""
    mapping = {
        OutOfScope: ("OutOfScope", 403),
        UndeclaredConnector: ("UndeclaredConnector", 403),
        ConsentRequired: ("ConsentRequired", 403),
        ConsentExpired: ("ConsentExpired", 403),
        ConsentError: ("ConsentError", 403),
        ApprovalRequired: ("ApprovalRequired", 403),
        AnchorExpired: ("AnchorExpired", 410),
        AnchorError: ("AnchorError", 410),
        PermissionDenied: ("PermissionDenied", 403),
        UnknownTool: ("UnknownTool", 404),
        PluginManifestError: ("PluginManifestError", 400),
    }
    for cls, (code, status) in mapping.items():
        if isinstance(exc, cls):
            return HTTPException(
                status_code=status,
                detail={"error": code, "message": str(exc)},
            )
    return HTTPException(status_code=500, detail={"error": "RuntimeError", "message": str(exc)})


def _manifest_to_payload(loaded) -> dict:
    return loaded.raw


# ============================================================
# Plugin catalog
# ============================================================


@router.get("/installed")
def list_installed() -> list[dict]:
    out: list[dict] = []
    for plugin_id, version in discover_installed():
        try:
            loaded = load_manifest(plugin_id, version)
        except PluginManifestError:
            continue
        out.append(_manifest_to_payload(loaded))
    return out


@router.get("/{plugin_id}/manifest")
def get_manifest(plugin_id: str) -> dict:
    # Find first installed version
    for pid, version in discover_installed():
        if pid == plugin_id:
            try:
                loaded = load_manifest(pid, version)
            except PluginManifestError as e:
                raise _wrap_runtime_error(e)
            return _manifest_to_payload(loaded)
    raise HTTPException(status_code=404, detail={"error": "NotInstalled", "plugin": plugin_id})


@router.get("/{plugin_id}/runs")
def list_runs(plugin_id: str) -> list[dict]:
    return [_run_to_payload(r) for r in rt.list_runs_for_plugin(plugin_id)]


# ============================================================
# Runs
# ============================================================


class StartRunBody(BaseModel):
    pluginId: str
    patientId: str = "8.4127.881"
    workflowId: str | None = None
    title: str | None = None
    user: dict | None = None


def _run_to_payload(run: rt.RunRow) -> dict:
    return {
        "id": run.id,
        "pluginId": run.pluginId,
        "pluginVersion": run.pluginVersion,
        "patientId": run.patientId,
        "state": run.state,
        "workflowId": run.workflowId,
        "title": run.title,
        "startedBy": run.startedBy.model_dump(),
        "startedAt": run.startedAt,
        "completedAt": run.completedAt,
        "anchor": run.anchor.model_dump(mode="json") if run.anchor else None,
        "canvas": run.canvas,
    }


@router.post("/runs")
def start_run(body: StartRunBody) -> dict:
    user = _coerce_user(body.model_dump())
    try:
        run = rt.start_run(
            plugin_id=body.pluginId,
            patient_id=body.patientId,
            workflow_id=body.workflowId,
            title=body.title,
            user=user,
        )
    except Exception as e:
        raise _wrap_runtime_error(e)
    return _run_to_payload(run)


@router.get("/runs/{run_id}")
def get_run(run_id: str) -> dict:
    try:
        return _run_to_payload(rt.get_run(run_id))
    except RuntimeError as e:
        raise HTTPException(status_code=404, detail={"error": "NotFound", "message": str(e)})


class ConsentBody(BaseModel):
    user: dict | None = None


@router.post("/runs/{run_id}/consent")
def grant_consent(run_id: str, body: ConsentBody) -> dict:
    user = _coerce_user(body.model_dump())
    try:
        token = rt.grant_consent(run_id, approver=user)
    except Exception as e:
        raise _wrap_runtime_error(e)
    return {
        "runId": run_id,
        "consentToken": token.model_dump(mode="json"),
    }


@router.post("/runs/{run_id}/revoke-consent")
def revoke_consent(run_id: str, body: ConsentBody) -> dict:
    user = _coerce_user(body.model_dump())
    try:
        rt.revoke_consent(run_id, approver=user)
    except Exception as e:
        raise _wrap_runtime_error(e)
    return {"runId": run_id, "state": "revoked"}


# ============================================================
# Tool calls
# ============================================================


class ToolCallBody(BaseModel):
    payload: dict | None = None


@router.post("/runs/{run_id}/tool/{tool_id}")
def call_tool(run_id: str, tool_id: str, body: ToolCallBody) -> dict:
    try:
        return rt.call_tool(
            run_id=run_id, tool_id=tool_id, payload=body.payload or {}
        )
    except Exception as e:
        raise _wrap_runtime_error(e)


# ============================================================
# Approvals
# ============================================================


class ApprovalRequestBody(BaseModel):
    toolId: str
    toolPayload: dict
    action: str
    description: str
    payloadPreview: str
    destination: str
    approverRole: str = "clinician"


@router.post("/runs/{run_id}/approvals")
def request_approval(run_id: str, body: ApprovalRequestBody) -> dict:
    try:
        request = rt.request_outbound_approval(
            run_id=run_id,
            tool_id=body.toolId,
            tool_payload=body.toolPayload,
            action=body.action,  # type: ignore[arg-type]
            description=body.description,
            payload_preview=body.payloadPreview,
            destination=body.destination,
            approver_role=body.approverRole,
        )
    except Exception as e:
        raise _wrap_runtime_error(e)
    return request.model_dump(mode="json")


@router.get("/runs/{run_id}/approvals")
def list_approvals(run_id: str) -> list[dict]:
    return rt.list_approvals(run_id)


class ApprovalDecisionBody(BaseModel):
    user: dict | None = None


@router.post("/runs/{run_id}/approvals/{approval_id}/approve")
def approve_outbound(run_id: str, approval_id: str, body: ApprovalDecisionBody) -> dict:
    user = _coerce_user(body.model_dump())
    try:
        return rt.approve_outbound(approval_id=approval_id, approver=user)
    except Exception as e:
        raise _wrap_runtime_error(e)


@router.post("/runs/{run_id}/approvals/{approval_id}/deny")
def deny_outbound(run_id: str, approval_id: str, body: ApprovalDecisionBody) -> dict:
    user = _coerce_user(body.model_dump())
    try:
        rt.deny_outbound(approval_id=approval_id, approver=user)
    except Exception as e:
        raise _wrap_runtime_error(e)
    return {"approvalId": approval_id, "status": "denied"}


# ============================================================
# Events + provenance
# ============================================================


@router.get("/runs/{run_id}/events")
def list_events(run_id: str) -> list[dict]:
    return rt.list_events(run_id)


@router.get("/runs/{run_id}/provenance")
def list_run_provenance(run_id: str) -> list[dict]:
    return [r.model_dump(mode="json") for r in prov_log.list_records(run_id=run_id)]


@router.get("/{plugin_id}/provenance")
def list_plugin_provenance(plugin_id: str) -> list[dict]:
    return [r.model_dump(mode="json") for r in prov_log.list_records(plugin_id=plugin_id)]
