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

| Table                | Rows    | Key columns                                                                                   |
|----------------------|---------|-----------------------------------------------------------------------------------------------|
| `patient`            |     200 | `id, gender, birth_date, family_name, given_name, deceased`                                   |
| `condition`          |   1,410 | `id, patient_ref, onset_date, display, code_system, code`                                     |
| `medication_request` |   1,948 | `id, patient_ref, authored_on, medication_text, rxnorm_code, rxnorm_display, drug_class` †    |
| `medication_episode` |     820 | `episode_id, patient_ref, display, drug_class, start_date, end_date, is_active, …` ‡          |
| `observation`        |  40,476 | `id, patient_ref, loinc_code, display, effective_date, value_quantity, value_unit`            |
| `encounter`          |   6,714 | `id, patient_ref, class_code, type_text, period_start, period_end`                            |

† `drug_class` is an **enriched** column (P1.1) — not in the raw FHIR.
Populated at ingest time by `patient-journey/core/sql_on_fhir/enrich.py`
using the shared `patient-journey/data/drug_classes.json` mapping.
Values: one of `anticoagulants`, `antiplatelets`, `ace_inhibitors`,
`arbs`, `jak_inhibitors`, `immunosuppressants`, `nsaids`, `opioids`,
`anticonvulsants`, `psych_medications`, `stimulants`,
`diabetes_medications`, or `NULL` when nothing matched. Use
`GROUP BY drug_class` for surgical-risk cohort queries.

‡ `medication_episode` is a **derived** table (P1.2) — not a
ViewDefinition projection. Built after the pure views by
`patient-journey/core/sql_on_fhir/derived.py`, which groups every
`medication_request` row per `(patient_ref, normalized display)` pair
and collapses each group into one episode with
`start_date`, `end_date`, `is_active` (1 if `latest_status` is
`active` or `on-hold`), `request_count`, `duration_days`, and the
`drug_class` carried forward from the enrichment pass. Use
`medication_episode` — not raw `medication_request` — whenever the
question is about treatment duration or "who is currently on X".
In this snapshot: 820 episodes, 308 active, 512 completed; four
active anticoagulant episodes make a small but real surgical-risk
cohort for the pitch demo.

Schema matches the five ViewDefinitions under
`patient-journey/core/sql_on_fhir/views/`, plus the `drug_class`
enrichment column declared in `enrich.py`, plus the derived
`medication_episode` table declared in `derived.py`. See
`patient-journey/core/sql_on_fhir/views/README.md` for the full
pure / enriched / derived architecture breakdown. Use `run_sql` on
the provider assistant agent — or plain `sqlite3 research/ehi-ignite.db`
— to query it.

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
