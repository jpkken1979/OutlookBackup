"""
AnomalyDetector — Detección de anomalías en comportamiento de agentes.

Monitorea métricas de ejecución de agentes en tiempo real:
  - Duración de tareas (z-score vs media histórica)
  - Tasa de errores (threshold configurable)
  - Patrones de uso anómalos (ráfagas, inactividad)

Cuando detecta una anomalía, genera una alerta con severidad
y la publica en el message bus para que el sistema reaccione.

Ejemplo de uso:
    detector = AnomalyDetector(bus)
    detector.record_execution("explorer", duration=5.2, success=True)
    detector.record_execution("explorer", duration=120.5, success=True)  # → anomalía
    alerts = detector.get_alerts()

Integración:
  - AgentDaemon registra cada ejecución automáticamente
  - Gateway expone alertas via REST y WebSocket
  - Nexus muestra panel de anomalías en tiempo real
"""

import logging
import math
import time
from collections import deque
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.anomaly_detector")


# ============================================================
# Configuración
# ============================================================
DEFAULT_WINDOW_SIZE = 50  # Ventana de muestras para estadísticas
Z_SCORE_THRESHOLD = 2.5  # Desviaciones estándar para anomalía de duración
ERROR_RATE_THRESHOLD = 0.4  # 40% de errores en la ventana → anomalía
BURST_THRESHOLD = 10  # Más de N ejecuciones en 60s → ráfaga
BURST_WINDOW_SECONDS = 60.0
INACTIVITY_THRESHOLD = 300.0  # 5 minutos sin ejecutar → inactividad (si estaba activo)
MAX_ALERTS = 500  # Máximo de alertas almacenadas


