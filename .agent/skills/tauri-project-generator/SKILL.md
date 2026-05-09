---
name: tauri-project-generator
description: Generate and scaffold Tauri desktop projects with an explicit frontend choice, project structure, security defaults, platform targets, and initial configuration decisions. Use when creating a new Tauri app, evaluating frontend/framework combinations for Tauri, or defining the base architecture for a desktop application built with Rust plus a web UI.
type: feature
---

# Tauri Project Generator

## Purpose

Provide a structured approach for generating Tauri projects with the right frontend stack, platform targets, and baseline security posture.

## When to Use

- Creating a new Tauri project from scratch
- Choosing a frontend framework for a Tauri app
- Defining base directory structure and platform targets
- Setting up a Tauri project with sensible defaults
- Reviewing the architecture of a new desktop app before scaffolding

## Workflow

1. Define the application goal and target platforms
2. Choose the frontend framework and package manager intentionally
3. Decide security, database, and authentication baseline early
4. Generate project structure and config layout
5. Validate Rust/frontend boundary and build assumptions

## Critical Patterns

- Treat platform targets as architecture input, not an afterthought
- Pick frontend framework based on team fit and runtime needs
- Define security defaults before adding features
- Keep Rust backend responsibilities and UI responsibilities clearly separated

## Examples

### Required inputs

```json
{
  "project_name": "my-tauri-app",
  "frontend_framework": "react",
  "target_platforms": ["windows", "macos", "linux"]
}
```

### Optional inputs

```json
{
  "typescript": true,
  "package_manager": "npm",
  "database": "sqlite",
  "authentication": false,
  "include_tauri_api_examples": true
}
```

### Expected output shape

```json
{
  "status": "success",
  "project_path": "/path/to/project",
  "structure": {
    "frontend": "src/",
    "backend": "src-tauri/",
    "configs": "tauri.conf.json, package.json, Cargo.toml"
  }
}
```

## Resources

- Tauri 2 project structure
- Frontend framework selection for desktop apps
- Security defaults for Tauri apps
- Cross-platform build considerations

## Validation

- Verify selected frontend stack fits the app requirements
- Confirm platform targets and build assumptions
- Validate security defaults and config boundaries
- Check that the generated structure cleanly separates Rust and frontend concerns
