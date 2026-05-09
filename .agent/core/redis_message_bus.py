"""
Redis Message Bus - Backbone de comunicación inter-agente real.

Reemplaza el sistema in-memory y de polling SQLite con una arquitectura
event-driven sobre Redis Streams + Pub/Sub. Fallback automático a SQLite
si Redis no está disponible.

Características:
  - Redis Streams (XADD/XREAD) para entrega garantizada con persistencia
  - Pub/Sub para notificaciones en tiempo real (sub-millisecond latency)
  - Sorted Sets para colas de prioridad
  - Dead Letter Queue (DLQ) para mensajes fallados
  - Consumer Groups para procesamiento distribuido
  - Fallback a TelepathyBlackboard (SQLite) si Redis no disponible

Usage:
    bus = await RedisMessageBus.create()
    await bus.publish("agent.explorer.inbox", {"task": "analiza repo", "from": "planner"})

    async for message in bus.subscribe("agent.explorer.inbox"):
        process(message)

    # Cola con prioridad
    await bus.enqueue_priority("tasks", payload, priority=Priority.HIGH)
    task = await bus.dequeue_priority("tasks")
"""

import asyncio
import json
import logging
import time
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from enum import IntEnum
from typing import Any

logger = logging.getLogger("antigravity.redis_message_bus")

# ============================================================
# Constantes
# ============================================================
STREAM_MAXLEN = 10_000  # Máximo de mensajes en un stream
DLQ_STREAM = "antigravity:dlq"  # Dead Letter Queue stream
HEARTBEAT_CHANNEL = "antigravity:heartbeats"
TASK_QUEUE_KEY = "antigravity:tasks"  # Sorted Set para prioridad
DEFAULT_CONSUMER_GROUP = "antigravity-workers"
BLOCK_TIMEOUT_MS = 2_000  # Tiempo de bloqueo en XREAD (ms)


# ============================================================
# Prioridades de mensajes
# ============================================================
class Priority(IntEnum):
    """Prioridad de mensajes. Valor menor = mayor prioridad en Sorted Sets."""

    CRITICAL = 1
    HIGH = 2
    NORMAL = 3
    LOW = 4
    BACKGROUND = 5


