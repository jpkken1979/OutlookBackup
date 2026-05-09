---
name: ce-clean-gone-branches
description: "Clean up local branches whose remote tracking branch is gone. Use when user says 'clean up branches', 'delete gone branches', 'prune local branches', 'clean gone'."
---

# Clean Gone Branches

## Workflow

1. **Discover:** run `scripts/clean-gone` to find gone branches
2. **Present and ask confirmation:** show list, ask user to confirm
3. **Delete:** remove worktree if exists, then `git branch -D`

## Script

Uses `git worktree list` to detect associated worktrees before deletion.
