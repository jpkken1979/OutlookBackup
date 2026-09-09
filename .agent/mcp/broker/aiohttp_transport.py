"""Adapter that lets the official ASGI MCP transport run inside aiohttp."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import web
from aiohttp.client_exceptions import ClientConnectionResetError

AsgiReceive = Callable[[], Awaitable[dict[str, Any]]]
AsgiSend = Callable[[dict[str, Any]], Awaitable[None]]

_HOP_BY_HOP_HEADERS = frozenset({"connection", "content-length", "transfer-encoding"})


class _AsgiExchange:
    """Encapsula el estado mutable de un ciclo ASGI puenteado sobre una request aiohttp.

    Reemplaza el patron de closures + ``nonlocal`` por atributos de instancia,
    para que la logica de ``receive``/``send`` no cuente hacia la complejidad
    ciclomatica del metodo que orquesta el request.
    """

    def __init__(self, request: web.Request, body: bytes):
        self._request = request
        self._body = body
        self._body_sent = False
        self.response_started = False
        self.response_complete = False
        self.status = 200
        self.headers: list[tuple[str, str]] = []
        self._buffered_body = bytearray()
        self.stream_response: web.StreamResponse | None = None

    @property
    def buffered_body(self) -> bytes:
        return bytes(self._buffered_body)

    async def receive(self) -> dict[str, Any]:
        if not self._body_sent:
            self._body_sent = True
            return {"type": "http.request", "body": self._body, "more_body": False}
        while self._request.transport is not None and not self._request.transport.is_closing():
            await asyncio.sleep(0.1)
        return {"type": "http.disconnect"}

    async def _prepare_stream(self) -> web.StreamResponse:
        if self.stream_response is not None:
            return self.stream_response
        self.stream_response = web.StreamResponse(status=self.status)
        for name, value in self.headers:
            if name.lower() not in _HOP_BY_HOP_HEADERS:
                self.stream_response.headers.add(name, value)
        await self.stream_response.prepare(self._request)
        if self._buffered_body:
            await self.stream_response.write(bytes(self._buffered_body))
            self._buffered_body.clear()
        return self.stream_response

    async def send(self, message: dict[str, Any]) -> None:
        message_type = message["type"]
        if message_type == "http.response.start":
            await self._handle_response_start(message)
            return
        if message_type != "http.response.body":
            return
        await self._handle_response_body(message)

    async def _handle_response_start(self, message: dict[str, Any]) -> None:
        self.response_started = True
        self.status = int(message["status"])
        self.headers = [
            (name.decode("latin-1"), value.decode("latin-1"))
            for name, value in message.get("headers", [])
        ]
        content_type = next(
            (value for name, value in self.headers if name.lower() == "content-type"), ""
        )
        if content_type.startswith("text/event-stream"):
            await self._prepare_stream()

    async def _handle_response_body(self, message: dict[str, Any]) -> None:
        chunk = message.get("body", b"")
        more_body = bool(message.get("more_body", False))
        if self.stream_response is None and not more_body:
            self._buffered_body.extend(chunk)
            self.response_complete = True
            return
        response = await self._prepare_stream()
        if chunk:
            try:
                await response.write(chunk)
            except (ClientConnectionResetError, ConnectionResetError):
                self.response_complete = True
                return
        if not more_body:
            self.response_complete = True
            try:
                await response.write_eof()
            except (ClientConnectionResetError, ConnectionResetError):
                return


class AiohttpMcpTransport:
    """Bridge aiohttp requests to ``StreamableHTTPSessionManager``."""

    def __init__(self, session_manager: Any):
        self._session_manager = session_manager
        self._runner_task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None

    async def start(self) -> None:
        if self._runner_task is not None:
            return
        loop = asyncio.get_running_loop()
        ready: asyncio.Future[None] = loop.create_future()
        self._stop_event = asyncio.Event()

        async def run_manager() -> None:
            try:
                async with self._session_manager.run():
                    if not ready.done():
                        ready.set_result(None)
                    await self._stop_event.wait()
            except BaseException as exc:
                if not ready.done():
                    ready.set_exception(exc)
                raise

        self._runner_task = asyncio.create_task(
            run_manager(),
            name="antigravity-mcp-session-manager",
        )
        await ready

    async def stop(self) -> None:
        if self._runner_task is None:
            return
        task = self._runner_task
        self._runner_task = None
        if self._stop_event is not None:
            self._stop_event.set()
        self._stop_event = None
        await task

    @staticmethod
    def _build_scope(request: web.Request) -> dict[str, Any]:
        """Construye el scope ASGI a partir de una request aiohttp."""
        return {
            "type": "http",
            "asgi": {"version": "3.0", "spec_version": "2.3"},
            "http_version": f"{request.version.major}.{request.version.minor}",
            "method": request.method,
            "scheme": request.scheme,
            "path": "/mcp",
            "raw_path": b"/mcp",
            "root_path": "",
            "query_string": request.query_string.encode("ascii", errors="ignore"),
            "headers": [
                (name.lower().encode("latin-1"), value.encode("latin-1"))
                for name, value in request.headers.items()
            ],
            "client": (request.remote or "unknown", 0),
            "server": (request.host.split(":", 1)[0], request.url.port or 80),
            "state": {},
        }

    @staticmethod
    async def _finalize_response(exchange: _AsgiExchange) -> web.StreamResponse:
        """Traduce el estado final del intercambio ASGI a una respuesta aiohttp."""
        if exchange.stream_response is not None:
            if not exchange.response_complete and exchange.stream_response.prepared:
                try:
                    await exchange.stream_response.write_eof()
                except (ClientConnectionResetError, ConnectionResetError):
                    pass
            return exchange.stream_response
        if not exchange.response_started:
            raise RuntimeError("MCP SDK returned no ASGI response")

        response_headers: dict[str, str] = {
            name: value
            for name, value in exchange.headers
            if name.lower() not in _HOP_BY_HOP_HEADERS
        }
        return web.Response(
            status=exchange.status,
            body=exchange.buffered_body,
            headers=response_headers,
        )

    async def handle(self, request: web.Request) -> web.StreamResponse:
        body = await request.read()
        exchange = _AsgiExchange(request, body)
        scope = self._build_scope(request)
        await self._session_manager.handle_request(scope, exchange.receive, exchange.send)
        return await self._finalize_response(exchange)
