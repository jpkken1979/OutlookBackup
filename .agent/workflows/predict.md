# /predict

## Command

```
/predict <task> [--context <json>]
```

## Description

Predict risks and potential escalations before executing a task. Early warning system.

## Example

```
/predict Deploy new auth system to production
```

## Implementation

```python
from .agent.core.intelligence import PredictiveEscalation, predict_escalation

async def predict(task: str, context: dict = None):
    """
    Predict risks before execution.

    1. Detect risk signals
    2. Analyze task complexity
    3. Predict escalation probability
    4. Recommend mitigations
    """
    predictor = PredictiveEscalation()
    result = await predictor.predict(task, context or {})
    return result.export_report()
```

## Output

- Risk level (0-1) with breakdown
- Escalation prediction (NONE/WATCH/SOFT/HARD/CRITICAL)
- Risk signals detected
- Mitigation recommendations

## Related

- /think-deep - Deep analysis before action
- /compose - Plan safe execution
