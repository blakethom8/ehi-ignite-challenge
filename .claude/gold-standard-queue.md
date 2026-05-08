# Gold-Standard Pipeline + Ground-Truth Review — Task Queue

> Build a "gold standard" extraction pipeline (Claude Opus 4.7 + extended thinking + self-consistency + reviewer agent) plus a human-in-the-loop review surface that turns gold-pipeline output into versioned ground truth. Result: production pipelines get measured against a richer, human-validated reference instead of flawed structured siblings.

> Strategic context: `docs/daily/2026-05-07-ClaudeCode.md` Entry 11. Branch: `feature/code-resolution-loinc` (continues stacking).

**Status legend:** `Queued` → `In Progress` → `Completed (<hash>)`
**Builder:** `phase1-builder`. Each brief is self-contained.

---

## STEP 1 — Gold-standard pipeline (this session)

### GOLD-T01 · Register `multipass-fhir-gold` pipeline (Opus 4.7 + extended thinking)

- **Status:** ✅ Completed `18f2035` · 2026-05-07 · 508 tests pass
- **Goal:** New pipeline `multipass-fhir-gold` (architecture: `gold-standard`) using Claude Opus 4.7 with extended thinking enabled per pass. Same overall multipass-fhir architecture, just upgraded model + thinking. v1 — no self-consistency yet (GOLD-T02), no reviewer agent yet (GOLD-T03).
- **Files you may touch:** `lib/extract/pdf.py` (extend AnthropicBackend with optional thinking param), `lib/extract/pipelines/multipass_fhir.py` (register new subclass), `lib/tests/test_extract/test_gold_pipeline.py` (new).
- **Files you must NOT touch:** other pipelines (defaults / scout / bidi / gemma), `.claude/gold-standard-queue.md`, anything in `api/` / `app/` / `archive/`.

### What to build

#### 1. Extend `AnthropicBackend` with optional `thinking` config

Look at the existing `AnthropicBackend` class in `lib/extract/pdf.py`. It currently calls `anthropic.messages.create(...)` with `model`, `messages`, `max_tokens` etc. Anthropic supports an optional `thinking` parameter:

```python
client.messages.create(
    model="claude-opus-4-7",
    thinking={"type": "enabled", "budget_tokens": 16000},
    messages=[...],
    ...
)
```

Add an optional constructor parameter `thinking_budget_tokens: int | None = None`. When set, pass `thinking={"type": "enabled", "budget_tokens": thinking_budget_tokens}` to messages.create. When None (default), don't pass thinking — preserves existing behavior.

Per Anthropic docs, when thinking is enabled the assistant's response includes `thinking` blocks before the main content. Make sure the existing response-parsing logic skips `type=="thinking"` blocks correctly (look for the existing content-block iteration loop).

#### 2. Register `MultiPassFHIRGoldPipeline` in `multipass_fhir.py`

After the existing variant subclasses (gemma-tabular, scout, bidi-scout):

```python
@register
class MultiPassFHIRGoldPipeline(MultiPassFHIRPipeline):
    """multipass-fhir variant: gold-standard architecture for ground-truth
    generation. Same multipass architecture as default, but:
      - Claude Opus 4.7 (not Sonnet) for every pass
      - Extended thinking enabled (16k thinking tokens per pass)

    Cost ~5-10x production. Latency ~5-10x. Run-once-per-PDF; output is the
    starting point for human review (Step 2 / REVIEW-* tasks).

    GOLD-T02 will add self-consistency (run-twice + intersect).
    GOLD-T03 will add the reviewer agent (whole-bundle inconsistency check).
    """

    metadata = PipelineMetadata(
        name="multipass-fhir-gold",
        description=(
            "Gold-standard variant for ground-truth generation. Opus 4.7 + "
            "extended thinking on every pass. Run-once-per-PDF; output is the "
            "starting point for human review."
        ),
        architecture="gold-standard",
        primary_backends=["anthropic"],
        estimated_cost_per_pdf_usd=2.5,  # ~5-10x default; bake-off will measure
    )
```

