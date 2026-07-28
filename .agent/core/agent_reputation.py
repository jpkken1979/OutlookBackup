"""
Agent Reputation — Motor de confianza y reputación.

Sistema ELO-like que trackea el rendimiento de cada agente por dominio:
  - Cada ejecución exitosa sube el rating, cada fallo lo baja
  - Ratings por dominio (security, frontend, database, etc.)
  - Trust decay temporal (la confianza se degrada si no se usa)
  - Trust propagation (agentes pueden "vouchar" por otros)
  - Feeding directo al router, subastas y consenso
  - Badges de reputación (rookie, reliable, expert, elite, legendary)

Rating System (ELO-inspired):
  - Base rating: 1000
  - K-factor variable: 32 (nuevos) → 16 (establecidos)
  - Success: +K * (1 - expected)
  - Failure: -K * expected
  - Dominio match multiplier: 1.5x si el agente es experto en el dominio

Usage:
    reputation = AgentReputation(bus=bus)

    # Registrar resultado
    reputation.record_outcome("explorer", "code_analysis", success=True, duration=2.5)

    # Consultar confianza
    trust = reputation.get_trust("explorer", domain="code_analysis")
    print(trust.rating)          # 1032
    print(trust.badge)           # "reliable"
    print(trust.confidence)      # 0.85

    # Ranking global
    rankings = reputation.get_rankings(domain="security")

    # Trust propagation
    reputation.vouch("architect", "explorer", domain="architecture", weight=0.8)
"""

import logging
import math
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.agent_reputation")

# ============================================================
# Constantes
# ============================================================
BASE_RATING = 1000
K_FACTOR_NEW = 32  # Agentes con < 10 interacciones
K_FACTOR_ESTABLISHED = 16  # Agentes con >= 10 interacciones
ESTABLISHED_THRESHOLD = 10  # Interacciones para ser "establecido"
TRUST_DECAY_RATE = 0.005  # Rating decae 0.5% por día de inactividad
MAX_DECAY_DAYS = 30  # Máximo días de decay aplicables
VOUCH_WEIGHT = 0.3  # Peso del vouch en el rating
MAX_HISTORY = 500  # Máximo de registros por agente
MIN_RATING = 100  # Floor del rating
MAX_RATING = 3000  # Ceiling del rating


# ============================================================
# Enums
# ============================================================
class ReputationBadge(str, Enum):
    """Badges basados en rating."""

    ROOKIE = "rookie"  # < 800
    DEVELOPING = "developing"  # 800-999
    RELIABLE = "reliable"  # 1000-1199
    EXPERT = "expert"  # 1200-1499
    ELITE = "elite"  # 1500-1999
    LEGENDARY = "legendary"  # >= 2000


class OutcomeType(str, Enum):
    """Tipos de resultado."""

    SUCCESS = "success"
    FAILURE = "failure"
    PARTIAL = "partial"
    TIMEOUT = "timeout"


# ============================================================
# Modelos
# ============================================================
@dataclass
class DomainRating:
    """Rating de un agente en un dominio específico."""

    agent: str
    domain: str
    rating: float = BASE_RATING
    interactions: int = 0
    successes: int = 0
    failures: int = 0
    avg_duration: float = 0.0
    last_active: float = field(default_factory=time.time)
    vouches_received: int = 0

    @property
    def success_rate(self) -> float:
        """Tasa de éxito."""
        if self.interactions == 0:
            return 0.0
        return self.successes / self.interactions

    @property
    def badge(self) -> ReputationBadge:
        """Badge basado en rating actual."""
        if self.rating < 800:
            return ReputationBadge.ROOKIE
        elif self.rating < 1000:
            return ReputationBadge.DEVELOPING
        elif self.rating < 1200:
            return ReputationBadge.RELIABLE
        elif self.rating < 1500:
            return ReputationBadge.EXPERT
        elif self.rating < 2000:
            return ReputationBadge.ELITE
        return ReputationBadge.LEGENDARY

    @property
    def confidence(self) -> float:
        """Confianza normalizada [0, 1] basada en rating e interacciones."""
        # Sigmoid centrado en BASE_RATING
        raw = 1.0 / (1.0 + math.exp(-(self.rating - BASE_RATING) / 200))
        # Ajustar por experiencia (más interacciones = más confianza)
        experience_factor = min(1.0, self.interactions / 20)
        return round(raw * (0.5 + 0.5 * experience_factor), 3)

    @property
    def k_factor(self) -> float:
        """K-factor según experiencia."""
        if self.interactions < ESTABLISHED_THRESHOLD:
            return K_FACTOR_NEW
        return K_FACTOR_ESTABLISHED

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "domain": self.domain,
            "rating": round(self.rating, 1),
            "badge": self.badge.value,
            "confidence": self.confidence,
            "interactions": self.interactions,
            "successes": self.successes,
            "failures": self.failures,
            "success_rate": round(self.success_rate, 3),
            "avg_duration": round(self.avg_duration, 2),
            "last_active": self.last_active,
            "days_inactive": round((time.time() - self.last_active) / 86400, 1),
        }


