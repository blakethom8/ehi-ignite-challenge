# Net-New Workspace Architecture

## High-Level Shape

```text
React Workspace Shell
  Chat Surface
  Canvas Surface Registry
  Agent Inspector
  Management Board
  Artifact Viewer
        |
        | typed commands, events, snapshots
        v
FastAPI Workspace API
  sessions
  messages
  events
  tools
  artifacts
  patient context packages
  clinical trial pursuits
        |
        v
Agent Runtime
  skill loader
  context compiler
  tool registry
  model runner
  event emitter
  checkpoint manager
        |
        v
Clinical Tools
  SQL-on-FHIR
  patient dataset CLI
  ClinicalTrials.gov API
  source fetchers
  citation store
  packet generator
```

## Frontend Boundaries

The frontend owns layout, interaction, and rendering. It should render typed objects, not free-form HTML emitted by an agent.

Frontend packages in the net-new build should be shaped around:

- `workspace-shell` - layout, panes, resize, fullscreen, persistence
- `workspace-surfaces` - chat, canvas, inspector, artifacts, task board
- `workspace-contracts` - TypeScript contracts mirrored from backend schemas
- `clinical-trials` - domain surfaces for trial search, criteria, candidate details, pursuit board

## Backend Boundaries

The backend owns agent sessions, durable state, tools, and auditability.

Backend modules should be shaped around:

- `workspace_sessions` - lifecycle, resume, checkpoints
- `workspace_events` - append-only event stream
- `workspace_tools` - typed tool registry and permissions
- `workspace_artifacts` - generated files, markdown, packets, downloaded source snapshots
- `trial_pursuits` - durable clinical-trial project management
- `patient_context` - patient data package compilation

## Runtime Boundaries

The agent runtime should be a service, not a React behavior.

The runtime takes:

- active workspace
- patient context package
- active skill
- user message
- steering messages
- tool allowlist
- current durable state

The runtime emits:

- assistant messages
- tool calls
- tool results
- canvas object updates
- artifact updates
- pursuit updates
- checkpoint events
- human approval requests

## Storage Model

Use SQLite or another structured store for durable workspace state.

Recommended first schema groups:

- `workspace_session`
- `workspace_message`
- `workspace_event`
- `workspace_tool_call`
- `workspace_artifact`
- `workspace_canvas_object`
- `trial_candidate`
- `trial_pursuit`
- `trial_pursuit_task`
- `trial_pursuit_event`
- `source_snapshot`
- `citation`

JSON files are acceptable for exported snapshots and review artifacts, but not as the primary source of truth for active clinical-trial project management.
