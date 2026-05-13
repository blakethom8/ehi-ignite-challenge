# LLM Context Augmentation Plan

> **Status:** Active. Created 2026-05-11. Phase 1 demo target: 2026-05-13 submission.
> **Authors:** Strategy synthesized with Blake; written for a downstream coding agent.
> **Predecessors:** [`ATLAS-DATA-MODEL.md`](./ATLAS-DATA-MODEL.md), [`PDF-PROCESSOR.md`](./PDF-PROCESSOR.md), [`CONTEXT-ENGINEERING.md`](./CONTEXT-ENGINEERING.md).
>
> **Read this if:** you are picking up the upstream data pipeline and want to know what to build next, why, and in what order. This is a *delta* plan — it extends the architecture already in place; it does not replace it.

---

## 0. What this plan changes (TL;DR)

The Atlas pipeline already ships PDF → multipass FHIR extraction, a cross-source harmonizer with FHIR `Provenance` edges (5 USCDI-core resource types), a SQL-on-FHIR warehouse, and a guided Patient Context intake. **The intake writes Markdown to disk and dies.** Nothing downstream — harmonizer, Caspian, FHIR Charts — reads it. The chart is structurally complete but emotionally empty.

This plan closes that loop and layers in LLM-authored meaning above the deterministic data layer:

1. **Patient Context becomes FHIR-native.** Turns are minted as `Observation` / `MedicationStatement` / `Condition` / `Goal` resources and flow through the existing harmonizer as just another source.
2. **Patient-asserted facts outrank EHR-reported "active" status** on medications (and only there, in Phase 1). The harmonizer learns source-weighted resolution.
3. **LLM-generated per-episode narratives** become a new gold-tier artifact — one `Composition` per `EpisodeOfCare`, not one monolithic patient story.
4. **Caspian's opening turn cites the patient.** The system prompt prepends a voice summary; the structured tables follow.
5. **A conflict adjudicator** runs over the merged record, producing a small set of structured "harmonization caveats" Caspian sees and the UI surfaces as blockers.
6. **Mutability is overwrite-with-history** — current state is overwritten; superseded versions are archived as timestamped JSON for inspection.

What we *defer* to Phase 2: per-source `SourceProfile` resources, patient-supplied episode anchors as extractor priors, the full Cold Read agentic loop, caregiver/prior-provider voices, episode boundary auto-detection (Phase 1 ships with two hand-curated seed episodes).

**Success metric for Phase 1:** the demo arc in §9 runs end-to-end on one patient with zero hand-edits between beats.

---

## 1. Decisions locked in

| # | Decision | Rationale |
|---|---|---|
| D1 | Patient-voice resources are full FHIR resources, not sidecar JSON. | Lets `lib/harmonize/` ingest them as a source — no special-casing. Provenance graph extends naturally. |
| D2 | Patient-asserted **medication active/stopped status** outweighs EHR-reported status. All other fields keep current matcher behavior. | Cedars and Function Health frequently carry stale "active" flags; patients know what they take. Scope tight to avoid over-trusting the patient on dose, codes, or dates. |
| D3 | Narratives are **per-episode-of-care**, not one global patient story. | Smaller LLM calls = sharper text + cheaper. FHIR `EpisodeOfCare` is the right anchor. Per-episode Compositions are independently reviewable and citable. |
| D4 | Mutability: overwrite the "current" narrative on regeneration; archive prior versions in a `history/` directory keyed by timestamp. The new Composition carries `relatesTo.code=replaces` pointing at its predecessor. | Simple, durable, no schema rev. We can promote to a real version-walk UI later without breaking storage. |
| D5 | Phase 1 ships with **two seed episodes per demo patient**, hand-curated. Auto-detection is Phase 2. | Episode detection is its own LLM project; we can't burn the deadline on it. Two episodes are enough to demo the architecture. |
| D6 | Storage: patient-voice FHIR resources live in `data/patient-context/<patient>/fhir/` as JSON. Narratives in `data/narratives/<patient>/<episode-id>/`. Both register as sources for the existing harmonize collection model. | Reuses the collection scaffolding already shipping; one storage shape. |
| D7 | Defer: `SourceProfile` resources, episode-anchor priors for the extractor, agentic Cold Read loop, caregiver/prior-provider voices, episode auto-detection. | All valuable; none survives a 2-day window without cutting Phase 1 quality. |
| D8 | The LLM is **never** on the request path. All LLM work (classification, narrative generation, conflict adjudication, voice summary) runs at *publish time* or *intake time*, writes results to disk, and is read deterministically on subsequent requests. | Matches Atlas data-model Decision 3. Keeps Caspian sub-second. Keeps cost bounded. |
| D9 | All LLM calls go through `api/core/tracing.py` spans so cost, latency, and prompt versions are observable. | Already the convention; non-negotiable for new LLM surfaces. |

---

## 2. Architecture — the new data flow

```
                            BRONZE (immutable per-source)
                ┌──────────┬──────────────┬──────────────────────┐
                │ Cedars   │ Function     │  Patient Context     │ ◀── NEW source
                │ FHIR     │ Health PDFs  │  session.json +      │     (still bronze:
                │          │              │  turns/answers.jsonl │      raw patient turns)
                └────┬─────┴──────┬───────┴──────────┬───────────┘
                     ▼            ▼                  ▼
                     │            │     ┌────────────┴────────────┐
                     │            │     │ T1: patient_voice_to_fhir│
                     │            │     │   Turn → FHIR resources  │
                     │            │     │   Observation / MedStmt  │
                     │            │     │   / Condition / Goal     │
                     │            │     └────────────┬────────────┘
                     ▼            ▼                  ▼
                          SILVER (cross-source harmonized)
                ┌─────────────────────────────────────────────────┐
                │  lib/harmonize/  +  source-weighted resolution  │
                │  Observations / Conditions / Medications /      │
                │  Allergies / Immunizations                      │
                │                                                 │
                │  T2: medication merger consults source weights  │
                │  Patient assertion of stopped/active overrides  │
                │  EHR active flag. Provenance records the call.  │
                └────────────────────┬────────────────────────────┘
                                     ▼
                          GOLD (derived / LLM-augmented)
                ┌─────────────────────────────────────────────────┐
                │  Existing:                                      │
                │    medication_episode, observation_latest, etc. │
                │                                                 │
                │  NEW (this plan):                               │
                │    T4: EpisodeOfCare resources (2 seeds in P1)  │
                │    T5: Composition per EpisodeOfCare            │
                │         (LLM-generated, cited, versioned)       │
                │    T7: harmonization_caveats list               │
                │         (LLM-adjudicated conflicts)             │
                │    T8a: PatientVoiceSummary                     │
                │         (LLM-generated, ≤200 chars)             │
                └────────────────────┬────────────────────────────┘
                                     ▼
                          INTERPRET (Caspian + UI)
                ┌─────────────────────────────────────────────────┐
                │  T8b: ClinicalContext extended with:            │
                │    .patient_voice    (1-2 sentences, cited)     │
                │    .episode_briefs   (list of short summaries)  │
                │    .caveats          (3-7 conflict items)       │
                │                                                 │
                │  T8c: Caspian prepends patient_voice to system  │
                │       prompt; UI renders narratives & caveats   │
                └─────────────────────────────────────────────────┘
```

---

