# Agentic Shell Spec

Status: Draft vision package for the 2026 redesign of Atlas / EHI Ignite.

This folder defines the shift from a route-heavy collection of modules into a
single agentic shell with installable workspaces, coordinated panes, and a
clear portability story.

## Core Thesis

- The agentic harness is the product container, not a sidebar feature.
- Workspaces are packages that live inside the shell and bring their own
  context, panes, lightweight app surfaces, workflows, and export rules.
- Clinical Insights becomes the flagship first-party clinical shell:
  interpretation-first, private by default, and evidence-dense.
- Marketplace becomes a workspace library, installer, launcher, and consent
  boundary, with package workspaces that can feel more guided and
  cowork-oriented than the flagship clinical shell.
- Older "modules" mostly become workflows, presets, artifacts, and panes
  inside shared workspaces.

## Shell Families

The redesign package now treats Atlas as one shared harness with two distinct
workspace families:

- Clinical Insights family
  Calm, private, review-first, and centered on evidence, artifacts, and
  chart-grounded interpretation. Progress or run-state chrome stays minimal by
  default.
- Marketplace workspace family
  More action-oriented, more package-identified, and more comfortable showing
  working-folder state, consent posture, and guided run objects when the
  workflow requires them.

## Current Decisions Favored By This Package

- Browser-first, desktop-posture experience
- Docked panes instead of free-floating desktop windows
- Shared shell across first-party and marketplace workspaces
- Deep chat-to-pane coupling as a core interaction contract
- Ambient, branded "html-in-canvas" moments around the shell, not instead of it
- Strong export / fork / portability posture for every workspace

## Review Order

1. [01-shell-spec.md](./01-shell-spec.md)
2. [02-workspace-model.md](./02-workspace-model.md)
3. [03-browser-vs-local-app.md](./03-browser-vs-local-app.md)
4. [04-wireframes.md](./04-wireframes.md)
5. [05-rollout-phases.md](./05-rollout-phases.md)
6. [wireframes/agentic-shell-wireframes.html](./wireframes/agentic-shell-wireframes.html)
7. [wireframes/clinical-insights-balanced.html](./wireframes/clinical-insights-balanced.html)
8. [wireframes/clinical-insights-preview-review.html](./wireframes/clinical-insights-preview-review.html)
9. [wireframes/workspace-guided-cowork-blend.html](./wireframes/workspace-guided-cowork-blend.html)

## Folder Map

- `01-shell-spec.md`
  The north-star shell, its zones, pane system, interaction model, and visual
  direction.
- `02-workspace-model.md`
  Defines workspace package anatomy, first-party vs marketplace behavior, and
  how current modules migrate into the new model.
- `03-browser-vs-local-app.md`
  Compares browser and desktop options and recommends a browser-first path with
  desktop-grade posture.
- `04-wireframes.md`
  Text wireframes, annotated layouts, and behavior notes for the main shell and
  key workspace types.
- `05-rollout-phases.md`
  Suggested implementation sequence for landing the shell in the current
  codebase.
- `wireframes/agentic-shell-wireframes.html`
  Index page for the wireframe review set.
- `wireframes/clinical-insights-balanced.html`
  Primary Clinical Insights direction with denser sessions, tabbed preview, and
  a cleaner directory-style file tree.
- `wireframes/clinical-insights-preview-review.html`
  Focused Clinical Insights review mode with a shared preview surface and
  inspector access on demand.
- `wireframes/workspace-guided-cowork-blend.html`
  Marketplace workspace direction: guided, package-forward, and grounded in a
  denser workspace shell.

## Relationship To The Current Codebase

This package intentionally builds on the strongest existing seed in the app:
the full-screen Trial Finder workspace shell and workspace-definition model.

Most of the rest of the frontend still reflects the earlier route-per-module
product shape. This package is the bridge from that older structure to the new
shared harness structure.

Implementation guidance that translates this vision into concrete page / canvas /
workbench build rules now lives in
[`docs/architecture/HARNESS-SURFACES.md`](../../docs/architecture/HARNESS-SURFACES.md).

## Intended Outcome

This spec should be strong enough to guide:

- visual redesign work
- shell implementation work
- workspace package design
- migration of existing pages into the new harness
- future desktop wrapping if we decide to ship a local app later
