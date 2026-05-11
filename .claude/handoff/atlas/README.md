# Handoff: Atlas Agentic Workspaces — EHI Ignite

A developer handoff package for refactoring the EHI Ignite application
(`blakethom8/ehi-ignite-challenge`) to match the **Atlas Agentic
Workspaces** prototype. This bundle contains the working HTML prototype,
design tokens, IA decisions, component contracts, and a phased
migration plan.

---

## Overview

The redesign introduces a unified, agentic workspace shell that hosts
two distinct trust postures inside one consistent UI:

1. **Caspian** — first-party clinical insights workspace bound to a
   private patient record. Pre-Op, Medication Safety, and Longitudinal
   review now live here as workflow types.
2. **Workspaces (Marketplace)** — vendor-published packages (Trial
   Finder, Medication Access, Site Coordination, etc.) that operate on
   consented patient anchors from Caspian and may write to the outside
   world (registries, packets, outreach).

A new EHI Ignite top module bar grounds the user across the whole
product (Patient Record · FHIR Charts · Caspian · Workspaces · Learn),
and a collapsible **platform drawer** replaces the previous left icon
rail for account / settings / billing.

This is not a marketing rebrand. The visual direction moves
intentionally **away from the beige / cream surface tone** common in
current LLM tooling, onto a cool paper-white (`#eef2f6` / `#f4f7fb`)
with a clinical blue accent — the EHI Ignite Clinical Intelligence
design language.

---

## About the design files

The files in `prototype/` are **design references created in HTML +
inline-Babel React** to convey the intended look, structure, and
interaction model. They are **not production code to copy directly**.

The implementation task is to **recreate these designs inside the
existing EHI Ignite codebase** (React 19 + TypeScript + Tailwind v4 +
lucide-react + Plotly) using its established component patterns,
routing, and theme layer. Inline-Babel scripts, the global-scope
`Object.assign(window, …)` pattern, and the runtime-defined CSS
variables in the prototype all need to be translated into proper TSX
modules and Tailwind theme tokens.

When the prototype and the existing repo disagree, **the prototype
wins on visual + IA decisions** and **the repo wins on framework
conventions, file layout, state management, and routing**.

---

## Fidelity

**High-fidelity (hifi).** The prototype is pixel-accurate for
colors, typography, spacing, line weights, hover and focus states,
animation timing, and the resizer behavior. Recreate it pixel-for-pixel
in the target framework. Where a Tailwind utility class is the natural
expression of a token, use the utility — but the token value itself
should match `prototype/styles.css` exactly.

The only exceptions to pixel-perfect:
- Plotly chart canvases (they inherit colors from CSS variables)
- Lucide icon stroke weight is `1.5` everywhere (default lucide)
- Page-specific copy is final; clinical numerics in tables are
  representative and may be replaced with real backing data

---

## Migration phases

Do this in four PRs in order. Each phase is independently mergeable
and reviewable in 30 minutes.

### Phase 1 — Design tokens (smallest blast radius)

Replace the existing token layer in `app/src/index.css` and the
Tailwind v4 `@theme` block with the values in
`tokens/design-tokens.css`. Do not touch components yet. The visual
diff will be large but the component diff will be near zero — this
isolates the visual rebrand from the IA refactor.

Acceptance: app builds, every screen renders without component
changes, the beige tone is gone, the dark titlebar appears wherever a
header is rendered.

### Phase 2 — Shell & IA (biggest structural change)

Replace the existing `Layout.tsx` chrome with the new three-band
shell:

1. **Module bar** (`36px`, dark navy `#0c1320`) — top, full width
2. **Titlebar** (`44px`, dark) — second band, with breadcrumbs and
   pane-toggle cluster
3. **Body** — sessions pane (`248px` default, resizable) + stage

Top-nav items: **Patient Record · FHIR Charts · Caspian ·
Workspaces · Learn**.

Removed from top nav: Data Aggregator (folds into Patient Record as
the same pipeline rebranded — PDF parsing, harmonization, data review
become Patient Record sub-routes), Pre-Op (folds into Caspian as a
workflow type), Trials & Medication Access (now Workspaces packages,
accessed via the Workspaces dropdown).

