"""
Antigravity Gateway - WebSocket Control Plane.

Inspirado en OpenClaw Gateway, este módulo proporciona un hub centralizado
para coordinar agentes, clientes, herramientas y eventos.

Features:
- WebSocket server en ws://127.0.0.1:18789
- JSON-RPC 2.0 protocol
- Session management
- Event pub/sub
- Tool registration
- Agent coordination

Usage:
    from .agent.core.gateway import AntigravityGateway

    gateway = AntigravityGateway()
    await gateway.start()

Reference: https://github.com/clawdbot/clawdbot
"""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from collections.abc import Callable, Coroutine
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


class MessageType(str, Enum):
    """Tipos de mensajes del Gateway."""

    # Control
    CONNECT = "connect"
    DISCONNECT = "disconnect"
    PING = "ping"
    PONG = "pong"

    # JSON-RPC
    REQUEST = "request"
    RESPONSE = "response"
    NOTIFICATION = "notification"
    ERROR = "error"

    # Events
    EVENT = "event"
    SUBSCRIBE = "subscribe"
    UNSUBSCRIBE = "unsubscribe"

    # Agent
    AGENT_INVOKE = "agent.invoke"
    AGENT_RESULT = "agent.result"
    AGENT_STATUS = "agent.status"

    # Tool
    TOOL_CALL = "tool.call"
    TOOL_RESULT = "tool.result"
    TOOL_LIST = "tool.list"


class SessionState(str, Enum):
    """Estados de sesión."""

    PENDING = "pending"
    ACTIVE = "active"
    PAUSED = "paused"
    CLOSED = "closed"


class ClientType(str, Enum):
    """Tipos de clientes conectados."""

    CLI = "cli"
    WEB_UI = "web_ui"
    MOBILE = "mobile"
    MCP = "mcp"
    AGENT = "agent"
    TOOL = "tool"
    EXTERNAL = "external"


# =============================================================================
# Modelos Pydantic
# =============================================================================


class GatewayConfig(BaseModel):
    """Configuración del Gateway."""

    host: str = Field(default="127.0.0.1", description="Host del servidor")
    port: int = Field(default=18789, description="Puerto WebSocket")
    max_connections: int = Field(default=100, description="Máximo de conexiones")
    heartbeat_interval: int = Field(default=30, description="Intervalo de heartbeat (segundos)")
    session_timeout: int = Field(default=3600, description="Timeout de sesión (segundos)")
    enable_sandbox: bool = Field(default=False, description="Habilitar sandbox por defecto")
    sandbox_mode: str = Field(default="non-main", description="Modo sandbox: none | all | non-main")


class JsonRpcRequest(BaseModel):
    """Solicitud JSON-RPC 2.0."""

    jsonrpc: str = "2.0"
    method: str
    params: dict[str, Any] | None = None
    id: str | int | None = None


class JsonRpcResponse(BaseModel):
    """Respuesta JSON-RPC 2.0."""

    jsonrpc: str = "2.0"
    result: Any | None = None
    error: dict[str, Any] | None = None
    id: str | int | None = None


class GatewayMessage(BaseModel):
    """Mensaje del Gateway."""

    type: MessageType
    payload: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)
    session_id: str | None = None
    client_id: str | None = None


class ClientInfo(BaseModel):
    """Información de cliente conectado."""

    client_id: str
    client_type: ClientType
    session_id: str
    connected_at: datetime = Field(default_factory=datetime.now)
    last_activity: datetime = Field(default_factory=datetime.now)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SessionInfo(BaseModel):
    """Información de sesión."""

    session_id: str
    state: SessionState = SessionState.PENDING
    created_at: datetime = Field(default_factory=datetime.now)
    clients: list[str] = Field(default_factory=list)
    is_main: bool = False
    sandbox_enabled: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)


class ToolInfo(BaseModel):
    """Información de herramienta registrada."""

    name: str
    description: str
    input_schema: dict[str, Any] = Field(default_factory=dict)
    handler_id: str
    category: str = "general"


class EventSubscription(BaseModel):
    """Suscripción a eventos."""

    subscription_id: str
    client_id: str
    event_pattern: str
    created_at: datetime = Field(default_factory=datetime.now)


# =============================================================================
# Gateway Core
# =============================================================================


