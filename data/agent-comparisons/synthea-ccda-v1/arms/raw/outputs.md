# Raw arm outputs

Evidence used only from:
- `data/agent-comparisons/synthea-ccda-v1/arms/raw/inputs/ehr-snapshot-2018.json`
- `data/agent-comparisons/synthea-ccda-v1/arms/raw/inputs/ehr-snapshot-2024.json`

## patient-summary

1. **You are a 56-year-old woman in the record**: Adria871 Ankunding277, female, born 1968-03-02, living in Hopedale, Massachusetts. Source: `ehr-snapshot-2018.json` and `ehr-snapshot-2024.json` Patient resource.
2. **Main active problems listed are chronic sinusitis, obesity, prior miscarriage still marked active, and hyperlipidemia.** Chronic sinusitis started 2005; BMI 30+ obesity started 2016; hyperlipidemia appears in the later snapshot with onset 2018-03-03. The miscarriage in first trimester from 2010 is still marked active, which may be a chart cleanup issue. Sources: `ehr-snapshot-2024.json` Condition resources.
3. **Cholesterol became a major issue in 2018, but the same-day lipid data conflict.** One 2018-03-03 lipid panel shows high total cholesterol 216.0 mg/dL, triglycerides 203.6 mg/dL, LDL 178.2 mg/dL, and low HDL 32.6 mg/dL; another same-day lipid panel shows total cholesterol 173.2, triglycerides 106.8, LDL 75.6, HDL 76.2. Sources: `ehr-snapshot-2024.json` Observations `62bf6f68`, `03ea313a`, `fffcd252`, `18931cba`, `5d9ba2ac`, `d14048b6`, `e1f4f059`, `10b82af9`.
4. **A statin was started and remains listed as active.** Simvistatin 10 MG was ordered 2018-03-24 with status stopped, then again 2019-03-24 with status active. Source: `ehr-snapshot-2024.json` MedicationRequest resources.
5. **Kidney-related values need clinician review because the source values do not line up cleanly.** Creatinine is about 2.6 mg/dL in 2018 and 2.5 mg/dL in 2019, while eGFR is simultaneously about 86 mL/min. That combination is internally inconsistent for many adults and should be verified against the original lab system. Sources: `ehr-snapshot-2024.json` Observations `211e64ea`, `847c0f6d`, `3c1ee610`, `2c412690`.

**What changed recently / later in the record:** Compared with the 2018 snapshot, the 2024 snapshot adds hyperlipidemia, simvastatin therapy, 2018-2019 chemistry/lipid labs, 2018-2019 immunizations, claims/EOB/procedure resources, and a 2018 pregnancy/blighted ovum episode marked resolved. Sources: both snapshot files.

**Information that appears missing or incomplete:** No AllergyIntolerance resources are present; source lab reference ranges and abnormal flags are mostly absent; no encounters, labs, or medications after 2019 are evident despite the `2024` filename; medication dose instructions and adherence are unclear; no active problem list review date is visible. Sources: `ehr-snapshot-2024.json` resource inventory and lab resources.

**Ask your doctor:**
- Is simvastatin still intended, and is “Simvistatin” a spelling/data-entry issue for simvastatin?
- Which 2018 lipid panel is correct, and should the duplicate/conflicting same-day results be reconciled?
- Are the high creatinine values real, and if so why is the eGFR normal?
- Should the old miscarriage remain an active condition?
- Are there allergies or no known allergies that should be explicitly documented?

## clinician-handoff

**Patient:** Adria871 Ankunding277, female, DOB 1968-03-02, Hopedale MA. Sources: Patient resource in `ehr-snapshot-2018.json`; Patient resource in `ehr-snapshot-2024.json`.

**Reason for specialist review:** Later snapshot adds hyperlipidemia/statin therapy and internally inconsistent renal labs; source contains duplicate/conflicting lipid values on 2018-03-03.

### Active / current items

**Active conditions in `ehr-snapshot-2024.json`:**
- Chronic sinusitis, onset 2005-06-25.
- Miscarriage in first trimester, onset 2010-01-16, still marked active; likely needs problem-list review.
- Body mass index 30+ / obesity, onset 2016-03-26.
- Hyperlipidemia, onset 2018-03-03.

**Resolved historical conditions:** normal pregnancies/blighted ovum episodes, viral sinusitis, acute viral pharyngitis, wrist sprain. Source: `ehr-snapshot-2024.json` Condition resources.

**Medications:**
- Active: Simvistatin 10 MG, authored 2019-03-24. Source: `ehr-snapshot-2024.json` MedicationRequest.
- Prior stopped: Simvistatin 10 MG authored 2018-03-24; multiple prior contraceptives; amoxicillin/clavulanate in 2015; ibuprofen in 2016. Sources: `ehr-snapshot-2018.json` and `ehr-snapshot-2024.json` MedicationRequest resources.

