#!/usr/bin/env python3
"""
Skill Composition - Dynamically combines skills for complex tasks.

This module provides skill composition that:
1. Analyzes task requirements
2. Identifies relevant skills
3. Composes skill pipelines
4. Orchestrates skill execution
5. Handles skill dependencies

Usage:
    from .agent.core.intelligence import SkillComposer, compose_skills

    composer = SkillComposer()

    # Compose skills for a task
    pipeline = await composer.compose(
        task="Create a REST API with authentication and tests",
        available_skills=["api-design", "auth-implementation", "test-generation"]
    )

    result = await composer.execute(pipeline)
"""

import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.skill_composition")


class CompositionType(Enum):
    """Types of skill composition."""

    SEQUENTIAL = "sequential"  # Skills run one after another
    PARALLEL = "parallel"  # Skills run simultaneously
    CONDITIONAL = "conditional"  # Skills run based on conditions
    ITERATIVE = "iterative"  # Skills repeat until condition met
    BRANCHING = "branching"  # Fork based on output


class SkillDependency(Enum):
    """Types of skill dependencies."""

    REQUIRED = "required"  # Must have output from this skill
    OPTIONAL = "optional"  # Can use if available
    BLOCKING = "blocking"  # Must wait for completion


@dataclass
class SkillInfo:
    """Information about a skill."""

    name: str
    description: str
    inputs: list[str]
    outputs: list[str]
    tags: list[str]
    estimated_time_ms: int = 1000
    dependencies: list[str] = field(default_factory=list)
    compatible_with: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputs": self.inputs,
            "outputs": self.outputs,
            "tags": self.tags,
            "estimated_time_ms": self.estimated_time_ms,
            "dependencies": self.dependencies,
        }


@dataclass
class CompositionNode:
    """A node in a skill composition pipeline."""

    skill: SkillInfo
    composition_type: CompositionType
    inputs_from: dict[str, str] = field(default_factory=dict)  # param -> source
    condition: str | None = None
    children: list["CompositionNode"] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill": self.skill.name,
            "type": self.composition_type.value,
            "inputs_from": self.inputs_from,
            "condition": self.condition,
            "children": [c.to_dict() for c in self.children],
        }


@dataclass
class ComposedPipeline:
    """A composed skill pipeline."""

    pipeline_id: str
    task: str
    root_nodes: list[CompositionNode]
    skills_used: list[str]
    estimated_time_ms: int
    parallel_paths: int
    dependencies_resolved: bool
    warnings: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pipeline_id": self.pipeline_id,
            "task": self.task,
            "root_nodes": [n.to_dict() for n in self.root_nodes],
            "skills_used": self.skills_used,
            "estimated_time_ms": self.estimated_time_ms,
            "parallel_paths": self.parallel_paths,
            "dependencies_resolved": self.dependencies_resolved,
            "warnings": self.warnings,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class ExecutionResult:
    """Result of pipeline execution."""

    success: bool
    outputs: dict[str, Any]
    skills_executed: list[str]
    execution_time_ms: int
    errors: list[str]
    skill_results: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "skills_executed": self.skills_executed,
            "execution_time_ms": self.execution_time_ms,
            "errors": self.errors,
        }


class SkillMatcher:
    """Matches tasks to relevant skills."""

    def match_skills(
        self,
        task: str,
        available_skills: list[SkillInfo],
    ) -> list[SkillInfo]:
        """
        Find skills relevant to a task.

        Args:
            task: Task description
            available_skills: Available skills

        Returns:
            List of matching skills
        """
        task_lower = task.lower()
        task_words = set(task_lower.split())

        scored_skills = []

        for skill in available_skills:
            score = 0.0

            # Match by tags
            for tag in skill.tags:
                if tag.lower() in task_lower:
                    score += 0.3

            # Match by description
            desc_words = set(skill.description.lower().split())
            overlap = len(task_words & desc_words)
            score += overlap * 0.1

            # Match by name
            if skill.name.lower() in task_lower:
                score += 0.5
            elif any(part in task_lower for part in skill.name.lower().split("-")):
                score += 0.3

            # Match by outputs (what the task might need)
            for output in skill.outputs:
                if output.lower() in task_lower:
                    score += 0.2

            if score > 0:
                scored_skills.append((skill, score))

        # Sort by score
        scored_skills.sort(key=lambda x: x[1], reverse=True)

        return [skill for skill, score in scored_skills]


