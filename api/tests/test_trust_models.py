import pytest
from pydantic import ValidationError

from api.trust.models import (
    AnchorSpec,
    Connector,
    Permission,
    PluginAgentSpec,
    PluginFileSeed,
    PluginManifest,
    PluginToolDecl,
    PluginUISpec,
    TrustPosture,
    VendorIdentity,
    WorkbenchTabSpec,
    WorkflowDecl,
)


def _minimal_manifest_dict() -> dict:
    return {
        "schemaVersion": "1.0.0",
        "id": "trial-finder",
        "version": "2.4.1",
        "vendor": {
            "id": "helix-clinical",
            "name": "Helix Clinical",
            "keyFingerprint": "ed25519:abcdefghijkl",
        },
        "displayName": "Trial Finder",
        "subtitle": "Plugin",
        "description": "desc",
        "icon": "Telescope",
        "color": "#4338ca",
        "trust": {
            "posture": "consented-external",
            "boundaryLabel": "Consented external · registry lookup",
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
                "label": "CT.gov",
                "endpointPattern": "https://x/**",
                "auth": "none",
            }
        ],
        "permissions": [
            {"kind": "read-anchor", "scope": ["diagnoses.active"]},
            {"kind": "call-external", "connector": "ctgov"},
            {"kind": "send-outbound", "channel": "site-packet"},
        ],
        "workflows": [
            {
                "id": "shortlist",
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
                "label": "Search",
                "category": "clinical-trial",
                "permission": "call-external",
            }
        ],
        "ui": {
            "homeSections": ["hero"],
            "workbenchTabs": [
                {
                    "id": "tab",
                    "label": "tab",
                    "kind": "trial-board",
                    "renderer": "trial.board",
                }
            ],
            "files": [{"group": "working", "name": "x.md", "icon": "FileText"}],
            "agent": {
                "avatarInitials": "Tf",
                "avatarColor": "var(--mod-trials)",
                "modelPreset": "marketplace-act",
            },
        },
        "exports": ["markdown"],
        "signature": "ed25519:placeholder",
    }


def test_manifest_happy_path():
    m = PluginManifest.model_validate(_minimal_manifest_dict())
    assert m.id == "trial-finder"
    assert m.permissions[1].connector == "ctgov"


def test_undeclared_connector_rejected():
    raw = _minimal_manifest_dict()
    raw["permissions"][1]["connector"] = "missing"
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(raw)


def test_read_anchor_requires_scope():
    with pytest.raises(ValidationError):
        Permission.model_validate({"kind": "read-anchor"})


def test_send_outbound_requires_channel():
    with pytest.raises(ValidationError):
        Permission.model_validate({"kind": "send-outbound"})


def test_ttl_must_be_positive():
    with pytest.raises(ValidationError):
        AnchorSpec.model_validate(
            {"scope": ["diagnoses.active"], "redactionPreset": "de-id-v3", "ttlSeconds": 0}
        )


def test_ttl_capped_at_one_day():
    with pytest.raises(ValidationError):
        AnchorSpec.model_validate(
            {
                "scope": ["diagnoses.active"],
                "redactionPreset": "de-id-v3",
                "ttlSeconds": 86_401,
            }
        )


def test_tool_without_covering_permission_rejected():
    raw = _minimal_manifest_dict()
    raw["tools"].append(
        {
            "id": "rogue",
            "label": "x",
            "category": "outbound",
            "permission": "send-outbound",
        }
    )
    # ok — manifest already declares send-outbound
    PluginManifest.model_validate(raw)
    # remove the matching permission → must fail
    raw["permissions"] = [p for p in raw["permissions"] if p["kind"] != "send-outbound"]
    with pytest.raises(ValidationError):
        PluginManifest.model_validate(raw)
