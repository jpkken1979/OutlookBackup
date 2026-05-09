#!/usr/bin/env python3
"""
Antigravity Intelligent Orchestrator
=====================================
Orquestador inteligente que decide qué agentes invocar y en qué orden
basándose en el tipo de tarea.

Este orquestador implementa las siguientes estrategias:
1. Análisis de la tarea para clasificarla
2. Selección automática de agentes relevantes
3. Definición del orden de ejecución (secuencial/paralelo)
4. Invocación de agentes con contexto apropiado
5. Lectura de APP_KNOWLEDGE.md para contexto
6. Modo interactivo cuando se dice solo "orquesta"

Uso:
    python orchestrator.py "Descripción de la tarea"
    python orchestrator.py                              # Modo interactivo
    python orchestrator.py --strategy code-review src/auth.py
    python orchestrator.py --dry-run "Crear nueva feature"

Triggers:
    "orquesta" / "orquesta con todo" - Activa modo interactivo inteligente
"""

import argparse
import json
import re
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
import logging

CORE_DIR = Path(__file__).resolve().parents[1] / "core"
sys.path.insert(0, str(CORE_DIR))

from memory.unified_memory import get_unified_memory

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [ORCHESTRATOR] %(message)s", datefmt="%H:%M:%S"
)
logger = logging.getLogger(__name__)


class TaskType(Enum):
    """Tipos de tarea que el orquestador puede manejar."""

    NEW_FEATURE = "new_feature"
    BUG_FIX = "bug_fix"
    REFACTOR = "refactor"
    CODE_REVIEW = "code_review"
    SECURITY_AUDIT = "security_audit"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    API_DESIGN = "api_design"
    UI_UX = "ui_ux"
    MIGRATION = "migration"
    UNKNOWN = "unknown"


@dataclass
class ExecutionStep:
    """Un paso en el plan de ejecución."""

    agent: str
    action: str
    depends_on: list[str] = field(default_factory=list)
    parallel: bool = False
    optional: bool = False


@dataclass
class ExecutionPlan:
    """Plan completo de ejecución."""

    task_type: TaskType
    task_description: str
    steps: list[ExecutionStep]
    estimated_agents: int
    critical_path: list[str]
    notes: list[str] = field(default_factory=list)


@dataclass
class ProjectContext:
    """Contexto del proyecto extraído de APP_KNOWLEDGE.md y SESSION_LOG.md"""

    name: str = ""
    stack: str = ""
    framework: str = ""
    database: str = ""
    components: list[str] = field(default_factory=list)
    recent_tasks: list[str] = field(default_factory=list)
    pending_tasks: list[str] = field(default_factory=list)
    has_knowledge: bool = False


