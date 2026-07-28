"""
Skill Composition Engine — Encadenamiento dinámico de skills.

Permite descomponer tareas complejas en pipelines de skills que se ejecutan
en secuencia o en paralelo, pasando el output de cada paso como contexto
del siguiente.

Ejemplo de uso:

    from .agent.core.skill_composition_engine import SkillCompositionEngine

    engine = SkillCompositionEngine()

    # Componer un pipeline para una tarea
    pipeline = engine.compose("implementar autenticación JWT con tests")

    # Ejecutar el pipeline
    result = await engine.execute_pipeline(pipeline, context={"language": "python"})

    print(result.final_output)
    print(result.steps_executed)
"""

from __future__ import annotations

import asyncio
import logging
import re
import shlex
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from .skill_metadata_index import SkillMetadataIndex

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / ".agent" / "skills"
DEFAULT_TIMEOUT = 60


class ExecutionMode(str, Enum):
    """Modo de ejecución de un paso del pipeline."""

    SEQUENTIAL = "sequential"  # Espera el paso anterior
    PARALLEL = "parallel"  # Puede ejecutarse junto a otros


@dataclass
class SkillStep:
    """Un paso en el pipeline de composición."""

    skill_name: str
    description: str
    args_template: str = ""
    mode: ExecutionMode = ExecutionMode.SEQUENTIAL
    depends_on: list[str] = field(default_factory=list)
    relevance_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            "skill": self.skill_name,
            "description": self.description,
            "args_template": self.args_template,
            "mode": self.mode.value,
            "depends_on": self.depends_on,
            "relevance_score": round(self.relevance_score, 2),
        }


@dataclass
class StepResult:
    """Resultado de ejecutar un SkillStep."""

    step: SkillStep
    output: str
    success: bool
    error: str | None = None
    duration_ms: float = 0.0

    def to_dict(self) -> dict:
        return {
            "skill": self.step.skill_name,
            "success": self.success,
            "output_preview": self.output[:500] if self.output else "",
            "error": self.error,
            "duration_ms": round(self.duration_ms, 1),
        }


@dataclass
class PipelineResult:
    """Resultado completo de un pipeline ejecutado."""

    task: str
    steps_total: int
    steps_succeeded: int
    steps_failed: int
    step_results: list[StepResult] = field(default_factory=list)
    final_output: str = ""
    pipeline_output: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "summary": {
                "total": self.steps_total,
                "succeeded": self.steps_succeeded,
                "failed": self.steps_failed,
            },
            "steps": [r.to_dict() for r in self.step_results],
            "final_output": self.final_output[:2000],
        }


