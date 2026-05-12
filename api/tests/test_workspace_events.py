"""H0.5 regression: api/workspace/events.py — unified event log.

Schema + happy-path writes + the cross-surface query that H0.6's audit
endpoint depends on. The exit criterion is that a single user_id can
join across caspian, skill, and plugin events in one query.
"""

from __future__ import annotations

import pytest

from api.workspace.events import (
    WORKSPACE_CASPIAN,
    WORKSPACE_PLUGIN,
    WORKSPACE_SKILL,
    query_events,
    record_event,
    record_event_for_session,
)


@pytest.fixture
def db(tmp_path):
    return tmp_path / "events.db"


def test_record_event_writes_row(db):
    eid = record_event(
        user_id="u_1",
        session_id="sess_1",
        workspace_kind=WORKSPACE_CASPIAN,
        event_type="chat.turn",
        target_id="patient_42",
        payload={"question_preview": "what allergies?", "stance": "opinionated"},
        db_path=db,
    )
    assert eid.startswith("e_")
    rows = query_events(user_id="u_1", db_path=db)
    assert len(rows) == 1
    row = rows[0]
    assert row["workspace_kind"] == "caspian"
    assert row["event_type"] == "chat.turn"
    assert row["target_id"] == "patient_42"
    # Default preset (events-strict) redacts free-text fields; non-PHI metadata
    # like `stance` survives.
    assert row["payload"]["question_preview"] == "[redacted]"
    assert row["payload"]["stance"] == "opinionated"


def test_per_user_query_joins_three_workspace_kinds(db):
    """The H0.5 exit criterion: one user, three workspace kinds, one query."""
    user_id = "u_clinician_42"
    session_id = "sess_abc"

    record_event(
        user_id=user_id,
        session_id=session_id,
        workspace_kind=WORKSPACE_CASPIAN,
        event_type="chat.turn",
        target_id="patient_77",
        payload={"question_preview": "summarize"},
        db_path=db,
    )
    record_event(
        user_id=user_id,
        session_id=session_id,
        workspace_kind=WORKSPACE_SKILL,
        event_type="run.started",
        target_id="r_skill_1",
        payload={"skill_name": "discharge_summary"},
        db_path=db,
    )
    record_event(
        user_id=user_id,
        session_id=session_id,
        workspace_kind=WORKSPACE_PLUGIN,
        event_type="tool.called",
        target_id="trial.search",
        payload={"runId": "r_plugin_1"},
        db_path=db,
    )

    # Same user, no other filter — all three surfaces show up.
    rows = query_events(user_id=user_id, db_path=db)
    assert len(rows) == 3
    assert {r["workspace_kind"] for r in rows} == {"caspian", "skill", "plugin"}

    # A different user sees nothing.
    assert query_events(user_id="u_someone_else", db_path=db) == []


def test_record_event_for_session_handles_none(db):
    """No session (e.g. unauthenticated bg job) → no-op, no exception."""
    eid = record_event_for_session(
        None,
        workspace_kind=WORKSPACE_SKILL,
        event_type="run.started",
        target_id="r_x",
        db_path=db,
    )
    assert eid == ""
    assert query_events(db_path=db) == []


def test_record_event_for_session_extracts_principal_fields(db):
    class FakePrincipal:
        user_id = "u_99"
        session_id = "sess_99"

    record_event_for_session(
        FakePrincipal(),
        workspace_kind=WORKSPACE_PLUGIN,
        event_type="consent.granted",
        target_id="r_99",
        payload={"approverId": "u_99"},
        db_path=db,
    )
    rows = query_events(user_id="u_99", db_path=db)
    assert len(rows) == 1
    assert rows[0]["session_id"] == "sess_99"
    assert rows[0]["target_id"] == "r_99"


def test_workspace_kind_filter(db):
    record_event(
        user_id="u_1", session_id="s", workspace_kind=WORKSPACE_PLUGIN,
        event_type="tool.called", db_path=db,
    )
    record_event(
        user_id="u_1", session_id="s", workspace_kind=WORKSPACE_SKILL,
        event_type="run.started", db_path=db,
    )
    rows = query_events(user_id="u_1", workspace_kind="plugin", db_path=db)
    assert len(rows) == 1
    assert rows[0]["event_type"] == "tool.called"


def test_payload_redaction_strips_patient_name_from_freetext(monkeypatch, db):
    """H0.8 regression: a clinician question that embeds a patient name
    must not survive in the audit log."""
    monkeypatch.setenv("EVENTS_REDACTION_PRESET", "events-strict")
    # Reload events to pick up the env var.
    import importlib
    import api.workspace.events as events_mod

    importlib.reload(events_mod)

    events_mod.record_event(
        user_id="u_1",
        session_id="s",
        workspace_kind="caspian",
        event_type="chat.turn",
        target_id="patient_42",
        payload={
            "question_preview": "what allergies does John Hollister have?",
            "stance": "opinionated",
        },
        db_path=db,
    )
    rows = events_mod.query_events(user_id="u_1", db_path=db)
    assert len(rows) == 1
    payload = rows[0]["payload"]
    # Free-text field replaced; non-PHI metadata preserved.
    assert payload["question_preview"] == "[redacted]"
    assert payload["stance"] == "opinionated"
    # Belt-and-suspenders: the name string must not appear anywhere.
    assert "Hollister" not in str(payload)


def test_payload_redaction_strips_direct_identifier_keys(monkeypatch, db):
    """H0.8: keys named like direct identifiers (name, mrn, dob...) get
    stripped entirely, not just their string values."""
    monkeypatch.setenv("EVENTS_REDACTION_PRESET", "events-strict")
    import importlib
    import api.workspace.events as events_mod

    importlib.reload(events_mod)

    events_mod.record_event(
        user_id="u_2",
        session_id="s",
        workspace_kind="plugin",
        event_type="run.started",
        target_id="r_1",
        payload={
            "patient_name": "Jane Doe",
            "mrn": "12345",
            "pluginId": "trial-finder",  # not PII; survives
        },
        db_path=db,
    )
    rows = events_mod.query_events(user_id="u_2", db_path=db)
    payload = rows[0]["payload"]
    assert "patient_name" not in payload
    assert "mrn" not in payload
    assert payload["pluginId"] == "trial-finder"


def test_minimal_preset_disables_redaction_for_dev(monkeypatch, db):
    """Operators can flip EVENTS_REDACTION_PRESET=minimal in dev to see
    raw payloads when debugging."""
    monkeypatch.setenv("EVENTS_REDACTION_PRESET", "minimal")
    import importlib
    import api.workspace.events as events_mod

    importlib.reload(events_mod)

    events_mod.record_event(
        user_id="u_3",
        session_id="s",
        workspace_kind="caspian",
        event_type="chat.turn",
        target_id="p",
        payload={"question_preview": "raw text with patient name"},
        db_path=db,
    )
    rows = events_mod.query_events(user_id="u_3", db_path=db)
    assert rows[0]["payload"]["question_preview"] == "raw text with patient name"


def test_record_event_failure_returns_empty_string(monkeypatch, db):
    """Audit must never break the request path — failures swallow + log."""
    import api.workspace.events as events_mod

    def boom(*args, **kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(events_mod, "_conn", boom)
    eid = record_event(
        user_id="u", session_id="s", workspace_kind="caspian",
        event_type="chat.turn", db_path=db,
    )
    assert eid == ""
