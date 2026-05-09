#!/usr/bin/env python3
"""
Agent Composer - Crea agentes compuestos dinámicamente
"""

import json
import argparse
from pathlib import Path
from dataclasses import dataclass, field
from typing import Any
from datetime import datetime
import sys


@dataclass
class AgentCapability:
    """Capacidad individual de un agente"""

    name: str
    description: str
    priority: int = 0
    source_agent: str = ""


@dataclass
class ComposedAgent:
    """Agente compuesto de múltiples agentes"""

    name: str
    components: list[str]
    capabilities: list[AgentCapability] = field(default_factory=list)
    created_at: str = ""
    priority_order: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


# Templates predefinidos
TEMPLATES = {
    "security-suite": {
        "name": "security-suite",
        "components": ["security-auditor", "penetration-tester", "compliance-auditor"],
        "description": "Suite completa de seguridad",
    },
    "full-stack": {
        "name": "full-stack-developer",
        "components": [
            "frontend-specialist",
            "backend-specialist",
            "api-designer",
            "database-architect",
        ],
        "description": "Desarrollador full-stack completo",
    },
    "quality-gate": {
        "name": "quality-gate",
        "components": [
            "code-reviewer",
            "test-engineer",
            "security-auditor",
            "performance-optimizer",
        ],
        "description": "Gate de calidad para PRs",
    },
    "release-manager": {
        "name": "release-manager",
        "components": [
            "git-orchestrator",
            "test-engineer",
            "devops-engineer",
            "documentation-writer",
        ],
        "description": "Gestor de releases",
    },
    "architect-suite": {
        "name": "architect-suite",
        "components": [
            "architect",
            "database-architect",
            "api-designer",
            "infrastructure-architect",
        ],
        "description": "Suite de arquitectura",
    },
    "ml-pipeline": {
        "name": "ml-pipeline",
        "components": ["ml-engineer", "data-engineer", "performance-optimizer", "cost-optimizer"],
        "description": "Pipeline de ML completo",
    },
    "documentation-suite": {
        "name": "documentation-suite",
        "components": ["documentation-writer", "api-designer", "docusaurus-expert"],
        "description": "Suite de documentación",
    },
    "testing-suite": {
        "name": "testing-suite",
        "components": ["test-engineer", "load-testing-engineer", "regression-detector", "a11y"],
        "description": "Suite completa de testing",
    },
}


