#!/usr/bin/env python3
"""
GraphQL Subscriptions Demo

Este script demuestra patrones de GraphQL Subscriptions incluyendo:
- PubSub para eventos
- Subscriptions con filtros
- Typing indicators
- Presencia online

Uso:
    python subscriptions_demo.py --demo basic
    python subscriptions_demo.py --demo chat
    python subscriptions_demo.py --demo presence
"""

import argparse
import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from collections.abc import Callable, Iterator
from uuid import uuid4

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class Message:
    """Mensaje de chat."""

    id: str
    room_id: str
    author_id: str
    author_name: str
    content: str
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class User:
    """Usuario."""

    id: str
    name: str
    status: str = "offline"
    last_seen: datetime | None = None


@dataclass
class TypingEvent:
    """Evento de usuario escribiendo."""

    room_id: str
    user_id: str
    user_name: str
    is_typing: bool


class PubSub:
    """
    Sistema PubSub en memoria para demostración.

    En producción, usar graphql-subscriptions con Redis
    para soporte multi-servidor.
    """

    def __init__(self) -> None:
        self.subscriptions: dict[str, list[Callable]] = {}
        self._lock = threading.Lock()
        logger.info("PubSub inicializado")

    def subscribe(self, channel: str, callback: Callable) -> str:
        """Suscribirse a un canal."""
        subscription_id = str(uuid4())[:8]

        with self._lock:
            if channel not in self.subscriptions:
                self.subscriptions[channel] = []
            self.subscriptions[channel].append((subscription_id, callback))

        logger.debug(f"Suscripción {subscription_id} a canal '{channel}'")
        return subscription_id

    def unsubscribe(self, channel: str, subscription_id: str) -> None:
        """Cancelar suscripción."""
        with self._lock:
            if channel in self.subscriptions:
                self.subscriptions[channel] = [
                    (sid, cb) for sid, cb in self.subscriptions[channel] if sid != subscription_id
                ]
        logger.debug(f"Suscripción {subscription_id} cancelada de '{channel}'")

    def publish(self, channel: str, payload: Any) -> int:
        """Publicar mensaje a un canal."""
        with self._lock:
            subscribers = self.subscriptions.get(channel, [])

        count = 0
        for subscription_id, callback in subscribers:
            try:
                callback(payload)
                count += 1
            except Exception as e:
                logger.error(f"Error en suscriptor {subscription_id}: {e}")

        logger.debug(f"Publicado a '{channel}': {count} suscriptores notificados")
        return count

    def async_iterator(self, channel: str) -> "AsyncIterator":
        """Obtener iterador asíncrono para un canal."""
        return AsyncIterator(self, channel)


class AsyncIterator:
    """Iterador para subscriptions de GraphQL."""

    def __init__(self, pubsub: PubSub, channel: str) -> None:
        self.pubsub = pubsub
        self.channel = channel
        self.queue: list[Any] = []
        self.subscription_id = pubsub.subscribe(channel, self._on_message)
        self._closed = False

    def _on_message(self, payload: Any) -> None:
        """Callback cuando llega un mensaje."""
        if not self._closed:
            self.queue.append(payload)

    def __iter__(self) -> Iterator[Any]:
        while not self._closed:
            if self.queue:
                yield self.queue.pop(0)
            else:
                time.sleep(0.1)

    def close(self) -> None:
        """Cerrar el iterador."""
        self._closed = True
        self.pubsub.unsubscribe(self.channel, self.subscription_id)


