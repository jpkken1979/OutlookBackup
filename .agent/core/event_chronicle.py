"""
Event Chronicle — Event Sourcing + Time Travel.

Registro causal completo de toda actividad del ecosistema:
  - Cada acción se registra como un evento inmutable
  - Cadena causal: cada evento referencia su causa
  - Reconstrucción de estado en cualquier punto temporal
  - Análisis de cadena causal (root cause analysis)
  - Replay de escenarios "what-if"
  - Snapshots periódicos para reconstrucción eficiente

Concepts:
  - ChronicleEntry: Evento inmutable con causa y efecto
  - CausalChain: Secuencia de eventos conectados causalmente
  - Snapshot: Estado del sistema en un punto temporal
  - Timeline: Vista filtrada de eventos en rango temporal

Usage:
    chronicle = EventChronicle(bus=bus)

    # Registrar evento
    entry = chronicle.record(
        event_type="agent_execution",
        agent="explorer",
        action="analyze_code",
        data={"file": "main.py"},
        caused_by="request-123",  # ID del evento que causó este
    )

    # Trazar cadena causal
    chain = chronicle.trace_cause(entry.entry_id)
    print(chain)  # [root_event → event_2 → ... → entry]

    # Timeline
    events = chronicle.query(
        since=time.time() - 3600,
        agent="explorer",
        event_type="agent_execution",
    )

    # Snapshot
    snapshot = chronicle.create_snapshot()
    state = chronicle.get_state_at(timestamp)
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.event_chronicle")

# ============================================================
# Constantes
# ============================================================
MAX_CHRONICLE_SIZE = 10000  # Máximo de entradas en memoria
MAX_SNAPSHOTS = 50  # Máximo de snapshots
MAX_CHAIN_DEPTH = 100  # Máxima profundidad de cadena causal
SNAPSHOT_INTERVAL = 500  # Crear snapshot cada N eventos


# ============================================================
# Enums
# ============================================================
class ChronicleEventType(str, Enum):
    """Tipos de evento del chronicle."""

    AGENT_EXECUTION = "agent_execution"
    AGENT_RESULT = "agent_result"
    TASK_CREATED = "task_created"
    TASK_COMPLETED = "task_completed"
    TASK_FAILED = "task_failed"
    ROUTE_DECISION = "route_decision"
    AUCTION_STARTED = "auction_started"
    AUCTION_COMPLETED = "auction_completed"
    CONSENSUS_PROPOSAL = "consensus_proposal"
    CONSENSUS_RESOLVED = "consensus_resolved"
    SWARM_STARTED = "swarm_started"
    SWARM_COMPLETED = "swarm_completed"
    REPUTATION_CHANGE = "reputation_change"
    TOPOLOGY_CHANGE = "topology_change"
    ERROR = "error"
    SYSTEM_EVENT = "system_event"
    USER_ACTION = "user_action"
    ESCALATION = "escalation"


class SnapshotType(str, Enum):
    """Tipos de snapshot."""

    AUTO = "auto"  # Generado automáticamente
    MANUAL = "manual"  # Generado manualmente
    CHECKPOINT = "checkpoint"  # Punto de control explícito


# ============================================================
# Modelos
# ============================================================
@dataclass
class ChronicleEntry:
    """Evento inmutable del chronicle."""

    entry_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type: ChronicleEventType = ChronicleEventType.SYSTEM_EVENT
    agent: str | None = None
    action: str = ""
    data: dict[str, Any] = field(default_factory=dict)
    caused_by: str | None = None  # ID del evento causa
    correlation_id: str | None = None  # ID de correlación (agrupa eventos relacionados)
    severity: str = "info"
    timestamp: float = field(default_factory=time.time)
    sequence: int = 0  # Número de secuencia global

    def to_dict(self) -> dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "event_type": self.event_type.value,
            "agent": self.agent,
            "action": self.action,
            "data": self.data,
            "caused_by": self.caused_by,
            "correlation_id": self.correlation_id,
            "severity": self.severity,
            "timestamp": self.timestamp,
            "sequence": self.sequence,
            "age_seconds": round(time.time() - self.timestamp, 1),
        }


@dataclass
class CausalChain:
    """Cadena causal de eventos."""

    chain_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    entries: list[ChronicleEntry] = field(default_factory=list)
    root_cause: str | None = None
    final_effect: str | None = None
    depth: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "chain_id": self.chain_id,
            "root_cause": self.root_cause,
            "final_effect": self.final_effect,
            "depth": self.depth,
            "entries": [e.to_dict() for e in self.entries],
            "agents_involved": list({e.agent for e in self.entries if e.agent}),
            "event_types": list({e.event_type.value for e in self.entries}),
        }


@dataclass
class Snapshot:
    """Estado del sistema en un punto temporal."""

    snapshot_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    snapshot_type: SnapshotType = SnapshotType.AUTO
    timestamp: float = field(default_factory=time.time)
    sequence_at: int = 0
    state: dict[str, Any] = field(default_factory=dict)
    label: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "snapshot_id": self.snapshot_id,
            "snapshot_type": self.snapshot_type.value,
            "timestamp": self.timestamp,
            "sequence_at": self.sequence_at,
            "label": self.label,
            "state_keys": list(self.state.keys()),
            "age_seconds": round(time.time() - self.timestamp, 1),
        }


# ============================================================
# Event Chronicle
# ============================================================
class EventChronicle:
    """
    Event sourcing con trazabilidad causal.
    Cada evento es inmutable y referencia su causa.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus
        self._entries: list[ChronicleEntry] = []
        self._index_by_id: dict[str, ChronicleEntry] = {}
        self._index_by_agent: dict[str, list[str]] = defaultdict(list)
        self._index_by_type: dict[str, list[str]] = defaultdict(list)
        self._index_by_correlation: dict[str, list[str]] = defaultdict(list)
        self._snapshots: list[Snapshot] = []
        self._sequence_counter = 0

        # Métricas
        self._metrics = {
            "entries_recorded": 0,
            "chains_traced": 0,
            "snapshots_created": 0,
            "queries_executed": 0,
            "replays_executed": 0,
        }

    # --------------------------------------------------------
    # Record
    # --------------------------------------------------------
    def record(
        self,
        event_type: str,
        action: str = "",
        agent: str | None = None,
        data: dict[str, Any] | None = None,
        caused_by: str | None = None,
        correlation_id: str | None = None,
        severity: str = "info",
    ) -> ChronicleEntry:
        """
        Registra un evento inmutable en el chronicle.

        Args:
            event_type: Tipo de evento.
            action: Acción descriptiva.
            agent: Agente involucrado.
            data: Datos del evento.
            caused_by: ID del evento que causó este.
            correlation_id: ID para agrupar eventos relacionados.
            severity: Severidad (info, warning, error, critical).

        Returns:
            ChronicleEntry inmutable.
        """
        self._sequence_counter += 1

        # Auto-generar correlation_id si hay causa
        if caused_by and not correlation_id:
            cause_entry = self._index_by_id.get(caused_by)
            if cause_entry:
                correlation_id = cause_entry.correlation_id or caused_by

        entry = ChronicleEntry(
            event_type=ChronicleEventType(event_type),
            agent=agent,
            action=action,
            data=data or {},
            caused_by=caused_by,
            correlation_id=correlation_id,
            severity=severity,
            sequence=self._sequence_counter,
        )

        # Almacenar
        self._entries.append(entry)
        self._index_by_id[entry.entry_id] = entry

        if agent:
            self._index_by_agent[agent].append(entry.entry_id)
        self._index_by_type[event_type].append(entry.entry_id)
        if correlation_id:
            self._index_by_correlation[correlation_id].append(entry.entry_id)

        # Limitar tamaño
        if len(self._entries) > MAX_CHRONICLE_SIZE:
            self._compact()

        # Auto-snapshot
        if self._sequence_counter % SNAPSHOT_INTERVAL == 0:
            self._auto_snapshot()

        self._metrics["entries_recorded"] += 1

        return entry

    # --------------------------------------------------------
    # Causal Tracing
    # --------------------------------------------------------
    def trace_cause(self, entry_id: str) -> CausalChain:
        """
        Traza la cadena causal hacia atrás desde un evento.

        Returns:
            CausalChain con todos los eventos en la cadena.
        """
        chain_entries: list[ChronicleEntry] = []
        current_id: str | None = entry_id
        visited: set[str] = set()

        while current_id and len(chain_entries) < MAX_CHAIN_DEPTH:
            if current_id in visited:
                break  # Ciclo detectado
            visited.add(current_id)

            entry = self._index_by_id.get(current_id)
            if not entry:
                break

            chain_entries.append(entry)
            current_id = entry.caused_by

        # Invertir para tener root cause primero
        chain_entries.reverse()

        chain = CausalChain(
            entries=chain_entries,
            root_cause=chain_entries[0].entry_id if chain_entries else None,
            final_effect=chain_entries[-1].entry_id if chain_entries else None,
            depth=len(chain_entries),
        )

        self._metrics["chains_traced"] += 1
        return chain

    def trace_effects(self, entry_id: str) -> list[dict[str, Any]]:
        """
        Traza los efectos directos de un evento (hijos causales).

        Returns:
            Lista de eventos causados por el evento dado.
        """
        effects = [e.to_dict() for e in self._entries if e.caused_by == entry_id]
        return effects

    def get_correlation_group(self, correlation_id: str) -> list[dict[str, Any]]:
        """Obtiene todos los eventos con el mismo correlation_id."""
        entry_ids = self._index_by_correlation.get(correlation_id, [])
        entries = [
            self._index_by_id[eid].to_dict() for eid in entry_ids if eid in self._index_by_id
        ]
        return sorted(entries, key=lambda e: e["sequence"])

    # --------------------------------------------------------
    # Query / Timeline
    # --------------------------------------------------------
    def query(
        self,
        since: float | None = None,
        until: float | None = None,
        agent: str | None = None,
        event_type: str | None = None,
        severity: str | None = None,
        correlation_id: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """
        Consulta eventos con filtros.

        Args:
            since: Timestamp mínimo.
            until: Timestamp máximo.
            agent: Filtrar por agente.
            event_type: Filtrar por tipo.
            severity: Filtrar por severidad.
            correlation_id: Filtrar por correlación.
            limit: Máximo de resultados.

        Returns:
            Lista de eventos ordenados por timestamp descendente.
        """
        self._metrics["queries_executed"] += 1

        # Start from index if possible
        if agent and not event_type and not correlation_id:
            entry_ids = self._index_by_agent.get(agent, [])
            entries = [self._index_by_id[eid] for eid in entry_ids if eid in self._index_by_id]
        elif event_type and not agent and not correlation_id:
            entry_ids = self._index_by_type.get(event_type, [])
            entries = [self._index_by_id[eid] for eid in entry_ids if eid in self._index_by_id]
        elif correlation_id:
            entry_ids = self._index_by_correlation.get(correlation_id, [])
            entries = [self._index_by_id[eid] for eid in entry_ids if eid in self._index_by_id]
        else:
            entries = list(self._entries)

        # Apply remaining filters
        if since:
            entries = [e for e in entries if e.timestamp >= since]
        if until:
            entries = [e for e in entries if e.timestamp <= until]
        if agent and (event_type or correlation_id):
            entries = [e for e in entries if e.agent == agent]
        if event_type and (agent or correlation_id):
            entries = [e for e in entries if e.event_type.value == event_type]
        if severity:
            entries = [e for e in entries if e.severity == severity]

        # Últimos N, descendente
        return [e.to_dict() for e in entries[-limit:]][::-1]

    # --------------------------------------------------------
    # Snapshots
    # --------------------------------------------------------
    def create_snapshot(
        self,
        state: dict[str, Any] | None = None,
        label: str = "",
        snapshot_type: SnapshotType = SnapshotType.MANUAL,
    ) -> Snapshot:
        """
        Crea un snapshot del estado actual.

        Args:
            state: Estado del sistema a capturar.
            label: Etiqueta descriptiva.
            snapshot_type: Tipo de snapshot.

        Returns:
            Snapshot creado.
        """
        snapshot = Snapshot(
            snapshot_type=snapshot_type,
            sequence_at=self._sequence_counter,
            state=state or self._build_auto_state(),
            label=label,
        )

        self._snapshots.append(snapshot)
        if len(self._snapshots) > MAX_SNAPSHOTS:
            self._snapshots = self._snapshots[-MAX_SNAPSHOTS:]

        self._metrics["snapshots_created"] += 1
        return snapshot

    def get_state_at(self, timestamp: float) -> dict[str, Any]:
        """
        Reconstruye el estado del sistema en un punto temporal.

        Busca el snapshot más cercano anterior al timestamp
        y reproduce los eventos posteriores.
        """
        # Encontrar snapshot más cercano
        best_snapshot = None
        for snap in self._snapshots:
            if snap.timestamp <= timestamp:
                best_snapshot = snap

        # Eventos entre snapshot y timestamp
        start_seq = best_snapshot.sequence_at if best_snapshot else 0
        replay_entries = [
            e for e in self._entries if e.sequence > start_seq and e.timestamp <= timestamp
        ]

        state = dict(best_snapshot.state) if best_snapshot else {}

        # Reconstruir estado aplicando eventos
        state["reconstructed_at"] = timestamp
        state["snapshot_base"] = best_snapshot.snapshot_id if best_snapshot else None
        state["events_replayed"] = len(replay_entries)
        state["agents_active"] = list({e.agent for e in replay_entries if e.agent})
        state["event_types_seen"] = list({e.event_type.value for e in replay_entries})
        state["error_count"] = sum(1 for e in replay_entries if e.severity == "error")

        # Agrupar por agente
        agent_activity: dict[str, list[str]] = defaultdict(list)
        for e in replay_entries:
            if e.agent:
                agent_activity[e.agent].append(e.action or e.event_type.value)
        state["agent_activity"] = dict(agent_activity)

        self._metrics["replays_executed"] += 1
        return state

    def list_snapshots(self) -> list[dict[str, Any]]:
        """Lista todos los snapshots."""
        return [s.to_dict() for s in self._snapshots]

    # --------------------------------------------------------
    # Root Cause Analysis
    # --------------------------------------------------------
    def root_cause_analysis(self, error_entry_id: str) -> dict[str, Any]:
        """
        Análisis de causa raíz para un evento de error.

        Traza la cadena causal, identifica el punto de fallo original,
        y genera un resumen.
        """
        chain = self.trace_cause(error_entry_id)
        error_entry = self._index_by_id.get(error_entry_id)

        if not error_entry:
            return {"error": "Entry not found", "entry_id": error_entry_id}

        # Encontrar el primer error en la cadena
        first_error = None
        for entry in chain.entries:
            if entry.severity in ("error", "critical"):
                first_error = entry
                break

        # Encontrar patrones
        agents_involved = list({e.agent for e in chain.entries if e.agent})
        event_types = [e.event_type.value for e in chain.entries]

        return {
            "error_event": error_entry.to_dict(),
            "root_cause": first_error.to_dict() if first_error else None,
            "causal_chain": chain.to_dict(),
            "agents_involved": agents_involved,
            "event_flow": event_types,
            "chain_depth": chain.depth,
            "time_span_seconds": (
                chain.entries[-1].timestamp - chain.entries[0].timestamp
                if len(chain.entries) > 1
                else 0
            ),
        }

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del chronicle."""
        return {
            "entries_count": len(self._entries),
            "max_entries": MAX_CHRONICLE_SIZE,
            "sequence_counter": self._sequence_counter,
            "snapshots_count": len(self._snapshots),
            "indexed_agents": len(self._index_by_agent),
            "indexed_types": len(self._index_by_type),
            "indexed_correlations": len(self._index_by_correlation),
            "metrics": {**self._metrics},
        }

    def get_entry(self, entry_id: str) -> dict[str, Any] | None:
        """Obtiene una entrada por ID."""
        entry = self._index_by_id.get(entry_id)
        return entry.to_dict() if entry else None

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _auto_snapshot(self) -> None:
        """Crea un snapshot automático."""
        self.create_snapshot(
            label=f"auto-seq-{self._sequence_counter}",
            snapshot_type=SnapshotType.AUTO,
        )

    def _build_auto_state(self) -> dict[str, Any]:
        """Construye estado automático para snapshot."""
        recent = self._entries[-100:] if self._entries else []
        return {
            "total_entries": len(self._entries),
            "sequence": self._sequence_counter,
            "agents_seen": list(self._index_by_agent.keys()),
            "event_types_seen": list(self._index_by_type.keys()),
            "recent_agents": list({e.agent for e in recent if e.agent}),
            "recent_errors": sum(1 for e in recent if e.severity == "error"),
        }

    def _compact(self) -> None:
        """Compacta el chronicle eliminando entradas antiguas."""
        # Crear snapshot antes de compactar
        self.create_snapshot(
            label=f"pre-compact-{self._sequence_counter}",
            snapshot_type=SnapshotType.AUTO,
        )

        # Mantener solo las últimas entradas
        keep = self._entries[-MAX_CHRONICLE_SIZE:]
        removed_ids = {e.entry_id for e in self._entries} - {e.entry_id for e in keep}

        self._entries = keep

        # Limpiar índices
        for eid in removed_ids:
            self._index_by_id.pop(eid, None)

        # Rebuild secondary indices
        self._index_by_agent = defaultdict(list)
        self._index_by_type = defaultdict(list)
        self._index_by_correlation = defaultdict(list)

        for entry in self._entries:
            if entry.agent:
                self._index_by_agent[entry.agent].append(entry.entry_id)
            self._index_by_type[entry.event_type.value].append(entry.entry_id)
            if entry.correlation_id:
                self._index_by_correlation[entry.correlation_id].append(entry.entry_id)

        logger.debug("Chronicle compacted: removed %d entries", len(removed_ids))


# ============================================================
# Singleton
# ============================================================
_instance: EventChronicle | None = None


def get_event_chronicle(bus: Any = None) -> EventChronicle:
    """Obtiene o crea el chronicle global."""
    global _instance
    if _instance is None:
        _instance = EventChronicle(bus=bus)
    return _instance
