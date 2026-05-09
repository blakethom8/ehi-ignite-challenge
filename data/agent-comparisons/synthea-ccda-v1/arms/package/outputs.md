# PACKAGE arm outputs — EHI Atlas Synthea CCDA v1

Evidence base: EHI Atlas workspace package `synthea-demo-with-ccda.zip`, package version `atlas-workspace.v1`; demo/synthetic patient Adria871 Ankunding277. I used `MANIFEST.json`, `AGENT-INSTRUCTIONS.md`, `evidence/`, `packets/`, `exports/`, and source files only as supporting context.

## patient-summary

This is a synthetic/demo record, not medical advice. Five important things visible in the package:

1. **Heart/stroke risk history is important.** The CCDA problem/medication source lists active essential hypertension, chronic obstructive airways disease/COPD, and a prior cerebral artery occlusion with cerebral infarction; it also lists active aspirin, clonidine, Lipitor, and Tavist. Sources: fact-0007-condition; prov: prov-0007-01; source: extra-problems-and-medications:Condition/ccda-condition-3; fact-0011-condition; prov: prov-0011-01; source: extra-problems-and-medications:Condition/ccda-condition-2; fact-0008-condition; prov: prov-0008-01; source: extra-problems-and-medications:Condition/ccda-condition-1; fact-0068-medicationrequest; prov: prov-0068-01; source: extra-problems-and-medications:MedicationRequest/ccda-medication-10; fact-0075-medicationrequest; prov: prov-0075-01; source: extra-problems-and-medications:MedicationRequest/ccda-medication-7; fact-0080-medicationrequest; prov: prov-0080-01; source: extra-problems-and-medications:MedicationRequest/ccda-medication-9.
2. **Cholesterol history is mixed and needs review.** Hyperlipidemia appears in the 2024 EHR snapshot, and simvastatin 10 mg is active as of 2019-03-24. Recent lipids on 2019-03-24: total cholesterol 176.3945040832056 mg/dL, LDL 119.41047962688698 mg/dL, HDL 54.520528147734204 mg/dL, triglycerides 156.27982796203796 mg/dL. Sources: fact-0012-condition; prov: prov-0012-01; source: ehr-snapshot-2024:Condition/cbea4cdd-ec32-4a27-b619-c75f2c96bffb; fact-0072-medicationrequest; prov: prov-0072-01; source: ehr-snapshot-2024:MedicationRequest/834fef49-cd6d-4dbd-bcd1-f1c94707c0f1; fact-0110-observation; prov: prov-0110-01; source: ehr-snapshot-2024:Observation/d290669b-b453-46ba-927b-b935338f30c6; fact-0092-observation; prov: prov-0092-01; source: ehr-snapshot-2024:Observation/9bc80bdd-63dc-4799-9fbb-8568e9f62e2f; fact-0105-observation; prov: prov-0105-01; source: ehr-snapshot-2024:Observation/39d05548-8331-4889-b4dc-372ec41d461d; fact-0118-observation; prov: prov-0118-01; source: ehr-snapshot-2024:Observation/11a9c57e-92a6-4200-9408-e7773eca6d84.
3. **Kidney-related labs have internally odd-looking values and no source reference ranges/flags.** On 2019-03-24, creatinine is 2.5226746533976074 mg/dL with eGFR 86.3958917280481 mL/min and BUN 18.87099499622739 mg/dL. The package does not provide reference ranges or abnormal flags, so these should be clinician-reviewed rather than interpreted here. Sources: fact-0134-observation; prov: prov-0134-01; source: ehr-snapshot-2024:Observation/3c1ee610-870e-4c0c-a7ff-ee7c3f90f610; fact-0132-observation; prov: prov-0132-01; source: ehr-snapshot-2024:Observation/2c412690-e04d-4a2d-bf92-de864c1dfc29; fact-0153-observation; prov: prov-0153-01; source: ehr-snapshot-2024:Observation/552dbd65-91d7-4ce6-be08-54c2c9f5a11d.
4. **Recent changes are mostly in the 2024 snapshot.** Newer 2018–2019 items include hyperlipidemia, normal pregnancy/blighted ovum in 2018, zoster/Td/influenza immunizations in 2018–2019, an active simvastatin medication in 2019, and a 2019 CMP/lipid panel. Sources: fact-0012-condition; prov: prov-0012-01; source: ehr-snapshot-2024:Condition/cbea4cdd-ec32-4a27-b619-c75f2c96bffb; fact-0015-condition; prov: prov-0015-01, prov-0015-02; source: ehr-snapshot-2018:Condition/6c020948-4c27-471a-81aa-d623e9dccec3; ehr-snapshot-2024:Condition/6c020948-4c27-471a-81aa-d623e9dccec3; fact-0005-condition; prov: prov-0005-01; source: ehr-snapshot-2024:Condition/7082bd16-5280-423e-9d21-6eeee1f9180c; fact-0057-immunization; prov: prov-0057-01; source: ehr-snapshot-2024:Immunization/e454373e-4c24-482e-bd27-9fac3336d446; fact-0056-immunization; prov: prov-0056-01; source: ehr-snapshot-2024:Immunization/01ea6a2e-95e3-46c5-906d-0555ac74dfc8; fact-0064-immunization; prov: prov-0064-01; source: ehr-snapshot-2024:Immunization/b5494427-f550-4caf-bb6a-c0ddbafb9a5e; fact-0072-medicationrequest; prov: prov-0072-01; source: ehr-snapshot-2024:MedicationRequest/834fef49-cd6d-4dbd-bcd1-f1c94707c0f1; fact-0019-diagnosticreport; prov: prov-0019-01; source: ehr-snapshot-2024:DiagnosticReport/b53109e1-e8e0-44f3-8549-20f278a059f6; fact-0023-diagnosticreport; prov: prov-0023-01; source: ehr-snapshot-2024:DiagnosticReport/2c6ceaea-bb70-4117-89c3-f3901246c362.
5. **Allergy information is missing.** The package explicitly reports: “No allergy list facts found in packaged sources.” Source: `evidence/missing-information.json`.

