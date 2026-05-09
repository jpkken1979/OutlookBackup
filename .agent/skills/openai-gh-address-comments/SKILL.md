---
name: openai-gh-address-comments
description: >
type: feature
---
  Systematically address GitHub PR review comments. Read comments, categorize
  by type, apply fixes, respond to reviewers, and re-request review. Use when
  handling PR feedback from code reviewers.
source: OpenAI
type: feature
---

# Address GitHub PR Comments

Systematic workflow for resolving PR review comments.

## Workflow

### Step 1: Gather All Comments

```bash
# List all review comments on the PR
gh pr view --comments
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments | jq '.[].body'

# Get review threads
gh api repos/{owner}/{repo}/pulls/{pr_number}/reviews
```

### Step 2: Categorize Comments

| Category | Action | Priority |
|----------|--------|----------|
| **Bug/Error** | Must fix | HIGH |
| **Security** | Must fix | CRITICAL |
| **Performance** | Should fix | MEDIUM |
| **Style/Nit** | Fix if easy | LOW |
| **Question** | Respond with explanation | MEDIUM |
| **Suggestion** | Evaluate and decide | MEDIUM |
| **Approval** | No action needed | — |

### Step 3: Address Each Comment

For each comment:

1. **Read carefully** — Understand what the reviewer is asking
2. **Agree or discuss** — If you disagree, explain why respectfully
3. **Make the change** — Apply the fix in code
4. **Respond** — Reply to the comment explaining what you did

### Step 4: Commit Fixes

```bash
# Stage and commit changes addressing review
git add -A
git commit -m "fix(scope): address PR review comments

- Fix null check in handler (reviewer: @alice)
- Add missing error handling (reviewer: @bob)
- Update docstring per style guide

Co-Authored-By: Claude <noreply@anthropic.com>"

git push
```

### Step 5: Respond to Thread

```bash
# Reply to specific review comment
gh api repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies \
  -f body="Fixed in latest commit. Added null check and test."
```

### Step 6: Re-request Review

```bash
gh pr edit {pr_number} --add-reviewer @alice,@bob
```

## Response Templates

### Agreeing and Fixing
```
Good catch! Fixed in [commit_sha]. Added null check and a test case for this edge case.
```

### Disagree with Explanation
```
I considered this approach, but went with the current one because:
1. [Reason 1]
2. [Reason 2]

Happy to discuss further — would you prefer I change it?
```

### Asking for Clarification
```
Could you clarify what you mean by "simplify this"? I see two options:
1. Extract to a helper function
2. Use a built-in library method

Which do you prefer?
```

### Acknowledging Nit
```
Good nit, fixed! ✓
```

## Anti-Patterns

| Anti-Pattern | Better Approach |
|-------------|----------------|
| Ignoring comments | Address every comment, even with "Acknowledged" |
| Bulk "fixed" reply | Reply individually with what was fixed |
| Defensive responses | Thank reviewer, explain reasoning calmly |
| Force-pushing without notice | Comment before force-push so reviewers know |
| Mixing review fixes with new features | Keep review-fix commits separate |

## Checklist

- [ ] All comments read and categorized
- [ ] Bug/security comments fixed first
- [ ] Each comment responded to individually
- [ ] Changes committed with descriptive message
- [ ] Tests pass after changes
- [ ] Re-requested review from original reviewers
