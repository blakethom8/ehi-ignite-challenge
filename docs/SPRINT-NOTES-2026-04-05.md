# Sprint Notes — April 5, 2026

## What happened

This session was a full-day autonomous build sprint using an orchestrated multi-agent loop. Three research agents ran simultaneously at the start to generate a feature backlog, and then build agents were dispatched in parallel throughout the session to implement features without human intervention between each build.

### The loop architecture

```
Research agents (3 parallel)
    ↓ feature backlog → .claude/feature-queue.md
Orchestrator (me)
    ↓ prioritize → dispatch build agents
Build agents (up to 3 parallel, non-overlapping files)
    ↓ implement → TSC check → smoke test → report
Orchestrator
    ↓ update queue → dispatch next batch
Cron jobs (every 23 min: research | every 37 min: build)
    ↓ keep loop running autonomously
```

Key discipline: build agents were always given explicit lists of which files to touch and which to avoid, preventing write conflicts on the same file from parallel agents.

---

## Features shipped

### Session 1 — Foundation (before the sprint)
- Timeline table with sort/filter/class filter
- Encounter preview pane (Summary + Details tabs)
- Arrow key navigation in encounter table
- Raw FHIR JSON modal with copy button
- Year filter pills (replaced broken Plotly chart)
- In-memory LRU cache (30 patients)

### Sprint builds

**BUILD-001** — Frontend UX foundations
- Patient bookmarks/favorites (localStorage, star icon in sidebar, Favorites section at top)
- Command Palette (Cmd+K): instant patient search, arrow key nav, complexity badge, Enter to navigate
- Smart empty states (page-specific bullets, stat counter) across Overview/Timeline/Journey

**BUILD-002** — Backend data endpoints
- `/patients/{id}/key-labs`: LOINC panel matching (Hematology/Metabolic/Coagulation/Cardiac), most recent value per code, trend detection (up/down/stable), history array for sparklines
- `/corpus/stats`: full population aggregate (1,180 patients, gender breakdown, complexity tiers, avg encounter/condition/med counts)

**BUILD-003** — Enhanced Overview content
- Allergy cross-reference: amber warning chips with AlertTriangle icon, cross-reactivity advisory, green "no allergies" state
- Key Labs panel: LOINC-matched panels with trend arrows and collapsible-per-panel layout

**BUILD-004** — Corpus Stats page (`/explorer/corpus`)
- KPI bar: 1,180 patients, 46,868 encounters, 527,113 resources, avg age 48.2
- Gender split: CSS bar (Male 48.1% / Female 51.9%)
- Complexity tiers: color-coded cards (Simple green / Moderate blue / Complex amber / Highly Complex red)
- Clinical averages grid

**BUILD-005** — Pre-Op Safety page (`/explorer/safety`)
- Wired existing `DrugClassifier` from `patient-journey/core/` into FastAPI
- `/patients/{id}/safety` endpoint: classifies all medications into 10 surgical risk drug classes
- Safety page: ACTIVE/HISTORICAL/NONE status per class, severity-colored left borders, collapsible med lists, all-clear state

**BUILD-006** — UX polish on Explorer
- Encounter Composition Panel in Timeline: per-class avg obs/conditions/procedures/meds, collapsible
- Overview skeleton loading: full-layout skeleton (matches card structure) instead of generic spinner

**BUILD-007** — Immunizations page (`/explorer/immunizations`)
- `/patients/{id}/immunizations` endpoint
- Year-grouped timeline with CVX codes, status badges, vaccine chip summary at top

**BUILD-008** — Condition Acuity backend
- `api/core/condition_ranker.py`: keyword-based surgical risk ranker, 11 categories
- `/patients/{id}/condition-acuity` endpoint: ranked active + resolved conditions

**BUILD-009** — Conditions page (`/explorer/conditions`)
- Anesthesia Risk Spotlight: PULMONARY/CARDIAC/METABOLIC conditions highlighted in amber panel
- Active conditions grouped by risk category in priority order
- Resolved conditions collapsible (collapsed by default)

**BUILD-010** — Procedures page (`/explorer/procedures`)
- `/patients/{id}/procedures` endpoint
- Year-grouped procedure history with status badges and reason display

**BUILD-011** — Lab sparklines
- `LabHistoryPoint` model + `history` array in key-labs response (up to 10 readings, oldest first)
- `Sparkline` component in Overview: inline SVG polyline + dot, blue/red/gray trend coloring
- Graceful fallback when < 2 history points

