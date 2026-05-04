# Build Orchestration

> The meta-doc. How the build is run, who does what, what models do which work, and how new contributors (human or agent) plug in. Read this once; refer to `BUILD-TRACKER.md` for active task state.

## Roles

| Role | Owner | Tools | Responsibilities |
|---|---|---|---|
| **Main thread** | Claude Opus 4.7 (Max mode) | full toolset, agent dispatch, write/edit, bash | Synthesis, decisions, code review, doc updates, dispatching sub-agents, tracker maintenance, propagating implications |
| **Sub-agent (Sonnet 4.6)** | Claude Sonnet 4.6 | full toolset within sub-agent scope | Multi-file code work, harmonization sub-tasks with logic, vision-extraction prompt iteration, test fixture generation |
| **Sub-agent (Haiku 4.5)** | Claude Haiku 4.5 | full toolset within sub-agent scope | Pure research (read N URLs, summarize), single-file code generation from a tight spec, file inventory, bibliography compilation, format conversions |
| **Blake** | Human | login credentials, decisions, outreach | Real-data acquisition, strategic decisions, Josh outreach, demo direction, final approval |

**Sub-agent model rule of thumb (revised 2026-04-29 per Blake):**

Default to **Sonnet 4.6** for any task that writes, modifies, or designs code. Blake is more comfortable with Sonnet's code quality than Haiku's, and the cost difference is modest at this scale.

- **Sonnet 4.6 (default for coding):** any adapter implementation, any harmonize sub-task, any extraction prompt iteration, any test fixture generation, any non-trivial documentation that requires structured judgment (architecture-adjacent docs, decision logs)
- **Haiku 4.5 (reserved for narrow mechanical work):** pure file-system inventory, single-file format conversions with no logic, repo-clone + record-SHA tasks, summarization of pre-structured input. If the task involves *writing more than ~50 lines of new code*, use Sonnet.
- **Main thread (Opus 4.7):** synthesis, decisions, code review, doc updates that propagate implications, dispatching, tracker maintenance.

Never default to spawning Opus sub-agents. Reserve Opus for the main thread.

## Dispatch loop

The standard cycle for every task in the tracker:

