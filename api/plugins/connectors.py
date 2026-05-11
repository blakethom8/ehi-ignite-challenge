"""Connector registry for the three example plugins.

v1: every connector reads from a fixture JSON file on disk. The
fixture path is keyed by connector id and lives at
``data/plugins/{plugin_id}/fixtures/{fixture}.json``. v2 routes
through real HTTP adapters.

Each connector function takes ``(payload: dict) -> dict``. The payload
shape is connector-specific; callers see the same return shape as the
real registry would produce in v2.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from api.trust.keys import REPO_ROOT


ConnectorFn = Callable[[dict], dict]
REGISTRY: dict[str, ConnectorFn] = {}


class ConnectorError(Exception):
    pass


class UndeclaredConnector(ConnectorError):
    pass


class RedactionMismatch(ConnectorError):
    pass


def register(connector_id: str) -> Callable[[ConnectorFn], ConnectorFn]:
    def _decorator(fn: ConnectorFn) -> ConnectorFn:
        REGISTRY[connector_id] = fn
        return fn

    return _decorator


def _read_fixture(plugin_id: str, name: str) -> dict:
    p = REPO_ROOT / "data" / "plugins" / plugin_id / "fixtures" / f"{name}.json"
    return json.loads(p.read_text())


# ============================================================
# Trial Finder connectors
# ============================================================


@register("clinicaltrials-gov")
def _ctgov(payload: dict) -> dict:
    fx = _read_fixture("trial-finder", "clinicaltrials_gov")
    return {
        "endpoint": "https://clinicaltrials.gov/api/v2/studies",
        "status": 200,
        "studies": fx["studies"],
    }


@register("nci-trial-connect")
def _nci(payload: dict) -> dict:
    fx = _read_fixture("trial-finder", "nci_trial_connect")
    return {
        "endpoint": "https://trialconnect.cancer.gov/api/studies",
        "status": 200,
        "studies": fx["studies"],
    }


# ============================================================
# Medication Access connectors
# ============================================================


@register("surescripts-formulary")
def _surescripts(payload: dict) -> dict:
    fx = _read_fixture("med-access", "surescripts_formulary")
    return {
        "endpoint": "https://formulary.surescripts.net/api/lookup",
        "status": 200,
        "results": fx["results"],
    }


@register("manufacturer-pap-api")
def _pap(payload: dict) -> dict:
    fx = _read_fixture("med-access", "manufacturer_pap")
    action = payload.get("action", "lookup")
    if action == "enroll":
        return {
            "endpoint": "https://pap.bms3b.com/api/enroll",
            "status": 201,
            "enrollmentId": "PAP-2026-001142",
            "summary": "Enrollment received; eligibility confirmation pending.",
        }
    return {
        "endpoint": "https://pap.bms3b.com/api/programs",
        "status": 200,
        "programs": fx["programs"],
    }


@register("payer-portal-edi")
def _payer(payload: dict) -> dict:
    fx = _read_fixture("med-access", "payer_portal")
    return {
        "endpoint": fx["ack"]["endpoint"],
        "status": 202,
        "submissionId": fx["ack"]["submissionId"],
        "summary": f"PA received. Expected adjudication: {fx['ack']['expectedAdjudicationDays']}d.",
    }


# ============================================================
# Second Opinion connectors
# ============================================================


@register("confermd-network")
def _confermd(payload: dict) -> dict:
    fx = _read_fixture("second-opinion", "confermd")
    action = payload.get("action", "lookup")
    if action == "route":
        return {
            "endpoint": fx["routing"]["endpoint"],
            "status": 202,
            "referenceId": fx["routing"]["ack"]["referenceId"],
            "summary": "Referral queued in consulting network.",
        }
    return {
        "endpoint": "https://api.confermd.com/v1/specialists",
        "status": 200,
        "specialists": fx["specialists"],
    }


# ============================================================
# Dispatch
# ============================================================


def call_connector(connector_id: str, payload: dict) -> dict:
    fn = REGISTRY.get(connector_id)
    if fn is None:
        raise UndeclaredConnector(f"no connector registered for: {connector_id}")
    return fn(payload)
