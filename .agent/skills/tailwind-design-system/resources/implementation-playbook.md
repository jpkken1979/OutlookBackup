# Tailwind Design System Implementation Playbook

This file contains detailed patterns, checklists, and code samples referenced by the skill.

# Tailwind Design System

Build production-ready design systems with Tailwind CSS, including design tokens, component variants, responsive patterns, and accessibility.

## When to Use This Skill

- Creating a component library with Tailwind
- Implementing design tokens and theming
- Building responsive and accessible components
- Standardizing UI patterns across a codebase
- Migrating to or extending Tailwind CSS
- Setting up dark mode and color schemes

## Core Concepts

### 1. Design Token Hierarchy

```
Brand Tokens (abstract)
    └── Semantic Tokens (purpose)
        └── Component Tokens (specific)

Example:
    blue-500 → primary → button-bg
```

### 2. Component Architecture

```
Base styles → Variants → Sizes → States → Overrides
```

## Quick Start (Tailwind CSS v4.1 - 2026)

### Installation

```bash
npm install tailwindcss @tailwindcss/vite
```

### Vite Configuration

```typescript
// vite.config.ts
import { defineConfig } from 'vite'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [tailwindcss()],
})
```

### CSS-First Theme Configuration

```css
/* globals.css - Tailwind v4 CSS-first approach */
@import "tailwindcss";

/* Custom dark mode variant (class-based) */
@custom-variant dark (&:where(.dark, .dark *));

/* Design System Theme */
@theme {
  /* ============================================
     COLORS - Using OKLCH for perceptual uniformity
     ============================================ */

  /* Semantic Colors */
  --color-background: oklch(1 0 0);
  --color-foreground: oklch(0.145 0.02 250);

  --color-primary: oklch(0.205 0.02 250);
  --color-primary-foreground: oklch(0.985 0 0);

  --color-secondary: oklch(0.97 0.01 250);
  --color-secondary-foreground: oklch(0.205 0.02 250);

  --color-muted: oklch(0.97 0.01 250);
  --color-muted-foreground: oklch(0.556 0.02 250);

  --color-accent: oklch(0.97 0.01 250);
  --color-accent-foreground: oklch(0.205 0.02 250);

  --color-destructive: oklch(0.577 0.245 27);
  --color-destructive-foreground: oklch(0.985 0 0);

  --color-success: oklch(0.696 0.17 142);
  --color-warning: oklch(0.769 0.188 70);
  --color-info: oklch(0.623 0.214 255);

  --color-border: oklch(0.922 0.01 250);
  --color-ring: oklch(0.708 0.165 254);

  /* Card/Surface colors */
  --color-card: oklch(1 0 0);
  --color-card-foreground: oklch(0.145 0.02 250);

  /* ============================================
     TYPOGRAPHY
     ============================================ */
  --font-sans: 'Inter', ui-sans-serif, system-ui, sans-serif;
  --font-mono: 'JetBrains Mono', ui-monospace, monospace;
  --font-display: 'Outfit', var(--font-sans);

  /* ============================================
     SPACING (8pt Grid System)
     ============================================ */
  --spacing-0: 0;
  --spacing-px: 1px;
  --spacing-0\.5: 0.125rem;
  --spacing-1: 0.25rem;
  --spacing-2: 0.5rem;
  --spacing-3: 0.75rem;
  --spacing-4: 1rem;
  --spacing-5: 1.25rem;
  --spacing-6: 1.5rem;
  --spacing-8: 2rem;
  --spacing-10: 2.5rem;
  --spacing-12: 3rem;
  --spacing-16: 4rem;
  --spacing-20: 5rem;
  --spacing-24: 6rem;

  /* ============================================
     BORDER RADIUS
     ============================================ */
  --radius-none: 0;
  --radius-sm: calc(var(--radius) - 4px);
  --radius-md: calc(var(--radius) - 2px);
  --radius-lg: var(--radius);
  --radius-xl: calc(var(--radius) + 4px);
  --radius-2xl: calc(var(--radius) + 8px);
  --radius-full: 9999px;
  --radius: 0.5rem;

  /* ============================================
     SHADOWS
     ============================================ */
  --shadow-xs: 0 1px 2px 0 oklch(0 0 0 / 0.05);
  --shadow-sm: 0 1px 3px 0 oklch(0 0 0 / 0.1), 0 1px 2px -1px oklch(0 0 0 / 0.1);
  --shadow-md: 0 4px 6px -1px oklch(0 0 0 / 0.1), 0 2px 4px -2px oklch(0 0 0 / 0.1);
  --shadow-lg: 0 10px 15px -3px oklch(0 0 0 / 0.1), 0 4px 6px -4px oklch(0 0 0 / 0.1);
  --shadow-xl: 0 20px 25px -5px oklch(0 0 0 / 0.1), 0 8px 10px -6px oklch(0 0 0 / 0.1);

  /* ============================================
     ANIMATIONS
     ============================================ */
  --animate-accordion-down: accordion-down 0.2s ease-out;
  --animate-accordion-up: accordion-up 0.2s ease-out;
  --animate-fade-in: fade-in 0.3s ease-out;
  --animate-fade-out: fade-out 0.2s ease-in;
  --animate-slide-in-from-top: slide-in-from-top 0.3s ease-out;
  --animate-slide-in-from-bottom: slide-in-from-bottom 0.3s ease-out;

  @keyframes accordion-down {
    from { height: 0; }
    to { height: var(--radix-accordion-content-height); }
  }

  @keyframes accordion-up {
    from { height: var(--radix-accordion-content-height); }
    to { height: 0; }
  }

  @keyframes fade-in {
    from { opacity: 0; }
    to { opacity: 1; }
  }

  @keyframes fade-out {
    from { opacity: 1; }
    to { opacity: 0; }
  }

  @keyframes slide-in-from-top {
    from { transform: translateY(-100%); }
    to { transform: translateY(0); }
  }

  @keyframes slide-in-from-bottom {
    from { transform: translateY(100%); }
    to { transform: translateY(0); }
  }
}

/* Dark Mode Overrides */
@layer base {
  .dark {
    --color-background: oklch(0.145 0.02 250);
    --color-foreground: oklch(0.985 0 0);

    --color-primary: oklch(0.985 0 0);
    --color-primary-foreground: oklch(0.205 0.02 250);

    --color-secondary: oklch(0.269 0.02 250);
    --color-secondary-foreground: oklch(0.985 0 0);

    --color-muted: oklch(0.269 0.02 250);
    --color-muted-foreground: oklch(0.708 0.02 250);

    --color-accent: oklch(0.269 0.02 250);
    --color-accent-foreground: oklch(0.985 0 0);

    --color-destructive: oklch(0.396 0.141 25);
    --color-destructive-foreground: oklch(0.985 0 0);

    --color-border: oklch(0.269 0.02 250);
    --color-ring: oklch(0.839 0.05 250);

    --color-card: oklch(0.145 0.02 250);
    --color-card-foreground: oklch(0.985 0 0);

    /* Adjusted shadows for dark mode */
    --shadow-sm: 0 1px 3px 0 oklch(0 0 0 / 0.3);
    --shadow-md: 0 4px 6px -1px oklch(0 0 0 / 0.4);
  }
}
```

