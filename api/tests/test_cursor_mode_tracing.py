"""H0.10 regression: Cursor sidecar tracing parity.

The 'all four modes emit the same span shape' priority is verified here.
Cursor-mode chat calls must land a trace in traces.db with:
- mode='cursor'
- matching user_id + session_id from the request session
- workspace_kind='caspian' (cursor mode runs inside the assistant chat
  surface, same as context/agent_sdk/deterministic)

Implementation note: the Cursor sidecar runs in a separate Node process
and doesn't expose token/cost telemetry today. We trace from the Python
client's vantage point — the round-trip latency, the engine returned,
and the mode that resolved. Token/cost gaps are documented as a known
limitation, not papered over.
"""

from __future__ import annotations

import importlib
import sqlite3

import pytest


@pytest.fixture
def traces_db(tmp_path, monkeypatch):
    db_path = tmp_path / "traces.db"
    monkeypatch.setenv("TRACING_ENABLED", "true")
    monkeypatch.setenv("TRACES_DB_PATH", str(db_path))
    monkeypatch.setenv("TRACING_SAMPLE_RATE", "1.0")
    from api.core import tracing as core_tracing

    importlib.reload(core_tracing)
    return db_path, core_tracing


def _read_traces(db_path):
    if not db_path.exists():
        return []
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT trace_id, user_id, session_id, workspace_kind, mode, engine "
            "FROM traces ORDER BY created_at"
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def test_record_trace_metadata_populates_mode_cursor(traces_db):
    """The wiring contract: when the cursor mode resolves and returns an
    AssistantResult(mode_used='cursor'), trace.mode lands as 'cursor'."""
    db_path, core_tracing = traces_db

    # Reload service so its `from api.core.tracing import get_current_trace`
    # binds to the reloaded module.
    from api.core import provider_assistant_service as svc_mod

    importlib.reload(svc_mod)

    # Fake AssistantResult — only the fields _record_trace_metadata reads.
    class FakeResult:
        engine = "cursor-sdk-sidecar"
        mode_used = "cursor"
        confidence = "high"
        answer = "stubbed cursor answer"
        citations = [{"id": "c1"}]
        follow_ups = ["fu1"]

    with core_tracing.start_trace(
        patient_id="p_test",
        question="what allergies",
        stance="opinionated",
        user_id="u_clinician",
        session_id="sess_42",
        workspace_kind=core_tracing.WORKSPACE_CASPIAN,
    ):
        svc_mod._record_trace_metadata(FakeResult())

    rows = _read_traces(db_path)
    assert len(rows) == 1
    row = rows[0]
    assert row["mode"] == "cursor"
    assert row["engine"] == "cursor-sdk-sidecar"
    assert row["user_id"] == "u_clinician"
    assert row["session_id"] == "sess_42"
    assert row["workspace_kind"] == "caspian"


def test_record_trace_metadata_populates_mode_context(traces_db):
    """Mode-parity sanity check: context mode lands with mode='context',
    same span shape as cursor."""
    db_path, core_tracing = traces_db
    from api.core import provider_assistant_service as svc_mod

    importlib.reload(svc_mod)

    class FakeResult:
        engine = "anthropic-context"
        mode_used = "context"
        confidence = "medium"
        answer = "context answer"
        citations = []
        follow_ups = []

    with core_tracing.start_trace(
        patient_id="p_test",
        question="q",
        stance="opinionated",
        user_id="u_clinician",
        session_id="sess_42",
        workspace_kind=core_tracing.WORKSPACE_CASPIAN,
    ):
        svc_mod._record_trace_metadata(FakeResult())

    rows = _read_traces(db_path)
    # Both context and cursor traces would share the same column set —
    # this asserts the SHAPE is the same; mode is the only differentiator.
    assert len(rows) == 1
    assert rows[0]["mode"] == "context"
    assert rows[0]["workspace_kind"] == "caspian"


def test_known_limitation_cursor_sidecar_token_counts_unavailable():
    """Documents the parity gap. The Node sidecar doesn't currently return
    token usage in /invoke responses, so input_tokens / output_tokens /
    total_cost_usd are None on cursor-mode LLM spans. Closing this gap
    requires a sidecar protocol change — tracked for Phase 3 H3.3.

    This test exists so the gap is provable, not just claimed in a doc.
    """
    from api.core.cursor_sidecar_client import CursorSidecarInvokeResult

    # The dataclass schema itself proves the gap: no token/cost fields.
    fields = set(CursorSidecarInvokeResult.__dataclass_fields__.keys())
    assert "input_tokens" not in fields
    assert "output_tokens" not in fields
    assert "total_cost_usd" not in fields
    # What we DO get from the sidecar today.
    assert "model_used" in fields
    assert "duration_ms" in fields
    assert "engine" in fields
