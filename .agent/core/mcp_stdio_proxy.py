"""Portable stdio shim for clients without Streamable HTTP support.

This module intentionally lives outside the historical ``mcp`` package.  The
project package and the official SDK share that top-level name in source mode;
keeping the portable shim under ``core`` lets PyInstaller freeze it without
shadowing the official SDK or collecting the whole gateway package.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from typing import Any, cast

import httpx

from core.gateway_client import resolve_gateway_token

DEFAULT_BROKER_URL: str = "http://127.0.0.1:4747/mcp"


def _read_gateway_token() -> str:
    """Read the gateway authentication token from the local credential store.

    Returns:
        str: The gateway token or empty string if unavailable.
    """
    return resolve_gateway_token()


class StdioBrokerProxy:
    """Translates newline-delimited stdio JSON-RPC to Streamable HTTP."""

    def __init__(self, broker_url: str = DEFAULT_BROKER_URL) -> None:
        """Initialize the stdio broker proxy.

        Args:
            broker_url: HTTP endpoint of the MCP broker (default: localhost:4747).
        """
        self.broker_url: str = broker_url
        self.session_id: str | None = None
        self.protocol_version: str | None = None
        self._stdout_lock: asyncio.Lock = asyncio.Lock()
        self._notification_task: asyncio.Task[None] | None = None
        self._client: httpx.AsyncClient = httpx.AsyncClient(timeout=130.0)
        # Se guarda el initialize original para poder rehacer la sesion sin
        # depender de que el cliente vuelva a mandarlo (ver _reinitialize).
        self._init_payload: dict[str, Any] | None = None

    def _headers(self) -> dict[str, str]:
        """Build HTTP headers for broker requests.

        Returns:
            dict[str, str]: HTTP headers including auth token and session info.
        """
        headers: dict[str, str] = {
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        }
        # Resolve on every request so rotating the encrypted local credential
        # never requires reinjecting or restarting IDE clients.
        token: str = _read_gateway_token()
        if token:
            headers["X-API-Key"] = token
        if self.session_id:
            headers["MCP-Session-Id"] = self.session_id
        if self.protocol_version:
            headers["MCP-Protocol-Version"] = self.protocol_version
        return headers

    async def _write_message(self, payload: dict[str, Any]) -> None:
        """Write a JSON-RPC message to stdout.

        Args:
            payload: JSON-RPC message dict.
        """
        serialized: str = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        async with self._stdout_lock:
            await asyncio.to_thread(sys.stdout.write, serialized + "\n")
            await asyncio.to_thread(sys.stdout.flush)

    async def _post(self, payload: dict[str, Any]) -> httpx.Response:
        """POST a message to the broker with exponential backoff retry.

        Args:
            payload: JSON-RPC request payload.

        Returns:
            httpx.Response: HTTP response from the broker.

        Raises:
            httpx.HTTPError: If all retries fail.
        """
        delay: float = 0.2
        last_error: httpx.HTTPError | None = None
        for attempt in range(5):
            try:
                return await self._client.post(
                    self.broker_url,
                    json=payload,
                    headers=self._headers(),
                )
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt == 4:
                    break
                await asyncio.sleep(delay)
                delay = min(delay * 2, 1.6)
        assert last_error is not None
        raise last_error

    async def _reinitialize(self) -> bool:
        """Rehace la sesion contra el broker tras un reinicio del gateway.

        El broker corre con ``stateless_http=False``: si el gateway se reinicia,
        el ``MCP-Session-Id`` que teniamos deja de existir y toda request
        posterior responde 404. Sin esto, el cliente queda sin MCP hasta que el
        usuario reinicia el IDE.

        Returns:
            bool: True si se obtuvo una sesion nueva.
        """
        if self._init_payload is None:
            return False

        # Cancelar el stream de notificaciones: quedo atado a la sesion muerta.
        if self._notification_task is not None:
            self._notification_task.cancel()
            await asyncio.gather(self._notification_task, return_exceptions=True)
            self._notification_task = None

        self.session_id = None
        try:
            response: httpx.Response = await self._post(self._init_payload)
        except httpx.HTTPError:
            return False
        if response.status_code >= 400:
            return False

        new_session_id: str | None = response.headers.get("mcp-session-id")
        if not new_session_id:
            return False
        self.session_id = new_session_id
        return True

    async def _post_with_recovery(self, payload: dict[str, Any]) -> httpx.Response:
        """Publica un mensaje y rehace una sesion perdida una sola vez.

        Args:
            payload: JSON-RPC request payload.

        Returns:
            httpx.Response: HTTP response from the broker.
        """
        response: httpx.Response = await self._post(payload)
        # 404 = la sesion ya no existe del lado del broker (gateway
        # reiniciado). Se rehace la sesion y se reintenta UNA vez.
        if (
            response.status_code == 404
            and self.session_id is not None
            and payload.get("method") != "initialize"
            and await self._reinitialize()
        ):
            response = await self._post(payload)
        return response

    async def _write_offline_error(
        self,
        request_id: Any,
        exc: httpx.HTTPError,
    ) -> None:
        """Responde el error JSON-RPC usado cuando el broker esta offline.

        Args:
            request_id: The JSON-RPC request id to respond to.
            exc: The HTTPError that occurred.
        """
        if request_id is None:
            return
        await self._write_message(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32001,
                    "message": (
                        "OpenAntigravity broker is offline; retry after the "
                        f"client reconnects ({type(exc).__name__})"
                    ),
                    "data": {"retryable": True},
                },
            }
        )

    async def _write_broker_error(self, request_id: Any, response: httpx.Response) -> None:
        """Traduce un error HTTP del broker a una respuesta JSON-RPC.

        Args:
            request_id: The JSON-RPC request id to respond to.
            response: The error response from the broker.
        """
        if request_id is None:
            return
        status_label: str = {
            401: "AUTH_REQUIRED",
            403: "FORBIDDEN",
            404: "NOT_FOUND",
        }.get(response.status_code, "BROKER_ERROR")
        await self._write_message(
            {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {
                    "code": -32000,
                    "message": status_label,
                    "data": {
                        "http_status": response.status_code,
                        "retryable": response.status_code >= 500,
                    },
                },
            }
        )

    async def _forward_successful_response(self, response: httpx.Response) -> None:
        """Actualiza la sesion y reenvia una respuesta HTTP exitosa.

        Args:
            response: The successful response from the broker.
        """
        new_session_id: str | None = response.headers.get("mcp-session-id")
        if new_session_id and new_session_id != self.session_id:
            self.session_id = new_session_id
        try:
            result: dict[str, Any] = response.json()
        except ValueError:
            return

        negotiated: Any = result.get("result", {}).get("protocolVersion")
        if isinstance(negotiated, str):
            self.protocol_version = negotiated
        await self._write_message(result)

        if self.session_id and self._notification_task is None:
            self._notification_task = asyncio.create_task(
                self._forward_notifications(),
                name="antigravity-mcp-notifications",
            )

    async def _handle_message(self, payload: dict[str, Any]) -> None:
        """Process an incoming JSON-RPC message from the client.

        Args:
            payload: Parsed JSON-RPC message from stdin.
        """
        request_id: Any = payload.get("id")
        if payload.get("method") == "initialize":
            self._init_payload = payload
        try:
            response: httpx.Response = await self._post_with_recovery(payload)
        except httpx.HTTPError as exc:
            await self._write_offline_error(request_id, exc)
            return

        if response.status_code == 202:
            return
        if response.status_code >= 400:
            await self._write_broker_error(request_id, response)
            return
        await self._forward_successful_response(response)

    async def _forward_notifications(self) -> None:
        """Stream notifications from the broker to the client.

        Connects to the broker in SSE mode and forwards notifications
        back to the client via JSON-RPC.
        """
        try:
            async with self._client.stream(
                "GET",
                self.broker_url,
                headers=self._headers(),
                timeout=None,
            ) as response:
                if response.status_code != 200:
                    return
                data_lines: list[str] = []
                async for line in response.aiter_lines():
                    if line.startswith("data:"):
                        data_lines.append(line[5:].lstrip())
                    elif not line and data_lines:
                        raw: str = "\n".join(data_lines)
                        data_lines.clear()
                        try:
                            payload: Any = json.loads(raw)
                        except json.JSONDecodeError:
                            continue
                        if isinstance(payload, dict):
                            await self._write_message(cast(dict[str, Any], payload))
        except (httpx.HTTPError, asyncio.CancelledError):
            return

    async def run(self) -> int:
        """Run the main event loop, reading from stdin and forwarding to broker.

        Returns:
            int: Exit code (0 on success).
        """
        try:
            while True:
                raw_line: bytes = await asyncio.to_thread(sys.stdin.buffer.readline)
                if not raw_line:
                    break
                try:
                    payload: Any = json.loads(raw_line)
                except json.JSONDecodeError:
                    await self._write_message(
                        {
                            "jsonrpc": "2.0",
                            "id": None,
                            "error": {"code": -32700, "message": "Parse error"},
                        }
                    )
                    continue
                if not isinstance(payload, dict):
                    continue
                await self._handle_message(cast(dict[str, Any], payload))
        finally:
            if self._notification_task is not None:
                self._notification_task.cancel()
                await asyncio.gather(self._notification_task, return_exceptions=True)
            if self.session_id:
                try:
                    await self._client.delete(
                        self.broker_url,
                        headers=self._headers(),
                    )
                except httpx.HTTPError:
                    pass
            await self._client.aclose()
        return 0


def main() -> int:
    """Run the authenticated stdio bridge.

    Returns:
        int: Exit code from the proxy.
    """
    # Windows may start this process with the user's legacy console encoding
    # (for example CP932). MCP responses contain Unicode tool descriptions, so
    # writing them through that stream can terminate the proxy with
    # UnicodeEncodeError before the client finishes initialization.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(encoding="utf-8", errors="replace")
            except (OSError, ValueError):
                pass
    broker_url: str = os.environ.get("ANTIGRAVITY_MCP_URL", DEFAULT_BROKER_URL)
    return asyncio.run(StdioBrokerProxy(broker_url).run())


if __name__ == "__main__":
    raise SystemExit(main())