**Allergies:** No AllergyIntolerance resources found in either raw input. This should be treated as missing allergy documentation, not proof of no allergies.

### Recent labs needing review

Source abnormal flags/reference ranges are not populated in the lab Observation resources. Values needing review:
- **Lipids, 2018-03-03:** conflicting same-day panels: total cholesterol 216.0 / TG 203.6 / LDL 178.2 / HDL 32.6 versus total cholesterol 173.2 / TG 106.8 / LDL 75.6 / HDL 76.2. Source: `ehr-snapshot-2024.json` lipid Observations and DiagnosticReports `d43af450`, `814fa904`.
- **Kidney function, 2018-2019:** creatinine 2.59 mg/dL on 2018-03-03 and 2.52 mg/dL on 2019-03-24, with eGFR 85.7 and 86.4 mL/min respectively. This is discordant and should be validated. Source: `ehr-snapshot-2024.json` Observations `211e64ea`, `847c0f6d`, `3c1ee610`, `2c412690`.
- **ALT:** 47.8 U/L on 2019-03-24; no source reference range or abnormal interpretation provided. Source: `ehr-snapshot-2024.json` Observation `ad318a17`.

### Other data

2018-2019 immunizations include zoster, seasonal influenza, and Td. Source: `ehr-snapshot-2024.json` Immunization resources. Procedures include colonoscopy, contraceptive procedures, physical exams, depression screening, pregnancy tests, and fetal viability ultrasounds, but many Procedure resources lack performed dates in the extracted fields. Source: `ehr-snapshot-2024.json` Procedure resources.

### Missing / uncertain

- No allergy documentation.
- No source lab reference ranges or abnormal flags.
- No clear data after 2019 in the `2024` snapshot.
- Medication adherence, fill history, dose schedule, and statin indication/goals are not clear.
- Old obstetric condition still active may be stale.

## source-contribution

### `ehr-snapshot-2018.json`

Contributed baseline EHR-style clinical history through 2016: patient demographics, organizations/practitioners, 21 encounters, 9 conditions, 44 observations, 6 immunizations, 3 diagnostic reports, 8 medication requests, care teams, and a care plan. Unique or mostly unique details include earlier lipid results from 2010 and 2014, a 2014 CBC, contraceptive medication history, 2015 amoxicillin/clavulanate for viral sinusitis episode context, and 2016 wrist sprain/ibuprofen. No allergies present.

### `ehr-snapshot-2024.json`

Contributed the later/enriched record: same patient demographics, 12 conditions, 40 claims, 30 EOBs, 17 procedures, 9 encounters, 56 observations, 5 diagnostic reports, 2 medication requests, and 2018-2019 additions. Unique later facts include hyperlipidemia onset 2018-03-03, active Simvistatin 10 MG authored 2019-03-24, comprehensive metabolic panels from 2018 and 2019, duplicate/conflicting lipid panels on 2018-03-03, 2019 lipid panel, 2018-2019 immunizations, and claims/EOB/procedure resources.

### Facts appearing in both sources

- Same patient identity/demographics: female Adria871 Ankunding277, DOB 1968-03-02, Hopedale MA.
- Earlier conditions through 2016 are carried forward: chronic sinusitis, 2010 pregnancy/miscarriage/blighted ovum history, viral sinusitis episodes, acute viral pharyngitis, obesity, wrist sprain.
- No AllergyIntolerance resources in either input.

### Unique facts / conflicts requiring review

- **Same-day lipid conflict in 2024 source:** two 2018-03-03 lipid panels differ substantially; one supports hyperlipidemia and one appears much improved/normal. Needs reconciliation before clinical use.
- **Creatinine/eGFR discordance in 2024 source:** creatinine ~2.5-2.6 mg/dL with eGFR ~86 mL/min is internally suspicious and should be validated.
- **Active miscarriage condition:** 2010 miscarriage remains marked active in both snapshots while related pregnancy/blighted ovum entries are resolved; likely duplicate/stale problem-list artifact.
- **No data after 2019 despite 2024 file name:** the later snapshot may be a 2024 export containing data only through 2019, or post-2019 data are missing.
- **Medication spelling:** `Simvistatin` appears in source; likely intended simvastatin but should not be silently normalized.

## chart-ready-labs

Reference ranges and explicit abnormal interpretation flags are not present in the raw Observation resources reviewed. “Abnormal flag” below therefore means source-provided flag, not clinical interpretation.

