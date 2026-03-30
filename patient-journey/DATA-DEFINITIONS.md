# Patient Journey App — Data Definitions & Application Architecture

*Last updated: March 29, 2026*

This document defines the data models, classification systems, and UX approach used in the Patient Journey application. It serves as both a technical reference and a guide for understanding how raw FHIR data is transformed into clinical insights.

---

## 1. Source Data: FHIR R4 Resources

All patient data originates from FHIR R4 JSON bundles. Each bundle is a single patient's complete clinical record. The existing `fhir_explorer/parser/` layer parses these into typed Python dataclasses. The Patient Journey app builds on top of these parsed structures — it never touches raw FHIR JSON directly.

### 1.1 PatientRecord (top-level container)

The root object for a single patient. Produced by `bundle_parser.parse_bundle()`. Contains all clinical data organized by resource type.

| Attribute | Type | Description |
|---|---|---|
| `summary` | `PatientSummary` | Demographics — name, DOB, age, gender, address, identifiers |
| `encounters` | `list[EncounterRecord]` | All clinical visits (ambulatory, inpatient, emergency) |
| `medications` | `list[MedicationRecord]` | All medication prescriptions (active + historical) |
| `conditions` | `list[ConditionRecord]` | All diagnoses (active, resolved, inactive) |
| `observations` | `list[ObservationRecord]` | Labs, vitals, social history, survey results |
| `procedures` | `list[ProcedureRecord]` | Surgeries, interventions, clinical procedures |
| `immunizations` | `list[ImmunizationRecord]` | Vaccine history |
| `allergies` | `list[AllergyRecord]` | Drug, food, and environmental allergies |
| `claims` | `list[ClaimRecord]` | Insurance claims and billing |
| `diagnostic_reports` | `list[DiagnosticReportRecord]` | Radiology, pathology, lab panels |
| `imaging_studies` | `list[ImagingStudyRecord]` | CT, MRI, X-ray studies |

Index structures for fast lookup:
- `encounter_index`: `dict[encounter_id, EncounterRecord]`
- `obs_index`: `dict[obs_id, ObservationRecord]`
- `obs_by_encounter`: `dict[encounter_id, list[obs_id]]`
- `obs_by_loinc`: `dict[loinc_code, list[obs_id]]`

---

## 2. Core Clinical Data Models

### 2.1 EncounterRecord — A Clinical Visit

An encounter is a single interaction between the patient and the healthcare system. This is the fundamental unit of "when did the patient see a doctor."

| Field | Description |
|---|---|
| `encounter_id` | Unique identifier (UUID) |
| `class_code` | Visit classification (see below) |
| `encounter_type` | Human-readable type (e.g., "General examination") |
| `reason_display` | Why the visit happened |
| `period.start` / `period.end` | When the visit occurred and its duration |
| `practitioner_name` | Treating physician |
| `provider_org` | Facility or organization |
| `linked_*` | Lists of UUIDs linking observations, conditions, procedures, medications, etc. ordered during this encounter |

**Encounter class codes** (how we categorize visit types):

| Code | Label | Description | Timeline Marker |
|---|---|---|---|
| `AMB` | Ambulatory | Routine outpatient visit, clinic appointment | Blue circle |
| `IMP` | Inpatient | Hospital admission, overnight stay | Orange square |
| `EMER` | Emergency | Emergency department visit | Red diamond |
| `VR` | Virtual | Telehealth visit | — |
| `WELLNESS` | Wellness | Preventive care, annual physical | — |

### 2.2 MedicationRecord — A Prescription

Each MedicationRecord represents a single prescription event — one instance of a drug being ordered at a specific encounter. A patient on a chronic medication will have **multiple MedicationRecords** for the same drug (one per encounter where it was prescribed or refilled).

| Field | Description |
|---|---|
| `med_id` | Unique identifier |
| `display` | Human-readable drug name (e.g., "Lisinopril 10 MG Oral Tablet") |
| `rxnorm_code` | RxNorm code for the drug substance |
| `status` | Prescription status (see below) |
| `authored_on` | When the prescription was written |
| `requester` | Prescribing physician |
| `dosage_text` | Dosage instructions |
| `reason_display` | Clinical reason for prescribing |
| `encounter_id` | Which visit this was prescribed during |

**Medication status values:**

| Status | Meaning |
|---|---|
| `active` | Currently prescribed and presumably being taken |
| `stopped` | Explicitly discontinued |
| `completed` | Course finished (e.g., antibiotics) |
| `cancelled` | Prescription was cancelled before being filled |
| `on-hold` | Temporarily paused |

### 2.3 ConditionRecord — A Diagnosis

A condition is a clinical problem or diagnosis on the patient's problem list.