class DependencyResolver:
    """Resolves skill dependencies."""

    def resolve(
        self,
        skills: list[SkillInfo],
    ) -> list[list[SkillInfo]]:
        """
        Resolve dependencies and create execution order.

        Args:
            skills: Skills to order

        Returns:
            List of skill tiers (can run in parallel within tier)
        """
        # Build dependency graph
        skill_map = {s.name: s for s in skills}
        in_degree = {s.name: 0 for s in skills}
        dependents: dict[str, list[str]] = {s.name: [] for s in skills}

        for skill in skills:
            for dep in skill.dependencies:
                if dep in skill_map:
                    in_degree[skill.name] += 1
                    dependents[dep].append(skill.name)

        # Topological sort with tiers
        tiers = []
        remaining = {s.name for s in skills}

        while remaining:
            # Find skills with no unresolved dependencies
            tier = [name for name in remaining if in_degree[name] == 0]

            if not tier:
                # Circular dependency - break by taking any
                tier = [next(iter(remaining))]
                logger.warning(f"Circular dependency detected, breaking at {tier[0]}")

            tiers.append([skill_map[name] for name in tier])

            # Update degrees
            for name in tier:
                remaining.remove(name)
                for dependent in dependents[name]:
                    if dependent in in_degree:
                        in_degree[dependent] -= 1

        return tiers


class PipelineBuilder:
    """Builds composition pipelines."""

    def build(
        self,
        skills_tiers: list[list[SkillInfo]],
        task: str,
    ) -> list[CompositionNode]:
        """
        Build pipeline from skill tiers.

        Args:
            skills_tiers: Ordered skill tiers
            task: Original task

        Returns:
            List of root nodes
        """
        root_nodes = []
        previous_tier_outputs: dict[str, str] = {}  # output -> skill_name

        for tier_idx, tier in enumerate(skills_tiers):
            tier_idx == len(skills_tiers) - 1

            if len(tier) == 1:
                # Sequential
                skill = tier[0]
                node = self._create_node(
                    skill,
                    CompositionType.SEQUENTIAL,
                    previous_tier_outputs,
                )
                root_nodes.append(node)

                # Update outputs
                for output in skill.outputs:
                    previous_tier_outputs[output] = skill.name

            else:
                # Parallel tier
                parallel_nodes = []
                for skill in tier:
                    node = self._create_node(
                        skill,
                        CompositionType.PARALLEL,
                        previous_tier_outputs,
                    )
                    parallel_nodes.append(node)

                    # Update outputs
                    for output in skill.outputs:
                        previous_tier_outputs[output] = skill.name

                root_nodes.extend(parallel_nodes)

        return root_nodes

    def _create_node(
        self,
        skill: SkillInfo,
        composition_type: CompositionType,
        available_inputs: dict[str, str],
    ) -> CompositionNode:
        """Create a composition node."""
        # Map required inputs to sources
        inputs_from = {}
        for req_input in skill.inputs:
            if req_input in available_inputs:
                inputs_from[req_input] = available_inputs[req_input]

        return CompositionNode(
            skill=skill,
            composition_type=composition_type,
            inputs_from=inputs_from,
        )


