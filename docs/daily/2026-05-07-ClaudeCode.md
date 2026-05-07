# Claude Code Working Log — 2026-05-07

> Claude Code workspace. Separate from `2026-05-07.md` (the human review log). This file captures architecture / strategy thinking that comes out of design conversations — what's strong, what's weak, what to build next, and why. Append-only with date-stamped entries.

---

## Entry 1 — Aggregation layer review + PDF parser deepen plan

Conversation thread: deeper review of the upfront data aggregation layer. Strategic question — is what we have today strong? Then: how should we deepen it, and what does an agentic upgrade to the PDF parser look like?

### Aggregation layer — current state

#### What's strong

- **PDF → FHIR (multipass-fhir).** Vision-primary, no privileged-format backdoor. One focused pass per FHIR resource type, parallel dispatch via thread pool, per-pass model selection, deterministic SHA-keyed cache. Bake-off harness measures it: weighted F1 0.70 on Cedars Health Summary — medications 0.92, allergies 1.00, immunizations 0.88, labs 0.70. Decisions documented in `docs/architecture/PDF-PROCESSOR.md`.
- **FHIR JSON pass-through.** Cedars JSON, Synthea bundles, SMART-pulled bundles flow to harmonization unchanged. Spec P0 — done.
- **Per-source Bundle abstraction with provenance.** Every adapter outputs the same shape (FHIR Bundle with `meta.source` + `meta.extension` for source locator + bbox). The harmonizer is adapter-agnostic.
- **Pluggable `ExtractionPipeline` Protocol + bake-off harness.** New architectures (OCR-first, agentic, future Gemma-tabular) slot in without framework changes; F1/cost/latency decides what wins.

#### What's weak

1. **Format coverage is shallow.** `docs/ideas/FORMAT-AGNOSTIC-INGESTION.md` lists 8 formats. Two are implemented (PDF, FHIR JSON). C-CDA / CCD XML, HL7 v2, free-text clinical notes, CSV/Excel, OCR-fallback for scanned PDFs, proprietary EHR exports — all stubbed. Upload accepts them and stores them with `parse_status = "stored, parser planned"`.
2. **There is no format detector module.** Spec opens with `core/format_detector.py` as Component #1. It does not exist. Format dispatch is ad-hoc inside `_with_processing_state()` (`api/core/aggregation.py:197-235`) and is **extension-based only** — no MIME sniff, no JSON-shape validation that a `.json` is actually a FHIR Bundle. A malformed JSON silently routes downstream and fails in harmonization.
3. **Free-text / clinical notes are second-class.** Notes flow through only when embedded in `DocumentReference` / `Composition` / `DiagnosticReport.presentedForm`. No "paste a discharge summary" path; no `.txt` extraction; no LLM-NER on raw narrative.
4. **No explicit OCR fallback.** Vision LLM handles many scanned PDFs in practice, but if vision extraction fails on a page (token limits, content filter), there is no OCR-then-text retry. Open question in `PDF-PROCESSOR.md`.
5. **Conditions extraction at F1 0.35.** Weakest resource type by a wide margin. Not a coverage gap, a quality gap. `PIPELINE-LOG.md` Move H "Next" lists prompt v4 targeting Z/R/S codes; not yet shipped.
6. **Doc/code drift.** `CLAUDE.md` describes `ehi-atlas/ehi_atlas/{adapters,extract,harmonize}`. Only `extract/` exists. The 5-layer scaffold was archived. The docs describe a richer aggregation layer than the code currently provides.

### Strategic call — deepen, not widen

Two paths:

- **Widen** — add C-CDA, free-text, HL7 v2, CSV; close the spec gap.
- **Deepen** — lift conditions F1, ship OCR fallback, ship the format detector, ship the vision-wins reviewer, expand bake-off beyond Cedars.

Pick: **deepen first**, then widen on one or two formats most likely to come up in judging (C-CDA + a real free-text-paste path).

Reasoning:

- The wedge — *"vision extraction recovers facts the structured EHR missed"* — is what `PDF-PROCESSOR.md` already calls "the Atlas wedge in concrete, measurable form." Widening doesn't strengthen the wedge; depth does.
- The eval harness is only honest for formats that have ground truth. Adding C-CDA / HL7 without ground truth ships code we can't measure.
- The judge story scales better with depth than breadth: "we beat the structured EHR by 4 conditions and 41 labs the structured record never coded" beats "we kind of handle 8 formats."

### Is FHIR usable for us?

Strategic question raised today. Short answer: **yes, but with a permissive bronze tier.**

- **FHIR R4 + US Core is the right interop target.** Everything downstream — harmonizer, SQL-on-FHIR warehouse, Clinical Insights agent, Provenance graph — assumes FHIR. Changing the target breaks four systems.
- **At the extraction boundary, be permissive.** Today a resource that fails US Core profile validation is silently dropped. Better: land it in a `draft` / `pending-review` state with the validation error attached, so a human can rescue borderline findings instead of losing them.
- **Narrative findings without a code should still emit.** Use `Observation` / `Condition` with `code.text` only. We already see this on the IgE allergen panel — Cedars FHIR codes them as `code.text="class"` with no shared LOINC, and our matcher honestly flags it as a miss. The right answer is text + a normalization queue, not exclusion.
- **Bronze always preserves native shape.** Original file goes into a `DocumentReference` with `content.attachment.url` pointing at the stored upload, regardless of whether extraction succeeds. We can always re-extract later; we cannot recover an unstored file.
- **Patient ad-hoc situations** — photo of a pill bottle, handwritten note, half-faxed page, screenshot of a portal, obsolete CCDA — get the same path: store as `DocumentReference`, attempt extraction, never block on extraction failure. Today the pipeline drops things it can't classify; that's a Phase 1 fix.

