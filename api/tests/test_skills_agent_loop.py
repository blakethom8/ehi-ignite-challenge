"""Tests for the Claude agent loop + mode dispatch.

Uses a scripted fake `create_message` so tests never make real API
calls. The fake mimics Anthropic's response shape closely enough that
the loop's tool dispatch + escalation + finalize paths are all exercised.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from api.core.skills import workspace as workspace_module
from api.core.skills import patient_memory as memory_module
from api.core.skills.agent_loop import (
    AgentConfig,
    AgentLoopAbort,
    drive_claude_agent_loop,
    load_config,
)
from api.core.skills.event_hub import EventHub
from api.core.skills.loader import SKILLS_ROOT, load_skill
from api.core.skills.patient_memory import PatientMemory
from api.core.skills.runner import SkillRunner
from api.core.skills.workspace import Workspace, allocate_run_dir


# ── Fake Anthropic response objects ────────────────────────────────────────


@dataclass
class FakeBlock:
    type: str  # "text" | "tool_use"
    text: str = ""
    name: str = ""
    id: str = ""
    input: dict[str, Any] = field(default_factory=dict)


@dataclass
class FakeResponse:
    content: list[FakeBlock]
    stop_reason: str = "tool_use"


def _text(text: str) -> FakeBlock:
    return FakeBlock(type="text", text=text)


def _tool(name: str, input: dict[str, Any], id: str | None = None) -> FakeBlock:
    return FakeBlock(
        type="tool_use",
        name=name,
        id=id or f"tu_{abs(hash(name)) % 100000:05d}",
        input=input,
    )


def _scripted(scripts: list[FakeResponse]):
    """Return a `create_message` callable that yields scripted responses."""
    iterator = iter(scripts)

    async def create_message(**kwargs: Any) -> FakeResponse:
        try:
            return next(iterator)
        except StopIteration:
            raise AssertionError(
                "fake create_message called more times than scripted responses"
            )

    return create_message


# ── Fixtures ───────────────────────────────────────────────────────────────


@pytest.fixture(autouse=True)
def isolated_cases_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    cases_root = tmp_path / "cases"
    cases_root.mkdir()
    monkeypatch.setenv("SKILLS_CASES_PATH", str(cases_root))
    monkeypatch.setattr(workspace_module, "CASES_ROOT", cases_root)
    monkeypatch.setattr(memory_module, "CASES_ROOT", cases_root)
    return cases_root


@pytest.fixture()
def trial_skill():
    return load_skill(SKILLS_ROOT / "trial-matching")


def _runner(trial_skill, brief: dict[str, Any], patient_id: str = "agent-test-001"):
    memory = PatientMemory(patient_id)
    run_dir = allocate_run_dir(patient_id, trial_skill.name)
    hub = EventHub()
    workspace = Workspace(
        skill=trial_skill,
        patient_id=patient_id,
        patient_memory=memory,
        run_dir=run_dir,
        brief=brief,
        event_hub=hub,
    )
    workspace.start()
    runner = SkillRunner(
        skill=trial_skill,
        workspace=workspace,
        patient_memory=memory,
        brief=brief,
        event_hub=hub,
    )
    return runner


# ── Configuration ──────────────────────────────────────────────────────────


def test_load_config_has_sane_defaults(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SKILLS_AGENT_MODEL", raising=False)
    monkeypatch.delenv("SKILLS_AGENT_MAX_TURNS", raising=False)
    monkeypatch.delenv("SKILLS_AGENT_MAX_TOKENS", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    cfg = load_config()
    assert cfg.model.startswith("claude-")
    assert 1 <= cfg.max_turns <= 100
    assert 256 <= cfg.max_tokens_per_turn <= 64000
    assert cfg.has_credentials is False


def test_load_config_clamps_out_of_range(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SKILLS_AGENT_MAX_TURNS", "9999")
    monkeypatch.setenv("SKILLS_AGENT_MAX_TOKENS", "10")
    cfg = load_config()
    assert cfg.max_turns == 100
    assert cfg.max_tokens_per_turn == 256


def test_has_credentials_rejects_placeholder() -> None:
    cfg = AgentConfig(
        model="claude-sonnet-4-6",
        max_turns=30,
        max_tokens_per_turn=4096,
        api_key="sk-ant-YOUR_KEY_HERE",
    )
    assert cfg.has_credentials is False


# ── Mode dispatch ──────────────────────────────────────────────────────────


def test_run_mode_defaults_to_deterministic(trial_skill) -> None:
    runner = _runner(trial_skill, brief={})
    assert runner.resolve_run_mode() == "deterministic"


def test_run_mode_brief_override_wins(
    trial_skill, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SKILLS_RUN_MODE", "deterministic")
    runner = _runner(trial_skill, brief={"_run_mode": "agent"})
    assert runner.resolve_run_mode() == "agent"


def test_run_mode_env_var_used_when_no_brief_override(
    trial_skill, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SKILLS_RUN_MODE", "agent")
    runner = _runner(trial_skill, brief={})
    assert runner.resolve_run_mode() == "agent"


def test_run_mode_unknown_falls_back_to_deterministic(
    trial_skill, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SKILLS_RUN_MODE", "telepathic")
    runner = _runner(trial_skill, brief={})
    assert runner.resolve_run_mode() == "deterministic"


def test_run_mode_auto_falls_back_when_no_credentials(
    trial_skill, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SKILLS_RUN_MODE", "auto")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    runner = _runner(trial_skill, brief={})
    assert runner.resolve_run_mode() == "deterministic"


def test_run_mode_auto_promotes_when_credentials_present(
    trial_skill, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("SKILLS_RUN_MODE", "auto")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-real-looking-key")
    runner = _runner(trial_skill, brief={})
    assert runner.resolve_run_mode() == "agent"


# ── Agent loop happy path ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_loop_finalizes_with_scripted_artifact(trial_skill) -> None:
    runner = _runner(trial_skill, brief={"anchors": []})

    artifact = {
        "run_id": runner.workspace.run_id,
        "skill_version": trial_skill.manifest.version,
        "patient_id": runner.workspace.patient_id,
        "summary": {
            "trials_reviewed": 0,
            "trials_surviving": 0,
            "trials_excluded": 0,
            "confidence_note": "no anchors — agent skipped search",
        },
        "trials": [],
        "escalations": [],
    }

    create_message = _scripted(
        [
            FakeResponse(
                stop_reason="tool_use",
                content=[
                    _text("I'll register the empty-shortlist artifact."),
                    _tool("submit_final_artifact", {"output": artifact}),
                ],
            )
        ]
    )

    cfg = AgentConfig(
        model="claude-test", max_turns=5, max_tokens_per_turn=1024, api_key="x"
    )
    output = await drive_claude_agent_loop(
        runner, create_message=create_message, config=cfg
    )
    assert output["summary"]["trials_reviewed"] == 0
    assert runner.agent_state["finalize_signal"] is True


@pytest.mark.asyncio
async def test_agent_loop_dispatches_workspace_cite_then_write(trial_skill) -> None:
    """Multi-turn loop: cite → write → finalize."""
    runner = _runner(trial_skill, brief={})

    artifact = {
        "run_id": runner.workspace.run_id,
        "skill_version": trial_skill.manifest.version,
        "patient_id": runner.workspace.patient_id,
        "summary": {
            "trials_reviewed": 1,
            "trials_surviving": 1,
            "trials_excluded": 0,
            "confidence_note": "demo",
        },
        "trials": [
            {
                "nct_id": "NCT12345678",
                "title": "Demo trial",
                "fit_score": 70,
                "evidence_tier": "T2",
                "supporting_facts": [],
                "gaps": [],
                "excluded": False,
                "escalation_triggered": False,
            }
        ],
        "escalations": [],
    }

    create_message = _scripted(
        [
            FakeResponse(
                stop_reason="tool_use",
                content=[
                    _tool(
                        "workspace_cite",
                        {
                            "claim": "Trial NCT12345678 retrieved",
                            "source_kind": "external_url",
                            "source_ref": "https://clinicaltrials.gov/study/NCT12345678",
                            "evidence_tier": "T2",
                        },
                        id="t1",
                    )
                ],
            ),
            FakeResponse(
                stop_reason="tool_use",
                content=[
                    _tool(
                        "workspace_write",
                        {
                            "section": "NCT12345678",
                            "content": "Demo trial body [cite:c_0001].",
                            "anchor": "TRIAL_SECTIONS",
                        },
                        id="t2",
                    )
                ],
            ),
            FakeResponse(
                stop_reason="tool_use",
                content=[
                    _tool(
                        "submit_final_artifact",
                        {"output": artifact},
                        id="t3",
                    )
                ],
            ),
        ]
    )

    cfg = AgentConfig(
        model="claude-test", max_turns=10, max_tokens_per_turn=1024, api_key="x"
    )
    output = await drive_claude_agent_loop(
        runner, create_message=create_message, config=cfg
    )

    assert output["trials"][0]["nct_id"] == "NCT12345678"
    workspace_md = runner.workspace.workspace_md_path.read_text("utf-8")
    assert "NCT12345678" in workspace_md
    assert "[cite:c_0001]" in workspace_md


# ── Escalation pauses the loop ─────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_loop_pauses_on_escalation(trial_skill) -> None:
    runner = _runner(trial_skill, brief={"anchors": []})

    create_message = _scripted(
        [
            FakeResponse(
                stop_reason="tool_use",
                content=[
                    _tool(
                        "workspace_escalate",
                        {
                            "condition": "no_anchor_condition",
                            "prompt": "No anchors — confirm or skip?",
                        },
                    )
                ],
            )
        ]
    )

    cfg = AgentConfig(
        model="claude-test", max_turns=5, max_tokens_per_turn=1024, api_key="x"
    )
    output = await drive_claude_agent_loop(
        runner, create_message=create_message, config=cfg
    )

    assert output == {}
    assert runner.workspace.status == "escalated"
    assert runner.agent_state["escalation_signal"] is True


# ── Failure paths ──────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_agent_loop_aborts_when_max_turns_exceeded(trial_skill) -> None:
    runner = _runner(trial_skill, brief={})

    # Every response calls workspace_cite (a tool that won't trigger
    # finalize), forcing the loop to keep going.
    response = FakeResponse(
        stop_reason="tool_use",
        content=[
            _tool(
                "workspace_cite",
                {
                    "claim": "x",
                    "source_kind": "agent_inference",
                    "evidence_tier": "T4",
                },
            )
        ],
    )
    create_message = _scripted([response, response, response])

    cfg = AgentConfig(
        model="claude-test", max_turns=2, max_tokens_per_turn=1024, api_key="x"
    )
    with pytest.raises(AgentLoopAbort, match="2 turns"):
        await drive_claude_agent_loop(
            runner, create_message=create_message, config=cfg
        )


@pytest.mark.asyncio
async def test_agent_loop_aborts_when_agent_ends_without_finalizing(
    trial_skill,
) -> None:
    runner = _runner(trial_skill, brief={})

    create_message = _scripted(
        [
            FakeResponse(
                stop_reason="end_turn",
                content=[_text("I'm done thinking.")],
            )
        ]
    )

    cfg = AgentConfig(
        model="claude-test", max_turns=5, max_tokens_per_turn=1024, api_key="x"
    )
    with pytest.raises(AgentLoopAbort, match="without calling submit_final_artifact"):
        await drive_claude_agent_loop(
            runner, create_message=create_message, config=cfg
        )


@pytest.mark.asyncio
async def test_unknown_tool_call_returns_error_not_crash(trial_skill) -> None:
    """An unknown tool call should produce an error tool_result, not raise."""
    runner = _runner(trial_skill, brief={})

    artifact = {
        "run_id": runner.workspace.run_id,
        "skill_version": trial_skill.manifest.version,
        "patient_id": runner.workspace.patient_id,
        "summary": {
            "trials_reviewed": 0,
            "trials_surviving": 0,
            "trials_excluded": 0,
            "confidence_note": "n/a",
        },
        "trials": [],
        "escalations": [],
    }
    create_message = _scripted(
        [
            FakeResponse(
                stop_reason="tool_use",
                content=[_tool("delete_everything", {})],
            ),
            FakeResponse(
                stop_reason="tool_use",
                content=[_tool("submit_final_artifact", {"output": artifact})],
            ),
        ]
    )

    cfg = AgentConfig(
        model="claude-test", max_turns=5, max_tokens_per_turn=1024, api_key="x"
    )
    output = await drive_claude_agent_loop(
        runner, create_message=create_message, config=cfg
    )
    assert output["summary"]["trials_reviewed"] == 0
    # Loop survived the unknown tool call and finalized.


@pytest.mark.asyncio
async def test_workspace_contract_error_is_surfaced_as_tool_error(trial_skill) -> None:
    """A workspace contract error from a tool handler must come back as
    an error tool result so the agent can correct its next turn — not
    crash the loop."""
    runner = _runner(trial_skill, brief={})

    artifact = {
        "run_id": runner.workspace.run_id,
        "skill_version": trial_skill.manifest.version,
        "patient_id": runner.workspace.patient_id,
        "summary": {
            "trials_reviewed": 0,
            "trials_surviving": 0,
            "trials_excluded": 0,
            "confidence_note": "n/a",
        },
        "trials": [],
        "escalations": [],
    }

    create_message = _scripted(
        [
            FakeResponse(
                stop_reason="tool_use",
                content=[
                    _tool(
                        "workspace_cite",
                        {
                            "claim": "x",
                            "source_kind": "fhir_resource",
                            # missing source_ref — should fail validation
                            "evidence_tier": "T1",
                        },
                    )
                ],
            ),
            FakeResponse(
                stop_reason="tool_use",
                content=[_tool("submit_final_artifact", {"output": artifact})],
            ),
        ]
    )

    cfg = AgentConfig(
        model="claude-test", max_turns=5, max_tokens_per_turn=1024, api_key="x"
    )
    # Should NOT raise — the contract error becomes a tool result and
    # the agent's next turn finalizes.
    output = await drive_claude_agent_loop(
        runner, create_message=create_message, config=cfg
    )
    assert output["summary"]["trials_reviewed"] == 0


# ── Tool registry filtering ───────────────────────────────────────────────


def test_tool_registry_includes_submit_final_artifact_even_if_skill_omits_it(
    trial_skill,
) -> None:
    from api.core.skills.agent_loop import _resolve_tools_for_skill

    # The trial-matching skill doesn't list submit_final_artifact in
    # its required_tools — but the loop adds it automatically because
    # there's no other way to end the run cleanly.
    specs = _resolve_tools_for_skill(list(trial_skill.manifest.required_tools))
    names = {s.name for s in specs}
    assert "submit_final_artifact" in names
    assert "workspace_cite" in names
    assert "workspace_write" in names
    assert "workspace_escalate" in names


def test_tool_registry_drops_unknown_aliases() -> None:
    from api.core.skills.agent_loop import _resolve_tools_for_skill

    specs = _resolve_tools_for_skill(["workspace.write", "mcp.bogus.tool"])
    names = {s.name for s in specs}
    assert "workspace_write" in names
    assert "mcp.bogus.tool" not in names
    assert "submit_final_artifact" in names
