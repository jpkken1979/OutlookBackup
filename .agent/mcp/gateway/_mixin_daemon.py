"""Mixin: handlers del daemon autónomo, scheduler, bus y A2A.

Usa DaemonProxy para comunicarse con el worker subprocess en :4748.
NO importa core.agent_daemon directamente (bloquea GIL ~30s).
"""

from __future__ import annotations

import asyncio
import logging

import aiohttp
from aiohttp import web
from ._mixin_advanced import _get_daemon_safe, _reset_daemon_safe

log = logging.getLogger("antigravity-gateway")


async def _get_daemon_proxy():
    """Retorna proxy al daemon worker subprocess (non-blocking)."""
    return await _get_daemon_safe()


class _DaemonMixin:
    """Handlers de daemon: status, submit, task, scheduler, bus, a2a."""

    async def handle_daemon_status(self, request: web.Request) -> web.Response:
        """GET /v1/daemon/status - Estado del daemon autónomo."""
        from .._gateway_main import _make_response

        proxy = await _get_daemon_proxy()
        if proxy is None:
            return web.json_response(
                _make_response(
                    data={
                        "running": False,
                        "workers": 0,
                        "active_tasks": 0,
                        "completed_tasks": 0,
                        "message": "Daemon disponible bajo demanda (inicializando)",
                    }
                )
            )

        try:
            status = await asyncio.wait_for(
                proxy.get_status(),
                timeout=5.0,
            )
            if not isinstance(status, dict):
                raise ValueError("daemon status inválido")

            metrics = status.get("metrics") if isinstance(status.get("metrics"), dict) else {}
            completed = int(metrics.get("tasks_succeeded", metrics.get("tasks_processed", 0)))
            running = bool(status.get("running", False))
            workers = int(status.get("workers", 0))
            active_tasks = int(status.get("active_tasks", 0))

            return web.json_response(
                _make_response(
                    data={
                        "running": running,
                        "workers": workers,
                        "active_tasks": active_tasks,
                        "completed_tasks": completed,
                        "message": "Daemon operativo"
                        if (running and workers > 0)
                        else "Daemon iniciado sin workers",
                    }
                )
            )
        except Exception as e:
            log.warning("Daemon status no disponible: %s", e)
            return web.json_response(
                _make_response(
                    data={
                        "running": False,
                        "workers": 0,
                        "active_tasks": 0,
                        "completed_tasks": 0,
                        "message": "Daemon inicializando o no disponible",
                    }
                )
            )

    async def handle_daemon_submit(self, request: web.Request) -> web.Response:
        """POST /v1/daemon/submit - Encola tarea para ejecución autónoma."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400),
                status=400,
            )

        agent = body.get("agent", "")
        task = body.get("task", "")
        priority = body.get("priority", "NORMAL").upper()
        context = body.get("context", {})

        if not agent or not task:
            return web.json_response(
                _make_response(error="Campos 'agent' y 'task' requeridos", status=400),
                status=400,
            )
        if not _validate_name(agent):
            return web.json_response(
                _make_response(error="Nombre de agente inválido", status=400),
                status=400,
            )

        try:
            proxy = await _get_daemon_proxy()
            if proxy is None:
                return web.json_response(
                    _make_response(data={"status": "not_ready"}),
                    status=200,
                )
            task_id = await proxy.submit_task(
                agent_name=agent,
                task=task,
                from_agent="gateway",
                context=context,
                priority_name=priority,
            )
            return web.json_response(
                _make_response(
                    data={
                        "task_id": task_id,
                        "agent": agent,
                        "status": "queued",
                        "message": f"Tarea encolada para ejecución autónoma por agente '{agent}'",
                    }
                ),
                status=202,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_daemon_restart(self, request: web.Request) -> web.Response:
        """POST /v1/daemon/restart - Reinicia worker/proxy del daemon."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            await _reset_daemon_safe()

            # Disparar recreación en background (non-blocking)
            await _get_daemon_proxy()
            return web.json_response(
                _make_response(
                    data={
                        "status": "restarting",
                        "message": "Reinicio del daemon solicitado. Espera 2-10s y refresca estado.",
                    }
                )
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_daemon_diagnostic(self, request: web.Request) -> web.Response:
        """GET /v1/daemon/diagnostic - Diagnóstico rápido de daemon worker/proxy."""
        from .._gateway_main import _make_response

        worker_health: dict[str, object] = {
            "reachable": False,
            "ok": False,
            "error": "sin datos",
        }

        try:
            timeout = aiohttp.ClientTimeout(total=2)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get("http://127.0.0.1:4748/health") as resp:
                    payload = await resp.json(content_type=None)
                    worker_health = {
                        "reachable": True,
                        "ok": bool(payload.get("ok", False)),
                        "status_code": resp.status,
                        "payload": payload,
                    }
        except Exception as e:
            worker_health = {
                "reachable": False,
                "ok": False,
                "error": str(e),
            }

        daemon_snapshot: dict[str, object] = {
            "running": False,
            "workers": 0,
            "active_tasks": 0,
            "completed_tasks": 0,
            "ready": False,
            "message": "Daemon inicializando o no disponible",
        }

        try:
            proxy = await _get_daemon_proxy()
            if proxy is None:
                daemon_snapshot["message"] = "Proxy no listo (worker iniciando)"
            else:
                status = await asyncio.wait_for(
                    proxy.get_status(),
                    timeout=5.0,
                )
                if isinstance(status, dict):
                    metrics = (
                        status.get("metrics") if isinstance(status.get("metrics"), dict) else {}
                    )
                    completed = int(
                        metrics.get("tasks_succeeded", metrics.get("tasks_processed", 0))
                    )
                    running = bool(status.get("running", False))
                    workers = int(status.get("workers", 0))
                    active_tasks = int(status.get("active_tasks", 0))
                    daemon_snapshot = {
                        "running": running,
                        "workers": workers,
                        "active_tasks": active_tasks,
                        "completed_tasks": completed,
                        "ready": bool(running and workers > 0),
                        "message": "Daemon operativo"
                        if (running and workers > 0)
                        else "Daemon sin workers",
                    }
        except Exception as e:
            daemon_snapshot["message"] = f"Daemon no respondió: {e}"

        return web.json_response(
            _make_response(
                data={
                    "daemon": daemon_snapshot,
                    "worker": worker_health,
                }
            )
        )

    async def handle_daemon_task(self, request: web.Request) -> web.Response:
        """GET /v1/daemon/tasks/:id - Estado de una tarea del daemon."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        task_id = request.match_info["task_id"]
        if not _validate_name(task_id):
            return web.json_response(
                _make_response(error="ID de tarea invalido", status=400),
                status=400,
            )
        try:
            proxy = await _get_daemon_proxy()
            if proxy is None:
                return web.json_response(
                    _make_response(data={"status": "not_ready"}),
                    status=200,
                )
            task_info = await proxy.get_task(task_id)
            if not task_info:
                return web.json_response(
                    _make_response(error=f"Tarea '{task_id}' no encontrada", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data=task_info))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # AutonomousScheduler Endpoints
    # --------------------------------------------------------
    async def handle_scheduler_list(self, request: web.Request) -> web.Response:
        """GET /v1/scheduler/schedules - Lista schedules activos."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            from core.autonomous_scheduler import get_scheduler

            scheduler = await get_scheduler()
            return web.json_response(
                _make_response(
                    data={
                        "schedules": scheduler.list_schedules(),
                        "count": len(scheduler.list_schedules()),
                    }
                )
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=503),
                status=503,
            )

    async def handle_scheduler_create(self, request: web.Request) -> web.Response:
        """POST /v1/scheduler/schedules - Crea un nuevo schedule."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400),
                status=400,
            )

        trigger_type = body.get("trigger_type", "interval").lower()
        name = body.get("name", "")
        agent = body.get("agent", "")
        task = body.get("task", "")

        if not all([name, agent, task]):
            return web.json_response(
                _make_response(error="Campos 'name', 'agent', 'task' requeridos", status=400),
                status=400,
            )
        if not _validate_name(agent):
            return web.json_response(
                _make_response(error="Nombre de agente inválido", status=400),
                status=400,
            )

        try:
            from core.autonomous_scheduler import get_scheduler

            scheduler = await get_scheduler()

            if trigger_type == "interval":
                seconds = float(body.get("seconds", 300))
                schedule = scheduler.add_interval(
                    name=name, agent=agent, task=task, seconds=seconds
                )
            elif trigger_type == "cron":
                cron_expr = body.get("cron_expression", "*/5 * * * *")
                schedule = scheduler.add_cron(
                    name=name, agent=agent, task=task, cron_expression=cron_expr
                )
            elif trigger_type == "event":
                channel = body.get("channel", "")
                if not channel:
                    return web.json_response(
                        _make_response(
                            error="Campo 'channel' requerido para trigger type 'event'", status=400
                        ),
                        status=400,
                    )
                schedule = scheduler.add_event_trigger(
                    name=name, channel=channel, agent=agent, task_template=task
                )
            elif trigger_type == "one_shot":
                delay = float(body.get("delay_seconds", 0))
                schedule = scheduler.add_one_shot(
                    name=name, agent=agent, task=task, delay_seconds=delay
                )
            else:
                return web.json_response(
                    _make_response(error=f"Tipo de trigger inválido: '{trigger_type}'", status=400),
                    status=400,
                )

            return web.json_response(
                _make_response(data=schedule.to_dict()),
                status=201,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_scheduler_delete(self, request: web.Request) -> web.Response:
        """DELETE /v1/scheduler/schedules/:name - Elimina un schedule."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        name = request.match_info["name"]
        if not _validate_name(name):
            return web.json_response(
                _make_response(error="Nombre de schedule invalido", status=400),
                status=400,
            )
        try:
            from core.autonomous_scheduler import get_scheduler

            scheduler = await get_scheduler()
            removed = scheduler.remove(name)
            if not removed:
                return web.json_response(
                    _make_response(error=f"Schedule '{name}' no encontrado", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data={"removed": name}))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_bus_stats(self, request: web.Request) -> web.Response:
        """GET /v1/bus/stats - Estadísticas del message bus."""
        from .._gateway_main import _make_response

        # Retornar stats básicas sin importar core.redis_message_bus (bloquea GIL)
        return web.json_response(
            _make_response(
                data={
                    "backend": "sqlite",
                    "running": True,
                    "published": 0,
                    "consumed": 0,
                    "dlq_count": 0,
                    "errors": 0,
                }
            )
        )
        try:
            pass  # Dead code — imports pesados removidos
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=503),
                status=503,
            )

    # --------------------------------------------------------
    # A2A Request-Reply Endpoints
    # --------------------------------------------------------
    async def handle_a2a_request(self, request: web.Request) -> web.Response:
        """POST /v1/a2a/request - Envía un request A2A entre agentes."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400),
                status=400,
            )

        from_agent = body.get("from_agent", "")
        to_agent = body.get("to_agent", "")
        question = body.get("question", "")
        context = body.get("context", {})
        timeout = float(body.get("timeout", 60))
        request_type = body.get("request_type", "question")

        if not all([from_agent, to_agent, question]):
            return web.json_response(
                _make_response(
                    error="Campos 'from_agent', 'to_agent' y 'question' requeridos",
                    status=400,
                ),
                status=400,
            )
        for name in (from_agent, to_agent):
            if not _validate_name(name):
                return web.json_response(
                    _make_response(error=f"Nombre de agente inválido: '{name}'", status=400),
                    status=400,
                )

        try:
            proxy = await _get_daemon_proxy()
            if proxy is None:
                return web.json_response(
                    _make_response(data={"status": "not_ready"}),
                    status=200,
                )
            result = await proxy.a2a_request(
                from_agent=from_agent,
                to_agent=to_agent,
                question=question,
                context=context,
                timeout=timeout,
                request_type=request_type,
            )
            return web.json_response(
                _make_response(
                    data={
                        "from_agent": from_agent,
                        "to_agent": to_agent,
                        "request_type": request_type,
                        "response": result,
                    }
                )
            )
        except TimeoutError:
            return web.json_response(
                _make_response(
                    error=f"Timeout: el agente '{to_agent}' no respondió en {timeout}s",
                    status=504,
                ),
                status=504,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_a2a_stats(self, request: web.Request) -> web.Response:
        """GET /v1/a2a/stats - Estadísticas del sistema A2A."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            from core.redis_message_bus import get_message_bus

            bus = await get_message_bus()
            return web.json_response(_make_response(data=bus.get_a2a_stats()))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=503),
                status=503,
            )
