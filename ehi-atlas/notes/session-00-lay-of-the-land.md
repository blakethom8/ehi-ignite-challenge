# Session 00 — Lay of the Land

**Repos pinned:** see `SHAS-PINNED.md`. Four core repos cloned to `/tmp/josh-stack/`.
**Files visited (count):** ~20 (entry points + manifests, not deep walks)
**Reading time estimate:** ~15 minutes
**Built on prior sessions:** none — this is the kickoff.
**Prior dossier consulted:** `~/Chief/20-projects/ehi-ignite-challenge/research/josh-mandel/notes/github-inventory.md` (Chief vault, dated 2026-04-28). That note already has the high-level read; this session **verifies it against the pinned SHAs and lays the spine for the next ten sessions**.

## What you'll learn

- The four core repos cohere into a **three-stage patient-data pipeline**: request → connect/extract → analyze. Each stage is shippable independently, and Josh has been migrating the stack from MCP-over-the-wire toward Anthropic-Skill-bundled-on-disk.
- The **SMART-on-FHIR client lives in two places** (an old monolith in `health-record-mcp/clientFhirUtils.ts` and a refactored modular form in `health-skillz/src/client/lib/smart/`). The lineage is the single most informative diff in the stack.
- The **Anthropic Skill format** is the unifying packaging convention across `request-my-ehi` and `health-skillz` (and `write-clinical-notes.skill`). MCP is being phased toward a smaller role.
- Josh's stack is **runtime-light, build-time-heavy**: lots of TypeScript scripts, almost no server-side state, with the work pushed into either the browser (web crypto, SQLite-WASM, Babel-in-the-page) or the LLM (eval-record, generated React components).
- He **deliberately does not merge sources**. Every patient-source slice is preserved as a discrete bundle. That's a defensible aesthetic choice and the most important contrast point for the EHI Atlas thesis (which *is* a merge layer).

## The code in scope

Top-level inventory only — no deep walks. We touch:

- `health-skillz/{src/server.ts, package.json, src/client/lib/, skill/build-skill.ts, skill/partials/header.md}`
- `health-record-mcp/{package.json, src/tools.ts (header only), ehretriever.ts (head), src/}`
- `my-health-data-ehi-wip/{package.json, 00-redact.js…08-generate-short-descriptions.ts, src/agent.ts (existence)}`
- `request-my-ehi/{SKILL.md, scripts/, templates/, server/, site/skill.zip}`

Per-file deep walks happen in Sessions 01–09.

## Walkthrough

### 1. `health-skillz` — the current flagship

**Pinned SHA:** `a7fd8acf`. **Stack:** Bun + React 19 + TypeScript, Zustand, react-router 7, JSZip, dompurify, rtf.js. **No backend framework** — Bun's native fullstack server in a single 1066-line `src/server.ts` that imports `./index.html` directly (`import homepage from "./index.html"`, server.ts:6).

What it does, in one paragraph from reading code (not the README): a Bun server hosts a React SPA that does SMART App Launch in-browser against patient portals (Epic prod + sandbox today), pulls a per-source FHIR bundle into IndexedDB, lets the user run a non-destructive redaction studio over the bundle, and then emits the data to Claude in one of two ways — either (a) **agent mode** by uploading ECDH-encrypted chunks to a session-bound endpoint that Claude reaches via a server-side skill, or (b) **local mode** by JSZip-bundling the redacted JSON next to a `SKILL.md` and handing the user a ZIP they upload to Claude themselves. Server stores ciphertext only; the trust model leans hard on the browser.

**Top-level layout** (verified by `ls`):

