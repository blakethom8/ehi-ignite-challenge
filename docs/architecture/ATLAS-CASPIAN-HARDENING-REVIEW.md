# Atlas/Caspian Hardening Review

Date: 2026-05-10

Scope for this pass:

- downstream Atlas/Caspian application shell
- navigation, routing, pane behavior, and workspace state
- plugin/runtime data flow from HTTP routes into workspace-visible state
- test strategy for the current harness architecture

Non-scope for this pass:

- raw ingestion / upstream bundle-generation redesign
- broad visual polish work
- replacing existing product IA

## 1. Current surface map

### Top-level route families

- `Patient Record`
  - canonical: `/patient-record/*`
  - legacy absorbed aliases: `/aggregate/*`, `/record`, `/charts`, `/data-aggregator/*`
- `FHIR Charts`
  - canonical: `/fhir-charts/*`
  - legacy absorbed aliases: `/explorer/*`, `/journey`
- `Caspian`
  - canonical: `/caspian`, `/caspian/sessions/:sessionId`
- `Workspaces / Plugins`
  - catalog: `/workspaces`
  - workspace: `/workspaces/:pluginId`
  - run/session: `/workspaces/:pluginId/sessions/:sessionId`
- `Learn`
  - canonical: `/learn/*`
  - legacy absorbed aliases: `/analysis/*`, `/pipeline-lab`, `/ccda-lab`, `/ground-truth-review/*`

### Major user-flow map

- `Patient Record`
  - layout owner: `app/src/pages/PatientRecord/PatientRecordLayout.tsx`
  - flow:
    - overview -> workspaces -> sources -> harmonize -> publish -> context -> methodology
  - state:
    - preserves `?patient=...` in left-rail navigation
    - left-rail collapse persists in localStorage
- `FHIR Charts`
  - layout owner: `app/src/pages/FhirCharts/FhirChartsLayout.tsx`
  - flow:
    - summary -> history -> care journey -> labs -> safety -> interactions -> immunizations -> patient data -> assistant
  - state:
    - preserves `?patient=...` in left-rail navigation
    - left-rail collapse persists in localStorage
- `Caspian`
  - route owner: `app/src/pages/Caspian/Workspace.tsx`
  - shell owner: `app/src/components/atlas/WorkspaceFrame.tsx`
  - flow:
    - session selection -> chat -> workbench -> files -> inspector
  - persisted shell state:
    - pane visibility
    - pane sizes
    - right-pane focus
- `Plugin workspaces`
  - route owner: `app/src/pages/Plugins/Workspace.tsx`
  - current split:
    - fixture session -> `WorkspaceFrame`
    - live run -> `PluginRunPanel`
- `Preview / workbench / files / inspector`
  - owners:
    - `app/src/components/atlas/WorkbenchPane.tsx`
    - `app/src/components/atlas/FilesPane.tsx`
    - `app/src/components/atlas/InspectorPane.tsx`
- `Canvas / stateful run surfaces`
  - fixture canvas:
    - `app/src/components/atlas/data.ts`
  - live plugin run canvas:
    - `app/src/components/atlas/usePluginRun.ts`
    - `app/src/components/atlas/PluginRunPanel.tsx`
- `Learn / eval / review surfaces`
  - route owner: `app/src/App.tsx`
  - downstream answer-quality surface:
    - `app/src/pages/InternalTools/QaEvalLab.tsx`

### Shell ownership

- `app/src/App.tsx`
  - route graph, legacy redirects, shell wrapping rules
- `app/src/components/atlas/AppShell.tsx`
  - module chrome, workspace switch memory, top-level module activation
- `app/src/components/atlas/WorkspaceFrame.tsx`
  - five-pane shell for fixture-backed Caspian/plugin workspaces
- `app/src/components/atlas/PluginRunPanel.tsx`
  - live plugin-run surface

### Important architectural distinction

The repo currently has two different plugin interaction surfaces:

- fixture-backed plugin sessions use `WorkspaceFrame`
- live plugin runs use `PluginRunPanel`

That means the shared five-pane shell contract is only partially universal today. This is the biggest remaining navigation/runtime consistency risk.

## 2. Data-flow review

### Caspian / assistant path

- `POST /api/assistant/chat`
  - router: `api/routers/assistant.py`
  - service dispatch: `api/core/provider_assistant_service.py`
  - engines:
    - deterministic provider assistant
    - context mode
    - Anthropic Agent SDK mode
    - Cursor sidecar mode
