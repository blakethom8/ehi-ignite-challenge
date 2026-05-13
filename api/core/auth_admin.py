"""Admin + self-service user management.

Backs the ``/api/admin/*`` and ``/api/auth/me/*`` routes:

* Admin: list users, fetch one, patch role/status, delete user, list/revoke
  live sessions, list activity for a user.
* Self-service: rename your display name, rotate your password, list / revoke
  your own sessions, delete your own account.

Depends one-way on :mod:`auth_session` (DB connection + audit + session
constants) and :mod:`auth_account` (password hashing for the self-service
password-change path).
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from datetime import datetime

from fastapi import HTTPException, status

from api.auth_models import AccountSessionSummary, AuthRole
from api.core.auth_account import _hash_password, _verify_password
from api.core.auth_session import (
    SessionPrincipal,
    _VALID_ROLES,
    _connect,
    _now,
    audit_event,
    init_auth_store,
)


@dataclass
class _AdminUserRow:
    id: str
    email: str
    display_name: str
    role: AuthRole
    status: str
    created_at: datetime
    last_login_at: datetime | None


def _row_to_admin_user(row: sqlite3.Row) -> _AdminUserRow:
    last_login_raw = row["last_login_at"]
    return _AdminUserRow(
        id=row["id"],
        email=row["email"],
        display_name=row["display_name"],
        role=row["role"] or "clinician",
        status=row["status"] or "active",
        created_at=datetime.fromisoformat(row["created_at"]),
        last_login_at=datetime.fromisoformat(last_login_raw) if last_login_raw else None,
    )


def admin_list_users() -> list[_AdminUserRow]:
    init_auth_store()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, email, display_name, role, status, created_at, last_login_at
            FROM users
            ORDER BY created_at ASC
            """
        ).fetchall()
    return [_row_to_admin_user(row) for row in rows]


def admin_get_user(user_id: str) -> _AdminUserRow:
    init_auth_store()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, email, display_name, role, status, created_at, last_login_at
            FROM users WHERE id = ?
            """,
            (user_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail=f"Unknown user: {user_id}")
    return _row_to_admin_user(row)


@dataclass
class _AdminAuditEvent:
    id: str
    created_at: datetime
    session_id: str | None
    user_id: str | None
    mode: str | None
    patient_id: str | None
    event_type: str
    payload: dict[str, object]


def admin_list_user_activity(user_id: str, limit: int = 100) -> list[_AdminAuditEvent]:
    init_auth_store()
    bounded = max(1, min(int(limit), 500))
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, created_at, session_id, user_id, mode, patient_id, event_type, payload_json
            FROM audit_events WHERE user_id = ?
            ORDER BY created_at DESC LIMIT ?
            """,
            (user_id, bounded),
        ).fetchall()
    events: list[_AdminAuditEvent] = []
    for row in rows:
        try:
            payload = json.loads(row["payload_json"] or "{}")
        except (TypeError, ValueError):
            payload = {}
        events.append(
            _AdminAuditEvent(
                id=row["id"],
                created_at=datetime.fromisoformat(row["created_at"]),
                session_id=row["session_id"],
                user_id=row["user_id"],
                mode=row["mode"],
                patient_id=row["patient_id"],
                event_type=row["event_type"],
                payload=payload if isinstance(payload, dict) else {},
            )
        )
    return events


