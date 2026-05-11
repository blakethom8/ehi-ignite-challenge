# Workspace Model

## 1. Product Model

The shell stays stable. Workspaces vary.

A workspace package is the unit of product expression. It brings:

- context
- permissions
- pane definitions
- workflow triggers
- lightweight app surfaces
- templates
- artifacts
- export rules

This replaces the older idea that each product area should be a separate custom
React application with its own navigation logic.

## 2. Workspace Package Anatomy

At a conceptual level, every workspace package should define:

```yaml
id: trial-finder
kind: marketplace
title: Trial Finder
boundary: consented-external
default_layout:
  left: sessions
  center: chat
  right:
    - app
    - files
    - inspector
surfaces:
  - chat
  - app
  - files
  - artifacts
  - inspector
workflows:
  - launch-search
  - review-candidates
  - build-packet
context_sources:
  - patient workspace
  - skill manifest
  - local notes
  - external registries
artifacts:
  - ranked-shortlist
  - outreach-packet
exports:
  - markdown
  - json
  - shareable bundle
```

The exact technical shape can evolve, but the conceptual ingredients should not.

## 3. Workspace Classes

| Workspace Class | Purpose | Example |
|---|---|---|
| First-party clinical workspace | Atlas-owned clinical operating environment | Clinical Insights |
| Marketplace workspace | Installed or launched specialized workspace package | Trial Finder, Medication Access |
| Support workspace | Foundation data or QA work | Data intake, review, evaluation, tracing |

## 3.1 Shell Family Comparison

| Shell Family | Default Mood | What Stays Visible | What Usually Stays Secondary |
|---|---|---|---|
| Clinical Insights | Interpretation-first | chat, evidence-rich preview, files, artifacts | progress tracking, detailed logs, package mechanics |
| Marketplace workspace | Guided action-first | package identity, working folder, consent posture, module actions | deep provenance unless opened, editorial briefing chrome |

## 4. Clinical Insights Workspace

Clinical Insights should become the flagship first-party workspace.

### 4.1 Identity

- private by default
- deeply curated
- clinically opinionated
- grounded in Atlas-prepared patient context
- capable of running prepared workflows quickly

### 4.2 Core Surfaces

- chat
- patient brief / summary surface
- evidence reader
- workflow launcher
- artifacts
- files / context packages
- provenance access
- settings

### 4.2.1 Default posture

Clinical Insights is not the same thing as a cowork-style action workspace.

It should default to:

- a calmer clinical review posture
- dense evidence and artifact review
- less visible run management
- no progress panel by default
- optional trace / log access through review surfaces rather than always-on
  shell chrome

### 4.2.2 Shell cues

The Clinical Insights shell should communicate:

- private patient boundary first
- workflow triggers as reusable launchers, not giant cards
- one shared preview pane that can hold app, file, note, or settings tabs
- directory-style files and pinned objects
- trace and runtime detail available, but usually one click away

### 4.3 Example Workflows

- pre-op review
- medication safety review
- longitudinal synthesis
- chart-grounded Q&A
- handoff packet creation
- specialist briefing

These are no longer separate top-level product pages first. They are workflow
entry points inside the workspace.

## 5. Marketplace Workspace Model

Marketplace should shift from "cards for product concepts" to "library of
workspace packages."

### 5.1 Marketplace Responsibilities

- browse workspaces
- inspect manifest / permissions / boundary
- install or enable
- launch against a selected patient workspace
- review outputs and exports
- fork or customize when allowed

### 5.2 Marketplace Workspace Traits

- can bring a custom lightweight app pane
- can expose files, templates, and project state specific to the package
- may have outbound tools or consent gates
- should always show what leaves the private patient boundary
- can feel more guided or cowork-oriented than Clinical Insights
- should show stronger package identity than the first-party clinical shell
- should prefer module-specific actions over generic shell actions

### 5.2.1 Shell cues

The Marketplace shell should communicate:

- which package is running right now
- what the package is allowed to do
- what working-folder objects the package has produced or touched
- which guided actions are available next
- when consent or approval gates block outbound work

### 5.3 Example Marketplace Surfaces

- package README
- chat
- app pane
- pursuit / board pane
- artifact pane
- files pane
- permission / consent drawer
- working folder / package context panel
- optional run-state or progress panel when the workflow is truly action-heavy

## 6. Old Modules To New Homes

The older product map can be simplified by moving many existing pages into one
of three destinations: workflow, pane, or support area.

| Current Shape | New Home |
|---|---|
| Pre-Op Overview | Clinical Insights workflow |
| Clinical Trials / Trial Finder | Marketplace workspace |
| Medication Access | Marketplace workspace |
| Patient Memory | shared pane or reusable workspace asset |
| Context Library | files / library pane within Clinical Insights |
| Clinical module inventory pages | workspace launch / workflow catalog surfaces |
| Internal review pages | support workspaces or review shell |

## 7. Shared Rules Across Workspaces

Every workspace should obey the same core rules:

1. The chat knows the workspace context.
2. The shell can persist pane layout per workspace.
3. Files, artifacts, and citations are durable and inspectable.
4. Every workspace advertises its boundary clearly:
   private, consented external, or system/internal.
5. The user can export or carry the workspace state forward.
6. Files and assets should read like a directory or working folder, not a grid
   of fluffy cards.
7. The preview surface is shared. Apps, files, notes, artifacts, and settings
   should prefer opening as tabs inside one durable workbench surface.

## 8. Launch Flow

The preferred flow:

1. Select patient or source workspace
2. Choose workspace package
3. Inspect purpose, permissions, and outputs
4. Launch into shared shell
5. Run workflow or converse freely
6. Save, export, fork, or reopen later

This is a better mental model than "go to a module page and then maybe open an
assistant."

## 9. Package Portability

Portability should be explicit at the package level:

- export artifact only
- export workspace files and notes
- export structured state
- fork package config into a private variant

This matters both for customer trust and for the marketplace strategy. A
workspace should feel like a contained asset the user can take with them.

## 10. Migration Direction For The Frontend

At the UI layer, the long-term shape should move toward:

- one shared workspace shell route
- workspace definitions drive pane layout
- workflows drive surface configuration
- old standalone pages are retired or embedded

That lets the codebase grow by defining new workspace packages instead of
repeating navigation and layout scaffolding for each new workflow.
