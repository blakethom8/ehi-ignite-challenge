"""Materialize the three example plugin manifests + vendor allowlist.

Run this any time the example manifests need to be rebuilt. The script
is deterministic: vendor private keys are derived from fixed seeds, so
checked-in signatures stay stable across machines.

    uv run python scripts/build_example_plugins.py
"""

from __future__ import annotations

import json
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from api.plugins.signer import write_signed_manifest
from api.trust.signatures import fingerprint, public_key_to_b64


REPO_ROOT = Path(__file__).resolve().parent.parent
PLUGINS_ROOT = REPO_ROOT / "data" / "plugins"
VENDORS_PATH = PLUGINS_ROOT / "vendors.json"


def _seed_to_key(seed: str) -> Ed25519PrivateKey:
    """Deterministic ed25519 private key from a 32-byte seed string."""
    raw = seed.encode("utf-8")
    if len(raw) < 32:
        raw = raw + b"\x00" * (32 - len(raw))
    return Ed25519PrivateKey.from_private_bytes(raw[:32])


VENDORS = [
    {"id": "helix-clinical", "name": "Helix Clinical", "seed": "vendor:helix-clinical:v1"},
    {"id": "rxbridge", "name": "RxBridge", "seed": "vendor:rxbridge:v1"},
    {"id": "confermd", "name": "ConferMD", "seed": "vendor:confermd:v1"},
]


def _trial_finder_manifest(fp: str) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "id": "trial-finder",
        "version": "2.4.1",
        "vendor": {"id": "helix-clinical", "name": "Helix Clinical", "keyFingerprint": fp},
        "displayName": "Trial Finder",
        "subtitle": "Clinical-trial discovery + outreach",
        "description": (
            "Pulls a consented patient anchor from Caspian and runs a clinical-trial "
            "discovery loop against external registries. Produces ranked candidate "
            "boards, eligibility checks, and outreach packets — every outbound action "
            "gated by per-run approval."
        ),
        "icon": "Telescope",
        "color": "#4338ca",
        "trust": {
            "posture": "consented-external",
            "boundaryLabel": "Consented external · registry lookup",
            "requiresPerRunConsent": True,
        },
        "anchor": {
            "scope": [
                "demographics.age-band",
                "demographics.sex",
                "demographics.geography",
                "diagnoses.active",
                "biomarkers",
                "labs.recent",
                "performance-status",
            ],
            "redactionPreset": "de-id-v3",
            "ttlSeconds": 3600,
        },
        "connectors": [
            {
                "id": "clinicaltrials-gov",
                "label": "ClinicalTrials.gov",
                "endpointPattern": "https://clinicaltrials.gov/api/v2/**",
                "auth": "none",
            },
            {
                "id": "nci-trial-connect",
                "label": "NCI Trial Connect",
                "endpointPattern": "https://trialconnect.cancer.gov/api/**",
                "auth": "vendor-token",
            },
        ],
        "permissions": [
            {
                "kind": "read-anchor",
                "scope": [
                    "diagnoses.active",
                    "biomarkers",
                    "labs.recent",
                    "performance-status",
                ],
            },
            {"kind": "call-external", "connector": "clinicaltrials-gov"},
            {"kind": "call-external", "connector": "nci-trial-connect"},
            {"kind": "send-outbound", "channel": "site-packet"},
        ],
        "workflows": [
            {
                "id": "shortlist",
                "title": "Shortlist candidate trials",
                "description": "Search registries against the patient anchors and rank likely fits.",
                "tags": ["external"],
                "needs": ["diagnoses.active", "biomarkers"],
                "produces": ["candidate-board"],
            },
            {
                "id": "review",
                "title": "Review eligibility fit",
                "description": "Compare inclusion/exclusion against shortlist.",
                "tags": ["review"],
                "needs": ["candidate-board"],
                "produces": ["eligibility-report"],
            },
            {
                "id": "packet",
                "title": "Draft outreach packet",
                "description": "Prepare a redacted artifact for site contact.",
                "tags": ["export"],
                "needs": ["candidate-board"],
                "produces": ["outreach-packet"],
            },
        ],
        "tools": [
            {"id": "trial.search", "label": "Search trials", "category": "clinical-trial", "permission": "call-external"},
            {"id": "trial.fetch_detail", "label": "Fetch trial detail", "category": "clinical-trial", "permission": "call-external"},
            {"id": "trial.score_fit", "label": "Score patient fit", "category": "clinical-trial", "permission": "read-anchor"},
            {"id": "packet.draft", "label": "Draft outreach packet", "category": "artifact", "permission": "read-anchor"},
            {"id": "packet.send", "label": "Send packet", "category": "outbound", "permission": "send-outbound"},
        ],
        "ui": {
            "homeSections": ["hero", "permissions-ledger", "workflows", "recent-runs", "about"],
            "workbenchTabs": [
                {"id": "candidate-board", "label": "Candidate board", "kind": "trial-board", "renderer": "trial.board"},
                {"id": "shortlist", "label": "ranked-shortlist.md", "kind": "packet-outline", "renderer": "markdown.doc"},
                {"id": "manifest", "label": "manifest.json", "kind": "manifest-json", "renderer": "json.viewer"},
            ],
            "files": [
                {"group": "working", "name": "ranked-shortlist.md", "icon": "FileText", "dirty": True},
                {"group": "working", "name": "candidate-board.json", "icon": "Braces"},
                {"group": "working", "name": "packet-outline.md", "icon": "FileText"},
                {"group": "anchors", "name": "diagnoses.md", "icon": "FileText"},
                {"group": "anchors", "name": "biomarkers.csv", "icon": "FileSpreadsheet"},
                {"group": "anchors", "name": "geography.json", "icon": "Braces"},
            ],
            "agent": {
                "avatarInitials": "Tf",
                "avatarColor": "var(--mod-trials)",
                "modelPreset": "marketplace-act",
            },
        },
        "exports": ["markdown", "json", "shareable-bundle"],
    }