class SkillComposer:
    """
    Composes skills dynamically for complex tasks.

    This class:
    1. Analyzes task requirements
    2. Matches relevant skills
    3. Resolves dependencies
    4. Builds execution pipelines
    """

    def __init__(self, memory_dir: Path | None = None, skills_dir: Path | None = None):
        self.memory_dir = memory_dir or Path(".agent/memory/composition")
        self.skills_dir = skills_dir or Path(".agent/skills")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.matcher = SkillMatcher()
        self.resolver = DependencyResolver()
        self.builder = PipelineBuilder()

        # Skill registry
        self.skill_registry: dict[str, SkillInfo] = {}
        self._load_skill_registry()

        # Execution history
        self.execution_history: list[ExecutionResult] = []

    def _load_skill_registry(self) -> None:
        """Load skills from registry or disk."""
        # Populate with some common skills
        common_skills = [
            SkillInfo(
                name="api-design",
                description="Design REST API endpoints and schemas",
                inputs=["requirements"],
                outputs=["api-spec", "endpoints"],
                tags=["api", "rest", "design"],
                estimated_time_ms=5000,
            ),
            SkillInfo(
                name="auth-implementation",
                description="Implement authentication and authorization",
                inputs=["api-spec"],
                outputs=["auth-code", "tokens"],
                tags=["auth", "security", "jwt"],
                estimated_time_ms=8000,
                dependencies=["api-design"],
            ),
            SkillInfo(
                name="test-generation",
                description="Generate tests for code",
                inputs=["code", "api-spec"],
                outputs=["tests"],
                tags=["testing", "unit-test", "integration"],
                estimated_time_ms=4000,
                dependencies=["api-design"],
            ),
            SkillInfo(
                name="database-schema",
                description="Design database schema",
                inputs=["requirements", "api-spec"],
                outputs=["schema", "migrations"],
                tags=["database", "sql", "schema"],
                estimated_time_ms=6000,
            ),
            SkillInfo(
                name="documentation",
                description="Generate documentation",
                inputs=["api-spec", "code"],
                outputs=["docs", "readme"],
                tags=["docs", "readme", "api-docs"],
                estimated_time_ms=3000,
                dependencies=["api-design"],
            ),
            SkillInfo(
                name="frontend-component",
                description="Create frontend UI components",
                inputs=["design", "api-spec"],
                outputs=["component", "styles"],
                tags=["frontend", "react", "ui"],
                estimated_time_ms=7000,
            ),
            SkillInfo(
                name="validation",
                description="Add input validation",
                inputs=["api-spec", "code"],
                outputs=["validated-code"],
                tags=["validation", "security", "input"],
                estimated_time_ms=3000,
                dependencies=["api-design"],
            ),
            SkillInfo(
                name="error-handling",
                description="Implement error handling",
                inputs=["code"],
                outputs=["robust-code"],
                tags=["errors", "exceptions", "handling"],
                estimated_time_ms=2000,
            ),
        ]

        for skill in common_skills:
            self.skill_registry[skill.name] = skill

        # Try to load from disk
        if self.skills_dir.exists():
            for skill_dir in self.skills_dir.iterdir():
                if skill_dir.is_dir():
                    skill_md = skill_dir / "SKILL.md"
                    if skill_md.exists():
                        # Parse SKILL.md (simplified)
                        try:
                            skill_md.read_text(encoding="utf-8")
                            name = skill_dir.name
                            if name not in self.skill_registry:
                                self.skill_registry[name] = SkillInfo(
                                    name=name,
                                    description=f"Skill from {name}",
                                    inputs=[],
                                    outputs=[],
                                    tags=[name],
                                )
                        except Exception:
                            pass

    def register_skill(self, skill: SkillInfo) -> None:
        """Register a skill."""
        self.skill_registry[skill.name] = skill

    async def compose(
        self,
        task: str,
        available_skills: list[str] | None = None,
        context: dict[str, Any] | None = None,
    ) -> ComposedPipeline:
        """
        Compose a skill pipeline for a task.

        Args:
            task: Task description
            available_skills: Limit to these skills (all if None)
            context: Additional context

        Returns:
            ComposedPipeline
        """
        context = context or {}

        # Get available skills
        if available_skills:
            skills = [
                self.skill_registry[name]
                for name in available_skills
                if name in self.skill_registry
            ]
        else:
            skills = list(self.skill_registry.values())

        # Match skills to task
        matched_skills = self.matcher.match_skills(task, skills)

        if not matched_skills:
            return ComposedPipeline(
                pipeline_id=self._generate_id(),
                task=task,
                root_nodes=[],
                skills_used=[],
                estimated_time_ms=0,
                parallel_paths=0,
                dependencies_resolved=True,
                warnings=["No matching skills found"],
            )

        # Resolve dependencies
        skill_tiers = self.resolver.resolve(matched_skills)

        # Build pipeline
        root_nodes = self.builder.build(skill_tiers, task)

        # Calculate estimates
        estimated_time = sum(s.estimated_time_ms for s in matched_skills)
        parallel_paths = max(len(tier) for tier in skill_tiers) if skill_tiers else 0

        # Check for warnings
        warnings = self._check_warnings(matched_skills, task)

        pipeline = ComposedPipeline(
            pipeline_id=self._generate_id(),
            task=task,
            root_nodes=root_nodes,
            skills_used=[s.name for s in matched_skills],
            estimated_time_ms=estimated_time,
            parallel_paths=parallel_paths,
            dependencies_resolved=True,
            warnings=warnings,
        )

        logger.info(
            f"Composed pipeline: {len(matched_skills)} skills, "
            f"{len(skill_tiers)} tiers, {parallel_paths} parallel paths"
        )

        return pipeline

    async def execute(
        self,
        pipeline: ComposedPipeline,
        inputs: dict[str, Any] | None = None,
        executor: Callable | None = None,
    ) -> ExecutionResult:
        """
        Execute a composed pipeline.

        Args:
            pipeline: Pipeline to execute
            inputs: Initial inputs
            executor: Skill execution function

        Returns:
            ExecutionResult
        """
        import time

        start_time = time.time()

        inputs = inputs or {}
        outputs: dict[str, Any] = dict(inputs)
        skills_executed = []
        errors = []
        skill_results: dict[str, Any] = {}

        try:
            for node in pipeline.root_nodes:
                result = await self._execute_node(
                    node,
                    outputs,
                    executor,
                )

                if result.get("success"):
                    skills_executed.append(node.skill.name)
                    outputs.update(result.get("outputs", {}))
                    skill_results[node.skill.name] = result
                else:
                    errors.append(f"{node.skill.name}: {result.get('error', 'Unknown error')}")

        except Exception as e:
            errors.append(f"Pipeline error: {str(e)}")

        elapsed_ms = int((time.time() - start_time) * 1000)

        result = ExecutionResult(  # type: ignore[assignment]  # dataclass fields match, mypy confused by overload
            success=len(errors) == 0,
            outputs=outputs,
            skills_executed=skills_executed,
            execution_time_ms=elapsed_ms,
            errors=errors,
            skill_results=skill_results,
        )

        self.execution_history.append(result)  # type: ignore[arg-type]  # ExecutionResult variant
        return result  # type: ignore[return-value]  # ExecutionResult variant

    async def _execute_node(
        self,
        node: CompositionNode,
        context: dict[str, Any],
        executor: Callable | None,
    ) -> dict[str, Any]:
        """Execute a single pipeline node."""
        # Gather inputs
        node_inputs = {}
        for param, source in node.inputs_from.items():
            if source in context:
                node_inputs[param] = context[source]

        # Execute skill
        if executor:
            try:
                result = await executor(node.skill.name, node_inputs)
                return {"success": True, "outputs": result}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            # Simulate execution
            return {
                "success": True,
                "outputs": {
                    output: f"[{node.skill.name} output: {output}]" for output in node.skill.outputs
                },
            }

    def _check_warnings(
        self,
        skills: list[SkillInfo],
        task: str,
    ) -> list[str]:
        """Check for potential issues."""
        warnings = []

        # Check for missing dependencies
        skill_names = {s.name for s in skills}
        for skill in skills:
            for dep in skill.dependencies:
                if dep not in skill_names:
                    warnings.append(
                        f"Skill '{skill.name}' depends on '{dep}' which is not included"
                    )

        # Check for long execution time
        total_time = sum(s.estimated_time_ms for s in skills)
        if total_time > 60000:
            warnings.append(f"Estimated execution time is {total_time / 1000:.0f}s")

        return warnings

    def _generate_id(self) -> str:
        """Generate pipeline ID."""
        return f"pipeline_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

    def get_available_skills(self) -> list[SkillInfo]:
        """Get all available skills."""
        return list(self.skill_registry.values())

    def export_report(self) -> str:
        """Export composition report as markdown."""
        lines = [
            "# Skill Composition Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            f"**Registered skills:** {len(self.skill_registry)}",
            f"**Executions:** {len(self.execution_history)}",
            "",
            "## Available Skills",
            "",
        ]

        for skill in self.skill_registry.values():
            lines.append(f"- **{skill.name}**: {skill.description}")
            lines.append(f"  - Tags: {', '.join(skill.tags)}")
            if skill.dependencies:
                lines.append(f"  - Depends on: {', '.join(skill.dependencies)}")

        return "\n".join(lines)


# Convenience function
async def compose_skills(
    task: str,
    skills: list[str] | None = None,
) -> ComposedPipeline:
    """Quick function to compose skills."""
    composer = SkillComposer()
    return await composer.compose(task, skills)
