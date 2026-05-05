# Atlas Data Model — Architectural Decisions

*Status: load-bearing. Read this first. Last updated: 2026-05-05.*

> **Purpose.** This is the single entry-point architecture doc for Atlas's data layer. It captures *what we decided and why*, not the exhaustive spec. For depth, follow the cross-references at the end.

---

## TL;DR — five decisions

1. **Schema: FHIR R4 + USCDI as the canonical silver/gold target.** Don't invent a new common data model. Use FHIR's extension mechanisms for the 15% that doesn't fit standard resources. Use sidecar SQL tables for the 5% that isn't really "facts about a patient" (audit logs, billing internals, scheduling).
2. **Bronze layer preserves native shape.** SMART-pulled FHIR stays FHIR. Epic EHI TSV stays SQLite-with-Epic-table-names. PDFs stay PDFs (with extracted-text sidecar). No upfront mapping work — bronze is where Provenance points.
3. **Bronze → silver mapping is LLM-authored at design-time, code-applied deterministically at runtime.** The LLM agent's role is *generating mapping specs*, not *generating data on the fly*. Apps query a fixed schema; specs are versioned and reviewable.
4. **Product shape: hot path UI + cold path agent, sharing the same data graph.** The Patient Journey app is the dense, fast, deterministic surface (~80% of clinician needs). An agent panel handles the long tail via `run_sql` + the Agent SDK. Both query bronze/silver/gold; both render Provenance.
5. **The wedge is the Provenance graph, not the agent or the UI.** Fact-level FHIR Provenance edges from gold facts → silver resources → bronze rows, surfaced as a clinician-facing UX. Nobody else does this; everyone treats Provenance as audit metadata.

---

## Where Atlas sits relative to existing work

```
                                 ATLAS
            ╔═══════════════════════════════════════════════╗
            ║  Layer 5 — INTERPRET                          ║
            ║  Patient Journey UI + agent panel             ║
            ║  "right 5 facts in 30 seconds" briefing       ║  ◀── exists, refining
            ╠═══════════════════════════════════════════════╣
            ║  Layer 4 — CURATE   (gold)                    ║
            ║  medication_episode, condition_active,        ║
            ║  observation_latest, drug_class enrichments   ║  ◀── exists in api/core/sof_materialize
            ╠═══════════════════════════════════════════════╣
            ║  Layer 3 — HARMONIZE   (silver)               ║
            ║  Cross-source merge, entity resolution,       ║  ◀── ★ Atlas's wedge
            ║  conflict detection, FHIR Provenance edges    ║       prototype exists
            ╠═══════════════════════════════════════════════╣
            ║  Layer 2 — STANDARDIZE   (bronze→silver)      ║
            ║  TSV/PDF/HL7v2/CCDA → FHIR R4 + USCDI         ║  ◀── active for FHIR JSON + PDFs
            ║  with extensions for the non-mapping 15%      ║
            ╠═══════════════════════════════════════════════╣
            ║  Layer 1 — INGEST   (bronze)                  ║
            ║  Per-source adapters, raw immutable bronze    ║  ◀── file workspaces active
            ║  Synthea / SMART / EHI Export TSV / PDF /     ║       (Synthea exists today)
            ║  CMS Blue Button / wearables                  ║
            ╚═══════════════════════════════════════════════╝
                          ▲                          ▲
                          │                          │
                          │           Layers 1–2 are what Josh's stack covers
                          │           — but Josh stops at bronze, never merges.
                          │           Atlas owns Layers 3–5.
                          │
              Sources Atlas accepts in the prototype: Synthea, uploaded
              FHIR JSON, and uploaded PDFs. Phase 2 widens to SMART pull,
              EHI TSV, claims, wearables, and richer document types.
```

The full 5-layer spec is in `~/Chief/20-projects/ehi-ignite-challenge/architecture/DATA-AGGREGATION-LAYER.md`. **The wedge is Layer 3 (HARMONIZE) with Provenance — that's the thin spot in the prior-art landscape.**

