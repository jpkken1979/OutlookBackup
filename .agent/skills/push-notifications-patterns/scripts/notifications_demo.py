#!/usr/bin/env python3
"""
Push Notifications Patterns Demo

Este script demuestra patrones de notificaciones push incluyendo:
- Registro de dispositivos
- Envío a dispositivos individuales
- Envío a topics/grupos
- Gestión de preferencias
- Analytics de notificaciones

Uso:
    python notifications_demo.py --demo basic
    python notifications_demo.py --demo topics
    python notifications_demo.py --demo preferences
"""

import argparse
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from uuid import uuid4

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class Platform(Enum):
    """Plataformas de notificación."""

    IOS = "ios"
    ANDROID = "android"
    WEB = "web"


class NotificationPriority(Enum):
    """Prioridad de notificación."""

    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


@dataclass
class Device:
    """Dispositivo registrado para notificaciones."""

    id: str
    user_id: str
    token: str
    platform: Platform
    registered_at: datetime = field(default_factory=datetime.now)
    active: bool = True
    topics: list[str] = field(default_factory=list)


@dataclass
class NotificationPayload:
    """Payload de notificación."""

    title: str
    body: str
    data: dict = field(default_factory=dict)
    image_url: str | None = None
    action_url: str | None = None
    priority: NotificationPriority = NotificationPriority.NORMAL


@dataclass
class NotificationResult:
    """Resultado de envío de notificación."""

    id: str
    device_id: str
    success: bool
    sent_at: datetime = field(default_factory=datetime.now)
    error: str | None = None
    delivered_at: datetime | None = None
    opened_at: datetime | None = None


@dataclass
class UserPreferences:
    """Preferencias de notificación del usuario."""

    user_id: str
    email_enabled: bool = True
    push_enabled: bool = True
    categories: dict[str, bool] = field(
        default_factory=lambda: {
            "marketing": True,
            "transactional": True,
            "social": True,
            "updates": True,
        }
    )
    quiet_hours: tuple[int, int] | None = None  # (start_hour, end_hour)


