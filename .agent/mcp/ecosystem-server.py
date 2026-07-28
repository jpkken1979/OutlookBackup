#!/usr/bin/env python3
"""
Antigravity Ecosystem MCP Server (Zero Dependencies)
=====================================================
Servidor MCP ligero que expone agentes, skills y búsqueda del ecosistema
usando SOLO la librería estándar de Python. Funciona sin mcp, pydantic,
ni ninguna dependencia externa.

Diseñado como fallback cuando el servidor principal (mcp-server/server.py)
no puede arrancar por falta de dependencias.

Tools:
- list_agents: Lista los 40 agentes operativos con descripción
- get_agent: Obtiene la identidad completa de un agente
- list_skills: Lista skills disponibles con filtro opcional
- read_skill: Lee el SKILL.md completo de una skill
- search_skills: Busca skills por keyword en nombre
- search_agents: Busca agentes por keyword en nombre o descripción
- invoke_agent: Genera el prompt completo para invocar un agente con tarea
- ecosystem_stats: Estadísticas del ecosistema
"""

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)

# NOTE: Rate limiting is enforced at the gateway level (gateway.py).
# Individual MCP servers do not implement their own rate limiting.

try:
    from .security_utils import is_within_root, validate_url_for_ssrf
except ImportError:
    from security_utils import is_within_root, validate_url_for_ssrf

BASE_DIR = Path(__file__).parent.parent.parent
SKILLS_DIR = BASE_DIR / ".agent" / "skills"
AGENTS_DIR = BASE_DIR / ".agent" / "agents"
WORKFLOWS_DIR = BASE_DIR / ".agent" / "workflows"

MAX_FILE_SIZE = 50_000


def _coerce_limit(raw_value: Any, default: int = 50, minimum: int = 1, maximum: int = 500) -> int:
    """Normaliza límites recibidos por el servidor zero-deps."""
    try:
        limit = int(raw_value)
    except (TypeError, ValueError):
        limit = default
    return max(minimum, min(limit, maximum))


def _read_safe(path: Path) -> str:
    """Lee un archivo de forma segura con límite de tamaño."""
    try:
        if not is_within_root(BASE_DIR, path):
            return "Error: ruta fuera del proyecto"
        content = path.read_text(encoding="utf-8", errors="replace")
        if len(content) > MAX_FILE_SIZE:
            return content[:MAX_FILE_SIZE] + "\n\n[... truncado ...]"
        return content
    except (OSError, UnicodeDecodeError) as e:
        logger.error("Error reading %s: %s", path, e)
        return "Error: no se pudo leer el recurso"


def _extract_description(path: Path) -> str:
    """Extrae descripción del frontmatter YAML o primera línea útil."""
    if not path.exists():
        return ""
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
        lines = content.split("\n")

        # Intentar frontmatter YAML
        if lines and lines[0].strip() == "---":
            for line in lines[1:]:
                if line.strip() == "---":
                    break
                if line.startswith("description:"):
                    return line.split(":", 1)[1].strip().strip("\"'")

        # Fallback: primera línea no-header, no-vacía
        for line in lines:
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and not stripped.startswith("---"):
                return stripped[:200]
    except (OSError, UnicodeDecodeError):
        pass
    return ""


def _discover_agents() -> list[dict[str, str]]:
    """Descubre todos los agentes disponibles."""
    agents = []
    if not AGENTS_DIR.exists():
        return agents
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
            continue
        identity = agent_dir / "IDENTITY.md"
        if identity.exists():
            agents.append(
                {
                    "name": agent_dir.name,
                    "description": _extract_description(identity) or f"Agente: {agent_dir.name}",
                }
            )
    return agents


def _discover_skills() -> list[str]:
    """Descubre todos los skills disponibles."""
    if not SKILLS_DIR.exists():
        return []
    return sorted(
        d.name
        for d in SKILLS_DIR.iterdir()
        if d.is_dir() and not d.name.startswith(".") and not d.name.startswith("_")
    )


# =========================================================================
# Tool handlers
# =========================================================================


