"""Mixin: handlers de memoria de agentes y MetaPlanner."""

from __future__ import annotations

import asyncio
import logging
from functools import partial
from typing import Any

from aiohttp import web

log = logging.getLogger("antigravity-gateway")

# Cached memory server module — loaded once, reused across requests
_cached_mem_module: Any = None

# Concurrencia maxima de handlers mem0 simultaneos en el thread pool.
# Con mem0 + Ollama, cada request tarda 4-15s; sin limite, 20+ reqs concurrentes
# saturan el pool y acumulan tasks fantasma hasta colgar el event loop.
_MEM0_CONCURRENCY = 5

# Timeout por handler mem0 individual (segundos).
# Debe ser menor que el middleware_timeout global para que el TimeoutError
# se genere en el handler y devuelva 504 sin matar el request a nivel middleware.
_MEM0_HANDLER_TIMEOUT_S = 15.0


def _get_mem_module() -> Any:
    """Load and cache the memory-server module (singleton).

    Returns:
        The loaded memory-server module, or None if loading fails.
    """
    global _cached_mem_module
    if _cached_mem_module is not None:
        return _cached_mem_module

    import importlib.util
    from pathlib import Path

    _srv_path = Path(__file__).parent.parent / "memory-server.py"
    if not _srv_path.exists():
        log.error("memory-server.py no encontrado en %s", _srv_path)
        return None

    try:
        _spec = importlib.util.spec_from_file_location("_mem_srv_cached", _srv_path)
        _mod = importlib.util.module_from_spec(_spec)
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
        _cached_mem_module = _mod
        log.info("memory-server.py cargado y cacheado exitosamente")
        return _mod
    except Exception as e:
        log.error("Error cargando memory-server.py: %s", e)
        return None


