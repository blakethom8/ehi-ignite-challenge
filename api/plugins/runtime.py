"""Plugin run lifecycle.

State machine:

    awaiting-consent  --grant_consent--> running
    running          --pending outbound--> waiting
    waiting          --approve--> running
    waiting          --deny--> running
    running          --complete--> complete
    running          --revoke_consent--> revoked
    waiting          --revoke_consent--> revoked
    *                --error--> failed

Per HARNESS-SURFACES: the run carries structured canvas state (the
anchor + accumulated tool outputs + pending approvals). The frontend
projects that state into the InspectorPane Context tab and the
WorkbenchPane renderers without re-deriving anything.

Runs are persisted in ``data/runs.db`` (SQLite). A second table holds
the pending + resolved approvals.
"""

from __future__ import annotations

import json
import sqlite3
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from api.plugins import provenance as prov_log
from api.plugins.anchors import (
    AnchorError,
    AnchorExpired,
    compile_anchor_package,
    new_run_id,
    verify_anchor_package,
)
from api.plugins.connectors import UndeclaredConnector
from api.plugins.consent import (
    ConsentError,
    ConsentExpired,
    ConsentRequired,
    mint_consent_token,
    new_approval_id,
    verify_consent_token,
)
from api.plugins.manifest import (
    LoadedManifest,
    PluginManifestError,
    load_all_installed,
    load_manifest,
)
from api.plugins.tools import (
    ApprovalRequired,
    PermissionDenied,
    ToolContext,
    dispatch_tool,
)
from api.trust.keys import REPO_ROOT
from api.trust.models import (
    AnchorPackage,
    ConsentToken,
    OutboundActionKind,
    PluginApprovalRequest,
    PluginManifest,
    RunState,
    UserIdentity,
    VendorIdentity,
)


DEFAULT_DB_PATH = REPO_ROOT / "data" / "runs.db"
_lock = threading.Lock()


# ============================================================
# In-process registry: cached verified manifests
# ============================================================


_manifests_by_id: dict[str, LoadedManifest] = {}


def reload_manifests() -> list[LoadedManifest]:
    """Refresh the in-process manifest cache from disk. Called at app start."""
    global _manifests_by_id
    out: list[LoadedManifest] = []
    for loaded in load_all_installed():
        out.append(loaded)
    _manifests_by_id = {m.manifest.id: m for m in out}
    return out


def installed_manifests() -> list[LoadedManifest]:
    if not _manifests_by_id:
        reload_manifests()
    return list(_manifests_by_id.values())


def get_manifest(plugin_id: str) -> PluginManifest:
    if plugin_id not in _manifests_by_id:
        reload_manifests()
    if plugin_id not in _manifests_by_id:
        raise PluginManifestError(f"plugin not installed: {plugin_id}")
    return _manifests_by_id[plugin_id].manifest


# ============================================================
# SQLite schema
# ============================================================


