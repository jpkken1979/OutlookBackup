#!/usr/bin/env python3
"""
Gestor de conexiones WebSocket para el Antigravity Gateway.
============================================================

Proporciona comunicacion bidireccional en tiempo real entre clientes y el gateway
mediante WebSocket (aiohttp). Soporta suscripciones a canales con patron glob,
heartbeat, rate limiting por cliente y broadcasting de eventos.

Protocolo de mensajes (JSON):

    Cliente -> Servidor:
        {"type": "subscribe", "channels": ["agent.*", "log.entry"]}
        {"type": "unsubscribe", "channels": ["log.entry"]}
        {"type": "ping"}

    Servidor -> Cliente:
        {"type": "event", "channel": "agent.completed", "data": {...}, "timestamp": "..."}
        {"type": "subscribed", "channels": ["agent.*"]}
        {"type": "pong"}
        {"type": "error", "message": "..."}

Uso:
    from gateway_websocket import setup_websocket, broadcast_event, get_ws_manager

    await setup_websocket(app)
    await broadcast_event("agent.completed", {"agent": "explorer", "result": "ok"})
"""

from __future__ import annotations

import asyncio
import fnmatch
import json
import logging
import time
import uuid
from dataclasses import dataclass, field

try:
    from datetime import datetime, UTC
except ImportError:  # Python < 3.11
    from datetime import datetime

    UTC = UTC
from typing import Any

from aiohttp import web, WSMsgType

try:
    from .security_utils import (
        DEFAULT_CORS_ORIGINS,
        is_origin_allowed,
    )
except ImportError:
    from security_utils import (  # type: ignore[no-redef]
        DEFAULT_CORS_ORIGINS,
        is_origin_allowed,
    )

log = logging.getLogger("antigravity-gateway.websocket")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
MAX_CLIENTS = 200
MAX_MESSAGES_PER_MINUTE = 100
MAX_SUBSCRIPTIONS_PER_CLIENT = 50
HEARTBEAT_INTERVAL_SECONDS = 30.0
CLEANUP_INTERVAL_SECONDS = 60.0

# Canales validos (prefijos reconocidos por el sistema)
VALID_CHANNEL_PREFIXES = (
    "agent.",
    "skill.",
    "task.",
    "log.",
    "health.",
    "memory.",
)


# ---------------------------------------------------------------------------
# Modelo de cliente conectado
# ---------------------------------------------------------------------------
@dataclass
class ConnectedClient:
    """Representa un cliente WebSocket conectado."""

    client_id: str
    ws: web.WebSocketResponse
    subscriptions: set[str] = field(default_factory=set)
    connected_at: float = field(default_factory=time.monotonic)
    last_message_at: float = field(default_factory=time.monotonic)
    message_count: int = 0
    message_window_start: float = field(default_factory=time.monotonic)
    remote: str = ""

    def is_rate_limited(self) -> bool:
        """Verifica si el cliente excedio el limite de mensajes por minuto."""
        now = time.monotonic()
        # Reiniciar ventana si paso mas de un minuto
        if now - self.message_window_start >= 60.0:
            self.message_count = 0
            self.message_window_start = now
        return self.message_count >= MAX_MESSAGES_PER_MINUTE

    def record_message(self) -> None:
        """Registra un mensaje entrante para rate limiting."""
        now = time.monotonic()
        if now - self.message_window_start >= 60.0:
            self.message_count = 0
            self.message_window_start = now
        self.message_count += 1
        self.last_message_at = now


def _match_channel(pattern: str, channel: str) -> bool:
    """Verifica si un canal coincide con un patron glob.

    Soporta patrones como 'agent.*' que matchean 'agent.started',
    'agent.completed', etc. Tambien soporta '**' para match profundo
    y patrones exactos.

    Args:
        pattern: Patron glob (ej: 'agent.*', 'task.progress', '*').
        channel: Canal a verificar (ej: 'agent.started').

    Returns:
        True si el canal coincide con el patron.
    """
    if pattern == "*":
        return True
    return fnmatch.fnmatch(channel, pattern)


