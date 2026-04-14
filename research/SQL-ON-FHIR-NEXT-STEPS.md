# SQL-on-FHIR → LLM Platform: Next Steps

*April 13, 2026*

Living roadmap for turning the SQL-on-FHIR prototype (`patient-journey/core/sql_on_fhir/`) into the LLM-facing substrate for the EHI Ignite submission. Ordered by "what unlocks the most next" rather than strict dependency.

Companion to `research/SQL-ON-FHIR-REVIEW.md` (the "was it worth it" writeup) and `research/EP16-EP19-SYNTHESIS.md` (the strategic framing). Read those first if you're picking this up cold.

---

## Phase 0 — Lock the prototype in (≤1 day)

### 0.1 Wire `run_sql()` into the Claude agent  ⭐ **highest ROI**
**Why:** This is the first demo where "SQL-on-FHIR as LLM substrate" goes from a slide to a working thing. It's also the half-day move from the review.

**What:**
- New tool in `api/core/provider_assistant_agent_sdk.py`: `run_sql(query: str, limit: int = 50)` that opens `data/sof_demo.db` read-only and executes `query`.
- Inject the ViewDefinition schemas into the system prompt as CREATE TABLE statements plus the description fields from the JSONs.
- Hard cap: `SELECT`-only via simple regex gate + `EXPLAIN` sanity check; reject anything containing `ATTACH`, `PRAGMA`, `INSERT`, `UPDATE`, `DELETE`, `DROP`.
- Return rows as JSON with column names so Claude can cite them.

**Done when:** Asking Claude "which patients are on an anticoagulant and an NSAID at the same time?" produces a SQL query, runs it, and cites rows inline.

### 0.2 Materialize on service startup
**Why:** Demo currently rebuilds the DB every `python demo.py` run. For the agent tool we need a persistent DB that matches the loaded corpus.

**What:**
- `api/core/sof_materialize.py` — a FastAPI startup hook that checks `data/sof.db` mtime against the Synthea bundle directory and rebuilds only if stale.
- Idempotent: safe to call on every boot, cheap when up-to-date.

### 0.3 Persist `sof_demo.db` as a committed pitch artifact
**Why:** Lets reviewers `sqlite3 research/ehi-ignite.db "SELECT ..."` with zero setup. Strong demo affordance.

**What:**
- Generate a 200-patient snapshot, commit it under `research/` (not `data/` — avoids the gitignore).
- Sanity-cap size (<20MB) by limiting observation rows or filtering to a meaningful corpus.

---

## Phase 1 — Make the tables clinically smart (≤2 days)

### 1.1 Bridge the SQL world to `drug_classifier`
**Why:** SQL over raw RxNorm codes misses everything the existing `drug_classifier` module already knows (anticoagulant vs NSAID vs immunosuppressant). Without it, the killer cohort queries don't work.

**What:**
- Add a derived column to the `medication_request` view: `drug_class` (computed post-materialization by `drug_classifier.classify(rxnorm_code)`).
- This is a post-view enrichment step — the ViewDefinition JSON stays pure; enrichment lives in `sqlite_sink.materialize_all()` as an optional hook.
- Enables queries like `SELECT COUNT(*) FROM medication_request WHERE drug_class = 'anticoagulant' AND status = 'active'`.

### 1.2 Expose `episode_detector` as a view
**Why:** The Python parser already groups medications into episodes. Turning that into a SQLite table means Claude can ask "how many distinct ibuprofen courses has this patient had?" without running Python.

**What:**
- New table `medication_episode`: `(patient_ref, drug_class, rxnorm_display, start_date, end_date, n_fills, is_active)`.
- Populated by calling `episode_detector.detect_episodes()` per patient and inserting rows. Not a ViewDefinition — a derived materialized view.
- Document in `views/README.md` so the distinction between "pure ViewDefinition views" and "derived analytical views" is clear.

### 1.3 Add a `condition_active` convenience view
**Why:** Most clinical questions only care about active conditions. Filtering in every query is noise.

