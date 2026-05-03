# CLAUDE.md — `ehi-atlas/` Development Zone

> The development surface for the EHI Atlas data-aggregation platform: research notes, prototypes, the corpus bench (bronze/silver/gold + raw sources), end-to-end notebooks, and an in-development Python package. Reads from `lib/` and the production `data/` drops; never modifies them.

---

## What this directory is for

`ehi-atlas/` is the **development zone**. The application zone (`api/`, `app/`, `lib/`, production `data/`) builds and ships; this zone is where we prototype, study, benchmark, and stage data — without touching the runtime app.

| Subdir | Purpose |
|---|---|
| `corpus/` | The data bench. `_sources/` (raw drops), `bronze/` (canonical staging), `silver/` (FHIR-standardized), `gold/` (merged + Provenance), `reference/` (terminology snapshots). See `corpus/README.md`. |
| `ehi_atlas/` | In-development Python package — adapters, extract, harmonize, standardize, terminology, audit. Imports from `lib/` for FHIR parsing and SQL-on-FHIR. |
| `notebooks/` | End-to-end Jupyter notebooks: bronze → silver → gold pipelines, vision extraction, code mapping, temporal/identity merge. |
| `prototypes/` | Self-contained prototype dirs prefixed `josh-*` (faithful ports of Josh Mandel's pipelines) or `atlas-*` (Atlas-specific harmonization experiments). See `prototypes/README.md`. |
| `notes/` | Research notes, primarily the multi-session `josh-stack-deep-dive/`. Code excerpts + commentary belong here; strategic narrative lives in the Chief vault (see below). |
| `scripts/` | Utility scripts for corpus build, validation, ad-hoc data prep. |
| `tests/` | Tests for `ehi_atlas/`. Library-code tests live at `lib/tests/`; FastAPI tests at `api/tests/`. |
| `app/`, `docs/` | Atlas-specific UI prototype + per-package design docs. |

## What does NOT live here

- **Production runtime code.** That's `api/`, `app/`, `lib/`, `data/`, `deploy/` at the repo root.
- **Production runtime data.** `data/synthea-samples/`, `data/sof.db`, `data/patient-context/` belong to the production app and ship in Docker.
- **Strategic narrative.** That's in the Chief vault. See cross-references below.

## Promotion path

If a prototype or notebook matures into production-grade code:

- **Library code** (FHIR parsers, SQL-on-FHIR engines, clinical classifiers) → `lib/<module>/`. Add a one-line note in `prototypes/<topic>/README.md` pointing at the new home, then archive or delete the prototype.
- **API endpoints** → `api/routers/`, `api/core/`.
- **UI features** → `app/src/`.
- **Adapters / harmonization logic** → may stay in `ehi_atlas/` permanently if it's the package's core responsibility.

The legacy Streamlit shells in `archive/fhir-explorer-streamlit/` and `archive/patient-journey-streamlit/` are the historical record of the previous "everything in one folder" pattern. Don't replicate it — keep prototypes scoped, then graduate.

## Working conventions

1. **Reuse, don't rebuild.** Always import from `lib/` for FHIR parsing, models, SQL-on-FHIR, drug classification. Never copy parser code.
2. **Prototypes are scoped.** Each `prototypes/<topic>/` is self-contained: `README.md`, source, optional tests. Reads from `corpus/_sources/`, writes to `corpus/bronze/` or `corpus/silver/`.
3. **Notebooks commit cleared outputs** unless the output *is* the artifact (e.g. a benchmark table).
4. **Personal-source data is gitignored.** Anything under `corpus/_sources/blake-cedars/raw/`, `devon-cedars/raw/`, `cedars-portal-pdfs/raw/` stays local — see the privacy gate in `corpus/README.md`.
5. **Don't pollute `data/`.** That directory is reserved for the production app's runtime data.

## Cross-references

### Repo-level
- Repo CLAUDE.md (product strategy, build order, top-level layout) — `../CLAUDE.md`
- Application zone library code — `../lib/README.md`
- Architecture docs — `../docs/architecture/` (`ATLAS-DATA-MODEL.md`, `CONTEXT-ENGINEERING.md`, `DATA-DEFINITIONS.md`, `DEPLOYMENT.md`, `tracing.md`)

### Chief vault (qualitative research lives here, not in this repo)
- `~/Chief/20-projects/ehi-ignite-challenge/research/` — strategy, prior-art notes, screenshots, unzipped artifacts
- `~/Chief/20-projects/ehi-ignite-challenge/architecture/` — full design specs (longer than `docs/architecture/`)
- `~/Chief/20-projects/ehi-ignite-challenge/EXECUTION-PLAN.md` — phased plan toward 2026-05-13 Phase 1 deadline

**Rule of thumb:** if it has code, numbers, or repro steps, it lives here. If it has narrative, strategy, or stakeholder context, it lives in the vault.

## North star

*"Clinicians don't need more records. They need the right 5 facts in 30 seconds."*

Atlas's defensible wedge is the Provenance graph (gold → silver → bronze, surfaced in the UI). Everything in this dev zone should serve that wedge — cross-source merge, conflict detection, multi-format ingestion, terminology harmonization. Don't drift into building a generic FHIR browser or a chat-only assistant.
