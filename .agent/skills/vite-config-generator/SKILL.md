---
name: vite-config-generator
type: feature
description: Generate and shape Vite configuration based on project type, framework, TypeScript usage, plugin choices, and performance goals. Use when creating a new Vite config, migrating an app to Vite, selecting plugins, or standardizing build configuration for a frontend project.
---

# Vite Config Generator

## Purpose

Provide structured guidance for generating Vite configuration aligned with project type, framework, and performance goals.

## When to Use

- Creating a new `vite.config.*`
- Migrating a project to Vite
- Choosing framework plugins and config defaults
- Standardizing aliases, env handling, or browser targets
- Defining a Vite setup for SPA, SSR, MPA, or library mode

## Workflow

1. Confirm project type and framework
2. Define TypeScript, CSS, and plugin requirements
3. Decide target browsers and performance level
4. Generate config with only necessary features
5. Validate the config against the project structure and scripts

## Critical Patterns

- Start from project shape, not from a random plugin list
- Keep config explicit and proportionate to the app’s needs
- Treat aliases and env handling as part of architecture
- Avoid over-configuring before real build/runtime needs appear

## Examples

### Required inputs

```json
{
  "project_type": "spa",
  "framework": "react",
  "node_version": "20.19"
}
```

### Optional inputs

```json
{
  "typescript": true,
  "css_preprocessor": "sass",
  "performance_level": "aggressive",
  "include_plugins": ["inspect", "compression"],
  "target_browsers": "modern"
}
```

### Output shape

```json
{
  "status": "success",
  "config_file": "vite.config.ts",
  "features_enabled": [
    "TypeScript support",
    "Framework plugin",
    "Env handling"
  ]
}
```

## Resources

- Vite modes: SPA, SSR, MPA, library
- Framework plugin selection
- Alias and env configuration patterns
- Target browser and performance tradeoffs

## Validation

- Verify config matches the project type
- Check plugin list against actual runtime/build needs
- Confirm aliases and env behavior work with the codebase
- Validate build scripts and config assumptions together
