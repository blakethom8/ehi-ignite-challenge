# Polypharmacy — Synthea (Ester635 Echevarría842)

**Source:** existing Synthea corpus (`data/synthea-samples/synthea-r4-individual/fhir/`)
**Bundle:** `Ester635_Echevarría842_d36b57d2-052b-4b7a-9978-d4bac3f59c36.json` (16.5 MB)
**License:** Apache 2.0 (Synthea Synthetic Mass)

## Why this persona

Curated pick from the 1,180-bundle Synthea corpus, chosen to **contrast with `cardiac-coherent/Brady998`**:

| Axis | Brady998 (Coherent) | Ester635 (Synthea) |
|---|---|---|
| Sex / Age | Male / ~96 / deceased | Female / 99 / alive |
| Cardiac story | Cardiac arrest, post-stroke | Atrial fibrillation, anticoagulated |
| Cognitive | — | Alzheimer's on galantamine |
| Cancer | Prostate (Leuprolide + Docetaxel) | Colorectal (FOLFOX: Leucovorin + Oxaliplatin) |
| Multimodal | FHIR + DICOM + DNA | FHIR only |

Together they cover most of the "elderly multi-condition + chemo" surgical-clearance territory from both sexes and both cancer types.

## Patient at a glance

- Female, **alive**, age 99
- Selected from the corpus as the top non-deceased polypharmacy candidate (408 MedicationRequests, 17 distinct conditions, 654 encounters)

### Conditions

- **Cardiac:** Atrial Fibrillation
- **Neuro:** Alzheimer's disease
- **Renal:** Chronic kidney disease stage 1, Diabetic renal disease
- **Endocrine:** Diabetes, Diabetic retinopathy (NPDR), Hyperlipidemia, Hypertriglyceridemia, Metabolic syndrome X
- **GI / oncology:** Recurrent rectal polyp, Polyp of colon (treated with FOLFOX — Leucovorin + Oxaliplatin)
- **MSK:** Osteoarthritis of knee
- **Other:** Acute bronchitis, Chronic sinusitis, Anemia

### Notable medications (12 distinct)

- **Warfarin Sodium 5 MG** — anticoagulation for A-fib (bleeding-risk centerpiece)
- **Digoxin 0.125 MG** + **Verapamil 40 MG** — rate control
- **Galantamine 4 MG** — Alzheimer's cholinesterase inhibitor
- **Leucovorin 100 MG + Oxaliplatin 5 MG/ML** — FOLFOX chemo for colorectal
- **Epoetin Alfa (Epogen)** — for CKD-related anemia (the most-prescribed item, 378 fills)
- **Humulin 70/30 insulin** — diabetes
- **Simvastatin 10 MG** — lipid management

## What it shows off in a demo

- **Surgical clearance tension** — peri-operative warfarin management is the textbook example of why a surgeon needs "the right 5 facts in 30 seconds"
- **Dementia + consent capacity** — Alzheimer's on cholinesterase inhibitor opens the consent-capacity dimension
- **Multi-modal renal dosing** — CKD + diabetes + on Epogen + on metformin-class meds → drug-dosing landmines
- **Chemo cytopenia interaction** — FOLFOX bone-marrow suppression + anticoagulation = bleeding risk

## How this was picked

```python
# Ranked all 1,180 bundles in data/synthea-samples/synthea-r4-individual/fhir/
# by MedicationRequest count, then filtered for: alive, female, multi-system involvement.
# Top alive female candidate: Ester635 Echevarría842 (408 MedicationRequests, 17 conditions).
```

To pick a different Synthea persona later, the scan logic is short enough to inline — see the chat history when this file was created, or rerun any ranking over the corpus.

## Loading

```python
from lib.fhir_parser.bundle_parser import parse_bundle
record = parse_bundle(
    "data/demo-profiles/polypharmacy-synthea/fhir/"
    "Ester635_Echevarría842_d36b57d2-052b-4b7a-9978-d4bac3f59c36.json"
)
```

## Synthetic multi-source documents

`documents/` holds six LLM-generated documents simulating the disparate sources Ester635's chart would arrive from:

- 4 PDFs (hospital discharge summary, warfarin clinic letter, neurology dementia consult, colonoscopy + path)
- 1 C-CDA XML (stale outside-PCP CCDA, pre-warfarin)
- **1 FHIR R4 Bundle** (`home_monitoring_fhir_feed.json`) — 60 days of patient-collected Observations from a connected BP cuff + glucometer + scale

Three deliberate inconsistencies are baked in — outside ASA vs in-house warfarin (antithrombotic conflict), uncontrolled HTN signal in home data vs qualitative "hypertension" code in the chart, and glucose readings >250 mg/dL despite prescribed insulin (medication-effectiveness gap). See [sources.md](sources.md) for per-document detail.
