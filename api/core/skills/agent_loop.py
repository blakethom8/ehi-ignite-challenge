"""Claude-driven agent loop — Layer 2 implementation.

Per `docs/architecture/SKILL-AGENT-WORKSPACE.md` §6.0, the runtime is
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
sees only what it declared. The runner caller decides which loop to use
(deterministic vs agent) via `SKILLS_RUN_MODE` or a per-run override —
this module just runs the agent path when invoked.

The implementation uses the bare `anthropic` SDK (already in deps) for
direct control over the message loop, tool dispatch, and event emission.
For tests, callers can inject a `create_message` callable that yields
scripted responses without making real API calls.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any, Awaitable, Callable

from api.core.skills import clinicaltrials_gov as ctgov

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
    runner.agent_state["final_artifact"] = output
    runner.agent_state["finalize_signal"] = True
    return "Artifact captured. End your turn now."


# Skill alias → ToolSpec.
TOOL_REGISTRY: dict[str, ToolSpec] = {
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
                tool_results.append(
                    _tool_result_block(
                        call["id"],
                        f"ERROR: tool '{call['name']}' is not available to this skill.",
                        is_error=True,
                    )
                )
                continue
            try:
                result_text = await handler(call["input"], runner)
            except Exception as exc:  # noqa: BLE001
                runner._emit(
                    "agent_tool_error",
                    tool=call["name"],
                    error=repr(exc),
                )
                tool_results.append(
                    _tool_result_block(
                        call["id"], f"ERROR: {exc!r}", is_error=True
                    )
                )
                continue
            runner._emit(
                "agent_tool_result",
                tool=call["name"],
                result_preview=_preview(result_text),
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


def _make_default_create_message(cfg: AgentConfig) -> CreateMessage:
    """Build the default messages.create coroutine.

    Imports anthropic lazily so tests can monkeypatch / inject fakes
    without the SDK being importable in the test env.
    """
    from anthropic import AsyncAnthropic

    if not cfg.has_credentials:
        raise AgentLoopAbort(
            "agent mode requires ANTHROPIC_API_KEY (or set "
            "SKILLS_RUN_MODE=deterministic to use the deterministic loop)"
        )
    client = AsyncAnthropic(api_key=cfg.api_key)

    async def _create(**kwargs: Any) -> Any:
        return await client.messages.create(**kwargs)

    return _create
