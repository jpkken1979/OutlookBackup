#!/usr/bin/env python3
"""
Antigravity Observations MCP Server v1.0 - Pipeline de Observaciones via MCP.

Expone el ObservationPipeline, HybridSearch y SessionSummarizer como
herramientas MCP accesibles desde cualquier IDE o app externa.

Tools:
- search_observations: Busqueda hibrida (SQLite + ChromaDB)
- get_session_summary: Resumen de una sesion
- get_recent_sessions: Ultimas N sesiones con resumenes
- get_pipeline_stats: Estadisticas del pipeline
- get_file_history: Historia de cambios de un archivo

Protocolo: JSON-RPC 2.0 sobre stdio (compatible MCP)
Transporte: Adaptivo (Content-Length framing o JSON puro)

Usage:
    python3 .agent/mcp/observations-server.py

    # En mcp.json de cualquier IDE:
    {
        "mcpServers": {
            "antigravity-observations": {
                "command": "python3",
                "args": [".agent/mcp/observations-server.py"]
            }
        }
    }
"""

import asyncio
import json
import logging
import os
import sys
import traceback
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration & Logging
# ---------------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).parent.parent.parent
LOG_FILE = Path(__file__).parent / "observations_mcp.log"

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    filename=str(LOG_FILE),
    filemode="a",
)
logger = logging.getLogger("antigravity.observations_mcp")

# Stderr handler for critical errors only
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.ERROR)
logger.addHandler(stderr_handler)

# Paths
_ANTIGRAVITY_HOME = os.environ.get("ANTIGRAVITY_HOME")
if _ANTIGRAVITY_HOME:
    BASE_DIR = Path(_ANTIGRAVITY_HOME).absolute()
else:
    BASE_DIR = Path(__file__).parent.parent.parent.absolute()

# Add core to sys.path
sys.path.insert(0, str(BASE_DIR / ".agent"))

logger.info("Observations Server paths: BASE_DIR=%s", BASE_DIR)


# ---------------------------------------------------------------------------
# Lazy Module Loading
# ---------------------------------------------------------------------------

_pipeline = None
_hybrid_search = None
_summarizer = None
_plugin_manager = None


def _get_pipeline() -> Any:
    global _pipeline
    if _pipeline is None:
        try:
            from core.observation_pipeline import get_observation_pipeline

            _pipeline = get_observation_pipeline(str(BASE_DIR))
            logger.info("ObservationPipeline cargado correctamente")
        except Exception as e:
            logger.error("Error cargando ObservationPipeline: %s", e)
    return _pipeline


def _get_hybrid_search() -> Any:
    global _hybrid_search
    if _hybrid_search is None:
        try:
            from core.hybrid_search import get_hybrid_search

            _hybrid_search = get_hybrid_search(str(BASE_DIR))
            logger.info("HybridSearch cargado correctamente")
        except Exception as e:
            logger.error("Error cargando HybridSearch: %s", e)
    return _hybrid_search


def _get_summarizer() -> Any:
    global _summarizer
    if _summarizer is None:
        try:
            from core.session_summarizer import get_session_summarizer

            _summarizer = get_session_summarizer(str(BASE_DIR))
            logger.info("SessionSummarizer cargado correctamente")
        except Exception as e:
            logger.error("Error cargando SessionSummarizer: %s", e)
    return _summarizer


def _get_plugin_manager() -> Any:
    """Lazy-load PluginManager for plugin operations."""
    global _plugin_manager
    if _plugin_manager is None:
        try:
            from core.plugin_manager import PluginManager

            _plugin_manager = PluginManager()
            _plugin_manager.discover()
            logger.info("PluginManager cargado correctamente")
        except Exception as e:
            logger.error("Error cargando PluginManager: %s", e)
    return _plugin_manager


# ---------------------------------------------------------------------------
# Tool Definitions
# ---------------------------------------------------------------------------


