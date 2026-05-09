from typing import List, Dict, Any
from backend.agents.base_agent import BaseAgent, AgentContext, AgentResult, ActionType

class {{AgentName}}(BaseAgent):
    """
    {{AgentDescription}}
    """

    def __init__(self):
        super().__init__(
            name="{{agent_snake_case}}",
            description="{{AgentDescription}}"
        )

    def get_capabilities(self) -> List[str]:
        return [
            # TODO: Add capabilities here
            "{{agent_capability}}"
        ]

    def execute(self, context: AgentContext, **kwargs) -> AgentResult:
        """
        Main execution logic for {{AgentName}}.
        """
        try:
            # Extract arguments
            # data = kwargs.get("data")

            # TODO: Implement agent logic here
            
            return AgentResult(
                success=True,
                agent_name=self.name,
                action_type=ActionType.CALCULATE, # Change as needed
                data={},
                message=f"{{AgentName}} executed successfully"
            )

        except Exception as e:
            return AgentResult(
                success=False,
                agent_name=self.name,
                action_type=ActionType.AUDIT,
                message=f"Error executing {{AgentName}}: {str(e)}",
                errors=[str(e)]
            )
