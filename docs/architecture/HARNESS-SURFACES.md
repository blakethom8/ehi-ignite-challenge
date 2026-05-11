# Harness Surfaces: Pages, Workbench Apps, and Canvas Views

Status: build guidance for the Atlas / EHI agentic harness.

Audience:
- frontend engineers
- product / design collaborators
- backend engineers shaping workspace contracts

Related docs:
- `docs/architecture/AGENTIC-HARNESS.md`
- `design/agentic-shell-spec/01-shell-spec.md`
- `design/agentic-shell-spec/02-workspace-model.md`
- `app/src/components/atlas/README.md`

## 1. Why this doc exists

The redesign introduced a shared agentic shell, but we still need a stricter
build rule for the different UI surfaces inside that shell.

Without that rule, teams tend to blur together:

- top-level pages
- workbench app tabs
- side canvases
- inline widgets
- preview panes

That creates route sprawl, duplicate state, and fragile UI contracts.

This document defines the intended structure.

## 2. The core distinction

There are two ideas we want to borrow from products like Codex:

1. A **shared workbench / preview surface** for real application state
2. A **bounded embedded surface** for smaller tools and package-specific UI

In EHI, those become four concrete surface types.

## 3. The four surface types

### 3.1 Workspace page

This is the full agentic harness route.

Examples:
- `/caspian`
- `/caspian/sessions/:sessionId`
- `/workspaces/:pluginId`
- `/workspaces/:pluginId/sessions/:sessionId`

Responsibilities:
- enter the correct workspace family
- mount `AppShell` + `WorkspaceFrame`
- establish trust posture
- establish patient / plugin context
- own session selection and high-level run lifecycle

A workspace page is not where we should build lots of bespoke UI logic. It is
the container and router for the workspace.

Current code:
- `app/src/pages/Caspian/Workspace.tsx`
- `app/src/pages/Plugins/Workspace.tsx`
- `app/src/components/atlas/WorkspaceFrame.tsx`

### 3.2 Workbench app

This is the main "app page" inside the harness. It lives in the workbench
pane, usually as a tab.

Examples:
- pre-op briefing
- medication review artifact
- trial board
- packet draft
- manifest review
- JSON or diff viewer

Responsibilities:
- render the primary task artifact
- support dense interaction
- accept routed / selected context from chat, files, or inspector
- stay inside the tabbed workbench instead of spawning new top-level routes

Rule:

> If a surface makes sense as a tab next to files, evidence, or another
> artifact, it should be a workbench app, not a new product page.

### 3.3 Canvas view

The canvas is not the same thing as the workbench app.

A canvas is the structured run-state surface that accumulates intermediate
objects while the agent works.

Examples:
- trial criteria
- patient anchors
- shortlist candidates
- packet tasks
- summaries
- selected artifacts

Responsibilities:
- show the current run objects
- make steering inputs editable
- preserve structured state between chat turns
- reflect what the agent thinks is "in play" right now

The canvas is closer to a living sidecar than a standalone app.

Current seed:
- `app/src/pages/InternalTools/skills/TrialFinder/index.tsx`
- `docs/architecture/skill-runtime/TOOL-SURFACE.md`

### 3.4 Inline widget / embedded surface

This is the smallest UI unit.

Examples:
- approval card
- evidence card
- compact result list
- small embedded map / table / inspector launch point

Responsibilities:
- one tight task
- minimal state
- easy open/close/expand behavior
- hand off to workbench or canvas when the task becomes complex

This is where a future plugin-bundle contract should become more bridge-like
and portable.

## 4. What should become a route vs a tab vs a canvas

### Make it a route when

- it changes the workspace family
- it changes the trust posture
- it changes the primary shell context
- it needs its own session namespace
- the user would reasonably bookmark it as a distinct workspace

### Make it a workbench tab when

- it is one artifact among several
- it depends on the current session
- it should sit beside files, trace, and evidence
- it is opened from chat, files, or citations
- it should not replace the whole harness

### Make it a canvas when

- the agent is iteratively building up structured run state
- the user needs to steer criteria or selections while the run evolves
- the information is more operational than presentational
- the state should survive multiple tool calls and messages

### Make it an inline widget when

- the task is narrow
- the user needs a quick confirm / inspect / launch interaction
- the surface is disposable
- the user should escalate into workbench or canvas only if needed

## 5. Product rules

### 5.1 Caspian

Caspian should prefer:

- full workspace routes
- dense workbench artifacts
- evidence and review surfaces
- minimal always-on operational chrome

