# EHI Export Data Overview

## The Two Export Formats

### 1. Individual Patient Bundle (Single-Patient Export)
**What it is:** A single JSON file — an `hl7.fhir.r4.Bundle` with type `"transaction"`. Each entry is a FHIR resource.  
**Triggered by:** Patient request, care team request. This is what patients download from MyChart/patient portal.  
**Size:** 65–2,640+ resources per patient depending on complexity.  
**Key distinction:** Includes `Claim` and `ExplanationOfBenefit` resources (billing history). This is the FULL designated record set.

```json
{
  "resourceType": "Bundle",
  "type": "transaction",
  "entry": [
    { "resource": { "resourceType": "Patient", ... } },
    { "resource": { "resourceType": "Condition", ... } },
    { "resource": { "resourceType": "Claim", ... } },
    { "resource": { "resourceType": "ExplanationOfBenefit", ... } },
    ...
  ]
}
```

### 2. Bulk NDJSON (Population Export)
**What it is:** One `.ndjson` file per resource type. Each line is one JSON resource.  
**Triggered by:** Health system admin or IT — for migrations, population health.  
**Size:** Per-file, can be millions of lines.

```
AllergyIntolerance.000.ndjson
Condition.000.ndjson
Encounter.000.ndjson
MedicationRequest.000.ndjson
Observation.000.ndjson
...
```

---

## Resource Type Reference

| Resource | What's In It | Codes Used | Clinical Significance |
|---|---|---|---|
| **Patient** | Demographics, address, contact, race/ethnicity | — | Identity anchor for everything else |
| **Condition** | Diagnoses, problem list entries | SNOMED CT, ICD-10 | The "what's wrong" list |
| **MedicationRequest** | Prescriptions ordered | RxNorm | Current + historical meds |
| **Observation** | Labs, vitals, social history (smoking, etc) | LOINC | Largest resource type by volume |
| **Encounter** | Every visit (inpatient, outpatient, ED, telehealth) | CPT/SNOMED | The "when/where" spine |
| **Procedure** | Surgeries, interventions | CPT, SNOMED | Clinical actions taken |
| **DiagnosticReport** | Radiology reads, pathology, lab panels | LOINC | Structured report output |
| **DocumentReference** | Clinical notes (often C-CDA XML inside) | LOINC | Free-text narrative |
| **AllergyIntolerance** | Drug/food/environmental allergies | SNOMED, RxNorm | Safety critical |
| **Immunization** | Vaccine history | CVX | Preventive care |
| **CarePlan** | Goals, planned activities | SNOMED | Care coordination |
| **Coverage** | Insurance, payer, member ID | — | Payer intelligence |
| **Claim** | Billed services, CPT codes, amounts | CPT, ICD-10 | Billing history — HUGE for agent use cases |
| **ExplanationOfBenefit** | Insurer's response to claim, payment | — | What was actually paid |
| **ImagingStudy** | Reference to DICOM imaging | — | Radiology studies |
| **Device** | Implantable devices | — | Pacemakers, stents, etc. |
| **CareTeam** | Provider relationships for this patient | — | Who's involved in care |

---

## Real Patient Profiles from Synthea Analysis

### Patient A: Healthy Young Adult (Simple)
**Name:** Mariette443 Hackett68  
**Resources:** 65 total  
**Conditions:** 0 chronic conditions  
**Meds:** None  
**Encounters:** 4 (routine checkups)  
**Profile:** This is a healthy 20-something. Labs, immunizations, no ongoing issues.  
**EHI challenge:** The data is *almost* usable as-is. Main value add = aggregation from multiple care settings.

### Patient B: Moderate Chronic (Middle Ground)
**Name:** Steven797 Fadel536  
**Resources:** 98 total  
**Conditions:** 5 (hypertension, obesity, allergies, viral sinusitis)  
**Meds:** 3 (Hydrochlorothiazide, Fexofenadine, Epi-pen)  
**Encounters:** 9  
**Insurance:** Blue Cross Blue Shield  
**Claims:** 12 claims, $27–$416 range, $0 EOB payments (Synthea limitation)  
**Profile:** A typical middle-aged patient with managed chronic conditions. Common in primary care.  
**EHI challenge:** Drug interaction checking, network verification (is my doctor in-network?), care gap identification.

### Patient C: Complex Multi-System (Maximum Complexity)
**Name:** Marine542 Ai120 Upton904  
**Resources:** 5,518+ (just 5 resource types)  
**Conditions:** 219 (Diabetes → Metabolic Syndrome → Hypertension → CKD → Dialysis → Kidney Transplant)  
**Meds:** 13 unique (tacrolimus = transplant immunosuppressant, insulin, metformin, metoprolol, lisinopril...)  
**Encounters:** 708 spanning 67 years  
**Profile:** This is your high-cost complex patient. Multiple chronic conditions cascading over decades.  
**EHI challenge:** This is where raw data is truly unusable. 219 conditions shown as a flat list is meaningless. The agent needs to understand the disease trajectory (prediabetes → T2DM → CKD → transplant).

---

## What Synthea Includes That Real EHRs Also Include

✅ Claim + ExplanationOfBenefit (billing history) — present in individual bundles  
✅ ImagingStudy references  
✅ CareTeam and CarePlan  
✅ Social determinants (employment status, housing, IPV in conditions list)  
✅ Multiple organization and practitioner relationships  

## What Real EHR Exports Have That Synthea Doesn't Fully Simulate

⚠️ Clinical notes (DocumentReference with full C-CDA XML narratives) — Synthea generates references but limited content  
⚠️ Prior authorization records  
⚠️ Real payer/network data  
⚠️ Lab reports with full interpretation text  
⚠️ DICOM imaging links  
