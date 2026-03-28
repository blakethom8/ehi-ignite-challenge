# FHIR Explorer — Internal Data Review Tool

## Purpose

This tool is **not part of the patient-facing app submission**. It is an internal developer instrument to deeply understand the EHI dataset before designing the real application.

The core questions we need to answer before writing the app:
- What fields are always present vs. sometimes present across patient bundles?
- Which resource types carry real clinical signal vs. administrative/billing noise?
- What does a patient's chronological story actually look like when assembled?
- What information is safe to pass to an LLM — and what would cause context overload?
- Which patients in the dataset make good test cases for different complexity scenarios?

Only after this exploration can we make confident decisions about data parsing strategy, LLM context design, and UI information architecture for the patient-facing product.

---

## What We Know About the Data

**Source**: Synthea FHIR R4 synthetic patient bundles
**Location**: `data/synthea-samples/synthea-r4-individual/fhir/`
**Scale**: 1,180 patient files, 56KB (26 resources) to 40MB (18,488 resources)

**Format**: Each file is a FHIR `Bundle` (type: `transaction`) — one file per patient, all resource types mixed together, linked by UUID cross-references.

**Resource types present** (16–19 per bundle):

| Resource Type | Approx. % of Bundle | Clinical Value |
|---|---|---|
| Observation | ~58% | High — labs, vitals, measurements |
| Encounter | ~6% | High — the temporal anchor for all events |
| Condition | <1% | High — sparse but critical |
| MedicationRequest | ~7% | High |
| Procedure | ~7% | High |
| DiagnosticReport | ~2.5% | High — groups related observations |
| Immunization | <1% | High |
| AllergyIntolerance | <1% | High |
| CarePlan / CareTeam / Goal | <1% | Medium |
| ImagingStudy | <0.1% | Medium |
| Claim | ~11% | Low — billing noise |
| ExplanationOfBenefit | ~10% | Low — billing noise |
| Organization / Practitioner / Location | <1% | Low — reference data |

**Coding systems**:
- `LOINC` — labs and vital signs (Observation, DiagnosticReport)
- `SNOMED CT` — conditions and procedures (Condition, Procedure, Encounter)
- `RxNorm` — medications (MedicationRequest)
- `CVX` — vaccines (Immunization)
- `CPT` — billing codes (Claim, ExplanationOfBenefit)

**Key structural facts**:
- Patient is the central hub; Encounter is the clinical sub-hub
- Every Observation, Procedure, DiagnosticReport, etc. references both Patient and Encounter
- UUID references use `urn:uuid:` prefix — must be stripped when resolving
- EOB's insurer is in a `contained` Coverage resource (not a top-level bundle resource)
- Synthea does NOT generate free-text clinical notes (`presentedForm` absent) — real EHR exports will have these
- One Claim + one EOB generated per Encounter (1:1:1 relationship)

**Three representative test patients identified**:
- `Letha284_Haag279` — small (56KB, 26 resources) — for UI and basic parsing tests
- `Abby752_Kuvalis369` — medium (472KB, 183 resources) — for timeline and relationship testing
- `Floyd420_Jerde200` — large (40MB, 18,488 resources) — for performance and complexity testing

---

## Architecture

### Stack
- **Python** — parsing and statistics
- **Streamlit** — quick internal UI, no frontend build required
- **Pandas + Plotly** — tables and charts
- **stdlib only for parsing** — `json`, `dataclasses`, `datetime`, `collections` (no `fhir.resources`, no `pydantic`)

### Module Structure

