# /compose

## Command

```
/compose <complex-task> [--constraints <json>]
```

## Description

Dynamically compose skills into an optimal pipeline for complex tasks.

## Example

```
/compose Build REST API with auth, tests, and documentation
```

## Implementation

```python
from .agent.core.intelligence import SkillComposer, compose_skills

async def compose(task: str, constraints: dict = None):
    """
    Compose skills into pipeline.

    1. Analyze task requirements
    2. Identify required skills
    3. Resolve dependencies
    4. Build optimal pipeline
    """
    composer = SkillComposer()
    result = await composer.compose(
        task=task,
        constraints=constraints or {}
    )
    return result.export_diagram()
```

## Output

- Required skills identified
- Dependency graph
- Execution order (parallel where possible)
- Pipeline visualization

## Related

- /orchestrate - Full orchestration
- /predict - Risk assessment first
