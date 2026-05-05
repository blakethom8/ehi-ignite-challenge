# Streaming + Gateway — Connection Architecture for the Skill Runtime

> **Status:** Architecture record. Documents the connection layer between
> the agent runtime and clients, the trade-offs that drove the current
> design, and how it evolves as the runtime moves through worker phases
> W1 → W2 → W3.
>
> **Companion docs:** [`SKILL-AGENT-WORKSPACE.md`](SKILL-AGENT-WORKSPACE.md)
> (the layered architecture), [`SELF-MODIFYING-WORKSPACE.md`](SELF-MODIFYING-WORKSPACE.md)
> (save destinations), [`tracing.md`](tracing.md) (observability).
>
> **Last updated:** 2026-05-05

---

## 1. The question

A clinician opens the Trial Finder. The agent starts a run. As the agent
queries ClinicalTrials.gov, parses inclusion criteria, registers
citations, and writes per-trial sections, **how does that progress get to
the browser?**

The naive options span a spectrum:

```
poll ←──────────────────── SSE ───────────── WebSockets ──── separate gateway service
 simplest                                                        most flexible
 highest latency                                                 most infra
```

This doc records the call we're making, why, and where each option
becomes worth its cost.

## 2. What's wired today (the W1 baseline)

```
┌──────────┐   poll every 2s   ┌──────────────┐   read   ┌─────────────────┐
│ Browser  │ ────────────────► │ FastAPI GET  │ ────────►│ /cases/{pid}/.. │
│ React Q  │ ◄──────────────── │  endpoints   │          │ workspace.md    │
└──────────┘                   └──────────────┘          │ transcript.jsonl│
                                                         │ citations.jsonl │
                                                         │ approvals.jsonl │
                                                         │ status.json     │
┌──────────────────┐                                     │ output.json     │
│ Worker pool task │ ───────── write ────────────────────►                 │
│ (asyncio)        │                                     └─────────────────┘
│ runs the agent   │
└──────────────────┘
```

The disk *is* the source of truth. The worker writes through mediated
primitives (`workspace.write`, `workspace.cite`, `workspace.escalate`);
the router reads from disk on every poll. They share no in-memory state.

Properties:

| Concern | Today's behavior |
|---|---|
| Latency | Up to 2s per UI update (the React Query refetch interval) |
| Multi-tab | Each tab polls independently — works, no fan-out logic |
| Reconnect | Trivial — next poll just succeeds |
| Backpressure | None — disk is durable, slow client doesn't slow runner |
| Cost | Light — small JSON reads, FastAPI handles trivially |
| Observability | Disk artifacts are the audit trail; tracing.py captures spans |

This is fine for a deterministic Phase-0..5 loop that emits ~10–30
events per run. It will feel laggy the moment we wire in token-by-token
LLM streaming (commit 4), where a 2s poll cadence misses the entire UX
benefit of "watching the agent think."

## 3. The connection-layer options, plainly

### Option A — Server-Sent Events (SSE)

One-way, server → client, over plain HTTP. `Content-Type:
text/event-stream`. The browser's `EventSource` API reconnects
automatically on transient drops.

**Why it fits us:** the connection direction matches the reality of
agent runs — the *agent* produces a stream of progress; the *client*
mostly watches. The handful of client → server actions we need
(escalation resolution, save) are discrete request/response moments
that fit fine as POST endpoints alongside the SSE stream.

**Trade-offs:**
- ✅ Standard HTTP — passes through proxies, CDNs, our existing nginx
- ✅ Browser auto-reconnect with `Last-Event-ID` resume
- ✅ Trivial debugging — `curl -N http://.../events` shows the stream
- ✅ Survives behind authenticated FastAPI middleware unchanged
- ⚠️ One-way only — needs a separate POST channel for client → server
- ⚠️ Long-lived connection — server must be tolerant to many open sockets

**Verdict:** the right call for W1. Cheap to add, cheap to remove.

### Option B — WebSockets

Bidirectional, persistent, framed binary or text.

**Why we don't need it (yet):** every interaction we have today is either
"watch progress" (SSE) or "discrete action" (POST). We don't yet support
mid-run inline comments, free-form chat, or computer-use turns where the
client needs to push messages into the agent loop. When we do — likely
when commit 4's Claude integration grows tool calls that genuinely
require user-mid-stream input — we revisit. Until then WebSockets buy
us complexity (framing, ping/pong, proxy quirks) without buying capability.

### Option C — Gateway service (separate process)

A dedicated service in front of the agent workers. Owns the long-lived
client connections, multiplexes them across workers, normalizes auth +
observability + rate limits. Often pairs with Redis for cross-worker
fan-out and tool-server colocation.

**Where this becomes attractive:**

1. **Out-of-process agents.** The W2 architecture (Docker sandbox per
   run) makes it physically impossible for the agent to serve HTTP to
   the browser — it can't bind a port the public can reach. Something
   in front has to relay events. **That something is a gateway, even
   if you don't call it that.**
2. **Multiple LLM providers.** If we proxy Claude + GPT + a local
   open-weight model behind a unified surface, the gateway is the
   right layering. Today we use a single SDK directly; deferred.
