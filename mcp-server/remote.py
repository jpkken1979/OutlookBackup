#!/usr/bin/env python3
"""
Antigravity MCP Remote Server v3.0
===================================
Servidor MCP remoto con Streamable HTTP transport (spec 2025-03-26).

Expone el ecosistema completo como servidor MCP estandar:
- 11 Tools: list_skills, search_skills, run_skill, list_agents,
            list_workflows, list_commands, get_agent_prompt, get_workflow,
            get_command, compose_skills, get_ecosystem_stats
- 7 Resources: catalogo de skills/agentes/workflows, memoria, arquitectura
- 7 Prompts: architect, debug, review, plan, brainstorm, security-audit, find-agent

Desplegado en: https://mcp.uns-kikaku.cloud/mcp

Uso:
    python remote.py                                    # Puerto 3777, requiere token
    python remote.py --port 8080                        # Puerto custom
    ANTIGRAVITY_API_TOKEN=xxx python remote.py          # Con auth (recomendado)
    python remote.py --no-auth                          # Sin auth (solo desarrollo local)

Conectar desde cualquier IDE:
    {
        "mcpServers": {
            "antigravity": {
                "url": "https://mcp.uns-kikaku.cloud/mcp",
                "headers": {
                    "Authorization": "Bearer TU_TOKEN"
                }
            }
        }
    }
"""

import contextlib
import importlib.util
import logging
import os
import secrets
import sys
from collections.abc import AsyncIterator
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
shared_build_cors_policy = _security_utils.build_cors_policy
parse_cors_origins = _security_utils.parse_cors_origins

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger("antigravity.mcp.remote")

# ---------------------------------------------------------------------------
# Imports del SDK MCP y Starlette
# ---------------------------------------------------------------------------
try:
    import uvicorn
    from mcp.server.streamable_http_manager import StreamableHTTPSessionManager
    from starlette.applications import Starlette
    from starlette.middleware.cors import CORSMiddleware
    from starlette.requests import Request
    from starlette.responses import JSONResponse
    from starlette.routing import Mount, Route
    from starlette.types import Receive, Scope, Send
