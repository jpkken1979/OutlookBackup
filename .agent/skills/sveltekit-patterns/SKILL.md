---
name: sveltekit-patterns
description: SvelteKit development patterns for file-based routing, SSR/SSG decisions, load functions, form actions, API routes, layouts, adapters, and error handling. Use when building or reviewing SvelteKit apps, debugging SvelteKit routing/data loading, designing +page/+layout/+server flows, or deciding between SSR, SSG, and client-side rendering.
type: feature
---

# SvelteKit Patterns

## Purpose

Provide practical SvelteKit guidance for routing, rendering strategy, server logic, forms, and project structure.

## When to Use

- Building a SvelteKit app from scratch
- Reviewing SvelteKit route/layout organization
- Designing SSR, SSG, or hybrid rendering flows
- Implementing `+page`, `+layout`, `+server`, or form actions
- Debugging data loading or endpoint behavior in SvelteKit

## Workflow

1. Confirm the rendering model: SSR, SSG, CSR, or hybrid
2. Define route structure and nested layouts
3. Decide what belongs in `load` functions versus API routes
4. Use form actions for server-side mutations when appropriate
5. Configure the adapter and deployment target explicitly
6. Verify error handling and data boundaries

## Critical Patterns

- Prefer explicit rendering decisions instead of defaulting blindly
- Keep route responsibilities clear: page rendering vs server endpoints
- Use form actions for server-driven mutations when they fit better than client fetches
- Treat adapters and deployment target as architecture decisions, not afterthoughts

## Examples

### Page rendering with server load

```svelte
<!-- +page.svelte -->
<script>
  export let data;
</script>

<h1>Usuarios</h1>
<ul>
  {#each data.users as user}
    <li>{user.name}</li>
  {/each}
</ul>
```

```typescript
// +page.server.ts
import type { PageServerLoad } from './$types';

export const load: PageServerLoad = async ({ fetch }) => {
  const response = await fetch('/api/users');
  const users = await response.json();
  return { users };
};
```

### API route

```typescript
// +server.ts
import { json } from '@sveltejs/kit';
import type { RequestHandler } from './$types';

export const GET: RequestHandler = async () => {
  const users = await db.query('SELECT * FROM users');
  return json(users);
};

export const POST: RequestHandler = async ({ request }) => {
  const data = await request.json();
  const user = await db.insert('users', data);
  return json(user, { status: 201 });
};
```

### Form action

```typescript
// +page.server.ts
import type { Actions } from './$types';

export const actions: Actions = {
  default: async ({ request }) => {
    const data = await request.formData();
    const email = data.get('email');
    // Process form...
    return { success: true };
  }
};
```

## Resources

- SvelteKit route structure: `+page`, `+layout`, `+server`
- Rendering models: SSR, SSG, CSR, hybrid
- Deployment adapters and environment-specific configuration

## Validation

- Check whether the chosen rendering model matches the product requirements
- Verify route boundaries and nested layout structure
- Confirm data loading and mutation flows are consistent
- Test error handling around server routes and form actions
