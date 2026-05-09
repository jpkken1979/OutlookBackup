---
name: ui-ux-superskill
type: feature
description: "Sistema definitivo de diseño UI/UX. Cubre arquetipos estéticos, design tokens W3C, componentes React+Tailwind v4, accesibilidad WCAG 2.2, animaciones, dark mode, CRO, y validación visual. Usa cuando el usuario pida diseño, UI, UX, componentes, landing pages, dashboards, formularios, temas, o cualquier trabajo visual/frontend."
allowed-tools: "Read, Write, Edit, Glob, Grep, Bash, Agent"
---

# UI/UX Superskill — Sistema Definitivo de Diseño

> Unifica 50+ skills fragmentados en un sistema cohesivo de 10 módulos.
> Aplica a todo trabajo de diseño visual, componentes, layouts y experiencia de usuario.

---

## MÓDULO 1: FUNDACIÓN DE DISEÑO

### 1.1 Arquetipos estéticos (elegir ANTES de codear)

Cada proyecto debe tener UN arquetipo definido. No mezclar.

| Arquetipo | Fuentes | Radius | Shadows | Motion |
|---|---|---|---|---|
| **Editorial** | Playfair Display + Source Serif | 0-2px | Sutil | Fade elegante |
| **Swiss/International** | Helvetica Neue + Suisse | 0px | Ninguna | Slide preciso |
| **Brutalist** | JetBrains Mono + Space Mono | 0px | Hard/offset | Glitch/snap |
| **Minimalist** | Inter (excepción) + DM Sans | 8-12px | Soft difusa | Micro fade |
| **Maximalist** | Bricolage Grotesque + Clash | Mix | Layered | Bouncy/spring |
| **Retro-Futuristic** | Orbitron + Share Tech | 4px | Neon glow | Scan/sweep |
| **Organic** | Fraunces + Lora | 16-24px | Warm | Flow/morph |
| **Industrial** | IBM Plex + Roboto Mono | 2px | Sharp | Mechanical |
| **Art Deco** | Poiret One + Tenor Sans | 0px | Gold accent | Reveal |
| **Lo-Fi/Zine** | Courier Prime + Permanent Marker | 0px | Cut-out | Jitter |

**Lista negra**: NO usar Inter, Roboto, Open Sans, Lato, Arial como default sin justificación.

### 1.2 Design tokens (W3C DTCG)

3 capas obligatorias:

```css
/* 1. Brand tokens (primitivos) */
--color-blue-500: oklch(0.55 0.22 250);
--space-unit: 4px;
--font-display: 'Playfair Display', serif;

/* 2. Semantic tokens */
--color-primary: var(--color-blue-500);
--color-destructive: var(--color-red-500);
--space-sm: calc(var(--space-unit) * 2);  /* 8px */
--space-md: calc(var(--space-unit) * 4);  /* 16px */
--space-lg: calc(var(--space-unit) * 8);  /* 32px */

/* 3. Component tokens */
--button-bg: var(--color-primary);
--button-radius: var(--radius-md);
--button-padding: var(--space-sm) var(--space-md);
```

**Escala de spacing**: 4, 8, 12, 16, 20, 24, 32, 40, 48, 64, 80, 96
**Escala tipográfica** (ratio 1.25): 12, 14, 16, 20, 24, 30, 36, 48, 60, 72

### 1.3 Color — OKLCH

```css
/* Paleta con OKLCH para uniformidad perceptual */
--color-primary: oklch(0.55 0.22 250);
--color-primary-hover: oklch(0.50 0.22 250);
--color-primary-foreground: oklch(0.98 0.01 250);

/* Dark mode: NO invertir 1:1, reducir brillo y desaturar */
.dark {
  --color-primary: oklch(0.65 0.18 250);
  --background: oklch(0.15 0.01 250);
  --foreground: oklch(0.90 0.01 250); /* NO blanco puro */
}
```

