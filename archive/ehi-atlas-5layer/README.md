# Archived: EHI Atlas 5-Layer Harmonization Scaffold

**Archived May 2026.** The strategic wedge is unchanged — multi-source harmonization with FHIR-native Provenance is still the Atlas direction (see [`../../docs/architecture/ATLAS-DATA-MODEL.md`](../../docs/architecture/ATLAS-DATA-MODEL.md)). What was archived is the **early Python scaffold** for that vision — per-source adapters → silver standardization → gold harmonization, built before the ingestion path had been stress-tested. Phase 1 demanded one ingestion path that actually worked under load (PDF → FHIR), and the scaffold's silver/gold output paths and Streamlit pages were entangling that work.

This directory preserves the full scaffold as a reference for when the harmonization phase reactivates. Nothing live imports from here.

## What's here

```
archive/ehi-atlas-5layer/
├── ehi_atlas/                 ← Python subsystems for the 5-layer pipeline
│   ├── adapters/              ← per-source ingest (synthea, ccda, epic_ehi, lab_pdf, synthea_payer)
│   ├── standardize/           ← bronze → silver (FHIR R4 + USCDI/CARIN BB profiles)
│   ├── harmonize/             ← silver → gold (identity, code mapping, temporal,
│   │                            condition/medication/observation merge, conflict
│   │                            detection, Provenance, orchestrator)
│   ├── terminology/           ← RxNorm loader + terminology helpers
│   ├── audit/                 ← (was empty)
│   └── cli.py                 ← `ehi-atlas` typer CLI (corpus / ingest / standardize / extract / harmonize / pipeline)
│
├── tests/                     ← matching test suites
│   ├── adapters/
│   ├── harmonize/
│   ├── standardize/
│   └── fixtures/
│
├── notebooks/                 ← end-to-end pipeline notebooks (02–09)
│   ├── 02_layer2_synthea_standardize.ipynb
│   ├── 03_layer2b_vision_extraction.ipynb
│   ├── 04_layer3_code_mapping.ipynb
│   ├── 05_layer3_temporal_and_identity.ipynb
│   ├── 06_layer3_condition_merge_artifact_1.ipynb
│   ├── 07_layer3_medication_artifact_2.ipynb
│   ├── 08_layer3_observation_artifact_5.ipynb
│   └── 09_orchestrator_end_to_end.ipynb
│
├── app_pages/                 ← Streamlit pages for the 5-layer console
│   ├── 02_Standardize.py
│   ├── 06_Harmonize.py
│   └── 07_Gold_and_Provenance.py
├── app_components/
│   └── pipeline_diagram.py    ← graphviz pipeline-stage diagram
│
├── corpus/                    ← gold + silver outputs from the showcase patient
│   ├── gold/patients/rhett759/   (manifest, bundle, provenance.ndjson)
│   ├── silver/                   (synthea, rhett759 bundles)
│   └── handcrafted-crosswalk/    (showcase code-mapping crosswalk)
│
├── docs/                      ← operating docs for the 5-layer pipeline
│   ├── ADAPTER-CONTRACT.md
│   ├── CROSSWALK-WORKFLOW.md
│   ├── FHIR-CONVERTER-SETUP.md
│   ├── INTEGRATION.md
│   ├── PROVENANCE-SPEC.md
│   └── mapping-decisions.md
│
├── scripts/
│   └── stage-bronze.py        ← Phase-1 manual bronze staging
│
├── BUILD-TRACKER.md           ← build-state ledger for the 5-layer plan (43 KB)
├── BUILD-ORCHESTRATION.md     ← meta-doc on how the 5-layer build was organized
└── prototypes-README.md       ← old `prototypes/` README (referenced data-research/ paths)
```

## Why it was archived

This was a *scoping* decision, not a strategic pivot:

- **Strategic wedge — unchanged:** multi-source harmonization with the Provenance graph is still the Atlas direction. The full design lives at `../../docs/architecture/ATLAS-DATA-MODEL.md`.
- **Phase 1 demands depth on one ingestion path.** The PDF → FHIR pipeline reached an evaluable F1 baseline (0.70 weighted F1 on the Cedars health-summary fixture, May 2026); that's the path most directly relevant to the EHI Ignite Challenge submission.
- **The scaffold was getting in the way.** Silver/gold output paths assumed a five-source bronze world that wasn't being kept in sync; the harmonize/orchestrator was stub-heavy; the Streamlit pages displayed silver/gold tiers that the live PDF flow doesn't produce.

When the harmonization phase reactivates (after Phase 1, or once a second ingestion path matures), this scaffold is the reference for shape and Provenance Extension URLs — but the implementation will be rebuilt against the production parser, not lifted wholesale.

Strategic / decision context:
- `../../docs/architecture/ATLAS-DATA-MODEL.md` — full harmonization plan, Provenance as wedge
- `../../docs/architecture/PDF-PROCESSOR.md` — why vision-first extraction won the current phase
- `../../docs/architecture/PIPELINE-LOG.md` — experimental evidence

## How to revive any of it

Everything is git-history-stable. To resurrect a piece:

1. Find the file under this directory.
2. `git mv` it back to its original location (mirror the path under `ehi-atlas/`).
3. Re-add the relevant Makefile targets, pyproject `[project.scripts]` entry (if needed), and CLAUDE.md cross-references.

The `archive/` convention (parallel to `archive/fhir-explorer-streamlit/` and `archive/patient-journey-streamlit/`) is the project's standard pattern for retired work.
