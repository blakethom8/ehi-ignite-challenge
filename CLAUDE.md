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


## Durable Planning Docs

Use `/Users/blake/Chief/codex` for durable Codex planning artifacts, including Linear project briefs, issue seeds, roadmap notes, decision logs, meeting notes, and research summaries.

Keep implementation code, tests, repo-specific docs, deployment config, and generated app artifacts in this repository. Use dated Codex scratch folders only for temporary drafts or disposable intermediate files.

## Repository Structure

The codebase splits cleanly into two zones:

- **Application zone** — code and data the production app runs on. Ships in Docker, covered by tests, deployed to Hetzner.
- **Development zone** — research, prototypes, the data bench, end-to-end notebooks. Reads from the application zone but never modifies it.

```
ehi-ignite-challenge/
│
├── CLAUDE.md                              ← you are here
├── README.md
│
│ ─── APPLICATION ZONE ────────────────────────────────────────────
│
├── api/                                   ← FastAPI backend (PRIMARY — build here)
│   ├── main.py                            ← app entry, dotenv loading, middleware registration
│   ├── routers/                           ← patients, safety, timeline, search, corpus, traces
│   ├── middleware/
│   │   └── tracing.py                     ← request-level trace lifecycle
│   ├── core/                              ← clinical intelligence modules
│   │   ├── tracing.py                     ← LLM observability (traces, spans, SQLite, Langfuse)
│   │   ├── provider_assistant_service.py  ← mode selector (agent-sdk / deterministic)
│   │   ├── provider_assistant_agent_sdk.py ← Claude Agent SDK runtime (instrumented)
│   │   ├── provider_assistant.py          ← deterministic fact ranking + evidence retrieval
│   │   ├── sof_tools.py                   ← run_sql MCP tool: SELECT-only gate + read-only runner
│   │   ├── sof_materialize.py             ← FastAPI startup hook — rebuilds data/sof.db on mtime gate
│   │   ├── loader.py
│   │   ├── temporal.py                    ← TODO
│   │   ├── batch_enrichment.py            ← TODO (LLM pipeline)
│   │   ├── context_builder.py             ← TODO (5-layer pipeline)
│   │   └── rag_tools.py                   ← TODO
│   └── tests/                             ← FastAPI tests
│
├── app/                                   ← React + Vite + TypeScript frontend (PRIMARY)
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Explorer/                  ← FHIR data exploration
│   │   │   └── PatientJourney/            ← clinician-facing app
│   │   ├── components/
│   │   ├── hooks/
│   │   └── api/client.ts
│   └── vite.config.ts
│
├── lib/                                   ← Shared production library code ⭐
│   ├── README.md                          ← what's here, import conventions
│   ├── fhir_parser/                       ← FHIR R4 bundle parser + dataclass models
│   │   ├── bundle_parser.py
│   │   ├── extractors.py
│   │   └── models.py                      ← PatientRecord + all data models (source of truth)
│   ├── patient_catalog/                   ← single-patient stats + corpus loader
│   │   ├── single_patient.py
│   │   ├── corpus.py
│   │   └── field_profiler.py
│   ├── sql_on_fhir/                       ← SQL-on-FHIR v2 engine: ViewDefinition → SQLite ⭐
│   │   ├── enrich.py                      ← extra columns spliced onto view rows at ingest (drug_class)
│   │   ├── derived.py                     ← derived tables built after views flush (medication_episode)
│   │   └── views/                         ← 5 ViewDefinitions + README of the four warehouse layers
│   ├── clinical/                          ← drug classifier, episode detector, interaction checker
│   │   ├── drug_classifier.py
│   │   ├── drug_classes.json              ← canonical drug-class mapping
│   │   ├── episode_detector.py
│   │   ├── interaction_checker.py
│   │   └── loader.py
│   └── tests/                             ← library tests
│
├── data/                                  ← Production runtime data only
│   ├── synthea-samples/
│   │   ├── synthea-r4-individual/fhir/    ← 1,180 individual FHIR bundles (PRIMARY TEST DATA)
│   │   └── sample-bulk-fhir-datasets-10-patients/
│   ├── sof.db                             ← live SOF warehouse (gitignored, materialized on startup)
│   ├── traces.db                          ← request traces (gitignored)
│   └── patient-context/                   ← LLM session captures (gitignored)
│
├── deploy/                                ← Docker Compose + nginx configs (LIVE)
│   ├── docker-compose.prod.yml            ← production compose (api:8090, app:8091)
│   ├── Dockerfile.api                     ← Python 3.13 + uv + FastAPI
│   ├── Dockerfile.app                     ← Node build + nginx serve
│   ├── nginx-app.conf                     ← SPA routing inside the app container
│   └── nginx-host.conf                    ← Hetzner 2 host nginx (ehi.healthcaredataai.com)
│
├── scripts/                               ← Utility scripts (classify_patients, etc.)
│
├── docs/architecture/                     ← architecture docs
│   ├── ATLAS-DATA-MODEL.md                ← architectural decisions for Atlas's data layer ⭐
│   ├── PDF-PROCESSOR.md                   ← PDF → FHIR pipeline decision record + bake-off results ⭐
│   ├── PIPELINE-LOG.md                    ← running journal of pipeline experiments + measurements ⭐
│   ├── CONTEXT-ENGINEERING.md             ← LLM context pipeline design ⭐
│   ├── DATA-DEFINITIONS.md                ← data model reference ⭐
│   ├── ECOSYSTEM-OVERVIEW.md              ← platform framing, full directory layout, build sequence
│   ├── DEPLOYMENT.md                      ← Hetzner + Docker Compose deployment guide
│   ├── tracing.md                         ← LLM observability — traces, spans, costs, Langfuse
│   ├── FHIR-EXPLORER-DATA-REVIEW.md       ← original FHIR explorer purpose statement
│   └── CONTEXT-PIPELINE.md                ← LLM context engineering (TODO)
│
├── design/                                ← design system reference
│   ├── README.md
│   └── DESIGN.md                          ← Miro-inspired tokens, components, color roles
│
├── ideas/                                 ← product specs (read before building)
│   ├── FEATURE-IDEAS.md
│   ├── PATIENT-JOURNEY-APP.md             ← patient journey spec ⭐
│   ├── FORMAT-AGNOSTIC-INGESTION.md       ← ingestion service spec ⭐
│   └── PODCAST-INSIGHTS-FHIR-POSITIONING.md ← strategic positioning (on feature branch)
│
├── research/                              ← committed research artifacts
│   ├── SQL-ON-FHIR-REVIEW.md              ← SOF prototype review + run_sql tool surface addendum ⭐
│   └── ehi-ignite.db                      ← 200-patient pitch snapshot (committed, 11 MB)
│
│ ─── DEVELOPMENT ZONE ────────────────────────────────────────────
│
├── ehi-atlas/                             ← The dev surface for the Atlas data platform
│   ├── CLAUDE.md                          ← Atlas-zone conventions ⭐
│   ├── corpus/                            ← bench: _sources/ bronze/ silver/ gold/
│   ├── ehi_atlas/                         ← in-development Python package (adapters/extract/harmonize)
│   ├── notebooks/                         ← end-to-end pipeline notebooks
│   ├── prototypes/                        ← josh-* (faithful ports) and atlas-* (Atlas experiments)
│   ├── notes/                             ← josh-stack-deep-dive multi-session notes
│   ├── scripts/, tests/, app/, docs/      ← Atlas-specific utility, tests, UI, design docs
│
├── archive/                               ← Frozen legacy code (do not extend)
│   ├── README.md                          ← what's here, why it's frozen
│   ├── fhir-explorer-streamlit/           ← original Streamlit data-review tool
│   └── patient-journey-streamlit/         ← original Streamlit clinician journey app
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

These are the primary test files. The shared FHIR parser at `lib/fhir_parser/` reads these directly.

---

## The Shared Parser (Always Reuse This)

The `lib/fhir_parser/` module is stable and well-tested. **Do not rewrite it.** Always import from `lib/` — `api/`, `ehi-atlas/`, and `scripts/` all share this code.

### Loading a patient

```python
from lib.fhir_parser.bundle_parser import parse_bundle
from lib.patient_catalog.single_patient import compute_patient_stats