- trace shaping:
  - `api/routers/assistant.py` builds `TraceDetail`
  - request tracing middleware + trace store live under `api/middleware/tracing.py` and `api/core/tracing.py`

Current note:

- the assistant HTTP contract is reasonably covered
- the frontend workspace shell is still mostly fixture-driven and does not yet project the live assistant state into the same workbench/files/inspector model as the plugin runtime

### Plugin runtime path

- manifest and install surface
  - router: `api/plugins/routers/plugins.py`
  - manifest verification/loading: `api/plugins/manifest.py`
- runtime state
  - `api/plugins/runtime.py`
  - persisted in `data/runs.db`
  - tables: `runs`, `events`, `approvals`
- provenance
  - `api/plugins/provenance.py`
- frontend client path
  - `app/src/api/plugins.ts`
  - `app/src/components/atlas/usePluginRun.ts`
  - `app/src/components/atlas/manifests.ts`

Runtime-to-UI projection today:

- live plugin runs fold `tool.result` events into `canvas`
- `PluginRunPanel` renders that `canvas` through the renderer registry
- fixture workspaces still use local seed state in `app/src/components/atlas/data.ts`

## 3. Fixes landed in this pass

### Fixed

1. Legacy ground-truth review redirects now preserve `runId`.
   - files:
     - `app/src/App.tsx`
     - `app/src/routing.ts`
   - problem:
     - `/ground-truth-review/:runId` redirected to `/learn/ground-truth-review` and dropped the selected run
   - result:
     - deep links now survive the alias redirect

2. Module-route classification is now a pure shared helper instead of an implicit shell-local detail.
   - files:
     - `app/src/components/atlas/navigation.ts`
     - `app/src/components/atlas/AppShell.tsx`
     - `app/src/components/atlas/index.ts`
   - result:
     - route-to-module behavior is directly testable

3. Fixture file routing is now workspace-aware.
   - files:
     - `app/src/components/atlas/data.ts`
     - `app/src/components/atlas/useWorkspaceState.ts`
   - problem:
     - file ids such as `f_manifest` were reused across multiple workspaces, but tab routing was global
     - non-trial plugin files could open the wrong tab contract or nothing at all
   - result:
     - file-to-tab and action-to-tab lookup now resolves against the active workspace

4. Visible fixture files now have workbench coverage across Caspian and plugin shells.
   - files:
     - `app/src/components/atlas/data.ts`
     - `app/src/components/atlas/WorkspaceFrame.tsx`
   - result:
     - missing seeded tabs and placeholder canvas payloads were added for:
       - Caspian workflow/history/labs/settings artifacts
       - Trial Finder diagnosis/biomarker/geography artifacts
       - Med Access, Site Coordination, and Second Opinion fixture files

5. Workspace state now tracks the active file and has safer tab-close fallback behavior.
   - file:
     - `app/src/components/atlas/useWorkspaceState.ts`
   - result:
     - files pane selection can stay aligned with the workbench
     - closing the active tab now computes the next tab from current state rather than stale captured state

6. Frontend shell contract tests now exist.
   - files:
     - `app/vitest.config.ts`
     - `app/src/test/setup.ts`
     - `app/src/components/atlas/navigation.test.ts`
     - `app/src/components/atlas/data.test.ts`
     - `app/src/components/atlas/useWorkspaceState.test.tsx`
   - `app/src/routing.test.ts`
   - result:
     - route alias behavior, workspace file/tab routing, and shell state transitions now have an executable guardrail

7. Internal navigation now favors canonical Atlas routes instead of retired aliases.
   - files:
     - `app/src/pages/PatientRecord/Methodology.tsx`
     - `app/src/pages/PatientRecord/aggregator/shared.tsx`
     - `app/src/components/ChatWidget.tsx`
   - problem:
     - some in-product links still depended on legacy redirects such as `/aggregate/*`, `/charts`, and `/explorer/assistant`
   - result:
     - user-visible navigation now uses canonical routes directly
     - the floating assistant widget now recognizes the canonical assistant route

8. Live plugin runs now keep the persisted `run.canvas` field in sync with emitted `tool.result` events.
   - files:
     - `api/plugins/runtime.py`
     - `api/tests/test_plugin_runtime.py`
     - `api/tests/test_plugin_routers.py`
   - problem:
     - the runtime emitted `tool.result` events, but the `run.canvas` field returned by `/api/plugins/runs/{runId}` was not updated
     - that created a drift between the advertised runtime contract and the data the frontend actually received
   - result:
     - direct tool calls and approved outbound actions now update both the event stream and the persisted run canvas
     - the HTTP surface now has an explicit sync test for `canvas` and `tool.result`

