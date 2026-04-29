# LLM Tracing & Observability

> Last updated: April 7, 2026

Every LLM call in the Provider Assistant is traced — prompt/response payloads (capped for storage), token counts, cost, tool calls, and latency. Traces are stored locally in SQLite and optionally exported to Langfuse for dashboards.

---

## Why This Exists

The Provider Assistant sends patient FHIR data to Claude and asks it to make safety-critical clinical assessments. Without observability:

- **You can't debug** — if the model gives a bad answer, what context did it actually see?
- **You can't optimize** — are we sending too much data? Too little? Which tool calls are useful?
- **You can't audit** — what exactly was sent to the model for a given patient query?
- **You can't budget** — how much does each query cost? How many tokens per patient?

The tracing system answers all of these by capturing the full round-trip of every LLM call.

---

## Security Notes

Tracing can contain PHI and other sensitive clinical context.

- Keep `TRACING_ENABLED=false` by default outside debugging workflows.
- Treat `data/traces.db` as sensitive local data (it is gitignored by default).
- If exporting to Langfuse, ensure your deployment/compliance posture allows it.
- Do not expose `/api/traces/*` publicly without authentication and access controls.

---

## Architecture

```
                         ┌──────────────────────────────────────┐
  POST /api/assistant/   │         TracingMiddleware            │
  chat                   │  Opens trace, extracts patient_id,   │
  ─────────────────────► │  question, stance from request body  │
                         └──────────┬───────────────────────────┘
                                    │
                                    ▼
                         ┌──────────────────────────────────────┐
                         │   provider_assistant_service.py      │
                         │                                      │
                         │  Records on trace:                   │
                         │  - engine (agent-sdk / deterministic) │
                         │  - confidence, citations, follow-ups │
                         │  - status (ok / error / fallback)    │
                         └──────────┬───────────────────────────┘
                                    │
                    ┌───────────────┼───────────────┐
                    ▼                               ▼
         ┌────────────────┐              ┌────────────────────┐
         │  Deterministic │              │  Agent SDK Runtime  │
         │  (no spans)    │              │                    │
         └────────────────┘              │  Span: RETRIEVAL   │
                                         │  └─ baseline_evidence
                                         │                    │
                                         │  Span: LLM         │
                                         │  └─ agent_query    │
                                         │    - prompt (capped) │
                                         │    - response (capped) │
                                         │    - tokens / cost │
                                         │    - turns         │
                                         │                    │
                                         │  Span: TOOL (×N)   │
                                         │  └─ get_patient_snapshot
                                         │  └─ query_chart_evidence
                                         └────────────────────┘
                                                    │
                         ┌──────────────────────────┘
                         ▼
              ┌─────────────────────┐     ┌──────────────────┐
              │   SQLite            │     │   Langfuse        │
              │   data/traces.db   │     │   (optional)      │
              │                     │     │                   │
              │   traces table      │     │   Dashboard       │
              │   spans table       │     │   Cost tracking   │
              └─────────────────────┘     └──────────────────┘
                         │
                         ▼
              ┌─────────────────────┐
              │   Traces API        │
              │                     │
              │   GET /api/traces/  │
              │   GET /api/traces/{trace_id}
              │   GET /api/traces/summary
              └─────────────────────┘
```

---

## What Gets Captured

### Trace (one per request)

| Field | Description |
|-------|-------------|
| `trace_id` | Unique identifier |
| `patient_id` | Which patient was queried |
| `question` | The provider's clinical question |
| `stance` | `opinionated` or `balanced` |
| `engine` | `anthropic-agent-sdk`, `deterministic`, or `deterministic-fallback` |
| `status` | `ok`, `error`, or `fallback` |
| `confidence` | `high`, `medium`, or `low` |
| `answer_preview` | First 500 chars of the response |
| `answer_length` | Total response length |
| `citation_count` | Number of FHIR citations in the response |
| `follow_up_count` | Number of follow-up suggestions |
| `duration_ms` | Wall-clock time for the full request |
| `created_at` | Timestamp |

### Spans (nested within a trace)

Each span has a **kind**:

