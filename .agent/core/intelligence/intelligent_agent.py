# mypy: ignore-errors
#!/usr/bin/env python3
"""
Intelligent Agent - Enhanced agent base with TOP A capabilities.

This module provides an enhanced agent base class that integrates:
- Self-Reflection
- Chain-of-Thought reasoning
- Metacognition
- Quality scoring
- Knowledge graph access

Usage:
    from .agent.core.intelligence import IntelligentAgent

    class MyAgent(IntelligentAgent):
        async def _execute_core(self, task: str) -> str:
            # Your agent logic here
            return result

    agent = MyAgent(name="my-agent")
    result = await agent.execute("Do something complex")
    # Automatically includes reflection, CoT, and quality scoring
"""

import inspect
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any

from .chain_of_thought import ChainOfThought, ChainOfThoughtResult
from .knowledge_graph import KnowledgeGraph
from .metacognition import ConfidenceAssessment, Metacognition
from .quality_scorer import QualityScore, QualityScorer
from .self_reflection import ReflectionResult, SelfReflection

logger = logging.getLogger("antigravity.intelligence.intelligent_agent")


@dataclass
class ExecutionContext:
    """Context for an intelligent execution."""

    task: str
    agent_name: str
    start_time: datetime = field(default_factory=datetime.now)
    chain_of_thought: ChainOfThoughtResult | None = None
    metacognition: ConfidenceAssessment | None = None
    reflection: ReflectionResult | None = None
    quality_score: QualityScore | None = None
    retries: int = 0
    final_output: str = ""
    success: bool = False


@dataclass
class IntelligentResult:
    """Result from intelligent agent execution."""

    output: str
    success: bool
    confidence: float
    quality_grade: str
    reasoning_trace: str
    reflections: list[str]
    suggestions: list[str]
    execution_time_ms: int
    retries: int
    metadata: dict[str, Any] = field(default_factory=dict)


