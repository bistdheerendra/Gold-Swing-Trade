# Instrument Theming (Gold / Silver)

**Phase:** 11.12  
**Goal:** One product UI; palette follows the active research instrument.

## Model

| Active symbol | Theme id | Feel |
|---------------|----------|------|
| `PAXGUSD` | `gold` (default) | Warm gold accents on dark ink |
| `SLVONUSD` | `silver` | Cool greys / platinum with a steel-blue undertone |

Themes share **layout, spacing, and typography**. Only color tokens and ambient background glow change.

## How it works

1. Design tokens live in `frontend/src/index.css` (`@theme` + `:root` / `[data-instrument-theme]`).
2. Tailwind utilities (`bg-gold`, `text-cream`, `border-line`, …) read CSS variables such as `--color-gold`.
3. Selecting a symbol calls `applyInstrumentTheme(symbol)` (`frontend/src/lib/theme.ts`), which sets:

```html
<html data-instrument-theme="gold|silver">
```

4. Silver overrides the **same** variable names (`--color-gold` becomes the silver accent, etc.) so components do not need per-symbol class forks.
5. `html` / `body` / `#root` use a short CSS transition on color / background so tab switches do not flash.

## Token map (conceptual)

| Token | Gold | Silver |
|-------|------|--------|
| `--color-gold` | `#d4af37` | `#8fa3b8` (steel accent) |
| `--color-gold-bright` | `#f0d78c` | `#d7e0ea` |
| `--color-cream` | warm cream | cool near-white `#e8eef5` |
| `--color-panel` / `--color-ink` | warm dark | cool dark slate |
| `--theme-glow-*` | gold radial wash | cool silver / blue wash |

Bull / bear / Binance research colors stay shared (signal semantics, not instrument metal).

## Adding a third instrument theme

1. Add `theme: "…"` on the symbol in `frontend/src/lib/symbols.ts`.
2. Add a `[data-instrument-theme="…"]` block in `index.css` overriding the same `--color-*` / `--theme-*` variables.
3. Keep dark structure; avoid scattering conditional colors in components.

## Don’t

- Don’t blend gold and silver **data** because themes share a codebase.
- Don’t hard-code hex gold in new components — use theme tokens / Tailwind color utilities.
- Don’t invent a literal “shiny metal” look; prefer crisp neutrals and clear contrast.