## 3. New FHIR resources we will mint

All carry the standard Atlas provenance shape (`meta.source`, `meta.extension[atlas:source-locator]`). All are emitted from `lib/patient_voice/to_fhir.py` (T1) or `lib/narratives/generator.py` (T5).

### 3.1 Patient-asserted clinical facts (worked examples)

The patient-context model defining the input shape is `api/models.py:880 class PatientContextTurn`. A turn looks like:

```python
PatientContextTurn(
    id="t_4f2c9b",
    role="patient",
    content="I stopped lisinopril about 3 weeks ago — was making me cough.",
    created_at=datetime(2026, 5, 11, 14, 23, 0, tzinfo=UTC),
    linked_gap_id="medication-reality",
)
```

#### Med stopped (the demo's headline case)

```json
{
  "resourceType": "MedicationStatement",
  "id": "pv-sess_a91c-t_4f2c9b-0",
  "status": "stopped",
  "medicationCodeableConcept": {"text": "lisinopril"},
  "subject": {"reference": "Patient/demo"},
  "informationSource": {"reference": "Patient/demo"},
  "dateAsserted": "2026-05-11T14:23:00Z",
  "effectivePeriod": {"end": "2026-04-20"},
  "note": [{"text": "I stopped lisinopril about 3 weeks ago — was making me cough."}],
  "meta": {
    "source": "patient-context://sess_a91c",
    "extension": [
      {"url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-label",
       "valueString": "Patient (self-reported)"},
      {"url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-locator",
       "valueString": "session=sess_a91c;turn=t_4f2c9b;gap=medication-reality"}
    ]
  }
}
```

#### Med started

```json
{
  "resourceType": "MedicationStatement",
  "id": "pv-sess_a91c-t_4f2c9b-1",
  "status": "active",
  "medicationCodeableConcept": {"text": "fish oil"},
  "subject": {"reference": "Patient/demo"},
  "informationSource": {"reference": "Patient/demo"},
  "dateAsserted": "2026-05-11T14:23:00Z",
  "note": [{"text": "Also taking fish oil every morning, my cardiologist suggested it."}],
  "meta": {"source": "patient-context://sess_a91c", "extension": [...] }
}
```

#### Condition claim (low confidence, patient-recorded)

```json
{
  "resourceType": "Condition",
  "id": "pv-sess_a91c-t_71aa3e-0",
  "verificationStatus": {"coding": [{
    "system": "http://terminology.hl7.org/CodeSystem/condition-ver-status",
    "code": "unconfirmed"}]},
  "code": {"text": "kidney stone"},
  "subject": {"reference": "Patient/demo"},
  "recorder": {"reference": "Patient/demo"},
  "onsetPeriod": {"start": "2022-06-01", "end": "2022-08-31"},
  "note": [{"text": "I had a kidney stone in summer 2022."}],
  "meta": {"source": "patient-context://sess_a91c", "extension": [...] }
}
```

#### Goal

```json
{
  "resourceType": "Goal",
  "id": "pv-sess_a91c-t_88de01-0",
  "lifecycleStatus": "active",
  "description": {"text": "Avoid another stroke."},
  "subject": {"reference": "Patient/demo"},
  "expressedBy": {"reference": "Patient/demo"},
  "meta": {"source": "patient-context://sess_a91c", "extension": [...] }
}
```

#### Generic observation (fallback for "I worry about my memory")

```json
{
  "resourceType": "Observation",
  "id": "pv-sess_a91c-t_9c2f15-0",
  "status": "final",
  "code": {"coding": [{
    "system": "http://atlas.healthcaredataai.com/fhir/CodeSystem/patient-voice",
    "code": "patient-claim"}]},
  "category": [{"coding": [{
    "system": "http://terminology.hl7.org/CodeSystem/observation-category",
    "code": "survey"}]}],
  "subject": {"reference": "Patient/demo"},
  "effectiveDateTime": "2026-05-11T14:23:00Z",
  "valueString": "I've been worried about my memory lately.",
  "meta": {"source": "patient-context://sess_a91c", "extension": [...] }
}
```

**Identification convention:** `id = "pv-<session_id>-<turn_id>-<seq>"`. The harmonizer can deterministically reload them from disk and re-merge across runs.

### 3.2 EpisodeOfCare anchors (Phase 1: two hand-seeded)

```json
{
  "resourceType": "EpisodeOfCare",
  "id": "episode-cardiac-meds",
  "status": "active",
  "patient": {"reference": "Patient/demo"},
  "period": {"start": "2019-08-01"},
  "type": [{"coding": [{
    "system": "http://atlas.healthcaredataai.com/fhir/CodeSystem/episode-type",
    "code": "chronic-condition-management",
    "display": "Cardiovascular medication management"}]}],
  "diagnosis": [
    {"condition": {"reference": "Condition/cedars-cond-htn"}, "rank": 1},
    {"condition": {"reference": "Condition/cedars-cond-afib"}, "rank": 2}
  ],
  "extension": [{"url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/episode-narrative-id",
                 "valueReference": {"reference": "Composition/narrative-cardiac-meds-current"}}]
}
```

### 3.3 Per-episode narrative (Composition)

```json
{
  "resourceType": "Composition",
  "id": "narrative-cardiac-meds-2026-05-12T10-15-00Z",
  "status": "final",
  "type": {"coding": [{"system": "http://atlas.healthcaredataai.com/fhir/CodeSystem/composition-type",
                       "code": "episode-narrative"}]},
  "subject": {"reference": "Patient/demo"},
  "date": "2026-05-12T10:15:00Z",
  "extension": [{"url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/episode-ref",
                 "valueReference": {"reference": "EpisodeOfCare/episode-cardiac-meds"}}],
  "section": [
    {"title": "Summary",
     "text": {"status": "additional", "div": "<div>Patient has managed HTN and a-fib...</div>"}},
    {"title": "Timeline",
     "text": {"status": "additional", "div": "<div>Lisinopril started 2019-08 [[ref:MedicationRequest/merged-lisinopril]]. Patient stopped 2026-04-20 [[ref:MedicationStatement/pv-sess_a91c-t_4f2c9b-0]]...</div>"}},
    {"title": "Key facts", "text": {...}},
    {"title": "Patient's own words", "text": {"status": "additional", "div": "<div>\"I stopped lisinopril about 3 weeks ago — was making me cough.\"</div>"}},
    {"title": "Open questions", "text": {...}}
  ],
  "relatesTo": [{"code": "replaces",
                 "targetReference": {"reference": "Composition/narrative-cardiac-meds-2026-05-11T08-30-00Z"}}]
}
```

Each `[[ref:Resource/id]]` marker is validated post-generation against the resource IDs that the prompt explicitly listed as cite-able. Markers pointing at non-existent IDs are rejected and the generator retries once.

### 3.4 Harmonization caveat

