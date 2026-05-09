---
name: openai-yeet
description: >
type: feature
---
  Git workflow automation: stage, commit, push, and open a draft PR in one
  flow. Creates codex/{description} branches with conventional commits.
  Use when you want to quickly ship changes as a PR.
source: OpenAI (codex-universal)
type: feature
---

# Yeet — Ship Changes Fast

Stage, commit, push, and open a draft PR in a single flow.

## Workflow

### Step 1: Create Branch
```bash
# Create descriptive branch from current state
git checkout -b codex/$(echo "description of change" | tr ' ' '-' | tr '[:upper:]' '[:lower:]')
```

### Step 2: Stage Changes
```bash
# Stage all changes
git add -A

# Or stage specific files
git add path/to/file1 path/to/file2

# Review what's staged
git diff --cached --stat
```

### Step 3: Commit
```bash
# Write a conventional commit message
git commit -m "feat(scope): description of the change"
```

Commit format: `<type>(<scope>): <description>`
- `feat` — New feature
- `fix` — Bug fix
- `refactor` — Code restructuring
- `docs` — Documentation only
- `test` — Adding/fixing tests
- `chore` — Maintenance

### Step 4: Push
```bash
git push -u origin HEAD
```

### Step 5: Open Draft PR
```bash
gh pr create --draft \
  --title "feat(scope): description" \
  --body "## Changes

- What changed and why
- Any notable decisions

## Testing

- How the changes were tested"
```

## One-Liner
```bash
git add -A && \
git commit -m "feat(scope): description" && \
git push -u origin HEAD && \
gh pr create --draft --title "feat(scope): description" --body "Description of changes"
```

## Tips
- Always create a new branch — never push directly to `main`
- Use `--draft` to signal the PR is ready for initial review but not merge
- Include `Co-Authored-By: Claude <noreply@anthropic.com>` in commit body when AI-assisted
- Use `gh pr ready <pr-number>` to mark as ready for review when done
- Use `gh pr merge <pr-number> --squash` to merge when approved