> **Note:** Tailwind v4 uses CSS-first configuration via `@theme`. No `tailwind.config.js` needed!

## Patterns

### Pattern 1: CVA (Class Variance Authority) Components

```typescript
// components/ui/button.tsx
import { cva, type VariantProps } from 'class-variance-authority'
import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

const buttonVariants = cva(
  // Base styles
  'inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50',
  {
    variants: {
      variant: {
        default: 'bg-primary text-primary-foreground hover:bg-primary/90',
        destructive: 'bg-destructive text-destructive-foreground hover:bg-destructive/90',
        outline: 'border border-input bg-background hover:bg-accent hover:text-accent-foreground',
        secondary: 'bg-secondary text-secondary-foreground hover:bg-secondary/80',
        ghost: 'hover:bg-accent hover:text-accent-foreground',
        link: 'text-primary underline-offset-4 hover:underline',
      },
      size: {
        default: 'h-10 px-4 py-2',
        sm: 'h-9 rounded-md px-3',
        lg: 'h-11 rounded-md px-8',
        icon: 'h-10 w-10',
      },
    },
    defaultVariants: {
      variant: 'default',
      size: 'default',
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : 'button'
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = 'Button'

export { Button, buttonVariants }

// Usage
<Button variant="destructive" size="lg">Delete</Button>
<Button variant="outline">Cancel</Button>
<Button asChild><Link href="/home">Home</Link></Button>
```

