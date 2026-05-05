"""Skill runner — orchestrates one run from start through finalize.

The runner is the bridge between the workspace contract (Layer 1) and the
agent loop (Layer 2). It:

1. Mounts the patient memory + brief into the agent's session-start context.
2. Registers the universal workspace primitives + skill-declared tools.
3. Drives the agent loop via `claude-agent-sdk` (or a deterministic fake
   for tests).
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
import os
from dataclasses import dataclass
from typing import Any

from api.core.skills import clinicaltrials_gov as ctgov
from api.core.skills.event_hub import EventHub
from api.core.skills.loader import Skill
from api.core.skills.patient_memory import PatientMemory
from api.core.skills.workspace import (
    TranscriptEvent,
    Workspace,
    WorkspaceContractError,
)


SKILLS_AGENT_FAKE = os.getenv("SKILLS_AGENT_FAKE", "").strip().lower() in {"1", "true", "yes"}

# Mode toggle: per-run brief override (`_run_mode`) wins over env var, env
# var wins over the deterministic default. "auto" picks "agent" if an
# Anthropic key is present, otherwise falls back to "deterministic". See
# `docs/architecture/MODE-SWITCHING.md` for the full contract.
_VALID_MODES = frozenset({"deterministic", "agent", "auto"})


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
        # (the deterministic loop ignores it; the Claude agent loop uses
        # `escalation_signal`, `finalize_signal`, `final_artifact` here).
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
        1. Per-run brief: `_run_mode` ("deterministic" | "agent" | "auto")
        2. Env var: `SKILLS_RUN_MODE`
        3. Default: "deterministic"

        "auto" promotes to "agent" iff an Anthropic API key is configured;
        otherwise it falls back to "deterministic" so a missing key never
        crashes a run.
        """
        raw = (
            self.brief.get("_run_mode")
            or os.getenv("SKILLS_RUN_MODE", "")
            or "deterministic"
        )
        mode = str(raw).strip().lower() or "deterministic"
        if mode not in _VALID_MODES:
            mode = "deterministic"
        if mode == "auto":
            from api.core.skills.agent_loop import load_config

            mode = "agent" if load_config().has_credentials else "deterministic"
        return mode

    async def _drive_agent_loop(self) -> dict[str, Any]:
        """Drive the agent until it produces a final artifact.

        Dispatches on `resolve_run_mode()`. Both modes write through the
        same workspace contract; the difference is whether decisions are
        made by hardcoded Python (deterministic) or by Claude (agent).
        Tests can inject a scripted loop by setting
        `brief["_agent_overrides"] = {"create_message": fake_fn}`.
        """
        mode = self.resolve_run_mode()
        self._emit("agent_loop_dispatched", mode=mode, skill=self.skill.name)

        if mode == "agent":
            from api.core.skills.agent_loop import (
                AgentLoopAbort,
                drive_claude_agent_loop,
            )

            overrides = self.brief.get("_agent_overrides") or {}
            try:
                return await drive_claude_agent_loop(self, **overrides)
            except AgentLoopAbort as exc:
                # Surface the abort as a deterministic failure rather
                # than a 500. Caller's run() converts this into a
                # `failed` RunResult.
                raise WorkspaceContractError(f"agent loop aborted: {exc}") from exc

        # Deterministic mode — per-skill hardcoded walks.
        if self.skill.name == "trial-matching":
            return await _trial_matching_deterministic_loop(self)
        raise WorkspaceContractError(
            f"no deterministic loop registered for skill '{self.skill.name}'"
        )


# ── Trial-matching deterministic loop ──────────────────────────────────────


