"""Per-user audit timeline.

H0.6 endpoint. Joins three audit stores by user_id and ts, returning a
single chronological timeline:

- ``api/workspace/events.py`` — explicit user actions (chat turns, skill
  runs, plugin consent + tool calls + approvals)
- ``api/core/tracing.py`` (``traces.db``) — LLM/tool spans tagged with
  user_id since H0.4 added the column
- ``api/plugins/provenance.py`` (``provenance.db``) — signed records of
  every outbound plugin action (joined by approver id)

Auth model mirrors /api/traces: bearer token, required in production.
"""

from __future__ import annotations

import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from api.core.auth import current_session
from api.core.tracing import query_traces
from api.plugins import provenance as prov_log
from api.workspace.events import query_events

router = APIRouter(prefix="/audit", tags=["audit"])

_AUDIT_API_TOKEN = os.getenv("AUDIT_API_TOKEN", "").strip()
_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").strip().lower()


def _is_production() -> bool:
    return _ENVIRONMENT in {"prod", "production"}


def _assert_authorized(request: Request) -> None:
    if _is_production() and not _AUDIT_API_TOKEN:
        raise HTTPException(
            status_code=503,
            detail="Audit API requires AUDIT_API_TOKEN in production.",
        )
    if _AUDIT_API_TOKEN:
        expected = f"Bearer {_AUDIT_API_TOKEN}"
        provided = request.headers.get("Authorization", "")
        if not secrets.compare_digest(provided, expected):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid audit API token.",
            )


def _parse_window(
    since: str | None, until: str | None, default_hours: float = 1.0
) -> tuple[datetime, datetime]:
    until_dt = (
        datetime.fromisoformat(until.replace("Z", "+00:00")) if until
        else datetime.now(timezone.utc)
    )
    since_dt = (
        datetime.fromisoformat(since.replace("Z", "+00:00")) if since
        else until_dt - timedelta(hours=default_hours)
    )
    if since_dt.tzinfo is None:
        since_dt = since_dt.replace(tzinfo=timezone.utc)
    if until_dt.tzinfo is None:
        until_dt = until_dt.replace(tzinfo=timezone.utc)
    return since_dt, until_dt


def _trace_to_timeline_entry(t: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "trace",
        "source": "traces.db",
        "ts": t.get("created_at"),
        "user_id": t.get("user_id", ""),
        "session_id": t.get("session_id", ""),
        "workspace_kind": t.get("workspace_kind") or "caspian",
        "event_type": "trace.flushed",
        "target_id": t.get("trace_id"),
        "summary": (t.get("question") or "")[:120],
        "payload": {
            "engine": t.get("engine"),
            "status": t.get("status"),
            "patient_id": t.get("patient_id"),
            "duration_ms": t.get("duration_ms"),
            "answer_length": t.get("answer_length"),
            "citation_count": t.get("citation_count"),
        },
    }


def _event_to_timeline_entry(e: dict[str, Any]) -> dict[str, Any]:
    return {
        "kind": "event",
        "source": "events.db",
        "ts": e["ts"],
        "user_id": e["user_id"],
        "session_id": e["session_id"],
        "workspace_kind": e["workspace_kind"],
        "event_type": e["event_type"],
        "target_id": e["target_id"],
        "summary": e["event_type"],
        "payload": e["payload"],
    }


def _provenance_to_timeline_entry(p) -> dict[str, Any]:
    """Map a ProvenanceRecord (signed plugin outbound action) into the
    timeline shape, keyed on the approver's user identity."""
    approver = getattr(p, "approver", None)
    return {
        "kind": "provenance",
        "source": "provenance.db",
        "ts": str(p.ts),
        "user_id": getattr(approver, "id", "") if approver else "",
        "session_id": "",
        "workspace_kind": "plugin",
        "event_type": f"outbound.{p.action}",
        "target_id": getattr(p, "artifactId", "") or p.runId,
        "summary": (p.responseSummary or "")[:120],
        "payload": {
            "pluginId": p.pluginId,
            "pluginVersion": p.pluginVersion,
            "vendorId": getattr(p.vendor, "id", "") if p.vendor else "",
            "endpoint": p.endpoint,
            "responseStatus": p.responseStatus,
            "redactionPreset": p.redactionPreset,
            "provenanceId": p.id,
            "runId": p.runId,
        },
    }


