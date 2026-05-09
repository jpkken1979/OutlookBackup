---
name: nextjs-best-practices
description: >-
type: feature
---
  Use when building or optimizing Next.js App Router applications. Triggers:
  nextjs, app router, server components, client components, server actions,
  generateMetadata, revalidate.
metadata:
  category: framework
  author: ozy
  triggers: nextjs, react, server components, server actions, caching, metadata
  references: Rules.md, AGENTS.md
type: feature
---

# Next.js App Router Mastery (God Mode) 🚀

Expert principles for building high-fidelity, performant, and type-safe Next.js applications.

## 💎 Core Principles (Axioms)
1. **Server by Default**: All components are Server Components unless interactivity (`useState`, `useEffect`) is strictly required. 
2. **Data Locality**: Fetch data as close as possible to the component that needs it. Don't prop-drill; let Next.js handle request memoization.
3. **The Static-First Rule**: Aim for static rendering (SSG/ISR) by default. Only move to dynamic rendering (`force-dynamic`, `no-store`) for per-request user data.
4. **Action-Driven Mutations**: Use Server Actions for all data mutations. Pair them with `revalidatePath` or `revalidateTag` for immediate UI updates.
5. **Streaming is Better Than Waiting**: Use `loading.tsx` and React Suspense boundaries to keep the UI interactive while heavy data loads.

## 🛠️ Step-by-Step implementation
1. **The Layout Phase**: Define your route hierarchy in the `app/` directory. Set up shared `layout.tsx` for persistent UI.
2. **The Fetch Phase**: Implement data fetching in Server Components using `await` directly. Use `fetch` with specific revalidation tags.
3. **The Interaction Phase**: Create Client Components ('use client') for localized interactive bits (buttons, forms, effects).
4. **The Security Phase**: Protect your Server Actions and API routes with Zod validation and session checks.

## 🛡️ Security & Quality Checklist
- [ ] **Data Leaks**: Are there any `'use client'` components receiving large, sensitive objects from the server?
- [ ] **Validation Check**: Do all Server Actions validate their arguments with a schema (Zod/Valibot)?
- [ ] **Image Optimization**: Are we using `next/image` with proper `priority` for the LCP element?
- [ ] **CORS/Auth**: Are API routes protected by middleware or inline session checks?
- [ ] **Metadata**: Does every page have a unique title and description via `generateMetadata`?

## 📚 Examples (Few-shot)

### Example: Data Fetching in Server Component
```tsx
// ✅ God Mode: Direct fetching, typed, and cached
async function ProductList() {
  const products = await db.product.findMany({ where: { active: true } });
  
  return (
    <ul className="grid gap-4">
      {products.map(p => <ProductCard key={p.id} {...p} />)}
    </ul>
  );
}
```

### Example: Secure Server Action
```tsx
// ✅ God Mode: marked, validated, and revalidated
'use server'

import { revalidatePath } from 'next/cache';
import { z } from 'zod';

export async function addComment(formData: FormData) {
  const schema = z.object({ text: z.string().min(1) });
  const { text } = schema.parse(Object.fromEntries(formData));
  
  await db.comment.create({ data: { text } });
  revalidatePath('/post/123');
}
```

---
*Skill: nextjs-best-practices v2.0 (Bibek Poudel Edition)*
