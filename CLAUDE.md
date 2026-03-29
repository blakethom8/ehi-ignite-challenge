# CLAUDE.md — EHI Ignite Challenge Project Guide

> Read this file first. It tells you what this project is, how it's structured, what data is available, and what's already been built so you don't duplicate work.

---

## What This Project Is

This is the codebase for **Blake's submission to the EHI Ignite Challenge** — an HHS-sponsored $490K competition to build innovative applications that transform Electronic Health Information (EHI) into actionable clinical insights.

**Prize pool:** $490K across two phases  
**Phase 1 deadline:** May 13, 2026 (concept + wireframes)  
**Phase 2:** Summer 2026 – Spring 2027 (prototype)

**The core problem:** Patient health records are siloed, unstructured, and nearly impossible for clinicians to rapidly parse under time pressure. We're building tools to fix that.

---

## Repository Structure

```
ehi-ignite-challenge/
├── CLAUDE.md                          ← you are here
├── README.md                          ← project overview + contest details
│
├── ideas/                             ← product specs (read before building)
│   ├── FEATURE-IDEAS.md               ← full agent platform brainstorm
│   ├── PATIENT-JOURNEY-APP.md         ← spec for the Patient Journey application ⭐
│   └── FORMAT-AGNOSTIC-INGESTION.md   ← spec for the upstream ingestion service ⭐
│
├── fhir_explorer/                     ← EXISTING internal data exploration tool (Streamlit)
│   ├── app.py                         ← entry point: `streamlit run fhir_explorer/app.py`
│   ├── requirements.txt
│   ├── data-review-plan.md
│   ├── parser/                        ← FHIR parsing layer (reuse this in new apps)
│   │   ├── bundle_parser.py           ← parses a FHIR R4 JSON bundle → PatientRecord
│   │   ├── extractors.py              ← resource-type extractors (Condition, Med, etc.)
│   │   └── models.py                  ← PatientRecord + all data models (source of truth)
│   ├── catalog/
│   │   ├── corpus.py                  ← multi-patient corpus analysis
│   │   ├── field_profiler.py          ← FHIR field coverage profiling
│   │   └── single_patient.py          ← PatientStats + complexity scoring
│   └── views/                         ← Streamlit pages
│       ├── overview.py                ← patient summary
│       ├── timeline.py                ← encounter timeline (chronological)
│       ├── encounter_hub.py           ← encounter detail browser
│       ├── signal_filter.py           ← LLM signal tiering + token budget
│       ├── catalog_view.py            ← code catalog (SNOMED, RxNorm, LOINC)
│       ├── corpus_view.py             ← multi-patient corpus view
│       └── field_profiler_view.py     ← field coverage analysis
│
├── data/
│   ├── synthea-samples/
│   │   ├── synthea-r4-individual/fhir/   ← 1,180 individual patient FHIR bundles (JSON)
│   │   │                                    ← PRIMARY TEST DATA — use these for development
│   │   ├── sample-bulk-fhir-datasets-10-patients/  ← bulk NDJSON format (10 patients)
│   │   │   ├── Patient.000.ndjson
│   │   │   ├── Condition.000.ndjson
│   │   │   ├── MedicationRequest.000.ndjson
│   │   │   ├── Encounter.000.ndjson
│   │   │   ├── Observation.000.ndjson
│   │   │   └── ... (all FHIR resource types)
│   │   └── synthea-r4-samples.zip
│   └── real-world-examples/              ← placeholder for real de-identified data
│
├── architecture/                         ← architecture docs
├── docs/
│   └── DATA-OVERVIEW.md
└── __init__.py
```

---

## Available Data

### Primary: Synthea Individual Patient Bundles

