"""Claude-driven agent loop — Layer 2 implementation.

Per `docs/architecture/skill-runtime/SKILL-AGENT-WORKSPACE.md` §6.0, the runtime is
layered: universal substrate (Layer 1), default agent loop (Layer 2),
per-skill SKILL.md (Layer 3). This module is the Layer-2 implementation
that wires Claude into the loop.

A run executes against a stable tool surface:
- `workspace_write`, `workspace_cite`, `workspace_escalate` — Layer-1
  workspace primitives
- `submit_final_artifact` — explicit end-of-run signal carrying the
  validated output
- `clinicaltrials_search`, `clinicaltrials_get_record` — domain tools
  for the trial-matching skill

Tools are filtered against `skill.manifest.required_tools` so a skill
sees only what it declared. This module runs the production agent path;
tests can inject a fake `create_message` callable, but product runs do
not fall back to a scripted clinical workflow.

The implementation uses the bare `anthropic` SDK (already in deps) for
direct control over the message loop, tool dispatch, and event emission.
For tests, callers can inject a `create_message` callable that yields
scripted responses without making real API calls.
"""

from __future__ import annotations

import json
import os
from time import perf_counter
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from api.core.loader import load_active_published_run
from api.core.provider_assistant import get_relevant_provider_evidence
from api.core.skills import clinicaltrials_gov as ctgov
from api.core.skills.trial_pursuits import TrialPursuitStore
from api.core.sof_tools import (
    SqlRunResult,
    build_tool_description as _sof_build_tool_description,
    run_sql as _sof_run_sql,
    tool_result_payload as _sof_tool_result_payload,
)

if TYPE_CHECKING:
    from api.core.skills.runner import SkillRunner


# ── Configuration ──────────────────────────────────────────────────────────


@dataclass
class AgentConfig:
    """Runtime configuration for the agent loop.

    Tunable via `SKILLS_AGENT_MODEL`, `SKILLS_AGENT_MAX_TURNS`,
    `SKILLS_AGENT_MAX_TOKENS`. Defaults are conservative — a run is a
    short bounded conversation, not an open-ended chat.
    """

    model: str
    max_turns: int
    max_tokens_per_turn: int
    api_key: str | None

    @property
    def has_credentials(self) -> bool:
        if not self.api_key:
            return False
        return "YOUR_KEY_HERE" not in self.api_key


def load_config() -> AgentConfig:
    return AgentConfig(
        model=os.getenv("SKILLS_AGENT_MODEL", "claude-sonnet-4-6").strip()
        or "claude-sonnet-4-6",
        max_turns=_int_env("SKILLS_AGENT_MAX_TURNS", 30, minimum=1, maximum=100),
        max_tokens_per_turn=_int_env(
            "SKILLS_AGENT_MAX_TOKENS", 4096, minimum=256, maximum=64000
        ),
        api_key=(os.getenv("ANTHROPIC_API_KEY") or "").strip() or None,
    )


