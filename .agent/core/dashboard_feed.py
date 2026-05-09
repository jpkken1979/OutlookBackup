"""
Dashboard Feed — agregador unificado de datos para UI.

Recopila datos de los 15+ módulos del ecosistema y los presenta
en un feed unificado para Nexus Desktop y otros dashboards.

Secciones del feed:
  - overview: resumen general del ecosistema
  - agents: estado de agentes + reputation + genome
  - tasks: tareas activas + historial reciente
  - evolution: genoma + fitness + generación actual
  - knowledge: destilación + expertos + transferencias
  - arena: batallas + rankings + ELO
  - health: circuit breakers + SLA + contracts
  - topology: red de agentes + adaptaciones
  - events: stream de eventos recientes

Usage:
    feed = DashboardFeed(bus=bus)
    snapshot = feed.get_snapshot()
    section = feed.get_section("evolution")
    timeline = feed.get_timeline(minutes=30)
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.dashboard_feed")

# ============================================================
# Constantes
# ============================================================
MAX_TIMELINE_ENTRIES = 500
SNAPSHOT_CACHE_TTL = 2.0  # Cache de snapshot por 2 segundos
SECTIONS = [
    "overview",
    "agents",
    "tasks",
    "evolution",
    "knowledge",
    "arena",
    "health",
    "topology",
    "events",
]


# ============================================================
# Modelos
# ============================================================
@dataclass
class TimelineEntry:
    """Entrada en el timeline."""

    category: str = "system"
    event: str = ""
    detail: str = ""
    severity: str = "info"  # info, warning, error, critical
    agent: str = ""
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "event": self.event,
            "detail": self.detail,
            "severity": self.severity,
            "agent": self.agent,
            "timestamp": self.timestamp,
        }


# ============================================================
# Dashboard Feed
# ============================================================
class DashboardFeed:
    """
    Feed unificado que agrega datos de todos los módulos.
    Diseñado para alimentar dashboards en tiempo real.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus

        # Timeline global
        self._timeline: list[TimelineEntry] = []

        # Cache de snapshot
        self._snapshot_cache: dict[str, Any] | None = None
        self._snapshot_ts: float = 0.0

        # Datos registrados por sección
        self._section_data: dict[str, dict[str, Any]] = {s: {} for s in SECTIONS}

        # Contadores
        self._metrics = {
            "snapshots_served": 0,
            "timeline_entries": 0,
            "section_updates": 0,
            "cache_hits": 0,
        }

    # --------------------------------------------------------
    # Timeline
    # --------------------------------------------------------
    def add_timeline_entry(
        self,
        category: str,
        event: str,
        detail: str = "",
        severity: str = "info",
        agent: str = "",
    ) -> dict[str, Any]:
        """Agrega entrada al timeline."""
        entry = TimelineEntry(
            category=category,
            event=event,
            detail=detail,
            severity=severity,
            agent=agent,
        )
        self._timeline.append(entry)
        if len(self._timeline) > MAX_TIMELINE_ENTRIES:
            self._timeline = self._timeline[-MAX_TIMELINE_ENTRIES:]

        self._metrics["timeline_entries"] += 1
        self._invalidate_cache()

        return entry.to_dict()

    def get_timeline(
        self,
        minutes: int = 30,
        category: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Timeline filtrado."""
        cutoff = time.time() - (minutes * 60)
        entries = self._timeline

        entries = [e for e in entries if e.timestamp >= cutoff]
        if category:
            entries = [e for e in entries if e.category == category]
        if severity:
            entries = [e for e in entries if e.severity == severity]

        return [e.to_dict() for e in entries[-limit:]][::-1]

    # --------------------------------------------------------
    # Section Data
    # --------------------------------------------------------
    def update_section(self, section: str, data: dict[str, Any]) -> bool:
        """Actualiza datos de una sección."""
        if section not in self._section_data:
            return False

        self._section_data[section].update(data)
        self._metrics["section_updates"] += 1
        self._invalidate_cache()
        return True

    def get_section(self, section: str) -> dict[str, Any]:
        """Datos de una sección."""
        return {**self._section_data.get(section, {})}

    # --------------------------------------------------------
    # Snapshot
    # --------------------------------------------------------
    def get_snapshot(self) -> dict[str, Any]:
        """
        Snapshot completo del ecosistema.
        Cachea por SNAPSHOT_CACHE_TTL segundos.
        """
        now = time.time()
        if self._snapshot_cache and (now - self._snapshot_ts) < SNAPSHOT_CACHE_TTL:
            self._metrics["cache_hits"] += 1
            return self._snapshot_cache

        snapshot = {
            "timestamp": now,
            "sections": {s: {**d} for s, d in self._section_data.items()},
            "timeline_recent": self.get_timeline(minutes=5, limit=20),
            "alerts": self._get_active_alerts(),
            "summary": self._build_summary(),
        }

        self._snapshot_cache = snapshot
        self._snapshot_ts = now
        self._metrics["snapshots_served"] += 1

        return snapshot

    # --------------------------------------------------------
    # Alerts
    # --------------------------------------------------------
    def _get_active_alerts(self) -> list[dict[str, Any]]:
        """Alertas activas del timeline reciente."""
        cutoff = time.time() - 300  # últimos 5 minutos
        alerts = [
            e.to_dict()
            for e in self._timeline
            if e.timestamp >= cutoff and e.severity in ("warning", "error", "critical")
        ]
        return alerts[-10:]

    # --------------------------------------------------------
    # Summary
    # --------------------------------------------------------
    def _build_summary(self) -> dict[str, Any]:
        """Construye resumen del estado."""
        recent = [e for e in self._timeline if e.timestamp > time.time() - 300]
        return {
            "recent_events": len(recent),
            "warnings": sum(1 for e in recent if e.severity == "warning"),
            "errors": sum(1 for e in recent if e.severity in ("error", "critical")),
            "categories_active": len({e.category for e in recent}),
        }

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_categories(self) -> list[str]:
        """Categorías con actividad."""
        return sorted({e.category for e in self._timeline})

    def search_timeline(self, query: str, limit: int = 50) -> list[dict[str, Any]]:
        """Busca en el timeline."""
        q = query.lower()
        matches = [
            e
            for e in self._timeline
            if q in e.event.lower() or q in e.detail.lower() or q in e.agent.lower()
        ]
        return [e.to_dict() for e in matches[-limit:]][::-1]

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del feed."""
        return {
            "timeline_size": len(self._timeline),
            "sections": list(self._section_data.keys()),
            "cache_valid": (
                self._snapshot_cache is not None
                and (time.time() - self._snapshot_ts) < SNAPSHOT_CACHE_TTL
            ),
            "metrics": {**self._metrics},
        }

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _invalidate_cache(self) -> None:
        """Invalida cache del snapshot."""
        self._snapshot_cache = None


# ============================================================
# Singleton
# ============================================================
_instance: DashboardFeed | None = None


def get_dashboard_feed(bus: Any = None) -> DashboardFeed:
    """Obtiene o crea el dashboard feed global."""
    global _instance
    if _instance is None:
        _instance = DashboardFeed(bus=bus)
    return _instance
