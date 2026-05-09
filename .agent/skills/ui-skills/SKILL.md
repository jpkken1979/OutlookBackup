---
name: ui-skills
type: feature
description: "Opinionated design constraints and principles for building consistent, accessible, performant user interfaces. Covers component design patterns, layout systems, typography scales, color accessibility, interaction patterns, and design system principles. Use when building component libraries, designing design systems, creating UI component patterns, ensuring accessibility (WCAG 2.1), standardizing component behavior across applications, or establishing design consistency."
source: "https://github.com/ibelick/ui-skills"
risk: safe
user-invocable: true
---

# UI Skills: Design System Constraints

Establish opinionated constraints that ensure consistency, accessibility, and performance across all UI components and interfaces.

## Core Principles

### 1. Constraint > Flexibility

Unlimited flexibility leads to inconsistency. **Constraints enable consistency.**

```
Bad:  "Buttons can be any size, color, and style"
       → 50 different buttons across codebase

Good: "Buttons: 3 sizes (sm, md, lg), 4 variants (primary, secondary, ghost, danger)"
       → Predictable, maintainable, accessible
```

### 2. Design System as Contract

The design system is a **contract between designers and engineers**.

| Component | Variants | Sizes | States | Documentation |
|-----------|----------|-------|--------|----------------|
| Button | primary, secondary, ghost, danger | sm, md, lg | default, hover, active, disabled | ✓ Storybook |
| Input | text, password, search, email | sm, md, lg | default, focus, error, disabled | ✓ Props table |
| Card | elevated, flat, outlined | — | default, hover | ✓ Example patterns |

## Design System Architecture

### Layer 1: Tokens (Base Values)

Foundation values for all components:

```
Colors:
  primary-50, primary-100, ..., primary-900
  (9 shades provide flexibility without chaos)

Typography:
  h1 (32px/1.2), h2 (28px/1.3), ..., body (16px/1.5)
  (Predefined scales, not arbitrary sizes)

Spacing:
  0, 2px, 4px, 8px, 16px, 24px, 32px, 48px, 64px
  (8px grid system for alignment)

Shadows:
  shadow-sm, shadow-md, shadow-lg, shadow-xl
  (Semantic naming, not arbitrary values)
```

### Layer 2: Components (Reusable)

Combine tokens into reusable components:

```
Button component:
- Uses color tokens (primary, secondary, etc)
- Uses spacing tokens (padding)
- Uses typography tokens (font size, weight)
- Uses shadow tokens (elevation)
- Accepts props: variant, size, disabled, icon, loading
```

### Layer 3: Patterns (Combinations)

Combine components into patterns:

```
Form Patterns:
- Text Input + Label + Error message
- Select + Label + Helper text
- Checkbox Group + Legend
- Radio Group + Legend

Page Patterns:
- Header + Sidebar + Main Content
- Card Grid (3 columns on desktop, 1 on mobile)
- Breadcrumb + Title + Content
```

## Component API Design

### Define Clear Props

```typescript
// Bad: Too many props, unclear behavior
Button(children, onClick, style, class, variant, disabled, ...)

// Good: Semantic props with clear constraints
Button {
  children: ReactNode,          // What to display
  variant: 'primary' | 'secondary' | 'ghost',  // Visual style
  size: 'sm' | 'md' | 'lg',     // Physical size
  disabled?: boolean,            // Interaction state
  onClick?: () => void,          // Action
  icon?: ReactNode,              // Optional leading icon
}
```

### Document Constraints

For each component, document:

```
### Button

#### Variants
- **primary**: Action buttons, CTAs (use sparingly)
- **secondary**: Alternative actions
- **ghost**: Low-emphasis actions

#### Sizes
- **sm**: Inline, tight spaces (28px height)
- **md**: Standard, default (40px height)
- **lg**: Prominent, mobile-friendly (48px height)

#### When to Use
- Primary: "Submit", "Save", "Create"
- Secondary: "Cancel", "Clear", "Reset"
- Ghost: "Help", "Learn More", "View Details"

#### Don't Do This
- ❌ Use primary for "Cancel"
- ❌ Mix more than 2 buttons on same row
- ❌ Button with long text (wrap with ellipsis)
```

## Accessibility Constraints

### Color: WCAG Contrast Minimum

All text must meet WCAG AA standards (4.5:1 for normal text):

```
✓ White text on primary-600 blue: 6.5:1 (passes)
✗ White text on primary-300 light blue: 2:1 (fails)

Rule: Use tokens tested for contrast, don't create custom colors
```

### Focus States: Always Visible

```css
/* Always visible focus indicator */
button:focus {
  outline: 2px solid primary-600;
  outline-offset: 2px;
}

/* Not this:  */
button:focus {
  outline: none;  /* ❌ Breaks keyboard navigation */
}
```

### Keyboard Navigation

Every interactive element must be keyboard accessible:

```
✓ Can Tab to it
✓ Can activate with Space/Enter
✓ Can close modals with Escape
✓ Arrow keys work for lists/tabs
✓ Focus trap in modals
```

## Performance Constraints

### Bundle Size Limits

Define max sizes by component type:

```
Component type       | Max bundle | Reasoning
--------------------|------------|-------------------
Button               | 2KB        | Used everywhere
Modal                | 10KB       | Loaded on-demand
Charts               | 50KB       | Advanced feature
Date picker          | 15KB       | Specialized
```

### Rendering Performance

```
✓ Memoize functional components
✓ Avoid layout thrashing (read then write)
✓ Lazy load heavy components
✗ Don't render 1000+ items without virtualization
```

## Responsive Design Constraints

### Breakpoint System

Define semantic breakpoints:

```
Mobile-first approach:
- Default: 320px+ (mobile)
- sm: 640px+ (small screens)
- md: 1024px+ (tablet)
- lg: 1280px+ (desktop)
- xl: 1920px+ (large desktop)

Rule: Design mobile-first, add layout at larger screens
```

### Touch vs. Click

```
Touch targets (mobile):
- Minimum 44x44px (Apple), 48x48px (Android)
- 8px+ spacing between targets

Click targets (desktop):
- Minimum 32x32px acceptable
- Can be closer together
```

## Component Quality Checklist

For each new component:

- [ ] Has 3+ documented variants
- [ ] Props are semantic and constrained
- [ ] WCAG AA contrast tested
- [ ] Keyboard navigation works
- [ ] Responsive at all breakpoints
- [ ] Mobile touch target size
- [ ] Focus states visible
- [ ] Example usage in Storybook
- [ ] TypeScript types defined
- [ ] Bundle size measured
- [ ] Performance benchmark included
- [ ] Accessibility scan passed

## Anti-Patterns to Avoid

| Anti-Pattern | Why | What to Do |
|--------------|-----|-----------|
| Custom colors per page | Breaks consistency | Use color tokens |
| Arbitrary padding/margins | Layout misalignment | Use spacing tokens (8px grid) |
| Many button variants | Confusing choices | Limit to 3-4 variants |
| No focus states | Keyboard inaccessible | Always define :focus styles |
| Untested responsive | Broken on some devices | Test on 3+ device sizes |

## Iterating on Constraints

Constraints should evolve:

1. **Month 1**: Define initial tokens, 10 core components
2. **Month 2**: Collect feedback, refine tokens
3. **Month 3**: Add 10 more components
4. **Month 6**: Comprehensive design system v1.0
5. **Quarterly**: Review usage, update constraints

Monitor:
- How often designers request new variants (want to add = constraint too tight)
- How often variants unused (want to remove = constraint too loose)

See [UI Skills repository](https://github.com/ibelick/ui-skills) for design tokens reference and component library templates.