class AgentComposer:
    """Compositor de agentes"""

    def __init__(self, agents_dir: Path = None):
        self.agents_dir = agents_dir or Path(".agent/agents")
        self.composed_dir = self.agents_dir / "_composed"
        self.composed_dir.mkdir(parents=True, exist_ok=True)

    def list_available_agents(self) -> list[str]:
        """Listar agentes disponibles para composición"""
        agents = []
        for agent_dir in self.agents_dir.iterdir():
            if agent_dir.is_dir() and not agent_dir.name.startswith("_"):
                identity_file = agent_dir / "IDENTITY.md"
                if identity_file.exists():
                    agents.append(agent_dir.name)
        return sorted(agents)

    def get_agent_capabilities(self, agent_name: str) -> list[AgentCapability]:
        """Extraer capacidades de un agente"""
        capabilities = []
        identity_file = self.agents_dir / agent_name / "IDENTITY.md"

        if not identity_file.exists():
            return capabilities

        try:
            content = identity_file.read_text()

            # Buscar sección de capacidades
            in_capabilities = False
            for line in content.split("\n"):
                if "## Capacidades" in line or "## Capabilities" in line:
                    in_capabilities = True
                    continue
                elif line.startswith("## ") and in_capabilities:
                    break
                elif in_capabilities and line.strip().startswith(("-", "*", "1.", "2.", "3.")):
                    # Extraer capacidad
                    cap_text = line.strip().lstrip("-*0123456789. ")
                    if cap_text:
                        # Separar nombre y descripción si hay **bold**
                        if "**" in cap_text:
                            parts = cap_text.split("**")
                            if len(parts) >= 2:
                                name = parts[1]
                                desc = parts[2].strip(" -:") if len(parts) > 2 else ""
                            else:
                                name = cap_text
                                desc = ""
                        else:
                            name = cap_text[:50]
                            desc = cap_text

                        capabilities.append(
                            AgentCapability(name=name, description=desc, source_agent=agent_name)
                        )

        except Exception:
            pass

        return capabilities

    def compose(
        self, name: str, components: list[str], priority_order: list[str] | None = None
    ) -> ComposedAgent:
        """Crear agente compuesto"""

        # Validar componentes
        available = self.list_available_agents()
        invalid = [c for c in components if c not in available]
        if invalid:
            raise ValueError(f"Agentes no encontrados: {invalid}")

        if len(components) > 5:
            raise ValueError("Máximo 5 agentes por composición")

        if len(components) < 2:
            raise ValueError("Mínimo 2 agentes para composición")

        # Recolectar capacidades
        all_capabilities = []
        for i, component in enumerate(components):
            caps = self.get_agent_capabilities(component)
            for cap in caps:
                cap.priority = len(components) - i  # Mayor prioridad a primeros
                all_capabilities.append(cap)

        # Crear agente compuesto
        composed = ComposedAgent(
            name=name,
            components=components,
            capabilities=all_capabilities,
            created_at=datetime.now().isoformat(),
            priority_order=priority_order or components,
        )

        # Guardar
        self._save_composed_agent(composed)

        return composed

    def compose_from_template(self, template_name: str) -> ComposedAgent:
        """Crear agente desde template predefinido"""
        if template_name not in TEMPLATES:
            raise ValueError(f"Template no encontrado: {template_name}")

        template = TEMPLATES[template_name]
        return self.compose(name=template["name"], components=template["components"])

    def _save_composed_agent(self, agent: ComposedAgent):
        """Guardar agente compuesto"""
        agent_dir = self.composed_dir / agent.name
        agent_dir.mkdir(parents=True, exist_ok=True)

        # Crear IDENTITY.md
        identity_content = f"""# {agent.name} (Composed Agent)

## Componentes

Este agente está compuesto por:

"""
        for comp in agent.components:
            identity_content += f"- **{comp}**\n"

        identity_content += """
## Capacidades Heredadas

"""
        for cap in agent.capabilities[:20]:  # Limitar a 20
            identity_content += f"- [{cap.source_agent}] {cap.name}\n"

        identity_content += f"""
## Orden de Prioridad

{" > ".join(agent.priority_order)}

## Metadata

- Creado: {agent.created_at}
- Componentes: {len(agent.components)}
- Capacidades: {len(agent.capabilities)}
"""

        (agent_dir / "IDENTITY.md").write_text(identity_content)

        # Crear script de ejecución
        script_dir = agent_dir / "scripts"
        script_dir.mkdir(exist_ok=True)

        script_content = f'''#!/usr/bin/env python3
"""
{agent.name} - Agente Compuesto
Componentes: {", ".join(agent.components)}
"""

import sys
import json
from pathlib import Path

COMPONENTS = {json.dumps(agent.components)}
PRIORITY = {json.dumps(agent.priority_order)}

def run_component(component: str, task: str):
    """Ejecutar un componente"""
    script_path = Path(f".agent/agents/{{component}}/scripts")

    # Buscar script ejecutable
    for script in script_path.glob("*.py"):
        if script.name != "__init__.py":
            import subprocess
            result = subprocess.run(
                [sys.executable, str(script), task],
                capture_output=True,
                text=True
            )
            return {{
                "component": component,
                "success": result.returncode == 0,
                "output": result.stdout,
                "error": result.stderr
            }}

    return {{"component": component, "success": False, "error": "No script found"}}


def main():
    if len(sys.argv) < 2:
        print(f"Uso: {{sys.argv[0]}} <tarea>")
        print(f"Componentes: {{', '.join(COMPONENTS)}}")
        sys.exit(1)

    task = " ".join(sys.argv[1:])
    results = []

    print(f"Ejecutando agente compuesto: {agent.name}")
    print(f"Tarea: {{task}}")
    print("-" * 50)

    for component in PRIORITY:
        print(f"\\n[{{component}}] Ejecutando...")
        result = run_component(component, task)
        results.append(result)

        if result["success"]:
            print(f"[{{component}}] ✓ Completado")
            if result["output"]:
                print(result["output"][:500])
        else:
            print(f"[{{component}}] ✗ Error: {{result.get('error', 'Unknown')}}")

    # Resumen
    successful = sum(1 for r in results if r["success"])
    print(f"\\n{{'='*50}}")
    print(f"Completado: {{successful}}/{{len(results)}} componentes")


if __name__ == "__main__":
    main()
'''
        (script_dir / f"{agent.name}.py").write_text(script_content)

        # Guardar metadata JSON
        metadata = {
            "name": agent.name,
            "components": agent.components,
            "created_at": agent.created_at,
            "priority_order": agent.priority_order,
            "capabilities_count": len(agent.capabilities),
        }
        (agent_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))

    def list_composed_agents(self) -> list[dict]:
        """Listar agentes compuestos existentes"""
        composed = []
        for agent_dir in self.composed_dir.iterdir():
            if agent_dir.is_dir():
                metadata_file = agent_dir / "metadata.json"
                if metadata_file.exists():
                    try:
                        metadata = json.loads(metadata_file.read_text())
                        composed.append(metadata)
                    except Exception:
                        pass
        return composed

    def run_composed(self, name: str, task: str) -> dict:
        """Ejecutar agente compuesto"""
        import subprocess

        script_path = self.composed_dir / name / "scripts" / f"{name}.py"
        if not script_path.exists():
            return {"success": False, "error": f"Agente {name} no encontrado"}

        result = subprocess.run(
            [sys.executable, str(script_path), task], capture_output=True, text=True
        )

        return {"success": result.returncode == 0, "output": result.stdout, "error": result.stderr}


