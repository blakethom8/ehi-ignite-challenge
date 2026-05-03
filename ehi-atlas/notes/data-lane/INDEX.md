# Data Lane — Josh Mandel Stack

**Goal:** understand every data shape that flows through Josh's stack — what enters, what's emitted, how it's transformed — so EHI Atlas can sit cleanly atop, beneath, or alongside it.

**Working-directory ethos:** this is a bench, not a reading list. Each session lands study notes here **and** running code in [`../../prototypes/josh-…/`](../../prototypes/) against real data in [`../../datamart/`](../../datamart/). When a session introduces a data shape, Blake should be able to `cat` an actual file on disk by the end of it.

**Three sibling directories under `data-research/` cooperate:**
- [`josh-stack-deep-dive/`](../) — qualitative study notes (this directory)
- [`../../datamart/`](../../datamart/) — shared data store: inputs, intermediates, schemas
- [`../../prototypes/`](../../prototypes/) — code that reads/writes the datamart

**Reading mindset:** ignore React, OAuth, transports. When Josh's code does authentication or UI, skim. When it touches a JSON record, a TSV row, a SQL schema, an in-memory snapshot, a Skill-bundle file on disk — slow down.

## Consolidated session arc (7 sessions)

| #   | Topic                                                                                          | Primary code (read)                                                                                     | Code we ship (`../../prototypes/`)                       | Status     | 1-line takeaway |
| --- | ---------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------- | -------------------------------------------------------- | ---------- | --------------- |
| D01 | **Josh's data catalog & public datasets.** 12 distinct data shapes across the 4 repos, per-app usage matrix, public-dataset survey, nuances per dataset, datamart seed plan | all 4 repos manifest + `clientTypes.ts` + `fhirSearchQueries.ts` + Josh's vendor catalog | (planned) `josh-vendor-catalog/` mirror script — pending greenlight | ✅ done 2026-05-01 (note); ⏳ seed actions pending greenlight | 12-shape catalog landed; FHIR-pull and Epic-EHI apps barely overlap on the data plane; "no merge, ever" is Josh's defining choice |
| D02 | **FHIR data lifecycle.** Wire-format → `ClientFullEHR` snapshot → flattened SQLite → per-resource plaintext. End-to-end on one Synthea patient | `health-record-mcp/clientFhirUtils.ts` + `clientTypes.ts` + `dbUtils.ts` + `fhirToPlaintext.ts`         | `josh-fhir-snapshot/`, `josh-fhir-flatten/`, `josh-plaintext-render/` | ⏳ pending | —               |
| D03 | **Redaction + Skill-bundle output.** From "all the patient's data" to "the data Claude reads." Variant clusters, redaction profile, JSZip layout, `data/<provider>.json` | `health-skillz/src/client/lib/{redaction,skill-builder}.ts`                                              | `josh-redaction-profile/`, `josh-skill-bundle/`          | ⏳ pending | —               |
| D04 | **Epic EHI raw shape.** TSV format, per-table JSON schemas (~6,631), redaction, the 552 raw physical tables | `my-health-data-ehi-wip/00-redact.js` + `01-make-json.js` + `schemas/` + `tsv/`                          | `josh-ehi-tsv-ingest/`                                   | ⏳ pending | —               |
| D05 | ⭐ **Logical-table inference.** The 523-line heuristic that turns 552 physical tables into N logical tables. Standalone session — densest single data-pipeline lesson in the stack | `my-health-data-ehi-wip/02-merge-related-tables.ts`                                                      | `josh-ehi-table-merge/`                                  | ⏳ pending | —               |
| D06 | **Materialization + LLM annotation.** Per-table JSON split → TS codegen → SQLite schema + bulk load → LLM-assisted sample-row + table-cluster + short-description passes | `03-split-files.ts` + `04-codegen.ts` + `05-sqlite.ts` + `06`/`07`/`08`                                  | `josh-ehi-materialize/`                                  | ⏳ pending | —               |
| D07 | **Cross-stack synthesis.** End-to-end data-flow diagram. The "patient-data atom" model. Where Atlas's bronze/silver/gold + Provenance graph fits relative to Josh | all data sessions + Atlas architecture docs                                                              | `atlas-shape-diff/` (first Atlas-side prototype)         | ⏳ pending | —               |

## What was consolidated

The old 12-session arc collapsed:
- old D01 (inventory) + D02 (vendor metadata) → **new D01**
- old D03 (FHIR fetch) + D04 (SQLite flattening) + D05 (plaintext renderer) → **new D02** (one session because they're three views of the same FHIR snapshot)
- old D06 (redaction model) + D07 (skill-bundle output) → **new D03**
- old D08 (Epic EHI raw) → **new D04**
- old D09 (logical-table inference) → **new D05** (kept standalone — too dense to merge)
- old D10 (codegen + SQLite) + D11 (LLM annotation) → **new D06**
- old D12 (synthesis) → **new D07**

Net: 12 → 7, with the FHIR lifecycle (D02) and EHI materialization (D06) being deliberately big.

## Per-session template (data lane variant)

Each data-lane note follows the standard study-note shape **plus three mandatory sections**:

> **## Data flow at this stage**
> Diagram or table: input shape → transformation → output shape. Type signatures, table/column counts, file-on-disk layouts, JSON shapes. The single most load-bearing section.

> **## Code shipped in `../../prototypes/`**
> List of prototypes (`josh-…/` or `atlas-…/`) written this session, what they do, how to invoke them, what files they emit into `../../datamart/intermediate/`.

> **## Datamart artifacts produced**
> What new files exist in `../../datamart/` after this session, with paths and shapes.

## Data-lane themes Blake should track

- **Where Josh preserves provenance vs. where it's lost.** Per-source bundles preserve it; SQLite flattening loses some; plaintext rendering loses most. Atlas needs to add it back as first-class.
- **The four data-shape transitions in the stack:**
  1. Wire-format (FHIR-JSON over HTTPS, or TSV-over-ZIP) → in-memory snapshot
  2. In-memory snapshot → queryable (SQLite) form
  3. Queryable → human/LLM-readable text
  4. Anything → bundled-on-disk for Skills
- **What's missing on the data side.** Cross-source merge, conflict adjudication, fact-level provenance, longitudinal episode/timeline modeling, drug-class enrichment, derived "is this medication active right now" flags. *Atlas's wedge.*

## Where to read next

**Session D01: Bench setup + data-shape inventory.** Lay down the `datamart/` structure, seed inputs (Synthea symlink, `research/ehi-ignite.db` reference, Josh's vendor catalog mirror, Josh's redacted Epic EHI SQLite dump), then a manifest pass: every distinct data shape that exists across the four repos, one paragraph each, with a pointer into the datamart for the file you can actually open.
