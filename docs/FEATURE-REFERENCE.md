# Feature Reference — EHI Ignite Explorer

> Built during the April 5, 2026 sprint. Covers all pages, API endpoints, and UX components shipped in the FastAPI + React rewrite.

---

## Application Overview

The EHI Ignite Explorer is a clinical intelligence web application built on top of 1,180 Synthea FHIR R4 patient bundles. It serves two audiences simultaneously:

- **Data analysts** exploring FHIR structure, coverage, and population patterns
- **Clinicians / surgeons** doing rapid pre-operative chart review

The architecture is a FastAPI backend (Python 3.13) that reuses the existing `fhir_explorer` parser, served to a React + TypeScript + Tailwind CSS v4 frontend via a Vite dev proxy.

---

## Explorer Pages

### Overview (`/explorer`)
**What it does:** The primary patient detail view. Loads a full patient bundle and surfaces the most clinically relevant facts in a single scrollable page.

**Sections:**
- **KPI bar** — total resources, clinical vs. billing split, years of history, complexity score
- **Demographics** — name, age, gender, DOB, race, ethnicity, city/state, language, marital status
- **DALY/QALY** — disability-adjusted and quality-adjusted life year estimates
- **Resource type breakdown** — counts by FHIR resource type with Clinical/Billing/Administrative categories
- **Active Conditions** — table of active diagnoses with onset dates
- **Active Medications** — table with status, authored date
- **Allergies & Sensitivities** — amber warning chips with cross-reactivity advisory note; green "no allergies" state
- **Immunizations** — vaccine chip summary
- **Key Labs Panel** — LOINC-matched panels (Hematology, Metabolic, Coagulation, Cardiac) with most recent value, trend arrow (↑↓→), and sparkline chart for historical readings
- **Collapsible sections** — each major section can be collapsed; preferences saved to localStorage

**API:** `GET /api/patients/{id}/overview`, `GET /api/patients/{id}/key-labs`

---

### Timeline (`/explorer/timeline`)
**What it does:** Chronological encounter history with filtering, sorting, and a full encounter preview pane.

**Features:**
- **Year filter pills** — click any year bar to filter; mini sparkbar chart shows encounter density by year
- **Composition stats panel** — collapsible bar showing avg obs/conditions/procedures/meds per encounter class
- **Table** — sortable by date/class/type, filterable by encounter class (AMB/IMP/EMER/VR)
- **Arrow key navigation** — click a row to select, then ↑↓ to move through the list; auto-scrolls selected row into view
- **Encounter preview pane** — slides in from the right with:
  - *Summary tab:* key fields (type, reason, date, duration, provider, org) + linked resource counts
  - *Details tab:* full observation list (LOINC code + value + unit), conditions, procedures, medications
  - *Raw FHIR button* (`</>`) — opens modal with the exact FHIR Encounter resource JSON; copy-to-clipboard
- **Encounter breadcrumb** — shows `Timeline › Date › Type › Encounter preview` when pane is open; close button
- **Scroll position restore** — table scroll position is restored when the preview pane is closed

**API:** `GET /api/patients/{id}/timeline`, `GET /api/patients/{id}/encounters/{enc_id}`, `GET /api/patients/{id}/encounters/{enc_id}/raw`

---

### Safety (`/explorer/safety`)
**What it does:** Pre-operative medication safety panel. Classifies all of a patient's medications into surgical risk categories.

**Drug classes flagged:**
- Anticoagulants / Blood Thinners (critical) — warfarin, heparin, apixaban, rivaroxaban
- Antiplatelet Agents (critical) — aspirin, clopidogrel, ticagrelor
- JAK Inhibitors (critical) — tofacitinib, baricitinib, upadacitinib
- Immunosuppressants (critical) — tacrolimus, cyclosporine, mycophenolate
- NSAIDs (warning) — ibuprofen, naproxen, indomethacin
- Opioids (warning) — morphine, oxycodone, fentanyl, tramadol
- Anticonvulsants (warning) — phenytoin, carbamazepine, valproate, levetiracetam
- Corticosteroids (warning) — prednisone, dexamethasone, methylprednisolone
- MAOIs (warning) — phenelzine, tranylcypromine
- Antidiabetics (info) — metformin, insulin, glipizide

**Status per class:**
- `ACTIVE` — patient currently on this drug class (red/amber badge)
- `HISTORICAL` — past medication in this class (muted badge)
- `NONE` — no medications in this class (not shown)

**All-clear state:** Green "No surgical risk medications detected" card when all classes are NONE.

**API:** `GET /api/patients/{id}/safety`

---

### Conditions (`/explorer/conditions`)
**What it does:** Active and resolved conditions ranked by surgical relevance, with an anesthesia risk spotlight.

**Anesthesia Risk Spotlight:** Amber panel at top showing any PULMONARY (OSA, COPD, respiratory), CARDIAC (severe), or METABOLIC (diabetes, obesity) conditions that directly affect anesthesia planning.