```json
{
  "resourceType": "Observation",
  "id": "caveat-lisinopril-status",
  "status": "final",
  "code": {"coding": [{
    "system": "http://atlas.healthcaredataai.com/fhir/CodeSystem/harmonization-caveat",
    "code": "merge-judgment"}]},
  "subject": {"reference": "Patient/demo"},
  "effectiveDateTime": "2026-05-12T10:14:00Z",
  "component": [
    {"code": {"text": "fact_path"}, "valueString": "MedicationRequest/merged-lisinopril.status"},
    {"code": {"text": "verdict"}, "valueString": "stopped"},
    {"code": {"text": "confidence"}, "valueString": "high"},
    {"code": {"text": "rationale"},
     "valueString": "Patient asserted stoppage 2026-04-20 with reason (cough); Cedars active flag has not been refreshed since 2025-09."},
    {"code": {"text": "dissenting_sources"},
     "valueString": "DocumentReference/cedars-2025-summary;DocumentReference/fh-2025-11"}
  ],
  "extension": [{"url": "http://atlas.healthcaredataai.com/fhir/StructureDefinition/caveat-blocker",
                 "valueBoolean": false}]
}
```

### 3.5 Provenance extensions added by this plan

`lib/harmonize/provenance.py` already mints FHIR Provenance with two Atlas extensions (`source-label`, `harmonize-activity`). This plan adds two more:

| URL | Where it appears | Values |
|---|---|---|
| `http://atlas.healthcaredataai.com/fhir/StructureDefinition/resolution-rule` | On `Provenance.entity.extension[]` when a source-weighting rule fired | `"patient-voice-status-override"` (Phase 1; more codes possible in Phase 2) |
| `http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-locator` | On any patient-voice FHIR resource | `"session=<id>;turn=<id>;gap=<id>"` |

These four URLs are catalogued in §13 below as the full Atlas extension vocabulary after this plan lands.

---

## 4. Task breakdown

Each task is **scoped to be picked up cold** by another agent.

- **Goal** (one sentence)
- **Files** (exactly what to touch / create)
- **Acceptance** (what passes)
- **Depends on** (prior task IDs)
- **Out of scope** (so the agent doesn't drift)
- **Failure modes & fallback** (what can go wrong, what to do)

Phase 1 tasks (T1-T9) are sequenced. Phase 2 tasks (P1-P7) are independent.

---

### **T1. Patient-voice → FHIR adapter** *(Phase 1, ~4h)*

**Goal:** convert a completed Patient Context session into a list of FHIR resources persisted to disk.

**Files:**
- **Create** `lib/patient_voice/__init__.py` — empty.
- **Create** `lib/patient_voice/to_fhir.py` — one entry point:
  ```python
  def session_to_fhir_bundle(
      session: PatientContextSessionResponse,
      *,
      classifier: TurnClassifier | None = None,
  ) -> dict:
      """Return a FHIR Bundle (type='collection') of patient-voice resources."""
  ```
- **Create** `lib/patient_voice/classifier.py`:
  ```python
  @dataclass
  class TurnClassification:
      kind: Literal["med_statement", "condition", "goal", "generic"]
      status: str | None              # for med_statement: active|stopped
      drug_text: str | None           # for med_statement
      effective_end_iso: str | None   # for med_statement (stopped)
      condition_text: str | None      # for condition
      onset_period: tuple[str, str] | None  # for condition
      goal_text: str | None           # for goal

  class TurnClassifier(Protocol):
      def classify(self, turn: PatientContextTurn, gap: PatientContextGapCard | None) -> TurnClassification: ...

  class HaikuTurnClassifier:
      """Default impl using Claude Haiku via the shared anthropic client.

      Cached on disk by sha256(turn.id + turn.content + prompt_version + model).
      Cache path: lib/patient_voice/.classifier_cache/<sha>.json
      """
  ```
- **Create** `lib/patient_voice/prompts.py` — `TURN_CLASSIFIER_PROMPT_V1` (template below).
- **Create** `lib/tests/test_patient_voice_to_fhir.py` — fixtures for each kind; use a `FakeTurnClassifier` that returns canned classifications (no live LLM calls in tests).
- **Modify** `api/core/patient_context.py` at the existing `export_session()` call — after Markdown export, call `session_to_fhir_bundle(session)` and write to `data/patient-context/<patient>/fhir/<session_id>.json`.

**Classifier prompt skeleton** (`TURN_CLASSIFIER_PROMPT_V1`):
```
You are extracting structured FHIR-shaped facts from one turn of a patient's own words.

Patient turn (verbatim): "{turn.content}"
Linked gap card: {gap.title if gap else "(none)"} — {gap.prompt if gap else ""}
Today's date: {today}

Classify into exactly one of:
  med_statement  — patient is describing a medication they take, started, or stopped
  condition      — patient is describing a diagnosis or disease they have / had
  goal           — patient is describing what they want from their care
  generic        — anything else (preferences, symptoms, worries, social context)

For med_statement: extract {status: "active"|"stopped", drug_text, effective_end_iso (only if stopped — compute from phrases like "3 weeks ago" relative to today)}.
For condition:    extract {condition_text, onset_period: [start_iso, end_iso] inclusive — be conservative}.
For goal:         extract {goal_text}.

Return JSON only. Refuse to extract codes (RxNorm, ICD, SNOMED) — the harmonizer attaches those later.
```

**Acceptance:**
- A session with "I stopped lisinopril 3 weeks ago" produces a `MedicationStatement` with `status="stopped"` and an `effectivePeriod.end` ≤ 25 days before today.
- The emitted resources all carry the provenance shape from §3.1.
- `data/patient-context/<patient>/fhir/<session_id>.json` is a valid FHIR Bundle (`resourceType=Bundle`, `type=collection`, `entry[]` non-empty).
- Tests green using the fake classifier.

**Depends on:** nothing — `patient_context.py` already runs.

**Out of scope:** wiring into the harmonizer (T3); UI changes; classifier accuracy beyond the three demo patterns.

**Failure modes & fallback:**
- *LLM classifier returns malformed JSON.* Generator retries once with a "JSON only, no prose" reminder; if still bad, emits a `generic` observation with `confidence: low` so the data is at least preserved.
- *Anthropic API down at export time.* Skip FHIR emission; log a span with `status: skipped`; the Markdown export still runs. Re-running export later picks up where it left off.
- *Classifier confidently mis-classifies* (e.g., says `goal` for a med statement). Acceptable in Phase 1; the merged record still includes the patient turn under a different resource type. Phase 2 adds a confidence threshold and a manual review queue.

---

### **T2. Source-weighted medication resolver** *(Phase 1, ~2h)*

**Goal:** teach `lib/harmonize/medications.py` that when sources disagree on `status` and one of the sources is patient-voice, the patient wins.

**Files:**
- **Create** `lib/harmonize/source_weights.py`:
  ```python
  """Source-weight tables. Phase 1 supports medication.status only.

  Weight semantics: when sources disagree on a field, the source with the
  highest weight wins. Default = 1.0. Patient-voice wins on med status
  only; on every other field, default behavior (most-recent / passthrough)
  applies.
  """
  MEDICATION_STATUS_WEIGHTS: dict[str, float] = {
      "patient-context://": 5.0,   # prefix-matched
      "*": 1.0,
  }

  def weight_for_source(source_ref: str, field: str) -> float:
      """Return the weight applied to this (source, field) pair. Defaults to 1.0."""
  ```
- **Modify** `lib/harmonize/medications.py` — at the merge step where `status` is currently resolved (look for the place `MergedMedication.sources` are reduced to a final status), replace the resolution logic with a weight-aware version using `weight_for_source`. Document the asymmetry in the module docstring with a pointer to this plan.
- **Modify** `lib/harmonize/provenance.py:mint_provenance` — when a non-default weight fired, attach `{url: "atlas:resolution-rule", valueString: "patient-voice-status-override"}` to the corresponding entity extension.
- **Add** tests next to the existing harmonize tests (run `git grep "test_harmonize" lib/` to find the right location):
  - Cedars asserts `active`, patient asserts `stopped` → merged is `stopped`, provenance carries the rule code.
  - Cedars asserts dose `20mg`, patient says nothing about dose → merged is `20mg` (patient doesn't override fields they didn't claim).
  - Two non-patient sources disagree on status → existing behavior (most-recent wins).
  - Patient asserts `active`, Cedars asserts `stopped` 6 months ago → patient wins (patient assertion is newer signal).

**Acceptance:**
- All four tests above pass.
- `git grep "patient-context://" lib/harmonize/` returns hits only in `source_weights.py` (no scattering).
- Provenance for the override case includes the rule code, visible in the JSON dump.

**Depends on:** nothing (the harmonizer already runs; this is a local extension).

**Out of scope:** weighting for any field other than medication status. Conditions, observations, allergies, immunizations keep their current resolution logic in Phase 1.

**Failure modes & fallback:**
- *Patient turn produces no `MedicationStatement` (classifier got it wrong).* Harmonizer never sees the patient claim → falls back to EHR-derived status. No regression.
- *Patient says "stopped" but doesn't say when.* `effectivePeriod.end` is `dateAsserted` (today). The most-recent rule still favors the patient.
- *Patient and EHR agree.* Weight doesn't matter; no rule code attached.

---

### **T3. Patient-voice ingest into harmonize collections** *(Phase 1, ~2h)*

**Goal:** when a workspace's harmonize collection runs, include the patient-voice FHIR bundle (T1's output) as a source alongside PDFs and FHIR uploads.

