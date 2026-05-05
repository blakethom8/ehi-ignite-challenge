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
import os
from dataclasses import dataclass, field
from typing import Any

from api.core.skills.event_hub import EventHub
from api.core.skills.loader import Skill, load_skill, SKILLS_ROOT
from api.core.skills.patient_memory import PatientMemory
from api.core.skills.runner import RunResult, SkillRunner
from api.core.skills.workspace import Workspace, allocate_run_dir, load_workspace


_DEFAULT_CONCURRENCY = int(os.getenv("SKILLS_WORKER_CONCURRENCY", "2"))


@dataclass
class _RunState:
    runner: SkillRunner
    task: asyncio.Task[RunResult]
    event_hub: EventHub
    started_at: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


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
                    return await runner.run()
            finally:
                # End-of-stream signal — connected SSE clients complete
                # cleanly. Disk replay still serves any future readers.
                await event_hub.close()

        task = asyncio.create_task(_execute(), name=f"skill_run:{run_id}")
        async with self._lock:
            self._runs[self._key(patient_id, skill.name, run_id)] = _RunState(
                runner=runner, task=task, event_hub=event_hub
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
                    return await runner.resume()
            finally:
                await event_hub.close()

        task = asyncio.create_task(_continue(), name=f"skill_run_resume:{run_id}")
        async with self._lock:
            self._runs[key] = _RunState(
                runner=runner, task=task, event_hub=event_hub
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
