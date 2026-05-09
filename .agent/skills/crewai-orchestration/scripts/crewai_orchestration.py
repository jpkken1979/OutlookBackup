#!/usr/bin/env python3
"""
CrewAI-Inspired Orchestration Skill

Multi-agent orchestration following CrewAI patterns:
- Role-based agents with goals and backstories
- Task management with dependencies
- Sequential, parallel, and hierarchical processes
- Shared memory between agents
"""

import asyncio
import json
import yaml
from dataclasses import dataclass, field
from enum import Enum
from typing import Any
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ProcessType(Enum):
    """Crew execution process types."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HIERARCHICAL = "hierarchical"


@dataclass
class Agent:
    """
    An agent with a specific role in the crew.

    Attributes:
        name: Unique identifier
        role: The agent's function (e.g., "Code Reviewer")
        goal: What the agent aims to achieve
        backstory: Context that shapes behavior
        tools: List of tools/skills available
        allow_delegation: Can delegate to other agents
        verbose: Enable detailed logging
    """

    name: str
    role: str
    goal: str
    backstory: str = ""
    tools: list[str] = field(default_factory=list)
    allow_delegation: bool = False
    verbose: bool = True
    max_iterations: int = 10

    def __post_init__(self):
        if not self.backstory:
            self.backstory = f"You are a {self.role} focused on achieving: {self.goal}"


@dataclass
class Task:
    """
    A task to be executed by an agent.

    Attributes:
        name: Unique identifier
        description: What needs to be done
        agent: Agent responsible for this task
        expected_output: Format of expected result
        context: List of previous tasks whose output is needed
        async_execution: Run asynchronously
    """

    name: str
    description: str
    agent: Agent
    expected_output: str = "Task completion report"
    context: list["Task"] = field(default_factory=list)
    async_execution: bool = False
    output: str | None = None

    def __hash__(self):
        return hash(self.name)


@dataclass
class TaskResult:
    """Result of a task execution."""

    task_name: str
    agent_name: str
    output: str
    success: bool
    duration_ms: float
    tokens_used: int = 0
    error: str | None = None


@dataclass
class CrewResult:
    """Result of a crew execution."""

    crew_name: str
    process_type: str
    task_results: list[TaskResult] = field(default_factory=list)
    final_output: str = ""
    total_duration_ms: float = 0
    success: bool = True

    def to_dict(self) -> dict:
        return {
            "crew_name": self.crew_name,
            "process_type": self.process_type,
            "success": self.success,
            "total_duration_ms": self.total_duration_ms,
            "final_output": self.final_output,
            "tasks": [
                {
                    "task": r.task_name,
                    "agent": r.agent_name,
                    "success": r.success,
                    "duration_ms": r.duration_ms,
                    "output": r.output[:200] + "..." if len(r.output) > 200 else r.output,
                }
                for r in self.task_results
            ],
        }


class SharedMemory:
    """
    Shared memory system for crew communication.

    Implements three types of memory:
    - Short-term: Current session context
    - Long-term: Persistent learnings (simulated)
    - Entity: Information about mentioned entities
    """

    def __init__(self):
        self.short_term: dict[str, Any] = {}
        self.long_term: dict[str, Any] = {}
        self.entities: dict[str, dict] = {}
        self.conversation: list[dict] = []

    def store(self, key: str, value: Any, memory_type: str = "short_term"):
        """Store a value in memory."""
        if memory_type == "short_term":
            self.short_term[key] = value
        elif memory_type == "long_term":
            self.long_term[key] = value
        elif memory_type == "entity":
            self.entities[key] = value

    def retrieve(self, key: str, memory_type: str = "short_term") -> Any | None:
        """Retrieve a value from memory."""
        if memory_type == "short_term":
            return self.short_term.get(key)
        elif memory_type == "long_term":
            return self.long_term.get(key)
        elif memory_type == "entity":
            return self.entities.get(key)
        return None

    def add_message(self, role: str, content: str):
        """Add a message to conversation history."""
        self.conversation.append(
            {"role": role, "content": content, "timestamp": datetime.now().isoformat()}
        )

    def get_context(self) -> str:
        """Get relevant context for agents."""
        context_parts = []

        if self.short_term:
            context_parts.append("## Current Session Context")
            for k, v in self.short_term.items():
                context_parts.append(f"- {k}: {v}")

        if self.entities:
            context_parts.append("\n## Known Entities")
            for entity, info in self.entities.items():
                context_parts.append(f"- {entity}: {info}")

        return "\n".join(context_parts)


class Crew:
    """
    A crew of agents working together on tasks.

    Supports three execution processes:
    - Sequential: Tasks run one after another
    - Parallel: Independent tasks run simultaneously
    - Hierarchical: A manager agent coordinates others
    """

    def __init__(
        self,
        name: str = "Crew",
        agents: list[Agent] = None,
        tasks: list[Task] = None,
        process: ProcessType = ProcessType.SEQUENTIAL,
        manager: Agent | None = None,
        verbose: bool = True,
    ):
        self.name = name
        self.agents = agents or []
        self.tasks = tasks or []
        self.process = process
        self.manager = manager
        self.verbose = verbose
        self.memory = SharedMemory()

        # Map Antigravity agents
        self.agent_mapping = {
            "code reviewer": "code-reviewer",
            "security expert": "security-auditor",
            "test engineer": "test-engineer",
            "architect": "architect",
            "planner": "planner",
            "backend developer": "backend-specialist",
            "frontend developer": "frontend-specialist",
            "debugger": "debugger",
        }

    async def kickoff(self, inputs: dict | None = None) -> CrewResult:
        """
        Start the crew execution.

        Args:
            inputs: Initial inputs for the crew

        Returns:
            CrewResult with all task outputs
        """
        logger.info(f"🚀 Starting crew '{self.name}' with {len(self.tasks)} tasks")
        start_time = datetime.now()

        # Store inputs in memory
        if inputs:
            for key, value in inputs.items():
                self.memory.store(key, value)

        result = CrewResult(crew_name=self.name, process_type=self.process.value)

        try:
            if self.process == ProcessType.SEQUENTIAL:
                task_results = await self._run_sequential()
            elif self.process == ProcessType.PARALLEL:
                task_results = await self._run_parallel()
            elif self.process == ProcessType.HIERARCHICAL:
                task_results = await self._run_hierarchical()
            else:
                task_results = await self._run_sequential()

            result.task_results = task_results
            result.success = all(r.success for r in task_results)

            # Combine outputs for final result
            if task_results:
                result.final_output = task_results[-1].output

        except Exception as e:
            logger.error(f"Crew execution failed: {e}")
            result.success = False
            result.final_output = str(e)

        end_time = datetime.now()
        result.total_duration_ms = (end_time - start_time).total_seconds() * 1000

        logger.info(f"✅ Crew completed in {result.total_duration_ms:.0f}ms")
        return result

    async def _run_sequential(self) -> list[TaskResult]:
        """Run tasks sequentially, passing context between them."""
        results = []

        for i, task in enumerate(self.tasks):
            logger.info(f"📋 Task {i + 1}/{len(self.tasks)}: {task.name}")

            # Build context from previous tasks
            context = self._build_context(task, results)

            # Execute task
            task_result = await self._execute_task(task, context)
            results.append(task_result)

            # Store result in memory
            self.memory.store(f"task_{task.name}_output", task_result.output)

            if not task_result.success:
                logger.warning(f"Task {task.name} failed, continuing...")

        return results

    async def _run_parallel(self) -> list[TaskResult]:
        """Run independent tasks in parallel."""
        # Group tasks by dependencies
        independent_tasks = [t for t in self.tasks if not t.context]
        dependent_tasks = [t for t in self.tasks if t.context]

        results = []

        # Run independent tasks in parallel
        if independent_tasks:
            logger.info(f"Running {len(independent_tasks)} tasks in parallel")
            parallel_results = await asyncio.gather(
                *[self._execute_task(task, "") for task in independent_tasks]
            )
            results.extend(parallel_results)

            # Store results
            for task, result in zip(independent_tasks, parallel_results, strict=False):
                self.memory.store(f"task_{task.name}_output", result.output)

        # Run dependent tasks sequentially
        for task in dependent_tasks:
            context = self._build_context(task, results)
            task_result = await self._execute_task(task, context)
            results.append(task_result)
            self.memory.store(f"task_{task.name}_output", task_result.output)

        return results

    async def _run_hierarchical(self) -> list[TaskResult]:
        """Run with a manager agent coordinating."""
        if not self.manager:
            logger.warning("No manager specified, falling back to sequential")
            return await self._run_sequential()

        results = []

        # Manager reviews tasks and assigns order
        logger.info(f"🎯 Manager '{self.manager.role}' coordinating crew")

        # For now, delegate to sequential with manager oversight
        for task in self.tasks:
            context = self._build_context(task, results)

            # Manager pre-review
            manager_guidance = f"Manager guidance: Execute {task.name} efficiently"
            full_context = f"{context}\n\n{manager_guidance}"

            task_result = await self._execute_task(task, full_context)
            results.append(task_result)

            self.memory.store(f"task_{task.name}_output", task_result.output)

        return results

    def _build_context(self, task: Task, previous_results: list[TaskResult]) -> str:
        """Build context for a task from previous results and memory."""
        context_parts = []

        # Add memory context
        memory_context = self.memory.get_context()
        if memory_context:
            context_parts.append(memory_context)

        # Add context from dependency tasks
        if task.context:
            context_parts.append("\n## Previous Task Outputs")
            for dep_task in task.context:
                for result in previous_results:
                    if result.task_name == dep_task.name:
                        context_parts.append(f"\n### {dep_task.name}")
                        context_parts.append(result.output)

        return "\n".join(context_parts)

    async def _execute_task(self, task: Task, context: str) -> TaskResult:
        """Execute a single task."""
        start_time = datetime.now()

        # Build the prompt for the agent
        prompt = self._build_agent_prompt(task, context)

        # Simulate agent execution (in real impl, this would call the LLM)
        output = await self._simulate_agent_execution(task.agent, prompt, task)

        end_time = datetime.now()
        duration_ms = (end_time - start_time).total_seconds() * 1000

        return TaskResult(
            task_name=task.name,
            agent_name=task.agent.name,
            output=output,
            success=True,
            duration_ms=duration_ms,
        )

    def _build_agent_prompt(self, task: Task, context: str) -> str:
        """Build the full prompt for an agent."""
        agent = task.agent

        return f"""# Agent Profile
