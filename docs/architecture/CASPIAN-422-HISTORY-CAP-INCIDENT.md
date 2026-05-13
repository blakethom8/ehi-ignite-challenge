# Caspian 422 — History Content-Length Cap Incident

*Discovered: 2026-05-12 (UTC 2026-05-13 ~05:05). Status: diagnosed, fix not yet shipped. Triaged by: investigation against prod logs at `hetzner2:/opt/ehi-ignite`.*

> **TL;DR.** Caspian appears to "stop answering" partway through a deep conversation. The cause is a per-message content-length cap on the backend (`max_length=8000`) combined with a frontend that echoes the full prior conversation back on every turn. When Caspian writes a long answer, the next user turn carries that answer in `history[].content`, fails Pydantic validation with **HTTP 422 Unprocessable Content** before the agent loop runs, and the UI shows silence. Not related to the 2026-05-13 04:49Z deploy.

---

## Symptom

A user reported: *"I was having a good conversation with Caspian and it stopped answering my questions."*

From the user's perspective, the UI accepts the question but no response ever streams back.

---

## Timeline (UTC)

Session `sess_6c767c5a0d5d473ca991b81d4c3445e3`, workspace `workspace-75ac4674-a563-4b28-8cc1-b4fa363f948f`:

| Time (UTC) | Turn | Question (truncated) | Result | HTTP | Duration |
|---|---|---|---|---|---|
| 04:49:30 | — | Production deploy (containers restarted) | — | — | — |
| 04:57:01 | 1 | "Thanks for this. I may have to get surgery on my shoulder soon. should I be concerned of any of my medications?" | ok | 200 | 14ms* |
| 05:01:19 | 2 | "okay so interesting. I asked another agent and they were able to realize that the Methylprednisolone..." | ok | 200 | 15ms* |
| 05:02:35 | 3 | "so you did not see the start date for the methlyprednisolone? It seems like maybe my pdf parsing to FHIr may have missed the date." | ok | 200 | 16ms* |
| 05:04:14 | 4 | "okay, so a couple of things. You are sharing evidence in the request that has no relation to this request... is the evidence share back real..." | ok | 200 | 13ms* |
| 05:05:00 | 5 | "could you run tool calls to look more deeply into my FHIR Json and tell me what you find?" | **error** | **422** | 1.2ms |
| 05:06:43 | 5 (retry) | (same) | **error** | **422** | 1.8ms |

\* The `duration_ms` field on trace rows reflects only the synchronous-handler portion, not the full streaming completion — actual answer generation took longer. The point is that turns 5 and 5-retry have ~1ms durations, consistent with pre-flight validation rejection.

The 4 successful turns produced streamed answers via `POST /api/assistant/chat/stream` (visible in container logs as `200 OK`). The 2 failed turns hit the same endpoint and returned `422 Unprocessable Content` immediately, with **zero spans recorded** — the agent loop never started.

---

## Root cause

Two pieces of code in tension:

### Backend — `api/models.py:734-746`

```python
class ProviderAssistantTurn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    role: Literal["user", "assistant"]
    content: str = Field(min_length=1, max_length=8000)
```

Every entry in the request's `history` array has a hard cap of 8000 characters. Exceed it → Pydantic raises ValidationError → FastAPI returns 422 → the request is rejected before any handler code runs.

### Frontend — `app/src/components/atlas/useCaspianAssistantSession.ts:462-465`

```typescript
const history: ProviderAssistantTurn[] = messages.map((message) => ({
  role: message.role,
  content: message.content,
}));
```

The frontend maps every prior message — user and assistant — into the history payload **verbatim, with no truncation, no per-message length cap, and no awareness of the backend's 8000-char limit**. Whatever the agent streamed last turn is sent back in full on the next turn.

### The combination

The conversation in question was a deep technical follow-up: shoulder-surgery preop safety review, Methylprednisolone start-date investigation, then a complaint about evidence-relevance. These are exactly the kinds of questions where Caspian produces long answers with multi-section evidence walks, fact tables, and per-medication risk notes. One of those assistant turns crossed 8000 characters. From that point on, every subsequent user turn carries an over-cap entry in `history` and gets rejected at the door.

The user retried turn 5 (05:05 → 05:06) and got the same 422 because the offending content is in the conversation state, not the new question.

---

## Why the deploy is a red herring

The 04:49Z deploy rebuilt both `api` and `app` containers from the same commit, so both halves shipped consistent code. The user successfully completed 4 turns after the deploy before hitting the cap. The cap-vs-history-echo bug exists in the codebase as deployed and would manifest equally on any prior build that had the same schema constraint.

The deploy is relevant only in that it wiped pre-deploy `docker logs` from memory, which slowed diagnosis. The persisted `data/traces.db` survived the restart and is what we used to reconstruct the timeline.

---

## Evidence

Pulled from `hetzner2:/opt/ehi-ignite/data/traces.db` via the live api container's Python:

```text
trace_id          status   duration_ms    question (truncated)
94b7374f...       error    1.8            "could you run tool calls to look more deeply into my FHIR Json..."
1da736f7...       error    1.2            "could you run tool calls to look more deeply into my FHIR Json..."
5ed548dd...       ok      13.5            "okay, so a couple of things. You are sharing evidence..."
3716d05a...       ok      16.0            "so you did not see the start date for the methlyprednisolone?..."
43514302...       ok      14.7            "okay so interesting. I asked another agent..."
9e503509...       ok      14.5            "Thanks for this. I may have to get surgery on my shoulder soon..."
```

