# Archived: EHI Atlas 5-Layer Harmonization Stack

**Archived May 2026.** The original Atlas vision — per-source adapters → silver standardization → gold harmonization with FHIR-native Provenance — was the foundational idea but was set aside once **PDF → FHIR extraction** became the project's wedge. Live development moved to `ehi-atlas/ehi_atlas/extract/` and the Streamlit console at `ehi-atlas/app/`.

This directory preserves the full implementation as a historical record. None of this code is imported by anything live.

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

The PDF → FHIR pipeline (single-pass vision → multi-pass FHIR) reached an evaluable F1 baseline (0.70 weighted F1 on the Cedars health-summary fixture, May 2026) and validated that vision-LLM extraction is the highest-leverage wedge for the EHI Ignite Challenge submission. The 5-layer harmonization vision (cross-source merge, Provenance graph) remains the long-horizon Atlas direction, but is not on the Phase 1 critical path.

The strategic rationale lives in:
- `../../docs/architecture/PDF-PROCESSOR.md` — why vision-first extraction won
- `../../docs/architecture/ATLAS-DATA-MODEL.md` — long-horizon harmonization plan
- `../../docs/architecture/PIPELINE-LOG.md` — experimental evidence

## How to revive any of it

Everything is git-history-stable. To resurrect a piece:

1. Find the file under this directory.
2. `git mv` it back to its original location (mirror the path under `ehi-atlas/`).
3. Re-add the relevant Makefile targets, pyproject `[project.scripts]` entry (if needed), and CLAUDE.md cross-references.

The `archive/` convention (parallel to `archive/fhir-explorer-streamlit/` and `archive/patient-journey-streamlit/`) is the project's standard pattern for retired work.
