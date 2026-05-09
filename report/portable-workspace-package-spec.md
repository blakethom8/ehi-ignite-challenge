# Portable Workspace Package Spec — EHI Atlas

Date: 2026-05-08
Status: build-ready concept spec

## Why this is the next best demo

The strongest demonstration for the EHIgnite submission is not another isolated PDF parser result. It is a portable, patient-owned evidence workspace that can be downloaded, inspected, and handed to another agent system.

This directly proves the core thesis:

> EHI Atlas does not merely summarize records. It creates a reusable evidence environment that makes humans, Claude, Codex, local models, CLI tools, and future clinical agents more effective.

The package is the concrete artifact behind “patient ownership.” A patient should be able to carry a structured workspace, not just a pile of PDFs or a one-time PDF summary.

## Product goal

Create a downloadable `.zip` package for one patient/workspace that contains:

1. Original source inventory and metadata.
2. Prepared/extracted FHIR-compatible facts.
3. Harmonized canonical facts.
4. Provenance and source contribution maps.
5. Conflict and missing-information reports.
6. Human-readable summaries and instructions.
7. Agent-ready context packets.
8. A CLI/review surface that can inspect the package without the full web app.

## User story

As a patient, I want to download my record workspace so I can:

- keep a copy outside any one portal or application
- inspect what each source contributed
- share a scoped packet with a doctor, caregiver, payer, or second-opinion service
- bring the same evidence workspace to Claude, Codex, a local model, or a future medical agent
- avoid starting over with raw PDFs every time I use a new tool

## Strategic positioning

### Not this

> “Our assistant beats Claude.”

### This

> “Structured, provenance-backed evidence makes capable agents better. EHI Atlas creates the workspace that humans and agents can both use.”

## Package format

File name pattern:

```text
ehi-atlas-workspace-<workspace_id>-<YYYYMMDD>.zip
```

Example:

```text
ehi-atlas-workspace-synthea-demo-20260508.zip
```

## Proposed directory structure

```text
ehi-atlas-workspace-<id>/
  README.md
  MANIFEST.json
  PATIENT-SUMMARY.md
  AGENT-INSTRUCTIONS.md

  sources/
    sources.json
    original/
      <source files or source placeholders>
    prepared/
      <per-source extracted/prepared bundles>

  evidence/
    canonical-facts.json
    observations.json
    medications.json
    conditions.json
    allergies.json
    immunizations.json
    encounters.json
    provenance.json
    source-contributions.json
    conflicts.json
    missing-information.json

  fhir/
    harmonized-bundle.json
    source-bundles/
      <source-id>.bundle.json

  packets/
    patient-summary.context.json
    clinician-handoff.context.json
    second-opinion.context.json
    preop-review.context.json

  exports/
    labs.csv
    medications.csv
    conditions.csv
    timeline.csv
    clinician-handoff.md
    patient-readable-summary.md

  cli/
    atlas_workspace.py
    examples.sh
```

## Top-level files

### README.md

Human-readable explanation of the package:

- what the package is
- who owns it
- what sources are included
- how to inspect it
- how to hand it to an agent
- privacy warning
- limitations / not medical advice

Key language:

> This package is a patient-owned evidence workspace. It is designed to be inspected by humans and used by tools. It is not a replacement for clinical judgment.

### MANIFEST.json

Machine-readable package index:

```json
{
  "package_version": "atlas-workspace.v1",
  "workspace_id": "synthea-demo",
  "created_at": "2026-05-08T20:00:00Z",
  "patient": {
    "display": "Synthetic Demo Patient",
    "source": "synthea"
  },
  "source_count": 3,
  "canonical_fact_count": 206,
  "review_item_count": 1,
  "files": [
    {
      "path": "evidence/observations.json",
      "kind": "observations",
      "description": "Canonical lab/vital observations with provenance references"
    }
  ],
  "privacy": {
    "contains_phi": false,
    "demo_data": true,
    "sharing_warning": "Review before sharing outside your care team."
  }
}
```

### AGENT-INSTRUCTIONS.md

Instructions for Claude/Codex/local agents using the package.

Should say:

- read `MANIFEST.json` first
- do not infer unsupported facts from raw files when structured evidence exists
- cite `provenance.json` or source contribution IDs for important claims
- use `missing-information.json` to disclose gaps
- prefer `packets/*.context.json` for focused tasks
- if uncertain, say what evidence is missing

### PATIENT-SUMMARY.md

Short plain-language record overview:

- sources included
- key facts
- missing information
- conflicts requiring review
- suggested next questions

This is both useful and a demo artifact.

## Evidence files

### canonical-facts.json

Top-level fact index across resource types.

