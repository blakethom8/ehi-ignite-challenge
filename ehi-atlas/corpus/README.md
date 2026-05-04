# Corpus

The data bench for EHI Atlas. The platform is designed to ingest and harmonize
heterogeneous patient health data — FHIR R4 bundles, Epic EHI Export SQLite,
C-CDA documents, payer claims, lab PDFs, clinical-note PDFs. This directory
holds raw source materials (`_sources/`), staged canonical artifacts (`bronze/`),
and terminology snapshots (`reference/`).

> **Current development focus:** the PDF → FHIR ingestion path. The cross-source
> harmonization implementation (silver / gold / Provenance graph) is the
> platform's defensible wedge and remains the long-horizon target — see
> [`../../docs/architecture/ATLAS-DATA-MODEL.md`](../../docs/architecture/ATLAS-DATA-MODEL.md).
> The early 5-layer scaffold lives at
> [`../../archive/ehi-atlas-5layer/`](../../archive/ehi-atlas-5layer/) and will
> be rebuilt against the production parser once PDF ingestion stabilizes.

## Layout

```
corpus/
├── README.md                       # this file
├── _sources/                       # raw source materials, per-source
│   ├── synthea/                    # open: Synthea-generated FHIR R4 bundles
│   ├── josh-epic-ehi/              # open: Mandel's Epic EHI Export SQLite samples
│   ├── josh-ccdas/                 # open: Mandel's C-CDA fixtures (~12 vendors)
│   ├── synthesized-lab-pdf/        # constructed: rhett759 Quest lab fixture
│   ├── synthetic-pdf-fixtures/     # constructed: lab / med-rec / radiology PDFs
│   ├── uploads/                    # ad-hoc PDFs uploaded via the Streamlit UI
│   ├── blake-cedars/               # personal — gitignored
│   ├── devon-cedars/               # personal — gitignored
│   └── cedars-portal-pdfs/         # personal — gitignored
├── bronze/                         # canonical staged artifacts
│   └── clinical-portfolios/        # Cedars PDFs + Health-Skillz FHIR ground truth
└── reference/                      # terminology snapshots (LOINC, RxNorm); see VERSIONS.md
```

## What the live pipeline reads

The PDF → FHIR pipeline (`ehi_atlas/extract/`, exposed via the Streamlit
console) reads from:

| Path | Used by |
|---|---|
| `_sources/synthesized-lab-pdf/raw/lab-report-2025-09-12-quest.pdf` | Pipeline Bakeoff: rhett759 Quest CMP fixture |
| `_sources/synthetic-pdf-fixtures/raw/*.pdf` | Bake-off fixtures (lab, med-rec, radiology) |
| `_sources/uploads/<sha>/` | PDF Lab + Bakeoff: ad-hoc uploads |
| `bronze/clinical-portfolios/blake_records/HealthSummary_*/...PDF` | Bake-off: Cedars health-summary PDF |
| `bronze/clinical-portfolios/blake_records/cedars-healthskillz-download/health-records.json` | Bake-off: ClientFullEHR ground truth |
| `reference/loinc/`, `reference/rxnorm/` | Terminology lookups (LOINC subset, RxNorm CUI bridge) |

## Privacy gate

Personal sources never get committed in raw form. The gate enforces:

- `_sources/blake-cedars/`, `devon-cedars/`, `cedars-portal-pdfs/` directories
  are gitignored at the dir level (raw, JSON, ZIP all blocked).
- `bronze/` is entirely gitignored — staged artifacts are reproducible from
  `_sources/` and shouldn't enter git history.
- `reference/loinc/`, `reference/rxnorm/`, `reference/snomed/`, `reference/umls/`
  are gitignored (large terminology snapshots); only `reference/VERSIONS.md`
  is tracked.

Verify: `make validate-gate` (runs `scripts/validate-privacy-gate.sh`).

## How to acquire the open sources

The "open" portion of the corpus reproduces fully on a fresh checkout. Personal
sources require Blake's portal credentials and aren't in the public reproduction
path.

### Synthea (already vendored at the repo root)

Used by both this dev zone and the production app. Lives at
`../../data/synthea-samples/synthea-r4-individual/fhir/` (1,180 individual
FHIR bundles); a copy of the showcase patient is symlinked or referenced from
`_sources/synthea/` as needed.

### Mandel's Epic EHI + CCDA samples

```bash
cd corpus/_sources/

git clone --depth 1 https://github.com/jmandel/my-health-data-ehi-wip josh-epic-ehi/raw
cd josh-epic-ehi/raw && git checkout 188d93814515636afd9f027f2d5efebfd00260c7 && cd ../..

git clone --depth 1 https://github.com/jmandel/sample_ccdas josh-ccdas/raw
cd josh-ccdas/raw && git checkout 39aab8a882cd166bbbeff7f79995c7f09eb588bc && cd ../..
```

Pinned SHAs are also recorded at `_sources/josh-epic-ehi/PINNED-SHA.txt` and
`_sources/josh-ccdas/PINNED-SHA.txt`.

### Synthesized lab PDF (rhett759 Quest fixture)

```bash
cd ehi-atlas
uv run python corpus/_sources/synthesized-lab-pdf/generator.py
```

Produces `_sources/synthesized-lab-pdf/raw/lab-report-2025-09-12-quest.pdf`.
Deterministic via `SOURCE_DATE_EPOCH=946684800`; expected MD5
`cd7124966b5be8b7974684a5bd533b63`.

### Personal sources

See per-source READMEs (each documents privacy gate + acquisition):

- `_sources/blake-cedars/README.md` — SMART-on-FHIR pull via Health Skillz.
  Live data lives at `bronze/clinical-portfolios/blake_records/`.
- `_sources/devon-cedars/README.md` — same workflow, Devon's consent.
- `_sources/cedars-portal-pdfs/README.md` — manual portal download.
