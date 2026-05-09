# Antigravity Ecosystem Integration

How to create skills that integrate with the Antigravity agent ecosystem.

## Contents
- Skill placement and locations
- Naming conventions
- Agent-skill relationship
- Skill composition pipelines
- Testing skills
- Quality standards

---

## Skill Locations

| Location | Path | Purpose | Who uses it |
|---|---|---|---|
| Base skills | `.agent/skills/` | Core ecosystem skills (788) | All agents via orchestrator |
| Custom skills | `.agent/skills-custom/` | Project-specific skills (9) | Project agents |
| Claude Code skills | `.claude/skills/` | Claude Code IDE integration | Claude Code sessions |
| Plugin skills | `.agent/plugins/*/` | Plugin-provided skills (140) | Plugin consumers |
| Personal skills | `~/.claude/skills/` | User-wide skills | All Claude Code projects |

**Decision guide:**
- Creating a general-purpose skill for the ecosystem → `.agent/skills/`
- Creating a project-specific skill → `.agent/skills-custom/`
- Creating a Claude Code IDE skill → `.claude/skills/`
- Creating a skill inside a plugin → `.agent/plugins/<plugin>/`

---

## Naming Conventions

### For `.agent/skills/` (ecosystem skills)

Follow the existing pattern observed in 788 skills:

- **Format**: `<scope>-<action>` or `<tool>-<capability>`
- **Examples**: `cc-skill-security-review`, `api-documentation-generator`, `python-development-python-scaffold`
- **Prefixes**:
  - `cc-skill-*` — Claude Code specific
  - `uns-*` — UNS enterprise specific
  - No prefix — general purpose

### For `.claude/skills/` (Claude Code skills)

- **Format**: gerund form (verb + -ing) preferred
- **Examples**: `processing-pdfs`, `analyzing-data`, `deploying-apps`

---

## Agent-Skill Relationship

The 40 agents in `.agent/agents/` consume skills via the orchestrator. When creating a skill, consider which agents will use it:

| Agent | Typical skills consumed |
|---|---|
| `explorer` | Code analysis, search patterns |
| `architect` | Design patterns, architecture templates |
| `security-auditor` | Security review checklists, vulnerability patterns |
| `test-engineer` | Testing patterns, test generation |
| `frontend-specialist` | UI patterns, component templates |
| `documentation-writer` | Doc generation, API docs |
| `devops-engineer` | CI/CD patterns, deployment scripts |
| `performance-optimizer` | Profiling scripts, optimization patterns |

### Making skills agent-compatible

Skills in `.agent/skills/` should follow these conventions for agent consumption:

1. **SKILL.md must exist** with valid YAML frontmatter (name + description)
2. **Scripts must be executable** and handle errors explicitly
3. **No interactive prompts** — agents run autonomously
4. **Output should be structured** (JSON preferred for programmatic consumption)

---

## Skill Composition Pipelines

The `skill_composition_engine.py` in `.agent/core/` enables chaining skills:

```python
# Conceptual pipeline (executed by orchestrator)
pipeline = [
    {"skill": "data-extraction", "input": "raw_data.csv"},
    {"skill": "statistical-analysis", "input": "$previous_output"},
    {"skill": "report-generation", "input": "$previous_output"},
]
```

When creating skills meant for pipelines:
- Define clear **inputs** and **outputs** in the SKILL.md
- Use structured output formats (JSON, structured markdown)
- Make the skill self-contained (don't assume context from other skills)

---

## Testing Skills

### Ecosystem validation

```bash
# Validate all skills structure
python .agent/scripts/validate_ecosystem.py

# Health check specific skill
python .agent/scripts/skill_health_check.py

# Security scan
python .agent/scripts/scan_skills.py --fail-on-high

# Run skill-specific tests
make test-skills
```

### Skill quality scoring

```bash
# Score a skill (0-100)
python .agent/skills/skill-creator/scripts/score_skill.py .agent/skills/<skill-name>
```

The scorer evaluates:
- Frontmatter completeness and description quality
- Body length compliance (< 500 lines)
- Reference file organization
- Script quality (error handling, documentation)
- Overall structure adherence

---

## Quality Standards

### Minimum requirements for `.agent/skills/`

- [ ] SKILL.md exists with valid YAML frontmatter
- [ ] `name` field matches directory name
- [ ] `description` field is specific and includes trigger keywords
- [ ] Body is under 500 lines
- [ ] No hardcoded secrets or paths
- [ ] Scripts use `pathlib.Path` (not `os.path`)
- [ ] Scripts include `encoding="utf-8"` in `open()` calls
- [ ] No `shell=True` in subprocess calls

### Recommended for high-quality skills

- [ ] References use progressive disclosure pattern
- [ ] Scripts handle errors explicitly
- [ ] 3+ evaluation scenarios documented
- [ ] Table of contents in reference files > 100 lines
- [ ] Consistent terminology throughout
- [ ] Concrete examples with real scenarios
