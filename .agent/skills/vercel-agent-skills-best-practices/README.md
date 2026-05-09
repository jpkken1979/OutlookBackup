# Vercel Agent Skills Best Practices

Comprehensive guide for creating high-quality, production-ready agent skills based on Vercel's Agent Skills specification and open standards.

## Overview

This skill teaches AI agents how to create **packaged, reusable instructions** following the [Agent Skills specification](https://agentskills.io/). Skills transition agents from "kind of works" to understanding "how we do things here" by providing centralized, on-demand expertise.

## What's Included

### Documentation
- **SKILL.md** - Main skill instructions following Vercel specification
- **references/skill-template.md** - Complete template for creating new skills
- **README.md** - This file

### Scripts
- **scripts/validate_skill.py** - Automated skill package validator

### Examples
- **examples/example-skill-simple.md** - Simple skill (API error responses)
- **examples/example-skill-with-scripts.md** - Complex skill with automation (database migrations)

## Quick Start

### Use This Skill

When creating new agent skills or refactoring existing ones:

```bash
# For AI agents (e.g., Claude Code)
/skill vercel-agent-skills-best-practices

# For manual reference
cat .agent/skills/vercel-agent-skills-best-practices/SKILL.md
```

### Validate Your Skill

```bash
# Validate a skill package
python .agent/skills/vercel-agent-skills-best-practices/scripts/validate_skill.py path/to/your-skill/

# Batch validation
python .agent/skills/vercel-agent-skills-best-practices/scripts/validate_skill.py --batch .agent/skills/*/
```

### Create a New Skill

```bash
# Copy template
cp -r .agent/skills/vercel-agent-skills-best-practices/references/skill-template.md \
      .agent/skills/my-new-skill/SKILL.md

# Edit with your content
code .agent/skills/my-new-skill/SKILL.md

# Validate
python .agent/skills/vercel-agent-skills-best-practices/scripts/validate_skill.py \
       .agent/skills/my-new-skill/
```

## Key Concepts

### What Are Agent Skills?

Agent skills are **packaged, reusable instructions** built on an open standard. They provide:

- **Centralized expertise** - Organizational knowledge and workflow patterns
- **On-demand guidance** - Context loaded when tasks match skill domains
- **Repeatable solutions** - Consistent execution across similar tasks
- **Version-controlled instructions** - Trackable, auditable agent behavior

### Problems Skills Solve

1. **Prompt Drift** - Inconsistent results from identical requests worded differently
2. **Lost Workflow Conventions** - Quality checks and decision criteria scattered across conversations
3. **Instruction Sprawl** - Bulky playbooks cluttering prompt context

### Three-Layer Architecture

1. **Metadata Index** - Lightweight catalog of available skills
2. **Full Content Loading** - On-demand loading when task matches
3. **Explicit Invocation** - Manual triggering for debugging/testing

## Skill Structure

### Required

- **SKILL.md** - Primary instruction file with YAML frontmatter

### Optional

- **scripts/** - Deterministic, auditable procedures
- **references/** - Supporting documentation (long specs, API docs)
- **assets/** - Templates, examples, configuration files
- **examples/** - Usage examples and test cases

## Naming Conventions

Skill names must:
- Match regex pattern: `^[a-z0-9]+(-[a-z0-9]+)*$`
- Be 1-64 characters
- Use lowercase only
- Separate words with single hyphens
- Match directory name exactly

✅ Good: `api-error-response`, `database-migration-validator`
❌ Bad: `API_Error_Response`, `db..migration`, `skill-name-`

## YAML Frontmatter

Required fields:
```yaml
---
name: skill-name-here
description: "Brief description (1-2 sentences)"
---
```

Recommended fields:
```yaml
version: 1.0.0
tags: [domain, technology]
author: Your Name
repository: https://github.com/your-org/skill
license: MIT
```

## Integration with Antigravity

This skill integrates seamlessly with Antigravity's 4-layer architecture:

| Layer | Antigravity | Vercel Skills |
|-------|-------------|---------------|
| **Layer 1: Directiva** | SKILL.md, IDENTITY.md | SKILL.md provides directives |
| **Layer 2: Contexto** | .context/, memory/ | references/ provides context |
| **Layer 3: Ejecución** | scripts/, src/ | scripts/ perform actions |
| **Layer 4: Observabilidad** | logs/, artifacts/ | logs/ track execution |

### Enhanced Metadata for Antigravity

Extend YAML frontmatter with Antigravity-specific fields:

```yaml
---
name: skill-name
description: "Skill description"
version: 1.0.0

# Antigravity extensions
antigravity:
  tier: 3
  compatible_agents: [planner, architect, explorer]
  required_tools: [file_read, file_write]
  mcp_servers: [github, linear]
  memory_usage: medium
  estimated_tokens: 2000
---
```

## Best Practices

### Focus on Repeatable Patterns

✅ Good skill candidates:
- Development processes (API routes, components, tests)
- Content creation (headlines, documentation, marketing)
- Support operations (ticket triage, escalation)
- Data analysis (cleaning, visualization, reporting)

❌ Poor skill candidates:
- One-off tasks without repeat value
- Too generic without specific patterns
- Tool-specific (better served by tool docs)
- Constantly changing requirements

### Avoid Information Duplication

Don't replicate content between SKILL.md and references/. Use grep patterns:

```markdown
For authentication details:
`grep -A 20 "OAuth 2.0 Flow" references/api-spec.md`
```

### Modular Organization

- Each skill focuses on ONE workflow or pattern
- Clear boundaries without overlaps
- Independently usable
- Single Responsibility Principle

### Progressive Disclosure

Structure from simple to complex:
1. Quick Start (5 minutes)
2. Intermediate Usage (15 minutes)
3. Advanced Patterns (30 minutes)
4. Reference (complete details)

## Security Guidelines

Before deploying:

- [ ] Review all scripts for malicious code
- [ ] Check for hardcoded secrets/credentials
- [ ] Validate input sanitization
- [ ] Audit external dependencies
- [ ] Verify file permission requirements
- [ ] Test rollback procedures
- [ ] Document security considerations

## Testing and Validation

### Automated Validation

```bash
# Run validator
python scripts/validate_skill.py .

# Example output:
# 🔍 Validating skill: vercel-agent-skills-best-practices
#
# ✅ SKILL.md exists
# ✅ YAML frontmatter valid
# ✅ Name pattern valid: 'vercel-agent-skills-best-practices'
# ✅ Directory name matches skill name
# ✅ Required field 'name' present
# ✅ Required field 'description' present
# ...
#
# ✅ Validation PASSED
```

### Cross-Agent Testing

Test with multiple LLMs:
- Claude (Anthropic)
- GPT-4 (OpenAI)
- Gemini (Google)
- Local models (Ollama)

### Quality Checklist

- [ ] Name follows regex pattern
- [ ] YAML frontmatter valid
- [ ] Description clear and concise
- [ ] Instructions step-by-step
- [ ] Examples cover common/edge cases
- [ ] Safety considerations documented
- [ ] Scripts tested and documented
- [ ] No information duplication
- [ ] Grep patterns work correctly
- [ ] References accurate and current

## Publishing to skills.sh

### Preparation

1. Complete quality checklist
2. Add README.md with usage instructions
3. Include LICENSE file (MIT recommended)
4. Add comprehensive examples
5. Complete security review
6. Tag version properly

### Installation

```bash
# Local installation
cp -r skill-name ./skills/

# Or use skills CLI
npx skills add your-org/skill-name

# Global installation
npx skills add your-org/skill-name --global
```

## Resources

### Official Documentation
- [Agent Skills Specification](https://agentskills.io/)
- [Skills Discovery Platform](https://skills.sh/)
- [NPM CLI Tool](https://www.npmjs.com/package/skills)
- [Vercel Blog Post](https://vercel.com/blog/agent-skills-explained-an-faq)

### Antigravity Ecosystem
- [Architecture](.agent/ARCHITECTURE.md)
- [Standards](.antigravity/rules.md)
- [Skills Library](.agent/skills/)

## Examples

### Simple Skill
See `examples/example-skill-simple.md` - API error response generator

### Complex Skill with Scripts
See `examples/example-skill-with-scripts.md` - Database migration validator

### Skill Template
See `references/skill-template.md` - Complete template for new skills

## Contributing

Improvements to this skill are welcome:

1. Fork and create feature branch
2. Update documentation and examples
3. Test with multiple agents/LLMs
4. Submit pull request with changelog

## Version History

### 1.0.0 (2026-02-05)
- Initial release
- Core best practices documented
- Validation script included
- Examples and template provided
- Integrated with Antigravity ecosystem

## License

MIT License

## Credits

- **Vercel** - Agent Skills specification and best practices
- **Anthropic** - Claude agent architecture insights
- **Antigravity Team** - Integration with Antigravity ecosystem

---

**Remember**: Agent skills encode organizational knowledge and repeatable patterns. Focus on workflows that benefit from consistency, quality standards, and centralized expertise.