The pipeline configuration should:
- Override `_resolve_backend_for_pass` (or whatever the existing per-pass backend resolution method is named — read the parent code) to always return an AnthropicBackend instance configured for Opus + thinking.
- Or: in the constructor, set `pass_overrides` so EVERY pass routes to `{"backend": "anthropic", "model": "claude-opus-4-7", "thinking_budget_tokens": 16000}`.

Pick whichever pattern matches the existing variant subclasses (look at how `MultiPassFHIRGemmaTabularPipeline` overrides per-pass model selection).

#### 3. Cost estimation

Update `lib/extract/lab/cost.py` to include `claude-opus-4-7` rates. The Opus rates: $15/1M input, $75/1M output (per Anthropic published rates). Thinking tokens count as output tokens for billing.

### Tests

Use the existing test patterns from `test_scout_pipeline.py` and `test_bidi_pipeline.py`. Don't invoke real LLMs — verify the pipeline registration + metadata + the per-pass backend config.

Required test cases:

1. `test_gold_pipeline_registered` — `multipass-fhir-gold` appears in `list_pipelines()`
2. `test_gold_pipeline_metadata` — name, architecture == "gold-standard", primary_backends contains "anthropic", cost estimate ≥ $1
3. `test_gold_pipeline_inherits_specialist_passes` — _specialist_passes returns the same shape as parent (same _PASSES, no skipping)
4. `test_gold_pipeline_uses_opus_model_for_all_passes` — for each pass in _PASSES, the resolved backend config has `model="claude-opus-4-7"` (test the resolution logic without invoking)
5. `test_gold_pipeline_enables_thinking_for_all_passes` — for each pass, the resolved config has `thinking_budget_tokens` set
6. `test_anthropic_backend_thinking_param_optional` — direct unit test: AnthropicBackend(thinking_budget_tokens=None) doesn't pass thinking; AnthropicBackend(thinking_budget_tokens=16000) does
7. `test_estimate_cost_opus_known_model` — `estimate_cost(model="claude-opus-4-7", input_tokens=1000, output_tokens=500)` returns ~$0.0525 (15/1M*1000 + 75/1M*500)

### Smoke test
```bash
uv run --project /Users/blake/Repo/ehi-ignite-challenge pytest lib/tests/ api/tests/test_harmonize_api.py api/tests/test_context_builder.py -q
```

### Commit message format
```
feat(gold-t01): multipass-fhir-gold — Opus 4.7 + extended thinking

Registers a new pipeline variant for ground-truth generation. Same
multipass architecture as the default, but every pass routes to
Claude Opus 4.7 with extended thinking enabled (16k thinking tokens
per pass).

Cost ~5-10x default. Latency ~5-10x. Intended for run-once-per-PDF;
output is the starting point for human review (Step 2 / REVIEW-*).

GOLD-T02 will add self-consistency. GOLD-T03 will add the
reviewer agent.

Updates AnthropicBackend with optional thinking_budget_tokens param
(None preserves existing behavior). Updates lib/extract/lab/cost.py
with Opus rates ($15/1M input, $75/1M output).

Tests: 7 new in test_gold_pipeline.py covering registration, metadata,
specialist-pass inheritance, per-pass model resolution, thinking
config, and Opus cost estimation.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

### GOLD-T02 · Self-consistency wrapper — run each pass twice, intersect facts

- **Status:** ✅ Completed `289c826` · 2026-05-07 · 517 tests pass
- **Depends on:** GOLD-T01 (gold pipeline must exist)
- **Goal:** Add a `run_count: int = 1` field to `ExtractionPass`. When `run_count >= 2`, the dispatcher runs the pass that many times (in parallel via the existing ThreadPoolExecutor) and intersects the resulting facts. Bump the gold pipeline's per-pass `run_count` to 2.

### Why
Self-consistency catches model variance. Facts that appear in BOTH runs are high-confidence; facts that appear in only one are flagged for human review. For ground-truth generation we want high precision over high recall.

### What to build

#### 1. Extend ExtractionPass + dispatcher

Add `run_count: int = 1` to the `ExtractionPass` dataclass. In the dispatcher (`_run_pass` or wherever the parallel executor is), when `pass.run_count >= 2`, submit N copies of the call and reduce.

Reduction logic per resource type:
- **Tabular** (Observations, Vital Signs, Immunizations, Medications): match by (display, value) — both must appear identically in all runs to be kept
- **Narrative** (Conditions, Clinical Notes, Allergies): match by normalized display text only
- **Identity** (Patient, Practitioner, Organization, Encounter, Coverage): match by primary key (NPI, MRN, name+date, etc.)

Add helper `_intersect_extractions(extractions: list[BaseModel]) -> BaseModel` that handles each resource type. Lives in `lib/extract/pipelines/multipass_fhir.py` near the post-pass methods.

#### 2. Configure gold pipeline for run_count=2

In `MultiPassFHIRGoldPipeline.__init__` or via pass_overrides, set every pass's run_count to 2.

### Tests

1. `test_extraction_pass_default_run_count_one` — backward compat: ExtractionPass() defaults to run_count=1, existing pipeline behavior unchanged
2. `test_intersect_observations_keeps_only_common_facts` — synthetic two-run output where some facts overlap, some don't; intersect returns only the overlap
3. `test_intersect_conditions_normalized_display_match` — same condition with slightly different displays in the two runs (case, punctuation) → still matched as same
4. `test_dispatcher_runs_pass_twice_when_run_count_two` — mock the LLM call, verify it's invoked 2x for a pass with run_count=2
5. `test_gold_pipeline_uses_run_count_two_for_all_passes` — every pass on the gold pipeline has run_count=2

### Commit message format
```
feat(gold-t02): self-consistency wrapper — run-twice intersect

