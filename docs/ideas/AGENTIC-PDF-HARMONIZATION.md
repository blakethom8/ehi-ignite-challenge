# Agentic PDF-to-FHIR and Harmonization Report

| Field | Value |
|---|---|
| Date | 2026-05-04 |
| Topic | Should PDF-to-FHIR ingestion and cross-source harmonization become an agentic workflow? |
| Scope | EHI Atlas PDF extraction, upload-derived collections, harmonization, provenance, future app workflow |
| Primary references | `docs/snapshot/2026-05-04-harmonize-catchup.md`, `docs/architecture/PIPELINE-LOG.md`, `docs/architecture/CONTEXT-PIPELINE.md` |

## Executive take

Yes, there is real value in making the ingestion and PDF-to-FHIR portion of this system agentic. The reason is not that an agent should "magically harmonize clinical data." The value is that real patient data acquisition is messy, multi-step, and failure-prone:

- Users upload mixed PDFs, FHIR JSON, portal exports, zip files, image scans, and lab reports.
- Some files are structured, some are semi-structured, and some are just visual documents.
- The right extraction strategy depends on document type.
- Many failures require inspection, rerouting, retries, or a user-facing clarification.
- Outputs must pass validation before they should influence the longitudinal patient record.

That is not a good fit for a single fixed pipeline. It is a good fit for a guided agentic job workflow with deterministic tools, validation gates, and provenance.

The core harmonization layer should remain deterministic. Matching facts across sources, minting provenance, computing unique-vs-shared contribution diffs, and producing the clinician-facing merged record should not be left to free-form model judgment. The agent should orchestrate ingestion and extraction. The harmonizer should adjudicate only through explicit, testable algorithms.

## What we have now

The recent work is directionally strong. The system now has the shape of a real product workflow rather than an offline notebook.

Current capabilities:

- `multipass-fhir` extracts PDF facts directly into FHIR-shaped resources with a document-context pass and five focused resource passes.
- The pipeline log shows empirical learning: multipass is essential for comprehensive chart PDFs, while lab-only PDFs likely need a cheaper routed path.
- Upload-derived collections auto-register from `data/aggregation-uploads/<session>/`.
- `POST /api/harmonize/{collection_id}/extract` runs extraction in the background and returns a job id.
- React polls `/api/harmonize/extract-jobs/{job_id}` and refreshes all merged-record queries on completion.
- The harmonize layer merges Observations, Conditions, Medications, Allergies, and Immunizations.
- Provenance is bidirectional: from a merged fact to sources, and from a source document to contributed facts.
- Source-diff now surfaces unique vs shared facts. This is the product version of "vision wins."
- `synthea-demo` gives fresh clones a working cross-source harmonization flow without private data.

The most important strategic signal is Move R in `PIPELINE-LOG.md`: Cedars PDF-only unique conditions surfaced automatically as source-diff results. That means PDF extraction is not just reformatting. It can reveal clinically relevant facts that the structured FHIR export does not carry.

## Why an agentic process fits this problem

The agentic layer should exist because the system needs to make bounded decisions over a heterogeneous workspace:

1. Identify what the user uploaded.
2. Detect whether a file is FHIR JSON, Health Skillz style envelope, C-CDA, lab PDF, portal health summary, imaging report, discharge summary, scan, zip, or unknown.
3. Decide which extraction pipeline to run.
4. Route lab-only documents away from expensive multipass when possible.
5. Run extraction with the right backend/model.
6. Validate the FHIR bundle and provenance metadata.
7. If validation fails, repair only the invalid resource shape or re-run the relevant pass.
8. If ambiguity remains, ask the user for specific input rather than silently guessing.
9. Write extracted bundles beside the source documents.
10. Trigger harmonization and produce a clear source contribution report.

A manual process works while Blake is the only operator. It does not scale to clinicians or reviewers bringing arbitrary portal exports.

The product should not expose this as "an AI agent is thinking." It should expose it as a guided import job:

```text
Upload documents
  -> Inspect files
  -> Classify source types
  -> Extract structured facts
  -> Validate FHIR + provenance
  -> Harmonize across sources
  -> Show what each source contributed
  -> Ask for user help only when needed
```

## What should be agentic vs deterministic

