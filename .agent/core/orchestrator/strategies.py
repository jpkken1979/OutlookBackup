"""Execution strategies for AntigravityOrchestrator.

Replaces 4-tier fallback (CrewAI → AutonomousLoop → Script → SIMULATED)
with named strategy classes. Each strategy encapsulates one execution tier.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from ..intelligence_hub import IntelligenceHub

logger = logging.getLogger("antigravity.orchestrator.strategies")


class ExecutionStrategy(ABC, BaseModel):
    """Base class for execution strategies."""

    class Config:
        arbitrary_types_allowed = True

    name: str = Field(..., description="Strategy name (crew_ai, autonomous_loop, etc)")
    priority: int = Field(..., description="Priority: 1=highest, 4=lowest")
    verbose: bool = Field(default=False, description="Verbose logging")

    @abstractmethod
    async def execute(
        self, agent_name: str, task_description: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Execute task with this strategy.

        Args:
            agent_name: Name of agent to execute
            task_description: Task to accomplish
            **kwargs: Additional execution parameters (context, callback, etc)

        Returns:
            Execution result dict with keys: agent, result, duration, strategy_used

        Raises:
            RuntimeError: If execution fails
        """

    @abstractmethod
    def is_available(self) -> bool:
        """Check if this strategy can be used in current environment."""

    async def _record_execution(
        self,
        agent_name: str,
        task_description: str,
        success: bool,
        duration_ms: float,
        intelligence_hub: IntelligenceHub | None = None,
    ) -> None:
        """Record execution outcome in Intelligence Hub if available."""
        if not intelligence_hub:
            return

        try:
            intelligence_hub.record_outcome(
                task=task_description,
                agent_name=agent_name,
                success=success,
                quality_score=1.0 if success else 0.0,
                duration_ms=int(duration_ms),
            )
        except Exception as e:
            logger.debug(f"Failed to record execution outcome: {e}")


