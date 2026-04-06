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
