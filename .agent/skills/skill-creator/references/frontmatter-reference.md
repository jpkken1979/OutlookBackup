# Frontmatter Reference

Complete reference for all YAML frontmatter fields in SKILL.md.

## Contents
- Required fields (name, description)
- Invocation control (disable-model-invocation, user-invocable)
- Tool restrictions (allowed-tools)
- Subagent execution (context, agent)
- Model selection (model)
- Arguments (argument-hint)
- Hooks (hooks)
- String substitutions

---

## Required Fields

### `name`
- **Type**: string
- **Required**: No (defaults to directory name), but recommended
- **Constraints**: lowercase letters, numbers, hyphens only. Max 64 chars. Cannot contain "anthropic" or "claude".
- **Convention**: Prefer gerund form (verb + -ing): `processing-pdfs`, `analyzing-data`

```yaml
name: processing-pdfs
```

### `description`
- **Type**: string
- **Required**: Recommended (falls back to first paragraph if omitted)
- **Constraints**: Max 1024 chars. No angle brackets (`<`, `>`). No XML tags.
- **Critical**: This is the PRIMARY triggering mechanism. Claude uses it to decide when to use the skill.

**Rules for effective descriptions:**
1. Write in **third person** ("Processes files", not "I process files")
2. Include both **what it does** AND **when to use it**
3. Include all **trigger keywords** users might say
4. Be "pushy" — Claude undertriggers by default

**Formula**: `[What it does]. Use when [trigger scenarios].`

```yaml
description: >-
  Extracts text and tables from PDF files, fills forms, merges documents.
  Use when working with PDF files or when the user mentions PDFs, forms,
  or document extraction.
```

**Activation rate by description quality:**

| Description quality | Activation rate |
|---|---|
| Vague ("Helps with documents") | ~20% |
| Specific but no triggers | ~50% |
| Specific + trigger keywords | ~72% |
| Specific + triggers + examples | ~90% |

---

## Invocation Control

### `disable-model-invocation`
- **Type**: boolean
- **Default**: `false`
- **Effect**: When `true`, only the user can invoke with `/skill-name`. Claude cannot trigger it automatically. The description is NOT loaded into context.

**Use for**: Skills with side effects — `/deploy`, `/commit`, `/send-message`

```yaml
disable-model-invocation: true
```

### `user-invocable`
- **Type**: boolean
- **Default**: `true`
- **Effect**: When `false`, the skill is hidden from the `/` menu. Only Claude can invoke it. The description IS loaded into context.

**Use for**: Background knowledge — `legacy-system-context`, `api-conventions`

```yaml
user-invocable: false
```

### Invocation matrix

| Setting | User invokes | Claude invokes | In context |
|---|:---:|:---:|:---:|
| Default | Yes | Yes | Description only |
| `disable-model-invocation: true` | Yes | No | Not loaded |
| `user-invocable: false` | No | Yes | Description only |

---

## Tool Restrictions

### `allowed-tools`
- **Type**: string (comma-separated tool names)
- **Effect**: Tools Claude can use without asking permission when the skill is active. Does not override deny rules.

```yaml
# Read-only mode
allowed-tools: Read, Grep, Glob

# Allow specific bash patterns
allowed-tools: Read, Grep, Bash(python *), Bash(npm test *)

# Full access (use carefully)
allowed-tools: Read, Write, Edit, Bash, Glob, Grep
```

---

## Subagent Execution

### `context`
- **Type**: `"fork"`
- **Effect**: Runs the skill in an isolated subagent. The skill content becomes the subagent's task. No access to conversation history.

**Only use when**: The skill has explicit task instructions. Guidelines-only skills without a task will produce no output.

```yaml
context: fork
```

### `agent`
- **Type**: string
- **Default**: `"general-purpose"`
- **Options**: Built-in (`Explore`, `Plan`, `general-purpose`) or custom agents from `.claude/agents/`

**Use with**: `context: fork`

```yaml
context: fork
agent: Explore    # Read-only exploration
```

**Agent selection guide:**

