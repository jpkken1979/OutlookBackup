#!/usr/bin/env python3
"""
Skill Architect Agent.

Dynamically composes skills into optimal pipelines for complex tasks.
"""

import asyncio
import json
import logging
import sys
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger("skill-architect")

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))


class PipelineType(Enum):
    """Pipeline execution types."""

    SEQUENTIAL = "sequential"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    ITERATIVE = "iterative"
    HYBRID = "hybrid"


@dataclass
class SkillRequirement:
    """A skill requirement."""

    skill_name: str
    purpose: str
    inputs: list[str]
    outputs: list[str]
    priority: int
    optional: bool = False


@dataclass
class PipelineNode:
    """A node in the skill pipeline."""

    node_id: str
    skill_name: str
    inputs: dict
    outputs: list[str]
    dependencies: list[str]
    parallel_group: int | None = None


@dataclass
class SkillPipeline:
    """A composed skill pipeline."""

    pipeline_id: str
    task: str
    pipeline_type: PipelineType
    nodes: list[PipelineNode]
    execution_order: list[list[str]]  # Grouped by parallel stages
    estimated_duration_ms: float
    confidence: float

    def to_dict(self) -> dict:
        return {
            "pipeline_id": self.pipeline_id,
            "task": self.task,
            "pipeline_type": self.pipeline_type.value,
            "nodes": [
                {
                    "node_id": n.node_id,
                    "skill_name": n.skill_name,
                    "inputs": n.inputs,
                    "outputs": n.outputs,
                    "dependencies": n.dependencies,
                    "parallel_group": n.parallel_group,
                }
                for n in self.nodes
            ],
            "execution_order": self.execution_order,
            "estimated_duration_ms": self.estimated_duration_ms,
            "confidence": self.confidence,
        }

    def export_diagram(self) -> str:
        """Export as ASCII diagram."""
        lines = [
            f"Pipeline: {self.task[:50]}",
            f"Type: {self.pipeline_type.value}",
            "",
            "Execution Flow:",
            "===============",
        ]

        for stage_idx, stage in enumerate(self.execution_order):
            if len(stage) == 1:
                lines.append(f"  Stage {stage_idx + 1}: [{stage[0]}]")
            else:
                parallel = " | ".join(f"[{s}]" for s in stage)
                lines.append(f"  Stage {stage_idx + 1}: {parallel} (parallel)")
            if stage_idx < len(self.execution_order) - 1:
                lines.append("         ↓")

        return "\n".join(lines)