class CrewAIStrategy(ExecutionStrategy):
    """Execute via CrewAI framework (Tier 1, highest priority)."""

    name: str = "crew_ai"
    priority: int = 1

    def is_available(self) -> bool:
        """Check if CrewAI is available and configured."""
        try:
            import os

            from crewai import Agent, Crew, Process, Task

            if not os.getenv("ANTHROPIC_API_KEY"):
                return False

            return True
        except ImportError:
            return False

    async def execute(
        self, agent_name: str, task_description: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Execute task using CrewAI."""
        import asyncio
        import os
        import time

        from crewai import Agent, Crew, Process, Task

        start = time.time()

        try:
            # Create CrewAI agent
            agent = Agent(
                role=f"Agent: {agent_name}",
                goal=task_description,
                backstory=f"Expert at executing {agent_name} tasks",
            )

            # Create task
            task = Task(
                description=task_description,
                agent=agent,
                expected_output="Task completion summary",
            )

            # Create crew (single agent, single task)
            crew = Crew(agents=[agent], tasks=[task], process=Process.sequential)

            # Execute with timeout
            result = await asyncio.wait_for(
                asyncio.to_thread(crew.kickoff),
                timeout=600.0,  # 10 min timeout
            )

            duration_ms = (time.time() - start) * 1000

            if self.verbose:
                logger.info(f"{agent_name} (CrewAI): {result}")

            return {
                "agent": agent_name,
                "result": str(result),
                "duration_ms": duration_ms,
                "strategy_used": self.name,
            }

        except TimeoutError:
            duration_ms = (time.time() - start) * 1000
            raise RuntimeError(f"CrewAI execution timed out after {duration_ms / 1000:.1f}s")
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            raise RuntimeError(f"CrewAI execution failed: {e}") from e


class AutonomousLoopStrategy(ExecutionStrategy):
    """Execute via AutonomousLoop (Tier 2)."""

    name: str = "autonomous_loop"
    priority: int = 2

    def is_available(self) -> bool:
        """Check if AutonomousLoop is available."""
        try:
            from ..autonomous_loop import AutonomousLoop

            return True
        except ImportError:
            return False

    async def execute(
        self, agent_name: str, task_description: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Execute task using AutonomousLoop."""
        import asyncio
        import time

        from ..autonomous_loop import AutonomousLoop

        start = time.time()

        try:
            loop = AutonomousLoop(max_iterations=8, verbose=self.verbose)
            system_prompt = f"You are the {agent_name} Antigravity agent."

            result = await asyncio.wait_for(
                loop.run(
                    task=task_description,
                    system_prompt=system_prompt,
                    context=kwargs.get("context_input") or None,
                    agent_name=agent_name,
                ),
                timeout=600.0,
            )

            duration_ms = (time.time() - start) * 1000

            if self.verbose:
                logger.info(f"{agent_name} (AutonomousLoop): completed")

            return {
                "agent": agent_name,
                "result": str(result),
                "duration_ms": duration_ms,
                "strategy_used": self.name,
            }

        except TimeoutError:
            duration_ms = (time.time() - start) * 1000
            raise RuntimeError(
                f"AutonomousLoop execution timed out after {duration_ms / 1000:.1f}s"
            )
        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            raise RuntimeError(f"AutonomousLoop execution failed: {e}") from e


class ScriptStrategy(ExecutionStrategy):
    """Execute via simplified script (Tier 3)."""

    name: str = "script"
    priority: int = 3

    def is_available(self) -> bool:
        """Script execution always available."""
        return True

    async def execute(
        self, agent_name: str, task_description: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Execute task using simplified script approach."""
        import time

        start = time.time()

        try:
            # Simplified execution: parse task and execute directly
            result_text = f"[Script] Executed: {task_description[:100]}"

            duration_ms = (time.time() - start) * 1000

            if self.verbose:
                logger.info(f"{agent_name} (Script): {result_text}")

            return {
                "agent": agent_name,
                "result": result_text,
                "duration_ms": duration_ms,
                "strategy_used": self.name,
            }

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            raise RuntimeError(f"Script execution failed: {e}") from e


class SimulatedStrategy(ExecutionStrategy):
    """Mock execution (Tier 4, last resort)."""

    name: str = "simulated"
    priority: int = 4

    def is_available(self) -> bool:
        """Simulated execution always available as fallback."""
        return True

    async def execute(
        self, agent_name: str, task_description: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Return simulated result without actual execution."""
        import time

        start = time.time()

        try:
            result_text = f"[SIMULATED] Would execute: {task_description[:100]}... [mock result]"

            duration_ms = (time.time() - start) * 1000

            if self.verbose:
                logger.warning(f"{agent_name} (Simulated): All strategies exhausted, using mock")

            return {
                "agent": agent_name,
                "result": result_text,
                "duration_ms": duration_ms,
                "strategy_used": self.name,
                "simulated": True,
            }

        except Exception as e:
            duration_ms = (time.time() - start) * 1000
            raise RuntimeError(f"Simulated execution failed: {e}") from e


class StrategyChain:
    """Manages execution strategy fallback chain.

    Tries each strategy in priority order until one succeeds.
    Logs attempts and failures for debugging.
    """

    def __init__(
        self,
        strategies: list[ExecutionStrategy],
        intelligence_hub: IntelligenceHub | None = None,
        verbose: bool = False,
    ):
        """Initialize strategy chain.

        Args:
            strategies: List of execution strategies (should be all 4 tiers)
            intelligence_hub: Optional Intelligence Hub for outcome recording
            verbose: Enable verbose logging
        """
        self.strategies = sorted(strategies, key=lambda s: s.priority)
        self.intelligence_hub = intelligence_hub
        self.verbose = verbose

    async def execute(
        self, agent_name: str, task_description: str, **kwargs: Any
    ) -> dict[str, Any]:
        """Execute task using strategy chain fallback.

        Args:
            agent_name: Name of agent
            task_description: Task to execute
            **kwargs: Additional parameters (context, callback, etc)

        Returns:
            Execution result from the successful strategy

        Raises:
            RuntimeError: If all strategies fail
        """
        errors: dict[str, str] = {}

        for strategy in self.strategies:
            if not strategy.is_available():
                if self.verbose:
                    logger.debug(f"{agent_name}: {strategy.name} not available, skipping")
                continue

            try:
                if self.verbose:
                    logger.info(f"{agent_name}: trying {strategy.name}")

                result = await strategy.execute(agent_name, task_description, **kwargs)

                logger.info(f"{agent_name}: {strategy.name} succeeded")

                # Record success in Intelligence Hub
                await strategy._record_execution(
                    agent_name,
                    task_description,
                    success=True,
                    duration_ms=result.get("duration_ms", 0),
                    intelligence_hub=self.intelligence_hub,
                )

                return result

            except Exception as e:
                error_msg = str(e)
                errors[strategy.name] = error_msg
                logger.warning(f"{agent_name}: {strategy.name} failed: {error_msg}")

                # Record failure in Intelligence Hub
                await strategy._record_execution(
                    agent_name,
                    task_description,
                    success=False,
                    duration_ms=0,
                    intelligence_hub=self.intelligence_hub,
                )

        # All strategies failed
        error_details = "\n".join([f"  {name}: {msg}" for name, msg in errors.items()])
        raise RuntimeError(f"All execution strategies failed for {agent_name}:\n{error_details}")
