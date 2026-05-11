# Patient Journey Application
## Product Definition, Vision & Specs

*Created: March 29, 2026 — Based on clinical insights from Max Gibber (Neurosurgeon)*

---

## The Problem

When a physician receives a patient for an urgent or surgical case, they're handed a physical or digital stack of chart history. Before operating, they must rapidly answer critical questions:

- Is the patient on blood thinners or anticoagulants?
- Any immunosuppressants (JAK inhibitors, steroids, tacrolimus)?
- ACE inhibitors or other cardiac/hemodynamic meds?
- History of drug use — illicit or prescription opioids?
- What conditions has this patient been managing, and for how long?
- What treatment cycles have they been through? How did they respond?
- When were medications started, stopped, or changed?
- What hospitalizations, ER visits, or procedures are in their history?

Today this is purely manual — linear reading through unstructured documents under time pressure. The data is there. The tooling is not.

---

## Product Vision

**A clinician-facing patient history and journey visualization tool.**

Think of it like a *git history for a patient's health* — a scannable, filterable, searchable timeline of the patient's full clinical journey. Designed for the doctor who has 5 minutes before a case, not an hour.

The primary users in this context are:
- **Surgeons and neurosurgeons** reviewing chart history before a case
- **Anesthesiologists** running pre-op checklists
- **Emergency physicians** orienting to a complex patient quickly
- **Psychiatrists** tracking medication episodes and hospitalization history
- **Any clinician** receiving a referral patient with an unknown history

---

## Core Features

### 1. Patient Journey Timeline

A chronological, visual timeline of the patient's clinical life.

- **Horizontal timeline** spanning the patient's full history
- **Medication bars** — each drug displayed as a horizontal bar showing duration on/off (like a Gantt chart). Color-coded by drug class.
- **Clinical events overlaid** — hospitalizations, surgeries, ER visits, diagnoses. Shown as markers on the timeline.
- **Zoom in/out** — view the last 6 months or the full 20-year history
- **Filter by category** — medications only, diagnoses only, procedures only, or combined
- **Episode detection** — automatically detect when a medication was started, stopped, dose changed, or restarted

**Inspiration:** Think of it like a Gantt chart + event log, built for clinical reading speed.

---

### 2. Pre-Surgery / Pre-Procedure Safety Panel

A dedicated "flags" view that answers the surgical pre-op checklist automatically.

Auto-populated from medication history:

| Flag | Status | Details |
|---|---|---|
| ⚠️ Blood Thinners | ACTIVE | Warfarin 5mg since Jan 2022. Last INR: 3.1 (March 2024) |
| ⚠️ ACE Inhibitors | ACTIVE | Lisinopril 10mg since 2019 |
| ✅ JAK Inhibitors | None found | — |
| ⚠️ Opioid History | HISTORICAL | Hydrocodone 2018–2020, Oxycodone 2021 (post-op) |
| ✅ Immunosuppressants | None found | — |
| ✅ NSAIDs | None active | Ibuprofen PRN, stopped 2023 |
| ⚠️ Psych Meds | ACTIVE | Sertraline 100mg (2020–present) |

**Drug categories to flag (surgical safety focus):**

| Category | Examples |
|---|---|
| Anticoagulants / Blood Thinners | Warfarin, Eliquis (apixaban), Xarelto, Heparin, Plavix (clopidogrel), Aspirin (antiplatelet) |
| JAK Inhibitors | Tofacitinib (Xeljanz), Baricitinib (Olumiant), Upadacitinib |
| ACE Inhibitors | Lisinopril, Enalapril, Ramipril, Benazepril |
| ARBs | Losartan, Valsartan, Irbesartan |
| Immunosuppressants | Tacrolimus, Cyclosporine, Mycophenolate, Prednisone, Methotrexate |
| NSAIDs | Ibuprofen, Naproxen, Ketorolac |
| Anticonvulsants | Phenytoin, Valproate, Carbamazepine |
| MAOIs / Psych meds | Phenelzine, high-dose SSRIs, TCAs |
| Opioid history | Any prior or current opioid prescription |
| Stimulants | Adderall, Ritalin, cocaine history |
| Illicit drug use | Any documented substance use disorder |

