# Session D01 — Josh's Data Catalog & Public Datasets

**Repos:** see `../SHAS-PINNED.md`. All four pinned at 2026-05-01.
**Files visited (count):** ~12 files for ground-truth on shapes
**Reading time estimate:** ~25 minutes
**Built on prior sessions:** Session 00 (lay of the land) — repo inventory; this session catalogs the *data*.

## What you'll learn

- **Every distinct data shape** that exists in Josh's stack — wire formats, in-memory snapshots, materialized stores, output bundles. Twelve shapes total, each documented with a pointer into the live code.
- **Which public datasets** Josh's stack consumes, ships, or implies — and which ones are *not* actually publicly available even though they look like they should be.
- **Per-application usage matrix** — which of the four apps touches which shapes, and what direction (read / write / pass-through).
- **The sharp nuances** between similar-looking datasets: Synthea-FHIR vs. real-EHR-FHIR vs. EHI-Export-derived-FHIR are *not* interchangeable. C-CDA is not a subset of FHIR. Vendor catalogs are derivative of CHPL but not equivalent.
- **A concrete seed plan** for `../../datamart/inputs/` — what to pull in, in what order, what's safe vs. what needs greenlighting.

## The code in scope (read for ground truth)

- `health-record-mcp/clientTypes.ts` — `ClientFullEHR` and `ClientProcessedAttachment` shape definitions
- `health-record-mcp/src/fhirSearchQueries.ts` — the canonical list of initial patient-scoped FHIR queries (29 base queries, not 44 as in older notes)
- `health-record-mcp/clientFhirUtils.ts:540–740` — fetch orchestrator + concurrency + reference-discovery loop
- `request-my-ehi/scripts/lookup-vendor.ts` — the `Vendor` interface (the consumer of `vendors.json`)
- `my-health-data-ehi-wip/schemas/ABN_FOLLOW_UP.json` — sample of Josh's per-table Epic schema shape
- `my-health-data-ehi-wip/schemas/_index.json` — empty (0 bytes); the schema set is the *files in the directory*, not an index file
- `my-health-data-ehi-wip/json/ACCOUNT.json` — sample of post-merge JSON-with-`$meta` shape
- `my-health-data-ehi-wip/tsv/ACCOUNT.tsv` — sample raw TSV (one of 550 tables)
- `my-health-data-ehi-wip/db.sqlite.dump` — head only (1.7 MB redacted Epic EHI dump)

## The 12 distinct data shapes in the stack

Numbered for cross-reference from the per-application matrix below. Each shape is documented with: where it lives in the code, what it looks like at the byte/JSON level, which app produces or consumes it.

### Shape 1 — FHIR R4 wire format (per-resource JSON over HTTPS)

The **input** to Josh's SMART pull. Returned by EHR FHIR servers in response to `GET {fhirBaseUrl}/{ResourceType}?patient={id}&...`. Shape is the FHIR R4 `Bundle` (`{ resourceType: "Bundle", entry: [{ resource: {...} }, ...] }`) for searches, or a single resource for direct reads.

**Where consumed:** `health-record-mcp/clientFhirUtils.ts:608` — every fetched body is examined for `resourceType === 'Bundle'` and entries are extracted.

**Sample shape (one entry):**

```json
{
  "resourceType": "Observation",
  "id": "lab-12345",
  "status": "final",
  "category": [{ "coding": [{ "system": "...", "code": "laboratory" }] }],
  "code":  { "coding": [{ "system": "http://loinc.org", "code": "718-7", "display": "Hemoglobin" }] },
  "subject": { "reference": "Patient/abc" },
  "effectiveDateTime": "2024-09-12T08:30:00Z",
  "valueQuantity": { "value": 13.4, "unit": "g/dL" }
}
```

**Nuance:** the wire format Josh actually receives differs subtly between Epic, athena, Cerner, etc. — every server has quirks (missing `subject`, non-standard extensions, paging cursor formats). Josh's fetcher doesn't normalize — it stores what comes in.

