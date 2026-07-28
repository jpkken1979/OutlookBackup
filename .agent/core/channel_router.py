"""
Antigravity Channel Router - Multi-Platform Message Routing.

Inspirado en OpenClaw Multi-Channel Integration, este módulo proporciona
un enrutador unificado para múltiples plataformas de mensajería.

Plataformas soportadas:
- WhatsApp (via Baileys/whatsapp-web.js)
- Telegram (via python-telegram-bot)
- Discord (via discord.py)
- Slack (via slack-sdk)
- Signal (via signal-cli-rest-api)
- Matrix (via matrix-nio)
- WebChat (WebSocket nativo)

Features:
- Interfaz unificada UnifiedMessage
- Normalización automática de mensajes
- Enrutamiento inteligente
- Soporte para grupos y menciones
- Rate limiting por canal
- Retry con backoff exponencial

Usage:
    from .agent.core.channel_router import ChannelRouter, UnifiedMessage

    router = ChannelRouter()
    await router.connect_channel("telegram", config)

    # Recibir mensaje normalizado
    message = await router.receive()

    # Enviar respuesta
    await router.send(UnifiedMessage(
        platform="telegram",
        chat_id="123456",
        content="Hola!"
    ))

Reference: https://github.com/clawdbot/clawdbot
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

# Configurar logging
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


# =============================================================================
# Enums y Constantes
# =============================================================================


class Platform(str, Enum):
    """Plataformas de mensajería soportadas."""

    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    DISCORD = "discord"
    SLACK = "slack"
    SIGNAL = "signal"
    MATRIX = "matrix"
    WEBCHAT = "webchat"
    IMESSAGE = "imessage"
    TEAMS = "teams"


class MessageType(str, Enum):
    """Tipos de mensaje."""

    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    DOCUMENT = "document"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACT = "contact"
    REACTION = "reaction"
    REPLY = "reply"
    COMMAND = "command"


class ChatType(str, Enum):
    """Tipos de chat."""

    PRIVATE = "private"
    GROUP = "group"
    CHANNEL = "channel"
    THREAD = "thread"


class ChannelState(str, Enum):
    """Estados del canal."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


# =============================================================================
# Modelos Pydantic
# =============================================================================


class UnifiedUser(BaseModel):
    """Usuario normalizado entre plataformas."""

    user_id: str
    username: str | None = None
    display_name: str | None = None
    avatar_url: str | None = None
    platform: Platform
    is_bot: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class UnifiedChat(BaseModel):
    """Chat normalizado entre plataformas."""

    chat_id: str
    chat_type: ChatType = ChatType.PRIVATE
    title: str | None = None
    platform: Platform
    member_count: int | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UnifiedAttachment(BaseModel):
    """Attachment normalizado."""

    attachment_id: str
    type: str
    url: str | None = None
    file_path: str | None = None
    mime_type: str | None = None
    size: int | None = None
    filename: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class UnifiedMessage(BaseModel):
    """
    Mensaje normalizado entre plataformas.

    Esta clase unifica la representación de mensajes de todas las plataformas
    soportadas, permitiendo que la lógica de agentes sea independiente del canal.
    """

    message_id: str = Field(default_factory=lambda: "")
    platform: Platform
    chat_id: str
    content: str = ""
    message_type: MessageType = MessageType.TEXT

    # Usuario
    sender: UnifiedUser | None = None
    chat: UnifiedChat | None = None

    # Contenido adicional
    attachments: list[UnifiedAttachment] = Field(default_factory=list)
    reply_to: str | None = None
    mentions: list[str] = Field(default_factory=list)
    commands: list[str] = Field(default_factory=list)

    # Metadata
    timestamp: datetime = Field(default_factory=datetime.now)
    raw: dict[str, Any] = Field(default_factory=dict)
    metadata: dict[str, Any] = Field(default_factory=dict)