| Layer | Should be agentic? | Why |
|---|---:|---|
| File intake and classification | Yes | User uploads are unpredictable. The system needs to inspect, route, and explain. |
| Source acquisition guidance | Yes | Users may need help downloading portal zips, finding the right export, or separating duplicate files. |
| Pipeline selection | Yes | Lab PDFs, chart summaries, scans, and discharge summaries need different pipelines. |
| Extraction pass orchestration | Yes | Retry, route, swap model, repair, and summarize failures. |
| FHIR validation repair | Partly | Agent can propose or run constrained repairs, but validators decide pass/fail. |
| Clinical fact merging | No | Keep deterministic matchers for LOINC, RxNorm, SNOMED, CVX, dates, units, and source identity. |
| Provenance graph | No | Must be deterministic and auditable. |
| Clinician-facing clinical summary | Hybrid | Deterministic context builder first, LLM for explanation and Q&A second. |

This separation matters. The agent is the operator of tools. It is not the source of truth.

## Proposed application model

The app should treat ingestion as a long-running workspace job with stages. A single upload session becomes a collection. The collection has files, extracted bundles, validation reports, harmonized records, and a job event log.

Recommended job states:

```text
created
inspecting_files
awaiting_user_input
ready_to_extract
extracting
validating
repairing
harmonizing
complete
failed
```

Recommended job artifacts:

```text
data/aggregation-uploads/<session>/
  original/
    <uploaded files>
  normalized/
    <expanded zip contents, renamed files, derived page images if needed>
  extracted/
    <file>.bundle.json
    <file>.validation.json
    <file>.provenance.ndjson
  job.json
  events.ndjson
```

The current implementation already has the start of this pattern with `<basename>.extracted.json` next to uploaded PDFs. That is good for a first version. The next step is to make the job state and event log first-class so the UI can show progress, partial success, and next actions.

## Agent capabilities needed

The agentic ingestion worker should have a small set of explicit tools:

- `inspect_uploads(session_id)`: list files, sizes, mime types, page counts, JSON shapes.
- `classify_source(file)`: assign source type and confidence.
- `extract_pdf(file, pipeline, backend, model)`: run single-pass, multipass, or specialized route.
- `validate_bundle(bundle)`: run FHIR/provenance validation.
- `repair_bundle(bundle, validation_report)`: constrained repair of structural errors only.
- `harmonize_collection(collection_id)`: run deterministic merge layer.
- `source_diff(collection_id)`: report unique/shared source contribution.
- `request_user_input(question, file_refs)`: ask targeted questions when automation cannot proceed.

The worker should be able to retry and branch, but every step should emit durable events:

```json
{"stage":"classify_source","file":"cedars-summary.pdf","result":"patient-summary","confidence":0.91}
{"stage":"extract_pdf","pipeline":"multipass-fhir","status":"complete","entry_count":156}
{"stage":"validate_bundle","status":"failed","errors":["MedicationRequest missing subject"]}
{"stage":"repair_bundle","status":"complete","repaired_resources":3}
{"stage":"harmonize","status":"complete","merged_facts":350,"cross_source":65}
```

This is how the agent becomes auditable rather than opaque.

## Local model or cloud VM?

There is a plausible role for a local or self-hosted model, but it should not be the first dependency of the product.

Best split:

- Use hosted frontier models for high-risk, narrative-heavy extraction while the prompts and schemas are still changing.
- Use cheaper or local/open-weight models for lower-risk repetitive tasks:
  - document classification
  - table extraction triage
  - chunk summarization
  - validation-error repair suggestions
  - duplicate/source-quality summaries
- Keep the pipeline backend-pluggable, which `multipass-fhir` already started with per-pass overrides.

The cloud VM version is attractive for batch runs:

```text
API app enqueues ingestion job
  -> worker VM pulls job
  -> model runtime + PDF tooling run close to disk
  -> writes extracted bundles and validation reports
  -> API polls job store
```

The local-model path is best treated as an optimization and privacy posture, not as the main architecture. The real architecture is the job framework, tool contracts, validation gates, and provenance. The model can change behind that.

## Two-agent architecture: runtime vs builder

There are two very different meanings of "agent" in this product. They should not be collapsed.

### 1. Runtime ingestion agent

This is the agent a user indirectly interacts with after uploading documents. It operates inside a prepared workspace and can make decisions about files, extraction routes, retries, validation, and user handoffs.