class ChatService:
    """Servicio de chat con subscriptions."""

    def __init__(self, pubsub: PubSub) -> None:
        self.pubsub = pubsub
        self.rooms: dict[str, list[Message]] = {}
        self.users: dict[str, User] = {}
        self.online_users: set[str] = set()
        self.typing_users: dict[str, dict[str, datetime]] = {}  # room_id -> {user_id: timestamp}
        logger.info("ChatService inicializado")

    def create_user(self, user_id: str, name: str) -> User:
        """Crear usuario."""
        user = User(id=user_id, name=name)
        self.users[user_id] = user
        return user

    def user_connect(self, user_id: str) -> None:
        """Usuario se conecta."""
        if user_id in self.users:
            self.users[user_id].status = "online"
            self.online_users.add(user_id)

            self.pubsub.publish("PRESENCE_CHANGED", {"user_id": user_id, "is_online": True})
            logger.info(f"Usuario {user_id} conectado")

    def user_disconnect(self, user_id: str) -> None:
        """Usuario se desconecta."""
        if user_id in self.users:
            self.users[user_id].status = "offline"
            self.users[user_id].last_seen = datetime.now()
            self.online_users.discard(user_id)

            self.pubsub.publish("PRESENCE_CHANGED", {"user_id": user_id, "is_online": False})
            logger.info(f"Usuario {user_id} desconectado")

    def send_message(self, room_id: str, author_id: str, content: str) -> Message:
        """Enviar mensaje a una sala."""
        author = self.users.get(author_id)
        if not author:
            raise ValueError(f"Usuario {author_id} no encontrado")

        message = Message(
            id=str(uuid4())[:8],
            room_id=room_id,
            author_id=author_id,
            author_name=author.name,
            content=content,
        )

        if room_id not in self.rooms:
            self.rooms[room_id] = []
        self.rooms[room_id].append(message)

        # Publicar a suscriptores
        self.pubsub.publish(f"MESSAGE_ADDED_{room_id}", message)

        # Limpiar typing indicator
        self.set_typing(room_id, author_id, False)

        logger.info(f"Mensaje enviado en sala {room_id} por {author.name}")
        return message

    def set_typing(self, room_id: str, user_id: str, is_typing: bool) -> None:
        """Establecer estado de escritura."""
        user = self.users.get(user_id)
        if not user:
            return

        if room_id not in self.typing_users:
            self.typing_users[room_id] = {}

        if is_typing:
            self.typing_users[room_id][user_id] = datetime.now()
        else:
            self.typing_users[room_id].pop(user_id, None)

        event = TypingEvent(
            room_id=room_id, user_id=user_id, user_name=user.name, is_typing=is_typing
        )

        self.pubsub.publish(f"TYPING_{room_id}", event)

    def get_messages(self, room_id: str, limit: int = 50) -> list[Message]:
        """Obtener mensajes de una sala."""
        messages = self.rooms.get(room_id, [])
        return messages[-limit:]

    def get_online_users(self) -> list[User]:
        """Obtener usuarios online."""
        return [self.users[uid] for uid in self.online_users if uid in self.users]


def demo_basic_subscriptions() -> None:
    """Demostrar subscriptions básicas."""
    logger.info("=== Demo: Subscriptions Básicas ===")

    pubsub = PubSub()

    print("\n1. Creando suscriptores...")

    received_messages = []

    def on_message(payload):
        received_messages.append(payload)
        print(f"   Recibido: {payload}")

    # Suscribirse a diferentes canales
    sub1 = pubsub.subscribe("channel-1", on_message)
    pubsub.subscribe("channel-1", on_message)
    pubsub.subscribe("channel-2", on_message)

    print("   - 2 suscriptores en 'channel-1'")
    print("   - 1 suscriptor en 'channel-2'")

    print("\n2. Publicando mensajes...")

    count1 = pubsub.publish("channel-1", {"type": "update", "value": 42})
    print(f"   - Publicado a 'channel-1': {count1} notificados")

    count2 = pubsub.publish("channel-2", {"type": "alert", "message": "Hello"})
    print(f"   - Publicado a 'channel-2': {count2} notificados")

    print("\n3. Cancelando suscripción...")
    pubsub.unsubscribe("channel-1", sub1)

    count3 = pubsub.publish("channel-1", {"type": "update", "value": 100})
    print(f"   - Publicado a 'channel-1': {count3} notificados (uno menos)")

    print(f"\n4. Total mensajes recibidos: {len(received_messages)}")


