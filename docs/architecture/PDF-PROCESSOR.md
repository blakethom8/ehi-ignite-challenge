# PDF Processor — Architectural Decisions

*Status: load-bearing. Read this first before touching any extraction code. Last updated: 2026-05-03.*

> **Purpose.** This is the canonical decision record for Atlas's PDF → FHIR pipeline — the architectural surface that ingests heterogeneous patient documents and emits structured, harmonization-ready FHIR R4. Captures *what we decided and why*, not the exhaustive spec. For depth on data-layer architecture see [ATLAS-DATA-MODEL.md](./ATLAS-DATA-MODEL.md).

---

## TL;DR — seven decisions

1. **Output is FHIR R4 directly, not a bespoke intermediate format.** The LLM emits FHIR-shaped JSON validated against US Core profiles. No `ExtractedClinicalNote` / `ExtractedLabReport` middle layer — those proved to be a schema-gap source rather than a flexibility win.
2. **Vision parsing is the primary path, not a fallback.** Atlas's product story is "arbitrary patient PDFs in → harmonized FHIR out" — without privileged structured-data access. Structured data (ClientFullEHR JSON, C-CDA XML) exists only as **eval ground truth** to measure how good our PDF pipeline is.
3. **Multi-pass extraction with a document-context pass.** One vision call per FHIR resource type (Conditions, Medications, Observations, Allergies, Immunizations, Procedures), preceded by a small Pass 0 that extracts document-wide metadata (patient ID, date, lab name) once for the whole PDF. Per-pass focused prompts + parallel dispatch beats one mega-prompt.
4. **Per-pass model selection.** Each pass is configured with its own backend + model. Cheap models (Gemma 4) for tabular passes; smarter models (Claude) for narrative passes. The right mix is determined by the eval harness, not by intuition.
5. **Pipelines are pluggable via a Protocol; multiple architectures coexist.** `ExtractionPipeline` is the contract: PDF in, FHIR Bundle out. Any architecture (single-pass vision, multi-pass vision, OCR-first text, hybrid) implements it. New pipelines slot in without framework changes.
6. **The eval harness is load-bearing for architecture decisions.** No "I think OCR is better" / "I think vision is better." We run a bake-off — every pipeline × every PDF × ground truth — and ship the architecture that wins on F1 / cost / latency for our actual data.
7. **The destination is cross-source harmonization, not a single-document parser.** Function Health PDFs + Cedars PDFs + future-source PDFs → per-source FHIR Bundles → deterministic merger → one canonical patient record with Provenance edges to every source. The pipeline outputs are the *inputs* to that merger.

---

## Where the PDF processor sits in Atlas

```
                                ATLAS
            ╔═══════════════════════════════════════════════╗
            ║  Layer 5 — INTERPRET                          ║
            ║  Patient Journey UI + agent panel             ║
            ╠═══════════════════════════════════════════════╣
            ║  Layer 4 — CURATE   (gold)                    ║
            ║  medication_episode, condition_active, etc.   ║
            ╠═══════════════════════════════════════════════╣
            ║  Layer 3 — HARMONIZE   (silver)               ║
            ║  Cross-source merge, Provenance edges         ║  ◀── consumes the
            ║                                               ║       PDF processor's
            ╠═══════════════════════════════════════════════╣       output
            ║  Layer 2 — STANDARDIZE   (bronze→silver)      ║
            ║                                               ║
            ║   ┌─────────────────────────────────────┐     ║
            ║   │ THIS DOC: PDF Processor             │     ║  ◀── you are here
            ║   │   PDF → multi-pass extraction       │     ║
            ║   │       → per-source FHIR Bundle      │     ║
            ║   └─────────────────────────────────────┘     ║
            ║                                               ║
            ║   Other adapters: ClientFullEHR JSON,         ║
            ║   C-CDA XML, Epic EHI TSV, etc. — same        ║
            ║   per-source FHIR Bundle output target        ║
            ╠═══════════════════════════════════════════════╣
            ║  Layer 1 — INGEST   (bronze)                  ║
            ║  Per-source raw archive                       ║
            ╚═══════════════════════════════════════════════╝
```

The PDF processor is one adapter among several at Layer 2. It produces the **same output shape** (per-source FHIR Bundle) as every other adapter. Layer 3 doesn't care which adapter produced a given Bundle — they all merge through the same harmonizer.

---

## Decision 1 — Output FHIR R4 directly

