#!/usr/bin/env python3
"""jp skill - Orquestador autonomo inteligente."""

from __future__ import annotations

import argparse
import json
import logging
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Fix Windows Unicode
try:
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class Step:
    """Paso de un plan de ejecución."""

    id: int
    action: str
    description: str
    skill: Optional[str] = None
    agent: Optional[str] = None
    depends_on: list[int] = field(default_factory=list)
    parallel_group: str = "A"
    attempts: int = 0
    status: str = "pending"  # pending, running, success, error, skipped


@dataclass
class ExecutionResult:
    """Resultado de una ejecución de plan."""

    task: str
    start_time: str = ""
    end_time: str = ""
    steps: list[Step] = field(default_factory=list)
    status: str = "pending"  # pending, running, success, partial, aborted
    total_retries: int = 0
    errors: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "task": self.task,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "steps": [
                {
                    "id": s.id,
                    "action": s.action,
                    "description": s.description,
                    "skill": s.skill,
                    "agent": s.agent,
                    "depends_on": s.depends_on,
                    "parallel_group": s.parallel_group,
                    "status": s.status,
                }
                for s in self.steps
            ],
            "status": self.status,
            "total_retries": self.total_retries,
            "errors": self.errors,
        }


class JPOrchestrator:
    """Orquestador autónomo inteligente."""

    TASK_SKILLS = {
        "refactorizar": {
            "skills": ["code-simplifier", "sdd-apply"],
            "agents": ["code-reviewer", "Explore"],
        },
        "implementar": {
            "skills": ["scaffold-generator", "sdd-apply"],
            "agents": ["code-reviewer", "Explore", "test-engineer"],
        },
        "auditar": {
            "skills": ["auditoriajp"],
            "agents": ["security-reviewer", "code-reviewer"],
        },
        "testear": {
            "skills": ["test-fixing"],
            "agents": ["test-engineer", "code-reviewer"],
        },
        "documentar": {
            "skills": [],
            "agents": ["document-specialist", "writer"],
        },
        "migrar": {
            "skills": ["scaffold-generator"],
            "agents": ["Explore", "code-reviewer", "test-engineer"],
        },
        "correction": {
            "skills": ["test-fixing", "code-simplifier"],
            "agents": ["debugger", "code-reviewer"],
        },
        "build": {
            "skills": ["tauri-build"],
            "agents": ["code-reviewer"],
        },
    }

    def __init__(
        self,
        task: str,
        context: str = ".",
        max_parallel: int = 5,
        max_retries: int = 3,
        abort_threshold: float = 30.0,
        verbose: bool = False,
        auto_approve: bool = False,
    ) -> None:
        self.task = task
        self.context = context
        self.max_parallel = max_parallel
        self.max_retries = max_retries
        self.abort_threshold = abort_threshold
        self.verbose = verbose
        self.auto_approve = auto_approve
        self.result = ExecutionResult(task=task)
        self.result.start_time = datetime.now().isoformat()

    def analyze_task(self) -> dict[str, Any]:
        """Analiza el objetivo y detecta tipo de tarea."""
        task_lower = self.task.lower()

        # Detectar tipo de acción
        action = "implementar"
        for key in self.TASK_SKILLS.keys():
            if key in task_lower:
                action = key
                break

        # Detectar scope (archivos/rutas mencionadas)
        scope = [self.context]
        path_mentions = [w for w in task_lower.split() if "/" in w or w.endswith((".py", ".ts", ".tsx", ".rs"))]
        if path_mentions:
            scope.extend(path_mentions)

        # Detectar skill y agente necesarios
        resources = self.TASK_SKILLS.get(action, {"skills": [], "agents": ["Explore", "code-reviewer"]})

        return {
            "action": action,
            "scope": scope,
            "skills": resources["skills"],
            "agents": resources["agents"],
        }

    def generate_plan(self, analysis: dict[str, Any]) -> list[Step]:
        """Genera plan estructurado basado en el análisis."""
        steps: list[Step] = []
        step_id = 1

        action = analysis["action"]

        # Paso 1: Análisis inicial (Explore agent)
        steps.append(
            Step(
                id=step_id,
                action="analizar",
                description=f"Analizar estado actual del proyecto/task: {self.task}",
                agent="Explore",
                parallel_group="A",
            )
        )
        step_id += 1

        # Paso 2: Análisis de código existente
        if action in ["refactorizar", "implementar"]:
            steps.append(
                Step(
                    id=step_id,
                    action="code_review",
                    description="Revisión de código existente para entender estructura",
                    agent="code-reviewer",
                    depends_on=[step_id - 1],
                    parallel_group="B",
                )
            )
            step_id += 1

        # Paso 3: Detectar issues
        if action in ["refactorizar", "correction"]:
            steps.append(
                Step(
                    id=step_id,
                    action="detectar_issues",
                    description="Detectar issues, código duplicado, y deuda técnica",
                    agent="Explore",
                    depends_on=[step_id - 1],
                    parallel_group="B",
                )
            )
            step_id += 1

        # Paso 4: Implementar/Refactorizar
        if action in ["refactorizar", "implementar", "correction"]:
            steps.append(
                Step(
                    id=step_id,
                    action="implementar",
                    description=f"{action.capitalize()} según plan detectado",
                    skill="code-simplifier" if action == "refactorizar" else "scaffold-generator",
                    agent="code-reviewer",
                    depends_on=[step_id - 1],
                    parallel_group="C",
                )
            )
            step_id += 1

        # Paso 5: Tests
        if action in ["refactorizar", "implementar", "correction", "migrar"]:
            steps.append(
                Step(
                    id=step_id,
                    action="testear",
                    description="Verificar que todo funciona con tests",
                    skill="test-fixing",
                    agent="test-engineer",
                    depends_on=[step_id - 1],
                    parallel_group="D",
                )
            )
            step_id += 1

        # Paso 6: Documentación
        if action == "implementar":
            steps.append(
                Step(
                    id=step_id,
                    action="documentar",
                    description="Actualizar documentación",
                    agent="document-specialist",
                    depends_on=[step_id - 1],
                    parallel_group="E",
                )
            )
            step_id += 1

        # Para auditoría
        if action == "auditar":
            steps.append(
                Step(
                    id=step_id,
                    action="auditar",
                    description=f"Ejecutar auditoría completa de {analysis['scope']}",
                    skill="auditoriajp",
                    depends_on=[],
                    parallel_group="A",
                )
            )

        return steps

    def print_plan(self, steps: list[Step]) -> None:
        """Imprime el plan generado."""
        print("\n" + "=" * 70)
        print(f"PLAN: {self.task}")
        print("=" * 70)
        print("\n## Pasos\n")
        print("| # | Acción | Descripción | Skill/Agent | Depende | Grupo |")
        print("|---|--------|-------------|-------------|--------|-------|")
        for step in steps:
            deps = ", ".join(str(d) for d in step.depends_on) or "-"
            resource = step.skill or step.agent or "-"
            print(f"| {step.id} | {step.action} | {step.description[:40]}... | {resource} | {deps} | {step.parallel_group} |")

        # Agrupar por parallel group
        groups = {}
        for step in steps:
            if step.parallel_group not in groups:
                groups[step.parallel_group] = []
            groups[step.parallel_group].append(step)

        print("\n## Grupos de Ejecución Paralela")
        for group, group_steps in groups.items():
            step_ids = [s.id for s in group_steps]
            print(f"- **Grupo {group}**: Steps {step_ids} (ejecutan en paralelo)")

        print("\n" + "=" * 70)

    def execute_step(self, step: Step) -> dict[str, Any]:
        """Ejecuta un step individual usando execute_agent.py para agentes reales."""
        import shlex

        logger.info(f"[STEP {step.id}] Ejecutando: {step.action}")

        try:
            if step.skill:
                # Ejecutar skill via script directo
                skill_path = Path(self.context) / ".agent" / "skills-custom" / step.skill / "scripts" / "main.py"
                if not skill_path.exists():
                    # Buscar en skills base
                    skill_path = Path(self.context) / ".agent" / "skills" / step.skill / "scripts" / "main.py"

                if skill_path.exists():
                    cmd = f'python "{skill_path}" --task "{step.description}"'
                    logger.info("  → Ejecutando skill: %s", step.skill)
                    result = subprocess.run(
                        shlex.split(cmd),
                        shell=False,
                        capture_output=True,
                        text=True,
                        timeout=300,
                    )
                    return {
                        "status": "success" if result.returncode == 0 else "error",
                        "output": result.stdout[:500] if result.stdout else "",
                        "stderr": result.stderr[:200] if result.stderr else "",
                    }
                else:
                    logger.warning("  → Skill no encontrado: %s", step.skill)
                    return {"status": "skipped", "output": f"Skill {step.skill} no hallada"}

            elif step.agent:
                # Ejecutar agent via execute_agent.py (autonomous loop real)
                repo_root = Path(self.context).resolve()
                agent_script = repo_root / ".agent" / "scripts" / "execute_agent.py"

                if agent_script.exists():
                    cmd = f'python "{agent_script}" "{step.agent}" "{step.description}" --json'
                    logger.info("  → Ejecutando agent: %s", step.agent)
                    result = subprocess.run(
                        shlex.split(cmd),
                        shell=False,
                        capture_output=True,
                        text=True,
                        timeout=600,
                    )
                    if result.returncode == 0:
                        try:
                            output = json.loads(result.stdout)
                            return {
                                "status": "success" if output.get("success") else "error",
                                "output": str(output.get("result", ""))[:500],
                            }
                        except json.JSONDecodeError:
                            return {"status": "success", "output": result.stdout[:500]}
                    else:
                        return {"status": "error", "output": result.stderr[:200]}
                else:
                    logger.warning("  → execute_agent.py no encontrado")
                    return {"status": "skipped", "output": "execute_agent.py no disponible"}

            else:
                logger.warning("  → No hay skill/agent definido, marcando como skipped")
                return {"status": "skipped", "output": "Sin skill/agent"}

        except subprocess.TimeoutExpired:
            logger.error("  ⏱ Timeout en step %d", step.id)
            return {"status": "error", "output": "Timeout (10 min)"}
        except Exception as e:
            logger.error("  ❌ Error en step %d: %s", step.id, str(e))
            return {"status": "error", "output": str(e)}

    def run(self) -> int:
        """Ejecuta el flujo completo de JP orchestrator."""
        logger.info("JP Orchestrator iniciando...")
        logger.info("  Task: %s", self.task)
        logger.info("  Context: %s", self.context)

        # STEP 1: Analizar
        print("\n🔍 Analizando tarea...")
        analysis = self.analyze_task()
        print(f"  → Acción detectada: {analysis['action']}")
        print(f"  → Scope: {analysis['scope']}")
        print(f"  → Skills: {analysis['skills']}")
        print(f"  → Agents: {analysis['agents']}")

        # STEP 2: Generar plan
        print("\n📋 Generando plan...")
        steps = self.generate_plan(analysis)
        self.result.steps = steps
        self.print_plan(steps)

        # STEP 3: Approval gate
        if self.auto_approve:
            print("\n✅ Auto-aprobando plan (flag --yes)")
            approval = "y"
        else:
            print("\n⚠️  Approval required")
            approval = input("¿Procedo con el plan? (y/n): ").strip().lower()
            if approval not in ["y", "yes", "sí", "s"]:
                print("Plan cancelado por el usuario.")
            return 1

        # STEP 4: Ejecutar plan
        print("\n🚀 Ejecutando plan...")

        # Agrupar steps por parallel group
        groups: dict[str, list[Step]] = {}
        for step in steps:
            if step.parallel_group not in groups:
                groups[step.parallel_group] = []
            groups[step.parallel_group].append(step)

        # Ejecutar grupos en orden (A, B, C, D, E...)
        for group_name in sorted(groups.keys()):
            group_steps = groups[group_name]
            print(f"\n📦 Grupo {group_name}: Ejecutando {len(group_steps)} steps en paralelo...")

            with ThreadPoolExecutor(max_workers=self.max_parallel) as executor:
                futures = {executor.submit(self.execute_step, step): step for step in group_steps}

                for future in as_completed(futures):
                    step = futures[future]
                    try:
                        result = future.result()
                        step.status = result["status"]
                        print(f"  ✅ Step {step.id} ({step.action}): {result['status']}")
                    except Exception as e:
                        step.status = "error"
                        step.attempts += 1
                        self.result.errors.append(f"Step {step.id}: {str(e)}")
                        logger.error("  ❌ Step %d error: %s", step.id, str(e))

                        # Retry logic
                        if step.attempts < self.max_retries:
                            logger.info("  ↻ Retry %d/%d", step.attempts, self.max_retries)
                            self.result.total_retries += 1

                        # Check abort threshold
                        error_count = sum(1 for s in self.result.steps if s.status == "error")
                        total = len(self.result.steps)
                        if total > 0 and (error_count / total) * 100 >= self.abort_threshold:
                            logger.error("⛔ Abort threshold superado: %.1f%%", (error_count / total) * 100)
                            self.result.status = "aborted"
                            break

        # STEP 5: Resultado final
        self.result.end_time = datetime.now().isoformat()

        success_count = sum(1 for s in self.result.steps if s.status == "success")
        error_count = sum(1 for s in self.result.steps if s.status == "error")
        total = len(self.result.steps)

        if error_count == 0:
            self.result.status = "success"
        elif error_count < total:
            self.result.status = "partial"
        else:
            self.result.status = "aborted"

        # Guardar resultado
        result_file = Path(".claude/memory/jp_result.json")
        result_file.parent.mkdir(parents=True, exist_ok=True)
        result_file.write_text(json.dumps(self.result.to_dict(), indent=2, ensure_ascii=False))

        # Reporte final
        print("\n" + "=" * 70)
        print(f"RESULTADO: {self.task}")
        print("=" * 70)
        print(f"\n**Estado**: {self.result.status}")
        print(f"**Duración**: {self.result.start_time} → {self.result.end_time}")
        print(f"**Steps**: {success_count}/{total} exitosos")
        print(f"**Errores**: {error_count}/{total}")
        print(f"**Retries**: {self.result.total_retries}")

        print("\n## Resumen de Steps")
        print("| # | Acción | Status |")
        print("|---|--------|--------|")
        for step in self.result.steps:
            icon = {"success": "✅", "error": "❌", "running": "🔄", "pending": "⏳", "skipped": "⏭️"}[step.status]
            print(f"| {step.id} | {step.action} | {icon} |")

        if self.result.errors:
            print("\n## Errors")
            for err in self.result.errors:
                print(f"- {err}")

        print("\n" + "=" * 70)
        logger.info("[OK] Ejecución completada. Estado: %s", self.result.status)

        return 0 if self.result.status == "success" else 1