def main():
    parser = argparse.ArgumentParser(description="Agent Composer - Crea agentes compuestos")
    subparsers = parser.add_subparsers(dest="command", help="Comando")

    # Comando create
    create_parser = subparsers.add_parser("create", help="Crear agente compuesto")
    create_parser.add_argument("--name", "-n", required=True, help="Nombre del agente")
    create_parser.add_argument(
        "--components", "-c", required=True, help="Componentes separados por coma"
    )

    # Comando template
    template_parser = subparsers.add_parser("template", help="Crear desde template")
    template_parser.add_argument("template_name", help="Nombre del template")

    # Comando list
    subparsers.add_parser("list", help="Listar agentes disponibles")

    # Comando templates
    subparsers.add_parser("templates", help="Listar templates disponibles")

    # Comando composed
    subparsers.add_parser("composed", help="Listar agentes compuestos")

    # Comando run
    run_parser = subparsers.add_parser("run", help="Ejecutar agente compuesto")
    run_parser.add_argument("agent_name", help="Nombre del agente")
    run_parser.add_argument("task", nargs="+", help="Tarea a ejecutar")

    # JSON output
    parser.add_argument("--json", action="store_true", help="Output en JSON")

    args = parser.parse_args()
    composer = AgentComposer()

    if args.command == "list":
        agents = composer.list_available_agents()
        if args.json:
            print(json.dumps(agents, indent=2))
        else:
            print(f"\n{len(agents)} agentes disponibles para composición:\n")
            for agent in agents:
                print(f"  • {agent}")

    elif args.command == "templates":
        if args.json:
            print(json.dumps(TEMPLATES, indent=2))
        else:
            print("\nTemplates disponibles:\n")
            for name, template in TEMPLATES.items():
                print(f"  {name}")
                print(f"    {template['description']}")
                print(f"    Componentes: {', '.join(template['components'])}\n")

    elif args.command == "composed":
        composed = composer.list_composed_agents()
        if args.json:
            print(json.dumps(composed, indent=2))
        else:
            if composed:
                print("\nAgentes compuestos:\n")
                for agent in composed:
                    print(f"  {agent['name']}")
                    print(f"    Componentes: {', '.join(agent['components'])}\n")
            else:
                print("No hay agentes compuestos aún")

    elif args.command == "create":
        components = [c.strip() for c in args.components.split(",")]
        try:
            agent = composer.compose(args.name, components)
            if args.json:
                print(
                    json.dumps(
                        {
                            "success": True,
                            "name": agent.name,
                            "components": agent.components,
                            "capabilities": len(agent.capabilities),
                        },
                        indent=2,
                    )
                )
            else:
                print(f"\n✓ Agente '{agent.name}' creado exitosamente")
                print(f"  Componentes: {', '.join(agent.components)}")
                print(f"  Capacidades: {len(agent.capabilities)}")
                print(
                    f"\n  Ejecutar: python .agent/agents/_composed/{agent.name}/scripts/{agent.name}.py <tarea>"
                )
        except ValueError as e:
            print(f"Error: {e}")

    elif args.command == "template":
        try:
            agent = composer.compose_from_template(args.template_name)
            print(f"\n✓ Agente '{agent.name}' creado desde template")
            print(f"  Componentes: {', '.join(agent.components)}")
        except ValueError as e:
            print(f"Error: {e}")

    elif args.command == "run":
        task = " ".join(args.task)
        result = composer.run_composed(args.agent_name, task)
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            if result["success"]:
                print(result["output"])
            else:
                print(f"Error: {result['error']}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