It can:

- inspect uploaded files
- classify source types
- choose an extraction pipeline
- run OCR, layout, PDF, and FHIR tools
- write extracted bundles to staging
- write validation reports
- write job events
- ask the user for clarification
- trigger deterministic harmonization

It should not:

- rewrite application code
- silently change FHIR schemas
- bypass validation gates
- write directly to gold/harmonized records
- modify production database tables outside narrow service APIs

The runtime agent is flexible with workflow, not with system rules.

### 2. Builder / research agent

This is the agent that improves EHI Atlas itself. It runs in an isolated development workspace, branch, or VM. It can modify code, schemas, prompts, adapters, tests, and fixture generators.

It can:

- add a new extraction pass
- add a new FHIR resource converter
- change schemas
- update validators
- create synthetic fixtures
- run tests
- open a reviewed diff or pull request

It should not process production patient uploads as its main job. It may use deidentified or synthetic fixtures to improve the system, but code changes should land through normal review and tests before they affect runtime ingestion.

The builder agent is flexible with code, not with production patient state.

## VM and container mental model

A virtual machine is a rented computer in the cloud. It has CPU, RAM, disk, an operating system, and usually a public or private network address. You install Docker or a runtime on it and run services there.

A container is a packaged process running on a machine. It includes the app code and dependencies but shares the host machine's kernel. Containers are usually the unit we deploy. VMs are usually the machines containers run on.

For this project, the practical shape is:

```text
Main app VM
  - FastAPI
  - React/nginx
  - app database
  - job API

Worker VM or worker container
  - PDF tooling
  - model client or local model runtime
  - extraction pipelines
  - validation tools
  - access to staging object/file storage

Optional model VM
  - local/open-weight model server
  - GPU or high-RAM CPU instance
  - reachable only by worker containers
```

This can start as one VM with separate containers:

```text
docker compose:
  api
  app
  ingestion-worker
  sqlite/postgres
  redis or sqlite job store
```

Later, if extraction gets expensive or needs GPU/RAM, move `ingestion-worker` or the model runtime onto a separate VM.

## Access boundaries

Access should be designed around least privilege.

| Component | Can read | Can write | Should not do |
|---|---|---|---|
| React app | API responses | Nothing directly | Access files/databases directly |
| FastAPI orchestrator | job DB, manifests, harmonized records | job rows, collection metadata | Run heavy PDF extraction in request thread |
| Runtime ingestion worker | upload session, schemas, tool config | staging bundles, validation reports, job events | Modify app code or gold records directly |
| Deterministic harmonizer | validated bundles | merged records, provenance graph | Call LLM to decide merges |
| Builder agent | dev workspace, fixtures, docs | code/schema/tests in branch | Mutate production patient state |
| Model server | prompt payloads from worker | model responses | Read storage or databases directly |

This suggests four storage zones:

```text
uploads/original/      user-provided raw files
work/                  OCR text, layout JSON, page images, intermediate artifacts
staging/extracted/     extracted FHIR bundles + validation reports
gold/harmonized/       deterministic merged record + provenance
```

The runtime agent writes to `work/` and `staging/extracted/`. The harmonizer promotes validated artifacts into `gold/harmonized/`. The builder agent writes code in a development branch, not patient data.

## Who orchestrates?

FastAPI should remain the application orchestrator from the user's perspective:

1. User uploads files.
2. FastAPI creates an ingestion job.
3. FastAPI persists the job and returns `job_id`.
4. A worker claims the job.
5. The worker runs the runtime ingestion agent loop.
6. The worker writes events and artifacts.
7. FastAPI serves job status to React.
8. When extraction is validated, FastAPI or the worker calls deterministic harmonization.
9. React refreshes the harmonized record and source-diff panels.

The runtime agent orchestrates only inside the job:

```text
inspect -> classify -> choose route -> extract -> validate -> repair/retry -> harmonize -> summarize
```

The builder agent is not in this production path. It is invoked separately when the system needs new capabilities.

## Schema evolution rule

The runtime agent may detect schema gaps, but it should not mutate schemas live.

Example:

