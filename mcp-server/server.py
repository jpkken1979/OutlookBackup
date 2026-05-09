#!/usr/bin/env python3
"""
Antigravity MCP Server v4.0 — Resources + Prompts + Sampling.

Mejoras sobre v3:
- MCP Resources: memoria, observaciones, catálogo de skills y agentes
- MCP Prompts: workflows reutilizables para cualquier IA
- MCP Sampling: razonamiento IA dentro del servidor (sin exponer API keys)
- Agent Card: describe el ecosistema a orquestadores externos
"""

import asyncio
import hashlib
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, ValidationError

try:
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.server.lowlevel.helper_types import ReadResourceContents
    from mcp.types import (
        # Herramientas
        TextContent,
        Tool,
        # Recursos
        Resource,
        ResourceContents,
        TextResourceContents,
        # Prompts
        Prompt,
        PromptArgument,
        PromptMessage,
        GetPromptResult,
    )
except ImportError:
    print(
        "Error: mcp library no instalada. Instalar con: pip install mcp>=1.8.0",
        file=sys.stderr,
    )
    sys.exit(1)

# Imports opcionales (pueden no existir en versiones nuevas del SDK)
try:
    from mcp.server.models import InitializationOptions
except ImportError:
    InitializationOptions = None  # type: ignore[assignment,misc]

try:
    from mcp.types import ServerCapabilities
except ImportError:
    ServerCapabilities = None  # type: ignore[assignment,misc]

# Sampling desactivado en MCP SDK actual — imports opcionales
try:
    from mcp.types import CreateMessageRequest, CreateMessageResult, SamplingMessage
except ImportError:
    CreateMessageRequest = None  # type: ignore[assignment,misc]
    CreateMessageResult = None  # type: ignore[assignment,misc]
    SamplingMessage = None  # type: ignore[assignment,misc]

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)

# Rutas del proyecto
PROJECT_ROOT = Path(__file__).parent.parent
SKILLS_DIR = PROJECT_ROOT / ".agent" / "skills"
AGENTS_DIR = PROJECT_ROOT / ".agent" / "agents"
WORKFLOWS_DIR = PROJECT_ROOT / ".agent" / "workflows"
LEGACY_COMMANDS_DIR = PROJECT_ROOT / ".antigravity" / "legacy" / "claude-commands"
CONTEXT_DIR = PROJECT_ROOT / ".context"
OBSERVATIONS_DIR = PROJECT_ROOT / ".antigravity" / "observations"

DEFAULT_SCRIPT_TIMEOUT_SECONDS = 60
GLOBAL_SKILL_TIMEOUT_SECONDS = 120
MAX_CONCURRENT_SKILLS = 5
_active_skill_executions = 0
SKILL_ARG_ALLOWLIST_DEFAULT = [
    r"^--?[a-zA-Z0-9][a-zA-Z0-9._-]*$",
    r"^[a-zA-Z0-9_.,=+-]+$",
]
DEFAULT_MEMORY_AGENT = "codex"
DEFAULT_MEMORY_BACKEND = "local"

# ---------------------------------------------------------------------------
# Backend de memoria unificado — delega a memory-server.py (ChromaDB)
# Patron reutilizado de .agent/mcp/gateway/_mixin_memory.py
# Fallback JSONL se mantiene como ultimo recurso si ChromaDB no esta disponible
# ---------------------------------------------------------------------------
_cached_memory_module: Any = None


def _get_memory_module() -> Any:
    """Carga y cachea el modulo memory-server.py (singleton).

    Importa memory-server.py como biblioteca para reutilizar el backend
    ChromaDB + sentence-transformers, evitando duplicar logica.

    Returns:
        El modulo cargado, o None si la carga falla.
    """
    global _cached_memory_module
    if _cached_memory_module is not None:
        return _cached_memory_module

    import importlib.util

    # Ruta relativa al memory-server.py del ecosistema
    mem_server_path = PROJECT_ROOT / ".agent" / "mcp" / "memory-server.py"
    if not mem_server_path.exists():
        logger.warning("memory-server.py no encontrado en %s", mem_server_path)
        return None

    try:
        spec = importlib.util.spec_from_file_location("_mem_srv_cached", mem_server_path)
        if spec is None or spec.loader is None:
            logger.error("No se pudo crear spec para memory-server.py")
            return None
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        _cached_memory_module = mod
        logger.info("memory-server.py cargado y cacheado — backend ChromaDB unificado")
        return mod
    except Exception as e:
        logger.warning("Error cargando memory-server.py: %s — se usara fallback JSONL", e)
        return None
DEFAULT_REGISTRY_TTL_SECONDS = 900
REGISTRY_CACHE_FILE = PROJECT_ROOT / ".agent" / "cache" / "skills-registry-cache.json"
TEAM_TRACE_FILE = PROJECT_ROOT / ".agent" / "logs" / "teams-traces.jsonl"


# =============================================================================
# Modelos de validación
# =============================================================================


class RunSkillRequest(BaseModel):
    """Entrada validada para run_skill."""

    skill_name: str = Field(min_length=1)
    args: str | None = None


class SearchSkillsRequest(BaseModel):
    """Entrada validada para search_skills."""

    query: str = Field(min_length=1)


class ComposeSkillsRequest(BaseModel):
    """Entrada validada para compose_skills."""

    task: str = Field(min_length=1, description="Tarea de alto nivel a resolver")
    max_skills: int = Field(default=5, ge=1, le=10)


class MemoryStoreRequest(BaseModel):
    """Entrada validada para memory_store."""

    key: str = Field(min_length=1)
    value: str = Field(min_length=1)
    agent: str = Field(default=DEFAULT_MEMORY_AGENT, min_length=1)


class MemoryRecallRequest(BaseModel):
    """Entrada validada para memory_recall."""

    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=50)
    agent: str = Field(default=DEFAULT_MEMORY_AGENT, min_length=1)


class RegistrySearchRequest(BaseModel):
    """Entrada validada para registry_search."""

    query: str = Field(min_length=1)
    limit: int = Field(default=20, ge=1, le=100)
    kind: str = Field(default="all")
    use_cache: bool = Field(default=True)


class RegistryLoadRequest(BaseModel):
    """Entrada validada para registry_load."""

    kind: str = Field(min_length=1)
    name: str = Field(min_length=1)


class TeamsRunStepRequest(BaseModel):
    """Entrada validada para teams_run_step."""

    step: str = Field(min_length=1)
    task: str = Field(min_length=1)
    execute: bool = Field(default=False)


class TeamsRunPipelineRequest(BaseModel):
    """Entrada validada para teams_run_pipeline."""

    task: str = Field(min_length=1)
    steps: list[str] = Field(default_factory=list)
    execute: bool = Field(default=False)


# =============================================================================
# Helpers
# =============================================================================


def _is_within_project_root(candidate_path: Path) -> bool:
    """Verifica que una ruta esté dentro de PROJECT_ROOT (previene traversal)."""
    try:
        candidate_path.relative_to(PROJECT_ROOT.resolve())
        return True
    except ValueError:
        return False


def _read_file_safe(path: Path, max_bytes: int = 50_000) -> str:
    """Lee un archivo de forma segura con límite de tamaño."""
    try:
        content = path.read_text(encoding="utf-8")
        if len(content) > max_bytes:
            content = content[:max_bytes] + "\n\n[... contenido truncado ...]"
        return content
    except (OSError, UnicodeDecodeError) as e:
        return f"Error leyendo archivo: {e}"


def _extract_description(md_path: Path, max_len: int = 300) -> str:
    """Extrae la primera descripción significativa de un archivo Markdown."""
    if not md_path.exists():
        return ""
    try:
        for line in md_path.read_text(encoding="utf-8").split("\n"):
            stripped = line.strip()
            if stripped and not stripped.startswith("#"):
                return stripped[:max_len]
    except (OSError, UnicodeDecodeError):
        pass
    return ""


