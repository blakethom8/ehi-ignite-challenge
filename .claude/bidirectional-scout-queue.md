# Bidirectional Scout Pipeline — Task Queue

> Architecture experiment: a new pipeline `multipass-fhir-bidi-scout` that runs TWO Pass-0 scouts with different prompt framings, reconciles their `DocumentMap` outputs, and dispatches the specialist passes against the reconciled manifest. Strategic context: `docs/daily/2026-05-07-ClaudeCode.md` Entry 9.

**Status legend:** `Queued` → `In Progress` → `Completed (<hash>)`
**Builder:** `phase1-builder`. Each brief is self-contained.

---

## Why this experiment

The single-scout `multipass-fhir-scout` (shipped Move Y) shipped a routing manifest — present/absent + page hints per resource type. But that manifest is from ONE pass with ONE framing. Hypothesis: different framings probe different content, and reconciliation surfaces:

- Coverage we'd otherwise miss (union — what either scout finds)
- High-confidence content (intersection — what both agree on)
- Disagreement as a feature (sections where scouts disagree → uncertainty signal)

**Cost:** 2× Pass 0 (cheap relative to 12+ specialist passes). Specialist dispatch logic unchanged.

---

## BIDI-T01 · Reconciliation logic — `reconcile_document_maps()`

- **Status:** Queued
- **Goal:** Pure-function helper that takes two `DocumentMap` instances and returns a single reconciled `DocumentMap` plus a structured disagreement report.
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, `lib/tests/test_extract/test_bidi_reconcile.py` (new)
- **Files you must NOT touch:** the existing scout pipeline; any prompts; anything in `api/`, `app/`, `archive/`

### What to build

#### 1. Add a `MapReconciliation` dataclass (after `DocumentMap`)

```python
@dataclass(frozen=True)
class MapReconciliation:
    """Result of reconciling two DocumentMap instances.

    The reconciled DocumentMap drives downstream dispatch. The disagreement
    report is metadata for observability — counted in extension fields on
    the bundle so test-bench UIs can surface uncertainty.
    """
    reconciled: DocumentMap
    agreement_count: int        # passes where both scouts agreed (both present, or both absent)
    disagreement_count: int     # passes where exactly one scout marked present
    only_in_a: list[str]        # pass names present in scout A only
    only_in_b: list[str]        # pass names present in scout B only
    page_hint_overlap: dict[str, int]  # per-pass: count of pages both scouts agreed on
```

#### 2. Implement `reconcile_document_maps()` (module-level function near `_VITAL_LOINC_MAP` constants)

```python
def reconcile_document_maps(
    map_a: DocumentMap,
    map_b: DocumentMap,
    *,
    strategy: Literal["union", "intersection"] = "union",
) -> MapReconciliation:
    """Reconcile two DocumentMap instances into one.

    Strategy:
    - "union" (default): include a pass if EITHER scout marks it present.
      Page hints are the union of both scouts' pages. More permissive;
      higher recall, possibly more cost.
    - "intersection": include a pass only if BOTH scouts mark it present.
      Page hints are the intersection. Tighter precision; possibly missed
      content.

    Inherited DocumentContext fields (patient_name, dob, etc.):
    - Prefer the value from map_a (top-down / first scout) when both present
    - Fall back to map_b if map_a's field is None
    - Report disagreement on identity fields via the dataclass

    Section list: union of both, in order of first appearance.
    """
    ...
```

Implementation rules:
- Iterate the union of presence keys
- For each key: check `present` in both maps; apply strategy
- Page hints: union or intersection of `pages` lists per strategy
- Section hints: prefer non-null one; if both differ, prefer scout A's
- Track agreement / disagreement counts
- Identity fields (patient_name, etc.): prefer scout A; record disagreement if maps disagree

### Tests to write

Use `_new_pipeline()` helper for any pipeline-instance code. Tests don't need pipeline instances since `reconcile_document_maps` is a pure function.

