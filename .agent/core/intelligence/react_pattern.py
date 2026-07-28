# mypy: ignore-errors
#!/usr/bin/env python3
"""
ReAct Pattern Module - Reasoning + Acting in a loop.

Implements the ReAct (Reasoning and Acting) pattern where agents:
1. THINK - Reason about the current situation
2. ACT - Take an action (tool use, query, etc.)
3. OBSERVE - See the result of the action
4. Repeat until task is complete

This creates a powerful loop of deliberate reasoning combined with
concrete actions, enabling complex multi-step problem solving.

Usage:
    from .agent.core.intelligence import ReActAgent

    agent = ReActAgent(tools={"search": search_fn, "read": read_fn})
    result = await agent.solve("Find all security vulnerabilities in src/auth/")
"""

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.react")


class StepType(Enum):
    """Types of steps in the ReAct loop."""

    THOUGHT = "thought"
    ACTION = "action"
    OBSERVATION = "observation"


@dataclass
class Thought:
    """A reasoning step."""

    content: str
    confidence: float
    next_action_planned: str
    reasoning: str


@dataclass
class Action:
    """An action to be taken."""

    tool: str
    parameters: dict[str, Any]
    rationale: str


@dataclass
class Observation:
    """Result of an action."""

    action_taken: str
    result: str
    success: bool
    insights: list[str]


@dataclass
class ReActStep:
    """A single step in the ReAct loop."""

    step_num: int
    step_type: StepType
    content: Any  # Thought, Action, or Observation
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = {
            "step_num": self.step_num,
            "step_type": self.step_type.value,
            "timestamp": self.timestamp,
        }
        if isinstance(self.content, (Thought, Action, Observation)):
            d["content"] = asdict(self.content)
        else:
            d["content"] = str(self.content)
        return d


@dataclass
class ReActResult:
    """Complete result of a ReAct reasoning session."""

    task: str
    steps: list[ReActStep]
    final_answer: str
    success: bool
    total_actions: int
    total_thoughts: int
    reasoning_trace: str
    lessons_learned: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            **asdict(self),
            "steps": [s.to_dict() for s in self.steps],
        }

    def to_trace(self) -> str:
        """Generate human-readable reasoning trace."""
        lines = [f"# ReAct Trace: {self.task}", ""]

        for step in self.steps:
            if step.step_type == StepType.THOUGHT:
                lines.append(
                    f"**THOUGHT {step.step_num}:** {step.content.content if isinstance(step.content, Thought) else step.content}"
                )
            elif step.step_type == StepType.ACTION:
                if isinstance(step.content, Action):
                    lines.append(
                        f"**ACTION {step.step_num}:** {step.content.tool}({step.content.parameters})"
                    )
                else:
                    lines.append(f"**ACTION {step.step_num}:** {step.content}")
            elif step.step_type == StepType.OBSERVATION:
                if isinstance(step.content, Observation):
                    lines.append(f"**OBSERVATION {step.step_num}:** {step.content.result[:200]}...")
                else:
                    lines.append(f"**OBSERVATION {step.step_num}:** {str(step.content)[:200]}...")
            lines.append("")

        lines.extend(
            [
                "---",
                f"**FINAL ANSWER:** {self.final_answer}",
                f"**SUCCESS:** {self.success}",
            ]
        )

        return "\n".join(lines)