def _conn(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS runs (
          id TEXT PRIMARY KEY,
          pluginId TEXT NOT NULL,
          pluginVersion TEXT NOT NULL,
          patientId TEXT NOT NULL,
          state TEXT NOT NULL,
          workflowId TEXT,
          title TEXT,
          startedBy TEXT NOT NULL,
          startedAt TEXT NOT NULL,
          completedAt TEXT,
          anchor TEXT,
          consent TEXT,
          canvas TEXT NOT NULL DEFAULT '{}'
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS events (
          id TEXT PRIMARY KEY,
          runId TEXT NOT NULL,
          ts TEXT NOT NULL,
          kind TEXT NOT NULL,
          payload TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS approvals (
          id TEXT PRIMARY KEY,
          runId TEXT NOT NULL,
          pluginId TEXT NOT NULL,
          status TEXT NOT NULL,
          action TEXT NOT NULL,
          description TEXT NOT NULL,
          payloadPreview TEXT NOT NULL,
          destination TEXT NOT NULL,
          redactionPreset TEXT NOT NULL,
          approverRole TEXT NOT NULL,
          toolId TEXT NOT NULL,
          toolPayload TEXT NOT NULL,
          createdAt TEXT NOT NULL,
          resolvedAt TEXT,
          resolvedBy TEXT
        )
        """
    )
    return conn


# ============================================================
# In-process revoked-run set (cached across requests)
# ============================================================

_revoked_ids: set[str] = set()


# ============================================================
# Public API
# ============================================================


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _emit(conn: sqlite3.Connection, run_id: str, kind: str, payload: dict) -> None:
    conn.execute(
        "INSERT INTO events (id, runId, ts, kind, payload) VALUES (?,?,?,?,?)",
        (
            "evt_" + uuid.uuid4().hex[:10],
            run_id,
            _now_iso(),
            kind,
            json.dumps(payload, default=str),
        ),
    )


def _serialize_anchor(anchor: AnchorPackage | None) -> str | None:
    if anchor is None:
        return None
    return json.dumps(anchor.model_dump(mode="json"), default=str)


def _deserialize_anchor(s: str | None) -> AnchorPackage | None:
    if not s:
        return None
    return AnchorPackage.model_validate_json(s)


def _serialize_consent(token: ConsentToken | None) -> str | None:
    if token is None:
        return None
    return json.dumps(token.model_dump(mode="json"), default=str)


def _deserialize_consent(s: str | None) -> ConsentToken | None:
    if not s:
        return None
    return ConsentToken.model_validate_json(s)


@dataclass
class RunRow:
    id: str
    pluginId: str
    pluginVersion: str
    patientId: str
    state: RunState
    workflowId: Optional[str]
    title: Optional[str]
    startedBy: UserIdentity
    startedAt: str
    completedAt: Optional[str]
    anchor: Optional[AnchorPackage]
    consent: Optional[ConsentToken]
    canvas: dict = field(default_factory=dict)


def _row_to_run(row) -> RunRow:
    return RunRow(
        id=row[0],
        pluginId=row[1],
        pluginVersion=row[2],
        patientId=row[3],
        state=row[4],
        workflowId=row[5],
        title=row[6],
        startedBy=UserIdentity.model_validate_json(row[7]),
        startedAt=row[8],
        completedAt=row[9],
        anchor=_deserialize_anchor(row[10]),
        consent=_deserialize_consent(row[11]),
        canvas=json.loads(row[12] or "{}"),
    )


def start_run(
    *,
    plugin_id: str,
    patient_id: str,
    workflow_id: str | None,
    title: str | None,
    user: UserIdentity,
    db_path: Path | None = None,
) -> RunRow:
    manifest = get_manifest(plugin_id)
    run_id = new_run_id()
    anchor = compile_anchor_package(
        manifest=manifest, patient_id=patient_id, run_id=run_id
    )
    state: RunState = (
        "awaiting-consent" if manifest.trust.requiresPerRunConsent else "running"
    )
    with _lock, _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO runs
              (id, pluginId, pluginVersion, patientId, state, workflowId, title,
               startedBy, startedAt, anchor, consent, canvas)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                run_id,
                manifest.id,
                manifest.version,
                patient_id,
                state,
                workflow_id,
                title,
                user.model_dump_json(),
                _now_iso(),
                _serialize_anchor(anchor),
                None,
                "{}",
            ),
        )
        _emit(conn, run_id, "run.started", {
            "pluginId": manifest.id,
            "pluginVersion": manifest.version,
            "workflowId": workflow_id,
            "anchorScope": list(manifest.anchor.scope),
            "redactionPreset": manifest.anchor.redactionPreset,
            "state": state,
        })
    return get_run(run_id, db_path=db_path)


def get_run(run_id: str, *, db_path: Path | None = None) -> RunRow:
    with _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
    if not row:
        raise RuntimeError(f"run not found: {run_id}")
    return _row_to_run(row)


def list_runs_for_plugin(plugin_id: str, *, db_path: Path | None = None) -> list[RunRow]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT * FROM runs WHERE pluginId = ? ORDER BY startedAt DESC",
            (plugin_id,),
        ).fetchall()
    return [_row_to_run(r) for r in rows]


def _update_state(
    conn: sqlite3.Connection, run_id: str, state: RunState, completed: bool = False
) -> None:
    if completed:
        conn.execute(
            "UPDATE runs SET state = ?, completedAt = ? WHERE id = ?",
            (state, _now_iso(), run_id),
        )
    else:
        conn.execute(
            "UPDATE runs SET state = ? WHERE id = ?", (state, run_id)
        )


def grant_consent(
    run_id: str, *, approver: UserIdentity, db_path: Path | None = None
) -> ConsentToken:
    with _lock, _conn(db_path) as conn:
        row = conn.execute("SELECT * FROM runs WHERE id = ?", (run_id,)).fetchone()
        if not row:
            raise RuntimeError(f"run not found: {run_id}")
        run = _row_to_run(row)
        manifest = get_manifest(run.pluginId)
        # Token TTL == anchor TTL so the boundaries align.
        ttl = manifest.anchor.ttlSeconds
        token = mint_consent_token(
            plugin_id=run.pluginId,
            run_id=run.id,
            scope=list(manifest.anchor.scope),
            approver_id=approver.id,
            ttl_seconds=ttl,
        )
        conn.execute(
            "UPDATE runs SET consent = ?, state = ? WHERE id = ?",
            (_serialize_consent(token), "running", run.id),
        )
        _emit(conn, run.id, "run.consent-granted", {
            "approverId": approver.id,
            "approverRole": approver.role,
            "ttlSeconds": ttl,
        })
    return token


def revoke_consent(
    run_id: str, *, approver: UserIdentity, db_path: Path | None = None
) -> None:
    with _lock, _conn(db_path) as conn:
        _update_state(conn, run_id, "revoked")
        # Void all pending approvals on the run.
        conn.execute(
            "UPDATE approvals SET status = 'voided', resolvedAt = ?, resolvedBy = ? "
            "WHERE runId = ? AND status = 'pending'",
            (_now_iso(), approver.id, run_id),
        )
        _emit(conn, run_id, "run.consent-revoked", {"approverId": approver.id})
    _revoked_ids.add(run_id)


def run_canvas_update(
    run_id: str, key: str, value: Any, *, db_path: Path | None = None
) -> None:
    """Append a key/value into the run's canvas state."""
    with _lock, _conn(db_path) as conn:
        row = conn.execute("SELECT canvas FROM runs WHERE id = ?", (run_id,)).fetchone()
        canvas = json.loads(row[0] or "{}") if row else {}
        canvas[key] = value
        conn.execute(
            "UPDATE runs SET canvas = ? WHERE id = ?",
            (json.dumps(canvas, default=str), run_id),
        )


def list_events(run_id: str, *, db_path: Path | None = None) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT id, runId, ts, kind, payload FROM events "
            "WHERE runId = ? ORDER BY ts ASC, id ASC",
            (run_id,),
        ).fetchall()
    return [
        {
            "id": r[0],
            "runId": r[1],
            "ts": r[2],
            "kind": r[3],
            "payload": json.loads(r[4]),
        }
        for r in rows
    ]


# ============================================================
# Approvals
# ============================================================


def request_outbound_approval(
    *,
    run_id: str,
    tool_id: str,
    tool_payload: dict,
    action: OutboundActionKind,
    description: str,
    payload_preview: str,
    destination: str,
    approver_role: str = "clinician",
    db_path: Path | None = None,
) -> PluginApprovalRequest:
    run = get_run(run_id, db_path=db_path)
    manifest = get_manifest(run.pluginId)
    request = PluginApprovalRequest(
        runId=run.id,
        approvalId=new_approval_id(),
        pluginId=manifest.id,
        action=action,
        description=description,
        payloadPreview=payload_preview,
        destination=destination,
        redactionPreset=manifest.anchor.redactionPreset,
        approverRole=approver_role,  # type: ignore[arg-type]
        status="pending",
    )
    with _lock, _conn(db_path) as conn:
        conn.execute(
            """
            INSERT INTO approvals
              (id, runId, pluginId, status, action, description,
               payloadPreview, destination, redactionPreset, approverRole,
               toolId, toolPayload, createdAt)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (
                request.approvalId,
                request.runId,
                request.pluginId,
                "pending",
                request.action,
                request.description,
                request.payloadPreview,
                request.destination,
                request.redactionPreset,
                request.approverRole,
                tool_id,
                json.dumps(tool_payload, default=str),
                _now_iso(),
            ),
        )
        _update_state(conn, run.id, "waiting")
        _emit(conn, run.id, "approval.requested", {
            "approvalId": request.approvalId,
            "action": request.action,
            "destination": request.destination,
            "approverRole": request.approverRole,
        })
    return request


def _load_approval(conn: sqlite3.Connection, approval_id: str) -> dict | None:
    row = conn.execute(
        "SELECT id, runId, pluginId, status, action, description, payloadPreview, "
        "destination, redactionPreset, approverRole, toolId, toolPayload, "
        "createdAt, resolvedAt, resolvedBy "
        "FROM approvals WHERE id = ?",
        (approval_id,),
    ).fetchone()
    if not row:
        return None
    return {
        "id": row[0],
        "runId": row[1],
        "pluginId": row[2],
        "status": row[3],
        "action": row[4],
        "description": row[5],
        "payloadPreview": row[6],
        "destination": row[7],
        "redactionPreset": row[8],
        "approverRole": row[9],
        "toolId": row[10],
        "toolPayload": json.loads(row[11]),
        "createdAt": row[12],
        "resolvedAt": row[13],
        "resolvedBy": row[14],
    }


def list_approvals(run_id: str, *, db_path: Path | None = None) -> list[dict]:
    with _conn(db_path) as conn:
        rows = conn.execute(
            "SELECT id, runId, pluginId, status, action, description, "
            "payloadPreview, destination, redactionPreset, approverRole, "
            "toolId, toolPayload, createdAt, resolvedAt, resolvedBy "
            "FROM approvals WHERE runId = ? ORDER BY createdAt ASC",
            (run_id,),
        ).fetchall()
    out = []
    for row in rows:
        out.append({
            "id": row[0],
            "runId": row[1],
            "pluginId": row[2],
            "status": row[3],
            "action": row[4],
            "description": row[5],
            "payloadPreview": row[6],
            "destination": row[7],
            "redactionPreset": row[8],
            "approverRole": row[9],
            "toolId": row[10],
            "toolPayload": json.loads(row[11]),
            "createdAt": row[12],
            "resolvedAt": row[13],
            "resolvedBy": row[14],
        })
    return out


def approve_outbound(
    *,
    approval_id: str,
    approver: UserIdentity,
    db_path: Path | None = None,
) -> dict:
    """Approve an outbound, run the tool, write provenance, return the result."""
    with _lock, _conn(db_path) as conn:
        appr = _load_approval(conn, approval_id)
        if appr is None:
            raise RuntimeError(f"approval not found: {approval_id}")
        if appr["status"] != "pending":
            raise RuntimeError(f"approval {approval_id} is {appr['status']}")
        run = _row_to_run(
            conn.execute("SELECT * FROM runs WHERE id = ?", (appr["runId"],)).fetchone()
        )
        if run.state == "revoked":
            conn.execute(
                "UPDATE approvals SET status = 'voided', resolvedAt = ?, resolvedBy = ? WHERE id = ?",
                (_now_iso(), approver.id, approval_id),
            )
            raise ConsentError(f"run {run.id} consent revoked; approval voided")
        manifest = get_manifest(run.pluginId)

    # Out of the lock — run the tool.
    ctx = ToolContext(
        manifest=manifest,
        anchor=run.anchor,
        consent=run.consent,
        run_id=run.id,
        revoked_ids=_revoked_ids,
    )
    # Pre-flight: verify the anchor is still valid.
    try:
        verify_anchor_package(ctx.anchor)
    except AnchorExpired:
        raise

    # Pre-flight: re-verify consent.
    if ctx.consent is None:
        raise ConsentRequired("run has no consent token")
    verify_consent_token(
        ctx.consent,
        plugin_id=ctx.manifest.id,
        run_id=ctx.run_id,
        revoked_ids=_revoked_ids,
    )

    result = dispatch_tool(
        tool_id=appr["toolId"],
        ctx=ctx,
        payload=appr["toolPayload"],
        approved_outbound=True,
    )

    # Write provenance.
    vendor = manifest.vendor
    record = prov_log.write_record(
        run_id=run.id,
        plugin_id=manifest.id,
        plugin_version=manifest.version,
        vendor=VendorIdentity(**vendor.model_dump()),
        action=appr["action"],
        approver=approver,
        redaction_preset=manifest.anchor.redactionPreset,
        artifact_id=result.get("artifactId") or appr["toolPayload"].get("artifactId"),
        endpoint=result.get("endpoint", appr["destination"]),
        response_status=result.get("status", 200),
        response_summary=result.get("summary") or json.dumps(result)[:200],
    )

    # Resolve the approval and emit event.
    with _lock, _conn(db_path) as conn:
        conn.execute(
            "UPDATE approvals SET status = 'approved', resolvedAt = ?, resolvedBy = ? WHERE id = ?",
            (_now_iso(), approver.id, approval_id),
        )
        _update_state(conn, run.id, "running")
        _emit(conn, run.id, "approval.approved", {
            "approvalId": approval_id,
            "approverId": approver.id,
            "provenanceId": record.id,
        })
        _emit(conn, run.id, "tool.result", {
            "toolId": appr["toolId"],
            "result": result,
        })
    return {"approval": appr["id"], "result": result, "provenance": record.id}


def deny_outbound(
    *, approval_id: str, approver: UserIdentity, db_path: Path | None = None
) -> None:
    with _lock, _conn(db_path) as conn:
        appr = _load_approval(conn, approval_id)
        if appr is None or appr["status"] != "pending":
            raise RuntimeError(f"approval not pending: {approval_id}")
        conn.execute(
            "UPDATE approvals SET status = 'denied', resolvedAt = ?, resolvedBy = ? WHERE id = ?",
            (_now_iso(), approver.id, approval_id),
        )
        _update_state(conn, appr["runId"], "running")
        _emit(conn, appr["runId"], "approval.denied", {
            "approvalId": approval_id,
            "approverId": approver.id,
        })


# ============================================================
# Direct tool call (non-outbound)
# ============================================================


def call_tool(
    *, run_id: str, tool_id: str, payload: dict, db_path: Path | None = None
) -> dict:
    """Execute a non-outbound tool against the run. Outbound tools
    must be approved through ``request_outbound_approval`` first."""
    run = get_run(run_id, db_path=db_path)
    manifest = get_manifest(run.pluginId)
    ctx = ToolContext(
        manifest=manifest,
        anchor=run.anchor,
        consent=run.consent,
        run_id=run.id,
        revoked_ids=_revoked_ids,
    )
    # Anchor TTL check.
    verify_anchor_package(ctx.anchor)
    result = dispatch_tool(tool_id=tool_id, ctx=ctx, payload=payload)

    with _lock, _conn(db_path) as conn:
        _emit(conn, run.id, "tool.result", {
            "toolId": tool_id,
            "result": result,
        })
    return result


def complete_run(run_id: str, *, db_path: Path | None = None) -> None:
    with _lock, _conn(db_path) as conn:
        _update_state(conn, run_id, "complete", completed=True)
        _emit(conn, run_id, "run.completed", {})


# ============================================================
# Maintenance
# ============================================================


def reset_in_memory_state() -> None:
    """Used by tests to clear cached manifests + revoked set."""
    _manifests_by_id.clear()
    _revoked_ids.clear()