3. **Multi-tenant scale.** When a single FastAPI process can't hold all
   open client connections (thousands of concurrent runs), we need
   horizontal worker scaling with shared state (Redis pub/sub). Far
   from our current scale.

**Our position today:** **FastAPI itself plays the gateway role.** It's
the single auth point, the single observability point, the single place
where streaming connections live. We just hadn't surfaced that role
explicitly.

We do *not* need a separate gateway *service* until W2 forces it.
Building one now is premature infrastructure.

## 4. Where this lives in the layered architecture

Per [`SKILL-AGENT-WORKSPACE.md`](SKILL-AGENT-WORKSPACE.md) §6.0 the
runtime is three layers:

- Layer 1 — universal substrate (workspace fs, citation graph,
  escalation primitive, MCP wire, tracing)
- Layer 2 — default agent loop
- Layer 3 — per-skill files

The streaming connection layer is **Layer 1 infrastructure** — it sits
beside the workspace fs and the citation graph. Skills don't know it
exists; they call `workspace.write/cite/escalate` and the runtime
decides what to mediate, persist, and broadcast.

```
                    ┌──────────────────────────────┐
                    │ Layer 1 — universal substrate │
                    │                              │
                    │  workspace.fs                │
                    │  citation graph              │
                    │  escalation primitive        │
                    │  tracing                     │
   ─────new────►    │  EventHub (per-run pub/sub)  │ ──── SSE  ──► browsers
                    │  MCP wire                    │
                    └──────────────────────────────┘
```

The `EventHub` is the new piece. It's a per-run pub/sub the runtime
publishes to; the SSE endpoint subscribes to it. Disk artifacts stay
unchanged — they remain the durable replay surface.

## 5. The design: `EventHub` + replay-then-subscribe

### 5.1 `EventHub` — per-run multi-subscriber fan-out

One hub per run. Created when the worker pool submits a run; closed
when the run terminates.

```python
class EventHub:
    """Per-run pub/sub. Non-blocking publish, multi-subscriber fan-out."""

    def publish_nowait(self, event: dict) -> None:
        """Publish to every subscriber. Drops the event for any subscriber
        whose queue is full (prevents a slow client from blocking the
        runner). Disk persistence is the source of truth — a dropped
        event is recoverable via transcript.jsonl replay."""

    async def subscribe(self) -> AsyncIterator[dict]:
        """Yield events from this point forward. Late subscribers do NOT
        get historical events — replay happens out-of-band via the
        transcript. Combining replay + subscribe is the SSE endpoint's
        job."""

    async def close(self) -> None:
        """End-of-stream signal. Subscribers receive a sentinel and
        complete cleanly; the SSE response then closes."""
```

Key properties:

1. **Non-blocking publish.** `_emit()` from inside the runner stays
   synchronous. `publish_nowait` puts to each subscriber's bounded
   queue with `put_nowait`; full queues drop the event. This is safe
   because…
2. **Disk is durable.** Every event the runner publishes is *also*
   appended to `transcript.jsonl` *before* publish. A dropped live
   event is recoverable by re-reading the transcript.
3. **Late subscribers get full state via replay.** The SSE endpoint
   first emits every event in `transcript.jsonl`, *then* subscribes
   for new events. So a client that connects mid-run sees the full
   history before joining the live stream. A client that connects
   *after* the run finishes gets the full transcript and a
   `stream_closed` sentinel.
4. **Subscribers are isolated.** Each subscriber has its own queue;
   one slow client doesn't slow another or the runner.

### 5.2 SSE endpoint contract

```
GET /api/skills/{skill_name}/runs/{run_id}/events?patient_id={pid}

Response: text/event-stream

   data: {"at":"2026-05-05T...","kind":"run_started","run_id":"abc"}
   
   data: {"at":"2026-05-05T...","kind":"phase_complete","phase":0,"anchors":2}
   
   ...

   data: {"kind":"stream_closed"}
```

Behavior:

1. Resolve the run from disk (404 if not found).
2. **Replay**: yield every event in `transcript.jsonl` as `data:` lines.
3. **Subscribe**: if a hub exists for this run (i.e., the runner is
   still in flight or recently finished), subscribe and yield each
   new event.
4. **Close**: yield a final `{"kind":"stream_closed"}` event so the
   client knows to stop reading.

Headers we set: `Cache-Control: no-cache`, `X-Accel-Buffering: no`
(disables nginx buffering for the SSE path), `Connection: keep-alive`.

### 5.3 What the runner publishes

Every existing `_emit()` call publishes to the hub *and* appends to
disk. No change in API for the deterministic loop or for commit 4's
Claude integration. The contract is: **anything that lands in
`transcript.jsonl` also gets broadcast live.**

When commit 4 swaps in `claude-agent-sdk.query()`, token deltas can be
emitted as `kind: "agent_text_delta"` events — the SSE pipe handles
them without runtime changes.

### 5.4 Workspace markdown — hybrid update path

The workspace markdown itself isn't streamed event-by-event (it's a
diffable artifact, not a stream). We keep React Query polling for
`/workspace`, but we **invalidate that query when an SSE event of kind
`workspace_write` or `cite` arrives** — so the workspace updates
sub-second on writes without needing structured-diff streaming.