| Field | Description |
|---|---|
| `condition_id` | Unique identifier |
| `code.system` | Coding system (typically SNOMED CT) |
| `code.code` | SNOMED code |
| `code.display` | Human-readable diagnosis name |
| `clinical_status` | Current state (see below) |
| `verification_status` | Confidence level (confirmed, unconfirmed, refuted) |
| `onset_dt` | When the condition was first diagnosed |
| `abatement_dt` | When the condition resolved (null = still present) |
| `is_active` | Derived: `clinical_status == "active"` AND no `abatement_dt` |

**Condition clinical status values:**

| Status | Meaning |
|---|---|
| `active` | Currently an active problem |
| `resolved` | No longer present, has an abatement date |
| `inactive` | Not currently active but not formally resolved |
| `remission` | In remission (e.g., cancer) |
| `recurrence` | Previously resolved, now recurred |

### 2.4 ProcedureRecord — A Clinical Procedure

| Field | Description |
|---|---|
| `code.system` | Coding system (SNOMED CT or CPT) |
| `code.display` | Human-readable procedure name |
| `performed_period` | When the procedure was performed (start/end) |
| `reason_display` | Clinical indication |
| `encounter_id` | Which visit this occurred during |

### 2.5 ObservationRecord — A Lab Result or Vital Sign

| Field | Description |
|---|---|
| `loinc_code` | LOINC code identifying the test |
| `display` | Human-readable name (e.g., "Hemoglobin A1c") |
| `category` | `vital-signs`, `laboratory`, `social-history`, `survey` |
| `value_type` | `quantity` (numeric), `codeable_concept` (coded), `component` (multi-part like BP) |
| `value_quantity` / `value_unit` | Numeric result and unit |
| `effective_dt` | When the observation was taken |

---

## 3. Derived Data Models (Patient Journey App)

These are the models we build on top of the raw FHIR data to power the visualization layer.

### 3.1 MedicationEpisode — A Continuous Treatment Period

**Problem:** FHIR gives us individual prescription events (MedicationRecords), not treatment periods. A patient on Lisinopril for 5 years might have 20+ MedicationRecords — one per refill encounter.

**Solution:** The `episode_detector` groups all MedicationRecords for the same drug into a single `MedicationEpisode` representing the full duration of treatment.

| Field | Derived From | Description |
|---|---|---|
| `display` | First MedicationRecord | Drug name |
| `rxnorm_code` | First MedicationRecord | RxNorm identifier |
| `status` | Latest MedicationRecord | Most recent prescription status |
| `requests` | All matching MedicationRecords | Every individual prescription for this drug |
| `start_date` | Earliest `authored_on` | When this drug was first prescribed |
| `end_date` | Latest `authored_on` (if stopped) | When last prescribed; null = still active |
| `is_active` | Latest status in (`active`, `on-hold`) | Whether the patient is currently on this drug |
| `dosage_text` | Latest non-empty dosage | Current dosing instructions |
| `reason` | First non-empty reason | Why this drug was prescribed |
| `duration_days` | `end_date - start_date` | How long the patient was on this drug |

**Grouping logic:** MedicationRecords are grouped by **normalized display name** (lowercase, stripped). All records for the same drug name are assumed to be part of the same treatment episode. This works well for Synthea data where display names are consistent. Real-world EHR data may require fuzzy matching or RxNorm-based grouping.

**Active determination:** An episode is considered active if the most recent MedicationRecord has status `active` or `on-hold`. If status is `stopped`, `completed`, or `cancelled`, the episode is historical and the end date is set to the last `authored_on` date.

### 3.2 ConditionEpisode — A Diagnosis with Context

Links a condition to the encounter where it was diagnosed and any medications ordered in that same encounter.

| Field | Derived From | Description |
|---|---|---|
| `condition` | ConditionRecord | The diagnosis itself |
| `related_encounters` | Lookup via `encounter_id` | The visit where this was diagnosed |
| `related_medications` | Medications sharing the same `encounter_id` | Drugs prescribed at the same visit |

**Linking logic:** Uses the `encounter_id` field on both conditions and medications to find co-occurring events. This enables the "what was prescribed when this was diagnosed" view.

**Sort order:** Active conditions first, then by onset date descending (most recent first).

---

## 4. Drug Classification System

### 4.1 Overview

The `DrugClassifier` maps medications to **12 surgical-risk drug classes** using two matching strategies:
1. **Keyword matching** — checks if any keyword appears in the medication display name (case-insensitive substring match)
2. **RxNorm code matching** — checks if the medication's RxNorm code matches a known code in the class

A single medication can match multiple classes (e.g., a combination drug).

### 4.2 Drug Classes

