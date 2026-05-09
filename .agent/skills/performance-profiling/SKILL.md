---
name: performance-profiling
description: >-
type: feature
---
  Use when debugging slow apps, optimizing bundle size, or improving Core Web
  Vitals. Triggers: lighthouse, bundle analyzer, slow interaction, jank, memory
  leak, LCP, INP, CLS, optimization.
metadata:
  category: performance
  author: ozy
  triggers: performance, profiling, optimization, lighthouse, bundles, bottlenecks, memory, network
  references: Rules.md, AGENTS.md
---

# Performance Mastery (God Mode) ⚡

Expert principles for measuring, analyzing, and achieving extreme speed in web applications.

## 💎 Core Principles (Axioms)
1. **Profile, Don't Guess**: Never optimize based on intuition. Always use data from Lighthouse or DevTools.
2. **The Critical Path First**: Focus on the code that blocks the initial render (LCP) and user interaction (INP).
3. **The Budget is Law**: Set performance budgets (e.g., <200kb JS) and never let features break them.
4. **Data Locality (Client)**: Reduce network roundtrips. Batch API calls or use optimistic UI to mask latency.
5. **The Fastest Code is Deleted Code**: If a feature or dependency doesn't add value, remove it instead of optimizing it.

## 🛠️ Step-by-Step implementation
1. **The Baseline Phase**: Take a snapshot of current Core Web Vitals (LCP, INP, CLS) using Lighthouse.
2. **The Discovery Phase**: Use the Flame Graph in DevTools to find "Long Tasks" (>50ms) that block the UI.
3. **The Bundle Phase**: Analyze the artifact size. Split giant vendor chunks into lazy-loaded routes.
4. **The Validation Phase**: Repeat measurements after the fix to calculate the "Impact Delta".

## 🛡️ Security & Quality Checklist
- [ ] **Lighthouse Score**: Is the Performance score >90?
- [ ] **Main Thread Blocking**: Are there any red bars in the DevTools Performance timeline?
- [ ] **Memory Growth**: Does the heap size return to baseline after interaction (Garbage Collection)?
- [ ] **Asset Compression**: Are we using Brotli/Gzip and modern image formats (WebP/AVIF)?
- [ ] **Cache Headers**: Are static assets configured with `Cache-Control: immutable`?

## 📚 Examples (Few-shot)

### Example: Targeted Optimization (TS)
```typescript
// ❌ BAD: Loading heavy library on every page
import { heavyChartLib } from 'heavy-lib';

// ✅ GOOD (God Mode): Lazy loading when needed
const Chart = lazy(() => import('heavy-lib'));
```

### Example: Avoiding Layout Thrashing
```javascript
// ❌ BAD: Read-Write in a loop
elements.forEach(el => {
  const height = el.offsetHeight; // Read
  el.style.width = height + 'px'; // Write -> Reflow!
});

// ✅ GOOD (God Mode): Batch Reads then Writes
const heights = elements.map(el => el.offsetHeight);
elements.forEach((el, i) => el.style.width = heights[i] + 'px');
```

---
*Skill: performance-profiling v2.0 (Bibek Poudel Edition)*