def _int_env(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    return max(minimum, min(value, maximum))


# ── Tool registry ──────────────────────────────────────────────────────────


@dataclass
class ToolSpec:
    """Bridge between the skill manifest's tool aliases and the agent API.

    `name` is what Claude sees and calls.
    `skill_alias` is what the skill's `required_tools:` frontmatter
    declares (e.g., `workspace.write`).
    `handler` is the async callable that dispatches the tool against the
    runner's workspace and patient context.
    """

    name: str
    skill_alias: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[[dict[str, Any], "SkillRunner"], Awaitable[str]]


# ── Tool handlers ──────────────────────────────────────────────────────────


async def _tool_workspace_write(args: dict[str, Any], runner: "SkillRunner") -> str:
    runner.workspace.write(
        section=args["section"],
        content=args["content"],
        citation_ids=list(args.get("citation_ids") or []),
        anchor=args.get("anchor"),
    )
    return f"OK — section '{args['section']}' written."


async def _tool_workspace_cite(args: dict[str, Any], runner: "SkillRunner") -> str:
    citation_id = runner.workspace.cite(
        claim=args["claim"],
        source_kind=args["source_kind"],
        source_ref=args.get("source_ref"),
        evidence_tier=args["evidence_tier"],
    )
    return citation_id


async def _tool_workspace_escalate(args: dict[str, Any], runner: "SkillRunner") -> str:
    runner.workspace.escalate(
        condition=args["condition"],
        prompt=args["prompt"],
        context=args.get("context") or {},
    )
    # The runner checks this flag after every agent turn to break the loop
    # cleanly; the prompt also tells the model to end its turn here.
    runner.agent_state["escalation_signal"] = True
    return (
        "ESCALATION REGISTERED. The run is now PAUSED awaiting a "
        "clinician decision. End your turn now — do not call any "
        "further tools. The run will resume after the gate is resolved."
    )


async def _tool_clinicaltrials_search(
    args: dict[str, Any], runner: "SkillRunner"
) -> str:
    transport = runner.brief.get("_test_ctgov_transport")
    results = await ctgov.search(
        condition=args["condition"],
        status=args.get("status"),
        age_band=args.get("age_band"),
        sex=args.get("sex"),
        page_size=int(args.get("page_size") or 10),
        transport=transport,
    )
    return json.dumps([r.to_dict() for r in results], default=str)


async def _tool_clinicaltrials_get_record(
    args: dict[str, Any], runner: "SkillRunner"
) -> str:
    transport = runner.brief.get("_test_ctgov_transport")
    record = await ctgov.get_record(args["nct_id"], transport=transport)
    return json.dumps(record.to_dict(), default=str)


async def _tool_submit_final_artifact(
    args: dict[str, Any], runner: "SkillRunner"
) -> str:
    output = args.get("output")
    if not isinstance(output, dict):
        return (
            "ERROR: submit_final_artifact requires an `output` object "
            "conforming to the skill's output_schema."
        )
    runner.workspace.sync_canvas_from_output(output)
    runner.agent_state["final_artifact"] = output
    runner.agent_state["finalize_signal"] = True
    return "Artifact captured. End your turn now."


async def _tool_workspace_canvas_upsert(
    args: dict[str, Any], runner: "SkillRunner"
) -> str:
    node = runner.workspace.upsert_canvas_node(
        node_id=args.get("node_id"),
        kind=args["kind"],
        title=args["title"],
        status=args.get("status") or "active",
        summary=args.get("summary") or "",
        data=args.get("data") or {},
        selected=args.get("selected"),
    )
    return json.dumps(node.__dict__, default=str)


async def _tool_trial_pursuit_upsert(
    args: dict[str, Any], runner: "SkillRunner"
) -> str:
    store = TrialPursuitStore(runner.workspace.patient_id)
    payload = dict(args)
    payload.setdefault("created_from_run_id", runner.workspace.run_id)
    pursuit = store.upsert(payload, actor="agent")
    return json.dumps(
        {
            "pursuit_id": pursuit.pursuit_id,
            "nct_id": pursuit.nct_id,
            "status": pursuit.status,
            "next_step": pursuit.next_step,
            "tasks": [task.__dict__ for task in pursuit.tasks],
        },
        default=str,
    )


async def _tool_trial_pursuit_add_event(
    args: dict[str, Any], runner: "SkillRunner"
) -> str:
    store = TrialPursuitStore(runner.workspace.patient_id)
    pursuit = store.add_event(
        str(args["pursuit_id"]),
        kind=str(args["kind"]),
        note=str(args["note"]),
        actor="agent",
        data_payload=dict(args.get("data") or {}),
    )
    return json.dumps(
        {
            "pursuit_id": pursuit.pursuit_id,
            "nct_id": pursuit.nct_id,
            "status": pursuit.status,
            "events": [event.__dict__ for event in pursuit.events[-3:]],
        },
        default=str,
    )


async def _tool_trial_pursuit_add_task(
    args: dict[str, Any], runner: "SkillRunner"
) -> str:
    store = TrialPursuitStore(runner.workspace.patient_id)
    pursuit = store.add_task(
        str(args["pursuit_id"]),
        title=str(args["title"]),
        due_at=args.get("due_at"),
        actor="agent",
    )
    return json.dumps(
        {
            "pursuit_id": pursuit.pursuit_id,
            "nct_id": pursuit.nct_id,
            "status": pursuit.status,
            "tasks": [task.__dict__ for task in pursuit.tasks],
        },
        default=str,
    )


async def _tool_get_patient_snapshot(
    args: dict[str, Any], runner: "SkillRunner"
) -> str:
    max_facts = _bounded_int(args.get("max_facts"), default=10, minimum=3, maximum=12)
    snapshot = get_relevant_provider_evidence(
        patient_id=runner.workspace.patient_id,
        query=(
            "Summarize the current trial-matching context: active conditions, "
            "major safety signals, demographics relevant to eligibility, and "
            "chart facts likely to affect inclusion or exclusion criteria."
        ),
        history=None,
        max_facts=max_facts,
        max_citations=8,
    )
    return json.dumps(snapshot, default=str)


async def _tool_query_chart_evidence(
    args: dict[str, Any], runner: "SkillRunner"
) -> str:
    query = str(args.get("query") or "").strip()
    if not query:
        return json.dumps({"error": "query is required"}, default=str)
    max_facts = _bounded_int(args.get("max_facts"), default=8, minimum=3, maximum=12)
    evidence = get_relevant_provider_evidence(
        patient_id=runner.workspace.patient_id,
        query=query,
        history=None,
        max_facts=max_facts,
        max_citations=8,
    )
    return json.dumps(evidence, default=str)


async def _tool_run_sql(args: dict[str, Any], runner: "SkillRunner") -> str:
    query = str(args.get("query") or "").strip()
    if not query:
        return json.dumps({"error": "query is required"}, default=str)
    limit = _bounded_int(args.get("limit"), default=50, minimum=1, maximum=500)
    result = _run_sql_for_patient_scope(runner.workspace.patient_id, query, limit)
    payload = _sof_tool_result_payload(result)
    content = payload.get("content") or []
    if content and isinstance(content[0], dict):
        text = content[0].get("text")
        if isinstance(text, str):
            return text
    return json.dumps(result.to_dict(), default=str)


def _run_sql_for_patient_scope(
    patient_id: str, query_text: str, limit: int
) -> SqlRunResult:
    if load_active_published_run(patient_id) is not None:
        return SqlRunResult(
            columns=[],
            rows=[],
            row_count=0,
            truncated=False,
            query=query_text,
            error=(
                "global SQL-on-FHIR is disabled because this patient has an "
                "active published chart snapshot; use chart evidence tools "
                "for the active snapshot."
            ),
        )
    return _sof_run_sql(query_text, limit=limit)


# Skill alias → ToolSpec.
TOOL_REGISTRY: dict[str, ToolSpec] = {
    "get_patient_snapshot": ToolSpec(
        name="get_patient_snapshot",
        skill_alias="get_patient_snapshot",
        description=(
            "Return a high-signal chart snapshot for the selected patient, "
            "focused on active conditions, safety signals, and facts relevant "
            "to trial eligibility. Use this before searching registries."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "max_facts": {"type": "integer", "minimum": 3, "maximum": 12},
            },
        },
        handler=_tool_get_patient_snapshot,
    ),
    "query_chart_evidence": ToolSpec(
        name="query_chart_evidence",
        skill_alias="query_chart_evidence",
        description=(
            "Retrieve chart-grounded evidence and citations for a specific "
            "clinical question or trial eligibility criterion."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_facts": {"type": "integer", "minimum": 3, "maximum": 12},
            },
            "required": ["query"],
        },
        handler=_tool_query_chart_evidence,
    ),
    "run_sql": ToolSpec(
        name="run_sql",
        skill_alias="run_sql",
        description=_sof_build_tool_description(),
        input_schema={
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "limit": {"type": "integer", "minimum": 1, "maximum": 500},
            },
            "required": ["query"],
        },
        handler=_tool_run_sql,
    ),
    "workspace.write": ToolSpec(
        name="workspace_write",
        skill_alias="workspace.write",
        description=(
            "Append-or-replace a named section of the workspace markdown. "
            "Citation references like [cite:c_NNNN] embedded in `content` "
            "must resolve to citations registered via workspace_cite. "
            "`anchor` (optional) targets a named anchor block in the "
            "workspace template — use TRIAL_SECTIONS for per-trial sections."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "section": {"type": "string"},
                "content": {"type": "string"},
                "citation_ids": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "anchor": {"type": "string"},
            },
            "required": ["section", "content"],
        },
        handler=_tool_workspace_write,
    ),
    "workspace.cite": ToolSpec(
        name="workspace_cite",
        skill_alias="workspace.cite",
        description=(
            "Register a citation. Returns the citation id (c_NNNN) you "
            "can embed as [cite:c_NNNN] in workspace_write content. "
            "source_kind ∈ {fhir_resource, external_url, clinician_input, "
            "agent_inference}. evidence_tier ∈ {T1, T2, T3, T4}. "
            "source_ref is required for fhir_resource and external_url."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "claim": {"type": "string"},
                "source_kind": {
                    "type": "string",
                    "enum": [
                        "fhir_resource",
                        "external_url",
                        "clinician_input",
                        "agent_inference",
                    ],
                },
                "source_ref": {"type": "string"},
                "evidence_tier": {
                    "type": "string",
                    "enum": ["T1", "T2", "T3", "T4"],
                },
            },
            "required": ["claim", "source_kind", "evidence_tier"],
        },
        handler=_tool_workspace_cite,
    ),
    "workspace.escalate": ToolSpec(
        name="workspace_escalate",
        skill_alias="workspace.escalate",
        description=(
            "Pause the run and surface a question to the clinician. "
            "`condition` must match a trigger declared in the skill's "
            "frontmatter (or be prefixed `ad_hoc:` for unanticipated cases). "
            "After calling this, end your turn — do not call further tools."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "condition": {"type": "string"},
                "prompt": {"type": "string"},
                "context": {"type": "object"},
            },
            "required": ["condition", "prompt"],
        },
        handler=_tool_workspace_escalate,
    ),
    "workspace.canvas.upsert": ToolSpec(
        name="workspace_canvas_upsert",
        skill_alias="workspace.canvas.upsert",
        description=(
            "Create or update one typed right-canvas object. Use this for "
            "search criteria, chart anchors, candidate trials, selected "
            "trials, packet tasks, and other UI objects the clinician can "
            "click. `node_id` should be stable, e.g. trial:NCT01234567."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "node_id": {"type": "string"},
                "kind": {
                    "type": "string",
                    "enum": [
                        "criteria",
                        "anchor",
                        "candidate_trial",
                        "selected_trial",
                        "packet_task",
                        "summary",
                        "artifact",
                    ],
                },
                "title": {"type": "string"},
                "status": {"type": "string"},
                "summary": {"type": "string"},
                "data": {"type": "object"},
                "selected": {"type": "boolean"},
            },
            "required": ["kind", "title"],
        },
        handler=_tool_workspace_canvas_upsert,
    ),
    "trial_pursuit.upsert": ToolSpec(
        name="trial_pursuit_upsert",
        skill_alias="trial_pursuit.upsert",
        description=(
            "Create or update a durable patient-level trial pursuit. Use this "
            "when a candidate trial should become a longitudinal mini-project "
            "for review, packet preparation, outreach, submission, or follow-up."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "nct_id": {"type": "string", "pattern": r"^NCT\d{8}$"},
                "title": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": [
                        "interested",
                        "reviewing",
                        "packet",
                        "contacted",
                        "submitted",
                        "follow_up",
                        "closed",
                    ],
                },
                "sponsor": {"type": "string"},
                "trial_status": {"type": "string"},
                "source_url": {"type": "string"},
                "source_kind": {"type": "string"},
                "source_updated_at": {"type": "string"},
                "fit_score": {"type": "number"},
                "next_step": {"type": "string"},
                "notes": {"type": "string"},
                "tags": {"type": "array", "items": {"type": "string"}},
                "created_from_canvas_node_id": {"type": "string"},
                "evidence_snapshot": {"type": "object"},
            },
            "required": ["nct_id", "title"],
        },
        handler=_tool_trial_pursuit_upsert,
    ),
    "trial_pursuit.add_event": ToolSpec(
        name="trial_pursuit_add_event",
        skill_alias="trial_pursuit.add_event",
        description=(
            "Append an auditable event to a durable trial pursuit, such as "
            "eligibility reviewed, coordinator contacted, submission sent, "
            "follow-up due, or closed with reason."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pursuit_id": {"type": "string"},
                "kind": {"type": "string"},
                "note": {"type": "string"},
                "data": {"type": "object"},
            },
            "required": ["pursuit_id", "kind", "note"],
        },
        handler=_tool_trial_pursuit_add_event,
    ),
    "trial_pursuit.add_task": ToolSpec(
        name="trial_pursuit_add_task",
        skill_alias="trial_pursuit.add_task",
        description=(
            "Add a task to a durable trial pursuit, for example collect labs, "
            "call coordinator, prepare packet, request imaging report, or "
            "check follow-up status."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "pursuit_id": {"type": "string"},
                "title": {"type": "string"},
                "due_at": {"type": "string"},
            },
            "required": ["pursuit_id", "title"],
        },
        handler=_tool_trial_pursuit_add_task,
    ),
    "submit_final_artifact": ToolSpec(
        name="submit_final_artifact",
        skill_alias="submit_final_artifact",
        description=(
            "Submit the final structured artifact. The runtime validates "
            "it against the skill's output_schema. Call this exactly once "
            "at the end of the run, then end your turn."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "output": {"type": "object"},
            },
            "required": ["output"],
        },
        handler=_tool_submit_final_artifact,
    ),
    "mcp.clinicaltrials_gov.search": ToolSpec(
        name="clinicaltrials_search",
        skill_alias="mcp.clinicaltrials_gov.search",
        description=(
            "Search ClinicalTrials.gov v2 by condition. Returns up to "
            "`page_size` summaries (nct_id, title, status, conditions, "
            "phases, sponsor, eligibility band, locations_count)."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "condition": {"type": "string"},
                "status": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "e.g., RECRUITING, ENROLLING_BY_INVITATION",
                },
                "age_band": {
                    "type": "object",
                    "properties": {
                        "min": {"type": "integer"},
                        "max": {"type": "integer"},
                    },
                },
                "sex": {"type": "string", "enum": ["MALE", "FEMALE"]},
                "page_size": {"type": "integer", "minimum": 1, "maximum": 100},
            },
            "required": ["condition"],
        },
        handler=_tool_clinicaltrials_search,
    ),
    "mcp.clinicaltrials_gov.get_record": ToolSpec(
        name="clinicaltrials_get_record",
        skill_alias="mcp.clinicaltrials_gov.get_record",
        description=(
            "Fetch the full record for one trial by NCT id. Returns "
            "title, status, full eligibility text, parsed inclusion/"
            "exclusion lines, locations, central contacts."
        ),
        input_schema={
            "type": "object",
            "properties": {
                "nct_id": {
                    "type": "string",
                    "pattern": r"^NCT\d{8}$",
                },
            },
            "required": ["nct_id"],
        },
        handler=_tool_clinicaltrials_get_record,
    ),
}