Contraste mínimo: 4.5:1 texto normal, 3:1 componentes grandes, 7:1 AAA.

### 1.4 Tipografía

```css
/* Fluid typography con clamp() */
--text-sm: clamp(0.8rem, 0.75rem + 0.25vw, 0.875rem);
--text-base: clamp(1rem, 0.9rem + 0.5vw, 1.125rem);
--text-lg: clamp(1.125rem, 1rem + 0.75vw, 1.5rem);
--text-xl: clamp(1.5rem, 1.2rem + 1.5vw, 2.25rem);
--text-4xl: clamp(2.25rem, 1.5rem + 3.75vw, 4.5rem);
```

- Headings: weight 700-900, line-height 1.1-1.2, letter-spacing -0.02em
- Body: weight 400, line-height 1.5-1.7, max-width 65-75ch

---

## MÓDULO 2: COMPONENTES REACT + TAILWIND v4

### 2.1 Arquitectura

```tsx
// CVA para variantes type-safe
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils"; // clsx + tailwind-merge

const buttonVariants = cva(
  "inline-flex items-center justify-center rounded-md font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 disabled:pointer-events-none disabled:opacity-50",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:bg-primary/90",
        destructive: "bg-destructive text-destructive-foreground hover:bg-destructive/90",
        outline: "border border-input bg-background hover:bg-accent",
        ghost: "hover:bg-accent hover:text-accent-foreground",
        link: "text-primary underline-offset-4 hover:underline",
      },
      size: {
        sm: "h-9 px-3 text-sm",
        default: "h-10 px-4",
        lg: "h-11 px-8 text-lg",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: { variant: "default", size: "default" },
  }
);
```

### 2.2 Matriz de 10 estados (obligatorio por componente)

| # | Estado | Qué mostrar | ARIA |
|---|---|---|---|
| 1 | Default | Estado normal | — |
| 2 | Hover | Feedback visual sutil | — |
| 3 | Active/Pressed | `scale(0.97)` momentáneo | — |
| 4 | Focus | Ring visible (`:focus-visible`) | — |
| 5 | Disabled | Opacity 50%, cursor not-allowed | `aria-disabled` |
| 6 | Loading | Spinner/skeleton | `aria-busy="true"` |
| 7 | Error | Border destructive + mensaje | `aria-invalid`, `aria-describedby` |
| 8 | Success | Checkmark + color green | `aria-live="polite"` |
| 9 | Empty | Ilustración + CTA | — |
| 10 | Skeleton | Pulse shimmer placeholder | `aria-hidden="true"` |

### 2.3 Compound components (no monolitos)

```tsx
// MAL: <Card title="..." subtitle="..." image="..." actions={[...]} />
// BIEN:
<Card>
  <Card.Header>
    <Card.Title>Título</Card.Title>
    <Card.Description>Subtítulo</Card.Description>
  </Card.Header>
  <Card.Content>...</Card.Content>
  <Card.Footer>...</Card.Footer>
</Card>
```

### 2.4 Tailwind v4

```css
/* @theme en CSS, no tailwind.config.js */
@theme {
  --color-primary: oklch(0.55 0.22 250);
  --color-background: oklch(0.98 0.01 250);
  --radius-md: 0.5rem;
  --animate-fade-in: fade-in 0.3s ease-out;
}
```

- Container queries: `@container` en vez de solo media queries
- NO usar `@apply` anidado
- Dark mode: `dark:` variant con class strategy

---

## MÓDULO 3: RESPONSIVE MOBILE-FIRST

### Estrategia

```css
/* Default = mobile (375px). Escalar hacia arriba. */
.card { padding: var(--space-sm); }

@media (min-width: 768px) { .card { padding: var(--space-md); } }
@media (min-width: 1024px) { .card { padding: var(--space-lg); } }
```

### Fluid layouts

```css
/* Grid auto-responsive */
.grid-auto {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(min(300px, 100%), 1fr));
  gap: var(--space-md);
}
```

