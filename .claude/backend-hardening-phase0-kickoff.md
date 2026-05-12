You're starting Phase 0 of the backend hardening sprint for the EHI Ignite Challenge submission. No prior conversation context — orient from these files first:

  .claude/backend-hardening-plan.md             ← READ FIRST. Full plan.
  .claude/backend-hardening-build-log.md        ← append after each ticket
  docs/architecture/BACKEND-REPORT-2026-05-11.html  ← the audit it derives from
  CLAUDE.md                                      ← project conventions

Scope: H0.1 → H0.6 in the plan. Nothing in Phase 1, 2, or 3.

Two hard requirements that override the audit's original framing:

  1. Per-user audit is non-negotiable. End-of-phase deliverable: hitting GET /api/audit/users/{user_id}?since=1h (and the /learn/audit admin page) returns a single chronological timeline joining a Caspian chat turn, a skill run, and a plugin tool call for the same user. Shipping H0.1–H0.3 without H0.4–H0.6 does not close Phase 0.

  2. All four assistant modes (context, deterministic, agent_sdk, cursor) must emit the same span shape on every audited surface. Don't add audit code that one mode emits and the others don't — that's a regression even if the mode is "incomplete" today.

Execution:
  - Enter a worktree before touching code (CLAUDE.md convention).
  - Ship in this order — H0.1 + H0.2 first (both Small, parallelize where files don't conflict), then check in with me before H0.3 (Medium, touches the live FHIR data path), then H0.4 → H0.5 → H0.6 in sequence.
  - Smoke test from the plan must pass before commit. Add a regression pytest where the plan calls for one. New code must populate user_id + session_id + workspace_kind everywhere it writes to traces.db, provenance.db, or the new events store.
  - Append a build-log entry after every shipped ticket — use the template at the bottom of backend-hardening-build-log.md.
  - Local commits on the worktree branch only. Don't push to master without my explicit OK.
  - Open questions in the plan have defaults — take the default and note the choice in the build-log entry. Only stop to ask if the default risks data loss or trust-chain compromise.
  - If you find the plan needs revision (a ticket is mis-scoped, a smoke test is wrong, a dependency is missing), edit the plan first and flag it before continuing — don't silently drift.

Done = the audit-endpoint deliverable above is demonstrable on a fresh dev boot, and the build log has six new entries (H0.1 → H0.6). Ping me then to start Phase 1.
