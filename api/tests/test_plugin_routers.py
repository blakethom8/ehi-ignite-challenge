"""HTTP-layer tests for /api/plugins/*."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.core import auth as auth_core
from api.plugins import provenance as prov_log
from api.plugins import runtime as rt
from api.plugins.routers.plugins import router as plugins_router
from api.routers.auth import router as auth_router

from fastapi import FastAPI


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(rt, "DEFAULT_DB_PATH", tmp_path / "runs.db")
    monkeypatch.setattr(prov_log, "DEFAULT_DB_PATH", tmp_path / "provenance.db")
    monkeypatch.setattr(auth_core, "AUTH_DB_PATH", tmp_path / "auth.db")
    monkeypatch.setattr(auth_core, "SESSION_SECRET_PATH", tmp_path / "atlas-session.key")
    rt.reset_in_memory_state()

    app = FastAPI()
    app.include_router(auth_router, prefix="/api")
    app.include_router(plugins_router, prefix="/api")
    yield TestClient(app)
    rt.reset_in_memory_state()


def enter_authenticated_session(client: TestClient) -> None:
    response = client.post(
        "/api/auth/login",
        json={"email": "clinician@atlas.local", "password": "atlas-demo-password"},
    )
    assert response.status_code == 200


def test_list_installed_returns_three(client):
    enter_authenticated_session(client)
    res = client.get("/api/plugins/installed")
    assert res.status_code == 200
    ids = {m["id"] for m in res.json()}
    assert ids == {"trial-finder", "med-access", "second-opinion"}


def test_get_manifest_404_for_unknown(client):
    enter_authenticated_session(client)
    res = client.get("/api/plugins/no-such-plugin/manifest")
    assert res.status_code == 404


def test_start_run_then_grant_then_call_tool(client):
    enter_authenticated_session(client)
    res = client.post(
        "/api/plugins/runs",
        json={
            "pluginId": "trial-finder",
            "patientId": "8.4127.881",
            "workflowId": "shortlist",
            "title": "x",
        },
    )
    assert res.status_code == 200
    run = res.json()
    assert run["state"] == "awaiting-consent"

    res = client.post(f"/api/plugins/runs/{run['id']}/consent", json={})
    assert res.status_code == 200

    res = client.post(
        f"/api/plugins/runs/{run['id']}/tool/trial.search",
        json={"payload": {"connector": "clinicaltrials-gov"}},
    )
    assert res.status_code == 200
    assert any(s["nctId"] == "NCT-0421187" for s in res.json()["studies"])

    run_res = client.get(f"/api/plugins/runs/{run['id']}")
    assert run_res.status_code == 200
    body = run_res.json()
    assert body["canvas"]["trial.search"] == res.json()

    events_res = client.get(f"/api/plugins/runs/{run['id']}/events")
    assert events_res.status_code == 200
    tool_events = [event for event in events_res.json() if event["kind"] == "tool.result"]
    assert len(tool_events) == 1
    assert tool_events[0]["payload"]["toolId"] == "trial.search"
    assert tool_events[0]["payload"]["result"] == res.json()


def test_undeclared_connector_returns_403(client):
    enter_authenticated_session(client)
    run = client.post(
        "/api/plugins/runs",
        json={"pluginId": "trial-finder", "patientId": "8.4127.881"},
    ).json()
    client.post(f"/api/plugins/runs/{run['id']}/consent", json={})
    res = client.post(
        f"/api/plugins/runs/{run['id']}/tool/trial.search",
        json={"payload": {"connector": "surescripts-formulary"}},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "UndeclaredConnector"


def test_full_outbound_flow_writes_provenance(client):
    enter_authenticated_session(client)
    run = client.post(
        "/api/plugins/runs",
        json={
            "pluginId": "trial-finder",
            "patientId": "8.4127.881",
            "workflowId": "packet",
        },
    ).json()
    client.post(f"/api/plugins/runs/{run['id']}/consent", json={})
    draft = client.post(
        f"/api/plugins/runs/{run['id']}/tool/packet.draft",
        json={"payload": {"nctId": "NCT-0421187"}},
    ).json()
    appr = client.post(
        f"/api/plugins/runs/{run['id']}/approvals",
        json={
            "toolId": "packet.send",
            "toolPayload": {
                "channel": "site-packet",
                "site": "MSKCC",
                "artifactId": draft["artifactId"],
            },
            "action": "send-packet",
            "description": "Route packet to MSKCC",
            "payloadPreview": draft["preview"],
            "destination": "MSKCC",
        },
    ).json()
    res = client.post(
        f"/api/plugins/runs/{run['id']}/approvals/{appr['approvalId']}/approve",
        json={},
    )
    assert res.status_code == 200

    prov = client.get(f"/api/plugins/runs/{run['id']}/provenance").json()
    assert len(prov) == 1
    assert prov[0]["action"] == "send-packet"


def test_consent_required_when_calling_tool_before_grant(client):
    enter_authenticated_session(client)
    run = client.post(
        "/api/plugins/runs",
        json={"pluginId": "trial-finder", "patientId": "8.4127.881"},
    ).json()
    res = client.post(
        f"/api/plugins/runs/{run['id']}/tool/trial.search",
        json={"payload": {"connector": "clinicaltrials-gov"}},
    )
    assert res.status_code == 403
    assert res.json()["detail"]["error"] == "ConsentRequired"


def test_revoke_consent_voids_pending_approval(client):
    enter_authenticated_session(client)
    run = client.post(
        "/api/plugins/runs",
        json={
            "pluginId": "trial-finder",
            "patientId": "8.4127.881",
            "workflowId": "packet",
        },
    ).json()
    client.post(f"/api/plugins/runs/{run['id']}/consent", json={})
    draft = client.post(
        f"/api/plugins/runs/{run['id']}/tool/packet.draft",
        json={"payload": {"nctId": "NCT-0421187"}},
    ).json()
    client.post(
        f"/api/plugins/runs/{run['id']}/approvals",
        json={
            "toolId": "packet.send",
            "toolPayload": {"channel": "site-packet", "site": "MSKCC"},
            "action": "send-packet",
            "description": "x",
            "payloadPreview": draft["preview"],
            "destination": "MSKCC",
        },
    )
    res = client.post(f"/api/plugins/runs/{run['id']}/revoke-consent", json={})
    assert res.status_code == 200
    approvals = client.get(f"/api/plugins/runs/{run['id']}/approvals").json()
    assert all(a["status"] == "voided" for a in approvals)
