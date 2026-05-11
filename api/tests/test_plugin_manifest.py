import json
from pathlib import Path

import pytest

from api.plugins.manifest import (
    BadSignature,
    PluginManifestError,
    UnknownVendor,
    load_manifest,
    load_all_installed,
)
from api.plugins.signer import sign_manifest_dict, write_signed_manifest
from api.trust import keys as keys_mod
from api.trust.signatures import generate_keypair


def _manifest_dict(plugin_id: str, fingerprint: str) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "id": plugin_id,
        "version": "1.0.0",
        "vendor": {"id": "test-vendor", "name": "TestCo", "keyFingerprint": fingerprint},
        "displayName": "Test Plugin",
        "subtitle": "Plugin",
        "description": "desc",
        "icon": "Box",
        "color": "#000000",
        "trust": {
            "posture": "consented-external",
            "boundaryLabel": "Consented external · test",
            "requiresPerRunConsent": True,
        },
        "anchor": {
            "scope": ["diagnoses.active"],
            "redactionPreset": "de-id-v3",
            "ttlSeconds": 3600,
        },
        "connectors": [
            {
                "id": "ctgov",
                "label": "CT",
                "endpointPattern": "https://x/**",
                "auth": "none",
            }
        ],
        "permissions": [
            {"kind": "read-anchor", "scope": ["diagnoses.active"]},
            {"kind": "call-external", "connector": "ctgov"},
        ],
        "workflows": [
            {
                "id": "w",
                "title": "t",
                "description": "d",
                "tags": [],
                "needs": [],
                "produces": [],
            }
        ],
        "tools": [
            {
                "id": "trial.search",
                "label": "s",
                "category": "clinical-trial",
                "permission": "call-external",
            }
        ],
        "ui": {
            "homeSections": ["hero"],
            "workbenchTabs": [
                {
                    "id": "t",
                    "label": "t",
                    "kind": "trial-board",
                    "renderer": "trial.board",
                }
            ],
            "files": [{"group": "working", "name": "x.md", "icon": "FileText"}],
            "agent": {
                "avatarInitials": "Tp",
                "avatarColor": "#000",
                "modelPreset": "marketplace-act",
            },
        },
        "exports": ["markdown"],
    }


@pytest.fixture
def isolated_keys(tmp_path: Path, monkeypatch):
    """Point the vendor allowlist + Atlas key at a tmp directory."""
    monkeypatch.setattr(keys_mod, "DEFAULT_VENDORS_PATH", tmp_path / "vendors.json")
    monkeypatch.setattr(keys_mod, "DEFAULT_KEY_PATH", tmp_path / "atlas.key")
    keys_mod._vendor_cache = None
    keys_mod._atlas_keypair = None
    yield tmp_path
    keys_mod._vendor_cache = None
    keys_mod._atlas_keypair = None


def test_load_manifest_happy_path(tmp_path: Path, isolated_keys):
    sk, pk = generate_keypair()
    rec = keys_mod.register_vendor(vendor_id="test-vendor", name="TestCo", public_key=pk)

    raw = _manifest_dict("trial-finder", rec.keyFingerprint)
    write_signed_manifest(
        plugin_id="trial-finder", version="1.0.0",
        manifest=raw, sk=sk, plugins_root=tmp_path,
    )
    loaded = load_manifest("trial-finder", "1.0.0", plugins_root=tmp_path)
    assert loaded.manifest.id == "trial-finder"
    assert loaded.manifest.vendor.name == "TestCo"


def test_load_manifest_missing_file(tmp_path: Path, isolated_keys):
    with pytest.raises(PluginManifestError):
        load_manifest("nope", "1.0.0", plugins_root=tmp_path)


def test_load_manifest_unknown_vendor(tmp_path: Path, isolated_keys):
    sk, _ = generate_keypair()
    raw = _manifest_dict("trial-finder", "ed25519:zzzzzzzzzzzz")
    write_signed_manifest(
        plugin_id="trial-finder", version="1.0.0",
        manifest=raw, sk=sk, plugins_root=tmp_path,
    )
    with pytest.raises(UnknownVendor):
        load_manifest("trial-finder", "1.0.0", plugins_root=tmp_path)


def test_load_manifest_tampered_displayname(tmp_path: Path, isolated_keys):
    sk, pk = generate_keypair()
    rec = keys_mod.register_vendor(vendor_id="test-vendor", name="TestCo", public_key=pk)
    raw = _manifest_dict("trial-finder", rec.keyFingerprint)
    path = write_signed_manifest(
        plugin_id="trial-finder", version="1.0.0",
        manifest=raw, sk=sk, plugins_root=tmp_path,
    )
    on_disk = json.loads(path.read_text())
    on_disk["displayName"] = "Evil Plugin"
    path.write_text(json.dumps(on_disk))
    with pytest.raises(BadSignature):
        load_manifest("trial-finder", "1.0.0", plugins_root=tmp_path)


def test_load_manifest_missing_signature(tmp_path: Path, isolated_keys):
    sk, pk = generate_keypair()
    rec = keys_mod.register_vendor(vendor_id="test-vendor", name="TestCo", public_key=pk)
    raw = _manifest_dict("trial-finder", rec.keyFingerprint)
    raw["signature"] = ""
    path = tmp_path / "trial-finder" / "1.0.0" / "manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(raw))
    with pytest.raises(BadSignature):
        load_manifest("trial-finder", "1.0.0", plugins_root=tmp_path)


def test_load_manifest_vendor_id_mismatch(tmp_path: Path, isolated_keys):
    sk, pk = generate_keypair()
    rec = keys_mod.register_vendor(vendor_id="alpha", name="TestCo", public_key=pk)
    raw = _manifest_dict("trial-finder", rec.keyFingerprint)
    raw["vendor"]["id"] = "beta"  # registered as alpha
    write_signed_manifest(
        plugin_id="trial-finder", version="1.0.0",
        manifest=raw, sk=sk, plugins_root=tmp_path,
    )
    with pytest.raises(UnknownVendor):
        load_manifest("trial-finder", "1.0.0", plugins_root=tmp_path)


def test_load_all_installed_discovers_three(tmp_path: Path, isolated_keys):
    sk, pk = generate_keypair()
    rec = keys_mod.register_vendor(vendor_id="test-vendor", name="TestCo", public_key=pk)
    for pid, ver in [("trial-finder", "1.0.0"), ("med-access", "1.7.0"), ("second-opinion", "0.9.0-beta")]:
        raw = _manifest_dict(pid, rec.keyFingerprint)
        raw["id"] = pid
        raw["version"] = ver
        write_signed_manifest(
            plugin_id=pid, version=ver,
            manifest=raw, sk=sk, plugins_root=tmp_path,
        )
    loaded = load_all_installed(plugins_root=tmp_path)
    assert {m.manifest.id for m in loaded} == {"trial-finder", "med-access", "second-opinion"}


def test_signed_then_loaded_signature_field_preserved(tmp_path: Path, isolated_keys):
    sk, pk = generate_keypair()
    rec = keys_mod.register_vendor(vendor_id="test-vendor", name="TestCo", public_key=pk)
    raw = _manifest_dict("trial-finder", rec.keyFingerprint)
    signed = sign_manifest_dict(raw, sk)
    assert signed["signature"].startswith("ed25519:")
