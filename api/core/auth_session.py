"""Session cookie / token mechanics, session principal model, audit log.

This is the load-bearing core of the auth stack:

* :class:`SessionPrincipal` — request-bound dataclass surfaced to routers.
* Cookie signing / verification (HMAC over the random session id).
* SQLite-backed sessions table — create / lookup / refresh / revoke.
* :func:`current_session` and the guest-cookie adapter used by routers.
* The role-gating ``require_*`` dependencies + the ``audit_event`` writer.

Module-level configuration (``AUTH_DB_PATH``, ``SESSION_SECRET_PATH``, idle /
max session windows, the cookie name, the secure flag) lives on the
:mod:`api.core.auth` facade so existing tests that
``monkeypatch.setattr(auth, "AUTH_DB_PATH", …)`` continue to work — readers
here look the values up on the facade module at call time.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import secrets
import sqlite3
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Callable, Literal

from fastapi import Depends, HTTPException, Request, Response, status

from api.auth_models import (
    AuthRole,
    AuthSessionResponse,
    AuthUserResponse,
)
from api.core import auth as _facade  # late-lookup target for module constants
from api.core.aggregation import list_upload_workspaces
from api.core.auth_demo import (
    DEMO_PATIENT_BY_ALIAS,
    demo_patient_label,
    demo_patient_option,
    demo_patient_options,
    is_demo_alias,
)
from api.core.loader import path_from_patient_id
from api.settings import get_settings
from api.trust.models import UserIdentity


_VALID_ROLES: frozenset[str] = frozenset(
    {"consumer", "clinician", "attending", "coordinator", "admin"}
)


@dataclass
class SessionPrincipal:
    session_id: str
    mode: Literal["demo", "authenticated", "guest"]
    user_id: str | None
    email: str | None
    display_name: str | None
    role: AuthRole
    active_patient_id: str | None
    active_patient_name: str | None
    expires_at: datetime
    guest_run_ids: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_demo(self) -> bool:
        return self.mode == "demo"

    @property
    def is_authenticated(self) -> bool:
        return self.mode == "authenticated"

    @property
    def is_guest(self) -> bool:
        return self.mode == "guest"

    def to_response(self) -> AuthSessionResponse:
        user = None
        if self.user_id and self.email and self.display_name:
            user = AuthUserResponse(
                id=self.user_id,
                email=self.email,
                display_name=self.display_name,
                role=self.role,
            )
        return AuthSessionResponse(
            mode=self.mode,
            user=user,
            active_patient_id=self.active_patient_id,
            active_patient_name=self.active_patient_name,
            active_demo_patient=demo_patient_option(self.active_patient_id),
            expires_at=self.expires_at,
            available_demo_patients=demo_patient_options(),
        )

    def to_user_identity(self) -> UserIdentity:
        if self.user_id and self.display_name:
            return UserIdentity(id=self.user_id, name=self.display_name, role=self.role)
        return UserIdentity(id="demo-clinician", name="Demo Clinician", role="clinician")


def _now() -> datetime:
    return datetime.now(UTC)


def _ensure_parent(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)


def _is_production() -> bool:
    return get_settings().is_production


def _session_secret() -> bytes:
    override = (get_settings().ehi_session_secret or "").strip()
    if override:
        return override.encode("utf-8")
    if _is_production():
        raise RuntimeError(
            "EHI_SESSION_SECRET env var is required when ENVIRONMENT=production. "
            "Refusing to fall back to data/atlas-session.key — session signing "
            "secrets must not live as a plaintext file on disk in production."
        )
    secret_path: Path = _facade.SESSION_SECRET_PATH
    _ensure_parent(secret_path)
    if secret_path.exists():
        return secret_path.read_bytes()
    secret = secrets.token_bytes(32)
    secret_path.write_bytes(secret)
    return secret


def _sign_session_id(session_id: str) -> str:
    signature = hmac.new(_session_secret(), session_id.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{session_id}.{signature}"


def _unsign_cookie_value(raw: str | None) -> str | None:
    if not raw or "." not in raw:
        return None
    session_id, signature = raw.rsplit(".", 1)
    expected = hmac.new(_session_secret(), session_id.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(signature, expected):
        return None
    return session_id


def _ip_hash(request: Request | None) -> str | None:
    if request is None or request.client is None or not request.client.host:
        return None
    return hashlib.sha256(request.client.host.encode("utf-8")).hexdigest()


def _user_agent(request: Request | None) -> str | None:
    if request is None:
        return None
    raw = request.headers.get("user-agent", "").strip()
    return raw[:255] if raw else None


def _connect() -> sqlite3.Connection:
    auth_db_path: Path = _facade.AUTH_DB_PATH
    _ensure_parent(auth_db_path)
    conn = sqlite3.connect(auth_db_path, detect_types=sqlite3.PARSE_DECLTYPES)
    conn.row_factory = sqlite3.Row
    return conn


def init_auth_store() -> None:
    with _connect() as conn:
        conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS users (
                id TEXT PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                display_name TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'clinician',
                password_hash TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'active',
                created_at TEXT NOT NULL,
                last_login_at TEXT
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                mode TEXT NOT NULL,
                user_id TEXT,
                active_patient_id TEXT,
                active_patient_name TEXT,
                created_at TEXT NOT NULL,
                last_seen_at TEXT NOT NULL,
                expires_at TEXT NOT NULL,
                revoked_at TEXT,
                user_agent TEXT,
                ip_address_hash TEXT,
                FOREIGN KEY(user_id) REFERENCES users(id)
            );

            CREATE TABLE IF NOT EXISTS audit_events (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                session_id TEXT,
                user_id TEXT,
                mode TEXT,
                patient_id TEXT,
                event_type TEXT NOT NULL,
                payload_json TEXT NOT NULL
            );
            """
        )
        conn.commit()
    _seed_bootstrap_user()


