"""
Agent Observatory — Agregador de eventos en tiempo real.

Unifica todos los streams del ecosistema en un timeline único:
  - Ejecuciones de agentes (daemon)
  - Eventos reactivos (reactive_event_system)
  - Subastas y negociaciones (agent_negotiation)
  - Progreso de swarms (swarm_coordinator)
  - Decisiones del router (intelligent_router)
  - Resoluciones de consenso (consensus_protocol)
  - Anomalías detectadas (anomaly_detector)
  - Heartbeats del daemon

Proporciona:
  - Timeline unificado con filtros por tipo/agente/severidad
  - Snapshot del estado actual de todo el ecosistema
  - Métricas agregadas en tiempo real
  - Ring buffer configurable (últimos N eventos)

Usage:
    observatory = AgentObservatory(bus=bus)
    await observatory.start()

    # Obtener timeline
    events = observatory.get_timeline(limit=50, event_type="agent_execution")

    # Snapshot del ecosistema
    snapshot = await observatory.get_ecosystem_snapshot()
    print(snapshot["active_agents"])
    print(snapshot["active_swarms"])
    print(snapshot["recent_decisions"])

    # Stream para WebSocket
    async for event in observatory.stream():
        send_to_ws(event)
"""
# mypy: ignore-errors

import asyncio
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.agent_observatory")

# ============================================================
# Constantes
# ============================================================
MAX_TIMELINE_SIZE = 2000
MAX_SUBSCRIBERS = 50
OBSERVATORY_CHANNEL = "observatory.events"

# Canales del bus que el observatorio escucha
WATCHED_CHANNELS = [
    "tasks.completed",
    "tasks.failed",
    "daemon.lifecycle",
    "reactive.events",
    "reactive.triggers",
    "negotiation",
    "swarm.events",
    "router.decisions",
    "consensus.events",
]


# ============================================================
# Tipos de evento del observatory
# ============================================================
class ObservatoryEventType(str, Enum):
    """Tipos de evento unificados."""

    AGENT_STARTED = "agent_started"
    AGENT_COMPLETED = "agent_completed"
    AGENT_FAILED = "agent_failed"
    DAEMON_LIFECYCLE = "daemon_lifecycle"
    REACTIVE_EVENT = "reactive_event"
    REACTIVE_TRIGGER = "reactive_trigger"
    AUCTION_RESULT = "auction_result"
    SWARM_EVENT = "swarm_event"
    ROUTE_DECISION = "route_decision"
    CONSENSUS_EVENT = "consensus_event"
    ANOMALY = "anomaly"
    HEARTBEAT = "heartbeat"
    SYSTEM = "system"