Workspaces is a **dropdown**: an "Explore workspaces" primary entry
(routes to the marketplace home) plus a "Recently viewed" list.

The previous 56-px left icon rail is **removed** entirely. A
hamburger button at the top-left of the module bar opens a
**platform drawer** (account, settings, billing, organization,
permissions & audit, help, sign out).

Acceptance: navigating between modules works, all old routes
redirect cleanly, no orphaned icons remain on the left edge.

### Phase 3 — Atlas workspace shell (Caspian + Marketplace)

New code, not a refactor. Build the five-pane workspace shell:

`sessions | chat | workbench | files | inspector`

— with independent show/hide toggles (S · C · P · F · I), drag
resizers on every gutter, the citation-chip → inspector flow, the
package-home pattern for Marketplace packages, and the active-session
view for any workspace.

Caspian sessions land directly in the active-session view.
Marketplace workspaces (Trial Finder, etc.) land on the **package
home** first; the user starts a workflow which then opens the active
session view.

Acceptance: open `Caspian → Hollister → Pre-op clearance`, click
`c_1042` in chat, see evidence card in Inspector. Switch to Trial
Finder via the Workspaces dropdown, see the package home with
permissions ledger, workflows, recent runs.

### Phase 4 — Shared component lift

Extract these into shared components under
`app/src/components/atlas/`:

- `AppShell`, `ModuleBar`, `PlatformDrawer`, `Titlebar`
- `SessionsPane`, `WorkbenchTabs`, `FilesTree`, `InspectorPane`
- `Composer`, `MessageBubble`, `CitationChip`, `ApprovalCard`,
  `ToolTrace`
- `FactRail`, `DispositionBanner`, `EvidenceTable`, `SourceRow`,
  `StatusBanner`, `AgentPanel`, `PatientHeader` (these may already
  exist — replace with the new versions, keep prop signatures
  compatible where possible)
- `PackageHome` + sub-components (`PermissionsLedger`,
  `WorkflowCard`, `RunsTable`)

---

## Information architecture

### Top-level navigation (module bar)

```
EHI Ignite logo · Patient Record · FHIR Charts · Caspian · Workspaces ▾ · Learn
```

| Module          | Role                                                                                          |
| --------------- | --------------------------------------------------------------------------------------------- |
| Patient Record  | Source-of-truth chart layer. Now includes the former Data Aggregator pipeline (PDF parsing, harmonization, review) as sub-routes. |
| FHIR Charts     | FHIR resource browser, unchanged scope.                                                       |
| Caspian         | First-party agentic workspace bound to the private patient. Hosts Pre-Op, Med Safety, Longitudinal as workflows. |
| Workspaces      | Marketplace gateway. Dropdown reveals "Explore workspaces" + recently viewed packages.        |
| Learn           | **Internal section** — runbooks, internal tooling, changelogs, prompt evals, vendor reviews. Reads as docs/training externally; operates as the internal ops console. |

The hamburger to the left of the EHI Ignite logo opens the
**platform drawer** (formerly the left icon rail). It contains
account, settings, billing, organization, permissions & audit, help,
what's new, send feedback, and sign out.

### Workspace switcher (inside the Atlas shell)

Sessions pane header carries a workspace switcher with two top-level
entries — **Caspian** and **Trial Finder** — and the same recently
viewed entries the top-nav Workspaces dropdown shows. Switching
workspaces preserves the panes layout but resets the active session
to the package home (for marketplace workspaces) or the most recent
session (for Caspian).

### Caspian vs. Marketplace boundaries

This is the most important UI affordance. Two workspaces, one shell,
two trust postures — and the UI must make the difference legible
without reading copy.

