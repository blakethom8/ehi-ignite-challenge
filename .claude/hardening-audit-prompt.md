# Hardening Audit — EHI Ignite Codebase

## Context

Audit the EHI Ignite Challenge codebase (FastAPI + React, turns FHIR bundles into clinical insights) ahead of a Phase 2 production prototype. Recent weeks shipped fast — Caspian agent, harmonization pipeline, demo flows, auth, Atlas IA rewrite — and left scaffolding behind. Find what to **harden, simplify, or delete**. No new features.

Make no code changes; produce a written audit only.

## Read first

- `CLAUDE.md` — current repo layout + conventions
- `docs/architecture/AGENTIC-HARNESS.md` — Caspian vs. Plugins trust contract
- `lib/README.md`, `archive/README.md` — library scope vs. already-deleted
- `git log --since='3 weeks ago' --stat` — what moved recently

## What to look for

Hardening = reducing failure modes in production. Simplification = removing code that exists but no longer earns its place. Look across these categories:

1. **Dead or superseded code.** Modules with no live callers, parallel implementations of the same concept (e.g. there are five `api/core/provider_assistant_*.py` variants and both `harmonize_service.py` and `guest_harmonization.py` — figure out what's still authoritative), stubs referenced in docs but never implemented (`temporal.py`, `batch_enrichment.py`, `rag_tools.py` are flagged TODO in `CLAUDE.md`).
2. **God files.** Single files >1,000 LOC that mix concerns. Known candidates: `api/routers/patients.py` (2,210), `api/core/harmonize_service.py` (2,374), `api/models.py` (1,886), `api/core/auth.py` (1,399), `api/core/guest_harmonization.py` (1,351), `api/routers/skills.py` (1,204), `api/core/aggregation.py` (1,167). For each you call out, name the seam to split along.
3. **Documentation drift.** Docs that describe a structure the code no longer has. Concretely: root `README.md` and `docs/architecture/ECOSYSTEM-OVERVIEW.md` still list `fhir_explorer/` and `patient-journey/` as live top-level dirs and never mention Caspian, Plugins, or the Atlas IA. Find the rest.
4. **Boundary violations.** `api/` reaching into `ehi-atlas/` (the dev zone), `lib/` importing from `api/`, routers doing work that belongs in `core/`, configuration/secrets read ad-hoc instead of via a settings module, request-path code touching the filesystem or running blocking I/O.
5. **Production risks.** Bare `except:` that swallow exceptions, mutable module-level caches without bounds, untyped or unvalidated boundaries (FastAPI route bodies, agent tool inputs), missing tests on critical paths (auth, the `run_sql` SELECT-only gate, harmonization writes, agent tool execution), anything that silently fails in prod.

Be concrete, not vibes. Cite files and line ranges. Where possible, give numbers — LOC, call counts, test coverage gaps.

## Constraints

- No new features, no framework migrations.
- Don't recommend changes to `lib/fhir_parser`, `lib/sql_on_fhir`, or `lib/clinical` — stable, widely imported.
- Ignore `archive/` — deliberately frozen.
- If you can't tell whether something is dead without runtime tracing, say so rather than guess.

## Deliverable

Write `.claude/hardening-audit.md` with **exactly 5 findings**, ordered by impact (highest first). Use this shape for each:

```text
### N. <Short title>

**What:** 1–2 sentences.
**Evidence:** Specific files + line ranges. Numbers.
**Why it matters in production:** Concrete failure mode or maintenance cost.
**Recommended action:** Concrete next step. Size: S (≤½ day) / M (1–2 days) / L (≥3 days).
**Risk if deferred:** One sentence.
```

Top of file: 3-bullet executive summary.
Bottom of file: a "considered and rejected" section — what you looked at and decided was fine, one line each. This is as important as the findings; it tells the reader where you actually searched.

Length cap: 1,500 words. Specificity over coverage — a sharp finding with line numbers beats a broad one without.