def _sha256_text(content: str) -> str:
    """Hash estable para contenido textual."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def _read_json_file(path: Path) -> dict[str, Any]:
    """Lee JSON tolerando ausencia/corrupción."""
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return data if isinstance(data, dict) else {}


def _write_json_file(path: Path, payload: dict[str, Any]) -> None:
    """Escribe JSON creando directorios padres."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _validate_url(url: str) -> None:
    """Valida que la URL sea segura para requests HTTP salientes.

    Rechaza schemes no-HTTP/HTTPS y hostnames privados/internos para
    prevenir ataques SSRF (Server-Side Request Forgery).

    Args:
        url: URL a validar.

    Raises:
        ValueError: Si la URL tiene scheme inválido o apunta a un host privado.
    """
    parsed = urllib.parse.urlparse(url)

    # Solo permitir HTTP y HTTPS
    if parsed.scheme not in {"http", "https"}:
        raise ValueError(f"Scheme no permitido: '{parsed.scheme}'. Solo se permiten http/https.")

    hostname = parsed.hostname or ""
    if not hostname:
        raise ValueError("URL sin hostname válido.")

    hostname_lower = hostname.lower()

    # Rechazar localhost y variantes
    _BLOCKED_HOSTNAMES = {
        "localhost",
        "::1",
        "0.0.0.0",  # noqa: S104
    }
    if hostname_lower in _BLOCKED_HOSTNAMES:
        raise ValueError(f"Hostname bloqueado por política SSRF: '{hostname}'.")

    # Rechazar IPs de loopback IPv4 (127.x.x.x)
    _LOOPBACK_RE = re.compile(r"^127\.\d{1,3}\.\d{1,3}\.\d{1,3}$")
    if _LOOPBACK_RE.match(hostname_lower):
        raise ValueError(f"IP de loopback bloqueada por política SSRF: '{hostname}'.")

    # Rechazar link-local (169.254.x.x) — metadata services en cloud providers
    _LINK_LOCAL_RE = re.compile(r"^169\.254\.\d{1,3}\.\d{1,3}$")
    if _LINK_LOCAL_RE.match(hostname_lower):
        raise ValueError(f"IP link-local bloqueada por política SSRF: '{hostname}'.")

    # Rechazar rangos privados RFC 1918
    _PRIVATE_RANGES = [
        re.compile(r"^10\.\d{1,3}\.\d{1,3}\.\d{1,3}$"),
        re.compile(r"^192\.168\.\d{1,3}\.\d{1,3}$"),
        re.compile(r"^172\.(1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3}$"),
    ]
    for pattern in _PRIVATE_RANGES:
        if pattern.match(hostname_lower):
            raise ValueError(f"IP de red privada bloqueada por política SSRF: '{hostname}'.")


def _http_json(
    *,
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    timeout: int = 8,
) -> tuple[int, dict[str, Any] | list[Any] | str]:
    """Ejecuta request HTTP JSON simple usando stdlib.

    Valida la URL antes de realizar la request para prevenir SSRF.

    Args:
        method: Método HTTP (GET, POST, etc.).
        url: URL destino. Debe ser HTTP/HTTPS y apuntar a un host público.
        payload: Cuerpo JSON opcional para la request.
        timeout: Tiempo máximo de espera en segundos.

    Returns:
        Tupla (status_code, body) donde body es el JSON parseado o string raw.

    Raises:
        ValueError: Si la URL no pasa la validación anti-SSRF.
    """
    # Validar URL antes de cualquier request para prevenir SSRF
    _validate_url(url)

    data_bytes: bytes | None = None
    headers = {"Accept": "application/json"}
    if payload is not None:
        data_bytes = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url=url, data=data_bytes, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310
            body = resp.read().decode("utf-8", errors="replace")
            try:
                return resp.status, json.loads(body)
            except json.JSONDecodeError:
                return resp.status, body
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            parsed = json.loads(body)
        except json.JSONDecodeError:
            parsed = body
        return exc.code, parsed
    except urllib.error.URLError as exc:
        return 0, {"error": str(exc)}


