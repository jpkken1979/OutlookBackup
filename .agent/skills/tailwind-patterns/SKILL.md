---
name: tailwind-patterns
description: "Expert guide to tailwind css patterns (v4.1 - 2026)."
type: feature

---
name: tailwind-patterns
description: Tailwind CSS v4.1 (2026) - CSS-first configuration, @theme directive, container queries, OKLCH colors, design tokens, responsive patterns.
allowed-tools: Read, Write, Edit, Glob, Grep
version: 4.1.0
updated: 2026-02-02
---

# Tailwind CSS Patterns (v4.1 - 2026)

> Modern utility-first CSS framework with CSS-native configuration and zero-runtime.

---

## 1. Tailwind v4 Architecture

### What Changed from v3

| v3 (Legacy) | v4.1 (Current) |
|-------------|----------------|
| `tailwind.config.js` | CSS-based `@theme` directive |
| PostCSS plugin | Oxide engine (10x faster) |
| JIT mode | Native, always-on |
| Plugin system | CSS-native `@utility` and `@custom-variant` |
| `@apply` directive | Still works, but prefer components |
| `@tailwind base/components/utilities` | `@import "tailwindcss"` |
| HSL colors | **OKLCH** colors (perceptually uniform) |
| Content config | Automatic detection |

### v4 Core Concepts

| Concept | Description |
|---------|-------------|
| **CSS-first** | Configuration in CSS, not JavaScript |
| **Oxide Engine** | Rust-based compiler, 10x faster builds |
| **Native Nesting** | CSS nesting without PostCSS |
| **CSS Variables** | All tokens exposed as `--*` vars |
| **Zero-runtime** | No JS in production (~10kB CSS) |
| **OKLCH Colors** | Wide-gamut P3 colors support |
| **Container Queries** | `@container` native support |
| **Cascade Layers** | Proper specificity management |

---

## 2. Installation (v4.1)

### Vite (Recommended)

```bash
npm create vite@latest my-project
cd my-project
npm install tailwindcss @tailwindcss/vite
```

**vite.config.ts:**
```typescript
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [tailwindcss()],
})
```

**CSS entry point:**
```css
@import "tailwindcss";
```

### Other Methods

| Method | Command/Config |
|--------|----------------|
| **PostCSS** | `npm i tailwindcss @tailwindcss/postcss` |
| **CLI** | `npx @tailwindcss/cli -i input.css -o output.css` |
| **CDN** | `<script src="https://cdn.tailwindcss.com"></script>` (dev only) |

---

## 3. CSS-Based Configuration (@theme)

### Theme Definition

```css
@import "tailwindcss";

@theme {
  /* Colors - OKLCH format (perceptually uniform) */
  --color-primary: oklch(0.7 0.15 250);
  --color-primary-hover: oklch(0.6 0.15 250);
  --color-surface: oklch(0.98 0 0);
  --color-surface-dark: oklch(0.15 0 0);

  /* Custom brand colors */
  --color-brand-mint: oklch(0.72 0.11 178);
  --color-brand-coral: oklch(0.74 0.17 40.24);

  /* Spacing scale (generates p-*, m-*, gap-*, etc.) */
  --spacing-xs: 0.25rem;
  --spacing-sm: 0.5rem;
  --spacing-md: 1rem;
  --spacing-lg: 2rem;
  --spacing-xl: 3rem;

  /* Typography */
  --font-sans: 'Inter', system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', monospace;
  --font-display: 'Outfit', sans-serif;

  /* Custom breakpoints */
  --breakpoint-xs: 30rem;
  --breakpoint-3xl: 120rem;

  /* Border radius */
  --radius-pill: 9999px;

  /* Shadows */
  --shadow-glow: 0 0 20px oklch(0.7 0.15 250 / 0.3);

  /* Custom animations */
  --animate-fade-in: fade-in 0.3s ease-out;

  @keyframes fade-in {
    from { opacity: 0; transform: translateY(-4px); }
    to { opacity: 1; transform: translateY(0); }
  }
}
```

### Theme Variable Namespaces

