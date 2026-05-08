# PDF Lab — CLI / Agent-First — Task Queue

> Supersedes `pdf-lab-studio-queue.md` (Streamlit-heavy). Focus is **agent-first**: a library + CLI that captures full traces, compares runs, and emits markdown reports the orchestrator (Claude) can paste into conversations to share findings with the user.

> Strategic context: `docs/daily/2026-05-07-ClaudeCode.md` Entry 10. Branch: `feature/code-resolution-loinc` (continues stacking).

**Status legend:** `Queued` → `In Progress` → `Completed (<hash>)`
**Builder:** `phase1-builder`. Each brief is self-contained.

---

## Why this queue exists

After the 5-pipeline architecture build (default / scout / bidi-scout / gemma-tabular / single-pass), we have hypotheses about which architecture wins on which PDF type — but **no measurement surface**. This queue builds that surface. The user explicitly directed agent-first, CLI-driven design rather than a UI-heavy Streamlit studio.

The agent-loop the user described:
1. Claude runs a pipeline (or several) on a PDF
2. Claude reads the resulting traces / metrics
3. Claude shares findings with the user via markdown
4. User decides next experiment

Everything in this queue serves that loop.

---

## Disk layout target

```
data/pdf-lab/
├── runs.jsonl                                 ← append-only run index
└── runs/
    └── 2026-05-07T18-30-00_a3b2c1_multipass-fhir/
        ├── manifest.json
        ├── source.pdf
        ├── ground-truth.json (optional)
        ├── bundle.json
        ├── eval.json
        └── traces/
            ├── document_context/
            │   ├── prompt.txt
            │   ├── response.json
            │   ├── usage.json
            │   └── extraction.json
            ├── conditions/...
            └── ... (one dir per pass)
```

Run-id format: `<utc-iso-no-colons>_<pdf-sha-prefix>_<pipeline-name>` — sortable, human-readable, deterministic.

---

## LAB-T01 · `RunRecorder` + on-disk artifact layout

- **Status:** Queued
- **Goal:** A library class that captures everything for a single pipeline run: per-pass prompts, raw responses, token usage, latency, cost, parsed extraction, final bundle, ground truth (optional). Persists under `data/pdf-lab/runs/<run-id>/` with the documented layout.
- **Files you may touch:** `lib/extract/lab/__init__.py` (new), `lib/extract/lab/recorder.py` (new), `lib/tests/test_extract/test_lab_recorder.py` (new). Mirror the directory pattern of `lib/extract/terminology/` (existing precedent for sub-package).
- **Files you must NOT touch:** any pipeline code; any `api/`; the existing queue files.

### What to build

#### Module structure
```
lib/extract/lab/
├── __init__.py        ← exports RunRecorder, RunArtifact dataclasses
└── recorder.py        ← the implementation
```

#### Public API

```python
@dataclass
class TraceEntry:
    pass_name: str
    prompt: str
    response: dict           # raw LLM response (Anthropic / Google AI Studio shape)
    usage: dict              # {input_tokens, output_tokens, latency_ms, cost_usd}
    extraction: dict | None  # parsed XExtraction output (model_dump)


@dataclass
class RunManifest:
    run_id: str
    pipeline_name: str
    pdf_path: str             # source PDF path (absolute)
    pdf_sha256: str
    ground_truth_path: str | None
    started_at: str           # ISO 8601
    finished_at: str | None   # ISO 8601 (None if still running)
    cost_usd: float
    latency_ms: int
    status: Literal["running", "succeeded", "failed"]
    error: str | None


class RunRecorder:
    """Captures per-run artifacts to disk under data/pdf-lab/runs/<run-id>/.

    Usage:
        recorder = RunRecorder.start(
            pipeline_name="multipass-fhir",
            pdf_path=Path("..."),
            ground_truth_path=Path("..."),
        )
        # ... pipeline calls recorder.log_pass(...) for each pass ...
        recorder.finish(bundle=bundle_dict, eval_result=eval_dict)
    """

    def __init__(self, manifest: RunManifest, root: Path) -> None: ...

    @classmethod
    def start(cls, *, pipeline_name: str, pdf_path: Path,
              ground_truth_path: Path | None = None,
              root: Path | None = None) -> "RunRecorder":
        """Creates the run directory + manifest.json. Returns a recorder."""

    def log_pass(self, *, pass_name: str, prompt: str,
                 response: dict, usage: dict,
                 extraction: dict | None = None) -> None:
        """Persists prompt.txt, response.json, usage.json, extraction.json
        under traces/<pass_name>/. Updates running cost/latency totals on
        manifest.json (rewritten atomically)."""

    def finish(self, *, bundle: dict, eval_result: dict | None = None,
               status: Literal["succeeded", "failed"] = "succeeded",
               error: str | None = None) -> None:
        """Writes bundle.json + eval.json (if provided), finalizes
        manifest.json with finished_at/status, appends a line to
        runs.jsonl index."""

    @property
    def run_id(self) -> str: ...

    @property
    def root(self) -> Path: ...
```

