# EHI Atlas — Development Zone

The dev surface for the EHI Atlas data-aggregation platform. Active focus: the
**PDF → FHIR** extraction pipeline. Reads from `lib/` and the production `data/`
drops at the repo root; ships nothing to production directly. See
[`CLAUDE.md`](CLAUDE.md) for zone conventions and `../CLAUDE.md` for the
repo-level product strategy.

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

## Archived: 5-layer harmonization stack

The original Atlas vision (per-source adapters → silver standardization →
gold harmonization with Provenance) was archived in May 2026 once PDF → FHIR
became the wedge. The full implementation — adapters, standardize,
harmonize, terminology, the corresponding tests, notebooks, and Streamlit
pages — lives at [`../archive/ehi-atlas-5layer/`](../archive/ehi-atlas-5layer/)
for historical reference.

## License

MIT — see [`LICENSE`](LICENSE).
