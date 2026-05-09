#!/usr/bin/env python3
"""
Bus de eventos para el Antigravity Gateway.
=============================================

Proporciona un bus de eventos desacoplado que integra el endpoint SSE existente
con el nuevo endpoint WebSocket. Los componentes del gateway pueden emitir
eventos sin conocer los mecanismos de transporte subyacentes.

Uso:
    from gateway_events import get_event_bus

    bus = get_event_bus()

    # Registrar listener
    bus.on("agent.*", my_callback)

    # Emitir evento (se propaga a SSE + WebSocket)
    await bus.emit("agent.completed", {"agent": "explorer", "result": "ok"})
"""

from __future__ import annotations

import asyncio
import fnmatch
import logging
import time
from dataclasses import dataclass, field

try:
    from datetime import datetime, UTC
except ImportError:  # Python < 3.11
    from datetime import datetime, timezone

    UTC = UTC
from typing import Any
from collections.abc import Awaitable, Callable

# Constante compartida para el tamaño de la queue SSE
SSE_QUEUE_MAXSIZE = 256
MAX_SSE_SUBSCRIBERS = 50

log = logging.getLogger("antigravity-gateway.events")

# Tipo de callback: puede ser sincrono o asincrono
EventCallback = (
    Callable[[str, dict[str, Any]], None] | Callable[[str, dict[str, Any]], Awaitable[None]]
)


@dataclass
class EventListener:
    """Listener registrado en el bus de eventos.

    Atributos:
        pattern: Patron glob del canal (ej: 'agent.*').
        callback: Funcion a ejecutar cuando se emite un evento.
        listener_id: Identificador unico del listener.
        created_at: Timestamp de creacion.
    """

    pattern: str
    callback: EventCallback
    listener_id: str = ""
    created_at: float = field(default_factory=time.monotonic)

    def matches(self, channel: str) -> bool:
        """Verifica si un canal coincide con el patron del listener.

        Args:
            channel: Canal a verificar.

        Returns:
            True si el canal coincide con el patron.
        """
        if self.pattern == "*":
            return True
        return fnmatch.fnmatch(channel, self.pattern)


@dataclass
class EventRecord:
    """Registro de un evento emitido (para historial).

    Atributos:
        channel: Canal del evento.
        data: Datos del evento.
        timestamp: Momento de emision.
        source: Origen del evento (ej: 'gateway', 'websocket', 'sse').
        listeners_notified: Cantidad de listeners notificados.
    """

    channel: str
    data: dict[str, Any]
    timestamp: str
    source: str = "gateway"
    listeners_notified: int = 0


