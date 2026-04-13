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
- [ ] **P1.2** — Derived `medication_episode` table via `episode_detector`
  - Files: `patient-journey/core/sql_on_fhir/sqlite_sink.py` (edit), `patient-journey/core/sql_on_fhir/views/README.md` (new — documents pure vs derived views)
  - Read first: `patient-journey/core/episode_detector.py`
  - Smoke test: `SELECT * FROM medication_episode LIMIT 5` returns rows
- [ ] **P1.3** — `views/condition_active.json` filtered subset view
  - Files: new JSON, test
  - Smoke test: pytest asserts row count ≤ `condition`
- [ ] **P1.4** — `observation_latest` SQLite VIEW
  - Files: `sqlite_sink.py` (edit), test
  - Smoke test: row count ≤ observation row count and each (patient_ref, loinc_code) pair appears at most once

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

> **Phase 0 closed.** P1.1 shipped on the same day. Next up: P1.2 (`medication_episode`) or a parallelizable Phase 1 task.

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