def _build_tools_list() -> list[dict]:
    """Construye la lista de herramientas MCP disponibles."""
    return [
        {
            "name": "search_observations",
            "description": (
                "Busqueda hibrida de observaciones (SQLite exacta + ChromaDB semantica). "
                "Busca en todo el historial de acciones, archivos editados, "
                "errores, decisiones y patrones."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Texto de busqueda (ej: 'autenticacion', 'error pytest', 'main.py')",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximo de resultados (default: 10)",
                        "default": 10,
                    },
                    "search_type": {
                        "type": "string",
                        "enum": ["hybrid", "sql", "semantic"],
                        "description": "Tipo de busqueda: hybrid (default), sql (exacta), semantic (significado)",
                        "default": "hybrid",
                    },
                    "filters": {
                        "type": "object",
                        "description": "Filtros opcionales: {type: 'file_edit', tool: 'Bash'}",
                        "properties": {
                            "type": {"type": "string"},
                            "tool": {"type": "string"},
                        },
                    },
                    "session_id": {
                        "type": "string",
                        "description": "Filtrar por sesion especifica (opcional)",
                    },
                },
                "required": ["query"],
            },
        },
        {
            "name": "get_session_summary",
            "description": (
                "Obtiene el resumen de una sesion de trabajo. "
                "Incluye archivos modificados, herramientas usadas, errores y resumen AI."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "session_id": {
                        "type": "string",
                        "description": "ID de la sesion a resumir",
                    },
                },
                "required": ["session_id"],
            },
        },
        {
            "name": "get_recent_sessions",
            "description": (
                "Lista las sesiones de trabajo recientes con sus resumenes. "
                "Util para ver que se ha hecho ultimamente en el proyecto."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "limit": {
                        "type": "integer",
                        "description": "Numero de sesiones a retornar (default: 10)",
                        "default": 10,
                    },
                },
            },
        },
        {
            "name": "get_pipeline_stats",
            "description": (
                "Estadisticas del pipeline de observaciones: total de observaciones, "
                "sesiones, distribucion por tipo de accion."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {},
            },
        },
        {
            "name": "get_file_history",
            "description": (
                "Obtiene el historial de acciones sobre un archivo especifico. "
                "Muestra cuando fue leido, editado, quien lo modifico y que errores hubo."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "file_path": {
                        "type": "string",
                        "description": "Ruta del archivo (relativa o absoluta)",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Maximo de entradas (default: 20)",
                        "default": 20,
                    },
                },
                "required": ["file_path"],
            },
        },
        {
            "name": "manage_plugins",
            "description": (
                "Gestion de plugins del ecosistema (list, info, activate, deactivate). "
                "Permite operar plugins via MCP desde IDEs sin pasar por REST."
            ),
            "inputSchema": {
                "type": "object",
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["list", "info", "activate", "deactivate"],
                        "description": "Operacion a ejecutar",
                    },
                    "name": {
                        "type": "string",
                        "description": "Nombre del plugin (requerido para info/activate/deactivate)",
                    },
                    "state": {
                        "type": "string",
                        "description": "Filtro opcional de estado para action=list",
                    },
                    "search": {
                        "type": "string",
                        "description": "Filtro opcional por texto para action=list",
                    },
                },
                "required": ["action"],
            },
        },
    ]


# ---------------------------------------------------------------------------
# Tool Handlers
# ---------------------------------------------------------------------------


async def _handle_search_observations(arguments: dict) -> dict:
    """Handler: busqueda hibrida de observaciones."""
    query_text: str = arguments.get("query", "")
    limit: int = arguments.get("limit", 10)
    search_type: str = arguments.get("search_type", "hybrid")
    filters: dict = arguments.get("filters", {})
    session_id: str | None = arguments.get("session_id")

    if not query_text:
        return {
            "content": [{"type": "text", "text": "Error: query es requerido"}],
            "isError": True,
        }

    search = _get_hybrid_search()
    if not search:
        return {
            "content": [{"type": "text", "text": "Error: HybridSearch no disponible"}],
            "isError": True,
        }

    if search_type == "sql":
        results = search.search_sql(query_text, limit=limit, filters=filters or None)
    elif search_type == "semantic":
        results = search.search_semantic(query_text, limit=limit)
    else:
        results = search.search(
            query_text,
            limit=limit,
            filters=filters or None,
            session_id=session_id,
        )

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "query": query_text,
                        "search_type": search_type,
                        "total_results": len(results),
                        "results": [r.to_dict() for r in results],
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
            }
        ],
    }


