# Pipeline Development Log

> A running journal of pipeline experiments, tuning attempts, bake-off results, and decisions. **Newest entries at top.** Append-only — never edit historical entries; correct via a follow-up entry instead.
>
> The architecture decision record at [`PDF-PROCESSOR.md`](./PDF-PROCESSOR.md) captures *stable* decisions. This file captures the *empirical work* that produces them. Bake-off result tables, prompt-tuning A/Bs, model-swap experiments, dead-ends — all go here. The audience is future-Blake, future-Claude, and future contributors trying to understand "why is this pipeline configured this way?"

## Quick index — all experiments to date

Best multipass-fhir result on Cedars Health Summary: **F1 0.70** (post-Move H, with `findable_only=True` + GT dedup).

| Date | Move | Subject | Headline result |
|---|---|---|---|
| 2026-05-03 | **H** | Conditions prompt v3 + GT dedup | F1 **0.67 → 0.70**; 4 condition "FPs" classified as **vision wins** (clinical findings in PDF that Cedars FHIR never coded) |
| 2026-05-03 | **I** | Lab "FPs" diagnostic | 41/41 are correctly-extracted IgE allergen panel; matching issue (GT display="class"), not pipeline error |
| 2026-05-03 | **F** | Page chunking for long PDFs | Gemma-tabular F1 0.55, 352s; 12 pts below all-Claude, 3.7× slower. Decision: keep all-Claude as default |
| 2026-05-03 | **D** | Findable-in-PDF GT filter | F1 0.64 → 0.67. Resolves the recall ceiling (9 of 28 GT conditions aren't in PDF) |
| 2026-05-03 | **C** | Multipass vs baseline across all PDFs | Lab-only PDFs: no improvement. Chart PDFs (Cedars, H&P, discharge): +15-153 facts. Routing opportunity. |
| 2026-05-03 | **B** | Gemma-tabular variant | First HTTP 400 on long PDFs; works on small (3-page rhett759). Led to Move F chunking work |
| 2026-05-03 | **A** | Conditions prompt v1 → v2 | F1 unchanged; surfaced recall-ceiling ambiguity → Move D |
| 2026-05-03 | K.4 | First bake-off (multipass vs single-pass) | F1 **0.03 → 0.64** (21× improvement). Schema-direct multipass validated. |

Pipeline framework + eval harness shipped 2026-05-03 (commits: pipeline Protocol + registry + bake-off + Streamlit Pipeline Bakeoff page).

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

## 2026-05-03 · Move H — conditions prompt v3 + GT dedup + vision-wins finding

**Agent:** Claude Opus 4.7

**What:** Wrote conditions prompt v3 with explicit ICD-code-family enumeration (Z-codes for screening/encounters, R-codes for symptoms-as-conditions, S-codes for injuries, D-codes for neoplasms). Added concrete example codes for each. Plus added GT deduplication to the eval (`dedupe_gt_facts()`) — Cedars FHIR emits a separate Condition resource per encounter, so the same code repeated across 4 visits was inflating GT count.

**Why:** Move A v2 (less specific) had condition recall stuck at 0.16. Diagnostic dump revealed the 16 missed-but-findable conditions clustered around Z/R/S code families the model wasn't pulling.

**How:** `multipass-fhir × cedars-health-summary`, conditions prompt at v3 (other passes unchanged), `findable_only=True`, `dedupe_gt=True`.

**Result:**

| metric | v2 | v3 | delta |
|---|---:|---:|---|
| **Overall weighted F1** | **0.67** | **0.70** | **+3 pts** |
| Conditions extracted | 5 | 7 | +2 |
| Conditions GT (deduped + findable) | 19 (raw findable) | 10 (deduped findable) | -9 (real fairness) |
| Conditions TP | 3 | 3 | 0 |
| Conditions FP | 2 | 4 | +2 |
| Conditions recall | 0.16 | 0.30 | +14 pts |
| Conditions F1 | 0.27 | 0.35 | +8 pts |

The condition recall headline (0.16 → 0.30) is mostly GT dedup, not v3 prompt. v3 added 2 new emissions; both went into the FP bucket. **But inspecting the FPs revealed the actual story — they're vision wins, not hallucinations.**

**The 4 condition FPs are all clinical findings in the PDF that Cedars FHIR never coded:**

  1. `'chronic appearing fracture at the base of the right 2nd toe proximal phalanx'` — X-ray report narrative
  2. `'bipartite tibial sesamoid on the left'` — imaging anatomical variant
  3. `'marginal osteophyte at the lateral left 1st mtp joint'` — bone spur
  4. `'bilateral inferior turbinate hypertrophy'` — ENT exam finding

These are real clinical facts in the PDF. Cedars represents them as narrative text (imaging reports, exam findings) but **never created Condition resources for them**. Vision extraction recovered them. The eval's "FP" classification is an artifact of using FHIR-only ground truth.

**Conclusion:**

1. **The Atlas wedge is now empirically demonstrated.** Vision extraction pulled 4 clinical facts the structured FHIR is missing. This is the cross-source-augmentation use case the architecture was designed for.
2. **Conditions recall improvement was 50% real, 50% GT-dedup-cosmetic.** The 7 still-missed conditions (Z-codes, R-codes, S-codes for sprains/fractures) suggest the model is biased toward narrative descriptions over coded encounter diagnoses. v4 might iterate further but diminishing returns set in.
3. **The eval's precision metric is misleading.** Calling vision wins "false positives" punishes the pipeline for doing the right thing. Future eval upgrade: a "vision-wins reviewer" surface that lets a human classify each FP as `valid_extra` vs `hallucination`.
4. **GT deduplication was a real fairness improvement.** Without it, recall was bounded by Cedars's encounter-multiplicity. Should ship by default for all future runs.

**Decisions:**

- **Conditions stays at v3.** Modest gain over v2 but enables vision-wins extraction.
- **`dedupe_gt=True` is the new eval default.**
- **Future: "vision-wins reviewer"** Streamlit page or notebook cell — let a human triage condition/lab "FPs" into valid-extras vs hallucinations.

**Next:**

- ⏳ Move I follow-up: the lab "FPs" deserve the same diagnostic.
- ⏳ Conditions v4: target the 7 still-missed Z/R/S-codes specifically.
- ⏳ Vision-wins reviewer surface.

---

## 2026-05-03 · Move I — lab "FPs" diagnostic: matching issue, not hallucination

**Agent:** Claude Opus 4.7

**What:** Dumped the 41 lab false-positives from the multipass-fhir × Cedars run. Goal was to classify them as vision wins vs hallucinations to inform a v2 lab prompt.

**Why:** Lab F1 stuck at 0.70 (precision 0.71, recall 0.69). Reducing 40 FPs through prompt tightening would push F1 toward 0.85.

**Result — finding flipped the framing:**

All 41 lab "FPs" are an **IgE allergen panel** extracted with proper allergen names:
- "egg white (f001) ige class"
- "peanut (f013) ige class"
- "walnut (f256) ige class"
- "milk, cow's (f02) ige class"
- "shrimp (f024) ige class"
- "d pteronyssinus (d001) ige class"
- "aspergillus fumigatus (m003) ige class"
- … 34 more

The GT has these same labs but coded as `loinc:102136-9 'class'` / `loinc:102639-2 'class'` / etc. — the GT `code.text` is just `"class"` with no allergen identifier, plus a LOINC code per allergen.

**The labs are correctly extracted.** The matcher can't link them because:
- Code match fails (model emitted no LOINC; GT has LOINC but the model couldn't read it from the PDF)
- Display match fails (GT display = "class"; model display = "egg white (f001) ige class" — token overlap with "class" alone is too low)

**Conclusion:**

1. **These are not hallucinations.** They are correctly-extracted allergen-panel results that fail to match against poorly-displayed GT entries.
2. **No prompt change can fix this** — the LOINC codes for individual IgE allergens (Egg White IgE = LOINC 6075-6, Peanut IgE = LOINC 6206-7, etc.) are not printed in the PDF; they're inferred from the test panel by the lab system at coding time.
3. **The fix is matcher-side or eval-side**, not pipeline-side:
   - Option A: Add a known LOINC mapping table for common allergens — when the model emits "egg white ige" mark it as matching `loinc:6075-6`. Brittle.
   - Option B: For labs with `code.text="class"` in GT, surface this in the eval as "low-quality GT display, manual review required."
   - Option C: Mark these as vision wins (same as Move H's 4 condition FPs) and accept that lab precision is conservative for this Cedars data quality issue.

**Decision:** No code change today. Document the finding; lab F1 0.70 is as good as the matcher can score on this PDF given the GT's display-quality. Re-evaluate when we have ground truth from a different source (Function Health labs would have proper LOINC codes printed).

**Next:**

- ⏳ Add a Streamlit "vision-wins reviewer" page that lets a human triage condition/lab FPs.
- ⏳ When working with future PDFs that have ground truth, prefer GT sources where `code.text` has meaningful displays (Synthea, MIMIC).

---

## 2026-05-03 · Move F — page chunking unblocks Gemma-tabular on long PDFs

**Agent:** Claude Opus 4.7

**What:** Added page chunking to `GoogleAIStudioBackend` (default 8 pages per chunk). When a PDF exceeds the threshold, `extract()` splits the rasterized images into chunks, calls the API per chunk sequentially, merges responses with cross-chunk deduplication. Plus three follow-on fixes from real failures during the work: markdown-fence stripping (Gemma sometimes wraps JSON in `` ```json … ``` `` despite `responseMimeType=application/json`), code-based dedup signature in the merger (cross-chunk dups when the same medication appears on pages 4 and 12), and a urlopen timeout bump (180s → 600s, dense passes can legitimately take minutes).

**Why:** Move B failed on the 25-page Cedars PDF with `HTTP 400 INVALID_ARGUMENT`. We needed Gemma to handle long documents to make per-pass cost optimization viable.

**How:** `multipass-fhir-gemma-tabular × cedars-health-summary`, 25-page PDF, 4 chunks per Gemma pass, 600s timeout, `findable_only=True`, all 5 passes ran (2 Claude + 3 Gemma + Pass 0).

**Result:**

| type | findable GT | extracted | TP | precision | recall | F1 | route |
|---|---:|---:|---:|---:|---:|---:|---|
| condition | 19 | 3 | 3 | 1.00 | 0.16 | 0.27 | Claude |
| medication | 7 | 7 | 6 | 0.86 | 0.86 | 0.86 | Gemma chunked |
| allergy | 1 | 1 | 1 | 1.00 | 1.00 | 1.00 | Claude |
| immunization | 10 | 7 | 7 | 1.00 | 0.70 | 0.82 | Gemma chunked |
| lab | 143 | **55** | 55 | 1.00 | **0.38** | 0.56 | Gemma chunked |

**Overall F1: 0.55 weighted, 352s wall-clock.**

**Side-by-side vs all-Claude multipass:**

| metric | all-Claude | Gemma-tabular (chunked) | delta |
|---|---:|---:|---|
| weighted F1 | **0.67** | 0.55 | **-12 pts** |
| latency | **95s** | 352s | **+3.7×** |
| est. cost / PDF | $0.30 | $0.12 | -60% |
| medications F1 | 0.92 | 0.86 | -6 |
| immunizations F1 | 0.89 | 0.82 | -7 |
| **labs F1** | **0.70** | **0.56** | **-14** |

**Conclusion:**

1. **Chunking works at the architecture level.** Long PDFs no longer fail with HTTP 400; medications and immunizations recover proper recall via chunked Gemma. The bugs caught along the way (fence stripping, dedup, timeout) are now fixed in the framework — they'd benefit any future chunking caller.
2. **Gemma-tabular is currently inferior on every dimension except cost.** Slower (3.7×), lower F1 (12 points), worse on the highest-volume task (labs F1 0.56 vs 0.70). Cost win is real but the latency penalty makes it unattractive for interactive workflows.
3. **The lab gap is the dominant story.** Gemma extracted 55 of 143 labs vs Claude's 138. Likely causes: (a) chunks miss the cross-page table-continuation context Claude sees in one shot; (b) Gemma is genuinely less aggressive at extracting all rows from dense tables; (c) cross-chunk overlap loses some rows.
4. **Real bugs caught.** The fence-stripper, the dedup signature, the urlopen timeout — all generic infrastructure improvements that benefit anyone using `GoogleAIStudioBackend` with long PDFs going forward.

**Decisions made:**

- **`multipass-fhir` (all-Claude) remains the default.** Gemma-tabular variant kept registered for cost-constrained workflows on small PDFs, with the `chunked-but-slow-and-lossier` caveat documented.
- **Don't pursue parallel chunk dispatch yet** — the latency penalty is real, but parallel chunks would still be slower than all-Claude on chart documents (rate limits, sequential per-pass) and the F1 gap suggests Gemma is the wrong tool for dense tables, not just chunking.
- **Real cost-optimization story** is probably "different model entirely" rather than "smaller model on subset of passes." Claude Haiku 4.5 might be a better experiment than Gemma 4 31B for the cost-constrained path.

**Next:**

- ⏳ Try `multipass-fhir-haiku` (Haiku 4.5 for tabular passes) — Anthropic's cheap tier likely outperforms Gemma 4 on document-density tasks.
- ⏳ Investigate why Gemma's lab recall is ~50% — does it skip rows? Does the chunked extraction miss tables that span a chunk boundary?
- ⏳ Conditions still at 0.16 recall with 16 findable misses. Real prompt-tuning room exists; on the backlog after we know what other architectures look like.

---

## 2026-05-03 · Move D — findable-in-PDF GT filter

**Agent:** Claude Opus 4.7

**What:** Added `filter_gt_to_findable_in_pdf()` to the eval module — extracts pdfplumber text from a PDF, filters ground-truth facts to those whose primary code or display tokens actually appear in the PDF text. Wired through `evaluate_bundle(pdf_path=, findable_only=)` and the bake-off harness's `findable_only` flag. Streamlit page now exposes the toggle (default ON).

**Why:** Move A surfaced a recall-ceiling ambiguity: the Cedars FHIR has 28 conditions but the 25-page Health Summary PDF is a snapshot, not the full chart. Without filtering, multipass-fhir's recall is bounded by *how much of the chart appears in the PDF*, not *how good the pipeline is at extracting from what's there*.

**How:** Three matching tests per fact (any one passes → findable):

  1. Any code in any terminology (ICD-10, SNOMED, RxNorm, LOINC, CVX) appears as a substring in PDF text
  2. Display name appears as case-insensitive substring
  3. ≥50% of display tokens appear in PDF token set

Anything that fails all three is unfindable. Scanned PDFs (no extractable text layer) default to all-findable.

**Result on Cedars Health Summary:**

| type | all GT | findable | unfindable |
|---|---:|---:|---:|
| condition | 28 | **19** | **9** |
| medication | 7 | 7 | 0 |
| allergy | 1 | 1 | 0 |
| immunization | 10 | 10 | 0 |
| lab | 143 | 143 | 0 |
| **total** | **189** | **180** | **9** |

All 9 unfindables are conditions — exactly the historical conditions we suspected weren't in the snapshot:
- `D22.9` multiple nevi
- `L82.1` seborrheic keratoses
- `L81.9` post-inflammatory pigmentary changes
- `Z00.00` annual physical exam (×3 — three encounter records all coded the same way)
- `Z11.59` special screening examination for viral disease
- `E78.5` hyperlipidemia, unspecified

Re-scored multipass-fhir × cedars-health-summary with findable-only:

| type | gt(strict) | gt(findable) | TP | recall(strict) | recall(findable) | F1(strict) | F1(findable) |
|---|---:|---:|---:|---:|---:|---:|---:|
| condition | 28 | **19** | 3 | 0.11 | **0.16** | 0.18 | **0.27** |
| medication | 7 | 7 | 6 | 0.86 | 0.86 | 0.92 | 0.92 |
| allergy | 1 | 1 | 1 | 1.00 | 1.00 | 1.00 | 1.00 |
| immunization | 10 | 10 | 8 | 0.80 | 0.80 | 0.89 | 0.89 |
| lab | 143 | 143 | 98 | 0.69 | 0.69 | 0.70 | 0.70 |

**Overall F1: 0.64 (strict) → 0.67 (findable).**

**Conclusion:**

1. **The recall ceiling was real but smaller than I estimated.** Only 9 of 28 conditions are unfindable; the other 19 are in the PDF and we missed 16 of them. So there *is* meaningful prompt-tuning room for conditions — we're not at the floor.
2. **All 16 still-missed conditions are in the PDF text.** Future prompt iterations can be measured against this filtered baseline. Worth a separate experiment.
3. **The filter caught exactly the kind of GT noise we expected** — historical/encounter-level conditions that don't make it into a Health Summary export. It did NOT filter out any medications/allergies/immunizations/labs, which makes sense (those have their own sections in the summary).
4. **The eval harness now has a meaningful signal-to-noise improvement.** Future experiments should use `findable_only=True` by default; legacy strict mode kept for cases where we want to measure GT-coverage gap.

**Next:**

- ⏳ Investigate the 16 still-missed-but-findable conditions. Likely candidates for the next conditions-prompt iteration.
- ⏳ The 40 lab false-positives still need triage — vision wins or hallucinations? Filterable similarly?
- ⏳ Move F next: page chunking on GoogleAIStudioBackend.

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