Required:
1. `test_reconcile_both_empty_returns_empty_map` — two DocumentMaps with no presence entries → reconciled has empty presence
2. `test_reconcile_union_includes_either_present` — A says vital_signs present, B says no → union strategy includes vital_signs; reconciled.presence["vital_signs"].present == True
3. `test_reconcile_intersection_excludes_partial_agreement` — A says vital_signs present, B says no → intersection strategy → presence.get("vital_signs") returns ResourcePresence(present=False) or absent entirely
4. `test_reconcile_union_pages_are_union` — A pages=[2, 3], B pages=[3, 4] → union pages=[2, 3, 4] sorted
5. `test_reconcile_intersection_pages_are_intersection` — same → intersection pages=[3]
6. `test_reconcile_disagreement_count` — 3 passes where scouts disagree → reconciliation.disagreement_count == 3
7. `test_reconcile_only_in_a_lists_correctly` — A has clinical_notes present, B has lab_observations present, no overlap → only_in_a=["clinical_notes"], only_in_b=["lab_observations"]
8. `test_reconcile_prefers_scout_a_for_identity_fields` — A.patient_name="Blake", B.patient_name="Robert" → reconciled.patient_name=="Blake" (and ideally captured in the disagreement report)
9. `test_reconcile_falls_back_to_b_when_a_field_is_none` — A.patient_dob=None, B.patient_dob="1993-06-16" → reconciled.patient_dob=="1993-06-16"
10. `test_reconcile_section_hint_preferred_when_one_null` — A presence has section_hint="Vital Signs", B has section_hint=None → reconciled section_hint=="Vital Signs"

### Smoke test
```bash
uv run --project /Users/blake/Repo/ehi-ignite-challenge pytest lib/tests/test_extract/ api/tests/test_harmonize_api.py api/tests/test_context_builder.py -q
```

### Commit message
```
feat(bidi-t01): reconcile_document_maps() — merge two scout outputs

Pure function that takes two DocumentMap instances (from differently-
framed Pass 0 scouts) and returns a single reconciled DocumentMap plus
a MapReconciliation report capturing agreement / disagreement counts,
per-pass overlap, and identity-field conflicts.

Two strategies:
  - union: include a pass if EITHER scout marks present (broader)
  - intersection: include only if BOTH agree (tighter)

Identity fields prefer scout A with fallback to scout B; disagreements
are recorded for observability.

Tests: 10 new in test_bidi_reconcile.py covering both strategies,
identity-field reconciliation, page-list set ops, and disagreement
counting.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## BIDI-T02 · Two scout-prompt variants

- **Status:** Queued
- **Depends on:** none (parallel with BIDI-T01 if you want; both feed into T03)
- **Goal:** Define two distinct scout prompts as constants and a small helper that maps a "scout flavor" identifier to (prompt, schema_version) pairs.
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, `lib/tests/test_extract/test_bidi_prompts.py` (new)

### What to build

#### 1. Add `_DOCUMENT_MAP_PROMPT_EVENTS` and `_DOCUMENT_MAP_PROMPT_TABLES` constants

After the existing `_DOCUMENT_MAP_PROMPT`:

```python
_DOCUMENT_MAP_PROMPT_EVENTS = """You are scanning a medical document to produce
a ROUTING MANIFEST focused on CLINICAL EVENTS — encounters, visits, narrative
notes, observed conditions, treatments delivered.

[same per-resource enumeration as _DOCUMENT_MAP_PROMPT, but the rules section
emphasizes:]

- Prioritize identifying ENCOUNTERS and the events around them (visits,
  notes, conditions discussed during a visit).
- Pay attention to NARRATIVE content (Subjective / Objective / A&P).
- For tables of structured data (labs, immunizations), still mark present
  but you don't need to enumerate every page exhaustively — note the
  range.
"""

_DOCUMENT_MAP_PROMPT_TABLES = """You are scanning a medical document to produce
a ROUTING MANIFEST focused on STRUCTURED DATA — tables of labs, vital signs,
immunizations, medications with dose/frequency, allergens with values.

[same per-resource enumeration, but rules section emphasizes:]

- Prioritize identifying STRUCTURED TABLES with rows of data.
- Include EVERY page that contains a structured-data row in pages[].
- For narrative content (notes, A&P paragraphs), still mark present
  but enumeration of pages can be approximate.
"""
```

The two prompts share most content but differ in emphasis. Pulled out as constants so prompt_version tracks them independently in the cache.

#### 2. Add a `ScoutFlavor` Literal + helper

```python
ScoutFlavor = Literal["events", "tables"]


def get_scout_prompt(flavor: ScoutFlavor) -> str:
    """Return the system prompt for a scout flavor."""
    if flavor == "events":
        return _DOCUMENT_MAP_PROMPT_EVENTS
    if flavor == "tables":
        return _DOCUMENT_MAP_PROMPT_TABLES
    raise ValueError(f"unknown scout flavor: {flavor}")