---

### 3. Natural Language Search

Clinician types a question and gets an answer with evidence:

> *"Has this patient been on blood thinners in the last 5 years?"*
> → Yes. Warfarin 5mg (2022–present, active). Plavix (2019–2021, stopped after stent placement).

> *"What surgeries has this patient had?"*
> → 3 procedures found: Coronary stent placement (March 2019), Appendectomy (June 2014), Knee arthroscopy (November 2021).

> *"Is this patient immunocompromised?"*
> → Possibly. On Methotrexate 15mg/week (active, for rheumatoid arthritis) + Prednisone 5mg daily. No transplant history found.

The LLM has access to the patient's parsed FHIR data and answers with citations back to specific resources.

---

### 4. Medication History Deep Dive

A dedicated medication view separate from the timeline:

- Full medication history (active + historical)
- Per-drug detail card: when started, dosage over time, why stopped, who prescribed
- Drug class grouping (anticoagulants, cardiac, psych, pain, etc.)
- **Interaction highlighter** — flag current active meds that interact with each other or with a proposed procedure
- Treatment cycle detection — "Patient has had 3 cycles of methotrexate over 10 years"

---

### 5. Condition & Episode Tracker

- Active conditions vs. resolved vs. historical
- Timeline of when each condition was diagnosed
- Related medications linked to each condition
- Hospitalization episodes tied to condition flares
- **Recurrence detection** — "This patient has had 4 DVT episodes since 2015"

---

## Technical Architecture

### Data Source

- **Input:** FHIR R4 patient bundle (JSON) — from Synthea for development, real EHI exports for production
- **Parser:** Existing `fhir_explorer/parser/` layer (already built) — reuse `bundle_parser.py`, `models.py`, `extractors.py`
- **Internal model:** `PatientRecord` (already defined in `models.py`)

### Application Stack

- **Framework:** Streamlit (consistent with existing fhir_explorer) OR a dedicated FastAPI + React frontend for the contest submission (more polished)
- **Visualization:** Plotly for timeline charts, medication Gantt, encounter density
- **LLM layer:** Anthropic Claude for natural language search (structured tool calls over patient data)
- **Drug safety data:** OpenFDA Drug Interaction API + custom surgical risk classification list
- **Storage:** In-memory for single-patient session; DuckDB for multi-patient corpus

### Key New Components Needed

1. **Medication Gantt chart** — horizontal bar chart per drug, showing active date ranges
2. **Pre-op safety panel** — rule-based flag generator from medication list
3. **Drug class classifier** — map RxNorm codes → drug class → safety category
4. **NLP search layer** — LLM with FHIR data as context, structured Q&A
5. **Episode detector** — detect starts/stops/changes in medication history

### Reuse from fhir_explorer

| Existing Component | Reuse For |
|---|---|
| `parser/bundle_parser.py` | Load and parse FHIR bundles |
| `parser/models.py` | PatientRecord, Medication, Condition, Encounter models |
| `parser/extractors.py` | Resource extraction logic |
| `views/timeline.py` | Encounter timeline (extend with medication layer) |
| `views/signal_filter.py` | Signal tiering logic for LLM context window |
| `catalog/single_patient.py` | Patient stats and complexity scoring |

---

## File Structure (New Application)

