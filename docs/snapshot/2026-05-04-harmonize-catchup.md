# Harmonization Layer — Catch-Up Report

| Field | Value |
|---|---|
| **Date** | 2026-05-04 |
| **Topic** | Harmonization layer — current state, recent commits, data flows |
| **Author** | Claude Opus 4.7 (autonomous build loop) |
| **Repo state** | `master` @ `5e9246a` |
| **Commits covered** | `dad8041..5e9246a` (Moves S–V; harmonize feature ships end-to-end) |
| **Tests at writeup** | 153 green (129 lib unit + 24 API) |

> Use this snapshot as the get-up-to-speed read after a multi-iteration autonomous build run. The entries below trace what shipped, where it lives in the tree, and how data flows through it. The companion experiment journal at [`docs/architecture/PIPELINE-LOG.md`](../architecture/PIPELINE-LOG.md) has per-move detail; this report is the higher-altitude picture.

---

## 1. The last 8 commits (Moves S–V — final polish on the harmonize feature)

| Commit | Date | What shipped |
|---|---|---|
| `dad8041` — feat(harmonize): self-bootstrapping Synthea demo | 2026-05-03 | A fresh-clone reviewer with no private data still sees a working harmonize flow. One Synthea patient bundle is split at a 2018-01-01 cutoff into two artificial "EHR snapshot" sources. Chronic conditions / persistent identity carry across the cut so 8 of 9 conditions cross-source merge. |
| `d228669` — docs: Move S | 2026-05-03 | PIPELINE-LOG entry recording the demo-collection design + carry-forward semantics. |
| `88554d6` — feat(harmonize): empty-state + loading UI | 2026-05-03 | Three render branches at the top of the harmonize page: spinner while collections load, centered "no collections" card when empty (with two CTAs), populated state otherwise. The empty state was previously unreachable; once `blake-real` registered conditionally, it became real. |
| `d357009` — docs: Move T | 2026-05-03 | PIPELINE-LOG entry for the empty/loading branches. |
| `c1af1e5` — feat(harmonize): async PDF extraction | 2026-05-03 | `POST /extract` no longer blocks 30–90s. Returns 202 + `job_id` immediately; React polls `/extract-jobs/{job_id}` every 1.5s. On `status=complete` all six harmonize-scoped query caches invalidate in one paint. Background daemon thread + `sys.path` fix for `ehi_atlas` import. |
| `9f5b9e7` — docs: Move U | 2026-05-03 | PIPELINE-LOG entry for the async extract pattern. |
| `ff22a14` — feat(harmonize): responsive breakpoints | 2026-05-03 | All six merged-record tables collapse columns at sm/md/lg breakpoints. No more horizontal scrollbar on tablet/narrow-laptop viewports. |
| `5e9246a` — docs: Move V | 2026-05-03 | PIPELINE-LOG entry for the responsive pass. |

These were the polish wave. The structural work — merge logic for all 5 USCDI resource types, the bidirectional Provenance graph, the source-diff feature — landed in earlier commits (Moves J–R) and is also covered briefly in the data-flow diagrams below.

---

## 2. Where everything lives — folder tree

