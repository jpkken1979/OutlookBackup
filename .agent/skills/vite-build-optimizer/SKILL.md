---
name: vite-build-optimizer
type: feature
description: Optimize Vite builds for bundle size, chunking, build speed, and output quality. Use when analyzing a Vite build, reducing bundle size, tuning chunk strategy, improving build performance, or deciding which optimizations are worth applying in a Vite-based frontend project.
---

# Vite Build Optimizer

## Purpose

Provide structured guidance for analyzing and improving Vite build performance and output size.

## When to Use

- Investigating large Vite bundles
- Improving build time or chunk strategy
- Reviewing Vite output for optimization opportunities
- Planning code-splitting and vendor chunking decisions
- Comparing optimization levels for a frontend build

## Workflow

1. Measure the current build output and bottlenecks
2. Identify the biggest size or build-time drivers
3. Choose the optimization level deliberately
4. Apply chunking, plugin, and config changes selectively
5. Re-measure and validate the impact

## Critical Patterns

- Measure before optimizing
- Prioritize the heaviest chunks and slowest build stages first
- Avoid cargo-cult optimization flags without evidence
- Re-check projected gains against real output after changes

## Examples

### Optimization request

```json
{
  "project_path": "/path/to/vite-project",
  "analyze_current": true,
  "optimization_level": "aggressive"
}
```

### Metrics output shape

```json
{
  "current_metrics": {
    "bundle_size": "500KB",
    "gzip_size": "150KB",
    "build_time": 25
  },
  "projected_metrics": {
    "bundle_size": "350KB",
    "gzip_size": "105KB",
    "build_time": 20
  }
}
```

## Resources

- Chunking and code-splitting strategy
- Plugin impact on build time
- Bundle-size and compression analysis
- Vite config tuning for production builds

## Validation

- Compare before/after bundle metrics
- Verify build-time improvement is real
- Confirm chunk strategy did not break runtime assumptions
- Re-check compression and output quality after optimization
