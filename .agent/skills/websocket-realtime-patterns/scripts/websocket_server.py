#!/usr/bin/env python3
"""
WebSocket Server Demo
Servidor WebSocket simple con autenticación y rooms.
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field, asdict
from datetime import datetime
from enum import Enum
import secrets

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# MODELOS
# =============================================================================


class MessageType(Enum):
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    JOIN_ROOM = "join_room"
    LEAVE_ROOM = "leave_room"
    MESSAGE = "message"
    TYPING = "typing"
    PRESENCE = "presence"
    ERROR = "error"
    ACK = "ack"


@dataclass
class User:
    id: str
    username: str
    is_authenticated: bool = False


@dataclass
class WebSocketMessage:
    type: MessageType
    payload: dict = field(default_factory=dict)
    room: str | None = None
    sender_id: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    message_id: str = field(default_factory=lambda: secrets.token_hex(8))

    def to_json(self) -> str:
        data = asdict(self)
        data["type"] = self.type.value
        return json.dumps(data)

    @classmethod
    def from_json(cls, data: str) -> "WebSocketMessage":
        parsed = json.loads(data)
        parsed["type"] = MessageType(parsed["type"])
        return cls(**parsed)


@dataclass
class Connection:
    user: User
    rooms: set = field(default_factory=set)
    connected_at: str = field(default_factory=lambda: datetime.now().isoformat())


# =============================================================================
# WEBSOCKET MANAGER
# =============================================================================


class WebSocketManager:
    """Gestor de conexiones WebSocket."""

    def __init__(self):
        self.connections: dict[str, Connection] = {}
        self.rooms: dict[str, set[str]] = {}  # room_id -> set of user_ids
        self._message_handlers: dict[MessageType, callable] = {}

    def register_handler(self, msg_type: MessageType, handler: callable):
        """Registra un handler para un tipo de mensaje."""
        self._message_handlers[msg_type] = handler

    async def connect(self, user: User) -> Connection:
        """Registra una nueva conexión."""
        conn = Connection(user=user)
        self.connections[user.id] = conn

        logger.info(f"User {user.username} connected. Total: {len(self.connections)}")

        # Notificar a todos sobre la nueva conexión
        await self.broadcast(
            WebSocketMessage(
                type=MessageType.PRESENCE,
                payload={"user_id": user.id, "username": user.username, "status": "online"},
                sender_id=user.id,
            )
        )

        return conn

    async def disconnect(self, user_id: str):
        """Desconecta un usuario."""
        if user_id not in self.connections:
            return

        conn = self.connections[user_id]

        # Salir de todas las rooms
        for room_id in list(conn.rooms):
            await self.leave_room(user_id, room_id)

        del self.connections[user_id]

        logger.info(f"User {conn.user.username} disconnected. Total: {len(self.connections)}")

        # Notificar desconexión
        await self.broadcast(
            WebSocketMessage(
                type=MessageType.PRESENCE,
                payload={"user_id": user_id, "status": "offline"},
                sender_id=user_id,
            )
        )

    async def join_room(self, user_id: str, room_id: str):
        """Añade un usuario a una room."""
        if user_id not in self.connections:
            return

        if room_id not in self.rooms:
            self.rooms[room_id] = set()

        self.rooms[room_id].add(user_id)
        self.connections[user_id].rooms.add(room_id)

        logger.info(f"User {user_id} joined room {room_id}")

        # Notificar a la room
        await self.broadcast_to_room(
            room_id,
            WebSocketMessage(
                type=MessageType.JOIN_ROOM,
                payload={"user_id": user_id, "room_id": room_id},
                room=room_id,
                sender_id=user_id,
            ),
        )

    async def leave_room(self, user_id: str, room_id: str):
        """Remueve un usuario de una room."""
        if room_id in self.rooms:
            self.rooms[room_id].discard(user_id)
            if not self.rooms[room_id]:
                del self.rooms[room_id]

        if user_id in self.connections:
            self.connections[user_id].rooms.discard(room_id)

        logger.info(f"User {user_id} left room {room_id}")

        # Notificar a la room
        await self.broadcast_to_room(
            room_id,
            WebSocketMessage(
                type=MessageType.LEAVE_ROOM,
                payload={"user_id": user_id, "room_id": room_id},
                room=room_id,
                sender_id=user_id,
            ),
        )

    async def send_to_user(self, user_id: str, message: WebSocketMessage):
        """Envía mensaje a un usuario específico."""
        if user_id in self.connections:
            # En producción, aquí enviarías por el websocket real
            logger.info(f"-> {user_id}: {message.type.value}")

    async def broadcast(self, message: WebSocketMessage, exclude: str | None = None):
        """Envía mensaje a todos los usuarios conectados."""
        for user_id in self.connections:
            if user_id != exclude:
                await self.send_to_user(user_id, message)

    async def broadcast_to_room(
        self, room_id: str, message: WebSocketMessage, exclude: str | None = None
    ):
        """Envía mensaje a todos los usuarios de una room."""
        if room_id not in self.rooms:
            return

        for user_id in self.rooms[room_id]:
            if user_id != exclude:
                await self.send_to_user(user_id, message)

    async def handle_message(self, user_id: str, raw_message: str):
        """Procesa un mensaje entrante."""
        try:
            message = WebSocketMessage.from_json(raw_message)
            message.sender_id = user_id

            handler = self._message_handlers.get(message.type)
            if handler:
                await handler(user_id, message)
            else:
                logger.warning(f"No handler for message type: {message.type}")

        except json.JSONDecodeError:
            await self.send_to_user(
                user_id, WebSocketMessage(type=MessageType.ERROR, payload={"error": "Invalid JSON"})
            )
        except Exception as e:
            logger.error(f"Error handling message: {e}")
            await self.send_to_user(
                user_id, WebSocketMessage(type=MessageType.ERROR, payload={"error": str(e)})
            )

    def get_room_users(self, room_id: str) -> list[str]:
        """Obtiene usuarios de una room."""
        return list(self.rooms.get(room_id, set()))

    def get_user_rooms(self, user_id: str) -> list[str]:
        """Obtiene rooms de un usuario."""
        if user_id in self.connections:
            return list(self.connections[user_id].rooms)
        return []

    def get_stats(self) -> dict:
        """Obtiene estadísticas del servidor."""
        return {
            "total_connections": len(self.connections),
            "total_rooms": len(self.rooms),
            "rooms": {room_id: len(users) for room_id, users in self.rooms.items()},
        }


# =============================================================================
# DEMO
# =============================================================================


async def demo():
    """Demostración del WebSocket Manager."""
    print("\n" + "=" * 60)
    print("WEBSOCKET SERVER DEMO")
    print("=" * 60)

    manager = WebSocketManager()

    # Registrar handlers
    async def handle_join_room(user_id: str, message: WebSocketMessage):
        room_id = message.payload.get("room_id")
        if room_id:
            await manager.join_room(user_id, room_id)

    async def handle_leave_room(user_id: str, message: WebSocketMessage):
        room_id = message.payload.get("room_id")
        if room_id:
            await manager.leave_room(user_id, room_id)

    async def handle_message(user_id: str, message: WebSocketMessage):
        # Broadcast a la room o a todos
        if message.room:
            await manager.broadcast_to_room(message.room, message, exclude=user_id)
        else:
            await manager.broadcast(message, exclude=user_id)

        # ACK al sender
        await manager.send_to_user(
            user_id,
            WebSocketMessage(type=MessageType.ACK, payload={"message_id": message.message_id}),
        )

    manager.register_handler(MessageType.JOIN_ROOM, handle_join_room)
    manager.register_handler(MessageType.LEAVE_ROOM, handle_leave_room)
    manager.register_handler(MessageType.MESSAGE, handle_message)

    # Simular conexiones
    print("\n--- Simulando conexiones ---")

    user1 = User(id="user-1", username="alice", is_authenticated=True)
    user2 = User(id="user-2", username="bob", is_authenticated=True)
    user3 = User(id="user-3", username="charlie", is_authenticated=True)

    await manager.connect(user1)
    await manager.connect(user2)
    await manager.connect(user3)

    print(f"\nStats: {manager.get_stats()}")

    # Simular rooms
    print("\n--- Simulando rooms ---")

    await manager.join_room("user-1", "room-general")
    await manager.join_room("user-2", "room-general")
    await manager.join_room("user-1", "room-private")
    await manager.join_room("user-3", "room-general")

    print(f"\nStats: {manager.get_stats()}")
    print(f"Users in room-general: {manager.get_room_users('room-general')}")
    print(f"Rooms for user-1: {manager.get_user_rooms('user-1')}")

    # Simular mensajes
    print("\n--- Simulando mensajes ---")

    # Mensaje a room
    await manager.handle_message(
        "user-1",
        json.dumps(
            {"type": "message", "payload": {"text": "Hola a todos!"}, "room": "room-general"}
        ),
    )

    # Desconexión
    print("\n--- Simulando desconexión ---")
    await manager.disconnect("user-2")

    print(f"\nStats finales: {manager.get_stats()}")

    # Ejemplo de mensaje serializado
    print("\n--- Ejemplo de mensaje serializado ---")
    msg = WebSocketMessage(
        type=MessageType.MESSAGE,
        payload={"text": "Hello World", "mentions": ["user-2"]},
        room="room-general",
        sender_id="user-1",
    )
    print(f"JSON: {msg.to_json()}")

    print("\n" + "=" * 60)
    print("Demo completada")
    print("=" * 60)


def main():
    """Entry point."""
    asyncio.run(demo())


if __name__ == "__main__":
    main()