| Property              | Caspian                                              | Marketplace package (Trial Finder)                 |
| --------------------- | ---------------------------------------------------- | -------------------------------------------------- |
| Context strip color   | Neutral white, green "Private patient boundary" pill | White, amber permission chips, RUN state pill      |
| Context strip subject | Patient identity (name, MRN, age/sex, complexity)    | Package identity (`Trial Finder @2.4.1`, vendor)   |
| Entry view            | Most recent session                                  | Package home (permissions, workflows, recent runs) |
| Allowed actions       | Read patient record, query agent, draft notes        | Read consented anchors, call external registries, send packets (gated approval) |
| Boundary pill         | `🔒 Private patient boundary` (green)                | `Consented external boundary` (amber)              |

---

## Voice and copy

(Carried forward from the EHI Ignite Clinical Intelligence design
system — do not change in this refactor.)

- **Sentence case** for all UI labels. Exception: proper nouns
  (Caspian, Trial Finder, Pre-Op Support) and the four clinical
  status flags (`HOLD`, `REVIEW`, `CLEAR`, `CRITICAL`) which stay
  uppercase.
- **One verb per action button** — `Open`, `Hold`, `Cite`, `Send to
  anesthesia`, `Run workflow`. Never `Get started` / `Learn more` /
  `Discover`.
- **Third-person clinical** on patient surfaces. "The patient is …",
  not "You should …".
- **No emoji**, no exclamation marks. Lucide icons only.
- **ISO dates** in dense tables (`2024-11-02`); long form
  (`Nov 2, 2024`) only in narrative copy. Always include units on
  lab values.
- **Cite first, conclude second** in agent replies. Every clinical
  claim carries a `c_NNNN` citation chip that resolves to a FHIR
  resource in the Inspector.

---

## Design tokens

Full token file is at `tokens/design-tokens.css`. The summary table
below is the contract — the dev should diff their current values
against these.

### Surfaces (light)

| Token                | Value     | Use                                          |
| -------------------- | --------- | -------------------------------------------- |
| `--bg-app`           | `#eef2f6` | App background — cool paper, never beige     |
| `--bg-chrome`        | `#f4f7fb` | Subtle chrome variant                        |
| `--surface-0`        | `#ffffff` | Primary cards, panels, tables                |
| `--surface-1`        | `#fafbfc` | Sub-panels                                   |
| `--surface-2`        | `#f1f4f8` | Zebra stripe, muted toolbars                 |
| `--surface-3`        | `#e8edf3` | Hover row tint, divider blocks               |

### Surfaces (dark)

| Token                | Value     |
| -------------------- | --------- |
| `--bg-app`           | `#0c1014` |
| `--bg-chrome`        | `#11161c` |
| `--surface-0`        | `#161b22` |
| `--surface-1`        | `#1a2029` |

### Module bar + titlebar

Both the module bar (36px) and titlebar (44px) sit on a custom dark
navy regardless of theme:

| Token                       | Value     |
| --------------------------- | --------- |
| Module bar background       | `#0c1320` |
| Titlebar background         | `#0f172a` |
| Module bar text default     | `rgba(229, 233, 240, 0.62)` |
| Module bar text active      | `#ffffff` (on `rgba(255,255,255,0.08)` bg) |
| Active tab underline        | `var(--action)` 2px |

### Ink (text)

| Token       | Light     | Dark      |
| ----------- | --------- | --------- |
| `--ink-1`   | `#0b1220` | `#e8edf3` |
| `--ink-2`   | `#2b3648` | `#c2cad6` |
| `--ink-3`   | `#5b6677` | `#8e98a7` |
| `--ink-4`   | `#8b95a6` | `#6a7383` |
| `--ink-5`   | `#b6bfcc` | `#4a5260` |

### Lines

| Token       | Light     | Dark      |
| ----------- | --------- | --------- |
| `--line-1`  | `#dde3ea` | `#262d37` |
| `--line-2`  | `#cdd5df` | `#2f3845` |
| `--line-3`  | `#aab3c0` | `#3a4554` |

### Action (clinical blue)