def handle_list_agents(_args: dict[str, Any]) -> str:
    """Lista todos los agentes con sus descripciones."""
    agents = _discover_agents()
    lines = [f"Agentes del ecosistema Antigravity ({len(agents)}):\n"]
    for a in agents:
        lines.append(f"- **{a['name']}**: {a['description']}")
    return "\n".join(lines)


def handle_get_agent(args: dict[str, Any]) -> str:
    """Obtiene la identidad completa de un agente."""
    name = args.get("agent_name", "").strip()
    if not name:
        return "Error: se requiere agent_name"
    identity = AGENTS_DIR / name / "IDENTITY.md"
    if not identity.exists():
        available = [
            d.name for d in AGENTS_DIR.iterdir() if d.is_dir() and not d.name.startswith("_")
        ]
        close = [a for a in available if name.lower() in a.lower()]
        hint = f" Sugerencias: {close[:5]}" if close else ""
        return f"Agente '{name}' no encontrado.{hint}"
    return _read_safe(identity)


def handle_search_agents(args: dict[str, Any]) -> str:
    """Busca agentes por keyword."""
    query = args.get("query", "").lower().strip()
    if not query:
        return "Error: se requiere query"
    agents = _discover_agents()
    matches = [a for a in agents if query in a["name"].lower() or query in a["description"].lower()]
    if not matches:
        return f"Sin resultados para '{query}'. Hay {len(agents)} agentes disponibles."
    lines = [f"Agentes que coinciden con '{query}' ({len(matches)}):\n"]
    for a in matches:
        lines.append(f"- **{a['name']}**: {a['description']}")
    return "\n".join(lines)


def handle_list_skills(args: dict[str, Any]) -> str:
    """Lista skills con filtro opcional."""
    category = args.get("category", "").lower()
    limit = _coerce_limit(args.get("limit", 100), default=100)
    skills = _discover_skills()
    if category:
        skills = [s for s in skills if category in s.lower()]
    display = skills[:limit]
    result = f"Skills del ecosistema ({len(skills)} encontrados, mostrando {len(display)}):\n\n"
    result += "\n".join(f"- {s}" for s in display)
    if len(skills) > limit:
        result += f"\n\n... y {len(skills) - limit} más."
    return result


def handle_read_skill(args: dict[str, Any]) -> str:
    """Lee el SKILL.md completo de una skill."""
    name = args.get("skill_name", "").strip()
    if not name:
        return "Error: se requiere skill_name"
    skill_md = SKILLS_DIR / name / "SKILL.md"
    if not skill_md.exists():
        close = [s for s in _discover_skills() if name.lower() in s.lower()][:5]
        hint = f" Sugerencias: {close}" if close else ""
        return f"Skill '{name}' no encontrada.{hint}"
    return _read_safe(skill_md)


def handle_search_skills(args: dict[str, Any]) -> str:
    """Busca skills por keyword."""
    query = args.get("query", "").lower().strip()
    limit = _coerce_limit(args.get("limit", 50))
    if not query:
        return "Error: se requiere query"
    skills = _discover_skills()
    matches = [s for s in skills if query in s.lower()]
    if not matches:
        return f"Sin resultados para '{query}'. Hay {len(skills)} skills disponibles."
    display = matches[:limit]
    result = f"Skills que coinciden con '{query}' ({len(matches)} encontrados, mostrando {len(display)}):\n\n"
    result += "\n".join(f"- {s}" for s in display)
    if len(matches) > limit:
        result += f"\n\n... y {len(matches) - limit} más."
    return result


def handle_invoke_agent(args: dict[str, Any]) -> str:
    """Genera el prompt completo para invocar un agente con una tarea."""
    name = args.get("agent_name", "").strip()
    task = args.get("task", "").strip()
    if not name:
        return "Error: se requiere agent_name"
    if not task:
        return "Error: se requiere task"
    identity = AGENTS_DIR / name / "IDENTITY.md"
    if not identity.exists():
        return f"Agente '{name}' no encontrado."
    content = _read_safe(identity)
    return f"""## INVOCACIÓN DE AGENTE: {name.upper()}

### Instrucciones del Agente
{content}

---

### TAREA ASIGNADA
{task}

---

### INSTRUCCIONES DE EJECUCIÓN
1. Lee y comprende completamente las instrucciones del agente arriba
2. Adopta la personalidad y enfoque descrito
3. Ejecuta la tarea siguiendo el proceso definido por el agente
4. Produce el output en el formato especificado por el agente
"""


