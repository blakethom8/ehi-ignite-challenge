# First-Class Application Review Checklist

Date: May 10, 2026
Project: EHI Ignite Challenge
Status: Review plan for the next application hardening pass

## Goal

Re-review the entire Atlas application so it behaves like a first-class product application rather than a demo-guided prototype. The output of this review should be a prioritized fix list, a verified route-by-route audit, and a clear set of product and architectural changes needed before the next build phase.

This review should assume:

- auth and session handling now exist and must be exercised as real application infrastructure
- demo access should behave like a thin access posture, not a separate product architecture
- patient data should only appear after explicit access is established
- every major module must be tested both as a page and as part of a full user flow

## Primary Review Standard

The app should feel like:

- a coherent product with clear entry, identity, and navigation
- a trustworthy clinical review tool with real data wiring
- a system with consistent loading, empty, locked, and error states

The app should not feel like:

- a loose collection of prototype pages
- a route map that only makes sense to the builder
- a demo shell that depends on hidden mocks or fragile page-local assumptions

## Review Principles

1. Review real flows, not just isolated pages.
2. Prefer real backend wiring over frontend-only assumptions.
3. Treat demo mode as a constrained session type, not a parallel application.
4. Fail closed on patient access, but remain clear and usable.
5. Reduce legacy redirects and naming drift where they confuse the current product story.

## Core Questions

1. Does the app have a clear first-open experience for anonymous, demo, and authenticated users?
2. Does top-level navigation preserve context and move users to the right start surfaces?
3. Does each module open to a simple, comprehensible first state before exposing deeper tools?
4. Is patient context preserved, visible, and correctly enforced across module switching?
5. Are FHIR Charts, Caspian, Plugins, Patient Record, and informational pages wired to the intended backend data and runtime pipelines?
6. Are there any remaining fixture, mock, or placeholder behaviors in normal app mode that make the product feel fake?
7. Are loading, empty, error, and locked states coherent across the app?

## Review Scope

### 1. Entry, Identity, And Access

Routes to review:

- `/`
- `/records-pool`
- `/guided-tour`

Checklist:

- [ ] Landing explains the product clearly before patient access begins.
- [ ] Anonymous users cannot accidentally enter patient-specific live surfaces.
- [ ] Sign-in flow is understandable and visually first-class.
- [ ] Demo access is explicit, labeled, and obviously limited.
- [ ] Demo access does not create feature-level branching outside the auth boundary.
- [ ] Session restoration behaves correctly on refresh and revisit.
- [ ] Locked routes explain what the user needs to do next.

### 2. Global Navigation And Information Architecture

Surfaces to review:

- top bar
- module bar
- route redirects
- patient context indicator

Checklist:

- [ ] Primary modules are named and ordered in a way that makes sense for a first-time clinical user.
- [ ] Navigation does not drop patient context unexpectedly.
- [ ] Navigation does not route users into dense subpages as a first-open state.
- [ ] Redirects from legacy routes support the current IA instead of adding confusion.
- [ ] Active location, module, and patient state are visually obvious.
- [ ] Informational pages like architecture or about-style content are reachable without entering patient workflows.

### 3. Patient Record Module

Routes to review:

- `/patient-record`
- `/patient-record/methodology`
- `/patient-record/sources`
- `/patient-record/harmonize`
- `/patient-record/cleaning`
- `/patient-record/workspaces`
- `/patient-record/publish`
- `/patient-record/context`

Checklist:

- [ ] First-open state is simple and explains the module purpose.
- [ ] Uploaded or curated patient record workflows still function under auth/session gating.
- [ ] Harmonization and context surfaces match real backend capabilities.
- [ ] No patient-specific screen renders misleading data when access has not been established.

### 4. FHIR Charts Module

Routes to review:

- `/fhir-charts`
- `/fhir-charts/timeline`
- `/fhir-charts/labs`
- `/fhir-charts/history`
- `/fhir-charts/care-journey`
- `/fhir-charts/journey`
- `/fhir-charts/corpus`
- `/fhir-charts/safety`
- `/fhir-charts/immunizations`
- `/fhir-charts/conditions`
- `/fhir-charts/procedures`
- `/fhir-charts/clearance`
- `/fhir-charts/anesthesia`
- `/fhir-charts/distributions`
- `/fhir-charts/interactions`
- `/fhir-charts/assistant`
- `/fhir-charts/patient-data`

Checklist:

