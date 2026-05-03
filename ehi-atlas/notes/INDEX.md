# Index — Josh Mandel Stack Deep Dive

This study is split into **three swim lanes**. Each lane has its own session ledger and progresses independently. The shared kickoff (Session 00) sits above all three.

## Lanes

| Lane | What it covers | Status | Index |
|---|---|---|---|
| **Data** | Data pipelines, data structures, schemas, transformations, FHIR / EHI-TSV / SQLite materialization, redaction model, skill-bundle output format | 🟢 active — start here | [`data-lane/INDEX.md`](data-lane/INDEX.md) |
| **App** | React UI, SMART OAuth + PKCE, asymmetric client assertion, ECDH/AES crypto, MCP transports, in-browser Babel agent | ⏸ deferred until data lane lands | [`app-lane/INDEX.md`](app-lane/INDEX.md) |
| **Skill demo** | Hands-on walkthrough of the Claude skill Blake downloaded — install, run, inspect outputs, adapt | 🟢 parallel track, Blake-driven | [`skill-demo/INDEX.md`](skill-demo/INDEX.md) |

## Shared artifacts (within this directory)

- [`session-00-lay-of-the-land.md`](session-00-lay-of-the-land.md) — repo-by-repo inventory + dependency graph. Read once, applies to all three lanes.
- [`SHAS-PINNED.md`](SHAS-PINNED.md) — pinned commits all study sessions read against.
- [`GLOSSARY.md`](GLOSSARY.md) — unified term/acronym dictionary across all lanes, append-only.

## Sibling working directories under `data-research/`

- [`../datamart/`](../datamart/) — central data store: inputs (Synthea, EHI samples, vendor catalog), intermediates (regeneratable), schemas. **Read before D01.**
- [`../prototypes/`](../prototypes/) — code that reads/writes the datamart. `josh-…/` ports replay Josh's pipelines; `atlas-…/` experiments build Atlas's harmonization layer.

The split: this directory holds **qualitative study notes**; `datamart/` holds **data**; `prototypes/` holds **code**.

## Session-arc revisions

- **2026-05-01** — initial single-arc plan (11 sessions covering everything in sequence).
- **2026-05-01** — restructured into three swim lanes after Blake's redirect: data depth comes first, app/frontend mechanics deferred, skill demo split out as its own hands-on track. The original 11-session arc is retired in favor of the per-lane arcs in `data-lane/`, `app-lane/`, `skill-demo/`.
- **2026-05-01** — proposed merging Sessions 02 and 03 of the old arc — moot under the new structure (those become App lane A2/A3).
- **2026-05-01** — added explicit subtask to diff `health-record-mcp/clientFhirUtils.ts` against `health-skillz/src/client/lib/smart/*.ts`. Now lives in App lane A2.

## How to drive this

- "advance the data lane" → run the next session in `data-lane/INDEX.md`
- "advance the app lane" → run the next session in `app-lane/INDEX.md`
- "demo time" / "let's run the skill" → open `skill-demo/INDEX.md`
- Out-of-sequence questions are fine — answer briefly, then resume the active lane.
