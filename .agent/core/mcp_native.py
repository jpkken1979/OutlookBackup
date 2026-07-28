# mypy: ignore-errors
#!/usr/bin/env python3
"""
MCP Native - Exposicion nativa de agentes como herramientas MCP.

Permite que cualquier agente Antigravity sea automaticamente expuesto
como una herramienta MCP para uso en Claude Code, Cursor, etc.

Uso:
    from .agent.core.mcp_native import expose_agent_as_mcp

    # Exponer un agente
    mcp_tool = expose_agent_as_mcp(my_agent)

    # O usar el decorador
    @mcp_exportable
    class MyAgent(AntigravityAgent):
        ...
"""

from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from .agent_base import AntigravityAgent

logger = logging.getLogger("antigravity.core.mcp_native")


@dataclass
class MCPToolDefinition:
    """Definicion de herramienta MCP."""

    name: str
    description: str
    input_schema: dict
    agent_name: str
    capabilities: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_mcp_format(self) -> dict:
        """Convertir a formato MCP estandar."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": {
                "type": "object",
                "properties": {
                    "task": {"type": "string", "description": "La tarea a ejecutar"},
                    "context": {
                        "type": "object",
                        "description": "Contexto adicional opcional",
                        "default": {},
                    },
                },
                "required": ["task"],
            },
        }


@dataclass
class MCPToolResult:
    """Resultado de ejecucion de herramienta MCP."""

    tool_name: str
    success: bool
    output: Any
    error: str | None = None
    execution_time_ms: float = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)

    def to_mcp_format(self) -> dict:
        """Convertir a formato MCP estandar."""
        if self.success:
            return {
                "content": [
                    {
                        "type": "text",
                        "text": json.dumps(self.output, indent=2, default=str, ensure_ascii=False),
                    }
                ]
            }
        else:
            return {"content": [{"type": "text", "text": f"Error: {self.error}"}], "isError": True}


class MCPToolWrapper:
    """Wrapper para herramientas MCP."""

    def __init__(self, name: str, description: str, input_schema: dict):
        self.name = name
        self.description = description
        self.input_schema = input_schema


class MCPAgentWrapper:
    """
    Wrapper que expone un agente como herramienta MCP.

    Ejemplo:
        agent = SecurityAuditor(...)
        wrapper = MCPAgentWrapper(agent)

        # Obtener definicion de tool
        tool_def = wrapper.get_tool_definition()

        # Ejecutar como MCP tool
        result = await wrapper.execute({"task": "Audit security of src/"})
    """

    def __init__(self, agent: AntigravityAgent):
        self.agent = agent
        self._tool_def: MCPToolDefinition | None = None

    def get_tool_definition(self) -> MCPToolDefinition:
        """Generar definicion de herramienta MCP para el agente."""
        if self._tool_def:
            return self._tool_def

        identity = self.agent.identity

        self._tool_def = MCPToolDefinition(
            name=f"agent_{identity.name.replace('-', '_')}",
            description=f"{identity.role}: {identity.goal}",
            input_schema={
                "type": "object",
                "properties": {"task": {"type": "string"}, "context": {"type": "object"}},
                "required": ["task"],
            },
            agent_name=identity.name,
            capabilities=self.agent.capabilities.domains if self.agent.capabilities else [],
        )

        return self._tool_def

    async def execute(self, arguments: dict) -> MCPToolResult:
        """Ejecutar agente como herramienta MCP."""
        start_time = datetime.now()

        task = arguments.get("task", "")
        context = arguments.get("context", {})

        if not task:
            return MCPToolResult(
                tool_name=self.get_tool_definition().name,
                success=False,
                output=None,
                error="El parametro 'task' es requerido",
            )

        try:
            result = await self.agent.run(task, context)

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return MCPToolResult(
                tool_name=self.get_tool_definition().name,
                success=True,
                output=result,
                execution_time_ms=execution_time,
                metadata={
                    "agent": self.agent.identity.name,
                    "used_intelligence": self.agent.intelligence is not None,
                },
            )

        except Exception as e:
            logger.error(f"Error ejecutando agente {self.agent.identity.name}: {e}")

            execution_time = (datetime.now() - start_time).total_seconds() * 1000

            return MCPToolResult(
                tool_name=self.get_tool_definition().name,
                success=False,
                output=None,
                error=str(e),
                execution_time_ms=execution_time,
            )


class MCPAgentRegistry:
    """
    Registro central de agentes expuestos como MCP.

    Uso:
        registry = MCPAgentRegistry()
        registry.register(my_agent)

        # Listar herramientas
        tools = registry.list_tools()

        # Ejecutar herramienta
        result = await registry.execute("agent_explorer", {"task": "Find auth code"})
    """

    _instance: MCPAgentRegistry | None = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._wrappers = {}
        return cls._instance

    def register_agent(self, name: str, description: str, parameters: dict = None):
        """Metodo para compatibilidad con tests."""

        # Crear un dummy agent para el wrapper
        class DummyAgent:
            def __init__(self, name, role, goal):
                self.identity = type("obj", (object,), {"name": name, "role": role, "goal": goal})
                self.capabilities = type("obj", (object,), {"domains": []})
                self.intelligence = None

        agent = DummyAgent(name, "Agent", description)
        self.register(agent)

    def register(self, agent: AntigravityAgent) -> MCPToolDefinition:
        """Registrar un agente en el registry."""
        wrapper = MCPAgentWrapper(agent)
        tool_def = wrapper.get_tool_definition()

        self._wrappers[tool_def.name] = wrapper

        logger.info(f"Agente {agent.identity.name} registrado como MCP tool: {tool_def.name}")

        return tool_def

    def unregister(self, tool_name: str) -> bool:
        """Eliminar agente del registry."""
        if tool_name in self._wrappers:
            del self._wrappers[tool_name]
            return True
        return False

    def list_tools(self) -> list[MCPToolDefinition]:
        """Listar todas las herramientas disponibles."""
        return [w.get_tool_definition() for w in self._wrappers.values()]

    def get_tool(self, tool_name: str) -> MCPAgentWrapper | None:
        """Obtener wrapper de herramienta."""
        return self._wrappers.get(tool_name)

    async def execute(self, tool_name: str, arguments: dict) -> MCPToolResult:
        """Ejecutar una herramienta por nombre."""
        wrapper = self.get_tool(tool_name)

        if not wrapper:
            return MCPToolResult(
                tool_name=tool_name,
                success=False,
                output=None,
                error=f"Tool not found: {tool_name}",
            )

        return await wrapper.execute(arguments)

    def export_tools_manifest(self) -> dict:
        """Exportar manifiesto de herramientas en formato MCP."""
        return {"tools": [t.to_mcp_format() for t in self.list_tools()]}


# Singleton instance
_registry: MCPAgentRegistry | None = None


def get_mcp_registry() -> MCPAgentRegistry:
    """Obtener instancia del registry."""
    global _registry
    if _registry is None:
        _registry = MCPAgentRegistry()
    return _registry


def expose_agent_as_mcp(agent: AntigravityAgent) -> MCPToolDefinition:
    """
    Exponer un agente como herramienta MCP.

    Ejemplo:
        agent = MyAgent(...)
        tool = expose_agent_as_mcp(agent)
        print(f"Tool registrada: {tool.name}")
    """
    registry = get_mcp_registry()
    return registry.register(agent)


def mcp_exportable(cls):
    """
    Decorador que hace a una clase de agente exportable como MCP.

    Uso:
        @mcp_exportable
        class MyAgent(AntigravityAgent):
            ...

        agent = MyAgent(...)
        agent.expose_as_mcp()  # Metodo agregado automaticamente
    """

    original_init = cls.__init__

    @wraps(original_init)
    def new_init(self, *args, **kwargs):
        original_init(self, *args, **kwargs)
        self._mcp_exposed = False

    def expose_as_mcp(self) -> MCPToolDefinition:
        """Exponer este agente como herramienta MCP."""
        if not self._mcp_exposed:
            tool = expose_agent_as_mcp(self)
            self._mcp_exposed = True
            return tool
        return (
            get_mcp_registry()
            .get_tool(f"agent_{self.identity.name.replace('-', '_')}")
            .get_tool_definition()
        )

    cls.__init__ = new_init
    cls.expose_as_mcp = expose_as_mcp

    return cls


# =============================================================================
# MCP SERVER GENERATOR
# =============================================================================


def generate_mcp_server_code(agents: list[AntigravityAgent]) -> str:
    """
    Generar codigo de servidor MCP para un conjunto de agentes.

    Esto genera un archivo Python que puede ejecutarse como servidor MCP.
    """
    tool_defs = []
    for agent in agents:
        wrapper = MCPAgentWrapper(agent)
        tool_defs.append(wrapper.get_tool_definition())

    tools_json = json.dumps([t.to_mcp_format() for t in tool_defs], indent=2)

    code = f'''#!/usr/bin/env python3
"""
MCP Server generado automaticamente para agentes Antigravity.

