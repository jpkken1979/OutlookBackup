#!/usr/bin/env python3
"""
Antigravity Brain Network MCP Server
=====================================
Servidor MCP que expone la red de inteligencia distribuida del ecosistema.

Tools:
- brain_ingest: Ingestar conocimiento en un brain de app
- brain_query: Buscar conocimiento en uno o todos los brains
- brain_node_read: Leer un nodo especifico
- brain_node_list: Listar nodos con filtros
- brain_lint: Auditoria de salud de un brain
- brain_sync: Sincronizar un app brain al Mother Brain
- brain_connect: Descubrir conexiones cross-app
- brain_promote: Promover conceptos emergentes a globales
- brain_register: Registrar un nuevo app brain en la red
- brain_stats: Estadisticas de la red
- brain_rebuild_index: Reconstruir el indice de un brain

Arquitectura:
    Cada app tiene su propio brain/ local.
    El Mother Brain (.agent/brain/) conecta todos.
    Este servidor MCP es la interfaz unificada.

v1.0.0 — 2026-04-13
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

from core.brain import Brain, BrainNode  # noqa: E402
from core.brain_network import BrainNetwork  # noqa: E402

# ---------------------------------------------------------------------------
# Singleton: Brain Network
# ---------------------------------------------------------------------------
_network: BrainNetwork | None = None
_INIT_ERROR: str | None = None


def _get_project_root() -> Path:
    """Resuelve el directorio raiz del proyecto."""
    root = os.environ.get("ANTIGRAVITY_ROOT", "")
    if root:
        return Path(root)
    # Fallback: subir desde .agent/mcp/ hasta la raiz
    return Path(__file__).parent.parent.parent


def _ensure_network() -> BrainNetwork:
    """Lazy-init del BrainNetwork singleton."""
    global _network, _INIT_ERROR
    if _network is not None:
        return _network

    try:
        project_root = _get_project_root()
        _network = BrainNetwork(project_root)
        logger.info(
            "Brain Network inicializado: mother=%s, apps=%d",
            _network.mother_dir,
            len(_network.list_apps()),
        )
        return _network
    except Exception as e:
        _INIT_ERROR = str(e)
        logger.error("Error inicializando Brain Network: %s", e)
        raise


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_brain_ingest(params: dict[str, Any]) -> dict[str, Any]:
    """Ingesta conocimiento nuevo en un brain.

    Args:
        params: title (requerido), app_id, context, decisions, output,
                pending, area, tags, sources, node_type, source_notes.

    Returns:
        Nodo creado con su slug y metadata.
    """
    title = params.get("title", "")
    if not title:
        return {"error": "title es requerido"}

    app_id = params.get("app_id", "")
    network = _ensure_network()

    # Determinar en que brain ingestar
    if app_id and app_id != "nexus-mother":
        brain = network.get_app_brain(app_id)
        if not brain:
            return {"error": f"App '{app_id}' no registrada. Usa brain_register primero."}
    else:
        brain = network.mother

    node = brain.ingest(
        title=title,
        context=params.get("context", ""),
        decisions=params.get("decisions", ""),
        output=params.get("output", ""),
        pending=params.get("pending", ""),
        area=params.get("area", "general"),
        tags=params.get("tags", []),
        sources=params.get("sources", []),
        node_type=params.get("node_type", "session"),
        source_notes=params.get("source_notes", ""),
    )

    # Auto-sync al Mother Brain si se ingesto en un app brain
    mother_slug = None
    if app_id and app_id != "nexus-mother":
        auto_sync = params.get("auto_sync", True)
        if auto_sync:
            mother_node = network.sync_to_mother(app_id, node)
            mother_slug = mother_node.slug

    return {
        "success": True,
        "slug": node.slug,
        "node_id": node.node_id,
        "app_id": app_id or "nexus-mother",
        "mother_slug": mother_slug,
        "title": node.title,
        "type": node.type,
        "area": node.area,
        "tags": node.tags,
        "related": node.related,
    }


def handle_brain_query(params: dict[str, Any]) -> dict[str, Any]:
    """Busca conocimiento en la red de brains.

    Args:
        params: question (requerido), app_filter, limit.

    Returns:
        Lista de resultados con nodos y relevancia.
    """
    question = params.get("question", "")
    if not question:
        return {"error": "question es requerido"}

    network = _ensure_network()
    results = network.query_network(
        question,
        limit=int(params.get("limit", 10)),
        app_filter=params.get("app_filter"),
    )

    return {
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
                "app_origin": r.node.app_origin,
            }
            for r in results
        ],
    }


def handle_brain_node_read(params: dict[str, Any]) -> dict[str, Any]:
    """Lee un nodo especifico completo.

    Args:
        params: slug (requerido), app_id (default: nexus-mother).

    Returns:
        Nodo completo serializado.
    """
    slug = params.get("slug", "")
    if not slug:
        return {"error": "slug es requerido"}

    app_id = params.get("app_id", "")
    network = _ensure_network()

    brain = network.get_app_brain(app_id) if app_id and app_id != "nexus-mother" else network.mother
    if not brain:
        return {"error": f"App '{app_id}' no registrada"}

    try:
        node = brain.get_node(slug)
        return {"success": True, "node": node.to_dict()}
    except FileNotFoundError:
        return {"error": f"Nodo '{slug}' no encontrado en brain '{app_id or 'nexus-mother'}'"}


def handle_brain_node_list(params: dict[str, Any]) -> dict[str, Any]:
    """Lista nodos con filtros.

    Args:
        params: app_id, node_type, area, status, tag.

    Returns:
        Lista de nodos que matchean los filtros.
    """
    app_id = params.get("app_id", "")
    network = _ensure_network()

    brain = network.get_app_brain(app_id) if app_id and app_id != "nexus-mother" else network.mother
    if not brain:
        return {"error": f"App '{app_id}' no registrada"}

    nodes = brain.list_nodes(
        node_type=params.get("node_type"),
        area=params.get("area"),
        status=params.get("status", "active"),
        tag=params.get("tag"),
    )

    return {
        "success": True,
        "total": len(nodes),
        "nodes": [
            {
                "slug": n.slug,
                "title": n.title,
                "type": n.type,
                "area": n.area,
                "tags": n.tags,
                "date": n.date,
                "status": n.status,
                "app_origin": n.app_origin,
                "related_count": len(n.related),
            }
            for n in nodes
        ],
    }


def handle_brain_lint(params: dict[str, Any]) -> dict[str, Any]:
    """Auditoria de salud de un brain o toda la red.

    Args:
        params: app_id (vacio = toda la red).

    Returns:
        Reporte de lint con score y issues.
    """
    app_id = params.get("app_id", "")
    network = _ensure_network()

    if not app_id:
        # Lint de toda la red
        report = network.lint_network()
        return {"success": True, **report}

    brain = network.get_app_brain(app_id) if app_id != "nexus-mother" else network.mother
    if not brain:
        return {"error": f"App '{app_id}' no registrada"}

    lint_report = brain.lint()
    return {
        "success": True,
        "app_id": app_id,
        "score": lint_report.score,
        "summary": lint_report.summary(),
        "total_nodes": lint_report.total_nodes,
        "healthy_nodes": lint_report.healthy_nodes,
        "issues": [
            {
                "severity": i.severity,
                "category": i.category,
                "message": i.message,
                "node_slug": i.node_slug,
                "suggestion": i.suggestion,
            }
            for i in lint_report.issues
        ],
        "concept_candidates": lint_report.concept_candidates,
    }


def handle_brain_sync(params: dict[str, Any]) -> dict[str, Any]:
    """Sincroniza un app brain al Mother Brain.

    Args:
        params: app_id (requerido), slug (opcional, para sync individual).

    Returns:
        Resultado de la sincronizacion.
    """
    app_id = params.get("app_id", "")
    if not app_id:
        return {"error": "app_id es requerido"}

    network = _ensure_network()
    slug = params.get("slug", "")

    if slug:
        # Sync individual de un nodo
        brain = network.get_app_brain(app_id)
        if not brain:
            return {"error": f"App '{app_id}' no registrada"}
        try:
            node = brain.get_node(slug)
            mother_node = network.sync_to_mother(app_id, node)
            return {
                "success": True,
                "synced": 1,
                "mother_slug": mother_node.slug,
            }
        except FileNotFoundError:
            return {"error": f"Nodo '{slug}' no encontrado en app '{app_id}'"}
    else:
        # Sync completo
        synced = network.sync_app_full(app_id)
        return {"success": True, "synced": synced, "app_id": app_id}


def handle_brain_connect(params: dict[str, Any]) -> dict[str, Any]:
    """Descubre conexiones cross-app en la red.

    Returns:
        Lista de conexiones descubiertas.
    """
    network = _ensure_network()
    connections = network.discover_connections()

    return {
        "success": True,
        "total": len(connections),
        "connections": [c.to_dict() for c in connections[:50]],
    }


def handle_brain_promote(params: dict[str, Any]) -> dict[str, Any]:
    """Promueve conceptos emergentes cross-app a conceptos globales.

    Returns:
        Lista de conceptos promovidos.
    """
    network = _ensure_network()
    promoted = network.promote_concepts()

    return {
        "success": True,
        "promoted": len(promoted),
        "concepts": [
            {
                "slug": n.slug,
                "title": n.title,
                "tags": n.tags,
                "area": n.area,
            }
            for n in promoted
        ],
    }


def handle_brain_register(params: dict[str, Any]) -> dict[str, Any]:
    """Registra un nuevo app brain en la red.

    Args:
        params: app_id (requerido), brain_dir (requerido),
                description, surface.

    Returns:
        Configuracion del brain registrado.
    """
    app_id = params.get("app_id", "")
    brain_dir = params.get("brain_dir", "")
    if not app_id or not brain_dir:
        return {"error": "app_id y brain_dir son requeridos"}

    network = _ensure_network()

    # Resolver path relativo desde el project root
    brain_path = Path(brain_dir)
    if not brain_path.is_absolute():
        brain_path = network.project_root / brain_path

    config = network.register_app(
        app_id=app_id,
        brain_dir=brain_path,
        description=params.get("description", ""),
        surface=params.get("surface", "unknown"),
    )

    return {
        "success": True,
        "app_id": config.app_id,
        "brain_dir": config.brain_dir,
        "surface": config.surface,
        "message": f"Brain '{app_id}' registrado en la red",
    }


def handle_brain_stats(params: dict[str, Any]) -> dict[str, Any]:
    """Estadisticas de la red de brains.

    Returns:
        Stats globales y por brain.
    """
    network = _ensure_network()
    return {"success": True, **network.network_stats()}


def handle_brain_rebuild_index(params: dict[str, Any]) -> dict[str, Any]:
    """Reconstruye el indice de un brain.

    Args:
        params: app_id (vacio = Mother Brain).

    Returns:
        Numero de nodos indexados.
    """
    app_id = params.get("app_id", "")
    network = _ensure_network()

    brain = network.get_app_brain(app_id) if app_id and app_id != "nexus-mother" else network.mother
    if not brain:
        return {"error": f"App '{app_id}' no registrada"}

    count = brain.rebuild_index()
    return {"success": True, "indexed": count, "app_id": app_id or "nexus-mother"}


def handle_brain_traverse(params: dict[str, Any]) -> dict[str, Any]:
    """Navega el grafo de conocimiento desde un nodo.

    BFS que descubre todo el conocimiento conectado a N saltos.
    Permite descubrir relaciones indirectas: JWT → Token → Security.

    Args:
        params: slug (requerido), app_id, max_depth (default: 3).

    Returns:
        Vecindario del nodo con nodos por nivel de profundidad.
    """
    slug = params.get("slug", "")
    if not slug:
        return {"error": "slug es requerido"}

    app_id = params.get("app_id", "")
    network = _ensure_network()

    brain = network.get_app_brain(app_id) if app_id and app_id != "nexus-mother" else network.mother
    if not brain:
        return {"error": f"App '{app_id}' no registrada"}

    max_depth = int(params.get("max_depth", 3))
    neighborhood = brain.get_neighborhood(slug, depth=max_depth)

    return {"success": True, **neighborhood}


def handle_brain_consolidate(params: dict[str, Any]) -> dict[str, Any]:
    """Consolida memoria: archiva nodos viejos y huerfanos.

    Nodos con importancia 'critical' NUNCA se archivan.
    Solo cambia status a 'archived', nunca elimina.

    Args:
        params: app_id (vacio = toda la red), min_age_days.

    Returns:
        Reporte de consolidacion.
    """
    app_id = params.get("app_id", "")
    min_age_days = int(params.get("min_age_days", 30))
    network = _ensure_network()

    if not app_id:
        # Consolidar toda la red
        report = network.consolidate_network(min_age_days=min_age_days)
        return {"success": True, **report}

    brain = network.get_app_brain(app_id) if app_id != "nexus-mother" else network.mother
    if not brain:
        return {"error": f"App '{app_id}' no registrada"}

    report = brain.consolidate(min_age_days=min_age_days)
    return {"success": True, "app_id": app_id, **report}


def handle_brain_conflicts(params: dict[str, Any]) -> dict[str, Any]:
    """Detecta conocimiento contradictorio entre apps.

    Busca nodos de diferentes apps sobre el mismo tema
    pero con contenido divergente.

    Returns:
        Lista de conflictos potenciales.
    """
    network = _ensure_network()
    conflicts = network.detect_conflicts()

    return {
        "success": True,
        "total": len(conflicts),
        "conflicts": conflicts[:20],
    }


# ---------------------------------------------------------------------------
# Tool Registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, Any] = {
    "brain_ingest": handle_brain_ingest,
    "brain_query": handle_brain_query,
    "brain_node_read": handle_brain_node_read,
    "brain_node_list": handle_brain_node_list,
    "brain_lint": handle_brain_lint,
    "brain_sync": handle_brain_sync,
    "brain_connect": handle_brain_connect,
    "brain_promote": handle_brain_promote,
    "brain_register": handle_brain_register,
    "brain_stats": handle_brain_stats,
    "brain_rebuild_index": handle_brain_rebuild_index,
    "brain_traverse": handle_brain_traverse,
    "brain_consolidate": handle_brain_consolidate,
    "brain_conflicts": handle_brain_conflicts,
}

TOOL_SCHEMAS: dict[str, Any] = {
    "brain_ingest": {
        "type": "object",
        "properties": {
            "title": {
                "type": "string",
                "description": "Titulo del conocimiento a ingestar",
            },
            "app_id": {
                "type": "string",
                "description": "ID de la app (vacio = Mother Brain)",
            },
            "context": {"type": "string", "description": "Contexto/background"},
            "decisions": {"type": "string", "description": "Decisiones tomadas"},
            "output": {"type": "string", "description": "Resultados concretos"},
            "pending": {"type": "string", "description": "Tareas pendientes"},
            "area": {
                "type": "string",
                "description": "Area tematica (dev, ops, ux, business, etc.)",
            },
            "tags": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Tags para discovery",
            },
            "sources": {
                "type": "array",
                "items": {"type": "string"},
                "description": "Referencias a fuentes (app:id, repo:path, url:...)",
            },
            "node_type": {
                "type": "string",
                "enum": ["session", "concept", "adr", "entity", "decision", "pattern"],
                "description": "Tipo de nodo (default: session)",
            },
            "source_notes": {"type": "string", "description": "Notas sobre fuentes"},
            "auto_sync": {
                "type": "boolean",
                "description": "Auto-sync al Mother Brain (default: true)",
            },
        },
        "required": ["title"],
    },
    "brain_query": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "Pregunta o termino de busqueda. Se busca en TODA la red.",
            },
            "app_filter": {
                "type": "string",
                "description": "Filtrar a un brain especifico (ej: telegram-bot)",
            },
            "limit": {
                "type": "integer",
                "description": "Maximo de resultados (default: 10)",
            },
        },
        "required": ["question"],
    },
    "brain_node_read": {
        "type": "object",
        "properties": {
            "slug": {"type": "string", "description": "Slug del nodo a leer"},
            "app_id": {
                "type": "string",
                "description": "Brain donde buscar (vacio = Mother Brain)",
            },
        },
        "required": ["slug"],
    },
    "brain_node_list": {
        "type": "object",
        "properties": {
            "app_id": {
                "type": "string",
                "description": "Brain a consultar (vacio = Mother Brain)",
            },
            "node_type": {
                "type": "string",
                "enum": ["session", "concept", "adr", "entity", "decision", "pattern"],
            },
            "area": {"type": "string"},
            "status": {
                "type": "string",
                "enum": ["active", "superseded", "archived"],
            },
            "tag": {"type": "string", "description": "Filtrar por tag"},
        },
    },
    "brain_lint": {
        "type": "object",
        "properties": {
            "app_id": {
                "type": "string",
                "description": "Brain a auditar (vacio = toda la red)",
            },
        },
    },
    "brain_sync": {
        "type": "object",
        "properties": {
            "app_id": {
                "type": "string",
                "description": "App brain a sincronizar al Mother Brain",
            },
            "slug": {
                "type": "string",
                "description": "Slug especifico a sincronizar (vacio = sync completo)",
            },
        },
        "required": ["app_id"],
    },
    "brain_connect": {
        "type": "object",
        "properties": {},
        "description": "Descubre conexiones cross-app automaticamente",
    },
    "brain_promote": {
        "type": "object",
        "properties": {},
        "description": "Promueve conceptos que aparecen en 2+ apps a conceptos globales",
    },
    "brain_register": {
        "type": "object",
        "properties": {
            "app_id": {
                "type": "string",
                "description": "ID unico de la app (ej: telegram-bot, nexus, my-project)",
            },
            "brain_dir": {
                "type": "string",
                "description": "Path al directorio brain/ de la app (relativo al proyecto o absoluto)",
            },
            "description": {"type": "string", "description": "Descripcion de la app"},
            "surface": {
                "type": "string",
                "enum": ["telegram-bot", "nexus", "claude-code", "project", "unknown"],
                "description": "Tipo de superficie",
            },
        },
        "required": ["app_id", "brain_dir"],
    },
    "brain_stats": {
        "type": "object",
        "properties": {},
        "description": "Estadisticas globales de la red de brains",
    },
    "brain_rebuild_index": {
        "type": "object",
        "properties": {
            "app_id": {
                "type": "string",
                "description": "Brain a reconstruir (vacio = Mother Brain)",
            },
        },
    },
    "brain_traverse": {
        "type": "object",
        "properties": {
            "slug": {
                "type": "string",
                "description": "Slug del nodo de inicio para navegar el grafo",
            },
            "app_id": {
                "type": "string",
                "description": "Brain donde buscar (vacio = Mother Brain)",
            },
            "max_depth": {
                "type": "integer",
                "description": "Profundidad maxima de busqueda (default: 3)",
            },
        },
        "required": ["slug"],
    },
    "brain_consolidate": {
        "type": "object",
        "properties": {
            "app_id": {
                "type": "string",
                "description": "Brain a consolidar (vacio = toda la red)",
            },
            "min_age_days": {
                "type": "integer",
                "description": "Edad minima en dias para archivar (default: 30)",
            },
        },
    },
    "brain_conflicts": {
        "type": "object",
        "properties": {},
        "description": "Detecta conocimiento contradictorio entre apps",
    },
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "brain_ingest": (
        "Ingestar conocimiento nuevo en un brain de la red. "
        "Crea nodo con frontmatter YAML, cross-refs bidireccionales, "
        "y auto-sync al Mother Brain."
    ),
    "brain_query": (
        "Buscar conocimiento en toda la red de brains. "
        "Busca en el Mother Brain + todos los app brains registrados."
    ),
    "brain_node_read": "Leer un nodo completo por su slug.",
    "brain_node_list": "Listar nodos de un brain con filtros opcionales.",
    "brain_lint": (
        "Auditoria de salud: orphan nodes, broken links, conceptos emergentes, "
        "index desync. Read-only, nunca modifica."
    ),
    "brain_sync": (
        "Sincronizar un app brain al Mother Brain. "
        "El Mother Brain mantiene copia indexada de todo el conocimiento."
    ),
    "brain_connect": (
        "Descubrir conexiones cross-app automaticamente. "
        "Analiza tags, areas y contenido para encontrar relaciones."
    ),
    "brain_promote": (
        "Promover conceptos emergentes: tags que aparecen en 2+ apps "
        "se convierten en nodos concepto globales en el Mother Brain."
    ),
    "brain_register": (
        "Registrar un nuevo app brain en la red. "
        "Cada app puede tener su propio brain/ con indice y nodos."
    ),
    "brain_stats": "Estadisticas globales de la red: nodos, conexiones, brains.",
    "brain_rebuild_index": "Reconstruir el indice denso de un brain desde sus nodos.",
    "brain_traverse": (
        "Navegar el grafo de conocimiento desde un nodo. "
        "BFS que descubre relaciones indirectas a N saltos: "
        "JWT → Token → Security."
    ),
    "brain_consolidate": (
        "Consolidar memoria: archivar nodos viejos y huerfanos. "
        "Nodos con importancia 'critical' NUNCA se archivan. "
        "Solo cambia status, nunca elimina."
    ),
    "brain_conflicts": (
        "Detectar conocimiento contradictorio entre apps. "
        "Busca nodos sobre el mismo tema pero con contenido divergente."
    ),
}


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 Dispatcher
# ---------------------------------------------------------------------------


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    """Despacha una solicitud JSON-RPC 2.0 al manejador correspondiente.

    Args:
        request: Objeto JSON-RPC con method, id y params.

    Returns:
        Respuesta JSON-RPC o None para notificaciones.
    """
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
                "serverInfo": {
                    "name": "antigravity-brain",
                    "version": "1.0.0",
                },
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
    """Punto de entrada. Lee JSON-RPC desde stdin."""
    logger.info("Antigravity Brain Network Server v1.0.0 iniciando")

    try:
        network = _ensure_network()
        apps = network.list_apps()
        logger.info(
            "Red inicializada: Mother Brain + %d apps registradas",
            len(apps),
        )
        for app in apps:
            logger.info("  - %s (%s) en %s", app.app_id, app.surface, app.brain_dir)
    except Exception as e:
        logger.warning("Brain Network no inicializado: %s", e)

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
