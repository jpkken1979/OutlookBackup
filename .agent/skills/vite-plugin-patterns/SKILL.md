---
name: vite-plugin-patterns
type: feature
description: Vite plugin development patterns for virtual modules, transforms, dev helpers, and build-time extensions. Use when designing a Vite plugin, choosing plugin hooks, implementing virtual modules, or structuring reusable build-time behavior in a Vite ecosystem.
---

# Vite Plugin Patterns

## Purpose

Provide structured guidance for designing and implementing Vite plugins with clear hook usage and maintainable extension patterns.

## When to Use

- Building a custom Vite plugin
- Choosing between Vite plugin hook patterns
- Implementing virtual modules or transforms
- Designing reusable build-time extensions
- Reviewing plugin structure for maintainability

## Workflow

1. Define the plugin’s job precisely
2. Choose the minimum set of hooks needed
3. Decide whether the plugin is dev-only, build-only, or hybrid
4. Implement the pattern with explicit boundaries
5. Validate behavior with realistic build/dev scenarios

## Critical Patterns

- Use the smallest viable hook surface
- Keep plugin intent explicit: transform, resolve, virtual module, or helper
- Avoid mixing unrelated plugin responsibilities
- Validate generated output and developer ergonomics together

## Examples

### Virtual module pattern

```typescript
export default function virtualModulePlugin() {
  const virtualModuleId = 'virtual-module'
  const resolvedId = '\0' + virtualModuleId

  return {
    name: 'virtual-module-plugin',
    resolveId(id: string) {
      if (id === virtualModuleId) return resolvedId
    },
    load(id: string) {
      if (id === resolvedId) {
        return 'export const value = "generated";'
      }
    }
  }
}
```

### Pattern request

```json
{
  "pattern_type": "virtual_module",
  "framework": "react",
  "include_typescript": true
}
```

## Resources

- Vite plugin hook selection
- Virtual module and transform patterns
- Dev-only vs build-only plugin design
- Testing and packaging considerations for plugins

## Validation

- Verify the selected hooks are sufficient and minimal
- Confirm generated output is correct in dev/build modes
- Check plugin ergonomics for consumers
- Validate plugin boundaries and maintenance cost
