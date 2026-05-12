You're starting Phase 0+ of the backend hardening sprint — seven follow-up tickets that close gaps the original Phase 0 (commits f38aeff..045d031) surfaced during implementation. No prior conversation context — orient from these files first:

  .claude/backend-hardening-plan.md             ← READ FIRST. New "Phase 0+" section.
  .claude/backend-hardening-build-log.md        ← Phase 0 closeout + append template
  CLAUDE.md                                      ← project conventions

Scope: H0.7 → H0.13 only. Don't touch Phase 1+ work.

Both original priority signals still bind:

  1. Per-user audit. H0.7 (skills router auth) and H0.9 (skill lifecycle events: completed + escalated) directly close audit gaps Phase 0 left open. Don't ship a fix that records empty user_ids or partial lifecycles.

  2. Mode parity. H0.10 is the verification step for the "all four modes emit the same span shape" promise. If you can't make Cursor sidecar emit our span shape, document the gap explicitly and add a test that proves the gap exists — don't paper over it.

Two new constraints from this round of review:

  A. PII-by-default. After H0.8 lands, no event payload field that may contain free-text clinical input may be stored without going through the redaction pass. Tests must include a "patient name doesn't leak" case.

  B. Operational soundness. Phase 0 made prod boot stricter (env vars required). H0.12 (runbook) and H0.13 (events retention) close the follow-on gaps so the next deploy doesn't fail-to-boot or balloon disk.

Execution:
  - Enter a worktree before touching code.
  - Ship in this order — H0.7 → H0.8 (both directly improve correctness) → H0.9 → H0.10 → H0.11 → H0.12 → H0.13. Check in with me after H0.10 (the largest; touches sidecar code in a different language).
  - Smoke test from the plan must pass before commit. Add regression tests where the plan calls for them.
  - Append a build-log entry after every shipped ticket using the template at the bottom of backend-hardening-build-log.md.
  - Local commits on the worktree branch only. Don't push to master without my explicit OK.
  - Open questions in the plan have defaults — take the default and note the choice in the build-log entry. Only stop to ask if the default risks data loss or trust-chain compromise.
  - Run the existing 42-test hardening suite + 47-test plugin suite after every ticket; both must stay green. New tests add to that baseline, never replace it.
  - If you find the plan needs revision (a ticket is mis-scoped, a smoke test is wrong, a dependency is missing), edit the plan first and flag it before continuing — don't silently drift.

Done = all seven tickets shipped, all tests green, the build log has seven new entries (H0.7 → H0.13), and the cursor mode tracing question is decided (parity shipped OR documented as deferred with a regression test that proves the gap). Ping me then to start Phase 1.
