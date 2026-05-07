# Blake Function Health Lab (11/19/2025) — Parser Comparison

Source PDF: `inputs/function-lab-results-11-19-2025.pdf` — 5 pages, Quest Diagnostics-West Hills, ordered by Joshua A Emdur D.O., collected 2025-11-19, reported 2025-11-21. Tests: CMP, urinalysis, CBC w/ diff, hs-CRP, insulin, A1c, ApoB.

## Critical HAR-reading correction

Initial read of the HAR was misleading. The **polling endpoint** `GET /api/v1/medical-docs/parsed/pending?format=list` (called 26 times) returned only the user's older Cedars-Sinai IgE allergen panel (doc `1778176673093541`, status `parsed`, 83 biomarkers) because the new upload was still in `parsing` status during all 26 polls.

The actual Function Health output for **our** PDF (the Quest 11/19/2025 lab, doc `1778178825031939`) lives in a single response: `GET /api/v1/medical-docs/parsed/1778178825031939` at HAR entry [118] (13,479 bytes). That's the correct comparator.

**Lesson for HAR analysis going forward:** Function Health uses a list+detail pattern. The list endpoint surfaces metadata; the detail endpoint surfaces parsed biomarkers. Don't trust the list response as the parsed output.

## Side-by-side metadata

| Field | Function Health | Ours |
|---|---|---|
| Provider | `Quest` ✅ | `Quest Diagnostics-West Hills` ✅ |
| Lab name | `Quest Diagnostics-West Hills` ✅ | (same as provider) ✅ |
| Lab ID / Accession | `ZD789742H` ✅ | not captured ❌ |
| Collection date | `2025-11-19T18:13:00Z` ✅ | not captured separately ❌ |
| Report date | `2025-11-21T02:19:00Z` ✅ | `encounter_date: "2025-11-21"` ⚠️ (only this one) |
| Received date | `2025-11-21T02:21:00Z` ✅ | not captured ❌ |
| Patient name | not captured ❌ | `Blake Thomson` ✅ |
| Patient DOB | not captured ❌ | `1993-06-16` ✅ |
| Ordering provider | not captured ❌ | `Joshua A Emdur, D.O.` ✅ |
| Document type | `blood` ✅ (auto-classified) | `lab-report` ✅ |
| Document summary | full paragraph ✅ | not generated ❌ |
| Suggested questions | 5 patient-friendly questions ✅ | not generated ❌ |

**Verdict on metadata:** different fields captured, but each gets the things they capture correct. We have stronger patient identity + ordering provider; FH has stronger lab/source identity + multiple distinct dates. **No false data on either side.**

## Test coverage

Name-by-name diff (synonym-aware: BUN ↔ Blood Urea Nitrogen, etc.):

| | Count |
|---|---|
| FH biomarkers extracted | **57** |
| Ours Observations extracted | **58** |
| Tests both parsers got | **57** |
| FH-only | 0 |
| Ours-only | 1 — `BUN/Creatinine Ratio` (FH missed it) |

**Verdict on coverage:** parity. Both parsers extracted essentially the same tests. We caught one extra (BUN/Cr ratio). Neither parser missed anything substantive.

## Per-resource enrichment

This is where the gap is real and concrete:

| Field | FH (out of 57) | Ours (out of 58) |
|---|---:|---:|
| Numeric value | 100% | 100% |
| Unit | 100% (where applicable) | 100% (where applicable) |
| **LOINC code** | **38 (67%)** | **0 (0%)** ❌ |
| **SNOMED code** | **38 (67%)** | **0 (0%)** ❌ |
| Reference range | ~100% | 37 (63%) |
| **In-range / out-of-range flag** | ~100% | **3 (5%)** ❌ |
| **Clinical category** (Metabolic/Kidney/Liver/etc.) | 100% | 0% (only generic FHIR `laboratory`) ❌ |

**Verdict on enrichment:** FH wins decisively. Three concrete gaps in our parser:

1. **No code resolution.** We extract names like "Glucose" but don't resolve to LOINC `2345-7`. FH resolves both LOINC + SNOMED.
2. **No interpretation flag.** Even when we have both value and reference range, we don't compute whether the value is in/out of range. FH does this for nearly everything.
3. **No clinical category.** FH groups tests into clinically meaningful buckets (Metabolic, Kidney, Liver, Blood, Immune Regulation, Heart, Urine). We use only the FHIR `observation-category=laboratory` — useful for FHIR, useless for clinical UI.

## Display-name normalization

FH consistently expands abbreviations to full + abbreviated form:

| Ours | Function Health |
|---|---|
| `eGFR` | `Estimated Glomerular Filtration Rate (eGFR)` |
| `AST` | `Aspartate Transaminase (AST)` |
| `ALT` | `Alanine Transaminase (ALT)` |
| `Alkaline Phosphatase` | `Alkaline Phosphatase (ALP)` |
| `MCV` | `Mean Corpuscular Volume (MCV)` |
| `MCH` | `Mean Corpuscular Hemoglobin (MCH)` |
| `MCHC` | `Mean Corpuscular Hemoglobin Concentration (MCHC)` |
| `RDW` | `Red Cell Distribution Width (RDW)` |
| `MPV` | `Mean Platelet Volume (MPV)` |
| `WBC` (count) | `White Blood Cell (WBC) Count` |
| `RBC` (count) | `Red Blood Cell (RBC) Count` |
| `Hemoglobin A1c` | `Hemoglobin A1c (HbA1c)` |
| `Apolipoprotein B` | `Apolipoprotein B (ApoB)` |
| `hs CRP` | `High-Sensitivity C-Reactive Protein (hs-CRP)` |

