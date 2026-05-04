# Extraction Pipelines — contributor guide

This directory holds the PDF → FHIR Bundle pipelines that the Atlas bake-off harness compares. Each subdirectory or module is one architecture: single-pass vision, multi-pass vision, OCR-then-text, hybrid, anything new.

**If you're an external agent or a teammate implementing a new pipeline, this is the only doc you need to read.** You don't need to understand the rest of the Atlas codebase — the contract is intentionally small.

For the *why* behind this design (instead of the how), see [`docs/architecture/PDF-PROCESSOR.md`](../../../../docs/architecture/PDF-PROCESSOR.md). The TL;DR: we don't pick a single pipeline architecture. We measure, compare, and ship the architecture that wins on F1, cost, and latency for our actual data.

---

## The contract — five things your pipeline must do

### 1. Implement `ExtractionPipeline` (a Protocol)

```python
from pathlib import Path
from ehi_atlas.extract.pipelines import (
    ExtractionPipeline,
    PipelineMetadata,
    register,
)


@register
class MyPipeline:
    metadata = PipelineMetadata(
        name="my-pipeline",                         # stable, lowercase, hyphenated
        description="One-line summary of approach.",
        architecture="multipass-vision",            # or "single-pass-vision",
                                                    #    "ocr-text", "hybrid"
        primary_backends=["anthropic"],             # which backends you call
        estimated_cost_per_pdf_usd=0.15,            # rough $$ per extraction
    )

    def extract(self, pdf_path: Path) -> dict:
        # ... your implementation ...
        return bundle_dict  # FHIR Bundle (R4 / US Core profiled)
```

The `@register` decorator adds your class to the global pipeline registry at import time. The bake-off harness discovers your pipeline via that registry — no other wiring needed.

### 2. Return a valid FHIR Bundle

Your `extract()` method returns a Python dict shaped like a FHIR R4 Bundle:

```python
{
    "resourceType": "Bundle",
    "type": "document",
    "entry": [
        {"resource": {"resourceType": "Patient", ...}},
        {"resource": {"resourceType": "Condition", ...}},
        {"resource": {"resourceType": "Observation", ...}},
        # ... etc
    ],
}
```

The bake-off harness validates against US Core profiles before scoring. Pipelines that emit invalid Bundles fail before reaching the eval — surface a clear error rather than letting the validator report it for you.

**Resource types we score on today** (per [`eval.py`](../eval.py)):

- `Condition`
- `MedicationRequest` (and we resolve `medicationReference` against any `Medication` resources you emit)
- `AllergyIntolerance`
- `Immunization`
- `Observation` with `category=laboratory`

Other resource types are accepted in the Bundle but currently ignored by the eval. Emit them if your architecture naturally produces them — adding them to the eval is straightforward when we expand coverage.

### 3. Carry Provenance metadata on every resource

Every FHIR resource you emit MUST include:

```python
{
    "resourceType": "Condition",
    # ... clinical content ...
    "meta": {
        "source": "extracted://lab-pdf/<original-filename-stem>",
        "extension": [
            {
                "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-model",
                "valueString": "<backend>/<model>",
            },
            {
                "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-confidence",
                "valueDecimal": 0.92,
            },
            {
                "url": "https://ehi-atlas.example/fhir/StructureDefinition/extraction-prompt-version",
                "valueString": "v0.1.0",
            },
            {
                "url": "https://ehi-atlas.example/fhir/StructureDefinition/source-locator",
                "valueString": "page=2;bbox=72,574,540,590",  # PDF user units, bottom-left origin
            },
        ],
    },
}
```

These five extensions are what the harmonizer reads to construct Provenance edges all the way back to bbox-on-page. Without them, the canonical patient bundle can't render lineage. **This isn't optional.**

If your pipeline can't determine an exact bbox (e.g. an OCR-first pipeline only knows page numbers), emit `source-locator` with just the page (`"page=2"`) — the framework's existing bbox calibration step (in [`pdf.py`](../pdf.py)) will look up the row bbox via pdfplumber if your pipeline emits the test name and the page.

### 4. Be deterministic for the same input

If `extract(pdf_path)` is called twice with the same PDF, same configuration, same code version — the output should match. This is non-negotiable for two reasons:

- The eval harness uses replay to catch regressions
- The cache layer (if you implement caching) requires it

Models are stochastic, so "deterministic" means "given a configured backend that's set to temperature=0 and a stable schema/prompt version, the output is reproducible enough for our cache key to be valid." If your model's stochasticity is meaningfully visible in F1, that's a finding to surface — don't hide it behind randomization.

### 5. Cache where it makes sense, but don't require a warm cache

Cache aggressively to avoid burning quota on repeat eval runs. Recommended location:

```
ehi-atlas/ehi_atlas/extract/.cache/pipelines/<pipeline-name>/<pdf-sha256>.json
```

(Already gitignored.) Use the existing `ehi_atlas.extract.cache.ExtractionCache` if you want — it's content-hash keyed and survives across sessions.

But the bake-off harness will sometimes pass `skip_cache=True` to force a live run. Your `extract()` method should accept this via a kwarg or via a constructor flag — see how `SinglePassVisionPipeline` does it once it lands.

---

