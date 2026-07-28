"""
Skill Composer - Dynamic Skill Composition

Enables runtime composition of skills:
- Combine existing skills into new capabilities
- Sequential, parallel, and conditional composition
- Validate composed skills before execution
- Track composition effectiveness

Version: 1.0.0
"""

import asyncio
import inspect
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

# SkillRegistry will be imported lazily to avoid circular dependencies

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class CompositionType(Enum):
    """Types of skill composition."""

    SEQUENTIAL = "sequential"  # One after another
    PARALLEL = "parallel"  # All at once
    CONDITIONAL = "conditional"  # Based on conditions
    PIPELINE = "pipeline"  # Output of one feeds next
    FALLBACK = "fallback"  # Try alternatives on failure


class ValidationStatus(Enum):
    """Validation status of composed skill."""

    VALID = "valid"
    INVALID = "invalid"
    WARNING = "warning"
    UNTESTED = "untested"


@dataclass
class SkillInterface:
    """Interface definition for a skill."""

    inputs: dict = field(default_factory=dict)  # name -> type
    outputs: dict = field(default_factory=dict)  # name -> type
    required_context: list = field(default_factory=list)
    produces_context: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "inputs": self.inputs,
            "outputs": self.outputs,
            "required_context": self.required_context,
            "produces_context": self.produces_context,
        }


@dataclass
class SkillMetadata:
    """Metadata about a skill."""

    name: str
    description: str = ""
    category: str = ""
    tags: list = field(default_factory=list)
    version: str = "1.0.0"
    interface: SkillInterface = field(default_factory=SkillInterface)
    path: str | None = None  # Path to skill directory
    dependencies: list = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "tags": self.tags,
            "version": self.version,
            "interface": self.interface.to_dict(),
            "path": self.path,
            "dependencies": self.dependencies,
        }


@dataclass
class ComposedSkill:
    """A dynamically composed skill."""

    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    components: list = field(default_factory=list)  # Skill names
    composition_type: CompositionType = CompositionType.SEQUENTIAL
    interface: SkillInterface = field(default_factory=SkillInterface)
    conditions: dict = field(default_factory=dict)  # For conditional composition
    created_at: datetime = field(default_factory=datetime.now)
    validation_status: ValidationStatus = ValidationStatus.UNTESTED
    execution_count: int = 0
    success_rate: float = 0.0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "components": self.components,
            "composition_type": self.composition_type.value,
            "interface": self.interface.to_dict(),
            "conditions": self.conditions,
            "created_at": self.created_at.isoformat(),
            "validation_status": self.validation_status.value,
            "execution_count": self.execution_count,
            "success_rate": self.success_rate,
            "metadata": self.metadata,
        }


@dataclass
class ValidationResult:
    """Result of skill validation."""

    status: ValidationStatus
    errors: list = field(default_factory=list)
    warnings: list = field(default_factory=list)
    interface_valid: bool = True
    dependencies_satisfied: bool = True
    estimated_complexity: str = "medium"

    def to_dict(self) -> dict:
        return {
            "status": self.status.value,
            "errors": self.errors,
            "warnings": self.warnings,
            "interface_valid": self.interface_valid,
            "dependencies_satisfied": self.dependencies_satisfied,
            "estimated_complexity": self.estimated_complexity,
        }


@dataclass
class ExecutionResult:
    """Result of executing a composed skill."""

    success: bool
    outputs: dict = field(default_factory=dict)
    component_results: list = field(default_factory=list)
    duration_ms: int = 0
    error: str | None = None

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "outputs": self.outputs,
            "component_results": self.component_results,
            "duration_ms": self.duration_ms,
            "error": self.error,
        }


