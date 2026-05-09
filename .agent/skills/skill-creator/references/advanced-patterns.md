# Advanced Skill Patterns

Patterns for building powerful skills beyond basic instructions.

## Contents
- Subagent execution patterns
- Dynamic context injection
- Visual output generation
- Feedback loop patterns
- Plan-validate-execute pattern
- Checklist-driven workflows
- MCP tool references
- Conditional workflow routing
- Skill composition
- Hot reload
- Monorepo support
- Context budget

---

## Subagent Execution

Run skills in isolated contexts with `context: fork`. The skill content becomes the subagent's task.

### Research skill (read-only)

```yaml
---
name: deep-research
description: Researches a topic thoroughly across the codebase
context: fork
agent: Explore
---

Research $ARGUMENTS thoroughly:

1. Find relevant files using Glob and Grep
2. Read and analyze the code
3. Summarize findings with specific file:line references
```

### Parallel batch processing

```yaml
---
name: batch-refactor
description: Refactors multiple files in parallel
context: fork
agent: general-purpose
disable-model-invocation: true
---

Refactor all files matching the pattern described below.
For each file, apply the transformation independently.

Target: $ARGUMENTS
```

### Architecture planning

```yaml
---
name: plan-feature
description: Plans feature implementation with architectural analysis
context: fork
agent: Plan
---

Plan the implementation of: $ARGUMENTS

1. Analyze current architecture
2. Identify affected components
3. Propose implementation strategy
4. List risks and mitigations
```

**Key rule**: `context: fork` only works with explicit task instructions. A skill with only guidelines (no task) produces no meaningful output in a subagent.

---

## Dynamic Context Injection

Fetch live data with `` !`command` `` preprocessing:

### Git-aware deployment

```yaml
---
name: deploy-check
description: Checks deployment readiness
disable-model-invocation: true
---

## Current state
- Branch: !`git branch --show-current`
- Uncommitted changes: !`git status --porcelain | wc -l`
- Last tag: !`git describe --tags --abbrev=0 2>/dev/null || echo "no tags"`
- CI status: !`gh run list --limit 1 --json status --jq '.[0].status' 2>/dev/null || echo "unknown"`

## Deployment checklist
Based on the state above, determine if deployment is safe.
```

### PR review with full context

```yaml
---
name: review-pr
description: Reviews a pull request with full diff context
context: fork
agent: Explore
allowed-tools: Bash(gh *)
---

## Pull request
- Diff: !`gh pr diff`
- Comments: !`gh pr view --comments`
- Changed files: !`gh pr diff --name-only`

Review this PR for:
1. Correctness and potential bugs
2. Performance implications
3. Security concerns
4. Test coverage gaps
```

---

## Visual Output Generation

Skills can generate interactive HTML visualizations:

```yaml
---
name: visualize-deps
description: Generates interactive dependency graph visualization
allowed-tools: Bash(python *)
---

Generate an interactive HTML dependency graph:

```bash
python ${CLAUDE_SKILL_DIR}/scripts/visualize_deps.py .
```

This creates `deps-graph.html` and opens it in the browser.
```

Bundle the Python script in `scripts/visualize_deps.py`. The script does the heavy lifting while Claude handles orchestration.

**Best patterns for visual output:**
- Dependency graphs
- Test coverage reports
- API documentation
- Database schema visualizations
- Codebase structure maps

---

## Feedback Loop Pattern

Run validator → fix errors → repeat. Greatly improves output quality.

```markdown
## Document editing process

1. Make edits to the target file
2. **Validate immediately**: `python scripts/validate.py output/`
3. If validation fails:
   - Review the error message carefully
   - Fix the issues
   - Run validation again
4. **Only proceed when validation passes**
5. Run final verification: `python scripts/verify.py output/`
```

**For skills without scripts**, use reference documents as validators:

```markdown
## Content review process

1. Draft content following STYLE_GUIDE.md guidelines
2. Review against the checklist:
   - Terminology consistency
   - Example format compliance
   - Required sections present
3. If issues found → revise → review again
4. Finalize only when all checks pass
```

---

## Plan-Validate-Execute Pattern

For complex, multi-step operations that could go wrong:

```markdown
## Batch update workflow

1. **Plan**: Generate `changes.json` with proposed modifications
2. **Validate**: `python scripts/validate_plan.py changes.json`
   - Checks for conflicts, missing references, invalid values
   - Reports specific errors with fix suggestions
3. **Execute**: `python scripts/apply_changes.py changes.json`
4. **Verify**: `python scripts/verify_output.py`

If validation fails, iterate on the plan before executing.
```

**When to use**: Batch operations, destructive changes, complex validation rules.

**Tip**: Make validation scripts verbose with specific error messages like `"Field 'email' not found. Available fields: name, address, phone"`.

---

## Checklist-Driven Workflows

For multi-step processes, provide a checklist Claude can track:

````markdown
## Migration workflow

Copy this checklist and track progress:

```
Migration Progress:
- [ ] Step 1: Analyze current implementation
- [ ] Step 2: Create migration plan
- [ ] Step 3: Implement changes
- [ ] Step 4: Run test suite
- [ ] Step 5: Verify backward compatibility
- [ ] Step 6: Update documentation
```

**Step 1: Analyze current implementation**
Read all files in the target module. Document the current API surface.

**Step 2: Create migration plan**
...
````

---

## MCP Tool References

When skills use MCP tools, always use fully qualified names:

```markdown
Use the BigQuery:bigquery_schema tool to retrieve schemas.
Use the GitHub:create_issue tool to create issues.
```

Format: `ServerName:tool_name`. Without the server prefix, Claude may fail to locate the tool when multiple MCP servers are available.

---

## Conditional Workflow Routing

Guide Claude through decision points:

```markdown
## Document modification

1. Determine the type:
   **Creating new?** → Follow "Creation workflow" below
   **Editing existing?** → Follow "Editing workflow" below

2. Creation workflow:
   - Use template from assets/
   - Build from scratch
   - Export to target format

3. Editing workflow:
   - Analyze existing structure
   - Make targeted modifications
   - Validate after each change
```

**Tip**: If workflows become large, push them to separate files:

```markdown
## Workflow selection

Based on the task:
- **Creating new content**: See [references/creation-workflow.md](references/creation-workflow.md)
- **Editing existing content**: See [references/editing-workflow.md](references/editing-workflow.md)
- **Migrating content**: See [references/migration-workflow.md](references/migration-workflow.md)
```

---

## Skill Composition

Chain multiple skills for complex tasks:

```markdown
## Complex analysis workflow

1. Use the `data-extraction` skill to parse input files
2. Use the `statistical-analysis` skill to process the data
3. Use the `report-generation` skill to create the output

Each skill handles its domain; this skill orchestrates the pipeline.
```

In the Antigravity ecosystem, use `skill_composition_engine.py` for programmatic pipelines.

---

## Hot Reload

Skills in `~/.claude/skills/` and `.claude/skills/` are **automatically detected and loaded** when created or modified — no session restart needed. This applies to:

- New skill directories added while a session is active
- Modifications to existing SKILL.md files
- Changes to frontmatter metadata

**Implication for development**: Use the Claude A/B testing pattern (see SKILL.md Step 7) without restarting sessions. Edit the skill in one terminal, test immediately in another.

---

## Monorepo Support

Nested `.claude/skills/` directories are auto-discovered. If Claude is editing files in `packages/frontend/`, skills from `packages/frontend/.claude/skills/` are also loaded.

```
monorepo/
├── .claude/skills/           # Root skills (always loaded)
│   └── shared-conventions/
├── packages/
│   ├── frontend/
│   │   └── .claude/skills/   # Loaded when editing frontend/
│   │       └── react-patterns/
│   └── backend/
│       └── .claude/skills/   # Loaded when editing backend/
│           └── api-patterns/
```

Skills from `--add-dir` directories are also loaded and support live change detection.

---

## Context Budget

Skill descriptions (Level 1 metadata) compete for a shared context budget:

- **Budget**: 2% of the context window (~16,000 characters fallback)
- **Override**: Set `SLASH_COMMAND_TOOL_CHAR_BUDGET` environment variable
- **Implication**: With 30+ skills, keep descriptions concise. Long descriptions eat into the budget and may cause other skills to be excluded.

**Recommendations:**
- Limit to **20-30 high-quality skills** per project
- Keep descriptions under 200 characters when possible
- Use specific trigger keywords rather than verbose explanations
- If activation is unreliable, consider a `UserPromptSubmit` hook that reminds Claude to evaluate skills