---

## Decision 1 — Schema: FHIR R4 + USCDI

**FHIR R4** is the umbrella standard (resource types, fields, references). **USCDI** is the regulatory data-class checklist (~18 classes covering ~80% of point-of-care clinical needs). **US Core** is the FHIR Implementation Guide that operationalizes USCDI as profiled FHIR resources.

When this doc says "FHIR R4 + USCDI" it means:

- Schema = FHIR R4 resource types
- Constrained to USCDI's required data classes
- With required terminologies (LOINC, RxNorm, SNOMED, ICD-10-CM)
- Tagged with US Core profiles where applicable

**Why not OMOP / PCORnet / Tuva / a custom schema?** Because:

- Atlas's audience speaks FHIR (clinicians, regulators, patient-facing tools).
- Existing Atlas code (`api/`, `app/`, `fhir_explorer/`, the SOF warehouse) is FHIR-shaped.
- USCDI = certification mandate = guaranteed interop with every certified EHR.
- Inventing a new CDM means abandoning every IG, validator, and tool.
- The active research frontier is *FHIR ↔ OMOP bidirectional + tabular views over FHIR*, not new schemas. (See `harmonization-prior-art.md`.)

### What goes where when FHIR doesn't fit cleanly

Three escape hatches, in order of preference:

| Mechanism | Use when | Example |
|---|---|---|
| **`extension` arrays on standard resources** | Adding a small custom field | `MedicationRequest.extension = [{url: "atlas:drug_class", valueCode: "anticoagulants"}]` (already done) |
| **`Observation` with custom code system** | Recording a new measurement / fact type | Whoop recovery score → `Observation.code.coding[0].system = "https://api.whoop.com/codes"` |
| **Sidecar SQL tables** | Data that isn't really "facts about a patient" | Audit logs, billing internals, scheduling, Epic-internal workflow flags |

**Mapping budget per source:** target ~80% USCDI coverage in standard FHIR, ~15% in extensions, ~5% in sidecar. Don't try to round-trip 100%. The Provenance edges keep the dropped data reachable.

---

## Decision 2 — Bronze preserves native shape

Bronze is the immutable per-source archive. **Never lossy.** Stored in source-native shape:

| Source | Bronze shape |
|---|---|
| Synthea individual bundles | FHIR R4 JSON files, untouched |
| SMART-pulled FHIR (live portals) | `ClientFullEHR` JSON per portal connection (Josh's shape) |
| Epic EHI Export | SQLite materialization with Epic table names (`HNO`, `CSN`, `_C_NAME` etc.) — Josh's `my-health-data-ehi-wip` pipeline |
| CMS Blue Button claims | NDJSON, untouched |
| C-CDA documents | XML, untouched |
| PDFs | Original file + multimodal-extracted JSON sidecar |
| Wearables (Whoop, etc.) | Vendor JSON, untouched |

**Rationale:** the moment you transform bronze, you've made a schema decision that is hard to reverse. Keep the source-of-truth at the source. Provenance edges from silver point back to *exact* bronze rows / fields / file paths.

This matches Josh's "preserve provenance, no merge" instinct **at the bronze layer.** Atlas adds the merge *above* bronze, not in place of it.

---

## Decision 3 — LLM-authored specs, code-applied at runtime

The TSV→FHIR mapping problem (and PDF, claims, wearables) looks like a "let the agent figure it out" problem at first. It mostly is — but **at design-time, not runtime.**

```
DESIGN-TIME (one-time per source, refreshed on schema changes)
  Agent reads: schema annotations + sample rows + Epic FHIR IG
  Agent writes: a typed mapping module (TS/Python)
                  epic_table_X[col_Y] → FHIR_resource_Z[field_W]
                  with transforms, NULL handling, code mapping
  Human reviews: clinical sanity-check, ~4–8h per major resource type
  Output: versioned mapping spec, deterministic, testable

RUNTIME (every patient, every query)
  Code applies the spec → silver
  Queries hit silver / gold (fast, deterministic, sub-second)
  Cold-path queries hit bronze via run_sql tool (LLM may be involved here, OK)
```

**Why not runtime LLM-as-data-engineer (Josh's pattern in `my-health-data-ehi-wip`)?** Because:

- **Determinism.** Production apps can't have stochastic mapping between bronze and silver — same input must produce same output.
- **Speed.** Sub-second UI response can't wait for an LLM round-trip per patient.
- **Validation.** Mapping correctness needs test fixtures, not prompt confidence.
- **Auditability.** Regulators and clinical reviewers need to inspect the spec, not infer behavior from agent traces.
- **Cost.** LLM-per-query at scale is prohibitively expensive.

The agent is *brilliant* at drafting the spec from sparse signal. It's the wrong tool for executing the spec on every query.

**Mapping cadence per source:** days to draft (LLM agent) + weeks to harden (human review + test fixtures + regression tests). Not years. The "multi-year" estimate that sometimes appears in EHI→FHIR discussions assumes complete production-grade conversion of all of EHI; Atlas only needs the USCDI-aligned subset, which is bounded.

---

## Decision 4 — Hot path UI + cold path agent, shared data graph

**The product is not a dashboard. The product is not a chat agent. It's both, with clear roles.**

```
HOT PATH (the primary surface)         COLD PATH (the depth)
  Patient Journey UI                     "Ask anything about this patient" panel
  Dense, deterministic, sub-second       run_sql + FHIR tools via Agent SDK
  Pre-computed gold-layer FHIR views     5–30s response is acceptable
  ~80% of clinician needs                The long tail
  Renders Provenance breadcrumbs         Returns provenance with every answer

           Both query the SAME bronze/silver/gold graph.
           Both surface Provenance edges from gold → silver → bronze.
```

**Why this shape:** clinicians under time pressure want a dense, fast, predictable surface — they don't want to chat-and-wait for facts they need now. But the surface can't anticipate every query a clinician might ask. The agent panel is the escape hatch for the long tail, *using the same underlying data and tools.*

This is the same shape as Cursor (editor + agent), Notion AI (doc + agent), Perplexity (results + agent). The agent is the power tool; the UI is the primary interface.

---

## Decision 5 — The wedge is the Provenance graph

Atlas's defensible technical contribution, per `harmonization-prior-art.md` §1.5:

> *"Nobody combines (a) merge across SMART-pull FHIR + Epic EHI Export TSV + claims + C-CDA + SDoH, (b) FHIR-native Provenance edges from every gold fact back to bronze sources, (c) a clinician-facing 'where did this fact come from' UI."*

Three concrete implications:

1. **Every silver resource carries `meta.source` provenance.** Implemented as a real FHIR `Provenance` resource (not a homegrown audit field), pointing at the bronze record.
2. **Every gold fact carries multi-step provenance** — gold → silver(s) → bronze(s). For derived facts (e.g. `medication_episode`), all contributing silver rows are referenced.
3. **The UI surfaces this**, not just stores it. Click any fact in the briefing → see the lineage with timestamps and source labels.

**What we deliberately don't build:**

- A new common data model (use FHIR + USCDI).
- Runtime LLM-as-database (deterministic specs, code execution).
- A pure chat agent (it's a UI + agent product).
- A pure dashboard (the agent handles the long tail).
- Provenance as audit-log-only (it's the UX).
- Full TSV → FHIR conversion (USCDI-aligned subset only; the rest stays in bronze with pointers).

---

## Phase 1 vs Phase 2 priority

**Phase 1 (Submission deadline 2026-05-13):** prove the architecture end-to-end
on a tight vertical slice: curated Synthea workspaces for reproducible demos,
plus uploaded workspace records that can ingest FHIR JSON/PDF sources, run
harmonization, review blockers, publish a snapshot, and feed downstream FHIR
Charts / Clinical Insights.

1. Provenance edges in the data layer — every fact carries `bronze_source` + `bronze_path`.
2. Provenance breadcrumbs in the UI — click any fact → see lineage.
3. Run artifacts — scripted harmonization creates a durable candidate record
   with source fingerprints, matcher version, review items, and provenance.
4. Publish snapshots — an activated workspace snapshot becomes the read target
   for FHIR Charts and Clinical Insights.
5. Agent panel using existing chart context + Agent SDK — same data graph.

**Phase 2 (2026 summer onward):** widen the source set.

- LLM-authored Epic TSV → FHIR mapping spec (USCDI-aligned subset).
- CMS Blue Button claims ingest.
- C-CDA → FHIR converter (use Microsoft FHIR-Converter as starting point).
- Expand PDF multimodal extraction beyond the current lab/report slice.
- Wearables (Whoop, Oura, Apple HealthKit) via FHIR Observation extensions.
- Real cross-source merge with conflict resolution.
- Per-fact confidence/quality scoring.

---

## Cross-references

| For depth on... | Read |
|---|---|
| 5-layer pipeline spec | `~/Chief/20-projects/ehi-ignite-challenge/architecture/DATA-AGGREGATION-LAYER.md` |
| Competitive landscape | `~/Chief/20-projects/ehi-ignite-challenge/research/harmonization-prior-art.md` |
| Multi-format ingestion product spec | `docs/ideas/FORMAT-AGNOSTIC-INGESTION.md` |
| Layer 5 — context engineering for the LLM | `docs/architecture/CONTEXT-PIPELINE.md` |
| SOF warehouse (current Layer 4 implementation) | `patient-journey/core/sql_on_fhir/views/README.md` |
| Platform-level architecture | `docs/architecture/ECOSYSTEM-OVERVIEW.md` |
| Josh Mandel's stack (the bronze-only prior art) | `data-research/josh-stack-deep-dive/INDEX.md` |
| Data shape catalog | `data-research/josh-stack-deep-dive/data-lane/session-D01-data-catalog.md` |
| Agent SDK + tracing implementation | `docs/architecture/ANTHROPIC-AGENT-SDK.md`, `docs/architecture/tracing.md` |

---

## Glossary (just enough)

- **FHIR R4** — Fast Healthcare Interoperability Resources, version 4. The umbrella standard for clinical-data resource types.
- **USCDI** — United States Core Data for Interoperability. ONC-published list of ~18 data classes that certified EHRs must support. *Not a schema — a checklist of which FHIR resources/fields are mandatory.*
- **US Core** — the FHIR Implementation Guide that profiles FHIR R4 to meet USCDI requirements.
- **Bronze / silver / gold (medallion)** — preserved-native / harmonized-and-mapped / derived-and-ranked. Standard data-engineering layer naming.
- **Provenance graph** — fact-level lineage from gold → silver → bronze, implemented as FHIR `Provenance` resources, surfaced in the UI.
- **EHI Export** — bulk patient-record export mandated by ONC § 170.315(b)(10) (since Dec 31, 2023). Format varies per vendor (TSV for Epic, NDJSON for athena, etc.). *Different from FHIR API — both exist for every certified EHR but emit different shapes.*
- **Hot path / cold path** — UI surface (sub-second, deterministic) vs. agent surface (5–30s, flexible). Both query the same data graph.

---

## What changes when this doc changes

- If a new data source is added → update Decision 2's table + Phase 2 list.
- If the schema target changes (it shouldn't) → update Decision 1 and notify everything in `api/core/sof_materialize.py`.
- If the product shape changes (UI vs. agent split) → update Decision 4 and re-read the prior-art landscape.
- Always preserve the wedge in Decision 5. If you find yourself drifting away from "Provenance as UX," stop and re-check.