def _resolve_tools_for_skill(required_aliases: list[str]) -> list[ToolSpec]:
    """Return ToolSpecs for the aliases the skill declared.

    Always includes `submit_final_artifact` even if the skill didn't list
    it — the agent has no way to end the run without it. Aliases the
    runtime doesn't know about are silently dropped (the loader's
    contract validation is the place to flag missing tools, not here).
    """
    out: list[ToolSpec] = []
    seen: set[str] = set()
    for alias in list(required_aliases) + ["submit_final_artifact"]:
        spec = TOOL_REGISTRY.get(alias)
        if spec is None or spec.skill_alias in seen:
            continue
        out.append(spec)
        seen.add(spec.skill_alias)
    return out


def _tool_specs_for_anthropic(specs: list[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {
            "name": spec.name,
            "description": spec.description,
            "input_schema": spec.input_schema,
        }
        for spec in specs
    ]


# ── System prompt ──────────────────────────────────────────────────────────


_AGENT_HEADER = """\
You are running inside the Skill+Agent+Workspace runtime. The skill body
below describes WHAT you must accomplish for this run. Your tools mediate
HOW you record progress.

Hard rules — the runtime enforces these:
1. Every fact in the workspace artifact must carry a citation, registered
   via `workspace_cite`. Embed citations in workspace_write content as
   [cite:c_NNNN] and pass the same ids in `citation_ids`. Uncited claims
   are rejected.
2. When you escalate, end your turn immediately. The run pauses until the
   clinician resolves the gate.
3. End the run by calling `submit_final_artifact` with the structured
   output, then end your turn. The output must conform to the
   skill's output_schema (the runtime validates).
4. Keep the side canvas useful as you work. Upsert typed canvas nodes for
   criteria, anchors, candidate trials, selected trials, and packet tasks
   whenever you have structured state the clinician can act on.
5. When a trial becomes something the clinician may pursue beyond this run,
   create or update a durable trial pursuit. Use pursuit tasks/events for
   packet preparation, outreach, submission, and follow-up.

Below: the skill body, then optional patient memory and brief inputs."""


def assemble_system_prompt(
    skill_body: str,
    patient_memory: str,
    brief: dict[str, Any],
    skill_name: str,
    skill_version: str,
) -> str:
    chunks = [_AGENT_HEADER, "", "---", "", f"# Skill: {skill_name} v{skill_version}", "", skill_body.strip()]
    if patient_memory.strip():
        chunks.extend(["", "---", "", patient_memory])
    public_brief = {k: v for k, v in brief.items() if not k.startswith("_")}
    chunks.extend(
        [
            "",
            "---",
            "",
            "# Brief inputs for this run",
            "",
            "```json",
            json.dumps(public_brief, indent=2, sort_keys=True, default=str),
            "```",
        ]
    )
    return "\n".join(chunks)


# ── Loop ──────────────────────────────────────────────────────────────────


CreateMessage = Callable[..., Awaitable[Any]]


class AgentLoopAbort(RuntimeError):
    """Raised when the loop must abort cleanly with a known failure."""


async def drive_claude_agent_loop(
    runner: "SkillRunner",
    *,
    create_message: CreateMessage | None = None,
    config: AgentConfig | None = None,
) -> dict[str, Any]:
    """Drive one run via Claude with tool dispatch.

    `create_message` is the messages.create coroutine. Default uses the
    real `anthropic.AsyncAnthropic`; tests inject a scripted fake.

    Returns the artifact dict captured via `submit_final_artifact`. If
    the run is escalated mid-loop, returns an empty dict — the runner
    sees `workspace.status == "escalated"` and short-circuits before
    finalize.
    """
    cfg = config or load_config()
    if create_message is None:
        create_message = _make_default_create_message(cfg)

    specs = _resolve_tools_for_skill(list(runner.skill.manifest.required_tools))
    tools_payload = _tool_specs_for_anthropic(specs)
    handlers: dict[str, Callable[[dict[str, Any], "SkillRunner"], Awaitable[str]]] = {
        spec.name: spec.handler for spec in specs
    }

    runner.agent_state.setdefault("escalation_signal", False)
    runner.agent_state.setdefault("finalize_signal", False)
    runner.agent_state.setdefault("final_artifact", None)

    system_prompt = assemble_system_prompt(
        skill_body=runner.skill.body,
        patient_memory=runner.patient_memory.session_context(
            requested_packages=list(runner.skill.manifest.context_packages)
        ),
        brief=runner.brief,
        skill_name=runner.skill.name,
        skill_version=runner.skill.manifest.version,
    )

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": (
                "Begin the run. Use the tools to read sources, register "
                "citations, write workspace sections, and submit the final "
                "artifact when done."
            ),
        }
    ]

    runner._emit(
        "agent_run_started",
        model=cfg.model,
        tool_count=len(specs),
        max_turns=cfg.max_turns,
    )

    for turn_index in range(cfg.max_turns):
        pending_messages = runner.workspace.drain_messages()
        if pending_messages:
            messages.append(
                {
                    "role": "user",
                    "content": _steering_messages_to_text(pending_messages),
                }
            )
            runner._emit(
                "agent_steering_messages",
                turn=turn_index,
                message_count=len(pending_messages),
                message_ids=[msg.message_id for msg in pending_messages],
            )

        response = await create_message(
            model=cfg.model,
            max_tokens=cfg.max_tokens_per_turn,
            system=system_prompt,
            tools=tools_payload,
            messages=messages,
        )

        stop_reason = _get_attr(response, "stop_reason")
        content_blocks = _get_attr(response, "content") or []
        text_chunks: list[str] = []
        tool_calls: list[dict[str, Any]] = []

        for block in content_blocks:
            block_type = _get_attr(block, "type")
            if block_type == "text":
                text_chunks.append(_get_attr(block, "text") or "")
            elif block_type == "tool_use":
                tool_calls.append(
                    {
                        "id": _get_attr(block, "id"),
                        "name": _get_attr(block, "name"),
                        "input": _get_attr(block, "input") or {},
                    }
                )

        text = "\n".join(c for c in text_chunks if c.strip())
        if text:
            runner._emit("agent_text", turn=turn_index, text=text)
        runner._emit(
            "agent_turn",
            turn=turn_index,
            stop_reason=stop_reason,
            tool_calls=[{"name": t["name"]} for t in tool_calls],
        )

        if not tool_calls:
            # No tool calls means the agent ended its turn without
            # submitting an artifact and without escalating. That's a
            # protocol violation — surface it.
            if not runner.agent_state["finalize_signal"] and not runner.agent_state[
                "escalation_signal"
            ]:
                raise AgentLoopAbort(
                    "agent ended without calling submit_final_artifact or "
                    "workspace_escalate"
                )
            break

        # Dispatch every tool call sequentially (we don't allow parallel
        # workspace writes — citation ordering matters).
        tool_results: list[dict[str, Any]] = []
        for call in tool_calls:
            handler = handlers.get(call["name"])
            if handler is None:
                runner._emit(
                    "agent_tool_call",
                    turn=turn_index,
                    tool_call_id=call["id"],
                    tool=call["name"],
                    args=_redact_tool_args(call["input"]),
                )
                runner._emit(
                    "agent_tool_error",
                    turn=turn_index,
                    tool_call_id=call["id"],
                    tool=call["name"],
                    duration_ms=0,
                    error=f"tool '{call['name']}' is not available to this skill",
                )
                tool_results.append(
                    _tool_result_block(
                        call["id"],
                        f"ERROR: tool '{call['name']}' is not available to this skill.",
                        is_error=True,
                    )
                )
                continue
            started = perf_counter()
            runner._emit(
                "agent_tool_call",
                turn=turn_index,
                tool_call_id=call["id"],
                tool=call["name"],
                args=_redact_tool_args(call["input"]),
            )
            try:
                result_text = await handler(call["input"], runner)
            except Exception as exc:  # noqa: BLE001
                duration_ms = round((perf_counter() - started) * 1000)
                runner._emit(
                    "agent_tool_error",
                    turn=turn_index,
                    tool_call_id=call["id"],
                    tool=call["name"],
                    duration_ms=duration_ms,
                    error=repr(exc),
                )
                tool_results.append(
                    _tool_result_block(
                        call["id"], f"ERROR: {exc!r}", is_error=True
                    )
                )
                continue
            duration_ms = round((perf_counter() - started) * 1000)
            runner._emit(
                "agent_tool_result",
                turn=turn_index,
                tool_call_id=call["id"],
                tool=call["name"],
                duration_ms=duration_ms,
                result_preview=_preview(result_text),
                result_summary=_summarize_tool_result(call["name"], result_text),
            )
            tool_results.append(_tool_result_block(call["id"], result_text))

        messages.append({"role": "assistant", "content": _to_messages(content_blocks)})
        messages.append({"role": "user", "content": tool_results})

        if runner.agent_state["escalation_signal"]:
            runner._emit("agent_run_paused", reason="escalation")
            return {}
        if runner.agent_state["finalize_signal"]:
            runner._emit("agent_run_finalized", turn=turn_index)
            break
    else:
        raise AgentLoopAbort(
            f"agent did not finish within {cfg.max_turns} turns"
        )

    artifact = runner.agent_state.get("final_artifact")
    if not isinstance(artifact, dict):
        if runner.agent_state.get("escalation_signal"):
            return {}
        raise AgentLoopAbort("agent finalized without producing an artifact dict")
    return artifact


