# UX Cleanup Review

Date: May 11, 2026
Project: EHI Ignite Challenge / Atlas
Scope: product UX review focused on first-time use, navigation clarity, module entry states, and demo/auth behavior

## Summary

The app is materially stronger than it was a few days ago: it now has a real access gate, better patient-context preservation, and a more coherent shell. It no longer feels like a pure route map. But it still does not fully feel like a first-class application.

The main reason is not visual quality. The main reason is that the product still mixes three different modes in the same visible surface:

1. product-facing application flows
2. technical documentation / architecture explanation
3. internal tools / evaluation harnesses

That makes the app understandable to the builder, but still somewhat unstable and confusing for a first-time user.

## Highest-Priority Cleanup List

### P0

1. Fix the demo-entry race in [DemoPatientPicker.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/components/atlas/DemoPatientPicker.tsx:1).
The picker calls `enterDemoPatient()` and then navigates immediately without awaiting session establishment. In browser review, this produced initial `401` calls against `/api/patients/demo-high-risk/overview` and `/api/canonical/demo-high-risk/summary` before the session fully settled. This is a trust problem, not just a loading problem.

2. Replace unauthorized plugin-marketplace behavior with a real locked or error state in [Index.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/pages/Plugins/Index.tsx:1).
In live review, `/workspaces` returned `401` on `/api/plugins/installed`, but the screen still resolved to “No plugins installed. Run `uv run python scripts/build_example_plugins.py`…”. That is misleading product copy and leaks a builder command into a user-facing route.

3. Remove or hide placeholder routes that are not real product surfaces.
[GuidedTour.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/pages/GuidedTour.tsx:1) is explicitly a future concept page, not a finished experience. It should not be reachable from the drawer as if it were a normal user destination.

### P1

4. Remove `Learn` / `Internal Tools` from primary product navigation.
The top nav and drawer still expose `/learn` as a peer to clinician modules through [App.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/App.tsx:84), [navigation.ts](/Users/blake/Repo/ehi-ignite-challenge/app/src/components/atlas/navigation.ts:3), and [PlatformDrawer.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/components/atlas/PlatformDrawer.tsx:1). The actual landing page for that section in [Overview.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/pages/InternalTools/Overview.tsx:1) is clearly an internal evaluation/tools area. It should move behind a secondary “Docs / Labs / Technical” boundary.

5. Consolidate `Architecture`, `Using Atlas`, and `Learn` into one clearer information model.
Right now these pages overlap:
- [PlatformArchitecture.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/pages/PlatformArchitecture.tsx:1)
- [GettingStarted.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/pages/UsingAtlas/GettingStarted.tsx:1)
- [InternalTools/Overview.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/pages/InternalTools/Overview.tsx:1)

Recommended split:
- `About Atlas` or `How Atlas Works`: product-level explanation
- `Technical Docs`: pipeline, standards, trustworthy AI, architecture
- `Labs / Internal Tools`: evals, coverage, conversion labs, ground-truth review

6. Reduce first-screen choice overload on [Landing.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/pages/Landing.tsx:1).
The landing page is visually strong, but it asks the user to process too many parallel choices at once:
- sign in
- choose demo patient
- open four modules
- read three trust/value cards
- decide whether to use the header CTA or the lower CTA

The first screen should drive one clear action:
- `Sign in`
- or `Continue with demo patient`

Module selection should come after access is established, not at the same decision depth.

7. Rename or clarify confusing module vocabulary in [PatientRecordLayout.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/pages/PatientRecord/PatientRecordLayout.tsx:1).
Inside `Patient Record`, the first nav item is labeled `FHIR Chart`, while there is also a top-level module called `FHIR Charts`. That creates a product-language collision:
- `Patient Record` sounds like the ingestion/canonical workflow
- `FHIR Charts` sounds like the chart-exploration module
- `FHIR Chart` inside `Patient Record` sounds like a third concept

This should be simplified so each label maps to exactly one mental model.

8. Improve loading and partial-loading states across module entry pages.
During review, `Patient Record` initially rendered a mostly blank workspace with a spinner before its content resolved. The shell itself is loading correctly, but the content stage still does not always explain what is happening. Spinner-only states should become:
- `Loading chart posture`
- `Fetching prepared chart`
- `Checking access`

