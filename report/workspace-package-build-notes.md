# Workspace Package Build Notes

Date: 2026-05-08
Status: V1 exporter/validator/CLI implemented and smoke-tested

## What exists now

The portable EHI Atlas workspace package is no longer just a spec. The repo now has a working scripts-first implementation.

### Exporter

```bash
python3 scripts/export_workspace_package.py \
  --collection synthea-demo \
  --out data/workspace-packages/synthea-demo.zip
```

Also tested with uploaded synthetic PDF lab package:

```bash
python3 scripts/export_workspace_package.py \
  --collection smoke-codex-upload-2026 \
  --include-originals \
  --out data/workspace-packages/smoke-codex-upload-2026.zip
```

### Validator

```bash
python3 scripts/validate_workspace_package.py data/workspace-packages/synthea-demo.zip
python3 scripts/validate_workspace_package.py data/workspace-packages/smoke-codex-upload-2026.zip
```

Both currently pass.

## Generated packages

### `data/workspace-packages/synthea-demo.zip`

- 2 source FHIR snapshots
- 181 canonical facts
- 100 Observations
- 30 Encounters
- 12 Conditions
- 11 Immunizations
- 10 MedicationRequests
- 11 Procedures
- 7 DiagnosticReports
- 4 conflict/review signals
- 1 missing-information signal
- privacy flags: demo data, no PHI

### `data/workspace-packages/smoke-codex-upload-2026.zip`

- 1 synthetic uploaded PDF lab source
- includes original PDF and prepared extracted bundle
- 12 canonical facts
- 12 Observations
- 0 conflicts
- 3 missing-information signals
- privacy flags: demo data, no PHI

## Package contents

Each package includes:

```text
README.md
MANIFEST.json
AGENT-INSTRUCTIONS.md
PATIENT-SUMMARY.md
sources/sources.json
sources/prepared/*
evidence/canonical-facts.json
evidence/provenance.json
evidence/source-contributions.json
evidence/conflicts.json
evidence/missing-information.json
fhir/harmonized-bundle.json
packets/second-opinion.context.json
exports/clinician-handoff.md
exports/labs.csv
cli/atlas_workspace.py
```

## CLI smoke test

After unzipping:

```bash
python cli/atlas_workspace.py manifest
python cli/atlas_workspace.py sources
python cli/atlas_workspace.py facts --type Observation --search glucose
python cli/atlas_workspace.py missing
python cli/atlas_workspace.py packet second-opinion
```

## Validation gates run

```bash
python3 -m py_compile scripts/export_workspace_package.py scripts/validate_workspace_package.py
python3 scripts/export_workspace_package.py --collection synthea-demo --out data/workspace-packages/synthea-demo.zip
python3 scripts/validate_workspace_package.py data/workspace-packages/synthea-demo.zip
python3 scripts/export_workspace_package.py --collection smoke-codex-upload-2026 --include-originals --out data/workspace-packages/smoke-codex-upload-2026.zip
python3 scripts/validate_workspace_package.py data/workspace-packages/smoke-codex-upload-2026.zip
```

## Remaining improvements

1. Add formal unit tests for exporter/validator.
2. Add C-CDA sample source to a package.
3. Improve conflict detection beyond simple same-concept/date/value checks.
4. Build a direct raw-files vs package evaluation harness.
5. Run Claude/Codex comparisons and add scoring table to the Phase 1 report.
6. Wire exporter into API endpoint for web UI download.

## 2026-05-08 21:28 heartbeat update

Added automated tests and a comparison-run scaffold.

### New files

- `lib/tests/test_workspace_package.py`
  - tests synthea-demo package export + validation
  - tests synthetic PDF package export with original PDF included
- `scripts/prepare_agent_comparison.py`
  - creates reproducible raw-vs-package comparison folders
  - writes standard prompts and arm instructions
  - can copy raw sources and package inputs into each arm
- `lib/tests/test_agent_comparison_prepare.py`
  - verifies comparison run creation

### Verification

```bash
.venv/bin/python -m py_compile \
  scripts/export_workspace_package.py \
  scripts/validate_workspace_package.py \
  scripts/prepare_agent_comparison.py \
  lib/tests/test_workspace_package.py \
  lib/tests/test_agent_comparison_prepare.py

.venv/bin/python -m pytest \
  lib/tests/test_workspace_package.py \
  lib/tests/test_agent_comparison_prepare.py -q
# 3 passed
```

### Generated comparison run

```bash
.venv/bin/python scripts/prepare_agent_comparison.py \
  --collection synthea-demo \
  --package data/workspace-packages/synthea-demo.zip \
  --out data/agent-comparisons/synthea-demo-v1 \
  --copy-inputs
```

Created arms:

- `raw`
- `package`
- `package-plus-raw`

Created prompts:

- patient summary
- clinician handoff
- source contribution
- chart-ready labs
- agent audit

## 2026-05-08 21:43 heartbeat update

Added safe C-CDA source packaging support.

### New capability

`export_workspace_package.py` now accepts repeatable extra source files:

```bash
.venv/bin/python scripts/export_workspace_package.py \
  --collection synthea-demo \
  --extra-source "ehi-atlas/corpus/_sources/josh-ccdas/raw/Cerner Samples/problems-and-medications.xml" \
  --out data/workspace-packages/synthea-demo-with-ccda.zip
```