| Kind | Name | What It Captures |
|------|------|-----------------|
| `retrieval` | `baseline_evidence` | Initial fact retrieval from FHIR data before the LLM call |
| `llm` | `agent_query` | The full Claude Agent SDK execution — prompt, response, tokens, cost, turns |
| `tool` | `get_patient_snapshot` | Agent's call to retrieve a safety/risk snapshot |
| `tool` | `query_chart_evidence` | Agent's call to retrieve evidence for a specific clinical question |

### LLM Span Detail

The `agent_query` span is the most important. It captures:

| Field | Description |
|-------|-------------|
| `input_data` | Prompt payload (JSON-capped to 50KB) — system instructions + patient data + baseline evidence + conversation history |
| `output_data` | Claude response payload (JSON-capped to 50KB) — answer payload, stop reason, and metadata |
| `input_tokens` | Tokens sent to Claude |
| `output_tokens` | Tokens generated by Claude |
| `cache_read_tokens` | Tokens served from prompt cache (reduces cost) |
| `total_cost_usd` | Dollar cost of this call |
| `num_turns` | How many turns the agent took (tool calls + final answer) |
| `duration_ms` | Time spent in the SDK |

---

## Configuration

All configuration is in `.env` (loaded via `python-dotenv` in `api/main.py`):

```bash
# --- Tracing / Observability ---
TRACING_ENABLED=true              # Master switch (default: false)
TRACES_API_ENABLED=false          # Enable /api/traces/* endpoints (default: false)
TRACES_API_TOKEN=...              # Required for /api/traces/* in production

# Langfuse (optional — for production dashboards)
# LANGFUSE_PUBLIC_KEY=pk_...
# LANGFUSE_SECRET_KEY=sk_...
# LANGFUSE_HOST=https://cloud.langfuse.com
```

When `TRACING_ENABLED=false` (the default), the tracing system has **zero overhead** — context managers yield `None` and no-op immediately. Keep `TRACES_API_ENABLED=false` on public deployments unless the route is protected with `TRACES_API_TOKEN` and only used from trusted admin clients.

---

## API Endpoints

### `GET /api/traces/`

List traces with optional filters.

```bash
# All traces, most recent first
curl localhost:8001/api/traces/

# Filter by patient
curl "localhost:8001/api/traces/?patient_id=Brian582_Legros616_..."

# Filter by engine or status
curl "localhost:8001/api/traces/?engine=anthropic-agent-sdk&status=ok"

# Pagination
curl "localhost:8001/api/traces/?limit=10&offset=20"
```

### `GET /api/traces/{trace_id}`

Full trace detail with all spans, including stored prompt/response payload text.

```bash
curl localhost:8001/api/traces/eb5124c39edf4ffea17db8e8df70d705
```

### `GET /api/traces/summary`

Aggregate statistics across all traces.

```bash
curl localhost:8001/api/traces/summary
```

Returns:

```json
{
  "total_traces": 7,
  "avg_duration_ms": 10904.5,
  "total_input_tokens": 44,
  "total_output_tokens": 3430,
  "total_cache_read_tokens": 49269,
  "total_cost_usd": 0.223,
  "avg_cost_usd": 0.112,
  "by_engine": {"anthropic-agent-sdk": 2, "deterministic": 1, "deterministic-fallback": 4},
  "by_status": {"ok": 3, "fallback": 4},
  "by_confidence": {"high": 3, "medium": 4}
}
```

---

## Files

| File | Role |
|------|------|
| `api/core/tracing.py` | Core module — Trace/Span models, SQLite storage, Langfuse export, query helpers |
| `api/middleware/tracing.py` | FastAPI middleware — opens traces for assistant chat requests |
| `api/routers/traces.py` | Read-only API — list, detail, summary endpoints |
| `api/core/provider_assistant_service.py` | Instrumented — records engine, confidence, status on each trace |
| `api/core/provider_assistant_agent_sdk.py` | Instrumented — LLM span, tool spans, retrieval span, token capture |
| `api/main.py` | Registers middleware and traces router, loads `.env` |
| `data/traces.db` | SQLite database (auto-created on first traced request, gitignored) |