Role: {agent.role}
Goal: {agent.goal}
Backstory: {agent.backstory}

# Task
{task.description}

# Expected Output
{task.expected_output}

# Context
{context}

# Instructions
Execute this task to the best of your abilities. Use your expertise as a {agent.role}.
"""

    async def _simulate_agent_execution(self, agent: Agent, prompt: str, task: Task) -> str:
        """
        Simulate agent execution.

        In a real implementation, this would:
        1. Call the appropriate LLM
        2. Use the agent's tools
        3. Iterate if needed
        """
        # For demonstration, return a structured response
        return f"""# Task Result: {task.name}

## Agent: {agent.role}

## Analysis
Executed task: {task.description}

## Output
Task completed successfully by {agent.role}.
The agent applied expertise to achieve: {agent.goal}

## Recommendations
- Continue with dependent tasks
- Review output for quality assurance

---
*Executed by {agent.name} agent*
"""


def load_crew_from_yaml(yaml_path: str) -> Crew:
    """Load a crew configuration from YAML file."""
    with open(yaml_path) as f:
        config = yaml.safe_load(f)

    # Parse agents
    agents = {}
    for agent_config in config.get("agents", []):
        agent = Agent(
            name=agent_config["name"],
            role=agent_config["role"],
            goal=agent_config["goal"],
            backstory=agent_config.get("backstory", ""),
            tools=agent_config.get("tools", []),
            allow_delegation=agent_config.get("allow_delegation", False),
        )
        agents[agent.name] = agent

    # Parse tasks
    tasks = []
    for task_config in config.get("tasks", []):
        agent_name = task_config["agent"]
        if agent_name not in agents:
            raise ValueError(f"Unknown agent: {agent_name}")

        task = Task(
            name=task_config["name"],
            description=task_config["description"],
            agent=agents[agent_name],
            expected_output=task_config.get("expected_output", "Task completion"),
        )
        tasks.append(task)

    # Handle task dependencies
    for i, task_config in enumerate(config.get("tasks", [])):
        if "context" in task_config:
            context_tasks = []
            for ctx_name in task_config["context"]:
                for t in tasks:
                    if t.name == ctx_name:
                        context_tasks.append(t)
            tasks[i].context = context_tasks

    # Parse crew config
    crew_config = config.get("crew", {})
    process_str = crew_config.get("process", "sequential")
    process = ProcessType(process_str)

    manager = None
    if "manager" in crew_config and crew_config["manager"] in agents:
        manager = agents[crew_config["manager"]]

    return Crew(
        name=crew_config.get("name", "Crew"),
        agents=list(agents.values()),
        tasks=tasks,
        process=process,
        manager=manager,
    )


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="CrewAI Orchestration Skill")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Run command
    run_parser = subparsers.add_parser("run", help="Run a crew")
    run_parser.add_argument("--config", "-c", required=True, help="YAML config file")
    run_parser.add_argument("--input", "-i", help="Input string")
    run_parser.add_argument("--json", action="store_true", help="JSON output")

    # Demo command
    subparsers.add_parser("demo", help="Run demo crew")

    args = parser.parse_args()

    if args.command == "run":
        crew = load_crew_from_yaml(args.config)

        inputs = {}
        if args.input:
            inputs["user_input"] = args.input

        result = await crew.kickoff(inputs=inputs)

        if args.json:
            print(json.dumps(result.to_dict(), indent=2))
        else:
            print(f"\n{'=' * 60}")
            print(f"Crew: {result.crew_name}")
            print(f"Process: {result.process_type}")
            print(f"Duration: {result.total_duration_ms:.0f}ms")
            print(f"Success: {'✅' if result.success else '❌'}")
            print(f"{'=' * 60}")
            print(f"\n{result.final_output}")

    elif args.command == "demo":
        # Create a demo crew
        reviewer = Agent(
            name="reviewer",
            role="Senior Code Reviewer",
            goal="Find bugs and improve code quality",
            backstory="Expert developer with 10 years experience",
        )

        tester = Agent(
            name="tester",
            role="Test Engineer",
            goal="Ensure comprehensive test coverage",
            backstory="QA specialist focused on edge cases",
        )

        review_task = Task(
            name="review_code",
            description="Review the code for bugs, style issues, and improvements",
            agent=reviewer,
            expected_output="List of issues with severity and suggestions",
        )

        test_task = Task(
            name="generate_tests",
            description="Generate tests for the reviewed code",
            agent=tester,
            context=[review_task],
            expected_output="pytest test file",
        )

        crew = Crew(
            name="Code Review Crew",
            agents=[reviewer, tester],
            tasks=[review_task, test_task],
            process=ProcessType.SEQUENTIAL,
        )

        result = await crew.kickoff(inputs={"code": "example.py"})
        print(json.dumps(result.to_dict(), indent=2))


if __name__ == "__main__":
    asyncio.run(main())