**Files:**
- **Modify** `api/routers/harmonize.py` and `api/core/aggregation.py` — the source-resolution step that walks the collection. After listing PDFs and uploaded JSON, also enumerate `data/patient-context/<patient>/fhir/*.json` for the collection's patient. Tag each as `source_type = "patient-voice"`.
- **Modify** `lib/harmonize/__init__.py` (or wherever the per-source dispatch lives) — accept the new source type and route it through the existing per-resource matchers. Patient-voice resources are already FHIR-shaped; no extraction step needed.
- **Add** a `source_kind` field on `MedicationSource` / `ObservationSource` (`lib/harmonize/models.py`) with values `"ehr-fhir" | "ehr-pdf" | "patient-voice"`. Default to `"ehr-fhir"` for backward compat. Wire `to_fhir.py` to populate `"patient-voice"`.

**Acceptance:**
- A workspace containing one Cedars PDF + one patient-context session (with a "stopped lisinopril" turn) harmonizes and the resulting merged record:
  - Includes a lisinopril `MergedMedication`.
  - Its `status = "stopped"`.
  - Its `sources` list includes both the PDF and the patient-context bundle.
  - The provenance edges in `merged.provenance` include the `patient-voice-status-override` rule code.
- An end-to-end smoke at `scripts/demo_smoke.py` (created in T9) hits this assertion.

**Depends on:** T1 (the FHIR bundle must exist), T2 (the resolver must respect weights).

**Out of scope:** UI surfacing of the override (T8 handles that).

**Failure modes & fallback:**
- *No patient-context bundle for this patient.* Source list is empty for that type; harmonization runs as before.
- *Bundle file is malformed.* Log + skip with a warning surfaced on the harmonize page; don't fail the merge.
- *Patient-voice bundle has resources for the wrong patient.* Filter by `subject.reference == "Patient/<id>"` before ingest. If filter empties the bundle, treat as no bundle.

---

### **T4. Hand-seed two episodes-of-care for the demo patient** *(Phase 1, ~1h)*

**Goal:** because auto-detection is Phase 2, ship two EpisodeOfCare resources hand-written for the demo patient so T5/T6 have something to narrate.

**Files:**
- **Create** `data/narratives/<demo-patient-id>/episodes.json` — JSON array of two `EpisodeOfCare` resources per §3.2.
- **Create** `scripts/seed_demo_episodes.py` — reads the demo patient's harmonized record, lists candidate conditions/encounters, and writes the JSON. The script is idempotent.

**Picking the two episodes:** read the harmonized record. One should be the *chronic* theme that the patient-voice turn is most relevant to (cardiovascular meds, given the lisinopril demo). The other should be *anything else* with a clear time boundary — recent orthopedic event, allergy workup, surgical episode — picked manually by reading the chart. Do not LLM-generate the episode list in Phase 1.

**Acceptance:**
- `data/narratives/<demo-patient-id>/episodes.json` parses, has two entries, and each entry references real `Condition` IDs in the harmonized record.

**Depends on:** harmonize having run for the demo patient (already the case).

**Out of scope:** episode auto-detection; using a patient context turn to suggest episodes. Both are Phase 2 (P1, P3).

**Failure modes & fallback:**
- *Demo patient's chart doesn't have two clean episodes.* Pick a different demo patient. Add a note in the demo script.

---

### **T5. Per-episode narrative generator** *(Phase 1, ~4-5h)*

**Goal:** for each `EpisodeOfCare` in `episodes.json`, generate a `Composition` narrative grounded in the harmonized chart, the patient-voice turns, and the provenance graph.

**Files:**
- **Create** `lib/narratives/__init__.py` — empty.
- **Create** `lib/narratives/generator.py`:
  ```python
  def generate_episode_narrative(
      patient_id: str,
      episode: dict,                  # FHIR EpisodeOfCare
      harmonized_record: dict,        # Bundle of merged resources
      patient_voice_bundle: dict | None,
      *,
      model: str = "claude-sonnet-4-6",
  ) -> dict:                          # FHIR Composition
      """Generate a per-episode narrative as a FHIR Composition."""
  ```
- **Create** `lib/narratives/prompts.py` — `EPISODE_NARRATIVE_PROMPT_V1` (template below).
- **Create** `lib/narratives/storage.py`:
  ```python
  def write_current(patient_id: str, episode_slug: str, composition: dict) -> Path:
      """Atomic write: if current.json exists, move to history/<its-date>.json first.
      Set new composition.relatesTo[0] to point at the prior id.
      Returns the path written.
      """
  ```
- **Create** `api/core/narrative_service.py`:
  ```python
  def regenerate_all_episodes(patient_id: str) -> list[Path]:
      """Read episodes.json, generate a Composition per episode, persist via storage.
      Returns the list of paths written. Tracing-instrumented per episode.
      """
  ```
- **Create** `lib/tests/test_narrative_generator.py` — one fixture episode, assert all required sections present and every `[[ref:...]]` marker resolves.

