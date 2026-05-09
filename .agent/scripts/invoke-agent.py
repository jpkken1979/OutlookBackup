#!/usr/bin/env python3
"""
Antigravity Agent Invoker
=========================
Script para invocar agentes especializados y pasarles contexto.

Uso:
    python invoke-agent.py <agent_name> [task_description]
    python invoke-agent.py --list
    python invoke-agent.py --help

Ejemplos:
    python invoke-agent.py planner "Crear API REST para usuarios"
    python invoke-agent.py critic "Revisar el código de auth.py"
    python invoke-agent.py explorer "Analizar dependencias de utils/"
"""

import argparse
import json
import sys
from pathlib import Path
from dataclasses import dataclass
import logging

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class Agent:
    """Representa un agente del ecosistema."""

    name: str
    description: str
    path: Path
    identity_content: str = ""

    def load_identity(self) -> str:
        """Carga el contenido de IDENTITY.md del agente."""
        identity_file = self.path / "IDENTITY.md"
        if identity_file.exists():
            self.identity_content = identity_file.read_text(encoding="utf-8")
        return self.identity_content


class AgentOrchestrator:
    """Orquestador central de agentes Antigravity."""

    def __init__(self, base_path: Path | None = None):
        """Inicializa el orquestador.

        Args:
            base_path: Ruta base del proyecto. Si es None, detecta automáticamente.
        """
        self.base_path = base_path or self._detect_base_path()
        self.agents_dir = self.base_path / ".agent" / "agents"
        self.agents: dict[str, Agent] = {}
        self._discover_agents()

    def _detect_base_path(self) -> Path:
        """Detecta la ruta base del proyecto buscando .agent/ o CLAUDE.md."""
        current = Path.cwd()

        # Buscar hacia arriba hasta encontrar .agent/ o CLAUDE.md
        for parent in [current] + list(current.parents):
            if (parent / ".agent").exists() or (parent / "CLAUDE.md").exists():
                return parent

        # Si no encuentra, usar directorio actual
        return current

    def _discover_agents(self) -> None:
        """Descubre todos los agentes disponibles en el directorio."""
        if not self.agents_dir.exists():
            logger.warning(f"Directorio de agentes no encontrado: {self.agents_dir}")
            return

        for agent_dir in self.agents_dir.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
                identity_file = agent_dir / "IDENTITY.md"
                if identity_file.exists():
                    # Extraer descripción del frontmatter
                    content = identity_file.read_text(encoding="utf-8")
                    description = self._extract_description(content)

                    self.agents[agent_dir.name] = Agent(
                        name=agent_dir.name, description=description, path=agent_dir
                    )

        logger.info(f"Descubiertos {len(self.agents)} agentes")

    def _extract_description(self, content: str) -> str:
        """Extrae la descripción del frontmatter YAML."""
        if content.startswith("---"):
            try:
                # Buscar el segundo ---
                end_idx = content.find("---", 3)
                if end_idx != -1:
                    frontmatter = content[3:end_idx]
                    for line in frontmatter.split("\n"):
                        if line.startswith("description:"):
                            return line.split(":", 1)[1].strip()
            except Exception:
                pass
        return "Sin descripción"

    def list_agents(self) -> list[dict]:
        """Lista todos los agentes disponibles."""
        return [
            {"name": agent.name, "description": agent.description, "path": str(agent.path)}
            for agent in sorted(self.agents.values(), key=lambda a: a.name)
        ]

    def get_agent(self, name: str) -> Agent | None:
        """Obtiene un agente por nombre."""
        return self.agents.get(name)

    def invoke_agent(self, name: str, task: str) -> dict:
        """Invoca un agente con una tarea específica.

        Args:
            name: Nombre del agente a invocar
            task: Descripción de la tarea

        Returns:
            Dict con el prompt construido para Claude
        """
        agent = self.get_agent(name)
        if not agent:
            available = ", ".join(sorted(self.agents.keys()))
            return {
                "success": False,
                "error": f"Agente '{name}' no encontrado. Disponibles: {available}",
            }

        # Cargar identidad del agente
        agent.load_identity()

        # Construir prompt
        prompt = self._build_agent_prompt(agent, task)

        return {
            "success": True,
            "agent": agent.name,
            "task": task,
            "prompt": prompt,
            "identity_path": str(agent.path / "IDENTITY.md"),
        }

    def _build_agent_prompt(self, agent: Agent, task: str) -> str:
        """Construye el prompt completo para invocar al agente."""
        base_prompt = f"""## INVOCACIÓN DE AGENTE: {agent.name.upper()}

### Instrucciones del Agente
{agent.identity_content}

---

### TAREA ASIGNADA
{task}

---

### INSTRUCCIONES DE EJECUCIÓN
1. Lee y comprende completamente las instrucciones del agente arriba
2. Adopta la personalidad y enfoque descrito
3. Ejecuta la tarea siguiendo el proceso definido por el agente
4. Produce el output en el formato especificado por el agente
5. Si encuentras problemas, invoca el agente 'stuck' para escalar
"""
        # Inject Ultra-Instinct if requested
        if "/ultra-instinct" in task.lower() or "/goku" in task.lower():
            skill_path = (
                self.base_path
                / ".agent"
                / "skills-custom"
                / "ultra-instinct-reasoning"
                / "SKILL.md"
            )
            if skill_path.exists():
                ui_content = skill_path.read_text(encoding="utf-8")
                base_prompt += f"\n\n### 🔥 OVERRIDE: ULTRA INSTINCT ACTIVADO 🔥\n{ui_content}\n\n"
            else:
                base_prompt += "\n\n### 🔥 OVERRIDE: ULTRA INSTINCT MODO ACTIVADO 🔥\nDEBES usar System-2 thinking, auto-corregirte, dudar y verificar 5 veces antes de terminar. Ejecuta en paralelo y NUNCA te rindas en el primer error de terminal.\n\n"

        base_prompt += (
            "IMPORTANTE: Actúa EXACTAMENTE como el agente descrito actuaría y resuelve la tarea."
        )
        return base_prompt

    def create_execution_plan(self, task: str) -> dict:
        """Crea un plan de ejecución usando el agente planner.

        Args:
            task: Descripción de la tarea a planificar

        Returns:
            Plan de ejecución con secuencia de agentes
        """
        planner = self.get_agent("planner")
        if not planner:
            return {"success": False, "error": "Agente 'planner' no encontrado"}

        # Invocar planner para crear plan
        result = self.invoke_agent(
            "planner",
            f"""
Analiza la siguiente tarea y crea un plan de ejecución:

TAREA: {task}

AGENTES DISPONIBLES:
{json.dumps(self.list_agents(), indent=2, ensure_ascii=False)}

Genera un plan detallado indicando qué agentes usar y en qué orden.
""",
        )

        return result