Each class has a **severity level** that determines its visual priority in the safety panel:

#### Critical Severity (must address before surgery)

| Class Key | Label | Surgical Concern | Example Drugs |
|---|---|---|---|
| `anticoagulants` | Anticoagulants / Blood Thinners | Bleeding risk — must hold pre-op. Check INR/PT for warfarin | Warfarin, Heparin, Eliquis, Xarelto, Pradaxa |
| `antiplatelets` | Antiplatelet Agents | Increased bleeding risk. Hold 5-7 days pre-op | Clopidogrel/Plavix, Aspirin, Brilinta |
| `jak_inhibitors` | JAK Inhibitors | Immunosuppressive — infection risk. Hold 1+ week pre-op | Tofacitinib/Xeljanz, Baricitinib/Olumiant |
| `immunosuppressants` | Immunosuppressants | Infection + wound healing risk. Do NOT stop without transplant team | Tacrolimus, Cyclosporine, Methotrexate, Prednisone |

#### Warning Severity (review and potentially adjust)

| Class Key | Label | Surgical Concern | Example Drugs |
|---|---|---|---|
| `ace_inhibitors` | ACE Inhibitors | Hypotension under anesthesia. Often held morning of surgery | Lisinopril, Enalapril, Ramipril |
| `arbs` | ARBs | Same hemodynamic concerns as ACE inhibitors | Losartan, Valsartan, Irbesartan |
| `nsaids` | NSAIDs | Bleeding risk + renal concerns. Hold 3-5 days pre-op | Ibuprofen, Naproxen, Ketorolac |
| `opioids` | Opioid History | Tolerance affects post-op pain management. Review for OUD | Oxycodone, Hydrocodone, Fentanyl, Tramadol |
| `anticonvulsants` | Anticonvulsants | Enzyme inducers affect anesthetic metabolism. Check levels | Phenytoin, Valproate, Carbamazepine, Gabapentin |

#### Info Severity (be aware)

| Class Key | Label | Surgical Concern | Example Drugs |
|---|---|---|---|
| `psych_medications` | Psychiatric Medications | MAOIs need 2-week washout. SSRIs may increase bleeding | Sertraline, Fluoxetine, Lithium, Quetiapine |
| `stimulants` | Stimulants | Arrhythmia risk under anesthesia. Hold day of surgery | Adderall, Ritalin, Vyvanse |
| `diabetes_medications` | Diabetes Medications | Hold metformin 48h pre-op. Adjust insulin dosing | Metformin, Insulin, Glipizide, Semaglutide |

### 4.3 Safety Flag States

Each drug class produces a **SafetyFlag** with one of three states:

| Status | Meaning | Visual |
|---|---|---|
| `ACTIVE` | Patient is currently on a medication in this class | Red indicator |
| `HISTORICAL` | Patient was previously on a medication in this class (now stopped) | Yellow indicator |
| `NONE` | No medications found in this class | Green checkmark |

Flags are sorted: critical severity first, then active before historical before none.

### 4.4 Classification Data Source

All keyword and RxNorm mappings are stored in `data/drug_classes.json`. This file is the single source of truth for drug classification. To add a new drug class or update keywords, edit this file — no code changes required.

---

## 5. Application Views & UX Approach

The app is designed for a **5-minute pre-case review**. A surgeon or anesthesiologist selecting a patient should be able to answer critical safety questions within seconds, then drill deeper as needed.

### 5.1 Journey Timeline (default view)

**Purpose:** Visual overview of the patient's entire medication and clinical history on a single screen.

**Visualization:** Plotly `px.timeline` (Gantt-style horizontal bars)
- Each medication episode is a horizontal bar spanning its start-to-end dates
- Bars are colored by medication status (Active vs. stopped/completed)
- Clinical events are overlaid as markers on the timeline

**Overlay markers:**

| Event Type | Marker | Color | Source |
|---|---|---|---|
| Emergency visits | Diamond | Red | `EncounterRecord` where `class_code == "EMER"` |
| Inpatient stays | Square | Orange | `EncounterRecord` where `class_code == "IMP"` |
| Ambulatory visits | Circle | Blue | `EncounterRecord` where `class_code == "AMB"` |
| Procedures | Cross | Dark gray | `ProcedureRecord` via `performed_period.start` |
| Diagnoses | Star | Purple | `ConditionRecord` via `onset_dt` |

**Controls:**
- Year range slider — zoom into a specific time window
- Overlay toggle — show/hide encounters, procedures, diagnoses
- Active-only checkbox — filter to only currently active medications

**Summary table** below the chart lists all medication episodes with drug class tags, dates, dosage, and reason.

### 5.2 Pre-Op Safety Panel