### Improvement plan — deepen the PDF parser

#### P0 — next 1-2 sessions
1. **Format detector module.** `lib/extract/format_detector.py` (or `api/core/`). MIME sniff + content-shape validation: is the JSON actually a FHIR Bundle? is the PDF text-layer or scanned? Replace the extension-based dispatch in `_with_processing_state()`. ~half-day.
2. **Vision-wins reviewer.** Streamlit/React page that surfaces the 4 condition + 41 lab "FPs" from the Cedars bake-off. Human classifies each as `valid_extra` / `hallucination` / `out_of_scope`; verdict persisted; eval harness recomputes "human-adjusted F1." Moves the wedge story from anecdote to measured. ~1 day.
3. **Conditions prompt v4.** F1 0.35. Targets: Z/R/S codes, conditions implied by procedures, encounter-reason → condition extraction. Currently parked in `PIPELINE-LOG.md` Move H "Next." ~half-day + bake-off run.

#### P1 — next 1-2 weeks
4. **Agentic refactor of multipass-fhir** (see next section).
5. **Permissive validation boundary.** Resources that fail US Core land in a `draft` state instead of being dropped.
6. **Expand bake-off corpus beyond Cedars.** Function Health 2024-07-29 + 2025-11-29 PDFs already in the corpus. Generate ground truth where structured siblings exist; otherwise human-graded review. Without this, we are tuning to one PDF.

#### P2 — later
7. **OCR fallback** for vision-extraction page failures. Wrap MinerU or Mistral OCR; do not build our own.
8. **Free-text paste path.** New endpoint accepting raw text + document-type hint, runs a "narrative pass," emits `Observation` / `Condition` / `MedicationRequest` with `code.text` only.
9. **C-CDA adapter.** XML → FHIR using the same per-source Bundle output target.

---

## Agentic architecture for the PDF parser

### Today — pipeline-style

- Pass 0 extracts document context once (patient, date, lab, doc type).
- Per-resource passes (Conditions, Medications, Observations, Allergies, Immunizations, Procedures) each issue a single vision call; parallel via threadpool.
- Each pass returns `list[FHIRResource]` from one LLM call.
- Merger concatenates into a Bundle; US Core validation at the boundary.

This works. The proposal below is an upgrade, not a rewrite.

### Why upgrade

Three failure modes the current pipeline cannot handle:

1. **Code resolution.** The vision model is decent at "this looks like lisinopril" but bad at "RxNorm code for lisinopril is 29046." Forcing it to emit codes pushes hallucination upstream of validation.
2. **Validation retries.** A resource that fails US Core today is dropped. There's no "look again" / "fix this field" path.
3. **Cross-resource consistency.** A medication start date before the patient's DOB is impossible. Today nothing catches it — the merger is deterministic.

### Proposed agentic architecture

Each per-resource pass becomes an **agent** instead of a single LLM call. The agent has a tool surface and a budget (e.g., max 5 tool calls per pass).

#### Tool surface

| Tool | Purpose |
|---|---|
| `lookup_rxnorm(name, dose?, form?)` | Drug name → RxNorm code via RxNav |
| `lookup_loinc(test_name, units?, specimen?)` | Test name → LOINC |
| `lookup_icd10(condition_text)` | Condition phrase → ICD-10 |
| `lookup_cvx(vaccine_name)` | Vaccine name → CVX |
| `lookup_snomed(term)` | Clinical term → SNOMED |
| `examine_page(page_num, region?, zoom?)` | Re-examine a page region — same vision backend, different framing |
| `request_ocr(page_num)` | Force-OCR a page when vision is failing |
| `cross_reference_doc_context(field)` | Pull from Pass 0 (patient ID, encounter date, lab name) |
| `validate_resource(resource)` | Run US Core profile validator, return errors |
| `flag_for_human_review(resource, reason)` | Escalate when confidence is low or validation fails after retries |

The first five (code-resolution tools) are the highest-leverage — they convert a hallucination problem into a deterministic API lookup.

#### Pass data structure

```python
@dataclass
class PassResult:
    resource_type: str
    resources: list[FHIRResource]              # validated, ready for Bundle
    candidates: list[CandidateResource]        # extracted but failed validation; needs review
    trace: list[ToolCall]                      # ordered tool-call log for replay/debug
    cost: TokenUsage
    confidence_per_resource: dict[str, float]
```

`CandidateResource` keeps the raw extraction + validation errors + bbox/page provenance, so a reviewer can rescue it without re-extracting.

#### Control flow

1. Pass 0 (doc context) runs first — single call, populates a shared context object.
2. Per-resource agents run in parallel. Each can call tools up to its budget. On validation failure, the agent retries (up to N) before flagging for review.
3. Optional **Reviewer agent** runs over the merged Bundle and flags inconsistencies (med start before DOB; allergy ↔ medication conflicts; conditions implied by procedures but not coded).
4. Merger is deterministic, as today; provenance preserved per resource.

#### What this buys us