record = parse_bundle("data/synthea-samples/synthea-r4-individual/fhir/Robert854_Botsford977_148ad83c-4dbc-4cb6-9334-44e6886f1e42.json")
stats = compute_patient_stats(record)
```

### Key data models (from `lib/fhir_parser/models.py`)

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
- Imports from `lib.fhir_parser`, `lib.patient_catalog`, `lib.sql_on_fhir`, `lib.clinical` for shared library code
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

1. **FastAPI backend** — stand up `api/`, wire in shared parser from `lib/`, expose patient list + data endpoints
2. **React shell** — routing, patient selector sidebar, layout
3. **Explorer views** (React ports of the original Streamlit explorer in `archive/fhir-explorer-streamlit/`): Overview → Timeline → Encounter Hub → Field Profiler → Corpus
4. **Patient Journey views**: Safety Panel → Medication Timeline → Conditions
5. **Context engineering pipeline**: `temporal.py` → `batch_enrichment.py` → `context_builder.py`
6. **NL Search**: streaming Claude Q&A with citations
7. **Deployment**: Docker Compose → Hetzner

**Current focus: Steps 1–3 (Explorer)**

---

## Key Reference Docs

| Doc | What It Is |
|---|---|
| `docs/architecture/ATLAS-DATA-MODEL.md` | ⭐ **Read this first.** Architectural decisions for Atlas's data layer — FHIR R4 + USCDI as silver, bronze preserves native shape, LLM-authored mapping specs, hot path UI + cold path agent, Provenance graph as the wedge |
| `docs/architecture/PDF-PROCESSOR.md` | ⭐ PDF → FHIR pipeline decision record. Seven decisions, bake-off results, vision-wins evidence. Read before touching any extraction code. |
| `docs/architecture/PIPELINE-LOG.md` | Running journal of pipeline experiments — bake-off result tables, prompt-tuning A/Bs, model-swap experiments. Append-only, newest at top. |
| `docs/architecture/CONTEXT-ENGINEERING.md` | 5-layer LLM context pipeline design — read before building batch_enrichment or NL search |
| `docs/architecture/DATA-DEFINITIONS.md` | Full data model reference — encounter types, medication records, observation fields |
| `ideas/PATIENT-JOURNEY-APP.md` | Full product spec for the clinical journey app |
| `docs/architecture/ECOSYSTEM-OVERVIEW.md` | Platform framing and complete directory layout |
| `docs/architecture/DEPLOYMENT.md` | Hetzner + Docker Compose deployment guide |
| `docs/architecture/tracing.md` | LLM observability — traces, spans, token/cost tracking, Langfuse |
| `research/SQL-ON-FHIR-REVIEW.md` | SOF prototype "was it worth it" review **+ `run_sql` tool-surface addendum** (Phase 0) |
| `research/README.md` | Pitch snapshot layout + regen command for `research/ehi-ignite.db` |
| `lib/sql_on_fhir/views/README.md` | Pure views, filtered subset views, enriched columns, derived tables/views — the four warehouse layers and how to extend each |
| `lib/README.md` | Shared library code — what's where, import conventions |
| `ehi-atlas/CLAUDE.md` | Atlas development zone — corpus bench, prototypes, notes, promotion path |
| `archive/README.md` | Frozen legacy Streamlit shells — what they were, what replaced them |
| `design/DESIGN.md` | Miro-inspired design tokens + component guide |

### SQL-on-FHIR quick reference

- **Engine:** `lib/sql_on_fhir/` — ViewDefinition → SQLite (stable, reused everywhere)
- **Four-layer warehouse** (see `lib/sql_on_fhir/views/README.md`):
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
- **Imports:** always import from `lib/` (`lib.fhir_parser`, `lib.patient_catalog`, `lib.sql_on_fhir`, `lib.clinical`) — never copy library code
- **No hardcoded paths** — use `Path(__file__).parent` for relative paths in Python; `import.meta.env.VITE_API_URL` for API URL in React
- **No sys.path hacks** — repo root is on `sys.path` when uvicorn runs from the project directory, which makes `lib.*`, `api.*` importable directly

---

## Git Workflow

- Branch off `master` for features
- Naming: `feature/descriptive-name`
- Clear commit messages: `feat:`, `fix:`, `docs:`, `refactor:`
- Never commit directly to `master`

---

*Last updated: May 3, 2026 — major refactor: lib/ extracted, fhir_explorer/ + patient-journey/ archived, data-research/ absorbed into ehi-atlas/*
