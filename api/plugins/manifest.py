"""Load, parse, and verify plugin manifests from disk.

Verification chain:
  1. Parse JSON, validate against ``PluginManifest`` (Pydantic raises on invalid).
  2. Look up vendor public key by ``manifest.vendor.keyFingerprint`` in the
     vendor allowlist.
  3. Verify the detached signature (in ``manifest.signature`` OR a
     companion ``manifest.sig`` file) over the canonical JSON of the
     manifest minus the ``signature`` field.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from api.trust.keys import REPO_ROOT, find_vendor
from api.trust.models import PluginManifest
from api.trust.signatures import SignatureError, verify_object


PLUGINS_ROOT = REPO_ROOT / "data" / "plugins"


class PluginManifestError(Exception):
    pass


class BadSignature(PluginManifestError):
    pass


class UnknownVendor(PluginManifestError):
    pass


@dataclass(frozen=True)
class LoadedManifest:
    manifest: PluginManifest
    path: Path
    raw: dict  # the on-disk dict, before Pydantic coercion


def manifest_path(plugin_id: str, version: str) -> Path:
    return PLUGINS_ROOT / plugin_id / version / "manifest.json"


def load_manifest(
    plugin_id: str, version: str, *, plugins_root: Path | None = None
) -> LoadedManifest:
    root = plugins_root or PLUGINS_ROOT
    path = root / plugin_id / version / "manifest.json"
    if not path.exists():
        raise PluginManifestError(f"manifest not found: {path}")
    raw = json.loads(path.read_text())
    manifest = PluginManifest.model_validate(raw)

    vendor = find_vendor(manifest.vendor.keyFingerprint)
    if vendor is None:
        raise UnknownVendor(
            f"vendor keyFingerprint {manifest.vendor.keyFingerprint} not in allowlist"
        )
    if vendor.id != manifest.vendor.id:
        raise UnknownVendor(
            f"vendor id mismatch: allowlist={vendor.id} manifest={manifest.vendor.id}"
        )

    # Detached signature lives in the manifest field; the sidecar
    # ``manifest.sig`` may also exist (for archival) but the field is canonical.
    signature = raw.get("signature", "")
    if not signature:
        raise BadSignature("manifest missing signature")
    try:
        verify_object(vendor.publicKey, raw, signature, exclude_field="signature")
    except SignatureError as e:
        raise BadSignature(str(e)) from e

    return LoadedManifest(manifest=manifest, path=path, raw=raw)


def discover_installed(plugins_root: Path | None = None) -> Iterable[tuple[str, str]]:
    """Yield ``(plugin_id, version)`` for every manifest on disk."""
    root = plugins_root or PLUGINS_ROOT
    if not root.exists():
        return
    for plugin_dir in sorted(root.iterdir()):
        if not plugin_dir.is_dir():
            continue
        if plugin_dir.name in {"vendors.json"}:
            continue
        for version_dir in sorted(plugin_dir.iterdir()):
            if not version_dir.is_dir():
                continue
            if (version_dir / "manifest.json").exists():
                yield plugin_dir.name, version_dir.name


def load_all_installed(
    plugins_root: Path | None = None,
) -> list[LoadedManifest]:
    out: list[LoadedManifest] = []
    for plugin_id, version in discover_installed(plugins_root):
        out.append(load_manifest(plugin_id, version, plugins_root=plugins_root))
    return out
