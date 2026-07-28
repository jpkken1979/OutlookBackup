#!/usr/bin/env python3
"""
Antigravity Delta Reader MCP Server
====================================
Servidor MCP que expone lectura delta-aware de archivos.

Cuando el mismo archivo se lee mas de una vez en la sesion, devuelve solo
el diff unificado respecto de la lectura anterior en vez del contenido
completo. Esto reduce drasticamente el consumo de tokens.

Tools:
- delta_read: leer archivo con deduplicacion por diff
- delta_stats: metricas de ahorro de una sesion
- delta_reset_session: limpiar snapshots de una sesion
- delta_cleanup: limpiar snapshots expiradas (TTL global)
- delta_status: estado del engine (config, ruta del store, schema)

Flujo tipico:
    1. Claude Code llama delta_read con session_id + path.
    2. Primera vez: devuelve contenido full y guarda snapshot.
    3. Siguientes veces: devuelve "unchanged" o diff unificado.
    4. En cualquier momento delta_stats reporta ahorro acumulado.

v1.0.0 — 2026-04-14
"""

from __future__ import annotations

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

from core.delta_reader import (  # noqa: E402
    DeltaReader,
    DeltaReaderConfig,
    default_state_path,
)

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_reader: DeltaReader | None = None
_DEFAULT_SESSION = "claude-code-default"


def _resolve_roots() -> tuple[str, ...]:
    """Lee ANTIGRAVITY_DELTA_ROOTS (paths separados por os.pathsep)."""
    raw = os.environ.get("ANTIGRAVITY_DELTA_ROOTS", "").strip()
    if not raw:
        # Default: raiz del proyecto si esta seteada.
        root = os.environ.get("ANTIGRAVITY_ROOT", "").strip()
        return (root,) if root else ()
    return tuple(r for r in raw.split(os.pathsep) if r)


def _build_config() -> DeltaReaderConfig:
    """Construye config desde env vars con defaults sanos.

    Falla rapido (RuntimeError) si no hay ningun root configurado: sin
    allowed_roots el reader leeria cualquier path del filesystem
    (incluyendo ~/.ssh, /etc, .env con tokens, etc.).
    """

    def _int_env(key: str, default: int) -> int:
        try:
            return int(os.environ.get(key, "") or default)
        except ValueError:
            return default

    def _float_env(key: str, default: float) -> float:
        try:
            return float(os.environ.get(key, "") or default)
        except ValueError:
            return default

    roots = _resolve_roots()
    if not roots:
        raise RuntimeError(
            "delta-reader-server: ni ANTIGRAVITY_DELTA_ROOTS ni ANTIGRAVITY_ROOT estan "
            "configuradas. Setear al menos una para evitar lecturas arbitrarias del "
            "filesystem.",
        )

    return DeltaReaderConfig(
        min_lines_for_delta=_int_env("ANTIGRAVITY_DELTA_MIN_LINES", 50),
        max_file_bytes=_int_env("ANTIGRAVITY_DELTA_MAX_BYTES", 2_000_000),
        delta_ratio_threshold=_float_env("ANTIGRAVITY_DELTA_RATIO", 0.4),
        session_ttl_seconds=_int_env(
            "ANTIGRAVITY_DELTA_TTL",
            7 * 24 * 3600,
        ),
        allowed_roots=roots,
    )


def _ensure_reader() -> DeltaReader:
    """Lazy-init del DeltaReader singleton."""
    global _reader
    if _reader is not None:
        return _reader
    state_path = default_state_path()
    config = _build_config()
    _reader = DeltaReader(state_path, config=config)
    logger.info(
        "DeltaReader inicializado: state=%s, roots=%s, min_lines=%d, max_bytes=%d, ratio=%.2f",
        state_path,
        config.allowed_roots or "(sin restriccion)",
        config.min_lines_for_delta,
        config.max_file_bytes,
        config.delta_ratio_threshold,
    )
    return _reader


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def handle_delta_read(params: dict[str, Any]) -> dict[str, Any]:
    """Leer archivo con deduplicacion por diff.

    Args:
        params: path (requerido), session_id (opcional), force_full (opcional).

    Returns:
        dict con mode, content/diff, stats, prior_turn.
    """
    path = params.get("path", "").strip()
    if not path:
        return {"error": "path es requerido", "success": False}

    session_id = params.get("session_id", "").strip() or _DEFAULT_SESSION
    force_full = bool(params.get("force_full", False))

    reader = _ensure_reader()
    result = reader.read(path, session_id=session_id, force_full=force_full)
    payload = result.to_dict()
    payload["success"] = result.mode != "error"
    return payload


