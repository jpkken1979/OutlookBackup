#!/usr/bin/env python3
"""
Antigravity Skills MCP Server v2.0
===================================
Exposes the generic skills library as MCP tools using centralized SkillRegistry.

Replaces 6 fragmented directory-scanning implementations with single canonical registry.

Tools:
- list_skills: List available skills with optional filtering (uses registry)
- read_skill: Read the full instructions (SKILL.md) of a specific skill
- search_skills: Search skills by name or keyword (uses registry)

Integration: Phase 1 Consolidation Fase 3 (MCP Integration)
- Singleton SkillRegistry eliminates redundant directory scans
- Unified search across all skill discovery points
- Cached results improve latency
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

try:
    from .security_utils import is_within_root
except ImportError:
    from security_utils import is_within_root

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent
SKILLS_DIRS = [
    BASE_DIR / ".agent" / "skills",
    BASE_DIR / ".agent" / "skills-custom",
]

# Import SkillRegistry (centralized skills discovery)
try:
    sys.path.insert(0, str(BASE_DIR / ".agent"))
    from core.skill_registry import SkillRegistry, SkillRegistryError  # noqa: F401

    REGISTRY_ENABLED = True
except ImportError:
    REGISTRY_ENABLED = False
    SkillRegistry = None

# Singleton registry instance
_registry_instance: SkillRegistry | None = None


def _get_registry() -> SkillRegistry | None:
    """Obtener instancia singleton de SkillRegistry con fallback graceful."""
    global _registry_instance
    if not REGISTRY_ENABLED:
        return None

    if _registry_instance is None:
        try:
            _registry_instance = SkillRegistry.instance(SKILLS_DIRS)
        except Exception:
            return None

    return _registry_instance


def _coerce_limit(
    raw_value: object, default: int = 50, minimum: int = 1, maximum: int = 500
) -> int:
    """Normaliza límites recibidos por MCP sin confiar en el cliente."""
    try:
        limit = int(raw_value)
    except (TypeError, ValueError):
        limit = default
    return max(minimum, min(limit, maximum))


def _handle_list_skills(request_id: int, args: dict) -> dict:
    """
    Listar skills usando SkillRegistry (centralizado).

    Reemplaza búsqueda manual de directorio con llamada al registry.
    Antes: 6 implementaciones independientes scanning directorio
    Ahora: 1 registry centralizado con caching
    """
    category = args.get("category", "")
    limit = _coerce_limit(args.get("limit", 100), default=100)

    registry = _get_registry()

    if registry:
        # Usar registry centralizado (una sola búsqueda cachada)
        try:
            all_skills = registry.list_all(lazy=True)
            found = [
                s.name for s in all_skills if not category or category.lower() in s.name.lower()
            ]
            found.sort()
            display_list = found[:limit]

            result_text = f"Found {len(found)} skills (showing {len(display_list)}):\n\n"
            result_text += "\n".join([f"- {s}" for s in display_list])

            if len(found) > limit:
                result_text += f"\n\n... and {len(found) - limit} more."

            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": result_text}]},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"Registry error: {e}"}],
                    "isError": True,
                },
            }
    else:
        # Fallback: escaneo manual de ambos directorios (sin registry)
        found = []
        for sd in SKILLS_DIRS:
            if not sd.exists():
                continue
            for item in sd.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    if category and category.lower() not in item.name.lower():
                        continue
                    found.append(item.name)

        found.sort()
        display_list = found[:limit]

        result_text = f"Found {len(found)} skills (showing {len(display_list)}):\n\n"
        result_text += "\n".join([f"- {s}" for s in display_list])

        if len(found) > limit:
            result_text += f"\n\n... and {len(found) - limit} more."

        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": result_text}]},
        }


def _skill_text_response(request_id: int, text: str, *, is_error: bool = False) -> dict:
    """Construye una respuesta JSON-RPC con un único bloque de texto.

    Args:
        request_id: Id de la request JSON-RPC a la que responde.
        text: Texto a incluir en el bloque `content`.
        is_error: Si `True`, marca el resultado como error (`isError`).

    Returns:
        Diccionario con la respuesta JSON-RPC 2.0 lista para serializar.
    """
    result: dict = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _read_skill_via_registry(request_id: int, registry: Any, skill_name: str) -> dict:
    """Lee el SKILL.md de un skill registrado usando el registry centralizado.

    Args:
        request_id: Id de la request JSON-RPC a la que responde.
        registry: Instancia del SkillRegistry centralizado.
        skill_name: Nombre del skill (ya validado y normalizado).

    Returns:
        Respuesta JSON-RPC con el contenido del SKILL.md o un error.
    """
    try:
        skill = registry.get(skill_name, lazy=False)
        if not skill:
            return _skill_text_response(
                request_id, f"Skill '{skill_name}' not found in registry", is_error=True
            )

        skill_path = SKILLS_DIRS[0] / skill_name / "SKILL.md"

        # Prevenir path traversal: verificar que la ruta resuelta está dentro de cada SKILLS_DIR
        try:
            within = any(is_within_root(sd, skill_path) for sd in SKILLS_DIRS)
        except Exception:
            within = False
        if not within or not skill_path.exists():
            return _skill_text_response(
                request_id, f"SKILL.md not found for '{skill_name}'", is_error=True
            )

        content = skill_path.read_text(encoding="utf-8", errors="replace")
        return _skill_text_response(request_id, content)
    except Exception as e:
        return _skill_text_response(request_id, f"Error reading skill: {e}", is_error=True)


def _read_skill_via_scan(request_id: int, skill_name: str) -> dict:
    """Lee el SKILL.md de un skill escaneando directamente los directorios.

    Fallback usado cuando no hay registry disponible. Busca el `SKILL.md`
    en cada directorio de skills, previniendo path traversal.

    Args:
        request_id: Id de la request JSON-RPC a la que responde.
        skill_name: Nombre del skill (ya validado y normalizado).

    Returns:
        Respuesta JSON-RPC con el contenido del SKILL.md o un error.
    """
    skill_path = None
    for sd in SKILLS_DIRS:
        candidate = sd / skill_name / "SKILL.md"
        # Prevenir path traversal
        try:
            if not is_within_root(sd, candidate):
                continue
        except Exception:
            continue
        if candidate.exists():
            skill_path = candidate
            break

    if skill_path is None:
        return _skill_text_response(
            request_id, f"Skill '{skill_name}' not found or has no SKILL.md", is_error=True
        )

    content = skill_path.read_text(encoding="utf-8", errors="replace")
    return _skill_text_response(request_id, content)


def _handle_read_skill(request_id: int, args: dict) -> dict:
    """
    Leer SKILL.md de un skill (usa registry si disponible).
    """
    skill_name = args.get("skill_name")
    if not skill_name or not isinstance(skill_name, str) or not skill_name.strip():
        return _skill_text_response(
            request_id,
            "Error: skill_name is required and must be a non-empty string",
            is_error=True,
        )

    skill_name = skill_name.strip()

    registry = _get_registry()
    if registry:
        return _read_skill_via_registry(request_id, registry, skill_name)
    return _read_skill_via_scan(request_id, skill_name)


def _search_skills_via_registry(registry: Any, query: str, limit: int) -> str:
    """Busca skills usando el SkillRegistry centralizado (con scores).

    Args:
        registry: Instancia de SkillRegistry.
        query: Query en minúsculas.
        limit: Máximo de resultados.

    Returns:
        Texto formateado con los resultados rankeados.
    """
    results = registry.search(query, k=limit)
    result_text = f"Search results for '{query}' ({len(results)} found, showing {len(results)}):\n"
    for i, (name, score) in enumerate(results, 1):
        result_text += f"\n{i}. {name} (score: {score:.2f})"
    return result_text


def _search_skills_via_scan(query: str, limit: int) -> str:
    """Fallback: escaneo manual de directorios de skills por substring.

    Args:
        query: Query en minúsculas.
        limit: Máximo de resultados a mostrar.

    Returns:
        Texto formateado con los nombres que matchean.
    """
    matches = []
    for sd in SKILLS_DIRS:
        if not sd.exists():
            continue
        for item in sd.iterdir():
            if item.is_dir() and not item.name.startswith(".") and query in item.name.lower():
                matches.append(item.name)

    matches.sort()
    display_list = matches[:limit]
    result_text = (
        f"Search results for '{query}' ({len(matches)} found, showing {len(display_list)}):\n"
        + "\n".join([f"- {s}" for s in display_list])
    )
    if len(matches) > limit:
        result_text += f"\n\n... and {len(matches) - limit} more."
    return result_text


def _handle_search_skills(request_id: int, args: dict) -> dict:
    """
    Buscar skills por keyword usando SkillRegistry (centralizado).

    Reemplaza búsqueda manual independiente con llamada al registry.
    """
    query = args.get("query", "").lower().strip()
    limit = _coerce_limit(args.get("limit", 50))

    if not query:
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": "Empty query"}]},
        }

    registry = _get_registry()

    if registry:
        try:
            result_text = _search_skills_via_registry(registry, query, limit)
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"Search error: {e}"}],
                    "isError": True,
                },
            }
    else:
        result_text = _search_skills_via_scan(query, limit)

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "result": {"content": [{"type": "text", "text": result_text}]},
    }


def handle_request(request):
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    # Notifications don't get responses (JSON-RPC 2.0 spec)
    if method and method.startswith("notifications/"):
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "antigravity-skills", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        tools = [
            {
                "name": "list_skills",
                "description": "List available skills in the library",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Filter by category (folder name partial match)",
                        },
                        "limit": {"type": "integer", "description": "Max results", "default": 100},
                    },
                },
            },
            {
                "name": "read_skill",
                "description": "Read the instructions (SKILL.md) for a specific skill",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "skill_name": {
                            "type": "string",
                            "description": "Exact name of the skill (folder name)",
                        }
                    },
                    "required": ["skill_name"],
                },
            },
            {
                "name": "search_skills",
                "description": "Search for skills by keyword",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search term"},
                        "limit": {"type": "integer", "description": "Max results", "default": 50},
                    },
                    "required": ["query"],
                },
            },
        ]
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "list_skills":
            return _handle_list_skills(request_id, args)
        elif name == "read_skill":
            return _handle_read_skill(request_id, args)
        elif name == "search_skills":
            return _handle_search_skills(request_id, args)

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"},
    }


if __name__ == "__main__":
    # Los pipes stdio en Windows heredan la codepage del locale (cp932 en JP),
    # pero el protocolo MCP habla UTF-8: sin esto, el JSON entrante con no-ASCII
    # llega con surrogates sueltos y la respuesta puede fallar al escribirse.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except Exception:
            logger.exception("main loop error")
