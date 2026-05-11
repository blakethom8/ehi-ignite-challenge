# Wireframes

This document provides text-first wireframes and behavior notes. The companion
HTML mockup lives in
[wireframes/agentic-shell-wireframes.html](./wireframes/agentic-shell-wireframes.html).

## Review Pages

- [wireframes/agentic-shell-wireframes.html](./wireframes/agentic-shell-wireframes.html)
  Index page for the wireframe set
- [wireframes/clinical-insights-balanced.html](./wireframes/clinical-insights-balanced.html)
  Balanced operator shell with explicit pane toggles, tabbed preview, and a real file tree
- [wireframes/clinical-insights-preview-review.html](./wireframes/clinical-insights-preview-review.html)
  Preview-heavy review shell with shared tabs for app, markdown, notes, and settings
- [wireframes/workspace-guided-cowork-blend.html](./wireframes/workspace-guided-cowork-blend.html)
  Guided cowork blend with run-state and working-folder side panels

## Directional distinction

This pass clarifies that we are not designing one monolithic shell mood.

- Clinical Insights variants should feel more clinical, private, and
  interpretation-first.
- Marketplace variants can feel more cowork or guided, but they still need a
  professional preview surface, explicit package identity, and real workspace
  files rather than soft cards.
- The tabbed preview concept is shared across both.
- The file surface should behave more like Cursor / VS Code / Codex than like
  a marketing dashboard.

## Family Readout

### Clinical Insights

- Primary direction: [wireframes/clinical-insights-balanced.html](./wireframes/clinical-insights-balanced.html)
- Secondary focused mode:
  [wireframes/clinical-insights-preview-review.html](./wireframes/clinical-insights-preview-review.html)
- Key traits:
  denser session rows, pinned workflow launchers, one tabbed preview surface,
  cleaner directory tree, and no default progress module

### Marketplace workspace

- Primary direction:
  [wireframes/workspace-guided-cowork-blend.html](./wireframes/workspace-guided-cowork-blend.html)
- Key traits:
  clearer package identity, guided module actions, working-folder state, and
  action-oriented side objects when the package is actually running a staged
  workflow

## Legend

- `GR` = Global rail
- `SR` = Session rail
- `CH` = Chat pane
- `WB` = Workbench pane
- `IN` = Inspector / evidence
- `AR` = Artifacts / tasks / settings drawer

## 1. Universal Shell

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Workspace Header: title · patient · workflow trigger · permissions · export · run status  │
├──────┬──────────────┬──────────────────────────────┬──────────────────────────┬─────────────┤
│ GR   │ SR           │ CH                           │ WB                       │ IN / AR     │
│      │              │                              │                          │             │
│ Home │ Session A    │ Conversation                 │ Preview / app / file     │ Evidence    │
│ Lib  │ Session B    │ Approvals                    │ Candidate object         │ Tool calls  │
│ Pat  │ Session C    │ Pinned context               │ Notes / file             │ Settings    │
│ CI   │ Session D    │ Follow-ups                   │ Compare view             │ Tasks       │
│ Rev  │              │                              │                          │             │
│ Set  │              │                              │                          │             │
└──────┴──────────────┴──────────────────────────────┴──────────────────────────┴─────────────┘
```

### Notes

- This is the default desktop-web posture.
- Chat is always visible.
- The right-most zone can hold a pane column or a tabbed drawer.
- The workbench can host one or more pane tabs depending on task complexity.

## 2. Clinical Insights Workspace

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Clinical Insights · Demo Patient · Run workflow ▾ · Private boundary · Export              │
├──────┬──────────────┬──────────────────────────────┬──────────────────────────┬─────────────┤
│ GR   │ SR           │ CH                           │ WB                       │ IN          │
│      │              │                              │                          │             │
│ CI   │ Pre-op run   │ Chart-grounded Q&A           │ Clinical brief           │ Citations   │
│ Lib  │ Longitudinal │ Workflow prompts             │ Evidence reader          │ Prompt ctx  │
│ Pat  │ Safety       │ Approval cards               │ Timeline / chart note    │ Tool trace  │
│ Rev  │              │ Pinned facts                 │ Workflow artifact        │             │
└──────┴──────────────┴──────────────────────────────┴──────────────────────────┴─────────────┘
```

### Notes

- Workflow triggers live in the workspace header, not on separate product pages.
- The main workbench should easily swap between summary, evidence, and artifact
  views without route changes.
- Inspector stays close because provenance is part of the clinical trust model.
- Sessions should read as dense run rows, not roomy vertical cards.
- Preview controls should be simple: tab strip first, advanced split / inspect
  behavior only when justified.

## 3. Marketplace Workspace

```text
┌─────────────────────────────────────────────────────────────────────────────────────────────┐
│ Trial Finder · Demo Patient · Consent boundary: external search · Export packet            │
├──────┬──────────────┬──────────────────────────────┬──────────────────────────┬─────────────┤
│ GR   │ SR           │ CH                           │ WB                       │ AR / IN     │
│      │              │                              │                          │             │
│ Lib  │ Trial run 1  │ Agent steering               │ Ranked candidates        │ Tasks board │
│ CI   │ Trial run 2  │ Outreach drafting            │ Trial detail             │ Sources     │
│ Pat  │ Packet prep  │ Human approval steps         │ Lightweight app surface  │ Manifest    │
│ Rev  │              │                              │ Packet preview           │ Permissions │
└──────┴──────────────┴──────────────────────────────┴──────────────────────────┴─────────────┘
```

### Notes

- Marketplace workspaces should still feel native to the shell.
- The package-specific lightweight app lives in the workbench.
- Permission and boundary surfaces must be easy to open and inspect.
- The shell should clearly name the running package, not just the generic page.
- Action objects can be more visible here than in Clinical Insights, but they
  should stay specific to the package rather than generic shell filler.

## 4. Narrow Browser Layout

```text
┌───────────────────────────────────────────────────────────────┐
│ Header: workspace · patient · trigger · more                 │
├──────┬──────────────────────────────┬─────────────────────────┤
│ GR   │ CH                           │ WB                      │
│      │                              │                         │
│ icon │ Conversation                 │ active pane            │
│ rail │ approvals                    │ tabbed support panes   │
│      │ pinned context               │ drawer for inspector   │
└──────┴──────────────────────────────┴─────────────────────────┘
```

### Notes

- The session rail can collapse into a drawer.
- Inspector, files, and settings become tabbed drawers or slide-over panes.
- We keep the shell identity even when width is constrained.

## 5. Behavior Patterns

### 5.1 Open In Pane

The agent references an object in chat and offers actions:

- open note
- compare versions
- pin to context
- send to artifact

The action targets a specific pane, not a new route.

### 5.2 Workflow Trigger

The user launches a workflow from the header. The shell changes state:

- opens the relevant workbench pane
- reveals the correct task or artifact panel
- seeds the chat with the workflow contract

### 5.3 Evidence Review

Selecting a citation from either the chat or artifact should populate the
inspector pane with:

- source
- excerpt
- provenance path
- related artifacts

## 6. Visual Use Of Html-In-Canvas

The shell wireframes assume two visual layers:

- a calm application shell with paper-like panes
- a softer atmospheric canvas around launch cards, background glows, and
  workspace identity moments

This gives the product a more modern feel without sacrificing work clarity.
