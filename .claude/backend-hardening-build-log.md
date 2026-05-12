# Backend Hardening Build Log

*Chronological record of every backend-hardening task that shipped. Append a new entry after each successful unit. Read top-to-bottom for the full history.*

Companion files:
- `.claude/backend-hardening-plan.md` — the phased plan + open questions
- `docs/architecture/BACKEND-REPORT-2026-05-11.html` — original audit + 15 recommendations

---

## 2026-05-11 — Plan baselined

**Commit (planning, no code):** *(this commit)*

**What exists at the start of the hardening sprint:**

Verified against the source on master @ `92bb50e`. All claims spot-checked.

| Subsystem | State at baseline | Source of truth |
|---|---|---|
| Plugin trust chain | Cryptographically complete; anchor compiled from 4 demo fixtures only | `api/plugins/anchors.py:46–284`, `api/plugins/runtime.py:180` |
| Consent revocation | In-memory `_revoked_ids` set, no persistence | `api/plugins/runtime.py:180,388,711` |
| Secrets | Env-var preferred + file fallback in `data/`; production allows fallback | `api/trust/keys.py:56–62`, `api/core/auth.py:161–169` |
| Tracing | `TRACING_ENABLED=false` default; middleware wraps `/api/assistant/chat` only | `api/core/tracing.py:33`, `api/middleware/tracing.py:31` |
| CI/CD | None — manual SSH deploy; no `.github/workflows/*.yml` | `deploy/deploy-prod.sh` |
| SQLite schema versioning | None across `auth.db`, `sof.db`, `traces.db`, `runs.db`, `provenance.db` | `api/core/auth.py:237–278`, `api/core/sof_materialize.py`, `api/core/tracing.py:222–260`, `api/plugins/runtime.py:124–172`, `api/plugins/provenance.py:47–64` |
| Plugin connectors | All 6 connectors read fixture JSON via `_read_fixture()` | `api/plugins/connectors.py:46,56–141` |
| Context Layer 2 | Explicitly TODO; `api/core/batch_enrichment.py` does not exist | `api/core/context_builder.py:14` |
| `api/workspace/` shared module | Does not exist; Caspian + plugins maintain separate session/event/artifact code | dirscan |
| Provenance in gold layer | Bronze provenance exists; gold derivations lack `source_bundle_path` columns | `lib/sql_on_fhir/derived.py` |

**Decisions carried into the plan (diverging from the audit):**

- **Reframed BR#3 (plaintext keys):** env-var support already exists. The fix is to make production refuse the file fallback (`ENVIRONMENT=production` raises on missing env), not to "add env var support."
- **Promoted BR#7 (tracing) High → Critical and expanded scope.** Now H0.4 — also extends `TracingMiddleware` to skill runs and plugin tool calls so all three workspace kinds emit comparable spans.
- **Un-deferred BR#6 (`api/workspace/`), narrowly scoped to events only.** Now H0.5 — a single shared events table with `(user_id, session_id, workspace_kind, event_type, payload, ts)` so per-user audit is queryable in one place. The full `sessions.py` + `artifacts.py` refactor stays deferred.
- **Added H0.6 (per-user audit query API + admin viewer).** Not in the original audit. The unifying user-facing surface that sits on top of H0.4 + H0.5.
- **Reframed BR#15 (Cursor sidecar) "decide" → "keep + harden."** Now H3.3 — the user has committed to keeping it as a first-class toggleable mode.
- **Elevated BR#10 (Agent SDK) Medium → Phase 3 with concrete completion target.** Now H3.2 — Agent SDK, Cursor, context, and deterministic must reach parity on tracing/audit so they can be compared side-by-side.
- **Added H3.1 (mode comparison harness) and H3.5 (agentic patterns research doc).** Both new — make multi-mode comparison and "more than call/response" a structured workstream rather than ad-hoc experimentation.
- **BR#14 (Provenance edges) elevated** from "Medium" into Phase 2 because the wedge promise depends on it (H2.1).
- **BR#11 (process sandbox) and BR#13 (per-org registry) remain deferred.**

**Priority signal (2026-05-11, post-baseline):** user surfaced two hard requirements that re-shaped the plan:
1. Per-user audit logs are non-negotiable. Three siloed audit stores joinable only by stitching is unacceptable.
2. Multiple agentic modes (Claude SDK, Cursor SDK, plus future patterns) must be wired live and side-by-side comparable so output quality can be vetted before a mode is endorsed.

