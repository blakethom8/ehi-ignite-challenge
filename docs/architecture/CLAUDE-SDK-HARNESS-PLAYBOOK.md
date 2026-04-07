# Claude SDK Harness Playbook

This document explains how to think about the Claude SDK as an application harness, how we use it in this project, and how to reuse the same approach in other products.

Audience:
- product builders
- backend engineers
- AI workflow designers

## 1) What "Claude Code SDK" Means In Practice

In this repository, we use the Python package `claude-agent-sdk` as the runtime harness.

Mental model:
- Claude is not just a text model endpoint.
- The SDK is an orchestration harness for:
  - tool-enabled reasoning loops
  - session/runtime controls
  - constrained permissions
  - structured outputs

Think of it as an "agent runtime adapter" between your application and Claude.

## 2) Why Use A Harness Instead Of Plain Prompt Calls

Plain model calls are enough for one-shot generation.

Harness mode is better when you need:
- tool execution (MCP tools, web tools)
- policy-enforced reasoning boundaries
- reusable runtime controls across many app flows
- better separation of concerns between:
  - retrieval
  - reasoning
  - response synthesis

In clinical use cases, this separation is mandatory for auditability and safety.

## 3) How We Use It In This Codebase

### Runtime architecture
- API endpoint: `POST /api/assistant/chat`
- Runtime selector chooses deterministic or Anthropic SDK mode.

Key files:
- `api/routers/assistant.py`
- `api/core/provider_assistant_service.py`
- `api/core/provider_assistant.py`
- `api/core/provider_assistant_agent_sdk.py`
- `api/models.py`

### Mode strategy
- `deterministic`: default and stable
- `anthropic`: agent loop with tools
- fallback available to deterministic on Anthropic failures

This gives fast reliability + optional advanced reasoning.

## 4) Personality Profiles: How We Drive Behavior

We split behavior into profile files under:
- `api/agents/provider-assistant/`

Files and intent:
- `CLAUDE.md`: voice and personality
- `METHODOLOGY.md`: reasoning sequence and evidence weighting
- `RULES.md`: hard constraints and runtime behavior

Pattern to scale profiles:
1. create profile directories per role/use case
2. select profile by env or route context
3. version profiles explicitly (`v1`, `v2`, etc.)
4. evaluate before promotion

## 5) Tool Harness Pattern We Use

Our Anthropic runtime exposes scoped MCP tools:
- `get_patient_snapshot`
- `query_chart_evidence`

Important design choice:
- tools call deterministic evidence retrieval (`get_relevant_provider_evidence`)
- model does synthesis, not raw parsing from full FHIR

Why this matters:
- citation consistency between deterministic and agentic modes
- lower hallucination risk
- easier debugging and regression testing

## 6) Context Strategy (FHIR-Specific)

Do not pass entire FHIR bundles into the model context.

Use layered context:
1. request envelope (patient, question, stance)
2. risk snapshot (flags, interactions, high-risk burden)
3. top ranked evidence units with citations
4. drill-down on demand only

Related deeper doc:
- `docs/architecture/FHIR-AGENT-CONTEXT-ENGINEERING-REPORT.md`

## 7) How To Leverage This Harness In Other Applications

### Reusable blueprint
1. Build deterministic retrieval/service layer first.
2. Define narrow tool interfaces over that layer.
3. Wire Claude SDK runtime with explicit allowed tools.
4. Add profile files for domain-specific behavior.
5. Keep fallback mode for reliability.

### Good fit use cases
- chart review copilots
- legal document risk triage
- incident postmortem assistants
- support operations copilots with policy constraints
- internal engineering assistants that must use local tools

### Anti-patterns
- giving model direct access to all raw records by default
- no fallback mode for production flows
- unbounded tool permissions
- no citation structure in outputs

## 8) Workflow Automation Patterns With Claude Harness

Use the same harness for background workflows, not just chat UI.

Examples:
- pre-op briefing generation on schedule
- daily patient risk re-evaluation jobs
- batch chart quality checks
- unresolved blocker escalation summaries

Recommended workflow shape:
1. fetch deterministic candidate data
2. run constrained agent synthesis
3. validate output schema
4. store artifact (JSON + human summary)
5. route downstream action (task, alert, queue)

## 9) Environment Strategy (Dev / Staging / Prod)

### Development
- quick iteration
- lower turn/budget caps
- verbose logging

### Staging
- production-like profiles and tools
- test key rotation and failure behavior
- run regression eval set

### Production
- strict tool allowlist
- budget caps and timeouts
- fallback enabled unless explicitly required off
- audit logs for question, tool calls, citations, confidence

## 10) Suggested "SDK Kit" Checklist

For each new app integrating Claude harness:

1. Runtime wrapper
- one service module that isolates SDK calls

2. Tool contract
- narrow MCP tools with stable input/output schemas

3. Profile pack
- `CLAUDE.md`, methodology, rules, domain constraints

4. Safety controls
- allowlist tools
- env-gated web access
- fallback mode

5. Observability
- engine label
- latency
- confidence distribution
- citation count
- failure category

6. Regression tests
- deterministic API tests
- optional live SDK tests gated by env

## 11) Testing In This Repository

Backend tests:
- `api/tests/test_assistant_api.py`

What they check:
- health endpoint
- deterministic assistant path
- Anthropic missing-key behavior
- fallback behavior
- placeholder-key rejection
- optional live Anthropic smoke test

Run:
```bash
uv run python -m unittest -v api.tests.test_assistant_api
```

Enable live SDK test:
```bash
RUN_ANTHROPIC_LIVE_TESTS=1 ANTHROPIC_API_KEY=<real_key> \
uv run python -m unittest -v api.tests.test_assistant_api.ProviderAssistantApiTests.test_assistant_chat_anthropic_live_if_enabled
```

## 12) Troubleshooting Quick Guide

If assistant shows "request failed":
1. check `/api/health`
2. confirm `/api/assistant/chat` exists in OpenAPI
3. verify `PROVIDER_ASSISTANT_MODE`
4. verify `ANTHROPIC_API_KEY` (not placeholder)
5. decide whether fallback should be on/off
6. inspect response `detail` and `engine`

## 13) Practical Recommendations For Next Iteration

1. Add profile registry + explicit profile selection per route/use case.
2. Add server-side session binding `(session_id, patient_id)` for context integrity.
3. Formalize context packet schema (TUNE-style) before Anthropic tool calls.
4. Add eval dashboards for latency, citation precision, and blocker recall.

---

Use this playbook as the top-level guide.
For implementation details, pair it with:
- `docs/architecture/ANTHROPIC-SDK-OPERATING-REPORT.md`
- `docs/architecture/FHIR-AGENT-CONTEXT-ENGINEERING-REPORT.md`
