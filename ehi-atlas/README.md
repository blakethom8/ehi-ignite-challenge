# EHI Atlas — Development Zone

The dev surface for the EHI Atlas data-aggregation platform. The platform is
designed to ingest and harmonize heterogeneous patient health data — FHIR R4
bundles, Epic EHI Export SQLite, C-CDA documents, payer claims, lab PDFs,
clinical-note PDFs — into one canonical FHIR R4 record with full Provenance
lineage. The cross-source merge / Provenance graph is the platform's
defensible wedge ([`../docs/architecture/ATLAS-DATA-MODEL.md`](../docs/architecture/ATLAS-DATA-MODEL.md)).

**Current development focus:** the **PDF → FHIR** ingestion path — the
hardest single ingestion path and the one most directly relevant to the
EHI Ignite Challenge Phase 1 deadline. Other ingestion paths (FHIR, EHI SQLite,
C-CDA) and the harmonization layer (silver / gold / Provenance) are the next
chapters; an early scaffold lives at
[`../archive/ehi-atlas-5layer/`](../archive/ehi-atlas-5layer/) and will be
rebuilt against the production parser when those phases activate.

Reads from `lib/` and the production `data/` drops at the repo root; ships
nothing to production directly. See [`CLAUDE.md`](CLAUDE.md) for zone
conventions and `../CLAUDE.md` for the repo-level product strategy.

## Quickstart

```bash
cd ehi-atlas
uv sync --all-extras

# Launch the Streamlit console (PDF Lab, PDF Compare, Pipeline Bakeoff)
make console

# Run the test suite
make test
```

## What's here

| Subdir | Purpose |
|---|---|
| `ehi_atlas/extract/` | PDF→FHIR extraction framework — `pipelines/` (Protocol + registry), `bake_off.py`, `eval.py`, `pdf.py` (Anthropic + Google AI Studio backends) |
| `app/` | Streamlit console — overview, Sources & Bronze, **PDF Lab**, **PDF Compare**, **Pipeline Bakeoff** |
| `corpus/` | Data bench: `_sources/` (raw drops), `bronze/` (canonical staging), `reference/` (terminology snapshots). See `corpus/README.md`. |
| `notebooks/` | Welcome + bronze-tier notebook |
| `notes/` | Research notes (Josh-stack data-lane sessions) |
| `tests/` | Tests for `ehi_atlas/extract/` |
| `scripts/` | Privacy-gate validation script |

## Architecture & experiment journal

- [`../docs/architecture/PDF-PROCESSOR.md`](../docs/architecture/PDF-PROCESSOR.md) — decision record for the PDF → FHIR pipeline (seven decisions, bake-off results, vision-wins evidence).
- [`../docs/architecture/PIPELINE-LOG.md`](../docs/architecture/PIPELINE-LOG.md) — running journal of pipeline experiments (bake-off tables, prompt iterations, model swaps).
- [`../docs/architecture/ATLAS-DATA-MODEL.md`](../docs/architecture/ATLAS-DATA-MODEL.md) — top-level data-layer decisions (FHIR R4 + USCDI canonical, Provenance graph as wedge).

## Where the rest of the platform lives

The production app — FastAPI backend, React frontend, shared `lib/` library
code, deployment configs — lives at the repo root. See `../CLAUDE.md` for the
full layout. This zone never imports from `api/` or `app/` and never writes
into production `data/`.

## Archived: 5-layer harmonization scaffold

The strategic vision is unchanged: cross-source merge with FHIR-native
Provenance is still the Atlas wedge. What was archived in May 2026 is the
**early Python scaffold** for that vision — per-source adapters, silver
standardization, harmonize/orchestrator, terminology — built before the
ingestion path had been stress-tested. Phase 1 demands one ingestion path
that actually works under load (PDF → FHIR), and the scaffold's silver/gold
output paths and Streamlit pages were getting in the way of that work.

The full scaffold — adapters, standardize, harmonize, terminology, the
corresponding tests, notebooks, and Streamlit pages — lives at
[`../archive/ehi-atlas-5layer/`](../archive/ehi-atlas-5layer/) and will be
rebuilt against the production parser once PDF ingestion stabilizes and the
multi-source merge becomes the bottleneck.

## License

MIT — see [`LICENSE`](LICENSE).
