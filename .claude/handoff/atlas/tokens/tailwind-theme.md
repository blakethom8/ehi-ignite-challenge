# Tailwind v4 `@theme` mapping

The Atlas tokens map cleanly to a Tailwind v4 `@theme` block. Drop this
into `app/src/index.css` (or wherever you currently host the theme
import) **after** `@import "tailwindcss";` and the
`design-tokens.css` file.

```css
@import "tailwindcss";
@import "./design-tokens.css";

@theme {
  /* color */
  --color-app:        var(--bg-app);
  --color-chrome:     var(--bg-chrome);
  --color-surface-0:  var(--surface-0);
  --color-surface-1:  var(--surface-1);
  --color-surface-2:  var(--surface-2);
  --color-surface-3:  var(--surface-3);

  --color-ink-1: var(--ink-1);
  --color-ink-2: var(--ink-2);
  --color-ink-3: var(--ink-3);
  --color-ink-4: var(--ink-4);
  --color-ink-5: var(--ink-5);

  --color-line-1: var(--line-1);
  --color-line-2: var(--line-2);
  --color-line-3: var(--line-3);

  --color-action:        var(--action);
  --color-action-hover:  var(--action-hover);
  --color-action-press:  var(--action-press);
  --color-action-tint:   var(--action-tint);
  --color-action-tint-2: var(--action-tint-2);
  --color-action-line:   var(--action-line);

  --color-critical:      var(--critical);
  --color-critical-tint: var(--critical-tint);
  --color-critical-line: var(--critical-line);
  --color-caution:       var(--caution);
  --color-caution-tint:  var(--caution-tint);
  --color-caution-line:  var(--caution-line);
  --color-clear:         var(--clear);
  --color-clear-tint:    var(--clear-tint);
  --color-clear-line:    var(--clear-line);
  --color-info:          var(--info);
  --color-info-tint:     var(--info-tint);

  --color-mod-record: var(--mod-record);
  --color-mod-preop:  var(--mod-preop);
  --color-mod-trials: var(--mod-trials);
  --color-mod-meds:   var(--mod-meds);

  --color-chrome-modulebar: var(--chrome-modulebar);
  --color-chrome-titlebar:  var(--chrome-titlebar);

  /* font */
  --font-sans:  var(--font-sans);
  --font-serif: var(--font-serif);
  --font-mono:  var(--font-mono);

  /* spacing — extend, don't replace, so Tailwind defaults still work */
  --spacing-s1: var(--s1);
  --spacing-s2: var(--s2);
  --spacing-s3: var(--s3);
  --spacing-s4: var(--s4);
  --spacing-s5: var(--s5);
  --spacing-s6: var(--s6);
  --spacing-s8: var(--s8);

  /* radius */
  --radius-r1:   var(--r-1);
  --radius-r2:   var(--r-2);
  --radius-r3:   var(--r-3);
  --radius-pill: var(--r-pill);

  /* shadow */
  --shadow-s1: var(--shadow-1);
  --shadow-s2: var(--shadow-2);
  --shadow-s3: var(--shadow-3);
}
```

## Utility usage examples

```tsx
// App background
<div className="bg-app min-h-screen">

// Card
<div className="bg-surface-0 border border-line-1 rounded-r2 p-s4 shadow-s1">

// Primary button
<button className="bg-action hover:bg-action-hover text-white px-s4 py-s2 rounded-r2">

// Citation chip
<span className="bg-action-tint text-action border border-action-line rounded-pill px-s2 py-0.5 font-mono text-[11px]">

// Disposition banner (HOLD)
<div className="bg-critical-tint border-l-4 border-critical text-critical p-s4">

// Module bar tab
<button className="text-[rgba(229,233,240,0.62)] hover:text-white hover:bg-[rgba(255,255,255,0.05)] data-[active]:text-white data-[active]:bg-[rgba(255,255,255,0.08)] px-s3 py-s2">
```

## Removing the legacy values

After Phase 1 merges, audit and delete from your existing styles:
- Any beige/cream surface values (commonly `#faf8f3`, `#f5f1ea`,
  `#fdfbf6` and similar warm tones)
- Any radius value of `12 / 16 / 20 / 24px` outside `--r-pill`
- Any shadow with a tint other than `rgba(15, 23, 42, ...)` — the
  ramp is intentionally cool and tiny
- Decorative borders / "ring" effects
- Hover scale or translate transitions

Run a grep for these and either remove or remap to the new tokens.