9. Stop leaking technical dataset terms into product-facing routes.
Examples observed:
- `frontend_mock`
- `C-CDA/PDF conversion`
- `coverage checks`
- `pipeline tests`
- `seed the three examples`

These terms are acceptable in technical docs and internal tools, but not in primary product routes or normal empty states.

### P2

10. Tighten the left-rail copy in module start states.
The start states in `Patient Record`, `FHIR Charts`, and `Caspian` are directionally correct, but they still over-explain the intended architecture instead of helping the user take the next step. They should become shorter and more action-oriented.

11. Make the shell status model more explicit.
The current shell shows module, patient badge, and access mode, but it still lacks a single, simple product-status line like:
- `Signed in as Atlas Clinician`
- `Demo patient: Surgical Review`
- `Viewing prepared chart`

This would help reduce ambiguity when switching modules.

12. Rework the plugin-marketplace first impression.
The page in [Index.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/pages/Plugins/Index.tsx:1) opens with runtime/trust language before answering a simpler question: “What are these tools, and when would I use them?” The first screen should start with concrete use cases, then reveal boundary and approval detail.

13. Simplify the “Also” section in [SectionNav.tsx](/Users/blake/Repo/ehi-ignite-challenge/app/src/pages/UsingAtlas/components/SectionNav.tsx:1).
`Open patient explorer` and `Data lab reference` are reasonable links, but they collapse product, docs, and lab references into the same sidebar. This contributes to category drift.

## Route-Level Notes

### `/`

What works:
- strong visual design
- explicit access gate
- clear demo options

Needs cleanup:
- too many simultaneous CTAs
- too much explanatory copy before user action
- module cards appear before access is established

### `/records-pool`

What works:
- safe locked state for anonymous users

Needs cleanup:
- name still feels builder-oriented
- “pool” and “patient environments” are useful internally but not especially user-natural
- likely needs a simpler “Switch patient” framing after access exists

### `/patient-record`

What works:
- left rail makes the workflow explicit
- clear operational framing

Needs cleanup:
- temporary spinner-heavy content transition
- naming collision between `Patient Record`, `FHIR Chart`, and top-level `FHIR Charts`

### `/fhir-charts`

What works:
- summary-first concept is clear
- sidebar structure is understandable

Needs cleanup:
- start state still repeats demo gating language rather than focusing on chart review
- default no-patient view leaves large unused canvas space

### `/caspian`

What works:
- strong shell
- coherent protected-start concept

Needs cleanup:
- no-patient start state is clear but sparse
- could use a more product-like “what you can do here” preview

### `/workspaces`

Needs cleanup:
- unauthorized state is misleading
- first screen is too abstract
- should explain the concrete plugin set more directly

### `/using-atlas`

What works:
- strong documentation quality
- clear technical framing

Needs cleanup:
- should not be confused with onboarding
- some links still point users into product/lab surfaces without enough categorization

### `/learn`

Needs cleanup:
- explicitly internal
- should not be a primary product destination
- needs stronger separation from user-facing product navigation

### `/architecture`

What works:
- readable system explanation

Needs cleanup:
- overlaps heavily with `Using Atlas`
- should likely become a subpage of docs, not a near-peer to app entry

## Recommended Work Sequence

1. Fix the demo-entry race and marketplace unauthorized state.
2. Remove or hide `Guided tour` and demote `Learn / Internal Tools` from primary navigation.
3. Consolidate docs / architecture / labs information architecture.
4. Simplify landing to one primary action before module choice.
5. Clean up module naming, especially `Patient Record` vs `FHIR Charts` vs `FHIR Chart`.
6. Improve loading, locked, and empty states across module entry surfaces.
7. Remove remaining developer-facing copy from user-visible routes.

## Short Version

The app is now structurally credible, but it still needs one more cleanup pass to decide what it is:

- application
- documentation hub
- internal lab

Right now it is all three at once. The next UX pass should reduce that ambiguity more than it adds new features.