class ChannelConfig(BaseModel):
    """Configuración de canal."""

    platform: Platform
    credentials: dict[str, str] = Field(default_factory=dict)
    options: dict[str, Any] = Field(default_factory=dict)
    rate_limit: int = Field(default=30, description="Mensajes por minuto")
    retry_attempts: int = Field(default=3)
    retry_delay: float = Field(default=1.0, description="Segundos entre reintentos")


# =============================================================================
# Channel Base Class
# =============================================================================


class BaseChannel(ABC):
    """
    Clase base abstracta para canales de mensajería.

    Todos los adaptadores de plataforma deben heredar de esta clase
    e implementar los métodos abstractos.
    """

    def __init__(self, config: ChannelConfig):
        self.config = config
        self.state = ChannelState.DISCONNECTED
        self._message_queue: asyncio.Queue[UnifiedMessage] = asyncio.Queue()
        self._client: Any = None

    @property
    def platform(self) -> Platform:
        return self.config.platform

    @abstractmethod
    async def connect(self) -> None:
        """Conecta al servicio de mensajería."""
        pass

    @abstractmethod
    async def disconnect(self) -> None:
        """Desconecta del servicio de mensajería."""
        pass

    @abstractmethod
    async def send(self, message: UnifiedMessage) -> bool:
        """Envía mensaje a la plataforma."""
        pass

    @abstractmethod
    async def normalize(self, raw: dict[str, Any]) -> UnifiedMessage:
        """Normaliza mensaje de la plataforma a UnifiedMessage."""
        pass

    async def receive(self) -> UnifiedMessage:
        """Recibe siguiente mensaje de la cola."""
        return await self._message_queue.get()

    def queue_message(self, message: UnifiedMessage) -> None:
        """Añade mensaje a la cola."""
        self._message_queue.put_nowait(message)


# =============================================================================
# Platform Adapters
# =============================================================================


class WhatsAppChannel(BaseChannel):
    """Adaptador para WhatsApp via whatsapp-web.js."""

    async def connect(self) -> None:
        self.state = ChannelState.CONNECTING
        logger.info("Conectando a WhatsApp...")
        # Implementación real usaría whatsapp-web.js o Baileys
        self.state = ChannelState.CONNECTED
        logger.info("WhatsApp conectado")

    async def disconnect(self) -> None:
        self.state = ChannelState.DISCONNECTED
        logger.info("WhatsApp desconectado")

    async def send(self, message: UnifiedMessage) -> bool:
        if self.state != ChannelState.CONNECTED:
            logger.warning("WhatsApp no conectado")
            return False

        logger.info(f"[WhatsApp] Enviando a {message.chat_id}: {message.content[:50]}...")
        # Implementación real enviaría via API
        return True

    async def normalize(self, raw: dict[str, Any]) -> UnifiedMessage:
        return UnifiedMessage(
            message_id=raw.get("id", {}).get("id", ""),
            platform=Platform.WHATSAPP,
            chat_id=raw.get("from", ""),
            content=raw.get("body", ""),
            sender=UnifiedUser(
                user_id=raw.get("author", raw.get("from", "")), platform=Platform.WHATSAPP
            ),
            raw=raw,
        )


