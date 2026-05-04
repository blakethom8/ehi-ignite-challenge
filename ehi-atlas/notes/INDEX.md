# Notes — Josh Mandel Stack Deep Dive

Qualitative study notes for the Josh Mandel stack (FHIR pipelines, EHI-TSV
materialization, redaction model, skill-bundle output format). The original
three-lane structure (data / app / skill-demo) was simplified in May 2026 —
only the **data lane** stays active here. The deferred app and skill-demo
lanes were archived under
[`../../archive/ehi-atlas-5layer/notes/`](../../archive/ehi-atlas-5layer/notes/).

## Active

- [`data-lane/INDEX.md`](data-lane/INDEX.md) — data pipelines, data structures,
  schemas, transformations, FHIR / EHI-TSV / SQLite materialization,
  redaction model, skill-bundle output format.

## Shared artifacts in this directory

- [`session-00-lay-of-the-land.md`](session-00-lay-of-the-land.md) — repo-by-repo
  inventory + dependency graph. Read once.
- [`SHAS-PINNED.md`](SHAS-PINNED.md) — pinned commits all study sessions read
  against.
- [`GLOSSARY.md`](GLOSSARY.md) — unified term/acronym dictionary, append-only.

## Where the related code/data live

- **Data:** `../corpus/` — `_sources/` (raw drops), `bronze/` (canonical staging),
  `reference/` (terminology snapshots).
- **Code:** `../ehi_atlas/extract/` — the live PDF→FHIR extraction framework.

The original `prototypes/` (Josh-stack ports) and `datamart/` (data store)
folders were never built out as planned and have been archived.