1. **Pick the next unblocked task** from `BUILD-TRACKER.md`.
2. **Decide the owner.** Self (main thread), sub-agent (specify model), or Blake.
3. **If sub-agent:** write a brief using the template below. Spawn with `run_in_background: true` if independent of the next task; foreground if blocking.
4. **While sub-agent runs:** continue with non-overlapping work on the main thread.
5. **When sub-agent returns:** read the output file, update the tracker (`in_progress` → `done` + notes), check downstream tasks for unblocking, propagate implications to relevant docs (architecture, plan, etc.).
6. **Status update to Blake** when: (a) a milestone clears (a stage's gate is met), (b) a blocker appears, (c) an open decision needs his input. Routine progress is not pinged — Blake reads the tracker on his own cadence.

## Sub-agent brief template

Every spawned sub-agent gets a brief in this shape, kept tight (under ~400 words for Haiku, under ~600 for Sonnet):

```
GOAL: <one sentence on what to deliver>

READ FIRST (for context, do not re-derive):
- /Users/blake/Repo/ehi-ignite-challenge/ehi-atlas/BUILD-TRACKER.md (your task: ID <X.Y>)
- <other paths with line ranges if relevant>

DO:
- <bounded steps>
- <output format / length>

DON'T:
- <out-of-scope work>
- <copyright limits if research>
- update BUILD-TRACKER.md yourself — propose the update in your final message

OUTPUT PATH: <explicit absolute path>
RETURN: punch-line summary + proposed tracker update (status + new notes)
```

## Parallelism rules

- **Independent file targets → parallel.** Sub-agents A and B writing to different paths spawn together (one assistant message with two `Agent` tool calls + `run_in_background: true`).
- **Shared file target → serial.** Two sub-agents writing the same file is forbidden.
- **Tracker writes → main thread only.** Sub-agents propose updates in their final message; main thread applies.
- **Decisions → main thread only.** Sub-agents flag, never decide.
- **Default cap: 3 sub-agents in flight.** Higher only on demand.

## Tracker maintenance

`BUILD-TRACKER.md` has the canonical task list. Conventions:

- **Status values:** `pending`, `in_progress`, `blocked`, `review`, `done`, `cut`
- **Owner values:** `main-thread`, `sub:haiku`, `sub:sonnet`, `Blake`
- **Update protocol:** edit the row's status + notes columns when it transitions; add to the `## Recent activity` section if the change is notable
- **New tasks:** add to the appropriate Stage section with a sequential ID (e.g., `1.7`, `2.4`)
- **Open decisions:** flag in the `## Open decisions` table at the bottom of the tracker; recommendation always present

## Synthesis cadence

When a sub-agent returns, the main thread:

1. Reads the output file the sub-agent wrote (do not skip this — the agent's summary describes what it intended; the file shows what it did)
2. Updates the tracker row to `done` with a one-line note
3. Checks downstream tasks: any unblocked? Mark `pending` → ready for dispatch
4. If the output reveals a new architectural fact, propagates to relevant arch doc with a one-line edit
5. Brief status update to Blake when warranted (see "Status update to Blake" rules above)

## Stand-up at session start

When a fresh main-thread session opens:

1. Read `BUILD-TRACKER.md` top-to-bottom
2. Summarize: what's `done` since last touch, what's `in_progress`, what's `blocked`, what's the next unblocked work
3. Propose the next 1–3 actions (dispatch X, ask Blake about Y, write Z)
4. Wait for Blake's signal before spawning anything material

## Where state lives (three layers)

| Layer | Path | Updated | Read by |
|---|---|---|---|
| **Strategic foundation** | `~/Chief/20-projects/ehi-ignite-challenge/{EXECUTION-PLAN, architecture/, research/}` | Rarely; major pivots only | Everyone, always read first |
| **Operational state** | `ehi-atlas/BUILD-TRACKER.md` | Every task transition | Anyone running the build |
| **Cross-session memory** | `~/.claude/projects/-Users-blake-Chief/memory/` | When durable facts surface | Future Claude sessions |

The tracker is the bridge between session-by-session execution and long-lived strategic docs.

## Things sub-agents must never do

1. Update `BUILD-TRACKER.md` (propose only)
2. Update strategic foundation docs (`EXECUTION-PLAN.md`, architecture docs) — those are main-thread territory
3. Decide architectural questions (flag, don't decide)
4. Spawn further sub-agents (no recursive dispatch — main thread orchestrates)
5. Run destructive `git` operations (push, force-push, branch -D, reset --hard)
6. Touch any file outside their declared output path without surfacing it first

## Privacy gate enforcement

Built into the dispatch:

- **Real personal data** (Blake's, Devon's, Cedars portal scrapes) lives in `corpus/_sources/<personal>/raw/` — gitignored
- **Redacted variants** live in `raw-redacted/` — committable
- **Sub-agents working with personal data** must verify their output writes only to redacted paths or non-personal tier locations
- **A privacy-gate validator** runs before any commit (`make validate-gate`) and fails the build if personal raw data has been staged

## Session continuity

Three rituals to keep continuity tight across sessions and across agents:

1. **End-of-session note:** main thread writes a one-paragraph `## Recent activity` entry at the bottom of `BUILD-TRACKER.md` summarizing what was done and what's next.
2. **Memory updates:** durable facts that future sessions need (decisions made, paths chosen, gotchas discovered) get saved to `~/.claude/projects/-Users-blake-Chief/memory/` via the auto-memory system.
3. **Architecture-doc edits propagate:** when implementation discovers an architectural fact not in the doc, main thread updates the doc with a one-line edit referencing the source of the discovery (commit, sub-agent output, etc.).

## Versioning

This document is stable. Material changes (new role, new model assignment, new state layer) require an explicit version bump and a note in `BUILD-TRACKER.md` `## Recent activity`.

- **v1** (2026-04-29): Initial orchestration plan, three-layer state model, model selection rules, sub-agent brief template
