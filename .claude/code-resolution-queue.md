# Code Resolution Post-Pass — Task Queue

> Phase 2 promotion of the terminology layer. Closes the LOINC + SNOMED + interpretation + clinical-category gaps surfaced by the Function Health parser comparison (`pdf-review/blake-functionhealth-2025-11-19/notes.md`). Strategic context: `docs/daily/2026-05-07-ClaudeCode.md` Entry 6.

**Status legend:** `Queued` → `In Progress (dispatched YYYY-MM-DD HH:MM)` → `Completed (hash)` / `⚠ In Progress (failed HH:MM)` / `⛔ Blocked (open question #)`

**Kind:** all `builder` (Sonnet) unless noted.

---

## Prerequisites

- **PROMOTE-EXTRACT must ship first.** All paths in this queue assume `lib/extract/`. The reference data lives at `ehi-atlas/corpus/reference/` (stays in Atlas zone — it's data, not code).
- **CODE-T04/T05 (SNOMED) blocked on UMLS registration.** User registers at https://uts.nlm.nih.gov, drops API key in `.env`. CODE-T01..T03 (LOINC) and CODE-T06..T07 (interpretation, category) are unblocked.

---

## CODE-T01 · Extend LOINC reference table to ~500 common labs

- **Status:** Queued
- **Kind:** builder
- **Goal:** Grow `corpus/reference/loinc/` from the 22-code showcase to ~500 entries covering the long tail of common lab tests, with verified codes for the 58 tests in our example Function Health PDF.
- **Why:** Today's curated table covers 17 of the 58 tests in our PDF (29%). To close the visible gap with Function Health (67%), we need broad LOINC coverage.
- **Approach:**
  1. Keep the existing `showcase-loinc.json` schema (`code`, `display`, `system`, `unit`, `category`, `notes`). Add fields: `aliases: list[str]` (canonical aliases for matching) and `verified_against: list[str]` (tags like "function-health-2025-11-19" for traceability).
  2. Build curated set from three sources:
     - **Function Health verified subset** — extract from `pdf-review/blake-functionhealth-2025-11-19/function-outputs/...har`. ~38 codes verified against a real-world parser.
     - **NLM Clinical Tables LOINC API** (`/api/loinc_items/v3/search`) — fill gaps for tests where FH didn't emit codes (eGFR, ALT, etc.). Pull top candidates, filter to Serum/Plasma scale, pick best match.
     - **Common-lab universe** — top ~300 LOINC codes by frequency (Quest/LabCorp standard panels: CMP, BMP, CBC, lipid panel, thyroid, A1c, urinalysis, lipid-extended, hormone panels, vitamins).
  3. Output: `corpus/reference/loinc/common-labs.json` (replaces `showcase-loinc.json` or supersedes it; decide in implementation).
- **Files you may touch:** `corpus/reference/loinc/common-labs.json`, `corpus/reference/loinc/_curate.py` (helper script — committed for repro), `corpus/reference/VERSIONS.md` (note the bump).
- **Files you must NOT touch:** any `lib/`, `api/`, `app/` code yet — this task is data only.
- **Smoke test:**
  ```bash
  uv run python -c "
  import json
  d = json.load(open('ehi-atlas/corpus/reference/loinc/common-labs.json'))
  print(f'codes: {len(d[\"codes\"])}')
  # sanity check: known codes from Function Health verified set
  codes_by_loinc = {c['code']: c for c in d['codes']}
  for expected in ['2345-7', '3094-0', '2160-0', '3097-3', '4548-4', '1884-6']:
      assert expected in codes_by_loinc, f'missing {expected}'
  print('all known codes present')
  "
  ```
- **Acceptance:** ≥500 LOINC entries; covers all 58 tests from the Function Health PDF (verifiable by display-name match); JSON validates against the schema; `_curate.py` is reproducible.

---

## CODE-T02 · LOINC matcher module

- **Status:** Queued
- **Kind:** builder
- **Depends on:** CODE-T01
- **Goal:** A pure-Python module that takes an extracted display name (`"Glucose"`, `"BUN"`, `"WBC Count"`) and returns a LOINC code (or null) with confidence score.
- **Approach:**
  1. Module: `lib/extract/terminology/loinc_matcher.py` (after PROMOTE-EXTRACT).
  2. Load `common-labs.json` once at module import.
  3. Public API:
     ```python
     def match_loinc(display: str, unit: str | None = None) -> LoincMatch | None: ...
     ```
     `LoincMatch` carries `code`, `display`, `confidence: float`, `match_type: Literal["exact","alias","fuzzy"]`.
  4. Match strategy:
     - **Exact match** on normalized display → confidence 1.0
     - **Alias match** on the `aliases` list of any entry → confidence 0.9
     - **Fuzzy match** on Jaccard token overlap ≥0.7 → confidence 0.5–0.8
     - Use `unit` as a tiebreaker when multiple candidates pass (prefer entry whose `unit` matches input unit)
  5. Display normalization rules:
     - Lowercase, strip parentheticals, trim whitespace
     - Expand common abbreviations: `ALT → Alanine Aminotransferase`, `eGFR → Estimated Glomerular Filtration Rate`, `MCV → Mean Corpuscular Volume`, `WBC → White Blood Cell`, `RBC → Red Blood Cell`, `MCH → Mean Corpuscular Hemoglobin`, `MCHC → Mean Corpuscular Hemoglobin Concentration`, `RDW → Red Cell Distribution Width`, `MPV → Mean Platelet Volume`, `BUN → Blood Urea Nitrogen`, `A1c → Hemoglobin A1c`, `ApoB → Apolipoprotein B`, `hs-CRP → High-Sensitivity C-Reactive Protein`
- **Files you may touch:** `lib/extract/terminology/__init__.py` (new), `lib/extract/terminology/loinc_matcher.py` (new), `lib/tests/test_loinc_matcher.py` (new).
- **Smoke test:**
  ```bash
  uv run pytest lib/tests/test_loinc_matcher.py -q
  ```
  Tests must include: exact match (`"Glucose" → 2345-7`), alias match (`"BUN" → 3094-0`), unit-tiebreaker (different LOINC for same display + different units), fuzzy fallback for known variants (`"Hgb" → 718-7`), null for nonsense input.
- **Acceptance:** ≥95% match rate on the 58 tests in our Function Health PDF.

---

## CODE-T03 · Wire LOINC matcher into multipass-fhir as post-pass

- **Status:** Queued
- **Kind:** builder
- **Depends on:** CODE-T01 + CODE-T02
- **Goal:** After multipass extraction emits Observations, run each through the LOINC matcher and attach the resolved code.
- **Approach:**
  1. Edit `lib/extract/pipelines/multipass_fhir.py` (after PROMOTE-EXTRACT).
  2. After per-resource passes complete, before bundle assembly: iterate each `LabObservationEntry`, call `match_loinc(test_name, unit)`, populate `loinc_code` field.
  3. Track stats: how many got exact / alias / fuzzy / no-match.
  4. Emit a `meta.extension` per Observation indicating resolution source: `manual` (already populated by extraction), `lookup-table` (post-pass added), `unmatched` (post-pass tried, failed).
  5. Don't overwrite codes already populated by extraction (rare but possible).
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, `lib/tests/test_multipass_fhir_loinc_post_pass.py` (new).
- **Smoke test:**
  ```bash
  uv run pytest lib/tests/test_multipass_fhir_loinc_post_pass.py -q
  ```
  Test: feed a synthetic `LabObservationExtraction` with 5 known tests + 1 unmatchable; assert 5 get codes, 1 stays null, all 6 get the resolution-source extension.
- **Acceptance:** End-to-end run on the Function Health PDF produces ≥80% LOINC code coverage (vs 0% today).

---

## CODE-T04 · Curate SNOMED conditions reference table

- **Status:** ⛔ Blocked on UMLS registration
- **Kind:** builder
- **Goal:** Build `corpus/reference/snomed/common-conditions.json` covering ~500 most common diagnoses with codes verified against UMLS.
- **Why:** Conditions schema needs SNOMED for USCDI conformance + harmonization wedge.
- **Approach:**
  1. Add `snomed_code: str | None` field to `ConditionEntry` in `lib/extract/pipelines/multipass_fhir.py` (mirror the `loinc_code` pattern).
  2. Curate 500 SNOMED concepts via UMLS REST API (`uts-ws.nlm.nih.gov/rest/...`). Common-condition list: top ~300 chronic conditions + ~200 acute presentations + cardiovascular + endocrine + GI + respiratory + neuro + mental health + musculoskeletal + dermatology + GU.
  3. For each entry: `code`, `display`, `system: http://snomed.info/sct`, `aliases: list[str]`, `parent_codes: list[str]` (1-2 levels of IS-A hierarchy for fuzzy matching).
- **Files you may touch:** `corpus/reference/snomed/common-conditions.json` (new), `corpus/reference/snomed/_curate.py` (new — UMLS API client), `corpus/reference/VERSIONS.md`.
- **Smoke test:** ≥500 SNOMED entries, sanity-check known codes (`73211009` = Diabetes mellitus, `38341003` = Essential hypertension).
- **Blocker resolution:** User registers at https://uts.nlm.nih.gov, drops API key in `.env`.

---

## CODE-T05 · SNOMED matcher + Conditions post-pass

- **Status:** ⛔ Blocked on CODE-T04
- **Kind:** builder
- **Goal:** Match condition display names to SNOMED codes; wire into multipass-fhir as a Conditions post-pass.
- **Approach:** Same shape as CODE-T02/T03 but for conditions, with one addition: when exact/alias match fails, walk up the parent hierarchy from the curated `parent_codes` field for partial matches (return parent + lower confidence).
- **Files you may touch:** `lib/extract/terminology/snomed_matcher.py` (new), `lib/extract/pipelines/multipass_fhir.py`, tests.
- **Smoke test:** ≥90% match rate on conditions extracted from a synthetic test corpus (we need to assemble this — Synthea conditions are a good proxy).

---

## CODE-T06 · INTERPRETATION post-pass

- **Status:** Queued
- **Kind:** builder
- **Depends on:** none functionally (could ship before T01-T03), but most useful after T03 because resolved LOINC enables better reference-range lookups.
- **Goal:** For every Observation with both `valueQuantity` and `referenceRange`, derive `interpretation: H | L | N | A`. Deterministic — no LLM.
- **Approach:**
  1. Add a post-pass step in `lib/extract/pipelines/multipass_fhir.py`.
  2. For each Observation:
     - If extraction populated `flag` already, map it (`H/HH/A → H`, `L/LL → L`, `N → N`).
     - Else if `valueQuantity` and `referenceRange.low/high` both present: numeric compare. `< low → L`, `> high → H`, else `N`.
     - Map to FHIR `interpretation` CodeableConcept using `http://terminology.hl7.org/CodeSystem/v3-ObservationInterpretation` codes.
  3. Edge cases: text values ("Negative", "None Seen") — only emit interpretation if the value is itself qualitative-normal (most are). Defer to a small heuristic table.
- **Files you may touch:** `lib/extract/pipelines/multipass_fhir.py`, helper module `lib/extract/terminology/interpretation.py`, tests.
- **Smoke test:**
  ```bash
  uv run pytest lib/tests/test_interpretation_post_pass.py -q
  ```
  Test: glucose 115 with range 65-99 → H; glucose 80 with range 65-99 → N; glucose 50 with range 65-99 → L; flag-only `H` (no value) → H; no value + no range → no interpretation.
- **Acceptance:** ≥95% of numeric-with-range Observations get an interpretation; matches Function Health's `isInRange` boolean for the same data.

---

## CODE-T07 · CLINICAL-CATEGORY extension

- **Status:** Queued
- **Kind:** builder
- **Depends on:** CODE-T03 (needs LOINC populated)
- **Goal:** Add a `clinical-category` extension to each Observation: `Metabolic`, `Kidney`, `Liver`, `Blood`, `Immune Regulation`, `Heart`, `Urine`, `Endocrine`, `Lipids`, `Inflammation`, etc. Mirrors Function Health's category field.
- **Approach:** Drive from LOINC code. Build a `loinc_code → clinical_category` mapping (rule table, ~50 categories × LOINC ranges/specific codes). When an Observation has a resolved LOINC, look up the category, attach as extension.
- **Files you may touch:** `lib/extract/terminology/clinical_categories.py` (new), `lib/extract/pipelines/multipass_fhir.py`, tests.
- **Smoke test:** Cover all 58 tests in the Function Health PDF; assert each gets a category that matches Function Health's.

---

## After T07

- Run a fresh bake-off via PDF-LAB-STUDIO (or one-off) on the Function Health PDF + Cedars Health Summary
- Compare F1 + qualitative output to Function Health's parser
- Capture results in `docs/architecture/PIPELINE-LOG.md`
- Update `docs/daily/2026-05-07-ClaudeCode.md` Entry 6 with measured impact

---

## Open questions parked

1. **Should `common-labs.json` replace `showcase-loinc.json` or supersede it?** Lean: replace. Showcase was a 22-code subset; common-labs is its proper successor. Update VERSIONS.md.
2. **Curated table vs full LOINC release on disk?** Lean: curated table for v1 (smaller, faster, version-controlled). Add full release as offline fallback in Phase 3.
3. **For unmatched LOINC codes, do we call out to the NLM API at runtime as a safety net?** Lean: no — adds network dependency to extraction. Prefer to ship a richer curated table.
4. **Should clinical-category extension use a custom URL or piggyback on something existing?** Open. Custom URL is fine for v1 (`https://ehi-atlas.example/fhir/StructureDefinition/clinical-category`); revisit if we adopt a real terminology server.

---

*Created 2026-05-07. Seven builder-sized tasks. Total estimate: ~5 days of focused work, gated on PROMOTE-EXTRACT + UMLS registration for SNOMED.*