async def _handle_get_session_summary(arguments: dict) -> dict:
    """Handler: resumen de una sesion."""
    session_id: str = arguments.get("session_id", "")

    if not session_id:
        return {
            "content": [{"type": "text", "text": "Error: session_id es requerido"}],
            "isError": True,
        }

    pipeline = _get_pipeline()
    if not pipeline:
        return {
            "content": [{"type": "text", "text": "Error: ObservationPipeline no disponible"}],
            "isError": True,
        }

    # Get structured summary
    summary = pipeline.generate_session_summary(session_id)

    # Try AI summary
    summarizer = _get_summarizer()
    ai_summary = None
    if summarizer:
        try:
            ai_summary = await summarizer.summarize_session(session_id)
        except Exception as e:
            logger.warning("Error generando resumen AI: %s", e)

    result = {
        "session_id": summary.session_id,
        "start_time": summary.start_time,
        "end_time": summary.end_time,
        "total_observations": summary.total_observations,
        "files_modified": summary.files_modified,
        "files_read": summary.files_read,
        "tools_used": summary.tools_used,
        "errors": summary.errors,
        "decisions": summary.decisions,
        "success_rate": summary.success_rate,
    }
    if ai_summary:
        result["ai_summary"] = ai_summary

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(result, indent=2, ensure_ascii=False),
            }
        ],
    }


async def _handle_get_recent_sessions(arguments: dict) -> dict:
    """Handler: lista sesiones recientes."""
    limit: int = arguments.get("limit", 10)

    pipeline = _get_pipeline()
    if not pipeline:
        return {
            "content": [{"type": "text", "text": "Error: ObservationPipeline no disponible"}],
            "isError": True,
        }

    summaries = pipeline._store.get_recent_session_summaries(limit)

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "total_sessions": len(summaries),
                        "sessions": summaries,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
            }
        ],
    }


async def _handle_get_pipeline_stats(arguments: dict) -> dict:
    """Handler: estadisticas del pipeline."""
    pipeline = _get_pipeline()
    if not pipeline:
        return {
            "content": [{"type": "text", "text": "Error: ObservationPipeline no disponible"}],
            "isError": True,
        }

    stats = pipeline.get_stats()

    # Enriquecer con info de sesiones
    summaries = pipeline._store.get_recent_session_summaries(5)
    stats["recent_sessions"] = len(summaries)
    if summaries:
        stats["last_session"] = summaries[0].get("session_id", "unknown")
        stats["last_session_time"] = summaries[0].get("end_time", "unknown")

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(stats, indent=2, ensure_ascii=False),
            }
        ],
    }


async def _handle_get_file_history(arguments: dict) -> dict:
    """Handler: historial de un archivo."""
    file_path: str = arguments.get("file_path", "")
    limit: int = arguments.get("limit", 20)

    if not file_path:
        return {
            "content": [{"type": "text", "text": "Error: file_path es requerido"}],
            "isError": True,
        }

    pipeline = _get_pipeline()
    if not pipeline:
        return {
            "content": [{"type": "text", "text": "Error: ObservationPipeline no disponible"}],
            "isError": True,
        }

    observations = pipeline._store.get_observations_by_file(file_path, limit)

    entries = []
    for obs in observations:
        entries.append(
            {
                "timestamp": obs.timestamp,
                "tool": obs.tool_name,
                "action": obs.observation_type,
                "summary": obs.tool_input_summary,
                "success": obs.success,
                "error": obs.error_message,
                "session_id": obs.session_id,
            }
        )

    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(
                    {
                        "file_path": file_path,
                        "total_entries": len(entries),
                        "history": entries,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
            }
        ],
    }


def _filter_plugins(plugins: list, state_filter: str, search: str) -> list:
    """Filtra una lista de plugins por estado y termino de busqueda.

    Args:
        plugins: Lista de plugins a filtrar.
        state_filter: Estado por el que filtrar (vacio = sin filtro).
        search: Termino de busqueda en nombre/descripcion (vacio = sin filtro).

    Returns:
        Lista de plugins que cumplen los filtros aplicados.
    """
    if state_filter:
        plugins = [p for p in plugins if p.state.value == state_filter]
    if search:
        plugins = [
            p
            for p in plugins
            if search in p.metadata.name.lower() or search in p.metadata.description.lower()
        ]
    return plugins