```

### Tests to write
1. `test_scout_flavor_returns_distinct_prompts` — events != tables
2. `test_scout_flavor_unknown_raises` — flavor="random" raises ValueError
3. `test_both_prompts_share_resource_type_enumeration` — both prompts contain the 13 resource type names (sanity check that the schema-determining content is consistent)

### Commit message
```
feat(bidi-t02): two scout-prompt flavors — events + tables

Adds _DOCUMENT_MAP_PROMPT_EVENTS (encounter / narrative-focused) and
_DOCUMENT_MAP_PROMPT_TABLES (structured-data-focused) plus a
ScoutFlavor Literal + get_scout_prompt() helper.

The two prompts share resource-type enumeration but differ in emphasis.
Different framings are expected to surface different content, with
reconciliation (BIDI-T01) merging the outputs.

Tests: 3 new in test_bidi_prompts.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## BIDI-T03 · MultiPassFHIRBidiScoutPipeline class

- **Status:** Queued
- **Depends on:** BIDI-T01 + BIDI-T02
- **Goal:** Register `multipass-fhir-bidi-scout` as a parallel pipeline that runs the two scouts, reconciles, and dispatches specialists against the reconciled DocumentMap.

### What to build

#### Subclass `MultiPassFHIRBidiScoutPipeline` (after `MultiPassFHIRScoutPipeline`)

```python
@register
class MultiPassFHIRBidiScoutPipeline(MultiPassFHIRScoutPipeline):
    """multipass-fhir variant: two scouts + reconciliation.

    Pass 0 runs TWICE with two distinct prompt flavors:
      - "events" — encounter/narrative-focused
      - "tables" — structured-data-focused

    The two DocumentMap outputs are reconciled via `reconcile_document_maps()`
    (default strategy: union — broader recall). Specialist passes dispatch
    against the reconciled manifest (page hints are the union of both scouts'
    page lists for each present resource type).

    The reconciliation metadata (agreement count, disagreement count,
    per-pass overlap) is attached to the bundle's meta.extension as a
    JSON-serialized scout-reconciliation extension, so the test bench can
    surface uncertainty.

    Cost: 2× Pass 0 (cheap relative to 12+ specialist passes). Specialist
    dispatch is unchanged from the single-scout pipeline.

    Hypothesis: different framings catch different content; the reconciled
    manifest has higher recall than either scout alone.
    """

    metadata = PipelineMetadata(
        name="multipass-fhir-bidi-scout",
        description=(
            "Two-scout variant of multipass-fhir-scout. Runs Pass 0 twice "
            "with events-focused and tables-focused prompts, reconciles, "
            "and dispatches specialists against the merged manifest. "
            "Same FHIR Bundle output shape; reconciliation metadata "
            "attached to bundle meta.extension."
        ),
        architecture="bidirectional-scout-then-specialist",
        primary_backends=["anthropic"],
        estimated_cost_per_pdf_usd=0.22,  # +0.04 for the second scout vs scout pipeline
    )
```

#### Override `_run_pass_0` (or equivalent) to run two scouts + reconcile

The parent (`MultiPassFHIRScoutPipeline`) overrode `_pass_0_prompt` / `_pass_0_schema` to use `_DOCUMENT_MAP_PROMPT` / `DocumentMap`. The bidi subclass needs to:

1. Run Pass 0 twice with two different prompts (events flavor + tables flavor)
2. Reconcile the two outputs via `reconcile_document_maps`
3. Stash both the reconciled DocumentMap (drives dispatch) and the `MapReconciliation` (lands in bundle meta) on instance attributes

Implementation pattern (adjust based on what hooks the parent exposes — read carefully):

```python
def _run_pass_0(self, pdf_path: Path, layout: Any) -> DocumentMap:
    """Override to run two scouts + reconcile. Returns the reconciled
    DocumentMap (the rest of the pipeline treats this as Pass 0's output)."""
    map_a = self._invoke_pass_0_with_prompt(
        pdf_path=pdf_path,
        layout=layout,
        prompt=get_scout_prompt("events"),
        prompt_version="bidi-events-v1",
    )
    map_b = self._invoke_pass_0_with_prompt(
        pdf_path=pdf_path,
        layout=layout,
        prompt=get_scout_prompt("tables"),
        prompt_version="bidi-tables-v1",
    )
    reconciliation = reconcile_document_maps(map_a, map_b, strategy="union")
    self._scout_reconciliation = reconciliation  # for bundle meta
    return reconciliation.reconciled
```

