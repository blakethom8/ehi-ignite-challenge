"""Unified workspace event log.

Every meaningful action across Caspian (assistant + skills) and plugins
writes one row here via ``record_event()``. The per-user audit query
(api/routers/audit.py, H0.6) joins this against traces.db and
provenance.db to render a single chronological timeline of "everything
user X did in the last hour" — across all three workspace surfaces.

Schema:
  event_id         TEXT PRIMARY KEY  (e_xxxxxxxxxxxxxx)
  ts               TEXT NOT NULL     (ISO 8601 UTC, second precision)
  user_id          TEXT NOT NULL DEFAULT ''
  session_id       TEXT NOT NULL DEFAULT ''
  workspace_kind   TEXT NOT NULL     (caspian | skill | plugin)
  event_type       TEXT NOT NULL     (chat.turn | run.started | consent.granted ...)
  target_id        TEXT NOT NULL DEFAULT ''  (run_id, tool_id, patient_id, etc.)
  payload_json     TEXT NOT NULL DEFAULT '{}'
  parent_event_id  TEXT              (optional — for threading related events)
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DB_PATH = Path(
    os.getenv("EVENTS_DB_PATH", str(REPO_ROOT / "data" / "events.db"))
)

# PII-by-default: every payload runs through this redaction preset before
# the row is written. ``events-strict`` strips direct identifiers and
# scrubs free-text fields (question_preview, message, brief...) where
# clinician-typed PHI tends to land. Set to ``minimal`` in dev when you
# need to see what got logged.
EVENTS_REDACTION_PRESET = os.getenv("EVENTS_REDACTION_PRESET", "events-strict").strip()

# Workspace-kind tags, mirrored from api.core.tracing so callers can import
# from a single place.
WORKSPACE_CASPIAN = "caspian"
WORKSPACE_SKILL = "skill"
WORKSPACE_PLUGIN = "plugin"

_init_lock = threading.Lock()
_initialized_paths: set[str] = set()


def _conn(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or DEFAULT_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def _ensure_schema(db_path: Path | None = None) -> None:
    path = str(db_path or DEFAULT_DB_PATH)
    if path in _initialized_paths:
        return
    with _init_lock:
        if path in _initialized_paths:
            return
        conn = _conn(db_path)
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS events (
                  event_id        TEXT PRIMARY KEY,
                  ts              TEXT NOT NULL,
                  user_id         TEXT NOT NULL DEFAULT '',
                  session_id      TEXT NOT NULL DEFAULT '',
                  workspace_kind  TEXT NOT NULL,
                  event_type      TEXT NOT NULL,
                  target_id       TEXT NOT NULL DEFAULT '',
                  payload_json    TEXT NOT NULL DEFAULT '{}',
                  parent_event_id TEXT
                );
                CREATE INDEX IF NOT EXISTS idx_events_user_ts
                    ON events(user_id, ts);
                CREATE INDEX IF NOT EXISTS idx_events_session
                    ON events(session_id);
                CREATE INDEX IF NOT EXISTS idx_events_kind_type
                    ON events(workspace_kind, event_type);
                CREATE INDEX IF NOT EXISTS idx_events_target
                    ON events(target_id);
                CREATE INDEX IF NOT EXISTS idx_events_ts ON events(ts);
                """
            )
        finally:
            conn.close()
        _initialized_paths.add(path)


def _now_iso() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _redact_payload(payload: dict[str, Any] | None) -> dict[str, Any]:
    """Apply EVENTS_REDACTION_PRESET. If the preset misfires, drop the
    payload rather than leaking it — the event row still gets recorded."""
    if not payload:
        return {}
    try:
        from api.trust.redactions import apply_preset

        return apply_preset(EVENTS_REDACTION_PRESET, payload)
    except Exception:
        import logging

        logging.getLogger(__name__).warning(
            "events redaction preset %r failed; dropping payload",
            EVENTS_REDACTION_PRESET,
        )
        return {"_redaction_error": "preset-failed"}