| Category | Test | Date | Value | Unit | Reference range | Abnormal flag | Source |
|---|---|---:|---:|---|---|---|---|
| Metabolic/lipid | Total Cholesterol | 2010-03-13 | 178.67 | mg/dL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `95cd9627` |
| Metabolic/lipid | Triglycerides | 2010-03-13 | 144.36 | mg/dL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `241f1bb5` |
| Metabolic/lipid | LDL Cholesterol | 2010-03-13 | 90.44 | mg/dL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `0cb4b22a` |
| Metabolic/lipid | HDL Cholesterol | 2010-03-13 | 59.36 | mg/dL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `da762eed` |
| Metabolic/lipid | Total Cholesterol | 2014-03-22 | 183.13 | mg/dL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `b905dc11` |
| Metabolic/lipid | Triglycerides | 2014-03-22 | 101.41 | mg/dL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `91362ed5` |
| Metabolic/lipid | LDL Cholesterol | 2014-03-22 | 96.06 | mg/dL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `7c1df92c` |
| Metabolic/lipid | HDL Cholesterol | 2014-03-22 | 66.79 | mg/dL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `4474fe42` |
| Hematology | Leukocytes | 2014-03-22 | 9.24 | 10*3/uL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `ffcf2e06` |
| Hematology | Erythrocytes | 2014-03-22 | 5.15 | 10*6/uL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `6b456e9a` |
| Hematology | Hemoglobin | 2014-03-22 | 13.87 | g/dL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `70dc8c2f` |
| Hematology | Hematocrit | 2014-03-22 | 44.85 | % | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `005d2407` |
| Hematology | Platelets | 2014-03-22 | 355.14 | 10*3/uL | Not provided | Not provided | `ehr-snapshot-2018.json` Obs `a989f023` |
| Metabolic/lipid | Total Cholesterol | 2018-03-03 | 216.00 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `62bf6f68` |
| Metabolic/lipid | Triglycerides | 2018-03-03 | 203.62 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `03ea313a` |
| Metabolic/lipid | LDL Cholesterol | 2018-03-03 | 178.24 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `fffcd252` |
| Metabolic/lipid | HDL Cholesterol | 2018-03-03 | 32.61 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `18931cba` |
| Metabolic | Glucose | 2018-03-03 | 89.29 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `e7cba112` |
| Kidney | Urea Nitrogen | 2018-03-03 | 16.63 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `d8b3964e` |
| Kidney | Creatinine | 2018-03-03 | 2.59 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `211e64ea` |
| Kidney | eGFR | 2018-03-03 | 85.67 | mL/min | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `847c0f6d` |
| Metabolic | Calcium | 2018-03-03 | 8.53 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `4060d6b9` |
| Metabolic | Sodium | 2018-03-03 | 137.68 | mmol/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `64f06f8c` |
| Metabolic | Potassium | 2018-03-03 | 4.23 | mmol/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `ca3d71b4` |
| Metabolic | Chloride | 2018-03-03 | 103.14 | mmol/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `42b2f66f` |
| Metabolic | Carbon Dioxide | 2018-03-03 | 28.70 | mmol/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `c4ce6586` |
| Liver/protein | Total Protein | 2018-03-03 | 78.55 | g/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `5a596695` |
| Liver/protein | Albumin | 2018-03-03 | 5.05 | g/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `67a26e8a` |
| Liver/protein | Globulin | 2018-03-03 | 2.02 | g/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `ebc90006` |
| Liver | Total Bilirubin | 2018-03-03 | 0.82 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `0364b963` |
| Liver | Alkaline phosphatase | 2018-03-03 | 60.04 | U/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `df641d6a` |
| Liver | ALT | 2018-03-03 | 20.09 | U/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `17ff603e` |
| Liver | AST | 2018-03-03 | 20.12 | U/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `45556218` |
| Metabolic/lipid | Total Cholesterol | 2018-03-03 | 173.21 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `5d9ba2ac` |
| Metabolic/lipid | Triglycerides | 2018-03-03 | 106.76 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `d14048b6` |
| Metabolic/lipid | LDL Cholesterol | 2018-03-03 | 75.61 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `e1f4f059` |
| Metabolic/lipid | HDL Cholesterol | 2018-03-03 | 76.25 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `10b82af9` |
| Metabolic | Glucose | 2019-03-24 | 94.72 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `11a14e9f` |
| Kidney | Urea Nitrogen | 2019-03-24 | 18.87 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `552dbd65` |
| Kidney | Creatinine | 2019-03-24 | 2.52 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `3c1ee610` |
| Kidney | eGFR | 2019-03-24 | 86.40 | mL/min | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `2c412690` |
| Metabolic | Calcium | 2019-03-24 | 10.04 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `7b5414d0` |
| Metabolic | Sodium | 2019-03-24 | 137.96 | mmol/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `41ab9332` |
| Metabolic | Potassium | 2019-03-24 | 4.12 | mmol/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `75b3a534` |
| Metabolic | Chloride | 2019-03-24 | 103.38 | mmol/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `f07f6baf` |
| Metabolic | Carbon Dioxide | 2019-03-24 | 25.66 | mmol/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `edec7ab8` |
| Liver/protein | Total Protein | 2019-03-24 | 61.10 | g/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `38951eea` |
| Liver/protein | Albumin | 2019-03-24 | 5.50 | g/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `2bfa4552` |
| Liver/protein | Globulin | 2019-03-24 | 2.96 | g/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `3bfd6e06` |
| Liver | Total Bilirubin | 2019-03-24 | 0.38 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `4ae3f0e7` |
| Liver | Alkaline phosphatase | 2019-03-24 | 53.01 | U/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `25e8f745` |
| Liver | ALT | 2019-03-24 | 47.83 | U/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `ad318a17` |
| Liver | AST | 2019-03-24 | 17.25 | U/L | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `8428f97d` |
| Metabolic/lipid | Total Cholesterol | 2019-03-24 | 176.39 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `d290669b` |
| Metabolic/lipid | Triglycerides | 2019-03-24 | 156.28 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `11a9c57e` |
| Metabolic/lipid | LDL Cholesterol | 2019-03-24 | 119.41 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `9bc80bdd` |
| Metabolic/lipid | HDL Cholesterol | 2019-03-24 | 54.52 | mg/dL | Not provided | Not provided | `ehr-snapshot-2024.json` Obs `39d05548` |

