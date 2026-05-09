# /intelligent

## Command

```
/intelligent <task> [--modules <list>] [--strategy <name>]
```

## Description

Execute any task with full intelligence capabilities enabled. The meta-command.

## Example

```
/intelligent Refactor the auth module for better security
```

## Implementation

```python
from .agent.core.intelligent_orchestrator import intelligent_execute

async def intelligent(task: str, modules: list = None, strategy: str = None):
    """
    Full intelligent execution.

    1. Analyze task (complexity, domains, risks)
    2. Select optimal strategy
    3. Choose best agents and modules
    4. Execute with reflection
    5. Learn from execution
    """
    config = {}
    if modules:
        config["modules"] = modules
    if strategy:
        config["strategy"] = strategy

    result = await intelligent_execute(task, config=config)
    return result.export_report()
```

## Output

- Task analysis (complexity, domains, risks)
- Execution steps with reasoning
- Quality score
- Learnings extracted
- Full explanation

## Related

- All other /commands are specialized versions of this