def _med_access_manifest(fp: str) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "id": "med-access",
        "version": "1.7.0",
        "vendor": {"id": "rxbridge", "name": "RxBridge", "keyFingerprint": fp},
        "displayName": "Medication Access",
        "subtitle": "Patient assistance + prior-auth concierge",
        "description": (
            "Identifies medication-access barriers, matches the patient to "
            "manufacturer assistance programs, and prepares + files prior-auth "
            "packets with payer portals. Every outbound submission is gated by "
            "per-run consent + per-action clinician approval."
        ),
        "icon": "Pill",
        "color": "#0f766e",
        "trust": {
            "posture": "consented-external",
            "boundaryLabel": "Consented external · assistance program",
            "requiresPerRunConsent": True,
        },
        "anchor": {
            "scope": [
                "medications.active",
                "medications.history",
                "diagnoses.active",
                "allergies",
                "demographics.age-band",
                "demographics.geography",
            ],
            "redactionPreset": "minimal",
            "ttlSeconds": 3600,
        },
        "connectors": [
            {
                "id": "surescripts-formulary",
                "label": "Surescripts Formulary",
                "endpointPattern": "https://formulary.surescripts.net/api/**",
                "auth": "none",
            },
            {
                "id": "manufacturer-pap-api",
                "label": "Manufacturer PAP",
                "endpointPattern": "https://pap.{vendor}.com/api/**",
                "auth": "vendor-token",
            },
            {
                "id": "payer-portal-edi",
                "label": "Payer Portal",
                "endpointPattern": "https://payer-portal.example.com/edi/**",
                "auth": "user-delegated",
            },
        ],
        "permissions": [
            {
                "kind": "read-anchor",
                "scope": [
                    "medications.active",
                    "medications.history",
                    "diagnoses.active",
                    "allergies",
                ],
            },
            {"kind": "call-external", "connector": "surescripts-formulary"},
            {"kind": "call-external", "connector": "manufacturer-pap-api"},
            {"kind": "call-external", "connector": "payer-portal-edi"},
            {"kind": "send-outbound", "channel": "pap-enrollment"},
            {"kind": "send-outbound", "channel": "pa-submission"},
        ],
        "workflows": [
            {
                "id": "identify-barriers",
                "title": "Identify access barriers",
                "description": "Pull active meds + diagnoses and surface formulary, PA, and cost barriers.",
                "tags": ["analysis"],
                "needs": ["medications.active", "diagnoses.active"],
                "produces": ["barriers-list"],
            },
            {
                "id": "match-pap",
                "title": "Match patient assistance programs",
                "description": "Find manufacturer assistance programs the patient qualifies for.",
                "tags": ["external"],
                "needs": ["barriers-list"],
                "produces": ["pap-matches"],
            },
            {
                "id": "file-pa",
                "title": "File prior authorization",
                "description": "Compose and submit the PA packet to the payer portal.",
                "tags": ["external"],
                "needs": ["barriers-list"],
                "produces": ["pa-packet", "pa-submission-receipt"],
            },
            {
                "id": "appeal-denial",
                "title": "Appeal a denial",
                "description": "Compose an appeal packet for a denied PA.",
                "tags": ["external"],
                "needs": ["pa-submission-receipt"],
                "produces": ["appeal-packet"],
            },
        ],
        "tools": [
            {"id": "med.lookup_formulary", "label": "Look up formulary", "category": "external", "permission": "call-external"},
            {"id": "med.identify_barriers", "label": "Identify barriers", "category": "patient", "permission": "read-anchor"},
            {"id": "pap.match", "label": "Match PAP", "category": "external", "permission": "call-external"},
            {"id": "pap.enroll", "label": "Enroll in PAP", "category": "outbound", "permission": "send-outbound"},
            {"id": "pa.compose", "label": "Compose PA packet", "category": "artifact", "permission": "read-anchor"},
            {"id": "pa.submit", "label": "Submit PA", "category": "outbound", "permission": "send-outbound"},
        ],
        "ui": {
            "homeSections": ["hero", "permissions-ledger", "workflows", "recent-runs", "about"],
            "workbenchTabs": [
                {"id": "barriers", "label": "Barriers", "kind": "barriers-list", "renderer": "list.barriers"},
                {"id": "pa-form", "label": "PA form preview", "kind": "pa-form", "renderer": "form.pa"},
                {"id": "pap-matcher", "label": "Manufacturer programs", "kind": "manufacturer-program-matcher", "renderer": "matcher.manufacturer"},
                {"id": "status", "label": "Submission status", "kind": "network-status-board", "renderer": "board.network-status"},
            ],
            "files": [
                {"group": "working", "name": "pa-packet.md", "icon": "FileText", "dirty": True},
                {"group": "working", "name": "barriers.json", "icon": "Braces"},
                {"group": "working", "name": "pap-matches.md", "icon": "FileText"},
                {"group": "anchors", "name": "active-meds.md", "icon": "FileText"},
                {"group": "anchors", "name": "diagnoses.md", "icon": "FileText"},
            ],
            "agent": {
                "avatarInitials": "Mx",
                "avatarColor": "var(--mod-meds)",
                "modelPreset": "marketplace-act",
            },
        },
        "exports": ["markdown", "json"],
    }


