---
name: vercel-agent-skills-best-practices
type: feature
description: "antigravity:"
---

---
name: vercel-agent-skills-best-practices
description: "Best practices for creating high-quality, production-ready agent skills based on Vercel's Agent Skills specification and open standards."
version: 1.0.0
tags: [agent-skills, best-practices, vercel, standards, mcp-integration, antigravity]
author: Antigravity Team

# Antigravity-specific metadata
antigravity:
  tier: 3                           # Quality & Testing tier
  compatible_agents:
    - planner                       # Usa para estructurar nuevas skills
    - architect                     # Valida design patterns
    - explorer                      # Investiga estructura de skills
    - critic                        # Valida calidad de skills
    - code-reviewer                 # Revisa implementación
    - memory                        # Documenta aprendizajes
  required_tools:
    - file_read
    - file_write
    - yaml_parser
  optional_tools:
    - grep
    - git
  mcp_servers: []                   # No requiere MCP servers externos
  memory_usage: low
  estimated_tokens: 2000
  estimated_duration: "5-20 minutes"
---

# Vercel Agent Skills: Best Practices Guide

Comprehensive guide for creating packaged, reusable instructions for AI agents following the open Agent Skills standard.

[Extended thinking: Agent skills transform agents from "kind of works" to understanding "how we do things here" by providing centralized, on-demand expertise. Success requires focusing on repeatable patterns, modular organization, and avoiding information duplication while maintaining security and quality standards.]

## Use this skill when

- Creating new agent skills from scratch
- Refactoring existing skills to follow Vercel standards
- Designing skill packages for organizational workflows
- Implementing repeatable patterns across domains
- Building shareable skills for the skills.sh ecosystem

## Do not use this skill when

- Building one-off prompts or instructions
- Creating general documentation (not skill-specific)
- Working on non-agent or non-LLM tasks
- Task requires custom agent architecture (not skills)

## Instructions

1. Identify repeatable patterns and organizational workflows
2. Structure skills using modular three-layer architecture
3. Create SKILL.md with proper YAML frontmatter and markdown
4. Add scripts, references, and assets as needed
5. Follow naming conventions and security guidelines
6. Test skills across different agent implementations
7. Document integration with MCP and complementary technologies

## Safety

- Review all scripts in skill packages before deployment
- Pin versions where possible for reproducibility
- Avoid hardcoding sensitive information in skills
- Audit skill packages as you would any production code
- Prefer auditable, open-source skill packages

## Core Concepts

### What Are Agent Skills?

Agent skills are **packaged, reusable instructions for AI agents** built on an open standard. They function as:

- **Centralized expertise**: Organizational knowledge and workflow patterns
- **On-demand guidance**: Context-loaded when tasks match skill domains
- **Repeatable solutions**: Consistent execution across similar tasks
- **Version-controlled instructions**: Trackable, auditable agent behavior

**Value Proposition:**
Skills transition agents from "kind of works" to understanding "how we do things here" by eliminating prompt drift, preserving workflow conventions, and reducing instruction sprawl.

### Problems Skills Solve

#### 1. Prompt Drift
**Problem**: Identical requests worded differently produce inconsistent results.
**Solution**: Centralized skill provides canonical instructions loaded automatically.

#### 2. Lost Workflow Conventions
**Problem**: Quality checks, validations, and decision criteria scattered across conversations.
**Solution**: Skills encode organizational standards and best practices.

#### 3. Instruction Sprawl
**Problem**: Bulky playbooks clutter prompt context, wasting tokens.
**Solution**: Skills loaded on-demand only when relevant, keeping context lean.

## Three-Layer Architecture

### Layer 1: Lightweight Metadata Index
**When**: On agent initialization
**What**: Agent loads only names and descriptions of available skills
**Why**: Minimal memory footprint, fast startup

```yaml
# Example metadata index
skills:
  - name: api-route-creation
    description: "Add new API routes following our REST conventions"
  - name: pr-creation-workflow
    description: "Create pull requests with proper formatting and checks"
```

### Layer 2: Full Skill Content Loading
**When**: Task matches skill description (semantic matching)
**What**: Agent loads complete SKILL.md with instructions, examples, references
**Why**: Provides detailed context only when needed

### Layer 3: Optional Explicit Invocation
**When**: Debugging, testing, or forcing specific workflow
**What**: User manually triggers skill (e.g., `/skill api-route-creation`)
**Why**: Enables testing and workflow override

## Skill Package Structure

### Required Components

