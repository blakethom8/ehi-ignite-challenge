# Harmonization Worked Example — HDL Cholesterol

A single concrete walkthrough of Atlas's harmonization layer, using
Blake's two real sources (Cedars-Sinai FHIR pull + Function Health PDF
extractions). Read alongside [`ATLAS-DATA-MODEL.md`](ATLAS-DATA-MODEL.md)
for the strategic framing and `lib/harmonize/` for the implementation.

> **Status:** v1, May 2026. Vertical slice on Observations only.
> Conditions, Medications, Allergies, Immunizations follow the same
> shape and are not yet implemented.

## The fact

**HDL Cholesterol** — a marker of cardiovascular risk. Higher is generally
better; below 40 mg/dL in men is a flag.

## Inputs (two heterogeneous sources)

### Source A — Cedars-Sinai (FHIR pull via Health Skillz)

Pulled 2025-11-07 via the Cedars patient portal, materialized as a
Health-Skillz envelope (`providers[] × fhir{} × attachments[]`). The
Cedars FHIR server emits Observations with full LOINC coding:

```json
{
  "resourceType": "Observation",
  "code": {
    "coding": [
      {
        "system": "http://loinc.org",
        "code": "2085-9",
        "display": "HDL Cholesterol"
      }
    ],
    "text": "HDL Cholesterol"
  },
  "valueQuantity": {"value": 67, "unit": "mg/dL"},
  "effectiveDateTime": "2025-11-07T00:00:00Z"
}
```

Source path: `corpus/bronze/clinical-portfolios/blake_records/cedars-healthskillz-download/health-records.json`.

### Source B — Function Health (Quest lab PDF, 2024-07-29)

A 17-page Quest lab report, surfaced via Function Health's portal, downloaded
as a PDF. Run through the multi-pass FHIR extraction pipeline
(`ehi_atlas/extract/pipelines/multipass_fhir.py`), which produces FHIR
Observations directly — but with **text labels only, no LOINC codes**, because
Quest's printed reports don't include LOINC alongside the lab name:

```json
{
  "resourceType": "Observation",
  "code": {
    "text": "HDL Cholesterol"
  },
  "valueQuantity": {"value": 81, "unit": "mg/dL"},
  "effectiveDateTime": "2024-07-29T00:00:00Z",
  "meta": {
    "source": "extracted://lab-report/bt_functionhealth_7-29-2024"
  }
}
```

Source path: `corpus/bronze/clinical-portfolios/blake_records/blake_function_pdfs/extracted-2024-07-29.json`.

## The harmonization step

`lib.harmonize.merge_observations` walks both sources and produces one
canonical `MergedObservation` for HDL:

1. **Identity resolution.** Cedars contributes LOINC `2085-9` directly. Function
   Health contributes only the text label `"HDL Cholesterol"`. The bridge
   (`lib.harmonize.loinc_bridge`) normalizes the label
   (`"HDL Cholesterol"` → `"hdl cholesterol"`) and looks it up — finding LOINC
   `2085-9`. Both sources collapse onto the same canonical identity.
2. **Unit normalization.** Both sources report `mg/dL`, so no conversion fires.
   (If Function Health had reported in `mmol/L`, the matcher would multiply by
   38.67 and tag the edge with activity `unit-normalize`.)
3. **Longitudinal assembly.** The matcher attaches both source observations
   to the merged record, sorted oldest-first.
4. **Provenance minting.** `lib.harmonize.mint_provenance` produces one FHIR
   Provenance resource with two `entity` entries — one per source — each
   stamped with Atlas extension URLs (`source-label`, `harmonize-activity`).

## The merged record

```text
canonical_name = "HDL Cholesterol [Mass/volume] in Serum or Plasma"
loinc_code     = "2085-9"
canonical_unit = "mg/dL"

sources = [
  ObservationSource(
    source_label = "Function Health",
    value = 81,  unit = "mg/dL",
    effective_date = 2024-07-29,
    document_reference = "DocumentReference/extracted-2024-07-29",
  ),
  ObservationSource(
    source_label = "Cedars-Sinai",
    value = 67,  unit = "mg/dL",
    effective_date = 2025-11-07,
    document_reference = "DocumentReference/cedars-healthskillz-2025-11-07",
  ),
]
```

The clinical signal — invisible if you only look at one source — is **HDL
dropped from 81 → 67 mg/dL over 16 months**. That's the harmonization wedge:
a longitudinal trajectory across heterogeneous sources, not a snapshot from one.

## The Provenance resource

```json
{
  "resourceType": "Provenance",
  "target": [{"reference": "Observation/merged-loinc-2085-9"}],
  "recorded": "2026-05-03T22:14:34",
  "activity": {
    "coding": [
      {
        "system": "http://atlas.healthcaredataai.com/fhir/CodeSystem/harmonize-activity",
        "code": "loinc-match",
        "display": "Loinc Match"
      }
    ]
  },
  "agent": [
    {
      "type": {
        "coding": [
          {
            "system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
            "code": "assembler"
          }
        ]
      },
      "who": {"display": "EHI Atlas Harmonizer v1"}
    }
  ],
  "entity": [
    {
      "role": "source",
      "what": {"reference": "Observation/function-health-0"},
      "extension": [
        {"url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-label",
         "valueString": "Function Health"},
        {"url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/harmonize-activity",
         "valueString": "name-match"}
      ]
    },
    {
      "role": "source",
      "what": {"reference": "Observation/cedars-sinai-67"},
      "extension": [
        {"url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-label",
         "valueString": "Cedars-Sinai"},
        {"url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/harmonize-activity",
         "valueString": "loinc-match"}
      ]
    }
  ]
}
```

The `activity` rolls up to `loinc-match` (the strongest evidence type across
edges); the per-edge `harmonize-activity` extensions preserve the granular
story (the Cedars edge fired on a direct LOINC match; the Function Health
edge fired through the name bridge).

## What this demonstrates for the Phase 1 reviewer

- **Multi-format ingestion works.** A native FHIR pull and a vision-extracted
  PDF both feed the same canonical record without writing per-source
  custom code.
- **Identity resolution survives missing codes.** Even when one source omits
  LOINC, the bridge resolves the fact onto the canonical identity instead
  of producing two unmerged duplicates.
- **Provenance is first-class.** Every fact in the canonical record links
  back to the source observation, the source document, and the harmonization
  step that produced the edge. That's the lineage pane the clinician UI and
  the agent assistant read to render explainability.
- **Longitudinal change is visible.** The thing a clinician needs to see
  (HDL trajectory) is the thing the harmonized view emits — not buried in a
  pile of per-source bundles.

## Beyond v1

- **More resource types.** Conditions, Medications, Allergies, Immunizations
  follow the same shape. Each gets its own match strategy (Conditions: SNOMED
  + ICD-10 cross-walk; Medications: RxNorm + drug-class fallback;
  Immunizations: CVX + date proximity).
- **Conflict detection.** `MergedObservation.has_conflict` flags same-day
  cross-source disagreement >10%. The richer version surfaces *which* sources
  disagree, by *how much*, and *why* (units? reference range? methodology?).
- **Bridge expansion.** The hand-curated name→LOINC dict covers the ~50
  most-common labs across Blake's sources today. Scaling to the long tail
  is an LLM-bootstrapped crosswalk job mirroring `lib/sql_on_fhir/`
  enrichments — not v1.
- **Bidirectional Provenance walk.** From a fact, walk back to source
  documents (already shipped). From a source document, walk forward to every
  fact it produced (one query, not yet wired into the UI).
