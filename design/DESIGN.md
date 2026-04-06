# Design System: Miro-Inspired

*Source: [VoltAgent/awesome-design-md](https://github.com/VoltAgent/awesome-design-md/tree/main/design-md/miro)*  
*Use this file as reference when prompting AI agents (Claude, Cursor) to generate UI.*

---

## 1. Visual Theme & Atmosphere

Clean, collaborative-tool-forward. Communicates clarity and precision through generous whitespace, pastel accent colors, and a confident geometric font. Predominantly white canvas with near-black text and a distinctive pastel palette.

**Key Characteristics:**
- White canvas with near-black (`#1c1c1e`) text
- Roobert PRO Medium with multiple OpenType character variants
- Pastel accent palette: coral, rose, teal, orange, yellow, moss (light + dark pairs)
- Blue 450 (`#5b76fe`) as primary interactive color
- Success green (`#00b473`) for positive states
- Generous border-radius: 8px–50px range
- Ring shadow border: `rgb(224,226,232) 0px 0px 0px 1px`

---

## 2. Color Palette & Roles

### Primary
- **Near Black** (`#1c1c1e`): Primary text
- **White** (`#ffffff`): Primary surface
- **Blue 450** (`#5b76fe`): Primary interactive (buttons, links, focus rings)
- **Actionable Pressed** (`#2a41b6`): Pressed/active state for primary interactive

### Pastel Accents (Light/Dark pairs)
- **Coral**: Light `#ffc6c6` / Dark `#600000`
- **Rose**: Light `#ffd8f4`
- **Teal**: Light `#c3faf5` / Dark `#187574`
- **Orange**: Light `#ffe6cd`
- **Yellow**: Dark `#746019`
- **Pink** (`#fde0f0`): Soft pink surface
- **Red** (`#fbd4d4`): Light red surface

### Semantic
- **Success** (`#00b473`): Positive states, active/confirmed
- **Warning** (implied orange): Caution states
- **Error** (implied red): Destructive/danger states

### Neutral
- **Slate** (`#555a6a`): Secondary text, captions
- **Input Placeholder** (`#a5a8b5`): Form placeholder text
- **Border** (`#c7cad5`): Button borders, dividers
- **Ring** (`rgb(224,226,232)`): Shadow-as-border for cards

---

## 3. Typography Rules

### Font Families
- **Display**: `Roobert PRO Medium` — OpenType: `"blwf", "cv03", "cv04", "cv09", "cv11"`
- **Display Variants**: `Roobert PRO SemiBold`, `Roobert PRO SemiBold Italic`
- **Body**: `Noto Sans` — OpenType: `"liga" 0, "ss01", "ss04", "ss05"`

### Hierarchy

| Role | Font | Size | Weight | Line Height | Letter Spacing |
|------|------|------|--------|-------------|----------------|
| Display Hero | Roobert PRO Medium | 56px | 400 | 1.15 | -1.68px |
| Section Heading | Roobert PRO Medium | 48px | 400 | 1.15 | -1.44px |
| Card Title | Roobert PRO Medium | 24px | 400 | 1.15 | -0.72px |
| Sub-heading | Noto Sans | 22px | 400 | 1.35 | -0.44px |
| Feature | Roobert PRO Medium | 18px | 600 | 1.35 | normal |
| Body | Noto Sans | 18px | 400 | 1.45 | normal |
| Body Standard | Noto Sans | 16px | 400–600 | 1.50 | -0.16px |
| Button | Roobert PRO Medium | 17.5px | 700 | 1.29 | 0.175px |
| Caption | Roobert PRO Medium | 14px | 400 | 1.71 | normal |
| Small | Roobert PRO Medium | 12px | 400 | 1.15 | -0.36px |
| Micro Uppercase | Roobert PRO | 10.5px | 400 | 0.90 | uppercase |

---

## 4. Component Stylings

### Buttons
- **Primary**: Blue 450 background, white text, 8px radius, 7px 12px padding
- **Outlined**: Transparent bg, `1px solid #c7cad5`, 8px radius, 7px 12px padding
- **Icon circle**: 50% radius, white bg with ring shadow

### Cards
- Radius: 12px–24px
- Background: white or pastel accent
- Border: ring shadow `rgb(224,226,232) 0px 0px 0px 1px`

### Inputs
- White background
- `1px solid #e9eaef` border
- 8px radius
- 16px padding
- Placeholder: `#a5a8b5`

### Badges / Status Pills
- Small, rounded-full
- Use semantic colors (success green, warning orange, error red)
- Light background + darker text (e.g., `#c3faf5` bg + `#187574` text for teal)

---

## 5. Layout Principles

- **Spacing scale**: 1–24px base (Tailwind default scale works well)
- **Radius**:
  - Buttons: 8px
  - Cards: 10px–12px
  - Panels: 20px–24px
  - Large containers: 40px–50px
- **Elevation**: Minimal — use ring shadow + pastel surface contrast instead of heavy drop shadows
- **Whitespace**: Generous — padding inside containers should feel comfortable, not cramped

---

## 6. Depth & Elevation

Avoid heavy box shadows. Use:
- `box-shadow: rgb(224,226,232) 0px 0px 0px 1px` for cards and containers
- Pastel surface background color to create visual separation
- Subtle `box-shadow: 0 1px 3px rgba(0,0,0,0.08)` for floating elements

---

## 7. Do's and Don'ts

### Do
- Use pastel light/dark pairs for feature sections and status indicators
- Apply Roobert PRO with OpenType character variants for headings
- Use Blue 450 (`#5b76fe`) for all interactive elements
- Use ring shadow for card separation (not drop shadows)
- Keep layouts generous with whitespace

### Don't
- Don't use heavy shadows
- Don't mix more than 2 pastel accents per section
- Don't use pure black (`#000000`) — use near-black (`#1c1c1e`)
- Don't use generic grey for all secondary text — use Slate (`#555a6a`)

---

## 8. Responsive Breakpoints

| Breakpoint | Width |
|------------|-------|
| xs | 425px |
| sm | 576px |
| md | 768px |
| lg | 1024px |
| xl | 1280px |
| 2xl | 1920px |

---

## 9. Agent Prompt Guide

### Quick Color Reference for Prompts
```
Text: Near Black (#1c1c1e)
Background: White (#ffffff)
Interactive: Blue 450 (#5b76fe)
Interactive pressed: #2a41b6
Success: #00b473
Border: #c7cad5
Ring: rgb(224,226,232)
Secondary text: #555a6a
Placeholder: #a5a8b5
```

### Example Component Prompts

**Hero section:**
> "White background. Roobert PRO Medium 56px, line-height 1.15, letter-spacing -1.68px. Near-black text. Blue 450 primary CTA. Outlined secondary (1px solid #c7cad5, 8px radius). Generous padding."

**Status badge (active):**
> "Rounded-full pill. Success green (#00b473) background at 15% opacity. #00b473 text. 12px Roobert PRO Medium. Uppercase letter-spacing."

**Data card:**
> "White surface. Ring shadow (rgb(224,226,232) 0px 0px 0px 1px). 12px radius. 24px padding. Card title in Roobert PRO Medium 24px. Body in Noto Sans 16px Slate (#555a6a)."

**Risk flag (critical):**
> "Coral light (#ffc6c6) background. #600000 text. 8px radius. ⚠️ icon. Roobert PRO SemiBold 14px."

---

## Clinical Application Adaptations

For the EHI Ignite clinical tools, map the Miro palette to clinical semantics:

| Clinical State | Color | Token |
|---------------|-------|-------|
| Critical / Active risk | Coral `#ffc6c6` / `#600000` | `risk-critical` |
| Warning / Historical risk | Orange `#ffe6cd` | `risk-warning` |
| Clear / No finding | Teal `#c3faf5` / `#187574` | `risk-clear` |
| Active medication | Blue 450 `#5b76fe` | `med-active` |
| Stopped medication | Slate `#555a6a` | `med-stopped` |
| Positive lab trend | Success `#00b473` | `trend-positive` |
| Negative lab trend | Coral `#ffc6c6` | `trend-negative` |
