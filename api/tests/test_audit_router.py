"""H0.6 regression: per-user audit timeline endpoint.

Plan exit criterion: GET /api/audit/users/{user_id}?since=1h returns a
single chronological timeline that joins events from three workspace
kinds for the same user, gated by bearer token in production.
"""

from __future__ import annotations

import importlib

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def audit_client(monkeypatch, tmp_path):
    events_db = tmp_path / "events.db"
    monkeypatch.setenv("EVENTS_DB_PATH", str(events_db))
    monkeypatch.setenv("AUDIT_API_TOKEN", "test-token-xyz")
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("TRACES_DB_PATH", str(tmp_path / "traces.db"))

    # Reload events + audit so the new env vars take effect.
    from api.workspace import events as events_mod
    from api.routers import audit as audit_mod

    importlib.reload(events_mod)
    importlib.reload(audit_mod)

    app = FastAPI()
    app.include_router(audit_mod.router, prefix="/api")
    client = TestClient(app)
    return client, events_mod, events_db


def _seed_three_kinds(events_mod, user_id: str = "u_q1"):
    events_mod.record_event(
        user_id=user_id, session_id="sess_a",
        workspace_kind="caspian", event_type="chat.turn",
        target_id="patient_x", payload={"q": "what allergies?"},
    )
    events_mod.record_event(
        user_id=user_id, session_id="sess_a",
        workspace_kind="skill", event_type="run.started",
        target_id="r_skill_1", payload={"skill_name": "discharge_summary"},
    )
    events_mod.record_event(
        user_id=user_id, session_id="sess_a",
        workspace_kind="plugin", event_type="tool.called",
        target_id="trial.search", payload={"runId": "r_plug_1"},
    )


def test_user_timeline_joins_three_workspace_kinds(audit_client):
    """The flagship deliverable: one user, three surfaces, one query."""
    client, events_mod, _ = audit_client
    _seed_three_kinds(events_mod)

    r = client.get(
        "/api/audit/users/u_q1?since=1970-01-01T00:00:00Z",
        headers={"Authorization": "Bearer test-token-xyz"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["user_id"] == "u_q1"
    assert body["count"] == 3
    kinds = {entry["workspace_kind"] for entry in body["timeline"]}
    assert kinds == {"caspian", "skill", "plugin"}
    # Sorted ascending by ts.
    timestamps = [entry["ts"] for entry in body["timeline"]]
    assert timestamps == sorted(timestamps)


def test_user_timeline_filters_by_workspace_kind(audit_client):
    client, events_mod, _ = audit_client
    _seed_three_kinds(events_mod)

    r = client.get(
        "/api/audit/users/u_q1?workspace_kind=plugin&since=1970-01-01T00:00:00Z",
        headers={"Authorization": "Bearer test-token-xyz"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["count"] == 1
    assert body["timeline"][0]["workspace_kind"] == "plugin"
    assert body["timeline"][0]["event_type"] == "tool.called"


def test_user_timeline_returns_empty_for_other_user(audit_client):
    client, events_mod, _ = audit_client
    _seed_three_kinds(events_mod, user_id="u_q1")

    r = client.get(
        "/api/audit/users/u_someone_else?since=1970-01-01T00:00:00Z",
        headers={"Authorization": "Bearer test-token-xyz"},
    )
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_user_timeline_rejects_missing_token(audit_client):
    client, _, _ = audit_client
    r = client.get("/api/audit/users/u_q1")
    assert r.status_code == 401


def test_user_timeline_rejects_wrong_token(audit_client):
    client, _, _ = audit_client
    r = client.get(
        "/api/audit/users/u_q1",
        headers={"Authorization": "Bearer wrong"},
    )
    assert r.status_code == 401


def test_me_endpoint_requires_session(audit_client):
    client, _, _ = audit_client
    r = client.get("/api/audit/me")
    assert r.status_code == 401