def _validate_channel(channel: str) -> bool:
    """Valida que un canal o patron tenga un prefijo reconocido.

    Args:
        channel: Canal o patron a validar.

    Returns:
        True si el canal es valido.
    """
    if channel == "*":
        return True
    # Permitir patrones glob que comiencen con prefijo valido
    base = channel.split("*")[0].rstrip(".")
    if not base:
        return True  # Solo wildcard
    return any(channel.startswith(prefix) for prefix in VALID_CHANNEL_PREFIXES)


# ---------------------------------------------------------------------------
# WebSocketManager
# ---------------------------------------------------------------------------
class WebSocketManager:
    """Gestor de conexiones WebSocket para el Gateway.

    Administra el ciclo de vida de conexiones WebSocket, suscripciones
    a canales de eventos, broadcasting y rate limiting.

    Atributos:
        clients: Diccionario de clientes conectados por ID.
        cors_origins: Lista de origenes CORS permitidos.
    """

    def __init__(self, cors_origins: list[str] | None = None) -> None:
        """Inicializa el gestor de WebSocket.

        Args:
            cors_origins: Lista de origenes CORS permitidos.
                Si es None, usa los origenes por defecto.
        """
        self.clients: dict[str, ConnectedClient] = {}
        self.cors_origins: list[str] = cors_origins or DEFAULT_CORS_ORIGINS.copy()
        self._cleanup_task: asyncio.Task[None] | None = None
        self._event_callbacks: list[Any] = []
        self._lock = asyncio.Lock()

    @property
    def client_count(self) -> int:
        """Numero de clientes conectados actualmente."""
        return len(self.clients)

    async def start(self) -> None:
        """Inicia tareas en background del gestor (limpieza periodica)."""
        if self._cleanup_task is None or self._cleanup_task.done():
            self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
            log.info("WebSocketManager iniciado")

    async def stop(self) -> None:
        """Detiene el gestor y cierra todas las conexiones."""
        if self._cleanup_task is not None:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
            self._cleanup_task = None

        # Cerrar todas las conexiones
        async with self._lock:
            for client in list(self.clients.values()):
                try:
                    await client.ws.close(
                        code=WSMsgType.CLOSE,  # type: ignore[arg-type]
                        message=b"Server shutting down",
                    )
                except Exception:
                    pass
            self.clients.clear()

        log.info("WebSocketManager detenido, todas las conexiones cerradas")

    async def register_client(
        self,
        ws: web.WebSocketResponse,
        remote: str = "",
    ) -> ConnectedClient | None:
        """Registra un nuevo cliente WebSocket.

        Args:
            ws: Respuesta WebSocket de aiohttp.
            remote: IP remota del cliente.

        Returns:
            El cliente conectado, o None si se alcanzo el limite.
        """
        if len(self.clients) >= MAX_CLIENTS:
            log.warning(
                "Limite de clientes WebSocket alcanzado (%d/%d)",
                len(self.clients),
                MAX_CLIENTS,
            )
            return None

        client_id = uuid.uuid4().hex[:12]
        client = ConnectedClient(
            client_id=client_id,
            ws=ws,
            remote=remote,
        )

        async with self._lock:
            self.clients[client_id] = client

        log.info(
            "Cliente WebSocket registrado: id=%s remote=%s (total: %d)",
            client_id,
            remote,
            len(self.clients),
        )
        return client

    async def unregister_client(self, client_id: str) -> None:
        """Elimina un cliente del registro.

        Args:
            client_id: ID del cliente a eliminar.
        """
        async with self._lock:
            client = self.clients.pop(client_id, None)

        if client is not None:
            log.info(
                "Cliente WebSocket eliminado: id=%s (total: %d)",
                client_id,
                len(self.clients),
            )

    def subscribe(self, client_id: str, channels: list[str]) -> list[str]:
        """Suscribe un cliente a uno o mas canales.

        Args:
            client_id: ID del cliente.
            channels: Lista de canales o patrones glob.

        Returns:
            Lista de canales efectivamente suscritos.
        """
        client = self.clients.get(client_id)
        if client is None:
            return []

        added: list[str] = []
        for channel in channels:
            if not _validate_channel(channel):
                log.warning(
                    "Canal invalido ignorado: '%s' (client=%s)",
                    channel,
                    client_id,
                )
                continue
            if len(client.subscriptions) >= MAX_SUBSCRIPTIONS_PER_CLIENT:
                log.warning(
                    "Limite de suscripciones alcanzado para client=%s (%d)",
                    client_id,
                    MAX_SUBSCRIPTIONS_PER_CLIENT,
                )
                break
            client.subscriptions.add(channel)
            added.append(channel)

        return added

    def unsubscribe(self, client_id: str, channels: list[str]) -> list[str]:
        """Desuscribe un cliente de uno o mas canales.

        Args:
            client_id: ID del cliente.
            channels: Lista de canales a remover.

        Returns:
            Lista de canales efectivamente removidos.
        """
        client = self.clients.get(client_id)
        if client is None:
            return []

        removed: list[str] = []
        for channel in channels:
            if channel in client.subscriptions:
                client.subscriptions.discard(channel)
                removed.append(channel)

        return removed

    async def broadcast(self, channel: str, data: dict[str, Any]) -> int:
        """Emite un evento a todos los clientes suscritos al canal.

        Args:
            channel: Canal del evento (ej: 'agent.completed').
            data: Datos del evento.

        Returns:
            Numero de clientes que recibieron el evento.
        """
        message = {
            "type": "event",
            "channel": channel,
            "data": data,
            "timestamp": datetime.now(tz=UTC).isoformat(),
        }
        payload = json.dumps(message)

        sent_count = 0
        dead_clients: list[str] = []

        for client_id, client in list(self.clients.items()):
            # Verificar si el cliente tiene una suscripcion que matchee
            if not any(_match_channel(pattern, channel) for pattern in client.subscriptions):
                continue

            try:
                if not client.ws.closed:
                    await client.ws.send_str(payload)
                    sent_count += 1
                else:
                    dead_clients.append(client_id)
            except (ConnectionResetError, ConnectionAbortedError, OSError):
                dead_clients.append(client_id)
            except Exception as exc:
                log.warning(
                    "Error enviando a client=%s: %s",
                    client_id,
                    exc,
                )
                dead_clients.append(client_id)

        # Limpiar clientes muertos
        for cid in dead_clients:
            await self.unregister_client(cid)

        return sent_count

    async def send_to_client(
        self,
        client_id: str,
        message: dict[str, Any],
    ) -> bool:
        """Envia un mensaje directo a un cliente especifico.

        Args:
            client_id: ID del cliente destino.
            message: Mensaje a enviar.

        Returns:
            True si el mensaje fue enviado exitosamente.
        """
        client = self.clients.get(client_id)
        if client is None or client.ws.closed:
            return False

        try:
            await client.ws.send_json(message)
            return True
        except Exception as exc:
            log.warning("Error enviando a client=%s: %s", client_id, exc)
            await self.unregister_client(client_id)
            return False

    def get_stats(self) -> dict[str, Any]:
        """Retorna estadisticas del gestor WebSocket.

        Returns:
            Diccionario con metricas del gestor.
        """
        now = time.monotonic()
        client_details = []
        for cid, client in self.clients.items():
            client_details.append(
                {
                    "client_id": cid,
                    "remote": client.remote,
                    "subscriptions": sorted(client.subscriptions),
                    "connected_seconds": round(now - client.connected_at, 1),
                    "messages_sent": client.message_count,
                }
            )

        all_channels: set[str] = set()
        for client in self.clients.values():
            all_channels.update(client.subscriptions)

        return {
            "connected_clients": len(self.clients),
            "max_clients": MAX_CLIENTS,
            "unique_channels": sorted(all_channels),
            "clients": client_details,
        }

    async def _periodic_cleanup(self) -> None:
        """Tarea periodica para limpiar conexiones muertas."""
        while True:
            try:
                await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)
                dead: list[str] = []
                for cid, client in list(self.clients.items()):
                    if client.ws.closed:
                        dead.append(cid)
                for cid in dead:
                    await self.unregister_client(cid)
                if dead:
                    log.info(
                        "Limpieza WebSocket: %d conexiones muertas eliminadas",
                        len(dead),
                    )
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.warning("Error en limpieza WebSocket: %s", exc)