- **Precision up.** Code resolution moves from LLM emit to deterministic API lookup. Hallucinated codes go away.
- **Recall up.** Validation failures become retries instead of drops. The "draft state" recovery story is built-in.
- **Cross-resource consistency.** Reviewer agent catches a class of errors the deterministic merger misses.
- **Debuggability.** Tool-call trace per pass = full replay + a stronger eval-harness story ("here's the tool sequence that led to this extraction").

#### What this risks

- **Latency.** Tool calls serialize within an agent. Medications pass with 5 RxNorm lookups: 20s → 40s.
- **Cost.** More tokens (tool calls + retries).
- **Complexity.** Current pipeline is ~200 lines per pass; an agent is ~500 + the tool surface + the validator + the lookup clients.

#### Mitigation

Keep `multipass-fhir` as the default. Add `multipass-fhir-agentic` as a parallel pipeline behind the same Protocol. Bake-off decides. **Do conditions first** — it's the weakest at F1 0.35 and the highest-leverage place to test the agentic upgrade.

---

## How other groups solve this

### Generic PDF / document AI (not clinical)
- **Marker, MinerU, olmOCR, Mistral OCR API** — PDF → Markdown / structured text. Strong on layout, weak on clinical structuring. Used as preprocessing layers, not endpoints.
- **AWS Textract, Google Document AI, Azure Form Recognizer** — generic key-value + table. Healthcare-aware variants exist, but entity-focused, not Bundle-focused.

### Clinical NLP — entity extraction
- **AWS Comprehend Medical** — extracts medications, conditions, anatomy, PHI. Returns entities, not FHIR. Customer assembles the Bundle.
- **Google Cloud Healthcare NLP API** — entities + FHIR-like links, no Bundle assembly.
- **Azure Text Analytics for Health** — entities + UMLS linking. Same gap.
- **Common pattern:** entity extraction is solved; FHIR Bundle assembly with provenance is left as an exercise to the integrator.

### Health record aggregators
- **Particle Health, 1upHealth, Health Gorilla** — handle real FHIR feeds via SMART / TEFCA / Carequality. Mostly *don't* extract from PDFs; they query networks for structured records and return what they get.
- **Datavant / Ciox Health** — record retrieval companies. Handle the messy stuff (faxes, paper, PDFs) but their structuring is for medical-coding workflows (chart abstraction for payers / clinical trials), not patient-facing FHIR.
- **Carta Healthcare, AirCover** — abstraction-as-a-service. Humans + LLMs extract structured data from charts for registries and trials.

### Clinical scribe / live capture
- **Abridge, Suki, Nabla, Augmedix** — different problem (live audio → structured note). But the structured-output discipline (HPI, A&P, plan as discrete fields) is the same idea applied to a different input modality.

### Autonomous medical coding
- **Nym Health** — PDF / EHR notes → ICD-10 / CPT codes. Mature structured-output system. Output is codes for billing, not a FHIR Bundle, but the rigor on accuracy + provenance is comparable. The closest commercial analog to what we're building.

### Academic / open
- **CheXagent, MedAlpaca, MEDITRON, BioGPT** — generative clinical models. Good at narrative summarization, weak on structured extraction with provenance.
- **OpenAI Structured Outputs + vision** — recent academic work shows direct FHIR-shaped JSON extraction works. Atlas's `multipass-fhir` is in this lineage.

### Where Atlas fits

I cannot find a publicly available system that ships **"PDF → FHIR R4 Bundle with provenance + bbox locators + bake-off-measured F1."** The pieces exist (vision LLMs, structured outputs, eval harnesses, FHIR validators) but the integration is bespoke per-team.

The differentiator framing — **"a PDF parser specific for FHIR formats, designed for cross-source harmonization"** — is correct and underused. Most parsers stop at Markdown. We stop at validated FHIR with provenance edges back to page+bbox. That's a narrower output target with much stronger downstream guarantees: the harmonizer consumes Atlas output without reshaping; the agent panel cites back to a specific PDF region; the SQL-on-FHIR warehouse queries a typed schema.

---

## Open questions / decisions parked

- Format detector before or after the agentic refactor? **Lean: format detector first.** ~1 day, unblocks everything else, low risk.
- Agentic refactor end-to-end, or just for the conditions pass first? **Lean: conditions-first as a proof.** F1 0.35 is the weakest pass and the highest-leverage place to measure whether agentic helps.
- Add a Reviewer agent now or skip until we measure cross-resource error rate? **Lean: skip until we have data.**
- C-CDA — when? After deepen, or never? **Open.** Depends on whether Phase 1 judges weight format breadth.

---

## Entry 2 — Directory promotion + drift cleanup (decided 2026-05-07)

### Decision

Move forward with **Option B**: promote `lib/extract/` → `lib/extract/` to fix the inverted dependency model where `api/core/harmonize_service.py` imports from the "dev zone." This sequences **before** P1 (agentic refactor), because the agentic work will land in this code and we want one move, not two.

### Task: PROMOTE-EXTRACT

**Type:** refactor (no functional change). **Scope:**

- `git mv lib/extract lib/extract`
- Update import in `api/core/harmonize_service.py` (~line 1814): `from lib.extract.pipelines` → `from lib.extract.pipelines`
- Update any Streamlit pages in `ehi-atlas/app/` that import from extract
- Update path references in `docs/architecture/PDF-PROCESSOR.md` (multiple `../../lib/extract/...` links throughout)
- Update `ehi-atlas/CLAUDE.md` so it no longer claims `extract/` lives in this zone
- Update root `CLAUDE.md`:
  - line 152: replace `(adapters/extract/harmonize)` with the corrected description
  - `lib/` section: add `lib/extract/` with description (PDF→FHIR pipelines, eval harness)
