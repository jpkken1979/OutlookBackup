#!/usr/bin/env python3
# ---------------------------------------------------------------------------
# Ejecutable directo: asegurar que el paquete 'mcp' sea importable
# para que los relative imports de los mixins funcionen.
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import sys
    import importlib
    from pathlib import Path

    _agent_dir = str(Path(__file__).resolve().parent.parent)  # .agent/
    sys.path.insert(0, _agent_dir)

    # Evictar el paquete 'mcp' de pip (MCP SDK) del cache de módulos
    # para que Python use NUESTRO .agent/mcp/ local en vez del de site-packages.
    for _k in [k for k in sys.modules if k == "mcp" or k.startswith("mcp.")]:
        del sys.modules[_k]

    # Importar nuestro paquete mcp local ANTES de setear __package__
    importlib.import_module("mcp")

    __package__ = "mcp"  # noqa: A001

"""
Antigravity MCP HTTP Gateway v3.1
==================================
Gateway HTTP production-ready que expone el ecosistema de agentes via REST API.
Incluye SSE streaming, OpenTelemetry, Event Bus y health aggregation.
WebSocket removido (Option C) para evitar freeze por zombie connections.

Seguridad:
    - Binding a 127.0.0.1 por defecto (solo localhost)
    - Autenticacion via API key (header X-API-Key)
    - CORS configurable
    - Rate limiting por IP
    - Validacion de path traversal
    - Errores sanitizados (sin stack traces)
    - Limites en max_iterations y timeout

Endpoints (prefijo /v1):
    GET  /v1/                    - Info del gateway + OpenAPI schema link
    GET  /v1/health              - Health check (liveness)
    GET  /v1/ready               - Readiness check
    GET  /v1/metrics             - Metricas Prometheus-compatible
    GET  /v1/agents              - Lista agentes (?filter=executable&offset=0&limit=50)
    GET  /v1/agents/:name        - Info detallada de un agente
    POST /v1/agents/:name/run    - Ejecutar agente con tarea
    POST /v1/agents/find         - Buscar mejor agente para tarea
    POST /v1/autonomous          - Ejecutar agente en modo autonomo (ReAct)
    POST /v1/teams               - Crear equipo de agentes
    POST /v1/teams/:id/message   - Enviar mensaje entre agentes del equipo
    GET  /v1/skills              - Listar skills (?search=keyword&offset=0&limit=50)
    GET  /v1/skills/:name        - Leer SKILL.md completo
    GET  /v1/costs               - Reporte de costos (?days=30)
    GET  /v1/history             - Historial de ejecuciones (?limit=10)
    GET  /v1/events              - SSE stream de eventos en tiempo real
    GET  /v1/openapi.json        - Schema OpenAPI 3.0

Uso:
    python gateway.py                              # Puerto 4747, localhost
    python gateway.py --port 4747                   # Puerto especifico
    python gateway.py --host 0.0.0.0               # Exponer a red (requiere API key)
    python gateway.py --no-auth                     # Desactivar auth (solo dev)

Configuracion via env vars:
    ANTIGRAVITY_GATEWAY_PORT   - Puerto (default: 4747)
    ANTIGRAVITY_GATEWAY_HOST   - Host (default: 127.0.0.1)
    ANTIGRAVITY_HOME           - Directorio raiz del ecosistema
    ANTIGRAVITY_API_KEY        - API key para autenticacion
    ANTIGRAVITY_CORS_ORIGINS   - Origenes CORS (comma-separated, default: localhost)
    ANTIGRAVITY_RATE_LIMIT     - Requests por minuto por IP (default: 60)
"""

import sys
import os

# Forzar modo offline de HuggingFace/Transformers ANTES de cualquier import
# que pueda cargar sentence-transformers (directa o transitivamente via
# memory-server o executores). Sin esto, cualquier entry point que no pase
# por start_gateway.py (ej. `python -m mcp.gateway_main` que usa Nexus)
# puede bloquearse al intentar consultar HuggingFace Hub en el primer uso.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")

import re
import asyncio
import json
import logging
import time
import uuid
import hashlib
import hmac
import ipaddress
from pathlib import Path
from typing import Any
from datetime import datetime
from dataclasses import dataclass, field
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor

# Runtime profile — cargado antes de configurar logging para respetar log_level del perfil.
try:
    from .gateway_profiles import load_profile, ProfileConfig
except ImportError:
    from gateway_profiles import load_profile, ProfileConfig  # type: ignore[no-redef]

ACTIVE_PROFILE: ProfileConfig = load_profile()

# Configurar logging estructurado — nivel determinado por el perfil activo
logging.basicConfig(
    level=getattr(logging, ACTIVE_PROFILE.log_level, logging.INFO),
    format="[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s",
    stream=sys.stderr,
)
log = logging.getLogger("antigravity-gateway")

# ============================================================
# Paths
# ============================================================
_ANTIGRAVITY_HOME = os.environ.get("ANTIGRAVITY_HOME")
if _ANTIGRAVITY_HOME:
    BASE_DIR = Path(_ANTIGRAVITY_HOME)
else:
    BASE_DIR = Path(__file__).parent.parent.parent

AGENTS_DIR = BASE_DIR / ".agent" / "agents"
SKILLS_DIR = BASE_DIR / ".agent" / "skills"
SKILLS_CUSTOM_DIR = BASE_DIR / ".agent" / "skills-custom"
CORE_DIR = BASE_DIR / ".agent" / "core"

# Add core to path
sys.path.insert(0, str(CORE_DIR.parent))


def _mcp_broker_v2_enabled(project_root: Path = BASE_DIR) -> bool:
    """Resolve the rollout kill-switch from env, then project configuration."""

    override = os.environ.get("ANTIGRAVITY_MCP_BROKER_V2")
    if override is not None:
        return override.strip().lower() not in {"0", "false", "no", "off"}
    config_path = project_root / ".antigravity" / "config.json"
    try:
        payload = json.loads(config_path.read_text(encoding="utf-8"))
        configured = payload.get("featureFlags", {}).get("mcpBrokerV2")
        if isinstance(configured, bool):
            return configured
    except (OSError, ValueError, TypeError):
        pass
    return True


