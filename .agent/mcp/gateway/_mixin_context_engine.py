"""Mixin: endpoints HTTP del Pluggable Context Engine.

Expone las 5 operaciones del context engine como endpoints REST para que
Nexus y otros clientes HTTP las consuman sin necesidad de un cliente MCP
stdio (que ya cubre Claude Code via `antigravity-context-engine`).

Endpoints:
    GET  /v1/context-engine/list            -> engines disponibles + metadata
    GET  /v1/context-engine/current         -> activo + fuentes de seleccion
    POST /v1/context-engine/switch          -> cambia el activo (persiste)
    POST /v1/context-engine/preview         -> simula sin side effects
    POST /v1/context-engine/stats           -> metricas chars/tokens vs legacy

Los imports del paquete `core.context_engines` son lazy y toleran ausencia
del paquete (si el runtime fue inyectado sin engines, endpoints responden
503 en vez de 500). Esto permite al gateway seguir vivo con degradacion.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from aiohttp import web

log = logging.getLogger("antigravity-gateway")

_agent_core_added = False


def _ensure_core_path() -> None:
    """Inserta .agent en sys.path una sola vez para que los engines importen."""
    global _agent_core_added
    if _agent_core_added:
        return
    agent_dir = Path(__file__).resolve().parent.parent.parent
    if str(agent_dir) not in sys.path:
        sys.path.insert(0, str(agent_dir))
    _agent_core_added = True


def _err(msg: str, status: int = 500) -> web.Response:
    return web.json_response({"ok": False, "error": msg}, status=status)


class _ContextEngineMixin:
    """Handlers HTTP del Pluggable Context Engine."""

    async def handle_context_engine_list(
        self, request: web.Request
    ) -> web.Response:
        """GET /v1/context-engine/list."""
        _ensure_core_path()
        try:
            from core.context_engines import list_engines  # type: ignore[import-not-found]
        except Exception as exc:  # noqa: BLE001
            return _err(f"context_engines no disponible: {exc}", status=503)
        try:
            engines = list_engines()
        except Exception as exc:  # noqa: BLE001
            return _err(f"list_engines fallo: {exc}", status=500)
        return web.json_response(
            {
                "ok": True,
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
        )

    async def handle_context_engine_current(
        self, request: web.Request
    ) -> web.Response:
        """GET /v1/context-engine/current."""
        _ensure_core_path()
        try:
            from core.context_engines.registry import (  # type: ignore[import-not-found]
                config_snapshot,
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"registry no disponible: {exc}", status=503)
        try:
            snap = config_snapshot()
        except Exception as exc:  # noqa: BLE001
            return _err(f"snapshot fallo: {exc}", status=500)
        return web.json_response({"ok": True, **snap})

    async def handle_context_engine_switch(
        self, request: web.Request
    ) -> web.Response:
        """POST /v1/context-engine/switch.

        Body: {name, project_dir?}
        Escribe `.antigravity/config.json` del proyecto target.
        """
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            return _err(f"json invalido: {exc}", status=400)
        if not isinstance(body, dict):
            return _err("body debe ser objeto", status=400)

        name = str(body.get("name") or "").strip()
        if not name:
            return _err("name es requerido", status=400)

        _ensure_core_path()
        try:
            from core.context_engines.registry import (  # type: ignore[import-not-found]
                engine_names,
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"registry no disponible: {exc}", status=503)

        available = engine_names()
        if name not in available:
            return _err(
                f"engine desconocido: {name}; disponibles={available}",
                status=400,
            )

        import json as _json
        import os as _os

        project_dir = body.get("project_dir")
        target = (
            Path(project_dir)
            if project_dir
            else Path(_os.environ.get("ANTIGRAVITY_ROOT", "") or ".").resolve()
        )
        config_path = target / ".antigravity" / "config.json"
        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            data: dict[str, Any] = {}
            if config_path.is_file():
                data = _json.loads(config_path.read_text(encoding="utf-8"))
            data["context_engine"] = name
            config_path.write_text(
                _json.dumps(data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            return _err(f"no pude escribir {config_path}: {exc}", status=500)

        return web.json_response(
            {"ok": True, "name": name, "config_path": str(config_path)}
        )

    async def handle_context_engine_preview(
        self, request: web.Request
    ) -> web.Response:
        """POST /v1/context-engine/preview.

        Body: {task, engine_name?, project_dir?, current_file?, open_files?, include_prompt?}
        Ejecuta el engine y devuelve el contexto enriquecido sin persistir nada.
        """
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            return _err(f"json invalido: {exc}", status=400)
        if not isinstance(body, dict):
            return _err("body debe ser objeto", status=400)
        task = str(body.get("task") or "").strip()
        if not task:
            return _err("task es requerido", status=400)

        _ensure_core_path()
        try:
            from core.context_engines import resolve_engine_name  # type: ignore[import-not-found]
            from core.context_injection import (  # type: ignore[import-not-found]
                enhance_agent_prompt,
                prepare_context,
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"context engines no disponibles: {exc}", status=503)

        engine_name = body.get("engine_name") or None
        open_files = body.get("open_files") or []
        if not isinstance(open_files, list):
            return _err("open_files debe ser array", status=400)

        try:
            ctx = await prepare_context(
                task=task,
                project_dir=body.get("project_dir") or None,
                current_file=body.get("current_file") or None,
                open_files=[str(f) for f in open_files],
                engine_name=engine_name,
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"preview fallo: {exc}", status=500)

        result: dict[str, Any] = {
            "ok": True,
            "engine": resolve_engine_name(engine_name),
            "context": ctx.to_dict(),
            "section": ctx.to_prompt_section(),
        }
        if bool(body.get("include_prompt", False)):
            result["prompt"] = enhance_agent_prompt(
                "### TAREA ASIGNADA\n" + task, ctx
            )
        return web.json_response(result)

    async def handle_context_engine_stats(
        self, request: web.Request
    ) -> web.Response:
        """POST /v1/context-engine/stats.

        Body: {task?, project_dir?, engine_name?}
        Compara chars/tokens del contexto actual vs el modo legacy.
        """
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            return _err(f"json invalido: {exc}", status=400)
        if not isinstance(body, dict):
            body = {}

        task = str(body.get("task") or "tarea de ejemplo").strip()
        engine_name = body.get("engine_name") or None

        _ensure_core_path()
        try:
            from core.context_engines import resolve_engine_name  # type: ignore[import-not-found]
            from core.context_injection import (  # type: ignore[import-not-found]
                estimate_tokens_approx,
                measure_prompt_footprint,
                prepare_context,
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"context engines no disponibles: {exc}", status=503)

        try:
            ctx = await prepare_context(
                task=task,
                project_dir=body.get("project_dir") or None,
                engine_name=engine_name,
            )
        except Exception as exc:  # noqa: BLE001
            return _err(f"stats fallo: {exc}", status=500)

        try:
            footprint = measure_prompt_footprint(ctx)
        except Exception as exc:  # noqa: BLE001
            footprint = {"error": str(exc)}
        section = ctx.to_prompt_section()
        return web.json_response(
            {
                "ok": True,
                "engine": resolve_engine_name(engine_name),
                "section_chars": len(section),
                "section_tokens_approx": estimate_tokens_approx(section),
                **footprint,
            }
        )
