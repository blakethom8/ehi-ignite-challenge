# Mode Switching — Deterministic vs Claude Agent Loop

> **Status:** Architecture record. Documents the run-mode toggle that
> selects between the deterministic Phase-0..5 loop and the Claude-driven
> agent loop. Both modes write through the same Layer-1 workspace
> contract.
>
> **Companions:** [`SKILL-AGENT-WORKSPACE.md`](SKILL-AGENT-WORKSPACE.md)
> (layered architecture), [`STREAMING-AND-GATEWAY.md`](STREAMING-AND-GATEWAY.md)
> (event broadcast).
>
> **Last updated:** 2026-05-05

---

## 1. Why two modes

The deterministic loop was the right starting point for the Layer-2 walk:
it lets us validate the workspace contract (citations, escalations,
finalize, save destinations) end-to-end without spending tokens, without
needing API keys, and without prompt-engineering iteration polluting the
audit trail. Every test in `test_skills_runtime.py` runs against the
deterministic loop.

The Claude agent loop is the real product. The agent reads the skill
body as its system prompt, calls registered tools to interact with the
workspace and the world (ClinicalTrials.gov, in trial-matching's case),
and produces the same artifact shape. It pays in tokens; it earns in
flexibility for the long-tail trials where a hardcoded Phase-N walk
can't capture the right judgment.

Keeping both means we can:
1. Run the deterministic mode in CI and demos (free, fast, repeatable).
2. Run the agent mode in production (correct by construction for the
   open-ended cases the deterministic loop can't enumerate).
3. Toggle per run for A/B comparison or for cost-conscious flows.
4. Fall back gracefully if API credentials are missing or the SDK is
   misconfigured.

## 2. The toggle, end-to-end

Precedence (highest first):

| Layer | Source | Examples |
|---|---|---|
| **Per-run brief** | `brief["_run_mode"]` | `"deterministic"`, `"agent"`, `"auto"` |
| **System default** | `SKILLS_RUN_MODE` env var | `"deterministic"` (default), `"agent"`, `"auto"` |
| **Hardcoded fallback** | runner constant | `"deterministic"` |

`"auto"` resolves at run time:

- Has `ANTHROPIC_API_KEY` (and not the placeholder) → `"agent"`
- Otherwise → `"deterministic"`

This means you can ship a build with `SKILLS_RUN_MODE=auto` to
production and have the same code path run agent mode where keys are
provisioned and deterministic everywhere else (CI, dev sandboxes, etc.)
without conditional logic in the deployment.

Resolution lives in `runner.resolve_run_mode()` and emits an
`agent_loop_dispatched` event into the transcript so the audit trail
shows which loop drove the run.

## 3. The agent-loop tool surface

The Claude agent has access to a curated set of tools. The skill's
`required_tools:` frontmatter declares which it needs; the runtime adds
`submit_final_artifact` automatically because there's no other way to
end the run.

| Skill alias | Agent-facing name | What it does |
|---|---|---|
| `workspace.write` | `workspace_write` | Append/replace a section of `workspace.md`. Citations in `[cite:c_NNNN]` form must resolve. |
| `workspace.cite` | `workspace_cite` | Register a citation. Returns the `c_NNNN` id the agent embeds in writes. |
| `workspace.escalate` | `workspace_escalate` | Pause the run; surface a question to the clinician. Agent ends its turn after calling. |
| `submit_final_artifact` | `submit_final_artifact` | Submit the structured output. Runtime validates against `output_schema`. |
| `mcp.clinicaltrials_gov.search` | `clinicaltrials_search` | CT.gov v2 search. |
| `mcp.clinicaltrials_gov.get_record` | `clinicaltrials_get_record` | Full trial record + parsed eligibility. |

Tools the skill manifest doesn't list are not registered for that run.
Tools the registry doesn't recognize are silently dropped (loader-level
manifest validation is the right place to catch missing tools, not
runtime).

## 4. The agent loop, control flow

```
┌───────────────────────────────────────────────────────────────┐
│  drive_claude_agent_loop                                       │
│                                                                │
│  1. Resolve tool specs from skill.required_tools               │
│  2. Assemble system prompt:                                    │
│     header + skill body + patient memory + brief               │
│  3. Initial user message: "Begin the run."                     │
│                                                                │
│  for turn in range(max_turns):                                 │
│     response = await create_message(...)                       │
│     # split response into text + tool_use blocks               │
│                                                                │
│     for tc in tool_calls:                                      │
│        result = await dispatch[tc.name](tc.input, runner)      │
│        # handlers may set escalation_signal or finalize_signal │
│                                                                │
│     append assistant + user(tool_results) to messages          │
│                                                                │
│     if escalation_signal: return {} (workspace state=escalated)│
│     if finalize_signal:  break (return captured artifact)      │
│                                                                │
│  else: AgentLoopAbort("max turns exceeded")                    │
└───────────────────────────────────────────────────────────────┘
```

Properties:

- **One-loop, no recursion.** The agent runs in a single sequential
  turn loop. No planner-executor split for V1.
- **Tool errors become tool results, not exceptions.** A
  `WorkspaceContractError` from a handler comes back as `is_error: true`
  on the tool result; the agent can see the error and adjust on its
  next turn instead of crashing the loop.
- **Escalation is the only "stop early" exit other than finalize.** The
  agent calls `workspace_escalate`; the handler sets
  `agent_state["escalation_signal"]`; the loop returns `{}` and the
  runner sees `workspace.status == "escalated"`.
- **Finalize is explicit.** No magic JSON parsing — the agent calls
  `submit_final_artifact(output={...})` and the loop captures the
  artifact via `agent_state["final_artifact"]`.
- **Test seam:** `create_message` is injectable. Tests pass scripted
  responses; production uses `anthropic.AsyncAnthropic.messages.create`
  built lazily so `import anthropic` only happens when actually needed.

## 5. Configuration

| Env var | Default | Notes |
|---|---|---|
| `SKILLS_RUN_MODE` | `deterministic` | Also accepts `agent`, `auto` |
| `SKILLS_AGENT_MODEL` | `claude-sonnet-4-6` | Bare anthropic API model id |
| `SKILLS_AGENT_MAX_TURNS` | `30` | Clamped to `[1, 100]` |
| `SKILLS_AGENT_MAX_TOKENS` | `4096` | Per-turn `max_tokens` limit, clamped to `[256, 64000]` |
| `ANTHROPIC_API_KEY` | (none) | Required for agent mode |

Per-run overrides via the brief:

```python
brief = {
    # Anchors and other public fields...
    "_run_mode": "agent",
    "_agent_overrides": {           # advanced: tests / custom callers only
        "create_message": fake_fn,
        "config": custom_config,
    },
}
```

Underscore-prefixed keys are stripped before persistence — they exist
only on the in-flight brief and never land in `brief.json`.

## 6. Failure modes and recovery

| Trigger | Behavior |
|---|---|
| Agent ends turn without finalize or escalate | `AgentLoopAbort` → run marked `failed` with reason `"agent ended without calling submit_final_artifact"` |
| Max turns exceeded | `AgentLoopAbort` → run marked `failed` with reason `"agent did not finish within N turns"` |
| Unknown tool name | Tool result `is_error: true`; agent retries on next turn |
| Workspace contract violation in a tool | Tool result `is_error: true`; agent retries on next turn |
| API key missing in `agent` mode | `AgentLoopAbort` raised at first `create_message` build → run marked `failed` |
| API key missing in `auto` mode | Falls back to `deterministic` silently; `agent_loop_dispatched` event records `mode=deterministic` |
| Agent calls `submit_final_artifact` with output that fails schema validation | `Workspace.finalize` raises `WorkspaceContractError`; run marked `failed`. Future enhancement: feed schema errors back to the agent for one revision pass. |

## 7. Forward path

| When | What changes |
|---|---|
| **Now** | Deterministic + agent both implemented. `auto` falls back. Tests cover both. |
| **Commit 5+ (planner-executor)** | Skills can declare `agent_topology: planner_executor` in frontmatter. The runner spawns sub-agents per criterion-parsing call. Same workspace contract. |
| **Commit 6+ (token streaming)** | `create_message` switches from `messages.create` to `messages.stream`; per-token deltas published as `agent_text_delta` events through the existing hub. |
| **Phase 2 (W2 sandbox)** | The agent loop runs inside a Docker sandbox; FastAPI relays events through the EventHub via a unix socket. Mode toggle stays the same. |
| **Multi-LLM** | Add a `SKILLS_AGENT_PROVIDER` env var + a provider abstraction. `create_message` becomes a thin shim over Claude / GPT / open-weight. The skill body and tool surface are unchanged. |

## 8. Decision summary

- **Two loops, one workspace contract.** Both modes write through
  `workspace.write/cite/escalate`; both produce schema-validated
  artifacts; both publish through the same EventHub.
- **Deterministic is the default** — free, fast, demoable without an
  API key. CI runs against it.
- **`auto` is the recommended production setting** — promotes to agent
  where credentials exist, deterministic everywhere else, no deploy-time
  conditional logic needed.
- **Per-run override via brief** — for A/B testing or cost-controlled
  flows where some patients run agent and others run deterministic.
- **Agent-loop scope kept tight** — single-turn dispatcher, no
  planner-executor yet, no streaming yet, no multi-provider yet. All
  three are explicit forward-path items with clear seams already in
  place.