```
health-skillz/
├── src/
│   ├── server.ts                      # 1066 lines, the entire backend
│   ├── index.html
│   └── client/
│       ├── components/, pages/, store/  # React UI
│       └── lib/
│           ├── smart/                  # SMART OAuth client
│           │   ├── oauth.ts
│           │   ├── client.ts
│           │   ├── client-assertion.ts # asymmetric assertion (JWT-signed)
│           │   ├── launch.ts
│           │   └── attachments.ts
│           ├── api.ts, connections.ts
│           ├── crypto.ts               # ECDH + AES-GCM chunked upload
│           ├── redaction.ts            # variant-cluster redaction profile
│           ├── skill-builder.ts        # JSZip → local-skill.zip
│           ├── storage.ts              # IndexedDB
│           └── brands/                 # FHIR endpoint registry
└── skill/
    ├── build-skill.ts                  # concatenates partials → SKILL.md
    ├── partials/                       # 9 ordered Markdown fragments
    │   ├── header.md (frontmatter)
    │   ├── when-to-use.md
    │   ├── analysis-philosophy.md
    │   ├── connect-agent.md / connect-local.md
    │   ├── data-structure.md
    │   ├── fhir-guide.md (USCDI cookbook)
    │   ├── guidelines.md
    │   └── testing.md
    └── health-record-assistant/        # references/ + scripts/
```

**Dependencies actually used heavily** (per `package.json` + 30 seconds of grepping):

- `jszip` — local-skill ZIP construction.
- `dompurify` — sanitizing HTML attachments before they reach Claude/the user.
- `rtf.js` — converting RTF attachments (Epic ships these for old chart notes) into plaintext.
- `zustand` — UI state, including the redaction profile.
- `react-router-dom@7` — `/records/*` (standalone) vs `/connect/:sessionId` (AI session) split.
- `bun:sqlite`, `bun`'s native `Database`, and Web Crypto APIs — server-side persistence and key handling. **Note: no Express, no Hono, no Fastify** — `Bun.serve`-style routing inline in `server.ts`.

**License:** README claims MIT, but **no LICENSE file ships in the repo**. Mild redistribution risk if you copy code out wholesale. (Safe to study; ask Josh before vendoring.)

**Design philosophy this teaches us:** Josh treats the browser as the trusted boundary. The server is a dumb relay for ciphertext + an authoritative copy of the brand registry. The "skill" format lets him hand off work to Claude without running an agent backend himself. He's optimizing for *zero ongoing operational cost*.

### 2. `health-record-mcp` — the predecessor

**Pinned SHA:** `e4b03bd1`. **Stack:** Bun + TypeScript, `@modelcontextprotocol/sdk@^1.13.1`, Express 5, zod, pkce-challenge, html-to-text, rtf.js, fast-xml-parser, `bun:sqlite`, `vm` (sandboxed eval).

**31,572 LOC** across 142 TS/JS/MD/JSON files (largest of the four by code volume). Top-level — note the **flat layout**: critical files like `clientFhirUtils.ts` (741 lines) and `ehretriever.ts` (1201 lines) live in the repo root, not under `src/`. That's an early-prototype code-shape, not a deliberate architectural statement.

```
health-record-mcp/
├── ehretriever.ts             # 1201 — browser SMART client, postMessage to opener
├── clientFhirUtils.ts         # 741  — fetchAllEhrDataClientSideParallel
├── clientTypes.ts             # ClientFullEHR shape
├── opener.html
├── intrabrowser/              # postMessage MCP transport (705 lines)
├── src/
│   ├── tools.ts               # 1148 — registerEhrTools (5 MCP tools)
│   ├── fhirToPlaintext.ts     # 1513 — per-resource-type renderer
│   ├── cli.ts                 # 449  — local stdio MCP
│   ├── sse.ts                 # 548  — SSE MCP
│   ├── oauth.ts               # 951  — OAuth 2.1 dynamic-client-reg
│   ├── http.ts, dbUtils.ts, sessionUtils.ts, types.ts, …
│   └── tools-browser-entry.ts # bundled with `bun build` for the in-browser variant
├── a4a/                       # embedded Agent-to-Agent submonorepo (tangential)
├── static/brands/             # FHIR endpoint registry — same format as health-skillz
└── LICENSE.txt                # MIT, present
```

