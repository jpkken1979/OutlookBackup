#!/usr/bin/env python3
"""
MCP Client - Conecta Antigravity con servidores MCP externos.

Permite que los agentes Antigravity llamen herramientas de otros servidores MCP:
- Context7: Documentación actualizada de librerías
- GitHub: Issues, PRs, repos
- Playwright: Automatización de browser
- Figma: Diseños y tokens
- Semgrep: Análisis de seguridad
- Y cualquier otro servidor MCP configurado

Uso:
    from core.mcp_client import MCPClientManager, get_mcp_manager

    # Obtener manager (singleton)
    manager = await get_mcp_manager()

    # Listar herramientas disponibles
    tools = await manager.list_all_tools()

    # Llamar una herramienta
    result = await manager.call_tool("context7", "resolve", {"libraryName": "react"})

    # Usar con agentes
    async with MCPClientManager() as manager:
        result = await manager.call_tool("github", "create_issue", {...})
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import subprocess
import time
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from types import TracebackType
from typing import Any

logger = logging.getLogger("antigravity.mcp_client")

# =============================================================================
# CONSTANTES DE COMUNICACIÓN
# =============================================================================
DEFAULT_REQUEST_TIMEOUT = 30.0  # Timeout por request (segundos)
DEFAULT_CONNECT_TIMEOUT = 15.0  # Timeout para connect/initialize
MAX_RECONNECT_ATTEMPTS = 3  # Intentos de reconexión automática
RECONNECT_BASE_DELAY = 1.0  # Delay base para backoff exponencial
HEALTH_CHECK_INTERVAL = 60.0  # Verificar salud cada 60s


def _build_url_opener() -> urllib.request.OpenerDirector:
    """Construye un opener HTTP que respeta proxy y NO_PROXY.

    Lee HTTPS_PROXY / HTTP_PROXY / NO_PROXY del entorno.
    Si ANTIGRAVITY_NO_PROXY=1 se salta el proxy completamente.
    """
    # Si el usuario quiere saltar proxy
    if os.environ.get("ANTIGRAVITY_NO_PROXY", "") == "1":
        return urllib.request.build_opener(urllib.request.ProxyHandler({}))

    # Si hay proxy explícito configurado
    proxy_url = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY") or ""
    if proxy_url:
        proxies = {"https": proxy_url, "http": proxy_url}
        logger.info("Using proxy: %s", proxy_url)
        return urllib.request.build_opener(urllib.request.ProxyHandler(proxies))

    # Default: usar proxy del sistema (urllib lo detecta automáticamente)
    return urllib.request.build_opener()


# =============================================================================
# CONFIGURACIÓN
# =============================================================================


# Ruta al archivo de configuración MCP
def _find_mcp_config() -> Path | None:
    """Busca archivo de configuración MCP en ubicaciones conocidas."""
    search_paths = [
        Path.cwd() / ".claude" / "settings.json",
        Path.cwd() / ".mcp.json",
        Path.cwd() / ".cursor" / "mcp.json",
        Path(__file__).parent.parent.parent / ".claude" / "settings.json",
        Path(__file__).parent.parent.parent / ".mcp.json",
    ]

    for path in search_paths:
        if path.exists():
            return path
    return None


@dataclass
class MCPServerConfig:
    """Configuración de un servidor MCP (stdio o HTTP remoto)."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict[str, str] = field(default_factory=dict)
    description: str = ""
    enabled: bool = True
    # Soporte HTTP remoto
    transport: str = "stdio"  # "stdio" | "http" | "url"
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    # Timeouts personalizables
    request_timeout: float = DEFAULT_REQUEST_TIMEOUT
    connect_timeout: float = DEFAULT_CONNECT_TIMEOUT

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> MCPServerConfig:
        """Crear desde diccionario de configuración."""
        transport = data.get("type", "stdio")
        url = data.get("url", "")
        headers = data.get("headers", {})

        # Expandir variables de entorno en headers
        expanded_headers = {}
        for key, value in headers.items():
            if isinstance(value, str) and "${" in value:
                import re

                def _expand(m: re.Match) -> str:
                    return os.environ.get(m.group(1), "")

                expanded_headers[key] = re.sub(r"\$\{(\w+)\}", _expand, value)
            else:
                expanded_headers[key] = value

        return cls(
            name=name,
            command=data.get("command", ""),
            args=data.get("args", []),
            env=data.get("env", {}),
            description=data.get("description", ""),
            enabled=data.get("enabled", True),
            transport=transport,
            url=url,
            headers=expanded_headers,
        )


