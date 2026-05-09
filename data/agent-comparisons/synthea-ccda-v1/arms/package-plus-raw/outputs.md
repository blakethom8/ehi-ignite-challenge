# patient-summary

Patient: Adria871 Ankunding277, female, born 1968-03-02 (raw Patient record: `ehr-snapshot-2024:Patient/7978d71c-094b-459e-92be-2b62f4cf5e6c`). This is a synthetic Synthea record package and is not medical advice.

Five most important plain-language takeaways:

1. **Cholesterol became an active diagnosis in 2018, with ongoing statin treatment in 2019.** Hyperlipidemia appears as an active/confirmed 2018 condition in the 2024 EHR snapshot (`fact-0012-condition; prov-0012-01`; raw Condition status checked in `ehr-snapshot-2024`). Simvastatin 10 mg was reordered/active on 2019-03-24 (`fact-0072-medicationrequest; prov-0072-01`; raw MedicationRequest status checked in `ehr-snapshot-2024`).
2. **Recent labs are mostly from March 2019, but the package does not provide reference ranges or abnormal flags.** Recent values include LDL 119.41 mg/dL (`fact-0092-observation; prov-0092-01`), triglycerides 156.28 mg/dL (`fact-0118-observation; prov-0118-01`), glucose 94.72 mg/dL (`fact-0113-observation; prov-0113-01`), creatinine 2.52 mg/dL (`fact-0134-observation; prov-0134-01`), and eGFR 86.40 mL/min (`fact-0132-observation; prov-0132-01`). Ask a clinician to interpret these using the lab's actual reference ranges.
3. **Kidney-related values need review because creatinine and eGFR look discordant in the structured data.** Creatinine is recorded at 2.59 mg/dL in 2018 and 2.52 mg/dL in 2019 (`fact-0133-observation; prov-0133-01`, `fact-0134-observation; prov-0134-01`), while eGFR is recorded around 86 mL/min in both years (`fact-0131-observation; prov-0131-01`, `fact-0132-observation; prov-0132-01`). The record itself does not explain the discrepancy.
4. **Weight/BMI history shows obesity was recorded in 2016, with later BMI just under 30.** Obesity is a cross-source matched condition dated 2016 (`fact-0001-condition; prov-0001-01, prov-0001-02`). BMI was 30.19 kg/m2 in 2016 (`fact-0138-observation; prov-0138-01`), 28.49 in 2018 (`fact-0139-observation; prov-0139-01`), and 29.08 in 2019 (`fact-0140-observation; prov-0140-01`).
5. **The medication/problem list has extra CCDA history that is not duplicated in the two EHR snapshots.** The CCDA-only source contributes hypertension, cerebral artery occlusion with infarction, COPD, UTI, syncope/collapse, and older medications such as lisinopril, clonidine, aspirin, Lipitor, and Tavist (`prov-0007-01`, `prov-0008-01`, `prov-0011-01`, `prov-0013-01`, `prov-0017-01`, `prov-0067-01` to `prov-0081-01`). These need reconciliation before assuming they are current.

What changed recently:
- The 2024 snapshot adds 2018-2019 data not present in the 2018 snapshot, including active hyperlipidemia, simvastatin orders, 2018/2019 CMP and lipid labs, 2019 immunizations, and 2018 pregnancy-related encounters/procedures (`source-contributions.json`; `fact-0012-condition`, `fact-0071-medicationrequest`, `fact-0072-medicationrequest`, `fact-0018-diagnosticreport`, `fact-0019-diagnosticreport`, `fact-0023-diagnosticreport`).
- The latest broad lab date is 2019-03-24 (`prov-0019-01`, `prov-0023-01`), with a separate 2019-03-09 visit/vitals/immunization set (`prov-0035-01`, `prov-0056-01`, `prov-0058-01`, `prov-0064-01`).

Missing or uncertain information:
- No allergy list facts found in packaged sources (`missing-information.json`).
- Lab reference ranges and abnormal flags are not provided in the Atlas labs export or FHIR observations checked.
- Blood pressure observations exist but have no packaged numeric value (`fact-0144-observation` to `fact-0149-observation`).
- 2018 lipid values conflict/duplicate on the same date and need review (`conflicts.json`; see source-contribution section).

