#!/usr/bin/env python3
"""
Antigravity Universal Search MCP Server
========================================

Expone el motor UniversalSearch como servidor MCP con stdio.

Tools:
- universal_search: Búsqueda unificada multi-fuente
- universal_search_sources: Fuentes disponibles

v1.0.0 — 2026-05-09
"""

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

from core.universal_search import UniversalSearch  # noqa: E402

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_search_engine: UniversalSearch | None = None


def _get_project_root() -> Path:
    """Resuelve el directorio raíz del proyecto."""
    root = os.environ.get("ANTIGRAVITY_ROOT", "")
    if root:
        return Path(root)
    return Path(__file__).parent.parent.parent


def _get_engine() -> UniversalSearch:
    """Lazy-init singleton del motor de búsqueda."""
    global _search_engine
    if _search_engine is None:
        _search_engine = UniversalSearch(_get_project_root())
    return _search_engine


# ---------------------------------------------------------------------------
# Protocolo MCP stdio
# ---------------------------------------------------------------------------

TOOL_DEFINITIONS = [
    {
        "name": "universal_search",
        "description": (
            "Búsqueda unificada en el ecosistema Antigravity. Busca en memorias "
            "(.claude/memory/), Brain Network (.agent/brain/), código fuente, "
            "y agentes/skills. Retorna resultados ordenados por relevancia."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Término de búsqueda (mínimo 2 caracteres)",
                },
                "sources": {
                    "type": "array",
                    "items": {"type": "string", "enum": ["memories", "brain", "code", "agents"]},
                    "description": "Fuentes a consultar. Si se omite, busca en todas.",
                    "default": ["memories", "brain", "code", "agents"],
                },
                "limit_per_source": {
                    "type": "integer",
                    "description": "Límite de resultados por fuente. Default: 5.",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "universal_search_sources",
        "description": "Lista las fuentes disponibles con metadata.",
        "inputSchema": {
            "type": "object",
            "properties": {},
        },
    },
]


def _tool_response(tool_name: str, result: Any) -> str:
    """Construye una respuesta MCP de tool use."""
    return json.dumps(
        {
            "tool": tool_name,
            "result": result,
        },
        ensure_ascii=False,
    )


def _error_response(tool_name: str, error: str) -> str:
    """Construye una respuesta de error."""
    return json.dumps(
        {
            "tool": tool_name,
            "error": error,
        },
        ensure_ascii=False,
    )


def handle_tool(tool_name: str, arguments: dict[str, Any]) -> str:
    """Maneja una llamada a tool."""
    engine = _get_engine()

    if tool_name == "universal_search":
        query = arguments.get("query", "").strip()
        if len(query) < 2:
            return _error_response(tool_name, "query debe tener al menos 2 caracteres")

        sources = arguments.get("sources")
        limit = arguments.get("limit_per_source", 5)

        results = engine.search(query, sources=sources, limit_per_source=limit)

        return _tool_response(
            tool_name,
            {
                "query": query,
                "total": len(results),
                "sources_used": sources or UniversalSearch.DEFAULT_SOURCES,
                "results": [
                    {
                        "title": r.title,
                        "preview": r.preview,
                        "source": r.source,
                        "source_label": r.source_label,
                        "score": r.score,
                        "path": r.path,
                        "tags": r.tags,
                        "metadata": r.metadata,
                    }
                    for r in results
                ],
            },
        )

    if tool_name == "universal_search_sources":
        return _tool_response(
            tool_name,
            {
                "sources": engine.available_sources(),
            },
        )

    return _error_response(tool_name, f"Unknown tool: {tool_name}")


# ---------------------------------------------------------------------------
# Handshake
# ---------------------------------------------------------------------------


def main() -> None:
    """Loop principal — lee requests MCP desde stdin, responde por stdout."""
    # Los pipes stdio en Windows heredan la codepage del locale (cp932 en JP),
    # pero el protocolo MCP habla UTF-8: sin esto, el JSON entrante con no-ASCII
    # llega con surrogates sueltos y la respuesta puede fallar al escribirse.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logger.info("Universal Search MCP Server iniciado")

    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue

        try:
            request = json.loads(line)
        except json.JSONDecodeError:
            continue

        method = request.get("method", "")
        params = request.get("params", {})

        if method == "initialize":
            print(
                json.dumps(
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": "antigravity-universal-search",
                            "version": "1.0.0",
                        },
                    }
                )
            )
            sys.stdout.flush()

        elif method == "tools/list":
            print(
                json.dumps(
                    {
                        "tools": TOOL_DEFINITIONS,
                    }
                )
            )
            sys.stdout.flush()

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            result = handle_tool(tool_name, arguments)
            print(
                json.dumps(
                    {
                        "content": [
                            {
                                "type": "text",
                                "text": result,
                            }
                        ]
                    }
                )
            )
            sys.stdout.flush()

        elif method == "notifications/initialized":
            pass  # handshake completo


if __name__ == "__main__":
    main()