async def _trial_matching_deterministic_loop(runner: SkillRunner) -> dict[str, Any]:
    """A scripted Phase-0..5 walk that uses the workspace primitives directly.

    This is the "do the work" path the skill body describes. It is the same
    set of tool calls a real agent would issue, made directly from Python so
    we can exercise the workspace contract end-to-end without an LLM in the
    loop. Replace with real `claude-agent-sdk.query()` driven loop in
    commit 4; the workspace primitives below stay unchanged.
    """
    ws = runner.workspace
    brief = runner.brief
    transport = brief.get("_test_ctgov_transport")  # tests may inject

    # Phase 0 — verify
    anchors: list[dict[str, Any]] = brief.get("anchors") or []
    if not anchors:
        ws.escalate(
            condition="no_anchor_condition",
            prompt=(
                "I cannot find an active anchor condition with a recognized "
                "body-system category. Confirm the patient should still be "
                "searched, or provide a target condition."
            ),
            context={"phase": 0},
        )
        return {}
    runner._emit("phase_complete", phase=0, anchors=len(anchors))

    # Phase 1 — search
    candidates: dict[str, dict[str, Any]] = {}
    for anchor in anchors:
        condition_text = anchor.get("display") or anchor.get("text") or ""
        if not condition_text:
            continue
        try:
            results = await ctgov.search(
                condition=condition_text,
                status=brief.get("status") or ["RECRUITING"],
                age_band=brief.get("age_band"),
                sex=brief.get("sex"),
                page_size=brief.get("page_size", 10),
                transport=transport,
            )
        except Exception as exc:  # noqa: BLE001
            ws.escalate(
                condition="ad_hoc:ctgov_unavailable",
                prompt=(
                    f"ClinicalTrials.gov returned an error for anchor "
                    f"'{condition_text}': {exc!r}. Retry, skip this anchor, or stop?"
                ),
                context={"phase": 1, "anchor": anchor, "error": repr(exc)},
            )
            return {}
        for summary in results:
            candidates.setdefault(summary.nct_id, {"summary": summary, "anchors": []})
            candidates[summary.nct_id]["anchors"].append(anchor)
    runner._emit("phase_complete", phase=1, candidate_count=len(candidates))

    if not candidates:
        ws.escalate(
            condition="all_fit_scores_below_threshold",
            prompt="No trials returned for any anchor. Broaden anchors or stop?",
            context={"phase": 1},
        )
        return {}

    # Phase 2/3 — parse + score
    trials_payload: list[dict[str, Any]] = []
    for nct_id, payload in candidates.items():
        summary: ctgov.TrialSummary = payload["summary"]
        try:
            record = await ctgov.get_record(nct_id, transport=transport)
        except Exception as exc:  # noqa: BLE001
            runner._emit("trial_skipped", nct_id=nct_id, reason=repr(exc))
            continue

        if not record.inclusion_lines and not record.exclusion_lines:
            ws.escalate(
                condition="inclusion_criteria_unparseable",
                prompt=(
                    f"Trial {nct_id} has eligibility text I cannot reliably "
                    f"parse. Skip this trial, include it as needs-verification, or stop?"
                ),
                context={"phase": 2, "nct_id": nct_id},
            )
            return {}

        # Without an LLM in the loop, we cannot classify each criterion against
        # the chart. We mark every inclusion line as `needs-verification` so
        # the artifact is honest about its confidence — and the runner adds a
        # T4 citation to make the agent_inference explicit.
        verification_lines = list(record.inclusion_lines)
        anchor = payload["anchors"][0]
        anchor_resource = anchor.get("resource_id") or anchor.get("display") or "anchor"

        anchor_cite = ws.cite(
            claim=f"Active condition '{anchor.get('display') or anchor_resource}'",
            source_kind="fhir_resource",
            source_ref=str(anchor_resource),
            evidence_tier="T1",
        )
        trial_cite = ws.cite(
            claim=f"Eligibility criteria for {nct_id} retrieved from ClinicalTrials.gov",
            source_kind="external_url",
            source_ref=f"https://clinicaltrials.gov/study/{nct_id}",
            evidence_tier="T2",
        )

        # Deterministic placeholder fit score — the real agent will compute
        # this from per-criterion classification. We keep the artifact valid
        # by emitting a low-confidence T3 score and a clear gap list.
        fit_score = max(40, 60 - 2 * len(verification_lines))
        fit_score = min(fit_score, 95)

        section_md = (
            f"**{record.title}** · status `{record.status}` · "
            f"phases {', '.join(record.phases) if record.phases else 'n/a'}\n\n"
            f"_Anchored on:_ {anchor.get('display') or anchor_resource} "
            f"[cite:{anchor_cite}]\n\n"
            f"_Source:_ ClinicalTrials.gov [cite:{trial_cite}]\n\n"
            f"**Fit score:** {fit_score} / 100 _(deterministic placeholder; "
            f"real per-criterion scoring lands with the agent loop)_\n\n"
            f"**Inclusion lines flagged for verification ({len(verification_lines)}):**\n\n"
            + "\n".join(f"- {line}" for line in verification_lines[:6])
            + ("\n- … (truncated)\n" if len(verification_lines) > 6 else "\n")
        )

        ws.write(
            section=nct_id,
            content=section_md,
            citation_ids=[anchor_cite, trial_cite],
            anchor="TRIAL_SECTIONS",
        )

        trials_payload.append(
            {
                "nct_id": nct_id,
                "title": record.title,
                "sponsor": record.sponsor or "",
                "phase": record.phases[0] if record.phases else "",
                "status": record.status,
                "fit_score": fit_score,
                "evidence_tier": "T3",
                "anchor_condition_id": str(anchor_resource),
                "supporting_facts": [
                    {
                        "claim": f"Active condition: {anchor.get('display') or anchor_resource}",
                        "source_kind": "fhir_resource",
                        "source_ref": str(anchor_resource),
                        "evidence_tier": "T1",
                    }
                ],
                "gaps": list(verification_lines)[:10],
                "locations": [
                    {
                        "facility": (loc.get("facility") or "")[:200],
                        "city": loc.get("city"),
                        "state": loc.get("state"),
                        "country": loc.get("country"),
                    }
                    for loc in record.locations[:5]
                    if isinstance(loc, dict)
                ],
                "excluded": False,
                "escalation_triggered": False,
            }
        )

    runner._emit("phase_complete", phase=3, surviving=len(trials_payload))

    # Phase 4 — write summary section
    summary_section = (
        f"Total trials reviewed: {len(candidates)}. "
        f"Surviving the fit threshold: {len(trials_payload)}. "
        f"Excluded: {len(candidates) - len(trials_payload)}. "
        "_This run used the deterministic Phase-1 placeholder loop; per-criterion "
        "scoring lands with the agent integration. Citations are real and resolve._"
    )
    ws.write(
        section="run-summary",
        content=summary_section,
        anchor="WORKSPACE_BODY",
    )

    return {
        "run_id": ws.run_id,
        "skill_version": runner.skill.manifest.version,
        "patient_id": ws.patient_id,
        "summary": {
            "trials_reviewed": len(candidates),
            "trials_surviving": len(trials_payload),
            "trials_excluded": len(candidates) - len(trials_payload),
            "confidence_note": (
                "Deterministic placeholder loop — fit scores are heuristic and "
                "all inclusion criteria are flagged for clinician verification."
            ),
        },
        "trials": trials_payload,
        "escalations": [
            {
                "condition": e.condition,
                "prompt": e.prompt,
                "context": e.context,
                "resolved": e.resolved,
                "resolution_choice": e.resolution_choice,
                "resolution_notes": e.resolution_notes,
                "resolved_at": e.resolved_at or "",
            }
            for e in ws._escalations
        ],
    }
