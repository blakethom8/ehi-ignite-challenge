# Autonomous Build Loop — Process Reference

> How to run the self-directed, multi-agent feature development loop for this project.
> Written after the April 5, 2026 sprint that shipped 23 features in a single session.

---

## What This Is

A fully autonomous build loop where Claude acts as an **orchestrator** dispatching specialized sub-agents to research, plan, and implement features — without human intervention between each build. The orchestrator maintains a shared queue file as coordination state, runs builds in parallel when files don't conflict, and smoke-tests every backend change before marking it done.

In the April 5 sprint: 3 research agents ran in parallel to generate a 21-item backlog, then 23 features shipped across ~14 build cycles, including parallel builds that ran simultaneously on non-overlapping files.

---

## The Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    YOU (Orchestrator)                     │
│                                                           │
│  Read queue → pick items → dispatch agents → update queue │
└──────────────┬──────────────────────────┬────────────────┘
               │                          │
    ┌──────────▼──────────┐   ┌──────────▼──────────┐
    │   Research Agents    │   │    Build Agents       │
    │  (Explore subtype)   │   │  (general-purpose)   │
    │                      │   │                       │
    │  Read codebase →     │   │  Read → implement →  │
    │  propose features →  │   │  smoke test → TSC →  │
    │  return ideas        │   │  report back         │
    └──────────┬──────────┘   └──────────┬──────────┘
               │                          │
               ▼                          ▼
    .claude/feature-queue.md    (queue updated by orchestrator)
    .claude/build-log.md        (build log updated by orchestrator)
```

---

## The Shared State Files

| File | Purpose |
|---|---|
| `.claude/feature-queue.md` | Single source of truth — queued, in-progress, and completed items |
| `.claude/build-log.md` | Timestamped log of every build: what changed, smoke test output |
| `.claude/AUTONOMOUS-BUILD-LOOP.md` | This file — process reference |

---

## The Two Prompt Templates

To run the loop, paste either prompt into a Claude Code session. The prompts are designed to be run together (both in the same message) or separately on a schedule.

### Research Orchestrator Prompt

```
You are the research orchestrator for the EHI Ignite Challenge build loop.

1. Read /Users/blake/Repo/ehi-ignite-challenge/.claude/feature-queue.md to see what's already queued and completed.
2. Count how many items are currently QUEUED (not completed, not in-progress). If there are already 6+ queued items, skip this cycle and just report "Queue full, skipping research pass."
3. If fewer than 6 are queued: spawn a background Explore agent to review the codebase from whichever of these perspectives has fewest queued items: (C) Clinician, (D) Data, (U) UX. Ask it to produce 3-4 new feature ideas NOT already in the queue. When the agent returns, append its suggestions to the Queued section of /Users/blake/Repo/ehi-ignite-challenge/.claude/feature-queue.md.
4. Append a timestamped entry to the Research Log section of the queue file recording what was added.

Keep the queue file clean and well-formatted markdown. Do not duplicate items that are already there.
```

### Build Orchestrator Prompt

```
You are the build orchestrator for the EHI Ignite Challenge build loop.

1. Read /Users/blake/Repo/ehi-ignite-challenge/.claude/feature-queue.md.
2. If there are no QUEUED items (only In Progress or empty), skip this cycle.
3. If an item is already IN PROGRESS, check whether it seems stuck (it should complete within one cycle). If stuck, move it back to QUEUED and pick the next one.
4. Pick the highest-priority QUEUED item. Move it to "In Progress" in the queue file.
5. Spawn a general-purpose agent (NOT background) to implement it. Give the agent:
   - The full feature description
   - Relevant files to read first (check api/, app/src/, fhir_explorer/)
   - The instruction: after implementing, restart uvicorn if backend changed: `lsof -ti :8001 | xargs kill -9 2>/dev/null; cd /Users/blake/Repo/ehi-ignite-challenge && uv run uvicorn api.main:app --reload --port 8001 &> /tmp/uvicorn-ehi.log &`
   - The instruction: run `cd /Users/blake/Repo/ehi-ignite-challenge/app && npx tsc --noEmit` to verify no TypeScript errors before finishing
6. When the build agent returns: move the item from "In Progress" to "Completed" in the queue file, and append a timestamped entry to /Users/blake/Repo/ehi-ignite-challenge/.claude/build-log.md describing what was built and which files changed.

