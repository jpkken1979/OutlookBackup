---
name: nextjs-app-router-patterns
description: "Expert guide to next.js app router patterns (v16.1.6 - 2026)."
type: feature
---

---
name: nextjs-app-router-patterns
description: Master Next.js 16+ App Router with Server Components, Partial Prerendering (PPR), Server Actions, and advanced caching. Use when building Next.js applications, implementing SSR/SSG, or optimizing React Server Components.
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
version: 16.1.6
updated: 2026-02-02
---

# Next.js App Router Patterns (v16.1.6 - 2026)

> Modern full-stack React framework with Server Components, Partial Prerendering, and zero-config deployment.

---

## 1. What's New in Next.js 16

### Key Changes from v14/15

| Feature | v14/15 | v16.1.6 (Current) |
|---------|--------|-------------------|
| **params/searchParams** | Sync objects | **Promises** (must await) |
| **Partial Prerendering** | Experimental | **Stable with `use cache`** |
| **Caching** | fetch options | **`use cache` directive** |
| **Cache Lifetime** | `revalidate` only | **`cacheLife()` profiles** |
| **Server Actions** | Basic | **Enhanced with useActionState** |
| **Image Optimization** | Good | **Better with `quality` presets** |
| **Turbopack** | Dev only | **Stable for production** |

### Breaking Changes

```typescript
// v14 (OLD) - params was sync
export default function Page({ params }) {
  const { id } = params // Direct access
}

// v16 (NEW) - params is a Promise
export default async function Page({
  params
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params // Must await
}
```

---

## 2. Core Concepts

### Rendering Modes

| Mode | Where | When to Use |
|------|-------|-------------|
| **Server Components** | Server only | Data fetching, secrets, heavy compute |
| **Client Components** | Browser | Interactivity, hooks, browser APIs |
| **Partial Prerendering** | Hybrid | Static shell + dynamic content |
| **Streaming** | Progressive | Large pages, slow data sources |

### File Conventions

```
app/
├── layout.tsx       # Shared UI wrapper (persists across navigation)
├── page.tsx         # Route UI (unique per route)
├── loading.tsx      # Loading UI (auto Suspense boundary)
├── error.tsx        # Error boundary
├── not-found.tsx    # 404 UI
├── route.ts         # API endpoint
├── template.tsx     # Re-mounted on navigation
├── default.tsx      # Parallel route fallback
└── opengraph-image.tsx  # Dynamic OG image
```

---

## 3. Partial Prerendering (PPR) - NEW

### What is PPR?

PPR combines static and dynamic rendering in a single route:
- **Static shell** renders at build time (instant)
- **Dynamic holes** stream in at request time (personalized)

### Enabling PPR

```typescript
// next.config.ts
import type { NextConfig } from 'next'

const config: NextConfig = {
  experimental: {
    ppr: 'incremental', // Enable per-route
  },
}

export default config
```

### Using `use cache` Directive

```typescript
// app/products/page.tsx
import { Suspense } from 'react'

// This function's result is cached
async function getProducts() {
  'use cache'
  const res = await fetch('https://api.example.com/products')
  return res.json()
}

// Static shell with dynamic user section
export default async function ProductsPage() {
  const products = await getProducts() // Cached (static)

  return (
    <div>
      <h1>Products</h1>
      <ProductGrid products={products} />

      {/* Dynamic content streams in */}
      <Suspense fallback={<CartSkeleton />}>
        <UserCart /> {/* Personalized, not cached */}
      </Suspense>
    </div>
  )
}
```

### Cache Lifetime Profiles

```typescript
import { cacheLife } from 'next/cache'

async function getProducts() {
  'use cache'
  cacheLife('hours') // Built-in profile

  return fetch('https://api.example.com/products').then(r => r.json())
}

// Built-in profiles:
// - 'seconds' (revalidate: 1)
// - 'minutes' (revalidate: 60)
// - 'hours' (revalidate: 3600)
// - 'days' (revalidate: 86400)
// - 'weeks' (revalidate: 604800)
// - 'max' (revalidate: Infinity)

// Custom profile in next.config.ts
experimental: {
  cacheLife: {
    products: {
      stale: 300,    // Serve stale for 5 min
      revalidate: 3600, // Revalidate every hour
      expire: 86400, // Max age 1 day
    }
  }
}
```