This hybrid keeps the SSE channel small and structured (events only)
while making the visible UX live.

## 6. Cohesiveness with the rest of the runtime

| Component | Before this change | After |
|---|---|---|
| `runner._emit()` | wrote to vestigial `asyncio.Queue` + `transcript.jsonl` | publishes to `EventHub` + writes `transcript.jsonl` |
| `runner._event_queue`, `runner.events()` | unused (dead code) | removed |
| `WorkerPool` | tracked runs by key | also tracks `EventHub` per run, closes on finish |
| Router | poll-only GET endpoints | adds streaming endpoint; existing GETs unchanged |
| Frontend `RunView` | polls `/transcript` every 2s | opens an `EventSource`; falls back to polling if SSE not supported |
| Frontend `WorkspacePane` | polled every 2s | still polls, but invalidates on relevant SSE events |
| Disk artifacts | source of truth | unchanged; still source of truth |

The change is contained to: `api/core/skills/event_hub.py` (new),
`api/core/skills/runner.py` (modified), `api/core/skills/worker.py`
(modified), `api/routers/skills.py` (one new endpoint),
`app/src/api/skills.ts` (one new helper),
`app/src/pages/Modules/TrialFinder/index.tsx` and
`/components/TranscriptPane.tsx` (consume SSE). **Nothing outside the
skills module is touched.**

## 7. The forward path

| Phase | Connection layer | Why |
|---|---|---|
| **W1 (today + this commit)** | SSE on FastAPI; in-process `EventHub`; disk-replay for late subscribers | Single FastAPI process holds runs and connections. Simple. |
| **W2 (Docker sandbox per run)** | FastAPI relays sandbox stdout/events into SSE. Sandbox writes events to a unix-socket-mounted endpoint; FastAPI's `EventHub` fans out to clients. | Sandbox can't serve HTTP. FastAPI becomes the literal gateway. |
| **W3 (microVM, multi-host)** | Add a small pub/sub (Redis Streams or NATS) between worker hosts and FastAPI instances. Same SSE endpoint shape. | One client may connect to a different FastAPI instance than the worker is running on. |
| **Multi-LLM providers** | Introduce a model gateway service if/when we proxy Claude + GPT + open-weight under one surface. Independent of the run-event SSE. | Different concern: model routing, not run streaming. |
| **WebSockets** | Add a WS endpoint when we genuinely need bidirectional mid-run client → agent input. Lives alongside SSE; doesn't replace it. | Mid-run inline comments, computer-use, free-form chat. |

Each step preserves the contract: **clients call FastAPI, FastAPI is
the gateway, disk is durable replay.** The implementation behind that
contract evolves; the contract doesn't.

## 8. What we explicitly do not promise yet

- **Cross-process pub/sub.** A second FastAPI worker process (e.g.,
  uvicorn `--workers 2`) won't share `EventHub` state — clients
  connecting to a different worker than the one running the run will
  see only the disk replay, not live events. Acceptable today (we run
  single-worker); a known item before W3.
- **Reconnect resume by `Last-Event-ID`.** We send `id:` lines but the
  endpoint doesn't yet honor `Last-Event-ID` headers from a
  reconnecting client — it always starts replay from the beginning.
  Cheap to add later.
- **Backpressure beyond drop-on-full.** A truly slow client misses
  events under sustained load. Disk replay covers correctness; the
  live experience degrades gracefully.
- **Per-event auth.** Auth is at connection time (the GET request).
  No mid-stream re-auth.
- **Computed-diff streaming of `workspace.md`.** We invalidate the
  whole-document query on write events; we don't ship a Yjs/Automerge-
  style live diff. Worth revisiting if the artifact grows large.

## 9. Decision summary

- **Build SSE on FastAPI now.** Adds the right Layer-1 primitive
  (`EventHub`) without committing to a separate gateway service.
- **Keep disk as the source of truth.** SSE is the fast path; replay
  is correctness.
- **Do not build a standalone gateway service yet.** FastAPI plays
  that role. A separate service becomes warranted at W2/W3 or when we
  add multi-LLM proxying.
- **Defer WebSockets** until we genuinely need mid-run client → agent
  input.
- **Keep the change inside the skills module.** No edits outside
  `api/core/skills/`, `api/routers/skills.py`, and the frontend
  TrialFinder paths.

## 10. References

- [`SKILL-AGENT-WORKSPACE.md`](SKILL-AGENT-WORKSPACE.md) §6.0 (layered architecture), §6.7 (worker phases W0–W4)
- [`SELF-MODIFYING-WORKSPACE.md`](SELF-MODIFYING-WORKSPACE.md) (save destinations consume the same hub for save events)
- [`tracing.md`](tracing.md) (per-span cost/token capture; orthogonal to SSE)
- [HTML SSE spec](https://html.spec.whatwg.org/multipage/server-sent-events.html)
- [FastAPI streaming responses](https://fastapi.tiangolo.com/advanced/custom-response/#streamingresponse)

---

*End of document.*
