# _sources/josh-epic-ehi/

**Source name (canonical):** `epic-ehi`
**Format:** Epic proprietary TSV → SQLite (`db.sqlite.dump`)
**License:** MIT (claimed in package.json; LICENSE file confirmation pending)
**Consent posture:** `open` (Josh's redacted personal export, public)
**Acquisition mode:** `git clone`

## What this source is

[`jmandel/my-health-data-ehi-wip`](https://github.com/jmandel/my-health-data-ehi-wip) — Josh Mandel's working pipeline against his own redacted Epic EHI Export. Contains:

- ~1.7 MB redacted SQLite dump (`db.sqlite.dump`) generated from a real Epic EHI Export
- 552 raw TSV table schemas
- 6,631 per-table JSON schemas
- Numbered pipeline scripts `00-redact.js`, `01-make-json.js`, `02-merge-related-tables.ts`, `03-split-files.ts`, `04-codegen.ts`, `05-sqlite.ts`

We use this source to **validate our parser against real Epic EHI shape**. We do NOT use the patient content as our showcase patient — that work is done in the synthesized projection of the Synthea ground-truth patient into Epic-EHI shape.

## How to acquire

```bash
cd ehi-atlas/corpus/_sources/josh-epic-ehi/
gh repo clone jmandel/my-health-data-ehi-wip raw --depth 1
# or:
git clone --depth 1 https://github.com/jmandel/my-health-data-ehi-wip.git raw

# Document the SHA we pinned to:
cd raw && git log -1 --pretty=format:"%H %ad %s%n" >> ../PINNED-SHA.txt
```

## Reproduction recipe

Cloned at depth=1 with the SHA pinned in `PINNED-SHA.txt`. Subsequent re-clones must verify the same SHA or document the upgrade in `mapping-decisions.md`.

## Why we use this source

Three things this source gives us that nothing else in the public landscape provides:

1. **A real Epic EHI Export** (redacted) — we can develop our adapter against actual data shape, not a spec
2. **Josh's heuristic table-merge logic** in `02-merge-related-tables.ts` — non-trivial reverse engineering we lift verbatim into our `epic_ehi.py` adapter
3. **The schema corpus** — 6,631 schemas serve as the input to our LLM-bootstrapped Epic-table → FHIR-resource crosswalk (see `docs/CROSSWALK-WORKFLOW.md`)

## License confirmation status

Josh's `package.json` declares `"license": "MIT"` but no `LICENSE` file is in the repo. License confirmation is on the Day-1 Josh email checklist (D4 in BUILD-TRACKER).

## Privacy gate

Josh's data is already redacted; the published repo is intentionally public. No additional privacy gate needed at our boundary. We use his pipeline + schemas, not his patient identity.

## Contents of this directory

```
_sources/josh-epic-ehi/
├── README.md           # this file
├── PINNED-SHA.txt      # the git SHA we cloned (written by 1.3)
├── INSPECTION.md       # what's in the SQLite dump (written by 1.6)
└── raw/                # the cloned repo (gitignored at commit time? no — public source)
    └── ...
```

## Used in tracker tasks

- **1.3** Clone Mandel's repos to `_sources/josh-*/raw/`
- **1.6** Inspect Josh's Epic SQLite dump
- **2.3** Epic EHI TSV adapter (lift Mandel's heuristics)
- **2.7** Build-time crosswalk: Epic table → FHIR resource