- [ ] Overview page opens as the right first surface.
- [ ] Patient selection and route state drive real data consistently across tabs.
- [ ] Charts and summary views agree with the underlying patient record.
- [ ] Assistant route uses the intended backend assistant path and session identity.
- [ ] Empty, sparse, or no-data clinical states are handled gracefully.
- [ ] No route is still depending on demo-only assumptions in normal mode.

### 5. Caspian Clinical Workspace

Routes to review:

- `/caspian`
- `/caspian/sessions/:sessionId`

Checklist:

- [ ] Caspian opens to the right first-open workspace state.
- [ ] The live assistant path is actually wired, not fixture-backed.
- [ ] Workspace panes, inspector state, traces, and citations behave coherently.
- [ ] Session history and patient context remain stable across refresh and navigation.
- [ ] Locked or no-patient states are product-quality, not developer placeholders.

### 6. Plugin Workspace And Marketplace

Routes to review:

- `/workspaces`
- `/workspaces/:pluginId`
- `/workspaces/:pluginId/sessions/:sessionId`

Checklist:

- [ ] Marketplace or plugin index communicates what these tools are before entering a run.
- [ ] Plugin start pages are simple and trustworthy.
- [ ] Live runs are wired to the shared workspace shell correctly.
- [ ] Consent, approvals, chat, files, workbench tabs, and artifacts behave consistently.
- [ ] Built-in plugin UIs feel app-native, not bolted on.
- [ ] Missing data, failed runs, or disconnected backend states surface cleanly.

### 7. Informational And About-Style Pages

Routes to review:

- `/architecture`
- `/using-atlas`
- `/using-atlas/pipeline`
- `/using-atlas/pdf-extraction`
- `/using-atlas/harmonization`
- `/using-atlas/trustworthy-ai`
- `/using-atlas/standards`
- `/learn`
- related internal tool pages that remain user-visible

Checklist:

- [ ] The user can access an about-style explanation of Atlas without entering patient workflows.
- [ ] Informational pages are clearly separated from core clinician tasks.
- [ ] Internal tools that are still exposed do not confuse the primary product narrative.
- [ ] Route naming and page framing match the current product story.

### 8. Backend And Pipeline Wiring

Endpoints and systems to verify:

- `/api/auth/session`
- `/api/auth/login`
- `/api/auth/demo`
- `/api/patients`
- patient detail and canonical endpoints
- patient context APIs
- assistant APIs
- plugin runtime APIs
- aggregation APIs where still exposed

Checklist:

- [ ] Normal app mode uses real API data rather than silent frontend fallbacks.
- [ ] Demo-mode exceptions are explicit and contained.
- [ ] Patient authorization is enforced server-side.
- [ ] Session identity flows into assistant, plugin, patient context, and audit surfaces.
- [ ] Core pipelines return data that matches what the UI claims to show.
- [ ] There are no critical mismatches between page labels and actual backend behavior.

### 9. Product Quality States

Checklist:

- [ ] Loading states look intentional and consistent.
- [ ] Empty states explain what is missing and what to do next.
- [ ] Error states are actionable and not raw developer failures.
- [ ] Locked states explain why access is blocked.
- [ ] Success feedback exists where the user initiates meaningful actions.
- [ ] Browser refresh and deep-link behavior are stable.

### 10. Demo Containment

Checklist:

- [ ] Demo data is not over-represented in the codebase.
- [ ] Demo selection is treated as a session choice, not app-wide special logic.
- [ ] Shared UI components do not branch excessively on demo state.
- [ ] Mock mode remains limited to explicit frontend-only development mode.

## Review Method

For each surface:

1. Verify first-open behavior from an anonymous state.
2. Verify the same flow in demo mode.
3. Verify the same flow in authenticated mode where supported.
4. Confirm patient selection, route state, and backend state stay aligned.
5. Record mismatches as one of:
   - `P0`: broken or unsafe
   - `P1`: core product confusion or missing wiring
   - `P2`: quality gap, polish issue, or cleanup

## Expected Deliverables

- a route-by-route findings log
- a prioritized remediation backlog
- a short IA recommendation if navigation still feels too complex
- a list of remaining demo-only assumptions to remove
- a verified statement of which modules are fully live versus partially staged

## Exit Criteria

This review is complete when:

- every major route has been exercised intentionally
- the app no longer presents as a demo-guided shell in normal use
- patient access and session behavior are coherent
- FHIR Charts, Caspian, Plugins, Patient Record, and informational pages are all accounted for
- the next implementation wave can proceed from a trusted, documented product baseline