The exporter classifies `.xml` files as `ccda-xml`, packages them under `sources/original/`, and records them in `sources/sources.json` with `original_packaged_path`.

### Generated package

- `data/workspace-packages/synthea-demo-with-ccda.zip`
  - 2 FHIR snapshots
  - 1 safe/public C-CDA XML source from the Josh C-CDA sample corpus
  - 181 canonical facts from the FHIR snapshots
  - C-CDA appears as a first-class input source in the package manifest/source inventory

### Verification

```bash
.venv/bin/python -m py_compile scripts/export_workspace_package.py
.venv/bin/python scripts/validate_workspace_package.py data/workspace-packages/synthea-demo-with-ccda.zip
.venv/bin/python -m pytest lib/tests/test_workspace_package.py lib/tests/test_agent_comparison_prepare.py -q
# 4 passed
```

### Notes

This is C-CDA inclusion, not full C-CDA normalization yet. The next improvement is to add a lightweight C-CDA adapter that extracts medication/problem/allergy section entries into FHIR-compatible facts so the C-CDA contributes to `canonical-facts.json`, not just the source inventory.

## 2026-05-08 21:58 heartbeat update

Added lightweight C-CDA normalization into canonical package facts.

### New capability

The package exporter now performs conservative C-CDA extraction for XML sources:

- Problem List sections (`LOINC 11450-4`) → FHIR-compatible `Condition` facts
- Medications sections (`LOINC 10160-0`) → FHIR-compatible `MedicationRequest` facts
- CDA narrative references are resolved where possible so medications/problems have usable display text
- Source/provenance refs preserve the C-CDA source id

This is intentionally not a full CDA converter. It is a lightweight package-demo adapter that proves C-CDA can contribute structured facts into the same evidence layer as FHIR/PDF sources.

### Updated generated package

`data/workspace-packages/synthea-demo-with-ccda.zip` now contains:

- 3 sources: 2 FHIR snapshots + 1 C-CDA XML
- 192 canonical facts
- 17 Conditions, including C-CDA problem-list facts
- 16 MedicationRequests, including C-CDA medication facts
- C-CDA provenance/source references in `evidence/provenance.json`

### Verification

```bash
.venv/bin/python -m py_compile scripts/export_workspace_package.py scripts/validate_workspace_package.py scripts/prepare_agent_comparison.py lib/tests/test_workspace_package.py lib/tests/test_agent_comparison_prepare.py
.venv/bin/python scripts/validate_workspace_package.py data/workspace-packages/synthea-demo-with-ccda.zip
.venv/bin/python -m pytest lib/tests/test_workspace_package.py lib/tests/test_agent_comparison_prepare.py -q
# 4 passed
```

## 2026-05-08 22:13 heartbeat update

Wired portable workspace export into API and UI.

### API

Added endpoint:

```http
GET /api/harmonize/{collection_id}/export-workspace
GET /api/harmonize/{collection_id}/export-workspace?include_demo_ccda=true
```

Behavior:

- builds the package on demand via `scripts.export_workspace_package.build_package`
- returns `application/zip`
- returns 404 for unknown collections
- can include the safe demo C-CDA source for the Synthea demo

### UI

Added a **Download workspace** button to the Harmonized Record view header. For the Synthea fixture, the link includes the demo C-CDA source:

```text
/api/harmonize/synthea-demo/export-workspace?include_demo_ccda=true
```

For other active collections it downloads the active collection package.

### Tests / verification

Added `api/tests/test_workspace_export_api.py` covering:

- package download for `synthea-demo`
- optional demo C-CDA inclusion
- 404 on unknown collection

Verification run:

```bash
.venv/bin/python -m py_compile api/routers/harmonize.py api/tests/test_workspace_export_api.py
.venv/bin/python -m pytest api/tests/test_workspace_export_api.py lib/tests/test_workspace_package.py lib/tests/test_agent_comparison_prepare.py -q
# 7 passed

cd app && npm run build
# success
```

## 2026-05-08 22:28 heartbeat update

Ran the first full raw-vs-package agent comparison.

### Comparison run

Prepared and executed:

- `data/agent-comparisons/synthea-ccda-v1/arms/raw/outputs.md`
- `data/agent-comparisons/synthea-ccda-v1/arms/package/outputs.md`
- `data/agent-comparisons/synthea-ccda-v1/arms/package-plus-raw/outputs.md`

Created scorecard:

- `data/agent-comparisons/synthea-ccda-v1/scorecard.md`

### Result

The comparison supports the core hypothesis: prepared, provenance-backed evidence made outputs more traceable, reusable, source-aware, and complete than raw-file reading alone.

Average scores:

| Arm | Average |
|---|---:|
| Raw | 3.56 |
| Package | 4.67 |
| Package + raw | 5.00 |

### Key finding

Raw FHIR reading produced a good narrative, but package-based work surfaced structured source contribution, explicit missing allergy signal, four lipid conflicts, provenance IDs, and C-CDA-only problem/medication facts. The strongest operating model is package first + raw verification for gaps.