Questions to ask the doctor:
- Is the active medication list correct, especially simvastatin 10 mg daily and the older CCDA medications?
- Are there any medication or environmental allergies that should be added?
- How should the creatinine/eGFR discrepancy be interpreted, and should kidney labs be repeated?
- Which 2018 lipid result set is valid, and what lipid goal applies?
- Are the CCDA-only diagnoses (hypertension, prior cerebral artery occlusion/infarction, COPD) current, historical, or erroneous?

# clinician-handoff

**Patient:** Adria871 Ankunding277; female; DOB 1968-03-02. Sources: `ehr-snapshot-2018.json`, `ehr-snapshot-2024.json`, `problems-and-medications.xml`.

## Active / clinically relevant conditions

| Condition | Date/onset | Status/evidence | Source |
| --- | --- | --- | --- |
| Hyperlipidemia | 2018-03-03 | Active/confirmed in raw 2024 Condition; canonical fact | `fact-0012-condition; prov-0012-01` |
| Body mass index 30+ / obesity | 2016-03-26 | Active/confirmed in raw 2018/2024 Conditions; cross-source matched | `fact-0001-condition; prov-0001-01, prov-0001-02` |
| Chronic sinusitis | 2005-06-25 | Active/confirmed in raw 2018/2024 Conditions; cross-source matched | `fact-0006-condition; prov-0006-01, prov-0006-02` |
| Miscarriage in first trimester | 2010-01-16 | Raw status active in EHR snapshots, but clinically may be historical; review | `fact-0002-condition; prov-0002-01, prov-0002-02` |
| Hypertension, essential | 2006-05-16 | CCDA-only; status/currentness unclear | `fact-0007-condition; prov-0007-01` |
| Cerebral artery occlusion with cerebral infarction | 2009-07-09 | CCDA-only; status/currentness unclear | `fact-0008-condition; prov-0008-01` |
| Chronic obstructive airways disease | 2007-08-12 | CCDA-only; status/currentness unclear | `fact-0011-condition; prov-0011-01` |

## Medications

| Medication | Date | Status / note | Source |
| --- | --- | --- | --- |
| Simvistatin 10 MG | 2019-03-24 | Active in raw 2024 MedicationRequest; daily dosing present in raw source | `fact-0072-medicationrequest; prov-0072-01` |
| Simvistatin 10 MG | 2018-03-24 | Stopped in raw 2024 MedicationRequest | `fact-0071-medicationrequest; prov-0071-01` |
| Lipitor 20 mg oral tablet | 2007-08-14 | CCDA-only, ordered; no end date in CCDA narrative; reconcile with simvastatin | `fact-0075-medicationrequest; prov-0075-01` |
| Lisinopril / lisinopril 10 mg oral tablet | 2008-09-22 and 2009-07-15 | CCDA-only; one 2008 row has end date 2008-10-02, later Zestril/lisinopril row has no CCDA end date | `fact-0070-medicationrequest; prov-0070-01`, `fact-0067-medicationrequest; prov-0067-01` |
| Clonidine | 2006-05-16 | CCDA-only ordered medication; currentness unclear | `fact-0068-medicationrequest; prov-0068-01` |
| Aspirin | 2009-07-15 | CCDA-only ordered medication; currentness unclear | `fact-0080-medicationrequest; prov-0080-01` |
| Tavist | 2009-07-15 | CCDA-only ordered medication; currentness unclear | `fact-0081-medicationrequest; prov-0081-01` |
| Other stopped/historical meds | 2010-2016 | contraception, antibiotic, ibuprofen, medroxyprogesterone listed as stopped in EHR snapshots | `fact-0066`, `fact-0069`, `fact-0073`, `fact-0074`, `fact-0076`-`fact-0079` |

## Allergies

No allergy list facts found in packaged sources (`missing-information.json`). Confirm allergies directly with patient/source system.

## Recent labs / abnormalities

No source-provided abnormal flags or reference ranges were found. Recent 2019 values for review: creatinine 2.52 mg/dL with eGFR 86.40 mL/min (`fact-0134-observation; prov-0134-01`, `fact-0132-observation; prov-0132-01`), triglycerides 156.28 mg/dL (`fact-0118-observation; prov-0118-01`), LDL 119.41 mg/dL (`fact-0092-observation; prov-0092-01`), ALT 47.83 U/L (`fact-0085-observation; prov-0085-01`), glucose 94.72 mg/dL (`fact-0113-observation; prov-0113-01`). Interpret against actual lab reference ranges.

