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
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Literal

from typing import Callable

from fastapi import Depends, HTTPException, Request, Response, status

from api.auth_models import (
    AuthRole,
    AuthSessionResponse,
    AuthUserResponse,
    DemoPatientMetadata,
    DemoPatientOption,
)
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
    short_journey: str
    care_setting: str
    clinical_focus: str
    complexity: str
    tags: tuple[str, ...]

    def to_option(self) -> DemoPatientOption:
        return DemoPatientOption(
            id=self.alias_id,
            name=self.name,
            description=self.description,
            short_journey=self.short_journey,
            metadata=DemoPatientMetadata(
                care_setting=self.care_setting,
                clinical_focus=self.clinical_focus,
                complexity=self.complexity,
                tags=list(self.tags),
            ),
        )


DEMO_PATIENTS: tuple[DemoPatientConfig, ...] = (
    DemoPatientConfig(
        alias_id="demo-high-risk",
        name="Demo Patient - Surgical Review",
        actual_patient_id="81e1b4cb-6817-4bdc-97cd-c1f3ac960345",
        description="Curated pre-op chart with cardiology, anticoagulation, heart-failure, stroke, and oncology context in one record.",
        short_journey="A 93-year-old man with coronary disease, atrial fibrillation, CHF, prior stroke, and prostate cancer who needs a fast surgical-safety review.",
        care_setting="Pre-op surgical review",
        clinical_focus="Medication safety and longitudinal risk review",
        complexity="high",
        tags=("FHIR-only", "Polypharmacy", "Peri-op", "Risk flags"),
    ),
    DemoPatientConfig(
        alias_id="demo-trial-match",
        name="Demo Patient - Trial Match",
        actual_patient_id="8143897c-e650-4e55-b08d-8306e2f424bb",
        description="Curated oncology referral chart with active cancer treatment, chronic disease burden, and trial-screening style review needs.",
        short_journey="A 95-year-old man with prostate neoplasm, CKD, coronary disease, diabetes, and active oncology treatment for referral and eligibility review.",
        care_setting="Specialty referral review",
        clinical_focus="Trial matching and evidence-backed referral prep",
        complexity="medium",
        tags=("FHIR-only", "Oncology", "Referral", "Trial matching"),
    ),
    DemoPatientConfig(
        alias_id="demo-med-access",
        name="Demo Patient - Medication Access",
        actual_patient_id="eec393be-2569-46db-a974-33d7c853d690",
        description="Curated longitudinal chart for polypharmacy, diabetes, CKD, chronic pain, and treatment-continuity review.",
        short_journey="A 91-year-old woman with diabetes, CKD, neuropathy, retinopathy, chronic pain, stroke history, and insulin plus oncology medications.",
        care_setting="Care coordination",
        clinical_focus="Medication access and ongoing treatment management",
        complexity="medium",
        tags=("FHIR-only", "Longitudinal", "Coverage", "Adherence"),
    ),
    # ─── Multi-source aggregation demos ──────────────────────────────────────
    # These four personas pair a structured FHIR baseline with a small fan of
    # pre-staged synthetic source documents (PDF discharge summaries, C-CDA
    # outside-provider exports, supplemental FHIR feeds from specialty clinics
    # / patient apps / device telemetry / home monitoring). They exist to
    # demonstrate the data-aggregation feature on real multi-source evidence
    # — each one ships with deliberate cross-source inconsistencies that the
    # harmonization pipeline is supposed to surface.
    # All four aliases share the demo-aggregate-* prefix so they can be
    # filtered or sunset as a group without touching the original Synthea
    # demos above.
    DemoPatientConfig(
        alias_id="demo-aggregate-icu",
        name="Demo Patient - Critical Care Aggregation",
        actual_patient_id="cb70e6ae-90b1-562b-8ab0-467c65d18d5e",
        description="Real (de-identified) MIMIC-IV ICU survivor — assembled from a structured FHIR baseline plus a discharge summary, anticoag clinic letter, pacemaker interrogation, sleep study, pre-op intake, outside oncology C-CDA, and Dana-Farber FHIR feed.",
        short_journey="A male in his 60s with CLL on active treatment, paroxysmal AFib with a Medtronic pacemaker, T2DM on insulin, OSA, and a prior TIA — chart assembled from seven distinct sources for a peri-operative review.",
        care_setting="Peri-operative / multi-source intake",
        clinical_focus="Multi-source data aggregation and reconciliation",
        complexity="high",
        tags=("Multi-source", "Real ICU data", "Polypharmacy", "Inconsistencies"),
    ),
    DemoPatientConfig(
        alias_id="demo-aggregate-oncology",
        name="Demo Patient - Oncology Aggregation",
        actual_patient_id="cancer-patient-jenny-m",
        description="Structured oncology chart (HL7 mCODE Jenny M) paired with a screening mammogram, biopsy pathology report, tumor board summary, genetic counseling letter, outside community-gynecologist C-CDA, and 8 weeks of patient-generated symptom-tracker FHIR data.",
        short_journey="A 55-year-old woman newly diagnosed with invasive ductal carcinoma — workup assembled from imaging, pathology, multidisciplinary review, genetic counseling, outside historical records, and a chemo symptom-tracker app.",
        care_setting="Specialty oncology workup",
        clinical_focus="Multi-source oncology assembly with mCODE staging",
        complexity="medium",
        tags=("Multi-source", "mCODE", "PGHD", "Family history"),
    ),
    DemoPatientConfig(
        alias_id="demo-aggregate-cardiac",
        name="Demo Patient - Cardiac Multimodal Aggregation",
        actual_patient_id="fec6d99f-1cfd-f397-e740-e3952410ea2a",
        description="Synthea Coherent CVD patient — a multimodal chart assembled from a 35 MB FHIR baseline, a cardiac MRI DICOM, simulated genomics, plus a cardiology post-arrest consult, stroke discharge summary, prostate pathology, oncology chemo plan, and Medtronic CareLink pacemaker telemetry FHIR feed.",
        short_journey="An elderly man, cardiac-arrest survivor with prior stroke and active prostate cancer on combined ADT + docetaxel — chart spans structured FHIR, imaging, genomics, and device telemetry.",
        care_setting="Complex cardiology / oncology coordination",
        clinical_focus="Multimodal aggregation across FHIR, imaging, genomics, and device feeds",
        complexity="high",
        tags=("Multi-source", "Multimodal", "DICOM", "Device telemetry"),
    ),
    DemoPatientConfig(
        alias_id="demo-aggregate-polypharmacy",
        name="Demo Patient - Polypharmacy Aggregation",
        actual_patient_id="b0f49c80-b59b-4df6-8292-40ce8b8f8612",
        description="Synthea polypharmacy patient — structured FHIR baseline plus a recent discharge summary, outpatient warfarin clinic letter, neurology dementia consult, colonoscopy + pathology, stale outside-PCP C-CDA, and 60 days of home-monitoring FHIR data from a connected BP cuff and glucometer.",
        short_journey="A 99-year-old woman with atrial fibrillation on warfarin, Alzheimer's on galantamine, and colorectal cancer on FOLFOX — chart assembled across hospital, anticoag clinic, neurology, GI, PCP, and home-monitoring sources.",
        care_setting="Geriatric polypharmacy / care coordination",
        clinical_focus="Cross-source medication safety and home-data harmonization",
        complexity="high",
        tags=("Multi-source", "Polypharmacy", "Home monitoring", "Stale outside data"),
    ),
)
DEMO_PATIENT_BY_ALIAS = {item.alias_id: item for item in DEMO_PATIENTS}


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
    return os.getenv("ENVIRONMENT", "development").strip().lower() in {"prod", "production"}


