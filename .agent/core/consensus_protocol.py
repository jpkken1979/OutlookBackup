"""
Consensus Protocol — Votación y consenso multi-agente.

Cuando múltiples agentes trabajan en la misma tarea y producen
resultados diferentes o contradictorios, este protocolo resuelve
el conflicto mediante votación ponderada:

Modos de consenso:
  - MAJORITY: Mayoría simple (>50% de votos)
  - SUPERMAJORITY: Supermayoría (>66% de votos)
  - UNANIMOUS: Unanimidad requerida
  - WEIGHTED: Ponderado por expertise del agente en el dominio
  - QUORUM: Requiere mínimo de participantes + mayoría

El flujo:
  1. PROPOSE — Se plantea una pregunta/decisión a los agentes
  2. VOTE — Cada agente emite su voto con justificación
  3. EVALUATE — Se evalúan votos según el modo de consenso
  4. RESOLVE — Se emite la decisión final o se escala

Usage:
    protocol = ConsensusProtocol(bus=bus)

    # Crear propuesta
    proposal = protocol.create_proposal(
        question="¿Debemos usar JWT o sessions para auth?",
        options=["jwt", "sessions", "hybrid"],
        voters=["architect", "security-auditor", "backend-specialist"],
        mode=ConsensusMode.WEIGHTED,
    )

    # Registrar votos
    protocol.cast_vote(proposal.proposal_id, "architect", "jwt",
        confidence=0.85, reason="Stateless, escalable")
    protocol.cast_vote(proposal.proposal_id, "security-auditor", "hybrid",
        confidence=0.90, reason="JWT para API, sessions para web")
    protocol.cast_vote(proposal.proposal_id, "backend-specialist", "jwt",
        confidence=0.75, reason="Menor complejidad de implementación")

    # Resolver
    result = protocol.resolve(proposal.proposal_id)
    print(result.winner)      # "jwt"
    print(result.consensus)   # True
    print(result.vote_tally)  # {"jwt": 2, "hybrid": 1}
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.consensus_protocol")

# ============================================================
# Constantes
# ============================================================
MAX_PROPOSAL_HISTORY = 200
CONSENSUS_CHANNEL = "consensus.events"


# ============================================================
# Enums
# ============================================================
class ConsensusMode(str, Enum):
    """Modo de consenso."""

    MAJORITY = "majority"  # >50%
    SUPERMAJORITY = "supermajority"  # >66%
    UNANIMOUS = "unanimous"  # 100%
    WEIGHTED = "weighted"  # Ponderado por expertise
    QUORUM = "quorum"  # Mínimo participantes + mayoría


class ProposalStatus(str, Enum):
    """Estado de una propuesta."""

    OPEN = "open"
    VOTING = "voting"
    RESOLVED = "resolved"
    NO_CONSENSUS = "no_consensus"
    ESCALATED = "escalated"
    EXPIRED = "expired"


class VoteValue(str, Enum):
    """Tipos de voto especiales."""

    ABSTAIN = "_abstain"


# ============================================================
# Modelos
# ============================================================
@dataclass
class Vote:
    """Voto de un agente en una propuesta."""

    voter: str
    choice: str  # Una de las options de la propuesta, o VoteValue.ABSTAIN
    confidence: float  # 0.0 a 1.0
    reason: str = ""
    vote_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: float = field(default_factory=time.time)
    weight: float = 1.0  # Peso calculado por expertise

    def to_dict(self) -> dict[str, Any]:
        return {
            "vote_id": self.vote_id,
            "voter": self.voter,
            "choice": self.choice,
            "confidence": self.confidence,
            "reason": self.reason,
            "weight": round(self.weight, 3),
            "timestamp": self.timestamp,
        }


@dataclass
class Proposal:
    """Propuesta sometida a votación."""

    proposal_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    question: str = ""
    options: list[str] = field(default_factory=list)
    voters: list[str] = field(default_factory=list)
    mode: ConsensusMode = ConsensusMode.MAJORITY
    quorum_minimum: int = 2  # Mínimo de votantes para quorum
    deadline_seconds: float = 300.0  # Tiempo límite
    context: dict[str, Any] = field(default_factory=dict)
    status: ProposalStatus = ProposalStatus.OPEN
    votes: list[Vote] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    resolved_at: float | None = None
    from_agent: str = "system"

    def to_dict(self) -> dict[str, Any]:
        tally = self.get_tally()
        return {
            "proposal_id": self.proposal_id,
            "question": self.question,
            "options": self.options,
            "voters": self.voters,
            "mode": self.mode.value,
            "status": self.status.value,
            "votes": [v.to_dict() for v in self.votes],
            "vote_count": len(self.votes),
            "expected_voters": len(self.voters),
            "tally": tally,
            "quorum_minimum": self.quorum_minimum,
            "created_at": self.created_at,
            "resolved_at": self.resolved_at,
        }

    def get_tally(self) -> dict[str, float]:
        """Cuenta votos (ponderados por weight)."""
        tally: dict[str, float] = dict.fromkeys(self.options, 0.0)
        for vote in self.votes:
            if vote.choice in tally:
                tally[vote.choice] += vote.weight * vote.confidence
        return tally


@dataclass
class ConsensusResult:
    """Resultado de la resolución de consenso."""

    proposal_id: str
    winner: str | None = None
    consensus_reached: bool = False
    vote_tally: dict[str, float] = field(default_factory=dict)
    total_votes: int = 0
    total_weight: float = 0.0
    winner_percentage: float = 0.0
    mode: ConsensusMode = ConsensusMode.MAJORITY
    dissenting_votes: list[Vote] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "proposal_id": self.proposal_id,
            "winner": self.winner,
            "consensus_reached": self.consensus_reached,
            "vote_tally": {k: round(v, 3) for k, v in self.vote_tally.items()},
            "total_votes": self.total_votes,
            "total_weight": round(self.total_weight, 3),
            "winner_percentage": round(self.winner_percentage, 3),
            "mode": self.mode.value,
            "dissenting_voters": [v.voter for v in self.dissenting_votes],
            "reason": self.reason,
        }


# ============================================================
# Expertise Weights
# ============================================================
class ExpertiseWeighter:
    """Calcula peso de voto basado en expertise del agente en el dominio."""

    # Agent → dominios de expertise (score 0-1)
    EXPERTISE: dict[str, dict[str, float]] = {
        "architect": {
            "architecture": 1.0,
            "design": 0.9,
            "patterns": 0.9,
            "scalability": 0.8,
            "general": 0.7,
        },
        "security-auditor": {
            "security": 1.0,
            "auth": 0.95,
            "vulnerabilities": 0.9,
            "compliance": 0.85,
            "general": 0.5,
        },
        "test-engineer": {
            "testing": 1.0,
            "quality": 0.9,
            "coverage": 0.9,
            "regression": 0.85,
            "general": 0.6,
        },
        "explorer": {
            "code-analysis": 1.0,
            "dependencies": 0.9,
            "search": 0.9,
            "legacy": 0.8,
            "general": 0.7,
        },
        "frontend-specialist": {
            "frontend": 1.0,
            "ui": 0.95,
            "react": 0.9,
            "css": 0.85,
            "a11y": 0.8,
            "general": 0.5,
        },
        "backend-specialist": {
            "backend": 1.0,
            "api": 0.95,
            "server": 0.9,
            "database": 0.7,
            "general": 0.6,
        },
        "database-architect": {
            "database": 1.0,
            "sql": 0.95,
            "schema": 0.9,
            "migration": 0.85,
            "general": 0.5,
        },
        "performance-optimizer": {
            "performance": 1.0,
            "optimization": 0.95,
            "profiling": 0.9,
            "general": 0.5,
        },
        "devops-engineer": {
            "devops": 1.0,
            "ci-cd": 0.95,
            "infrastructure": 0.9,
            "docker": 0.85,
            "general": 0.5,
        },
    }

    @classmethod
    def calculate_weight(
        cls,
        agent: str,
        question: str,
        options: list[str],
    ) -> float:
        """Calcula el peso de un agente para una pregunta dada."""
        expertise = cls.EXPERTISE.get(agent, {"general": 0.5})

        # Buscar keywords del dominio en la pregunta y opciones
        all_text = (question + " " + " ".join(options)).lower()
        max_score = 0.0

        for domain, score in expertise.items():
            if domain in all_text:
                max_score = max(max_score, score)

        # Si no se encontró dominio específico, usar general
        if max_score == 0.0:
            max_score = expertise.get("general", 0.5)

        return max_score


# ============================================================
# Consensus Protocol
# ============================================================
class ConsensusProtocol:
    """
    Protocolo de consenso multi-agente.
    Gestiona propuestas, votos, y resolución de conflictos.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus
        self._proposals: dict[str, Proposal] = {}
        self._history: list[ConsensusResult] = []

        # Métricas
        self._metrics = {
            "proposals_total": 0,
            "proposals_resolved": 0,
            "proposals_no_consensus": 0,
            "proposals_escalated": 0,
            "votes_cast": 0,
            "avg_consensus_rate": 0.0,
        }

    # --------------------------------------------------------
    # Proposal Management
    # --------------------------------------------------------
    def create_proposal(
        self,
        question: str,
        options: list[str],
        voters: list[str],
        mode: ConsensusMode = ConsensusMode.MAJORITY,
        quorum_minimum: int = 2,
        deadline_seconds: float = 300.0,
        context: dict[str, Any] | None = None,
        from_agent: str = "system",
    ) -> Proposal:
        """Crea una nueva propuesta de votación."""
        self._metrics["proposals_total"] += 1

        proposal = Proposal(
            question=question,
            options=options,
            voters=voters,
            mode=mode,
            quorum_minimum=min(quorum_minimum, len(voters)),
            deadline_seconds=deadline_seconds,
            context=context or {},
            status=ProposalStatus.VOTING,
            from_agent=from_agent,
        )
        self._proposals[proposal.proposal_id] = proposal

        logger.info(
            "Propuesta creada: id=%s mode=%s voters=%d options=%s — '%.60s...'",
            proposal.proposal_id[:8],
            mode.value,
            len(voters),
            options,
            question,
        )
        return proposal

    def get_proposal(self, proposal_id: str) -> Proposal | None:
        """Retorna una propuesta por ID."""
        return self._proposals.get(proposal_id)

    def list_proposals(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Lista propuestas."""
        proposals = list(self._proposals.values())
        if status:
            proposals = [p for p in proposals if p.status.value == status]
        return [p.to_dict() for p in proposals[-limit:]]

    # --------------------------------------------------------
    # Voting
    # --------------------------------------------------------
    def cast_vote(
        self,
        proposal_id: str,
        voter: str,
        choice: str,
        confidence: float = 0.8,
        reason: str = "",
    ) -> Vote | None:
        """
        Registra un voto en una propuesta.

        Returns:
            Vote si fue aceptado, None si no.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            logger.warning("Voto rechazado: propuesta %s no existe", proposal_id)
            return None

        if proposal.status not in (ProposalStatus.OPEN, ProposalStatus.VOTING):
            logger.warning("Voto rechazado: propuesta %s ya resuelta", proposal_id)
            return None

        # Validar que el voter está en la lista
        if voter not in proposal.voters:
            logger.warning("Voto rechazado: '%s' no es votante autorizado", voter)
            return None

        # Validar que la opción es válida
        if choice not in proposal.options and choice != VoteValue.ABSTAIN.value:
            logger.warning("Voto rechazado: opción '%s' no válida", choice)
            return None

        # Verificar si ya votó
        existing = [v for v in proposal.votes if v.voter == voter]
        if existing:
            logger.warning("Voto rechazado: '%s' ya votó", voter)
            return None

        # Calcular peso por expertise
        weight = 1.0
        if proposal.mode == ConsensusMode.WEIGHTED:
            weight = ExpertiseWeighter.calculate_weight(voter, proposal.question, proposal.options)

        vote = Vote(
            voter=voter,
            choice=choice,
            confidence=max(0.0, min(1.0, confidence)),
            reason=reason,
            weight=weight,
        )
        proposal.votes.append(vote)
        self._metrics["votes_cast"] += 1

        logger.debug(
            "Voto registrado: voter=%s choice=%s confidence=%.2f weight=%.2f",
            voter,
            choice,
            confidence,
            weight,
        )
        return vote

    # --------------------------------------------------------
    # Resolution
    # --------------------------------------------------------
    def resolve(self, proposal_id: str) -> ConsensusResult:
        """
        Resuelve una propuesta evaluando los votos según el modo.

        Returns:
            ConsensusResult con el resultado de la votación.
        """
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return ConsensusResult(
                proposal_id=proposal_id,
                reason="Propuesta no encontrada",
            )

        # Excluir abstenciones
        active_votes = [v for v in proposal.votes if v.choice != VoteValue.ABSTAIN.value]
        tally = proposal.get_tally()
        total_weight = sum(v.weight * v.confidence for v in active_votes) or 1.0

        # Encontrar ganador
        if tally:
            winner_choice = max(tally, key=lambda k: tally[k])
            winner_score = tally[winner_choice]
            winner_pct = winner_score / total_weight if total_weight > 0 else 0
        else:
            winner_choice = None
            winner_score = 0
            winner_pct = 0

        # Evaluar consenso según modo
        consensus, reason = self._evaluate_consensus(
            proposal, active_votes, tally, winner_choice, winner_pct
        )

        # Identificar votos disidentes
        dissenting = [v for v in active_votes if v.choice != winner_choice] if winner_choice else []

        result = ConsensusResult(
            proposal_id=proposal_id,
            winner=winner_choice if consensus else None,
            consensus_reached=consensus,
            vote_tally=tally,
            total_votes=len(active_votes),
            total_weight=total_weight,
            winner_percentage=winner_pct,
            mode=proposal.mode,
            dissenting_votes=dissenting,
            reason=reason,
        )

        # Actualizar estado de propuesta
        if consensus:
            proposal.status = ProposalStatus.RESOLVED
            self._metrics["proposals_resolved"] += 1
        else:
            proposal.status = ProposalStatus.NO_CONSENSUS
            self._metrics["proposals_no_consensus"] += 1

        proposal.resolved_at = time.time()

        # Actualizar tasa de consenso
        total = self._metrics["proposals_resolved"] + self._metrics["proposals_no_consensus"]
        if total > 0:
            self._metrics["avg_consensus_rate"] = self._metrics["proposals_resolved"] / total

        # Guardar en historial
        self._history.append(result)
        if len(self._history) > MAX_PROPOSAL_HISTORY:
            self._history = self._history[-MAX_PROPOSAL_HISTORY:]

        logger.info(
            "Propuesta %s resuelta: consensus=%s winner=%s pct=%.1f%% mode=%s",
            proposal_id[:8],
            consensus,
            winner_choice,
            winner_pct * 100,
            proposal.mode.value,
        )

        return result

    def _evaluate_consensus(
        self,
        proposal: Proposal,
        active_votes: list[Vote],
        tally: dict[str, float],
        winner: str | None,
        winner_pct: float,
    ) -> tuple[bool, str]:
        """Evalúa si se alcanzó consenso según el modo."""
        mode = proposal.mode
        vote_count = len(active_votes)

        # Check quorum para modo QUORUM
        if mode == ConsensusMode.QUORUM:
            if vote_count < proposal.quorum_minimum:
                return False, (
                    f"Quorum no alcanzado: {vote_count}/{proposal.quorum_minimum} votantes"
                )
            # Con quorum, aplica mayoría simple
            if winner_pct > 0.5:
                return True, (
                    f"Quorum alcanzado ({vote_count} votantes) "
                    f"y mayoría ({winner_pct:.0%}) para '{winner}'"
                )
            return False, f"Quorum alcanzado pero sin mayoría ({winner_pct:.0%})"

        if mode == ConsensusMode.MAJORITY:
            if winner_pct > 0.5:
                return True, f"Mayoría simple ({winner_pct:.0%}) para '{winner}'"
            return False, f"Sin mayoría simple ({winner_pct:.0%})"

        elif mode == ConsensusMode.SUPERMAJORITY:
            if winner_pct > 0.666:
                return True, f"Supermayoría ({winner_pct:.0%}) para '{winner}'"
            return False, f"Sin supermayoría ({winner_pct:.0%}, requerido >66%)"

        elif mode == ConsensusMode.UNANIMOUS:
            if winner_pct >= 0.999:
                return True, f"Unanimidad alcanzada para '{winner}'"
            return False, f"Sin unanimidad ({winner_pct:.0%})"

        elif mode == ConsensusMode.WEIGHTED:
            # En modo weighted, la confianza ponderada del ganador debe ser > 50%
            if winner_pct > 0.5:
                return True, (
                    f"Consenso ponderado ({winner_pct:.0%}) para '{winner}' (weighted by expertise)"
                )
            return False, f"Sin consenso ponderado ({winner_pct:.0%})"

        return False, "Modo de consenso no reconocido"

    def escalate(self, proposal_id: str, reason: str = "") -> bool:
        """Escala una propuesta sin consenso."""
        proposal = self._proposals.get(proposal_id)
        if proposal is None:
            return False
        proposal.status = ProposalStatus.ESCALATED
        self._metrics["proposals_escalated"] += 1
        logger.info("Propuesta %s escalada: %s", proposal_id[:8], reason)
        return True

    # --------------------------------------------------------
    # Quick Consensus — atajo para votación rápida
    # --------------------------------------------------------
    def quick_consensus(
        self,
        question: str,
        options: list[str],
        agent_votes: dict[str, tuple[str, float, str]],
        mode: ConsensusMode = ConsensusMode.WEIGHTED,
    ) -> ConsensusResult:
        """
        Atajo: crea propuesta, vota, y resuelve en un solo paso.

        Args:
            question: La pregunta.
            options: Opciones disponibles.
            agent_votes: dict de {agent: (choice, confidence, reason)}.
            mode: Modo de consenso.

        Returns:
            ConsensusResult directamente.
        """
        voters = list(agent_votes.keys())
        proposal = self.create_proposal(
            question=question,
            options=options,
            voters=voters,
            mode=mode,
        )

        for agent, (choice, confidence, reason) in agent_votes.items():
            self.cast_vote(
                proposal.proposal_id,
                agent,
                choice,
                confidence,
                reason,
            )

        return self.resolve(proposal.proposal_id)

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Retorna estadísticas del protocolo."""
        return {
            "active_proposals": sum(
                1
                for p in self._proposals.values()
                if p.status in (ProposalStatus.OPEN, ProposalStatus.VOTING)
            ),
            "total_proposals": len(self._proposals),
            "history_size": len(self._history),
            "metrics": {**self._metrics},
        }

    def get_consensus_history(self, limit: int = 50) -> list[dict[str, Any]]:
        """Retorna historial de resoluciones."""
        return [r.to_dict() for r in self._history[-limit:]]


# ============================================================
# Singleton
# ============================================================
_instance: ConsensusProtocol | None = None


async def get_consensus_protocol(bus: Any = None) -> ConsensusProtocol:
    """Obtiene o crea la instancia global."""
    global _instance
    if _instance is None:
        _instance = ConsensusProtocol(bus=bus)
    return _instance
