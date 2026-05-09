#!/usr/bin/env python3
"""
Antigravity SDK Client - Cliente Python para el Gateway HTTP v2.

Permite que cualquier aplicacion Python se conecte al ecosistema de agentes
Antigravity a traves del gateway HTTP (puerto 4747 por defecto).

Usa SOLO urllib.request de la stdlib (sin httpx, sin requests).

Uso basico:

    from antigravity.sdk.client import Client

    # Conectar (default localhost:4747)
    client = Client()

    # Con API key y URL personalizada
    client = Client("http://mi-server:4747", api_key="mi-key")

    # Context manager
    with Client() as c:
        agents = c.list_agents()
        result = c.run("explorer", "analizar codebase")
        print(result.output)

    # Listar agentes
    agents = client.list_agents(filter="executable")

    # Ejecutar agente
    result = client.run("explorer", "analizar este codebase", timeout=30)
    print(result.output)
    print(result.success)
    print(result.execution_time_ms)

    # Buscar mejor agente para tarea
    matches = client.find("optimizar performance React")

    # Skills
    skills = client.list_skills(search="docker")
    skill = client.read_skill("docker-expert")

    # Health y readiness
    health = client.health()
    ready = client.ready()

    # Costos y historial
    costs = client.costs(days=7)
    history = client.history(limit=5)

    # Modo autonomo (ReAct loop)
    result = client.autonomous("security-auditor", "auditar auth", max_iterations=10)

    # Teams
    team = client.create_team(task="crear API", agents=["architect", "api-designer"])
    msg = client.team_message(team.id, from_a="architect", to_a="api-designer",
                              content="endpoints?")
"""

from __future__ import annotations

import json
import logging
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from typing import Any, cast

__all__ = [
    "Client",
    "AgentInfo",
    "AgentMatch",
    "AgentRunResult",
    "AutonomousResult",
    "CostReport",
    "GatewayInfo",
    "HealthStatus",
    "HistoryEntry",
    "PaginatedResult",
    "ReadinessStatus",
    "SkillInfo",
    "SkillDetail",
    "TeamInfo",
    "TeamMessageResult",
    "AntigravityError",
    "AuthenticationError",
    "GatewayConnectionError",
    "GatewayTimeoutError",
    "NotFoundError",
    "RateLimitError",
    "ServerError",
    "ValidationError",
]

logger = logging.getLogger("antigravity.sdk.client")

# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------
DEFAULT_BASE_URL = "http://127.0.0.1:4747"
DEFAULT_TIMEOUT = 120
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 1.0  # segundos
MAX_TASK_LENGTH = 10_000  # chars (limite del gateway)
API_PREFIX = "/v1"
SDK_VERSION = "2.1.0"


# ===========================================================================
# Excepciones
# ===========================================================================