# =============================================================================
# MCP CLIENT (Conexión individual)
# =============================================================================


@dataclass
class MCPToolInfo:
    """Información de una herramienta MCP."""

    name: str
    description: str
    input_schema: dict[str, Any]
    server_name: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_schema,
            "server": self.server_name,
        }


@dataclass
class MCPCallResult:
    """Resultado de llamar una herramienta MCP."""

    success: bool
    content: Any
    error: str | None = None
    server_name: str = ""
    tool_name: str = ""
    execution_time_ms: float = 0
    retries: int = 0
    transport: str = "stdio"

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "content": self.content,
            "error": self.error,
            "server": self.server_name,
            "tool": self.tool_name,
            "execution_time_ms": self.execution_time_ms,
            "retries": self.retries,
            "transport": self.transport,
        }


class MCPClient:
    """
    Cliente para un servidor MCP individual.

    Maneja la comunicación stdio/HTTP con el servidor MCP usando JSON-RPC 2.0.
    Incluye: timeout por request, reconexión automática, métricas de salud.
    """

    def __init__(self, config: MCPServerConfig) -> None:
        self.config = config
        self.process: subprocess.Popen[str] | None = None
        self._request_id: int = 0
        self._tools: list[MCPToolInfo] = []
        self._initialized: bool = False
        self._lock: asyncio.Lock = asyncio.Lock()
        # Métricas de salud
        self._total_calls: int = 0
        self._successful_calls: int = 0
        self._failed_calls: int = 0
        self._consecutive_failures: int = 0
        self._last_success: float = 0.0
        self._last_failure: float = 0.0
        self._last_error: str = ""
        self._total_latency_ms: float = 0.0
        self._connect_time: float = 0.0
        self._reconnect_count: int = 0

    @property
    def name(self) -> str:
        return self.config.name

    @property
    def is_remote(self) -> bool:
        """Es un servidor HTTP remoto."""
        return self.config.transport in ("http", "url")

    @property
    def is_connected(self) -> bool:
        if self.is_remote:
            return self._initialized
        return self.process is not None and self.process.poll() is None

    @property
    def health_status(self) -> dict[str, Any]:
        """Estado de salud del cliente."""
        success_rate = (
            self._successful_calls / self._total_calls * 100 if self._total_calls > 0 else 0.0
        )
        avg_latency = self._total_latency_ms / self._total_calls if self._total_calls > 0 else 0.0
        return {
            "name": self.name,
            "transport": self.config.transport,
            "connected": self.is_connected,
            "initialized": self._initialized,
            "total_calls": self._total_calls,
            "successful_calls": self._successful_calls,
            "failed_calls": self._failed_calls,
            "success_rate_pct": round(success_rate, 1),
            "consecutive_failures": self._consecutive_failures,
            "avg_latency_ms": round(avg_latency, 1),
            "last_error": self._last_error,
            "reconnect_count": self._reconnect_count,
            "tools_count": len(self._tools),
        }

    async def connect(self) -> bool:
        """Inicia el servidor MCP y establece conexión."""
        if self.is_connected:
            return True

        if self.is_remote:
            return await self._connect_http()
        return await self._connect_stdio()

    async def _connect_stdio(self) -> bool:
        """Conexión via stdio (servidores locales)."""
        try:
            env = os.environ.copy()
            for key, value in self.config.env.items():
                if value.startswith("${") and value.endswith("}"):
                    env_key = value[2:-1]
                    env[key] = os.environ.get(env_key, "")
                else:
                    env[key] = value

            cmd = [self.config.command] + self.config.args
            logger.info("Connecting to MCP server: %s -> %s", self.name, " ".join(cmd))

            self.process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=True,
                bufsize=1,
            )

            await asyncio.wait_for(
                self._initialize(),
                timeout=self.config.connect_timeout,
            )
            await asyncio.wait_for(
                self._fetch_tools(),
                timeout=self.config.connect_timeout,
            )

            self._initialized = True
            self._connect_time = time.monotonic()
            logger.info("MCP server %s connected with %d tools", self.name, len(self._tools))
            return True

        except TimeoutError:
            logger.error("Timeout connecting to %s (%.0fs)", self.name, self.config.connect_timeout)
            await self.disconnect()
            return False
        except Exception as e:
            logger.error("Error connecting to %s: %s", self.name, e)
            await self.disconnect()
            return False

    async def _connect_http(self) -> bool:
        """Conexión via HTTP (servidores remotos). Respeta HTTPS_PROXY / NO_PROXY."""
        try:
            import urllib.error
            import urllib.request

            opener = _build_url_opener()
            health_url = self.config.url.replace("/mcp", "/health")
            req = urllib.request.Request(health_url, method="GET")
            for key, value in self.config.headers.items():
                req.add_header(key, value)

            response = await asyncio.get_running_loop().run_in_executor(
                None, lambda: opener.open(req, timeout=int(self.config.connect_timeout))
            )

            if response.status == 200:
                # Inicializar via POST /mcp
                init_result = await self._send_http_request(
                    "initialize",
                    {
                        "protocolVersion": "2024-11-05",
                        "capabilities": {},
                        "clientInfo": {"name": "antigravity-mcp-client", "version": "2.0.0"},
                    },
                )

                if init_result:
                    # Fetch tools
                    tools_result = await self._send_http_request("tools/list")
                    if tools_result:
                        self._tools = [
                            MCPToolInfo(
                                name=tool.get("name", ""),
                                description=tool.get("description", ""),
                                input_schema=tool.get("inputSchema", {}),
                                server_name=self.name,
                            )
                            for tool in tools_result.get("tools", [])
                        ]

                    self._initialized = True
                    self._connect_time = time.monotonic()
                    logger.info(
                        "MCP remote %s connected with %d tools via HTTP",
                        self.name,
                        len(self._tools),
                    )
                    return True

            logger.error("HTTP health check failed for %s: status %d", self.name, response.status)
            return False

        except Exception as e:
            logger.error("Error connecting to remote %s: %s", self.name, e)
            self._last_error = str(e)
            return False

    async def disconnect(self) -> None:
        """Cierra la conexión con el servidor MCP."""
        if self.process:
            try:
                self.process.terminate()
                loop = asyncio.get_running_loop()
                await asyncio.wait_for(
                    loop.run_in_executor(None, self.process.wait),
                    timeout=5.0,
                )
            except TimeoutError:
                try:
                    self.process.kill()
                except Exception:
                    pass
            except Exception:
                try:
                    self.process.kill()
                except Exception:
                    pass
            self.process = None

        self._initialized = False
        self._tools = []

    async def reconnect(self) -> bool:
        """Reconecta con backoff exponencial."""
        for attempt in range(MAX_RECONNECT_ATTEMPTS):
            delay = RECONNECT_BASE_DELAY * (2**attempt)
            logger.warning(
                "Reconnect attempt %d/%d for %s (delay: %.1fs)",
                attempt + 1,
                MAX_RECONNECT_ATTEMPTS,
                self.name,
                delay,
            )
            await self.disconnect()
            await asyncio.sleep(delay)

            if await self.connect():
                self._reconnect_count += 1
                self._consecutive_failures = 0
                logger.info("Reconnected to %s after %d attempts", self.name, attempt + 1)
                return True

        logger.error(
            "Failed to reconnect to %s after %d attempts", self.name, MAX_RECONNECT_ATTEMPTS
        )
        return False

    async def _send_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Envía una solicitud JSON-RPC al servidor stdio con timeout."""
        async with self._lock:
            if not self.is_connected:
                raise RuntimeError(f"Not connected to {self.name}")

            if self.is_remote:
                return await self._send_http_request(method, params) or {}

            assert self.process is not None
            self._request_id += 1
            request = {
                "jsonrpc": "2.0",
                "id": self._request_id,
                "method": method,
            }
            if params:
                request["params"] = params

            request_line = json.dumps(request) + "\n"
            assert self.process.stdin is not None
            assert self.process.stdout is not None

            # Escribir con protección
            try:
                self.process.stdin.write(request_line)
                self.process.stdin.flush()
            except (BrokenPipeError, OSError) as e:
                raise RuntimeError(f"Broken pipe to {self.name}: {e}") from e

            # Leer respuesta con timeout
            loop = asyncio.get_running_loop()
            try:
                response_line = await asyncio.wait_for(
                    loop.run_in_executor(None, self.process.stdout.readline),
                    timeout=self.config.request_timeout,
                )
            except TimeoutError:
                raise RuntimeError(
                    f"Timeout ({self.config.request_timeout}s) waiting for response "
                    f"from {self.name} (method: {method})"
                ) from None

            if not response_line:
                raise RuntimeError(f"No response from {self.name} (process may have died)")

            response = json.loads(response_line)

            if "error" in response:
                error_info = response["error"]
                msg = (
                    error_info.get("message", str(error_info))
                    if isinstance(error_info, dict)
                    else str(error_info)
                )
                raise RuntimeError(f"MCP error from {self.name}: {msg}")

            return response.get("result", {})

    async def _send_http_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any] | None:
        """Envía una solicitud JSON-RPC via HTTP. Respeta HTTPS_PROXY / NO_PROXY."""
        import urllib.error
        import urllib.request

        opener = _build_url_opener()
        self._request_id += 1
        request_body = {
            "jsonrpc": "2.0",
            "id": self._request_id,
            "method": method,
        }
        if params:
            request_body["params"] = params

        data = json.dumps(request_body).encode("utf-8")
        req = urllib.request.Request(
            self.config.url,
            data=data,
            method="POST",
        )
        req.add_header("Content-Type", "application/json")
        for key, value in self.config.headers.items():
            req.add_header(key, value)

        try:
            response = await asyncio.get_running_loop().run_in_executor(
                None, lambda: opener.open(req, timeout=int(self.config.request_timeout))
            )
            body = json.loads(response.read().decode("utf-8"))

            if isinstance(body, dict) and "error" in body:
                error_info = body["error"]
                msg = (
                    error_info.get("message", str(error_info))
                    if isinstance(error_info, dict)
                    else str(error_info)
                )
                raise RuntimeError(f"MCP HTTP error from {self.name}: {msg}")

            return body.get("result", body) if isinstance(body, dict) else body

        except urllib.error.HTTPError as e:
            raise RuntimeError(f"HTTP {e.code} from {self.name}: {e.reason}") from e
        except urllib.error.URLError as e:
            raise RuntimeError(f"Connection error to {self.name}: {e.reason}") from e

    async def _initialize(self) -> None:
        """Inicializa el protocolo MCP."""
        await self._send_request(
            "initialize",
            {
                "protocolVersion": "2024-11-05",
                "capabilities": {},
                "clientInfo": {"name": "antigravity-mcp-client", "version": "2.0.0"},
            },
        )

        # Enviar notificación de inicializado
        if self.process and self.process.stdin:
            notify = {"jsonrpc": "2.0", "method": "notifications/initialized"}
            self.process.stdin.write(json.dumps(notify) + "\n")
            self.process.stdin.flush()

    async def _fetch_tools(self) -> None:
        """Obtiene la lista de herramientas del servidor."""
        result = await self._send_request("tools/list")

        self._tools = [
            MCPToolInfo(
                name=tool.get("name", ""),
                description=tool.get("description", ""),
                input_schema=tool.get("inputSchema", {}),
                server_name=self.name,
            )
            for tool in result.get("tools", [])
        ]

    def get_tools(self) -> list[MCPToolInfo]:
        """Retorna las herramientas disponibles."""
        return self._tools

    async def call_tool(self, tool_name: str, arguments: dict[str, Any]) -> MCPCallResult:
        """Llama una herramienta del servidor con timeout, retry y métricas."""
        start_time = time.monotonic()
        self._total_calls += 1
        retries = 0

        try:
            if not self._initialized:
                await self.connect()

            result = await self._send_request(
                "tools/call", {"name": tool_name, "arguments": arguments}
            )

            execution_time = (time.monotonic() - start_time) * 1000

            # Extraer contenido
            content = result.get("content", [])
            if content and isinstance(content, list):
                text_content = "\n".join(
                    item.get("text", "") for item in content if item.get("type") == "text"
                )
                content = text_content or content

            # Actualizar métricas
            self._successful_calls += 1
            self._consecutive_failures = 0
            self._last_success = time.monotonic()
            self._total_latency_ms += execution_time

            return MCPCallResult(
                success=True,
                content=content,
                server_name=self.name,
                tool_name=tool_name,
                execution_time_ms=execution_time,
                retries=retries,
                transport=self.config.transport,
            )

        except RuntimeError as e:
            error_msg = str(e)
            # Intentar reconectar si parece un problema de conexión
            if any(
                kw in error_msg.lower()
                for kw in ("broken pipe", "not connected", "process may have died", "timeout")
            ):
                logger.warning(
                    "Connection issue with %s, attempting reconnect: %s", self.name, error_msg
                )
                if await self.reconnect():
                    retries = 1
                    try:
                        result = await self._send_request(
                            "tools/call", {"name": tool_name, "arguments": arguments}
                        )
                        execution_time = (time.monotonic() - start_time) * 1000
                        content = result.get("content", [])
                        if content and isinstance(content, list):
                            text_content = "\n".join(
                                item.get("text", "")
                                for item in content
                                if item.get("type") == "text"
                            )
                            content = text_content or content

                        self._successful_calls += 1
                        self._consecutive_failures = 0
                        self._last_success = time.monotonic()
                        self._total_latency_ms += execution_time

                        return MCPCallResult(
                            success=True,
                            content=content,
                            server_name=self.name,
                            tool_name=tool_name,
                            execution_time_ms=execution_time,
                            retries=retries,
                            transport=self.config.transport,
                        )
                    except Exception as retry_err:
                        error_msg = str(retry_err)

            execution_time = (time.monotonic() - start_time) * 1000
            self._failed_calls += 1
            self._consecutive_failures += 1
            self._last_failure = time.monotonic()
            self._last_error = error_msg
            self._total_latency_ms += execution_time
            logger.error("Error calling %s on %s: %s", tool_name, self.name, error_msg)

            return MCPCallResult(
                success=False,
                content=None,
                error=error_msg,
                server_name=self.name,
                tool_name=tool_name,
                execution_time_ms=execution_time,
                retries=retries,
                transport=self.config.transport,
            )

        except Exception as e:
            execution_time = (time.monotonic() - start_time) * 1000
            self._failed_calls += 1
            self._consecutive_failures += 1
            self._last_failure = time.monotonic()
            self._last_error = str(e)
            self._total_latency_ms += execution_time
            logger.error("Error calling %s on %s: %s", tool_name, self.name, e)

            return MCPCallResult(
                success=False,
                content=None,
                error=str(e),
                server_name=self.name,
                tool_name=tool_name,
                execution_time_ms=execution_time,
                retries=retries,
                transport=self.config.transport,
            )


# =============================================================================
# MCP CLIENT MANAGER (Múltiples servidores)
# =============================================================================


class MCPClientManager:
    """
    Manager para múltiples clientes MCP.

    Carga configuración automáticamente y maneja conexiones lazy.

    Uso:
        async with MCPClientManager() as manager:
            tools = await manager.list_all_tools()
            result = await manager.call_tool("context7", "resolve", {"libraryName": "react"})
    """

    _instance: MCPClientManager | None = None

    def __init__(self, config_path: Path | None = None) -> None:
        self.config_path: Path | None = config_path or _find_mcp_config()
        self.servers: dict[str, MCPServerConfig] = {}
        self.clients: dict[str, MCPClient] = {}
        self._loaded: bool = False

    async def __aenter__(self) -> MCPClientManager:
        await self.load_config()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: TracebackType | None,
    ) -> None:
        await self.disconnect_all()

    def load_config_sync(self) -> None:
        """Carga configuración de forma síncrona."""
        if self._loaded:
            return

        if self.config_path is None or not self.config_path.exists():
            logger.warning("No MCP configuration file found")
            self._loaded = True
            return

        try:
            content = self.config_path.read_text(encoding="utf-8")
            data = json.loads(content)

            mcp_servers = data.get("mcpServers", {})

            for name, server_data in mcp_servers.items():
                # Saltar el servidor de antigravity-agents (somos nosotros)
                if name == "antigravity-agents":
                    continue

                config = MCPServerConfig.from_dict(name, server_data)
                # Aceptar servidores con command (stdio) o url (HTTP remoto)
                if config.enabled and (config.command or config.url):
                    self.servers[name] = config

            logger.info("Loaded %d MCP servers from %s", len(self.servers), self.config_path)
            self._loaded = True

        except Exception as e:
            logger.error("Error loading MCP config: %s", e)
            self._loaded = True

    async def load_config(self) -> None:
        """Carga configuración de servidores MCP."""
        self.load_config_sync()

    async def get_client(self, server_name: str) -> MCPClient | None:
        """Obtiene o crea cliente para un servidor."""
        if server_name not in self.servers:
            logger.warning(f"Servidor MCP '{server_name}' no configurado")
            return None

        if server_name not in self.clients:
            client = MCPClient(self.servers[server_name])
            if await client.connect():
                self.clients[server_name] = client
            else:
                return None

        return self.clients.get(server_name)

    async def list_servers(self) -> list[str]:
        """Lista servidores configurados."""
        await self.load_config()
        return list(self.servers.keys())

    async def list_all_tools(self) -> list[MCPToolInfo]:
        """Lista todas las herramientas de todos los servidores."""
        await self.load_config()

        all_tools = []
        for server_name in self.servers:
            client = await self.get_client(server_name)
            if client:
                all_tools.extend(client.get_tools())

        return all_tools

    async def list_tools(self, server_name: str) -> list[MCPToolInfo]:
        """Lista herramientas de un servidor específico."""
        client = await self.get_client(server_name)
        if client:
            return client.get_tools()
        return []

    async def call_tool(
        self, server_name: str, tool_name: str, arguments: dict[str, Any]
    ) -> MCPCallResult:
        """Llama una herramienta de un servidor específico."""
        client = await self.get_client(server_name)
        if not client:
            return MCPCallResult(
                success=False,
                content=None,
                error=f"Servidor '{server_name}' no disponible",
                server_name=server_name,
                tool_name=tool_name,
            )

        return await client.call_tool(tool_name, arguments)

    async def call_tool_auto(self, tool_name: str, arguments: dict[str, Any]) -> MCPCallResult:
        """Llama una herramienta buscando automáticamente en qué servidor está."""
        await self.load_config()

        for server_name in self.servers:
            client = await self.get_client(server_name)
            if client:
                for tool in client.get_tools():
                    if tool.name == tool_name:
                        return await client.call_tool(tool_name, arguments)

        return MCPCallResult(
            success=False,
            content=None,
            error=f"Herramienta '{tool_name}' no encontrada en ningún servidor",
            tool_name=tool_name,
        )

    async def disconnect_all(self) -> None:
        """Desconecta todos los clientes."""
        for client in self.clients.values():
            await client.disconnect()
        self.clients.clear()

    def get_tools_for_llm(self) -> list[dict[str, Any]]:
        """
        Retorna definiciones de herramientas en formato para LLM.

        Compatible con el formato de autonomous_loop.py
        """
        tools = []
        for server_name, client in self.clients.items():
            for tool in client.get_tools():
                tools.append(
                    {
                        "name": f"mcp_{server_name}_{tool.name}",
                        "description": f"[{server_name}] {tool.description}",
                        "input_schema": tool.input_schema,
                    }
                )
        return tools

    async def health_check_all(self) -> dict[str, Any]:
        """Verifica la salud de todas las conexiones MCP.

        Returns:
            Reporte con estado de cada servidor y resumen global.
        """
        await self.load_config()
        report: dict[str, Any] = {
            "timestamp": datetime.now().isoformat(),
            "total_servers": len(self.servers),
            "connected_servers": 0,
            "servers": {},
        }

        for name in self.servers:
            client = self.clients.get(name)
            if client:
                status = client.health_status
                report["servers"][name] = status
                if status["connected"]:
                    report["connected_servers"] += 1
            else:
                report["servers"][name] = {
                    "name": name,
                    "transport": self.servers[name].transport,
                    "connected": False,
                    "initialized": False,
                    "status": "not_started",
                }

        total = report["total_servers"]
        connected = report["connected_servers"]
        if total > 0:
            report["health_pct"] = round(connected / total * 100, 1)
        else:
            report["health_pct"] = 0.0

        report["status"] = (
            "healthy" if connected == total else "degraded" if connected > 0 else "unhealthy"
        )

        return report

    async def reconnect_unhealthy(self) -> list[str]:
        """Reconecta servidores con fallos consecutivos.

        Returns:
            Lista de servidores reconectados exitosamente.
        """
        reconnected = []
        for name, client in list(self.clients.items()):
            if client._consecutive_failures >= 3 or not client.is_connected:
                logger.warning("Attempting reconnect for unhealthy server: %s", name)
                if await client.reconnect():
                    reconnected.append(name)
                else:
                    # Remover cliente muerto
                    await client.disconnect()
                    del self.clients[name]
                    logger.error("Removed dead client: %s", name)
        return reconnected


# =============================================================================
# SINGLETON & HELPERS
# =============================================================================

_manager: MCPClientManager | None = None


async def get_mcp_manager() -> MCPClientManager:
    """Obtiene instancia singleton del manager."""
    global _manager
    if _manager is None:
        _manager = MCPClientManager()
        await _manager.load_config()
    return _manager


def get_mcp_manager_sync() -> MCPClientManager:
    """Obtiene manager de forma síncrona (sin conectar)."""
    global _manager
    if _manager is None:
        _manager = MCPClientManager()
        _manager.load_config_sync()
    return _manager


# =============================================================================
# HERRAMIENTAS PRE-CONFIGURADAS
# =============================================================================


class MCPTools:
    """
    Acceso directo a herramientas MCP comunes.

    Uso:
        tools = MCPTools()

        # Context7 - Documentación de librerías
        docs = await tools.context7_resolve("react")
        docs = await tools.context7_get_docs("react", "/docs/hooks/useState")

        # GitHub
        issues = await tools.github_list_issues("owner/repo")

        # Playwright
        screenshot = await tools.playwright_screenshot("https://example.com")
    """

    def __init__(self, manager: MCPClientManager | None = None) -> None:
        self._manager: MCPClientManager | None = manager

    async def _get_manager(self) -> MCPClientManager:
        if self._manager is None:
            self._manager = await get_mcp_manager()
        return self._manager

    # -------------------------------------------------------------------------
    # Context7 - Documentación de librerías
    # -------------------------------------------------------------------------

    async def context7_resolve(self, library_name: str) -> MCPCallResult:
        """
        Resuelve una librería y obtiene su ID en Context7.

        Args:
            library_name: Nombre de la librería (react, nextjs, fastapi, etc.)
        """
        manager = await self._get_manager()
        return await manager.call_tool("context7", "resolve", {"libraryName": library_name})

    async def context7_get_docs(
        self, library_name: str, topic: str = "/", tokens: int = 10000
    ) -> MCPCallResult:
        """
        Obtiene documentación de una librería.

        Args:
            library_name: Nombre de la librería
            topic: Ruta al topic (ej: /docs/hooks/useState)
            tokens: Máximo de tokens a retornar
        """
        manager = await self._get_manager()
        return await manager.call_tool(
            "context7",
            "get-library-docs",
            {"context7CompatibleLibraryID": f"/{library_name}", "topic": topic, "tokens": tokens},
        )

    # -------------------------------------------------------------------------
    # GitHub
    # -------------------------------------------------------------------------

    async def github_list_issues(self, repo: str, state: str = "open") -> MCPCallResult:
        """Lista issues de un repositorio."""
        manager = await self._get_manager()
        return await manager.call_tool("github", "list_issues", {"repo": repo, "state": state})

    async def github_create_issue(self, repo: str, title: str, body: str) -> MCPCallResult:
        """Crea un issue en un repositorio."""
        manager = await self._get_manager()
        return await manager.call_tool(
            "github", "create_issue", {"repo": repo, "title": title, "body": body}
        )

    async def github_create_pr(
        self, repo: str, title: str, body: str, head: str, base: str = "main"
    ) -> MCPCallResult:
        """Crea un pull request."""
        manager = await self._get_manager()
        return await manager.call_tool(
            "github",
            "create_pull_request",
            {"repo": repo, "title": title, "body": body, "head": head, "base": base},
        )

    # -------------------------------------------------------------------------
    # Playwright - Browser automation
    # -------------------------------------------------------------------------

    async def playwright_navigate(self, url: str) -> MCPCallResult:
        """Navega a una URL."""
        manager = await self._get_manager()
        return await manager.call_tool("playwright", "navigate", {"url": url})

    async def playwright_screenshot(
        self, url: str | None = None, full_page: bool = False
    ) -> MCPCallResult:
        """Captura screenshot de página actual o URL."""
        manager = await self._get_manager()
        params: dict[str, Any] = {"fullPage": full_page}
        if url:
            await self.playwright_navigate(url)
        return await manager.call_tool("playwright", "screenshot", params)

    async def playwright_click(self, selector: str) -> MCPCallResult:
        """Hace click en un elemento."""
        manager = await self._get_manager()
        return await manager.call_tool("playwright", "click", {"selector": selector})

    # -------------------------------------------------------------------------
    # Semgrep - Análisis de seguridad
    # -------------------------------------------------------------------------

    async def semgrep_scan(self, path: str = ".", config: str = "auto") -> MCPCallResult:
        """Escanea código con Semgrep."""
        manager = await self._get_manager()
        return await manager.call_tool("semgrep", "scan", {"path": path, "config": config})

    # -------------------------------------------------------------------------
    # Filesystem
    # -------------------------------------------------------------------------

    async def fs_read_file(self, path: str) -> MCPCallResult:
        """Lee un archivo."""
        manager = await self._get_manager()
        return await manager.call_tool("filesystem", "read_file", {"path": path})

    async def fs_write_file(self, path: str, content: str) -> MCPCallResult:
        """Escribe un archivo."""
        manager = await self._get_manager()
        return await manager.call_tool(
            "filesystem", "write_file", {"path": path, "content": content}
        )

    async def fs_list_directory(self, path: str = ".") -> MCPCallResult:
        """Lista contenido de directorio."""
        manager = await self._get_manager()
        return await manager.call_tool("filesystem", "list_directory", {"path": path})

    # -------------------------------------------------------------------------
    # Git
    # -------------------------------------------------------------------------

    async def git_status(self) -> MCPCallResult:
        """Obtiene estado de git."""
        manager = await self._get_manager()
        return await manager.call_tool("git", "status", {})

    async def git_diff(self, ref: str = "HEAD") -> MCPCallResult:
        """Obtiene diff de git."""
        manager = await self._get_manager()
        return await manager.call_tool("git", "diff", {"ref": ref})

    async def git_log(self, limit: int = 10) -> MCPCallResult:
        """Obtiene log de git."""
        manager = await self._get_manager()
        return await manager.call_tool("git", "log", {"maxCount": limit})

    # -------------------------------------------------------------------------
    # Memory
    # -------------------------------------------------------------------------

    async def memory_store(self, key: str, value: Any) -> MCPCallResult:
        """Guarda valor en memoria."""
        manager = await self._get_manager()
        return await manager.call_tool(
            "memory", "create_entities", {"entities": [{"name": key, "content": json.dumps(value)}]}
        )

    async def memory_retrieve(self, key: str) -> MCPCallResult:
        """Recupera valor de memoria."""
        manager = await self._get_manager()
        return await manager.call_tool("memory", "search_nodes", {"query": key})

    # -------------------------------------------------------------------------
    # Fetch - Web content
    # -------------------------------------------------------------------------

    async def fetch_url(self, url: str) -> MCPCallResult:
        """Obtiene contenido de una URL."""
        manager = await self._get_manager()
        return await manager.call_tool("fetch", "fetch", {"url": url})


# =============================================================================
# CLI
# =============================================================================


async def _cmd_list_servers(manager: MCPClientManager) -> None:
    """Imprime los servidores MCP configurados."""
    servers = await manager.list_servers()
    print(f"Servidores MCP configurados ({len(servers)}):")
    for name in servers:
        config = manager.servers[name]
        print(f"  - {name}: {config.description or config.command}")


async def _cmd_list_tools(manager: MCPClientManager, server: str) -> None:
    """Imprime las herramientas de un servidor MCP."""
    tools = await manager.list_tools(server)
    print(f"Herramientas de {server} ({len(tools)}):")
    for tool in tools:
        print(f"  - {tool.name}: {tool.description[:60]}...")


async def _cmd_list_all_tools(manager: MCPClientManager) -> None:
    """Imprime todas las herramientas agrupadas por servidor."""
    tools = await manager.list_all_tools()
    print(f"Todas las herramientas MCP ({len(tools)}):")
    current_server = ""
    for tool in tools:
        if tool.server_name != current_server:
            current_server = tool.server_name
            print(f"\n[{current_server}]")
        print(f"  - {tool.name}: {tool.description[:50]}...")


async def _cmd_call(manager: MCPClientManager, call_args: list[str]) -> None:
    """Llama una herramienta y muestra el resultado."""
    server, tool_name, args_json = call_args
    arguments = json.loads(args_json)
    result = await manager.call_tool(server, tool_name, arguments)
    print(f"Resultado ({result.execution_time_ms:.0f}ms):")
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


async def _cmd_context7(manager: MCPClientManager, library: str) -> None:
    """Busca documentación de una librería vía Context7."""
    tools = MCPTools(manager)  # type: ignore[assignment]  # MCPTools: dynamic wrapper
    result = await tools.context7_get_docs(library)  # type: ignore[attr-defined]  # dynamic method via MCP
    if result.success:
        print(f"Documentación de {library}:")
        print(result.content[:2000])
    else:
        print(f"Error: {result.error}")


async def main() -> None:
    """CLI para testing."""
    import argparse

    parser = argparse.ArgumentParser(description="MCP Client para Antigravity")
    parser.add_argument(
        "--list-servers", action="store_true", help="Listar servidores configurados"
    )
    parser.add_argument("--list-tools", metavar="SERVER", help="Listar herramientas de un servidor")
    parser.add_argument(
        "--list-all-tools", action="store_true", help="Listar todas las herramientas"
    )
    parser.add_argument(
        "--call", nargs=3, metavar=("SERVER", "TOOL", "ARGS_JSON"), help="Llamar una herramienta"
    )
    parser.add_argument("--context7", metavar="LIBRARY", help="Buscar docs de librería en Context7")

    args = parser.parse_args()

    async with MCPClientManager() as manager:
        if args.list_servers:
            await _cmd_list_servers(manager)
        elif args.list_tools:
            await _cmd_list_tools(manager, args.list_tools)
        elif args.list_all_tools:
            await _cmd_list_all_tools(manager)
        elif args.call:
            await _cmd_call(manager, args.call)
        elif args.context7:
            await _cmd_context7(manager, args.context7)
        else:
            parser.print_help()


if __name__ == "__main__":
    asyncio.run(main())
