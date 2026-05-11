# Design system

The active design system for EHI Ignite is **Atlas Agentic Workspaces**.

- **Token contract:** [`.claude/handoff/atlas/tokens/design-tokens.css`](../.claude/handoff/atlas/tokens/design-tokens.css)
- **Live source:** [`app/src/index.css`](../app/src/index.css) (Tailwind v4 `@theme` block)
- **Spec:** [`.claude/handoff/atlas/README.md`](../.claude/handoff/atlas/README.md)
- **Vision:** [`design/agentic-shell-spec/`](./agentic-shell-spec/)
- **Component inventory:** [`app/src/components/atlas/README.md`](../app/src/components/atlas/README.md)

## Quick reference

```
Surface  --bg-app          #eef2f6   cool paper, never beige
         --surface-0       #ffffff   primary cards/panels
Ink      --ink-1           #0b1220   primary text
         --ink-3           #5b6677   secondary text
Lines    --line-1          #dde3ea   default border
Action   --action          #1d4ed8   clinical blue
         --action-tint     #e8eefe
Semantic --critical        #b91c1c
         --caution         #a85a07
         --clear           #047857
Chrome   --chrome-modulebar #0c1320  dark navy module bar
         --chrome-titlebar  #0f172a  dark navy titlebar
Type     Inter Tight (sans), IBM Plex Mono (mono), Source Serif 4 (display)
Spacing  4 / 8 / 12 / 16 / 20 / 24 / 32   (4px base, intentionally tight)
Radii    4 / 6 / 10 / 999  — no other values
Shadow   0 1px 2px / 0 4px 14px / 0 18px 40px  (cool, tiny ramp)
Motion   120ms ease-out (modal/drawer 160ms). No spring, no bounce, no scale-on-hover.
```

## Conventions

- **Tokens, not hex.** Inline `style={{ background: "var(--action)" }}` and Tailwind utilities (`bg-action`, `text-ink-1`, `border-line-1`) both read against the same vars.
- **Sentence case** in copy. Exception: proper nouns (Caspian, Trial Finder) and clinical status flags (`HOLD`, `REVIEW`, `CLEAR`, `CRITICAL`).
- **Lucide icons** at 14px in nav, 16px in dense UI, stroke 1.5. No emoji.
- **No 12 / 16 / 20 / 24px radii** anywhere outside `--r-pill`.
- **Border-first surfaces.** 1px `--line-1` defines almost every card; the shadow ramp is intentionally tiny.
- **Cool shadows only.** `rgba(15, 23, 42, …)`. No colored glows.

## Historical

The previous Miro-inspired design system (Blue 450, beige canvas, Roobert PRO, pastel palette) is preserved at [`archive/design-miro/`](../archive/design-miro/) for reference. It was replaced wholesale during the Atlas redesign — every token, every color, the full font stack.
