# Next.js 16 App Router - Implementation Playbook

> Patrones detallados, checklists y ejemplos de código para Next.js 16.1.6+

---

## 1. Project Setup

### Crear Proyecto Next.js 16

```bash
# Crear nuevo proyecto
npx create-next-app@latest my-app --typescript --tailwind --eslint --app --src-dir

# Estructura resultante
my-app/
├── src/
│   ├── app/
│   │   ├── layout.tsx
│   │   ├── page.tsx
│   │   └── globals.css
│   └── components/
├── public/
├── next.config.ts      # TypeScript config (v16)
├── tailwind.config.ts
└── package.json
```

### next.config.ts (v16)

```typescript
import type { NextConfig } from 'next'

const config: NextConfig = {
  // Turbopack (estable en v16)
  experimental: {
    // Partial Prerendering
    ppr: 'incremental',

    // Custom cache profiles
    cacheLife: {
      products: {
        stale: 300,      // 5 min stale
        revalidate: 3600, // 1 hour revalidate
        expire: 86400,   // 1 day max
      },
      user: {
        stale: 0,
        revalidate: 60,
        expire: 300,
      },
    },
  },

  // Images
  images: {
    remotePatterns: [
      {
        protocol: 'https',
        hostname: '**.example.com',
      },
    ],
  },

  // Redirects
  async redirects() {
    return [
      {
        source: '/old-path',
        destination: '/new-path',
        permanent: true,
      },
    ]
  },
}

export default config
```

---

## 2. Root Layout Pattern

```typescript
// src/app/layout.tsx
import type { Metadata, Viewport } from 'next'
import { Inter, JetBrains_Mono } from 'next/font/google'
import { Providers } from './providers'
import './globals.css'

const inter = Inter({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-sans',
})

const jetbrains = JetBrains_Mono({
  subsets: ['latin'],
  display: 'swap',
  variable: '--font-mono',
})

export const metadata: Metadata = {
  title: {
    default: 'My App',
    template: '%s | My App',
  },
  description: 'Built with Next.js 16',
  metadataBase: new URL('https://myapp.com'),
  openGraph: {
    type: 'website',
    locale: 'en_US',
    siteName: 'My App',
  },
  twitter: {
    card: 'summary_large_image',
    creator: '@myapp',
  },
}

export const viewport: Viewport = {
  themeColor: [
    { media: '(prefers-color-scheme: light)', color: '#ffffff' },
    { media: '(prefers-color-scheme: dark)', color: '#000000' },
  ],
  width: 'device-width',
  initialScale: 1,
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html
      lang="en"
      className={`${inter.variable} ${jetbrains.variable}`}
      suppressHydrationWarning
    >
      <body className="min-h-screen bg-background font-sans antialiased">
        <Providers>{children}</Providers>
      </body>
    </html>
  )
}
```

### Providers Pattern

```typescript
// src/app/providers.tsx
'use client'

import { ThemeProvider } from 'next-themes'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { useState } from 'react'

export function Providers({ children }: { children: React.ReactNode }) {
  const [queryClient] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            staleTime: 60 * 1000,
            refetchOnWindowFocus: false,
          },
        },
      })
  )

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider
        attribute="class"
        defaultTheme="system"
        enableSystem
        disableTransitionOnChange
      >
        {children}
      </ThemeProvider>
    </QueryClientProvider>
  )
}
```

---

## 3. Data Fetching Patterns

### Pattern A: Server Component con `use cache`

