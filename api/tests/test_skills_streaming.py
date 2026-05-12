"""Tests for the streaming/connection layer: EventHub + SSE endpoint.

Companion doc: `docs/architecture/skill-runtime/STREAMING-AND-GATEWAY.md`.

The tests exercise:

- `EventHub` non-blocking publish, multi-subscriber fan-out, drop-on-full
  semantics, late subscribers getting nothing, and clean close.
- The SSE endpoint replaying transcript history, then attaching to the
  hub for live events when a run is in flight.
- The runner publishing through the hub when one is attached, and only
  writing to disk when the hub is absent (test-time default).
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from api.core.skills import workspace as workspace_module
from api.core.skills import patient_memory as memory_module
from api.core.skills import trial_pursuits as trial_pursuits_module
from api.core.skills.event_hub import EventHub
from api.core.skills.loader import SKILLS_ROOT, load_skill
from api.core.skills.patient_memory import PatientMemory
from api.core.skills.runner import SkillRunner
from api.core.skills.workspace import Workspace, allocate_run_dir


@pytest.fixture(autouse=True)
def isolated_cases_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    monkeypatch.setenv("SKILLS_CASES_PATH", str(cases_root))
    monkeypatch.setattr(workspace_module, "CASES_ROOT", cases_root)
    monkeypatch.setattr(memory_module, "CASES_ROOT", cases_root)
    monkeypatch.setattr(trial_pursuits_module, "CASES_ROOT", cases_root)
    return cases_root


@pytest.fixture(autouse=True)
def fake_skills_session(monkeypatch: pytest.MonkeyPatch):
    """Stand in for require_access_session in skill router tests.

    H0.7 made every POST require an authenticated session. The pre-existing
    tests in this file hit those endpoints without setting a cookie, so
    rather than re-route every test through the auth flow, we stub the
    session check at the router import site.
    """
    from datetime import datetime, timedelta, timezone

    from api.core.auth import SessionPrincipal
    from api.routers import skills as skills_router

    principal = SessionPrincipal(
        session_id="sess_test",
        mode="authenticated",
        user_id="u_test_clinician",
        email="test@atlas.local",
        display_name="Test Clinician",
        role="clinician",
        active_patient_id=None,
        active_patient_name=None,
        expires_at=datetime.now(timezone.utc) + timedelta(hours=1),
    )
    monkeypatch.setattr(skills_router, "require_access_session", lambda req: principal)
    monkeypatch.setattr(skills_router, "current_session", lambda req: principal)
    return principal


@pytest.fixture()
def trial_skill():
    return load_skill(SKILLS_ROOT / "trial-matching")


# ── EventHub ───────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_subscriber_receives_published_events() -> None:
    hub = EventHub()
    received: list[dict[str, Any]] = []

    async def consume() -> None:
        async for event in hub.subscribe():
            received.append(event)
            if len(received) == 2:
                return

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.02)  # let the subscription register

    hub.publish_nowait({"kind": "a"})
    hub.publish_nowait({"kind": "b"})
    await asyncio.wait_for(consumer, timeout=1.0)
    assert [e["kind"] for e in received] == ["a", "b"]


@pytest.mark.asyncio
async def test_late_subscribers_see_only_new_events() -> None:
    hub = EventHub()
    hub.publish_nowait({"kind": "before"})

    received: list[dict[str, Any]] = []

    async def consume() -> None:
        async for event in hub.subscribe():
            received.append(event)
            if event["kind"] == "after":
                return

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.02)
    hub.publish_nowait({"kind": "after"})
    await asyncio.wait_for(consumer, timeout=1.0)

    # The pre-subscribe event must NOT appear — the SSE endpoint replays
    # historical events out-of-band from disk; the hub is live-only.
    assert [e["kind"] for e in received] == ["after"]


@pytest.mark.asyncio
async def test_multi_subscriber_fan_out() -> None:
    hub = EventHub()
    bucket_a: list[dict[str, Any]] = []
    bucket_b: list[dict[str, Any]] = []

    async def consume(into: list[dict[str, Any]]) -> None:
        async for event in hub.subscribe():
            into.append(event)
            if len(into) == 3:
                return

    a = asyncio.create_task(consume(bucket_a))
    b = asyncio.create_task(consume(bucket_b))
    await asyncio.sleep(0.02)

    for i in range(3):
        hub.publish_nowait({"kind": "n", "i": i})

    await asyncio.wait_for(asyncio.gather(a, b), timeout=1.0)
    assert [e["i"] for e in bucket_a] == [0, 1, 2]
    assert [e["i"] for e in bucket_b] == [0, 1, 2]


@pytest.mark.asyncio
async def test_close_terminates_subscribers_cleanly() -> None:
    hub = EventHub()
    finished = asyncio.Event()

    async def consume() -> None:
        async for _ in hub.subscribe():
            pass
        finished.set()

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.02)
    await hub.close()
    await asyncio.wait_for(finished.wait(), timeout=1.0)
    assert hub.closed
    consumer.cancel()


@pytest.mark.asyncio
async def test_publish_after_close_is_no_op() -> None:
    hub = EventHub()
    await hub.close()
    # Must not raise.
    hub.publish_nowait({"kind": "x"})


@pytest.mark.asyncio
async def test_subscribe_after_close_yields_nothing() -> None:
    hub = EventHub()
    await hub.close()

    seen: list[dict[str, Any]] = []
    async for event in hub.subscribe():
        seen.append(event)
    assert seen == []


@pytest.mark.asyncio
async def test_slow_subscriber_does_not_block_publisher() -> None:
    """A subscriber that never consumes must not slow other subscribers
    or the publisher. Drop-on-full is the W1 contract."""
    hub = EventHub()

    fast: list[dict[str, Any]] = []

    async def consume_fast() -> None:
        async for event in hub.subscribe():
            fast.append(event)
            if len(fast) == 5:
                return

    # Slow subscriber: registers with a 2-slot queue and never reads —
    # it'll fill at 2 and drop the rest. Fast subscriber uses the default
    # 256-slot queue and must still receive every event.
    slow_iter = hub.subscribe(maxsize=2)
    slow_first = asyncio.create_task(slow_iter.__anext__())
    fast_task = asyncio.create_task(consume_fast())
    await asyncio.sleep(0.02)

    for i in range(5):
        hub.publish_nowait({"kind": "n", "i": i})

    await asyncio.wait_for(fast_task, timeout=1.0)
    assert [e["i"] for e in fast] == [0, 1, 2, 3, 4]
    slow_first.cancel()


# ── Runner publishes through hub ──────────────────────────────────────────


@pytest.mark.asyncio
async def test_runner_publishes_emitted_events_through_hub(trial_skill) -> None:
    async def create_message(**_kwargs: Any) -> dict[str, Any]:
        return {
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "workspace_escalate",
                    "input": {
                        "condition": "no_anchor_condition",
                        "prompt": "No target trial condition is available.",
                    },
                }
            ],
        }

    memory = PatientMemory("hub-001")
    run_dir = allocate_run_dir("hub-001", trial_skill.name)
    workspace = Workspace(
        skill=trial_skill,
        patient_id="hub-001",
        patient_memory=memory,
        run_dir=run_dir,
        brief={"anchors": []},
    )
    hub = EventHub()
    runner = SkillRunner(
        skill=trial_skill,
        workspace=workspace,
        patient_memory=memory,
        brief={"anchors": [], "_agent_overrides": {"create_message": create_message}},
        event_hub=hub,
    )

    received: list[dict[str, Any]] = []

    async def consume() -> None:
        async for event in hub.subscribe():
            received.append(event)
            if event["kind"] == "escalation":
                return

    consumer = asyncio.create_task(consume())
    await asyncio.sleep(0.02)

    result = await runner.run()
    await asyncio.wait_for(consumer, timeout=1.0)

    assert result.status == "escalated"
    kinds = [e["kind"] for e in received]
    assert "run_started" in kinds or "run_resumed" in kinds
    assert "escalation" in kinds


@pytest.mark.asyncio
async def test_runner_without_hub_still_records_to_disk(trial_skill) -> None:
    """Backwards-compatible: a runner with no hub still writes the
    transcript. Hub is purely the live fast path."""
    async def create_message(**_kwargs: Any) -> dict[str, Any]:
        return {
            "stop_reason": "tool_use",
            "content": [
                {
                    "type": "tool_use",
                    "id": "t1",
                    "name": "workspace_escalate",
                    "input": {
                        "condition": "no_anchor_condition",
                        "prompt": "No target trial condition is available.",
                    },
                }
            ],
        }

    memory = PatientMemory("nohub-001")
    run_dir = allocate_run_dir("nohub-001", trial_skill.name)
    workspace = Workspace(
        skill=trial_skill,
        patient_id="nohub-001",
        patient_memory=memory,
        run_dir=run_dir,
        brief={"anchors": []},
    )
    runner = SkillRunner(
        skill=trial_skill,
        workspace=workspace,
        patient_memory=memory,
        brief={"anchors": [], "_agent_overrides": {"create_message": create_message}},
        event_hub=None,
    )
    await runner.run()
    transcript = list(workspace.transcript_events())
    assert any(e.get("kind") == "escalation" for e in transcript)


# ── SSE endpoint ──────────────────────────────────────────────────────────


def _parse_sse_data_lines(payload: bytes) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for line in payload.decode("utf-8").splitlines():
        if line.startswith("data: "):
            events.append(json.loads(line[len("data: ") :]))
    return events


def test_sse_endpoint_replays_transcript_for_finished_run(
    trial_skill, isolated_cases_root: Path
) -> None:
    """A run that's already finished should still stream the full
    transcript on connect, followed by a close sentinel."""
    memory = PatientMemory("sse-finished-001")
    run_dir = allocate_run_dir("sse-finished-001", trial_skill.name)
    workspace = Workspace(
        skill=trial_skill,
        patient_id="sse-finished-001",
        patient_memory=memory,
        run_dir=run_dir,
        brief={"anchors": []},
    )
    workspace.start()
    workspace.escalate(
        condition="no_anchor_condition",
        prompt="Confirm anchor.",
    )
    # Don't resolve — run stays escalated, hub never created.

    from api.main import app
    client = TestClient(app)
    response = client.get(
        f"/api/skills/{trial_skill.name}/runs/{run_dir.name}/events",
        params={"patient_id": "sse-finished-001"},
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")

    events = _parse_sse_data_lines(response.content)
    assert events, "must emit at least the close sentinel"
    assert events[-1]["kind"] == "stream_closed"
    kinds = [e["kind"] for e in events]
    assert "escalation" in kinds


def test_sse_endpoint_404_for_unknown_run(trial_skill) -> None:
    from api.main import app
    client = TestClient(app)
    response = client.get(
        f"/api/skills/{trial_skill.name}/runs/does-not-exist/events",
        params={"patient_id": "nobody"},
    )
    assert response.status_code == 404


def test_messages_endpoint_appends_and_lists_run_messages(trial_skill) -> None:
    memory = PatientMemory("messages-api-001")
    run_dir = allocate_run_dir("messages-api-001", trial_skill.name)
    workspace = Workspace(
        skill=trial_skill,
        patient_id="messages-api-001",
        patient_memory=memory,
        run_dir=run_dir,
        brief={"anchors": []},
    )
    workspace.start()

    from api.main import app

    client = TestClient(app)
    response = client.post(
        f"/api/skills/{trial_skill.name}/runs/{run_dir.name}/messages",
        params={"patient_id": "messages-api-001"},
        json={
            "actor": "clinician",
            "message": "Look more closely at trials with travel support.",
            "canvas_ref": {"kind": "trial_list", "selected_nct_ids": ["NCT01234567"]},
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["message_id"].startswith("m_")
    assert payload["consumed"] is False

    list_response = client.get(
        f"/api/skills/{trial_skill.name}/runs/{run_dir.name}/messages",
        params={"patient_id": "messages-api-001"},
    )
    assert list_response.status_code == 200
    messages = list_response.json()["messages"]
    assert len(messages) == 1
    assert messages[0]["message"] == "Look more closely at trials with travel support."


def test_inspector_endpoint_returns_run_workspace_contract(trial_skill) -> None:
    memory = PatientMemory("inspector-api-001")
    run_dir = allocate_run_dir("inspector-api-001", trial_skill.name)
    workspace = Workspace(
        skill=trial_skill,
        patient_id="inspector-api-001",
        patient_memory=memory,
        run_dir=run_dir,
        brief={
            "anchors": [
                {
                    "display": "Alzheimer's disease",
                    "resource_id": "cond-1",
                    "risk_category": "NEUROLOGIC",
                }
            ],
            "trial_guidance": "Boston only",
        },
    )
    workspace.start()
    workspace.upsert_canvas_node(
        node_id="trial:NCT01234567",
        kind="candidate_trial",
        title="Demo trial",
        data={"nct_id": "NCT01234567"},
    )

    from api.main import app

    client = TestClient(app)
    response = client.get(
        f"/api/skills/{trial_skill.name}/runs/{run_dir.name}/inspector",
        params={"patient_id": "inspector-api-001"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["run"]["run_id"] == run_dir.name
    assert payload["skill"]["name"] == trial_skill.name
    assert payload["context"]["brief"]["trial_guidance"] == "Boston only"
    assert any(tool["alias"] == "query_chart_evidence" for tool in payload["tools"])
    assert payload["permissions"]["enabled_capabilities"]["canvas_writes"] is True
    assert payload["artifacts"]["files"]


def test_canvas_endpoint_lists_and_selects_nodes(trial_skill) -> None:
    memory = PatientMemory("canvas-api-001")
    run_dir = allocate_run_dir("canvas-api-001", trial_skill.name)
    workspace = Workspace(
        skill=trial_skill,
        patient_id="canvas-api-001",
        patient_memory=memory,
        run_dir=run_dir,
        brief={"anchors": []},
    )
    workspace.start()
    workspace.upsert_canvas_node(
        node_id="trial:NCT01234567",
        kind="candidate_trial",
        title="A test trial",
        status="candidate",
    )

    from api.main import app

    client = TestClient(app)
    list_response = client.get(
        f"/api/skills/{trial_skill.name}/runs/{run_dir.name}/canvas",
        params={"patient_id": "canvas-api-001"},
    )
    assert list_response.status_code == 200
    assert any(
        node["node_id"] == "trial:NCT01234567"
        for node in list_response.json()["nodes"]
    )

    select_response = client.post(
        f"/api/skills/{trial_skill.name}/runs/{run_dir.name}/canvas/nodes/trial%3ANCT01234567/selection",
        params={"patient_id": "canvas-api-001"},
        json={"selected": True},
    )
    assert select_response.status_code == 200
    assert select_response.json()["selected"] is True


def test_trial_pursuit_endpoints_create_project_board_item() -> None:
    from api.main import app

    client = TestClient(app)
    patient_id = "trial-pursuit-api-001"
    create_response = client.post(
        f"/api/skills/patients/{patient_id}/trial-pursuits",
        json={
            "nct_id": "NCT01234567",
            "title": "A durable trial",
            "status": "interested",
            "sponsor": "Demo sponsor",
            "fit_score": 82,
            "created_from_run_id": "run-123",
            "created_from_canvas_node_id": "trial:NCT01234567",
            "evidence_snapshot": {"anchor": "Alzheimer's disease"},
        },
    )
    assert create_response.status_code == 200
    pursuit = create_response.json()
    assert pursuit["nct_id"] == "NCT01234567"
    assert pursuit["status"] == "interested"
    assert pursuit["events"][0]["kind"] == "created"

    task_response = client.post(
        f"/api/skills/patients/{patient_id}/trial-pursuits/{pursuit['pursuit_id']}/tasks",
        json={"title": "Call site coordinator"},
    )
    assert task_response.status_code == 200
    assert task_response.json()["tasks"][0]["title"] == "Call site coordinator"

    update_response = client.patch(
        f"/api/skills/patients/{patient_id}/trial-pursuits/{pursuit['pursuit_id']}",
        json={
            "status": "packet",
            "next_step": "Prepare outreach packet.",
            "event_note": "Clinician wants to pursue this trial.",
        },
    )
    assert update_response.status_code == 200
    assert update_response.json()["status"] == "packet"

    list_response = client.get(f"/api/skills/patients/{patient_id}/trial-pursuits")
    assert list_response.status_code == 200
    pursuits = list_response.json()["pursuits"]
    assert len(pursuits) == 1
    assert pursuits[0]["next_step"] == "Prepare outreach packet."
