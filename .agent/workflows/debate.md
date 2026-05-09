# /debate

## Command

```
/debate <topic> [--perspectives <list>] [--rounds <n>]
```

## Description

Multi-agent debate for complex decisions. Multiple perspectives argue and reach consensus.

## Example

```
/debate Should we migrate to microservices? --perspectives optimist,pessimist,pragmatist --rounds 3
```

## Implementation

```python
from .agent.core.intelligence import MultiAgentDebate, quick_debate

async def debate(topic: str, perspectives: list = None, rounds: int = 3):
    """
    Multi-agent debate for decisions.

    1. Setup perspectives
    2. Conduct debate rounds
    3. Build consensus
    4. Explain decision
    """
    debater = MultiAgentDebate()
    result = await debater.debate(
        topic=topic,
        perspectives=perspectives or ["optimist", "pessimist", "pragmatist"],
        max_rounds=rounds
    )
    return result.export_report()
```

## Output

- Arguments from each perspective
- Rebuttals and counter-arguments
- Consensus (if reached)
- Final recommendation with confidence

## Related

- /think-deep - Single-perspective deep thinking
- /explain - Decision explanation
