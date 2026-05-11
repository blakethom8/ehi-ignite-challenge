# Browser vs Local App

## 1. The Question

The strongest reference products in this category, including Codex GUI and
Claude Code GUI, are local applications. They benefit from:

- stronger filesystem access
- richer window management
- multi-pane persistence
- native keyboard feel
- better long-running process affordances

The question is whether Atlas should target that form directly or behave that
way while remaining browser-first.

## 2. Recommendation

Build browser-first, but with a desktop posture.

That means:

- docked panes
- strong layout persistence
- keyboard-heavy workflows
- first-class files / preview / settings / artifacts panes
- workspace routes that feel like application states, not websites

This preserves reach and deployment simplicity while keeping a path open for a
future local wrapper.

## 3. Why Browser-First Still Makes Sense

### 3.1 Lower Distribution Friction

The browser version is easier to share, demo, deploy, and iterate.

### 3.2 Current Product Scope

The immediate redesign work is about shell coherence, workspace coupling, and
workflow identity. Those benefits do not require a native app first.

### 3.3 Better Phased Risk

If we build the right shell model now, we can later wrap it in Tauri or
Electron without discarding the interaction contract.

## 4. What Changes Because We Are In The Browser

The web version should be slightly more rigid than the local-app ideal.

### 4.1 Prefer Docked Panes Over Free Windows

In the browser, pane systems stay easier to reason about when they are:

- column-based
- tabbed
- resizable
- collapsible
- persistent

Free-floating windows can arrive later if we wrap the app locally.

### 4.2 Treat Layout As Saved State

Each workspace should remember:

- open panes
- pane widths
- pinned panes
- focus mode
- last artifact / file open

### 4.3 Make Deep Linking Useful

The browser version should support links into:

- a workspace
- a patient context
- a workflow trigger
- a specific artifact or session

That is harder to leverage in a local-first product and is valuable here.

## 5. Capability Comparison

| Capability | Browser-First | Local App |
|---|---|---|
| Shareable URLs | Excellent | Weaker by default |
| Deployment simplicity | Excellent | Medium |
| Native filesystem integration | Limited | Strong |
| Multi-window / multi-monitor | Medium | Strong |
| Browser automation / portal work | Medium | Stronger |
| Offline local state | Medium | Strong |
| Native keyboard / command palette feel | Good | Better |

## 6. What We Should Design For Now

The browser shell should support:

- three-to-five visible docked panes
- a persistent global rail and session rail
- workspace-specific lightweight app panes
- durable inspector / evidence surfaces
- a files surface that feels integral to the agent
- command palette and keyboard shortcuts

## 7. What Can Wait For A Desktop Version

If we later ship a local wrapper, the first things to unlock would be:

- multiple detached workspace windows
- richer local filesystem sync
- background agents and downloads
- native notifications
- deeper local-model or portal-automation integration
- stronger offline bundle handling

## 8. Decision Triggers For Revisiting Desktop-First

We should reconsider a true desktop app if any of these become central:

- heavy filesystem-first workflows
- frequent multi-window comparison work
- browser automation as a core product loop
- background long-running agents that need native process semantics
- customer demand for local-only execution posture

## 9. Conclusion

The right immediate stance is:

- design like a serious application
- implement like a robust browser shell
- preserve a clean migration path to desktop

That gives us the best balance between product quality, speed, and future
optionality.
