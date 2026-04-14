# SQL-on-FHIR Task Queue

*Single source of truth for the `sof-orchestrator` loop. Mutated by the orchestrator agent only — not by build sub-agents or by the user directly (the user edits `sof-project-plan.md` instead, and the orchestrator copies tasks down).*

**Legend:**
- `[ ]` Queued
- `[~]` In Progress (agent name in parens)
- `[x]` Completed (commit hash in parens)
- `⭐` Highest-ROI items — dispatch first
- `⛔` Blocked — waiting on an open question from `sof-project-plan.md`

Tasks are dispatched **in phase order**. Do not pull Phase 1 work while any Phase 0 task is Queued or In Progress.

---

## Phase 0 — Lock the prototype in

- [x] ⭐ **P0.1** — Add `run_sql(query, limit)` tool to `provider_assistant_agent_sdk` *(done `cf0efaa`, 2026-04-13)*
  - Files: `api/core/provider_assistant_agent_sdk.py` (edit), `api/core/sof_tools.py` (new), `api/tests/test_sof_tools.py` (new)
  - Read first: `api/core/provider_assistant_agent_sdk.py`, `patient-journey/core/sql_on_fhir/views/*.json`, `patient-journey/core/sql_on_fhir/sqlite_sink.py`
  - Smoke test: `uv run pytest api/tests/test_sof_tools.py -q`
  - Acceptance: the tool is discoverable by the agent SDK, SELECT-only gate rejects DROP/INSERT, the system prompt includes the five view schemas
- [x] **P0.2** — FastAPI startup hook materializes `data/sof.db` if stale *(done `0edbd8b`, 2026-04-13)*
  - Files: `api/main.py` (edit), `api/core/sof_materialize.py` (new), `api/tests/test_sof_materialize.py` (new), `.gitignore` (edit)
  - Read first: `api/main.py`, `patient-journey/core/sql_on_fhir/sqlite_sink.py`, `patient-journey/core/sql_on_fhir/loader.py`
  - Smoke test: delete `data/sof.db`, boot API, confirm DB exists and row counts are >0
  - Acceptance: idempotent — second boot is fast (mtime check)
- [x] **P0.3** — 200-patient pitch snapshot at `research/ehi-ignite.db` *(done `472994d`, 2026-04-13)*
  - Files: `research/ehi-ignite.db` (new), `.gitignore` (edit), `research/README.md` (edit)
  - Smoke test: `python3 -c "import sqlite3; c=sqlite3.connect('research/ehi-ignite.db'); print(c.execute('SELECT COUNT(*) FROM patient').fetchone())"` prints `(200,)`
  - Acceptance: file size < 20 MB
- [x] **P0.4** — Document the `run_sql` tool surface *(done, 2026-04-13 — commit pending in same pass as queue update)*
  - Files: `research/SQL-ON-FHIR-REVIEW.md` (append), `CLAUDE.md` (add mention of `sql_on_fhir` module)
  - Dispatch: `sof-scribe` directly (no builder needed)

## Phase 1 — Clinically smart tables

- [x] ⭐ **P1.1** — `drug_class` enrichment on `medication_request` *(done, 2026-04-13 — commit pending in same pass as queue update)*
  - Files: `patient-journey/core/sql_on_fhir/sqlite_sink.py` (edit), `patient-journey/core/sql_on_fhir/enrich.py` (new), `patient-journey/core/sql_on_fhir/__init__.py` (edit), `patient-journey/tests/test_sql_on_fhir.py` (extend, +15 tests), `api/core/sof_tools.py` (edit — schema renderer + preamble), `research/ehi-ignite.db` (rebuilt), `research/README.md` / `research/SQL-ON-FHIR-REVIEW.md` / `CLAUDE.md` (doc updates)
  - Read first: `patient-journey/core/drug_classifier.py`, `patient-journey/core/sql_on_fhir/sqlite_sink.py`
  - Smoke test: `python3 -m pytest patient-journey/tests/test_sql_on_fhir.py -q` + `SELECT drug_class, COUNT(*) FROM medication_request GROUP BY drug_class` returns non-empty groups ✅
- [x] **P1.2** — Derived `medication_episode` table via `episode_detector` *(done `4b2de2f`, 2026-04-13)*
  - Files: `patient-journey/core/sql_on_fhir/derived.py` (new — Derivation registry), `patient-journey/core/sql_on_fhir/sqlite_sink.py` (edit — derivation pass + sentinel resolver), `patient-journey/core/sql_on_fhir/__init__.py` (edit), `patient-journey/core/sql_on_fhir/views/README.md` (new — documents pure vs enriched vs derived), `api/core/sof_tools.py` (edit — render derived tables in prompt), `patient-journey/tests/test_sql_on_fhir.py` (+11 tests), `research/ehi-ignite.db` (rebuilt)
  - Smoke test: `SELECT * FROM medication_episode LIMIT 5` returns rows ✅ (820 episodes in pitch snapshot: 512 completed + 308 active)