```typescript
// src/app/products/page.tsx
import { Suspense } from 'react'
import { cacheLife, cacheTag } from 'next/cache'
import { ProductGrid, ProductSkeleton } from '@/components/products'

// Cached data fetching
async function getProducts(category?: string) {
  'use cache'
  cacheLife('products') // Custom profile
  cacheTag('products', category ? `category-${category}` : 'all')

  const res = await fetch(
    `${process.env.API_URL}/products${category ? `?category=${category}` : ''}`
  )

  if (!res.ok) throw new Error('Failed to fetch products')
  return res.json()
}

// Page component
export default async function ProductsPage({
  searchParams,
}: {
  searchParams: Promise<{ category?: string; page?: string }>
}) {
  const { category, page } = await searchParams

  return (
    <main className="container py-8">
      <h1 className="text-3xl font-bold mb-8">Products</h1>

      <Suspense
        key={`${category}-${page}`}
        fallback={<ProductSkeleton count={12} />}
      >
        <ProductGrid category={category} page={Number(page) || 1} />
      </Suspense>
    </main>
  )
}

// Server Component that fetches data
async function ProductGrid({
  category,
  page,
}: {
  category?: string
  page: number
}) {
  const { products, totalPages } = await getProducts(category)

  return (
    <>
      <div className="grid grid-cols-1 md:grid-cols-3 lg:grid-cols-4 gap-6">
        {products.map((product: Product) => (
          <ProductCard key={product.id} product={product} />
        ))}
      </div>
      <Pagination current={page} total={totalPages} />
    </>
  )
}
```

### Pattern B: Parallel Data Fetching

```typescript
// src/app/dashboard/page.tsx
import { Suspense } from 'react'

// Fetch functions run in parallel
async function getStats() {
  'use cache'
  cacheLife('minutes')
  return fetch(`${process.env.API_URL}/stats`).then(r => r.json())
}

async function getRecentOrders() {
  'use cache'
  cacheLife('seconds')
  return fetch(`${process.env.API_URL}/orders/recent`).then(r => r.json())
}

async function getNotifications() {
  // No cache - always fresh
  return fetch(`${process.env.API_URL}/notifications`).then(r => r.json())
}

export default async function DashboardPage() {
  // Start all fetches in parallel
  const statsPromise = getStats()
  const ordersPromise = getRecentOrders()
  const notificationsPromise = getNotifications()

  // Await all
  const [stats, orders, notifications] = await Promise.all([
    statsPromise,
    ordersPromise,
    notificationsPromise,
  ])

  return (
    <div className="grid grid-cols-12 gap-6">
      <StatsCard stats={stats} className="col-span-12" />
      <OrdersList orders={orders} className="col-span-8" />
      <NotificationsFeed notifications={notifications} className="col-span-4" />
    </div>
  )
}
```

### Pattern C: Streaming with Suspense

```typescript
// src/app/product/[id]/page.tsx
import { Suspense } from 'react'
import { notFound } from 'next/navigation'

async function getProduct(id: string) {
  'use cache'
  cacheLife('hours')
  cacheTag(`product-${id}`)

  const product = await db.product.findUnique({ where: { id } })
  return product
}

export default async function ProductPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  const { id } = await params
  const product = await getProduct(id)

  if (!product) notFound()

  return (
    <main>
      {/* Critical content - renders immediately */}
      <ProductHeader product={product} />
      <ProductGallery images={product.images} />
      <ProductInfo product={product} />

      {/* Streams in - can be slow */}
      <Suspense fallback={<ReviewsSkeleton />}>
        <ProductReviews productId={id} />
      </Suspense>

      <Suspense fallback={<RecommendationsSkeleton />}>
        <RelatedProducts productId={id} />
      </Suspense>
    </main>
  )
}

// Slow component - streams in
async function ProductReviews({ productId }: { productId: string }) {
  // Simulate slow API
  const reviews = await fetch(
    `${process.env.API_URL}/products/${productId}/reviews`
  ).then(r => r.json())

  return (
    <section>
      <h2>Reviews ({reviews.length})</h2>
      {reviews.map((review: Review) => (
        <ReviewCard key={review.id} review={review} />
      ))}
    </section>
  )
}
```

---

## 4. Server Actions Patterns

### Pattern A: Form Action