| Token              | Light             | Dark                         |
| ------------------ | ----------------- | ---------------------------- |
| `--action`         | `#1d4ed8`         | `#5b8af0`                    |
| `--action-hover`   | `#1e40af`         | `#7da4f5`                    |
| `--action-press`   | `#1e3a8a`         | `#4a78dc`                    |
| `--action-tint`    | `#e8eefe`         | `rgba(91,138,240,0.14)`      |
| `--action-tint-2`  | `#dbe5fd`         | `rgba(91,138,240,0.22)`      |
| `--action-line`    | `#b9c9f7`         | `rgba(91,138,240,0.35)`      |

### Semantic

| Token              | Light     | Tint      | Line      |
| ------------------ | --------- | --------- | --------- |
| `--critical`       | `#b91c1c` | `#fdecec` | `#f4b4b4` |
| `--caution`        | `#a85a07` | `#fdf5e6` | `#f0d39a` |
| `--clear`          | `#047857` | `#e7f6ef` | `#a0d9bc` |
| `--info`           | `#0e7490` | `#e6f5f7` | —         |

### Module identity (used only in eyebrow tags + sidebar accents)

| Module         | Color     |
| -------------- | --------- |
| Patient Record | `#475569` |
| Pre-Op         | `#1d4ed8` |
| Trials         | `#4338ca` |
| Med Access     | `#0f766e` |

### Type

| Token         | Value                                                                                 |
| ------------- | ------------------------------------------------------------------------------------- |
| `--font-sans` | `"Inter Tight", -apple-system, "Segoe UI", sans-serif`                                |
| `--font-serif`| `"Source Serif 4", "Iowan Old Style", Georgia, serif`                                 |
| `--font-mono` | `"IBM Plex Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace`                |

Hierarchy (use sentence case, never title case):

| Role     | Size / line / weight              |
| -------- | --------------------------------- |
| h1       | 24 / 32 / 600                     |
| h2       | 18 / 26 / 600                     |
| h3       | 14 / 20 / 600                     |
| body     | 13 / 20 / 400                     |
| small    | 12 / 18 / 400                     |
| eyebrow  | 10.5 / 16 / 600 / uppercase / +1.4% tracking |
| mono     | 12.5 / 18 / 400 (IBM Plex Mono)   |

### Spacing (4px base, intentionally tight)

`--s1 4 · --s2 8 · --s3 12 · --s4 16 · --s5 20 · --s6 24 · --s8 32`

Card padding: 16–20px. Table cell padding: 8 / 12px. The 32–40px
paddings common in marketing UI are forbidden inside the app.

### Radii

`--r-1 4 · --r-2 6 (default) · --r-3 10 · --r-pill 999` (chips only).
**No 12 / 16 / 24px radii anywhere.**

### Shadows

| Token         | Value                                |
| ------------- | ------------------------------------ |
| `--shadow-1`  | `0 1px 2px rgba(15, 23, 42, 0.04)`   |
| `--shadow-2`  | `0 4px 14px rgba(15, 23, 42, 0.06)`  |
| `--shadow-3`  | `0 18px 40px rgba(15, 23, 42, 0.10)` |

Surfaces are **border-first** — 1px `--line-1` defines almost every
card. Shadow ramp is intentionally tiny. No colored glows. No rings.

### Motion

All transitions: 120ms ease-out. Modal/drawer enters at 160ms. No
spring, no bounce, no scale-on-hover, no translate-on-hover.

---

## Screens

### 1. Module bar (always visible)

- **Layout**: 36px tall, full-width, dark navy `#0c1320`, sticky top.
- **Left**: hamburger (28×28, opens platform drawer) → EHI Ignite
  logo+wordmark (22px logo, 12.5px wordmark in `#fff`) → vertical
  divider → five module tabs.
- **Tabs**: 8×12px padding, 12px font, `rgba(229,233,240,0.62)`
  default, white-on-`rgba(255,255,255,0.08)` active, 2px blue
  underline on active. The Workspaces tab carries a `ChevronDown` 10px
  caret.
- **Right**: search icon, help icon, user avatar (26px circle, blue
  bg, initials in 10.5px / 600).

### 2. Platform drawer

- **Trigger**: hamburger in module bar.
- **Layout**: fixed left, 296px wide, full-height, slides in 160ms
  ease-out from `translateX(-12px)`. Dim scrim `rgba(15,23,42,0.32)`
  over the rest of the page.
