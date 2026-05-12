# Demo Profiles

A curated set of patient personas used for demos, evals, and screenshots. Each persona is a **multi-source chart**: a structured FHIR Bundle as ground truth, plus a small fan of synthetic source documents (PDFs, C-CDA XML, and supplemental FHIR Bundles from outside systems) that simulate the messy real-world experience of records arriving from different hospitals, clinics, labs, patient-tracking apps, implanted devices, and home-monitoring platforms. A handful of deliberate inconsistencies between sources is baked in per persona — those are exactly the moments the platform's reconciliation/harmonization features are supposed to surface.

## The roster

| Slot | Persona | Source | What it shows off |
|---|---|---|---|
| `icu-mimic/` | `cb70e6ae…` male, alive, 4 ICU stays — CLL + AFib + pacemaker + T2DM + OSA + prior TIA | MIMIC-IV-FHIR Demo (PhysioNet) | Real (de-identified) critical-care data — 27K entries, 6.8K ICU chartevents, 9.7K labs, 1.4K med requests |
| `oncology-breast-mcode/` | Jenny M, 55F, breast cancer | HL7 mCODE IG examples | Structured oncology: cancer staging, biomarkers, FamilyMemberHistory, Specimen, chemo regimen |
| `cardiac-coherent/` | Brady998 Hickle134, ~96M, cardiac arrest + stroke + prostate ca | Synthea Coherent Data Set | Multimodal: 35 MB FHIR + DICOM MRI + DNA + 1023 SOAP-style notes |
| `polypharmacy-synthea/` | Ester635 Echevarría842, 99F, A-fib + Alzheimer's + colorectal | Existing Synthea corpus | Anticoagulation + dementia + FOLFOX chemo — surgical-clearance archetype |
| *reserve slot* | TBD | — | Possible: pediatric / pregnancy / mental health |

## Why these four

The medication-centered surgical chart-review wedge (see `CLAUDE.md`) needs personas where the platform actually has something useful to say. Each persona has a distinct "what would the surgeon want to know in 30 seconds?" answer:

- **Jenny M** — what cancer? what stage? what biomarkers? what regimen is she on right now?
- **Brady998** — survived a cardiac arrest, currently on amiodarone + anticoagulation, also on chemo (leuprolide + docetaxel for prostate cancer). Surgical clearance is non-trivial.
- **Ester635** — A-fib on warfarin, Alzheimer's on galantamine, colorectal cancer on FOLFOX. Bleeding risk + cognitive consent capacity + chemo-induced cytopenia all matter.
- **cb70e6ae (MIMIC)** — active CLL + paroxysmal AFib on dual antithrombotic + pacemaker + T2DM on insulin + OSA + prior TIA. Every peri-op concern in one chart, with real ICU-event density behind it.

## What's committed

Everything in this directory is tracked by git, including the heavy Coherent multimodal artefacts (FHIR + DICOM + DNA) and the Synthea bundle. This keeps the gallery reproducible across machines without a separate fetch step.

The `icu-mimic/` slot ships empty — drop a MIMIC patient export into `icu-mimic/fhir/` and commit it alongside the rest. Verify the PhysioNet MIMIC DUA permits redistribution before pushing real MIMIC data to a public remote.

Re-fetch commands for the original Coherent source are kept in each persona README for reference.

## Adding the 5th persona

Drop a new subdirectory here, follow the `fhir/` layout, add a per-persona README explaining provenance + the "what would the surgeon want to know" angle, then update this table.

## Standard layout per persona

```
<persona>/
├── README.md          ← persona overview + clinical narrative
├── sources.md         ← which documents come from where + deliberate inconsistencies
├── fhir/              ← structured ground truth (FHIR R4 Bundle JSON)
├── documents/         ← synthetic source documents
│   ├── *.pdf          ← narrative documents (discharge summary, consult letter, path report, ...)
│   ├── *.xml          ← C-CDA Continuity of Care documents from outside providers
│   ├── *.json         ← supplemental FHIR R4 Bundles from outside systems (specialty clinic, device telemetry, patient app, home monitoring)
│   └── _cache/        ← raw HTML used to render each PDF
├── imaging/           ← opaque DICOM / image files  (cardiac-coherent only)
├── genomics/          ← opaque DNA files            (cardiac-coherent only)
└── raw/               ← original distribution before slicing  (icu-mimic only)
```

## Document formats per persona

| Persona | PDFs | C-CDA XML | Supplemental FHIR |
|---|:-:|:-:|---|
| `icu-mimic` (cb70e6ae) | 5 | 1 | Dana-Farber outside hematology FHIR feed |
| `oncology-breast-mcode` (Jenny M) | 4 | 1 | OncoLife patient symptom-tracker FHIR feed |
| `cardiac-coherent` (Brady998) | 5 | — | Medtronic CareLink pacemaker telemetry FHIR feed |
| `polypharmacy-synthea` (Ester635) | 4 | 1 | Lively Care home-monitoring (BP+glucose) FHIR feed |

The supplemental FHIR Bundles use `Bundle.type = "collection"` (outside data feeds, not in-house transactions) and carry resources from a *different* identifier system than the in-house bundle — forcing the platform to do cross-source identity matching, code-system reconciliation, and temporal version resolution.

## Loading these in code

All four personas ship at least one FHIR R4 Bundle JSON at `<persona>/fhir/*.json`, which is the same shape `lib/fhir_parser` already consumes:

```python
from lib.fhir_parser.bundle_parser import parse_bundle
record = parse_bundle("data/demo-profiles/cardiac-coherent/fhir/Brady998_Hickle134_*.json")
```

No new loader needed for the FHIR side. The synthetic documents in `documents/` are flat PDF / XML files — surface them through the same document-ingestion path as any other PDF the platform handles. Non-FHIR modalities (DICOM, DNA, MIMIC NDJSON-per-resource) get their own loaders as they're wired up.

## Synthesizing the documents

The `documents/` artefacts are LLM-grounded outputs from `scripts/synthesize_documents.py`. The script reads each persona's FHIR Bundle as ground truth, then asks Claude to draft each document in the voice and shape of a specific source (hospital discharge, anticoag clinic, pacemaker EP lab, etc.). Deliberate inconsistencies are passed in as explicit directives in the per-document spec.

To regenerate:

```bash
uv run python scripts/synthesize_documents.py                       # all four personas
uv run python scripts/synthesize_documents.py --persona icu-mimic   # one persona
uv run python scripts/synthesize_documents.py --persona icu-mimic --doc discharge_summary_icu --force
```

Documents already present are skipped unless `--force` is set. Source HTML for each rendered PDF is cached alongside it at `documents/_cache/<name>.html` for inspection and quick re-rendering.

## Provenance + licensing

| Source | License | Citation |
|---|---|---|
| mCODE IG examples | CC0 (HL7) | hl7.org/fhir/us/mcode |
| Coherent Data Set | CC-BY-4.0 | Walonoski et al., *Electronics* 2022 — synthea-open-data on AWS |
| Synthea Synthetic Mass | Apache 2.0 | synthea.mitre.org |
| MIMIC-IV-FHIR demo | PhysioNet Open DUA — verify before public-facing demos | physionet.org/content/mimic-iv-fhir-demo |