If the parent doesn't have a `_run_pass_0` hook OR an `_invoke_pass_0_with_prompt` helper, factor one out — the parent's existing hooks (`_pass_0_prompt`, `_pass_0_schema`, `_doc_context_from_pass_0`) are designed for ONE invocation. You'll need a small refactor to support two.

If the refactor is risky, an alternative is to override `extract()` directly in the subclass and replace the Pass 0 step inline. Either is acceptable — pick the smaller diff.

#### Bundle meta enhancement

In `_merge_to_bundle` (override only the bundle-meta construction, keep the rest), attach the `MapReconciliation` data:

```python
if hasattr(self, "_scout_reconciliation") and self._scout_reconciliation:
    bundle["meta"]["extension"].append(
        {
            "url": "https://ehi-atlas.example/fhir/StructureDefinition/scout-reconciliation",
            "valueString": json.dumps({
                "agreement_count": self._scout_reconciliation.agreement_count,
                "disagreement_count": self._scout_reconciliation.disagreement_count,
                "only_in_a": self._scout_reconciliation.only_in_a,
                "only_in_b": self._scout_reconciliation.only_in_b,
            }),
        }
    )
```

### Tests to write

Use `MultiPassFHIRBidiScoutPipeline.__new__(MultiPassFHIRBidiScoutPipeline)` for instances.

1. `test_bidi_pipeline_registered` — present in `list_pipelines()`
2. `test_bidi_pipeline_metadata` — name == "multipass-fhir-bidi-scout", architecture == "bidirectional-scout-then-specialist"
3. `test_bidi_inherits_specialist_passes` — `_specialist_passes(reconciled_map)` returns the same shape as the parent scout pipeline given the same DocumentMap (regression check)
4. `test_run_pass_0_returns_reconciled_map` — mock the two scout invocations to return synthetic DocumentMaps; assert the result is the reconciliation
5. `test_run_pass_0_stashes_reconciliation_metadata` — after `_run_pass_0`, `self._scout_reconciliation` is populated with a `MapReconciliation` instance

For tests that need to mock two LLM invocations, use a small subclass that overrides `_invoke_pass_0_with_prompt` to return synthetic DocumentMaps; OR if the parent's helper doesn't exist yet (you factored it out as part of this task), confirm the parent's tests still pass.

### Smoke test
```bash
uv run --project /Users/blake/Repo/ehi-ignite-challenge pytest lib/tests/test_extract/ api/tests/test_harmonize_api.py api/tests/test_context_builder.py -q
```
Must show no regressions. New count should be `(prior baseline) + (BIDI-T01 tests) + (BIDI-T02 tests) + (BIDI-T03 tests)`.

### Commit message
```
feat(bidi-t03): MultiPassFHIRBidiScoutPipeline — two scouts + reconciliation

Registers `multipass-fhir-bidi-scout` (architecture =
bidirectional-scout-then-specialist) as a parallel pipeline. Runs Pass
0 TWICE with two distinct prompt flavors (events / tables), reconciles
their DocumentMap outputs via reconcile_document_maps (union strategy
default), then dispatches specialist passes against the merged
manifest.

Same FHIR Bundle output shape as the single-scout pipeline.
Reconciliation metadata (agreement/disagreement counts, only-in-a /
only-in-b lists) attached to bundle.meta.extension at
.../scout-reconciliation so the test bench can surface uncertainty.

Subclasses MultiPassFHIRScoutPipeline to inherit specialist dispatch
+ all builders + post-passes.

Cost: 2× Pass 0 (small relative to 12+ specialist passes).

Tests: 5 new in test_bidi_pipeline.py covering registration, metadata,
specialist-pass inheritance, reconciled-map propagation, and metadata
stashing.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## After all three

5 pipelines registered:
- `multipass-fhir` (default)
- `multipass-fhir-gemma-tabular` (cost-optimized)
- `multipass-fhir-scout` (single scout)
- `multipass-fhir-bidi-scout` (two scouts + reconciliation) — NEW
- `single-pass-vision` (baseline)

Real cost / F1 / latency comparison still requires PDF-LAB-STUDIO. Bidirectional reconciliation's value (does it actually improve recall? does the disagreement signal correlate with real uncertainty?) is unmeasured until then.

---

*Created 2026-05-07. 3 builder-sized tasks. ~1 day of focused work.*