class _MemoryMixin:
    """Handlers de memoria: recall, stats, conversations, store, planner."""

    async def _run_mem0_handler(self, handler: Any, payload: dict[str, Any]) -> Any:
        """Ejecuta handlers sync de mem0 con semaforo y timeout.

        Limita a ``_MEM0_CONCURRENCY`` handlers simultaneos para evitar saturar
        el thread pool cuando Ollama esta lento. Aborta con TimeoutError si el
        handler excede ``_MEM0_HANDLER_TIMEOUT_S``; el caller debe convertirlo
        en 504 para el cliente.
        """
        sem = getattr(self, "_mem0_semaphore", None)
        if sem is None:
            sem = asyncio.Semaphore(_MEM0_CONCURRENCY)
            self._mem0_semaphore = sem

        loop = asyncio.get_running_loop()
        async with sem:
            return await asyncio.wait_for(
                loop.run_in_executor(self._thread_pool, partial(handler, payload)),
                timeout=_MEM0_HANDLER_TIMEOUT_S,
            )

    def _prewarm_mem0_sync(self) -> None:
        """Carga el modulo de memoria e intenta inicializar su backend en background."""
        mem_module = _get_mem_module()
        if mem_module is None:
            return

        ensure_initialized = getattr(mem_module, "_ensure_initialized", None)
        if callable(ensure_initialized):
            ensure_initialized()

    async def prewarm_mem0_background(self) -> None:
        """Precalienta mem0 sin bloquear el event loop del gateway."""
        try:
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._thread_pool, self._prewarm_mem0_sync)
            log.info("mem0 precalentado en background")
        except Exception as e:
            log.warning("Error precalentando mem0 en background: %s", e)

    async def handle_agent_memory_recall(self, request: web.Request) -> web.Response:
        """GET /v1/memory/:agent/recall?q=...&limit=5 - Busca en la memoria de un agente."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        agent_name = request.match_info["agent"]
        query = request.query.get("q", "")
        limit = int(request.query.get("limit", "5"))
        memory_type = request.query.get("type")

        if not _validate_name(agent_name):
            return web.json_response(
                _make_response(error="Nombre de agente inválido", status=400),
                status=400,
            )
        if not query:
            return web.json_response(
                _make_response(error="Parámetro 'q' requerido", status=400),
                status=400,
            )

        try:
            from core.agent_memory import get_agent_memory

            memory = get_agent_memory(agent_name)
            results = memory.recall(query, limit=limit, memory_type=memory_type)
            return web.json_response(
                _make_response(
                    data={
                        "agent": agent_name,
                        "query": query,
                        "results": results,
                        "count": len(results),
                    }
                )
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_agent_memory_stats(self, request: web.Request) -> web.Response:
        """GET /v1/memory/:agent/stats - Estadísticas de la memoria de un agente."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        agent_name = request.match_info["agent"]

        if not _validate_name(agent_name):
            return web.json_response(
                _make_response(error="Nombre de agente inválido", status=400),
                status=400,
            )

        try:
            from core.agent_memory import get_agent_memory

            memory = get_agent_memory(agent_name)
            return web.json_response(_make_response(data=memory.get_stats()))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_agent_memory_conversations(self, request: web.Request) -> web.Response:
        """GET /v1/memory/:agent/conversations - Recupera conversaciones A2A de un agente."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        agent_name = request.match_info["agent"]
        with_agent = request.query.get("with")
        limit = int(request.query.get("limit", "10"))

        if not _validate_name(agent_name):
            return web.json_response(
                _make_response(error="Nombre de agente inválido", status=400),
                status=400,
            )

        try:
            from core.agent_memory import get_agent_memory

            memory = get_agent_memory(agent_name)
            conversations = memory.recall_conversations(with_agent=with_agent, limit=limit)
            return web.json_response(
                _make_response(
                    data={
                        "agent": agent_name,
                        "conversations": conversations,
                        "count": len(conversations),
                    }
                )
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_agent_memory_store(self, request: web.Request) -> web.Response:
        """POST /v1/memory/:agent/store - Almacena contexto en la memoria de un agente."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        agent_name = request.match_info["agent"]

        if not _validate_name(agent_name):
            return web.json_response(
                _make_response(error="Nombre de agente inválido", status=400),
                status=400,
            )

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400),
                status=400,
            )

        key = body.get("key", "")
        value = body.get("value", "")
        source_agent = body.get("source_agent")

        if not key or not value:
            return web.json_response(
                _make_response(error="Campos 'key' y 'value' requeridos", status=400),
                status=400,
            )

        try:
            from core.agent_memory import get_agent_memory

            memory = get_agent_memory(agent_name)
            memory_id = memory.store_context(key=key, value=value, source_agent=source_agent)
            return web.json_response(
                _make_response(
                    data={
                        "memory_id": memory_id,
                        "agent": agent_name,
                        "key": key,
                    }
                ),
                status=201,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # MetaPlanner Handlers (Sprint 2)
    # --------------------------------------------------------
    async def handle_planner_execute(self, request: web.Request) -> web.Response:
        """POST /v1/planner/execute - Descompone y ejecuta una tarea compleja."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400),
                status=400,
            )

        task = body.get("task", "")
        context = body.get("context")

        if not task:
            return web.json_response(
                _make_response(error="Campo 'task' requerido", status=400),
                status=400,
            )

        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            result = await daemon.plan_and_execute(task, context)
            return web.json_response(_make_response(data=result))
        except RuntimeError as e:
            return web.json_response(
                _make_response(error=str(e), status=503),
                status=503,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_planner_analyze(self, request: web.Request) -> web.Response:
        """POST /v1/planner/analyze - Analiza una tarea sin ejecutarla."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400),
                status=400,
            )

        task = body.get("task", "")
        if not task:
            return web.json_response(
                _make_response(error="Campo 'task' requerido", status=400),
                status=400,
            )

        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            analysis = await daemon.analyze_task(task)
            return web.json_response(_make_response(data=analysis))
        except RuntimeError as e:
            return web.json_response(
                _make_response(error=str(e), status=503),
                status=503,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_planner_create(self, request: web.Request) -> web.Response:
        """POST /v1/planner/plan - Crea un plan sin ejecutarlo."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400),
                status=400,
            )

        task = body.get("task", "")
        context = body.get("context")

        if not task:
            return web.json_response(
                _make_response(error="Campo 'task' requerido", status=400),
                status=400,
            )

        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            plan = await daemon.create_plan(task, context)
            return web.json_response(_make_response(data=plan), status=201)
        except RuntimeError as e:
            return web.json_response(
                _make_response(error=str(e), status=503),
                status=503,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_planner_list(self, request: web.Request) -> web.Response:
        """GET /v1/planner/plans - Lista planes recientes."""
        from .._gateway_main import _make_response, _sanitize_error

        limit = int(request.query.get("limit", "20"))
        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            plans = await daemon.list_plans(limit=limit)
            return web.json_response(_make_response(data={"plans": plans, "count": len(plans)}))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_planner_get(self, request: web.Request) -> web.Response:
        """GET /v1/planner/plans/:plan_id - Obtiene un plan por ID."""
        from .._gateway_main import _make_response, _sanitize_error

        plan_id = request.match_info["plan_id"]
        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            plan = await daemon.get_plan(plan_id)
            if plan is None:
                return web.json_response(
                    _make_response(error=f"Plan '{plan_id}' no encontrado", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data=plan))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_mem0_store(self, request: web.Request) -> web.Response:
        """POST /v1/mem0/store - Guarda en memoria semántica (mem0) desde cualquier app."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400), status=400
            )

        content = body.get("content", "")
        user_id = body.get("user_id", "antigravity")
        metadata = body.get("metadata", {})

        if not content:
            return web.json_response(
                _make_response(error="Campo 'content' requerido", status=400), status=400
            )

        try:
            _mod = _get_mem_module()
            if _mod is None:
                return web.json_response(
                    _make_response(error="memory-server no disponible", status=503), status=503
                )
            result = await self._run_mem0_handler(
                _mod.handle_memory_store,
                {"content": content, "user_id": user_id, "metadata": metadata},
            )
            return web.json_response(_make_response(data=result))
        except TimeoutError:
            log.warning("mem0 store timeout (>%ss) — devolviendo 504", _MEM0_HANDLER_TIMEOUT_S)
            return web.json_response(
                _make_response(error="mem0 store timeout", status=504), status=504
            )
        except Exception as e:
            log.error("mem0 store error: %s", e)
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500), status=500
            )

    async def handle_mem0_stats(self, request: web.Request) -> web.Response:
        """GET /v1/mem0/stats - Estadísticas del sistema de memoria semántica (mem0)."""
        from .._gateway_main import _make_response, _sanitize_error

        user_id = request.rel_url.query.get("user_id", "antigravity")

        try:
            _mod = _get_mem_module()
            if _mod is None:
                return web.json_response(
                    _make_response(error="memory-server no disponible", status=503), status=503
                )
            result = await self._run_mem0_handler(_mod.handle_memory_stats, {"user_id": user_id})
            return web.json_response(_make_response(data=result))
        except TimeoutError:
            log.warning("mem0 stats timeout (>%ss) — devolviendo 504", _MEM0_HANDLER_TIMEOUT_S)
            return web.json_response(
                _make_response(error="mem0 stats timeout", status=504), status=504
            )
        except Exception as e:
            log.error("mem0 stats error: %s", e)
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500), status=500
            )

    async def handle_mem0_recall(self, request: web.Request) -> web.Response:
        """GET /v1/mem0/recall?q=...&limit=5 - Recupera memorias semánticas (mem0)."""
        from .._gateway_main import _make_response, _sanitize_error

        query = request.rel_url.query.get("q", "")
        user_id = request.rel_url.query.get("user_id", "antigravity")
        limit = int(request.rel_url.query.get("limit", "10"))

        if not query:
            return web.json_response(
                _make_response(error="Parámetro 'q' requerido", status=400), status=400
            )

        try:
            _mod = _get_mem_module()
            if _mod is None:
                return web.json_response(
                    _make_response(error="memory-server no disponible", status=503), status=503
                )
            result = await self._run_mem0_handler(
                _mod.handle_memory_recall,
                {"query": query, "user_id": user_id, "limit": limit},
            )
            return web.json_response(_make_response(data=result))
        except TimeoutError:
            log.warning("mem0 recall timeout (>%ss) — devolviendo 504", _MEM0_HANDLER_TIMEOUT_S)
            return web.json_response(
                _make_response(error="mem0 recall timeout", status=504), status=504
            )
        except Exception as e:
            log.error("mem0 recall error: %s", e)
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500), status=500
            )

    async def handle_planner_stats(self, request: web.Request) -> web.Response:
        """GET /v1/planner/stats - Estadísticas del MetaPlanner."""
        from .._gateway_main import _make_response, _sanitize_error
        from ._mixin_advanced import _daemon_unavailable_response, _get_daemon_safe

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await asyncio.wait_for(
                asyncio.to_thread(daemon.get_planner_stats),
                timeout=4.0,
            )
            return web.json_response(_make_response(data=stats))
        except TimeoutError:
            return web.json_response(
                _make_response(
                    data={
                        "status": "not_ready",
                        "message": "MetaPlanner ocupado o inicializando",
                    }
                ),
                status=200,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )
