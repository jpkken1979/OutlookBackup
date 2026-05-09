---
name: ce-test-browser
description: "Run browser E2E tests en páginas afectadas por PR o branch actual."
argument-hint: "[PR number | branch name | 'current' | --port PORT]"
---

# Browser Test Skill

## Workflow

1. Verify `agent-browser` installed
2. Determine test scope (PR/files)
3. Map files to routes
4. Detect dev server port
5. Verify server running
6. Test each affected page
7. Handle failures
8. Present summary

## Prerequisites

- Dev server running
- `agent-browser` CLI installed

## Usage

```
/ce-test-browser current
/ce-test-browser --port 3000
```

## Scope Detection

- PR number: usa `gh pr view <n> --json files` para detectar archivos cambiados
- Branch name: usa `git diff main...<branch> --name-only`
- Current: usa `git diff --name-only` del unstaged
- Files: mappea .ts/.tsx → routes de Next.js/React, detecta dev server port