### Shape 2 — `ClientFullEHR` (in-memory per-patient snapshot)

The **canonical in-memory output** of Josh's FHIR fetch path. Defined precisely in `clientTypes.ts:23–33`:

```ts
interface ClientFullEHR {
  fhir: Record<string, any[]>;       // resourceType → array of resources
  attachments: ClientProcessedAttachment[];
}

interface ClientProcessedAttachment {
  resourceType: string;
  resourceId: string;
  path: string;                       // dotted path to the attachment node
  contentType: string;
  json: string;                       // JSON of the original attachment node
  contentBase64: string | null;       // raw bytes
  contentPlaintext: string | null;    // best-effort plaintext lift
}
```

**Where produced:** `health-record-mcp/clientFhirUtils.ts:542` `fetchAllEhrDataClientSideParallel()`.
**Where consumed:** by everything downstream — `tools.ts` (MCP), the SQLite materializer, the plaintext renderer, the redaction studio (in `health-skillz`, with the same shape). This is **the single most important shape in the stack**.

**Nuance:** `fhir` values are typed `any[]` — there is no FHIR profile validation. Josh trusts the wire format. `attachments` *can* be null bytes (`contentBase64: null`) when an attachment failed to fetch but the reference was preserved.

### Shape 3 — Initial FHIR query plan (29 base queries)

Not data per se — but a *data-catalog claim*: the set of queries Josh runs to call the patient's record "fully fetched." Defined in `health-record-mcp/src/fhirSearchQueries.ts:16–46`:

| Resource type        | Variants                                                                                                              |
| -------------------- | --------------------------------------------------------------------------------------------------------------------- |
| `Observation`        | 7 category facets — `laboratory`, `vital-signs`, `social-history`, `sdoh`, `functional-status`, `disability-status`, `mental-health` |
| `Condition`          | one query                                                                                                              |
| `MedicationRequest`  | one query                                                                                                              |
| `AllergyIntolerance` | one query                                                                                                              |
| `Immunization`       | one query                                                                                                              |
| `Procedure`          | one query                                                                                                              |
| `DiagnosticReport`   | one query                                                                                                              |
| `DocumentReference`  | one query                                                                                                              |
| `CarePlan` / `CareTeam` / `Coverage` / `Device` / `Encounter` / `Goal` | one query each                                                                                                         |
| `MedicationDispense` / `MedicationStatement`                          | one each (alongside `MedicationRequest`)                                                                               |
| `QuestionnaireResponse` / `RelatedPerson` / `Specimen` / `ServiceRequest` | one each                                                                                                              |
| `Patient` / `Practitioner` / `Organization`                            | one each                                                                                                              |

**Total: 29 queries** (the often-cited "44 query slots" is from older code; current pinned SHA has 29). Plus a direct `Patient/{id}` fetch and *expanding-frontier discovery*: every fetched resource has its `reference` fields scraped; new references become next-batch fetch tasks. So actual fetches per patient typically run into the hundreds.

**Nuance:** Josh splits `Observation` by category but does NOT split `Condition` or `MedicationRequest` — those return everything. For Synthea data this is fine; for real Epic this can produce very large pages and his code does not paginate (he relies on default `_count` from the server, no explicit `_count` set — see line 661 commented out).

### Shape 4 — Flattened SQLite over FHIR (Josh's per-resource-type tables)

The **queryable** form. Josh ingests the `ClientFullEHR.fhir` map into `bun:sqlite` with one table per resource type, plus a small handful of extracted scalar columns and a JSON column carrying the full resource. This is what `query_record` SQLs against.

**Where produced:** `health-record-mcp/src/dbUtils.ts` (not yet read in detail; covered in D02).
**Where consumed:** `query_record` MCP tool, internal grep, and serialization back to disk for the Skill bundle.

**Sample shape (paraphrased — verify in D02):**

