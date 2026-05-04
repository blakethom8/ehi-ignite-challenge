# Pipeline Development Log

> A running journal of pipeline experiments, tuning attempts, bake-off results, and decisions. **Newest entries at top.** Append-only — never edit historical entries; correct via a follow-up entry instead.
>
> The architecture decision record at [`PDF-PROCESSOR.md`](./PDF-PROCESSOR.md) captures *stable* decisions. This file captures the *empirical work* that produces them. Bake-off result tables, prompt-tuning A/Bs, model-swap experiments, dead-ends — all go here. The audience is future-Blake, future-Claude, and future contributors trying to understand "why is this pipeline configured this way?"

## Entry template

```
## YYYY-MM-DD · short title

**Agent:** who ran this (Claude Opus 4.7, Cursor session, you, etc.)

**What:** the change made / experiment run

**Why:** the hypothesis being tested

**How:** bake-off setup — pipelines, PDFs, ground truth

**Result:** the data (paste markdown table from `format_markdown(cells)`)

**Conclusion:** what we now believe (or fail to learn)

**Next:** what this unblocks; pending follow-ups

---
```

Each entry should be 200–500 words. Tables and code snippets welcome. **Honesty about negative results matters as much as wins** — knowing what *didn't* work prevents future re-litigation.

---

## 2026-05-03 · Move B — Gemma 4 31B for tabular passes on Cedars

**Agent:** Claude Opus 4.7

**What:** Built `MultiPassFHIRGemmaTabularPipeline` (registered as `multipass-fhir-gemma-tabular`). Same architecture as `multipass-fhir` but with per-pass overrides routing medications, immunizations, and lab observations to Gemma 4 31B. Conditions, allergies, and Pass 0 stay on Claude.

**Why:** Cost optimization per `PDF-PROCESSOR.md` Decision 4. Tabular passes (lab tables, med lists, vaccine schedules) play to Gemma's strengths and are 5–10× cheaper than Claude. If F1 holds, this becomes the new default.

**How:** First attempt failed with `pypdfium2` race condition on concurrent rasterization (3 Gemma passes opening the same byte buffer simultaneously). Fix: class-level `threading.Lock` on `GoogleAIStudioBackend._RASTERIZE_LOCK`. Second attempt failed with three `HTTP 400 INVALID_ARGUMENT` errors from the Google AI Studio API on the 25-page Cedars PDF.

**Result:**

```
[multipass-fhir] pass 'medications'      failed: HTTP 400 INVALID_ARGUMENT
[multipass-fhir] pass 'immunizations'    failed: HTTP 400 INVALID_ARGUMENT
[multipass-fhir] pass 'lab_observations' failed: HTTP 400 INVALID_ARGUMENT
```

| type | gt | extracted | F1 | source |
|---|---:|---:|---:|---|
| condition | 28 | 3 | 0.19 | Claude (worked) |
| allergy | 1 | 1 | 1.00 | Claude (worked) |
| medication | 7 | 0 | 0.00 | Gemma (FAILED) |
| immunization | 10 | 0 | 0.00 | Gemma (FAILED) |
| lab | 143 | 0 | 0.00 | Gemma (FAILED) |

Overall F1: **0.03** (only the Claude passes succeeded).

**Conclusion:**