def handle_ecosystem_stats(_args: dict[str, Any]) -> str:
    """Estadísticas del ecosistema."""
    agents = _discover_agents()
    skills = _discover_skills()
    workflows = list(WORKFLOWS_DIR.glob("*.md")) if WORKFLOWS_DIR.exists() else []
    stats = {
        "version": "2.1.0",
        "agentes": len(agents),
        "skills": len(skills),
        "workflows": len(workflows),
        "server": "ecosystem-server (zero-deps)",
        "pid": os.getpid(),
    }
    return json.dumps(stats, indent=2, ensure_ascii=False)


def _check_http_server(name: str, transport: str, url: str, config: dict[str, Any]) -> str:
    """Verifica la salud de un servidor MCP HTTP.

    Args:
        name: Nombre del servidor en la configuración.
        transport: Tipo de transporte (`http` o `url`).
        url: URL base del servidor.
        config: Configuración del servidor (headers, etc.).

    Returns:
        Línea de estado con emoji descriptivo del resultado.
    """
    import urllib.error
    import urllib.request

    health_url = url.replace("/mcp", "/health")
    # SSRF: validar URL antes de hacer request
    valid, reason = validate_url_for_ssrf(health_url)
    if not valid:
        return f"🚫 {name} ({transport}): SSRF bloqueado - {reason}"
    try:
        req = urllib.request.Request(health_url, method="GET")
        headers = config.get("headers", {})
        for k, v in headers.items():
            # Expandir env vars
            if "${" in str(v):
                import re

                v = re.sub(
                    r"\$\{(\w+)\}",
                    lambda m: os.environ.get(m.group(1), ""),
                    v,
                )
            req.add_header(k, v)
        resp = urllib.request.urlopen(req, timeout=10)
        return f"✅ {name} ({transport}): HTTP {resp.status} - healthy"
    except urllib.error.HTTPError as e:
        return f"⚠️ {name} ({transport}): HTTP {e.code} - {e.reason}"
    except urllib.error.URLError as e:
        reason = str(e.reason)
        if "host_not_allowed" in reason or "403" in reason:
            return f"🚫 {name} ({transport}): Blocked by proxy"
        if "timed out" in reason:
            return f"⏱️ {name} ({transport}): Connection timeout"
        return f"❌ {name} ({transport}): {reason}"
    except Exception as e:
        return f"❌ {name} ({transport}): {e}"


def _check_stdio_server(name: str, config: dict[str, Any]) -> str | None:
    """Verifica la disponibilidad de un servidor MCP stdio.

    Args:
        name: Nombre del servidor en la configuración.
        config: Configuración del servidor (command, args).

    Returns:
        Línea de estado, o `None` si no hay command que verificar.
    """
    cmd = config.get("command", "")
    args = config.get("args", [])
    if cmd in ("python", "python3") and args:
        script = BASE_DIR / args[0]
        if script.exists():
            return f"✅ {name} (stdio): Script exists"
        return f"❌ {name} (stdio): Script not found: {args[0]}"
    if cmd:
        import shutil

        if shutil.which(cmd):
            return f"✅ {name} (stdio): Command available"
        return f"❌ {name} (stdio): Command not found: {cmd}"
    return None


def handle_connection_health(_args: dict[str, Any]) -> str:
    """Verifica la salud de las conexiones MCP configuradas."""
    mcp_json = BASE_DIR / ".mcp.json"
    if not mcp_json.exists():
        return "No .mcp.json found"

    try:
        data = json.loads(mcp_json.read_text(encoding="utf-8"))
    except Exception as e:
        logger.error("Error reading .mcp.json: %s", e)
        return "Error: no se pudo leer la configuración MCP"

    servers = data.get("mcpServers", {})
    results = []

    for name, config in servers.items():
        transport = config.get("type", "stdio")
        url = config.get("url", "")

        if transport in ("http", "url") and url:
            results.append(_check_http_server(name, transport, url, config))
        else:
            stdio_result = _check_stdio_server(name, config)
            if stdio_result is not None:
                results.append(stdio_result)

    header = f"Estado de conexiones MCP ({len(servers)} servidores):\n"
    return header + "\n".join(results)


