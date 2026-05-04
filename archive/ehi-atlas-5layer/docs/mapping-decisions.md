# Mapping Decisions Log

> Per-source log of the non-obvious mapping choices we made and why. Future contributors (and our future selves) read this when "why does adapter X handle field Y this way?" comes up.

Format: one entry per decision, dated, with rationale. Append-only — don't rewrite history; add a new entry that supersedes if the decision changes.

## Template

```
## [Source] — Decision: <one-line summary>

**Date:** YYYY-MM-DD
**Owner:** main-thread / sub-agent / Blake
**Affected:** <files / Extensions / etc.>

**Decision:** <what we decided>

**Rationale:** <why; refer to source docs, prior art, validation results>

**Alternatives considered:** <what else we looked at>

**Reversibility:** <how hard would it be to change>
```

---

## Initial entries (2026-04-29)

### Architecture-wide — Decision: FHIR R4 as the canonical merge target

**Date:** 2026-04-29
**Owner:** main-thread (architecture pre-build)
**Affected:** all Layer 2 adapters; entire harmonizer

**Decision:** Standardize all sources to FHIR R4 with USCDI / CARIN BB profiles. Do not mint a custom canonical schema.

**Rationale:** The existing patient-journey app already speaks FHIR; standardizing at Layer 2 means downstream code is unchanged. FHIR is the only target with broad vendor support, established profiles, and a mature provenance model. Josh Mandel is a SMART/FHIR co-creator and the EHI Ignite implicit benchmark — the framing reads fluent in his vocabulary.

**Alternatives considered:** OMOP CDM (research-grade but not exchange-grade; requires another translation for the clinician-facing app), custom envelope (Mandel's `providers[]` shape — preserves provenance but doesn't merge).

**Reversibility:** High cost. The entire downstream app + warehouse depends on this choice.

---

### Architecture-wide — Decision: CCDA conversion via subprocess wrapper around Microsoft FHIR-Converter

**Date:** 2026-04-29
**Owner:** Blake (D1 in BUILD-TRACKER)
**Affected:** `ehi_atlas/standardize/ccda_to_fhir.py`, `ehi_atlas/adapters/ccda.py`

**Decision:** Wrap the Microsoft FHIR-Converter CLI as a subprocess. Do not port Liquid templates inline.

**Rationale:** Microsoft's converter has battle-tested templates covering the published CCDA → FHIR mapping IG. Pure-Python alternatives (LinuxForHealth, older libraries) are patchier. Subprocess overhead is negligible for build-time work. Adopting > rebuilding.

**Alternatives considered:** Pure-Python port (rejected: ongoing maintenance burden), pyfhir-converter packages (rejected: less battle-tested, smaller community).

**Reversibility:** Medium. The subprocess interface is small; replacing it is a single-file change.

---

### Architecture-wide — Decision: Showcase patient is fully synthetic

**Date:** 2026-04-29
**Owner:** Blake (D3 in BUILD-TRACKER)
**Affected:** all `corpus/_sources/*` for the showcase; `tests/fixtures/`

**Decision:** Use one Synthea ground-truth patient projected into the other source shapes (Epic EHI TSV, CMS BB claims, CCDA, lab PDF). Real Blake / Devon data stays as a "real connector proof-of-life" sidebar in the live demo, not the harmonization showcase.

**Rationale:** Real Blake doesn't have public Epic EHI export or Medicare claims. Stitching real FHIR to synthetic claims about a different person creates a fake merge. The showcase patient must logically be the same person across sources for the merge to be honest.

**Alternatives considered:** Hybrid (real-Blake FHIR + synthetic other) — rejected as misleading.

**Reversibility:** Medium. Switching showcase patient would require regenerating all _sources/synthesized-* outputs.

---

### Provenance — Decision: Custom Extension URLs at `https://ehi-atlas.example/fhir/StructureDefinition/`

**Date:** 2026-04-29
**Owner:** main-thread
**Affected:** `ehi_atlas/harmonize/provenance.py`, `docs/PROVENANCE-SPEC.md`

**Decision:** Use placeholder domain `ehi-atlas.example` for Extension URLs in Phase 1; migrate to canonical domain post-Phase-1 with the standard FHIR overlap-period pattern.

**Rationale:** No canonical domain chosen yet; brand name still working title. Stable URLs matter for app code that references them by constant. Migration pattern is well-trodden.

**Alternatives considered:** Picking a domain now (rejected: brand decision still open).

**Reversibility:** Low cost. Migration plan documented in PROVENANCE-SPEC §"Future-stable URLs."

---

### Provenance — Decision: Provenance graph in separate ndjson, not inside the bundle

**Date:** 2026-04-29
**Owner:** main-thread
**Affected:** `corpus/gold/patients/<patient>/provenance.ndjson`, app loader integration