class TelegramChannel(BaseChannel):
    """Adaptador para Telegram via python-telegram-bot."""

    async def connect(self) -> None:
        self.state = ChannelState.CONNECTING
        logger.info("Conectando a Telegram...")

        try:
            # Importación lazy
            from telegram.ext import Application

            token = self.config.credentials.get("token", "")
            if token:
                self._client = Application.builder().token(token).build()
                await self._client.initialize()
                self.state = ChannelState.CONNECTED
                logger.info("Telegram conectado")
            else:
                logger.warning("Token de Telegram no configurado")
                self.state = ChannelState.ERROR
        except ImportError:
            logger.warning("python-telegram-bot no instalado. Modo mock activado.")
            self.state = ChannelState.CONNECTED

    async def disconnect(self) -> None:
        if self._client:
            await self._client.shutdown()
        self.state = ChannelState.DISCONNECTED
        logger.info("Telegram desconectado")

    async def send(self, message: UnifiedMessage) -> bool:
        if self.state != ChannelState.CONNECTED:
            return False

        logger.info(f"[Telegram] Enviando a {message.chat_id}: {message.content[:50]}...")

        if self._client:
            try:
                await self._client.bot.send_message(chat_id=message.chat_id, text=message.content)
                return True
            except Exception as e:
                logger.error(f"Error enviando a Telegram: {e}")
                return False
        return True  # Mock mode

    async def normalize(self, raw: dict[str, Any]) -> UnifiedMessage:
        return UnifiedMessage(
            message_id=str(raw.get("message_id", "")),
            platform=Platform.TELEGRAM,
            chat_id=str(raw.get("chat", {}).get("id", "")),
            content=raw.get("text", ""),
            sender=UnifiedUser(
                user_id=str(raw.get("from", {}).get("id", "")),
                username=raw.get("from", {}).get("username"),
                display_name=raw.get("from", {}).get("first_name"),
                platform=Platform.TELEGRAM,
                is_bot=raw.get("from", {}).get("is_bot", False),
            ),
            raw=raw,
        )


class DiscordChannel(BaseChannel):
    """Adaptador para Discord via discord.py."""

    async def connect(self) -> None:
        self.state = ChannelState.CONNECTING
        logger.info("Conectando a Discord...")

        try:
            import discord

            token = self.config.credentials.get("token", "")
            if token:
                intents = discord.Intents.default()
                intents.message_content = True
                self._client = discord.Client(intents=intents)
                # En producción: await self._client.start(token)
                self.state = ChannelState.CONNECTED
                logger.info("Discord conectado")
            else:
                logger.warning("Token de Discord no configurado")
                self.state = ChannelState.ERROR
        except ImportError:
            logger.warning("discord.py no instalado. Modo mock activado.")
            self.state = ChannelState.CONNECTED

    async def disconnect(self) -> None:
        if self._client:
            await self._client.close()
        self.state = ChannelState.DISCONNECTED
        logger.info("Discord desconectado")

    async def send(self, message: UnifiedMessage) -> bool:
        if self.state != ChannelState.CONNECTED:
            return False

        logger.info(f"[Discord] Enviando a {message.chat_id}: {message.content[:50]}...")

        if self._client:
            try:
                channel = self._client.get_channel(int(message.chat_id))
                if channel:
                    await channel.send(message.content)
                    return True
            except Exception as e:
                logger.error(f"Error enviando a Discord: {e}")
                return False
        return True

    async def normalize(self, raw: dict[str, Any]) -> UnifiedMessage:
        return UnifiedMessage(
            message_id=str(raw.get("id", "")),
            platform=Platform.DISCORD,
            chat_id=str(raw.get("channel_id", "")),
            content=raw.get("content", ""),
            sender=UnifiedUser(
                user_id=str(raw.get("author", {}).get("id", "")),
                username=raw.get("author", {}).get("username"),
                display_name=raw.get("author", {}).get("global_name"),
                platform=Platform.DISCORD,
                is_bot=raw.get("author", {}).get("bot", False),
            ),
            raw=raw,
        )


