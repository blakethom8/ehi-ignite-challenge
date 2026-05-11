# Consumer Auth + Demo UX Cleanup Plan

## Purpose

The app is a consumer-facing health-record workspace, not a clinician portal. The current landing/auth UX still carries older clinician/demo language, exposes local seeded credentials, and makes the intended public demo path feel like a fallback. This document defines the target experience and implementation plan for cleaning it up.

## Product Positioning

Atlas should present two clear entry paths:

1. **Try the demo** — review a prepared synthetic sample patient workspace with no account required.
2. **Log in / Sign up** — access a personal consumer account, create private health-record workspaces, upload records, and return later.

The product should never describe the primary account as a clinician login unless a future explicit clinician/enterprise mode is added.

## Current State

### Backend

Implemented:

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/session`
- `POST /api/auth/demo`
- `POST /api/auth/demo/exit`
- `POST /api/auth/select-patient`
- Server-side sessions in `data/auth.db`
- Signed HTTP-only `atlas_session` cookie
- Scrypt password hashing for existing users
- Demo patient aliases mapped to approved Synthea records
- Server-local upload/profile persistence under:
  - `data/aggregation-profiles`
  - `data/aggregation-uploads`

Not implemented:

- Public consumer sign-up endpoint
- Account verification / password reset
- User-owned workspace tables or ownership metadata
- Per-user authorization for workspaces/uploads
- Account settings or “my records” workspace list scoped to user

### Frontend

Implemented:

- Landing page with demo picker + sign-in form
- Access context (`AccessProvider`) that hydrates backend session
- Demo mode and authenticated mode in UI state
- Authenticated upload/profile UI paths

Problems:

- Landing page makes sign-in look like the main path even when prod credentials do not work.
- Copy says “clinician,” “demo access posture,” and “unlock,” which does not match a consumer product.
- Login is not paired with sign-up, so users cannot create accounts.
- Demo path feels like a technical auth mode instead of a polished sample experience.
- Authenticated uploads exist, but not safely scoped to a user-owned account/workspace model.

## Target UX

### Landing Page

Hero should answer: “What can I do right now?”

Primary area:

- Headline: consumer language about organizing and reviewing health records.
- Primary CTA: **Try the demo**
- Secondary CTA: **Log in / Sign up**

Suggested copy:

> Bring scattered health records into one reviewable workspace.
>
> Try Atlas with a prepared sample chart, or create an account to upload your own records.

### Demo Flow

Clicking **Try the demo** opens or scrolls to three demo cards:

1. **Surgical Review Sample**
   - “Review a prepared synthetic chart with medications, conditions, and surgical-risk signals.”
   - Route: `/patient-record?patient=demo-high-risk`

2. **Trial Match Sample**
   - “Explore how a structured chart can support trial-search workflows.”
   - Route: `/workspaces/trial-finder?patient=demo-trial-match`

3. **Medication Access Sample**
   - “Review medication burden and access-oriented workflow surfaces.”
   - Route: `/workspaces/med-access?patient=demo-med-access`

Language rules:

- Use “sample patient,” “prepared sample chart,” or “demo workspace.”
- Avoid “demo mode,” “access posture,” “clinician,” and “unlock.”
- State clearly: “These are synthetic records. No real patient data is used.”

### Account Flow

Clicking **Log in / Sign up** opens a dedicated route or modal:

- Tab 1: Log in
- Tab 2: Create account

Consumer account copy:

- “Use your account to save private record workspaces and return later.”
- “Upload PDFs, portal exports, and other health-record files.”

If sign-up is not implemented in the current release, the UI should not pretend it is. Either:

- hide the sign-up tab, or
- show an honest “Account creation is coming soon” state.

Preferred for MVP: implement minimal sign-up.

## Backend Target Architecture

### Phase 1: Minimal Consumer Sign-up

Add:

```http
POST /api/auth/signup
```

Request:

```json
{
  "email": "user@example.com",
  "password": "minimum length password",
  "display_name": "Blake"
}
```

Behavior:

1. Normalize email to lowercase.
2. Reject duplicate active users with `409`.
3. Hash password with existing `_hash_password`.
4. Insert `users` row with role `consumer` or update roles to include `consumer`.
5. Create authenticated session.
6. Set `atlas_session` cookie.
7. Return `AuthSessionResponse`.

Important: current `AuthUserResponse.role` type only allows clinician/admin-ish roles. For consumer product language, update roles to include `consumer`, or introduce an account type separate from medical/professional roles.

### Phase 2: User-owned Workspaces

Today aggregation profiles are global. That is unsafe for real consumer accounts.

Add ownership in the minimal way first:

- Extend `AggregationProfile` or persisted profile JSON with `owner_user_id`.
- On profile creation, set owner to `session.user_id`.
- On profile lookup/update/delete/upload, verify `profile.owner_user_id == session.user_id`.
- Authenticated users should only list their own upload workspaces.

Better long-term shape:

```sql
workspaces (
  id TEXT PRIMARY KEY,
  owner_user_id TEXT NOT NULL,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL,
  updated_at TEXT NOT NULL
)