def _seed_bootstrap_user() -> None:
    # Lazy import to avoid the auth_account ↔ auth_session import cycle.
    from api.core.auth_account import _hash_password

    settings = get_settings()
    email = (settings.ehi_auth_bootstrap_email or "clinician@atlas.local").strip().lower()
    password = (settings.ehi_auth_bootstrap_password or "").strip()
    display_name = (settings.ehi_auth_bootstrap_name or "Atlas Clinician").strip() or "Atlas Clinician"
    role_raw = (settings.ehi_auth_bootstrap_role or "clinician").strip().lower()
    role = role_raw if role_raw in _VALID_ROLES else "clinician"
    if not password:
        if settings.is_production:
            return
        password = "atlas-demo-password"

    with _connect() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing is not None:
            return
        conn.execute(
            """
            INSERT INTO users (id, email, display_name, role, password_hash, status, created_at)
            VALUES (?, ?, ?, ?, ?, 'active', ?)
            """,
            (
                f"user_{uuid.uuid4().hex[:12]}",
                email,
                display_name,
                role,
                _hash_password(password),
                _now().isoformat(),
            ),
        )
        conn.commit()


def _known_patient_name(patient_id: str) -> str | None:
    if is_demo_alias(patient_id):
        return demo_patient_label(patient_id)
    for item in list_upload_workspaces():
        if item.id == patient_id:
            return item.name
    path = path_from_patient_id(patient_id)
    if path is None:
        return None
    stem = path.stem
    parts = stem.split("_")
    if len(parts) >= 2:
        first = "".join(ch for ch in parts[0] if not ch.isdigit()).strip()
        last = "".join(ch for ch in parts[1] if not ch.isdigit()).strip()
        label = f"{first} {last}".strip()
        return label or stem
    return stem


def patient_exists(patient_id: str) -> bool:
    if is_demo_alias(patient_id):
        return True
    if path_from_patient_id(patient_id) is not None:
        return True
    return any(item.id == patient_id for item in list_upload_workspaces())


def _accessible_authenticated_workspace_ids(user_id: str | None) -> set[str]:
    if not user_id:
        return set()
    return {item.id for item in list_upload_workspaces(user_id=user_id)}


def _authenticated_workspace_access_allowed(user_id: str | None, patient_id: str | None) -> bool:
    if not user_id or not patient_id:
        return False
    return patient_id in _accessible_authenticated_workspace_ids(user_id)


