"""Key management for the plugin runtime.

v1: single Atlas signing key (loaded from ``ATLAS_SIGNING_KEY`` env var
or generated on first run and persisted at ``data/atlas-signing.key``)
+ vendor allowlist read from ``data/plugins/vendors.json``.

v2 (out of scope): per-org keys, key rotation, vendor key federation.
"""

from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import (
    Ed25519PrivateKey,
    Ed25519PublicKey,
)

from .signatures import (
    fingerprint,
    generate_keypair,
    private_key_from_b64,
    private_key_to_b64,
    public_key_from_b64,
    public_key_to_b64,
)


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_KEY_PATH = REPO_ROOT / "data" / "atlas-signing.key"
DEFAULT_VENDORS_PATH = REPO_ROOT / "data" / "plugins" / "vendors.json"

_lock = threading.Lock()
_atlas_keypair: tuple[Ed25519PrivateKey, Ed25519PublicKey] | None = None
_vendor_cache: dict[str, "VendorRecord"] | None = None


@dataclass(frozen=True)
class VendorRecord:
    id: str
    name: str
    keyFingerprint: str
    publicKey: Ed25519PublicKey


# ============================================================
# Atlas signing key
# ============================================================


def _is_production() -> bool:
    return os.getenv("ENVIRONMENT", "development").strip().lower() in {"prod", "production"}


def _load_or_create_atlas_key(path: Path) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    env = os.environ.get("ATLAS_SIGNING_KEY")
    if env:
        sk = private_key_from_b64(env)
        return sk, sk.public_key()
    if _is_production():
        raise RuntimeError(
            "ATLAS_SIGNING_KEY env var is required when ENVIRONMENT=production. "
            "Refusing to fall back to data/atlas-signing.key — the Atlas signing "
            "key is the root of the plugin trust chain and must not live as a "
            "plaintext file on disk in production."
        )
    if path.exists():
        sk = private_key_from_b64(path.read_text().strip())
        return sk, sk.public_key()
    path.parent.mkdir(parents=True, exist_ok=True)
    sk, pk = generate_keypair()
    path.write_text(private_key_to_b64(sk))
    return sk, pk


def atlas_keypair(
    *, path: Path | None = None, reset: bool = False
) -> tuple[Ed25519PrivateKey, Ed25519PublicKey]:
    global _atlas_keypair
    with _lock:
        if reset:
            _atlas_keypair = None
        if _atlas_keypair is None:
            _atlas_keypair = _load_or_create_atlas_key(path or DEFAULT_KEY_PATH)
        return _atlas_keypair


def atlas_signing_key() -> Ed25519PrivateKey:
    return atlas_keypair()[0]


def atlas_public_key() -> Ed25519PublicKey:
    return atlas_keypair()[1]


def atlas_public_key_b64() -> str:
    return public_key_to_b64(atlas_public_key())


# ============================================================
# Vendor allowlist
# ============================================================


def load_vendors(
    *, path: Path | None = None, reset: bool = False
) -> dict[str, VendorRecord]:
    global _vendor_cache
    with _lock:
        if reset:
            _vendor_cache = None
        if _vendor_cache is None:
            p = path or DEFAULT_VENDORS_PATH
            if not p.exists():
                _vendor_cache = {}
            else:
                raw = json.loads(p.read_text())
                out: dict[str, VendorRecord] = {}
                for v in raw:
                    pk = public_key_from_b64(v["publicKey"])
                    out[v["keyFingerprint"]] = VendorRecord(
                        id=v["id"],
                        name=v["name"],
                        keyFingerprint=v["keyFingerprint"],
                        publicKey=pk,
                    )
                _vendor_cache = out
        return _vendor_cache


def find_vendor(key_fingerprint: str) -> VendorRecord | None:
    return load_vendors().get(key_fingerprint)


def write_vendors(records: list[dict], path: Path | None = None) -> None:
    """Persist the vendor allowlist (used by dev tools + manifest signer)."""
    global _vendor_cache
    p = path or DEFAULT_VENDORS_PATH
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(records, indent=2))
    with _lock:
        _vendor_cache = None


def register_vendor(
    *,
    vendor_id: str,
    name: str,
    public_key: Ed25519PublicKey,
    path: Path | None = None,
) -> VendorRecord:
    """Append a vendor to the allowlist (used in tests + manifest signer)."""
    p = path or DEFAULT_VENDORS_PATH
    existing: list[dict] = []
    if p.exists():
        existing = json.loads(p.read_text())
    fp = fingerprint(public_key)
    existing = [v for v in existing if v.get("keyFingerprint") != fp]
    existing.append(
        {
            "id": vendor_id,
            "name": name,
            "keyFingerprint": fp,
            "publicKey": public_key_to_b64(public_key),
        }
    )
    write_vendors(existing, path=p)
    return VendorRecord(
        id=vendor_id, name=name, keyFingerprint=fp, publicKey=public_key
    )
