# Tool Surface — Current Capabilities and Forward Path

> **Status:** Architecture record. Documents the tools the agent has
> *today*, the tools we deliberately don't have *yet*, and the
> recommended path for adding web search, web fetch, browser
> automation, and richer artifact production. Pairs with the runtime
> contract in [`SKILL-AGENT-WORKSPACE.md`](SKILL-AGENT-WORKSPACE.md).
>
> **Last updated:** 2026-05-05

---

## 1. What the agent can do today

The Layer-1 tool registry in `api/core/skills/agent_loop.py` exposes
exactly six tool aliases. A skill's `required_tools:` frontmatter
selects the subset it uses; `submit_final_artifact` is added
automatically because there's no other way to end a run.

| Skill alias | Agent-facing name | Kind | What it does |
|---|---|---|---|
| `workspace.write` | `workspace_write` | Local — Workspace primitive | Append-or-replace a section of `workspace.md`. Citations in `[cite:c_NNNN]` form must resolve. Anchors (e.g., `TRIAL_SECTIONS`) target named blocks. |
| `workspace.cite` | `workspace_cite` | Local — Workspace primitive | Register a citation. Returns `c_NNNN`. `source_kind ∈ {fhir_resource, external_url, clinician_input, agent_inference}`. Disk-persisted to `citations.jsonl`. |
| `workspace.escalate` | `workspace_escalate` | Local — Workspace primitive | Pause the run, surface a question to the clinician. `condition` must match a manifest-declared trigger or be `ad_hoc:` prefixed. |
| `submit_final_artifact` | `submit_final_artifact` | Local — Lifecycle | Submit the structured output. Runtime validates against the skill's `output_schema`. The only legitimate way to end a run. |
| `mcp.clinicaltrials_gov.search` | `clinicaltrials_search` | HTTP — Public API | ClinicalTrials.gov v2 search by condition + status + age band + sex. |
| `mcp.clinicaltrials_gov.get_record` | `clinicaltrials_get_record` | HTTP — Public API | Full trial record + parsed inclusion / exclusion lines. |

That's the entire surface. Important properties:

- **Every write to `workspace.md` is mediated.** The agent cannot
  bypass `workspace_write` to scribble at the file directly. The
  citation graph and the audit trail are unforgeable.
- **Every transcript event broadcasts.** Tool calls, tool results,
  citations, escalations, save destinations — all go through
  `Workspace.append_transcript`, which writes to disk *and* publishes
  to the per-run `EventHub` (see
  [`STREAMING-AND-GATEWAY.md`](STREAMING-AND-GATEWAY.md)).
- **No filesystem access outside the run dir.** The agent cannot
  create files, read files, or escape its case directory. There is
  no `read_file` / `write_file` / `bash` tool.
- **No outbound network outside the registered MCP-style tools.**
  The agent has no general HTTP client, no browser, no shell.

This is a deliberately small footprint for Phase 1. It's correct for
trial-matching's structured workflow but it's a hard ceiling on what
agents can achieve until we add more.

## 2. What the agent cannot do (yet) — and why

### 2.1 Web search

**Status:** ❌ Not available.

**Why it matters:** Several of the planned skills in
[`docs/ideas/FEATURE-IDEAS.md`](../../ideas/FEATURE-IDEAS.md) need it
explicitly — the Rare Disease Funding Finder web-searches manufacturer
PAPs and foundation grants, the Med Access agent looks up coupon
programs, the Second Opinion Prep packet pulls specialist literature.
Trial-matching itself is fine without web search because
ClinicalTrials.gov is a structured registry; the moment we leave
structured registries, we need search.

**What we'd add:** a `web_search(query, count?)` tool returning a list
of `{title, url, snippet}` results. Implementation options below in §3.

### 2.2 Web fetch / page reader

**Status:** ❌ Not available.

**Why it matters:** Even with search results in hand, the agent
currently has no way to read the linked pages. CT.gov is special-cased
because we built a dedicated parser; a generic "fetch this URL and
return text" tool covers everything else.

