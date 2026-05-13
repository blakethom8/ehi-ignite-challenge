# Agentic Clinical Workspace Redesign

This folder is a clean-room planning and contract area for a net-new workspace build. It intentionally does not modify the existing React or FastAPI application.

The goal is to design the next workspace around the interaction pattern we actually want:

- chat first
- structured canvas panes beside the chat
- transparent agent tools, context, and skills
- durable clinical micro-projects, starting with clinical-trial pursuit management
- production-oriented agent loops rather than demo-only deterministic flows

The current app remains a reference, not a dependency. The strongest existing reference is the ground-truth review workspace because it already has resizable panes, a source pane, an object list, a detail pane, and durable review state.

## Contents

- `docs/research-notes.md` - notes from current Codex, Claude Code, OpenCode-style GUI patterns.
- `docs/product-thesis.md` - what this workspace is and is not.
- `docs/architecture.md` - proposed frontend/backend/runtime architecture.
- `docs/panel-system.md` - how panes, canvases, inspectors, and fullscreen states should work.
- `docs/agent-harness.md` - proposed agent loop, tools, skills, context, and transparency model.
- `docs/clinical-trials-workspace.md` - Trial Finder as the first real micro-project workspace.
- `docs/build-sequence.md` - staged implementation plan.
- `src/contracts.ts` - TypeScript contract sketch for workspaces, surfaces, agent events, and tools.
- `src/trialFinderWorkspace.ts` - example configuration for the Trial Finder workspace.

## Core Decision

The agent should not generate arbitrary HTML as the primary UI contract.

The agent should produce typed workspace events and typed domain objects. React renders those objects into known workspace surfaces: chat, canvas, inspector, source views, candidate lists, detail panes, pursuit boards, artifacts, and transcripts.

That gives us a Codex-like interaction model without making the UI unpredictable or unsafe.
