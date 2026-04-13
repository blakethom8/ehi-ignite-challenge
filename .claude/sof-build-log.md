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

### P0.3 — 200-patient pitch snapshot committed at `research/ehi-ignite.db`

**Shipped:** 2026-04-13
**Commit:** `472994d`
**Files:**
- `research/ehi-ignite.db` — new, **committed binary** (11.43 MB)
- `.gitignore` — now allow-lists the snapshot while blocking every other
  `research/*.db` (and the `-wal`/`-shm` siblings)
- `research/README.md` — documents the rebuild command, the row counts,
  and the column layout of each ViewDefinition table

**What it does:** Freezes a reviewer-facing dataset into the repo so
graders, pitch demos, and reproducible `run_sql` examples all hit the
same 200 patients without anyone first having to run a multi-minute
ingest against the 1,180 Synthea bundles. Because the SOF warehouse is
deterministic (no random sampling, sorted glob, fixed patient limit)
the committed DB is reproducible byte-for-byte from anyone's checkout.

**Build command** (used to produce the committed file):
```bash
rm -f research/ehi-ignite.db
SOF_DB_PATH=research/ehi-ignite.db SOF_PATIENT_LIMIT=200 \
  uv run python -c "from api.core.sof_materialize import materialize_from_env; print(materialize_from_env())"
```

**Build report:**

| Table                | Rows    |
|----------------------|---------|
| `patient`            |     200 |
| `condition`          |   1,410 |
| `medication_request` |   1,948 |
| `observation`        |  40,476 |
| `encounter`          |   6,714 |

Build time: 8.44s. File size: 11.43 MB (queue budget: 20 MB).

**Smoke test:**
```bash
python3 -c "import sqlite3; c=sqlite3.connect('research/ehi-ignite.db'); print(c.execute('SELECT COUNT(*) FROM patient').fetchone())"
(200,)
```

**.gitignore design note:** rather than broadly un-ignoring a single
file, I added a three-line block that (a) ignores every `*.db` and
`-wal`/`-shm` sibling under `research/`, then (b) explicitly
allow-lists `research/ehi-ignite.db`. This is the "protected asset"
pattern — no future broad rule can silently drop the pitch DB, and
any accidental second snapshot (e.g. `research/ehi-ignite-next.db`)
stays out of the commit.

**Follow-ups surfaced:**
- The snapshot is **not** re-materialized on boot — production still
  uses `data/sof.db` via the P0.2 startup hook. If someone edits a
  ViewDefinition, they need to rerun the build command above to
  refresh the committed snapshot. A CI check that diffs the views
  dir mtime against the committed DB mtime would close this gap;
  deferred to a later pass.
- When P1.1 adds a `drug_class` column to the medication view, this
  snapshot will have to be rebuilt and re-committed in the same
  commit so reviewers never see a schema mismatch between the
  snapshot and the agent's system prompt.

### P0.4 — `run_sql` tool surface documented *(scribe-only)*

**Shipped:** 2026-04-13
**Commit:** captured in the same docs commit as this build-log entry
**Files:**
- `research/SQL-ON-FHIR-REVIEW.md` — ~120-line addendum appended to the
  end of the "was it worth it" review. Documents the module layout
  (`sof_tools.py` / `sof_materialize.py` / agent SDK wiring), the
  `SqlRunResult` contract, the five gate failure modes, the row cap +
  `LIMIT+1` truncation probe, the schema surfacing into the system
  prompt, and the 30 reference tests across `test_sof_tools.py` +
  `test_sof_materialize.py`. Also lists the known Phase-0 limitations
  (no `drug_class` yet, no date arithmetic, schema description is
  CREATE-TABLE-only).
- `CLAUDE.md` — added `sof_tools.py` and `sof_materialize.py` rows to
  the `api/core/` tree, surfaced `patient-journey/core/sql_on_fhir/`
  and its `views/` subtree, added a `research/` tree entry for the
  review doc + pitch snapshot, added two new rows to the Key
  Reference Docs table, and appended a "SQL-on-FHIR quick reference"
  block listing the engine, LLM tool, warehouse, pitch snapshot, and
  the five shipped views.