| Namespace | Generates | Example Usage |
|-----------|-----------|---------------|
| `--color-*` | Color utilities | `bg-primary`, `text-brand-mint` |
| `--font-*` | Font families | `font-sans`, `font-display` |
| `--text-*` | Font sizes | `text-xl`, `text-2xl` |
| `--spacing-*` | Spacing/sizing | `p-md`, `gap-lg`, `w-xl` |
| `--radius-*` | Border radius | `rounded-pill` |
| `--shadow-*` | Box shadows | `shadow-glow` |
| `--breakpoint-*` | Responsive variants | `xs:*`, `3xl:*` |
| `--animate-*` | Animations | `animate-fade-in` |

### When to Extend vs Override

| Action | Syntax | Use When |
|--------|--------|----------|
| **Extend** | Just add new vars | Adding alongside defaults |
| **Reset namespace** | `--color-*: initial;` | Replacing entire scale |
| **Reset all** | `--*: initial;` | Custom theme from scratch |
| **Semantic tokens** | `--color-primary` | Purpose-based naming |

---

## 3. Container Queries (v4 Native)

### Breakpoint vs Container

| Type | Responds To |
|------|-------------|
| **Breakpoint** (`md:`) | Viewport width |
| **Container** (`@container`) | Parent element width |

### Container Query Usage

| Pattern | Classes |
|---------|---------|
| Define container | `@container` on parent |
| Container breakpoint | `@sm:`, `@md:`, `@lg:` on children |
| Named containers | `@container/card` for specificity |

### When to Use

| Scenario | Use |
|----------|-----|
| Page-level layouts | Viewport breakpoints |
| Component-level responsive | Container queries |
| Reusable components | Container queries (context-independent) |

---

## 4. Responsive Design

### Breakpoint System

| Prefix | Min Width | Target |
|--------|-----------|--------|
| (none) | 0px | Mobile-first base |
| `sm:` | 640px | Large phone / small tablet |
| `md:` | 768px | Tablet |
| `lg:` | 1024px | Laptop |
| `xl:` | 1280px | Desktop |
| `2xl:` | 1536px | Large desktop |

### Mobile-First Principle

1. Write mobile styles first (no prefix)
2. Add larger screen overrides with prefixes
3. Example: `w-full md:w-1/2 lg:w-1/3`

---

## 5. Dark Mode

### Configuration Strategies

| Method | Behavior | Use When |
|--------|----------|----------|
| `class` | `.dark` class toggles | Manual theme switcher |
| `media` | Follows system preference | No user control |
| `selector` | Custom selector (v4) | Complex theming |

### Dark Mode Pattern

| Element | Light | Dark |
|---------|-------|------|
| Background | `bg-white` | `dark:bg-zinc-900` |
| Text | `text-zinc-900` | `dark:text-zinc-100` |
| Borders | `border-zinc-200` | `dark:border-zinc-700` |

---

## 6. Modern Layout Patterns

### Flexbox Patterns

| Pattern | Classes |
|---------|---------|
| Center (both axes) | `flex items-center justify-center` |
| Vertical stack | `flex flex-col gap-4` |
| Horizontal row | `flex gap-4` |
| Space between | `flex justify-between items-center` |
| Wrap grid | `flex flex-wrap gap-4` |

### Grid Patterns

| Pattern | Classes |
|---------|---------|
| Auto-fit responsive | `grid grid-cols-[repeat(auto-fit,minmax(250px,1fr))]` |
| Asymmetric (Bento) | `grid grid-cols-3 grid-rows-2` with spans |
| Sidebar layout | `grid grid-cols-[auto_1fr]` |

> **Note:** Prefer asymmetric/Bento layouts over symmetric 3-column grids.

---

## 7. Modern Color System

### OKLCH vs RGB/HSL

| Format | Advantage |
|--------|-----------|
| **OKLCH** | Perceptually uniform, better for design |
| **HSL** | Intuitive hue/saturation |
| **RGB** | Legacy compatibility |

### Color Token Architecture

| Layer | Example | Purpose |
|-------|---------|---------|
| **Primitive** | `--blue-500` | Raw color values |
| **Semantic** | `--color-primary` | Purpose-based naming |
| **Component** | `--button-bg` | Component-specific |

