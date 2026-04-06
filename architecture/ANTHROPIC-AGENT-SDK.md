# Anthropic Agent SDK Integration

For full operating guidance, use:
- `architecture/ANTHROPIC-SDK-OPERATING-REPORT.md`
- `architecture/FHIR-AGENT-CONTEXT-ENGINEERING-REPORT.md`

This file is the quick-start reference.

This project now supports two provider-assistant runtimes behind the same API endpoint:

- `deterministic` (existing rules-based chart assistant)
- `anthropic` (Claude Agent SDK with scoped chart tools)

Endpoint stays the same:

- `POST /api/assistant/chat`

## Runtime Selection

Set environment variable:

```bash
export PROVIDER_ASSISTANT_MODE=anthropic
```

Accepted values:

- `deterministic` (default)
- `anthropic`
- `anthropic_agent`
- `agent_sdk`
- `anthropic_sdk`

If Anthropic mode fails, server falls back to deterministic mode unless disabled:

```bash
export PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC=true
```

## Required Credentials

```bash
export ANTHROPIC_API_KEY=your_key_here
```

## Anthropic Runtime Tuning

```bash
export PROVIDER_ASSISTANT_MODEL=claude-sonnet-4-5
export PROVIDER_ASSISTANT_MAX_TURNS=6
export PROVIDER_ASSISTANT_MAX_BUDGET_USD=0.20

# Optional web tools
export PROVIDER_ASSISTANT_ENABLE_WEB_SEARCH=false
export PROVIDER_ASSISTANT_WEB_SEARCH_MAX_USES=2
export PROVIDER_ASSISTANT_ENABLE_WEB_FETCH=false
export PROVIDER_ASSISTANT_WEB_FETCH_MAX_USES=2
```

## Personality And Behavior Files

Scoped agent profile directory:

- `api/agents/provider-assistant/CLAUDE.md`
- `api/agents/provider-assistant/METHODOLOGY.md`
- `api/agents/provider-assistant/RULES.md`

These files define voice, reasoning policy, pushback behavior, and operational rules.

## How It Is Wired

1. Router: `api/routers/assistant.py`
2. Mode selector: `api/core/provider_assistant_service.py`
3. Deterministic engine: `api/core/provider_assistant.py`
4. Anthropic engine: `api/core/provider_assistant_agent_sdk.py`

The Anthropic engine exposes two MCP tools to Claude:

- `get_patient_snapshot`
- `query_chart_evidence`

Both tools call the same deterministic evidence-retrieval function (`get_relevant_provider_evidence`) to keep citations and ranking consistent between modes.

## Response Contract

`ProviderAssistantResponse` now includes:

- `engine`: `deterministic`, `anthropic-agent-sdk`, or `deterministic-fallback`

This lets the UI show which runtime produced the answer.