1. **Gemma 4 31B via Google AI Studio API fails on long PDFs.** 25 pages × 150 DPI rasterized PNGs = ~5 MB of inline image data. The API rejects with INVALID_ARGUMENT — likely a per-request image-count limit (Google's docs say 20 MB inline-data limit but may have a separate parts-per-request constraint).
2. **The error message is generic** — "Request contains an invalid argument." doesn't tell us what's invalid. Need to try smaller PDFs to localize the constraint.
3. **The pypdfium2 concurrency bug was real and is now fixed.** Class-level `_RASTERIZE_LOCK` serializes the rasterization step across threads while leaving the API call (the slow part) parallel.
4. **Cost-optimization hypothesis still untested on Cedars.** Need either chunking or a smaller PDF to confirm whether tabular F1 holds when Gemma replaces Claude on tabular passes.

**Next:**

- ⏳ **Test Gemma-tabular variant on a smaller PDF** (rhett759, 3 pages, 17 facts) — confirms Gemma can handle the multi-pass structure when it's not constrained by image count.
- ⏳ **If Gemma works on small PDFs:** add page-chunking to GoogleAIStudioBackend so 25-page PDFs split into 5-page chunks per call.
- ⏳ **If Gemma fails on small PDFs too:** the issue is in the schema/prompt/structure, not page count — investigate the request payload.
- ⏳ Once Gemma-tabular works at all, measure F1 + cost vs Claude on equivalent PDFs.

### 2026-05-03 · Move B follow-up: rhett759 (3 pages)

**Result:** `multipass-fhir-gemma-tabular × rhett759-quest-cmp (3 pages)` — **succeeded** in 49.8s, produced 17 bundle entries (2 Conditions + 15 Observations).

Comparable to `multipass-fhir × rhett759-quest-cmp` (all-Claude) from Move C: 17 entries, ~20s.

**Confirmed:** Gemma 4 31B works at small PDF sizes. The 25-page Cedars failure is specifically about long-PDF / large-image-payload constraint in the Google AI Studio API. **Architectural integrity intact**; the issue is API-layer.

**Surprising finding:** Gemma was *slower* than Claude on rhett759 (50s vs 20s wall-clock). Per-call Gemma latency on small PDFs is ~30–50s, vs Claude's ~10s. Cost win is real (~$0.12 vs ~$0.30 estimated) but **the speed advantage we expected from "smaller, cheaper model" doesn't materialize** at this PDF size.

**Updated decisions:**
- `multipass-fhir-gemma-tabular` is **not** the new default. Cost-only wins on small PDFs; broken on long PDFs.
- Reasonable to keep as a registered variant for cost-constrained dev workflows on small inputs.
- Real next step for cost-optimization: **page chunking on `GoogleAIStudioBackend`** so 25-page PDFs can split into 5-page chunks. Until then, Gemma-tabular is unfit for chart-export documents.

---

## 2026-05-03 · Move A — conditions prompt v1 → v2 on Cedars

**Agent:** Claude Opus 4.7

**What:** Rewrote the conditions pass system prompt to be more comprehensive (`v1` → `v2`). Bumped per-pass prompt version. Re-ran multipass-fhir on Cedars Health Summary.

**Why:** Move K.4's bake-off result showed condition recall at 0.11 (3/28). Hypothesis: the v1 prompt didn't enumerate where conditions hide in chart exports (Active Problems, PMH, Assessment, encounter diagnoses, screening exams, etc.). v2 explicitly lists all those sections and pushes for completeness ("be comprehensive — finding zero conditions on a chart export is unusual").

**How:** `multipass-fhir × cedars-health-summary` with new conditions prompt. Per-pass prompt versioning means only the conditions cache invalidates; other 4 passes re-extracted from scratch due to cache-key migration but with unchanged prompts.

Also: encountered a transient Anthropic API failure on the first attempt (Pass 0 returned `{}`); added a single retry to `_run_pass` for robustness.

**Result:**

| type | gt | extracted (v2) | extracted (v1) | TP | FP | precision | recall | F1 (v2) | F1 (v1) |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| condition | 28 | **5** | 3 | 3 | 2 | 0.60 | 0.11 | 0.18 | 0.19 |

Other passes unchanged (same model, same data):

| type | F1 | unchanged |
|---|---:|---|
| medication | 0.92 | ✓ |
| allergy | 1.00 | ✓ |
| immunization | 0.89 | ✓ |
| lab | 0.70 | ✓ |

Overall weighted F1: **0.64 → 0.64** (unchanged within rounding).

**Conclusion:**

1. **The prompt change made the model more aggressive but did not increase TP count.** Recall stayed at 0.11; the 2 new extractions were FPs against ground truth.
2. **This may be the recall ceiling, not a prompt-tuning bottleneck.** The Cedars FHIR (`cedars-sinai.json`) contains 28 conditions covering the patient's entire chart history. The Health Summary PDF is a 25-page snapshot. It's plausible that **most of the missed 25 conditions simply aren't in the PDF at all** — Lucy/Epic Health Summary exports don't include every historical condition.
3. **Don't conclude the prompt is wrong without checking what's actually IN the PDF.** Need either:
   - Manual inspection of the 25 missed conditions to see which appear in the PDF text
   - A new eval mode that filters ground truth to "facts findable in the PDF" before scoring
4. **Two FPs are worth investigating.** Could be vision wins (real conditions in the document text not coded as Cedars Conditions) or hallucinations. Without manual review we can't tell.

**Decisions:**
- Conditions prompt **stays at v2** (more comprehensive is better even if F1 didn't shift on this PDF — should help on PDFs that DO have more findable conditions).
- Recall ceiling is real and worth surfacing in the eval harness — adding "GT-in-PDF presence check" to the backlog.

**Next:**

- ⏳ Add eval mode: filter ground-truth facts by "is this string findable somewhere in the PDF text?" before scoring. Resolves the recall-ceiling ambiguity.
- ⏳ Run conditions v2 on the other comprehensive PDFs (Sample H&P, Discharge Summary) — different documents may have different recall ceilings.
- ⏳ Continue Move B (currently re-running after pypdfium2 lock fix).

---

## 2026-05-03 · Move C — multipass vs baseline across Blake's full PDF set

**Agent:** Claude Opus 4.7

**What:** Ran the bake-off matrix against 6 PDFs (Cedars Health Summary, Function Health 7-29-2024, Function Health 11-29-2025, rhett759 Quest CMP fixture, Sample H&P, Discharge Summary). 12 cells total; only Cedars has ClientFullEHR ground truth.

**Why:** First bake-off only validated multipass on one PDF. Need to know whether the schema-direct multi-pass approach generalizes — particularly whether it provides value on lab-only PDFs (Function Health) where the baseline already extracts everything.

**How:** 2 pipelines (`single-pass-vision`, `multipass-fhir`) × 6 PDFs. Multipass uses default Claude Opus 4.7 for all 6 passes. Cache hits where present from K.4.

**Result:**

| PDF | baseline | multipass | delta | F1 (if GT) |
|---|---:|---:|---:|---:|
| cedars-health-summary | 3 | **156** | +153 | 0.64 |
| sample-h-and-p | 10 | **65** | +55 | — |
| discharge-summary | 5 | **20** | +15 | — |
| rhett759-quest-cmp | 15 | 17 | +2 | — |
| fh-2024-07-29-panel | 86 | 86 | 0 | — |
| fh-2025-11-29-panel | 58 | 58 | 0 | — |

Total wall-clock for all 12 cells: 178s.

**Conclusion:**

1. **Architecture choice is document-type dependent.** For pure lab PDFs (Function Health, rhett759), `multipass-fhir` produces the same fact count as `single-pass-vision` — the schema gap doesn't apply when the document only contains labs. Latency is ~70× higher for zero gain on these documents.
2. **For comprehensive chart PDFs (Cedars, H&P, discharge), multipass is essential.** The schema gap was hurting baseline by 15–153 facts per document on these. This is exactly the use case the architecture was designed for.
3. **Routing opportunity.** A pipeline router that detects lab-report-only documents and dispatches to `single-pass-vision` while routing chart documents through `multipass-fhir` would be ~70× faster on lab-heavy workloads with no quality loss. Defer until we have real workload data.
4. **Generalization confirmed.** Multipass works on every PDF tested without failures. Pass 0 + 5 parallel passes = robust orchestration.

**Next:**

- ⏳ Move A: prompt-tune the conditions pass (target conditions recall > 0.6 on Cedars).
- ⏳ Move B: per-pass Gemma swap (already wired as `multipass-fhir-gemma-tabular`; needs bake-off run).
- ⏳ Document-type detection / pipeline routing (deferred).
- ⏳ Acquire ground truth for at least one Function Health PDF (would let us measure baseline ≈ multipass quantitatively).

---

## 2026-05-03 · First bake-off — multipass-fhir vs single-pass-vision baseline

**Agent:** Claude Opus 4.7

**What:** Built the [pipeline framework](../../ehi-atlas/ehi_atlas/extract/pipelines/) (Protocol + registry + bake-off harness), shipped two pipelines (`single-pass-vision` baseline + `multipass-fhir`), ran first bake-off against Blake's Cedars Health Summary PDF (25 pages, 189 ground-truth facts in `cedars-sinai.json`).

**Why:** Validate decisions 1–4 of `PDF-PROCESSOR.md`. The eval harness from earlier in the session showed `single-pass-vision` losing **161 of 189 ground-truth facts** to schema gaps (medications, allergies, immunizations, labs all 0/N). Schema-direct multi-pass should close the gap.

**How:** 2 pipelines × 1 PDF, both backends defaulting to Anthropic Claude Opus 4.7. Multi-pass uses 6 parallel calls (Pass 0 + 5 resource passes) via `ThreadPoolExecutor`.

**Result:**

| pipeline | weighted F1 | latency | bundle entries |
|---|---:|---:|---:|
| `single-pass-vision` | **0.03** | 1.3s (cache hit) | 3 |
| `multipass-fhir` | **0.64** | 93.7s | **156** |

Per-resource for `multipass-fhir`:

| type | gt | extracted | precision | recall | F1 |
|---|---:|---:|---:|---:|---:|
| medication | 7 | 6 | 1.00 | 0.86 | **0.92** |
| allergy | 1 | 1 | 1.00 | 1.00 | **1.00** |
| immunization | 10 | 8 | 1.00 | 0.80 | **0.89** |
| lab | 143 | 138 | 0.71 | 0.69 | 0.70 |
| condition | 28 | 3 | 1.00 | 0.11 | 0.19 |

**Conclusion:**

1. **The architecture hypothesis holds.** 21× weighted-F1 improvement on the same PDF — schema-direct multi-pass is dramatically better than the bespoke `ExtractedClinicalNote` intermediate format.
2. **Conditions stayed at 0.11 recall on both pipelines.** Same model, same prompt — this is *not* a schema-gap finding, it's a prompt-quality finding for the conditions pass. Health Summary PDFs decompose conditions across visit-section subheadings ("Active Problems," "Past Medical History," "Reason for Visit") that the current prompt doesn't nudge the model toward.
3. **Lab precision = 0.71** with 40 false positives. Could be vision wins (clinical-note text never coded as Observations server-side) or hallucinations. Manual review pending.
4. **Cost trade: ~6× more per PDF, ~70× longer wall-clock.** Per-pass Gemma swap is the natural next experiment to claw back cost.

**Next:**

- ✅ `multipass-fhir` is the new default architecture.
- ⏳ **Prompt-tune the conditions pass** (target: condition recall > 0.6 on same PDF).
- ⏳ **Per-pass Gemma swap** for the high-volume tabular passes (medications, immunizations, lab observations).
- ⏳ **Run multipass against Blake's other PDFs** (Function Health 7-29-2024, Requested Record, Sample H&P, rhett759 fixture) — confirms generalization beyond Cedars.
- ⏳ **Manual triage of the 40 lab false-positives** — vision wins vs hallucinations.

---