def _provenance_for_user(
    user_id: str, since_dt: datetime, until_dt: datetime
) -> list[dict[str, Any]]:
    """Filter the global provenance log down to records this user approved
    inside the time window. Provenance is small, so a full scan + filter is
    fine for v1."""
    out: list[dict[str, Any]] = []
    try:
        records = prov_log.list_records()
    except Exception:
        return out
    for r in records:
        approver = getattr(r, "approver", None)
        if approver is None or getattr(approver, "id", "") != user_id:
            continue
        try:
            ts = (
                r.ts
                if isinstance(r.ts, datetime)
                else datetime.fromisoformat(str(r.ts).replace("Z", "+00:00"))
            )
        except Exception:
            continue
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        if since_dt <= ts <= until_dt:
            out.append(_provenance_to_timeline_entry(r))
    return out


@router.get("/users/{user_id}")
def get_user_timeline(
    user_id: str,
    request: Request,
    since: str | None = Query(None, description="ISO 8601; defaults to 1h ago"),
    until: str | None = Query(None, description="ISO 8601; defaults to now"),
    workspace_kind: str | None = Query(
        None, description="Filter to one of: caspian | skill | plugin"
    ),
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    """Unified per-user timeline.

    Returns events + traces + provenance for ``user_id`` inside the window,
    sorted chronologically. Bearer-token gated; required in production.
    """
    _assert_authorized(request)
    since_dt, until_dt = _parse_window(since, until)

    events = query_events(
        user_id=user_id,
        workspace_kind=workspace_kind,
        since=since_dt,
        until=until_dt,
        limit=limit,
    )
    timeline = [_event_to_timeline_entry(e) for e in events]

    # Traces — only when workspace_kind isn't filtering them out.
    if workspace_kind is None or workspace_kind in {"caspian", "skill", "plugin"}:
        try:
            traces = query_traces(limit=limit)
        except Exception:
            traces = []
        for t in traces:
            if t.get("user_id") != user_id:
                continue
            if workspace_kind and (t.get("workspace_kind") or "caspian") != workspace_kind:
                continue
            ts_str = t.get("created_at") or ""
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except ValueError:
                continue
            if ts.tzinfo is None:
                ts = ts.replace(tzinfo=timezone.utc)
            if since_dt <= ts <= until_dt:
                timeline.append(_trace_to_timeline_entry(t))

    if workspace_kind is None or workspace_kind == "plugin":
        timeline.extend(_provenance_for_user(user_id, since_dt, until_dt))

    timeline.sort(key=lambda e: e.get("ts") or "")
    return {
        "user_id": user_id,
        "since": since_dt.isoformat(),
        "until": until_dt.isoformat(),
        "count": len(timeline),
        "workspace_kind_filter": workspace_kind,
        "timeline": timeline[:limit],
    }


@router.get("/me")
def get_my_timeline(
    request: Request,
    since: str | None = Query(None),
    until: str | None = Query(None),
    workspace_kind: str | None = Query(None),
    limit: int = Query(500, ge=1, le=2000),
) -> dict:
    """Self-service timeline for the currently signed-in user.

    Unlike /users/{id}, this requires a valid session (not the admin
    token). Returns 401 for unauthenticated callers.
    """
    session = current_session(request)
    if session is None or not session.user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in to view your activity timeline.",
        )
    since_dt, until_dt = _parse_window(since, until)
    events = query_events(
        user_id=session.user_id,
        workspace_kind=workspace_kind,
        since=since_dt,
        until=until_dt,
        limit=limit,
    )
    return {
        "user_id": session.user_id,
        "since": since_dt.isoformat(),
        "until": until_dt.isoformat(),
        "count": len(events),
        "timeline": [_event_to_timeline_entry(e) for e in events],
    }