def handle_delta_stats(params: dict[str, Any]) -> dict[str, Any]:
    """Metricas acumuladas de una sesion."""
    session_id = params.get("session_id", "").strip() or _DEFAULT_SESSION
    reader = _ensure_reader()
    return {"success": True, **reader.session_stats(session_id)}


def handle_delta_reset_session(params: dict[str, Any]) -> dict[str, Any]:
    """Elimina snapshots de una sesion."""
    session_id = params.get("session_id", "").strip()
    if not session_id:
        return {"error": "session_id es requerido", "success": False}
    reader = _ensure_reader()
    removed = reader.reset_session(session_id)
    return {"success": True, "session_id": session_id, "removed": removed}


def handle_delta_cleanup(params: dict[str, Any]) -> dict[str, Any]:
    """Borra snapshots mas viejas que el TTL configurado."""
    reader = _ensure_reader()
    removed = reader.cleanup_expired()
    return {
        "success": True,
        "removed": removed,
        "ttl_seconds": reader.config.session_ttl_seconds,
    }


def handle_delta_status(params: dict[str, Any]) -> dict[str, Any]:
    """Estado del engine: config activa, path del store."""
    reader = _ensure_reader()
    cfg = reader.config
    return {
        "success": True,
        "state_path": str(reader.state_path),
        "config": {
            "min_lines_for_delta": cfg.min_lines_for_delta,
            "max_file_bytes": cfg.max_file_bytes,
            "delta_ratio_threshold": cfg.delta_ratio_threshold,
            "session_ttl_seconds": cfg.session_ttl_seconds,
            "unified_diff_context": cfg.unified_diff_context,
            "allowed_roots": list(cfg.allowed_roots),
        },
    }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, Any] = {
    "delta_read": handle_delta_read,
    "delta_stats": handle_delta_stats,
    "delta_reset_session": handle_delta_reset_session,
    "delta_cleanup": handle_delta_cleanup,
    "delta_status": handle_delta_status,
}

TOOL_SCHEMAS: dict[str, Any] = {
    "delta_read": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": (
                    "Ruta al archivo (relativa o absoluta). Si hay "
                    "ANTIGRAVITY_DELTA_ROOTS, debe estar adentro."
                ),
            },
            "session_id": {
                "type": "string",
                "description": (
                    "ID logico de la sesion. Mismos (session, path) comparten "
                    "snapshot. Si se omite, usa 'claude-code-default'."
                ),
            },
            "force_full": {
                "type": "boolean",
                "description": (
                    "Si true, ignora snapshot previa y devuelve full. "
                    "Util cuando sospechas corrupcion de estado."
                ),
            },
        },
        "required": ["path"],
    },
    "delta_stats": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Sesion a consultar (default: sesion actual).",
            },
        },
    },
    "delta_reset_session": {
        "type": "object",
        "properties": {
            "session_id": {
                "type": "string",
                "description": "Sesion a limpiar (requerido).",
            },
        },
        "required": ["session_id"],
    },
    "delta_cleanup": {
        "type": "object",
        "properties": {},
        "description": "Limpia snapshots mas viejas que session_ttl_seconds.",
    },
    "delta_status": {
        "type": "object",
        "properties": {},
        "description": "Reporta config activa y path del store SQLite.",
    },
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "delta_read": (
        "Leer un archivo con deduplicacion por diff. "
        "Primera lectura devuelve contenido full; relecturas en la misma "
        "sesion devuelven 'unchanged' (si el archivo no cambio) o un diff "
        "unificado chico (si cambio poco). Reduce tokens en sesiones largas."
    ),
    "delta_stats": (
        "Metricas acumuladas de una sesion: reads totales, reads por modo "
        "(full/delta/unchanged), bytes ahorrados, savings_ratio."
    ),
    "delta_reset_session": (
        "Elimina todas las snapshots de una sesion. Util cuando cambias de "
        "contexto de trabajo y las lecturas viejas ya no son utiles."
    ),
    "delta_cleanup": (
        "Elimina snapshots mas viejas que el TTL configurado (default 7 dias). "
        "Seguro de correr periodicamente."
    ),
    "delta_status": (
        "Reporta configuracion activa del engine y path del SQLite. "
        "Util para verificar que el servidor esta corriendo."
    ),
}


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 dispatcher
# ---------------------------------------------------------------------------


def handle_request(request: dict[str, Any]) -> dict[str, Any] | None:
    """Despacha una request JSON-RPC 2.0."""
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
                    "name": "antigravity-delta-reader",
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
        except Exception as exc:
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

    logger.info("Antigravity Delta Reader Server v1.0.0 iniciando")
    try:
        _ensure_reader()
    except Exception as exc:
        logger.warning("Engine no inicializado en boot: %s", exc)

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
