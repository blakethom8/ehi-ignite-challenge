"""Server-managed application auth + session primitives."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from fastapi import Depends, HTTPException, Request, Response, status

from api.auth_models import AuthSessionResponse, AuthUserResponse, DemoPatientOption
from api.core.aggregation import list_upload_workspaces
from api.core.loader import path_from_patient_id
from api.trust.models import UserIdentity

REPO_ROOT = Path(__file__).resolve().parents[2]
AUTH_DB_PATH = Path(os.getenv("EHI_AUTH_DB_PATH", REPO_ROOT / "data" / "auth.db"))
SESSION_SECRET_PATH = Path(
    os.getenv("EHI_SESSION_SECRET_PATH", REPO_ROOT / "data" / "atlas-session.key")
)
SESSION_COOKIE_NAME = "atlas_session"
SESSION_IDLE_HOURS = max(1, int(os.getenv("EHI_AUTH_SESSION_IDLE_HOURS", "12")))
SESSION_MAX_DAYS = max(1, int(os.getenv("EHI_AUTH_SESSION_MAX_DAYS", "7")))
SESSION_SECURE = os.getenv("ENVIRONMENT", "development").strip().lower() in {"prod", "production"}


@dataclass(frozen=True)
class DemoPatientConfig:
    alias_id: str
    name: str
    actual_patient_id: str
    description: str


DEMO_PATIENTS: tuple[DemoPatientConfig, ...] = (
    DemoPatientConfig(
        alias_id="demo-high-risk",
        name="Demo Patient - Surgical Review",
        actual_patient_id="763b6101-133a-44bb-ac60-3c097d6c0ba1",
        description="High-signal pre-op review demo with active medication and condition burden.",
    ),
    DemoPatientConfig(
        alias_id="demo-trial-match",
        name="Demo Patient - Trial Match",
        actual_patient_id="5cbc121b-cd71-4428-b8b7-31e53eba8184",
        description="Curated oncology-style demo for trial-finding and referral workflows.",
    ),
    DemoPatientConfig(
        alias_id="demo-med-access",
        name="Demo Patient - Medication Access",
        actual_patient_id="eec393be-2569-46db-a974-33d7c853d690",
        description="Medication-access demo with a heavier longitudinal record and care burden.",
    ),
)
DEMO_PATIENT_BY_ALIAS = {item.alias_id: item for item in DEMO_PATIENTS}


@dataclass
class SessionPrincipal:
    session_id: str
    mode: Literal["demo", "authenticated"]
    user_id: str | None
    email: str | None
    display_name: str | None
    role: Literal["clinician", "attending", "coordinator", "admin"]
    active_patient_id: str | None
    active_patient_name: str | None
    expires_at: datetime

    @property
    def is_demo(self) -> bool:
        return self.mode == "demo"

    @property
    def is_authenticated(self) -> bool:
        return self.mode == "authenticated"

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


def _session_secret() -> bytes:
    override = (os.getenv("EHI_SESSION_SECRET") or "").strip()
    if override:
        return override.encode("utf-8")
    _ensure_parent(SESSION_SECRET_PATH)
    if SESSION_SECRET_PATH.exists():
        return SESSION_SECRET_PATH.read_bytes()
    secret = secrets.token_bytes(32)
    SESSION_SECRET_PATH.write_bytes(secret)
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


def _hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=2**14, r=8, p=1)
    return (
        "scrypt$16384$8$1$"
        f"{base64.urlsafe_b64encode(salt).decode('ascii')}$"
        f"{base64.urlsafe_b64encode(digest).decode('ascii')}"
    )


def _verify_password(password: str, encoded: str) -> bool:
    try:
        algo, n_raw, r_raw, p_raw, salt_raw, digest_raw = encoded.split("$", 5)
        if algo != "scrypt":
            return False
        salt = base64.urlsafe_b64decode(salt_raw.encode("ascii"))
        expected = base64.urlsafe_b64decode(digest_raw.encode("ascii"))
        candidate = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n_raw),
            r=int(r_raw),
            p=int(p_raw),
        )
    except Exception:
        return False
    return hmac.compare_digest(candidate, expected)


def _connect() -> sqlite3.Connection:
    _ensure_parent(AUTH_DB_PATH)
    conn = sqlite3.connect(AUTH_DB_PATH, detect_types=sqlite3.PARSE_DECLTYPES)
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
    env = os.getenv("ENVIRONMENT", "development").strip().lower()
    email = (os.getenv("EHI_AUTH_BOOTSTRAP_EMAIL") or "clinician@atlas.local").strip().lower()
    password = (os.getenv("EHI_AUTH_BOOTSTRAP_PASSWORD") or "").strip()
    display_name = (os.getenv("EHI_AUTH_BOOTSTRAP_NAME") or "Atlas Clinician").strip() or "Atlas Clinician"
    if not password:
        if env in {"prod", "production"}:
            return
        password = "atlas-demo-password"

    with _connect() as conn:
        existing = conn.execute("SELECT id FROM users WHERE email = ?", (email,)).fetchone()
        if existing is not None:
            return
        conn.execute(
            """
            INSERT INTO users (id, email, display_name, role, password_hash, status, created_at)
            VALUES (?, ?, ?, 'clinician', ?, 'active', ?)
            """,
            (
                f"user_{uuid.uuid4().hex[:12]}",
                email,
                display_name,
                _hash_password(password),
                _now().isoformat(),
            ),
        )
        conn.commit()


def demo_patient_options() -> list[DemoPatientOption]:
    return [
        DemoPatientOption(id=item.alias_id, name=item.name, description=item.description)
        for item in DEMO_PATIENTS
    ]


def is_demo_alias(patient_id: str) -> bool:
    return patient_id in DEMO_PATIENT_BY_ALIAS


def resolve_demo_patient_alias(patient_id: str) -> str:
    item = DEMO_PATIENT_BY_ALIAS.get(patient_id)
    if item is None:
        raise HTTPException(status_code=403, detail="Demo sessions can only access approved demo patients.")
    return item.actual_patient_id


def demo_patient_label(patient_id: str) -> str:
    item = DEMO_PATIENT_BY_ALIAS.get(patient_id)
    return item.name if item is not None else patient_id


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
    expires_at = now + min(timedelta(hours=SESSION_IDLE_HOURS), timedelta(days=SESSION_MAX_DAYS))
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
        key=SESSION_COOKIE_NAME,
        value=_sign_session_id(session_id),
        httponly=True,
        secure=SESSION_SECURE,
        samesite="lax",
        max_age=int(timedelta(days=SESSION_MAX_DAYS).total_seconds()),
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")


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
            _now() + timedelta(hours=SESSION_IDLE_HOURS),
            datetime.fromisoformat(row["created_at"]) + timedelta(days=SESSION_MAX_DAYS),
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
    return _row_to_principal(row) if row is not None else None


def current_session(request: Request) -> SessionPrincipal | None:
    init_auth_store()
    raw = request.cookies.get(SESSION_COOKIE_NAME)
    session_id = _unsign_cookie_value(raw)
    if session_id is None:
        return None
    return _lookup_session(session_id)


def optional_session_response(request: Request) -> AuthSessionResponse:
    session = current_session(request)
    if session is None:
        return AuthSessionResponse(mode="anonymous", available_demo_patients=demo_patient_options())
    return session.to_response()


def login_user(email: str, password: str, request: Request) -> SessionPrincipal:
    init_auth_store()
    with _connect() as conn:
        row = conn.execute(
            """
            SELECT id, email, display_name, role, password_hash, status
            FROM users WHERE email = ?
            """,
            (email.strip().lower(),),
        ).fetchone()
    if row is None or row["status"] != "active" or not _verify_password(password, row["password_hash"]):
        audit_event(event_type="auth.login_failed", payload={"email": email.strip().lower()})
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password.")
    principal = _create_session(
        mode="authenticated",
        user_id=row["id"],
        active_patient_id=None,
        active_patient_name=None,
        request=request,
    )
    audit_event(event_type="auth.login_succeeded", session=principal, payload={"email": row["email"]})
    return principal


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
            if not patient_exists(patient_id):
                raise HTTPException(status_code=404, detail=f"Patient not found: {patient_id}")
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
    actual_patient_id = requested_patient_id
    if principal.is_demo:
        actual_patient_id = resolve_demo_patient_alias(requested_patient_id)
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