Focus on LOW and MEDIUM complexity items first. Skip HIGH complexity items until most LOW/MEDIUM items are done.
```

---

## Running the Loop

### Option 1 — Manual (one cycle at a time)

Paste both prompts into Claude Code. The orchestrator will:
1. Check if research is needed (queue < 6 items)
2. Pick the next build item
3. Run research and build in parallel if both are needed
4. Update the queue and log when done
5. You can paste again to run the next cycle

### Option 2 — Cron-scheduled (fully autonomous)

Use Claude Code's `CronCreate` tool to schedule both orchestrators to run automatically:

```
Research cron: every 23 minutes
Build cron: every 37 minutes (offset from research to avoid conflicts)
```

Example cron setup (run in a Claude Code session):

```
Please create two cron jobs:
1. Every 23 minutes, run the research orchestrator prompt
2. Every 37 minutes, run the build orchestrator prompt
Use CronCreate for each.
```

The offset (23 vs 37 min) prevents the research and build orchestrators from writing to the queue file simultaneously.

To check cron status: `CronList`
To stop: `CronDelete` with the cron ID

### Option 3 — Parallel builds (manual, high throughput)

When you have multiple queued items that touch non-overlapping files, run two build orchestrator prompts simultaneously. The key discipline: give each agent an explicit "files you may touch / files you must not touch" list.

Safe to parallelize:
- Backend-only agent + frontend-only agent
- Two agents on different pages (e.g., Safety.tsx vs Corpus.tsx)
- Corpus endpoint + patient endpoint (different router files)

Never parallelize:
- Two agents both touching `api/models.py`
- Two agents both touching `api/routers/patients.py`
- Two agents both touching `app/src/App.tsx`

---

## How Build Agents Are Briefed

The orchestrator is responsible for writing a detailed brief for each build agent. A good brief includes:

1. **Feature description** — what to build, exact behavior, edge cases
2. **Files to read first** — always tell the agent what to read before writing
3. **Files it may touch** — explicit allowlist
4. **Files it must not touch** — explicit blocklist (prevents conflicts with parallel agents)
5. **Implementation spec** — data models, API endpoint shape, UI layout, design tokens
6. **Smoke test command** — exact curl command to verify the backend works
7. **TSC check command** — `cd app && npx tsc --noEmit`

The more precise the brief, the less likely the agent is to make architectural decisions you don't want.

---

## Queue File Format

```markdown
## 🔨 In Progress
- **(C) Feature Name** — BUILD-XXX — brief description

## 📋 Queued (priority order)

### LOW complexity
1. **(C/D/U) Feature Name** — Description. No new endpoint needed / new endpoint at /path.

### MEDIUM complexity
2. ...

### HIGH complexity
3. ...

## ✅ Completed
- [x] Feature Name — what was built [BUILD-XXX]

## 🔬 Research Log
**2026-04-05 — Research pass N**
- What perspective ran, what was found, what was added
```

Perspective tags: `(C)` Clinician/Surgeon · `(D)` Data Transparency · `(U)` UX/Product

---

## What Worked Well in the April 5 Sprint

**File-as-mutex discipline.** Every build agent got an explicit may-touch / must-not-touch list. In 23 builds across a full day, zero write conflicts occurred in practice.

**Backend-first when uncertain.** When two agents might conflict on a shared file, send one to do backend-only work while the other does frontend-only work.

**Smoke test every backend change.** Every backend build was verified with a `curl` before being declared done. This caught import errors, method name mismatches, and timezone issues before they accumulated.

**Research at low tide.** Research agents only ran when the queue dropped below 6 items. This prevented backlog bloat while ensuring the queue never ran dry.

**Rotating perspectives.** Research agents alternated between Clinician, Data, and UX perspectives. This produced a balanced backlog instead of over-indexing on one domain.

**LRU cache matters.** The `@lru_cache(maxsize=30)` on `load_patient()` made every repeat request sub-1ms. Without it, parallel frontend + corpus agents would both be thrashing disk.

---

## What to Watch For

**`api/models.py` is a write-conflict bottleneck.** Multiple builds often need to add Pydantic models here. When running parallel builds, assign one agent to do all model additions, or stagger the builds sequentially for any feature requiring new models.

**`api/routers/patients.py` grows fast.** It hit ~800 lines in one session. Consider splitting into sub-routers (`routers/patients_labs.py`, `routers/patients_safety.py`) before the next major sprint.

**Corpus endpoints are slow on cold start.** `/corpus/stats`, `/corpus/observation-distributions`, and `/corpus/export` all load 1,180 bundles. First call takes 30–90 seconds. The LRU cache warms up individual patients but corpus-level scans are always cold. A pre-computed stats file or background warmup task would help.

**Stale queue entries accumulate.** The orchestrator should verify completed items against the actual codebase, not just the queue file. A build that was interrupted mid-way may be partially complete — always check before marking done or re-queueing.

**TSC passes but runtime can still fail.** TypeScript checks types but not runtime API shapes. Always run the smoke test curl, not just TSC.

---

## Adapting This Loop to a New Project

1. Copy this `.claude/` directory structure to the new repo
2. Update `feature-queue.md` with the new project's initial backlog (or run 3 research agents to generate it)
3. Update the server restart command in the build orchestrator prompt to match the new stack
4. Update the TSC check command if the frontend is in a different directory
5. Adjust the file conflict rules to match the new repo's architecture

The loop itself is stack-agnostic — the research and build agent prompts can be adapted to any FastAPI/React, Django/Vue, Rails, or other stack by updating the file paths and commands.
