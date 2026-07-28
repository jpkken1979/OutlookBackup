#!/usr/bin/env python3
"""
Antigravity Shu Webhook MCP Server
====================================
Expone herramientas MCP para gestionar webhooks de notificaciones de /shu.

Tools:
- shu_webhook_publish: Broadcast de mejoras a todos los subscribers
- shu_webhook_subscribe: Agregar endpoint a la lista de subscribers
- shu_webhook_unsubscribe: Remover endpoint de la lista
- shu_webhook_list: Listar subscribers actuales
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


def _text_response(request_id: int, text: str, *, is_error: bool = False) -> dict:
    """Construye respuesta JSON-RPC con texto.

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


def _handle_publish(request_id: int, args: dict) -> dict:
    """Publica mejoras a todos los subscribers registrados.

    Args:
        request_id: ID de la request.
        args: Argumentos con 'suggestions' y 'affected_templates'.

    Returns:
        Respuesta JSON-RPC con el resultado del broadcast.
    """
    if not PUBLISHER_AVAILABLE:
        return _text_response(request_id, "Error: ShuWebhookPublisher no disponible", is_error=True)

    suggestions = args.get("suggestions", [])
    affected_templates = args.get("affected_templates", [])

    if not isinstance(suggestions, list):
        suggestions = [str(suggestions)]
    if not isinstance(affected_templates, list):
        affected_templates = [str(affected_templates)]

    try:
        result = _publisher.publish_improvement(suggestions, affected_templates)
        text = (
            f"Broadcast completado:\n"
            f"  - Endpoints notificados: {result['broadcast_count']}\n"
            f"  - Exitosos: {result['successful']}\n"
            f"  - Fallidos: {result['failed']}\n"
        )
        if result["errors"]:
            text += "\nErrores:\n" + "\n".join(f"  - {e}" for e in result["errors"])
        return _text_response(request_id, text)
    except Exception as exc:
        return _text_response(request_id, f"Error en broadcast: {exc}", is_error=True)


def _handle_subscribe(request_id: int, args: dict) -> dict:
    """Agrega un endpoint a la lista de subscribers.

    Args:
        request_id: ID de la request.
        args: Argumentos con 'endpoint_url'.

    Returns:
        Respuesta JSON-RPC con confirmacion.
    """
    if not PUBLISHER_AVAILABLE:
        return _text_response(request_id, "Error: ShuWebhookPublisher no disponible", is_error=True)

    endpoint_url = args.get("endpoint_url", "").strip()
    if not endpoint_url:
        return _text_response(request_id, "Error: endpoint_url es requerido", is_error=True)

    if not (endpoint_url.startswith("http://") or endpoint_url.startswith("https://")):
        return _text_response(
            request_id,
            "Error: endpoint_url debe comenzar con http:// o https://",
            is_error=True,
        )

    try:
        added = _publisher.subscribe(endpoint_url)
        if added:
            return _text_response(request_id, f"Subscriber agregado: {endpoint_url}")
        return _text_response(request_id, f"Subscriber ya registrado: {endpoint_url}")
    except Exception as exc:
        return _text_response(request_id, f"Error al suscribir: {exc}", is_error=True)


def _handle_unsubscribe(request_id: int, args: dict) -> dict:
    """Remueve un endpoint de la lista de subscribers.

    Args:
        request_id: ID de la request.
        args: Argumentos con 'endpoint_url'.

    Returns:
        Respuesta JSON-RPC con confirmacion.
    """
    if not PUBLISHER_AVAILABLE:
        return _text_response(request_id, "Error: ShuWebhookPublisher no disponible", is_error=True)

    endpoint_url = args.get("endpoint_url", "").strip()
    if not endpoint_url:
        return _text_response(request_id, "Error: endpoint_url es requerido", is_error=True)

    try:
        removed = _publisher.unsubscribe(endpoint_url)
        if removed:
            return _text_response(request_id, f"Subscriber removido: {endpoint_url}")
        return _text_response(request_id, f"Subscriber no encontrado: {endpoint_url}")
    except Exception as exc:
        return _text_response(request_id, f"Error al desuscribir: {exc}", is_error=True)


def _handle_list(request_id: int, _args: dict) -> dict:
    """Lista los subscribers actuales.

    Args:
        request_id: ID de la request.
        _args: Argumentos (no se usan).

    Returns:
        Respuesta JSON-RPC con la lista de subscribers.
    """
    if not PUBLISHER_AVAILABLE:
        return _text_response(request_id, "Error: ShuWebhookPublisher no disponible", is_error=True)

    try:
        subscribers = _publisher.list_subscribers()
        if not subscribers:
            return _text_response(request_id, "No hay subscribers registrados.")
        lines = [f"Subscribers registrados ({len(subscribers)}):"]
        for i, url in enumerate(subscribers, 1):
            lines.append(f"  {i}. {url}")
        return _text_response(request_id, "\n".join(lines))
    except Exception as exc:
        return _text_response(request_id, f"Error al listar subscribers: {exc}", is_error=True)


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
                "serverInfo": {"name": "antigravity-shu-webhook", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        tools = [
            {
                "name": "shu_webhook_publish",
                "description": "Publica mejoras de /shu a todos los endpoints suscritos via HTTP POST",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "suggestions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Lista de sugerencias de mejora generadas por /shu",
                        },
                        "affected_templates": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Templates o archivos afectados por las mejoras",
                        },
                    },
                },
            },
            {
                "name": "shu_webhook_subscribe",
                "description": "Registra un endpoint HTTP para recibir notificaciones de /shu",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "endpoint_url": {
                            "type": "string",
                            "description": "URL HTTP/HTTPS del endpoint receptor (ej: http://localhost:9000/hook)",
                        }
                    },
                    "required": ["endpoint_url"],
                },
            },
            {
                "name": "shu_webhook_unsubscribe",
                "description": "Remueve un endpoint de la lista de subscribers de /shu",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "endpoint_url": {
                            "type": "string",
                            "description": "URL del endpoint a desuscribir",
                        }
                    },
                    "required": ["endpoint_url"],
                },
            },
            {
                "name": "shu_webhook_list",
                "description": "Lista todos los endpoints suscritos a notificaciones de /shu",
                "inputSchema": {
                    "type": "object",
                    "properties": {},
                },
            },
        ]
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "shu_webhook_publish":
            return _handle_publish(request_id, args)
        elif name == "shu_webhook_subscribe":
            return _handle_subscribe(request_id, args)
        elif name == "shu_webhook_unsubscribe":
            return _handle_unsubscribe(request_id, args)
        elif name == "shu_webhook_list":
            return _handle_list(request_id, args)

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
            logger.exception("Error en main loop del shu-webhook-server")