def _build_list_payload(pm: Any, state_filter: str, search: str) -> dict:
    """Construye el payload para la accion 'list'.

    Args:
        pm: Instancia del PluginManager.
        state_filter: Estado por el que filtrar.
        search: Termino de busqueda.

    Returns:
        Diccionario con el listado de plugins y estadisticas.
    """
    plugins = _filter_plugins(pm.list_plugins(), state_filter, search)
    return {
        "action": "list",
        "total": len(plugins),
        "stats": pm.get_stats(),
        "plugins": [
            {
                "name": p.metadata.name,
                "state": p.state.value,
                "version": p.metadata.version,
                "description": p.metadata.description,
                "skills_count": p.skills_count,
                "agents_count": p.agents_count,
                "commands_count": p.commands_count,
                "category": p.metadata.category,
            }
            for p in plugins
        ],
    }


def _build_info_payload(pm: Any, name: str) -> dict:
    """Construye el payload para la accion 'info'.

    Args:
        pm: Instancia del PluginManager.
        name: Nombre del plugin a consultar.

    Returns:
        Diccionario con los detalles del plugin.

    Raises:
        ValueError: Si el nombre esta vacio.
        KeyError: Si el plugin no existe.
    """
    if not name:
        raise ValueError("name es requerido para action=info")
    info = pm.get(name)
    if info is None:
        raise KeyError(f"Plugin '{name}' no encontrado")
    return {
        "action": "info",
        "plugin": {
            "name": info.metadata.name,
            "state": info.state.value,
            "metadata": info.metadata.model_dump(),
            "skills_count": info.skills_count,
            "agents_count": info.agents_count,
            "commands_count": info.commands_count,
            "activated_at": info.activated_at,
            "deactivated_at": info.deactivated_at,
            "error_message": info.error_message,
        },
    }


async def _build_activate_payload(pm: Any, name: str) -> dict:
    """Construye el payload para la accion 'activate'.

    Args:
        pm: Instancia del PluginManager.
        name: Nombre del plugin a activar.

    Returns:
        Diccionario con el resultado de la activacion.

    Raises:
        ValueError: Si el nombre esta vacio.
    """
    if not name:
        raise ValueError("name es requerido para action=activate")
    info = await pm.activate(name)
    return {
        "action": "activate",
        "plugin": name,
        "state": info.state.value,
        "skills_registered": info.skills_count,
    }


async def _build_deactivate_payload(pm: Any, name: str) -> dict:
    """Construye el payload para la accion 'deactivate'.

    Args:
        pm: Instancia del PluginManager.
        name: Nombre del plugin a desactivar.

    Returns:
        Diccionario con el resultado de la desactivacion.

    Raises:
        ValueError: Si el nombre esta vacio.
    """
    if not name:
        raise ValueError("name es requerido para action=deactivate")
    info = await pm.deactivate(name)
    return {
        "action": "deactivate",
        "plugin": name,
        "state": info.state.value,
    }


async def _handle_manage_plugins(arguments: dict) -> dict:
    """Handler: gestion MCP de plugins (list/info/activate/deactivate)."""
    action = str(arguments.get("action", "")).strip().lower()
    name = str(arguments.get("name", "")).strip()
    state_filter = str(arguments.get("state", "")).strip().lower()
    search = str(arguments.get("search", "")).strip().lower()

    if action not in {"list", "info", "activate", "deactivate"}:
        return {
            "content": [{"type": "text", "text": "Error: action invalida"}],
            "isError": True,
        }

    pm = _get_plugin_manager()
    if not pm:
        return {
            "content": [{"type": "text", "text": "Error: PluginManager no disponible"}],
            "isError": True,
        }

    try:
        if action == "list":
            payload = _build_list_payload(pm, state_filter, search)
        elif action == "info":
            payload = _build_info_payload(pm, name)
        elif action == "activate":
            payload = await _build_activate_payload(pm, name)
        else:
            payload = await _build_deactivate_payload(pm, name)

        return {
            "content": [
                {"type": "text", "text": json.dumps(payload, indent=2, ensure_ascii=False)}
            ],
        }
    except Exception as exc:
        return {
            "content": [{"type": "text", "text": f"Error: {exc}"}],
            "isError": True,
        }


