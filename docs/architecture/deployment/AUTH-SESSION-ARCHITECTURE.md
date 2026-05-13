# EHI Ignite Auth + Session Architecture Plan

Date: May 10, 2026
Project: EHI Ignite Challenge
Status: Planning document for a major application refactor

## Why This Needs To Happen Now

The product has moved past a pure data-lab prototype. We now have:

- a shared Atlas shell
- module switching across Explorer, Caspian, plugins, and patient views
- explicit demo-patient gating in the frontend
- backend assistant and plugin runtimes that are starting to behave like real product surfaces

What we still do not have is a real application boundary. Today:

- the backend API is effectively open
- frontend access state is stored locally, not authenticated
- there is no durable user identity
- there is no trusted session model
- there is no per-user audit trail for patient access, outbound actions, or assistant use
- patient access is still too close to route state and local browser state

That is acceptable for a prototype milestone, but it is the wrong base for the next wave of product work. If we keep building on top of demo-only access control, navigation, patient context, approvals, and plugins will become harder to reason about and harder to secure later.

This refactor should establish the app’s real operating model:

1. Who is the user?
2. What are they allowed to access?
3. How is that access established and revoked?
4. How is patient context attached to a user session?
5. How are actions audited?

## Current State

### Frontend

- `AccessContext` is a useful prototype gate, but it is not authentication.
- Access mode is derived from local browser storage.
- Demo patient access and `authenticated` mode share the same client-side abstraction.
- Route protection is UX-level only.
- Module navigation now preserves patient context better, but that context is not backed by a trusted server session.

### Backend

- FastAPI does not have a first-class auth subsystem.
- Most API routes do not require an authenticated principal.
- There is no user table, session table, role model, or org model.
- There is no central authorization dependency applied across routers.
- Assistant, plugin, and patient-data access are not consistently tied to a user identity.

### Deployment / Runtime

- The app is still positioned as a competition prototype.
- We do not yet have production-grade identity, key rotation, session revocation, or audit guarantees.
- There is no formal split between anonymous landing behavior, demo mode, and authenticated clinician mode.

## Product Goals

We need an auth and session model that makes the application feel real without overbuilding the wrong enterprise stack too early.

The system should support:

- a true login flow
- persistent authenticated sessions across app visits
- a clean distinction between demo mode and real authenticated use
- route-level and API-level access control
- patient context that is attached to the authenticated user session
- auditability for patient access, assistant usage, exports, and plugin actions
- a path to future enterprise identity and SMART on FHIR integration

## Non-Goals For The First Refactor

Do not treat this first implementation as the final enterprise IAM platform.

Out of scope for phase 1:

- full hospital SSO integration
- vendor-specific SMART on FHIR launch flows
- multi-tenant enterprise admin consoles
- fine-grained ABAC policy engines
- external IdP migration during the first cut

Those should remain possible later, but they should not block a clean first application auth model now.

## Recommended Product Model

Use three explicit access modes:

1. `anonymous`
2. `demo`
3. `authenticated`

### Anonymous

- Can see the landing page and product framing.
- Cannot load patient data.
- Cannot open patient-specific modules in a live state.
- Can be prompted to sign in or start demo mode.

### Demo

- Can access a constrained demo dataset only.
- Must be visually labeled as demo mode at all times.
- Should never be conflated with a real signed-in clinician session.
- Should use its own demo-scoped session semantics, even if the UX feels lightweight.

### Authenticated

- Represents a real user principal.
- Can maintain a durable session.
- Can access non-demo patient data according to policy.
- Can create assistant sessions, plugin runs, exports, and other auditable actions under identity.

## Recommended Technical Direction

### Authentication Strategy

For the next build, use app-native accounts with server-managed sessions.

Recommendation:

- invite-only accounts for now
- email + password login to start
- optional magic-link or SSO later
- HTTP-only secure session cookies, not localStorage bearer tokens

Why this path:

- simplest trustworthy application boundary
- works with FastAPI cleanly
- aligns with browser-first product behavior
- avoids exposing auth tokens to frontend JavaScript
- gives us revocation, expiry, and server-side session inspection
- does not block later migration to OIDC or SMART-backed delegated access