class ReActAgent:
    """
    ReAct (Reasoning + Acting) Agent.

    Implements the ReAct pattern for complex problem solving
    through interleaved reasoning and action steps.
    """

    MAX_ITERATIONS = 15

    def __init__(
        self,
        tools: dict[str, Callable[..., Awaitable[str]]] | None = None,
        llm_reasoner: Callable | None = None,
        memory_dir: Path | None = None,
        max_iterations: int = MAX_ITERATIONS,
    ):
        self.tools = tools or {}
        self.llm_reasoner = llm_reasoner
        self.memory_dir = memory_dir or Path(".agent/memory/react")
        self.memory_dir.mkdir(parents=True, exist_ok=True)
        self.max_iterations = max_iterations
        self.history: list[ReActResult] = []
        logger.info(f"ReActAgent initialized with tools: {list(self.tools.keys())}")

    def register_tool(
        self,
        name: str,
        func: Callable[..., Awaitable[str]],
        description: str = "",
    ) -> None:
        """Register a tool for the agent to use."""
        self.tools[name] = func
        logger.info(f"Registered tool: {name}")

    async def solve(
        self,
        task: str,
        context: dict[str, Any] | None = None,
        max_iterations: int | None = None,
    ) -> ReActResult:
        """
        Solve a task using the ReAct pattern.

        Args:
            task: The task to solve
            context: Optional context information
            max_iterations: Override default max iterations

        Returns:
            ReActResult with complete reasoning trace
        """
        max_iter = max_iterations or self.max_iterations
        context = context or {}

        logger.info(f"Starting ReAct solving: {task[:50]}...")

        steps: list[ReActStep] = []
        step_num = 0
        task_complete = False
        final_answer = ""

        # Initial thought
        thought = await self._think(task, steps, context)
        steps.append(
            ReActStep(
                step_num=step_num,
                step_type=StepType.THOUGHT,
                content=thought,
            )
        )
        step_num += 1

        while (
            not task_complete and step_num < max_iter * 3
        ):  # *3 for thought-action-observation cycles
            # Decide on action
            action = await self._decide_action(task, steps, context)
            steps.append(
                ReActStep(
                    step_num=step_num,
                    step_type=StepType.ACTION,
                    content=action,
                )
            )
            step_num += 1

            # Execute action
            observation = await self._execute_action(action)
            steps.append(
                ReActStep(
                    step_num=step_num,
                    step_type=StepType.OBSERVATION,
                    content=observation,
                )
            )
            step_num += 1

            # Reflect and decide if complete
            thought = await self._think(task, steps, context)
            steps.append(
                ReActStep(
                    step_num=step_num,
                    step_type=StepType.THOUGHT,
                    content=thought,
                )
            )
            step_num += 1

            # Check for completion
            task_complete, final_answer = self._check_completion(thought, steps)

        if not final_answer:
            final_answer = self._synthesize_answer(steps)

        # Extract lessons
        lessons = self._extract_lessons(steps)

        result = ReActResult(
            task=task,
            steps=steps,
            final_answer=final_answer,
            success=task_complete,
            total_actions=sum(1 for s in steps if s.step_type == StepType.ACTION),
            total_thoughts=sum(1 for s in steps if s.step_type == StepType.THOUGHT),
            reasoning_trace=self._generate_trace(steps),
            lessons_learned=lessons,
        )

        self.history.append(result)
        await self._save_result(result)

        logger.info(f"ReAct complete: {result.total_actions} actions, success: {result.success}")
        return result

    async def _think(
        self,
        task: str,
        steps: list[ReActStep],
        context: dict[str, Any],
    ) -> Thought:
        """Generate a thought about the current situation."""
        if self.llm_reasoner:
            return await self._llm_think(task, steps, context)
        return self._heuristic_think(task, steps, context)

    async def _llm_think(
        self,
        task: str,
        steps: list[ReActStep],
        context: dict[str, Any],
    ) -> Thought:
        """Use LLM to generate thought."""
        recent_steps = steps[-6:] if steps else []
        steps_text = "\n".join(f"[{s.step_type.value}] {s.content}" for s in recent_steps)

        prompt = f"""
You are solving this task: {task}

Recent steps:
{steps_text or "None yet"}

Available tools: {list(self.tools.keys())}

Think about what you know and what to do next.
Respond in JSON:
{{
    "content": "Your thought",
    "confidence": 0.0-1.0,
    "next_action_planned": "What tool to use next or 'FINISH' if done",
    "reasoning": "Why this is the right next step"
}}
"""
        try:
            response = await self.llm_reasoner(prompt)
            data = json.loads(response)
            return Thought(**data)
        except Exception as e:
            logger.warning(f"LLM think failed: {e}")
            return self._heuristic_think(task, steps, context)

    def _heuristic_think(
        self,
        task: str,
        steps: list[ReActStep],
        context: dict[str, Any],
    ) -> Thought:
        """Heuristic thought generation."""
        action_count = sum(1 for s in steps if s.step_type == StepType.ACTION)

        if action_count == 0:
            return Thought(
                content=f"I need to solve: {task}. Let me start by exploring.",
                confidence=0.8,
                next_action_planned=list(self.tools.keys())[0] if self.tools else "search",
                reasoning="Starting with exploration to understand the problem",
            )

        # Check last observation
        last_obs = [s for s in steps if s.step_type == StepType.OBSERVATION]
        if last_obs:
            obs = last_obs[-1]
            if isinstance(obs.content, Observation) and obs.content.success:
                if action_count >= 3:
                    return Thought(
                        content="I have gathered enough information. Let me synthesize an answer.",
                        confidence=0.85,
                        next_action_planned="FINISH",
                        reasoning="Multiple successful actions completed",
                    )

        return Thought(
            content="Continuing to gather more information.",
            confidence=0.7,
            next_action_planned=list(self.tools.keys())[0] if self.tools else "continue",
            reasoning="Need more data to complete the task",
        )

    async def _decide_action(
        self,
        task: str,
        steps: list[ReActStep],
        context: dict[str, Any],
    ) -> Action:
        """Decide what action to take next."""
        # Get the last thought
        last_thoughts = [s for s in steps if s.step_type == StepType.THOUGHT]
        if last_thoughts:
            thought = last_thoughts[-1].content
            if isinstance(thought, Thought):
                tool_name = thought.next_action_planned
                if tool_name and tool_name != "FINISH" and tool_name in self.tools:
                    return Action(
                        tool=tool_name,
                        parameters={"query": task, "context": "from reasoning"},
                        rationale=thought.reasoning,
                    )

        # Default action
        tool_name = list(self.tools.keys())[0] if self.tools else "search"
        return Action(
            tool=tool_name,
            parameters={"query": task},
            rationale="Default exploration action",
        )

    async def _execute_action(self, action: Action) -> Observation:
        """Execute an action using available tools."""
        tool_name = action.tool

        if tool_name not in self.tools:
            return Observation(
                action_taken=f"{tool_name}({action.parameters})",
                result=f"Tool '{tool_name}' not available. Available: {list(self.tools.keys())}",
                success=False,
                insights=["Need to use an available tool"],
            )

        try:
            tool_func = self.tools[tool_name]
            result = await tool_func(**action.parameters)

            return Observation(
                action_taken=f"{tool_name}({action.parameters})",
                result=str(result),
                success=True,
                insights=self._extract_insights_from_result(result),
            )
        except Exception as e:
            logger.warning(f"Action execution failed: {e}")
            return Observation(
                action_taken=f"{tool_name}({action.parameters})",
                result=f"Error: {str(e)}",
                success=False,
                insights=["Action failed, may need different approach"],
            )

    def _extract_insights_from_result(self, result: str) -> list[str]:
        """Extract key insights from action result."""
        insights = []
        result_lower = result.lower()

        # Check for common patterns
        if "error" in result_lower or "failed" in result_lower:
            insights.append("Result contains errors")
        if "success" in result_lower or "found" in result_lower:
            insights.append("Action was successful")
        if len(result) > 1000:
            insights.append("Large result - may contain detailed information")
        if len(result) < 50:
            insights.append("Short result - may need more exploration")

        return insights or ["Result received"]

    def _check_completion(
        self,
        thought: Thought,
        steps: list[ReActStep],
    ) -> tuple[bool, str]:
        """Check if the task is complete."""
        # Check if thought indicates completion
        if thought.next_action_planned == "FINISH":
            return True, thought.content

        if thought.confidence >= 0.9 and "answer" in thought.content.lower():
            return True, thought.content

        # Check iteration limits
        action_count = sum(1 for s in steps if s.step_type == StepType.ACTION)
        if action_count >= self.max_iterations:
            return True, "Reached maximum iterations. Best answer based on gathered information."

        return False, ""

    def _synthesize_answer(self, steps: list[ReActStep]) -> str:
        """Synthesize final answer from all steps."""
        observations = [
            s.content
            for s in steps
            if s.step_type == StepType.OBSERVATION and isinstance(s.content, Observation)
        ]

        successful_obs = [o for o in observations if o.success]

        if successful_obs:
            insights = []
            for obs in successful_obs:
                insights.extend(obs.insights)
            return f"Based on {len(successful_obs)} successful actions: {'; '.join(set(insights))}"

        return "Unable to complete task fully. Partial information gathered."

    def _extract_lessons(self, steps: list[ReActStep]) -> list[str]:
        """Extract lessons learned from the session."""
        lessons = []

        # Analyze what worked
        successful_actions = [
            s
            for s in steps
            if s.step_type == StepType.OBSERVATION
            and isinstance(s.content, Observation)
            and s.content.success
        ]

        if successful_actions:
            lessons.append(f"Successful approach: {successful_actions[0].content.action_taken}")

        # Analyze what didn't work
        failed_actions = [
            s
            for s in steps
            if s.step_type == StepType.OBSERVATION
            and isinstance(s.content, Observation)
            and not s.content.success
        ]

        if failed_actions:
            lessons.append(f"Approach to avoid: {failed_actions[0].content.action_taken}")

        return lessons

    def _generate_trace(self, steps: list[ReActStep]) -> str:
        """Generate reasoning trace string."""
        parts = []
        for step in steps:
            if step.step_type == StepType.THOUGHT:
                content = (
                    step.content.content if isinstance(step.content, Thought) else str(step.content)
                )
                parts.append(f"THINK: {content}")
            elif step.step_type == StepType.ACTION:
                if isinstance(step.content, Action):
                    parts.append(f"ACT: {step.content.tool}")
                else:
                    parts.append(f"ACT: {step.content}")
            elif step.step_type == StepType.OBSERVATION:
                if isinstance(step.content, Observation):
                    parts.append(f"OBSERVE: {'OK' if step.content.success else 'FAIL'}")
                else:
                    parts.append(f"OBSERVE: {str(step.content)[:50]}")

        return " -> ".join(parts)

    async def _save_result(self, result: ReActResult) -> None:
        """Save ReAct result to disk."""
        try:
            filename = f"react_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            filepath = self.memory_dir / filename
            with open(filepath, "w", encoding="utf-8") as f:
                json.dump(result.to_dict(), f, indent=2, ensure_ascii=False)

            # Save trace
            trace_path = self.memory_dir / filename.replace(".json", "_trace.md")
            with open(trace_path, "w", encoding="utf-8") as f:
                f.write(result.to_trace())
        except Exception as e:
            logger.warning(f"Failed to save ReAct result: {e}")


# Built-in tools for common operations
async def search_tool(query: str, **kwargs) -> str:
    """Simple search tool placeholder."""
    return f"Search results for: {query}"


async def read_tool(path: str, **kwargs) -> str:
    """Read file tool."""
    try:
        with open(path, encoding="utf-8") as f:
            return f.read()[:2000]
    except Exception as e:
        return f"Error reading {path}: {e}"


async def list_tool(path: str = ".", **kwargs) -> str:
    """List directory tool."""
    try:
        p = Path(path)
        files = list(p.iterdir())[:20]
        return "\n".join(str(f) for f in files)
    except Exception as e:
        return f"Error listing {path}: {e}"


def create_default_react_agent() -> ReActAgent:
    """Create a ReActAgent with default tools."""
    agent = ReActAgent()
    agent.register_tool("search", search_tool, "Search for information")
    agent.register_tool("read", read_tool, "Read a file")
    agent.register_tool("list", list_tool, "List directory contents")
    return agent
