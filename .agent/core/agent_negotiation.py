"""
Agent Negotiation — Contract Net Protocol para asignación de tareas.

Implementa el Contract Net Protocol (Smith 1980) adaptado para el
ecosistema Antigravity. Cuando una tarea llega al sistema, se subasta
entre los agentes capaces:

1. ANNOUNCE — Se publica la tarea con capabilities requeridas
2. BID — Los agentes capaces pujan con confianza, costo estimado y carga
3. EVALUATE — Se evalúan las pujas con una función de scoring configurable
4. AWARD — El ganador recibe la tarea, los demás se retiran
5. MONITOR — Si el ganador falla, se re-subasta entre los demás

Estrategias de evaluación:
  - BEST_CONFIDENCE: Agente con mayor confianza gana
  - LOWEST_LOAD: Agente con menor carga de trabajo gana
  - FASTEST: Agente con menor tiempo estimado gana
  - BALANCED: Score ponderado de confianza, carga y velocidad

Usage:
    protocol = ContractNetProtocol(bus=bus)

    # Registrar capacidades de agentes
    protocol.register_agent("explorer", ["code-analysis", "search", "dependencies"])
    protocol.register_agent("architect", ["design", "architecture", "patterns"])
    protocol.register_agent("security-auditor", ["security", "vulnerabilities", "audit"])

    # Subastar una tarea
    result = await protocol.auction(TaskAnnouncement(
        task="Analiza la arquitectura del módulo de auth",
        required_capabilities=["code-analysis"],
        deadline_seconds=30.0,
    ))

    print(result.winner)       # "explorer"
    print(result.winning_bid)  # Bid(confidence=0.92, ...)
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.agent_negotiation")

# ============================================================
# Constantes
# ============================================================
DEFAULT_BID_TIMEOUT = 10.0  # Tiempo para recibir pujas
DEFAULT_TASK_TIMEOUT = 300.0  # Timeout de ejecución de tarea
MAX_AUCTION_HISTORY = 200
NEGOTIATION_CHANNEL = "negotiation"
BID_CHANNEL_TPL = "negotiation.bids.{auction_id}"
AWARD_CHANNEL_TPL = "negotiation.award.{auction_id}"

# Directorio de agentes para auto-descubrimiento
_BASE_DIR = Path(__file__).parent.parent.parent


# ============================================================
# Enums
# ============================================================
class AuctionStrategy(str, Enum):
    """Estrategia para evaluar pujas."""

    BEST_CONFIDENCE = "best_confidence"
    LOWEST_LOAD = "lowest_load"
    FASTEST = "fastest"
    BALANCED = "balanced"


class AuctionStatus(str, Enum):
    """Estado de una subasta."""

    OPEN = "open"
    EVALUATING = "evaluating"
    AWARDED = "awarded"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    NO_BIDS = "no_bids"
    RE_AUCTION = "re_auction"


# ============================================================
# Modelos de datos
# ============================================================
@dataclass
class AgentProfile:
    """Perfil de un agente registrado en el protocolo."""

    name: str
    capabilities: list[str]
    current_load: float = 0.0  # 0.0 (libre) a 1.0 (saturado)
    max_concurrent: int = 3
    active_tasks: int = 0
    avg_duration_seconds: float = 30.0
    success_rate: float = 0.9
    total_tasks: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "capabilities": self.capabilities,
            "current_load": self.current_load,
            "max_concurrent": self.max_concurrent,
            "active_tasks": self.active_tasks,
            "avg_duration_seconds": self.avg_duration_seconds,
            "success_rate": self.success_rate,
            "total_tasks": self.total_tasks,
        }


@dataclass
class TaskAnnouncement:
    """Anuncio de tarea para subasta."""

    task: str
    required_capabilities: list[str] = field(default_factory=list)
    preferred_capabilities: list[str] = field(default_factory=list)
    deadline_seconds: float = DEFAULT_TASK_TIMEOUT
    bid_timeout: float = DEFAULT_BID_TIMEOUT
    strategy: AuctionStrategy = AuctionStrategy.BALANCED
    context: dict[str, Any] = field(default_factory=dict)
    from_agent: str = "system"
    priority: str = "NORMAL"
    excluded_agents: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task,
            "required_capabilities": self.required_capabilities,
            "preferred_capabilities": self.preferred_capabilities,
            "deadline_seconds": self.deadline_seconds,
            "bid_timeout": self.bid_timeout,
            "strategy": self.strategy.value,
            "from_agent": self.from_agent,
            "priority": self.priority,
            "excluded_agents": self.excluded_agents,
        }


@dataclass
class Bid:
    """Puja de un agente para una tarea."""

    agent_name: str
    confidence: float  # 0.0 a 1.0 — qué tan seguro está de hacerla bien
    estimated_duration: float  # segundos estimados
    current_load: float  # carga actual del agente
    capabilities_match: float  # 0.0 a 1.0 — qué tanto matchean sus capabilities
    reason: str = ""  # Justificación de la puja
    bid_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    score: float = 0.0  # Score calculado por la estrategia

    def to_dict(self) -> dict[str, Any]:
        return {
            "bid_id": self.bid_id,
            "agent_name": self.agent_name,
            "confidence": self.confidence,
            "estimated_duration": self.estimated_duration,
            "current_load": self.current_load,
            "capabilities_match": self.capabilities_match,
            "reason": self.reason,
            "score": self.score,
            "timestamp": self.timestamp,
        }


@dataclass
class AuctionResult:
    """Resultado de una subasta."""

    auction_id: str
    task: str
    status: AuctionStatus
    winner: str | None = None
    winning_bid: Bid | None = None
    all_bids: list[Bid] = field(default_factory=list)
    strategy: AuctionStrategy = AuctionStrategy.BALANCED
    task_id: str | None = None
    started_at: float = field(default_factory=time.time)
    completed_at: float | None = None
    re_auction_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "auction_id": self.auction_id,
            "task": self.task[:100],
            "status": self.status.value,
            "winner": self.winner,
            "winning_bid": self.winning_bid.to_dict() if self.winning_bid else None,
            "all_bids": [b.to_dict() for b in self.all_bids],
            "strategy": self.strategy.value,
            "task_id": self.task_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "re_auction_count": self.re_auction_count,
            "bid_count": len(self.all_bids),
        }


# ============================================================
# Bid Scorer — evalúa pujas según la estrategia
# ============================================================
class BidScorer:
    """Calcula el score de cada puja según la estrategia."""

    @staticmethod
    def score(bid: Bid, strategy: AuctionStrategy) -> float:
        """Calcula un score para la puja (mayor = mejor)."""
        if strategy == AuctionStrategy.BEST_CONFIDENCE:
            return bid.confidence * bid.capabilities_match

        elif strategy == AuctionStrategy.LOWEST_LOAD:
            return (1.0 - bid.current_load) * bid.capabilities_match

        elif strategy == AuctionStrategy.FASTEST:
            # Normalizar duración: menor duración → mayor score
            speed = 1.0 / max(bid.estimated_duration, 1.0)
            return speed * bid.capabilities_match

        elif strategy == AuctionStrategy.BALANCED:
            # Ponderación: 40% confianza, 25% carga, 20% velocidad, 15% match
            w_confidence = 0.40
            w_load = 0.25
            w_speed = 0.20
            w_match = 0.15

            load_score = 1.0 - bid.current_load
            speed_score = 1.0 / max(bid.estimated_duration / 60.0, 0.1)
            speed_score = min(speed_score, 1.0)  # Cap a 1.0

            return (
                w_confidence * bid.confidence
                + w_load * load_score
                + w_speed * speed_score
                + w_match * bid.capabilities_match
            )

        return 0.0


# ============================================================
# Contract Net Protocol
# ============================================================
class ContractNetProtocol:
    """
    Implementación del Contract Net Protocol para negociación
    de tareas entre agentes del ecosistema Antigravity.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus
        self._agents: dict[str, AgentProfile] = {}
        self._auction_history: list[AuctionResult] = []
        self._active_auctions: dict[str, AuctionResult] = {}

        # Métricas
        self._metrics = {
            "auctions_total": 0,
            "auctions_awarded": 0,
            "auctions_no_bids": 0,
            "auctions_failed": 0,
            "re_auctions": 0,
            "avg_bid_count": 0.0,
            "avg_winning_score": 0.0,
        }

    # --------------------------------------------------------
    # Agent Registration
    # --------------------------------------------------------
    def register_agent(
        self,
        name: str,
        capabilities: list[str],
        max_concurrent: int = 3,
    ) -> None:
        """Registra un agente con sus capacidades."""
        self._agents[name] = AgentProfile(
            name=name,
            capabilities=capabilities,
            max_concurrent=max_concurrent,
        )
        logger.info(
            "Agente registrado para negociación: '%s' caps=%s",
            name,
            capabilities,
        )

    def unregister_agent(self, name: str) -> bool:
        """Elimina un agente del protocolo."""
        if name in self._agents:
            del self._agents[name]
            return True
        return False

    def update_agent_load(
        self,
        name: str,
        current_load: float | None = None,
        active_tasks: int | None = None,
    ) -> None:
        """Actualiza la carga de un agente."""
        profile = self._agents.get(name)
        if profile is None:
            return
        if current_load is not None:
            profile.current_load = max(0.0, min(1.0, current_load))
        if active_tasks is not None:
            profile.active_tasks = active_tasks

    def list_agents(self) -> list[dict[str, Any]]:
        """Lista agentes registrados."""
        return [a.to_dict() for a in self._agents.values()]

    def auto_discover_agents(self) -> int:
        """Auto-descubre agentes desde el filesystem del ecosistema."""
        agents_dir = _BASE_DIR / ".agent" / "agents"
        if not agents_dir.exists():
            return 0

        discovered = 0
        for agent_dir in agents_dir.iterdir():
            if not agent_dir.is_dir() or agent_dir.name.startswith(("_", ".")):
                continue

            identity = agent_dir / "IDENTITY.md"
            if not identity.exists():
                continue

            if agent_dir.name in self._agents:
                continue

            # Extraer capabilities básicas del nombre del agente
            capabilities = self._infer_capabilities(agent_dir.name)
            self.register_agent(agent_dir.name, capabilities)
            discovered += 1

        logger.info("Auto-descubiertos %d agentes para negociación", discovered)
        return discovered

    @staticmethod
    def _infer_capabilities(agent_name: str) -> list[str]:
        """Infiere capabilities de un agente por su nombre."""
        capability_map: dict[str, list[str]] = {
            "explorer": ["code-analysis", "search", "dependencies"],
            "architect": ["design", "architecture", "patterns", "planning"],
            "security-auditor": ["security", "vulnerabilities", "audit"],
            "test-engineer": ["testing", "quality", "coverage"],
            "debugger": ["debugging", "troubleshooting", "errors"],
            "frontend-specialist": ["frontend", "ui", "react", "css"],
            "backend-specialist": ["backend", "api", "server"],
            "database-architect": ["database", "sql", "schema"],
            "devops-engineer": ["devops", "ci-cd", "infrastructure"],
            "performance-optimizer": ["performance", "optimization", "profiling"],
            "documentation-writer": ["documentation", "writing", "api-docs"],
            "code-archaeologist": ["legacy", "code-analysis", "history"],
            "ml-engineer": ["machine-learning", "data-science", "models"],
            "planner": ["planning", "strategy", "decomposition"],
        }
        return capability_map.get(agent_name, ["general"])

    # --------------------------------------------------------
    # Auction Process
    # --------------------------------------------------------
    async def auction(
        self,
        announcement: TaskAnnouncement,
        max_re_auctions: int = 2,
    ) -> AuctionResult:
        """
        Ejecuta una subasta completa para una tarea.

        1. Identifica agentes capaces
        2. Genera pujas automáticas basadas en profiles
        3. Evalúa pujas con la estrategia elegida
        4. Retorna resultado con ganador

        Si no hay pujas o el ganador falla, puede re-subastar.
        """
        _ = max_re_auctions  # reservado para estrategia de re-subasta
        auction_id = str(uuid.uuid4())
        self._metrics["auctions_total"] += 1

        result = AuctionResult(
            auction_id=auction_id,
            task=announcement.task,
            status=AuctionStatus.OPEN,
            strategy=announcement.strategy,
        )
        self._active_auctions[auction_id] = result

        # Fase 1: Solicitar pujas
        bids = await self._collect_bids(announcement)
        result.all_bids = bids

        if not bids:
            result.status = AuctionStatus.NO_BIDS
            self._metrics["auctions_no_bids"] += 1
            logger.warning(
                "Subasta %s sin pujas para tarea '%.50s...'",
                auction_id,
                announcement.task,
            )
            self._finalize_auction(result)
            return result

        # Fase 2: Evaluar y seleccionar ganador
        result.status = AuctionStatus.EVALUATING
        winner_bid = self._evaluate_bids(bids, announcement.strategy)

        if winner_bid is None:
            result.status = AuctionStatus.NO_BIDS
            self._finalize_auction(result)
            return result

        result.winner = winner_bid.agent_name
        result.winning_bid = winner_bid
        result.status = AuctionStatus.AWARDED
        self._metrics["auctions_awarded"] += 1

        # Actualizar métricas del agente ganador
        profile = self._agents.get(winner_bid.agent_name)
        if profile:
            profile.active_tasks += 1
            profile.total_tasks += 1
            profile.current_load = min(
                1.0,
                profile.active_tasks / max(profile.max_concurrent, 1),
            )

        logger.info(
            "Subasta %s: ganador='%s' score=%.3f confianza=%.2f (de %d pujas)",
            auction_id,
            winner_bid.agent_name,
            winner_bid.score,
            winner_bid.confidence,
            len(bids),
        )

        # Publicar resultado en bus
        if self._bus:
            try:
                await self._bus.publish(
                    NEGOTIATION_CHANNEL,
                    {
                        "event": "auction_awarded",
                        "auction_id": auction_id,
                        "winner": winner_bid.agent_name,
                        "task": announcement.task[:100],
                        "bids": len(bids),
                        "score": winner_bid.score,
                    },
                    from_agent="negotiation-protocol",
                )
            except Exception:
                pass

        self._finalize_auction(result)
        return result

    async def _collect_bids(self, announcement: TaskAnnouncement) -> list[Bid]:
        """Recolecta pujas de agentes capaces."""
        bids: list[Bid] = []

        for profile in self._agents.values():
            # Excluir agentes explícitamente excluidos
            if profile.name in announcement.excluded_agents:
                continue

            # Check si el agente tiene capacity
            if profile.active_tasks >= profile.max_concurrent:
                continue

            # Calcular match de capabilities
            match_score = self._calculate_capability_match(
                profile.capabilities,
                announcement.required_capabilities,
                announcement.preferred_capabilities,
            )

            if match_score <= 0 and announcement.required_capabilities:
                continue  # No matchea ninguna capability requerida

            # Generar puja automática basada en el perfil
            bid = Bid(
                agent_name=profile.name,
                confidence=profile.success_rate * match_score,
                estimated_duration=profile.avg_duration_seconds,
                current_load=profile.current_load,
                capabilities_match=match_score,
                reason=f"Match {match_score:.0%} de capabilities requeridas",
            )
            bids.append(bid)

        return bids

    @staticmethod
    def _calculate_capability_match(
        agent_caps: list[str],
        required: list[str],
        preferred: list[str],
    ) -> float:
        """Calcula qué tan bien matchean las capabilities."""
        if not required and not preferred:
            return 0.5  # Sin requisitos, score medio

        score = 0.0
        total_weight = 0.0

        # Required: peso 1.0 cada una
        for cap in required:
            total_weight += 1.0
            if cap in agent_caps:
                score += 1.0

        # Si no cumple todas las requeridas, score muy bajo
        if required and score < len(required):
            return score / len(required) * 0.3  # Penalizar fuerte

        # Preferred: peso 0.5 cada una
        for cap in preferred:
            total_weight += 0.5
            if cap in agent_caps:
                score += 0.5

        return score / max(total_weight, 1.0)

    def _evaluate_bids(
        self,
        bids: list[Bid],
        strategy: AuctionStrategy,
    ) -> Bid | None:
        """Evalúa pujas y retorna la ganadora."""
        if not bids:
            return None

        # Calcular scores
        for bid in bids:
            bid.score = BidScorer.score(bid, strategy)

        # Ordenar por score descendente
        bids.sort(key=lambda b: b.score, reverse=True)

        # Actualizar métricas
        self._metrics["avg_bid_count"] = (
            self._metrics["avg_bid_count"] * (self._metrics["auctions_total"] - 1) + len(bids)
        ) / self._metrics["auctions_total"]
        self._metrics["avg_winning_score"] = (
            self._metrics["avg_winning_score"] * max(self._metrics["auctions_awarded"] - 1, 0)
            + bids[0].score
        ) / max(self._metrics["auctions_awarded"], 1)

        return bids[0]

    async def re_auction(
        self,
        auction_id: str,
        failed_agent: str,
    ) -> AuctionResult | None:
        """
        Re-subasta una tarea cuando el agente ganador falla.

        Excluye al agente fallido y re-ejecuta la subasta con los demás.
        """
        original = None
        for result in reversed(self._auction_history):
            if result.auction_id == auction_id:
                original = result
                break

        if original is None:
            logger.warning("Re-auction: subasta %s no encontrada", auction_id)
            return None

        self._metrics["re_auctions"] += 1

        # Actualizar perfil del agente fallido
        profile = self._agents.get(failed_agent)
        if profile:
            profile.active_tasks = max(0, profile.active_tasks - 1)
            profile.success_rate = max(0.1, profile.success_rate * 0.9)

        # Crear nuevo announcement excluyendo al fallido
        announcement = TaskAnnouncement(
            task=original.task,
            excluded_agents=[failed_agent]
            + [b.agent_name for b in original.all_bids if b.agent_name == failed_agent],
        )

        new_result = await self.auction(announcement)
        new_result.re_auction_count = original.re_auction_count + 1
        return new_result

    def _finalize_auction(self, result: AuctionResult) -> None:
        """Archiva una subasta completada."""
        result.completed_at = time.time()
        self._active_auctions.pop(result.auction_id, None)
        self._auction_history.append(result)
        if len(self._auction_history) > MAX_AUCTION_HISTORY:
            self._auction_history = self._auction_history[-MAX_AUCTION_HISTORY:]

    # --------------------------------------------------------
    # Record execution outcomes (feedback para ajustar profiles)
    # --------------------------------------------------------
    def record_outcome(
        self,
        agent_name: str,
        success: bool,
        duration_seconds: float,
    ) -> None:
        """
        Registra el resultado de una ejecución para ajustar el perfil.
        Feedback loop: resultados reales mejoran futuras pujas.
        """
        profile = self._agents.get(agent_name)
        if profile is None:
            return

        profile.active_tasks = max(0, profile.active_tasks - 1)
        profile.current_load = profile.active_tasks / max(profile.max_concurrent, 1)

        # Exponential moving average para success_rate
        alpha = 0.1
        profile.success_rate = (
            alpha * (1.0 if success else 0.0) + (1 - alpha) * profile.success_rate
        )

        # EMA para avg_duration
        profile.avg_duration_seconds = (
            alpha * duration_seconds + (1 - alpha) * profile.avg_duration_seconds
        )

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del protocolo."""
        return {
            "agents_registered": len(self._agents),
            "active_auctions": len(self._active_auctions),
            "auction_history_size": len(self._auction_history),
            "metrics": {**self._metrics},
        }

    def get_auction_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna historial de subastas."""
        return [a.to_dict() for a in self._auction_history[-limit:]]

    def get_auction(self, auction_id: str) -> dict[str, Any] | None:
        """Retorna una subasta por ID."""
        if auction_id in self._active_auctions:
            return self._active_auctions[auction_id].to_dict()
        for result in reversed(self._auction_history):
            if result.auction_id == auction_id:
                return result.to_dict()
        return None


# ============================================================
# Singleton
# ============================================================
_instance: ContractNetProtocol | None = None


async def get_negotiation_protocol(bus: Any = None) -> ContractNetProtocol:
    """Obtiene o crea la instancia global del protocolo."""
    global _instance
    if _instance is None:
        _instance = ContractNetProtocol(bus=bus)
    return _instance
