"""
Instrumentación OpenTelemetry para Antigravity Gateway.
=======================================================

Telemetría con degradación elegante: si OpenTelemetry no está instalado,
todas las operaciones son no-ops silenciosos.

Configuración vía variables de entorno:
    OTEL_EXPORTER_OTLP_ENDPOINT  - Endpoint OTLP (default: ninguno)
    OTEL_SERVICE_NAME            - Nombre del servicio
    OTEL_LOG_LEVEL               - Si es "debug", activa console exporter
"""

from __future__ import annotations

import asyncio
import logging
import os
import re
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from collections.abc import Generator
from typing import Any

# --- aiohttp (requerido por el gateway) ---
try:
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False
    web = None  # type: ignore[assignment]

# --- OpenTelemetry — todos opcionales ---
_OTEL_AVAILABLE = False
_OTEL_METRICS_AVAILABLE = False
_OTEL_EXPORTER_OTLP_AVAILABLE = False
_PROMETHEUS_AVAILABLE = False

try:
    from opentelemetry import trace as otel_trace
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter
    from opentelemetry.trace import SpanKind, StatusCode, get_current_span

    _OTEL_AVAILABLE = True
except ImportError:
    pass

try:
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        ConsoleMetricExporter,
        PeriodicExportingMetricReader,
    )

    _OTEL_METRICS_AVAILABLE = True
except ImportError:
    pass

try:
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

    _OTEL_EXPORTER_OTLP_AVAILABLE = True
except ImportError:
    try:
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter  # type: ignore[assignment]

        _OTEL_EXPORTER_OTLP_AVAILABLE = True
    except ImportError:
        pass

try:
    from prometheus_client import (
        CollectorRegistry,
        Counter as PromCounter,
        Histogram as PromHistogram,
        generate_latest,
    )

    _PROMETHEUS_AVAILABLE = True
except ImportError:
    pass

try:
    import httpx

    _HTTPX_AVAILABLE = True
except ImportError:
    _HTTPX_AVAILABLE = False

log = logging.getLogger("antigravity-gateway.telemetry")
_telemetry_instance: TelemetryManager | None = None

# Patrones de normalización compilados
_RE_AGENT_RUN = re.compile(r"/v1/agents/([^/]+)/run")
_RE_AGENT = re.compile(r"/v1/agents/([^/]+)$")
_RE_SKILL = re.compile(r"/v1/skills/([^/]+)$")
_RE_TEAM_MSG = re.compile(r"/v1/teams/([^/]+)/message")


# ============================================================
# No-op stubs para cuando OTel no está disponible
# ============================================================
class _NoOpSpan:
    """Span ficticio que no registra nada."""

    def set_attribute(self, key: str, value: Any) -> None:
        pass

    def set_status(self, status: Any, description: str | None = None) -> None:
        pass

    def record_exception(
        self, exception: BaseException, attributes: dict[str, Any] | None = None
    ) -> None:
        pass

    def add_event(self, name: str, attributes: dict[str, Any] | None = None) -> None:
        pass

    def end(self) -> None:
        pass

    def __enter__(self) -> _NoOpSpan:
        return self

    def __exit__(self, *args: Any) -> None:
        pass