class NotificationService:
    """
    Servicio de notificaciones push en memoria para demostración.

    En producción, usar Firebase Cloud Messaging (FCM),
    Apple Push Notification Service (APNs), o servicios como OneSignal.
    """

    def __init__(self) -> None:
        self.devices: dict[str, Device] = {}
        self.users_devices: dict[str, list[str]] = {}
        self.topics: dict[str, set[str]] = {}
        self.notifications: list[NotificationResult] = []
        self.preferences: dict[str, UserPreferences] = {}
        logger.info("Servicio de notificaciones inicializado")

    def register_device(self, user_id: str, token: str, platform: Platform) -> Device:
        """Registrar un nuevo dispositivo."""
        device_id = str(uuid4())[:8]

        device = Device(id=device_id, user_id=user_id, token=token, platform=platform)

        self.devices[device_id] = device

        if user_id not in self.users_devices:
            self.users_devices[user_id] = []
        self.users_devices[user_id].append(device_id)

        logger.info(
            f"Dispositivo registrado: {device_id} ({platform.value}) para usuario {user_id}"
        )
        return device

    def unregister_device(self, device_id: str) -> bool:
        """Dar de baja un dispositivo."""
        if device_id not in self.devices:
            return False

        device = self.devices[device_id]
        device.active = False

        # Remover de topics
        for _topic_name, device_ids in self.topics.items():
            device_ids.discard(device_id)

        logger.info(f"Dispositivo dado de baja: {device_id}")
        return True

    def subscribe_to_topic(self, device_id: str, topic: str) -> bool:
        """Suscribir dispositivo a un topic."""
        if device_id not in self.devices:
            return False

        if topic not in self.topics:
            self.topics[topic] = set()

        self.topics[topic].add(device_id)
        self.devices[device_id].topics.append(topic)

        logger.info(f"Dispositivo {device_id} suscrito a topic '{topic}'")
        return True

    def unsubscribe_from_topic(self, device_id: str, topic: str) -> bool:
        """Desuscribir dispositivo de un topic."""
        if topic in self.topics:
            self.topics[topic].discard(device_id)

        if device_id in self.devices:
            device = self.devices[device_id]
            if topic in device.topics:
                device.topics.remove(topic)

        logger.info(f"Dispositivo {device_id} desuscrito de topic '{topic}'")
        return True

    def send_to_device(
        self, device_id: str, payload: NotificationPayload, category: str = "transactional"
    ) -> NotificationResult:
        """Enviar notificación a un dispositivo específico."""
        result = NotificationResult(id=str(uuid4())[:8], device_id=device_id, success=False)

        if device_id not in self.devices:
            result.error = "Device not found"
            return result

        device = self.devices[device_id]

        if not device.active:
            result.error = "Device inactive"
            return result

        # Verificar preferencias del usuario
        prefs = self.preferences.get(device.user_id)
        if prefs:
            if not prefs.push_enabled:
                result.error = "Push notifications disabled"
                return result

            if not prefs.categories.get(category, True):
                result.error = f"Category '{category}' disabled"
                return result

            if prefs.quiet_hours:
                current_hour = datetime.now().hour
                start, end = prefs.quiet_hours
                if start <= current_hour < end:
                    result.error = "Quiet hours active"
                    return result

        # Simular envío (en producción, llamar a FCM/APNs)
        result.success = True
        self.notifications.append(result)

        logger.info(f"Notificación enviada a {device_id}: {payload.title}")

        # Simular formato según plataforma
        self._format_for_platform(device.platform, payload)

        return result

    def send_to_user(
        self, user_id: str, payload: NotificationPayload, category: str = "transactional"
    ) -> list[NotificationResult]:
        """Enviar notificación a todos los dispositivos de un usuario."""
        results = []

        device_ids = self.users_devices.get(user_id, [])

        for device_id in device_ids:
            result = self.send_to_device(device_id, payload, category)
            results.append(result)

        success_count = sum(1 for r in results if r.success)
        logger.info(
            f"Notificación enviada a usuario {user_id}: {success_count}/{len(results)} exitosas"
        )

        return results

    def send_to_topic(
        self, topic: str, payload: NotificationPayload, category: str = "marketing"
    ) -> list[NotificationResult]:
        """Enviar notificación a todos los suscriptores de un topic."""
        results = []

        device_ids = self.topics.get(topic, set())

        for device_id in device_ids:
            result = self.send_to_device(device_id, payload, category)
            results.append(result)

        success_count = sum(1 for r in results if r.success)
        logger.info(
            f"Notificación enviada a topic '{topic}': {success_count}/{len(results)} exitosas"
        )

        return results

    def set_user_preferences(self, user_id: str, preferences: UserPreferences) -> None:
        """Establecer preferencias de notificación para un usuario."""
        self.preferences[user_id] = preferences
        logger.info(f"Preferencias actualizadas para usuario {user_id}")

    def get_analytics(self) -> dict:
        """Obtener analytics de notificaciones."""
        total = len(self.notifications)
        successful = sum(1 for n in self.notifications if n.success)

        by_device = {}
        for n in self.notifications:
            if n.device_id in self.devices:
                platform = self.devices[n.device_id].platform.value
                by_device[platform] = by_device.get(platform, 0) + 1

        return {
            "total_sent": total,
            "successful": successful,
            "failed": total - successful,
            "success_rate": f"{(successful / total * 100):.1f}%" if total > 0 else "0%",
            "by_platform": by_device,
            "registered_devices": len(self.devices),
            "active_devices": sum(1 for d in self.devices.values() if d.active),
            "topics": {t: len(d) for t, d in self.topics.items()},
        }

    def _format_for_platform(self, platform: Platform, payload: NotificationPayload) -> dict:
        """Formatear payload según plataforma."""
        if platform == Platform.IOS:
            return {
                "aps": {
                    "alert": {"title": payload.title, "body": payload.body},
                    "badge": 1,
                    "sound": "default",
                },
                "data": payload.data,
            }
        elif platform == Platform.ANDROID:
            return {
                "notification": {
                    "title": payload.title,
                    "body": payload.body,
                    "image": payload.image_url,
                },
                "data": payload.data,
                "priority": payload.priority.value,
            }
        else:  # WEB
            return {
                "title": payload.title,
                "body": payload.body,
                "icon": "/icon.png",
                "badge": "/badge.png",
                "data": payload.data,
            }


def demo_basic_notifications() -> None:
    """Demostrar notificaciones básicas."""
    logger.info("=== Demo: Notificaciones Básicas ===")

    service = NotificationService()

    # Registrar dispositivos
    print("\n1. Registrando dispositivos...")
    device1 = service.register_device("user-1", "token-ios-abc", Platform.IOS)
    service.register_device("user-1", "token-android-xyz", Platform.ANDROID)
    service.register_device("user-2", "token-web-123", Platform.WEB)

    print(f"   - Registrados: {len(service.devices)} dispositivos")

    # Enviar a dispositivo individual
    print("\n2. Enviando a dispositivo individual...")
    payload = NotificationPayload(
        title="¡Bienvenido!",
        body="Gracias por registrarte en nuestra app",
        data={"screen": "onboarding"},
    )
    result = service.send_to_device(device1.id, payload)
    print(f"   - Resultado: {'✓ Éxito' if result.success else f'✗ Error: {result.error}'}")

    # Enviar a todos los dispositivos de un usuario
    print("\n3. Enviando a todos los dispositivos de user-1...")
    payload = NotificationPayload(
        title="Nueva oferta", body="50% de descuento solo hoy", action_url="/offers/50off"
    )
    results = service.send_to_user("user-1", payload, category="marketing")
    success = sum(1 for r in results if r.success)
    print(f"   - Enviados: {success}/{len(results)}")