---

## 4. Server Components Pattern

```typescript
// app/products/page.tsx - Server Component (default)
import { Suspense } from 'react'
import { ProductList, ProductSkeleton } from '@/components/products'

interface Props {
  searchParams: Promise<{ category?: string; page?: string }>
}

export default async function ProductsPage({ searchParams }: Props) {
  const params = await searchParams // v16: Must await

  return (
    <div className="container">
      <h1>Products</h1>
      <Suspense
        key={params.category} // Reset on filter change
        fallback={<ProductSkeleton />}
      >
        <ProductList
          category={params.category}
          page={Number(params.page) || 1}
        />
      </Suspense>
    </div>
  )
}

// components/products/ProductList.tsx
async function getProducts(category?: string, page = 1) {
  'use cache'
  cacheLife('minutes')

  const res = await fetch(
    `${process.env.API_URL}/products?category=${category}&page=${page}`
  )
  return res.json()
}

export async function ProductList({ category, page }: Props) {
  const { products, total } = await getProducts(category, page)

  return (
    <>
      <div className="grid grid-cols-3 gap-4">
        {products.map(p => <ProductCard key={p.id} product={p} />)}
      </div>
      <Pagination current={page} total={total} />
    </>
  )
}
```

---

## 5. Client Components Pattern

```typescript
// components/AddToCartButton.tsx
'use client'

import { useTransition, useOptimistic } from 'react'
import { addToCart } from '@/app/actions/cart'

export function AddToCartButton({ productId }: { productId: string }) {
  const [isPending, startTransition] = useTransition()
  const [optimisticCart, addOptimistic] = useOptimistic(
    [],
    (state, newItem) => [...state, newItem]
  )

  const handleClick = () => {
    startTransition(async () => {
      addOptimistic({ productId, pending: true })
      await addToCart(productId)
    })
  }

  return (
    <button
      onClick={handleClick}
      disabled={isPending}
      className="btn-primary disabled:opacity-50"
    >
      {isPending ? 'Adding...' : 'Add to Cart'}
    </button>
  )
}
```

---

## 6. Server Actions Pattern

```typescript
// app/actions/cart.ts
'use server'

import { revalidateTag, revalidatePath } from 'next/cache'
import { cookies } from 'next/headers'
import { redirect } from 'next/navigation'

export async function addToCart(productId: string) {
  const cookieStore = await cookies()
  const sessionId = cookieStore.get('session')?.value

  if (!sessionId) {
    redirect('/login')
  }

  try {
    await db.cart.upsert({
      where: { sessionId_productId: { sessionId, productId } },
      update: { quantity: { increment: 1 } },
      create: { sessionId, productId, quantity: 1 },
    })

    revalidateTag('cart')
    return { success: true }
  } catch (error) {
    return { error: 'Failed to add to cart' }
  }
}

// Form with Server Action
export async function createProduct(formData: FormData) {
  'use server'

  const name = formData.get('name') as string
  const price = parseFloat(formData.get('price') as string)

  if (!name || isNaN(price)) {
    return { error: 'Invalid input' }
  }

  const product = await db.product.create({
    data: { name, price }
  })

  revalidatePath('/products')
  redirect(`/products/${product.id}`)
}
```

---

## 7. Caching System (v16)

### Four Caching Layers

| Layer | What | Duration | Invalidation |
|-------|------|----------|--------------|
| **Request Memoization** | fetch() deduplication | Single request | Automatic |
| **Data Cache** | API/DB responses | Persistent | `revalidateTag()`, `revalidatePath()` |
| **Full Route Cache** | Rendered HTML | Persistent | On revalidation |
| **Router Cache** | Prefetched routes | Session (30s-5min) | `router.refresh()` |

