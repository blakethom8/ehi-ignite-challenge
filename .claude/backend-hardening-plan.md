# Backend Hardening — Project Plan

*Created May 11, 2026. Post-Phase-1-submission sprint. Starts May 14, 2026 — no work begins before Phase 1 ships on May 13.*

This is the executable plan for hardening the Caspian + Plugin backend after the EHI Ignite Phase 1 submission. It is the operational cousin of `archive/docs/BACKEND-REPORT-2026-05-11.html` — that doc explains *what's there and what's missing*, this doc tells us *what to ship next, in what order, and how we'll know it's done*.

Companion files:
- `archive/docs/BACKEND-REPORT-2026-05-11.html` — the audit + 15 numbered recommendations
- `.claude/backend-hardening-build-log.md` — timestamped log of every unit shipped
- *(no queue or agent triad yet — add when we commit to an orchestrator loop)*

---

## North Star

Take the Phase 1 submission codebase from "complete in depth, demo-grade in operation" to **production-grade for one pilot organization** by **June 30, 2026**. Production-grade means:

1. The plugin trust chain is rooted in env-only secrets, with consent revocation that survives a deploy.
2. Anchor packages are compiled from real patient FHIR data, not demo fixtures — the cryptographic enforcement protects real data.
3. Every deploy goes through CI with passing tests; no broken commits silently shipped.
4. **Per-user audit is first-class.** Every LLM call, skill run, and plugin tool call writes a unified event with `(user_id, session_id, workspace_kind, event_type, payload, ts)`. "Show me everything user X did across Caspian + plugins + skills in the last hour" is a single query, not a 3-store stitch job.
5. **All four assistant modes (context, deterministic, agent_sdk, cursor) are wired live and side-by-side comparable.** A clinician — or me, during eval — can run the same question through any mode and see the answers, latencies, costs, and traces in one view.
6. The competitive wedge (Provenance edges) is honored end-to-end from bronze to gold to UI.

Strategic / open-ended items (Layer 2 enrichment, multi-step agentic patterns) are tracked in Phase 3 as design conversations — they get a doc before they get a ticket. **Agent SDK completion and Cursor sidecar are no longer "decisions to make" — they're committed first-class modes** that need to reach parity with `context` mode on tracing, rate limiting, and audit.

---

## Operating Principles