```
ehi-ignite-challenge/
│
├── lib/                                    # ← Production library code (imports allowed from api/, app/, ehi-atlas/)
│   └── harmonize/                          # ⭐ THE HARMONIZE ENGINE (1,920 LOC)
│       ├── __init__.py                       # public API surface (merge_observations, merge_conditions, …)
│       ├── models.py                         # MergedObservation, MergedCondition, MergedMedication,
│       │                                     # MergedAllergy, MergedImmunization, ProvenanceEdge dataclasses
│       ├── observations.py                   # LOINC + name-bridge matcher, longitudinal merge
│       ├── conditions.py                    # SNOMED → ICD-10 → ICD-9 → name matcher
│       ├── medications.py                   # RxNorm + drug-name canonicalization (strips brand parens)
│       ├── allergies.py                     # SNOMED + RxNorm + name matcher
│       ├── immunizations.py                 # (CVX, occurrence_date) event-keyed matcher
│       ├── loinc_bridge.py                  # ~50 hand-curated lab name → LOINC mappings
│       ├── units.py                         # mg/dL ⇄ mmol/L (LOINC-aware glucose/cholesterol disambiguation)
│       └── provenance.py                    # FHIR Provenance resource minter, Atlas Extension URLs
│
├── lib/tests/                              # 129 unit tests on the merge engine
│   ├── test_harmonize.py                     # observations + smoke (17)
│   ├── test_harmonize_conditions.py          # SNOMED/ICD/name-bridge (11)
│   ├── test_harmonize_medications.py         # RxNorm + drug-name canonicalize (11)
│   └── test_harmonize_allergies_immunizations.py  # 13 tests
│
├── api/                                    # FastAPI service (the JSON layer in front of lib/harmonize)
│   ├── core/
│   │   └── harmonize_service.py            # ⭐ COLLECTION REGISTRY + LOADER + ASYNC JOB STORE (1,165 LOC)
│   │                                       #   • CollectionDefinition / SourceDefinition
│   │                                       #   • blake-real (conditional), synthea-demo (self-bootstrapping),
│   │                                       #     upload-<session> (auto-discovered from data/aggregation-uploads/)
│   │                                       #   • merged_observations() / _conditions() / _medications() /
│   │                                       #     _allergies() / _immunizations()
│   │                                       #   • facts_for_document_reference() ← per-source contribution walk
│   │                                       #   • source_contribution_diff() ← unique-vs-shared partition
│   │                                       #   • ExtractJob store + start_extract_job() + get_extract_job()
│   ├── routers/
│   │   └── harmonize.py                    # ⭐ 12 ENDPOINTS — see "Pipeline #2" below
│   ├── models.py                           # Pydantic response schemas (Harmonize* classes)
│   └── tests/
│       └── test_harmonize_api.py           # 24 API tests
│
├── app/src/                                # React clinician app (Vite + TypeScript)
│   ├── pages/Modules/
│   │   ├── HarmonizeView.tsx               # ⭐ THE REACT SURFACE (1,611 LOC)
│   │   │                                     #   • collection picker
│   │   │                                     #   • Sources panel (clickable rows → contribution panel)
│   │   │                                     #   • 5 tabs: Labs / Conditions / Medications / Allergies / Immunizations
│   │   │                                     #   • Per-fact detail card + Provenance lineage panel
│   │   │                                     #   • Async extract button with polling-backed progress
│   │   │                                     #   • Empty-state + loading UI
│   │   └── DataAggregator.tsx              # Upload UI; "Harmonize N uploads →" CTA links here
│   ├── api/client.ts                       # Typed HTTP client (12 harmonize methods)
│   └── types/index.ts                      # Pydantic mirror types for the harmonize endpoints
│
├── data/                                   # Runtime data (mostly gitignored)
│   ├── synthea-samples/                    # 1,180 Synthea bundles (gitignored)
│   ├── harmonize-demo/                     # ⭐ self-bootstrapping cache (gitignored)
│   │   └── synthea-demo/
│   │       ├── ehr-snapshot-2018.json      # Pre-2018 split of one Synthea patient
│   │       └── ehr-snapshot-2024.json      # Full record (carries chronic conditions forward)
│   └── aggregation-uploads/                # User-uploaded files (gitignored)
│       └── <session>/                      # Each subdir auto-registers as upload-<session>
│           ├── *.pdf                       # Triggers extract-pdf source
│           ├── *.json                      # FHIR-shaped → fhir-pull source
│           └── <basename>.extracted.json   # Cached multipass-fhir output
│
├── ehi-atlas/                              # Dev zone (PDF extraction pipeline lives here)
│   ├── lib/extract/pipelines/        # multipass-fhir, single-pass-vision, gemma-tabular
│   │   └── multipass_fhir.py               # Used by harmonize_service.extract_pending_pdfs()
│   └── corpus/bronze/clinical-portfolios/blake_records/  # The Cedars + Function Health real data
│       ├── cedars-healthskillz-download/health-records.json    # Cedars FHIR pull
│       ├── HealthSummary_May_03_2026/extracted-cedars-healthsummary.json  # Cedars PDF (extracted)
│       └── blake_function_pdfs/extracted-{2024-07-26,2024-07-29,2025-11-29}.json  # Function Health
│
└── docs/
    ├── architecture/
    │   ├── PIPELINE-LOG.md                 # Running journal — Moves J through V cover this work
    │   ├── ATLAS-DATA-MODEL.md             # Strategic framing of harmonization as the Atlas wedge
    │   └── HARMONIZATION-WORKED-EXAMPLE.md # HDL Cholesterol walkthrough (Move J)
    └── snapshot/                           # ← you are here
        └── 2026-05-04-harmonize-catchup.md
```

---

## 3. Data flow #1 — INGESTION (sources → merged record)

The forward pipeline. This is what runs when a user opens the harmonize page or extracts a new upload.