# ============================================================
# Modelo de mensaje del bus
# ============================================================
@dataclass
class BusMessage:
    """Mensaje normalizado del bus."""

    message_id: str
    channel: str
    payload: dict[str, Any]
    from_agent: str
    to_agent: str | None
    priority: Priority
    timestamp: float
    ttl_seconds: int
    retries: int = 0
    stream_id: str | None = None  # Redis stream entry ID
    correlation_id: str | None = None  # Para request-reply A2A
    reply_channel: str | None = None  # Canal donde enviar la respuesta

    @classmethod
    def create(
        cls,
        channel: str,
        payload: dict[str, Any],
        from_agent: str = "system",
        to_agent: str | None = None,
        priority: Priority = Priority.NORMAL,
        ttl_seconds: int = 3600,
        correlation_id: str | None = None,
        reply_channel: str | None = None,
    ) -> "BusMessage":
        """Crea un nuevo mensaje con ID único."""
        return cls(
            message_id=str(uuid.uuid4()),
            channel=channel,
            payload=payload,
            from_agent=from_agent,
            to_agent=to_agent,
            priority=priority,
            timestamp=time.time(),
            ttl_seconds=ttl_seconds,
            correlation_id=correlation_id,
            reply_channel=reply_channel,
        )

    def to_redis_dict(self) -> dict[str, str]:
        """Serializa para almacenar en Redis Stream."""
        return {
            "message_id": self.message_id,
            "channel": self.channel,
            "payload": json.dumps(self.payload),
            "from_agent": self.from_agent,
            "to_agent": self.to_agent or "",
            "priority": str(self.priority.value),
            "timestamp": str(self.timestamp),
            "ttl_seconds": str(self.ttl_seconds),
            "retries": str(self.retries),
            "correlation_id": self.correlation_id or "",
            "reply_channel": self.reply_channel or "",
        }

    @classmethod
    def from_redis_dict(cls, data: dict, stream_id: str = "") -> "BusMessage":
        """Deserializa desde Redis Stream entry."""
        return cls(
            message_id=data.get("message_id", ""),
            channel=data.get("channel", ""),
            payload=json.loads(data.get("payload", "{}")),
            from_agent=data.get("from_agent", "system"),
            to_agent=data.get("to_agent") or None,
            priority=Priority(int(data.get("priority", Priority.NORMAL.value))),
            timestamp=float(data.get("timestamp", 0)),
            ttl_seconds=int(data.get("ttl_seconds", 3600)),
            retries=int(data.get("retries", 0)),
            stream_id=stream_id,
            correlation_id=data.get("correlation_id") or None,
            reply_channel=data.get("reply_channel") or None,
        )

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict Python normal."""
        return {
            "message_id": self.message_id,
            "channel": self.channel,
            "payload": self.payload,
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "priority": self.priority.name,
            "timestamp": self.timestamp,
            "ttl_seconds": self.ttl_seconds,
            "retries": self.retries,
            "correlation_id": self.correlation_id,
            "reply_channel": self.reply_channel,
        }


# ============================================================
# Fallback SQLite (cuando Redis no está disponible)
# ============================================================
class _SQLiteFallback:
    """
    Fallback usando TelepathyBlackboard + asyncio cuando Redis no está disponible.
    Mantiene la misma interfaz que RedisMessageBus.
    """

    def __init__(self) -> None:
        from pathlib import Path

        self._db_path = Path(".antigravity_message_bus.db")
        self._subscribers: dict[str, list[asyncio.Queue]] = {}
        self._init_db()

    def _init_db(self) -> None:
        import sqlite3

        with sqlite3.connect(self._db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS bus_messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_id TEXT NOT NULL,
                    channel TEXT NOT NULL,
                    payload TEXT NOT NULL,
                    from_agent TEXT NOT NULL,
                    to_agent TEXT,
                    priority INTEGER DEFAULT 3,
                    timestamp REAL NOT NULL,
                    ttl_seconds INTEGER DEFAULT 3600,
                    retries INTEGER DEFAULT 0,
                    acked INTEGER DEFAULT 0
                )
            """)
            conn.execute("CREATE INDEX IF NOT EXISTS idx_channel ON bus_messages(channel)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_acked ON bus_messages(acked)")
            conn.commit()

    async def publish(self, channel: str, message: BusMessage) -> str:
        """Publica en SQLite y notifica subscribers en memoria."""
        import sqlite3

        with sqlite3.connect(self._db_path) as conn:
            conn.execute(
                """INSERT INTO bus_messages
                   (message_id, channel, payload, from_agent, to_agent, priority, timestamp, ttl_seconds)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    message.message_id,
                    channel,
                    json.dumps(message.payload),
                    message.from_agent,
                    message.to_agent,
                    message.priority.value,
                    message.timestamp,
                    message.ttl_seconds,
                ),
            )
            conn.commit()

        # Notificar subscribers en memoria
        for queue in self._subscribers.get(channel, []):
            await queue.put(message)
        # Wildcard subscribers
        for queue in self._subscribers.get("*", []):
            await queue.put(message)

        return message.message_id

    async def subscribe_queue(self, channel: str) -> asyncio.Queue:
        """Retorna una queue para suscribirse a un canal."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        if channel not in self._subscribers:
            self._subscribers[channel] = []
        self._subscribers[channel].append(queue)
        return queue

    async def get_messages(self, channel: str, since_timestamp: float = 0.0) -> list[BusMessage]:
        """Lee mensajes históricos de un canal."""
        import sqlite3

        with sqlite3.connect(self._db_path) as conn:
            rows = conn.execute(
                """SELECT message_id, channel, payload, from_agent, to_agent,
                          priority, timestamp, ttl_seconds, retries
                   FROM bus_messages
                   WHERE channel = ? AND timestamp > ? AND acked = 0
                   ORDER BY priority ASC, timestamp ASC""",
                (channel, since_timestamp),
            ).fetchall()

        messages = []
        for row in rows:
            messages.append(
                BusMessage(
                    message_id=row[0],
                    channel=row[1],
                    payload=json.loads(row[2]),
                    from_agent=row[3],
                    to_agent=row[4] or None,
                    priority=Priority(row[5]),
                    timestamp=row[6],
                    ttl_seconds=row[7],
                    retries=row[8],
                )
            )
        return messages

    async def ack(self, message_id: str) -> None:
        """Marca un mensaje como procesado."""
        import sqlite3

        with sqlite3.connect(self._db_path) as conn:
            conn.execute("UPDATE bus_messages SET acked = 1 WHERE message_id = ?", (message_id,))
            conn.commit()

    async def close(self) -> None:
        pass

    @property
    def is_redis(self) -> bool:
        return False


# ============================================================
# Redis Message Bus Principal
# ============================================================
class RedisMessageBus:
    """
    Message bus basado en Redis Streams + Pub/Sub.

    Arquitectura:
      - Canal de notificación: Redis Pub/Sub (sub-ms, fire-and-forget)
      - Entrega garantizada: Redis Streams (XADD/XREAD + consumer groups)
      - Cola prioridad: Redis Sorted Sets (ZADD/ZPOPMIN)
      - DLQ: Stream "antigravity:dlq" para mensajes fallados
      - Fallback: SQLite si Redis no disponible
    """

    def __init__(self, backend: Any, use_redis: bool) -> None:
        self._backend = backend
        self._use_redis = use_redis
        self._pubsub_handlers: dict[str, list] = {}
        self._running = False
        self._listener_task: asyncio.Task | None = None
        self._reply_listener_task: asyncio.Task | None = None
        self._stats = {
            "published": 0,
            "consumed": 0,
            "dlq_count": 0,
            "errors": 0,
            "a2a_requests": 0,
            "a2a_replies": 0,
        }
        # A2A Request-Reply state
        self._pending_replies: dict[str, asyncio.Future] = {}
        self._a2a_handlers: dict[str, Any] = {}
        self._inbox_tasks: dict[str, asyncio.Task] = {}

    @classmethod
    async def create(
        cls,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
    ) -> "RedisMessageBus":
        """
        Crea una instancia del bus.
        Intenta conectar a Redis; si falla, usa fallback SQLite.
        """
        try:
            import redis.asyncio as aioredis

            client = aioredis.Redis(
                host=host,
                port=port,
                db=db,
                password=password,
                decode_responses=True,
                socket_connect_timeout=2,
                socket_timeout=2,
            )
            # Test de conectividad. `redis.asyncio.Redis.ping()` retorna
            # `Awaitable[bool] | bool` segun la version de redis-py — el cliente
            # async siempre devuelve coroutine, asi que ignoramos el `misc`.
            await client.ping()  # type: ignore[misc]
            logger.info("RedisMessageBus conectado a Redis %s:%s", host, port)
            return cls(backend=client, use_redis=True)
        except Exception as e:
            logger.warning("Redis no disponible (%s). Usando fallback SQLite.", e)
            return cls(backend=_SQLiteFallback(), use_redis=False)

    # --------------------------------------------------------
    # Publish
    # --------------------------------------------------------
    async def publish(
        self,
        channel: str,
        payload: dict[str, Any],
        from_agent: str = "system",
        to_agent: str | None = None,
        priority: Priority = Priority.NORMAL,
        ttl_seconds: int = 3600,
    ) -> str:
        """
        Publica un mensaje en un canal.

        Returns:
            message_id del mensaje publicado.
        """
        msg = BusMessage.create(
            channel=channel,
            payload=payload,
            from_agent=from_agent,
            to_agent=to_agent,
            priority=priority,
            ttl_seconds=ttl_seconds,
        )

        if self._use_redis:
            stream_key = f"antigravity:stream:{channel}"
            await self._backend.xadd(
                stream_key,
                msg.to_redis_dict(),
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
            # Pub/Sub para notificación instantánea
            await self._backend.publish(channel, json.dumps(msg.to_dict()))
            logger.debug("Publicado en %s [%s] msg=%s", channel, priority.name, msg.message_id)
        else:
            await self._backend.publish(channel, msg)

        self._stats["published"] += 1
        return msg.message_id

    # --------------------------------------------------------
    # Broadcast a múltiples canales
    # --------------------------------------------------------
    async def broadcast(
        self,
        channels: list[str],
        payload: dict[str, Any],
        from_agent: str = "system",
        priority: Priority = Priority.NORMAL,
    ) -> list[str]:
        """Publica el mismo mensaje en múltiples canales."""
        tasks = [
            self.publish(ch, payload, from_agent=from_agent, priority=priority) for ch in channels
        ]
        return list(await asyncio.gather(*tasks))

    # --------------------------------------------------------
    # Subscribe (async generator)
    # --------------------------------------------------------
    async def subscribe(
        self,
        channel: str,
        consumer_name: str | None = None,
        group: str = DEFAULT_CONSUMER_GROUP,
        block_ms: int = BLOCK_TIMEOUT_MS,
    ) -> AsyncIterator[BusMessage]:
        """
        Suscripción a un canal con entrega garantizada (Consumer Groups).

        Usage:
            async for msg in bus.subscribe("agent.explorer.inbox"):
                await process(msg)
                await bus.ack(msg)
        """
        consumer = consumer_name or f"consumer-{uuid.uuid4().hex[:6]}"

        if self._use_redis:
            stream_key = f"antigravity:stream:{channel}"
            # Crear consumer group si no existe
            try:
                await self._backend.xgroup_create(stream_key, group, id="0", mkstream=True)
            except Exception:
                pass  # Ya existe

            while self._running:
                try:
                    results = await self._backend.xreadgroup(
                        groupname=group,
                        consumername=consumer,
                        streams={stream_key: ">"},
                        count=10,
                        block=block_ms,
                    )
                    if results:
                        for _stream, entries in results:
                            for entry_id, data in entries:
                                msg = BusMessage.from_redis_dict(data, stream_id=entry_id)
                                self._stats["consumed"] += 1
                                yield msg
                except asyncio.CancelledError:
                    return
                except Exception as e:
                    logger.error("Error en subscribe %s: %s", channel, e)
                    self._stats["errors"] += 1
                    await asyncio.sleep(1)
        else:
            queue = await self._backend.subscribe_queue(channel)
            while self._running:
                try:
                    msg = await asyncio.wait_for(queue.get(), timeout=block_ms / 1000)
                    self._stats["consumed"] += 1
                    yield msg
                except TimeoutError:
                    continue
                except asyncio.CancelledError:
                    return

    # --------------------------------------------------------
    # ACK (marcar mensaje como procesado)
    # --------------------------------------------------------
    async def ack(
        self,
        message: BusMessage,
        group: str = DEFAULT_CONSUMER_GROUP,
    ) -> None:
        """Confirma el procesamiento de un mensaje (Consumer Group ACK)."""
        if self._use_redis and message.stream_id:
            stream_key = f"antigravity:stream:{message.channel}"
            await self._backend.xack(stream_key, group, message.stream_id)
        elif not self._use_redis:
            await self._backend.ack(message.message_id)

    # --------------------------------------------------------
    # Dead Letter Queue
    # --------------------------------------------------------
    async def send_to_dlq(
        self,
        message: BusMessage,
        reason: str = "max_retries_exceeded",
    ) -> None:
        """Envía un mensaje fallado al DLQ."""
        dlq_payload = {**message.to_dict(), "dlq_reason": reason, "dlq_timestamp": time.time()}

        if self._use_redis:
            await self._backend.xadd(DLQ_STREAM, {"data": json.dumps(dlq_payload)}, maxlen=5000)
        else:
            await self._backend.publish(
                DLQ_STREAM,
                BusMessage.create(
                    channel=DLQ_STREAM,
                    payload=dlq_payload,
                    from_agent=message.from_agent,
                ),
            )

        self._stats["dlq_count"] += 1
        logger.warning("Mensaje enviado a DLQ: %s (razón: %s)", message.message_id, reason)

    # --------------------------------------------------------
    # Cola de prioridad (para task queue)
    # --------------------------------------------------------
    async def enqueue_priority(
        self,
        queue_name: str,
        payload: dict[str, Any],
        priority: Priority = Priority.NORMAL,
        from_agent: str = "system",
    ) -> str:
        """
        Encola una tarea con prioridad usando Redis Sorted Set.
        Score = priority * 1e12 + timestamp (prioridad + FIFO dentro del mismo nivel).
        """
        msg = BusMessage.create(
            channel=queue_name,
            payload=payload,
            from_agent=from_agent,
            priority=priority,
        )
        score = priority.value * 1e12 + msg.timestamp

        if self._use_redis:
            key = f"antigravity:queue:{queue_name}"
            await self._backend.zadd(key, {json.dumps(msg.to_dict()): score})
        else:
            await self._backend.publish(queue_name, msg)

        logger.debug("Encolado en %s [%s] id=%s", queue_name, priority.name, msg.message_id)
        return msg.message_id

    async def dequeue_priority(
        self,
        queue_name: str,
        timeout_seconds: float = 5.0,
    ) -> BusMessage | None:
        """
        Desencola la tarea de mayor prioridad (score más bajo).
        Bloquea hasta timeout_seconds si la cola está vacía.
        """
        if self._use_redis:
            key = f"antigravity:queue:{queue_name}"
            deadline = time.monotonic() + timeout_seconds
            while time.monotonic() < deadline:
                result = await self._backend.zpopmin(key, count=1)
                if result:
                    data_str, _score = result[0]
                    data = json.loads(data_str)
                    return BusMessage(
                        message_id=data["message_id"],
                        channel=data["channel"],
                        payload=data["payload"],
                        from_agent=data["from_agent"],
                        to_agent=data.get("to_agent"),
                        priority=Priority[data["priority"]],
                        timestamp=data["timestamp"],
                        ttl_seconds=data.get("ttl_seconds", 3600),
                    )
                await asyncio.sleep(0.1)
            return None
        else:
            # Fallback: leer desde SQLite
            messages = await self._backend.get_messages(queue_name)
            if messages:
                msg = messages[0]
                await self._backend.ack(msg.message_id)
                return msg
            return None

    async def queue_size(self, queue_name: str) -> int:
        """Retorna el tamaño actual de una cola de prioridad."""
        if self._use_redis:
            key = f"antigravity:queue:{queue_name}"
            return await self._backend.zcard(key)
        else:
            messages = await self._backend.get_messages(queue_name)
            return len(messages)

    # --------------------------------------------------------
    # Heartbeat de agentes
    # --------------------------------------------------------
    async def heartbeat(self, agent_name: str, metadata: dict[str, Any] | None = None) -> None:
        """Publica un heartbeat para indicar que el agente está vivo."""
        await self.publish(
            channel=HEARTBEAT_CHANNEL,
            payload={
                "agent": agent_name,
                "ts": time.time(),
                "metadata": metadata or {},
            },
            from_agent=agent_name,
            priority=Priority.LOW,
            ttl_seconds=60,
        )

    async def get_alive_agents(self, max_age_seconds: float = 30.0) -> list[str]:
        """
        Retorna la lista de agentes que enviaron heartbeat recientemente.
        """
        if not self._use_redis:
            return []

        stream_key = f"antigravity:stream:{HEARTBEAT_CHANNEL}"
        cutoff = time.time() - max_age_seconds
        alive: dict[str, float] = {}

        try:
            entries = await self._backend.xrevrange(stream_key, count=500)
            for _entry_id, data in entries:
                try:
                    payload = json.loads(data.get("payload", "{}"))
                except json.JSONDecodeError:
                    continue
                agent_name = payload.get("agent", "")
                ts = float(payload.get("ts", 0))
                if ts > cutoff and agent_name and agent_name not in alive:
                    alive[agent_name] = ts
        except Exception as e:
            logger.debug("Error leyendo heartbeats: %s", e)

        return list(alive.keys())

    # --------------------------------------------------------
    # A2A Request-Reply (RPC sobre Redis Streams)
    # --------------------------------------------------------
    async def request(
        self,
        from_agent: str,
        to_agent: str,
        question: str,
        context: dict[str, Any] | None = None,
        timeout: float = 60.0,
        priority: Priority = Priority.NORMAL,
        request_type: str = "question",
    ) -> dict[str, Any]:
        """
        Envía una solicitud A2A y espera la respuesta (RPC síncrono sobre el bus).

        Crea un reply_channel efímero, publica el request en el inbox del
        agente destino, y bloquea hasta recibir la respuesta o timeout.

        Args:
            from_agent: Agente que origina la solicitud.
            to_agent: Agente que debe responder.
            question: La pregunta o instrucción.
            context: Contexto adicional para el agente destino.
            timeout: Tiempo máximo de espera en segundos.
            priority: Prioridad del mensaje.
            request_type: Tipo de request (question, review, validate, delegate).

        Returns:
            dict con la respuesta del agente destino.

        Raises:
            TimeoutError: Si no se recibe respuesta dentro del timeout.
        """
        correlation_id = str(uuid.uuid4())
        reply_channel = f"a2a:reply:{correlation_id}"

        # Registrar future para la respuesta
        future: asyncio.Future[dict[str, Any]] = asyncio.get_running_loop().create_future()
        self._pending_replies[correlation_id] = future

        # Publicar request en el inbox del agente destino
        inbox_channel = f"a2a:inbox:{to_agent}"
        msg = BusMessage.create(
            channel=inbox_channel,
            payload={
                "type": request_type,
                "question": question,
                "context": context or {},
            },
            from_agent=from_agent,
            to_agent=to_agent,
            priority=priority,
            ttl_seconds=int(timeout) + 30,
            correlation_id=correlation_id,
            reply_channel=reply_channel,
        )

        if self._use_redis:
            stream_key = f"antigravity:stream:{inbox_channel}"
            await self._backend.xadd(
                stream_key,
                msg.to_redis_dict(),
                maxlen=STREAM_MAXLEN,
                approximate=True,
            )
            await self._backend.publish(inbox_channel, json.dumps(msg.to_dict()))
        else:
            await self._backend.publish(inbox_channel, msg)

        self._stats["published"] += 1
        self._stats.setdefault("a2a_requests", 0)
        self._stats["a2a_requests"] += 1

        logger.info(
            "A2A request: %s → %s (type=%s, corr=%s)",
            from_agent,
            to_agent,
            request_type,
            correlation_id[:8],
        )

        # Esperar la respuesta con timeout
        try:
            result = await asyncio.wait_for(future, timeout=timeout)
            return result
        except TimeoutError:
            self._pending_replies.pop(correlation_id, None)
            logger.warning(
                "A2A timeout: %s → %s (corr=%s, timeout=%.0fs)",
                from_agent,
                to_agent,
                correlation_id[:8],
                timeout,
            )
            raise

    async def reply(
        self,
        original_message: BusMessage,
        response: dict[str, Any],
        status: str = "completed",
    ) -> str:
        """
        Responde a un request A2A.

        Args:
            original_message: Mensaje de request original (contiene correlation_id y reply_channel).
            response: Datos de la respuesta.
            status: Estado de la respuesta (completed, declined, partial, error).

        Returns:
            message_id de la respuesta publicada.
        """
        if not original_message.correlation_id or not original_message.reply_channel:
            raise ValueError("El mensaje no tiene correlation_id o reply_channel para responder")

        reply_msg = BusMessage.create(
            channel=original_message.reply_channel,
            payload={
                "status": status,
                "response": response,
                "request_type": original_message.payload.get("type", "unknown"),
            },
            from_agent=original_message.to_agent or "unknown",
            to_agent=original_message.from_agent,
            priority=original_message.priority,
            ttl_seconds=300,
            correlation_id=original_message.correlation_id,
            reply_channel=original_message.reply_channel,
        )

        if self._use_redis:
            stream_key = f"antigravity:stream:{original_message.reply_channel}"
            await self._backend.xadd(
                stream_key,
                reply_msg.to_redis_dict(),
                maxlen=1000,
                approximate=True,
            )
            await self._backend.publish(
                original_message.reply_channel,
                json.dumps(reply_msg.to_dict()),
            )
        else:
            await self._backend.publish(original_message.reply_channel, reply_msg)

        self._stats["published"] += 1
        self._stats.setdefault("a2a_replies", 0)
        self._stats["a2a_replies"] += 1

        logger.info(
            "A2A reply: %s → %s (status=%s, corr=%s)",
            original_message.to_agent,
            original_message.from_agent,
            status,
            original_message.correlation_id[:8],
        )

        return reply_msg.message_id

    async def subscribe_inbox(
        self,
        agent_name: str,
        handler: "Callable[[BusMessage], Any]",
    ) -> asyncio.Task:
        """
        Suscribe un agente a su inbox A2A.

        El handler recibe cada BusMessage de request entrante.
        El agente debe llamar a bus.reply() para responder.

        Args:
            agent_name: Nombre del agente.
            handler: Callable async que procesa el request entrante.

        Returns:
            asyncio.Task que ejecuta el listener.
        """
        inbox_channel = f"a2a:inbox:{agent_name}"
        self._a2a_handlers[agent_name] = handler

        async def _inbox_listener() -> None:
            if self._use_redis:
                # Suscribirse via Pub/Sub para notificación instantánea
                pubsub = self._backend.pubsub()
                await pubsub.subscribe(inbox_channel)
                try:
                    while self._running:
                        raw = await pubsub.get_message(
                            ignore_subscribe_messages=True,
                            timeout=1.0,
                        )
                        if raw and raw.get("type") == "message":
                            try:
                                data = json.loads(raw["data"])
                                msg = BusMessage(
                                    message_id=data.get("message_id", ""),
                                    channel=data.get("channel", ""),
                                    payload=data.get("payload", {}),
                                    from_agent=data.get("from_agent", ""),
                                    to_agent=data.get("to_agent"),
                                    priority=Priority[data.get("priority", "NORMAL")],
                                    timestamp=data.get("timestamp", 0),
                                    ttl_seconds=data.get("ttl_seconds", 3600),
                                    correlation_id=data.get("correlation_id"),
                                    reply_channel=data.get("reply_channel"),
                                )
                                await handler(msg)
                            except Exception as e:
                                logger.error("Error procesando A2A inbox %s: %s", agent_name, e)
                except asyncio.CancelledError:
                    await pubsub.unsubscribe(inbox_channel)
                    return
            else:
                queue = await self._backend.subscribe_queue(inbox_channel)
                try:
                    while self._running:
                        try:
                            msg = await asyncio.wait_for(queue.get(), timeout=2.0)
                            await handler(msg)
                        except TimeoutError:
                            continue
                except asyncio.CancelledError:
                    return

        task = asyncio.create_task(
            _inbox_listener(),
            name=f"a2a-inbox-{agent_name}",
        )
        self._inbox_tasks[agent_name] = task
        logger.info("A2A inbox registrado para agente '%s'", agent_name)
        return task

    async def _start_reply_listener(self) -> None:
        """
        Listener interno que resuelve futures de request-reply.

        Escucha todos los canales a2a:reply:* via Pub/Sub pattern matching.
        Cuando llega una respuesta, resuelve el Future correspondiente.
        """
        if self._use_redis:
            pubsub = self._backend.pubsub()
            await pubsub.psubscribe("a2a:reply:*")
            try:
                while self._running:
                    raw = await pubsub.get_message(
                        ignore_subscribe_messages=True,
                        timeout=1.0,
                    )
                    if raw and raw.get("type") == "pmessage":
                        try:
                            data = json.loads(raw["data"])
                            corr_id = data.get("correlation_id")
                            if corr_id and corr_id in self._pending_replies:
                                future = self._pending_replies.pop(corr_id)
                                if not future.done():
                                    future.set_result(data.get("payload", {}))
                        except Exception as e:
                            logger.debug("Error procesando reply: %s", e)
            except asyncio.CancelledError:
                await pubsub.punsubscribe("a2a:reply:*")
                return
        else:
            # Fallback SQLite: polling de reply channels
            queue = await self._backend.subscribe_queue("a2a:reply:*")
            try:
                while self._running:
                    try:
                        msg = await asyncio.wait_for(queue.get(), timeout=2.0)
                        corr_id = msg.correlation_id
                        if corr_id and corr_id in self._pending_replies:
                            future = self._pending_replies.pop(corr_id)
                            if not future.done():
                                future.set_result(msg.payload)
                    except TimeoutError:
                        continue
            except asyncio.CancelledError:
                return

    def get_a2a_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del sistema A2A."""
        return {
            "registered_handlers": list(self._a2a_handlers.keys()),
            "pending_replies": len(self._pending_replies),
            "active_inboxes": list(self._inbox_tasks.keys()),
            "a2a_requests": self._stats.get("a2a_requests", 0),
            "a2a_replies": self._stats.get("a2a_replies", 0),
        }

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------
    async def start(self) -> None:
        """Inicia el bus (habilita subscribe + A2A reply listener)."""
        self._running = True
        # Iniciar listener de replies A2A
        self._reply_listener_task = asyncio.create_task(
            self._start_reply_listener(),
            name="a2a-reply-listener",
        )
        logger.info(
            "RedisMessageBus iniciado (backend=%s)", "Redis" if self._use_redis else "SQLite"
        )

    async def stop(self) -> None:
        """Para el bus limpiamente."""
        self._running = False
        if self._listener_task and not self._listener_task.done():
            self._listener_task.cancel()
        # Cancelar reply listener A2A
        if self._reply_listener_task and not self._reply_listener_task.done():
            self._reply_listener_task.cancel()
        # Cancelar inbox listeners A2A
        for task in self._inbox_tasks.values():
            if not task.done():
                task.cancel()
        self._inbox_tasks.clear()
        # Resolver futures pendientes con error
        for corr_id, future in self._pending_replies.items():
            if not future.done():
                future.cancel()
        self._pending_replies.clear()
        if self._use_redis:
            await self._backend.aclose()
        else:
            await self._backend.close()
        logger.info("RedisMessageBus detenido")

    # --------------------------------------------------------
    # Stats & debug
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del bus."""
        return {
            "backend": "redis" if self._use_redis else "sqlite",
            "running": self._running,
            **self._stats,
        }

    async def get_stream_info(self, channel: str) -> dict[str, Any]:
        """Info sobre un stream específico (solo Redis)."""
        if not self._use_redis:
            return {"backend": "sqlite", "channel": channel}

        stream_key = f"antigravity:stream:{channel}"
        try:
            info = await self._backend.xinfo_stream(stream_key)
            return {
                "channel": channel,
                "length": info.get("length", 0),
                "first_entry": info.get("first-entry"),
                "last_entry": info.get("last-entry"),
            }
        except Exception:
            return {"channel": channel, "length": 0}

    @property
    def is_redis(self) -> bool:
        """True si usa Redis real, False si usa SQLite fallback."""
        return self._use_redis


# ============================================================
# Singleton global
# ============================================================
_bus_instance: RedisMessageBus | None = None
_bus_lock = asyncio.Lock()


async def get_message_bus(
    host: str = "localhost",
    port: int = 6379,
) -> RedisMessageBus:
    """
    Obtiene la instancia global del bus (singleton async-safe).
    """
    global _bus_instance
    async with _bus_lock:
        if _bus_instance is None:
            _bus_instance = await RedisMessageBus.create(host=host, port=port)
            await _bus_instance.start()
    return _bus_instance


async def reset_bus() -> None:
    """Reset del singleton (útil para tests)."""
    global _bus_instance
    async with _bus_lock:
        if _bus_instance is not None:
            await _bus_instance.stop()
            _bus_instance = None