**11 surgical risk categories (ranked):**
1. Cardiac — heart failure, arrhythmia, hypertension, CAD, valve disease
2. Pulmonary — COPD, sleep apnea, asthma, interstitial lung disease
3. Metabolic — diabetes, obesity, thyroid disorders
4. Renal — CKD, dialysis, nephrotic syndrome
5. Hepatic — cirrhosis, hepatitis, portal hypertension
6. Hematologic — anemia, coagulopathy, thrombocytopenia
7. Neurologic — seizure disorder, stroke, Parkinson's, dementia
8. Immunologic — HIV, lupus, rheumatoid arthritis, IBD
9. Oncologic — cancer, malignancy, metastatic disease
10. Vascular — PAD, DVT, aortic aneurysm
11. Other — everything else

Active conditions grouped by category in risk rank order. Resolved conditions collapsible (collapsed by default).

**API:** `GET /api/patients/{id}/condition-acuity`

---

### Procedures (`/explorer/procedures`)
**What it does:** Full procedure history grouped by year, sorted most recent first.

Each procedure shows: date, display name, status badge (completed/stopped/error), reason in muted text.

**API:** `GET /api/patients/{id}/procedures`

---

### Immunizations (`/explorer/immunizations`)
**What it does:** Complete vaccination history with CVX codes, grouped by year.

Shows: vaccine chip summary at top (deduped names), then year-grouped timeline rows with date, full vaccine name, CVX code badge, and status badge.

**API:** `GET /api/patients/{id}/immunizations`

---

### Corpus (`/explorer/corpus`)
**What it does:** Population-level statistics across all 1,180 patients in the dataset.

- **KPI bar:** Total patients, total encounters (46,868), total resources (527,113), avg age (48.2)
- **Gender split:** CSS horizontal bar — Male 48.1% / Female 51.9%
- **Complexity tiers:** Simple (42%) / Moderate (44%) / Complex (13%) / Highly Complex (1%)
- **Clinical averages per patient:** avg encounters (39.7), active conditions (3.5), active meds (1.8), resources per patient (446)

Note: First load parses all 1,180 bundles (~30 seconds). Subsequent loads are instant via LRU cache.

**API:** `GET /api/corpus/stats`

---

## Global UX Components

### Command Palette (Cmd+K / Ctrl+K)
Accessible from any page. Instant patient search with arrow key navigation, complexity tier badge, Enter to navigate to that patient's overview. Escape to close.

### Patient Bookmarks / Favorites
Star icon on each patient in the sidebar. Favorited patients appear at the top of the list under a "Favorites" section header. Stored in localStorage (`ehi-favorites`).

### Smart Empty States
Every page shows a helpful empty state when no patient is selected — with page-specific bullets describing what the view contains and a "1,180 patients available" stat.

### Skeleton Loading
Overview page shows a full-layout skeleton (matching card structure, table rows, section layout) while the bundle loads, instead of a generic spinner.

---

## Backend API Reference

| Endpoint | Description |
|---|---|
| `GET /api/patients` | Fast patient list (filename parsing, no bundle load) |
| `GET /api/patients/loaded` | Patient list with computed stats (slow) |
| `GET /api/patients/{id}/overview` | Full patient overview — all demographics and stats |
| `GET /api/patients/{id}/timeline` | Encounter list with year density counts |
| `GET /api/patients/{id}/encounters/{enc_id}` | Full encounter detail with linked resources |
| `GET /api/patients/{id}/encounters/{enc_id}/raw` | Raw FHIR Encounter resource JSON |
| `GET /api/patients/{id}/key-labs` | LOINC-matched lab panels with trend + history |
| `GET /api/patients/{id}/safety` | Pre-op drug class safety flags |
| `GET /api/patients/{id}/condition-acuity` | Conditions ranked by surgical risk category |
| `GET /api/patients/{id}/procedures` | Full procedure history |
| `GET /api/patients/{id}/immunizations` | Immunization history |
| `GET /api/corpus/stats` | Population-level aggregate statistics |
| `GET /api/corpus/field-coverage` | FHIR field population rates across corpus |

### Performance
All patient bundles are parsed once and cached in-memory via `functools.lru_cache(maxsize=30)` in `api/core/loader.py`. First request for a patient takes ~100-300ms (disk parse); repeat requests are <1ms.

---

## Internal Modules

### `api/core/condition_ranker.py`
Keyword-based surgical risk ranker. Maps condition display names to 11 risk categories using substring matching. Instantiated as a module-level singleton. No external dependencies.

### `api/core/drug_classifier.py` (from `patient-journey/core/`)
Drug class classifier using `patient-journey/data/drug_classes.json` keyword + RxNorm mapping. Produces `SafetyFlag` objects with ACTIVE/HISTORICAL/NONE status.