**BUILD-012** (in progress at commit time) — Collapsible Overview sections
- `useSectionPrefs` hook with localStorage persistence
- `CollapsibleSection` wrapper component
- Each major Overview section individually collapsible

**BUILD-013** — Encounter context preservation
- Scroll position restore in Timeline when preview pane closes (50ms reflow delay)
- Encounter breadcrumb: `Timeline › Date › Type › Encounter preview` with close button

**BUILD-014** (in progress at commit time) — Field Coverage Profiler
- `/corpus/field-coverage` endpoint
- Checks 20 FHIR fields across all patients, reports Always/Usually/Sometimes/Rarely coverage

---

## What worked well

**Parallel builds with file ownership.** The key insight was treating each file as a mutex. Build agents were given explicit "files you may touch / files you must not touch" instructions. This let us run 2-3 agents in parallel with zero conflicts in practice.

**Research → Queue → Build pipeline.** Starting with 3 research agents from different perspectives (Clinician, Data, UX) produced a 21-item backlog in one pass. The queue file (`.claude/feature-queue.md`) served as the shared state for the orchestration loop.

**Backend-first when uncertain.** When two builds might conflict on shared files, sending one agent to do backend-only work while another does frontend-only work kept things clean.

**Smoke testing after every backend change.** Every backend build was smoke-tested with curl before being declared done. This caught a few issues (import errors, timezone-naive datetime conflicts) before they accumulated.

**LRU cache for performance.** Adding `@lru_cache(maxsize=30)` to `load_patient()` meant that clicking through multiple encounters for the same patient went from ~200ms per click (disk parse) to <1ms after the first load.

---

## What to watch for

**Stale queue entries.** The queue file accumulated completed items that still showed as "queued." The orchestrator cleaned these up mid-session but it required manual intervention. A better system would have build agents mark their own items complete.

**models.py as a bottleneck.** Multiple agents needed to add new Pydantic models to `api/models.py`. This file was a write conflict risk throughout the session. Consider splitting it into per-domain model files (`models/patient.py`, `models/corpus.py`, etc.).

**patients.py as a bottleneck.** Similarly, `api/routers/patients.py` grew to contain all patient endpoints. It should be split into sub-routers before it gets much larger.

**Corpus endpoints are slow on cold start.** `GET /corpus/stats` loads all 1,180 bundles sequentially. This is acceptably fast after the LRU cache warms up (~30-60 seconds), but the first request will time out if the client has a short timeout. Consider a background warmup task on server startup, or pre-computed stats files.

---

## Files created this session

### Backend (new)
- `api/main.py`
- `api/models.py`
- `api/routers/patients.py`
- `api/routers/corpus.py`
- `api/core/loader.py`
- `api/core/condition_ranker.py`

### Frontend pages (new)
- `app/src/pages/Explorer/Overview.tsx`
- `app/src/pages/Explorer/Timeline.tsx`
- `app/src/pages/Explorer/Safety.tsx`
- `app/src/pages/Explorer/Conditions.tsx`
- `app/src/pages/Explorer/Procedures.tsx`
- `app/src/pages/Explorer/Immunizations.tsx`
- `app/src/pages/Explorer/Corpus.tsx`

### Frontend components (new)
- `app/src/components/Layout.tsx`
- `app/src/components/CommandPalette.tsx`
- `app/src/components/EmptyState.tsx`

### Frontend hooks (new)
- `app/src/hooks/useFavorites.ts`

### Infrastructure
- `app/src/App.tsx`
- `app/src/api/client.ts`
- `app/src/types/index.ts`
- `app/src/index.css`
- `app/vite.config.ts`

### Documentation (new)
- `docs/FEATURE-REFERENCE.md`
- `docs/ROADMAP.md`
- `docs/SPRINT-NOTES-2026-04-05.md`
- `.claude/feature-queue.md`
- `.claude/build-log.md`

---

## Next session priorities

1. **Patient Journey MVP** — the 30-second clinical briefing card. This is the core product for Phase 1 demo. Should feel like a risk dashboard, not a data browser.
2. **Pick the demo patient** — find the most compelling patient in the 1,180-patient corpus: active cardiac condition, anticoagulant, recent labs, interesting allergy history.
3. **NL Search / Clinical Q&A** — Claude Haiku endpoint with 5-layer context pipeline. The streaming Q&A feature is the "wow" moment for demo judges.
4. **Deployment** — stand up the Hetzner VPS, get a live URL before May 13 deadline.