class ContextLoader:
    """Carga contexto del proyecto desde archivos .context/"""

    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.context_dir = base_path / ".context"
        self.memory_dir = base_path / ".agent" / "memory"
        self.unified_memory = get_unified_memory(self.memory_dir)

    def load(self) -> ProjectContext:
        """Carga todo el contexto disponible."""
        ctx = ProjectContext()

        # Cargar Shared Memory (JSON) vía UnifiedMemory
        if self.unified_memory and hasattr(self.unified_memory, "shared_memory"):
            data = self.unified_memory.shared_memory.export()
            overview = data.get("project_overview", {})
            if overview:
                ctx.name = overview.get("name", ctx.name)
                ctx.stack = overview.get("stack", ctx.stack)
                ctx.has_knowledge = True

            prefs = data.get("user_preferences", {})
            if prefs:
                ctx.has_knowledge = True

            history = data.get("session_history", [])
            for entry in history:
                if isinstance(entry, dict) and "task" in entry:
                    ctx.recent_tasks.append(entry["task"])

        # Cargar APP_KNOWLEDGE.md
        app_knowledge = self.context_dir / "APP_KNOWLEDGE.md"
        if app_knowledge.exists():
            ctx.has_knowledge = True
            content = app_knowledge.read_text(encoding="utf-8")
            ctx = self._parse_app_knowledge(content, ctx)

        # Cargar SESSION_LOG.md para tareas recientes
        session_log = self.context_dir / "SESSION_LOG.md"
        if session_log.exists():
            content = session_log.read_text(encoding="utf-8")
            ctx = self._parse_session_log(content, ctx)

        # Cargar PENDING_TASKS.md
        pending = self.context_dir / "PENDING_TASKS.md"
        if pending.exists():
            content = pending.read_text(encoding="utf-8")
            for match in re.finditer(r"- \[ \] (.+)", content):
                ctx.pending_tasks.append(match.group(1).strip())

        return ctx

    def _parse_app_knowledge(self, content: str, ctx: ProjectContext) -> ProjectContext:
        """Extrae información de APP_KNOWLEDGE.md"""
        # Nombre del proyecto
        name_match = re.search(r"^# (.+?) -", content, re.MULTILINE)
        if name_match:
            ctx.name = name_match.group(1).strip()

        # Stack
        stack_match = re.search(r"\*\*Stack\*\*:?\s*(.+)", content, re.IGNORECASE)
        if stack_match:
            ctx.stack = stack_match.group(1).strip()

        # Framework
        fw_match = re.search(r"\*\*Framework\*\*:?\s*(.+)", content, re.IGNORECASE)
        if fw_match:
            ctx.framework = fw_match.group(1).strip()

        # Database
        db_match = re.search(r"\*\*(?:Base de Datos|Database)\*\*:?\s*(.+)", content, re.IGNORECASE)
        if db_match:
            ctx.database = db_match.group(1).strip()

        return ctx

    def _parse_session_log(self, content: str, ctx: ProjectContext) -> ProjectContext:
        """Extrae tareas recientes de SESSION_LOG.md"""
        # Buscar las últimas sesiones
        sessions = re.findall(r"## Sesion (.+?)(?=## Sesion|$)", content, re.DOTALL)
        if sessions:
            # Última sesión
            last_session = sessions[-1]
            # Extraer tareas completadas
            for match in re.finditer(r"- \[x\] (.+)", last_session):
                ctx.recent_tasks.append(match.group(1).strip())
            # Extraer tareas pendientes
            for match in re.finditer(r"- \[ \] (.+)", last_session):
                if match.group(1).strip() not in ctx.pending_tasks:
                    ctx.pending_tasks.append(match.group(1).strip())

        return ctx


class TaskClassifier:
    """Clasifica tareas basándose en palabras clave."""

    PATTERNS = {
        TaskType.NEW_FEATURE: [
            r"\b(crear|añadir|implementar|agregar|nuevo|nueva|feature)\b",
            r"\b(create|add|implement|new|feature)\b",
        ],
        TaskType.BUG_FIX: [
            r"\b(bug|error|fix|arreglar|corregir|fallo|crash|broken)\b",
            r"\b(no funciona|doesn\'t work|not working)\b",
        ],
        TaskType.REFACTOR: [
            r"\b(refactor|refactorizar|mejorar|optimizar|limpiar|clean)\b",
            r"\b(reorganizar|restructure|simplify|simplificar)\b",
        ],
        TaskType.CODE_REVIEW: [
            r"\b(review|revisar|revisión|check|verificar)\b",
            r"\b(pull request|pr|merge)\b",
        ],
        TaskType.SECURITY_AUDIT: [
            r"\b(security|seguridad|vulnerabil|auth|token|password)\b",
            r"\b(owasp|xss|sql injection|csrf)\b",
        ],
        TaskType.PERFORMANCE: [
            r"\b(performance|rendimiento|lento|slow|optimiz|speed)\b",
            r"\b(cache|lazy|bundle|memory)\b",
        ],
        TaskType.DOCUMENTATION: [r"\b(document|documentar|readme|docs|comentar|api docs)\b"],
        TaskType.API_DESIGN: [r"\b(api|endpoint|rest|graphql|openapi|swagger)\b"],
        TaskType.UI_UX: [
            r"\b(ui|ux|diseño|design|interfaz|componente|estilos|css)\b",
            r"\b(responsive|mobile|accesib)\b",
        ],
        TaskType.MIGRATION: [r"\b(migra|upgrade|actualizar|version|legacy)\b"],
    }

    @classmethod
    def classify(cls, task: str) -> TaskType:
        """Clasifica una tarea basándose en su descripción."""
        task_lower = task.lower()

        scores = dict.fromkeys(TaskType, 0)

        for task_type, patterns in cls.PATTERNS.items():
            for pattern in patterns:
                matches = re.findall(pattern, task_lower, re.IGNORECASE)
                scores[task_type] += len(matches)

        # Encontrar el tipo con mayor score
        best_type = max(scores, key=scores.get)
        if scores[best_type] > 0:
            return best_type

        return TaskType.UNKNOWN


