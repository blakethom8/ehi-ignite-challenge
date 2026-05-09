# Portable Workspace Package Queue

Goal: build the demo artifact that proves EHI Atlas is a patient-owned, portable evidence workspace — not just a web app or assistant.

## P0 — Build the package exporter

### PW-P0-01 — Export `synthea-demo` workspace zip

Build script:

```bash
python scripts/export_workspace_package.py --collection synthea-demo --out data/workspace-packages/synthea-demo.zip
```

Required contents:

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

Acceptance:

- zip opens
- manifest paths exist
- no absolute local paths
- demo data only
- includes at least one provenance/source contribution example

### PW-P0-02 — Add agent instructions

Create durable `AGENT-INSTRUCTIONS.md` template.

Must instruct external agents to:

- read `MANIFEST.json` first
- use structured evidence before raw files
- cite provenance/source refs
- disclose missing information
- avoid unsupported clinical claims

### PW-P0-03 — Add package validation test

Test:

```bash
python scripts/validate_workspace_package.py data/workspace-packages/synthea-demo.zip
```

Checks:

- manifest JSON parses
- all referenced files exist
- no absolute paths
- required files present
- privacy flags present

## P1 — CLI review surface

### PW-P1-01 — Add minimal package CLI

Inside package:

```bash
python cli/atlas_workspace.py manifest
python cli/atlas_workspace.py sources
python cli/atlas_workspace.py facts --search creatinine
python cli/atlas_workspace.py provenance <fact_id>
python cli/atlas_workspace.py conflicts
python cli/atlas_workspace.py missing
python cli/atlas_workspace.py packet second-opinion
```

Acceptance:

- commands work against unpacked package directory
- output is plain text or JSON
- no app server required

### PW-P1-02 — Add installed/project CLI command

Optional project-level command:

```bash
python -m scripts.workspace_cli inspect data/workspace-packages/synthea-demo.zip
```

or formal package CLI later:

```bash
atlas workspace inspect <zip-or-dir>
```

## P1 — C-CDA inclusion

### PW-P1-03 — Add a C-CDA sample source to the package demo

Use safe/public/synthetic C-CDA if available.

Acceptance:

- source appears in `sources/sources.json`
- parsed or staged facts appear in evidence layer
- package demonstrates C-CDA as input, not intelligence layer

## P2 — Agent comparison

### PW-P2-01 — Run Claude raw vs package comparison

Arms:

1. raw files only
2. workspace package only
3. package + raw files

Tasks:

- patient summary
- clinician handoff
- source contribution
- chart-ready labs
- self-audit

Score using `report/agent-comparison-protocol.md`.

### PW-P2-02 — Run Codex raw vs package comparison

Same as Claude comparison.

### PW-P2-03 — Add evaluation table to report

Add compact table to Phase 1 PDF/report:

- traceability
- source contribution
- missing info
- chart readiness
- narrative synthesis

## References

- `report/portable-workspace-package-spec.md`
- `report/agent-comparison-protocol.md`
- `report/raw-agent-vs-structured-eval-plan.md`
- `report/strategy-scratchpad.md`