class IntelligentAgent(ABC):
    """
    Enhanced agent base with integrated intelligence capabilities.

    This class provides:
    1. Automatic chain-of-thought reasoning before action
    2. Metacognitive assessment of capabilities
    3. Self-reflection on outputs
    4. Quality scoring with retry logic
    5. Knowledge graph integration

    Subclasses must implement _execute_core() with their specific logic.
    """

    # Configuration
    CONFIDENCE_THRESHOLD = 0.6
    QUALITY_THRESHOLD = 0.70
    MAX_RETRIES = 2

    def __init__(
        self,
        name: str,
        expertise: list[str] | None = None,
        memory_dir: Path | None = None,
        enable_cot: bool = True,
        enable_reflection: bool = True,
        enable_quality_check: bool = True,
        enable_metacognition: bool = True,
    ):
        self.name = name
        self.expertise = expertise or []
        self.memory_dir = memory_dir or Path(f".agent/memory/{name}")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        # Feature flags
        self.enable_cot = enable_cot
        self.enable_reflection = enable_reflection
        self.enable_quality_check = enable_quality_check
        self.enable_metacognition = enable_metacognition

        # Initialize components
        self.chain_of_thought = ChainOfThought(memory_dir=self.memory_dir / "thoughts")
        self.self_reflection = SelfReflection(memory_dir=self.memory_dir / "reflections")
        self.metacognition = Metacognition(memory_dir=self.memory_dir / "metacognition")
        self.quality_scorer = QualityScorer(memory_dir=self.memory_dir / "quality")
        self.knowledge_graph = KnowledgeGraph(storage_path=self.memory_dir / "knowledge")

        logger.info(f"IntelligentAgent '{name}' initialized with expertise: {expertise}")

    @abstractmethod
    async def _execute_core(self, task: str, context: ExecutionContext) -> str:
        """
        Core execution logic - must be implemented by subclasses.

        Args:
            task: The task to execute
            context: Execution context with reasoning and metacognition results

        Returns:
            The agent's output string
        """
        pass

    async def execute(
        self,
        task: str,
        context: dict[str, Any] | None = None,
    ) -> IntelligentResult:
        """
        Execute task with full intelligence pipeline.

        Pipeline:
        1. Metacognition - Assess if we can handle this
        2. Chain-of-Thought - Reason through the problem
        3. Core Execution - Do the actual work
        4. Self-Reflection - Evaluate our output
        5. Quality Check - Score the output
        6. Retry if needed - Improve based on feedback
        """
        import time

        start_time = time.time()

        exec_context = ExecutionContext(task=task, agent_name=self.name)
        context = context or {}

        logger.info(f"[{self.name}] Starting intelligent execution: {task[:50]}...")

        # Phase 1: Metacognition - Can we handle this?
        if self.enable_metacognition:
            exec_context.metacognition = await self.metacognition.assess(
                task=task,
                agent_expertise=self.expertise,
                context=context,
            )

            logger.info(
                f"[{self.name}] Metacognition: confidence={exec_context.metacognition.calibrated_confidence:.0%}"
            )

            # Check if we should escalate
            if exec_context.metacognition.should_escalate:
                logger.warning(f"[{self.name}] Metacognition suggests escalation")
                # Could integrate with stuck agent here

        # Phase 2: Chain-of-Thought - Reason through it
        if self.enable_cot:
            exec_context.chain_of_thought = await self.chain_of_thought.reason(
                task=task,
                agent_context={"name": self.name, "expertise": self.expertise},
            )

            logger.info(
                f"[{self.name}] Chain-of-Thought: {len(exec_context.chain_of_thought.steps)} steps"
            )

        # Phase 3: Core Execution with retry loop
        output = ""
        while exec_context.retries <= self.MAX_RETRIES:
            try:
                output = await self._execute_core(task, exec_context)
                exec_context.final_output = output

                # Phase 4: Self-Reflection
                if self.enable_reflection:
                    exec_context.reflection = await self.self_reflection.reflect(
                        task=task,
                        output=output,
                        agent_name=self.name,
                    )

                    logger.info(
                        f"[{self.name}] Reflection: confidence={exec_context.reflection.overall_confidence:.0%}"
                    )

                    # Check if we should retry based on reflection
                    if (
                        exec_context.reflection.should_retry
                        and exec_context.retries < self.MAX_RETRIES
                    ):
                        logger.info(
                            f"[{self.name}] Reflection suggests retry. Attempt {exec_context.retries + 1}"
                        )
                        exec_context.retries += 1
                        # Add reflection feedback to context for retry
                        context["retry_suggestions"] = exec_context.reflection.retry_suggestions
                        continue

                # Phase 5: Quality Check
                if self.enable_quality_check:
                    exec_context.quality_score = await self.quality_scorer.score(
                        agent_name=self.name,
                        task=task,
                        output=output,
                    )

                    logger.info(
                        f"[{self.name}] Quality: {exec_context.quality_score.grade.value} ({exec_context.quality_score.overall_score:.0%})"
                    )

                    # Check if we should retry based on quality
                    if (
                        not exec_context.quality_score.pass_threshold
                        and exec_context.retries < self.MAX_RETRIES
                    ):
                        logger.info(
                            f"[{self.name}] Quality check failed. Retry {exec_context.retries + 1}"
                        )
                        exec_context.retries += 1
                        context["quality_suggestions"] = (
                            exec_context.quality_score.improvement_suggestions
                        )
                        continue

                # Success!
                exec_context.success = True
                break

            except Exception as e:
                logger.error(f"[{self.name}] Execution error: {e}")
                exec_context.retries += 1
                if exec_context.retries > self.MAX_RETRIES:
                    output = f"Error after {self.MAX_RETRIES} retries: {str(e)}"
                    break

        # Record to knowledge graph
        await self._record_execution(exec_context)

        elapsed_ms = int((time.time() - start_time) * 1000)

        return IntelligentResult(
            output=exec_context.final_output,
            success=exec_context.success,
            confidence=self._get_confidence(exec_context),
            quality_grade=exec_context.quality_score.grade.value
            if exec_context.quality_score
            else "N/A",
            reasoning_trace=self._get_reasoning_trace(exec_context),
            reflections=self._get_reflections(exec_context),
            suggestions=self._get_suggestions(exec_context),
            execution_time_ms=elapsed_ms,
            retries=exec_context.retries,
            metadata={
                "metacognition": exec_context.metacognition.to_dict()
                if exec_context.metacognition
                else None,
                "cot_steps": len(exec_context.chain_of_thought.steps)
                if exec_context.chain_of_thought
                else 0,
            },
        )

    def _get_confidence(self, ctx: ExecutionContext) -> float:
        """Calculate overall confidence from various sources."""
        confidences = []

        if ctx.metacognition:
            confidences.append(ctx.metacognition.calibrated_confidence)

        if ctx.reflection:
            confidences.append(ctx.reflection.overall_confidence)

        if ctx.quality_score:
            confidences.append(ctx.quality_score.overall_score)

        if ctx.chain_of_thought:
            confidences.append(ctx.chain_of_thought.overall_confidence)

        return sum(confidences) / len(confidences) if confidences else 0.5

    def _get_reasoning_trace(self, ctx: ExecutionContext) -> str:
        """Get readable reasoning trace."""
        parts = []

        if ctx.metacognition:
            parts.append(f"METACOGNITION: {ctx.metacognition.recommended_approach}")

        if ctx.chain_of_thought:
            parts.append(f"REASONING: {ctx.chain_of_thought.final_conclusion[:200]}")

        if ctx.reflection:
            parts.append(f"REFLECTION: {ctx.reflection.summary}")

        if ctx.quality_score:
            parts.append(f"QUALITY: {ctx.quality_score.grade.value}")

        return " | ".join(parts)

    def _get_reflections(self, ctx: ExecutionContext) -> list[str]:
        """Get list of reflections and insights."""
        reflections = []

        if ctx.reflection:
            reflections.extend(ctx.reflection.blind_spots[:2])
            reflections.extend(ctx.reflection.assumptions[:2])

        if ctx.chain_of_thought:
            reflections.extend(ctx.chain_of_thought.uncertainties[:2])

        return reflections

    def _get_suggestions(self, ctx: ExecutionContext) -> list[str]:
        """Get improvement suggestions."""
        suggestions = []

        if ctx.reflection:
            suggestions.extend(ctx.reflection.retry_suggestions[:2])

        if ctx.quality_score:
            suggestions.extend(ctx.quality_score.improvement_suggestions[:3])

        if ctx.metacognition:
            suggestions.extend(ctx.metacognition.questions_to_clarify[:2])

        return suggestions[:5]

    async def _record_execution(self, ctx: ExecutionContext) -> None:
        """Record execution to knowledge graph for learning."""
        from .knowledge_graph import EdgeType, NodeType

        # Create execution node
        exec_id = f"exec:{self.name}:{datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.knowledge_graph.add_node(
            node_id=exec_id,
            content=f"Execution: {ctx.task[:100]}",
            node_type=NodeType.ACTION,
            tags=["execution", self.name],
            confidence=self._get_confidence(ctx),
            metadata={
                "success": ctx.success,
                "retries": ctx.retries,
                "quality_grade": ctx.quality_score.grade.value if ctx.quality_score else None,
            },
        )

        # Link to agent node
        agent_id = f"agent:{self.name}"
        if agent_id not in self.knowledge_graph.nodes:
            self.knowledge_graph.add_node(
                node_id=agent_id,
                content=f"Agent: {self.name}",
                node_type=NodeType.ENTITY,
                tags=["agent"] + self.expertise,
            )

        self.knowledge_graph.add_edge(agent_id, exec_id, EdgeType.LEADS_TO)

        # Record lessons if failed
        if not ctx.success and ctx.quality_score:
            for issue in ctx.quality_score.critical_issues:
                lesson_id = f"lesson:{hash(issue) % 10000}"
                self.knowledge_graph.add_node(
                    node_id=lesson_id,
                    content=issue,
                    node_type=NodeType.LESSON,
                    tags=["failure", self.name],
                )
                self.knowledge_graph.add_edge(exec_id, lesson_id, EdgeType.LEARNED_FROM)

    async def query_knowledge(self, query: str, limit: int = 5) -> list[str]:
        """Query the knowledge graph for relevant information."""
        results = self.knowledge_graph.search(query, limit=limit)
        return [node.content for node, score in results]


class SimpleIntelligentAgent(IntelligentAgent):
    """
    Simple implementation of IntelligentAgent for quick use.

    Allows providing a function as the core logic.
    """

    def __init__(
        self,
        name: str,
        execute_fn: Callable | None = None,
        **kwargs,
    ):
        super().__init__(name=name, **kwargs)
        self._execute_fn = execute_fn

    async def _execute_core(self, task: str, context: ExecutionContext) -> str:
        if self._execute_fn:
            if inspect.iscoroutinefunction(self._execute_fn):
                return await self._execute_fn(task, context)
            return self._execute_fn(task, context)

        # Default implementation
        return f"[{self.name}] Processed task: {task}"


# Convenience function
def create_intelligent_agent(
    name: str,
    execute_fn: Callable | None = None,
    expertise: list[str] | None = None,
    **kwargs,
) -> SimpleIntelligentAgent:
    """Create an intelligent agent quickly."""
    return SimpleIntelligentAgent(
        name=name,
        execute_fn=execute_fn,
        expertise=expertise,
        **kwargs,
    )
