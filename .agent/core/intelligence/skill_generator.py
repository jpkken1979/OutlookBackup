# mypy: ignore-errors
#!/usr/bin/env python3
"""
Autonomous Skill Generator - Auto-generates skills from successful patterns.

This module automatically:
1. Monitors execution patterns across agents
2. Identifies successful, repeatable patterns
3. Generates reusable skills from patterns
4. Validates and tests generated skills
5. Integrates skills into the ecosystem

Usage:
    from .agent.core.intelligence import SkillGenerator, auto_generate_skill

    generator = SkillGenerator()

    # Generate skill from a pattern
    skill = await generator.generate_from_pattern(
        pattern_name="api-crud-generator",
        examples=[execution1, execution2, execution3],
        domain="backend"
    )

    # Auto-discover and generate skills
    skills = await generator.discover_and_generate()
"""

import hashlib
import json
import logging
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.skill_generator")


class SkillComplexity(Enum):
    """Complexity levels for skills."""

    SIMPLE = "simple"  # Single action
    MODERATE = "moderate"  # 2-5 steps
    COMPLEX = "complex"  # 5-10 steps
    ADVANCED = "advanced"  # 10+ steps or multi-agent


class SkillDomain(Enum):
    """Domains for skills."""

    FRONTEND = "frontend"
    BACKEND = "backend"
    DATABASE = "database"
    DEVOPS = "devops"
    TESTING = "testing"
    SECURITY = "security"
    DOCUMENTATION = "documentation"
    REFACTORING = "refactoring"
    ANALYSIS = "analysis"
    GENERAL = "general"


@dataclass
class ExecutionPattern:
    """A pattern extracted from executions."""

    pattern_id: str
    name: str
    description: str
    domain: SkillDomain
    steps: list[dict[str, Any]]
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    success_count: int
    total_count: int
    agents_involved: list[str]
    avg_execution_time_ms: float
    confidence: float
    first_seen: datetime
    last_seen: datetime
    examples: list[dict[str, Any]] = field(default_factory=list)

    @property
    def success_rate(self) -> float:
        return self.success_count / max(self.total_count, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain.value,
            "steps": self.steps,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "success_count": self.success_count,
            "total_count": self.total_count,
            "success_rate": self.success_rate,
            "agents_involved": self.agents_involved,
            "avg_execution_time_ms": self.avg_execution_time_ms,
            "confidence": self.confidence,
            "first_seen": self.first_seen.isoformat(),
            "last_seen": self.last_seen.isoformat(),
        }


@dataclass
class GeneratedSkill:
    """A skill generated from patterns."""

    skill_id: str
    name: str
    description: str
    domain: SkillDomain
    complexity: SkillComplexity
    source_pattern: str
    skill_md_content: str
    script_content: str
    test_content: str
    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    dependencies: list[str]
    estimated_time_ms: float
    confidence: float
    created_at: datetime = field(default_factory=datetime.now)
    validated: bool = False
    deployed: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "skill_id": self.skill_id,
            "name": self.name,
            "description": self.description,
            "domain": self.domain.value,
            "complexity": self.complexity.value,
            "source_pattern": self.source_pattern,
            "input_schema": self.input_schema,
            "output_schema": self.output_schema,
            "dependencies": self.dependencies,
            "estimated_time_ms": self.estimated_time_ms,
            "confidence": self.confidence,
            "created_at": self.created_at.isoformat(),
            "validated": self.validated,
            "deployed": self.deployed,
        }


@dataclass
class GenerationResult:
    """Result of skill generation."""

    success: bool
    skill: GeneratedSkill | None
    pattern_used: ExecutionPattern | None
    validation_passed: bool
    validation_errors: list[str]
    suggestions: list[str]


