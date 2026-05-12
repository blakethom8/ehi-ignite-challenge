# Oncology — Breast Cancer (mCODE Jenny M)

**Source:** [HL7 mCODE Implementation Guide v4.0.0](https://hl7.org/fhir/us/mcode/)
**Bundle:** `Bundle-mcode-patient-bundle-jenny-m.json` (132 KB, 40 entries)
**Patient:** Jenny M, 55F
**License:** CC0

## Why this persona

Adds a structured oncology profile to the gallery. Where Synthea gives you a `Condition` like "Malignant neoplasm of breast" and not much else, mCODE ships the full oncology data model — staging, biomarkers, tumor morphology, performance status, family history, specimen tracking, treatment plans — exactly the kind of structure a surgical-oncology demo needs.

## The story (per the mCODE IG)

Routine screening mammography (Feb 2018) flagged a possible mass → core-needle biopsy → breast cancer diagnosed → staged → treatment regimen begun. Includes a `FamilyMemberHistory` flagging maternal-side cancer history.

## What's in the bundle

| Resource | Count | Notable |
|---|---|---|
| Observation | 22 | Staging, biomarkers (ER/PR/HER2), tumor morphology, performance status |
| MedicationRequest | 4 | Chemo / endocrine therapy regimen |
| Procedure | 4 | Biopsy, surgical, etc. |
| DiagnosticReport | 2 | Pathology |
| FamilyMemberHistory | 2 | Family cancer history |
| Patient | 1 | Jenny M |
| Condition | 1 | Primary cancer condition (mCODE profile) |
| Specimen | 1 | Biopsy specimen |
| Practitioner | 2 | Care team |
| Organization | 1 | Facility |

## What it shows off in a demo

- **mCODE profiles** the platform can render meaningfully (PrimaryCancerCondition, CancerStage, TumorMarkerTest, ECOG status)
- **Structured staging** rather than free-text — drives a clean staging widget
- **Family history** linked to the patient — opens "hereditary risk" cards
- **Specimen + DiagnosticReport** linkage — supports a pathology-trace view

## Loading

```python
from lib.fhir_parser.bundle_parser import parse_bundle
record = parse_bundle("data/demo-profiles/oncology-breast-mcode/fhir/Bundle-mcode-patient-bundle-jenny-m.json")
```

If `bundle_parser` doesn't yet handle mCODE-specific extensions (Condition.extension for histologyMorphologyBehavior, etc.) those degrade to passthrough — the core resources still load.

## Synthetic multi-source documents

`documents/` holds six LLM-generated documents that walk this persona through the breast-cancer workup as if assembled from the real-world sources a patient encounters:

- 4 PDFs (screening mammogram, biopsy pathology, tumor board summary, genetic counseling letter)
- 1 C-CDA XML (prior outside gynecologist)
- **1 FHIR R4 Bundle** (`patient_app_symptom_tracker_fhir.json`) — 8 weeks of patient-generated Observations from a chemo symptom-tracker app

Three deliberate inconsistencies are baked in to drive the platform's reconciliation features — including a *temporal* one (the symptom tracker implies active chemo not in the in-house chart) and a *patient-identity* one (different identifier system + name spelling for fuzzy-matching tests). See [sources.md](sources.md) for the per-document breakdown.

## Re-fetching

```
curl -L https://hl7.org/fhir/us/mcode/Bundle-mcode-patient-bundle-jenny-m.json \
  -o data/demo-profiles/oncology-breast-mcode/fhir/Bundle-mcode-patient-bundle-jenny-m.json
```
