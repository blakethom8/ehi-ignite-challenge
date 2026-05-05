# Ingestion and Harmonization UX Plan

| Field | Value |
|---|---|
| Date | 2026-05-04 |
| Scope | Current app workflow for uploading files, extracting PDFs, harmonizing sources, and reviewing usable data |
| Related future idea | `docs/ideas/AGENTIC-PDF-HARMONIZATION.md` |

## Purpose

This document focuses on the near-term product path, not the future agentic build. The current application already has the core pieces:

- Data Aggregator upload staging
- local file persistence under `data/aggregation-uploads/`
- upload-derived harmonize collections
- async PDF extraction jobs
- cross-source harmonization
- persisted harmonization runs
- review queue items
- published chart snapshots
- downstream read path for FHIR Charts and Clinical Insights
- source contribution diff
- provenance drill-down

The next product problem is making this understandable and dependable for a user: what they uploaded, what the system did with it, what became usable clinical data, and what still needs review.

## Current workflow

Today the flow is roughly:

```text
Data Aggregator
  -> user creates or selects a workspace
  -> user uploads files and adds source context
  -> files are stored locally under data/aggregation-uploads/<patient_id>/
  -> PDFs show a per-file Extract PDF / Run PDF processor action
  -> structured files are marked FHIR ready

Harmonize View
  -> user runs harmonization or re-runs harmonization
  -> backend writes a persisted run artifact
  -> review queue blocks publish when source gaps or fact conflicts need judgment
  -> user reviews merged facts, unique/shared source contribution, and provenance

Publish Chart
  -> user activates a reviewed snapshot
  -> FHIR Charts and Clinical Insights read the active published snapshot
```

This is a strong foundation. The main gap is that the user experience does not yet clearly present this as a stepwise build process with artifact states.

## Product framing

The user should understand that uploaded files move through four states:

```text
1. Stored source material
2. Extracted candidate facts
3. Harmonization run
4. Reviewed candidate record
5. Published chart snapshot
```

The app should avoid implying that "upload" equals "chart truth." It should show that upload starts a transformation process.

Recommended user-facing language:

- `Uploaded`: file is safely staged.
- `Ready to extract`: the system recognizes the file type and can process it.
- `Extracting`: PDF/JSON parsing is running.
- `Needs review`: extraction succeeded but validation/confidence needs attention.
- `Harmonized`: structured facts are merged into the usable data layer.
- `Unsupported`: file is stored but cannot yet be parsed.

## Recommended frontend flow

### Page 1: Add Sources

The Data Aggregator page should be the user's source workspace.

It should answer:

- What files have I added?
- What kind of source is each file?
- What context did I provide?
- What is the next step for each file?
- Is this file currently just stored, or has it been parsed?

Near-term UX improvements:

- Use a compact local flow:
  `Add files -> Prepare sources`
- Replace generic `Confidence` with clearer `Parse readiness` or `Extraction readiness`.
- Add per-file status text:
  - `Stored only`
  - `FHIR JSON detected`
  - `PDF pending extraction`
  - `Extracted`
  - `Unsupported format`
- Use `Open Harmonized Record` as the bridge once at least one source is
  prepared. Keep `Run harmonization` on Harmonized Record so upload does not
  imply chart truth.
- Show that deleting a file also removes any derived extraction for that file.

### Page 2: Run Harmonization and Review Candidate Record

The Harmonize page should become the operational build surface.

It should answer:

- Which collection am I working on?
- Which sources are available?
- Has harmonization been run?
- Which sources are included in the run?
- How many structured facts did each source contribute?
- What facts are unique to a source?
- What facts are shared across sources?
- What source supports this merged fact?
- What blocks publish?

Near-term UX improvements:

- Add a compact pipeline status panel above the source table:

```text
Source readiness
  5 files staged
  3 structured sources available
  2 PDFs pending extraction
  0 validation failures
  350 harmonized facts
```

- Make `Run harmonization` / `Re-run harmonization` the primary action when
  sources have changed. The output should be a durable run artifact with source
  fingerprints, matcher version, candidate facts, review items, and provenance
  links.

- After extraction completes, show:
  - files processed
  - cache hits
  - elapsed time
  - resource count
  - validation status when available

- In the source table, distinguish:
  - `Raw resources`
  - `Unique harmonized facts`
  - `Shared harmonized facts`
  - `Status`

### Page 3: Review Candidate Data

The current tabs already support review of Labs, Conditions, Medications, Allergies, and Immunizations.

Near-term UX improvements:

- Add a persistent summary:
  `This record contains X harmonized facts from Y sources. Z facts appear in multiple sources. N facts are unique to PDFs.`
- Add filters:
  - all facts
  - cross-source only
  - PDF-only
  - needs review
- Add source badges directly in fact rows.
- Make "vision wins" explicit but restrained:
  `PDF-only findings`

