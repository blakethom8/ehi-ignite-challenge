"""Skill runner — orchestrates one run from start through finalize.

The runner is the bridge between the workspace contract (Layer 1) and the
agent loop (Layer 2). It:

1. Mounts the patient memory + brief into the agent's session-start context.
2. Registers the universal workspace primitives + skill-declared tools.
3. Drives the production agent loop.
4. Translates agent escalation calls into run-status transitions.
5. On natural completion, requests the final structured artifact and
   invokes `workspace.finalize`.

The runner is intentionally small: per the architecture doc §6.0, the
"Layer 2 default agent loop" is one canonical loop. Skill-specific
behavior lives in `SKILL.md`, not here.
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import dataclass
from typing import Any

from api.core.skills.event_hub import EventHub
from api.core.skills.loader import Skill
from api.core.skills.patient_memory import PatientMemory
from api.core.skills.workspace import (
    TranscriptEvent,
    Workspace,
    WorkspaceContractError,
)


@dataclass
class RunResult:
    run_id: str
    status: str
    output: dict[str, Any] | None
    failure_reason: str | None = None


class SkillRunner:
    """Drives a single skill run.

    Public surface:
    - `await runner.run()` — run to completion, escalation, or failure.
    - `await runner.resume()` — continue after an escalation is resolved.

    Live progress is broadcast via an injected `EventHub` (the worker
    pool owns the hub lifecycle); SSE endpoints subscribe to that hub.
    The runner itself does not expose an event stream — that
    responsibility lives in Layer 1 substrate, not in the runner.
    """

    def __init__(
        self,
        skill: Skill,
        workspace: Workspace,
        patient_memory: PatientMemory,
        brief: dict[str, Any],
        event_hub: EventHub | None = None,
    ) -> None:
        self.skill = skill
        self.workspace = workspace
        self.patient_memory = patient_memory
        self.brief = dict(brief)
        # Hub plumbing lives on the workspace — every transcript event
        # (whether emitted from the runner or from a workspace internal
        # like `escalate`) reaches the hub uniformly. We attach here for
        # callers that pass the hub through the runner constructor.
        if event_hub is not None and workspace.event_hub is None:
            workspace.event_hub = event_hub
        self._completed = asyncio.Event()
        # Loose-typed scratch space for the active loop implementation
        # (`escalation_signal`, `finalize_signal`, `final_artifact` live here).
        # Kept on the runner instance so the loop can stay a free function.
        self.agent_state: dict[str, Any] = {}

    @property
    def event_hub(self) -> EventHub | None:
        return self.workspace.event_hub

    @event_hub.setter
    def event_hub(self, hub: EventHub | None) -> None:
        self.workspace.event_hub = hub

    # ── Event emission ──────────────────────────────────────────────────

    def _emit(self, kind: str, **payload: Any) -> None:
        """Emit a structured event via the workspace transcript.

        The workspace handles both disk persistence and (if a hub is
        attached) live broadcast. Keeping all emission funnelled through
        `Workspace.append_transcript` is what guarantees that escalations
        and citations — emitted from inside workspace primitives —
        reach the hub on the same path as runner-level events.
        """
        self.workspace.append_transcript(TranscriptEvent(kind=kind, payload=payload))

    # ── System prompt assembly ──────────────────────────────────────────

    def system_prompt(self) -> str:
        chunks = [
            f"# Skill: {self.skill.name} v{self.skill.manifest.version}",
            "",
            self.skill.body.strip(),
        ]
        memory = self.patient_memory.session_context(
            requested_packages=list(self.skill.manifest.context_packages)
        )
        if memory.strip():
            chunks.append("\n---\n")
            chunks.append(memory)
        chunks.append("\n---\n")
        chunks.append("# Brief inputs for this run\n")
        chunks.append("```json")
        # Drop underscore-prefixed keys (test injectables, internal state).
        public_brief = {k: v for k, v in self.brief.items() if not k.startswith("_")}
        chunks.append(json.dumps(public_brief, indent=2, sort_keys=True, default=str))
        chunks.append("```")
        return "\n".join(chunks)

    # ── Lifecycle ───────────────────────────────────────────────────────

    async def run(self) -> RunResult:
        self.workspace.start()
        self._emit("system_prompt_assembled", char_count=len(self.system_prompt()))
        try:
            output = await self._drive_agent_loop()
        except WorkspaceContractError as exc:
            self.workspace.fail(str(exc))
            self._emit("run_failed", reason=str(exc))
            self._completed.set()
            return RunResult(
                run_id=self.workspace.run_id,
                status="failed",
                output=None,
                failure_reason=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            self.workspace.fail(repr(exc))
            self._emit("run_failed", reason=repr(exc))
            self._completed.set()
            return RunResult(
                run_id=self.workspace.run_id,
                status="failed",
                output=None,
                failure_reason=repr(exc),
            )

        if self.workspace.status == "escalated":
            self._completed.set()
            return RunResult(
                run_id=self.workspace.run_id,
                status="escalated",
                output=None,
            )

        try:
            final = self.workspace.finalize(output)
        except WorkspaceContractError as exc:
            self.workspace.fail(str(exc))
            self._emit("finalize_failed", reason=str(exc))
            self._completed.set()
            return RunResult(
                run_id=self.workspace.run_id,
                status="failed",
                output=None,
                failure_reason=str(exc),
            )

        self._emit("run_finished")
        self._completed.set()
        return RunResult(
            run_id=self.workspace.run_id,
            status="finished",
            output=final,
        )

    async def resume(self) -> RunResult:
        if self.workspace.pending_escalations():
            return RunResult(
                run_id=self.workspace.run_id,
                status="escalated",
                output=None,
            )
        return await self.run()

    # ── Agent loop ──────────────────────────────────────────────────────

    def resolve_run_mode(self) -> str:
        """Decide which loop implementation to use for this run.

        Precedence (highest first):
        1. Per-run brief: `_run_mode` ("agent" | "auto")
        2. Env var: `SKILLS_RUN_MODE`
        3. Default: "agent"

        `auto` is accepted as an alias for `agent` so old deploy configs keep
        working, but there is no deterministic fallback. If the real agent
        runtime is not configured, the run fails with a clear setup error.
        """
        from api.settings import get_settings

        raw = (
            self.brief.get("_run_mode")
            or get_settings().skills_run_mode
            or "agent"
        )
        mode = str(raw).strip().lower() or "agent"
        if mode == "deterministic":
            raise WorkspaceContractError(
                "deterministic skill runs are disabled; configure the production "
                "agent runtime instead"
            )
        if mode == "auto":
            return "agent"
        if mode != "agent":
            raise WorkspaceContractError(
                f"unsupported skill run mode '{raw}'; only agent mode is supported"
            )
        return "agent"

    async def _drive_agent_loop(self) -> dict[str, Any]:
        """Drive the agent until it produces a final artifact.

        Tests can inject a scripted agent loop by setting
        `brief["_agent_overrides"] = {"create_message": fake_fn}`.
        """
        mode = self.resolve_run_mode()
        self._emit("agent_loop_dispatched", mode=mode, skill=self.skill.name)

        from api.core.skills.agent_loop import (
            AgentLoopAbort,
            drive_claude_agent_loop,
        )

        overrides = self.brief.get("_agent_overrides") or {}
        try:
            return await drive_claude_agent_loop(self, **overrides)
        except AgentLoopAbort as exc:
            raise WorkspaceContractError(f"agent loop aborted: {exc}") from exc