#### SKILL.md (Mandatory)
Primary instruction file with YAML frontmatter and markdown content.

**YAML Frontmatter Requirements:**
```yaml
---
name: skill-name-here               # REQUIRED: 1-64 chars, lowercase, hyphens only
description: "Brief description"    # REQUIRED: Clear, concise purpose
version: 1.0.0                      # RECOMMENDED: Semantic versioning
tags: [domain, technology]          # OPTIONAL: Discovery tags
author: Your Name                   # OPTIONAL: Attribution
---
```

**Naming Rules:**
- Pattern: `^[a-z0-9]+(-[a-z0-9]+)*$`
- Length: 1-64 characters
- Case: Lowercase only
- Separators: Single hyphens only
- Must match directory name exactly

**Content Structure:**
```markdown
# Skill Title

Brief introduction paragraph.

[Extended thinking: Deep rationale and context.]

## Use this skill when
- Condition 1
- Condition 2

## Do not use this skill when
- Anti-pattern 1
- Anti-pattern 2

## Instructions
1. Step-by-step guidance
2. Decision trees and workflows
3. Output expectations

## Safety
- Security considerations
- Error handling
- Rollback procedures

## [Additional sections as needed]
```

### Optional Components

#### scripts/ Directory
**Purpose**: Deterministic, auditable procedures
**When to use**: Calculations, validations, data transformations
**Best practices**:
- Make scripts idempotent
- Include clear error messages
- Add logging for debugging
- Document all parameters
- Use exit codes properly

**Example Structure:**
```
scripts/
├── main.py                # Primary entry point
├── validate.sh            # Validation logic
├── helpers.py             # Shared utilities
└── README.md              # Script documentation
```

#### references/ Directory
**Purpose**: Supporting documentation without bloating main context
**When to use**: Long specifications, API docs, compliance guides
**Best practices**:
- Include grep patterns in SKILL.md for targeted retrieval
- Organize by topic or domain
- Keep files focused and modular
- Use clear naming conventions

**Example:**
```markdown
# In SKILL.md
For detailed API specifications, search references/:
`grep -r "authentication" references/api-specs/`
```

#### assets/ Directory
**Purpose**: Templates, examples, configuration files
**When to use**: Code templates, configuration samples, data fixtures
**Best practices**:
- Use clear, descriptive filenames
- Include multiple complexity levels (simple, advanced)
- Add inline comments explaining key sections
- Keep assets up-to-date with current standards

**Example Structure:**
```
assets/
├── templates/
│   ├── api-route-basic.ts
│   └── api-route-advanced.ts
├── examples/
│   ├── success-case.json
│   └── error-case.json
└── configs/
    └── recommended-settings.yaml
```

## Focus on Repeatable Patterns

### Good Skill Candidates

#### Development Processes
- Adding API routes with consistent patterns
- Creating components following design system
- Writing tests using organizational conventions
- Code review checklists and quality gates

#### Content Creation
- Writing headlines matching brand voice
- Generating documentation with standard structure
- Creating marketing copy following guidelines
- SEO optimization workflows

#### Support Operations
- Ticket triage and classification
- Escalation decision trees
- Response templates by issue type
- Follow-up and resolution workflows

#### Data Analysis
- Dataset cleaning and validation
- Visualization standards and templates
- Statistical analysis protocols
- Report generation workflows

### Poor Skill Candidates

❌ **One-off tasks**: Single-use instructions without repeat value
❌ **Too generic**: "Write good code" without specific patterns
❌ **Tool-specific only**: Better served by tool documentation
❌ **Constantly changing**: Requires frequent updates (use dynamic sources)
❌ **Highly contextual**: Depends on specific conversation state

## Modular Organization Best Practices

### Principle: Avoid Information Duplication

**Anti-pattern:**
```
SKILL.md: Contains full API specification (5000 lines)
references/api-spec.md: Same content duplicated
```

**Best practice:**
```markdown
# SKILL.md (concise)
For API authentication details:
`grep -A 20 "OAuth 2.0 Flow" references/api-spec.md`

For rate limiting specifications:
`grep -A 10 "Rate Limits" references/api-spec.md`
```

### Single Responsibility Principle

**Each skill should:**
- Focus on ONE workflow or pattern
- Have clear boundaries
- Avoid overlapping with other skills
- Be independently usable

**Example: Good Separation**
```
✅ api-route-creation        # Creating routes
✅ api-error-handling        # Error responses
✅ api-authentication        # Auth patterns
✅ api-testing               # Testing APIs
```