def main() -> int:
    """CLI principal."""
    parser = argparse.ArgumentParser(prog="jp")
    parser.add_argument("--task", help="Objetivo libre de la tarea")
    parser.add_argument("--context", default=".", help="Path del proyecto/contexto")
    parser.add_argument("--continue", dest="continue_task", action="store_true", help="Continuar tarea pendiente")
    parser.add_argument("--parallel", type=int, default=5, help="Máx subagentes en paralelo")
    parser.add_argument("--retry", type=int, default=3, help="Intentos max retry por paso")
    parser.add_argument("--abort-threshold", type=float, default=30.0, help="Threshold abort (%%)")
    parser.add_argument("--verbose", action="store_true", help="Output verbose")
    parser.add_argument("--yes", "-y", action="store_true", help="Auto-aprobar plan sin preguntar")

    args = parser.parse_args()

    if args.verbose:
        logger.setLevel(logging.DEBUG)

    # Check for continue mode
    if args.continue_task:
        result_file = Path(".claude/memory/jp_result.json")
        if result_file.exists():
            prev_result = json.loads(result_file.read_text())
            task = prev_result.get("task", "")
            logger.info("Continuando tarea previa: %s", task)
            # Reset status para re-ejecutar
        else:
            logger.error("No hay tarea previa para continuar")
            return 1
    elif args.task:
        task = args.task
    else:
        logger.error("Se requiere --task o --continue")
        return 1

    orchestrator = JPOrchestrator(
        task=task,
        context=args.context,
        max_parallel=args.parallel,
        max_retries=args.retry,
        abort_threshold=args.abort_threshold,
        verbose=args.verbose,
        auto_approve=args.yes,
    )

    return orchestrator.run()


if __name__ == "__main__":
    sys.exit(main())
