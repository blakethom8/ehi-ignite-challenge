# Clinical Trials Workspace

## Opening State

The workspace should open with the chat focused.

The first assistant message should ask what the user is looking for:

> What kind of clinical trials are you interested in? You can tell me the disease area, geography, phase, intervention type, sponsor preferences, travel limits, or anything the patient or clinician wants to avoid.

The canvas should start light. It should not show a giant explainer card. A small info button opens the workspace overview modal.

## Core Surfaces

### Chat

The primary interaction channel. The agent asks clarifying questions, reports progress, and accepts steering.

### Candidate Trials

A structured list of trials found by the agent. Each candidate should show:

- title
- status
- phase
- condition
- intervention
- location burden
- enrollment size
- match score
- top inclusion matches
- top exclusion risks
- evidence/citation count

### Trial Detail

A focused view for one selected trial:

- summary
- why it may fit
- why it may not fit
- inclusion criteria
- exclusion criteria
- operational requirements
- locations
- contacts
- source snapshot
- user decisions

### Pursuit Board

A management view for trials the user is actively considering.

Statuses:

- interested
- reviewing
- packet
- contacted
- submitted
- follow-up
- closed

Each pursuit can have:

- tasks
- notes
- outreach events
- packet artifacts
- deadlines
- follow-up reminders

### Agent Inspector

The trust surface:

- active skill
- tools
- context package
- sources
- tool calls
- artifacts
- approvals

## Source Strategy

Phase 1 should prioritize API-first sources:

- ClinicalTrials.gov API
- trial registry source snapshots
- local patient SQL-on-FHIR data

Later phases can add:

- academic medical center trial pages
- disease foundation registries
- sponsor trial finders
- insurer or portal-specific information
- manually uploaded trial PDFs

## Matching Dimensions

Clinical:

- condition/disease state
- stage/severity
- biomarkers/genetics
- medications
- labs
- comorbidities
- prior procedures
- age/sex

Operational:

- geography
- visit frequency
- study duration
- travel burden
- remote/hybrid availability
- sponsor/site reputation
- enrollment target
- recruitment status
- paperwork burden
- likely time to first contact

Pursuit:

- patient interest
- clinician interest
- packet readiness
- missing facts
- required records
- contact attempts
- follow-up state

## Agent Output Contract

The agent should update typed objects:

- `TrialCandidate`
- `TrialMatchAssessment`
- `TrialPursuit`
- `PursuitTask`
- `SourceSnapshot`
- `WorkspaceArtifact`

The UI renders these objects. The agent does not own the visual layout.