```
┌─────────────────── SOURCE DATA ON DISK ───────────────────┐
│                                                            │
│  Synthea bundles                                           │
│  data/synthea-samples/synthea-r4-individual/fhir/          │
│      Adria871_Ankunding277_….json                          │
│                              │                             │
│                              ▼                             │
│  data/harmonize-demo/synthea-demo/    ← bootstraps once    │
│      ehr-snapshot-2018.json   (pre-2018 split)             │
│      ehr-snapshot-2024.json   (full record)                │
│                                                            │
│  Cedars + Function Health (blake-real, conditional)        │
│  ehi-atlas/corpus/bronze/clinical-portfolios/              │
│      cedars-healthskillz-download/health-records.json      │
│      HealthSummary_May_03_2026/extracted-….json            │
│      blake_function_pdfs/extracted-{date}.json             │
│                                                            │
│  User uploads (upload-<session>, dynamic)                  │
│  data/aggregation-uploads/<session>/                       │
│      *.pdf  +  *.pdf.extracted.json (cached)               │
│      *.json (FHIR-shaped)                                  │
└────────────────────────────┬───────────────────────────────┘
                             │
                             ▼ via SourceDefinition.path
            api/core/harmonize_service.py
            ┌────────────────────────────────────┐
            │  _load_resources_by_type(source)   │
            │    • fhir-pull  → Health-Skillz    │
            │       envelope OR plain Bundle     │
            │    • extracted-pdf → Bundle        │
            │  returns dict[ResourceType, list]  │
            │  (mtime-cached via lru_cache)      │
            └─────────────────┬──────────────────┘
                              │
                              ▼
             For each resource type, build SourceBundle objects:
             ┌──────────────────────────────────┐
             │  SourceBundle(                   │
             │    label="Cedars-Sinai (FHIR)",  │
             │    observations=[FHIR dicts],    │
             │    document_reference="DR/…",    │
             │  )                               │
             └─────────────┬────────────────────┘
                           │
                           ▼ lib/harmonize/observations.py (or .conditions, .medications, …)
        ┌─────────────────────────────────────────────────────────┐
        │  merge_observations([bundle1, bundle2, …])              │
        │                                                         │
        │  For each Observation in each bundle:                   │
        │    1. Extract LOINC code, name, value, unit, date       │
        │    2. Resolve identity:                                 │
        │         loinc match → key = "loinc:<code>"              │
        │         else name-bridge (lib/harmonize/loinc_bridge)   │
        │         else passthrough on normalized name             │
        │    3. Normalize unit if canonical_unit known            │
        │       (mg/dL ⇄ mmol/L via lib/harmonize/units)          │
        │    4. Emit ObservationSource into MergedObservation     │
        │    5. Emit ProvenanceEdge tagged with the activity      │
        │       (loinc-match, name-bridge, unit-normalize, …)     │
        └─────────────────────────────┬───────────────────────────┘
                                      │
                                      ▼
                  list[MergedObservation], list[MergedCondition], …
                  Each .sources is sorted oldest-first.
                  Each .provenance has one edge per contributing source.
                                      │
                                      ▼ FHIR Provenance JSON via lib/harmonize/provenance.py
                  ┌────────────────────────────────────┐
                  │  Provenance resource:              │
                  │    target: [{ref: merged_ref}]     │
                  │    activity: top-ranked edge       │
                  │    entity: [                       │
                  │      { what: source_ref,           │
                  │        extension: [                │
                  │          source-label,             │
                  │          harmonize-activity        │
                  │        ] },                        │
                  │      … one per source              │
                  │    ]                               │
                  └────────────────────────────────────┘
```

**The clinical signal that previously required two browser tabs:** HDL trajectory **81 → 67 mg/dL** between Function Health 2024-07 and Cedars FHIR 2025-11, surfaced because both sources contributed to the same `MergedObservation` keyed on LOINC `2085-9`.

---

## 4. Data flow #2 — API SURFACE (12 endpoints) and how the React app uses them

```
React HarmonizeView                          api/routers/harmonize.py
─────────────────                            ────────────────────────

On page load:
  collectionsQuery ─────────GET────────────► /api/harmonize/collections
                                                returns list[Collection]
                                                (synthea-demo, [blake-real],
                                                 upload-<session>…)

User picks collection:
  sourcesQuery ─────────────GET────────────► /api/harmonize/{id}/sources
                                                per-source counts
                                                + document_reference
  diffQuery ────────────────GET────────────► /api/harmonize/{id}/source-diff
                                                unique vs shared totals
                                                + unique_facts lists
                                                ⬑ surfaces vision wins

User picks "Labs" tab:
  observationsQuery ────────GET────────────► /api/harmonize/{id}/observations
                                                ?cross_source_only=true
  (similarly for /conditions, /medications,
   /allergies, /immunizations)

User clicks a merged-record row:
  provenanceQuery ──────────GET────────────► /api/harmonize/{id}/provenance/{merged_ref}
                                                returns the Provenance graph
                                                pointing back at sources
                                                ⬑ "where did this fact come from?"

User clicks a source row:
  contributionsQuery ───────GET────────────► /api/harmonize/{id}/contributions/{doc_ref}
                                                every merged record this
                                                source contributed to
                                                ⬑ "what did this PDF give us?"

User clicks "Extract uploaded PDFs":
  extractMutation ──────────POST 202───────► /api/harmonize/{id}/extract
                                                spawns daemon thread,
                                                returns job_id
  extractJobQuery ────GET (every 1.5s)─────► /api/harmonize/extract-jobs/{job_id}
                                                status: pending → running
                                                       → complete | failed
  on status=complete:
    invalidate sources, observations,
    conditions, medications, allergies,
    immunizations, source-diff caches
    → tables refresh in one paint
```