def demo_chat_subscriptions() -> None:
    """Demostrar chat con subscriptions."""
    logger.info("=== Demo: Chat en Tiempo Real ===")

    pubsub = PubSub()
    chat = ChatService(pubsub)

    # Crear usuarios
    print("\n1. Creando usuarios...")
    chat.create_user("alice", "Alice")
    chat.create_user("bob", "Bob")
    chat.create_user("charlie", "Charlie")

    # Conectar usuarios
    chat.user_connect("alice")
    chat.user_connect("bob")

    print(f"   - Online: {[u.name for u in chat.get_online_users()]}")

    # Suscribirse a mensajes de la sala
    room_id = "general"
    received = []

    def on_message(msg: Message):
        received.append(msg)
        print(f"   📨 [{msg.author_name}]: {msg.content}")

    print(f"\n2. Suscribiéndose a sala '{room_id}'...")
    pubsub.subscribe(f"MESSAGE_ADDED_{room_id}", on_message)

    # Simular typing
    print("\n3. Simulando conversación...")

    chat.set_typing(room_id, "alice", True)
    print("   ✍️  Alice está escribiendo...")
    time.sleep(0.3)

    chat.send_message(room_id, "alice", "Hola a todos!")
    time.sleep(0.2)

    chat.set_typing(room_id, "bob", True)
    print("   ✍️  Bob está escribiendo...")
    time.sleep(0.3)

    chat.send_message(room_id, "bob", "Hey Alice! Cómo estás?")
    time.sleep(0.2)

    chat.send_message(room_id, "alice", "Muy bien, gracias!")

    print(f"\n4. Mensajes en sala: {len(chat.get_messages(room_id))}")


def demo_presence_subscriptions() -> None:
    """Demostrar sistema de presencia."""
    logger.info("=== Demo: Presencia Online ===")

    pubsub = PubSub()
    chat = ChatService(pubsub)

    # Suscribirse a cambios de presencia
    presence_changes = []

    def on_presence_change(event):
        user_id = event["user_id"]
        status = "🟢 online" if event["is_online"] else "⚫ offline"
        print(f"   {user_id}: {status}")
        presence_changes.append(event)

    print("\n1. Monitoreando cambios de presencia...")
    pubsub.subscribe("PRESENCE_CHANGED", on_presence_change)

    # Crear usuarios
    chat.create_user("user-1", "Alice")
    chat.create_user("user-2", "Bob")
    chat.create_user("user-3", "Charlie")

    print("\n2. Usuarios conectándose...")
    chat.user_connect("user-1")
    time.sleep(0.1)
    chat.user_connect("user-2")
    time.sleep(0.1)
    chat.user_connect("user-3")

    print(f"\n3. Usuarios online: {len(chat.get_online_users())}")

    print("\n4. Usuarios desconectándose...")
    chat.user_disconnect("user-2")
    time.sleep(0.1)

    print(f"\n5. Usuarios online: {len(chat.get_online_users())}")
    for user in chat.get_online_users():
        print(f"   - {user.name}")

    print(f"\n6. Total eventos de presencia: {len(presence_changes)}")


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="GraphQL Subscriptions Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python subscriptions_demo.py --demo basic
    python subscriptions_demo.py --demo chat
    python subscriptions_demo.py --demo presence
    python subscriptions_demo.py --demo all
        """,
    )

    parser.add_argument(
        "--demo",
        choices=["basic", "chat", "presence", "all"],
        default="all",
        help="Tipo de demo a ejecutar",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("       GRAPHQL SUBSCRIPTIONS DEMO")
    print("=" * 60)

    if args.demo in ("basic", "all"):
        demo_basic_subscriptions()
        print()

    if args.demo in ("chat", "all"):
        demo_chat_subscriptions()
        print()

    if args.demo in ("presence", "all"):
        demo_presence_subscriptions()

    print("\n" + "=" * 60)
    print("Demo completada. Ver SKILL.md para patrones de producción")
    print("con Apollo Server, graphql-ws y Redis PubSub.")
    print("=" * 60)


if __name__ == "__main__":
    main()