**Purpose:** Answer "is this patient on anything dangerous before surgery?" in under 10 seconds.

**Layout:** Checklist-style, one row per drug class. Sorted by severity (critical first), then by status (active flags surface to top).

**For each drug class:**
- Severity icon (warning, caution, info)
- Drug class label
- Status badge (ACTIVE / HISTORICAL / NONE)
- If not NONE: surgical note explaining the clinical concern
- Each matched medication listed with: name, active/stopped badge, prescribe date, dosage, reason

**Summary metrics** at top: total medications, active flags count, historical flags count, clear count.

**Toggle:** "Show clear categories" to see all 12 classes including those with no matches.

### 5.3 Medication History (deep dive)

**Purpose:** Full medication review for a clinician who needs to understand the complete prescribing history.

**Layout:** Expandable card per unique medication (grouped into episodes). Active medications are expanded by default.

**Each card shows:**
- Drug name, date range, active/stopped status
- Dosage, prescribing reason, RxNorm code
- Drug class tags (from classifier)
- Duration metric (days/months/years)
- Prescription count (how many times refilled)
- If multiple prescriptions: a table of individual prescription records with date, status, dosage, and prescriber

**Filters:**
- Status filter: All / Active only / Historical only
- Drug class filter: dropdown of all 12 drug classes

### 5.4 Conditions (episode tracker)

**Purpose:** Understand the patient's diagnostic history — what conditions they have, when they started, and what was prescribed for them.

**Visualization:** Plotly `px.timeline` showing each condition as a horizontal bar from onset to resolution (or present if still active).

**Color coding:**
- Active conditions: Red
- Resolved: Gray
- Inactive: Light gray
- Remission: Green

**Condition cards** below the timeline, each showing:
- Clinical status, verification status
- Onset and resolution dates
- Duration (active for / total duration)
- Code system and SNOMED code
- Related encounters (the visit where diagnosed)
- Related medications (drugs prescribed at the same visit)

**Filter:** By clinical status (All / Active / Resolved / Inactive)

---

## 6. Data Flow Summary

```
FHIR R4 JSON Bundle
        |
        v
  fhir_explorer/parser/bundle_parser.py
        |
        v
  PatientRecord (typed dataclasses)
        |
        +---> episode_detector.py
        |         |
        |         +--> MedicationEpisode (grouped by drug name)
        |         +--> ConditionEpisode (linked to encounters + meds)
        |
        +---> drug_classifier.py
        |         |
        |         +--> ClassifiedMedication (matched to drug classes)
        |         +--> SafetyFlag (per-class surgical risk status)
        |
        v
  Streamlit Views
        |
        +--> Journey Timeline (Gantt bars + event markers)
        +--> Safety Panel (checklist of surgical risk flags)
        +--> Medication History (expandable drug cards)
        +--> Conditions (diagnosis timeline + episode cards)
```

---

## 7. Coding Systems Referenced

| System | Used For | Example |
|---|---|---|
| **SNOMED CT** | Conditions, procedures | `44054006` = Type 2 Diabetes |
| **RxNorm** | Medications | `6809` = Metformin |
| **LOINC** | Observations (labs, vitals) | `4548-4` = Hemoglobin A1c |
| **CPT** | Procedures (alternative to SNOMED) | `99213` = Office visit |
| **CVX** | Immunizations | `140` = Influenza vaccine |
| **ICD-10** | Conditions (alternative to SNOMED) | `E11` = Type 2 Diabetes |

---

## 8. Known Limitations & Future Work

**Current limitations:**
- **Medication episode grouping** is by exact display name match. Combination drugs or name variations may create duplicate episodes. Future: group by RxNorm ingredient code.
- **Condition-medication linking** only works when both share the same `encounter_id`. Chronic medications refilled at routine visits won't link to the original diagnosis encounter. Future: use `reason_display` or `reasonCode` to link medications to conditions directly.
- **No drug interaction checking.** The classifier flags drug classes but doesn't check for pairwise interactions between active medications. Planned: integrate OpenFDA Drug Interaction API.
- **No natural language search** yet. Planned: LLM-backed Q&A over the patient's structured data (e.g., "Has this patient been on blood thinners in the last 5 years?").
- **Encounter overlays on the timeline** are pinned to the top medication row rather than spanning the full chart height. This is a Plotly limitation with mixed bar+scatter charts.

**Planned features (from spec):**
- Natural language search view (`views/nl_search.py`)
- Drug interaction checker (`core/interaction_checker.py`)
- Recurrence detection for conditions (e.g., "4 DVT episodes since 2015")
- Dose-change detection within medication episodes
- Treatment cycle detection (e.g., "3 cycles of methotrexate over 10 years")
