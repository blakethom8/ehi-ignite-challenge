# Workspace Panel System

## Goal

Build a reusable Codex-like workspace frame that every future clinical micro-app can use.

The ground-truth review page already demonstrates the seed pattern: source pane, extracted-object pane, detail pane, resize handles, toggles, and persistent review state. The net-new build should extract that pattern into a first-class workspace shell.

## Required Behaviors

Every workspace surface should support:

- open
- close
- collapse
- resize
- expand to fullscreen
- restore previous size
- persist layout per user/workspace
- declare minimum width
- declare preferred width
- declare mobile behavior

## Surface Types

Core surfaces:

- `chat` - primary user/agent conversation
- `canvas` - current structured work object
- `inspector` - tools, skills, context, permissions, events, artifacts
- `management` - durable project board
- `source` - source documents, URLs, PDFs, source snapshots
- `artifact` - generated markdown, packet drafts, exports

Clinical-trial surfaces:

- `trial-search-criteria`
- `trial-candidates`
- `trial-detail`
- `trial-pursuit-board`
- `trial-packet`
- `trial-source-map`

## Layout Model

The shell should use a surface registry:

```ts
type WorkspaceSurface = {
  id: string;
  title: string;
  role: "chat" | "canvas" | "inspector" | "management" | "source" | "artifact";
  defaultOpen: boolean;
  defaultWidth: number;
  minWidth: number;
  canFullscreen: boolean;
  canCollapse: boolean;
  mobileMode: "hide" | "drawer" | "stack";
};
```

The workspace should not hardcode panes into the page body. It should receive a `WorkspaceDefinition` and render surfaces based on configuration and current layout state.

## Navigation Model

There are two kinds of navigation:

1. **Global product navigation** - Data Aggregator, FHIR Charts, Clinical Insights, Marketplace, Internal Tools.
2. **Workspace surface navigation** - Chat, Canvas, Inspector, Management, Sources, Artifacts.

The second should live inside the workspace, not in the global app nav.

## Modal Model

Workspace overview should be a modal or command surface, not a large persistent top card.

The overview modal should explain:

- what the workspace does
- what the agent can access
- what sources it searches
- what outputs it can create
- what requires user approval
- what durable records are maintained

This keeps the working area focused while making the workspace understandable on demand.
