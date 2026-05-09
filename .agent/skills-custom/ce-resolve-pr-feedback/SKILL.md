---
name: ce-resolve-pr-feedback
description: "Resolve PR comments conversationally. Reads PR comments, interprets feedback, generates responses."
argument-hint: "[PR reference]"
---

# PR Feedback Resolver

Reads and resolves GitHub PR comments conversationally, classifying each and generating appropriate responses.

## Workflow

1. **Fetch PR comments** via `gh pr view <ref> --json comments`
2. **Classify each comment** into one of:
   - `change_request`: actionable, requires code change
   - `question`: clarification needed before proceeding
   - `approval`: acknowledged, no action required
   - `suggestion`: optional improvement, acknowledge and thank
3. **For each `change_request`**: generate a response + proposed code fix
4. **For `suggestion`**: acknowledge and thank the reviewer
5. **For `question`**: provide a clear answer
6. **Summarize**: resolved vs pending items

## Comment Classification Logic

| Type | Indicator | Action |
|------|-----------|--------|
| `change_request` | "please change", "should be", "needs to", "must", "fix:" | Generate code response |
| `question` | "?", "can you explain", "why is", "how does" | Answer directly |
| `approval` | "LGTM", "looks good", "approved", :+1: | Acknowledge |
| `suggestion` | "nit:", "suggestion:", "optional", "consider" | Thank + note |

## Output Format

```
## Comment Analysis

| Reviewer | Type | Summary | Action |
|----------|------|---------|--------|
| @user1 | change_request | Update error handling | Code fix proposed |
| @user2 | suggestion | Typo in variable name | Acknowledged |

## Responses Generated

### @user1 — Change Request
**Comment**: <quote>
**Response**: <response text>
**Proposed Fix**:
\`\`\`diff
<diff>
\`\`\`

## Pending
- Item needing resolution before merge
```

## Implementation Notes

- Uses `gh pr view <ref> --json comments,author` to fetch comment data
- Generates responses in Spanish (per project language policy)
- Marks approvals as resolved immediately
- change_requests include proposed code diff when applicable
