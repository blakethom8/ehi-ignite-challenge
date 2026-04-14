# SQL-on-FHIR → LLM Platform — Project Plan

*Created April 13, 2026. Owned by the `sof-orchestrator` agent.*

This is the executable plan the Opus orchestrator reads to pick the next unit of work. It's a condensed, operational cousin of `research/SQL-ON-FHIR-NEXT-STEPS.md` — that doc explains *why*, this doc tells the orchestrator *what to dispatch next*.

Companion files:
- `research/SQL-ON-FHIR-REVIEW.md` — qualitative review + verdict
- `research/SQL-ON-FHIR-NEXT-STEPS.md` — the narrative roadmap
- `.claude/sof-task-queue.md` — the live queue the orchestrator mutates
- `.claude/sof-build-log.md` — timestamped log of every unit shipped
- `.claude/agents/sof-orchestrator.md` — Opus orchestrator
- `.claude/agents/sof-builder.md` — Sonnet build sub-agent
- `.claude/agents/sof-scribe.md` — Sonnet documentation/capture sub-agent

---

## North Star

Ship a working "SQL-on-FHIR as LLM substrate" demo for the EHI Ignite Challenge by **May 13, 2026** (Phase 1 deadline). The demo must show:

1. Claude answering a cohort question in the UI by emitting SQL against a materialized SQLite database
2. Row-level citations linking back to underlying FHIR resources
3. The ViewDefinition JSONs committed as portable artifacts
4. A committed pitch-ready `.db` snapshot reviewers can query directly

If we only hit one thing: **the cohort-builder chat demo**. Everything else is in service of it.

---

## Operating Principles

1. **Phase order is prescriptive.** Do not pull Phase 2 work while Phase 0 is open. Parallelism within a phase is fine when files don't conflict.
2. **Every build unit has a smoke test.** No task is Done until the orchestrator sees green output from the test the builder ran.
3. **Every build unit generates a capture.** After a builder finishes, the orchestrator dispatches the `sof-scribe` sub-agent to append a build-log entry and update any user-facing docs that changed meaning. Documentation is not optional.
4. **The Python parser stays untouched unless a task explicitly says so.** We decided (see the review) to keep both layers. Builders should not "improve" `fhir_explorer/` as a side effect.
5. **New ViewDefinitions are data, not code.** Prefer editing `views/*.json` over editing the runner. Edit the runner only when a JSON expression hits a real limitation.
6. **Tests before merge.** Every phase ends with a green pytest run of `patient-journey/tests/test_sql_on_fhir.py` plus any new suites.

---

## Phases — executable slices

Each task is sized to fit inside a single build sub-agent invocation (≤60 min of focused work).

### Phase 0 — Lock the prototype in

| ID | Task | Files | Smoke test | Priority |
|---|---|---|---|---|
| P0.1 | Add `run_sql(query, limit)` tool to `provider_assistant_agent_sdk`. SELECT-only gate. Injects ViewDefinition schemas into system prompt. | `api/core/provider_assistant_agent_sdk.py`, `api/core/sof_tools.py` (new), `api/tests/test_sof_tools.py` (new) | `uv run pytest api/tests/test_sof_tools.py -q` and manual Claude call returning a row | ⭐ HIGH |
| P0.2 | FastAPI startup hook materializes `data/sof.db` if stale (mtime check vs bundle dir). | `api/main.py`, `api/core/sof_materialize.py` (new) | Boot the API, confirm `data/sof.db` exists and row counts match expected | HIGH |
| P0.3 | Generate a 200-patient pitch `.db` snapshot under `research/ehi-ignite.db`. Update `.gitignore` exception. | `research/ehi-ignite.db`, `.gitignore`, `research/README.md` | `python3 -c "import sqlite3; print(sqlite3.connect('research/ehi-ignite.db').execute('SELECT COUNT(*) FROM patient').fetchone())"` | MED |
| P0.4 | Document `run_sql` tool surface for the competition writeup. | `research/SQL-ON-FHIR-REVIEW.md` (append), new section in `CLAUDE.md` | n/a — scribe task | MED |

**Exit criterion:** Claude Code session with `claude chat` can ask "which patients are on anticoagulants and NSAIDs simultaneously?" and get a correct answer backed by SQL.

### Phase 1 — Clinically smart tables