@dataclass
class OutcomeRecord:
    """Registro de un resultado."""

    record_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: str = ""
    domain: str = ""
    outcome: OutcomeType = OutcomeType.SUCCESS
    rating_before: float = BASE_RATING
    rating_after: float = BASE_RATING
    delta: float = 0.0
    duration: float = 0.0
    timestamp: float = field(default_factory=time.time)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "record_id": self.record_id,
            "agent": self.agent,
            "domain": self.domain,
            "outcome": self.outcome.value,
            "rating_before": round(self.rating_before, 1),
            "rating_after": round(self.rating_after, 1),
            "delta": round(self.delta, 1),
            "duration": round(self.duration, 2),
            "timestamp": self.timestamp,
        }


@dataclass
class VouchRecord:
    """Registro de un vouch entre agentes."""

    voucher: str
    vouchee: str
    domain: str
    weight: float = 0.5
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "voucher": self.voucher,
            "vouchee": self.vouchee,
            "domain": self.domain,
            "weight": self.weight,
            "timestamp": self.timestamp,
        }


# ============================================================
# Domain Detector
# ============================================================
class DomainDetector:
    """Detecta el dominio relevante de una tarea o contexto."""

    DOMAIN_KEYWORDS: dict[str, list[str]] = {
        "security": [
            "security",
            "auth",
            "token",
            "jwt",
            "oauth",
            "vulnerability",
            "encrypt",
            "permission",
            "audit",
            "firewall",
            "xss",
            "injection",
        ],
        "frontend": [
            "react",
            "css",
            "html",
            "ui",
            "ux",
            "component",
            "tailwind",
            "responsive",
            "layout",
            "animation",
            "dom",
            "browser",
        ],
        "backend": [
            "api",
            "endpoint",
            "server",
            "rest",
            "graphql",
            "middleware",
            "route",
            "handler",
            "controller",
            "microservice",
        ],
        "database": [
            "sql",
            "query",
            "table",
            "migration",
            "schema",
            "index",
            "postgres",
            "sqlite",
            "redis",
            "orm",
            "database",
        ],
        "testing": [
            "test",
            "pytest",
            "coverage",
            "mock",
            "fixture",
            "assertion",
            "unit",
            "integration",
            "e2e",
            "tdd",
        ],
        "devops": [
            "docker",
            "ci",
            "cd",
            "deploy",
            "kubernetes",
            "pipeline",
            "container",
            "nginx",
            "monitoring",
            "infrastructure",
        ],
        "code_analysis": [
            "refactor",
            "analyze",
            "review",
            "lint",
            "pattern",
            "architecture",
            "dependency",
            "complexity",
            "smell",
        ],
        "documentation": [
            "doc",
            "readme",
            "comment",
            "guide",
            "tutorial",
            "reference",
            "changelog",
            "api-doc",
        ],
        "performance": [
            "performance",
            "optimize",
            "cache",
            "latency",
            "throughput",
            "memory",
            "cpu",
            "bottleneck",
            "profil",
        ],
    }

    @classmethod
    def detect(cls, text: str) -> str:
        """Detecta el dominio principal de un texto."""
        text_lower = text.lower()
        scores: dict[str, int] = {}
        for domain, keywords in cls.DOMAIN_KEYWORDS.items():
            scores[domain] = sum(1 for kw in keywords if kw in text_lower)

        if not scores or max(scores.values()) == 0:
            return "general"
        return max(scores, key=lambda d: scores[d])

    @classmethod
    def detect_all(cls, text: str) -> list[str]:
        """Detecta todos los dominios relevantes."""
        text_lower = text.lower()
        results = []
        for domain, keywords in cls.DOMAIN_KEYWORDS.items():
            if any(kw in text_lower for kw in keywords):
                results.append(domain)
        return results or ["general"]