class SkillCompositionEngine:
    """
    Motor de composición de skills.

    Convierte tareas de alto nivel en pipelines ejecutables,
    resolviendo dependencias entre skills y optimizando el orden
    de ejecución.
    """

    # Reglas de composición: patrones de tarea → skills encadenadas
    COMPOSITION_RULES: list[dict[str, Any]] = [
        {
            "pattern": r"(autenticaci|auth|jwt|login|sesion)",
            "pipeline": [
                {"skill": "api-patterns", "mode": "sequential"},
                {"skill": "security-compliance", "mode": "sequential"},
                {"skill": "testing-patterns", "mode": "sequential"},
            ],
            "description": "Autenticación segura: diseño API → seguridad → tests",
        },
        {
            "pattern": r"(base de datos|database|schema|migra)",
            "pipeline": [
                {"skill": "database-design", "mode": "sequential"},
                {"skill": "sql-optimization", "mode": "sequential"},
                {"skill": "tdd-workflow", "mode": "sequential"},
            ],
            "description": "Database: diseño → optimización → tests",
        },
        {
            "pattern": r"(seguridad|security|vulnerabilidad|owasp|pentest)",
            "pipeline": [
                {"skill": "vulnerability-scanner", "mode": "sequential"},
                {"skill": "red-team-tactics", "mode": "parallel"},
                {"skill": "ethical-hacking-methodology", "mode": "parallel"},
            ],
            "description": "Auditoría de seguridad: scan → análisis ofensivo → metodología",
        },
        {
            "pattern": r"(frontend|react|nextjs|ui|interfaz)",
            "pipeline": [
                {"skill": "nextjs-react-expert", "mode": "sequential"},
                {"skill": "tailwind-patterns", "mode": "parallel"},
                {"skill": "webapp-testing", "mode": "sequential"},
            ],
            "description": "Frontend: React → estilos → tests",
        },
        {
            "pattern": r"(api|rest|endpoint|microservicio)",
            "pipeline": [
                {"skill": "api-patterns", "mode": "sequential"},
                {"skill": "fastapi-pro", "mode": "sequential"},
                {"skill": "api-testing-observability", "mode": "sequential"},
            ],
            "description": "API REST: diseño → implementación → testing",
        },
        {
            "pattern": r"(docker|contenedor|kubernetes|k8s|deploy)",
            "pipeline": [
                {"skill": "docker-expert", "mode": "sequential"},
                {"skill": "kubernetes-architect", "mode": "sequential"},
                {"skill": "deployment-strategies", "mode": "sequential"},
            ],
            "description": "DevOps: Docker → K8s → estrategia de deploy",
        },
        {
            "pattern": r"(ml|machine learning|modelo|entrenamiento|ia)",
            "pipeline": [
                {"skill": "ai-engineer", "mode": "sequential"},
                {"skill": "rag-engineer", "mode": "parallel"},
                {"skill": "prompt-engineering", "mode": "parallel"},
            ],
            "description": "ML/AI: ingeniería → RAG → prompts",
        },
        {
            "pattern": r"(excel|csv|datos|data|etl)",
            "pipeline": [
                {"skill": "excel-super-agent", "mode": "sequential"},
                {"skill": "data-engineering", "mode": "sequential"},
            ],
            "description": "Procesamiento de datos: Excel → ETL",
        },
        {
            "pattern": r"(test|prueba|cobertura|calidad)",
            "pipeline": [
                {"skill": "testing-patterns", "mode": "sequential"},
                {"skill": "tdd-workflow", "mode": "parallel"},
                {"skill": "playwright-testing", "mode": "parallel"},
            ],
            "description": "Testing: patrones → TDD → E2E",
        },
        {
            "pattern": r"(documentaci|doc|readme|wiki)",
            "pipeline": [
                {"skill": "code-documentation", "mode": "sequential"},
                {"skill": "api-documentation", "mode": "parallel"},
            ],
            "description": "Documentación: código → API",
        },
    ]

    def __init__(self) -> None:
        self.available_skills = self._index_skills()
        self.metadata_index = SkillMetadataIndex(SKILLS_DIR)
        # Enriquecer descripciones en available_skills con las del metadata_index
        for name, meta in self.metadata_index._metadata.items():
            if name in self.available_skills and meta.get("description"):
                self.available_skills[name]["description"] = meta["description"]
        logger.info("SkillCompositionEngine inicializado con %d skills", len(self.available_skills))

    def _index_skills(self) -> dict[str, dict]:
        """Indexa las skills disponibles."""
        index: dict[str, dict] = {}
        if not SKILLS_DIR.exists():
            return index
        for skill_dir in SKILLS_DIR.iterdir():
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            scripts = (
                list((skill_dir / "scripts").glob("*.py"))
                if (skill_dir / "scripts").exists()
                else []
            )
            if scripts:
                skill_md = skill_dir / "SKILL.md"
                desc = ""
                if skill_md.exists():
                    try:
                        for line in skill_md.read_text(encoding="utf-8").split("\n"):
                            if line.strip() and not line.startswith("#"):
                                desc = line.strip()[:200]
                                break
                    except (OSError, UnicodeDecodeError):
                        pass
                index[skill_dir.name] = {
                    "script": str(scripts[0]),
                    "description": desc or skill_dir.name,
                }
        return index

    # ------------------------------------------------------------------
    # Composición
    # ------------------------------------------------------------------

    def compose(self, task: str, max_steps: int = 6) -> list[SkillStep]:
        """
        Descompone una tarea en un pipeline de skills.

        Args:
            task: Descripción de la tarea de alto nivel.
            max_steps: Número máximo de pasos en el pipeline.

        Returns:
            Lista ordenada de SkillSteps listos para ejecutar.
        """
        task_lower = task.lower()

        # 1. Buscar reglas de composición predefinidas
        pipeline = self._match_composition_rules(task_lower, max_steps)

        # 2. Si no hay reglas específicas, usar scoring semántico
        if not pipeline:
            pipeline = self._semantic_compose(task_lower, max_steps)

        # 3. Filtrar skills que realmente existen
        pipeline = [s for s in pipeline if s.skill_name in self.available_skills]

        # 4. Resolver dependencias
        pipeline = self._resolve_dependencies(pipeline)

        logger.info(
            "Pipeline compuesto para '%s': %d pasos → %s",
            task[:50],
            len(pipeline),
            [s.skill_name for s in pipeline],
        )
        return pipeline

    def _match_composition_rules(self, task_lower: str, max_steps: int) -> list[SkillStep]:
        """Busca reglas de composición predefinidas."""
        for rule in self.COMPOSITION_RULES:
            if re.search(rule["pattern"], task_lower, re.IGNORECASE):
                steps = []
                for i, step_def in enumerate(rule["pipeline"][:max_steps]):
                    skill_name = step_def["skill"]
                    mode = ExecutionMode(step_def.get("mode", "sequential"))
                    desc = (
                        self.available_skills.get(skill_name, {}).get("description", "")
                        or f"Skill: {skill_name}"
                    )
                    steps.append(
                        SkillStep(
                            skill_name=skill_name,
                            description=desc,
                            mode=mode,
                            relevance_score=10.0 - i,
                        )
                    )
                return steps
        return []

    def _semantic_compose(self, task_lower: str, max_steps: int) -> list[SkillStep]:
        """Compone pipeline por scoring semántico de palabras clave."""
        scored: list[tuple[float, str, str]] = []

        for name, info in self.available_skills.items():
            desc_lower = info["description"].lower()
            name_lower = name.lower()
            score = 0.0

            for word in task_lower.split():
                if len(word) < 3:
                    continue
                if word in name_lower:
                    score += 3.0
                elif any(w.startswith(word[:4]) for w in name_lower.split("-")):
                    score += 1.5
                if word in desc_lower:
                    score += 1.0

            if score > 0:
                scored.append((score, name, info["description"]))

        scored.sort(key=lambda x: -x[0])

        return [
            SkillStep(
                skill_name=name,
                description=desc,
                mode=ExecutionMode.SEQUENTIAL,
                relevance_score=score,
            )
            for score, name, desc in scored[:max_steps]
        ]

    def _resolve_dependencies(self, steps: list[SkillStep]) -> list[SkillStep]:
        """
        Resuelve dependencias entre pasos:
        - Los pasos PARALLEL pueden ejecutarse junto a sus vecinos.
        - Los pasos SEQUENTIAL esperan al anterior.
        """
        resolved: list[SkillStep] = []
        for i, step in enumerate(steps):
            if i > 0 and step.mode == ExecutionMode.SEQUENTIAL:
                step.depends_on = [steps[i - 1].skill_name]
            resolved.append(step)
        return resolved

    # ------------------------------------------------------------------
    # Ejecución
    # ------------------------------------------------------------------

    async def execute_pipeline(
        self,
        pipeline: list[SkillStep],
        task: str = "",
        context: dict[str, str] | None = None,
    ) -> PipelineResult:
        """
        Ejecuta un pipeline de skills.

        Skills PARALLEL se ejecutan concurrentemente.
        Skills SEQUENTIAL esperan a que su dependencia termine.

        Args:
            pipeline: Lista de SkillSteps a ejecutar.
            task: Descripción de la tarea (para logging).
            context: Variables de contexto para los args templates.

        Returns:
            PipelineResult con todos los resultados.
        """
        context = context or {}
        results: list[StepResult] = []
        accumulated_context = dict(context)

        # Agrupar por modo de ejecución
        i = 0
        while i < len(pipeline):
            step = pipeline[i]

            if step.mode == ExecutionMode.PARALLEL:
                # Agrupar todos los pasos PARALLEL consecutivos
                parallel_group = [step]
                j = i + 1
                while j < len(pipeline) and pipeline[j].mode == ExecutionMode.PARALLEL:
                    parallel_group.append(pipeline[j])
                    j += 1

                # Ejecutar en paralelo
                group_results = await asyncio.gather(
                    *[self._execute_step(s, accumulated_context) for s in parallel_group]
                )
                results.extend(group_results)

                # Acumular contexto
                for r in group_results:
                    if r.success:
                        accumulated_context[f"output_{r.step.skill_name}"] = r.output[:1000]

                i = j
            else:
                # Ejecutar secuencialmente
                result = await self._execute_step(step, accumulated_context)
                results.append(result)
                if result.success:
                    accumulated_context[f"output_{step.skill_name}"] = result.output[:1000]
                    accumulated_context["last_output"] = result.output[:1000]
                i += 1

        succeeded = sum(1 for r in results if r.success)
        failed = len(results) - succeeded

        final_output = "\n\n---\n\n".join(
            f"## {r.step.skill_name}\n{r.output[:800]}" for r in results if r.success
        )

        return PipelineResult(
            task=task,
            steps_total=len(results),
            steps_succeeded=succeeded,
            steps_failed=failed,
            step_results=results,
            final_output=final_output,
        )

    async def _execute_step(self, step: SkillStep, context: dict[str, str]) -> StepResult:
        """Ejecuta un único SkillStep de forma segura."""
        import time

        start = time.perf_counter()

        if step.skill_name not in self.available_skills:
            return StepResult(
                step=step,
                output="",
                success=False,
                error=f"Skill '{step.skill_name}' no encontrada",
            )

        script_path = Path(self.available_skills[step.skill_name]["script"]).resolve()

        # Seguridad: prevenir path traversal
        try:
            script_path.relative_to(PROJECT_ROOT.resolve())
        except ValueError:
            return StepResult(
                step=step,
                output="",
                success=False,
                error="Ruta fuera del proyecto",
            )

        # Resolver args template
        args_str = step.args_template
        for key, val in context.items():
            args_str = args_str.replace(f"{{{key}}}", val[:200])

        try:
            safe_args = shlex.split(args_str) if args_str.strip() else ["--help"]
        except ValueError:
            safe_args = ["--help"]

        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(script_path),
                *safe_args,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=PROJECT_ROOT,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=DEFAULT_TIMEOUT)
            output = stdout.decode("utf-8", errors="replace") or stderr.decode(
                "utf-8", errors="replace"
            )
            success = proc.returncode == 0
        except TimeoutError:
            output = ""
            success = False
            error = f"Timeout ({DEFAULT_TIMEOUT}s)"
        except Exception as e:
            output = ""
            success = False
            error = str(e)
        else:
            error = None if success else f"Exit code {proc.returncode}"  # type: ignore[assignment]  # str|None narrowing

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info(
            "Skill '%s': %s (%.0fms)",
            step.skill_name,
            "OK" if success else "FAIL",
            duration_ms,
        )

        return StepResult(
            step=step,
            output=output,
            success=success,
            error=error,
            duration_ms=duration_ms,
        )

    # ------------------------------------------------------------------
    # Utilidades
    # ------------------------------------------------------------------

    def describe_pipeline(self, pipeline: list[SkillStep]) -> dict:
        """Genera una descripción legible del pipeline."""
        return {
            "steps": len(pipeline),
            "pipeline": [s.to_dict() for s in pipeline],
            "execution_groups": self._group_by_execution(pipeline),
        }

    def _group_by_execution(self, pipeline: list[SkillStep]) -> list[dict]:
        """Agrupa los pasos por modo de ejecución."""
        groups: list[dict] = []
        current_group: list[str] = []
        current_mode = ExecutionMode.SEQUENTIAL

        for step in pipeline:
            if step.mode != current_mode and current_group:
                groups.append({"mode": current_mode.value, "skills": current_group})
                current_group = []
            current_mode = step.mode
            current_group.append(step.skill_name)

        if current_group:
            groups.append({"mode": current_mode.value, "skills": current_group})

        return groups
