# Agent Harness

## Principle

The agentic harness is the production core. The UI is only trustworthy if the agent runtime is observable, steerable, and constrained by explicit tools and skills.

## Runtime Loop

```text
user message
  -> append message
  -> compile context
  -> load active skill
  -> expose tools
  -> run model
  -> emit assistant delta/events
  -> call tools as needed
  -> validate tool results
  -> update canvas objects
  -> update durable project state
  -> checkpoint
  -> wait for user steering or continue if safe
```

## Required Agent Capabilities

- receive mid-run steering
- pause and resume runs
- expose all tool calls
- expose all source reads
- expose patient context package contents
- expose skill files and active instructions
- create durable artifacts
- create and update project-management records
- request human approval before external submission or outreach
- checkpoint before irreversible state changes

## Tool Categories

Patient tools:

- query patient SQL-on-FHIR warehouse
- retrieve patient context package
- summarize relevant conditions, medications, observations, encounters
- cite source FHIR resources

Clinical-trial tools:

- search ClinicalTrials.gov
- fetch trial detail
- normalize criteria
- score patient fit
- identify operational burden
- capture source snapshot

Pursuit-management tools:

- create pursuit
- update status
- add task
- add note
- add outreach event
- create packet draft
- mark submission
- schedule follow-up

Transparency tools:

- list active tools
- list active skill files
- list context files
- list source URLs
- show event transcript
- export run bundle

## Inspector Tabs

The inspector is not generic settings. It is the trust and control surface.

Recommended tabs:

- **Workspace** - what this workspace is, active patient, active skill, session state
- **Tools** - each callable tool, permission level, last call, failure state
- **Context** - patient package, memory, selected facts, user steering
- **Sources** - configured source URLs/APIs, snapshots, fetch status
- **Events** - transcript of messages, tool calls, state updates, checkpoints
- **Artifacts** - generated markdown, packets, exports, source captures
- **Approvals** - pending actions that need explicit user confirmation

## Production Stance

Do not build deterministic mode as the main path.

Use deterministic tests, fixtures, and replay harnesses for verification, but the product runtime should be built around a real agent loop with tool calls, validation, and inspectable state.