class _NoOpTracer:
    """Tracer ficticio."""

    def start_span(self, name: str, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()

    def start_as_current_span(self, name: str, **kwargs: Any) -> _NoOpSpan:
        return _NoOpSpan()


class _NoOpCounter:
    """Contador ficticio."""

    def add(self, amount: int | float = 1, attributes: dict[str, Any] | None = None) -> None:
        pass


class _NoOpHistogram:
    """Histograma ficticio."""

    def record(self, value: float, attributes: dict[str, Any] | None = None) -> None:
        pass


class _NoOpUpDownCounter:
    """Up-down counter ficticio."""

    def add(self, amount: int | float = 1, attributes: dict[str, Any] | None = None) -> None:
        pass


# ============================================================
# TelemetryManager
# ============================================================
@dataclass
class TelemetryManager:
    """Gestor de telemetría OpenTelemetry para el Gateway.

    Encapsula tracer, meter y métricas Prometheus con degradación elegante.
    """

    service_name: str = "antigravity-gateway"
    enabled: bool = False
    _tracer: Any = field(default=None, repr=False)
    _tracer_provider: Any = field(default=None, repr=False)
    _meter_provider: Any = field(default=None, repr=False)
    # Métricas OTel
    requests_total: Any = field(default=None, repr=False)
    requests_duration: Any = field(default=None, repr=False)
    active_connections: Any = field(default=None, repr=False)
    agent_executions: Any = field(default=None, repr=False)
    skill_lookups: Any = field(default=None, repr=False)
    errors_total: Any = field(default=None, repr=False)
    websocket_connections: Any = field(default=None, repr=False)
    # Prometheus nativo
    _prom_registry: Any = field(default=None, repr=False)
    _prom_requests_total: Any = field(default=None, repr=False)
    _prom_requests_duration: Any = field(default=None, repr=False)
    _prom_errors_total: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        """Inicializa proveedores de telemetría si están disponibles."""
        self._setup_tracing()
        self._setup_metrics()
        self._setup_prometheus()

    def _setup_tracing(self) -> None:
        """Configura el proveedor de trazas y exportadores."""
        if not _OTEL_AVAILABLE:
            self._tracer = _NoOpTracer()
            return

        resource = Resource.create(
            {
                "service.name": self.service_name,
                "service.version": "2.0.0",
                "deployment.environment": os.environ.get("OTEL_ENVIRONMENT", "development"),
            }
        )
        self._tracer_provider = TracerProvider(resource=resource)

        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT")
        if _OTEL_EXPORTER_OTLP_AVAILABLE and otlp_endpoint:
            try:
                self._tracer_provider.add_span_processor(
                    BatchSpanProcessor(OTLPSpanExporter(endpoint=otlp_endpoint))
                )
                log.info("OTLP trace exporter configurado → %s", otlp_endpoint)
            except Exception as exc:
                log.warning("No se pudo configurar OTLP exporter: %s", exc)

        if os.environ.get("OTEL_LOG_LEVEL", "").lower() == "debug":
            self._tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        otel_trace.set_tracer_provider(self._tracer_provider)
        self._tracer = self._tracer_provider.get_tracer(
            self.service_name,
            schema_url="https://opentelemetry.io/schemas/1.21.0",
        )
        self.enabled = True
        log.info("OpenTelemetry trazas inicializadas para '%s'", self.service_name)

    def _setup_metrics(self) -> None:
        """Configura métricas OTel."""
        if not _OTEL_METRICS_AVAILABLE:
            self._init_noop_metrics()
            return

        readers = []
        if os.environ.get("OTEL_LOG_LEVEL", "").lower() == "debug":
            readers.append(
                PeriodicExportingMetricReader(ConsoleMetricExporter(), export_interval_millis=10000)
            )

        resource = Resource.create({"service.name": self.service_name})
        self._meter_provider = (
            MeterProvider(resource=resource, metric_readers=readers)
            if readers
            else MeterProvider(resource=resource)
        )
        meter = self._meter_provider.get_meter(self.service_name, version="2.0.0")

        self.requests_total = meter.create_counter(
            "gateway.requests.total", description="Total de requests", unit="1"
        )
        self.requests_duration = meter.create_histogram(
            "gateway.requests.duration", description="Duración en ms", unit="ms"
        )
        self.active_connections = meter.create_up_down_counter(
            "gateway.active_connections", description="Conexiones activas", unit="1"
        )
        self.agent_executions = meter.create_counter(
            "gateway.agents.executions", description="Ejecuciones de agentes", unit="1"
        )
        self.skill_lookups = meter.create_counter(
            "gateway.skills.lookups", description="Búsquedas de skills", unit="1"
        )
        self.errors_total = meter.create_counter(
            "gateway.errors", description="Errores por tipo", unit="1"
        )
        self.websocket_connections = meter.create_up_down_counter(
            "gateway.websocket.connections", description="Conexiones SSE/WS", unit="1"
        )
        log.info("Métricas OpenTelemetry inicializadas")

    def _init_noop_metrics(self) -> None:
        """Inicializa métricas no-op."""
        self.requests_total = _NoOpCounter()
        self.requests_duration = _NoOpHistogram()
        self.active_connections = _NoOpUpDownCounter()
        self.agent_executions = _NoOpCounter()
        self.skill_lookups = _NoOpCounter()
        self.errors_total = _NoOpCounter()
        self.websocket_connections = _NoOpUpDownCounter()

    def _setup_prometheus(self) -> None:
        """Configura métricas Prometheus nativas."""
        if not _PROMETHEUS_AVAILABLE:
            return
        self._prom_registry = CollectorRegistry()
        self._prom_requests_total = PromCounter(
            "antigravity_gateway_requests_total",
            "Total de requests",
            ["method", "path", "status"],
            registry=self._prom_registry,
        )
        self._prom_requests_duration = PromHistogram(
            "antigravity_gateway_request_duration_ms",
            "Duración en ms",
            ["method", "path"],
            buckets=(5, 10, 25, 50, 100, 250, 500, 1000, 2500, 5000, 10000),
            registry=self._prom_registry,
        )
        self._prom_errors_total = PromCounter(
            "antigravity_gateway_errors_total",
            "Errores por tipo",
            ["error_type"],
            registry=self._prom_registry,
        )

    # --- API pública ---

    @property
    def tracer(self) -> Any:
        """Obtiene el tracer (real o no-op)."""
        return self._tracer

    def get_trace_id(self) -> str | None:
        """Obtiene el trace ID del span actual."""
        if not _OTEL_AVAILABLE:
            return None
        ctx = get_current_span().get_span_context()
        return format(ctx.trace_id, "032x") if ctx and ctx.trace_id else None

    def record_request(self, method: str, path: str, status: int, duration_ms: float) -> None:
        """Registra métricas de un request completado."""
        attrs = {"http.method": method, "http.route": path, "http.status_code": str(status)}
        self.requests_total.add(1, attributes=attrs)
        self.requests_duration.record(
            duration_ms, attributes={"http.method": method, "http.route": path}
        )
        if self._prom_requests_total is not None:
            self._prom_requests_total.labels(method=method, path=path, status=str(status)).inc()
        if self._prom_requests_duration is not None:
            self._prom_requests_duration.labels(method=method, path=path).observe(duration_ms)

    def record_agent_execution(self, agent_name: str, status: str) -> None:
        """Registra la ejecución de un agente."""
        self.agent_executions.add(
            1, attributes={"antigravity.agent.name": agent_name, "status": status}
        )

    def record_skill_lookup(self, skill_name: str | None = None) -> None:
        """Registra una búsqueda de skill."""
        attrs: dict[str, str] = {"antigravity.skill.name": skill_name} if skill_name else {}
        self.skill_lookups.add(1, attributes=attrs)

    def record_error(self, error_type: str) -> None:
        """Registra un error del gateway."""
        self.errors_total.add(1, attributes={"error.type": error_type})
        if self._prom_errors_total is not None:
            self._prom_errors_total.labels(error_type=error_type).inc()

    def get_prometheus_metrics(self) -> bytes:
        """Genera métricas en formato Prometheus text exposition."""
        if not _PROMETHEUS_AVAILABLE or self._prom_registry is None:
            return b"# OpenTelemetry Prometheus metrics not available\n"
        return generate_latest(self._prom_registry)

    def shutdown(self) -> None:
        """Cierra los proveedores de telemetría."""
        for provider in (self._tracer_provider, self._meter_provider):
            if provider is not None and hasattr(provider, "shutdown"):
                try:
                    provider.shutdown()
                except Exception as exc:
                    log.warning("Error cerrando provider: %s", exc)


# ============================================================
# Utilidades de rutas
# ============================================================
def _normalize_path(path: str) -> str:
    """Normaliza rutas reemplazando segmentos dinámicos con placeholders."""
    path = _RE_AGENT_RUN.sub("/v1/agents/:name/run", path)
    path = _RE_AGENT.sub("/v1/agents/:name", path)
    path = _RE_SKILL.sub("/v1/skills/:name", path)
    path = _RE_TEAM_MSG.sub("/v1/teams/:id/message", path)
    return path


def _extract_resource_name(path: str) -> tuple[str | None, str | None]:
    """Extrae nombre de agente o skill de la ruta."""
    agent_m = re.search(r"/v1/agents/([^/]+)", path)
    skill_m = re.search(r"/v1/skills/([^/]+)", path)
    return (agent_m.group(1) if agent_m else None, skill_m.group(1) if skill_m else None)


# ============================================================
# Middleware aiohttp
# ============================================================
async def _handle_request_telemetry(
    request: Any,
    handler: Any,
    manager: TelemetryManager,
    request_id: str,
    start_time: float,
    normalized_path: str,
) -> Any:
    """Lógica compartida para registrar métricas y headers de telemetría."""
    try:
        response = await handler(request)
        duration_ms = (time.monotonic() - start_time) * 1000
        response.headers["X-Request-Id"] = request_id
        manager.record_request(request.method, normalized_path, response.status, duration_ms)
        return response, response.status, duration_ms
    except Exception:
        raise


if AIOHTTP_AVAILABLE:

    @web.middleware
    async def telemetry_middleware(request: web.Request, handler: Any) -> web.StreamResponse:
        """Middleware que instrumenta cada request con OpenTelemetry.

        Crea un span por request, registra métricas de duración y conteo,
        e inyecta el trace ID en los headers de respuesta.
        """
        manager = get_telemetry()
        request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))
        start_time = time.monotonic()
        normalized_path = _normalize_path(request.path)
        agent_name, skill_name = _extract_resource_name(request.path)

        manager.active_connections.add(1)

        span_attributes: dict[str, Any] = {
            "http.method": request.method,
            "http.url": str(request.url),
            "http.target": request.path,
            "http.route": normalized_path,
            "http.scheme": request.scheme,
            "http.host": request.host,
            "antigravity.request_id": request_id,
            "net.peer.ip": request.remote or "unknown",
        }
        if agent_name:
            span_attributes["antigravity.agent.name"] = agent_name
        if skill_name:
            span_attributes["antigravity.skill.name"] = skill_name

        span_name = f"{request.method} {normalized_path}"

        try:
            if _OTEL_AVAILABLE and manager.enabled:
                with manager.tracer.start_as_current_span(
                    span_name,
                    kind=SpanKind.SERVER,
                    attributes=span_attributes,
                ) as span:
                    try:
                        response = await handler(request)
                        status_code = response.status
                        span.set_attribute("http.status_code", status_code)
                        if status_code >= 400:
                            span.set_status(StatusCode.ERROR, f"HTTP {status_code}")
                        duration_ms = (time.monotonic() - start_time) * 1000
                        span.set_attribute("http.request.duration_ms", round(duration_ms, 2))
                        trace_id = manager.get_trace_id()
                        if trace_id:
                            response.headers["X-Trace-Id"] = trace_id
                        response.headers["X-Request-Id"] = request_id
                        manager.record_request(
                            request.method, normalized_path, status_code, duration_ms
                        )
                        return response
                    except web.HTTPException as exc:
                        _record_span_error(
                            span, manager, request, normalized_path, start_time, exc.status, exc
                        )
                        raise
                    except Exception as exc:
                        _record_span_error(
                            span, manager, request, normalized_path, start_time, 500, exc
                        )
                        raise
            else:
                # Sin OTel — solo métricas básicas
                try:
                    response = await handler(request)
                    duration_ms = (time.monotonic() - start_time) * 1000
                    response.headers["X-Request-Id"] = request_id
                    manager.record_request(
                        request.method, normalized_path, response.status, duration_ms
                    )
                    return response
                except web.HTTPException as exc:
                    duration_ms = (time.monotonic() - start_time) * 1000
                    manager.record_request(request.method, normalized_path, exc.status, duration_ms)
                    manager.record_error(type(exc).__name__)
                    raise
                except Exception as exc:
                    duration_ms = (time.monotonic() - start_time) * 1000
                    manager.record_request(request.method, normalized_path, 500, duration_ms)
                    manager.record_error(type(exc).__name__)
                    raise
        finally:
            manager.active_connections.add(-1)

    def _record_span_error(
        span: Any,
        manager: TelemetryManager,
        request: Any,
        normalized_path: str,
        start_time: float,
        status_code: int,
        exc: Exception,
    ) -> None:
        """Registra error en span y métricas."""
        duration_ms = (time.monotonic() - start_time) * 1000
        span.set_attribute("http.status_code", status_code)
        span.set_attribute("http.request.duration_ms", round(duration_ms, 2))
        span.set_status(StatusCode.ERROR, str(exc))
        span.record_exception(exc)
        manager.record_request(request.method, normalized_path, status_code, duration_ms)
        manager.record_error(type(exc).__name__)