```
src/tools/fhir_explorer/
│
├── app.py                       # Streamlit entry point: streamlit run app.py
├── requirements.txt
│
├── parser/                      # Core parsing layer
│   ├── models.py                # All dataclasses (PatientRecord, ObservationRecord, etc.)
│   ├── extractors.py            # One extraction function per resource type
│   └── bundle_parser.py         # parse_bundle(path) -> PatientRecord
│
├── catalog/                     # Statistics and analysis layer
│   ├── single_patient.py        # compute_patient_stats(record) -> PatientStats
│   ├── corpus.py                # Lazy corpus index over all 1,180 patients, with cache
│   └── field_profiler.py        # Recursive field presence analysis
│
└── views/                       # Streamlit page modules
    ├── overview.py              # Page 1: Patient summary + resource counts
    ├── timeline.py              # Page 2: Chronological event stream
    ├── encounter_hub.py         # Page 3: Encounter drill-down
    ├── catalog_view.py          # Page 4: LOINC / SNOMED / RxNorm catalogs
    ├── field_profiler_view.py   # Page 5: Field presence heatmap
    ├── corpus_view.py           # Page 6: Browse all 1,180 patients
    └── signal_filter.py         # Page 7: LLM signal vs. noise classifier
```

---

## Data Models (`parser/models.py`)

All models are stdlib `@dataclass`. No external validation libraries.

**`PatientRecord`** — top-level container returned by the parser:
```
PatientRecord
├── summary: PatientSummary          # demographics, race/ethnicity, DALY/QALY
├── encounters: list[EncounterRecord]
├── observations: list[ObservationRecord]
├── conditions: list[ConditionRecord]
├── medications: list[MedicationRecord]
├── procedures: list[ProcedureRecord]
├── diagnostic_reports: list[DiagnosticReportRecord]
├── immunizations: list[ImmunizationRecord]
├── allergies: list[AllergyRecord]
├── claims: list[ClaimRecord]
├── care_plans_raw: list[dict]       # kept as raw dict (lower priority)
├── care_teams_raw: list[dict]
├── goals_raw: list[dict]
├── encounter_index: dict[id, EncounterRecord]   # for O(1) reference lookup
├── obs_by_encounter: dict[id, list[obs_id]]     # encounter → observations
├── obs_by_loinc: dict[code, list[obs_id]]       # loinc → observations
└── parse_warnings: list[str]        # skipped/malformed resources
```

**Key derived fields**:
- `ConditionRecord.is_active` = `clinicalStatus == "active" AND abatementDateTime is None`
- `ObservationRecord.value_type` = one of `"quantity"`, `"codeable_concept"`, `"component"`, `"none"`
  - `component` handles multi-value observations (e.g., blood pressure: systolic + diastolic)
- `ClaimRecord.total_paid` = matched from corresponding EOB

---

## Parser Design (`parser/bundle_parser.py`)

**Entry point**: `parse_bundle(file_path: str | Path) -> PatientRecord`

**Steps**:
1. `json.load()` the file — stdlib, confirmed fast enough at 40MB (~0.16s)
2. Single-pass partition of `bundle['entry']` by `resourceType`
3. Extract `PatientSummary` — walk extensions by URL (not by position, which is fragile)
4. Call per-type extractors from `extractors.py`
5. **Post-process references**: loop all resources with an `encounter.reference` field, call `strip_ref()` to normalize `urn:uuid:` prefix, populate `EncounterRecord.linked_*` lists
6. Build `obs_by_loinc` index
7. Match Claims ↔ EOBs (share same UUID in Synthea); extract insurer from EOB's `contained` Coverage

**`strip_ref(ref: str) -> str`**: utility that strips `urn:uuid:` prefix. Used everywhere a UUID reference is resolved. Centralizing this prevents bugs.

---

## Catalog Layer

### `catalog/single_patient.py`

`compute_patient_stats(record: PatientRecord) -> PatientStats`

Outputs:
- Resource type counts, clinical vs. billing split (billing% = (Claim+EOB)/total)
- Condition catalog: active count, resolved count, list sorted by onset
- Medication catalog: active count, total count
- LOINC catalog: each unique lab/vital with count, first/last date, value range
- Encounter breakdown by class (AMB/IMP/EMER) and type
- **Complexity score** (0–100):

```
score = min(condition_count, 30) * 2.0
      + min(med_count, 20) * 1.5
      + min(years_of_history / 5, 20) * 1.0
      + min(encounter_count / 10, 20) * 0.5

tier: simple (<20) / moderate (<40) / complex (<70) / highly_complex (≥70)
```

### `catalog/corpus.py`