# =========================================================================
# Knowledge Base — memorias absorbidas por Nexus
# =========================================================================


def _get_knowledge_dir() -> Path:
    """Encuentra el directorio de knowledge de Nexus."""
    # Windows: %APPDATA%/com.antigravity.nexus/knowledge
    # Linux: ~/.local/share/com.antigravity.nexus/knowledge
    # macOS: ~/Library/Application Support/com.antigravity.nexus/knowledge
    if sys.platform == "win32":
        app_data = os.environ.get("APPDATA", "")
        knowledge_dir = Path(app_data) / "com.antigravity.nexus" / "knowledge"
    elif sys.platform == "darwin":
        knowledge_dir = (
            Path.home() / "Library" / "Application Support" / "com.antigravity.nexus" / "knowledge"
        )
    else:
        knowledge_dir = Path.home() / ".local" / "share" / "com.antigravity.nexus" / "knowledge"
    return knowledge_dir


def _load_knowledge_manifest() -> dict[str, Any]:
    """Carga el manifest de knowledge absorbido."""
    knowledge_dir = _get_knowledge_dir()
    manifest_path = knowledge_dir / "manifest.json"
    if manifest_path.exists():
        try:
            return json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception:
            return {"projects": {}}
    return {"projects": {}}


def _grep_knowledge_file(
    file_path: Path, project_name: str, fname: str, query: str, limit: int
) -> list[str]:
    """Busca `query` en las líneas de un archivo de knowledge base.

    Args:
        file_path: Ruta del archivo.
        project_name: Nombre del proyecto (para el prefijo del match).
        fname: Nombre del archivo (para el prefijo del match).
        query: Texto a buscar (ya en minúsculas).
        limit: Máximo de coincidencias a devolver.

    Returns:
        Lista de líneas formateadas "[proyecto/archivo:N] texto" (hasta `limit`).
    """
    try:
        content = file_path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return []
    matches: list[str] = []
    for line_num, line in enumerate(content.splitlines(), 1):
        if query in line.lower():
            matches.append(f"[{project_name}/{fname}:{line_num}] {line.strip()}")
            if len(matches) >= limit:
                break
    return matches


def handle_search_knowledge(args: dict[str, Any]) -> str:
    """Busca en toda la knowledge base absorbida por Nexus."""
    query = args.get("query", "").lower().strip()
    if len(query) < 2:
        return "Error: query debe tener al menos 2 caracteres"

    knowledge_dir = _get_knowledge_dir()
    manifest = _load_knowledge_manifest()
    results: list[str] = []
    max_results = int(args.get("limit", 20))

    for project_name, pm in manifest.get("projects", {}).items():
        for fname in pm.get("files", {}):
            file_path = knowledge_dir / project_name / fname
            if file_path.exists():
                results.extend(
                    _grep_knowledge_file(
                        file_path, project_name, fname, query, max_results - len(results)
                    )
                )
            if len(results) >= max_results:
                break
        if len(results) >= max_results:
            break

    if not results:
        return f"Sin resultados para '{query}' en la knowledge base"

    header = f"Resultados de '{query}' ({len(results)} coincidencias):\n\n"
    return header + "\n".join(results)


def handle_read_knowledge(args: dict[str, Any]) -> str:
    """Lee un archivo de memoria absorbido."""
    project = args.get("project", "")
    file_name = args.get("file_name", "")
    if not project or not file_name:
        return "Error: se requiere 'project' y 'file_name'"

    knowledge_dir = _get_knowledge_dir()
    file_path = knowledge_dir / project / file_name

    # Prevenir path traversal
    try:
        resolved = file_path.resolve()
        if not str(resolved).startswith(str(knowledge_dir.resolve())):
            return "Error: path traversal detectado"
    except Exception:
        return "Error: ruta inválida"

    if not file_path.exists():
        return f"Error: {project}/{file_name} no encontrado en knowledge base"

    content = file_path.read_text(encoding="utf-8", errors="replace")
    if len(content) > MAX_FILE_SIZE:
        return content[:MAX_FILE_SIZE] + "\n\n[... truncado ...]"
    return content