def demo_topic_notifications() -> None:
    """Demostrar notificaciones por topics."""
    logger.info("=== Demo: Topics ===")

    service = NotificationService()

    # Registrar dispositivos
    devices = []
    for i in range(5):
        device = service.register_device(
            f"user-{i}", f"token-{i}", Platform.ANDROID if i % 2 == 0 else Platform.IOS
        )
        devices.append(device)

    # Suscribir a topics
    print("\n1. Configurando topics...")

    # Topic de noticias: todos
    for device in devices:
        service.subscribe_to_topic(device.id, "news")
    print(f"   - Topic 'news': {len(service.topics['news'])} suscriptores")

    # Topic de ofertas: algunos
    for device in devices[:3]:
        service.subscribe_to_topic(device.id, "offers")
    print(f"   - Topic 'offers': {len(service.topics['offers'])} suscriptores")

    # Topic de deportes: algunos
    for device in devices[2:]:
        service.subscribe_to_topic(device.id, "sports")
    print(f"   - Topic 'sports': {len(service.topics['sports'])} suscriptores")

    # Enviar a topic
    print("\n2. Enviando notificación a topic 'news'...")
    payload = NotificationPayload(
        title="Breaking News",
        body="Algo importante acaba de suceder",
        priority=NotificationPriority.HIGH,
    )
    results = service.send_to_topic("news", payload)
    print(f"   - Enviados: {sum(1 for r in results if r.success)}/{len(results)}")

    # Desuscribir
    print("\n3. Desuscribiendo device-0 de 'news'...")
    service.unsubscribe_from_topic(devices[0].id, "news")
    print(f"   - Topic 'news' ahora tiene: {len(service.topics['news'])} suscriptores")


def demo_preferences() -> None:
    """Demostrar preferencias de usuario."""
    logger.info("=== Demo: Preferencias ===")

    service = NotificationService()

    # Registrar dispositivos
    device1 = service.register_device("user-1", "token-1", Platform.IOS)
    service.register_device("user-2", "token-2", Platform.ANDROID)

    # Configurar preferencias
    print("\n1. Configurando preferencias...")

    # User-1: Desactiva marketing
    prefs1 = UserPreferences(
        user_id="user-1",
        categories={"marketing": False, "transactional": True, "social": True, "updates": True},
    )
    service.set_user_preferences("user-1", prefs1)
    print("   - user-1: Marketing deshabilitado")

    # User-2: Configura horas silenciosas
    prefs2 = UserPreferences(
        user_id="user-2",
        quiet_hours=(22, 8),  # 10pm a 8am
    )
    service.set_user_preferences("user-2", prefs2)
    print("   - user-2: Horas silenciosas 22:00-08:00")

    # Intentar enviar marketing a user-1
    print("\n2. Intentando enviar marketing a user-1...")
    payload = NotificationPayload(title="Oferta especial", body="No te pierdas esta oportunidad")
    result = service.send_to_device(device1.id, payload, category="marketing")
    print(f"   - Resultado: {'✓ Éxito' if result.success else f'✗ Bloqueado: {result.error}'}")

    # Enviar transaccional a user-1
    print("\n3. Enviando transaccional a user-1...")
    payload = NotificationPayload(
        title="Tu pedido ha sido enviado", body="Llegará mañana entre 9am y 12pm"
    )
    result = service.send_to_device(device1.id, payload, category="transactional")
    print(f"   - Resultado: {'✓ Éxito' if result.success else f'✗ Error: {result.error}'}")

    # Mostrar analytics
    print("\n4. Analytics:")
    analytics = service.get_analytics()
    print(f"   - Total enviados: {analytics['total_sent']}")
    print(f"   - Exitosos: {analytics['successful']}")
    print(f"   - Tasa de éxito: {analytics['success_rate']}")


def main() -> None:
    """Punto de entrada principal."""
    parser = argparse.ArgumentParser(
        description="Push Notifications Patterns Demo",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
    python notifications_demo.py --demo basic
    python notifications_demo.py --demo topics
    python notifications_demo.py --demo preferences
    python notifications_demo.py --demo all
        """,
    )

    parser.add_argument(
        "--demo",
        choices=["basic", "topics", "preferences", "all"],
        default="all",
        help="Tipo de demo a ejecutar",
    )

    args = parser.parse_args()

    print("=" * 60)
    print("      PUSH NOTIFICATIONS PATTERNS DEMO")
    print("=" * 60)

    if args.demo in ("basic", "all"):
        demo_basic_notifications()
        print()

    if args.demo in ("topics", "all"):
        demo_topic_notifications()
        print()

    if args.demo in ("preferences", "all"):
        demo_preferences()

    print("\n" + "=" * 60)
    print("Demo completada. Ver SKILL.md para patrones de producción")
    print("con Firebase Cloud Messaging, APNs y Web Push.")
    print("=" * 60)


if __name__ == "__main__":
    main()