This normalization isn't just cosmetic — it's almost certainly what enables their LOINC matching. Full names map cleanly to LOINC display strings; bare abbreviations don't. The two issues (display-name normalization + LOINC) are coupled.

## Pass-0 / document-context comparison

Both parsers have a per-document context layer.

**Ours** (`meta.extension[document-context]`):
```json
{
  "document_type": "lab-report",
  "patient_name": "Blake Thomson",
  "patient_dob": "1993-06-16",
  "encounter_date": "2025-11-21",
  "ordering_provider": "Joshua A Emdur, D.O.",
  "facility_name": "Quest Diagnostics-West Hills"
}
```

**Function Health** (`content` top-level):
```json
{
  "docLanguage": "en",
  "provider": "Quest",
  "labName": "Quest Diagnostics-West Hills",
  "labId": "ZD789742H",
  "dates": {"collectionDate": "...", "reportDate": "...", "receivedDate": "..."},
  "summary": "...",
  "questions": [...]
}
```

Same idea, different schema. **FH adds two patient-facing layers we don't have:** a written summary and a list of patient-friendly questions. Worth considering for our Clinical Insights surface.

## What this comparison tells us

1. **Our extraction quality is comparable on test names + values.** This was the worry going in — we're not behind on the core extraction job.
2. **The wedge "vision LLM beats structured EHR" is real and visible here.** Both parsers extracted from a vision-encoded PDF. Both got 57 tests. FH's parser is doing additional work *post-extraction* (code resolution, interpretation, categorization) — but the underlying vision task is comparable.
3. **The biggest defensible deficit is code resolution (LOINC + SNOMED).** Not an extraction problem — a normalization problem. Solvable without re-architecting.
4. **The second defensible deficit is interpretation + clinical category.** Both are computed fields that need a small post-extraction pass.
5. **FH does NOT capture ordering provider or patient identity** — we do better there. That matters for cross-source harmonization (which patient does this lab belong to?).

## Deepening priorities surfaced (concrete tasks)

Tying back to `docs/daily/2026-05-07-ClaudeCode.md` Entry 2 P1 list:

### NEW · Add a code-resolution post-pass to multipass-fhir
For each Observation, lookup the display name (with normalization to expanded form) against a LOINC table. Two implementation paths:

- **Local table.** ~3500 LOINC codes for common labs; pre-built lookup. No external dependency. Fast. Limited to known labs.
- **External API.** RxNav-style endpoint or a clinical NLP API. Broader coverage, network cost, possible BAA needs.

Recommend local table first (one prompt → JSON dump from FHIR Terminology Server), API as fallback. This single change closes the largest gap.

### NEW · Add an interpretation pass
For each Observation with both `valueQuantity` and `referenceRange`, compute `interpretation: H | L | N | A`. Trivial — just numeric comparison. Maps to `http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation`. No LLM needed.

### NEW · Add a clinical-category extension
Add a non-FHIR-required extension `https://ehi-atlas.example/fhir/StructureDefinition/clinical-category` with values like `Metabolic`, `Kidney`, `Liver`, `Blood`, etc. Either:
- **LLM pass** (expensive but flexible — same prompt structure as existing passes)
- **Rule-based** (cheap — drive from LOINC code → category mapping)

Recommend rule-based after the LOINC post-pass lands; the LOINC code is a strong signal for category.

### NEW · Capture both collection AND report dates explicitly
PDF clearly distinguishes. We're collapsing to one. Update Pass-0 prompt to extract a date object, not a single date. Per-Observation `effectiveDateTime` should be the collection time, not the report time.

### NEW · Patient-friendly summary + questions pass
Optional. After extraction, run a final pass on the bundle to generate a 2-3 sentence summary + 5 patient-friendly questions. Useful for the Clinical Insights surface. Same shape as FH's `summary` + `questions` fields.

### Existing P0 task confirmed
The format detector / vision-wins reviewer / conditions prompt v4 priorities from Entry 2 stand. This comparison adds **code-resolution post-pass** as a new P0/P1 candidate — likely larger F1 impact than the conditions prompt fix.

## Next steps awaiting user

- [ ] Decide whether to implement code-resolution as a builder task now, or wait for PDF-LAB-STUDIO to ship and bake-off the alternatives
- [ ] Confirm the patient-summary + questions pass is in scope (it's UX-adjacent)
- [ ] Share another PDF? (Cedars MyHealth, Function Health on a different patient, etc.) to see if these conclusions hold across sources

---

## Working session log

### 2026-05-07 — Initial comparison
- Verified both parsers correctly identified the document
- Found the misleading polling-endpoint trap; corrected to using `/parsed/{id}` detail endpoint
- 57 of 57 tests extracted by both; ours +1 BUN/Cr ratio
- Top three deficits: LOINC, interpretation flag, clinical category
- Recommended new P1 tasks: code-resolution post-pass, interpretation post-pass, category extension