---

## Storage

### SQLite Schema

```sql
CREATE TABLE traces (
    trace_id        TEXT PRIMARY KEY,
    patient_id      TEXT NOT NULL,
    question        TEXT NOT NULL,
    stance          TEXT NOT NULL,
    engine          TEXT,
    status          TEXT NOT NULL DEFAULT 'ok',
    confidence      TEXT,
    answer_preview  TEXT,
    answer_length   INTEGER DEFAULT 0,
    citation_count  INTEGER DEFAULT 0,
    follow_up_count INTEGER DEFAULT 0,
    duration_ms     REAL DEFAULT 0,
    created_at      TEXT NOT NULL
);

CREATE TABLE spans (
    span_id           TEXT PRIMARY KEY,
    trace_id          TEXT NOT NULL,
    kind              TEXT NOT NULL,        -- 'llm', 'tool', 'retrieval'
    name              TEXT NOT NULL,
    input_data        TEXT,                 -- JSON payload (capped at 50KB)
    output_data       TEXT,                 -- JSON payload (capped at 50KB)
    input_tokens      INTEGER,
    output_tokens     INTEGER,
    cache_read_tokens INTEGER,
    total_cost_usd    REAL,
    num_turns         INTEGER,
    duration_ms       REAL DEFAULT 0,
    error             TEXT,
    started_at        TEXT NOT NULL,
    FOREIGN KEY (trace_id) REFERENCES traces(trace_id)
);
```

### Direct SQLite Queries

```bash
# Recent traces
sqlite3 data/traces.db "SELECT trace_id, engine, status, duration_ms, created_at FROM traces ORDER BY created_at DESC LIMIT 10;"

# Total cost
sqlite3 data/traces.db "SELECT SUM(total_cost_usd) FROM spans WHERE kind='llm';"

# Avg tokens per call
sqlite3 data/traces.db "SELECT AVG(input_tokens), AVG(output_tokens), AVG(cache_read_tokens) FROM spans WHERE kind='llm';"

# View a specific prompt
sqlite3 data/traces.db "SELECT input_data FROM spans WHERE trace_id='...' AND kind='llm';"
```

---

## Langfuse Integration

When `LANGFUSE_PUBLIC_KEY` and `LANGFUSE_SECRET_KEY` are set, traces are exported to Langfuse in a background thread after each request. The mapping:

| Local | Langfuse |
|-------|----------|
| Trace | Trace (with patient_id, engine, status as metadata) |
| LLM Span | Generation (with model, token usage, cost) |
| Tool / Retrieval Span | Span (with kind, error as metadata) |

Langfuse provides dashboards for cost tracking, latency monitoring, and trace visualization out of the box.

---

## Context Propagation

Tracing uses Python `contextvars.ContextVar` for implicit propagation:

1. **Middleware** creates a `Trace` and sets `_current_trace` ContextVar
2. **Service layer** reads `get_current_trace()` to attach metadata
3. **Agent SDK** calls `start_span()` which reads the current trace and appends spans
4. **On request completion**, the middleware's `start_trace()` context manager exits and flushes everything to SQLite

This works across the async boundary because `asyncio.run()` (used by the Agent SDK) copies ContextVars into the new event loop.

---

## Typical Trace Example

A single Provider Assistant query against a complex patient (109 medications, 20 conditions):

```
Trace: eb5124c3...
  Engine: anthropic-agent-sdk
  Status: ok
  Duration: 36,002ms
  Cost: $0.089

  Spans:
  1. [retrieval] baseline_evidence          — 6ms
  2. [llm]      agent_query                 — 35,885ms
     Tokens: 26 in / 1,716 out / 24,821 cache read
     Turns: 4
     Prompt: 2,859 chars (system instructions + patient FHIR data + baseline evidence)
  3. [tool]     get_patient_snapshot         — 1ms
  4. [tool]     query_chart_evidence         — 1ms
  5. [tool]     query_chart_evidence         — 1ms
```

The agent took 4 turns: retrieved a patient snapshot, queried chart evidence twice, then produced its final answer with 3 citations and 3 follow-up suggestions.
