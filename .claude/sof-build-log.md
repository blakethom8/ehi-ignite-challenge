# SQL-on-FHIR Build Log

*Chronological record of every SQL-on-FHIR task that shipped. Appended by `sof-scribe` after each successful `sof-builder` run. Read top-to-bottom for the full history.*

---

## 2026-04-13 — Bootstrap

**Commits (pre-orchestrator, captured manually):**
- `319ed24` — SQL-on-FHIR v2 prototype + head-to-head review vs Python parser
- `29b7e89` — Next-steps roadmap

**What exists at the start of the orchestrator loop:**

| Component | Location | State |
|---|---|---|
| ViewDefinition dataclass | `patient-journey/core/sql_on_fhir/view_definition.py` | Ships with tests |
| FHIRPath-lite evaluator | `patient-journey/core/sql_on_fhir/fhirpath.py` | Subset: fields, `.first()`, `.where()`, booleans, `getReferenceKey` |
| Runner | `patient-journey/core/sql_on_fhir/runner.py` | `select` / `where` / `forEach` / `forEachOrNull` / `unionAll` |
| SQLite sink | `patient-journey/core/sql_on_fhir/sqlite_sink.py` | Per-view + single-pass `materialize_all` |
| Views | `patient-journey/core/sql_on_fhir/views/*.json` | 5 views: patient, condition, medication_request, observation, encounter |
| Demo script | `patient-journey/core/sql_on_fhir/demo.py` | Loads N bundles, runs 6 example queries |
| Benchmark | `patient-journey/core/sql_on_fhir/benchmark.py` | Head-to-head vs `fhir_explorer.parser` |
| Tests | `patient-journey/tests/test_sql_on_fhir.py` | 24 passing |
| Review | `research/SQL-ON-FHIR-REVIEW.md` | Qualitative verdict |
| Next steps | `research/SQL-ON-FHIR-NEXT-STEPS.md` | Phased roadmap |
| Benchmark outputs | `research/sof-bench-{50,300}.md` | Raw numbers |

**Known verdict (carried forward):** keep both layers — Python parser owns the UI read path, SQL-on-FHIR owns corpus analytics + LLM tool surface.

---

## Phase 0 — Lock the prototype in

### P0.1 — `run_sql` MCP tool on the provider assistant agent

**Shipped:** 2026-04-13
**Commit:** `cf0efaa`
**Files:**
- `api/core/sof_tools.py` — new SELECT-only gate + read-only sqlite runner + schema renderer
- `api/tests/test_sof_tools.py` — new, 22 unit tests covering gate, runner, schema
- `api/core/provider_assistant_agent_sdk.py` — registers `mcp__fhir_chart__run_sql` and traces it as a TOOL span

**What it does:** Gives the Claude Agent SDK runtime a third MCP tool —
`run_sql(query, limit)` — that executes read-only SELECT/WITH statements
against `data/sof.db` (the SQL-on-FHIR warehouse). The gate strips string
literals + comments before tokenizing so quoted values like `'drop'` are
legal, but any DDL/DML keyword (DROP, INSERT, UPDATE, DELETE, ATTACH,
PRAGMA, CREATE, ALTER, REPLACE, TRUNCATE, VACUUM, REINDEX, ANALYZE) is
rejected and multi-statement input is blocked. Results are capped at 500
rows; when the caller omits a LIMIT we inject `LIMIT limit+1` so we can
return a `truncated` flag without a second query. The tool description
embeds CREATE TABLE statements for all five bundled ViewDefinitions so
the agent can self-serve joins (Synthea's `urn:uuid:` reference convention
is called out in the preamble).

**Smoke test:**
```
uv run pytest api/tests/test_sof_tools.py -q
......................                                                   [100%]
22 passed in 0.04s
```

