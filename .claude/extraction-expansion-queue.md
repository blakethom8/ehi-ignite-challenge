# Extraction Expansion — Task Queue

> Builder-dispatchable briefs for the 16-task expansion that adds 6+ new FHIR resource types to multipass-fhir output. Strategic context: `docs/daily/2026-05-07-ClaudeCode.md` Entry 7. Branch: `feature/code-resolution-loinc` (stacks on the LOINC build).

**Status legend:** `Queued` → `In Progress (dispatched YYYY-MM-DD HH:MM)` → `Completed (<hash>)` / `⚠ Failed (HH:MM)` / `⛔ Blocked (open question #)`

**Builder agent:** `phase1-builder`. Each brief below is self-contained; the orchestrator (Claude) dispatches with the brief inlined into the agent prompt.

**Convention:** All new resource emissions use extension URL base `https://ehi-atlas.example/fhir/StructureDefinition/...`.

---

## PHASE 0 — Foundation

### T00 · Per-pass schema versioning + extension URL unification

- **Status:** ✅ Completed `96f507c` · 2026-05-07 · 125 tests pass
- **Goal:** Add a `schema_version: str` field to `ExtractionPass` so individual passes can evolve their schema without invalidating other passes' caches. Make the cache key include per-pass schema version. Document the convention in code comments.
- **Why:** Today bumping global `_SCHEMA_VERSION` invalidates ALL pass caches. With 16 passes that's expensive churn. Per-pass versioning means changing the vital-signs schema doesn't re-extract conditions.
- **Context files:**
  - `lib/extract/pipelines/multipass_fhir.py` (lines 186–204 — `ExtractionPass` dataclass; line 372 — `_SCHEMA_VERSION` constant; line 522 — `full_prompt_version` construction)
  - `lib/extract/cache.py` (cache key shape; lines 56–79)
  - `lib/extract/pipelines/__init__.py` (registry)
- **What to build:**
  1. Add `schema_version: str = "v1"` field to the `ExtractionPass` dataclass.
  2. In `_run_one_cell` (around line 522), include the per-pass schema_version in the cache key string. Format: `"multipass-{pipeline_version}/{pass_name}@{prompt_version}#{schema_version}"`.
  3. Add comment in the `ExtractionPass` docstring explaining the convention: "Bump `prompt_version` for prompt-only changes (cheap re-extract for that pass). Bump `schema_version` when the BaseModel shape changes (forces re-extract). Both are per-pass — they do not invalidate other passes' caches."
  4. Audit existing extension URLs across `lib/` for the inconsistency between `ehi-atlas.example/fhir/...` and `atlas.healthcaredataai.com/fhir/...`. **Do not migrate `lib/harmonize/` URLs in this task** — note them in a follow-up comment for T15. Just confirm the new convention is `ehi-atlas.example/fhir/...` for all new emissions.
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, `lib/extract/cache.py` (only if cache key construction lives there — confirm first).
- **Files you must NOT touch:** any prompt strings, any FHIR builder methods, anything in `api/`, `app/`, or `archive/`.
- **Smoke test:**
  ```bash
  uv run pytest lib/tests/test_extract/ api/tests/test_harmonize_api.py api/tests/test_context_builder.py -q
  ```
  Must show 125 passing (no regressions). The cache key change is backward-compatible because old entries simply won't hit the new key shape — they'll re-extract once and persist with the new key.
- **Acceptance:** All 125 existing tests pass. `ExtractionPass.schema_version` exists with default "v1". Cache key string includes `#<schema_version>` segment.

---

## PHASE A — Vital signs + eval expansion

### T01 · Vital-signs extraction pass

- **Status:** ✅ Completed `3f1e0ab` · 2026-05-07 · 132 tests pass
- **Goal:** New extraction pass that captures vital signs from documents (BP, pulse, temperature, RR, O2 sat, weight, height, BMI). Emit as FHIR `Observation` resources with `category: vital-signs`.
- **Why:** Cedars MyHealth review: page 2 has BP 119/71, Pulse 58, Temp 36.4°C, RR 16, O2 98%, Weight 95.7kg, Height 188cm, BMI 27.09 dated 12/12/2025 — we extracted ZERO of these. Vital signs are clinically critical and the Key Labs panel already filters by LOINC, so they slot into existing infrastructure seamlessly.
- **Context files:**
  - `lib/extract/pipelines/multipass_fhir.py` (read the full file — model the new pass on `LabObservationEntry` / `LabObservationExtraction` / `_LAB_OBSERVATIONS_PROMPT` / `_lab_observation_to_fhir`)
  - `pdf-review/cedars-myhealth/notes.md` (the gap that motivated this)