```typescript
// src/app/products/new/page.tsx
import { createProduct } from '@/app/actions/products'

export default function NewProductPage() {
  return (
    <form action={createProduct}>
      <input type="text" name="name" required />
      <input type="number" name="price" step="0.01" required />
      <textarea name="description" />
      <button type="submit">Create Product</button>
    </form>
  )
}

// src/app/actions/products.ts
'use server'

import { revalidatePath, revalidateTag } from 'next/cache'
import { redirect } from 'next/navigation'
import { z } from 'zod'

const ProductSchema = z.object({
  name: z.string().min(1).max(100),
  price: z.coerce.number().positive(),
  description: z.string().optional(),
})

export async function createProduct(formData: FormData) {
  // Validate
  const parsed = ProductSchema.safeParse({
    name: formData.get('name'),
    price: formData.get('price'),
    description: formData.get('description'),
  })

  if (!parsed.success) {
    return { error: parsed.error.flatten().fieldErrors }
  }

  // Create
  const product = await db.product.create({
    data: parsed.data,
  })

  // Revalidate caches
  revalidateTag('products')
  revalidatePath('/products')

  // Redirect
  redirect(`/products/${product.id}`)
}
```

### Pattern B: Optimistic Updates

```typescript
// src/components/LikeButton.tsx
'use client'

import { useOptimistic, useTransition } from 'react'
import { toggleLike } from '@/app/actions/likes'

export function LikeButton({
  productId,
  initialLikes,
  isLiked,
}: {
  productId: string
  initialLikes: number
  isLiked: boolean
}) {
  const [isPending, startTransition] = useTransition()

  const [optimisticState, setOptimistic] = useOptimistic(
    { likes: initialLikes, isLiked },
    (state, newIsLiked: boolean) => ({
      likes: state.likes + (newIsLiked ? 1 : -1),
      isLiked: newIsLiked,
    })
  )

  const handleClick = () => {
    startTransition(async () => {
      setOptimistic(!optimisticState.isLiked)
      await toggleLike(productId)
    })
  }

  return (
    <button
      onClick={handleClick}
      disabled={isPending}
      className={optimisticState.isLiked ? 'text-red-500' : 'text-gray-500'}
    >
      ❤️ {optimisticState.likes}
    </button>
  )
}

// src/app/actions/likes.ts
'use server'

import { revalidateTag } from 'next/cache'
import { cookies } from 'next/headers'

export async function toggleLike(productId: string) {
  const cookieStore = await cookies()
  const userId = cookieStore.get('userId')?.value

  if (!userId) {
    throw new Error('Not authenticated')
  }

  const existing = await db.like.findUnique({
    where: { userId_productId: { userId, productId } },
  })

  if (existing) {
    await db.like.delete({ where: { id: existing.id } })
  } else {
    await db.like.create({ data: { userId, productId } })
  }

  revalidateTag(`product-${productId}`)
}
```

### Pattern C: useActionState (v16)

```typescript
// src/components/ContactForm.tsx
'use client'

import { useActionState } from 'react'
import { submitContact } from '@/app/actions/contact'

const initialState = {
  message: '',
  errors: {} as Record<string, string[]>,
}

export function ContactForm() {
  const [state, formAction, isPending] = useActionState(
    submitContact,
    initialState
  )

  return (
    <form action={formAction}>
      <div>
        <label htmlFor="email">Email</label>
        <input type="email" id="email" name="email" required />
        {state.errors?.email && (
          <p className="text-red-500">{state.errors.email[0]}</p>
        )}
      </div>

      <div>
        <label htmlFor="message">Message</label>
        <textarea id="message" name="message" required />
        {state.errors?.message && (
          <p className="text-red-500">{state.errors.message[0]}</p>
        )}
      </div>

      <button type="submit" disabled={isPending}>
        {isPending ? 'Sending...' : 'Send Message'}
      </button>

      {state.message && (
        <p className={state.errors ? 'text-red-500' : 'text-green-500'}>
          {state.message}
        </p>
      )}
    </form>
  )
}

// src/app/actions/contact.ts
'use server'

import { z } from 'zod'

const ContactSchema = z.object({
  email: z.string().email('Invalid email'),
  message: z.string().min(10, 'Message too short'),
})

export async function submitContact(prevState: any, formData: FormData) {
  const parsed = ContactSchema.safeParse({
    email: formData.get('email'),
    message: formData.get('message'),
  })

  if (!parsed.success) {
    return {
      message: 'Validation failed',
      errors: parsed.error.flatten().fieldErrors,
    }
  }

  // Send email, save to DB, etc.
  await sendContactEmail(parsed.data)

  return {
    message: 'Message sent successfully!',
    errors: {},
  }
}
```

