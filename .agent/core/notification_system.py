# mypy: ignore-errors
#!/usr/bin/env python3
"""
Notification System - Sistema de notificaciones multi-canal

Soporta:
- Console (siempre disponible)
- Desktop notifications (si disponible)
- Webhooks (Slack, Discord, custom)
- Email (si configurado)
- File logging
"""

import json
import os
import logging
import threading

logger = logging.getLogger(__name__)
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

try:
    from .security_utils import validate_url_for_ssrf
except ImportError:
    from security_utils import validate_url_for_ssrf


class NotificationLevel(Enum):
    """Niveles de notificación"""

    DEBUG = "debug"
    INFO = "info"
    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class NotificationChannel(Enum):
    """Canales de notificación disponibles"""

    CONSOLE = "console"
    DESKTOP = "desktop"
    SLACK = "slack"
    DISCORD = "discord"
    WEBHOOK = "webhook"
    EMAIL = "email"
    FILE = "file"


@dataclass
class Notification:
    """Representa una notificación"""

    title: str
    message: str
    level: NotificationLevel = NotificationLevel.INFO
    timestamp: str = ""
    source: str = "antigravity"
    metadata: dict[str, Any] = field(default_factory=dict)
    channels: list[NotificationChannel] = field(default_factory=list)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()
        if not self.channels:
            self.channels = [NotificationChannel.CONSOLE]


@dataclass
class ChannelConfig:
    """Configuración de un canal"""

    enabled: bool = True
    webhook_url: str | None = None
    min_level: NotificationLevel = NotificationLevel.INFO
    filters: list[str] = field(default_factory=list)


