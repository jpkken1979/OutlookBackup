# /explain

## Command

```
/explain <decision>
```

## Description

Generate human-readable explanation for any decision or action. Makes reasoning transparent.

## Example

```
/explain Why did you choose PostgreSQL over MongoDB for this project?
```

## Implementation

```python
from .agent.core.intelligence import DecisionExplainer, explain_decision

async def explain(decision: str, context: dict = None):
    """
    Explain a decision transparently.

    1. Identify decision factors
    2. Analyze alternatives considered
    3. Document risks and assumptions
    4. Generate clear explanation
    """
    explainer = DecisionExplainer()
    result = await explainer.explain(
        decision=decision,
        context=context,
        detail_level="detailed"
    )
    return result.export_report()
```

## Output

- Decision factors with weights
- Alternatives considered
- Risks acknowledged
- Clear reasoning in plain language

## Related

- /debate - Decision through debate
- /think-deep - Deep analysis
