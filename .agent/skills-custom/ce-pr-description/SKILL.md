---
name: ce-pr-description
description: "Write or regenerate a value-first pull-request description (title + body) for the current branch's commits."
argument-hint: "[PR ref e.g. pr:561 | #561 | URL] [free-text steering]"
---

# PR Description Generator

Generates structured, value-first pull-request descriptions from branch commits using the GitHub CLI (`gh`).

## Workflow

1. **Parse PR reference** from argument (URL, `pr:number`, `#number`, or current branch)
2. **Fetch commits** from the branch via `gh pr view`
3. **Generate PR title**
   - Imperative mood, max 72 characters
   - Reflects the primary change or intent
4. **Generate PR body**
   - **Summary**: 2-3 bullets describing what changed
   - **Motivation**: why this change was necessary
   - **How to test**: verification steps the reviewer can follow
5. **Return structured output**: `{title, body}`
6. **Apply** via `gh pr create` or `gh pr edit`

## Output Format

```
title: <imperative title, max 72 chars>

---

## Summary
- <bullet 1>
- <bullet 2>
- <bullet 3>

## Motivation
<paragraph explaining why>

## How to Test
- <step 1>
- <step 2>
- <step 3>
```

## Implementation Notes

- Uses `gh pr view <ref> --json commits,title,body` to fetch existing PR data
- Uses `gh pr create --title ... --body ...` or `gh pr edit`
- Falls back to branch name for title if no commits found
- All content is generated in Spanish (per project language policy)
- Respects conventional commit format when parsing commit messages
