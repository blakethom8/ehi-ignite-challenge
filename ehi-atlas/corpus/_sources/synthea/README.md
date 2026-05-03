# _sources/synthea/

**Source name (canonical):** `synthea`
**Format:** FHIR R4 (Bundle JSON)
**License:** Apache-2.0
**Consent posture:** `open`
**Acquisition mode:** Already on disk (existing repo's `data/synthea-samples/`)

## What this source is

[Synthea](https://synthea.mitre.org/) is MITRE's open-source synthetic patient generator. It produces fully synthetic FHIR R4 records covering decades of simulated clinical history. The existing repo already has 1,180 generated patients at `~/Repo/ehi-ignite-challenge/data/synthea-samples/`.

## How to acquire

```bash
# Already on disk — no download required.
# To regenerate (not needed for Phase 1):
#   git clone https://github.com/synthetichealth/synthea
#   cd synthea && ./run_synthea -p 1180
```

## Reproduction recipe

The Synthea patients used by EHI Atlas are a snapshot of the existing repo's samples. We pin to a specific subset (the showcase patient candidate plus a handful of negative controls) by copying their bundle files into `_sources/synthea/raw/` during corpus-build. The `CHOSEN.md` file (written by sub-agent task 1.2) documents which patient IDs are pinned.

## Showcase patient criteria

The selected Synthea patient must have:

- ≥10 Encounters
- ≥30 Observations
- ≥5 MedicationRequests
- ≥2 attachments / clinical notes (to support free-text extraction artifact)
- Active anticoagulation OR active diabetes OR active hypertension (relevant for surgical risk demo)
- ≥3 Conditions in the active problem list

See `CHOSEN.md` (created by task 1.2) for the chosen ID and rationale.

## Privacy gate

Not applicable — Synthea is fully synthetic.

## Contents of this directory

```
_sources/synthea/
├── README.md           # this file
├── CHOSEN.md           # which patient is the showcase + why (written by 1.2)
└── raw/                # symlink or copy of the chosen patient bundles
    └── <patient-id>.json
```

## Used in tracker tasks

- **1.2** Pick showcase Synthea patient
- **2.1** Build Synthea adapter (passthrough)
