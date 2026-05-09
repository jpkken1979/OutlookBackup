---
type: feature
name: git-pushing
description: Stage, commit, and push git changes with conventional commit messages. Use when user wants to commit and push changes, mentions pushing to remote, or asks to save and push their work. Also activates when user says "push changes", "commit and push", "push this", "push to github", or similar git workflow requests.
---

# Git Push Workflow

Detect current git state, decide whether to group or separate pending changes, create conventional commits, push, and verify repository cleanliness post-push.

## When to Use

Automatically activate when the user:

- Explicitly asks to push changes ("push this", "commit and push")
- Mentions saving work to remote ("save to github", "push to remote")
- Completes a feature and wants to share it
- Says phrases like "let's push this up" or "commit these changes"

## Workflow

**ALWAYS use the script** - do NOT use manual git commands:

```bash
bash .agent/skills/git-pushing/scripts/smart_commit.sh
```

With custom message:

```bash
bash .agent/skills/git-pushing/scripts/smart_commit.sh "feat(core): add feature"
```

With explicit grouping mode:

```bash
bash .agent/skills/git-pushing/scripts/smart_commit.sh "fix(ci): adjust pipeline" --group
bash .agent/skills/git-pushing/scripts/smart_commit.sh "fix(parser): commit staged only" --separate
```

Script handles:
- Detection of `staged`, `unstaged`, and `untracked` changes before commit
- Interactive prompt to **group** all changes or **separate** and commit only staged files when mixed state is detected
- Conventional commit creation
- Push to current branch with upstream configuration when needed
- Post-push `git status --porcelain` verification and clean/dirty report

## Important Rules

- Never append AI attribution or co-authored footer automatically
- If there are no changes, do not create empty commits
- If the repository is still dirty after push, report it explicitly
