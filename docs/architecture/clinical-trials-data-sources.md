# Clinical Trial Data Sources

Last updated: 2026-05-09

This workspace should be API-first. Scraping is a fallback only when a public
source lacks a usable API/export, and every fetched record should keep source
URL, access timestamp, registry id, and enough raw payload to audit what the
agent saw.

## Product Contract

The Trial Finder agent is not a one-shot search form. It manages a clinical
trial pursuit:

1. Search official registries from patient/chart anchors.
2. Show candidate trials in the canvas.
3. Let the clinician track trials into a durable pursuit board.
4. Review eligibility gaps against patient evidence.
5. Prepare packet tasks and outreach notes.
6. Track contact, submission, follow-up, and closure.

## Source Tiers

### Tier 1 — Structured Registry APIs

- **ClinicalTrials.gov API v2** — primary US/global source for NCT studies.
  Use `/api/v2/studies` and `/api/v2/studies/{nctId}`.
  Source: https://clinicaltrials.gov/data-api/about-api
- **NCI Clinical Trials Search API** — cancer-specific API backed by NCI CTRP.
  Use for oncology trials and NCI-network context not always visible in the
  same shape on ClinicalTrials.gov.
  Source: https://www.cancer.gov/syndication/api
- **WHO ICTRP Search Portal / Web Service** — global registry aggregation and
  bridged records across primary registries.
  Source: https://www.who.int/tools/clinical-trials-registry-platform/the-ictrp-search-portal
- **EU CTIS public website** — EU/EEA public trial records from CTIS.
  Source: https://www.ema.europa.eu/en/human-regulatory-overview/research-development/clinical-trials-human-medicines/clinical-trials-information-system

### Tier 2 — Registry Exports And Specialty Registries

- ISRCTN, ANZCTR, jRCT/JPRN, UMIN-CTR, DRKS, ChiCTR, ReBEC, CRiS, IRCT, and
  other WHO primary registries.
- Pull through ICTRP when possible, then fall back to registry-specific APIs or
  exports where permitted.

### Tier 3 — Trial Context Sources

- Sponsor trial pages.
- Academic medical center trial pages.
- Disease-foundation and advocacy-group trial finders.
- PubMed publications tied to NCT IDs.
- Site/coordinator pages.

These enrich trial pursuit work, but they should not override registry facts
without preserving provenance.

## Data Model Implications

Every candidate or pursuit should preserve:

- canonical registry id (`nct_id` when present, plus registry-specific ids),
- title, sponsor, recruitment status, phase, conditions, interventions,
- eligibility text and parsed inclusion/exclusion lines,
- location/site/contact data,
- source URL, source kind, access timestamp, and source update timestamp,
- fit score and chart-evidence snapshot,
- pursuit state, tasks, events, and closure reason.

## Match Dimensions

The agent should not treat "match" as a single score. It should separate at
least three dimensions:

### Clinical Fit

- disease state, phenotype, stage, severity, and recurrence status,
- biomarkers, genetic markers, pathology, and imaging requirements,
- age, sex, pregnancy status, ECOG/performance status when available,
- comorbidities and active problem-list exclusions,
- recent labs, vitals, organ-function thresholds, and treatment history.

### Operational Fit

- recruitment status and site availability,
- geography, travel burden, remote/hybrid options, and visit cadence,
- expected duration and follow-up length,
- intervention burden, procedures, biopsies, imaging, and lab frequency,
- placebo/randomization considerations and patient effort required.

### Pursuit Fit

- enrollment size and how constrained the cohort appears,
- sponsor/site contactability and coordinator availability,
- packet/document requirements,
- missing facts that block outreach,
- submission status, follow-up tasks, and closure reason.

## Guardrails

- Do not send PHI to third-party registries unless explicitly authorized.
- Query registries with condition/search terms derived from the chart, not raw
  patient identifiers.
- Use official APIs/export feeds before scraping.
- If scraping is required, store URL, timestamp, hash/raw payload, and a parser
  version; respect access limits and terms.
- Outreach/submission actions must be explicit clinician actions, not automatic
  background sends.