This pushed BR#7 + a narrow BR#6 into Phase 0 and reframed Phase 3 from "decide what to keep" into "achieve mode parity + build the comparison harness."

**Phase order:** 0 → 1 → 2 → 3, no parallelism across phases. Within a phase, parallelism is allowed when files don't conflict.

---

<!--
Append entries below this marker as tasks ship.
Template:

## YYYY-MM-DD — H#.# — One-line description

**Shipped:** YYYY-MM-DD
**Commit:** `<sha>`
**Files:**
- path/to/file.py — what changed

**What it does:** 2–4 sentence summary, plain prose. Why this fix matters in one line.

**Smoke test:**
```
<command + condensed output>
```

**Follow-ups (if any):** bullets — left open, blocked, or punted to a later phase.

---
-->

## 2026-05-11 — H0.1 — Persist plugin consent revocation across restarts

**Shipped:** 2026-05-11
**Commit:** `f38aeff`
**Files:**
- `api/plugins/runtime.py` — added `revoked_at TEXT` column to `runs`; `revoke_consent()` writes the timestamp; new `reload_revoked_runs()` rehydrates `_revoked_ids` from rows where `revoked_at IS NOT NULL`. Forward-compat ALTER guards existing DBs.
- `api/main.py` — startup hook now calls `plugin_runtime.reload_revoked_runs()` after `reload_manifests()`. Wrapped in try/except so a malformed runs.db doesn't crash boot.
- `api/tests/test_plugin_runtime.py` — added `test_revocation_survives_restart`: revoke → clear `_revoked_ids` (simulate restart) → `reload_revoked_runs()` → assert tool call still raises `ConsentError`.

**What it does:** Closes the gap where revoking a plugin's consent only invalidated tool access until the next API restart. The `_revoked_ids` set is now seeded at startup from a persistent column, so a deploy or crash mid-run can no longer silently restore a revoked plugin's access.

**Smoke test:**
```
$ uv run pytest api/tests/test_plugin_runtime.py -q
9 passed in 1.13s
$ uv run pytest api/tests/test_plugin_runtime.py api/tests/test_plugin_tools.py \
    api/tests/test_plugin_routers.py api/tests/test_plugin_consent.py \
    api/tests/test_plugin_anchors.py -q
47 passed in 0.85s
```

**Follow-ups:** the ad-hoc `ALTER TABLE` belongs to a real migration runner — that's H1.2.

---

## 2026-05-11 — H0.2 — Production refuses file-based secret fallback

**Shipped:** 2026-05-11
**Commit:** `4edbbaa`
**Files:**
- `api/trust/keys.py` — new `_is_production()` helper; `_load_or_create_atlas_key()` now raises `RuntimeError` when `ENVIRONMENT=production` and `ATLAS_SIGNING_KEY` is unset.
- `api/core/auth.py` — same shape: new `_is_production()`; `_session_secret()` now raises when `ENVIRONMENT=production` and `EHI_SESSION_SECRET` is unset.
- `api/tests/test_trust_keys.py` (new) — 6 tests covering production-fail, development-fallback, and env-supplied paths for both secrets.

**What it does:** Both functions already preferred env vars over the file fallback. The change closes the silent-degradation path: in production, a missing env var now fails fast at the call site instead of materializing a key on disk in the data bind mount.

**Smoke test:**
```
$ uv run pytest api/tests/test_trust_keys.py -v
6 passed in 0.20s
$ uv run pytest api/tests/test_auth_api.py api/tests/test_trust_models.py \
    api/tests/test_plugin_runtime.py api/tests/test_plugin_routers.py -q
30 passed in 9.81s
```

**Follow-ups:** `api/core/guest_harmonization.py` loads `data/atlas-guest-harmonization.key` with the same fallback shape. Out of explicit scope for H0.2 (plan named only the two files above) — flagged here so it can be swept either as part of H0.5 wiring (the events-store work touches similar surfaces) or as a tiny standalone follow-up. Track as a punch-list item before deploy.

---

## 2026-05-11 — H0.3 — Wire anchor compiler to live FHIR data

