# Automated Build Pipeline — Management Reference

Quick reference for starting, stopping, and understanding the autonomous build loop.

---

## Where Everything Lives

```
ehi-ignite-challenge/
└── .claude/                          ← Pipeline control plane (all here)
    ├── PIPELINE-MANAGEMENT.md        ← This file
    ├── AUTONOMOUS-BUILD-LOOP.md      ← Full process reference + prompt templates
    ├── feature-queue.md              ← Live queue state (queued / in-progress / done)
    ├── build-log.md                  ← Timestamped log of every completed build
    └── scheduled_tasks.lock          ← Created by Claude Code when crons are active
```

The cron jobs themselves are **session-only** — they live in Claude Code's in-memory session store, not in any file on disk. The `.lock` file is a side effect of scheduling; deleting it does not stop the crons.

---

## Starting the Pipeline

Paste both prompts into a Claude Code session (one message is fine). The orchestrator will:
1. Check the queue
2. Spawn research if queue < 6 items
3. Pick and build the next item
4. Update the queue and log

The full prompt templates are in `.claude/AUTONOMOUS-BUILD-LOOP.md`.

**Quick start — paste this into Claude Code:**

```
[Research orchestrator prompt from AUTONOMOUS-BUILD-LOOP.md]
[Build orchestrator prompt from AUTONOMOUS-BUILD-LOOP.md]
```

To schedule them to repeat automatically, add this after the prompts:

```
Please also create two cron jobs:
1. Every 23 minutes: run the research orchestrator
2. Every 37 minutes: run the build orchestrator
```

---

## Stopping the Pipeline

### Check what's running

In a Claude Code session, the cron IDs are returned when created and also visible via `CronList`. Ask Claude:

```
Please run CronList to show me all active cron jobs, then delete them with CronDelete.
```

Or tell Claude the IDs directly if you have them:

```
Please delete cron jobs [ID1] and [ID2] using CronDelete.
```

### Important: crons are session-scoped

- Crons **stop automatically** when the Claude Code session ends (window close, `/clear`, or timeout)
- A new session has **no crons** — you must re-create them
- The `.claude/scheduled_tasks.lock` file persists between sessions but is just a marker — it does not restart the crons

### To pause without stopping

Simply let the session sit — the crons will fire but if you don't want builds to proceed, you can move items out of the Queued section of `feature-queue.md` to a "Paused" section temporarily.

---

## Reading the Queue

```
.claude/feature-queue.md
```

| Section | Meaning |
|---|---|
| `🔨 In Progress` | Currently being built by an agent |
| `📋 Queued` | Ready to build, priority order |
| `✅ Completed` | Done — don't re-queue |
| `🔬 Research Log` | Timestamped research pass history |

**To add an item manually:** Insert it in the correct complexity tier in the Queued section. The build orchestrator will pick it up on the next cycle.

**To remove an item:** Delete the line or move it to a `### Paused` subsection.

**To re-prioritize:** Reorder the numbered lines — the orchestrator picks the first Queued item.

---

## Reading the Build Log

```
.claude/build-log.md
```

Append-only log. Each entry records:
- Date and build number
- Feature description
- Files changed
- Smoke test output
- TSC result

Useful for understanding what changed and why, without reading git diffs.

---

## Servers (separate from the pipeline)

The pipeline does not manage the dev servers — those must be started manually:

```bash
# Backend (FastAPI)
uv run uvicorn api.main:app --port 8001 &> /tmp/uvicorn-ehi.log &

# Frontend (Vite)
cd app && npm run dev &> /tmp/vite-ehi.log &
```

Build agents restart the backend automatically when they make backend changes. The frontend hot-reloads automatically via Vite.

To check server health:
```bash
curl -s http://localhost:8001/api/patients | python3 -c "import sys,json; print(len(json.load(sys.stdin)), 'patients')"
```

---

## Common Operations

| Task | How |
|---|---|
| Start the loop | Paste both orchestrator prompts into Claude Code |
| Schedule auto-repeat | Ask Claude to run `CronCreate` for each prompt |
| Stop crons | Ask Claude to run `CronList` then `CronDelete` |
| Check crons | Ask Claude: "Run CronList to show active cron jobs" |
| Add a feature | Add it to `feature-queue.md` Queued section |
| Skip a feature | Remove it from the queue or move to a Paused section |
| Force a build now | Paste the build orchestrator prompt directly |
| Force research now | Paste the research orchestrator prompt directly |
| See what was built | Read `.claude/build-log.md` |
| Commit everything | Run `git add -A && git commit` manually |