```
patient-journey/
├── README.md
├── requirements.txt
├── app.py                    # Streamlit entry point
├── core/
│   ├── __init__.py
│   ├── loader.py             # FHIR bundle loader (wraps existing parser)
│   ├── drug_classifier.py    # RxNorm → drug class → surgical risk flag
│   ├── episode_detector.py   # Medication start/stop/change detection
│   └── interaction_checker.py # OpenFDA drug interaction checks
├── views/
│   ├── __init__.py
│   ├── journey_timeline.py   # Combined medication + event Gantt timeline
│   ├── safety_panel.py       # Pre-op surgical flags panel
│   ├── medication_history.py # Full medication deep dive view
│   ├── condition_tracker.py  # Conditions + episodes
│   └── nl_search.py          # Natural language search (LLM-backed)
├── data/
│   └── drug_classes.json     # Manual drug class → surgical risk mapping
└── tests/
    └── test_drug_classifier.py
```

---

## Clinical Use Cases (Priority Order)

1. **Neurosurgery pre-op** — Max's use case. Surgeon reviewing chart 24–48h before case.
2. **Anesthesia pre-op** — Drug interactions, hemodynamic risk, airway history.
3. **ER handoff** — Patient admitted emergently, covering team needs rapid orientation.
4. **Psychiatric history review** — Taylor's use case. Episode tracking, hospitalization history, psych med timeline.
5. **Referral intake** — New specialist seeing a referred patient for the first time.

---

## Phase 1 Contest Alignment

This application maps directly to EHI Ignite Phase 1 evaluation criteria:

| Criterion | How This Addresses It |
|---|---|
| **Usable health information summary** ✅ Required | Pre-op safety panel + patient overview |
| **Clinical domain filtering** | Drug class filtering, specialty-relevant views |
| **Interactive patient tools** | Natural language search, custom date ranges |
| **User experience / usability** | Timeline visualization beats wall-of-text charts |
| **AI innovation** | LLM-backed NL search over structured FHIR data |
| **Technical feasibility** | Built on top of already-working FHIR parser |

---

## Coding Session Prompt

> Use this prompt to kick off a new Claude Code session:

```
I'm building a Patient Journey Application as part of the EHI Ignite Challenge — an HHS-sponsored $490K competition to improve how electronic health information is used clinically.

The application is a clinician-facing patient history visualization tool. The core problem: surgeons and physicians receiving a patient for a case are handed a stack of unstructured chart history and need to quickly answer critical pre-surgical safety questions (is the patient on blood thinners? anticoagulants? JAK inhibitors? opioid history?).

This application is a new Streamlit app that builds on top of an existing FHIR parsing layer already in this repo (fhir_explorer/parser/).

Please read the following files to orient yourself:
- ideas/PATIENT-JOURNEY-APP.md — full product definition, features, and specs
- fhir_explorer/parser/models.py — the PatientRecord data model we'll build on
- fhir_explorer/parser/extractors.py — how we extract FHIR resources
- fhir_explorer/views/timeline.py — existing timeline view to reference
- fhir_explorer/views/signal_filter.py — signal tiering logic

Build the new application in a new top-level directory: patient-journey/

Start with:
1. app.py — Streamlit shell with sidebar (FHIR file picker) and page navigation
2. core/loader.py — wraps the existing parser to load a PatientRecord from a FHIR bundle JSON
3. core/drug_classifier.py — maps medication display names and RxNorm codes to drug classes and surgical risk flags (anticoagulants, JAK inhibitors, ACE inhibitors, immunosuppressants, opioids, etc.)
4. views/safety_panel.py — the Pre-Op Safety Panel: a table of surgical risk flags auto-populated from the patient's medication history, showing status (ACTIVE / HISTORICAL / NONE), drug name, dose, and dates
5. views/journey_timeline.py — a Plotly Gantt-style medication timeline showing each drug as a horizontal bar over time, with encounter events overlaid as markers

Use the existing Synthea sample data in data/synthea-samples/ for testing.
Keep code clean, typed, and consistent with the style in fhir_explorer/.
```

---

*Created by Chief · March 29, 2026*
*Source: Phone call with Max Gibber (Neurosurgeon) + Blake Thomson*
