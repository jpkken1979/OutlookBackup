---
name: vercel-next-cache-components
type: feature
description: >
---
  Next.js 16 Cache Components with PPR (Partial Prerendering), use cache
  directive, cacheLife(), cacheTag(), and updateTag(). Migration from
  unstable_cache. Use when implementing caching strategies in Next.js 15/16
  or migrating from older caching patterns.
source: Vercel Labs
---

# Next.js Cache Components

Modern caching patterns for Next.js 15+ with the `use cache` directive and Partial Prerendering.

## Core Concepts

### Partial Prerendering (PPR)
PPR combines static and dynamic content in a single route:
- Static shell is prerendered at build time
- Dynamic holes are streamed at request time
- No configuration needed per-route — just use Suspense boundaries

```tsx
// app/page.tsx — Static shell with dynamic holes
import { Suspense } from 'react';

export default function Page() {
  return (
    <div>
      <StaticHeader />           {/* Prerendered */}
      <Suspense fallback={<Skeleton />}>
        <DynamicContent />       {/* Streamed at request time */}
      </Suspense>
      <StaticFooter />           {/* Prerendered */}
    </div>
  );
}
```

### `use cache` Directive
Mark functions or components as cacheable:

```tsx
// Cache a data-fetching function
async function getProducts() {
  'use cache';
  const res = await fetch('https://api.example.com/products');
  return res.json();
}

// Cache a component
async function ProductList() {
  'use cache';
  const products = await getProducts();
  return <ul>{products.map(p => <li key={p.id}>{p.name}</li>)}</ul>;
}
```

### `cacheLife()` — Control Cache Duration
```tsx
import { cacheLife } from 'next/cache';

async function getProducts() {
  'use cache';
  cacheLife('hours');  // Predefined profile
  // OR custom:
  // cacheLife({ revalidate: 3600, stale: 300, expire: 86400 });
  return fetch('https://api.example.com/products').then(r => r.json());
}
```

**Predefined profiles:**
| Profile | Stale | Revalidate | Expire |
|---------|-------|------------|--------|
| `'seconds'` | 0 | 1s | 60s |
| `'minutes'` | 5m | 1m | 1h |
| `'hours'` | 5m | 1h | 1d |
| `'days'` | 5m | 1d | 1w |
| `'weeks'` | 5m | 1w | 30d |
| `'max'` | 5m | 30d | ∞ |

### `cacheTag()` — Tag Cache Entries
```tsx
import { cacheTag } from 'next/cache';

async function getProduct(id: string) {
  'use cache';
  cacheTag(`product-${id}`, 'products');
  return fetch(`https://api.example.com/products/${id}`).then(r => r.json());
}
```

### `revalidateTag()` — Invalidate by Tag
```tsx
import { revalidateTag } from 'next/cache';

// In a Server Action or Route Handler
export async function updateProduct(id: string, data: FormData) {
  'use server';
  await db.products.update(id, data);
  revalidateTag(`product-${id}`);  // Invalidate specific product
  revalidateTag('products');        // Invalidate all products
}
```

## Migration from `unstable_cache`

```tsx
// BEFORE (deprecated)
import { unstable_cache } from 'next/cache';
const getCachedData = unstable_cache(
  async (id) => fetchData(id),
  ['data-key'],
  { revalidate: 3600, tags: ['data'] }
);

// AFTER (Next.js 15+)
import { cacheLife, cacheTag } from 'next/cache';
async function getCachedData(id: string) {
  'use cache';
  cacheLife('hours');
  cacheTag('data', `data-${id}`);
  return fetchData(id);
}
```

## Best Practices

1. **Cache at the data level**, not the component level when possible
2. **Use specific tags** for granular invalidation (`product-123` not just `products`)
3. **Combine PPR + `use cache`** for optimal performance
4. **Set appropriate `cacheLife`** — don't over-cache dynamic data
5. **Use `revalidateTag`** in Server Actions for immediate updates
6. **Wrap dynamic parts in Suspense** for PPR to work correctly