**Missing / not comparable:**
- No source reference ranges or interpretation flags were found for the listed labs.
- CBC/hematology data are present in 2014 only; no later CBC trend is available in the raw inputs reviewed.
- Comprehensive metabolic/liver/kidney panels are present in 2018 and 2019 only, not in the 2018 snapshot baseline.
- Lipids are not cleanly comparable on 2018-03-03 because two same-day panels conflict.
- Protein units appear questionable/inconsistent (`g/dL` values like 78.55; globulin in `g/L`), requiring source-system validation.

## agent-audit

| Claim | Evidence used | Support status / caveat |
|---|---|---|
| Patient is female, DOB 1968-03-02, Hopedale MA | Patient resources in both raw input JSON files | Supported |
| Active conditions include chronic sinusitis, miscarriage, obesity, hyperlipidemia | Condition resources in `ehr-snapshot-2024.json` | Supported by source statuses; miscarriage being clinically active is questionable but source says active |
| No allergies documented | Absence of AllergyIntolerance resources in both files | Supported as “not documented”; does not prove no allergies |
| Hyperlipidemia appears in later snapshot, onset 2018-03-03 | Condition resource in `ehr-snapshot-2024.json` | Supported |
| Simvistatin 10 MG is active as of 2019-03-24 | MedicationRequest in `ehr-snapshot-2024.json` | Supported; spelling reproduced from source |
| Earlier simvistatin order was stopped | MedicationRequest in `ehr-snapshot-2024.json` authored 2018-03-24 | Supported |
| 2018 same-day lipid panels conflict | Observation values in `ehr-snapshot-2024.json` on 2018-03-03 | Supported |
| Creatinine and eGFR are internally discordant | Creatinine/eGFR Observation pairs in `ehr-snapshot-2024.json` plus clinical consistency reasoning | Values supported; discordance interpretation is analytic and should be clinician-verified |
| Source has no lab reference ranges/abnormal flags for reviewed labs | Observation resources reviewed from both inputs | Supported for reviewed lab set |
| No data after 2019 despite 2024 filename | Dates observed in encounters/labs/medications/immunizations reviewed from `ehr-snapshot-2024.json` | Supported for reviewed resource types; there may be other nonclinical metadata dates not assessed |
| 2024 source added claims/EOB/procedure resources | Resource type counts from `ehr-snapshot-2024.json` | Supported |
| 2018 source contributed baseline through 2016 plus earlier labs | Resource dates/types in `ehr-snapshot-2018.json` | Supported |
| Procedures include colonoscopy and contraceptive/pregnancy-related procedures | Procedure resources in `ehr-snapshot-2024.json` | Supported, but many procedure date fields were not obvious from simple extraction |
| Patient should ask doctor to reconcile active miscarriage and no allergies | Derived from source statuses/absence | Reasonable recommendation, not directly source-stated |
| Protein/globulin units may be questionable | Observation values/units in `ehr-snapshot-2024.json` | Analytic caveat; adequate support from unusual units/values but needs lab-system confirmation |
