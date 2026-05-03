# _sources/cms-blue-button/

**Source name (canonical):** `blue-button`
**Format:** FHIR R4 with CARIN BB profiles (synthetic Medicare claims)
**License:** Open / public-use
**Consent posture:** `open` (synthetic beneficiaries from CMS sandbox)
**Acquisition mode:** OAuth + REST API

## What this source is

[CMS Blue Button 2.0 sandbox](https://bluebutton.cms.gov/) — Centers for Medicare & Medicaid Services API providing synthetic Medicare claims data in FHIR R4 with CARIN BB profiles. ~30 sample beneficiaries with multi-year claim histories.

This source unlocks the **payer workflow scenario** (one of the EHI Ignite challenge's five scenarios) by giving us claims-side data alongside the clinical FHIR data.

## How to acquire

### One-time: register a sandbox app

1. Go to https://sandbox.bluebutton.cms.gov/v2/accounts/login
2. Create a developer account (free, self-service)
3. Register a new application:
   - Name: `EHI Atlas (development)`
   - Type: Confidential client
   - Redirect URI: `http://localhost:8000/callback` (or appropriate)
4. Save the issued `client_id` and `client_secret`

### Per-acquisition: pull a beneficiary

```bash
# Configure credentials
echo "BB_CLIENT_ID=<id>" >> ../../../../.env
echo "BB_CLIENT_SECRET=<secret>" >> ../../../../.env

# Pull a sample beneficiary
uv run ehi-atlas ingest --source blue-button --beneficiary <synthetic-bene-id>
```

The synthetic beneficiary IDs are listed at https://bluebutton.cms.gov/developers/#sample-beneficiaries.

## Reproduction recipe

Anyone with a sandbox app can pull the same synthetic beneficiaries. The chosen beneficiary ID is documented in `CHOSEN.md` (written by task 1.8) along with the OAuth token snapshot info.

## Showcase beneficiary selection criteria

The selected synthetic beneficiary must have:

- Multi-year claim history (≥3 years of claims)
- Mix of Part A (institutional) + Part B (professional) + Part D (pharmacy) claims
- At least one Part D claim that creates Artifact 3 (the orphan: claim shows fill not in clinical FHIR)
- Active diagnoses overlapping with showcase Synthea patient's conditions

## Why we use this source

Three things claims data adds:

1. **Payer-side perspective** — the patient's care viewed through what the insurer paid for, often diverging from what's in the clinical record
2. **Pharmacy fill history** — Part D claims expose actual medication fills, supporting the medication-reconciliation scenario
3. **The orphan artifact** — Artifact 3 in the showcase patient is a statin fill visible only in BB claims, demonstrating cross-source asymmetry

## Privacy gate

Not applicable — synthetic beneficiaries from CMS sandbox.

## Contents of this directory

```
_sources/cms-blue-button/
├── README.md              # this file
├── CHOSEN.md              # which beneficiary is the showcase + why (written by 1.8)
└── raw/                   # OAuth-pulled FHIR JSON
    └── <beneficiary-id>/
        ├── ExplanationOfBenefit.json
        ├── Coverage.json
        └── Patient.json
```

## Used in tracker tasks

- **1.5** CMS Blue Button 2.0 sandbox app registration (Blake)
- **1.8** BB sandbox: pull a sample beneficiary
- **2.2** CMS Blue Button adapter (CARIN BB profiles)
