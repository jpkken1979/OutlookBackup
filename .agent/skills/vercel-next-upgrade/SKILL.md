---
name: vercel-next-upgrade
type: feature
description: >
---
  Upgrade Next.js applications between versions using codemods, dependency
  updates, and migration guides. Handles breaking changes, deprecated APIs,
  and configuration migrations. Use when upgrading Next.js to a newer version.
source: Vercel Labs
---

# Next.js Version Upgrade

Systematic workflow for upgrading Next.js applications between major versions.

## Upgrade Workflow

### Step 1: Assess Current State
```bash
# Check current versions
npx next --version
node --version
npm ls next react react-dom

# Check for known issues
npx next info
```

### Step 2: Update Dependencies
```bash
# Upgrade Next.js and React
npm install next@latest react@latest react-dom@latest

# Or with specific version
npm install next@15 react@19 react-dom@19

# Update TypeScript types
npm install -D @types/react@latest @types/react-dom@latest
```

### Step 3: Run Codemods
```bash
# Run all codemods for target version
npx @next/codemod@latest upgrade

# Run specific codemod
npx @next/codemod@latest <codemod-name>

# Dry run to preview changes
npx @next/codemod@latest upgrade --dry
```

### Step 4: Review Breaking Changes
Check each version's migration guide and address breaking changes.

### Step 5: Test
```bash
# Build to catch compile errors
npm run build

# Run tests
npm test

# Start dev server and manually verify
npm run dev
```

## Major Version Migration Notes

### Next.js 13 → 14
- **Minimum Node.js**: 18.17+
- **App Router stable**: Migrate from `pages/` to `app/`
- **Server Actions stable**: Remove `experimental.serverActions`
- **`next export`**: Replace with `output: 'export'` in config

### Next.js 14 → 15
- **Async Request APIs**: `cookies()`, `headers()`, `params`, `searchParams` are now async
- **Caching changes**: `fetch` no longer cached by default
- **React 19**: Support for Server Components, Actions, `use()` hook
- **Turbopack**: Default for dev (`next dev --turbopack`)

```tsx
// BEFORE (Next.js 14)
export default function Page({ params }: { params: { id: string } }) {
  const { id } = params;
}

// AFTER (Next.js 15)
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
}
```

```tsx
// BEFORE (Next.js 14) — cookies sync
import { cookies } from 'next/headers';
const cookieStore = cookies();
const token = cookieStore.get('token');

// AFTER (Next.js 15) — cookies async
import { cookies } from 'next/headers';
const cookieStore = await cookies();
const token = cookieStore.get('token');
```

### Next.js 15 → 16
- **`use cache` directive**: Replaces `unstable_cache`
- **`cacheLife()` / `cacheTag()`**: New cache control APIs
- **PPR (Partial Prerendering)**: Static + dynamic in one route
- **React Compiler**: Automatic memoization (no more manual `useMemo`/`useCallback`)

## Available Codemods

| Codemod | Description |
|---------|-------------|
| `next-image-to-legacy-image` | Rename `next/image` to `next/legacy/image` |
| `next-image-experimental` | Migrate to new Image component |
| `built-in-next-font` | Migrate `@next/font` to `next/font` |
| `metadata-to-viewport-export` | Move viewport from metadata to separate export |
| `next-async-request-api` | Convert sync request APIs to async |
| `next-dynamic-access-named-export` | Convert `next/dynamic` default import |

## Common Issues After Upgrade

| Issue | Fix |
|-------|-----|
| Type errors with async params | Add `Promise<>` wrapper and `await` |
| Hydration mismatch | Check Server/Client component boundaries |
| Missing data (cache) | Explicitly opt-in to caching with `cache: 'force-cache'` |
| Build failures | Check `next.config.js` for deprecated options |
| Module not found | Clear `.next` directory: `rm -rf .next` |

## Checklist
- [ ] Dependencies updated (next, react, react-dom, types)
- [ ] Codemods applied
- [ ] Breaking changes addressed
- [ ] `next.config.js` updated
- [ ] Build passes (`npm run build`)
- [ ] Tests pass
- [ ] Dev server works correctly
- [ ] Production deployment verified
