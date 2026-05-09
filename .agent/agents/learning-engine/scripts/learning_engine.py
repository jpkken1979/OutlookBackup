#!/usr/bin/env python3
"""
Learning Engine - Autonomous learning and evolution system.

This is the BRAIN that makes Antigravity agents smarter over time.

Features:
- Captures execution metadata from projects
- Extracts patterns from successes and failures
- Updates vector memory with new knowledge
- Generates new skills automatically
- Improves agent identities over time

Usage:
    python learning_engine.py "analyze last project"
    python learning_engine.py --extract-patterns
    python learning_engine.py --show-learnings
    python learning_engine.py --generate-skill "pattern_name"
"""

import argparse
import asyncio
import hashlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("learning_engine")

# Paths
BASE_DIR = Path(__file__).parent.parent.parent.parent.parent
AGENTS_DIR = BASE_DIR / ".agent" / "agents"
SKILLS_DIR = BASE_DIR / ".agent" / "skills"
MEMORY_DIR = Path(__file__).parent.parent / "memory"
MEMORY_DIR.mkdir(parents=True, exist_ok=True)


class PatternType(Enum):
    """Types of patterns that can be learned."""

    SUCCESS = "success"
    FAILURE = "failure"
    OPTIMIZATION = "optimization"
    SECURITY = "security"
    ARCHITECTURE = "architecture"
    TESTING = "testing"
    CODE_QUALITY = "code_quality"


class LearningSource(Enum):
    """Sources of learning."""

    PROJECT_EXECUTION = "project_execution"
    ERROR_ANALYSIS = "error_analysis"
    USER_FEEDBACK = "user_feedback"
    CODE_REVIEW = "code_review"
    PERFORMANCE_METRICS = "performance_metrics"
    SECURITY_AUDIT = "security_audit"


@dataclass
class Pattern:
    """A learned pattern."""

    id: str
    name: str
    pattern_type: PatternType
    description: str
    trigger_conditions: list[str]
    recommended_actions: list[str]
    evidence: list[str]
    confidence: float
    occurrence_count: int = 1
    last_observed: str = field(default_factory=lambda: datetime.now().isoformat())
    source: LearningSource = LearningSource.PROJECT_EXECUTION
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["pattern_type"] = self.pattern_type.value
        d["source"] = self.source.value
        return d

    @classmethod
    def from_dict(cls, data: dict) -> "Pattern":
        data["pattern_type"] = PatternType(data["pattern_type"])
        data["source"] = LearningSource(data["source"])
        return cls(**data)