Run-id derivation in `start()`:
```python
import hashlib, datetime
sha = hashlib.sha256(pdf_path.read_bytes()).hexdigest()[:6]
ts = datetime.datetime.utcnow().strftime("%Y-%m-%dT%H-%M-%S")
run_id = f"{ts}_{sha}_{pipeline_name}"
```

#### Default root

`data/pdf-lab/runs/` (gitignored under existing `data/` rules). Optional `root` parameter for tests.

### Tests to write (in `lib/tests/test_extract/test_lab_recorder.py`)

Use a `tmp_path` fixture (pytest built-in).

1. `test_recorder_start_creates_run_dir` — `RunRecorder.start(...)` creates `<root>/<run-id>/manifest.json` with `status="running"`
2. `test_recorder_run_id_is_deterministic_from_pdf_sha` — same PDF + same pipeline + same UTC time → same run_id format (just check it contains the SHA prefix and pipeline name)
3. `test_log_pass_persists_all_four_files` — call `log_pass(pass_name="conditions", ...)` → `traces/conditions/prompt.txt`, `response.json`, `usage.json`, `extraction.json` all exist with correct content
4. `test_log_pass_updates_running_cost_and_latency` — log two passes with cost 0.05 and 0.10; manifest.cost_usd == 0.15
5. `test_finish_writes_bundle_and_eval` — call `finish(bundle={...}, eval_result={...})` → `bundle.json` and `eval.json` present
6. `test_finish_appends_to_runs_jsonl` — runs.jsonl gets one line per finished run; line is valid JSON matching manifest fields
7. `test_finish_marks_status_succeeded` — manifest.status flips to "succeeded"
8. `test_finish_with_failure` — `status="failed", error="..."` → manifest reflects it
9. `test_extraction_optional_on_log_pass` — log_pass with extraction=None → no extraction.json file

### Smoke test
```bash
uv run --project /Users/blake/Repo/ehi-ignite-challenge pytest lib/tests/test_extract/ api/tests/test_harmonize_api.py api/tests/test_context_builder.py -q
```

### Commit message format
```
feat(lab-t01): RunRecorder + run-artifact disk layout

New library at lib/extract/lab/ for the PDF Lab CLI. RunRecorder
captures per-run artifacts to disk under data/pdf-lab/runs/<run-id>/:
  - manifest.json (pipeline, PDF SHA, timing, cost, status)
  - source.pdf reference
  - ground-truth.json (optional)
  - bundle.json (final FHIR Bundle output)
  - eval.json (F1 + bundle-shape metrics)
  - traces/<pass-name>/ (prompt.txt, response.json, usage.json,
    extraction.json per pass)

Run IDs are deterministic: {utc-iso-no-colons}_{pdf-sha-prefix}_{pipeline}.
runs.jsonl is an append-only index for the CLI's `list` subcommand
(LAB-T06).

Tests: 9 new in test_lab_recorder.py covering start/log/finish
lifecycle, manifest updates, file persistence, jsonl append.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## LAB-T02 · Wire `RunRecorder` into `MultiPassFHIRPipeline.extract()`

- **Status:** Queued
- **Depends on:** LAB-T01
- **Goal:** Thread the recorder through extraction so every pipeline run produces full traces. Optional parameter — default `None` preserves existing behavior; pipelines used outside the lab don't pay any cost.

### What to build

#### Modify `MultiPassFHIRPipeline.extract()` signature

```python
def extract(
    self,
    pdf_path: Path,
    *,
    recorder: RunRecorder | None = None,
) -> dict:
    ...
