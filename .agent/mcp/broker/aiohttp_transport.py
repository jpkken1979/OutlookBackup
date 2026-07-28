"""Adapter that lets the official ASGI MCP transport run inside aiohttp."""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import web
from aiohttp.client_exceptions import ClientConnectionResetError

AsgiReceive = Callable[[], Awaitable[dict[str, Any]]]
AsgiSend = Callable[[dict[str, Any]], Awaitable[None]]


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

    async def handle(self, request: web.Request) -> web.StreamResponse:
        body = await request.read()
        body_sent = False
        response_started = False
        response_complete = False
        status = 200
        headers: list[tuple[str, str]] = []
        buffered_body = bytearray()
        stream_response: web.StreamResponse | None = None

        async def receive() -> dict[str, Any]:
            nonlocal body_sent
            if not body_sent:
                body_sent = True
                return {
                    "type": "http.request",
                    "body": body,
                    "more_body": False,
                }
            while request.transport is not None and not request.transport.is_closing():
                await asyncio.sleep(0.1)
            return {"type": "http.disconnect"}

        async def prepare_stream() -> web.StreamResponse:
            nonlocal stream_response
            if stream_response is not None:
                return stream_response
            stream_response = web.StreamResponse(status=status)
            for name, value in headers:
                lowered = name.lower()
                if lowered not in {"connection", "content-length", "transfer-encoding"}:
                    stream_response.headers.add(name, value)
            await stream_response.prepare(request)
            if buffered_body:
                await stream_response.write(bytes(buffered_body))
                buffered_body.clear()
            return stream_response

        async def send(message: dict[str, Any]) -> None:
            nonlocal response_started, response_complete, status, headers
            message_type = message["type"]
            if message_type == "http.response.start":
                response_started = True
                status = int(message["status"])
                headers = [
                    (name.decode("latin-1"), value.decode("latin-1"))
                    for name, value in message.get("headers", [])
                ]
                content_type = next(
                    (value for name, value in headers if name.lower() == "content-type"),
                    "",
                )
                if content_type.startswith("text/event-stream"):
                    await prepare_stream()
                return

            if message_type != "http.response.body":
                return
            chunk = message.get("body", b"")
            more_body = bool(message.get("more_body", False))
            if stream_response is None and not more_body:
                buffered_body.extend(chunk)
                response_complete = True
                return
            response = await prepare_stream()
            if chunk:
                try:
                    await response.write(chunk)
                except (ClientConnectionResetError, ConnectionResetError):
                    response_complete = True
                    return
            if not more_body:
                response_complete = True
                try:
                    await response.write_eof()
                except (ClientConnectionResetError, ConnectionResetError):
                    return

        scope = {
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

        await self._session_manager.handle_request(scope, receive, send)
        if stream_response is not None:
            if not response_complete and stream_response.prepared:
                try:
                    await stream_response.write_eof()
                except (ClientConnectionResetError, ConnectionResetError):
                    pass
            return stream_response
        if not response_started:
            raise RuntimeError("MCP SDK returned no ASGI response")

        response_headers: dict[str, str] = {}
        for name, value in headers:
            if name.lower() not in {"connection", "content-length", "transfer-encoding"}:
                response_headers[name] = value
        return web.Response(
            status=status,
            body=bytes(buffered_body),
            headers=response_headers,
        )
