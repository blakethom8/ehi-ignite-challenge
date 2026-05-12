"""H0.7 regression: every write endpoint on /api/skills/* requires an
authenticated session.

Before this fix, anonymous callers could start runs (and other write
operations) which meant H0.5's record_event wrote empty user_id values
for every skill action — silently breaking the per-user audit story
for the workspace surface most likely to drive 'what did Dr. X do?'
queries.

This file checks the auth wall directly (no monkeypatch of the session
check, unlike test_skills_streaming.py): every POST returns 401 without
a session, and a logged-in caller writes a non-empty user_id to events.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def configured_app(tmp_path, monkeypatch):
    """Boot a TestClient with isolated DB paths so the auth + events stores
    don't pollute the real data/ directory."""
    monkeypatch.setenv("EHI_AUTH_DB_PATH", str(tmp_path / "auth.db"))
    monkeypatch.setenv("EHI_SESSION_SECRET", "x" * 32)
    monkeypatch.setenv("EVENTS_DB_PATH", str(tmp_path / "events.db"))
    monkeypatch.setenv("SKILLS_CASES_PATH", str(tmp_path / "cases"))
    (tmp_path / "cases").mkdir()

    # Reload modules that read these env vars at import time.
    from api.core import auth as auth_mod
    from api.workspace import events as events_mod

    importlib.reload(auth_mod)
    importlib.reload(events_mod)

    from api.main import app

    return TestClient(app), tmp_path


def test_anonymous_post_runs_returns_401(configured_app):
    client, _ = configured_app
    r = client.post(
        "/api/skills/trial-matching/runs",
        json={"patient_id": "p_anon"},
    )
    assert r.status_code == 401


def test_anonymous_post_messages_returns_401(configured_app):
    client, _ = configured_app
    r = client.post(
        "/api/skills/trial-matching/runs/r_dummy/messages?patient_id=p_anon",
        json={"actor": "clinician", "message": "test"},
    )
    assert r.status_code == 401


def test_anonymous_post_save_returns_401(configured_app):
    client, _ = configured_app
    r = client.post(
        "/api/skills/trial-matching/runs/r_dummy/save?patient_id=p_anon",
        json={"destination": "run", "edits_markdown": "x", "actor": "clinician"},
    )
    assert r.status_code == 401


def test_authenticated_run_writes_non_empty_user_id_to_events(
    configured_app, monkeypatch
):
    """The H0.7 deliverable: H0.5's record_event no longer silently
    records empty user_id for skill runs."""
    client, tmp_path = configured_app

    # Sign up + log in to get an HTTP-only session cookie.
    signup = client.post(
        "/api/auth/signup",
        json={
            "email": "skills-auth-test@atlas.local",
            "password": "hunter2-skills-test-password",
            "display_name": "Skills Auth Tester",
        },
    )
    assert signup.status_code == 200
    body = signup.json()
    assert body["mode"] == "authenticated"
    user_id = body["user"]["id"]

    # Stub the skills pool's submit so we don't actually run the skill — we
    # only care that the auth wall lets us through and the event lands.
    from api.routers import skills as skills_router

    class _StubTask:
        pass

    class _StubPool:
        async def submit(self, *, skill, patient_id, brief, user_id="", session_id=""):
            return ("r_test_run_42", _StubTask())

    monkeypatch.setattr(skills_router, "get_pool", lambda: _StubPool())

    r = client.post(
        "/api/skills/trial-matching/runs",
        json={"patient_id": "p_test"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["run_id"] == "r_test_run_42"

    # The event must carry the signed-in user's id.
    from api.workspace.events import query_events

    events = query_events(user_id=user_id, db_path=tmp_path / "events.db")
    assert len(events) == 1
    event = events[0]
    assert event["workspace_kind"] == "skill"
    assert event["event_type"] == "run.started"
    assert event["target_id"] == "r_test_run_42"
    assert event["user_id"] == user_id
    assert event["session_id"]  # non-empty