## Useful infrastructure already in place

You don't need to rebuild any of this:

| Module | What it gives you |
|---|---|
| [`ehi_atlas.extract.pdf`](../pdf.py) | `VisionBackend` Protocol, `AnthropicBackend`, `GoogleAIStudioBackend` (with automatic page chunking for long PDFs), `get_backend()` selector, response-coercion helpers (`_coerce_stringified_subobjects`, `_unwrap_extraction_envelope`), bbox calibration via pdfplumber (`_calibrate_bboxes_via_layout`). Use these. |
| [`ehi_atlas.extract.layout`](../layout.py) | PDF rasterization + per-page text+bbox extraction via pdfplumber. The `extract_layout()` function returns a `DocumentLayout` you can use to look up bboxes for any text on any page. |
| [`ehi_atlas.extract.cache`](../cache.py) | Content-hash cache, atomic writes, deterministic-replay guarantee. |
| [`ehi_atlas.extract.uploads`](../uploads.py) | If you need to round-trip arbitrary PDFs through the corpus. |
| [`ehi_atlas.extract.eval`](../eval.py) | The eval harness — what the bake-off uses to score you. Includes `filter_gt_to_findable_in_pdf()` so recall is measured against facts actually in the PDF, not the patient's full chart history. Worth reading to see what your output gets compared against. |
| [`ehi_atlas.extract.bake_off`](../bake_off.py) | The bake-off harness. `bake_off(pipelines, pairs, findable_only=True)` runs every (pipeline × pdf) cell, scores against ground truth, returns a list of `BakeoffCell` ready for markdown rendering or Streamlit display. |

---

## How the bake-off harness consumes your pipeline

```python
from ehi_atlas.extract.pipelines import get
from ehi_atlas.extract.eval import evaluate, format_markdown

pipeline_cls = get("my-pipeline")
pipeline = pipeline_cls()  # construct with default config

bundle = pipeline.extract(pdf_path)
# Validate Bundle against US Core (skipped here — bake-off harness handles it)

eval_report = evaluate(
    ground_truth=ground_truth_clientfullehr_json,
    extraction=bundle_to_extraction_result(bundle),  # bridging adapter
    extraction_label=pipeline.metadata.name,
    ground_truth_label="cedars-sinai-fhir",
)

print(format_markdown(eval_report))
```

The bake-off page in Streamlit (`05_Pipeline_Bakeoff.py` after K.3) shows the `pipeline × PDF` matrix with F1 / cost / latency / failure cells.

---

## Tips from the existing pipelines

These are observations from building the baseline — feel free to apply or ignore.

- **Multi-task prompts underperform single-task prompts.** If your architecture asks one LLM call to emit Conditions AND Medications AND Labs, expect lower recall than running each as its own pass. The eval harness will surface this.
- **A "document context" pre-pass is worth its weight.** Extract patient ID, encounter date, lab name, ordering provider once at the top of the PDF. Pass that context into every subsequent pass. Cross-page tables stop being a problem when every emitted resource carries the document-level context.
- **bbox calibration via pdfplumber is free quality.** Whatever bbox the model emits, run it through `_calibrate_bboxes_via_layout` from [`pdf.py`](../pdf.py). The function looks up the row bbox via pdfplumber's text extraction and replaces what the model emitted. Both Claude and Gemma converge on identical bboxes after this step.
- **If you call multiple passes, dispatch them via `asyncio.gather()`.** Six 20-second passes finish in ~25 seconds wall-clock if parallelized. Sequential is ~120 seconds. The Anthropic and Google AI Studio APIs both handle concurrent requests fine.

---

## Submitting a pipeline

If you're contributing from outside this repo (Cursor session, Codex run, Aider session, etc.):

1. Implement your pipeline as a single Python module under `ehi_atlas/extract/pipelines/`.
2. Add an import line in `pipelines/__init__.py` so the registry picks it up.
3. Run `uv run --quiet pytest tests/extract/ -q` to confirm nothing breaks.
4. Run the bake-off against at least one PDF + ground-truth pair to confirm your `extract()` returns a valid Bundle.
5. Open a PR or hand back the diff. The Atlas team runs the full bake-off; results land in [`docs/architecture/PDF-PROCESSOR.md`](../../../../docs/architecture/PDF-PROCESSOR.md) as a decision-log entry.

If your pipeline beats the current default on F1, cost, or latency for our PDFs — it ships.

---

## Where the framework does NOT help you

Honestly:

- We do not validate that your `extract()` is fast or efficient. If you make 50 LLM calls per PDF, the eval will run; it'll just be expensive.
- We do not provide a built-in OCR engine. Wrap an existing one (MinerU, Marker, olmOCR, Mistral OCR) per-pipeline if you need OCR.
- We do not score clinical synonymy. "Hyperlipidemia" and "high cholesterol" only match in the eval if they share a code or a Jaccard token overlap above 0.5. If your pipeline emits `code.text` only and no terminology codes, eval recall will look weak — emit codes.
- We do not handle scanned-image-only PDFs gracefully. Today the layout extractor raises if a page has no extractable text. OCR-first pipelines bypass this; vision pipelines might.

The framework is intentionally thin. Pipelines are where the interesting work happens.
