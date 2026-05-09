# _sources/synthetic-pdf-fixtures/

**Source name (canonical):** `synthetic-pdf-fixtures`
**Format:** PDF fixtures generated from synthetic plaintext sources
**License:** Constructed (MIT-redistributable)
**Consent posture:** `constructed`
**Acquisition mode:** Generated locally from committed synthetic text

## What this source is

This directory contains small, deliberately different synthetic PDF fixtures for
EHI Atlas PDF-to-FHIR extraction tests. Subagents should generate differing PDFs
when testing PDF ingestion because one "clean lab report" only validates the
happy path. The fixtures here cover separate extraction failure modes:

1. Corrected lab report: amended values should override earlier preliminary values.
2. Medication reconciliation: active medications, held medications, and stopped
   medications must not be collapsed into one undifferentiated list.
3. Radiology report with page noise: headers, footers, and family-history language
   must not be extracted as patient findings.

These are not meant to replace the existing showcase Quest-style lab PDF. They are
small regression fixtures for adapter and LLM prompt tests.

## Directory layout

```
synthetic-pdf-fixtures/
├── README.md
├── manifest.json
├── expected-facts.json
├── sources/
│   ├── corrected-lab-report.txt
│   ├── medication-reconciliation.txt
│   └── radiology-report-page-noise.txt
└── raw/
    ├── corrected-lab-report.pdf
    ├── medication-reconciliation.pdf
    └── radiology-report-page-noise.pdf
```

## Regeneration

The PDFs were generated from the plaintext sources with macOS `cupsfilter`:

```bash
cupsfilter sources/corrected-lab-report.txt > raw/corrected-lab-report.pdf
cupsfilter sources/medication-reconciliation.txt > raw/medication-reconciliation.pdf
cupsfilter sources/radiology-report-page-noise.txt > raw/radiology-report-page-noise.pdf
```

No patient data is real. All names, identifiers, accessions, facilities, and
clinical facts are synthetic.