### Pattern 2: Compound Components

```typescript
// components/ui/card.tsx
import { cn } from '@/lib/utils'
import { forwardRef } from 'react'

const Card = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn(
        'rounded-lg border bg-card text-card-foreground shadow-sm',
        className
      )}
      {...props}
    />
  )
)
Card.displayName = 'Card'

const CardHeader = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('flex flex-col space-y-1.5 p-6', className)}
      {...props}
    />
  )
)
CardHeader.displayName = 'CardHeader'

const CardTitle = forwardRef<HTMLHeadingElement, React.HTMLAttributes<HTMLHeadingElement>>(
  ({ className, ...props }, ref) => (
    <h3
      ref={ref}
      className={cn('text-2xl font-semibold leading-none tracking-tight', className)}
      {...props}
    />
  )
)
CardTitle.displayName = 'CardTitle'

const CardDescription = forwardRef<HTMLParagraphElement, React.HTMLAttributes<HTMLParagraphElement>>(
  ({ className, ...props }, ref) => (
    <p
      ref={ref}
      className={cn('text-sm text-muted-foreground', className)}
      {...props}
    />
  )
)
CardDescription.displayName = 'CardDescription'

const CardContent = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div ref={ref} className={cn('p-6 pt-0', className)} {...props} />
  )
)
CardContent.displayName = 'CardContent'

const CardFooter = forwardRef<HTMLDivElement, React.HTMLAttributes<HTMLDivElement>>(
  ({ className, ...props }, ref) => (
    <div
      ref={ref}
      className={cn('flex items-center p-6 pt-0', className)}
      {...props}
    />
  )
)
CardFooter.displayName = 'CardFooter'

export { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter }

// Usage
<Card>
  <CardHeader>
    <CardTitle>Account</CardTitle>
    <CardDescription>Manage your account settings</CardDescription>
  </CardHeader>
  <CardContent>
    <form>...</form>
  </CardContent>
  <CardFooter>
    <Button>Save</Button>
  </CardFooter>
</Card>
```

### Pattern 3: Form Components

```typescript
// components/ui/input.tsx
import { forwardRef } from 'react'
import { cn } from '@/lib/utils'

export interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  error?: string
}

const Input = forwardRef<HTMLInputElement, InputProps>(
  ({ className, type, error, ...props }, ref) => {
    return (
      <div className="relative">
        <input
          type={type}
          className={cn(
            'flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background file:border-0 file:bg-transparent file:text-sm file:font-medium placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50',
            error && 'border-destructive focus-visible:ring-destructive',
            className
          )}
          ref={ref}
          aria-invalid={!!error}
          aria-describedby={error ? `${props.id}-error` : undefined}
          {...props}
        />
        {error && (
          <p
            id={`${props.id}-error`}
            className="mt-1 text-sm text-destructive"
            role="alert"
          >
            {error}
          </p>
        )}
      </div>
    )
  }
)
Input.displayName = 'Input'

// components/ui/label.tsx
import { cva, type VariantProps } from 'class-variance-authority'

const labelVariants = cva(
  'text-sm font-medium leading-none peer-disabled:cursor-not-allowed peer-disabled:opacity-70'
)

const Label = forwardRef<HTMLLabelElement, React.LabelHTMLAttributes<HTMLLabelElement>>(
  ({ className, ...props }, ref) => (
    <label ref={ref} className={cn(labelVariants(), className)} {...props} />
  )
)
Label.displayName = 'Label'

// Usage with React Hook Form
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import * as z from 'zod'

const schema = z.object({
  email: z.string().email('Invalid email address'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
})

function LoginForm() {
  const { register, handleSubmit, formState: { errors } } = useForm({
    resolver: zodResolver(schema),
  })

  return (
    <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
      <div className="space-y-2">
        <Label htmlFor="email">Email</Label>
        <Input
          id="email"
          type="email"
          {...register('email')}
          error={errors.email?.message}
        />
      </div>
      <div className="space-y-2">
        <Label htmlFor="password">Password</Label>
        <Input
          id="password"
          type="password"
          {...register('password')}
          error={errors.password?.message}
        />
      </div>
      <Button type="submit" className="w-full">Sign In</Button>
    </form>
  )
}
```