```sql
CREATE TABLE Observation (
  id TEXT PRIMARY KEY,
  patient_id TEXT,
  effective_date TEXT,
  category TEXT,
  code_system TEXT, code TEXT, code_display TEXT,
  value_text TEXT,
  resource_json TEXT  -- full FHIR resource as JSON
);
-- one such table per resource type in clientFullEhr.fhir
```

**Nuance:** this is *not* SQL-on-FHIR-v2 — Josh's own pragmatic schema, predates the IG. Useful for `query_record` but loses round-trip fidelity (extension fields not promoted to columns).

### Shape 5 — FHIR-to-plaintext rendering (per-resource-type narrative)

The **human-and-LLM-readable** form. `health-record-mcp/src/fhirToPlaintext.ts` (1513 lines) has a per-resource-type renderer that produces 1–N short text lines per resource. This is what `grep_record` searches over and what gets injected into agent context.

**Sample output (paraphrased):**

```
Observation: Hemoglobin (LOINC 718-7) | 13.4 g/dL | 2024-09-12 | final
Condition: Type 2 diabetes mellitus (E11.9) | active | onset 2019-03-04
MedicationRequest: Metformin 500mg | active | authored 2024-08-01 | reason: E11.9
```

**Nuance:** lossy by design — the renderer drops most of the FHIR structure (extensions, provenance, contained resources) in favor of one-line legibility. Atlas should *adopt the per-resource-type approach* but *diverge by emitting a structured fact + provenance edge* alongside the text.

### Shape 6 — Redaction profile (variant clusters + suggestion engine)

`health-skillz/src/client/lib/redaction.ts` defines a profile shape that maps over the FHIR snapshot to mark resources/fields as redactable. Variants are clustered (same drug name across multiple `MedicationRequest` entries gets one profile entry, applied N times). Profile is a separate JSON document Blake can serialize.

**Where produced:** the React redaction studio (covered in App lane A06).
**Where consumed:** the Skill-bundle assembler — applied as a final pass before bytes are written to `data/<provider>.json`.

**Nuance:** redaction is non-destructive in memory — the profile records *what to remove* but the original `ClientFullEHR` is preserved until bundle export. This is a deliberate UX: "preview redactions before committing."

### Shape 7 — Skill output bundle (`health-record-assistant/data/<provider>.json`)

The **on-disk-for-Claude** form. JSZip-assembled in-browser, contains `SKILL.md` + scripts + references + per-provider JSON file (one redacted `ClientFullEHR` per source). This is what gets uploaded to Claude as a Skill.

**Bundle layout (verified from `skill/build-skill.ts` + skill-builder docs):**

```
health-record-assistant/
├── SKILL.md                 ← concatenated from 9 ordered partials
├── references/              ← FHIR cookbook, analysis philosophy, etc.
├── scripts/                 ← Bun TS helpers Claude invokes
└── data/
    ├── kaiser-2024-09.json   ← one ClientFullEHR per portal connection
    ├── athena-2024-09.json
    └── ...
```

**Nuance:** *one provider per file*. Josh deliberately preserves source-level provenance by keeping these as separate files. **No merge.** This is the single most important architectural fact for Atlas to contrast against.

### Shape 8 — Vendor catalog (`vendors.json` + per-vendor analyses)

The **request-my-ehi consumes** shape. Hosted at `https://joshuamandel.com/ehi-export-analysis/data/vendors.json`. ~71 vendors in the `request-my-ehi` consumer, ~219 in the upstream `ehi-export-analysis` repo (different scopes).

**Per-vendor entry shape (verified from `request-my-ehi/scripts/lookup-vendor.ts:23`):**