# ============================================================
# Audit Logger — registro persistente de accesos a endpoints sensibles
# ============================================================
def _setup_audit_logger() -> logging.Logger:
    """Configura el logger de auditoria con rotacion de archivos.

    Returns:
        Logger configurado para escribir en logs/audit.log con rotacion 10MB/5 backups.
    """
    import logging.handlers

    audit_log_dir = BASE_DIR / "logs"
    audit_log_dir.mkdir(parents=True, exist_ok=True)
    audit_log_path = audit_log_dir / "audit.log"

    audit_logger = logging.getLogger("antigravity.audit")
    audit_logger.setLevel(logging.INFO)
    audit_logger.propagate = False  # No propagar al root logger

    handler = logging.handlers.RotatingFileHandler(
        filename=str(audit_log_path),
        maxBytes=10 * 1024 * 1024,  # 10 MB
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(
        logging.Formatter("[%(asctime)s] [AUDIT] %(message)s", datefmt="%Y-%m-%dT%H:%M:%S")
    )
    audit_logger.addHandler(handler)
    return audit_logger


_audit_log: logging.Logger = _setup_audit_logger()

try:
    from .security_utils import (
        DEFAULT_CORS_ORIGINS,
        is_localhost_client as shared_is_localhost_client,
        is_origin_allowed as shared_is_origin_allowed,
        parse_cors_origins,
    )
except ImportError:
    from security_utils import (
        DEFAULT_CORS_ORIGINS,
        is_localhost_client as shared_is_localhost_client,
        is_origin_allowed as shared_is_origin_allowed,
        parse_cors_origins,
    )

try:
    from .session_key import ensure_session_key
except ImportError:
    from session_key import ensure_session_key  # type: ignore[no-redef]

try:
    from .gateway_middleware import RateLimiter, TTLCache, CACHE_TTL_SECONDS  # noqa: F401
except ImportError:
    from gateway_middleware import RateLimiter, TTLCache  # type: ignore[no-redef]

try:
    from .openapi_schema import build_openapi_schema as _build_openapi_schema_fn
except ImportError:
    from openapi_schema import build_openapi_schema as _build_openapi_schema_fn  # type: ignore[no-redef]

try:
    from .gateway_events import EventManager
except ImportError:
    from gateway_events import EventManager  # type: ignore[no-redef]

# Import AgentExecutor — primero intenta agents-server.py, luego core.llm
try:
    import importlib.util

    _server_path = Path(__file__).parent / "agents-server.py"
    _spec = importlib.util.spec_from_file_location("agents_server", _server_path)
    if _spec is not None and _spec.loader is not None:
        _agents_server = importlib.util.module_from_spec(_spec)

        os.environ.setdefault("ANTIGRAVITY_HOME", str(BASE_DIR))
        _spec.loader.exec_module(_agents_server)
    else:
        raise ImportError(f"Could not load spec from {_server_path}")

    AgentExecutor = _agents_server.AgentExecutor
    EXECUTOR_AVAILABLE = True
    log.info("AgentExecutor cargado desde %s", _server_path)
except (AttributeError, Exception):
    # Fallback: usar GatewayExecutor del core (adaptador del orquestador)
    try:
        from core.gateway_executor import AgentExecutor  # type: ignore[assignment]

        EXECUTOR_AVAILABLE = True
        log.info("AgentExecutor cargado desde core.gateway_executor")
    except Exception as e2:
        log.warning("AgentExecutor no disponible: %s", e2)
        EXECUTOR_AVAILABLE = False
        AgentExecutor = None

# Verificar aiohttp
try:
    from aiohttp import web

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# ============================================================
# Constantes y limites
# ============================================================
VERSION = "3.1.0"
DEFAULT_PORT = 4747
DEFAULT_HOST = "127.0.0.1"
MAX_ITERATIONS_CAP = 50
MAX_TIMEOUT_SECONDS = 300
MAX_TASK_LENGTH = 10000
MAX_TEAMS = 100
TEAM_TTL_SECONDS = 3600
SSE_QUEUE_MAXSIZE = 256
MAX_SSE_SUBSCRIBERS = 50
# CACHE_TTL_SECONDS importado desde gateway_middleware
SAFE_NAME_PATTERN = re.compile(r"^[a-zA-Z0-9][a-zA-Z0-9_-]{0,63}$")


# ============================================================
# Configuracion
# ============================================================
@dataclass
class GatewayConfig:
    """Configuracion del gateway.

    Attributes:
        port: Puerto HTTP.
        host: Dirección de bind.
        api_key: API key para autenticación.
        require_auth: Si True, requiere autenticación en endpoints privados.
        cors_origins: Lista de orígenes CORS permitidos.
        rate_limit_per_minute: Requests por minuto por IP (0 = desactivado).
        profile: Perfil de runtime activo.
    """

    port: int = DEFAULT_PORT
    host: str = DEFAULT_HOST
    api_key: str | None = None
    require_auth: bool = True
    cors_origins: list[str] = field(default_factory=lambda: DEFAULT_CORS_ORIGINS.copy())
    rate_limit_per_minute: int = 60
    profile: ProfileConfig = field(default_factory=lambda: ACTIVE_PROFILE)


def _is_local_client(client_ip: str) -> bool:
    """Retorna True si la IP corresponde a localhost."""
    return shared_is_localhost_client(client_ip)


def _is_origin_allowed(origin: str, allowed_origins: list[str]) -> bool:
    """Valida origen CORS, permitiendo match por host aunque cambie el puerto."""
    return shared_is_origin_allowed(origin, allowed_origins)


# RateLimiter y TTLCache importados desde gateway_middleware


# ============================================================
# Metricas
# ============================================================
class Metrics:
    """Recolector de metricas para el gateway."""

    def __init__(self):
        self.request_count: dict[str, int] = defaultdict(int)
        self.request_errors: dict[str, int] = defaultdict(int)
        self.request_duration_ms: dict[str, list[float]] = defaultdict(list)
        self.active_sse_connections: int = 0
        self.agents_executed: int = 0
        self.teams_created: int = 0
        # Latencia de ejecución por agente (en segundos)
        self.agent_execution_seconds: dict[str, list[float]] = defaultdict(list)

    @staticmethod
    def _normalize_path(path: str) -> str:
        """Normaliza paths dinamicos para evitar crecimiento ilimitado de metricas."""
        # /v1/agents/some-name -> /v1/agents/:name
        path = re.sub(r"/v1/agents/([^/]+)/run", "/v1/agents/:name/run", path)
        path = re.sub(r"/v1/agents/([^/]+)$", "/v1/agents/:name", path)
        path = re.sub(r"/v1/skills/([^/]+)$", "/v1/skills/:name", path)
        path = re.sub(r"/v1/teams/([^/]+)/message", "/v1/teams/:id/message", path)
        return path

    def record_request(self, method: str, path: str, status: int, duration_ms: float) -> None:
        """Registra una request completada."""
        key = f"{method} {self._normalize_path(path)}"
        self.request_count[key] += 1
        if status >= 400:
            self.request_errors[key] += 1
        durations = self.request_duration_ms[key]
        durations.append(duration_ms)
        # Mantener solo ultimas 1000 mediciones por endpoint
        if len(durations) > 1000:
            self.request_duration_ms[key] = durations[-1000:]

    def to_prometheus(self) -> str:
        """Exporta metricas en formato Prometheus."""
        lines = [
            "# HELP antigravity_gateway_requests_total Total de requests",
            "# TYPE antigravity_gateway_requests_total counter",
        ]
        for key, count in self.request_count.items():
            method, path = key.split(" ", 1)
            lines.append(
                f'antigravity_gateway_requests_total{{method="{method}",path="{path}"}} {count}'
            )

        lines.extend(
            [
                "# HELP antigravity_gateway_errors_total Total de errores",
                "# TYPE antigravity_gateway_errors_total counter",
            ]
        )
        for key, count in self.request_errors.items():
            method, path = key.split(" ", 1)
            lines.append(
                f'antigravity_gateway_errors_total{{method="{method}",path="{path}"}} {count}'
            )

        lines.extend(
            [
                "# HELP antigravity_gateway_sse_connections Conexiones SSE activas",
                "# TYPE antigravity_gateway_sse_connections gauge",
                f"antigravity_gateway_sse_connections {self.active_sse_connections}",
                "# HELP antigravity_gateway_agents_executed Agentes ejecutados",
                "# TYPE antigravity_gateway_agents_executed counter",
                f"antigravity_gateway_agents_executed {self.agents_executed}",
                "# HELP antigravity_gateway_teams_created Equipos creados",
                "# TYPE antigravity_gateway_teams_created counter",
                f"antigravity_gateway_teams_created {self.teams_created}",
            ]
        )

        # Latencia p50/p95/p99 por endpoint
        lines.extend(
            [
                "# HELP antigravity_gateway_request_duration_ms Latencia por endpoint",
                "# TYPE antigravity_gateway_request_duration_ms summary",
            ]
        )
        for key, durations in self.request_duration_ms.items():
            if not durations:
                continue
            method, path = key.split(" ", 1)
            sorted_d = sorted(durations)
            n = len(sorted_d)
            p50 = sorted_d[int(n * 0.5)] if n > 0 else 0
            p95 = sorted_d[int(n * 0.95)] if n > 1 else p50
            p99 = sorted_d[int(n * 0.99)] if n > 2 else p95
            lines.append(
                f'antigravity_gateway_request_duration_ms{{method="{method}",path="{path}",quantile="0.5"}} {p50:.1f}'
            )
            lines.append(
                f'antigravity_gateway_request_duration_ms{{method="{method}",path="{path}",quantile="0.95"}} {p95:.1f}'
            )
            lines.append(
                f'antigravity_gateway_request_duration_ms{{method="{method}",path="{path}",quantile="0.99"}} {p99:.1f}'
            )

        # Latencia de ejecucion por agente (en segundos)
        lines.extend(
            [
                "# HELP agent_execution_seconds Duracion de ejecucion de agente en segundos",
                "# TYPE agent_execution_seconds summary",
            ]
        )
        for agent_name, durations in self.agent_execution_seconds.items():
            if not durations:
                continue
            sorted_d = sorted(durations)
            n = len(sorted_d)
            p50 = sorted_d[int(n * 0.5)] if n > 0 else 0
            p95 = sorted_d[int(n * 0.95)] if n > 1 else p50
            lines.append(
                f'agent_execution_seconds{{agent_name="{agent_name}",quantile="0.5"}} {p50:.3f}'
            )
            lines.append(
                f'agent_execution_seconds{{agent_name="{agent_name}",quantile="0.95"}} {p95:.3f}'
            )
            lines.append(f'agent_execution_seconds_count{{agent_name="{agent_name}"}} {n}')
            lines.append(
                f'agent_execution_seconds_sum{{agent_name="{agent_name}"}} {sum(sorted_d):.3f}'
            )

        # Conexiones activas como gauge
        lines.extend(
            [
                "# HELP gateway_active_connections Conexiones SSE activas en este momento",
                "# TYPE gateway_active_connections gauge",
                f"gateway_active_connections {self.active_sse_connections}",
            ]
        )

        return "\n".join(lines) + "\n"


# EventManager importado desde gateway_events


# ============================================================
# Helpers
# ============================================================
def _validate_name(name: str) -> bool:
    """Valida que un nombre de agente/skill sea seguro (sin path traversal)."""
    return bool(SAFE_NAME_PATTERN.match(name))


def _sanitize_error(error: Exception) -> str:
    """Sanitiza mensaje de error para no exponer internals."""
    return sanitize_error(error)


def _make_response(data: Any = None, error: str = "", status: int = 200) -> dict:
    """Envelope consistente de respuesta."""
    return make_response(data=data, error=error, status=status)


def _normalize_plugin_stats(raw: dict) -> dict:
    """Normaliza las stats del PluginManager al formato que espera el frontend.

    El backend devuelve {total_plugins, by_state: {active, inactive, ...}, ...}.
    El frontend espera {total, active, inactive, error}.
    """
    by_state = raw.get("by_state", {})
    return {
        "total": raw.get("total_plugins", 0),
        "active": by_state.get("active", 0),
        "inactive": by_state.get("inactive", 0) + by_state.get("installed", 0),
        "error": by_state.get("error", 0),
        "discovered": by_state.get("discovered", 0),
        "total_skills": raw.get("total_skills", 0),
        "total_agents": raw.get("total_agents", 0),
    }


# _build_openapi_schema importado desde openapi_schema como _build_openapi_schema_fn
def _build_openapi_schema() -> dict:
    """Genera schema OpenAPI 3.0 del gateway (wrapper para compatibilidad)."""
    return _build_openapi_schema_fn(
        version=VERSION,
        max_task_length=MAX_TASK_LENGTH,
        max_timeout_seconds=MAX_TIMEOUT_SECONDS,
        max_iterations_cap=MAX_ITERATIONS_CAP,
    )


# ============================================================
# Response helpers (centralizados en _response.py)
# ============================================================
from .gateway._response import make_response, sanitize_error

# ============================================================
# Mixin imports
# ============================================================
from .gateway._mixin_system import _SystemMixin
from .gateway._mixin_agents import _AgentsMixin
from .gateway._mixin_skills import _SkillsMixin
from .gateway._mixin_project import _ProjectMixin
from .gateway._mixin_streaming import _StreamingMixin
from .gateway._mixin_daemon import _DaemonMixin
from .gateway._mixin_memory import _MemoryMixin
from .gateway._mixin_intelligence import _IntelligenceMixin
from .gateway._mixin_swarm import _SwarmMixin
from .gateway._mixin_observatory import _ObservatoryMixin
from .gateway._mixin_resilience import _ResilienceMixin
from .gateway._mixin_advanced import _AdvancedMixin
from .gateway._mixin_context_engine import _ContextEngineMixin
from .gateway._mixin_watcher import _WatcherMixin
from .gateway._mixin_brain import _BrainMixin
from .gateway._mixin_provider import _ProviderMixin
from .gateway._mixin_proxy import _ProxyMixin
from .broker import AntigravityMcpBroker

# Telemetría OpenTelemetry (opcional — graceful degradation)
try:
    from .gateway_telemetry import setup_telemetry, get_telemetry, telemetry_middleware  # noqa: F401

    HAS_TELEMETRY = True
except ImportError:
    HAS_TELEMETRY = False

# Event Bus mejorado (opcional)
try:
    from .gateway_events import EventBus, get_event_bus  # noqa: F401

    HAS_EVENT_BUS = True
except ImportError:
    HAS_EVENT_BUS = False

# AutoTune Engine (opcional — graceful degradation)
try:
    from core.autotune import AutoTuneEngine, TuneProfile, ContextCategory  # noqa: F401

    HAS_AUTOTUNE = True
except ImportError:
    HAS_AUTOTUNE = False
    AutoTuneEngine = None  # type: ignore[assignment,misc]

# Parallel Racer (opcional — graceful degradation)
try:
    from core.parallel_racer import ParallelRacer, RacingTier  # noqa: F401

    HAS_RACER = True
except ImportError:
    HAS_RACER = False
    ParallelRacer = None  # type: ignore[assignment,misc]

# Sliding Window Rate Limiter (opcional — fallback al RateLimiter simple)
try:
    from core.rate_limiter import SlidingWindowRateLimiter, RateTier

    HAS_SLIDING_RATE_LIMITER = True
except ImportError:
    HAS_SLIDING_RATE_LIMITER = False
    SlidingWindowRateLimiter = None  # type: ignore[assignment,misc]
    RateTier = None  # type: ignore[assignment,misc]


def _is_loopback(client_ip: str) -> bool:
    """Indica si la IP del cliente es de loopback.

    Args:
        client_ip: Direccion remota reportada por aiohttp.

    Returns:
        True si la direccion es loopback (IPv4 o IPv6).
    """
    try:
        return ipaddress.ip_address(client_ip.strip("[]")).is_loopback
    except ValueError:
        return False


# ============================================================
# Gateway HTTP Server
# ============================================================
class AntigravityGateway(
    _SystemMixin,
    _AgentsMixin,
    _SkillsMixin,
    _ProjectMixin,
    _StreamingMixin,
    _DaemonMixin,
    _MemoryMixin,
    _IntelligenceMixin,
    _SwarmMixin,
    _ObservatoryMixin,
    _ResilienceMixin,
    _AdvancedMixin,
    _WatcherMixin,
    _ContextEngineMixin,
    _BrainMixin,
    _ProviderMixin,
    _ProxyMixin,
):
    """HTTP Gateway production-ready para el ecosistema de agentes Antigravity."""

    def __init__(self, config: GatewayConfig):
        self.config = config
        self.events = EventManager()
        self.metrics = Metrics()
        self.cache = TTLCache()
        self._executor = None
        self._teams: dict[str, dict] = {}  # {id: {team, created_at}}
        self._start_time = datetime.now()
        # Thread pool escalable: evita saturacion con mem0/Ollama concurrente.
        # Antes era fijo en 8; con 20+ reqs simultaneos se acumulaban tasks fantasma.
        _pool_workers = min((os.cpu_count() or 4) * 2, 32)
        self._thread_pool = ThreadPoolExecutor(max_workers=_pool_workers, thread_name_prefix="gw")
        self._ready = False
        self._openapi = _build_openapi_schema()
        self.mcp_broker = AntigravityMcpBroker(self, BASE_DIR)
        self.mcp_broker_v2_enabled = _mcp_broker_v2_enabled()
        # Guard para loguear el warning de CORS wildcard una sola vez (evita spam).
        self._cors_wildcard_warned = False

        # --- Sliding Window Rate Limiter (reemplaza RateLimiter simple) ---
        self._sliding_rate_limiter: Any = None
        if HAS_SLIDING_RATE_LIMITER and SlidingWindowRateLimiter is not None:
            try:
                self._sliding_rate_limiter = SlidingWindowRateLimiter(
                    default_tier=RateTier.STANDARD,
                )
                log.info("SlidingWindowRateLimiter inicializado (reemplaza rate limiter simple)")
            except Exception as e:
                log.warning("Error inicializando SlidingWindowRateLimiter, usando fallback: %s", e)
                self._sliding_rate_limiter = None

        # Fallback: rate limiter simple (token bucket)
        self.rate_limiter = RateLimiter(config.rate_limit_per_minute)

        # --- AutoTune Engine (opcional) ---
        self._autotune_engine: Any = None
        if HAS_AUTOTUNE and AutoTuneEngine is not None:
            try:
                self._autotune_engine = AutoTuneEngine()
                log.info("AutoTuneEngine inicializado")
            except Exception as e:
                log.warning("Error inicializando AutoTuneEngine: %s", e)

        # --- Parallel Racer (opcional) ---
        self._parallel_racer: Any = None
        if HAS_RACER and ParallelRacer is not None:
            try:
                self._parallel_racer = ParallelRacer(
                    agents_dir=str(AGENTS_DIR),
                    timeout=30,
                )
                log.info("ParallelRacer inicializado")
            except Exception as e:
                log.warning("Error inicializando ParallelRacer: %s", e)

    @property
    def executor(self):
        """Retorna el executor si ya fue cargado, o None."""
        return self._executor

    async def get_executor(self):
        """Carga el executor en thread pool (no bloquea event loop)."""
        if self._executor is not None:
            return self._executor
        if not EXECUTOR_AVAILABLE:
            return None
        loop = asyncio.get_running_loop()
        self._executor = await loop.run_in_executor(self._thread_pool, AgentExecutor)
        return self._executor

    # --------------------------------------------------------
    # Middlewares
    # --------------------------------------------------------
    @web.middleware
    async def middleware_request_id(self, request: web.Request, handler) -> web.Response:
        """Agrega request ID unico a cada peticion."""
        request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
        request["request_id"] = request_id
        request["start_time"] = time.monotonic()

        response = await handler(request)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Gateway-Version"] = VERSION

        # Loguear request completada
        duration_ms = (time.monotonic() - request["start_time"]) * 1000
        path = request.path.replace("/v1", "") or "/"
        self.metrics.record_request(request.method, path, response.status, duration_ms)

        log.info(
            "[%s] %s %s -> %d (%.0fms)",
            request_id,
            request.method,
            request.path,
            response.status,
            duration_ms,
        )
        return response

    # Endpoints sensibles que requieren audit logging (metodo POST solamente)
    _AUDIT_POST_PREFIXES: tuple[str, ...] = (
        "/v1/agents/",  # cubre /v1/agents/{name}/run
        "/v1/skills/",  # cubre /v1/skills/{name}/execute
        "/v1/mcp",  # cubre /v1/mcp y /v1/mcp/message
        "/v1/autonomous",
        "/v1/planner/",
        "/v1/swarm/",
        "/v1/workflows/",
        "/v1/teams",
        "/v1/daemon/submit",
        "/v1/mem0/",
        "/v1/memory/",
        "/v1/improvement/",
        "/v1/reactive/emit",
        "/v1/negotiation/",
        "/v1/a2a/request",
        "/v1/project/write",
    )

    @web.middleware
    async def middleware_audit_log(self, request: web.Request, handler: Any) -> web.Response:
        """Audit logging no-bloqueante para endpoints sensibles.

        Registra timestamp, client_ip, method, path, status_code y duration_ms
        en logs/audit.log via RotatingFileHandler. Solo actua en POST a rutas
        sensibles; health checks y GETs simples son ignorados.
        """
        # Filtrar: solo POST a rutas sensibles
        path = request.path
        is_sensitive = request.method == "POST" and any(
            path.startswith(prefix) for prefix in self._AUDIT_POST_PREFIXES
        )

        if not is_sensitive:
            return await handler(request)

        start = time.monotonic()
        response = await handler(request)
        duration_ms = (time.monotonic() - start) * 1000

        # IP del cliente. Cierra el MEDIO [M3] del reporte 2026-04-11:
        # antes, el gateway respetaba el header `X-Forwarded-For` sin tener
        # un proxy de confianza, lo que permitia spoofear la IP en los
        # audit logs (`X-Forwarded-For: 127.0.0.1` desde un cliente remoto).
        # Como el gateway por defecto bindea solo a localhost y no hay
        # cadena de proxies, ignoramos el header y usamos `request.remote`
        # directamente. Si en el futuro se introduce un reverse proxy real,
        # debe configurarse una allowlist explicita de proxies confiables.
        client_ip = request.remote or "unknown"

        _audit_log.info(
            "%s %s %d %.0fms client=%s",
            request.method,
            path,
            response.status,
            duration_ms,
            client_ip,
        )
        return response

    @web.middleware
    async def middleware_cors(self, request: web.Request, handler) -> web.Response:
        """CORS middleware."""
        # Preflight
        if request.method == "OPTIONS":
            response = web.Response(status=204)
        else:
            response = await handler(request)

        origin = request.headers.get("Origin", "")
        # Origenes CORS configurables via env var ANTIGRAVITY_CORS_ORIGINS
        # (parseada en main() hacia config.cors_origins). Sin env var explicita,
        # el default es localhost-only; el wildcard "*" solo aplica si se setea
        # explicitamente, y en ese caso logueamos un warning una unica vez.
        allowed = self.config.cors_origins

        if "*" in allowed:
            if not self._cors_wildcard_warned:
                log.warning(
                    "CORS configurado con wildcard '*' (Access-Control-Allow-Origin: *). "
                    "Setea ANTIGRAVITY_CORS_ORIGINS con una lista explicita de origenes "
                    "para entornos no locales."
                )
                self._cors_wildcard_warned = True
            response.headers["Access-Control-Allow-Origin"] = "*"
        elif _is_origin_allowed(origin, allowed):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Vary"] = "Origin"

        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = (
            "Content-Type, X-API-Key, X-Request-ID, MCP-Protocol-Version, "
            "MCP-Session-Id, Last-Event-ID"
        )
        response.headers["Access-Control-Expose-Headers"] = (
            "MCP-Protocol-Version, MCP-Session-Id, X-Request-ID"
        )
        response.headers["Access-Control-Max-Age"] = "86400"

        # Forzar cierre de conexión TCP para evitar acumulación de CLOSE_WAIT.
        # Los clientes (Nexus WebView, reqwest) hacen polling corto — no necesitan keep-alive.
        if request.path not in {"/mcp", "/v1/mcp"} and (
            not isinstance(response, web.StreamResponse) or not response.prepared
        ):
            response.headers["Connection"] = "close"

        return response

    @web.middleware
    async def middleware_auth(self, request: web.Request, handler) -> web.Response:
        """Autenticacion via API key."""
        # Endpoints publicos (sin auth)
        public_paths = {"/health", "/v1/health", "/v1/ready", "/v1/"}
        # /claudeproxy NO lleva API key del gateway: Claude Code manda el auth del
        # provider en sus propios headers. El gateway bindea a 127.0.0.1 (local-only).
        is_proxy = request.path.startswith("/claudeproxy/")
        if request.path in public_paths or is_proxy or not self.config.require_auth:
            return await handler(request)

        # OPTIONS siempre pasa (CORS preflight)
        if request.method == "OPTIONS":
            return await handler(request)

        expected = self.config.api_key or ""
        if not expected:
            # NOTA DE SEGURIDAD (2026-04-11): el bypass por loopback fue
            # eliminado. Antes, cuando ANTIGRAVITY_API_KEY estaba vacia,
            # cualquier cliente con IP 127.0.0.1/::1 (incluyendo el browser
            # del usuario) pasaba auth sin credenciales. Combinado con CORS
            # `*` en dev, esto permitia drive-by CORS desde cualquier sitio
            # web abierto. Ahora el gateway SIEMPRE requiere session key:
            # si no se setea explicitamente, `main()` invoca
            # `ensure_session_key()` para generar una y persistirla en
            # `~/.antigravity/session.key` con permisos 0600. Si llegamos
            # aqui con `expected` vacio, es un bug de inicializacion.
            return web.json_response(
                _make_response(
                    error="Gateway sin API key configurada (bug de inicializacion)",
                    status=503,
                ),
                status=503,
            )

        api_key = request.headers.get("X-API-Key", "")
        if not api_key:
            return web.json_response(
                _make_response(error="API key requerida (header X-API-Key)", status=401),
                status=401,
            )

        # Comparar hash con hmac.compare_digest para evitar timing attacks.
        if not hmac.compare_digest(
            hashlib.sha256(api_key.encode()).digest(),
            hashlib.sha256(expected.encode()).digest(),
        ):
            return web.json_response(
                _make_response(error="API key invalida", status=403),
                status=403,
            )

        return await handler(request)

    @web.middleware
    async def middleware_rate_limit(self, request: web.Request, handler) -> web.Response:
        """Rate limiting por IP.  Desactivado cuando profile.rate_limit == 0."""
        # Health, ready y endpoints de monitoreo exentos del rate limit
        # (son health checks internos, no operaciones de datos)
        if (
            request.path
            in {
                "/v1/health",
                "/v1/ready",
                "/v1/metrics",
                "/v1/mem0/stats",
                # Long-lived internal SSE stream. Counting it as an active request
                # exhausts the per-IP concurrent limit and traps clients in 429.
                "/v1/watcher/stream",
            }
            or request.path.startswith("/claudeproxy/")
            or (request.method == "GET" and request.path in {"/mcp", "/v1/mcp"})
        ):
            return await handler(request)

        # Rate limit desactivado por perfil (minimal)
        if self.config.rate_limit_per_minute <= 0:
            return await handler(request)

        client_ip = request.remote or "unknown"

        # Usar SlidingWindowRateLimiter si está disponible
        if self._sliding_rate_limiter is not None:
            # Loopback = todos los clientes locales (Nexus, Claude Code/MCP, CLI,
            # bot) colapsan en un unico client_id. El tope diario de STANDARD los
            # hace competir por el mismo balde y el mas charlatan tumba a los
            # demas. LOCAL conserva el limite por minuto pero sin tope diario.
            client_tier = RateTier.LOCAL if _is_loopback(client_ip) else None
            result = self._sliding_rate_limiter.check(client_ip, tier=client_tier)
            if not result.allowed:
                response = web.json_response(
                    _make_response(
                        error=f"Rate limit excedido: {result.reason}",
                        status=429,
                    ),
                    status=429,
                )
                for header_name, header_value in result.headers.items():
                    response.headers[header_name] = header_value
                return response
            try:
                response = await handler(request)
            except Exception:
                self._sliding_rate_limiter.release(client_ip)
                raise
            # Inyectar rate limit headers en la respuesta
            for header_name, header_value in result.headers.items():
                response.headers[header_name] = header_value
            self._sliding_rate_limiter.release(client_ip)
            return response

        # Fallback: rate limiter simple (token bucket)
        if not self.rate_limiter.is_allowed(client_ip):
            return web.json_response(
                _make_response(error="Rate limit excedido. Intenta en unos segundos.", status=429),
                status=429,
                headers={"Retry-After": "10"},
            )

        return await handler(request)

    @web.middleware
    async def middleware_timeout(self, request: web.Request, handler) -> web.Response:
        """Timeout global: ningun handler puede bloquear mas de 60s.

        Es mayor que el timeout individual de mem0 (15s) para que handlers
        mem0 saturados devuelvan 504 a nivel handler (con cleanup correcto)
        en vez de quedar colgados aca y dejar tasks huerfanas en el pool.
        """
        # El proxy de hot-swap hace streaming LLM largo (puede superar 60s con
        # respuestas extensas + thinking); no debe quedar sujeto al wait_for global.
        if (
            request.path.startswith("/claudeproxy/")
            or request.path == "/v1/watcher/stream"
            or request.path in {"/mcp", "/v1/mcp"}
        ):
            return await handler(request)
        try:
            return await asyncio.wait_for(handler(request), timeout=60.0)
        except TimeoutError:
            log.error(
                "TIMEOUT 60s en %s %s — handler bloqueado, forzando 504",
                request.method,
                request.path,
            )
            return web.json_response(
                _make_response(error="Handler timeout (60s)", status=504),
                status=504,
            )

    @web.middleware
    async def middleware_error_handler(self, request: web.Request, handler) -> web.Response:
        """Captura errores no manejados y los sanitiza."""
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except Exception:
            request_id = request.get("request_id", "unknown")
            log.exception(
                "[%s] Error no manejado en %s %s", request_id, request.method, request.path
            )
            return web.json_response(
                _make_response(error="Error interno del servidor", status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Lifecycle
    # --------------------------------------------------------
    async def on_startup(self, app: web.Application) -> None:
        """Inicializacion al arrancar."""
        await self.mcp_broker.start()
        self._ready = True
        self._cleanup_task = asyncio.create_task(self._periodic_cleanup())
        if os.environ.get("ANTIGRAVITY_PORTABLE_RUNTIME", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            log.info(
                "Portable runtime activo: memoria global, autonomia y pollers "
                "permanecen lazy"
            )
            return
        self._mem0_prewarm_task = asyncio.create_task(self.prewarm_mem0_background())
        # Activación eager de la autonomía (daemon + subsistemas) en background.
        # Best-effort y non-blocking: el daemon corre como subproceso (DaemonProxy),
        # así que spawnearlo no bloquea el event loop del gateway. Reversible con
        # ANTIGRAVITY_AUTONOMY_EAGER=0 (vuelve al modo lazy on-demand).
        self._autonomy_task = asyncio.create_task(self._activate_autonomy_background())
        # Polling de cuota por provider (señal del auto-rotate proactivo). El loop
        # se auto-gatea por opt-in (ANTIGRAVITY_PROXY_QUOTA_POLL o auto-failover ON):
        # con la feature OFF solo duerme, cero llamadas de red. Best-effort.
        try:
            from core import usage_poller

            self._quota_poll_task = asyncio.create_task(usage_poller.start_poll_loop())
        except Exception as exc:  # noqa: BLE001 — non-blocking, no debe abortar el arranque
            log.debug("quota poll loop no se pudo arrancar: %s", exc)
        # Watcher history cleanup (cada 6h) — idempotente si ya arranco
        try:
            from .gateway._mixin_watcher import start_periodic_cleanup

            start_periodic_cleanup()
        except Exception as exc:  # noqa: BLE001
            log.debug("watcher periodic cleanup no se pudo arrancar: %s", exc)
        # Executor NO se carga al arranque ni en background.
        # Razón: AgentExecutor() importa chromadb/pydantic que bloquean el GIL
        # por ~3-5 segundos, congelando el event loop de aiohttp incluso
        # dentro de run_in_executor (Python GIL contention).
        # Se carga on-demand via subprocess cuando se ejecuta un agente.
        log.info("Gateway listo para recibir trafico")

    async def _activate_autonomy_background(self) -> None:
        """Spawnea el daemon de autonomía al arranque (eager), en background.

        El daemon corre como subproceso (DaemonProxy), así que spawnearlo NO bloquea
        el event loop del gateway (a diferencia del executor, que sí se difiere por
        GIL). Best-effort: cualquier fallo se loguea sin afectar el arranque.
        Reversible con ``ANTIGRAVITY_AUTONOMY_EAGER=0`` (vuelve al modo lazy on-demand,
        donde el daemon se spawnea recién cuando un endpoint lo necesita).
        """
        if os.environ.get("ANTIGRAVITY_AUTONOMY_EAGER", "1").lower() in {
            "0",
            "false",
            "no",
            "off",
        }:
            log.debug("Autonomia eager deshabilitada (ANTIGRAVITY_AUTONOMY_EAGER=0); modo lazy")
            return
        try:
            from .gateway._mixin_advanced import _get_daemon_safe

            # _get_daemon_safe es non-blocking: lanza el spawn y devuelve None mientras
            # se crea. Poll hasta que el proxy este listo (timeout ~30s).
            for _ in range(30):
                daemon = await _get_daemon_safe()
                if daemon is not None:
                    log.info("Autonomia activada: daemon spawneado al arranque del gateway")
                    return
                await asyncio.sleep(1.0)
            log.warning("Autonomia eager: el daemon no termino de spawnear en 30s (sigue lazy)")
        except Exception as e:  # noqa: BLE001
            log.warning("No se pudo activar la autonomia eager al boot: %s", e)

    async def _init_executor_background(self) -> None:
        """Carga el executor en background para no bloquear requests."""
        try:
            # Ejecutar en thread pool para no bloquear el event loop
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(self._thread_pool, self._load_executor_sync)
            log.info("Executor cargado en background — gateway completamente operativo")
        except Exception as e:
            log.warning("Error cargando executor en background: %s", e)

    def _load_executor_sync(self) -> None:
        """Carga síncrona del executor (se ejecuta en thread pool)."""
        _ = self.executor  # Trigger lazy-load

    async def on_shutdown(self, app: web.Application) -> None:
        """Graceful shutdown."""
        log.info("Iniciando shutdown graceful...")
        self._ready = False
        await self.mcp_broker.stop()

        # Shutdown daemon worker subprocess
        try:
            from .daemon_proxy import DaemonProxy

            DaemonProxy.shutdown()
            log.info("Daemon worker detenido")
        except Exception:
            pass

        # Cancelar tarea de limpieza
        if hasattr(self, "_cleanup_task"):
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass

        if hasattr(self, "_mem0_prewarm_task"):
            self._mem0_prewarm_task.cancel()
            try:
                await self._mem0_prewarm_task
            except asyncio.CancelledError:
                pass

        # Watcher cleanup task
        try:
            from .gateway._mixin_watcher import stop_periodic_cleanup

            stop_periodic_cleanup()
        except Exception:  # noqa: BLE001
            pass

        # Notificar a suscriptores SSE
        await self.events.emit("shutdown", {"message": "Gateway cerrando"})

        # Esperar a que las conexiones SSE se cierren
        await asyncio.sleep(1)

        # Cerrar thread pool
        self._thread_pool.shutdown(wait=False)
        log.info("Shutdown completado")

    async def _periodic_cleanup(self) -> None:
        """Tarea periodica de limpieza (cada 5 min)."""
        while True:
            try:
                await asyncio.sleep(300)
                self._cleanup_teams()
                self.rate_limiter.cleanup()
                if self._sliding_rate_limiter is not None:
                    self._sliding_rate_limiter.cleanup()
                self.cache.invalidate()  # Forzar recarga periodica
                log.info("Limpieza periodica completada")
            except asyncio.CancelledError:
                break
            except Exception as e:
                log.warning("Error en limpieza periodica: %s", e)

    # --------------------------------------------------------
    # AutoTune Handlers
    # --------------------------------------------------------
    async def handle_autotune_analyze(self, request: web.Request) -> web.Response:
        """POST /v1/autotune/analyze — Analizar mensajes y obtener parametros optimizados."""
        if self._autotune_engine is None:
            return web.json_response(
                _make_response(error="AutoTune no disponible", status=503),
                status=503,
            )
        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="JSON invalido en el body", status=400),
                status=400,
            )

        messages = body.get("messages")
        if not messages or not isinstance(messages, list):
            return web.json_response(
                _make_response(error="Campo 'messages' requerido (lista de mensajes)", status=400),
                status=400,
            )

        model = body.get("model", "")
        try:
            profile = self._autotune_engine.tune(messages, model=model)
            log.info(
                "AutoTune analyze: category=%s confidence=%.2f",
                profile.category.value,
                profile.confidence,
            )
            return web.json_response(
                _make_response(
                    data={
                        "category": profile.category.value,
                        "parameters": {
                            "temperature": profile.temperature,
                            "top_p": profile.top_p,
                            "top_k": profile.top_k,
                            "max_tokens": profile.max_tokens,
                        },
                        "confidence": profile.confidence,
                        "reasoning": profile.reasoning,
                        "detected_patterns": profile.detected_patterns,
                    }
                )
            )
        except Exception as exc:
            log.exception("Error en AutoTune analyze")
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500),
                status=500,
            )

    async def handle_autotune_feedback(self, request: web.Request) -> web.Response:
        """POST /v1/autotune/feedback — Enviar feedback para mejorar el tuning."""
        if self._autotune_engine is None:
            return web.json_response(
                _make_response(error="AutoTune no disponible", status=503),
                status=503,
            )
        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="JSON invalido en el body", status=400),
                status=400,
            )

        category_str = body.get("category")
        rating = body.get("rating")
        parameters = body.get("parameters", {})

        if not category_str or rating is None:
            return web.json_response(
                _make_response(error="Campos 'category' y 'rating' requeridos", status=400),
                status=400,
            )

        try:
            rating_val = float(rating)
            if not 0.0 <= rating_val <= 1.0:
                return web.json_response(
                    _make_response(error="'rating' debe estar entre 0.0 y 1.0", status=400),
                    status=400,
                )
        except (TypeError, ValueError):
            return web.json_response(
                _make_response(error="'rating' debe ser un numero entre 0.0 y 1.0", status=400),
                status=400,
            )

        try:
            from core.autotune import ContextCategory as CC, TuneProfile as TP

            cat = CC(category_str)
            # Construir un TuneProfile minimo para apply_feedback
            profile = TP(
                category=cat,
                temperature=parameters.get("temperature", 0.5),
                top_p=parameters.get("top_p", 0.9),
                top_k=parameters.get("top_k", 40),
                max_tokens=parameters.get("max_tokens", 4096),
                confidence=0.0,
                reasoning="",
                detected_patterns=[],
            )
            self._autotune_engine.apply_feedback(profile, rating_val)
            log.info("AutoTune feedback: category=%s rating=%.2f", category_str, rating_val)
            return web.json_response(
                _make_response(data={"status": "ok", "message": "Feedback applied"})
            )
        except ValueError as exc:
            return web.json_response(
                _make_response(error=str(exc), status=400),
                status=400,
            )
        except Exception as exc:
            log.exception("Error en AutoTune feedback")
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Parallel Racer Handlers
    # --------------------------------------------------------
    async def handle_race_run(self, request: web.Request) -> web.Response:
        """POST /v1/race/run — Ejecutar una carrera paralela de agentes."""
        if self._parallel_racer is None:
            return web.json_response(
                _make_response(error="ParallelRacer no disponible", status=503),
                status=503,
            )
        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="JSON invalido en el body", status=400),
                status=400,
            )

        task = body.get("task")
        if not task or not isinstance(task, str):
            return web.json_response(
                _make_response(error="Campo 'task' requerido (string)", status=400),
                status=400,
            )

        if len(task) > MAX_TASK_LENGTH:
            return web.json_response(
                _make_response(
                    error=f"Task demasiado largo (max {MAX_TASK_LENGTH} chars)", status=400
                ),
                status=400,
            )

        tier_str = body.get("tier", "standard")
        agents_list = body.get("agents")

        try:
            from core.parallel_racer import RacingTier as RT

            tier = RT(tier_str)
        except (ValueError, ImportError):
            return web.json_response(
                _make_response(
                    error=f"Tier invalido: '{tier_str}'. Opciones: fast, standard, thorough, ultra",
                    status=400,
                ),
                status=400,
            )

        try:
            log.info("Race run: task=%.80s tier=%s agents=%s", task, tier_str, agents_list)
            result = await self._parallel_racer.race(
                task=task,
                tier=tier,
                agents=agents_list,
            )
            return web.json_response(_make_response(data=result.to_dict()))
        except ValueError as exc:
            return web.json_response(
                _make_response(error=str(exc), status=400),
                status=400,
            )
        except Exception as exc:
            log.exception("Error en race run")
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500),
                status=500,
            )

    async def handle_race_rankings(self, request: web.Request) -> web.Response:
        """GET /v1/race/rankings — Obtener rankings acumulados de agentes."""
        if self._parallel_racer is None:
            return web.json_response(
                _make_response(error="ParallelRacer no disponible", status=503),
                status=503,
            )
        try:
            rankings = self._parallel_racer.get_agent_rankings()
            total_races = len(self._parallel_racer.race_history)
            log.info("Race rankings: %d agents, %d races total", len(rankings), total_races)
            return web.json_response(
                _make_response(
                    data={
                        "rankings": rankings,
                        "total_races": total_races,
                    }
                )
            )
        except Exception as exc:
            log.exception("Error en race rankings")
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Rate Limit Stats Handler
    # --------------------------------------------------------
    async def handle_rate_limit_stats(self, request: web.Request) -> web.Response:
        """GET /v1/rate-limit/stats — Estadisticas del rate limiter."""
        if self._sliding_rate_limiter is None:
            return web.json_response(
                _make_response(
                    data={
                        "engine": "simple_token_bucket",
                        "message": "SlidingWindowRateLimiter no disponible, usando rate limiter simple",
                    }
                )
            )
        try:
            stats = self._sliding_rate_limiter.get_stats()
            log.info(
                "Rate limit stats: %d clients, %d requests",
                stats.get("tracked_clients", 0),
                stats.get("total_requests", 0),
            )
            return web.json_response(_make_response(data=stats))
        except Exception as exc:
            log.exception("Error en rate limit stats")
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Unified Knowledge Bridge handlers
    # --------------------------------------------------------

    async def handle_knowledge_search(self, request: web.Request) -> web.Response:
        """POST /v1/knowledge/search — Búsqueda unificada across mem0 + Obsidian + ProjectMemory."""
        try:
            body = await request.json()
            query = body.get("query", "")
            if not query:
                return web.json_response({"error": "query is required"}, status=400)
            sources = body.get("sources")  # optional list
            limit = body.get("limit", 20)

            from core.unified_knowledge_bridge import (
                KnowledgeSource,
                get_knowledge_bridge,
            )

            bridge = get_knowledge_bridge(
                project_root=str(BASE_DIR),
                gateway_url=f"http://127.0.0.1:{self.config.port}",
            )
            source_enums = None
            if sources:
                source_enums = []
                for s in sources:
                    try:
                        source_enums.append(KnowledgeSource(s))
                    except ValueError:
                        pass  # skip unknown sources

            results = await bridge.search(query, sources=source_enums or None, limit=limit)
            return web.json_response(
                {
                    "query": query,
                    "results": [r.to_dict() for r in results],
                    "count": len(results),
                }
            )
        except Exception as exc:
            log.exception("knowledge/search failed")
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_knowledge_context(self, request: web.Request) -> web.Response:
        """GET /v1/knowledge/context — Todo el contexto conocido del proyecto."""
        try:
            from core.unified_knowledge_bridge import get_knowledge_bridge

            bridge = get_knowledge_bridge(
                project_root=str(BASE_DIR),
                gateway_url=f"http://127.0.0.1:{self.config.port}",
            )
            pk = await bridge.get_project_context()
            return web.json_response(pk.to_dict())
        except Exception as exc:
            log.exception("knowledge/context failed")
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_knowledge_sync(self, request: web.Request) -> web.Response:
        """POST /v1/knowledge/sync — Sincronización bidireccional."""
        try:
            body = await request.json() if request.can_read_body else {}
            direction = body.get("direction", "full")  # full, to_obsidian, from_obsidian

            from core.unified_knowledge_bridge import get_knowledge_bridge

            bridge = get_knowledge_bridge(
                project_root=str(BASE_DIR),
                gateway_url=f"http://127.0.0.1:{self.config.port}",
            )

            if direction == "to_obsidian":
                result = await bridge.sync_to_obsidian()
            elif direction == "from_obsidian":
                result = await bridge.sync_from_obsidian()
            else:
                result = await bridge.full_sync()

            return web.json_response(result.to_dict())
        except Exception as exc:
            log.exception("knowledge/sync failed")
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_knowledge_brief(self, request: web.Request) -> web.Response:
        """GET /v1/knowledge/brief — Knowledge brief markdown del proyecto."""
        try:
            max_chars = int(request.query.get("max_chars", "8000"))

            from core.unified_knowledge_bridge import get_knowledge_bridge

            bridge = get_knowledge_bridge(
                project_root=str(BASE_DIR),
                gateway_url=f"http://127.0.0.1:{self.config.port}",
            )
            brief = await bridge.generate_knowledge_brief(max_chars=max_chars)
            return web.Response(text=brief, content_type="text/markdown")
        except Exception as exc:
            log.exception("knowledge/brief failed")
            return web.json_response({"error": str(exc)}, status=500)

    # ── Universal Search ──────────────────────────────────────────────────────

    async def handle_universal_search(self, request: web.Request) -> web.Response:
        """POST /v1/search/universal — Búsqueda multi-fuente: memories, brain, código, agentes."""
        try:
            body = await request.json()
            query = body.get("query", "")
            if not query or len(query) < 2:
                return web.json_response(
                    {"error": "query debe tener al menos 2 caracteres"}, status=400
                )

            sources = body.get("sources")
            limit_per_source = body.get("limit_per_source", 5)

            from core.universal_search import UniversalSearch

            engine = UniversalSearch(BASE_DIR)
            results = engine.search(query, sources=sources, limit_per_source=limit_per_source)

            return web.json_response(
                {
                    "query": query,
                    "total": len(results),
                    "sources_used": sources or engine.DEFAULT_SOURCES,
                    "results": [
                        {
                            "title": r.title,
                            "preview": r.preview,
                            "source": r.source,
                            "source_label": r.source_label,
                            "score": r.score,
                            "path": r.path,
                            "tags": r.tags,
                            "metadata": r.metadata,
                        }
                        for r in results
                    ],
                }
            )
        except Exception as exc:
            log.exception("search/universal failed")
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_session_report(self, request: web.Request) -> web.Response:
        """POST /v1/hooks/session-report — Recibe reportes de sesión de proyectos inyectados.

        Claude Code hooks envían datos de sesión aquí para memoria centralizada.
        """
        try:
            body = await request.json()
            project = body.get("project", "unknown")
            summary = body.get("summary", "")
            files_changed = body.get("files_changed", [])
            decisions = body.get("decisions", [])
            errors = body.get("errors", [])

            if not summary:
                return web.json_response({"error": "summary is required"}, status=400)
            idempotency_key = request.headers.get("X-Idempotency-Key", "").strip()
            if idempotency_key and (
                not 8 <= len(idempotency_key) <= 128
                or not all(
                    character.isalnum() or character in "-_" for character in idempotency_key
                )
            ):
                return web.json_response({"error": "invalid idempotency key"}, status=400)
            if idempotency_key and not self.mcp_broker.state.claim_idempotency_key(
                idempotency_key,
                "session-report",
            ):
                return web.json_response(
                    {
                        "stored": False,
                        "project": project,
                        "duplicate": True,
                        "idempotency_key": idempotency_key,
                    }
                )

            # Store in mem0 for semantic search
            from core.unified_knowledge_bridge import (
                KnowledgeCategory,
                get_knowledge_bridge,
            )

            bridge = get_knowledge_bridge(
                project_root=str(BASE_DIR),
                gateway_url=f"http://127.0.0.1:{self.config.port}",
            )

            result = await bridge.store(
                content=f"[Sesión {project}] {summary}",
                category=KnowledgeCategory.SESSION,
                metadata={
                    "project": project,
                    "files_changed": files_changed,
                    "decisions": decisions,
                    "errors": errors,
                    "source": "session-hook",
                },
                targets=None,  # auto-route
            )

            log.info("[session-report] %s: %s", project, summary[:80])
            return web.json_response(
                {
                    "stored": result,
                    "project": project,
                    "duplicate": False,
                    "idempotency_key": idempotency_key or None,
                }
            )
        except Exception as exc:
            if "idempotency_key" in locals() and idempotency_key:
                self.mcp_broker.state.release_idempotency_key(idempotency_key)
            log.exception("session-report failed")
            return web.json_response({"error": str(exc)}, status=500)

    async def handle_mcp_approvals(self, request: web.Request) -> web.Response:
        """List pending or resolved broker approvals for Nexus."""

        status = request.query.get("status", "pending")
        if status not in {"pending", "approved", "denied", "consumed", "all"}:
            return web.json_response({"error": "invalid approval status"}, status=400)
        return web.json_response(
            {
                "data": {
                    "approvals": self.mcp_broker.list_approvals(status),
                }
            }
        )

    async def handle_mcp_approval_resolve(self, request: web.Request) -> web.Response:
        """Approve or deny exactly one pending broker operation."""

        approval_id = request.match_info["approval_id"]
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "JSON body is required"}, status=400)
        if not isinstance(body.get("approved"), bool):
            return web.json_response({"error": "'approved' must be boolean"}, status=400)
        result = self.mcp_broker.resolve_approval(approval_id, body["approved"])
        if result is None:
            return web.json_response({"error": "approval not found"}, status=404)
        return web.json_response({"data": result})

    async def handle_mcp_traces(self, request: web.Request) -> web.Response:
        """Return redacted MCP traces for the Nexus activity view."""

        try:
            limit = int(request.query.get("limit", "100"))
        except ValueError:
            return web.json_response({"error": "limit must be an integer"}, status=400)
        return web.json_response({"data": {"traces": self.mcp_broker.list_traces(limit)}})

    async def handle_mcp_catalog(self, request: web.Request) -> web.Response:
        """Return connector metadata without secret values."""

        return web.json_response(
            {
                "data": {
                    "schema_version": self.mcp_broker.registry.schema_version,
                    "feature_flags": {
                        "mcpBrokerV2": self.mcp_broker_v2_enabled,
                    },
                    "connectors": self.mcp_broker.registry.safe_catalog(),
                }
            }
        )

    async def handle_mcp_tool_call(self, request: web.Request) -> web.Response:
        """Execute one broker meta-tool from an authenticated first-party client."""

        if not self.mcp_broker_v2_enabled:
            return web.json_response(
                {"error": "MCP_BROKER_V2_DISABLED", "retryable": False},
                status=503,
            )
        try:
            body = await request.json()
        except Exception:
            return web.json_response({"error": "JSON body is required"}, status=400)
        if not isinstance(body, dict):
            return web.json_response({"error": "JSON body must be an object"}, status=400)
        name = body.get("name")
        arguments = body.get("arguments", {})
        if not isinstance(name, str) or not _validate_name(name):
            return web.json_response({"error": "Invalid MCP tool name"}, status=400)
        if not isinstance(arguments, dict):
            return web.json_response({"error": "'arguments' must be an object"}, status=400)
        try:
            result = await self.mcp_broker.call_tool_from_host(name, arguments)
        except ValueError:
            return web.json_response({"error": "Unknown MCP meta-tool"}, status=404)
        return web.json_response({"data": result})

    async def handle_mcp_transport(self, request: web.Request) -> web.StreamResponse:
        """Serve v2 or expose a deterministic rollback signal."""

        if not self.mcp_broker_v2_enabled:
            return web.json_response(
                {
                    "error": "MCP_BROKER_V2_DISABLED",
                    "retryable": False,
                    "legacy_sse": "/v1/mcp/sse",
                    "rollback": "antigravity-installer rollback",
                },
                status=503,
            )
        return await self.mcp_broker.handle_http(request)

    # --------------------------------------------------------
    # App Builder
    # --------------------------------------------------------
    def build_app(self) -> web.Application:
        """Construye la aplicacion aiohttp con middlewares y rutas."""
        middlewares = [
            self.middleware_timeout,  # Timeout global 30s — ningún handler bloquea
            self.middleware_error_handler,
            self.middleware_cors,
            self.middleware_rate_limit,
            self.middleware_auth,
            self.middleware_request_id,
            self.middleware_audit_log,  # Audit logging — solo endpoints sensibles POST
        ]

        # Inyectar telemetría OpenTelemetry si está disponible
        if HAS_TELEMETRY:
            middlewares.insert(0, telemetry_middleware)
            log.info("OpenTelemetry middleware activado")

        app = web.Application(
            middlewares=middlewares,
            # 1MB max body para el REST (hardening). Las rutas /claudeproxy/*
            # amplian su tope por-request via request.clone() al limite real de
            # la API Anthropic (32MB) — ver _proxy_max_body_bytes en _mixin_proxy.
            client_max_size=1024 * 1024,
        )

        # Configurar telemetría
        if HAS_TELEMETRY:
            setup_telemetry(app, service_name="antigravity-gateway")

        # Configurar event bus
        if HAS_EVENT_BUS:
            app["event_bus"] = get_event_bus()
            log.info("Event bus configurado")

        # Lifecycle hooks
        app.on_startup.append(self.on_startup)
        app.on_shutdown.append(self.on_shutdown)

        # Rutas v1
        app.router.add_get("/v1/", self.handle_root)
        app.router.add_get("/v1/health", self.handle_health)
        app.router.add_get("/v1/health/details", self.handle_health_details)
        app.router.add_get("/v1/ready", self.handle_ready)
        app.router.add_get("/v1/metrics", self.handle_metrics)
        app.router.add_get("/v1/openapi.json", self.handle_openapi)
        # Provider switch (conmutar backend IA de Claude Code) — protegido por X-API-Key
        app.router.add_get("/v1/provider/status", self.handle_provider_status)
        app.router.add_post("/v1/provider/switch", self.handle_provider_switch)
        app.router.add_post("/v1/provider/disable", self.handle_provider_disable)
        app.router.add_post("/v1/provider/hotswap", self.handle_provider_hotswap)
        app.router.add_post("/v1/provider/refresh-models", self.handle_provider_refresh_models)
        app.router.add_post("/v1/provider/reset", self.handle_provider_reset)
        # Canonical routing v2. Provider endpoints above remain temporary aliases.
        app.router.add_get("/v1/routing/status", self.handle_routing_status)
        app.router.add_get("/v1/routing/profiles", self.handle_routing_profiles)
        app.router.add_post("/v1/routing/profiles", self.handle_routing_profiles)
        app.router.add_get(
            "/v1/routing/active-profile",
            self.handle_routing_active_profile,
        )
        app.router.add_put(
            "/v1/routing/active-profile",
            self.handle_routing_active_profile,
        )
        app.router.add_post("/v1/routing/probe", self.handle_routing_probe)
        app.router.add_get("/v1/routing/events", self.handle_routing_events)
        app.router.add_get(
            "/v1/routing/models/{provider}",
            self.handle_routing_models,
        )
        app.router.add_post("/v1/proxy/circuit/reset", self.handle_provider_circuit_reset)
        app.router.add_get("/v1/proxy/quota", self.handle_proxy_quota)
        # Proxy de hot-swap: Claude Code apunta aca de forma fija (ANTHROPIC_BASE_URL)
        app.router.add_post("/claudeproxy/v1/messages", self.handle_claude_proxy)
        app.router.add_post(
            "/claudeproxy/v1/messages/count_tokens",
            self.handle_claude_proxy_count_tokens,
        )
        app.router.add_get("/v1/agents", self.handle_list_agents)
        app.router.add_get("/v1/agents/{name}", self.handle_agent_info)
        app.router.add_post("/v1/agents/{name}/run", self.handle_execute_agent)
        app.router.add_post("/v1/agents/find", self.handle_find_agent)
        app.router.add_post("/v1/agents/reload", self.handle_reload_agents)
        app.router.add_post("/v1/autonomous", self.handle_autonomous)
        app.router.add_post("/v1/teams", self.handle_create_team)
        app.router.add_post("/v1/teams/{id}/message", self.handle_team_message)
        app.router.add_get("/v1/skills", self.handle_list_skills)
        app.router.add_get("/v1/skills/{name}", self.handle_read_skill)
        app.router.add_post("/v1/skills/{name}/execute", self.handle_execute_skill)
        app.router.add_get("/v1/tools/manifest", self.handle_tools_manifest)
        app.router.add_get("/v1/project/tree", self.handle_project_tree)
        app.router.add_get("/v1/project/read", self.handle_project_read)
        app.router.add_post("/v1/project/write", self.handle_project_write)
        app.router.add_get("/v1/project/search", self.handle_project_search)
        app.router.add_get("/v1/plugins", self.handle_list_plugins)
        app.router.add_get("/v1/plugins/list", self.handle_list_plugins_alias)
        app.router.add_get("/v1/plugins/{name}", self.handle_plugin_info)
        app.router.add_post("/v1/plugins/activate", self.handle_activate_plugin_alias)
        app.router.add_post("/v1/plugins/deactivate", self.handle_deactivate_plugin_alias)
        app.router.add_post("/v1/plugins/{name}/activate", self.handle_activate_plugin)
        app.router.add_post("/v1/plugins/{name}/deactivate", self.handle_deactivate_plugin)
        app.router.add_get("/v1/costs", self.handle_costs)
        app.router.add_get("/v1/history", self.handle_history)
        # --- Brain Network HTTP ---
        app.router.add_get("/v1/brain/query", self.handle_brain_query)
        app.router.add_get("/v1/brain/stats", self.handle_brain_stats)
        # SSE /v1/events removido — bloquea middleware CORS (handler nunca retorna)
        # y causa CLOSE_WAIT zombie connections que freezan el gateway.
        # Nexus usa polling REST cada 3s como reemplazo.

        # --- MCP Protocol Endpoints ---
        # /mcp is the canonical Streamable HTTP endpoint implemented by the
        # official SDK. /v1/mcp remains an alias for one migration release.
        app.router.add_route("*", "/mcp", self.handle_mcp_transport)
        app.router.add_route("*", "/v1/mcp", self.handle_mcp_transport)
        # Legacy SSE transport remains opt-in for clients that cannot use
        # Streamable HTTP yet. It is intentionally isolated from the new broker.
        app.router.add_get("/v1/mcp/sse", self.handle_mcp_sse)
        app.router.add_post("/v1/mcp/message", self.handle_mcp_message)
        app.router.add_get("/v1/mcp/catalog", self.handle_mcp_catalog)
        app.router.add_post("/v1/mcp/call", self.handle_mcp_tool_call)
        app.router.add_get("/v1/mcp/approvals", self.handle_mcp_approvals)
        app.router.add_post(
            "/v1/mcp/approvals/{approval_id}",
            self.handle_mcp_approval_resolve,
        )
        app.router.add_get("/v1/mcp/traces", self.handle_mcp_traces)

        # --- LLM Streaming Proxy (para bots y clients locales) ---
        app.router.add_post("/v1/llm/stream", self.handle_llm_stream)

        # --- Daemon Autónomo Endpoints (REST) ---
        app.router.add_get("/v1/daemon/status", self.handle_daemon_status)
        app.router.add_get("/v1/daemon/diagnostic", self.handle_daemon_diagnostic)
        app.router.add_post("/v1/daemon/restart", self.handle_daemon_restart)
        app.router.add_post("/v1/daemon/submit", self.handle_daemon_submit)
        app.router.add_get("/v1/daemon/tasks/{task_id}", self.handle_daemon_task)

        # --- Scheduler Endpoints ---
        app.router.add_get("/v1/scheduler/schedules", self.handle_scheduler_list)
        app.router.add_post("/v1/scheduler/schedules", self.handle_scheduler_create)
        app.router.add_delete("/v1/scheduler/schedules/{name}", self.handle_scheduler_delete)

        # --- Message Bus Stats ---
        app.router.add_get("/v1/bus/stats", self.handle_bus_stats)

        # --- A2A Request-Reply Endpoints ---
        app.router.add_post("/v1/a2a/request", self.handle_a2a_request)
        app.router.add_get("/v1/a2a/stats", self.handle_a2a_stats)

        # --- AgentMemory Endpoints ---
        app.router.add_get("/v1/memory/{agent}/recall", self.handle_agent_memory_recall)
        app.router.add_get("/v1/memory/{agent}/stats", self.handle_agent_memory_stats)
        app.router.add_get(
            "/v1/memory/{agent}/conversations", self.handle_agent_memory_conversations
        )
        app.router.add_post("/v1/memory/{agent}/store", self.handle_agent_memory_store)

        # --- mem0 Semantic Memory Endpoints ---
        app.router.add_post("/v1/mem0/store", self.handle_mem0_store)
        app.router.add_post("/v1/mem0/recall", self.handle_mem0_recall)
        app.router.add_get("/v1/mem0/recall", self.handle_mem0_recall)
        app.router.add_get("/v1/mem0/stats", self.handle_mem0_stats)
        app.router.add_post("/v1/mem0/clear", self.handle_mem0_clear)

        # --- Unified Memory Endpoints (compat layer over mem0 + durable layers) ---
        app.router.add_post("/v1/memory/store", self.handle_memory_store)
        app.router.add_post("/v1/memory/recall", self.handle_memory_recall)
        app.router.add_get("/v1/memory/recall", self.handle_memory_recall)
        app.router.add_get("/v1/memory/stats", self.handle_memory_stats)
        app.router.add_get("/v1/memory/events", self.handle_memory_events_list)
        app.router.add_post("/v1/memory/events", self.handle_memory_events_record)
        app.router.add_get("/v1/memory/diagnose", self.handle_memory_diagnose)
        app.router.add_post("/v1/memory/diagnose", self.handle_memory_diagnose)

        # --- MetaPlanner Endpoints (Sprint 2) ---
        app.router.add_post("/v1/planner/execute", self.handle_planner_execute)
        app.router.add_post("/v1/planner/analyze", self.handle_planner_analyze)
        app.router.add_post("/v1/planner/plan", self.handle_planner_create)
        app.router.add_get("/v1/planner/plans", self.handle_planner_list)
        app.router.add_get("/v1/planner/plans/{plan_id}", self.handle_planner_get)
        app.router.add_get("/v1/planner/stats", self.handle_planner_stats)

        # --- AnomalyDetector Endpoints (Sprint 2) ---
        app.router.add_get("/v1/anomalies/alerts", self.handle_anomaly_alerts)
        app.router.add_post("/v1/anomalies/alerts/{alert_id}/ack", self.handle_anomaly_ack)
        app.router.add_get("/v1/anomalies/profiles", self.handle_anomaly_profiles)
        app.router.add_get("/v1/anomalies/profiles/{agent}", self.handle_anomaly_agent_profile)
        app.router.add_get("/v1/anomalies/stats", self.handle_anomaly_stats)

        # --- WorkflowEngine Endpoints (Sprint 3) ---
        app.router.add_get("/v1/workflows/graphs", self.handle_workflow_list_graphs)
        app.router.add_post("/v1/workflows/execute", self.handle_workflow_execute)
        app.router.add_get("/v1/workflows", self.handle_workflow_list)
        app.router.add_get("/v1/workflows/stats", self.handle_workflow_stats)
        app.router.add_get("/v1/workflows/{workflow_id}", self.handle_workflow_get)
        app.router.add_get("/v1/workflows/{workflow_id}/events", self.handle_workflow_events)
        app.router.add_post("/v1/workflows/{workflow_id}/resume", self.handle_workflow_resume)
        app.router.add_post("/v1/workflows/{workflow_id}/cancel", self.handle_workflow_cancel)

        # --- SelfImprovement Endpoints (Sprint 3) ---
        app.router.add_get("/v1/improvement/proposals", self.handle_improvement_proposals)
        app.router.add_post(
            "/v1/improvement/proposals/{proposal_id}", self.handle_improvement_apply
        )
        app.router.add_get("/v1/improvement/report", self.handle_improvement_report)
        app.router.add_get("/v1/improvement/health", self.handle_improvement_health)
        app.router.add_get("/v1/ecosystem/health", self.handle_ecosystem_health)
        app.router.add_get("/v1/improvement/analyze/{agent}", self.handle_improvement_analyze)
        app.router.add_post("/v1/improvement/auto-apply", self.handle_improvement_auto_apply)

        # --- ReactiveEventSystem Endpoints (Sprint 4) ---
        app.router.add_post("/v1/reactive/emit", self.handle_reactive_emit)
        app.router.add_get("/v1/reactive/rules", self.handle_reactive_rules)
        app.router.add_post("/v1/reactive/rules", self.handle_reactive_register_rule)
        app.router.add_post("/v1/reactive/rules/{name}/toggle", self.handle_reactive_toggle_rule)
        app.router.add_get("/v1/reactive/events", self.handle_reactive_events_history)
        app.router.add_get("/v1/reactive/triggers", self.handle_reactive_triggers_history)
        app.router.add_get("/v1/reactive/stats", self.handle_reactive_stats)

        # --- Negotiation Endpoints (Sprint 4) ---
        app.router.add_post("/v1/negotiation/auction", self.handle_negotiation_auction)
        app.router.add_get("/v1/negotiation/agents", self.handle_negotiation_agents)
        app.router.add_get("/v1/negotiation/auctions", self.handle_negotiation_history)
        app.router.add_get(
            "/v1/negotiation/auctions/{auction_id}", self.handle_negotiation_auction_get
        )
        app.router.add_get("/v1/negotiation/stats", self.handle_negotiation_stats)

        # --- Swarm Endpoints (Sprint 4) ---
        app.router.add_post("/v1/swarm/execute", self.handle_swarm_execute)
        app.router.add_get("/v1/swarm", self.handle_swarm_list)
        app.router.add_get("/v1/swarm/stats", self.handle_swarm_stats)
        app.router.add_get("/v1/swarm/{swarm_id}", self.handle_swarm_get)
        app.router.add_post("/v1/swarm/{swarm_id}/cancel", self.handle_swarm_cancel)

        # --- IntelligentRouter Endpoints (Sprint 5) ---
        app.router.add_post("/v1/router/analyze", self.handle_router_analyze)
        app.router.add_post("/v1/router/execute", self.handle_router_execute)
        app.router.add_get("/v1/router/history", self.handle_router_history)
        app.router.add_get("/v1/router/stats", self.handle_router_stats)

        # --- Consensus Endpoints (Sprint 5) ---
        app.router.add_post("/v1/consensus/proposals", self.handle_consensus_create)
        app.router.add_post(
            "/v1/consensus/proposals/{proposal_id}/vote", self.handle_consensus_vote
        )
        app.router.add_post(
            "/v1/consensus/proposals/{proposal_id}/resolve", self.handle_consensus_resolve
        )
        app.router.add_post("/v1/consensus/quick", self.handle_consensus_quick)
        app.router.add_get("/v1/consensus/proposals", self.handle_consensus_list)
        app.router.add_get("/v1/consensus/stats", self.handle_consensus_stats)

        # --- Observatory Endpoints (Sprint 5) ---
        app.router.add_get("/v1/observatory/timeline", self.handle_observatory_timeline)
        app.router.add_get("/v1/observatory/snapshot", self.handle_observatory_snapshot)
        app.router.add_get("/v1/observatory/stats", self.handle_observatory_stats)

        # --- Reputation Endpoints (Sprint 6) ---
        app.router.add_post("/v1/reputation/outcome", self.handle_reputation_outcome)
        app.router.add_get("/v1/reputation/agents/{agent}/trust", self.handle_reputation_trust)
        app.router.add_get("/v1/reputation/agents/{agent}", self.handle_reputation_profile)
        app.router.add_get("/v1/reputation/rankings", self.handle_reputation_rankings)
        app.router.add_post("/v1/reputation/vouch", self.handle_reputation_vouch)
        app.router.add_get("/v1/reputation/stats", self.handle_reputation_stats)
        app.router.add_get("/v1/reputation/history", self.handle_reputation_history)

        # --- Topology Endpoints (Sprint 6) ---
        app.router.add_post("/v1/topology/interaction", self.handle_topology_interaction)
        app.router.add_get("/v1/topology/agents/{agent}/neighbors", self.handle_topology_neighbors)
        app.router.add_get("/v1/topology/agents/{agent}/recommend", self.handle_topology_recommend)
        app.router.add_get("/v1/topology/clusters", self.handle_topology_clusters)
        app.router.add_get("/v1/topology/bottlenecks", self.handle_topology_bottlenecks)
        app.router.add_get("/v1/topology/graph", self.handle_topology_graph)
        app.router.add_get("/v1/topology/stats", self.handle_topology_stats)

        # --- Chronicle Endpoints (Sprint 6) ---
        app.router.add_post("/v1/chronicle/record", self.handle_chronicle_record)
        app.router.add_get("/v1/chronicle/events", self.handle_chronicle_query)
        app.router.add_get(
            "/v1/chronicle/events/{entry_id}/cause", self.handle_chronicle_trace_cause
        )
        app.router.add_get(
            "/v1/chronicle/events/{entry_id}/effects", self.handle_chronicle_trace_effects
        )
        app.router.add_get(
            "/v1/chronicle/events/{entry_id}/root-cause", self.handle_chronicle_root_cause
        )
        app.router.add_post("/v1/chronicle/snapshots", self.handle_chronicle_snapshot)
        app.router.add_get("/v1/chronicle/snapshots", self.handle_chronicle_snapshots_list)
        app.router.add_get("/v1/chronicle/state", self.handle_chronicle_state_at)
        app.router.add_get("/v1/chronicle/stats", self.handle_chronicle_stats)

        # --- CircuitBreaker Endpoints (Sprint 7) ---
        app.router.add_get("/v1/breaker", self.handle_breaker_all)
        app.router.add_get("/v1/breaker/open", self.handle_breaker_open)
        app.router.add_get("/v1/breaker/health", self.handle_breaker_health)
        app.router.add_get("/v1/breaker/stats", self.handle_breaker_stats)
        app.router.add_get("/v1/breaker/agents/{agent}", self.handle_breaker_status)
        app.router.add_post("/v1/breaker/agents/{agent}/reset", self.handle_breaker_reset)
        app.router.add_post("/v1/breaker/agents/{agent}/configure", self.handle_breaker_configure)

        # --- PredictivePrefetch Endpoints (Sprint 7) ---
        app.router.add_get("/v1/prefetch/predict", self.handle_prefetch_predict)
        app.router.add_get("/v1/prefetch/warmup", self.handle_prefetch_warmup)
        app.router.add_get("/v1/prefetch/sequences", self.handle_prefetch_sequences)
        app.router.add_get("/v1/prefetch/matrix", self.handle_prefetch_matrix)
        app.router.add_get("/v1/prefetch/accuracy", self.handle_prefetch_accuracy)
        app.router.add_get("/v1/prefetch/stats", self.handle_prefetch_stats)

        # --- Contract Endpoints (Sprint 7) ---
        app.router.add_post("/v1/contracts", self.handle_contract_create)
        app.router.add_get("/v1/contracts", self.handle_contract_list)
        app.router.add_get("/v1/contracts/compliance", self.handle_contract_compliance_all)
        app.router.add_get("/v1/contracts/violations", self.handle_contract_violations)
        app.router.add_get("/v1/contracts/stats", self.handle_contract_stats)
        app.router.add_get("/v1/contracts/agents/{agent}", self.handle_contract_get)
        app.router.add_get(
            "/v1/contracts/agents/{agent}/compliance", self.handle_contract_compliance
        )
        app.router.add_post("/v1/contracts/agents/{agent}/auto", self.handle_contract_auto)

        # --- Genome Endpoints (Sprint 8) ---
        app.router.add_get("/v1/genome", self.handle_genome_all)
        app.router.add_get("/v1/genome/ranking", self.handle_genome_ranking)
        app.router.add_get("/v1/genome/stats", self.handle_genome_stats)
        app.router.add_post("/v1/genome/evolve", self.handle_genome_evolve)
        app.router.add_get("/v1/genome/agents/{agent}", self.handle_genome_get)
        app.router.add_post("/v1/genome/agents/{agent}", self.handle_genome_register)
        app.router.add_post("/v1/genome/agents/{agent}/evaluate", self.handle_genome_evaluate)

        # --- Knowledge Distillation Endpoints (Sprint 8) ---
        app.router.add_post("/v1/knowledge/distill", self.handle_distill)
        app.router.add_post("/v1/knowledge/transfer", self.handle_transfer)
        app.router.add_get("/v1/knowledge/stats", self.handle_distillation_stats)
        app.router.add_get("/v1/knowledge/agents/{agent}", self.handle_knowledge_get)
        app.router.add_get("/v1/knowledge/experts/{domain}", self.handle_find_experts)

        # --- Adversarial Arena Endpoints (Sprint 8) ---
        app.router.add_post("/v1/arena/challenges", self.handle_arena_challenge)
        app.router.add_post("/v1/arena/challenges/{id}/respond", self.handle_arena_respond)
        app.router.add_get("/v1/arena/rankings", self.handle_arena_rankings)
        app.router.add_get("/v1/arena/matchups", self.handle_arena_matchups)
        app.router.add_get("/v1/arena/history", self.handle_arena_history)
        app.router.add_get("/v1/arena/stats", self.handle_arena_stats)
        app.router.add_get("/v1/arena/agents/{agent}", self.handle_arena_profile)

        # --- Nervous System Endpoints (Sprint 9A) ---
        app.router.add_post("/v1/ws/broadcast", self.handle_ws_broadcast)
        app.router.add_post("/v1/ws/connect", self.handle_ws_connect)
        app.router.add_post("/v1/ws/subscribe", self.handle_ws_subscribe)
        app.router.add_get("/v1/ws/clients", self.handle_ws_clients)
        app.router.add_get("/v1/ws/stats", self.handle_ws_stats)
        app.router.add_get("/v1/dashboard/snapshot", self.handle_dashboard_snapshot)
        app.router.add_get("/v1/dashboard/timeline", self.handle_dashboard_timeline)
        app.router.add_get("/v1/dashboard/stats", self.handle_dashboard_stats)
        app.router.add_post("/v1/alerts/fire", self.handle_alert_fire)
        app.router.add_post("/v1/alerts/resolve", self.handle_alert_resolve)
        app.router.add_get("/v1/alerts/active", self.handle_alert_active)
        app.router.add_get("/v1/alerts/stats", self.handle_alert_stats)

        # --- Federation Endpoints (Sprint 9B) ---
        app.router.add_post("/v1/federation/local", self.handle_federation_register_local)
        app.router.add_post("/v1/federation/peers", self.handle_federation_register_peer)
        app.router.add_post("/v1/federation/delegate", self.handle_federation_delegate)
        app.router.add_get("/v1/federation/peers", self.handle_federation_peers)
        app.router.add_get("/v1/federation/stats", self.handle_federation_stats)
        app.router.add_post("/v1/marketplace/publish", self.handle_marketplace_publish)
        app.router.add_get("/v1/marketplace/search", self.handle_marketplace_search)
        app.router.add_post("/v1/marketplace/acquire", self.handle_marketplace_acquire)
        app.router.add_get("/v1/marketplace/trending", self.handle_marketplace_trending)
        app.router.add_get("/v1/marketplace/stats", self.handle_marketplace_stats)
        app.router.add_post("/v1/trust/set", self.handle_trust_set)
        app.router.add_get("/v1/trust/calculate/{target}", self.handle_trust_calculate)
        app.router.add_get("/v1/trust/graph", self.handle_trust_graph)
        app.router.add_get("/v1/trust/stats", self.handle_trust_stats)

        # --- Cortex Endpoints (Sprint 9C) ---
        app.router.add_post("/v1/metacognition/record", self.handle_meta_record)
        app.router.add_get("/v1/metacognition/diagnose", self.handle_meta_diagnose)
        app.router.add_get("/v1/metacognition/recommendations", self.handle_meta_recommendations)
        app.router.add_get("/v1/metacognition/stats", self.handle_meta_stats)
        app.router.add_post("/v1/goals/create", self.handle_goal_create)
        app.router.add_get("/v1/goals/active", self.handle_goal_active)
        app.router.add_post("/v1/goals/{goal_id}/progress", self.handle_goal_progress)
        app.router.add_get("/v1/goals/stats", self.handle_goal_stats)
        app.router.add_post("/v1/emergent/observe", self.handle_emergent_observe)
        app.router.add_post("/v1/emergent/detect", self.handle_emergent_detect)
        app.router.add_get("/v1/emergent/patterns", self.handle_emergent_patterns)
        app.router.add_get("/v1/emergent/stats", self.handle_emergent_stats)

        # --- Intelligence Aggregation Endpoints (Evolución Panel) ---
        app.router.add_get("/v1/intelligence/agent-performance", self.handle_agent_performance)
        app.router.add_get("/v1/intelligence/skill-effectiveness", self.handle_skill_effectiveness)

        # --- AutoTune Endpoints ---
        app.router.add_post("/v1/autotune/analyze", self.handle_autotune_analyze)
        app.router.add_post("/v1/autotune/feedback", self.handle_autotune_feedback)

        # --- Parallel Racer Endpoints ---
        app.router.add_post("/v1/race/run", self.handle_race_run)
        app.router.add_get("/v1/race/rankings", self.handle_race_rankings)

        # --- Universal Search Endpoint ---
        app.router.add_post("/v1/search/universal", self.handle_universal_search)

        # --- Rate Limit Stats Endpoint ---
        app.router.add_get("/v1/rate-limit/stats", self.handle_rate_limit_stats)

        # --- Unified Knowledge Bridge Endpoints ---
        app.router.add_post("/v1/knowledge/search", self.handle_knowledge_search)
        app.router.add_get("/v1/knowledge/context", self.handle_knowledge_context)
        app.router.add_post("/v1/knowledge/sync", self.handle_knowledge_sync)
        app.router.add_get("/v1/knowledge/brief", self.handle_knowledge_brief)

        # --- Session Reporting Hooks ---
        app.router.add_post("/v1/hooks/session-report", self.handle_session_report)

        # --- Process Watcher (events ingest + polling + SSE stream + daemon) ---
        app.router.add_post("/v1/watcher/events", self.handle_watcher_events)
        app.router.add_get("/v1/watcher/events/recent", self.handle_watcher_events_recent)
        app.router.add_get("/v1/watcher/events/history", self.handle_watcher_events_history)
        app.router.add_get("/v1/watcher/stream", self.handle_watcher_stream)
        app.router.add_get("/v1/watcher/status", self.handle_watcher_status)
        app.router.add_get("/v1/watcher/metrics", self.handle_watcher_metrics)
        app.router.add_post("/v1/watcher/spawn", self.handle_watcher_spawn)
        app.router.add_get("/v1/watcher/list", self.handle_watcher_list_http)
        app.router.add_post("/v1/watcher/{watch_id}/kill", self.handle_watcher_kill_http)
        app.router.add_get("/v1/watcher/{watch_id}/tail", self.handle_watcher_tail_http)

        # --- Context Engine HTTP endpoints ---
        app.router.add_get("/v1/context-engine/list", self.handle_context_engine_list)
        app.router.add_get("/v1/context-engine/current", self.handle_context_engine_current)
        app.router.add_post("/v1/context-engine/switch", self.handle_context_engine_switch)
        app.router.add_post("/v1/context-engine/preview", self.handle_context_engine_preview)
        app.router.add_post("/v1/context-engine/stats", self.handle_context_engine_stats)

        # Redirect / -> /v1/
        app.router.add_get("/", lambda r: web.HTTPFound("/v1/"))
        app.router.add_get("/health", lambda r: web.HTTPFound("/v1/health"))

        # --- Excel Engine Routes ---
        register_excel_routes(app)

        return app