# ============================================================
# Data models
# ============================================================
class AlertSeverity(Enum):
    """Severidad de una alerta."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class AnomalyType(Enum):
    """Tipos de anomalía detectados."""

    SLOW_EXECUTION = "slow_execution"
    FAST_EXECUTION = "fast_execution"
    HIGH_ERROR_RATE = "high_error_rate"
    EXECUTION_BURST = "execution_burst"
    AGENT_INACTIVITY = "agent_inactivity"
    CONSECUTIVE_FAILURES = "consecutive_failures"


@dataclass
class ExecutionSample:
    """Una muestra de ejecución de un agente."""

    agent: str
    duration_seconds: float
    success: bool
    timestamp: float = field(default_factory=time.time)
    task_id: str | None = None


@dataclass
class Alert:
    """Alerta de anomalía detectada."""

    alert_id: str
    agent: str
    anomaly_type: AnomalyType
    severity: AlertSeverity
    message: str
    details: dict[str, Any]
    timestamp: float = field(default_factory=time.time)
    acknowledged: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "agent": self.agent,
            "anomaly_type": self.anomaly_type.value,
            "severity": self.severity.value,
            "message": self.message,
            "details": self.details,
            "timestamp": self.timestamp,
            "acknowledged": self.acknowledged,
        }


@dataclass
class AgentProfile:
    """Perfil estadístico de un agente para detección de anomalías."""

    agent: str
    samples: deque = field(default_factory=lambda: deque(maxlen=DEFAULT_WINDOW_SIZE))
    total_executions: int = 0
    total_successes: int = 0
    total_failures: int = 0
    consecutive_failures: int = 0
    last_execution_ts: float | None = None

    @property
    def durations(self) -> list[float]:
        """Lista de duraciones en la ventana actual."""
        return [s.duration_seconds for s in self.samples]

    @property
    def mean_duration(self) -> float:
        """Media de la duración."""
        d = self.durations
        return sum(d) / len(d) if d else 0.0

    @property
    def stddev_duration(self) -> float:
        """Desviación estándar de la duración."""
        d = self.durations
        if len(d) < 2:
            return 0.0
        mean = self.mean_duration
        variance = sum((x - mean) ** 2 for x in d) / (len(d) - 1)
        return math.sqrt(variance)

    @property
    def error_rate(self) -> float:
        """Tasa de errores en la ventana actual."""
        if not self.samples:
            return 0.0
        failures = sum(1 for s in self.samples if not s.success)
        return failures / len(self.samples)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "total_executions": self.total_executions,
            "total_successes": self.total_successes,
            "total_failures": self.total_failures,
            "consecutive_failures": self.consecutive_failures,
            "window_size": len(self.samples),
            "mean_duration": round(self.mean_duration, 3),
            "stddev_duration": round(self.stddev_duration, 3),
            "error_rate": round(self.error_rate, 3),
            "last_execution_ts": self.last_execution_ts,
        }


# ============================================================
# AnomalyDetector
# ============================================================
class AnomalyDetector:
    """
    Detector de anomalías en comportamiento de agentes.

    Monitorea métricas en tiempo real y genera alertas cuando
    detecta desviaciones significativas del comportamiento normal.
    """

    def __init__(
        self,
        bus: Any | None = None,
        z_threshold: float = Z_SCORE_THRESHOLD,
        error_rate_threshold: float = ERROR_RATE_THRESHOLD,
        window_size: int = DEFAULT_WINDOW_SIZE,
    ) -> None:
        self._bus = bus
        self._z_threshold = z_threshold
        self._error_rate_threshold = error_rate_threshold
        self._window_size = window_size

        self._profiles: dict[str, AgentProfile] = {}
        self._alerts: deque[Alert] = deque(maxlen=MAX_ALERTS)
        self._alert_counter = 0

    # --------------------------------------------------------
    # Registrar ejecuciones
    # --------------------------------------------------------
    def record_execution(
        self,
        agent: str,
        duration_seconds: float,
        success: bool,
        task_id: str | None = None,
    ) -> list[Alert]:
        """
        Registra una ejecución de agente y detecta anomalías.

        Args:
            agent: Nombre del agente.
            duration_seconds: Duración de la ejecución.
            success: Si la ejecución fue exitosa.
            task_id: ID de la tarea (opcional).

        Returns:
            Lista de alertas generadas (puede estar vacía).
        """
        profile = self._get_or_create_profile(agent)
        now = time.time()

        sample = ExecutionSample(
            agent=agent,
            duration_seconds=duration_seconds,
            success=success,
            timestamp=now,
            task_id=task_id,
        )

        # Actualizar contadores
        profile.total_executions += 1
        if success:
            profile.total_successes += 1
            profile.consecutive_failures = 0
        else:
            profile.total_failures += 1
            profile.consecutive_failures += 1

        # Detectar anomalías ANTES de agregar la muestra (comparar con histórico)
        new_alerts = self._detect_anomalies(profile, sample)

        # Agregar muestra al historial
        profile.samples.append(sample)
        profile.last_execution_ts = now

        # Publicar alertas
        for alert in new_alerts:
            self._alerts.append(alert)
            self._publish_alert(alert)

        return new_alerts

    def _detect_anomalies(
        self,
        profile: AgentProfile,
        sample: ExecutionSample,
    ) -> list[Alert]:
        """Detecta anomalías comparando la muestra con el perfil."""
        alerts: list[Alert] = []

        # Solo analizar si hay suficiente historial
        if len(profile.samples) >= 5:
            # 1. Anomalía de duración (z-score)
            alert = self._check_duration_anomaly(profile, sample)
            if alert:
                alerts.append(alert)

            # 2. Tasa de errores alta
            alert = self._check_error_rate(profile, sample)
            if alert:
                alerts.append(alert)

            # 3. Ráfaga de ejecuciones
            alert = self._check_burst(profile, sample)
            if alert:
                alerts.append(alert)

        # 4. Fallos consecutivos (no requiere historial largo)
        if profile.consecutive_failures >= 3 and not sample.success:
            alerts.append(
                self._create_alert(
                    agent=sample.agent,
                    anomaly_type=AnomalyType.CONSECUTIVE_FAILURES,
                    severity=AlertSeverity.CRITICAL,
                    message=(
                        f"Agente '{sample.agent}' con {profile.consecutive_failures + 1} "
                        f"fallos consecutivos"
                    ),
                    details={
                        "consecutive_failures": profile.consecutive_failures + 1,
                        "last_error_task_id": sample.task_id,
                    },
                )
            )

        return alerts

    def _check_duration_anomaly(
        self,
        profile: AgentProfile,
        sample: ExecutionSample,
    ) -> Alert | None:
        """Detecta si la duración es anómala via z-score."""
        mean = profile.mean_duration
        stddev = profile.stddev_duration

        if stddev == 0:
            return None

        z_score = (sample.duration_seconds - mean) / stddev

        if z_score > self._z_threshold:
            return self._create_alert(
                agent=sample.agent,
                anomaly_type=AnomalyType.SLOW_EXECUTION,
                severity=(
                    AlertSeverity.CRITICAL
                    if z_score > self._z_threshold * 2
                    else AlertSeverity.WARNING
                ),
                message=(
                    f"Agente '{sample.agent}' ejecución lenta: "
                    f"{sample.duration_seconds:.1f}s (media: {mean:.1f}s, z={z_score:.1f})"
                ),
                details={
                    "duration": round(sample.duration_seconds, 3),
                    "mean": round(mean, 3),
                    "stddev": round(stddev, 3),
                    "z_score": round(z_score, 2),
                    "task_id": sample.task_id,
                },
            )

        if z_score < -self._z_threshold and mean > 1.0:
            return self._create_alert(
                agent=sample.agent,
                anomaly_type=AnomalyType.FAST_EXECUTION,
                severity=AlertSeverity.INFO,
                message=(
                    f"Agente '{sample.agent}' ejecución inusualmente rápida: "
                    f"{sample.duration_seconds:.1f}s (media: {mean:.1f}s)"
                ),
                details={
                    "duration": round(sample.duration_seconds, 3),
                    "mean": round(mean, 3),
                    "z_score": round(z_score, 2),
                },
            )

        return None

    def _check_error_rate(
        self,
        profile: AgentProfile,
        sample: ExecutionSample,
    ) -> Alert | None:
        """Detecta si la tasa de errores supera el threshold."""
        if not sample.success and profile.error_rate >= self._error_rate_threshold:
            return self._create_alert(
                agent=sample.agent,
                anomaly_type=AnomalyType.HIGH_ERROR_RATE,
                severity=AlertSeverity.CRITICAL,
                message=(
                    f"Agente '{sample.agent}' con tasa de error alta: "
                    f"{profile.error_rate:.0%} (threshold: {self._error_rate_threshold:.0%})"
                ),
                details={
                    "error_rate": round(profile.error_rate, 3),
                    "threshold": self._error_rate_threshold,
                    "window_size": len(profile.samples),
                    "total_failures": profile.total_failures,
                },
            )
        return None

    def _check_burst(
        self,
        profile: AgentProfile,
        sample: ExecutionSample,
    ) -> Alert | None:
        """Detecta ráfagas de ejecución (demasiadas en poco tiempo)."""
        cutoff = sample.timestamp - BURST_WINDOW_SECONDS
        recent = sum(1 for s in profile.samples if s.timestamp > cutoff)

        if recent >= BURST_THRESHOLD:
            return self._create_alert(
                agent=sample.agent,
                anomaly_type=AnomalyType.EXECUTION_BURST,
                severity=AlertSeverity.WARNING,
                message=(
                    f"Agente '{sample.agent}' ráfaga detectada: "
                    f"{recent + 1} ejecuciones en {BURST_WINDOW_SECONDS:.0f}s"
                ),
                details={
                    "executions_in_window": recent + 1,
                    "window_seconds": BURST_WINDOW_SECONDS,
                    "threshold": BURST_THRESHOLD,
                },
            )
        return None

    # --------------------------------------------------------
    # Detección proactiva (llamar periódicamente)
    # --------------------------------------------------------
    def check_inactivity(self) -> list[Alert]:
        """
        Verifica inactividad de agentes que estaban activos.
        Llamar periódicamente (ej. cada 60s).

        Returns:
            Lista de alertas de inactividad.
        """
        alerts: list[Alert] = []
        now = time.time()

        for profile in self._profiles.values():
            if (
                profile.last_execution_ts is not None
                and profile.total_executions >= 5
                and (now - profile.last_execution_ts) > INACTIVITY_THRESHOLD
            ):
                alert = self._create_alert(
                    agent=profile.agent,
                    anomaly_type=AnomalyType.AGENT_INACTIVITY,
                    severity=AlertSeverity.INFO,
                    message=(
                        f"Agente '{profile.agent}' inactivo por "
                        f"{(now - profile.last_execution_ts):.0f}s"
                    ),
                    details={
                        "last_execution_ts": profile.last_execution_ts,
                        "inactive_seconds": round(now - profile.last_execution_ts, 1),
                        "total_executions": profile.total_executions,
                    },
                )
                alerts.append(alert)
                self._alerts.append(alert)
                self._publish_alert(alert)
                # Resetear para no volver a alertar
                profile.last_execution_ts = None

        return alerts

    # --------------------------------------------------------
    # Helpers
    # --------------------------------------------------------
    def _get_or_create_profile(self, agent: str) -> AgentProfile:
        """Obtiene o crea el perfil de un agente."""
        if agent not in self._profiles:
            self._profiles[agent] = AgentProfile(
                agent=agent,
                samples=deque(maxlen=self._window_size),
            )
        return self._profiles[agent]

    def _create_alert(
        self,
        agent: str,
        anomaly_type: AnomalyType,
        severity: AlertSeverity,
        message: str,
        details: dict[str, Any],
    ) -> Alert:
        """Crea una nueva alerta."""
        self._alert_counter += 1
        alert_id = f"alert-{self._alert_counter:06d}"
        return Alert(
            alert_id=alert_id,
            agent=agent,
            anomaly_type=anomaly_type,
            severity=severity,
            message=message,
            details=details,
        )

    def _publish_alert(self, alert: Alert) -> None:
        """Publica una alerta en el message bus (fire-and-forget)."""
        if self._bus is None:
            return
        try:
            import asyncio

            loop = asyncio.get_running_loop()
            loop.create_task(
                self._bus.publish(
                    "anomaly.alert",
                    alert.to_dict(),
                    from_agent="anomaly-detector",
                )
            )
        except RuntimeError:
            # No hay event loop (tests síncronos o shutdown)
            pass

    # --------------------------------------------------------
    # API pública
    # --------------------------------------------------------
    def get_alerts(
        self,
        agent: str | None = None,
        severity: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """
        Retorna alertas recientes.

        Args:
            agent: Filtrar por agente.
            severity: Filtrar por severidad.
            limit: Máximo de alertas.

        Returns:
            Lista de alertas como dicts.
        """
        alerts = list(self._alerts)

        if agent:
            alerts = [a for a in alerts if a.agent == agent]
        if severity:
            alerts = [a for a in alerts if a.severity.value == severity]

        # Más recientes primero
        alerts.sort(key=lambda a: a.timestamp, reverse=True)
        return [a.to_dict() for a in alerts[:limit]]

    def acknowledge_alert(self, alert_id: str) -> bool:
        """Marca una alerta como reconocida."""
        for alert in self._alerts:
            if alert.alert_id == alert_id:
                alert.acknowledged = True
                return True
        return False

    def get_agent_profile(self, agent: str) -> dict[str, Any] | None:
        """Retorna el perfil estadístico de un agente."""
        profile = self._profiles.get(agent)
        return profile.to_dict() if profile else None

    def get_all_profiles(self) -> list[dict[str, Any]]:
        """Retorna todos los perfiles de agentes."""
        return [p.to_dict() for p in self._profiles.values()]

    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del detector."""
        return {
            "monitored_agents": len(self._profiles),
            "total_alerts": len(self._alerts),
            "unacknowledged_alerts": sum(1 for a in self._alerts if not a.acknowledged),
            "alerts_by_severity": {
                sev.value: sum(1 for a in self._alerts if a.severity == sev)
                for sev in AlertSeverity
            },
            "alerts_by_type": {
                at.value: sum(1 for a in self._alerts if a.anomaly_type == at) for at in AnomalyType
            },
            "agent_profiles": {
                name: {
                    "executions": p.total_executions,
                    "error_rate": round(p.error_rate, 3),
                    "mean_duration": round(p.mean_duration, 3),
                }
                for name, p in self._profiles.items()
            },
        }