```ts
interface Vendor {
  developer?: string;          // "athenahealth, Inc."
  product_name?: string;       // "athenaClinicals"
  family?: string;
  slug?: string;               // URL-safe key for the analyses/ subdir
  grade?: string;              // "A" / "B" / "C"
  coverage?: string;           // "comprehensive" / "partial"
  approach?: string;           // "native" / "standards_based" / "hybrid"
  export_formats?: string[];   // ["NDJSON", "HTML", "PDF"]
  entity_count?: number;       // 133
  field_count?: number;        // 6809
  ehi_documentation_url?: string;
  has_data_dictionary?: boolean;
  has_sample_data?: boolean;
  includes_billing?: boolean;
  patient_communications?: string;
  chpl_ids?: number[];         // foreign keys into ONC CHPL
  summary?: string;
}
```

**Companion files:** `joshuamandel.com/ehi-export-analysis/data/analyses/{slug}.md` — one Markdown deep-dive per vendor.

**Nuance:** this is **derived data**. The upstream source-of-truth is ONC's CHPL (Certified Health IT Product List). Josh's catalog adds editorial grading and per-vendor analysis prose that CHPL doesn't have.

### Shape 9 — Epic EHI raw TSV (`tsv/*.tsv`, ~550 tables)

The **input to Josh's Epic-EHI pipeline**. Tab-separated, one file per Epic physical table. First row is column headers (denormalized — display columns inlined, e.g. `ABN_FLUP_USER_ID` *and* `ABN_FLUP_USER_ID_NAME`).

**Sample header (verified `ACCOUNT.tsv`):**

```
ACCOUNT_ID  ACCOUNT_NAME  CONTACT_PERSON  BIRTHDATE  SEX  IS_ACTIVE  CITY  STATE_C_NAME  ZIP  HOME_PHONE  ...
```