def _session_patient_allowed(mode: str, user_id: str | None, patient_id: str | None) -> bool:
    if patient_id is None:
        return True
    if mode == "demo":
        return patient_id in DEMO_PATIENT_BY_ALIAS
    if mode == "authenticated":
        # Route through the facade so tests that
        # ``monkeypatch.setattr(auth, "_authenticated_workspace_access_allowed", …)``
        # (see ``api/tests/conftest.py::_allow_test_workspace_ids``) still hook
        # every call site without us having to drag the patch into a new module.
        return _facade._authenticated_workspace_access_allowed(user_id, patient_id)
    return False


def _row_to_principal(row: sqlite3.Row) -> SessionPrincipal:
    return SessionPrincipal(
        session_id=row["id"],
        mode=row["mode"],
        user_id=row["user_id"],
        email=row["email"],
        display_name=row["display_name"],
        role=row["role"] or "clinician",
        active_patient_id=row["active_patient_id"],
        active_patient_name=row["active_patient_name"],
        expires_at=datetime.fromisoformat(row["expires_at"]),
    )


def _create_session(
    *,
    mode: Literal["demo", "authenticated"],
    user_id: str | None,
    active_patient_id: str | None,
    active_patient_name: str | None,
    request: Request | None,
) -> SessionPrincipal:
    session_id = f"sess_{uuid.uuid4().hex}"
    now = _now()
    expires_at = now + min(
        timedelta(hours=_facade.SESSION_IDLE_HOURS),
        timedelta(days=_facade.SESSION_MAX_DAYS),
    )
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO sessions (
                id, mode, user_id, active_patient_id, active_patient_name,
                created_at, last_seen_at, expires_at, user_agent, ip_address_hash
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                session_id,
                mode,
                user_id,
                active_patient_id,
                active_patient_name,
                now.isoformat(),
                now.isoformat(),
                expires_at.isoformat(),
                _user_agent(request),
                _ip_hash(request),
            ),
        )
        if user_id:
            conn.execute(
                "UPDATE users SET last_login_at = ? WHERE id = ?",
                (now.isoformat(), user_id),
            )
        conn.commit()
        row = conn.execute(
            """
            SELECT s.*, u.email, u.display_name, COALESCE(u.role, 'clinician') AS role
            FROM sessions s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.id = ?
            """,
            (session_id,),
        ).fetchone()
    if row is None:
        raise RuntimeError("Failed to create session.")
    principal = _row_to_principal(row)
    audit_event(
        event_type="session.created",
        session=principal,
        patient_id=active_patient_id,
        payload={"mode": mode},
    )
    return principal


def set_session_cookie(response: Response, session_id: str) -> None:
    response.set_cookie(
        key=_facade.SESSION_COOKIE_NAME,
        value=_sign_session_id(session_id),
        httponly=True,
        secure=_facade.SESSION_SECURE,
        samesite="lax",
        max_age=int(timedelta(days=_facade.SESSION_MAX_DAYS).total_seconds()),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=_facade.SESSION_COOKIE_NAME, path="/")