class SkillArchitect:
    """
    Agent that composes skills into optimal pipelines.
    """

    def __init__(self):
        self.pipelines: list[SkillPipeline] = []
        self._available_skills = self._load_available_skills()

    def _load_available_skills(self) -> dict[str, dict]:
        """Load available skills metadata."""
        # In production, would scan .agent/skills/
        return {
            "code_analysis": {"inputs": ["code"], "outputs": ["analysis"]},
            "security_scan": {"inputs": ["code"], "outputs": ["vulnerabilities"]},
            "performance_profile": {"inputs": ["code"], "outputs": ["metrics"]},
            "test_generation": {"inputs": ["code", "analysis"], "outputs": ["tests"]},
            "documentation_gen": {"inputs": ["code", "analysis"], "outputs": ["docs"]},
            "refactoring": {"inputs": ["code", "analysis"], "outputs": ["refactored_code"]},
            "deployment": {"inputs": ["code", "tests"], "outputs": ["deployment"]},
            "api_design": {"inputs": ["requirements"], "outputs": ["api_spec"]},
            "database_design": {"inputs": ["requirements"], "outputs": ["schema"]},
            "ui_design": {"inputs": ["requirements"], "outputs": ["ui_spec"]},
            "validation": {"inputs": ["any"], "outputs": ["validation_result"]},
        }

    def _analyze_task(self, task: str) -> list[SkillRequirement]:
        """Analyze task to identify required skills."""
        task_lower = task.lower()
        requirements = []

        # Skill detection patterns
        skill_patterns = {
            "code_analysis": ["analyze", "review", "understand", "check"],
            "security_scan": ["security", "vulnerability", "audit", "owasp"],
            "performance_profile": ["performance", "optimize", "speed", "profile"],
            "test_generation": ["test", "spec", "coverage"],
            "documentation_gen": ["document", "readme", "docs"],
            "refactoring": ["refactor", "improve", "clean"],
            "deployment": ["deploy", "release", "publish"],
            "api_design": ["api", "endpoint", "rest", "graphql"],
            "database_design": ["database", "schema", "model"],
            "ui_design": ["ui", "interface", "design", "ux"],
            "validation": ["validate", "verify", "check"],
        }

        priority = 1
        for skill, patterns in skill_patterns.items():
            if any(p in task_lower for p in patterns):
                skill_meta = self._available_skills.get(skill, {})
                requirements.append(
                    SkillRequirement(
                        skill_name=skill,
                        purpose=f"Required for {patterns[0]}",
                        inputs=skill_meta.get("inputs", []),
                        outputs=skill_meta.get("outputs", []),
                        priority=priority,
                    )
                )
                priority += 1

        # Always include analysis for complex tasks
        if len(requirements) > 2 and not any(r.skill_name == "code_analysis" for r in requirements):
            requirements.insert(
                0,
                SkillRequirement(
                    skill_name="code_analysis",
                    purpose="Foundation analysis",
                    inputs=["code"],
                    outputs=["analysis"],
                    priority=0,
                ),
            )

        return requirements

    def _resolve_dependencies(self, requirements: list[SkillRequirement]) -> list[PipelineNode]:
        """Resolve skill dependencies and create nodes."""
        nodes = []
        output_map: dict[str, str] = {}  # output -> node_id

        for req in sorted(requirements, key=lambda r: r.priority):
            node_id = f"node_{req.skill_name}"

            # Find dependencies
            dependencies = []
            for input_name in req.inputs:
                if input_name in output_map:
                    dependencies.append(output_map[input_name])

            node = PipelineNode(
                node_id=node_id,
                skill_name=req.skill_name,
                inputs={i: output_map.get(i, "input") for i in req.inputs},
                outputs=req.outputs,
                dependencies=dependencies,
            )
            nodes.append(node)

            # Register outputs
            for output in req.outputs:
                output_map[output] = node_id

        return nodes

    def _determine_execution_order(self, nodes: list[PipelineNode]) -> list[list[str]]:
        """Determine parallel execution groups."""
        # Topological sort with parallel grouping
        executed = set()
        order = []

        while len(executed) < len(nodes):
            # Find nodes with all dependencies satisfied
            ready = []
            for node in nodes:
                if node.node_id in executed:
                    continue
                if all(dep in executed for dep in node.dependencies):
                    ready.append(node.node_id)

            if not ready:
                # Circular dependency - break it
                remaining = [n for n in nodes if n.node_id not in executed]
                ready = [remaining[0].node_id]

            order.append(ready)
            executed.update(ready)

        return order

    def _determine_pipeline_type(self, order: list[list[str]]) -> PipelineType:
        """Determine the pipeline type."""
        has_parallel = any(len(stage) > 1 for stage in order)
        if has_parallel:
            return PipelineType.HYBRID if len(order) > 3 else PipelineType.PARALLEL
        return PipelineType.SEQUENTIAL

    async def compose(self, task: str, constraints: dict | None = None) -> SkillPipeline:
        """
        Compose a skill pipeline for the task.

        Args:
            task: The complex task
            constraints: Optional constraints

        Returns:
            Composed pipeline
        """
        import hashlib

        # Analyze task
        requirements = self._analyze_task(task)
        logger.info(f"Identified {len(requirements)} skill requirements")

        # Resolve dependencies
        nodes = self._resolve_dependencies(requirements)

        # Determine execution order
        order = self._determine_execution_order(nodes)

        # Determine pipeline type
        pipeline_type = self._determine_pipeline_type(order)

        # Estimate duration
        estimated_duration = len(nodes) * 1000  # 1s per skill baseline

        # Calculate confidence
        confidence = min(0.9, 0.5 + (len(requirements) * 0.1))

        pipeline = SkillPipeline(
            pipeline_id=hashlib.sha256(task.encode()).hexdigest()[:16],
            task=task,
            pipeline_type=pipeline_type,
            nodes=nodes,
            execution_order=order,
            estimated_duration_ms=estimated_duration,
            confidence=confidence,
        )

        self.pipelines.append(pipeline)
        return pipeline


async def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Skill Architect Agent")
    parser.add_argument("task", nargs="?", help="Task to compose pipeline for")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if not args.task:
        parser.print_help()
        return

    architect = SkillArchitect()
    pipeline = await architect.compose(args.task)

    if args.json:
        print(json.dumps(pipeline.to_dict(), indent=2))
    else:
        print(pipeline.export_diagram())
        print(f"\nConfidence: {pipeline.confidence:.0%}")
        print(f"Estimated Duration: {pipeline.estimated_duration_ms:.0f}ms")


if __name__ == "__main__":
    asyncio.run(main())