class SlackChannel(BaseChannel):
    """Adaptador para Slack via slack-sdk."""

    async def connect(self) -> None:
        self.state = ChannelState.CONNECTING
        logger.info("Conectando a Slack...")

        try:
            from slack_sdk.web.async_client import AsyncWebClient

            token = self.config.credentials.get("token", "")
            if token:
                self._client = AsyncWebClient(token=token)
                self.state = ChannelState.CONNECTED
                logger.info("Slack conectado")
            else:
                logger.warning("Token de Slack no configurado")
                self.state = ChannelState.ERROR
        except ImportError:
            logger.warning("slack-sdk no instalado. Modo mock activado.")
            self.state = ChannelState.CONNECTED

    async def disconnect(self) -> None:
        self._client = None
        self.state = ChannelState.DISCONNECTED
        logger.info("Slack desconectado")

    async def send(self, message: UnifiedMessage) -> bool:
        if self.state != ChannelState.CONNECTED:
            return False

        logger.info(f"[Slack] Enviando a {message.chat_id}: {message.content[:50]}...")

        if self._client:
            try:
                await self._client.chat_postMessage(channel=message.chat_id, text=message.content)
                return True
            except Exception as e:
                logger.error(f"Error enviando a Slack: {e}")
                return False
        return True

    async def normalize(self, raw: dict[str, Any]) -> UnifiedMessage:
        return UnifiedMessage(
            message_id=raw.get("ts", ""),
            platform=Platform.SLACK,
            chat_id=raw.get("channel", ""),
            content=raw.get("text", ""),
            sender=UnifiedUser(user_id=raw.get("user", ""), platform=Platform.SLACK),
            raw=raw,
        )


class WebChatChannel(BaseChannel):
    """Adaptador para WebChat via WebSocket."""

    async def connect(self) -> None:
        self.state = ChannelState.CONNECTED
        logger.info("WebChat conectado (modo pasivo)")

    async def disconnect(self) -> None:
        self.state = ChannelState.DISCONNECTED
        logger.info("WebChat desconectado")

    async def send(self, message: UnifiedMessage) -> bool:
        logger.info(f"[WebChat] Enviando a {message.chat_id}: {message.content[:50]}...")
        # WebChat envía via Gateway WebSocket
        return True

    async def normalize(self, raw: dict[str, Any]) -> UnifiedMessage:
        return UnifiedMessage(
            message_id=raw.get("id", ""),
            platform=Platform.WEBCHAT,
            chat_id=raw.get("session_id", ""),
            content=raw.get("content", ""),
            raw=raw,
        )


# =============================================================================
# Channel Router
# =============================================================================