**Sample row (verified, Josh's own redacted dump):**

```
1810018166  MANDEL,JOSHUA C  MANDEL,JOSHUA C  10/26/1982 12:00:00 AM  M  Y  MADISON  Wisconsin  REDACTED  617-894-1015  ...
```

**Nuance:** `_C_NAME` columns are **denormalized lookup-table joins** — Epic stores categorical values as integer codes in `_C` columns and maintains separate lookup tables, but the EHI Export serializes both the code and the human label as adjacent columns. This makes the export self-contained but bloats column counts. **This is a key fact for D04/D05.**

### Shape 10 — Per-table JSON schema (`schemas/*.json`, **6,631 files**)

Verified count: 6,631 files in `schemas/` (the `_index.json` is **0 bytes** — empty placeholder). Each file describes one column-set (logical or physical table). Sample:

```json
{
  "name": "ABN_FOLLOW_UP",
  "description": "This table stores the data related to the follow up done on an Advanced Beneficiary Notice (ABN).",
  "primaryKey": [{ "columnName": "NOTE_CSN_ID", "ordinalPosition": 1 }],
  "columns": [
    {
      "ordinalPosition": 9,
      "name": "ABN_FLUP_STATUS_C_NAME",
      "type": "VARCHAR",
      "discontinued": false,
      "description": "Stores the status of the Advance Beneficiary Notice (ABN) follow-up.",
      "entries": ["Not Started", "Provider Contacted", "Review Complete: ABN Resolved", ...]
    }
  ]
}
```

**Nuance:** schemas come with **inline enum values** (`entries`) for `_C_NAME` columns — that's the *Epic data dictionary embedded in the export*. Type info uses Epic's published types (`NUMERIC`, `VARCHAR`, `DATETIME`, `DATETIME (Local)`, `FLOAT`, `INTEGER`). Why **6,631** schemas for **550** TSVs? Some logical tables are split across multiple physical TSVs (the inverse of D05's merge problem) and some schemas describe view-layer or index-layer tables that don't have their own TSV file. Josh's `02-merge-related-tables.ts` figures this out.

### Shape 11 — Post-merge JSON (`json/*.json`, ~414 files, with `$meta`)

The **post-merge logical-table** form. Each file holds *both* the merged data and a copy of the schema(s) under `$meta.schemas`. Inspected `json/ACCOUNT_CONTACT.json` head (line 1–50):

```json
{
  "$meta": {
    "schemas": {
      "ACCOUNT_CONTACT": { "name": "...", "primaryKey": [...], "columns": [...] }
      // possibly multiple schemas if this logical table merged several physical tables
    }
  },
  "rows": [ ... ]   // (presumed; verify in D06)
}
```

**Nuance:** by carrying schema in every file, the post-merge artifacts are *self-describing*. An LLM reading one of these files doesn't need a sidecar schema fetch.

### Shape 12 — Materialized SQLite over Epic EHI (`db.sqlite.dump`, 1.7 MB)

The **final** form of Josh's Epic pipeline. SQL `.dump` text format. Inspected head:

```sql
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE MED_CVG_ESTIMATE_VALS ( -- This table holds information about values sent ...
```

**Nuance:** the dump *includes table comments* (the `-- ...` after each `CREATE TABLE`). That's Josh's table descriptions from Shape 10 round-tripped through SQLite. Useful for any downstream consumer that wants schema annotations as part of the SQL surface (e.g., LLM tool calling).

## Per-application data-usage matrix

Reading: rows are apps, columns are shapes. **R** = consumes, **W** = produces, **R/W** = round-trips, **·** = doesn't touch.

| App                       | 1 FHIR wire | 2 ClientFullEHR | 3 Query plan | 4 FHIR-SQLite | 5 Plaintext | 6 Redaction profile | 7 Skill bundle | 8 Vendor catalog | 9 EHI TSV | 10 Per-table schemas | 11 Post-merge JSON | 12 EHI SQLite |
| ------------------------- | ----------- | --------------- | ------------ | ------------- | ----------- | ------------------- | -------------- | ---------------- | --------- | -------------------- | ------------------ | ------------- |
| `request-my-ehi`          | ·           | ·               | ·            | ·             | ·           | ·                   | ·              | **R**            | ·         | ·                    | ·                  | ·             |
| `health-record-mcp`       | **R**       | **W**           | **R**        | **W**         | **W**       | ·                   | ·              | ·                | ·         | ·                    | ·                  | ·             |
| `health-skillz`           | **R**       | **W**           | **R** (refactored) | ·       | **W** (via fhir-guide.md partial) | **W** | **W**           | ·                | ·         | ·                    | ·                  | ·             |
| `my-health-data-ehi-wip`  | ·           | ·               | ·            | ·             | ·           | ·                   | ·              | ·                | **R**     | **R/W**              | **W**              | **W**         |

**Read this matrix as the answer to "where do data shapes overlap between apps?"** — they almost don't. The two FHIR-pull apps (`mcp` and `skillz`) share Shapes 1–7. The Epic-EHI app (`my-health-data-ehi-wip`) lives in a parallel universe, Shapes 9–12. `request-my-ehi` only consumes vendor metadata (Shape 8). **The four apps barely talk to each other on the data plane.** That's both an opportunity (Atlas can be the bridge) and a warning (the bridge is non-trivial — these are *different* data shapes, not different views of the same data).

## Public datasets (what's actually publicly available)

| Dataset                                          | What it is                                                                            | Format                       | Volume                         | License           | Where to get it                                                                       | Used by Josh's stack? |
| ------------------------------------------------ | ------------------------------------------------------------------------------------- | ---------------------------- | ------------------------------ | ----------------- | ------------------------------------------------------------------------------------- | --------------------- |
| **Synthea synthetic FHIR**                       | Generated synthetic patients, FHIR R4 bundles, complete (Conditions/Meds/Obs/Encs/Procs) | FHIR R4 JSON                 | 1,180 in repo (this repo)       | Apache-2.0        | Already at `data/synthea-samples/synthea-r4-individual/fhir/`                          | Indirectly (test only) |
| **`jmandel/sample_ccdas`**                       | 747 PHI-free CCDA fixtures from ~12 vendors (Allscripts, Cerner, NextGen, Greenway, …) | C-CDA XML                    | 747 docs                       | CC BY 4.0         | github.com/jmandel/sample_ccdas                                                       | No (parallel universe) |
| **`vendors.json` + analyses**                    | 71 EHR vendors with EHI-Export-specific metadata + per-vendor MD analyses             | JSON + Markdown              | ~30 KB JSON, ~1.5 MB MD        | unspecified       | joshuamandel.com/ehi-export-analysis/data/                                            | **Yes** — `request-my-ehi` |
| **`jmandel/ehi-export-analysis` raw**            | 219 vendor product abstractions, deeper than `vendors.json`                          | JSON in `abstraction/`       | 219 files                      | none (no LICENSE) | github.com/jmandel/ehi-export-analysis                                                | Indirectly (drives `vendors.json`) |
| **ONC CHPL (Certified Health IT Product List)**  | Authoritative US registry of certified EHR products + their certification criteria    | JSON via API + CSV downloads | thousands                      | Public domain     | chpl.healthit.gov                                                                     | Indirectly (Josh's `chpl_ids` field) |
| **Josh's redacted Epic EHI dump**                | His own real Epic EHI export, redacted-but-not-fully (name/DOB visible, SSN/ZIP redacted) | SQLite `.dump` text          | 1.7 MB compressed              | MIT               | `/tmp/josh-stack/my-health-data-ehi-wip/db.sqlite.dump`                               | **Yes** — fixture for `my-health-data-ehi-wip` |
| **MIMIC-IV-on-FHIR**                             | Beth Israel Deaconess ICU, deidentified, mapped to FHIR R4 with custom profiles       | FHIR R4 JSON                 | ~50K patients                  | PhysioNet (gated) | physionet.org (credentialed access)                                                   | No                     |
| **All of Us / NIH**                              | Multi-site research cohort, OMOP CDM + FHIR ingest                                    | OMOP + FHIR                  | ~750K participants             | Gated             | researchallofus.org                                                                   | No                     |
| **SMART Health IT sandbox / Epic on FHIR**       | Real-shape but synthetic patients exposed via SMART OAuth endpoints                   | FHIR R4 wire                 | ~30 sandbox patients each      | Public            | launch.smarthealthit.org / fhir.epic.com                                              | **Yes** — Josh's brand directory has them |
| **Open Epic EHI Tables docs**                    | Epic's own published documentation of the EHI Export schema                           | HTML                         | hundreds of pages              | Public            | open.epic.com/EHITables                                                               | Indirectly (basis for Josh's schemas) |

**The non-obvious gap:** there is **no public sample of a real-EHR FHIR pull**. Sandbox endpoints emit Synthea-shaped or contrived data; MIMIC is gated; everything else is real-PHI behind portals. **The closest thing to a real EHR FHIR snapshot in the open is whatever Josh's redaction studio outputs from his own SMART pulls — which is not published.** This is a gap Atlas might fill if Blake ever ships a "demo with my own connected portal" path.

## Nuances and gotchas (per dataset)

These are the not-from-the-README facts that bite if you assume datasets are interchangeable.

- **Synthea ≠ real EHR FHIR.** Synthea bundles are *complete* (every Observation has a `valueQuantity`, every Condition has an `onset`). Real Epic FHIR is *sparse* (missing values, non-standard extensions, paged search results). A fetcher that works against Synthea may break against Epic. **Atlas should test against both.**
- **CCDA is not a strict subset of FHIR.** The mapping is lossy in both directions. CCDA's narrative-document model carries clinical reasoning prose that FHIR resources don't. FHIR's resource graph captures relationships CCDA flattens. `sample_ccdas` is useful for *converter* testing, not as a stand-in for FHIR data.
- **`vendors.json` is not authoritative — CHPL is.** Josh's catalog adds editorial grading. Treat it as a *useful* derivative, not the source of truth. If Atlas needs to know "is this vendor certified for EHI Export?" hit CHPL directly.
- **Epic EHI Export ≠ Epic FHIR API.** They overlap (both come from the same Chronicles DB) but diverge enormously: EHI is bulk TSV with thousands of tables; FHIR is per-resource JSON over HTTPS. Josh's two pipelines (`health-skillz` for FHIR, `my-health-data-ehi-wip` for EHI) ingest **different shapes from the same underlying system**. This is the single biggest reason FHIR-and-EHI-Export merge is a non-trivial Atlas problem.
- **Josh's "redacted" dump still has his name in it.** `MANDEL,JOSHUA C` appears literally in `ACCOUNT.tsv`. The redaction is targeted (SSN, ZIP, some addresses) — not blanket. Treat it as a *demo* dataset, not a *PHI-free* dataset. Don't blast it through any service that logs.
- **MAX_CONCURRENCY = 5, no `_count` set, no pagination.** Josh's fetcher relies on server defaults for page size. Real Epic prod FHIR may default to 100 — that means a patient with 5,000 Observations gets a partial pull unless pagination is added. Atlas should fix this if lifting the SMART client.
- **The `_index.json` in `schemas/` is empty.** I expected a manifest; it's a 0-byte placeholder. The schema "set" is the *files in the directory*. If you write a script that loads `_index.json`, you get an empty object and nothing loads. **Future bug magnet.**
- **6,631 schemas vs. 550 TSVs vs. 414 post-merge JSONs — the numbers don't agree because they count different things.** Schemas describe column-sets (logical or physical); TSVs are physical table files; post-merge JSONs are logical tables. The whole point of D05 is to explain why these three counts diverge.
- **`vendors.json`'s `analyses/{slug}.md` files are LLM-generated.** Josh's `wiggum/` runner (in `ehi-export-analysis`) generated them with an LLM over CHPL data + vendor docs. They're useful narrative summaries but should not be cited as authoritative — they have the typical hallucination risk.

## Datamart seed plan

Concrete proposed actions for `../../datamart/inputs/`. **Greenlight individually before D01b runs them.**

| Order | Action                                                                                       | Source                                                          | Destination                                                  | Size      | Risk                              |
| ----- | -------------------------------------------------------------------------------------------- | --------------------------------------------------------------- | ------------------------------------------------------------ | --------- | --------------------------------- |
| 1     | Symlink Synthea bundles                                                                      | `../../data/synthea-samples/synthea-r4-individual/fhir/`        | `datamart/inputs/synthea-fhir-bundles`                       | ~2 GB     | None (local, immutable)           |
| 2     | Symlink pitch SQLite                                                                         | `../../research/ehi-ignite.db`                                  | `datamart/inputs/ehi-ignite-pitch.db`                        | 11 MB     | None                              |
| 3     | Symlink Synthea bulk dataset                                                                 | `../../data/synthea-samples/sample-bulk-fhir-datasets-10-patients/` | `datamart/inputs/synthea-bulk`                           | small     | None                              |
| 4     | Copy Josh's redacted dump (and a `.sqlite` reconstituted form)                               | `/tmp/josh-stack/my-health-data-ehi-wip/db.sqlite.dump`         | `datamart/inputs/josh-epic-ehi-dump/db.sqlite.dump` (+ `.sqlite`) | 1.7 MB → ~6 MB | None (MIT, on disk)               |
| 5     | Copy a small fixture-set of Josh's per-table schemas (10–20 files)                           | `/tmp/josh-stack/my-health-data-ehi-wip/schemas/`               | `datamart/inputs/josh-epic-schemas-sample/`                  | <500 KB   | None                              |
| 6     | Copy a small fixture-set of Josh's TSV (5–10 tables matching the schema sample)              | `/tmp/josh-stack/my-health-data-ehi-wip/tsv/`                   | `datamart/inputs/josh-epic-tsv-sample/`                      | <2 MB     | None (already redacted)           |
| 7     | Mirror `vendors.json`                                                                        | `https://joshuamandel.com/ehi-export-analysis/data/vendors.json` | `datamart/inputs/josh-vendor-catalog/vendors.json`           | ~30 KB    | **Live URL — needs greenlight**   |
| 8     | Mirror `analyses/*.md` (one fetch loop, 71 files)                                            | `https://joshuamandel.com/ehi-export-analysis/data/analyses/{slug}.md` | `datamart/inputs/josh-vendor-catalog/analyses/`        | ~1.5 MB   | **Live URL — needs greenlight**   |
| 9     | (Future) Clone `jmandel/sample_ccdas` for D04+                                               | github.com/jmandel/sample_ccdas                                 | `datamart/inputs/ccdas-sample/`                              | ~50 MB    | External clone — defer            |
| 10    | Write `datamart/.gitignore` (excludes `intermediate/`, large copied snapshots)               | —                                                               | `datamart/.gitignore`                                        | —         | None                              |

Items 1–6 + 10 are zero-risk and Blake can greenlight them in one go. Items 7–8 hit a live URL hosted by Josh and should be confirmed once. Item 9 defers until D04.

## Code shipped in `../../prototypes/`

**None yet.** D01 is a study + planning session. The first prototype lands in D01b (the seed runner) once Blake confirms the seed plan, or in D02 (the FHIR-lifecycle ports) directly.

## Datamart artifacts produced

**None yet** — this session creates the *plan* for `datamart/`, not the contents. After Blake's greenlight on the seed plan, items 1–6 + 10 land in `datamart/inputs/` and `datamart/.gitignore`.

## Glossary additions

See `../GLOSSARY.md`. New entries this session:
- `ClientFullEHR` (formal definition with type signature)
- `ClientProcessedAttachment`
- Initial-fetch query plan (29 queries)
- `_C_NAME` denormalized lookup column convention (Epic)
- Wiggum (Josh's LLM runner for generating vendor analyses)

## Open questions

- **Why 6,631 schemas if there are only ~550 physical tables?** Hypothesis: many schemas describe column subsets, indexed projections, or related-tables that don't have their own TSV. Confirm in D04/D05.
- **Why is `schemas/_index.json` empty?** Possibly an expected output of a build step that never ran, or a placeholder pre-D04 stage of Josh's pipeline. Worth confirming when reading `01-make-json.js`.
- **Does `vendors.json` ever update, and does Josh have a regen path?** Important for caching strategy. Likely answered by reading `ehi-export-analysis/wiggum/`.
- **What's the fhirToPlaintext.ts coverage matrix?** 1513 lines suggests per-resource-type renderers for ~30+ resource types — but does it cover everything in the 29-query plan? D02 will check.
- **Can Atlas find or generate a real-EHR FHIR snapshot for testing?** Synthea is too clean; sandbox endpoints are limited; MIMIC is gated. Possibly worth a side-trip to MIMIC-IV-on-FHIR access.

## Where to read next

**Session D02: FHIR data lifecycle.** Walk one Synthea patient end-to-end through Josh's pipeline — wire FHIR → `ClientFullEHR` → SQLite → plaintext. Three files we ship into `prototypes/`: `josh-fhir-snapshot/` (ingest a Synthea bundle, materialize the snapshot), `josh-fhir-flatten/` (the SQLite schema), `josh-plaintext-render/` (per-resource narrative). Each writes into `datamart/intermediate/` so the same patient appears in three forms on disk by session end.

**Before D02 starts**, the bench needs the seed plan items 1–6 + 10 done. That can either be a "D01b — bench bootstrap" mini-session (runs the symlinks + copies, no study notes) or rolled into the start of D02.

---

Ready for one of three next moves:
1. **Greenlight the safe seeds (items 1–6 + 10)** and I run them in a quick D01b before D02.
2. **Greenlight everything including the live-URL fetches (items 7–8)** and I run all of D01b at once.
3. **Open a question above** if any of the gotchas raise concerns before we proceed.
