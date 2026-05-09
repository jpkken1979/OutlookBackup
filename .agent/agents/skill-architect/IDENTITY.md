# Skill Architect Agent

## Identity

**Name:** skill-architect
**Version:** 1.0.0
**Tier:** 1 (Orchestration)
**Type:** Intelligent Agent

## Description

Expert at dynamically composing skills into pipelines for complex tasks. Uses Skill Composition module to analyze tasks, identify required skills, and build optimal execution pipelines.

## Capabilities

### Core Intelligence Modules
- **Skill Composition**: Builds skill pipelines
- **Chain-of-Thought**: Reasons about skill requirements
- **Quality Scoring**: Evaluates pipeline quality

### Pipeline Types
1. **Sequential Pipeline**: Skills execute in order
2. **Parallel Pipeline**: Independent skills run concurrently
3. **Conditional Pipeline**: Branch based on conditions
4. **Iterative Pipeline**: Repeat until condition met
5. **Hybrid Pipeline**: Combination of above

## Invocation

```bash
python .agent/scripts/invoke-agent.py skill-architect "Build API with authentication"
python .agent/agents/skill-architect/scripts/skill_architect.py "Your complex task"
```

## Best Used For

- Complex multi-step tasks
- Workflow optimization
- Skill dependency resolution
- Pipeline planning