else:

    async def telemetry_middleware(request: Any, handler: Any) -> Any:  # type: ignore[misc]
        """Middleware stub cuando aiohttp no está disponible."""
        return await handler(request)


# ============================================================
# Funciones de integración
# ============================================================
def setup_telemetry(
    app: Any | None = None,
    service_name: str = "antigravity-gateway",
) -> TelemetryManager:
    """Configura OpenTelemetry para la aplicación.

    Args:
        app: Instancia de aiohttp.web.Application (opcional).
        service_name: Nombre del servicio para identificación en trazas.

    Returns:
        Instancia configurada de TelemetryManager.
    """
    global _telemetry_instance
    effective_name = os.environ.get("OTEL_SERVICE_NAME", service_name)
    _telemetry_instance = TelemetryManager(service_name=effective_name)

    if app is not None and AIOHTTP_AVAILABLE:
        app.router.add_get("/v1/metrics/otel", _prometheus_metrics_handler)
        app.router.add_get("/v1/health/all", health_aggregator_handler)
        app.on_cleanup.append(_on_app_cleanup)
        log.info("Telemetría registrada — endpoints: /v1/metrics/otel, /v1/health/all")

    return _telemetry_instance


def get_telemetry() -> TelemetryManager:
    """Obtener instancia singleton. Crea una por defecto si no existe."""
    global _telemetry_instance
    if _telemetry_instance is None:
        _telemetry_instance = TelemetryManager()
    return _telemetry_instance


