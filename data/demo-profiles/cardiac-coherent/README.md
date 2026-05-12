# Cardiac — Coherent Data Set (Brady998 Hickle134)

**Source:** [Synthea Coherent Data Set](https://registry.opendata.aws/synthea-coherent-data/) (AWS Open Data, CC-BY-4.0)
**Patient stem:** `Brady998_Hickle134_fec6d99f-1cfd-f397-e740-e3952410ea2a`
**Reference:** Walonoski et al., "The Coherent Data Set: Combining Patient Data and Imaging in a Comprehensive, Synthetic Health Record," *Electronics* 2022.

## Why this persona

The only freely-redistributable patient record that ships **structured FHIR + DICOM imaging + a DNA file + free-text SOAP notes in one bundle**. Lets the platform demonstrate cross-modal stitching (chart → imaging study → genome → notes), which Synthea alone can't.

Brady998 is also a textbook surgical-clearance worry: cardiac arrest survivor on amiodarone, post-stroke, on warfarin-equivalent anticoagulation chain, with active prostate cancer on chemo. Exactly the patient where "the right 5 facts in 30 seconds" matters.

## Patient at a glance

- Male, DOB 1914-11-27 (died in chart, age ~96)
- **Cardiac/vascular:** Coronary Heart Disease, Cardiac Arrest, History of cardiac arrest, Stroke, Silent micro-hemorrhage of brain
- **Renal:** Chronic kidney disease stage 1, Diabetic renal disease
- **Endocrine/metabolic:** Diabetes, Hyperglycemia, Hypertriglyceridemia, Metabolic syndrome X, Prediabetes, Obesity
- **Oncology:** Prostate carcinoma in situ → Neoplasm of prostate (on Leuprolide + Docetaxel)
- **Other:** Alcoholism, Anemia, Osteoarthritis of hip, Polyp of colon, Monoparesis - arm

## What's in the FHIR bundle (`fhir/<stem>.json`, ~35 MB)

| Resource | Count |
|---|---|
| Observation | 4,950 |
| Claim | 3,119 |
| MedicationRequest | 2,096 |
| DiagnosticReport | 1,294 |
| Encounter | 1,023 |
| DocumentReference | 1,023 |
| ExplanationOfBenefit | 1,023 |
| Procedure | 654 |
| Condition | 28 |
| Immunization | 11 |
| CareTeam, CarePlan | 16 |
| ImagingStudy, Media, Device, Provenance, MedicationAdministration | 5 |
| Patient | 1 |

**Total entries: 15,244** — this is the densest patient in the gallery and a fair stress test for any chart-summarization pipeline.

## Multimodal artefacts (`imaging/`, `genomics/`)

| File | Size | What it is |
|---|---|---|
| `imaging/Brady998_…dcm` | 33 MB | Cardiac MRI DICOM (referenced from the FHIR `ImagingStudy` resource). The platform does NOT parse this — it sits as an opaque source-of-record artefact, with the human-readable read provided as `documents/cardiac_mri_report.pdf`. |
| `genomics/Brady998_…_dna.csv` | 23 KB | Simulated genome variants from the Coherent data set. Also opaque — included to demonstrate the platform handles genomic-data attachment without trying to interpret it. |

## Re-fetching

```bash
BASE=https://synthea-open-data.s3.amazonaws.com/coherent/unzipped
PATIENT=Brady998_Hickle134_fec6d99f-1cfd-f397-e740-e3952410ea2a

curl -L -o "fhir/${PATIENT}.json"        "${BASE}/fhir/${PATIENT}.json"
curl -L -o "imaging/${PATIENT}.dcm"      "${BASE}/dicom/${PATIENT}1.2.840.99999999.64484254.723245133887.dcm"
curl -L -o "genomics/${PATIENT}_dna.csv" "${BASE}/dna/${PATIENT}_dna.csv"
```

## Synthetic multi-source documents

`documents/` holds six LLM-generated documents simulating the disparate sources Brady998's chart would actually come from:

- 5 PDFs (cardiology post-arrest consult, stroke discharge, prostate pathology, oncology chemo plan, cardiac MRI radiology read)
- **1 FHIR R4 Bundle** (`pacemaker_telemetry_fhir.json`) — 6 months of Medtronic CareLink device-generated Observations (AT/AF burden, % pacing, lead impedance, battery)

Three deliberate inconsistencies are baked in — chemo dosing frequency (narrative vs structured), AF burden (quantitative trend vs qualitative diagnosis), and RV pacing (telemetry shows 38% vs the in-office interrogation PDF's 4%, a temporal version conflict). See [sources.md](sources.md) for per-document detail.

## Loading

```python
from lib.fhir_parser.bundle_parser import parse_bundle
record = parse_bundle(
    "data/demo-profiles/cardiac-coherent/fhir/"
    "Brady998_Hickle134_fec6d99f-1cfd-f397-e740-e3952410ea2a.json"
)
```

The DICOM and DNA files don't yet have loaders — wire those up when the imaging / genomics surfaces of the app come online.