**The five MCP tools** (verified in `src/tools.ts:1022` `registerEhrTools`):

```
grep_record       — substring/regex search across resource bodies
query_record      — SQL against bun:sqlite-flattened FHIR
eval_record       — sandboxed JS via Node's vm module, with ClientFullEHR in scope
read_resource     — fetch a single FHIR resource by reference
read_attachment   — fetch a single Binary/DocumentReference attachment
```

The `getContext` callback is pluggable across **three transports**: stdio (Cursor / Claude Desktop), SSE (`src/sse.ts` + OAuth), and `IntraBrowserTransport` (postMessage between two windows on the same origin — clever, lets the MCP server live entirely in the user's browser).

**License:** MIT, with a real `LICENSE.txt`. Cleanest reuse story of the four.

**Design philosophy this teaches us:** Josh first tried "expose record data via MCP tools the LLM calls at runtime." The toolset is well chosen — `grep` + `SQL` + `eval` covers most analysis patterns — but operating an MCP server is a non-trivial substrate. The migration from this repo to `health-skillz` is a step *away from runtime tool-calls and toward bundled-on-disk*: same retrieval semantics, packaged so Claude doesn't need an external server.

### 3. `my-health-data-ehi-wip` — the Epic EHI lab

**Pinned SHA:** `188d9381`. **Stack:** Vite + React 18 + TS, `@sqlite.org/sqlite-wasm`, `@babel/standalone` (in-browser JSX compilation), OpenAI SDK pointed at OpenRouter, d3, lodash. **MIT** declared in `package.json`; no LICENSE file.

**The whole repo is two halves**:

**Half A — the numbered build pipeline** (TSV → JSON → JSON-cluster → TS → SQLite, plus LLM annotation passes):

```
00-redact.js                       (52 lines)   regex-based PHI scrubber
01-make-json.js                    (142 lines)  TSV → schema-validated JSON
02-merge-related-tables.ts         (523 lines)  ★ heuristic logical-table inference
03-split-files.ts                  (87 lines)   per-table JSON split
04-codegen.ts                      (4 lines)    delegates to src/codegen.ts (TS interfaces/classes/proxies)
05-sqlite.ts                       (309 lines)  ★ schema + bulk load
06-sample-rows.ts                  (45 lines)
07-sample-table-clusters.ts        (156 lines)
08-generate-short-descriptions.ts  (103 lines)  LLM-assisted one-line table summaries
```

`02-merge-related-tables.ts` is the crown jewel — Epic ships ~552 raw TSV tables that fragment what users would think of as a single "logical table" (e.g., one logical "encounter" splits across 6+ physical TSVs). Josh's heuristic merges them. **This is non-trivial reverse engineering of an unpublished Epic schema.**

**Half B — the in-browser app** (`src/`):

- `agent.ts` — multi-task agent with three named "guides": `TableExtraction`, `DataAnalysis`, `DevelopReactComponent`. Wired to OpenRouter via the OpenAI SDK.
- `EhiNavigator.tsx`, `EhiView.jsx`, `EhiComp.jsx` — UI for paging through the SQLite-WASM-backed dump.
- `@babel/standalone` — Claude (well, OpenRouter) generates a JSX React component, the page compiles + renders it live. This is **the agent-generates-UI pattern**, three years before it became fashionable.

**Scale numbers (from the working tree):**

```
schemas/   — ~6,631 per-table JSON schemas (one per Epic table)
tsv/       — 552 raw tables
json/      — 414 processed files
db.sqlite.dump — 1.7 MB redacted personal fixture (Josh's own EHI Export, redacted)
```

**Design philosophy this teaches us:** the gap between FHIR-shaped data and Epic-EHI-shaped data is *enormous*. FHIR gives you a few dozen well-known resource types; Epic EHI gives you 6000+ schemas across 552 physical tables and expects you to figure out the relations yourself. Josh's bet here is that LLM-annotated table samples (`07`/`08`) are good enough to navigate that complexity at human + agent speed. **No `SKILL.md`** — this repo predates the skill-format consolidation in the rest of the stack.

### 4. `request-my-ehi` — the upstream skill

**Pinned SHA:** `fd0a8cd8`. **Apache-2.0**, real LICENSE file. The cleanest license of the four.

This is the *patient onboarding* step — generates a paper packet (cover letter + ROI form + vendor-specific Appendix A) the patient mails or faxes to their provider to obtain an EHI Export. Layout:

```
request-my-ehi/
├── SKILL.md              ← canonical Anthropic-Skill frontmatter (see below)
├── scripts/              ← Bun TS scripts the skill invokes
│   ├── generate-cover-letter.ts
│   ├── generate-appendix.ts        (vendor-specific Appendix A)
│   ├── build-right-of-access-form.ts
│   ├── fill-and-merge.ts           (PDF assembly via pdf-lib)
│   ├── send-fax.ts, check-fax-status.ts
│   ├── lookup-vendor.ts
│   └── create-signature-session.ts, poll-signature.ts
├── templates/
│   ├── appendix.pdf, cover-letter.pdf
│   ├── right-of-access-form.pdf, right-of-access-form.tex
│   └── drivers-license-page.md
├── server/ (Dockerfile + a small relay)
├── site/skill.zip        ← pre-built ZIP for distribution
└── tests/
```

**The `SKILL.md` frontmatter** — this is the canonical Anthropic-Skill shape, repeated in `health-skillz`:

```yaml
---
name: request-my-ehi
description: Help a patient request their complete Electronic Health Information (EHI) Export from their healthcare provider. Supports Epic and 70+ other certified EHR vendors. […]
argument-hint: [provider-name]
allowed-tools: Read, Write, Edit, Glob, Grep, Bash, WebFetch, WebSearch, Task
---
```

`allowed-tools` is the field that makes Claude Code accept this as a runnable skill. **Note `request-my-ehi` ships a ready-built `skill.zip` in `site/`** — that's the artifact users install. We'll dissect this in Session 01.

**Design philosophy this teaches us:** Josh treats *patient agency* as the real entry point. Before any FHIR pull, the patient first needs the right paper packet to even get the EHI Export. The skill is essentially a paperwork compiler with vendor-aware conditionals. The fact that it's its own repo signals he sees onboarding as a separable module from analysis.

## Repo-level dependency graph (ASCII)

```
                  ┌───────────────────────────┐
                  │    request-my-ehi         │  Apache-2.0
                  │  (Anthropic Skill)        │  generates PDF
                  │   templates + scripts     │  packet to mail/fax
                  └────────────┬──────────────┘
                               │ patient receives EHI Export
                               │ (Epic TSV bundle, hundreds of files)
                               ▼
        ┌─────────────────────────────────────────────────────┐
        │                                                     │
        │   ┌────────────────────────┐                        │
        │   │ my-health-data-ehi-wip │   Vite + sqlite-wasm   │
        │   │  (TSV → SQLite + UI)   │   in-browser agent     │
        │   │                        │   ★ no SKILL.md        │
        │   └────────────────────────┘                        │
        │                                                     │
        │   The Epic-EHI bulk path                            │
        └─────────────────────────────────────────────────────┘

                               OR (alternative pull path)

        ┌─────────────────────────────────────────────────────┐
        │   ┌────────────────────────┐                        │
        │   │ health-record-mcp      │   Bun + MCP SDK        │
        │   │  (SMART pull → MCP)    │   5 tools: grep/query/ │
        │   │  predecessor of skillz │   eval/read_resource/  │
        │   │                        │   read_attachment      │
        │   └────────┬───────────────┘                        │
        │            │ SMART client refactored & moved        │
        │            │ ───────────────────────►               │
        │   ┌────────▼───────────────┐                        │
        │   │ health-skillz          │   Bun + React + Skill  │
        │   │  (SMART pull → Skill)  │   • SMART OAuth client │
        │   │  current flagship      │   • Redaction studio   │
        │   │                        │   • E2E-encrypted upl. │
        │   │                        │   • SKILL.md generator │
        │   └────────────────────────┘                        │
        │                                                     │
        │   The SMART-pull path (FHIR APIs, not bulk TSV)     │
        └─────────────────────────────────────────────────────┘

  Shared substrate that flows through everything Josh ships:
  ─────────────────────────────────────────────────────────
  •  Brand directory (static/brands/*.json) — same format in mcp & skillz
  •  Anthropic-Skill packaging — request-my-ehi & health-skillz both ship SKILL.md
  •  rtf.js + html-to-text + dompurify — the attachment-to-plaintext stack
  •  bun:sqlite or sqlite-wasm — flatten FHIR for query, in-process
```

**Two clear lineages worth naming up front for Sessions 02 + 10:**

1. **The SMART client lineage.** `health-record-mcp/clientFhirUtils.ts` (741 lines, monolithic) was refactored into `health-skillz/src/client/lib/smart/{oauth,client,client-assertion,launch,attachments}.ts` (5 files, modular). Same protocol semantics, different code shape. Sessions 02 and 10 both touch this.
2. **The retrieval-tool lineage.** `health-record-mcp` exposes retrieval as **MCP tools** (`grep_record`, `query_record`, `eval_record`, `read_resource`, `read_attachment`) that Claude calls at runtime. `health-skillz` collapses this to **"write everything to disk + bundle FHIR cookbook into `SKILL.md`"** — Claude does the same operations using its own Read/Bash/Grep tools instead of MCP tools. Same conceptual moves, less infrastructure.

## Architectural decisions worth flagging (preview)

These are the calls Josh made that I want to come back to in later sessions. For each: (a) what he chose, (b) the alternative, (c) why his choice probably won.

- **Browser-only crypto + ciphertext-only server.** (a) The browser holds the trust boundary; the server stores ciphertext and never sees plaintext records. (b) Server-side TLS termination + at-rest encryption. (c) His choice makes the privacy story trivially auditable and removes any HIPAA-BAA conversation about the relay. **Session 06.**
- **Skill-bundle-on-disk over MCP-tools-over-the-wire.** (a) `SKILL.md` + scripts + JSON in a directory the LLM reads from disk. (b) MCP server with `query_record` etc. (c) Skill is operationally free; Anthropic Skills lock in distribution; users don't need to run a server. **Sessions 01, 05, 07.**
- **Per-source preserved bundles, no merge.** (a) Every fetched provider produces an independent `data/<provider>.json`. (b) A single harmonized cross-provider record. (c) Preservation is honest and keeps provenance trivially intact; merge is open-ended and has no "done" state. **This is the most consequential choice for EHI Atlas — Blake's wedge sits exactly in the gap Josh deliberately left open. Session 10.**
- **Concatenated `SKILL.md` from ordered partials.** (a) `build-skill.ts` reads 8–9 ordered `.md` partials and concatenates them. (b) A single 1500-line monolithic `SKILL.md`. (c) Diffability + variant emission (agent vs local) without code dup. **Session 05.**
- **Vite + `@babel/standalone` for live LLM-generated React.** (a) Compile JSX in the browser at runtime. (b) Server-side TSX compile. (c) Zero deploy surface; user controls execution; fits the "runtime-light" thesis. **Session 09.**

## Patterns to adopt or diverge from (for EHI Atlas)

- **Adopt: brand-directory format and tag filtering.** Both `health-record-mcp/static/brands/*.json` and `health-skillz/src/client/lib/brands/` use the same JSON shape. Use this for Atlas's portal picker — interop with both Josh and his published brand list is free.
- **Adopt: the Anthropic-Skill packaging pattern, including ordered partials.** Atlas's "patient briefing" output should ship as a Skill the clinician can load into Claude Code. The `build-skill.ts` partials pattern is worth copying outright.
- **Adopt: in-browser SMART client with PKCE + asymmetric assertion.** Don't rebuild this — the `health-skillz/src/client/lib/smart/` form is already modular enough to lift, license caveat aside.
- **Diverge: Atlas *is* the merge layer Josh deliberately omits.** This is the wedge. Every fact in Atlas's gold/silver layer should carry FHIR Provenance edges back to Josh-style preserved bronze bundles. Frame Atlas as "Josh's stack as the bronze, Atlas as the gold + provenance graph."
- **Diverge: redaction is per-fact, not per-resource.** Josh redacts at the resource/category level via `RedactionProfile` flags. Atlas's clinical-briefing thesis ("right 5 facts in 30 seconds") needs *per-fact* visibility controls, not coarse category toggles. Session 04 will pin this contrast.
- **Adopt with extension: the `eval_record` idiom.** Josh's `eval_record` MCP tool runs LLM-generated JS in a Node `vm` sandbox over `ClientFullEHR`. Worth adapting for Atlas as a `run_python` (or `run_sql`-on-FHIR-views) tool — the same pattern, scoped to a provenance-aware view.

## Glossary (running)

See `GLOSSARY.md` (Session 00 block adds 13 terms + an acronym table).

## Open questions

- **License clarity for `health-skillz`.** README claims MIT, no LICENSE file present. Worth pinging Josh before any code reuse beyond fair-use study.
- **Is `health-record-mcp` actually deprecated or just stale?** Last push 2025-08-14, but the SSE OAuth path is non-trivial work. Josh might still maintain it for the Cursor/Claude-Desktop case while `health-skillz` handles the Anthropic-Skill case. Ask in Session 07.
- **The `a4a/` submonorepo inside `health-record-mcp`.** "Agent-to-Agent" — looks tangential. Worth one paragraph in Session 07 to confirm it's not load-bearing.
- **Why `04-codegen.ts` is only 4 lines** in `my-health-data-ehi-wip` (delegates to `src/codegen.ts`). Mild surprise; check in Session 08 — possibly a script-runner shim, possibly an in-progress WIP cut.
- **The `intrabrowser/` directory in `health-record-mcp`.** A 705-line postMessage transport. Is anything in `health-skillz` still using this pattern, or did it get dropped? Session 07.

## Confirmation / revisions to the proposed 11-session arc

The proposed arc holds well after this inventory. Two refinements:

1. **Sessions 02 + 03 might collapse** if the `health-skillz/src/client/lib/smart/` files turn out to be small. The combined OAuth + fetcher walk is what Blake actually wants — splitting at the OAuth/fetch seam is logical but might leave one thin session. Decision deferred to start of Session 02 — if total LOC across `smart/` + `connections.ts` + `api.ts` is under ~600, merge.
2. **Session 10 gets an explicit subtask:** diff `health-record-mcp/clientFhirUtils.ts` against `health-skillz/src/client/lib/smart/*` and characterize the refactor. That diff is the clearest before/after picture in the whole stack.

No other arc changes. Reference-tier repos (`sample_ccdas`, `ehi-export-analysis`, `write-clinical-notes.skill`) stay out of scope unless a primary session needs them.

## Where to read next

**Session 01: The Anthropic Skill format primer, via `request-my-ehi`.** Smallest of the four repos (5,690 LOC) and the cleanest license. We'll dissect: the `SKILL.md` frontmatter, the `argument-hint` + `allowed-tools` fields and how Claude Code uses them, the script-invocation pattern (`bun <skill-dir>/scripts/<script-name>.ts`), the `templates/` PDF bundle, and the `site/skill.zip` distribution artifact. Foundation for Session 05 (which dissects how `health-skillz` *generates* a `SKILL.md` from partials).

---

Ready to proceed to Session 01: The Anthropic Skill format, via `request-my-ehi`. Reply "go" to continue.