# ─────────────────────────────────────────────────────────────────
# Manager Tools (agent instances via orchestrator)
# ─────────────────────────────────────────────────────────────────


def handle_agent_use_tool(args: dict[str, Any]) -> str:
    """Execute a tool from an agent's tool_manager.

    NOTE: This is a stub. Full implementation requires agent runtime access
    via the orchestrator. Currently returns documentation.
    """
    agent_name = args.get("agent_name", "").strip()
    tool_name = args.get("tool_name", "").strip()
    kwargs = args.get("kwargs", {})

    if not agent_name:
        return "Error: agent_name required"
    if not tool_name:
        return "Error: tool_name required"

    return f"""STUB: Execute tool '{tool_name}' on agent '{agent_name}'

This tool requires runtime agent access. To use:
1. Ensure gateway is running: python start_gateway.py
2. Access via: http://localhost:4747/v1/agents/{agent_name}/tools/{tool_name}

Arguments passed: {json.dumps(kwargs)}

Full implementation: POST /v1/agents/<name>/tools/<tool_name> with kwargs"""


def handle_agent_remember(args: dict[str, Any]) -> str:
    """Store a value in an agent's memory_manager.

    NOTE: This is a stub. Full implementation requires agent runtime access
    via the orchestrator.
    """
    agent_name = args.get("agent_name", "").strip()
    key = args.get("key", "").strip()
    value = args.get("value", "")

    if not agent_name:
        return "Error: agent_name required"
    if not key:
        return "Error: key required"

    return f"""STUB: Remember key='{key}' for agent '{agent_name}'

To store memory:
1. Ensure gateway is running: python start_gateway.py
2. Access via: POST /v1/agents/{agent_name}/memory/remember
3. Body: {{"key": "{key}", "value": {json.dumps(value)}}}"""


def handle_agent_recall(args: dict[str, Any]) -> str:
    """Retrieve a value from an agent's memory_manager.

    NOTE: This is a stub. Full implementation requires agent runtime access
    via the orchestrator.
    """
    agent_name = args.get("agent_name", "").strip()
    key = args.get("key", "").strip()

    if not agent_name:
        return "Error: agent_name required"
    if not key:
        return "Error: key required"

    return f"""STUB: Recall key='{key}' from agent '{agent_name}'

To retrieve memory:
1. Ensure gateway is running: python start_gateway.py
2. Access via: GET /v1/agents/{agent_name}/memory/recall?key={key}"""


def handle_agent_get_context(args: dict[str, Any]) -> str:
    """Search an agent's memory for relevant context.

    NOTE: This is a stub. Full implementation requires agent runtime access
    via the orchestrator with vector search capabilities.
    """
    agent_name = args.get("agent_name", "").strip()
    query = args.get("query", "").strip()
    limit = _coerce_limit(args.get("limit", 5), default=5, minimum=1, maximum=20)

    if not agent_name:
        return "Error: agent_name required"
    if not query:
        return "Error: query required"

    return f"""STUB: Get context for query='{query}' from agent '{agent_name}' (limit={limit})

To retrieve context:
1. Ensure gateway is running: python start_gateway.py
2. Access via: GET /v1/agents/{agent_name}/memory/context?query={query}&limit={limit}
3. Requires mem0 integration for vector search"""


def handle_list_knowledge(args: dict[str, Any]) -> str:
    """Lista los proyectos y memorias absorbidas."""
    manifest = _load_knowledge_manifest()
    projects = manifest.get("projects", {})
    if not projects:
        return "No hay memorias absorbidas. Usa Nexus > Memoria > Knowledge Absorber para absorber."

    lines: list[str] = []
    total_files = 0
    for project_name, pm in sorted(projects.items()):
        files = pm.get("files", {})
        total_files += len(files)
        updated = pm.get("updated_at", "?")
        lines.append(f"\n## {project_name} ({len(files)} memorias, sync: {updated[:10]})")
        for fname, finfo in sorted(files.items()):
            size = finfo.get("size", 0)
            lines.append(f"  - {fname} ({size} bytes)")

    header = f"Knowledge Base: {len(projects)} proyectos, {total_files} memorias\n"
    return header + "\n".join(lines)