Caspian should not feel like a plugin package with a giant side canvas by
default. It is interpretation-first.

### 5.2 Plugins

Plugins can be more guided and more operational.

Plugins may bring:

- package-specific workbench tabs
- a more visible run canvas
- stronger consent / boundary surfaces
- package home views and workflow launchers

But they still live inside the same shell. A plugin should not fork the shell
layout for aesthetic reasons alone.

## 6. Build rules for this repo

### 6.1 Route ownership

Keep full harness routes in:

- `app/src/pages/Caspian/`
- `app/src/pages/Plugins/`

These route entry files should stay thin. Their job is to bind route params,
workspace identity, and shell state together.

### 6.2 Shared shell primitives

Keep shell-level primitives in:

- `app/src/components/atlas/`

This includes:

- pane chrome
- workbench tabs
- files / inspector / sessions
- trust-boundary indicators
- citation plumbing
- approval cards

Do not clone shell components per workspace unless the trust contract truly
requires different behavior.

### 6.3 Workspace-specific app surfaces

Prefer one folder per workspace package or first-party workflow for real app
surfaces.

Current acceptable locations:

- `app/src/pages/Caspian/`
- `app/src/pages/Plugins/`
- `app/src/pages/InternalTools/skills/`

Preferred long-term pattern for new work:

```text
app/src/workspaces/
  caspian/
    apps/
    canvas/
    fixtures/
    hooks/
  trial-finder/
    apps/
    canvas/
    fixtures/
    hooks/
```

This keeps route containers separate from task surfaces.

### 6.4 Canvas data ownership

Canvas state should be structured and tool-driven, not just ad hoc React state.

Use the frontend to render canvas objects, but keep the canonical model aligned
with typed runtime payloads.

Current contract seeds already exist:

- `app/src/types/skills.ts`
- `app/src/api/skills.ts`
- `docs/architecture/skill-runtime/TOOL-SURFACE.md`

Rule:

> The canvas is a rendered projection of workspace state, not a second hidden
> business-logic layer.

### 6.5 Workbench tab ownership

Workbench tabs should open from durable identifiers:

- citation id
- file ref
- artifact id
- manifest id
- canvas node id

Avoid anonymous tabs with local-only meaning when the same object should be
re-openable from chat or files.

## 7. Preview / local app contract

For local development we should think in terms of a stable preview contract,
not "some Vite page happens to be open."

Every meaningful workspace app should have:

- a deterministic startup command
- a deterministic port during development when practical
- a clear reload path
- a visible failed / disconnected state

Why this matters:

- the shell preview surface becomes reliable
- browser automation becomes less brittle
- collaborators can open the same app surface with less ceremony

This is especially important for workbench-heavy surfaces and future
desktop-posture testing.

## 8. Data tools vs render tools

Do not bury domain logic inside UI surfaces.

Use this split:

- **data tools** fetch, compute, mutate, and validate
- **render surfaces** display the resulting structured state

Examples:

- Caspian medication review logic belongs in backend or tool/runtime layers
- the workbench app renders the medication review artifact
- the canvas shows intermediate risk objects and user steering state

This is mandatory for auditability and makes it much easier to reuse the same
logic across:

- chat output
- workbench tabs
- canvas views
- exports

## 9. Anti-patterns

Do not:

- create a new top-level route for every workflow artifact
- make canvas state exist only inside one React component
- put core business logic inside a tab renderer
- duplicate shell layout code per plugin
- treat a preview pane as the product contract
- let a plugin UI silently widen scope beyond its declared workspace context

## 10. Practical examples

### Good

- A user clicks a citation in Caspian and the inspector opens on the evidence
  while the workbench keeps the active briefing tab.

- Trial Finder keeps candidate trials and anchor criteria in the canvas while
  the workbench shows a trial board artifact.

- A plugin home launches a run, then opens the resulting artifact in the
  workbench without leaving the workspace route.

### Bad

- Trial Finder gets its own totally different page layout outside
  `WorkspaceFrame`.

- A packet draft becomes a new route like `/packet-draft/:id` even though it
  only needs to be a workbench tab.

- The only copy of run state lives in component-local arrays that tools know
  nothing about.

## 11. Bottom line

Use this mental model:

- **workspace page** = the harness container
- **workbench app** = the main task surface
- **canvas** = the structured run-state sidecar
- **inline widget** = the smallest embedded control surface

If we hold that line, the shell stays coherent, plugins stay portable, and
future Codex-style preview / desktop wrapping stays possible without a major
re-architecture.
