#!/usr/bin/env python3
"""
Antigravity HTTP Gateway v1.0 — Acceso universal al ecosistema.

Features:
- Agent Card A2A (/.well-known/agent.json) — discovery estándar
- REST API para skills y agentes
- Streaming SSE de respuestas (token-by-token)
- CORS restringido por origen (configurable)
- Auth opcional via `X-API-Key` (fallback localhost si no hay key)
- Health check y estadísticas

Uso:
    python mcp-server/http_gateway.py
    python mcp-server/http_gateway.py --port 8888 --host 0.0.0.0

Endpoints:
    GET  /.well-known/agent.json    Agent Card A2A estándar
    GET  /health                    Health check
    GET  /v1/skills                 Listar skills
    GET  /v1/agents                 Listar agentes
    GET  /v1/skills/search?q=...    Buscar skills
    POST /v1/skills/compose         Pipeline de skills para una tarea
    GET  /v1/stats                  Estadísticas del ecosistema
    GET  /v1/memory/{resource}      Leer recursos de memoria
    GET  /openapi.json              Schema OpenAPI 3.1
"""

from __future__ import annotations

import argparse
import asyncio
import hmac
import importlib.util
import json
import logging
import os
import sys
try:
    from datetime import datetime, UTC
except ImportError:  # Python < 3.11
    from datetime import datetime, timezone
    UTC = timezone.utc
from pathlib import Path

SECURITY_UTILS_PATH = Path(__file__).with_name("security_utils.py")
SECURITY_UTILS_SPEC = importlib.util.spec_from_file_location(
    "mcp_server_security_utils",
    SECURITY_UTILS_PATH,
)
if SECURITY_UTILS_SPEC is None or SECURITY_UTILS_SPEC.loader is None:
    raise RuntimeError("Unable to load mcp-server/security_utils.py")
_security_utils = importlib.util.module_from_spec(SECURITY_UTILS_SPEC)
SECURITY_UTILS_SPEC.loader.exec_module(_security_utils)
is_localhost_client = _security_utils.is_localhost_client
is_origin_allowed = _security_utils.is_origin_allowed
parse_cors_origins = _security_utils.parse_cors_origins

# Dependencia: aiohttp (ligera, sin necesidad de FastAPI/uvicorn)
try:
    from aiohttp import web
    from aiohttp.web import Request, Response, StreamResponse
except ImportError:
    print("Error: aiohttp no instalado. Instalar con: pip install aiohttp", file=sys.stderr)
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Rutas del proyecto
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent
SKILLS_DIR = PROJECT_ROOT / ".agent" / "skills"
AGENTS_DIR = PROJECT_ROOT / ".agent" / "agents"
WORKFLOWS_DIR = PROJECT_ROOT / ".agent" / "workflows"
CONTEXT_DIR = PROJECT_ROOT / ".context"
OBSERVATIONS_DIR = PROJECT_ROOT / ".antigravity" / "observations"
API_KEY = os.environ.get("ANTIGRAVITY_API_KEY", "")
# Cuando True, replica el comportamiento legado: requests desde localhost no
# requieren API key incluso si ANTIGRAVITY_API_KEY no está configurada.
# Activar explícitamente con ANTIGRAVITY_ALLOW_LOCALHOST_NOAUTH=true en desarrollo.
# En producción debe permanecer False (valor por defecto).
ALLOW_LOCALHOST_NOAUTH: bool = (
    os.environ.get("ANTIGRAVITY_ALLOW_LOCALHOST_NOAUTH", "false").lower() == "true"
)
PUBLIC_PATHS = {"/.well-known/agent.json", "/health", "/openapi.json"}


def _read_safe(path: Path, max_bytes: int = 50_000) -> str:
    try:
        text = path.read_text(encoding="utf-8")
        if len(text) > max_bytes:
            text = text[:max_bytes] + "\n\n[... truncado ...]"
        return text
    except (OSError, UnicodeDecodeError) as e:
        return f"Error: {e}"


def _extract_description(md_path: Path, max_len: int = 300) -> str:
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


# ---------------------------------------------------------------------------
# Discovery del ecosistema
# ---------------------------------------------------------------------------