# ---------------------------------------------------------------------------
# Singleton
# ---------------------------------------------------------------------------
_ws_manager: WebSocketManager | None = None
_ws_manager_lock = asyncio.Lock()


def get_ws_manager() -> WebSocketManager:
    """Obtener instancia singleton del WebSocket manager.

    Returns:
        La instancia global de WebSocketManager.
    """
    global _ws_manager
    if _ws_manager is None:
        _ws_manager = WebSocketManager()
    return _ws_manager


# ---------------------------------------------------------------------------
# Handler aiohttp
# ---------------------------------------------------------------------------
async def websocket_handler(request: web.Request) -> web.WebSocketResponse:
    """Handler para conexiones WebSocket en /v1/ws.

    Gestiona el ciclo de vida completo de una conexion WebSocket:
    preparacion, validacion CORS, registro, procesamiento de mensajes
    y limpieza al desconectar.

    Args:
        request: Request HTTP de aiohttp (upgrade a WebSocket).

    Returns:
        Respuesta WebSocket de aiohttp.
    """
    manager = get_ws_manager()

    # Validar origen CORS
    origin = request.headers.get("Origin", "")
    if origin and not is_origin_allowed(origin, manager.cors_origins):
        log.warning("WebSocket rechazado por CORS: origin=%s", origin)
        return web.Response(  # type: ignore[return-value]
            status=403,
            text="Origin not allowed",
        )

    ws = web.WebSocketResponse(
        heartbeat=HEARTBEAT_INTERVAL_SECONDS,
        max_msg_size=64 * 1024,  # 64KB max por mensaje
    )
    await ws.prepare(request)

    remote = request.remote or "unknown"
    client = await manager.register_client(ws, remote=remote)

    if client is None:
        await ws.send_json(
            {
                "type": "error",
                "message": "Limite de conexiones alcanzado",
            }
        )
        await ws.close()
        return ws

    # Enviar confirmacion de conexion
    await ws.send_json(
        {
            "type": "connected",
            "client_id": client.client_id,
            "heartbeat_interval": HEARTBEAT_INTERVAL_SECONDS,
            "max_subscriptions": MAX_SUBSCRIPTIONS_PER_CLIENT,
            "max_messages_per_minute": MAX_MESSAGES_PER_MINUTE,
        }
    )

    try:
        async for msg in ws:
            if msg.type == WSMsgType.TEXT:
                await _handle_text_message(manager, client, msg.data)
            elif msg.type == WSMsgType.BINARY:
                # Intentar decodificar binary como UTF-8 JSON
                try:
                    text = msg.data.decode("utf-8")
                    await _handle_text_message(manager, client, text)
                except UnicodeDecodeError:
                    await ws.send_json(
                        {
                            "type": "error",
                            "message": "Mensajes binarios deben ser JSON UTF-8",
                        }
                    )
            elif msg.type == WSMsgType.ERROR:
                log.warning(
                    "WebSocket error client=%s: %s",
                    client.client_id,
                    ws.exception(),
                )
                break
    except asyncio.CancelledError:
        pass
    except Exception as exc:
        log.warning(
            "Error inesperado en WebSocket client=%s: %s",
            client.client_id,
            exc,
        )
    finally:
        await manager.unregister_client(client.client_id)

    return ws