```

#### Hook points

Inside `_run_pass`/`_invoke_pass_0` (or whichever method actually invokes the LLM), after the call returns, call:

```python
if recorder is not None:
    recorder.log_pass(
        pass_name=pass_name,
        prompt=full_system_prompt,
        response=raw_llm_response,
        usage={
            "input_tokens": ...,
            "output_tokens": ...,
            "latency_ms": ...,
            "cost_usd": ...,
        },
        extraction=parsed_pydantic_output.model_dump() if parsed else None,
    )
```

Cost computation uses Anthropic's published rates per model — encapsulate in a small helper `_estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float`. Lookup table for known models, conservative default otherwise.

#### Bundle finalization

At the end of `extract()`, if recorder is provided, call `recorder.finish(bundle=bundle)`. Don't call `eval_result` here — that's LAB-T05's responsibility.

### Files you may touch
- `lib/extract/pipelines/multipass_fhir.py`
- `lib/extract/lab/cost.py` (new — small helper for token-cost estimation)
- `lib/tests/test_extract/test_lab_pipeline_tracing.py` (new)

### Files you must NOT touch
- The pipeline registry / Protocol
- Other pipeline classes (the recorder hook on the parent applies to all subclasses)
- `lib/extract/eval.py`
- `.claude/pdf-lab-cli-queue.md`

### Tests to write

Use a synthetic backend that returns deterministic responses (no real LLM calls). Pattern:

```python
class _StubBackend:
    def call(self, *, prompt, image_data, schema, ...):
        # return a synthetic response shaped like the real backend
        ...
```

Or mock at the HTTP layer if there's an existing pattern. Match what the existing `test_pdf.py` does for backend mocking.

Required test cases:

1. `test_extract_with_recorder_writes_traces_for_each_pass` — running with recorder produces a `traces/<pass-name>/` directory for each pass that ran
2. `test_extract_without_recorder_unchanged_behavior` — existing tests still pass; recorder is opt-in
3. `test_recorder_captures_full_prompt_text` — the recorded prompt matches what was actually sent (includes context_suffix etc.)
4. `test_recorder_captures_token_usage_per_pass` — usage.json has input_tokens / output_tokens / latency_ms / cost_usd populated
5. `test_recorder_captures_extraction_pydantic_dump` — extraction.json parses back as the same XExtraction shape

### Commit message format
```
feat(lab-t02): wire RunRecorder into MultiPassFHIRPipeline.extract()

Adds optional `recorder: RunRecorder | None = None` parameter to
extract(). When provided, every pass invocation captures
prompt/response/usage/extraction to disk under the run's
traces/<pass-name>/ directory.

Cost estimation via lib/extract/lab/cost.py — lookup table per known
model with conservative defaults.

Recorder is opt-in; production extraction (api/core/harmonize_service.py)
keeps calling extract(pdf) without arguments and pays no cost. Lab CLI
(LAB-T03) is the primary consumer.

Tests: 5 new in test_lab_pipeline_tracing.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## LAB-T03 · CLI entry point + `run` subcommand

- **Status:** Queued
- **Depends on:** LAB-T01 + LAB-T02
- **Goal:** A CLI module at `lib/extract/lab/__main__.py` invoked via `python -m lib.extract.lab`. First subcommand: `run` (single-pipeline or multi-pipeline against a PDF).

### What to build

#### Argument parsing — use stdlib `argparse` (no new deps)

```python
# lib/extract/lab/__main__.py
import argparse, sys

def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="lib.extract.lab")
    sub = parser.add_subparsers(dest="cmd", required=True)
    _add_run_parser(sub)
    # _add_compare_parser, _add_show_parser, _add_list_parser, _add_report_parser
    # added in LAB-T04 / T06; leave as TODO stubs that raise NotImplementedError

    args = parser.parse_args(argv)
    if args.cmd == "run":
        return _cmd_run(args)
    raise NotImplementedError(args.cmd)

if __name__ == "__main__":
    sys.exit(main())
```

#### `run` subcommand

