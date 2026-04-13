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

_(no entries yet — P0.1 not started)_

---

## Phase 1 — Clinically smart tables

_(no entries yet)_

---

## Phase 2 — NL search demo

_(no entries yet)_