def record_event(
    *,
    user_id: str,
    session_id: str,
    workspace_kind: str,
    event_type: str,
    target_id: str = "",
    payload: dict[str, Any] | None = None,
    parent_event_id: str | None = None,
    db_path: Path | None = None,
) -> str:
    """Append one row to the unified events log. Returns the event_id.

    Best-effort: a database failure logs and returns an empty string rather
    than raising — audit must not break the request path.
    """
    try:
        _ensure_schema(db_path)
        event_id = "e_" + uuid.uuid4().hex[:14]
        redacted = _redact_payload(payload)
        conn = _conn(db_path)
        try:
            conn.execute(
                """INSERT INTO events
                   (event_id, ts, user_id, session_id, workspace_kind, event_type,
                    target_id, payload_json, parent_event_id)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    event_id,
                    _now_iso(),
                    user_id or "",
                    session_id or "",
                    workspace_kind,
                    event_type,
                    target_id or "",
                    json.dumps(redacted, default=str),
                    parent_event_id,
                ),
            )
        finally:
            conn.close()
        return event_id
    except Exception:
        import logging

        logging.getLogger(__name__).exception(
            "record_event failed (kind=%s type=%s target=%s)",
            workspace_kind,
            event_type,
            target_id,
        )
        return ""


def record_event_for_session(
    session: Any,
    *,
    workspace_kind: str,
    event_type: str,
    target_id: str = "",
    payload: dict[str, Any] | None = None,
    parent_event_id: str | None = None,
    db_path: Path | None = None,
) -> str:
    """Convenience wrapper — pulls user_id/session_id off a SessionPrincipal.

    Tolerates None (returns empty string without writing) so callers in
    test paths or unauthenticated surfaces don't have to guard.
    """
    if session is None:
        return ""
    return record_event(
        user_id=getattr(session, "user_id", "") or "",
        session_id=getattr(session, "session_id", "") or "",
        workspace_kind=workspace_kind,
        event_type=event_type,
        target_id=target_id,
        payload=payload,
        parent_event_id=parent_event_id,
        db_path=db_path,
    )


def query_events(
    *,
    user_id: str | None = None,
    session_id: str | None = None,
    workspace_kind: str | None = None,
    since: datetime | None = None,
    until: datetime | None = None,
    limit: int = 200,
    db_path: Path | None = None,
) -> list[dict[str, Any]]:
    """Read events filtered by user/session/kind/time. Used by H0.6's
    audit endpoint plus tests."""
    _ensure_schema(db_path)
    conditions: list[str] = []
    params: list[Any] = []
    if user_id is not None:
        conditions.append("user_id = ?")
        params.append(user_id)
    if session_id is not None:
        conditions.append("session_id = ?")
        params.append(session_id)
    if workspace_kind is not None:
        conditions.append("workspace_kind = ?")
        params.append(workspace_kind)
    # Normalize to second-precision Z-suffixed strings so lexicographic SQL
    # compare matches the canonical _now_iso() format. Without this, an
    # `until` with microseconds (e.g. `...55.561415Z`) sorts BEFORE a
    # whole-second event (`...55Z`) because '.' < 'Z'.
    if since is not None:
        conditions.append("ts >= ?")
        params.append(
            since.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
    if until is not None:
        conditions.append("ts <= ?")
        params.append(
            until.replace(microsecond=0).isoformat().replace("+00:00", "Z")
        )
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM events {where} ORDER BY ts ASC, event_id ASC LIMIT ?"
    params.append(limit)

    conn = _conn(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(sql, params).fetchall()
    finally:
        conn.close()
    return [
        {
            "event_id": r["event_id"],
            "ts": r["ts"],
            "user_id": r["user_id"],
            "session_id": r["session_id"],
            "workspace_kind": r["workspace_kind"],
            "event_type": r["event_type"],
            "target_id": r["target_id"],
            "payload": json.loads(r["payload_json"] or "{}"),
            "parent_event_id": r["parent_event_id"],
        }
        for r in rows
    ]
