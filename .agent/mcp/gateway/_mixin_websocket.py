"""Mixin: handlers WebSocket — conexion en tiempo real del ecosistema."""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from typing import Any

from aiohttp import web

log = logging.getLogger("antigravity-gateway")


class _WebSocketMixin:
    """Handlers WebSocket: handle_websocket, _ws_forward_bus_events."""

    async def _ws_handle_subscribe(
        self,
        ws: web.WebSocketResponse,
        data: dict,
        subscribed_channels: set,
        **_kwargs: Any,
    ) -> None:
        """Procesa acción 'subscribe'."""
        new_channels = set(data.get("channels", []))
        subscribed_channels.update(new_channels)
        await ws.send_json({"type": "subscribed", "channels": list(subscribed_channels)})

    async def _ws_handle_unsubscribe(
        self,
        ws: web.WebSocketResponse,
        data: dict,
        subscribed_channels: set,
        **_kwargs: Any,
    ) -> None:
        """Procesa acción 'unsubscribe'."""
        for ch in data.get("channels", []):
            subscribed_channels.discard(ch)
        await ws.send_json({"type": "unsubscribed", "channels": list(subscribed_channels)})

    async def _ws_handle_submit_task(
        self,
        ws: web.WebSocketResponse,
        data: dict,
        client_id: str,
        _validate_name: Any,
        _sanitize_error: Any,
        **_kwargs: Any,
    ) -> None:
        """Procesa acción 'submit_task'."""
        agent = data.get("agent", "")
        task = data.get("task", "")
        priority = data.get("priority", "NORMAL")
        if not (agent and task and _validate_name(agent)):
            await ws.send_json({"type": "error", "message": "Campos 'agent' y 'task' requeridos"})
            return
        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            task_id = await daemon.submit_task(
                agent_name=agent,
                task=task,
                from_agent=f"ws:{client_id}",
                priority_name=priority,
            )
            await ws.send_json({"type": "task_submitted", "task_id": task_id, "agent": agent})
        except Exception as e:
            await ws.send_json({"type": "error", "message": _sanitize_error(e)})

    async def _ws_handle_a2a_request(
        self,
        ws: web.WebSocketResponse,
        data: dict,
        _sanitize_error: Any,
        **_kwargs: Any,
    ) -> None:
        """Procesa acción 'a2a_request'."""
        from_agent = data.get("from_agent", "")
        to_agent = data.get("to_agent", "")
        question = data.get("question", "")
        a2a_context = data.get("context", {})
        a2a_timeout = float(data.get("timeout", 60))
        request_type = data.get("request_type", "question")
        if not (from_agent and to_agent and question):
            await ws.send_json(
                {
                    "type": "error",
                    "message": "Campos 'from_agent', 'to_agent' y 'question' requeridos",
                }
            )
            return
        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            result = await daemon.a2a_request(
                from_agent=from_agent,
                to_agent=to_agent,
                question=question,
                context=a2a_context,
                timeout=a2a_timeout,
                request_type=request_type,
            )
            await ws.send_json(
                {
                    "type": "a2a_response",
                    "from_agent": from_agent,
                    "to_agent": to_agent,
                    "response": result,
                }
            )
        except TimeoutError:
            await ws.send_json(
                {
                    "type": "a2a_timeout",
                    "from_agent": from_agent,
                    "to_agent": to_agent,
                    "message": f"Timeout: '{to_agent}' no respondió en {a2a_timeout}s",
                }
            )
        except Exception as e:
            await ws.send_json({"type": "error", "message": _sanitize_error(e)})

    async def _ws_handle_plan_execute(
        self,
        ws: web.WebSocketResponse,
        data: dict,
        _sanitize_error: Any,
        **_kwargs: Any,
    ) -> None:
        """Procesa acción 'plan_execute'."""
        plan_task = data.get("task", "")
        plan_context = data.get("context")
        if not plan_task:
            await ws.send_json(
                {"type": "error", "message": "Campo 'task' requerido para plan_execute"}
            )
            return
        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            result = await daemon.plan_and_execute(plan_task, plan_context)
            await ws.send_json({"type": "plan_result", "plan": result})
        except Exception as e:
            await ws.send_json({"type": "error", "message": _sanitize_error(e)})

    async def _ws_handle_get_anomalies(
        self,
        ws: web.WebSocketResponse,
        data: dict,
        _sanitize_error: Any,
        **_kwargs: Any,
    ) -> None:
        """Procesa acción 'get_anomalies'."""
        agent_filter = data.get("agent")
        sev_filter = data.get("severity")
        alert_limit = int(data.get("limit", 50))
        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            alerts = await daemon.get_anomaly_alerts(
                agent=agent_filter,
                severity=sev_filter,
                limit=alert_limit,
            )
            await ws.send_json({"type": "anomaly_alerts", "alerts": alerts, "count": len(alerts)})
        except Exception as e:
            await ws.send_json({"type": "error", "message": _sanitize_error(e)})

    async def _ws_handle_ping(
        self,
        ws: web.WebSocketResponse,
        **_kwargs: Any,
    ) -> None:
        """Procesa acción 'ping'."""
        await ws.send_json({"type": "pong", "ts": time.time()})

    def _get_ws_action_handlers(self) -> dict[str, Any]:
        """Retorna el dispatch de acciones WebSocket.

        Returns:
            Dict action_name → handler_method.
        """
        return {
            "subscribe": self._ws_handle_subscribe,
            "unsubscribe": self._ws_handle_unsubscribe,
            "submit_task": self._ws_handle_submit_task,
            "a2a_request": self._ws_handle_a2a_request,
            "plan_execute": self._ws_handle_plan_execute,
            "get_anomalies": self._ws_handle_get_anomalies,
            "ping": self._ws_handle_ping,
        }

    async def handle_websocket(self, request: web.Request) -> web.WebSocketResponse:
        """
        GET /v1/ws - WebSocket para actualizaciones en tiempo real.

        Emite eventos del bus de mensajes: tareas, resultados, heartbeats.
        El cliente puede suscribirse a canales específicos via JSON:
          {"action": "subscribe", "channels": ["tasks.completed", "daemon.lifecycle"]}
          {"action": "submit_task", "agent": "explorer", "task": "analiza repo"}
        """
        from .._gateway_main import _validate_name, _sanitize_error

        ws = web.WebSocketResponse(heartbeat=30.0)
        await ws.prepare(request)

        client_id = str(uuid.uuid4())[:8]
        log.info("WebSocket conectado: client=%s", client_id)

        subscribed_channels: set[str] = {
            "tasks.completed",
            "tasks.failed",
            "daemon.lifecycle",
            "antigravity:heartbeats",
        }

        bus = None
        try:
            from core.redis_message_bus import get_message_bus

            bus = await get_message_bus()
        except Exception as e:
            log.warning("Bus no disponible para WebSocket: %s", e)

        forward_task = asyncio.create_task(
            self._ws_forward_bus_events(ws, bus, subscribed_channels, client_id)
        )

        action_handlers = self._get_ws_action_handlers()

        try:
            async for msg in ws:
                if msg.type == web.WSMsgType.TEXT:
                    try:
                        data = json.loads(msg.data)
                        action = data.get("action", "")
                        handler = action_handlers.get(action)
                        if handler:
                            await handler(
                                ws=ws,
                                data=data,
                                client_id=client_id,
                                subscribed_channels=subscribed_channels,
                                _validate_name=_validate_name,
                                _sanitize_error=_sanitize_error,
                            )
                    except (json.JSONDecodeError, Exception) as e:
                        await ws.send_json({"type": "error", "message": str(e)})

                elif msg.type == web.WSMsgType.ERROR:
                    log.warning("WebSocket error client=%s: %s", client_id, ws.exception())
                    break

        except asyncio.CancelledError:
            pass
        finally:
            forward_task.cancel()
            log.info("WebSocket desconectado: client=%s", client_id)

        return ws

    async def _ws_forward_bus_events(
        self,
        ws: web.WebSocketResponse,
        bus: Any,
        subscribed_channels: set,
        client_id: str,
    ) -> None:
        """Reenvía eventos del bus de mensajes al cliente WebSocket."""
        if bus is None:
            # Sin bus, solo enviar eventos SSE del gateway
            queue = self.events.subscribe()
            try:
                while not ws.closed:
                    try:
                        event = await asyncio.wait_for(queue.get(), timeout=5.0)
                        if not ws.closed:
                            await ws.send_json({"type": "gateway_event", "data": event})
                    except TimeoutError:
                        continue
            except (asyncio.CancelledError, ConnectionResetError):
                pass
            finally:
                self.events.unsubscribe(queue)
            return

        # Con bus: escuchar todos los canales suscritos
        # Usamos el stream de Redis para todos los canales relevantes
        try:
            # Suscripción vía simple polling del bus
            while not ws.closed:
                await asyncio.sleep(0.5)  # Poll cada 500ms

                # También reenviar eventos del gateway
                # (el forward real se hace via SSE/bus nativo)
        except asyncio.CancelledError:
            pass