@dataclass
class ExecutionMetadata:
    """Metadata captured from a project execution."""

    project_name: str
    task_description: str
    agents_used: list[str]
    success: bool
    duration_ms: int
    errors_encountered: list[str]
    solutions_applied: list[str]
    decisions_made: list[dict[str, str]]
    files_modified: list[str]
    technologies_used: list[str]
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Insight:
    """An insight derived from learning."""

    id: str
    title: str
    description: str
    impact: str  # high, medium, low
    applicable_to: list[str]  # agent names or domains
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class LearningEngine:
    """
    The Learning Engine - makes agents smarter over time.

    This is the meta-agent that:
    1. Observes what happens during executions
    2. Identifies patterns in successes and failures
    3. Extracts actionable insights
    4. Updates agent knowledge bases
    5. Generates new skills when patterns recur
    """

    def __init__(self):
        self.memory_dir = MEMORY_DIR
        self.patterns: dict[str, Pattern] = {}
        self.executions: list[ExecutionMetadata] = []
        self.insights: list[Insight] = []
        self._load_state()
        logger.info(f"LearningEngine initialized with {len(self.patterns)} patterns")

    def _load_state(self) -> None:
        """Load saved state from disk."""
        # Load patterns
        patterns_file = self.memory_dir / "patterns.json"
        if patterns_file.exists():
            try:
                with open(patterns_file) as f:
                    data = json.load(f)
                    for pid, pdata in data.items():
                        self.patterns[pid] = Pattern.from_dict(pdata)
            except Exception as e:
                logger.warning(f"Failed to load patterns: {e}")

        # Load executions
        executions_file = self.memory_dir / "executions.json"
        if executions_file.exists():
            try:
                with open(executions_file) as f:
                    data = json.load(f)
                    self.executions = [ExecutionMetadata(**e) for e in data]
            except Exception as e:
                logger.warning(f"Failed to load executions: {e}")

    def _save_state(self) -> None:
        """Save state to disk."""
        # Save patterns
        patterns_file = self.memory_dir / "patterns.json"
        with open(patterns_file, "w") as f:
            json.dump({pid: p.to_dict() for pid, p in self.patterns.items()}, f, indent=2)

        # Save executions
        executions_file = self.memory_dir / "executions.json"
        with open(executions_file, "w") as f:
            json.dump([e.to_dict() for e in self.executions[-100:]], f, indent=2)  # Keep last 100

        logger.info("State saved to disk")

    async def capture_execution(
        self,
        project_name: str,
        task_description: str,
        agents_used: list[str],
        success: bool,
        duration_ms: int,
        errors: list[str] | None = None,
        solutions: list[str] | None = None,
        decisions: list[dict[str, str]] | None = None,
        files: list[str] | None = None,
        technologies: list[str] | None = None,
    ) -> ExecutionMetadata:
        """
        Capture metadata from a project execution.

        This is called after each significant execution to feed the learning loop.
        """
        metadata = ExecutionMetadata(
            project_name=project_name,
            task_description=task_description,
            agents_used=agents_used,
            success=success,
            duration_ms=duration_ms,
            errors_encountered=errors or [],
            solutions_applied=solutions or [],
            decisions_made=decisions or [],
            files_modified=files or [],
            technologies_used=technologies or [],
        )

        self.executions.append(metadata)
        logger.info(f"Captured execution: {project_name} ({'success' if success else 'failure'})")

        # Trigger learning analysis
        await self._analyze_execution(metadata)

        self._save_state()
        return metadata

    async def _analyze_execution(self, execution: ExecutionMetadata) -> None:
        """Analyze an execution to extract patterns."""
        logger.info(f"Analyzing execution: {execution.task_description[:50]}...")

        # Extract patterns based on outcome
        if execution.success:
            await self._extract_success_patterns(execution)
        else:
            await self._extract_failure_patterns(execution)

        # Look for optimization opportunities
        await self._identify_optimizations(execution)

    async def _extract_success_patterns(self, execution: ExecutionMetadata) -> None:
        """Extract patterns from successful executions."""
        # Agent combination pattern
        if len(execution.agents_used) >= 2:
            agent_combo = sorted(execution.agents_used)
            combo_id = f"combo:{'-'.join(agent_combo)}"

            if combo_id in self.patterns:
                pattern = self.patterns[combo_id]
                pattern.occurrence_count += 1
                pattern.confidence = min(1.0, pattern.confidence + 0.05)
                pattern.last_observed = datetime.now().isoformat()
            else:
                pattern = Pattern(
                    id=combo_id,
                    name=f"Effective agent combination: {', '.join(agent_combo)}",
                    pattern_type=PatternType.SUCCESS,
                    description=f"These agents work well together for tasks like: {execution.task_description[:100]}",
                    trigger_conditions=[
                        f"Task involves: {', '.join(execution.technologies_used[:3])}"
                    ],
                    recommended_actions=[f"Use agents: {', '.join(agent_combo)}"],
                    evidence=[f"Success on: {execution.project_name}"],
                    confidence=0.6,
                )
                self.patterns[combo_id] = pattern

        # Technology + agent pattern
        for tech in execution.technologies_used:
            for agent in execution.agents_used:
                tech_agent_id = f"tech:{tech}-{agent}"
                if tech_agent_id not in self.patterns:
                    self.patterns[tech_agent_id] = Pattern(
                        id=tech_agent_id,
                        name=f"{agent} effective for {tech}",
                        pattern_type=PatternType.SUCCESS,
                        description=f"Agent {agent} successfully handled {tech} tasks",
                        trigger_conditions=[f"Task involves {tech}"],
                        recommended_actions=[f"Consider using {agent}"],
                        evidence=[execution.task_description[:100]],
                        confidence=0.5,
                    )
                else:
                    self.patterns[tech_agent_id].occurrence_count += 1
                    self.patterns[tech_agent_id].confidence = min(
                        1.0, self.patterns[tech_agent_id].confidence + 0.03
                    )

        # Decision pattern
        for decision in execution.decisions_made:
            decision_id = f"decision:{hashlib.md5(str(decision).encode(), usedforsecurity=False).hexdigest()[:8]}"
            if decision_id not in self.patterns:
                self.patterns[decision_id] = Pattern(
                    id=decision_id,
                    name=f"Good decision: {decision.get('choice', 'unknown')[:50]}",
                    pattern_type=PatternType.SUCCESS,
                    description=decision.get("rationale", "Decision led to success"),
                    trigger_conditions=[decision.get("context", "Similar context")],
                    recommended_actions=[decision.get("choice", "")],
                    evidence=[f"Project: {execution.project_name}"],
                    confidence=0.55,
                )

    async def _extract_failure_patterns(self, execution: ExecutionMetadata) -> None:
        """Extract patterns from failed executions."""
        for error in execution.errors_encountered:
            error_id = f"error:{hashlib.md5(error.encode(), usedforsecurity=False).hexdigest()[:8]}"

            if error_id in self.patterns:
                pattern = self.patterns[error_id]
                pattern.occurrence_count += 1
                pattern.confidence = min(1.0, pattern.confidence + 0.1)
                pattern.last_observed = datetime.now().isoformat()
            else:
                # Try to find corresponding solution
                solution = ""
                if execution.solutions_applied:
                    solution = execution.solutions_applied[0]

                pattern = Pattern(
                    id=error_id,
                    name=f"Known error: {error[:50]}",
                    pattern_type=PatternType.FAILURE,
                    description=f"Error encountered: {error}",
                    trigger_conditions=[
                        f"When working with: {', '.join(execution.technologies_used[:2])}"
                    ],
                    recommended_actions=[solution] if solution else ["Investigate root cause"],
                    evidence=[f"Occurred in: {execution.project_name}"],
                    confidence=0.7,
                    source=LearningSource.ERROR_ANALYSIS,
                )
                self.patterns[error_id] = pattern

    async def _identify_optimizations(self, execution: ExecutionMetadata) -> None:
        """Identify optimization opportunities."""
        # Duration optimization
        if execution.duration_ms > 30000:  # Over 30 seconds
            opt_id = f"opt:duration:{execution.project_name}"
            if opt_id not in self.patterns:
                self.patterns[opt_id] = Pattern(
                    id=opt_id,
                    name=f"Optimization opportunity: {execution.project_name}",
                    pattern_type=PatternType.OPTIMIZATION,
                    description=f"Execution took {execution.duration_ms}ms - may be optimizable",
                    trigger_conditions=["Similar task complexity"],
                    recommended_actions=[
                        "Consider parallel agent execution",
                        "Cache intermediate results",
                        "Review agent selection for efficiency",
                    ],
                    evidence=[f"Duration: {execution.duration_ms}ms"],
                    confidence=0.5,
                )

    async def extract_patterns(self) -> list[Pattern]:
        """
        Extract patterns from all recorded executions.

        This is the main learning loop that finds recurring patterns.
        """
        logger.info(f"Extracting patterns from {len(self.executions)} executions...")

        # Group executions by various dimensions
        by_technology: dict[str, list[ExecutionMetadata]] = {}
        by_agent: dict[str, list[ExecutionMetadata]] = {}
        by_outcome: dict[bool, list[ExecutionMetadata]] = {True: [], False: []}

        for exec_data in self.executions:
            by_outcome[exec_data.success].append(exec_data)

            for tech in exec_data.technologies_used:
                if tech not in by_technology:
                    by_technology[tech] = []
                by_technology[tech].append(exec_data)

            for agent in exec_data.agents_used:
                if agent not in by_agent:
                    by_agent[agent] = []
                by_agent[agent].append(exec_data)

        # Find technology success patterns
        for tech, execs in by_technology.items():
            success_rate = sum(1 for e in execs if e.success) / max(len(execs), 1)
            if success_rate > 0.8 and len(execs) >= 3:
                pattern_id = f"tech_success:{tech}"
                if pattern_id not in self.patterns:
                    # Find most common agents for this tech
                    agent_counts: dict[str, int] = {}
                    for e in execs:
                        for a in e.agents_used:
                            agent_counts[a] = agent_counts.get(a, 0) + 1
                    top_agents = sorted(agent_counts.items(), key=lambda x: x[1], reverse=True)[:3]

                    self.patterns[pattern_id] = Pattern(
                        id=pattern_id,
                        name=f"High success with {tech}",
                        pattern_type=PatternType.SUCCESS,
                        description=f"{success_rate:.0%} success rate with {tech} ({len(execs)} executions)",
                        trigger_conditions=[f"Task involves {tech}"],
                        recommended_actions=[f"Use agents: {', '.join(a for a, _ in top_agents)}"],
                        evidence=[f"Based on {len(execs)} executions"],
                        confidence=success_rate,
                    )

        # Find agent effectiveness patterns
        for agent, execs in by_agent.items():
            success_rate = sum(1 for e in execs if e.success) / max(len(execs), 1)
            if len(execs) >= 5:
                pattern_id = f"agent_eff:{agent}"
                self.patterns[pattern_id] = Pattern(
                    id=pattern_id,
                    name=f"Agent effectiveness: {agent}",
                    pattern_type=PatternType.SUCCESS
                    if success_rate > 0.7
                    else PatternType.OPTIMIZATION,
                    description=f"{agent} has {success_rate:.0%} success rate",
                    trigger_conditions=["When selecting agents"],
                    recommended_actions=[
                        f"{'Prefer' if success_rate > 0.7 else 'Review usage of'} {agent}"
                    ],
                    evidence=[f"Based on {len(execs)} executions"],
                    confidence=min(success_rate + 0.1, 1.0),
                )

        self._save_state()
        return list(self.patterns.values())

    async def generate_skill(self, pattern_name: str) -> dict[str, Any] | None:
        """
        Generate a new skill from a learned pattern.

        When a pattern recurs enough, we can codify it as a reusable skill.
        """
        # Find matching pattern
        matching = [p for p in self.patterns.values() if pattern_name.lower() in p.name.lower()]

        if not matching:
            logger.warning(f"No pattern found matching: {pattern_name}")
            return None

        pattern = matching[0]

        if pattern.occurrence_count < 3 or pattern.confidence < 0.6:
            logger.info(
                f"Pattern not mature enough: {pattern.occurrence_count} occurrences, {pattern.confidence:.0%} confidence"
            )
            return None

        # Generate skill structure
        skill_name = re.sub(r"[^a-z0-9-]", "-", pattern.name.lower())[:50]
        skill_dir = SKILLS_DIR / f"learned-{skill_name}"
        skill_dir.mkdir(parents=True, exist_ok=True)

        skill_md = f"""---
name: learned-{skill_name}
description: Auto-generated skill from learning engine. {pattern.description[:100]}
allowed-tools: Read, Glob, Grep, Bash
auto-generated: true
confidence: {pattern.confidence}
---

# {pattern.name}

> Auto-generated by Learning Engine from {pattern.occurrence_count} observations.

## Description

{pattern.description}

## When to Apply

This skill is applicable when:
{chr(10).join(f"- {cond}" for cond in pattern.trigger_conditions)}

## Recommended Actions

{chr(10).join(f"{i + 1}. {action}" for i, action in enumerate(pattern.recommended_actions))}

## Evidence

Based on:
{chr(10).join(f"- {ev}" for ev in pattern.evidence)}

## Confidence Level

**Confidence:** {pattern.confidence:.0%}
**Observations:** {pattern.occurrence_count}
**Last Observed:** {pattern.last_observed}

---

*This skill was automatically generated by the Learning Engine on {datetime.now().isoformat()}*
"""

        skill_file = skill_dir / "SKILL.md"
        with open(skill_file, "w") as f:
            f.write(skill_md)

        logger.info(f"Generated skill: {skill_dir}")

        return {
            "skill_name": f"learned-{skill_name}",
            "skill_dir": str(skill_dir),
            "pattern": pattern.to_dict(),
        }

    async def get_recommendations(
        self, task: str, technologies: list[str] | None = None
    ) -> dict[str, Any]:
        """
        Get recommendations based on learned patterns.

        Given a task description, suggest agents and approaches based on learning.
        """
        recommendations = {
            "agents": [],
            "approaches": [],
            "warnings": [],
            "relevant_patterns": [],
        }

        task_lower = task.lower()
        technologies = technologies or []

        # Find relevant patterns
        for pattern in self.patterns.values():
            relevance = 0.0

            # Check trigger conditions
            for condition in pattern.trigger_conditions:
                if any(word in task_lower for word in condition.lower().split()):
                    relevance += 0.3

            # Check technology match
            for tech in technologies:
                if (
                    tech.lower() in pattern.name.lower()
                    or tech.lower() in pattern.description.lower()
                ):
                    relevance += 0.4

            if relevance > 0.2:
                recommendations["relevant_patterns"].append(
                    {
                        "pattern": pattern.name,
                        "confidence": pattern.confidence,
                        "relevance": relevance,
                        "actions": pattern.recommended_actions,
                    }
                )

                # Extract agent recommendations
                for action in pattern.recommended_actions:
                    if "agent" in action.lower():
                        recommendations["agents"].append(action)

                # Add warnings for failure patterns
                if pattern.pattern_type == PatternType.FAILURE:
                    recommendations["warnings"].append(pattern.description)

        # Sort by relevance
        recommendations["relevant_patterns"].sort(key=lambda x: x["relevance"], reverse=True)

        return recommendations

    def show_learnings(self) -> str:
        """Display current learnings in human-readable format."""
        lines = [
            "# Learning Engine Status",
            "",
            f"**Total Patterns:** {len(self.patterns)}",
            f"**Total Executions:** {len(self.executions)}",
            "",
            "## Pattern Summary",
            "",
        ]

        # Group by type
        by_type: dict[PatternType, list[Pattern]] = {}
        for pattern in self.patterns.values():
            if pattern.pattern_type not in by_type:
                by_type[pattern.pattern_type] = []
            by_type[pattern.pattern_type].append(pattern)

        for ptype, patterns in by_type.items():
            lines.append(f"### {ptype.value.upper()} ({len(patterns)})")
            lines.append("")

            # Sort by confidence
            for p in sorted(patterns, key=lambda x: x.confidence, reverse=True)[:5]:
                lines.append(
                    f"- **{p.name}** ({p.confidence:.0%} confidence, {p.occurrence_count} occurrences)"
                )
                lines.append(f"  - {p.description[:100]}")

            lines.append("")

        # Recent executions
        lines.extend(
            [
                "## Recent Executions",
                "",
            ]
        )

        for exec_data in self.executions[-5:]:
            status = "SUCCESS" if exec_data.success else "FAILURE"
            lines.append(
                f"- [{status}] {exec_data.project_name}: {exec_data.task_description[:50]}..."
            )
            lines.append(f"  Agents: {', '.join(exec_data.agents_used)}")

        return "\n".join(lines)

    async def run(self, task: str) -> str:
        """Main entry point for running the learning engine."""
        logger.info(f"Learning Engine processing: {task}")

        if task == "--extract-patterns" or "extract" in task.lower():
            patterns = await self.extract_patterns()
            return f"Extracted {len(patterns)} patterns. Use --show-learnings to view."

        elif task == "--show-learnings" or "show" in task.lower():
            return self.show_learnings()

        elif task.startswith("--generate-skill"):
            pattern_name = task.replace("--generate-skill", "").strip()
            result = await self.generate_skill(pattern_name)
            if result:
                return f"Generated skill: {result['skill_name']}"
            return "No mature pattern found to generate skill"

        elif task.startswith("--recommend"):
            query = task.replace("--recommend", "").strip()
            recs = await self.get_recommendations(query)
            return json.dumps(recs, indent=2)

        else:
            # Default: analyze and provide status
            await self.extract_patterns()
            return self.show_learnings()


