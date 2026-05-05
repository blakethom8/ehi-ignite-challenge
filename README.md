# EHI Ignite Challenge

**Clinical intelligence tools that transform raw FHIR patient records into actionable insights for clinicians.**

Built for the [HHS EHI Ignite Challenge](https://ehignitechallenge.org/) — a $490K competition to make Electronic Health Information (EHI) exports genuinely useful.

**Live demo:** [ehi.healthcaredataai.com](https://ehi.healthcaredataai.com)

---

## The Problem

Federal regulations now require every certified EHR (Epic, Cerner, etc.) to export a patient's complete health record on demand as FHIR R4. The result: technically computable but practically overwhelming. A complex patient can have 5,000+ resources — conditions, medications, labs, encounters, procedures — scattered across decades of care.

Clinicians don't need more records. They need the right 5 facts in 30 seconds.

## What This Does

- **Patient Explorer** — Browse, search, and profile 1,180 synthetic patient records (Synthea FHIR R4)
- **Clinical Safety Panel** — Drug class risk classification, interaction checking, allergy criticality
- **Care Journey Timeline** — Medication episodes, condition arcs, and encounter history on an interactive Gantt chart
- **SQL-on-FHIR Warehouse** — ViewDefinition-driven ETL from raw FHIR bundles into a queryable SQLite layer
- **Provider Assistant** — Claude-powered chart Q&A with evidence-backed citations grounded in the patient's actual record

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
│   ├── core/               ← Clinical intelligence modules
│   ├── routers/            ← REST endpoints
│   └── agents/             ← Claude Agent SDK profiles
├── app/                    ← React + Vite frontend
│   └── src/
│       ├── pages/          ← Explorer, PatientJourney views
│       └── components/     ← Shared UI components
├── fhir_explorer/          ← FHIR parser library (shared)
├── patient-journey/        ← SQL-on-FHIR engine + data models
├── deploy/                 ← Docker + nginx production configs
├── data/                   ← FHIR bundles + SQLite databases
└── research/               ← Competition research + pitch snapshot
```

## License

MIT — see [LICENSE](LICENSE).
