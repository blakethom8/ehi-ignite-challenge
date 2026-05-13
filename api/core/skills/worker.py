"""Skill run worker pool — Phase 1 worker layer (W1) per architecture §6.7.

The Phase-1 worker keeps the agent loop off the request handler so a slow or
hung run cannot block API traffic. It does *not* sandbox the run — that's
Phase 2 (W2) and arrives when we accept community skills, real PHI, or
multi-tenant orgs. The worker boundary contracts (workspace mediation,
citation enforcement) are already correct for the W2 migration; only the
execution shell changes.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any

from api.core.skills.event_hub import EventHub
from api.core.skills.loader import Skill, load_skill, SKILLS_ROOT
from api.core.skills.patient_memory import PatientMemory
from api.core.skills.runner import RunResult, SkillRunner
from api.core.skills.workspace import Workspace, allocate_run_dir, load_workspace
from api.settings import get_settings


_DEFAULT_CONCURRENCY = get_settings().skills_worker_concurrency


@dataclass
class _RunState:
    runner: SkillRunner
    task: asyncio.Task[RunResult]
    event_hub: EventHub
    user_id: str = ""
    session_id: str = ""
    started_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


def _emit_lifecycle_event(
    *,
    user_id: str,
    session_id: str,
    skill_name: str,
    patient_id: str,
    result: RunResult,
) -> None:
    """Translate a SkillRunner.RunResult into a workspace audit event.

    H0.9 — H0.5 only shipped run.started. Completion, escalation, and
    failure transitions also need to land in events.db so the per-user
    timeline shows the full lifecycle of every skill run.
    """
    # Lazy import keeps the worker module importable in tests that
    # monkeypatch the events module.
    from api.workspace.events import WORKSPACE_SKILL, record_event

    event_type = {
        "escalated": "run.escalated",
        "finished": "run.completed",
        "failed": "run.failed",
    }.get(result.status)
    if event_type is None:
        return
    record_event(
        user_id=user_id,
        session_id=session_id,
        workspace_kind=WORKSPACE_SKILL,
        event_type=event_type,
        target_id=result.run_id,
        payload={
            "skill_name": skill_name,
            "patient_id": patient_id,
            "status": result.status,
            "failure_reason": result.failure_reason,
        },
    )


class WorkerPool:
    """Asyncio-based worker pool with bounded concurrency.

    Tracks active runs by `(patient_id, skill_name, run_id)` so the router
    can poll status and resolve escalations against in-flight runs.
    """

    def __init__(self, concurrency: int = _DEFAULT_CONCURRENCY) -> None:
        self._semaphore = asyncio.Semaphore(concurrency)
        self._runs: dict[str, _RunState] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _key(patient_id: str, skill_name: str, run_id: str) -> str:
        return f"{patient_id}/{skill_name}/{run_id}"

    async def submit(
        self,
        skill: Skill,
        patient_id: str,
        brief: dict[str, Any],
        *,
        user_id: str = "",
        session_id: str = "",
    ) -> tuple[str, asyncio.Task[RunResult]]:
        run_dir = allocate_run_dir(patient_id, skill.name)
        run_id = run_dir.name
        memory = PatientMemory(patient_id)
        workspace = Workspace(
            skill=skill,
            patient_id=patient_id,
            patient_memory=memory,
            run_dir=run_dir,
            brief=brief,
        )
        event_hub = EventHub()
        runner = SkillRunner(
            skill=skill,
            workspace=workspace,
            patient_memory=memory,
            brief=brief,
            event_hub=event_hub,
        )

        async def _execute() -> RunResult:
            try:
                async with self._semaphore:
                    result = await runner.run()
                _emit_lifecycle_event(
                    user_id=user_id,
                    session_id=session_id,
                    skill_name=skill.name,
                    patient_id=patient_id,
                    result=result,
                )
                return result
            finally:
                # End-of-stream signal — connected SSE clients complete
                # cleanly. Disk replay still serves any future readers.
                await event_hub.close()

        task = asyncio.create_task(_execute(), name=f"skill_run:{run_id}")
        async with self._lock:
            self._runs[self._key(patient_id, skill.name, run_id)] = _RunState(
                runner=runner,
                task=task,
                event_hub=event_hub,
                user_id=user_id,
                session_id=session_id,
            )
        return run_id, task

    async def runner_for(
        self, patient_id: str, skill_name: str, run_id: str
    ) -> SkillRunner | None:
        async with self._lock:
            state = self._runs.get(self._key(patient_id, skill_name, run_id))
        return state.runner if state else None

    async def task_for(
        self, patient_id: str, skill_name: str, run_id: str
    ) -> asyncio.Task[RunResult] | None:
        async with self._lock:
            state = self._runs.get(self._key(patient_id, skill_name, run_id))
        return state.task if state else None

    async def hub_for(
        self, patient_id: str, skill_name: str, run_id: str
    ) -> EventHub | None:
        """Return the live event hub for an active run, or None if the run
        is not in memory (already finished, or process restarted)."""
        async with self._lock:
            state = self._runs.get(self._key(patient_id, skill_name, run_id))
        if state is None or state.event_hub.closed:
            return None
        return state.event_hub

    async def resume(
        self, patient_id: str, skill: Skill, run_id: str
    ) -> tuple[SkillRunner, asyncio.Task[RunResult]]:
        """Reattach to a paused run and continue execution.

        Used by the escalation-resolution endpoint: after writing the
        resolution to disk, the router calls this to kick the agent loop
        back into motion. If the runner is no longer in memory (e.g.,
        process restart), we rebuild it from the run dir.
        """
        key = self._key(patient_id, skill.name, run_id)
        async with self._lock:
            state = self._runs.get(key)

        # Resuming a run reuses the existing hub if still open; otherwise
        # spins up a fresh one so SSE subscribers can attach to the
        # continuation. The previous hub's subscribers (if any) have
        # already received the close sentinel.
        if state is None or state.event_hub.closed:
            event_hub = EventHub()
        else:
            event_hub = state.event_hub

        # Preserve the originator's identity across resumes — process
        # restarts (state is None) lose it, but in-memory resumes keep it
        # so the next lifecycle event still carries the right user_id.
        user_id = state.user_id if state else ""
        session_id = state.session_id if state else ""

        if state is None:
            workspace = load_workspace(skill, patient_id, run_id)
            memory = PatientMemory(patient_id)
            runner = SkillRunner(
                skill=skill,
                workspace=workspace,
                patient_memory=memory,
                brief=workspace.brief,
                event_hub=event_hub,
            )
        else:
            runner = state.runner
            runner.event_hub = event_hub

        async def _continue() -> RunResult:
            try:
                async with self._semaphore:
                    result = await runner.resume()
                _emit_lifecycle_event(
                    user_id=user_id,
                    session_id=session_id,
                    skill_name=skill.name,
                    patient_id=patient_id,
                    result=result,
                )
                return result
            finally:
                await event_hub.close()

        task = asyncio.create_task(_continue(), name=f"skill_run_resume:{run_id}")
        async with self._lock:
            self._runs[key] = _RunState(
                runner=runner,
                task=task,
                event_hub=event_hub,
                user_id=user_id,
                session_id=session_id,
            )
        return runner, task


# ── Module-level singleton ──────────────────────────────────────────────────


_pool: WorkerPool | None = None


def get_pool() -> WorkerPool:
    global _pool
    if _pool is None:
        _pool = WorkerPool()
    return _pool


def reset_pool_for_tests() -> None:
    global _pool
    _pool = WorkerPool()


# ── Skill registry helper ──────────────────────────────────────────────────


_skill_cache: dict[str, Skill] = {}


def get_skill(name: str) -> Skill:
    if name in _skill_cache:
        return _skill_cache[name]
    skill_dir = SKILLS_ROOT / name
    skill = load_skill(skill_dir)
    _skill_cache[name] = skill
    return skill


def reset_skill_cache_for_tests() -> None:
    _skill_cache.clear()