## Gaps / review items

- Reconcile allergies, active medications, and CCDA-only problem list.
- Resolve 2018 duplicate/conflicting lipid panel values.
- Blood pressure observations have no numeric values in canonical evidence.
- Verify creatinine/eGFR internal consistency.

# source-contribution

## Source contributions by package metadata

| Source | Kind | Fact count | Resource mix | Contribution |
| --- | ---: | ---: | --- | --- |
| `ehr-snapshot-2018.json` | FHIR bundle | 91 | 9 conditions, 3 diagnostic reports, 21 encounters, 6 immunizations, 8 medication requests, 44 observations | Earlier EHR history through 2018 snapshot: cross-source shared chronic/past conditions, historical encounters, 2010/2014 lipid/CBC labs, vitals, immunizations, stopped meds. |
| `ehr-snapshot-2024.json` | FHIR bundle | 106 | 12 conditions, 5 diagnostic reports, 9 encounters, 5 immunizations, 2 medication requests, 56 observations, 17 procedures | Newer EHR view adding 2018-2019 labs, active hyperlipidemia, active 2019 simvastatin, 2018 pregnancy-related events, procedures, later immunizations/vitals. |
| `problems-and-medications.xml` | CCDA XML | 11 | 5 conditions, 6 medication requests | Extra problem/medication list not matched in the EHR snapshots: hypertension, cerebral infarction diagnosis, COPD, UTI, syncope/collapse; lisinopril/clonidine/Lipitor/aspirin/Tavist. |

## Facts appearing in more than one source

The two FHIR snapshots share multiple core condition facts, including obesity (`fact-0001-condition; prov-0001-01, prov-0001-02`), miscarriage in first trimester (`fact-0002-condition; prov-0002-01, prov-0002-02`), acute viral pharyngitis (`fact-0003-condition; prov-0003-01, prov-0003-02`), blighted ovum dated 2010 (`fact-0004-condition; prov-0004-01, prov-0004-02`), chronic sinusitis (`fact-0006-condition; prov-0006-01, prov-0006-02`), viral sinusitis episodes (`fact-0009-condition; prov-0009-01, prov-0009-02`, `fact-0010-condition; prov-0010-01, prov-0010-02`), wrist sprain (`fact-0014-condition; prov-0014-01, prov-0014-02`), and normal pregnancy dated 2010 (`fact-0015-condition; prov-0015-01, prov-0015-02`).

## Unique facts by source

- **2018 EHR snapshot unique:** older diagnostic reports/labs, many historical encounters/immunizations, and stopped medication requests such as medroxyprogesterone, ibuprofen, etonogestrel implant, amoxicillin-clavulanate, and oral contraceptives (`source-contributions.json`; examples `fact-0020`, `fact-0021`, `fact-0024`, `fact-0066`, `fact-0069`, `fact-0073`, `fact-0074`, `fact-0076`-`fact-0079`).
- **2024 EHR snapshot unique:** active hyperlipidemia (`fact-0012-condition; prov-0012-01`), 2018/2019 CMP and lipid panels (`fact-0018`, `fact-0019`, `fact-0022`, `fact-0023`), active simvastatin (`fact-0072-medicationrequest; prov-0072-01`), later labs/vitals, procedures, and 2018 pregnancy-related resolved conditions (`fact-0005`, `fact-0016`).
- **CCDA unique:** all 11 CCDA facts are unique to `problems-and-medications.xml`; no shared fact IDs are reported for that source in `source-contributions.json`.

## Conflicts / duplicates requiring review

On 2018-03-03 the package reports same-date lipid duplicates/conflicts:
- LDL: 178.24 vs 75.61 mg/dL (`prov-0090-01`, `prov-0091-01`).
- HDL: 32.61 vs 76.25 mg/dL (`prov-0103-01`, `prov-0104-01`).
- Total cholesterol: 173.21 vs 216.00 mg/dL (`prov-0108-01`, `prov-0109-01`).
- Triglycerides: 106.76 vs 203.62 mg/dL (`prov-0116-01`, `prov-0117-01`).

# chart-ready-labs

Reference ranges and abnormal flags were **not provided** in the Atlas `exports/labs.csv` or the FHIR observations checked, so those columns are marked `not provided`. Duplicate 2018 lipid values are retained rather than collapsed because `conflicts.json` flags them for review.