**Decision:** the LLM emits FHIR-shaped JSON validated against US Core profiles. There is no intermediate `ExtractedLabReport` / `ExtractedClinicalNote` schema between the model and the FHIR Bundle.

### Why we tried an intermediate format first (and abandoned it)

Original justification (preserved in [extract/schemas.py](../../ehi-atlas/ehi_atlas/extract/schemas.py) docstrings): *"Lets prompt authors iterate on extraction quality without touching FHIR serialization, and gives us deterministic FHIR output."*

What actually happened, measured by the eval harness:

- The intermediate schema had only `extracted_conditions` and `extracted_symptoms` for clinical notes
- Your Cedars Health Summary PDF contained 143 LOINC-coded labs, 7 RxNorm-coded medications, 10 CVX-coded immunizations, 1 allergy
- **Zero of those 161 facts were extracted** — not because the model couldn't see them, but because the schema had no slot to put them in
- The intermediate format *was* the bottleneck

Adding new fact types via field-by-field expansion (extracted_medications, extracted_allergies, ...) would solve today's gap but recreate it the moment we encounter Procedures, Vital Signs, Encounters, or any future FHIR resource type. Permanent fix: emit FHIR directly.

### What FHIR-direct looks like

```python
# Each pass returns a list of FHIR resource dicts
medications: list[FHIRResource] = await medication_pass.extract(pdf)
# [{"resourceType": "MedicationRequest", "medicationCodeableConcept": {...}, "meta": {"extension": [...]}}]

# Merger concatenates into a Bundle
bundle = Bundle(type="document", entry=[...])
```

Validation is at the boundary using US Core profiles (subset of full FHIR R4 — smaller LLM constraint surface, aligns with [ATLAS-DATA-MODEL.md](./ATLAS-DATA-MODEL.md) Decision 1).

### Bbox / Provenance preservation

The current `ExtractedLabResult.bbox` field disappears as a top-level field. Instead, every emitted FHIR resource carries a `meta.extension` entry with the source-locator string (`"page=2;bbox=72,574,540,590"`) — same shape we already use in [to_fhir.py](../../ehi-atlas/ehi_atlas/extract/to_fhir.py). No information loss.

---

## Decision 2 — Vision parsing is the primary path

**Decision:** the PDF → FHIR pipeline assumes we have **only the PDF**. Structured siblings (ClientFullEHR JSON, C-CDA XML) exist for evaluation, not as runtime inputs.

### Why this matters for the product

Atlas's positioning: *"normalize and harmonize across record types from PDFs alone."* If we route a source through its structured sibling whenever one exists, we're building a routing engine for privileged data formats — not a record-harmonization platform.

The Cedars JSON exists because Blake happens to have SMART portal access to Cedars-Sinai. Most patients don't. Most providers don't ship structured exports. The pipeline that earns Atlas's product story is the one that turns a Quest lab PDF and an Epic chart PDF and a CCDA-rendered Health Summary PDF into the same canonical FHIR Bundle without needing a backdoor.

### Where structured sources do contribute

**Eval ground truth.** Blake's `cedars-sinai.json` (from Josh Mandel's Health Skillz SMART pull) is the answer key for the Health Summary PDF. The eval harness compares our PDF extraction's output to the ground-truth Bundle and reports F1 per resource type. This is the only way we know whether the pipeline is good.

```
PDF (input) ────→ Pipeline ────→ FHIR Bundle (output)
                                       │
                                       ▼
                                  Eval Harness ◀──── ClientFullEHR JSON
                                       │             (ground truth, when available)
                                       ▼
                                  per-resource F1
```

When ground truth doesn't exist (Function Health, novel sources), eval falls back to human review via the Streamlit PDF Lab.

---

## Decision 3 — Multi-pass extraction

**Decision:** instead of one mega-prompt that asks the LLM to extract everything at once, dispatch one focused pass per FHIR resource type, preceded by a Pass 0 that extracts document-wide metadata.

### The architecture

