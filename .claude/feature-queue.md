# EHI Feature Queue

> Orchestrated build loop. Research agents populate this. Build agents consume it.
> Perspectives: (C) Clinician/Surgeon · (D) Data Transparency · (U) UX/Product

---

## 🔨 In Progress
_none_

---

## 📋 Queued (priority order — genuine remaining work)

### MEDIUM complexity
3. **(D) Observation Distributions** — Corpus-level histogram + percentile stats for quantitative labs (LOINC). New `/corpus/observation-distributions` endpoint.
4. **(D) Structured Data Export (CSV/JSON)** — Download patient cohort data as normalized CSVs (one per resource type). New `/corpus/export` endpoint.
5. **(C) Recent Lab Alert Flags** — Flag labs from the last 30 days that are abnormal or trending toward critical (e.g. rising creatinine, falling Hgb). Adds `alert_flags` array to `/key-labs` response; renders amber/red badges in Overview.
6. **(C) Medication Hold/Bridge Protocol Guidance** — Per-drug-class protocol lookup (e.g. "Hold warfarin 5 days pre-op, bridge with LMWH if high-risk"). Static lookup table. Adds protocol_note field to Safety page drug class cards.

### HIGH complexity
7. **(D) Resource Linkage Graph** — Interactive viz of encounter ↔ observation ↔ condition ↔ med cross-references.
8. **(U) Patient Comparison Mode** — Side-by-side patient cards with multi-select in sidebar.
9. **(C) Drug-Drug Interaction Checker** — Flag interactions between current meds and common surgical drugs.

---

## ✅ Completed
- [x] Pre-Op Clearance Checklist — 3-domain readiness card (Meds/Conditions/Labs), CLEARED/FLAGGED/REVIEW per domain, overall status bar [BUILD-015]
- [x] Anesthesia Risk Summary Card — ASA I-IV derivation, anticoag/opioid panels, airway notes, printable layout [BUILD-015]
- [x] Scroll restore + encounter breadcrumb in Timeline (prevSelectedId ref, 50ms reflow delay) [BUILD-013]
- [x] Surgical Procedure History Page + `/procedures` endpoint (year-grouped, status badges) [BUILD-010]
- [x] Lab Sparklines (inline SVG + LabHistoryPoint history field in API, up to 10 readings) [BUILD-011]
- [x] Conditions Page (acuity ranking by category, anesthesia spotlight, collapsible resolved) [BUILD-009]
- [x] Condition Acuity Ranker (backend module + /condition-acuity endpoint, 11 surgical risk categories) [BUILD-008]
- [x] Immunization Timeline Page (year-grouped, CVX codes, vaccine chips) [BUILD-007]
- [x] Encounter Composition Panel (per-class avg obs/cond/proc/med, collapsible) [BUILD-006]
- [x] Overview Skeleton Loading States (matches real layout, animate-pulse) [BUILD-006]
- [x] Pre-Op Safety Flag Dashboard (drug classifier wired, ACTIVE/HISTORICAL/NONE per class) [BUILD-005]
- [x] Corpus Stats Page (KPI bar, gender split, complexity tiers, clinical averages) [BUILD-004]
- [x] Enhanced Allergy Display (amber warning chips, severity note, cross-reactivity warning) [BUILD-003]
- [x] Key Labs Panel in Overview (LOINC panels, trend arrows, collapsible per-panel) [BUILD-003]
- [x] Bookmarks/Favorites (localStorage, star icons, Favorites section in sidebar) [BUILD-001]
- [x] Command Palette (Cmd+K, fuzzy patient search, arrow nav, complexity badge) [BUILD-001]
- [x] Smart Empty States (EmptyState component, applied to Overview/Timeline/Journey) [BUILD-001]
- [x] Key Labs endpoint (`/patients/{id}/key-labs`) — LOINC panels, trend detection [BUILD-002]
- [x] Corpus stats endpoint (`/corpus/stats`) — 1,180 patients, gender/tier/avg breakdowns [BUILD-002]
- [x] Timeline table with sort/filter + class filter pills
- [x] Encounter preview pane (Summary + Details tabs)
- [x] Arrow key navigation in encounter table
- [x] Raw FHIR JSON modal with copy button
- [x] Year filter pills replacing Plotly chart
- [x] In-memory LRU cache for patient bundles

---

## 🔬 Research Log

**2026-04-05 — Initial research pass (3 agents)**
- Clinician agent: 10 features around surgical safety, medication holds, anesthesia risk, lab context
- Data agent: 10 features around field coverage, corpus analytics, observation distributions, export
- UX agent: 10 features around search, shortcuts, favorites, skeleton states, empty states, sparklines
- Prioritized 21 items into queue (7 Low, 11 Medium, 3 High)

**2026-04-05 — Research orchestrator cron (23-min cycle, pass 1)**
- Counted 20 queued items — exceeds threshold of 6. Skipping research pass. Queue is healthy.

**2026-04-05 — Research orchestrator cron (23-min cycle, pass 2)**
- Queue cleaned up: removed 11 already-completed items, 10 genuinely unbuilt remain.
- Still above threshold of 6. Skipping research pass.

**2026-04-05 — Build orchestrator cron (37-min cycle)**
- BUILD-009 in progress (Conditions page) — not stuck, let it run.
- Parallel backend-safe build: picked Surgical Procedure History (BUILD-010, non-overlapping files).

**2026-04-05 — Research orchestrator cron (23-min cycle, pass 3)**
- Queue had 5 genuine unbuilt items — below threshold of 6. Spawned Clinician research agent.
- Agent returned 4 new (C) features focused on Patient Journey MVP and Phase 1 demo needs:
  1. Pre-Op Clearance Checklist (Low) — no new API needed, composes from existing endpoints
  2. Anesthesia Risk Summary Card (Low) — composites Safety + Conditions data
  3. Recent Lab Alert Flags (Medium) — `alert_flags` array on `/key-labs` response
  4. Medication Hold/Bridge Protocol Guidance (Medium) — static protocol lookup table
- All 4 items appended to queue. Queue now at 9 items. Dispatching BUILD-015 (low-complexity pair).