- [x] **P1.3** — `views/condition_active.json` filtered subset view *(done `ca9e284`, 2026-04-13)*
  - Files: `patient-journey/core/sql_on_fhir/views/condition_active.json` (new — same columns as condition + view-level where clause), `patient-journey/core/sql_on_fhir/views/README.md` (edit — new row in pure-views table + subset footnote), `patient-journey/tests/test_sql_on_fhir.py` (+6 tests), `research/ehi-ignite.db` (rebuilt)
  - Smoke test: pitch snapshot `condition_active`=674 rows, exact 'active' subset of `condition`=1410 ✅
- [x] **P1.4** — `observation_latest` SQLite VIEW *(done `ca9e284`, 2026-04-13)*
  - Files: `patient-journey/core/sql_on_fhir/derived.py` (edit — `Derivation.kind` field + `build_observation_latest` + registry entry), `patient-journey/core/sql_on_fhir/__init__.py` (edit — re-exports), `api/core/sof_tools.py` (edit — renderer emits CREATE VIEW/TABLE by kind + preamble guidance), `patient-journey/core/sql_on_fhir/views/README.md` (edit — 4th layer + schema), `patient-journey/tests/test_sql_on_fhir.py` (+10 tests), `research/ehi-ignite.db` (rebuilt)
  - Smoke test: pitch snapshot `observation_latest`=5,546 rows = 5,546 distinct (patient_ref, loinc_code) pairs, live reflection of source table verified in test ✅

## Phase 2 — NL search demo

- [ ] ⛔ **P2.1** — `POST /api/cohort/chat` streams Claude + tool-calls to `run_sql`
  - Blocked on: open question #4 (SSE vs websockets) from sof-project-plan.md
  - Files: `api/routers/cohort.py` (new), `api/main.py` (register), `api/tests/test_cohort.py` (new)
- [ ] ⛔ **P2.2** — Frontend `CohortBuilder.tsx` at `/explorer/cohort`
  - Blocked on: open question #1 (hero query for Max Gibber)
  - Files: `app/src/pages/Explorer/CohortBuilder.tsx` (new), route, `app/src/api/client.ts`
- [ ] **P2.3** — Row-level citations
  - Files: `api/routers/cohort.py` (edit), `app/src/components/Citation.tsx` (new)
- [ ] **P2.4** — Query result cache
  - Files: `api/core/sof_cache.py` (new), tests

---

## In Progress

_(none)_

---

## Completed

- **P0.1** — `run_sql` wired into the agent SDK (`cf0efaa`, 2026-04-13)
- **P0.2** — FastAPI startup hook materializes `data/sof.db` with mtime gate (`0edbd8b`, 2026-04-13)
- **P0.3** — 200-patient pitch snapshot committed at `research/ehi-ignite.db` (`472994d`, 2026-04-13)
- **P0.4** — `run_sql` tool surface documented in `SQL-ON-FHIR-REVIEW.md` addendum + `CLAUDE.md` (2026-04-13)
- **P1.1** — `drug_class` enrichment on `medication_request`: enrich.py module, default-on registry, sof_tools schema aware, 15 new tests, pitch snapshot rebuilt (2026-04-13)
- **P1.2** — Derived `medication_episode` table: derived.py registry, sink derivation pass with sentinel resolver, views/README.md (pure/enriched/derived layers), sof_tools renders derived tables in the LLM prompt, 11 new tests, pitch snapshot rebuilt with 820 episodes (`4b2de2f`, 2026-04-13)
- **P1.3** — `condition_active` filtered subset view: new ViewDefinition JSON with view-level where clause (active|recurrence|relapse), same column shape as `condition`, 6 new tests, pitch snapshot carries 674 active conditions out of 1,410 total (`ca9e284`, 2026-04-13)
- **P1.4** — `observation_latest` SQLite VIEW: Derivation gains `kind="view"` mode, build_observation_latest emits DROP+CREATE VIEW with ROW_NUMBER() OVER partition, sof_tools emits CREATE VIEW vs CREATE TABLE by kind, 10 new tests, pitch snapshot carries 5,546 latest-per-pair observations (live projection, always fresh) (`ca9e284`, 2026-04-13)

> **Phase 1 closed.** All four Phase 1 tasks done — the warehouse now exposes four categories of query target: pure ViewDefinitions, filtered subset views (P1.3), enriched columns (P1.1), and derived artifacts in two flavours (materialized table P1.2, lazy view P1.4). Next up: Phase 2 (NL search demo) — but P2.1 and P2.2 are both blocked on open questions in `sof-project-plan.md`. Tomorrow should unblock those before resuming the loop.

---

## Research Log

| When | What | Who |
|---|---|---|
| 2026-04-13 | Initial queue bootstrapped from `sof-project-plan.md` | human |

---

## Dispatch Notes

- Parallelizable in Phase 0: **none** (P0.1 → P0.2 → P0.3 are sequential, P0.4 is doc-only and can run after P0.1 ships)
- Parallelizable in Phase 1: **P1.3 ⊥ P1.4** (different files), **P1.1 ⊥ P1.3** (different files), **P1.2 and P1.1 conflict** (both edit `sqlite_sink.py`)
- Parallelizable in Phase 2: **P2.1 ⊥ P2.2** once both are unblocked — the frontend can stub the backend contract until the backend lands
