# _sources/josh-ccdas/

**Source name (canonical):** `ccda`
**Format:** HL7 CDA R2 XML
**License:** CC BY 4.0 (per repo README)
**Consent posture:** `open` (PHI-free vendor fixtures)
**Acquisition mode:** `git clone`

## What this source is

[`jmandel/sample_ccdas`](https://github.com/jmandel/sample_ccdas) — 747 PHI-free C-CDA documents across ~12 vendors, the de-facto open C-CDA corpus. Vendors include Allscripts (3 product lines), Cerner, Greenway, Kareo, Kinsights, NextGen, NIST, Partners HealthCare, PracticeFusion, Vitera, mTuitive, EMERGE.

## How to acquire

```bash
cd ehi-atlas/corpus/_sources/josh-ccdas/
gh repo clone jmandel/sample_ccdas raw --depth 1
# or:
git clone --depth 1 https://github.com/jmandel/sample_ccdas.git raw

cd raw && git log -1 --pretty=format:"%H %ad %s%n" >> ../PINNED-SHA.txt
```

## Reproduction recipe

Cloned at depth=1, SHA pinned. Repo last updated 2018 — frozen but evergreen.

## Showcase fixture selection criteria

We use **one CCDA fixture** for the showcase patient, picked to:

- Match the showcase patient's clinical profile (active conditions, similar age range)
- Represent a transition-of-care document (i.e., the kind of document a patient receives when seeing a new specialist)
- Be from a vendor representative of real-world clinical exchange (Cerner or Epic-flavored)
- Have rich enough content (problems list + medications + recent encounters) to demonstrate the deterministic CCDA → FHIR conversion path

The chosen fixture is documented in `CHOSEN.md` (written by sub-agent task 1.7).

## Why we use this source

CCDA is the predecessor format to FHIR R4 and is still the dominant exchange format for transition-of-care documents in real clinical workflows. Including a CCDA in the showcase patient demonstrates the **Path A (deterministic) standardization** alongside the vision-extraction path — using the Microsoft FHIR-Converter to convert CCDA XML to FHIR R4 Bundles.

## Privacy gate

Not applicable — repo is intentionally PHI-free and published as public sample data.

## Contents of this directory

```
_sources/josh-ccdas/
├── README.md           # this file
├── PINNED-SHA.txt      # the git SHA we cloned (written by 1.3)
├── CHOSEN.md           # which fixture is the showcase + why (written by 1.7)
└── raw/                # the cloned repo
    └── ...
```

## Used in tracker tasks

- **1.3** Clone Mandel's repos to `_sources/josh-*/raw/`
- **1.7** Inspect Josh's CCDA fixtures (pick one matching showcase)
- **2.4** CCDA adapter (subprocess FHIR-Converter)