def audit_event(
    *,
    event_type: str,
    session: SessionPrincipal | None = None,
    patient_id: str | None = None,
    payload: dict[str, object] | None = None,
) -> None:
    init_auth_store()
    with _connect() as conn:
        conn.execute(
            """
            INSERT INTO audit_events (id, created_at, session_id, user_id, mode, patient_id, event_type, payload_json)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                f"audit_{uuid.uuid4().hex}",
                _now().isoformat(),
                session.session_id if session else None,
                session.user_id if session else None,
                session.mode if session else None,
                patient_id,
                event_type,
                json.dumps(payload or {}, sort_keys=True),
            ),
        )
        conn.commit()


def _lookup_session(session_id: str) -> SessionPrincipal | None:
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT s.*, u.email, u.display_name, COALESCE(u.role, 'clinician') AS role
            FROM sessions s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.id = ? AND s.revoked_at IS NULL
            """,
            (session_id,),
        ).fetchone()
        if row is None:
            return None
        expires_at = datetime.fromisoformat(row["expires_at"])
        if expires_at <= _now():
            conn.execute("UPDATE sessions SET revoked_at = ? WHERE id = ?", (_now().isoformat(), session_id))
            conn.commit()
            return None
        refreshed = min(
            _now() + timedelta(hours=_facade.SESSION_IDLE_HOURS),
            datetime.fromisoformat(row["created_at"]) + timedelta(days=_facade.SESSION_MAX_DAYS),
        )
        conn.execute(
            "UPDATE sessions SET last_seen_at = ?, expires_at = ? WHERE id = ?",
            (_now().isoformat(), refreshed.isoformat(), session_id),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT s.*, u.email, u.display_name, COALESCE(u.role, 'clinician') AS role
            FROM sessions s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.id = ?
            """,
            (session_id,),
        ).fetchone()
        if row is not None and not _session_patient_allowed(
            row["mode"],
            row["user_id"],
            row["active_patient_id"],
        ):
            conn.execute(
                "UPDATE sessions SET active_patient_id = NULL, active_patient_name = NULL WHERE id = ?",
                (session_id,),
            )
            conn.commit()
            row = conn.execute(
                """
                SELECT s.*, u.email, u.display_name, COALESCE(u.role, 'clinician') AS role
                FROM sessions s
                LEFT JOIN users u ON u.id = s.user_id
                WHERE s.id = ?
                """,
                (session_id,),
            ).fetchone()
    return _row_to_principal(row) if row is not None else None


def current_session(request: Request) -> SessionPrincipal | None:
    init_auth_store()
    raw = request.cookies.get(_facade.SESSION_COOKIE_NAME)
    session_id = _unsign_cookie_value(raw)
    if session_id is None:
        return None
    return _lookup_session(session_id)


def _guest_principal_from_request(request: Request) -> SessionPrincipal | None:
    """Synthesize a guest SessionPrincipal from the harmonization cookie.

    Guest sessions are not stored in the auth.db sessions table — they live in
    the signed ``atlas_guest_harmonization`` cookie. This adapter lets the rest
    of the app treat them as a SessionPrincipal at the request boundary.
    """
    # Import locally to avoid an import cycle with api.core.guest_harmonization
    # (which may eventually pull from this module).
    from api.core import guest_harmonization as guest_module

    raw = request.cookies.get(guest_module.GUEST_COOKIE_NAME)
    state = guest_module.parse_cookie(raw)
    if not state.run_ids:
        return None
    primary = state.run_ids[0] if state.run_ids else "anon"
    expires_at = datetime.now(UTC) + timedelta(hours=guest_module.GUEST_TTL_HOURS)
    return SessionPrincipal(
        session_id=f"guest-{primary}",
        mode="guest",
        user_id=None,
        email=None,
        display_name=None,
        role="consumer",
        active_patient_id=None,
        active_patient_name=None,
        expires_at=expires_at,
        guest_run_ids=tuple(state.run_ids),
    )


def current_session_including_guest(request: Request) -> SessionPrincipal | None:
    """Resolve the active session OR a guest principal from the harmonization cookie."""
    session = current_session(request)
    if session is not None:
        return session
    return _guest_principal_from_request(request)


def require_session_or_guest(request: Request) -> SessionPrincipal:
    """Require any session — demo, authenticated, OR guest. Raises 401 otherwise."""
    principal = current_session_including_guest(request)
    if principal is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Sign in, choose a demo patient, or start a guest run first.",
        )
    return principal


def optional_session_response(request: Request) -> AuthSessionResponse:
    session = current_session(request)
    if session is None:
        return AuthSessionResponse(mode="anonymous", available_demo_patients=demo_patient_options())
    return session.to_response()


def begin_demo_session(patient_id: str, request: Request) -> SessionPrincipal:
    init_auth_store()
    if patient_id not in DEMO_PATIENT_BY_ALIAS:
        raise HTTPException(status_code=404, detail=f"Unknown demo patient: {patient_id}")
    principal = _create_session(
        mode="demo",
        user_id=None,
        active_patient_id=patient_id,
        active_patient_name=demo_patient_label(patient_id),
        request=request,
    )
    audit_event(event_type="auth.demo_entered", session=principal, patient_id=patient_id)
    return principal


def revoke_session(principal: SessionPrincipal | None) -> None:
    init_auth_store()
    if principal is None:
        return
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET revoked_at = ? WHERE id = ?",
            (_now().isoformat(), principal.session_id),
        )
        conn.commit()
    audit_event(event_type="auth.logout", session=principal, patient_id=principal.active_patient_id)


def require_access_session(request: Request) -> SessionPrincipal:
    principal = current_session(request)
    if principal is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Sign in or choose a demo patient first.")
    return principal


def require_authenticated_session(request: Request) -> SessionPrincipal:
    principal = require_access_session(request)
    if not principal.is_authenticated:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="This action requires an authenticated account.")
    return principal


def require_role(*roles: AuthRole) -> Callable[[Request], SessionPrincipal]:
    """Return a FastAPI dependency that requires one of ``roles``.

    The caller must be an authenticated session (not demo, not anonymous) AND
    have a role in the allowed set. Demo sessions and consumers attempting to
    hit admin endpoints get a 403 with a generic message — no enumeration.
    """
    allowed = frozenset(roles)

    def _dependency(request: Request) -> SessionPrincipal:
        principal = require_authenticated_session(request)
        if principal.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="This account does not have access to that resource.",
            )
        return principal

    return _dependency


def select_patient(principal: SessionPrincipal, patient_id: str | None) -> SessionPrincipal:
    init_auth_store()
    active_patient_id = patient_id
    active_patient_name = None
    if patient_id:
        if principal.is_demo:
            if patient_id not in DEMO_PATIENT_BY_ALIAS:
                raise HTTPException(status_code=403, detail="Demo sessions can only select approved demo patients.")
            active_patient_name = demo_patient_label(patient_id)
        else:
            if not _facade._authenticated_workspace_access_allowed(principal.user_id, patient_id):
                raise HTTPException(
                    status_code=403,
                    detail="This account does not have access to that workspace.",
                )
            active_patient_name = _known_patient_name(patient_id) or patient_id
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET active_patient_id = ?, active_patient_name = ? WHERE id = ?",
            (active_patient_id, active_patient_name, principal.session_id),
        )
        conn.commit()
        row = conn.execute(
            """
            SELECT s.*, u.email, u.display_name, COALESCE(u.role, 'clinician') AS role
            FROM sessions s
            LEFT JOIN users u ON u.id = s.user_id
            WHERE s.id = ?
            """,
            (principal.session_id,),
        ).fetchone()
    if row is None:
        raise HTTPException(status_code=404, detail="Session not found.")
    refreshed = _row_to_principal(row)
    audit_event(
        event_type="patient.selected",
        session=refreshed,
        patient_id=active_patient_id,
        payload={"patient_name": active_patient_name},
    )
    return refreshed


def authorize_patient_access(
    principal: SessionPrincipal,
    requested_patient_id: str,
    *,
    event_type: str = "patient.accessed",
) -> str:
    # Lazy import to keep the demo helper inside auth_demo without forcing a
    # second top-level import here — resolve_demo_patient_alias is the only
    # cross-module hop in this function.
    from api.core.auth_demo import resolve_demo_patient_alias

    actual_patient_id = requested_patient_id
    if principal.is_demo:
        actual_patient_id = resolve_demo_patient_alias(requested_patient_id)
    elif not _facade._authenticated_workspace_access_allowed(principal.user_id, requested_patient_id):
        raise HTTPException(
            status_code=403,
            detail="This account does not have access to that workspace.",
        )
    audit_event(
        event_type=event_type,
        session=principal,
        patient_id=requested_patient_id,
        payload={"resolved_patient_id": actual_patient_id},
    )
    return actual_patient_id


def require_access_session_dep(request: Request) -> SessionPrincipal:
    return require_access_session(request)


def require_authenticated_session_dep(request: Request) -> SessionPrincipal:
    return require_authenticated_session(request)


AccessSessionDep = Depends(require_access_session_dep)
AuthenticatedSessionDep = Depends(require_authenticated_session_dep)