except ImportError as e:
    logger.error(
        "Dependencias faltantes: %s\n"
        "Instala con: pip install 'mcp>=1.8.0' uvicorn starlette",
        e,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Importar server.py v4.0 (reutiliza 100%% de tools/resources/prompts)
# ---------------------------------------------------------------------------

# Asegurar que el directorio de mcp-server/ está en sys.path para que
# `from server import ...` funcione independientemente del CWD
# (Docker WORKDIR es /app, pero server.py está en /app/mcp-server/).
_mcp_server_dir = str(Path(__file__).parent)
if _mcp_server_dir not in sys.path:
    sys.path.insert(0, _mcp_server_dir)

try:
    from server import AntigravityMCPServer  # noqa: E402
except ImportError as e:
    logger.error(
        "No se pudo importar server.py: %s\n"
        "Asegurate de que mcp-server/server.py existe y sus dependencias estan instaladas.",
        e,
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
API_TOKEN = os.environ.get("ANTIGRAVITY_API_TOKEN", "")
ALLOW_NO_AUTH_DEFAULT = os.environ.get("ANTIGRAVITY_ALLOW_NO_AUTH", "0") == "1"


def _build_cors_policy(origins: list[str] | None) -> tuple[list[str], str | None]:
    """Compat wrapper para tests internos."""
    return shared_build_cors_policy(origins)


# ---------------------------------------------------------------------------
# HTTP Handlers (endpoints fuera de MCP)
# ---------------------------------------------------------------------------
async def handle_health(request: Request) -> JSONResponse:
    """GET /health - Health check (sin auth)."""
    return JSONResponse({
        "status": "healthy",
        "server": "antigravity-mcp",
        "version": "3.0.0",
        "ecosystem": "2.1.0",
        "transport": "streamable-http",
        "auth_required": bool(API_TOKEN),
    })


async def handle_root(request: Request) -> JSONResponse:
    """GET / - Info del servidor."""
    return JSONResponse({
        "server": "Antigravity MCP Remote Server",
        "version": "3.0.0",
        "ecosystem": "2.1.0",
        "transport": "streamable-http",
        "mcp_endpoint": "/mcp",
        "auth_required": bool(API_TOKEN),
        "capabilities": {
            "tools": 11,
            "resources": 8,
            "prompts": 7,
        },
        "connect": {
            "url": "https://mcp.uns-kikaku.cloud/mcp",
            "docs": "https://github.com/jokken79/OpenAntigravity/blob/main/CONNECT.md",
        },
    })


# ---------------------------------------------------------------------------
# Auth Middleware (ASGI)
# ---------------------------------------------------------------------------
class BearerAuthMiddleware:
    """ASGI middleware para autenticacion Bearer token.

    Solo protege /mcp. Los endpoints /health y / son publicos.
    """

    PUBLIC_PATHS = ("/health", "/", "/favicon.ico")

    def __init__(self, app: object, *, token: str = "", allow_no_auth: bool = False) -> None:
        self.app = app
        self.token = token
        self.allow_no_auth = allow_no_auth

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")

        # Endpoints publicos
        if path in self.PUBLIC_PATHS:
            await self.app(scope, receive, send)
            return

        # No token configurado: solo permitido si el operador lo habilita explícitamente.
        if not self.token:
            if not self.allow_no_auth:
                response = JSONResponse(
                    {"error": "Server misconfigured: ANTIGRAVITY_API_TOKEN is required"},
                    status_code=503,
                )
                await response(scope, receive, send)
                return
            await self.app(scope, receive, send)
            return

        # Extraer Authorization header
        headers = dict(scope.get("headers", []))
        auth_value = headers.get(b"authorization", b"").decode("utf-8", errors="ignore")

        if not auth_value.startswith("Bearer "):
            response = JSONResponse(
                {"error": "Unauthorized: Bearer token required"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        provided_token = auth_value[7:]
        if not secrets.compare_digest(provided_token, self.token):
            response = JSONResponse(
                {"error": "Unauthorized: Invalid token"},
                status_code=401,
            )
            await response(scope, receive, send)
            return

        await self.app(scope, receive, send)


# ---------------------------------------------------------------------------
# Server Factory
# ---------------------------------------------------------------------------
def create_app(
    *,
    host: str = "127.0.0.1",
    port: int = 3777,
    json_response: bool = True,
    allow_no_auth: bool = False,
    cors_origins: list[str] | None = None,
) -> tuple:
    """Crea la aplicacion ASGI completa con MCP + auth + health.

    Returns:
        Tuple de (asgi_app, lifespan_context)
    """
    # 1. Crear el servidor MCP con todas las capacidades de server.py v4.0
    logger.info("Inicializando ecosistema Antigravity MCP...")
    mcp = AntigravityMCPServer()

    # 2. Crear el session manager para Streamable HTTP (stateless = escalable)
    session_manager = StreamableHTTPSessionManager(
        app=mcp.server,
        event_store=None,
        json_response=json_response,
        stateless=True,
    )

    # 3. Handler ASGI para el endpoint /mcp
    async def handle_mcp(scope: Scope, receive: Receive, send: Send) -> None:
        await session_manager.handle_request(scope, receive, send)

    # 4. Lifespan (startup/shutdown)
    @contextlib.asynccontextmanager
    async def lifespan(app: Starlette) -> AsyncIterator[None]:
        async with session_manager.run():
            auth_status = "ACTIVADA" if API_TOKEN else "DESACTIVADA (--no-auth)"
            logger.info(
                "\n"
                "  Antigravity MCP Remote Server v3.0\n"
                "  ====================================\n"
                "  Skills:     %d\n"
                "  Agentes:    %d\n"
                "  Workflows:  %d\n"
                "  Auth:       %s\n"
                "  Transport:  Streamable HTTP (stateless)\n"
                "  \n"
                "  Endpoints:\n"
                "    MCP:     http://%s:%d/mcp  (POST/GET/DELETE)\n"
                "    Health:  http://%s:%d/health\n"
                "    Info:    http://%s:%d/\n"
                "  \n"
                "  Conectar IDE:\n"
                '    {"mcpServers": {"antigravity": {\n'
                '      "url": "https://mcp.uns-kikaku.cloud/mcp",\n'
                '      "headers": {"Authorization": "Bearer TU_TOKEN"}\n'
                "    }}}\n",
                len(mcp.skills),
                len(mcp.agents),
                len(mcp.workflows),
                auth_status,
                host, port,
                host, port,
                host, port,
            )
            if not API_TOKEN and allow_no_auth:
                logger.warning(
                    "SEGURIDAD: servidor MCP remoto sin autenticacion. Solo usar en desarrollo local."
                )
            allowed_origins, _allow_origin_regex = _build_cors_policy(cors_origins)
            logger.info("CORS permitido: %s", ", ".join(allowed_origins))
            yield

    # 5. Starlette app con rutas
    starlette_app = Starlette(
        routes=[
            Route("/", handle_root),
            Route("/health", handle_health),
            Mount("/mcp", app=handle_mcp),
        ],
        lifespan=lifespan,
    )

    # 5b. Wrapper ASGI que reescribe /mcp → /mcp/ para evitar 307 redirect
    #     Mount("/mcp") de Starlette redirige /mcp → /mcp/ con 307, lo cual
    #     rompe clientes MCP que usan /mcp sin trailing slash.
    async def app_with_rewrite(scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            scope = dict(scope, path="/mcp/")
        await starlette_app(scope, receive, send)

    # 6. CORS (outermost — maneja OPTIONS antes de auth)
    allowed_origins, allow_origin_regex = _build_cors_policy(cors_origins)
    cors_app = CORSMiddleware(
        app_with_rewrite,
        allow_origins=allowed_origins,
        allow_origin_regex=allow_origin_regex,
        allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Mcp-Session-Id", "Accept"],
        expose_headers=["Mcp-Session-Id"],
    )

    # 7. Auth middleware
    final_app = BearerAuthMiddleware(cors_app, token=API_TOKEN, allow_no_auth=allow_no_auth)

    return final_app, mcp


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------
def main() -> None:
    """Punto de entrada del servidor MCP remoto."""
    port = 3777
    host = "127.0.0.1"
    json_response = True
    allow_no_auth = ALLOW_NO_AUTH_DEFAULT
    cors_origins = parse_cors_origins(os.environ.get("ANTIGRAVITY_CORS_ORIGINS"))

    # Parse CLI args
    args = sys.argv[1:]

    if "--help" in args or "-h" in args:
        print(__doc__)
        sys.exit(0)

    if "--port" in args:
        idx = args.index("--port")
        if idx + 1 < len(args):
            port = int(args[idx + 1])

    if "--host" in args:
        idx = args.index("--host")
        if idx + 1 < len(args):
            host = args[idx + 1]

    if "--no-json" in args:
        json_response = False

    if "--no-auth" in args:
        allow_no_auth = True
        # Warning si --no-auth combinado con bind no-localhost
        if host not in ("localhost", "127.0.0.1", "::1", "0.0.0.0"):
            logger.warning(
                "ADVERTENCIA: --no-auth activo con host '%s'. "
                "El servidor es accesible sin autenticacion desde la red. "
                "Usar --no-auth SOLO en desarrollo local.",
                host,
            )

    if not API_TOKEN and not allow_no_auth:
        logger.error(
            "ANTIGRAVITY_API_TOKEN no configurado. "
            "Define el token o usa --no-auth solo para desarrollo local."
        )
        sys.exit(2)

    app, _mcp = create_app(
        host=host,
        port=port,
        json_response=json_response,
        allow_no_auth=allow_no_auth,
        cors_origins=cors_origins,
    )

    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    main()