- **Sections**:
  1. Header: brand + close (X)
  2. User card: 36px avatar + name + org
  3. Primary section: Settings, Account, Billing & usage,
     Organization, Permissions & audit
  4. Divider
  5. Secondary section: Help & support, What's new, Send feedback
  6. Footer: Sign out (muted)
- **Item style**: 8×10px padding, 12.5px, lucide icon at 14px, hover
  background `--surface-2`.

### 3. Titlebar (44px, dark)

- **Left**: macOS traffic-light cluster (decorative), Atlas mark,
  breadcrumbs `Atlas / {workspace} / {session}` with ellipsis-on-overflow.
- **Right**: Run workflow button (primary), command-K hint, bell,
  pane-toggle cluster **S C P F I** (sessions, chat, workbench, files,
  inspector — Alt+letter shortcuts).
- **Background**: `#0f172a`. Text `rgba(255,255,255,0.85)`. Subtle
  border-bottom `rgba(255,255,255,0.06)`.

### 4. Context strip (48px, light, sticky)

Sits directly under the titlebar. Renders different content per
workspace mode:

**Caspian — patient identity strip**:
`UserRound icon · M. Hollister · MRN 8.4127.881 · 68 F · Complex • Tier C · 1,184 resources · 47 encounters` →
right side: `Pinned to session` chip + green `🔒 Private patient
boundary` chip.

**Trial Finder — package identity strip**:
`Package logo · Trial Finder @2.4.1 · vendor Helix Clinical ·
permission chips (read patient anchors / external registry /
outbound packet) · RUN state pill (animated dot + step counter +
elapsed) · Pause` → right side: amber `Caspian · Hollister` anchor
chip.

### 5. Atlas body — five-pane shell

```
| sessions (248) | chat (1fr, min 360) | workbench (1.4fr, min 320) | files (260) + inspector (260, stacked) |
```

Every gutter is a 5px drag resizer that lights up on hover. Min widths
enforced. The right column stacks files (top) and inspector (bottom)
with a horizontal resizer between them.

Toggles S / C / P / F / I in the titlebar (or Alt+letter) collapse
the corresponding pane. Surviving panes reflow to fill the freed
space.

### 6. Sessions pane

- Header: workspace switcher (workspace name with chevron) + "New
  session" button.
- Below: PACKAGE row (only on marketplace workspaces — links to the
  package home), then session list grouped by date.
- Session row: 14×1fr grid, 6×8px padding, status dot (active /
  running / complete) + title + meta line (workflow tag + relative
  time).
- Hover row: `--surface-3` background; active row: 2px left border
  in module color.

### 7. Chat (Caspian session)

- Header: `Clinical chat · Caspian agent` + green private-boundary
  chip.
- Message types:
  - **User**: rounded card, `--surface-2`, right-aligned avatar
  - **Agent**: 28×1fr grid, square avatar with module mark, body
    text 13/20, citation chips inline (`99 c_1042` style with quote
    glyph)
  - **Tool trace**: 11px mono, indented under agent message,
    collapsed by default
  - **Approval card**: `--caution-tint` bg, amber line, icon +
    title (12/600/uppercase) + body + actions (`Approve` primary
    ink-1, `Hold for attending` ghost)
- **Action chip row** (under selected messages): pill chips with
  lucide icons that open the matching workbench tab.
- Citation chip click: opens Inspector → Evidence tab with the
  resource detail card.

### 8. Composer

- Sits at bottom of chat pane, sticky.
- 1-line input → expands to up to 5 lines.
- Below: Attach chip, Pin context chip, mode select
  (`clinical-high` / `clinical-balanced` / `draft`), `↩ to send`
  hint, send button (32×32, ink-1 bg).

### 9. Workbench (P pane)

Multi-tab artifact viewer.

- **Tab strip**: 32px tall, tabs are 12×8px padding with 12.5px text,
  dirty marker (•), close X on hover. Plus button at the end.
