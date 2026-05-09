"""
Circuit Breaker — Resilience Patterns para agentes.

Implementa el patrón Circuit Breaker con estados:
  - CLOSED: operación normal, se cuentan fallos
  - OPEN: agente aislado, todas las llamadas fallan rápido
  - HALF_OPEN: permite una llamada de prueba para verificar recovery

Además:
  - Bulkhead isolation: limita concurrencia por agente
  - Rate limiting por agente
  - Fallback chains: agentes alternativos cuando el principal falla
  - Health probes: verificación periódica de agentes aislados
  - Integración con reputation (fallo en circuit → baja reputación)

Usage:
    breaker = CircuitBreakerManager(bus=bus)

    # Verificar si un agente está disponible
    if breaker.can_execute("explorer"):
        try:
            result = await execute_agent("explorer", task)
            breaker.record_success("explorer")
        except Exception:
            breaker.record_failure("explorer")
    else:
        fallback = breaker.get_fallback("explorer")

    # Estado de todos los breakers
    status = breaker.get_all_status()

    # Forzar reset manual
    breaker.force_reset("explorer")
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.circuit_breaker")

# ============================================================
# Constantes
# ============================================================
FAILURE_THRESHOLD = 3  # Fallos para abrir el circuito
RECOVERY_TIMEOUT = 60.0  # Segundos antes de half-open
HALF_OPEN_MAX_CALLS = 1  # Llamadas permitidas en half-open
SUCCESS_THRESHOLD = 2  # Éxitos en half-open para cerrar
MAX_CONCURRENT_PER_AGENT = 5  # Bulkhead: máximo concurrente
RATE_LIMIT_PER_MINUTE = 30  # Rate limit por agente
MAX_EVENT_HISTORY = 200  # Historial de eventos por breaker


# ============================================================
# Enums
# ============================================================
class BreakerState(str, Enum):
    """Estados del circuit breaker."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Isolated, fast-fail
    HALF_OPEN = "half_open"  # Testing recovery


class BreakerEventType(str, Enum):
    """Tipos de evento del breaker."""

    SUCCESS = "success"
    FAILURE = "failure"
    STATE_CHANGE = "state_change"
    FALLBACK_USED = "fallback_used"
    RATE_LIMITED = "rate_limited"
    BULKHEAD_REJECTED = "bulkhead_rejected"
    MANUAL_RESET = "manual_reset"
    PROBE_SUCCESS = "probe_success"
    PROBE_FAILURE = "probe_failure"


# ============================================================
# Modelos
# ============================================================
@dataclass
class BreakerEvent:
    """Evento de un circuit breaker."""

    event_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: str = ""
    event_type: BreakerEventType = BreakerEventType.SUCCESS
    state_before: BreakerState = BreakerState.CLOSED
    state_after: BreakerState = BreakerState.CLOSED
    detail: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_id": self.event_id,
            "agent": self.agent,
            "event_type": self.event_type.value,
            "state_before": self.state_before.value,
            "state_after": self.state_after.value,
            "detail": self.detail,
            "timestamp": self.timestamp,
        }


@dataclass
class AgentBreaker:
    """Circuit breaker para un agente individual."""

    agent: str
    state: BreakerState = BreakerState.CLOSED
    failure_count: int = 0
    success_count: int = 0  # Éxitos consecutivos en half-open
    total_successes: int = 0
    total_failures: int = 0
    total_calls: int = 0
    last_failure_time: float = 0.0
    last_state_change: float = field(default_factory=time.time)
    opened_count: int = 0  # Veces que se abrió
    concurrent_calls: int = 0
    rate_calls: list[float] = field(default_factory=list)
    fallback_agents: list[str] = field(default_factory=list)
    events: list[BreakerEvent] = field(default_factory=list)

    # Config overrides (per-agent)
    failure_threshold: int = FAILURE_THRESHOLD
    recovery_timeout: float = RECOVERY_TIMEOUT
    max_concurrent: int = MAX_CONCURRENT_PER_AGENT
    rate_limit: int = RATE_LIMIT_PER_MINUTE

    @property
    def is_available(self) -> bool:
        """Si el agente puede recibir llamadas."""
        if self.state == BreakerState.CLOSED:
            return True
        if self.state == BreakerState.HALF_OPEN:
            return self.concurrent_calls < HALF_OPEN_MAX_CALLS
        # OPEN: check if recovery timeout passed
        if self.state == BreakerState.OPEN:
            elapsed = time.time() - self.last_state_change
            return elapsed >= self.recovery_timeout
        return False

    @property
    def health_pct(self) -> float:
        """Porcentaje de salud [0, 100]."""
        if self.total_calls == 0:
            return 100.0
        return round(self.total_successes / self.total_calls * 100, 1)

    @property
    def time_in_state(self) -> float:
        """Segundos en el estado actual."""
        return round(time.time() - self.last_state_change, 1)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "state": self.state.value,
            "is_available": self.is_available,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "total_calls": self.total_calls,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "health_pct": self.health_pct,
            "opened_count": self.opened_count,
            "concurrent_calls": self.concurrent_calls,
            "time_in_state": self.time_in_state,
            "fallback_agents": self.fallback_agents,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout": self.recovery_timeout,
        }