def discover_skills() -> dict[str, dict]:
    skills: dict[str, dict] = {}
    if not SKILLS_DIR.exists():
        return skills
    for skill_dir in sorted(SKILLS_DIR.iterdir()):
        if not skill_dir.is_dir() or skill_dir.name.startswith("."):
            continue
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            main_script = next(scripts_dir.glob("*.py"), None)
            if main_script:
                skills[skill_dir.name] = {
                    "name": skill_dir.name,
                    "description": _extract_description(skill_dir / "SKILL.md")
                    or f"Skill: {skill_dir.name}",
                    "script": str(main_script),
                }
    return skills


def discover_agents() -> dict[str, dict]:
    agents: dict[str, dict] = {}
    if not AGENTS_DIR.exists():
        return agents
    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
            continue
        for doc_name in ("SYSTEM_PROMPT.md", "IDENTITY.md"):
            doc = agent_dir / doc_name
            if doc.exists():
                agents[agent_dir.name] = {
                    "name": agent_dir.name,
                    "description": _extract_description(doc) or f"Agente: {agent_dir.name}",
                    "doc_file": str(doc),
                }
                break
    return agents


# ---------------------------------------------------------------------------
# Handlers HTTP
# ---------------------------------------------------------------------------


class AntiqravityGateway:
    """Gateway HTTP con Agent Card, REST API y SSE streaming."""

    def __init__(self) -> None:
        self.skills = discover_skills()
        self.agents = discover_agents()
        self.started_at = datetime.now(UTC).isoformat().replace("+00:00", "Z")
        self.allowed_origins = self._load_allowed_origins()
        logger.info(
            "Gateway iniciado: %d skills | %d agentes",
            len(self.skills),
            len(self.agents),
        )

    def _load_allowed_origins(self) -> list[str]:
        return parse_cors_origins(os.environ.get("ANTIGRAVITY_CORS_ORIGINS"))

    def _is_origin_allowed(self, origin: str) -> bool:
        return is_origin_allowed(origin, self.allowed_origins)

    def _cors_headers(self, request: Request | None = None) -> dict[str, str]:
        headers = {
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
            "Access-Control-Allow-Headers": "Content-Type, Authorization, X-API-Key",
        }
        if "*" in self.allowed_origins:
            headers["Access-Control-Allow-Origin"] = "*"
            return headers

        if request is None:
            return headers

        origin = request.headers.get("Origin", "")
        if self._is_origin_allowed(origin):
            headers["Access-Control-Allow-Origin"] = origin
            headers["Vary"] = "Origin"
        return headers

    def _json(self, data: object, status: int = 200, request: Request | None = None) -> Response:
        return Response(
            body=json.dumps(data, ensure_ascii=False, indent=2),
            status=status,
            content_type="application/json",
            headers=self._cors_headers(request),
        )

    def _check_auth(self, request: Request) -> Response | None:
        """Verifica autenticación de la request.

        Lógica:
        - Rutas públicas (PUBLIC_PATHS) no requieren auth.
        - Si ANTIGRAVITY_API_KEY está configurada, toda request privada debe
          incluir el header X-API-Key con el valor correcto (timing-safe).
        - Si no hay API_KEY configurada:
            - Con ANTIGRAVITY_ALLOW_LOCALHOST_NOAUTH=true (modo desarrollo),
              las requests desde localhost pasan sin key (comportamiento legado).
            - Sin ese flag (producción por defecto), retorna 401 siempre para
              forzar la configuración explícita de una API key.

        Args:
            request: Request HTTP entrante de aiohttp.

        Returns:
            None si la autenticación es válida, Response de error en caso contrario.
        """
        path = request.path
        if path in PUBLIC_PATHS:
            return None

        client_ip = request.remote or ""

        if not API_KEY:
            if ALLOW_LOCALHOST_NOAUTH and is_localhost_client(client_ip):
                return None
            return self._json(
                {"error": "Unauthorized: configure ANTIGRAVITY_API_KEY"},
                status=401,
                request=request,
            )

        provided = request.headers.get("X-API-Key", "")
        if not provided:
            return self._json(
                {"error": "Unauthorized: X-API-Key header required"},
                status=401,
                request=request,
            )
        if not hmac.compare_digest(provided, API_KEY):
            return self._json({"error": "Forbidden: invalid API key"}, status=403, request=request)
        return None

    # ----------------------------------------------------------------
    # Agent Card A2A estándar
    # ----------------------------------------------------------------

    async def handle_agent_card(self, request: Request) -> Response:
        """
        GET /.well-known/agent.json

        Agent Card siguiendo el estándar Google A2A (2025).
        Permite que cualquier orquestador externo descubra y use el ecosistema.
        Ref: https://google.github.io/A2A/
        """
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error

        host = request.host or "127.0.0.1:8080"
        base_url = f"http://{host}"

        card = {
            "schema_version": "1.0",
            "name": "Antigravity Ecosystem",
            "description": (
                "Ecosistema autónomo de agentes IA empresarial con 940 skills, "
                "40 agentes especializados en 12 tiers, y soporte multi-LLM. "
                "Accesible vía MCP (stdio/HTTP/SSE) desde cualquier IDE o agente externo."
            ),
            "url": base_url,
            "version": "2.1.0",
            "provider": {
                "organization": "OpenAntigravity",
                "contact": "https://github.com/jokken79/OpenAntigravity",
            },
            "capabilities": {
                "streaming": True,
                "push_notifications": False,
                "state_management": {
                    "supports": True,
                    "storage": ["sqlite", "chromadb"],
                },
                "mcp": {
                    "version": "2024-11-05",
                    "transports": ["stdio", "http", "sse"],
                    "primitives": ["tools", "resources", "prompts", "sampling"],
                },
                "multi_llm": {
                    "providers": ["claude", "openai", "google", "ollama"],
                    "auto_detection": True,
                },
            },
            "authentication": {
                "schemes": ["none", "bearer"],
                "optional": True,
            },
            "default_input_modes": ["text/plain", "application/json"],
            "default_output_modes": ["text/plain", "application/json", "text/event-stream"],
            "skills": [
                {
                    "id": f"skill/{name}",
                    "name": name,
                    "description": info["description"],
                    "tags": self._infer_tags(name),
                    "examples": [f"Ejecutar skill {name}"],
                    "input_modes": ["text/plain"],
                    "output_modes": ["text/plain"],
                }
                for name, info in list(self.skills.items())[:50]  # Top 50 para el card
            ],
            "agents": [
                {
                    "id": f"agent/{name}",
                    "name": name,
                    "description": info["description"],
                    "endpoint": f"{base_url}/v1/agents/{name}",
                }
                for name, info in self.agents.items()
            ],
            "endpoints": {
                "rest_api": f"{base_url}/v1",
                "health": f"{base_url}/health",
                "openapi": f"{base_url}/openapi.json",
                "mcp_sse": f"{base_url}/v1/mcp/sse",
                "skills_list": f"{base_url}/v1/skills",
                "agents_list": f"{base_url}/v1/agents",
                "compose": f"{base_url}/v1/skills/compose",
            },
        }

        return self._json(card, request=request)

    def _infer_tags(self, skill_name: str) -> list[str]:
        """Infiere tags de una skill a partir de su nombre."""
        tag_map = {
            "security": ["security", "owasp"],
            "test": ["testing", "quality"],
            "docker": ["devops", "containers"],
            "api": ["backend", "api"],
            "react": ["frontend", "react"],
            "python": ["backend", "python"],
            "database": ["database", "data"],
            "sql": ["database", "sql"],
            "typescript": ["frontend", "typescript"],
            "ai": ["ai", "ml"],
            "ml": ["ai", "ml"],
            "k8s": ["devops", "kubernetes"],
            "kubernetes": ["devops", "kubernetes"],
        }
        tags: list[str] = []
        name_lower = skill_name.lower()
        for keyword, assigned_tags in tag_map.items():
            if keyword in name_lower:
                tags.extend(assigned_tags)
        return list(set(tags)) or ["general"]

    # ----------------------------------------------------------------
    # Health
    # ----------------------------------------------------------------

    async def handle_health(self, request: Request) -> Response:
        """GET /health"""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error

        return self._json(
            {
                "status": "ok",
                "version": "2.1.0",
                "started_at": self.started_at,
                "skills": len(self.skills),
                "agents": len(self.agents),
            },
            request=request,
        )

    # ----------------------------------------------------------------
    # Skills
    # ----------------------------------------------------------------

    async def handle_list_skills(self, request: Request) -> Response:
        """GET /v1/skills — Lista todas las skills."""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error

        search = request.rel_url.query.get("q", "").lower()
        try:
            offset = max(int(request.rel_url.query.get("offset", 0)), 0)
        except ValueError:
            offset = 0
        try:
            limit = min(max(int(request.rel_url.query.get("limit", 50)), 1), 200)
        except ValueError:
            limit = 50

        skills_list = [
            {"name": k, "description": v["description"]}
            for k, v in self.skills.items()
            if not search or search in k.lower() or search in v["description"].lower()
        ]
        total = len(skills_list)
        page = skills_list[offset : offset + limit]

        return self._json(
            {
                "skills": page,
                "total": total,
                "offset": offset,
                "limit": limit,
            },
            request=request,
        )

    async def handle_get_skill(self, request: Request) -> Response:
        """GET /v1/skills/{name} — Detalle de una skill."""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error

        name = request.match_info["name"]
        if name not in self.skills:
            return self._json({"error": f"Skill '{name}' no encontrada"}, status=404, request=request)
        info = self.skills[name]
        skill_dir = SKILLS_DIR / name
        skill_md = skill_dir / "SKILL.md"
        return self._json(
            {
                "name": name,
                "description": info["description"],
                "documentation": _read_safe(skill_md) if skill_md.exists() else None,
            },
            request=request,
        )

    # ----------------------------------------------------------------
    # Agents
    # ----------------------------------------------------------------

    async def handle_list_agents(self, request: Request) -> Response:
        """GET /v1/agents — Lista todos los agentes."""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error

        return self._json(
            {
                "agents": [
                    {"name": k, "description": v["description"]}
                    for k, v in self.agents.items()
                ],
                "total": len(self.agents),
            },
            request=request,
        )

    async def handle_get_agent(self, request: Request) -> Response:
        """GET /v1/agents/{name} — Detalle de un agente."""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error

        name = request.match_info["name"]
        if name not in self.agents:
            return self._json({"error": f"Agente '{name}' no encontrado"}, status=404, request=request)
        info = self.agents[name]
        return self._json(
            {
                "name": name,
                "description": info["description"],
                "identity": _read_safe(Path(info["doc_file"])),
            },
            request=request,
        )

    # ----------------------------------------------------------------
    # Compose skills
    # ----------------------------------------------------------------

    async def handle_compose_skills(self, request: Request) -> Response:
        """POST /v1/skills/compose — Sugiere pipeline de skills para una tarea."""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error

        try:
            body = await request.json()
        except Exception:
            return self._json({"error": "Body JSON inválido"}, status=400, request=request)

        task = body.get("task", "").strip()
        if not task:
            return self._json({"error": "Campo 'task' requerido"}, status=400, request=request)

        try:
            max_skills = min(max(int(body.get("max_skills", 5)), 1), 10)
        except (TypeError, ValueError):
            max_skills = 5
        task_lower = task.lower()
        scored: list[tuple[int, str, str]] = []

        for name, info in self.skills.items():
            score = sum(
                3 if w in name.lower() else 1 if w in info["description"].lower() else 0
                for w in task_lower.split()
                if len(w) >= 3
            )
            if score > 0:
                scored.append((score, name, info["description"]))

        scored.sort(key=lambda x: -x[0])
        pipeline = [
            {
                "step": i + 1,
                "skill": name,
                "description": desc,
                "relevance_score": score,
            }
            for i, (score, name, desc) in enumerate(scored[:max_skills])
        ]

        return self._json(
            {
                "task": task,
                "pipeline": pipeline,
                "instruction": (
                    "Ejecuta cada skill en secuencia. "
                    "El output de cada paso puede alimentar el siguiente."
                ),
            },
            request=request,
        )

    # ----------------------------------------------------------------
    # Memory resources
    # ----------------------------------------------------------------

    async def handle_memory(self, request: Request) -> Response:
        """GET /v1/memory/{resource} — Recursos de conocimiento."""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error

        resource = request.match_info["resource"]
        resource_map = {
            "app-knowledge": CONTEXT_DIR / "APP_KNOWLEDGE.md",
            "learnings": CONTEXT_DIR / "LEARNINGS.md",
            "architecture": PROJECT_ROOT / ".agent" / "ARCHITECTURE.md",
            "rules": PROJECT_ROOT / ".antigravity" / "rules.md",
        }
        if resource not in resource_map:
            return self._json(
                {
                    "error": f"Recurso '{resource}' no existe",
                    "available": list(resource_map.keys()),
                },
                status=404,
                request=request,
            )
        path = resource_map[resource]
        return Response(
            body=_read_safe(path),
            content_type="text/markdown",
            headers=self._cors_headers(request),
        )

    # ----------------------------------------------------------------
    # Brain Network
    # ----------------------------------------------------------------

    def _get_brain_network(self):
        """Lazy-init del BrainNetwork."""
        if not hasattr(self, "_brain_network"):
            try:
                import sys as _sys
                agent_dir = str(PROJECT_ROOT / ".agent")
                if agent_dir not in _sys.path:
                    _sys.path.insert(0, agent_dir)
                from core.brain_network import BrainNetwork
                self._brain_network = BrainNetwork(PROJECT_ROOT)
            except Exception as e:
                logger.warning("BrainNetwork no disponible: %s", e)
                self._brain_network = None
        return self._brain_network

    async def handle_brain_query(self, request: Request) -> Response:
        """GET /v1/brain/query?q=<question>&limit=10"""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error
        network = self._get_brain_network()
        if not network:
            return self._json({"error": "BrainNetwork no disponible"}, status=503, request=request)
        question = request.query.get("q", "")
        limit = int(request.query.get("limit", "10"))
        if not question:
            return self._json({"error": "q es requerido"}, status=400, request=request)
        results = network.query_network(question, limit=limit)
        return self._json({
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
                    "context": r.node.context[:300] if r.node.context else "",
                    "relevance": round(r.relevance_score, 2),
                }
                for r in results
            ],
        }, request=request)

    async def handle_brain_ingest(self, request: Request) -> Response:
        """POST /v1/brain/ingest {title, context, area, tags, ...}"""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error
        network = self._get_brain_network()
        if not network:
            return self._json({"error": "BrainNetwork no disponible"}, status=503, request=request)
        try:
            body = await request.json()
        except Exception:
            return self._json({"error": "JSON invalido"}, status=400, request=request)
        title = body.get("title", "")
        if not title:
            return self._json({"error": "title requerido"}, status=400, request=request)
        node = network.mother.ingest(
            title=title,
            context=body.get("context", ""),
            decisions=body.get("decisions", ""),
            area=body.get("area", "general"),
            tags=body.get("tags", []),
            node_type=body.get("node_type", "session"),
            importance=body.get("importance", "normal"),
        )
        return self._json({
            "success": True,
            "slug": node.slug,
            "title": node.title,
            "related": node.related,
        }, request=request)

    async def handle_brain_stats(self, request: Request) -> Response:
        """GET /v1/brain/stats"""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error
        network = self._get_brain_network()
        if not network:
            return self._json({"error": "BrainNetwork no disponible"}, status=503, request=request)
        return self._json({"success": True, **network.network_stats()}, request=request)

    # ----------------------------------------------------------------
    # Stats
    # ----------------------------------------------------------------

    async def handle_stats(self, request: Request) -> Response:
        """GET /v1/stats"""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error

        return self._json(
            {
                "version": "2.1.0",
                "skills": len(self.skills),
                "agents": len(self.agents),
                "mcp_capabilities": ["tools", "resources", "prompts", "sampling"],
                "transports": ["stdio", "http", "sse"],
                "llms_supported": ["claude", "openai", "gemini", "ollama"],
                "uptime_since": self.started_at,
            },
            request=request,
        )

    # ----------------------------------------------------------------
    # OpenAPI schema
    # ----------------------------------------------------------------

    async def handle_openapi(self, request: Request) -> Response:
        """GET /openapi.json — Schema OpenAPI 3.1"""
        auth_error = self._check_auth(request)
        if auth_error:
            return auth_error

        host = request.host or "127.0.0.1:8080"
        schema = {
            "openapi": "3.1.0",
            "info": {
                "title": "Antigravity Ecosystem API",
                "version": "2.1.0",
                "description": (
                    "API REST del ecosistema Antigravity. "
                    "Acceso a 940 skills y 40 agentes especializados."
                ),
            },
            "servers": [{"url": f"http://{host}"}],
            "paths": {
                "/.well-known/agent.json": {
                    "get": {
                        "summary": "Agent Card A2A",
                        "description": "Descriptor estándar del ecosistema para orquestadores externos.",
                        "responses": {"200": {"description": "Agent Card JSON"}},
                    }
                },
                "/health": {
                    "get": {
                        "summary": "Health check",
                        "responses": {"200": {"description": "Estado del servidor"}},
                    }
                },
                "/v1/skills": {
                    "get": {
                        "summary": "Listar skills",
                        "parameters": [
                            {
                                "name": "q",
                                "in": "query",
                                "description": "Búsqueda por nombre o descripción",
                                "schema": {"type": "string"},
                            },
                            {"name": "offset", "in": "query", "schema": {"type": "integer"}},
                            {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                        ],
                        "responses": {"200": {"description": "Lista de skills"}},
                    }
                },
                "/v1/skills/compose": {
                    "post": {
                        "summary": "Componer pipeline de skills",
                        "requestBody": {
                            "content": {
                                "application/json": {
                                    "schema": {
                                        "type": "object",
                                        "properties": {
                                            "task": {"type": "string"},
                                            "max_skills": {"type": "integer", "default": 5},
                                        },
                                        "required": ["task"],
                                    }
                                }
                            }
                        },
                        "responses": {"200": {"description": "Pipeline de skills recomendado"}},
                    }
                },
                "/v1/agents": {
                    "get": {
                        "summary": "Listar agentes",
                        "responses": {"200": {"description": "Lista de agentes"}},
                    }
                },
                "/v1/agents/{name}": {
                    "get": {
                        "summary": "Detalle de agente",
                        "parameters": [
                            {"name": "name", "in": "path", "required": True, "schema": {"type": "string"}}
                        ],
                        "responses": {"200": {"description": "Información del agente"}},
                    }
                },
                "/v1/memory/{resource}": {
                    "get": {
                        "summary": "Recursos de memoria del ecosistema",
                        "parameters": [
                            {
                                "name": "resource",
                                "in": "path",
                                "required": True,
                                "schema": {
                                    "type": "string",
                                    "enum": ["app-knowledge", "learnings", "architecture", "rules"],
                                },
                            }
                        ],
                        "responses": {"200": {"description": "Contenido Markdown del recurso"}},
                    }
                },
                "/v1/stats": {
                    "get": {
                        "summary": "Estadísticas del ecosistema",
                        "responses": {"200": {"description": "Métricas en tiempo real"}},
                    }
                },
            },
        }
        return self._json(schema, request=request)

    # ----------------------------------------------------------------
    # CORS preflight
    # ----------------------------------------------------------------

    async def handle_options(self, request: Request) -> Response:
        return Response(status=204, headers=self._cors_headers(request))

    # ----------------------------------------------------------------
    # App
    # ----------------------------------------------------------------

    def build_app(self) -> web.Application:
        app = web.Application()
        app.router.add_route("OPTIONS", "/{path_info:.*}", self.handle_options)
        app.router.add_get("/.well-known/agent.json", self.handle_agent_card)
        app.router.add_get("/health", self.handle_health)
        app.router.add_get("/v1/skills", self.handle_list_skills)
        app.router.add_get("/v1/skills/{name}", self.handle_get_skill)
        app.router.add_post("/v1/skills/compose", self.handle_compose_skills)
        app.router.add_get("/v1/agents", self.handle_list_agents)
        app.router.add_get("/v1/agents/{name}", self.handle_get_agent)
        app.router.add_get("/v1/memory/{resource}", self.handle_memory)
        app.router.add_get("/v1/brain/query", self.handle_brain_query)
        app.router.add_post("/v1/brain/ingest", self.handle_brain_ingest)
        app.router.add_get("/v1/brain/stats", self.handle_brain_stats)
        app.router.add_get("/v1/stats", self.handle_stats)
        app.router.add_get("/openapi.json", self.handle_openapi)
        return app


def main() -> None:
    parser = argparse.ArgumentParser(description="Antigravity HTTP Gateway")
    parser.add_argument("--host", default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8080, help="Puerto (default: 8080)")
    args = parser.parse_args()

    gateway = AntiqravityGateway()
    app = gateway.build_app()

    logger.info("Antigravity HTTP Gateway en http://%s:%d", args.host, args.port)
    logger.info("CORS permitido: %s", ", ".join(gateway.allowed_origins))
    if API_KEY:
        logger.info("Auth API key: ACTIVADA")
    elif ALLOW_LOCALHOST_NOAUTH:
        logger.warning(
            "Auth API key: DESACTIVADA (modo desarrollo). "
            "Endpoints privados aceptan clientes localhost sin key. "
            "Configurar ANTIGRAVITY_API_KEY para producción."
        )
    else:
        logger.warning(
            "Auth API key: DESACTIVADA. "
            "Todos los endpoints privados retornan 401. "
            "Configurar ANTIGRAVITY_API_KEY o activar "
            "ANTIGRAVITY_ALLOW_LOCALHOST_NOAUTH=true para desarrollo local."
        )
    logger.info("Agent Card: http://%s:%d/.well-known/agent.json", args.host, args.port)
    logger.info("OpenAPI:    http://%s:%d/openapi.json", args.host, args.port)

    web.run_app(app, host=args.host, port=args.port, access_log=None)


if __name__ == "__main__":
    main()
