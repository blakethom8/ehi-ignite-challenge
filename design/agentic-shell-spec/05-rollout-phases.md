# Rollout Phases

This file translates the shell vision into an implementation sequence that can
fit the current codebase.

## Phase 1: Shared Shell Foundation

Goal: establish the durable harness before migrating product areas.

### Deliverables

- one shared workspace shell component
- pane layout persistence
- global rail + session rail model
- workspace header contract
- shared pane roles: chat, preview, files, inspector, artifacts, settings
- command palette and shell-level keyboard patterns

### Code Direction

- expand the existing full-screen workspace frame pattern
- make workspace definitions drive pane availability and default layout
- stop treating the shell as Trial Finder-specific

## Phase 2: Clinical Insights As First-Party Workspace

Goal: turn Clinical Insights into the flagship agentic workspace.

### Deliverables

- workspace launcher surface for clinical workflows
- patient brief / evidence / artifact panes
- workflow triggers in the header
- migration of key clinical flows from separate pages into workspace states

### Candidate Migrations

- pre-op review
- medication safety
- longitudinal synthesis
- context package management
- chart-grounded assistant

## Phase 3: Marketplace As Workspace Library

Goal: replace concept-card marketplace behavior with a real workspace package
model.

### Deliverables

- workspace library / install flow
- package manifest inspection
- launch flow against a chosen patient workspace
- permission and boundary review surfaces
- package-specific app panes inside the shared shell

### Candidate Packages

- Trial Finder
- Medication Access
- Second Opinion
- Payer Coverage Check

## Phase 4: Retire Route-Heavy Module Sprawl

Goal: simplify the product map and reduce redundant scaffolding.

### Deliverables

- old module pages retired, embedded, or rewritten as workflow states
- fewer top-level routes
- clearer relationship between support areas and workspaces
- design system aligned around the shell rather than around section pages

## Phase 5: Desktop-Grade Enhancements

Goal: add deeper operating-system-like behaviors without changing the core
product model.

### Deliverables

- detached panes or multi-window support, if warranted
- stronger local filesystem integration
- background workspace processes
- deeper portal automation or local execution modes

This phase can happen either in the browser shell or in a local wrapper later.

## What This Sequencing Protects

This order avoids rebuilding the entire product at once.

1. Build the shared frame
2. Prove it with Clinical Insights
3. Expand it through Marketplace packages
4. Remove the old route-first structure
5. Add local-app behaviors only if they meaningfully improve the product

That keeps the redesign grounded in the current codebase while still moving
toward the new north star.