### Pattern 4: Responsive Grid System

```typescript
// components/ui/grid.tsx
import { cn } from '@/lib/utils'
import { cva, type VariantProps } from 'class-variance-authority'

const gridVariants = cva('grid', {
  variants: {
    cols: {
      1: 'grid-cols-1',
      2: 'grid-cols-1 sm:grid-cols-2',
      3: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-3',
      4: 'grid-cols-1 sm:grid-cols-2 lg:grid-cols-4',
      5: 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-5',
      6: 'grid-cols-2 sm:grid-cols-3 lg:grid-cols-6',
    },
    gap: {
      none: 'gap-0',
      sm: 'gap-2',
      md: 'gap-4',
      lg: 'gap-6',
      xl: 'gap-8',
    },
  },
  defaultVariants: {
    cols: 3,
    gap: 'md',
  },
})

interface GridProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof gridVariants> {}

export function Grid({ className, cols, gap, ...props }: GridProps) {
  return (
    <div className={cn(gridVariants({ cols, gap, className }))} {...props} />
  )
}

// Container component
const containerVariants = cva('mx-auto w-full px-4 sm:px-6 lg:px-8', {
  variants: {
    size: {
      sm: 'max-w-screen-sm',
      md: 'max-w-screen-md',
      lg: 'max-w-screen-lg',
      xl: 'max-w-screen-xl',
      '2xl': 'max-w-screen-2xl',
      full: 'max-w-full',
    },
  },
  defaultVariants: {
    size: 'xl',
  },
})

interface ContainerProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof containerVariants> {}

export function Container({ className, size, ...props }: ContainerProps) {
  return (
    <div className={cn(containerVariants({ size, className }))} {...props} />
  )
}

// Usage
<Container>
  <Grid cols={4} gap="lg">
    {products.map((product) => (
      <ProductCard key={product.id} product={product} />
    ))}
  </Grid>
</Container>
```

### Pattern 5: Animation Utilities

```typescript
// lib/animations.ts - Tailwind CSS Animate utilities
import { cn } from './utils'

export const fadeIn = 'animate-in fade-in duration-300'
export const fadeOut = 'animate-out fade-out duration-300'
export const slideInFromTop = 'animate-in slide-in-from-top duration-300'
export const slideInFromBottom = 'animate-in slide-in-from-bottom duration-300'
export const slideInFromLeft = 'animate-in slide-in-from-left duration-300'
export const slideInFromRight = 'animate-in slide-in-from-right duration-300'
export const zoomIn = 'animate-in zoom-in-95 duration-300'
export const zoomOut = 'animate-out zoom-out-95 duration-300'

// Compound animations
export const modalEnter = cn(fadeIn, zoomIn, 'duration-200')
export const modalExit = cn(fadeOut, zoomOut, 'duration-200')
export const dropdownEnter = cn(fadeIn, slideInFromTop, 'duration-150')
export const dropdownExit = cn(fadeOut, 'slide-out-to-top', 'duration-150')

// components/ui/dialog.tsx
import * as DialogPrimitive from '@radix-ui/react-dialog'

const DialogOverlay = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Overlay>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Overlay>
>(({ className, ...props }, ref) => (
  <DialogPrimitive.Overlay
    ref={ref}
    className={cn(
      'fixed inset-0 z-50 bg-black/80',
      'data-[state=open]:animate-in data-[state=closed]:animate-out',
      'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
      className
    )}
    {...props}
  />
))

const DialogContent = forwardRef<
  React.ElementRef<typeof DialogPrimitive.Content>,
  React.ComponentPropsWithoutRef<typeof DialogPrimitive.Content>
>(({ className, children, ...props }, ref) => (
  <DialogPortal>
    <DialogOverlay />
    <DialogPrimitive.Content
      ref={ref}
      className={cn(
        'fixed left-[50%] top-[50%] z-50 grid w-full max-w-lg translate-x-[-50%] translate-y-[-50%] gap-4 border bg-background p-6 shadow-lg',
        'data-[state=open]:animate-in data-[state=closed]:animate-out',
        'data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0',
        'data-[state=closed]:zoom-out-95 data-[state=open]:zoom-in-95',
        'data-[state=closed]:slide-out-to-left-1/2 data-[state=closed]:slide-out-to-top-[48%]',
        'data-[state=open]:slide-in-from-left-1/2 data-[state=open]:slide-in-from-top-[48%]',
        'sm:rounded-lg',
        className
      )}
      {...props}
    >
      {children}
    </DialogPrimitive.Content>
  </DialogPortal>
))
```