# ============================================================
# Agent Reputation
# ============================================================
class AgentReputation:
    """
    Motor de confianza y reputación para agentes.
    Rating ELO-like por agente y dominio.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus

        # ratings[agent][domain] = DomainRating
        self._ratings: dict[str, dict[str, DomainRating]] = defaultdict(dict)

        # Historial de outcomes
        self._history: list[OutcomeRecord] = []

        # Vouches
        self._vouches: list[VouchRecord] = []

        # Métricas
        self._metrics = {
            "outcomes_recorded": 0,
            "vouches_given": 0,
            "agents_tracked": 0,
            "domains_tracked": 0,
        }

    # --------------------------------------------------------
    # Core: Record Outcome
    # --------------------------------------------------------
    def record_outcome(
        self,
        agent: str,
        domain: str,
        success: bool = True,
        duration: float = 0.0,
        partial: bool = False,
        timeout: bool = False,
        metadata: dict[str, Any] | None = None,
    ) -> OutcomeRecord:
        """
        Registra el resultado de una ejecución.

        Args:
            agent: Nombre del agente.
            domain: Dominio de la tarea.
            success: Si la ejecución fue exitosa.
            duration: Duración en segundos.
            partial: Si fue un éxito parcial.
            timeout: Si fue un timeout.
            metadata: Datos adicionales.

        Returns:
            OutcomeRecord con el delta de rating.
        """
        rating = self._get_or_create_rating(agent, domain)
        rating_before = rating.rating

        # Aplicar trust decay antes de calcular
        self._apply_decay(rating)

        # Determinar outcome type
        if timeout:
            outcome = OutcomeType.TIMEOUT
            actual_score = 0.2  # Timeout es mejor que fallo total
        elif partial:
            outcome = OutcomeType.PARTIAL
            actual_score = 0.6
        elif success:
            outcome = OutcomeType.SUCCESS
            actual_score = 1.0
        else:
            outcome = OutcomeType.FAILURE
            actual_score = 0.0

        # ELO calculation
        expected = 1.0 / (1.0 + math.pow(10, (BASE_RATING - rating.rating) / 400))
        delta = rating.k_factor * (actual_score - expected)

        # Aplicar delta
        rating.rating = max(MIN_RATING, min(MAX_RATING, rating.rating + delta))
        rating.interactions += 1
        rating.last_active = time.time()

        if success or partial:
            rating.successes += 1
        else:
            rating.failures += 1

        # Update average duration (EMA)
        if duration > 0:
            if rating.avg_duration == 0:
                rating.avg_duration = duration
            else:
                alpha = 0.3
                rating.avg_duration = alpha * duration + (1 - alpha) * rating.avg_duration

        # Crear registro
        record = OutcomeRecord(
            agent=agent,
            domain=domain,
            outcome=outcome,
            rating_before=rating_before,
            rating_after=rating.rating,
            delta=delta,
            duration=duration,
            metadata=metadata or {},
        )

        self._history.append(record)
        if len(self._history) > MAX_HISTORY:
            self._history = self._history[-MAX_HISTORY:]

        self._metrics["outcomes_recorded"] += 1
        self._update_tracking_metrics()

        logger.debug(
            "Reputation %s@%s: %.0f → %.0f (%+.1f) [%s]",
            agent,
            domain,
            rating_before,
            rating.rating,
            delta,
            outcome.value,
        )

        return record

    # --------------------------------------------------------
    # Trust Query
    # --------------------------------------------------------
    def get_trust(
        self,
        agent: str,
        domain: str = "general",
    ) -> DomainRating:
        """
        Obtiene el trust de un agente en un dominio.

        Returns:
            DomainRating con el estado actual.
        """
        rating = self._get_or_create_rating(agent, domain)
        self._apply_decay(rating)
        return rating

    def get_trust_score(self, agent: str, domain: str = "general") -> float:
        """Shortcut: retorna solo el confidence [0, 1]."""
        return self.get_trust(agent, domain).confidence

    def get_agent_profile(self, agent: str) -> dict[str, Any]:
        """Perfil completo de un agente con todos sus dominios."""
        domains = self._ratings.get(agent, {})
        if not domains:
            return {
                "agent": agent,
                "domains": {},
                "overall_rating": BASE_RATING,
                "overall_badge": ReputationBadge.RELIABLE.value,
                "total_interactions": 0,
            }

        total_rating = 0.0
        total_interactions = 0
        domain_data = {}

        for domain, rating in domains.items():
            self._apply_decay(rating)
            domain_data[domain] = rating.to_dict()
            total_rating += rating.rating * rating.interactions
            total_interactions += rating.interactions

        overall = total_rating / total_interactions if total_interactions > 0 else BASE_RATING

        # Badge del overall
        temp = DomainRating(agent=agent, domain="overall", rating=overall)

        return {
            "agent": agent,
            "domains": domain_data,
            "overall_rating": round(overall, 1),
            "overall_badge": temp.badge.value,
            "total_interactions": total_interactions,
        }

    # --------------------------------------------------------
    # Rankings
    # --------------------------------------------------------
    def get_rankings(
        self,
        domain: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """
        Ranking de agentes, opcionalmente por dominio.

        Args:
            domain: Si se especifica, ranking en ese dominio.
            limit: Máximo de resultados.

        Returns:
            Lista ordenada por rating descendente.
        """
        if domain:
            rankings = []
            for agent, domains in self._ratings.items():
                if domain in domains:
                    r = domains[domain]
                    self._apply_decay(r)
                    rankings.append(r.to_dict())
            rankings.sort(key=lambda x: x["rating"], reverse=True)
            return rankings[:limit]

        # Overall ranking
        profiles = []
        for agent in self._ratings:
            profile = self.get_agent_profile(agent)
            profiles.append(profile)
        profiles.sort(key=lambda x: x["overall_rating"], reverse=True)
        return profiles[:limit]

    # --------------------------------------------------------
    # Trust Propagation (Vouching)
    # --------------------------------------------------------
    def vouch(
        self,
        voucher: str,
        vouchee: str,
        domain: str,
        weight: float = 0.5,
    ) -> VouchRecord | None:
        """
        Un agente "voucha" por otro en un dominio.

        El rating del vouchee sube proporcionalmente al rating
        del voucher y el peso del vouch.

        Args:
            voucher: Agente que da el vouch.
            vouchee: Agente que recibe el vouch.
            domain: Dominio del vouch.
            weight: Peso del vouch [0, 1].

        Returns:
            VouchRecord o None si el vouch es inválido.
        """
        if voucher == vouchee:
            return None

        weight = max(0.0, min(1.0, weight))

        voucher_rating = self._get_or_create_rating(voucher, domain)
        vouchee_rating = self._get_or_create_rating(vouchee, domain)

        # El boost depende del rating del voucher
        voucher_credibility = voucher_rating.confidence
        boost = VOUCH_WEIGHT * weight * voucher_credibility * voucher_rating.k_factor

        vouchee_rating.rating = min(MAX_RATING, vouchee_rating.rating + boost)
        vouchee_rating.vouches_received += 1

        record = VouchRecord(
            voucher=voucher,
            vouchee=vouchee,
            domain=domain,
            weight=weight,
        )
        self._vouches.append(record)
        self._metrics["vouches_given"] += 1

        logger.debug(
            "Vouch: %s → %s@%s (boost: +%.1f)",
            voucher,
            vouchee,
            domain,
            boost,
        )

        return record

    # --------------------------------------------------------
    # Integration Helpers (para router, subastas, consenso)
    # --------------------------------------------------------
    def get_weight_for_router(self, agent: str, task: str) -> float:
        """Peso de confianza para el router inteligente."""
        domain = DomainDetector.detect(task)
        return self.get_trust_score(agent, domain)

    def get_weight_for_auction(self, agent: str, task: str) -> float:
        """Peso de confianza para subastas/negociación."""
        domain = DomainDetector.detect(task)
        rating = self.get_trust(agent, domain)
        # Combinar confidence con success_rate
        if rating.interactions == 0:
            return 0.5
        return round(0.6 * rating.confidence + 0.4 * rating.success_rate, 3)

    def get_weight_for_consensus(self, agent: str, question: str) -> float:
        """Peso de confianza para votación de consenso."""
        domain = DomainDetector.detect(question)
        return self.get_trust_score(agent, domain)

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema de reputación."""
        self._update_tracking_metrics()
        return {
            "metrics": {**self._metrics},
            "total_agents": len(self._ratings),
            "total_outcomes": len(self._history),
            "total_vouches": len(self._vouches),
        }

    def get_history(
        self,
        agent: str | None = None,
        domain: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de outcomes filtrado."""
        records = self._history
        if agent:
            records = [r for r in records if r.agent == agent]
        if domain:
            records = [r for r in records if r.domain == domain]
        return [r.to_dict() for r in records[-limit:]][::-1]

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _get_or_create_rating(self, agent: str, domain: str) -> DomainRating:
        """Obtiene o crea un DomainRating."""
        if domain not in self._ratings[agent]:
            self._ratings[agent][domain] = DomainRating(agent=agent, domain=domain)
        return self._ratings[agent][domain]

    def _apply_decay(self, rating: DomainRating) -> None:
        """Aplica trust decay basado en inactividad."""
        days_inactive = (time.time() - rating.last_active) / 86400
        if days_inactive < 1:
            return  # No decay dentro del primer día

        days_to_apply = min(days_inactive, MAX_DECAY_DAYS)
        decay = 1.0 - (TRUST_DECAY_RATE * days_to_apply)
        decayed_rating = rating.rating * decay

        # No bajar por debajo de MIN_RATING
        rating.rating = max(MIN_RATING, decayed_rating)

    def _update_tracking_metrics(self) -> None:
        """Actualiza métricas de tracking."""
        self._metrics["agents_tracked"] = len(self._ratings)
        domains: set[str] = set()
        for agent_domains in self._ratings.values():
            domains.update(agent_domains.keys())
        self._metrics["domains_tracked"] = len(domains)


# ============================================================
# Singleton
# ============================================================
_instance: AgentReputation | None = None


def get_agent_reputation(bus: Any = None) -> AgentReputation:
    """Obtiene o crea el sistema de reputación global."""
    global _instance
    if _instance is None:
        _instance = AgentReputation(bus=bus)
    return _instance
