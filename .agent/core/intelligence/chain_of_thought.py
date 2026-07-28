#!/usr/bin/env python3
"""
Chain-of-Thought Module - Explicit reasoning before action.

This module enforces structured thinking:
- Break down complex problems into steps
- Show reasoning explicitly
- Validate each step before proceeding
- Enable debugging of agent decisions

Usage:
    from .agent.core.intelligence import ChainOfThought

    cot = ChainOfThought()
    result = await cot.reason(
        task="Design a scalable authentication system",
        agent_context={"expertise": "security"}
    )

    for step in result.steps:
        print(f"{step.step_num}. {step.thought}")
        print(f"   Confidence: {step.confidence}")
"""

import json
import logging
import os
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.chain_of_thought")


class ThoughtType(Enum):
    """Types of thoughts in the chain."""

    OBSERVATION = "observation"  # What I notice
    ANALYSIS = "analysis"  # Breaking down the problem
    HYPOTHESIS = "hypothesis"  # Possible approach
    EVALUATION = "evaluation"  # Assessing options
    DECISION = "decision"  # Choosing an approach
    VERIFICATION = "verification"  # Checking the decision
    CONCLUSION = "conclusion"  # Final synthesis


@dataclass
class ThoughtStep:
    """A single step in the chain of thought."""

    step_num: int
    thought_type: ThoughtType
    thought: str
    reasoning: str
    confidence: float  # 0.0 to 1.0
    evidence: list[str] = field(default_factory=list)
    alternatives_considered: list[str] = field(default_factory=list)
    risks_identified: list[str] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["thought_type"] = self.thought_type.value
        return d


@dataclass
class ChainOfThoughtResult:
    """Complete chain of thought for a task."""

    task: str
    steps: list[ThoughtStep]
    final_conclusion: str
    overall_confidence: float
    total_reasoning_time_ms: int
    key_insights: list[str]
    uncertainties: list[str]
    recommended_actions: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["steps"] = [s.to_dict() for s in self.steps]
        return d

    @staticmethod
    def _step_to_markdown(step: Any) -> list[str]:
        """Renderiza un paso de razonamiento a líneas markdown.

        Args:
            step: Paso del chain-of-thought.

        Returns:
            Lista de líneas markdown del paso (incluye evidencia/alternativas/riesgos).
        """
        lines = [
            f"### Step {step.step_num}: {step.thought_type.value.upper()}",
            "",
            f"**Thought:** {step.thought}",
            "",
            f"**Reasoning:** {step.reasoning}",
            "",
            f"**Confidence:** {step.confidence:.0%}",
        ]
        if step.evidence:
            lines.append("")
            lines.append("**Evidence:**")
            lines.extend(f"- {e}" for e in step.evidence)
        if step.alternatives_considered:
            lines.append("")
            lines.append("**Alternatives Considered:**")
            lines.extend(f"- {a}" for a in step.alternatives_considered)
        if step.risks_identified:
            lines.append("")
            lines.append("**Risks:**")
            lines.extend(f"- {r}" for r in step.risks_identified)
        lines.append("")
        return lines

    def to_markdown(self) -> str:
        """Convert to readable markdown format."""
        lines = [
            "# Chain of Thought Analysis",
            "",
            f"**Task:** {self.task}",
            f"**Confidence:** {self.overall_confidence:.0%}",
            f"**Reasoning Time:** {self.total_reasoning_time_ms}ms",
            "",
            "## Reasoning Steps",
            "",
        ]

        for step in self.steps:
            lines.extend(self._step_to_markdown(step))

        lines.extend(
            [
                "## Conclusion",
                "",
                self.final_conclusion,
                "",
                "## Key Insights",
                "",
            ]
        )

        for insight in self.key_insights:
            lines.append(f"- {insight}")

        if self.uncertainties:
            lines.extend(
                [
                    "",
                    "## Uncertainties",
                    "",
                ]
            )
            for u in self.uncertainties:
                lines.append(f"- {u}")

        lines.extend(
            [
                "",
                "## Recommended Actions",
                "",
            ]
        )
        for i, action in enumerate(self.recommended_actions, 1):
            lines.append(f"{i}. {action}")

        return "\n".join(lines)


