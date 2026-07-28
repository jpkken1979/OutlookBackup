#!/usr/bin/env python3
"""MCP Tool wrapper for ShuWebhookPublisher.

Exposes webhook management tools via MCP:
- shu_webhook_publish: Broadcast improvements to subscribers
- shu_webhook_subscribe: Register a new webhook endpoint
- shu_webhook_unsubscribe: Unregister a webhook endpoint
- shu_webhook_list: List registered subscribers
- shu_webhook_health: Health status based on recent broadcasts

Nota (bugfix 2026-07-02): este server importaba ``Server/TextContent/Tool``
de ``core.mcp_native`` — API que nunca existio, por lo que moria al arrancar
("Server disconnected" en Claude Desktop). Reescrito al patron JSON-RPC
stdio crudo que usan los demas bridges (shu_slack_bridge, shu-webhook-server).
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Agregar .agent al path para importar ShuWebhookPublisher
_AGENT_DIR = Path(__file__).parent.parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

try:
    from core.shu_webhook_publisher import ShuWebhookPublisher

    _publisher = ShuWebhookPublisher()
    PUBLISHER_AVAILABLE = True
except ImportError as _e:
    PUBLISHER_AVAILABLE = False
    _publisher = None  # type: ignore[assignment]
    logger.error("No se pudo importar ShuWebhookPublisher: %s", _e)

_TOOLS: list[dict] = [
    {
        "name": "shu_webhook_publish",
        "description": (
            "Broadcast /shu improvement suggestions to registered webhooks. "
            "Each subscriber endpoint receives an HTTP POST with improvement data. "
            "Failures are logged but do not block the broadcast."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "suggestions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of improvement suggestion strings.",
                },
                "affected_templates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Names of affected templates.",
                },
            },
            "required": ["suggestions", "affected_templates"],
        },
    },
    {
        "name": "shu_webhook_subscribe",
        "description": "Register a new webhook endpoint for /shu improvements.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "endpoint_url": {
                    "type": "string",
                    "description": "HTTPS/HTTP endpoint URL to receive webhook notifications.",
                },
            },
            "required": ["endpoint_url"],
        },
    },
    {
        "name": "shu_webhook_unsubscribe",
        "description": "Unregister a webhook endpoint.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "endpoint_url": {
                    "type": "string",
                    "description": "Endpoint URL to remove.",
                },
            },
            "required": ["endpoint_url"],
        },
    },
    {
        "name": "shu_webhook_list",
        "description": "List all registered webhook subscribers.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "shu_webhook_health",
        "description": "Get webhook system health status based on recent broadcasts.",
        "inputSchema": {"type": "object", "properties": {}, "required": []},
    },
]


def _text_response(request_id: int | None, text: str, *, is_error: bool = False) -> dict:
    """Construye respuesta JSON-RPC 2.0 con contenido de texto.

    Args:
        request_id: ID de la request JSON-RPC.
        text: Texto de la respuesta.
        is_error: Si True, marca la respuesta como error.

    Returns:
        Diccionario JSON-RPC 2.0 listo para serializar.
    """
    result: dict = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _handle_publish(request_id: int | None, args: dict) -> dict:
    """Broadcast de mejoras a los subscribers registrados."""
    suggestions = args.get("suggestions", [])
    affected_templates = args.get("affected_templates", [])
    try:
        result = _publisher.publish_improvement(suggestions, affected_templates)
        output = (
            f"Webhook broadcast completed\n"
            f"  Total subscribers: {result['broadcast_count']}\n"
            f"  Successful: {result['successful']}\n"
            f"  Failed: {result['failed']}"
        )
        if result["errors"]:
            output += "\n\nErrors:\n"
            for err in result["errors"]:
                output += f"  - {err['endpoint']}: {err['error']}\n"
        return _text_response(request_id, output)
    except Exception as exc:
        logger.error("Publish failed: %s", exc)
        return _text_response(request_id, f"Error: {exc}", is_error=True)


def _handle_subscribe(request_id: int | None, args: dict) -> dict:
    """Registra un endpoint webhook."""
    endpoint_url = args.get("endpoint_url", "").strip()
    if not endpoint_url:
        return _text_response(request_id, "Error: endpoint_url es requerido", is_error=True)
    try:
        if _publisher.subscribe(endpoint_url):
            return _text_response(request_id, f"Subscribed: {endpoint_url}")
        return _text_response(request_id, f"Already subscribed: {endpoint_url}")
    except ValueError as exc:
        return _text_response(request_id, f"Invalid URL: {exc}", is_error=True)
    except Exception as exc:
        logger.error("Subscribe failed: %s", exc)
        return _text_response(request_id, f"Error: {exc}", is_error=True)


def _handle_unsubscribe(request_id: int | None, args: dict) -> dict:
    """Remueve un endpoint webhook."""
    endpoint_url = args.get("endpoint_url", "").strip()
    if not endpoint_url:
        return _text_response(request_id, "Error: endpoint_url es requerido", is_error=True)
    try:
        if _publisher.unsubscribe(endpoint_url):
            return _text_response(request_id, f"Unsubscribed: {endpoint_url}")
        return _text_response(request_id, f"Not found: {endpoint_url}")
    except Exception as exc:
        logger.error("Unsubscribe failed: %s", exc)
        return _text_response(request_id, f"Error: {exc}", is_error=True)


def _handle_list(request_id: int | None, _args: dict) -> dict:
    """Lista los subscribers registrados."""
    try:
        subscribers = _publisher.list_subscribers()
        if not subscribers:
            return _text_response(request_id, "No subscribers registered")
        output = "Registered subscribers:\n"
        for url in subscribers:
            output += f"  - {url}\n"
        return _text_response(request_id, output)
    except Exception as exc:
        logger.error("List failed: %s", exc)
        return _text_response(request_id, f"Error: {exc}", is_error=True)


def _handle_health(request_id: int | None, _args: dict) -> dict:
    """Estado de salud del sistema de webhooks."""
    try:
        status = _publisher.get_health_status()
        history = _publisher.get_broadcast_history(limit=5)
        status_emoji = {
            "healthy": "🟢",
            "degraded": "🟡",
            "critical": "🔴",
            "unknown": "⚪",
        }.get(status, "⚪")
        output = f"Webhook Health: {status_emoji} {status}\n\n"
        output += "Recent broadcasts (last 5):\n"
        for entry in history:
            ts = entry.get("timestamp", "N/A")
            success = entry.get("successful", 0)
            total = entry.get("broadcast_count", 0)
            output += f"  {ts}: {success}/{total} successful\n"
        return _text_response(request_id, output)
    except Exception as exc:
        logger.error("Health check failed: %s", exc)
        return _text_response(request_id, f"Error: {exc}", is_error=True)


_HANDLERS = {
    "shu_webhook_publish": _handle_publish,
    "shu_webhook_subscribe": _handle_subscribe,
    "shu_webhook_unsubscribe": _handle_unsubscribe,
    "shu_webhook_list": _handle_list,
    "shu_webhook_health": _handle_health,
}


def handle_request(request: dict) -> dict | None:
    """Dispatcher principal de requests JSON-RPC.

    Args:
        request: Diccionario con la request JSON-RPC 2.0.

    Returns:
        Respuesta JSON-RPC o None si es una notificacion.
    """
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    # Las notificaciones no reciben respuesta (JSON-RPC 2.0 spec)
    if method and method.startswith("notifications/"):
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "shu-webhook-dispatcher", "version": "1.1.0"},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _TOOLS}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})
        handler = _HANDLERS.get(name)
        if handler is None:
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": f"Unknown tool: {name}"},
            }
        if not PUBLISHER_AVAILABLE:
            return _text_response(
                request_id, "Error: ShuWebhookPublisher no disponible", is_error=True
            )
        return handler(request_id, args)

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
            # Tolerar BOM y lineas vacias (p.ej. pipes de PowerShell en tests)
            line = line.strip().lstrip("﻿")
            if not line:
                continue
            response = handle_request(json.loads(line))
            if response is not None:
                # ponytail: print es la escritura real del transporte stdio
                print(json.dumps(response), flush=True)
        except Exception:
            logger.exception("Error in shu_webhook_dispatcher main loop")
