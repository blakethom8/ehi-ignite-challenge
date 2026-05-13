# Scout-Then-Specialist Pipeline — Task Queue

> Architecture experiment: a new pipeline `multipass-fhir-scout` that uses a beefed-up Pass 0 to produce a *routing manifest*, then dispatches downstream passes only for resource types the document actually contains, with page-scoped prompt hints. Strategic context: `docs/daily/2026-05-07-ClaudeCode.md` Entry 8. Branch: `feature/code-resolution-loinc` (continues stacking).

**Status legend:** `Queued` → `In Progress` → `Completed (<hash>)`

**Builder:** `phase1-builder`. Each brief is self-contained.

---

## Why this experiment

Current `multipass-fhir` runs all 12 specialist passes on every PDF, regardless of whether the PDF contains content for that pass. Cedars MyHealth (25 pages):
- Clinical notes only on pages 22-24 → 21 wasted pages of context for the clinical_notes pass
- Vital signs only on page 2 → 24 wasted pages for the vital_signs pass
- Lab-only PDFs (e.g., the Function Health 2025-11-19 PDF) → 5+ passes run with no content present

**Hypothesis:** a richer Pass 0 that returns a routing manifest can:
1. Skip passes whose resource types are absent → cuts cost ~40-60% on sparse docs
2. Page-scope prompts for present resource types → tighter signal, higher F1
3. Preserve the same FHIR Bundle output shape — downstream consumers don't notice the change

Validation strategy: register as a parallel pipeline. Bake-off harness compares on real PDFs once PDF-LAB-STUDIO ships.

---

## SCOUT-T01 · DocumentMap schema + scout pass prompt

- **Status:** ✅ Completed `6709017` · 2026-05-07 · 234 tests pass
- **Goal:** Add a new `DocumentMap` Pydantic schema (extends `DocumentContext`) and a `_DOCUMENT_MAP_PROMPT` constant. Schema captures: existing context fields PLUS per-resource-type presence + page hints + section structure.
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, `lib/tests/test_extract/test_document_map.py` (new)
- **Files you must NOT touch:** anything in `api/`, `app/`, the existing `_PASSES` list (this task is data-shape only), `.claude/scout-pipeline-queue.md`

### What to build

#### 1. Schema (place after `DocumentContext`)

```python
class ResourcePresence(BaseModel):
    """Per-resource-type presence + page hints from the scout pass."""
    present: bool = Field(False, description="Document contains content for this resource type")
    pages: list[int] = Field(default_factory=list, description="1-indexed pages containing this resource type")
    section_hint: str | None = Field(
        None,
        description="Short narrative hint for the specialist pass (e.g. 'Last Filed Vital Signs section', "
        "'Allergy & Immunology Progress Note', 'Comprehensive Metabolic Panel')",
    )


class DocumentMap(DocumentContext):
    """Beefed-up Pass 0 output. Inherits all DocumentContext fields and adds
    a routing manifest for downstream specialist passes.

    Each presence key matches a pass name in _PASSES. The scout pipeline uses
    this map to (a) skip passes whose resource type is absent and (b) attach
    page hints to the prompts of present passes.
    """

    presence: dict[
        Literal[
            "conditions",
            "medications",
            "allergies",
            "immunizations",
            "lab_observations",
            "vital_signs",
            "encounter",
            "practitioner",
            "organization",
            "clinical_notes",
            "patient_demographics",
            "coverage",
            "social_history",
        ],
        ResourcePresence,
    ] = Field(default_factory=dict, description="Per-pass presence + page hints")

    sections: list[str] = Field(
        default_factory=list,
        description="Top-level section titles in the document (e.g. ['Patient Demographics', "
        "'Allergies', 'Medications', 'Results', 'Progress Notes', 'Insurance']). Useful for "
        "downstream prompt hints.",
    )
```

#### 2. Prompt constant (after `_PASS_0_PROMPT`)

```python
_DOCUMENT_MAP_PROMPT = """You are scanning a medical document to produce a
ROUTING MANIFEST that tells downstream specialist extractors what's present
and where to focus.

This pass is a SUPERSET of the document_context pass. You output:

1. All the DocumentContext fields (document_type, patient_name, patient_dob,
   encounter_date, ordering_provider, facility_name) — same as before.
2. A `presence` dict with one entry per known resource type (see schema).
   For each: is it present? on which pages (1-indexed)? what section title or
   visual landmark identifies it?
3. A `sections` list of top-level section titles in document order.

Resource types to assess:
  - conditions          : diagnoses / problem list / assessment
  - medications         : current meds / med list / prescriptions
  - allergies           : allergies / sensitivities (including "No known")
  - immunizations       : vaccines / immunizations table
  - lab_observations    : lab result rows in detailed-results tables
  - vital_signs         : BP / HR / temp / weight / height / BMI / RR / O2
  - encounter           : office visits / encounter records / visit summaries
  - practitioner        : named providers / care team / authorizing physicians
  - organization        : hospitals / labs / clinics / payers as institutions
  - clinical_notes      : narrative SOAP notes / progress notes / consult notes
  - patient_demographics: name / DOB / address / phone / race / ethnicity / MRN
  - coverage            : insurance / payer / member ID / group / plan name
  - social_history      : tobacco / alcohol / PHQ / occupation / sex/gender items

Rules:
- Be CONSERVATIVE: mark `present=true` only when the document clearly contains
  content for that resource type. False positives waste downstream cost.
- Page hints are 1-indexed. List EVERY page containing relevant content, not
  just the first one (e.g., a multi-page lab table → list all those pages).
- section_hint should be a short identifying phrase from the document, not a
  paraphrase. Example: "Last Filed Vital Signs" not "the vital signs table".
- If the document has no resource of a type, use `present=false` and empty pages.
- sections list is in document order; capture top-level titles only (not
  every subsection inside a progress note)."""
```