**What to ask the doctor/care team**

- Please reconcile the active medication list, especially whether both Lipitor and simvastatin should be considered active/current, and whether clonidine/aspirin/Tavist are still being taken.
- Please review kidney labs, especially the creatinine/eGFR combination, because the package lacks source abnormal flags/reference ranges.
- Please reconcile the 2018 lipid duplicate/conflict values before using them clinically.
- Please confirm allergies, because no allergy list was found in the packaged sources.
- Please confirm which problems are truly active vs historical, because several imported FHIR conditions use status `accepted` rather than clear active/resolved clinical status.

## clinician-handoff

**Patient:** Adria871 Ankunding277 synthetic/demo record. **Sources:** 3 packaged sources: 2018 FHIR bundle, 2024 FHIR bundle, and CCDA problems/medications XML.

### Key conditions / problem list

| Condition | Date | Status in package | Evidence |
| --- | --- | --- | --- |
| Hypertension, essential | 2006-05-16 | active | fact-0007-condition; prov: prov-0007-01; source: extra-problems-and-medications:Condition/ccda-condition-3 |
| Cerebral artery occlusion, unspecified, with cerebral infarction | 2009-07-09 | active | fact-0008-condition; prov: prov-0008-01; source: extra-problems-and-medications:Condition/ccda-condition-1 |
| Chronic obstructive airways disease/COPD | 2007-08-12 | active | fact-0011-condition; prov: prov-0011-01; source: extra-problems-and-medications:Condition/ccda-condition-2 |
| Hyperlipidemia | 2018-03-03 | accepted | fact-0012-condition; prov: prov-0012-01; source: ehr-snapshot-2024:Condition/cbea4cdd-ec32-4a27-b619-c75f2c96bffb |
| Obesity / BMI 30+ | 2016-03-26 | accepted; cross-source matched | fact-0001-condition; prov: prov-0001-01, prov-0001-02; source: ehr-snapshot-2018:Condition/c362b137-7b43-4d62-ba11-9eab3e1b99fa; ehr-snapshot-2024:Condition/c362b137-7b43-4d62-ba11-9eab3e1b99fa |
| Reproductive history: normal pregnancy + blighted ovum/miscarriage entries | 2010 and 2018 | accepted; some cross-source matched, some 2024-only | fact-0015-condition; prov: prov-0015-01, prov-0015-02; source: ehr-snapshot-2018:Condition/6c020948-4c27-471a-81aa-d623e9dccec3; ehr-snapshot-2024:Condition/6c020948-4c27-471a-81aa-d623e9dccec3; fact-0002-condition; prov: prov-0002-01, prov-0002-02; source: ehr-snapshot-2018:Condition/b83ea5d5-8ebe-4915-adc5-5ac8534c0885; ehr-snapshot-2024:Condition/b83ea5d5-8ebe-4915-adc5-5ac8534c0885; fact-0004-condition; prov: prov-0004-01, prov-0004-02; source: ehr-snapshot-2018:Condition/d80ba0a2-b09a-4ba4-91d6-beb0945a17d4; ehr-snapshot-2024:Condition/d80ba0a2-b09a-4ba4-91d6-beb0945a17d4; fact-0005-condition; prov: prov-0005-01; source: ehr-snapshot-2024:Condition/7082bd16-5280-423e-9d21-6eeee1f9180c; fact-0016-condition; prov: prov-0016-01; source: ehr-snapshot-2024:Condition/f3ace9b8-8268-471a-95f1-5f07dd040baf |