**Example: Poor Separation**
```
❌ api-everything            # Too broad, unmaintainable
❌ backend-stuff             # Unclear scope
❌ web-development           # Overlaps with many domains
```

### Progressive Disclosure

Start simple, layer complexity:

```markdown
## Quick Start (5 minutes)
Basic workflow for common case.

## Intermediate Usage (15 minutes)
Handling edge cases and options.

## Advanced Patterns (30 minutes)
Complex scenarios and optimizations.

## Reference
Complete specifications and details.
```

## Integration with Complementary Technologies

### Skills vs. MCP Servers

**MCP (Model Context Protocol)**: Standardized tool access layer
**When to use MCP**: External data sources, APIs, live system state
**When to use Skills**: Workflow instructions, organizational patterns

**Complementary Example:**
```yaml
# MCP server provides tools
mcp_server: github
  tools:
    - create_pr
    - list_issues
    - get_repo_info

# Skill provides workflow
skill: pr-creation-workflow
  uses_mcp: github
  instructions: |
    1. Use github.get_repo_info to check branch protection
    2. Use github.create_pr with our template format
    3. Add standard labels and reviewers per our policy
```

### Skills vs. Tools

**Tools**: Discrete operations (API calls, file operations)
**Skills**: Orchestrated workflows using multiple tools

**Example:**
```
Tool: file_write(path, content)
Tool: test_runner(suite)
Tool: git_commit(message)

Skill: feature-implementation-workflow
  1. Write implementation using file_write
  2. Run tests using test_runner
  3. Commit changes using git_commit with standard message format
  4. Validate checklist completion
```

### Skills vs. Rules

**Rules**: Compliance constraints and hard requirements
**Skills**: Positive guidance and best practices

**Example:**
```yaml
# Rule (constraint)
rules:
  - no_console_log_in_production: true
  - require_tests_for_new_features: true

# Skill (guidance)
skill: logging-best-practices
  instructions: |
    Use our logging framework instead of console.log:
    - Import: import { logger } from '@/lib/logger'
    - Usage: logger.info('message', { context })
```

### Skills vs. System Prompts

**System Prompts**: Foundational agent identity and behavior
**Skills**: Domain-specific, task-focused instructions

**Hierarchy:**
```
System Prompt (always active)
├── Agent identity and core capabilities
├── General behavior and tone
└── Universal constraints

Skills (loaded on-demand)
├── api-design-patterns (when building APIs)
├── ui-component-creation (when building UI)
└── database-migration (when updating schema)
```

## Security and Quality Guidelines

### Security Review Checklist

Before deploying a skill package:

- [ ] Review all scripts for malicious code
- [ ] Check for hardcoded secrets or credentials
- [ ] Validate input sanitization in scripts
- [ ] Audit external dependencies
- [ ] Verify file permission requirements
- [ ] Test rollback procedures
- [ ] Document security considerations

### Version Pinning

**Recommended approach:**
```yaml
# In SKILL.md metadata
version: 1.2.3
dependencies:
  - package: "@skills/helpers"
    version: "^2.0.0"
    locked: true
```

**Update strategy:**
- Pin major versions for stability
- Test thoroughly before upgrading
- Maintain changelog with breaking changes
- Support backward compatibility when possible

### Auditability Standards

**Every skill package should include:**
- Clear authorship and ownership
- Version history and changelog
- Modification tracking (git or equivalent)
- Review and approval records
- Known issues and limitations

## Testing and Validation

### Skill Quality Checklist

- [ ] Name follows regex pattern `^[a-z0-9]+(-[a-z0-9]+)*$`
- [ ] YAML frontmatter is valid
- [ ] Description is clear and concise
- [ ] Instructions are step-by-step and actionable
- [ ] Examples cover common and edge cases
- [ ] Safety considerations documented
- [ ] Scripts are tested and documented
- [ ] No information duplication
- [ ] Grep patterns work correctly
- [ ] References are accurate and up-to-date

### Cross-Agent Testing

Test skills across multiple agent implementations:

```bash
# Test with different LLMs
test-skill --agent claude-3-5-sonnet api-route-creation
test-skill --agent gpt-4-turbo api-route-creation
test-skill --agent gemini-pro api-route-creation

# Test with different frameworks
test-skill --framework antigravity api-route-creation
test-skill --framework langchain api-route-creation
test-skill --framework autogen api-route-creation
```

### Performance Benchmarks

Measure skill effectiveness:

- **Activation accuracy**: Does skill load for correct tasks?
- **Instruction clarity**: Can agent follow without clarification?
- **Success rate**: Task completion with skill vs without
- **Token efficiency**: Context size impact
- **Time to competency**: How quickly agent masters skill

## Publishing to skills.sh Ecosystem

### Skill Discovery Platform

**skills.sh**: Central registry for agent skills
**Purpose**: Share skills across organizations and communities

### Publishing Checklist

- [ ] Skill follows naming conventions
- [ ] README.md explains purpose and usage
- [ ] LICENSE file included (MIT recommended)
- [ ] Examples demonstrate key workflows
- [ ] Documentation is complete
- [ ] Scripts are tested and documented
- [ ] Security review completed
- [ ] Version tagged properly

### Installation Methods

**Local installation:**
```bash
# Copy to project skills directory
cp -r skill-name ./skills/

# Or use skills CLI
npx skills add your-org/skill-name
```

**Global installation:**
```bash
# Install to user scope
npx skills add your-org/skill-name --global
```

## Antigravity Integration

### Adapting to Antigravity Architecture

Vercel Agent Skills align well with Antigravity's 4-layer architecture:

**Layer 1 (Directiva)**: SKILL.md provides directives
**Layer 2 (Contexto)**: references/ provides persistent context
**Layer 3 (Ejecución)**: scripts/ perform actions
**Layer 4 (Observabilidad)**: logs/ track execution

### Enhanced Metadata for Antigravity

```yaml
---
name: skill-name
description: "Skill description"
version: 1.0.0

# Antigravity-specific extensions
antigravity:
  tier: 3                           # Agent tier (1-8)
  compatible_agents: [planner, architect, explorer]
  required_tools: [file_read, file_write]
  mcp_servers: [github, linear]     # Required MCP integrations
  memory_usage: medium              # low/medium/high
  estimated_tokens: 2000            # Approximate context size
---
```

### Hybrid Approach: Skills + Agents

**Antigravity agents can use Vercel-style skills internally:**

```python
# .agent/agents/api-designer/main.py
from antigravity.core import AntigravityAgent
from antigravity.skills import load_skill

class APIDesigner(AntigravityAgent):
    async def execute(self, task: str):
        # Load Vercel-style skill dynamically
        skill = load_skill("api-design-patterns")

        # Incorporate skill instructions into agent execution
        instructions = skill.get_instructions()

        # Execute with skill-guided behavior
        result = await self.llm.generate(
            context=instructions,
            task=task
        )

        return result
```

## Success Criteria

A well-crafted agent skill should:

- **Activate correctly**: Load for relevant tasks (>90% accuracy)
- **Improve consistency**: Reduce variation in outputs (>30% improvement)
- **Increase success rate**: Higher task completion (>20% improvement)
- **Reduce clarifications**: Fewer follow-up questions (<50% reduction)
- **Maintain performance**: No significant latency increase (<10%)
- **Be maintainable**: Easy to update and version over time

## Continuous Improvement

### Feedback Collection

- Monitor skill activation patterns
- Track task success rates with/without skill
- Collect user feedback on skill helpfulness
- Analyze edge cases and failures
- Measure token efficiency impact

### Iterative Refinement

- Update instructions based on real usage
- Add examples for newly discovered patterns
- Refactor structure for clarity
- Optimize context size
- Enhance error handling

### Version Management

```
Version Format: [MAJOR].[MINOR].[PATCH]

MAJOR: Breaking changes to skill interface
MINOR: New instructions, examples, or features
PATCH: Bug fixes, clarifications, typo corrections
```

## Additional Resources

### Official Documentation
- **Agent Skills Specification**: https://agentskills.io/
- **Skills Discovery Platform**: https://skills.sh/
- **NPM CLI Tool**: https://www.npmjs.com/package/skills

### Vercel Blog Post
- **Agent Skills FAQ**: https://vercel.com/blog/agent-skills-explained-an-faq

### Antigravity Ecosystem
- **Architecture**: `.agent/ARCHITECTURE.md`
- **Standards**: `.antigravity/rules.md`
- **Skills Library**: `.agent/skills/`

---

**Remember**: Agent skills are about encoding organizational knowledge and repeatable patterns, not one-off instructions. Focus on workflows that benefit from consistency, quality standards, and centralized expertise.

**Integration with Antigravity**: This skill framework complements Antigravity's agent system by providing standardized skill packaging that works across different LLMs and agent frameworks, following open standards for maximum portability and reusability.
