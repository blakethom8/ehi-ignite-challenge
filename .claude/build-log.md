# EHI Build Log

> Auto-maintained by the orchestration loop. Each entry = one build cycle.

---

## 2026-04-05 — BUILD-016: Recent Lab Alert Flags

**Feature:** Flag labs from the last 30 days that are abnormal or trending toward critical.

**Backend changes:**
- `api/models.py` — Added `LabAlertFlag` Pydantic model (`lab_name`, `loinc_code`, `value`, `unit`, `severity`, `direction`, `message`, `days_ago`). Added `alert_flags: list[LabAlertFlag] = []` to `KeyLabsResponse`.
- `api/routers/patients.py` — Added `ALERT_THRESHOLDS` dict (10 LOINC codes: Hemoglobin, Hematocrit, Platelets, INR, Creatinine, Potassium, Sodium, Glucose, Albumin, Alk Phos). Added `_obs_date_to_date()` helper and `_compute_alert_flags()` function: filters to last-30-day observations, applies critical/warning thresholds, checks 3-reading trend (>5% consistent direction = trending_up/down at warning), deduplicates to most recent per LOINC, sorts critical-first.

**Frontend changes:**
- `app/src/types/index.ts` — Added `LabAlertFlag` interface; extended `KeyLabsResponse` with `alert_flags`.
- `app/src/pages/Explorer/Overview.tsx` — Added `LabAlertBanner` component: collapsible bar with AlertTriangle icon, red CRITICAL / amber WARNING chips per flag, message and days-ago label. Inserted above panel list in Key Labs section.

**Note:** Synthea data uses historical dates so no alerts fire on the corpus (by design — the 30-day window is relative to today). Logic verified correct via inline unit test with synthetic edge-case values.

**TSC:** zero errors.

---

## 2026-04-05 — BUILD-017: Medication Hold/Bridge Protocol Guidance

**Feature:** Per-drug-class pre-operative hold/bridge protocol notes surfaced as collapsible sections on the Safety page.

**Backend changes:**
- `api/models.py` — Added `protocol_note: str | None = None` to `SafetyFlag`.
- `api/routers/patients.py` — Added `PROTOCOL_NOTES` dict with detailed clinical guidance for 10 drug classes (anticoagulants, antiplatelets, JAK inhibitors, immunosuppressants, NSAIDs, opioids, anticonvulsants, corticosteroids, MAOIs, antidiabetics). Wired into `patient_safety` endpoint via `PROTOCOL_NOTES.get(rf.class_key)`.

**Frontend changes:**
- `app/src/types/index.ts` — Added `protocol_note?: string | null` to `SafetyFlag`.
- `app/src/pages/Explorer/Safety.tsx` — Added `BookOpen` import; per-card `protocolOpen` state; collapsible "Pre-Op Protocol" section rendered below medication list for ACTIVE and HISTORICAL cards that have a protocol note.

**Smoke test:** Protocol notes present for all 10 mapped classes, null for unmapped classes (ace_inhibitors, arbs, psych_medications, stimulants, diabetes_medications). Correct.

**TSC:** zero errors.

---

## 2026-04-05 — BUILD-018: Pre-Op Decision Card

**Feature:** Unified pre-operative readiness card at the top of the Overview page.

**Frontend changes (`app/src/pages/Explorer/Overview.tsx`):**
- Added `PreOpDecisionCard` component making 3 parallel React Query calls (safety, condition-acuity, key-labs)
- Computes FLAGGED/REVIEW/CLEARED per domain (Medications, Conditions, Labs) using inline logic mirroring Clearance.tsx
- Overall status bar: colored left border + background, bold status label
- 3 domain chips with Pill/Heart/FlaskConical icons + status badge
- Top-concern text: first ACTIVE critical drug class or flagged condition name
- Drill-down nav buttons: → Clearance, → Safety (useNavigate preserving ?patient= param)
- 2-line skeleton while loading; returns null if no patient selected
- Inserted as first child of OverviewContent, above KPI bar

**TSC:** zero errors.

---

## 2026-04-05 — BUILD-019: Risk-Filtered Patient Sidebar

**Feature:** Segmented filter toggle + per-row risk dots in the patient sidebar.

**Backend changes:**
- `api/models.py` — Added `PatientRiskSummary` and `PatientRiskSummaryResponse` models
- `api/routers/patients.py` — Added `GET /api/patients/risk-summary` endpoint (placed before `{patient_id}` routes to avoid routing conflict). Iterates all 1,180 patients via `load_patient()`, runs `_classifier.generate_safety_flags()` to detect active critical flags. Returns tier + has_critical_flag + active_critical_classes.

**Frontend changes:**
- `app/src/types/index.ts` — Added `PatientRiskSummary` interface
- `app/src/api/client.ts` — Added `getRiskSummary()` call
- `app/src/components/Layout.tsx` — Added filter toggle (All/High Risk/Needs Review) with pill styling; React Query fetch enabled only when filter active (5-min stale); red/amber risk dots per row; skeleton + empty state for filtered views

**Smoke test:** Total=1180, has_critical_flag=109, high_risk_tier=168. Correct.

**TSC:** zero errors.

---

## 2026-04-05 — BUILD-020: Observation Distributions

**Feature:** Corpus-level LOINC lab value distributions with percentile stats and histograms.