class EventBus:
    """Bus de eventos para el Gateway.

    Centraliza la emision de eventos y los distribuye a:
    - Listeners registrados por codigo (callbacks)
    - Endpoint SSE (via EventManager del gateway)
    - Endpoint WebSocket (via WebSocketManager)

    El bus soporta patrones glob para suscripciones y mantiene
    un historial limitado de eventos recientes.
    """

    def __init__(self, history_size: int = 500) -> None:
        """Inicializa el bus de eventos.

        Args:
            history_size: Cantidad maxima de eventos a mantener en historial.
        """
        self._listeners: list[EventListener] = []
        self._history: list[EventRecord] = []
        self._history_size = history_size
        self._listener_counter = 0
        self._total_events_emitted = 0
        self._lock = asyncio.Lock()

    async def emit(
        self,
        channel: str,
        data: dict[str, Any],
        source: str = "gateway",
    ) -> int:
        """Emite evento al WebSocket y al SSE stream.

        Distribuye el evento a todos los listeners registrados cuyo patron
        coincida con el canal, y tambien lo envia a los transportes
        WebSocket y SSE si estan disponibles.

        Args:
            channel: Canal del evento (ej: 'agent.started').
            data: Datos del evento.
            source: Origen del evento para trazabilidad.

        Returns:
            Numero total de listeners/clientes notificados.
        """
        timestamp = datetime.now(tz=UTC).isoformat()
        notified = 0

        # 1. Notificar listeners de codigo
        for listener in self._listeners:
            if listener.matches(channel):
                try:
                    result = listener.callback(channel, data)
                    if asyncio.iscoroutine(result):
                        await result
                    notified += 1
                except Exception as exc:
                    log.warning(
                        "Error en listener '%s' para canal '%s': %s",
                        listener.listener_id,
                        channel,
                        exc,
                    )

        # 2. Emitir a WebSocket (si no viene de websocket para evitar loop)
        if source != "websocket":
            try:
                from .gateway_websocket import get_ws_manager

                ws_manager = get_ws_manager()
                ws_sent = await ws_manager.broadcast(channel, data)
                notified += ws_sent
            except ImportError:
                pass
            except Exception as exc:
                log.debug("No se pudo emitir a WebSocket: %s", exc)

        # 3. Emitir a SSE (si no viene de sse para evitar loop)
        if source != "sse":
            try:
                # Intentar acceder al EventManager del gateway
                # Este se integra cuando el gateway pasa su referencia
                if self._sse_emitter is not None:
                    await self._sse_emitter(channel, data)
                    notified += 1
            except AttributeError:
                pass
            except Exception as exc:
                log.debug("No se pudo emitir a SSE: %s", exc)

        # 4. Registrar en historial
        record = EventRecord(
            channel=channel,
            data=data,
            timestamp=timestamp,
            source=source,
            listeners_notified=notified,
        )
        self._history.append(record)
        if len(self._history) > self._history_size:
            self._history = self._history[-self._history_size :]

        self._total_events_emitted += 1

        log.debug(
            "Evento emitido: channel=%s source=%s notified=%d",
            channel,
            source,
            notified,
        )

        return notified

    def on(self, channel: str, callback: EventCallback) -> str:
        """Registra listener para un canal.

        Args:
            channel: Patron glob del canal (ej: 'agent.*', 'task.progress').
            callback: Funcion a ejecutar cuando se emite un evento en el canal.
                Puede ser sincrona o asincrona.

        Returns:
            ID unico del listener para poder eliminarlo despues.
        """
        self._listener_counter += 1
        listener_id = f"listener_{self._listener_counter}"

        listener = EventListener(
            pattern=channel,
            callback=callback,
            listener_id=listener_id,
        )
        self._listeners.append(listener)

        log.info(
            "Listener registrado: id=%s pattern='%s'",
            listener_id,
            channel,
        )
        return listener_id

    def off(self, listener_id: str) -> bool:
        """Elimina un listener registrado.

        Args:
            listener_id: ID del listener retornado por on().

        Returns:
            True si el listener fue encontrado y eliminado.
        """
        for i, listener in enumerate(self._listeners):
            if listener.listener_id == listener_id:
                self._listeners.pop(i)
                log.info("Listener eliminado: id=%s", listener_id)
                return True
        return False

    def set_sse_emitter(
        self,
        emitter: Callable[[str, dict[str, Any]], Awaitable[None]],
    ) -> None:
        """Configura el emisor SSE para integrar con EventManager.

        Args:
            emitter: Funcion asincrona que emite eventos al SSE.
                Firma: async (event_type: str, data: dict) -> None
        """
        self._sse_emitter = emitter
        log.info("SSE emitter configurado en EventBus")

    def get_history(
        self,
        channel: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retorna historial de eventos recientes.

        Args:
            channel: Filtrar por patron de canal (glob). None retorna todos.
            limit: Cantidad maxima de eventos a retornar.

        Returns:
            Lista de eventos ordenados del mas reciente al mas antiguo.
        """
        events = self._history
        if channel is not None:
            events = [e for e in events if fnmatch.fnmatch(e.channel, channel)]

        result = []
        for record in reversed(events[-limit:]):
            result.append(
                {
                    "channel": record.channel,
                    "data": record.data,
                    "timestamp": record.timestamp,
                    "source": record.source,
                    "listeners_notified": record.listeners_notified,
                }
            )

        return result

    def get_stats(self) -> dict[str, Any]:
        """Retorna estadisticas del bus de eventos.

        Returns:
            Diccionario con metricas del bus.
        """
        # Contar eventos por canal
        channel_counts: dict[str, int] = {}
        for record in self._history:
            channel_counts[record.channel] = channel_counts.get(record.channel, 0) + 1

        return {
            "total_events_emitted": self._total_events_emitted,
            "registered_listeners": len(self._listeners),
            "history_size": len(self._history),
            "history_max_size": self._history_size,
            "listeners": [
                {
                    "id": listener.listener_id,
                    "pattern": listener.pattern,
                }
                for listener in self._listeners
            ],
            "events_by_channel": channel_counts,
            "has_sse_emitter": hasattr(self, "_sse_emitter") and self._sse_emitter is not None,
        }


# ============================================================
# SSE Event Manager (con limites)
# ============================================================
class EventManager:
    """Gestiona conexiones SSE para streaming de eventos."""

    def __init__(self, max_subscribers: int = MAX_SSE_SUBSCRIBERS):
        self._subscribers: set[asyncio.Queue] = set()
        self._max_subscribers = max_subscribers

    @property
    def count(self) -> int:
        """Retorna el numero de suscriptores activos."""
        return len(self._subscribers)

    def subscribe(self) -> asyncio.Queue | None:
        """Crea una nueva suscripcion SSE. Retorna None si se alcanzo el limite."""
        if len(self._subscribers) >= self._max_subscribers:
            return None
        queue: asyncio.Queue = asyncio.Queue(maxsize=SSE_QUEUE_MAXSIZE)
        self._subscribers.add(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Elimina una suscripcion."""
        self._subscribers.discard(queue)

    async def emit(self, event_type: str, data: dict) -> None:
        """Emite un evento a todos los suscriptores."""
        event = {
            "type": event_type,
            "data": data,
            "timestamp": datetime.now().isoformat(),
        }
        dead_queues = []
        for queue in self._subscribers:
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead_queues.append(queue)
        for q in dead_queues:
            self._subscribers.discard(q)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Obtener instancia singleton del EventBus.

    Returns:
        La instancia global de EventBus.
    """
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# ---------------------------------------------------------------------------
# Helper para integrar con el gateway existente
# ---------------------------------------------------------------------------
def integrate_with_gateway(event_manager: Any) -> EventBus:
    """Integra el EventBus con el EventManager SSE existente del gateway.

    Conecta el EventBus con el EventManager del gateway para que
    los eventos emitidos via el bus tambien se propaguen a los
    suscriptores SSE.

    Args:
        event_manager: Instancia de EventManager del gateway
            (debe tener metodo `emit(event_type, data)`).

    Returns:
        La instancia del EventBus configurada.
    """
    bus = get_event_bus()

    async def sse_emitter(channel: str, data: dict[str, Any]) -> None:
        """Emite evento al EventManager SSE."""
        await event_manager.emit(channel, data)

    bus.set_sse_emitter(sse_emitter)

    log.info(
        "EventBus integrado con EventManager SSE (%d suscriptores activos)",
        event_manager.count,
    )
    return bus
