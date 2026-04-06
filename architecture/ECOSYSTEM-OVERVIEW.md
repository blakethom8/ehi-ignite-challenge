# EHI Ignite — Ecosystem Architecture Overview

*Last updated: April 5, 2026*

---

## The Platform Model

This is not a single application. It is a **clinical intelligence platform** built on a shared data layer, with multiple specialized views surfacing different facets of the same patient data.

The organizing principle:

```
FHIR Data (any format)
    ↓
Python Intelligence Layer (FastAPI backend)
    ↓
React Frontend (multiple apps as routes)
    ↓
Clinician / Researcher
```

Every new use case — surgeon pre-op, memory care intake, payer review — becomes a new route in the React app, backed by the same FastAPI API and the same FHIR parsing layer. New views are additive, not new deployments.

---

## System Architecture

```
┌──────────────────────────────────────────────────────────────────────┐
│                        HETZNER VPS                                   │
│                     (Docker Compose)                                 │
│                                                                      │
│  ┌──────────────────────────────────────────────────────────────┐   │
│  │                  nginx (reverse proxy)                        │   │
│  │                  :80 / :443 (SSL via Let's Encrypt)           │   │
│  └──────────┬────────────────────────────┬───────────────────────┘  │
│             │                            │                           │
│             ▼                            ▼                           │
│  ┌────────────────────┐      ┌────────────────────────────┐         │
│  │   api (FastAPI)    │      │     app (React + Vite)     │         │
│  │      :8000         │      │          :3000             │         │
│  │                    │      │                            │         │
│  │  /api/patients     │      │  /explorer      (FHIR lab) │         │
│  │  /api/safety       │      │  /patient/:id   (journey)  │         │
│  │  /api/timeline     │      │  /corpus        (analysis) │         │
│  │  /api/search       │      │                            │         │
│  │  /api/corpus       │      │                            │         │
│  └────────┬───────────┘      └────────────────────────────┘         │
│           │                                                          │
│           ▼                                                          │
│  ┌────────────────────┐                                              │
│  │   fhir_explorer/   │  (shared Python parsing layer)              │
│  │   parser/          │                                              │
│  └────────────────────┘                                             │
│                                                                      │
└──────────────────────────────────────────────────────────────────────┘
                              │
              ┌───────────────┼───────────────┐
              │               │               │
              ▼               ▼               ▼
    ┌──────────────┐  ┌──────────────┐  ┌──────────────┐
    │ FHIR Bundles │  │  Anthropic   │  │  OpenFDA     │
    │ (local data) │  │  Claude API  │  │  Drug API    │
    └──────────────┘  └──────────────┘  └──────────────┘
```

---

## Directory Structure

