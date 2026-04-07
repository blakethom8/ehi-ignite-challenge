# Anthropic SDK Operating Report

This document is the canonical implementation guide for the provider assistant runtime in this repository.

Use this report when changing:
- SDK wiring
- tool permissions
- model/runtime configuration
- personality profiles
- provider assistant API contract

## 1) Repository Entry Points

### Runtime and API
- `api/routers/assistant.py`: HTTP endpoint (`POST /api/assistant/chat`)
- `api/core/provider_assistant_service.py`: mode switch and fallback orchestration
- `api/core/provider_assistant.py`: deterministic chart assistant + evidence ranking
- `api/core/provider_assistant_agent_sdk.py`: Anthropic Agent SDK runtime
- `api/models.py`: request/response contract (`ProviderAssistant*`)
- `api/main.py`: router registration

### Personality and behavior profiles
- `api/agents/provider-assistant/CLAUDE.md`: voice and behavior
- `api/agents/provider-assistant/METHODOLOGY.md`: reasoning method
- `api/agents/provider-assistant/RULES.md`: runtime constraints and tool sequencing

### Frontend integration
- `app/src/pages/Explorer/Assistant.tsx`: provider chat UI and per-patient context state
- `app/src/api/client.ts`: `/assistant/chat` API call
- `app/src/types/index.ts`: TS contracts for assistant response

### Dependency location
- `pyproject.toml`: `claude-agent-sdk>=0.1.56`
- `uv.lock`: exact lock state

## 2) Runtime Modes

The endpoint is stable while runtime is selectable.

### Mode selector
Set in env via `PROVIDER_ASSISTANT_MODE`:
- `deterministic` (default)
- `anthropic`
- `anthropic_agent`
- `agent_sdk`
- `anthropic_sdk`

### Fallback behavior
- On Anthropic runtime/config failure, fallback to deterministic unless disabled.
- Flag: `PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC` (default `true`)

Response includes `engine`:
- `deterministic`
- `anthropic-agent-sdk`
- `deterministic-fallback`

## 3) Anthropic SDK Wiring (Current)

Implemented in `api/core/provider_assistant_agent_sdk.py`.

### Core SDK primitives in use
- `query(...)`
- `ClaudeAgentOptions(...)`
- `tool(...)`
- `create_sdk_mcp_server(...)`

### Custom MCP tools exposed to Claude
- `get_patient_snapshot`: high-signal summary snapshot
- `query_chart_evidence`: query-specific evidence retrieval

Both tools call deterministic evidence retrieval:
- `get_relevant_provider_evidence(...)` in `api/core/provider_assistant.py`

This ensures citation and retrieval consistency between deterministic and agentic modes.

### Security and tool restrictions
- Permission mode set to `dontAsk` for server-side automation.
- Allowed tools are explicit:
  - `mcp__fhir_chart__get_patient_snapshot`
  - `mcp__fhir_chart__query_chart_evidence`
  - optional `WebSearch` / `WebFetch` if enabled by env
- `can_use_tool(...)` enforces hard caps for web tool call counts.

## 4) Anthropic Runtime Configuration

Required:
- `ANTHROPIC_API_KEY`

Optional runtime tuning:
- `PROVIDER_ASSISTANT_MODEL` (default `claude-sonnet-4-5`)
- `PROVIDER_ASSISTANT_MAX_TURNS` (default `6`)
- `PROVIDER_ASSISTANT_MAX_BUDGET_USD` (optional)
- `PROVIDER_ASSISTANT_ENABLE_WEB_SEARCH` (default `false`)
- `PROVIDER_ASSISTANT_ENABLE_WEB_FETCH` (default `false`)

## 5) Personality Profile Strategy

Current profile set is single-purpose for providers:
- Path: `api/agents/provider-assistant/`

### Division of responsibility
- `CLAUDE.md`: communication style and pushback stance
- `METHODOLOGY.md`: decision process and evidence prioritization
- `RULES.md`: tool usage order, citation discipline, brevity constraints

### Profile evolution model
Treat each profile as a versioned artifact.

Recommended approach:
1. Add a profile variant directory, e.g. `api/agents/provider-assistant-v2/`
2. Add profile selector env var, e.g. `PROVIDER_ASSISTANT_PROFILE`
3. Keep API contract stable while experimenting with profile behavior
4. Run A/B evaluation with fixed question sets before promotion

## 6) Current Request Flow

1. Frontend sends `patient_id`, `question`, `history`, `stance`.
2. Router validates payload (`api/routers/assistant.py`).
3. Mode selector routes call (`api/core/provider_assistant_service.py`).
4. Deterministic mode:
   - load parsed patient
   - rank evidence
   - produce direct answer + citations + follow-ups
5. Anthropic mode:
   - initialize scoped MCP tools
   - run Claude Agent SDK loop
   - parse structured output JSON
   - validate citations against retrieved evidence
6. Response returned with `engine` marker.

## 7) Context Isolation and Patient Switching

Current safety control in UI:
- `app/src/pages/Explorer/Assistant.tsx` stores `messagesByPatient` keyed by `patientId`.
- This prevents cross-patient chat history leakage when switching patients.

Operational rule:
- Never send history from a different `patient_id` in a chat request.

Future hardening recommended:
- Add server-side session checks to enforce patient-history consistency.

## 8) Change Management Checklist

When changing SDK/runtime code:
1. Keep `/api/assistant/chat` contract backward compatible.
2. Preserve citation-grounding path through deterministic evidence retrieval.
3. Re-validate tool restrictions and web-call caps.
4. Confirm fallback behavior and `engine` response values.
5. Run frontend and backend checks.

Minimum verification commands:
```bash
cd app && npm run lint && npm run build
cd .. && uv run python -m compileall api
```

## 9) Immediate Known Gaps

- Stance behavior (`opinionated` vs `balanced`) is still mostly phrasing-level.
- Server does not yet persist chat sessions; context is frontend-managed only.
- No explicit profile registry yet (single profile wired by folder convention).

## 10) Next Recommended Upgrades

1. Add profile registry and selector env var.
2. Add server-side conversation/session layer keyed by `(patient_id, session_id)`.
3. Add structured output schema enforcement (`output_format`) in Agent SDK path.
4. Add regression harness for 20-50 fixed provider questions across risk cohorts.
