# Research Notes: Agent GUI Patterns

This is a lightweight product/architecture scan for the net-new workspace. It is not a vendor commitment.

## What Codex-like Tools Are Teaching Us

OpenAI's Codex docs now frame the product around multiple clients and concepts that matter directly for us: sandboxing, subagents, workflows, rules, hooks, MCP, skills, AGENTS.md, review, in-app browser, local environments, and integrations. The important takeaway is not that we need to copy a coding UI literally. The takeaway is that serious agent products separate the runtime contract from the UI shell and expose the agent's environment as a first-class object.

For our clinical workspace, that means the user must be able to see:

- what patient/context package the agent received
- what skill file or workspace contract is active
- what tools are available
- what source systems are allowed
- what tool calls happened
- what artifacts were created
- what needs human approval

## What Claude Code-like Tools Are Teaching Us

Anthropic's Claude Code direction emphasizes checkpoints, subagents, hooks, and background tasks for longer autonomous work. The clinical analog is clear:

- checkpoint before high-impact state changes
- subagents for bounded tasks such as trial search, criteria review, packet preparation, portal outreach, and follow-up monitoring
- hooks for validation, citation checks, PHI redaction checks, or task creation
- background runs that continue while the user inspects canvas state

This supports a loop where the agent is not just answering chat messages. It is operating a transparent clinical workflow.

## Open Source / Wrapper Patterns

The current ecosystem around OpenCode, OpenChamber, OpenBox, CliDeck, and related tools points toward several recurring GUI patterns:

- session resume
- project/workspace grouping
- role-tagged agents
- multi-pane workspaces
- visible file/artifact preview
- live chat beside structured output
- isolated execution environments
- routing between agents
- branchable or restorable state
- mobile/remote status review

For us, the most relevant pattern is not the code diff. It is the idea of a durable run/session with visible event history and a structured side application that the agent continuously updates.

## Design Implications For EHI

The clinical workspace should have four durable planes:

1. **Conversation plane** - the agent explains, asks, and receives steering.
2. **Canvas plane** - the current structured object view: trial candidates, detail view, tasks, packets, source pages.
3. **Inspector plane** - transparent view of skills, context, tools, permissions, source configuration, tool calls, artifacts, and logs.
4. **Management plane** - persistent project state: selected trials, statuses, tasks, notes, outreach, deadlines, follow-up events.

The user should be able to collapse, expand, resize, and fullscreen these planes without losing run state.

## Sources Checked

- OpenAI Codex documentation: https://developers.openai.com/codex/cloud
- Anthropic Claude Code autonomy update: https://www.anthropic.com/news/enabling-claude-code-to-work-more-autonomously
- OpenCode: https://www.opencode.live/
- OpenChamber: https://github.com/openchamber/openchamber
- OpenBox: https://openbox.sh/
- CliDeck: https://clideck.dev/