Suggested shape:

```json
{
  "facts": [
    {
      "fact_id": "obs-creatinine-2026-04-22",
      "resource_type": "Observation",
      "display": "Creatinine",
      "date": "2026-04-22",
      "value": "1.04 mg/dL",
      "status": "accepted",
      "source_refs": ["src-quest-pdf:p2", "src-cedars-fhir:Observation/123"],
      "provenance_refs": ["prov-001", "prov-002"],
      "review_state": "auto_accepted"
    }
  ]
}
```

### provenance.json

Shows where each fact came from and how it was transformed.

```json
{
  "provenance": [
    {
      "provenance_id": "prov-001",
      "fact_id": "obs-creatinine-2026-04-22",
      "source_id": "src-quest-pdf",
      "source_label": "Quest lab PDF",
      "locator": "page=2;bbox=72,574,540,590",
      "method": "multipass-fhir lab_observations",
      "confidence": 0.94
    }
  ]
}
```

### source-contributions.json

Answers:

- what did each source contribute?
- which facts were shared?
- which were unique?
- what conflicts exist?

This is the key harmonization proof artifact.

### conflicts.json

Review queue for conflicting/ambiguous facts.

Examples:

- same-day lab value mismatch
- duplicate medication with uncertain status
- condition appears active in one source and historical in another
- source parsing failed

### missing-information.json

Make absence explicit.

Examples:

- no recent CBC found
- no allergy documentation found
- no active medication list from primary care source
- no source includes surgery type

## Agent packets

Agent packets are focused context bundles that can be handed to Claude, Codex, local models, or our own assistant.

Example:

```json
{
  "packet_version": "atlas-context.v1",
  "purpose": "second-opinion",
  "audience": "clinician",
  "workspace_id": "synthea-demo",
  "instructions": [
    "Use only facts in this packet unless explicitly asked to inspect raw sources.",
    "Cite source_refs for important claims.",
    "Mention missing_information items relevant to the question."
  ],
  "facts": [],
  "provenance": [],
  "missing_information": [],
  "conflicts": []
}
```

## CLI scope

The CLI should work against an unpacked workspace package.

Initial command surface:

```bash
python cli/atlas_workspace.py manifest
python cli/atlas_workspace.py sources
python cli/atlas_workspace.py facts --type Observation --search creatinine
python cli/atlas_workspace.py timeline --kind labs
python cli/atlas_workspace.py provenance <fact_id>
python cli/atlas_workspace.py conflicts
python cli/atlas_workspace.py missing
python cli/atlas_workspace.py packet second-opinion
python cli/atlas_workspace.py export --format markdown --purpose clinician-handoff
```

A future installed CLI could become:

```bash
atlas workspace inspect <zip-or-dir>
atlas facts search <zip-or-dir> creatinine
atlas packet export <zip-or-dir> --purpose second-opinion
```

## Minimal V1 implementation

V1 does not need to solve everything. It should produce a credible demo package for one existing collection.

### Inputs

- `synthea-demo` collection or one upload-derived collection.
- Existing harmonization service outputs.
- Existing source bundles and extracted PDF bundles where available.

### V1 outputs

Required:

- `README.md`
- `MANIFEST.json`
- `AGENT-INSTRUCTIONS.md`
- `PATIENT-SUMMARY.md`
- `sources/sources.json`
- `evidence/canonical-facts.json`
- `evidence/provenance.json`
- `evidence/source-contributions.json`
- `evidence/conflicts.json`
- `evidence/missing-information.json`
- `packets/second-opinion.context.json`
- `exports/clinician-handoff.md`
- `.zip`

Nice-to-have:

- `cli/atlas_workspace.py`
- labs/meds/conditions CSVs
- `fhir/harmonized-bundle.json`

## V1 build target

Command:

```bash
python scripts/export_workspace_package.py --collection synthea-demo --out data/workspace-packages/synthea-demo.zip
```

Alternative API endpoint:

```text
GET /api/harmonize/{collection_id}/export-workspace.zip
```

## Validation checks

- Zip opens.
- `MANIFEST.json` parses.
- All manifest file paths exist.
- No absolute local paths in output.
- No private PHI in demo package.
- Agent instructions are present.
- At least one source contribution and provenance example included.
- Package can be handed to Claude/Codex as a single zip.

## How this should appear in the report

Short report language:

> EHI Atlas can export a patient-owned workspace package: a portable zip containing structured facts, provenance, source contributions, conflicts, missing-information signals, and agent-ready context packets. This lets the patient carry usable evidence across tools, not just download raw records. The same package can be inspected by a human, queried by a CLI, or handed to Claude, Codex, a local model, or a future clinical agent.

