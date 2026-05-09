---
name: ce-worktree
description: "Git worktree manager mejorado con .env sync, safety rules, y branch-aware trust para dev tools."
argument-hint: "[create|list|switch|cleanup] [branch-name]"
---

# Git Worktree Manager — Enhanced Edition

## Commands

- `create <branch> [from-branch]` — crea worktree + copia .env
- `list` — lista worktrees activos
- `switch <name>` — cambia a worktree
- `cleanup` — limpia worktrees huerfanos

## Features

1. **.env sync** — copia .env del main repo al worktree nuevo
2. **Safety rules** — no permite crear worktree si hay cambios sin commitear
3. **Branch-aware dev tools** — mise/direnv configs copiados con branch-specific overrides
4. **.gitignore management** — maneja `.worktrees/` folder

## Script: worktree-manager.sh

Always use `worktree-manager.sh` script, never `git worktree add` directly.

## Usage

```bash
# Create a new worktree from main
./scripts/worktree-manager.sh create my-feature

# Create from a specific branch
./scripts/worktree-manager.sh create my-feature main

# List all worktrees
./scripts/worktree-manager.sh list

# Switch to a worktree
./scripts/worktree-manager.sh switch my-feature

# Cleanup orphaned worktrees
./scripts/worktree-manager.sh cleanup
```

## Safety Rules

- Bloquea creacion si hay cambios sin commitear en working tree
- Valida que el branch no exista antes de crear
- Verifica que el directorio de worktree no exista
- Confirma antes de cleanup de worktrees huerfanos
