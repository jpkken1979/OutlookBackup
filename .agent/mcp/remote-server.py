#!/usr/bin/env python3
"""Antigravity Agents MCP Remote Server v2.3.0.

Servidor HTTP remoto para exponer agentes del ecosistema via MCP.
Implementa MCP Streamable HTTP transport y compatibilidad con SSE legacy.

Features:
- MCP Streamable HTTP (POST /mcp, GET /mcp, DELETE /mcp)
- Session management con Mcp-Session-Id
- SSE support legacy (GET/POST /sse)
- API token authentication (Bearer)
- CORS enabled para clientes web
- Health check + metrics + agent discovery
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from aiohttp import web

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger("antigravity.remote")

BASE_DIR = Path(os.environ.get("ANTIGRAVITY_HOME", Path(__file__).parent.parent.parent))
AGENTS_DIR = BASE_DIR / ".agent" / "agents"
CORE_DIR = BASE_DIR / ".agent" / "core"

# API token from env (optional)
API_TOKEN = os.environ.get("ANTIGRAVITY_API_TOKEN") or os.environ.get("MCP_API_TOKEN") or ""

# Session storage for MCP Streamable HTTP
_mcp_sessions: dict[str, dict[str, Any]] = {}
_sse_clients: list[asyncio.Queue] = []

# Metrics
_metrics: dict[str, int] = {
    "total_requests": 0,
    "total_errors": 0,
    "total_sse_connections": 0,
    "total_mcp_sessions": 0,
    "total_sessions_expired": 0,
}

CLEANUP_TASK_KEY: web.AppKey[asyncio.Task[None]] = web.AppKey("cleanup_task")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def _check_auth(headers: dict[str, str]) -> bool:
    """Verifica autenticacion Bearer token si esta configurado."""
    if not API_TOKEN:
        return True

    auth = headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[7:]
        return secrets.compare_digest(token, API_TOKEN)

    return False


def _count_agents() -> int:
    """Cuenta agentes activos en el directorio."""
    if not AGENTS_DIR.exists():
        return 0

    count = 0
    for item in AGENTS_DIR.iterdir():
        if item.is_dir() and not item.name.startswith("_"):
            identity = item / "IDENTITY.md"
            if identity.exists():
                count += 1

    return count


def _discover_agents() -> list[dict[str, str]]:
    """Descubre metadata basica de agentes desde IDENTITY.md."""
    agents: list[dict[str, str]] = []

    if not AGENTS_DIR.exists():
        return agents

    for agent_dir in sorted(AGENTS_DIR.iterdir()):
        if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
            continue

        identity_file = agent_dir / "IDENTITY.md"
        if not identity_file.exists():
            continue

        agent_name = agent_dir.name
        role = ""
        description = ""

        try:
            content = identity_file.read_text(encoding="utf-8")
            for line in content.splitlines():
                line = line.strip()
                if line.startswith("- **Rol**:"):
                    role = line.split(":", 1)[1].strip()
                elif line.startswith("- **Descripción**:") or line.startswith("- **Descripcion**:"):
                    description = line.split(":", 1)[1].strip()
        except Exception as e:
            logger.debug("Error reading %s: %s", identity_file, e)

        agents.append(
            {
                "name": agent_name,
                "role": role,
                "description": description,
                "path": str(agent_dir),
            }
        )

    return agents


def _get_session(session_id: str) -> dict[str, Any] | None:
    """Obtiene una sesion MCP por ID y actualiza timestamp."""
    session = _mcp_sessions.get(session_id)
    if session:
        session["last_active"] = datetime.now().isoformat()
    return session


def _create_session() -> tuple[str, dict[str, Any]]:
    """Crea nueva sesion MCP con ID seguro."""
    session_id = secrets.token_urlsafe(24)
    session_data = {
        "id": session_id,
        "created_at": datetime.now().isoformat(),
        "last_active": datetime.now().isoformat(),
        "sse_queue": asyncio.Queue(maxsize=200),
    }
    _mcp_sessions[session_id] = session_data
    _metrics["total_mcp_sessions"] += 1
    return session_id, session_data


def _destroy_session(session_id: str) -> bool:
    """Elimina una sesion MCP."""
    if session_id in _mcp_sessions:
        del _mcp_sessions[session_id]
        return True
    return False


def _jsonrpc_error(id_val: Any, code: int, message: str) -> dict[str, Any]:
    """Construye respuesta JSON-RPC de error."""
    return {
        "jsonrpc": "2.0",
        "id": id_val,
        "error": {
            "code": code,
            "message": message,
        },
    }


# ---------------------------------------------------------------------------
# MCP protocol handlers
# ---------------------------------------------------------------------------
async def handle_mcp_request(body: dict[str, Any]) -> dict[str, Any] | None:
    """Maneja request MCP JSON-RPC y retorna respuesta.

    Implementa subset de metodos MCP para compatibilidad con clientes IDE.
    """
    if not isinstance(body, dict):
        return _jsonrpc_error(None, -32600, "Invalid Request")

    jsonrpc = body.get("jsonrpc")
    method = body.get("method")
    req_id = body.get("id")
    params = body.get("params", {})

    if jsonrpc != "2.0" or not method:
        return _jsonrpc_error(req_id, -32600, "Invalid Request")

    try:
        # MCP initialize
        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "antigravity-mcp-remote",
                        "version": "2.3.0",
                    },
                    "capabilities": {
                        "tools": {
                            "listChanged": True,
                        },
                        "prompts": {
                            "listChanged": False,
                        },
                        "resources": {
                            "subscribe": False,
                            "listChanged": False,
                        },
                        "logging": {},
                    },
                },
            }

        # MCP ping
        if method == "ping":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {},
            }

        # MCP tools/list
        if method == "tools/list":
            agents = _discover_agents()
            tools: list[dict[str, Any]] = []

            tools.append(
                {
                    "name": "list_agents",
                    "description": "List available Antigravity agents",
                    "inputSchema": {
                        "type": "object",
                        "properties": {},
                    },
                }
            )

            tools.append(
                {
                    "name": "invoke_agent",
                    "description": "Invoke an agent with a task",
                    "inputSchema": {
                        "type": "object",
                        "properties": {
                            "agent": {
                                "type": "string",
                                "description": "Agent name",
                            },
                            "task": {
                                "type": "string",
                                "description": "Task/instruction for the agent",
                            },
                        },
                        "required": ["agent", "task"],
                    },
                }
            )

            for agent in agents:
                tools.append(
                    {
                        "name": f"agent.{agent['name']}",
                        "description": agent["description"]
                        or agent["role"]
                        or f"Run {agent['name']}",
                        "inputSchema": {
                            "type": "object",
                            "properties": {
                                "task": {
                                    "type": "string",
                                    "description": "Task/instruction for the agent",
                                }
                            },
                            "required": ["task"],
                        },
                    }
                )

            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "tools": tools,
                },
            }

        # MCP tools/call
        if method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})

            if tool_name == "list_agents":
                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(
                                    {
                                        "count": len(_discover_agents()),
                                        "agents": _discover_agents(),
                                    },
                                    ensure_ascii=False,
                                ),
                            }
                        ]
                    },
                }

            if tool_name == "invoke_agent":
                agent_name = arguments.get("agent", "")
                task = arguments.get("task", "")

                if not agent_name or not task:
                    return _jsonrpc_error(
                        req_id,
                        -32602,
                        "Missing required arguments: agent and task",
                    )

                tool_name = f"agent.{agent_name}"

            if not tool_name.startswith("agent."):
                return _jsonrpc_error(req_id, -32602, f"Unknown tool: {tool_name}")

            agent_name = tool_name.replace("agent.", "", 1)
            task = arguments.get("task", "")

            if not task:
                return _jsonrpc_error(req_id, -32602, "Missing required argument: task")

            # Ejecutar agente via invoke-agent.py
            invoke_script = BASE_DIR / ".agent" / "scripts" / "invoke-agent.py"
            if not invoke_script.exists():
                return _jsonrpc_error(req_id, -32603, "invoke-agent.py not found")

            try:
                cmd = [
                    sys.executable,
                    str(invoke_script),
                    agent_name,
                    task,
                    "--json",
                ]
                # Security: shell=False, no interpolation
                proc = await asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=str(BASE_DIR),
                )
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=120)

                if proc.returncode != 0:
                    err = stderr.decode("utf-8", errors="replace").strip()
                    return _jsonrpc_error(req_id, -32603, f"Agent execution failed: {err}")

                output = stdout.decode("utf-8", errors="replace").strip()
                content_text = output

                return {
                    "jsonrpc": "2.0",
                    "id": req_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": content_text,
                            }
                        ]
                    },
                }

            except TimeoutError:
                return _jsonrpc_error(req_id, -32603, "Agent execution timeout (120s)")
            except Exception as e:
                return _jsonrpc_error(req_id, -32603, f"Agent execution error: {e}")

        # Notificacion fire-and-forget
        if req_id is None:
            return None

        return _jsonrpc_error(req_id, -32601, f"Method not found: {method}")

    except Exception as e:
        logger.exception("MCP handler error")
        return _jsonrpc_error(req_id, -32603, f"Internal error: {e}")


# ---------------------------------------------------------------------------
# HTTP handlers
# ---------------------------------------------------------------------------
async def handle_root(request: web.Request) -> web.Response:
    """GET / - Informacion del servidor."""
    return web.json_response(
        {
            "name": "antigravity-mcp-remote",
            "version": "2.3.0",
            "transport": "streamable-http",
            "endpoints": {
                "mcp": "/mcp",
                "health": "/health",
                "agents": "/agents",
                "metrics": "/metrics",
                "sse_legacy": "/sse",
            },
            "auth_enabled": bool(API_TOKEN),
            "agents_count": _count_agents(),
            "active_sessions": len(_mcp_sessions),
        }
    )


async def handle_health(request: web.Request) -> web.Response:
    """GET /health - Health check endpoint."""
    return web.json_response(
        {
            "status": "healthy",
            "server": "antigravity-mcp-remote",
            "service": "antigravity-mcp-remote",
            "version": "2.3.0",
            "timestamp": datetime.now().isoformat(),
            "agents": _count_agents(),
            "sessions": len(_mcp_sessions),
            "uptime": "running",
        }
    )


async def handle_metrics(request: web.Request) -> web.Response:
    """GET /metrics - Basic metrics endpoint."""
    payload = {
        **_metrics,
        "active_sessions": len(_mcp_sessions),
        "connected_sse_clients": len(_sse_clients),
        "agents_count": _count_agents(),
        "timestamp": datetime.now().isoformat(),
    }
    return web.json_response(payload)


async def handle_agents_list(request: web.Request) -> web.Response:
    """GET /agents - Lista agentes disponibles (REST helper)."""
    if not _check_auth(dict(request.headers)):
        return web.json_response({"error": "Unauthorized"}, status=401)

    agents = _discover_agents()
    return web.json_response(
        {
            "count": len(agents),
            "total": len(agents),
            "agents": agents,
            "timestamp": datetime.now().isoformat(),
        }
    )


async def handle_mcp_http(request: web.Request) -> web.Response:
    """POST /mcp - MCP Streamable HTTP endpoint principal."""
    if not _check_auth(dict(request.headers)):
        return web.json_response(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32000, "message": "Unauthorized"}},
            status=401,
        )

    # Parse JSON body
    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(_jsonrpc_error(None, -32700, "Parse error"), status=400)

    # Session handling (MCP Streamable HTTP)
    session_id = request.headers.get("Mcp-Session-Id", "")
    session = _get_session(session_id) if session_id else None

    response_headers: dict[str, str] = {}

    # Create session on initialize if absent
    is_initialize = isinstance(body, dict) and body.get("method") == "initialize"
    if is_initialize and not session:
        session_id, session = _create_session()
        response_headers["Mcp-Session-Id"] = session_id

    # For non-initialize requests session is optional for compatibility.

    # Batch request support
    wants_sse = "text/event-stream" in request.headers.get("Accept", "")
    if isinstance(body, list):
        if not body:
            return web.json_response(_jsonrpc_error(None, -32600, "Invalid Request"), status=400)

        results: list[dict[str, Any]] = []
        for item in body:
            result = await handle_mcp_request(item)
            if result is not None:
                results.append(result)

        return web.json_response(results, headers=response_headers)

    # Single request
    result = await handle_mcp_request(body)
    if result is None:
        return web.Response(status=204, headers=response_headers)

    # Broadcast event to session SSE queue if available
    if session:
        queue: asyncio.Queue = session["sse_queue"]
        payload = (
            "event: message\n"
            f"data: {json.dumps({'jsonrpc': '2.0', 'method': 'notifications/message', 'params': {'from': 'server', 'result': result}})}\n\n"
        )
        try:
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            logger.warning("Session SSE queue full for %s", session_id)

    # Broadcast to legacy SSE clients
    for queue in list(_sse_clients):
        try:
            payload = (
                "event: mcp\n"
                f"data: {json.dumps({'method': body.get('method', '') if isinstance(body, dict) else 'batch', 'timestamp': datetime.now().isoformat()})}\n\n"
            )
            queue.put_nowait(payload)
        except asyncio.QueueFull:
            continue

    # Si el cliente acepta SSE, responder como event stream
    if wants_sse and not isinstance(body, list):
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                **response_headers,
            },
        )
        await response.prepare(request)
        event = f"event: message\ndata: {json.dumps(result)}\n\n"
        await response.write(event.encode("utf-8"))
        return response

    return web.json_response(result, headers=response_headers)


async def handle_mcp_get(request: web.Request) -> web.StreamResponse:
    """GET /mcp - Abrir stream SSE para sesion MCP (Streamable HTTP spec).

    El cliente envia Mcp-Session-Id para recibir notificaciones server-to-client.
    """
    if not _check_auth(dict(request.headers)):
        return web.json_response({"error": "Unauthorized"}, status=401)

    session_id = request.headers.get("Mcp-Session-Id", "")
    if not session_id:
        return web.json_response(
            {"error": "Mcp-Session-Id header required for GET /mcp"},
            status=400,
        )

    session = _get_session(session_id)
    if not session:
        return web.json_response(
            {"error": "Session not found or expired"},
            status=404,
        )

    queue = session.get("sse_queue")
    if not queue:
        return web.json_response(
            {"error": "Session has no SSE queue"},
            status=500,
        )

    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Mcp-Session-Id": session_id,
        },
    )
    await response.prepare(request)

    # Send initial connection event
    welcome = f"event: open\ndata: {json.dumps({'session': session_id})}\n\n"
    await response.write(welcome.encode("utf-8"))

    try:
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=45)
                await response.write(payload.encode("utf-8"))
            except TimeoutError:
                await response.write(b": keepalive\n\n")
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                break
    finally:
        logger.info("MCP SSE session closed: %s", session_id)

    return response


async def handle_mcp_delete(request: web.Request) -> web.Response:
    """DELETE /mcp - Terminar sesion MCP (Streamable HTTP spec)."""
    if not _check_auth(dict(request.headers)):
        return web.json_response({"error": "Unauthorized"}, status=401)

    session_id = request.headers.get("Mcp-Session-Id", "")
    if not session_id:
        return web.json_response(
            {"error": "Mcp-Session-Id header required"},
            status=400,
        )

    if _destroy_session(session_id):
        return web.Response(status=204)
    else:
        return web.json_response(
            {"error": "Session not found"},
            status=404,
        )


async def handle_sse(request: web.Request) -> web.StreamResponse:
    """GET /sse - Server-Sent Events stream (legacy, para compatibilidad)."""
    if not _check_auth(dict(request.headers)):
        return web.json_response({"error": "Unauthorized"}, status=401)

    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "Access-Control-Allow-Origin": "*",
        },
    )
    await response.prepare(request)

    # Send initial connection event
    queue: asyncio.Queue = asyncio.Queue(maxsize=100)
    _sse_clients.append(queue)
    _metrics["total_sse_connections"] += 1

    welcome = (
        "event: connected\n"
        f"data: {json.dumps({'server': 'antigravity-mcp-remote', 'version': '2.3.0'})}\n\n"
    )
    await response.write(welcome.encode("utf-8"))

    try:
        while True:
            try:
                payload = await asyncio.wait_for(queue.get(), timeout=45)
                await response.write(payload.encode("utf-8"))
            except TimeoutError:
                # Send keepalive (45s reduce overhead vs 30s original)
                await response.write(b": keepalive\n\n")
            except (ConnectionResetError, ConnectionAbortedError, BrokenPipeError):
                break
    finally:
        if queue in _sse_clients:
            _sse_clients.remove(queue)

    return response


async def handle_mcp_sse(request: web.Request) -> web.StreamResponse:
    """POST /sse - MCP over SSE legacy (bidirectional)."""
    if not _check_auth(dict(request.headers)):
        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32000, "message": "Unauthorized"},
            },
            status=401,
        )

    try:
        body = await request.json()
    except json.JSONDecodeError:
        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32700, "message": "Parse error"},
            },
            status=400,
        )

    response = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Access-Control-Allow-Origin": "*",
        },
    )
    await response.prepare(request)

    # Execute the MCP request
    result = await handle_mcp_request(body)

    if result is not None:
        event = f"event: message\ndata: {json.dumps(result)}\n\n"
        await response.write(event.encode("utf-8"))

    # Signal completion
    await response.write(b"event: done\ndata: {}\n\n")

    return response


# ---------------------------------------------------------------------------
# CORS middleware
# ---------------------------------------------------------------------------
@web.middleware
async def cors_middleware(request: web.Request, handler: Any) -> web.Response:
    """Middleware para CORS headers en todas las respuestas."""
    if request.method == "OPTIONS":
        return web.Response(
            status=204,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Access-Control-Allow-Methods": "GET, POST, DELETE, OPTIONS",
                "Access-Control-Allow-Headers": (
                    "Content-Type, Authorization, Mcp-Session-Id, Accept"
                ),
                "Access-Control-Expose-Headers": "Mcp-Session-Id",
                "Access-Control-Max-Age": "86400",
            },
        )

    response = await handler(request)

    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = (
        "Content-Type, Authorization, Mcp-Session-Id, Accept"
    )
    response.headers["Access-Control-Expose-Headers"] = "Mcp-Session-Id"

    return response


@web.middleware
async def logging_middleware(request: web.Request, handler: Any) -> web.Response:
    """Middleware para logging de requests con métricas."""
    start = datetime.now()
    _metrics["total_requests"] += 1
    try:
        response = await handler(request)
        elapsed = (datetime.now() - start).total_seconds() * 1000
        logger.info(
            "%s %s -> %s (%.0fms)",
            request.method,
            request.path,
            response.status,
            elapsed,
        )
        return response
    except web.HTTPException:
        raise
    except Exception as e:
        elapsed = (datetime.now() - start).total_seconds() * 1000
        _metrics["total_errors"] += 1
        logger.error(
            "%s %s -> 500 (%.0fms): %s",
            request.method,
            request.path,
            elapsed,
            e,
        )
        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": "Internal server error"},
            },
            status=500,
        )


# ---------------------------------------------------------------------------
# Session cleanup task
# ---------------------------------------------------------------------------
async def _cleanup_sessions(app: web.Application) -> None:
    """Limpia sesiones inactivas cada 60 segundos."""
    while True:
        await asyncio.sleep(60)  # Verificar cada minuto (antes era 5min)
        now = datetime.now()
        expired = []
        for sid, session in _mcp_sessions.items():
            last = datetime.fromisoformat(session["last_active"])
            if (now - last).total_seconds() > 1800:  # 30 minutos de inactividad
                expired.append(sid)
        for sid in expired:
            _destroy_session(sid)
            _metrics["total_sessions_expired"] += 1
        if expired:
            logger.info(
                "Expired sessions cleaned: %d (active: %d)", len(expired), len(_mcp_sessions)
            )


async def start_cleanup(app: web.Application) -> None:
    """Inicia tarea de limpieza de sesiones."""
    app[CLEANUP_TASK_KEY] = asyncio.create_task(_cleanup_sessions(app))


async def stop_cleanup(app: web.Application) -> None:
    """Detiene tarea de limpieza de sesiones."""
    task = app.get(CLEANUP_TASK_KEY)
    if task:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


# ---------------------------------------------------------------------------
# App factory
# ---------------------------------------------------------------------------
def create_app() -> web.Application:
    """Crea la aplicacion aiohttp con todas las rutas."""
    app = web.Application(middlewares=[cors_middleware, logging_middleware])

    # MCP Streamable HTTP routes
    app.router.add_get("/", handle_root)
    app.router.add_get("/health", handle_health)
    app.router.add_get("/metrics", handle_metrics)
    app.router.add_get("/agents", handle_agents_list)
    app.router.add_post("/mcp", handle_mcp_http)
    app.router.add_get("/mcp", handle_mcp_get)
    app.router.add_delete("/mcp", handle_mcp_delete)

    # Legacy SSE routes (backward compatibility)
    app.router.add_get("/sse", handle_sse)
    app.router.add_post("/sse", handle_mcp_sse)

    # Session cleanup
    app.on_startup.append(start_cleanup)
    app.on_cleanup.append(stop_cleanup)

    return app


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
def main() -> None:
    """Punto de entrada del servidor MCP remoto."""
    global BASE_DIR, AGENTS_DIR, CORE_DIR

    # Parse CLI args
    args = sys.argv[1:]
    port = 3777
    host = "0.0.0.0"  # nosec B104

    if "--port" in args:
        idx = args.index("--port")
        if idx + 1 < len(args):
            port = int(args[idx + 1])

    if "--host" in args:
        idx = args.index("--host")
        if idx + 1 < len(args):
            host = args[idx + 1]

    if "--home" in args:
        idx = args.index("--home")
        if idx + 1 < len(args):
            home = args[idx + 1]
            BASE_DIR = Path(home)
            AGENTS_DIR = BASE_DIR / ".agent" / "agents"
            CORE_DIR = BASE_DIR / ".agent" / "core"

    if "--help" in args or "-h" in args:
        print(
            "Antigravity Agents MCP Remote Server v2.3.0\n"
            "=============================================\n\n"
            "Uso:\n"
            "  python remote-server.py                              # Puerto 3777, sin auth\n"
            "  python remote-server.py --port 8777                  # Puerto custom\n"
            "  python remote-server.py --host 127.0.0.1             # Solo localhost\n"
            "  python remote-server.py --home /ruta/al/proyecto     # Home custom\n"
            "  ANTIGRAVITY_API_TOKEN=xxx python remote-server.py    # Con autenticacion\n\n"
            "Endpoints (MCP Streamable HTTP):\n"
            "  POST   /mcp     JSON-RPC sobre HTTP (Streamable HTTP transport)\n"
            "  GET    /mcp     SSE stream de sesion (requiere Mcp-Session-Id)\n"
            "  DELETE /mcp     Terminar sesion MCP\n\n"
            "Endpoints (Legacy SSE):\n"
            "  GET    /sse     Server-Sent Events (notificaciones en tiempo real)\n"
            "  POST   /sse     MCP sobre SSE (bidireccional)\n\n"
            "Endpoints (REST):\n"
            "  GET    /health  Health check\n"
            "  GET    /agents  Lista de agentes (REST)\n\n"
            "Configuracion en IDE (Streamable HTTP):\n"
            '  {"mcpServers": {"antigravity-remote": {\n'
            '    "url": "https://mcp.uns-kikaku.cloud/mcp",\n'
            '    "headers": {"Authorization": "Bearer TU_TOKEN"}\n'
            "  }}}\n\n"
            "Configuracion en IDE (stdio via mcp-remote):\n"
            '  {"mcpServers": {"antigravity-remote": {\n'
            '    "command": "npx",\n'
            '    "args": ["-y", "mcp-remote",\n'
            '      "https://mcp.uns-kikaku.cloud/mcp",\n'
            '      "--header", "Authorization: Bearer TU_TOKEN"]\n'
            "  }}}\n"
        )
        sys.exit(0)

    # Validate paths
    if not AGENTS_DIR.exists():
        # Auto-detect
        search = Path.cwd()
        for _ in range(5):
            if (search / ".agent" / "agents").exists():
                BASE_DIR = search
                AGENTS_DIR = search / ".agent" / "agents"
                CORE_DIR = search / ".agent" / "core"
                break
            parent = search.parent
            if parent == search:
                break
            search = parent

    if not AGENTS_DIR.exists():
        logger.error(
            "No se encontro directorio de agentes en %s\n"
            "Usa --home para especificar la ruta al proyecto con .agent/agents/",
            AGENTS_DIR,
        )
        sys.exit(1)

    # Count agents
    agent_count = _count_agents()

    # Security warning
    auth_status = "ACTIVADA" if API_TOKEN else "DESACTIVADA (cualquiera puede conectar)"
    if not API_TOKEN:
        logger.warning("Autenticacion desactivada. Para produccion, define ANTIGRAVITY_API_TOKEN")

    # Banner
    logger.info(
        "\n"
        "  Antigravity Agents MCP Remote Server v2.3.0\n"
        "  ============================================\n"
        "  Home:       %s\n"
        "  Agentes:    %d\n"
        "  Auth:       %s\n"
        "  Transport:  MCP Streamable HTTP\n"
        "  \n"
        "  Endpoints:\n"
        "    MCP:     http://%s:%d/mcp  (POST/GET/DELETE)\n"
        "    SSE:     http://%s:%d/sse  (legacy)\n"
        "    Health:  http://%s:%d/health\n"
        "    Agents:  http://%s:%d/agents\n"
        "  \n"
        "  Configuracion IDE (Streamable HTTP):\n"
        '    {"mcpServers": {"antigravity-remote": {\n'
        '      "url": "https://mcp.uns-kikaku.cloud/mcp",\n'
        '      "headers": {"Authorization": "Bearer TU_TOKEN"}\n'
        "    }}}\n",
        BASE_DIR,
        agent_count,
        auth_status,
        host,
        port,
        host,
        port,
        host,
        port,
        host,
        port,
    )

    app = create_app()
    web.run_app(app, host=host, port=port, print=None)


if __name__ == "__main__":
    main()