Adds run_count: int = 1 to ExtractionPass. When >= 2, the dispatcher
runs the pass that many times in parallel and intersects the
resulting facts.

Per-resource-type intersection rules:
  - Tabular: match by (display, value) — strict
  - Narrative: match by normalized display
  - Identity: match by primary key

The gold pipeline (GOLD-T01) is configured with run_count=2 for every
pass — facts must appear in both runs to make it into the gold
output. Catches model variance; trades recall for precision.

Tests: 5 new covering run_count default, intersection logic per
resource type, dispatcher invocation count, gold pipeline config.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

### GOLD-T03 · Reviewer agent — whole-bundle inconsistency check

- **Status:** ✅ Completed `071a77f` · 2026-05-07 · 525 tests pass
- **Depends on:** GOLD-T01
- **Goal:** A meta-pass that runs AFTER the assembled FHIR Bundle is built. Reads the bundle, asks Opus to scrutinize it for inconsistencies (med start before DOB, encounter referenced in notes but not as Encounter resource, conflicting dates, etc.), emits a list of "concerns" onto `bundle.meta.extension`.

### What to build

#### 1. New module `lib/extract/lab/reviewer_agent.py`

```python
@dataclass
class BundleConcern:
    severity: Literal["info", "warning", "error"]
    category: str  # "date-inconsistency", "missing-cross-reference", "data-quality", "narrative-fact-not-extracted", ...
    description: str
    affected_resource_ids: list[str]


def review_bundle(bundle: dict, *, backend: VisionBackend | None = None,
                  thinking_budget_tokens: int = 8000) -> list[BundleConcern]:
    """Asks Claude Opus 4.7 (with extended thinking) to scrutinize the
    bundle for inconsistencies. Returns a list of concerns to attach
    to bundle.meta.extension."""
    ...
```

System prompt for the reviewer agent:

```
You are a clinical-document quality reviewer. Below is a FHIR Bundle
extracted from a medical PDF. Your job: scrutinize it for inconsistencies,
missing cross-references, suspicious dates, and clinical findings that
were probably present in the source but didn't make it into the bundle.

Rules:
- Do NOT add new facts. Only flag concerns about what's there or
  obviously missing.
- Severity:
    error   = clinically wrong (e.g., medication started before DOB)
    warning = suspicious but plausible (e.g., 2 practitioners with
              identical NPI; reference to encounter without matching
              Encounter resource)
    info    = potentially incomplete (e.g., narrative mentions a lab
              result that isn't in the Observations list)
- Cite affected resource IDs.
- Be concise — one sentence per concern.

Output schema: list of {severity, category, description, affected_resource_ids}.
```

