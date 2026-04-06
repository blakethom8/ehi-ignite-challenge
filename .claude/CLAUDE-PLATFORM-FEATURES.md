# Claude Platform Features — Workflow Reference

> How the broader Claude Code ecosystem (Remote Control, Dispatch, cloud compute, scheduling) 
> fits into our autonomous build pipeline and collaborative coding workflow.
> Written April 2026 based on current Claude Code documentation.

---

## Quick Map: What We Used vs. What Else Exists

```
What we built ──────────────────────────────────────────────────────────────
  /loop + CronCreate    → recurring research + build orchestrators
  Agent tool            → parallel build agents with file-ownership rules
  Remote Control        → you steering sessions from your phone

What else is available ──────────────────────────────────────────────────────
  Dispatch              → phone-initiated tasks routed to Desktop
  Desktop scheduled tasks → durable local crons (survive restarts)
  Cloud scheduled tasks → 24/7 cloud VMs (survive machine shutdown)
  Cloud sessions        → async one-shot tasks on Anthropic infrastructure
  Computer use          → Claude controls your screen/GUI
  Channels              → Claude reacts to Slack/Telegram/webhooks
  Worktrees             → isolated git checkouts per agent session
  MCP servers           → custom tool integrations
```

---

## 1. Remote Control

**What you did:** Controlled a Claude Code session from your phone during the build sprint.

**How it works:**
- Your local Claude Code session registers with Anthropic and polls via outbound HTTPS — no ports open on your machine
- Messages relay through an encrypted streaming connection
- Your full local environment (MCP servers, project config, all files) stays active
- Session survives network interruptions and auto-reconnects

**Setup:**
```bash
claude remote-control          # server mode — supports multiple connections
claude --remote-control "EHI"  # flag on a new session
# or type /remote-control inside an active session
```

**Requirements:**
- Pro, Max, Team, or Enterprise plan (not raw API keys)
- Full-scope login via `/login` (not `ANTHROPIC_API_KEY` env var)
- Claude Code v2.1.51+

**What you can do from your phone:**
- Send messages and steer work in real time
- Approve/deny tool use
- Work from multiple surfaces simultaneously (terminal + phone + web)

**Limitation:** Terminal must stay open. Machine must stay on. If you want 24/7 autonomous operation, pair with cloud sessions (see §4).

---

## 2. Dispatch

**What it is:** Send a task from your phone; Claude Desktop decides how to handle it — research in Cowork or spin up a Code session automatically.

**How it works:**
```
You (phone) → message → Dispatch (Desktop Cowork tab)
                           ↓
              Is this coding work?
              YES → spawn Code session in Desktop app
              NO  → handle in Cowork (research, docs, etc.)
                           ↓
              Push notification to phone when done
```

**Setup:** Pair the Claude mobile app with Claude Desktop. See Anthropic support docs.

**Dispatch vs. Remote Control:**

| | Dispatch | Remote Control |
|---|---|---|
| **Initiated from** | Phone | Phone/browser |
| **Runs on** | Your Desktop machine | Your local terminal |
| **Session started by** | Dispatch (automatic) | You (already running) |
| **Good for** | "Do this task while I'm away" | "I want to steer this live session" |

**Key constraint:** Dispatch is **Pro/Max only** — not available on Team or Enterprise plans.

**Computer use in Dispatch:** If computer use is enabled, Dispatch-spawned sessions can control your screen. App approvals expire after 30 minutes (vs. full session lifetime in manual sessions).

---

## 3. Scheduling: Three Tiers

We used `/loop` + `CronCreate` for the sprint. Here's the full landscape:

### Tier 1 — CLI `/loop` (what we used)
```
CronCreate / CronList / CronDelete
```
- **Lives in:** Current CLI session memory only
- **Survives restarts:** No — deleted when session ends
- **Min interval:** Any (we used 23 and 37 minutes)
- **Local access:** Full — all files, tools, MCP servers
- **Good for:** Active sprint sessions; fastest iteration

**Timing note:** Fires up to 10% late (max 15 min jitter). Only fires when Claude is idle.

### Tier 2 — Desktop Scheduled Tasks
- **Lives in:** Claude Desktop app (persists across restarts)
- **Survives restarts:** Yes — Desktop reruns on startup
- **Min interval:** 1 minute
- **Local access:** Full — your working directory, MCP servers, tools
- **Missed runs:** Runs one catch-up when Desktop wakes (not all missed)
- **Good for:** Daily or hourly recurring builds that need local files

**This is the upgrade path from `/loop`** — same prompts, same tools, but durable.

### Tier 3 — Cloud Scheduled Tasks (claude.ai/code)
- **Lives in:** Anthropic cloud infrastructure
- **Survives restarts:** Yes — machine can be fully off
- **Min interval:** 1 hour
- **Local access:** None — fresh GitHub clone each run
- **Good for:** Overnight dependency audits, daily PR reviews, CI-style checks

**Cloud environment includes:** Python, Node, Go, Rust, PostgreSQL, Docker, etc. pre-installed.

### Choosing a Tier