### Active medications

| Medication | Date | Status | Evidence |
| --- | --- | --- | --- |
| clonidine | 2006-05-16 | active | fact-0068-medicationrequest; prov: prov-0068-01; source: extra-problems-and-medications:MedicationRequest/ccda-medication-10 |
| Lipitor 20 mg oral tablet | 2007-08-14 | active | fact-0075-medicationrequest; prov: prov-0075-01; source: extra-problems-and-medications:MedicationRequest/ccda-medication-7 |
| aspirin | 2009-07-15 | active | fact-0080-medicationrequest; prov: prov-0080-01; source: extra-problems-and-medications:MedicationRequest/ccda-medication-9 |
| Tavist | 2009-07-15 | active | fact-0081-medicationrequest; prov: prov-0081-01; source: extra-problems-and-medications:MedicationRequest/ccda-medication-8 |
| Simvistatin/Simvastatin 10 mg | 2019-03-24 | active | fact-0072-medicationrequest; prov: prov-0072-01; source: ehr-snapshot-2024:MedicationRequest/834fef49-cd6d-4dbd-bcd1-f1c94707c0f1 |

Medication reconciliation issue: Lipitor and simvastatin are both represented as active/current in different sources/eras; package does not resolve whether both are intended current therapies.

### Allergies

No allergy list facts found in packaged sources (`evidence/missing-information.json`).

### Recent labs / review items

- 2019-03-24 kidney/metabolic: creatinine 2.5226746533976074 mg/dL, eGFR 86.3958917280481 mL/min, BUN 18.87099499622739 mg/dL, glucose 94.72057541618341 mg/dL; no source reference ranges or abnormal flags. Evidence: fact-0134-observation; prov: prov-0134-01; source: ehr-snapshot-2024:Observation/3c1ee610-870e-4c0c-a7ff-ee7c3f90f610; fact-0132-observation; prov: prov-0132-01; source: ehr-snapshot-2024:Observation/2c412690-e04d-4a2d-bf92-de864c1dfc29; fact-0153-observation; prov: prov-0153-01; source: ehr-snapshot-2024:Observation/552dbd65-91d7-4ce6-be08-54c2c9f5a11d; fact-0113-observation; prov: prov-0113-01; source: ehr-snapshot-2024:Observation/11a14e9f-5958-4de5-908d-96d00f82c24a.
- 2019-03-24 liver: ALT 47.830397924663544 U/L, AST 17.24537289682872 U/L, alkaline phosphatase 53.005910476690865 U/L, total bilirubin 0.3773260487708747 mg/dL; no source reference ranges or abnormal flags. Evidence: fact-0085-observation; prov: prov-0085-01; source: ehr-snapshot-2024:Observation/ad318a17-722c-41ab-afd4-0937edaf0446; fact-0094-observation; prov: prov-0094-01; source: ehr-snapshot-2024:Observation/8428f97d-4411-4cb6-af01-a50c154b09ed; fact-0156-observation; prov: prov-0156-01; source: ehr-snapshot-2024:Observation/25e8f745-fe3e-4558-98ae-195a60297108; fact-0096-observation; prov: prov-0096-01; source: ehr-snapshot-2024:Observation/4ae3f0e7-fb67-44d2-8418-9f6710255bc7.
- 2018-03-03 lipid panel has same-date duplicate/conflicting values: LDL 178.2404 vs 75.6122 mg/dL, HDL 32.6149 vs 76.2482 mg/dL, total cholesterol 173.2132 vs 215.9976 mg/dL, triglycerides 106.7640 vs 203.6163 mg/dL (`evidence/conflicts.json`).