def _session_secret() -> bytes:
    override = (os.getenv("EHI_SESSION_SECRET") or "").strip()
    if override:
        return override.encode("utf-8")
    if _is_production():
        raise RuntimeError(
            "EHI_SESSION_SECRET env var is required when ENVIRONMENT=production. "
            "Refusing to fall back to data/atlas-session.key — session signing "
            "secrets must not live as a plaintext file on disk in production."
        )
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


_VALID_ROLES: frozenset[str] = frozenset(
    {"consumer", "clinician", "attending", "coordinator", "admin"}
)


def _seed_bootstrap_user() -> None:
    env = os.getenv("ENVIRONMENT", "development").strip().lower()
    email = (os.getenv("EHI_AUTH_BOOTSTRAP_EMAIL") or "clinician@atlas.local").strip().lower()
    password = (os.getenv("EHI_AUTH_BOOTSTRAP_PASSWORD") or "").strip()
    display_name = (os.getenv("EHI_AUTH_BOOTSTRAP_NAME") or "Atlas Clinician").strip() or "Atlas Clinician"
    role_raw = (os.getenv("EHI_AUTH_BOOTSTRAP_ROLE") or "clinician").strip().lower()
    role = role_raw if role_raw in _VALID_ROLES else "clinician"
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


def demo_patient_options() -> list[DemoPatientOption]:
    return [item.to_option() for item in DEMO_PATIENTS]


def demo_patient_option(patient_id: str | None) -> DemoPatientOption | None:
    if patient_id is None:
        return None
    item = DEMO_PATIENT_BY_ALIAS.get(patient_id)
    return item.to_option() if item is not None else None


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
        return _authenticated_workspace_access_allowed(user_id, patient_id)
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
    raw = request.cookies.get(SESSION_COOKIE_NAME)
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


def signup_user(email: str, password: str, display_name: str, request: Request) -> SessionPrincipal:
    init_auth_store()
    normalized_email = email.strip().lower()
    normalized_name = display_name.strip()
    if not normalized_email or not normalized_name:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Email and display name are required.",
        )

    user_id = f"user_{uuid.uuid4().hex[:12]}"
    now = _now().isoformat()
    with _connect() as conn:
        existing = conn.execute(
            "SELECT id FROM users WHERE email = ? AND status = 'active'",
            (normalized_email,),
        ).fetchone()
        if existing is not None:
            audit_event(event_type="auth.signup_conflict", payload={"email": normalized_email})
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists for this email.",
            )
        try:
            conn.execute(
                """
                INSERT INTO users (id, email, display_name, role, password_hash, status, created_at)
                VALUES (?, ?, ?, 'consumer', ?, 'active', ?)
                """,
                (
                    user_id,
                    normalized_email,
                    normalized_name,
                    _hash_password(password),
                    now,
                ),
            )
            conn.commit()
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            audit_event(event_type="auth.signup_conflict", payload={"email": normalized_email})
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="An account already exists for this email.",
            ) from exc

    principal = _create_session(
        mode="authenticated",
        user_id=user_id,
        active_patient_id=None,
        active_patient_name=None,
        request=request,
    )
    audit_event(event_type="auth.signup_succeeded", session=principal, payload={"email": normalized_email})
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
            if not _authenticated_workspace_access_allowed(principal.user_id, patient_id):
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
    actual_patient_id = requested_patient_id
    if principal.is_demo:
        actual_patient_id = resolve_demo_patient_alias(requested_patient_id)
    elif not _authenticated_workspace_access_allowed(principal.user_id, requested_patient_id):
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


# ---------------------------------------------------------------------------
# Admin + self-service helpers
# ---------------------------------------------------------------------------


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
