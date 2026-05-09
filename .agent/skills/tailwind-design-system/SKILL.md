---
name: tailwind-design-system
description: Build scalable design systems with Tailwind CSS v4.1, @theme directive, OKLCH colors, design tokens, CVA components, and accessible patterns.
type: feature
version: 4.1.0
updated: 2026-02-02
allowed-tools: Read, Write, Edit, Glob, Grep
---

# Tailwind Design System (v4.1 - 2026)

Build production-ready design systems with Tailwind CSS v4.1, using CSS-first configuration, OKLCH colors, design tokens, component variants, and accessibility.

## Use this skill when

- Creating a component library with Tailwind v4
- Implementing design tokens via `@theme` directive
- Building responsive and accessible components
- Standardizing UI patterns across a codebase
- Setting up dark mode with OKLCH color system
- Using CVA (Class Variance Authority) for variants
- Implementing container queries for component-level responsive design

## Do not use this skill when

- The task is unrelated to tailwind design system
- You need Tailwind v3 legacy configuration (use migration guide)

## Key v4 Changes

| v3 (Legacy) | v4.1 (Current) |
|-------------|----------------|
| `tailwind.config.js` | CSS `@theme` directive |
| HSL colors | **OKLCH** colors |
| `@tailwind base/components/utilities` | `@import "tailwindcss"` |
| PostCSS plugin | Oxide engine (10x faster) |

## Quick Start

```css
@import "tailwindcss";

@theme {
  --color-primary: oklch(0.7 0.15 250);
  --font-sans: 'Inter', system-ui, sans-serif;
}
```

## Instructions

1. Use CSS-first configuration with `@theme` directive
2. Prefer OKLCH colors for perceptually uniform palettes
3. Implement CVA for type-safe component variants
4. Use container queries (`@container`) for reusable components
5. Follow 8pt grid system for spacing
6. Ensure WCAG 2.2 AA contrast ratios

## Resources

- `resources/implementation-playbook.md` - Complete patterns, CVA components, theming examples