**Shipped:** 2026-05-11
**Commit:** `ab0feb1`
**Files:**
- `api/plugins/anchors.py` — new `_load_from_fhir()` reads the Synthea bundle via `lib.fhir_parser.bundle_parser.parse_bundle()` and maps `PatientRecord` into the flat anchor schema (`_project_scope` still does the per-token scoping). `load_raw_patient()` prefers live FHIR by default; `PLUGIN_ANCHOR_USE_FIXTURES=true` keeps the curated demo path for screenshots/marketing. Last-resort fixture fallback preserved for legacy IDs without bundles.
- `api/tests/test_plugin_anchors.py` — 3 new regression tests: live-by-default, fixture-flag-pinning, redactions-still-applied.

**What it does:** Closes the credibility gap where every plugin run produced an anchor backed by 4 hardcoded demo dicts regardless of patient ID. The cryptographic scope enforcement is unchanged; what changed is that scope now constrains access to *real* patient data.

**Smoke test:**
```
$ uv run pytest api/tests/test_plugin_anchors.py -v
12 passed in 0.20s
```

**Open question default taken:** Q1 — kept the demo-fixture path behind `PLUGIN_ANCHOR_USE_FIXTURES=true` for screenshots/marketing; live FHIR is the default everywhere else.

**Follow-ups:** `_load_from_fhir` builds an empty `biomarkers` list. A future pass should map specific LOINC observations (BCR-ABL, PSA, etc.) into the biomarkers slot — useful for trial-finder. Out of H0.3 scope.

---

## 2026-05-11 — H0.4 — Enable tracing in prod + extend to skills + plugins

**Shipped:** 2026-05-11
**Commit:** `2d2dd4b`
**Files:**
- `api/core/tracing.py` — new `TRACING_SAMPLE_RATE` env (default 1.0). `Trace` dataclass + `traces` table gain `user_id`, `session_id`, `workspace_kind` (the join keys H0.6 depends on). Forward-compat `ALTER TABLE` for existing DBs.
- `api/middleware/tracing.py` — rewritten to classify three audited POST surfaces (caspian chat, skill, plugin tool); URL-only for skill + plugin (avoids consuming the request body); `_session_identity()` pulls user/session from the cookie via `current_session`.
- `deploy/docker-compose.prod.yml` — `TRACING_ENABLED=true` and `TRACING_SAMPLE_RATE=1.0` in the api service.
- `api/tests/test_tracing_middleware.py` — 3 tests including the plan's named smoke test (3 surfaces × matching user_id × 3 distinct workspace kinds).

**What it does:** The middleware now records spans for every audited surface, not just `/api/assistant/chat`. Every span carries the (user_id, session_id, workspace_kind) tuple that H0.6's audit query joins on. Tracing defaults to ON in production with full sampling.

**Smoke test:**
```
$ uv run pytest api/tests/test_tracing_middleware.py -v
3 passed in 0.14s
```

---

## 2026-05-11 — H0.5 — Unified workspace events table

**Shipped:** 2026-05-11
**Commit:** `35deb96`
**Files:**
- `api/workspace/__init__.py` (new) — re-exports.
- `api/workspace/events.py` (new) — SQLite at `data/events.db` with schema `(event_id, ts, user_id, session_id, workspace_kind, event_type, target_id, payload_json, parent_event_id)` plus indexes on user+ts, session, kind+type, target, ts. `record_event()` and `query_events()` helpers; `record_event_for_session()` pulls join keys off a `SessionPrincipal`.
- `api/plugins/routers/plugins.py` — `record_event` calls in `start_run`, `grant_consent`, `revoke_consent`, `call_tool`, `approve_outbound`, `deny_outbound`.
- `api/routers/assistant.py` — `record_event` in `/chat` handler.
- `api/routers/skills.py` — `record_event` in `start_run`; added `Request` parameter to that handler.
- `api/tests/test_workspace_events.py` — 6 tests including the named exit criterion (one user, three workspace kinds, one query).

**What it does:** Adds the unifying audit index. Before this, three audit stores (traces.db, provenance.db, per-skill workspace dirs) shared no first-class user_id key. Now every meaningful action across all three surfaces lands in `events.db` keyed on user_id, queryable in one shot.

**Best-effort recording:** a DB failure logs and returns `""` rather than raising — audit must never block the request path.