#### 2. Wire into the gold pipeline

In `MultiPassFHIRGoldPipeline._merge_to_bundle`:

```python
bundle = super()._merge_to_bundle(...)
concerns = review_bundle(bundle, backend=self._reviewer_backend)
if concerns:
    bundle["meta"].setdefault("extension", []).append({
        "url": "https://ehi-atlas.example/fhir/StructureDefinition/reviewer-concerns",
        "valueString": json.dumps([asdict(c) for c in concerns]),
    })
return bundle
```

### Tests

1. `test_review_bundle_returns_list_of_concerns` — synthetic bundle with med start before DOB → reviewer flags it
2. `test_review_bundle_categorizes_severity` — assert severity Literal works
3. `test_review_bundle_skips_when_bundle_empty` — empty bundle → empty concerns
4. `test_gold_pipeline_attaches_reviewer_concerns_to_meta` — end-to-end: gold pipeline output has reviewer-concerns extension on bundle.meta

For the end-to-end test, mock the reviewer backend to return a synthetic concerns list (avoid real LLM calls).

### Commit message format
```
feat(gold-t03): reviewer agent — whole-bundle inconsistency check

New module lib/extract/lab/reviewer_agent.py + integration into the
gold pipeline. After the bundle is assembled, Claude Opus 4.7 (with
extended thinking) scrutinizes it for:
  - Date inconsistencies (med before DOB)
  - Missing cross-references (note mentions encounter not extracted)
  - Data quality issues (duplicate NPIs, etc.)
  - Narrative findings probably missed by extraction

Concerns are attached to bundle.meta.extension at
.../reviewer-concerns as JSON. Severity: info / warning / error.

This is a META-pass — it runs ONCE on the assembled bundle, not
per-resource. Cost ~$0.10-0.20 per bundle (small relative to gold's
$2-5 total).

Tests: 4 new covering reviewer logic, severity categorization, empty-
bundle behavior, and end-to-end gold pipeline integration.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## STEP 2 — Review CLI + eval integration (next session)

### REVIEW-T01 · Ground-truth schema + on-disk format

- **Status:** Queued (next session)
- **Goal:** Define the schema for `data/pdf-lab/ground-truth/<pdf-sha>-vN.json` and a Python module that reads/writes it.

(Detailed brief written when Step 1 lands.)

### REVIEW-T02 · `lab review --run <id>` CLI

- **Status:** Queued (next session)
- **Goal:** CLI subcommand that walks each fact in a run's bundle, prompts the user for ✓ / ✗ / edit, persists the result as a versioned ground-truth file.

### REVIEW-T03 · Versioning + audit trail

- **Status:** Queued (next session)
- **Goal:** Each ground-truth file carries reviewer name, decision per fact, timestamp; older versions kept for audit.

### EVAL-T01 · Lab CLI auto-loads ground truth when pdf-sha matches

- **Status:** Queued (next session)
- **Goal:** When running a pipeline against a PDF that has a verified ground-truth file, automatically use that as the eval reference (overrides any manually-passed --ground-truth).

### EVAL-T02 · Vision-wins triage workflow

- **Status:** Queued (next session)
- **Goal:** Production extras (facts in run but not in ground truth) get surfaced via a CLI subcommand. Reviewer either incorporates them into the GT or marks them as hallucinations.

---

## After Step 1 — what we can do

```
1. Run gold pipeline on cedars-myhealth (~$3, ~10 min):
   python -m lib.extract.lab run \
     --pipeline multipass-fhir-gold \
     --pdf pdf-review/cedars-myhealth/inputs/...PDF

2. Inspect the gold run's bundle.json — should have richer extraction
   than production (more conditions from narrative, more thorough
   practitioner identification, fewer mistakes per Opus reasoning).

3. Read bundle.meta.extension[reviewer-concerns] to see what the
   reviewer agent flagged.

4. Use the gold output as a starting point for human review (manually
   for the first PDF; CLI in Step 2).
```

---

*Created 2026-05-07. 8 tasks across 2 steps. Step 1 (~3 tasks) builds this session.*