# ============================================================
# Modelo de evento unificado
# ============================================================
@dataclass
class ObservatoryEvent:
    """Evento unificado del observatorio."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: ObservatoryEventType = ObservatoryEventType.SYSTEM
    source_channel: str = ""
    agent: str | None = None
    summary: str = ""
    severity: str = "info"  # info, warning, error, critical
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type.value,
            "source_channel": self.source_channel,
            "agent": self.agent,
            "summary": self.summary,
            "severity": self.severity,
            "data": self.data,
            "timestamp": self.timestamp,
            "age_seconds": round(time.time() - self.timestamp, 1),
        }


# ============================================================
# Event Normalizer — convierte mensajes del bus en eventos unificados
# ============================================================
class EventNormalizer:
    """Normaliza mensajes de diferentes canales en ObservatoryEvents."""

    @staticmethod
    def normalize(channel: str, payload: dict[str, Any]) -> ObservatoryEvent:
        """Convierte un mensaje del bus en un ObservatoryEvent."""
        if channel == "tasks.completed":
            return ObservatoryEvent(
                event_type=ObservatoryEventType.AGENT_COMPLETED,
                source_channel=channel,
                agent=payload.get("agent"),
                summary=(
                    f"Agente '{payload.get('agent')}' completó tarea "
                    f"en {payload.get('duration_seconds', 0):.1f}s"
                ),
                data=payload,
            )

        elif channel == "tasks.failed":
            return ObservatoryEvent(
                event_type=ObservatoryEventType.AGENT_FAILED,
                source_channel=channel,
                agent=payload.get("agent"),
                summary=(
                    f"Agente '{payload.get('agent')}' falló: {payload.get('error', 'unknown')[:80]}"
                ),
                severity="error",
                data=payload,
            )

        elif channel == "daemon.lifecycle":
            return ObservatoryEvent(
                event_type=ObservatoryEventType.DAEMON_LIFECYCLE,
                source_channel=channel,
                summary=f"Daemon {payload.get('event', '?')}: {payload.get('daemon_id', '?')}",
                data=payload,
            )

        elif channel == "reactive.events":
            return ObservatoryEvent(
                event_type=ObservatoryEventType.REACTIVE_EVENT,
                source_channel=channel,
                summary=(
                    f"Evento reactivo: {payload.get('event_type', '?')} "
                    f"de {payload.get('source', '?')}"
                ),
                data=payload,
            )

        elif channel == "reactive.triggers":
            return ObservatoryEvent(
                event_type=ObservatoryEventType.REACTIVE_TRIGGER,
                source_channel=channel,
                agent=payload.get("agent"),
                summary=(
                    f"Trigger '{payload.get('rule_name', '?')}' "
                    f"→ agente '{payload.get('agent', '?')}'"
                ),
                data=payload,
            )

        elif channel == "negotiation":
            return ObservatoryEvent(
                event_type=ObservatoryEventType.AUCTION_RESULT,
                source_channel=channel,
                agent=payload.get("winner"),
                summary=(
                    f"Subasta: ganador='{payload.get('winner', '?')}' "
                    f"({payload.get('bids', 0)} pujas)"
                ),
                data=payload,
            )

        elif channel == "swarm.events":
            return ObservatoryEvent(
                event_type=ObservatoryEventType.SWARM_EVENT,
                source_channel=channel,
                summary=f"Swarm {payload.get('event', '?')}: {payload.get('swarm_id', '?')[:8]}",
                data=payload,
            )

        elif channel == "router.decisions":
            return ObservatoryEvent(
                event_type=ObservatoryEventType.ROUTE_DECISION,
                source_channel=channel,
                agent=payload.get("agent"),
                summary=(
                    f"Router → {payload.get('route', '?')}: '{payload.get('task', '?')[:60]}'"
                ),
                data=payload,
            )

        # Default
        return ObservatoryEvent(
            event_type=ObservatoryEventType.SYSTEM,
            source_channel=channel,
            summary=f"Evento de '{channel}'",
            data=payload,
        )


# ============================================================
# Agent Observatory
# ============================================================
class AgentObservatory:
    """
    Observatorio centralizado del ecosistema de agentes.
    Agrega todos los eventos en un timeline unificado.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus
        self._running = False

        # Timeline: ring buffer de eventos
        self._timeline: deque[ObservatoryEvent] = deque(maxlen=MAX_TIMELINE_SIZE)

        # Subscribers para streaming
        self._subscribers: list[asyncio.Queue[ObservatoryEvent]] = []

        # Background tasks
        self._listener_tasks: list[asyncio.Task] = []

        # Métricas agregadas
        self._metrics = {
            "events_total": 0,
            "events_by_type": {t.value: 0 for t in ObservatoryEventType},
            "events_by_severity": {"info": 0, "warning": 0, "error": 0, "critical": 0},
            "active_since": 0.0,
        }

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------
    async def start(self) -> None:
        """Inicia el observatorio y comienza a escuchar eventos."""
        if self._running:
            return
        self._running = True
        self._metrics["active_since"] = time.time()

        # Suscribirse a canales del bus
        if self._bus:
            for channel in WATCHED_CHANNELS:
                try:
                    queue = await self._bus.subscribe_queue(channel)
                    task = asyncio.create_task(
                        self._channel_listener(channel, queue),
                        name=f"observatory-{channel}",
                    )
                    self._listener_tasks.append(task)
                except Exception as e:
                    logger.debug("No se pudo suscribir a %s: %s", channel, e)

        logger.info(
            "AgentObservatory iniciado, escuchando %d canales",
            len(self._listener_tasks),
        )

    async def stop(self) -> None:
        """Detiene el observatorio."""
        self._running = False
        for task in self._listener_tasks:
            task.cancel()
        self._listener_tasks.clear()
        logger.info("AgentObservatory detenido")

    async def _channel_listener(
        self,
        channel: str,
        queue: asyncio.Queue,
    ) -> None:
        """Escucha un canal y agrega eventos al timeline."""
        while self._running:
            try:
                msg = await asyncio.wait_for(queue.get(), timeout=5.0)
                payload = msg.payload if hasattr(msg, "payload") else msg
                if not isinstance(payload, dict):
                    payload = {"raw": str(payload)}

                event = EventNormalizer.normalize(channel, payload)
                self._ingest(event)

            except TimeoutError:
                continue
            except asyncio.CancelledError:
                return
            except Exception as e:
                logger.debug("Error en listener %s: %s", channel, e)

    # --------------------------------------------------------
    # Event Ingestion
    # --------------------------------------------------------
    def _ingest(self, event: ObservatoryEvent) -> None:
        """Agrega un evento al timeline y notifica subscribers."""
        self._timeline.append(event)
        self._metrics["events_total"] += 1
        self._metrics["events_by_type"][event.event_type.value] = (
            self._metrics["events_by_type"].get(event.event_type.value, 0) + 1
        )
        self._metrics["events_by_severity"][event.severity] = (
            self._metrics["events_by_severity"].get(event.severity, 0) + 1
        )

        # Notificar subscribers
        dead_subscribers = []
        for i, queue in enumerate(self._subscribers):
            try:
                queue.put_nowait(event)
            except asyncio.QueueFull:
                dead_subscribers.append(i)

        # Limpiar subscribers muertos
        for i in reversed(dead_subscribers):
            self._subscribers.pop(i)

    def record_event(
        self,
        event_type: str,
        summary: str,
        agent: str | None = None,
        severity: str = "info",
        data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Registra un evento manualmente (API pública)."""
        event = ObservatoryEvent(
            event_type=ObservatoryEventType(event_type),
            source_channel="api",
            agent=agent,
            summary=summary,
            severity=severity,
            data=data or {},
        )
        self._ingest(event)
        return event.to_dict()

    # --------------------------------------------------------
    # Timeline & Queries
    # --------------------------------------------------------
    def get_timeline(
        self,
        limit: int = 50,
        event_type: str | None = None,
        agent: str | None = None,
        severity: str | None = None,
        since_timestamp: float | None = None,
    ) -> list[dict[str, Any]]:
        """
        Retorna el timeline filtrado.

        Args:
            limit: Máximo de eventos a retornar.
            event_type: Filtrar por tipo.
            agent: Filtrar por agente.
            severity: Filtrar por severidad.
            since_timestamp: Solo eventos después de este timestamp.
        """
        events = list(self._timeline)

        if event_type:
            events = [e for e in events if e.event_type.value == event_type]
        if agent:
            events = [e for e in events if e.agent == agent]
        if severity:
            events = [e for e in events if e.severity == severity]
        if since_timestamp:
            events = [e for e in events if e.timestamp > since_timestamp]

        # Últimos N, ordenados por timestamp descendente
        return [e.to_dict() for e in events[-limit:]][::-1]

    # --------------------------------------------------------
    # Ecosystem Snapshot
    # --------------------------------------------------------
    async def get_ecosystem_snapshot(self) -> dict[str, Any]:
        """
        Retorna un snapshot completo del estado actual del ecosistema.
        Agrega datos del daemon, reactive system, negotiations, swarms, etc.
        """
        snapshot: dict[str, Any] = {
            "timestamp": time.time(),
            "observatory": self.get_stats(),
        }

        try:
            from .agent_daemon import get_daemon

            daemon = await get_daemon()

            snapshot["daemon"] = daemon.get_status()
            snapshot["reactive"] = daemon.get_reactive_stats()
            snapshot["negotiation"] = daemon.get_negotiation_stats()
            snapshot["swarm"] = daemon.get_swarm_stats()
            snapshot["anomalies"] = daemon.get_anomaly_stats()
            snapshot["workflows"] = daemon.get_workflow_stats()
            snapshot["improvement"] = daemon.get_improvement_report()

        except Exception as e:
            snapshot["daemon_error"] = str(e)

        # Resumen de actividad reciente
        recent = list(self._timeline)[-20:]
        snapshot["recent_activity"] = {
            "event_count": len(recent),
            "agents_active": list({e.agent for e in recent if e.agent}),
            "error_count": sum(1 for e in recent if e.severity == "error"),
        }

        return snapshot

    # --------------------------------------------------------
    # Streaming
    # --------------------------------------------------------
    def subscribe(self) -> asyncio.Queue[ObservatoryEvent]:
        """Crea una suscripción para streaming de eventos."""
        if len(self._subscribers) >= MAX_SUBSCRIBERS:
            # Eliminar el subscriber más viejo
            self._subscribers.pop(0)
        queue: asyncio.Queue[ObservatoryEvent] = asyncio.Queue(maxsize=500)
        self._subscribers.append(queue)
        return queue

    def unsubscribe(self, queue: asyncio.Queue) -> None:
        """Elimina una suscripción."""
        try:
            self._subscribers.remove(queue)
        except ValueError:
            pass

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del observatorio."""
        uptime = time.time() - self._metrics["active_since"] if self._metrics["active_since"] else 0
        return {
            "running": self._running,
            "timeline_size": len(self._timeline),
            "timeline_max": MAX_TIMELINE_SIZE,
            "subscribers": len(self._subscribers),
            "listener_channels": len(self._listener_tasks),
            "uptime_seconds": round(uptime, 1),
            "metrics": {**self._metrics},
        }


# ============================================================
# Singleton
# ============================================================
_instance: AgentObservatory | None = None


async def get_agent_observatory(bus: Any = None) -> AgentObservatory:
    """Obtiene o crea el observatorio global."""
    global _instance
    if _instance is None:
        _instance = AgentObservatory(bus=bus)
    return _instance