def admin_patch_user(
    user_id: str,
    *,
    role: str | None = None,
    status_value: str | None = None,
    caller_user_id: str | None = None,
) -> _AdminUserRow:
    init_auth_store()
    if role is None and status_value is None:
        return admin_get_user(user_id)
    sets: list[str] = []
    params: list[object] = []
    if role is not None:
        normalized = role.strip().lower()
        if normalized not in _VALID_ROLES:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown role: {role}. Must be one of: {sorted(_VALID_ROLES)}.",
            )
        # Lock-out guard — refuse to demote yourself out of admin.
        if (
            caller_user_id is not None
            and caller_user_id == user_id
            and normalized != "admin"
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Refusing to change your own role to non-admin. Use another admin account to do this.",
            )
        sets.append("role = ?")
        params.append(normalized)
    if status_value is not None:
        normalized_status = status_value.strip().lower()
        if normalized_status not in {"active", "disabled"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=f"Unknown status: {status_value}. Must be 'active' or 'disabled'.",
            )
        sets.append("status = ?")
        params.append(normalized_status)
    params.append(user_id)
    with _connect() as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Unknown user: {user_id}")
        conn.execute(
            f"UPDATE users SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        # Disabling an account also revokes any live sessions for it.
        if status_value is not None and status_value.strip().lower() == "disabled":
            conn.execute(
                "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
                (_now().isoformat(), user_id),
            )
        conn.commit()
    audit_event(
        event_type="admin.user_patched",
        payload={
            "target_user_id": user_id,
            "role": role,
            "status": status_value,
            "actor_user_id": caller_user_id,
        },
    )
    return admin_get_user(user_id)


def _revoke_user_sessions(conn: sqlite3.Connection, user_id: str) -> None:
    conn.execute(
        "UPDATE sessions SET revoked_at = ? WHERE user_id = ? AND revoked_at IS NULL",
        (_now().isoformat(), user_id),
    )


def admin_delete_user(user_id: str, *, caller_user_id: str | None = None) -> None:
    init_auth_store()
    if caller_user_id is not None and caller_user_id == user_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Use DELETE /api/auth/me to delete your own account.",
        )
    # Defer the workspace wipe to api.core.aggregation so we don't import-cycle.
    from api.core.aggregation import delete_workspaces_owned_by

    with _connect() as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Unknown user: {user_id}")
        _revoke_user_sessions(conn, user_id)
        conn.execute("DELETE FROM users WHERE id = ?", (user_id,))
        conn.commit()

    workspaces_deleted = delete_workspaces_owned_by(user_id)
    audit_event(
        event_type="admin.user_deleted",
        payload={
            "target_user_id": user_id,
            "actor_user_id": caller_user_id,
            "workspaces_deleted": workspaces_deleted,
        },
    )


@dataclass
class _AdminSessionRow:
    id: str
    mode: str
    user_id: str | None
    user_email: str | None
    user_display_name: str | None
    active_patient_id: str | None
    active_patient_name: str | None
    created_at: datetime
    last_seen_at: datetime
    expires_at: datetime
    user_agent: str | None


def admin_list_sessions() -> list[_AdminSessionRow]:
    init_auth_store()
    now = _now().isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT s.*, u.email AS user_email, u.display_name AS user_display_name
            FROM sessions s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.revoked_at IS NULL AND s.expires_at > ?
            ORDER BY s.last_seen_at DESC
            """,
            (now,),
        ).fetchall()
    sessions: list[_AdminSessionRow] = []
    for row in rows:
        sessions.append(
            _AdminSessionRow(
                id=row["id"],
                mode=row["mode"],
                user_id=row["user_id"],
                user_email=row["user_email"],
                user_display_name=row["user_display_name"],
                active_patient_id=row["active_patient_id"],
                active_patient_name=row["active_patient_name"],
                created_at=datetime.fromisoformat(row["created_at"]),
                last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
                expires_at=datetime.fromisoformat(row["expires_at"]),
                user_agent=row["user_agent"],
            )
        )
    return sessions


def admin_revoke_session(session_id: str, *, caller_user_id: str | None = None) -> None:
    init_auth_store()
    with _connect() as conn:
        row = conn.execute(
            "SELECT id, revoked_at FROM sessions WHERE id = ?",
            (session_id,),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail=f"Unknown session: {session_id}")
        if row["revoked_at"] is not None:
            return
        conn.execute(
            "UPDATE sessions SET revoked_at = ? WHERE id = ?",
            (_now().isoformat(), session_id),
        )
        conn.commit()
    audit_event(
        event_type="admin.session_revoked",
        payload={"target_session_id": session_id, "actor_user_id": caller_user_id},
    )


# --- self-service ----------------------------------------------------------


def update_own_display_name(user_id: str, display_name: str) -> _AdminUserRow:
    init_auth_store()
    normalized = display_name.strip()
    if not normalized:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Display name is required.",
        )
    with _connect() as conn:
        row = conn.execute("SELECT id FROM users WHERE id = ?", (user_id,)).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Account not found.")
        conn.execute(
            "UPDATE users SET display_name = ? WHERE id = ?", (normalized, user_id)
        )
        conn.commit()
    audit_event(
        event_type="account.display_name_changed",
        payload={"user_id": user_id, "display_name": normalized},
    )
    return admin_get_user(user_id)


def change_own_password(
    user_id: str,
    current_password: str,
    new_password: str,
    *,
    keep_session_id: str,
) -> None:
    init_auth_store()
    if len(new_password) < 8:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="New password must be at least 8 characters.",
        )
    with _connect() as conn:
        row = conn.execute(
            "SELECT password_hash FROM users WHERE id = ?", (user_id,)
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Account not found.")
        if not _verify_password(current_password, row["password_hash"]):
            audit_event(
                event_type="account.password_change_failed",
                payload={"user_id": user_id},
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Current password did not match.",
            )
        conn.execute(
            "UPDATE users SET password_hash = ? WHERE id = ?",
            (_hash_password(new_password), user_id),
        )
        # Revoke every other live session for this user; keep the caller's.
        conn.execute(
            """
            UPDATE sessions SET revoked_at = ?
            WHERE user_id = ? AND revoked_at IS NULL AND id != ?
            """,
            (_now().isoformat(), user_id, keep_session_id),
        )
        conn.commit()
    audit_event(
        event_type="account.password_changed",
        payload={"user_id": user_id},
    )


def list_own_sessions(user_id: str, *, current_session_id: str) -> list[AccountSessionSummary]:
    init_auth_store()
    now = _now().isoformat()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id, mode, active_patient_id, active_patient_name, created_at,
                   last_seen_at, expires_at, user_agent
            FROM sessions
            WHERE user_id = ? AND revoked_at IS NULL AND expires_at > ?
            ORDER BY last_seen_at DESC
            """,
            (user_id, now),
        ).fetchall()
    return [
        AccountSessionSummary(
            id=row["id"],
            mode="authenticated",
            is_current=row["id"] == current_session_id,
            active_patient_id=row["active_patient_id"],
            active_patient_name=row["active_patient_name"],
            created_at=datetime.fromisoformat(row["created_at"]),
            last_seen_at=datetime.fromisoformat(row["last_seen_at"]),
            expires_at=datetime.fromisoformat(row["expires_at"]),
            user_agent=row["user_agent"],
        )
        for row in rows
    ]