### Pattern 6: Dark Mode Implementation

```typescript
// providers/ThemeProvider.tsx
'use client'

import { createContext, useContext, useEffect, useState } from 'react'

type Theme = 'dark' | 'light' | 'system'

interface ThemeProviderProps {
  children: React.ReactNode
  defaultTheme?: Theme
  storageKey?: string
}

interface ThemeContextType {
  theme: Theme
  setTheme: (theme: Theme) => void
  resolvedTheme: 'dark' | 'light'
}

const ThemeContext = createContext<ThemeContextType | undefined>(undefined)

export function ThemeProvider({
  children,
  defaultTheme = 'system',
  storageKey = 'theme',
}: ThemeProviderProps) {
  const [theme, setTheme] = useState<Theme>(defaultTheme)
  const [resolvedTheme, setResolvedTheme] = useState<'dark' | 'light'>('light')

  useEffect(() => {
    const stored = localStorage.getItem(storageKey) as Theme | null
    if (stored) setTheme(stored)
  }, [storageKey])

  useEffect(() => {
    const root = window.document.documentElement
    root.classList.remove('light', 'dark')

    let resolved: 'dark' | 'light'

    if (theme === 'system') {
      resolved = window.matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
    } else {
      resolved = theme
    }

    root.classList.add(resolved)
    setResolvedTheme(resolved)
  }, [theme])

  const value = {
    theme,
    setTheme: (newTheme: Theme) => {
      localStorage.setItem(storageKey, newTheme)
      setTheme(newTheme)
    },
    resolvedTheme,
  }

  return (
    <ThemeContext.Provider value={value}>{children}</ThemeContext.Provider>
  )
}

export const useTheme = () => {
  const context = useContext(ThemeContext)
  if (!context) throw new Error('useTheme must be used within ThemeProvider')
  return context
}

// components/ThemeToggle.tsx
import { Moon, Sun } from 'lucide-react'
import { useTheme } from '@/providers/ThemeProvider'

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme()

  return (
    <Button
      variant="ghost"
      size="icon"
      onClick={() => setTheme(resolvedTheme === 'dark' ? 'light' : 'dark')}
    >
      <Sun className="h-5 w-5 rotate-0 scale-100 transition-all dark:-rotate-90 dark:scale-0" />
      <Moon className="absolute h-5 w-5 rotate-90 scale-0 transition-all dark:rotate-0 dark:scale-100" />
      <span className="sr-only">Toggle theme</span>
    </Button>
  )
}
```

## Utility Functions

```typescript
// lib/utils.ts
import { type ClassValue, clsx } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

// Focus ring utility
export const focusRing = cn(
  'focus-visible:outline-none focus-visible:ring-2',
  'focus-visible:ring-ring focus-visible:ring-offset-2'
)

// Disabled utility
export const disabled = 'disabled:pointer-events-none disabled:opacity-50'
```

## Best Practices

### Do's
- **Use CSS variables** - Enable runtime theming
- **Compose with CVA** - Type-safe variants
- **Use semantic colors** - `primary` not `blue-500`
- **Forward refs** - Enable composition
- **Add accessibility** - ARIA attributes, focus states

### Don'ts
- **Don't use arbitrary values** - Extend theme instead
- **Don't nest @apply** - Hurts readability
- **Don't skip focus states** - Keyboard users need them
- **Don't hardcode colors** - Use semantic tokens
- **Don't forget dark mode** - Test both themes

## Resources

- [Tailwind CSS Documentation](https://tailwindcss.com/docs)
- [CVA Documentation](https://cva.style/docs)
- [shadcn/ui](https://ui.shadcn.com/)
- [Radix Primitives](https://www.radix-ui.com/primitives)