Generado: {datetime.now().isoformat()}
Agentes: {len(agents)}
"""
import asyncio
import json
import sys
from typing import Any

# Tool definitions
TOOLS = {tools_json}


async def handle_request(request: dict) -> dict:
    """Manejar request MCP."""
    method = request.get("method", "")

    if method == "tools/list":
        return {{"tools": TOOLS}}

    elif method == "tools/call":
        tool_name = request.get("params", {{}}).get("name", "")
        arguments = request.get("params", {{}}).get("arguments", {{}})

        # Importar y ejecutar agente
        # (En produccion, cargar agentes dinamicamente)
        return {{
            "content": [
                {{"type": "text", "text": f"Executed {{tool_name}} with {{arguments}}"}}
            ]
        }}

    return {{"error": f"Unknown method: {{method}}"}}


async def main():
    """Entry point del servidor MCP."""
    # Leer requests de stdin, escribir responses a stdout
    for line in sys.stdin:
        try:
            request = json.loads(line)
            response = await handle_request(request)
            print(json.dumps(response))
            sys.stdout.flush()
        except Exception as e:
            print(json.dumps({{"error": str(e)}}))
            sys.stdout.flush()


if __name__ == "__main__":
    asyncio.run(main())
'''

    return code


# =============================================================================
# CLI
# =============================================================================


async def main():
    """CLI para testing."""
    import argparse

    parser = argparse.ArgumentParser(description="MCP Native utilities")
    parser.add_argument("--list", action="store_true", help="Listar tools registradas")
    parser.add_argument("--export", help="Exportar manifiesto a archivo")

    args = parser.parse_args()

    registry = get_mcp_registry()

    if args.list:
        tools = registry.list_tools()
        print(f"Tools registradas: {len(tools)}")
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")

    if args.export:
        manifest = registry.export_tools_manifest()
        Path(args.export).write_text(json.dumps(manifest, indent=2))
        print(f"Manifiesto exportado a {args.export}")


if __name__ == "__main__":
    asyncio.run(main())