class ChainOfThought:
    """
    Chain-of-Thought reasoning engine.

    Enforces explicit, step-by-step reasoning that can be
    inspected, debugged, and improved over time.
    """

    # Standard reasoning template
    REASONING_TEMPLATE = [
        ThoughtType.OBSERVATION,
        ThoughtType.ANALYSIS,
        ThoughtType.HYPOTHESIS,
        ThoughtType.EVALUATION,
        ThoughtType.DECISION,
        ThoughtType.VERIFICATION,
        ThoughtType.CONCLUSION,
    ]

    # Prompts for each thought type
    THOUGHT_PROMPTS = {
        ThoughtType.OBSERVATION: "What do I observe about this task? What are the key elements?",
        ThoughtType.ANALYSIS: "How can I break this down? What are the sub-problems?",
        ThoughtType.HYPOTHESIS: "What approaches could work? What patterns apply?",
        ThoughtType.EVALUATION: "What are the pros/cons of each approach?",
        ThoughtType.DECISION: "Which approach should I choose and why?",
        ThoughtType.VERIFICATION: "Is this decision sound? What could go wrong?",
        ThoughtType.CONCLUSION: "What is my final answer/solution?",
    }

    def __init__(
        self,
        memory_dir: Path | None = None,
        llm_reasoner: Callable | None = None,
        max_steps: int = 10,
    ):
        # 3-tier resolution: explicit param > env var > user home (NO repo path)
        if memory_dir:
            self.memory_dir = Path(memory_dir)
        elif os.environ.get("ANTIGRAVITY_THOUGHTS_PATH"):
            self.memory_dir = Path(os.environ["ANTIGRAVITY_THOUGHTS_PATH"])
        else:
            self.memory_dir = Path.home() / ".antigravity" / "memory" / "thoughts"
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.llm_reasoner = llm_reasoner
        self.max_steps = max_steps
        self.thought_history: list[ChainOfThoughtResult] = []
        logger.info("ChainOfThought engine initialized")

    async def reason(
        self,
        task: str,
        agent_context: dict[str, Any] | None = None,
        template: list[ThoughtType] | None = None,
        prior_knowledge: list[str] | None = None,
    ) -> ChainOfThoughtResult:
        """
        Perform chain-of-thought reasoning on a task.

        Args:
            task: The task to reason about
            agent_context: Context about the agent doing the reasoning
            template: Custom reasoning template (default: standard)
            prior_knowledge: Relevant prior knowledge to consider

        Returns:
            ChainOfThoughtResult with all reasoning steps
        """
        import time

        start_time = time.time()

        template = template or self.REASONING_TEMPLATE
        agent_context = agent_context or {}
        prior_knowledge = prior_knowledge or []

        logger.info(f"Starting chain-of-thought for: {task[:50]}...")

        steps = []
        accumulated_context = {
            "task": task,
            "agent": agent_context,
            "prior_knowledge": prior_knowledge,
            "previous_steps": [],
        }

        for i, thought_type in enumerate(template[: self.max_steps]):
            step = await self._generate_step(
                step_num=i + 1,
                thought_type=thought_type,
                context=accumulated_context,
            )
            steps.append(step)
            accumulated_context["previous_steps"].append(step.to_dict())  # type: ignore[attr-defined]  # dict value is list, safe at runtime

        # Generate final synthesis
        final_conclusion = self._synthesize_conclusion(steps)
        key_insights = self._extract_insights(steps)
        uncertainties = self._identify_uncertainties(steps)
        recommended_actions = self._generate_actions(steps, final_conclusion)
        overall_confidence = self._calculate_confidence(steps)

        elapsed_ms = int((time.time() - start_time) * 1000)

        result = ChainOfThoughtResult(
            task=task,
            steps=steps,
            final_conclusion=final_conclusion,
            overall_confidence=overall_confidence,
            total_reasoning_time_ms=elapsed_ms,
            key_insights=key_insights,
            uncertainties=uncertainties,
            recommended_actions=recommended_actions,
        )

        # Save result
        self.thought_history.append(result)
        await self._save_thought_chain(result)

        logger.info(
            f"Chain-of-thought complete: {len(steps)} steps, confidence: {overall_confidence:.0%}"
        )
        return result

    async def _generate_step(
        self,
        step_num: int,
        thought_type: ThoughtType,
        context: dict[str, Any],
    ) -> ThoughtStep:
        """Generate a single reasoning step."""
        prompt = self.THOUGHT_PROMPTS[thought_type]

        if self.llm_reasoner:
            return await self._llm_generate_step(step_num, thought_type, prompt, context)

        return self._heuristic_generate_step(step_num, thought_type, prompt, context)

    async def _llm_generate_step(
        self,
        step_num: int,
        thought_type: ThoughtType,
        prompt: str,
        context: dict[str, Any],
    ) -> ThoughtStep:
        """Use LLM to generate a reasoning step."""
        reasoning_prompt = f"""
You are reasoning through a task step by step.

TASK: {context["task"]}

PREVIOUS STEPS:
{json.dumps(context["previous_steps"], indent=2) if context["previous_steps"] else "None yet"}

CURRENT STEP: {thought_type.value.upper()}
QUESTION: {prompt}

Respond in JSON format:
{{
    "thought": "Your thought for this step",
    "reasoning": "Why you think this",
    "confidence": 0.0-1.0,
    "evidence": ["supporting evidence"],
    "alternatives_considered": ["other options you considered"],
    "risks_identified": ["potential risks"]
}}
"""
        try:
            response = await self.llm_reasoner(reasoning_prompt)  # type: ignore[misc]  # callable: Optional, checked at init
            data = json.loads(response)
            return ThoughtStep(
                step_num=step_num,
                thought_type=thought_type,
                thought=data.get("thought", ""),
                reasoning=data.get("reasoning", ""),
                confidence=float(data.get("confidence", 0.7)),
                evidence=data.get("evidence", []),
                alternatives_considered=data.get("alternatives_considered", []),
                risks_identified=data.get("risks_identified", []),
            )
        except Exception as e:
            logger.warning(f"LLM reasoning failed: {e}, using heuristic")
            return self._heuristic_generate_step(step_num, thought_type, prompt, context)

    def _heuristic_generate_step(
        self,
        step_num: int,
        thought_type: ThoughtType,
        prompt: str,
        context: dict[str, Any],
    ) -> ThoughtStep:
        """Heuristic-based reasoning step generation."""
        task = context["task"]
        task_lower = task.lower()

        # Generate thought based on type
        thoughts = {
            ThoughtType.OBSERVATION: f"The task asks to: {task[:100]}. Key elements: {', '.join(task.split()[:5])}",
            ThoughtType.ANALYSIS: "Breaking this down: 1) Understand requirements, 2) Identify constraints, 3) Plan approach",
            ThoughtType.HYPOTHESIS: "Possible approaches: standard patterns, custom solution, or hybrid approach",
            ThoughtType.EVALUATION: "Evaluating options based on: complexity, maintainability, performance, security",
            ThoughtType.DECISION: "Choosing the approach that balances simplicity with requirements coverage",
            ThoughtType.VERIFICATION: "Checking: Does this address all requirements? Any edge cases? Security ok?",
            ThoughtType.CONCLUSION: "The solution addresses the core requirements with room for iteration",
        }

        reasoning = {
            ThoughtType.OBSERVATION: "Identifying key task elements helps focus the solution",
            ThoughtType.ANALYSIS: "Breaking down complex tasks into manageable pieces",
            ThoughtType.HYPOTHESIS: "Considering multiple approaches before committing",
            ThoughtType.EVALUATION: "Systematic comparison leads to better decisions",
            ThoughtType.DECISION: "Explicit decision-making with clear rationale",
            ThoughtType.VERIFICATION: "Double-checking catches errors before they propagate",
            ThoughtType.CONCLUSION: "Synthesizing insights into actionable output",
        }

        # Estimate confidence based on task clarity
        confidence = 0.7
        if "?" in task or "how" in task_lower or "what" in task_lower:
            confidence = 0.8  # Questions are clearer
        if "complex" in task_lower or "advanced" in task_lower:
            confidence = 0.6  # Complex tasks have more uncertainty

        return ThoughtStep(
            step_num=step_num,
            thought_type=thought_type,
            thought=thoughts.get(thought_type, prompt),
            reasoning=reasoning.get(thought_type, "Standard reasoning"),
            confidence=confidence,
            evidence=["Task analysis", "Domain knowledge"],
            alternatives_considered=["Other approaches exist but weren't evaluated in detail"],
            risks_identified=["Assumptions may not hold in all cases"],
        )

    def _synthesize_conclusion(self, steps: list[ThoughtStep]) -> str:
        """Synthesize final conclusion from all steps."""
        conclusions = [s for s in steps if s.thought_type == ThoughtType.CONCLUSION]
        if conclusions:
            return conclusions[-1].thought

        # Fallback: combine key thoughts
        key_thoughts = [s.thought for s in steps if s.confidence >= 0.7]
        return " | ".join(key_thoughts[:3]) if key_thoughts else "Analysis complete"

    def _extract_insights(self, steps: list[ThoughtStep]) -> list[str]:
        """Extract key insights from reasoning chain."""
        insights = []

        for step in steps:
            if step.confidence >= 0.8:
                insights.append(f"[{step.thought_type.value}] {step.thought[:100]}")
            insights.extend(step.evidence[:1])  # Include top evidence

        return insights[:5]

    def _identify_uncertainties(self, steps: list[ThoughtStep]) -> list[str]:
        """Identify uncertainties from the reasoning chain."""
        uncertainties = []

        for step in steps:
            if step.confidence < 0.6:
                uncertainties.append(
                    f"Low confidence in {step.thought_type.value}: {step.reasoning[:50]}"
                )
            uncertainties.extend(step.risks_identified[:1])

        return uncertainties[:5]

    def _generate_actions(self, steps: list[ThoughtStep], conclusion: str) -> list[str]:
        """Generate recommended actions from reasoning."""
        actions = []
        if conclusion.strip():
            actions.append(f"Conclusion summary: {conclusion[:100]}")

        # Find decision step
        decisions = [s for s in steps if s.thought_type == ThoughtType.DECISION]
        if decisions:
            actions.append(f"Primary action: {decisions[-1].thought[:100]}")

        # Add verification actions
        verifications = [s for s in steps if s.thought_type == ThoughtType.VERIFICATION]
        for v in verifications:
            if v.risks_identified:
                actions.append(f"Mitigate risk: {v.risks_identified[0]}")

        actions.append("Review and iterate based on feedback")
        return actions[:5]

    def _calculate_confidence(self, steps: list[ThoughtStep]) -> float:
        """Calculate overall confidence from steps."""
        if not steps:
            return 0.5

        # Weight later steps more heavily
        weighted_sum = sum(step.confidence * (1 + step.step_num * 0.1) for step in steps)
        total_weight = sum(1 + step.step_num * 0.1 for step in steps)

        return weighted_sum / total_weight

    async def _save_thought_chain(self, result: ChainOfThoughtResult) -> None:
        """Save thought chain to disk."""
        try:
            filename = f"thought_chain_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.memory_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

            # Also save markdown version
            md_filepath = self.memory_dir / filename.replace(".json", ".md")
            with open(md_filepath, "w", encoding="utf-8") as f:
                f.write(result.to_markdown())
        except Exception as e:
            logger.warning(f"Failed to save thought chain: {e}")


# Convenience function
async def think_through(task: str) -> ChainOfThoughtResult:
    """Quick chain-of-thought reasoning."""
    cot = ChainOfThought()
    return await cot.reason(task)
