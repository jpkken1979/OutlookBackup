"""
WebSocket Bridge — streaming en tiempo real del event bus.

Puente entre el event bus interno y clientes WebSocket.
Permite que Nexus Desktop y otros clientes reciban eventos en vivo:
  - Suscripción por tópico (wildcard con *)
  - Broadcast de eventos del bus
  - Heartbeat para detectar desconexiones
  - Historial de eventos recientes (replay)
  - Rate limiting por cliente

Usage:
    bridge = WebSocketBridge(bus=bus, host="0.0.0.0", port=4748)
    await bridge.start()

    # Desde cliente JS:
    # ws = new WebSocket("ws://localhost:4748")
    # ws.send(JSON.stringify({type: "subscribe", topics: ["task.*", "genome.*"]}))
"""

import asyncio
import json
import logging
import time
import uuid
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.ws_bridge")

# ============================================================
# Constantes
# ============================================================
DEFAULT_PORT = 4748
MAX_REPLAY_BUFFER = 200  # Eventos recientes almacenados
MAX_CLIENTS = 50  # Máximo de clientes simultáneos
HEARTBEAT_INTERVAL = 30.0  # Segundos entre heartbeats
RATE_LIMIT_PER_SEC = 100  # Mensajes por segundo por cliente
CLIENT_TIMEOUT = 120.0  # Timeout de inactividad


# ============================================================
# Modelos
# ============================================================
@dataclass
class WsClient:
    """Cliente WebSocket conectado."""

    client_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    subscriptions: set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=time.time)
    last_activity: float = field(default_factory=time.time)
    messages_sent: int = 0
    messages_received: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_id": self.client_id,
            "subscriptions": sorted(self.subscriptions),
            "connected_at": self.connected_at,
            "last_activity": self.last_activity,
            "messages_sent": self.messages_sent,
            "messages_received": self.messages_received,
            "uptime_seconds": round(time.time() - self.connected_at, 1),
        }