uploads (
  id TEXT PRIMARY KEY,
  workspace_id TEXT NOT NULL,
  owner_user_id TEXT NOT NULL,
  file_name TEXT NOT NULL,
  content_type TEXT,
  storage_path TEXT NOT NULL,
  metadata_json TEXT NOT NULL,
  uploaded_at TEXT NOT NULL
)
```

For the challenge timeline, JSON metadata ownership is acceptable if consistently enforced and covered by tests.

## Frontend Implementation Plan

### Files to inspect first

- `app/src/pages/Landing.tsx`
- `app/src/context/AccessContext.tsx`
- `app/src/api/client.ts`
- `app/src/types/index.ts`
- `app/src/components/atlas/DemoPatientPicker.tsx`
- `app/src/components/atlas/StartStateCard.tsx`
- `app/src/components/atlas/AppShell.tsx`
- `app/src/components/atlas/PlatformDrawer.tsx`
- `app/src/pages/PatientRecord/Overview.tsx`
- `app/src/pages/Plugins/Index.tsx`

### Copy cleanup rules

Replace:

- “clinician login” → “account login” or “your account”
- “demo mode” → “sample workspace”
- “demo access posture” → “sample chart is active”
- “unlock” → “continue,” “open,” or “start”
- “patient environment” where awkward → “health-record workspace”

Keep “patient” where it clearly means a sample chart/person record.

### UI route recommendation

Add a route:

```txt
/account
```

or a landing modal if smaller. A route is easier to test and less likely to make Landing too large.

Suggested components:

- `AccountAccessPage`
- `AuthForm`
- `SignupForm`

### Error handling

Map backend errors into consumer language:

- `401`: “Log in or start a sample workspace to continue.”
- `403` in demo: “This action is available in saved accounts. Create an account or log in to upload your own records.”
- duplicate sign-up: “An account already exists for this email.”

## Backend Implementation Plan

### Files to inspect first

- `api/core/auth.py`
- `api/routers/auth.py`
- `api/auth_models.py`
- `api/routers/aggregation.py`
- `api/core/aggregation.py`
- `api/tests/test_auth_api.py`
- `api/tests/test_aggregation_api.py`

### Minimal sign-up acceptance criteria

- New `POST /api/auth/signup` endpoint exists.
- Duplicate email returns `409`.
- Successful sign-up creates user and session cookie.
- `GET /api/auth/session` after sign-up returns `mode=authenticated` with the new user.
- Password is not stored plaintext.
- Existing login tests continue passing.

### Minimal ownership acceptance criteria

- Account-created workspace/upload is associated with current user.
- Another authenticated user cannot read/update/delete/upload into that workspace.
- Existing tests either use authenticated bootstrap account or create test accounts.
- Demo sessions still cannot use authenticated-only upload endpoints.

## Release Sequencing

### PR 1: UX language + demo-first landing

Scope:

- Consumer-facing copy cleanup.
- Demo CTA becomes primary.
- Login/sign-up moved behind secondary account entry point.
- If sign-up backend is not ready, show honest “Create account coming soon.”
- Preserve current backend behavior.

Verification:

```bash
cd app && npm run lint -- --format stylish && npm test && npm run build
```

### PR 2: Minimal sign-up

Scope:

- Add backend sign-up endpoint.
- Add frontend sign-up form.
- Consumer role/account language.
- Tests for sign-up, duplicate account, session hydration.

Verification:

```bash
uv run pytest -q api/tests/test_auth_api.py --tb=short
cd app && npm test && npm run build
```

### PR 3: User-owned workspace persistence

Scope:

- Add ownership metadata/model.
- Enforce workspace/upload ownership.
- Update list/create/upload/update/delete APIs.
- Add cross-user access tests.

Verification:

```bash
uv run pytest -q api/tests/test_auth_api.py api/tests/test_aggregation_api.py api/tests/test_harmonize_api.py --tb=short
cd app && npm test && npm run build
```

## Stop / Report Rules for Implementation Agents

Stop and report if:

- A change would require a database migration that risks existing demo data.
- Ownership cannot be enforced without a larger aggregation storage refactor.
- Tests require real external services or secrets.
- The implementation would expose uploaded files across users.

Do not:

- Push to `main` directly.
- Commit unrelated `package-lock.json` or demo zip changes unless intentionally required.
- Add a new auth provider or external dependency without explicit approval.
- Store plaintext passwords.
- Make demo users able to upload/delete source files.

---

# Addendum: Three-Mode Entry Model

## Why this addendum exists

The phrase “demo” is doing too much work. We need to separate three distinct user intents:

1. “Show me a guided sample.”
2. “Let me try the real harmonization pipeline with my own files without creating an account.”
3. “Let me save my health-record workspace and come back later.”

These should become three first-class product modes instead of one awkward demo/auth split.

## Mode 1: Prepared Sample Demo

**User promise:** Explore Atlas with synthetic sample records. No upload required.

**Primary audience:** Judges, evaluators, first-time visitors, sales demos.

**Data posture:**

- Uses only synthetic/sample data bundled with the app.
- Safe to persist as fixtures.
- No user-provided data.

**UX language:**

- “Explore sample demo”
- “Prepared sample chart”
- “Synthetic records”

**Avoid:**

- “Demo access posture”
- “Clinician mode”
- “Unlock”

## Mode 2: Guest Harmonization

**User promise:** Upload your own health-record files, preview the harmonized structure, and download a portable output without creating an account.

**Primary audience:** Users who want to test the pipeline before trusting us with an account; reviewers who want to see data harmonization work on non-sample files.

**Data posture:**

- Temporary server-side workspace scoped to a signed guest session/run id.
- Files and derived outputs expire automatically.
- User must download the output or create an account to save it.
- Guest runs should never silently become durable account workspaces.

**Recommended TTL:**

- Default: 24 hours.
- Configurable with env var, e.g. `GUEST_HARMONIZATION_TTL_HOURS`.
- Lower TTL in production is acceptable if clearly disclosed.

**Storage shape:**

```txt
data/guest-harmonization/{guest_run_id}/
  manifest.json
  uploads/
  derived/
  outputs/