class PatternExtractor:
    """Extracts patterns from execution history."""

    def __init__(self, min_occurrences: int = 3, min_success_rate: float = 0.8):
        self.min_occurrences = min_occurrences
        self.min_success_rate = min_success_rate

    def extract_patterns(
        self,
        executions: list[dict[str, Any]],
    ) -> list[ExecutionPattern]:
        """Extract patterns from a list of executions."""
        # Group executions by similarity
        pattern_groups: dict[str, list[dict[str, Any]]] = {}

        for execution in executions:
            # Create pattern signature
            signature = self._create_signature(execution)
            if signature not in pattern_groups:
                pattern_groups[signature] = []
            pattern_groups[signature].append(execution)

        # Convert groups to patterns
        patterns = []
        for signature, group in pattern_groups.items():
            if len(group) >= self.min_occurrences:
                pattern = self._group_to_pattern(signature, group)
                if pattern.success_rate >= self.min_success_rate:
                    patterns.append(pattern)

        return sorted(patterns, key=lambda p: p.confidence, reverse=True)

    def _create_signature(self, execution: dict[str, Any]) -> str:
        """Create a signature for grouping similar executions."""
        # Extract key elements
        task_type = execution.get("task_type", "unknown")
        agents = tuple(sorted(execution.get("agents", [])))
        steps = tuple(step.get("type", "") for step in execution.get("steps", []))

        # Hash them
        signature_data = f"{task_type}:{agents}:{steps}"
        return hashlib.md5(signature_data.encode(), usedforsecurity=False).hexdigest()[:12]

    def _group_to_pattern(
        self,
        signature: str,
        executions: list[dict[str, Any]],
    ) -> ExecutionPattern:
        """Convert a group of similar executions to a pattern."""
        # Aggregate data
        success_count = sum(1 for e in executions if e.get("success", False))
        total_count = len(executions)

        # Get common elements
        first_exec = executions[0]
        agents = list({agent for e in executions for agent in e.get("agents", [])})

        # Extract steps template
        steps = self._extract_step_template(executions)

        # Extract schemas
        input_schema = self._extract_input_schema(executions)
        output_schema = self._extract_output_schema(executions)

        # Calculate avg time
        times = [e.get("duration_ms", 0) for e in executions if e.get("duration_ms")]
        avg_time = sum(times) / len(times) if times else 0

        # Determine domain
        domain = self._detect_domain(first_exec, steps)

        # Generate name from task
        name = self._generate_pattern_name(first_exec.get("task", ""), domain)

        # Calculate confidence
        confidence = self._calculate_pattern_confidence(
            success_count, total_count, len(steps), len(agents)
        )

        dates = [
            datetime.fromisoformat(e.get("timestamp", datetime.now().isoformat()))
            for e in executions
            if e.get("timestamp")
        ]

        return ExecutionPattern(
            pattern_id=signature,
            name=name,
            description=f"Pattern extracted from {total_count} executions with {success_count / total_count:.0%} success rate",
            domain=domain,
            steps=steps,
            input_schema=input_schema,
            output_schema=output_schema,
            success_count=success_count,
            total_count=total_count,
            agents_involved=agents,
            avg_execution_time_ms=avg_time,
            confidence=confidence,
            first_seen=min(dates) if dates else datetime.now(),
            last_seen=max(dates) if dates else datetime.now(),
            examples=executions[:3],  # Keep first 3 as examples
        )

    def _extract_step_template(
        self,
        executions: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """Extract a step template from executions."""
        if not executions:
            return []

        # Use first execution as base
        base_steps = executions[0].get("steps", [])

        # Generalize steps
        template = []
        for step in base_steps:
            generalized = {
                "type": step.get("type", "action"),
                "action": step.get("action", "unknown"),
                "description": step.get("description", ""),
                "agent": step.get("agent"),
                "parameters": self._generalize_parameters(step.get("parameters", {})),
            }
            template.append(generalized)

        return template

    def _generalize_parameters(
        self,
        base_params: dict[str, Any],
        comparison_params: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Generalize parameters by finding common structure.

        Args:
            base_params: Base parameter set to inspect.
            comparison_params: Reserved for backward compatibility with older
                call sites/tests that pass additional execution parameter sets.
                Currently unused.
        """
        _ = comparison_params
        generalized = {}

        for key, value in base_params.items():
            if isinstance(value, str):
                # Check if it's a variable (different across executions)
                generalized[key] = {"type": "string", "example": value}
            elif isinstance(value, int):
                generalized[key] = {"type": "integer", "example": value}
            elif isinstance(value, bool):
                generalized[key] = {"type": "boolean", "example": value}
            elif isinstance(value, list):
                generalized[key] = {"type": "array", "example": value}
            elif isinstance(value, dict):
                generalized[key] = {"type": "object", "example": value}
            else:
                generalized[key] = {"type": "any", "example": str(value)}

        return generalized

    def _extract_input_schema(
        self,
        executions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract input schema from executions."""
        schema = {
            "type": "object",
            "properties": {},
            "required": [],
        }

        # Analyze inputs
        for execution in executions:
            task = execution.get("task", "")
            context = execution.get("context", {})

            # Extract placeholders from task
            placeholders = re.findall(r"\{(\w+)\}", task)
            for placeholder in placeholders:
                if placeholder not in schema["properties"]:
                    schema["properties"][placeholder] = {
                        "type": "string",
                        "description": f"Value for {placeholder}",
                    }
                    schema["required"].append(placeholder)

            # Add context keys
            for key, value in context.items():
                if key not in schema["properties"]:
                    schema["properties"][key] = {
                        "type": self._infer_type(value),
                        "description": f"Context: {key}",
                    }

        return schema

    def _extract_output_schema(
        self,
        executions: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Extract output schema from executions."""
        schema = {
            "type": "object",
            "properties": {
                "result": {"type": "string", "description": "Execution result"},
                "success": {"type": "boolean", "description": "Whether execution succeeded"},
            },
        }

        # Analyze outputs
        for execution in executions:
            output = execution.get("output", {})
            if isinstance(output, dict):
                for key, value in output.items():
                    if key not in schema["properties"]:
                        schema["properties"][key] = {
                            "type": self._infer_type(value),
                            "description": f"Output: {key}",
                        }

        return schema

    def _infer_type(self, value: Any) -> str:
        """Infer JSON Schema type from value."""
        if isinstance(value, bool):
            return "boolean"
        if isinstance(value, int):
            return "integer"
        if isinstance(value, float):
            return "number"
        if isinstance(value, str):
            return "string"
        if isinstance(value, list):
            return "array"
        if isinstance(value, dict):
            return "object"
        return "string"

    def _detect_domain(
        self,
        execution: dict[str, Any],
        steps: list[dict[str, Any]],
    ) -> SkillDomain:
        """Detect the domain of a pattern."""
        task = execution.get("task", "").lower()
        agents = execution.get("agents", [])

        domain_keywords = {
            SkillDomain.FRONTEND: ["ui", "frontend", "react", "css", "component", "html"],
            SkillDomain.BACKEND: ["api", "backend", "server", "endpoint", "route"],
            SkillDomain.DATABASE: ["database", "sql", "query", "schema", "migration"],
            SkillDomain.DEVOPS: ["deploy", "ci", "cd", "docker", "kubernetes"],
            SkillDomain.TESTING: ["test", "spec", "coverage", "e2e", "unit"],
            SkillDomain.SECURITY: ["security", "auth", "vulnerability", "audit"],
            SkillDomain.DOCUMENTATION: ["doc", "readme", "comment", "jsdoc"],
            SkillDomain.REFACTORING: ["refactor", "clean", "optimize", "improve"],
            SkillDomain.ANALYSIS: ["analyze", "review", "inspect", "check"],
        }

        for domain, keywords in domain_keywords.items():
            if any(kw in task for kw in keywords):
                return domain

        # Check agents
        agent_domains = {
            "frontend-specialist": SkillDomain.FRONTEND,
            "backend-specialist": SkillDomain.BACKEND,
            "database-architect": SkillDomain.DATABASE,
            "devops-engineer": SkillDomain.DEVOPS,
            "test-engineer": SkillDomain.TESTING,
            "security-auditor": SkillDomain.SECURITY,
            "documentation-writer": SkillDomain.DOCUMENTATION,
            "refactor": SkillDomain.REFACTORING,
            "explorer": SkillDomain.ANALYSIS,
        }

        for agent in agents:
            if agent in agent_domains:
                return agent_domains[agent]

        return SkillDomain.GENERAL

    def _generate_pattern_name(self, task: str, domain: SkillDomain) -> str:
        """Generate a name for the pattern."""
        # Extract key words
        words = re.findall(r"\b[a-z]+\b", task.lower())
        stop_words = {"the", "a", "an", "to", "for", "with", "in", "on", "at", "by"}
        key_words = [w for w in words if w not in stop_words][:3]

        name = "-".join(key_words) + f"-{domain.value}" if key_words else f"pattern-{domain.value}"

        return name

    def _calculate_pattern_confidence(
        self,
        success_count: int,
        total_count: int,
        num_steps: int,
        num_agents: int,
    ) -> float:
        """Calculate confidence in the pattern."""
        # Base confidence from success rate
        success_rate = success_count / max(total_count, 1)
        confidence = success_rate * 0.5

        # Bonus for more occurrences
        occurrence_bonus = min(0.2, total_count * 0.02)
        confidence += occurrence_bonus

        # Bonus for well-defined steps
        if 2 <= num_steps <= 10:
            confidence += 0.15
        elif num_steps > 0:
            confidence += 0.05

        # Bonus for focused agent usage
        if 1 <= num_agents <= 3:
            confidence += 0.15
        elif num_agents > 0:
            confidence += 0.05

        return min(confidence, 0.95)


class SkillTemplateGenerator:
    """Generates skill files from patterns."""

    def generate_skill_md(
        self,
        pattern: ExecutionPattern,
        skill_name: str,
    ) -> str:
        """Generate SKILL.md content."""
        template = f"""---
name: {skill_name}
description: {pattern.description}
domain: {pattern.domain.value}
auto_generated: true
source_pattern: {pattern.pattern_id}
confidence: {pattern.confidence:.0%}
---

# {skill_name}

{pattern.description}

## Overview

This skill was automatically generated from {pattern.total_count} successful executions
with a {pattern.success_rate:.0%} success rate.

**Domain:** {pattern.domain.value}
**Agents Involved:** {", ".join(pattern.agents_involved)}
**Average Execution Time:** {pattern.avg_execution_time_ms:.0f}ms

## Input

```json
{json.dumps(pattern.input_schema, indent=2)}
```

## Output

```json
{json.dumps(pattern.output_schema, indent=2)}
```

## Steps

"""
        for i, step in enumerate(pattern.steps, 1):
            template += f"""
### Step {i}: {step.get("action", "Action")}

- **Type:** {step.get("type", "action")}
- **Agent:** {step.get("agent", "any")}
- **Description:** {step.get("description", "")}

"""

        template += f"""
## Usage

```bash
python .agent/skills/{skill_name}/scripts/main.py --input '<your_input>'
```

## Generated

- **Date:** {datetime.now().strftime("%Y-%m-%d")}
- **Pattern ID:** {pattern.pattern_id}
- **Confidence:** {pattern.confidence:.0%}
"""
        return template

    def generate_script(
        self,
        pattern: ExecutionPattern,
        skill_name: str,
    ) -> str:
        """Generate main.py script content."""
        steps_code = self._generate_steps_code(pattern.steps)

        template = f'''#!/usr/bin/env python3
"""
{skill_name} - Auto-generated skill

{pattern.description}

Generated from pattern: {pattern.pattern_id}
Confidence: {pattern.confidence:.0%}
"""

import argparse
import asyncio
import json
import logging
import sys
from typing import Dict, Any
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


class {self._to_class_name(skill_name)}:
    """Auto-generated skill executor."""

    def __init__(self):
        self.name = "{skill_name}"
        self.domain = "{pattern.domain.value}"

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the skill.

        Args:
            input_data: Input matching the schema

        Returns:
            Result of execution
        """
        logger.info(f"Executing {{self.name}}...")

        result = {{
            "success": False,
            "steps_completed": 0,
            "output": None,
            "errors": [],
        }}

        try:
{steps_code}

            result["success"] = True
            logger.info(f"{{self.name}} completed successfully")

        except Exception as e:
            logger.error(f"Error in {{self.name}}: {{e}}")
            result["errors"].append(str(e))

        return result


async def main():
    parser = argparse.ArgumentParser(description="{pattern.description}")
    parser.add_argument("--input", "-i", type=str, help="JSON input data")
    parser.add_argument("--input-file", "-f", type=str, help="JSON input file")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    # Get input
    input_data = {{}}
    if args.input:
        input_data = json.loads(args.input)
    elif args.input_file:
        with open(args.input_file, encoding="utf-8") as f:
            input_data = json.load(f)
    else:
        # Try reading from stdin
        if not sys.stdin.isatty():
            input_data = json.load(sys.stdin)

    # Execute
    skill = {self._to_class_name(skill_name)}()
    result = await skill.execute(input_data)

    # Output
    if args.json:
        print(json.dumps(result, indent=2))
    else:
        if result["success"]:
            print(f"✓ {{skill.name}} completed successfully")
            print(f"  Steps completed: {{result['steps_completed']}}")
            if result.get("output"):
                print(f"  Output: {{result['output']}}")
        else:
            print(f"✗ {{skill.name}} failed")
            for error in result.get("errors", []):
                print(f"  Error: {{error}}")


if __name__ == "__main__":
    asyncio.run(main())
'''
        return template

    def generate_test(
        self,
        pattern: ExecutionPattern,
        skill_name: str,
    ) -> str:
        """Generate test file content."""
        template = f'''#!/usr/bin/env python3
"""
Tests for {skill_name}

Auto-generated tests based on pattern: {pattern.pattern_id}
"""

import pytest
import asyncio
from pathlib import Path
import sys

# Add skill to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from main import {self._to_class_name(skill_name)}


class Test{self._to_class_name(skill_name)}:
    """Test suite for {skill_name}."""

    @pytest.fixture
    def skill(self):
        """Create skill instance."""
        return {self._to_class_name(skill_name)}()

    @pytest.mark.asyncio
    async def test_basic_execution(self, skill):
        """Test basic execution."""
        input_data = {json.dumps(self._generate_sample_input(pattern.input_schema))}

        result = await skill.execute(input_data)

        assert "success" in result
        assert "steps_completed" in result
        assert isinstance(result.get("errors", []), list)

    @pytest.mark.asyncio
    async def test_empty_input(self, skill):
        """Test with empty input."""
        result = await skill.execute({{}})

        assert "success" in result
        # Should handle empty input gracefully

    @pytest.mark.asyncio
    async def test_invalid_input(self, skill):
        """Test with invalid input."""
        result = await skill.execute({{"invalid": "data"}})

        assert "success" in result
        # Should handle invalid input gracefully

'''

        # Add example-based tests
        for i, example in enumerate(pattern.examples[:3]):
            template += f'''
    @pytest.mark.asyncio
    async def test_example_{i + 1}(self, skill):
        """Test based on real execution example {i + 1}."""
        # Based on: {example.get("task", "Unknown task")[:50]}
        input_data = {json.dumps(example.get("context", {}))}

        result = await skill.execute(input_data)

        # Original execution was {"successful" if example.get("success") else "unsuccessful"}
        assert "success" in result

'''

        return template

    def _to_class_name(self, skill_name: str) -> str:
        """Convert skill name to class name."""
        words = skill_name.replace("-", " ").replace("_", " ").split()
        return "".join(word.capitalize() for word in words)

    def _generate_steps_code(self, steps: list[dict[str, Any]]) -> str:
        """Generate Python code for steps."""
        code_lines = []

        for i, step in enumerate(steps):
            action = step.get("action", "unknown")
            description = step.get("description", "")
            step.get("agent", "self")

            code_lines.append(f"            # Step {i + 1}: {description or action}")
            code_lines.append(f'            logger.info("Step {i + 1}: {action}")')
            code_lines.append(f"            # Implementar: {action}")
            code_lines.append(f'            result["steps_completed"] = {i + 1}')
            code_lines.append("")

        return "\n".join(code_lines)

    def _generate_sample_input(self, schema: dict[str, Any]) -> dict[str, Any]:
        """Generate sample input from schema."""
        sample = {}
        properties = schema.get("properties", {})

        for key, prop in properties.items():
            prop_type = prop.get("type", "string")
            if prop_type == "string":
                sample[key] = f"sample_{key}"
            elif prop_type == "integer":
                sample[key] = 1
            elif prop_type == "number":
                sample[key] = 1.0
            elif prop_type == "boolean":
                sample[key] = True
            elif prop_type == "array":
                sample[key] = []
            elif prop_type == "object":
                sample[key] = {}

        return sample


class SkillGenerator:
    """
    Generates skills from execution patterns.

    This class:
    1. Monitors execution history
    2. Extracts successful patterns
    3. Generates reusable skills
    4. Validates and deploys skills
    """

    PATTERN_THRESHOLD = 3  # Minimum occurrences
    SUCCESS_THRESHOLD = 0.8  # Minimum success rate
    CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence for generation

    def __init__(self, memory_dir: Path | None = None, skills_dir: Path | None = None):
        self.memory_dir = memory_dir or Path(".agent/memory/skill_generator")
        self.skills_dir = skills_dir or Path(".agent/skills")
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.extractor = PatternExtractor(
            min_occurrences=self.PATTERN_THRESHOLD,
            min_success_rate=self.SUCCESS_THRESHOLD,
        )
        self.template_generator = SkillTemplateGenerator()

        # Load state
        self.patterns: dict[str, ExecutionPattern] = {}
        self.generated_skills: dict[str, GeneratedSkill] = {}
        self._load_state()

    def _load_state(self) -> None:
        """Load saved state."""
        state_file = self.memory_dir / "generator_state.json"
        if state_file.exists():
            try:
                with open(state_file, encoding="utf-8") as f:
                    json.load(f)
                    # Load patterns and skills
                    logger.info("Loaded skill generator state")
            except Exception as e:
                logger.warning(f"Failed to load state: {e}")

    def _save_state(self) -> None:
        """Save state to disk."""
        state_file = self.memory_dir / "generator_state.json"
        data = {
            "patterns": {k: v.to_dict() for k, v in self.patterns.items()},
            "generated_skills": {k: v.to_dict() for k, v in self.generated_skills.items()},
            "updated_at": datetime.now().isoformat(),
        }
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)

    async def record_execution(self, execution: dict[str, Any]) -> None:
        """
        Record an execution for pattern analysis.

        Args:
            execution: Execution data including task, steps, agents, success, etc.
        """
        # Store execution
        history_file = self.memory_dir / "execution_history.jsonl"
        with open(history_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(execution, default=str) + "\n")

        logger.debug("Recorded execution for pattern analysis")

    async def analyze_patterns(self) -> list[ExecutionPattern]:
        """
        Analyze execution history and extract patterns.

        Returns:
            List of extracted patterns
        """
        # Load execution history
        history_file = self.memory_dir / "execution_history.jsonl"
        executions = []

        if history_file.exists():
            with open(history_file, encoding="utf-8") as f:
                for line in f:
                    try:
                        executions.append(json.loads(line))
                    except json.JSONDecodeError:
                        continue

        if not executions:
            logger.info("No executions to analyze")
            return []

        # Extract patterns
        patterns = self.extractor.extract_patterns(executions)

        # Update pattern store
        for pattern in patterns:
            self.patterns[pattern.pattern_id] = pattern

        self._save_state()

        logger.info(f"Extracted {len(patterns)} patterns from {len(executions)} executions")
        return patterns

    async def generate_from_pattern(
        self,
        pattern: ExecutionPattern,
    ) -> GenerationResult:
        """
        Generate a skill from a pattern.

        Args:
            pattern: The pattern to generate from

        Returns:
            GenerationResult with generated skill
        """
        logger.info(f"Generating skill from pattern: {pattern.name}")

        # Check confidence threshold
        if pattern.confidence < self.CONFIDENCE_THRESHOLD:
            return GenerationResult(
                success=False,
                skill=None,
                pattern_used=pattern,
                validation_passed=False,
                validation_errors=[
                    f"Pattern confidence ({pattern.confidence:.0%}) below threshold ({self.CONFIDENCE_THRESHOLD:.0%})"
                ],
                suggestions=["Gather more successful executions to increase confidence"],
            )

        # Generate skill name
        skill_name = self._generate_skill_name(pattern)

        # Check if skill already exists
        if skill_name in self.generated_skills:
            existing = self.generated_skills[skill_name]
            if existing.validated and existing.deployed:
                return GenerationResult(
                    success=True,
                    skill=existing,
                    pattern_used=pattern,
                    validation_passed=True,
                    validation_errors=[],
                    suggestions=["Skill already exists and is deployed"],
                )

        # Generate content
        skill_md = self.template_generator.generate_skill_md(pattern, skill_name)
        script = self.template_generator.generate_script(pattern, skill_name)
        test = self.template_generator.generate_test(pattern, skill_name)

        # Determine complexity
        complexity = self._determine_complexity(pattern)

        # Create skill
        skill = GeneratedSkill(
            skill_id=f"gen-{pattern.pattern_id}-{datetime.now().strftime('%Y%m%d')}",
            name=skill_name,
            description=pattern.description,
            domain=pattern.domain,
            complexity=complexity,
            source_pattern=pattern.pattern_id,
            skill_md_content=skill_md,
            script_content=script,
            test_content=test,
            input_schema=pattern.input_schema,
            output_schema=pattern.output_schema,
            dependencies=pattern.agents_involved,
            estimated_time_ms=pattern.avg_execution_time_ms,
            confidence=pattern.confidence,
        )

        # Validate
        validation_errors = self._validate_skill(skill)
        skill.validated = len(validation_errors) == 0

        # Store
        self.generated_skills[skill_name] = skill
        self._save_state()

        return GenerationResult(
            success=skill.validated,
            skill=skill,
            pattern_used=pattern,
            validation_passed=skill.validated,
            validation_errors=validation_errors,
            suggestions=self._generate_suggestions(skill, validation_errors),
        )

    def _generate_skill_name(self, pattern: ExecutionPattern) -> str:
        """Generate a unique skill name."""
        base_name = pattern.name.lower().replace(" ", "-")
        base_name = re.sub(r"[^a-z0-9-]", "", base_name)

        # Ensure uniqueness
        if base_name not in self.generated_skills:
            return base_name

        counter = 2
        while f"{base_name}-{counter}" in self.generated_skills:
            counter += 1

        return f"{base_name}-{counter}"

    def _determine_complexity(self, pattern: ExecutionPattern) -> SkillComplexity:
        """Determine skill complexity from pattern."""
        num_steps = len(pattern.steps)
        num_agents = len(pattern.agents_involved)

        if num_steps <= 1 and num_agents <= 1:
            return SkillComplexity.SIMPLE
        elif num_steps <= 5 and num_agents <= 2:
            return SkillComplexity.MODERATE
        elif num_steps <= 10 and num_agents <= 3:
            return SkillComplexity.COMPLEX
        else:
            return SkillComplexity.ADVANCED

    def _validate_skill(self, skill: GeneratedSkill) -> list[str]:
        """Validate generated skill."""
        errors = []

        # Check content is not empty
        if not skill.skill_md_content.strip():
            errors.append("SKILL.md content is empty")
        if not skill.script_content.strip():
            errors.append("Script content is empty")

        # Check for required elements
        if "def execute" not in skill.script_content:
            errors.append("Script missing execute method")
        if "---" not in skill.skill_md_content:
            errors.append("SKILL.md missing frontmatter")

        # Check confidence
        if skill.confidence < 0.5:
            errors.append(f"Low confidence: {skill.confidence:.0%}")

        return errors

    def _generate_suggestions(
        self,
        skill: GeneratedSkill,
        errors: list[str],
    ) -> list[str]:
        """Generate improvement suggestions."""
        suggestions = []

        if errors:
            suggestions.append("Fix validation errors before deployment")

        if skill.confidence < 0.8:
            suggestions.append("Gather more examples to improve pattern confidence")

        if skill.complexity == SkillComplexity.ADVANCED:
            suggestions.append("Consider breaking into smaller, focused skills")

        if not skill.test_content:
            suggestions.append("Add comprehensive tests")

        return suggestions

    async def deploy_skill(self, skill: GeneratedSkill) -> bool:
        """
        Deploy a generated skill to the skills directory.

        Args:
            skill: The skill to deploy

        Returns:
            True if deployment succeeded
        """
        if not skill.validated:
            logger.error(f"Cannot deploy unvalidated skill: {skill.name}")
            return False

        skill_dir = self.skills_dir / skill.name
        skill_dir.mkdir(parents=True, exist_ok=True)

        try:
            # Write SKILL.md
            (skill_dir / "SKILL.md").write_text(skill.skill_md_content)

            # Write script
            scripts_dir = skill_dir / "scripts"
            scripts_dir.mkdir(exist_ok=True)
            (scripts_dir / "main.py").write_text(skill.script_content)

            # Write tests
            tests_dir = skill_dir / "tests"
            tests_dir.mkdir(exist_ok=True)
            (tests_dir / f"test_{skill.name.replace('-', '_')}.py").write_text(skill.test_content)

            skill.deployed = True
            self._save_state()

            logger.info(f"Deployed skill: {skill.name} to {skill_dir}")
            return True

        except Exception as e:
            logger.error(f"Failed to deploy skill {skill.name}: {e}")
            return False

    async def discover_and_generate(self) -> list[GenerationResult]:
        """
        Discover patterns and generate skills automatically.

        Returns:
            List of generation results
        """
        # Analyze patterns
        patterns = await self.analyze_patterns()

        # Filter patterns ready for generation
        ready_patterns = [
            p
            for p in patterns
            if p.confidence >= self.CONFIDENCE_THRESHOLD
            and p.pattern_id not in [s.source_pattern for s in self.generated_skills.values()]
        ]

        # Generate skills
        results = []
        for pattern in ready_patterns[:5]:  # Limit to 5 at a time
            result = await self.generate_from_pattern(pattern)
            results.append(result)

            # Auto-deploy if successful
            if result.success and result.skill:
                await self.deploy_skill(result.skill)

        logger.info(
            f"Generated {len([r for r in results if r.success])} skills from {len(patterns)} patterns"
        )
        return results

    def get_patterns(self) -> list[ExecutionPattern]:
        """Get all known patterns."""
        return list(self.patterns.values())

    def get_generated_skills(self) -> list[GeneratedSkill]:
        """Get all generated skills."""
        return list(self.generated_skills.values())

    def export_report(self) -> str:
        """Export generation report as markdown."""
        lines = [
            "# Skill Generation Report",
            "",
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M')}",
            "",
            "## Patterns Discovered",
            "",
            f"Total patterns: {len(self.patterns)}",
            "",
        ]

        for pattern in sorted(self.patterns.values(), key=lambda p: p.confidence, reverse=True):
            lines.extend(
                [
                    f"### {pattern.name}",
                    f"- **Confidence:** {pattern.confidence:.0%}",
                    f"- **Success Rate:** {pattern.success_rate:.0%}",
                    f"- **Occurrences:** {pattern.total_count}",
                    f"- **Domain:** {pattern.domain.value}",
                    "",
                ]
            )

        lines.extend(
            [
                "## Generated Skills",
                "",
                f"Total skills: {len(self.generated_skills)}",
                "",
            ]
        )

        for skill in sorted(
            self.generated_skills.values(), key=lambda s: s.created_at, reverse=True
        ):
            status = (
                "✓ Deployed"
                if skill.deployed
                else ("○ Validated" if skill.validated else "✗ Pending")
            )
            lines.extend(
                [
                    f"### {skill.name}",
                    f"- **Status:** {status}",
                    f"- **Complexity:** {skill.complexity.value}",
                    f"- **Confidence:** {skill.confidence:.0%}",
                    f"- **Source Pattern:** {skill.source_pattern}",
                    "",
                ]
            )

        return "\n".join(lines)


# Convenience function
async def auto_generate_skill(
    executions: list[dict[str, Any]],
) -> list[GenerationResult]:
    """Quick function to generate skills from executions."""
    generator = SkillGenerator()
    for execution in executions:
        await generator.record_execution(execution)
    return await generator.discover_and_generate()