| Need | Use |
|---|---|
| Active sprint (machine on, building fast) | CLI `/loop` |
| Recurring local builds (survive restarts) | Desktop tasks |
| 24/7 autonomous (machine can be off) | Cloud tasks |
| One-shot long async task | Cloud session (`claude --remote "..."`) |

---

## 4. Cloud Sessions (Giving Claude a Computer)

**What it is:** Run a Claude Code task on an Anthropic-managed VM — no local machine required.

```bash
claude --remote "Fix the auth bug and open a PR"
# or start from claude.ai/code in browser
# or from Claude mobile app
```

**What happens:**
1. Anthropic spins up a fresh VM
2. Clones your GitHub repo
3. Runs your task asynchronously
4. You can monitor from Desktop, web, or phone
5. Task completes and pushes results — machine can be off the whole time

**VM comes with pre-installed:** Python, Node, Ruby, Go, Rust, Java, PostgreSQL, Redis, Docker, kubectl, Terraform, and more.

**Network:** Limited by default (allowlist of 60+ domains: GitHub, npm, PyPI, cloud APIs, etc.). Can configure full access.

**Limitations:**
- Requires GitHub (no GitLab, self-hosted)
- Fresh clone each run (not your local working directory)
- Only available on claude.ai/code (not VS Code extension)
- Minimum interval 1 hour for scheduled runs

**For our pipeline:** Cloud sessions would let the build loop run overnight without your laptop staying on. Trade-off: 1-hour minimum interval is much slower than our 23/37 minute crons, and it can't access uncommitted local state.

---

## 5. Computer Use

**What it is:** Claude can see your screen and control it — click, type, drag, interact with native apps.

**Available on:**
- Claude Code Desktop (macOS and Windows) — full support
- Claude Code CLI on macOS — via `computer-use` MCP server

**How it works:**
- Claude takes screenshots at intervals
- You grant per-app permissions (explicit prompts)
- All processing stays local — no screenshots uploaded to Anthropic

**Useful for:** Testing UIs, clicking through multi-step workflows, form automation, app testing in the browser.

**For our pipeline:** Not needed for code builds, but useful if you ever need to automate testing against the running React app or interact with external web tools.

---

## 6. Channels (Reacting to External Events)

**What it is:** Instead of polling on a timer, Claude listens for incoming events and reacts.

**Supported inputs:** Slack, Telegram, Discord, iMessage, webhooks.

**Use case for our pipeline:**
```
GitHub Action fails CI → webhook → Claude reacts → investigates + files issue
```

**vs. our cron approach:**
- Crons = polling (fires at interval regardless of whether there's work)
- Channels = push-based (fires only when an event arrives)

For a real production pipeline, Channels + cloud sessions would be more efficient than crons.

---

## 7. Worktrees (Agent Isolation)

**What it is:** Each agent session gets its own git worktree — an isolated copy of the repo.

**Why it matters for parallel builds:**
- Two agents can edit the same file path in their own worktrees without conflict
- Changes only merge back to main when explicitly pushed/merged
- No `.lock` file collisions or partial-write race conditions

**How we worked around this manually:** We gave each agent explicit "files you may/must not touch" lists. Worktrees would be a cleaner alternative — each agent gets isolated and can't conflict by definition.

**Enable per agent:**
```python
Agent(prompt="...", isolation="worktree")  # in Agent SDK
```
or use the `EnterWorktree` / `ExitWorktree` tools inside a session.

---

## 8. Applying This to Our Pipeline: Upgrade Path

Our current pipeline runs in a CLI session with cron jobs. Here's how to evolve it:

### Today (what we built)
```
CLI session → /loop crons (23 min research, 37 min build)
  → session-only, dies when terminal closes
  → manual commit + push
```

### Next step: Desktop tasks
```
Claude Desktop → Scheduled tasks (every 30 min)
  → survives restarts, runs while Desktop is open
  → machine must stay on
  → same prompts, same tools, same queue file
```

### Production: Cloud tasks + GitHub Actions webhook
```
Cloud scheduled tasks (every hour)
  → machine can be fully off
  → GitHub pushes managed by agents
  → Channels listen for CI failures and react
```

### What doesn't change regardless of tier
- `.claude/feature-queue.md` — still the coordination state file
- The orchestrator prompts — work identically on all tiers
- The build agent briefs — file ownership rules still apply
- The commit/push step — agents handle this directly

---

## 9. Key Limitations to Plan Around

| Limitation | Impact on pipeline |
|---|---|
| CLI crons are session-only | Need to re-create after each restart |
| Cloud tasks min 1-hour interval | Too slow for rapid iteration sprints |
| Cloud tasks need GitHub (no local files) | Can't use uncommitted local state |
| Dispatch is Pro/Max only | Not available on Team plans |
| Computer use approvals expire in 30 min (Dispatch) | Not suited for long-running GUI automation |
| Worktree isolation not automatic in CLI | Must manage file conflicts manually |
| No native webhook endpoint to trigger sessions | Use Channels or poll-based crons |

---

*Last updated: April 2026. Claude Code features evolve rapidly — verify against `claude.ai/code` docs for latest.*