class AntigravityError(Exception):
    """Error base del SDK Antigravity.

    Attributes:
        message: Descripcion del error.
        status_code: Codigo HTTP si aplica.
        response_body: Cuerpo de la respuesta si aplica.
    """

    def __init__(
        self,
        message: str,
        status_code: int = 0,
        response_body: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.response_body = response_body


class GatewayConnectionError(AntigravityError):
    """Error de conexion con el gateway.

    Se lanza cuando no se puede establecer conexion TCP con el servidor,
    por ejemplo si el gateway no esta corriendo o la URL es incorrecta.

    Nota: Se usa el prefijo 'Gateway' para evitar shadow del builtin
    builtins.ConnectionError de Python.
    """


class AuthenticationError(AntigravityError):
    """Error de autenticacion (401/403).

    Se lanza cuando el API key es invalido, faltante o expirado.
    """


class NotFoundError(AntigravityError):
    """Recurso no encontrado (404).

    Se lanza cuando el agente, skill o equipo solicitado no existe.
    """


class ValidationError(AntigravityError):
    """Error de validacion de request (400).

    Se lanza cuando los parametros enviados al gateway son invalidos.
    """


class RateLimitError(AntigravityError):
    """Rate limit excedido (429).

    Se lanza cuando se excede el limite de requests por minuto.
    """


class GatewayTimeoutError(AntigravityError):
    """Timeout en la ejecucion (504).

    Se lanza cuando el gateway reporta timeout en la ejecucion de un agente.

    Nota: Se usa el prefijo 'Gateway' para evitar shadow del builtin
    builtins.TimeoutError de Python.
    """


class ServerError(AntigravityError):
    """Error interno del servidor (500+).

    Se lanza para errores no clasificados del lado del servidor.
    """


# ===========================================================================
# Dataclasses de resultado
# ===========================================================================


@dataclass(frozen=True)
class GatewayInfo:
    """Informacion del gateway.

    Attributes:
        name: Nombre del gateway.
        version: Version del gateway.
        status: Estado actual (running, degraded, etc).
        uptime_seconds: Segundos desde el arranque.
        agents: Cantidad de agentes disponibles.
        skills: Cantidad de skills disponibles.
        auth_required: Si la autenticacion esta activa.
        docs_url: URL del schema OpenAPI.
        endpoints: Lista de endpoints disponibles.
        raw: Datos crudos de la respuesta.
    """

    name: str = ""
    version: str = ""
    status: str = ""
    uptime_seconds: int = 0
    agents: int = 0
    skills: int = 0
    auth_required: bool = False
    docs_url: str = ""
    endpoints: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class HealthStatus:
    """Estado de salud del gateway.

    Attributes:
        status: Estado global (healthy, degraded).
        checks: Diccionario de checks individuales.
        uptime_seconds: Segundos desde el arranque.
        sse_connections: Conexiones SSE activas.
        active_teams: Equipos activos.
        raw: Datos crudos de la respuesta.
    """

    status: str = ""
    checks: dict[str, str] = field(default_factory=dict)
    uptime_seconds: int = 0
    sse_connections: int = 0
    active_teams: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def healthy(self) -> bool:
        """Retorna True si el gateway esta completamente saludable."""
        return self.status == "healthy"


@dataclass(frozen=True)
class ReadinessStatus:
    """Estado de readiness del gateway.

    Attributes:
        ready: Si el gateway puede recibir trafico.
        executor_loaded: Si el executor esta cargado.
        agents_available: Si hay agentes disponibles.
        raw: Datos crudos de la respuesta.
    """

    ready: bool = False
    executor_loaded: bool = False
    agents_available: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AgentInfo:
    """Informacion de un agente.

    Attributes:
        name: Nombre del agente.
        description: Descripcion breve.
        tier: Tier del agente (1-12).
        has_executable: Si tiene script ejecutable.
        triggers: Lista de triggers (palabras clave).
        identity_content: Contenido de IDENTITY.md (solo en detalle).
        raw: Datos crudos de la respuesta.
    """

    name: str = ""
    description: str = ""
    tier: int = 0
    has_executable: bool = False
    triggers: list[str] = field(default_factory=list)
    identity_content: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AgentMatch:
    """Resultado de busqueda de agente.

    Attributes:
        agent: Nombre del agente.
        score: Puntuacion de match.
        reasons: Razones del match.
        has_executable: Si tiene script ejecutable.
        raw: Datos crudos de la respuesta.
    """

    agent: str = ""
    score: float = 0.0
    reasons: list[str] = field(default_factory=list)
    has_executable: bool = False
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AgentRunResult:
    """Resultado de ejecucion de un agente.

    Attributes:
        success: Si la ejecucion fue exitosa.
        output: Salida del agente.
        execution_time_ms: Tiempo de ejecucion en milisegundos.
        agent_name: Nombre del agente ejecutado.
        raw: Datos crudos de la respuesta completa.
    """

    success: bool = False
    output: str = ""
    execution_time_ms: float = 0.0
    agent_name: str = ""
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class AutonomousResult:
    """Resultado de ejecucion autonoma (ReAct loop).

    Attributes:
        success: Si la ejecucion fue exitosa.
        output: Salida final del agente.
        status: Estado final (completed, max_iterations, error, etc).
        total_iterations: Total de iteraciones ejecutadas.
        total_cost_usd: Costo total en dolares.
        tools_used: Lista de herramientas utilizadas.
        raw: Datos crudos de la respuesta.
    """

    success: bool = False
    output: str = ""
    status: str = ""
    total_iterations: int = 0
    total_cost_usd: float = 0.0
    tools_used: list[str] = field(default_factory=list)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class SkillInfo:
    """Informacion basica de una skill.

    Attributes:
        name: Nombre de la skill.
        description: Descripcion breve.
        source: Origen (main, custom).
    """

    name: str = ""
    description: str = ""
    source: str = "main"


@dataclass(frozen=True)
class SkillDetail:
    """Detalle completo de una skill.

    Attributes:
        name: Nombre de la skill.
        content: Contenido completo de SKILL.md.
        source: Origen (main, custom).
        size_bytes: Tamano en bytes.
        raw: Datos crudos de la respuesta.
    """

    name: str = ""
    content: str = ""
    source: str = "main"
    size_bytes: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class TeamInfo:
    """Informacion de un equipo de agentes.

    Attributes:
        id: ID unico del equipo.
        name: Nombre del equipo.
        lead: Agente lider.
        members: Lista de miembros con rol y descripcion.
        status: Estado del equipo.
        execution: Resultado de ejecucion (si execute=True).
        raw: Datos crudos de la respuesta.
    """

    id: str = ""
    name: str = ""
    lead: str = ""
    members: list[dict[str, str]] = field(default_factory=list)
    status: str = ""
    execution: dict[str, Any] | None = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class TeamMessageResult:
    """Resultado de envio de mensaje en equipo.

    Attributes:
        sent: Si el mensaje fue enviado exitosamente.
        from_agent: Agente emisor.
        to_agent: Agente receptor.
        conversation: Resumen de la conversacion.
        raw: Datos crudos de la respuesta.
    """

    sent: bool = False
    from_agent: str = ""
    to_agent: str = ""
    conversation: Any = None
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class CostReport:
    """Reporte de costos de ejecucion.

    Attributes:
        days: Periodo del reporte en dias.
        data: Datos del reporte.
        raw: Datos crudos de la respuesta.
    """

    days: int = 30
    data: dict[str, Any] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


@dataclass(frozen=True)
class HistoryEntry:
    """Entrada del historial de ejecuciones.

    Attributes:
        history: Lista de ejecuciones.
        count: Total de entradas retornadas.
        raw: Datos crudos de la respuesta.
    """

    history: list[dict[str, Any]] = field(default_factory=list)
    count: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)


# ===========================================================================
# Paginated result
# ===========================================================================


