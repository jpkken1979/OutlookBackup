"""Lazy MCP connector runtime built on the official Python SDK."""

from __future__ import annotations

import asyncio
import os
from contextlib import AsyncExitStack
from datetime import timedelta
from pathlib import Path
from typing import Any

import httpx
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from mcp.client.streamable_http import streamable_http_client

from .models import ConnectorManifest, ConnectorStatus
from .registry import ConnectorRegistry
from .internal import INTERNAL_OPERATIONS, InternalConnectorError, call_internal


class ConnectorRuntimeError(RuntimeError):
    """Structured connector failure used by the broker envelope."""

    def __init__(
        self,
        message: str,
        *,
        status: ConnectorStatus = ConnectorStatus.ERROR,
        retryable: bool = False,
    ):
        super().__init__(message)
        self.status = status
        self.retryable = retryable


class LazyConnectorRuntime:
    """Starts no connector until a concrete tool is invoked."""

    def __init__(
        self,
        registry: ConnectorRegistry,
        project_root: Path,
        timeout_seconds: float = 30.0,
    ):
        self.registry = registry
        self.project_root = project_root.resolve()
        self.timeout_seconds = timeout_seconds

    def _auth_headers(self, connector: ConnectorManifest) -> dict[str, str]:
        headers: dict[str, str] = {}
        for header, environment_name in connector.auth.header_from_env.items():
            value = os.environ.get(environment_name)
            if not value:
                continue
            if header.lower() == "authorization" and not value.lower().startswith(
                ("bearer ", "basic ")
            ):
                value = f"Bearer {value}"
            headers[header] = value
        return headers

    async def call(
        self,
        connector: ConnectorManifest,
        operation: str,
        arguments: dict[str, Any],
    ) -> dict[str, Any]:
        if connector.verification != "verified":
            raise ConnectorRuntimeError(
                f"Connector '{connector.id}' has no verified pinned artifact",
                status=ConnectorStatus.UNVERIFIED,
            )

        missing = self.registry.required_secrets_missing(connector)
        if missing:
            raise ConnectorRuntimeError(
                f"Connector '{connector.id}' requires authentication",
                status=ConnectorStatus.AUTH_REQUIRED,
            )

        transport = self.registry.transport_values(connector)
        try:
            async with asyncio.timeout(self.timeout_seconds):
                if transport["type"] == "internal":
                    try:
                        return await asyncio.to_thread(
                            call_internal,
                            self.project_root,
                            connector.id,
                            operation,
                            arguments,
                        )
                    except InternalConnectorError as exc:
                        raise ConnectorRuntimeError(
                            str(exc),
                            status=exc.status,
                            retryable=exc.retryable,
                        ) from exc
                async with AsyncExitStack() as stack:
                    if transport["type"] == "streamable_http":
                        url = transport.get("url")
                        if not url:
                            raise ConnectorRuntimeError("Connector URL is not configured")
                        http_client = await stack.enter_async_context(
                            httpx.AsyncClient(
                                headers=self._auth_headers(connector),
                                timeout=self.timeout_seconds,
                                follow_redirects=False,
                            )
                        )
                        read_stream, write_stream, _ = await stack.enter_async_context(
                            streamable_http_client(url, http_client=http_client)
                        )
                    elif transport["type"] == "stdio":
                        command = transport.get("command")
                        if not command:
                            raise ConnectorRuntimeError("Connector command is not configured")
                        parameters = StdioServerParameters(
                            command=command,
                            args=transport.get("args", []),
                            cwd=transport.get("cwd"),
                            env={},
                        )
                        read_stream, write_stream = await stack.enter_async_context(
                            stdio_client(parameters)
                        )
                    else:
                        raise ConnectorRuntimeError(
                            f"Connector '{connector.id}' requires a managed adapter",
                            status=ConnectorStatus.OFFLINE,
                        )

                    session = await stack.enter_async_context(
                        ClientSession(read_stream, write_stream)
                    )
                    initialize_result = await session.initialize()
                    result = await session.call_tool(
                        operation,
                        arguments,
                        read_timeout_seconds=timedelta(seconds=self.timeout_seconds),
                    )
                    return {
                        "connector": connector.id,
                        "protocol_version": initialize_result.protocolVersion,
                        "server": initialize_result.serverInfo.model_dump(),
                        "result": result.model_dump(mode="json"),
                    }
        except ConnectorRuntimeError:
            raise
        except TimeoutError as exc:
            raise ConnectorRuntimeError(
                f"Connector '{connector.id}' timed out",
                status=ConnectorStatus.OFFLINE,
                retryable=True,
            ) from exc
        except (httpx.HTTPError, OSError) as exc:
            raise ConnectorRuntimeError(
                f"Connector '{connector.id}' is offline: {type(exc).__name__}",
                status=ConnectorStatus.OFFLINE,
                retryable=True,
            ) from exc

    async def probe(self, connector: ConnectorManifest) -> dict[str, Any]:
        """Perform initialize/list without executing a connector tool."""

        if connector.verification != "verified":
            raise ConnectorRuntimeError(
                f"Connector '{connector.id}' has no verified pinned artifact",
                status=ConnectorStatus.UNVERIFIED,
            )
        missing = self.registry.required_secrets_missing(connector)
        if missing:
            raise ConnectorRuntimeError(
                f"Connector '{connector.id}' requires authentication",
                status=ConnectorStatus.AUTH_REQUIRED,
            )

        transport = self.registry.transport_values(connector)
        try:
            async with asyncio.timeout(self.timeout_seconds):
                if transport["type"] == "internal":
                    return {
                        "connector": connector.id,
                        "status": ConnectorStatus.READY.value,
                        "protocol_version": "internal-v1",
                        "server": {
                            "name": f"antigravity-{connector.id}",
                            "version": connector.version,
                        },
                        "tool_count": len(INTERNAL_OPERATIONS.get(connector.id, ())),
                        "operations": list(INTERNAL_OPERATIONS.get(connector.id, ())),
                    }
                async with AsyncExitStack() as stack:
                    if transport["type"] == "streamable_http":
                        http_client = await stack.enter_async_context(
                            httpx.AsyncClient(
                                headers=self._auth_headers(connector),
                                timeout=self.timeout_seconds,
                                follow_redirects=False,
                            )
                        )
                        streams = await stack.enter_async_context(
                            streamable_http_client(
                                transport["url"],
                                http_client=http_client,
                            )
                        )
                        read_stream, write_stream, _ = streams
                    elif transport["type"] == "stdio":
                        parameters = StdioServerParameters(
                            command=transport["command"],
                            args=transport.get("args", []),
                            cwd=transport.get("cwd"),
                            env={},
                        )
                        read_stream, write_stream = await stack.enter_async_context(
                            stdio_client(parameters)
                        )
                    else:
                        raise ConnectorRuntimeError(
                            f"Connector '{connector.id}' requires a managed adapter",
                            status=ConnectorStatus.OFFLINE,
                        )
                    session = await stack.enter_async_context(
                        ClientSession(read_stream, write_stream)
                    )
                    initialized = await session.initialize()
                    tools = await session.list_tools()
                    return {
                        "connector": connector.id,
                        "status": ConnectorStatus.READY.value,
                        "protocol_version": initialized.protocolVersion,
                        "server": initialized.serverInfo.model_dump(),
                        "tool_count": len(tools.tools),
                    }
        except ConnectorRuntimeError:
            raise
        except TimeoutError as exc:
            raise ConnectorRuntimeError(
                f"Connector '{connector.id}' timed out during handshake",
                status=ConnectorStatus.OFFLINE,
                retryable=True,
            ) from exc
        except (httpx.HTTPError, OSError) as exc:
            raise ConnectorRuntimeError(
                f"Connector '{connector.id}' handshake failed: {type(exc).__name__}",
                status=ConnectorStatus.OFFLINE,
                retryable=True,
            ) from exc