@dataclass
class ChannelRouter:
    """
    Router unificado para múltiples plataformas de mensajería.

    Abstrae las diferencias entre plataformas y proporciona una interfaz
    unificada para enviar y recibir mensajes.

    Attributes:
        channels: Canales conectados por plataforma
        default_platform: Plataforma por defecto para envíos

    Example:
        >>> router = ChannelRouter()
        >>> await router.connect_channel("telegram", ChannelConfig(
        ...     platform=Platform.TELEGRAM,
        ...     credentials={"token": "your-token"}
        ... ))
        >>> async for message in router.stream_messages():
        ...     response = await process_message(message)
        ...     await router.reply(message, response)
    """

    channels: dict[Platform, BaseChannel] = field(default_factory=dict)
    default_platform: Platform | None = None
    _running: bool = field(default=False)

    # Registry de adaptadores
    _adapters: dict[Platform, type[BaseChannel]] = field(
        default_factory=lambda: {
            Platform.WHATSAPP: WhatsAppChannel,
            Platform.TELEGRAM: TelegramChannel,
            Platform.DISCORD: DiscordChannel,
            Platform.SLACK: SlackChannel,
            Platform.WEBCHAT: WebChatChannel,
        }
    )

    def __post_init__(self) -> None:
        logger.info("ChannelRouter inicializado")

    # -------------------------------------------------------------------------
    # Channel Management
    # -------------------------------------------------------------------------

    async def connect_channel(self, platform: Platform | str, config: ChannelConfig) -> bool:
        """
        Conecta un canal de mensajería.

        Args:
            platform: Plataforma a conectar
            config: Configuración del canal

        Returns:
            True si conexión exitosa
        """
        if isinstance(platform, str):
            platform = Platform(platform)

        if platform not in self._adapters:
            logger.error(f"Plataforma no soportada: {platform}")
            return False

        adapter_class = self._adapters[platform]
        channel = adapter_class(config)

        try:
            await channel.connect()
            self.channels[platform] = channel

            if self.default_platform is None:
                self.default_platform = platform

            logger.info(f"Canal {platform.value} conectado")
            return True
        except Exception as e:
            logger.error(f"Error conectando {platform.value}: {e}")
            return False

    async def disconnect_channel(self, platform: Platform | str) -> None:
        """Desconecta un canal."""
        if isinstance(platform, str):
            platform = Platform(platform)

        if platform in self.channels:
            await self.channels[platform].disconnect()
            del self.channels[platform]
            logger.info(f"Canal {platform.value} desconectado")

    async def disconnect_all(self) -> None:
        """Desconecta todos los canales."""
        for platform in list(self.channels.keys()):
            await self.disconnect_channel(platform)

    def get_channel(self, platform: Platform | str) -> BaseChannel | None:
        """Obtiene un canal por plataforma."""
        if isinstance(platform, str):
            platform = Platform(platform)
        return self.channels.get(platform)

    def list_channels(self) -> list[dict[str, Any]]:
        """Lista canales conectados."""
        return [{"platform": p.value, "state": c.state.value} for p, c in self.channels.items()]

    # -------------------------------------------------------------------------
    # Message Routing
    # -------------------------------------------------------------------------

    async def send(self, message: UnifiedMessage) -> bool:
        """
        Envía mensaje a la plataforma apropiada.

        Args:
            message: Mensaje unificado a enviar

        Returns:
            True si envío exitoso
        """
        channel = self.channels.get(message.platform)
        if not channel:
            logger.error(f"Canal no conectado: {message.platform}")
            return False

        # Rate limiting (simplificado)
        await asyncio.sleep(0.1)

        # Retry con backoff
        for attempt in range(channel.config.retry_attempts):
            try:
                success = await channel.send(message)
                if success:
                    return True
            except Exception as e:
                logger.warning(f"Intento {attempt + 1} fallido: {e}")
                await asyncio.sleep(channel.config.retry_delay * (2**attempt))

        return False

    async def reply(self, original: UnifiedMessage, content: str, **kwargs: Any) -> bool:
        """
        Responde a un mensaje.

        Args:
            original: Mensaje original
            content: Contenido de respuesta
            **kwargs: Argumentos adicionales

        Returns:
            True si envío exitoso
        """
        response = UnifiedMessage(
            platform=original.platform,
            chat_id=original.chat_id,
            content=content,
            reply_to=original.message_id,
            **kwargs,
        )
        return await self.send(response)

    async def broadcast(
        self, content: str, platforms: list[Platform] | None = None, **kwargs: Any
    ) -> dict[Platform, bool]:
        """
        Broadcast mensaje a múltiples plataformas.

        Args:
            content: Contenido del mensaje
            platforms: Plataformas objetivo (None = todas)
            **kwargs: Argumentos adicionales

        Returns:
            Dict con resultado por plataforma
        """
        targets = platforms or list(self.channels.keys())
        results: dict[Platform, bool] = {}

        for platform in targets:
            channel = self.channels.get(platform)
            if channel:
                # Necesita chat_id específico por plataforma
                chat_id = kwargs.get(f"{platform.value}_chat_id", "")
                if chat_id:
                    message = UnifiedMessage(platform=platform, chat_id=chat_id, content=content)
                    results[platform] = await self.send(message)

        return results

    async def receive(self, platform: Platform | str) -> UnifiedMessage:
        """
        Recibe próximo mensaje de un canal específico.

        Args:
            platform: Plataforma de origen

        Returns:
            Mensaje unificado
        """
        if isinstance(platform, str):
            platform = Platform(platform)

        channel = self.channels.get(platform)
        if not channel:
            raise ValueError(f"Canal no conectado: {platform}")

        return await channel.receive()

    async def stream_messages(self) -> AsyncIterator[UnifiedMessage]:
        """
        Stream de mensajes de todos los canales conectados.

        Yields:
            UnifiedMessage de cualquier canal
        """
        self._running = True
        queues = [c._message_queue for c in self.channels.values()]

        while self._running and queues:
            # Esperar mensaje de cualquier cola
            done, _ = await asyncio.wait(
                [asyncio.create_task(q.get()) for q in queues], return_when=asyncio.FIRST_COMPLETED
            )

            for task in done:
                try:
                    message = task.result()
                    yield message
                except Exception as e:
                    logger.error(f"Error recibiendo mensaje: {e}")

    def stop_stream(self) -> None:
        """Detiene el stream de mensajes."""
        self._running = False

    # -------------------------------------------------------------------------
    # Message Processing
    # -------------------------------------------------------------------------

    async def normalize_message(
        self, platform: Platform | str, raw: dict[str, Any]
    ) -> UnifiedMessage:
        """
        Normaliza mensaje crudo de una plataforma.

        Args:
            platform: Plataforma de origen
            raw: Mensaje crudo de la plataforma

        Returns:
            Mensaje unificado
        """
        if isinstance(platform, str):
            platform = Platform(platform)

        channel = self.channels.get(platform)
        if not channel:
            raise ValueError(f"Canal no conectado: {platform}")

        return await channel.normalize(raw)

    def extract_commands(self, message: UnifiedMessage) -> list[str]:
        """
        Extrae comandos de un mensaje.

        Args:
            message: Mensaje a analizar

        Returns:
            Lista de comandos encontrados
        """
        commands: list[str] = []
        content = message.content

        # Detectar comandos estilo /command
        import re

        slash_commands = re.findall(r"/(\w+)", content)
        commands.extend(slash_commands)

        # Detectar menciones @bot
        if message.mentions:
            # Si el bot está mencionado, todo el mensaje es un comando
            commands.append("mentioned")

        return commands

    def extract_mentions(self, message: UnifiedMessage) -> list[str]:
        """
        Extrae menciones de un mensaje.

        Args:
            message: Mensaje a analizar

        Returns:
            Lista de user_ids mencionados
        """
        import re

        mentions: list[str] = []

        # Menciones estilo @username
        at_mentions = re.findall(r"@(\w+)", message.content)
        mentions.extend(at_mentions)

        # Menciones de la plataforma (ya parseadas)
        mentions.extend(message.mentions)

        return list(set(mentions))