---

## 5. Parallel Routes Patterns

### Dashboard with Independent Loading

```typescript
// src/app/dashboard/layout.tsx
export default function DashboardLayout({
  children,
  analytics,
  notifications,
  activity,
}: {
  children: React.ReactNode
  analytics: React.ReactNode
  notifications: React.ReactNode
  activity: React.ReactNode
}) {
  return (
    <div className="min-h-screen grid grid-cols-12 gap-4 p-4">
      <nav className="col-span-2 bg-gray-100 rounded-lg p-4">
        <DashboardNav />
      </nav>

      <main className="col-span-7">
        {children}
      </main>

      <aside className="col-span-3 space-y-4">
        {analytics}
        {notifications}
        {activity}
      </aside>
    </div>
  )
}

// src/app/dashboard/@analytics/page.tsx
export default async function AnalyticsSlot() {
  const data = await getAnalytics()
  return <AnalyticsWidget data={data} />
}

// src/app/dashboard/@analytics/loading.tsx
export default function AnalyticsLoading() {
  return <WidgetSkeleton title="Analytics" />
}

// src/app/dashboard/@notifications/page.tsx
export default async function NotificationsSlot() {
  const notifications = await getNotifications()
  return <NotificationsWidget notifications={notifications} />
}

// src/app/dashboard/@notifications/loading.tsx
export default function NotificationsLoading() {
  return <WidgetSkeleton title="Notifications" />
}

// src/app/dashboard/@activity/page.tsx
export default async function ActivitySlot() {
  const activity = await getRecentActivity()
  return <ActivityFeed activity={activity} />
}

// src/app/dashboard/@activity/loading.tsx
export default function ActivityLoading() {
  return <WidgetSkeleton title="Recent Activity" />
}
```

---

## 6. Intercepting Routes (Modal Pattern)

### Photo Gallery Modal

```
src/app/
├── @modal/
│   ├── (.)photos/[id]/page.tsx    # Modal view
│   └── default.tsx                # Empty when no modal
├── photos/
│   ├── page.tsx                   # Gallery grid
│   └── [id]/page.tsx              # Full photo page
└── layout.tsx
```