class StrategyBuilder:
    """Construye estrategias de ejecución basadas en el tipo de tarea."""

    # Mapeo de tipo de tarea a secuencia de agentes
    STRATEGIES = {
        TaskType.NEW_FEATURE: [
            ExecutionStep("memory", "Load project context"),
            ExecutionStep("explorer", "Analyze related existing code"),
            ExecutionStep("architect", "Design feature integration"),
            ExecutionStep("critic", "Validate approach before implementing"),
            ExecutionStep("security-auditor", "Verify security requirements", optional=True),
            ExecutionStep("react-specialist", "Implement UI components", optional=True),
            ExecutionStep("code-reviewer", "Review implemented code"),
            ExecutionStep("memory", "Save decisions made"),
        ],
        TaskType.BUG_FIX: [
            ExecutionStep("memory", "Check if bug was reported before"),
            ExecutionStep("explorer", "Locate related code"),
            ExecutionStep("debugger", "Analyze root cause"),
            ExecutionStep("critic", "Validate proposed solution"),
            ExecutionStep("code-reviewer", "Verify fix"),
            ExecutionStep("memory", "Document solution"),
        ],
        TaskType.REFACTOR: [
            ExecutionStep("memory", "Load decision history"),
            ExecutionStep("explorer", "Map code to refactor"),
            ExecutionStep("refactor", "Identify patterns to improve"),
            ExecutionStep("architect", "Validate structural changes"),
            ExecutionStep("critic", "Evaluate risks"),
            ExecutionStep("code-reviewer", "Verify refactoring"),
            ExecutionStep("memory", "Document changes"),
        ],
        TaskType.CODE_REVIEW: [
            ExecutionStep("explorer", "Understand code context"),
            ExecutionStep("critic", "Analyze approach and decisions"),
            ExecutionStep("security-auditor", "Verify security"),
            ExecutionStep("a11y", "Verify accessibility", optional=True),
            ExecutionStep("code-reviewer", "Complete review"),
        ],
        TaskType.SECURITY_AUDIT: [
            ExecutionStep("explorer", "Map attack surface"),
            ExecutionStep("security-auditor", "Complete audit"),
            ExecutionStep("dependency", "Verify dependencies"),
            ExecutionStep("critic", "Prioritize vulnerabilities"),
        ],
        TaskType.PERFORMANCE: [
            ExecutionStep("explorer", "Identify critical code"),
            ExecutionStep("performance-optimizer", "Analyze bottlenecks"),
            ExecutionStep("architect", "Evaluate architectural changes"),
            ExecutionStep("critic", "Validate optimizations"),
        ],
        TaskType.DOCUMENTATION: [
            ExecutionStep("explorer", "Understand code to document"),
            ExecutionStep("documentation-writer", "Create documentation"),
            ExecutionStep("code-reviewer", "Review accuracy"),
        ],
        TaskType.API_DESIGN: [
            ExecutionStep("memory", "Load project standards"),
            ExecutionStep("api-designer", "Design API contracts"),
            ExecutionStep("security-auditor", "Validate endpoint security"),
            ExecutionStep("critic", "Review design"),
            ExecutionStep("documentation-writer", "Document API"),
        ],
        TaskType.UI_UX: [
            ExecutionStep("explorer", "Analyze existing UI"),
            ExecutionStep("ui-ux-designer", "Evaluate and propose improvements"),
            ExecutionStep("a11y", "Audit accessibility"),
            ExecutionStep("react-specialist", "Implement changes", optional=True),
            ExecutionStep("code-reviewer", "Review implementation"),
        ],
        TaskType.MIGRATION: [
            ExecutionStep("memory", "Load project history"),
            ExecutionStep("explorer", "Map dependencies"),
            ExecutionStep("migrator", "Plan migration"),
            ExecutionStep("architect", "Validate compatibility"),
            ExecutionStep("critic", "Evaluate risks"),
            ExecutionStep("dependency", "Verify new dependencies"),
        ],
        TaskType.UNKNOWN: [
            ExecutionStep("planner", "Analyze task and create plan"),
            ExecutionStep("explorer", "Explore relevant code"),
            ExecutionStep("critic", "Validate approach"),
        ],
    }

    @classmethod
    def build_plan(cls, task_type: TaskType, task: str) -> ExecutionPlan:
        """Construye un plan de ejecución para el tipo de tarea."""
        steps = cls.STRATEGIES.get(task_type, cls.STRATEGIES[TaskType.UNKNOWN])

        # Filtrar pasos opcionales si no son necesarios
        # (En una implementación real, esto sería más inteligente)
        required_steps = [s for s in steps if not s.optional]

        # Construir critical path (agentes no opcionales)
        critical_path = [s.agent for s in required_steps]

        return ExecutionPlan(
            task_type=task_type,
            task_description=task,
            steps=steps,
            estimated_agents=len({s.agent for s in steps}),
            critical_path=critical_path,
            notes=[
                f"Tipo de tarea detectado: {task_type.value}",
                f"Agentes principales: {', '.join(critical_path[:3])}",
            ],
        )