Container access logs corroborate:

```
05:04:14  POST /api/assistant/chat/stream   200 OK
05:05:00  POST /api/assistant/chat/stream   422 Unprocessable Content
05:06:43  POST /api/assistant/chat/stream   422 Unprocessable Content
```

Both error traces have zero spans recorded (`SELECT count(*) FROM spans WHERE trace_id IN (...)` → 0). The agent loop never executed.

---

## Fix options

| # | Where | Change | Effort | Trade-off |
|---|---|---|---|---|
| 1 | `api/models.py:738` — `ProviderAssistantTurn.content` | Raise `max_length` from 8000 to ~32000 | one-line | Buys headroom but doesn't eliminate the failure mode — Caspian's longer artifacts (workflow runs, fact walks) keep getting longer. |
| 2 | `app/src/components/atlas/useCaspianAssistantSession.ts:462` | Truncate prior assistant content client-side before sending — e.g., keep first 4000 + last 2000 chars, mark middle with `[...truncated for context...]` | ~15 min | Keeps backend contract honest. Some fidelity loss on echo-back of long agent answers, but the **agent already has** its own context — history is just a recap for the model, not source-of-truth. |
| 3 | `api/routers/assistant.py:336` validator | Server-side leniency: instead of rejecting the request, truncate over-cap history entries with a logged warning. **Never 422 a user mid-conversation for content length.** | ~30 min | Most robust. Treats long content as a UX failure to absorb, not a security failure to reject. Requires moving validation from the Pydantic field to a custom pre-handler. |
| 4 | All of the above | (1) raise cap to 32000, (2) truncate client-side at 8000 to be safe, (3) server-side last-resort truncation | ~45 min | Defense in depth. Recommended. |

### Recommended fix

**Option 4 (all three).** Principle: the backend should never 422 a user mid-conversation because of content length. That's a UX failure dressed as a validation error. The right behavior is:

1. **Frontend** sends a sensible-size history (truncating long prior assistant turns to the most useful slice).
2. **Backend cap** is set high enough that normal traffic never hits it (32k chars ≈ ~8k tokens — well above any realistic single agent turn).
3. **Backend** *additionally* truncates instead of rejecting, so an old/buggy frontend or a future schema mismatch can't silently lock a user out mid-thread.

Separately, audit other `extra="forbid"` + tight-length-cap pairings on streaming endpoints — this same failure mode could exist elsewhere (e.g., `ProviderAssistantContextPackage` has `instructions: max_length=1500`, `question: max_length=4000`).

---

## Action items (for tomorrow)

- [ ] Confirm diagnosis: open the affected session in the browser, inspect `localStorage["caspian:sess_6c767c5a0d5d473ca991b81d4c3445e3:messages"]`, find the assistant message whose `content.length > 8000`, screenshot for the fix PR.
- [ ] Ship fix per Option 4 (single commit ok — three small changes).
- [ ] Add a regression test: `POST /api/assistant/chat/stream` with a history entry of 9000 chars. Pre-fix: expect 422. Post-fix: expect 200 (with content truncated server-side) and a warning logged.
- [ ] Audit other request models for the same pattern (tight `max_length` + `extra="forbid"` on multi-turn payloads). Candidates: `ProviderAssistantRequest.question` (4000), `ProviderAssistantContextPackage.*`.
- [ ] Consider: should the API return 200 + a warning header instead of 422 for any validation issue on chat endpoints? Streaming UX needs the request to *complete*, not fail loudly.
- [ ] Link this incident from `PIPELINE-LOG.md` once fixed, so the experiment journal stays the source of truth.

---

## Why this matters beyond the immediate fix

The bug surfaced because a user was having the *best* kind of conversation with Caspian — deep, multi-turn, evidence-heavy, the surgeon-doing-chart-review scenario the entire product is built for. The system rewarded that engagement by silently locking the user out. That is the exact opposite of the trust posture Caspian is supposed to hold ([AGENTIC-HARNESS.md](./AGENTIC-HARNESS.md)).

Two lessons for the broader codebase:

1. **Streaming chat endpoints should never 422 for content length.** The user has no recovery path — they didn't author the over-cap content, the agent did, and they have no way to edit it out of the conversation state from the UI. Treat content-length on chat endpoints as a "fit-the-content" problem (truncate, summarize), not a "reject-the-request" problem.
2. **`extra="forbid"` plus tight string caps is a fragile combination on payloads that include echoed prior agent output.** Either the cap needs slack proportional to what the agent itself can emit, or the validator needs to be lenient. This is structurally the same risk on every chat-like endpoint we'll add.

---

## Cross-references

| For depth on... | Read |
|---|---|
| The full backend request schema | `api/models.py:734-812` (`ProviderAssistantTurn`, `ProviderAssistantRequest`) |
| The chat-stream handler | `api/routers/assistant.py:335-...` |
| Frontend history-shaping | `app/src/components/atlas/useCaspianAssistantSession.ts:458-478` |
| LLM tracing (how we reconstructed the timeline) | [tracing.md](./tracing.md), `data/traces.db` schema |
| Caspian trust posture | [AGENTIC-HARNESS.md](./AGENTIC-HARNESS.md) |
