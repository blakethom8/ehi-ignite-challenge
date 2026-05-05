# Harmonization Workflow

## Decision

The Data Aggregator needs an explicit harmonization workflow between Source Intake and downstream chart use. Source Intake prepares source material. Harmonization creates a candidate canonical record. Publish Chart decides whether that candidate record should feed FHIR Charts, Clinical Insights, and future clinical products.

The implementation should be scripts-first, with LLM assistance added inside bounded review steps after the deterministic path is stable.

## Why This Matters

The core product promise is not PDF extraction by itself. The core promise is that messy, multi-source EHI becomes a traceable, usable patient record. That requires a durable workflow artifact:

- which sources were used
- when harmonization ran
- which rules and matchers were applied
- which facts were accepted automatically
- which facts need review
- what provenance supports each canonical fact
- what downstream modules are allowed to trust

Without that artifact, the Harmonized Record page is only a live preview. It can be useful, but it does not give the user a clear operational step or a publishable chart state.

## Workflow Model

1. **Prepare sources**
   - User uploads PDFs, portal exports, JSON, CSV, images, or device data.
   - PDFs run through extraction and produce candidate FHIR-like bundles.
   - Structured files are recognized as ready source data.
   - Every source keeps file-level metadata and provenance.

2. **Run harmonization**
   - User starts a harmonization run from the Harmonized Record page.
   - Backend captures an immutable run artifact with source fingerprints, matcher version, candidate facts, review items, and summary counts.
   - This is the first durable boundary between source material and canonical record.

3. **Review candidate record**
   - Automatically accepted facts are visible with provenance.
   - Conflicts and preparation gaps are routed to a review queue.
   - The first version can be deterministic: source preparation issues, same-day lab conflicts, missing extraction, and unsupported files.

4. **Resolve and accept**
   - Later versions should allow human acceptance, rejection, override, and source exclusion.
   - Review decisions should be persisted separately from matcher output so re-running harmonization does not erase user judgment.

5. **Publish canonical snapshot**
   - A published snapshot becomes the read layer for FHIR Charts, Clinical Insights, and agent tools.
   - Publishing should record run ID, timestamp, source set, review state, and storage posture.
   - Prior snapshots remain visible so the application can roll downstream modules back to an earlier chart state.

## LLM Role

LLMs should not own the canonical record. The deterministic scripts should own record creation, validation, provenance, and publish state.

LLMs should assist with bounded ambiguity:

- classify messy PDF notes into likely FHIR resource candidates
- propose term mappings when codes are missing
- explain why two facts may or may not match
- summarize conflicts for the reviewer
- identify missing source context
- repair invalid candidate FHIR into schema-valid resources

Every LLM suggestion should be structured, validated, and reviewable before it changes the canonical record.

## Build Sequence

### V1: Scripted Run Artifact

- Add persisted `harmonization_run` records.
- Capture source fingerprints and matcher version.
- Store candidate facts by resource type.
- Generate deterministic review items.
- Add a `Run harmonization` control to the Harmonized Record page.
- Show last run, readiness, candidate counts, and review counts.

### V2: Review Decisions

- Add accept/reject/override endpoints.
- Persist decisions by run ID and merged reference.
- Separate automatic facts from human-reviewed facts.
- Let Publish Chart depend on unresolved review items.

### V3: Publish Snapshot

- Add a publish endpoint that pins a run as the active canonical chart.
- Wire FHIR Charts and Clinical Insights to the published snapshot first.
- Keep source-level provenance attached to every published fact.

### V4: LLM-Assisted Review

- Add an assistant lane in the review queue.
- LLM output is suggestions only.
- Scripts validate suggestions before they become reviewable changes.

## Principle

Scripts own the record. LLMs help with ambiguity, explanation, and repair.