| ID | Task | Files | Smoke test | Priority |
|---|---|---|---|---|
| P1.1 | Post-materialization hook: add `drug_class` column to `medication_request` using `drug_classifier.classify()`. | `patient-journey/core/sql_on_fhir/sqlite_sink.py`, new `enrich.py`, tests | pytest + `SELECT drug_class, COUNT(*) FROM medication_request GROUP BY drug_class` returns non-empty | ⭐ HIGH |
| P1.2 | Derived `medication_episode` table via `episode_detector`. | `sqlite_sink.py`, `views/README.md` (explain pure vs derived), tests | `SELECT * FROM medication_episode LIMIT 5` returns rows | MED |
| P1.3 | `views/condition_active.json` as a filtered subset view. | new JSON, test | pytest asserts strict subset | LOW |
| P1.4 | `observation_latest` SQLite VIEW (ROW_NUMBER over partition). | `sqlite_sink.py`, tests | `SELECT COUNT(*) FROM observation_latest` ≤ `COUNT(*) FROM observation` | MED |

**Exit criterion:** `SELECT * FROM medication_request WHERE drug_class = 'anticoagulant' AND status = 'active'` returns real rows.

### Phase 2 — NL search demo

| ID | Task | Files | Smoke test | Priority |
|---|---|---|---|---|
| P2.1 | Backend: `POST /api/cohort/chat` streams Claude output with tool-calls to `run_sql`. | `api/routers/cohort.py` (new), `api/tests/test_cohort.py` | pytest + manual curl returns streaming response | ⭐ HIGH |
| P2.2 | Frontend: `CohortBuilder.tsx` page at `/explorer/cohort`. Chat UI, progressive disclosure (tokens → SQL → result table). | `app/src/pages/Explorer/CohortBuilder.tsx`, route registration, `api/client.ts` | `cd app && npx tsc --noEmit` + manual render | ⭐ HIGH |
| P2.3 | Row-level citations in responses: every emitted fact carries `{table, id}`. Frontend renders as hoverable badges. | `api/routers/cohort.py`, `app/src/components/Citation.tsx` (new) | pytest + type-check | MED |
| P2.4 | Query result cache keyed on `(query_hash, corpus_mtime)`. | `api/core/sof_cache.py` (new), tests | pytest — second call within cache TTL returns cached row | LOW |

**Exit criterion:** A clinician types "patients on warfarin with a recent A1c > 9" and sees Claude emit SQL, run it, and render a sortable result table with row citations.

### Phase 3 — Platform moves (post-submission)

Deferred. Captured in `research/SQL-ON-FHIR-NEXT-STEPS.md` §3. Orchestrator should not pick these up until P0–P2 are all Done.

### Phase 4 — Speculative research

Deferred. Captured in `research/SQL-ON-FHIR-NEXT-STEPS.md` §4.

---

## Dispatch Strategy

The `sof-orchestrator` Opus agent follows this loop:

```
1. Read .claude/sof-task-queue.md
2. If any task is stuck In Progress > 1 cycle, move it back to Queued with a note
3. Pick the highest-priority Queued task whose phase is open (no earlier-phase work is Queued or In Progress)
4. Move it to In Progress
5. Dispatch sof-builder (Sonnet) with a tight brief:
   - Task ID, description, file list, smoke test command
   - Read order: CLAUDE.md, research/SQL-ON-FHIR-REVIEW.md, research/SQL-ON-FHIR-NEXT-STEPS.md
   - Explicit "do not touch fhir_explorer/" guardrail
6. When builder reports back with a PASS + commit hash:
   - Dispatch sof-scribe (Sonnet) to append an entry to .claude/sof-build-log.md and update any affected user docs
   - Move the task to Completed
7. If builder reports FAIL: append to build log with the failure, leave task In Progress, and surface to the user
```

When two Queued tasks touch non-overlapping file sets, the orchestrator may dispatch two builders in parallel in the same tool-call batch. The file-conflict check is the orchestrator's responsibility, not the builders'.

---

## Guardrails (hard)

- **Never push to master.** All work lands on `feature/patient-journey-app-rEMpm`.
- **Never touch `fhir_explorer/parser/`.** Read only.
- **Never downgrade SQLite to an in-memory-only database.** `data/sof.db` is the persistence contract.
- **Never skip pytest.** A green test run is the contract for "Done."
- **Never commit `data/sof*.db` or `data/sof_bench.db`.** They are build artifacts and ignored.
- **Never modify this plan file from inside a build agent.** Only the orchestrator or the user edits `sof-project-plan.md`.

---

## Open Questions (for the user, not the agents)

These sit outside the orchestrator's autonomy. When a phase would need one of these to be resolved, the orchestrator should surface the question to the user and pause, not guess.

1. **Hero query for the P2 demo** — what's the single neurosurgery-relevant cohort question Max Gibber would type first?
2. **One DB or per-patient DBs?** Current default is one DB; revisit if the cohort UI gets slow.
3. **Should the pitch .db be regenerated deterministically?** If so, which 200 Synthea patients?
4. **Streaming protocol** — SSE or websockets for the cohort chat? Match existing `api/` conventions.

---

*Next action: the orchestrator should read `.claude/sof-task-queue.md` and dispatch P0.1.*