```typescript
// src/app/layout.tsx
export default function RootLayout({
  children,
  modal,
}: {
  children: React.ReactNode
  modal: React.ReactNode
}) {
  return (
    <html lang="en">
      <body>
        {children}
        {modal}
      </body>
    </html>
  )
}

// src/app/@modal/default.tsx
export default function Default() {
  return null
}

// src/app/@modal/(.)photos/[id]/page.tsx
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
      <div className="relative aspect-video">
        <Image
          src={photo.url}
          alt={photo.title}
          fill
          className="object-contain"
        />
      </div>
      <div className="p-4">
        <h2 className="text-xl font-bold">{photo.title}</h2>
        <p className="text-gray-600">{photo.description}</p>
      </div>
    </Modal>
  )
}

// src/components/Modal.tsx
'use client'

import { useRouter } from 'next/navigation'
import { useCallback, useEffect, useRef } from 'react'

export function Modal({ children }: { children: React.ReactNode }) {
  const router = useRouter()
  const overlayRef = useRef<HTMLDivElement>(null)

  const onDismiss = useCallback(() => {
    router.back()
  }, [router])

  const onKeyDown = useCallback(
    (e: KeyboardEvent) => {
      if (e.key === 'Escape') onDismiss()
    },
    [onDismiss]
  )

  useEffect(() => {
    document.addEventListener('keydown', onKeyDown)
    return () => document.removeEventListener('keydown', onKeyDown)
  }, [onKeyDown])

  return (
    <div
      ref={overlayRef}
      className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center"
      onClick={(e) => {
        if (e.target === overlayRef.current) onDismiss()
      }}
    >
      <div className="relative bg-white rounded-lg max-w-4xl max-h-[90vh] overflow-auto">
        <button
          onClick={onDismiss}
          className="absolute top-2 right-2 p-2 rounded-full hover:bg-gray-100"
        >
          ✕
        </button>
        {children}
      </div>
    </div>
  )
}
```

---

## 7. API Routes (Route Handlers)

```typescript
// src/app/api/products/route.ts
import { NextRequest, NextResponse } from 'next/server'
import { z } from 'zod'

// GET /api/products
export async function GET(request: NextRequest) {
  const searchParams = request.nextUrl.searchParams
  const category = searchParams.get('category')
  const page = parseInt(searchParams.get('page') || '1')
  const limit = parseInt(searchParams.get('limit') || '20')

  const products = await db.product.findMany({
    where: category ? { category } : undefined,
    skip: (page - 1) * limit,
    take: limit,
  })

  const total = await db.product.count({
    where: category ? { category } : undefined,
  })

  return NextResponse.json({
    products,
    pagination: {
      page,
      limit,
      total,
      totalPages: Math.ceil(total / limit),
    },
  })
}

// POST /api/products
const CreateProductSchema = z.object({
  name: z.string().min(1).max(100),
  price: z.number().positive(),
  category: z.string(),
  description: z.string().optional(),
})

export async function POST(request: NextRequest) {
  try {
    const body = await request.json()
    const parsed = CreateProductSchema.parse(body)

    const product = await db.product.create({
      data: parsed,
    })

    return NextResponse.json(product, { status: 201 })
  } catch (error) {
    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Validation failed', details: error.errors },
        { status: 400 }
      )
    }
    return NextResponse.json(
      { error: 'Internal server error' },
      { status: 500 }
    )
  }
}

// src/app/api/products/[id]/route.ts
export async function GET(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  const product = await db.product.findUnique({
    where: { id },
    include: { reviews: true },
  })

  if (!product) {
    return NextResponse.json(
      { error: 'Product not found' },
      { status: 404 }
    )
  }

  return NextResponse.json(product)
}

export async function PATCH(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const body = await request.json()

  const product = await db.product.update({
    where: { id },
    data: body,
  })

  return NextResponse.json(product)
}

export async function DELETE(
  request: NextRequest,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params

  await db.product.delete({ where: { id } })

  return new NextResponse(null, { status: 204 })
}
```

---

## 8. Image Optimization

```typescript
// src/components/ProductImage.tsx
import Image from 'next/image'

export function ProductImage({
  src,
  alt,
  priority = false,
}: {
  src: string
  alt: string
  priority?: boolean
}) {
  return (
    <div className="relative aspect-square overflow-hidden rounded-lg bg-gray-100">
      <Image
        src={src}
        alt={alt}
        fill
        sizes="(max-width: 768px) 100vw, (max-width: 1200px) 50vw, 33vw"
        className="object-cover transition-transform hover:scale-105"
        priority={priority}
        quality={85}
      />
    </div>
  )
}

// Responsive hero image
export function HeroImage({ src, alt }: { src: string; alt: string }) {
  return (
    <div className="relative w-full h-[60vh]">
      <Image
        src={src}
        alt={alt}
        fill
        sizes="100vw"
        className="object-cover"
        priority
        quality={90}
        placeholder="blur"
        blurDataURL={src + '?w=10&q=10'} // Low-res placeholder
      />
    </div>
  )
}
```