async def main():
    parser = argparse.ArgumentParser(
        description="Learning Engine - Autonomous learning for Antigravity"
    )
    parser.add_argument("task", nargs="?", default="--show-learnings", help="Task or command")
    parser.add_argument(
        "--extract-patterns", action="store_true", help="Extract patterns from executions"
    )
    parser.add_argument("--show-learnings", action="store_true", help="Show current learnings")
    parser.add_argument("--generate-skill", type=str, help="Generate skill from pattern")
    parser.add_argument("--recommend", type=str, help="Get recommendations for a task")
    parser.add_argument("--json", action="store_true", help="Output in JSON format")

    args = parser.parse_args()

    engine = LearningEngine()

    # Handle flag-based commands
    if args.extract_patterns:
        task = "--extract-patterns"
    elif args.show_learnings:
        task = "--show-learnings"
    elif args.generate_skill:
        task = f"--generate-skill {args.generate_skill}"
    elif args.recommend:
        task = f"--recommend {args.recommend}"
    else:
        task = args.task

    result = await engine.run(task)

    if args.json:
        try:
            # Try to parse as JSON for pretty printing
            data = json.loads(result)
            print(json.dumps(data, indent=2))
        except json.JSONDecodeError:
            print(json.dumps({"result": result}))
    else:
        print(result)


if __name__ == "__main__":
    asyncio.run(main())
