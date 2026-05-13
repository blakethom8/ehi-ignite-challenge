# Build Sequence

## Phase 0: Clean Contracts

- Define workspace/session/event/surface/tool contracts.
- Define trial candidate and pursuit-management contracts.
- Define inspector tabs and event types.
- Do not wire into the existing app yet.

## Phase 1: Workspace Shell Prototype

- Create a new isolated React route or standalone package.
- Implement `WorkspaceFrame`.
- Implement surface registry.
- Implement collapsible/resizable/fullscreen panes.
- Persist layout locally.
- Add a mock Trial Finder workspace using typed fixture objects.

## Phase 2: Backend Session API

- Add workspace session CRUD.
- Add message append/list.
- Add event stream.
- Add artifact list/read.
- Add tool registry endpoint.
- Add inspector endpoint.

## Phase 3: Real Agent Loop

- Wire skill loading.
- Wire patient context compilation.
- Wire tool registry.
- Stream assistant events and tool events.
- Validate structured outputs before committing canvas objects.
- Add checkpoints.

## Phase 4: Clinical Trial Tools

- ClinicalTrials.gov search.
- Trial detail fetch.
- Criteria normalization.
- Fit assessment against patient facts.
- Source snapshot capture.
- Citation linking.

## Phase 5: Pursuit Management

- SQLite-backed trial pursuits.
- Status board.
- Tasks, notes, outreach, packet drafts, follow-ups.
- Approval gates for external actions.

## Phase 6: Migration Decision

After the new shell proves itself, decide whether to:

- replace the current Trial Finder route,
- mount the new workspace beside the current route,
- or move it into a separate app package.

The existing app should not be rewritten until the new workspace contract feels correct.
