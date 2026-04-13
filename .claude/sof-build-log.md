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

---

## Phase 1 — Clinically smart tables

_(no entries yet)_

---

## Phase 2 — NL search demo

_(no entries yet)_