**Narrative prompt skeleton** (`EPISODE_NARRATIVE_PROMPT_V1`):
```
You are a clinical writer. Produce a one-page narrative for one episode of a
patient's care. Cite resources by ID. Do not invent facts. Quote patient turns
verbatim where they shed light on the episode.

Episode:
  type: {episode.type.coding[0].display}
  period: {episode.period.start} → {episode.period.end or "ongoing"}
  diagnoses: {episode.diagnosis[].condition.reference}

Resources you may cite (ID list — do not cite anything else):
  Conditions: {ids}
  Medications (merged): {ids}
  Observations (merged): {ids}
  Encounters: {ids}
  Patient turns: {ids}

Harmonized facts in this episode window:
{...rendered as a compact table per resource type, oldest first...}

Patient's own words (verbatim, with turn ids):
{...turn quotes that fall in the window OR mention episode diagnoses...}

Produce JSON only, in this shape:
{
  "summary": "<≤200 chars>",
  "timeline": "<markdown bullets, each citing [[ref:Resource/id]]>",
  "key_facts": "<markdown paragraphs with [[ref:...]] markers>",
  "patient_words": "<verbatim quoted turns with [[ref:turn-id]] markers, or empty>",
  "open_questions": "<markdown bullets — what you couldn't reconcile, or empty>"
}
```

**Storage shape** (per D6):
```
data/narratives/<patient-id>/
  episodes.json
  <episode-slug>/
    current.json
    history/
      2026-05-12T14-30-00Z.json
      2026-05-13T09-15-00Z.json
```

**Acceptance:**
- `python -m lib.narratives.generator <patient_id>` produces two `current.json` files (one per seed episode), each parses as a FHIR Composition, every section is non-empty (or explicitly the empty-but-present marker), and every cited resource ID exists in the patient's harmonized record.
- Re-running the generator moves the prior `current.json` into `history/` and the new one has `relatesTo[0].targetReference` pointing at the prior id.
- Each generation emits a trace span with `model`, `prompt_version`, `input_tokens`, `output_tokens`, `cost_usd`, `cited_ids_count`.

**Depends on:** T1, T2, T3, T4.

**Out of scope:** UI rendering (T8); generating across episodes a clinician hasn't selected; calling the generator from the workspace publish flow (T6 does that).

**Failure modes & fallback:**
- *Model returns a `[[ref:...]]` to a non-existent resource.* Generator retries once with the bad refs listed and a "use only the IDs in the cite list" reminder. If still bad on retry, drop the offending markers but keep the surrounding prose; log a warning.
- *Model output isn't valid JSON.* Same retry pattern. After two failures, write a placeholder Composition with `status: "preliminary"` and a `note` recording the failure. UI shows "Narrative unavailable — regenerate."
- *Generation exceeds context window.* Drop oldest resources from the prompt until it fits. Log the truncation in the span.
- *Anthropic API down.* Write a placeholder Composition with `status: "preliminary"`; publish flow continues without blocking.
- *History directory not writable.* Fall back to writing `current.json` only; log a warning. We lose version history for this regeneration but don't fail the publish.

---

### **T6. Trigger narrative regeneration on workspace publish** *(Phase 1, ~1h)*

**Goal:** when a user publishes a workspace snapshot, regenerate all episode narratives.

**Files:**
- Locate the workspace publish handler (`grep -rn "def.*publish" api/routers/ api/core/` — likely `api/routers/harmonize.py` or `api/core/aggregation.py`; pattern parallels `api/core/sof_materialize.py`).
- Modify to call `narrative_service.regenerate_all_episodes(patient_id)` after the snapshot is committed. Phase 1: synchronous. Phase 2: async with the job-polling pattern already used by extraction (`Move U` in PIPELINE-LOG.md).

**Acceptance:**
- Publishing the demo workspace causes both episode narratives to refresh.
- Timestamp in `current.json` is within 60s of the publish moment.
- Publish handler logs an event with `narrative_regen.duration_ms` and `narrative_regen.episodes_count`.

**Depends on:** T5.

**Out of scope:** background job system; partial regeneration.

**Failure modes & fallback:**
- *Narrative generation fails for one episode.* Catch per-episode; continue with the others; surface the failure in the publish-result payload so the UI can show "1 narrative pending."
- *Publish handler not found / has unusual control flow.* Fall back to running narrative regen via a separate `POST /api/narratives/regenerate` endpoint the UI can trigger manually. Note as P1-followup.

---

### **T7. Conflict adjudicator** *(Phase 1 stretch, ~3-4h — drop to Phase 2 if T1-T6 run long)*

**Goal:** after harmonization completes, scan the merged record for unresolved conflicts and ask an LLM to adjudicate, producing the `harmonization_caveats` list described in §3.4.

**Files:**
- **Create** `lib/harmonize/adjudicator.py`:
  ```python
  def adjudicate_conflicts(merged_bundle: dict, *, model: str = "claude-sonnet-4-6") -> list[dict]:
      """Walk the merged bundle, find unresolved cross-source disagreements,
      LLM-adjudicate each one, return a list of caveat FHIR resources.

      In Phase 1: looks at dose, frequency, condition severity, allergy
      criticality, lab unit. Skips medication.status (T2 already handles it).
      """
  ```
- Persist caveats to `data/patient-context/<patient>/caveats.json` (FHIR Bundle of `Observation` resources per §3.4).
- Wire into the publish flow alongside T6.

**Adjudicator prompt skeleton**:
```
Two sources disagree on a clinical fact. Adjudicate.

Fact path: {fact_path}
Source A ({source_a.label}): {value_a}, recorded {source_a.date}
Source B ({source_b.label}): {value_b}, recorded {source_b.date}
{...more sources if any...}

Patient turn context (may be empty): {relevant_patient_turns}

Return JSON:
{
  "verdict": "<one of the values, verbatim>",
  "confidence": "high"|"medium"|"low",
  "rationale": "<one sentence>",
  "dissenting_sources": ["<source ref>", ...]
}

If confidence is "low", the UI will surface this as a blocker for the clinician to resolve.
```

**Acceptance:**
- A workspace with at least one cross-source disagreement (e.g., two PDFs reporting different doses) produces a `caveats.json` with at least one entry, each entry has all five fields from §3.4.
- Caveats with `confidence="low"` are tagged with `extension[caveat-blocker]=true`.

**Depends on:** T3.

**Out of scope:** caveats UI (T8); blocking publish on low-confidence caveats (just emit the flag).

**Failure modes & fallback:**
- *LLM judges every conflict as "low" confidence.* Acceptable; UI lists them and a clinician resolves. Quality metric tracked in observability §11.
- *Adjudicator timeout / API down.* Publish proceeds without caveats.json; UI shows a "Conflict scan unavailable" banner with a retry button.

---

### **T8. Extend ClinicalContext + render in Caspian + UI surfaces** *(Phase 1, ~4-5h)*

**Goal:** the surgeon feels the patient. Extend `ClinicalContext`, prepend the patient voice to Caspian's system prompt, and add narrative + caveats panels to the merged-record UI.

This task has three sub-units (8a/8b/8c) but ships as one atomic change because Caspian and the UI both depend on the extended context shape.

#### T8a. Patient-voice summarizer

**Files:**
- **Create** `lib/patient_voice/summarize.py`:
  ```python
  def summarize_patient_voice(bundle: dict, *, model: str = "claude-haiku-4-5") -> PatientVoiceSummary:
      """Produce a ≤200-char first-person summary citing turn ids."""
  ```
- **Create** the dataclass in `api/core/context_builder.py`:
  ```python
  @dataclass
  class PatientVoiceSummary:
      summary: str         # ≤200 chars
      citations: list[str] # turn ids the summary draws from
      generated_at: datetime
  ```
- Cache on disk: `data/patient-context/<patient>/voice_summary.json` (overwritten on regen).