| Agent | Best for |
|---|---|
| `Explore` | Research, code analysis, read-only tasks |
| `Plan` | Architecture design, implementation planning |
| `general-purpose` | Full implementation tasks |
| Custom agent | Specialized workflows |

---

## Model Selection

### `model`
- **Type**: string (model ID)
- **Effect**: Override the model used when this skill is active.

```yaml
model: claude-haiku-4-5-20251001    # Fast, economical
model: claude-sonnet-4-6            # Balanced
model: claude-opus-4-6              # Maximum reasoning
```

---

## Arguments

### `argument-hint`
- **Type**: string
- **Effect**: Shown during autocomplete to indicate expected arguments.

```yaml
argument-hint: "[issue-number]"
argument-hint: "[filename] [format]"
argument-hint: "[component-name] [source-framework] [target-framework]"
```

---

## Hooks

### `hooks`
- **Type**: object
- **Effect**: Hooks scoped to this skill's lifecycle. Only run when this skill is active.

**Supported hook events:**

| Event | When it fires | Can modify? |
|---|---|---|
| `PreToolUse` | Before tool execution | Yes — can block or modify tool inputs |
| `PostToolUse` | After successful tool completion | No |
| `PostToolUseFailure` | After tool failure | No |
| `UserPromptSubmit` | Before Claude processes user prompt | Yes — can enrich or reject |
| `PermissionRequest` | When a permission decision is needed | Yes — allow/deny/ask |
| `Stop` | When the agent finishes responding | No |
| `SubagentStop` | When a subagent finishes | No |
| `TaskCompleted` | On task completion | No |
| `TeammateIdle` | Multi-agent: when a teammate becomes idle | No |

**Hook types:** Each event supports 4 hook types:
- `command` — Shell command (exit code 2 = deny)
- `HTTP` — HTTP request to external service
- `prompt` — LLM-evaluated prompt
- `agent` — Spawns an agentic verifier with tool access

**Example — validate before edits:**

```yaml
hooks:
  PreToolUse:
    - matcher: Edit
      command: "python ${CLAUDE_SKILL_DIR}/scripts/validate.py"
```

**Example — enrich user prompts with context:**

```yaml
hooks:
  UserPromptSubmit:
    - command: "echo 'Remember to evaluate available skills before starting'"
```

---

## String Substitutions

Available in skill body content (not in frontmatter):

| Variable | Description | Example |
|---|---|---|
| `$ARGUMENTS` | All arguments as a string | `/fix 123` → `"123"` |
| `$ARGUMENTS[0]` or `$0` | First argument | Position-based access |
| `$ARGUMENTS[1]` or `$1` | Second argument | Position-based access |
| `${CLAUDE_SESSION_ID}` | Current session ID | For logging, correlation |
| `${CLAUDE_SKILL_DIR}` | Skill directory path | Reference bundled scripts |

If `$ARGUMENTS` is not present in the content, arguments are appended as `ARGUMENTS: <value>`.

**Example skill using substitutions:**

```yaml
---
name: migrate-component
description: Migrates a component between frameworks
argument-hint: "[component] [from-framework] [to-framework]"
---

Migrate the $0 component from $1 to $2.
Preserve all existing behavior and tests.
Run validation: python ${CLAUDE_SKILL_DIR}/scripts/validate.py
```

---

## Dynamic Context Injection

Run shell commands before Claude sees the content with `` !`command` ``:

```yaml
---
name: repo-status
description: Analyzes current repository state
---

## Current state
- Branch: !`git branch --show-current`
- Status: !`git status --short`
- Recent commits: !`git log --oneline -5`

Analyze the current state and suggest next steps.
```

Commands execute as preprocessing — Claude only sees the output. Use for fetching live data (git state, API responses, file listings).

---

## Extended Thinking

Include the word **"ultrathink"** anywhere in skill content to enable extended thinking mode. Use for complex reasoning tasks.

```yaml
---
name: deep-analysis
description: Performs deep code analysis with extended reasoning
---

ultrathink

Analyze the following codebase for architectural issues...
```
