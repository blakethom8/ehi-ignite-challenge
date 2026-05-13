"""H0.4 regression: TracingMiddleware covers caspian + skill + plugin
surfaces, and every trace carries (user_id, session_id, workspace_kind).

The plan's smoke test contract: a single run exercises all three
audited POST surfaces and lands three trace rows in traces.db with
matching user_id and three distinct workspace_kinds.
"""

from __future__ import annotations

import importlib
import sqlite3

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture
def traced_app(monkeypatch, tmp_path):
    """Build a minimal FastAPI app with TracingMiddleware + the three
    audited routes (stub handlers). Tracing writes to a tmp traces.db."""
    db_path = tmp_path / "traces.db"
    monkeypatch.setenv("TRACING_ENABLED", "true")
    monkeypatch.setenv("TRACES_DB_PATH", str(db_path))
    monkeypatch.setenv("TRACING_SAMPLE_RATE", "1.0")

    # Reload tracing so the env vars are picked up at module level.
    from api.core import tracing as core_tracing
    from api.middleware import tracing as middleware_tracing

    importlib.reload(core_tracing)
    importlib.reload(middleware_tracing)

    # Pin a deterministic identity in place of the real cookie-based session.
    def fake_identity(request):
        return ("u_test_user", "sess_test_42")

    monkeypatch.setattr(middleware_tracing, "_session_identity", fake_identity)

    app = FastAPI()
    app.add_middleware(middleware_tracing.TracingMiddleware)

    @app.post("/api/assistant/chat")
    async def chat():
        return {"engine": "context"}

    @app.post("/api/assistant/chat/stream")
    async def chat_stream():
        return {"engine": "context"}

    @app.post("/api/skills/{name}/runs")
    async def skill_run(name: str):
        return {"runId": "r_skill_1"}

    @app.post("/api/plugins/runs/{run_id}/tool/{tool_id}")
    async def plugin_tool(run_id: str, tool_id: str):
        return {"ok": True}

    return app, db_path


def _read_traces(db_path) -> list[dict]:
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        try:
            rows = conn.execute(
                "SELECT trace_id, user_id, session_id, workspace_kind FROM traces "
                "ORDER BY created_at"
            ).fetchall()
        except sqlite3.OperationalError:
            # Table not created yet — no traces ever written.
            return []
        return [dict(r) for r in rows]
    finally:
        conn.close()


def test_three_surfaces_emit_traces_with_join_keys(traced_app):
    app, db_path = traced_app
    client = TestClient(app)

    # Caspian chat — middleware reads body for patient_id/question.
    r1 = client.post(
        "/api/assistant/chat",
        json={"patient_id": "p1", "question": "what allergies?", "stance": "opinionated"},
    )
    assert r1.status_code == 200

    # Skill run start — no body parsing needed.
    r2 = client.post("/api/skills/discharge_summary/runs", json={"patient_id": "p1"})
    assert r2.status_code == 200

    # Plugin tool call.
    r3 = client.post("/api/plugins/runs/r_abc/tool/trial.search", json={})
    assert r3.status_code == 200

    rows = _read_traces(db_path)
    assert len(rows) == 3, f"expected 3 traces, got {len(rows)}: {rows}"

    # Same user joins all three.
    assert {r["user_id"] for r in rows} == {"u_test_user"}
    assert {r["session_id"] for r in rows} == {"sess_test_42"}

    # Three distinct workspace kinds.
    assert {r["workspace_kind"] for r in rows} == {"caspian", "skill", "plugin"}


def test_non_audited_path_is_not_traced(traced_app):
    app, db_path = traced_app
    client = TestClient(app)

    @app.get("/api/health")
    async def health():
        return {"ok": True}

    r = client.get("/api/health")
    assert r.status_code == 200
    rows = _read_traces(db_path)
    assert rows == []


def test_streaming_chat_path_is_also_traced(traced_app):
    app, db_path = traced_app
    client = TestClient(app)

    r = client.post(
        "/api/assistant/chat/stream",
        json={"patient_id": "p1", "question": "what changed?", "stance": "opinionated"},
    )
    assert r.status_code == 200

    rows = _read_traces(db_path)
    assert len(rows) == 1
    assert rows[0]["workspace_kind"] == "caspian"


def test_sample_rate_zero_drops_all_traces(monkeypatch, tmp_path):
    db_path = tmp_path / "traces.db"
    monkeypatch.setenv("TRACING_ENABLED", "true")
    monkeypatch.setenv("TRACES_DB_PATH", str(db_path))
    monkeypatch.setenv("TRACING_SAMPLE_RATE", "0.0")

    from api.core import tracing as core_tracing
    from api.middleware import tracing as middleware_tracing

    importlib.reload(core_tracing)
    importlib.reload(middleware_tracing)
    monkeypatch.setattr(
        middleware_tracing, "_session_identity", lambda r: ("u", "s")
    )

    app = FastAPI()
    app.add_middleware(middleware_tracing.TracingMiddleware)

    @app.post("/api/assistant/chat")
    async def chat():
        return {"ok": True}

    client = TestClient(app)
    for _ in range(20):
        client.post("/api/assistant/chat", json={"patient_id": "x", "question": "q"})

    rows = _read_traces(db_path) if db_path.exists() else []
    assert rows == []
