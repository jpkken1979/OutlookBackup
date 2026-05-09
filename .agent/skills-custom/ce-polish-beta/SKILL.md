---
name: ce-polish-beta
description: "[BETA] Interactive design polish — start dev server, open feature in browser, iterate on improvements together."
argument-hint: "[PR number, branch name, or blank for current branch]"
---

# Polish — Interactive Design Polish Loop

## Phase 0: Get on the right branch

1. If PR/branch provided, checkout it (probe for existing worktrees first)
2. If blank, use current branch
3. Verify not on main/master

## Phase 1: Start dev server

### 1.1 Check for .claude/launch.json

Run `read-launch-json.sh`. Use it if found.

### 1.2 Auto-detect project type

Run `detect-project-type.sh` to identify framework:
- rails, next, vite, nuxt, astro, remix, sveltekit, procfile, unknown

Route to matching recipe for start command and port defaults.

### 1.3 Start server

Start dev server in background, log to temp file. Probe for up to 30s.

### 1.4 Open in browser

Use IDE's mechanism to open browser.

## Phase 2: Iterate

User browses, says what to improve, you fix. Dev server hot-reloads. Repeat until happy.

## Scripts

- `read-launch-json.sh` — launch.json reader
- `detect-project-type.sh` — project type classifier
- `resolve-port.sh` — port resolution cascade