```
PDF
 │
 ▼
[Pass 0: Document Context Extractor]
 Extracts ONCE per PDF: patient name, DOB, encounter date, lab name,
 ordering provider, document type. Returns small JSON header.
 │
 ▼
[Per-resource passes — parallel via asyncio]
  ├─ Conditions Pass    → list[Condition]
  ├─ Medications Pass   → list[MedicationRequest]
  ├─ Observations Pass  → list[Observation]   (labs, vitals)
  ├─ Allergies Pass     → list[AllergyIntolerance]
  ├─ Immunizations Pass → list[Immunization]
  └─ Procedures Pass    → list[Procedure]
 │
 ▼
[Merger]
 Concatenate into FHIR Bundle. Apply bbox calibration via pdfplumber
 layout (existing _calibrate_bboxes_via_layout). Validate against
 US Core profiles. Cache.
 │
 ▼
FHIR Bundle (per-source)
```

### Why multi-pass beats single-pass

Three reasons, all observed in our data:

1. **Multi-task prompts underperform single-task prompts.** When asked to "extract Conditions and Symptoms" simultaneously, the model emitted 3/28 conditions on the Health Summary PDF (recall = 0.11) while also handling Symptoms. Focused prompts have less to balance.

2. **Schema constraints can be tighter per pass.** A medication-only pass uses just the `MedicationRequest` profile schema — small LLM surface, no chance of confusion with Condition fields. The single-pass approach has to use a discriminated-union schema that's larger and easier to mis-fill.

3. **Parallel dispatch hides latency.** Six 20-second passes via `asyncio.gather()` finish in ~25s wall-clock. Single-pass would be ~30s for the equivalent fact volume. Latency budget mostly goes to the slowest pass, not the sum.

### Why Pass 0 (document context) is necessary

Cross-page context. Long PDFs have headers on page 1 ("Patient: Blake Thomson, Collected 2024-08-06, Quest Diagnostics") that don't repeat. Per-resource extractors processing page 7 need that context attached to every emitted resource. Pass 0 captures it once, every other pass receives it as system-prompt context.

This is the cleanest fix for the cross-page-table problem (table starts on page 3, continues to page 11) — the per-resource passes don't need to reconstruct the table, they just need to know which patient/date/lab to attribute each row to.

---

## Decision 4 — Per-pass model selection

**Decision:** each pass declares its backend + model. Tabular passes (labs, immunizations) default to cheap models (Gemma 4); narrative passes (conditions, allergies that may include free-text reaction descriptions) default to capable models (Claude).

### How this enables the agentic vision

Once each pass is a focused single-task call with its own schema slice, "use a sub-agent for this task" reduces to "select a different model for this pass." The infrastructure is already there — we have `VisionBackend` Protocol with both `AnthropicBackend` and `GoogleAIStudioBackend` implementations. Adding `OllamaBackend` for local Gemma is ~150 lines.

```python
PASSES = [
    ExtractionPass("doc_context", backend="anthropic",              model="claude-haiku-4-5"),
    ExtractionPass("conditions",  backend="anthropic",              model="claude-opus-4-7"),
    ExtractionPass("medications", backend="gemma-google-ai-studio", model="gemma-4-31b-it"),
    ExtractionPass("observations", backend="gemma-google-ai-studio", model="gemma-4-31b-it"),
    ExtractionPass("immunizations", backend="gemma-google-ai-studio", model="gemma-4-31b-it"),
    ExtractionPass("allergies",   backend="anthropic",              model="claude-opus-4-7"),
    ExtractionPass("procedures",  backend="gemma-google-ai-studio", model="gemma-4-31b-it"),
]
```

### How model selection per pass is decided

Eval harness. The bake-off framework (Decision 5) runs each candidate pipeline through every PDF × ground truth. Per-pass model swaps are just configuration changes; we run the same eval and compare F1, cost, latency. The data picks.

---

## Decision 5 — Pipelines are pluggable; multiple architectures coexist

**Decision:** the pipeline abstraction is a Protocol. Any architecture that takes a PDF and emits a FHIR Bundle is a valid pipeline. The framework supports running multiple in parallel and comparing outputs.

### The contract

```python
class ExtractionPipeline(Protocol):
    name: str
    description: str

    def extract(self, pdf_path: Path) -> dict:
        """Returns a FHIR Bundle (R4 / US Core profiled) as a dict."""
        ...
```

Every pipeline implements this. Internal architecture is opaque — single-pass vision, multi-pass vision, OCR-first text, hybrid, anything else. The eval harness operates on Bundles, so any pipeline that emits a valid Bundle plugs in immediately.

### Initial pipeline candidates

Three pipelines built first to validate the framework:

