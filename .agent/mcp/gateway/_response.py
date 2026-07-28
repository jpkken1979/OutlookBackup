"""Envelope API profesional para respuestas del gateway.

Reemplaza y mejora el ``_make_response()`` / ``_sanitize_error()`` originales
de ``gateway_main.py`` con contratos tipados, codigos de error enum y tracing
por request_id.

Uso::

    from gateway._response import ok, err, make_response, sanitize_error

    # Success
    return web.json_response(ok({"health": True}))

    # Error con codigo
    return web.json_response(
        err("memory.query_missing", "Parametro q requerido"),
        status=400,
    )

    # Backward compatible
    return web.json_response(make_response(data={"status": "ok"}))
"""

from __future__ import annotations

import logging
import re
import uuid
from datetime import datetime, UTC
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Error codes
# ---------------------------------------------------------------------------


class ErrorCode(str, Enum):
    """Codigos de error canonicos del gateway.

    El valor string se usa directamente como ``error.code`` en el envelope.
    El formato es ``<dominio>.<motivo>`` para agrupar y filtrar facilmente.
    """

    MEMORY_QUERY_MISSING = "memory.query_missing"
    MEMORY_STORE_FAILED = "memory.store_failed"
    MEMORY_SCOPE_FORBIDDEN = "memory.scope_forbidden"
    PROVIDER_UNAVAILABLE = "provider.unavailable"
    PROVIDER_SWITCH_FAILED = "provider.switch_failed"
    GATEWAY_UNHEALTHY = "gateway.unhealthy"
    CONFIG_INVALID = "config.invalid"
    REMOTE_AUTH_MISSING = "remote.auth_missing"
    REMOTE_SERVER_OFFLINE = "remote.server_offline"
    REMOTE_PORT_BUSY = "remote.port_busy"
    REMOTE_HTTPS_REQUIRED = "remote.https_required"
    MCP_CLIENT_UNAUTHORIZED = "mcp.client_unauthorized"
    SKILL_NOT_PUBLISHED = "skill.not_published"
    AGENT_NOT_PUBLISHED = "agent.not_published"
    BRAIN_INDEX_STALE = "brain.index_stale"
    HOOKS_REGISTRATION_FAILED = "hooks.registration_failed"


# ---------------------------------------------------------------------------
# Helpers internos
# ---------------------------------------------------------------------------


def _utc_now_iso() -> str:
    """Timestamp ISO-8601 con timezone UTC.

    Returns:
        String como ``2026-05-27T12:00:00+00:00``.
    """
    return datetime.now(UTC).isoformat()


def new_request_id() -> str:
    """Genera UUID4 corto (sin guiones) para tracing de requests.

    Returns:
        32 caracteres hex, ej. ``a1b2c3d4e5f6...``.
    """
    return uuid.uuid4().hex


def sanitize_error(error: Exception) -> str:
    """Sanitiza mensaje de error para no exponer internals del filesystem.

    Aplica las mismas regex que ``_sanitize_error`` original:
    - Oculta paths Windows (``C:\\Users\\...``) y UNC (``\\\\server\\...``).
    - Oculta paths UNIX (``/home/...``).
    - Trunca a 200 caracteres.

    Args:
        error: Excepcion original.

    Returns:
        Mensaje sanitizado seguro para enviar al cliente.
    """
    msg = str(error)
    # Windows: drive letters (C:\Users\...) y UNC (\\server\share\...)
    msg = re.sub(r"[A-Za-z]:\\[^\"\s]+", "[path]", msg)
    msg = re.sub(r"\\\\[^\"\s]+", "[path]", msg)
    # UNIX: /home/... /usr/... etc
    msg = re.sub(r"(/[a-zA-Z0-9_./-]+)+", "[path]", msg)
    # Limitar longitud
    if len(msg) > 200:
        msg = msg[:200] + "..."
    return msg


# ---------------------------------------------------------------------------
# Envelope builders
# ---------------------------------------------------------------------------


def ok(
    data: Any = None,
    *,
    source: str = "gateway",
    request_id: str | None = None,
) -> dict[str, Any]:
    """Envelope de exito.

    Args:
        data: Payload de la respuesta. Si es ``None`` se envia ``null``.
        source: Identificador del componente que genera la respuesta,
            ej. ``"gateway"``, ``"brain"``, ``"memory"``.
        request_id: ID de tracing. Si es ``None`` se genera uno nuevo.

    Returns:
        Diccionario con formato::

            {
                "ok": true,
                "data": <any>,
                "error": null,
                "meta": {
                    "timestamp": "2026-05-27T12:00:00+00:00",
                    "source": "gateway",
                    "request_id": "a1b2c3..."
                }
            }
    """
    rid = request_id or new_request_id()
    envelope: dict[str, Any] = {
        "ok": True,
        "data": data,
        "error": None,
        "meta": {
            "timestamp": _utc_now_iso(),
            "source": source,
            "request_id": rid,
        },
    }
    return envelope


def err(
    code: str,
    message: str,
    hint: str = "",
    *,
    status: int = 400,
    source: str = "gateway",
    request_id: str | None = None,
) -> dict[str, Any]:
    """Envelope de error.

    Args:
        code: Codigo de error canonico, preferiblemente de :class:`ErrorCode`.
            Se acepta cualquier string para forward-compatibility.
        message: Descripcion humana del error.
        hint: Sugerencia para resolver el error (opcional).
        status: HTTP status code (solo informativo, no se incluye en el JSON).
        source: Componente que genera el error.
        request_id: ID de tracing. Si es ``None`` se genera uno nuevo.

    Returns:
        Diccionario con formato::

            {
                "ok": false,
                "data": null,
                "error": {
                    "code": "memory.query_missing",
                    "message": "Parametro q requerido",
                    "hint": "Envia ?query=... o body JSON con query"
                },
                "meta": {
                    "timestamp": "2026-05-27T12:00:00+00:00",
                    "source": "gateway",
                    "request_id": "a1b2c3..."
                }
            }
    """
    rid = request_id or new_request_id()
    # Asegurar serializacion limpia: Enum -> str, str -> str
    code_str = code.value if isinstance(code, ErrorCode) else str(code)
    error_obj: dict[str, str] = {
        "code": code_str,
        "message": message,
    }
    if hint:
        error_obj["hint"] = hint

    envelope: dict[str, Any] = {
        "ok": False,
        "data": None,
        "error": error_obj,
        "meta": {
            "timestamp": _utc_now_iso(),
            "source": source,
            "request_id": rid,
        },
    }

    logger.debug(
        "Error response: code=%s status=%s request_id=%s",
        code,
        status,
        rid,
    )
    return envelope


# ---------------------------------------------------------------------------
# Backward compatibility
# ---------------------------------------------------------------------------


def make_response(
    data: Any = None,
    error: str = "",
    status: int = 200,
    *,
    source: str = "gateway",
) -> dict[str, Any]:
    """Backward compatible con ``_make_response`` existente en gateway_main.py.

    Produce el mismo formato de salida que la funcion original para permitir
    migracion gradual. La firma es identica con un kwarg extra ``source``.

    Si ``error`` esta presente, delega a :func:`err`. Si no, delega a :func:`ok`.

    Args:
        data: Payload de exito (se ignora si hay error).
        error: Mensaje de error. Si no esta vacio, genera envelope de error.
        status: HTTP status code.
        source: Componente que genera la respuesta.

    Returns:
        Envelope compatible con el formato legacy de ``_make_response``.
    """
    if error:
        return err(
            code="gateway.error",
            message=error,
            status=status,
            source=source,
        )
    return ok(data=data, source=source)
