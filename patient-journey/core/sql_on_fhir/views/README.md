# SQL-on-FHIR views

This directory holds the canonical ViewDefinition JSON files that the
SOF runtime materializes into `data/sof.db` (production) and
`research/ehi-ignite.db` (pitch snapshot). It's the source of truth
for the warehouse's table shape.

There are **three** kinds of tables in the warehouse. Knowing which
kind you're looking at explains why a column exists — and where to go
to change it.

---

## 1. Pure ViewDefinition tables

> "What a standards-compliant SQL-on-FHIR runtime would produce."

These are driven entirely by the JSON files in this directory. Every
column is reachable from a FHIRPath-lite expression against the raw
FHIR resource. A separate SQL-on-FHIR runtime (DuckDB, Pathling, the
reference implementation) could consume these same JSON files and
produce the same columns.

| Table                | Source file              | Resource         |
|----------------------|--------------------------|------------------|
| `patient`            | `patient.json`           | Patient          |
| `condition`          | `condition.json`         | Condition        |
| `medication_request` | `medication_request.json`| MedicationRequest|
| `observation`        | `observation.json`       | Observation      |
| `encounter`          | `encounter.json`         | Encounter        |

**To change a column:** edit the JSON, bump the snapshot, done. No
Python changes needed.

---

## 2. Enriched columns on pure tables

> "Clinically-smart columns that FHIRPath can't express."

Some columns — like `drug_class` on `medication_request` — require
logic that FHIRPath-lite has no way to express (RxNorm code lookups,
keyword classification, severity scoring). Rather than shoehorn them
into the JSON, they're spliced onto the row dict in Python *after*
the runtime evaluates the ViewDefinition but *before* the row hits
SQLite.

This happens in `patient-journey/core/sql_on_fhir/enrich.py`. Each
`Enrichment` binds a view name to:

1. A list of extra `Column` definitions (which the sink appends to
   the `CREATE TABLE` statement).
2. A `enrich_row(row)` callable that mutates the row in place.

**Default-on.** Every warehouse built by `materialize_all` carries
the enrichment columns by default. Pass `enrichments={}` to
`materialize_all` if you need a pure ViewDefinition build for
validation against another runtime.

| Table                | Enrichment column | Module              |
|----------------------|-------------------|---------------------|
| `medication_request` | `drug_class`      | `enrich.py` (P1.1)  |

**To add an enrichment column:** add an entry to
`enrich.default_enrichments()` and extend the enrichment's
`enrich_row` callable. The sink picks it up automatically on the next
rebuild.

---

## 3. Derived tables

> "New tables built by aggregating rows across one or more existing
> tables."

Some clinical abstractions aren't a column at all — they're a whole
new row shape. A *medication episode*, for example, is built by
grouping many `medication_request` rows for the same drug into a
single continuous treatment span with a start date, end date, and
status. That's a table, not a column.

Derived tables are declared in
`patient-journey/core/sql_on_fhir/derived.py`. Each `Derivation` has:

1. A `table_name` (what to create).
2. A list of `depends_on` source tables.
3. A `build(conn)` callable that `SELECT`s from those sources and
   writes to the new table, returning the row count.

The sink runs every derivation *after* every view has been
materialized, in a second pass. Derivations whose dependencies
weren't part of the current run are silently skipped.

**Default-on.** Every warehouse carries the derived tables by
default. Pass `derivations={}` to `materialize_all` to skip them.

| Derived table        | Depends on           | Module                |
|----------------------|----------------------|-----------------------|
| `medication_episode` | `medication_request` | `derived.py` (P1.2)   |

### `medication_episode` schema

| Column             | Type    | Notes                                                   |
|--------------------|---------|---------------------------------------------------------|
| `episode_id`       | TEXT PK | `{patient_ref}::{normalized_display}`                  |
| `patient_ref`      | TEXT    | Same value as `medication_request.patient_ref`          |
| `display`          | TEXT    | Representative drug display (earliest-seen)             |
| `rxnorm_code`      | TEXT    | First non-null RxNorm code in the episode               |
| `drug_class`       | TEXT    | First non-null class from the enrichment pass           |
| `latest_status`    | TEXT    | Status of the most recent request                       |
| `is_active`        | INTEGER | `1` if `latest_status` in (`active`, `on-hold`)         |
| `start_date`       | TEXT    | Min `authored_on` in the group                          |
| `end_date`         | TEXT    | Max `authored_on`, or `NULL` if the episode is active   |
| `request_count`    | INTEGER | How many `medication_request` rows rolled up            |
| `duration_days`    | REAL    | `(end - start)` in days, or `NULL` when active          |
| `first_request_id` | TEXT    | `id` of the earliest `medication_request` in the group  |

Grouping key mirrors `core/episode_detector.detect_medication_episodes`:
lower-cased, stripped display name. Active-status logic is shared with
the safety panel so the warehouse and the clinician UI never disagree
about "is this patient still on X".

**To add a derived table:** add an entry to
`derived.default_derivations()`. The sink picks it up automatically
on the next rebuild. Document the schema here and flag it in the
build log.

---

## Rebuilding the warehouse

```bash
# Dev: data/sof.db (gitignored, auto-built on API boot)
uv run python -c "from api.core.sof_materialize import materialize_from_env; print(materialize_from_env())"

# Pitch snapshot: research/ehi-ignite.db (committed, 200 patients)
rm -f research/ehi-ignite.db
SOF_DB_PATH=research/ehi-ignite.db SOF_PATIENT_LIMIT=200 \
  uv run python -c "from api.core.sof_materialize import materialize_from_env; print(materialize_from_env())"
```

Every rebuild runs all three layers — pure views, enrichments,
derivations — so what you see in SQL is exactly what the LLM tool
(`api/core/sof_tools.run_sql`) sees at query time.