## 4. Verification status

### Passing in this pass

- `cd app && npm run test`
- `cd app && npm run build`
- `cd app && npm run smoke:shell`
- `uv run pytest api/tests/test_plugin_runtime.py api/tests/test_plugin_routers.py -q`
- `uv run pytest api/tests/test_plugin_routers.py api/tests/test_assistant_api.py -q`

### Still red

- `cd app && npm run lint`

Current lint blockers are pre-existing and should be treated as a separate cleanup stream:

- `app/src/components/ClinicalNoteReader.tsx`
- `app/src/components/atlas/ChatPane.tsx`
- `app/src/components/atlas/PluginRunPanel.tsx`
- `app/src/pages/InternalTools/GroundTruthReview.tsx`
- `app/src/pages/InternalTools/QaEvalLab.tsx`

## 5. Reliability risks still open

### P0

1. Live plugin runs do not use the shared five-pane workspace shell.
   - ownership:
     - `app/src/pages/Plugins/Workspace.tsx`
     - `app/src/components/atlas/PluginRunPanel.tsx`
     - `app/src/components/atlas/WorkspaceFrame.tsx`
   - risk:
     - the app is advertising one harness model, but live plugin execution still diverges into a custom two-pane surface

2. Browser-level coverage is present only as a focused smoke layer.
   - ownership:
     - `app/scripts/smoke-shell.mjs`
   - risk:
     - current smoke covers redirects, per-workspace pane persistence, session switching, and file-to-workbench behavior
     - it does not yet cover pane resize, inspector flows, or live backend plugin runs

3. Frontend lint is not green.
   - ownership:
     - files listed in section 4
   - risk:
     - hook ordering / set-state-in-effect findings can hide real runtime issues and block a clean CI gate

### P1

1. Workspace persistence is partial.
   - today:
     - panes, pane sizes, and right-pane focus persist
   - missing:
     - active session
     - active tab
     - active file
     - citation selection

2. Caspian’s live assistant/workbench integration is still weaker than the plugin runtime’s canvas model.
   - ownership:
     - `app/src/components/atlas/WorkspaceFrame.tsx`
     - `app/src/components/atlas/ChatPane.tsx`
     - assistant-facing page/components

3. Fixture shell and live runtime contracts should be merged or explicitly separated.
   - recommended rule:
     - either all real workspaces run through one shell contract, or the repo should name the divergence and test both paths independently

### P2

1. Q&A Eval Lab should become the acceptance gate for downstream answer quality, not just a review surface.
2. Latency, unsupported citation rate, and repeated-run variance should become first-class benchmark metrics.

## 6. Recommended test layers

### Layer 1: frontend contract tests

Use Vitest + jsdom for:

- route alias helpers
- module activation logic
- workspace state transitions
- file/action routing tables
- renderer selection rules

Purpose:

- catch fast regressions in navigation and shell behavior without spinning a browser

### Layer 2: frontend browser tests

Use Playwright for:

- route smoke:
  - every canonical route renders
  - every important legacy alias resolves to the correct canonical route
- shell behavior:
  - pane toggles
  - pane persistence after reload
  - session switching
  - file click -> tab open -> inspector interaction
- plugin runtime:
  - start run
  - grant consent
  - tool call
  - outbound approval request
  - approve/deny/revoke flows

### Layer 3: backend API/data-contract tests

Keep strengthening pytest coverage around:

- plugin manifest verification
- run/event/approval/provenance lifecycle
- assistant response contract
- trace detail contract
- explicit invariants on event kinds and canvas foldability

### Layer 4: harness integration tests

Add scenario-level checks that verify:

- a backend run produces events the frontend can project without ad hoc transforms
- renderer keys referenced by manifests exist
- tool outputs required by renderers are present and correctly shaped

### Layer 5: LLM evaluation / clinical answer quality

Treat Q&A Eval Lab as the stable acceptance harness for answer quality.

Minimum scored dimensions:

- clinical relevance to the user task
- factual grounding in chart/bundle/evidence context
- citation correctness and usefulness
- correctness of tool choice and tool sequencing
- correctness of artifact / preview / file / canvas references
- clarity, prioritization, safety, and actionability of the final answer
- observability completeness:
  - prompt/context metadata
  - tool-call trace
  - citations
  - run metadata
  - latency