```

**Manifest shape:**

```json
{
  "run_id": "guest_...",
  "mode": "guest",
  "created_at": "...",
  "expires_at": "...",
  "uploaded_files": [],
  "outputs": [],
  "status": "ready|processing|completed|expired|failed"
}
```

**Initial endpoints:**

```http
POST /api/guest-harmonization/runs
GET  /api/guest-harmonization/runs/{run_id}
POST /api/guest-harmonization/runs/{run_id}/uploads
POST /api/guest-harmonization/runs/{run_id}/process
GET  /api/guest-harmonization/runs/{run_id}/output
DELETE /api/guest-harmonization/runs/{run_id}
```

For MVP, `process` may reuse existing upload preview/extraction/harmonization primitives and return a transparent “candidate structure” even if not all file types are deeply parsed.

**Output contract:**

Guest mode should produce a portable package:

```json
{
  "schema_version": "atlas.harmonized_record.v1",
  "created_at": "...",
  "source_files": [],
  "patient": {},
  "facts": [],
  "provenance": [],
  "quality_issues": []
}
```

The key product point is portability: the user can leave with a structured artifact.

**Required user-facing disclosure:**

> Guest uploads are processed in a temporary workspace and automatically deleted. Download your output or create an account to save your workspace.

**Security/privacy requirements:**

- Guest run ids must be unguessable.
- Guest data must not be listed globally.
- Guest data must not be accessible from another guest run id.
- Guest uploads must have size/type limits.
- Guest workspaces must have a cleanup path.
- Guest mode must not share storage with persistent account workspaces unless explicitly converted.

## Mode 3: Account Workspace

**User promise:** Create an account to save private health-record workspaces, upload records, return later, and export portable structured outputs.

**Data posture:**

- Durable server-side workspace.
- Must be scoped by `user_id`.
- Requires ownership enforcement before production use.
- User should eventually have delete/export controls.

**UX language:**

- “Log in / Sign up”
- “Save my workspace”
- “My records”
- “Private account workspace”

## Landing Page Target

The landing page should expose three clear cards/CTAs:

1. **Explore sample demo**
   - Synthetic records, fastest guided path.

2. **Try with my files**
   - Temporary guest harmonization, downloadable output, no account.

3. **Log in / Sign up**
   - Persistent saved workspaces.

Suggested copy:

> Choose how you want to try Atlas.
>
> Explore synthetic sample records, run a temporary harmonization with your own files, or sign in to save private record workspaces.

## Implementation sequencing

### PR A: Landing model update

- Update landing page from two-entry model to three-entry model.
- Add “Try with my files” CTA.
- If guest backend is not ready, route to an honest placeholder explaining temporary harmonization is being wired.

### PR B: Guest harmonization backend MVP

- Add temporary guest-run service and routes.
- Store uploads/manifest/output under `data/guest-harmonization`.
- Add TTL/expiration logic.
- Add tests for create/upload/process/output/delete/expired access.

### PR C: Guest harmonization UI

- Add guest upload page.
- Show temporary workspace disclosure.
- Support download/export.
- Add “Create account to save” CTA once signup/account flow exists.

### PR D: Account workspace ownership

- Add owner metadata/ACLs to persistent aggregation profiles/uploads.
- Ensure account mode is truly private per user.

## Codex worker guidance

Do not merge guest harmonization into existing demo patient code. Treat it as a separate mode with separate copy and separate storage. Do not promise persistence in guest mode.

## Caspian / Plugins Access Rules Across Modes

Caspian and Plugins should not be treated as globally locked behind account auth. They serve different purposes depending on the entry mode.

### Prepared sample demo

**Allowed:** Yes — showcase Caspian and selected Plugins against synthetic sample records.

**Purpose:**

- Demonstrate the product vision without forcing account creation.
- Let reviewers see agent/plugin workflows in context.
- Make the prepared sample patients feel like real workspaces.

**Constraints:**

- Synthetic/sample records only.
- Read-only or simulated side effects.
- No real outbound actions.
- No durable user-owned writes.
- No user uploads.
- Plugin actions that would normally mutate/send/register should display demo-safe simulated outcomes or be explicitly disabled with clear copy.

Suggested copy:

> You’re viewing a synthetic sample workspace. Plugin actions are shown in demo-safe mode and do not affect real patient data.

### Guest harmonization

**Allowed:** Not initially, except possibly a narrow read-only summary of the temporary output.

**Purpose:**

- Keep guest mode focused: upload files, generate a portable harmonized output, inspect/download it.
- Avoid introducing broad agent/plugin permissions before temporary-session boundaries are mature.

**Constraints:**

- No full Caspian workspace persistence.
- No plugin run history persistence.
- No real outbound actions.
- No durable artifacts after TTL expiration.

Future extension:

- Add a lightweight “summarize my harmonized output” assistant panel once guest-run isolation and cleanup are solid.

### Logged-in account workspace

**Allowed:** Yes — full personal use once account/workspace ownership is enforced.

**Purpose:**

- Caspian and Plugins operate on saved user-owned workspaces.
- Plugin runs, artifacts, conversations, exports, and history can persist.

**Requirements before production use:**

- Account signup/login.
- User-owned workspace ACLs.
- Per-user upload/profile ownership enforcement.
- Durable plugin/Caspian run storage scoped by `user_id` and workspace id.
- Delete/export controls.

### Summary matrix

| Mode | Caspian / Plugins | Data posture |
|---|---|---|
| Prepared sample demo | Yes, showcase/read-only/simulated | Synthetic fixtures only |
| Guest harmonization | Not initially, or limited output summary | Temporary TTL guest run |
| Logged-in account | Yes, full personal workspace use | Durable user-owned storage |

Implementation note: do not remove Caspian/Plugins from prepared demo mode. The account gate applies to real/persistent/personal usage, not to synthetic showcase usage.
