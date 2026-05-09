"""Mixin: Process Watcher endpoints del gateway.

Cierra el loop de notificaciones del ProcessWatcher: recibe eventos del MCP
server `antigravity-watcher`, los normaliza, les aplica dedup + rate limit
por watch_id, y los emite al EventBus (que los distribuye a WebSocket, SSE
y listeners internos).

Endpoints expuestos:
    POST /v1/watcher/events          — ingesta de notificaciones del watcher
    GET  /v1/watcher/events/recent   — ultimos N eventos (polling-friendly)
    GET  /v1/watcher/status          — stats del subsistema watcher
    GET  /v1/watcher/stream          — SSE stream de eventos en vivo

Diseno "inteligente":
    - Normalizacion: estructura canonica de evento para downstream.
    - Dedup: (watch_id, pattern_label, line_number) en ventana de 500ms
      se colapsan en uno solo para evitar spam por flapping.
    - Rate limit por watch_id: max 60 eventos/min (criticals bypassan).
    - Fan-out via EventBus (canal `watcher.*`) sin acoplar al resto del gateway.
    - Historial disponible por HTTP (polling) para Nexus/Telegram sin WS.
    - SSE stream filtrable por importance para clientes browser/Nexus.
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
import time
from collections import deque
from datetime import datetime
from pathlib import Path
from typing import Any

from aiohttp import web

from ..gateway_events import get_event_bus
from ._watcher_event_store import WatcherEventStore, default_store_path

log = logging.getLogger("antigravity-gateway")

# ---------------------------------------------------------------------------
# ProcessWatcher singleton hosteado en el gateway
# ---------------------------------------------------------------------------

_watcher_instance: Any = None
_event_store: WatcherEventStore | None = None

# ---------------------------------------------------------------------------
# Contadores Prometheus — counters incrementales process-local
# ---------------------------------------------------------------------------

_METRICS: dict[str, int] = {
    "events_received_total": 0,
    "events_dropped_duplicate_total": 0,
    "events_dropped_rate_limit_total": 0,
    "events_emitted_total": 0,
    "events_persisted_total": 0,
}
_METRICS_BY_IMPORTANCE: dict[str, int] = {"low": 0, "high": 0, "critical": 0}


def _metrics_snapshot() -> dict[str, Any]:
    return {
        "counters": dict(_METRICS),
        "by_importance": dict(_METRICS_BY_IMPORTANCE),
    }


def _format_prometheus() -> str:
    """Expone los contadores en formato text/plain Prometheus."""
    lines: list[str] = [
        "# HELP watcher_events_received_total Total eventos recibidos por /v1/watcher/events",
        "# TYPE watcher_events_received_total counter",
        f"watcher_events_received_total {_METRICS['events_received_total']}",
        "# HELP watcher_events_dropped_total Eventos descartados por dedup o rate limit",
        "# TYPE watcher_events_dropped_total counter",
        f'watcher_events_dropped_total{{reason="duplicate"}} {_METRICS["events_dropped_duplicate_total"]}',
        f'watcher_events_dropped_total{{reason="rate_limit"}} {_METRICS["events_dropped_rate_limit_total"]}',
        "# HELP watcher_events_emitted_total Eventos publicados al EventBus",
        "# TYPE watcher_events_emitted_total counter",
        f"watcher_events_emitted_total {_METRICS['events_emitted_total']}",
        "# HELP watcher_events_persisted_total Eventos persistidos en SQLite",
        "# TYPE watcher_events_persisted_total counter",
        f"watcher_events_persisted_total {_METRICS['events_persisted_total']}",
        "# HELP watcher_events_by_importance_total Eventos recibidos agrupados por importance",
        "# TYPE watcher_events_by_importance_total counter",
    ]
    for importance, count in _METRICS_BY_IMPORTANCE.items():
        lines.append(
            f'watcher_events_by_importance_total{{importance="{importance}"}} {count}'
        )
    return "\n".join(lines) + "\n"


def _reset_metrics_for_tests() -> None:
    """Helper para tests — no uses en runtime."""
    for k in _METRICS:
        _METRICS[k] = 0
    for k in _METRICS_BY_IMPORTANCE:
        _METRICS_BY_IMPORTANCE[k] = 0


# ---------------------------------------------------------------------------
# Daemon cleanup: asyncio task que corre periodico mientras el gateway vive
# ---------------------------------------------------------------------------

_cleanup_task: asyncio.Task[None] | None = None
_CLEANUP_INTERVAL_SEC = 6 * 3600  # 6 horas


async def _periodic_cleanup_loop() -> None:
    """Loop interno: ejecuta cleanup_expired del store cada 6h.

    Usa try/except amplio para que un error en un ciclo NO tumbe el loop.
    """
    while True:
        try:
            await asyncio.sleep(_CLEANUP_INTERVAL_SEC)
            store = _get_event_store()
            removed = store.cleanup_expired()
            log.info("watcher history cleanup: removidos %d eventos expirados", removed)
            if _watcher_instance is not None:
                try:
                    removed_engine = _watcher_instance.cleanup_expired()
                    if removed_engine:
                        log.info(
                            "watcher engine cleanup: removidos %d watches expirados",
                            removed_engine,
                        )
                except Exception as exc:  # noqa: BLE001
                    log.debug("engine cleanup fallo: %s", exc)
        except asyncio.CancelledError:
            raise
        except Exception as exc:  # noqa: BLE001
            log.warning("periodic cleanup fallo (reintentando en 1h): %s", exc)
            await asyncio.sleep(3600)


def start_periodic_cleanup() -> asyncio.Task[None] | None:
    """Arranca el loop de cleanup si no esta corriendo. Idempotente."""
    global _cleanup_task
    if _cleanup_task is not None and not _cleanup_task.done():
        return _cleanup_task
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        log.debug("start_periodic_cleanup: no hay event loop activo")
        return None
    _cleanup_task = loop.create_task(_periodic_cleanup_loop())
    log.info("watcher periodic cleanup task arrancado (cada %ds)", _CLEANUP_INTERVAL_SEC)
    return _cleanup_task


def stop_periodic_cleanup() -> None:
    """Cancela el loop si esta corriendo."""
    global _cleanup_task
    if _cleanup_task is not None and not _cleanup_task.done():
        _cleanup_task.cancel()
    _cleanup_task = None


def _get_event_store() -> WatcherEventStore:
    """Lazy-init del store SQLite de historial."""
    global _event_store
    if _event_store is None:
        _event_store = WatcherEventStore(default_store_path())
        log.info("WatcherEventStore inicializado en %s", _event_store.db_path)
    return _event_store


def _get_watcher() -> Any:
    """Lazy-init del ProcessWatcher singleton hospedado en el gateway.

    El gateway es un proceso persistente, por lo tanto puede sostener el
    engine vivo indefinidamente — los watches spawneados por Nexus o por
    HTTP sobreviven mientras el gateway este arriba.
    """
    global _watcher_instance
    if _watcher_instance is not None:
        return _watcher_instance

    agent_dir = Path(__file__).resolve().parent.parent.parent
    if str(agent_dir) not in sys.path:
        sys.path.insert(0, str(agent_dir))
    from core.process_watcher import (  # type: ignore[import-not-found]
        ProcessWatcher,
        WatcherConfig,
        default_state_path,
    )

    _watcher_instance = ProcessWatcher(
        default_state_path(),
        config=WatcherConfig(
            # Matches se enrutan al handle_watcher_events del mismo gateway
            # via HTTP local (~1ms) — permite reusar dedup/rate-limit sin
            # duplicar logica y sin crear recursion (el handler no re-emite).
            enable_gateway_notify=True,
            enable_brain_ingest=False,
        ),
    )
    log.info("ProcessWatcher singleton inicializado en gateway")
    return _watcher_instance

# ---------------------------------------------------------------------------
# Estado local (por proceso gateway)
# ---------------------------------------------------------------------------

_DEDUP_WINDOW_SEC = 0.5
_RATE_LIMIT_PER_WATCH_PER_MIN = 60
_RATE_LIMIT_WINDOW_SEC = 60.0

# Recent keys para dedup: set de (watch_id, label, line_number, second_bucket)
_dedup_cache: set[tuple[str, str, int, int]] = set()
_dedup_cache_mtime: float = 0.0

# Ring buffer por watch_id para rate limit (sliding window)
_rate_buckets: dict[str, deque[float]] = {}
_RATE_GC_INTERVAL_SEC = 120.0
_rate_gc_last: float = 0.0


def _gc_dedup_cache(now: float) -> None:
    """Limpia el set cada ~5s para no crecer indefinidamente."""
    global _dedup_cache, _dedup_cache_mtime
    if now - _dedup_cache_mtime > 5.0:
        _dedup_cache = set()
        _dedup_cache_mtime = now


def _gc_rate_buckets(now: float) -> None:
    """Remueve buckets de watches inactivos (>2x window sin tocarse)."""
    global _rate_gc_last
    if now - _rate_gc_last < _RATE_GC_INTERVAL_SEC:
        return
    _rate_gc_last = now
    cutoff = now - (_RATE_LIMIT_WINDOW_SEC * 2)
    stale = [wid for wid, bucket in _rate_buckets.items() if not bucket or bucket[-1] < cutoff]
    for wid in stale:
        del _rate_buckets[wid]


def _should_drop_duplicate(event: dict[str, Any]) -> bool:
    """Colapsa eventos identicos en ventana de 500ms."""
    now = time.monotonic()
    _gc_dedup_cache(now)
    key = (
        str(event.get("watch_id", "")),
        str(event.get("pattern_label", "")),
        int(event.get("line_number", 0) or 0),
        int(now / _DEDUP_WINDOW_SEC),
    )
    if key in _dedup_cache:
        return True
    _dedup_cache.add(key)
    return False


def _rate_limit_ok(watch_id: str, importance: str) -> bool:
    """Rate limit por watch_id (sliding window). Criticals siempre pasan."""
    if importance == "critical":
        return True
    now = time.monotonic()
    _gc_rate_buckets(now)
    bucket = _rate_buckets.setdefault(watch_id, deque())
    cutoff = now - _RATE_LIMIT_WINDOW_SEC
    while bucket and bucket[0] < cutoff:
        bucket.popleft()
    if len(bucket) >= _RATE_LIMIT_PER_WATCH_PER_MIN:
        return False
    bucket.append(now)
    return True


def _normalize_event(payload: dict[str, Any]) -> dict[str, Any]:
    """Estructura canonica y campos defaults."""
    return {
        "type": str(payload.get("type", "watcher.match")),
        "watch_id": str(payload.get("watch_id", "") or ""),
        "label": str(payload.get("label", "") or ""),
        "pattern_label": str(payload.get("pattern_label", "") or ""),
        "importance": str(payload.get("importance", "low") or "low"),
        "line_text": str(payload.get("line_text", "") or "")[:500],
        "line_number": int(payload.get("line_number", 0) or 0),
        "stream": str(payload.get("stream", "stdout") or "stdout"),
        "matched_at": int(payload.get("matched_at", int(time.time())) or 0),
    }


class _WatcherMixin:
    """Handlers del subsistema watcher (ingesta + historial + status)."""

    async def handle_watcher_events(self, request: web.Request) -> web.Response:
        """POST /v1/watcher/events.

        Ingesta una notificacion del ProcessWatcher. La normaliza, aplica
        dedup + rate limit, y la publica al EventBus como canal
        `watcher.<importance>` y alias `watcher.match` para wildcard.
        """
        try:
            raw = await request.json()
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                {"ok": False, "error": f"json invalido: {exc}"},
                status=400,
            )
        if not isinstance(raw, dict):
            return web.json_response(
                {"ok": False, "error": "body debe ser objeto"}, status=400
            )

        event = _normalize_event(raw)
        if not event["watch_id"]:
            return web.json_response(
                {"ok": False, "error": "watch_id es requerido"}, status=400
            )

        _METRICS["events_received_total"] += 1
        importance_bucket = event["importance"]
        if importance_bucket in _METRICS_BY_IMPORTANCE:
            _METRICS_BY_IMPORTANCE[importance_bucket] += 1

        if _should_drop_duplicate(event):
            _METRICS["events_dropped_duplicate_total"] += 1
            return web.json_response(
                {"ok": True, "dropped": "duplicate", "event": event}, status=202
            )
        if not _rate_limit_ok(event["watch_id"], event["importance"]):
            _METRICS["events_dropped_rate_limit_total"] += 1
            return web.json_response(
                {"ok": True, "dropped": "rate_limit", "event": event}, status=429
            )

        bus = get_event_bus()
        importance = event["importance"]
        # Fan-out: canal por importance + alias general para suscripciones amplias.
        notified = 0
        try:
            notified += await bus.emit(
                f"watcher.{importance}", event, source="watcher"
            )
            notified += await bus.emit("watcher.match", event, source="watcher")
        except Exception as exc:  # noqa: BLE001
            log.warning("EventBus emit watcher fallo: %s", exc)
            return web.json_response(
                {"ok": False, "error": f"bus emit: {exc}"}, status=500
            )

        _METRICS["events_emitted_total"] += 1

        # Persistencia opcional — no bloquea si falla (TTL default 30 dias).
        try:
            row_id = _get_event_store().append(f"watcher.{importance}", event)
            if row_id is not None:
                _METRICS["events_persisted_total"] += 1
        except Exception as exc:  # noqa: BLE001
            log.debug("event store append fallo: %s", exc)

        return web.json_response(
            {"ok": True, "notified": notified, "event": event}, status=200
        )

    async def handle_watcher_events_recent(
        self, request: web.Request
    ) -> web.Response:
        """GET /v1/watcher/events/recent?limit=50&importance=critical.

        Devuelve los eventos `watcher.*` recientes del historial del EventBus.
        Permite filtrar por importance para consumidores (Nexus, bot Telegram)
        que no tienen WebSocket abierto.
        """
        try:
            limit = int(request.query.get("limit", "50"))
        except ValueError:
            limit = 50
        limit = max(1, min(limit, 500))

        importance = (request.query.get("importance") or "").strip()
        channel = (
            f"watcher.{importance}"
            if importance in {"low", "high", "critical"}
            else "watcher.*"
        )

        bus = get_event_bus()
        try:
            history = bus.get_history(channel=channel, limit=limit)
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                {"ok": False, "error": f"history: {exc}"}, status=500
            )

        return web.json_response({"ok": True, "events": history, "count": len(history)})

    async def handle_watcher_stream(self, request: web.Request) -> web.StreamResponse:
        """GET /v1/watcher/stream?importance=critical.

        SSE stream que emite eventos del watcher en tiempo real. Ideal para
        consumidores browser/Nexus que no tienen WebSocket. Se subscribe al
        EventBus con un listener custom filtrado por importance.
        """
        importance = (request.query.get("importance") or "").strip()
        channel_pattern = (
            f"watcher.{importance}"
            if importance in {"low", "high", "critical"}
            else "watcher.*"
        )

        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
                "Access-Control-Allow-Origin": "*",
            },
        )
        await response.prepare(request)

        queue: asyncio.Queue[dict[str, Any]] = asyncio.Queue(maxsize=200)

        async def _on_event(ch: str, data: dict[str, Any]) -> None:
            try:
                queue.put_nowait({"channel": ch, "data": data})
            except asyncio.QueueFull:
                log.debug("SSE queue full — dropping watcher event")

        bus = get_event_bus()
        listener_id = bus.on(channel_pattern, _on_event)

        welcome = json.dumps(
            {
                "type": "connected",
                "channel": channel_pattern,
                "timestamp": datetime.now().isoformat(),
            }
        )
        try:
            await response.write(f"event: connected\ndata: {welcome}\n\n".encode())
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=25.0)
                    payload = json.dumps(event, ensure_ascii=False)
                    await response.write(
                        f"event: watcher\ndata: {payload}\n\n".encode()
                    )
                except TimeoutError:
                    await response.write(b": heartbeat\n\n")
                except (ConnectionResetError, ConnectionError):
                    break
        finally:
            bus.off(listener_id)
            try:
                await response.write_eof()
            except Exception:  # noqa: BLE001
                pass

        return response

    async def handle_watcher_metrics(self, request: web.Request) -> web.Response:
        """GET /v1/watcher/metrics — contadores Prometheus text/plain.

        Compatible con scrapers Prometheus estandar. Si el request trae
        Accept: application/json, devuelve el snapshot JSON para consumers
        internos (dashboard, Nexus).
        """
        accept = (request.headers.get("Accept") or "").lower()
        if "application/json" in accept:
            return web.json_response({"ok": True, **_metrics_snapshot()})
        body = _format_prometheus()
        return web.Response(
            body=body.encode("utf-8"),
            content_type="text/plain",
            charset="utf-8",
            headers={"Cache-Control": "no-store"},
        )

    async def handle_watcher_events_history(self, request: web.Request) -> web.Response:
        """GET /v1/watcher/events/history?limit=100&importance=critical&watch_id=...

        Historial persistido (SQLite). A diferencia de `events/recent` (ring
        buffer en memoria), sobrevive restarts del gateway.
        """
        try:
            limit = int(request.query.get("limit", "100"))
        except ValueError:
            limit = 100
        importance = (request.query.get("importance") or "").strip() or None
        watch_id = (request.query.get("watch_id") or "").strip() or None

        try:
            events = _get_event_store().recent(
                limit=limit, importance=importance, watch_id=watch_id
            )
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                {"ok": False, "error": f"history: {exc}"}, status=500
            )
        return web.json_response({"ok": True, "events": events, "count": len(events)})

    async def handle_watcher_status(self, request: web.Request) -> web.Response:
        """GET /v1/watcher/status.

        Estado del subsistema watcher desde la perspectiva del gateway:
        eventos recientes, contadores de dedup/rate-limit, totales del bus.
        """
        bus = get_event_bus()
        try:
            stats = bus.get_stats() if hasattr(bus, "get_stats") else {}
        except Exception:  # noqa: BLE001
            stats = {}

        watcher_initialized = _watcher_instance is not None
        engine_stats = {}
        if watcher_initialized:
            try:
                engine_stats = _watcher_instance.stats()
            except Exception:  # noqa: BLE001
                engine_stats = {}

        history_stats: dict[str, Any] = {"available": False}
        if _event_store is not None:
            try:
                history_stats = _event_store.stats()
            except Exception:  # noqa: BLE001
                pass

        return web.json_response(
            {
                "ok": True,
                "dedup_cache_size": len(_dedup_cache),
                "tracked_watches": len(_rate_buckets),
                "rate_limit_per_watch_per_min": _RATE_LIMIT_PER_WATCH_PER_MIN,
                "dedup_window_sec": _DEDUP_WINDOW_SEC,
                "bus_stats": stats,
                "engine_hosted": watcher_initialized,
                "engine_stats": engine_stats,
                "history_store": history_stats,
            }
        )

    # -- Daemon persistente: spawn/kill/list/tail via HTTP -------------------

    async def handle_watcher_spawn(self, request: web.Request) -> web.Response:
        """POST /v1/watcher/spawn — lanza un proceso en el engine hospedado.

        Body: {cmd, patterns?, cwd?, label?, env?}
        Retorna: {ok, watch_id}

        El proceso sobrevive mientras el gateway este arriba — esto es lo
        que permite a Nexus spawnear desde la UI sin ser el owner del engine.
        """
        try:
            body = await request.json()
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                {"ok": False, "error": f"json invalido: {exc}"}, status=400
            )
        if not isinstance(body, dict):
            return web.json_response(
                {"ok": False, "error": "body debe ser objeto"}, status=400
            )
        cmd = str(body.get("cmd") or "").strip()
        if not cmd:
            return web.json_response(
                {"ok": False, "error": "cmd es requerido"}, status=400
            )

        watcher = _get_watcher()
        try:
            watch_id = watcher.spawn(
                cmd,
                patterns=body.get("patterns") or [],
                cwd=body.get("cwd") or None,
                env={str(k): str(v) for k, v in (body.get("env") or {}).items()}
                or None,
                label=body.get("label") or None,
            )
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                {"ok": False, "error": str(exc)}, status=400
            )
        return web.json_response({"ok": True, "watch_id": watch_id})

    async def handle_watcher_kill_http(self, request: web.Request) -> web.Response:
        """POST /v1/watcher/{watch_id}/kill — termina un proceso hospedado."""
        watch_id = request.match_info.get("watch_id", "").strip()
        if not watch_id:
            return web.json_response(
                {"ok": False, "error": "watch_id requerido"}, status=400
            )
        watcher = _get_watcher()
        try:
            ok = watcher.kill(watch_id)
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                {"ok": False, "error": str(exc)}, status=404
            )
        return web.json_response({"ok": True, "killed": ok, "watch_id": watch_id})

    async def handle_watcher_list_http(self, request: web.Request) -> web.Response:
        """GET /v1/watcher/list?include_finished=true."""
        include_finished = request.query.get("include_finished", "true").lower() != "false"
        watcher = _get_watcher()
        watches = watcher.list_watches(include_finished=include_finished)
        return web.json_response({"ok": True, "watches": watches})

    async def handle_watcher_tail_http(self, request: web.Request) -> web.Response:
        """GET /v1/watcher/{watch_id}/tail?lines=50&stream=both."""
        watch_id = request.match_info.get("watch_id", "").strip()
        if not watch_id:
            return web.json_response(
                {"ok": False, "error": "watch_id requerido"}, status=400
            )
        try:
            lines = int(request.query.get("lines", "50"))
        except ValueError:
            lines = 50
        stream = request.query.get("stream", "both")
        watcher = _get_watcher()
        try:
            data = watcher.tail(watch_id, lines=lines, stream=stream)
        except Exception as exc:  # noqa: BLE001
            return web.json_response(
                {"ok": False, "error": str(exc)}, status=404
            )
        return web.json_response({"ok": True, **data})
