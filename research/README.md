# Research

Supporting research materials for the EHI Ignite Challenge.

## Pitch snapshot (`ehi-ignite.db`)

A frozen, 200-patient SQL-on-FHIR SQLite warehouse built from the
Synthea individual bundles at
`data/synthea-samples/synthea-r4-individual/fhir/`. This is the
**canonical reviewer / pitch dataset** — it's small enough to commit
(≈ 12 MB) but large enough to show real distributions in the pitch
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
| `condition_active`   |     674 | same columns as `condition`, filtered to clinically-active rows ◊                             |
| `medication_request` |   1,948 | `id, patient_ref, authored_on, medication_text, rxnorm_code, rxnorm_display, drug_class` †    |
| `medication_episode` |     820 | `episode_id, patient_ref, display, drug_class, start_date, end_date, is_active, …` ‡          |
| `observation`        |  40,476 | `id, patient_ref, loinc_code, display, effective_date, value_quantity, value_unit`            |
| `observation_latest` |   5,546 | same columns as `observation`, latest row per `(patient_ref, loinc_code)` §                   |
| `encounter`          |   6,714 | `id, patient_ref, class_code, type_text, period_start, period_end`                            |

† `drug_class` is an **enriched** column (P1.1) — not in the raw FHIR.
Populated at ingest time by `patient-journey/core/sql_on_fhir/enrich.py`
using the shared `patient-journey/data/drug_classes.json` mapping.
Values: one of `anticoagulants`, `antiplatelets`, `ace_inhibitors`,
`arbs`, `jak_inhibitors`, `immunosuppressants`, `nsaids`, `opioids`,
`anticonvulsants`, `psych_medications`, `stimulants`,
`diabetes_medications`, or `NULL` when nothing matched. Use
`GROUP BY drug_class` for surgical-risk cohort queries.

‡ `medication_episode` is a **derived table** (P1.2) — not a
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

◊ `condition_active` is a **filtered subset view** (P1.3) — same
column shape as `condition`, but a view-level `where` clause drops
every row whose `clinicalStatus` isn't `active`, `recurrence`, or
`relapse`. Use it as a clinician-style "problem list"; fall back to
the full `condition` table for history. In this snapshot: 674 active
rows out of 1,410 total.

§ `observation_latest` is a **derived SQLite view** (P1.4) — not a
stored table. Built lazily from `observation` via a
`ROW_NUMBER() OVER (PARTITION BY patient_ref, loinc_code ORDER BY
effective_date DESC, id DESC)` projection. Always fresh: any new
`observation` row is visible on the next `SELECT` with no rebuild.
Use it whenever the question is "what's the patient's current A1c /
creatinine / blood pressure" so you don't have to write
`ORDER BY … LIMIT 1` by hand. In this snapshot: 5,546 rows =
5,546 distinct `(patient_ref, loinc_code)` pairs.

Schema matches the six ViewDefinitions under
`patient-journey/core/sql_on_fhir/views/` (five pure + one filtered
subset), plus the `drug_class` enrichment column declared in
`enrich.py`, plus the two derived artifacts declared in `derived.py`:
the materialized `medication_episode` table and the lazy
`observation_latest` view. See
`patient-journey/core/sql_on_fhir/views/README.md` for the full
four-layer architecture breakdown. Use `run_sql` on
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