class Orchestrator:
    """Orquestador principal del ecosistema Antigravity."""

    def __init__(self, base_path: Path | None = None):
        self.base_path = base_path or self._detect_base_path()
        self.agents_dir = self.base_path / ".agent" / "agents"
        self.classifier = TaskClassifier()
        self.strategy_builder = StrategyBuilder()
        self.context_loader = ContextLoader(self.base_path)
        self.context: ProjectContext | None = None

    def _detect_base_path(self) -> Path:
        """Detecta la ruta base del proyecto."""
        current = Path.cwd()
        for parent in [current] + list(current.parents):
            if (parent / ".agent").exists():
                return parent
        return current

    def load_context(self) -> ProjectContext:
        """Carga el contexto del proyecto."""
        if self.context is None:
            self.context = self.context_loader.load()
        return self.context

    def get_available_agents(self) -> list[str]:
        """Lista los agentes disponibles."""
        agents = []
        if self.agents_dir.exists():
            for agent_dir in self.agents_dir.iterdir():
                if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
                    identity = agent_dir / "IDENTITY.md"
                    if identity.exists():
                        agents.append(agent_dir.name)
        return sorted(agents)

    def interactive_mode(self) -> str:
        """Modo interactivo cuando se dice solo 'orquesta'."""
        ctx = self.load_context()
        agents = self.get_available_agents()

        output = []
        output.append("=" * 60)
        output.append("ORQUESTADOR INTELIGENTE - MODO INTERACTIVO")
        output.append("=" * 60)

        # Mostrar contexto del proyecto
        if ctx.has_knowledge:
            output.append(f"\n[PROYECTO] {ctx.name or self.base_path.name}")
            if ctx.stack:
                output.append(f"[STACK] {ctx.stack}")
            if ctx.framework:
                output.append(f"[FRAMEWORK] {ctx.framework}")
            if ctx.database:
                output.append(f"[DATABASE] {ctx.database}")
        else:
            output.append(f"\n[PROYECTO] {self.base_path.name}")
            output.append("[WARN] No existe APP_KNOWLEDGE.md")
            output.append("       Ejecuta 'entiende la app' primero para mejor contexto")

        # Tareas pendientes
        if ctx.pending_tasks:
            output.append(f"\n[PENDIENTES] {len(ctx.pending_tasks)} tareas:")
            for i, task in enumerate(ctx.pending_tasks[:5], 1):
                output.append(f"  {i}. {task}")
            if len(ctx.pending_tasks) > 5:
                output.append(f"  ... y {len(ctx.pending_tasks) - 5} mas")

        # Tareas recientes
        if ctx.recent_tasks:
            output.append("\n[RECIENTES] Ultima sesion:")
            for task in ctx.recent_tasks[:3]:
                output.append(f"  - {task}")

        # Agentes disponibles
        output.append(f"\n[AGENTES] {len(agents)} disponibles:")
        output.append(f"  {', '.join(agents[:10])}")
        if len(agents) > 10:
            output.append(f"  ... y {len(agents) - 10} mas")

        # Tipos de tarea soportados
        output.append("\n[TIPOS DE TAREA SOPORTADOS]")
        task_examples = {
            "NEW_FEATURE": "crear, agregar, implementar, nuevo",
            "BUG_FIX": "bug, error, fix, arreglar",
            "REFACTOR": "refactor, mejorar, optimizar",
            "CODE_REVIEW": "review, revisar, PR",
            "SECURITY_AUDIT": "security, vulnerabilidad, auth",
            "PERFORMANCE": "performance, lento, cache",
            "API_DESIGN": "api, endpoint, rest",
            "UI_UX": "ui, ux, diseno, componente",
            "MIGRATION": "migrar, upgrade, actualizar",
        }
        for task_type, keywords in task_examples.items():
            output.append(f"  {task_type}: {keywords}")

        output.append("\n" + "=" * 60)
        output.append("COMO USAR:")
        output.append("  1. Describe tu tarea: 'orquesta crear sistema de login'")
        output.append("  2. El orquestador detectara el tipo y asignara agentes")
        output.append("  3. Los agentes se ejecutaran en secuencia optima")

        if ctx.pending_tasks:
            output.append("\nSUGERENCIA:")
            output.append(f"  Tienes {len(ctx.pending_tasks)} tareas pendientes.")
            output.append(f"  Prueba: 'orquesta {ctx.pending_tasks[0]}'")

        output.append("=" * 60)

        return "\n".join(output)

    def analyze_task(self, task: str) -> dict:
        """Analiza una tarea y devuelve información sobre cómo ejecutarla."""
        task_type = self.classifier.classify(task)
        plan = self.strategy_builder.build_plan(task_type, task)

        return {
            "task": task,
            "task_type": task_type.value,
            "plan": {
                "steps": [
                    {"agent": step.agent, "action": step.action, "optional": step.optional}
                    for step in plan.steps
                ],
                "estimated_agents": plan.estimated_agents,
                "critical_path": plan.critical_path,
                "notes": plan.notes,
            },
        }

    def generate_execution_prompt(self, task: str) -> str:
        """Genera el prompt completo para ejecutar la tarea con agentes."""
        analysis = self.analyze_task(task)
        plan = analysis["plan"]

        prompt = f"""## PLAN DE EJECUCIÓN ORQUESTADO

### Tarea Original
{task}

### Tipo de Tarea Detectado
{analysis["task_type"]}

### Plan de Ejecución

"""
        for i, step in enumerate(plan["steps"], 1):
            optional_tag = " (opcional)" if step["optional"] else ""
            prompt += f"""#### Paso {i}: {step["agent"].upper()}{optional_tag}
**Acción:** {step["action"]}

Para ejecutar este paso, lee e internaliza las instrucciones de:
`.agent/agents/{step["agent"]}/IDENTITY.md`

---

"""

        prompt += f"""### Camino Crítico
{" → ".join(plan["critical_path"])}

### Notas
"""
        for note in plan["notes"]:
            prompt += f"- {note}\n"

        prompt += """
### Instrucciones de Ejecución
1. Ejecuta cada paso en orden
2. Si un paso falla, invoca el agente 'stuck' para escalar
3. Documenta decisiones importantes con el agente 'memory'
4. Los pasos opcionales pueden omitirse si no son relevantes

¡Comienza la ejecución!
"""
        return prompt


