# PDF Lab Studio — Task Queue

> ⚠️ **SUPERSEDED 2026-05-07** by `.claude/pdf-lab-cli-queue.md`. The user directed agent-first / CLI-driven design rather than a Streamlit-heavy UI. This queue is preserved for reference; tasks here are NOT scheduled for build. See `docs/daily/2026-05-07-ClaudeCode.md` Entry 10 for the reframe.

---


> Test-environment build for the PDF parser. Six builder-sized tasks that compose into a side-by-side, per-PDF, per-model comparison studio with provenance, ground-truth-driven F1, vision-wins triage, and run history. Source spec: `docs/daily/2026-05-07-ClaudeCode.md` Entry 4. Strategic context: the parent-company pitch ("vendor-neutrality with empirical model selection") needs the bake-off to be cheap and routine, not a one-off command-line ritual.

**Status legend:** `Queued` → `In Progress (dispatched YYYY-MM-DD HH:MM)` → `Completed (hash)` / `⚠ In Progress (failed HH:MM)` / `⛔ Blocked (open question #)`

**Kind:** all `builder` (Sonnet) unless noted. None are refiner tasks — this is infra, not polish.

---

## Prerequisites

- **PROMOTE-EXTRACT must ship first.** All paths in this queue assume `lib/extract/` (not `ehi-atlas/ehi_atlas/extract/`). If PROMOTE-EXTRACT slips, the orchestrator either (a) waits, or (b) rewrites these briefs to use the old path — but do not let the studio cement the inverted-dep model.
- **Verify the eval harness is callable from `lib/extract/eval.py` after the move.** A 1-line `from lib.extract.eval import evaluate_bundle` smoke is enough.

---

## PDFLAB-T01 · Per-pass trace logging

- **Status:** Queued
- **Kind:** builder
- **Goal:** Persist full prompt + raw response + token-usage per pass, so any extraction can be replayed/audited later without re-billing the model.
- **Why:** today's cache stores the parsed FHIR result keyed on `(pdf_sha, pass_name, schema_version, backend/model)`, but the *inputs* and *raw outputs* are gone after the call returns. Eval can only see what the parser kept. We need full-fidelity traces to debug bad extractions, compare prompt versions, and feed the eventual vision-wins reviewer.
- **Context files:**
  - `lib/extract/pipelines/multipass_fhir.py` (pass-dispatch loop)
  - `lib/extract/pdf.py` (`VisionBackend` Protocol + `AnthropicBackend.extract`, `GoogleAIStudioBackend.extract`)
  - `lib/extract/cache.py` (existing cache shape — match it)
  - `docs/architecture/extraction/PDF-PROCESSOR.md` Decision 6 (eval is load-bearing)
- **What to build:** new module `lib/extract/run_logger.py`. Exposes `RunLogger(run_id: str, root: Path)` with method `log_pass(pass_name: str, prompt: str | list[dict], response: dict, usage: dict, latency_ms: float)`. Writes:
  - `runs/{run_id}/{pass_name}/prompt.txt`
  - `runs/{run_id}/{pass_name}/response.json`
  - `runs/{run_id}/{pass_name}/usage.json`
  - `runs/{run_id}/manifest.json` (PDF SHA, pipeline name, started_at, finished_at, list of passes)
- **Wire it:** thread an optional `run_logger: RunLogger | None = None` parameter through `multipass_fhir.MultiPassFHIRPipeline.extract`. When present, log every pass. When absent (the default — preserves current behavior), do nothing.
- **Files you may touch:** `lib/extract/run_logger.py` (new), `lib/extract/pipelines/multipass_fhir.py`, `lib/extract/__init__.py` (export), `lib/tests/test_run_logger.py` (new)
- **Files you must NOT touch:** `api/`, `app/`, any pipeline file other than `multipass_fhir.py`, the cache module
- **Smoke test:**
  ```bash
  uv run pytest lib/tests/test_run_logger.py -q
  ```
  Test must: instantiate `RunLogger` with a tmp dir, call `log_pass` once with synthetic args, assert all four files exist and parse, assert `manifest.json` contains the pass name.
- **Acceptance:** running `multipass-fhir` against any cached PDF with a `RunLogger` produces a populated `runs/{run_id}/` tree; running without one produces zero new files. No behavior change to the parsed FHIR Bundle.

---

## PDFLAB-T02 · Studio page shell + bring-your-own-PDF upload