@dataclass(frozen=True)
class PaginatedResult:
    """Resultado paginado generico.

    Attributes:
        items: Lista de items de la pagina actual.
        total: Total de items disponibles.
        offset: Offset de la pagina actual.
        limit: Limite de items por pagina.
        raw: Datos crudos de la respuesta.
    """

    items: list[Any] = field(default_factory=list)
    total: int = 0
    offset: int = 0
    limit: int = 0
    raw: dict[str, Any] = field(default_factory=dict, repr=False)

    @property
    def has_more(self) -> bool:
        """Retorna True si hay mas paginas disponibles."""
        return (self.offset + self.limit) < self.total


# ===========================================================================
# Cliente principal
# ===========================================================================


class Client:
    """Cliente SDK para el Gateway HTTP Antigravity v2.

    Conecta a cualquier instancia del gateway y expone todos los endpoints
    /v1/ como metodos Python con tipado fuerte.

    Usa solo urllib.request de la stdlib (sin dependencias externas).
    Incluye retry automatico con backoff exponencial para errores de red.

    Args:
        base_url: URL base del gateway. Default: http://127.0.0.1:4747.
                  Tambien puede configurarse con la variable de entorno
                  ANTIGRAVITY_GATEWAY_URL.
        api_key: API key para autenticacion. Default: None (lee de env
                 ANTIGRAVITY_API_KEY).
        timeout: Timeout por defecto en segundos para requests HTTP.
        max_retries: Numero maximo de reintentos para errores de red.
        verify_ssl: Si verificar certificados SSL (True por defecto).

    Example:
        >>> client = Client()
        >>> health = client.health()
        >>> print(health.status)
        'healthy'

        >>> with Client("http://remote:4747", api_key="key") as c:
        ...     result = c.run("explorer", "analizar codebase")
        ...     print(result.success)
        True
    """

    def __init__(
        self,
        base_url: str | None = None,
        api_key: str | None = None,
        timeout: int = DEFAULT_TIMEOUT,
        max_retries: int = MAX_RETRIES,
        verify_ssl: bool = True,
    ) -> None:
        raw_url = base_url or os.environ.get("ANTIGRAVITY_GATEWAY_URL") or DEFAULT_BASE_URL
        # Normalizar: quitar trailing slash
        self._base_url = raw_url.rstrip("/")
        self._api_key = api_key or os.environ.get("ANTIGRAVITY_API_KEY")
        self._timeout = timeout
        self._max_retries = max_retries
        self._verify_ssl = verify_ssl

        # Construir SSL context si es necesario
        self._ssl_context: ssl.SSLContext | None = None
        if not verify_ssl:
            self._ssl_context = ssl.create_default_context()
            self._ssl_context.check_hostname = False
            self._ssl_context.verify_mode = ssl.CERT_NONE

    # ------------------------------------------------------------------
    # Context manager
    # ------------------------------------------------------------------

    def __enter__(self) -> Client:
        """Soporte para 'with Client() as c:'."""
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Cierre del context manager. Limpieza de recursos si es necesario."""
        self.close()

    def close(self) -> None:
        """Cierra el cliente. Actualmente no-op, reservado para futuro pooling."""
        pass

    def __repr__(self) -> str:
        auth_info = "auth=yes" if self._api_key else "auth=no"
        return f"Client({self._base_url!r}, {auth_info})"

    # ------------------------------------------------------------------
    # HTTP internal
    # ------------------------------------------------------------------

    def _build_url(self, path: str, params: dict[str, Any] | None = None) -> str:
        """Construye la URL completa con prefijo /v1 y query params.

        Args:
            path: Path relativo al prefijo /v1 (ej: '/agents', '/health').
            params: Query parameters opcionales.

        Returns:
            URL completa lista para la request.
        """
        url = f"{self._base_url}{API_PREFIX}{path}"
        if params:
            # Filtrar valores None; bool a minusculas (true/false)
            clean: dict[str, str] = {}
            for k, v in params.items():
                if v is None:
                    continue
                if isinstance(v, bool):
                    clean[k] = str(v).lower()
                else:
                    clean[k] = str(v)
            if clean:
                url = f"{url}?{urllib.parse.urlencode(clean)}"
        return url

    def _build_headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        """Construye headers HTTP para la request.

        Args:
            extra: Headers adicionales opcionales.

        Returns:
            Diccionario de headers.
        """
        headers: dict[str, str] = {
            "Accept": "application/json",
            "User-Agent": f"antigravity-sdk-python/{SDK_VERSION}",
        }
        if self._api_key:
            headers["X-API-Key"] = self._api_key
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self,
        method: str,
        path: str,
        params: dict[str, Any] | None = None,
        body: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Ejecuta una request HTTP con retry automatico.

        Args:
            method: Metodo HTTP (GET, POST).
            path: Path relativo a /v1.
            params: Query parameters opcionales.
            body: Body JSON para POST requests.
            timeout: Timeout especifico para esta request.

        Returns:
            Diccionario parseado de la respuesta JSON.

        Raises:
            GatewayConnectionError: No se pudo conectar al gateway.
            AuthenticationError: API key invalida o faltante.
            NotFoundError: Recurso no encontrado.
            ValidationError: Parametros invalidos.
            RateLimitError: Rate limit excedido.
            GatewayTimeoutError: Timeout del gateway.
            ServerError: Error interno del servidor.
        """
        url = self._build_url(path, params)
        headers = self._build_headers()
        effective_timeout = timeout if timeout is not None else self._timeout

        # Preparar body
        data_bytes: bytes | None = None
        if body is not None:
            data_bytes = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"

        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                req = urllib.request.Request(
                    url,
                    data=data_bytes,
                    headers=headers,
                    method=method,
                )

                # Ejecutar request
                kwargs: dict[str, Any] = {"timeout": effective_timeout}
                if self._ssl_context is not None:
                    kwargs["context"] = self._ssl_context

                with urllib.request.urlopen(req, **kwargs) as response:
                    raw_body = response.read().decode("utf-8", errors="replace")
                    if not raw_body:
                        return {"ok": True, "data": None, "timestamp": ""}
                    try:
                        parsed = json.loads(raw_body)
                    except json.JSONDecodeError as je:
                        raise ServerError(
                            f"Respuesta invalida del gateway (no es JSON): {raw_body[:200]}",
                            status_code=0,
                        ) from je
                    if not isinstance(parsed, dict):
                        raise ServerError(
                            "Respuesta invalida del gateway (JSON no es objeto)",
                            status_code=0,
                        )
                    return cast(dict[str, Any], parsed)

            except urllib.error.HTTPError as e:
                # Leer body del error
                error_body_str = ""
                error_body: dict[str, Any] = {}
                try:
                    error_body_str = e.read().decode("utf-8")
                    error_body = json.loads(error_body_str) if error_body_str else {}
                except Exception:
                    pass

                error_msg = (
                    error_body.get("error", "")
                    or error_body.get("message", "")
                    or e.reason
                    or f"HTTP {e.code}"
                )
                status = e.code

                # No reintentar errores de cliente (4xx) excepto 429 y 503
                if status == 401:
                    raise AuthenticationError(
                        f"Autenticacion requerida: {error_msg}",
                        status_code=401,
                        response_body=error_body,
                    )
                elif status == 403:
                    raise AuthenticationError(
                        f"API key invalida: {error_msg}",
                        status_code=403,
                        response_body=error_body,
                    )
                elif status == 404:
                    raise NotFoundError(
                        f"No encontrado: {error_msg}",
                        status_code=404,
                        response_body=error_body,
                    )
                elif status == 400:
                    raise ValidationError(
                        f"Solicitud invalida: {error_msg}",
                        status_code=400,
                        response_body=error_body,
                    )
                elif status == 429:
                    if attempt < self._max_retries:
                        # Leer Retry-After header si existe (puede ser
                        # segundos o fecha RFC 7231; solo parseamos segundos)
                        retry_after = e.headers.get("Retry-After")
                        try:
                            wait = (
                                float(retry_after)
                                if retry_after
                                else (RETRY_BACKOFF_BASE * (2 ** (attempt - 1)))
                            )
                        except (ValueError, TypeError):
                            wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                        logger.warning(
                            "Rate limit excedido, reintentando en %.1fs (intento %d/%d)",
                            wait,
                            attempt,
                            self._max_retries,
                        )
                        time.sleep(wait)
                        last_error = RateLimitError(
                            error_msg,
                            status_code=429,
                            response_body=error_body,
                        )
                        continue
                    raise RateLimitError(
                        f"Rate limit excedido despues de {self._max_retries} intentos: {error_msg}",
                        status_code=429,
                        response_body=error_body,
                    )
                elif status == 504:
                    raise GatewayTimeoutError(
                        f"Timeout del gateway: {error_msg}",
                        status_code=504,
                        response_body=error_body,
                    )
                elif status == 503:
                    # Servicio no disponible, reintentar
                    if attempt < self._max_retries:
                        wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                        logger.warning(
                            "Servicio no disponible, reintentando en %.1fs (intento %d/%d)",
                            wait,
                            attempt,
                            self._max_retries,
                        )
                        time.sleep(wait)
                        last_error = ServerError(
                            error_msg,
                            status_code=503,
                            response_body=error_body,
                        )
                        continue
                    raise ServerError(
                        f"Servicio no disponible: {error_msg}",
                        status_code=503,
                        response_body=error_body,
                    )
                else:
                    raise ServerError(
                        f"Error del servidor ({status}): {error_msg}",
                        status_code=status,
                        response_body=error_body,
                    )

            except urllib.error.URLError as e:
                # Error de conexion (DNS, refused, etc)
                if attempt < self._max_retries:
                    wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "Error de conexion (%s), reintentando en %.1fs (intento %d/%d)",
                        e.reason,
                        wait,
                        attempt,
                        self._max_retries,
                    )
                    time.sleep(wait)
                    last_error = e
                    continue
                raise GatewayConnectionError(
                    f"No se pudo conectar al gateway en {self._base_url}: {e.reason}",
                    status_code=0,
                ) from e

            except OSError as e:
                # Timeout de socket (builtins.TimeoutError hereda de OSError)
                # u otro error de red
                if attempt < self._max_retries:
                    wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "Timeout/Error de red (%s), reintentando en %.1fs (intento %d/%d)",
                        e,
                        wait,
                        attempt,
                        self._max_retries,
                    )
                    time.sleep(wait)
                    last_error = e
                    continue
                raise GatewayConnectionError(
                    f"Error de red con el gateway en {self._base_url}: {e}",
                    status_code=0,
                ) from e

        # No deberia llegar aqui, pero por seguridad
        raise GatewayConnectionError(
            f"Fallo despues de {self._max_retries} intentos: {last_error}",
            status_code=0,
        )

    def _get(
        self,
        path: str,
        params: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Shortcut para GET request.

        Args:
            path: Path relativo a /v1.
            params: Query parameters opcionales.
            timeout: Timeout especifico.

        Returns:
            Respuesta parseada.
        """
        return self._request("GET", path, params=params, timeout=timeout)

    def _post(
        self,
        path: str,
        body: dict[str, Any] | None = None,
        timeout: int | None = None,
    ) -> dict[str, Any]:
        """Shortcut para POST request.

        Args:
            path: Path relativo a /v1.
            body: Body JSON.
            timeout: Timeout especifico.

        Returns:
            Respuesta parseada.
        """
        return self._request("POST", path, body=body, timeout=timeout)

    def _extract_data(self, response: dict[str, Any]) -> Any:
        """Extrae el campo 'data' del envelope de respuesta del gateway.

        El gateway v2 responde con envelope {ok, timestamp, data, error?}.
        Este metodo valida el envelope y extrae 'data'.

        Args:
            response: Respuesta cruda del gateway.

        Returns:
            Contenido del campo 'data'.

        Raises:
            ServerError: Si el envelope indica error (ok=False).
        """
        if not isinstance(response, dict):
            return response

        # Si el gateway respondio con ok=False, lanzar error
        if response.get("ok") is False:
            error_msg = response.get("error", "Error desconocido del gateway")
            raise ServerError(
                error_msg,
                status_code=0,
                response_body=response,
            )

        return response.get("data", response)

    # ==================================================================
    # Endpoints publicos
    # ==================================================================

    # ------------------------------------------------------------------
    # Gateway info
    # ------------------------------------------------------------------

    def info(self) -> GatewayInfo:
        """Obtiene informacion general del gateway.

        Returns:
            GatewayInfo con datos del gateway (version, agentes, skills, etc).

        Raises:
            GatewayConnectionError: No se pudo conectar.
            AntigravityError: Error del gateway.

        Example:
            >>> info = client.info()
            >>> print(f"Gateway v{info.version} con {info.agents} agentes")
        """
        resp = self._get("/")
        data = self._extract_data(resp)
        return GatewayInfo(
            name=data.get("name", ""),
            version=data.get("version", ""),
            status=data.get("status", ""),
            uptime_seconds=data.get("uptime_seconds", 0),
            agents=data.get("agents", 0),
            skills=data.get("skills", 0),
            auth_required=data.get("auth_required", False),
            docs_url=data.get("docs", ""),
            endpoints=data.get("endpoints", []),
            raw=data,
        )

    # ------------------------------------------------------------------
    # Health y readiness
    # ------------------------------------------------------------------

    def health(self) -> HealthStatus:
        """Verifica el estado de salud del gateway (liveness).

        Returns:
            HealthStatus con checks individuales y estado global.

        Raises:
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> h = client.health()
            >>> print(h.healthy)  # True/False
            >>> print(h.checks)   # {'gateway': 'ok', 'executor': 'ok', ...}
        """
        resp = self._get("/health", timeout=10)
        data = self._extract_data(resp)
        return HealthStatus(
            status=data.get("status", ""),
            checks=data.get("checks", {}),
            uptime_seconds=data.get("uptime_seconds", 0),
            sse_connections=data.get("sse_connections", 0),
            active_teams=data.get("active_teams", 0),
            raw=data,
        )

    def ready(self) -> ReadinessStatus:
        """Verifica si el gateway puede recibir trafico (readiness).

        Returns:
            ReadinessStatus con informacion de disponibilidad.

        Raises:
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> r = client.ready()
            >>> if r.ready:
            ...     print("Gateway listo para recibir trafico")
        """
        resp = self._get("/ready", timeout=10)
        data = self._extract_data(resp)
        return ReadinessStatus(
            ready=data.get("ready", False),
            executor_loaded=data.get("executor_loaded", False),
            agents_available=data.get("agents_available", False),
            raw=data,
        )

    # ------------------------------------------------------------------
    # Agents
    # ------------------------------------------------------------------

    def list_agents(
        self,
        filter: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> PaginatedResult:
        """Lista los agentes disponibles con paginacion.

        Args:
            filter: Filtro de agentes. Valores: "all", "executable".
            offset: Offset para paginacion (default: 0).
            limit: Limite de resultados (default: 50, max: 100).

        Returns:
            PaginatedResult con lista de AgentInfo en .items.

        Raises:
            GatewayConnectionError: No se pudo conectar.
            ServerError: Error del gateway.

        Example:
            >>> agents = client.list_agents(filter="executable")
            >>> for a in agents.items:
            ...     print(f"{a.name} - {a.description}")
            >>> if agents.has_more:
            ...     more = client.list_agents(offset=agents.offset + agents.limit)
        """
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if filter:
            params["filter"] = filter

        resp = self._get("/agents", params=params)
        data = self._extract_data(resp)

        agents_raw = data.get("agents", [])
        agents = [
            AgentInfo(
                name=a.get("name", ""),
                description=a.get("description", ""),
                tier=a.get("tier", 0),
                has_executable=a.get("has_executable", False),
                triggers=a.get("triggers", []),
                raw=a,
            )
            for a in agents_raw
        ]

        return PaginatedResult(
            items=agents,
            total=data.get("total", len(agents)),
            offset=data.get("offset", offset),
            limit=data.get("limit", limit),
            raw=data,
        )

    def get_agent(self, name: str) -> AgentInfo:
        """Obtiene informacion detallada de un agente especifico.

        Args:
            name: Nombre del agente (ej: 'explorer', 'architect').

        Returns:
            AgentInfo con datos detallados incluyendo IDENTITY.md.

        Raises:
            NotFoundError: Agente no encontrado.
            ValidationError: Nombre de agente invalido.
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> agent = client.get_agent("explorer")
            >>> print(agent.identity_content)
        """
        resp = self._get(f"/agents/{urllib.parse.quote(name, safe='')}")
        data = self._extract_data(resp)
        return AgentInfo(
            name=data.get("name", ""),
            description=data.get("description", ""),
            tier=data.get("tier", 0),
            has_executable=data.get("has_executable", False),
            triggers=data.get("triggers", []),
            identity_content=data.get("identity_content", ""),
            raw=data,
        )

    def run(
        self,
        agent: str,
        task: str,
        timeout: int = 120,
    ) -> AgentRunResult:
        """Ejecuta un agente con una tarea especifica.

        Args:
            agent: Nombre del agente a ejecutar.
            task: Descripcion de la tarea.
            timeout: Timeout en segundos (default: 120, max: 300).

        Returns:
            AgentRunResult con el output del agente.

        Raises:
            NotFoundError: Agente no encontrado.
            ValidationError: Parametros invalidos.
            GatewayTimeoutError: Timeout en la ejecucion.
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> result = client.run("explorer", "analizar modulo de pagos", timeout=30)
            >>> print(result.success)
            >>> print(result.output)
            >>> print(f"Tiempo: {result.execution_time_ms}ms")
        """
        if len(task) > MAX_TASK_LENGTH:
            raise ValidationError(
                f"Tarea excede el limite de {MAX_TASK_LENGTH} caracteres ({len(task)} enviados)",
                status_code=400,
            )
        resp = self._post(
            f"/agents/{urllib.parse.quote(agent, safe='')}/run",
            body={"task": task, "timeout": timeout},
            timeout=timeout + 10,  # Margen sobre el timeout del agente
        )
        data = self._extract_data(resp)
        return AgentRunResult(
            success=data.get("success", False),
            output=data.get("output", str(data)),
            execution_time_ms=data.get("execution_time_ms", 0.0),
            agent_name=data.get("agent_name", agent),
            raw=data,
        )

    def find(
        self,
        task_description: str,
        limit: int = 5,
    ) -> list[AgentMatch]:
        """Busca los mejores agentes para una tarea dada.

        Utiliza el sistema de clasificacion del gateway (keywords, triggers,
        capability registry) para rankear agentes por relevancia.

        Args:
            task_description: Descripcion de la tarea.
            limit: Maximo de resultados (default: 5, max: 20).

        Returns:
            Lista de AgentMatch ordenada por score descendente.

        Raises:
            ValidationError: Parametros invalidos.
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> matches = client.find("optimizar performance React")
            >>> for m in matches:
            ...     print(f"{m.agent}: {m.score} - {m.reasons}")
        """
        resp = self._post(
            "/agents/find",
            body={"task_description": task_description, "limit": limit},
        )
        data = self._extract_data(resp)
        matches_raw = data.get("matches", [])
        return [
            AgentMatch(
                agent=m.get("agent", ""),
                score=m.get("score", 0.0),
                reasons=m.get("reasons", []),
                has_executable=m.get("has_executable", False),
                raw=m,
            )
            for m in matches_raw
        ]

    # ------------------------------------------------------------------
    # Autonomous
    # ------------------------------------------------------------------

    def autonomous(
        self,
        agent_name: str,
        task: str,
        max_iterations: int = 15,
    ) -> AutonomousResult:
        """Ejecuta un agente en modo autonomo (ReAct loop).

        El agente ejecuta un ciclo de razonamiento y accion con herramientas
        hasta completar la tarea o alcanzar el maximo de iteraciones.

        Args:
            agent_name: Nombre del agente.
            task: Descripcion de la tarea.
            max_iterations: Maximo de iteraciones (default: 15, max: 50).

        Returns:
            AutonomousResult con la salida final y metricas.

        Raises:
            NotFoundError: Agente no encontrado.
            ValidationError: Parametros invalidos.
            GatewayTimeoutError: Timeout en la ejecucion autonoma.
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> result = client.autonomous(
            ...     "security-auditor",
            ...     "auditar modulo de autenticacion",
            ...     max_iterations=10,
            ... )
            >>> print(f"Status: {result.status}")
            >>> print(f"Iteraciones: {result.total_iterations}")
            >>> print(f"Costo: ${result.total_cost_usd:.4f}")
        """
        if len(task) > MAX_TASK_LENGTH:
            raise ValidationError(
                f"Tarea excede el limite de {MAX_TASK_LENGTH} caracteres ({len(task)} enviados)",
                status_code=400,
            )
        # Timeout proporcional a iteraciones (30s/iteracion + margen)
        request_timeout = max_iterations * 30 + 60

        resp = self._post(
            "/autonomous",
            body={
                "agent_name": agent_name,
                "task": task,
                "max_iterations": max_iterations,
            },
            timeout=request_timeout,
        )
        data = self._extract_data(resp)
        return AutonomousResult(
            success=data.get("success", False),
            output=data.get("output", data.get("final_output", str(data))),
            status=data.get("status", ""),
            total_iterations=data.get("total_iterations", 0),
            total_cost_usd=data.get("total_cost_usd", 0.0),
            tools_used=data.get("tools_used", []),
            raw=data,
        )

    # ------------------------------------------------------------------
    # Teams
    # ------------------------------------------------------------------

    def create_team(
        self,
        task: str,
        agents: list[str] | None = None,
        lead: str | None = None,
        auto_select: bool = False,
        execute: bool = False,
    ) -> TeamInfo:
        """Crea un equipo de agentes para colaboracion.

        Args:
            task: Descripcion de la tarea del equipo.
            agents: Lista de nombres de agentes. Si vacio y auto_select=True,
                    se seleccionan automaticamente.
            lead: Agente lider del equipo. Si None, se elige automaticamente.
            auto_select: Si True, selecciona agentes automaticamente.
            execute: Si True, ejecuta el equipo inmediatamente.

        Returns:
            TeamInfo con datos del equipo creado.

        Raises:
            ValidationError: Parametros invalidos.
            ServerError: Error al crear el equipo.
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> team = client.create_team(
            ...     task="crear API REST con auth",
            ...     agents=["architect", "api-designer", "security-auditor"],
            ...     lead="architect",
            ...     execute=True,
            ... )
            >>> print(f"Equipo: {team.name} ({team.id})")
            >>> for m in team.members:
            ...     print(f"  {m['name']} - {m['role']}")
        """
        body: dict[str, Any] = {"task": task}
        if agents:
            body["agents"] = agents
        if lead:
            body["lead"] = lead
        if auto_select:
            body["auto_select"] = True
        if execute:
            body["execute"] = True

        resp = self._post("/teams", body=body, timeout=300 if execute else 30)
        data = self._extract_data(resp)

        return TeamInfo(
            id=data.get("team_id", ""),
            name=data.get("name", ""),
            lead=data.get("lead", ""),
            members=data.get("members", []),
            status=data.get("status", ""),
            execution=data.get("execution"),
            raw=data,
        )

    def team_message(
        self,
        team_id: str,
        from_a: str,
        to_a: str,
        content: str,
    ) -> TeamMessageResult:
        """Envia un mensaje entre agentes dentro de un equipo.

        Args:
            team_id: ID del equipo.
            from_a: Nombre del agente emisor.
            to_a: Nombre del agente receptor.
            content: Contenido del mensaje.

        Returns:
            TeamMessageResult con confirmacion y resumen de conversacion.

        Raises:
            NotFoundError: Equipo no encontrado.
            ValidationError: Parametros invalidos.
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> msg = client.team_message(
            ...     team.id,
            ...     from_a="architect",
            ...     to_a="api-designer",
            ...     content="Necesitamos endpoints para usuarios y auth",
            ... )
            >>> print(msg.sent)
        """
        resp = self._post(
            f"/teams/{urllib.parse.quote(team_id, safe='')}/message",
            body={
                "from_agent": from_a,
                "to_agent": to_a,
                "content": content,
            },
        )
        data = self._extract_data(resp)
        return TeamMessageResult(
            sent=data.get("sent", False),
            from_agent=data.get("from", from_a),
            to_agent=data.get("to", to_a),
            conversation=data.get("conversation"),
            raw=data,
        )

    # ------------------------------------------------------------------
    # Skills
    # ------------------------------------------------------------------

    def list_skills(
        self,
        search: str | None = None,
        offset: int = 0,
        limit: int = 50,
    ) -> PaginatedResult:
        """Lista las skills disponibles con busqueda y paginacion.

        Args:
            search: Termino de busqueda (filtra por nombre y descripcion).
            offset: Offset para paginacion (default: 0).
            limit: Limite de resultados (default: 50, max: 100).

        Returns:
            PaginatedResult con lista de SkillInfo en .items.

        Raises:
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> skills = client.list_skills(search="docker")
            >>> for s in skills.items:
            ...     print(f"{s.name} [{s.source}] - {s.description}")
        """
        params: dict[str, Any] = {"offset": offset, "limit": limit}
        if search:
            params["search"] = search

        resp = self._get("/skills", params=params)
        data = self._extract_data(resp)

        skills_raw = data.get("skills", [])
        skills = [
            SkillInfo(
                name=s.get("name", ""),
                description=s.get("description", ""),
                source=s.get("source", "main"),
            )
            for s in skills_raw
        ]

        return PaginatedResult(
            items=skills,
            total=data.get("total", len(skills)),
            offset=data.get("offset", offset),
            limit=data.get("limit", limit),
            raw=data,
        )

    def read_skill(self, name: str) -> SkillDetail:
        """Lee el contenido completo de SKILL.md de una skill.

        Args:
            name: Nombre de la skill (ej: 'docker-expert').

        Returns:
            SkillDetail con el contenido completo.

        Raises:
            NotFoundError: Skill no encontrada.
            ValidationError: Nombre de skill invalido.
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> skill = client.read_skill("docker-expert")
            >>> print(skill.content[:200])
            >>> print(f"Tamano: {skill.size_bytes} bytes")
        """
        resp = self._get(f"/skills/{urllib.parse.quote(name, safe='')}")
        data = self._extract_data(resp)
        return SkillDetail(
            name=data.get("name", name),
            content=data.get("content", ""),
            source=data.get("source", "main"),
            size_bytes=data.get("size_bytes", 0),
            raw=data,
        )

    # ------------------------------------------------------------------
    # Costs
    # ------------------------------------------------------------------

    def costs(self, days: int = 30) -> CostReport:
        """Obtiene el reporte de costos de ejecucion de agentes.

        Args:
            days: Periodo en dias para el reporte (default: 30, max: 365).

        Returns:
            CostReport con datos de costos por agente/periodo.

        Raises:
            GatewayConnectionError: No se pudo conectar.
            ServerError: Executor no disponible.

        Example:
            >>> costs = client.costs(days=7)
            >>> print(costs.data)
        """
        resp = self._get("/costs", params={"days": days})
        data = self._extract_data(resp)
        return CostReport(
            days=days,
            data=data if isinstance(data, dict) else {"report": data},
            raw=data if isinstance(data, dict) else {},
        )

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    def history(self, limit: int = 10) -> HistoryEntry:
        """Obtiene el historial de ejecuciones recientes.

        Args:
            limit: Maximo de entradas (default: 10, max: 100).

        Returns:
            HistoryEntry con lista de ejecuciones y conteo.

        Raises:
            GatewayConnectionError: No se pudo conectar.
            ServerError: Executor no disponible.

        Example:
            >>> h = client.history(limit=5)
            >>> for entry in h.history:
            ...     print(f"{entry.get('agent')} - {entry.get('task', '')[:50]}")
        """
        resp = self._get("/history", params={"limit": limit})
        data = self._extract_data(resp)
        return HistoryEntry(
            history=data.get("history", []),
            count=data.get("count", 0),
            raw=data,
        )

    # ------------------------------------------------------------------
    # Metrics
    # ------------------------------------------------------------------

    def metrics(self) -> str:
        """Obtiene metricas en formato Prometheus.

        Returns:
            String con metricas en formato text/plain Prometheus.

        Raises:
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> metrics_text = client.metrics()
            >>> for line in metrics_text.split('\\n'):
            ...     if not line.startswith('#'):
            ...         print(line)
        """
        url = self._build_url("/metrics")
        headers = self._build_headers({"Accept": "text/plain"})
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                req = urllib.request.Request(url, headers=headers, method="GET")
                kwargs: dict[str, Any] = {"timeout": 10}
                if self._ssl_context is not None:
                    kwargs["context"] = self._ssl_context
                with urllib.request.urlopen(req, **kwargs) as response:
                    payload = response.read().decode("utf-8", errors="replace")
                    return cast(str, payload)
            except urllib.error.HTTPError as e:
                raise ServerError(
                    f"Error al obtener metricas: HTTP {e.code}",
                    status_code=e.code,
                ) from e
            except (urllib.error.URLError, OSError) as e:
                if attempt < self._max_retries:
                    wait = RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                    time.sleep(wait)
                    last_error = e
                    continue
                reason = getattr(e, "reason", str(e))
                raise GatewayConnectionError(
                    f"No se pudo conectar al gateway: {reason}",
                ) from e

        raise GatewayConnectionError(
            f"Fallo metricas despues de {self._max_retries} intentos: {last_error}",
        )

    # ------------------------------------------------------------------
    # OpenAPI schema
    # ------------------------------------------------------------------

    def openapi(self) -> dict[str, Any]:
        """Obtiene el schema OpenAPI 3.0 del gateway.

        Returns:
            Diccionario con el schema OpenAPI completo.

        Raises:
            GatewayConnectionError: No se pudo conectar.

        Example:
            >>> schema = client.openapi()
            >>> print(f"Version: {schema['info']['version']}")
            >>> print(f"Endpoints: {len(schema['paths'])}")
        """
        resp = self._get("/openapi.json")
        # El schema OpenAPI no usa el envelope {ok, data}, se retorna directo
        return resp

    # ------------------------------------------------------------------
    # Utility methods
    # ------------------------------------------------------------------

    def ping(self) -> bool:
        """Verifica conectividad basica con el gateway.

        Returns:
            True si el gateway responde, False si no.

        Example:
            >>> if client.ping():
            ...     print("Gateway accesible")
            ... else:
            ...     print("Gateway no responde")
        """
        try:
            self.health()
            return True
        except AntigravityError:
            return False
        except Exception:
            return False

    def wait_ready(self, timeout: int = 60, interval: float = 2.0) -> bool:
        """Espera hasta que el gateway este listo para recibir trafico.

        Util para scripts que inician el gateway y necesitan esperar a que
        este completamente operativo.

        Args:
            timeout: Tiempo maximo de espera en segundos.
            interval: Intervalo entre checks en segundos.

        Returns:
            True si el gateway esta listo, False si se alcanzo el timeout.

        Example:
            >>> # Despues de iniciar el gateway
            >>> if client.wait_ready(timeout=30):
            ...     result = client.run("explorer", "analizar codebase")
            ... else:
            ...     print("Gateway no arranco a tiempo")
        """
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                status = self.ready()
                if status.ready:
                    return True
            except AntigravityError:
                pass
            except Exception:
                pass
            time.sleep(interval)
        return False