```bash
uv run python -m lib.extract.lab run \
    --pipeline multipass-fhir \
    [--pipeline multipass-fhir-scout]   # repeatable
    --pdf path/to.pdf \
    [--ground-truth path/to.json] \
    [--root data/pdf-lab]               # default
```

For each `--pipeline` invocation:
1. Get the pipeline via `from lib.extract.pipelines import get`
2. Construct it (the existing constructor takes optional backend overrides; just use defaults for now)
3. Start a `RunRecorder`
4. Call `pipeline.extract(pdf_path, recorder=recorder)`
5. Print the run_id to stdout
6. On error: catch, recorder.finish(status="failed", error=str(e)), re-raise

Multiple pipelines: run them sequentially in v1 (parallel can be a future enhancement). Each gets its own run_id. Print all run_ids at the end.

#### Output

Plain text to stdout, structured for both human and machine reading:

```
Running pipeline 'multipass-fhir' on /path/to.pdf...
  ✓ run-id: 2026-05-07T18-30-00_a3b2c1_multipass-fhir
  ✓ artifacts: data/pdf-lab/runs/2026-05-07T18-30-00_a3b2c1_multipass-fhir/
  ✓ cost: $0.32
  ✓ latency: 18.4s
  ✓ bundle: 47 entries

Done. 1 run completed.
```

### Files you may touch
- `lib/extract/lab/__main__.py` (new)
- `lib/extract/lab/cli.py` (new — keeps __main__ thin; logic in cli.py)
- `lib/tests/test_extract/test_lab_cli.py` (new)

### Tests to write