@dataclass
class AntigravityGateway:
    """
    Gateway WebSocket Control Plane.

    Hub centralizado que coordina agentes, clientes, herramientas y eventos.
    Inspirado en la arquitectura de OpenClaw.

    Attributes:
        config: Configuración del gateway
        sessions: Sesiones activas
        clients: Clientes conectados
        tools: Herramientas registradas
        subscriptions: Suscripciones a eventos

    Example:
        >>> gateway = AntigravityGateway()
        >>> await gateway.start()
        >>> # Registrar herramienta
        >>> gateway.register_tool("my_tool", "Descripción", handler_fn)
        >>> # Broadcast evento
        >>> await gateway.broadcast_event("agent.completed", {"result": "success"})
    """

    config: GatewayConfig = field(default_factory=GatewayConfig)
    sessions: dict[str, SessionInfo] = field(default_factory=dict)
    clients: dict[str, ClientInfo] = field(default_factory=dict)
    tools: dict[str, ToolInfo] = field(default_factory=dict)
    subscriptions: dict[str, EventSubscription] = field(default_factory=dict)
    _handlers: dict[str, Callable] = field(default_factory=dict)
    _server: Any = field(default=None)
    _running: bool = field(default=False)

    def __post_init__(self) -> None:
        """Inicialización post-dataclass."""
        self._register_default_handlers()
        logger.info(f"Gateway inicializado en ws://{self.config.host}:{self.config.port}")

    def _register_default_handlers(self) -> None:
        """Registra handlers por defecto para mensajes."""
        self._handlers = {
            "initialize": self._handle_initialize,
            "ping": self._handle_ping,
            "tools/list": self._handle_tools_list,
            "tools/call": self._handle_tools_call,
            "agents/list": self._handle_agents_list,
            "agents/invoke": self._handle_agents_invoke,
            "sessions/list": self._handle_sessions_list,
            "sessions/create": self._handle_sessions_create,
            "events/subscribe": self._handle_events_subscribe,
            "events/unsubscribe": self._handle_events_unsubscribe,
        }

    # -------------------------------------------------------------------------
    # Lifecycle Methods
    # -------------------------------------------------------------------------

    async def start(self) -> None:
        """Inicia el servidor Gateway."""
        try:
            # Importación lazy de aiohttp para evitar errores si no está instalado
            from aiohttp import web

            app = web.Application()
            app.router.add_get("/ws", self._websocket_handler)
            app.router.add_get("/health", self._health_handler)

            runner = web.AppRunner(app)
            await runner.setup()
            self._server = web.TCPSite(runner, self.config.host, self.config.port)
            await self._server.start()

            self._running = True
            logger.info(f"Gateway iniciado en ws://{self.config.host}:{self.config.port}")

            # Iniciar heartbeat loop
            asyncio.create_task(self._heartbeat_loop())

        except ImportError:
            logger.warning("aiohttp no instalado. Gateway funcionará en modo mock.")
            self._running = True

    async def stop(self) -> None:
        """Detiene el servidor Gateway."""
        self._running = False
        if self._server:
            await self._server.stop()
        logger.info("Gateway detenido")

    async def _health_handler(self, request: Any) -> Any:
        """Handler para health check."""
        from aiohttp import web

        return web.json_response(
            {
                "status": "healthy",
                "sessions": len(self.sessions),
                "clients": len(self.clients),
                "tools": len(self.tools),
                "timestamp": datetime.now().isoformat(),
            }
        )

    async def _websocket_handler(self, request: Any) -> Any:
        """Handler principal para conexiones WebSocket."""
        from aiohttp import WSMsgType, web

        ws = web.WebSocketResponse()
        await ws.prepare(request)

        client_id = str(uuid.uuid4())
        session_id = request.query.get("session", str(uuid.uuid4()))

        # Registrar cliente
        await self._register_client(client_id, session_id, ws)

        try:
            async for msg in ws:
                if msg.type == WSMsgType.TEXT:
                    await self._handle_message(client_id, msg.data)
                elif msg.type == WSMsgType.ERROR:
                    logger.error(f"Error WebSocket: {ws.exception()}")
        finally:
            await self._unregister_client(client_id)

        return ws

    async def _heartbeat_loop(self) -> None:
        """Loop de heartbeat para mantener conexiones vivas."""
        while self._running:
            await asyncio.sleep(self.config.heartbeat_interval)
            # Enviar ping a todos los clientes
            for client_id in list(self.clients.keys()):
                try:
                    await self.send_to_client(
                        client_id,
                        GatewayMessage(
                            type=MessageType.PING, payload={"timestamp": datetime.now().isoformat()}
                        ),
                    )
                except Exception as e:
                    logger.warning(f"Error enviando heartbeat a {client_id}: {e}")

    # -------------------------------------------------------------------------
    # Client Management
    # -------------------------------------------------------------------------

    async def _register_client(self, client_id: str, session_id: str, websocket: Any) -> None:
        """Registra un nuevo cliente."""
        # Crear o obtener sesión
        if session_id not in self.sessions:
            self.sessions[session_id] = SessionInfo(
                session_id=session_id, state=SessionState.ACTIVE
            )

        # Registrar cliente
        self.clients[client_id] = ClientInfo(
            client_id=client_id, client_type=ClientType.EXTERNAL, session_id=session_id
        )
        self.clients[client_id].metadata["websocket"] = websocket

        # Añadir cliente a sesión
        self.sessions[session_id].clients.append(client_id)

        logger.info(f"Cliente {client_id} conectado a sesión {session_id}")

        # Enviar mensaje de bienvenida
        await self.send_to_client(
            client_id,
            GatewayMessage(
                type=MessageType.CONNECT,
                payload={
                    "client_id": client_id,
                    "session_id": session_id,
                    "server_info": {
                        "name": "Antigravity Gateway",
                        "version": "1.0.0",
                        "protocol": "JSON-RPC 2.0",
                    },
                },
            ),
        )

    async def _unregister_client(self, client_id: str) -> None:
        """Desregistra un cliente."""
        if client_id in self.clients:
            client = self.clients[client_id]
            session_id = client.session_id

            # Remover de sesión
            if session_id in self.sessions:
                if client_id in self.sessions[session_id].clients:
                    self.sessions[session_id].clients.remove(client_id)

            # Remover suscripciones
            for sub_id in list(self.subscriptions.keys()):
                if self.subscriptions[sub_id].client_id == client_id:
                    del self.subscriptions[sub_id]

            del self.clients[client_id]
            logger.info(f"Cliente {client_id} desconectado")

    async def send_to_client(self, client_id: str, message: GatewayMessage) -> None:
        """Envía mensaje a un cliente específico."""
        if client_id not in self.clients:
            return

        client = self.clients[client_id]
        ws = client.metadata.get("websocket")
        if ws:
            try:
                await ws.send_str(message.model_dump_json())
            except Exception as e:
                logger.error(f"Error enviando a {client_id}: {e}")

    async def broadcast_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Broadcast evento a todos los suscriptores."""
        for sub in self.subscriptions.values():
            if self._matches_pattern(event_type, sub.event_pattern):
                await self.send_to_client(
                    sub.client_id,
                    GatewayMessage(
                        type=MessageType.EVENT, payload={"event": event_type, "data": data}
                    ),
                )

    def _matches_pattern(self, event_type: str, pattern: str) -> bool:
        """Verifica si evento coincide con patrón."""
        if pattern == "*":
            return True
        if pattern.endswith(".*"):
            prefix = pattern[:-2]
            return event_type.startswith(prefix)
        return event_type == pattern

    # -------------------------------------------------------------------------
    # Message Handlers
    # -------------------------------------------------------------------------

    async def _handle_message(self, client_id: str, raw_message: str) -> None:
        """Procesa mensaje entrante."""
        try:
            data = json.loads(raw_message)

            # Actualizar actividad
            if client_id in self.clients:
                self.clients[client_id].last_activity = datetime.now()

            # Parsear como JSON-RPC
            if "jsonrpc" in data:
                request = JsonRpcRequest(**data)
                response = await self._process_rpc(client_id, request)
                await self.send_to_client(
                    client_id,
                    GatewayMessage(type=MessageType.RESPONSE, payload=response.model_dump()),
                )
            else:
                # Mensaje genérico
                message = GatewayMessage(**data)
                await self._process_message(client_id, message)

        except json.JSONDecodeError:
            logger.error(f"JSON inválido de {client_id}")
        except Exception as e:
            logger.error(f"Error procesando mensaje de {client_id}: {e}")

    async def _process_rpc(self, client_id: str, request: JsonRpcRequest) -> JsonRpcResponse:
        """Procesa solicitud JSON-RPC."""
        handler = self._handlers.get(request.method)
        if not handler:
            return JsonRpcResponse(
                id=request.id,
                error={"code": -32601, "message": f"Método no encontrado: {request.method}"},
            )

        try:
            result = await handler(client_id, request.params or {})
            return JsonRpcResponse(id=request.id, result=result)
        except Exception as e:
            return JsonRpcResponse(id=request.id, error={"code": -32603, "message": str(e)})

    async def _process_message(self, client_id: str, message: GatewayMessage) -> None:
        """Procesa mensaje genérico."""
        if message.type == MessageType.PONG:
            logger.debug(f"Pong recibido de {client_id}")
        elif message.type == MessageType.EVENT:
            await self.broadcast_event(
                message.payload.get("event", "unknown"), message.payload.get("data", {})
            )

    # -------------------------------------------------------------------------
    # RPC Handlers
    # -------------------------------------------------------------------------

    async def _handle_initialize(self, client_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para initialize."""
        client_type = params.get("client_type", "external")
        if client_id in self.clients:
            self.clients[client_id].client_type = ClientType(client_type)

        return {
            "capabilities": {"agents": True, "tools": True, "events": True, "sessions": True},
            "server_info": {"name": "Antigravity Gateway", "version": "1.0.0"},
        }

    async def _handle_ping(self, client_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para ping."""
        return {"pong": True, "timestamp": datetime.now().isoformat()}

    async def _handle_tools_list(self, client_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para tools/list."""
        return {
            "tools": [
                {
                    "name": tool.name,
                    "description": tool.description,
                    "inputSchema": tool.input_schema,
                    "category": tool.category,
                }
                for tool in self.tools.values()
            ]
        }

    async def _handle_tools_call(self, client_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para tools/call."""
        tool_name = params.get("name")
        if not tool_name:
            raise ValueError("Se requiere 'name' para invocar herramienta")

        tool_args = params.get("arguments", {})

        if tool_name not in self.tools:
            raise ValueError(f"Herramienta no encontrada: {tool_name}")

        tool_info = self.tools[tool_name]
        handler = self._handlers.get(f"tool:{tool_name}")
        if not handler:
            raise ValueError(f"Handler no registrado para herramienta: {tool_info.name}")

        result = await handler(tool_args)
        return {"result": result}

    async def _handle_agents_list(self, client_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para agents/list.

        Lists available agents from the orchestrator registry.
        Falls back to an empty list with an error message when the
        orchestrator is unavailable.
        """
        try:
            from .orchestrator import AntigravityOrchestrator

            orchestrator = AntigravityOrchestrator()
            agents = orchestrator.list_agents()  # type: ignore[attr-defined]  # dynamic orchestrator API
            return {"agents": agents}
        except ImportError:
            logger.warning("Orchestrator module not available for agents/list")
            return {"agents": [], "warning": "orchestrator module not available"}
        except Exception as e:
            logger.error("Error listing agents: %s", e)
            return {"agents": [], "error": str(e)}

    async def _handle_agents_invoke(self, client_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Invoke an agent to execute a task.

        Delegates execution to the orchestrator and broadcasts lifecycle
        events (started / completed / failed) to all subscribers.
        """
        agent_name = params.get("agent")
        task = params.get("task")

        if not agent_name:
            raise ValueError("Se requiere 'agent' para invocar agente")
        if not task:
            raise ValueError("Se requiere 'task' para invocar agente")

        # Broadcast evento de inicio
        await self.broadcast_event(
            "agent.started", {"agent": agent_name, "task": task, "client_id": client_id}
        )

        try:
            from .orchestrator import AntigravityOrchestrator

            orchestrator = AntigravityOrchestrator()
            result = await orchestrator.invoke_agent(agent_name, task)  # type: ignore[attr-defined]  # dynamic orchestrator API

            # Broadcast evento de completado
            await self.broadcast_event("agent.completed", {"agent": agent_name, "result": result})

            return {"status": "completed", "agent": agent_name, "result": result}
        except ImportError:
            logger.error("Orchestrator module not available for agents/invoke")
            await self.broadcast_event(
                "agent.failed", {"agent": agent_name, "error": "orchestrator module not available"}
            )
            raise ValueError("Orchestrator module not available") from None
        except Exception as e:
            logger.error("Error invoking agent '%s': %s", agent_name, e)
            await self.broadcast_event("agent.failed", {"agent": agent_name, "error": str(e)})
            raise

    async def _handle_sessions_list(self, client_id: str, params: dict[str, Any]) -> dict[str, Any]:
        """Handler para sessions/list."""
        return {
            "sessions": [
                {
                    "session_id": s.session_id,
                    "state": s.state.value,
                    "clients": len(s.clients),
                    "created_at": s.created_at.isoformat(),
                }
                for s in self.sessions.values()
            ]
        }

    async def _handle_sessions_create(
        self, client_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handler para sessions/create."""
        session_id = str(uuid.uuid4())
        is_main = params.get("is_main", False)
        sandbox = params.get("sandbox", self.config.enable_sandbox)

        self.sessions[session_id] = SessionInfo(
            session_id=session_id,
            state=SessionState.ACTIVE,
            is_main=is_main,
            sandbox_enabled=sandbox,
        )

        return {"session_id": session_id, "is_main": is_main, "sandbox_enabled": sandbox}

    async def _handle_events_subscribe(
        self, client_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handler para events/subscribe."""
        pattern = params.get("pattern", "*")
        sub_id = str(uuid.uuid4())

        self.subscriptions[sub_id] = EventSubscription(
            subscription_id=sub_id, client_id=client_id, event_pattern=pattern
        )

        return {"subscription_id": sub_id, "pattern": pattern}

    async def _handle_events_unsubscribe(
        self, client_id: str, params: dict[str, Any]
    ) -> dict[str, Any]:
        """Handler para events/unsubscribe."""
        sub_id = params.get("subscription_id")
        if sub_id in self.subscriptions:
            del self.subscriptions[sub_id]
            return {"unsubscribed": True}
        return {"unsubscribed": False}

    # -------------------------------------------------------------------------
    # Tool Registration
    # -------------------------------------------------------------------------

    def register_tool(
        self,
        name: str,
        description: str,
        handler: Callable[..., Coroutine[Any, Any, Any]],
        input_schema: dict[str, Any] | None = None,
        category: str = "general",
    ) -> None:
        """
        Registra una herramienta en el Gateway.

        Args:
            name: Nombre de la herramienta
            description: Descripción de la herramienta
            handler: Función async que maneja la herramienta
            input_schema: Schema JSON de entrada
            category: Categoría de la herramienta

        Example:
            >>> async def my_tool(args):
            ...     return {"result": "success"}
            >>> gateway.register_tool("my_tool", "Mi herramienta", my_tool)
        """
        self.tools[name] = ToolInfo(
            name=name,
            description=description,
            input_schema=input_schema or {},
            handler_id=f"tool:{name}",
            category=category,
        )
        self._handlers[f"tool:{name}"] = handler
        logger.info(f"Herramienta registrada: {name}")

    def unregister_tool(self, name: str) -> None:
        """Desregistra una herramienta."""
        if name in self.tools:
            del self.tools[name]
            handler_id = f"tool:{name}"
            if handler_id in self._handlers:
                del self._handlers[handler_id]
            logger.info(f"Herramienta desregistrada: {name}")


# =============================================================================
# Factory Function
# =============================================================================


def create_gateway(host: str = "127.0.0.1", port: int = 18789, **kwargs: Any) -> AntigravityGateway:
    """
    Factory function para crear Gateway.

    Args:
        host: Host del servidor
        port: Puerto WebSocket
        **kwargs: Argumentos adicionales para GatewayConfig

    Returns:
        Instancia de AntigravityGateway
    """
    config = GatewayConfig(host=host, port=port, **kwargs)
    return AntigravityGateway(config=config)


# =============================================================================
# CLI Entry Point
# =============================================================================


async def main() -> None:
    """Entry point para ejecutar Gateway standalone."""
    import argparse

    parser = argparse.ArgumentParser(description="Antigravity Gateway Server")
    parser.add_argument("--host", default="127.0.0.1", help="Host del servidor")
    parser.add_argument("--port", type=int, default=18789, help="Puerto WebSocket")
    args = parser.parse_args()

    gateway = create_gateway(host=args.host, port=args.port)
    await gateway.start()

    print(f"Gateway ejecutándose en ws://{args.host}:{args.port}")
    print("Presiona Ctrl+C para detener")

    try:
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        await gateway.stop()


if __name__ == "__main__":
    asyncio.run(main())