```text
Runtime finding:
  "This discharge summary contains procedures, but the current multipass
   extraction schema does not include Procedure."

Runtime action:
  record schema_gap event
  extract supported facts
  optionally preserve unsupported text as DocumentReference/Composition narrative

Builder action:
  add ProcedureExtraction schema
  add procedure prompt/pass
  add FHIR Procedure converter
  add synthetic fixtures
  add validator coverage
  run tests
  land reviewed code change
```

This keeps the production data path auditable while still allowing the system to improve quickly.

## How this connects to the context pipeline

`CONTEXT-PIPELINE.md` is still the right direction for clinician Q&A: build clean deterministic context first, then call the LLM. The new harmonize layer should become the upstream source for that context.

Recommended future flow:

```text
Source documents and FHIR exports
  -> agentic ingestion job
  -> validated extracted FHIR bundles
  -> deterministic harmonization
  -> provenance-backed merged record
  -> deterministic clinical context builder
  -> LLM answer with citations
```

This preserves the "right 5 facts in 30 seconds" product wedge. The agent helps create the data foundation. It should not replace the context builder or become a free-form chart reviewer over raw documents.

## Product implications

The user-facing feature should feel like a guided data-import workspace:

- Show every source the user provided.
- Show whether each source was recognized, extracted, validated, and harmonized.
- Show what each source uniquely contributed.
- Show what facts were shared across sources.
- Let the user click into failures with concrete next steps.
- Ask for user help only when needed:
  - "This zip contains two possible patient records. Which one should we import?"
  - "This PDF appears scanned and has low OCR confidence. Try uploading the portal export instead?"
  - "This document has no visible encounter date. Should we use the upload date, file name date, or skip date assignment?"

This is more valuable than a generic "upload and hope" parser.

## Risks and guardrails

Key risks:

- Silent over-extraction from narrative documents.
- Incorrect dates attached to facts.
- False cross-source merges when display text is similar but clinical identity differs.
- Agent retries masking systematic prompt failures.
- Local/open-weight model quality varying by document type.
- In-memory job state not surviving restarts.
- Private documents leaking into committed corpus paths.

Guardrails:

- Every extracted resource needs source provenance and, when possible, page/bbox locator.
- Validation should gate movement from extracted bundle to harmonized record.
- Per-pass failure should be visible in the job event log.
- The harmonizer should expose conflicts and low-confidence matches rather than collapsing them silently.
- Live extraction tests should stay opt-in behind an environment flag.
- Synthetic fixtures should be generated deterministically and include machine-readable expected facts.

## Recommended next moves

1. Make extraction jobs durable.
   - Replace or supplement the in-memory job store with SQLite.
   - Persist job stage, events, file decisions, extraction outputs, and validation reports.

2. Add an ingestion manifest.
   - One manifest per upload session.
   - Track original files, derived files, source classification, selected pipeline, status, and output paths.

3. Add pipeline routing.
   - Lab-only PDF -> single-pass or table-focused path.
   - Patient summary / discharge / H&P -> multipass-fhir.
   - Scanned/no-text PDF -> OCR/vision route.
   - Unknown -> inspect + ask user.

4. Add validator-gated extraction.
   - Run bundle/provenance validation before extracted output becomes harmonizable.
   - Keep failed bundles available for debugging but do not merge them by default.

5. Improve synthetic fixtures.
   - Build realistic reportlab-generated PDFs under a stable constructed-fixture path.
   - Include expected facts, expected bundles where practical, and source locators.

6. Wire harmonized data into Clinical Insights.
   - The catch-up report already identifies this as the natural next integration.
   - The "right 5 facts" briefing should consume merged records, not raw Synthea-only data.

7. Add agentic worker behind the existing async extraction endpoint.
   - Keep the API shape: enqueue job, poll job.
   - Upgrade the implementation from "run multipass on pending PDFs" to "inspect, classify, route, extract, validate, repair, harmonize."

## Bottom line

The project is heading in the right direction. The harmonize layer is the strongest part because it is deterministic, testable, and provenance-first. The PDF extraction layer is correctly becoming empirical and pipeline-based rather than pretending there is one universal PDF-to-FHIR parser.

The next product leap is to wrap ingestion in an agentic workflow. That workflow should be a disciplined operator around explicit tools, not an unconstrained clinical reasoning agent. In application terms, it should look like a durable import job with progress, decisions, validation, and user handoffs.

That is the right structure for a world with diverse data sources, messy documents, and edge cases that cannot be handled by a single end-to-end pipeline.
