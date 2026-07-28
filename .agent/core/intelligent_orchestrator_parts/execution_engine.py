# mypy: ignore-errors
"""Motor de ejecucion de estrategias del IntelligentOrchestrator (mixin).

Extraido de ``IntelligentOrchestrator`` (Plan 018). Es un MIXIN: las estrategias de
ejecucion (``_execute_strategy`` dispatcher + ``_execute_direct``/``_execute_think``/
``_execute_with_thinking``/``_execute_debate``/``_execute_with_consensus``/
``_execute_react``/``_compose_pipeline``/``_execute_pipeline``/``_execute_collaborative``/
``_execute_adaptive``) operan sobre ``self`` del orchestrator (usan ``self._modules`` y
se invocan entre si), provisto via herencia. Sigue el patron ``_daemon_mixin_*`` del
ecosistema. No tiene estado propio.
"""

from __future__ import annotations

import logging
from typing import Any

from .models import ExecutionStep, ExecutionStrategy, TaskAnalysis

logger = logging.getLogger("antigravity.orchestrator.execution")


class ExecutionStrategiesMixin:
    """Estrategias de ejecucion del orchestrator (opera sobre ``self`` del host)."""

    async def _execute_strategy(
        self, task: str, analysis: TaskAnalysis, context: dict, config: dict
    ) -> tuple[Any, list[ExecutionStep]]:
        """Execute task based on selected strategy."""
        strategy = analysis.recommended_strategy
        steps = []

        if strategy == ExecutionStrategy.DIRECT:
            output, step = await self._execute_direct(task, analysis, context)
            steps.append(step)

        elif strategy == ExecutionStrategy.THINK_FIRST:
            thinking, think_step = await self._execute_think(task, analysis, context)
            steps.append(think_step)
            output, exec_step = await self._execute_with_thinking(task, thinking, analysis, context)
            steps.append(exec_step)

        elif strategy == ExecutionStrategy.DEBATE:
            debate_result, debate_step = await self._execute_debate(task, analysis, context)
            steps.append(debate_step)
            output, exec_step = await self._execute_with_consensus(
                task, debate_result, analysis, context
            )
            steps.append(exec_step)

        elif strategy == ExecutionStrategy.REACT:
            output, react_steps = await self._execute_react(task, analysis, context)
            steps.extend(react_steps)

        elif strategy == ExecutionStrategy.COMPOSED:
            pipeline, compose_step = await self._compose_pipeline(task, analysis, context)
            steps.append(compose_step)
            output, exec_steps = await self._execute_pipeline(pipeline, analysis, context)
            steps.extend(exec_steps)

        elif strategy == ExecutionStrategy.COLLABORATIVE:
            output, collab_steps = await self._execute_collaborative(task, analysis, context)
            steps.extend(collab_steps)

        elif strategy == ExecutionStrategy.ADAPTIVE:
            output, adaptive_steps = await self._execute_adaptive(task, analysis, context)
            steps.extend(adaptive_steps)

        else:
            output, step = await self._execute_direct(task, analysis, context)
            steps.append(step)

        return output, steps

    async def _execute_direct(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, ExecutionStep]:
        """Direct execution without extra reasoning."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 2,
            action="Direct execution",
            agent=analysis.recommended_agents[0] if analysis.recommended_agents else None,
            module=None,
            input_data={"task": task},
        )

        # Simulate execution (in real implementation, would call actual agent)
        output = {
            "status": "completed",
            "task": task,
            "approach": "direct",
            "result": f"Task '{task[:50]}...' executed directly",
        }

        step.output_data = output
        step.status = "completed"

        return output, step

    async def _execute_think(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[dict, ExecutionStep]:
        """Execute chain-of-thought reasoning."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 2,
            action="Chain-of-thought reasoning",
            agent=None,
            module="cot",
            input_data={"task": task},
        )

        if "cot" in self._modules and self._modules["cot"]:
            try:
                result = await self._modules["cot"].think(task)
                thinking = (
                    result.to_dict() if hasattr(result, "to_dict") else {"thoughts": str(result)}
                )
            except Exception as e:
                thinking = {"thoughts": f"Thinking about: {task}", "error": str(e)}
        else:
            thinking = {"thoughts": f"Analyzing task: {task}"}

        step.output_data = thinking
        step.status = "completed"

        return thinking, step

    async def _execute_with_thinking(
        self, task: str, thinking: dict, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, ExecutionStep]:
        """Execute with chain-of-thought results."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 3,
            action="Execution with reasoning",
            agent=analysis.recommended_agents[0] if analysis.recommended_agents else None,
            module=None,
            input_data={"task": task, "thinking": thinking},
        )

        output = {
            "status": "completed",
            "task": task,
            "approach": "think_first",
            "reasoning": thinking,
            "result": "Task executed with reasoning",
        }

        step.output_data = output
        step.status = "completed"

        return output, step

    async def _execute_debate(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[dict, ExecutionStep]:
        """Execute multi-agent debate."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 2,
            action="Multi-agent debate",
            agent=None,
            module="debate",
            input_data={"task": task},
        )

        if "debate" in self._modules and self._modules["debate"]:
            try:
                result = await self._modules["debate"].debate(task)
                debate_result = (
                    result.to_dict() if hasattr(result, "to_dict") else {"consensus": str(result)}
                )
            except Exception as e:
                debate_result = {"consensus": "Proceed with caution", "error": str(e)}
        else:
            debate_result = {"consensus": "Agreed approach for: " + task[:50]}

        step.output_data = debate_result
        step.status = "completed"

        return debate_result, step

    async def _execute_with_consensus(
        self, task: str, debate_result: dict, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, ExecutionStep]:
        """Execute with debate consensus."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 3,
            action="Execution with consensus",
            agent=analysis.recommended_agents[0] if analysis.recommended_agents else None,
            module=None,
            input_data={"task": task, "consensus": debate_result},
        )

        output = {
            "status": "completed",
            "task": task,
            "approach": "debate",
            "consensus": debate_result,
            "result": "Task executed with multi-agent consensus",
        }

        step.output_data = output
        step.status = "completed"

        return output, step

    async def _execute_react(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, list[ExecutionStep]]:
        """Execute using ReAct pattern."""
        steps = []
        iterations = min(analysis.estimated_steps, self.config.get("max_steps", 10))

        for i in range(iterations):
            step = ExecutionStep(
                step_number=len(self.execution_history) + 2 + i,
                action=f"ReAct iteration {i + 1}",
                agent=None,
                module="react",
                input_data={"task": task, "iteration": i},
            )

            # Simulated ReAct iteration
            step.output_data = {
                "thought": f"Thinking about step {i + 1}",
                "action": f"Executing step {i + 1}",
                "observation": f"Observed result of step {i + 1}",
            }
            step.status = "completed"
            steps.append(step)

        output = {
            "status": "completed",
            "task": task,
            "approach": "react",
            "iterations": iterations,
            "result": "Task completed via ReAct pattern",
        }

        return output, steps

    async def _compose_pipeline(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[dict, ExecutionStep]:
        """Compose skills into a pipeline."""
        step = ExecutionStep(
            step_number=len(self.execution_history) + 2,
            action="Composing skill pipeline",
            agent=None,
            module="composer",
            input_data={"task": task, "domains": analysis.domains},
        )

        if "composer" in self._modules and self._modules["composer"]:
            try:
                result = await self._modules["composer"].compose(task)
                pipeline = result.to_dict() if hasattr(result, "to_dict") else {"skills": []}
            except Exception:
                logger.exception(
                    "Error in composer compose for task %s",
                    task.get("id") if isinstance(task, dict) else str(task),
                )
                pipeline = {"skills": analysis.required_capabilities}
        else:
            pipeline = {"skills": analysis.required_capabilities}

        step.output_data = pipeline
        step.status = "completed"

        return pipeline, step

    async def _execute_pipeline(
        self, pipeline: dict, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, list[ExecutionStep]]:
        """Execute composed pipeline."""
        steps = []
        skills = pipeline.get("skills", [])

        for i, skill in enumerate(skills):
            step = ExecutionStep(
                step_number=len(self.execution_history) + 3 + i,
                action=f"Executing skill: {skill}",
                agent=None,
                module="composer",
                input_data={"skill": skill},
            )
            step.output_data = {"skill": skill, "status": "executed"}
            step.status = "completed"
            steps.append(step)

        output = {
            "status": "completed",
            "approach": "composed",
            "skills_executed": skills,
            "result": "Pipeline executed successfully",
        }

        return output, steps

    async def _execute_collaborative(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, list[ExecutionStep]]:
        """Execute with multiple agents collaborating."""
        steps = []
        agents = analysis.recommended_agents[:3]

        for i, agent in enumerate(agents):
            step = ExecutionStep(
                step_number=len(self.execution_history) + 2 + i,
                action=f"Agent {agent} contribution",
                agent=agent,
                module="messenger",
                input_data={"task": task, "agent": agent},
            )
            step.output_data = {"agent": agent, "contribution": f"Work from {agent}"}
            step.status = "completed"
            steps.append(step)

        # Synthesis step
        synthesis_step = ExecutionStep(
            step_number=len(self.execution_history) + 2 + len(agents),
            action="Synthesizing contributions",
            agent=None,
            module="collab_memory",
            input_data={"agents": agents},
        )
        synthesis_step.output_data = {"synthesis": "Combined work from all agents"}
        synthesis_step.status = "completed"
        steps.append(synthesis_step)

        output = {
            "status": "completed",
            "approach": "collaborative",
            "agents": agents,
            "result": "Collaborative execution completed",
        }

        return output, steps

    async def _execute_adaptive(
        self, task: str, analysis: TaskAnalysis, context: dict
    ) -> tuple[Any, list[ExecutionStep]]:
        """Execute with adaptive strategy changes."""
        steps = []
        current_strategy = ExecutionStrategy.THINK_FIRST

        # Start with thinking
        thinking, think_step = await self._execute_think(task, analysis, context)
        steps.append(think_step)

        # Adapt based on thinking
        if "uncertain" in str(thinking).lower():
            current_strategy = ExecutionStrategy.DEBATE
            debate_result, debate_step = await self._execute_debate(task, analysis, context)
            steps.append(debate_step)

        # Final execution
        exec_step = ExecutionStep(
            step_number=len(self.execution_history) + 2 + len(steps),
            action="Adaptive execution",
            agent=analysis.recommended_agents[0] if analysis.recommended_agents else None,
            module=None,
            input_data={"task": task, "adapted_strategy": current_strategy.value},
        )
        exec_step.output_data = {"result": "Adaptive execution completed"}
        exec_step.status = "completed"
        steps.append(exec_step)

        output = {
            "status": "completed",
            "approach": "adaptive",
            "strategies_used": [current_strategy.value],
            "result": "Adaptive execution completed",
        }

        return output, steps