```
ehi-ignite-challenge/
│
├── api/                            ← FastAPI backend
│   ├── main.py                     ← app entry, CORS, router registration
│   ├── routers/
│   │   ├── patients.py             ← list, load, parse FHIR bundles
│   │   ├── safety.py               ← drug flags, surgical safety panel
│   │   ├── timeline.py             ← medication episodes, Gantt data
│   │   ├── conditions.py           ← condition tracker
│   │   ├── observations.py         ← labs, vitals, trends
│   │   ├── search.py               ← NL search / LLM Q&A
│   │   └── corpus.py               ← multi-patient corpus analysis
│   ├── core/                       ← clinical intelligence modules
│   │   ├── loader.py               ← wraps fhir_explorer parser
│   │   ├── drug_classifier.py      ← RxNorm → drug class → risk flag
│   │   ├── episode_detector.py     ← medication/condition episode grouping
│   │   ├── temporal.py             ← temporal metadata (TODO)
│   │   ├── batch_enrichment.py     ← LLM batch pipeline (TODO)
│   │   ├── context_builder.py      ← 5-layer context pipeline (TODO)
│   │   └── rag_tools.py            ← tool functions for NL search (TODO)
│   ├── prompts/                    ← LLM prompt templates
│   └── requirements.txt
│
├── app/                            ← React + Vite + TypeScript frontend
│   ├── src/
│   │   ├── pages/
│   │   │   ├── Explorer/           ← FHIR data exploration (replaces fhir_explorer)
│   │   │   │   ├── Overview.tsx
│   │   │   │   ├── Timeline.tsx
│   │   │   │   ├── EncounterHub.tsx
│   │   │   │   ├── FieldProfiler.tsx
│   │   │   │   ├── SignalFilter.tsx
│   │   │   │   └── CorpusView.tsx
│   │   │   └── PatientJourney/     ← clinician-facing app
│   │   │       ├── SafetyPanel.tsx
│   │   │       ├── MedTimeline.tsx
│   │   │       ├── Conditions.tsx
│   │   │       └── NLSearch.tsx
│   │   ├── components/             ← shared UI components
│   │   │   ├── PatientSelector.tsx
│   │   │   ├── RiskBadge.tsx
│   │   │   ├── DrugClassTag.tsx
│   │   │   └── TimelineChart.tsx
│   │   ├── hooks/
│   │   │   ├── usePatient.ts
│   │   │   └── useCorpus.ts
│   │   ├── api/
│   │   │   └── client.ts           ← typed API client
│   │   └── App.tsx
│   ├── package.json
│   └── vite.config.ts
│
├── deploy/                         ← deployment configuration
│   ├── docker-compose.prod.yml
│   ├── nginx.conf
│   └── Dockerfile.api
│   └── Dockerfile.app
│
├── design/                         ← design system reference
│   ├── README.md
│   └── DESIGN.md                   ← Miro-inspired tokens + component guide
│
├── architecture/                   ← you are here
│   ├── ECOSYSTEM-OVERVIEW.md
│   ├── DEPLOYMENT.md
│   └── CONTEXT-PIPELINE.md         ← LLM context engineering (simplified)
│
├── fhir_explorer/                  ← legacy Streamlit (reference + internal use)
├── patient-journey/                ← legacy Streamlit (reference + internal use)
├── data/
├── ideas/
├── pyproject.toml                  ← root UV environment (api deps)
└── CLAUDE.md
```

---

## The Two Modes

### Explorer Mode (Internal / Development)
- Route: `/explorer`
- Users: Blake, developers, data analysts
- Purpose: Understanding FHIR data structure, profiling fields, exploring patient records, validating parsing
- This is the `fhir_explorer` reimagined as a proper web app
- **Start here** — building this first since it's mission-critical for data learning

### Patient Journey Mode (Competition Submission / Clinical)
- Route: `/patient/:id`
- Users: Surgeons, anesthesiologists, clinicians
- Purpose: Fast clinical briefing before a case
- The competition submission surface
- Build second, once data understanding is solid

---

## Build Sequence

### Phase 1: Foundation + Explorer (current focus)
1. FastAPI backend — patient list endpoint, bundle loading, existing parser wired up
2. React shell — routing, patient selector, layout
3. Explorer views — Overview, Timeline, Encounter Hub, Field Profiler (port from Streamlit)
4. Corpus view — multi-patient analysis

### Phase 2: Patient Journey
5. Safety Panel — drug flags, surgical risk view
6. Medication Timeline — Gantt chart with episode grouping
7. Conditions tracker
8. Context engineering pipeline — temporal.py, batch_enrichment.py

### Phase 3: NL Search
9. LLM Q&A layer — context_builder.py, rag_tools.py
10. NLSearch view — streaming chat with citations

### Phase 4: Deployment
11. Docker Compose setup
12. Hetzner deploy (same pattern as provider-search)
13. nginx + SSL

---

## Key Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Frontend | React + Vite + TypeScript | Full control, proper routing, streaming LLM, polished demo |
| Backend | FastAPI (Python) | Reuses all existing parser code, 0 rewrite |
| Styling | Tailwind + shadcn/ui | Matches Miro design system, rapid composition |
| Charts | Plotly.js (react-plotly) | Existing Gantt/timeline logic already works in Plotly |
| Hosting | Hetzner CX21 + Docker Compose | Same pattern as provider-search and cms-data |
| Auth | None for MVP | Not needed for competition submission |
| LLM | Anthropic Claude (Haiku for batch, Sonnet for chat) | Already in stack, best for clinical reasoning |
| Design | Miro-inspired (see design/DESIGN.md) | Clean, clinical-appropriate, not generic Material |