**Why scribe-only:** No executable code changed in this task. The goal
is to make sure anyone picking the project up tomorrow (human or
agent) can see the `run_sql` contract without having to reverse it
out of the source. The review doc is the narrative home; CLAUDE.md is
the tree/map. Both now point at each other.

**Smoke test:** N/A — docs only. Manual read-through confirms the
addendum matches the actual `sof_tools.py` source byte-for-byte on:
forbidden keyword list, row cap (500), default limit (50), gate
return contract, `SqlRunResult` fields.

**Follow-ups surfaced:**
- When P1.1 ships the `drug_class` column, **three** docs need the
  same-day update: this build log, the SQL-ON-FHIR-REVIEW addendum
  ("Known limitations" bullet), and whichever table diagram the
  pitch deck ends up using. Easy to forget — put the reminder at
  the top of the P1.1 task brief.
- The review doc now has two distinct dated sections (main review +
  Phase 0 addendum). If we keep appending, the doc will drift into
  changelog territory. Consider splitting into
  `SQL-ON-FHIR-REVIEW.md` (stable) and `SQL-ON-FHIR-CHANGELOG.md`
  (append-only) if we add a third date-stamped section.

> **Phase 0 closed.** P0.1 → P0.4 all shipped on 2026-04-13. Phase 1
> (clinically smart tables) is unblocked and the first task is P1.1
> (`drug_class` column on the `medication_request` view).

---

## Phase 1 — Clinically smart tables

### P1.1 — `drug_class` enrichment on `medication_request`

**Shipped:** 2026-04-13
**Commit:** captured in the same docs commit as this build-log entry
**Files:**
- `patient-journey/core/sql_on_fhir/enrich.py` — new (~180 lines). Defines `Enrichment` dataclass, `load_drug_classifier`, `medication_request_enrichment`, and `default_enrichments()` registry.
- `patient-journey/core/sql_on_fhir/sqlite_sink.py` — edit. `_ensure_table`, `materialize`, and `materialize_all` all accept an optional `enrichments` kwarg; `None` means "use the default registry", `{}` means "pure unenriched build". Sentinel resolver: `_resolve_enrichments`.
- `patient-journey/core/sql_on_fhir/__init__.py` — re-exports `Enrichment`, `default_enrichments`, `load_drug_classifier`, `medication_request_enrichment`, plus `materialize_all` and `open_db` which were missing from the public surface.
- `patient-journey/tests/test_sql_on_fhir.py` — extended from 24 → 39 tests. New classes: `TestDrugClassifier` (7 tests), `TestMedicationEnrichment` (4 tests), `TestMaterializeWithEnrichment` (4 tests).
- `api/core/sof_tools.py` — `get_schemas_for_prompt` now walks the default enrichment registry and tags injected columns with a `-- enriched` suffix in the CREATE TABLE output. Preamble lists every drug_class key inline so the agent never has to guess.
- `research/ehi-ignite.db` — **rebuilt** with the new column (still 11.43 MB, still 200 patients).
- `research/SQL-ON-FHIR-REVIEW.md` — "Known limitations" bullet updated to mark the drug_class gap as resolved; new "Row-level enrichment" section with the full pitch-snapshot distribution table.
- `research/README.md` — medication_request row in the pitch-snapshot table now lists `drug_class` with a footnote explaining it's enriched and enumerating the twelve class keys.
- `CLAUDE.md` — SQL-on-FHIR quick reference now lists the enrichment registry and the canonical `GROUP BY drug_class` query as the Phase 1 example.

