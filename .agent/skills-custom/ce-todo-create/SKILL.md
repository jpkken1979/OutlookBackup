---
name: ce-todo
description: "Unified todo skill: create, resolve, or triage findings in the Compound Engineering workflow."
argument-hint: "--action create|resolve|triage [args]"
---

# ce-todo

Unified skill for the Compound Engineering todo workflow. Handles creation, resolution, and triage of structured findings stored as markdown files.

## Storage

```
~/.antigravity/todos/
  NNN-pending-pN-<slug>.md   # pending todos
  NNN-ready-pN-<slug>.md     # approved todos (ready to resolve)
  NNN-complete-pN-<slug>.md  # resolved todos
```

If the directory does not exist, it is created automatically.

## Frontmatter Schema

```yaml
---
severity: p1|p2|p3        # P1=CRITICAL, P2=IMPORTANT, P3=NICE-TO-HAVE
category: string          # e.g. security, performance, correctness, ux
status: pending|ready|complete
description: string       # What was found
location: string         # File(s) or area affected
proposed_solution: string # How to fix it
created: YYYY-MM-DD
---
```

## Severity Guidelines

| Level | Label | Color | When to use |
|-------|-------|-------|-------------|
| P1 | CRITICAL | Red | Security vuln, data loss, crash, broken core flow |
| P2 | IMPORTANT | Yellow | Performance issue, significant bug, missing validation |
| P3 | NICE-TO-HAVE | Green | Polish, code quality, minor UX improvements |

## File Naming Convention

```
NNN-<status>-pN-<slug>.md
```

- `NNN`: 3-digit sequential number (auto-incremented)
- `<status>`: `pending`, `ready`, or `complete`
- `pN`: severity level
- `slug`: short kebab-case description

## Usage

```bash
# Create a todo
python scripts/main.py --action create --severity p1 --category security --description "Memory leak" --location "brain.py:45" --solution "Add cleanup on timeout"

# Triage pending todos
python scripts/main.py --action triage

# Resolve ready todos
python scripts/main.py --action resolve
```

## Actions

### create

Parses the finding description and creates a `pending` todo file. Auto-increments the sequence number.

**Example input**: `"memory leak in session handler at brain.py line 45"`

**Output file**: `001-pending-p1-memory-leak-session-handler.md`

### triage

Lists all pending todos sorted by severity (P1 first). For each one, the agent decides:
- `yes` — approve: upgrade status to `ready`
- `delete` — dismiss: remove the file
- `p1/p2/p3` — override severity and mark `ready`
- `next` — skip and leave as `pending`

**Triage Summary**:
```
TRIAGE COMPLETE
==============
Approved (ready): 5
Skipped (pending): 2
Dismissed: 1
Total processed: 8
```

### resolve

Processes all `ready` todos. For each one:
1. Read frontmatter (`location`, `proposed_solution`, `severity`)
2. Log that resolution would be applied (skill delegates to an executor)
3. Mark as `complete` in frontmatter and rename file

**Resolution Summary**:
```
RESOLUTION COMPLETE
==================
P1 resolved: 3
P2 resolved: 5
P3 resolved: 2
Failed: 0
Total: 10
```
