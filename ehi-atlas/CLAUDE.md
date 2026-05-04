# CLAUDE.md — `ehi-atlas/` Development Zone

> The development surface for the EHI Atlas data-aggregation platform. Active focus: **PDF → FHIR extraction**. Reads from `lib/` and the production `data/` drops; never modifies them.

---

## What this directory is for

`ehi-atlas/` is the **development zone**. The application zone (`api/`, `app/`, `lib/`, production `data/`) builds and ships; this zone is where we prototype, study, benchmark, and stage data — without touching the runtime app.

| Subdir | Purpose |
|---|---|
| `ehi_atlas/extract/` | PDF→FHIR extraction framework — `pipelines/` (Protocol + registry), `bake_off.py` (architecture comparison harness), `eval.py` (ground-truth scoring with findable-only filter + GT dedup), `pdf.py` (Anthropic + Google AI Studio backends). See `pipelines/README.md` for the contributor guide. |
| `app/` | Streamlit console for the Atlas data platform. Pages: Overview, Sources & Bronze, **PDF Lab** (single-PDF live extraction), **PDF Compare** (vision-LLM backend A/B), **Pipeline Bakeoff** (extraction-architecture comparison with eval-harness scoring). |
| `corpus/` | The data bench. `_sources/` (raw drops), `bronze/` (canonical staging), `reference/` (terminology snapshots — LOINC, RxNorm). See `corpus/README.md`. |
| `notes/` | Research notes — primarily the Josh-Mandel-stack data lane. |
| `scripts/` | Utility scripts (privacy-gate validation). |
| `tests/` | Tests for `ehi_atlas/extract/`. Library-code tests live at `lib/tests/`; FastAPI tests at `api/tests/`. |

## What does NOT live here

- **Production runtime code.** That's `api/`, `app/`, `lib/`, `data/`, `deploy/` at the repo root.
- **Production runtime data.** `data/synthea-samples/`, `data/sof.db`, `data/patient-context/` belong to the production app and ship in Docker.
- **Strategic narrative.** That's in the Chief vault. See cross-references below.

## Archived: 5-layer harmonization stack

The original Atlas vision (per-source adapters → silver standardization → gold harmonization with FHIR-native Provenance) was archived in May 2026 once PDF → FHIR became the wedge. The full implementation — `ehi_atlas/{adapters,standardize,harmonize,terminology,audit}/`, the typer CLI, the 5-layer Streamlit pages (Standardize, Harmonize, Gold & Provenance), notebooks 02–09, the showcase silver/gold outputs — lives at [`../archive/ehi-atlas-5layer/`](../archive/ehi-atlas-5layer/). Nothing live imports from there.

## Promotion path

If extraction-framework code matures into production-grade code:

- **Library code** (FHIR parsers, SQL-on-FHIR engines, clinical classifiers) → `lib/<module>/`.
- **API endpoints** → `api/routers/`, `api/core/`.
- **UI features** → `app/src/`.

The legacy Streamlit shells in `archive/fhir-explorer-streamlit/` and `archive/patient-journey-streamlit/` are the historical record of the previous "everything in one folder" pattern. Don't replicate it — keep work scoped, then graduate.

## Working conventions

1. **Reuse, don't rebuild.** Always import from `lib/` for FHIR parsing, models, SQL-on-FHIR, drug classification. Never copy parser code.
2. **Personal-source data is gitignored.** Anything under `corpus/_sources/blake-cedars/raw/`, `devon-cedars/raw/`, `cedars-portal-pdfs/raw/` stays local — see the privacy gate in `corpus/README.md`.
3. **Don't pollute `data/`.** That directory is reserved for the production app's runtime data.

## Cross-references

### Repo-level
- Repo CLAUDE.md (product strategy, build order, top-level layout) — `../CLAUDE.md`
- Application zone library code — `../lib/README.md`
- Architecture docs — `../docs/architecture/`:
    - `PDF-PROCESSOR.md` — PDF → FHIR pipeline decisions, bake-off results, vision-wins evidence ⭐
    - `PIPELINE-LOG.md` — running experiment journal (bake-off tables, prompt iterations, model swaps) ⭐
    - `ATLAS-DATA-MODEL.md` — top-level data-layer decisions (FHIR R4 + USCDI as canonical, Provenance as wedge)
    - `CONTEXT-ENGINEERING.md` — 5-layer LLM context pipeline
    - `DATA-DEFINITIONS.md` — data model reference
    - `DEPLOYMENT.md`, `tracing.md` — operational

### Chief vault (qualitative research lives here, not in this repo)
- `~/Chief/20-projects/ehi-ignite-challenge/research/` — strategy, prior-art notes, screenshots, unzipped artifacts
- `~/Chief/20-projects/ehi-ignite-challenge/architecture/` — full design specs (longer than `docs/architecture/`)
- `~/Chief/20-projects/ehi-ignite-challenge/EXECUTION-PLAN.md` — phased plan toward 2026-05-13 Phase 1 deadline

**Rule of thumb:** if it has code, numbers, or repro steps, it lives here. If it has narrative, strategy, or stakeholder context, it lives in the vault.

## North star

*"Clinicians don't need more records. They need the right 5 facts in 30 seconds."*

The Atlas wedge is high-fidelity ingestion — turning unstructured clinical PDFs into FHIR R4 resources with measurable F1. Once that flows reliably, the cross-source merge / Provenance graph layer (currently archived) becomes the next chapter. Don't drift into building a generic FHIR browser or a chat-only assistant.
