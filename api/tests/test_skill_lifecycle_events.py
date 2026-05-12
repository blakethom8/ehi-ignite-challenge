"""H0.9 regression: skill lifecycle events: completed + escalated.

H0.5 shipped only ``run.started``. The audit timeline was missing every
``run.completed`` and ``run.escalated`` transition. This file exercises
the worker pool directly to confirm the new lifecycle events land in
events.db with the originating user's id, even across an escalation +
resume cycle.
"""

from __future__ import annotations

import asyncio
import importlib
from pathlib import Path

import pytest

from api.core.skills import patient_memory as memory_module
from api.core.skills import trial_pursuits as trial_pursuits_module
from api.core.skills import workspace as workspace_module
from api.core.skills.loader import SKILLS_ROOT, load_skill
from api.core.skills.runner import RunResult


@pytest.fixture(autouse=True)
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    events_db = tmp_path / "events.db"
    monkeypatch.setenv("SKILLS_CASES_PATH", str(cases_root))
    monkeypatch.setenv("EVENTS_DB_PATH", str(events_db))
    monkeypatch.setenv("EVENTS_REDACTION_PRESET", "minimal")
    monkeypatch.setattr(workspace_module, "CASES_ROOT", cases_root)
    monkeypatch.setattr(memory_module, "CASES_ROOT", cases_root)
    monkeypatch.setattr(trial_pursuits_module, "CASES_ROOT", cases_root)

    # Reload events to pick up the env var.
    from api.workspace import events as events_mod

    importlib.reload(events_mod)

    # Reload worker so its lazy import of events points at the reloaded module.
    from api.core.skills import worker as worker_mod

    importlib.reload(worker_mod)

    return tmp_path


@pytest.fixture
def trial_skill():
    return load_skill(SKILLS_ROOT / "trial-matching")


def _query_events(tmp_path):
    from api.workspace import events as events_mod

    return events_mod.query_events(db_path=tmp_path / "events.db")


@pytest.mark.asyncio
async def test_run_completion_emits_completed_event(
    isolated_state, trial_skill, monkeypatch
):
    """A successful skill run ends with run.completed in events.db,
    keyed on the originating user_id."""
    from api.core.skills import worker as worker_mod

    pool = worker_mod.WorkerPool(concurrency=1)

    # Stub the runner so this test stays fast and deterministic — the
    # lifecycle event emission is what we're verifying, not the agent loop.
    async def fake_run(self):
        self.workspace._set_status("finished")
        return RunResult(
            run_id=self.workspace.run_id, status="finished", output={"ok": True}
        )

    from api.core.skills.runner import SkillRunner

    monkeypatch.setattr(SkillRunner, "run", fake_run)

    run_id, task = await pool.submit(
        skill=trial_skill,
        patient_id="lifecycle-001",
        brief={"anchors": []},
        user_id="u_alice",
        session_id="sess_abc",
    )
    await task

    events = _query_events(isolated_state)
    completion = [
        e for e in events if e["event_type"] == "run.completed"
    ]
    assert len(completion) == 1
    assert completion[0]["user_id"] == "u_alice"
    assert completion[0]["session_id"] == "sess_abc"
    assert completion[0]["target_id"] == run_id
    assert completion[0]["payload"]["skill_name"] == trial_skill.name


@pytest.mark.asyncio
async def test_run_escalation_emits_escalated_event(
    isolated_state, trial_skill, monkeypatch
):
    """When a run ends in escalation, run.escalated lands in events.db."""
    from api.core.skills import worker as worker_mod

    pool = worker_mod.WorkerPool(concurrency=1)

    async def fake_run(self):
        self.workspace._set_status("escalated")
        return RunResult(
            run_id=self.workspace.run_id, status="escalated", output=None
        )

    from api.core.skills.runner import SkillRunner

    monkeypatch.setattr(SkillRunner, "run", fake_run)

    run_id, task = await pool.submit(
        skill=trial_skill,
        patient_id="lifecycle-002",
        brief={"anchors": []},
        user_id="u_bob",
        session_id="sess_xyz",
    )
    await task

    events = _query_events(isolated_state)
    escalations = [e for e in events if e["event_type"] == "run.escalated"]
    assert len(escalations) == 1
    assert escalations[0]["user_id"] == "u_bob"
    assert escalations[0]["target_id"] == run_id


@pytest.mark.asyncio
async def test_run_failure_emits_failed_event(
    isolated_state, trial_skill, monkeypatch
):
    from api.core.skills import worker as worker_mod

    pool = worker_mod.WorkerPool(concurrency=1)

    async def fake_run(self):
        self.workspace._set_status("failed")
        return RunResult(
            run_id=self.workspace.run_id,
            status="failed",
            output=None,
            failure_reason="contrived test failure",
        )

    from api.core.skills.runner import SkillRunner

    monkeypatch.setattr(SkillRunner, "run", fake_run)

    _, task = await pool.submit(
        skill=trial_skill,
        patient_id="lifecycle-003",
        brief={"anchors": []},
        user_id="u_carol",
        session_id="sess_q",
    )
    await task

    events = _query_events(isolated_state)
    failures = [e for e in events if e["event_type"] == "run.failed"]
    assert len(failures) == 1
    assert failures[0]["payload"]["failure_reason"] == "contrived test failure"


@pytest.mark.asyncio
async def test_resume_after_escalation_preserves_user_id(
    isolated_state, trial_skill, monkeypatch
):
    """The escalation→resume→completion cycle must keep the same
    originating user_id across all three events."""
    from api.core.skills import worker as worker_mod

    pool = worker_mod.WorkerPool(concurrency=1)

    call_count = {"n": 0}

    async def fake_run(self):
        call_count["n"] += 1
        # First call: escalates. Second call (via resume): completes.
        if call_count["n"] == 1:
            self.workspace._set_status("escalated")
            return RunResult(
                run_id=self.workspace.run_id, status="escalated", output=None
            )
        self.workspace._set_status("finished")
        return RunResult(
            run_id=self.workspace.run_id, status="finished", output={"ok": True}
        )

    async def fake_resume(self):
        return await self.run()

    from api.core.skills.runner import SkillRunner

    monkeypatch.setattr(SkillRunner, "run", fake_run)
    monkeypatch.setattr(SkillRunner, "resume", fake_resume)

    run_id, start_task = await pool.submit(
        skill=trial_skill,
        patient_id="lifecycle-004",
        brief={"anchors": []},
        user_id="u_dana",
        session_id="sess_r",
    )
    await start_task

    _, resume_task = await pool.resume(
        patient_id="lifecycle-004", skill=trial_skill, run_id=run_id
    )
    await resume_task

    events = _query_events(isolated_state)
    types = [e["event_type"] for e in events]
    assert types.count("run.escalated") == 1
    assert types.count("run.completed") == 1
    # All lifecycle events carry the same originating user_id.
    user_ids = {
        e["user_id"]
        for e in events
        if e["event_type"] in {"run.escalated", "run.completed"}
    }
    assert user_ids == {"u_dana"}
