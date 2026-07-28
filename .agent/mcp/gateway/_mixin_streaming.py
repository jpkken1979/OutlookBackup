"""Mixin: handlers de streaming — costs, history, events SSE, MCP JSON-RPC."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import logging
import os
import socket
import uuid
from datetime import datetime
from urllib.parse import urlsplit

from aiohttp import web
from aiohttp.abc import AbstractResolver

log = logging.getLogger("antigravity-gateway")

# Hosts de metadata de cloud que NUNCA deben alcanzarse via el proxy de
# streaming LLM (vectores clasicos de SSRF para robar credenciales IAM).
# El rango link-local 169.254.0.0/16 cubre el IMDS de AWS/GCP/Azure por IP;
# los nombres se listan explicitos porque pueden resolver a otras IPs.
_BLOCKED_UPSTREAM_HOSTS: frozenset[str] = frozenset(
    {
        "169.254.169.254",  # AWS / GCP / Azure IMDS
        "metadata.google.internal",
        "metadata.azure.com",
    }
)


def _private_upstream_allowed() -> bool:
    """Indica si el proxy de streaming puede alcanzar IPs privadas/LAN.

    Por defecto ``False`` (defensa en profundidad anti-SSRF): un usuario
    autenticado no deberia poder usar el proxy para alcanzar servicios de la
    red interna. Se habilita seteando ``ANTIGRAVITY_GATEWAY_ALLOW_PRIVATE_UPSTREAM``
    a un valor truthy para el caso legitimo de un provider LLM corriendo en
    otra maquina de la LAN.

    Returns:
        ``True`` si el override esta activo, ``False`` en caso contrario.
    """
    raw = os.environ.get("ANTIGRAVITY_GATEWAY_ALLOW_PRIVATE_UPSTREAM", "")
    return raw.strip().lower() in ("1", "true", "yes", "on")


async def _build_llm_stream_request(
    body: dict,
) -> tuple[str, dict[str, str], dict] | web.Response:
    """Valida el body del proxy de streaming LLM y arma headers + payload upstream.

    Centraliza la validacion de campos requeridos, la verificacion anti-SSRF de
    la baseUrl y la construccion del payload OpenAI-compatible, devolviendo una
    respuesta de error lista para retornar cuando algo no valida.

    Args:
        body: Cuerpo JSON ya parseado del request (baseUrl, apiKey, model,
            messages, tools opcional).

    Returns:
        Una tupla ``(base_url, headers, payload)`` cuando la validacion pasa, o
        un ``web.Response`` con status 400 describiendo el primer error hallado.
    """
    base_url = body.get("baseUrl")
    api_key = body.get("apiKey", "")
    model = body.get("model")
    messages = body.get("messages", [])
    tools = body.get("tools")

    if not base_url or not model or not messages:
        return web.json_response({"error": "baseUrl, model y messages son requeridos"}, status=400)

    # Validacion anti-SSRF de la baseUrl antes de cualquier session.post.
    # Permite providers locales (Ollama/LMStudio/LiteLLM en 127.0.0.1) y
    # bloquea esquemas no http/https + endpoints de metadata cloud.
    try:
        base_url = await _validate_upstream_url(base_url)
    except ValueError as exc:
        return web.json_response({"error": str(exc)}, status=400)

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

    return base_url, headers, payload


def _openai_sse_line_to_chunk(line: bytes) -> bytes | None:
    """Convierte una linea SSE de un upstream OpenAI-compatible al formato del proxy.

    Traduce el formato `data: {...}` que emiten Ollama/LM Studio al evento SSE
    simplificado `{chunk}` / `{done}` que consumen los clientes locales del
    gateway. Las lineas vacias o sin contenido util se descartan.

    Args:
        line: Linea cruda (bytes) leida del stream del upstream.

    Returns:
        Los bytes ya formateados listos para escribir en la respuesta, o
        ``None`` si la linea no aporta contenido (vacia, no-`data:`, delta sin
        texto o JSON invalido).
    """
    line_str = line.decode("utf-8", errors="replace").strip()
    if not line_str or not line_str.startswith("data:"):
        return None
    payload_str = line_str[5:].strip()
    if payload_str == "[DONE]":
        return b'data: {"done": true}\n\n'
    try:
        parsed = json.loads(payload_str)
        # Python no tiene optional chaining (?.),
        # usamos `or {}` para corto-circuitar None/vacio.
        choices = parsed.get("choices") or [{}]
        first = choices[0] if choices else {}
        delta = (first or {}).get("delta") or {}
        content = delta.get("content", "")
        if content:
            return f"data: {json.dumps({'chunk': content})}\n\n".encode()
    except Exception:
        return None
    return None


def _ip_is_blocked(addr: ipaddress.IPv4Address | ipaddress.IPv6Address) -> str | None:
    """Decide si una IP es un upstream prohibido para el proxy de streaming.

    Normaliza IPv4-mapped en IPv6 (``::ffff:a.b.c.d``) para que no se evada el
    filtro. Loopback (127.0.0.1 / ::1) siempre se permite (Ollama/LMStudio/
    LiteLLM). Link-local/multicast/reserved/unspecified se bloquean siempre;
    las privadas (RFC 1918) salvo override ``ANTIGRAVITY_GATEWAY_ALLOW_PRIVATE_UPSTREAM``.

    Args:
        addr: La direccion IP ya parseada a validar.

    Returns:
        Un mensaje de error generico si la IP esta bloqueada, o ``None`` si
        es un upstream permitido.
    """
    mapped = getattr(addr, "ipv4_mapped", None)
    if mapped is not None:
        addr = mapped
    if addr.is_loopback:
        return None
    if addr.is_link_local or addr.is_multicast or addr.is_reserved or addr.is_unspecified:
        return "baseUrl apunta a una IP bloqueada"
    if addr.is_private and not _private_upstream_allowed():
        return "baseUrl apunta a una IP privada bloqueada"
    return None


async def _validate_upstream_url(url: str) -> str:
    """Valida la baseUrl de un upstream LLM para prevenir SSRF.

    Permite providers locales legitimos (127.0.0.1 / localhost para Ollama,
    LMStudio, LiteLLM, que corren en loopback) y bloquea los vectores
    peligrosos: esquemas que no sean http/https, los endpoints de metadata de
    cloud (IMDS) y las IPs privadas/LAN (RFC 1918, link-local, reservadas).

    Cuando el host es un nombre (no una IP literal) se resuelve via DNS y se
    valida **cada** IP resultante; un nombre que apunta a una IP bloqueada se
    rechaza (mitigacion best-effort de DNS rebinding). El acceso a IPs privadas
    se puede rehabilitar con ``ANTIGRAVITY_GATEWAY_ALLOW_PRIVATE_UPSTREAM``.

    Nota TOCTOU: la resolucion aqui no fija (pin) la IP usada al conectar; aiohttp
    resuelve de nuevo al abrir la conexion, por lo que un rebinding con TTL 0
    podria diferir entre validacion y conexion. Esto es defensa en profundidad,
    no una garantia dura; cerrar el TOCTOU requeriria pinear la IP en el connector.

    Args:
        url: La baseUrl provista en el body del request.

    Returns:
        La misma URL si pasa la validacion.

    Raises:
        ValueError: Si el esquema no es http/https, el host esta bloqueado o no
            es resoluble. El mensaje es generico (no expone internals).
    """
    try:
        parsed = urlsplit(url)
    except ValueError:
        raise ValueError("baseUrl mal formada")

    # Solo http/https — rechaza file://, data://, gopher://, etc.
    if parsed.scheme not in ("http", "https"):
        raise ValueError("baseUrl con esquema no permitido")

    hostname = (parsed.hostname or "").lower()
    if not hostname:
        raise ValueError("baseUrl sin host")

    # Lista negra explicita de endpoints de metadata cloud (belt-and-suspenders:
    # ademas se cubren por IP tras resolver).
    if hostname in _BLOCKED_UPSTREAM_HOSTS:
        raise ValueError("baseUrl apunta a un host bloqueado")

    # Caso 1: el host es una IP literal — validarla directo, sin resolver.
    try:
        literal = ipaddress.ip_address(hostname)
    except ValueError:
        literal = None
    if literal is not None:
        err = _ip_is_blocked(literal)
        if err:
            raise ValueError(err)
        return url

    # Caso 2: el host es un nombre — resolver TODAS sus IPs y validarlas.
    loop = asyncio.get_running_loop()
    try:
        infos = await loop.getaddrinfo(hostname, None)
    except OSError:
        raise ValueError("baseUrl: host no resoluble")
    if not infos:
        raise ValueError("baseUrl: host no resoluble")
    for info in infos:
        # info[4] es el sockaddr; [0] la IP. IPv6 puede traer scope (fe80::1%eth0).
        ip_str = str(info[4][0]).split("%")[0]
        try:
            addr = ipaddress.ip_address(ip_str)
        except ValueError:
            # Una IP no parseable es sospechosa: fail-closed.
            raise ValueError("baseUrl: resolucion DNS invalida")
        err = _ip_is_blocked(addr)
        if err:
            raise ValueError(err)

    return url


class _SSRFGuardResolver(AbstractResolver):
    """Resolver de aiohttp que valida cada IP contra SSRF al momento de conectar.

    Envuelve el resolver interno (por defecto el de aiohttp) y rechaza la
    conexion si el host resuelve a una IP bloqueada (IMDS, link-local, privada
    sin override). A diferencia de la validacion previa en
    ``_validate_upstream_url`` (que valida y luego aiohttp re-resuelve), este
    resolver corre en el MISMO resolve que usa la conexion TCP, cerrando el
    TOCTOU / DNS-rebinding: no hay ventana entre validar y conectar.
    """

    def __init__(self, inner: AbstractResolver) -> None:
        self._inner = inner

    async def resolve(self, host: str, port: int = 0, family: int = socket.AF_INET) -> list[dict]:
        """Resuelve via el resolver interno y valida cada IP; OSError si bloqueada."""
        infos = await self._inner.resolve(host, port, family)
        for info in infos:
            ip_str = str(info["host"]).split("%")[0]
            try:
                addr = ipaddress.ip_address(ip_str)
            except ValueError as exc:
                raise OSError("baseUrl: resolucion DNS invalida") from exc
            err = _ip_is_blocked(addr)
            if err:
                raise OSError(err)
        return infos

    async def close(self) -> None:
        """Cierra el resolver interno."""
        await self._inner.close()


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
                    return web.json_response(
                        {
                            "jsonrpc": "2.0",
                            "id": request_id,
                            "error": {"code": -32603, "message": "Executor no disponible"},
                        }
                    )
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
        from aiohttp import ClientSession, ClientTimeout, TCPConnector
        from aiohttp.resolver import DefaultResolver
        import logging
        from .._gateway_main import _sanitize_error

        _log = logging.getLogger("antigravity-gateway.llm-stream")

        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "JSON invalido en el body"}, status=400)

        built = await _build_llm_stream_request(body)
        if isinstance(built, web.Response):
            return built
        base_url, headers, payload = built

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
            # Resolver-guard: valida cada IP en el momento exacto de conectar,
            # cerrando el TOCTOU/DNS-rebinding (la validacion previa es early-reject).
            connector = TCPConnector(resolver=_SSRFGuardResolver(DefaultResolver()))
            async with ClientSession(timeout=timeout, connector=connector) as session:
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
                            out = _openai_sse_line_to_chunk(line)
                            if out is not None:
                                await response.write(out)
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
