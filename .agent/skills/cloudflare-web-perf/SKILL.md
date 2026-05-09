---
name: cloudflare-web-perf
description: >
type: feature
---
  Chrome DevTools MCP-based Core Web Vitals audit with 5-phase workflow:
  trace capture, CWV analysis, network analysis, accessibility check, and
  codebase correlation. Use when auditing website performance, diagnosing
  slow pages, or optimizing Core Web Vitals metrics.
source: Cloudflare
---

# Web Performance Audit

Core Web Vitals performance audit using Chrome DevTools Protocol with specific thresholds and remediation.

## 5-Phase Workflow

### Phase 1: Trace Capture
Collect performance trace via Chrome DevTools MCP:
- Navigate to target URL
- Enable Performance domain
- Capture trace for full page load
- Export trace data for analysis

### Phase 2: Core Web Vitals Analysis

| Metric | Good | Needs Improvement | Poor |
|--------|------|-------------------|------|
| **LCP** (Largest Contentful Paint) | ≤ 2.5s | ≤ 4.0s | > 4.0s |
| **INP** (Interaction to Next Paint) | ≤ 200ms | ≤ 500ms | > 500ms |
| **CLS** (Cumulative Layout Shift) | ≤ 0.1 | ≤ 0.25 | > 0.25 |
| **FCP** (First Contentful Paint) | ≤ 1.8s | ≤ 3.0s | > 3.0s |
| **TTFB** (Time to First Byte) | ≤ 800ms | ≤ 1.8s | > 1.8s |

### Phase 3: Network Analysis
- **Waterfall analysis**: Identify blocking resources
- **Resource size**: Find oversized assets (images, JS bundles)
- **Cache headers**: Check caching strategy (Cache-Control, ETag)
- **Compression**: Verify gzip/brotli for text resources
- **HTTP/2+**: Confirm multiplexing is enabled
- **Third-party scripts**: Measure impact of external resources

### Phase 4: Accessibility Check
- **Contrast ratios**: WCAG AA minimum 4.5:1 for text
- **Alt text**: All images must have descriptive alt attributes
- **Focus management**: Tab order must be logical
- **ARIA labels**: Interactive elements properly labeled
- **Semantic HTML**: Proper heading hierarchy, landmarks

### Phase 5: Codebase Correlation
Map findings to source code:
- LCP element → Component that renders it
- Layout shifts → CSS that causes reflow
- Long tasks → JavaScript functions in profiler
- Large bundles → Webpack/Vite chunks to optimize

## Common Fixes

### LCP Optimization
```html
<!-- Preload critical LCP image -->
<link rel="preload" as="image" href="/hero.webp" fetchpriority="high">

<!-- Use responsive images -->
<img src="hero.webp" srcset="hero-400.webp 400w, hero-800.webp 800w" 
     sizes="(max-width: 600px) 400px, 800px" loading="eager">
```

### CLS Prevention
```css
/* Reserve space for images */
img, video { aspect-ratio: 16/9; width: 100%; height: auto; }

/* Reserve space for ads/embeds */
.ad-slot { min-height: 250px; }

/* Avoid FOIT for fonts */
@font-face { font-display: swap; }
```

### INP Improvement
```typescript
// Break long tasks with scheduler
function processItems(items: Item[]) {
  const CHUNK_SIZE = 50;
  for (let i = 0; i < items.length; i += CHUNK_SIZE) {
    requestIdleCallback(() => {
      items.slice(i, i + CHUNK_SIZE).forEach(process);
    });
  }
}

// Use web workers for heavy computation
const worker = new Worker('/heavy-task.js');
worker.postMessage(data);
```

### Bundle Optimization
```typescript
// Dynamic imports for code splitting
const HeavyComponent = lazy(() => import('./HeavyComponent'));

// Tree-shaking friendly imports
import { specific } from 'library'; // NOT: import * as lib from 'library'
```

## Report Template

```markdown
# Web Performance Audit Report

## Summary
| Metric | Value | Rating | Target |
|--------|-------|--------|--------|
| LCP | X.Xs | 🟢/🟡/🔴 | ≤ 2.5s |
| INP | Xms | 🟢/🟡/🔴 | ≤ 200ms |
| CLS | X.XX | 🟢/🟡/🔴 | ≤ 0.1 |

## Top Issues
1. [Issue with highest impact]
2. [Next highest]

## Recommendations
[Prioritized by impact × effort]
```