---

## 5. Data flow #3 — REVERSE PROVENANCE WALK (the Atlas wedge in action)

This is the differentiating feature. From any DocumentReference, walk back to every fact derived from it.

```
                 ┌──────────────────────────────────┐
                 │  User clicks a Sources row       │
                 │  (e.g. "Cedars-Sinai (FHIR)")    │
                 └────────────────┬─────────────────┘
                                  │
                                  ▼ document_reference = "DocumentReference/cedars-healthskillz-…"
                 GET /api/harmonize/blake-real/contributions/{ref}
                                  │
                                  ▼
       api/core/harmonize_service.facts_for_document_reference():
       ─────────────────────────────────────────────────────────
       For each merged-record list (Obs / Cond / Med / All / Imm):
         filter to records where ANY source has this doc_ref
         serialize to JSON
       ─────────────────────────────────────────────────────────
                                  │
                                  ▼  HarmonizeContributionsResponse
       {
         label: "Cedars-Sinai (FHIR)",
         totals: { observations: 174, conditions: 15, medications: 7,
                   allergies: 1, immunizations: 10, all: 207 },
         observations: [...],   conditions: [...],   medications: [...],
         allergies: [...],      immunizations: [...]
       }

                                  ▼  React renders inline panel:
       ┌──────────────────────────────────────────────┐
       │ Reverse Provenance walk                      │
       │ What did Cedars-Sinai (FHIR) contribute?     │
       │                                              │
       │ [Labs 174] [Cond 15] [Med 7] [All 1] [Imm 10]│
       │                                              │
       │ Conditions · 15      Medications · 7         │
       │ ───────────────      ───────────────         │
       │ • Hyperlipidemia     • cetirizine            │
       │ • Allergic rhin…     • fluticasone…          │
       │ • Sinus congest…     • loratadine            │
       │   …                    …                    │
       └──────────────────────────────────────────────┘
```

**The same shape feeds the source-diff feature** — `source_contribution_diff()` runs the same walk for every source, then partitions each merged record into "unique to this source" vs "shared with at least one other." The PDF's unique conditions on `blake-real` are exactly the four vision wins identified by manual triage in earlier work (turbinate hypertrophy, sesamoid variant, toe fracture, MTP osteophyte) — now surfaced automatically by the graph.

---

## 6. Live numbers (current state of `blake-real`)

| | Sources | Obs | Cond | Med | All | Imm |
|---|---:|---:|---:|---:|---:|---:|
| Cedars-Sinai (FHIR) raw | 1 | 234 | 28 | 7 | 1 | 10 |
| Cedars-Sinai (PDF) raw | 1 | 138 | 7 | 6 | 1 | 8 |
| Function Health × 3 raw | 3 | 169 | 0 | 0 | 0 | 0 |
| **Total raw** | **5** | 541 | 35 | 13 | 2 | 18 |
| **Merged (canonical)** | | 350 | 19 | 7 | 1 | 10 |
| **Cross-source merges** | | 65 | 3 | 6 | 1 | 8 |
| **Cedars FHIR contributes** | | 174 | 15 | 7 | 1 | 10 (= 207 facts) |
| **Cedars PDF contributes** | | 138 | 7 | 6 | 1 | 8 (= 160 facts) |

**`synthea-demo` (the fresh-clone fallback):** 38 merged Observations / 10 cross-source · 9 merged Conditions / 8 cross-source · 0 cross-source on the other types (Synthea models them as discrete events, not chronic state, so the temporal split correctly produces non-overlapping records).

153 tests green (129 lib unit + 24 API). The harmonize feature is production-shaped end-to-end across every collection-registry state, every viewport size, and every USCDI v3 clinical-summary core resource type.

---

## 7. What's next, when you want to direct again

The natural follow-on is **integration** — the harmonize layer is now serving structured JSON, but the rest of the React app still reads the raw Synthea bundle:

1. Wire **Clinical Insights** (`app/src/pages/Modules/ClinicalInsights.tsx`) to consume the harmonized record so the "right 5 facts in 30 seconds" briefing is backed by cross-source merge.
2. Wire the **agent assistant** (`api/core/provider_assistant_service.py`) to query merged records as tools, so chat answers like "what does the PDF say about HDL" come back with source attribution.
3. **Demo recording / reviewer narrative** — capture a walkthrough video before the May 13 Phase 1 deadline.

Lower priority: pairwise source diff (A − B specifically, not just "A − everyone else"), persistent job store (sqlite-backed), Streamlit-page parity with the React side.
