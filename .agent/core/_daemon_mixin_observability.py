"""Mixin de observabilidad y diagnósticos para AgentDaemon.

Adaptadores para: EventChronicle (Sprint 6), CircuitBreaker (Sprint 7),
DashboardFeed (Sprint 9A), AlertEngine (Sprint 9A). Gestiona el monitoreo,
eventos, resiliencia y alertas del ecosistema.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DaemonObservabilityMixin:
    """Adaptadores de chronicle, circuit breaker, dashboard y alertas.

    Agrupa los subsistemas de observabilidad: registro de eventos,
    protección contra fallos en cascada, feed de dashboard y motor
    de alertas.
    """

    # Atributos inyectados por AgentDaemon en runtime.
    _metrics: dict[str, int]
    _event_chronicle: Any | None
    _circuit_breaker: Any | None
    _dashboard_feed: Any | None
    _alert_engine: Any | None

    # --------------------------------------------------------
    # EventChronicle (Sprint 6)
    # --------------------------------------------------------
    def chronicle_record(
        self,
        event_type: str,
        action: str = "",
        agent: str | None = None,
        data: dict[str, Any] | None = None,
        caused_by: str | None = None,
        correlation_id: str | None = None,
        severity: str = "info",
    ) -> dict[str, Any]:
        """Registra un evento en el chronicle."""
        if self._event_chronicle is None:
            raise RuntimeError("EventChronicle no inicializado")
        self._metrics["chronicle_entries"] += 1
        entry = self._event_chronicle.record(
            event_type,
            action,
            agent,
            data,
            caused_by,
            correlation_id,
            severity,
        )
        return entry.to_dict()

    def chronicle_trace_cause(self, entry_id: str) -> dict[str, Any]:
        """Traza la cadena causal de un evento."""
        if self._event_chronicle is None:
            return {"error": "EventChronicle no inicializado"}
        chain = self._event_chronicle.trace_cause(entry_id)
        return chain.to_dict()

    def chronicle_trace_effects(self, entry_id: str) -> list[dict[str, Any]]:
        """Traza los efectos de un evento."""
        if self._event_chronicle is None:
            return []
        return self._event_chronicle.trace_effects(entry_id)

    def chronicle_query(
        self,
        since: float | None = None,
        until: float | None = None,
        agent: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Consulta eventos del chronicle."""
        if self._event_chronicle is None:
            return []
        return self._event_chronicle.query(since, until, agent, event_type, severity, limit=limit)

    def chronicle_root_cause(self, entry_id: str) -> dict[str, Any]:
        """Análisis de causa raíz."""
        if self._event_chronicle is None:
            return {"error": "EventChronicle no inicializado"}
        return self._event_chronicle.root_cause_analysis(entry_id)

    def chronicle_create_snapshot(
        self,
        label: str = "",
        state: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Crea un snapshot manual."""
        if self._event_chronicle is None:
            return {"error": "EventChronicle no inicializado"}
        snapshot = self._event_chronicle.create_snapshot(state, label)
        return snapshot.to_dict()

    def chronicle_get_state_at(self, timestamp: float) -> dict[str, Any]:
        """Reconstruye estado en un punto temporal."""
        if self._event_chronicle is None:
            return {"error": "EventChronicle no inicializado"}
        return self._event_chronicle.get_state_at(timestamp)

    def chronicle_list_snapshots(self) -> list[dict[str, Any]]:
        """Lista snapshots del chronicle."""
        if self._event_chronicle is None:
            return []
        return self._event_chronicle.list_snapshots()

    def get_chronicle_stats(self) -> dict[str, Any]:
        """Estadísticas del chronicle."""
        if self._event_chronicle is None:
            return {"status": "disabled"}
        return self._event_chronicle.get_stats()

    # --------------------------------------------------------
    # CircuitBreaker (Sprint 7)
    # --------------------------------------------------------
    def breaker_can_execute(self, agent: str) -> bool:
        """Verifica si un agente puede ejecutarse (circuit breaker)."""
        if self._circuit_breaker is None:
            return True
        self._metrics["circuit_breaker_checks"] += 1
        return self._circuit_breaker.can_execute(agent)

    def breaker_record_success(self, agent: str) -> str:
        """Registra ejecución exitosa en el circuit breaker."""
        if self._circuit_breaker is None:
            return "disabled"
        return self._circuit_breaker.record_success(agent).value

    def breaker_record_failure(self, agent: str, error: str = "") -> str:
        """Registra fallo en el circuit breaker."""
        if self._circuit_breaker is None:
            return "disabled"
        return self._circuit_breaker.record_failure(agent, error).value

    def breaker_get_status(self, agent: str) -> dict[str, Any]:
        """Obtiene estado del circuit breaker para un agente."""
        if self._circuit_breaker is None:
            return {"status": "disabled"}
        return self._circuit_breaker.get_status(agent)

    def breaker_get_all(self) -> list[dict[str, Any]]:
        """Obtiene estado de todos los circuit breakers."""
        if self._circuit_breaker is None:
            return []
        return self._circuit_breaker.get_all_status()

    def breaker_get_open(self) -> list[dict[str, Any]]:
        """Obtiene circuitos abiertos (agentes bloqueados)."""
        if self._circuit_breaker is None:
            return []
        return self._circuit_breaker.get_open_circuits()

    def breaker_force_reset(self, agent: str) -> dict[str, Any]:
        """Fuerza reset del circuit breaker de un agente."""
        if self._circuit_breaker is None:
            return {"status": "disabled"}
        return self._circuit_breaker.force_reset(agent)

    def breaker_configure(
        self,
        agent: str,
        failure_threshold: int | None = None,
        recovery_timeout: float | None = None,
        max_concurrent: int | None = None,
        fallbacks: list[str] | None = None,
    ) -> dict[str, Any]:
        """Configura parámetros del circuit breaker para un agente."""
        if self._circuit_breaker is None:
            return {"status": "disabled"}
        return self._circuit_breaker.configure(
            agent,
            failure_threshold,
            recovery_timeout,
            max_concurrent,
            fallbacks=fallbacks,
        )

    def breaker_get_fallback(self, agent: str) -> str | None:
        """Obtiene el fallback configurado para un agente."""
        if self._circuit_breaker is None:
            return None
        return self._circuit_breaker.get_fallback(agent)

    def breaker_health(self) -> dict[str, Any]:
        """Resumen de salud de todos los circuit breakers."""
        if self._circuit_breaker is None:
            return {"status": "disabled"}
        return self._circuit_breaker.health_summary()

    def get_breaker_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema de circuit breakers."""
        if self._circuit_breaker is None:
            return {"status": "disabled"}
        return self._circuit_breaker.get_stats()

    # --------------------------------------------------------
    # Dashboard Feed (Sprint 9A)
    # --------------------------------------------------------
    def dashboard_snapshot(self) -> dict[str, Any]:
        """Obtiene snapshot actual del dashboard."""
        if self._dashboard_feed is None:
            return {"status": "disabled"}
        return self._dashboard_feed.get_snapshot()

    def dashboard_timeline(
        self,
        minutes: int = 30,
        category: str | None = None,
    ) -> list[dict[str, Any]]:
        """Obtiene timeline de eventos del dashboard."""
        if self._dashboard_feed is None:
            return []
        return self._dashboard_feed.get_timeline(minutes, category)

    def dashboard_add_entry(
        self,
        category: str,
        event: str,
        detail: str = "",
        severity: str = "info",
        agent: str = "",
    ) -> dict[str, Any]:
        """Agrega entrada al timeline del dashboard."""
        if self._dashboard_feed is None:
            return {"status": "disabled"}
        return self._dashboard_feed.add_timeline_entry(category, event, detail, severity, agent)

    def get_dashboard_stats(self) -> dict[str, Any]:
        """Estadísticas del feed de dashboard."""
        if self._dashboard_feed is None:
            return {"status": "disabled"}
        return self._dashboard_feed.get_stats()

    # --------------------------------------------------------
    # Alert Engine (Sprint 9A)
    # --------------------------------------------------------
    def alert_fire(self, rule_id: str, agent: str = "", detail: str = "") -> dict[str, Any] | None:
        """Dispara una alerta según una regla."""
        if self._alert_engine is None:
            return None
        self._metrics["alerts_fired"] += 1
        return self._alert_engine.fire(rule_id, agent, detail)

    def alert_resolve(self, rule_id: str, agent: str = "") -> list[dict[str, Any]]:
        """Resuelve alertas activas para una regla."""
        if self._alert_engine is None:
            return []
        return self._alert_engine.resolve(rule_id, agent)

    def alert_get_active(self, severity: str | None = None) -> list[dict[str, Any]]:
        """Obtiene alertas activas, opcionalmente filtradas por severidad."""
        if self._alert_engine is None:
            return []
        return self._alert_engine.get_active_alerts(severity)

    def get_alert_stats(self) -> dict[str, Any]:
        """Estadísticas del motor de alertas."""
        if self._alert_engine is None:
            return {"status": "disabled"}
        return self._alert_engine.get_stats()
