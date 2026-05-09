#!/usr/bin/env python3
"""Antigravity Context Engine MCP Server.

Expone control del sistema de Pluggable Context Engines:
    - context_engine_list: engines disponibles + metadata.
    - context_engine_current: engine activo + fuente de seleccion.
    - context_engine_switch: cambio en caliente (escribe .antigravity/config.json).
    - context_engine_preview: preview del contexto sin side effects.
    - context_engine_stats: diagnostico basico (chars, tokens aproximados).

v1.0.0 - 2026-04-17
"""

from __future__ import annotations

import asyncio
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

_agent_dir = Path(__file__).parent.parent
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))

from core.context_engines import (  # noqa: E402
    ContextEngineInput,
    get_engine,
    list_engines,
    resolve_engine_name,
)
from core.context_engines.registry import (  # noqa: E402
    config_snapshot,
    engine_names,
)
from core.context_injection import (  # noqa: E402
    enhance_agent_prompt,
    estimate_tokens_approx,
    measure_prompt_footprint,
    prepare_context,
)


def _err(msg: str) -> dict[str, Any]:
    return {"success": False, "error": msg}


def handle_context_engine_list(params: dict[str, Any]) -> dict[str, Any]:
    """Lista los engines disponibles con metadata."""
    engines = list_engines()
    return {
        "success": True,
        "engines": [
            {
                "name": m.name,
                "description": m.description,
                "requires": list(m.requires),
                "version": m.version,
            }
            for m in engines
        ],
    }


def handle_context_engine_current(params: dict[str, Any]) -> dict[str, Any]:
    """Retorna el engine resuelto + fuentes de seleccion."""
    snap = config_snapshot()
    return {"success": True, **snap}


