"""
Alert Engine — sistema de alertas inteligentes.

Monitorea el ecosistema y genera alertas basadas en reglas:
  - Circuit breaker abierto → alerta crítica
  - ELO cayendo rápido → alerta de warning
  - Genoma mutando excesivamente → alerta de info
  - SLA violation → alerta de error
  - Agent offline → alerta de warning

Cada alerta tiene:
  - Severity: info, warning, error, critical
  - Rule: la regla que la generó
  - Cooldown: evita spam (misma alerta no se repite en X segundos)
  - Auto-resolve: se resuelve si la condición deja de cumplirse

Usage:
    engine = AlertEngine(bus=bus)

    # Registrar reglas
    engine.add_rule("circuit_open", severity="critical",
                    cooldown=60, description="Circuit breaker abierto")

    # Disparar alerta
    engine.fire("circuit_open", agent="explorer", detail="3 failures")

    # Resolver
    engine.resolve("circuit_open", agent="explorer")

    # Consultar alertas activas
    active = engine.get_active_alerts()
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.alert_engine")

# ============================================================
# Constantes
# ============================================================
DEFAULT_COOLDOWN = 60  # Segundos entre alertas duplicadas
MAX_ACTIVE_ALERTS = 200  # Máximo de alertas activas
MAX_ALERT_HISTORY = 1000  # Historial
SEVERITY_LEVELS = {
    "info": 0,
    "warning": 1,
    "error": 2,
    "critical": 3,
}


# ============================================================
# Modelos
# ============================================================
@dataclass
class AlertRule:
    """Regla que define cuándo se genera una alerta."""

    rule_id: str
    severity: str = "warning"
    description: str = ""
    cooldown: float = DEFAULT_COOLDOWN
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "description": self.description,
            "cooldown": self.cooldown,
            "enabled": self.enabled,
        }


@dataclass
class Alert:
    """Una alerta activa o resuelta."""

    alert_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    rule_id: str = ""
    severity: str = "warning"
    agent: str = ""
    detail: str = ""
    resolved: bool = False
    fired_at: float = field(default_factory=time.time)
    resolved_at: float = 0.0

    @property
    def duration(self) -> float:
        end = self.resolved_at if self.resolved else time.time()
        return end - self.fired_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "rule_id": self.rule_id,
            "severity": self.severity,
            "agent": self.agent,
            "detail": self.detail,
            "resolved": self.resolved,
            "fired_at": self.fired_at,
            "resolved_at": self.resolved_at,
            "duration_seconds": round(self.duration, 1),
        }


# ============================================================
# Alert Engine
# ============================================================
class AlertEngine:
    """
    Motor de alertas inteligentes con reglas, cooldown y auto-resolve.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus

        # Reglas registradas
        self._rules: dict[str, AlertRule] = {}

        # Alertas activas (no resueltas)
        self._active: dict[str, Alert] = {}  # alert_id -> Alert

        # Historial completo
        self._history: list[Alert] = []

        # Cooldown tracking: (rule_id, agent) -> last_fired_at
        self._cooldowns: dict[tuple[str, str], float] = {}

        # Callbacks por severity
        self._callbacks: dict[str, list[Any]] = defaultdict(list)

        # Métricas
        self._metrics = {
            "alerts_fired": 0,
            "alerts_resolved": 0,
            "alerts_suppressed": 0,
            "rules_registered": 0,
        }

        # Pre-registrar reglas del ecosistema
        self._register_default_rules()

    # --------------------------------------------------------
    # Rules
    # --------------------------------------------------------
    def add_rule(
        self,
        rule_id: str,
        severity: str = "warning",
        description: str = "",
        cooldown: float = DEFAULT_COOLDOWN,
    ) -> dict[str, Any]:
        """Registra una regla de alerta."""
        rule = AlertRule(
            rule_id=rule_id,
            severity=severity,
            description=description,
            cooldown=cooldown,
        )
        self._rules[rule_id] = rule
        self._metrics["rules_registered"] += 1
        return rule.to_dict()

    def remove_rule(self, rule_id: str) -> bool:
        """Elimina una regla."""
        if rule_id in self._rules:
            del self._rules[rule_id]
            return True
        return False

    def get_rules(self) -> list[dict[str, Any]]:
        """Lista todas las reglas."""
        return [r.to_dict() for r in self._rules.values()]

    # --------------------------------------------------------
    # Fire & Resolve
    # --------------------------------------------------------
    def fire(
        self,
        rule_id: str,
        agent: str = "",
        detail: str = "",
    ) -> dict[str, Any] | None:
        """
        Dispara una alerta según una regla.
        Respeta cooldown — retorna None si suprimida.
        """
        rule = self._rules.get(rule_id)
        if not rule or not rule.enabled:
            return None

        # Cooldown check
        cooldown_key = (rule_id, agent)
        now = time.time()
        last_fired = self._cooldowns.get(cooldown_key, 0.0)
        if now - last_fired < rule.cooldown:
            self._metrics["alerts_suppressed"] += 1
            return None

        alert = Alert(
            rule_id=rule_id,
            severity=rule.severity,
            agent=agent,
            detail=detail,
        )

        self._active[alert.alert_id] = alert
        self._history.append(alert)
        self._cooldowns[cooldown_key] = now

        # Limitar historial
        if len(self._history) > MAX_ALERT_HISTORY:
            self._history = self._history[-MAX_ALERT_HISTORY:]

        # Limitar activas (resolver las más antiguas)
        while len(self._active) > MAX_ACTIVE_ALERTS:
            oldest_id = min(self._active, key=lambda k: self._active[k].fired_at)
            self._active[oldest_id].resolved = True
            self._active[oldest_id].resolved_at = now
            del self._active[oldest_id]

        self._metrics["alerts_fired"] += 1

        logger.warning(
            "ALERT [%s] %s: %s (agent=%s)",
            rule.severity.upper(),
            rule_id,
            detail,
            agent,
        )

        return alert.to_dict()

    def resolve(
        self,
        rule_id: str,
        agent: str = "",
    ) -> list[dict[str, Any]]:
        """
        Resuelve alertas de un rule_id + agent.
        Retorna alertas resueltas.
        """
        resolved = []
        now = time.time()

        to_remove = []
        for alert_id, alert in self._active.items():
            if alert.rule_id == rule_id and (not agent or alert.agent == agent):
                alert.resolved = True
                alert.resolved_at = now
                to_remove.append(alert_id)
                resolved.append(alert.to_dict())
                self._metrics["alerts_resolved"] += 1

        for aid in to_remove:
            del self._active[aid]

        return resolved

    def resolve_by_id(self, alert_id: str) -> dict[str, Any] | None:
        """Resuelve una alerta por ID."""
        alert = self._active.get(alert_id)
        if not alert:
            return None

        alert.resolved = True
        alert.resolved_at = time.time()
        del self._active[alert_id]
        self._metrics["alerts_resolved"] += 1
        return alert.to_dict()

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_active_alerts(
        self,
        severity: str | None = None,
        agent: str | None = None,
    ) -> list[dict[str, Any]]:
        """Alertas activas (no resueltas)."""
        alerts = list(self._active.values())
        if severity:
            alerts = [a for a in alerts if a.severity == severity]
        if agent:
            alerts = [a for a in alerts if a.agent == agent]
        return [
            a.to_dict()
            for a in sorted(
                alerts,
                key=lambda a: SEVERITY_LEVELS.get(a.severity, 0),
                reverse=True,
            )
        ]

    def get_alert_history(
        self,
        rule_id: str | None = None,
        agent: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de alertas."""
        alerts = self._history
        if rule_id:
            alerts = [a for a in alerts if a.rule_id == rule_id]
        if agent:
            alerts = [a for a in alerts if a.agent == agent]
        return [a.to_dict() for a in alerts[-limit:]][::-1]

    def get_alert_counts(self) -> dict[str, int]:
        """Conteo de alertas por severity."""
        counts: dict[str, int] = {"info": 0, "warning": 0, "error": 0, "critical": 0}
        for alert in self._active.values():
            counts[alert.severity] = counts.get(alert.severity, 0) + 1
        return counts

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del engine."""
        return {
            "rules_count": len(self._rules),
            "active_alerts": len(self._active),
            "history_size": len(self._history),
            "alert_counts": self.get_alert_counts(),
            "metrics": {**self._metrics},
        }

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _register_default_rules(self) -> None:
        """Registra reglas por defecto del ecosistema."""
        defaults = [
            ("circuit_open", "critical", "Circuit breaker abierto", 60),
            ("sla_violation", "error", "Violación de SLA/contrato", 120),
            ("agent_offline", "warning", "Agente no responde", 300),
            ("elo_drop", "warning", "Caída brusca de ELO", 180),
            ("genome_divergence", "info", "Alta mutación en genoma", 300),
            ("knowledge_stale", "info", "Conocimiento sin actualizar", 600),
            ("high_error_rate", "error", "Tasa de error elevada", 60),
            ("consensus_deadlock", "warning", "Consenso sin resolución", 120),
            ("swarm_timeout", "warning", "Swarm excedió timeout", 60),
            ("topology_instability", "warning", "Red de agentes inestable", 180),
        ]
        for rule_id, severity, desc, cooldown in defaults:
            self.add_rule(rule_id, severity, desc, cooldown)


# ============================================================
# Singleton
# ============================================================
_instance: AlertEngine | None = None


def get_alert_engine(bus: Any = None) -> AlertEngine:
    """Obtiene o crea el alert engine global."""
    global _instance
    if _instance is None:
        _instance = AlertEngine(bus=bus)
    return _instance