### Caching Patterns

```typescript
// Pattern 1: Cache with tags
async function getProduct(id: string) {
  'use cache'
  cacheLife('hours')
  cacheTag(`product-${id}`)

  return db.product.findUnique({ where: { id } })
}

// Pattern 2: Revalidation
import { revalidateTag } from 'next/cache'

export async function updateProduct(id: string, data: ProductData) {
  'use server'

  await db.product.update({ where: { id }, data })
  revalidateTag(`product-${id}`)
  revalidatePath('/products')
}

// Pattern 3: No cache (always fresh)
async function getCurrentUser() {
  // No 'use cache' = no caching
  const session = await getSession()
  return session?.user
}
```

---

## 8. Parallel Routes

```typescript
// app/dashboard/layout.tsx
export default function DashboardLayout({
  children,
  analytics,  // @analytics slot
  team,       // @team slot
}: {
  children: React.ReactNode
  analytics: React.ReactNode
  team: React.ReactNode
}) {
  return (
    <div className="grid grid-cols-12 gap-4">
      <main className="col-span-8">{children}</main>
      <aside className="col-span-2">{analytics}</aside>
      <aside className="col-span-2">{team}</aside>
    </div>
  )
}

// app/dashboard/@analytics/page.tsx
export default async function AnalyticsSlot() {
  const data = await getAnalytics()
  return <AnalyticsChart data={data} />
}

// app/dashboard/@analytics/loading.tsx
export default function Loading() {
  return <ChartSkeleton />
}
```

---

## 9. Intercepting Routes (Modals)

```
app/
├── @modal/
│   ├── (.)photos/[id]/page.tsx  # Intercept (modal)
│   └── default.tsx              # Empty default
├── photos/
│   └── [id]/page.tsx            # Full page
└── layout.tsx
```

```typescript
// app/@modal/(.)photos/[id]/page.tsx
import { Modal } from '@/components/Modal'

export default async function PhotoModal({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const photo = await getPhoto(id)

  return (
    <Modal>
      <img src={photo.url} alt={photo.title} />
    </Modal>
  )
}
```

---

## 10. Best Practices

### Do's ✅
- **Start with Server Components** - Add 'use client' only when needed
- **Use `use cache`** - For data that can be shared across requests
- **Await params/searchParams** - They're Promises in v16
- **Use Suspense boundaries** - Enable streaming for slow data
- **Leverage PPR** - Static shell + dynamic content
- **Use Server Actions** - For mutations with progressive enhancement

### Don'ts ❌
- **Don't use hooks in Server Components** - No useState, useEffect
- **Don't pass functions to Client Components** - Only serializable data
- **Don't fetch in Client Components** - Use Server Components or Server Actions
- **Don't forget loading states** - Always provide loading.tsx
- **Don't over-cache** - Personalized data shouldn't be cached

---

## Quick Reference

### File Structure
```
app/
├── (marketing)/        # Route group (no URL impact)
│   ├── page.tsx       # /
│   └── about/page.tsx # /about
├── dashboard/
│   ├── layout.tsx     # Shared dashboard layout
│   ├── page.tsx       # /dashboard
│   ├── @modal/        # Parallel route
│   └── settings/      # /dashboard/settings
├── api/
│   └── products/
│       └── route.ts   # API route
└── [...slug]/page.tsx # Catch-all route
```

### Common Patterns
```typescript
// Dynamic params (v16)
export default async function Page({
  params
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
}

// Search params (v16)
export default async function Page({
  searchParams
}: {
  searchParams: Promise<{ q?: string }>
}) {
  const { q } = await searchParams
}

// Generate static params
export async function generateStaticParams() {
  const posts = await getPosts()
  return posts.map(p => ({ slug: p.slug }))
}

// Metadata
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const { id } = await params
  const product = await getProduct(id)
  return { title: product.name }
}
```

---

## 11. Legacy Versions Reference

