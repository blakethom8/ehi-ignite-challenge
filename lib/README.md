# lib/ — Shared Production Library Code

Production library code imported by `api/`, `ehi-atlas/`, `scripts/`, and prototypes alike. Everything here is part of the **application zone** — it runs in production, ships in Docker images, and is covered by tests.

## What lives here

| Module | Purpose | Imported by |
|---|---|---|
| `lib.fhir_parser` | FHIR R4 bundle parser + dataclass models (`PatientRecord`, `Condition`, `Medication`, etc.) | `api/`, `ehi-atlas/`, `scripts/` |
| `lib.patient_catalog` | Single-patient stats + corpus loader | `api/`, `scripts/` |
| `lib.sql_on_fhir` | SQL-on-FHIR v2 engine: ViewDefinition → SQLite, enrichments, derivations | `api/core/sof_materialize.py`, `api/core/sof_tools.py` |
| `lib.clinical` | Drug classifier, episode detector, interaction checker, patient loader | `api/core/`, `api/routers/` |

## Conventions

- Each submodule is a regular Python package with `__init__.py`.
- Import style: `from lib.fhir_parser.bundle_parser import parse_bundle`.
- No `sys.path` hacks. The repo root is on `sys.path` when running `uvicorn` from the project directory, which makes `lib.*` importable directly.
- Tests for library modules live in `lib/tests/`. Tests for the FastAPI app live in `api/tests/`.

## Where this code came from

Pre-refactor the same modules lived in two top-level dirs (`fhir_explorer/`, `patient-journey/`) that mixed library code with legacy Streamlit apps. The library code graduated here; the Streamlit shells were archived under `archive/`.

## What does **not** live here

- The FastAPI app (`api/`) — that's the application server, not a library.
- Research notes, prototypes, datamart artifacts (`ehi-atlas/`) — that's the **development zone**.
- Production runtime data (`data/synthea-samples/`, `data/sof.db`) — that's data, not code.