# =========================================================================
# MCP Protocol (JSONRPC over stdio)
# =========================================================================

TOOLS = [
    {
        "name": "list_agents",
        "description": "Lista los 40 agentes operativos del ecosistema con descripciones",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "get_agent",
        "description": "Obtiene la identidad completa (IDENTITY.md) de un agente específico",
        "inputSchema": {
            "type": "object",
            "properties": {"agent_name": {"type": "string", "description": "Nombre del agente"}},
            "required": ["agent_name"],
        },
    },
    {
        "name": "search_agents",
        "description": "Busca agentes por keyword en nombre o descripción",
        "inputSchema": {
            "type": "object",
            "properties": {"query": {"type": "string", "description": "Término de búsqueda"}},
            "required": ["query"],
        },
    },
    {
        "name": "list_skills",
        "description": "Lista skills disponibles (791+) con filtro opcional por categoría",
        "inputSchema": {
            "type": "object",
            "properties": {
                "category": {"type": "string", "description": "Filtro por categoría (parcial)"},
                "limit": {"type": "integer", "description": "Máximo de resultados (default 100)"},
            },
        },
    },
    {
        "name": "read_skill",
        "description": "Lee las instrucciones completas (SKILL.md) de una skill específica",
        "inputSchema": {
            "type": "object",
            "properties": {
                "skill_name": {"type": "string", "description": "Nombre exacto de la skill"}
            },
            "required": ["skill_name"],
        },
    },
    {
        "name": "search_skills",
        "description": "Busca skills por keyword en el nombre",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Término de búsqueda"},
                "limit": {"type": "integer", "description": "Máximo de resultados (default 50)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "invoke_agent",
        "description": "Genera el prompt completo para invocar un agente especialista con una tarea",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Nombre del agente"},
                "task": {"type": "string", "description": "Descripción de la tarea"},
            },
            "required": ["agent_name", "task"],
        },
    },
    {
        "name": "ecosystem_stats",
        "description": "Devuelve estadísticas del ecosistema (agentes, skills, workflows)",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "connection_health",
        "description": "Verifica la salud de todas las conexiones MCP (locales y remotas)",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "search_knowledge",
        "description": "Busca en la knowledge base absorbida por Nexus. Contiene memorias de TODOS los proyectos Claude Code del usuario (feedback, decisiones, contexto de proyecto, preferencias). Usa esto para encontrar conocimiento previo relevante.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Texto a buscar en la knowledge base"},
                "limit": {"type": "integer", "description": "Máximo de resultados (default: 20)"},
            },
            "required": ["query"],
        },
    },
    {
        "name": "read_knowledge",
        "description": "Lee una memoria específica de la knowledge base absorbida. Útil para obtener contexto completo de un archivo encontrado con search_knowledge.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "project": {"type": "string", "description": "Nombre del proyecto"},
                "file_name": {"type": "string", "description": "Nombre del archivo .md"},
            },
            "required": ["project", "file_name"],
        },
    },
    {
        "name": "list_knowledge",
        "description": "Lista todos los proyectos y memorias absorbidas en la knowledge base de Nexus.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "agent_use_tool",
        "description": "Execute a tool from an agent's tool_manager (read_file, write_file, search_codebase, execute_command, or custom)",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Name of the agent"},
                "tool_name": {"type": "string", "description": "Name of the tool to execute"},
                "kwargs": {"type": "object", "description": "Tool arguments"},
            },
            "required": ["agent_name", "tool_name"],
        },
    },
    {
        "name": "agent_remember",
        "description": "Store a key-value pair in an agent's memory via memory_manager",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Name of the agent"},
                "key": {"type": "string", "description": "Memory key"},
                "value": {"description": "Value to store (any JSON-serializable type)"},
            },
            "required": ["agent_name", "key", "value"],
        },
    },
    {
        "name": "agent_recall",
        "description": "Retrieve a value from an agent's memory via memory_manager",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Name of the agent"},
                "key": {"type": "string", "description": "Memory key to retrieve"},
            },
            "required": ["agent_name", "key"],
        },
    },
    {
        "name": "agent_get_context",
        "description": "Search an agent's memory for relevant context using semantic similarity",
        "inputSchema": {
            "type": "object",
            "properties": {
                "agent_name": {"type": "string", "description": "Name of the agent"},
                "query": {"type": "string", "description": "Search query"},
                "limit": {"type": "integer", "description": "Max results (default 5, max 20)"},
            },
            "required": ["agent_name", "query"],
        },
    },
]