| Category | Test name | Date | Value | Unit | Reference range | Abnormal flag | Source |
| --- | --- | --- | ---: | --- | --- | --- | --- |
| Hematology | Erythrocyte distribution width [Entitic volume] by Automated count | 2014-03-22 | 41.00 | fL | not provided | not provided | prov-0111-01 |
| Hematology | Erythrocytes [#/volume] in Blood by Automated count | 2014-03-22 | 5.15 | 10*6/uL | not provided | not provided | prov-0174-01 |
| Hematology | Hematocrit [Volume Fraction] of Blood by Automated count | 2014-03-22 | 44.85 | % | not provided | not provided | prov-0141-01 |
| Hematology | Hemoglobin [Mass/volume] in Blood | 2014-03-22 | 13.87 | g/dL | not provided | not provided | prov-0157-01 |
| Hematology | Leukocytes [#/volume] in Blood by Automated count | 2014-03-22 | 9.24 | 10*3/uL | not provided | not provided | prov-0154-01 |
| Hematology | MCH [Entitic mass] by Automated count | 2014-03-22 | 30.05 | pg | not provided | not provided | prov-0171-01 |
| Hematology | MCHC [Mass/volume] by Automated count | 2014-03-22 | 35.86 | g/dL | not provided | not provided | prov-0172-01 |
| Hematology | MCV [Entitic volume] by Automated count | 2014-03-22 | 83.86 | fL | not provided | not provided | prov-0173-01 |
| Hematology | Platelet distribution width [Entitic volume] in Blood by Automated count | 2014-03-22 | 171.84 | fL | not provided | not provided | prov-0129-01 |
| Hematology | Platelet mean volume [Entitic volume] in Blood by Automated count | 2014-03-22 | 12.19 | fL | not provided | not provided | prov-0130-01 |
| Hematology | Platelets [#/volume] in Blood by Automated count | 2014-03-22 | 355.14 | 10*3/uL | not provided | not provided | prov-0170-01 |
| Kidney | Creatinine | 2018-03-03 | 2.59 | mg/dL | not provided | not provided | prov-0133-01 |
| Kidney | Creatinine | 2019-03-24 | 2.52 | mg/dL | not provided | not provided | prov-0134-01 |
| Kidney | Glomerular filtration rate/1.73 sq M.predicted | 2018-03-03 | 85.67 | mL/min | not provided | not provided | prov-0131-01 |
| Kidney | Glomerular filtration rate/1.73 sq M.predicted | 2019-03-24 | 86.40 | mL/min | not provided | not provided | prov-0132-01 |
| Kidney | Urea Nitrogen | 2018-03-03 | 16.63 | mg/dL | not provided | not provided | prov-0152-01 |
| Kidney | Urea Nitrogen | 2019-03-24 | 18.87 | mg/dL | not provided | not provided | prov-0153-01 |
| Liver | Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma | 2018-03-03 | 20.09 | U/L | not provided | not provided | prov-0084-01 |
| Liver | Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma | 2019-03-24 | 47.83 | U/L | not provided | not provided | prov-0085-01 |
| Liver | Albumin [Mass/volume] in Serum or Plasma | 2018-03-03 | 5.05 | g/dL | not provided | not provided | prov-0086-01 |
| Liver | Albumin [Mass/volume] in Serum or Plasma | 2019-03-24 | 5.50 | g/dL | not provided | not provided | prov-0087-01 |
| Liver | Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma | 2018-03-03 | 60.04 | U/L | not provided | not provided | prov-0155-01 |
| Liver | Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma | 2019-03-24 | 53.01 | U/L | not provided | not provided | prov-0156-01 |
| Liver | Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma | 2018-03-03 | 20.12 | U/L | not provided | not provided | prov-0093-01 |
| Liver | Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma | 2019-03-24 | 17.25 | U/L | not provided | not provided | prov-0094-01 |
| Liver | Bilirubin.total [Mass/volume] in Serum or Plasma | 2018-03-03 | 0.82 | mg/dL | not provided | not provided | prov-0095-01 |
| Liver | Bilirubin.total [Mass/volume] in Serum or Plasma | 2019-03-24 | 0.38 | mg/dL | not provided | not provided | prov-0096-01 |
| Liver | Globulin [Mass/volume] in Serum by calculation | 2018-03-03 | 2.02 | g/L | not provided | not provided | prov-0082-01 |
| Liver | Globulin [Mass/volume] in Serum by calculation | 2019-03-24 | 2.96 | g/L | not provided | not provided | prov-0083-01 |
| Liver | Protein [Mass/volume] in Serum or Plasma | 2018-03-03 | 78.55 | g/dL | not provided | not provided | prov-0119-01 |
| Liver | Protein [Mass/volume] in Serum or Plasma | 2019-03-24 | 61.10 | g/dL | not provided | not provided | prov-0120-01 |
| Metabolic | Calcium | 2018-03-03 | 8.53 | mg/dL | not provided | not provided | prov-0142-01 |
| Metabolic | Calcium | 2019-03-24 | 10.04 | mg/dL | not provided | not provided | prov-0143-01 |
| Metabolic | Carbon Dioxide | 2018-03-03 | 28.70 | mmol/L | not provided | not provided | prov-0097-01 |
| Metabolic | Carbon Dioxide | 2019-03-24 | 25.66 | mmol/L | not provided | not provided | prov-0098-01 |
| Metabolic | Chloride | 2018-03-03 | 103.14 | mmol/L | not provided | not provided | prov-0099-01 |
| Metabolic | Chloride | 2019-03-24 | 103.38 | mmol/L | not provided | not provided | prov-0100-01 |
| Metabolic | Glucose | 2018-03-03 | 89.29 | mg/dL | not provided | not provided | prov-0112-01 |
| Metabolic | Glucose | 2019-03-24 | 94.72 | mg/dL | not provided | not provided | prov-0113-01 |
| Metabolic | High Density Lipoprotein Cholesterol | 2010-03-13 | 59.36 | mg/dL | not provided | not provided | prov-0101-01 |
| Metabolic | High Density Lipoprotein Cholesterol | 2014-03-22 | 66.79 | mg/dL | not provided | not provided | prov-0102-01 |
| Metabolic | High Density Lipoprotein Cholesterol | 2018-03-03 | 32.61 | mg/dL | not provided | not provided | prov-0103-01 |
| Metabolic | High Density Lipoprotein Cholesterol | 2018-03-03 | 76.25 | mg/dL | not provided | not provided | prov-0104-01 |
| Metabolic | High Density Lipoprotein Cholesterol | 2019-03-24 | 54.52 | mg/dL | not provided | not provided | prov-0105-01 |
| Metabolic | Low Density Lipoprotein Cholesterol | 2010-03-13 | 90.44 | mg/dL | not provided | not provided | prov-0088-01 |
| Metabolic | Low Density Lipoprotein Cholesterol | 2014-03-22 | 96.06 | mg/dL | not provided | not provided | prov-0089-01 |
| Metabolic | Low Density Lipoprotein Cholesterol | 2018-03-03 | 178.24 | mg/dL | not provided | not provided | prov-0090-01 |
| Metabolic | Low Density Lipoprotein Cholesterol | 2018-03-03 | 75.61 | mg/dL | not provided | not provided | prov-0091-01 |
| Metabolic | Low Density Lipoprotein Cholesterol | 2019-03-24 | 119.41 | mg/dL | not provided | not provided | prov-0092-01 |
| Metabolic | Potassium | 2018-03-03 | 4.23 | mmol/L | not provided | not provided | prov-0150-01 |
| Metabolic | Potassium | 2019-03-24 | 4.12 | mmol/L | not provided | not provided | prov-0151-01 |
| Metabolic | Sodium | 2018-03-03 | 137.68 | mmol/L | not provided | not provided | prov-0127-01 |
| Metabolic | Sodium | 2019-03-24 | 137.96 | mmol/L | not provided | not provided | prov-0128-01 |
| Metabolic | Total Cholesterol | 2010-03-13 | 178.67 | mg/dL | not provided | not provided | prov-0106-01 |
| Metabolic | Total Cholesterol | 2014-03-22 | 183.13 | mg/dL | not provided | not provided | prov-0107-01 |
| Metabolic | Total Cholesterol | 2018-03-03 | 173.21 | mg/dL | not provided | not provided | prov-0108-01 |
| Metabolic | Total Cholesterol | 2018-03-03 | 216.00 | mg/dL | not provided | not provided | prov-0109-01 |
| Metabolic | Total Cholesterol | 2019-03-24 | 176.39 | mg/dL | not provided | not provided | prov-0110-01 |
| Metabolic | Triglycerides | 2010-03-13 | 144.36 | mg/dL | not provided | not provided | prov-0114-01 |
| Metabolic | Triglycerides | 2014-03-22 | 101.41 | mg/dL | not provided | not provided | prov-0115-01 |
| Metabolic | Triglycerides | 2018-03-03 | 106.76 | mg/dL | not provided | not provided | prov-0116-01 |
| Metabolic | Triglycerides | 2018-03-03 | 203.62 | mg/dL | not provided | not provided | prov-0117-01 |
| Metabolic | Triglycerides | 2019-03-24 | 156.28 | mg/dL | not provided | not provided | prov-0118-01 |

Missing/not comparable:
- No source-provided reference ranges or abnormal flags.
- Hematology labs appear only on 2014-03-22 in the packaged evidence, so no hematology trend can be compared across dates.
- Kidney/liver/CMP-style labs appear in 2018 and 2019 only.
- Lipids are longitudinal (2010, 2014, 2018, 2019), but 2018 contains unresolved same-date duplicate/conflicting results.
- Blood pressure observations lack numeric component values in canonical facts and therefore are not chart-ready here.

# agent-audit

| Important claim | Evidence used | Support status |
| --- | --- | --- |
| Patient identity/DOB/sex | Raw `ehr-snapshot-2024:Patient/7978d71c-094b-459e-92be-2b62f4cf5e6c` | Supported by raw source; not a canonical fact. |
| Hyperlipidemia is active/confirmed in 2024 source | `fact-0012-condition`; raw 2024 Condition checked for clinicalStatus/verificationStatus | Supported; raw used because canonical fact omits status. |
| Simvastatin 10 mg active on 2019-03-24 | `fact-0072-medicationrequest`; raw MedicationRequest checked for status/dose timing | Supported; raw used because canonical fact omits status/dose. |
| Older simvastatin order stopped | `fact-0071-medicationrequest`; raw MedicationRequest checked | Supported. |
| No allergies found | `missing-information.json` | Supported as absence signal from package, not proof patient has no allergies. |
| Creatinine 2018/2019 and eGFR 2018/2019 values | `fact-0133`, `fact-0134`, `fact-0131`, `fact-0132` | Supported by canonical facts. |
| Creatinine/eGFR need review because values appear discordant | Same kidney facts plus clinical plausibility reasoning | Partly supported; the need for review is an interpretive safety recommendation, not source-stated. |
| 2018 lipid duplicate/conflict values | `conflicts.json`; `fact-0090`/`0091`, `0103`/`0104`, `0108`/`0109`, `0116`/`0117` | Supported. |
| Obesity/BMI trend | `fact-0001`, `fact-0138`, `fact-0139`, `fact-0140`; raw condition status checked | Supported; active status from raw. |
| CCDA-only diagnoses and meds require reconciliation | `source-contributions.json`; CCDA provenance refs `prov-0007-01`, `prov-0008-01`, `prov-0011-01`, `prov-0013-01`, `prov-0017-01`, `prov-0067-01`-`prov-0081-01`; raw CCDA narrative spot-check | Supported; currentness unclear. |
| Lab reference ranges/abnormal flags absent | Atlas labs export columns and raw FHIR observations checked | Supported for inspected packaged/raw files. |
| Blood pressure numeric values missing | `fact-0144`-`fact-0149` have empty/null value in canonical facts/labs export | Supported for package evidence; raw components were not deeply reconstructed. |
| Active conditions list includes miscarriage as active but clinically review-needed | `fact-0002`; raw FHIR status active | Supported status, but clinical interpretation/currentness uncertain. |
| Source counts/resource mixes | `evidence/source-contributions.json` | Supported. |
| This is synthetic Synthea data/not medical advice | Package README/source text + agent instructions | Supported. |

Claims lacking adequate support:
- Any definitive clinical abnormal/normal interpretation of labs: **not made**, because reference ranges/flags are absent.
- Any assertion that CCDA-only medications or diagnoses are current: **not made**; explicitly marked unclear/reconcile.
- Any allergy status beyond “no allergy facts found”: **not made**.
