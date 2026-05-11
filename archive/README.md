# archive/ — Frozen Legacy Code

Streamlit prototypes that predated the FastAPI + React stack. Kept as **frozen reference** — historical context for design decisions, useful when porting features into the production app — not as runnable code.

## What lives here

| Subdir | What it was | Replaced by |
|---|---|---|
| `fhir-explorer-streamlit/` | Internal data-review tool: corpus stats, field profiler, timeline, encounter hub | `app/src/pages/FhirCharts/` (React, formerly `pages/Explorer/`) |
| `patient-journey-streamlit/` | Clinician-facing journey app: medication history, condition tracker, safety panel, interaction view, NL search | Folded into Caspian + `app/src/pages/FhirCharts/Journey.tsx` |
| `ehi-atlas-5layer/` | Early Python scaffold for Atlas's multi-source harmonization layer: per-source adapters → silver standardization → gold harmonization with FHIR-native Provenance. Includes Python subsystems, tests, notebooks 02–09, Streamlit pages 02/06/07, the typer CLI, and showcase-patient gold/silver outputs. **Strategic wedge unchanged** — see [`docs/architecture/ATLAS-DATA-MODEL.md`](../docs/architecture/ATLAS-DATA-MODEL.md). Will be rebuilt when the harmonization phase reactivates. | Active focus moved to `lib/extract/` (PDF → FHIR ingestion path) for Phase 1. |
| `design-miro/` | Pre-Atlas Miro-inspired design system — Blue 450 (`#5b76fe`), Roobert PRO, beige canvas, pastel palette, 8–50px radii. | Atlas Agentic Workspaces design tokens — see [`design/DESIGN.md`](../design/DESIGN.md) and [`.claude/handoff/atlas/tokens/`](../.claude/handoff/atlas/tokens/). |
| `ideas-pre-atlas/` | Product spec docs that fed the original (pre-Atlas) IA: PatientJourneyApp, FormatAgnosticIngestion, DataAggregatorWireframes. | Caspian (longitudinal workflow) + `lib/extract/` + Patient Record sub-routes. See [`archive/ideas-pre-atlas/README.md`](./ideas-pre-atlas/README.md). |

## Status

- **Not maintained.** New features go into `api/` + `app/`, not here.
- **Imports may or may not resolve** depending on virtualenv. The shells used to import from `fhir_explorer.parser` and `patient_journey.core` — those modules now live at `lib.fhir_parser` and `lib.clinical` / `lib.sql_on_fhir`. Imports were updated during the refactor so they *can* still run if you `pip install streamlit pandas plotly` and execute from the repo root, but this isn't part of CI.
- **Do not extend.** If you need a feature that exists here, port it into `app/src/` and `api/`.

## Where the load-bearing pieces went

The refactor that produced this archive split the legacy dirs into three:

- Library code → `lib/` (`fhir_parser`, `patient_catalog`, `sql_on_fhir`, `clinical`)
- Reference docs → `docs/architecture/` (`CONTEXT-ENGINEERING.md`, `DATA-DEFINITIONS.md`, `FHIR-EXPLORER-DATA-REVIEW.md`)
- Streamlit shells → here (`archive/`)