**Prompt:**
```
The patient has shared the following facts in their own words.
Summarize their current self-described state in ≤200 chars, in third person.
Cite the turn ids you used.

Turns:
{...turns rendered with ids...}

Return JSON: {"summary": "...", "citations": ["turn-id", ...]}
```

#### T8b. ClinicalContext extension

**Files:**
- **Modify** `api/core/context_builder.py:42` `ClinicalContext`. Add:
  - `patient_voice: PatientVoiceSummary | None`
  - `episode_briefs: list[EpisodeBrief]` — `{ episode_id, type, period, one_liner }`. One-liner is the summary section of each episode's `current.json` Composition.
  - `caveats: list[Caveat]` — pulled from `caveats.json` (T7) if present, else `[]`.
- **Modify** `api/core/context_builder.py:422` `build_clinical_context()` — populate the new fields by reading from disk. No recomputation on the request path (per D8).

#### T8c. Caspian + UI

**Files (backend):**
- **Modify** `api/core/provider_assistant.py` and `api/core/provider_assistant_agent_sdk.py` — Caspian's prompt assembly. Prepend `patient_voice.summary` as the first sentence of the system prompt: *"In the patient's own words: <summary>."*. Append `episode_briefs` as a bulleted list under a `## Care episodes` heading. Render caveats as a `## Open conflicts` block listing each with `verdict` + `rationale`.

**Files (frontend):**
- Find the merged-record page (`grep -rn "HarmonizeView\|merged-record" app/src/`) and modify to add:
  - **"Patient's words" card at the top.** Shows `patient_voice.summary` with a chip showing source-session date. Click → opens drawer with the cited turns.
  - **"Care episodes" panel.** Lists each episode with one-liner. Click → drawer with full Composition narrative; `[[ref:Resource/id]]` markers render as clickable chips that scroll-highlight the corresponding merged-record row.
  - **"Conflicts to review" panel.** Lists caveats. Items with `blocker=true` show a red badge. Each item links to the conflicting source rows.

**Acceptance:**
- Caspian's first system-prompt sentence references something the patient actually said in a turn (visible in the trace via `api/middleware/tracing.py`).
- Merged-record page renders all three new panels with non-empty content for the demo patient.
- Clicking a citation chip scrolls / highlights the corresponding merged-record row.
- A Playwright (or equivalent) UI smoke captures three screenshots covering the demo arc's beats 3, 4, 5 (§9).

**Depends on:** T1, T3, T5, T6. T7 optional — caveats panel just shows empty state if `caveats.json` is missing.

**Out of scope:** editing turns from the merged-record page; regenerating narratives from a UI button (Phase 2); rendering narrative history (Phase 2).

**Failure modes & fallback:**
- *`voice_summary.json` missing.* Card hidden (not "Loading..."); the merged record renders without the patient banner.
- *Composition missing for an episode.* Episode card renders the one-liner from `episodes.json` `type.display`; the drawer shows "Narrative not yet generated — publish to regenerate."
- *Citation chip targets an ID that no longer exists* (chart updated, narrative stale). Chip renders disabled with tooltip "Resource superseded; regenerate narrative."

---

### **T9. Demo dry-run + smoke** *(Phase 1, ~2h)*

**Goal:** end-to-end smoke on the demo patient, with a checklist that mirrors the submission video script (§9).

**Files:**
- **Create** `scripts/demo_smoke.py`. Sequence:
  1. Curl-or-API: create patient-context session with the lisinopril/fish-oil turn.
  2. Export → assert `data/patient-context/<patient>/fhir/<session>.json` exists.
  3. Trigger harmonize on a collection containing one Cedars PDF + the new patient-voice bundle.
  4. Assert merged lisinopril row has `status=stopped` and provenance carries `patient-voice-status-override`.
  5. Publish snapshot → assert `data/narratives/<patient>/<episode-slug>/current.json` is freshly written.
  6. Call `POST /assistant/chat` with a stock question; assert the response contains a citation to the patient turn.
  7. Exit 0 on success; print a one-line diagnostic per beat on failure.
- **Create** `docs/architecture/context/LLM-CONTEXT-AUGMENTATION-DEMO.md` — video script (§9 below), screenshot list, manual walkthrough checklist.

**Acceptance:**
- `scripts/demo_smoke.py` exits 0.
- Manual walkthrough completes in <2 minutes.

**Depends on:** T1-T8.

**Failure modes & fallback:**
- *Smoke fails on a single beat.* Print which beat; do not run subsequent beats; exit non-zero with the offending beat id.

---

## 5. Worked end-to-end example (the lisinopril turn)

To make the data flow concrete, here's the artifact trail for the demo's headline beat.

**T0.** Patient submits the turn at `2026-05-11T14:23:00Z`:
```
"I stopped lisinopril about 3 weeks ago — was making me cough.
 Also taking fish oil every morning, my cardiologist suggested it."
```

**Bronze (existing).** Persisted to:
```
data/patient-context/demo/sess_a91c/session.json
data/patient-context/demo/sess_a91c/answers.jsonl  (turn t_4f2c9b)
```

**T1 → silver-ready FHIR.** `lib/patient_voice/to_fhir.py` produces:
```
data/patient-context/demo/fhir/sess_a91c.json
```
…containing the two `MedicationStatement` resources from §3.1 (lisinopril stopped, fish oil active).

**T3 → harmonizer ingest.** Collection harmonize lists the new bundle; matchers run.

**T2 → resolver decision.** Three medication sources for lisinopril: Cedars FHIR (`active`, recorded 2025-09), Function Health PDF (`active`, recorded 2025-11), patient-voice (`stopped`, asserted 2026-05-11). Weight table fires; merged `status=stopped`. Provenance entity for the patient source carries:
```json
{"url": "atlas:resolution-rule", "valueString": "patient-voice-status-override"}
```

**T5 → narrative regen.** On publish, `regenerate_all_episodes("demo")` runs. The cardiac-meds episode includes the lisinopril resources in its window. The model produces a Composition whose "Patient's own words" section quotes the turn verbatim with marker `[[ref:turn-t_4f2c9b]]`. Written to:
```
data/narratives/demo/cardiac-meds/current.json
data/narratives/demo/cardiac-meds/history/2026-05-11T08-30-00Z.json  (the prior version if any)
```

**T7 → caveat.** Adjudicator notices three sources disagreed on `MedicationRequest/merged-lisinopril.status`. Verdict `stopped`, confidence `high`. Written to `data/patient-context/demo/caveats.json`.

**T8a → voice summary.** Haiku reads the bundle, emits:
```json
{"summary": "Stopped lisinopril ~3 weeks ago due to cough. Started fish oil daily on cardiology recommendation.",
 "citations": ["t_4f2c9b"], "generated_at": "2026-05-12T10:16:00Z"}
```

**T8b → ClinicalContext.** Read on next Caspian request:
```python
ClinicalContext(
    patient_voice=PatientVoiceSummary(summary="Stopped lisinopril...", citations=["t_4f2c9b"], ...),
    episode_briefs=[EpisodeBrief(episode_id="episode-cardiac-meds", one_liner="...", ...), ...],
    caveats=[Caveat(fact_path="...lisinopril.status", verdict="stopped", confidence="high", ...)],
    # ... existing fields ...
)
```