- **What to build:**
  1. **Schema** (`VitalSignEntry`, `VitalSignExtraction` BaseModels) with fields: `vital_type` (Literal: "blood-pressure-systolic" | "blood-pressure-diastolic" | "heart-rate" | "body-temperature" | "respiratory-rate" | "oxygen-saturation" | "body-weight" | "body-height" | "bmi"), `value: float | None`, `unit: str | None`, `effective_date: str | None`, `reference_range_low/high: float | None`, `flag: Literal["H","L","N",...] | None`, `page: int | None`, `source_text: str | None`.
  2. **Prompt** (`_VITAL_SIGNS_PROMPT`): instruct the model to extract vital-signs tables (Last Filed Vital Signs / Vital Signs / etc.). For BP, emit TWO entries (systolic + diastolic). UCUM units. ISO date.
  3. **`_PASSES` entry** with `name="vital_signs"`, `schema_version="v1"`, `prompt_version="v1"`. Per architecture audit: this is a tabular pass — eligible for Gemma in the variant pipeline.
  4. **FHIR builder method** `_vital_sign_to_fhir(vs, common_meta, layout, doc_context) -> dict`. Maps `vital_type` to LOINC codes (8480-6 systolic, 8462-4 diastolic, 8867-4 heart rate, 8310-5 body temp, 9279-1 RR, 2708-6 O2 sat, 29463-7 body weight, 8302-2 body height, 39156-5 BMI). Set `category: [{ coding: [{ system: "http://terminology.hl7.org/CodeSystem/observation-category", code: "vital-signs", display: "Vital Signs" }] }]`. Include `effectiveDateTime`, `valueQuantity` with UCUM, `meta.extension` with bbox.
  5. **Entry-emission loop** in `_merge_to_bundle` (after the lab_observations section): pull `vs_extraction`, iterate, append.
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, `lib/tests/test_extract/test_vital_signs.py` (new).
- **Files you must NOT touch:** existing pass schemas/prompts, `eval.py` (T02 handles it).
- **Smoke test:**
  ```bash
  uv run pytest lib/tests/test_extract/test_vital_signs.py -q
  ```
  Tests must include: schema validation, FHIR builder produces `category=vital-signs`, BP extraction emits 2 observations (systolic + diastolic), unknown `vital_type` is rejected by the Literal.
