"""Manifest signing helpers.

Used by the example-plugin authoring code path and by tests. Production
vendors would run an equivalent CLI in their own infrastructure.
"""

from __future__ import annotations

import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from api.trust.signatures import canonical_json, sign_object


def sign_manifest_dict(manifest: dict, sk: Ed25519PrivateKey) -> dict:
    """Return a new dict with ``signature`` set."""
    out = {k: v for k, v in manifest.items() if k != "signature"}
    out["signature"] = sign_object(sk, out, exclude_field=None)
    return out


def write_signed_manifest(
    *,
    plugin_id: str,
    version: str,
    manifest: dict,
    sk: Ed25519PrivateKey,
    plugins_root: Path,
) -> Path:
    signed = sign_manifest_dict(manifest, sk)
    path = plugins_root / plugin_id / version / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(signed, indent=2) + "\n")
    # Sidecar .sig for archival; the canonical signature lives in the field.
    (path.parent / "manifest.sig").write_text(signed["signature"] + "\n")
    return path


def canonical_payload(manifest: dict) -> bytes:
    """The exact bytes a vendor signs. Useful for debugging interop bugs."""
    return canonical_json({k: v for k, v in manifest.items() if k != "signature"})