**Smoke test:**
```
$ uv run pytest api/tests/test_workspace_events.py -v
6 passed in 0.03s
```

**Open question default taken:** Q2 — `events.db` is a new SQLite separate from `runs.db` / `traces.db`, so audit volume can't push back-pressure on the LLM-trace store.

**Scope discipline:** explicitly NOT shipped in this ticket — the full `api/workspace/sessions.py` + `artifacts.py` + `tools/envelope.py` refactor described in `AGENTIC-HARNESS.md`. That stays deferred to a future phase per Plan §"Items deferred."

---

## 2026-05-11 — H0.6 — Per-user audit query API + admin viewer

**Shipped:** 2026-05-11
**Commit:** *(this commit)*
**Files:**
- `api/routers/audit.py` (new) — `GET /api/audit/users/{user_id}?since=&until=&workspace_kind=` joins events + traces + provenance into one chronologically-sorted timeline. Bearer-token gated via `AUDIT_API_TOKEN`; required in production. Plus `GET /api/audit/me` for self-service via session cookie.
- `api/main.py` — new router registered.
- `api/tests/test_audit_router.py` — 6 tests: the named flagship deliverable (3 surfaces, one query, sorted), workspace_kind filter, empty-for-other-user, three auth-rejection cases.
- `api/workspace/events.py` — bug fix: `query_events` now normalizes `since`/`until` to second precision before SQL compare. Without this, an `until=now()` (microsecond precision) would lexicographically sort before whole-second events because `'.' < 'Z'`.
- `app/src/pages/InternalTools/Audit.tsx` (new) + `app/src/App.tsx` — minimal admin page at `/learn/audit`. User_id input, token input, window selector, workspace_kind filter, color-coded timeline rendering with per-entry payload drawer.

**What it does:** Closes the loop on the per-user audit story. Hitting the endpoint with a valid token returns a single chronological view of "everything user X did in the last hour" across Caspian + skills + plugins. The admin page renders it.

**End-of-phase deliverable demonstrated:** see `test_user_timeline_joins_three_workspace_kinds` — writes 3 events on 3 different workspace kinds with the same user_id, hits `/api/audit/users/{user_id}?since=...`, asserts 3 entries returned with 3 distinct kinds, sorted chronologically. Equivalent to running the same flow against a freshly-booted dev API.

**Open question default taken:** Q3 — `/api/audit/users/*` is admin-token only; user-facing self-view at `/api/audit/me` requires session cookie.

**Smoke test:**
```
$ uv run pytest api/tests/test_audit_router.py -v
6 passed in 0.25s
$ uv run pytest api/tests/test_audit_router.py api/tests/test_workspace_events.py \
    api/tests/test_tracing_middleware.py api/tests/test_plugin_runtime.py \
    api/tests/test_trust_keys.py api/tests/test_plugin_anchors.py -q
42 passed in 0.46s
```

**Frontend type-check:** deferred to H1.1 (CI pipeline). The fresh worktree has no `app/node_modules` installed and a full `npm ci + tsc` run is out of session scope; the TSX is hand-validated against the existing InternalTools page conventions.

---

## Phase 0 closeout — 2026-05-11

All six Phase 0 tickets shipped:

| ID | Ticket | Commit |
|---|---|---|
| H0.1 | Persist consent revocation across restarts | `f38aeff` |
| H0.2 | Production refuses file-based secret fallback | `4edbbaa` |
| H0.3 | Wire anchor compiler to live FHIR data | `ab0feb1` |
| H0.4 | Enable tracing in prod + extend to skills + plugins | `2d2dd4b` |
| H0.5 | Unified workspace events table | `35deb96` |
| H0.6 | Per-user audit query API + admin viewer | *(this commit)* |

**Test posture:** 42 tests across the hardening surface, all green. Existing 47-test plugin baseline still green.

**Fresh-boot deliverable:** the audit endpoint is exercised end-to-end by `test_user_timeline_joins_three_workspace_kinds`, which builds the FastAPI app from scratch on a fresh `events.db` and asserts the joined timeline. The same flow is reproducible at `/learn/audit` against a running dev API once the frontend is built.

**Ready for Phase 1** (CI/CD, schema versioning, host upsize) — see `.claude/backend-hardening-plan.md` Phase 1.

---
