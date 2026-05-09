#!/usr/bin/env python3
"""
Planner Agent - Strategic Task Planning and Decomposition

Capabilities:
- Break down complex tasks into actionable steps
- Estimate complexity and dependencies
- Generate execution plans with parallel/sequential paths
- Identify required agents and skills
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class TaskComplexity(Enum):
    TRIVIAL = "trivial"  # < 30 min
    SIMPLE = "simple"  # 30 min - 2 hours
    MODERATE = "moderate"  # 2-8 hours
    COMPLEX = "complex"  # 1-3 days
    EPIC = "epic"  # > 3 days


class ExecutionMode(Enum):
    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    HYBRID = "hybrid"


@dataclass
class PlanStep:
    """A single step in the execution plan."""

    id: str
    title: str
    description: str
    complexity: TaskComplexity
    agent: str
    skills: list[str] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)
    estimated_minutes: int = 30
    parallel_group: int | None = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "description": self.description,
            "complexity": self.complexity.value,
            "agent": self.agent,
            "skills": self.skills,
            "dependencies": self.dependencies,
            "estimated_minutes": self.estimated_minutes,
            "parallel_group": self.parallel_group,
        }


@dataclass
class ExecutionPlan:
    """Complete execution plan for a task."""

    task: str
    summary: str
    total_steps: int
    execution_mode: ExecutionMode
    steps: list[PlanStep] = field(default_factory=list)
    total_estimated_minutes: int = 0
    agents_required: list[str] = field(default_factory=list)
    skills_required: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    created_at: str = ""

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "summary": self.summary,
            "execution_mode": self.execution_mode.value,
            "total_steps": self.total_steps,
            "total_estimated_minutes": self.total_estimated_minutes,
            "agents_required": self.agents_required,
            "skills_required": self.skills_required,
            "risks": self.risks,
            "steps": [s.to_dict() for s in self.steps],
            "created_at": self.created_at,
        }

    def to_markdown(self) -> str:
        """Generate markdown representation of the plan."""
        lines = [
            "# Execution Plan",
            "",
            f"**Task:** {self.task}",
            "",
            "## Summary",
            f"{self.summary}",
            "",
            "## Metrics",
            f"- **Total Steps:** {self.total_steps}",
            f"- **Execution Mode:** {self.execution_mode.value}",
            f"- **Estimated Time:** {self.total_estimated_minutes} minutes",
            f"- **Agents Required:** {', '.join(self.agents_required)}",
            "",
            "## Steps",
            "",
        ]

        current_group = None
        for step in self.steps:
            if step.parallel_group != current_group:
                if step.parallel_group is not None:
                    lines.append(f"\n### Parallel Group {step.parallel_group}")
                current_group = step.parallel_group

            deps = f" (depends on: {', '.join(step.dependencies)})" if step.dependencies else ""
            lines.append(f"### {step.id}. {step.title}")
            lines.append(f"- **Agent:** {step.agent}")
            lines.append(f"- **Complexity:** {step.complexity.value}")
            lines.append(f"- **Est. Time:** {step.estimated_minutes} min{deps}")
            lines.append(f"- **Description:** {step.description}")
            if step.skills:
                lines.append(f"- **Skills:** {', '.join(step.skills)}")
            lines.append("")

        if self.risks:
            lines.append("## Risks")
            for risk in self.risks:
                lines.append(f"- {risk}")

        return "\n".join(lines)


class PlannerAgent:
    """
    Strategic Planner Agent.

    Analyzes tasks and creates detailed execution plans with:
    - Step decomposition
    - Agent assignment
    - Dependency mapping
    - Parallel execution opportunities
    """

    # Task patterns for classification
    TASK_PATTERNS = {
        "feature": r"(create|add|implement|build|develop)\s+(new\s+)?(feature|functionality|module|component)",
        "bug": r"(fix|resolve|debug|repair|patch)\s+(bug|issue|error|problem)",
        "refactor": r"(refactor|restructure|reorganize|clean\s*up|improve)\s+(code|module|function)",
        "test": r"(test|write\s+tests|add\s+tests|testing|coverage)",
        "docs": r"(document|documentation|readme|docs|write\s+docs)",
        "security": r"(security|vulnerability|audit|penetration|owasp)",
        "performance": r"(performance|optimize|speed|latency|throughput)",
        "api": r"(api|endpoint|rest|graphql|grpc)",
        "database": r"(database|db|migration|schema|query)",
        "ui": r"(ui|ux|frontend|design|interface|component)",
        "devops": r"(deploy|ci|cd|docker|kubernetes|pipeline)",
        "auth": r"(auth|authentication|authorization|login|oauth|jwt)",
    }

    # Agent recommendations by task type
    AGENT_RECOMMENDATIONS = {
        "feature": [
            "planner",
            "architect",
            "backend-specialist",
            "frontend-specialist",
            "test-engineer",
        ],
        "bug": ["debugger", "explorer", "test-engineer"],
        "refactor": ["refactor", "code-reviewer", "architect"],
        "test": ["test-engineer", "qa-specialist"],
        "docs": ["documentation-writer", "docusaurus-expert"],
        "security": ["security-auditor", "code-reviewer"],
        "performance": ["performance-optimizer", "debugger"],
        "api": ["api-designer", "backend-specialist"],
        "database": ["database-architect", "backend-specialist"],
        "ui": ["ui-ux-designer", "frontend-specialist", "react-specialist"],
        "devops": ["devops-engineer", "mcp-integrator"],
        "auth": ["security-auditor", "backend-specialist"],
    }

    def __init__(self):
        self.plans_created = 0

    async def create_plan(self, task: str, context: str | None = None) -> ExecutionPlan:
        """
        Create an execution plan for a task.

        Args:
            task: The task description
            context: Optional additional context

        Returns:
            ExecutionPlan with steps and metadata
        """
        logger.info(f"Creating plan for: {task[:50]}...")

        # Classify task
        task_type = self._classify_task(task)
        logger.info(f"Task classified as: {task_type}")

        # Get recommended agents
        recommended_agents = self.AGENT_RECOMMENDATIONS.get(task_type, ["explorer", "planner"])

        # Generate steps based on task type
        steps = self._generate_steps(task, task_type, recommended_agents)

        # Calculate metrics
        total_minutes = sum(s.estimated_minutes for s in steps)
        all_agents = list({s.agent for s in steps})
        all_skills = list({skill for s in steps for skill in s.skills})

        # Determine execution mode
        execution_mode = self._determine_execution_mode(steps)

        # Identify risks
        risks = self._identify_risks(task, task_type, steps)

        # Create summary
        summary = self._generate_summary(task, task_type, steps)

        plan = ExecutionPlan(
            task=task,
            summary=summary,
            total_steps=len(steps),
            execution_mode=execution_mode,
            steps=steps,
            total_estimated_minutes=total_minutes,
            agents_required=all_agents,
            skills_required=all_skills,
            risks=risks,
        )

        self.plans_created += 1
        logger.info(f"Plan created with {len(steps)} steps")

        return plan

    def _classify_task(self, task: str) -> str:
        """Classify task based on patterns."""
        task_lower = task.lower()

        for task_type, pattern in self.TASK_PATTERNS.items():
            if re.search(pattern, task_lower):
                return task_type

        return "feature"  # Default

    def _generate_steps(self, task: str, task_type: str, agents: list[str]) -> list[PlanStep]:
        """Generate execution steps based on task type."""
        steps = []
        step_id = 1

        # Common initial steps
        steps.append(
            PlanStep(
                id=f"S{step_id}",
                title="Analyze Requirements",
                description=f"Understand the full scope of: {task}",
                complexity=TaskComplexity.SIMPLE,
                agent="explorer",
                skills=["code-analysis"],
                estimated_minutes=15,
            )
        )
        step_id += 1

        # Task-specific steps
        if task_type == "feature":
            steps.extend(self._feature_steps(step_id, task))
        elif task_type == "bug":
            steps.extend(self._bug_steps(step_id, task))
        elif task_type == "refactor":
            steps.extend(self._refactor_steps(step_id, task))
        elif task_type == "security":
            steps.extend(self._security_steps(step_id, task))
        elif task_type == "api":
            steps.extend(self._api_steps(step_id, task))
        elif task_type == "test":
            steps.extend(self._test_steps(step_id, task))
        else:
            steps.extend(self._generic_steps(step_id, task, agents))

        # Common final steps
        final_id = len(steps) + 1
        steps.append(
            PlanStep(
                id=f"S{final_id}",
                title="Review and Validate",
                description="Final review of all changes and validation",
                complexity=TaskComplexity.SIMPLE,
                agent="code-reviewer",
                skills=["code-review"],
                dependencies=[f"S{final_id - 1}"],
                estimated_minutes=20,
            )
        )

        return steps

    def _feature_steps(self, start_id: int, task: str) -> list[PlanStep]:
        """Generate steps for feature development."""
        return [
            PlanStep(
                id=f"S{start_id}",
                title="Design Architecture",
                description="Design the technical architecture for the feature",
                complexity=TaskComplexity.MODERATE,
                agent="architect",
                skills=["system-design", "architecture-patterns"],
                dependencies=["S1"],
                estimated_minutes=45,
            ),
            PlanStep(
                id=f"S{start_id + 1}",
                title="Implement Backend",
                description="Implement backend logic and APIs",
                complexity=TaskComplexity.MODERATE,
                agent="backend-specialist",
                skills=["backend-patterns", "api-design"],
                dependencies=[f"S{start_id}"],
                estimated_minutes=90,
                parallel_group=1,
            ),
            PlanStep(
                id=f"S{start_id + 2}",
                title="Implement Frontend",
                description="Implement frontend components and UI",
                complexity=TaskComplexity.MODERATE,
                agent="frontend-specialist",
                skills=["frontend-patterns", "react-patterns"],
                dependencies=[f"S{start_id}"],
                estimated_minutes=90,
                parallel_group=1,
            ),
            PlanStep(
                id=f"S{start_id + 3}",
                title="Write Tests",
                description="Create unit and integration tests",
                complexity=TaskComplexity.SIMPLE,
                agent="test-engineer",
                skills=["testing-patterns"],
                dependencies=[f"S{start_id + 1}", f"S{start_id + 2}"],
                estimated_minutes=60,
            ),
            PlanStep(
                id=f"S{start_id + 4}",
                title="Security Review",
                description="Review for security vulnerabilities",
                complexity=TaskComplexity.SIMPLE,
                agent="security-auditor",
                skills=["security-scanning"],
                dependencies=[f"S{start_id + 3}"],
                estimated_minutes=30,
            ),
        ]

    def _bug_steps(self, start_id: int, task: str) -> list[PlanStep]:
        """Generate steps for bug fixing."""
        return [
            PlanStep(
                id=f"S{start_id}",
                title="Reproduce Bug",
                description="Reproduce the bug and understand the root cause",
                complexity=TaskComplexity.SIMPLE,
                agent="debugger",
                skills=["debugging"],
                dependencies=["S1"],
                estimated_minutes=30,
            ),
            PlanStep(
                id=f"S{start_id + 1}",
                title="Identify Root Cause",
                description="Deep analysis to find the exact cause",
                complexity=TaskComplexity.MODERATE,
                agent="debugger",
                skills=["debugging", "code-analysis"],
                dependencies=[f"S{start_id}"],
                estimated_minutes=45,
            ),
            PlanStep(
                id=f"S{start_id + 2}",
                title="Implement Fix",
                description="Implement the fix with minimal changes",
                complexity=TaskComplexity.SIMPLE,
                agent="backend-specialist",
                skills=["backend-patterns"],
                dependencies=[f"S{start_id + 1}"],
                estimated_minutes=30,
            ),
            PlanStep(
                id=f"S{start_id + 3}",
                title="Add Regression Test",
                description="Add test to prevent regression",
                complexity=TaskComplexity.SIMPLE,
                agent="test-engineer",
                skills=["testing-patterns"],
                dependencies=[f"S{start_id + 2}"],
                estimated_minutes=20,
            ),
        ]

    def _refactor_steps(self, start_id: int, task: str) -> list[PlanStep]:
        """Generate steps for refactoring."""
        return [
            PlanStep(
                id=f"S{start_id}",
                title="Analyze Current Code",
                description="Understand current implementation and identify issues",
                complexity=TaskComplexity.SIMPLE,
                agent="explorer",
                skills=["code-analysis"],
                dependencies=["S1"],
                estimated_minutes=30,
            ),
            PlanStep(
                id=f"S{start_id + 1}",
                title="Design Refactoring Plan",
                description="Plan the refactoring approach",
                complexity=TaskComplexity.SIMPLE,
                agent="refactor",
                skills=["refactoring-patterns"],
                dependencies=[f"S{start_id}"],
                estimated_minutes=30,
            ),
            PlanStep(
                id=f"S{start_id + 2}",
                title="Ensure Test Coverage",
                description="Verify existing tests or add new ones",
                complexity=TaskComplexity.SIMPLE,
                agent="test-engineer",
                skills=["testing-patterns"],
                dependencies=[f"S{start_id + 1}"],
                estimated_minutes=30,
            ),
            PlanStep(
                id=f"S{start_id + 3}",
                title="Execute Refactoring",
                description="Perform the refactoring in small increments",
                complexity=TaskComplexity.MODERATE,
                agent="refactor",
                skills=["refactoring-patterns"],
                dependencies=[f"S{start_id + 2}"],
                estimated_minutes=60,
            ),
        ]

    def _security_steps(self, start_id: int, task: str) -> list[PlanStep]:
        """Generate steps for security tasks."""
        return [
            PlanStep(
                id=f"S{start_id}",
                title="Security Scan",
                description="Run automated security scans",
                complexity=TaskComplexity.SIMPLE,
                agent="security-auditor",
                skills=["security-scanning", "sast"],
                dependencies=["S1"],
                estimated_minutes=30,
            ),
            PlanStep(
                id=f"S{start_id + 1}",
                title="Manual Security Review",
                description="Manual review of critical paths",
                complexity=TaskComplexity.MODERATE,
                agent="security-auditor",
                skills=["security-patterns", "owasp"],
                dependencies=[f"S{start_id}"],
                estimated_minutes=60,
            ),
            PlanStep(
                id=f"S{start_id + 2}",
                title="Remediate Findings",
                description="Fix identified vulnerabilities",
                complexity=TaskComplexity.MODERATE,
                agent="backend-specialist",
                skills=["security-patterns"],
                dependencies=[f"S{start_id + 1}"],
                estimated_minutes=90,
            ),
            PlanStep(
                id=f"S{start_id + 3}",
                title="Verify Fixes",
                description="Re-scan to verify fixes",
                complexity=TaskComplexity.SIMPLE,
                agent="security-auditor",
                skills=["security-scanning"],
                dependencies=[f"S{start_id + 2}"],
                estimated_minutes=20,
            ),
        ]

    def _api_steps(self, start_id: int, task: str) -> list[PlanStep]:
        """Generate steps for API development."""
        return [
            PlanStep(
                id=f"S{start_id}",
                title="Design API Contract",
                description="Design OpenAPI/GraphQL schema",
                complexity=TaskComplexity.MODERATE,
                agent="api-designer",
                skills=["api-design", "openapi"],
                dependencies=["S1"],
                estimated_minutes=45,
            ),
            PlanStep(
                id=f"S{start_id + 1}",
                title="Implement Endpoints",
                description="Implement API endpoints",
                complexity=TaskComplexity.MODERATE,
                agent="backend-specialist",
                skills=["backend-patterns", "api-patterns"],
                dependencies=[f"S{start_id}"],
                estimated_minutes=90,
            ),
            PlanStep(
                id=f"S{start_id + 2}",
                title="Add Validation",
                description="Add input validation and error handling",
                complexity=TaskComplexity.SIMPLE,
                agent="backend-specialist",
                skills=["validation-patterns"],
                dependencies=[f"S{start_id + 1}"],
                estimated_minutes=30,
            ),
            PlanStep(
                id=f"S{start_id + 3}",
                title="Write API Tests",
                description="Create API integration tests",
                complexity=TaskComplexity.SIMPLE,
                agent="test-engineer",
                skills=["api-testing"],
                dependencies=[f"S{start_id + 2}"],
                estimated_minutes=45,
            ),
            PlanStep(
                id=f"S{start_id + 4}",
                title="Generate Documentation",
                description="Generate API documentation",
                complexity=TaskComplexity.SIMPLE,
                agent="documentation-writer",
                skills=["api-documentation"],
                dependencies=[f"S{start_id + 3}"],
                estimated_minutes=20,
            ),
        ]

    def _test_steps(self, start_id: int, task: str) -> list[PlanStep]:
        """Generate steps for testing tasks."""
        return [
            PlanStep(
                id=f"S{start_id}",
                title="Analyze Test Coverage",
                description="Identify gaps in current test coverage",
                complexity=TaskComplexity.SIMPLE,
                agent="test-engineer",
                skills=["testing-patterns"],
                dependencies=["S1"],
                estimated_minutes=20,
            ),
            PlanStep(
                id=f"S{start_id + 1}",
                title="Write Unit Tests",
                description="Create unit tests for uncovered code",
                complexity=TaskComplexity.MODERATE,
                agent="test-engineer",
                skills=["testing-patterns", "mocking"],
                dependencies=[f"S{start_id}"],
                estimated_minutes=60,
            ),
            PlanStep(
                id=f"S{start_id + 2}",
                title="Write Integration Tests",
                description="Create integration tests",
                complexity=TaskComplexity.MODERATE,
                agent="test-engineer",
                skills=["integration-testing"],
                dependencies=[f"S{start_id + 1}"],
                estimated_minutes=45,
            ),
            PlanStep(
                id=f"S{start_id + 3}",
                title="Verify Coverage",
                description="Verify test coverage meets targets",
                complexity=TaskComplexity.SIMPLE,
                agent="qa-specialist",
                skills=["quality-assurance"],
                dependencies=[f"S{start_id + 2}"],
                estimated_minutes=15,
            ),
        ]

    def _generic_steps(self, start_id: int, task: str, agents: list[str]) -> list[PlanStep]:
        """Generate generic steps."""
        return [
            PlanStep(
                id=f"S{start_id}",
                title="Plan Implementation",
                description="Create detailed implementation plan",
                complexity=TaskComplexity.SIMPLE,
                agent="architect",
                skills=["architecture-patterns"],
                dependencies=["S1"],
                estimated_minutes=30,
            ),
            PlanStep(
                id=f"S{start_id + 1}",
                title="Implement Solution",
                description="Implement the planned solution",
                complexity=TaskComplexity.MODERATE,
                agent=agents[0] if agents else "backend-specialist",
                skills=[],
                dependencies=[f"S{start_id}"],
                estimated_minutes=60,
            ),
            PlanStep(
                id=f"S{start_id + 2}",
                title="Test Implementation",
                description="Test the implementation",
                complexity=TaskComplexity.SIMPLE,
                agent="test-engineer",
                skills=["testing-patterns"],
                dependencies=[f"S{start_id + 1}"],
                estimated_minutes=30,
            ),
        ]

    def _determine_execution_mode(self, steps: list[PlanStep]) -> ExecutionMode:
        """Determine the best execution mode."""
        parallel_groups = {s.parallel_group for s in steps if s.parallel_group is not None}

        if len(parallel_groups) > 1:
            return ExecutionMode.HYBRID
        elif len(parallel_groups) == 1:
            return ExecutionMode.PARALLEL
        return ExecutionMode.SEQUENTIAL

    def _identify_risks(self, task: str, task_type: str, steps: list[PlanStep]) -> list[str]:
        """Identify potential risks."""
        risks = []

        total_minutes = sum(s.estimated_minutes for s in steps)
        if total_minutes > 480:  # > 8 hours
            risks.append("Large scope - consider breaking into smaller tasks")

        complex_steps = [
            s for s in steps if s.complexity in [TaskComplexity.COMPLEX, TaskComplexity.EPIC]
        ]
        if complex_steps:
            risks.append(f"{len(complex_steps)} complex steps may need additional review")

        if task_type == "security":
            risks.append("Security changes require thorough testing before deployment")

        if task_type == "refactor":
            risks.append("Refactoring may introduce regressions - ensure test coverage")

        return risks

    def _generate_summary(self, task: str, task_type: str, steps: list[PlanStep]) -> str:
        """Generate plan summary."""
        total_minutes = sum(s.estimated_minutes for s in steps)
        agents = list({s.agent for s in steps})

        return (
            f"This {task_type} task requires {len(steps)} steps across {len(agents)} agents, "
            f"with an estimated completion time of {total_minutes} minutes. "
            f"The plan includes analysis, implementation, testing, and review phases."
        )


async def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Planner Agent")
    parser.add_argument("task", nargs="?", help="Task to plan")
    parser.add_argument("--context", "-c", help="Additional context")
    parser.add_argument("--json", action="store_true", help="JSON output")
    parser.add_argument("--markdown", "-m", action="store_true", help="Markdown output")

    args = parser.parse_args()

    if not args.task:
        args.task = "Create a new user authentication system with OAuth support"

    agent = PlannerAgent()
    plan = await agent.create_plan(args.task, args.context)

    if args.json:
        print(json.dumps(plan.to_dict(), indent=2))
    elif args.markdown:
        print(plan.to_markdown())
    else:
        print(plan.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