async def _handle_text_message(
    manager: WebSocketManager,
    client: ConnectedClient,
    raw: str,
) -> None:
    """Procesa un mensaje de texto de un cliente WebSocket.

    Args:
        manager: Gestor de WebSocket.
        client: Cliente que envio el mensaje.
        raw: Mensaje en texto plano (se espera JSON).
    """
    # Rate limiting
    if client.is_rate_limited():
        await client.ws.send_json(
            {
                "type": "error",
                "message": (
                    f"Rate limit excedido ({MAX_MESSAGES_PER_MINUTE} msg/min). "
                    "Espera antes de enviar mas mensajes."
                ),
            }
        )
        return

    client.record_message()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        await client.ws.send_json(
            {
                "type": "error",
                "message": "JSON invalido",
            }
        )
        return

    if not isinstance(data, dict):
        await client.ws.send_json(
            {
                "type": "error",
                "message": "Se espera un objeto JSON",
            }
        )
        return

    msg_type = data.get("type", "")

    if msg_type == "subscribe":
        channels = data.get("channels", [])
        if not isinstance(channels, list):
            await client.ws.send_json(
                {
                    "type": "error",
                    "message": "'channels' debe ser una lista",
                }
            )
            return
        added = manager.subscribe(client.client_id, channels)
        await client.ws.send_json(
            {
                "type": "subscribed",
                "channels": sorted(client.subscriptions),
            }
        )
        log.info(
            "Client=%s suscrito a %d canales: %s",
            client.client_id,
            len(added),
            added,
        )

    elif msg_type == "unsubscribe":
        channels = data.get("channels", [])
        if not isinstance(channels, list):
            await client.ws.send_json(
                {
                    "type": "error",
                    "message": "'channels' debe ser una lista",
                }
            )
            return
        removed = manager.unsubscribe(client.client_id, channels)
        await client.ws.send_json(
            {
                "type": "unsubscribed",
                "channels": sorted(client.subscriptions),
                "removed": removed,
            }
        )

    elif msg_type == "ping":
        await client.ws.send_json(
            {
                "type": "pong",
                "timestamp": datetime.now(tz=UTC).isoformat(),
            }
        )

    else:
        await client.ws.send_json(
            {
                "type": "error",
                "message": f"Tipo de mensaje desconocido: '{msg_type}'",
            }
        )