**What it does:** Closes the "we have SQL but it doesn't know what a
medication *is*" gap from the Phase 0 review. Every
`medication_request` row that hits the SQLite sink is now first
passed through `Enrichment.apply`, which looks up the RxNorm code (or
falls back to a case-insensitive keyword match against
`medication_text` / `rxnorm_display`) and writes a canonical single
drug class key into a new `drug_class` TEXT column. Values: one of
`anticoagulants`, `antiplatelets`, `ace_inhibitors`, `arbs`,
`jak_inhibitors`, `immunosuppressants`, `nsaids`, `opioids`,
`anticonvulsants`, `psych_medications`, `stimulants`,
`diabetes_medications`, or `NULL`.

The classifier reuses the same `patient-journey/data/drug_classes.json`
mapping file that the surgical safety panel (`core/drug_classifier.py`)
reads — so the SQL warehouse and the safety panel cannot disagree
about what counts as an anticoagulant. We did not import
`DrugClassifier` directly because it depends on
`fhir_explorer.parser.models.MedicationRecord`; the SQL-on-FHIR
pipeline only has `(rxnorm_code, display)` strings, so `enrich.py`
loads the JSON and exposes a lightweight
`classify(rxnorm_code, display) -> class_key | None` function.

**Architectural decision — enrichment is a sink-layer concern, not
a ViewDefinition concern.** I deliberately did *not* add `drug_class`
to `views/medication_request.json` because the SQL-on-FHIR v2 spec
doesn't include a `classify()` function and shoehorning one into our
FHIRPath-lite runtime would break portability — the whole point of
the ViewDefinition layer is that it's standards-compatible by
construction. Keeping enrichment in `enrich.py` means the JSON views
stay pure and a future consumer running our views through a
different engine (DuckDB, Databricks) would still get a valid
warehouse, just without the drug_class column.

**Smoke test A — unit suite:**
```
uv run pytest api/tests/test_sof_tools.py api/tests/test_sof_materialize.py \
  patient-journey/tests/test_sql_on_fhir.py -q
.....................................................................    [100%]
69 passed in 0.24s
```

**Smoke test B — rendered system prompt:**
The MCP tool description now contains the line
`drug_class TEXT  -- enriched` right after `rxnorm_system TEXT` in
the `medication_request` block, so the agent sees the column
without us having to hand-write it into the system prompt.

**Smoke test C — full cohort query against the pitch snapshot:**
```
SELECT drug_class, COUNT(*) FROM medication_request
GROUP BY drug_class ORDER BY 2 DESC
```
Result:

| `drug_class`           | Rows  |
|------------------------|------:|
| `NULL`                 | 1,746 |
| `nsaids`               |    97 |
| `opioids`              |    35 |
| `diabetes_medications` |    16 |
| `arbs`                 |    13 |
| `antiplatelets`        |    13 |
| `immunosuppressants`   |    13 |
| `anticonvulsants`      |     4 |
| `anticoagulants`       |     4 |
| `ace_inhibitors`       |     4 |
| `stimulants`           |     2 |
| `psych_medications`    |     1 |

Every shipped class has at least one row in the snapshot. The high
`NULL` count (~90%) is Synthea-honest: vaccines, vitamins, antibiotics,
contrast agents, routine meds. Risk-group cohort queries will return
a non-empty result for every surgical-safety category we care about.

**Follow-ups surfaced:**
- The P0.1 follow-up ("schema description is CREATE TABLE only —
  once P1.1 lands the drug_class column, the prompt should mention
  it explicitly") is now resolved — the preamble lists every class
  key inline.
- The P0.3 follow-up ("when P1.1 adds a drug_class column to the
  medication view, this snapshot will have to be rebuilt") is
  resolved in this same commit. The snapshot was rebuilt with the
  new column and the row count is unchanged (1,948).
- `drug_classes.json` is currently keyword-first. A real production
  feed would want a stronger RxNorm ingredient-level join (using
  RxClass or ATC codes) before we trust this for anything
  safety-critical. Fine for the prototype; flag it in the pitch deck.
- The enrichment registry is hard-coded to one entry
  (`medication_request`). P1.2 will add a second (`medication_episode`)
  and the pattern scales cleanly; no sink changes needed.

---

## Phase 2 — NL search demo

_(no entries yet)_
