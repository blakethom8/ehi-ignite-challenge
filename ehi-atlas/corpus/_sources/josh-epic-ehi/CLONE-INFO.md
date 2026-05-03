# Clone Info: josh-epic-ehi

**Cloned:** 2026-04-28  
**Source:** https://github.com/jmandel/my-health-data-ehi-wip

## SHA Pinned

```
188d93814515636afd9f027f2d5efebfd00260c7
```

**Commit Date:** 2026-01-02  
**Commit Message:** Merge pull request #13 from jmandel/copilot/fix-open-router-api-calls

## Inventory

- **Total Files:** 7,685
- **Disk Size:** 62 MB
- **Top-level Directories:**
  - `example-analysis/` — exploratory analysis scripts
  - `json/` — generated JSON schemas (6,631 total)
  - `schemas/` — TSV table schema definitions
  - `src/` — source pipeline scripts (JavaScript/TypeScript)
  - `tsv/` — raw TSV extracts (552 tables)

## License Status

**License Field:** MIT (declared in `package.json`)  
**LICENSE File:** NOT present in repository root  
⚠️ **Note:** Josh's README states intent to make this available under MIT, but no physical LICENSE file was included at clone time. The package.json declaration is sufficient for open licensing, but a file-based LICENSE would be cleaner.

## Key Contents

- **Redacted Epic EHI Export:** ~1.7 MB SQLite dump (`db.sqlite.dump`)
- **Table Merge Logic:** `02-merge-related-tables.ts` — non-trivial reverse engineering for table relationships
- **Pipeline Scripts:** `00-redact.js` → `05-sqlite.ts` (numbered pipeline)
- **Generated Schemas:** 6,631 JSON schemas from 552 TSV table templates

## README Summary (First 5 lines)

```
# EHI Export: Data Exploration

Welcome to the EHI Data Exploration repository! This project is an individual exploration by Josh Mandel, aimed at creating components that others can try and learn from in the context of electronic health information (EHI) data. It focuses on processing EHI Export data from Epic, which users can request from their health care provider.

## Project Overview
```

## Unusual Notes

None observed. Repo is clean and actively maintained (last commit Jan 2026). Well-organized with clear separation of raw data, schemas, and pipeline logic.
