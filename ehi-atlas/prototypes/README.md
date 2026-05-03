# Prototypes — Code That Reads/Writes the Datamart

Code home for everything in `data-research/`. Each prototype is a self-contained subdirectory that reads from [`../datamart/inputs/`](../datamart/inputs/) and writes to [`../datamart/intermediate/<topic>/`](../datamart/intermediate/).

**Scope:** code only. Data lives in `../datamart/`. Study notes live in `../josh-stack-deep-dive/`.

## Two flavors of prototype

Filenames carry a one-word prefix so the inventory stays scannable:

| Prefix | Purpose |
|---|---|
| `josh-…/` | Replays or thin-wrappers of Josh Mandel's pipelines. Goal: faithfully reproduce his data shapes against our Synthea/EHI fixtures so we can `cat` what he produces. Driven by data-lane sessions D02–D06. |
| `atlas-…/` | EHI Atlas–specific experiments. Goal: prototype the harmonization/merge/provenance work that *isn't* in Josh's stack. Driven by data-lane session D07 onward, plus standalone Atlas work. |

## Directory layout (populated session-by-session)

```
prototypes/
├── README.md
│
├── josh-fhir-snapshot/          ← D02: fetch FHIR bundle → ClientFullEHR JSON
├── josh-fhir-flatten/           ← D02: FHIR → SQLite per-resource-type tables
├── josh-plaintext-render/       ← D02: per-resource → narrative text
├── josh-redaction-profile/      ← D03: variant clusters + redaction suggestions
├── josh-skill-bundle/           ← D03: assemble local-skill ZIP
├── josh-ehi-tsv-ingest/         ← D04: TSV + per-table schemas → JSON
├── josh-ehi-table-merge/        ← D05: 552 physical → N logical tables
├── josh-ehi-materialize/        ← D06: codegen + SQLite + LLM annotation
│
├── atlas-shape-diff/            ← D07: diff Synthea-FHIR vs. Epic-EHI-derived FHIR
├── atlas-cross-source-merge/    ← Atlas: merge SMART-pulled + EHI-derived per patient
├── atlas-provenance-graph/      ← Atlas: FHIR Provenance edges bronze→silver→gold
└── atlas-bronze-silver-gold/    ← Atlas: target medallion schema + fact-shape
```

(Subdirectories don't exist yet — each is created in the session that builds it.)

## Per-prototype conventions

Each `<prefix>-<topic>/` directory contains:

```
<prefix>-<topic>/
├── README.md          ← purpose, usage, output paths, data-lane session reference
├── package.json       ← Bun TS prototypes; or pyproject snippet for Python ones
├── src/               ← source code
└── tests/             ← optional, for Atlas-side experiments
```

- **Bun TS** preferred for `josh-*` prototypes (matches Josh's runtime, easiest faithful port).
- **Python** preferred for `atlas-*` prototypes (matches the rest of `api/` in the repo root).
- Every entry-point script reads from `../../datamart/inputs/`, writes to `../../datamart/intermediate/<topic>/`, never overwrites inputs.
- Idempotent — re-running produces the same output (or a versioned subfolder).
- A 3-line header comment on every entry-point: `purpose`, `usage`, `output path`.

## Promotion path

If a prototype matures into production-grade code:
- `josh-*` ports may stay here permanently as reference — they're study artifacts, not Atlas code.
- `atlas-*` experiments graduate into `~/Repo/ehi-ignite-challenge/api/`, `app/`, or `ehi-atlas/`. Leave a one-line note in this README pointing at the new home, then archive or delete the prototype.

## Cross-references

- Each prototype's `README.md` links back to the data-lane session that created it: `See: josh-stack-deep-dive/data-lane/session-D02-...md`.
- Each data-lane session links forward to the prototype it shipped: `Code: prototypes/josh-fhir-snapshot/`.