Use `argparse.Namespace`-style invocation directly + a `monkeypatch` to stub the pipeline call (don't actually invoke an LLM in tests).

1. `test_cli_run_single_pipeline_creates_run_artifacts` — invoke main(["run", "--pipeline", "single-pass-vision", "--pdf", str(test_pdf), "--root", str(tmp_path)]) → run dir exists under tmp_path
2. `test_cli_run_multiple_pipelines_creates_separate_runs` — pass `--pipeline` twice → two run dirs created with different run_ids
3. `test_cli_run_unknown_pipeline_errors_cleanly` — `--pipeline xyzzy` → error message names the missing pipeline; exit code != 0
4. `test_cli_run_missing_pdf_errors_cleanly` — pdf path doesn't exist → clear error; exit != 0
5. `test_cli_run_with_ground_truth_persists_it` — `--ground-truth path.json` → file copied into run dir as ground-truth.json

### Commit message format
```
feat(lab-t03): CLI entry point + `run` subcommand

New CLI at python -m lib.extract.lab. First subcommand: run, which
invokes one or more pipelines against a PDF and persists full run
artifacts via RunRecorder.

Multi-pipeline mode supported (sequential). Each pipeline gets its own
run_id. Output is plain-text-but-grep-able to stdout for both human
and agent reading.

Tests: 5 new in test_lab_cli.py covering single-pipeline,
multi-pipeline, error paths, and ground-truth file handling.

Subcommands compare/show/list/report stubbed (NotImplementedError) —
landing in LAB-T04 + LAB-T06.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## LAB-T04 · `compare` subcommand — diff two run artifacts

- **Status:** Queued
- **Depends on:** LAB-T01 + LAB-T03
- **Goal:** Compute structured diff between two completed runs. Surfaces what changed: per-resource counts, per-fact agreement, cost / latency delta, bundle-shape delta.

### What to build

#### Comparison module `lib/extract/lab/compare.py`

```python
@dataclass(frozen=True)
class RunComparison:
    run_a_id: str
    run_b_id: str
    pipeline_a: str
    pipeline_b: str
    cost_delta_usd: float          # b - a
    latency_delta_ms: int           # b - a
    resource_counts_a: dict[str, int]
    resource_counts_b: dict[str, int]
    counts_delta: dict[str, int]    # b - a per resource type
    fact_overlap: dict[str, int]    # per resource type: count of facts both extracted
    fact_only_in_a: dict[str, list[dict]]  # facts only in a (small sample, e.g. first 10)
    fact_only_in_b: dict[str, list[dict]]
    bundle_shape_a: dict            # patient_count, encounter_link_rate, etc. (LAB-T05)
    bundle_shape_b: dict


def compare_runs(run_a_id: str, run_b_id: str, root: Path | None = None) -> RunComparison: ...
```

Fact-level agreement uses display-name + code-system match per resource type (mirror what `lib/harmonize/` already does). Cap reported "only in" lists at 10 facts each — full lists are recoverable from the bundle.json files.

#### CLI subcommand

```bash
uv run python -m lib.extract.lab compare --run-a <id> --run-b <id>
```

Output: a markdown table summary plus the structured RunComparison printed as JSON. Two output modes:
- `--format text` (default): human-readable summary
- `--format json`: machine-readable RunComparison dump

### Files you may touch
- `lib/extract/lab/compare.py` (new)
- `lib/extract/lab/cli.py` (extend with compare command)
- `lib/tests/test_extract/test_lab_compare.py` (new)

### Tests to write

Construct two synthetic run directories with known bundles, then call `compare_runs`. Assert RunComparison fields.

Required:
1. `test_compare_identical_runs` — same bundle in both → counts_delta all zero, fact_overlap == counts
2. `test_compare_b_extracted_more_conditions` — b has 3 more conditions → counts_delta["Condition"] == 3, fact_only_in_b populated
3. `test_compare_cost_and_latency_delta` — verify arithmetic
4. `test_compare_unknown_run_id_raises` — clear error

### Commit message format
```
feat(lab-t04): `compare` subcommand — structured diff between runs

New compare module + CLI subcommand. Diffs two completed runs across:
  - per-resource counts (delta and per-side)
  - per-fact agreement (overlap, only-in-a, only-in-b with samples)
  - cost / latency delta (b - a)
  - bundle-shape delta (patient_count, encounter_link_rate, etc.)

Output modes: --format text (markdown summary) or --format json
(RunComparison dump for downstream tooling).

Tests: 4 new in test_lab_compare.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## LAB-T05 · Bundle-shape assertions module

- **Status:** Queued
- **Depends on:** LAB-T01 (eval.json target)
- **Goal:** Beyond F1 per resource type, score each Bundle on structural quality. The new resource types (Patient, Encounter, Practitioner, Organization, etc.) need cross-resource sanity checks that F1 doesn't capture.

### What to build

```python
# lib/extract/lab/bundle_shape.py
@dataclass(frozen=True)
class BundleShapeReport:
    patient_count: int                         # should be exactly 1 for single-patient PDFs
    encounter_count: int
    encounter_link_rate: float                  # fraction of encounter-scopable resources with encounter ref
    patient_link_rate: float                    # fraction of subject-bearing resources pointing at the actual Patient.id (not 'unknown')
    practitioner_count: int
    practitioner_npi_rate: float                # fraction of Practitioners with NPI identifier
    organization_count: int
    document_reference_count: int
    composition_count: int
    loinc_resolution_rate: float                # fraction of Observations with a LOINC code
    interpretation_rate: float                  # fraction of numeric Observations with a flag
    clinical_category_rate: float               # fraction of Observations with the clinical-category extension
    note_encounter_link_rate: float             # fraction of DocumentReferences linked to an Encounter
    duplicate_practitioner_npis: list[str]      # NPIs appearing on more than one Practitioner (red flag)
    orphaned_subject_references: list[str]      # subject.reference values pointing at nonexistent ids


def score_bundle_shape(bundle: dict) -> BundleShapeReport: ...
```

Compute each metric directly from the bundle dict. No LLM, deterministic. Wire it into the `RunRecorder.finish` flow (or into a separate `eval` step that LAB-T03 calls right before `recorder.finish`) so every run gets a `bundle_shape.json` next to `eval.json`.

### Files you may touch
- `lib/extract/lab/bundle_shape.py` (new)
- `lib/extract/lab/recorder.py` (add `bundle_shape: dict | None` to `finish()`)
- `lib/extract/lab/cli.py` (call score_bundle_shape on the final bundle in `run` command)
- `lib/tests/test_extract/test_lab_bundle_shape.py` (new)

### Tests to write

Construct synthetic bundles with known shapes, assert metrics.

Required:
1. `test_patient_count_one_for_normal_bundle` — bundle with 1 Patient → patient_count == 1
2. `test_patient_count_zero_when_no_patient` — empty bundle → 0
3. `test_encounter_link_rate_fully_linked` — bundle with 1 Encounter + 5 Observations all linked → rate == 1.0
4. `test_practitioner_npi_rate` — 2 of 3 Practitioners have NPI → 2/3
5. `test_loinc_resolution_rate` — count Observations with LOINC coding entries
6. `test_duplicate_practitioner_npis_detected` — two Practitioner resources with same NPI → flagged
7. `test_orphaned_subject_reference_detected` — Observation referencing Patient/<nonexistent> → flagged

### Commit message format
```
feat(lab-t05): bundle-shape assertions module

Beyond F1 per resource type, score each Bundle on structural quality:
patient uniqueness, encounter linkage rate, practitioner NPI rate,
LOINC resolution rate, interpretation rate, clinical-category rate,
note-encounter linkage rate, duplicate-NPI detection, orphaned-
reference detection.

These metrics catch regressions F1 doesn't — e.g., post-pass T10 broke
patient reference rewrite would show as patient_link_rate dropping
from 1.0 to ~0.

Wired into the `run` CLI flow so every run gets a bundle_shape.json
artifact alongside eval.json.

Tests: 7 new in test_lab_bundle_shape.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## LAB-T06 · `show` / `list` / `report` subcommands + markdown report generator

- **Status:** Queued
- **Depends on:** LAB-T01 + LAB-T03 + LAB-T04 + LAB-T05
- **Goal:** Three subcommands that read run artifacts and emit human-readable output. The agent-loop's "share findings" step.

### What to build

#### `show --run <id>`

Prints a markdown summary of one run: pipeline, PDF, cost, latency, resource counts, bundle-shape report, top "vision wins" if ground truth was provided.

#### `list [--pipeline <name>] [--last <n>]`

Reads `runs.jsonl`. Prints a table of recent runs with id, pipeline, PDF basename, cost, weighted F1 (when ground truth exists), bundle status. Default `--last 20`.

#### `report --run <id>` and `report --compare <a> <b>`

Generates a longer, paste-able markdown report. For `--run`: full single-run summary including a sample of extracted facts. For `--compare`: full RunComparison rendered as markdown — tables for resource counts, cost / latency delta, fact-level disagreement samples.

This is the artifact the **agent uses to share findings with the user** — copy the markdown into the conversation.

### Files you may touch
- `lib/extract/lab/cli.py` (extend)
- `lib/extract/lab/report.py` (new — markdown generators)
- `lib/tests/test_extract/test_lab_report.py` (new)

### Tests to write

Required:
1. `test_show_run_markdown_includes_pipeline_and_cost`
2. `test_list_runs_filters_by_pipeline`
3. `test_list_runs_respects_last_n`
4. `test_report_compare_includes_resource_count_table`
5. `test_report_compare_renders_markdown_table_correctly`

### Commit message format
```
feat(lab-t06): `show` / `list` / `report` subcommands + markdown reports

Closes the agent-loop. Three new subcommands:
  - show --run <id>: single-run markdown summary
  - list [--pipeline <name>] [--last <n>]: recent runs table
  - report --run <id> | --compare <a> <b>: paste-able markdown report

The report subcommand is the primary artifact for the agent to share
findings with the user — markdown that drops directly into a
conversation.

Tests: 5 new in test_lab_report.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## After LAB-T06 — what the agent loop looks like in practice

```
[user]   "Run the bidi-scout pipeline on cedars-myhealth and tell me
         what's different vs the default pipeline."

[claude] uv run python -m lib.extract.lab run \
            --pipeline multipass-fhir \
            --pipeline multipass-fhir-bidi-scout \
            --pdf pdf-review/cedars-myhealth/inputs/...PDF
         → run-id A: ...
         → run-id B: ...

[claude] uv run python -m lib.extract.lab report \
            --compare A B
         → markdown comparison report

[claude] reads the report, summarizes for user, flags interesting
         disagreements (e.g. bidi-scout extracted 3 more conditions
         from page 22-24 narrative that the default pipeline missed),
         suggests next experiment.

[user]   directs next move.
```

Real PDFs through real pipelines, with full traces, costs, F1 scores, bundle-shape metrics. No UI required.

---

*Created 2026-05-07. 6 tasks. Total estimate: ~3 days condensed.*