### Session Strategy

Use server-side sessions with a signed opaque session id in a cookie.

Cookie properties:

- `HttpOnly`
- `Secure`
- `SameSite=Lax` for normal app navigation, revisit `Strict` after UX testing
- short idle timeout
- bounded absolute lifetime

Session records should store:

- session id
- user id
- created at
- last seen at
- expires at
- revoked at
- ip hash or ip metadata
- user agent summary
- session type: `demo` or `authenticated`
- current patient context if we choose to persist it server-side

## Recommended Data Model

Add first-class persistence for identity and access.

Core tables:

- `users`
- `organizations`
- `memberships`
- `sessions`
- `audit_events`
- `patient_access_grants` or equivalent policy table
- `user_preferences`

Suggested minimum fields:

### `users`

- `id`
- `email`
- `password_hash`
- `display_name`
- `status` (`invited`, `active`, `disabled`)
- `created_at`
- `last_login_at`

### `organizations`

- `id`
- `name`
- `type`
- `created_at`

### `memberships`

- `id`
- `user_id`
- `organization_id`
- `role` (`admin`, `clinician`, `analyst`, `reviewer`)

### `sessions`

- `id`
- `user_id`
- `mode`
- `created_at`
- `last_seen_at`
- `expires_at`
- `revoked_at`
- `user_agent`
- `ip_address_hash`

### `audit_events`

- `id`
- `user_id`
- `session_id`
- `patient_id`
- `event_type`
- `event_payload`
- `created_at`

### `user_preferences`

- `user_id`
- `last_selected_patient_id`
- `last_module`
- `ui_preferences`

## Authorization Model

Authentication and authorization need to be separate.

Minimum authorization rules:

- anonymous users cannot load patient data
- demo users can only access the demo dataset
- authenticated users can access approved patient datasets
- outbound or high-risk actions require stronger checks than read-only browsing

Action classes:

1. Read patient data
2. Start assistant session
3. Start plugin run
4. Export or download patient artifacts
5. Trigger outbound actions or external connector writes
6. Administer users, orgs, or access policy

The plugin runtime and approval flows should eventually consume the same principal and audit model rather than inventing their own identity abstractions.

## Frontend Refactor Plan

### Replace Prototype Access State

`AccessContext` should evolve from a local gate into a session-aware app auth context.

It should:

- bootstrap from `GET /api/auth/session`
- expose `anonymous`, `demo`, and `authenticated`
- hold the trusted user profile
- hold session metadata
- hold patient context
- support `signIn`, `signOut`, `enterDemo`, `exitDemo`, `setActivePatient`

### Route Design

Use explicit route posture:

- public pages: landing, learn, marketing, auth
- demo-only or demo-capable flows
- authenticated clinician flows

Modules should not self-infer access from URL params. They should consume a trusted app-level auth/session state and redirect or render start pages accordingly.

### First-Open UX

After this refactor, first-open behavior should become:

1. user lands on public gate
2. user chooses `Sign in` or `Try demo`
3. authenticated users land in a clean start page with no patient loaded yet, unless a safe last-context restore is intentional
4. patient selection becomes an explicit step within a trusted session
5. module shells only hydrate patient views after policy checks succeed

## Backend Refactor Plan

### Add Auth Router + Service Layer

Add a dedicated auth subsystem under `api/`.

Suggested structure:

- `api/routers/auth.py`
- `api/core/auth/`
- `api/models/auth.py` or a split models package
- DB migrations for identity tables

Suggested endpoints:

- `POST /api/auth/login`
- `POST /api/auth/logout`
- `GET /api/auth/session`
- `POST /api/auth/demo`
- `POST /api/auth/demo/exit`
- `POST /api/auth/select-patient`

Potential later endpoints:

- `POST /api/auth/invite`
- `POST /api/auth/password/reset`
- `POST /api/auth/oidc/callback`

### Add Shared Dependencies

Introduce FastAPI dependencies like:

- `require_authenticated_user`
- `require_demo_or_authenticated_user`
- `require_patient_access`
- `require_role("admin")`

Then apply them consistently across routers rather than relying on frontend gating.

