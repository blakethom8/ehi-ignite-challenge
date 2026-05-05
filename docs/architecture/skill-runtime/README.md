# Skill Runtime — Architecture Bundle

> Documents in this folder describe the **Skill + Agent + Workspace**
> runtime: the layered substrate that lets clinical skills ship as
> versioned markdown files executed by a generic agent loop in a
> mediated workspace. Read in this order if it's your first pass.

---

## Read order

| # | Doc | What it covers | When to read |
|---|---|---|---|
| 1 | [`SKILL-AGENT-WORKSPACE.md`](SKILL-AGENT-WORKSPACE.md) | The parent architecture spec. Three layers, three module shapes (Dashboard / Brief+Workspace / Conversational), skill format, workspace runtime, citation graph, worker phases (W0→W4). | First. This is the foundation everything else extends. |
| 2 | [`SELF-MODIFYING-WORKSPACE.md`](SELF-MODIFYING-WORKSPACE.md) | The "save → mutate" loop. Per-run edits, patient memory layer, three save destinations, what's explicitly out of scope. | After 1, before any work involving `_memory/` or save destinations. |
| 3 | [`MODE-SWITCHING.md`](MODE-SWITCHING.md) | Toggle between deterministic Phase-N walks and Claude-driven agent loop. Tool registry, dispatch, escalation handling, finalize, env vars + brief overrides. | Before turning on `SKILLS_RUN_MODE=agent` or wiring a new skill into agent mode. |
| 4 | [`STREAMING-AND-GATEWAY.md`](STREAMING-AND-GATEWAY.md) | Connection layer between the runtime and clients. SSE vs WebSockets vs gateway-service, EventHub contract, why FastAPI plays the gateway role today. | Before adding new run-event endpoints, wiring streaming UI, or moving toward W2 sandbox isolation. |
| 5 | [`TOOL-SURFACE.md`](TOOL-SURFACE.md) | Inventory of agent capabilities — what's in the registry today, what's not, recommended next adds (web search, web fetch, browser automation, mid-run messages). | When proposing a new skill that needs capabilities the current agent doesn't have. |
| 6 | [`PI-MONO-EVALUATION.md`](PI-MONO-EVALUATION.md) | Decision record on adopting pi-mono (the TS harness behind OpenClaw) vs borrowing patterns. Recommends Option C — borrow, not adopt — and lists the four next commits that close the gap. | If reconsidering the harness substrate or migrating providers. |

## How the docs map to the code

```
api/core/skills/
  loader.py          ← SKILL-AGENT-WORKSPACE §5 (skill format)
  workspace.py       ← SKILL-AGENT-WORKSPACE §6.3 + SELF-MODIFYING-WORKSPACE §3-5
  patient_memory.py  ← SELF-MODIFYING-WORKSPACE §4
  event_hub.py       ← STREAMING-AND-GATEWAY §5
  runner.py          ← MODE-SWITCHING §2 (mode dispatch)
  agent_loop.py      ← MODE-SWITCHING §3-5 (Claude agent loop)
  worker.py          ← SKILL-AGENT-WORKSPACE §6.7 (W1 worker phase)
  clinicaltrials_gov.py ← TOOL-SURFACE §1 (registered domain tool)

api/routers/skills.py ← STREAMING-AND-GATEWAY §5.2 (SSE endpoint)

skills/trial-matching/
  SKILL.md, workspace.template.md, output.schema.json, evals/rubric.md
                     ← SKILL-AGENT-WORKSPACE §5.1, §7
```

## Companion docs outside this folder

These are referenced from the runtime docs but live elsewhere:

- [`../ATLAS-DATA-MODEL.md`](../ATLAS-DATA-MODEL.md) — the data-graph
  decisions (Provenance lineage, hot/cold path, USCDI-aligned silver
  layer). The skill runtime *consumes* the data graph; this doc
  defines it.
- [`../tracing.md`](../tracing.md) — per-span cost / token / duration
  capture. Orthogonal to SSE; both publish to disk and observability
  surfaces.
- [`../CONTEXT-ENGINEERING.md`](../CONTEXT-ENGINEERING.md) — the
  pre-digested context pipeline that feeds the agent's session-start
  context.
- [`../ANTHROPIC-AGENT-SDK.md`](../ANTHROPIC-AGENT-SDK.md) — earlier
  agent integration we left in place; the skill runtime is the next
  iteration past it.
- [`../../ideas/FEATURE-IDEAS.md`](../../ideas/FEATURE-IDEAS.md) —
  the full skill catalog driving capability requirements (Trial
  Match, Med Access, Grants, Care Gap, Second Opinion, etc.).

## Status snapshot (2026-05-05)

What's shipping in code today:

- ✅ Skill loader + manifest validator (Layer 3)
- ✅ Workspace primitives (write/cite/escalate) and three save destinations (Layer 1)
- ✅ Patient memory layer (cross-run pinned facts + context packages)
- ✅ EventHub + SSE streaming endpoint
- ✅ Worker pool (W1)
- ✅ Deterministic Phase-0..5 trial-matching loop
- ✅ Claude agent loop (mode-toggleable; `SKILLS_RUN_MODE=auto`)
- ✅ Trial Finder UI module (`/skills/trial-finder`)
- ✅ Patient memory page (`/skills/patients/memory`)

What's documented as deferred:

- ⏳ Token-by-token streaming in agent mode (`MODE-SWITCHING.md` §7)
- ⏳ Schema-error feedback to the agent on bad finalize (`MODE-SWITCHING.md` §6)
- ⏳ Mid-run clinician messages / steering queue (`SELF-MODIFYING-WORKSPACE.md` §2.5)
- ⏳ Web search + web fetch tools (`TOOL-SURFACE.md` §3-4)
- ⏳ Browser automation + W2 sandbox (`TOOL-SURFACE.md` §5)
- ⏳ Multi-provider abstraction (`PI-MONO-EVALUATION.md` §6 borrow #4)
- ⏳ Resume after escalation in agent mode (`MODE-SWITCHING.md` §6)