### Missing / unclear

- Allergy list absent.
- Source abnormal flags/reference ranges absent for labs.
- Active vs historical status is unclear for FHIR conditions marked `accepted`; clinician reconciliation needed.
- Duplicated 2018 lipid values require review before charting/trending.

## source-contribution

| Source | Kind | Fact count / resource counts | Main contribution | Unique vs shared |
| --- | --- | --- | --- | --- |
| `ehr-snapshot-2018.json` (`ehr-snapshot-2018`) | FHIR bundle | 91 facts: 9 conditions, 3 diagnostic reports, 21 encounters, 6 immunizations, 8 medication requests, 44 observations | Earlier longitudinal FHIR record: 2010/2014 lipid panels, 2014 CBC, 2010–2016 vitals, immunizations, contraception/short-course meds, and cross-source-matched historical conditions. | Shared condition facts with 2024 include: fact-0001 obesity, fact-0002 miscarriage, fact-0003 acute viral pharyngitis, fact-0004 blighted ovum (2010), fact-0006 chronic sinusitis, fact-0009/fact-0010 viral sinusitis, fact-0014 wrist sprain, fact-0015 normal pregnancy. Unique facts include earlier labs/immunizations/encounters and stopped medications such as medroxyprogesterone, ibuprofen, etonogestrel implant, amoxicillin/clavulanate, Levora/Camila/Errin (`evidence/source-contributions.json`). |
| `ehr-snapshot-2024.json` (`ehr-snapshot-2024`) | FHIR bundle | 106 facts: 12 conditions, 5 diagnostic reports, 9 encounters, 5 immunizations, 2 medication requests, 56 observations, 17 procedures | Newer FHIR record: 2018–2019 CMP/lipid panels, hyperlipidemia, 2018 pregnancy/blighted ovum facts, 2018–2019 immunizations, active 2019 simvastatin, and procedures. | Shares the same cross-source condition facts listed above with 2018. Unique facts include 2018/2019 CMP/lipid observations and 2018 same-date duplicate lipid values (`evidence/source-contributions.json`; `evidence/conflicts.json`). |
| `problems-and-medications.xml` (`extra-problems-and-medications`) | CCDA XML | 11 facts: 5 conditions, 6 medication requests | Problem/medication supplement: active hypertension, cerebral infarction, COPD, UTI, syncope/collapse; active clonidine, Lipitor, aspirin, Tavist; completed lisinopril entries. | All 11 facts are unique to this CCDA source; no shared fact IDs are listed in `evidence/source-contributions.json`. |

**Facts appearing in more than one source:** The structured evidence marks these conditions as cross-source matched between 2018 and 2024: obesity, miscarriage, acute viral pharyngitis, blighted ovum (2010), chronic sinusitis, viral sinusitis, wrist sprain, and normal pregnancy. Example evidence: fact-0001-condition; prov: prov-0001-01, prov-0001-02; source: ehr-snapshot-2018:Condition/c362b137-7b43-4d62-ba11-9eab3e1b99fa; ehr-snapshot-2024:Condition/c362b137-7b43-4d62-ba11-9eab3e1b99fa; fact-0006-condition; prov: prov-0006-01, prov-0006-02; source: ehr-snapshot-2018:Condition/5a12665b-c9ae-410c-9491-11c3fe4d0e92; ehr-snapshot-2024:Condition/5a12665b-c9ae-410c-9491-11c3fe4d0e92; fact-0014-condition; prov: prov-0014-01, prov-0014-02; source: ehr-snapshot-2018:Condition/c9cfc295-1e5a-4b70-99f2-5b211829e4ae; ehr-snapshot-2024:Condition/c9cfc295-1e5a-4b70-99f2-5b211829e4ae.

**Conflicts / duplicates requiring review:** Four same-concept/same-date 2018-03-03 lipid observations in the 2024 source have multiple values: LDL, HDL, total cholesterol, and triglycerides (`evidence/conflicts.json`). The source-contribution file also repeats some 2024 unique fact IDs for diagnostic reports/procedures, suggesting duplicate/linked package entries that should be interpreted carefully.

## chart-ready-labs

Reference ranges and abnormal/interpretation flags are **not source-provided** in the package FHIR observations, harmonized bundle, or `exports/labs.csv`; those columns are therefore populated as “Not source-provided.” Values are package values, rounded only by display truncation? No: values below are copied from canonical facts.

