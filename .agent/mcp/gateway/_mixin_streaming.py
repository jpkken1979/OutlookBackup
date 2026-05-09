"""Mixin: handlers de streaming — costs, history, events SSE, MCP JSON-RPC."""

from __future__ import annotations

import asyncio
import json
import logging
import uuid
from datetime import datetime

from aiohttp import web

log = logging.getLogger("antigravity-gateway")


class _StreamingMixin:
    """Handlers de streaming: costs, history, events SSE, MCP."""

    async def handle_costs(self, request: web.Request) -> web.Response:
        """GET /v1/costs - Reporte de costos."""
        from .._gateway_main import _make_response, _sanitize_error

        executor = self.executor or await self.get_executor()
        if not executor:
            return web.json_response(
                _make_response(error="Executor no disponible", status=503),
                status=503,
            )

        days = min(int(request.query.get("days", "30")), 365)
        try:
            report = executor.get_cost_report(days)
            return web.json_response(
                _make_response(data=json.loads(json.dumps(report, default=str)))
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_history(self, request: web.Request) -> web.Response:
        """GET /v1/history - Historial."""
        from .._gateway_main import _make_response

        executor = self.executor or await self.get_executor()
        if not executor:
            return web.json_response(
                _make_response(error="Executor no disponible", status=503),
                status=503,
            )

        limit = min(int(request.query.get("limit", "10")), 100)
        history = executor.get_execution_history(limit)
        return web.json_response(
            _make_response(
                data={
                    "history": history,
                    "count": len(history),
                }
            )
        )

    async def handle_events(self, request: web.Request) -> web.StreamResponse:
        """GET /v1/events - SSE stream."""
        from .._gateway_main import _make_response, MAX_SSE_SUBSCRIBERS

        queue = self.events.subscribe()
        if queue is None:
            return web.json_response(
                _make_response(
                    error=f"Limite de {MAX_SSE_SUBSCRIBERS} conexiones SSE alcanzado", status=429
                ),
                status=429,
            )

        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        await response.prepare(request)

        welcome = json.dumps(
            {
                "type": "connected",
                "message": "Conectado al stream de eventos Antigravity",
                "subscribers": self.events.count,
                "timestamp": datetime.now().isoformat(),
            }
        )
        await response.write(f"data: {welcome}\n\n".encode())

        try:
            while True:
                try:
                    event = await asyncio.wait_for(queue.get(), timeout=30)
                    data = json.dumps(event)
                    await response.write(f"event: {event['type']}\ndata: {data}\n\n".encode())
                except TimeoutError:
                    await response.write(b": heartbeat\n\n")
                except (ConnectionResetError, ConnectionError):
                    break
        finally:
            self.events.unsubscribe(queue)
            # Cerrar apropiadamente el stream para evitar CLOSE_WAIT
            await response.write_eof()

        return response

    # --------------------------------------------------------
    # MCP Protocol Support (JSON-RPC over HTTP)
    # --------------------------------------------------------
    async def handle_mcp(self, request: web.Request) -> web.Response:
        """Handler universal para MCP JSON-RPC sobre POST."""
        from .._gateway_main import _sanitize_error, VERSION

        try:
            body = await request.json()
            request_id = body.get("id")
            method = body.get("method")
            params = body.get("params", {})

            log.info("MCP Request: %s (id: %s)", method, request_id)

            if method == "initialize":
                result = {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {
                        "tools": {"listChanged": True},
                        "resources": {"subscribe": True},
                    },
                    "serverInfo": {"name": "Antigravity Gateway", "version": VERSION},
                }
            elif method == "tools/list":
                executor = self.executor or await self.get_executor()
                agents = executor.get_available_agents() if executor else []
                tools = []
                for agent in agents:
                    tools.append(
                        {
                            "name": agent["name"],
                            "description": agent.get("description", ""),
                            "inputSchema": {
                                "type": "object",
                                "properties": {
                                    "task": {
                                        "type": "string",
                                        "description": "Tarea para el agente",
                                    }
                                },
                                "required": ["task"],
                            },
                        }
                    )
                result = {"tools": tools}
            elif method == "tools/call":
                tool_name = params.get("name")
                tool_args = params.get("arguments", {})
                task = tool_args.get("task", "")

                if not tool_name or not task:
                    return web.json_response(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {"code": -32602, "message": "Invalid params"},
                        }
                    )

                log.info("MCP Call Agent: %s Task: %s", tool_name, task[:50])
                executor = self.executor or await self.get_executor()
                if not executor:
                    return web.json_response({
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32603, "message": "Executor no disponible"},
                    })
                exec_result = await executor.execute_agent(tool_name, task, 120)

                result = {
                    "content": [
                        {
                            "type": "text",
                            "text": exec_result.output
                            if exec_result.success
                            else f"Error: {exec_result.output}",
                        }
                    ],
                    "isError": not exec_result.success,
                }
            else:
                return web.json_response(
                    {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    }
                )

            return web.json_response({"jsonrpc": "2.0", "id": request_id, "result": result})

        except Exception as e:
            log.exception("Error en MCP handler")
            return web.json_response(
                {
                    "jsonrpc": "2.0",
                    "id": body.get("id") if "id" in locals() else None,
                    "error": {"code": -32603, "message": _sanitize_error(e)},
                },
                status=500,
            )

    async def handle_mcp_sse(self, request: web.Request) -> web.StreamResponse:
        """Registration endpoint for MCP SSE transport."""
        log.info("MCP SSE Connection requested")
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
            },
        )
        await response.prepare(request)

        # Enviar el endpoint de mensajes segun spec MCP
        session_id = uuid.uuid4().hex
        host = request.host
        scheme = request.scheme
        msg_url = f"{scheme}://{host}/v1/mcp/message?session_id={session_id}"

        log.info(f"Sending MCP endpoint: {msg_url}")
        await response.write(f"event: endpoint\ndata: {msg_url}\n\n".encode())

        # Heartbeat inicial
        await response.write(b": heartbeat\n\n")

        # Mantener conexion abierta
        try:
            while True:
                await asyncio.sleep(15)
                await response.write(b": heartbeat\n\n")
        except (ConnectionResetError, ConnectionError, asyncio.CancelledError):
            pass
        finally:
            # Cerrar apropiadamente el stream para evitar CLOSE_WAIT
            await response.write_eof()
        return response

    async def handle_mcp_message(self, request: web.Request) -> web.Response:
        """Message handler for SSE transport."""
        return await self.handle_mcp(request)

    # --------------------------------------------------------
    # LLM Streaming Proxy (para bots y clients locales)
    # --------------------------------------------------------
    async def handle_llm_stream(self, request: web.Request) -> web.StreamResponse:
        """POST /v1/llm/stream — SSE proxy para modelos locales (Ollama/LM Studio).

        Body JSON: { baseUrl, apiKey, model, messages, tools? }
        Returns: text/event-stream con {chunk, done}
        """
        from aiohttp import ClientSession, ClientTimeout
        import logging
        from .._gateway_main import _sanitize_error

        _log = logging.getLogger("antigravity-gateway.llm-stream")

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "JSON invalido en el body"}, status=400)

        base_url = body.get("baseUrl")
        api_key = body.get("apiKey", "")
        model = body.get("model")
        messages = body.get("messages", [])
        tools = body.get("tools")

        if not base_url or not model or not messages:
            return web.json_response(
                {"error": "baseUrl, model y messages son requeridos"}, status=400
            )

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        payload: dict = {
            "stream": True,
            "model": model,
            "messages": messages,
        }
        if tools:
            payload["tools"] = tools

        timeout = ClientTimeout(total=120)
        response = web.StreamResponse(
            status=200,
            headers={
                "Content-Type": "text/event-stream",
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "X-Accel-Buffering": "no",
            },
        )
        await response.prepare(request)

        try:
            async with ClientSession(timeout=timeout) as session:
                async with session.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                ) as resp:
                    if resp.status != 200:
                        text = await resp.text()
                        _log.error("Upstream error %s: %s", resp.status, text)
                        await response.write(
                            f"data: {json.dumps({'error': f'Upstream error {resp.status}'})}\n\n".encode()
                        )
                    else:
                        async for line in resp.content:
                            line_str = line.decode("utf-8", errors="replace").strip()
                            if not line_str:
                                continue
                            if line_str.startswith("data:"):
                                payload_str = line_str[5:].strip()
                                if payload_str == "[DONE]":
                                    await response.write(
                                        b"data: {\"done\": true}\n\n"
                                    )
                                else:
                                    try:
                                        parsed = json.loads(payload_str)
                                        # Python no tiene optional chaining (?.),
                                        # usamos `or {}` para corto-circuitar None/vacio.
                                        choices = parsed.get("choices") or [{}]
                                        first = choices[0] if choices else {}
                                        delta = (first or {}).get("delta") or {}
                                        content = delta.get("content", "")
                                        if content:
                                            await response.write(
                                                f"data: {json.dumps({'chunk': content})}\n\n".encode()
                                            )
                                    except Exception:
                                        pass
                        await response.write_eof()
                        return response
        except TimeoutError:
            _log.error("Timeout en streaming hacia %s", base_url)
            await response.write(
                f"data: {json.dumps({'error': 'Timeout de streaming (120s)'})}\n\n".encode()
            )
        except Exception as exc:
            _log.exception("Error en handle_llm_stream")
            await response.write(
                f"data: {json.dumps({'error': _sanitize_error(exc)})}\n\n".encode()
            )
        finally:
            try:
                await response.write_eof()
            except Exception:
                pass

        return response