### Next.js 14/15 Patterns (Para proyectos existentes)

#### Diferencias Clave con v16

| Aspecto | v14/15 | v16+ |
|---------|--------|------|
| params | Objeto síncrono | Promise (await) |
| searchParams | Objeto síncrono | Promise (await) |
| cookies() | Síncrono | Async (await) |
| headers() | Síncrono | Async (await) |
| Caching | `fetch` options | `use cache` directive |
| ISR | `revalidate` option | `cacheLife()` profiles |

#### Patrones v14/15 (Legacy)

```typescript
// v14/15: params es objeto síncrono
export default function Page({
  params,
  searchParams,
}: {
  params: { id: string }      // NO Promise
  searchParams: { q?: string } // NO Promise
}) {
  const { id } = params       // Acceso directo
  const { q } = searchParams  // Acceso directo

  return <div>ID: {id}</div>
}

// v14/15: cookies síncrono
import { cookies } from 'next/headers'

export default function Page() {
  const cookieStore = cookies() // Sin await
  const token = cookieStore.get('token')
  return <div>...</div>
}
```

#### Data Fetching v14/15

```typescript
// v14/15: ISR con fetch options
async function getProducts() {
  const res = await fetch('https://api.example.com/products', {
    next: { revalidate: 3600 }, // ISR: 1 hora
  })
  return res.json()
}

// v14/15: Sin cache
async function getUser() {
  const res = await fetch('https://api.example.com/user', {
    cache: 'no-store', // Siempre fresh
  })
  return res.json()
}

// v14/15: Cache con tags
async function getProduct(id: string) {
  const res = await fetch(`https://api.example.com/products/${id}`, {
    next: {
      tags: [`product-${id}`],
      revalidate: 3600,
    },
  })
  return res.json()
}
```

#### Server Actions v14/15

```typescript
// v14/15: Server Actions básicos
'use server'

import { revalidatePath } from 'next/cache'
import { cookies } from 'next/headers'

export async function addToCart(productId: string) {
  const cookieStore = cookies() // Sin await en v14/15
  const sessionId = cookieStore.get('session')?.value

  // ... lógica

  revalidatePath('/cart')
  return { success: true }
}
```

#### Migración v14/15 → v16

```typescript
// ANTES (v14/15)
export default function Page({ params }: { params: { id: string } }) {
  const { id } = params
  const cookieStore = cookies()
  // ...
}

// DESPUÉS (v16)
export default async function Page({
  params
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const cookieStore = await cookies()
  // ...
}
```

### Next.js 13 Patterns (Legacy)

#### App Router Inicial (v13.4+)

```typescript
// v13: Estructura básica igual, pero menos features
// - Sin PPR
// - Sin use cache
// - Server Actions experimentales

// v13: Server Component
async function ProductPage({ params }: { params: { id: string } }) {
  const product = await fetch(`/api/products/${params.id}`).then(r => r.json())
  return <ProductDetail product={product} />
}

// v13: Client Component
'use client'

import { useState } from 'react'

function Counter() {
  const [count, setCount] = useState(0)
  return <button onClick={() => setCount(c => c + 1)}>{count}</button>
}
```

### Guía de Migración Rápida

| De | A | Cambio Principal |
|----|---|------------------|
| v13 → v14 | Estable | Server Actions estables |
| v14 → v15 | Mejoras | Turbopack dev, mejoras caching |
| v15 → v16 | **Breaking** | params/searchParams como Promises, `use cache` |

### Detectar Versión en Proyecto

```bash
# Ver versión instalada
npm list next

# En package.json
"dependencies": {
  "next": "^14.2.0"  // v14
  "next": "^15.0.0"  // v15
  "next": "^16.0.0"  // v16
}
```

---

## Resources

- `resources/implementation-playbook.md` for detailed patterns and examples
- `resources/legacy-patterns.md` for v13/v14/v15 specific patterns
- [Next.js Documentation](https://nextjs.org/docs)
- [Vercel Templates](https://vercel.com/templates/next.js)
