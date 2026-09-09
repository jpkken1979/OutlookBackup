"""
WorkflowEngine - Motor de ejecución de grafos inspirado en LangGraph.

Implementa un motor ligero de workflows como DAGs (Directed Acyclic Graphs)
con soporte para:
  - Nodos: funciones sync/async que transforman estado
  - Edges condicionales: routing dinámico basado en el estado
  - Ejecución paralela de ramas independientes
  - Checkpointing: estado persistido entre pasos
  - Streaming de eventos de ejecución
  - Human-in-the-loop: pausa y reanudación con input humano

NO depende de la librería LangGraph — es un motor propio del ecosistema
Antigravity que sigue los mismos patrones de diseño.

Usage:
    from core.workflow_engine import WorkflowEngine, StateGraph

    # Definir nodos
    async def analyze(state):
        state["analysis"] = "..."
        return state

    async def decide(state):
        if state["complexity"] == "high":
            return "planner"
        return "executor"

    # Construir grafo
    graph = StateGraph("code-review")
    graph.add_node("analyze", analyze)
    graph.add_node("planner", plan_fn)
    graph.add_node("executor", exec_fn)
    graph.set_entry_point("analyze")
    graph.add_conditional_edge("analyze", decide)
    graph.add_edge("planner", "executor")
    graph.set_finish_point("executor")

    # Ejecutar
    engine = WorkflowEngine()
    result = await engine.execute(graph, {"code": "..."})
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
import uuid
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

from core.workflow_contracts import GateResult, redact_text, redact_value

logger = logging.getLogger("antigravity.workflow_engine")


# ============================================================
# Tipos y constantes
# ============================================================
NodeFn = Callable[[dict[str, Any]], dict[str, Any] | Awaitable[dict[str, Any]]]
RouterFn = Callable[[dict[str, Any]], str | Awaitable[str]]

END = "__end__"
START = "__start__"

MAX_STEPS = 100  # Protección contra loops infinitos


class WorkflowStatus(Enum):
    """Estado de un workflow en ejecución."""

    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"  # Human-in-the-loop
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class NodeType(Enum):
    """Tipo de nodo en el grafo."""

    FUNCTION = "function"
    AGENT = "agent"  # Ejecuta un agente del ecosistema
    SUBGRAPH = "subgraph"  # Ejecuta otro grafo


# ============================================================
# Eventos de streaming
# ============================================================
class EventType(Enum):
    """Tipos de eventos emitidos durante ejecución."""

    WORKFLOW_START = "workflow_start"
    WORKFLOW_END = "workflow_end"
    NODE_START = "node_start"
    NODE_END = "node_end"
    EDGE_TRAVERSED = "edge_traversed"
    STATE_UPDATE = "state_update"
    CHECKPOINT = "checkpoint"
    ERROR = "error"
    PAUSED = "paused"
    RESUMED = "resumed"
    CANCELLED = "cancelled"


@dataclass
class WorkflowEvent:
    """Evento emitido durante la ejecución de un workflow."""

    event_type: EventType
    workflow_id: str
    node: str | None = None
    data: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type.value,
            "workflow_id": self.workflow_id,
            "node": self.node,
            "data": self.data,
            "timestamp": self.timestamp,
        }


# ============================================================
# Nodo del grafo
# ============================================================
@dataclass
class GraphNode:
    """Nodo dentro de un StateGraph."""

    name: str
    fn: NodeFn
    node_type: NodeType = NodeType.FUNCTION
    metadata: dict[str, Any] = field(default_factory=dict)
    interrupt_before: bool = False  # Pausa antes de ejecutar (HITL)


# ============================================================
# Edge del grafo
# ============================================================
@dataclass
class GraphEdge:
    """Arista entre nodos."""

    source: str
    target: str | None = None  # None si es condicional
    router: RouterFn | None = None  # Función que decide el siguiente nodo
    condition_map: dict[str, str] | None = None  # Mapa de resultado → nodo


# ============================================================
# StateGraph - Definición del grafo
# ============================================================
class StateGraph:
    """
    Grafo de estados que define un workflow.

    Cada nodo es una función que recibe y retorna un dict de estado.
    Las edges definen la transición entre nodos.
    """

    def __init__(
        self,
        name: str,
        description: str = "",
        *,
        version: int = 1,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        if not isinstance(version, int) or isinstance(version, bool) or version < 1:
            raise ValueError("La versión del grafo debe ser un entero positivo")
        self.name = name
        self.description = description
        self.version = version
        self.metadata = metadata or {}
        self._nodes: dict[str, GraphNode] = {}
        self._edges: list[GraphEdge] = []
        self._entry_point: str | None = None
        self._finish_points: set[str] = set()
        self._created_at: float = time.time()

    def add_node(
        self,
        name: str,
        fn: NodeFn,
        node_type: NodeType = NodeType.FUNCTION,
        metadata: dict[str, Any] | None = None,
        interrupt_before: bool = False,
    ) -> StateGraph:
        """Agrega un nodo al grafo."""
        if name in self._nodes:
            raise ValueError(f"Nodo '{name}' ya existe en el grafo")
        self._nodes[name] = GraphNode(
            name=name,
            fn=fn,
            node_type=node_type,
            metadata=metadata or {},
            interrupt_before=interrupt_before,
        )
        return self  # Fluent API

    def add_edge(self, source: str, target: str) -> StateGraph:
        """Agrega una edge directa entre dos nodos."""
        self._validate_node(source)
        if target != END:
            self._validate_node(target)
        self._edges.append(GraphEdge(source=source, target=target))
        return self

    def add_conditional_edge(
        self,
        source: str,
        router: RouterFn,
        condition_map: dict[str, str] | None = None,
    ) -> StateGraph:
        """Agrega una edge condicional que usa un router para elegir destino."""
        self._validate_node(source)
        self._edges.append(
            GraphEdge(
                source=source,
                router=router,
                condition_map=condition_map,
            )
        )
        return self

    def set_entry_point(self, name: str) -> StateGraph:
        """Define el nodo de entrada del grafo."""
        self._validate_node(name)
        self._entry_point = name
        return self

    def set_finish_point(self, name: str) -> StateGraph:
        """Define un nodo de finalización."""
        self._validate_node(name)
        self._finish_points.add(name)
        return self

    def _validate_node(self, name: str) -> None:
        if name not in self._nodes:
            raise ValueError(f"Nodo '{name}' no existe en el grafo '{self.name}'")

    def get_next_nodes(self, current: str) -> list[GraphEdge]:
        """Retorna las edges que salen de un nodo."""
        return [e for e in self._edges if e.source == current]

    def validate(self) -> list[str]:
        """Valida la integridad del grafo. Retorna lista de errores."""
        errors: list[str] = []
        if not self._entry_point:
            errors.append("No se definió entry_point")
        if not self._finish_points:
            errors.append("No se definió finish_point")
        if not self._nodes:
            errors.append("El grafo no tiene nodos")

        # Verificar que todas las edges referencian nodos válidos
        for edge in self._edges:
            if edge.source not in self._nodes:
                errors.append(f"Edge referencia nodo inexistente: '{edge.source}'")
            if edge.target and edge.target != END and edge.target not in self._nodes:
                errors.append(f"Edge referencia nodo destino inexistente: '{edge.target}'")

        # Verificar alcanzabilidad desde entry_point
        if self._entry_point:
            reachable = self._get_reachable_nodes(self._entry_point)
            for name in self._nodes:
                if name not in reachable and name != self._entry_point:
                    errors.append(f"Nodo '{name}' no es alcanzable desde entry_point")

        return errors

    def _edge_targets(self, edge: GraphEdge) -> list[str]:
        """Devuelve los nodos destino candidatos de un edge.

        Args:
            edge: Edge del workflow a inspeccionar.

        Returns:
            Lista de nombres de nodos alcanzables desde este edge (excluye END).
        """
        targets: list[str] = []
        if edge.target and edge.target != END:
            targets.append(edge.target)
        if edge.condition_map:
            targets.extend(t for t in edge.condition_map.values() if t != END)
        # Router sin condition_map: puede retornar cualquier nodo
        if edge.router is not None and edge.condition_map is None:
            targets.extend(self._nodes)
        return targets

    def _get_reachable_nodes(self, start: str) -> set[str]:
        """BFS para encontrar nodos alcanzables."""
        visited: set[str] = set()
        queue = [start]
        while queue:
            current = queue.pop(0)
            if current in visited:
                continue
            visited.add(current)
            for edge in self.get_next_nodes(current):
                queue.extend(t for t in self._edge_targets(edge) if t not in visited)
        return visited

    def to_dict(self) -> dict[str, Any]:
        """Serializa el grafo (sin funciones)."""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "metadata": redact_value(self.metadata),
            "entry_point": self._entry_point,
            "finish_points": list(self._finish_points),
            "nodes": [
                {
                    "name": n.name,
                    "type": n.node_type.value,
                    "metadata": n.metadata,
                    "interrupt_before": n.interrupt_before,
                }
                for n in self._nodes.values()
            ],
            "edges": [
                {
                    "source": e.source,
                    "target": e.target,
                    "conditional": e.router is not None,
                    "condition_map": e.condition_map,
                }
                for e in self._edges
            ],
            "created_at": self._created_at,
        }


# ============================================================
# Checkpoint - Estado persistido
# ============================================================
@dataclass
class Checkpoint:
    """Estado persistido de un workflow en ejecución."""

    workflow_id: str
    graph_name: str
    current_node: str
    state: dict[str, Any]
    step: int
    status: WorkflowStatus
    graph_version: int = 1
    events: list[dict[str, Any]] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    error: str | None = None
    human_input: dict[str, Any] | None = None  # Para HITL

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow_id": self.workflow_id,
            "graph_name": self.graph_name,
            "graph_version": self.graph_version,
            "current_node": self.current_node,
            "state": self.state,
            "step": self.step,
            "status": self.status.value,
            "events_count": len(self.events),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "error": self.error,
        }


# ============================================================
# WorkflowEngine - Motor de ejecución
# ============================================================
class WorkflowEngine:
    """
    Motor de ejecución de workflows basados en grafos.

    Ejecuta StateGraphs paso a paso, con:
    - Checkpointing automático entre pasos
    - Streaming de eventos
    - Soporte para human-in-the-loop
    - Protección contra loops infinitos
    - Ejecución con timeout por nodo
    """

    def __init__(
        self,
        bus: Any = None,
        checkpoint_dir: Path | None = None,
        node_timeout: float = 120.0,
    ) -> None:
        self._bus = bus
        self._checkpoint_dir = checkpoint_dir or Path.home() / ".antigravity" / "workflows"
        self._checkpoint_dir.mkdir(parents=True, exist_ok=True)
        self._node_timeout = node_timeout

        # Registros
        self._graphs: dict[str, StateGraph] = {}
        self._checkpoints: dict[str, Checkpoint] = {}
        self._event_listeners: list[Callable[[WorkflowEvent], Any]] = []

        # Métricas
        self._metrics = {
            "workflows_started": 0,
            "workflows_completed": 0,
            "workflows_failed": 0,
            "nodes_executed": 0,
            "total_execution_time": 0.0,
        }

    # --------------------------------------------------------
    # Registro de grafos
    # --------------------------------------------------------
    def register_graph(self, graph: StateGraph) -> None:
        """Registra un grafo para ejecución."""
        errors = graph.validate()
        if errors:
            raise ValueError(f"Grafo '{graph.name}' inválido: {'; '.join(errors)}")
        self._graphs[graph.name] = graph
        logger.info("Grafo '%s' registrado (%d nodos)", graph.name, len(graph._nodes))

    def get_graph(self, name: str) -> StateGraph | None:
        """Retorna un grafo registrado."""
        return self._graphs.get(name)

    def list_graphs(self) -> list[dict[str, Any]]:
        """Lista grafos registrados."""
        return [g.to_dict() for g in self._graphs.values()]

    # --------------------------------------------------------
    # Ejecución
    # --------------------------------------------------------
    def _check_idempotent_replay(
        self, workflow_id: str, graph: StateGraph
    ) -> dict[str, Any] | None:
        """Busca un checkpoint existente para reusar via idempotency key.

        Args:
            workflow_id: Idempotency key provisto por el llamador.
            graph: Grafo contra el que se ejecutaria el workflow.

        Returns:
            El resultado cacheado si el workflow_id ya corrio contra el mismo
            grafo, o None si no hay nada que reusar.

        Raises:
            ValueError: si el workflow_id existente pertenece a otro grafo.
        """
        existing = self._checkpoints.get(workflow_id) or self._load_checkpoint(workflow_id)
        if existing is None:
            return None
        if existing.graph_name != graph.name:
            raise ValueError("El idempotency key ya pertenece a otro grafo")
        return self._checkpoint_result(existing, replayed=True)

    @staticmethod
    def _init_or_resume_checkpoint(
        wf_id: str,
        graph: StateGraph,
        state: dict[str, Any],
        resume_checkpoint: Checkpoint | None,
    ) -> tuple[Checkpoint, str | None, int, bool]:
        """Construye un checkpoint nuevo o retoma uno existente.

        Args:
            wf_id: Id efectivo del workflow.
            graph: Grafo resuelto a ejecutar.
            state: Estado inicial (usado solo si se crea un checkpoint nuevo).
            resume_checkpoint: Checkpoint a retomar, si el llamado es un resume.

        Returns:
            Tupla (checkpoint, current_node, step, resuming).

        Raises:
            ValueError: si el checkpoint a retomar es de otra version del grafo.
        """
        if resume_checkpoint is not None:
            checkpoint = resume_checkpoint
            if checkpoint.graph_version != graph.version:
                raise ValueError("La versión del workflow cambió; inicia una ejecución nueva")
            checkpoint.status = WorkflowStatus.RUNNING
            checkpoint.error = None
            return checkpoint, checkpoint.current_node, checkpoint.step, True
        checkpoint = Checkpoint(
            workflow_id=wf_id,
            graph_name=graph.name,
            graph_version=graph.version,
            current_node=graph._entry_point or "",
            state=state,
            step=0,
            status=WorkflowStatus.RUNNING,
        )
        return checkpoint, graph._entry_point, 0, False

    async def _maybe_pause_before_node(
        self,
        node: GraphNode,
        checkpoint: Checkpoint,
        state: dict[str, Any],
        wf_id: str,
        graph: StateGraph,
        current_node: str,
    ) -> dict[str, Any] | None:
        """Pausa el workflow antes de un nodo human-in-the-loop, si corresponde.

        No pausa si ya hay human_input disponible (viene de `resume()`).

        Returns:
            El resultado del checkpoint si se pauso, o None para continuar.
        """
        has_human_input = checkpoint.human_input is not None or "__human_input__" in state
        if not (node.interrupt_before and not has_human_input):
            return None
        checkpoint.status = WorkflowStatus.PAUSED
        checkpoint.current_node = current_node
        await self._emit(
            WorkflowEvent(
                event_type=EventType.PAUSED,
                workflow_id=wf_id,
                node=current_node,
                data={
                    "reason": "interrupt_before",
                    "state_keys": sorted(state),
                    "verdict": self._state_verdict(state),
                    "next_action": self._state_next_action(state),
                    "graph_version": graph.version,
                },
            )
        )
        self._save_checkpoint(checkpoint)
        return self._checkpoint_result(checkpoint)

    async def _run_node_step(
        self,
        node: GraphNode,
        state: dict[str, Any],
        checkpoint: Checkpoint,
        wf_id: str,
        current_node: str,
        step: int,
        graph: StateGraph,
    ) -> tuple[dict[str, Any], int]:
        """Ejecuta un nodo, emite sus eventos y guarda el checkpoint resultante.

        Returns:
            Tupla (nuevo_state, nuevo_step).
        """
        step += 1
        await self._emit(
            WorkflowEvent(
                event_type=EventType.NODE_START,
                workflow_id=wf_id,
                node=current_node,
                data={"step": step, "graph_version": graph.version},
            )
        )

        node_start = time.time()

        # Inyectar human_input si existe
        if checkpoint.human_input:
            state["__human_input__"] = checkpoint.human_input
            checkpoint.human_input = None

        state = await self._execute_node(node, state)
        state.pop("__human_input__", None)
        state = redact_value(state)
        node_duration = time.time() - node_start
        self._metrics["nodes_executed"] += 1

        await self._emit(
            WorkflowEvent(
                event_type=EventType.NODE_END,
                workflow_id=wf_id,
                node=current_node,
                data={
                    "step": step,
                    "duration": node_duration,
                    "verdict": self._state_verdict(state),
                    "graph_version": graph.version,
                },
            )
        )

        checkpoint.current_node = current_node
        checkpoint.state = state
        checkpoint.step = step
        checkpoint.updated_at = time.time()
        self._save_checkpoint(checkpoint)

        await self._emit(
            WorkflowEvent(
                event_type=EventType.CHECKPOINT,
                workflow_id=wf_id,
                node=current_node,
                data={"step": step, "graph_version": graph.version},
            )
        )
        return state, step

    async def _advance_to_next_node(
        self,
        graph: StateGraph,
        current_node: str,
        state: dict[str, Any],
        wf_id: str,
    ) -> str:
        """Resuelve y emite la transicion hacia el proximo nodo del grafo.

        Returns:
            El id del proximo nodo, o END si el nodo actual no tiene sucesores.
        """
        edges = self._outgoing_edges_or_end(graph, current_node)
        if not edges:
            return END
        next_node = await self._resolve_next(edges, state)
        await self._emit(
            WorkflowEvent(
                event_type=EventType.EDGE_TRAVERSED,
                workflow_id=wf_id,
                node=current_node,
                data={"next": next_node, "graph_version": graph.version},
            )
        )
        return next_node

    async def _finalize_workflow_success(
        self,
        checkpoint: Checkpoint,
        wf_id: str,
        graph: StateGraph,
        state: dict[str, Any],
        step: int,
        start_time: float,
    ) -> dict[str, Any]:
        """Marca el workflow como completado, emite el evento final y persiste."""
        duration = time.time() - start_time
        checkpoint.status = WorkflowStatus.COMPLETED
        checkpoint.updated_at = time.time()
        self._metrics["workflows_completed"] += 1
        self._metrics["total_execution_time"] += duration

        await self._emit(
            WorkflowEvent(
                event_type=EventType.WORKFLOW_END,
                workflow_id=wf_id,
                data={
                    "status": "completed",
                    "steps": step,
                    "duration": duration,
                    "verdict": self._state_verdict(state),
                    "graph_version": graph.version,
                },
            )
        )
        state.pop("__human_input__", None)
        checkpoint.state = state
        self._save_checkpoint(checkpoint)

        return {
            "workflow_id": wf_id,
            "status": "completed",
            "current_node": checkpoint.current_node,
            "final_state": state,
            "steps": step,
            "duration_seconds": round(duration, 3),
            "graph": graph.name,
        }

    async def _record_workflow_failure(
        self,
        exc: Exception,
        checkpoint: Checkpoint,
        wf_id: str,
        current_node: str | None,
        step: int,
        start_time: float,
        graph: StateGraph,
    ) -> None:
        """Registra el fallo del workflow: checkpoint, metricas, evento y log."""
        duration = time.time() - start_time
        checkpoint.status = WorkflowStatus.FAILED
        checkpoint.error = redact_text(str(exc))
        checkpoint.updated_at = time.time()
        self._save_checkpoint(checkpoint)
        self._metrics["workflows_failed"] += 1
        self._metrics["total_execution_time"] += duration

        await self._emit(
            WorkflowEvent(
                event_type=EventType.ERROR,
                workflow_id=wf_id,
                node=current_node,
                data={
                    "error": redact_text(str(exc)),
                    "step": step,
                    "graph_version": graph.version,
                },
            )
        )
        self._save_checkpoint(checkpoint)

        logger.error("Workflow '%s' fallido en paso %d: %s", wf_id, step, exc)

    async def _run_workflow_loop(
        self,
        graph: StateGraph,
        checkpoint: Checkpoint,
        wf_id: str,
        state: dict[str, Any],
        current_node: str | None,
        step: int,
        start_time: float,
    ) -> dict[str, Any]:
        """Corre el bucle principal del workflow hasta terminar, pausar o fallar.

        Encapsula el manejo de errores: si un nodo lanza, se registra el fallo
        (checkpoint, metricas, evento) antes de volver a lanzar la excepcion.
        """
        try:
            while current_node and current_node != END and step < MAX_STEPS:
                if checkpoint.status == WorkflowStatus.CANCELLED:
                    return self._checkpoint_result(checkpoint)
                node = graph._nodes.get(current_node)
                if node is None:
                    raise RuntimeError(f"Nodo '{current_node}' no encontrado")

                paused_result = await self._maybe_pause_before_node(
                    node, checkpoint, state, wf_id, graph, current_node
                )
                if paused_result is not None:
                    return paused_result

                state, step = await self._run_node_step(
                    node, state, checkpoint, wf_id, current_node, step, graph
                )
                current_node = await self._advance_to_next_node(graph, current_node, state, wf_id)

            if step >= MAX_STEPS:
                raise RuntimeError(f"Workflow excedió {MAX_STEPS} pasos (posible loop infinito)")

            return await self._finalize_workflow_success(
                checkpoint, wf_id, graph, state, step, start_time
            )

        except Exception as e:
            await self._record_workflow_failure(
                e, checkpoint, wf_id, current_node, step, start_time, graph
            )
            raise

    async def execute(
        self,
        graph: StateGraph | str,
        initial_state: dict[str, Any] | None = None,
        workflow_id: str | None = None,
        *,
        _resume_checkpoint: Checkpoint | None = None,
    ) -> dict[str, Any]:
        """
        Ejecuta un workflow completo.

        Args:
            graph: StateGraph o nombre de un grafo registrado.
            initial_state: Estado inicial del workflow.
            workflow_id: ID opcional (se genera uno si no se provee).

        Returns:
            Dict con resultado: workflow_id, final_state, events, metrics.
        """
        graph = self._resolve_graph(graph)

        wf_id = workflow_id or f"wf-{uuid.uuid4().hex[:12]}"
        if _resume_checkpoint is None and workflow_id:
            replay = self._check_idempotent_replay(workflow_id, graph)
            if replay is not None:
                return replay

        state = dict(initial_state or {})
        start_time = time.time()

        checkpoint, current_node, step, resuming = self._init_or_resume_checkpoint(
            wf_id, graph, state, _resume_checkpoint
        )
        self._checkpoints[wf_id] = checkpoint
        if not resuming:
            self._metrics["workflows_started"] += 1
            await self._emit(
                WorkflowEvent(
                    event_type=EventType.WORKFLOW_START,
                    workflow_id=wf_id,
                    data={
                        "graph": graph.name,
                        "graph_version": graph.version,
                        "initial_state_keys": list(state.keys()),
                    },
                )
            )

        return await self._run_workflow_loop(
            graph, checkpoint, wf_id, state, current_node, step, start_time
        )

    def _resolve_graph(self, graph: StateGraph | str) -> StateGraph:
        """Resuelve y valida el grafo a ejecutar.

        Si se recibe un nombre, lo busca en los grafos registrados. Luego
        valida la integridad del grafo resultante.

        Args:
            graph: StateGraph o nombre de un grafo registrado.

        Returns:
            El StateGraph resuelto y validado.

        Raises:
            ValueError: Si el nombre no está registrado o el grafo es inválido.
        """
        if isinstance(graph, str):
            g = self._graphs.get(graph)
            if g is None:
                raise ValueError(f"Grafo '{graph}' no registrado")
            graph = g

        errors = graph.validate()
        if errors:
            raise ValueError(f"Grafo inválido: {'; '.join(errors)}")

        return graph

    @staticmethod
    def _state_verdict(state: dict[str, Any]) -> str | None:
        payload = state.get("gate_result")
        if not isinstance(payload, dict):
            return None
        try:
            return GateResult.from_dict(payload).verdict.value
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _state_next_action(state: dict[str, Any]) -> str | None:
        payload = state.get("gate_result")
        if not isinstance(payload, dict):
            return None
        try:
            return GateResult.from_dict(payload).next_action
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _checkpoint_result(
        checkpoint: Checkpoint,
        *,
        replayed: bool = False,
    ) -> dict[str, Any]:
        result: dict[str, Any] = {
            "workflow_id": checkpoint.workflow_id,
            "status": checkpoint.status.value,
            "current_node": checkpoint.current_node,
            "state": redact_value(checkpoint.state),
            "steps": checkpoint.step,
            "graph": checkpoint.graph_name,
            "graph_version": checkpoint.graph_version,
            "replayed": replayed,
        }
        if checkpoint.status == WorkflowStatus.COMPLETED:
            result["final_state"] = result["state"]
        if checkpoint.error:
            result["error"] = redact_text(checkpoint.error)
        return result

    def _outgoing_edges_or_end(self, graph: StateGraph, current_node: str) -> list[GraphEdge]:
        """Obtiene las edges salientes de un nodo para determinar el siguiente.

        Tanto los finish points como los nodos comunes terminan el workflow
        cuando no tienen edges salientes; en ese caso la lista vacía resultante
        señala END al llamador.

        Args:
            graph: Grafo en ejecución.
            current_node: Nodo actual desde el que se buscan edges salientes.

        Returns:
            Lista de edges salientes (vacía si el nodo no tiene sucesores).
        """
        return graph.get_next_nodes(current_node)

    async def resume(
        self,
        workflow_id: str,
        human_input: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Reanuda un workflow pausado (HITL).

        Args:
            workflow_id: ID del workflow pausado.
            human_input: Input del humano para continuar.

        Returns:
            Resultado de la ejecución reanudada.
        """
        checkpoint = self._checkpoints.get(workflow_id)
        if checkpoint is None:
            checkpoint = self._load_checkpoint(workflow_id)
        if checkpoint is None:
            raise ValueError(f"Workflow '{workflow_id}' no encontrado")
        if checkpoint.status != WorkflowStatus.PAUSED:
            raise ValueError(
                f"Workflow '{workflow_id}' no está pausado (status: {checkpoint.status.value})"
            )

        graph = self._graphs.get(checkpoint.graph_name)
        if graph is None:
            raise ValueError(f"Grafo '{checkpoint.graph_name}' no registrado")

        checkpoint.human_input = redact_value(human_input or {})
        checkpoint.status = WorkflowStatus.RUNNING
        checkpoint.updated_at = time.time()

        await self._emit(
            WorkflowEvent(
                event_type=EventType.RESUMED,
                workflow_id=workflow_id,
                node=checkpoint.current_node,
                data={
                    "human_input_keys": list((human_input or {}).keys()),
                    "graph_version": graph.version,
                },
            )
        )
        self._save_checkpoint(checkpoint)

        return await self.execute(
            graph,
            initial_state=dict(checkpoint.state),
            workflow_id=workflow_id,
            _resume_checkpoint=checkpoint,
        )

    # --------------------------------------------------------
    # Ejecución de nodos
    # --------------------------------------------------------
    async def _execute_node(
        self,
        node: GraphNode,
        state: dict[str, Any],
    ) -> dict[str, Any]:
        """Ejecuta un nodo individual con timeout."""
        try:
            if inspect.iscoroutinefunction(node.fn):
                result = await asyncio.wait_for(
                    node.fn(state),
                    timeout=self._node_timeout,
                )
            else:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(None, node.fn, state),
                    timeout=self._node_timeout,
                )

            if not isinstance(result, dict):
                raise TypeError(
                    f"Nodo '{node.name}' retornó {type(result).__name__}, se esperaba dict"
                )
            return result

        except TimeoutError:
            raise RuntimeError(
                f"Nodo '{node.name}' excedió timeout de {self._node_timeout}s"
            ) from None

    async def _resolve_next(
        self,
        edges: list[GraphEdge],
        state: dict[str, Any],
    ) -> str:
        """Resuelve el siguiente nodo a partir de las edges."""
        for edge in edges:
            if edge.target is not None:
                # Edge directa
                return edge.target

            if edge.router is not None:
                # Edge condicional
                if inspect.iscoroutinefunction(edge.router):
                    result = await edge.router(state)
                else:
                    result = edge.router(state)

                # Mapear resultado si hay condition_map
                if edge.condition_map and result in edge.condition_map:
                    return edge.condition_map[result]
                return result

        return END

    # --------------------------------------------------------
    # Eventos y listeners
    # --------------------------------------------------------
    def on_event(self, listener: Callable[[WorkflowEvent], Any]) -> None:
        """Registra un listener de eventos."""
        self._event_listeners.append(listener)

    async def _emit(self, event: WorkflowEvent) -> None:
        """Emite un evento a todos los listeners y al bus."""
        event.data = redact_value(event.data)
        # Almacenar en checkpoint
        checkpoint = self._checkpoints.get(event.workflow_id)
        if checkpoint:
            checkpoint.events.append(event.to_dict())

        # Notificar listeners
        for listener in self._event_listeners:
            try:
                if inspect.iscoroutinefunction(listener):
                    await listener(event)
                else:
                    listener(event)
            except Exception as e:
                logger.debug("Error en event listener: %s", e)

        # Publicar en bus si disponible
        if self._bus:
            try:
                await self._bus.publish(
                    f"workflow.{event.event_type.value}",
                    event.to_dict(),
                    from_agent="workflow-engine",
                )
            except Exception as e:
                logger.debug("Error publicando evento en bus: %s", e)

    # --------------------------------------------------------
    # Checkpointing
    # --------------------------------------------------------
    def _save_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Persiste un checkpoint a disco."""
        self._checkpoints[checkpoint.workflow_id] = checkpoint
        try:
            file_path = self._checkpoint_dir / f"{checkpoint.workflow_id}.json"
            data = checkpoint.to_dict()
            data["events"] = checkpoint.events[-50:]  # Últimos 50 eventos
            data["human_input"] = redact_value(checkpoint.human_input)
            temporary = file_path.with_suffix(f".{uuid.uuid4().hex}.tmp")
            temporary.write_text(
                json.dumps(data, indent=2, default=str),
                encoding="utf-8",
            )
            temporary.replace(file_path)
        except Exception as e:
            logger.debug("Error guardando checkpoint: %s", e)

    def _load_checkpoint(self, workflow_id: str) -> Checkpoint | None:
        """Carga un checkpoint desde disco."""
        file_path = self._checkpoint_dir / f"{workflow_id}.json"
        if not file_path.exists():
            return None
        try:
            data = json.loads(file_path.read_text(encoding="utf-8"))
            checkpoint = Checkpoint(
                workflow_id=data["workflow_id"],
                graph_name=data["graph_name"],
                graph_version=data.get("graph_version", 1),
                current_node=data["current_node"],
                state=data["state"],
                step=data["step"],
                status=WorkflowStatus(data["status"]),
                events=data.get("events", []),
                created_at=data.get("created_at", 0),
                updated_at=data.get("updated_at", 0),
                error=data.get("error"),
                human_input=data.get("human_input"),
            )
            self._checkpoints[workflow_id] = checkpoint
            return checkpoint
        except Exception as e:
            logger.warning("Error cargando checkpoint %s: %s", workflow_id, e)
            return None

    # --------------------------------------------------------
    # API pública
    # --------------------------------------------------------
    def get_workflow(self, workflow_id: str) -> dict[str, Any] | None:
        """Retorna el estado de un workflow."""
        cp = self._checkpoints.get(workflow_id)
        if cp is None:
            cp = self._load_checkpoint(workflow_id)
        if cp is None:
            return None
        return cp.to_dict()

    def list_workflows(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista workflows recientes."""
        # Cargar checkpoints de disco si no están en memoria
        for file_path in sorted(
            self._checkpoint_dir.glob("wf-*.json"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )[: limit * 2]:
            wf_id = file_path.stem
            if wf_id not in self._checkpoints:
                self._load_checkpoint(wf_id)

        workflows = list(self._checkpoints.values())

        if status:
            try:
                ws = WorkflowStatus(status)
                workflows = [w for w in workflows if w.status == ws]
            except ValueError as e:
                logger.warning(
                    "Filtro status=%r inválido, se listan todos los workflows: %s", status, e
                )

        workflows.sort(key=lambda w: w.updated_at, reverse=True)
        return [w.to_dict() for w in workflows[:limit]]

    def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancela un workflow en ejecución o pausado."""
        cp = self._checkpoints.get(workflow_id)
        if cp is None:
            cp = self._load_checkpoint(workflow_id)
        if cp is None:
            return False
        if cp.status == WorkflowStatus.CANCELLED:
            return True
        if cp.status in (WorkflowStatus.COMPLETED, WorkflowStatus.FAILED):
            return False
        cp.status = WorkflowStatus.CANCELLED
        cp.updated_at = time.time()
        cp.events.append(
            WorkflowEvent(
                event_type=EventType.CANCELLED,
                workflow_id=workflow_id,
                node=cp.current_node,
                data={
                    "graph_version": cp.graph_version,
                    "verdict": self._state_verdict(cp.state),
                },
            ).to_dict()
        )
        self._save_checkpoint(cp)
        return True

    def get_workflow_events(
        self,
        workflow_id: str,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Retorna eventos de un workflow."""
        cp = self._checkpoints.get(workflow_id)
        if cp is None:
            cp = self._load_checkpoint(workflow_id)
        if cp is None:
            return []
        return cp.events[-limit:]

    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del engine."""
        active = sum(
            1
            for cp in self._checkpoints.values()
            if cp.status in (WorkflowStatus.RUNNING, WorkflowStatus.PAUSED)
        )
        return {
            "registered_graphs": len(self._graphs),
            "active_workflows": active,
            "total_checkpoints": len(self._checkpoints),
            **self._metrics,
        }


# ============================================================
# Builder helpers — grafos pre-definidos del ecosistema
# ============================================================
def build_agent_pipeline(
    name: str,
    agents: list[str],
    description: str = "",
) -> StateGraph:
    """
    Construye un grafo secuencial que ejecuta una serie de agentes.

    Args:
        name: Nombre del workflow.
        agents: Lista de nombres de agentes a ejecutar en secuencia.
        description: Descripción del workflow.

    Returns:
        StateGraph configurado.
    """
    graph = StateGraph(name, description)

    for agent_name in agents:

        async def _agent_fn(state: dict[str, Any], _name: str = agent_name) -> dict[str, Any]:
            state.setdefault("results", {})
            state["results"][_name] = f"Ejecutado agente '{_name}'"
            state["last_agent"] = _name
            return state

        graph.add_node(agent_name, _agent_fn, node_type=NodeType.AGENT)

    # Encadenar secuencialmente
    graph.set_entry_point(agents[0])
    for i in range(len(agents) - 1):
        graph.add_edge(agents[i], agents[i + 1])
    graph.set_finish_point(agents[-1])

    return graph


def build_review_workflow(name: str = "code-review") -> StateGraph:
    """
    Construye un workflow de code review con branching condicional.

    Flujo:
      analyze → [simple] → review → END
      analyze → [complex] → plan → review → END
    """
    graph = StateGraph(name, "Workflow de revisión de código con branching")

    async def analyze(state: dict[str, Any]) -> dict[str, Any]:
        """Analiza complejidad del código."""
        code = state.get("code", "")
        state["complexity"] = "complex" if len(code) > 500 else "simple"
        state["analysis"] = f"Código de {len(code)} chars, complejidad: {state['complexity']}"
        return state

    async def plan(state: dict[str, Any]) -> dict[str, Any]:
        """Planifica la revisión para código complejo."""
        state["plan"] = "Plan de revisión: seguridad → performance → estilo"
        return state

    async def review(state: dict[str, Any]) -> dict[str, Any]:
        """Ejecuta la revisión."""
        state["review"] = f"Revisión completada. Análisis: {state.get('analysis', 'N/A')}"
        return state

    def route_by_complexity(state: dict[str, Any]) -> str:
        return "plan" if state.get("complexity") == "complex" else "review"

    graph.add_node("analyze", analyze)
    graph.add_node("plan", plan)
    graph.add_node("review", review)

    graph.set_entry_point("analyze")
    graph.add_conditional_edge("analyze", route_by_complexity)
    graph.add_edge("plan", "review")
    graph.set_finish_point("review")

    return graph


# ============================================================
# Singleton global
# ============================================================
_engine_instance: WorkflowEngine | None = None


def get_workflow_engine(bus: Any = None) -> WorkflowEngine:
    """Obtiene o crea la instancia global del WorkflowEngine."""
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = WorkflowEngine(bus=bus)
        # Registrar workflows pre-definidos
        _engine_instance.register_graph(build_review_workflow())
        from core.quality_gate_workflows import build_quality_gate_graphs

        for graph in build_quality_gate_graphs():
            _engine_instance.register_graph(graph)
        logger.info("WorkflowEngine inicializado con workflows pre-definidos")
    return _engine_instance