| Pipeline | What it does | Why |
|---|---|---|
| `SinglePassVisionPipeline` | Wraps the current code — one Claude call → Bundle | Baseline. Cheapest to wire. |
| `MultiPassFHIRPipeline` | Document-context pass + N per-resource passes, all vision-LLM, parallel | Tests Decisions 1-4 |
| `OCRThenExtractPipeline` | MinerU/Mistral OCR → cached markdown → text-LLM per resource type, parallel | Tests cheap-at-scale hypothesis |

After these three, a fourth (someone's hybrid? a paper-based approach? a different OCR vendor?) is one more file in `lib/extract/pipelines/`.

### Why this matters beyond Atlas

Three downstream payoffs:

1. **External agent contributions.** A clean Protocol + a documented contract + the eval harness as the judge means a Cursor / Codex / Aider session can implement a new pipeline against a stable interface without understanding our codebase. They submit; we run bake-off; data decides.
2. **Future model adoption.** When Gemma 5 lands or someone publishes a better OCR model, integrating it is one pipeline implementation away.
3. **Empirical decision-making.** No more architectural debates resolved by intuition — we measure.

---

## Decision 6 — Eval harness is load-bearing

**Decision:** [`ehi_atlas.extract.eval`](../../ehi-atlas/ehi_atlas/extract/eval.py) is the trusted authority on pipeline quality. Architecture decisions are made by running the eval, not by argument.

### What the eval measures

For a (pipeline × PDF × ground-truth) triple:

- **Per FHIR resource type** (Condition, Medication, Allergy, Immunization, Lab Observation):
  - Precision: of facts the pipeline emitted, how many are real?
  - Recall: of facts in the ground truth, how many did the pipeline catch?
  - F1: harmonic mean
- **Schema gap detector**: any resource type where ground truth has facts but the pipeline produced none — flagged as architectural failure
- **Vision-wins**: facts the pipeline extracted that aren't in ground truth — flagged for human review (notes often contain valid findings the structured FHIR doesn't code)

Matching is a two-stage cascade:
1. Exact code match across all terminologies in either record (ICD-10, SNOMED, RxNorm, LOINC, CVX). All-codes-considered.
2. Fuzzy display match by Jaccard token overlap (default threshold 0.5).

This is intentionally not a clinical-synonymy matcher (no embeddings, no LLM judge). The simple cascade catches exact codes and obvious display matches; everything else is honestly classified as a miss.

### What the eval does NOT do

- It is **not a clinical correctness check**. Two extracted facts with matching LOINC codes are scored as agreement even if the values differ. (Value-level checks are a future addition.)
- It is **not a Bundle validator**. Pipelines that emit invalid FHIR fail before reaching the eval; eval only sees Bundles that already passed US Core validation.
- It does **not handle clinical synonymy** like "hyperlipidemia" ↔ "high cholesterol" without a shared code. Workable today; upgradeable to embeddings later.

---

## Decision 7 — Cross-source harmonization is the destination

**Decision:** the per-source Bundle is *not* the end of the road. The harmonizer ([Layer 3](./ATLAS-DATA-MODEL.md) per the data-model decision record) consumes per-source Bundles from every adapter (PDF processor, JSON adapter, C-CDA adapter) and produces one canonical patient Bundle with Provenance edges to every contributing source.

### What this means for the PDF processor

Two implications:

1. **Patient identity is normalized in Pass 0.** The document-context pass returns a `subject` reference (patient name, DOB, MRN if present). Multiple PDFs from the same patient must produce subject references that the harmonizer can recognize as the same patient. We follow the [USCDI Patient Demographics + Identifier](https://www.healthit.gov/isa/uscdi-data-class/patient-demographics) shape so the harmonizer's identity-resolution module (Fellegi-Sunter or similar) can match.

2. **Provenance is mandatory, not optional.** Every emitted FHIR resource carries `meta.source` (the source PDF path or hash) and `meta.extension` (extraction-model, extraction-confidence, source-locator with bbox). The harmonizer uses these to construct the `Provenance` graph linking gold facts back through silver to bronze. Without them, the wedge ([per ATLAS-DATA-MODEL.md decision 5](./ATLAS-DATA-MODEL.md)) collapses.

### The harmonization story end-to-end

```
Function Health 2024-07-29 PDF ──→ pipeline ──→ Bundle (FH-source)  ─┐
Function Health 2025-11-29 PDF ──→ pipeline ──→ Bundle (FH-source)  ─┤
Cedars Health Summary PDF      ──→ pipeline ──→ Bundle (Cedars)     ─┼─→ Harmonizer
Cedars Requested Record PDF    ──→ pipeline ──→ Bundle (Cedars)     ─┤      │
                                                                     ─┘      │
                                                                              ▼
                                                             Canonical Patient Bundle
                                                              + Provenance.ndjson
                                                                (gold tier)
```

A canonical fact like "Glucose 102 mg/dL on 2024-08-06" might have Provenance edges to:

- `MedicationRequest/abc123` from FH 2024-07-29 PDF, page=4, bbox=72,508,540,524
- `Observation/xyz456` from Cedars Health Summary PDF, page=12, bbox=72,612,540,628

The UI surfaces this lineage. Click any fact → see every source that attested to it.

---

## What we deliberately don't build

- **A custom common data model.** FHIR R4 + US Core. See [ATLAS-DATA-MODEL.md decision 1](./ATLAS-DATA-MODEL.md).
- **A runtime LLM-as-database** that generates queries on the fly. The pipeline produces a fixed FHIR Bundle; queries hit that bundle deterministically.
- **A pure chat agent** (the agent panel sits on top of the harmonized Bundle, doesn't replace it).
- **A schema validator that's stricter than US Core.** We don't invent additional clinical constraints — let US Core's profile validators do that work.
- **A clinical synonymy matcher** in the eval (yet). The exact-code + fuzzy-display cascade is the v1 floor.
- **An OCR engine.** When OCR is needed, we wrap an existing one (MinerU, Marker, olmOCR, Mistral OCR API) — we do not build our own.
- **A pre-OCR document classification step** (medical record vs receipt vs photo). Out of scope. Caller must hand us a medical PDF.

---

## Phase plan

```
K.1   ExtractionPipeline Protocol + registry
      Define the contract; write contributor README so external agents
      can implement against it cold.
      ~2 hours.

K.2   SinglePassVisionPipeline (adapter over current code)
      Establishes the baseline. Validates the Protocol works.
      ~1 hour.

K.3   bake_off() comparison harness + Streamlit Pipeline Bakeoff page
      Pipeline × PDF matrix with F1/cost/latency/error cells.
      Reads from the Protocol; doesn't know about specific pipelines.
      ~3-4 hours.

K.4   MultiPassFHIRPipeline implementation
      Document-context pass + N per-resource passes. Parallel dispatch.
      Per-pass model configuration via ExtractionPass dataclass.
      ~4-5 hours.

K.5   OCRThenExtractPipeline implementation
      MinerU local OR Mistral OCR API → markdown cache → text-LLM
      per-resource passes. Tests cheap-at-scale hypothesis.
      ~3-4 hours.

K.6   First bake-off run: 3 pipelines × Blake's PDFs
      Generate the comparison report. THIS is when we make the
      architecture decision — with data, not opinion.
      ~2 hours.

K.7   Final docs pass:
        - This file updated with bake-off result
        - lib/extract/pipelines/README.md polished
        - Decision-log entry summarizing the winning architecture
      ~2 hours.
```

Total: ~17-20 hours. Output: multiple working pipelines + an empirical comparison + a framework that survives future model and approach changes.

---

## First bake-off result — 2026-05-03

`single-pass-vision` (baseline, current ExtractionResult-shaped path) vs
`multipass-fhir` (Decisions 1–4 implementation) on Blake's Cedars Health
Summary PDF (25 pages, 189 ground-truth facts in the ClientFullEHR JSON):

| pipeline | weighted F1 | latency | bundle entries |
|---|---:|---:|---:|
| `single-pass-vision` | **0.03** | 1.3s (cache hit) | 3 |
| `multipass-fhir`     | **0.64** | 93.7s            | 156 |

Per-resource breakdown for `multipass-fhir`:

| type | ground truth | extracted | precision | recall | F1 |
|---|---:|---:|---:|---:|---:|
| condition    |  28 |   3 | 1.00 | 0.11 | 0.19 |
| medication   |   7 |   6 | 1.00 | 0.86 | **0.92** |
| allergy      |   1 |   1 | 1.00 | 1.00 | **1.00** |
| immunization |  10 |   8 | 1.00 | 0.80 | **0.89** |
| lab          | 143 | 138 | 0.71 | 0.69 | 0.70 |

**Findings.**

1. **The architecture hypothesis holds.** Schema-direct multi-pass
   produced a **21× weighted-F1 improvement** over the bespoke
   intermediate format on the same PDF — driven entirely by closing
   the schema gaps in Decisions 1 + 3. Medications, allergies,
   immunizations went from `SCHEMA GAP — 0/N` to F1 ≥ 0.89.
2. **Conditions stayed at 0.11 recall on both pipelines** — same model,
   same prompt baseline, same input. This is **not a schema-gap finding;
   it's a prompt-quality finding for the conditions pass specifically**.
   Health Summary PDFs decompose conditions across visit-section
   subheadings ("Active Problems," "Past Medical History,"
   "Reason for Visit"); the conditions prompt needs to nudge the model
   toward all of those.
3. **Lab precision is 0.71, not 1.00.** The 40 false-positives are the
   "vision wins or hallucinations" bucket. Manual review pending; some
   are likely real findings the FHIR Bundle doesn't code (textual lab
   mentions in clinical notes that never become coded Observations
   server-side).
4. **Cost trade is real.** Multi-pass costs ~$0.30 per 25-page PDF
   vs ~$0.05 baseline. F1 0.64 vs 0.03 is worth it; per-pass downgrade
   to Gemma 4 (per Decision 4) is the natural next experiment to
   reduce cost without surrendering quality.

**Decisions made:**
- `multipass-fhir` is the new default architecture for the PDF processor.
- `single-pass-vision` retained as a baseline + regression detector.
- Next investigation: prompt tuning for the conditions pass (target:
  push condition recall above 0.6 on the same PDF).
- Next experiment: per-pass model swap for the high-volume tabular
  passes (medications, immunizations, lab observations) to Gemma 4 —
  measure F1 + cost + latency delta.

---

## Open questions

These are not blockers; they're decisions we'll revisit as data accumulates.

- **Should we add an OCR fallback to MultiPassFHIRPipeline?** If a page fails vision extraction (token limits, content filter), should we OCR-then-text that page rather than fail? Decision deferred until we see failure modes in production.
- **Per-pass page filtering?** If Pass 0 detects "no medication section in this PDF," should we skip the medications pass entirely? Cost optimization. Decision deferred.
- **Bundle validation strictness.** US Core has many profiles; we'll subset. Which exact profiles ship in v1? TBD when we wire the validator.
- **Caching granularity.** Today the cache is keyed on the whole PDF + prompt + schema + model. With multi-pass, each pass has its own cache key. Reasonable, but creates many small cache entries — rotation strategy TBD.

---

## Cross-references

| For depth on... | Read |
|---|---|
| Data model: FHIR R4 + USCDI as silver/gold target | [ATLAS-DATA-MODEL.md](./ATLAS-DATA-MODEL.md) |
| LLM context engineering (5-layer pipeline) | [CONTEXT-ENGINEERING.md](./CONTEXT-ENGINEERING.md) |
| Data definitions reference | [DATA-DEFINITIONS.md](./DATA-DEFINITIONS.md) |
| Eval harness implementation | [ehi-atlas/ehi_atlas/extract/eval.py](../../ehi-atlas/ehi_atlas/extract/eval.py) |
| Backend abstraction (VisionBackend Protocol) | [ehi-atlas/ehi_atlas/extract/pdf.py](../../ehi-atlas/ehi_atlas/extract/pdf.py) |
| Pipeline contributor guide (after K.1 lands) | `ehi-atlas/ehi_atlas/extract/pipelines/README.md` |
| Existing PDF Lab Streamlit page | [ehi-atlas/app/pages/03_PDF_Lab.py](../../ehi-atlas/app/pages/03_PDF_Lab.py) |
| Existing PDF Compare Streamlit page | [ehi-atlas/app/pages/04_PDF_Compare.py](../../ehi-atlas/app/pages/04_PDF_Compare.py) |

---

## What changes when this doc changes

- **New pipeline architecture introduced** → add to Decision 5's table + Phase K.4-K.6 list, log bake-off result.
- **FHIR target changes** (it shouldn't easily) → update Decision 1, notify Layer 3 harmonizer.
- **Eval harness gains new metrics** → update Decision 6, regenerate any cited bake-off numbers.
- **New ground-truth source acquired** (real-EHR FHIR snapshot, Mistral OCR-evaluated) → update Decision 2's eval-source enumeration.
- Always preserve the central commitment from Decision 2: **PDF is the primary input, structured siblings are eval ground truth**. If you find yourself drifting toward "let's just use the JSON," stop and re-read.