**Backend (`api/routers/corpus.py`):**
- `GET /api/corpus/observation-distributions` — iterates all 1,180 patients, collects float values keyed by LOINC code, filters to codes with ≥20 data points, caps at top 30 by count
- Computes min/max/mean/median/p10/p25/p75/p90 + 10-bucket histogram with evenly-spaced labels
- Resolves most-common display name and unit per code; sorts descending by count

**Backend (`api/models.py`):** Added `ObservationDistribution` and `ObservationDistributionsResponse`.

**Frontend (`app/src/pages/Explorer/Distributions.tsx`):** New page — KPI strip (99 LOINC codes found, 30 shown), client-side search filter, 2-col card grid. Each card: stats row, CSS-only percentile bar (min/p10/IQR/p90/max whiskers), 10-bar inline histogram with hover tooltips.

**Other frontend:** `App.tsx` route, `Layout.tsx` nav entry (BarChart2 icon), `client.ts` API call, `types/index.ts` interfaces.

**Smoke test:** top code = Pain severity (72514-3), n=17,837, mean=2.7. 99 LOINC codes found, 30 shown. Correct.

**TSC:** zero errors.

---

## 2026-04-05 — BUILD-021: Structured Data Export

**Feature:** ZIP download of 6 normalized CSVs from the full patient corpus.

**Backend (`api/routers/corpus.py`):**
- `GET /api/corpus/export?format=csv&limit=N` — stdlib only (io, csv, zipfile). Single-pass iteration over all patients, writes 6 CSV writers simultaneously, packs into deflate-compressed ZIP, returns StreamingResponse with application/zip.
- Tables: patients, encounters, conditions, medications, observations, procedures.
- `limit=0` exports all 1,180; non-zero limits for testing.

**Frontend (`app/src/pages/Explorer/Corpus.tsx`):** Added `<a href="/api/corpus/export" download="ehi-export.zip">` button with Download icon in page header.

**Smoke test (limit=5):** ZIP contents correct — 5 patient rows, 100 encounter rows, 838 observation rows. All 6 files present.

**TSC:** zero errors.

---

## 2026-04-05 — BUILD-022: Lab Critical-Change Timeline

**Feature:** Collapsible 6-month lab observation timeline with clickable month dots in the Key Labs section of Overview.

**Backend (`api/models.py`):** Added `TimelineEvent` (loinc_code, display_name, value, unit, date, change_direction) and `TimelineMonth` (month, label, events). Extended `KeyLabsResponse` with `timeline_events: list[TimelineMonth] = []`.

**Backend (`api/routers/patients.py`):** Added `_compute_timeline_events()` — builds 6 monthly buckets over the trailing 6 months, matches observations to the 10 ALERT_THRESHOLDS LOINC codes, computes `change_direction` (up/down/stable, >5% delta threshold) by comparing to prior month. Only months with ≥1 event included.

**Frontend (`app/src/types/index.ts`):** Added `TimelineEvent`, `TimelineMonth` interfaces; `timeline_events` on `KeyLabsResponse`.

**Frontend (`app/src/pages/Explorer/Overview.tsx`):** Added `LabHistoryTimeline` component — horizontal CSS dot timeline, dots colored red/amber/blue by critical-code direction, click toggles per-month popover table (lab name, value+unit, change arrow ↑↓→, date). Wrapped in CollapsibleSection (collapsed by default). Inserted between LabAlertBanner and panels list.

**Note:** Synthea data predates the 6-month window so timeline_events is always [] on this corpus — logic verified with offset test date.

**TSC:** zero errors.

---

## 2026-04-05 — BUILD-023: Drug-Drug Interaction Checker

**Feature:** Static drug-drug interaction checker flagging known dangerous interactions between a patient's active medication classes.

**New file — `api/core/interaction_checker.py`:** `Interaction` dataclass + `INTERACTIONS` list of 10 clinically significant pairs (anticoagulants↔antiplatelets, anticoagulants↔NSAIDs, MAOIs↔opioids [contraindicated], MAOIs↔antidepressants [contraindicated], JAK inhibitors↔immunosuppressants, etc.). `check_interactions(active_class_keys)` returns sorted results (contraindicated → major → moderate).

**Backend (`api/models.py`):** Added `InteractionResult` (drug_a/b, labels, severity, mechanism, clinical_effect, management, actual med names) and `InteractionResponse`.

**Backend (`api/routers/patients.py`):** Added `GET /api/patients/{id}/interactions` — pulls active safety flags, extracts class keys and med names, runs `check_interactions()`, returns structured response.

**New file — `app/src/pages/Explorer/Interactions.tsx`:** KPI strip (contraindicated/major/moderate counts), per-interaction cards with severity badge, drug pair header, actual med name chips, collapsible Mechanism/Clinical Effect/Management rows. All-clear green state. Empty state for no patient selected.

**Modified (`app/src/pages/Explorer/Safety.tsx`):** Interaction alert banner at top — fetches `/interactions`, shows amber "X interactions detected → View Interactions" link when `has_interactions` is true.

**Other:** `App.tsx` route, `Layout.tsx` Zap icon nav entry (between Safety and Conditions), `client.ts` + `types/index.ts` additions.

**Smoke test:** Patient with warfarin + naproxen → 1 MAJOR interaction (Anticoagulants ↔ NSAIDs). Correct.

**TSC:** zero errors.
