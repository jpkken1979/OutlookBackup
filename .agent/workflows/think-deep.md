# /think-deep

## Command

```
/think-deep <problem>
```

## Description

Deep Chain-of-Thought analysis for complex problems. Uses explicit reasoning steps to break down and analyze the problem thoroughly.

## Example

```
/think-deep How should we architect the payment system for scalability?
```

## Implementation

```python
from .agent.core.intelligence import ChainOfThought, think_through

async def think_deep(problem: str, context: dict = None):
    """
    Deep thinking with chain-of-thought.

    1. Break problem into sub-problems
    2. Reason through each step explicitly
    3. Validate conclusions
    4. Synthesize final answer
    """
    cot = ChainOfThought(max_steps=15, verbose=True)
    result = await cot.think(problem, context)
    return result.export_report()
```

## Output

- Step-by-step reasoning chain
- Confidence levels per step
- Final conclusion with justification
- Alternative considerations

## Related

- /debate - Multi-perspective analysis
- /explain - Decision explanation
