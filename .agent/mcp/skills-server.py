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
    from core.skill_registry import SkillRegistry, SkillRegistryError

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


def _handle_read_skill(request_id: int, args: dict) -> dict:
    """
    Leer SKILL.md de un skill (usa registry si disponible).
    """
    skill_name = args.get("skill_name")
    if not skill_name or not isinstance(skill_name, str) or not skill_name.strip():
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "content": [
                    {
                        "type": "text",
                        "text": "Error: skill_name is required and must be a non-empty string",
                    }
                ],
                "isError": True,
            },
        }

    skill_name = skill_name.strip()

    registry = _get_registry()

    if registry:
        # Usar registry
        try:
            skill = registry.get(skill_name, lazy=False)
            if not skill:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"Skill '{skill_name}' not found in registry"}
                        ],
                        "isError": True,
                    },
                }

            # Leer contenido SKILL.md
            skill_path = SKILLS_DIRS[0] / skill_name / "SKILL.md"

            # Prevenir path traversal: verificar que la ruta resuelta está dentro de cada SKILLS_DIR
            try:
                if not any(is_within_root(sd, skill_path) for sd in SKILLS_DIRS):
                    return {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "result": {
                            "content": [
                                {"type": "text", "text": f"SKILL.md not found for '{skill_name}'"}
                            ],
                            "isError": True,
                        },
                    }
            except Exception:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"SKILL.md not found for '{skill_name}'"}
                        ],
                        "isError": True,
                    },
                }

            if not skill_path.exists():
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {"type": "text", "text": f"SKILL.md not found for '{skill_name}'"}
                        ],
                        "isError": True,
                    },
                }

            content = skill_path.read_text(encoding="utf-8", errors="replace")
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": content}]},
            }
        except Exception as e:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [{"type": "text", "text": f"Error reading skill: {e}"}],
                    "isError": True,
                },
            }
    else:
        # Fallback: acceso directo — buscar en todos los directorios de skills
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
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": f"Skill '{skill_name}' not found or has no SKILL.md",
                        }
                    ],
                    "isError": True,
                },
            }

        content = skill_path.read_text(encoding="utf-8", errors="replace")
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {"content": [{"type": "text", "text": content}]},
        }


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
        # Usar registry centralizado (búsqueda cachada)
        try:
            results = registry.search(query, k=limit)
            matches = [name for name, score in results]

            result_text = (
                f"Search results for '{query}' ({len(matches)} found, showing {len(results)}):\n"
            )
            for i, (name, score) in enumerate(results, 1):
                result_text += f"\n{i}. {name} (score: {score:.2f})"

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
                    "content": [{"type": "text", "text": f"Search error: {e}"}],
                    "isError": True,
                },
            }
    else:
        # Fallback: escaneo manual en todos los directorios
        matches = []
        for sd in SKILLS_DIRS:
            if not sd.exists():
                continue
            for item in sd.iterdir():
                if item.is_dir() and not item.name.startswith("."):
                    if query in item.name.lower():
                        matches.append(item.name)

        matches.sort()
        display_list = matches[:limit]
        result_text = (
            f"Search results for '{query}' ({len(matches)} found, showing {len(display_list)}):\n"
            + "\n".join([f"- {s}" for s in display_list])
        )
        if len(matches) > limit:
            result_text += f"\n\n... and {len(matches) - limit} more."

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