**T8c → Caspian sees:**
```
SYSTEM PROMPT (first lines):
  In the patient's own words: Stopped lisinopril ~3 weeks ago due to
  cough. Started fish oil daily on cardiology recommendation.

  ## Care episodes
  - Cardiovascular medication management (active since 2019-08): ...
  - Recent orthopedic event (2024-03 → 2024-06): ...

  ## Open conflicts
  - lisinopril status — verdict: stopped (high confidence). Rationale: ...

  ## Active medications
  ...
```

**UI sees** (merged-record page beat 3 of §9): three source chips on the lisinopril row, Patient chip hovered → turn quoted. Episodes panel shows two cards. Conflicts panel shows the lisinopril caveat.

This is the wedge on a single fact.

---

## 6. Phase 2 — what we are explicitly deferring

### P1. Episode auto-detection
LLM pass that reads the harmonized chart, proposes EpisodeOfCare boundaries, and writes them to `episodes.json`. Replaces hand-seeded T4. Should consult patient-voice for hints ("I had surgery in 2022" → propose a surgical episode in that window). Acceptance: detector agrees with a human reviewer on ≥80% of episodes in a labeled set.

### P2. Source Profiles
Per-source `Library` resources capturing presence map + trust hints + known quirks, written by an LLM at first ingest, consulted deterministically at merge time.

### P3. Episode anchors as extractor priors
When the next PDF lands, Pass 0 / scout receives the patient's claimed episodes as a prompt augmentation: *"If you find evidence of <episode>, tag with `atlas:relates_to_anchor=<id>`."*

### P4. Cold Read agentic loop
Single Agent-SDK pass with tools (`read_bronze`, `read_silver`, `read_patient_turns`, `propose_merge_revision`, `propose_anchor`, `write_narrative_section`) that runs on workspace publish and produces everything in §3 atomically. Replaces orchestration scattered across T5/T6/T7.

### P5. Caregiver / prior-provider voices
Same shape as patient-voice, different `recorder` and source-weight defaults.

### P6. Narrative versioning UI
Render the `history/` directory as a timeline with diffs.

### P7. Source-weight knobs per field
Extend `source_weights.py` from medication-status-only to a per-(resource-type, field, source-kind) matrix.

### P8. Background-job pattern for narrative regen
Move from sync to async (job-polling, like `Move U` extraction).

### P9. Per-fact confidence scoring
For every merged fact, score confidence based on source agreement, source weight, age, and provenance-graph signals.

---

## 7. Order of operations / parallelization

**Single-agent sequential (Day 1 → Day 2):**

```
Day 1 AM:    T1 (patient_voice → FHIR)
Day 1 PM:    T2 (source weights) + T3 (harmonize ingest)
Day 1 EOD:   T4 (seed episodes) — 1h
Day 2 AM:    T5 (narrative generator) — biggest task
Day 2 PM:    T6 (publish trigger) + T8 (Caspian + UI)
Day 2 EOD:   T9 (smoke + script)

T7 (adjudicator) — only if T1-T6 done by lunch on Day 2.
```

**Multi-agent parallel:**
- Agent A owns T1 + T3 (FHIR-side).
- Agent B owns T2 + T7 (harmonizer extensions).
- Agent C owns T4 + T5 + T6 (narrative pipeline).
- Agent D owns T8 (UI integration).
- T9 is the meet-up; one agent owns it after all four merge.

**Sync points where parallel agents must coordinate:**
- After T1 lands: agents B/C/D rebase and pick up the new bundle shape.
- After T3 lands: agent C can use the live merged record for narrative input.
- After T8b lands: agent D can render against the extended ClinicalContext.

---

## 8. Reading list for the implementing agent

Before touching a single file, read:

1. This document (top to bottom).
2. [`ATLAS-DATA-MODEL.md`](./ATLAS-DATA-MODEL.md) — Decision 3 (LLM-authored specs, code-applied at runtime). This plan is the concrete instance of that for the qualitative layer.
3. [`PDF-PROCESSOR.md`](./PDF-PROCESSOR.md) — Decision 1 (output FHIR directly). This plan extends that to patient voice.
4. `api/core/patient_context.py` and `api/models.py:853-924` — existing intake + Pydantic models. Read **before** T1.
5. `lib/harmonize/medications.py` + `lib/harmonize/provenance.py` + `lib/harmonize/models.py` — the merge code you extend in T2.
6. `api/core/context_builder.py` lines 42 + 422 + 687 — `ClinicalContext` definition + `build_clinical_context()` + the constructor call. Read before T8.
7. [`PIPELINE-LOG.md`](./PIPELINE-LOG.md) Moves J/K/L/O/P — what's already merged.
8. `api/core/tracing.py` and [`tracing.md`](./tracing.md) — how to emit spans for the new LLM calls (mandatory per D9).

---

## 9. The Phase 1 demo arc (the 90-second submission video)

Every Phase 1 task exists to make some beat of this work. The smoke script in T9 asserts each beat.

| t | Beat | Asserts |
|---|---|---|
| 0:00-0:10 | Upload Cedars PDF + Function Health PDF for "demo patient." | Existing flow. |
| 0:10-0:25 | Open Patient Context. Patient says: *"I stopped lisinopril about 3 weeks ago — was making me cough. Also taking fish oil every morning, my cardiologist suggested it."* Export. | T1: FHIR bundle exists in `data/patient-context/demo/fhir/`. |
| 0:25-0:40 | Click Harmonize. Merged-record page: lisinopril row shows **status: stopped** with three source chips (Cedars [active], FH [active], Patient [stopped]). Hover Patient → turn quoted. Provenance trail. | T2+T3: merged status = stopped; provenance has override rule. |
| 0:40-0:55 | Open "Care episodes" panel. Two cards. Click "Cardiovascular medication management." Drawer shows one-page narrative. "Patient's own words" section quotes the lisinopril turn verbatim. | T5+T6: Composition exists, cites turn, all sections non-empty. |
| 0:55-1:15 | Open Caspian. First sentence: *"In the patient's own words: stopped lisinopril ~3 weeks ago due to cough; started fish oil daily on cardiology recommendation. Now reviewing..."* Ask *"Is this patient on any ACE inhibitors?"* — answer cites both patient turn and Cedars contradiction. | T8: system prompt has voice summary; response cites turn. |
| 1:15-1:30 | Open "Conflicts to review." Caveat: "Lisinopril active status — verdict: stopped (high confidence). Rationale: ..." | T7+T8c: caveat present, rationale rendered. |

**One-sentence wedge:** *the patient's own words flow through the same provenance graph as the structured chart, and the LLM narrative is the clinician's pre-read.*

---

## 10. Observability & evaluation

Every LLM call introduced by this plan must emit a trace span via `api/core/tracing.py` (per D9). Required attributes per span:

| span name | attributes |
|---|---|
| `patient_voice.classify` | `model`, `prompt_version`, `turn_id`, `gap_id`, `cached: bool`, `input_tokens`, `output_tokens`, `cost_usd`, `kind` (med_statement/condition/goal/generic) |
| `patient_voice.summarize` | `model`, `prompt_version`, `patient_id`, `turn_count`, `output_chars`, `input_tokens`, `output_tokens`, `cost_usd` |
| `narrative.generate` | `model`, `prompt_version`, `patient_id`, `episode_slug`, `cited_ids_count`, `invalid_refs_count` (after validation), `retry_count`, `input_tokens`, `output_tokens`, `cost_usd` |
| `harmonize.adjudicate` | `model`, `prompt_version`, `patient_id`, `fact_path`, `dissent_count`, `confidence`, `input_tokens`, `output_tokens`, `cost_usd` |