### Touch targets

- Mínimo: **44×44px** (iOS) / **48×48dp** (Android)
- Spacing entre targets: mínimo 8px
- No hover-only interactions en mobile

### Testear siempre en 3 viewports: 375px, 768px, 1440px

---

## MÓDULO 4: ACCESIBILIDAD (WCAG 2.2 AA)

### Checklist obligatorio

- [ ] HTML semántico (`<nav>`, `<main>`, `<article>`, `<aside>`)
- [ ] Jerarquía de headings sin saltos (h1→h2→h3)
- [ ] ARIA roles/labels en interactivos
- [ ] `aria-live` en contenido dinámico
- [ ] Skip link al inicio de la página
- [ ] Focus management en modals (focus trap + restore)
- [ ] `:focus-visible` ring en todos los interactivos
- [ ] Keyboard completo (Tab, Shift+Tab, Enter, Space, Escape, Arrows)
- [ ] Color NO como único indicador (icon + text + color)
- [ ] Alt text en imágenes
- [ ] Labels en form inputs (NO placeholder-only)
- [ ] `prefers-reduced-motion` respetado
- [ ] `prefers-color-scheme` respetado
- [ ] Zoom 200% funcional sin overflow

### Testing

```bash
# Auditoría automatizada
npx axe-core-cli http://localhost:5173
# O en Playwright
npx playwright test --grep accessibility
```

---

## MÓDULO 5: ANIMACIONES Y MOTION

### Principios

- **Propósito**: informar → orientar → deleitar (en ese orden)
- **Duración**: 150-300ms micro, 300-500ms transiciones de página
- **Easing**: `ease-out` entradas, `ease-in` salidas, `ease-in-out` loops

### Patrones

| Patrón | Cuándo | CSS/Framer |
|---|---|---|
| Fade in | Page load | `opacity 0→1, 200ms ease-out` |
| Stagger | Listas | `animation-delay: calc(var(--i) * 50ms)` |
| Scale tap | Click/tap | `scale(0.97) 100ms` |
| Slide up | Toasts, modals | `translateY(100%→0) 300ms ease-out` |
| Skeleton pulse | Loading | `opacity 0.5→1 loop 1.5s` |
| Hover lift | Cards | `translateY(-2px) + shadow` |

### Framer Motion (Nexus)

```ts
// SIEMPRE en archivos separados *Variants.ts
export const cardVariants = {
  hidden: { opacity: 0, y: 20 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.3 } },
};
```

### Reduced motion

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    transition-duration: 0.01ms !important;
  }
}
```

---

## MÓDULO 6: LIGHT MODE, DARK MODE Y THEMING — ZERO LEAKS

> **Regla absoluta**: NINGÚN color puede estar hardcodeado. TODO pasa por tokens semánticos.
> Si cambias de tema y un solo pixel no cambia, es un bug.

### 6.1 ThemeProvider — 3 modos (light / dark / system)

```tsx
const ThemeContext = createContext<{ theme: string; setTheme: (t: string) => void }>();

