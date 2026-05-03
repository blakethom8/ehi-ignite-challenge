# Corpus

> The data layer of EHI Atlas. Bronze (per-source raw), silver (FHIR-standardized), gold (cross-source merged + Provenance). All paths under this directory are owned by the harmonizer; the existing app reads only `gold/`.

## Layout

```
corpus/
├── README.md                # this file
├── _sources/                # raw source materials, per-source
│   ├── synthea/
│   ├── josh-epic-ehi/
│   ├── josh-ccdas/
│   ├── cms-blue-button/
│   ├── blake-cedars/        # personal — gitignored at raw/
│   ├── devon-cedars/        # personal — gitignored at raw/
│   ├── cedars-portal-pdfs/  # personal — gitignored at raw/
│   └── synthesized-lab-pdf/ # constructed
├── bronze/                  # canonical staging (Layer 1 output)
├── silver/                  # FHIR Bundles per source (Layer 2 output)
├── gold/                    # merged FHIR + Provenance (Layer 3 output, ext interface)
└── reference/               # terminology snapshots (UMLS, RxNorm, LOINC)
```

## Reproduction recipe

To rebuild the corpus from scratch on a fresh checkout. The "open" portion (Synthea + Mandel + synthesized lab PDF + CCDA) reproduces fully; personal sources (Blake's, Devon's, Cedars portal) require Blake's portal credentials and are not generally reproducible.

### Step 1 — Install dependencies

```bash
cd ehi-atlas
uv sync --all-extras
```

This installs `reportlab` (for the synthesized lab PDF generator), `pdfplumber` (for vision-extraction layout analysis), `instructor` (for schema-constrained LLM extraction), `fhir.resources` (FHIR R4 Pydantic models), and the rest of the stack documented in `pyproject.toml`.

### Step 2 — Clone Mandel's open repos at pinned SHAs

```bash
cd corpus/_sources/

# Epic EHI Export pipeline + redacted SQLite dump
git clone --depth 1 https://github.com/jmandel/my-health-data-ehi-wip josh-epic-ehi/raw
cd josh-epic-ehi/raw && git checkout 188d93814515636afd9f027f2d5efebfd00260c7 && cd ../..

# CC BY 4.0 CCDA fixtures across ~12 vendors
git clone --depth 1 https://github.com/jmandel/sample_ccdas josh-ccdas/raw
cd josh-ccdas/raw && git checkout 39aab8a882cd166bbbeff7f79995c7f09eb588bc && cd ../..
```

Pinned SHAs are also stored at `_sources/josh-epic-ehi/PINNED-SHA.txt` and `_sources/josh-ccdas/PINNED-SHA.txt`.

### Step 3 — Synthesize the constructed lab PDF (Artifact 5)

```bash
cd ehi-atlas
uv run python corpus/_sources/synthesized-lab-pdf/generator.py
```

Produces `corpus/_sources/synthesized-lab-pdf/raw/lab-report-2025-09-12-quest.pdf`. Deterministic via `SOURCE_DATE_EPOCH=946684800`. Verify integrity:

```bash
md5 -q corpus/_sources/synthesized-lab-pdf/raw/lab-report-2025-09-12-quest.pdf
# expected: cd7124966b5be8b7974684a5bd533b63
```

### Step 4 — (Optional) Acquire personal sources

These are not in the public reproduction path. See per-source READMEs:

- `_sources/blake-cedars/README.md` — SMART-on-FHIR pull via Health Skillz
- `_sources/devon-cedars/README.md` — same workflow, Devon's consent required
- `_sources/cedars-portal-pdfs/README.md` — manual portal download

### Step 5 — (Optional) CMS Blue Button 2.0 sandbox

Requires Blake's sandbox app registration. See `_sources/cms-blue-button/README.md`. After registration:

```bash
# .env file at ehi-atlas/.env
echo "BB_CLIENT_ID=<value>" >> .env
echo "BB_CLIENT_SECRET=<value>" >> .env

uv run ehi-atlas ingest --source blue-button --beneficiary <synthetic-bene-id>
```

### Step 6 — Stage to bronze

```bash
uv run ehi-atlas corpus build
```

This will run the staging sequence for each registered adapter. (Note: as of 2026-04-29 the adapters are not yet implemented — Stage 2 work; this command is currently a stub.)

### Step 7 — Verify

```bash
uv run ehi-atlas corpus status      # shows what's present and missing
make validate-gate                    # privacy-gate check; should print "✓ privacy gate clean"
```

## Pinned showcase fixtures

| Source | Fixture | Notes |
|---|---|---|
| Synthea | `Rhett759_Rohan584_cd64ff18-472b-4d58-b73c-2a04a2bf3e61` | from `~/Repo/ehi-ignite-challenge/data/synthea-samples/synthea-r4-individual/fhir/` |
| Mandel Epic EHI | `db.sqlite.dump` (1.6 MB, 415 SQLite tables, 7,294 rows) | at `_sources/josh-epic-ehi/raw/db.sqlite.dump` |
| Mandel CCDA | `Cerner Samples/Transition_of_Care_Referral_Summary.xml` | 92 KB, 13 sections |
| Synthesized lab PDF | `lab-report-2025-09-12-quest.pdf` | MD5 `cd7124966b5be8b7974684a5bd533b63`, creatinine on `page=2;bbox=72,574,540,590` |
| CMS Blue Button | _pending acquisition (task 1.8)_ | requires sandbox app reg |

The recipe is "anyone can rebuild the open parts; Blake re-runs personal acquisition if they're needed."

## Privacy gate

`make validate-gate` runs `scripts/validate-privacy-gate.sh` which fails the build if:

- Any `_sources/*/raw/` content is staged for commit when the source is `personal`
- Any `bronze/` / `silver/` / `gold/` directory contents are staged for commit (these are reproducible; never commit)
- Any file under a personal source's `raw-redacted/` lacks the marker `# REDACTED via <profile-name>` in its content or filename

The gate runs as a pre-commit hook and as part of `make integrate`.

## Status

See `BUILD-TRACKER.md` Stage 1 for current state of corpus assembly.