---

## 9. Error Handling

```typescript
// src/app/error.tsx
'use client'

import { useEffect } from 'react'

export default function Error({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  useEffect(() => {
    // Log error to monitoring service
    console.error(error)
  }, [error])

  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh]">
      <h2 className="text-2xl font-bold mb-4">Something went wrong</h2>
      <p className="text-gray-600 mb-4">
        {error.message || 'An unexpected error occurred'}
      </p>
      <button
        onClick={reset}
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
      >
        Try again
      </button>
    </div>
  )
}

// src/app/not-found.tsx
import Link from 'next/link'

export default function NotFound() {
  return (
    <div className="flex flex-col items-center justify-center min-h-[50vh]">
      <h2 className="text-4xl font-bold mb-4">404</h2>
      <p className="text-gray-600 mb-4">Page not found</p>
      <Link
        href="/"
        className="px-4 py-2 bg-blue-600 text-white rounded-lg hover:bg-blue-700"
      >
        Go home
      </Link>
    </div>
  )
}

// src/app/global-error.tsx (catches errors in root layout)
'use client'

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html>
      <body>
        <div className="flex flex-col items-center justify-center min-h-screen">
          <h2>Something went wrong!</h2>
          <button onClick={reset}>Try again</button>
        </div>
      </body>
    </html>
  )
}
```

---

## 10. Middleware

```typescript
// src/middleware.ts
import { NextResponse } from 'next/server'
import type { NextRequest } from 'next/server'

export function middleware(request: NextRequest) {
  const { pathname } = request.nextUrl

  // Auth check
  const token = request.cookies.get('token')?.value

  // Protect dashboard routes
  if (pathname.startsWith('/dashboard') && !token) {
    const loginUrl = new URL('/login', request.url)
    loginUrl.searchParams.set('redirect', pathname)
    return NextResponse.redirect(loginUrl)
  }

  // Redirect authenticated users from auth pages
  if ((pathname === '/login' || pathname === '/register') && token) {
    return NextResponse.redirect(new URL('/dashboard', request.url))
  }

  // Add custom headers
  const response = NextResponse.next()
  response.headers.set('x-pathname', pathname)

  return response
}

export const config = {
  matcher: [
    // Match all paths except static files
    '/((?!_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)',
  ],
}
```

---

## Checklist de Producción

### Pre-Deploy ✅

- [ ] `next.config.ts` configurado con PPR si necesario
- [ ] Imágenes remotas en `remotePatterns`
- [ ] Variables de entorno en `.env.local` y Vercel
- [ ] Metadata y OpenGraph configurados
- [ ] `loading.tsx` en rutas lentas
- [ ] `error.tsx` para manejo de errores
- [ ] Middleware para auth y redirects
- [ ] API routes con validación (Zod)
- [ ] Caching con `use cache` y `cacheLife`

### Performance ✅

- [ ] Server Components por defecto
- [ ] `'use client'` solo cuando necesario
- [ ] Suspense boundaries para streaming
- [ ] Parallel routes para loading independiente
- [ ] `next/image` para todas las imágenes
- [ ] `next/font` para fuentes
- [ ] Dynamic imports para componentes pesados

### SEO ✅

- [ ] `generateMetadata` en páginas dinámicas
- [ ] `generateStaticParams` para SSG
- [ ] `sitemap.ts` y `robots.ts`
- [ ] Structured data (JSON-LD)
- [ ] Canonical URLs

---

## Recursos

- [Next.js 16 Docs](https://nextjs.org/docs)
- [Vercel Templates](https://vercel.com/templates/next.js)
- [React 19 Docs](https://react.dev)