def main():
    parser = argparse.ArgumentParser(
        description="Orquestador inteligente de agentes Antigravity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python orchestrator.py                           # Modo interactivo
  python orchestrator.py "crear login"             # Ejecutar tarea
  python orchestrator.py --analyze "fix bug"       # Solo analizar
  python orchestrator.py --json "crear api"        # Output JSON

Triggers para IA:
  "orquesta"                  -> Modo interactivo
  "orquesta crear login"      -> Detecta NEW_FEATURE
  "orquesta fix bug"          -> Detecta BUG_FIX
  "orquesta con todo"         -> Modo interactivo + contexto
        """,
    )

    parser.add_argument(
        "task", nargs="*", help="Descripción de la tarea a ejecutar (o vacio para modo interactivo)"
    )
    parser.add_argument(
        "--analyze", "-a", action="store_true", help="Solo analiza la tarea sin generar prompt"
    )
    parser.add_argument("--dry-run", "-n", action="store_true", help="Muestra el plan sin ejecutar")
    parser.add_argument("--json", "-j", action="store_true", help="Output en formato JSON")
    parser.add_argument(
        "--worker",
        action="store_true",
        help="Ejecutar como worker persistente (modo daemon para Docker)",
    )
    parser.add_argument(
        "--context", "-c", action="store_true", help="Muestra contexto del proyecto"
    )

    args = parser.parse_args()

    # Modo daemon para Docker: proceso persistente que escucha stdin/señales
    if args.worker:
        import signal
        import time

        print("[orchestrator] Worker mode started. Waiting for tasks...", flush=True)
        stop = [False]
        signal.signal(signal.SIGTERM, lambda *_: stop.__setitem__(0, True))
        signal.signal(signal.SIGINT, lambda *_: stop.__setitem__(0, True))
        while not stop[0]:
            time.sleep(5)
        print("[orchestrator] Worker stopped.", flush=True)
        return 0

    orchestrator = Orchestrator()

    # Unir argumentos de tarea
    task = " ".join(args.task) if args.task else ""

    # Filtrar triggers especiales
    task_lower = task.lower().strip()
    if task_lower in ["", "con todo", "todo", "help", "ayuda"]:
        # Modo interactivo
        print(orchestrator.interactive_mode())
        return 0

    # Si solo es "orquesta" sin tarea real
    if task_lower in ["orquesta", "orchestrate"]:
        print(orchestrator.interactive_mode())
        return 0

    # Mostrar contexto si se pide
    if args.context:
        ctx = orchestrator.load_context()
        print("\n[CONTEXTO DEL PROYECTO]")
        print(f"  Nombre: {ctx.name or orchestrator.base_path.name}")
        print(f"  Stack: {ctx.stack or 'No detectado'}")
        print(f"  Framework: {ctx.framework or 'No detectado'}")
        print(f"  Database: {ctx.database or 'No detectada'}")
        print(f"  Tareas pendientes: {len(ctx.pending_tasks)}")
        print(f"  APP_KNOWLEDGE: {'Si' if ctx.has_knowledge else 'No'}")
        print()

    if args.analyze or args.dry_run:
        analysis = orchestrator.analyze_task(task)
        if args.json:
            print(json.dumps(analysis, indent=2, ensure_ascii=False))
        else:
            print("\n" + "=" * 60)
            print("ANALISIS DE TAREA")
            print("=" * 60)
            print(f"\nTarea: {analysis['task']}")
            print(f"Tipo: {analysis['task_type']}")
            print("\nPlan de ejecucion:")
            for i, step in enumerate(analysis["plan"]["steps"], 1):
                opt = " [opcional]" if step["optional"] else ""
                print(f"  {i}. [{step['agent']}] {step['action']}{opt}")
            print(f"\nCamino critico: {' -> '.join(analysis['plan']['critical_path'])}")
            print("=" * 60 + "\n")
    else:
        prompt = orchestrator.generate_execution_prompt(task)
        print(prompt)

    return 0


if __name__ == "__main__":
    sys.exit(main())