# ============================================================
# /v1/excel/* routes — Plan A
# ============================================================

import importlib.util as _excel_iutil  # noqa: E402
import sys as _excel_sys  # noqa: E402
from pathlib import Path as _ExcelPath  # noqa: E402


def _load_excel_handlers():  # type: ignore[no-untyped-def]
    """Lazy-load del módulo excel-server para reutilizar sus handlers."""
    server_path = _ExcelPath(__file__).parent / "excel-server.py"
    spec = _excel_iutil.spec_from_file_location("excel_server", server_path)
    assert spec is not None and spec.loader is not None
    mod = _excel_iutil.module_from_spec(spec)
    _excel_sys.modules["excel_server"] = mod
    spec.loader.exec_module(mod)  # type: ignore[union-attr]
    return mod


_excel_mod = None


def _excel():  # type: ignore[no-untyped-def]
    global _excel_mod
    if _excel_mod is None:
        _excel_mod = _load_excel_handlers()
    return _excel_mod


async def route_excel_health(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    return web.json_response(_excel().handle_excel_health({}))


async def route_excel_open(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    body = await request.json()
    return web.json_response(_excel().handle_excel_open(body))


async def route_excel_close(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    sid = request.match_info["session_id"]
    save_q = request.query.get("save", "true").lower() in ("true", "1", "yes")
    return web.json_response(_excel().handle_excel_close({"session_id": sid, "save": save_q}))


async def route_excel_list(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    return web.json_response(_excel().handle_excel_list_sessions({}))


async def route_excel_parse(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    body = await request.json()
    return web.json_response(_excel().handle_excel_parse_smart(body))


async def route_excel_range(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    """POST /v1/excel/sessions/{id}/range — acción en body (read|write)."""
    sid = request.match_info["session_id"]
    body = await request.json()
    body["session_id"] = sid
    action = body.get("action", "write")
    if action == "read":
        return web.json_response(_excel().handle_excel_read_range(body))
    return web.json_response(_excel().handle_excel_write_range(body))


async def route_excel_table(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    sid = request.match_info["session_id"]
    body = await request.json()
    body["session_id"] = sid
    return web.json_response(_excel().handle_excel_create_table(body))


async def route_excel_save(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    sid = request.match_info["session_id"]
    body = await request.json()
    body["session_id"] = sid
    return web.json_response(_excel().handle_excel_save_as(body))


async def route_excel_formula(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    sid = request.match_info["session_id"]
    body = await request.json()
    body["session_id"] = sid
    return web.json_response(_excel().handle_excel_apply_formula(body))


async def route_excel_format(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    sid = request.match_info["session_id"]
    body = await request.json()
    body["session_id"] = sid
    return web.json_response(_excel().handle_excel_set_format(body))


# Placeholders Plan B — el handler devuelve BACKEND_NOT_SHIPPED.
async def route_excel_plan_b_pivot(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    sid = request.match_info["session_id"]
    return web.json_response(_excel().handle_excel_create_pivot({"session_id": sid}))


async def route_excel_plan_b_chart(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    sid = request.match_info["session_id"]
    return web.json_response(_excel().handle_excel_create_chart({"session_id": sid}))


async def route_excel_plan_b_macro(request: web.Request) -> web.Response:  # type: ignore[no-untyped-def]
    sid = request.match_info["session_id"]
    return web.json_response(_excel().handle_excel_run_macro({"session_id": sid}))


def register_excel_routes(app: web.Application) -> None:
    """Registra todas las rutas /v1/excel/* en la aplicación aiohttp."""
    app.router.add_get("/v1/excel/health", route_excel_health)
    app.router.add_post("/v1/excel/sessions", route_excel_open)
    app.router.add_get("/v1/excel/sessions", route_excel_list)
    app.router.add_delete("/v1/excel/sessions/{session_id}", route_excel_close)
    app.router.add_post("/v1/excel/parse", route_excel_parse)
    app.router.add_post("/v1/excel/sessions/{session_id}/range", route_excel_range)
    app.router.add_post("/v1/excel/sessions/{session_id}/table", route_excel_table)
    app.router.add_post("/v1/excel/sessions/{session_id}/save", route_excel_save)
    app.router.add_post("/v1/excel/sessions/{session_id}/formula", route_excel_formula)
    app.router.add_post("/v1/excel/sessions/{session_id}/format", route_excel_format)
    app.router.add_post("/v1/excel/sessions/{session_id}/pivot", route_excel_plan_b_pivot)
    app.router.add_post("/v1/excel/sessions/{session_id}/chart", route_excel_plan_b_chart)
    app.router.add_post("/v1/excel/sessions/{session_id}/macro", route_excel_plan_b_macro)


def build_app_for_tests(
    api_key: str,
    require_auth: bool = True,
    brain_dir: str | None = None,
) -> web.Application:
    """Construye una app aiohttp mínima con auth middleware y rutas Excel.

    Usada por los tests para verificar las rutas Excel sin levantar el
    gateway completo.
    """
    import hashlib
    import hmac
    import os

    if brain_dir:
        os.environ["ANTIGRAVITY_BRAIN_DIR"] = brain_dir

    @web.middleware
    async def auth_mw(request: web.Request, handler: web.RequestHandler) -> web.StreamResponse:
        public_paths = {"/health", "/v1/health", "/v1/ready"}
        if request.path in public_paths or request.method == "OPTIONS":
            return await handler(request)
        if not require_auth:
            return await handler(request)
        provided = request.headers.get("X-API-Key", "")
        if not provided:
            return web.json_response({"error": "missing X-API-Key"}, status=401)
        if not hmac.compare_digest(
            hashlib.sha256(provided.encode()).digest(),
            hashlib.sha256(api_key.encode()).digest(),
        ):
            return web.json_response({"error": "invalid X-API-Key"}, status=403)
        return await handler(request)

    app = web.Application(middlewares=[auth_mw])
    register_excel_routes(app)
    return app


# ============================================================
# CLI Entry Point
# ============================================================
def _parse_cli_args(args: list[str], config: GatewayConfig, profile: ProfileConfig) -> None:
    """Parsea los flags CLI y los aplica sobre `config` in-place.

    Los flags tienen prioridad sobre los valores ya resueltos desde env vars.
    `--help`/`-h` imprime la ayuda y termina el proceso.

    Args:
        args: Lista de argumentos CLI (normalmente `sys.argv[1:]`).
        config: Configuracion del gateway a mutar segun los flags.
        profile: Perfil de runtime activo (controla si `--no-auth` es valido).
    """
    i = 0
    while i < len(args):
        if args[i] == "--port" and i + 1 < len(args):
            config.port = int(args[i + 1])
            i += 2
        elif args[i] == "--host" and i + 1 < len(args):
            config.host = args[i + 1]
            i += 2
        elif args[i] == "--api-key" and i + 1 < len(args):
            config.api_key = args[i + 1]
            i += 2
        elif args[i] == "--no-auth":
            if not profile.allow_no_auth_flag:
                log.warning(
                    "--no-auth ignorado: el perfil '%s' requiere autenticación obligatoria.",
                    profile.name,
                )
            else:
                config.require_auth = False
                log.warning(
                    "Modo --no-auth activado: el gateway acepta conexiones SIN autenticacion. "
                    "Usar solo en desarrollo local."
                )
            i += 1
        elif args[i] in ("--help", "-h"):
            sys.stderr.write(
                f"Antigravity MCP HTTP Gateway v{VERSION}\n"
                "========================================\n\n"
                "Uso:\n"
                "  python gateway.py                        # Puerto 4747, localhost\n"
                "  python gateway.py --port 4747            # Puerto especifico\n"
                "  python gateway.py --host 0.0.0.0         # Exponer a red\n"
                "  python gateway.py --api-key mi-clave     # Forzar API key\n"
                "  python gateway.py --no-auth              # Sin autenticacion (dev)\n\n"
                "Variables de entorno:\n"
                "  ANTIGRAVITY_GATEWAY_PORT   Puerto (default: 4747)\n"
                "  ANTIGRAVITY_GATEWAY_HOST   Host (default: 127.0.0.1)\n"
                "  ANTIGRAVITY_HOME           Directorio raiz del ecosistema\n"
                "  ANTIGRAVITY_API_KEY        API key para autenticacion\n"
                "  ANTIGRAVITY_CORS_ORIGINS   Origenes CORS (comma-separated)\n"
                "  ANTIGRAVITY_RATE_LIMIT     Requests/min por IP (default: 60)\n"
                "  ANTIGRAVITY_PROFILE        Perfil de runtime: minimal|standard|strict\n"
            )
            sys.exit(0)
        else:
            i += 1


def _log_startup_banner(config: GatewayConfig, profile: ProfileConfig) -> None:
    """Loguea el banner de arranque del gateway con la config efectiva.

    Args:
        config: Configuracion resuelta del gateway.
        profile: Perfil de runtime activo.
    """
    agent_count = sum(1 for d in AGENTS_DIR.iterdir() if d.is_dir() and not d.name.startswith("_"))

    log.info("Gateway starting with profile: %s", profile.name)
    log.info("Antigravity MCP HTTP Gateway v%s", VERSION)
    log.info("  Perfil: %s", profile.name)
    log.info("  Puerto: %d", config.port)
    log.info("  Host: %s", config.host)
    log.info("  Auth: %s", "ACTIVO" if config.require_auth else "DESACTIVADO")
    log.info("  CORS: %s (%s)", ", ".join(config.cors_origins), profile.cors_mode)
    log.info(
        "  Rate limit: %s",
        f"{config.rate_limit_per_minute} req/min"
        if config.rate_limit_per_minute > 0
        else "DESACTIVADO",
    )
    log.info("  Daemon: %s", "lite" if profile.daemon_lite else "full")
    log.info("  Agentes: %d", agent_count)
    log.info("  Home: %s", BASE_DIR)
    log.info("")
    log.info("  URL:     http://%s:%d/v1/", config.host, config.port)
    log.info("  Health:  http://%s:%d/v1/health", config.host, config.port)
    log.info("  Ready:   http://%s:%d/v1/ready", config.host, config.port)
    log.info("  Metrics: http://%s:%d/v1/metrics", config.host, config.port)
    log.info("  OpenAPI: http://%s:%d/v1/openapi.json", config.host, config.port)
    # Streaming removido (WS + SSE) — REST puro para estabilidad
    # WebSocket removido (Option C) — solo REST + SSE para evitar freeze por zombie connections
    if HAS_TELEMETRY:
        log.info("  OTel:    ACTIVO (traces + metrics)")
    if HAS_EVENT_BUS:
        log.info("  EventBus: ACTIVO")


def main() -> None:
    """Punto de entrada del gateway HTTP."""
    if not AIOHTTP_AVAILABLE:
        sys.stderr.write("Error: aiohttp no instalado.\nInstala con: pip install aiohttp\n")
        sys.exit(1)

    profile = ACTIVE_PROFILE

    # Env vars / CLI pueden sobreescribir valores del perfil.
    # El perfil provee los *defaults inteligentes*; env vars tienen prioridad explícita.
    config = GatewayConfig(
        port=int(os.environ.get("ANTIGRAVITY_GATEWAY_PORT", DEFAULT_PORT)),
        host=os.environ.get("ANTIGRAVITY_GATEWAY_HOST", DEFAULT_HOST),
        api_key=os.environ.get("ANTIGRAVITY_API_KEY"),
        cors_origins=parse_cors_origins(os.environ.get("ANTIGRAVITY_CORS_ORIGINS")),
        rate_limit_per_minute=int(
            os.environ.get("ANTIGRAVITY_RATE_LIMIT", str(profile.rate_limit))
        ),
        profile=profile,
    )

    # Parsear argumentos CLI (mutan `config` in-place segun los flags recibidos)
    _parse_cli_args(sys.argv[1:], config, profile)

    # Si require_auth pero no hay API key explicita, generar/cargar session key
    # del disco. Asi cualquier cliente local del ecosistema (Nexus, bot Telegram,
    # CLI) que tenga acceso al user's home puede leerla y autenticarse, sin que
    # un browser u otra app sin acceso al filesystem pueda hacer drive-by CORS.
    if config.require_auth:
        if not config.api_key:
            try:
                config.api_key = ensure_session_key()
                log.info(
                    "Session key efimera generada/cargada en ~/.antigravity/session.key (0600). "
                    "Los clientes locales del ecosistema deben leerla para autenticarse."
                )
            except OSError as exc:
                log.error(
                    "No se pudo crear ~/.antigravity/session.key: %s. "
                    "Setea ANTIGRAVITY_API_KEY explicitamente o corre con --no-auth.",
                    exc,
                )
                sys.exit(2)
        else:
            # Si hay una API key explicita configurada (por ejemplo, en el .env),
            # la persistimos cifrada en session.key para que los clientes locales
            # (Nexus, CLI, bot) puedan autenticarse sin discrepancias de llaves.
            try:
                try:
                    from .session_key import session_key_path, _atomic_write_encrypted
                except ImportError:
                    from session_key import session_key_path, _atomic_write_encrypted  # type: ignore[no-redef]

                try:
                    from core.dpapi import encrypt_for_user
                except ImportError:
                    parent_agent = str(Path(__file__).resolve().parents[1])
                    if parent_agent not in sys.path:
                        sys.path.insert(0, parent_agent)
                    from core.dpapi import encrypt_for_user

                path = session_key_path()
                path.parent.mkdir(parents=True, exist_ok=True)
                encrypted = encrypt_for_user(config.api_key.encode("utf-8"), path)
                _atomic_write_encrypted(path, encrypted)
                log.info(
                    "API key explicito guardado y cifrado en ~/.antigravity/session.key para compatibilidad local."
                )
            except Exception as e:
                log.warning("No se pudo persistir la API key explicito en session.key: %s", e)

    # SECURITY: Block --no-auth + 0.0.0.0 combination (was only warning)
    # nosec B104: no es un bind a 0.0.0.0 sino el guard que lo BLOQUEA sin auth.
    if config.host == "0.0.0.0" and not config.require_auth:  # nosec B104
        log.error(
            "SEGURIDAD CRITICA: Gateway no puede exponerse a 0.0.0.0 sin autenticacion. "
            "Usa --host 127.0.0.1 o configura ANTIGRAVITY_API_KEY."
        )
        sys.exit(1)

    if not AGENTS_DIR.exists():
        sys.stderr.write(
            f"Error: No se encontro directorio de agentes en {AGENTS_DIR}\n"
            "Usa ANTIGRAVITY_HOME para especificar la ruta.\n"
        )
        sys.exit(1)

    gateway = AntigravityGateway(config)
    app = gateway.build_app()

    _log_startup_banner(config, profile)

    web.run_app(
        app,
        host=config.host,
        port=config.port,
        print=None,
        keepalive_timeout=3,  # Cerrar conexiones idle rapido (Nexus pollea cada 3-15s)
        # shutdown_timeout ampliado a 15s para que mem0/ChromaDB/SQLite alcancen
        # a flushear en graceful shutdown. Antes era 5s y cortaba transacciones
        # en vuelo dejando DB inconsistente al proximo startup.
        shutdown_timeout=15,
    )


if __name__ == "__main__":
    main()
