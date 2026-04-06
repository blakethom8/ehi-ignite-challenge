# CLAUDE.md — EHI Ignite Challenge Project Guide

> Read this file first. It tells you what this project is, how it's structured, what data is available, and what's already been built so you don't duplicate work.

---

## What This Project Is

This is the codebase for **Blake's submission to the EHI Ignite Challenge** — an HHS-sponsored $490K competition to build innovative applications that transform Electronic Health Information (EHI) into actionable clinical insights.

**Prize pool:** $490K across two phases  
**Phase 1 deadline:** May 13, 2026 (concept + wireframes)  
**Phase 2:** Summer 2026 – Spring 2027 (prototype)

**The core problem:** Patient health records are siloed, unstructured, and nearly impossible for clinicians to rapidly parse under time pressure. We're building tools to fix that.

**North star:** *"Clinicians don't need more records. They need the right 5 facts in 30 seconds."*

---

## Product Strategy

- **Primary user:** Surgeon / specialist doing high-speed chart review (Max Gibber, neurosurgeon, is the prototype user)
- **Product wedge:** Medication-centered clinical intelligence — longitudinal, safety-critical, directly relevant to surgical decisions
- **Do not build:** A generic FHIR browser, patient portal, or vague "AI-powered EHR" product
- **Should feel like:** A clinical briefing. A risk dashboard. Evidence-backed Q&A.
- Full strategic context: `ideas/PODCAST-INSIGHTS-FHIR-POSITIONING.md` (on `feature/patient-journey-app` branch)

---

## Repository Structure

```
ehi-ignite-challenge/
│
├── CLAUDE.md                              ← you are here
├── README.md
│
├── api/                                   ← FastAPI backend (PRIMARY — build here)
│   ├── main.py
│   ├── routers/                           ← patients, safety, timeline, search, corpus
│   └── core/                             ← clinical intelligence modules (migrated from patient-journey/core/)
│       ├── loader.py
│       ├── drug_classifier.py
│       ├── episode_detector.py
│       ├── temporal.py                    ← TODO
│       ├── batch_enrichment.py            ← TODO (LLM pipeline)
│       ├── context_builder.py             ← TODO (5-layer pipeline)
│       └── rag_tools.py                   ← TODO
│
├── app/                                   ← React + Vite + TypeScript frontend (PRIMARY)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Explorer/                  ← FHIR data exploration (build first)
│   │   │   └── PatientJourney/            ← clinician-facing app (build second)
│   │   ├── components/
│   │   ├── hooks/
│   │   └── api/client.ts
│   └── vite.config.ts
│
├── deploy/                                ← Docker Compose + nginx configs
│   ├── docker-compose.prod.yml
│   ├── nginx.conf
│   ├── Dockerfile.api
│   └── Dockerfile.app
│
├── design/                                ← design system reference
│   ├── README.md
│   └── DESIGN.md                          ← Miro-inspired tokens, components, color roles
│
├── architecture/                          ← architecture docs
│   ├── ECOSYSTEM-OVERVIEW.md              ← platform framing, full directory layout, build sequence
│   ├── DEPLOYMENT.md                      ← Hetzner + Docker Compose deployment guide
│   └── CONTEXT-PIPELINE.md               ← LLM context engineering (TODO)
│
├── ideas/                                ← product specs (read before building)
│   ├── FEATURE-IDEAS.md
│   ├── PATIENT-JOURNEY-APP.md             ← patient journey spec ⭐
│   ├── FORMAT-AGNOSTIC-INGESTION.md       ← ingestion service spec ⭐
│   └── PODCAST-INSIGHTS-FHIR-POSITIONING.md ← strategic positioning (on feature branch)
│
├── fhir_explorer/                         ← LEGACY Streamlit (internal reference tool — DO NOT EXTEND)
│   ├── app.py                             ← run: streamlit run fhir_explorer/app.py
│   ├── parser/                            ← SHARED PARSER — always import from here
│   │   ├── bundle_parser.py
│   │   ├── extractors.py
│   │   └── models.py                      ← PatientRecord + all data models (source of truth)
│   ├── catalog/
│   │   ├── corpus.py
│   │   ├── field_profiler.py
│   │   └── single_patient.py
│   └── views/                             ← reference implementations for React ports
│
├── patient-journey/                       ← LEGACY Streamlit (reference only — DO NOT EXTEND)
│   ├── app.py
│   ├── core/                              ← drug_classifier, episode_detector (migrate to api/core/)
│   ├── views/                             ← reference implementations for React ports
│   ├── CONTEXT-ENGINEERING.md             ← READ THIS — LLM context pipeline design ⭐
│   └── DATA-DEFINITIONS.md               ← READ THIS — data model reference ⭐
│
├── data/
│   └── synthea-samples/
│       ├── synthea-r4-individual/fhir/    ← 1,180 individual FHIR bundles (PRIMARY TEST DATA)
│       └── sample-bulk-fhir-datasets-10-patients/
│
├── pyproject.toml                         ← UV root environment
└── uv.lock
```