### Audit Layer

Every sensitive action should emit an audit event:

- login success/failure
- logout
- demo entry
- patient selection
- patient chart open
- assistant question asked
- export generated
- plugin run started
- outbound approval granted

The goal is not only security. It also gives product visibility into actual usage patterns.

## Storage Recommendation

Do not anchor this system to localStorage or in-memory-only state.

Preferred path:

- PostgreSQL in production
- SQLite allowed for local development only if we keep a migration path clean

If the current app does not yet have a production relational store beyond SQLite usage for traces and runtime state, the auth subsystem is a good forcing function to standardize that decision.

## Security Baseline

This build should establish a minimum real application security posture:

- password hashing with Argon2 or bcrypt
- CSRF protection for cookie-backed session mutation endpoints
- secure cookie flags
- session expiry and revocation
- brute-force rate limiting on login
- structured audit logs
- no patient data in public routes or anonymous preload paths
- no trusting frontend-only role or patient state

## Integration With Existing Product Areas

### Caspian

- assistant sessions should be attributable to a user and a patient
- traces should be linkable to the authenticated principal
- saved conversations should become per-user artifacts

### Plugins

- plugin runs should inherit user identity and patient access checks
- outbound approvals should reference the authenticated actor
- connector policy can later incorporate org-level credentials and delegated user credentials

### Explorer / Patient Record

- patient browsing should require a trusted session
- patient context should be shared intentionally across modules, not leaked through query strings alone

## Rollout Plan

### Phase 0: Design + Schema

- finalize auth/session model
- choose database path
- define core tables
- define route posture and access modes
- define audit event taxonomy

### Phase 1: Backend Auth Foundation

- implement auth tables and migrations
- implement password hashing and session creation
- add auth/session endpoints
- add auth dependencies and protect patient-data routes
- add audit events

### Phase 2: Frontend Session Wiring

- replace prototype access bootstrapping with session bootstrap
- add login page and logout flow
- preserve explicit demo mode
- add authenticated patient selector flow
- update navigation and start-state behavior

### Phase 3: Product Surface Integration

- wire authenticated principal into Caspian
- wire authenticated principal into plugin runtime
- connect patient selection to backend session state or trusted access checks
- update exports and downloads to require authenticated context

### Phase 4: Hardening

- rate limits
- CSRF verification
- admin invite flow
- session management UI
- audit review views
- preparatory abstraction for future OIDC / SMART on FHIR support

## Migration Guidance

Do not try to swap the full product in one step without compatibility planning.

Safer migration pattern:

1. keep `AccessContext`, but make it session-backed
2. introduce auth endpoints and bootstrap flow
3. preserve demo mode behind explicit server-backed semantics
4. gradually move patient routes from client trust to API trust
5. remove legacy local-only access assumptions after coverage is in place

## Testing Plan

### Backend

- unit tests for auth service
- login/logout/session lifecycle tests
- protected-route access tests
- session expiry and revocation tests
- audit emission tests
- demo-vs-authenticated policy tests

### Frontend

- auth bootstrap tests
- login/logout flow tests
- route guard tests
- patient selection tests
- module-switch preservation tests under authenticated mode
- demo banner and demo constraints tests

### End-to-End

- anonymous user cannot access patient data
- demo user can only access demo patient paths
- authenticated user can sign in, pick patient, switch modules, and remain in session
- logout fully clears trusted access

## Recommended Decision

Build a real app auth layer now, but keep it narrow:

- app-native invite-only accounts
- server-managed HTTP-only cookie sessions
- explicit demo mode as a separate access posture
- centralized authorization dependencies in FastAPI
- audit-first treatment of patient access and assistant/plugin actions

That is the right middle ground between a throwaway prototype gate and an overbuilt enterprise identity program.

## What Success Looks Like

When this refactor is complete:

- the app opens in a true public state
- the user signs in or explicitly enters demo mode
- patient data does not load until the server trusts the session
- module navigation preserves context under a real user session
- assistant and plugin activity are attributable to a user and patient
- the system has a credible foundation for enterprise identity and SMART on FHIR later

This is the application boundary the product now needs.
