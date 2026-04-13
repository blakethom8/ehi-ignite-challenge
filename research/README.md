# Research

Supporting research materials for the EHI Ignite Challenge.

## Pitch snapshot (`ehi-ignite.db`)

A frozen, 200-patient SQL-on-FHIR SQLite warehouse built from the
Synthea individual bundles at
`data/synthea-samples/synthea-r4-individual/fhir/`. This is the
**canonical reviewer / pitch dataset** — it's small enough to commit
(≈ 11 MB) but large enough to show real distributions in the pitch
charts. Reviewers and graders can reproduce every `run_sql` example in
the submission against this exact file.

Built with:

```bash
rm -f research/ehi-ignite.db
SOF_DB_PATH=research/ehi-ignite.db SOF_PATIENT_LIMIT=200 \
  uv run python -c "from api.core.sof_materialize import materialize_from_env; print(materialize_from_env())"
```

| Table               | Rows    | Key columns                                                                                   |
|---------------------|---------|-----------------------------------------------------------------------------------------------|
| `patient`           |     200 | `id, gender, birth_date, family_name, given_name, deceased`                                   |
| `condition`         |   1,410 | `id, patient_ref, onset_date, display, code_system, code`                                     |
| `medication_request`|   1,948 | `id, patient_ref, authored_on, medication_text, rxnorm_code, rxnorm_display, drug_class` †    |
| `observation`       |  40,476 | `id, patient_ref, loinc_code, display, effective_date, value_quantity, value_unit`            |
| `encounter`         |   6,714 | `id, patient_ref, class_code, type_text, period_start, period_end`                            |

† `drug_class` is an **enriched** column (P1.1) — not in the raw FHIR.
Populated at ingest time by `patient-journey/core/sql_on_fhir/enrich.py`
using the shared `patient-journey/data/drug_classes.json` mapping.
Values: one of `anticoagulants`, `antiplatelets`, `ace_inhibitors`,
`arbs`, `jak_inhibitors`, `immunosuppressants`, `nsaids`, `opioids`,
`anticonvulsants`, `psych_medications`, `stimulants`,
`diabetes_medications`, or `NULL` when nothing matched. Use
`GROUP BY drug_class` for surgical-risk cohort queries.

Schema matches the five ViewDefinitions under
`patient-journey/core/sql_on_fhir/views/` plus the enrichment columns
declared in `enrich.py`. Use `run_sql` on the provider assistant agent
— or plain `sqlite3 research/ehi-ignite.db` — to query it.

Regenerate whenever a ViewDefinition changes. The snapshot is
intentionally **not** materialized at API boot: production uses
`data/sof.db` (gitignored) via the startup hook in `api/main.py`.

Every other `*.db` under `research/` is gitignored; only this one
specific file is allow-listed. See the bottom of `.gitignore`.

## Transcripts (`transcripts/`)

Podcast transcripts generated via OpenAI Whisper API from YouTube audio.

| File | Episode | Guest(s) | Topic |
|------|---------|----------|-------|
| `out-of-the-fhir-ep19-aaron-neiderhiser-phil-ballentine.txt` | Ep 19 | Aaron Neiderhiser (Tuva), Phil Ballentine (Atropos Health) | FHIR, analytics, democratizing healthcare data |
| `out-of-the-fhir-ep16-mark-scrimshire-blue-button-bulk-fhir.txt` | Ep 16 | Mark Scrimshire (ONIX Health) | Blue Button, Bulk FHIR, payer interoperability |

Source: [Out of the FHIR Podcast](https://www.youtube.com/@OutoftheFHIRPodcast)