**What:**
- `views/condition_active.json` — same as `condition.json` plus `where: [{"path": "clinicalStatus.coding.first().code = 'active'"}]`.
- Tests that it's a strict subset of `condition`.

### 1.4 Add an `observation_latest` view per patient per LOINC
**Why:** "What's this patient's most recent A1c?" is the single most asked pre-op question. The current `observation` view has every reading; answering the latest-per-patient question is a 10-line SQL window function that Claude will write every time.

**What:**
- Either: a materialized `observation_latest` table (patient × loinc × value × date), populated after `observation` is built.
- Or: a SQLite VIEW created alongside the tables: `CREATE VIEW observation_latest AS SELECT ... ROW_NUMBER() OVER (PARTITION BY patient_ref, loinc_code ORDER BY effective_date DESC) AS rn FROM observation WHERE rn = 1`.
- Start with the SQLite VIEW (cheaper). Promote to materialized table only if the NL search surface is slow.

---

## Phase 2 — The NL search demo (2–3 days)

### 2.1 Agent-mode "cohort builder" chat
**Why:** This is the killer demo for EHI Ignite. No other submission will have it.

**What:**
- React `CohortBuilder.tsx` page at `/explorer/cohort`.
- Chat UI where the clinician types "patients on Warfarin with a recent INR > 3" → Claude emits SQL → backend runs it → frontend renders the result as a sortable table with patient links.
- Every row is clickable into `/patient/:id` (the existing journey view).
- Streaming: tokens stream, then the SQL appears, then the result table appears. Three-stage progressive disclosure.

### 2.2 Citation format: row-level, not text-level
**Why:** The generic "cite your sources" approach is hand-wavy. Rows from SQLite are already addressable.

**What:**
- Every time Claude cites a fact ("this patient had a stroke in 2019"), the tool-call response includes `source: {table: "condition", id: "<id>"}`.
- Frontend renders citations as hoverable badges linked to the source row.
- Makes the "evidence-backed Q&A" story concrete and verifiable.

### 2.3 Query result cache
**Why:** Clinicians re-ask the same questions. LLM cost matters. Second run should be instant.

**What:**
- Hash the SQL query → store result JSON in `data/sof_query_cache.db` keyed by (query_hash, corpus_mtime).
- Invalidate when the corpus rebuilds.

---

## Phase 3 — Platform moves (≤1 week, post-submission)

### 3.1 Expose SQL-on-FHIR as an MCP server
**Why:** This is the "own the substrate" play from the Ep 19 synthesis. HealthSamurai's Aidbox already does this; we'd be one of the first to do it in open source.

**What:**
- `api/mcp/sof_server.py` — an MCP server exposing `run_sql`, `list_tables`, `describe_view`.
- Any MCP client (Claude Desktop, Zed, the `claude` CLI) can now query a FHIR corpus as if it were a database.
- Ships as a standalone submodule so it can be adopted outside our repo.
- **This is the artifact that turns "prototype" into "platform".**

### 3.2 Swap SQLite → DuckDB
**Why:** DuckDB has a first-class FHIR extension, columnar aggregation, and will make the perf argument flip once corpora get bigger. Plan for it before we hit the ceiling.

**What:**
- `sqlite_sink.py` → `duckdb_sink.py` with the same `materialize_all()` API.
- Benchmark at n=1,000 and n=5,000 patients. Re-run `research/SQL-ON-FHIR-REVIEW.md` tables.
- Keep SQLite as the default for zero-install demos; DuckDB for the production-scale story.

### 3.3 Upgrade FHIRPath to a real library
**Why:** Our evaluator is a practical subset. As ViewDefinitions get richer (extensions, date math, `resolve()`), we'll hit the wall.

**What:**
- Vendor `fhirpathpy` (MIT) behind the existing `evaluate()` interface.
- Fallback path: keep our own evaluator as the "fast path" for expressions it can handle, delegate the rest.
- Run the SQL-on-FHIR v2 test suite (`tests/*.json` from the spec) as a conformance check in CI.

