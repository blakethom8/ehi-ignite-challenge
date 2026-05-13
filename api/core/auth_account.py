"""Account lifecycle: password hashing, signup, login.

Password hashing primitives (scrypt) live here because the only callers are
account-creation, login verification, and password rotation. The session
bootstrap path also needs ``_hash_password`` — that single hop is handled with
a lazy import inside :func:`api.core.auth_session._seed_bootstrap_user` to
keep the import graph one-directional (account depends on session, never the
reverse).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import sqlite3
import uuid

from fastapi import HTTPException, Request, status

from api.core.auth_session import (
    SessionPrincipal,
    _connect,
    _create_session,
    _now,
    audit_event,
    init_auth_store,
)


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