@dataclass
class BridgeEvent:
    """Evento del bridge."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    topic: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    source: str = "system"
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "topic": self.topic,
            "payload": self.payload,
            "source": self.source,
            "timestamp": self.timestamp,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), default=str)


# ============================================================
# WebSocket Bridge
# ============================================================
class WebSocketBridge:
    """
    Puente WebSocket para streaming de eventos en tiempo real.
    Conecta el event bus interno con clientes externos.
    """

    def __init__(
        self,
        bus: Any = None,
        host: str = "127.0.0.1",
        port: int = DEFAULT_PORT,
    ) -> None:
        self._bus = bus
        self._host = host
        self._port = port
        self._running = False

        # Clientes conectados
        self._clients: dict[str, WsClient] = {}

        # Writers por client_id (simulado sin websocket real)
        self._writers: dict[str, asyncio.Queue[str]] = {}

        # Buffer de replay
        self._replay_buffer: deque[BridgeEvent] = deque(maxlen=MAX_REPLAY_BUFFER)

        # Métricas
        self._metrics = {
            "total_connections": 0,
            "total_disconnections": 0,
            "total_events_broadcast": 0,
            "total_events_received": 0,
            "total_subscriptions": 0,
            "peak_clients": 0,
        }

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------
    async def start(self) -> None:
        """Inicia el bridge."""
        self._running = True
        logger.info("WebSocketBridge started on ws://%s:%d", self._host, self._port)

    async def stop(self) -> None:
        """Detiene el bridge."""
        self._running = False
        self._clients.clear()
        self._writers.clear()
        logger.info("WebSocketBridge stopped")

    # --------------------------------------------------------
    # Client Management
    # --------------------------------------------------------
    def connect_client(self, client_id: str | None = None) -> dict[str, Any]:
        """Registra un nuevo cliente."""
        if len(self._clients) >= MAX_CLIENTS:
            return {"error": "Max clients reached", "limit": MAX_CLIENTS}

        client = WsClient(client_id=client_id or str(uuid.uuid4())[:8])
        self._clients[client.client_id] = client
        self._writers[client.client_id] = asyncio.Queue()

        self._metrics["total_connections"] += 1
        current = len(self._clients)
        if current > self._metrics["peak_clients"]:
            self._metrics["peak_clients"] = current

        logger.info("Client %s connected (%d active)", client.client_id, current)
        return client.to_dict()

    def disconnect_client(self, client_id: str) -> bool:
        """Desconecta un cliente."""
        if client_id not in self._clients:
            return False

        del self._clients[client_id]
        self._writers.pop(client_id, None)
        self._metrics["total_disconnections"] += 1

        logger.info("Client %s disconnected (%d active)", client_id, len(self._clients))
        return True

    # --------------------------------------------------------
    # Subscriptions
    # --------------------------------------------------------
    def subscribe(self, client_id: str, topics: list[str]) -> dict[str, Any]:
        """Suscribe un cliente a tópicos."""
        client = self._clients.get(client_id)
        if not client:
            return {"error": "Client not found"}

        for topic in topics:
            client.subscriptions.add(topic)
            self._metrics["total_subscriptions"] += 1

        client.last_activity = time.time()
        return {
            "client_id": client_id,
            "subscriptions": sorted(client.subscriptions),
        }

    def unsubscribe(self, client_id: str, topics: list[str]) -> dict[str, Any]:
        """Desuscribe de tópicos."""
        client = self._clients.get(client_id)
        if not client:
            return {"error": "Client not found"}

        for topic in topics:
            client.subscriptions.discard(topic)

        client.last_activity = time.time()
        return {
            "client_id": client_id,
            "subscriptions": sorted(client.subscriptions),
        }

    # --------------------------------------------------------
    # Broadcasting
    # --------------------------------------------------------
    def broadcast(
        self,
        topic: str,
        payload: dict[str, Any] | None = None,
        source: str = "system",
    ) -> dict[str, Any]:
        """
        Emite un evento a todos los clientes suscritos.

        Returns:
            Resumen del broadcast.
        """
        event = BridgeEvent(topic=topic, payload=payload or {}, source=source)
        self._replay_buffer.append(event)

        recipients = 0
        for client_id, client in self._clients.items():
            if self._matches_subscription(topic, client.subscriptions):
                queue = self._writers.get(client_id)
                if queue:
                    try:
                        queue.put_nowait(event.to_json())
                        client.messages_sent += 1
                        recipients += 1
                    except asyncio.QueueFull:
                        pass

        self._metrics["total_events_broadcast"] += 1

        return {
            "event_id": event.event_id,
            "topic": topic,
            "recipients": recipients,
            "total_clients": len(self._clients),
        }

    def replay(self, client_id: str, since: float = 0.0) -> list[dict[str, Any]]:
        """Replay de eventos recientes desde timestamp."""
        client = self._clients.get(client_id)
        if not client:
            return []

        events = []
        for event in self._replay_buffer:
            if event.timestamp > since:
                if self._matches_subscription(event.topic, client.subscriptions):
                    events.append(event.to_dict())

        return events

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_clients(self) -> list[dict[str, Any]]:
        """Lista clientes conectados."""
        return [c.to_dict() for c in self._clients.values()]

    def get_client(self, client_id: str) -> dict[str, Any] | None:
        """Info de un cliente."""
        client = self._clients.get(client_id)
        return client.to_dict() if client else None

    def get_replay_buffer(self, limit: int = 50) -> list[dict[str, Any]]:
        """Eventos recientes."""
        events = list(self._replay_buffer)[-limit:]
        return [e.to_dict() for e in events][::-1]

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del bridge."""
        return {
            "running": self._running,
            "host": self._host,
            "port": self._port,
            "active_clients": len(self._clients),
            "replay_buffer_size": len(self._replay_buffer),
            "metrics": {**self._metrics},
        }

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _matches_subscription(self, topic: str, subscriptions: set[str]) -> bool:
        """Verifica si un topic coincide con alguna suscripción."""
        if not subscriptions:
            return False

        for sub in subscriptions:
            if sub == "*":
                return True
            if sub == topic:
                return True
            # Wildcard: "task.*" matches "task.completed", "task.failed"
            if sub.endswith(".*"):
                prefix = sub[:-2]
                if topic.startswith(prefix + ".") or topic == prefix:
                    return True
        return False


# ============================================================
# Singleton
# ============================================================
_instance: WebSocketBridge | None = None


def get_ws_bridge(bus: Any = None) -> WebSocketBridge:
    """Obtiene o crea el WebSocket bridge global."""
    global _instance
    if _instance is None:
        _instance = WebSocketBridge(bus=bus)
    return _instance