def _second_opinion_manifest(fp: str) -> dict:
    return {
        "schemaVersion": "1.0.0",
        "id": "second-opinion",
        "version": "0.9.0-beta",
        "vendor": {"id": "confermd", "name": "ConferMD", "keyFingerprint": fp},
        "displayName": "Second Opinion",
        "subtitle": "Specialist referral + outside-consult packager",
        "description": (
            "Composes a redacted clinical packet for an outside specialist, "
            "routes it to a chosen consulting network, and tracks the response. "
            "Attending approval is required before any packet is routed."
        ),
        "icon": "UserRound",
        "color": "#0f766e",
        "trust": {
            "posture": "consented-external",
            "boundaryLabel": "Consented external · specialist network",
            "requiresPerRunConsent": True,
        },
        "anchor": {
            "scope": [
                "diagnoses.active",
                "diagnoses.history",
                "labs.recent",
                "encounters.recent",
                "allergies",
                "performance-status",
            ],
            "redactionPreset": "de-id-v3",
            "ttlSeconds": 3600,
        },
        "connectors": [
            {
                "id": "confermd-network",
                "label": "ConferMD",
                "endpointPattern": "https://api.confermd.com/v1/**",
                "auth": "vendor-token",
            }
        ],
        "permissions": [
            {
                "kind": "read-anchor",
                "scope": [
                    "diagnoses.active",
                    "diagnoses.history",
                    "labs.recent",
                    "encounters.recent",
                    "allergies",
                    "performance-status",
                ],
            },
            {"kind": "call-external", "connector": "confermd-network"},
            {"kind": "send-outbound", "channel": "consulting-network"},
        ],
        "workflows": [
            {
                "id": "compose-packet",
                "title": "Compose referral packet",
                "description": "Assemble the clinical packet for an outside specialist.",
                "tags": ["analysis"],
                "needs": ["diagnoses.active", "diagnoses.history", "labs.recent"],
                "produces": ["referral-packet"],
            },
            {
                "id": "route-packet",
                "title": "Route packet to specialist",
                "description": "Send the composed packet into the consulting network.",
                "tags": ["external"],
                "needs": ["referral-packet"],
                "produces": ["referral-submission-receipt"],
            },
            {
                "id": "track-response",
                "title": "Track specialist response",
                "description": "Poll for the consulting opinion and surface it back.",
                "tags": ["external"],
                "needs": ["referral-submission-receipt"],
                "produces": ["consulting-opinion"],
            },
        ],
        "tools": [
            {"id": "referral.compose_packet", "label": "Compose packet", "category": "artifact", "permission": "read-anchor"},
            {"id": "referral.apply_redactions", "label": "Apply redactions", "category": "transparency", "permission": "read-anchor"},
            {"id": "referral.route", "label": "Route packet", "category": "outbound", "permission": "send-outbound"},
            {"id": "referral.fetch_response", "label": "Fetch response", "category": "external", "permission": "call-external"},
        ],
        "ui": {
            "homeSections": ["hero", "permissions-ledger", "workflows", "recent-runs", "about"],
            "workbenchTabs": [
                {"id": "specialty", "label": "Specialty picker", "kind": "specialty-picker", "renderer": "picker.specialty"},
                {"id": "packet", "label": "Referral packet", "kind": "referral-packet", "renderer": "packet.referral"},
                {"id": "status", "label": "Network status", "kind": "network-status-board", "renderer": "board.network-status"},
            ],
            "files": [
                {"group": "working", "name": "referral-packet.md", "icon": "FileText", "dirty": True},
                {"group": "working", "name": "redaction-preview.md", "icon": "FileText"},
                {"group": "anchors", "name": "diagnoses.md", "icon": "FileText"},
                {"group": "anchors", "name": "recent-encounters.md", "icon": "FileText"},
            ],
            "agent": {
                "avatarInitials": "So",
                "avatarColor": "#0f766e",
                "modelPreset": "clinical-balanced",
            },
        },
        "exports": ["markdown", "json", "shareable-bundle"],
    }