# ---------------------------------------------------------------------------
# Tool Router
# ---------------------------------------------------------------------------

_TOOL_HANDLERS: dict[str, Any] = {
    "search_observations": _handle_search_observations,
    "get_session_summary": _handle_get_session_summary,
    "get_recent_sessions": _handle_get_recent_sessions,
    "get_pipeline_stats": _handle_get_pipeline_stats,
    "get_file_history": _handle_get_file_history,
    "manage_plugins": _handle_manage_plugins,
}


# ---------------------------------------------------------------------------
# MCP Request Handler
# ---------------------------------------------------------------------------


async def handle_request(request: dict) -> dict | None:
    """Procesa un request JSON-RPC del protocolo MCP."""
    method: str = request.get("method", "")
    params: dict = request.get("params", {})
    request_id = request.get("id")

    # initialize
    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {
                    "name": "antigravity-observations",
                    "version": "1.0.0",
                },
            },
        }

    # Notifications don't get responses (JSON-RPC 2.0 spec)
    if method and method.startswith("notifications/"):
        logger.info("Notification recibida: %s", method)
        return None

    # tools/list
    if method == "tools/list":
        tools = _build_tools_list()
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}

    # tools/call
    if method == "tools/call":
        tool_name: str = params.get("name", "")
        arguments: dict = params.get("arguments", {})

        logger.info("tools/call: %s args=%s", tool_name, json.dumps(arguments)[:200])

        handler = _TOOL_HANDLERS.get(tool_name)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32601,
                    "message": f"Tool not found: {tool_name}",
                    "data": {"available_tools": list(_TOOL_HANDLERS.keys())},
                },
            }

        try:
            result = await handler(arguments)
            return {"jsonrpc": "2.0", "id": request_id, "result": result}
        except Exception as e:
            logger.error("Error en tool '%s': %s", tool_name, traceback.format_exc())
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32603, "message": f"Internal error: {e}"},
            }

    # Unknown
    logger.warning("Metodo desconocido: %s", method)
    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": f"Method not found: {method}"},
    }


# ---------------------------------------------------------------------------
# Stdio Transport (adaptivo)
# ---------------------------------------------------------------------------


async def run_server() -> None:
    """Loop principal del servidor MCP via stdio."""
    logger.info("Observations MCP Server v1.0 starting...")

    # Pre-cargar modulos en background
    asyncio.get_running_loop().call_soon(_get_pipeline)

    reader = sys.stdin.buffer
    loop = asyncio.get_running_loop()

    while True:
        try:
            line = await loop.run_in_executor(None, reader.readline)
            if not line:
                break

            line_str = line.decode("utf-8").strip()
            if not line_str:
                continue

            # Detectar Content-Length framing
            use_framing = False
            if line_str.lower().startswith("content-length:"):
                use_framing = True
                length = int(line_str.split(":")[1].strip())
                await loop.run_in_executor(None, reader.readline)  # blank line
                body = await loop.run_in_executor(None, reader.read, length)
                message = json.loads(body.decode("utf-8"))
            else:
                try:
                    message = json.loads(line_str)
                except (json.JSONDecodeError, ValueError):
                    continue

            response = await handle_request(message)
            if response:
                res_json = json.dumps(response).encode("utf-8")
                if use_framing:
                    header = f"Content-Length: {len(res_json)}\r\n\r\n".encode()
                    sys.stdout.buffer.write(header + res_json)
                else:
                    sys.stdout.buffer.write(res_json + b"\n")
                sys.stdout.buffer.flush()

        except Exception as e:
            logger.error("Runtime error: %s", e)


if __name__ == "__main__":
    try:
        asyncio.run(run_server())
    except KeyboardInterrupt:
        logger.info("Server stopped by user")
    except Exception as e:
        logger.critical("Server crash: %s", e)