@contextmanager
def trace_operation(
    name: str,
    attributes: dict[str, Any] | None = None,
) -> Generator[Any, None, None]:
    """Traza una operación con un span de OpenTelemetry.

    Si OTel no está disponible, ejecuta sin instrumentación.

    Args:
        name: Nombre del span.
        attributes: Atributos adicionales para el span.

    Yields:
        Span activo (real o no-op).
    """
    manager = get_telemetry()
    if _OTEL_AVAILABLE and manager.enabled:
        with manager.tracer.start_as_current_span(name, attributes=attributes or {}) as span:
            yield span
    else:
        yield _NoOpSpan()


# ============================================================
# Handlers HTTP
# ============================================================
async def _prometheus_metrics_handler(request: Any) -> Any:
    """Handler para /v1/metrics/otel — métricas Prometheus."""
    return web.Response(
        body=get_telemetry().get_prometheus_metrics(),
        content_type="text/plain; version=0.0.4; charset=utf-8",
    )


async def _check_service_health(name: str, url: str, timeout: float = 3.0) -> dict[str, Any]:
    """Verifica la salud de un servicio HTTP externo."""
    if not _HTTPX_AVAILABLE:
        return {"name": name, "status": "unknown", "detail": "httpx no disponible"}
    start = time.monotonic()
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.get(url)
            elapsed_ms = round((time.monotonic() - start) * 1000, 2)
            status = "healthy" if resp.status_code < 400 else "degraded"
            return {
                "name": name,
                "status": status,
                "response_time_ms": elapsed_ms,
                "status_code": resp.status_code,
            }
    except httpx.ConnectError:
        return {"name": name, "status": "unreachable", "detail": "connection refused"}
    except httpx.TimeoutException:
        return {"name": name, "status": "timeout", "detail": f"timeout after {timeout}s"}
    except Exception as exc:
        return {"name": name, "status": "error", "detail": str(exc)}


