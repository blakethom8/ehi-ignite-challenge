# EHI Ignite Challenge

**Clinical intelligence tools that transform raw FHIR patient records into actionable insights for clinicians.**

Built for the [HHS EHI Ignite Challenge](https://ehignitechallenge.org/) — a $490K competition to make Electronic Health Information (EHI) exports genuinely useful.

**Live demo:** [ehi.healthcaredataai.com](https://ehi.healthcaredataai.com)

---

## The Problem

Federal regulations now require every certified EHR (Epic, Cerner, etc.) to export a patient's complete health record on demand as FHIR R4. The result: technically computable but practically overwhelming. A complex patient can have 5,000+ resources — conditions, medications, labs, encounters, procedures — scattered across decades of care.

Clinicians don't need more records. They need the right 5 facts in 30 seconds.

## What This Does

The app ships as **Atlas Agentic Workspaces** — five top-level modules sitting on one shared FHIR data layer:

- **Patient Record** — Source-of-truth chart layer (clinical overview, longitudinal history, Data Aggregator)
- **FHIR Charts** — Raw-resource browser for the underlying bundle (formerly "FHIR Explorer")
- **Caspian** — First-party agentic clinical workspace with full chart access (chat, workbench, tools)
- **Plugins** — Installable, sandboxed workspaces that read a signed anchor package, never the raw chart (Trial Finder, Medication Access, Site Coordination)
- **Learn** — Internal section: runbooks, evals, methodology, skills

Underneath, a **SQL-on-FHIR warehouse** materializes the 1,180 Synthea bundles into a queryable SQLite layer (patient, condition, medication, observation, encounter views plus drug-class enrichment and a derived medication-episode table). Caspian and the deterministic clinical-intelligence modules (drug classifier, episode detector, interaction checker, cross-source harmonizer) read from that layer.

## Tech Stack

| Layer | Stack |
|---|---|
| **Backend** | Python 3.13, FastAPI, SQLite (SQL-on-FHIR), Anthropic Claude SDK |
| **Frontend** | React 19, TypeScript, Vite, Tailwind CSS, shadcn/ui, Plotly.js |
| **Data** | 1,180 Synthea FHIR R4 patient bundles, SQL-on-FHIR v2 ViewDefinitions |
| **Deploy** | Docker Compose, nginx, Hetzner VPS |

## Quick Start

### Prerequisites

- Python 3.13+ and [uv](https://docs.astral.sh/uv/)
- Node.js 20+
- Anthropic API key (for the Provider Assistant feature)

### Setup

```bash
# Clone
git clone https://github.com/blakethom8/ehi-ignite-challenge.git
cd ehi-ignite-challenge

# Backend
cp .env.example .env
# Edit .env with your ANTHROPIC_API_KEY
uv sync
uv run uvicorn api.main:app --reload --port 8000

# Frontend (separate terminal)
cd app
npm install
npm run dev
```

The app runs at `http://localhost:5173` with the API at `http://localhost:8000`.

### Data

The app uses [Synthea](https://github.com/synthetichealth/synthea) synthetic FHIR R4 patient bundles. Download the individual patient bundles to `data/synthea-samples/synthea-r4-individual/fhir/`:

```bash
# Download from Synthea releases or generate your own
# See data/ directory for structure details
```

The SQL-on-FHIR warehouse (`data/sof.db`) is materialized automatically on API startup.

## Production Deployment

See [`deploy/`](deploy/) for Docker Compose configs and nginx setup.

```bash
# On the server
cd /opt/ehi-ignite
cp .env.example .env
# Edit .env with real ANTHROPIC_API_KEY
./deploy/deploy-prod.sh
```

## Project Structure

```
ehi-ignite-challenge/
├── api/                    ← FastAPI backend
│   ├── core/               ← Clinical intelligence modules (context_builder, harmonize_service, caspian_*, sof_*)
│   └── routers/            ← REST endpoints
├── app/                    ← React + Vite frontend
│   └── src/
│       ├── pages/          ← PatientRecord, FhirCharts, Caspian, Plugins, InternalTools, UsingAtlas
│       └── components/atlas/  ← Shared Atlas chrome + workspace shell
├── lib/                    ← Shared production library code
│   ├── fhir_parser/        ← FHIR R4 bundle parser + dataclass models
│   ├── patient_catalog/    ← Single-patient stats + corpus loader
│   ├── sql_on_fhir/        ← SQL-on-FHIR v2 engine: ViewDefinition → SQLite
│   ├── clinical/           ← Drug classifier, episode detector, interaction checker
│   ├── harmonize/          ← Cross-source Observation merge + FHIR Provenance
│   ├── extract/            ← PDF → FHIR extraction framework
│   ├── narratives/         ← Per-episode FHIR Composition generator
│   └── patient_voice/      ← Patient-intake → FHIR adapter
├── deploy/                 ← Docker + nginx production configs
├── data/                   ← FHIR bundles + SQLite databases
├── docs/architecture/      ← Architecture docs (AGENTIC-HARNESS, ATLAS-DATA-MODEL, …)
├── research/               ← Competition research + pitch snapshot
├── ehi-atlas/              ← Development zone: corpus bench, prototypes, notes
└── archive/                ← Frozen legacy Streamlit shells + pre-Atlas design
```

## License

MIT — see [LICENSE](LICENSE).