---

## 8. Typography System

### Font Stack Pattern

| Type | Recommended |
|------|-------------|
| Sans | `'Inter', 'SF Pro', system-ui, sans-serif` |
| Mono | `'JetBrains Mono', 'Fira Code', monospace` |
| Display | `'Outfit', 'Poppins', sans-serif` |

### Type Scale

| Class | Size | Use |
|-------|------|-----|
| `text-xs` | 0.75rem | Labels, captions |
| `text-sm` | 0.875rem | Secondary text |
| `text-base` | 1rem | Body text |
| `text-lg` | 1.125rem | Lead text |
| `text-xl`+ | 1.25rem+ | Headings |

---

## 9. Animation & Transitions

### Built-in Animations

| Class | Effect |
|-------|--------|
| `animate-spin` | Continuous rotation |
| `animate-ping` | Attention pulse |
| `animate-pulse` | Subtle opacity pulse |
| `animate-bounce` | Bouncing effect |

### Transition Patterns

| Pattern | Classes |
|---------|---------|
| All properties | `transition-all duration-200` |
| Specific | `transition-colors duration-150` |
| With easing | `ease-out` or `ease-in-out` |
| Hover effect | `hover:scale-105 transition-transform` |

---

## 10. Component Extraction

### When to Extract

| Signal | Action |
|--------|--------|
| Same class combo 3+ times | Extract component |
| Complex state variants | Extract component |
| Design system element | Extract + document |

### Extraction Methods

| Method | Use When |
|--------|----------|
| **React/Vue component** | Dynamic, JS needed |
| **@apply in CSS** | Static, no JS needed |
| **Design tokens** | Reusable values |

---

## 11. Anti-Patterns

| Don't | Do |
|-------|-----|
| Arbitrary values everywhere | Use design system scale |
| `!important` | Fix specificity properly |
| Inline `style=` | Use utilities |
| Duplicate long class lists | Extract component |
| Mix v3 config with v4 | Migrate fully to CSS-first |
| Use `@apply` heavily | Prefer components |

---

## 12. Performance Principles

| Principle | Implementation |
|-----------|----------------|
| **Purge unused** | Automatic in v4 |
| **Avoid dynamism** | No template string classes |
| **Use Oxide** | Default in v4, 10x faster |
| **Cache builds** | CI/CD caching |

---

## 13. Custom Utilities & Variants (v4)

### Creating Custom Utilities

```css
/* Simple utility */
@utility content-auto {
  content-visibility: auto;
}

/* Functional utility with theme values */
@utility tab-* {
  tab-size: --value(--tab-size-*);
}

/* Usage */
<div class="content-auto tab-4">...</div>
```

### Creating Custom Variants

```css
/* Custom variant for data attributes */
@custom-variant theme-midnight (&:where([data-theme="midnight"] *));

/* Usage */
<div class="bg-white theme-midnight:bg-slate-900">...</div>
```

### Using @layer for Custom CSS

```css
@import "tailwindcss";

@layer base {
  h1 { font-size: var(--text-3xl); font-weight: var(--font-weight-bold); }
  h2 { font-size: var(--text-2xl); font-weight: var(--font-weight-semibold); }
}

@layer components {
  .btn {
    @apply inline-flex items-center justify-center px-4 py-2 rounded-lg;
    @apply font-medium transition-colors duration-200;
    @apply focus:outline-none focus-visible:ring-2 focus-visible:ring-offset-2;
  }

  .btn-primary {
    @apply bg-primary text-white hover:bg-primary-hover;
  }

  .card {
    background: var(--color-surface);
    border-radius: var(--radius-lg);
    padding: var(--spacing-6);
    box-shadow: var(--shadow-md);
  }
}
```

---

## 14. Arbitrary Values & CSS Variables

### Arbitrary Values (Escape Hatch)

```html
<!-- One-off values -->
<div class="w-[350px] bg-[#1da1f2] text-[22px]">Custom</div>

<!-- With calc() -->
<div class="max-h-[calc(100vh-4rem)]">Dynamic height</div>

<!-- Arbitrary properties -->
<div class="[mask-type:luminance]">Mask effect</div>

<!-- Underscore for spaces -->
<div class="grid-cols-[1fr_500px_2fr]">Grid template</div>
```