**Path:** `data/synthea-samples/synthea-r4-individual/fhir/`  
**Count:** 1,180 JSON files  
**Format:** FHIR R4 Bundle (each file = one patient's complete record)  
**Content:** Each bundle contains all FHIR resource types for that patient: Patient, Condition, Encounter, MedicationRequest, Observation, Procedure, DiagnosticReport, Immunization, AllergyIntolerance, CarePlan, etc.

These are the primary test files. The existing `fhir_explorer` parser is built to read these directly.

**Notable patients for testing (complex histories):**
- `Robert854_Botsford977_*.json` — check for complex medication history
- Any file can be loaded — use the fhir_explorer app to browse them visually first

### Secondary: Bulk NDJSON Dataset (10 patients)

**Path:** `data/synthea-samples/sample-bulk-fhir-datasets-10-patients/`  
**Format:** NDJSON (one resource per line), split by resource type  
**Use case:** Useful for corpus-level analysis or if you need to work with the bulk FHIR export format

### Real-World Examples

`data/real-world-examples/` — currently empty placeholder. If Blake adds real de-identified records, they'll appear here.

---

## The Existing Parser (Always Reuse This)

The `fhir_explorer/parser/` module is stable and well-tested. **Do not rewrite it.** Import from it.

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
| `Condition` | A diagnosis — code, display, onset, status (active/resolved) |
| `Medication` | A medication — display, RxNorm code, status, dates |
| `EncounterRecord` | A clinical visit — type, date, linked resources |
| `Observation` | A lab result or vital — LOINC code, value, unit |
| `Procedure` | A procedure — CPT/SNOMED code, date |
| `Immunization` | A vaccine — display, date |
| `AllergyRecord` | An allergy — substance, reaction, severity |

### PatientRecord key attributes

```python
record.patient          # PatientDemographics
record.conditions       # list[Condition]
record.medications      # list[Medication]
record.encounters       # list[EncounterRecord]
record.observations     # list[Observation]
record.procedures       # list[Procedure]
record.immunizations    # list[Immunization]
record.allergies        # list[AllergyRecord]
record.obs_index        # dict[id, Observation] — fast lookup
```

---

## What's Been Built (fhir_explorer)

The `fhir_explorer` is an **internal data exploration tool** — it's for understanding the data, not for the competition submission. Think of it as our data lab.

### Running it

```bash
cd ehi-ignite-challenge
pip install -r fhir_explorer/requirements.txt
streamlit run fhir_explorer/app.py
```

### Pages available

| Page | What It Does |
|---|---|
| Overview | Patient summary — demographics, conditions, complexity score |
| Timeline | Chronological encounter timeline with density chart and filters |
| Encounter Hub | Expandable encounter cards with linked medications, labs, procedures |
| Code Catalogs | All SNOMED, RxNorm, LOINC codes found in the record |
| Field Profiler | Which FHIR fields are populated vs. missing |
| Corpus Explorer | Multi-patient analysis across all 1,180 patients |
| Signal vs. Noise | LLM signal tiering — which resources belong in the LLM context window |

---

## What to Build Next (New Applications)

Two new standalone applications are planned. **Each goes in its own top-level directory.** Read the full spec before starting.

### 1. Patient Journey Application (`patient-journey/`)

**Spec:** `ideas/PATIENT-JOURNEY-APP.md`  
**Purpose:** Clinician-facing patient history visualization tool. A surgeon reviewing a patient before a case needs to rapidly answer: is this patient on blood thinners? anticoagulants? opioid history?  
**Key features:**
- Medication Gantt timeline (each drug as a horizontal bar over time)
- Pre-op surgical safety panel (auto-flagging drug classes: anticoagulants, JAK inhibitors, ACE inhibitors, opioids, immunosuppressants)
- Natural language search ("Has this patient been on opioids in the last 5 years?")
- Condition/episode tracker

**Build in:** `patient-journey/`  
**Reuse:** `fhir_explorer/parser/` for all data loading

---

### 2. Format-Agnostic Ingestion Service (`fhir-ingestion/`)

**Spec:** `ideas/FORMAT-AGNOSTIC-INGESTION.md`  
**Purpose:** Upstream ETL service that accepts patient records in any format (PDF, CDA/CCD, HL7 v2, free text, FHIR) and outputs a standardized FHIR R4 bundle. Sits upstream of the Patient Journey App.  
**Key features:**
- Format detection
- PDF text extraction + LLM-based entity extraction
- CDA/CCD XML parsing
- Entity normalization (RxNorm, ICD-10, LOINC codes)
- FHIR R4 bundle builder

**Build in:** `fhir-ingestion/`

---

## Coding Conventions

- **Python 3.11+**, fully typed with type hints
- **Streamlit** for UI (consistent with fhir_explorer)
- **Plotly** for charts
- **Imports:** always import from `fhir_explorer.parser` — don't copy/paste parser code
- **Style:** match the existing code style in `fhir_explorer/` — clean, typed, docstrings on public functions
- **Tests:** put in `tests/` subdirectory within each app folder
- **No hardcoded paths** — use `Path(__file__).parent` for relative paths

---

## Git Workflow

- Branch off `master` for features
- Naming: `feature/descriptive-name`
- Clear commit messages: `feat:`, `fix:`, `docs:`, `refactor:`
- Never commit directly to `master`

---

*Last updated: March 29, 2026*