#### 3. Tests

- `test_document_map_inherits_context_fields` — DocumentMap can be instantiated with all DocumentContext fields and they round-trip
- `test_document_map_presence_dict_validates_keys` — only known pass names accepted; "random_pass" key raises
- `test_document_map_resource_presence_defaults` — ResourcePresence with no fields → present=False, pages=[], section_hint=None
- `test_document_map_full_serialization` — populate with patient/dob + 3 presence entries + sections, serialize/deserialize, all preserved

### Smoke test
```bash
uv run --project /Users/blake/Repo/ehi-ignite-challenge pytest lib/tests/test_extract/ api/tests/test_harmonize_api.py api/tests/test_context_builder.py -q
```
Must pass. New schema is dormant — not yet wired into any pipeline; no behavior change.

### Acceptance
- New `DocumentMap` and `ResourcePresence` schemas defined
- New `_DOCUMENT_MAP_PROMPT` constant defined
- Tests pass
- No existing pipeline behavior changed

### Commit message
```
feat(scout-t01): DocumentMap schema + scout-pass prompt

New Pydantic schemas DocumentMap (extends DocumentContext) and
ResourcePresence capture a routing manifest: per-resource-type
presence + page hints + section structure.

The new _DOCUMENT_MAP_PROMPT instructs the model to scan the PDF and
produce this manifest. Schema and prompt are dormant — not yet wired
into any registered pipeline. SCOUT-T02 builds the dispatcher that
consumes this output.

Tests: 4 new in test_document_map.py.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## SCOUT-T02 · MultiPassFHIRScoutPipeline class with skip + page-hint dispatcher

- **Status:** ✅ Completed `d784b37` · 2026-05-07 · 244 tests pass
- **Depends on:** SCOUT-T01
- **Goal:** Register a new pipeline `multipass-fhir-scout` that uses `DocumentMap` to skip absent-resource passes and attach page hints to present passes. Subclass `MultiPassFHIRPipeline` to inherit all the FHIR builders + post-passes.

### What to build

#### 1. The dispatcher subclass (after `MultiPassFHIRGemmaTabularPipeline` in the same file)

```python
@register
class MultiPassFHIRScoutPipeline(MultiPassFHIRPipeline):
    """multipass-fhir variant: scout-then-specialist architecture.

    Pass 0 is replaced with a richer "document_map" pass that returns a
    routing manifest (which resource types are present, on which pages).
    Specialist passes are dispatched ONLY for resource types the manifest
    says are present, AND each prompt is augmented with page hints from
    the manifest.

    Output is the same FHIR Bundle shape as multipass-fhir — downstream
    consumers see no difference. The bake-off compares cost/latency/F1
    on real PDFs.

    Hypothesis (per docs/daily/2026-05-07-ClaudeCode.md Entry 8):
    cuts cost 40-60% on sparse docs (lab-only, narrative-only) while
    holding F1 because page-scoped prompts have higher signal-to-noise.
    """

    metadata = PipelineMetadata(
        name="multipass-fhir-scout",
        description=(
            "Scout-then-specialist variant. A document_map pass replaces "
            "Pass 0 and produces a routing manifest; specialist passes "
            "are dispatched only for present resource types, with "
            "page-scoped prompt hints. Same FHIR Bundle output shape."
        ),
        architecture="scout-then-specialist",
        primary_backends=["anthropic"],
        estimated_cost_per_pdf_usd=0.18,  # ~40% lower estimate; bake-off will measure
    )