| Test name | Date | Value | Unit | Reference range | Abnormal flag | Source |
| --- | --- | ---: | --- | --- | --- | --- |
| High Density Lipoprotein Cholesterol | 2010-03-13 | 59.35814267610266 | mg/dL | Not source-provided | Not source-provided | fact-0101-observation; prov-0101-01 |
| Low Density Lipoprotein Cholesterol | 2010-03-13 | 90.43707844626245 | mg/dL | Not source-provided | Not source-provided | fact-0088-observation; prov-0088-01 |
| Total Cholesterol | 2010-03-13 | 178.66752386780138 | mg/dL | Not source-provided | Not source-provided | fact-0106-observation; prov-0106-01 |
| Triglycerides | 2010-03-13 | 144.36151372718138 | mg/dL | Not source-provided | Not source-provided | fact-0114-observation; prov-0114-01 |
| Erythrocyte distribution width [Entitic volume] by Automated count | 2014-03-22 | 40.996838287774054 | fL | Not source-provided | Not source-provided | fact-0111-observation; prov-0111-01 |
| Erythrocytes [#/volume] in Blood by Automated count | 2014-03-22 | 5.15212003096281 | 10*6/uL | Not source-provided | Not source-provided | fact-0174-observation; prov-0174-01 |
| Hematocrit [Volume Fraction] of Blood by Automated count | 2014-03-22 | 44.84743466532133 | % | Not source-provided | Not source-provided | fact-0141-observation; prov-0141-01 |
| Hemoglobin [Mass/volume] in Blood | 2014-03-22 | 13.872895313959383 | g/dL | Not source-provided | Not source-provided | fact-0157-observation; prov-0157-01 |
| High Density Lipoprotein Cholesterol | 2014-03-22 | 66.78698517537647 | mg/dL | Not source-provided | Not source-provided | fact-0102-observation; prov-0102-01 |
| Leukocytes [#/volume] in Blood by Automated count | 2014-03-22 | 9.235908928277976 | 10*3/uL | Not source-provided | Not source-provided | fact-0154-observation; prov-0154-01 |
| Low Density Lipoprotein Cholesterol | 2014-03-22 | 96.06371692255281 | mg/dL | Not source-provided | Not source-provided | fact-0089-observation; prov-0089-01 |
| MCH [Entitic mass] by Automated count | 2014-03-22 | 30.04520858177247 | pg | Not source-provided | Not source-provided | fact-0171-observation; prov-0171-01 |
| MCHC [Mass/volume] by Automated count | 2014-03-22 | 35.85690018666007 | g/dL | Not source-provided | Not source-provided | fact-0172-observation; prov-0172-01 |
| MCV [Entitic volume] by Automated count | 2014-03-22 | 83.86302445467665 | fL | Not source-provided | Not source-provided | fact-0173-observation; prov-0173-01 |
| Platelet distribution width [Entitic volume] in Blood by Automated count | 2014-03-22 | 171.84453903569235 | fL | Not source-provided | Not source-provided | fact-0129-observation; prov-0129-01 |
| Platelet mean volume [Entitic volume] in Blood by Automated count | 2014-03-22 | 12.190460348693415 | fL | Not source-provided | Not source-provided | fact-0130-observation; prov-0130-01 |
| Platelets [#/volume] in Blood by Automated count | 2014-03-22 | 355.13633930346793 | 10*3/uL | Not source-provided | Not source-provided | fact-0170-observation; prov-0170-01 |
| Total Cholesterol | 2014-03-22 | 183.1335109453303 | mg/dL | Not source-provided | Not source-provided | fact-0107-observation; prov-0107-01 |
| Triglycerides | 2014-03-22 | 101.41404423700506 | mg/dL | Not source-provided | Not source-provided | fact-0115-observation; prov-0115-01 |
| Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma | 2018-03-03 | 20.09138160449881 | U/L | Not source-provided | Not source-provided | fact-0084-observation; prov-0084-01 |
| Albumin [Mass/volume] in Serum or Plasma | 2018-03-03 | 5.045396693510592 | g/dL | Not source-provided | Not source-provided | fact-0086-observation; prov-0086-01 |
| Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma | 2018-03-03 | 60.04358430538001 | U/L | Not source-provided | Not source-provided | fact-0155-observation; prov-0155-01 |
| Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma | 2018-03-03 | 20.12304163779907 | U/L | Not source-provided | Not source-provided | fact-0093-observation; prov-0093-01 |
| Bilirubin.total [Mass/volume] in Serum or Plasma | 2018-03-03 | 0.8153070106318994 | mg/dL | Not source-provided | Not source-provided | fact-0095-observation; prov-0095-01 |
| Calcium | 2018-03-03 | 8.529772293637077 | mg/dL | Not source-provided | Not source-provided | fact-0142-observation; prov-0142-01 |
| Carbon Dioxide | 2018-03-03 | 28.698780559548467 | mmol/L | Not source-provided | Not source-provided | fact-0097-observation; prov-0097-01 |
| Chloride | 2018-03-03 | 103.13944667875408 | mmol/L | Not source-provided | Not source-provided | fact-0099-observation; prov-0099-01 |
| Creatinine | 2018-03-03 | 2.5859000002823596 | mg/dL | Not source-provided | Not source-provided | fact-0133-observation; prov-0133-01 |
| Globulin [Mass/volume] in Serum by calculation | 2018-03-03 | 2.021694066896167 | g/L | Not source-provided | Not source-provided | fact-0082-observation; prov-0082-01 |
| Glomerular filtration rate/1.73 sq M.predicted | 2018-03-03 | 85.66514138565137 | mL/min | Not source-provided | Not source-provided | fact-0131-observation; prov-0131-01 |
| Glucose | 2018-03-03 | 89.29442249634423 | mg/dL | Not source-provided | Not source-provided | fact-0112-observation; prov-0112-01 |
| High Density Lipoprotein Cholesterol | 2018-03-03 | 32.61494288140821 | mg/dL | Not source-provided | Not source-provided | fact-0103-observation; prov-0103-01 |
| High Density Lipoprotein Cholesterol | 2018-03-03 | 76.24821397637857 | mg/dL | Not source-provided | Not source-provided | fact-0104-observation; prov-0104-01 |
| Low Density Lipoprotein Cholesterol | 2018-03-03 | 178.24044090967763 | mg/dL | Not source-provided | Not source-provided | fact-0090-observation; prov-0090-01 |
| Low Density Lipoprotein Cholesterol | 2018-03-03 | 75.61217564868082 | mg/dL | Not source-provided | Not source-provided | fact-0091-observation; prov-0091-01 |
| Potassium | 2018-03-03 | 4.229915217484052 | mmol/L | Not source-provided | Not source-provided | fact-0150-observation; prov-0150-01 |
| Protein [Mass/volume] in Serum or Plasma | 2018-03-03 | 78.54736531513714 | g/dL | Not source-provided | Not source-provided | fact-0119-observation; prov-0119-01 |
| Sodium | 2018-03-03 | 137.68460615148524 | mmol/L | Not source-provided | Not source-provided | fact-0127-observation; prov-0127-01 |
| Total Cholesterol | 2018-03-03 | 173.21318495173398 | mg/dL | Not source-provided | Not source-provided | fact-0108-observation; prov-0108-01 |
| Total Cholesterol | 2018-03-03 | 215.99762005576812 | mg/dL | Not source-provided | Not source-provided | fact-0109-observation; prov-0109-01 |
| Triglycerides | 2018-03-03 | 106.76397663337295 | mg/dL | Not source-provided | Not source-provided | fact-0116-observation; prov-0116-01 |
| Triglycerides | 2018-03-03 | 203.61625319109777 | mg/dL | Not source-provided | Not source-provided | fact-0117-observation; prov-0117-01 |
| Urea Nitrogen | 2018-03-03 | 16.62541337868323 | mg/dL | Not source-provided | Not source-provided | fact-0152-observation; prov-0152-01 |
| Alanine aminotransferase [Enzymatic activity/volume] in Serum or Plasma | 2019-03-24 | 47.830397924663544 | U/L | Not source-provided | Not source-provided | fact-0085-observation; prov-0085-01 |
| Albumin [Mass/volume] in Serum or Plasma | 2019-03-24 | 5.499469774564668 | g/dL | Not source-provided | Not source-provided | fact-0087-observation; prov-0087-01 |
| Alkaline phosphatase [Enzymatic activity/volume] in Serum or Plasma | 2019-03-24 | 53.005910476690865 | U/L | Not source-provided | Not source-provided | fact-0156-observation; prov-0156-01 |
| Aspartate aminotransferase [Enzymatic activity/volume] in Serum or Plasma | 2019-03-24 | 17.24537289682872 | U/L | Not source-provided | Not source-provided | fact-0094-observation; prov-0094-01 |
| Bilirubin.total [Mass/volume] in Serum or Plasma | 2019-03-24 | 0.3773260487708747 | mg/dL | Not source-provided | Not source-provided | fact-0096-observation; prov-0096-01 |
| Calcium | 2019-03-24 | 10.041466341455358 | mg/dL | Not source-provided | Not source-provided | fact-0143-observation; prov-0143-01 |
| Carbon Dioxide | 2019-03-24 | 25.66400036348771 | mmol/L | Not source-provided | Not source-provided | fact-0098-observation; prov-0098-01 |
| Chloride | 2019-03-24 | 103.37827969691362 | mmol/L | Not source-provided | Not source-provided | fact-0100-observation; prov-0100-01 |
| Creatinine | 2019-03-24 | 2.5226746533976074 | mg/dL | Not source-provided | Not source-provided | fact-0134-observation; prov-0134-01 |
| Globulin [Mass/volume] in Serum by calculation | 2019-03-24 | 2.959164202052591 | g/L | Not source-provided | Not source-provided | fact-0083-observation; prov-0083-01 |
| Glomerular filtration rate/1.73 sq M.predicted | 2019-03-24 | 86.3958917280481 | mL/min | Not source-provided | Not source-provided | fact-0132-observation; prov-0132-01 |
| Glucose | 2019-03-24 | 94.72057541618341 | mg/dL | Not source-provided | Not source-provided | fact-0113-observation; prov-0113-01 |
| High Density Lipoprotein Cholesterol | 2019-03-24 | 54.520528147734204 | mg/dL | Not source-provided | Not source-provided | fact-0105-observation; prov-0105-01 |
| Low Density Lipoprotein Cholesterol | 2019-03-24 | 119.41047962688698 | mg/dL | Not source-provided | Not source-provided | fact-0092-observation; prov-0092-01 |
| Potassium | 2019-03-24 | 4.118546507376634 | mmol/L | Not source-provided | Not source-provided | fact-0151-observation; prov-0151-01 |
| Protein [Mass/volume] in Serum or Plasma | 2019-03-24 | 61.097150437097135 | g/dL | Not source-provided | Not source-provided | fact-0120-observation; prov-0120-01 |
| Sodium | 2019-03-24 | 137.95785158869703 | mmol/L | Not source-provided | Not source-provided | fact-0128-observation; prov-0128-01 |
| Total Cholesterol | 2019-03-24 | 176.3945040832056 | mg/dL | Not source-provided | Not source-provided | fact-0110-observation; prov-0110-01 |
| Triglycerides | 2019-03-24 | 156.27982796203796 | mg/dL | Not source-provided | Not source-provided | fact-0118-observation; prov-0118-01 |
| Urea Nitrogen | 2019-03-24 | 18.87099499622739 | mg/dL | Not source-provided | Not source-provided | fact-0153-observation; prov-0153-01 |

**Missing or not comparable labs**

- No source reference ranges or abnormal flags were provided, so abnormality cannot be charted from source evidence alone.
- Hematology/CBC data appear only on 2014-03-22 in the packaged observations; no later CBC trend is available.
- Kidney/liver/CMP values are mainly 2018 and 2019; older CMP values are not present for comparison.
- Lipid values on 2018-03-03 are not safely comparable until duplicate/conflict values are reconciled (`evidence/conflicts.json`).
- Some source units look clinically unusual (for example total protein recorded as g/dL with values 61.097 and 78.547; globulin recorded as g/L); preserve source units and have clinician/lab-system review before chart import.

## agent-audit

| Important claim | Evidence used | Support assessment |
| --- | --- | --- |
| Package is synthetic/demo and contains 3 sources, 192 canonical facts, 4 conflicts, 1 missing-information signal | `MANIFEST.json` | Supported. |
| Patient name/display is Adria871 Ankunding277 | `MANIFEST.json` | Supported. |
| No allergy list facts found | `evidence/missing-information.json` | Supported. |
| Active CCDA problems include hypertension, cerebral infarction, COPD, UTI, syncope/collapse | fact-0007-condition; prov: prov-0007-01; source: extra-problems-and-medications:Condition/ccda-condition-3; fact-0008-condition; prov: prov-0008-01; source: extra-problems-and-medications:Condition/ccda-condition-1; fact-0011-condition; prov: prov-0011-01; source: extra-problems-and-medications:Condition/ccda-condition-2; fact-0013-condition; prov: prov-0013-01; source: extra-problems-and-medications:Condition/ccda-condition-5; fact-0017-condition; prov: prov-0017-01; source: extra-problems-and-medications:Condition/ccda-condition-4 | Supported by CCDA prepared extraction. |
| Active medications include clonidine, Lipitor, aspirin, Tavist, and 2019 simvastatin | fact-0068-medicationrequest; prov: prov-0068-01; source: extra-problems-and-medications:MedicationRequest/ccda-medication-10; fact-0075-medicationrequest; prov: prov-0075-01; source: extra-problems-and-medications:MedicationRequest/ccda-medication-7; fact-0080-medicationrequest; prov: prov-0080-01; source: extra-problems-and-medications:MedicationRequest/ccda-medication-9; fact-0081-medicationrequest; prov: prov-0081-01; source: extra-problems-and-medications:MedicationRequest/ccda-medication-8; fact-0072-medicationrequest; prov: prov-0072-01; source: ehr-snapshot-2024:MedicationRequest/834fef49-cd6d-4dbd-bcd1-f1c94707c0f1 | Supported, but current medication reconciliation is unclear because sources span years and contain multiple statins. |
| Hyperlipidemia appears in the 2024 EHR snapshot | fact-0012-condition; prov: prov-0012-01; source: ehr-snapshot-2024:Condition/cbea4cdd-ec32-4a27-b619-c75f2c96bffb | Supported. |
| Obesity/BMI 30+ is cross-source matched | fact-0001-condition; prov: prov-0001-01, prov-0001-02; source: ehr-snapshot-2018:Condition/c362b137-7b43-4d62-ba11-9eab3e1b99fa; ehr-snapshot-2024:Condition/c362b137-7b43-4d62-ba11-9eab3e1b99fa | Supported. |
| Recent 2019 lipid values are total cholesterol 176.3945040832056 mg/dL, LDL 119.41047962688698 mg/dL, HDL 54.520528147734204 mg/dL, triglycerides 156.27982796203796 mg/dL | fact-0110-observation; prov: prov-0110-01; source: ehr-snapshot-2024:Observation/d290669b-b453-46ba-927b-b935338f30c6; fact-0092-observation; prov: prov-0092-01; source: ehr-snapshot-2024:Observation/9bc80bdd-63dc-4799-9fbb-8568e9f62e2f; fact-0105-observation; prov: prov-0105-01; source: ehr-snapshot-2024:Observation/39d05548-8331-4889-b4dc-372ec41d461d; fact-0118-observation; prov: prov-0118-01; source: ehr-snapshot-2024:Observation/11a9c57e-92a6-4200-9408-e7773eca6d84 | Supported. |
| Recent 2019 kidney values are creatinine 2.5226746533976074 mg/dL, eGFR 86.3958917280481 mL/min, BUN 18.87099499622739 mg/dL | fact-0134-observation; prov: prov-0134-01; source: ehr-snapshot-2024:Observation/3c1ee610-870e-4c0c-a7ff-ee7c3f90f610; fact-0132-observation; prov: prov-0132-01; source: ehr-snapshot-2024:Observation/2c412690-e04d-4a2d-bf92-de864c1dfc29; fact-0153-observation; prov: prov-0153-01; source: ehr-snapshot-2024:Observation/552dbd65-91d7-4ce6-be08-54c2c9f5a11d | Supported. Clinical abnormality is not asserted from source flags because none are present. |
| Four 2018 lipid conflicts exist | `evidence/conflicts.json`; fact IDs fact-0090/fact-0091, fact-0103/fact-0104, fact-0108/fact-0109, fact-0116/fact-0117 | Supported. |
| Reference ranges and abnormal flags are absent | Inspection of packaged FHIR observations/harmonized bundle and `exports/labs.csv` | Supported by source fields; no `referenceRange` or `interpretation` fields were present. |
| Source contribution counts and unique/shared-source statements | `evidence/source-contributions.json` | Supported. |
| “Ask doctor to reconcile meds/labs/allergies/conditions” | Derived from missing allergy signal, conflicts, multi-source med statuses, and lack of abnormal flags | Reasonable recommendation; not a source clinical fact. |
| Any definitive diagnosis of kidney disease or liver disease | Not claimed | Would be unsupported by package alone. |