def main() -> None:
    PLUGINS_ROOT.mkdir(parents=True, exist_ok=True)

    keys = {v["id"]: _seed_to_key(v["seed"]) for v in VENDORS}
    fps = {vid: fingerprint(k.public_key()) for vid, k in keys.items()}

    # Vendor allowlist (deterministic).
    allowlist = [
        {
            "id": v["id"],
            "name": v["name"],
            "keyFingerprint": fps[v["id"]],
            "publicKey": public_key_to_b64(keys[v["id"]].public_key()),
        }
        for v in VENDORS
    ]
    VENDORS_PATH.write_text(json.dumps(allowlist, indent=2) + "\n")

    # Three manifests.
    write_signed_manifest(
        plugin_id="trial-finder", version="2.4.1",
        manifest=_trial_finder_manifest(fps["helix-clinical"]),
        sk=keys["helix-clinical"], plugins_root=PLUGINS_ROOT,
    )
    write_signed_manifest(
        plugin_id="med-access", version="1.7.0",
        manifest=_med_access_manifest(fps["rxbridge"]),
        sk=keys["rxbridge"], plugins_root=PLUGINS_ROOT,
    )
    write_signed_manifest(
        plugin_id="second-opinion", version="0.9.0-beta",
        manifest=_second_opinion_manifest(fps["confermd"]),
        sk=keys["confermd"], plugins_root=PLUGINS_ROOT,
    )

    print("Wrote 3 signed manifests + vendor allowlist to", PLUGINS_ROOT)


if __name__ == "__main__":
    main()
