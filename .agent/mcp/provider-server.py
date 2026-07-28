#!/usr/bin/env python3
"""
Antigravity Provider Switch MCP Server
======================================
Servidor MCP que expone la conmutacion del backend de Claude Code entre providers
(Claude / MiniMax / GLM / NVIDIA / Ollama / LM Studio).

Permite que, desde cualquier chat, le pidas "cambia a MiniMax" y se ejecute como
tool MCP — reusando exactamente la misma logica que el CLI y el endpoint del gateway
(core.provider_switch), que a su vez replica provider_manager.rs de Nexus.

Tools:
- provider_status:       provider activo + lista de disponibles
- provider_switch:       activar un provider (limpia el anterior, sin contaminacion)
- provider_disable:      volver a Claude nativo
- provider_list_models:  modelos validos de un provider

IMPORTANTE: el switch escribe ~/.claude/settings.json y afecta sesiones NUEVAS de
Claude Code (las env se cargan al arrancar). La sesion actual no cambia hasta
reiniciarla; Nexus lo refleja al instante via polling.

v1.0.0 — 2026-05-25
"""

from __future__ import annotations

import json
import logging
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

from core import provider_switch  # noqa: E402

# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_provider_status(_params: dict[str, Any]) -> dict[str, Any]:
    """Devuelve el provider activo y la lista de disponibles."""
    return provider_switch.get_overview()


def handle_provider_switch(params: dict[str, Any]) -> dict[str, Any]:
    """Activa un provider, limpiando el anterior primero."""
    provider = (params.get("provider") or params.get("provider_id") or "").strip()
    model = params.get("model")
    scope = params.get("scope") or "global"
    if not provider:
        return {"error": "Falta el parametro 'provider'", "success": False}
    try:
        return provider_switch.switch_provider(provider, model, scope=scope)
    except provider_switch.ProviderError as exc:
        return {"error": str(exc), "success": False}


def handle_provider_disable(params: dict[str, Any]) -> dict[str, Any]:
    """Vuelve a Claude nativo (o quita el override del proyecto si scope=project)."""
    return provider_switch.disable_provider(scope=params.get("scope") or "global")


def handle_provider_list_models(params: dict[str, Any]) -> dict[str, Any]:
    """Lista los modelos validos de un provider."""
    provider = (params.get("provider") or "").strip()
    return {"provider": provider.lower(), "models": provider_switch.list_models(provider)}


def handle_provider_hotswap(params: dict[str, Any]) -> dict[str, Any]:
    """Cambia el backend del proxy en caliente (sin reiniciar Claude Code)."""
    provider = (params.get("provider") or params.get("provider_id") or "").strip()
    model = params.get("model")
    if not provider:
        return {"error": "Falta el parametro 'provider'", "success": False}
    try:
        return provider_switch.set_hotswap(provider, model)
    except provider_switch.ProviderError as exc:
        return {"error": str(exc), "success": False}


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, Any] = {
    "provider_status": handle_provider_status,
    "provider_switch": handle_provider_switch,
    "provider_disable": handle_provider_disable,
    "provider_list_models": handle_provider_list_models,
    "provider_hotswap": handle_provider_hotswap,
}

_PROVIDER_ENUM = ["claude", "minimax", "zai", "nvidia", "ollama", "lmstudio"]

TOOL_SCHEMAS: dict[str, Any] = {
    "provider_status": {
        "type": "object",
        "properties": {},
        "additionalProperties": False,
    },
    "provider_switch": {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": _PROVIDER_ENUM,
                "description": "Provider a activar. 'claude' equivale a disable.",
            },
            "model": {
                "type": "string",
                "description": "Modelo opcional. Si se omite, usa el default del provider.",
            },
            "scope": {
                "type": "string",
                "enum": ["global", "project"],
                "description": "global (~/.claude, default) o project (override local).",
            },
        },
        "required": ["provider"],
        "additionalProperties": False,
    },
    "provider_hotswap": {
        "type": "object",
        "properties": {
            "provider": {
                "type": "string",
                "enum": _PROVIDER_ENUM,
                "description": "Backend a activar EN CALIENTE (sin reiniciar Claude Code).",
            },
            "model": {
                "type": "string",
                "description": "Modelo opcional. Si se omite, usa el default del provider.",
            },
        },
        "required": ["provider"],
        "additionalProperties": False,
    },
    "provider_disable": {
        "type": "object",
        "properties": {
            "scope": {
                "type": "string",
                "enum": ["global", "project"],
                "description": "global (default) o project (quita solo el override local).",
            },
        },
        "additionalProperties": False,
    },
    "provider_list_models": {
        "type": "object",
        "properties": {
            "provider": {"type": "string", "enum": _PROVIDER_ENUM},
        },
        "required": ["provider"],
        "additionalProperties": False,
    },
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "provider_status": (
        "Devuelve el provider IA activo de Claude Code y la lista de providers "
        "disponibles con su estado de API key."
    ),
    "provider_switch": (
        "Conmuta el backend de Claude Code a otro provider (minimax, zai, nvidia, "
        "ollama, lmstudio) o vuelve a claude. Limpia el provider anterior "
        "automaticamente. Afecta sesiones NUEVAS de Claude Code."
    ),
    "provider_hotswap": (
        "Cambia el backend IA EN CALIENTE via el proxy del gateway, sin reiniciar "
        "Claude Code. Requiere ANTHROPIC_BASE_URL apuntando a /claudeproxy. El cambio "
        "aplica en el proximo prompt, en la misma conversacion."
    ),
    "provider_disable": "Vuelve a Claude nativo restaurando el backup.",
    "provider_list_models": "Lista los modelos validos de un provider.",
}


# ---------------------------------------------------------------------------
# JSON-RPC dispatch
# ---------------------------------------------------------------------------


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    """Despacha una request JSON-RPC 2.0."""
    method = request.get("method", "")
    req_id = request.get("id")
    params = request.get("params", {})

    def ok(result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def err(code: int, msg: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": msg}}

    if method == "initialize":
        return ok(
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "antigravity-provider", "version": "1.0.0"},
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
        except Exception as exc:  # noqa: BLE001 — boundary del handler MCP
            logger.exception("Tool '%s' lanzo excepcion", tool_name)
            result = {"error": f"Error interno en {tool_name}: {exc}", "success": False}
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
    # Los pipes stdio en Windows heredan la codepage del locale (cp932 en JP),
    # pero el protocolo MCP habla UTF-8: sin esto, el JSON entrante con no-ASCII
    # llega con surrogates sueltos y la respuesta puede fallar al escribirse.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    logger.info("Antigravity Provider Switch Server v1.0.0 iniciando")
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