1. **Phase order is prescriptive.** No Phase 1 work pulled while any Phase 0 task is open. Parallelism within a phase is fine when files don't conflict.
2. **Every unit has a smoke test.** No task is Done until the smoke test passes from a clean checkout.
3. **Critical-path items get a regression test.** Consent revocation, env-only secrets, anchor live-data wiring, and the unified event log all need pytest coverage that fails if the fix regresses.
4. **The Phase 1 submission code is the baseline.** No "while I'm in there" cleanups in critical-path patches.
5. **Every workspace event carries the join keys.** New code that writes to `traces.db`, `provenance.db`, or any skills/plugin event store must include `user_id`, `session_id`, and `workspace_kind` (`caspian` | `plugin` | `skill`). Old call sites get backfilled in H0.5 — new call sites must comply at the PR.
6. **Assistant-mode parity is enforced at the trace level.** Any new mode (or reactivated mode) must emit the same span shape — `mode`, `prompt_tokens`, `completion_tokens`, `latency_ms`, `cost_usd`, `tools_called[]` — so the comparison harness can join across modes without per-mode adapters.
7. **Numbered against the audit.** Every task carries the `BR-#` from `BACKEND-REPORT-2026-05-11.html` so the audit and the plan stay traceable. Notes call out where the plan diverges (un-deferred #6 narrowly; reframed #3 and #15; promoted #7 from High → Critical; elevated #14 and #10).

---

## Phases — executable slices

Each task is sized to fit inside a single focused work session (≤90 min). Sizes: **S** = ≤2h · **M** = ≤1d · **L** = >1d (split before dispatch).

### Phase 0 — Critical correctness + per-user audit (target: May 14–22)

These six block any claim of production readiness. The audit-trail items (H0.4–H0.6) are the largest scope shift from the original report — they were Medium/High/deferred, and they're now Critical because per-user visibility is a hard product requirement, not a nice-to-have.

| ID | BR# | Task | Files | Smoke test | Size |
|---|---|---|---|---|---|
| H0.1 | 4 | Persist plugin consent revocation across restarts. Add `revoked_at` column to `runs` table; reload `_revoked_ids` on startup. | `api/plugins/runtime.py`, `api/tests/test_plugin_runtime.py` (extend) | pytest: revoke → simulate restart (re-init module) → tool call returns 403 ConsentRevoked | S |
| H0.2 | 3 (reframed) | Production refuses file-based secret fallback. When `ENVIRONMENT=production`, `atlas_keypair()` and `init_auth_store()` raise on missing env var instead of reading `data/atlas-*.key`. | `api/trust/keys.py`, `api/core/auth.py`, `api/tests/test_trust_keys.py` (new) | pytest: `ENVIRONMENT=production` + missing env raises; `ENVIRONMENT=development` still falls back | S |
| H0.3 | 1 | Wire anchor compiler to live FHIR data. Replace `_load_patient_slice()` fixture lookup with `lib.fhir_parser.bundle_parser.parse_bundle()` for real patient IDs; keep fixtures only as a pinned demo path behind an explicit flag. | `api/plugins/anchors.py`, `api/tests/test_plugin_anchors.py` (extend) | pytest: compile_anchor for a real Synthea bundle returns scope-correct fields; redaction preset still applied | M |
| H0.4 | 7 (promoted from High) | Enable tracing in production + extend coverage to skills + plugins. Default `TRACING_ENABLED=true` in prod compose; add `TRACING_SAMPLE_RATE` env (default 1.0). Extend `TracingMiddleware` to wrap `/api/skills/*`, `/api/plugins/runs/*/tool/*`, and the streaming `/api/assistant/chat` (currently the only covered path). Every span carries `user_id` + `session_id` + `workspace_kind`. | `api/middleware/tracing.py`, `api/core/tracing.py`, `deploy/docker-compose.prod.yml`, `api/main.py` (middleware registration scope) | pytest: a single test exercises chat + skill + plugin tool and asserts three spans land in `traces.db` with matching `user_id` and three different `workspace_kind`s | M |
| H0.5 | 6 (un-deferred, narrowly scoped) | Create `api/workspace/events.py` — narrow shared events table only. Schema: `(event_id, ts, user_id, session_id, workspace_kind, event_type, target_id, payload_json, parent_event_id)`. Both Caspian (skills runtime + assistant) and plugins (consent grants, tool calls, outbound approvals) write through it via a single `record_event()` helper. Existing per-store logs stay; this adds a unifying index. **Explicitly NOT in scope:** the full `api/workspace/sessions.py` + `artifacts.py` refactor — that stays deferred. | `api/workspace/__init__.py` (new), `api/workspace/events.py` (new), `api/plugins/runtime.py` (insert `record_event` calls), `api/core/skills/agent_loop.py` (insert calls), `api/core/provider_assistant_service.py` (insert calls), tests | pytest: a contrived run that touches all 3 surfaces produces ≥3 events with the same `user_id`; querying by `user_id` returns all 3 | M |
| H0.6 | NEW | Per-user audit query API + admin viewer. New router `GET /api/audit/users/{user_id}?since=…&until=…` joins `events` + `traces.db` + `provenance.db` and returns a unified timeline. Add a minimal admin page at `/learn/audit` to render it (table + filters by workspace_kind). Bearer-token gated like `/api/traces`. | `api/routers/audit.py` (new), `api/main.py` (register), `app/src/pages/InternalTools/Audit.tsx` (new), tests | curl with valid token returns timeline for a known user; admin page renders it; unauthorized returns 401 | M |

**Exit criterion:** Pick any user_id in the system, hit `/learn/audit?user=<id>&since=1h`, and see a single chronological timeline that includes (a) every Caspian assistant turn, (b) every skill run started/completed/escalated, (c) every plugin consent grant + tool call + outbound approval. The cryptographic-trust regression tests (H0.1–H0.3) are green. Tracing spans land for all three workspace kinds.

### Phase 0+ — Closing gaps Phase 0 surfaced (target: May 19–22)

Added after Phase 0 shipped (commits `f38aeff`..`045d031`). Implementation
of the original six tickets exposed seven follow-on items: three are
correctness gaps in promises the original phase made (skills auth, skill
lifecycle events, cursor mode parity), two are safety/operational concerns
the audit-log work introduced (PII in payloads, no retention), and two are
performance / runbook hygiene (provenance index, prod secrets doc).
Sequenced before Phase 1 because they un-finish promises the user already
sees in the audit endpoint.

| ID | Source | Task | Files | Smoke test | Size |
|---|---|---|---|---|---|
| H0.7 | gap noted in H0.5 | **Skills router requires authenticated session.** `POST /api/skills/{name}/runs` and other write endpoints currently accept anonymous calls, which means H0.5's `record_event` writes empty `user_id` for every skill run. Add `require_access_session(request)` and pass the resulting principal into `record_event_for_session()` instead of `current_session(request)`. | `api/routers/skills.py`, `api/tests/test_skills_runtime.py` (extend) | pytest: anonymous POST → 401; authenticated POST → event rows carry the session's user_id | S |
| H0.8 | new safety concern | **PII redaction on event payloads.** Right now `chat.turn` events store `question_preview[:200]` raw — patient names embedded in clinician questions land in `events.db` unredacted. Add a redaction pass that runs every payload through the same `apply_preset()` path `api/plugins/anchors.py` uses (default preset configurable via env, e.g. `EVENTS_REDACTION_PRESET=minimal`). | `api/workspace/events.py`, `api/trust/redactions.py` (extend if needed), `api/tests/test_workspace_events.py` (add "patient name doesn't leak" case) | pytest: a record_event with `payload={"question_preview": "what allergies does John Hollister have?"}` round-trips with the name redacted | M |
| H0.9 | partial H0.5 ship | **Skill lifecycle events: completed + escalated.** H0.5 shipped only `run.started`. The plan promised "every skill run started/completed/escalated" — wire `record_event` calls into `api/core/skills/agent_loop.py` (or `worker.py`) at run completion and at every escalation gate. The event must carry the originating user_id; thread it through from the start_run handler if the worker context doesn't have it. | `api/core/skills/agent_loop.py`, `api/core/skills/worker.py`, `api/routers/skills.py`, tests | pytest: a full skill run produces 3 events (started, escalated, completed) all keyed on the same user_id | M |
| H0.10 | priority #2 verification | **Cursor sidecar tracing parity.** The "all four modes emit the same span shape" promise is unverified — Cursor sidecar runs in a separate Node process and writes to its own log, not `traces.db`. Either (a) have the sidecar POST a span back to a new internal `/api/traces/ingest` endpoint after each call, or (b) wrap `cursor_sidecar_client.call(...)` in a Python-side `start_span(...)` that records the round-trip from this process's vantage point. **Default: option (b)** — simpler, single source of truth, no cross-process auth required. Mode comparison test asserts `mode=cursor` traces land with the same `(user_id, session_id, workspace_kind=caspian)` triple as `mode=context`. | `api/core/cursor_sidecar_client.py`, `api/core/provider_assistant_cursor.py`, tests | pytest: a `mode=cursor` chat call lands a span in `traces.db` with `mode=cursor` populated and matching session keys | M |
| H0.11 | perf gap noted in H0.6 | **Index `provenance.approver_id` for the audit query.** `audit.get_user_timeline()` does a full scan of provenance.db then filters by approver in Python. Add `approver_id TEXT` column (denormalized from the JSON blob) + index, populate on insert, and have the audit query filter at SQL. Forward-compat ALTER + backfill on first read. | `api/plugins/provenance.py`, `api/routers/audit.py`, `api/tests/test_plugin_provenance.py` (extend) | pytest: 1000 provenance rows + 5 from a target user → audit query reads only the 5 (assert via SQL trace or row-fetched count) | S |
| H0.12 | follow-on from H0.2 | **Production secrets runbook.** H0.2 made `ATLAS_SIGNING_KEY` and `EHI_SESSION_SECRET` required in production. There is no operator doc explaining how to generate them, set them, or what happens at boot if they're missing. Write `docs/architecture/deployment/PROD-SECRETS.md`: required env vars, generation commands (one-liner using `api/trust/signatures.generate_keypair`), rotation procedure, what each missing var fails at. | `docs/architecture/deployment/PROD-SECRETS.md` (new) | doc exists, includes copy-paste-ready key generation snippet that round-trips through `private_key_from_b64` | S |
| H0.13 | unbounded growth from H0.5 | **events.db retention.** Plain INSERT-only growth at 3–5 events per user action will balloon disk on Hetzner CX21. Add a configurable retention policy (default: 90 days) with a startup-hook purge of rows older than the threshold. Plus a dev-mode `EVENTS_RETENTION_DAYS=0` to disable for tests. | `api/workspace/events.py` (purge function + env var), `api/main.py` (call on startup), tests | pytest: insert 5 events with backdated `ts`, run purge, assert only future-window rows remain | S |
| H0.14 | follow-on from H0.2 | **Sweep `atlas-guest-harmonization.key` plaintext fallback.** H0.2 fixed two of three plaintext key fallbacks; the guest-harmonization secret was explicitly out of scope. Mirror the same pattern: when `ENVIRONMENT=production` and `GUEST_HARMONIZATION_SECRET` is unset, raise instead of writing/reading the file. | `api/core/guest_harmonization.py`, `api/tests/test_trust_keys.py` (extend), `docs/architecture/deployment/PROD-SECRETS.md` (add to required-env table) | pytest: production + missing env raises; development still falls back | S |

**Exit criterion:** seven new entries in the build log (H0.7 → H0.13). Skills `POST` endpoints reject anonymous callers. A test asserts that an event payload containing "John Hollister" comes out redacted. A `mode=cursor` chat call shows up in `traces.db` with the same span shape as `mode=context`. The audit endpoint's provenance lookup is constant-time. `docs/architecture/deployment/PROD-SECRETS.md` exists. `events.db` has a documented purge.

### Phase 1 — Production reliability (target: May 19–25)

| ID | BR# | Task | Files | Smoke test | Size |
|---|---|---|---|---|---|
| H1.1 | 2 | CI pipeline: pytest + tsc + npm build on every PR; block merge on failure. | `.github/workflows/ci.yml` (new) | Open a PR with a failing test → merge blocked; passing PR shows green | M |
| H1.2 | 9 | SQLite schema versioning. Add `schema_version` table + minimal forward-only migration runner per DB; backfill version=1 for existing DBs. | `api/core/db_migrations.py` (new), per-DB `_init` callsites | pytest: missing migration raises on startup; applied migration sets version row | S |
| H1.3 | 12 | Resize Hetzner to CX31 (8 GB RAM); add UptimeRobot monitor on `/api/health` every 5 min. | Hetzner console, UptimeRobot setup, `docs/architecture/deployment/DEPLOYMENT.md` (note resize) | `free -m` on host shows 8 GB; UptimeRobot reports 200 OK twice | S |

**Exit criterion:** A junior contributor can open a PR, see it tested, get it merged, and trust that the deploy pipeline plus uptime monitor will catch a regression within 5 minutes.

### Phase 2 — Data layer + plugin reality (target: May 26 – June 8)

| ID | BR# | Task | Files | Smoke test | Size |
|---|---|---|---|---|---|
| H2.1 | 14 | Add provenance columns (`source_bundle_path`, `source_resource_id`) to gold-layer derivations. | `lib/sql_on_fhir/derived.py`, `lib/sql_on_fhir/views/README.md`, tests | `SELECT source_bundle_path FROM medication_episode LIMIT 5` returns non-null real paths | M |
| H2.2 | 8 | Replace fixture connectors with real HTTP adapters where the API contract exists today (start: ClinicalTrials.gov for trial-finder). Keep fixture path behind `CONNECTOR_MODE=fixture` flag for local dev. | `api/plugins/connectors.py`, `api/plugins/tests/test_connectors.py` | Live call to ClinicalTrials.gov returns ≥1 result for a known query; flag flip falls back to fixture | M |

**Exit criterion:** A clinician clicking a fact in the chart workspace can trace it back to the originating bundle path; trial-finder, when run against a real patient, makes a real HTTP call to ClinicalTrials.gov.

### Phase 3 — Agentic mode parity + evaluation (target: June 9 – June 30)

The framing here changed substantially from the original audit. Agent SDK and Cursor sidecar are no longer "decisions to make" — both are committed first-class modes that need to reach `context`-mode parity on tracing, rate limiting, and per-user audit. The new H3.1 (mode comparison harness) is the unifying piece that makes side-by-side vetting possible.

| ID | BR# | Task | Files | Smoke test | Size |
|---|---|---|---|---|---|
| H3.1 | NEW | **Mode comparison harness.** New endpoint `POST /api/assistant/compare` that accepts `{patient_id, question, modes: ["context", "deterministic", "agent_sdk", "cursor"]}` and runs the question through each mode in parallel. Captures answer, latency, cost, tool calls, and trace_id per mode into a single `comparison_runs` table. UI page renders results side-by-side with per-mode tracing drill-in. Reuses H0.4 + H0.5 plumbing. | `api/routers/assistant.py` (extend), `api/core/comparison_runner.py` (new), `data/migrations/comparisons_001.sql` (new), `app/src/pages/Caspian/CompareModes.tsx` (new) | curl returns one row with 4 sub-results; UI renders 4 columns; each carries a clickable trace_id | L (split: backend M + frontend M) |
| H3.2 | 10 (elevated from Medium) | **Complete Agent SDK assistant mode.** Finish `provider_assistant_agent_sdk.answer_with_agent_sdk()` — multi-turn loop with `run_sql` + FHIR-record tools, max_turns=10, instrumented end-to-end. Span shape matches H0.4 contract so the comparison harness can join. Add a small eval suite: 10 canonical clinical questions, scored against `context`-mode baseline. | `api/core/provider_assistant_agent_sdk.py`, `api/tests/test_agent_sdk_mode.py` (new), `eval/agent_sdk_baseline.jsonl` (new) | pytest: each of 10 eval questions returns an answer with ≥1 tool call recorded and trace ID populated | M |
| H3.3 | 15 (reframed: keep + harden, not "decide") | **Cursor sidecar — first-class mode parity.** Add the same tracing, rate limiting, cost capture, and per-user audit as the other modes. Update `cursor-sidecar/` to emit our span shape via the audit API rather than its own log file. Add health probe to compose. Update `cursor_sidecar_client` to populate `user_id` + `session_id` on every call. | `api/core/cursor_sidecar_client.py`, `cursor-sidecar/src/`, `deploy/docker-compose.prod.yml` (healthcheck), tests | A `/api/assistant/chat?mode=cursor` call lands a span in `traces.db` with `mode=cursor` and the calling user's id; sidecar healthcheck returns 200 | M |
| H3.4 | 5 | **Layer 2 LLM Batch Enrichment — design doc, then a thin first slice.** The doc pins the Haiku prompt, cache key (`patient_id × bundle_mtime × prompt_version`), output schema, and eval. The first slice ships *one* enrichment field (relevance_score) end-to-end so we can measure the cost/quality envelope before committing to the full Layer 2 build. | `docs/architecture/LAYER-2-DESIGN.md` (new), `api/core/batch_enrichment.py` (new — minimal), tests | Doc ends with a "build it" or "kill it" verdict; minimal pipeline scores 1 patient and the result lands in cache | L (split: doc S + slice M) |
| H3.5 | NEW | **Multi-step agentic patterns — research doc.** Survey the patterns beyond call/response: tool-use loop (we have it), planner/executor split, self-critique, verifier-in-the-loop, multi-agent debate. For each: when it fits Caspian's 30-second briefing use case, when it fits power queries, what it costs, what telemetry would prove it works. Output is a recommendation matrix, not a build. | `docs/architecture/AGENTIC-PATTERNS.md` (new) | Doc exists with at least one recommended pattern marked "try in H4" | S |

**Exit criterion:** A clinician (or me, during eval) can ask the same clinical question and get four answers + four traces in one view. Agent SDK and Cursor modes carry the same span shape and per-user audit as `context` mode. The Layer 2 question is decided (not deferred again). The agentic-patterns doc gives us a roadmap for "more than call and response" work in a future H4 phase.

---

## Items deferred from the audit

Logged so the decision is auditable, not lost.

| Audit BR# | Item | Why deferred |
|---|---|---|
| 6 (partial) | Full `api/workspace/sessions.py` + `artifacts.py` refactor | The narrow events-table slice is **un-deferred** as H0.5 because per-user audit demands it. The full session/artifact unification stays deferred until concrete pain emerges (4th plugin, or a session-mismatch bug across Caspian/skills). |
| 11 | Plugin process sandbox | Right answer for an untrusted-vendor marketplace; not the right answer for a prototype with three first-party plugins. Revisit when an external vendor signs first. |
| 13 | Per-org plugin registry + key rotation | Multi-org concern. Defer until pilot #2 is contractually committed. |

---

## Open questions

These get answered before the relevant phase is dispatched. Block the affected task with `⛔` in the build log if still open at dispatch time.

1. **For H0.3:** Does the anchor compiler need to support a "demo patient" mode at all, or does the live-data path subsume it? (Default: keep the demo path behind a flag for screenshots/marketing.)
2. **For H0.5:** Does `events.py` use the existing `runs.db` SQLite, a new `events.db`, or land in `traces.db` as a new table? (Default: new `events.db`, schema-versioned via H1.2 from day one. Prevents tracing perf regressions and keeps audit independent of the LLM trace store.)
3. **For H0.6:** Who can hit `/api/audit/users/*` — only platform admins, or also the user themselves (their own data)? (Default: admin token only for v1; user-facing "your activity" view in a later phase.)
4. **For H1.1:** Do we deploy from CI on master merge, or keep deploy manual gated by CI green? (Default: CI green gates merge; deploy stays manual until H3 is done.)
5. **For H2.2:** Do we have a ClinicalTrials.gov API key already, or do we need to obtain one? (Spike at start of phase.)
6. **For H3.1:** Does the comparison harness run modes in parallel (4× cost, fastest wall-clock) or sequentially (1× cost, 4× wall-clock)? (Default: parallel — eval is bursty and small, the cost is a rounding error against the value of side-by-side review.)
7. **For H3.4:** Is the "thin first slice" enrichment field `relevance_score` (LLM-judged) or something cheaper like `is_routine` (rule-based gate)? (Default: `relevance_score` so the slice actually exercises the Haiku call path; cheaper signals can come later if cost surprises.)

---

*Last updated: May 11, 2026 — initial creation from BACKEND-REPORT-2026-05-11.html audit.*