- Update `lib/README.md` to include the new extract package
- Run `uv run pytest api/tests/ -q` and `uv run pytest lib/tests/ -q` to confirm no import breaks
- Cache directory `.cache/` moves with the package (gitignored, no git churn)

**Acceptance:**
- All tests pass
- `grep -r "from lib.extract" .` returns zero hits outside `archive/`
- `grep -r "from lib.extract" .` returns at least the harmonize_service.py site
- Root CLAUDE.md no longer implies `adapters/` and `harmonize/` are live siblings of extract under `ehi_atlas/`

**Why this is safe:** pure import-path refactor; no behavior change. Tests verify the wiring. Single focused commit.

**Dispatchable to:** phase1-builder (or the daily-orchestrator pattern once we set it up).

### Follow-up: broader drift audit (in flight)

Three subagents dispatched in parallel to surface other quick fixes:
1. **CLAUDE.md vs live tree** — stale TODOs, missing files, misrepresented directories
2. **Cross-zone imports** — other instances of api/ or lib/ importing from ehi-atlas/
3. **Architecture doc cross-references** — rotted paths in `docs/architecture/*.md`

Findings will land here as Entry 3.

---

## Entry 3 — Drift audit findings (2026-05-07)

Three subagents (CLAUDE.md vs tree, cross-zone imports, architecture-doc cross-refs) returned. Filtered for false positives (one agent flagged the PODCAST doc as missing, but CLAUDE.md correctly notes it's on a feature branch — not drift). What remains, by severity:

### HIGH — would actually mislead a fresh reader or subagent

| # | Location | Claim | Reality | Proposed task |
|---|---|---|---|---|
| 1 | Root `CLAUDE.md` line 55 | Routers: `patients, safety, timeline, search, corpus, traces` | Actual: `aggregation, assistant, canonical, classifications, corpus, cursor_internal_tools, harmonize, patient_context, patients, skills, traces` (no `safety`, no `timeline`, no `search`) | CLAUDE-MD-RESYNC |
| 2 | Root `CLAUDE.md` line 76 | `app/src/pages/PatientJourney/` | Actual dir is `app/src/pages/Journey/` | CLAUDE-MD-RESYNC |
| 3 | Root `CLAUDE.md` lines 132–141, 277, 286 | `ideas/PATIENT-JOURNEY-APP.md`, `ideas/FORMAT-AGNOSTIC-INGESTION.md`, `ideas/PODCAST-INSIGHTS-...` | Directory is `docs/ideas/`. 4+ broken paths. | CLAUDE-MD-RESYNC |
| 4 | Root `CLAUDE.md` line 152 | `ehi_atlas/ ← (adapters/extract/harmonize)` | Only `extract/` exists | covered by PROMOTE-EXTRACT |
| 5 | Root `CLAUDE.md` line 68 | `context_builder.py ← TODO` | File exists, ~400 lines, has tests at `api/tests/test_context_builder.py` | CLAUDE-MD-RESYNC |
| 6 | Root `CLAUDE.md` line ~131 + Reference Docs table | `CONTEXT-PIPELINE.md ← LLM context engineering (TODO)` | File exists, 271 lines | CLAUDE-MD-RESYNC |
| 7 | `docs/architecture/CONTEXT-ENGINEERING.md` + `DATA-DEFINITIONS.md` | Cite `patient-journey/core/drug_classifier.py`, `fhir_explorer/parser/`, etc. | Pre-May-3-refactor paths. Code now lives at `lib/clinical/` and `lib/fhir_parser/`. | ARCH-DOC-RESYNC |
| 8 | `api/core/harmonize_service.py:1814` | (no claim — code) | Production imports from dev zone (`lib.extract.pipelines`) | covered by PROMOTE-EXTRACT |

### MEDIUM — explanation breaks but won't actively mislead

| # | Location | Claim | Reality | Proposed task |
|---|---|---|---|---|
| 9 | Root `CLAUDE.md` line 95 | `lib/sql_on_fhir/views/` has "5 ViewDefinitions" | 6 JSON files: patient, condition, condition_active, medication_request, observation, encounter | CLAUDE-MD-RESYNC |
| 10 | `docs/architecture/ATLAS-DATA-MODEL.md` | Cites `patient-journey/core/sql_on_fhir/views/README.md` | Wrong path; views live at `lib/sql_on_fhir/views/` | ARCH-DOC-RESYNC |
| 11 | `docs/architecture/ATLAS-DATA-MODEL.md` | Cites `data-research/josh-stack-deep-dive/INDEX.md` | Directory absorbed into `ehi-atlas/notes/` | ARCH-DOC-RESYNC |

### LOW — cosmetic

| # | Location | Claim | Reality | Proposed task |
|---|---|---|---|---|
| 12 | `docs/architecture/DEPLOYMENT.md` | References `deploy/nginx.conf` | Actual files: `deploy/nginx-app.conf`, `deploy/nginx-host.conf` | ARCH-DOC-RESYNC |
| 13 | Root `CLAUDE.md` lines 66–69 | `temporal.py / batch_enrichment.py / rag_tools.py ← TODO` in directory tree | Files genuinely don't exist | Intentional roadmap placeholder — leave or move to a "Planned" section |

### Confirmed clean (good news)

- `docs/architecture/PDF-PROCESSOR.md` cross-references all resolve. (PROMOTE-EXTRACT will introduce new drift here — task brief already covers it.)
- `lib/` has no inverted dependencies on `api/` or `ehi-atlas/`. `lib/` is a clean leaf.
- `ehi-atlas/` does not import from `api/`. Outbound dep convention is honored in that direction.
- `scripts/` does not import from `ehi-atlas/`.
- No live code imports from `archive/`.
- `api/core/interaction_checker.py` vs `lib/clinical/interaction_checker.py` look like duplication but are an intentional split (lib = full logic, api = lightweight wrapper). Not drift.

### Tasks surfaced

Two new doc-only tasks emerge, both perfect daily-refiner work (no code, low risk, ship as small focused PRs):

**CLAUDE-MD-RESYNC** — fix all root `CLAUDE.md` drift (rows 1, 2, 3, 5, 6, 9 above). Single pass through the directory tree section + Reference Docs table. ~1 hour. **Should run *after* PROMOTE-EXTRACT** so it can correctly describe the new `lib/extract/` location in one go.

**ARCH-DOC-RESYNC** — fix rotted refs in `CONTEXT-ENGINEERING.md`, `DATA-DEFINITIONS.md`, `ATLAS-DATA-MODEL.md`, `DEPLOYMENT.md` (rows 7, 10, 11, 12). ~1-2 hours. Independent of PROMOTE-EXTRACT.

### Sequencing

```
1. PROMOTE-EXTRACT          (refactor — includes PDF-PROCESSOR.md cross-ref updates)
       ↓
2. CLAUDE-MD-RESYNC         (doc-only — describes the new tree)
       ↓ (parallel-safe with above after step 1)
3. ARCH-DOC-RESYNC          (doc-only — fixes pre-refactor path references)
```

After all three: the project guide and architecture docs match the live tree. A subagent reading CLAUDE.md cold can navigate without tripping.

---

## Entry 4 — Model landscape + test environment (2026-05-07)

### What's already wired

Honest baseline before talking about new models:

- `VisionBackend` Protocol with two implementations: `AnthropicBackend`, `GoogleAIStudioBackend`
- Pipeline registry with `@register` decorator — adding a new pipeline is one file
- Five Streamlit pages in `ehi-atlas/app/pages/`: `01_Sources_and_Bronze`, `03_PDF_Lab`, `04_PDF_Compare`, `05_Pipeline_Bakeoff`, `06_Harmonize_Labs`
- `bake_off()` harness with `BakeoffCell` dataclass + `format_markdown()` reporter
- Eval harness (`eval.py`) measures schema gaps, in-schema misses, vision-wins per resource type
- SHA-keyed deterministic cache so repeated runs don't re-bill

So the question isn't "do we have a test environment?" — it's "what's missing for serious model comparison?"

### Models we could integrate

#### Vision-direct (PDF-native — same shape as today's pipeline)

| Provider | Model | Status today | Notes |
|---|---|---|---|
| Anthropic | Claude Sonnet 4.6, Opus 4.7 | ✅ wired | Production default for `multipass-fhir` |
| Google | Gemini 2.5 Pro / Flash | partial — `GoogleAIStudioBackend` exists, used for Gemma | Pro is reasoning-tier; Flash is the cost play |
| Google | **Gemma 4 31B IT (multimodal)** | ✅ wired via Google AI Studio backend | Already powers `multipass-fhir-gemma-tabular`. Bake-off shows F1 0.55 on Cedars vs 0.70 for all-Claude. Cheap; tabular-strong. |
| OpenAI | GPT-4o, GPT-4 Turbo Vision | ❌ not wired | Would need an `OpenAIBackend` adapter — ~150 lines following the existing Protocol |
| Open-weights | Qwen2.5-VL, Llama 3.2 Vision, InternVL, MiniCPM-V | ❌ not wired | Would need an `OllamaBackend` or `vLLMBackend` adapter |

#### Text-NER + entity linking (NOT PDF-native — requires OCR or text-layer extraction step)

| Provider | API | Output | Status |
|---|---|---|---|
| AWS | **Comprehend Medical** (DetectEntitiesV2, InferRxNorm, InferICD10CM, InferSNOMEDCT) | Entities w/ code linking; you assemble the Bundle | ❌ not wired |
| Google Cloud | **Healthcare Natural Language API** (`analyzeEntities`) | Entities w/ UMLS / SNOMED / RxNorm / LOINC / ICD-10 linking; you assemble the Bundle | ❌ not wired |
| Microsoft | **Azure Text Analytics for Health** | Entities w/ UMLS linking; you assemble the Bundle | ❌ not wired |

**Important framing:** these three are **not direct competitors to multipass-fhir.** They take *text*, not PDFs. Integrating any of them means building a new pipeline shape:

```
PDF → [OCR or pdfplumber text-layer] → [cloud NER API] → [FHIR assembler] → Bundle
```

That's a hybrid of the deferred `OCRThenExtractPipeline` (K.5 in PDF-PROCESSOR.md) plus a clinical NER step. They'd be evaluated against `multipass-fhir` in the same bake-off, on the same PDFs, with the same F1 metrics.

#### OCR engines (preprocessing layer)

| Engine | Notes |
|---|---|
| MinerU | Open-source; layout-strong; local |
| olmOCR | Allen Institute; open weights; markdown-quality |
| Marker | Fast, open-source, local |
| Mistral OCR API | Hosted, paid, very strong |
| AWS Textract | Cloud, paid; pairs naturally with Comprehend Medical |

These don't extract clinical structure — they preprocess. Pick one when we ship the OCR pipeline; not strategic on its own.

### Cost ballpark (for the pitch deck)

Order-of-magnitude, single ~10-page chart PDF, ~5k tokens of vision input:

| Pipeline | Approx. cost / PDF | Latency | F1 baseline |
|---|---|---|---|
| Claude Sonnet 4.6 (multipass) | $0.03–$0.08 | ~25s | 0.70 (Cedars) |
| Claude Opus 4.7 (per-pass for narrative) | $0.15–$0.40 | ~30s | TBD — likely +5pts on conditions |
| Gemini 2.5 Flash | $0.001–$0.005 | ~15s | TBD |
| Gemma 4 31B (Google AI Studio) | ~$0.0005–$0.002 | ~30s | 0.55 (Cedars, tabular) |
| AWS Comprehend Medical (text only) | $0.01–$0.05 (NER pricing per 100 chars) + OCR | ~10s NER + OCR | unknown — depends on OCR fidelity |
| Self-hosted Gemma via Ollama/vLLM | $0 marginal + GPU time | depends on hardware | unknown |

These are rough — the bake-off harness will produce real numbers per pipeline × PDF.

### Strategic pitch — what this looks like to a parent company

The defensible architectural claim is **vendor-neutrality with empirical model selection.** Atlas is not "the Claude PDF parser" — it is "a PDF→FHIR architecture where the model is a configuration choice, and the eval harness picks the winner per resource type per source." Pitch beats:

1. **Vendor flexibility for compliance.** Many enterprise health customers already have an AWS BAA, or a Google HIPAA contract, or are Azure shops. Atlas can run on whichever stack the customer is already covered by.
2. **Cost-tunable.** Tabular passes (labs, immunizations) run on Gemma at ~$0.001/PDF; narrative passes (conditions, allergies) run on Claude at ~$0.05/PDF. Customers who care about cost get a knob; customers who care about quality get a different knob.
3. **Verification via cross-extraction.** Run two different pipelines on the same PDF; resources that both extract are high-confidence; disagreements go to human review. That's a credible accuracy story for clinical deployment.
4. **The wedge stays the same regardless of model.** "Vision extraction recovers facts the structured EHR missed" was measured on Claude. Re-measuring it on Gemma + Comprehend Medical adds independent evidence to the same wedge — different eyes, same conclusion.

### Gemma 4 + competition angle

Gemma 4 is already wired. Today's bake-off shows it underperforming Claude on Cedars (F1 0.55 vs 0.70), but with a clear pattern: it loses ground on narrative passes (conditions, allergies), holds reasonable ground on tabular (labs, immunizations).

If there is a current Gemma competition (Kaggle / Google Developer Challenge — would need to verify which is active), Atlas has a credible entry shape:

- **Application:** PDF → FHIR R4 clinical extraction with provenance
- **Baseline:** measured F1 per resource type, published
- **Improvement target:** narrow the conditions-pass gap from Gemma to Claude via prompt tuning, few-shot examples, or LoRA fine-tuning on annotated clinical PDFs
- **Evaluation:** the same bake-off harness, made reproducible
- **Differentiator:** open-weights model running a regulated-industry workload with full provenance

Worth verifying which Gemma competition is currently open before committing to this — flag for follow-up.

### Test environment — what's missing

Inventory of gaps blocking serious model comparison:

| Gap | Impact | Fix shape |
|---|---|---|
| **Bring-your-own-PDF flow.** Test bench works on the corpus fixtures; user can't drop a new PDF in and run all pipelines. | Blocks fast iteration on real-world PDFs. | Streamlit upload page + pipeline-matrix runner button |
| **Per-pass logging.** Cache stores results, but the prompts + raw model responses + tool calls aren't archived for replay/debug. | Hard to understand WHY a pass failed; can't audit what the model saw. | Add a `runs/` directory keyed by run-id; append `prompt.txt`, `response.json`, `usage.json` per pass |
| **No OpenAI / vLLM / Ollama backends.** Today only Anthropic + Google AI Studio. | Can't bake-off GPT-4o or self-hosted Gemma. | One adapter per backend, ~150 lines each, following the `VisionBackend` Protocol |
| **No text-NER pipeline.** Cloud-NER APIs aren't integrated. | Can't bake-off AWS/Google/Azure clinical NER. | New pipeline class: OCR → NER → FHIR assembler. Reusable across all three providers (the FHIR assembler is the hard part; the API call is shallow). |
| **No vision-wins reviewer UI.** Bake-off flags vision-wins as "extras"; today they're listed but not classifiable. | Eval treats valid vision-wins as false positives, depressing precision. PDF-PROCESSOR.md flags this as planned. | Streamlit page that surfaces extras with PDF context; user clicks `valid / hallucination / out_of_scope`; persisted verdict feeds eval recompute. |
| **No cost / latency dashboard.** Bake-off captures these per cell, but nothing aggregates over time. | Hard to track which models drift in cost or latency week over week. | Append-only `bake_off_runs.jsonl` + a Streamlit chart. |
| **Ground-truth labeling for new PDFs.** Today only Cedars has structured-sibling ground truth. Function Health PDFs lack it. | F1 numbers only meaningful where ground truth exists. | Two paths: (a) accept user-pasted FHIR Bundle as ground truth; (b) human-review-as-truth for pure narrative PDFs. |
| **Run history / diff.** Re-running a pipeline overwrites the cache. Can't see "this pipeline got worse this week." | Regressions invisible. | Cache becomes append-only with run-id; bake-off page can pin a baseline and diff. |

### Proposed task — PDF-LAB-STUDIO

Bundle the gaps into one focused build (Phase 2 candidate, sized for ~3–5 days):

**Scope:**
1. **Bring-your-own-PDF upload page.** User uploads PDF + optional ground-truth Bundle JSON. Stored in `data/pdf-lab/{run_id}/`.
2. **Pipeline matrix runner.** Checkbox grid: which pipelines to run × which models per pass. Submit → background job → results land in the run dir.
3. **Per-pass full trace logging.** For each pass, persist: prompt, image inputs (or hash refs), raw model response, parsed FHIR resources, tool calls (when agentic lands), token usage, latency.
4. **Comparison view.** Side-by-side per-resource-type F1, cost, latency. Click any extracted resource → see which pipeline produced it + provenance back to PDF page/bbox.
5. **Vision-wins reviewer.** Tag each "extra" as `valid / hallucination / out_of_scope`. Verdict feeds the eval recompute and persists.
6. **Backend adapters needed before launch:** keep current set; add OpenAI + Ollama as P1 follow-ups. The studio shouldn't block on those — it ships with what's wired and grows from there.

**Where it lives:** `ehi-atlas/app/pages/07_PDF_Lab_Studio.py` (after PROMOTE-EXTRACT, paths in this scope adjust).

**Why this matters now:** without it, every model-comparison decision is a debate. With it, every decision is a bake-off cell.

### What I need from you to make this real

The user-action items the studio makes possible:

1. **Find PDFs.** Real Cedars / Function Health / Quest / Kaiser-style PDFs are gold. Synthetic PDFs from Synthea are a starting point but don't stress the architecture the same way.
2. **Provide ground truth where you have it.** SMART portal pulls (the Cedars JSON is the canonical example) become structured siblings that drive F1.
3. **Spend ~30 min on vision-wins triage per bake-off.** Eval credibility depends on someone classifying the extras.
4. **Decide which models to integrate first.** OpenAI, Mistral OCR, AWS Comprehend Medical are all one-adapter-each. Pick the one or two most valuable to the parent-company pitch.

### Questions parked

- Is there a specific Gemma competition currently open we should target? (Verify before committing.)
- Does the parent company have an existing AWS / GCP / Azure HIPAA agreement we should optimize toward?
- For PDF-LAB-STUDIO: ship as a Streamlit page in the dev zone, or promote to React in `app/` so judges can use it during the demo? (Streamlit first; promote later if it earns it.)

---

## Entry 5 — PDF-LAB-STUDIO task queue drafted (2026-05-07)

The studio described in Entry 4 has been broken into six builder-sized tasks at `.claude/pdf-lab-studio-queue.md`. Each fits the "one task per invocation" model the existing phase1-builder agent expects, with concrete file-touch lists and smoke tests.

### The six tasks

| ID | Title | Depends on | Why it matters |
|---|---|---|---|
| **PDFLAB-T01** | Per-pass trace logging (`lib/extract/run_logger.py`) | — (parallel-safe with T02) | Foundation. Every later task assumes traces exist. No behavior change to extraction itself. |
| **PDFLAB-T02** | Studio page shell + bring-your-own-PDF upload | — | One-minute path from "user has a PDF" to "PDF is queued." |
| **PDFLAB-T03** | Pipeline matrix runner (N pipelines × per-pass model overrides) | T01 + T02 | Drives the existing bake-off harness from the UI; persists per-cell artifacts under the run dir. |
| **PDFLAB-T04** | Side-by-side comparison view with provenance click-through | T03 | Surfaces per-resource-type F1 / precision / recall next to actual extractions, with page+bbox links. |
| **PDFLAB-T05** | Vision-wins reviewer + human-adjusted F1 | T04 | Closes the precision-penalty problem on valid extras (the 4 conditions + 41 labs from Cedars). Honest eval. |
| **PDFLAB-T06** | Run history (`bake_off_runs.jsonl`) + cost/latency/F1 dashboard | T03 | Regression detection over time + the chart that backs the parent-company pitch. |

### Hard prerequisite

**PROMOTE-EXTRACT must ship first.** All file paths in the queue assume `lib/extract/`. Documented at the top of the queue file.

### Deferred to later briefs (T07+)

- OpenAI backend adapter
- Ollama / vLLM backends for self-hosted vision models
- Cloud-NER pipeline shape (AWS Comprehend Medical / Google Healthcare NLP / Azure Text Analytics)
- Streamlit-to-React promotion for the demo

### Where to dispatch from

`.claude/pdf-lab-studio-queue.md` — same shape as `.claude/phase1-queue.md`. The phase1-orchestrator pattern can read from it directly; or a future `pdf-lab-orchestrator` (if we want to keep PDF Lab work isolated from Phase 1 submission work) can do the same job.

Dispatch order assuming PROMOTE-EXTRACT has shipped: **T01 || T02 → T03 → T04 → (T05 || T06)**.

---

## Entry 6 — CODE-RESOLUTION-POST-PASS (2026-05-07)

### Why this exists

The Function Health comparison (`pdf-review/blake-functionhealth-2025-11-19/notes.md`) showed our parser at 0% LOINC coverage vs FH's 67%. Three deficits identified, all post-extraction enrichment:

1. **LOINC** — schema accepts `loinc_code`; prompt forbids hallucination; PDF doesn't print codes; result: zero codes emitted. Disciplined extraction, missing resolution layer.
2. **SNOMED** — not in lab schema at all (only conditions schema has it).
3. **Interpretation flag** — we emit only what the PDF prints (3 of 58); FH derives in-range/out-of-range computationally for all.

The fix is **deterministic post-passes** that run after extraction: take the extracted display name, look it up in a curated terminology table, attach codes. Avoids the hallucination risk while closing the visible gap.

### Existing scaffolding (don't duplicate)

Phase 1 already has the bones:
- `ehi-atlas/corpus/reference/loinc/showcase-loinc.json` — **22-code LOINC subset**, well-structured, covers 17 of the 58 tests in our example PDF (29%). Pinned to LOINC 2.77.
- `ehi-atlas/corpus/reference/VERSIONS.md` — explicit Phase 1 / Phase 2 split: "Phase 1 = showcase codes; Phase 2 = full UMLS / LOINC / SNOMED coverage once Blake completes UMLS registration."
- `archive/ehi-atlas-5layer/ehi_atlas/terminology/rxnorm.py` — RxNorm REST client + cache pattern (archived but retrievable as starting point).

**This work IS the Phase 2 promotion** that VERSIONS.md anticipated. Same pattern, broader scope.

### Licensing & download paths

| Terminology | License | Path forward | User action needed |
|---|---|---|---|
| **LOINC** | Apache-style, attribution only | NLM Clinical Tables Search API (`/api/loinc_items/v3/search`) — **no auth required** | None for v1 (API). Optional: free account at loinc.org for full release download (Phase 2 nicety). |
| **SNOMED CT US Edition** | NLM UMLS license — free but registration-gated | UMLS REST API or full release download | **Register at uts.nlm.nih.gov** (~5 min, free). Then API key goes in `.env` (gitignored). Tracked as BUILD-TRACKER task 1.4. |
| **RxNorm** | Free, no registration | Existing `rxnorm.py` REST client (archived; restore it) | None |
| **CVX** | Free, public | CDC's CVX file or HL7 terminology server | None |

For Phase 1 LOINC v1, we use the NLM API. Verified working — queries for `Glucose`, `BUN`, `Creatinine`, `eGFR`, `BUN/Creatinine Ratio` all return valid LOINC codes including the same ones Function Health uses (`2345-7`, `3094-0`, `2160-0`, `3097-3`).

### Sub-task breakdown (CODE-RESOLUTION queue)

Detail at `.claude/code-resolution-queue.md`. Summary:

| ID | Title | Sized for |
|---|---|---|
| **CODE-T01** | Curate LOINC reference table — extend showcase to ~500 common labs via NLM API + verified-against-Function-Health subset | ½–1 day |
| **CODE-T02** | LOINC matcher module — display normalization + alias dict + confidence scoring | ½ day |
| **CODE-T03** | Wire LOINC matcher as post-pass in multipass-fhir; emit `loinc_code` on Observations | ½ day |
| **CODE-T04** | Add `snomed_code` field to ConditionEntry + curate ~500 SNOMED conditions reference table (gated on UMLS registration) | 1 day |
| **CODE-T05** | SNOMED matcher with simple hierarchy walk; wire as Conditions post-pass | 1 day |
| **CODE-T06** | INTERPRETATION post-pass — derive `H/L/N/A` from value + reference range (deterministic, no LLM) | ½ day |
| **CODE-T07** | CLINICAL-CATEGORY extension — drive Metabolic/Kidney/Liver/etc. from LOINC code | ½ day |

**Total: ~5 days of focused work.**

### Sequencing

```
PROMOTE-EXTRACT (refactor — gates everything)
       ↓
       ├─→ CODE-T01..T03 (LOINC — ~1.5 days, no UMLS dependency)
       │
       ├─→ CODE-T04..T05 (SNOMED — ~2 days, BLOCKED on UMLS registration)
       │
       ├─→ CODE-T06..T07 (interpretation + category — ~1 day, depends on T03)
       │
       └─→ PDF-LAB-STUDIO T01..T06 (parallel — measures the impact via bake-off)
```

LOINC track (T01-T03) and SNOMED track (T04-T05) are independent. Recommend starting LOINC immediately since it has no auth dependency, while UMLS registration runs in parallel.

### Expected impact

When CODE-T03 ships and the bake-off runs:
- Cedars Health Summary labs F1: was **0.70**. Estimate after: **0.80–0.90.** Codes that previously matched only via fuzzy display will now match via exact code.
- Function Health PDF coverage: from 0% LOINC → **~80% LOINC** (curated table miss rate dictates the ceiling).
- USCDI conformance for Observation (laboratory): structurally satisfied for the first time.

These numbers are estimates. The whole point of building PDF-LAB-STUDIO is so we don't have to estimate — we measure.

### What I need from the user

1. **Greenlight on the queue.** Once approved, CODE-T01 can dispatch immediately (no auth needed).
2. **UMLS registration** at https://uts.nlm.nih.gov/uts/signup-login (free, gated). Once you have credentials, drop the API key in `.env` as `UMLS_API_KEY=...`. Unblocks CODE-T04/T05.
3. **Optional: LOINC free account** at https://loinc.org for the full release download. Not strictly needed for v1 (NLM API covers it), nicer for Phase 2 offline + complete coverage.

---

*Last updated: 2026-05-07. Working log — append entries with date stamp.*