def print_agent_list(agents: list[dict]) -> None:
    """Imprime la lista de agentes de forma bonita."""
    print("\n" + "=" * 60)
    print("AGENTES ANTIGRAVITY DISPONIBLES")
    print("=" * 60 + "\n")

    for agent in agents:
        print(f"  📦 {agent['name']}")
        print(f"     {agent['description']}")
        print()

    print("=" * 60)
    print(f"Total: {len(agents)} agentes")
    print("=" * 60 + "\n")


def main():
    parser = argparse.ArgumentParser(
        description="Invocar agentes del ecosistema Antigravity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python invoke-agent.py planner "Crear sistema de autenticación"
  python invoke-agent.py critic "Revisar implementación de login"
  python invoke-agent.py --list
  python invoke-agent.py --plan "Migrar base de datos a PostgreSQL"
        """,
    )

    parser.add_argument("agent", nargs="?", help="Nombre del agente a invocar")
    parser.add_argument("task", nargs="?", default="", help="Descripción de la tarea")
    parser.add_argument(
        "--list", "-l", action="store_true", help="Lista todos los agentes disponibles"
    )
    parser.add_argument(
        "--plan", "-p", metavar="TASK", help="Crea un plan de ejecución para la tarea"
    )
    parser.add_argument("--json", "-j", action="store_true", help="Output en formato JSON")
    parser.add_argument("--base-path", "-b", type=Path, help="Ruta base del proyecto")

    args = parser.parse_args()

    # Inicializar orquestador
    orchestrator = AgentOrchestrator(args.base_path)

    # Listar agentes
    if args.list:
        agents = orchestrator.list_agents()
        if args.json:
            print(json.dumps(agents, indent=2, ensure_ascii=False))
        else:
            print_agent_list(agents)
        return 0

    # Crear plan de ejecución
    if args.plan:
        result = orchestrator.create_execution_plan(args.plan)
        if args.json:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            if result["success"]:
                print(result["prompt"])
            else:
                print(f"Error: {result['error']}", file=sys.stderr)
                return 1
        return 0

    # Invocar agente específico
    if not args.agent:
        parser.print_help()
        return 1

    result = orchestrator.invoke_agent(args.agent, args.task)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        if result["success"]:
            print(result["prompt"])
        else:
            print(f"Error: {result['error']}", file=sys.stderr)
            return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
