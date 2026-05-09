---
name: sentry-agents-md
description: >
type: feature
---
  Maintain AGENTS.md files following Sentry engineering practices. Symlink
  to CLAUDE.md, keep docs minimal and actionable, ensure proper skill discovery
  and required documentation sections. Use when creating or updating AGENTS.md.
type: feature
source: Sentry

# AGENTS.md Maintenance

Standards for maintaining AGENTS.md files following Sentry engineering practices.

## Core Principles

1. **Minimal** — Only include what agents need, not everything they could use
2. **Actionable** — Commands, not descriptions; examples, not theory
3. **Discoverable** — Skills and tools must be findable by agents
4. **Symlinked** — `CLAUDE.md` should be a symlink to `AGENTS.md`

## Required Sections

### 1. Package Manager & Build

```markdown
## Build & Run

Package manager: `uv` (or npm/pnpm/yarn)

```bash
uv sync                    # Install dependencies
uv run pytest              # Run tests
uv run ruff check .        # Lint
```
```

### 2. Commit Attribution

```markdown
## Commits

```
type(scope): description

Co-Authored-By: Claude <noreply@anthropic.com>
```
```

### 3. Key Conventions

```markdown
## Conventions

- Python 3.11+, strict typing
- Pydantic for data models
- Google-style docstrings
- ruff for linting, black for formatting
```

### 4. Architecture Overview

```markdown
## Architecture

- `src/core/` — Core business logic
- `src/api/` — API endpoints
- `tests/` — Test suite
```

## Symlink Setup

```bash
# CLAUDE.md should symlink to AGENTS.md
ln -sf AGENTS.md CLAUDE.md

# Verify
ls -la CLAUDE.md
# CLAUDE.md -> AGENTS.md
```

## Anti-Patterns

| Bad | Good |
|-----|------|
| Long prose explanations | Bullet points with commands |
| Duplicate info from README | Reference README, add agent-specific info |
| Listing every file | List key directories and their purpose |
| Outdated instructions | Keep in sync with actual tooling |
| Internal implementation details | Focus on "how to use" not "how it works" |

## Template

```markdown
# AGENTS.md

> Brief one-line project description

## Quick Start

```bash
uv sync && uv run pytest
```

## Build & Test

```bash
uv run pytest tests/ -v          # All tests
uv run pytest tests/ -x          # Stop on first failure
uv run ruff check .              # Lint
uv run ruff format .             # Format
uv run mypy src/                 # Type check
```

## Conventions

- Language: Python 3.11+, strict typing
- Models: Pydantic BaseModel
- Tests: pytest + pytest-asyncio
- Commits: `type(scope): description` in Spanish
- Security: No hardcoded secrets, no shell=True

## Architecture

```
src/
├── core/       # Business logic
├── api/        # API layer
├── models/     # Data models
└── utils/      # Shared utilities
tests/          # Test suite
```

## Key Files

| File | Purpose |
|------|---------|
| `pyproject.toml` | Dependencies and tool config |
| `src/core/main.py` | Entry point |
| `tests/conftest.py` | Shared fixtures |
```

## Maintenance Rules

1. **Update when tooling changes** — new deps, new scripts, new conventions
2. **Keep under 200 lines** — if longer, extract to referenced docs
3. **Test commands must work** — verify all listed commands actually run
4. **Version with code** — AGENTS.md changes should be part of relevant PRs
