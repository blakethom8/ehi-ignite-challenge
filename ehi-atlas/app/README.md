# EHI Atlas Console

**Working name.** Standalone Streamlit workflow visualization tool for the EHI Atlas harmonization pipeline.

This app is **read-only** — it visualizes existing gold-tier outputs produced by `make pipeline`.
It does not modify any corpus data and never invokes the harmonizer at runtime.

---

## How to run

From the repo root (`ehi-ignite-challenge/`):

```bash
# Using the main project venv (streamlit is installed there)
.venv/bin/streamlit run ehi-atlas/app/streamlit_app.py --server.port 8503
```

Or from inside `ehi-atlas/`:

```bash
uv run streamlit run app/streamlit_app.py --server.port 8503
```

Or via the `launch.json` entry in `.claude/launch.json` (name: "EHI Atlas Console").

The app opens at `http://localhost:8503`.

---

## Prerequisites

1. Run the harmonization pipeline first to build the gold tier:

```bash
cd ehi-atlas
make pipeline
```

This produces:
- `corpus/gold/patients/rhett759/manifest.json`
- `corpus/gold/patients/rhett759/bundle.json`
- `corpus/gold/patients/rhett759/provenance.ndjson`

The app shows a warning banner if the gold tier hasn't been built yet.

---

## Pages

| Page | File | What it shows |
|---|---|---|
| Overview | `streamlit_app.py` | Landing: 5-layer pipeline diagram, per-stage metrics, pipeline status |
| Sources & Bronze | `pages/01_Sources_and_Bronze.py` | Layer 1 outputs: source table, per-source drill-down (FHIR viewer, SQLite preview, PDF pages) |
| Standardize | `pages/02_Standardize.py` | Layer 2 outputs: silver tier viewer, tags + profiles per source, L2 status per source |
| Harmonize | `pages/03_Harmonize.py` | Layer 3: merge visualization — Artifact 1 (hyperlipidemia), Artifact 2 (statin conflict), Artifact 5 (creatinine cross-format) |
| Gold & Provenance | `pages/04_Gold_and_Provenance.py` | Final unified record + Provenance.ndjson lineage walker |

---

## Components

Reusable widgets in `components/`:

- **`badges.py`** — engine-type badge pills: 🔧 Script · 🤖 LLM · 📚 Reference table · ⚙️ Hybrid
- **`header.py`** — consistent header bar with brand mark "EA", working-name flag, page title
- **`corpus_loader.py`** — `@st.cache_data`-decorated loaders for all corpus files; invalidate on file mtime so pipeline re-runs reflect on reload
- **`pipeline_diagram.py`** — the 5-layer pipeline as a Graphviz chart (with ASCII fallback)

---

## What this app does NOT do

- Does not modify any corpus data (bronze / silver / gold)
- Does not invoke the harmonizer or any pipeline scripts
- Does not call any external APIs
- Does not integrate with the patient-journey app (Phase 2)

---

## Phase 2 integration plan

Phase 2 plugs the gold tier into the patient-journey app via a symlink:

```bash
cd ehi-atlas
make integrate    # creates data/ehi-atlas-output/ → corpus/gold/ symlink
```

The patient-journey app's `Sources` panel will then walk Provenance edges from
gold resources back to bronze, showing the origin of each fact. The standalone
EHI Atlas Console remains available for engineering/pipeline inspection.

See `docs/INTEGRATION.md` for the full integration contract.

---

## Streamlit note

Streamlit is installed in the main project venv (`../.venv`) but **not** in `ehi-atlas/pyproject.toml`.
To add it to the ehi-atlas venv: `uv add streamlit` from `ehi-atlas/`. For now, use the main venv
or the `uv run` invocation from the repo root.