def handle_context_engine_switch(params: dict[str, Any]) -> dict[str, Any]:
    """Cambia el engine activo escribiendo .antigravity/config.json.

    Args:
        name: slug del nuevo engine.
        project_dir: (opcional) donde escribir el config. Si None usa
            ANTIGRAVITY_ROOT o CWD.
    """
    name = str(params.get("name", "")).strip()
    if not name:
        return _err("name es requerido")
    available = engine_names()
    if name not in available:
        return _err(f"engine desconocido: {name}; disponibles={available}")

    project_dir = params.get("project_dir")
    if project_dir:
        target = Path(project_dir)
    else:
        root = os.environ.get("ANTIGRAVITY_ROOT", "").strip()
        target = Path(root) if root else Path.cwd()

    config_path = target / ".antigravity" / "config.json"
    try:
        config_path.parent.mkdir(parents=True, exist_ok=True)
        if config_path.is_file():
            data = json.loads(config_path.read_text(encoding="utf-8"))
        else:
            data = {}
        data["context_engine"] = name
        config_path.write_text(
            json.dumps(data, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    except OSError as exc:
        return _err(f"no pude escribir {config_path}: {exc}")

    return {"success": True, "name": name, "config_path": str(config_path)}


def handle_context_engine_preview(params: dict[str, Any]) -> dict[str, Any]:
    """Ejecuta el engine activo con una tarea de ejemplo y devuelve el ctx.

    NO escribe nada ni dispara side-effects duraderos — es solo inspeccion.

    Args:
        task: tarea de ejemplo (requerida).
        engine_name: override opcional del engine a probar.
        project_dir, current_file, open_files: contextuales.
        include_prompt: si true, devuelve tambien el prompt enriquecido.
    """
    task = str(params.get("task", "")).strip()
    if not task:
        return _err("task es requerido")

    engine_name = params.get("engine_name") or None
    project_dir = params.get("project_dir") or None
    current_file = params.get("current_file") or None
    open_files = params.get("open_files") or []
    include_prompt = bool(params.get("include_prompt", False))

    try:
        ctx = asyncio.run(
            prepare_context(
                task=task,
                project_dir=project_dir,
                current_file=current_file,
                open_files=list(open_files),
                engine_name=engine_name,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(f"preview fallo: {exc}")

    result: dict[str, Any] = {
        "success": True,
        "engine": resolve_engine_name(engine_name),
        "context": ctx.to_dict(),
        "section": ctx.to_prompt_section(),
    }
    if include_prompt:
        result["prompt"] = enhance_agent_prompt("### TAREA ASIGNADA\n" + task, ctx)
    return result


def handle_context_engine_stats(params: dict[str, Any]) -> dict[str, Any]:
    """Genera comparacion compact vs legacy con una tarea de ejemplo."""
    task = str(params.get("task", "")).strip() or "tarea de ejemplo"
    project_dir = params.get("project_dir") or None
    engine_name = params.get("engine_name") or None
    try:
        ctx = asyncio.run(
            prepare_context(
                task=task,
                project_dir=project_dir,
                engine_name=engine_name,
            )
        )
    except Exception as exc:  # noqa: BLE001
        return _err(f"stats fallo: {exc}")

    footprint = measure_prompt_footprint(ctx)
    section = ctx.to_prompt_section()
    return {
        "success": True,
        "engine": resolve_engine_name(engine_name),
        "section_chars": len(section),
        "section_tokens_approx": estimate_tokens_approx(section),
        **footprint,
    }


TOOLS: dict[str, Any] = {
    "context_engine_list": handle_context_engine_list,
    "context_engine_current": handle_context_engine_current,
    "context_engine_switch": handle_context_engine_switch,
    "context_engine_preview": handle_context_engine_preview,
    "context_engine_stats": handle_context_engine_stats,
}

TOOL_SCHEMAS: dict[str, Any] = {
    "context_engine_list": {"type": "object", "properties": {}},
    "context_engine_current": {"type": "object", "properties": {}},
    "context_engine_switch": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "description": "Slug del engine a activar (default|brain_aware|delta_aware|summarizing|domain_uns|composite).",
            },
            "project_dir": {
                "type": "string",
                "description": "Directorio donde escribir .antigravity/config.json.",
            },
        },
        "required": ["name"],
    },
    "context_engine_preview": {
        "type": "object",
        "properties": {
            "task": {"type": "string"},
            "engine_name": {"type": "string"},
            "project_dir": {"type": "string"},
            "current_file": {"type": "string"},
            "open_files": {"type": "array", "items": {"type": "string"}},
            "include_prompt": {"type": "boolean"},
        },
        "required": ["task"],
    },
    "context_engine_stats": {
        "type": "object",
        "properties": {
            "task": {"type": "string"},
            "project_dir": {"type": "string"},
            "engine_name": {"type": "string"},
        },
    },
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "context_engine_list": "Lista engines disponibles con metadata (descripcion, requires, version).",
    "context_engine_current": "Engine activo + fuentes de seleccion (env, config, fallback).",
    "context_engine_switch": "Cambia el engine escribiendo .antigravity/config.json del proyecto.",
    "context_engine_preview": (
        "Ejecuta el engine con una tarea de ejemplo y devuelve el contexto + "
        "seccion de prompt. Sin side effects persistentes."
    ),
    "context_engine_stats": (
        "Metricas: chars y tokens aproximados del contexto actual vs el modo legacy."
    ),
}


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {}) or {}

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
                    "name": "antigravity-context-engine",
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
        tool_input = params.get("arguments", {}) or {}
        if tool_name not in TOOLS:
            return err(-32601, f"Tool desconocida: {tool_name}")
        try:
            result = TOOLS[tool_name](tool_input)
        except Exception as exc:  # noqa: BLE001
            logger.exception("Tool %r lanzo excepcion", tool_name)
            result = {"success": False, "error": f"Error interno en {tool_name}: {exc}"}
        is_error = isinstance(result, dict) and not result.get("success")
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


def main() -> None:
    logger.info("Antigravity Context Engine Server v1.0.0 iniciando")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                print(json.dumps(response, ensure_ascii=False), flush=True)
        except json.JSONDecodeError as exc:
            print(
                json.dumps(
                    {
                        "jsonrpc": "2.0",
                        "id": None,
                        "error": {"code": -32700, "message": f"JSON invalido: {exc}"},
                    }
                ),
                flush=True,
            )


if __name__ == "__main__":
    main()
