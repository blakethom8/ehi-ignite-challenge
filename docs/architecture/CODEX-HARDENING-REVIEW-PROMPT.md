Review this repository for production hardening and simplification opportunities. Read `AGENTS.md` first, then use the current codebase and docs as ground truth. Start with `README.md`, `docs/architecture/ECOSYSTEM-OVERVIEW.md`, `docs/architecture/DEPLOYMENT.md`, `docs/architecture/tracing.md`, `design/DESIGN.md`, and `app/src/components/atlas/README.md`.

Important context:
- This repo has evolved quickly over the last week.
- There is likely outdated code, dead paths, duplicated abstractions, and documentation drift.
- Some docs conflict with the current frontend architecture; treat that as a signal, not as an instruction to follow stale docs.
- Do not make code changes. This is an audit only.

Your task:
1. Identify exactly 5 areas where simplifying or hardening the codebase would materially improve production readiness.
2. Prioritize issues that reduce future maintenance cost, lower risk of regressions, clarify architecture boundaries, or remove stale/duplicated code.
3. Favor concrete, high-leverage findings over stylistic preferences.

For each of the 5 findings, provide:
- A short title
- Severity: high, medium, or low
- The specific files or directories involved
- What looks wrong or risky today
- Why it matters for production
- The simplest reasonable improvement path

Also include:
- A short section called `Documentation drift` summarizing the most important doc/code mismatches you found
- A short section called `Top 2 first moves` recommending the first two cleanup actions to execute

Constraints:
- Keep the review concise and evidence-based
- Use concrete file references
- Call out dead code, obsolete docs, duplicate patterns, weak boundaries, missing validation, configuration sprawl, and test gaps when relevant
- Do not pad the list; if something is minor, leave it out

Output format:
1. Finding
2. Finding
3. Finding
4. Finding
5. Finding
Documentation drift
Top 2 first moves