# ── Helpers ───────────────────────────────────────────────────────────────


def _get_attr(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _tool_result_block(
    tool_use_id: str | None, content: str, *, is_error: bool = False
) -> dict[str, Any]:
    block: dict[str, Any] = {
        "type": "tool_result",
        "tool_use_id": tool_use_id or "",
        "content": content,
    }
    if is_error:
        block["is_error"] = True
    return block


def _to_messages(content_blocks: Any) -> list[dict[str, Any]]:
    """Normalize content blocks into a JSON-serializable assistant message
    payload that the next messages.create call can consume verbatim."""
    out: list[dict[str, Any]] = []
    for block in content_blocks or []:
        block_type = _get_attr(block, "type")
        if block_type == "text":
            out.append({"type": "text", "text": _get_attr(block, "text") or ""})
        elif block_type == "tool_use":
            out.append(
                {
                    "type": "tool_use",
                    "id": _get_attr(block, "id") or "",
                    "name": _get_attr(block, "name") or "",
                    "input": _get_attr(block, "input") or {},
                }
            )
    return out


def _preview(text: str, max_chars: int = 160) -> str:
    flat = text.strip().replace("\n", " ")
    if len(flat) <= max_chars:
        return flat
    return flat[: max_chars - 1] + "…"


def _bounded_int(
    raw: Any, *, default: int, minimum: int, maximum: int
) -> int:
    try:
        value = int(raw)
    except (TypeError, ValueError):
        value = default
    return max(minimum, min(value, maximum))


def _redact_tool_args(args: dict[str, Any]) -> dict[str, Any]:
    """Return transcript-safe args: no secrets, no massive payloads."""
    secret_keys = {
        "api_key",
        "authorization",
        "cookie",
        "password",
        "secret",
        "token",
    }

    def scrub(value: Any, *, key: str = "") -> Any:
        if key.lower() in secret_keys:
            return "[redacted]"
        if isinstance(value, dict):
            return {str(k): scrub(v, key=str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [scrub(item) for item in value[:25]]
        if isinstance(value, str):
            if len(value) > 600:
                return value[:597] + "..."
            return value
        return value

    return {str(k): scrub(v, key=str(k)) for k, v in (args or {}).items()}


def _summarize_tool_result(tool_name: str, result_text: str) -> dict[str, Any]:
    try:
        parsed = json.loads(result_text)
    except json.JSONDecodeError:
        return {"type": "text", "chars": len(result_text)}

    if isinstance(parsed, list):
        summary: dict[str, Any] = {"type": "list", "count": len(parsed)}
        if tool_name == "clinicaltrials_search":
            summary["source"] = "clinicaltrials.gov"
            summary["nct_ids"] = [
                item.get("nct_id")
                for item in parsed[:5]
                if isinstance(item, dict) and item.get("nct_id")
            ]
        return summary

    if isinstance(parsed, dict):
        summary = {"type": "object"}
        if "row_count" in parsed:
            summary.update(
                {
                    "row_count": parsed.get("row_count"),
                    "truncated": parsed.get("truncated"),
                    "error": parsed.get("error"),
                }
            )
        if "evidence_lines" in parsed:
            lines = parsed.get("evidence_lines")
            citations = parsed.get("citations")
            summary.update(
                {
                    "evidence_count": len(lines) if isinstance(lines, list) else 0,
                    "citation_count": len(citations)
                    if isinstance(citations, list)
                    else 0,
                    "intent": parsed.get("intent"),
                }
            )
        if "nct_id" in parsed:
            summary.update(
                {
                    "source": "clinicaltrials.gov",
                    "nct_id": parsed.get("nct_id"),
                    "inclusion_count": len(parsed.get("inclusion_lines") or []),
                    "exclusion_count": len(parsed.get("exclusion_lines") or []),
                }
            )
        if "node_id" in parsed:
            summary.update(
                {
                    "node_id": parsed.get("node_id"),
                    "node_kind": parsed.get("kind"),
                    "status": parsed.get("status"),
                }
            )
        if "pursuit_id" in parsed:
            summary.update(
                {
                    "pursuit_id": parsed.get("pursuit_id"),
                    "nct_id": parsed.get("nct_id"),
                    "status": parsed.get("status"),
                }
            )
        if "error" in parsed and len(summary) == 1:
            summary["error"] = parsed.get("error")
        return summary

    return {"type": type(parsed).__name__}


def _steering_messages_to_text(messages: list[Any]) -> str:
    parts = [
        "The clinician/patient added steering messages for this active run. "
        "Incorporate them into the next step. If they conflict with the "
        "brief, ask for clarification with workspace_escalate."
    ]
    for msg in messages:
        canvas_ref = getattr(msg, "canvas_ref", None)
        ref_text = (
            f"\nCanvas reference: {json.dumps(canvas_ref, sort_keys=True)}"
            if canvas_ref
            else ""
        )
        parts.append(
            f"\n[{getattr(msg, 'actor', 'clinician')}:{getattr(msg, 'message_id', '')}] "
            f"{getattr(msg, 'message', '')}{ref_text}"
        )
    return "\n".join(parts)


def _make_default_create_message(cfg: AgentConfig) -> CreateMessage:
    """Build the default messages.create coroutine.

    Imports anthropic lazily so tests can monkeypatch / inject fakes
    without the SDK being importable in the test env.
    """
    from anthropic import AsyncAnthropic

    if not cfg.has_credentials:
        raise AgentLoopAbort(
            "agent mode requires ANTHROPIC_API_KEY; skill runs do not have a "
            "deterministic fallback"
        )
    client = AsyncAnthropic(api_key=cfg.api_key)

    async def _create(**kwargs: Any) -> Any:
        return await client.messages.create(**kwargs)

    return _create