def datetime_now_iso() -> str:
    """Timestamp ISO UTC simple."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


# =============================================================================
# Servidor principal
# =============================================================================


class AntigravityMCPServer:
    """Servidor MCP v4.0 con Tools, Resources, Prompts y Sampling."""

    def __init__(self) -> None:
        self.server: Server = Server("antigravity")
        self.skills = self._discover_skills()
        self.agents = self._discover_agents()
        self.workflows = self._discover_workflows()
        self.commands = self._discover_commands()
        self.ecosystem_config = self._load_ecosystem_config()
        self.memory_backend = str(self.ecosystem_config.get("memoryBackend", DEFAULT_MEMORY_BACKEND))
        # Intentar cargar el modulo de memoria unificado (ChromaDB via memory-server.py)
        self._memory_module = _get_memory_module()
        registry_cfg = self.ecosystem_config.get("registry", {})
        if not isinstance(registry_cfg, dict):
            registry_cfg = {}
        self.registry_ttl_seconds = int(registry_cfg.get("cacheTtl", DEFAULT_REGISTRY_TTL_SECONDS))
        self.registry_url = str(
            os.environ.get("ANTIGRAVITY_REGISTRY_URL")
            or self.ecosystem_config.get("gateway")
            or "https://mcp.uns-kikaku.cloud"
        ).rstrip("/")

        self._register_tools()
        self._register_resources()
        self._register_prompts()
        # _register_sampling() desactivado: API create_message removida en MCP SDK actual

        logger.info(
            "Antigravity MCP v4.0: %d skills | %d agentes | %d workflows",
            len(self.skills),
            len(self.agents),
            len(self.workflows),
        )

    def _validate_url(self, url: str) -> None:
        """Valida que la URL sea segura para requests HTTP salientes.

        Delega a la función module-level `_validate_url` para prevenir SSRF.
        Adicionalmente verifica que el hostname coincida con el registry configurado.

        Args:
            url: URL a validar.

        Raises:
            ValueError: Si la URL tiene scheme inválido, apunta a un host privado,
                o no corresponde al hostname del registry configurado.
        """
        # Validación base anti-SSRF (scheme + rangos privados)
        _validate_url(url)

        # Restricción adicional: solo permitir el hostname del registry configurado
        parsed_url = urllib.parse.urlparse(url)
        parsed_registry = urllib.parse.urlparse(self.registry_url)
        if parsed_url.hostname != parsed_registry.hostname:
            raise ValueError(
                f"Host '{parsed_url.hostname}' no está en la lista de hosts permitidos. "
                f"Solo se permite '{parsed_registry.hostname}'."
            )

    def _load_ecosystem_config(self) -> dict[str, Any]:
        """Carga configuración del ecosistema (.antigravity/config.json)."""
        config_path = PROJECT_ROOT / ".antigravity" / "config.json"
        config = _read_json_file(config_path)
        return config if config else {}

    # ------------------------------------------------------------------
    # Discovery
    # ------------------------------------------------------------------

    def _discover_skills(self) -> dict[str, dict]:
        """Auto-descubre skills con scripts ejecutables."""
        skills: dict[str, dict] = {}
        if not SKILLS_DIR.exists():
            return skills
        for skill_dir in sorted(SKILLS_DIR.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith("."):
                continue
            scripts_dir = skill_dir / "scripts"
            if not scripts_dir.exists():
                continue
            main_script = next(scripts_dir.glob("*.py"), None)
            if main_script:
                skills[skill_dir.name] = {
                    "name": skill_dir.name,
                    "script": str(main_script),
                    "description": _extract_description(skill_dir / "SKILL.md")
                    or f"Skill: {skill_dir.name}",
                    "skill_md": skill_dir / "SKILL.md",
                }
        return skills

    def _discover_agents(self) -> dict[str, dict]:
        """Auto-descubre agentes con SYSTEM_PROMPT o IDENTITY."""
        agents: dict[str, dict] = {}
        if not AGENTS_DIR.exists():
            return agents
        for agent_dir in sorted(AGENTS_DIR.iterdir()):
            if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
                continue
            prompt_file = agent_dir / "SYSTEM_PROMPT.md"
            identity_file = agent_dir / "IDENTITY.md"
            doc_file = prompt_file if prompt_file.exists() else identity_file
            if doc_file.exists():
                agents[agent_dir.name] = {
                    "name": agent_dir.name,
                    "doc_file": doc_file,
                    "description": _extract_description(doc_file) or f"Agente: {agent_dir.name}",
                }
        return agents

    def _discover_workflows(self) -> dict[str, dict]:
        """Auto-descubre workflows (slash commands)."""
        workflows: dict[str, dict] = {}
        if not WORKFLOWS_DIR.exists():
            return workflows
        for wf_file in sorted(WORKFLOWS_DIR.glob("*.md")):
            name = wf_file.stem
            workflows[name] = {
                "name": name,
                "file": wf_file,
                "description": _extract_description(wf_file) or f"Workflow: {name}",
            }
        return workflows

    def _discover_commands(self) -> dict[str, dict]:
        """Descubre comandos legacy exportables como catálogo universal MCP."""
        commands: dict[str, dict] = {}
        if not LEGACY_COMMANDS_DIR.exists():
            return commands
        for command_file in sorted(LEGACY_COMMANDS_DIR.glob("*.md")):
            name = command_file.stem
            commands[name] = {
                "name": name,
                "file": command_file,
                "description": _extract_description(command_file) or f"Comando: {name}",
            }
        return commands

    # ------------------------------------------------------------------
    # TOOLS
    # ------------------------------------------------------------------

    # Lista de tools descubierta dinámicamente en _register_tools().
    # No editar manualmente: se llena automáticamente al instanciar el servidor.
    _registered_tools: list[str]

    async def _list_tools(self) -> list[str]:
        """Devuelve lista de nombres de tools registrados (extracción dinámica)."""
        return list(getattr(self, "_registered_tools", []))

    def list_tools_sync(self) -> list[str]:
        """Wrapper síncrono de _list_tools para uso fuera de contexto async."""
        return list(getattr(self, "_registered_tools", []))

    def _register_tools(self) -> None:
        """Registra todos los tools MCP y auto-descubre sus nombres en _registered_tools."""

        # Definir el catálogo de tools una sola vez para poder extraer los nombres
        _tools_catalog: list[Tool] = [
                Tool(
                    name="list_skills",
                    description="Lista todas las skills disponibles en el ecosistema Antigravity (793+ skills).",
                    inputSchema={"type": "object", "properties": {}, "required": []},
                ),
                Tool(
                    name="search_skills",
                    description="Busca skills por palabra clave en nombre o descripción.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Término de búsqueda"}
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="run_skill",
                    description="Ejecuta una skill específica del ecosistema por nombre.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "skill_name": {
                                "type": "string",
                                "description": "Nombre exacto de la skill (de list_skills o search_skills)",
                            },
                            "args": {
                                "type": "string",
                                "description": "Argumentos para el script de la skill",
                            },
                        },
                        "required": ["skill_name"],
                    },
                ),
                Tool(
                    name="list_agents",
                    description="Lista los 40 agentes operativos del ecosistema con sus descripciones.",
                    inputSchema={"type": "object", "properties": {}, "required": []},
                ),
                Tool(
                    name="list_workflows",
                    description="Lista workflows/comandos reutilizables del ecosistema.",
                    inputSchema={"type": "object", "properties": {}, "required": []},
                ),
                Tool(
                    name="list_commands",
                    description="Lista comandos universales exportados desde el catálogo legacy.",
                    inputSchema={"type": "object", "properties": {}, "required": []},
                ),
                Tool(
                    name="get_agent_prompt",
                    description="Obtiene el system prompt / identidad de un agente específico.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "agent_name": {
                                "type": "string",
                                "description": "Nombre del agente (de list_agents)",
                            }
                        },
                        "required": ["agent_name"],
                    },
                ),
                Tool(
                    name="get_workflow",
                    description="Obtiene el contenido de un workflow/comando reutilizable.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "workflow_name": {
                                "type": "string",
                                "description": "Nombre del workflow (sin .md)",
                            }
                        },
                        "required": ["workflow_name"],
                    },
                ),
                Tool(
                    name="get_command",
                    description="Obtiene el contenido de un comando universal exportado por MCP.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "command_name": {
                                "type": "string",
                                "description": "Nombre del comando (sin .md)",
                            }
                        },
                        "required": ["command_name"],
                    },
                ),
                Tool(
                    name="compose_skills",
                    description=(
                        "Descompone una tarea compleja y encuentra las skills más relevantes "
                        "para resolverla de forma encadenada."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": "Descripción de la tarea de alto nivel",
                            },
                            "max_skills": {
                                "type": "integer",
                                "description": "Número máximo de skills a sugerir (default: 5)",
                                "default": 5,
                            },
                        },
                        "required": ["task"],
                    },
                ),
                Tool(
                    name="memory_store",
                    description="Guarda memoria persistente (ChromaDB unificado, fallback JSONL).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "key": {"type": "string", "description": "Clave semántica"},
                            "value": {"type": "string", "description": "Contenido a guardar"},
                            "agent": {"type": "string", "description": "Namespace del agente"},
                        },
                        "required": ["key", "value"],
                    },
                ),
                Tool(
                    name="memory_recall",
                    description="Recupera memoria por busqueda semantica (ChromaDB unificado, fallback JSONL).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Consulta de búsqueda"},
                            "limit": {"type": "integer", "default": 5},
                            "agent": {"type": "string", "description": "Namespace del agente"},
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="memory_stats",
                    description="Estado y métricas del backend de memoria activo.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "agent": {"type": "string", "description": "Namespace del agente"},
                        },
                        "required": [],
                    },
                ),
                Tool(
                    name="registry_search",
                    description="Busca skills/agentes con cache local y fallback remoto.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "query": {"type": "string", "description": "Texto de búsqueda"},
                            "limit": {"type": "integer", "default": 20},
                            "kind": {"type": "string", "description": "all|skills|agents"},
                            "use_cache": {"type": "boolean", "default": True},
                        },
                        "required": ["query"],
                    },
                ),
                Tool(
                    name="registry_load",
                    description="Carga skill/agent por nombre (local -> remoto).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "kind": {"type": "string", "description": "skill|agent"},
                            "name": {"type": "string", "description": "Nombre exacto"},
                        },
                        "required": ["kind", "name"],
                    },
                ),
                Tool(
                    name="teams_run_pipeline",
                    description="Ejecuta pipeline declarativo SDD (init/new/plan/apply/verify).",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "task": {"type": "string", "description": "Objetivo del pipeline"},
                            "steps": {"type": "array", "items": {"type": "string"}},
                            "execute": {"type": "boolean", "default": False},
                        },
                        "required": ["task"],
                    },
                ),
                Tool(
                    name="teams_run_step",
                    description="Ejecuta un paso SDD individual y guarda traza.",
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "step": {"type": "string", "description": "init|new|plan|apply|verify"},
                            "task": {"type": "string", "description": "Objetivo del paso"},
                             "execute": {"type": "boolean", "default": False},
                        },
                        "required": ["step", "task"],
                    },
                ),
                Tool(
                    name="get_ecosystem_stats",
                    description="Devuelve estadísticas completas del ecosistema Antigravity.",
                    inputSchema={"type": "object", "properties": {}, "required": []},
                ),
                # Brain Network tools — red de inteligencia distribuida
                Tool(
                    name="brain_query",
                    description=(
                        "Buscar conocimiento en la red de brains del ecosistema. "
                        "Busca en el Mother Brain + todos los app brains registrados. "
                        "Soporta expansion semantica (auth↔jwt↔login, daicho↔nomina↔payroll)."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "question": {
                                "type": "string",
                                "description": "Pregunta o termino de busqueda",
                            },
                            "limit": {"type": "integer", "default": 10},
                            "app_filter": {
                                "type": "string",
                                "description": "Filtrar a un brain especifico",
                            },
                        },
                        "required": ["question"],
                    },
                ),
                Tool(
                    name="brain_ingest",
                    description=(
                        "Ingestar conocimiento nuevo en un brain de la red. "
                        "Crea nodo con frontmatter YAML, cross-refs bidireccionales, "
                        "y auto-sync al Mother Brain."
                    ),
                    inputSchema={
                        "type": "object",
                        "properties": {
                            "title": {"type": "string", "description": "Titulo del conocimiento"},
                            "context": {"type": "string", "description": "Contexto/background"},
                            "decisions": {"type": "string", "description": "Decisiones tomadas"},
                            "area": {"type": "string", "description": "Area (dev, ops, ux, etc.)"},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "node_type": {"type": "string", "default": "session"},
                            "importance": {"type": "string", "default": "normal"},
                        },
                        "required": ["title"],
                    },
                ),
                Tool(
                    name="brain_stats",
                    description="Estadisticas de la red de brains: nodos, conexiones, apps.",
                    inputSchema={"type": "object", "properties": {}, "required": []},
                ),
        ]

        # Auto-descubrir nombres desde el catálogo real (evita listas estáticas desincronizadas)
        self._registered_tools = [t.name for t in _tools_catalog]

        @self.server.list_tools()
        async def list_tools() -> list[Tool]:
            return _tools_catalog

        @self.server.call_tool()
        async def call_tool(name: str, arguments: dict) -> list[TextContent]:
            return await self._call_tool(name, arguments)

    async def _call_tool(self, name: str, arguments: dict) -> list[TextContent]:
        """Despacha llamadas a tools."""

        if name == "list_skills":
            result = [
                {"name": k, "description": v["description"]}
                for k, v in self.skills.items()
            ]
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        if name == "list_agents":
            result = [
                {"name": k, "description": v["description"]}
                for k, v in self.agents.items()
            ]
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        if name == "list_workflows":
            result = [
                {"name": k, "description": v["description"]}
                for k, v in self.workflows.items()
            ]
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        if name == "list_commands":
            result = [
                {"name": k, "description": v["description"]}
                for k, v in self.commands.items()
            ]
            return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

        if name == "search_skills":
            try:
                req = SearchSkillsRequest(**arguments)
            except ValidationError as e:
                return [TextContent(type="text", text=f"Error: {e}")]
            query = req.query.lower()
            matches = [
                {"name": k, "description": v["description"]}
                for k, v in self.skills.items()
                if query in k.lower() or query in v["description"].lower()
            ]
            return [TextContent(type="text", text=json.dumps(matches, indent=2, ensure_ascii=False))]

        if name == "get_agent_prompt":
            agent_name = arguments.get("agent_name", "")
            if agent_name not in self.agents:
                return [TextContent(type="text", text=f"Agente '{agent_name}' no encontrado.")]
            content = _read_file_safe(self.agents[agent_name]["doc_file"])
            return [TextContent(type="text", text=content)]

        if name == "get_workflow":
            workflow_name = arguments.get("workflow_name", "")
            if workflow_name not in self.workflows:
                return [TextContent(type="text", text=f"Workflow '{workflow_name}' no encontrado.")]
            content = _read_file_safe(self.workflows[workflow_name]["file"])
            return [TextContent(type="text", text=content)]

        if name == "get_command":
            command_name = arguments.get("command_name", "")
            if command_name not in self.commands:
                return [TextContent(type="text", text=f"Comando '{command_name}' no encontrado.")]
            content = _read_file_safe(self.commands[command_name]["file"])
            return [TextContent(type="text", text=content)]

        if name == "run_skill":
            return await self._run_skill(arguments)

        if name == "compose_skills":
            return await self._compose_skills(arguments)

        if name == "memory_store":
            return await self._memory_store(arguments)

        if name == "memory_recall":
            return await self._memory_recall(arguments)

        if name == "memory_stats":
            return await self._memory_stats(arguments)

        if name == "registry_search":
            return await self._registry_search(arguments)

        if name == "registry_load":
            return await self._registry_load(arguments)

        if name == "teams_run_pipeline":
            return await self._teams_run_pipeline(arguments)

        if name == "teams_run_step":
            return await self._teams_run_step(arguments)

        if name == "get_ecosystem_stats":
            registry_cache = self._read_registry_cache()
            registry_cfg = self.ecosystem_config.get("registry", {})
            if not isinstance(registry_cfg, dict):
                registry_cfg = {}
            stats = {
                "version": "2.1.0",
                "agentes_activos": len(self.agents),
                "skills_totales": len(self.skills),
                "workflows": len(self.workflows),
                "commands": len(self.commands),
                "memory_backend": self.memory_backend,
                "registry_mode": registry_cfg.get("mode", "remote-cache"),
                "registry_cache_queries": len(registry_cache.get("queries", {})),
                "mcp_server_version": "4.0",
                "capacidades": ["tools", "resources", "prompts", "sampling"],
                "transportes": ["stdio", "http", "sse"],
                "llms_soportados": ["claude", "gpt-4", "gemini", "ollama"],
                "gateway_url": "http://127.0.0.1:4747",
            }
            return [TextContent(type="text", text=json.dumps(stats, indent=2, ensure_ascii=False))]

        if name == "brain_query":
            return self._brain_query(arguments)

        if name == "brain_ingest":
            return self._brain_ingest(arguments)

        if name == "brain_stats":
            return self._brain_stats(arguments)

        return [TextContent(type="text", text=f"Tool desconocida: {name}")]

    # ------------------------------------------------------------------
    # Brain Network helpers
    # ------------------------------------------------------------------

    def _get_brain_network(self):
        """Lazy-init del BrainNetwork."""
        if not hasattr(self, "_brain_network"):
            try:
                import sys as _sys
                agent_dir = str(Path(__file__).parent.parent / ".agent")
                if agent_dir not in _sys.path:
                    _sys.path.insert(0, agent_dir)
                from core.brain_network import BrainNetwork
                self._brain_network = BrainNetwork(Path(__file__).parent.parent)
            except Exception as e:
                logger.warning("BrainNetwork no disponible: %s", e)
                self._brain_network = None
        return self._brain_network

    def _brain_query(self, arguments: dict) -> list[TextContent]:
        """Busca en la red de brains."""
        network = self._get_brain_network()
        if not network:
            return [TextContent(type="text", text=json.dumps({"error": "BrainNetwork no disponible"}))]
        question = arguments.get("question", "")
        if not question:
            return [TextContent(type="text", text=json.dumps({"error": "question requerido"}))]
        results = network.query_network(
            question,
            limit=int(arguments.get("limit", 10)),
            app_filter=arguments.get("app_filter"),
        )
        return [TextContent(type="text", text=json.dumps({
            "success": True,
            "total": len(results),
            "results": [
                {
                    "brain_id": r.brain_id,
                    "slug": r.node.slug,
                    "title": r.node.title,
                    "type": r.node.type,
                    "area": r.node.area,
                    "tags": r.node.tags,
                    "date": r.node.date,
                    "context": r.node.context[:500] if r.node.context else "",
                    "relevance": round(r.relevance_score, 2),
                }
                for r in results
            ],
        }, ensure_ascii=False, indent=2))]

    def _brain_ingest(self, arguments: dict) -> list[TextContent]:
        """Ingesta conocimiento en el Mother Brain."""
        network = self._get_brain_network()
        if not network:
            return [TextContent(type="text", text=json.dumps({"error": "BrainNetwork no disponible"}))]
        title = arguments.get("title", "")
        if not title:
            return [TextContent(type="text", text=json.dumps({"error": "title requerido"}))]
        node = network.mother.ingest(
            title=title,
            context=arguments.get("context", ""),
            decisions=arguments.get("decisions", ""),
            area=arguments.get("area", "general"),
            tags=arguments.get("tags", []),
            node_type=arguments.get("node_type", "session"),
            importance=arguments.get("importance", "normal"),
        )
        return [TextContent(type="text", text=json.dumps({
            "success": True,
            "slug": node.slug,
            "title": node.title,
            "type": node.type,
            "tags": node.tags,
            "related": node.related,
        }, ensure_ascii=False, indent=2))]

    def _brain_stats(self, arguments: dict) -> list[TextContent]:
        """Estadisticas de la red de brains."""
        network = self._get_brain_network()
        if not network:
            return [TextContent(type="text", text=json.dumps({"error": "BrainNetwork no disponible"}))]
        stats = network.network_stats()
        return [TextContent(type="text", text=json.dumps({
            "success": True,
            **stats,
        }, ensure_ascii=False, indent=2))]

    async def _run_skill(self, arguments: dict) -> list[TextContent]:
        """Ejecuta una skill de forma segura con límite de concurrencia y timeout global."""
        global _active_skill_executions

        # Concurrency limiter — prevent resource exhaustion
        if _active_skill_executions >= MAX_CONCURRENT_SKILLS:
            logger.warning("Concurrent skill limit reached (%d/%d)", _active_skill_executions, MAX_CONCURRENT_SKILLS)
            return [TextContent(type="text", text="Error: demasiadas ejecuciones concurrentes de skills. Intenta de nuevo más tarde.")]

        try:
            req = RunSkillRequest(**arguments)
        except ValidationError as e:
            return [TextContent(type="text", text=f"Error de validación: {e}")]

        skill_name = req.skill_name.strip()
        if skill_name not in self.skills:
            close = [k for k in self.skills if skill_name in k]
            hint = f" Sugerencias: {close[:3]}" if close else ""
            return [TextContent(type="text", text=f"Skill '{skill_name}' no encontrada.{hint}")]

        script_path = Path(self.skills[skill_name]["script"]).resolve()
        if not _is_within_project_root(script_path):
            return [TextContent(type="text", text="Error: ruta fuera del proyecto.")]

        args_str = req.args or "--help"
        try:
            safe_args = shlex.split(args_str)
        except ValueError as e:
            return [TextContent(type="text", text=f"Error parseando argumentos: {e}")]

        if not self._validate_args(safe_args):
            return [TextContent(type="text", text="Error: argumentos no permitidos.")]

        args_display = args_str[:200] if len(args_str) > 200 else args_str
        logger.info("Executing skill '%s' with args: %s", skill_name, args_display)

        _active_skill_executions += 1
        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(
                    subprocess.run,
                    [sys.executable, str(script_path)] + safe_args,
                    capture_output=True,
                    text=True,
                    timeout=DEFAULT_SCRIPT_TIMEOUT_SECONDS,
                    cwd=PROJECT_ROOT,
                    shell=False,
                ),
                timeout=GLOBAL_SKILL_TIMEOUT_SECONDS,
            )
            output = result.stdout or result.stderr or "Sin salida"
            return [TextContent(type="text", text=output)]
        except TimeoutError:
            logger.error("Global timeout exceeded for skill '%s' (%ds)", skill_name, GLOBAL_SKILL_TIMEOUT_SECONDS)
            return [TextContent(type="text", text=f"Timeout global ({GLOBAL_SKILL_TIMEOUT_SECONDS}s) excedido para skill '{skill_name}'.")]
        except subprocess.TimeoutExpired:
            logger.error("Skill '%s' timeout with args: %s", skill_name, args_display)
            return [TextContent(type="text", text=f"Timeout ({DEFAULT_SCRIPT_TIMEOUT_SECONDS}s)")]
        except Exception as e:
            logger.error("Skill '%s' failed with args: %s — error: %s", skill_name, args_display, e)
            return [TextContent(type="text", text=f"Error ejecutando skill: {e}")]
        finally:
            _active_skill_executions -= 1

    async def _compose_skills(self, arguments: dict) -> list[TextContent]:
        """Sugiere pipeline de skills para una tarea compleja."""
        try:
            req = ComposeSkillsRequest(**arguments)
        except ValidationError as e:
            return [TextContent(type="text", text=f"Error: {e}")]

        task_lower = req.task.lower()
        scored: list[tuple[int, str, str]] = []

        for name, info in self.skills.items():
            score = 0
            desc_lower = info["description"].lower()
            name_lower = name.lower()

            # Puntaje por coincidencia de palabras clave
            for word in task_lower.split():
                if len(word) < 3:
                    continue
                if word in name_lower:
                    score += 3
                if word in desc_lower:
                    score += 1

            if score > 0:
                scored.append((score, name, info["description"]))

        scored.sort(key=lambda x: -x[0])
        top_skills = scored[: req.max_skills]

        pipeline = {
            "task": req.task,
            "skill_pipeline": [
                {"step": i + 1, "skill": name, "description": desc, "relevance_score": score}
                for i, (score, name, desc) in enumerate(top_skills)
            ],
            "sugerencia": (
                "Ejecuta cada skill en secuencia usando run_skill. "
                "Pasa el output de cada paso como input del siguiente."
            ),
        }

        return [TextContent(type="text", text=json.dumps(pipeline, indent=2, ensure_ascii=False))]

    def _fallback_memory_file(self) -> Path:
        """Ruta de fallback local para memoria cuando backend principal falla."""
        return PROJECT_ROOT / ".agent" / "memory" / "engram-fallback.jsonl"

    def _fallback_memory_store(self, agent: str, key: str, value: str) -> dict[str, Any]:
        """Guarda memoria en fallback local JSONL."""
        path = self._fallback_memory_file()
        path.parent.mkdir(parents=True, exist_ok=True)
        memory_id = f"{agent}:{key}:{int(time.time())}"
        row = {
            "id": memory_id,
            "agent": agent,
            "key": key,
            "value": value,
            "timestamp": datetime_now_iso(),
            "backend": "fallback",
        }
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        return row

    def _fallback_memory_entries(self) -> list[dict[str, Any]]:
        """Lee todas las entradas del fallback local."""
        path = self._fallback_memory_file()
        if not path.exists():
            return []
        rows: list[dict[str, Any]] = []
        for line in path.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(obj, dict):
                rows.append(obj)
        return rows

    async def _memory_store(self, arguments: dict) -> list[TextContent]:
        """Store de memoria — delega a ChromaDB (memory-server.py) con fallback JSONL.

        Unifica el backend: usa el mismo ChromaDB que antigravity-memory,
        garantizando que lo guardado desde cualquier servidor sea visible
        desde ambos.
        """
        try:
            req = MemoryStoreRequest(**arguments)
        except ValidationError as e:
            return [TextContent(type="text", text=f"Error de validación: {e}")]

        started = time.perf_counter()

        # --- Backend primario: ChromaDB via memory-server.py ---
        mem_mod = self._memory_module
        if mem_mod is not None:
            try:
                # Adaptar interfaz key/value a content del memory-server
                content = f"{req.key}: {req.value}"
                chromadb_result = mem_mod.handle_memory_store({
                    "content": content,
                    "user_id": req.agent,
                    "metadata": {
                        "key": req.key,
                        "category": "mcp-server",
                        "source": "antigravity-main",
                    },
                })
                if chromadb_result.get("success"):
                    latency_ms = round((time.perf_counter() - started) * 1000, 2)
                    result: dict[str, Any] = {
                        "ok": True,
                        "backend": chromadb_result.get("mode", "chromadb"),
                        "latencyMs": latency_ms,
                        "response": chromadb_result,
                    }
                    logger.info(
                        "memory_store OK via ChromaDB (%s) — key=%s, latency=%.1fms",
                        chromadb_result.get("mode"), req.key, latency_ms,
                    )
                    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
                else:
                    logger.warning(
                        "ChromaDB store retorno error: %s — cayendo a fallback JSONL",
                        chromadb_result.get("error", "desconocido"),
                    )
            except Exception as e:
                logger.warning("ChromaDB store fallo: %s — cayendo a fallback JSONL", e)

        # --- Fallback: JSONL local ---
        fallback = self._fallback_memory_store(req.agent, req.key, req.value)
        result = {
            "ok": True,
            "backend": "fallback-jsonl",
            "latencyMs": round((time.perf_counter() - started) * 1000, 2),
            "response": fallback,
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    async def _memory_recall(self, arguments: dict) -> list[TextContent]:
        """Recall de memoria — busqueda semantica via ChromaDB con fallback JSONL.

        Usa el mismo backend ChromaDB que antigravity-memory para garantizar
        que las memorias guardadas desde cualquier servidor sean encontradas.
        """
        try:
            req = MemoryRecallRequest(**arguments)
        except ValidationError as e:
            return [TextContent(type="text", text=f"Error de validación: {e}")]

        started = time.perf_counter()

        # --- Backend primario: ChromaDB via memory-server.py ---
        mem_mod = self._memory_module
        if mem_mod is not None:
            try:
                chromadb_result = mem_mod.handle_memory_recall({
                    "query": req.query,
                    "user_id": req.agent,
                    "limit": req.limit,
                })
                if chromadb_result.get("success"):
                    latency_ms = round((time.perf_counter() - started) * 1000, 2)
                    result: dict[str, Any] = {
                        "ok": True,
                        "backend": "chromadb",
                        "latencyMs": latency_ms,
                        "response": {
                            "results": chromadb_result.get("memories", []),
                            "count": chromadb_result.get("total", 0),
                        },
                    }
                    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
                elif chromadb_result.get("error"):
                    logger.warning(
                        "ChromaDB recall retorno error: %s — cayendo a fallback JSONL",
                        chromadb_result.get("error"),
                    )
            except Exception as e:
                logger.warning("ChromaDB recall fallo: %s — cayendo a fallback JSONL", e)

        # --- Fallback: busqueda textual en JSONL ---
        entries = self._fallback_memory_entries()
        query_lower = req.query.lower()
        filtered = [
            row for row in entries
            if row.get("agent") == req.agent and query_lower in str(row.get("value", "")).lower()
        ][: req.limit]
        result = {
            "ok": True,
            "backend": "fallback-jsonl",
            "latencyMs": round((time.perf_counter() - started) * 1000, 2),
            "response": {"results": filtered, "count": len(filtered)},
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    async def _memory_stats(self, arguments: dict) -> list[TextContent]:
        """Estadisticas del backend de memoria — ChromaDB con fallback JSONL."""
        agent = str(arguments.get("agent", DEFAULT_MEMORY_AGENT))
        started = time.perf_counter()

        # --- Backend primario: ChromaDB via memory-server.py ---
        mem_mod = self._memory_module
        if mem_mod is not None:
            try:
                chromadb_result = mem_mod.handle_memory_stats({
                    "user_id": agent,
                })
                if chromadb_result.get("success"):
                    latency_ms = round((time.perf_counter() - started) * 1000, 2)
                    result: dict[str, Any] = {
                        "ok": True,
                        "backend": chromadb_result.get("backend", "chromadb"),
                        "healthy": True,
                        "latencyMs": latency_ms,
                        "response": chromadb_result,
                    }
                    return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]
            except Exception as e:
                logger.warning("ChromaDB stats fallo: %s — cayendo a fallback JSONL", e)

        # --- Fallback: estadisticas del JSONL ---
        entries = [row for row in self._fallback_memory_entries() if row.get("agent") == agent]
        result = {
            "ok": True,
            "backend": "fallback-jsonl",
            "healthy": True,
            "latencyMs": round((time.perf_counter() - started) * 1000, 2),
            "response": {
                "total": len(entries),
                "agent": agent,
                "storage_path": str(self._fallback_memory_file()),
            },
        }
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    def _read_registry_cache(self) -> dict[str, Any]:
        """Lee cache local de registry."""
        data = _read_json_file(REGISTRY_CACHE_FILE)
        if "queries" not in data or not isinstance(data.get("queries"), dict):
            data["queries"] = {}
        return data

    def _write_registry_cache(self, payload: dict[str, Any]) -> None:
        """Persistencia del cache local de registry."""
        _write_json_file(REGISTRY_CACHE_FILE, payload)

    def _search_local_registry(self, query: str, limit: int, kind: str) -> list[dict[str, Any]]:
        """Búsqueda local sobre skills/agentes descubiertos."""
        q = query.lower()
        results: list[dict[str, Any]] = []
        if kind in {"all", "skills"}:
            for name, info in self.skills.items():
                if q in name.lower() or q in info["description"].lower():
                    results.append({
                        "kind": "skill",
                        "name": name,
                        "description": info["description"],
                        "source": "local",
                    })
        if kind in {"all", "agents"}:
            for name, info in self.agents.items():
                if q in name.lower() or q in info["description"].lower():
                    results.append({
                        "kind": "agent",
                        "name": name,
                        "description": info["description"],
                        "source": "local",
                    })
        return results[:limit]

    def _search_remote_registry(self, query: str, limit: int, kind: str) -> list[dict[str, Any]]:
        """Búsqueda remota contra gateway/registry MCP."""
        encoded_q = urllib.parse.quote(query)
        results: list[dict[str, Any]] = []
        if kind in {"all", "skills"}:
            status, body = _http_json(
                method="GET",
                url=f"{self.registry_url}/v1/skills?search={encoded_q}&limit={limit}",
            )
            if 200 <= status < 300 and isinstance(body, dict):
                data = body.get("data")
                if isinstance(data, dict):
                    items = data.get("skills", [])
                    if isinstance(items, list):
                        for item in items[:limit]:
                            if isinstance(item, dict):
                                results.append({
                                    "kind": "skill",
                                    "name": item.get("name", ""),
                                    "description": item.get("description", ""),
                                    "source": "remote",
                                })
        if kind in {"all", "agents"}:
            status, body = _http_json(
                method="GET",
                url=f"{self.registry_url}/v1/agents?search={encoded_q}&limit={limit}",
            )
            if 200 <= status < 300 and isinstance(body, dict):
                data = body.get("data")
                if isinstance(data, dict):
                    items = data.get("agents", [])
                    if isinstance(items, list):
                        for item in items[:limit]:
                            if isinstance(item, dict):
                                results.append({
                                    "kind": "agent",
                                    "name": item.get("name", ""),
                                    "description": item.get("description", ""),
                                    "source": "remote",
                                })
        return results

    async def _registry_search(self, arguments: dict) -> list[TextContent]:
        """Router de skills/agentes con cache local + remote fallback."""
        try:
            req = RegistrySearchRequest(**arguments)
        except ValidationError as e:
            return [TextContent(type="text", text=f"Error de validación: {e}")]

        started = time.perf_counter()
        key = f"{req.kind}:{req.query}:{req.limit}"
        cache = self._read_registry_cache()
        now = time.time()
        if req.use_cache:
            cached_entry = cache["queries"].get(key)
            if isinstance(cached_entry, dict):
                cached_ts = float(cached_entry.get("ts", 0.0))
                if now - cached_ts <= self.registry_ttl_seconds:
                    response = {
                        "ok": True,
                        "cacheHit": True,
                        "latencyMs": round((time.perf_counter() - started) * 1000, 2),
                        "results": cached_entry.get("results", []),
                    }
                    return [TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False))]

        local_results = self._search_local_registry(req.query, req.limit, req.kind)
        merged = list(local_results)
        if len(merged) < req.limit:
            remote_results = self._search_remote_registry(req.query, req.limit, req.kind)
            seen = {f"{item['kind']}::{item['name']}" for item in merged}
            for item in remote_results:
                key_name = f"{item.get('kind')}::{item.get('name')}"
                if key_name in seen:
                    continue
                seen.add(key_name)
                merged.append(item)
                if len(merged) >= req.limit:
                    break

        cache["queries"][key] = {
            "ts": now,
            "results": merged,
            "hash": _sha256_text(json.dumps(merged, ensure_ascii=False)),
        }
        self._write_registry_cache(cache)

        response = {
            "ok": True,
            "cacheHit": False,
            "latencyMs": round((time.perf_counter() - started) * 1000, 2),
            "results": merged,
            "ttlSeconds": self.registry_ttl_seconds,
        }
        return [TextContent(type="text", text=json.dumps(response, indent=2, ensure_ascii=False))]

    async def _registry_load(self, arguments: dict) -> list[TextContent]:
        """Carga skill/agent específico por nombre con fallback remoto."""
        try:
            req = RegistryLoadRequest(**arguments)
        except ValidationError as e:
            return [TextContent(type="text", text=f"Error de validación: {e}")]

        kind = req.kind.lower()
        if kind in {"skill", "skills"}:
            local = self.skills.get(req.name)
            if local is not None:
                payload = {
                    "ok": True,
                    "kind": "skill",
                    "name": req.name,
                    "source": "local",
                    "description": local["description"],
                    "content": _read_file_safe(Path(local["skill_md"])),
                }
                return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]
            status, body = _http_json(method="GET", url=f"{self.registry_url}/v1/skills/{req.name}")
            payload = {"ok": 200 <= status < 300, "kind": "skill", "name": req.name, "source": "remote", "response": body}
            return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]

        if kind in {"agent", "agents"}:
            local = self.agents.get(req.name)
            if local is not None:
                payload = {
                    "ok": True,
                    "kind": "agent",
                    "name": req.name,
                    "source": "local",
                    "description": local["description"],
                    "content": _read_file_safe(Path(local["doc_file"])),
                }
                return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]
            status, body = _http_json(method="GET", url=f"{self.registry_url}/v1/agents/{req.name}")
            payload = {"ok": 200 <= status < 300, "kind": "agent", "name": req.name, "source": "remote", "response": body}
            return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]

        return [TextContent(type="text", text=f"Tipo no soportado: {req.kind}")]

    def _append_team_trace(self, trace: dict[str, Any]) -> None:
        """Persistencia de trazas de orquestación declarativa."""
        TEAM_TRACE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with TEAM_TRACE_FILE.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(trace, ensure_ascii=False) + "\n")

    def _run_team_step_internal(self, step: str, task: str, execute: bool) -> dict[str, Any]:
        """Resuelve un paso SDD declarativo y opcionalmente ejecuta orquestador local."""
        normalized_step = step.strip().lower()
        workflow_candidates = [
            WORKFLOWS_DIR / f"sdd-{normalized_step}.md",
            WORKFLOWS_DIR / f"{normalized_step}.md",
        ]
        workflow_path = next((path for path in workflow_candidates if path.exists()), None)
        workflow_content = _read_file_safe(workflow_path) if workflow_path else ""
        executed = False
        execution_output = ""

        if execute:
            orchestrator = PROJECT_ROOT / ".agent" / "scripts" / "orchestrator.py"
            if orchestrator.exists():
                try:
                    proc = subprocess.run(
                        [sys.executable, str(orchestrator), task],
                        capture_output=True,
                        text=True,
                        timeout=DEFAULT_SCRIPT_TIMEOUT_SECONDS,
                        cwd=PROJECT_ROOT,
                        shell=False,
                    )
                    executed = proc.returncode == 0
                    execution_output = (proc.stdout or proc.stderr or "").strip()
                except Exception as exc:
                    execution_output = f"Error ejecutando orquestador: {exc}"
            else:
                execution_output = "No se encontró orchestrator.py para ejecución local."

        result = {
            "step": normalized_step,
            "task": task,
            "workflowFound": workflow_path is not None,
            "workflowPath": str(workflow_path) if workflow_path else "",
            "workflowPreview": workflow_content[:1200] if workflow_content else "",
            "executed": executed,
            "executionOutput": execution_output,
            "timestamp": datetime_now_iso(),
        }
        self._append_team_trace(result)
        return result

    async def _teams_run_step(self, arguments: dict) -> list[TextContent]:
        """Ejecuta un paso declarativo SDD + traza."""
        try:
            req = TeamsRunStepRequest(**arguments)
        except ValidationError as e:
            return [TextContent(type="text", text=f"Error de validación: {e}")]

        result = self._run_team_step_internal(req.step, req.task, req.execute)
        return [TextContent(type="text", text=json.dumps(result, indent=2, ensure_ascii=False))]

    async def _teams_run_pipeline(self, arguments: dict) -> list[TextContent]:
        """Ejecuta pipeline SDD completo y registra trazas."""
        try:
            req = TeamsRunPipelineRequest(**arguments)
        except ValidationError as e:
            return [TextContent(type="text", text=f"Error de validación: {e}")]

        steps = req.steps or ["init", "new", "plan", "apply", "verify"]
        results = [self._run_team_step_internal(step, req.task, req.execute) for step in steps]
        payload = {
            "ok": True,
            "task": req.task,
            "steps": steps,
            "results": results,
            "summary": {
                "total": len(results),
                "found": sum(1 for item in results if item["workflowFound"]),
                "executed": sum(1 for item in results if item["executed"]),
            },
        }
        return [TextContent(type="text", text=json.dumps(payload, indent=2, ensure_ascii=False))]

    def _validate_args(self, args: list[str]) -> bool:
        """Valida argumentos contra la allowlist."""
        for arg in args:
            if not any(re.fullmatch(p, arg) for p in SKILL_ARG_ALLOWLIST_DEFAULT):
                logger.warning("Argumento rechazado: %s", arg)
                return False
        return True

    # ------------------------------------------------------------------
    # RESOURCES
    # ------------------------------------------------------------------

    def _register_resources(self) -> None:
        """Registra Resources MCP: memoria, observaciones, catálogo."""

        @self.server.list_resources()
        async def list_resources() -> list[Resource]:
            resources = [
                Resource(
                    uri="antigravity://catalog/skills",
                    name="Catálogo de Skills",
                    description="Índice completo de las 940 skills del ecosistema con descripciones.",
                    mimeType="application/json",
                ),
                Resource(
                    uri="antigravity://catalog/agents",
                    name="Catálogo de Agentes",
                    description="Los 40 agentes operativos con sus roles, tiers y capacidades.",
                    mimeType="application/json",
                ),
                Resource(
                    uri="antigravity://catalog/workflows",
                    name="Catálogo de Workflows",
                    description="Los 24 workflows / slash commands disponibles.",
                    mimeType="application/json",
                ),
                Resource(
                    uri="antigravity://catalog/commands",
                    name="Catálogo de Commands",
                    description="Comandos universales exportados desde el legado de Claude.",
                    mimeType="application/json",
                ),
                Resource(
                    uri="antigravity://memory/app-knowledge",
                    name="Conocimiento de la Aplicación",
                    description="Documento de conocimiento persistente del ecosistema.",
                    mimeType="text/markdown",
                ),
                Resource(
                    uri="antigravity://memory/learnings",
                    name="Lecciones Aprendidas",
                    description="Historial de lecciones y errores resueltos para evitar repetirlos.",
                    mimeType="text/markdown",
                ),
                Resource(
                    uri="antigravity://architecture",
                    name="Arquitectura del Ecosistema",
                    description="Especificación técnica completa: agentes, skills, MCP, core.",
                    mimeType="text/markdown",
                ),
                Resource(
                    uri="antigravity://stats",
                    name="Estadísticas del Ecosistema",
                    description="Métricas en tiempo real: conteo de skills, agentes, versión.",
                    mimeType="application/json",
                ),
                Resource(
                    uri="antigravity://memory/backend-status",
                    name="Estado del Backend de Memoria",
                    description="Backend activo (chromadb/fallback-jsonl), salud y estadisticas.",
                    mimeType="application/json",
                ),
                Resource(
                    uri="antigravity://registry/cache-stats",
                    name="Estado del Skills Registry Cache",
                    description="TTL, cantidad de queries cacheadas y modo de resolución.",
                    mimeType="application/json",
                ),
                Resource(
                    uri="antigravity://teams/traces",
                    name="Trazas de Orquestación Teams",
                    description="Últimas ejecuciones de steps/pipelines SDD.",
                    mimeType="application/json",
                ),
            ]

            # Recursos dinámicos: últimas observaciones si existen
            if OBSERVATIONS_DIR.exists():
                resources.append(
                    Resource(
                        uri="antigravity://observations/recent",
                        name="Observaciones Recientes",
                        description="Últimas 20 observaciones del pipeline de acciones.",
                        mimeType="application/json",
                    )
                )

            return resources

        @self.server.read_resource()
        async def read_resource(uri: str) -> list[ReadResourceContents]:
            return await self._read_resource(str(uri))

    async def _read_resource(self, uri: str) -> list[ReadResourceContents]:
        """Lee el contenido de un recurso por URI."""

        if uri == "antigravity://catalog/skills":
            data = {k: v["description"] for k, v in self.skills.items()}
            return [ReadResourceContents(
                content=json.dumps(data, indent=2, ensure_ascii=False),
                mime_type="application/json",
            )]

        if uri == "antigravity://catalog/agents":
            data = {k: v["description"] for k, v in self.agents.items()}
            return [ReadResourceContents(
                content=json.dumps(data, indent=2, ensure_ascii=False),
                mime_type="application/json",
            )]

        if uri == "antigravity://catalog/workflows":
            data = {k: v["description"] for k, v in self.workflows.items()}
            return [ReadResourceContents(
                content=json.dumps(data, indent=2, ensure_ascii=False),
                mime_type="application/json",
            )]

        if uri == "antigravity://catalog/commands":
            data = {k: v["description"] for k, v in self.commands.items()}
            return [ReadResourceContents(
                content=json.dumps(data, indent=2, ensure_ascii=False),
                mime_type="application/json",
            )]

        if uri == "antigravity://memory/app-knowledge":
            path = CONTEXT_DIR / "APP_KNOWLEDGE.md"
            return [ReadResourceContents(
                content=_read_file_safe(path),
                mime_type="text/markdown",
            )]

        if uri == "antigravity://memory/learnings":
            path = CONTEXT_DIR / "LEARNINGS.md"
            return [ReadResourceContents(
                content=_read_file_safe(path),
                mime_type="text/markdown",
            )]

        if uri == "antigravity://architecture":
            path = PROJECT_ROOT / ".agent" / "ARCHITECTURE.md"
            return [ReadResourceContents(
                content=_read_file_safe(path),
                mime_type="text/markdown",
            )]

        if uri == "antigravity://stats":
            stats = {
                "version": "2.1.0",
                "skills": len(self.skills),
                "agents": len(self.agents),
                "workflows": len(self.workflows),
                "commands": len(self.commands),
                "mcp_capabilities": ["tools", "resources", "prompts", "sampling"],
            }
            return [ReadResourceContents(
                content=json.dumps(stats, indent=2, ensure_ascii=False),
                mime_type="application/json",
            )]

        if uri == "antigravity://memory/backend-status":
            # Verificar estado del backend ChromaDB unificado
            mem_mod = self._memory_module
            chromadb_healthy = False
            chromadb_stats: dict[str, Any] = {}
            if mem_mod is not None:
                try:
                    chromadb_stats = mem_mod.handle_memory_stats({"user_id": "antigravity"})
                    chromadb_healthy = bool(chromadb_stats.get("success"))
                except Exception as e:
                    chromadb_stats = {"error": str(e)}

            active_backend = "chromadb" if chromadb_healthy else "fallback-jsonl"
            data: dict[str, Any] = {
                "memoryBackend": active_backend,
                "unified": chromadb_healthy,
                "chromadb": {
                    "healthy": chromadb_healthy,
                    "stats": chromadb_stats,
                },
                "fallbackPath": str(self._fallback_memory_file()),
            }
            return [ReadResourceContents(
                content=json.dumps(data, indent=2, ensure_ascii=False),
                mime_type="application/json",
            )]

        if uri == "antigravity://registry/cache-stats":
            cache = self._read_registry_cache()
            queries = cache.get("queries", {})
            data = {
                "mode": self.ecosystem_config.get("registry", {}).get("mode", "remote-cache")
                if isinstance(self.ecosystem_config.get("registry", {}), dict)
                else "remote-cache",
                "ttlSeconds": self.registry_ttl_seconds,
                "queryCount": len(queries) if isinstance(queries, dict) else 0,
                "cacheFile": str(REGISTRY_CACHE_FILE),
                "registryUrl": self.registry_url,
            }
            return [ReadResourceContents(
                content=json.dumps(data, indent=2, ensure_ascii=False),
                mime_type="application/json",
            )]

        if uri == "antigravity://teams/traces":
            traces: list[dict[str, Any]] = []
            if TEAM_TRACE_FILE.exists():
                for line in TEAM_TRACE_FILE.read_text(encoding="utf-8").splitlines()[-50:]:
                    if not line.strip():
                        continue
                    try:
                        item = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if isinstance(item, dict):
                        traces.append(item)
            data = {"count": len(traces), "traces": traces}
            return [ReadResourceContents(
                content=json.dumps(data, indent=2, ensure_ascii=False),
                mime_type="application/json",
            )]

        if uri == "antigravity://observations/recent":
            return [ReadResourceContents(
                content=self._get_recent_observations(),
                mime_type="application/json",
            )]

        return [ReadResourceContents(
            content=f"Recurso no encontrado: {uri}",
            mime_type="text/plain",
        )]

    def _get_recent_observations(self) -> str:
        """Lee observaciones recientes del pipeline."""
        observations: list[dict] = []
        if not OBSERVATIONS_DIR.exists():
            return json.dumps({"observations": [], "note": "Pipeline no inicializado"})

        for obs_file in sorted(OBSERVATIONS_DIR.rglob("*.json"), reverse=True)[:20]:
            try:
                data = json.loads(obs_file.read_text(encoding="utf-8"))
                observations.append(data)
            except (OSError, json.JSONDecodeError):
                continue

        return json.dumps(
            {"observations": observations, "total_leidas": len(observations)},
            indent=2,
            ensure_ascii=False,
        )

    # ------------------------------------------------------------------
    # PROMPTS
    # ------------------------------------------------------------------

    def _register_prompts(self) -> None:
        """Registra Prompts MCP: workflows reutilizables para cualquier IA."""

        PROMPTS: list[Prompt] = [
            Prompt(
                name="architect",
                description="Diseña la arquitectura de un sistema o feature desde cero.",
                arguments=[
                    PromptArgument(
                        name="system",
                        description="Descripción del sistema a diseñar",
                        required=True,
                    ),
                    PromptArgument(
                        name="constraints",
                        description="Restricciones o requisitos no funcionales",
                        required=False,
                    ),
                ],
            ),
            Prompt(
                name="debug",
                description="Depura un error o comportamiento inesperado paso a paso.",
                arguments=[
                    PromptArgument(
                        name="error",
                        description="Mensaje de error o descripción del problema",
                        required=True,
                    ),
                    PromptArgument(
                        name="context",
                        description="Contexto adicional (código, logs, stack trace)",
                        required=False,
                    ),
                ],
            ),
            Prompt(
                name="review",
                description="Hace una revisión de código profunda con foco en seguridad y calidad.",
                arguments=[
                    PromptArgument(
                        name="code",
                        description="Código a revisar",
                        required=True,
                    ),
                    PromptArgument(
                        name="focus",
                        description="Área de foco: security | performance | maintainability | all",
                        required=False,
                    ),
                ],
            ),
            Prompt(
                name="plan",
                description="Descompone una tarea compleja en pasos accionables con estimaciones.",
                arguments=[
                    PromptArgument(
                        name="task",
                        description="Tarea o feature a planificar",
                        required=True,
                    ),
                ],
            ),
            Prompt(
                name="brainstorm",
                description="Genera múltiples enfoques creativos para resolver un problema.",
                arguments=[
                    PromptArgument(
                        name="problem",
                        description="Problema o desafío a resolver",
                        required=True,
                    ),
                    PromptArgument(
                        name="count",
                        description="Número de ideas a generar (default: 5)",
                        required=False,
                    ),
                ],
            ),
            Prompt(
                name="security-audit",
                description="Auditoría de seguridad OWASP Top 10 de un componente o sistema.",
                arguments=[
                    PromptArgument(
                        name="target",
                        description="Componente, endpoint o sistema a auditar",
                        required=True,
                    ),
                ],
            ),
            Prompt(
                name="find-agent",
                description="Encuentra el agente óptimo del ecosistema para una tarea específica.",
                arguments=[
                    PromptArgument(
                        name="task",
                        description="Descripción de la tarea",
                        required=True,
                    ),
                ],
            ),
        ]

        @self.server.list_prompts()
        async def list_prompts() -> list[Prompt]:
            return PROMPTS

        @self.server.get_prompt()
        async def get_prompt(name: str, arguments: dict[str, str] | None) -> GetPromptResult:
            return await self._get_prompt(name, arguments or {})

    async def _get_prompt(self, name: str, args: dict[str, str]) -> GetPromptResult:
        """Genera el contenido de un prompt específico."""

        if name == "architect":
            system = args.get("system", "sistema no especificado")
            constraints = args.get("constraints", "ninguna")
            return GetPromptResult(
                description=f"Arquitectura para: {system}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Actúa como el agente `architect` del ecosistema Antigravity. "
                                f"Diseña la arquitectura completa para: **{system}**.\n\n"
                                f"Restricciones: {constraints}\n\n"
                                f"Incluye:\n"
                                f"1. Diagrama de componentes (texto ASCII)\n"
                                f"2. Stack tecnológico recomendado con justificación\n"
                                f"3. Interfaces entre componentes\n"
                                f"4. Puntos de extensión futuros\n"
                                f"5. Riesgos y mitigaciones\n\n"
                                f"Usa las skills disponibles en el ecosistema cuando sea relevante."
                            ),
                        ),
                    )
                ],
            )

        if name == "debug":
            error = args.get("error", "error no especificado")
            context = args.get("context", "")
            return GetPromptResult(
                description=f"Debug: {error[:50]}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Actúa como el agente `debugger` de Antigravity. "
                                f"Depura el siguiente problema:\n\n"
                                f"**Error:** {error}\n\n"
                                f"**Contexto:** {context or 'No provisto'}\n\n"
                                f"Proceso:\n"
                                f"1. Hipótesis más probables (ordenadas por probabilidad)\n"
                                f"2. Pasos de diagnóstico específicos\n"
                                f"3. Solución recomendada con código\n"
                                f"4. Cómo prevenir este error en el futuro"
                            ),
                        ),
                    )
                ],
            )

        if name == "review":
            code = args.get("code", "")
            focus = args.get("focus", "all")
            return GetPromptResult(
                description="Revisión de código",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Actúa como el agente `security-auditor` de Antigravity. "
                                f"Revisa el siguiente código con foco en: **{focus}**\n\n"
                                f"```\n{code}\n```\n\n"
                                f"Evalúa:\n"
                                f"- Vulnerabilidades de seguridad (OWASP Top 10)\n"
                                f"- Calidad y mantenibilidad\n"
                                f"- Performance\n"
                                f"- Cobertura de tests necesaria\n"
                                f"Incluye severidad (CRÍTICA/ALTA/MEDIA/BAJA) para cada hallazgo."
                            ),
                        ),
                    )
                ],
            )

        if name == "plan":
            task = args.get("task", "tarea no especificada")
            return GetPromptResult(
                description=f"Plan para: {task[:50]}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Actúa como el agente `planner` de Antigravity. "
                                f"Descompón esta tarea en pasos accionables:\n\n"
                                f"**Tarea:** {task}\n\n"
                                f"Para cada paso incluye:\n"
                                f"- Descripción clara\n"
                                f"- Agente o skill de Antigravity más adecuada\n"
                                f"- Dependencias con otros pasos\n"
                                f"- Criterios de éxito\n\n"
                                f"Usa compose_skills para encontrar las skills relevantes."
                            ),
                        ),
                    )
                ],
            )

        if name == "brainstorm":
            problem = args.get("problem", "problema no especificado")
            count = args.get("count", "5")
            return GetPromptResult(
                description=f"Brainstorm: {problem[:50]}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Genera {count} enfoques creativos y distintos para resolver:\n\n"
                                f"**Problema:** {problem}\n\n"
                                f"Para cada enfoque:\n"
                                f"1. Nombre conciso\n"
                                f"2. Descripción en 2-3 oraciones\n"
                                f"3. Ventajas principales\n"
                                f"4. Riesgos o limitaciones\n"
                                f"5. Skills de Antigravity relevantes\n\n"
                                f"Varía radicalmente entre enfoques: tecnologías, paradigmas, escalas."
                            ),
                        ),
                    )
                ],
            )

        if name == "security-audit":
            target = args.get("target", "sistema no especificado")
            return GetPromptResult(
                description=f"Auditoría de: {target[:50]}",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Ejecuta una auditoría de seguridad completa de: **{target}**\n\n"
                                f"Chequea OWASP Top 10:\n"
                                f"A01 - Broken Access Control\n"
                                f"A02 - Cryptographic Failures\n"
                                f"A03 - Injection (SQL, XSS, command)\n"
                                f"A04 - Insecure Design\n"
                                f"A05 - Security Misconfiguration\n"
                                f"A06 - Vulnerable Components\n"
                                f"A07 - Auth & Session Failures\n"
                                f"A08 - Data Integrity Failures\n"
                                f"A09 - Logging & Monitoring Failures\n"
                                f"A10 - SSRF\n\n"
                                f"Para cada hallazgo: severidad, evidencia, remediación concreta."
                            ),
                        ),
                    )
                ],
            )

        if name == "find-agent":
            task = args.get("task", "tarea no especificada")
            agent_list = "\n".join(
                f"- **{k}**: {v['description']}" for k, v in list(self.agents.items())[:20]
            )
            return GetPromptResult(
                description="Selección de agente óptimo",
                messages=[
                    PromptMessage(
                        role="user",
                        content=TextContent(
                            type="text",
                            text=(
                                f"Tarea a realizar: **{task}**\n\n"
                                f"Agentes disponibles en Antigravity:\n{agent_list}\n\n"
                                f"Selecciona el agente más adecuado y explica por qué. "
                                f"Si la tarea requiere múltiples agentes, propón el equipo óptimo."
                            ),
                        ),
                    )
                ],
            )

        return GetPromptResult(
            description="Prompt no encontrado",
            messages=[
                PromptMessage(
                    role="user",
                    content=TextContent(type="text", text=f"Prompt '{name}' no existe."),
                )
            ],
        )

    # ------------------------------------------------------------------
    # SAMPLING (MCP v4.0 — IA dentro del servidor)
    # ------------------------------------------------------------------

    def _register_sampling(self) -> None:
        """Registra el handler de Sampling: el servidor pide inferencias al cliente."""

        @self.server.create_message()
        async def create_message(
            request: CreateMessageRequest,
        ) -> CreateMessageResult:
            """
            Sampling: Antigravity le pide al cliente (Claude, Cursor, etc.)
            que haga una inferencia LLM. Esto permite inteligencia IA dentro
            del servidor sin exponer API keys.
            """
            # En este handler el servidor puede enriquecer el contexto
            # antes de que el cliente lo procese.
            logger.info("Sampling request recibida con %d mensajes", len(request.messages))

            # El cliente MCP procesará esta request y devolverá el resultado.
            # Aquí inyectamos contexto del ecosistema si es relevante.
            system_context = (
                f"Eres parte del ecosistema Antigravity v2.1.0 con acceso a "
                f"{len(self.skills)} skills y {len(self.agents)} agentes especializados. "
                f"Responde siempre en español con precisión técnica."
            )

            return CreateMessageResult(
                role="assistant",
                content=TextContent(
                    type="text",
                    text=f"[Sampling via Antigravity MCP]\nContexto: {system_context}",
                ),
                model="claude-sonnet-4-6",
                stopReason="endTurn",
            )

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    async def run(self) -> None:
        """Inicia el servidor MCP con transporte stdio."""
        logger.info("Antigravity MCP Server v4.0 iniciando (stdio)...")

        # InitializationOptions y ServerCapabilities pueden no existir en versiones
        # nuevas del SDK MCP — el servidor funciona sin ellas (el SDK las genera)
        init_options = None
        if InitializationOptions is not None and ServerCapabilities is not None:
            capabilities = ServerCapabilities(
                tools={},
                resources={"subscribe": False, "listChanged": False},
                prompts={"listChanged": False},
            )
            init_options = InitializationOptions(
                server_name="antigravity",
                server_version="4.0.0",
                capabilities=capabilities,
            )

        async with stdio_server() as (read_stream, write_stream):
            if init_options is not None:
                await self.server.run(read_stream, write_stream, init_options)
            else:
                await self.server.run(read_stream, write_stream)


def main() -> None:
    """Entry point principal."""
    server = AntigravityMCPServer()
    try:
        asyncio.run(server.run())
    except KeyboardInterrupt:
        logger.info("Servidor interrumpido por usuario")
    except Exception as e:
        logger.error("Error fatal: %s", e, exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
