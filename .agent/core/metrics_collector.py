# mypy: ignore-errors
#!/usr/bin/env python3
"""
Metrics Collector - Sistema de métricas en tiempo real

Recolecta y almacena métricas del ecosistema para:
- Monitoreo de rendimiento
- Tracking de uso de agentes
- Análisis de patrones
- Reportes históricos
"""

import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """Un punto de métrica."""

    name: str
    value: float
    timestamp: str
    tags: dict = field(default_factory=dict)


@dataclass
class AgentMetrics:
    """Métricas de un agente."""

    name: str
    invocations: int = 0
    successes: int = 0
    failures: int = 0
    total_duration_ms: int = 0
    last_invocation: str | None = None

    @property
    def success_rate(self) -> float:
        if self.invocations == 0:
            return 0.0
        return self.successes / self.invocations

    @property
    def avg_duration_ms(self) -> float:
        if self.invocations == 0:
            return 0.0
        return self.total_duration_ms / self.invocations


@dataclass
class SystemMetrics:
    """Métricas del sistema."""

    timestamp: str
    health_score: float = 0.0
    total_agents: int = 0
    active_agents: int = 0
    memory_entries: int = 0
    session_count: int = 0
    error_count: int = 0


class MetricsCollector:
    """
    Recolector y almacenador de métricas.

    Funcionalidades:
    - Recolección automática de métricas
    - Almacenamiento histórico
    - Agregaciones (hora, día, semana)
    - Exportación
    """

    METRICS_PATH = Path(".agent/metrics")
    CURRENT_FILE = "current.json"
    HISTORY_FILE = "history.json"
    AGENTS_FILE = "agents.json"

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.metrics_path = self.project_root / self.METRICS_PATH
        self.metrics_path.mkdir(parents=True, exist_ok=True)

        self._agent_metrics: dict[str, AgentMetrics] = {}
        self._history: list[SystemMetrics] = []
        self._load_state()

    def _load_state(self):
        """Carga estado desde disco."""
        # Cargar métricas de agentes
        agents_file = self.metrics_path / self.AGENTS_FILE
        if agents_file.exists():
            try:
                data = json.loads(agents_file.read_text(encoding="utf-8"))
                for name, metrics in data.items():
                    self._agent_metrics[name] = AgentMetrics(
                        name=name,
                        invocations=metrics.get("invocations", 0),
                        successes=metrics.get("successes", 0),
                        failures=metrics.get("failures", 0),
                        total_duration_ms=metrics.get("total_duration_ms", 0),
                        last_invocation=metrics.get("last_invocation"),
                    )
            except Exception as e:
                logger.debug("Error loading metrics data: %s", e)

        # Cargar historial
        history_file = self.metrics_path / self.HISTORY_FILE
        if history_file.exists():
            try:
                data = json.loads(history_file.read_text(encoding="utf-8"))
                for entry in data[-1000:]:  # Últimas 1000
                    self._history.append(
                        SystemMetrics(
                            timestamp=entry["timestamp"],
                            health_score=entry.get("health_score", 0),
                            total_agents=entry.get("total_agents", 0),
                            active_agents=entry.get("active_agents", 0),
                            memory_entries=entry.get("memory_entries", 0),
                            session_count=entry.get("session_count", 0),
                            error_count=entry.get("error_count", 0),
                        )
                    )
            except Exception as e:
                logger.debug("Error loading metrics data: %s", e)

    def _save_state(self):
        """Guarda estado a disco."""
        # Guardar métricas de agentes
        agents_file = self.metrics_path / self.AGENTS_FILE
        agents_data = {
            name: {
                "invocations": m.invocations,
                "successes": m.successes,
                "failures": m.failures,
                "total_duration_ms": m.total_duration_ms,
                "last_invocation": m.last_invocation,
                "success_rate": m.success_rate,
                "avg_duration_ms": m.avg_duration_ms,
            }
            for name, m in self._agent_metrics.items()
        }
        agents_file.write_text(json.dumps(agents_data, indent=2))

        # Guardar historial
        history_file = self.metrics_path / self.HISTORY_FILE
        history_data = [
            {
                "timestamp": h.timestamp,
                "health_score": h.health_score,
                "total_agents": h.total_agents,
                "active_agents": h.active_agents,
                "memory_entries": h.memory_entries,
                "session_count": h.session_count,
                "error_count": h.error_count,
            }
            for h in self._history[-1000:]
        ]
        history_file.write_text(json.dumps(history_data, indent=2))

    # ==================== TRACKING ====================

    def track_agent_invocation(self, agent_name: str, success: bool, duration_ms: int):
        """Registra invocación de agente."""
        if agent_name not in self._agent_metrics:
            self._agent_metrics[agent_name] = AgentMetrics(name=agent_name)

        metrics = self._agent_metrics[agent_name]
        metrics.invocations += 1
        metrics.total_duration_ms += duration_ms
        metrics.last_invocation = datetime.now().isoformat()

        if success:
            metrics.successes += 1
        else:
            metrics.failures += 1

        self._save_state()

    def track_system_state(
        self,
        health_score: float = 0.0,
        total_agents: int = 0,
        memory_entries: int = 0,
        error_count: int = 0,
    ):
        """Registra estado del sistema."""
        active = sum(1 for m in self._agent_metrics.values() if m.invocations > 0)

        metrics = SystemMetrics(
            timestamp=datetime.now().isoformat(),
            health_score=health_score,
            total_agents=total_agents,
            active_agents=active,
            memory_entries=memory_entries,
            session_count=len(self._history) + 1,
            error_count=error_count,
        )

        self._history.append(metrics)
        self._save_state()

    def track_error(self, error_type: str, message: str):
        """Registra un error."""
        errors_file = self.metrics_path / "errors.json"

        errors = []
        if errors_file.exists():
            try:
                errors = json.loads(errors_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                pass

        errors.append(
            {"timestamp": datetime.now().isoformat(), "type": error_type, "message": message[:500]}
        )

        # Mantener últimos 100 errores
        errors_file.write_text(json.dumps(errors[-100:], indent=2))

    # ==================== CONSULTAS ====================

    def get_agent_metrics(self, agent_name: str = None) -> dict:
        """Obtiene métricas de agentes."""
        if agent_name:
            if agent_name in self._agent_metrics:
                m = self._agent_metrics[agent_name]
                return {
                    "name": m.name,
                    "invocations": m.invocations,
                    "success_rate": m.success_rate,
                    "avg_duration_ms": m.avg_duration_ms,
                    "last_invocation": m.last_invocation,
                }
            return {}

        return {
            name: {
                "invocations": m.invocations,
                "success_rate": m.success_rate,
                "avg_duration_ms": m.avg_duration_ms,
            }
            for name, m in self._agent_metrics.items()
        }

    def get_top_agents(self, limit: int = 10) -> list[dict]:
        """Obtiene agentes más usados."""
        sorted_agents = sorted(
            self._agent_metrics.values(), key=lambda m: m.invocations, reverse=True
        )

        return [
            {"name": m.name, "invocations": m.invocations, "success_rate": m.success_rate}
            for m in sorted_agents[:limit]
        ]

    def get_system_history(self, hours: int = 24) -> list[dict]:
        """Obtiene historial del sistema."""
        cutoff = datetime.now() - timedelta(hours=hours)
        cutoff_str = cutoff.isoformat()

        return [
            {
                "timestamp": h.timestamp,
                "health_score": h.health_score,
                "active_agents": h.active_agents,
                "memory_entries": h.memory_entries,
            }
            for h in self._history
            if h.timestamp >= cutoff_str
        ]

    def get_summary(self) -> dict:
        """Obtiene resumen de métricas."""
        total_invocations = sum(m.invocations for m in self._agent_metrics.values())
        total_successes = sum(m.successes for m in self._agent_metrics.values())
        sum(m.failures for m in self._agent_metrics.values())

        return {
            "timestamp": datetime.now().isoformat(),
            "agents": {
                "tracked": len(self._agent_metrics),
                "total_invocations": total_invocations,
                "success_rate": total_successes / total_invocations if total_invocations > 0 else 0,
                "top_5": self.get_top_agents(5),
            },
            "system": {
                "history_points": len(self._history),
                "latest_health": self._history[-1].health_score if self._history else 0,
            },
        }

    def export_report(self, format: str = "json") -> str:
        """Exporta reporte completo."""
        report = {
            "generated_at": datetime.now().isoformat(),
            "summary": self.get_summary(),
            "agent_metrics": self.get_agent_metrics(),
            "recent_history": self.get_system_history(24),
        }

        if format == "json":
            return json.dumps(report, indent=2)
        elif format == "markdown":
            lines = [
                "# Antigravity Metrics Report",
                f"Generated: {report['generated_at']}",
                "",
                "## Summary",
                f"- Tracked agents: {report['summary']['agents']['tracked']}",
                f"- Total invocations: {report['summary']['agents']['total_invocations']}",
                f"- Success rate: {report['summary']['agents']['success_rate']:.1%}",
                "",
                "## Top Agents",
            ]
            for agent in report["summary"]["agents"]["top_5"]:
                lines.append(
                    f"- {agent['name']}: {agent['invocations']} invocations ({agent['success_rate']:.1%})"
                )

            return "\n".join(lines)

        return json.dumps(report)


# Singleton
_collector: MetricsCollector | None = None


def get_metrics_collector(project_root: str = ".") -> MetricsCollector:
    """Obtiene instancia singleton."""
    global _collector
    if _collector is None:
        _collector = MetricsCollector(project_root)
    return _collector


def track_agent(agent_name: str, success: bool, duration_ms: int):
    """Shortcut para tracking de agente."""
    get_metrics_collector().track_agent_invocation(agent_name, success, duration_ms)


if __name__ == "__main__":
    # Test
    collector = MetricsCollector()

    # Simular uso
    collector.track_agent_invocation("explorer", True, 150)
    collector.track_agent_invocation("explorer", True, 200)
    collector.track_agent_invocation("security-auditor", True, 500)
    collector.track_agent_invocation("security-auditor", False, 100)

    collector.track_system_state(health_score=81.0, total_agents=92, memory_entries=5)

    print(collector.export_report("markdown"))
