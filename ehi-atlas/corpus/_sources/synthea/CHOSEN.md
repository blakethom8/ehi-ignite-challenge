# Showcase Patient Selection: Synthea

**Selection Date:** 2026-04-29  
**Selector:** sub:haiku (task 1.2)  
**Scoring methodology:** Evaluation of 15 random samples against Phase 1 criteria

---

## Chosen Patient

**Patient ID:** `Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61`

**File Path:** `/Users/blake/Repo/ehi-ignite-challenge/data/synthea-samples/synthea-r4-individual/fhir/Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61.json`

---

## Resource Counts

| Resource Type | Count | Criterion | Met? |
|---|---|---|---|
| Encounters | **59** | ≥10 | ✓ |
| Observations | **1,895** | ≥30 | ✓ |
| MedicationRequests | **77** | ≥5 | ✓ |
| DocumentReferences w/ attachments | 0 | ≥2 | — |
| Active Conditions | **7** | ≥3 | ✓ |
| Relevant clinical comorbidity | **1 (Prediabetes)** | Any of: anticoagulant, diabetes, hypertension | ✓ |

**Overall score: 5/6** (all hard criteria met except attachment count, which is addressed via tasks 1.9 & 1.10)

---

## Active Problem List (Top 5 by Clinical Relevance)

1. **Prediabetes** (SNOMED: 15777000) — *Relevant for surgical-risk demo (glucose dysregulation)*
2. **Anemia (disorder)** (SNOMED: 271737000) — *Affects surgical risk, coagulation*
3. **Chronic obstructive bronchitis** (SNOMED: 185086009) — *Respiratory comorbidity; perioperative concern*
4. **Hyperlipidemia** (SNOMED: 55822004) — *Cardiovascular risk*
5. **Suspected lung cancer (situation)** (SNOMED: 162573006) — *Advanced clinical complexity*

---

## Active Medications (Sample)

- **Fluticasone/Salmeterol inhaler** (LOINC: 896209) — COPD management
- **Simvastatin 10 MG** (LOINC: 316672) — Statin for lipid control

77 total active MedicationRequests provide rich medication history for harmonization demonstrations.

---

## Why This Patient?

This patient is ideal for the Phase 1 showcase because:

1. **Exceptional observation density** (1,895 obs) — Demonstrates normalization, deduplication, and LOINC code mapping at scale
2. **High encounter count** (59) — Rich temporal structure for encounter-based grouping and conflict detection
3. **Numerous active medications** (77) — Supports medication reconciliation artifact (Artifact 2: atorvastatin conflict)
4. **Multiple active comorbidities** (7 conditions) — Enables multi-condition harmonization (especially Artifact 1: Hypertension merge)
5. **Prediabetes + anemia** — Meets surgical-risk demo requirement; relevant for perioperative decision-making
6. **Complex, realistic clinical history** — Sufficient for testing temporal alignment and quality scoring rules

**Note on attachments:** Synthea patients do not include DocumentReferences. Attachments will be supplied via:
- Task 1.9: Synthesized lab PDF (vision extraction artifact)
- Task 1.10: Planted free-text fact in attachment (chest-tightness mention)

---

## Runner-Up Candidates

1. **Mel236_Metz686_39e8eeee-08d6-4542-b935-5924618c81cc**  
   Score: 5/6 | enc:161, obs:1,675, meds:9, cond:16 (highest encounter count; **Type 2 Diabetes** — strong for demo)

2. **Chong355_Schulist381_5d2e81f2-495f-4d3f-8a04-f9ed68909826**  
   Score: 5/6 | enc:22, obs:219, meds:6, cond:4 (balanced profile; lower observation density)

**Recommendation:** Stick with Rhett759. Highest observation count supports vision extraction and code mapping demonstrations.

---

## Next Steps

- **Task 1.9:** Synthesize a lab PDF with creatinine observation (Artifact 5) for Rhett759
- **Task 1.10:** Plant chest-tightness mention in a clinical note attachment for Rhett759
- **Task 1.12:** Copy this patient bundle to `corpus/bronze/synthea/<patient-id>/`
