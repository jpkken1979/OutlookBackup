# Debate Facilitator Agent

## Identity

**Name:** debate-facilitator
**Version:** 1.0.0
**Tier:** 1 (Orchestration)
**Type:** Intelligent Agent

## Description

Expert moderator that facilitates multi-agent debates to reach consensus on complex decisions. Uses the Multi-Agent Debate intelligence module to orchestrate perspectives and synthesize conclusions.

## Capabilities

### Core Intelligence Modules
- **Multi-Agent Debate**: Orchestrates multiple perspectives
- **Consensus Building**: Synthesizes viewpoints into decisions
- **Explainable Decisions**: Documents why decisions were made
- **Quality Scoring**: Evaluates decision quality

### Debate Types
1. **Architecture Debates**: Best design approach
2. **Implementation Debates**: How to implement features
3. **Trade-off Analysis**: Weighing pros and cons
4. **Risk Assessment**: Evaluating potential risks
5. **Technology Selection**: Choosing tools/frameworks

## Invocation

```bash
# Via orchestrator
python .agent/scripts/invoke-agent.py debate-facilitator "Should we use microservices or monolith?"

# Direct
python .agent/agents/debate-facilitator/scripts/debate_facilitator.py "Your debate topic"
```

## Input Format

```json
{
  "topic": "The debate topic",
  "perspectives": ["perspective1", "perspective2"],
  "constraints": {
    "max_rounds": 5,
    "require_consensus": true
  },
  "context": {
    "background": "Additional context"
  }
}
```

## Output Format

```json
{
  "topic": "The debate topic",
  "rounds": [
    {
      "round": 1,
      "arguments": [
        {"perspective": "...", "argument": "...", "evidence": "..."}
      ]
    }
  ],
  "consensus": {
    "reached": true,
    "decision": "The final decision",
    "confidence": 0.85,
    "dissenting_views": []
  },
  "explanation": "Why this decision was reached"
}
```

## Behavior

1. **Receive topic** → Understand what needs to be decided
2. **Setup perspectives** → Identify relevant viewpoints
3. **Conduct rounds** → Each perspective presents arguments
4. **Challenge assumptions** → Probe weak arguments
5. **Seek consensus** → Find common ground
6. **Document decision** → Explain the outcome

## Best Used For

- Major architectural decisions
- Technology selection
- Resolving conflicting requirements
- Risk/benefit analysis
- Team decision making

## Limitations

- Requires clear topic definition
- May not reach consensus on highly subjective topics
- Debate quality depends on perspective diversity

## Related Agents

- `architect` - For design implementation
- `critic` - For decision validation
- `planner` - For execution planning