- **Acceptance:** New tests pass. Full suite still passes (126+ total). New pass appears in `list_pipelines()` indirectly (it's part of multipass-fhir). LOINC codes for vital_type values are correct per the mapping above.

### T02 · Update `eval.py` to support new fact types

- **Status:** ✅ Completed `a592e9a` · 2026-05-07 · 136 tests pass
- **Goal:** Extend the eval harness `FactType` Literal and `_FACT_TYPES` mapping so vital signs (and future passes) participate in F1 scoring.
- **Context files:**
  - `lib/extract/eval.py` (lines 58, 528, 147–269)
- **What to build:**
  1. Extend `FactType` Literal: add `"vital-sign"`. (Future passes will add their own; T02 only adds vital-sign.)
  2. Extend `_FACT_TYPES` tuple if needed.
  3. Add a resource-extraction bucket in `facts_from_fhir_resources` for `Observation` with `category=vital-signs` (vs `category=laboratory`). Same shape as existing `Observation` bucket; just discriminate by category.
  4. Make sure preferred-systems for vital-sign LOINC matching uses `http://loinc.org` (already the default).
- **Files you may touch:** `lib/extract/eval.py`, `lib/tests/test_extract/test_eval_vital_signs.py` (new — minimal coverage for the new bucket).
- **Smoke test:**
  ```bash
  uv run pytest lib/tests/test_extract/ -q
  ```
- **Acceptance:** `FactType` includes `"vital-sign"`. Synthetic test bundle with vital-signs Observations gets evaluated correctly.

---

## PHASE B — Encounters + care network

### T03 · Encounter extraction pass

- **Status:** ✅ Completed `40ecd9c` · 2026-05-07 · 144 tests pass
- **Goal:** New pass that extracts office visits / clinical encounters as FHIR `Encounter` resources.
- **Why:** Cedars MyHealth shows "04/22/2026 Office Visit at Beverly Hills Allergy with Ani Shirvanian, NP" — we extracted zero Encounter resources. Downstream code (`api/routers/patients.py:761` etc.) is ALREADY consuming `record.encounters` to build timelines, care team, sites of service. The whole "Encounters" tab in History.tsx is empty because extraction never emits these.
- **Context files:**
  - `lib/extract/pipelines/multipass_fhir.py`
  - `lib/fhir_parser/extractors.py` (read how Encounter is currently parsed FROM bundles; mirror the shape for emission)
  - `data/synthea-samples/synthea-r4-individual/fhir/<one bundle>` (canonical Encounter shape reference)
  - `api/routers/patients.py` lines 227–310 (`_care_network_summary`), 761–905 (`patient_timeline`, `encounter_detail`)
- **What to build:**
  1. **Schema** (`EncounterEntry`, `EncounterExtraction`) with fields: `encounter_id: str | None` (synthesize a UUID if absent), `status: Literal["finished","in-progress","planned","cancelled"] = "finished"`, `class_code: str | None` (AMB / IMP / EMER mapping), `type_display: str | None` (e.g., "Office Visit"), `period_start: str | None` (ISO), `period_end: str | None`, `service_provider_display: str | None` (organization), `participant_display: str | None` (practitioner), `reason_text: str | None`, `page: int | None`.
  2. **Prompt** (`_ENCOUNTERS_PROMPT`): "Extract every encounter / visit / appointment recorded in the document. Use ISO 8601 dates. If only the date is shown, use that as period.start with no period.end."
  3. **`_PASSES` entry** `name="encounter"`, narrative-class pass (default Claude).
  4. **FHIR builder** `_encounter_to_fhir` emitting `Encounter` resource with `class.coding` (system=`http://terminology.hl7.org/CodeSystem/v3-ActCode`), `type[].text`, `period`, `serviceProvider.display`, `participant[].individual.display`, `reasonCode[].text`, `meta.extension` w/ bbox.
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, `lib/tests/test_extract/test_encounter.py` (new).
- **Smoke test:**
  ```bash
  uv run pytest lib/tests/test_extract/test_encounter.py -q
  ```

### T04 · Practitioner extraction pass

- **Status:** ✅ Completed `95c6702` · 2026-05-07 · 153 tests pass
- **Goal:** Extract care-team practitioners as FHIR `Practitioner` resources. Capture NPI when present.
- **Context files:** same as T03 + Synthea Practitioner shape (look in any Synthea bundle for a Practitioner entry; canonical shape includes `identifier[system="http://hl7.org/fhir/sid/us-npi"]`, `name[]`, `telecom`, `address`).
- **What to build:**
  1. **Schema** (`PractitionerEntry`, `PractitionerExtraction`): `practitioner_id: str | None`, `npi: str | None`, `display_name: str | None`, `family_name: str | None`, `given_names: list[str] = []`, `prefix: str | None` (Dr./MD/NP/etc.), `specialty: str | None`, `phone: str | None`, `address_line: str | None`, `city: str | None`, `state: str | None`, `postal_code: str | None`, `page: int | None`.
  2. **Prompt** (`_PRACTITIONERS_PROMPT`): "Extract every practitioner / provider / physician mentioned. Capture NPI if printed. Capture specialty if mentioned (e.g., 'Board certified in Allergy & Immunology'). Distinguish first-time mentions from repeated references — emit ONE entry per unique practitioner."
  3. **`_PASSES` entry** `name="practitioner"`.
  4. **FHIR builder** `_practitioner_to_fhir` emitting `Practitioner` with `identifier[].system="http://hl7.org/fhir/sid/us-npi"` if NPI present, `name[].family/given/prefix`, `telecom`, `address`.
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, `lib/tests/test_extract/test_practitioner.py` (new).

### T05 · Organization extraction pass

- **Status:** ✅ Completed `f58adf5` · 2026-05-07 · 162 tests pass
- **Goal:** Extract care facilities as FHIR `Organization` resources.
- **What to build:**
  1. **Schema** (`OrganizationEntry`, `OrganizationExtraction`): `organization_id: str | None`, `name: str | None`, `type_display: str | None` (e.g., "Healthcare Provider", "Hospital", "Lab"), `phone: str | None`, `address_line/city/state/postal_code: str | None`, `page: int | None`.
  2. **Prompt** (`_ORGANIZATIONS_PROMPT`): "Extract every healthcare organization / facility / lab / hospital / clinic mentioned in the document."
  3. **FHIR builder** `_organization_to_fhir` with `type[].coding[].system="http://terminology.hl7.org/CodeSystem/organization-type"`, `name`, `telecom`, `address`.
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, `lib/tests/test_extract/test_organization.py` (new).

### T06 · Encounter linkage on existing resources

- **Status:** ✅ Completed `5473052` · 2026-05-07 · 169 tests pass
- **Goal:** When the doc-context indicates an encounter (e.g., "documented in this encounter" sections), set `encounter: Reference(Encounter/...)` on Observations / Conditions / MedicationRequests / Procedures emitted within that encounter scope.
- **Why:** Cedars MyHealth's "Progress Notes / documented in this encounter" sections clearly tie facts to specific visits. Today our resources reference no encounter, breaking timeline grouping.
- **Approach:** Augment `_merge_to_bundle` to: (a) extract encounter section markers from the doc-context output (Pass 0 may need a small enhancement), (b) when a resource's source-text is in an "encounter" section, set its `encounter` reference.
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, possibly Pass 0 prompt adjustment.

---

## PHASE C — Narrative & documents

### T07 · Clinical-notes extraction pass (DocumentReference + Composition)

- **Status:** ✅ Completed `71b7d48` · 2026-05-07 · 179 tests pass
- **Goal:** Extract narrative clinical notes (Subjective, Physical Exam, Assessment & Plan, patient education paragraphs) as FHIR `DocumentReference` (narrative container) + `Composition` (sectioned structure).
- **Why:** **The original ask.** Cedars MyHealth pages 22-24 have full SOAP-style progress notes that we currently discard.
- **Context files:** existing `Composition` parsing pattern in `api/core/harmonize_service.py:1051–1064` (shows what downstream expects).
- **What to build:**
  1. **Schema** (`ClinicalNoteEntry`, `ClinicalNoteExtraction`): `note_id: str | None`, `note_type: Literal["progress-note","discharge-summary","consult-note","procedure-note","other"] = "progress-note"`, `author_name: str | None`, `author_role: str | None`, `encounter_date: str | None`, `sections: list[ClinicalNoteSection]` where `ClinicalNoteSection` = `{title: str, code: str | None (LOINC), narrative_text: str}`, `page_start/page_end: int | None`.
  2. **Prompt**: "Extract long-form narrative clinical notes (progress notes, consult notes, A&P paragraphs). Preserve section structure (Subjective, Objective/Physical Exam, Assessment, Plan, Patient Education). Capture author name + role + date. Verbatim narrative — do NOT summarize."
  3. **FHIR builders**: emit BOTH a `DocumentReference` (with `content[].attachment.contentType="text/plain"` + `data` base64-encoded narrative OR `content[].attachment.url` if we keep the original) AND a `Composition` (with `section[]` per `ClinicalNoteSection`, including `code.coding[].system="http://loinc.org"` mapped via standard A&P LOINC codes: 11488-4 Consultation note, 11506-3 Progress note, 51847-2 Evaluation + Plan note, etc.).
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, `lib/tests/test_extract/test_clinical_notes.py` (new).

### T08 · Note ↔ Encounter linkage

- **Status:** ✅ Completed `d990d6f` · 2026-05-07 · 185 tests pass
- **Depends on:** T03 (Encounter pass), T07 (Clinical-notes pass)
- **Goal:** Link DocumentReference / Composition resources to the Encounter they belong to.
- **Approach:** Match by encounter_date + author. If multiple encounters on same date, prefer match on practitioner.

---

## PHASE D — Patient demographics

### T09 · Patient extraction pass with US Core extensions

- **Status:** ✅ Completed `08521ae` · 2026-05-07 · 200 tests pass
- **Goal:** Emit a FHIR `Patient` resource with full US Core extensions (race, ethnicity, birthsex, birthplace).
- **Context files:** `lib/fhir_parser/extractors.py:230–260` (existing PARSING with US Core extensions — mirror the shape on emission).
- **What to build:**
  1. **Schema** (`PatientEntry`, `PatientExtraction`): name, DOB, gender, address, phone, email, race, ethnicity, marital_status, language, mrn (identifier).
  2. **Prompt**: "Extract patient demographics. Use US Core race / ethnicity codes when possible (OMB categories)."
  3. **FHIR builder** emitting `Patient` with US Core extensions at `http://hl7.org/fhir/us/core/StructureDefinition/us-core-race`, `us-core-ethnicity`, `us-core-birthsex`.

### T10 · Replace `Patient/unknown` references

- **Status:** ✅ Completed `90d8ea1` · 2026-05-07 · 211 tests pass
- **Depends on:** T09
- **Goal:** Once Patient resource exists in the bundle, all other resources should `subject: Reference(Patient/<actual-id>)` instead of `Patient/unknown`.

---

## PHASE E — Auxiliary resources

### T11 · Coverage extraction pass

- **Status:** ✅ Completed `9754df1` · 2026-05-07 · 221 tests pass
- **Goal:** Extract insurance/payor info as FHIR `Coverage` resource.
- **What to build:**
  1. **Schema** (`CoverageEntry`, `CoverageExtraction`): `coverage_id: str | None`, `status: Literal["active","cancelled","draft","entered-in-error"] = "active"`, `payor_name: str | None`, `member_id: str | None`, `subscriber_id: str | None`, `group_id: str | None`, `plan_type: str | None` (HMO, PPO, etc.), `effective_period_start/end: str | None`.
  2. **FHIR builder** emitting `Coverage` with `payor[].display`, `subscriberId`, `beneficiary: Reference(Patient/...)`, `period`.

### T12 · Social-history Observations pass

- **Status:** ✅ Completed `624772e` · 2026-05-07 · 228 tests pass
- **Goal:** Tobacco / alcohol / depression-screening (PHQ-9) / occupation as FHIR `Observation` with appropriate `category` (social-history or survey).
- **What to build:**
  1. **Schema** (`SocialHistoryEntry`, `SocialHistoryExtraction`): `topic: Literal["tobacco","alcohol","drugs","occupation","sexual-orientation","gender-identity","phq-9","phq-2"]`, `value: str | None`, `value_quantity: float | None`, `effective_date: str | None`.
  2. **FHIR builder**: emit `Observation` with `category=[{coding:[{system:"http://terminology.hl7.org/CodeSystem/observation-category", code:"social-history" or "survey"}]}]`. LOINC mapping: 72166-2 Tobacco smoking status, 74076-4 Alcohol use, 44261-6 PHQ-9 total score, 11341-5 History of Occupation.

---

## PHASE F — Identity resolution + harmonize

### T13 · NPI-based Practitioner matcher in lib/harmonize/

- **Status:** ✅ Completed `4bddfd6` · 2026-05-07 · 367 tests pass
- **Goal:** Cross-source merge for Practitioner resources. Match by NPI; fall back to family+given+prefix normalized name.
- **Context files:** `lib/harmonize/conditions.py` (model the matcher pattern), `lib/harmonize/__init__.py`.
- **Files you may touch:** `lib/harmonize/practitioners.py` (new), `lib/tests/test_harmonize_practitioners.py` (new).

### T14 · Name+address Organization matcher

- **Status:** ✅ Completed `8d47bea` · 2026-05-07 · 377 tests pass
- **Goal:** Cross-source merge for Organization. Match by normalized name + city/state.
- **Files you may touch:** `lib/harmonize/organizations.py` (new), tests.

### T15 · DocumentReference dataclass in lib/fhir_parser/models.py

- **Status:** ✅ Completed `1d2fa7f` · 2026-05-07 · 385 tests pass
- **Goal:** Add a `DocumentReferenceRecord` dataclass to `lib/fhir_parser/models.py` so `lib/fhir_parser/extractors.py` can read DocumentReferences from bundles. Mirror existing `EncounterRecord` pattern.

---

## Sequencing

```
T00 (foundation, ~1h)
  ↓
T01 → T02              (Phase A — vital signs + eval)
  ↓
T03 ║ T04 ║ T05 → T06  (Phase B — encounters + care network; T03/T04/T05 parallel-safe)
  ↓
T07 → T08              (Phase C — clinical notes)
  ↓
T09 → T10              (Phase D — patient demographics)
  ↓
T11 ║ T12              (Phase E — auxiliary resources; parallel-safe)
  ↓
T13 ║ T14 ║ T15        (Phase F — identity resolution; all parallel-safe)
```

Phase boundaries: orchestrator runs full test sweep + status report to user before next phase begins.

---

*Created 2026-05-07. 16 builder-sized tasks. Total estimate: ~10–14 condensed days.*