async def health_aggregator_handler(request: Any) -> Any:
    """Endpoint que reporta el estado de todos los servicios.

    Verifica gateway, Ollama y servidores MCP configurados.
    """
    checks = [
        _check_service_health("ollama", "http://localhost:11434/api/version"),
    ]

    # Servidores MCP adicionales vía env: "name1=url1,name2=url2"
    mcp_servers_env = os.environ.get("ANTIGRAVITY_MCP_HEALTH_URLS", "")
    for entry in mcp_servers_env.split(","):
        entry = entry.strip()
        if "=" in entry:
            srv_name, srv_url = entry.split("=", 1)
            checks.append(_check_service_health(srv_name.strip(), srv_url.strip()))

    results = await asyncio.gather(*checks, return_exceptions=True)

    services: list[dict[str, Any]] = [
        {"name": "gateway", "status": "healthy", "detail": "responding"},
    ]
    for result in results:
        if isinstance(result, Exception):
            services.append({"name": "unknown", "status": "error", "detail": str(result)})
        else:
            services.append(result)  # type: ignore[arg-type]

    statuses = {s["status"] for s in services}
    if statuses <= {"healthy"}:
        overall = "healthy"
    elif "unreachable" in statuses or "error" in statuses:
        overall = "degraded"
    else:
        overall = "partial"

    return web.json_response(
        {
            "status": overall,
            "timestamp": time.time(),
            "services": services,
            "telemetry_enabled": get_telemetry().enabled,
        },
        status=200 if overall == "healthy" else 207,
    )


async def _on_app_cleanup(app: Any) -> None:
    """Limpia recursos de telemetría al cerrar la aplicación."""
    get_telemetry().shutdown()
    log.info("Telemetría cerrada correctamente")