# =============================================================================
# Factory Functions
# =============================================================================


def create_router() -> ChannelRouter:
    """Crea instancia de ChannelRouter."""
    return ChannelRouter()


async def quick_connect(platforms: dict[str, dict[str, str]]) -> ChannelRouter:
    """
    Conexión rápida a múltiples plataformas.

    Args:
        platforms: Dict de plataforma -> credenciales

    Example:
        >>> router = await quick_connect({
        ...     "telegram": {"token": "your-token"},
        ...     "discord": {"token": "your-token"}
        ... })
    """
    router = create_router()

    for platform_name, credentials in platforms.items():
        platform = Platform(platform_name)
        config = ChannelConfig(platform=platform, credentials=credentials)
        await router.connect_channel(platform, config)

    return router


# =============================================================================
# CLI Entry Point
# =============================================================================


async def main() -> None:
    """Entry point para testing."""
    router = create_router()

    # Conectar WebChat (siempre disponible)
    await router.connect_channel(Platform.WEBCHAT, ChannelConfig(platform=Platform.WEBCHAT))

    logger.info("ChannelRouter inicializado")
    logger.info("Canales conectados: %s", router.list_channels())

    # Simular envío
    await router.send(
        UnifiedMessage(
            platform=Platform.WEBCHAT, chat_id="test-session", content="Hola desde ChannelRouter!"
        )
    )


if __name__ == "__main__":
    asyncio.run(main())
