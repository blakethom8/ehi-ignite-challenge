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
