"""Mixin: handlers de memoria de agentes y MetaPlanner."""

from __future__ import annotations

import asyncio
import logging
import subprocess
import time
from functools import partial
from pathlib import Path
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

# Tiempo maximo para esperar un cupo mem0 antes de fallar rapido. Un worker que
# supera su timeout conserva el cupo hasta terminar realmente.
_MEM0_SLOT_TIMEOUT_S = 1.0

# Los stats de mem0 pueden tardar 10-50s en frio porque cargan ChromaDB y
# SentenceTransformer. La UI solo necesita una senal de vida rapida, asi que
# cacheamos el ultimo resultado real y respondemos "warming" mientras el
# refresh pesado corre en background.
_MEM0_STATS_CACHE_TTL_S = 300.0


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


async def _request_payload(request: web.Request) -> dict[str, Any]:
    """Merge query params and optional JSON body for compatibility endpoints."""
    payload: dict[str, Any] = dict(getattr(getattr(request, "rel_url", None), "query", {}) or {})
    if not getattr(request, "can_read_body", False):
        return payload
    try:
        body = await request.json()
    except Exception:
        body = {}
    if isinstance(body, dict):
        payload.update(body)
    return payload


def _coerce_limit(value: Any, default: int = 10) -> int:
    try:
        return max(1, min(int(value), 50))
    except (TypeError, ValueError):
        return default


