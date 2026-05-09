---
name: superpowers-lab
description: "Laboratory environment for exploring and testing Claude's advanced capabilities including tool use patterns, agentic workflows, structured outputs, multi-turn reasoning, and prompt engineering techniques. Use when experimenting with Claude superpowers, testing advanced prompting strategies, exploring capability boundaries, building agentic patterns, or prototyping complex tool-use chains."
type: feature
source: "https://github.com/obra/superpowers-lab"
risk: safe
user-invocable: true
---

# Superpowers Lab

A hands-on environment for exploring Claude's most advanced capabilities beyond standard prompting.

## What You Can Test

### Tool Use & Agent Patterns
- Design multi-step tool-use workflows with branching logic
- Build error recovery patterns for tool invocation
- Create loops that refine outputs based on tool results
- Explore tool composition and chaining strategies

### Structured Output Schemas
- Design JSON schemas for complex, nested outputs
- Test validation and refinement patterns
- Build processors that verify schema compliance
- Explore recursive and polymorphic schema patterns

### Advanced Prompting Techniques
- Multi-turn reasoning with explicit thinking patterns
- Constraint-based generation and boundary exploration
- Few-shot examples for nuanced behaviors
- Adversarial prompting to test robustness

### Agentic Workflows
- Design autonomous reasoning loops with clear termination
- Build debate/consensus protocols between Claude instances
- Explore meta-cognition patterns (Claude reasoning about its own reasoning)
- Test planning systems with refinement loops

## Experimentation Checklist

- [ ] **Tool Use**: Design a 3+ step workflow, test error cases
- [ ] **Structured Output**: Create a schema, verify parsing works
- [ ] **Prompting**: Compare 3 variants, measure effectiveness
- [ ] **Reasoning**: Trace multi-turn dialogue, identify weak links
- [ ] **Composition**: Combine 2+ techniques in a single workflow

## Key Experiments

1. **Tool Composition Chain**: String 3+ tools with conditional logic
2. **Schema Evolution**: Start simple, iteratively add constraints
3. **Capability Boundary Map**: Document what works vs. limitations
4. **Feedback Loop Optimization**: Measure iterations needed for convergence
5. **Hybrid Prompting**: Mix instructions, examples, and explicit reasoning

See [source repository](https://github.com/obra/superpowers-lab) for additional examples and case studies.
