---
name: sentry-claude-settings-audit
description: >
type: feature
---
  Audit and generate Claude Code settings.json for a repository. 4-phase process:
  detect tech stack, detect services, check existing settings, generate recommendations.
  Use when setting up or reviewing Claude Code configuration for a project.
type: feature
source: Sentry

# Claude Settings Audit

4-phase audit to generate optimal Claude Code `settings.json` for any repository.

## Phase 1: Detect Tech Stack

Scan the repository for language and framework markers:

```bash
# Python
test -f pyproject.toml && echo "python:pyproject"
test -f setup.py && echo "python:setup"
test -f requirements.txt && echo "python:requirements"
test -f Pipfile && echo "python:pipenv"

# JavaScript/TypeScript
test -f package.json && echo "node:npm"
test -f pnpm-lock.yaml && echo "node:pnpm"
test -f yarn.lock && echo "node:yarn"
test -f bun.lockb && echo "node:bun"
test -f tsconfig.json && echo "typescript"

# Go
test -f go.mod && echo "go"

# Rust
test -f Cargo.toml && echo "rust"

# Ruby
test -f Gemfile && echo "ruby"

# Docker
test -f Dockerfile && echo "docker"
test -f docker-compose.yml && echo "docker-compose"
```

### Framework Detection

```bash
# React / Next.js / Vite
grep -q "react" package.json 2>/dev/null && echo "react"
grep -q "next" package.json 2>/dev/null && echo "nextjs"
grep -q "vite" package.json 2>/dev/null && echo "vite"

# Django / Flask / FastAPI
grep -q "django" pyproject.toml 2>/dev/null && echo "django"
grep -q "flask" pyproject.toml 2>/dev/null && echo "flask"
grep -q "fastapi" pyproject.toml 2>/dev/null && echo "fastapi"

# Electron
grep -q "electron" package.json 2>/dev/null && echo "electron"
```

## Phase 2: Detect Services & Tools

Identify external services and development tools:

| Marker | Service |
|--------|---------|
| `.github/workflows/` | GitHub Actions CI |
| `sentry.properties` or `@sentry/` | Sentry error tracking |
| `.env` with `DATABASE_URL` | PostgreSQL/MySQL |
| `redis` in deps | Redis cache |
| `docker-compose.yml` | Docker orchestration |
| `.mcp.json` | MCP servers |
| `prometheus.yml` | Prometheus monitoring |

## Phase 3: Check Existing Settings

```bash
# Check for existing Claude config
cat .claude/settings.json 2>/dev/null || echo "No settings found"
cat .claude/settings.local.json 2>/dev/null || echo "No local settings"

# Check for other AI config
cat .cursorrules 2>/dev/null
cat .windsurfrules 2>/dev/null
cat CLAUDE.md 2>/dev/null | head -50
```

## Phase 4: Generate Recommendations

### Bash Command Allowlist by Stack

**Python:**
```json
{
  "permissions": {
    "allow": [
      "python *",
      "pip install *",
      "uv *",
      "pytest *",
      "ruff *",
      "black *",
      "mypy *",
      "bandit *"
    ]
  }
}
```

**Node.js / TypeScript:**
```json
{
  "permissions": {
    "allow": [
      "npm *",
      "npx *",
      "pnpm *",
      "node *",
      "tsc *",
      "eslint *",
      "prettier *",
      "vite *"
    ]
  }
}
```

**Go:**
```json
{
  "permissions": {
    "allow": [
      "go *",
      "golangci-lint *",
      "make *"
    ]
  }
}
```

**Docker:**
```json
{
  "permissions": {
    "allow": [
      "docker *",
      "docker-compose *"
    ]
  }
}
```

### MCP Server Suggestions

| Stack | Recommended MCP |
|-------|----------------|
| Any web project | `@anthropic-ai/mcp-server-playwright` |
| GitHub repos | `@anthropic-ai/mcp-server-github` |
| PostgreSQL | `@anthropic-ai/mcp-server-postgres` |
| File-heavy projects | `@anthropic-ai/mcp-server-filesystem` |
| Documentation needs | `context7` (npx) |

### Full Settings Template

```json
{
  "$schema": "https://raw.githubusercontent.com/anthropics/claude-code/main/settings-schema.json",
  "permissions": {
    "allow": [
      "python *",
      "pip install *",
      "pytest *",
      "ruff *",
      "npm *",
      "npx *",
      "git *",
      "make *"
    ],
    "deny": [
      "rm -rf /",
      "curl * | sh",
      "wget * | sh"
    ]
  },
  "env": {
    "PYTHONDONTWRITEBYTECODE": "1"
  }
}
```

## Output Format

Generate a complete `.claude/settings.json` with:
1. Stack-appropriate bash command allowlist
2. Relevant MCP server configurations
3. Environment variables for the detected stack
4. Deny list for dangerous commands