TOOL_HANDLERS = {
    "list_agents": handle_list_agents,
    "get_agent": handle_get_agent,
    "search_agents": handle_search_agents,
    "list_skills": handle_list_skills,
    "read_skill": handle_read_skill,
    "search_skills": handle_search_skills,
    "invoke_agent": handle_invoke_agent,
    "ecosystem_stats": handle_ecosystem_stats,
    "connection_health": handle_connection_health,
    "search_knowledge": handle_search_knowledge,
    "read_knowledge": handle_read_knowledge,
    "list_knowledge": handle_list_knowledge,
    "agent_use_tool": handle_agent_use_tool,
    "agent_remember": handle_agent_remember,
    "agent_recall": handle_agent_recall,
    "agent_get_context": handle_agent_get_context,
}


def handle_request(request: dict[str, Any]) -> dict[str, Any]:
    """Procesa una solicitud JSONRPC MCP."""
    method = request.get("method", "")
    params = request.get("params", {})
    request_id = request.get("id")

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "antigravity-ecosystem",
                    "version": "2.1.0",
                },
            },
        }

    # Notifications don't get responses (JSON-RPC 2.0 spec)
    if method and method.startswith("notifications/"):
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": TOOLS}}

    if method == "tools/call":
        name = params.get("name", "")
        args = params.get("arguments", {})
        handler = TOOL_HANDLERS.get(name)
        if not handler:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"Tool desconocida: {name}"}],
                    "isError": True,
                },
            }
        try:
            result_text = handler(args)
        except Exception as e:
            logger.error("Error ejecutando tool '%s': %s", name, e)
            result_text = f"Error ejecutando {name}: operación fallida"
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": result_text}]},
        }

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


def main() -> None:
    """Bucle principal: lee JSONRPC por stdin, responde por stdout."""
    # Los pipes stdio en Windows heredan la codepage del locale (cp932 en JP),
    # pero el protocolo MCP habla UTF-8: sin esto, el JSON entrante con no-ASCII
    # llega con surrogates sueltos y la respuesta puede fallar al escribirse.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    _request_count = 0
    _error_count = 0
    sys.stderr.write(
        f"[ecosystem-server] Started (pid={os.getpid()}) "
        f"agents={len(_discover_agents())} skills={len(_discover_skills())}\n"
    )
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                sys.stderr.write("[ecosystem-server] stdin closed, shutting down\n")
                break
            stripped = line.strip()
            if not stripped:
                continue
            request = json.loads(stripped)
            _request_count += 1
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError as e:
            _error_count += 1
            sys.stderr.write(f"[ecosystem-server] JSON parse error: {e}\n")
            continue
        except KeyboardInterrupt:
            sys.stderr.write("[ecosystem-server] Interrupted, shutting down\n")
            break
        except BrokenPipeError:
            sys.stderr.write("[ecosystem-server] Broken pipe, shutting down\n")
            break
        except Exception as e:
            _error_count += 1
            sys.stderr.write(
                f"[ecosystem-server] Error (req #{_request_count}): {type(e).__name__}: {e}\n"
            )
            continue
    sys.stderr.write(
        f"[ecosystem-server] Shutdown: {_request_count} requests, {_error_count} errors\n"
    )


if __name__ == "__main__":
    main()
