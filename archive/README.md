# archive/ — Frozen Legacy Code

Streamlit prototypes that predated the FastAPI + React stack. Kept as **frozen reference** — historical context for design decisions, useful when porting features into the production app — not as runnable code.

## What lives here

| Subdir | What it was | Replaced by |
|---|---|---|
| `fhir-explorer-streamlit/` | Internal data-review tool: corpus stats, field profiler, timeline, encounter hub | `app/src/pages/Explorer/` (React) |
| `patient-journey-streamlit/` | Clinician-facing journey app: medication history, condition tracker, safety panel, interaction view, NL search | `app/src/pages/PatientJourney/` (React, partial) |
| `ehi-atlas-5layer/` | Early Python scaffold for Atlas's multi-source harmonization layer: per-source adapters → silver standardization → gold harmonization with FHIR-native Provenance. Includes Python subsystems, tests, notebooks 02–09, Streamlit pages 02/06/07, the typer CLI, and showcase-patient gold/silver outputs. **Strategic wedge unchanged** — see [`docs/architecture/ATLAS-DATA-MODEL.md`](../docs/architecture/ATLAS-DATA-MODEL.md). Will be rebuilt when the harmonization phase reactivates. | Active focus moved to `ehi-atlas/ehi_atlas/extract/` (PDF → FHIR ingestion path) for Phase 1. |

## Status

- **Not maintained.** New features go into `api/` + `app/`, not here.
- **Imports may or may not resolve** depending on virtualenv. The shells used to import from `fhir_explorer.parser` and `patient_journey.core` — those modules now live at `lib.fhir_parser` and `lib.clinical` / `lib.sql_on_fhir`. Imports were updated during the refactor so they *can* still run if you `pip install streamlit pandas plotly` and execute from the repo root, but this isn't part of CI.
- **Do not extend.** If you need a feature that exists here, port it into `app/src/` and `api/`.

## Where the load-bearing pieces went

The refactor that produced this archive split the legacy dirs into three:

- Library code → `lib/` (`fhir_parser`, `patient_catalog`, `sql_on_fhir`, `clinical`)
- Reference docs → `docs/architecture/` (`CONTEXT-ENGINEERING.md`, `DATA-DEFINITIONS.md`, `FHIR-EXPLORER-DATA-REVIEW.md`)
- Streamlit shells → here (`archive/`)
