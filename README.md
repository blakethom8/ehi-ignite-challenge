# EHI Ignite Challenge

**HHS $490K Competition** — Build tools that transform single-patient FHIR EHI exports into usable, actionable experiences.

**Phase 1 Deadline:** May 13, 2026  
**Competition Site:** https://ehignitechallenge.org/

## What This Is

The federal government now mandates that every certified EHR (Epic, Cerner, etc.) must export a patient's complete health record on demand. The format is FHIR R4 NDJSON. The problem: "computable ≠ usable." These exports are technically correct but practically overwhelming. HHS is paying $490K for teams that solve this.

## Project Structure

```
ehi-ignite-challenge/
├── README.md                     ← you are here
├── data/
│   ├── synthea-samples/          ← downloaded synthetic FHIR datasets
│   │   ├── sample-bulk-fhir-datasets-10-patients/  ← bulk NDJSON format
│   │   └── synthea-r4-individual/fhir/             ← per-patient FHIR bundles
│   └── real-world-examples/      ← real EHR export docs / format specs
├── docs/
│   ├── DATA-OVERVIEW.md          ← what the data looks like, resource counts
│   └── FHIR-PRIMER.md            ← quick reference for FHIR R4 concepts
├── ideas/
│   └── FEATURE-IDEAS.md          ← use cases, agent concepts, product strategy
├── architecture/                 ← system design docs
└── src/                          ← code experiments
```

## Key Data Facts (from 10-patient Synthea analysis)

| Resource Type | Count (10 patients) | Notes |
|---|---|---|
| Observation | 9,878 | Labs, vitals, social history |
| DiagnosticReport | 2,101 | Radiology, pathology, lab panels |
| DocumentReference | 1,215 | Clinical notes (often C-CDA XML inside) |
| Procedure | 2,056 | Surgeries, interventions |
| MedicationRequest | 1,745 | Prescriptions |
| Encounter | 1,215 | All visits |
| Condition | 555 | Diagnoses, problem list |
| Immunization | 161 | Vaccine history |
| AllergyIntolerance | 11 | Drug/food/environmental |

**Avg per patient: ~1,545 resources** (ranging from 65 for a healthy young patient to 2,640 for a complex chronic patient)

## Patient Complexity Spectrum

**Simple Patient** (Mariette443, 65 resources): No chronic conditions, no meds. Just routine labs, immunizations, 4 encounters. Basically a healthy 20-something.

**Moderate Patient** (Steven797, 98 resources): 5 conditions (hypertension, obesity, allergies), 3 meds, 12 claims. Blue Cross Blue Shield. Manageable.

**Complex Patient** (Marine542, 5,518+ resources): 219 conditions. Diabetes → CKD → dialysis → kidney transplant. 13 unique medications including tacrolimus (immunosuppressant), insulin, metformin. 708 encounters spanning 67 years of life. This is your chronic multi-system patient.

## Sample Data Links

- [SMART on FHIR bulk datasets (Synthea)](https://github.com/smart-on-fhir/sample-bulk-fhir-datasets) — 10/100/1000 patients
- [Synthea patient generator](https://github.com/synthetichealth/synthea)
- [EHI Export API reference implementation](https://github.com/smart-on-fhir/ehi-server)
- [Argonaut EHI Export draft spec](https://build.fhir.org/ig/argonautproject/ehi-api/ehi-export.html)

## Provider Assistant Runtimes

The provider assistant now supports deterministic and Anthropic Agent SDK modes behind the same API endpoint.

- Integration guide: `architecture/ANTHROPIC-AGENT-SDK.md`
- Agent profile files: `api/agents/provider-assistant/`