class NotificationSystem:
    """Sistema central de notificaciones"""

    LEVEL_EMOJI = {
        NotificationLevel.DEBUG: "🔍",
        NotificationLevel.INFO: "ℹ️",
        NotificationLevel.SUCCESS: "✅",
        NotificationLevel.WARNING: "⚠️",
        NotificationLevel.ERROR: "❌",
        NotificationLevel.CRITICAL: "🚨",
    }

    LEVEL_COLORS = {
        NotificationLevel.DEBUG: "\033[90m",
        NotificationLevel.INFO: "\033[94m",
        NotificationLevel.SUCCESS: "\033[92m",
        NotificationLevel.WARNING: "\033[93m",
        NotificationLevel.ERROR: "\033[91m",
        NotificationLevel.CRITICAL: "\033[95m",
    }

    def __init__(self, config_file: Path | None = None, log_file: Path | None = None) -> None:
        # 3-tier resolution para config_file y log_file (NO repo paths como default)
        if config_file is not None:
            self.config_file = Path(config_file)
        elif os.environ.get("ANTIGRAVITY_NOTIFICATIONS_CONFIG"):
            self.config_file = Path(os.environ["ANTIGRAVITY_NOTIFICATIONS_CONFIG"])
        else:
            self.config_file = Path.home() / ".antigravity" / "config" / "notifications.json"
        if log_file is not None:
            self.log_file = Path(log_file)
        elif os.environ.get("ANTIGRAVITY_NOTIFICATIONS_LOG"):
            self.log_file = Path(os.environ["ANTIGRAVITY_NOTIFICATIONS_LOG"])
        else:
            self.log_file = Path.home() / ".antigravity" / "logs" / "notifications.log"
        self.channels: dict[NotificationChannel, ChannelConfig] = {}
        self.history: list[Notification] = []
        self.max_history = 1000
        self.subscribers: dict[str, list[Callable]] = {}
        self._lock = threading.Lock()

        self._load_config()
        self._setup_default_channels()

    def _load_config(self) -> None:
        """Cargar configuración desde archivo"""
        if self.config_file.exists():
            try:
                data = json.loads(self.config_file.read_text(encoding="utf-8"))
                for channel_name, config in data.get("channels", {}).items():
                    try:
                        channel = NotificationChannel(channel_name)
                        self.channels[channel] = ChannelConfig(
                            enabled=config.get("enabled", True),
                            webhook_url=config.get("webhook_url"),
                            min_level=NotificationLevel(config.get("min_level", "info")),
                            filters=config.get("filters", []),
                        )
                    except ValueError:
                        pass
            except Exception:
                pass

    def _setup_default_channels(self) -> None:
        """Configurar canales por defecto"""
        if NotificationChannel.CONSOLE not in self.channels:
            self.channels[NotificationChannel.CONSOLE] = ChannelConfig(enabled=True)

        if NotificationChannel.FILE not in self.channels:
            self.channels[NotificationChannel.FILE] = ChannelConfig(
                enabled=True, min_level=NotificationLevel.WARNING
            )

    def save_config(self) -> None:
        """Guardar configuración"""
        self.config_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "channels": {
                channel.value: {
                    "enabled": config.enabled,
                    "webhook_url": config.webhook_url,
                    "min_level": config.min_level.value,
                    "filters": config.filters,
                }
                for channel, config in self.channels.items()
            }
        }
        self.config_file.write_text(json.dumps(data, indent=2))

    def configure_channel(
        self,
        channel: NotificationChannel,
        enabled: bool = True,
        webhook_url: str | None = None,
        min_level: NotificationLevel = NotificationLevel.INFO,
    ) -> None:
        """Configurar un canal"""
        self.channels[channel] = ChannelConfig(
            enabled=enabled, webhook_url=webhook_url, min_level=min_level
        )
        self.save_config()

    def notify(
        self,
        title: str,
        message: str,
        level: NotificationLevel = NotificationLevel.INFO,
        channels: list[NotificationChannel] | None = None,
        source: str = "antigravity",
        metadata: dict | None = None,
    ) -> bool:
        """Enviar notificación"""
        notification = Notification(
            title=title,
            message=message,
            level=level,
            source=source,
            metadata=metadata or {},
            channels=channels or [NotificationChannel.CONSOLE],
        )

        handlers = {
            NotificationChannel.CONSOLE: self._send_console,
            NotificationChannel.DESKTOP: self._send_desktop,
            NotificationChannel.SLACK: self._send_slack,
            NotificationChannel.DISCORD: self._send_discord,
            NotificationChannel.WEBHOOK: self._send_webhook,
            NotificationChannel.FILE: self._send_file,
        }

        success = True
        for channel in notification.channels:
            if not self._should_send(channel, notification):
                continue

            handler = handlers.get(channel)
            if handler is None:
                continue

            try:
                handler(notification)
            except Exception as e:
                success = False
                print(f"Error sending to {channel.value}: {e}")

        # Guardar en historial
        with self._lock:
            self.history.append(notification)
            if len(self.history) > self.max_history:
                self.history = self.history[-self.max_history :]

        # Notificar subscribers
        self._notify_subscribers(notification)

        return success

    def _should_send(self, channel: NotificationChannel, notification: Notification) -> bool:
        """Verificar si debe enviar por este canal"""
        config = self.channels.get(channel)
        if not config or not config.enabled:
            return False

        # Verificar nivel mínimo
        levels = list(NotificationLevel)
        return not levels.index(notification.level) < levels.index(config.min_level)

    def _send_console(self, notification: Notification) -> None:
        """Enviar a consola"""
        emoji = self.LEVEL_EMOJI.get(notification.level, "•")
        color = self.LEVEL_COLORS.get(notification.level, "")
        reset = "\033[0m"

        print(f"{color}{emoji} [{notification.source}] {notification.title}{reset}")
        if notification.message:
            print(f"   {notification.message}")

    def _send_desktop(self, notification: Notification) -> None:
        """Enviar notificación de escritorio"""
        try:
            # Intentar con notify-send (Linux)
            import subprocess

            subprocess.run(
                [
                    "notify-send",
                    notification.title,
                    notification.message,
                    "--urgency",
                    "normal" if notification.level.value in ["info", "success"] else "critical",
                ],
                capture_output=True,
                timeout=5,
            )
        except Exception:
            # Fallback a consola
            pass

    def _send_slack(self, notification: Notification) -> None:
        """Enviar a Slack"""
        config = self.channels.get(NotificationChannel.SLACK)
        if not config or not config.webhook_url:
            return

        color_map = {
            NotificationLevel.SUCCESS: "good",
            NotificationLevel.WARNING: "warning",
            NotificationLevel.ERROR: "danger",
            NotificationLevel.CRITICAL: "danger",
        }

        payload = {
            "attachments": [
                {
                    "color": color_map.get(notification.level, "#439FE0"),
                    "title": notification.title,
                    "text": notification.message,
                    "footer": f"Antigravity | {notification.source}",
                    "ts": datetime.now().timestamp(),
                }
            ]
        }

        self._send_http_request(config.webhook_url, payload)

    def _send_discord(self, notification: Notification) -> None:
        """Enviar a Discord"""
        config = self.channels.get(NotificationChannel.DISCORD)
        if not config or not config.webhook_url:
            return

        color_map = {
            NotificationLevel.SUCCESS: 3066993,  # green
            NotificationLevel.WARNING: 15105570,  # orange
            NotificationLevel.ERROR: 15158332,  # red
            NotificationLevel.CRITICAL: 10038562,  # purple
        }

        payload = {
            "embeds": [
                {
                    "title": notification.title,
                    "description": notification.message,
                    "color": color_map.get(notification.level, 3447003),
                    "footer": {"text": f"Antigravity | {notification.source}"},
                    "timestamp": notification.timestamp,
                }
            ]
        }

        self._send_http_request(config.webhook_url, payload)

    def _send_webhook(self, notification: Notification) -> None:
        """Enviar a webhook genérico"""
        config = self.channels.get(NotificationChannel.WEBHOOK)
        if not config or not config.webhook_url:
            return

        payload = {
            "title": notification.title,
            "message": notification.message,
            "level": notification.level.value,
            "source": notification.source,
            "timestamp": notification.timestamp,
            "metadata": notification.metadata,
        }

        self._send_http_request(config.webhook_url, payload)

    def _send_file(self, notification: Notification) -> None:
        """Escribir a archivo de log"""
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        log_entry = (
            f"[{notification.timestamp}] [{notification.level.value.upper()}] "
            f"[{notification.source}] {notification.title}: {notification.message}\n"
        )

        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(log_entry)

    def _send_http_request(self, url: str, payload: dict) -> bytes | None:
        """Enviar request HTTP con validación SSRF"""
        # SSRF: validar URL antes de hacer request
        valid, reason = validate_url_for_ssrf(url)
        if not valid:
            logger.warning("SSRF bloqueado en notification webhook: %s", reason)
            return None
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=10) as response:
                return response.read()
        except urllib.error.URLError:
            pass

    def subscribe(self, event: str, callback: Callable[[Notification], None]) -> None:
        """Suscribirse a eventos de notificación"""
        if event not in self.subscribers:
            self.subscribers[event] = []
        self.subscribers[event].append(callback)

    def _notify_subscribers(self, notification: Notification) -> None:
        """Notificar a suscriptores"""
        for callback in self.subscribers.get("all", []):
            try:
                callback(notification)
            except Exception:
                pass

        for callback in self.subscribers.get(notification.level.value, []):
            try:
                callback(notification)
            except Exception:
                pass

    def get_history(
        self, level: NotificationLevel | None = None, source: str | None = None, limit: int = 50
    ) -> list[Notification]:
        """Obtener historial de notificaciones"""
        result = self.history

        if level:
            result = [n for n in result if n.level == level]

        if source:
            result = [n for n in result if n.source == source]

        return result[-limit:]

    # Métodos de conveniencia
    def info(self, title: str, message: str = "", **kwargs):
        return self.notify(title, message, NotificationLevel.INFO, **kwargs)

    def success(self, title: str, message: str = "", **kwargs):
        return self.notify(title, message, NotificationLevel.SUCCESS, **kwargs)

    def warning(self, title: str, message: str = "", **kwargs):
        return self.notify(title, message, NotificationLevel.WARNING, **kwargs)

    def error(self, title: str, message: str = "", **kwargs):
        return self.notify(title, message, NotificationLevel.ERROR, **kwargs)

    def critical(self, title: str, message: str = "", **kwargs):
        return self.notify(title, message, NotificationLevel.CRITICAL, **kwargs)


