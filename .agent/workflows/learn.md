# /learn

## Command

```
/learn [--from <source>] [--report]
```

## Description

Trigger autonomous learning from executions, feedback, and errors.

## Example

```
/learn --from recent --report
```

## Implementation

```python
from .agent.core.autonomous_learning import get_learning_pipeline

async def learn(source: str = "all", report: bool = False):
    """
    Autonomous learning cycle.

    1. Extract patterns from executions
    2. Process feedback
    3. Analyze errors
    4. Optimize strategies
    5. Generate skills
    """
    pipeline = get_learning_pipeline()
    await pipeline.run_learning_cycle()

    if report:
        return pipeline.generate_report().export_report()
    return "Learning cycle completed"
```

## Output

- Patterns discovered
- Strategies optimized
- Skills generated
- Improvement recommendations

## Related

- /improve - Self-improvement cycle
- /stats - View learning statistics