function ThemeProvider({ children }: { children: React.ReactNode }) {
  const [theme, setTheme] = useState(() =>
    localStorage.getItem("theme") || "system"
  );

  useEffect(() => {
    const root = document.documentElement;
    const systemDark = window.matchMedia("(prefers-color-scheme: dark)").matches;
    const isDark = theme === "dark" || (theme === "system" && systemDark);
    root.classList.toggle("dark", isDark);
    root.style.colorScheme = isDark ? "dark" : "light";
    localStorage.setItem("theme", theme);
  }, [theme]);

  return <ThemeContext value={{ theme, setTheme }}>{children}</ThemeContext>;
}
```

### 6.2 Prevenir Flash of Wrong Theme (FOWT)

Script bloqueante en `<head>` ANTES de cualquier CSS:

```html
<script>
  const t = localStorage.getItem('theme') ||
    (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light');
  document.documentElement.classList.toggle('dark', t === 'dark');
  document.documentElement.style.colorScheme = t === 'dark' ? 'dark' : 'light';
</script>
```

### 6.3 Tokens semánticos completos — Light Y Dark

**TODOS estos tokens son obligatorios.** Si falta uno, habrá fuga de color.

```css
/* ===== LIGHT MODE ===== */
:root {
  /* Superficies */
  --color-background:       #f8f9fa;  /* Gris sutil, NO blanco puro */
  --color-surface:          #ffffff;  /* Cards, paneles elevados */
  --color-surface-raised:   #ffffff;  /* Popovers, dropdowns */
  --color-surface-sunken:   #f1f3f5; /* Sidebars, áreas empotradas */
  --color-surface-overlay:  rgba(0, 0, 0, 0.4); /* Backdrop de modals */

  /* Texto */
  --color-foreground:       #111827;  /* Texto principal — 7:1 contraste */
  --color-text-secondary:   #4b5563;  /* Labels, subtítulos — 4.5:1 */
  --color-text-muted:       #9ca3af;  /* Hints, timestamps — 3:1 */
  --color-text-disabled:    #d1d5db;  /* Deshabilitado */
  --color-text-inverse:     #ffffff;  /* Texto sobre fondo oscuro */

  /* Bordes y líneas */
  --color-border:           #e5e7eb;  /* Bordes de cards, inputs */
  --color-border-strong:    #d1d5db;  /* Bordes con énfasis */
  --color-divider:          #f3f4f6;  /* Separadores sutiles, <hr> */

  /* Focus y ring */
  --color-ring:             #22d3ee;  /* cyan-400 — ring de focus */
  --color-ring-offset:      #ffffff;  /* Offset del ring */

  /* Sombras — pronunciadas en light mode (mecanismo de elevación) */
  --color-shadow:           rgba(0, 0, 0, 0.08);
  --color-shadow-strong:    rgba(0, 0, 0, 0.15);

  /* Elementos olvidables (CRÍTICOS para zero leaks) */
  --color-placeholder:      #9ca3af;  /* ::placeholder */
  --color-selection-bg:     oklch(0.77 0.19 200 / 0.30); /* ::selection */
  --color-selection-text:   inherit;
  --color-scrollbar-thumb:  #d1d5db;  /* ::-webkit-scrollbar-thumb */
  --color-scrollbar-track:  transparent;
  --color-skeleton:         #e5e7eb;  /* Loading skeleton base */
  --color-skeleton-shine:   #f3f4f6;  /* Loading skeleton shimmer */
  --color-backdrop:         rgba(0, 0, 0, 0.4); /* Modal overlay */
  --color-tooltip-bg:       #111827;  /* Tooltip fondo (invertido) */
  --color-tooltip-text:     #ffffff;  /* Tooltip texto */

  /* Inputs */
  --color-input-bg:         #ffffff;
  --color-input-border:     #d1d5db;
  --color-input-autofill:   #ffffff;  /* Chrome autofill hack */

  /* Iconos */
  --color-icon:             #6b7280;  /* gray-500 */
  --color-icon-hover:       #374151;  /* gray-700 */

  /* Status */
  --color-accent:           #22d3ee;  /* cyan-400 */
  --color-success:          #4ade80;  /* green-400 */
  --color-error:            #f87171;  /* red-400 */
  --color-warning:          #fbbf24;  /* amber-400 */
}

/* ===== DARK MODE ===== */
.dark {
  /* Superficies — elevar luminosidad por capas, NO invertir */
  --color-background:       #0a0a0a;
  --color-surface:          #141414;
  --color-surface-raised:   #1a1a1a;
  --color-surface-sunken:   #050505;
  --color-surface-overlay:  rgba(0, 0, 0, 0.7);

  /* Texto — NO blanco puro, reducir contraste ligeramente */
  --color-foreground:       #fafafa;  /* NO #ffffff */
  --color-text-secondary:   #a1a1aa;
  --color-text-muted:       #52525b;
  --color-text-disabled:    #3f3f46;
  --color-text-inverse:     #0a0a0a;

  /* Bordes — más visibles que en light (compensan sombras invisibles) */
  --color-border:           #27272a;
  --color-border-strong:    #3f3f46;
  --color-divider:          #1c1c1e;

  /* Focus y ring */
  --color-ring:             #22d3ee;
  --color-ring-offset:      #0a0a0a;

  /* Sombras — más fuertes o reemplazadas por bordes */
  --color-shadow:           rgba(0, 0, 0, 0.5);
  --color-shadow-strong:    rgba(0, 0, 0, 0.7);

  /* Elementos olvidables */
  --color-placeholder:      #52525b;
  --color-selection-bg:     oklch(0.77 0.19 200 / 0.25);
  --color-selection-text:   inherit;
  --color-scrollbar-thumb:  rgba(255, 255, 255, 0.08);
  --color-scrollbar-track:  transparent;
  --color-skeleton:         #27272a;
  --color-skeleton-shine:   #3f3f46;
  --color-backdrop:         rgba(0, 0, 0, 0.7);
  --color-tooltip-bg:       #fafafa;  /* Invertido vs light */
  --color-tooltip-text:     #0a0a0a;

  /* Inputs */
  --color-input-bg:         #1a1a1a;
  --color-input-border:     #3f3f46;
  --color-input-autofill:   #1a1a1a;

  /* Iconos */
  --color-icon:             #71717a;
  --color-icon-hover:       #a1a1aa;

  /* Status — mismos colores, funcionan en ambos modos */
  --color-accent:           #22d3ee;
  --color-success:          #4ade80;
  --color-error:            #f87171;
  --color-warning:          #fbbf24;
}
```

### 6.4 Estilos globales obligatorios (previenen fugas)

```css
/* Aplicar tokens a pseudo-elementos y elementos del browser */
html {
  background-color: var(--color-background); /* Previene scroll bounce leak */
}

::placeholder {
  color: var(--color-placeholder);
}

::selection {
  background-color: var(--color-selection-bg);
  color: var(--color-selection-text);
}

::-webkit-scrollbar { width: 8px; height: 8px; }
::-webkit-scrollbar-thumb {
  background: var(--color-scrollbar-thumb);
  border-radius: 4px;
}
::-webkit-scrollbar-track {
  background: var(--color-scrollbar-track);
}

/* Chrome autofill hack — SIN ESTO el autofill rompe dark mode */
input:-webkit-autofill,
input:-webkit-autofill:hover,
input:-webkit-autofill:focus,
textarea:-webkit-autofill {
  -webkit-text-fill-color: var(--color-foreground);
  -webkit-box-shadow: 0 0 0px 1000px var(--color-input-autofill) inset;
  transition: background-color 5000s ease-in-out 0s;
}

/* SVGs deben usar currentColor, no fill hardcodeado */
svg:not([fill]) { fill: currentColor; }
```

### 6.5 Reglas de diseño por modo

| Aspecto | Light Mode | Dark Mode |
|---|---|---|
| Fondo base | Gris sutil `#f8f9fa` (NO blanco puro) | Negro profundo `#0a0a0a` |
| Elevación | Sombras pronunciadas | Diferencia de luminosidad entre capas |
| Texto principal | `#111827` (gray-900) | `#fafafa` (NO `#ffffff`) |
| Bordes | Sutiles (gray-200) | Más visibles (zinc-800) |
| Sombras | `rgba(0,0,0,0.08)` — mecanismo principal | `rgba(0,0,0,0.5)` — secundario |
| Colores primarios | Saturación completa | Desaturar ligeramente |
| Tooltips | Fondo oscuro, texto claro | Fondo claro, texto oscuro (invertido) |
| Skeleton | gray-200 base | zinc-800 base |

### 6.6 Reglas prohibitivas (NUNCA hacer)

- **NUNCA** usar `#hex`, `rgb()`, `rgba()` directo en componentes — solo tokens
- **NUNCA** usar clases Tailwind atómicas de color (`bg-gray-900`, `text-white`) — solo semánticas (`bg-surface`, `text-foreground`)
- **NUNCA** usar `dark:` prefix en componentes — los tokens ya manejan ambos modos
- **NUNCA** usar `style={{ color: '...' }}` inline con valores hardcodeados
- **NUNCA** poner `fill="#000"` o `stroke="#fff"` en SVGs — usar `currentColor`
- **NUNCA** asumir que las sombras funcionan igual en dark mode

### 6.7 Auditoría anti-fugas

**Test Neón** — Importar temporalmente y TODO debe cambiar:

```css
/* debug-neon.css — si algo NO se pone neón, es una fuga */
:root, .light, .dark {
  --color-background: magenta !important;
  --color-surface: cyan !important;
  --color-foreground: lime !important;
  --color-border: yellow !important;
  --color-text-secondary: orange !important;
  --color-icon: blue !important;
}
```

**Grep anti-fugas** — Ejecutar antes de cada release:

```bash
# Hex colors en componentes (fuera de CSS de tokens)
grep -rn '#[0-9a-fA-F]\{3,8\}' --include='*.tsx' src/ | grep -v 'index.css\|tokens\|theme'

# Clases Tailwind con colores atómicos
grep -rnE '(bg|text|border|ring)-(white|black|gray|zinc|slate)-[0-9]' --include='*.tsx' src/

# Colores inline en style=
grep -rn 'style={{' --include='*.tsx' src/ | grep -iE 'color|background|border|shadow'
```

### 6.8 Checklist de cobertura de tema (VERIFICAR TODOS)

```
SUPERFICIES
[ ] html/body background
[ ] Card backgrounds
[ ] Sidebar / navigation background
[ ] Modal/dialog background
[ ] Dropdown/popover background
[ ] Tooltip background (INVERTIDO entre modos)
[ ] Toast/notification background
[ ] Skeleton loading shimmer

TEXTO
[ ] Headings (foreground)
[ ] Body text (foreground)
[ ] Labels, subtítulos (text-secondary)
[ ] Hints, timestamps (text-muted)
[ ] Links
[ ] Disabled text
[ ] Placeholder text (::placeholder)
[ ] Error/success messages

BORDES Y LÍNEAS
[ ] Card borders
[ ] Input borders
[ ] Table dividers
[ ] <hr> / Separator
[ ] Sidebar dividers

INTERACTIVOS
[ ] Focus ring + ring offset
[ ] Hover backgrounds
[ ] Active/pressed states
[ ] ::selection highlight
[ ] Scrollbar thumb + track
[ ] Input autofill (Chrome hack)

GRÁFICOS
[ ] SVG fill (currentColor)
[ ] SVG stroke
[ ] Icon colors + hover
[ ] Badge backgrounds

EFECTOS
[ ] Box shadows (diferente intensidad por modo)
[ ] Modal backdrop/overlay
[ ] Skeleton pulse
[ ] Gradient colors (si hay)
```

---

## MÓDULO 7: CRO (CONVERSION RATE OPTIMIZATION)

### Patrones de conversión

- **1 CTA primario** por viewport (color dominante, tamaño grande)
- **F-pattern / Z-pattern** para landing pages
- **Social proof** cerca del CTA (testimonios, logos, números)
- **Progressive disclosure**: no abrumar al usuario
- **Friction audit**: cada campo extra reduce conversión 7-10%

### Form optimization

- Inline validation (no post-submit)
- `autocomplete` attributes en todos los campos
- Smart defaults y valores prefilled
- Progress indicator en multi-step
- Error recovery sin perder datos

### Performance = CRO

- LCP < 2.5s, FID < 100ms, CLS < 0.1
- Above-the-fold priorizado
- Lazy loading below-the-fold
- Imágenes WebP/AVIF con `srcset` responsive

---

## MÓDULO 8: VALIDACIÓN VISUAL

### Checklist pre-delivery (5 puntos)

1. **Coherencia**: todos los elementos siguen el arquetipo elegido
2. **Responsive**: funciona en 375px, 768px, 1440px
3. **Accesibilidad**: contraste, keyboard, ARIA
4. **Estados**: los 10 estados cubiertos por componente
5. **Performance**: sin layout shifts, imágenes optimizadas

### Auditoría de 15 dimensiones

1. Visual hierarchy — ¿Queda claro qué es lo más importante?
2. Spacing & rhythm — ¿Consistente con la escala de tokens?
3. Typography — ¿Jerarquía clara, legible, fluid?
4. Color — ¿Paleta coherente, contraste WCAG?
5. Alignment & grid — ¿Todo alineado a la grilla?
6. Components — ¿CVA variants, compound, estados?
7. Iconography — ¿Estilo consistente, tamaño uniforme?
8. Motion — ¿Proporcional, con propósito?
9. Empty states — ¿Diseñados, no en blanco?
10. Loading states — ¿Skeleton, no spinner genérico?
11. Error states — ¿Informativos, con recovery?
12. Dark mode — ¿Correcto, no invertido 1:1?
13. Density — ¿Apropiada para el contexto?
14. Responsiveness — ¿3 viewports verificados?
15. Accessibility — ¿WCAG 2.2 AA completo?

### Anti-patterns (lista negra)

- Colores hardcodeados (sin tokens)
- Spacing inconsistente
- Missing focus states
- Placeholder-only labels
- Hover-only interactions
- Missing empty/error/loading states
- `@apply` anidado en Tailwind
- Boolean prop proliferation
- Layouts centrados genéricos sin personalidad
- Fondos sólidos planos sin textura/atmósfera

---

## MÓDULO 9: CIENCIA COGNITIVA APLICADA

| Ley | Aplicación práctica |
|---|---|
| **Fitts** | Botones grandes para acciones frecuentes, cerca del cursor |
| **Hick** | Máximo 5-7 opciones visibles |
| **Miller** | Chunking en grupos de 3-5 |
| **Jakob** | Seguir patrones que los usuarios ya conocen |
| **Gestalt** | Proximity, similarity para agrupar elementos |
| **Peak-End** | Optimizar el momento clave y el final |
| **Von Restorff** | El CTA debe ser visualmente diferente |

### Perceived performance

- Skeleton screens > spinners > nada
- Optimistic UI (mostrar resultado antes de confirmación)
- Progress bars con velocidad no-lineal
- Staggered content loading

---

## MÓDULO 10: PROCESO DE USO

### Flujo completo

```
1. Elegir arquetipo estético (Módulo 1.1)
   ↓
2. Generar design tokens (Módulo 1.2-1.4)
   ↓
3. Configurar ThemeProvider + dark mode (Módulo 6)
   ↓
4. Crear componentes con CVA + 10-state matrix (Módulo 2)
   ↓
5. Implementar layout responsive mobile-first (Módulo 3)
   ↓
6. Agregar animaciones con motion variants (Módulo 5)
   ↓
7. Optimizar CRO si es landing/producto (Módulo 7)
   ↓
8. Auditar con 15 dimensiones (Módulo 8)
   ↓
9. Validar accesibilidad con axe-core (Módulo 4)
   ↓
10. Quality gate final → Entregar
```

### Regla de oro

> Antes de escribir cualquier componente, DEFINIR: arquetipo + tokens + estados.
> Un componente sin sus 10 estados definidos está incompleto.
> Un diseño sin auditoría de 15 dimensiones no se entrega.