- consistency across repeated prompts / benchmark runs

## 7. Definition of “good” for agentic output

An answer should only count as good if it satisfies all of the following:

- it answers the clinician’s actual task rather than paraphrasing the chart
- every material claim is grounded in available chart evidence or clearly marked as uncertainty
- citations point to the specific supporting objects the user can inspect
- tool calls are necessary, correctly scoped, and not obviously wasteful
- references to preview/workbench/files/canvas objects match real artifacts visible in the UI
- the response prioritizes the highest-signal safety-critical facts first
- the trace can reconstruct what context, tools, and artifacts drove the answer
- latency is acceptable for interactive review:
  - time-to-first-meaningful-response
  - time-to-useful-answer
- repeated benchmark prompts do not drift materially without a code or model change

## 8. Completion audit against the current objective

### Requirement 1

- target:
  - map and review major user flows across Patient Record, FHIR Charts, Caspian, Workspaces/Plugins, preview/workbench, canvas/stateful run surfaces, files, and inspector/navigation interactions
- evidence:
  - sections 1 and 2 of this document
  - route owners and shell owners identified in:
    - `app/src/App.tsx`
    - `app/src/pages/PatientRecord/PatientRecordLayout.tsx`
    - `app/src/pages/FhirCharts/FhirChartsLayout.tsx`
    - `app/src/pages/Caspian/Workspace.tsx`
    - `app/src/pages/Plugins/Workspace.tsx`
    - `app/src/components/atlas/WorkspaceFrame.tsx`
    - `app/src/components/atlas/PluginRunPanel.tsx`
- status:
  - met
  - remaining caveat is captured as a prioritized reliability risk, not a missing review artifact

### Requirement 2

- target:
  - identify, prioritize, and fix or punch-list navigation/routing/pane/state persistence issues
- evidence:
  - fixed items in section 3
  - prioritized risks in section 5
  - browser smoke + unit coverage in section 4
- status:
  - met
  - remaining persistence gaps are captured as an explicit punch list

### Requirement 3

- target:
  - trace backend data contracts from API routes through workspace state, app data, canvas data, preview/workbench artifacts, and tool-call surfaces
- evidence:
  - assistant path and plugin runtime path in section 2
  - route/client/runtime/component owners named there
- status:
  - met
  - strongest evidence is on the plugin runtime and assistant surfaces
  - the missing unified Caspian live workbench contract remains a product/runtime risk, not an untraced path

### Requirement 4

- target:
  - redesign testing strategy across routing, workspace shell, API/data contracts, canvas/workbench/app-state behavior, tool-call behavior, and final LLM output quality
- evidence:
  - sections 6 and 7
  - new frontend contract tests
  - new browser smoke harness
  - existing backend pytest coverage
- status:
  - met
  - implementation now includes unit, browser-smoke, and backend contract coverage

### Requirement 5

- target:
  - define what matters for LLM evaluation: clinical relevance, grounding, tool use, artifact use, response quality, observability, latency, consistency
- evidence:
  - section 7
  - section 6 layer 5
- status:
  - met
  - the remaining gap is operational rollout into a mandatory release gate

### Requirement 6

- target:
  - deliver a durable verification framework, missing coverage inventory, concrete tests to add, and a prioritized reliability plan
- evidence:
  - sections 5, 6, 7, and 9
  - added commands:
    - `npm run test`
    - `npm run smoke:shell`
- status:
  - met

### Requirement 7

- target:
  - keep upstream pipeline review separate unless it blocks downstream validation
- evidence:
  - scope and non-scope at top of document
  - section 10
- status:
  - met

## 9. Next recommended sequence

1. Fix the red frontend lint gate.
2. Add Playwright route + pane smoke coverage for canonical and legacy routes.
3. Unify live plugin runs with `WorkspaceFrame`, or formalize and separately test the divergent contract.
4. Persist active session/tab/file selection per workspace.
5. Expand Q&A Eval Lab into a release gate for groundedness, latency, citations, and repeated-run consistency.

## 10. Separate review stream

Upstream ingestion and malformed-bundle issues should stay in a separate review stream unless a downstream contract is broken by demonstrably bad bundle shape. This pass is intentionally focused on the consumers of those bundles, not on redesigning the raw pipeline.