- **Status:** Queued
- **Kind:** builder
- **Depends on:** none (T01 is parallel-safe)
- **Goal:** A new Streamlit page where a user uploads an arbitrary PDF (and optionally a ground-truth FHIR Bundle JSON), and the upload is persisted under `data/pdf-lab/{run_id}/` for downstream extraction.
- **Why:** today's bake-off only operates on the corpus fixtures. Adding a real PDF means dropping it into `corpus/_sources/` and wiring it through. We need the path "user opens browser → drops PDF → it's queued for extraction" to be one minute, not one hour.
- **Context files:**
  - `ehi-atlas/app/pages/05_Pipeline_Bakeoff.py` (closest existing page — match its style)
  - `ehi-atlas/app/pages/03_PDF_Lab.py` (single-PDF interactive view — pattern reference)
  - `ehi-atlas/CLAUDE.md` (Streamlit app conventions)
- **What to build:** `ehi-atlas/app/pages/07_PDF_Lab_Studio.py`
  - File uploader (PDF only, ≤25 MB)
  - Optional file uploader for ground-truth Bundle (JSON)
  - On submit: generate `run_id = f"{utc-iso-no-colons}-{pdf_sha8}"`, persist:
    - `data/pdf-lab/{run_id}/source.pdf`
    - `data/pdf-lab/{run_id}/ground_truth.json` (if provided)
    - `data/pdf-lab/{run_id}/manifest.json` (uploaded_at, original_filename, pdf_sha, ground_truth_provided)
  - Past-runs section: list `data/pdf-lab/*/manifest.json` newest-first with original filename, date, ground-truth status, link to "open run" (placeholder action — wired in T03)
- **Files you may touch:** `ehi-atlas/app/pages/07_PDF_Lab_Studio.py` (new), `ehi-atlas/.gitignore` (add `data/pdf-lab/` if not already covered)
- **Files you must NOT touch:** other Streamlit pages, the pipelines module
- **Smoke test:**
  ```bash
  uv run streamlit run ehi-atlas/app/pages/07_PDF_Lab_Studio.py --server.headless true --server.port 8599 &
  sleep 5 && curl -sf http://127.0.0.1:8599/ -o /dev/null && echo "page renders" && kill %1
  ```
  Then a manual upload check: drop a small PDF, verify `data/pdf-lab/{run_id}/source.pdf` exists.
- **Acceptance:** page renders without errors, upload persists to disk with the documented manifest shape, past-runs section enumerates prior uploads.

---

## PDFLAB-T03 · Pipeline matrix runner

- **Status:** Queued
- **Kind:** builder
- **Depends on:** T01 (logging) + T02 (page shell)
- **Goal:** From a run page, select N pipelines × per-pass model overrides, kick off extraction in the background, persist cell artifacts under the run dir.
- **Why:** the bake-off harness exists; the studio just needs to drive it from the UI and store outputs in the run-scoped layout (not the global cache).
- **Context files:**
  - `lib/extract/bake_off.py` (`bake_off()` function + `BakeoffCell` dataclass)
  - `lib/extract/pipelines/__init__.py` (`list_pipelines()` registry)
  - `docs/architecture/extraction/PDF-PROCESSOR.md` Decision 4 (per-pass model selection) + Decision 5 (Pluggable pipelines)
  - `lib/extract/run_logger.py` (from T01)
