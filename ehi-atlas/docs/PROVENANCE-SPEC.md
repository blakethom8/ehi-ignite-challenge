# Provenance Specification

> The FHIR Extension URLs we mint, frozen. Anyone reading our gold-tier output (the existing app, judges, future contributors) needs this spec to interpret our Provenance machinery.

## Native FHIR mechanisms (used as-is)

We use FHIR R4's published Provenance machinery wherever possible. These are not our invention; we follow the spec.

| Field | Purpose |
|---|---|
| `Resource.meta.source` | URI of the source the resource came from (e.g. `harmonizer://merge/2026-04-29` or `epic-ehi-tsv://patient/12345`) |
| `Resource.meta.profile[]` | FHIR profile conformance (USCDI, CARIN BB, etc.) |
| `Resource.meta.tag[]` | CodeableConcepts for arbitrary tagging (source-tag, lifecycle-tag, conflict-flagged) |
| `Resource.meta.lastUpdated` + `versionId` | Version tracking |
| `Resource.identifier[]` (system + value) | Multiple source identifiers per resource (merged Patient retains all source MRNs) |
| `Provenance` resource | Standard FHIR resource: target + agent + entity + activity + recorded |

The `Provenance` resource is the load-bearing piece. Every cross-source merge emits one.

## Custom Extensions (we mint these — frozen URLs)

For things FHIR R4 does not natively cover, we use the standard `Extension` pattern. **These URLs are stable; we do not break them.**

### Extension namespace

Root: `https://ehi-atlas.example/fhir/StructureDefinition/`

(Will swap `example` for the canonical domain when we have one. For Phase 1 the URLs are stable but the domain is a placeholder. App code references them by constant in `ehi_atlas/harmonize/provenance.py`.)

### The Extensions

| URL | Type | Where | Purpose |
|---|---|---|---|
| `.../quality-score` | `valueDecimal` | on `meta` | Quality score 0-1: recency × source authority × completeness. Layer 3 emits. |
| `.../conflict-pair` | `valueReference` | on the resource | Reference to another resource this one conflicts with. Both records preserved; the extension marks the pair. |
| `.../extraction-model` | `valueCoding` | on `meta` | The model that extracted this resource from unstructured input (e.g. `claude-opus-4-7`). |
| `.../extraction-confidence` | `valueDecimal` | on `meta` | Confidence 0-1 from the extractor. Layer 2-B emits. |
| `.../extraction-prompt-version` | `valueString` | on `meta` | Frozen prompt version that produced this extraction (for reproducibility). |
| `.../source-attachment` | `valueReference` | on `meta` | Reference to the `Binary` resource the extraction came from. |
| `.../source-locator` | `valueString` | on `meta` | For PDF extractions: `page=N;bbox=x1,y1,x2,y2`. The Sources panel uses this to highlight the bounding box. |
| `.../merge-rationale` | `valueString` | on the resource | One-line explanation of why this merge happened (UMLS CUI hit, exact-match dedup, etc.). |
| `.../umls-cui` | `valueString` | on a CodeableConcept | The UMLS CUI used to bridge code systems during merge. |

### Frozen worked example

A creatinine Observation lifted from a Quest lab PDF:

```json
{
  "resourceType": "Observation",
  "code": {"coding": [{"system": "http://loinc.org", "code": "2160-0",
                       "display": "Creatinine [Mass/volume] in Serum or Plasma"}]},
  "valueQuantity": {"value": 1.4, "unit": "mg/dL", "system": "http://unitsofmeasure.org", "code": "mg/dL"},
  "effectiveDateTime": "2025-09-12",
  "subject": {"reference": "Patient/showcase-blake"},
  "meta": {
    "source": "lab-report-pdf://2025-09-12-quest.pdf",
    "profile": ["http://hl7.org/fhir/us/core/StructureDefinition/us-core-observation-lab"],
    "tag": [
      {"system": "https://ehi-atlas.example/fhir/CodeSystem/source-tag", "code": "lab-pdf"},
      {"system": "https://ehi-atlas.example/fhir/CodeSystem/lifecycle", "code": "extracted"}
    ],
    "extension": [
      {"url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-model",
       "valueCoding": {"system": "https://ehi-atlas.example/fhir/CodeSystem/llm-model",
                       "code": "claude-opus-4-7"}},
      {"url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-confidence",
       "valueDecimal": 0.97},
      {"url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-prompt-version",
       "valueString": "v0.1.2"},
      {"url": "https://ehi-atlas.example/fhir/StructureDefinition/source-attachment",
       "valueReference": {"reference": "Binary/quest-2025-09-12"}},
      {"url": "https://ehi-atlas.example/fhir/StructureDefinition/source-locator",
       "valueString": "page=2;bbox=144,302,260,318"}      // illustrative; actual showcase value is "page=2;bbox=72,574,540,590" — see _sources/synthesized-lab-pdf/README-extraction.md
    ]
  }
}
```

## Provenance resource shape

For every gold-tier resource, at least one `Provenance` resource is emitted. Standard shape:

```json
{
  "resourceType": "Provenance",
  "target": [{"reference": "Condition/harmonized-htn-blake"}],
  "recorded": "2026-04-29T14:21:00Z",
  "activity": {
    "coding": [{"system": "http://terminology.hl7.org/CodeSystem/v3-DataOperation",
                "code": "MERGE"}]
  },
  "agent": [{
    "type": {"coding": [{"system": "http://terminology.hl7.org/CodeSystem/provenance-participant-type",
                          "code": "performer"}]},
    "who": {"display": "ehi-atlas v0.1.0"}
  }],
  "entity": [
    {"role": "source", "what": {"reference": "Condition/cedars-abc123"}},
    {"role": "source", "what": {"reference": "Condition/epic-789xyz"}}
  ]
}
```

`activity` codes used:

- `MERGE` — combined N source records into one gold record
- `DERIVE` — produced this record from a single source via transformation
- `EXTRACT` — lifted this record from unstructured input (PDF, free text, etc.)
  The canonical extractor is `ehi_atlas.extract.pdf.extract_from_pdf`
  (task 4.3). It is the only runtime path that emits the extraction Extensions
  listed above (`extraction-model`, `extraction-confidence`,
  `extraction-prompt-version`, `source-attachment`, `source-locator`).
  See `ehi_atlas/extract/pdf.py` for the prompt, versioning policy, and
  cache-determinism guarantee.
- `TRANSFORM` — format conversion (CCDA → FHIR, TSV → FHIR, etc.)

## Storage layout

Provenance resources are emitted as line-delimited JSON in `corpus/gold/patients/<patient>/provenance.ndjson`. One Provenance per line; load lazily.

This is a deliberate departure from putting Provenance inside the main `bundle.json` — keeping the lineage graph in its own file lets the app load patient data fast and walk Provenance only when the user clicks "show source."

## Versioning

This spec is versioned via the `harmonizer_version` field in `manifest.json`. When this spec changes:

- Adding new Extension URLs: minor version bump, backward compatible
- Changing the meaning of an existing Extension: major version bump, breaking
- Renaming/removing Extensions: major version bump, breaking

Current spec version: **0.1.0** (2026-04-29).

## Future-stable URLs

When the canonical domain is chosen (post-Phase-1), URLs will migrate. Migration plan:

1. Mint new URLs at the canonical domain
2. Emit both old and new URLs on resources for one minor version (overlap period)
3. Update consumers (the app) to read new URLs
4. Remove old URLs in the next major version

This is the standard FHIR Extension migration pattern.