This is where the product wedge becomes obvious: the app is not just parsing documents; it is showing what each source added to the patient journey.

### Page 4: Publish Chart

Publish Chart should be the final activation surface, not a generic readiness
checklist.

It should answer:

- Which candidate run is active?
- Which run is currently published downstream?
- Is publish blocked by review items or missing preparation?
- Can the user activate, roll back, or delete workspace artifacts?
- Which downstream modules are reading this snapshot?

## Storage and persistence

There are three reasonable persistence levels.

### Option A: rebuild every run

Use this only for deterministic demo artifacts like `synthea-demo`.

Pros:

- clean
- reproducible
- low migration burden

Cons:

- bad user experience for uploads
- expensive for PDF extraction
- loses job history and review state

### Option B: file-based local persistence

This is what the app mostly does today.

Current shape:

```text
data/aggregation-uploads/<patient_id>/
  <file_id>-<filename>
  <file_id>.metadata.json
  <filename>.extracted.json
```

Pros:

- simple
- easy to inspect
- good for development
- works without database migrations
- compatible with ignored private/local data

Cons:

- weak job history
- difficult to query across sessions
- derived artifact naming can drift
- hard to show durable status after restart unless metadata is enriched

Recommended near-term path: keep file-based persistence, but make it more explicit.

Suggested shape:

```text
data/aggregation-uploads/<session>/
  originals/
    <file_id>-<filename>
  metadata/
    <file_id>.json
  extracted/
    <file_id>.bundle.json
    <file_id>.validation.json
  harmonized/
    merged-summary.json
  jobs/
    <job_id>.json
    events.ndjson
```

This still avoids a database while making the workflow understandable and durable.

### Option C: SQLite/Postgres persistence

Use this when we need multi-user sessions, job history, searchable artifacts, review assignments, or deployment durability.

Recommended later tables:

- `upload_sessions`
- `uploaded_files`
- `extraction_jobs`
- `extraction_events`
- `source_documents`
- `extracted_bundles`
- `validation_reports`
- `harmonized_collections`
- `review_decisions`

Near-term recommendation: do not jump to Postgres yet. Add a file-based manifest first. If the manifest starts acting like a database, then promote it to SQLite.

## Development recommendation

For the next phase, use hybrid persistence:

- Rebuild public demo data on demand.
- Persist uploaded files and extracted bundles locally.
- Persist job state enough that refreshes and restarts are understandable.
- Treat harmonized outputs as rebuildable from validated source artifacts.

In other words:

```text
Raw uploads: persistent
Extraction outputs: persistent cache
Validation reports: persistent
Harmonized record: rebuildable, optionally cached
UI review decisions: persistent once review is added
```

This gives us fast iteration without re-running expensive PDF extraction every time.

## Backend changes to consider

1. Add upload-session manifest.
   - Store file status, source type, extraction status, output paths, validation state.

2. Normalize derived artifact paths.
   - Use file ids, not original names, for extracted outputs.

3. Add extraction readiness to source manifest.
   - `pending`, `extracting`, `extracted`, `failed`, `unsupported`.

4. Persist extraction job events.
   - File-based JSON is enough for now.

5. Add validation status to `HarmonizeSource`.
   - Even if validation is shallow at first, the UI needs the concept.

6. Make delete remove derived artifacts.
   - If a PDF is removed, remove its extracted bundle and validation report too.

## Frontend changes to consider

1. Add a pipeline stepper shared across Data Aggregator and Harmonize.

2. Rename status labels to match user expectations.
   - `Stored`
   - `Ready to extract`
   - `Extracted`
   - `Harmonized`
   - `Needs review`

3. Add a source readiness summary to Harmonize.

4. Add per-source status badges in the source table.

5. Add PDF-only / cross-source / needs-review filters in resource tabs.

6. Make the review loop explicit:
   - "This source contributed 14 unique facts"
   - "Review PDF-only facts"
   - "Mark reviewed" later

## What not to do yet

- Do not make the future agentic workflow a dependency for the current app flow.
- Do not move private or upload data into committed corpus paths.
- Do not force live extraction into normal CI.
- Do not let extracted PDF facts silently become final chart truth without status/provenance.
- Do not overbuild a production database before the artifact lifecycle is stable.

## Bottom line

The current application is close to the right workflow. The near-term work is to make the transformation lifecycle visible:

```text
files -> extracted facts -> harmonization run -> reviewed candidate record -> published chart snapshot
```

For development, file-based persistence is enough if it is organized around manifests, job events, and explicit derived artifacts. The harmonized record can remain rebuildable. The expensive extraction outputs should persist.

The frontend should stop feeling like separate upload and harmonize tools. It should feel like one guided build process for turning patient-provided files into a usable, provenance-backed data layer.