# ============================================================
# Circuit Breaker Manager
# ============================================================
class CircuitBreakerManager:
    """
    Gestiona circuit breakers para todos los agentes.
    Implementa circuit breaker, bulkhead, rate limiting y fallbacks.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus
        self._breakers: dict[str, AgentBreaker] = {}

        # Métricas globales
        self._metrics = {
            "total_calls": 0,
            "total_successes": 0,
            "total_failures": 0,
            "circuits_opened": 0,
            "circuits_closed": 0,
            "fallbacks_used": 0,
            "rate_limited": 0,
            "bulkhead_rejected": 0,
        }

    # --------------------------------------------------------
    # Core: Can Execute / Record
    # --------------------------------------------------------
    def can_execute(self, agent: str) -> bool:
        """
        Verifica si un agente puede recibir una llamada.

        Checks: circuit state, bulkhead, rate limit.

        Returns:
            True si el agente está disponible.
        """
        breaker = self._get_or_create(agent)

        # Check state transition (OPEN → HALF_OPEN si timeout pasó)
        self._check_state_transition(breaker)

        # Circuit breaker check
        if not breaker.is_available:
            return False

        # Bulkhead check
        if breaker.concurrent_calls >= breaker.max_concurrent:
            self._add_event(
                breaker,
                BreakerEventType.BULKHEAD_REJECTED,
                f"concurrent={breaker.concurrent_calls}",
            )
            self._metrics["bulkhead_rejected"] += 1
            return False

        # Rate limit check
        now = time.time()
        cutoff = now - 60.0
        breaker.rate_calls = [t for t in breaker.rate_calls if t > cutoff]
        if len(breaker.rate_calls) >= breaker.rate_limit:
            self._add_event(
                breaker, BreakerEventType.RATE_LIMITED, f"calls_in_window={len(breaker.rate_calls)}"
            )
            self._metrics["rate_limited"] += 1
            return False

        return True

    def acquire(self, agent: str) -> bool:
        """
        Adquiere un slot de ejecución (incrementa concurrente).

        Returns:
            True si se adquirió exitosamente.
        """
        if not self.can_execute(agent):
            return False

        breaker = self._breakers[agent]
        breaker.concurrent_calls += 1
        breaker.rate_calls.append(time.time())
        breaker.total_calls += 1
        self._metrics["total_calls"] += 1
        return True

    def release(self, agent: str) -> None:
        """Libera un slot de ejecución (decrementa concurrente)."""
        breaker = self._breakers.get(agent)
        if breaker and breaker.concurrent_calls > 0:
            breaker.concurrent_calls -= 1

    def record_success(self, agent: str) -> BreakerState:
        """
        Registra una ejecución exitosa.

        Returns:
            Estado actual del breaker después del registro.
        """
        breaker = self._get_or_create(agent)

        breaker.total_successes += 1
        breaker.failure_count = 0  # Reset consecutive failures
        self._metrics["total_successes"] += 1

        self._add_event(breaker, BreakerEventType.SUCCESS)

        if breaker.state == BreakerState.HALF_OPEN:
            breaker.success_count += 1
            if breaker.success_count >= SUCCESS_THRESHOLD:
                self._transition(breaker, BreakerState.CLOSED, "recovery confirmed")
        elif breaker.state == BreakerState.OPEN:
            # Shouldn't happen normally, but handle it
            self._transition(breaker, BreakerState.CLOSED, "success while open")

        return breaker.state

    def record_failure(self, agent: str, error: str = "") -> BreakerState:
        """
        Registra una ejecución fallida.

        Returns:
            Estado actual del breaker después del registro.
        """
        breaker = self._get_or_create(agent)

        breaker.failure_count += 1
        breaker.total_failures += 1
        breaker.last_failure_time = time.time()
        self._metrics["total_failures"] += 1

        detail = f"failure #{breaker.failure_count}"
        if error:
            detail += f": {error[:100]}"
        self._add_event(breaker, BreakerEventType.FAILURE, detail)

        if breaker.state == BreakerState.HALF_OPEN:
            # Fallo en half-open → volver a open
            self._transition(breaker, BreakerState.OPEN, "half-open test failed")
        elif breaker.state == BreakerState.CLOSED:
            if breaker.failure_count >= breaker.failure_threshold:
                self._transition(
                    breaker, BreakerState.OPEN, f"{breaker.failure_count} consecutive failures"
                )

        return breaker.state

    # --------------------------------------------------------
    # Fallbacks
    # --------------------------------------------------------
    def set_fallbacks(self, agent: str, fallbacks: list[str]) -> None:
        """Configura agentes de fallback."""
        breaker = self._get_or_create(agent)
        breaker.fallback_agents = [f for f in fallbacks if f != agent]

    def get_fallback(self, agent: str) -> str | None:
        """
        Obtiene el mejor agente de fallback disponible.

        Returns:
            Nombre del agente fallback o None.
        """
        breaker = self._breakers.get(agent)
        if not breaker:
            return None

        for fallback in breaker.fallback_agents:
            if self.can_execute(fallback):
                self._add_event(breaker, BreakerEventType.FALLBACK_USED, f"routed to {fallback}")
                self._metrics["fallbacks_used"] += 1
                return fallback

        return None

    # --------------------------------------------------------
    # Configuration
    # --------------------------------------------------------
    def configure(
        self,
        agent: str,
        failure_threshold: int | None = None,
        recovery_timeout: float | None = None,
        max_concurrent: int | None = None,
        rate_limit: int | None = None,
        fallbacks: list[str] | None = None,
    ) -> dict[str, Any]:
        """Configura parámetros del breaker para un agente."""
        breaker = self._get_or_create(agent)
        if failure_threshold is not None:
            breaker.failure_threshold = max(1, failure_threshold)
        if recovery_timeout is not None:
            breaker.recovery_timeout = max(1.0, recovery_timeout)
        if max_concurrent is not None:
            breaker.max_concurrent = max(1, max_concurrent)
        if rate_limit is not None:
            breaker.rate_limit = max(1, rate_limit)
        if fallbacks is not None:
            breaker.fallback_agents = [f for f in fallbacks if f != agent]
        return breaker.to_dict()

    # --------------------------------------------------------
    # Manual Controls
    # --------------------------------------------------------
    def force_reset(self, agent: str) -> dict[str, Any]:
        """Fuerza el reset de un breaker a CLOSED."""
        breaker = self._get_or_create(agent)
        self._transition(breaker, BreakerState.CLOSED, "manual reset")
        breaker.failure_count = 0
        breaker.success_count = 0
        self._add_event(breaker, BreakerEventType.MANUAL_RESET)
        return breaker.to_dict()

    def force_open(self, agent: str, reason: str = "manual") -> dict[str, Any]:
        """Fuerza la apertura de un breaker."""
        breaker = self._get_or_create(agent)
        self._transition(breaker, BreakerState.OPEN, f"forced: {reason}")
        return breaker.to_dict()

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_status(self, agent: str) -> dict[str, Any]:
        """Estado de un breaker específico."""
        breaker = self._get_or_create(agent)
        self._check_state_transition(breaker)
        return breaker.to_dict()

    def get_all_status(self) -> list[dict[str, Any]]:
        """Estado de todos los breakers."""
        result = []
        for agent in sorted(self._breakers.keys()):
            breaker = self._breakers[agent]
            self._check_state_transition(breaker)
            result.append(breaker.to_dict())
        return result

    def get_open_circuits(self) -> list[dict[str, Any]]:
        """Retorna solo los circuitos abiertos o half-open."""
        return [
            b.to_dict()
            for b in self._breakers.values()
            if b.state in (BreakerState.OPEN, BreakerState.HALF_OPEN)
        ]

    def get_events(
        self,
        agent: str | None = None,
        event_type: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de eventos filtrado."""
        if agent:
            breaker = self._breakers.get(agent)
            if not breaker:
                return []
            events = breaker.events
        else:
            events = []
            for b in self._breakers.values():
                events.extend(b.events)
            events.sort(key=lambda e: e.timestamp)

        if event_type:
            events = [e for e in events if e.event_type.value == event_type]

        return [e.to_dict() for e in events[-limit:]][::-1]

    # --------------------------------------------------------
    # Health Check
    # --------------------------------------------------------
    def health_summary(self) -> dict[str, Any]:
        """Resumen de salud del sistema de breakers."""
        total = len(self._breakers)
        closed = sum(1 for b in self._breakers.values() if b.state == BreakerState.CLOSED)
        half_open = sum(1 for b in self._breakers.values() if b.state == BreakerState.HALF_OPEN)
        opened = sum(1 for b in self._breakers.values() if b.state == BreakerState.OPEN)

        system_health = "healthy"
        if opened > 0:
            system_health = "degraded"
        if opened > total * 0.5 and total > 0:
            system_health = "critical"

        return {
            "system_health": system_health,
            "total_breakers": total,
            "closed": closed,
            "half_open": half_open,
            "open": opened,
            "agents_degraded": [
                b.agent for b in self._breakers.values() if b.state != BreakerState.CLOSED
            ],
        }

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema de breakers."""
        return {
            "breakers_count": len(self._breakers),
            "health": self.health_summary(),
            "metrics": {**self._metrics},
        }

    def cleanup_stale_data(self) -> int:
        """Limpia rate_calls y events antiguos para prevenir memory leaks.

        Returns:
            Número de entradas eliminadas.
        """
        now = time.time()
        cutoff_rate = now - 60.0  # rate_calls: solo ultimo minuto
        cutoff_events = now - 3600.0  # events: solo ultima hora
        cleaned = 0

        for breaker in self._breakers.values():
            old_rate = len(breaker.rate_calls)
            breaker.rate_calls = [t for t in breaker.rate_calls if t > cutoff_rate]
            cleaned += old_rate - len(breaker.rate_calls)

            old_events = len(breaker.events)
            breaker.events = [e for e in breaker.events if e.timestamp > cutoff_events]
            cleaned += old_events - len(breaker.events)

        return cleaned

    def to_prometheus(self) -> str:
        """Exporta métricas en formato Prometheus."""
        lines = [
            "# HELP antigravity_breaker_state Estado del circuit breaker (0=closed, 1=half_open, 2=open)",
            "# TYPE antigravity_breaker_state gauge",
        ]
        state_map = {BreakerState.CLOSED: 0, BreakerState.HALF_OPEN: 1, BreakerState.OPEN: 2}
        for breaker in self._breakers.values():
            state_val = state_map.get(breaker.state, 0)
            lines.append(f'antigravity_breaker_state{{agent="{breaker.agent}"}} {state_val}')
        lines.extend(
            [
                "# HELP antigravity_breaker_failures_total Total de fallos por agente",
                "# TYPE antigravity_breaker_failures_total counter",
            ]
        )
        for breaker in self._breakers.values():
            lines.append(
                f'antigravity_breaker_failures_total{{agent="{breaker.agent}"}} {breaker.total_failures}'
            )
        return "\n".join(lines) + "\n"

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _get_or_create(self, agent: str) -> AgentBreaker:
        """Obtiene o crea un breaker."""
        if agent not in self._breakers:
            self._breakers[agent] = AgentBreaker(agent=agent)
        return self._breakers[agent]

    def _check_state_transition(self, breaker: AgentBreaker) -> None:
        """Verifica si un breaker OPEN debe pasar a HALF_OPEN."""
        if breaker.state != BreakerState.OPEN:
            return
        elapsed = time.time() - breaker.last_state_change
        if elapsed >= breaker.recovery_timeout:
            self._transition(breaker, BreakerState.HALF_OPEN, "recovery timeout elapsed")

    def _transition(self, breaker: AgentBreaker, new_state: BreakerState, reason: str) -> None:
        """Ejecuta una transición de estado."""
        old_state = breaker.state
        if old_state == new_state:
            return

        breaker.state = new_state
        breaker.last_state_change = time.time()
        breaker.success_count = 0

        if new_state == BreakerState.OPEN:
            breaker.opened_count += 1
            self._metrics["circuits_opened"] += 1
        elif new_state == BreakerState.CLOSED and old_state != BreakerState.CLOSED:
            self._metrics["circuits_closed"] += 1

        self._add_event(
            breaker,
            BreakerEventType.STATE_CHANGE,
            f"{old_state.value} → {new_state.value}: {reason}",
        )

        logger.info(
            "Circuit breaker %s: %s → %s (%s)",
            breaker.agent,
            old_state.value,
            new_state.value,
            reason,
        )

    def _add_event(
        self,
        breaker: AgentBreaker,
        event_type: BreakerEventType,
        detail: str = "",
    ) -> None:
        """Agrega un evento al historial del breaker."""
        event = BreakerEvent(
            agent=breaker.agent,
            event_type=event_type,
            state_before=breaker.state,
            state_after=breaker.state,
            detail=detail,
        )
        breaker.events.append(event)
        if len(breaker.events) > MAX_EVENT_HISTORY:
            breaker.events = breaker.events[-MAX_EVENT_HISTORY:]


# ============================================================
# Singleton
# ============================================================
_instance: CircuitBreakerManager | None = None


def get_circuit_breaker(bus: Any = None) -> CircuitBreakerManager:
    """Obtiene o crea el circuit breaker manager global."""
    global _instance
    if _instance is None:
        _instance = CircuitBreakerManager(bus=bus)
    return _instance
