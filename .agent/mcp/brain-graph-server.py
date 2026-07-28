#!/usr/bin/env python3
"""
Antigravity Brain Graph MCP Server
===================================
Servidor MCP que expone herramientas de visualizacion del Brain Network.

Tools:
- brain_graph: Retorna el grafo completo o focalizado en un nodo (D3-ready)
- brain_node_detail: Detalle completo de un nodo para panel lateral
- brain_graph_neighbors: Nodos relacionados directos
- brain_graph_search_tag: Buscar nodos por tag
- brain_graph_stats: Estadisticas del grafo

v1.0.0 — 2026-05-09
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Path setup
# ---------------------------------------------------------------------------
_agent_dir = Path(__file__).parent.parent
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))

from core.brain_graph import BrainGraph  # noqa: E402

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_graph: BrainGraph | None = None


def _get_project_root() -> Path:
    root = os.environ.get("ANTIGRAVITY_ROOT", "")
    if root:
        return Path(root)
    return Path(__file__).parent.parent.parent


def _ensure_graph() -> BrainGraph:
    global _graph
    if _graph is None:
        project_root = _get_project_root()
        brain_dir = project_root / ".agent" / "brain"
        _graph = BrainGraph(brain_dir)
        logger.info("BrainGraph inicializado: %s", brain_dir)
    return _graph


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_brain_graph(params: dict[str, Any]) -> dict[str, Any]:
    """Retorna el grafo del Brain para visualizacion D3.

    Args:
        params: center_slug (opcional), depth (default: 2).

    Returns:
        {nodes: [], edges: [], center, totalNodes, totalEdges, tags, areas}
    """
    graph = _ensure_graph()
    center_slug = params.get("center_slug") or None
    depth = int(params.get("depth", 2))

    data = graph.get_graph(center_slug=center_slug, depth=depth)
    return {"success": True, **data.to_d3()}


def handle_brain_node_detail(params: dict[str, Any]) -> dict[str, Any]:
    """Detalle completo de un nodo para el panel lateral.

    Args:
        params: slug (requerido).

    Returns:
        {slug, title, type, area, date, status, importance, tags,
         related, context, decisions, output, pending, access_count, last_accessed}
    """
    slug = params.get("slug", "")
    if not slug:
        return {"error": "slug es requerido"}

    graph = _ensure_graph()
    detail = graph.get_node_detail(slug)

    if detail is None:
        return {"error": f"Nodo '{slug}' no encontrado"}

    return {"success": True, **detail.to_dict()}


def handle_brain_graph_neighbors(params: dict[str, Any]) -> dict[str, Any]:
    """Nodos relacionados directos (1 salto).

    Args:
        params: slug (requerido).

    Returns:
        Lista de {id, title, type, area, tags, status, importance, access_count}
    """
    slug = params.get("slug", "")
    if not slug:
        return {"error": "slug es requerido"}

    graph = _ensure_graph()
    neighbors = graph.get_neighbors(slug)

    return {
        "success": True,
        "total": len(neighbors),
        "neighbors": [n.to_d3_node() for n in neighbors],
    }


def handle_brain_graph_search_tag(params: dict[str, Any]) -> dict[str, Any]:
    """Buscar todos los nodos con un tag.

    Args:
        params: tag (requerido).

    Returns:
        Lista de nodos que tienen el tag.
    """
    tag = params.get("tag", "")
    if not tag:
        return {"error": "tag es requerido"}

    graph = _ensure_graph()
    nodes = graph.search_by_tag(tag)

    return {
        "success": True,
        "total": len(nodes),
        "tag": tag,
        "nodes": [n.to_d3_node() for n in nodes],
    }


def handle_brain_graph_stats(params: dict[str, Any]) -> dict[str, Any]:
    """Estadisticas del grafo para el header UI."""
    graph = _ensure_graph()
    return {"success": True, **graph.get_stats()}


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, Any] = {
    "brain_graph": handle_brain_graph,
    "brain_node_detail": handle_brain_node_detail,
    "brain_graph_neighbors": handle_brain_graph_neighbors,
    "brain_graph_search_tag": handle_brain_graph_search_tag,
    "brain_graph_stats": handle_brain_graph_stats,
}

TOOL_SCHEMAS: dict[str, Any] = {
    "brain_graph": {
        "type": "object",
        "properties": {
            "center_slug": {
                "type": "string",
                "description": "Slug del nodo central para focar (opcional). Si se omite, retorna grafo completo.",
            },
            "depth": {
                "type": "integer",
                "description": "Profundidad de expansion a partir del centro (default: 2, max: 3).",
            },
        },
    },
    "brain_node_detail": {
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": "Slug del nodo a detallar (requerido).",
            },
        },
        "required": ["slug"],
    },
    "brain_graph_neighbors": {
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": "Slug del nodo central (requerido).",
            },
        },
        "required": ["slug"],
    },
    "brain_graph_search_tag": {
        "type": "object",
        "properties": {
            "tag": {
                "type": "string",
                "description": "Tag a buscar (case-insensitive, requerido).",
            },
        },
        "required": ["tag"],
    },
    "brain_graph_stats": {
        "type": "object",
        "properties": {},
        "description": "Estadisticas del grafo: nodos por tipo/area, tags top, colores e iconos.",
    },
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "brain_graph": (
        "Retorna el grafo completo del Brain Network en formato D3.js force-directed. "
        "Incluye nodes (con type, area, tags, importancia) y edges (related links). "
        "Si se provee center_slug, retorna un subgraph focalizado en ese nodo."
    ),
    "brain_node_detail": (
        "Detalle completo de un nodo: titulo, contenido de todas las secciones "
        "(context, decisions, output, pending), tags, related links y metricas de acceso."
    ),
    "brain_graph_neighbors": (
        "Nodos relacionados directos (1 salto de distancia) a partir de un nodo. "
        "Ordenados por importancia y cantidad de accesos."
    ),
    "brain_graph_search_tag": (
        "Buscar todos los nodos que tienen un tag especifico. "
        "Ideal para filtros y drill-down por categoria en la UI."
    ),
    "brain_graph_stats": (
        "Estadisticas del grafo: total de nodos, distribucion por tipo/area/status, "
        "top tags, y paleta de colores/iconos por tipo de nodo."
    ),
}

# Metadata util para el frontend
METADATA = {
    "typeColors": {
        "session": "#6366f1",
        "concept": "#22d3ee",
        "adr": "#f59e0b",
        "entity": "#a78bfa",
        "decision": "#34d399",
        "pattern": "#fb923c",
    },
    "typeIcons": {
        "session": "chat",
        "concept": "lightbulb",
        "adr": "scale",
        "entity": "box",
        "decision": "check-square",
        "pattern": "repeat",
    },
    "areaColors": {
        "dev": "#60a5fa",
        "ops": "#34d399",
        "ux": "#f472b6",
        "business": "#fbbf24",
        "security": "#f87171",
        "testing": "#a78bfa",
        "architecture": "#22d3ee",
        "data": "#6366f1",
        "infra": "#9ca3af",
        "docs": "#d1d5db",
        "general": "#6b7280",
    },
}


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 Dispatcher
# ---------------------------------------------------------------------------


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code: int, msg: str) -> dict[str, Any]:
        return {
            "jsonrpc": "2.0",
            "id": req_id,
            "error": {"code": code, "message": msg},
        }

    if method == "initialize":
        return ok(
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "antigravity-brain-graph", "version": "1.0.0"},
            }
        )

    if method == "tools/list":
        tools = [
            {
                "name": name,
                "description": TOOL_DESCRIPTIONS.get(name, name),
                "inputSchema": schema,
            }
            for name, schema in TOOL_SCHEMAS.items()
        ]
        return ok({"tools": tools})

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_input = params.get("arguments", {})
        if tool_name not in TOOLS:
            return err(-32601, f"Tool desconocida: {tool_name}")
        try:
            result = TOOLS[tool_name](tool_input)
        except Exception as e:
            logger.error("Tool '%s' lanzo excepcion: %s", tool_name, e)
            result = {"error": f"Error interno en {tool_name}: {e}"}
        is_error = isinstance(result, dict) and "error" in result and not result.get("success")
        return ok(
            {
                "content": [
                    {"type": "text", "text": json.dumps(result, ensure_ascii=False)},
                ],
                **({"isError": True} if is_error else {}),
            }
        )

    if method and method.startswith("notifications/"):
        return None

    return err(-32601, f"Metodo desconocido: {method}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    # Los pipes stdio en Windows heredan la codepage del locale (cp932 en JP),
    # pero el protocolo MCP habla UTF-8: sin esto, el JSON entrante con no-ASCII
    # llega con surrogates sueltos y la respuesta puede fallar al escribirse.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logger.info("Antigravity Brain Graph Server v1.0.0 iniciando")
    try:
        graph = _ensure_graph()
        stats = graph.get_stats()
        logger.info(
            "Grafo listo: %d nodos, %d edges",
            stats.get("total_nodes", 0),
            stats.get("total_connections", 0),
        )
    except Exception as e:
        logger.warning("Brain Graph no inicializado: %s", e)

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                print(json.dumps(response, ensure_ascii=False), flush=True)
        except json.JSONDecodeError as e:
            print(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": f"JSON invalido: {e}"},
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
