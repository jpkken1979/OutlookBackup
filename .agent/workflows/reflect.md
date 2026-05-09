# /reflect

## Command

```
/reflect <output> [--task <original-task>]
```

## Description

Self-reflection on any output to evaluate quality and identify improvements.

## Example

```
/reflect "The code I just wrote" --task "Implement user authentication"
```

## Implementation

```python
from .agent.core.intelligence import SelfReflection, quick_reflect

async def reflect(output: str, task: str = None):
    """
    Reflect on output quality.

    1. Evaluate accuracy
    2. Check completeness
    3. Assess clarity
    4. Identify improvements
    """
    reflection = SelfReflection(depth=3)
    result = await reflection.reflect(
        output=output,
        task=task,
        aspects=["accuracy", "completeness", "clarity", "relevance"]
    )
    return result.export_report()
```

## Output

- Quality scores by dimension
- Identified issues
- Suggested improvements
- Overall confidence

## Related

- /score - Detailed quality scoring
- /improve - Apply improvements
