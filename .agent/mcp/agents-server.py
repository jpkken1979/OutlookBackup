#!/usr/bin/env python3
"""
Antigravity Skills MCP Server
=============================
Exposes the generic skills library as MCP tools.
Allows any AI agent to discover, read, and utilize the 600+ available skills.

Tools:
- list_skills: List available skills with optional filtering
- read_skill: Read the full instructions (SKILL.md) of a specific skill
- search_skills: Search skills by name or keyword
"""

import json
import sys
from pathlib import Path

try:
    from .security_utils import is_within_root
except ImportError:
    from security_utils import is_within_root

# Configuration
BASE_DIR = Path(__file__).parent.parent.parent
SKILLS_DIR = BASE_DIR / ".agent" / "skills"


def _make_result(request_id, text, is_error=False):
    """Construye una respuesta JSON-RPC con contenido de texto.

    Args:
        request_id: ID de la petición JSON-RPC.
        text: Texto de respuesta.
        is_error: Si True, marca la respuesta como error.

    Returns:
        Dict con la respuesta JSON-RPC.
    """
    result = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _coerce_limit(raw_value, default=50, minimum=1, maximum=500):
    """Normaliza límites recibidos por MCP sin confiar en el cliente."""
    try:
        limit = int(raw_value)
    except (TypeError, ValueError):
        limit = default
    return max(minimum, min(limit, maximum))


def _handle_list_skills(args, request_id):
    """Maneja la herramienta list_skills.

    Args:
        args: Argumentos de la herramienta.
        request_id: ID de la petición JSON-RPC.

    Returns:
        Respuesta JSON-RPC.
    """
    category = args.get("category", "")
    limit = _coerce_limit(args.get("limit", 100), default=100)

    if not SKILLS_DIR.exists():
        return _make_result(request_id, "Skills directory not found")

    found = []
    for item in SKILLS_DIR.iterdir():
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

    return _make_result(request_id, result_text)


def _handle_read_skill(args, request_id):
    """Maneja la herramienta read_skill.

    Args:
        args: Argumentos de la herramienta.
        request_id: ID de la petición JSON-RPC.

    Returns:
        Respuesta JSON-RPC.
    """
    skill_name = args.get("skill_name")
    if not skill_name or not isinstance(skill_name, str) or not skill_name.strip():
        return _make_result(
            request_id,
            "Error: skill_name is required and must be a non-empty string",
            is_error=True,
        )

    skill_name = skill_name.strip()
    skill_path = SKILLS_DIR / skill_name / "SKILL.md"
    not_found_msg = f"Skill '{skill_name}' not found or has no SKILL.md"

    try:
        if not is_within_root(SKILLS_DIR, skill_path):
            return _make_result(request_id, not_found_msg, is_error=True)
    except Exception:
        return _make_result(request_id, not_found_msg, is_error=True)

    if not skill_path.exists():
        return _make_result(request_id, not_found_msg, is_error=True)

    content = skill_path.read_text(encoding="utf-8", errors="replace")
    return _make_result(request_id, content)


def _handle_search_skills(args, request_id):
    """Maneja la herramienta search_skills.

    Args:
        args: Argumentos de la herramienta.
        request_id: ID de la petición JSON-RPC.

    Returns:
        Respuesta JSON-RPC.
    """
    query = args.get("query", "").lower().strip()
    limit = _coerce_limit(args.get("limit", 50))
    if not query:
        return _make_result(request_id, "Empty query")

    matches = []
    for item in SKILLS_DIR.iterdir():
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
    return _make_result(request_id, result_text)


_TOOL_DEFINITIONS = [
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

_TOOL_HANDLERS = {
    "list_skills": _handle_list_skills,
    "read_skill": _handle_read_skill,
    "search_skills": _handle_search_skills,
}


def handle_request(request):
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

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

    # Notifications don't get responses (JSON-RPC 2.0 spec)
    if method and method.startswith("notifications/"):
        return None

    if method == "ping":
        return {"jsonrpc": "2.0", "id": request_id, "result": {}}

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _TOOL_DEFINITIONS}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        handler = _TOOL_HANDLERS.get(name)
        if handler:
            return handler(args, request_id)

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"},
    }


if __name__ == "__main__":
    import time

    # Los pipes stdio en Windows heredan la codepage del locale (cp932 en JP),
    # pero el protocolo MCP habla UTF-8: sin esto, el JSON entrante con no-ASCII
    # llega con surrogates sueltos y la respuesta puede fallar al escribirse.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    # Loop MCP stdio con resiliencia ante EOF temporal
    _empty_count = 0
    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                _empty_count += 1
                if _empty_count >= 5:
                    break  # EOF persistente - cliente desconectado
                time.sleep(0.2)
                continue
            _empty_count = 0
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except json.JSONDecodeError:
            continue
        except KeyboardInterrupt:
            break
        except Exception:
            import traceback

            print(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32603, "message": "Internal error"},
                    }
                ),
                flush=True,
            )
            print(traceback.format_exc(), file=sys.stderr, flush=True)