---

## Available Data

### Primary: Synthea Individual Patient Bundles

**Path:** `data/synthea-samples/synthea-r4-individual/fhir/`  
**Count:** 1,180 JSON files  
**Format:** FHIR R4 Bundle (each file = one patient's complete record)

These are the primary test files. The existing `fhir_explorer` parser reads these directly.

---

## The Existing Parser (Always Reuse This)

The `fhir_explorer/parser/` module is stable and well-tested. **Do not rewrite it.** Always import from it — even in the new `api/` backend.

### Loading a patient

```python
from fhir_explorer.parser.bundle_parser import parse_bundle
from fhir_explorer.catalog.single_patient import compute_patient_stats

record = parse_bundle("data/synthea-samples/synthea-r4-individual/fhir/Robert854_Botsford977_148ad83c-4dbc-4cb6-9334-44e6886f1e42.json")
stats = compute_patient_stats(record)
```

### Key data models (from `fhir_explorer/parser/models.py`)

| Class | What It Is |
|---|---|
| `PatientRecord` | Top-level object — contains everything about a patient |
| `PatientDemographics` | Name, DOB, gender, address |
| `Condition` | A diagnosis — code, display, onset, status |
| `Medication` | A medication — display, RxNorm code, status, dates |
| `EncounterRecord` | A clinical visit — type, date, linked resources |
| `Observation` | A lab result or vital — LOINC code, value, unit |
| `Procedure` | A procedure — CPT/SNOMED code, date |
| `Immunization` | A vaccine — display, date |
| `AllergyRecord` | An allergy — substance, reaction, severity |

---

## Tech Stack

### Backend (`api/`)
- **Python 3.13**, FastAPI, uvicorn
- Imports from `fhir_explorer.parser` for all FHIR parsing
- Anthropic SDK (Claude Haiku for batch enrichment, Sonnet for NL search)
- Run: `uv run uvicorn api.main:app --reload --port 8000`

### Frontend (`app/`)
- **React 18 + Vite + TypeScript**
- Tailwind CSS + shadcn/ui for components
- Plotly.js (react-plotly) for charts (Gantt, timeline, density)
- React Query for API state management
- Run: `cd app && npm run dev` (runs on :5173)

### Deployment
- Hetzner CX21 VPS (~€4.85/mo)
- Docker Compose + nginx + Let's Encrypt SSL
- See `architecture/DEPLOYMENT.md` for full setup

### Design System
- Miro-inspired (see `design/DESIGN.md`)
- Primary color: Blue 450 (`#5b76fe`)
- Display font: Roobert PRO Medium
- Body font: Noto Sans

---

## Build Order

1. **FastAPI backend** — stand up `api/`, wire in existing parser, expose patient list + data endpoints
2. **React shell** — routing, patient selector sidebar, layout
3. **Explorer views** (React ports of fhir_explorer): Overview → Timeline → Encounter Hub → Field Profiler → Corpus
4. **Patient Journey views**: Safety Panel → Medication Timeline → Conditions
5. **Context engineering pipeline**: `temporal.py` → `batch_enrichment.py` → `context_builder.py`
6. **NL Search**: streaming Claude Q&A with citations
7. **Deployment**: Docker Compose → Hetzner

**Current focus: Steps 1–3 (Explorer)**

---

## Key Reference Docs

| Doc | What It Is |
|---|---|
| `patient-journey/CONTEXT-ENGINEERING.md` | 5-layer LLM context pipeline design — read before building batch_enrichment or NL search |
| `patient-journey/DATA-DEFINITIONS.md` | Full data model reference — encounter types, medication records, observation fields |
| `ideas/PATIENT-JOURNEY-APP.md` | Full product spec for the clinical journey app |
| `architecture/ECOSYSTEM-OVERVIEW.md` | Platform framing and complete directory layout |
| `architecture/DEPLOYMENT.md` | Hetzner + Docker Compose deployment guide |
| `design/DESIGN.md` | Miro-inspired design tokens + component guide |

---

## Coding Conventions

- **Python 3.13+**, fully typed with type hints
- **FastAPI** for backend — follow `provider-search` repo patterns (routers, service layer, Pydantic models)
- **React + TypeScript** — functional components, hooks, React Query for data fetching
- **Imports:** always import from `fhir_explorer.parser` — never copy parser code
- **No hardcoded paths** — use `Path(__file__).parent` for relative paths in Python; `import.meta.env.VITE_API_URL` for API URL in React

---

## Git Workflow

- Branch off `master` for features
- Naming: `feature/descriptive-name`
- Clear commit messages: `feat:`, `fix:`, `docs:`, `refactor:`
- Never commit directly to `master`

---

*Last updated: April 5, 2026*