Lazy index over all 1,180 patient files. On first run, parses every file and writes a compact index (one row per patient — NOT full PatientRecord) to `.corpus_cache.json`. Subsequent loads read the cache instantly. Cache invalidated by comparing file modification times to `cache_generated_at`.

### `catalog/field_profiler.py`

Recursive dict flattener that produces dot-notation field paths with presence percentages (e.g., `code.coding[*].system` = 100%, `abatementDateTime` = 50% for Conditions). Tells us what we can rely on vs. what we need to guard against.

---

## Streamlit UI — 7 Pages

**Sidebar**: patient file dropdown (all 1,180, with complexity tier badge), page navigation radio. Active patient parsed once and cached in `st.session_state` via `@st.cache_data`.

### Page 1 — Patient Overview
Demographics strip, 4 metric cards (total resources / clinical / billing / complexity score), resource distribution bar chart (colored by tier), active conditions list, current medications list, parse warnings.

### Page 2 — Timeline
Date range slider, resource type checkboxes, encounter cards grouped by year (expandable to show linked resources inline), density bar chart (encounters per year across full history).

### Page 3 — Encounter Hub
Left panel: encounter list. Right panel: full detail for selected encounter — vitals, labs, conditions diagnosed, procedures, medications ordered, immunizations, imaging, plus billing toggle (Claim + EOB for that visit).

### Page 4 — Code Catalogs
Tabbed by coding system:
- **LOINC**: table with value ranges + sparkline trend button per lab type
- **SNOMED**: conditions (with status badge + onset/abatement) and procedures
- **RxNorm**: medications with status and date range
- **CVX**: immunizations with dates

### Page 5 — Field Profiler
Resource type selector → presence heatmap colored by tier (green=100%, yellow=80–99%, orange=20–79%, red=<20%). Toggle for nested path detail. CSV export.

### Page 6 — Corpus Explorer
Filter all 1,180 patients by: complexity tier, min/max conditions, years of history, presence of allergies, insurer, condition name search. Results table with click-to-load. **Scenario Finder** buttons: "Find simplest patient", "Find most complex", "Find patient with active chronic conditions", etc.

### Page 7 — Signal vs. Noise *(most important for app design)*

4-tier LLM inclusion model:

| Tier | Resources | Default |
|---|---|---|
| 1 — Always Include | Patient, active Conditions, active Medications, AllergyIntolerance | ✅ |
| 2 — Include Summarized | Recent Observations (last 2 yrs), recent Encounters (last 5), Immunizations | ✅ |
| 3 — Include on Request | All Observations, CarePlan, Goals, CareTeam | ⬜ |
| 4 — Exclude Default | Claim, EOB, Organization, Practitioner | ❌ |

Token budget slider → live estimate of resource count and tokens per tier for the active patient. "Generate LLM Context Preview" button → produces the plain-text context block as it would be sent to the model.

This page directly answers: *what do we actually send the LLM, and how do we avoid context overload while never missing a critical historical event?*

---

## Implementation Sequence

| Phase | Deliverable | Validates |
|---|---|---|
| 1 — Parser | `models.py`, `extractors.py`, `bundle_parser.py` | `python bundle_parser.py <file>` prints summary |
| 2 — Stats | `single_patient.py`, `field_profiler.py` | Complexity scores for 3 test patients |
| 3 — UI (single patient) | `app.py` + pages 1–4 | Load all 3 test patients in browser |
| 4 — Corpus + advanced | `corpus.py` + pages 5–7 | 1,180 patients indexed, LLM context preview works |
| 5 — Polish | `requirements.txt`, tune complexity formula | End-to-end run on all test patients |

---

## What This Tool Will Tell Us

After completing this tool we will have definitive answers to:

1. **Context strategy**: Exactly which fields and resource types to include in LLM prompts, and at what token budget
2. **Time-bounding logic**: Whether to filter observations by recency, and what "recent" means for different data types
3. **Human-guided experience**: What patient-specific questions are worth asking upfront to focus the LLM on the most relevant data
4. **Test coverage**: Which specific patients to use for testing simple, moderate, complex, and edge-case scenarios
5. **Real-world gaps**: What Synthea is missing vs. what real Epic/Cerner exports will contain (e.g., free-text clinical notes)