**Cost budget for the demo patient** (one full publish cycle):
- T1: ~10 turns × Haiku ≈ $0.005
- T5: 2 episodes × Sonnet ≈ $0.10
- T7: ~3 caveats × Sonnet ≈ $0.03
- T8a: 1 × Haiku ≈ $0.002
- **Total per publish: ~$0.14.** Budget guardrail: alert if a single publish exceeds $1.

**Eval extensions (deferred to a follow-on, but design now so we don't lock ourselves out):**
- `lib/narratives/eval.py` — per-narrative checks: every `[[ref:Resource/id]]` resolves; no resources outside the cite list referenced; required sections present.
- `lib/patient_voice/eval.py` — classifier accuracy against a small labeled fixture set (10-20 turns).
- The existing `lib/extract/eval.py` pattern is the model.

---

## 11. Anti-patterns — common ways this goes wrong

The architecture above is opinionated. Here's what to *not* do, even if it looks tempting in the moment.

1. **Don't bypass FHIR for patient voice.** "Just stick a `patient_notes` string on the ClinicalContext" is faster today and ruinous tomorrow. The whole point of D1 is that patient-voice flows through the same provenance graph as everything else. If you find yourself adding `if source == "patient-voice"` branches in the harmonizer, stop.

2. **Don't put the LLM on the request path.** Caspian must stay sub-second. All LLM work is publish-time or intake-time, results cached. If a code change makes Caspian wait for a model to generate something at request time, revert.

3. **Don't trust the patient on everything.** D2 is scoped to medication active/stopped *only*. Don't extend the override silently. If you want to widen it, edit D2 in this doc and own the change.

4. **Don't auto-detect episodes in Phase 1.** Phase 1 ships two hand-seeded episodes and demos them. Episode auto-detection is its own LLM project (P1). Burning Phase 1 hours on a detector will cost the deadline.

5. **Don't blend narrative generation with structured extraction.** The narrative LLM gets a *list* of resources it may cite. It does not extract new structured facts. New facts come from PDFs (the existing extractor) or patient turns (T1). The narrative model writes prose, period.

6. **Don't introduce a new common data model.** This plan uses FHIR R4 + Atlas extensions. Reach for a custom shape only when FHIR truly can't carry the data — and then use the escape hatches from ATLAS-DATA-MODEL §1.

7. **Don't lose patient turns when the LLM is unavailable.** Every LLM call has a fallback path that preserves data, even if structurally degraded. The Markdown export and the raw `session.json` are always written first; FHIR emission is a downstream enrichment.

8. **Don't conflate "the patient said X" with "X is true."** Patient-asserted resources carry `verificationStatus=unconfirmed` (conditions) and `informationSource=Patient` (med statements). The UI must surface this distinction visually.

9. **Don't add UI affordances to edit patient turns from the merged-record page.** Edits to the patient voice happen in Patient Context, not in the harmonize UI. Single source of truth for the patient's words.

10. **Don't skip the trace spans.** D9 isn't optional. If you ship an LLM call without a span, the cost/quality regression review can't see it, and the next agent will not know it exists.

---

## 12. Phase 1 "done" checklist

Mark each item only when verified with a real run on the demo patient.

- [ ] `data/patient-context/demo/fhir/<session>.json` exists and parses as FHIR Bundle (T1).
- [ ] `lib/harmonize/source_weights.py` exists; `MEDICATION_STATUS_WEIGHTS` has exactly one non-default entry (T2).
- [ ] Merged record for demo patient shows lisinopril `status=stopped` with three source chips, provenance carrying `patient-voice-status-override` (T2+T3).
- [ ] `data/narratives/demo/episodes.json` has two episodes (T4).
- [ ] `data/narratives/demo/<slug>/current.json` exists for each episode, parses as FHIR Composition, every `[[ref:...]]` resolves (T5).
- [ ] Re-running narrative generation moves the prior `current.json` to `history/` (T5).
- [ ] Publishing the workspace triggers narrative regeneration; both `current.json` timestamps refresh (T6).
- [ ] *(stretch)* `data/patient-context/demo/caveats.json` exists with at least one entry (T7).
- [ ] Caspian's system-prompt first sentence quotes / paraphrases a patient turn (T8a+T8c). Verifiable in `traces.db`.
- [ ] Merged-record page renders Patient's Words / Care Episodes / Conflicts panels (T8c).
- [ ] `scripts/demo_smoke.py` exits 0 (T9).
- [ ] Manual walkthrough of §9 completes in <2 minutes (T9).
- [ ] All new LLM calls emit trace spans per §10. Cost per publish <$1.

---

## 13. Atlas extension vocabulary after this plan

The Atlas FHIR extension URLs catalogued — keep this list in sync if you add more.

| URL | First defined | Use |
|---|---|---|
| `http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-label` | existing | Human-readable source name on Provenance.entity |
| `http://atlas.healthcaredataai.com/fhir/StructureDefinition/harmonize-activity` | existing | What harmonization step produced the edge |
| `http://atlas.healthcaredataai.com/fhir/StructureDefinition/resolution-rule` | this plan (T2) | Which source-weight rule fired |
| `http://atlas.healthcaredataai.com/fhir/StructureDefinition/source-locator` | this plan (T1) | Per-resource source pointer (session/turn/gap or page/bbox) |
| `http://atlas.healthcaredataai.com/fhir/StructureDefinition/episode-narrative-id` | this plan (T4) | EpisodeOfCare → Composition pointer |
| `http://atlas.healthcaredataai.com/fhir/StructureDefinition/episode-ref` | this plan (T5) | Composition → EpisodeOfCare reverse pointer |
| `http://atlas.healthcaredataai.com/fhir/StructureDefinition/caveat-blocker` | this plan (T7) | Whether a caveat blocks publish |

Atlas-defined `CodeSystem` URLs introduced:

| URL | Codes |
|---|---|
| `http://atlas.healthcaredataai.com/fhir/CodeSystem/patient-voice` | `patient-claim` |
| `http://atlas.healthcaredataai.com/fhir/CodeSystem/episode-type` | `medication-management`, `surgical-event`, `chronic-condition-management`, `diagnostic-workup`, `acute-episode` |
| `http://atlas.healthcaredataai.com/fhir/CodeSystem/composition-type` | `episode-narrative` |
| `http://atlas.healthcaredataai.com/fhir/CodeSystem/harmonization-caveat` | `merge-judgment` |

---

## 14. What changes when this doc changes

- New task added → append to §4, update §7 ordering, add a checklist item to §12.
- Phase 2 item promoted to Phase 1 → move from §6 to §4, mark "Phase 1 stretch."
- FHIR resource choices in §3 change → update §3, all affected tasks, the worked example in §5, and §13 vocabulary. Do not let code drift from this doc silently.
- A new Atlas extension URL or CodeSystem added → register in §13.
- A new LLM call introduced → register the span in §10.
- Always preserve the central commitment: **patient voice is a FHIR-native source, not a sidecar.** If you find yourself adding "if source is patient voice" branches everywhere, stop and re-check.

---

*Last updated: 2026-05-11.*
