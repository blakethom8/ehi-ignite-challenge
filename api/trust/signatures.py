"""Detached ed25519 signatures over canonical JSON.

Canonical JSON rules (must match the frontend):
  - keys sorted lexicographically at every level
  - no whitespace (compact separators)
  - UTF-8, NFC-normalized strings
  - NaN / Inf not permitted (json.dumps default)

The signature format is ``ed25519:<base64-no-padding>`` so it survives
JSON round-trips and is human-recognizable in logs.
"""

from __future__ import annotations

import base64
import json
import unicodedata
from typing import Any

from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)


class SignatureError(Exception):
    """Signature verification failed."""


def _normalize(obj: Any) -> Any:
    if isinstance(obj, str):
        return unicodedata.normalize("NFC", obj)
    if isinstance(obj, dict):
        return {k: _normalize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_normalize(v) for v in obj]
    return obj


def canonical_json(obj: dict | list, *, exclude_field: str | None = None) -> bytes:
    """Serialize ``obj`` to canonical JSON bytes.

    If ``exclude_field`` is given (top-level only), it is stripped before
    serialization — used so a manifest can sign every field except its
    own ``signature``.
    """
    if exclude_field is not None and isinstance(obj, dict):
        obj = {k: v for k, v in obj.items() if k != exclude_field}
    obj = _normalize(obj)
    return json.dumps(
        obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


# ============================================================
# Key handling
# ============================================================


def generate_keypair() -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    sk = Ed25519PrivateKey.generate()
    return sk, sk.public_key()


def private_key_to_b64(sk: Ed25519PrivateKey) -> str:
    raw = sk.private_bytes(
        encoding=Encoding.Raw,
        format=PrivateFormat.Raw,
        encryption_algorithm=NoEncryption(),
    )
    return base64.b64encode(raw).decode("ascii")


def public_key_to_b64(pk: Ed25519PublicKey) -> str:
    raw = pk.public_bytes(encoding=Encoding.Raw, format=PublicFormat.Raw)
    return base64.b64encode(raw).decode("ascii")


def private_key_from_b64(s: str) -> Ed25519PrivateKey:
    return Ed25519PrivateKey.from_private_bytes(base64.b64decode(s))


def public_key_from_b64(s: str) -> Ed25519PublicKey:
    return Ed25519PublicKey.from_public_bytes(base64.b64decode(s))


def fingerprint(pk: Ed25519PublicKey) -> str:
    """Stable fingerprint for a public key.

    Format: ``ed25519:<first 12 chars of b64(pk_raw)>``. Short enough
    for logs, unique enough at v1's scale.
    """
    return "ed25519:" + public_key_to_b64(pk)[:12]


# ============================================================
# Sign / verify
# ============================================================


def _encode_sig(sig: bytes) -> str:
    return "ed25519:" + base64.b64encode(sig).decode("ascii").rstrip("=")


def _decode_sig(s: str) -> bytes:
    if not s.startswith("ed25519:"):
        raise SignatureError(f"unsupported signature format: {s[:20]}…")
    raw = s[len("ed25519:") :]
    # restore padding
    raw += "=" * (-len(raw) % 4)
    try:
        return base64.b64decode(raw)
    except Exception as e:
        raise SignatureError(f"invalid base64 in signature: {e}") from e


def sign_bytes(sk: Ed25519PrivateKey, payload: bytes) -> str:
    return _encode_sig(sk.sign(payload))


def verify_bytes(pk: Ed25519PublicKey, payload: bytes, signature: str) -> None:
    sig = _decode_sig(signature)
    try:
        pk.verify(sig, payload)
    except InvalidSignature as e:
        raise SignatureError("signature does not verify") from e


def sign_object(
    sk: Ed25519PrivateKey, obj: dict, *, exclude_field: str | None = "signature"
) -> str:
    payload = canonical_json(obj, exclude_field=exclude_field)
    return sign_bytes(sk, payload)


def verify_object(
    pk: Ed25519PublicKey,
    obj: dict,
    signature: str,
    *,
    exclude_field: str | None = "signature",
) -> None:
    payload = canonical_json(obj, exclude_field=exclude_field)
    verify_bytes(pk, payload, signature)