```

#### 2. Override `_run_pass_0` (or equivalent) to use the document_map prompt

The base `MultiPassFHIRPipeline` runs Pass 0 with `_PASS_0_PROMPT` and `DocumentContext` schema. The scout subclass needs to run with `_DOCUMENT_MAP_PROMPT` and `DocumentMap` schema.

Two approaches:
- **A.** Override the Pass 0 invocation in `extract()` (cleanest if `extract` is structured for it).
- **B.** Define a class attribute `_pass_0_schema` and `_pass_0_prompt` that the parent uses.

Pick whichever the existing code supports with the smallest diff. Likely **A**: override `extract` to run the scout pass first, then call into the rest of the parent's logic with the doc_map.

#### 3. Override the per-resource dispatch loop to skip + augment

```python
def _augmented_passes(self, doc_map: "DocumentMap") -> list[ExtractionPass]:
    """Filter _PASSES to ones the document_map says are present, and
    augment each pass's system_prompt with page hints from the manifest."""
    augmented: list[ExtractionPass] = []
    for original in _PASSES:
        if original.name == "document_context":
            continue  # already replaced by document_map
        presence = doc_map.presence.get(original.name) if hasattr(doc_map, "presence") else None
        if presence is None or not presence.present:
            continue  # skip absent resource types
        # Augment the prompt with page hints
        page_hint = ""
        if presence.pages:
            page_hint = f"\n\nThis content is on page(s) {sorted(set(presence.pages))}."
        if presence.section_hint:
            page_hint += f"\nLook for the section labeled '{presence.section_hint}'."
        new_prompt = original.system_prompt + page_hint
        augmented.append(
            ExtractionPass(
                name=original.name,
                schema=original.schema,
                system_prompt=new_prompt,
                prompt_version=f"{original.prompt_version}+scout",
                schema_version=original.schema_version,
                backend_name=original.backend_name,
                model=original.model,
            )
        )
    return augmented
```

The dispatcher loop in `extract()` calls `_augmented_passes(doc_map)` instead of iterating `_PASSES` directly. Skipped passes mean the per_pass dict is missing those keys — the existing `_merge_to_bundle` already handles that gracefully (`per_pass.get("vital_signs") or VitalSignExtraction()`).

#### 4. Tests in `lib/tests/test_extract/test_scout_pipeline.py`

- `test_scout_pipeline_registered` — `from lib.extract.pipelines import list_pipelines` includes `multipass-fhir-scout`
- `test_augmented_passes_skips_absent_resources` — synthetic DocumentMap with only `vital_signs` present → `_augmented_passes` returns exactly 1 pass (vital_signs)
- `test_augmented_passes_attaches_page_hints` — ResourcePresence with pages=[2, 3] → augmented pass's system_prompt contains "page(s) [2, 3]"
- `test_augmented_passes_attaches_section_hint` — section_hint="Last Filed Vital Signs" → augmented prompt contains that phrase
- `test_augmented_passes_preserves_pass_metadata` — schema, schema_version, backend_name copied unchanged; prompt_version gets "+scout" suffix
- `test_augmented_passes_when_all_absent_returns_empty` — DocumentMap with no `present=True` entries → returns []
- `test_scout_pipeline_metadata_distinct_from_default` — `MultiPassFHIRScoutPipeline.metadata.name == "multipass-fhir-scout"` and `architecture == "scout-then-specialist"`

### Smoke test
```bash
uv run --project /Users/blake/Repo/ehi-ignite-challenge pytest lib/tests/test_extract/ api/tests/test_harmonize_api.py api/tests/test_context_builder.py -q
```
Must pass. The pipeline registers but is not invoked end-to-end in tests (would require a real LLM call). Tests cover the dispatcher LOGIC.

### Acceptance
- `multipass-fhir-scout` appears in the registry alongside `multipass-fhir`
- Augmented-pass list is correct for given DocumentMap inputs
- All existing tests still pass (no regression)

### Commit message
```
feat(scout-t02): MultiPassFHIRScoutPipeline — skip absent passes + page hints

Registers `multipass-fhir-scout` as a parallel pipeline (architecture =
scout-then-specialist). Subclasses MultiPassFHIRPipeline so it inherits
all 13 FHIR builder methods, post-passes, and the deterministic merger.

Two divergences from the parent:
1. Pass 0 uses _DOCUMENT_MAP_PROMPT and DocumentMap schema (not
   DocumentContext). Output is a richer routing manifest.
2. Per-resource dispatch filters _PASSES to only the resource types
   the manifest marks present, AND augments each surviving pass's
   system_prompt with page hints + section hints from the manifest.

Output FHIR Bundle is the same shape as multipass-fhir — downstream
consumers see no difference. Cost/latency/F1 deltas are measured by
the bake-off harness once PDF-LAB-STUDIO ships.

Tests: 7 new in test_scout_pipeline.py covering registration, dispatcher
logic, prompt augmentation, and metadata distinctness.

Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>
```

---

## SCOUT-T03 · Document architecture comparison in PIPELINE-LOG.md

- **Status:** ✅ Completed `c014e69` · 2026-05-07 · doc-only
- **Depends on:** SCOUT-T01, SCOUT-T02
- **Goal:** Append a Move Y entry in `docs/architecture/extraction/PIPELINE-LOG.md` documenting the scout-then-specialist architecture, the hypothesis, the implementation, and the open question (cost/F1 measurement requires PDF-LAB-STUDIO).

### What to build

Add a new entry at the top of `docs/architecture/extraction/PIPELINE-LOG.md` (newest first per convention). Pattern matches Move X (the LOINC post-pass entry just shipped).

### Files you may touch
- `docs/architecture/extraction/PIPELINE-LOG.md`

### Acceptance
- Move Y entry appended
- Index table at the top updated to include Move Y row

---

*Created 2026-05-07. 3 builder-sized tasks. ~1 day of focused work to get the parallel pipeline registered + tested. Real F1 measurement deferred until PDF-LAB-STUDIO.*