**Decision:** Provenance resources live in `provenance.ndjson` (line-delimited JSON), not embedded in `bundle.json`.

**Rationale:** Lets the app load patient data fast and walk Provenance only when the user clicks "show source." Provenance graphs can be 5-10x the size of the resources they describe; eager loading hurts UX.

**Alternatives considered:** Inline in bundle (rejected: performance), separate Bundle of Provenance resources (rejected: no streaming benefit over ndjson).

**Reversibility:** Low. App loader is the only consumer; one-line change to swap.

---

### Synthea — Decision: Showcase patient is Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61

**Date:** 2026-04-29
**Owner:** sub:haiku (task 1.2), confirmed main-thread
**Affected:** all _sources/* synthesized projections; tests/fixtures; demo scripts

**Decision:** Use Synthea patient `Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61` as the showcase ground-truth patient.

**Rationale:** Highest observation density of evaluated candidates (1,895 obs across 59 encounters, 77 medications, 137 procedures, 131 diagnostic reports). Active conditions include **lung cancer (non-small cell, TNM stage 1)**, COPD, hyperlipidemia, prediabetes, anemia. Active meds include simvastatin (relevant for Artifact 3 — claims-side statin fill) and a fluticasone/salmeterol inhaler. This profile supports a pre-op surgical-risk briefing scenario for lung cancer resection — clinically vivid and rubric-aligned (Interpretability scores well on a high-stakes scenario).

**Clinical-consistency note:** Several pre-engineered artifacts can be tightened to fit this profile:
- **Artifact 4 (planted free-text fact):** chest tightness on exertion is clinically consistent with both COPD and lung cancer — keep this fact, refine wording to fit a real clinical note's voice
- **Artifact 5 (synthesized lab PDF):** creatinine 1.4 mg/dL is plausible for an older patient on simvastatin with cancer
- **Artifact 2 (atorvastatin conflict):** patient is on simvastatin in Synthea; the Epic-EHI-projected version can show *atorvastatin* (a common Epic-side switch from simvastatin), creating both a plausible cross-source story and the conflict we need

**Alternatives considered:** Two runner-ups documented in `_sources/synthea/CHOSEN.md`. None had as much observation density.

**Reversibility:** Medium. Switching showcase patient requires regenerating all _sources/synthesized-* outputs (lab PDF, Epic EHI projection, BB claims).

---

### Synthea — Decision: Synthesize attachments rather than require them in the source patient

**Date:** 2026-04-29
**Owner:** main-thread
**Affected:** task 1.10 (planted free-text fact), bronze staging logic

**Decision:** The chosen showcase patient has 0 attachments. We synthesize:
1. A `DocumentReference` resource + `Binary` resource for Artifact 4 (planted free-text clinical note containing the chest-tightness fact)
2. The synthesized lab PDF from task 1.9 also yields a `DocumentReference` + `Binary` pair for Artifact 5

Both synthesized resources are added to the bronze tier alongside the original Synthea Bundle, with `Resource.meta.source` pointing at "constructed://" URIs and a clear note in the manifest that they are demo artifacts.

**Rationale:** Synthea patients with both rich observation data AND multiple clinical-note attachments are scarce. Adding constructed attachments is the same operation as modifying existing ones for demo purposes — both are deliberate constructions. Honesty principle from EXEC-PLAN: "these artifacts are pre-engineered to demonstrate canonical real-world cases."

**Alternatives considered:** Pick a lower-quality patient who has attachments (rejected: would weaken the harmonization demo by reducing observation overlap signals).

**Reversibility:** High. The constructed resources are clearly tagged; removing them is a manifest update.

---

### Epic EHI — Decision: LOINC codes resolved via LNC_DB_MAIN join, not direct column

**Date:** 2026-04-29
**Owner:** sub:sonnet (task 1.6 finding), confirmed main-thread
**Affected:** task 2.3 (Epic EHI adapter), Layer 2 ORDER_RESULTS → FHIR Observation mapping

**Decision:** When mapping `ORDER_RESULTS` rows to FHIR Observations, resolve LOINC codes by joining through `LNC_DB_MAIN` rather than reading `ORDER_RESULTS.COMPON_LNC_ID` directly.

**Rationale:** Inspection of Josh's Epic EHI fixture (`/corpus/_sources/josh-epic-ehi/INSPECTION.md`) revealed that `ORDER_RESULTS.COMPON_LNC_ID` is all-null in the published export. The LOINC code mapping lives in `LNC_DB_MAIN` and must be joined by the lab component identifier. Without this join, Layer 2 would emit Observations without LOINC codes — unusable for downstream Layer 3 LOINC-based dedup (Artifact 5 merge would fail).

**Scope:** Cause is unclear — could be a redaction artifact, an export-config choice on Josh's part, or a quirk of his specific Cedars-Sinai-flavored Epic deployment. Either way, the adapter must handle the case where LOINC is null on ORDER_RESULTS and fall back to the LNC_DB_MAIN lookup.

**Reversibility:** Easy. The adapter abstracts the join; if a future Epic export *does* populate `COMPON_LNC_ID` directly, we use it preferentially and skip the join.

---

### Epic EHI — Decision: Josh's published export is single-patient (his own); we use schema only

**Date:** 2026-04-29
**Owner:** sub:sonnet (task 1.6 finding), confirmed main-thread
**Affected:** task 2.3, all Epic EHI tier outputs

**Decision:** The published `db.sqlite.dump` is Josh Mandel's own redacted record (one patient, 2018-2024, 111 encounters). We use it to validate parser shape and to lift his merge heuristics — we do NOT use his patient identity, conditions, or content as the showcase patient. The synthesized projection of Rhett759 into Epic-EHI shape is the demo patient.

**Rationale:** Josh published this intentionally; the redaction is incomplete (ZIP and SSN redacted; name, phone, email, DOB, MRN present verbatim). Mixing his published identity into our public showcase would be inappropriate even though the data is technically published. The synthesized Rhett759 projection isolates our demo from Josh's personal data while still using his pipeline.

**Reversibility:** N/A — this is a respect-for-Josh's-data principle, not a technical choice.

---

### Source C (claims) — Decision: Synthea-payer split for Phase 1

**Date:** 2026-04-29
**Owner:** main-thread (D10 in BUILD-TRACKER, decided under Blake's autonomy grant)
**Affected:** task 2.2; corpus layout; showcase patient demo Artifact 3

**Decision:** Source C (the "claims" source) for Phase 1 is implemented by splitting Synthea-generated `Claim`, `ExplanationOfBenefit`, and `Coverage` resources OUT of Rhett759's clinical Bundle into a logically distinct `synthea-payer` source. The CMS Blue Button 2.0 sandbox adapter is deferred to Phase 2 (when Blake registers the sandbox app, or replaced if Phase 2 chooses a different claims source).

**Rationale:** Three reasons:
1. **Honesty.** Synthea simulates a complete healthcare system *end-to-end* — including payer behavior. The Claim/EoB/Coverage resources are genuinely modeled as a payer's view of the same simulated patient. Splitting them at ingest time is a transparent reframe, not a fabrication. We document the split explicitly in the showcase narrative.
2. **Coverage.** Rhett759 has **136 Claim + 59 ExplanationOfBenefit + small Coverage** resources — sufficient density to support Artifact 3 (the orphan: a claim-side fact missing from the clinical record).
3. **Unblocking.** The originally planned BB sandbox adapter is blocked on Blake's app registration (deferred per 2026-04-29). Waiting would compress Stage 3 work; the synthea-payer split unblocks the full 5-source harmonization pipeline immediately.

**Architectural shape:** A new adapter `synthea_payer.py` reads the same Rhett759 Synthea Bundle in `_sources/synthea/raw/` but filters to only Claim/EoB/Coverage resources, writing to `bronze/synthea-payer/rhett759/`. The clinical `synthea` adapter filters those resources OUT. Both sources share a raw input but produce distinct bronze records — clean separation downstream.

**Reversibility:** High. If Blake later registers the BB sandbox, we can add a real `blue_button.py` adapter alongside `synthea_payer.py`. The harmonizer would treat them as additional sources without changes to other layers. The narrative would then say "we demonstrated harmonization with Synthea's payer simulation in Phase 1; Phase 2 adds real synthetic Medicare claims."

---

### Crosswalk — Phase 2 follow-up: add `class_label` to per-drug entries

**Date:** 2026-04-29
**Owner:** main-thread (noted from 3.6 sub-agent)
**Affected:** `corpus/reference/handcrafted-crosswalk/showcase.json`, `ehi_atlas/harmonize/medication.py`

**Decision (deferred):** For Phase 1, `medication.py` uses a hardcoded `_RXCUI_CLASS_LABEL` dict mapping `{"36567": "statin", "83367": "statin"}`. Phase 2 should add a `class_label` field directly to the simvastatin and atorvastatin entries in the crosswalk, then have `medication.py` read from there at runtime so it's fully data-driven.

**Rationale:** Phase 1 needs 2 entries; the dict is fine. Phase 2 will scale to dozens or hundreds of medications across many therapeutic classes — the data should live in the crosswalk, not in code.

**Reversibility:** Trivial. ~10 lines of code change in `medication.py` once the crosswalk has the field.

---

(Append new decisions below.)
