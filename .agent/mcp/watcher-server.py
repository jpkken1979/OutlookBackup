#!/usr/bin/env python3
"""Antigravity Watcher MCP Server.

Servidor MCP que lanza procesos en background y matchea patrones regex en su
output en tiempo real. Reemplaza el flujo `bash run_in_background + polling`
con notificaciones reactivas al gateway y, opcionalmente, al Brain Network.

Tools expuestas:
    - watch_spawn: lanzar un proceso con lista de patterns.
    - watch_status: estado + metadata de un watch.
    - watch_tail: ultimas N lineas de stdout/stderr (en memoria).
    - watch_matches: matches persistidos en SQLite.
    - watch_kill: terminar un proceso activo.
    - watch_list: listar watches activos + historico reciente.
    - watch_stats: metricas globales.
    - watch_cleanup: purgar watches expirados (TTL).
    - watch_status_engine: estado del engine (config + path store).

v1.0.0 - 2026-04-17
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

from core.process_watcher import (  # noqa: E402
    ProcessWatcher,
    WatcherConfig,
    WatcherError,
    default_state_path,
)

# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------

_watcher: ProcessWatcher | None = None


def _resolve_allowed_cwds() -> tuple[str, ...]:
    raw = os.environ.get("ANTIGRAVITY_WATCHER_CWDS", "").strip()
    if raw:
        return tuple(r for r in raw.split(os.pathsep) if r)
    root = os.environ.get("ANTIGRAVITY_ROOT", "").strip()
    return (root,) if root else ()


def _build_config() -> WatcherConfig:
    def _int_env(key: str, default: int) -> int:
        try:
            return int(os.environ.get(key, "") or default)
        except ValueError:
            return default

    def _bool_env(key: str, default: bool) -> bool:
        raw = os.environ.get(key, "").strip().lower()
        if not raw:
            return default
        return raw in {"1", "true", "yes", "on"}

    return WatcherConfig(
        max_watches=_int_env("ANTIGRAVITY_WATCHER_MAX", 16),
        max_tail_lines=_int_env("ANTIGRAVITY_WATCHER_TAIL", 500),
        ttl_seconds=_int_env("ANTIGRAVITY_WATCHER_TTL", 7 * 24 * 3600),
        allowed_cwds=_resolve_allowed_cwds(),
        enable_gateway_notify=_bool_env("ANTIGRAVITY_WATCHER_GATEWAY", True),
        gateway_url=os.environ.get(
            "ANTIGRAVITY_GATEWAY_URL", "http://127.0.0.1:4747"
        ).strip()
        or "http://127.0.0.1:4747",
        enable_brain_ingest=_bool_env("ANTIGRAVITY_WATCHER_BRAIN", False),
    )


def _ensure_watcher() -> ProcessWatcher:
    global _watcher
    if _watcher is not None:
        return _watcher
    state_path = default_state_path()
    config = _build_config()
    _watcher = ProcessWatcher(state_path, config=config)
    logger.info(
        "ProcessWatcher inicializado: state=%s allowed_cwds=%s max=%d gateway_notify=%s brain=%s",
        state_path,
        config.allowed_cwds or "(sin restriccion)",
        config.max_watches,
        config.enable_gateway_notify,
        config.enable_brain_ingest,
    )
    return _watcher


# ---------------------------------------------------------------------------
# Handlers
# ---------------------------------------------------------------------------


def _err(msg: str, code: str = "error") -> dict[str, Any]:
    return {"success": False, "error": msg, "error_code": code}


def handle_watch_spawn(params: dict[str, Any]) -> dict[str, Any]:
    cmd = str(params.get("cmd", "")).strip()
    if not cmd:
        return _err("cmd es requerido")
    patterns = params.get("patterns", [])
    if not isinstance(patterns, list):
        return _err("patterns debe ser lista de {regex,label,importance}")
    cwd = params.get("cwd")
    env = params.get("env")
    label = params.get("label")
    if env is not None and not isinstance(env, dict):
        return _err("env debe ser dict de strings")
    try:
        watcher = _ensure_watcher()
        watch_id = watcher.spawn(
            cmd,
            patterns=patterns,
            cwd=str(cwd) if cwd else None,
            env={str(k): str(v) for k, v in (env or {}).items()} or None,
            label=str(label) if label else None,
        )
    except WatcherError as exc:
        return _err(str(exc))
    return {"success": True, "watch_id": watch_id}


def handle_watch_status(params: dict[str, Any]) -> dict[str, Any]:
    watch_id = str(params.get("watch_id", "")).strip()
    if not watch_id:
        return _err("watch_id es requerido")
    try:
        data = _ensure_watcher().status(watch_id)
    except WatcherError as exc:
        return _err(str(exc), code="unknown_watch")
    return {"success": True, **data}


def handle_watch_tail(params: dict[str, Any]) -> dict[str, Any]:
    watch_id = str(params.get("watch_id", "")).strip()
    if not watch_id:
        return _err("watch_id es requerido")
    try:
        lines = int(params.get("lines", 50))
    except (TypeError, ValueError):
        lines = 50
    stream = str(params.get("stream", "both")).strip() or "both"
    if stream not in {"stdout", "stderr", "both"}:
        return _err("stream debe ser stdout|stderr|both")
    try:
        data = _ensure_watcher().tail(watch_id, lines=lines, stream=stream)
    except WatcherError as exc:
        return _err(str(exc), code="unknown_watch")
    return {"success": True, **data}


def handle_watch_matches(params: dict[str, Any]) -> dict[str, Any]:
    watch_id = str(params.get("watch_id", "")).strip()
    if not watch_id:
        return _err("watch_id es requerido")
    try:
        limit = int(params.get("limit", 50))
    except (TypeError, ValueError):
        limit = 50
    try:
        matches = _ensure_watcher().matches(watch_id, limit=limit)
    except WatcherError as exc:
        return _err(str(exc), code="unknown_watch")
    return {"success": True, "watch_id": watch_id, "matches": matches}


def handle_watch_kill(params: dict[str, Any]) -> dict[str, Any]:
    watch_id = str(params.get("watch_id", "")).strip()
    if not watch_id:
        return _err("watch_id es requerido")
    try:
        ok = _ensure_watcher().kill(watch_id)
    except WatcherError as exc:
        return _err(str(exc), code="unknown_watch")
    return {"success": True, "watch_id": watch_id, "killed": ok}


def handle_watch_list(params: dict[str, Any]) -> dict[str, Any]:
    include_finished = bool(params.get("include_finished", True))
    watches = _ensure_watcher().list_watches(include_finished=include_finished)
    return {"success": True, "watches": watches}


def handle_watch_stats(params: dict[str, Any]) -> dict[str, Any]:
    return {"success": True, **_ensure_watcher().stats()}


def handle_watch_cleanup(params: dict[str, Any]) -> dict[str, Any]:
    removed = _ensure_watcher().cleanup_expired()
    return {"success": True, "removed": removed}


def handle_watch_status_engine(params: dict[str, Any]) -> dict[str, Any]:
    w = _ensure_watcher()
    cfg = w.config
    return {
        "success": True,
        "state_path": str(w.state_path),
        "config": {
            "max_watches": cfg.max_watches,
            "max_tail_lines": cfg.max_tail_lines,
            "ttl_seconds": cfg.ttl_seconds,
            "allowed_cwds": list(cfg.allowed_cwds),
            "enable_gateway_notify": cfg.enable_gateway_notify,
            "gateway_url": cfg.gateway_url,
            "enable_brain_ingest": cfg.enable_brain_ingest,
        },
    }


# ---------------------------------------------------------------------------
# Tool registry
# ---------------------------------------------------------------------------

TOOLS: dict[str, Any] = {
    "watch_spawn": handle_watch_spawn,
    "watch_status": handle_watch_status,
    "watch_tail": handle_watch_tail,
    "watch_matches": handle_watch_matches,
    "watch_kill": handle_watch_kill,
    "watch_list": handle_watch_list,
    "watch_stats": handle_watch_stats,
    "watch_cleanup": handle_watch_cleanup,
    "watch_status_engine": handle_watch_status_engine,
}

_PATTERN_SCHEMA = {
    "type": "object",
    "properties": {
        "regex": {"type": "string", "description": "Expresion regular (re.search)"},
        "label": {"type": "string", "description": "Nombre legible del match"},
        "importance": {
            "type": "string",
            "enum": ["low", "high", "critical"],
            "description": "low=solo log; high=notifica gateway; critical=notifica + opcional brain",
        },
        "auto_brain_ingest": {
            "type": "boolean",
            "description": "Si es critical y true, ingesta el match al Brain como pattern.",
        },
    },
    "required": ["regex", "label"],
}

TOOL_SCHEMAS: dict[str, Any] = {
    "watch_spawn": {
        "type": "object",
        "properties": {
            "cmd": {
                "type": "string",
                "description": "Comando a ejecutar (parseado con shlex.split, shell=False).",
            },
            "patterns": {
                "type": "array",
                "items": _PATTERN_SCHEMA,
                "description": "Lista de patrones regex a matchear contra stdout+stderr.",
            },
            "cwd": {
                "type": "string",
                "description": "Directorio de trabajo del proceso. Validado si hay allowed_cwds.",
            },
            "env": {
                "type": "object",
                "description": "Variables de entorno extra (heredan de os.environ).",
            },
            "label": {
                "type": "string",
                "description": "Alias humano del watch (aparece en notificaciones).",
            },
        },
        "required": ["cmd"],
    },
    "watch_status": {
        "type": "object",
        "properties": {"watch_id": {"type": "string"}},
        "required": ["watch_id"],
    },
    "watch_tail": {
        "type": "object",
        "properties": {
            "watch_id": {"type": "string"},
            "lines": {"type": "integer", "description": "Lineas a devolver (max 500)."},
            "stream": {"type": "string", "enum": ["stdout", "stderr", "both"]},
        },
        "required": ["watch_id"],
    },
    "watch_matches": {
        "type": "object",
        "properties": {
            "watch_id": {"type": "string"},
            "limit": {"type": "integer"},
        },
        "required": ["watch_id"],
    },
    "watch_kill": {
        "type": "object",
        "properties": {"watch_id": {"type": "string"}},
        "required": ["watch_id"],
    },
    "watch_list": {
        "type": "object",
        "properties": {
            "include_finished": {
                "type": "boolean",
                "description": "Si true, incluye watches terminados (hasta 50 recientes).",
            }
        },
    },
    "watch_stats": {"type": "object", "properties": {}},
    "watch_cleanup": {
        "type": "object",
        "properties": {},
        "description": "Purga watches finalizados mas viejos que TTL.",
    },
    "watch_status_engine": {
        "type": "object",
        "properties": {},
        "description": "Config activa y path del store SQLite.",
    },
}

TOOL_DESCRIPTIONS: dict[str, str] = {
    "watch_spawn": (
        "Lanza un proceso en background y empieza a matchear patrones regex "
        "sobre su stdout/stderr. Matches high/critical notifican al gateway "
        "local y, si auto_brain_ingest=true, ingesta al Brain Network. "
        "Reemplaza el flujo 'run_in_background + polling' con notificaciones "
        "reactivas. Devuelve watch_id para consultar status/tail/matches."
    ),
    "watch_status": (
        "Estado actual de un watch: state (running|exited|killed|error), "
        "pid, exit_code, match_count, patrones configurados, timestamps."
    ),
    "watch_tail": (
        "Ultimas N lineas de stdout/stderr del watch (en memoria, no "
        "persisten despues del fin del proceso). Util para inspeccionar "
        "output reciente cuando un match dispara una alerta."
    ),
    "watch_matches": (
        "Matches persistidos en SQLite para un watch, ordenados de mas "
        "reciente a mas viejo."
    ),
    "watch_kill": (
        "Termina un proceso activo (SIGTERM + SIGKILL como fallback). "
        "Devuelve killed=true si el proceso estaba corriendo."
    ),
    "watch_list": (
        "Lista watches activos en memoria + hasta 50 watches finalizados "
        "recientes del store."
    ),
    "watch_stats": "Metricas globales: total watches, by_state, total_matches, active_in_memory.",
    "watch_cleanup": "Elimina watches finalizados con ended_at < now - ttl_seconds y sus matches.",
    "watch_status_engine": "Estado del engine: path del store, config activa (env vars aplicadas).",
}


# ---------------------------------------------------------------------------
# JSON-RPC 2.0 dispatcher
# ---------------------------------------------------------------------------


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
                    "name": "antigravity-watcher",
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


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    logger.info("Antigravity Watcher Server v1.0.0 iniciando")
    try:
        _ensure_watcher()
    except Exception as exc:  # noqa: BLE001
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