**Follow-ups surfaced:**
- `run_sql` assumes `data/sof.db` exists. P0.2 (FastAPI startup hook) is the follow-up that materializes it on boot.
- Schema description today is CREATE TABLE only — once P1.1 lands the `drug_class` column, the prompt should mention it explicitly so the agent knows to group by it.

### P0.2 — FastAPI startup hook materializes `data/sof.db` with an mtime gate

**Shipped:** 2026-04-13
**Commit:** `0edbd8b`
**Files:**
- `api/core/sof_materialize.py` — new, idempotent rebuild helper
- `api/tests/test_sof_materialize.py` — new, 8 unit tests
- `api/main.py` — registers the `@app.on_event("startup")` hook
- `.gitignore` — excludes `data/sof.db`, `sof.db-wal`, `sof.db-shm`, `sof.db.tmp`

**What it does:** When the FastAPI app boots, it calls
`materialize_from_env()`, which compares the SOF SQLite DB's mtime
against (a) the ViewDefinitions in
`patient-journey/core/sql_on_fhir/views/*.json` and (b) the Synthea
bundle directory's own mtime. If anything upstream is newer, the helper
runs the ingest into `data/sof.db.tmp` and atomically renames it over
`data/sof.db` — a crashed build never leaves a half-populated warehouse
behind. If nothing moved the helper returns a `built=False` report and
the boot is effectively free.

The hook is fully env-driven so tests and prod share the same code
path:

| Var                    | Default                                           | Purpose                       |
|------------------------|---------------------------------------------------|-------------------------------|
| `SOF_AUTO_MATERIALIZE` | `1`                                               | set to `0` to skip entirely   |
| `SOF_DB_PATH`          | `data/sof.db`                                     | target warehouse path         |
| `SOF_FHIR_DIR`         | `data/synthea-samples/synthea-r4-individual/fhir` | source bundle directory       |
| `SOF_PATIENT_LIMIT`    | `200`                                             | cap on patients ingested      |

`materialize_from_env` catches every exception and logs a warning so a
broken warehouse can never take the API offline — the underlying
`materialize_if_stale` still raises on disk errors for the unit tests
to assert on.

**Smoke test A — unit suite:**
```
uv run pytest api/tests/test_sof_materialize.py -q
........                                                                 [100%]
8 passed in 0.11s
```
Tests cover: builds when DB missing, idempotent second call, rebuild
when FHIR dir mtime moves forward, all five tables present after build,
raises on missing FHIR dir, env-driven path builds correctly,
`SOF_AUTO_MATERIALIZE=0` skips cleanly, exceptions swallowed.

**Smoke test B — end-to-end boot:**
```
rm -f data/sof.db
SOF_PATIENT_LIMIT=50 uv run python -c "… trigger @app.on_event(startup) …"
row_counts: {'patient': 50, 'condition': 303, 'medication_request': 320,
             'observation': 9089, 'encounter': 1394}
OK
```
Second boot on the same DB: `pre-boot mtime == post-boot mtime` — the
mtime gate is working, no rewrite occurred.

**Follow-ups surfaced:**
- Pre-existing breakage: `api/tests/test_assistant_api.py` fails at
  collection time with `ModuleNotFoundError: No module named 'fastapi'`.
  Confirmed this is a pre-existing environment issue (reproduces on
  `aa8bfa9`, the parent commit). Not in scope for P0.2.
- The startup hook still uses `@app.on_event("startup")`, which is
  deprecated in newer FastAPI. Keep it for now; migrate to `lifespan`
  when we touch `api/main.py` next.
- `SOF_PATIENT_LIMIT=200` is the default, which means a cold-start boot
  ingests ~200 patients worth of resources (~20–40k rows) on the first
  request. Acceptable for dev; P0.3 will ship a pre-built 200-patient
  snapshot so deploys can skip the cold-start cost entirely.

---

## Phase 1 — Clinically smart tables

_(no entries yet)_

---

## Phase 2 — NL search demo

_(no entries yet)_
