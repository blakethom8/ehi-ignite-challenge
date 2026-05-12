# ICU MIMIC persona

**Source:** [MIMIC-IV Clinical Database Demo on FHIR v2.1.0](https://physionet.org/content/mimic-iv-fhir-demo/2.1.0/) (PhysioNet)
**Subset:** the openly downloadable 100-patient demo (no credentialing required).
**Patient picked:** `cb70e6ae-90b1-562b-8ab0-467c65d18d5e` — male, alive, 4 ICU stays (2146–2148, post-shift dates).

## Why this persona

Adds *real* (de-identified) critical-care data to the gallery so the demo isn't 100% synthetic. This patient is the densest record in the demo set and a textbook "complex surgical clearance" case:

- **Hematologic malignancy:** Chronic lymphocytic leukemia (B-cell), not in remission
- **Cardiac:** Atherosclerotic coronary artery disease, paroxysmal atrial fibrillation, cardiac pacemaker present, prior coronary angioplasty/stent
- **Anticoagulation & antiplatelet:** long-term use of both (coded explicitly in the chart)
- **Endocrine:** Type 2 diabetes with polyneuropathy, on insulin; hypothyroid
- **Neuro:** prior TIA / cerebral infarct without residual deficits
- **Pulm:** Obstructive sleep apnea
- **Other:** Bariatric surgery status, obesity, anxiety, major depressive disorder, history of testicular cancer

Exactly the kind of chart where "the right 5 facts in 30 seconds" is the whole product wedge — anticoagulation management, pacemaker/electrocautery considerations, peri-op glycemic control, OSA airway plan, active malignancy on treatment, mental-health peri-op compliance.

## What's on disk

```
icu-mimic/
├── README.md                                             ← this file
├── sources.md                                            ← per-document provenance + deliberate inconsistencies
├── mimic-iv-clinical-database-demo-on-fhir-2.1.0.zip     ← original PhysioNet zip (49 MB)
├── raw/                                                  ← unzipped distribution (full 100-patient demo)
│   ├── LICENSE.txt
│   ├── README_DEMO.md
│   ├── SHA256SUMS.txt
│   └── fhir/                                             ← 33 NDJSON.gz files (one per resource type)
├── fhir/
│   └── mimic-cb70e6ae-90b1-562b-8ab0-467c65d18d5e.json  ← assembled single-patient Bundle (47 MB)
└── documents/                                            ← synthetic multi-source docs
    ├── discharge_summary_icu.pdf
    ├── anticoag_clinic_letter.pdf
    ├── pacemaker_interrogation.pdf
    ├── sleep_study_polysomnography.pdf
    ├── preop_anesthesia_questionnaire.pdf
    ├── outside_oncology_records_ccda.xml
    ├── outside_oncology_fhir_feed.json                   ← supplemental FHIR Bundle from outside provider
    └── _cache/<name>.html                                ← raw HTML used to render each PDF
```

The single-patient Bundle is what `lib/fhir_parser` consumes. The `raw/` distribution stays alongside so you can re-slice a different patient at any time without re-downloading. The `documents/` folder simulates the multi-source experience of a real chart — see [sources.md](sources.md) for what each document represents and which inconsistencies are intentional.

## What's in the bundle

47 MB, 27,365 entries:

| Count | Resource |
|--:|---|
| 9,711 | Observation (lab events) |
| 6,843 | Observation (ICU chart events — vitals) |
| 4,108 | MedicationAdministration |
| 1,442 | MedicationRequest |
| 1,097 | MedicationDispense |
| 825 | Observation (ED vital signs) |
| 719 | SpecimenLab |
| 631 | MedicationStatement (ED) |
| 447 | Condition |
| 353 | Observation (ED) |
| 217 | MedicationDispense (ED) |
| 209 | Medication *(referenced by MedicationRequest/Administration)* |
| 165 | Procedure (ED) |
| 128 | MedicationAdministration (ICU) |
| 122 | Observation (datetime events) |
| 88 | Observation (output events — fluid balance) |
| 69 | Observation (microbiology test) |
| 60 | Specimen |
| 52 | Condition (ED) |
| 23 | Encounter (ED) |
| 20 | Encounter |
| 12 | Procedure (ICU) |
| 10 | Procedure |
| 6 | Observation (microbiology susceptibility) |
| 4 | Encounter (ICU) |
| 3 | Observation (microbiology organism) |
| 1 | Patient |

## Loading

```python
from lib.fhir_parser.bundle_parser import parse_bundle
record = parse_bundle(
    "data/demo-profiles/icu-mimic/fhir/"
    "mimic-cb70e6ae-90b1-562b-8ab0-467c65d18d5e.json"
)
```

If `lib/fhir_parser` doesn't yet recognize MIMIC's profile-specific extensions (`MimicMedicationICU`, `MimicSpecimenLab`, etc.), those resources still parse as their base FHIR types — `MedicationAdministration`, `Specimen`, etc.

## How the slice was built

The PhysioNet distribution is "all 100 patients, one NDJSON file per resource type." Our slicer streams each file, filters by `subject.reference == "Patient/cb70e6ae…"`, then does a second pass to pull in any `Medication` resources cited via `medicationReference`. Output is a FHIR R4 transaction Bundle JSON.

To pick a different patient, change `PID` at the top of the slicer and rerun. The ranking that produced this pick used a composite score weighted by:

- `50× MimicEncounterICU count` (ICU stays — the headline)
- `0.005× MimicObservationChartevents count` (vital sign density)
- `0.1× MimicMedicationAdministrationICU count`
- `0.02× MimicObservationLabevents count`
- `1× MimicProcedureICU count`
- `0.5× MimicMedicationRequest count`

Top 5 candidates from the 100-patient demo (full list in chat history):

| Patient | Sex | Alive | ICU stays | Chart events | Med Req | Score |
|---|---|---|---|---|---|---|
| **cb70e6ae** *(picked)* | M | yes | 4 | 6,843 | 1,442 | 1,174 |
| 8e77dd0b | F | yes | 3 | 29,388 | 653 | 903 |
| 77e10fd0 | F | no | 3 | 42,681 | 632 | 887 |
| 4f773083 | M | no | 1 | 19,890 | 688 | 809 |
| 8adbf3e4 | M | yes | 5 | 25,417 | 379 | 701 |

`cb70e6ae` was picked over `8adbf3e4` (5 ICU stays, alive) on the strength of medication and lab volume — the polypharmacy/peri-op narrative is more relevant to the medication-centered surgical-clearance wedge than raw ICU stay count.

## Re-fetching

```bash
curl -L -O https://physionet.org/static/published-projects/mimic-iv-fhir-demo/mimic-iv-clinical-database-demo-on-fhir-2.1.0.zip
```

## Licensing reminder

The demo subset is published under the [Open Data Commons Open Database License (ODbL) v1.0](https://opendatacommons.org/licenses/odbl/1-0/) — see `raw/LICENSE.txt`. Attribution required; redistribution permitted. The **full** MIMIC-IV-on-FHIR project (not this demo) requires PhysioNet credentialing and a separate DUA.