# ---------------------------------------------------------------------------
# Funciones de integracion con aiohttp
# ---------------------------------------------------------------------------
async def _on_startup(app: web.Application) -> None:
    """Hook de startup para iniciar el WebSocketManager."""
    manager = get_ws_manager()
    # Heredar CORS del app si esta disponible
    cors_origins = app.get("cors_origins")
    if cors_origins is not None:
        manager.cors_origins = cors_origins
    await manager.start()
    log.info("WebSocket endpoint registrado en /v1/ws")


async def _on_shutdown(app: web.Application) -> None:
    """Hook de shutdown para detener el WebSocketManager."""
    manager = get_ws_manager()
    await manager.stop()


async def setup_websocket(app: web.Application) -> None:
    """Registra el endpoint WebSocket en la app aiohttp.

    Agrega la ruta /v1/ws, hooks de startup/shutdown y almacena
    la referencia al manager en la app.

    Args:
        app: Aplicacion aiohttp donde registrar el WebSocket.
    """
    app.router.add_get("/v1/ws", websocket_handler)
    app.on_startup.append(_on_startup)
    app.on_shutdown.append(_on_shutdown)
    app["ws_manager"] = get_ws_manager()
    log.info("WebSocket configurado para /v1/ws")


# ---------------------------------------------------------------------------
# Funcion de broadcasting publica
# ---------------------------------------------------------------------------
async def broadcast_event(channel: str, data: dict[str, Any]) -> None:
    """Emitir evento a todos los clientes suscritos.

    Funcion de conveniencia que usa el singleton del WebSocketManager.
    Tambien emite al EventBus si esta disponible para integrar con SSE.

    Args:
        channel: Canal del evento (ej: 'agent.completed').
        data: Datos del evento a emitir.
    """
    manager = get_ws_manager()
    sent = await manager.broadcast(channel, data)

    if sent > 0:
        log.debug(
            "Broadcast WebSocket: channel=%s enviado a %d clientes",
            channel,
            sent,
        )

    # Integrar con EventBus si esta disponible
    try:
        from .gateway_events import get_event_bus

        bus = get_event_bus()
        await bus.emit(channel, data, source="websocket")
    except ImportError:
        pass
    except Exception as exc:
        log.debug("No se pudo emitir al EventBus: %s", exc)