- **What to build:** in `07_PDF_Lab_Studio.py`, after a run is selected:
  - Pipeline checkbox grid sourced from `list_pipelines()`
  - Per-pass model override dropdowns (default: pipeline's declared default; alternates: any backend listed in `lib/extract/pdf.py`)
  - "Run selected cells" button — kicks off `bake_off()` in a Streamlit background thread or `subprocess.Popen` (whichever the existing pages use); each cell writes to `data/pdf-lab/{run_id}/cells/{pipeline}__{model_signature}/` containing `bundle.json`, `runs/...` (logging from T01), and `cell_metadata.json` (started_at, finished_at, cost_estimate, latency_ms, error if any)
  - Live progress: poll cell dirs, update status table (queued/running/done/failed)
- **Files you may touch:** `ehi-atlas/app/pages/07_PDF_Lab_Studio.py`, possibly a small helper `ehi-atlas/app/_pdf_lab_helpers.py` for shared logic
- **Files you must NOT touch:** `lib/extract/bake_off.py` (use as-is — if it needs an API change, that's a separate task)
- **Smoke test:**
  ```bash
  uv run python -c "from lib.extract.bake_off import bake_off; from lib.extract.pipelines import list_pipelines; print(list(list_pipelines().keys()))"
  ```
  Then end-to-end: upload a PDF via T02, select `multipass-fhir` only, click run, verify `data/pdf-lab/{run_id}/cells/multipass-fhir__claude-sonnet-4-6/bundle.json` exists and parses as a FHIR Bundle.
- **Acceptance:** matrix grid renders, kicking off a single cell produces the documented artifact tree, errors surface in the UI rather than crashing the page.

---

## PDFLAB-T04 · Side-by-side comparison view

- **Status:** Queued
- **Kind:** builder
- **Depends on:** T03
- **Goal:** Given a run with ≥2 cells, render a per-resource-type table showing what each pipeline extracted, with click-through to provenance.
- **Why:** the eval harness already computes per-resource-type F1; we surface it next to the actual extractions so a reviewer can see *why* a number is what it is.
- **Context files:**
  - `lib/extract/eval.py` (`evaluate_bundle` — match cells to ground truth)
  - `docs/architecture/extraction/PDF-PROCESSOR.md` "Bake-off results" section (table format reference)
  - `lib/extract/pipelines/multipass_fhir.py` (provenance shape — `meta.extension` with page/bbox)
- **What to build:** in `07_PDF_Lab_Studio.py`, a "Compare cells" tab when ≥2 cells exist:
  - Top: per-resource-type F1 / precision / recall table, columns = cells, rows = (medication, condition, allergy, immunization, lab observation, procedure)
  - Bottom: per-resource detail. Pick a resource type → list the union of all extracted resources across cells, with checkboxes/badges showing which cells extracted each. Click a row → expand to show the FHIR JSON, provenance (page+bbox), and the source PDF region (image clip if feasible; otherwise just page number link).
  - When ground truth is present, mark resources as `match` / `extra` / `missing`.
- **Files you may touch:** `ehi-atlas/app/pages/07_PDF_Lab_Studio.py`, `ehi-atlas/app/_pdf_lab_helpers.py`
- **Files you must NOT touch:** the eval module
- **Smoke test:**
  ```bash
  uv run pytest ehi-atlas/tests/test_pdf_lab_compare.py -q
  ```
  Test must: build a synthetic run dir with 2 cells of known content + ground truth, call the comparison-data builder helper, assert F1 numbers and resource-row classification match expected.
- **Acceptance:** comparison tab renders for any run with ≥2 cells, F1 numbers match a direct `evaluate_bundle` call, resource detail rows show provenance correctly.

---

## PDFLAB-T05 · Vision-wins reviewer

- **Status:** Queued
- **Kind:** builder
- **Depends on:** T04
- **Goal:** Surface "extras" (resources extracted but not in ground truth) and let the user classify each as `valid_extra`, `hallucination`, or `out_of_scope`. Persist verdicts. Provide a "human-adjusted F1" recompute.
- **Why:** today the eval treats every extra as a precision penalty. PDF-PROCESSOR.md's bake-off section explicitly notes that 4 of 4 condition extras and 41 of 41 lab extras on Cedars are valid clinical findings the structured EHR never coded. Without a reviewer, the wedge story is anecdotal.
- **Context files:**
  - `lib/extract/eval.py` (current eval — note where extras are counted)
  - `docs/architecture/extraction/PDF-PROCESSOR.md` "Bake-off results — 2026-05-03" section (this is the use case)
- **What to build:** new tab "Vision-wins review":
  - Per cell, list all extras with FHIR JSON + provenance (page+bbox)
  - Three-button classifier per row: `valid_extra` / `hallucination` / `out_of_scope`
  - Verdicts persist to `data/pdf-lab/{run_id}/cells/{cell_id}/verdicts.json`
  - Add `evaluate_bundle_with_verdicts(bundle, ground_truth, verdicts) -> EvalResult` to `lib/extract/eval.py` — same shape, but `valid_extra` removed from FP count, `hallucination` retained, `out_of_scope` removed entirely
  - Comparison tab (T04) shows both raw F1 and human-adjusted F1 when verdicts exist
- **Files you may touch:** `ehi-atlas/app/pages/07_PDF_Lab_Studio.py`, `lib/extract/eval.py` (add the new function — do not change the existing one), `lib/tests/test_eval_with_verdicts.py` (new)
- **Files you must NOT touch:** existing `evaluate_bundle` signature
- **Smoke test:**
  ```bash
  uv run pytest lib/tests/test_eval_with_verdicts.py -q
  ```
  Test: build a bundle with 2 extras, mark one `valid_extra` and one `hallucination`, assert raw precision < adjusted precision, assert hallucination still penalizes, assert out_of_scope removes the row entirely.
- **Acceptance:** classifier persists, eval recomputes correctly, comparison tab shows the human-adjusted column.

---

## PDFLAB-T06 · Run history + cost/latency dashboard

- **Status:** Queued
- **Kind:** builder
- **Depends on:** T03
- **Goal:** Append-only run log + a chart-driven dashboard showing cost / latency / F1 per pipeline over time, so we can spot regressions and tell the parent-company pitch story with real numbers.
- **Why:** "trust me, the bake-off says X" is a weaker pitch than "here's the chart of every bake-off we've run." Also the only way to catch model-drift regressions is to track the metric over time.
- **Context files:**
  - `lib/extract/bake_off.py` (`BakeoffCell` shape — what numbers we have)
  - `docs/architecture/extraction/PIPELINE-LOG.md` (style reference for journaling — but this is data, not prose)
- **What to build:**
  - On every cell completion in T03, append a JSON line to `data/pdf-lab/bake_off_runs.jsonl` with: `run_id`, `cell_id`, `pipeline`, `model_signature`, `pdf_sha`, `started_at`, `finished_at`, `latency_ms`, `cost_estimate_usd`, `weighted_f1` (if ground truth), `per_resource_f1` (dict)
  - New tab "History":
    - Filter controls: pipeline, model, date range
    - Three line charts: weighted F1 over time, latency over time, cost over time
    - "Pin baseline" — select a run as baseline; show delta vs baseline for the most recent run per pipeline
- **Files you may touch:** `ehi-atlas/app/pages/07_PDF_Lab_Studio.py`, `lib/extract/run_history.py` (new — append + read helpers), `lib/tests/test_run_history.py`
- **Files you must NOT touch:** prior tabs (only consume the history file, don't restructure)
- **Smoke test:**
  ```bash
  uv run pytest lib/tests/test_run_history.py -q
  ```
  Test: append 5 synthetic runs, read back, filter by pipeline, assert ordering and counts. Plus manual: history tab renders charts when the file has ≥2 rows.
- **Acceptance:** every T03 cell completion appends one line, history tab renders, baseline-diff math is correct.

---

## After T06 — what we have

- Upload arbitrary PDF + optional ground truth in <60 sec
- Run any subset of registered pipelines × per-pass model overrides
- See per-resource-type F1, cost, latency, and human-adjusted-F1 per cell
- Triage vision-wins so eval is honest about valid extras
- Track every bake-off across time; detect regressions

What we still don't have (deferred — separate briefs when we want them):

- **PDFLAB-T07** — `OpenAIBackend` adapter (~150 lines following `VisionBackend` Protocol). Lets GPT-4o into the bake-off.
- **PDFLAB-T08** — `OllamaBackend` / `vLLMBackend` for self-hosted Gemma / Qwen / Llama vision.
- **PDFLAB-T09** — Cloud-NER pipeline shape (PDF → OCR → AWS Comprehend Medical / Google Healthcare NLP / Azure Text Analytics → FHIR assembler). One pipeline class, three provider configs.
- **PDFLAB-T10** — Promote the studio from Streamlit to a React route in `app/` so judges can use it during the demo. Streamlit-first earns the right to do this.

---

## Open questions parked

1. Should run artifacts go to `data/pdf-lab/` (gitignored, lost on container rebuild) or to a persistent volume / S3? For Phase 1, gitignored is fine; for production a persistent store is needed.
2. Cost estimate formulas — pull from the actual API responses (Anthropic returns `usage.input_tokens` etc.) or hardcode per-model unit prices? Lean: actual API responses where possible, hardcoded fallback table for models without usage in the response.
3. Streamlit background thread vs subprocess for cell execution — match whatever `05_Pipeline_Bakeoff.py` does today.

---

*Created 2026-05-07. Six builder-sized tasks. Total estimate: 3–5 days of focused work, sized so each task fits one builder invocation.*