### 3.4 Bulk FHIR ingestion path (from Ep 16)
**Why:** The "flip the script" thesis only lands if we can actually ingest Bulk FHIR, not just individual bundles. CMS BCDA is a real, free Bulk FHIR server.

**What:**
- `api/ingest/bulk_fhir.py` — poll a Bulk FHIR `$export` endpoint, download the NDJSON files, feed them into `materialize_all()` in streaming mode.
- Demo against CMS BCDA sandbox (already in `data/synthea-samples/sample-bulk-fhir-datasets-10-patients/`).
- Completes the Ep 16 narrative in our submission.

### 3.5 Conformance / data-quality view
**Why:** Ep 19's Tuva FHIR Inferno thesis: the real value of SQL-on-FHIR is that it surfaces data quality problems you can't see in opaque bundles.

**What:**
- `views/data_quality.json` isn't a thing — data quality is a *query*, not a view. So:
- `research/data-quality-queries.sql` — 10 canonical DQ queries (null rate by column, duplicate IDs, orphaned references, malformed dates, codes without displays, etc.).
- Runs as part of the demo and produces a scorecard. Good pitch artifact.

---

## Phase 4 — Speculative / research-grade

### 4.1 CQL → SQL transpilation experiment
**Why:** The other half of the Ep 19 thesis — Gene Geller's argument that LLMs can turn CQL libraries (HEDIS quality measures) into SQL-on-FHIR. We could be the first to demo this in anger.

**What:**
- Pick one real HEDIS measure (e.g. HEDIS-CBP, Controlling High Blood Pressure — simple, just BP readings).
- Feed its CQL definition to Claude with our ViewDefinition schemas and ask for equivalent SQL.
- Verify the answer matches a hand-written version.
- Ship as `research/cql-to-sql-experiment.md`.

### 4.2 ViewDefinition generator from a natural-language schema
**Why:** Writing ViewDefinition JSON by hand is tedious. The LLM can do it.

**What:**
- "Generate a ViewDefinition for US Core Immunization that flattens vaccineCode and reaction" → Claude emits JSON → we validate it against our runner → commit.
- Closes the loop: LLMs both author and query the view layer.

### 4.3 Cross-patient temporal reasoning
**Why:** The most interesting pre-op questions are temporal: "Has this patient EVER been on a DOAC? When did they stop? Did they restart?" The current schema has dates but no temporal algebra.

**What:**
- Start with a `medication_timeline` materialized table keyed by (patient_ref, rxnorm_code, start, end, gap_from_previous).
- Expose `SELECT ... FROM medication_timeline WHERE patient_ref = ?` as the backing store for the Gantt chart view.
- Lines up with the eventual `api/core/temporal.py` work already planned in CLAUDE.md.

---

## How to prioritize

If we only do one thing: **0.1 (wire `run_sql` into the agent)**. That's the demo nobody else has.

If we only do three: 0.1 + 1.1 (drug_class bridge) + 2.1 (cohort builder UI).

If we have a week: add 0.2, 0.3, 2.2, 3.1 (MCP server).

Everything in Phase 3+ is post-submission work that strengthens the platform story but isn't required for Phase 1 of the EHI Ignite competition (wireframes + concept, May 13).

---

## Open questions

1. **One DB or per-patient DBs?** A single corpus DB is simpler but mixes patients. Per-patient DBs align with the UI's single-patient focus but fragment cohort queries. **Lean:** one DB, partition by `patient_ref` in queries.
2. **Do we ship the CQL experiment or skip it?** It's the flashiest research story but has the highest failure risk. **Lean:** yes, but as a contained `research/` writeup, not as a dependency.
3. **MCP server as a separate repo or submodule?** Separate repo maximizes reuse and the "open substrate" narrative but splits attention. **Lean:** submodule for the submission, spin out post-deadline.
4. **Who is the demo clinician?** Max Gibber (neurosurgeon) is the prototype user. The cohort builder demo needs a neurosurgery-specific question to land. **TODO:** pick the hero query before building the UI.

---

*Status: prototype ships, phase 0 not started.*