def revoke_own_session(
    user_id: str,
    session_id: str,
    *,
    current_session_id: str,
) -> None:
    init_auth_store()
    if session_id == current_session_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Use sign out to end the current session.",
        )
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, active_patient_id
            FROM sessions
            WHERE id = ? AND user_id = ? AND revoked_at IS NULL
            """,
            (session_id, user_id),
        ).fetchone()
        if row is None:
            raise HTTPException(status_code=404, detail="Session not found.")
        conn.execute(
            "UPDATE sessions SET revoked_at = ? WHERE id = ?",
            (_now().isoformat(), session_id),
        )
        conn.commit()
    audit_event(
        event_type="account.session_revoked",
        payload={
            "user_id": user_id,
            "target_session_id": session_id,
            "patient_id": row["active_patient_id"],
        },
    )


def revoke_other_sessions(user_id: str, *, keep_session_id: str) -> int:
    init_auth_store()
    with _connect() as conn:
        rows = conn.execute(
            """
            SELECT id
            FROM sessions
            WHERE user_id = ? AND revoked_at IS NULL AND id != ?
            """,
            (user_id, keep_session_id),
        ).fetchall()
        conn.execute(
            """
            UPDATE sessions SET revoked_at = ?
            WHERE user_id = ? AND revoked_at IS NULL AND id != ?
            """,
            (_now().isoformat(), user_id, keep_session_id),
        )
        conn.commit()
    revoked_count = len(rows)
    audit_event(
        event_type="account.other_sessions_revoked",
        payload={"user_id": user_id, "revoked_count": revoked_count},
    )
    return revoked_count


def delete_own_account(principal: SessionPrincipal) -> int:
    """Delete the caller's account with full cascade. Returns workspaces removed."""
    if principal.user_id is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only authenticated accounts can be deleted.",
        )
    from api.core.aggregation import delete_workspaces_owned_by

    init_auth_store()
    with _connect() as conn:
        _revoke_user_sessions(conn, principal.user_id)
        conn.execute("DELETE FROM users WHERE id = ?", (principal.user_id,))
        conn.commit()
    workspaces_deleted = delete_workspaces_owned_by(principal.user_id)
    audit_event(
        event_type="account.self_deleted",
        payload={
            "user_id": principal.user_id,
            "workspaces_deleted": workspaces_deleted,
        },
    )
    return workspaces_deleted