# Singleton global
_notification_system: NotificationSystem | None = None
_ns_lock = threading.Lock()


def get_notification_system() -> NotificationSystem:
    """Obtener instancia singleton"""
    global _notification_system

    if _notification_system is None:
        with _ns_lock:
            if _notification_system is None:
                _notification_system = NotificationSystem()

    return _notification_system


# Funciones de conveniencia globales
def notify(title: str, message: str = "", level: str = "info", **kwargs):
    """Enviar notificación rápida"""
    ns = get_notification_system()
    level_enum = NotificationLevel(level)
    return ns.notify(title, message, level_enum, **kwargs)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Notification System")
    parser.add_argument("command", choices=["send", "history", "config", "test"])
    parser.add_argument("--title", "-t", help="Notification title")
    parser.add_argument("--message", "-m", help="Notification message")
    parser.add_argument(
        "--level",
        "-l",
        default="info",
        choices=["debug", "info", "success", "warning", "error", "critical"],
    )
    parser.add_argument("--channel", "-c", help="Channel (console, slack, discord, webhook)")
    parser.add_argument("--webhook-url", help="Webhook URL for configuration")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    ns = get_notification_system()

    if args.command == "send":
        if not args.title:
            print("Error: --title required")
            exit(1)

        channels = None
        if args.channel:
            channels = [NotificationChannel(args.channel)]

        ns.notify(
            title=args.title,
            message=args.message or "",
            level=NotificationLevel(args.level),
            channels=channels,
        )

    elif args.command == "history":
        history = ns.get_history(limit=20)
        if args.json:
            print(
                json.dumps(
                    [
                        {
                            "title": n.title,
                            "message": n.message,
                            "level": n.level.value,
                            "timestamp": n.timestamp,
                        }
                        for n in history
                    ],
                    indent=2,
                )
            )
        else:
            for n in history:
                emoji = ns.LEVEL_EMOJI.get(n.level, "•")
                print(f"{emoji} [{n.timestamp[:19]}] {n.title}")

    elif args.command == "config":
        if args.channel and args.webhook_url:
            ns.configure_channel(
                NotificationChannel(args.channel), enabled=True, webhook_url=args.webhook_url
            )
            print(f"Configured {args.channel} with webhook URL")
        else:
            print("Current configuration:")
            for channel, config in ns.channels.items():
                print(f"  {channel.value}: enabled={config.enabled}")

    elif args.command == "test":
        print("Testing notification system...\n")
        ns.info("Test Info", "This is an info notification")
        ns.success("Test Success", "This is a success notification")
        ns.warning("Test Warning", "This is a warning notification")
        ns.error("Test Error", "This is an error notification")
        print("\n✓ Notification system working")