**What we'd add:** `web_fetch(url)` returning sanitized text + links.
Critical safety questions: domain allow-list? robots.txt? scrub PHI
*before* the model sees the page? Discussed in §4.

### 2.3 Browser automation

**Status:** ❌ Not available.

**Why it matters:** This is the long-tail unblock for the
[`Tier 2 portal automation`](../../ideas/FEATURE-IDEAS.md#tier-2--patient-authorized-browser-agent-the-hard-one)
strategy in FEATURE-IDEAS.md — every certified EHR has an EHI export
button in the patient portal even when there's no FHIR API. Today, no
agent can click that button. Trial-matching doesn't need this; data
acquisition skills do. Discussed in §5.

### 2.4 File create / edit beyond the workspace

**Status:** ❌ Not available — and probably shouldn't be at the
agent layer.

**Why it matters:** Producing a prior-auth packet PDF, a CSV
shortlist, a structured FHIR bundle — these are real deliverables the
clinician wants. The agent shouldn't be the thing that emits PDFs;
deterministic post-processors should consume the structured artifact
(`output.json`) and produce the export. Keeps the audit trail clean
(the agent's output is data, not an opaque file). Discussed in §6.

### 2.5 Mid-run patient/clinician chat

**Status:** ⚠️ Limited — only escalation gates.

The agent can pause via `workspace_escalate`, the clinician resolves,
the run resumes. There is no continuous chat window where the
clinician can type "actually, also check trials in Boston" mid-run.
That's a real gap for the kind of conversational refinement you
described — already flagged as deferred in
[`SELF-MODIFYING-WORKSPACE.md`](SELF-MODIFYING-WORKSPACE.md) §2 item 5.
Discussed in §7.

### 2.6 Direct chart access tools

**Status:** ⚠️ Indirect only.

The agent sees the chart through the *brief* (assembled by the
runner, included in the system prompt) and through patient memory
(pinned facts + context packages). It cannot freely query the chart
mid-run. The existing `provider_assistant_agent_sdk.py` has
`get_patient_snapshot`, `query_chart_evidence`, and `run_sql` tools we
could lift into this registry — that's a small addition with clear
upside, especially for skills beyond trial-matching.

## 3. Web search — option comparison

The right answer depends on how much we care about (a) PHI exposure,
(b) cost predictability, (c) latency, (d) result quality.

| Provider | Pricing | PHI posture | Latency | Notes |
|---|---|---|---|---|
| **Brave Search API** | $3 / 1k for "Free AI" tier; $5 / 1k for paid | Privacy-respecting; no logging tied to user identifiers | ~200ms | JSON, simple auth header. Good general result quality. **Recommended default.** |
| **Tavily** | $0.005 / search; $0.02 with extraction | Standard SaaS — PHI must be scrubbed before query | ~400ms | AI-first. Returns synthesized answers + sources. Built for agents. Good for prototyping. |
| **Exa** | $0.005 / search | Standard SaaS | ~500ms | Semantic search, embedding-based. Strong for research-style queries; weaker for transactional ones. |
| **Serper.dev** | $0.30 / 1k | Wraps Google SERP — same Google data leak posture | ~300ms | Google-grade results at low cost; the lock-in is reverse-engineering Google's HTML. |
| **Google Custom Search** | $5 / 1k after 100/day free | Google's data policies apply | ~250ms | Reliable but rate-limited and costly at scale. |
| **Anthropic web search tool** | Bundled with Claude API usage | Anthropic's data policies | ~varies | Built into Claude; cheap path but tightly coupled. Worth considering for prototype velocity. |

**Recommendation for our roadmap:**

1. **Phase 1 prototype (now):** add Anthropic's built-in web search
   tool when we wire it into the agent loop — it's the cheapest path
   to "the agent can search" and it shares observability with the
   rest of the agent loop.
2. **Phase 2 production:** introduce a provider abstraction
   (`SearchProvider`) and default to **Brave Search API** for cost
   predictability and the privacy posture. Keep Anthropic as a
   fallback / dev-mode option.
3. **Skip Google for now.** Quotas + cost don't match where we are.

The skill manifest's `required_tools:` would just declare
`web.search`; the runtime maps to whatever provider is configured.

## 4. Web fetch / scraping — non-browser approaches

For 80% of "agent reads a page" cases we don't need a browser — a
text fetcher with link extraction is enough. Option space:

| Tool | What it does | Trade-offs |
|---|---|---|
| `httpx` + `selectolax` (fast HTML parser) + `readability-lxml` (article extraction) | Plain HTTP, parse HTML, extract main content + links | Fast, deterministic. Fails on JS-rendered pages. |
| **Anthropic's web fetch tool** | Bundled with Claude API; fetches + extracts text | Same observability as web search. Same provider-bundling tradeoff. |
| **Firecrawl / Browserless / Bright Data** | Hosted page-rendering APIs; handle JS | $$. Good when JS rendering matters and we don't want to host Playwright. |
| **Playwright (in-process or via a worker)** | Real Chromium, full JS, screenshots, click | Heavy. Right answer for browser automation (§5), overkill for "just read this page". |

**Recommendation:**

- **Default:** the simple httpx + readability path for general-purpose
  page reading. Add a `web_fetch(url)` tool returning
  `{url, title, text, links}`.
- **Allow-list:** by default, only allow well-known clinical /
  reference domains (UpToDate, NIH, manufacturer sites, NORD,
  ClinicalTrials.gov, CMS, payer formularies). The skill manifest
  can extend the list per skill.
- **PHI scrubbing:** every page response goes through a scrub pass
  before the model sees it. Even on trusted domains, the URL itself
  could leak (e.g., a portal page with `?patient_id=X`). The runtime
  redacts known-PHI patterns before logging the response into the
  transcript.

## 5. Browser automation — the patient-portal data acquisition story

This is where your browser-automation expertise matters most. The
`Tier 2` strategy in FEATURE-IDEAS.md hinges on this: every
ONC-certified EHR has an EHI export button in the patient portal,
which means the data is *accessible*, just not via API. A browser
agent can click that button. Today no agent in our stack can.

### 5.1 What the architecture would look like

```
┌──────────────────────────────────────────────────────────────┐
│  FastAPI host                                                 │
│  ┌─────────────┐                                             │
│  │ Skill agent │── tool call: portal.acquire(creds_ref) ──┐  │
│  └─────────────┘                                          │  │
└───────────────────────────────────────────────────────────│──┘
                                                            ▼
        ┌────────────────────────────────────────────────────────┐
        │  Browser worker container (W2 sandbox)                  │
        │  - Playwright + Chromium                                │
        │  - Per-session profile dir (cookies, MFA tokens)        │
        │  - Network egress allow-list: just the portal hostname  │
        │  - Mounts: /workspace (one case dir, read-write)        │
        │  - Returns: downloaded export ZIP, screenshots of steps │
        └────────────────────────────────────────────────────────┘
```

The browser worker is **not** an LLM agent. It's a deterministic
Playwright runner that:

1. Receives a portal-specific automation script (one per portal —
   Epic MyChart, Cerner Patient Portal, Athenahealth, etc.).
2. Loads patient credentials from the patient's own Azure Key Vault
   (never our infra).
3. Executes the script: log in, navigate, click "Download my records",
   wait for ZIP, save to the case dir.
4. Pauses for MFA / SMS codes by surfacing an escalation through the
   workspace contract (same `workspace_escalate` primitive — the
   trust contract is already there).
5. Returns artifact paths + step-by-step screenshots for the audit
   trail.

The *agent* calls this via a `portal.acquire(portal_name, creds_ref)`
tool. The worker runs in W2 (Docker sandbox per run) — see §5.4.

### 5.2 LLM-driven portal navigation (the novel research angle)

The plain Playwright path requires per-portal scripts. Per
FEATURE-IDEAS.md's "novel research angle for the competition," the
better long-term play is **vision-model-driven portal navigation**:

- Worker takes a screenshot.
- Vision model (Claude with vision, or a fine-tuned smaller model)
  identifies "which element is the Download button?".
- Worker clicks that element.
- Loop until export ZIP is in hand.

This is harder but resilient to portal UI changes that break
selector-based scripts. It's the right Phase-2 target. We should
build the deterministic-script path first (clean ROI for the top 3
portals: Epic, Cerner, Athena) and add vision-driven navigation when
we hit the long tail.

### 5.3 Trust contract implications

Portal automation crosses every line our architecture has been
careful about:

- **PHI flowing through automation infra.** The downloaded export
  *is* PHI. The browser worker can never persist anything outside
  the per-run case dir mounted into the sandbox.
- **Patient credentials.** We never see them. They live in the
  patient's own Azure Key Vault, mounted into the sandbox at run
  time, scrubbed on exit.
- **MFA / SMS codes.** Always require human-in-the-loop. The worker
  pauses; the patient enters the code via the escalation gate; the
  worker resumes. This is the *exact* shape of `workspace_escalate`
  — perfect reuse.
- **Adversarial portals.** A malicious portal could try to exfiltrate
  worker state. The sandbox is the answer (W3 microVM if we go
  paranoid).

### 5.4 Why browser automation forces W2 (Docker sandbox)

Today we run the agent loop in-process (W1). That works while every
tool call is a structured HTTP request to a well-known API. Browser
automation breaks this:

- A headless Chromium is a 200MB process that holds a port.
- It needs a writable filesystem for its profile directory.
- It does arbitrary outbound HTTP — by definition, we can't allow-list
  in advance.
- A browser exploit could in principle escape its host process.

Per [`SKILL-AGENT-WORKSPACE.md`](SKILL-AGENT-WORKSPACE.md) §6.7, this
is exactly the W2 trigger: **"Real PHI" + "third-party scripts"**.
Building browser automation effectively *requires* moving to W2 for
the runs that use it. Trial-matching can stay in W1; portal
acquisition must move to W2.

This is the cleanest forcing function for the W2 migration we'll
hit.

## 6. File ops / artifact production

The mediated workspace contract is intentionally narrow: the agent
writes structured sections to `workspace.md`, registers citations,
submits a JSON artifact. **It does not produce PDFs, CSVs, or other
exports directly.** That is correct.

**Why:** the artifact is the source of truth. Exports are derived.
If we let the agent produce a PDF directly, two things break:
1. The PDF could contain claims not in the JSON artifact — the audit
   trail is no longer complete.
2. PDF rendering is deterministic and styling-heavy; LLMs are bad at
   it; you'd burn tokens on layout choices that should be hardcoded.

**Right shape:** post-processors consume `output.json` and emit
exports. The Trial Finder shortlist's `artifacts/candidate-trials.csv`
and `artifacts/outreach-packet.pdf` are produced by Python helpers
the runtime calls *after* `workspace.finalize()` succeeds. Those
helpers can have their own tests; the agent doesn't need to know
they exist.

We should add this in the next runtime commit:

- `api/core/skills/exporters/{trial_csv,trial_pdf}.py` — pure
  functions: `output.json → file in artifacts/`.
- A `post_finalize` hook on the skill that lists which exporters to
  run.
- The frontend "Save / Download" UI surfaces them as download links.

## 7. Patient interaction beyond escalation

What we have:

- **Escalation gates** — the agent pauses, the clinician answers.
  One-shot, structured.

What we don't have, and you flagged:

- **Mid-run conversation** — a chat box alongside the workspace where
  the clinician can type "also include Boston-area sites" and the
  agent reads that on its next turn.

The runtime contract is already most of the way there:

1. Workspace already has `clinician_edits.md` (the "Annotate this
   run" save destination) — that file exists per run.
2. The runner already loops over agent turns; it would just need to
   read pending clinician messages between turns and surface them as
   user messages.

**Concrete addition (~commit 7 or 8):**

- `POST /api/skills/.../runs/{id}/messages` — clinician sends a
  message during a run.
- Worker reads the unresolved messages on each agent turn, prepends
  them as additional `user` content in the next `messages.create`.
- Frontend gains a small chat composer below the workspace.

This is small and high-value for the conversational refinement use
case. Worth doing before more tools.

## 8. Decision matrix — what to add next

Sorted by impact / effort, with my recommendation:

| Capability | Impact | Effort | Recommend |
|---|---|---|---|
| Anthropic built-in web search + web fetch | High — unblocks 4+ planned skills | Low (1 day) | **Yes — next commit** |
| Mid-run clinician messages | High for UX feel | Low (~1 day) | **Yes — soon** |
| Schema-error feedback to agent on bad finalize | Medium — recovery from bad runs | Very low | **Yes — next commit** |
| Token streaming (SSE deltas) | Medium UX | Low | Yes — when we wire agent mode in production |
| Chart-access tools (lift from provider_assistant_agent_sdk) | Medium — opens up 2nd / 3rd skills | Low | Yes when we ship a second skill |
| `web_search` provider abstraction (Brave / Tavily) | High once we leave prototype | Medium | Phase 2 |
| Post-finalize exporters (CSV / PDF) | Medium-high product polish | Medium | Concurrent with first agent-mode prod runs |
| Browser automation (Playwright + W2 sandbox) | Very high for data acquisition | High (weeks) | Phase 2; the moment we onboard a real EHR |
| Vision-model portal navigation | Very high research angle | High (weeks+) | Phase 2.5 |

The next-commit cluster is small and high-leverage: **web search +
web fetch + mid-run messages + schema-error feedback** is roughly
2–3 days of work and unblocks every planned skill that's not
trial-matching. Doing those before browser automation gets the most
velocity.

## 9. Forward path summary

Stages line up with the runtime's worker-phase ladder (W0–W3 in
[`SKILL-AGENT-WORKSPACE.md`](SKILL-AGENT-WORKSPACE.md) §6.7):

| Phase | Tool surface | Worker shell |
|---|---|---|
| **Today (W0/W1)** | workspace + CT.gov | In-process FastAPI |
| **Next (W1)** | + Anthropic web search/fetch + chart-access tools + post-finalize exporters + mid-run messages | In-process FastAPI |
| **Phase 2 entry (W2)** | + browser automation (Playwright) + portal-acquisition skills + Brave/Tavily search abstraction | Per-run Docker sandbox |
| **Phase 2.5 (W2/W3)** | + vision-driven portal navigation | Sandbox + GPU side-process for vision |
| **Multi-LLM (any phase)** | + provider abstraction (`SearchProvider`, `ModelProvider`) — agent code unchanged | Same shell, gateway role formalized |

Every step preserves the trust contract (mediated writes, citation
graph, escalation primitive, audit trail). The thing that grows is
*what the agent can reach*, not *who decides what's true*.

## 10. References

- [`SKILL-AGENT-WORKSPACE.md`](SKILL-AGENT-WORKSPACE.md) — layered architecture; Layer-1 substrate including the tool surface
- [`MODE-SWITCHING.md`](MODE-SWITCHING.md) — current agent loop + tool registry
- [`STREAMING-AND-GATEWAY.md`](STREAMING-AND-GATEWAY.md) — connection layer; relevant when browser automation moves to W2
- [`SELF-MODIFYING-WORKSPACE.md`](SELF-MODIFYING-WORKSPACE.md) — save destinations and patient memory
- [`docs/ideas/FEATURE-IDEAS.md`](../../ideas/FEATURE-IDEAS.md) — full skill catalog driving the tool requirements