### CSS Variables in Classes

```html
<!-- Reference theme variables -->
<div class="bg-(--color-brand-mint)">Uses theme var</div>

<!-- In arbitrary values -->
<div class="p-[var(--spacing-custom)]">Custom spacing</div>
```

---

## 15. Modern Layout Patterns (2026)

### Bento Grid Layout

```html
<div class="grid grid-cols-4 grid-rows-3 gap-4">
  <div class="col-span-2 row-span-2 bg-primary">Featured</div>
  <div class="bg-surface">Item 1</div>
  <div class="bg-surface">Item 2</div>
  <div class="col-span-2 bg-surface">Wide item</div>
</div>
```

### Auto-fit Responsive Grid

```html
<div class="grid grid-cols-[repeat(auto-fit,minmax(280px,1fr))] gap-6">
  <!-- Cards auto-wrap based on container -->
</div>
```

### Sticky Header + Scrollable Content

```html
<div class="h-screen flex flex-col">
  <header class="sticky top-0 z-10 bg-white/80 backdrop-blur-sm">Nav</header>
  <main class="flex-1 overflow-auto">Content</main>
  <footer class="mt-auto">Footer</footer>
</div>
```

### Container Query Card

```html
<div class="@container">
  <article class="flex flex-col @md:flex-row gap-4 p-4">
    <img class="w-full @md:w-48 rounded-lg" src="..." alt="" />
    <div class="flex flex-col gap-2">
      <h3 class="text-lg @lg:text-xl font-semibold">Title</h3>
      <p class="text-sm text-gray-600 @md:text-base">Description</p>
    </div>
  </article>
</div>
```

---

## 16. Companies Using Tailwind

OpenAI, Shopify, Vercel, Reddit, NASA/JPL, Midjourney, The Verge, and 500K+ projects.

---

## Quick Reference Card

### Breakpoints
| Prefix | Min Width | Target |
|--------|-----------|--------|
| (none) | 0 | Mobile base |
| `sm:` | 640px | Large phone |
| `md:` | 768px | Tablet |
| `lg:` | 1024px | Laptop |
| `xl:` | 1280px | Desktop |
| `2xl:` | 1536px | Large desktop |

### Container Queries
| Prefix | Container Width |
|--------|-----------------|
| `@sm` | 320px+ |
| `@md` | 448px+ |
| `@lg` | 512px+ |
| `@xl` | 576px+ |

### Common Patterns Cheatsheet
```
Center:         flex items-center justify-center
Stack:          flex flex-col gap-4
Row:            flex gap-4 items-center
Between:        flex justify-between items-center
Grid 3-col:     grid grid-cols-1 md:grid-cols-3 gap-6
Full height:    min-h-screen flex flex-col
Truncate:       truncate / line-clamp-2 / line-clamp-3
Focus ring:     focus:outline-none focus-visible:ring-2
Dark mode:      bg-white dark:bg-gray-900
Responsive:     text-sm md:text-base lg:text-lg
```

---

## 17. Legacy Version Reference (Tailwind v3)

### Diferencias Clave v3 vs v4

| Aspecto | v3 (Legacy) | v4.1 (Current) |
|---------|-------------|----------------|
| Configuración | `tailwind.config.js` | CSS `@theme` directive |
| Colores | HSL/RGB | **OKLCH** |
| Import | `@tailwind base/components/utilities` | `@import "tailwindcss"` |
| Plugins | JavaScript | CSS `@utility`, `@custom-variant` |
| Content | Manual en config | Detección automática |
| Engine | JIT | Oxide (10x más rápido) |

### Tailwind v3 Configuration (Legacy)

