# Agent Skill Template

Use this template as a starting point for creating new agent skills following Vercel's Agent Skills specification.

---

```markdown
---
name: your-skill-name-here
description: "Brief, clear description of what this skill does (1-2 sentences)"
version: 1.0.0
tags: [domain, technology, use-case]
author: Your Name or Organization
repository: https://github.com/your-org/your-skill
license: MIT
---

# Skill Title (Human-Readable Name)

One paragraph introduction explaining the skill's purpose and value.

[Extended thinking: Deeper rationale explaining why this skill exists, what problems it solves, and the approach it takes. This helps agents understand the context and intent behind the instructions.]

## Use this skill when

- Specific condition or scenario 1
- Specific condition or scenario 2
- Specific condition or scenario 3

Be as specific as possible. Good: "Creating a new REST API endpoint with authentication"
Bad: "Working with APIs"

## Do not use this skill when

- Anti-pattern or inappropriate scenario 1
- Anti-pattern or inappropriate scenario 2
- Anti-pattern or inappropriate scenario 3

Help agents avoid misapplying this skill. Good: "Building GraphQL endpoints (use graphql-api-design skill)"
Bad: "Not for APIs"

## Instructions

Clear, step-by-step instructions that agents can follow systematically.

### Phase 1: [Name of First Phase]

Brief description of what this phase accomplishes.

1. **Step 1**: Clear action with expected outcome
   - Sub-step or consideration
   - Another sub-step

2. **Step 2**: Next action
   ```
   Example code or command
   ```

3. **Step 3**: Continue with numbered steps
   - Keep steps atomic and actionable
   - Avoid ambiguity

### Phase 2: [Name of Second Phase]

Continue with additional phases as needed.

### Decision Trees

When there are multiple paths, provide clear decision criteria:

```
IF condition A is true:
  → Follow workflow A
  → Expect outcome A
ELSE IF condition B is true:
  → Follow workflow B
  → Expect outcome B
ELSE:
  → Follow default workflow
  → Expect default outcome
```

### Output Expectations

Describe what successful completion looks like:

- Deliverable 1 with format specifications
- Deliverable 2 with quality criteria
- Deliverable 3 with validation method

## Safety

Critical considerations for safe and correct execution:

- **Security**: Sensitive operations or data handling
- **Validation**: Required checks before proceeding
- **Error handling**: What to do when things fail
- **Rollback**: How to undo if needed
- **Constraints**: Hard limits or boundaries

## Examples

### Example 1: [Common Case Name]

**Scenario**: Brief description of the situation

**Input**:
```
What the user provides or requests
```

**Process**:
1. Step taken
2. Decision made
3. Action performed

**Output**:
```
What the agent produces
```

**Why this works**: Explanation of success factors

### Example 2: [Edge Case Name]

**Scenario**: Less common but important case

**Input**:
```
Edge case input
```

**Process**:
1. How this differs from common case
2. Special considerations

**Output**:
```
Expected result
```

**Why this is different**: Key variations explained

### Example 3: [Failure Case]

**Scenario**: What NOT to do

**Input**:
```
Problematic input
```

**What went wrong**: Explanation of the mistake

**Correct approach**:
1. How to handle this properly
2. Expected better outcome

## Advanced Usage

Optional section for complex scenarios or optimizations.

### Pattern 1: [Advanced Pattern Name]

When and why to use this pattern.

### Pattern 2: [Optimization Technique]

Trade-offs and benefits.

## Troubleshooting

Common issues and solutions:

**Problem**: Issue description
- **Cause**: Why this happens
- **Solution**: How to fix it
- **Prevention**: How to avoid it

**Problem**: Another issue
- **Cause**: Root cause
- **Solution**: Resolution steps
- **Prevention**: Best practice

## Reference Materials

For detailed specifications, see:
- `grep -A 20 "Authentication" references/api-spec.md` - Auth patterns
- `grep -A 10 "Error Codes" references/error-handling.md` - Error responses
- `references/examples/success-case.json` - Full example

## Dependencies

### Required Tools
- tool_name: Purpose and usage
- another_tool: Purpose and usage

### Optional Tools
- optional_tool: Enhanced capabilities when available

### MCP Servers
- mcp_server_name: Required for functionality X

### Skills
- complementary-skill: Use in conjunction for workflow Y

## Validation Checklist

Before marking task complete, verify:

- [ ] Criterion 1 met
- [ ] Criterion 2 validated
- [ ] Criterion 3 confirmed
- [ ] No errors or warnings
- [ ] Output matches specification
- [ ] Safety checks passed

## Success Metrics

Measure skill effectiveness:

- **Task completion rate**: Target >95%
- **Consistency score**: Variation <10%
- **Time efficiency**: Complete within expected duration
- **Quality metrics**: Specific to domain (accuracy, compliance, etc.)

## Version History

### 1.0.0 (YYYY-MM-DD)
- Initial release
- Core functionality implemented
- Basic examples included

### 0.9.0 (YYYY-MM-DD)
- Beta release for testing
- Feature X added
- Known limitation Y

## Contributing

Guidelines for improving this skill:

1. Fork and create feature branch
2. Update instructions and examples
3. Test with multiple agents/LLMs
4. Submit pull request with changelog

## License

MIT License - See LICENSE file for details

## Credits

- Original author: Name
- Contributors: Name 1, Name 2
- Inspired by: Prior art or resources

---

**Maintenance Notes**:
- Review quarterly for updates
- Sync with organizational changes
- Update examples with real-world usage
- Incorporate user feedback

**Related Skills**:
- related-skill-1: For complementary workflow
- related-skill-2: For adjacent domain
```

---

## Template Usage Guidelines

### Adapt to Your Domain

This template is comprehensive. Remove sections that don't apply:

- **Simple skills**: May only need Instructions and Examples
- **Complex skills**: Might need additional phases or decision trees
- **Technical skills**: Emphasize code examples and validation
- **Workflow skills**: Focus on decision criteria and handoffs

### Progressive Disclosure

Structure content from simple to complex:

1. **Quick Start**: Minimal viable usage (top of Instructions)
2. **Standard Usage**: Common cases (main Instructions)
3. **Advanced Usage**: Optional optimizations (separate section)
4. **Reference**: Complete details (references/ directory)

### Keep it Actionable

Every instruction should be:
- **Specific**: Clear, unambiguous action
- **Measurable**: Verifiable completion criteria
- **Achievable**: Within agent capabilities
- **Relevant**: Directly supports task goals
- **Time-bound**: Expected completion duration (if applicable)

### Test Before Publishing

Validate with multiple agents:
- Claude (Anthropic)
- GPT-4 (OpenAI)
- Gemini (Google)
- Local models (Ollama, etc.)

Ensure consistent behavior and quality across implementations.
