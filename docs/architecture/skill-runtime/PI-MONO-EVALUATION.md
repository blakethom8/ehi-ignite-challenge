# Pi-Mono — Should We Adopt It as Our Harness?

> **Status:** Decision report. Evaluates [`badlogic/pi-mono`](https://github.com/badlogic/pi-mono)
> (the harness that powers OpenClaw) against our current Python/FastAPI
> skill runtime. Recommends a **borrow-not-adopt** posture and lists
> the specific patterns worth lifting.
>
> **Last updated:** 2026-05-05

---

## 1. The question

Pi-mono is a TypeScript monorepo by Mario Zechner that bundles a
multi-provider LLM API, an agent-loop core, a coding-agent CLI, and
TUI/web-UI primitives. It's the substrate behind OpenClaw — the
medical skills library we already reviewed in
[`SKILL-AGENT-WORKSPACE.md`](SKILL-AGENT-WORKSPACE.md) Appendix A.

The question on the table: should we adopt pi-mono as our agent
harness, throwing away (or sidecar-ing) the Python `agent_loop.py` we
just shipped?

Short version:

- **Pi-mono is genuinely well-architected.** The provider abstraction,
  the event-driven loop, the hooks framework, and the steering queue
  are all things we either don't have or have only partially built.
- **It's TypeScript.** Our backend is Python/FastAPI with a meaningful
  domain layer (FHIR parsing, harmonization, canonical chart, SOF SQL
  warehouse, tracing) we are not going to rewrite.
- **Their philosophy explicitly omits two things we treat as
  load-bearing:** MCP (cross-skill tool standard) and sandboxing
  (W2 Docker isolation when we accept community skills or real PHI).
  Adopting pi-mono means inheriting their philosophical position on
  both.

Recommendation: **Option C below — borrow patterns, don't adopt the
runtime.**

## 2. What pi-mono actually contains

| Package | Purpose | Notes |
|---|---|---|
| `@mariozechner/pi-ai` | Unified multi-provider LLM API | 20+ providers (Anthropic, OpenAI, Google, Bedrock, Vertex, GitHub Copilot, Groq, DeepSeek, Mistral, Cerebras, xAI, Cloudflare, OpenAI-compatibles like Ollama / vLLM). Streaming with typed events: `start`, `text_delta`, `toolcall_delta`, `thinking_delta`, `done`. Cost + token tracking. TypeBox tool schemas. Prompt caching by `sessionId`. OAuth for Anthropic / Codex / GitHub Copilot. |
| `@mariozechner/pi-agent-core` | Event-driven agent runtime | `agentLoop()` + `Agent` class. Lifecycle events (`agent_start`, `turn_start`, `tool_executing`, `agent_end`). Tool dispatch with parallel/sequential execution modes. Hooks: `beforeToolCall`, `afterToolCall`, `transformContext`. Steering queue (inject messages mid-run; processed after current turn). Follow-up queue (after agent completion). Custom `streamFn` for proxy/sidecar deployments. |
| `@mariozechner/pi-coding-agent` | Coding-agent CLI (Claude-Code-shaped) | Built-in tools: `read`, `write`, `edit`, `bash`, `grep`, `find`, `ls`. **No** built-in web search / fetch / browser — those are extensions. **No** MCP integration by design. **No** built-in sandboxing — "run in a container or build your own with extensions." |
| `@mariozechner/pi-tui` | Terminal UI library | Differential rendering for the CLI. Not relevant to our React app. |
| `@mariozechner/pi-web-ui` | Web components for chat interfaces | Lit-style web components. Not directly relevant — we have purpose-built React. |

License: MIT throughout. Active project. TypeScript 96.9%; rest is
build/scripts.

## 3. What pi-mono does that our current harness does not

This is the honest list of capability gaps. Ordered by how much they
matter for our roadmap.

| Capability | pi-mono | our harness today | impact for us |
|---|---|---|---|
| Multi-provider abstraction | ✅ 20+ providers behind one API | ❌ bare `anthropic` SDK only | Medium-high. We'll want OpenAI / Google / open-weight eventually for cost mix and per-skill model fit. |
| Token-level streaming with structured deltas | ✅ `text_delta`, `toolcall_delta`, `thinking_delta` events | ⚠️ per-turn events only | Medium. We listed this as deferred in `MODE-SWITCHING.md` §7. |
| Mid-run "steering" queue | ✅ inject messages between turns | ❌ only escalation gates | High for UX. We listed mid-run inline comments as deferred in `SELF-MODIFYING-WORKSPACE.md` §2.5. |
| Hooks framework | ✅ `beforeToolCall` / `afterToolCall` / `transformContext` | ⚠️ ad-hoc; mediation lives inside Workspace methods | Medium. Our mediation is *correct* but less composable than pi-mono's lifecycle hooks. |
| Cost / token tracking per turn | ✅ per `AssistantMessage` with `usage` + `cost.total` USD | ⚠️ tracing.py captures spans separately | Low-medium. Our `tracing.py` already covers this; just less integrated. |
| TypeBox tool schemas with progressive JSON parsing | ✅ partial tool args streamed during generation | ❌ wait for full block | Low. Nice-to-have for UI feel, not load-bearing. |
| OAuth flow for provider creds | ✅ for Anthropic, Codex, GitHub Copilot | ❌ env vars only | Low for clinical app. (Could matter if we ever offer a "bring your own key" model.) |
| Prompt caching across turns | ✅ via `sessionId` | ⚠️ implicit only | Medium. Real cost savings on long runs. |

## 4. What we have that pi-mono does not

Equally honest:

| Capability | our harness | pi-mono |
|---|---|---|
| **The workspace contract** (mediated `write`/`cite`/`escalate`, citation graph, audit trail) | ✅ Layer-1 substrate | ❌ not a runtime concept |
| **Skill manifests** (versioned SKILL.md + frontmatter + output schemas + eval rubrics) | ✅ first-class | ❌ pi has "skills" as CLI-tool READMEs, but no manifest contract / schema validation / promotion gates |
| **Patient memory layer** (cross-run `_memory/pinned.md` + context packages) | ✅ first-class | ❌ pi's session state is just messages |
| **MCP** as the cross-skill data-source standard | ✅ wired into the manifest (e.g., `mcp.clinicaltrials_gov.*`) | ❌ explicitly omitted by design |
| **Mediated workspace canvas** (clinician-readable artifact + structured output JSON) | ✅ workspace.md + output.json | ❌ no canvas concept; agent output is just text |
| **Domain layer** (FHIR parser, canonical chart, harmonization runs, SOF SQL views, condition ranker) | ✅ multi-thousand-line Python | ❌ none — pi is domain-agnostic by design |
| **Save destinations** (run / patient / package — the self-modifying loop) | ✅ first-class | ❌ no equivalent |
| **EventHub fan-out** (multi-subscriber per-run pub/sub for SSE) | ✅ | ⚠️ pi's events are single-stream from the loop |
| **Citation enforcement at write time** | ✅ unforgeable | ❌ would have to be a hook |
| **Schema-validated finalize** | ✅ output.schema.json | ❌ no equivalent |

In other words, pi-mono is a great **agent runtime**. Our harness is
an agent runtime *plus* the clinical-skill substrate the EHI Ignite
product needs. The clinical-skill substrate is the unique thing.

## 5. Three real options

### Option A — Adopt pi-mono as the harness

Rewrite the agent loop in TypeScript on top of pi-agent-core. FastAPI
becomes a thin proxy that delegates "run a turn" to a Node service.
Workspace contract / patient memory / skill manifests get re-implemented
as TypeScript hooks on pi-agent-core.

**Pros**
- Multi-provider, structured streaming, steering, OAuth out of the box.
- Less harness code we maintain long-term.
- Aligns with the OpenClaw ecosystem they target.

**Cons**
- **Throws away the Python agent_loop, runner, worker, workspace,
  patient_memory, skills router, and tests.** ~3,000 lines of code,
  102 tests.
- **Forces a Node sidecar in our deployment.** Today we ship one
  FastAPI container; we'd add a Node container, an IPC channel, and
  the operational surface that comes with both.
- **Loses MCP as a cross-skill standard** (pi explicitly skips it).
  The skill manifest's `required_tools:` field as an MCP-shaped surface
  was a deliberate bet; giving it up is non-trivial.
- **Doesn't solve the actual product problem.** None of the things
  pi-mono is good at are blocking us from shipping Trial Finder. The
  things blocking us are clinical depth, Phase 1 deadline, and getting
  the first agent run into a real clinician's hands.
- **Sunk cost is real.** We just spent six commits building the
  workspace contract precisely the way the doc says we want it.
  Throwing that away would be a *strategic* decision, not a tactical
  one — it'd say "the harness is the differentiator." It isn't. The
  Provenance graph and the workspace contract are.

### Option B — Run pi-mono as a sidecar

Keep the Python runtime. Replace `agent_loop.py`'s `messages.create`
loop with a call to a Node service that hosts pi-agent-core. The Node
service does the LLM provider routing + streaming; our Python code
does the workspace mediation and tool dispatch.

**Pros**
- Get pi-ai's multi-provider abstraction without rewriting the harness.
- Get pi's streaming events + steering queue.
- Preserves all the workspace contract code.

**Cons**
- **Tool dispatch becomes split-brain.** pi-agent-core's tool model
  expects synchronous `execute` callbacks; ours expect the workspace's
  Python primitives. We'd be calling Python tools from TS through a
  socket. Doable but inverts a lot of our ergonomics.
- **Two languages, two test suites, two deploy artifacts.** That's
  the exact operational complexity I just rejected in Option A,
  re-introduced in a smaller form.
- **The hard parts (steering, streaming) we can implement in Python
  for less code than the sidecar wiring requires.**

This is the worst of both worlds for our scale. It might be right
later if we want to use pi-ai purely as a model gateway (per
[`STREAMING-AND-GATEWAY.md`](STREAMING-AND-GATEWAY.md) §3 Option C),
but that's not the same as adopting their agent loop.

### Option C — Borrow patterns into our Python harness ✅ recommended

Treat pi-mono as a **design reference**, not a runtime. Lift the
specific patterns that solve our gaps; keep the Python implementation.

Concrete borrows, in priority order:

1. **Event shape.** Adopt pi-ai's structured streaming events
   (`text_delta`, `toolcall_delta`, `thinking_delta`) as the
   transport between the Claude SDK and our EventHub. Already a
   natural fit — the EventHub is provider-agnostic.
2. **Steering queue.** Add `pending_clinician_messages` to the
   runner; the loop drains it between turns and prepends to the next
   `messages.create`. This is the deferred mid-run-comments item from
   `SELF-MODIFYING-WORKSPACE.md`. Roughly 40 lines + a POST endpoint.
3. **Hooks framework.** Lift `beforeToolCall` / `afterToolCall` from
   pi-agent-core. Today our tool dispatch is hardcoded; a hook
   framework gives us per-skill tool gating + observability without
   touching the loop.
4. **Provider abstraction (lighter version).** A `ModelProvider`
   protocol with `claude` as the only implementation today, but the
   shape ready for `openai` / `bedrock` / `local-vllm` later. We do
   *not* need 20+ providers on day one; we need the abstraction.
5. **Cost / token tracking on the run object.** Pi-mono surfaces this
   per `AssistantMessage`; we should attach `usage` + `cost_usd` to
   each `agent_turn` event. `tracing.py` already captures it; the
   wiring is "publish through the hub too."
6. **Prompt caching via session id.** Anthropic supports it; pi-ai
   exposes it via `sessionId`. We can pass our `run_id` as the
   session id directly.

**Pros**
- Solves the real gaps without rewriting anything.
- Stays in one language.
- Preserves the workspace contract, the citation graph, MCP, and
  every domain primitive.
- Each borrow is a small, reviewable commit (probably 4 commits over
  ~3 days).

**Cons**
- We maintain the harness. Pi-mono is more code we don't have to
  write — adopting it would be a bet that they keep maintaining it.
  But our harness is small (~1.5k lines including tests) and the
  surface that matters is the workspace contract, not the loop.
- We don't get OAuth, 20+ providers, or the TUI for free. None of
  those are blocking us.

### Option D — Do nothing differently

Acknowledge pi-mono as inspiration, ship the planned commits in
[`MODE-SWITCHING.md`](MODE-SWITCHING.md) §7 as written, leave the
gaps until they hurt.

This is fine and would also work. Option C is just Option D with a
small set of explicit borrows that close the most felt gaps faster.

## 6. The recommendation

**Take Option C.** Specifically, the next four commits should be
(in order):

1. **Event shape upgrade.** Switch agent_loop.py from `messages.create`
   to `messages.stream`. Emit `agent_text_delta` / `agent_tool_call_delta`
   / `agent_thinking_delta` events through the EventHub. Frontend
   shows the agent's prose materialize in real time. This is the
   single most felt UX improvement.
2. **Steering queue + mid-run messages endpoint.** Closes the chat-
   alongside-workspace loop you flagged earlier. Small.
3. **Hook framework.** `beforeToolCall` / `afterToolCall` /
   `transformContext` lifted into the Workspace + Runner. Lets us
   add tool-call rate limits, redaction, and per-tenant policy
   without touching the loop body.
4. **Provider protocol shim.** `ModelProvider` protocol; default
   `AnthropicModelProvider`. Sets up the seam for OpenAI / Bedrock /
   local-vllm later. Doesn't block on actually adding any of those.

After those four, we're in the same architectural position pi-mono
puts you in *for the runtime*, while keeping our domain layer intact.

The deeper bet — that the differentiator is the **workspace contract
+ citation graph + Provenance lineage** rather than the agent loop —
is exactly what `ATLAS-DATA-MODEL.md` Decision 5 already says. Our
moat is data lineage. Adopting pi-mono wouldn't accelerate that; it
would distract from it.

## 7. What changes if the answer is actually Option A

If you decide the harness *is* the differentiator (e.g., we want to
ship to the OpenClaw ecosystem, or you want to merge upstream into
pi-mono itself, or the JS/TS ecosystem move makes operational sense
for other reasons), the migration shape is:

- Phase 1: stand up pi-agent-core + workspace-contract hooks in TS
  in parallel. Same skills, same workspace dirs on disk, dual-write.
- Phase 2: switch the FastAPI router's run-execution path from the
  Python worker pool to the Node sidecar; keep all reads (workspace,
  transcript, output, memory) in Python.
- Phase 3: retire the Python `agent_loop.py` + `runner.py` + `worker.py`.
  Keep `workspace.py`, `patient_memory.py`, `event_hub.py`, the
  router, and the entire domain layer.
- Phase 4: optionally migrate the rest of the API to TypeScript if
  the operational simplicity is a win. (Probably not — FHIR parsing
  in Python is mature.)

Roughly 4–6 weeks of pure migration work. Doable; not where I'd
spend the time.

## 8. References

- [`badlogic/pi-mono`](https://github.com/badlogic/pi-mono) — the repo under evaluation
- [`SKILL-AGENT-WORKSPACE.md`](SKILL-AGENT-WORKSPACE.md) Appendix A — prior openclaw review (different focus: skill content, not the harness)
- [`MODE-SWITCHING.md`](MODE-SWITCHING.md) §7 — the current forward path the borrows in §6 above accelerate
- [`STREAMING-AND-GATEWAY.md`](STREAMING-AND-GATEWAY.md) §3 — model-gateway discussion; pi-ai is one possible implementation
- [`SELF-MODIFYING-WORKSPACE.md`](SELF-MODIFYING-WORKSPACE.md) §2.5 — mid-run inline comments deferred item that the steering queue closes
- [`ATLAS-DATA-MODEL.md`](../ATLAS-DATA-MODEL.md) Decision 5 — provenance, not the harness, is the moat

---

*End of report.*