- **Tab types in use**:
  - Pre-op briefing (rich preview document — see #10)
  - Anticoag note (markdown editor)
  - Clearance summary (JSON viewer with FHIR resource IDs)
  - v1 → v2 diff (unified diff, 40×14×1fr grid)
  - Trial Finder candidate board
  - Packet outline (markdown editor)
  - Package manifest (JSON viewer)
- All tabs share a header strip: title + saved/dirty state + actions
  (Cite source, Pin, Share, Export).

### 10. Preview document (pre-op briefing)

The hero artifact in Caspian. Structure:

1. **Disposition banner** — 36×1fr×auto grid, icon (`AlertOctagon` /
   `AlertTriangle` / `CheckCircle2`), `HOLD / REVIEW / CLEAR` flag in
   semantic color, one-line rationale, action button. 4px left bar.
2. **Fact rail** — 5-cell strip, each cell: 10.5px eyebrow label +
   18px value (mono for numerics).
3. **Dense panels** — Critical Medications, Key Comorbidities, Recent
   Labs, Anesthesia Notes. Each is an EvidenceTable with a citation
   column.
4. **Footer link** — `Curated briefing — full chart in Care Journey →`.

### 11. Files pane

- 260px wide (resizable), filter input, file tree, pinned objects
  section, drag-to-tab.
- File row: icon + name, click opens in workbench, double-click
  pins.

### 12. Inspector pane

- 260px wide (resizable, stacked under files).
- Three tabs: **Evidence · Trace · Context**.
- Evidence: empty state (`No citation selected`), or evidence card
  with type / id / body / metadata (resource type, date, encounter,
  open in FHIR link).
- Trace: tool call trace for the active message.
- Context: pinned context items, persistent across the session.

### 13. Package home (Marketplace entry view)

Renders in place of the workspace body when no session is selected
on a marketplace workspace.

1. **Hero**: package logo (40px), name + version chip + vendor,
   one-paragraph description, `Start new run` primary button + `Configure` ghost button.
2. **Permissions ledger**: 3-column grid of permission cards
   (Reads patient anchors / Calls external registries / Sends
   outbound packets). The last one is amber (`ph-perm.warn`) because
   it's gated.
3. **Workflows**: 2-column grid of runnable workflow cards. Each
   card: lucide icon + title + plain-English description + input /
   output meta line.
4. **Recent runs**: dense table with columns `id · patient ·
   workflow · started · status · outcome · open`. Status pill in
   semantic color. Hover row: `--surface-2`.
5. **About**: vendor, version, installed by, update channel, trust
   posture, audit log link — all as 180×1fr grid rows.

### 14. Tweaks panel (dev/internal only)

Floating bottom-right panel toggled by the app's tweaks affordance.
Controls: theme (light/dark), accent palette (4 options), density,
and pane visibility. Persistent via the project's
`__edit_mode_set_keys` host protocol. Wrap defaults in
`/*EDITMODE-BEGIN*/{ … }/*EDITMODE-END*/`.

---

## Interactions

- **Pane toggles**: clicking S / C / P / F / I (or Alt+letter)
  toggles that pane's visibility. The stage grid template reflows
  with `grid-template-columns`; pane components themselves remain
  mounted and just collapse to `display: none`.
- **Pane resizers**: 5px wide vertical resizers between sessions↔chat,
  chat↔workbench, workbench↔right rail. Horizontal resizer between
  files↔inspector. Hover lights to `--action-tint`. `min-width`
  enforced on every pane.
- **Citation chip click**: `<CitationChip>` posts `{type: 'select',
  id}` to the inspector store. Inspector switches to Evidence tab and
  loads the resource detail.
- **Action chip click**: opens the matching workbench tab; if already
  open, focuses it.
- **File tree click**: opens file as new workbench tab; double-click
  pins it.
- **Workspace switcher**: switches workspaceId, resets active session,
  triggers context strip variant change.
- **Top-nav Caspian click**: routes to Caspian workspace.
- **Top-nav Workspaces click**: opens dropdown.
- **Top-nav Workspaces → Explore workspaces**: routes to marketplace
  index.
- **Top-nav Workspaces → recently viewed item**: routes directly to
  that workspace's package home.
- **Hamburger click**: opens platform drawer; scrim click or X
  closes.
- **Run workflow click**: posts a new turn to the active session
  with the current workflow type.

---

## State management

Carry forward the prototype's state shape into proper Zustand /
Redux / Context (developer's choice based on what the repo already
uses). The state surface area is roughly:

```ts
type AtlasState = {
  // top-level
  activeModule: 'patient-record' | 'fhir-charts' | 'caspian' | 'workspaces' | 'learn';
  platformDrawerOpen: boolean;

  // workspace-level
  workspaceId: 'clinical-insights' | 'trial-finder' | 'med-access' | 'site-coord';
  activeSessionId: string | null;          // null = package home for marketplace, latest for Caspian

  // pane visibility + sizing
  panes: { sessions: boolean; chat: boolean; workbench: boolean; files: boolean; inspector: boolean };
  paneSizes: { sessionsW: number; chatW: number; workbenchW: number; rightW: number; filesH: number };

  // workbench
  tabs: WorkbenchTab[];
  activeTabId: string;
  dirtyTabIds: Set<string>;

  // inspector
  inspectorTab: 'evidence' | 'trace' | 'context';
  selectedCitationId: string | null;

  // theme / tweaks
  theme: 'light' | 'dark';
  accent: 'clinical' | 'indigo' | 'teal' | 'graphite';
  density: 'comfortable' | 'compact';
};
```

State transitions follow the interaction list above. Persist
`paneSizes`, `theme`, `accent`, `density` to `localStorage` keyed by
workspace.

---

## Routing

Suggested URL shape:

```
/patient-record/...                            existing
/fhir-charts/...                               existing
/caspian                                       Caspian home (latest session)
/caspian/sessions/:id                          Caspian session
/workspaces                                    marketplace index
/workspaces/:packageId                         package home
/workspaces/:packageId/sessions/:id            package session
/learn/...                                     internal section
/settings, /account, /billing, ...             reached from platform drawer
```

Old routes to redirect:
- `/data-aggregator/*` → `/patient-record/data-aggregator/*` (folded
  in as a sub-route)
- `/preop/*` → `/caspian/sessions/new?workflow=preop` (or nearest
  active pre-op session)
- `/trials/*` → `/workspaces/trial-finder/*`
- `/medication-access/*` → `/workspaces/med-access/*`

---

## Iconography

Lucide React at **14px in nav, 16px in dense UI, 18–20px in module
overview tiles**. Stroke weight **1.5** (default). Color inherits
from text.

Locked icon mappings:
- Patient Record → `Database`
- FHIR Charts → `LineChart`
- Caspian → `Sparkles` (or `Activity` if Caspian needs to read as
  clinical-first)
- Workspaces → `Boxes`
- Learn → `BookOpen`
- Pre-Op (workflow type) → `Activity`
- Status: critical → `AlertOctagon`, caution → `AlertTriangle`,
  clear → `CheckCircle2`, info → `Info`
- Citation → `Quote`
- Agent → `MessageSquareText`
- Run state (active) → `Loader` (animated)

No emoji. No Unicode glyphs except `→` inline in agent reasoning.

---

## Component contracts

The key new / refactored components and their prop signatures.
Implement these as TypeScript modules.

```ts
// AppShell.tsx
type AppShellProps = {
  children: React.ReactNode;
};

// ModuleBar.tsx
type ModuleBarProps = {
  activeModule: ModuleId;
  onSelect: (m: ModuleId) => void;
  workspaceId: WorkspaceId;
  onSwitchWorkspace: (w: WorkspaceId) => void;
  user: { initials: string; name: string; org: string };
};

// PlatformDrawer.tsx
type PlatformDrawerProps = {
  open: boolean;
  onClose: () => void;
  user: { initials: string; name: string; org: string };
};

// Titlebar.tsx
type TitlebarProps = {
  breadcrumbs: { label: string; href?: string }[];
  onRunWorkflow: () => void;
  panes: PaneVisibility;
  onTogglePane: (key: keyof PaneVisibility) => void;
};

// ContextStrip.tsx — switches variant on workspaceId
type ContextStripProps =
  | { variant: 'caspian-patient'; patient: PatientIdentity }
  | { variant: 'package'; package: PackageIdentity; anchor: { workspace: string; patient: string }; runState: RunState };

// SessionsPane, ChatPane, WorkbenchPane, FilesPane, InspectorPane
// — each takes (id, visible, width, onResize, ...content props)

// CitationChip.tsx
type CitationChipProps = {
  id: string;       // e.g. 'c_1042'
  label?: string;
  onClick: (id: string) => void;
};

// EvidenceCard.tsx
type EvidenceCardProps = {
  citation: {
    id: string;
    resourceType: string;   // 'Observation', 'MedicationStatement', etc.
    body: string;
    date: string;
    encounterId?: string;
    fhirUrl: string;
  };
};

// PackageHome.tsx
type PackageHomeProps = {
  pkg: {
    id: string; name: string; version: string; vendor: string;
    description: string; logoColor: string;
  };
  permissions: Permission[];
  workflows: Workflow[];
  recentRuns: Run[];
};

// FactRail.tsx
type FactRailProps = {
  cells: { label: string; value: string | number; mono?: boolean }[];
};

// DispositionBanner.tsx
type DispositionBannerProps = {
  state: 'HOLD' | 'REVIEW' | 'CLEAR' | 'CRITICAL';
  message: string;
  action?: { label: string; onClick: () => void };
};

// EvidenceTable.tsx
type EvidenceTableProps<Row> = {
  columns: { id: keyof Row; header: string; mono?: boolean; align?: 'left'|'right' }[];
  rows: Row[];
  citationKey?: keyof Row;   // when set, renders a CitationChip in that column
};
```

---

## Files in this bundle

```
README.md                          this document
tokens/
  design-tokens.css                drop-in token layer (light + dark)
  tailwind-theme.md                Tailwind v4 @theme mapping
prototype/
  Atlas Agentic Workspaces.html    entry HTML — load this in a browser to see the prototype
  app.jsx                          shell composition, state, resizers, tweaks
  shell.jsx                        ModuleBar, PlatformDrawer, Titlebar, ContextStrip
  panes.jsx                        SessionsPane, ChatPane, WorkbenchPane, FilesPane, InspectorPane, PackageHome
  icons.jsx                        lucide subset + Icon wrapper
  data.js                          seed sessions, files, tabs, citations, workflows, runs
  styles.css                       full stylesheet — every value matches the token table above
  tweaks-panel.jsx                 dev tweaks panel (theme, accent, density, panes)
```

To preview: open `prototype/Atlas Agentic Workspaces.html` in any
modern browser. No build step. The bundle is fully offline-capable.

---

## Assets

The prototype uses **no raster assets**. All marks (EHI Ignite logo,
Atlas mark, package logos) are CSS / SVG. Reuse existing brand
assets from the EHI Ignite repo where applicable; do not lift the
prototype's placeholder marks.

Fonts:
- **Inter Tight** — Google Fonts CDN
- **IBM Plex Mono** — Google Fonts CDN
- **Source Serif 4** — Google Fonts CDN (optional, used sparingly in
  display contexts)

If the org has brand-sanctioned faces, swap them in via the
`--font-sans` / `--font-mono` / `--font-serif` variables.

---

## Open questions for the dev to confirm with design

1. **Caspian icon** — `Sparkles` (agentic) or `Activity` (clinical)?
   Pick one and commit; both are listed above.
2. **Workspaces dropdown trigger** — click only, or hover-to-open
   with click-to-pin? Prototype uses click. If the team wants hover,
   keep the click behavior as a fallback for accessibility.
3. **Pre-Op redirect target** — when the URL is `/preop/:patientId`,
   route to the latest pre-op session for that patient if one exists,
   or always start a new one?
4. **Learn section visibility** — restrict to internal users by
   org/role, or show to all with internal-only sub-routes? Prototype
   assumes the former.

Hand these back to design before merging Phase 2.
