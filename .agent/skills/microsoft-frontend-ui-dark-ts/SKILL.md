---
name: microsoft-frontend-ui-dark-ts
description: "Componentes React/TypeScript con tema oscuro siguiendo patrones de Microsoft. Dark-first design, accesibilidad WCAG, CSS custom properties, tokens de diseño."
type: feature
---

# Microsoft Frontend UI — Dark Theme TypeScript

Patrones para componentes React/TypeScript con tema oscuro profesional.

## Principios de Diseño

1. **Dark-first** — Diseñar primero para tema oscuro, adaptar para claro.
2. **Accesibilidad** — WCAG 2.1 AA mínimo (contraste 4.5:1 texto, 3:1 UI).
3. **Tokens semánticos** — Usar tokens en vez de colores directos.
4. **Consistencia** — Sistema de diseño cohesivo.

## Design Tokens

```typescript
// tokens.ts
export const darkTokens = {
  // Backgrounds
  bgPrimary: "#1e1e1e",
  bgSecondary: "#252526",
  bgTertiary: "#2d2d2d",
  bgElevated: "#333333",
  bgHover: "#3e3e42",
  bgActive: "#094771",

  // Foregrounds
  fgPrimary: "#cccccc",
  fgSecondary: "#999999",
  fgMuted: "#6e6e6e",
  fgAccent: "#569cd6",
  fgError: "#f44747",
  fgWarning: "#cca700",
  fgSuccess: "#4ec9b0",

  // Borders
  borderDefault: "#3e3e42",
  borderFocus: "#007fd4",
  borderError: "#f44747",

  // Interactive
  buttonPrimary: "#0e639c",
  buttonPrimaryHover: "#1177bb",
  buttonSecondary: "#3a3d41",
  buttonSecondaryHover: "#45494e",
} as const;

export type TokenKey = keyof typeof darkTokens;
```

## CSS Custom Properties

```css
/* theme.css */
:root[data-theme="dark"] {
  --bg-primary: #1e1e1e;
  --bg-secondary: #252526;
  --bg-tertiary: #2d2d2d;
  --bg-elevated: #333333;
  --bg-hover: #3e3e42;

  --fg-primary: #cccccc;
  --fg-secondary: #999999;
  --fg-accent: #569cd6;

  --border-default: #3e3e42;
  --border-focus: #007fd4;

  --radius-sm: 2px;
  --radius-md: 4px;
  --radius-lg: 6px;

  --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
  --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.4);
  --shadow-lg: 0 8px 16px rgba(0, 0, 0, 0.5);
}
```

## Componentes Base

### Button

```tsx
import { type ButtonHTMLAttributes, forwardRef } from "react";

interface ButtonProps extends ButtonHTMLAttributes<HTMLButtonElement> {
  variant?: "primary" | "secondary" | "ghost" | "danger";
  size?: "sm" | "md" | "lg";
}

export const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ variant = "primary", size = "md", className, children, ...props }, ref) => {
    const baseStyles = "inline-flex items-center justify-center font-medium transition-colors " +
      "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[var(--border-focus)] " +
      "disabled:opacity-50 disabled:pointer-events-none rounded-[var(--radius-md)]";

    const variants = {
      primary: "bg-[var(--button-primary)] text-white hover:bg-[var(--button-primary-hover)]",
      secondary: "bg-[var(--bg-tertiary)] text-[var(--fg-primary)] hover:bg-[var(--bg-hover)]",
      ghost: "text-[var(--fg-secondary)] hover:bg-[var(--bg-hover)] hover:text-[var(--fg-primary)]",
      danger: "bg-[var(--fg-error)] text-white hover:opacity-90",
    };

    const sizes = {
      sm: "h-7 px-3 text-xs",
      md: "h-8 px-4 text-sm",
      lg: "h-10 px-6 text-base",
    };

    return (
      <button
        ref={ref}
        className={`${baseStyles} ${variants[variant]} ${sizes[size]} ${className ?? ""}`}
        {...props}
      >
        {children}
      </button>
    );
  }
);

Button.displayName = "Button";
```

### Input

```tsx
import { type InputHTMLAttributes, forwardRef } from "react";

interface InputProps extends InputHTMLAttributes<HTMLInputElement> {
  error?: string;
  label?: string;
}

export const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ error, label, className, ...props }, ref) => {
    return (
      <div className="flex flex-col gap-1">
        {label && (
          <label className="text-xs text-[var(--fg-secondary)]">{label}</label>
        )}
        <input
          ref={ref}
          className={`
            h-8 px-3 text-sm rounded-[var(--radius-md)]
            bg-[var(--bg-tertiary)] text-[var(--fg-primary)]
            border border-[var(--border-default)]
            focus:border-[var(--border-focus)] focus:outline-none
            placeholder:text-[var(--fg-muted)]
            ${error ? "border-[var(--fg-error)]" : ""}
            ${className ?? ""}
          `}
          {...props}
        />
        {error && (
          <span className="text-xs text-[var(--fg-error)]">{error}</span>
        )}
      </div>
    );
  }
);

Input.displayName = "Input";
```

## Accesibilidad

- `aria-label` en botones sin texto visible
- `role="alert"` para mensajes de error
- Focus indicators visibles (ring de 2px)
- Keyboard navigation completa (Tab, Enter, Escape)
- Contraste mínimo 4.5:1 para texto, 3:1 para elementos UI

## Recursos

- [Fluent UI](https://developer.microsoft.com/en-us/fluentui)
- [VS Code Theme Colors](https://code.visualstudio.com/api/references/theme-color)
- [WCAG 2.1 Guidelines](https://www.w3.org/WAI/WCAG21/quickref/)