```javascript
// tailwind.config.js (v3)
/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  darkMode: 'class', // o 'media'
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          100: '#dbeafe',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
          900: '#1e3a8a',
        },
        brand: {
          mint: '#10b981',
          coral: '#f97316',
        },
      },
      fontFamily: {
        sans: ['Inter', 'system-ui', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      spacing: {
        '18': '4.5rem',
        '112': '28rem',
        '128': '32rem',
      },
      borderRadius: {
        '4xl': '2rem',
      },
      animation: {
        'fade-in': 'fadeIn 0.3s ease-out',
        'slide-up': 'slideUp 0.3s ease-out',
      },
      keyframes: {
        fadeIn: {
          '0%': { opacity: '0' },
          '100%': { opacity: '1' },
        },
        slideUp: {
          '0%': { transform: 'translateY(10px)', opacity: '0' },
          '100%': { transform: 'translateY(0)', opacity: '1' },
        },
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
    require('@tailwindcss/typography'),
    require('@tailwindcss/aspect-ratio'),
  ],
}
```

### CSS Entry Point v3

```css
/* globals.css (v3) */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  html {
    @apply scroll-smooth;
  }
  body {
    @apply bg-white text-gray-900 dark:bg-gray-900 dark:text-white;
  }
}

@layer components {
  .btn {
    @apply inline-flex items-center justify-center px-4 py-2 rounded-lg;
    @apply font-medium transition-colors duration-200;
    @apply focus:outline-none focus:ring-2 focus:ring-offset-2;
  }
  .btn-primary {
    @apply bg-primary-600 text-white hover:bg-primary-700;
    @apply focus:ring-primary-500;
  }
  .card {
    @apply bg-white dark:bg-gray-800 rounded-lg shadow-md p-6;
  }
}

@layer utilities {
  .text-balance {
    text-wrap: balance;
  }
}
```

### Dark Mode v3

```javascript
// tailwind.config.js
module.exports = {
  darkMode: 'class', // Requiere clase .dark en html/body
  // ...
}
```

```html
<!-- HTML v3 -->
<html class="dark">
  <body class="bg-white dark:bg-gray-900 text-gray-900 dark:text-white">
    <!-- Contenido -->
  </body>
</html>
```

### PostCSS Config v3

```javascript
// postcss.config.js (v3)
module.exports = {
  plugins: {
    tailwindcss: {},
    autoprefixer: {},
  },
}
```

### Plugins v3 (JavaScript)

```javascript
// Plugin personalizado v3
const plugin = require('tailwindcss/plugin')

module.exports = {
  plugins: [
    plugin(function({ addUtilities, addComponents, theme }) {
      addUtilities({
        '.content-auto': {
          'content-visibility': 'auto',
        },
      })
      addComponents({
        '.card-hover': {
          '@apply transition-transform duration-200 hover:scale-105': {},
        },
      })
    }),
  ],
}
```

### Migración v3 → v4

```css
/* ANTES (v3 - tailwind.config.js) */
module.exports = {
  theme: {
    extend: {
      colors: {
        primary: '#3b82f6',
      },
    },
  },
}

/* CSS v3 */
@tailwind base;
@tailwind components;
@tailwind utilities;

/* DESPUÉS (v4 - solo CSS) */
@import "tailwindcss";

@theme {
  --color-primary: oklch(0.62 0.21 255);
}
```

### Detectar Versión en Proyecto

```bash
# Ver versión instalada
npm list tailwindcss

# En package.json
"devDependencies": {
  "tailwindcss": "^3.4.0"  // v3
  "tailwindcss": "^4.1.0"  // v4
}

# Indicador: si existe tailwind.config.js → v3
# Indicador: si usa @import "tailwindcss" → v4
```

### Cuándo Usar Cada Versión

| Escenario | Recomendación |
|-----------|---------------|
| Proyecto nuevo | **v4** - CSS-first, más rápido |
| Proyecto existente v3 | Mantener v3 hasta migración planificada |
| Muchos plugins JS | v3 - Más ecosistema de plugins |
| Necesitas OKLCH | **v4** - Soporte nativo |
| Container queries | **v4** - Soporte nativo |

---

> **Remember:** Tailwind v4.1 is CSS-first. Use `@theme` for tokens, `@import "tailwindcss"` to start, and embrace container queries for component-level responsive design. No config file needed!
>
> **Para proyectos v3:** Usa `tailwind.config.js` con JavaScript y `@tailwind` directives. La migración a v4 es opcional pero recomendada para nuevos proyectos.

