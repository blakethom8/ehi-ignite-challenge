# EHI Cursor sidecar

Small **Node** (TypeScript) HTTP service that runs the Cursor **TypeScript SDK** ([`@cursor/sdk`](https://cursor.com/docs/api/sdk/typescript)) so the main **FastAPI** app can offer a **`cursor` assistant mode** without embedding JavaScript in Python.

This file is written for **future coding/agents** who need intent, boundaries, and levers—not only run instructions.

---

## Why this exists (intent)

1. **Vendor SDK boundary** — Cursor ships a first-class **TypeScript** agent API (`Agent.prompt`, `Agent.create`, MCP, cloud/local runtimes). There is no supported in-process Python equivalent. A **thin Node service** is the straightforward way to use that SDK from a Python backend.

2. **Harness and comparison** — The product already has:
   - **Deterministic** chart Q&A ([`api/core/provider_assistant.py`](../api/core/provider_assistant.py))
   - **Context** mode — one Anthropic call with pre-built clinical context ([`api/core/provider_assistant_context.py`](../api/core/provider_assistant_context.py))
   - **Anthropic Agent SDK** — multi-turn agent + MCP tools ([`api/core/provider_assistant_agent_sdk.py`](../api/core/provider_assistant_agent_sdk.py))

   The sidecar path adds a **Cursor-runtime harness**: same **patient grounding contract** on the Python side (baseline evidence from `get_relevant_provider_evidence`), with the **LLM/agent loop** executed by Cursor’s runtime. That lets you compare **model choice**, **latency**, **answer shape**, and (once MCP is wired) **tool behavior** against the Anthropic agent path **without** mixing Cursor imports into Python.

3. **Isolation and upgrades** — Cursor SDK version bumps, auth quirks, and runtime behavior stay in **`cursor-sidecar/`** and `package.json`. The core clinical API remains Python.

---

## What we are trying to achieve

| Goal | How this harness supports it |
|------|------------------------------|
| **A/B models** in the Cursor runtime | `model` on `/invoke` and env defaults / allowlists (see below). Python mirrors allowlist before calling the sidecar. |
| **Auditable chart grounding** | FastAPI always builds **`baseline_evidence`** via `get_relevant_provider_evidence` and passes it in the invoke body. Citations returned to the client are **filtered to baseline keys** in [`api/core/provider_assistant_cursor.py`](../api/core/provider_assistant_cursor.py) (same idea as the Anthropic agent path). |
| **Operational parity (future)** | [`api/routers/cursor_internal_tools.py`](../api/routers/cursor_internal_tools.py) exposes HTTP endpoints that mirror the Anthropic MCP tools (`query-chart-evidence`, `patient-snapshot`, `run-sql`). **v1** does *not* register them as Cursor `mcpServers` yet; the agent is prompted with baseline JSON only. Wiring MCP is the next step for true tool parity. |
| **Safe fallbacks** | [`api/core/provider_assistant_service.py`](../api/core/provider_assistant_service.py) can fall back to deterministic mode if the sidecar or Cursor SDK fails (`PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC`). |

Non-goals for this package: **owning patient persistence**, **FHIR parsing**, or **SQL-on-FHIR** — that stays in Python.

---

## Architecture (mental model)

```text
Client / React
       │  POST /api/assistant/chat  (mode=cursor)
       ▼
FastAPI
  • build baseline_evidence (get_relevant_provider_evidence)
  • optional: enforce CURSOR_SIDECAR_MODEL_ALLOWLIST
  • POST  CURSOR_SIDECAR_URL/invoke  + JSON body
       │
       ▼
cursor-sidecar (this service)
  • Agent.prompt(prompt, { apiKey, model, local: { cwd, settingSources: [] } })
  • parse model JSON → answer / confidence / citations / follow_ups
       │
       ▼
Response normalized to AssistantResult → same API contract as other modes
```

---

## HTTP API (this service)

| Method | Path | Purpose |
|--------|------|---------|
| `GET` | `/health` | Liveness; Python calls this before `/invoke` today. |
| `POST` | `/invoke` | Run one Cursor `Agent.prompt` with the JSON body below. |

### `POST /invoke` body (JSON)

| Field | Required | Notes |
|-------|----------|--------|
| `patient_id` | yes | Echoed into the prompt for traceability. |
| `question` | yes | Provider question. |
| `stance` | no | Default `opinionated` if omitted. |
| `history` | no | Last turns; same shape as API (`role`, `content`). |
| `baseline_evidence` | no | **Should be supplied by Python** — full snapshot from `get_relevant_provider_evidence`. If missing, the prompt warns the model (only useful for debugging). |
| `model` | no | Cursor model id; must pass **sidecar** allowlist when `CURSOR_SIDECAR_MODEL_ALLOWLIST` is set. |

### Success JSON (normalized)

Includes at least: `answer`, `confidence`, `citations`, `follow_ups`, `engine`, `model_used`, and when available `run_id`, `duration_ms`.

### Error JSON

`{ "code": "config" | "execution" | "timeout" | "bad_request", "message": "..." }` with appropriate HTTP status. Python maps these to `CursorSidecarConfigurationError` / `CursorSidecarExecutionError` where applicable.

---

## Configuration reference

### Environment variables (sidecar process)

Set these on the **Node** container or the shell that runs `npm run dev`.

| Variable | Default | Purpose |
|----------|---------|---------|
| `CURSOR_API_KEY` | — | **Required** for real runs. Cursor dashboard → Integrations (or team service account). |
| `CURSOR_SIDECAR_PORT` | `3040` | Listen port. |
| `CURSOR_SIDECAR_MODEL` | `composer-2` | Default model id if `body.model` is omitted. |
| `CURSOR_SIDECAR_MODEL_ALLOWLIST` | *(unset)* | Comma-separated ids; if set, **only** these are accepted for `body.model` / default. |
| `CURSOR_SIDECAR_CWD` | `/workspace` | Local agent **working directory** (must be writable). Chart data is **not** read from the repo here; it is injected via `baseline_evidence`. This cwd exists to satisfy the SDK’s local runtime. |

### Environment variables (Python / FastAPI — same repo, different process)

These affect **how** the API talks to this service and how requests are gated:

| Variable | Purpose |
|----------|---------|
| `CURSOR_SIDECAR_URL` | Base URL (e.g. `http://127.0.0.1:3040` local, `http://cursor-sidecar:3040` in Compose). **Required** for `cursor` mode. |
| `CURSOR_SIDECAR_TIMEOUT_S` | HTTP client timeout for `/invoke` (default **120** in [`api/core/cursor_sidecar_client.py`](../api/core/cursor_sidecar_client.py)). |
| `PROVIDER_ASSISTANT_MODE` | Set to `cursor` (or `cursor_sdk`) to use this path by default. |
| `PROVIDER_ASSISTANT_FALLBACK_TO_DETERMINISTIC` | If `true`, failures fall back to deterministic engine (see service layer). |
| `PROVIDER_ASSISTANT_ALLOW_CLIENT_OVERRIDES` | When `false` (typical prod), client cannot set `mode` / `cursor_model` / etc. |
| `CURSOR_SIDECAR_MODEL` / `CURSOR_SIDECAR_MODEL_ALLOWLIST` | **Duplicated semantics** in Python for fail-fast validation before HTTP (`provider_assistant_cursor.py`). Keep in sync with sidecar env in deployment. |
| `CURSOR_INTERNAL_TOOL_SECRET` | Shared secret for **`/api/internal/cursor-tools/*`**. Sidecar does not use this until MCP is wired; Python enforces it on those routes. |

### Request-level overrides (API)

When client overrides are allowed: [`ProviderAssistantRequest`](../api/models.py) supports `mode: "cursor"` / `"cursor_sdk"` and optional **`cursor_model`** (string). That becomes the `model` field on `/invoke` after allowlist checks.

---

## Code map (what to change for future work)

| Change | Where |
|--------|--------|
| **Prompt text, JSON schema instructions** | [`src/prompt.ts`](src/prompt.ts) |
| **Parse / normalize model output** | [`src/parse.ts`](src/parse.ts) |
| **Swap `Agent.prompt` for `Agent.create` + `send` + `stream` + `wait`** | [`src/invoke.ts`](src/invoke.ts) — use when you need multi-turn session state inside one patient thread (remember async disposal per Cursor docs). |
| **Register MCP / HTTP tools toward FastAPI** | `mcpServers` in agent options — point at a **streamable HTTP MCP** URL or Cursor-supported transport; likely bridge [`api/routers/cursor_internal_tools.py`](../api/routers/cursor_internal_tools.py) or a dedicated MCP wrapper. |
| **Skip `/health` on every request** | [`api/core/provider_assistant_cursor.py`](../api/core/provider_assistant_cursor.py) / client — optional optimization via env flag (not implemented yet). |
| **Mode wiring, fallback, tracing span names** | [`api/core/provider_assistant_service.py`](../api/core/provider_assistant_service.py), [`api/routers/assistant.py`](../api/routers/assistant.py) |

---

## Local development

From repo root:

```bash
cd cursor-sidecar
npm install
export CURSOR_API_KEY="cursor_..."
export CURSOR_SIDECAR_PORT=3040
npm run dev
```

Point the API at it:

```bash
export CURSOR_SIDECAR_URL=http://127.0.0.1:3040
export PROVIDER_ASSISTANT_MODE=cursor
```

`GET /api/assistant/settings` includes a **`cursor_sidecar`** section (default model, allowlist-driven model list) for UI or bench tooling.

---

## Docker

- Image: [`deploy/Dockerfile.cursor-sidecar`](../deploy/Dockerfile.cursor-sidecar) (build context = **repository root**).
- Compose: [`deploy/docker-compose.prod.yml`](../deploy/docker-compose.prod.yml) — `cursor-sidecar` service and `CURSOR_SIDECAR_URL` on `api`.

Ensure **`CURSOR_API_KEY`** is present in the environment passed to the sidecar container for production or CI agents.

---

## Troubleshooting (for agents)

- **503 / “CURSOR_SIDECAR_URL is not set”** — Python has no sidecar URL; set env on the API process.
- **503 / “not reachable … /health”** — Sidecar down, wrong host/port, or firewall between containers.
- **400 / model not allowed** — `CURSOR_SIDECAR_MODEL_ALLOWLIST` rejects the requested id; align Python + Node env and request `cursor_model`.
- **502 / execution** — Cursor run failed or returned non-parseable output; inspect sidecar logs and Cursor dashboard usage for the SDK tag.

---

## Related documentation

- [Cursor TypeScript SDK](https://cursor.com/docs/api/sdk/typescript)
- Claude / Anthropic harness docs in-repo: [`docs/architecture/ANTHROPIC-AGENT-SDK.md`](../docs/architecture/ANTHROPIC-AGENT-SDK.md), [`docs/architecture/CONTEXT-PIPELINE.md`](../docs/architecture/CONTEXT-PIPELINE.md) (mode selector table)
