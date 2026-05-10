"""Per-run consent tokens.

A consent token is the clinician-signed grant that lets a plugin run.
It binds: pluginId, runId, the scope the plugin can read, the
approver, and an expiry. Once minted, every subsequent tool call in
the run carries the token; the runtime verifies on every call.

Tokens are detached-signed by the Atlas key — the same key that signs
anchor packages. v2: per-org keys.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

from api.trust.keys import atlas_keypair
from api.trust.models import ConsentToken
from api.trust.signatures import SignatureError, sign_object, verify_object


class ConsentError(Exception):
    pass


class ConsentRequired(ConsentError):
    pass


class ConsentExpired(ConsentError):
    pass


class ConsentRevoked(ConsentError):
    pass


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)


def mint_consent_token(
    *,
    plugin_id: str,
    run_id: str,
    scope: list[str],
    approver_id: str,
    ttl_seconds: int,
    issued_at: datetime | None = None,
) -> ConsentToken:
    issued = (issued_at or _now()).replace(microsecond=0)
    expires = issued + timedelta(seconds=ttl_seconds)
    payload = {
        "pluginId": plugin_id,
        "runId": run_id,
        "scope": list(scope),
        "issuedAt": issued.isoformat().replace("+00:00", "Z"),
        "expiresAt": expires.isoformat().replace("+00:00", "Z"),
        "approverId": approver_id,
    }
    sk, _ = atlas_keypair()
    payload["signature"] = sign_object(sk, payload, exclude_field=None)
    return ConsentToken.model_validate(payload)


def verify_consent_token(
    token: ConsentToken,
    *,
    plugin_id: str,
    run_id: str,
    revoked_ids: set[str] | None = None,
    now: datetime | None = None,
) -> None:
    """Raise if the token is invalid for this (plugin, run) at this moment."""
    if token.pluginId != plugin_id:
        raise ConsentError("consent token plugin mismatch")
    if token.runId != run_id:
        raise ConsentError("consent token run mismatch")
    _, pk = atlas_keypair()
    raw = token.model_dump(mode="json")
    sig = raw.pop("signature")
    try:
        verify_object(pk, raw, sig, exclude_field=None)
    except SignatureError as e:
        raise ConsentError(f"consent token signature invalid: {e}") from e
    current = now or _now()
    if token.expiresAt < current:
        raise ConsentExpired(f"consent token expired at {token.expiresAt.isoformat()}")
    if revoked_ids and run_id in revoked_ids:
        raise ConsentRevoked(f"consent revoked for run {run_id}")


def new_approval_id() -> str:
    """UUIDv7-ish (sortable): microsecond timestamp prefix + random."""
    ts = int(datetime.now(timezone.utc).timestamp() * 1_000_000)
    return f"appr_{ts:016d}_{uuid.uuid4().hex[:8]}"