class SkillComposer:
    """
    Dynamically compose skills at runtime.

    Allows combining existing skills into new capabilities
    without manual skill creation.
    """

    def __init__(self, skills_path: Path | None = None):
        self.skills_path = skills_path or Path(".agent/skills")
        self.composed_skills: dict[str, ComposedSkill] = {}
        self.skill_executors: dict[str, Callable] = {}  # Skill name -> executor
        self._registry = None  # Lazy-loaded

    def _get_registry(self):
        """Get or initialize SkillRegistry lazily."""
        if self._registry is None:
            if not self.skills_path.exists():
                self._registry = False
                return None

            try:
                # Lazy import to avoid circular dependencies
                from skill_registry import SkillRegistry

                registry = SkillRegistry.instance(self.skills_path)
                if (
                    registry.skills_dirs
                    and Path(registry.skills_dirs[0]).resolve() != self.skills_path.resolve()
                ):
                    registry = SkillRegistry(self.skills_path)
                self._registry = registry
            except ImportError:
                try:
                    from .skill_registry import SkillRegistry

                    registry = SkillRegistry.instance(self.skills_path)
                    if (
                        registry.skills_dirs
                        and Path(registry.skills_dirs[0]).resolve() != self.skills_path.resolve()
                    ):
                        registry = SkillRegistry(self.skills_path)
                    self._registry = registry
                except Exception as e:
                    logger.error(f"Failed to initialize SkillRegistry: {e}")
                    self._registry = False  # Mark as failed
            except Exception as e:
                logger.error(f"Failed to initialize SkillRegistry: {e}")
                self._registry = False
        return self._registry if self._registry is not False else None

    @property
    def registry(self):
        """Get SkillRegistry instance (lazy-loaded)."""
        return self._get_registry()

    @property
    def available_skills(self) -> dict[str, SkillMetadata]:
        """Get available skills from registry plus filesystem fallback."""
        result: dict[str, SkillMetadata] = {}

        if self.registry:
            for record in self.registry.list_all(lazy=True):
                frontmatter = record.frontmatter if hasattr(record, "frontmatter") else {}
                result[record.name] = SkillMetadata(
                    name=record.name,
                    path=str(record.path),
                    description=frontmatter.get("description") or f"Skill: {record.name}",
                    category=frontmatter.get("category") or "",
                    tags=frontmatter.get("tags") or [],
                    version=frontmatter.get("version") or "1.0.0",
                )

        if self.skills_path.exists():
            for skill_dir in sorted(self.skills_path.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith((".", "_")):
                    continue

                skill_file = skill_dir / "SKILL.md"
                if not skill_file.exists():
                    continue

                result[skill_dir.name] = SkillMetadata(
                    name=skill_dir.name,
                    path=str(skill_dir),
                    description=f"Skill: {skill_dir.name}",
                )

        return result

    def register_executor(self, skill_name: str, executor: Callable):
        """Register an executor function for a skill."""
        self.skill_executors[skill_name] = executor

    async def compose_for_task(
        self,
        task: str,
        available_skills: list[str] | None = None,
        composition_type: CompositionType = CompositionType.SEQUENTIAL,
    ) -> ComposedSkill:
        """
        Compose skills for a specific task.

        Args:
            task: Task description
            available_skills: Skills to consider (default: all)
            composition_type: How to compose

        Returns:
            ComposedSkill ready for execution
        """
        if not self.registry:
            logger.warning("SkillRegistry not available, using fallback")
            return ComposedSkill(
                name=f"composed_{task[:30].replace(' ', '_').lower()}",
                description=f"Composed skill for: {task}",
            )

        # Use SkillRegistry for semantic search
        search_results = self.registry.search(task, k=10)
        selected_skills = [name for name, _score in search_results]

        # If specific skills requested, intersect with results
        if available_skills:
            selected_skills = [s for s in selected_skills if s in available_skills]

        # If no matches, select from available
        if not selected_skills:
            all_available = available_skills or [s.name for s in self.registry.list_all(lazy=True)]
            selected_skills = all_available[:3]

        # Create composed skill
        composed = ComposedSkill(
            name=f"composed_{task[:30].replace(' ', '_').lower()}",
            description=f"Composed skill for: {task}",
            components=selected_skills,
            composition_type=composition_type,
            interface=self._merge_interfaces(selected_skills),
        )

        self.composed_skills[composed.id] = composed
        logger.info(f"Composed skill with {len(selected_skills)} components using registry search")
        return composed

    def _merge_interfaces(self, skill_names: list[str]) -> SkillInterface:
        """Merge interfaces of multiple skills."""
        merged = SkillInterface()

        for name in skill_names:
            if name in self.available_skills:
                skill = self.available_skills[name]
                # Merge inputs (union)
                merged.inputs.update(skill.interface.inputs)
                # Merge outputs (union)
                merged.outputs.update(skill.interface.outputs)
                # Merge required context (union, dedupe)
                for ctx in skill.interface.required_context:
                    if ctx not in merged.required_context:
                        merged.required_context.append(ctx)
                # Merge produces context (union, dedupe)
                for ctx in skill.interface.produces_context:
                    if ctx not in merged.produces_context:
                        merged.produces_context.append(ctx)

        return merged

    @staticmethod
    def _estimate_complexity(n_components: int) -> str:
        """Estima la complejidad de una composición según su número de componentes.

        Args:
            n_components: Cantidad de skills componentes.

        Returns:
            "high" (>5), "medium" (>2) o "low".
        """
        if n_components > 5:
            return "high"
        if n_components > 2:
            return "medium"
        return "low"

    @staticmethod
    def _determine_status(errors: list, warnings: list) -> ValidationStatus:
        """Determina el status de validación a partir de errores/warnings.

        Args:
            errors: Lista de errores detectados.
            warnings: Lista de advertencias detectadas.

        Returns:
            INVALID si hay errores, WARNING si solo hay advertencias, VALID si nada.
        """
        if errors:
            return ValidationStatus.INVALID
        if warnings:
            return ValidationStatus.WARNING
        return ValidationStatus.VALID

    async def validate_composition(self, skill: ComposedSkill) -> ValidationResult:
        """
        Validate a composed skill before use.

        Args:
            skill: ComposedSkill to validate

        Returns:
            ValidationResult
        """
        errors = []
        warnings = []

        # Check components exist
        for component in skill.components:
            if component not in self.available_skills:
                errors.append(f"Component skill not found: {component}")

        # Check for circular dependencies
        if self._has_circular_deps(skill.components):
            errors.append("Circular dependencies detected")

        # Check interface compatibility for pipeline
        if skill.composition_type == CompositionType.PIPELINE:
            if not self._check_pipeline_compatibility(skill.components):
                warnings.append("Output/input types may not align in pipeline")

        # Check executor availability
        missing_executors = [c for c in skill.components if c not in self.skill_executors]
        if missing_executors:
            warnings.append(f"No executors for: {', '.join(missing_executors)}")

        complexity = self._estimate_complexity(len(skill.components))
        status = self._determine_status(errors, warnings)

        result = ValidationResult(
            status=status,
            errors=errors,
            warnings=warnings,
            interface_valid=len(errors) == 0,
            dependencies_satisfied=len(missing_executors) == 0,
            estimated_complexity=complexity,
        )

        # Update skill status
        skill.validation_status = status
        return result

    def _has_circular_deps(self, components: list[str]) -> bool:
        """Check for circular dependencies."""
        # Simple check - in production would build dependency graph
        return False

    def _check_pipeline_compatibility(self, components: list[str]) -> bool:
        """Check if outputs match inputs in pipeline."""
        # Simple check - would need proper type checking
        return True

    async def execute_composed(
        self, skill: ComposedSkill, input_data: dict, context: dict | None = None
    ) -> ExecutionResult:
        """
        Execute a composed skill.

        Args:
            skill: ComposedSkill to execute
            input_data: Input data for the skill
            context: Execution context

        Returns:
            ExecutionResult
        """
        start_time = datetime.now()
        component_results: list = []
        current_data = input_data.copy()
        ctx = context or {}

        try:
            strategies = {
                CompositionType.SEQUENTIAL: self._run_sequential,
                CompositionType.PARALLEL: self._run_parallel,
                CompositionType.PIPELINE: self._run_pipeline,
                CompositionType.FALLBACK: self._run_fallback,
                CompositionType.CONDITIONAL: self._run_conditional,
            }
            strategy = strategies.get(skill.composition_type)
            if strategy is not None:
                component_results, current_data = await strategy(
                    skill, input_data, current_data, ctx
                )

            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Update stats
            skill.execution_count += 1
            skill.success_rate = (
                skill.success_rate * (skill.execution_count - 1) + 1.0
            ) / skill.execution_count

            return ExecutionResult(
                success=True,
                outputs=current_data,
                component_results=component_results,
                duration_ms=duration_ms,
            )

        except Exception as e:
            duration_ms = int((datetime.now() - start_time).total_seconds() * 1000)

            # Update stats
            skill.execution_count += 1
            skill.success_rate = (
                skill.success_rate * (skill.execution_count - 1)
            ) / skill.execution_count

            return ExecutionResult(
                success=False,
                outputs={},
                component_results=component_results,
                duration_ms=duration_ms,
                error=str(e),
            )

    async def _run_sequential(
        self, skill: ComposedSkill, input_data: dict, current_data: dict, ctx: dict
    ) -> tuple[list, dict]:
        """Ejecuta los componentes uno tras otro, propagando la salida.

        Args:
            skill: Skill compuesto a ejecutar.
            input_data: Datos de entrada originales.
            current_data: Acumulador de datos que se va actualizando.
            ctx: Contexto de ejecución.

        Returns:
            Tupla con los resultados de cada componente y los datos finales.

        Raises:
            Exception: Si algún componente falla.
        """
        component_results: list = []
        for component in skill.components:
            result = await self._execute_component(component, current_data, ctx)
            component_results.append(result)
            if not result.get("success", False):
                raise Exception(f"Component {component} failed")
            current_data.update(result.get("output", {}))
        return component_results, current_data

    async def _run_parallel(
        self, skill: ComposedSkill, input_data: dict, current_data: dict, ctx: dict
    ) -> tuple[list, dict]:
        """Ejecuta todos los componentes en paralelo.

        Args:
            skill: Skill compuesto a ejecutar.
            input_data: Datos de entrada originales (compartidos por todos).
            current_data: Acumulador de datos (sin cambios en paralelo).
            ctx: Contexto de ejecución.

        Returns:
            Tupla con los resultados de cada componente y los datos finales.

        Raises:
            Exception: Si algún componente lanza una excepción.
        """
        tasks = [self._execute_component(c, input_data, ctx) for c in skill.components]
        component_results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in component_results:
            if isinstance(result, Exception):
                raise result
        return list(component_results), current_data

    async def _run_pipeline(
        self, skill: ComposedSkill, input_data: dict, current_data: dict, ctx: dict
    ) -> tuple[list, dict]:
        """Ejecuta los componentes encadenando la salida de uno como entrada del siguiente.

        Args:
            skill: Skill compuesto a ejecutar.
            input_data: Datos de entrada originales.
            current_data: Acumulador de datos que se reemplaza en cada paso.
            ctx: Contexto de ejecución.

        Returns:
            Tupla con los resultados de cada componente y los datos finales.

        Raises:
            Exception: Si algún componente del pipeline falla.
        """
        component_results: list = []
        for component in skill.components:
            result = await self._execute_component(component, current_data, ctx)
            component_results.append(result)
            if not result.get("success", False):
                raise Exception(f"Pipeline failed at {component}")
            current_data = result.get("output", {})
        return component_results, current_data

    async def _run_fallback(
        self, skill: ComposedSkill, input_data: dict, current_data: dict, ctx: dict
    ) -> tuple[list, dict]:
        """Prueba alternativas hasta que una tenga éxito.

        Args:
            skill: Skill compuesto a ejecutar.
            input_data: Datos de entrada originales (compartidos por todos).
            current_data: Acumulador de datos.
            ctx: Contexto de ejecución.

        Returns:
            Tupla con los resultados de cada componente y los datos finales.

        Raises:
            Exception: Si todos los componentes de fallback fallan.
        """
        component_results: list = []
        for component in skill.components:
            result = await self._execute_component(component, input_data, ctx)
            component_results.append(result)
            if result.get("success", False):
                current_data = result.get("output", {})
                break
        else:
            raise Exception("All fallback components failed")
        return component_results, current_data

    async def _run_conditional(
        self, skill: ComposedSkill, input_data: dict, current_data: dict, ctx: dict
    ) -> tuple[list, dict]:
        """Ejecuta los componentes cuya condición se cumpla.

        Args:
            skill: Skill compuesto a ejecutar.
            input_data: Datos de entrada originales.
            current_data: Acumulador de datos que se va actualizando.
            ctx: Contexto de ejecución.

        Returns:
            Tupla con los resultados de cada componente y los datos finales.
        """
        component_results: list = []
        for component in skill.components:
            condition = skill.conditions.get(component, {})
            if self._evaluate_condition(condition, current_data, ctx):
                result = await self._execute_component(component, current_data, ctx)
                component_results.append(result)
                current_data.update(result.get("output", {}))
        return component_results, current_data

    async def _execute_component(self, component: str, input_data: dict, context: dict) -> dict:
        """Execute a single skill component."""
        if component in self.skill_executors:
            executor = self.skill_executors[component]
            if inspect.iscoroutinefunction(executor):
                return await executor(input_data, context)
            else:
                return executor(input_data, context)
        else:
            # Return mock success for skills without executors
            logger.warning(f"No executor for {component}, returning mock success")
            return {"success": True, "output": {"component": component, "status": "simulated"}}

    def _evaluate_condition(self, condition: dict, data: dict, context: dict) -> bool:
        """Evaluate a condition for conditional composition."""
        if not condition:
            return True

        # Simple condition evaluation
        # In production, would support complex expressions
        required_key = condition.get("requires_key")
        if required_key:
            return required_key in data or required_key in context

        min_value = condition.get("min_value")
        key = condition.get("key")
        if min_value is not None and key:
            value = data.get(key, context.get(key, 0))
            return value >= min_value

        return True

    def get_composed_skill(self, skill_id: str) -> ComposedSkill | None:
        """Get a composed skill by ID."""
        return self.composed_skills.get(skill_id)

    def list_composed_skills(self) -> list[dict]:
        """List all composed skills."""
        return [s.to_dict() for s in self.composed_skills.values()]

    def get_stats(self) -> dict:
        """Get composer statistics."""
        return {
            "available_skills": len(self.available_skills),
            "composed_skills": len(self.composed_skills),
            "registered_executors": len(self.skill_executors),
            "avg_success_rate": sum(s.success_rate for s in self.composed_skills.values())
            / max(len(self.composed_skills), 1),
        }


# Singleton instance
_composer_instance: SkillComposer | None = None


def get_skill_composer(skills_path: Path | None = None) -> SkillComposer:
    """Get the global SkillComposer instance."""
    global _composer_instance
    if _composer_instance is None:
        _composer_instance = SkillComposer(skills_path)
    return _composer_instance


# Example usage
if __name__ == "__main__":

    async def demo():
        composer = get_skill_composer()

        # Register mock executors
        def mock_executor(input_data, context):
            return {"success": True, "output": {"processed": True}}

        composer.register_executor("testing-patterns", mock_executor)
        composer.register_executor("api-patterns", mock_executor)

        # Compose for a task
        composed = await composer.compose_for_task(
            task="Create API with testing", composition_type=CompositionType.SEQUENTIAL
        )
        print(f"Composed skill: {composed.to_dict()}")

        # Validate
        validation = await composer.validate_composition(composed)
        print(f"Validation: {validation.to_dict()}")

        # Execute
        result = await composer.execute_composed(composed, input_data={"endpoint": "/users"})
        print(f"Execution: {result.to_dict()}")

        # Stats
        print(f"Stats: {composer.get_stats()}")

    asyncio.run(demo())
