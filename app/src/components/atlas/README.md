# `app/src/components/atlas/`

Atlas Agentic Workspaces — the durable shell, panes, and reusable
primitives for the EHI Ignite redesign.

> Spec: [`.claude/handoff/atlas/README.md`](../../../../.claude/handoff/atlas/README.md)
> Tokens: [`.claude/handoff/atlas/tokens/design-tokens.css`](../../../../.claude/handoff/atlas/tokens/design-tokens.css) (mirrored into `app/src/index.css`)
> Design: [`design/agentic-shell-spec/`](../../../../design/agentic-shell-spec/)

## When to use

Import from the barrel:

```ts
import { AppShell, WorkspaceFrame, CitationChip, EvidenceTable } from "@/components/atlas";
// or
import { AppShell, WorkspaceFrame } from "../../components/atlas";
```

Every routed page in the app should be wrapped in `<AppShell>` so the
module bar, titlebar, and platform drawer render consistently. Workspace
routes (`/caspian`, `/workspaces/:packageId`) compose `<AppShell>` with
`<WorkspaceFrame>` for the five-pane layout.

## Inventory

### Shell (always-on chrome)
| Component | Role |
|---|---|
| `AppShell` | 36px ModuleBar + 44px Titlebar + page body. Owns drawer state, derives the active module from the URL. |
| `ModuleBar` | Top dark navy band. Patient Record · FHIR Charts · Caspian · Workspaces ▾ · Learn. Hamburger opens the platform drawer. |
| `PlatformDrawer` | Slide-in left drawer (Settings, Account, Billing, Org, Permissions, Help, Sign out). |
| `Titlebar` | Breadcrumbs + Run workflow + ⌘K + bell + S/C/P/F/I pane toggles. |

### Workspace shell (Caspian + Marketplace)
| Component | Role |
|---|---|
| `WorkspaceFrame` | Composes the five panes. Owns resizers, persists pane sizes to localStorage, switches between active session and package home. |
| `ContextStrip` | 40px strip under the titlebar. Caspian = patient identity. Marketplace = package identity + run state. |
| `SessionsPane` | Workspace switcher, search, package row (marketplace), recent sessions, workflow library, pinned artifacts. |
| `ChatPane` | Header with boundary pill, message list, sticky composer. Citation chips and action chips inline. |
| `WorkbenchPane` | Multi-tab artifact viewer (preop brief, anticoag note, summary JSON, diff, trial board, packet outline, manifest). |
| `FilesPane` | Directory tree with folders, files, pinned object refs. |
| `InspectorPane` | Evidence / Trace / Context tabs. |
| `PackageHome` | Marketplace entry view: hero + permissions ledger + workflow cards + recent runs + about. |

### Reusable primitives
| Component | Role |
|---|---|
| `CitationChip` | Inline `[c_NNNN]` reference. Click → inspector. |
| `DispositionBanner` | HOLD / REVIEW / CLEAR / CRITICAL header for clinical artifacts. |
| `FactRail` | 5-cell horizontal stat rail. |
| `EvidenceTable` | Dense table with citation + risk-band columns. |
| `ApprovalCard` | Caution-toned card for controlled actions in chat. |
| `ToolTrace` | Mono tool-call indicator above an agent message. |
| `PatientHeader` | Standalone patient identity strip (used outside the workspace shell). |

### State + fixtures
| Symbol | Role |
|---|---|
| `useWorkspaceState(workspaceId)` | The workspace's reducer-style hook. Pane visibility, pane sizes, chat messages, workbench tabs, citation selection, file→tab routing. Persists pane state to localStorage. |
| `WORKSPACES`, `PATIENT`, `SESSIONS`, `WORKFLOWS`, `FILE_TREES`, `CITATIONS`, `INITIAL_CHAT`, `INITIAL_TABS` | Demo seed data mirroring the prototype's `data.js`. Replace with real backend wiring as the workspace API lands. |

## Conventions

- **Tokens, not hex.** All colors come from CSS variables declared in
  `app/src/index.css`. The Tailwind v4 `@theme` block exposes them as
  utilities (`bg-action`, `text-ink-1`, `border-line-1`, etc.) — but inline
  `style={{ background: "var(--action)" }}` is also fine for surface
  contrast that needs to read clinical, not toy.
- **Sentence case** in copy. UI labels are sentence case; clinical status
  flags (`HOLD`, `REVIEW`, `CLEAR`, `CRITICAL`) and product nouns (Caspian,
  Trial Finder) stay capitalized as proper nouns.
- **Lucide icons at 14px in nav, 16px in dense UI.** Stroke weight 1.5.
  No emoji.
- **No 12 / 16 / 24px radii.** Radii are `4 / 6 / 10 / 999` only.
- **No colored glows, no scale-on-hover, no spring.** All transitions
  are 120ms ease-out. The shadow ramp is intentionally tiny.

## Phase status

- [x] Phase 1 — Design tokens (drop-in `:root` + Tailwind `@theme`)
- [x] Phase 2 — Three-band shell + IA refactor (ModuleBar, Titlebar, PlatformDrawer, AppShell)
- [x] Phase 3 — Five-pane workspace shell (Caspian + Marketplace package)
- [x] Phase 4 — Shared primitives lifted, legacy `Layout.tsx` deleted

Migration of legacy pages (`/explorer/*`, `/preop/*`, `/clinical-insights/*`,
`/marketplace`) into proper Caspian workflows + marketplace packages is
ongoing — see `design/agentic-shell-spec/05-rollout-phases.md`.