def _count_jsonl_lines(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        return sum(
            1
            for line in path.read_text(encoding="utf-8", errors="ignore").splitlines()
            if line.strip()
        )
    except OSError:
        return 0


def _count_markdown_files(path: Path) -> int:
    if not path.exists():
        return 0
    return sum(1 for item in path.glob("*.md") if item.is_file())


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


def _build_memory_layers(
    *,
    memory_dir: Path,
    markdown_count: int,
    brain_dir: Path,
    brain_index: Path,
    index_lines: int,
    index_updated_at: float | None,
    brain_counts: dict[str, int],
    brain_total: int,
    mem0_state: str,
    mem0_stats: dict[str, Any],
    pending_file: Path,
    pending_events: int,
    observations_db: Path,
) -> list[dict[str, Any]]:
    """Construye la descripción de las capas de memoria para el diagnóstico.

    Args:
        memory_dir: Directorio de memorias markdown.
        markdown_count: Cantidad de archivos markdown encontrados.
        brain_dir: Directorio raíz del Brain Network.
        brain_index: Path al index.md del Brain.
        index_lines: Cantidad de líneas del index del Brain.
        index_updated_at: Timestamp de última modificación del index, o None.
        brain_counts: Conteo de nodos por categoría del Brain.
        brain_total: Total de nodos del Brain.
        mem0_state: Estado calculado de la capa mem0 ("ok"/"warming"/"degraded").
        mem0_stats: Estadísticas crudas de mem0.
        pending_file: Path al archivo de eventos pendientes de hooks.
        pending_events: Cantidad de eventos pendientes en la cola de hooks.
        observations_db: Path a la base de datos de observaciones.

    Returns:
        Lista de diccionarios, uno por capa de memoria.
    """
    return [
        {
            "id": "markdown",
            "name": "Markdown memory",
            "state": "ok" if memory_dir.exists() else "missing",
            "source_of_truth": True,
            "count": markdown_count,
            "path": str(memory_dir),
            "message": "Decisiones y sesiones versionadas",
        },
        {
            "id": "brain",
            "name": "Brain Network",
            "state": "ok" if brain_index.exists() and index_lines >= 50 else "degraded",
            "source_of_truth": True,
            "count": brain_total,
            "path": str(brain_dir),
            "message": f"index={index_lines} líneas",
            "details": {
                **brain_counts,
                "index_lines": index_lines,
                "index_updated_at": index_updated_at,
            },
        },
        {
            "id": "mem0",
            "name": "mem0 semantic cache",
            "state": mem0_state,
            "source_of_truth": False,
            "count": mem0_stats.get("total_memories") or mem0_stats.get("total") or 0,
            "path": mem0_stats.get("memory_dir") or mem0_stats.get("storage_path") or "",
            "message": mem0_stats.get("backend") or mem0_stats.get("status") or "mem0",
            "details": mem0_stats,
        },
        {
            "id": "hooks",
            "name": "Memory hooks queue",
            "state": "ok" if pending_events == 0 else "degraded",
            "source_of_truth": False,
            "count": pending_events,
            "path": str(pending_file),
            "message": "Sin backlog" if pending_events == 0 else "Eventos pendientes por reenviar",
        },
        {
            "id": "observations",
            "name": "Observations DB",
            "state": "ok" if observations_db.exists() else "missing",
            "source_of_truth": False,
            "count": observations_db.stat().st_size if observations_db.exists() else 0,
            "path": str(observations_db),
            "message": "DB local de observaciones" if observations_db.exists() else "No encontrada",
        },
    ]


def _collect_brain_index_info(
    brain_index: Path, issues: list[dict[str, Any]]
) -> tuple[int, float | None]:
    """Inspecciona el index del Brain y registra issues de salud.

    Args:
        brain_index: Path al archivo index.md del Brain Network.
        issues: Lista mutable de issues a la que se anexan los problemas detectados.

    Returns:
        Tupla (index_lines, index_updated_at) con la cantidad de líneas del
        index y el timestamp de última modificación (o None si no existe).
    """
    index_lines = 0
    index_updated_at: float | None = None
    if brain_index.exists():
        try:
            index_lines = len(brain_index.read_text(encoding="utf-8", errors="ignore").splitlines())
            index_updated_at = brain_index.stat().st_mtime
        except OSError:
            index_lines = 0
    else:
        issues.append(
            {
                "severity": "error",
                "code": "brain_index_missing",
                "message": ".agent/brain/index.md no existe",
            }
        )

    if brain_index.exists() and index_lines < 50:
        issues.append(
            {
                "severity": "warning",
                "code": "brain_index_small",
                "message": "Brain index parece incompleto; reconstruir index",
            }
        )
    return index_lines, index_updated_at


def _collect_queue_markdown_issues(
    pending_events: int, markdown_count: int, issues: list[dict[str, Any]]
) -> None:
    """Registra issues de la cola de hooks y de las memorias markdown.

    Args:
        pending_events: Cantidad de eventos pendientes en la cola de hooks.
        markdown_count: Cantidad de archivos markdown en .claude/memory.
        issues: Lista mutable de issues a la que se anexan los problemas detectados.
    """
    if pending_events > 0:
        issues.append(
            {
                "severity": "warning",
                "code": "memory_queue_pending",
                "message": f"{pending_events} evento(s) pendientes en hooks",
            }
        )

    if markdown_count == 0:
        issues.append(
            {
                "severity": "warning",
                "code": "markdown_memory_empty",
                "message": "No se encontraron memorias markdown en .claude/memory",
            }
        )


def _classify_memory_status(issues: list[dict[str, Any]], layers: list[dict[str, Any]]) -> str:
    """Clasifica el estado global del diagnóstico de memoria.

    Args:
        issues: Lista de issues detectados con su severidad.
        layers: Lista de capas de memoria con su estado individual.

    Returns:
        "error" si hay algún issue de severidad error, "degraded" si hay
        issues o capas degradadas/calentando, "ok" en caso contrario.
    """
    if any(issue["severity"] == "error" for issue in issues):
        return "error"
    if issues or any(layer["state"] in {"degraded", "warming"} for layer in layers):
        return "degraded"
    return "ok"


class _MemoryMixin:
    """Handlers de memoria: recall, stats, conversations, store, planner."""

    def _get_mem0_stats_cache(
        self,
        user_id: str,
        *,
        allow_stale: bool = False,
    ) -> dict[str, Any] | None:
        cache = getattr(self, "_mem0_stats_cache", {})
        entry = cache.get(user_id) if isinstance(cache, dict) else None
        if not entry:
            return None

        timestamp, payload = entry
        age = time.monotonic() - timestamp
        if not allow_stale and age > _MEM0_STATS_CACHE_TTL_S:
            return None

        result = dict(payload)
        result["cached"] = True
        result["cache_age_seconds"] = round(age, 3)
        if age > _MEM0_STATS_CACHE_TTL_S:
            result["stale"] = True
        return result

    def _set_mem0_stats_cache(self, user_id: str, payload: dict[str, Any]) -> None:
        if not isinstance(payload, dict):
            return
        cache = getattr(self, "_mem0_stats_cache", None)
        if not isinstance(cache, dict):
            cache = {}
            self._mem0_stats_cache = cache
        cache[user_id] = (time.monotonic(), dict(payload))

    def _mem0_warming_stats(self, mem_module: Any, user_id: str) -> dict[str, Any]:
        total = 0
        user_total = 0
        history_counts = getattr(mem_module, "_history_counts", None)
        if callable(history_counts):
            total, user_total = history_counts(user_id)

        return {
            "success": True,
            "total": user_total,
            "total_memories": total,
            "mem0_available": False,
            "backend": "warming",
            "status": "mem0 inicializando en segundo plano",
            "warming": True,
            "memory_dir": str(getattr(mem_module, "MEMORY_DIR", "")),
            "storage_path": str(getattr(mem_module, "MEMORY_DIR", "")),
            "chroma_path": str(getattr(mem_module, "CHROMA_PATH", "")),
            "history_db": str(getattr(mem_module, "HISTORY_DB_PATH", "")),
            "ollama_status": "warming",
        }

    def _schedule_mem0_stats_refresh(self, handler: Any, user_id: str) -> None:
        tasks = getattr(self, "_mem0_stats_refresh_tasks", None)
        if not isinstance(tasks, dict):
            tasks = {}
            self._mem0_stats_refresh_tasks = tasks

        task = tasks.get(user_id)
        if task is not None and not task.done():
            return

        tasks[user_id] = asyncio.create_task(self._refresh_mem0_stats_background(handler, user_id))

    async def _refresh_mem0_stats_background(self, handler: Any, user_id: str) -> None:
        try:
            loop = asyncio.get_running_loop()
            result = await loop.run_in_executor(
                self._thread_pool,
                partial(handler, {"user_id": user_id}),
            )
            if isinstance(result, dict) and result.get("success"):
                self._set_mem0_stats_cache(user_id, result)
                log.info("mem0 stats cache actualizado para user_id=%s", user_id)
            else:
                log.warning("mem0 stats refresh no exitoso: %s", result)
        except Exception as e:
            log.warning("mem0 stats refresh en background fallo: %s", e)

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

        try:
            await asyncio.wait_for(sem.acquire(), timeout=_MEM0_SLOT_TIMEOUT_S)
        except TimeoutError:
            raise TimeoutError("mem0 handler capacity exhausted") from None

        loop = asyncio.get_running_loop()
        release_slot = True
        try:
            future = loop.run_in_executor(self._thread_pool, partial(handler, payload))
            try:
                return await asyncio.wait_for(
                    asyncio.shield(future),
                    timeout=_MEM0_HANDLER_TIMEOUT_S,
                )
            except TimeoutError:
                # wait_for cannot stop a running thread. Retain the slot until
                # the worker really exits so phantom tasks cannot saturate the
                # shared gateway pool.
                future.add_done_callback(lambda _future: sem.release())
                release_slot = False
                raise
        finally:
            if release_slot:
                sem.release()

    def _prewarm_mem0_sync(self) -> None:
        """Carga el modulo de memoria e intenta inicializar su backend en background."""
        mem_module = _get_mem_module()
        if mem_module is None:
            return

        stats_handler = getattr(mem_module, "handle_memory_stats", None)
        if callable(stats_handler):
            result = stats_handler({"user_id": "antigravity"})
            if isinstance(result, dict) and result.get("success"):
                self._set_mem0_stats_cache("antigravity", result)
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

    def _record_typed_event(
        self,
        *,
        event_type: str,
        summary: str,
        metadata: dict[str, Any] | None = None,
        severity: str = "info",
        source: str = "gateway.memory",
        user_id: str = "antigravity",
    ) -> None:
        """Persist a typed memory event without affecting API flow on failures."""
        try:
            from core.memory_events import record_event

            record_event(
                event_type=event_type,
                summary=summary,
                metadata=metadata,
                severity=severity,
                source=source,
                user_id=user_id,
            )
        except Exception as exc:  # noqa: BLE001
            log.debug("typed memory event skipped: %s", exc)

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

        # Validar with_agent tambien (puede contener payload malicioso)
        if with_agent is not None and not _validate_name(with_agent):
            return web.json_response(
                _make_response(error="Parametro 'with' invalido", status=400),
                status=400,
            )

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
            self._record_typed_event(
                event_type="planner.executed",
                summary="Planner execution completed",
                metadata={"task": str(task)[:180], "has_context": bool(context)},
                source="gateway.planner.execute",
            )
            return web.json_response(_make_response(data=result))
        except RuntimeError as e:
            self._record_typed_event(
                event_type="planner.failed",
                summary="Planner execution unavailable",
                metadata={"task": str(task)[:180], "error": str(e)},
                severity="warning",
                source="gateway.planner.execute",
            )
            return web.json_response(
                _make_response(error=str(e), status=503),
                status=503,
            )
        except Exception as e:
            self._record_typed_event(
                event_type="planner.failed",
                summary="Planner execution failed",
                metadata={"task": str(task)[:180], "error": str(e)},
                severity="error",
                source="gateway.planner.execute",
            )
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
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        plan_id = request.match_info["plan_id"]
        if not _validate_name(plan_id):
            return web.json_response(
                _make_response(error="ID de plan invalido", status=400),
                status=400,
            )
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
            self._record_typed_event(
                event_type="memory.stored",
                summary=f"Stored semantic memory for user {user_id}",
                metadata={"content_preview": str(content)[:120], "metadata": metadata},
                source="gateway.mem0.store",
                user_id=str(user_id),
            )
            return web.json_response(_make_response(data=result))
        except TimeoutError:
            log.warning("mem0 store timeout (>%ss) — devolviendo 504", _MEM0_HANDLER_TIMEOUT_S)
            self._record_typed_event(
                event_type="error.detected",
                summary="mem0 store timeout",
                metadata={"endpoint": "/v1/mem0/store", "user_id": user_id},
                severity="warning",
                source="gateway.mem0.store",
                user_id=str(user_id),
            )
            return web.json_response(
                _make_response(error="mem0 store timeout", status=504), status=504
            )
        except Exception as e:
            log.error("mem0 store error: %s", e)
            self._record_typed_event(
                event_type="error.detected",
                summary="mem0 store error",
                metadata={"endpoint": "/v1/mem0/store", "user_id": user_id, "error": str(e)},
                severity="error",
                source="gateway.mem0.store",
                user_id=str(user_id),
            )
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
            cached = self._get_mem0_stats_cache(user_id)
            if cached is not None:
                return web.json_response(_make_response(data=cached))

            self._schedule_mem0_stats_refresh(_mod.handle_memory_stats, user_id)
            stale = self._get_mem0_stats_cache(user_id, allow_stale=True)
            if stale is not None:
                return web.json_response(_make_response(data=stale))

            return web.json_response(_make_response(data=self._mem0_warming_stats(_mod, user_id)))
        except Exception as e:
            log.error("mem0 stats error: %s", e)
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500), status=500
            )

    async def handle_mem0_clear(self, request: web.Request) -> web.Response:
        """POST /v1/mem0/clear - Elimina toda la memoria semantica de un usuario."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400), status=400
            )
        user_id = str(body.get("user_id") or "").strip()
        if not user_id:
            return web.json_response(
                _make_response(error="Campo 'user_id' requerido", status=400), status=400
            )

        try:
            _mod = _get_mem_module()
            if _mod is None:
                return web.json_response(
                    _make_response(error="memory-server no disponible", status=503), status=503
                )
            result = await self._run_mem0_handler(
                _mod.handle_memory_clear_user,
                {"user_id": user_id},
            )
            cache = getattr(self, "_mem0_stats_cache", None)
            if isinstance(cache, dict):
                cache.pop(user_id, None)
            self._record_typed_event(
                event_type="memory.cleared",
                summary=f"Cleared semantic memory for user {user_id}",
                metadata={
                    "semantic_deleted": result.get("semantic_deleted", 0),
                    "history_deleted": result.get("history_deleted", 0),
                },
                severity="warning",
                source="gateway.mem0.clear",
                user_id=user_id,
            )
            return web.json_response(_make_response(data=result))
        except TimeoutError:
            return web.json_response(
                _make_response(error="mem0 clear timeout", status=504), status=504
            )
        except Exception as e:
            log.error("mem0 clear error: %s", e)
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500), status=500
            )

    async def handle_mem0_recall(self, request: web.Request) -> web.Response:
        """GET/POST /v1/mem0/recall?q=...&limit=5 - Recupera memorias semánticas."""
        from .._gateway_main import _make_response, _sanitize_error

        payload = await _request_payload(request)
        query = str(payload.get("q") or payload.get("query") or "")
        user_id = str(payload.get("user_id") or "antigravity")
        limit = _coerce_limit(payload.get("limit"), 10)

        if not query:
            return web.json_response(
                _make_response(error="Parámetro 'q' o 'query' requerido", status=400),
                status=400,
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
            self._record_typed_event(
                event_type="memory.recalled",
                summary=f"Recalled semantic memory for user {user_id}",
                metadata={"query": query[:180], "limit": limit},
                source="gateway.mem0.recall",
                user_id=str(user_id),
            )
            return web.json_response(_make_response(data=result))
        except TimeoutError:
            log.warning("mem0 recall timeout (>%ss) — devolviendo 504", _MEM0_HANDLER_TIMEOUT_S)
            self._record_typed_event(
                event_type="error.detected",
                summary="mem0 recall timeout",
                metadata={"endpoint": "/v1/mem0/recall", "user_id": user_id, "query": query[:120]},
                severity="warning",
                source="gateway.mem0.recall",
                user_id=str(user_id),
            )
            return web.json_response(
                _make_response(error="mem0 recall timeout", status=504), status=504
            )
        except Exception as e:
            log.error("mem0 recall error: %s", e)
            self._record_typed_event(
                event_type="error.detected",
                summary="mem0 recall error",
                metadata={"endpoint": "/v1/mem0/recall", "user_id": user_id, "error": str(e)},
                severity="error",
                source="gateway.mem0.recall",
                user_id=str(user_id),
            )
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500), status=500
            )

    async def handle_memory_recall(self, request: web.Request) -> web.Response:
        """Unified recall alias for /v1/memory/recall."""
        return await self.handle_mem0_recall(request)

    async def handle_memory_store(self, request: web.Request) -> web.Response:
        """Unified store alias for /v1/memory/store."""
        return await self.handle_mem0_store(request)

    async def handle_memory_stats(self, request: web.Request) -> web.Response:
        """Unified stats alias for /v1/memory/stats."""
        return await self.handle_mem0_stats(request)

    async def handle_memory_events_list(self, request: web.Request) -> web.Response:
        """GET /v1/memory/events?limit=50&type=error.detected."""
        from .._gateway_main import _make_response, _sanitize_error

        payload = await _request_payload(request)
        limit = _coerce_limit(payload.get("limit"), 50)
        event_type = payload.get("type")

        try:
            from core.memory_events import list_events

            events = list_events(limit=limit, event_type=str(event_type) if event_type else None)
            return web.json_response(_make_response(data={"events": events, "count": len(events)}))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_memory_events_record(self, request: web.Request) -> web.Response:
        """POST /v1/memory/events - registra eventos tipados manualmente."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400),
                status=400,
            )

        if not isinstance(body, dict):
            return web.json_response(
                _make_response(error="Body debe ser objeto JSON", status=400),
                status=400,
            )

        event_type = str(body.get("type") or "").strip()
        summary = str(body.get("summary") or "").strip()
        user_id = str(body.get("user_id") or "antigravity")
        metadata = body.get("metadata") if isinstance(body.get("metadata"), dict) else {}
        severity = str(body.get("severity") or "info")
        source = str(body.get("source") or "gateway.memory")

        if not event_type or not summary:
            return web.json_response(
                _make_response(error="Campos 'type' y 'summary' requeridos", status=400),
                status=400,
            )

        try:
            from core.memory_events import record_event

            event = record_event(
                event_type=event_type,
                summary=summary,
                metadata=metadata,
                source=source,
                severity=severity,
                user_id=user_id,
            )
            return web.json_response(_make_response(data={"event": event}), status=201)
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    def _collect_mem0_stats_for_diagnose(
        self, user_id: str, issues: list[dict[str, Any]]
    ) -> dict[str, Any]:
        """Obtiene las estadísticas de mem0 para el diagnóstico de memoria.

        Args:
            user_id: Identificador del usuario para las estadísticas de mem0.
            issues: Lista mutable de issues a la que se anexa el problema si
                el módulo de memoria no está disponible.

        Returns:
            Diccionario con las estadísticas de mem0 (o un stub degradado si
            el módulo no está disponible).
        """
        _mod = _get_mem_module()
        if _mod is None:
            issues.append(
                {
                    "severity": "error",
                    "code": "mem0_module_missing",
                    "message": "memory-server no disponible",
                }
            )
            return {"success": False, "backend": "unavailable"}

        cached = self._get_mem0_stats_cache(user_id)
        if cached is None:
            self._schedule_mem0_stats_refresh(_mod.handle_memory_stats, user_id)
            cached = self._get_mem0_stats_cache(user_id, allow_stale=True)
        return cached if cached is not None else self._mem0_warming_stats(_mod, user_id)

    async def handle_memory_diagnose(self, request: web.Request) -> web.Response:
        """GET /v1/memory/diagnose - estado unificado de las capas de memoria."""
        from .._gateway_main import _make_response, _sanitize_error

        payload = await _request_payload(request)
        user_id = str(payload.get("user_id") or "antigravity")
        root = _repo_root()
        memory_dir = root / ".claude" / "memory"
        brain_dir = root / ".agent" / "brain"
        brain_index = brain_dir / "index.md"
        hooks_dir = Path.home() / ".antigravity" / "memory" / "hooks"
        pending_file = hooks_dir / "pending-events.jsonl"
        observations_db = Path.home() / ".antigravity" / "observations.db"

        issues: list[dict[str, Any]] = []

        try:
            mem0_stats = self._collect_mem0_stats_for_diagnose(user_id, issues)

            index_lines, index_updated_at = _collect_brain_index_info(brain_index, issues)

            pending_events = _count_jsonl_lines(pending_file)
            markdown_count = _count_markdown_files(memory_dir)
            _collect_queue_markdown_issues(pending_events, markdown_count, issues)

            brain_counts = {
                "concepts": _count_markdown_files(brain_dir / "concepts"),
                "sessions": _count_markdown_files(brain_dir / "sessions"),
                "patterns": _count_markdown_files(brain_dir / "patterns"),
            }
            brain_total = sum(brain_counts.values())
            mem0_available = bool(mem0_stats.get("mem0_available") or mem0_stats.get("success"))
            mem0_state = "ok" if mem0_available and not mem0_stats.get("warming") else "warming"
            if not mem0_available:
                mem0_state = "degraded"

            layers = _build_memory_layers(
                memory_dir=memory_dir,
                markdown_count=markdown_count,
                brain_dir=brain_dir,
                brain_index=brain_index,
                index_lines=index_lines,
                index_updated_at=index_updated_at,
                brain_counts=brain_counts,
                brain_total=brain_total,
                mem0_state=mem0_state,
                mem0_stats=mem0_stats,
                pending_file=pending_file,
                pending_events=pending_events,
                observations_db=observations_db,
            )

            status = _classify_memory_status(issues, layers)

            # Auto-remediation if requested (non-fatal fallback on any error)
            remediation_result: dict[str, Any] = {"attempted": False, "success": False}
            if payload.get("auto_fix") == "true" or payload.get("auto_fix") is True:
                remediation_result["attempted"] = True
                try:
                    # Remediate brain_index_small: rebuild index
                    brain_index_issues = [i for i in issues if i.get("id") == "brain_index_small"]
                    if brain_index_issues:
                        # Run rebuild_brain_index.py --check --json in background
                        script = root / ".agent" / "scripts" / "rebuild_brain_index.py"
                        if script.is_file():
                            result = await asyncio.get_event_loop().run_in_executor(
                                None,
                                lambda: subprocess.run(
                                    [
                                        "python",
                                        str(script),
                                        "--check",
                                        "--quiet",
                                    ],
                                    timeout=30,
                                    capture_output=True,
                                ),
                            )
                            remediation_result["brain_rebuild"] = result.returncode == 0
                except Exception as e:
                    log.warning("auto-remediation error (non-fatal): %s", e)

            response_data = {
                "status": status,
                "user_id": user_id,
                "generated_at": time.time(),
                "layers": layers,
                "issues": issues,
                "summary": {
                    "markdown_memories": markdown_count,
                    "brain_nodes": brain_total,
                    "mem0_memories": mem0_stats.get("total_memories")
                    or mem0_stats.get("total")
                    or 0,
                    "pending_events": pending_events,
                },
            }
            if remediation_result["attempted"]:
                response_data["remediation"] = remediation_result

            return web.json_response(_make_response(data=response_data))
        except Exception as e:
            log.error("memory diagnose error: %s", e)
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
