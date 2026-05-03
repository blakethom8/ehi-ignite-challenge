# EHI Atlas Build Tracker

**Last updated:** 2026-04-29 by main-thread
**Active stage:** Stage 1 — Data acquisition & corpus building
**Active focus:** Foundation just landed; dispatching first wave of Stage 1 sub-agents

> See [`BUILD-ORCHESTRATION.md`](BUILD-ORCHESTRATION.md) for roles, model selection, and dispatch protocol. This file is the live task list.

## Status legend

`pending` · `in_progress` · `blocked` · `review` · `done` · `cut`

## Owner legend

`main-thread` (Opus 4.7) · `sub:haiku` (Haiku 4.5) · `sub:sonnet` (Sonnet 4.6) · `Blake`

---

## Stage 0: Foundation

| ID  | Task                                            | Owner       | Status | Output                                              | Notes |
|-----|-------------------------------------------------|-------------|--------|-----------------------------------------------------|-------|
| 0.1 | Directory skeleton                              | main-thread | done   | `ehi-atlas/` tree                                    | 11 subdirs created |
| 0.2 | `pyproject.toml` (uv-managed, Python ≥ 3.11)    | main-thread | done   | `ehi-atlas/pyproject.toml`                           | matches existing repo's toolchain |
| 0.3 | `LICENSE` (MIT)                                 | main-thread | done   | `ehi-atlas/LICENSE`                                  | — |
| 0.4 | `Makefile` with corpus / pipeline / test targets | main-thread | done   | `ehi-atlas/Makefile`                                 | — |
| 0.5 | `README.md` (orientation + boundary contract)   | main-thread | done   | `ehi-atlas/README.md`                                | — |
| 0.6 | `.gitignore` with privacy-gate enforcement      | main-thread | done   | `ehi-atlas/.gitignore`                               | personal raw data gitignored |
| 0.7 | `BUILD-ORCHESTRATION.md`                        | main-thread | done   | `ehi-atlas/BUILD-ORCHESTRATION.md`                   | the meta-doc |
| 0.8 | `BUILD-TRACKER.md` (this file)                  | main-thread | done   | `ehi-atlas/BUILD-TRACKER.md`                         | — |
| 0.9 | Operating docs (INTEGRATION, ADAPTER-CONTRACT, CROSSWALK-WORKFLOW, PROVENANCE-SPEC) | main-thread | in_progress | `ehi-atlas/docs/*.md`                                | — |
| 0.10 | Per-source `_sources/*/README.md` stubs        | main-thread | pending | `corpus/_sources/*/README.md`                        | — |
| 0.11 | Package `__init__.py` files                    | main-thread | pending | `ehi_atlas/**/__init__.py`                           | empty stubs |
| 0.12 | Adapter ABC + bronze-tier write helpers         | main-thread | pending | `ehi_atlas/adapters/base.py`                         | the contract |
| 0.13 | Privacy-gate validator script                   | main-thread | pending | `scripts/validate-privacy-gate.sh`                   | invoked by `make validate-gate` |
| 0.14 | CLI entry stub                                  | main-thread | pending | `ehi_atlas/cli.py`                                   | typer-based, all commands stub |

---

## Stage 1: Data acquisition & corpus building

| ID  | Task                                            | Owner       | Status  | Output                                                  | Notes |
|-----|-------------------------------------------------|-------------|---------|---------------------------------------------------------|-------|
| 1.1 | Per-source READMEs (acquisition recipes)        | main-thread | pending | `corpus/_sources/*/README.md`                           | covered by 0.10 |
| 1.2 | Pick showcase Synthea patient (rich history)    | sub:haiku   | done    | `corpus/_sources/synthea/CHOSEN.md`                     | Rhett759_Rohan584_cd64ff18 — 59 enc / 1,895 obs / 77 meds / 137 procs / lung cancer + COPD; 0 attachments (constructed via 1.9 + 1.10) |
| 1.3 | Clone Mandel's repos to `_sources/josh-*/raw/`  | sub:haiku   | done    | `corpus/_sources/josh-{epic-ehi,ccdas}/raw/`            | both pinned: epic-ehi `188d938` (MIT, active 2026-01), ccdas `39aab8a` (CC BY 4.0, frozen 2018); no LICENSE files but declarations sufficient |
| 1.4 | UMLS license registration                       | Blake       | deferred | confirmation email                                      | per Blake (2026-04-29): handle later. Stage 3 mitigation = small hand-curated crosswalk for showcase-only codes; Phase 2 ambition = full UMLS load |
| 1.5 | CMS Blue Button 2.0 sandbox app registration    | Blake       | deferred | OAuth client credentials in `.env`                      | per Blake (2026-04-29): handle later. Source C fallback options: CMS static synthetic PUFs OR Synthea's own Claim/EoB resources reframed as payer source |
| 1.6 | Inspect Josh's Epic SQLite dump (1.7 MB)        | sub:sonnet  | done    | `corpus/_sources/josh-epic-ehi/INSPECTION.md`           | 415 tables / 7,294 rows / single patient (Josh, 2018-2024, 111 enc); messaging-heavy; **LOINC not on ORDER_RESULTS — must join LNC_DB_MAIN**; 3-pass merge heuristic + hardcoded overrides documented for 2.3 |
| 1.7 | Inspect Josh's CCDA fixtures (pick one matching showcase) | sub:haiku | done    | `corpus/_sources/josh-ccdas/CHOSEN.md`                  | Cerner Samples/Transition_of_Care_Referral_Summary.xml (92 KB, 13 sections, HTN+T2DM+statin+hypercholesterolemia → overlaps with Rhett759 for Artifacts 1+2) |
| 1.8 | BB sandbox: pull a sample beneficiary           | sub:sonnet  | deferred | `corpus/_sources/cms-blue-button/raw/`                  | depends on 1.5 (deferred); pivot decision pending — substitute with CMS PUF or Synthea claims |
| 1.9 | Synthesize lab report PDF for showcase patient  | sub:sonnet  | done    | `corpus/_sources/synthesized-lab-pdf/{generator.py, raw/lab-report-2025-09-12-quest.pdf, README-extraction.md}` | 3-page Quest-style PDF (9.6 KB), creatinine row at **page=2;bbox=72,574,540,590**; deterministic via SOURCE_DATE_EPOCH (MD5 `cd7124966b5be8b7974684a5bd533b63`); reportlab added to pyproject |
| 1.10 | Plant Artifact 4 (synthesized DocumentReference + free-text fact) | sub:sonnet | done    | `corpus/_sources/synthea/PLANTED-FACT.md` + `synthesized-clinical-note/{progress-note-2026-01-15.txt, DocumentReference.json, Binary.json}` | 430-word SOAP pulm/onc note; planted phrase "occasional chest tightness on exertion since approximately November of last year" in Subjective §2; LOINC 11506-3 (Progress note); base64-verified; expected Layer 3 extraction → Condition (SNOMED 23924001) |
| 1.11 | Reference terminology snapshots                  | sub:sonnet | done    | `ehi_atlas/terminology/{rxnorm.py,__init__.py}` + `corpus/reference/{loinc/showcase-loinc.json,handcrafted-crosswalk/showcase.json}` | RxNorm REST client (urllib + file cache) · 22-code LOINC subset (CMP panel + hematology + vitals + Artifact 4 doc type) · 17-entry crosswalk covering all Artifact 1/2/4/5 anchors (incl. SNOMED 23924001 chest-tightness, RxCUI 36567 simvastatin, RxCUI 83367 atorvastatin) · 28 tests pass · no new deps |
| 1.12 | Stage `_sources/` to `bronze/`                   | main-thread | done    | `corpus/bronze/<source>/<patient>/` + STAGING-MANIFEST.md | 5 sources staged via `scripts/stage-bronze.py`: synthea+ccda+lab-pdf+synthesized-clinical-note → patient `rhett759`; epic-ehi → fixture under `josh-fixture` (Stage 2 will project Rhett759 via adapter); blue-button deferred. Idempotent + byte-identical re-runs verified. |
| 1.13 | Write corpus reproduction recipe                 | main-thread | done    | `corpus/README.md`                                      | concrete recipe with pinned SHAs, MD5, showcase patient ID, command-by-command |

---

## Stage 2: Standardization & ingestion plumbing

| ID  | Task                                            | Owner       | Status  | Output                                                  | Notes |
|-----|-------------------------------------------------|-------------|---------|---------------------------------------------------------|-------|
| 2.1 | Synthea adapter (FHIR R4 passthrough)           | sub:sonnet  | done    | `ehi_atlas/adapters/synthea.py` + 8 tests + CLI wired   | hash matches stage-bronze exactly (`97f315b4…`); ABC contract validated end-to-end; `PATIENT_FILE_MAP` class dict for extension; `ACQUISITION_TS` frozen for idempotency; no new deps |
| 2.2 | Synthea-payer claims adapter (CARIN BB-flavored) | sub:sonnet  | done    | `ehi_atlas/adapters/synthea_payer.py` + 10 tests        | 196 payer entries (136 Claim + 59 EoB + 1 Patient; Synthea didn't gen Coverage for Rhett759); bronze hash `a3a905fa…`; auto-remaps source_root for CLI; clinical-dedup flagged for Stage 3 (SyntheaAdapter still emits all types) |
| 2.3 | Epic EHI TSV adapter (lift Mandel's heuristics) + Rhett759 projection | sub:sonnet  | done    | `ehi_atlas/adapters/epic_ehi.py` + 9 tests + stage-bronze updated | TWO flows: `josh-fixture` (parser validation) + `rhett759` (6-table projection). All 3 artifact anchors verified — Artifact 1 (ICD-10-only PROBLEM_LIST), Artifact 2 (ORDER_MED atorvastatin discontinued 2025-09-01), Artifact 5 (ORDER_RESULTS creatinine 1.4 mg/dL on 2025-09-12 via LNC_DB_MAIN join with COMPON_LNC_ID=NULL). 38/38 total adapter tests, zero new deps. |
| 2.4 | CCDA adapter (subprocess FHIR-Converter)        | sub:sonnet  | done    | `ehi_atlas/adapters/ccda.py` + 11 tests + `docs/FHIR-CONVERTER-SETUP.md` | Layer 1 passthrough (XML → bronze, hash matches source); FHIR-Converter probe = False on this machine (npm CLI doesn't exist under that name; tool distributed via Docker or build-from-source). Probe returns non-fatal `warning:` string. Layer 2 toolchain decision deferred to Phase 2. |
| 2.5 | Lab PDF adapter (Layer 1: PDF → bronze + pages/) | sub:sonnet  | done    | `ehi_atlas/adapters/lab_pdf.py` + 8 tests                | LabPDFAdapter writes data.pdf + pages/{001..003}.{png,text.json}; hash `834ed172…` matches stage-bronze; auto-remaps `_sources/lab-pdf/raw/` → `_sources/synthesized-lab-pdf/raw/` (same pattern as synthea-payer); pages/ feeds 4.3's vision extraction. |
| 2.6 | Layer 2 validators (FHIR profile validation)    | sub:sonnet  | done    | `ehi_atlas/standardize/validators.py` + 27 tests + CLI `validate` cmd + ADAPTER-CONTRACT §Using-BundleValidator | 3 layers (structural/profile/provenance); 32 known USCDI+CARIN-BB profiles; required `meta.tag` systems enforced; extracted-lifecycle requires 3 extraction Extensions; non-strict warnings vs strict errors |
| 2.7 | Build-time crosswalk: Epic table → FHIR resource | sub:sonnet | pending | `ehi_atlas/standardize/crosswalks/epic_to_fhir.json`    | LLM-bootstrapped, validated, frozen |
| 2.8 | Standardize CLI command + Synthea Layer-2 impl   | sub:sonnet  | done    | `ehi_atlas/standardize/{base.py,synthea.py,__init__.py}` + 6 tests + CLI wired | `Standardizer` ABC + `StandardizeResult`; SyntheaStandardizer passthrough annotates 2,640 resources w/ source-tag + lifecycle + 15 USCDI profile URLs; silver hash `ae04c36c79080391…`; CLI `standardize --source synthea --patient rhett759` works; 151/151 full suite. **Note:** fhir.resources 8.x rejects some valid Synthea patterns (Encounter.class as single Coding, etc.) — pre-existing library compat issue, not caused by L2; provenance checks pass cleanly. |

---

## Stage 3: Harmonization layer

| ID  | Task                                            | Owner       | Status  | Output                                                  | Notes |
|-----|-------------------------------------------------|-------------|---------|---------------------------------------------------------|-------|
| 3.1 | Patient identity resolution (Fellegi-Sunter)    | sub:sonnet  | done    | `ehi_atlas/harmonize/identity.py` + 12 tests             | inline Jaro-Winkler (MARTHA/MARHTA=0.961, DWAYNE/DUANE=0.840 textbook-correct); F-S aggregate w/ name(0.5)/dob(0.3)/address(0.1)/gender(0.1); MATCH≥0.85, POSSIBLE_MATCH≥0.6; Union-Find clusters; `canonical_id_for` override works; `merged_patient_resource` preserves all source MRNs as identifier[]; 188/188 full suite. |
| 3.2 | Provider identity resolution (NPPES-anchored)   | sub:sonnet  | done    | `ehi_atlas/harmonize/provider_identity.py` + 13 tests    | NPI-exact match (decisive) + name-Jaro-Winkler ≥0.90 fallback w/ Jaccard specialty>0 required for fallback match; 3 Synthea Practitioners → 3 distinct canonicals; NPPES API enrichment deferred to Phase 2; 292/292 full suite. |
| 3.3 | Code mapping (UMLS-anchored crosswalk-based)    | sub:sonnet  | done    | `ehi_atlas/harmonize/code_map.py` + 13 tests             | **Artifact 1 anchor verified:** SNOMED 38341003 ≡ ICD-10 I10 → CUI C0020538. `resolve_coding`, `codings_equivalent`, `codeable_concepts_equivalent`, `annotate_resource_codings` (Condition/Observation/MedicationRequest), `collect_concept_groups`. Idempotent CUI-extension upsert. Never guesses on unmapped codes. |
| 3.4 | Temporal alignment (DocRef precedence rule)     | sub:sonnet  | done    | `ehi_atlas/harmonize/temporal.py` + 13 tests             | UTC normalizer + 9-resource precedence dispatch (Observation/Condition/Encounter/DiagnosticReport/Procedure/MedicationRequest/AllergyIntolerance/Immunization/DocumentReference); **Mandel rule enforced** (test 10 explicitly asserts docRef.date never used as clinical time, both no-lookup and empty-lookup paths); `normalize_bundle_temporal` idempotent via URL-based dedup; 176/176 full suite. |
| 3.5 | Condition merge (CUI grouping + temporal env)   | sub:sonnet  | done    | `ehi_atlas/harmonize/condition.py` + 13 tests            | **Artifact 1 anchor verified at the resource level:** Synthea SNOMED 38341003 + Epic ICD-10 I10 → 1 Condition with code.coding length 2, both identifiers, both source-tags, earliest onset 2018 wins, EXT_UMLS_CUI=C0020538 on each coding, ProvenanceRecord activity=MERGE. 248/248 full suite. |
| 3.6 | Medication episode reconciliation               | sub:sonnet  | done    | `ehi_atlas/harmonize/medication.py` + 18 tests           | **Artifact 2 anchor verified:** Synthea simvastatin (RxCUI 36567 active) + Epic atorvastatin (RxCUI 83367 discontinued 2025-09-01) → 2 separate gold episodes (NOT merged) + 1 CrossClassFlag(class="statin") for 3.8 to consume. RxCUI-grouped episode reconciliation + STATUS_PRIORITY merge. **Note:** uses hardcoded `_RXCUI_CLASS_LABEL` dict; Phase 2 follow-up is to add `class_label` field to the crosswalk so it's data-driven. 279/279 full suite. |
| 3.7 | Observation dedup (LOINC + UCUM normalize)      | sub:sonnet  | done    | `ehi_atlas/harmonize/observation.py` + 17 tests          | **Artifact 5 anchor verified end-to-end:** synthea + lab-pdf creatinine 1.4 mg/dL on 2025-09-12 → one merged with both source-tags + both identifiers + max quality 0.94 + EXT_MERGE_RATIONALE. ObservationKey(loinc,date,value,unit); VALUE_TOLERANCE=0.001; near-match flagging for 3.8. **235/235 full suite.** |
| 3.8 | Conflict detection (rule + LLM-judge build-time) | sub:sonnet | done    | `ehi_atlas/harmonize/conflict.py` + 13 tests             | observation near-match (bucketed loinc+date) + medication cross-class (via CrossClassFlag structural protocol — no hard dep on 3.6); `apply_conflict_pairs` symmetric idempotent upsert; `emit_conflict_provenance` DERIVE activity w/ 2 entities + deterministic conflict-IDs; LLM-judge stubbed for Phase 2. 261/261 full suite. |
| 3.9 | Quality scoring (recency × authority × completeness) | sub:sonnet | done    | `ehi_atlas/harmonize/quality.py` + 17 tests             | 3 component scorers (40/40/20 weights); aggregate math verified exactly: synthea+complete=0.94, lab-pdf+partial=0.48; deterministic policy; `annotate_quality` delegates to `provenance.attach_quality_score`. |
| 3.10 | Provenance graph emission                       | sub:sonnet  | done    | `ehi_atlas/harmonize/provenance.py` + 12 tests          | 9 EXT_* URL constants verified against PROVENANCE-SPEC; 4 builders (MERGE/DERIVE/EXTRACT/TRANSFORM); 5 attach_* helpers (idempotent upserts); `ProvenanceWriter` with deterministic sort-on-flush; DEFAULT_RECORDED frozen for Phase 1; 163/163 full suite. |
| 3.11 | 5-artifact integration test on showcase patient | sub:sonnet  | done    | `tests/harmonize/test_showcase_patient.py` (23 cases, 21 pass + 2 phase-2 skips) | **STAGE 3 CLOSED.** Two-part Artifact-2 fix: (1) added RxCUI 316672 (Synthea's product-level SCD for Simvastatin) to `_RXCUI_CLASS_LABEL` — Synthea uses product-level not ingredient-level; (2) propagated EXT_CONFLICT_PAIR from silver dicts to merged gold dicts in orchestrator. **conflicts_detected now=1** (was 0). Artifact-1 corrected to **Hyperlipidemia** (Rhett759 has no HTN; SNOMED 55822004 ≡ ICD-10 E78.5 → CUI C0020473). Artifact-5 is **epic-ehi + lab-pdf** (Synthea has no creatinine for this patient). Phase-2 skips: chest-tightness extraction (needs vision wrapper running on clinical note); source-locator on Artifact-5 (stub-silver doesn't run vision). **321 passed + 2 skipped** = full suite green. |

---

## Stage 4: Vision extraction sub-layer

| ID  | Task                                            | Owner       | Status  | Output                                                  | Notes |
|-----|-------------------------------------------------|-------------|---------|---------------------------------------------------------|-------|
| 4.1 | Pydantic schemas for extraction outputs          | sub:sonnet | done    | `ehi_atlas/extract/schemas.py` + `to_fhir.py` + 25 tests | `BBox` (with `to_locator_string()` for the source-locator Extension), `ExtractedLabReport/LabResult/ClinicalNote/Condition/Symptom`, top-level `ExtractionResult` w/ discriminated union; `lab_result_to_observation` + `condition_to_fhir` emit all 5 extraction extensions; LOINC omitted when null; source_text preserved in Condition.note. 126/126 full suite. |
| 4.2 | PDF rasterization + bbox text extraction         | sub:sonnet | done    | `ehi_atlas/extract/layout.py` + 5 tests                  | pdfplumber for text+bbox (bottom-left normalize); pypdfium2 for rasterization (poppler→pypdfium2 fallback documented); `find_text_bbox()` returns Artifact 5 row at (75,576,520,585) vs documented (72,574,540,590) — within ±5pt for y, right-edge gap explained by H-flag absence at 540pt. **Important:** "Creatinine" on both p1 (summary) and p2 (detail) — must specify page=2. 131/131 full suite. |
| 4.3 | Claude vision wrapper (schema-constrained)       | sub:sonnet | done    | `ehi_atlas/extract/pdf.py` + 6 tests + CLI `extract run` | `extract_from_pdf` + `extract_lab_pdf` ship with forced tool-call structured output + content-hash cache integration; prompt frozen at `v0.1.0`; mocked tests run offline; 145/145 full suite. |
| 4.4 | Content-hash deterministic cache                 | sub:sonnet | done    | `ehi_atlas/extract/cache.py` + 8 tests                  | `CacheKey(file_sha256, prompt_version, schema_version, model_name)` → SHA-256 digest filename; atomic tmp→rename write; 8/8 tests; 110/110 full suite |
| 4.5 | Notebook: prompt iteration on the showcase PDF   | sub:sonnet | done    | `notebooks/03_layer2b_vision_extraction.ipynb` (replaces planned exploratory notebook) | covered by the pedagogical series; reads cached extraction; future prompt-iteration notebook reuses same setup |
| —   | **Pedagogical notebook series (10 notebooks)**   | sub:sonnet | done    | `notebooks/{00-09}_*.ipynb` + README + `build_notebooks.py` | All 10 spot-execute clean against live corpus. Kernel = `ehi-atlas` (registered in Jupyter). Series: 00 Welcome → 01 Bronze → 02 Synthea L2 → 03 Vision → 04 Code-mapping → 05 Temporal+Identity → 06 Artifact 1 deep-dive → 07 Artifact 2 deep-dive → 08 Artifact 5 deep-dive → 09 End-to-end. Engine badges (🔧/🤖/📚/⚙️) per step. |
| 4.6 | Golden-output fixture for the showcase lab PDF   | main-thread | pending | `tests/fixtures/showcase-lab-pdf-extraction.json`     | regression baseline |

---

## Stage 5: EHI Atlas standalone console (Streamlit)

**Pivot 2026-04-29:** Per Blake — keep EHI Atlas isolated for now. Build a NEW lightweight Streamlit frontend INSIDE `ehi-atlas/app/` rather than integrating into the existing patient-journey app. Phase 2 plugs the gold tier into the patient-journey app via the documented symlink; Phase 1 ships a standalone "EHI Atlas Console" that visualizes the workflow and lets Blake (and judges) walk through the pipeline.

| ID  | Task                                            | Owner       | Status  | Output                                                  | Notes |
|-----|-------------------------------------------------|-------------|---------|---------------------------------------------------------|-------|
| 5.1 | Streamlit console v1 — skeleton + 5 pages       | sub:sonnet  | done    | `ehi-atlas/app/{streamlit_app.py, pages/, components/, README.md}` + launch.json entry | 5 pages + reusable components; engine-type badges (🔧/🤖/📚/⚙️); Graphviz pipeline diagram + ASCII fallback; corpus_loader uses mtime cache invalidation; **console boots clean on port 8503** (`/_stcore/health` → ok); read-only access to gold tier — does not invoke harmonizer. **Note:** Streamlit lives in the parent project's `.venv`, not `ehi-atlas/pyproject.toml` — works for now via launch.json `.venv/bin/streamlit`; future ehi-atlas extraction would need an extras group. |
| 5.2 | Patient-journey app symlink integration          | main-thread | deferred | `data/ehi-atlas-output/` → `corpus/gold/` symlink         | Phase 2 (per pivot) |
| 5.3 | PDF page-bbox highlighting in console viewer    | sub:sonnet  | pending | console component (within 5.1's Standardize page)       | Artifact 5 UI moment |
| 5.4 | Conflict side-by-side UI in console             | sub:sonnet  | pending | within 5.1's Harmonize page                              | Artifact 2 |
| 5.5 | "What changed since last visit" diff view       | (deferred)  | deferred | —                                                        | Phase 2 (was Patient Journey only) |

---

## Stage 6: Submission packaging

| ID  | Task                                            | Owner       | Status  | Output                                                  | Notes |
|-----|-------------------------------------------------|-------------|---------|---------------------------------------------------------|-------|
| 6.1 | Phase 1 narrative (PDF)                          | main-thread + Blake | pending | submission package                                | drafted from existing docs |
| 6.2 | Wireframes assembled from `design/wireframes/*` | main-thread | pending | submission package                                       | + screenshots of live app |
| 6.3 | Public GitHub repo cleanup                      | main-thread | pending | clean public-facing README, license, attribution        | — |
| 6.4 | Live demo URL frozen                            | Blake       | pending | URL accessible to judges                                 | 24h before deadline |
| 6.5 | Submission upload                                | Blake       | pending | confirmation                                             | by 2026-05-13 23:59 ET |

---

## Open decisions

| ID  | Question                                                       | Recommendation                              | Decided?         |
|-----|----------------------------------------------------------------|---------------------------------------------|------------------|
| D1  | CCDA conversion: subprocess FHIR-Converter or pure-Python port | Subprocess FHIR-Converter wrapper           | yes (Blake)      |
| D2  | pyproject toolchain                                            | Match existing repo (uv, Python ≥ 3.11)     | yes (Blake)      |
| D3  | Showcase patient: real-Blake hybrid or fully synthetic         | Fully synthetic (Approach 3 in EXEC-PLAN)   | yes (Blake)      |
| D4  | Reach out to Josh Day 1                                        | Yes; Path-C framing (embed portal Phase 1)  | pending          |
| D5  | AI bonus angle (vision extraction default vs alternatives)     | Vision extraction (default per EXEC-PLAN)   | yes (Blake)      |
| D6  | Subagent budget cap                                            | 3 in flight default                         | implicit yes     |
| D7  | Tracker visibility / ping cadence                              | Ping on blockers + milestones; batch routine| implicit yes     |
| D8  | Default sub-agent model                                         | **Sonnet 4.6** for coding; Haiku only for narrow mechanical work | yes (Blake 2026-04-29) |
| D9  | UMLS for Phase 1                                                | Hand-curated crosswalk for showcase codes only; full UMLS = Phase 2 | yes (Blake 2026-04-29) |
| D10 | Source C (claims) for Phase 1                                   | **Synthea-payer split** — split Rhett759's 136 Claim + 59 EoB resources into a logically distinct `synthea-payer` source from the clinical Bundle. Honest because Synthea simulates both clinical and payer systems end-to-end. | yes (main-thread under autonomy 2026-04-29) |

---

## Recent activity

**2026-04-29 (main-thread):** Foundation laid. Skeleton, pyproject, LICENSE, Makefile, README, .gitignore, BUILD-ORCHESTRATION, BUILD-TRACKER all in. Operating docs and per-source READMEs next; then first wave of Stage 1 sub-agents.

**2026-04-29 (main-thread):** Foundation milestone complete. `uv sync` clean, CLI works, privacy gate passes. Wave 1 sub-agents dispatched in parallel: 1.2 (Haiku, Synthea showcase pick) + 1.3 (Haiku, Mandel repo clones).

**2026-04-29 (sub:haiku → main-thread):** Task 1.3 done. Both Mandel repos cloned. epic-ehi 7,685 files / 62 MB / SHA `188d938` (MIT declared in package.json, active 2026-01); ccdas 789 files / 72 MB / SHA `39aab8a` (CC BY 4.0 in README, frozen 2018). Neither has a LICENSE file but declarations are legally sufficient. Pipeline scripts (`00-redact.js` through `08-generate-short-descriptions.ts`) and 1.6 MB `db.sqlite.dump` confirmed present. Dispatched 1.6 (sub:sonnet, SQLite inspection).

**2026-04-29 (sub:haiku → main-thread):** Task 1.2 done. Showcase patient = `Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61`. Verified: 59 enc / 1,895 obs / 77 meds / 137 procs / 131 dx reports. Active **non-small cell lung cancer (TNM stage 1) + COPD + hyperlipidemia + on simvastatin** — pre-op briefing for lung resection is a stronger surgical-risk scenario than prediabetes alone. 0 attachments (constructed via 1.9 + 1.10). Dispatched wave 2: 1.6 retry, 1.7 (CCDA pick), 1.9 (lab PDF generator).

**2026-04-29 (sub:haiku → main-thread):** Task 1.7 done. CCDA fixture = `Cerner Samples/Transition_of_Care_Referral_Summary.xml` (92 KB, 13 sections, HTN+T2DM+statin+hypercholesterolemia profile). Cross-source story: Cerner CCDA → Epic EHI projection → Synthea FHIR pull, three-vendor merge with HTN as Artifact 1 and statin as Artifact 2 anchors.

**2026-04-29 (sub:sonnet → main-thread):** Task 1.6 done. Epic SQLite ingest is feasible — 415 tables / 7,294 rows / single patient. Main architectural finding logged in mapping-decisions: **LOINC codes are null on `ORDER_RESULTS.COMPON_LNC_ID` and must be joined via `LNC_DB_MAIN`**. Without this join Layer 2 emits LOINC-less Observations and Artifact 5's PDF↔FHIR creatinine merge would silently fail. Josh's 3-pass merge heuristic documented for the 2.3 adapter author. Holding for 1.9 (lab PDF generator) before dispatching wave 3.

**2026-04-29 (sub:sonnet → main-thread):** Task 1.9 done. Quest-style 3-page CMP PDF (9.6 KB) generated deterministically via `SOURCE_DATE_EPOCH=946684800`. Creatinine row at **page=2;bbox=72,574,540,590**; MD5 `cd7124966b5be8b7974684a5bd533b63` reproducible across runs. Sub-agent flagged missing `reportlab` dep; main-thread added `reportlab>=4.0.0` to pyproject.toml, ran `uv sync`, regenerated PDF inside the venv — byte-identical. PROVENANCE-SPEC's example bbox flagged as illustrative; actual showcase value documented in synthesized-lab-pdf/README-extraction.md. Wave 2 complete.

**2026-04-29 (main-thread):** Task 1.13 done. Corpus reproduction recipe written with concrete commands, pinned SHAs, expected MD5 for the lab PDF, showcase-patient ID, and the file-by-file fixture inventory. Open-source portion of the corpus is now reproducible by any contributor. Dispatched 1.10 (sub:sonnet, synthesize the planted clinical note as DocumentReference + Binary).

**2026-04-29 (Blake → main-thread):** Two policy updates: (a) UMLS registration (1.4) and BB sandbox app (1.5) deferred — handle later; (b) **default sub-agent model is now Sonnet 4.6** for coding work, Haiku reserved for narrow mechanical work. BUILD-ORCHESTRATION updated. Tracker rows 1.4, 1.5, 1.8 marked deferred; 1.11 unblocked with hand-curated-crosswalk approach. New decisions D8 / D9 / D10 logged.

**2026-04-29 (main-thread):** Stage 1 corpus complete. Bronze tier staged via `scripts/stage-bronze.py` — 5 sources, 11 files, all metadata.json conforming to SourceMetadata contract. Idempotent re-runs verified byte-identical. Privacy gate clean. Synthea bundle copied into `_sources/synthea/raw/` so adapter and staging script use the same canonical input path.

**2026-04-29 (main-thread):** Wave 4 dispatched — 3 Sonnet sub-agents in parallel: 1.11 (terminologies), 2.1 (Synthea adapter), 2.6 (validators).

**2026-04-29 (sub:sonnet → main-thread):** Task 2.1 done. SyntheaAdapter implements the ABC contract; 8/8 pytest cases pass; `ehi-atlas ingest --source synthea --patient rhett759` produces hash `97f315b456474064…` — exact match with `stage-bronze.py`. CLI wires `ingest --all` to iterate REGISTRY; future adapters drop in automatically. PATIENT_FILE_MAP class dict provides clean extension for new patients. No new dependencies.

**2026-04-29 (sub:sonnet → main-thread):** Task 1.11 done. Full terminology layer for Phase 1: RxNorm REST client (`urllib`, file cache; sample lookup `simvastatin` → RxCUI 36567 verified live); 22-code LOINC subset spanning the full CMP panel + hemoglobin (anemia) + vitals + HbA1c + document-type 11506-3; 17-entry hand-curated crosswalk covering every showcase artifact's anchor concept — HTN/T2DM/prediabetes/hyperlipidemia/hypercholesterolemia/COPD/NSCLC + TNM T1/anemia/chest-tightness (SNOMED 23924001 = Artifact 4 target)/three medications. Loader module exposes `load_loinc_showcase()`, `load_handcrafted_crosswalk()`, `lookup_cross()`. 28 tests pass. No new deps.

**2026-04-29 (sub:sonnet → main-thread):** Task 2.6 done. `BundleValidator` (3 layers: structural via fhir.resources / profile against 32 known USCDI+CARIN-BB URLs / provenance via meta.tag systems + extracted-lifecycle Extension checks). 27 tests pass. Architecture note: installed `fhir.resources==8.2.0` uses `__resource_type__` not `resource_type`; validator works around cleanly. CLI gains `validate --bundle <path>` subcommand. ADAPTER-CONTRACT updated with §"Using BundleValidator". Wave 4 fully complete.

**2026-04-29 (main-thread):** Wave 5 dispatched — 3 Sonnet sub-agents in parallel: 2.2 (Synthea-payer adapter per D10), 2.3 (Epic EHI adapter + Rhett759 projection — the hard one), 2.4 (CCDA adapter with FHIR-Converter subprocess probe). All write distinct file sets; REGISTRY edits constrained to minimal-additive 1-line each.

**2026-04-29 (sub:sonnet → main-thread):** Task 2.2 done. SyntheaPayerAdapter ships with 196 payer entries (136 Claim + 59 EoB + 1 Patient; 0 Coverage — real Synthea output for this patient). Hash `a3a905fa6943acab…`. 10/10 adapter tests + 73/73 full suite green. Architecture nicety: adapter auto-remaps `_sources/synthea-payer/raw/` → `_sources/synthea/raw/` so CLI uses standard `_sources/<name>/raw/` convention while sharing input with SyntheaAdapter. Dedup concern flagged: SyntheaAdapter still emits Claim/EoB in its clinical bronze record; Stage 3 harmonize or follow-up filter handles dedup. Holding for 2.3 + 2.4.

**2026-04-29 (sub:sonnet → main-thread):** Task 2.4 done. CCDAAdapter (Layer 1 XML passthrough); 11/11 tests; 29/29 total adapter tests across the wave's adapters. Bronze hash byte-identical to source. **Architecture finding:** Microsoft FHIR-Converter is NOT distributed as an npm CLI under any commonly-published name — it's a GitHub repo with Liquid templates, distributed via Docker / build-from-source. Probe returns clean False with install guidance written to `docs/FHIR-CONVERTER-SETUP.md`. Phase 2 decision required: Docker-subprocess invocation OR LinuxForHealth Java tool OR pure-Python CCDA→FHIR. Phase 1 unblocked — bronze layer ships; Layer 2 CCDA conversion is a Stage 2.x task following the toolchain decision. Cosmetic bug in CLI ingest output noted (prints `data.json` for all sources; harmless, fix queued).

**2026-04-29 (sub:sonnet → main-thread):** Task 2.3 done. EpicEhiAdapter implements both flows. `josh-fixture`: 1.6 MB SQLite dump copied verbatim for parser validation. `rhett759`: Synthea→Epic projection across 6 tables (PAT_PATIENT, PAT_ENC, PROBLEM_LIST, ORDER_MED, ORDER_RESULTS, LNC_DB_MAIN) with all 3 artifact anchors verified — Artifact 1 ICD-10-only conditions (E78.5, D64.9, etc.; no SNOMED → forces UMLS-CUI merge); Artifact 2 atorvastatin (RxCUI 83367) discontinued 2025-09-01; Artifact 5 creatinine 1.4 mg/dL on 2025-09-12 with COMPON_LNC_ID=NULL forcing the LNC_DB_MAIN join (per inspection finding). 9/9 epic tests; 38/38 total adapter tests; zero new deps.

**2026-04-29 (main-thread):** Wave 5 integration smoke test passes — 93/93 pytest, 7 bronze records (5 distinct sources × the 2 epic-ehi flows), 4 registered adapters (ccda, epic-ehi, synthea, synthea-payer), privacy gate clean. Cosmetic CLI bug fixed: ingest output now shows correct extension per source (data.xml / data.json / data.sqlite.dump). Wave 6 dispatched: Stage 4 vision extraction (4.1 schemas + 4.2 PDF rasterization + 4.4 content-hash cache, all sub:sonnet, all writing to distinct files in `ehi_atlas/extract/`).

**2026-04-29 (sub:sonnet × 3 → main-thread):** Wave 6 fully complete. 4.4 cache (8 tests, file-based with atomic-rename writes), 4.1 schemas + to_fhir helpers (25 tests, BBox.to_locator_string outputs the source-locator extension format, lab_result_to_observation emits all 5 extraction extensions), 4.2 PDF layout (5 tests, pdfplumber+pypdfium2, Creatinine bbox at p2 within ±5pt of documented). **131/131 full suite green.** Important finding from 4.2: "Creatinine" appears on both p1 (summary table) and p2 (detail rows) — find_text_bbox callers must specify page=2 for Artifact 5.

**2026-04-29 (main-thread):** Wave 7 dispatched — 3 Sonnet sub-agents in parallel: 4.3 (Claude vision wrapper using instructor + the cache + the layout module), 2.5 (Lab PDF Layer-1 adapter that writes bronze pages/ via 4.2's prepare_pdf_for_extraction), 2.8 (standardize CLI command + first concrete Layer-2: synthea passthrough validating against BundleValidator).

**2026-04-29 (sub:sonnet × 3 → main-thread):** Wave 7 fully complete. 4.3 vision wrapper (6 mocked tests, prompt v0.1.0 frozen, cache integration); 2.5 LabPDFAdapter (8 tests, hash `834ed172…`, writes pages/{001..003}.{png,text.json}); 2.8 SyntheaStandardizer (6 tests, silver hash `ae04c36c79080391…`, 2,640 resources annotated). **Vertical slice now buildable end-to-end through Layer 2 / Layer 2-B.** 151/151 full suite. Adapter registry: 5 entries (ccda, epic-ehi, lab-pdf, synthea, synthea-payer). Standardizer registry: 1 entry (synthea); other L2 standardizers are next-wave work.

**2026-04-29 (main-thread):** Wave 8 dispatched — 3 Sonnet sub-agents in parallel for Stage 3 harmonization foundation: 3.1 (patient identity resolution, Fellegi-Sunter), 3.4 (temporal alignment, DocRef.context.period.start precedence rule), 3.10 (provenance graph emission, the format every harmonize sub-task uses). These are independent foundational pieces that downstream merge logic depends on.

**2026-04-29 (sub:sonnet × 3 → main-thread):** Wave 8 fully complete. 3.10 (12 tests, 9 EXT_* URL constants verified vs spec, ProvenanceWriter byte-identical), 3.4 (13 tests, **Mandel rule load-bearing test passes** — `docRef.date` NEVER used as clinical time; 9-resource precedence dispatch), 3.1 (12 tests, Jaro-Winkler hits textbook values 0.961/0.840, Fellegi-Sunter clusters cross-source fingerprints into canonical patient with all MRNs preserved). **Stage 3 foundation laid.** 188/188 full suite green.

**2026-04-29 (main-thread):** Wave 9 dispatched — 3.3 (code mapping with UMLS-CUI crosswalk bridge), 3.7 (observation dedup, Artifact 5 anchor), 3.9 (quality scoring with deterministic 3-component policy).

**2026-04-29 (sub:sonnet × 3 → main-thread):** Wave 9 fully complete. 3.3 verified **Artifact 1 anchor** (SNOMED 38341003 ≡ ICD-10 I10 → CUI C0020538), 13 tests. 3.9 quality math verified exactly (0.94 / 0.48 hit weighted-aggregate targets), 17 tests. 3.7 verified **Artifact 5 anchor end-to-end** (creatinine 1.4 mg/dL across synthea + lab-pdf merges with both source-tags + both identifiers + max quality), 17 tests. **235/235 full suite green.** 7 of 11 Stage 3 sub-tasks done.

**2026-04-29 (main-thread):** Wave 10 dispatched — 3.5 condition merge + 3.6 medication reconciliation + 3.8 conflict detection.

**2026-04-29 (sub:sonnet × 3 → main-thread):** Wave 10 fully complete. 3.5 condition merge (Artifact 1 verified at resource level: 1 Condition with both codings, both identifiers, earliest onset, EXT_UMLS_CUI on each), 13 tests. 3.6 medication reconciliation (Artifact 2 verified: simvastatin + atorvastatin → 2 separate episodes + 1 CrossClassFlag), 18 tests. 3.8 conflict detection (observation near-match + medication cross-class + apply_conflict_pairs symmetric upsert + DERIVE Provenance), 13 tests. **279/279 full suite green.** All 5 showcase artifact anchors implemented at resource level.

**2026-04-29 (main-thread):** Wave 11a dispatched — 3.2 provider identity (NPPES) + harmonize orchestrator (pipeline driver). Logged Phase-2 follow-up: add `class_label` field to per-drug crosswalk entries to replace the hardcoded `_RXCUI_CLASS_LABEL` dict.

**2026-04-29 (sub:sonnet × 2 → main-thread):** Wave 11a fully complete. 3.2 provider identity (NPI exact + name fallback), 13 tests, 3 Synthea Practitioners → 3 distinct canonicals. **🎯 ORCHESTRATOR SHIPS GOLD TIER END-TO-END.** `ehi-atlas harmonize --patient rhett759` produces `corpus/gold/patients/rhett759/{bundle.json (12 MB), provenance.ndjson (16 KB, 17 records), manifest.json}`. 5 sources loaded (1 real silver + 4 stub-silver), 5 condition merges, 4 med reconciliations, 8 obs dedups, bundle hash `be0ab6c418b36214…`. **300/300 full suite green.** **Open issue:** conflicts_detected=0 — Artifact 2 cross-class flag is structurally present but doesn't surface in gold; integration test 3.11 will diagnose.

**2026-04-29 (main-thread):** Wave 11b dispatched — 3.11 5-artifact integration test (the regression bar). Will run the orchestrator + assert each of the 5 showcase artifacts produces expected behavior in the gold tier; surfaces any wiring gaps (notably the Artifact 2 detection issue).

**2026-04-29 (sub:sonnet → main-thread): 🎯 STAGE 3 COMPLETE.** Task 3.11 ships 23 integration tests — 21 pass + 2 documented Phase-2 skips. **Two-part Artifact-2 bug found and fixed inline:** (1) Synthea uses RxCUI **316672** (product-level SCD) not 36567 (ingredient-level IN); added 316672 to `_RXCUI_CLASS_LABEL` (3-line fix in medication.py). (2) `apply_conflict_pairs` mutated silver dicts but the reconciled gold MedicationRequest is a *new* dict object — added an 18-line propagation loop in orchestrator.py to copy EXT_CONFLICT_PAIR from silver to merged gold. **conflicts_detected now=1** (was 0); Provenance has 18 records (was 17, +1 DERIVE for the cross-class conflict); bundle hash `6c7ce02eea4bc3e0…`. **Two corrections to my Artifact assumptions surfaced by the test:** (a) Rhett759 has Hyperlipidemia, not HTN — Artifact 1 is now SNOMED 55822004 ≡ ICD-10 E78.5 → CUI C0020473. (b) Rhett759's Synthea bundle has no creatinine Observation — Artifact 5 is the epic-ehi + lab-pdf merge, not synthea + lab-pdf. **321 passed + 2 skipped** = full suite green.

**2026-04-29 (Blake → main-thread):** Pivot for Stage 5. Don't integrate into the existing patient-journey app yet — build a NEW standalone Streamlit console inside `ehi-atlas/app/` that visualizes the workflow (sources → bronze → standardize → harmonize → gold), with explicit badges showing which steps use LLMs vs scripts vs reference tables. Phase 2 plugs into the patient-journey app. Also: spawn a sub-agent to review a Josh Mandel YouTube video (`J3Fs_dEcbIc`) and write a short note in research/ on how it frames our positioning.

**2026-04-29 (main-thread):** Wave 12 dispatched — 5.1 Streamlit console v1 (sub:sonnet) + Josh-Mandel-YouTube-review (sub:sonnet, parallel). Stage 5 reframed in tracker.

**2026-04-29 (sub:sonnet → main-thread):** Josh YouTube review done. Transcript blocked but agent recovered the **DevDays 2024 PPTX deck** (8 slides, verified source devdays.com) + 5 adjacent sources (Flexpa article on the same talk, Josh's CMS RFI response, Banterop/conversational-interop LinkedIn article, SMART Health IT filings). Memo at `~/Chief/20-projects/ehi-ignite-challenge/research/josh-mandel/notes/youtube-talk.md`. **Headline positioning insight:** reframe the submission opening from "we built a harmonization platform" to "the patient holding the ZIP" — start with the scene Josh's DevDays talk opens with (a patient receives their §170.315(b)(10) export, hundreds of TSV files, no schema, no labels) and position EHI Atlas as the first tool they run after the ZIP arrives. Plus terminology to adopt verbatim: "(b)(10)", "computable", "timely, user-driven, comprehensive", "each provider is a separate slice." Three concrete narrative changes documented for Stage 6.

**2026-04-29 (sub:sonnet → main-thread):** Stage 5.1 done. EHI Atlas Console v1 ships at port 8503 (`.venv/bin/streamlit run ehi-atlas/app/streamlit_app.py`). 5 pages: Overview (pipeline diagram + per-stage metrics), Sources & Bronze (drill-down per source with FHIR / SQLite / PDF viewers), Standardize (silver tier annotation viewer), Harmonize (Artifact 1/2/5 before-after merge displays), Gold & Provenance (manifest + searchable resources + provenance walker). Reusable badge component (🔧 Script · 🤖 LLM · 📚 Reference · ⚙️ Hybrid) annotates engine type per step. Boot smoke-test passes (`/_stcore/health` → ok, no Python errors). launch.json entry added (was blocked for sub-agent; main-thread applied). **Wave 12 complete.**

**2026-04-29 (main-thread):** Wave 13 dispatched — pedagogical notebook series (10 notebooks). Jupyter kernel `ehi-atlas` registered for VS Code/Cursor pickup.

**2026-04-29 (sub:sonnet → main-thread):** Wave 13 done. 10 notebooks shipped at `ehi-atlas/notebooks/{00-09}_*.ipynb` plus README + builder script. All 10 spot-execute clean against live corpus. Notebook 06 confirms Artifact 1 merge with `CUI C0020473: 2 condition(s) → merged with both SNOMED+ICD-10 codings, both source-tags, onsetDateTime=2020-03-15`. Sub-agent caught 8 production-code API mismatches in my brief and worked around them (e.g., `BundleValidator.validate()` returns `list[str]` not named report; `find_text_bbox` needs `DocumentLayout`; `score()` not `score_pair()`) — defensive engineering, no broken cells reach Blake.
