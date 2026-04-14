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
│   ├── main.py                            ← app entry, dotenv loading, middleware registration
│   ├── routers/                           ← patients, safety, timeline, search, corpus, traces
│   ├── middleware/
│   │   └── tracing.py                     ← request-level trace lifecycle
│   └── core/                             ← clinical intelligence modules
│       ├── tracing.py                     ← LLM observability (traces, spans, SQLite, Langfuse)
│       ├── provider_assistant_service.py  ← mode selector (agent-sdk / deterministic)
│       ├── provider_assistant_agent_sdk.py ← Claude Agent SDK runtime (instrumented)
│       ├── provider_assistant.py          ← deterministic fact ranking + evidence retrieval
│       ├── sof_tools.py                   ← run_sql MCP tool: SELECT-only gate + read-only runner
│       ├── sof_materialize.py             ← FastAPI startup hook — rebuilds data/sof.db on mtime gate
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
├── deploy/                                ← Docker Compose + nginx configs (LIVE)
│   ├── docker-compose.prod.yml            ← production compose (api:8090, app:8091)
│   ├── Dockerfile.api                     ← Python 3.13 + uv + FastAPI
│   ├── Dockerfile.app                     ← Node build + nginx serve
│   ├── nginx-app.conf                     ← SPA routing inside the app container
│   └── nginx-host.conf                    ← Hetzner 2 host nginx (ehi.healthcaredataai.com)
│
├── design/                                ← design system reference
│   ├── README.md
│   └── DESIGN.md                          ← Miro-inspired tokens, components, color roles
│
├── docs/architecture/                     ← architecture docs
│   ├── ECOSYSTEM-OVERVIEW.md              ← platform framing, full directory layout, build sequence
│   ├── DEPLOYMENT.md                      ← Hetzner + Docker Compose deployment guide
│   ├── tracing.md                         ← LLM observability — traces, spans, costs, Langfuse
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
│   │   └── sql_on_fhir/                   ← SQL-on-FHIR v2 engine: ViewDefinition → SQLite ⭐
│   │       ├── enrich.py                  ← extra columns spliced onto view rows at ingest (drug_class)
│   │       ├── derived.py                 ← derived tables built after views flush (medication_episode)
│   │       └── views/                     ← 5 ViewDefinitions + README of the three warehouse layers
│   ├── views/                             ← reference implementations for React ports
│   ├── CONTEXT-ENGINEERING.md             ← READ THIS — LLM context pipeline design ⭐
│   └── DATA-DEFINITIONS.md               ← READ THIS — data model reference ⭐
│
├── research/
│   ├── SQL-ON-FHIR-REVIEW.md              ← SOF prototype review + run_sql tool surface addendum ⭐
│   └── ehi-ignite.db                      ← 200-patient pitch snapshot (committed, 11 MB)
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
- **Production:** https://ehi.healthcaredataai.com (Hetzner 2 — 5.78.148.70)
- Docker Compose + nginx + Let's Encrypt SSL
- Manual deploy: `ssh hetzner2 'cd /opt/ehi-ignite && git pull origin master && docker compose -f deploy/docker-compose.prod.yml up -d --build'`
- See `deploy/` for configs, `docs/architecture/DEPLOYMENT.md` for full setup

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
| `docs/architecture/ECOSYSTEM-OVERVIEW.md` | Platform framing and complete directory layout |
| `docs/architecture/DEPLOYMENT.md` | Hetzner + Docker Compose deployment guide |
| `docs/architecture/tracing.md` | LLM observability — traces, spans, token/cost tracking, Langfuse |
| `research/SQL-ON-FHIR-REVIEW.md` | SOF prototype "was it worth it" review **+ `run_sql` tool-surface addendum** (Phase 0) |
| `research/README.md` | Pitch snapshot layout + regen command for `research/ehi-ignite.db` |
| `patient-journey/core/sql_on_fhir/views/README.md` | Pure views, filtered subset views, enriched columns, derived tables/views — the four warehouse layers and how to extend each |
| `design/DESIGN.md` | Miro-inspired design tokens + component guide |

### SQL-on-FHIR quick reference

- **Engine:** `patient-journey/core/sql_on_fhir/` — ViewDefinition → SQLite (stable, reused everywhere)
- **Four-layer warehouse** (see `patient-journey/core/sql_on_fhir/views/README.md`):
  1. **Pure ViewDefinition tables** — JSON under `views/`. Standards-compliant projection from FHIR resources (`patient`, `condition`, `medication_request`, `observation`, `encounter`).
  2. **Filtered subset views** — still pure JSON, plus a view-level `where` clause that prunes rows at ingest. Same column shape as the "full" sibling so queries can swap one for the other. *(e.g. `condition_active` — only `active` / `recurrence` / `relapse` rows; P1.3)*
  3. **Enriched columns** — `enrich.py`. Extra columns spliced onto view rows at ingest time. *(e.g. `medication_request.drug_class`; P1.1)*
  4. **Derived artifacts** — `derived.py`. Whole new query targets built after the views are materialized. Two flavours:
     - `kind="table"` — materialized, built in Python. *(e.g. `medication_episode`; P1.2)*
     - `kind="view"` — lazy SQLite `CREATE VIEW`, always fresh. *(e.g. `observation_latest`; P1.4)*
- **LLM tool:** `api/core/sof_tools.run_sql(query, limit)` — SELECT-only gate, 500-row cap, read-only connection. Automatically renders enrichments and derivations into the agent's system prompt (including `CREATE VIEW` vs `CREATE TABLE` emission) so the schema is always in sync with the warehouse.
- **Warehouse:** `data/sof.db` (gitignored, materialized on FastAPI startup via `api/core/sof_materialize.py`)
- **Pitch snapshot:** `research/ehi-ignite.db` (committed, 200 patients, ~12 MB, reviewer-facing)
- **Query targets shipped today:** `patient`, `condition`, `condition_active` (subset), `medication_request` (+ `drug_class` enrichment), `observation`, `encounter`, plus the derived `medication_episode` table and the derived `observation_latest` view
- **Drug-class cohort query** (P1.1 canonical example):
  `SELECT drug_class, COUNT(*) FROM medication_request GROUP BY drug_class ORDER BY 2 DESC`
- **Active-treatment cohort query** (P1.2 example — use `medication_episode`, not raw `medication_request`):
  `SELECT drug_class, COUNT(*) FROM medication_episode WHERE is_active=1 GROUP BY drug_class`
- **Problem-list query** (P1.3 example — use `condition_active`, not raw `condition`):
  `SELECT display, COUNT(*) FROM condition_active GROUP BY display ORDER BY 2 DESC`
- **Current-lab query** (P1.4 example — use `observation_latest`, not raw `observation`):
  `SELECT value_quantity, value_unit, effective_date FROM observation_latest WHERE patient_ref = 'urn:uuid:…' AND loinc_code = '4548-4'`
  *(LOINC 4548-4 = HbA1c — returns exactly one row, always the most recent)*

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