---

## Patrones de Animación y Estado en Dashboards Oscuros

### `animate-ping` para Indicadores de Estado Activo
```html
<!-- Pulse ring rojo-verde para estado online/offline -->
<span class="relative inline-flex w-2 h-2">
  <!-- El ring anima solo cuando está activo -->
  <span class="absolute inline-flex h-full w-full rounded-full
    bg-green-400 opacity-60 animate-ping" />
  <!-- El punto real siempre visible -->
  <span class="relative inline-flex rounded-full h-2 w-2
    bg-green-500 shadow-[0_0_8px] shadow-green-500/80" />
</span>
```
> **Clave:** El span exterior necesita `relative inline-flex` para que `animate-ping` (absolute) se posicione bien.

### `animate-pulse` para Skeleton Loading Inline
Usar para valores que están cargando (async):
```html
<!-- Número que todavía no han llegado -->
<span class="h-3 w-20 rounded bg-white/5 animate-pulse"></span>

<!-- Card completa en skeleton -->
<div class="h-24 rounded-xl bg-white/5 animate-pulse"></div>

<!-- Skeleton de texto (ancho variable para parecer real) -->
<div class="space-y-2">
  <div class="h-3 w-3/4 rounded bg-white/5 animate-pulse"></div>
  <div class="h-3 w-1/2 rounded bg-white/5 animate-pulse"></div>
</div>
```

### Barra de Progreso con Framer Motion (`scaleX`)
Más performante que animar `width`:
```tsx
<motion.div
  initial={{ scaleX: 1 }}
  animate={{ scaleX: 0 }}
  transition={{ duration: 5, ease: 'linear' }}
  style={{ transformOrigin: 'left' }}
  className="absolute bottom-0 left-0 right-0 h-0.5 bg-green-400 opacity-50"
/>
```
> **Siempre** usar `style={{ transformOrigin: 'left' }}` para que la barra shrinkee p->d.
> `scaleX` no causa layout recalculation (solo composite layer).

### Ambient Gradient Blobs (Fondos Sutiles)
Blobs decorativos que no impactan el layout ni el rendimiento:
```html
<div class="fixed inset-0 pointer-events-none overflow-hidden" aria-hidden>
  <!-- Blob principal: esquina superior-izquierda, color temático -->
  <div class="absolute -top-40 -left-20 w-[500px] h-[500px]
    bg-purple-900/15 rounded-full blur-[140px]"></div>
  <!-- Blob secundario: esquina inferior-derecha -->
  <div class="absolute bottom-0 right-0 w-[400px] h-[400px]
    bg-blue-900/10 rounded-full blur-[120px]"></div>
</div>
```
**Reglas:**
- Opacidad: `/10` a `/20` máximo
- `blur-[100px]` o mayor para suavidad real
- `pointer-events-none` obligatorio
- `aria-hidden` para accesibilidad
- `fixed` + `overflow-hidden` en el wrapper para no desbordar el viewport

### Pills de Stats en Header
Badges inline de información compacta:
```html
<div class="flex items-center gap-4 mt-1">
  <span class="flex items-center gap-1.5 text-xs text-gray-500">
    <!-- icono 12x12 -->
    <svg class="w-3 h-3 text-purple-400">...</svg>
    <span class="text-green-400">2/3 activos</span>
  </span>
  <span class="text-gray-700">·</span>
  <span class="text-xs text-gray-500">940 skills</span>
</div>
```

### Hover Highlight en Líneas de Log
```html
<div class="font-mono text-xs">
  <!-- Cada línea con hover sutil --->
  <div class="px-2 py-0.5 hover:bg-white/[0.03] text-green-400 rounded">
    [SUCCESS] Servidor iniciado
  </div>
  <div class="px-2 py-0.5 hover:bg-white/[0.03] text-red-400 rounded">
    [ERROR] Conexión rechazada
  </div>
</div>
```
> `hover:bg-white/[0.03]` es la opacidad perfecta para hover en dark mode: visible pero no intrusivo.

