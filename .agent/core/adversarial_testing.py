"""
Adversarial Testing — Red Team / Blue Team para agentes.

Agentes desafían a otros agentes con challenges difíciles:
  - Red Team (Challenger): genera edge cases y escenarios adversos
  - Blue Team (Defender): intenta resolver los challenges correctamente
  - Referee: evalúa resultados y asigna puntos
  - Los resultados alimentan reputation + genome fitness

Tipos de challenge:
  - edge_case: escenarios límite
  - stress: carga y volumen
  - ambiguity: instrucciones ambiguas
  - contradiction: requisitos contradictorios
  - novel: dominio desconocido para el defender

Usage:
    arena = AdversarialArena(bus=bus)

    # Crear challenge
    challenge = arena.create_challenge(
        challenger="security-auditor",
        defender="explorer",
        challenge_type="edge_case",
        description="Handle circular dependency in imports",
        difficulty=0.8,
    )

    # Registrar respuesta
    arena.submit_response(challenge_id, success=True, quality=0.9)

    # Ver rankings
    rankings = arena.get_rankings()

    # Historial de batallas
    history = arena.get_battle_history()
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger("antigravity.adversarial_testing")

# ============================================================
# Constantes
# ============================================================
MAX_CHALLENGES_PER_AGENT = 200  # Historial por agente
MAX_BATTLE_HISTORY = 500  # Historial global
DIFFICULTY_LEVELS = {
    "trivial": 0.2,
    "easy": 0.4,
    "medium": 0.6,
    "hard": 0.8,
    "extreme": 1.0,
}
ELO_K_FACTOR = 32  # Factor K para cálculo ELO
ELO_DEFAULT = 1200  # ELO inicial


# ============================================================
# Enums
# ============================================================
class ChallengeType(str, Enum):
    """Tipos de challenge."""

    EDGE_CASE = "edge_case"
    STRESS = "stress"
    AMBIGUITY = "ambiguity"
    CONTRADICTION = "contradiction"
    NOVEL = "novel"


class ChallengeStatus(str, Enum):
    """Estados del challenge."""

    PENDING = "pending"
    RESPONDED = "responded"
    EVALUATED = "evaluated"
    EXPIRED = "expired"


class BattleOutcome(str, Enum):
    """Resultado de la batalla."""

    DEFENDER_WINS = "defender_wins"
    CHALLENGER_WINS = "challenger_wins"
    DRAW = "draw"


# ============================================================
# Modelos
# ============================================================
@dataclass
class Challenge:
    """Un challenge adversarial."""

    challenge_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    challenger: str = ""
    defender: str = ""
    challenge_type: ChallengeType = ChallengeType.EDGE_CASE
    description: str = ""
    difficulty: float = 0.5
    status: ChallengeStatus = ChallengeStatus.PENDING
    response_success: bool | None = None
    response_quality: float = 0.0
    outcome: BattleOutcome | None = None
    challenger_points: float = 0.0
    defender_points: float = 0.0
    created_at: float = field(default_factory=time.time)
    responded_at: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "challenge_id": self.challenge_id,
            "challenger": self.challenger,
            "defender": self.defender,
            "challenge_type": self.challenge_type.value,
            "description": self.description,
            "difficulty": round(self.difficulty, 2),
            "status": self.status.value,
            "response_success": self.response_success,
            "response_quality": round(self.response_quality, 3),
            "outcome": self.outcome.value if self.outcome else None,
            "challenger_points": round(self.challenger_points, 2),
            "defender_points": round(self.defender_points, 2),
            "created_at": self.created_at,
        }


@dataclass
class AgentProfile:
    """Perfil adversarial de un agente."""

    agent: str
    elo: float = ELO_DEFAULT
    challenges_issued: int = 0
    challenges_received: int = 0
    wins_as_challenger: int = 0
    wins_as_defender: int = 0
    draws: int = 0
    total_points: float = 0.0
    domains_strong: list[str] = field(default_factory=list)
    domains_weak: list[str] = field(default_factory=list)

    @property
    def total_battles(self) -> int:
        return self.challenges_issued + self.challenges_received

    @property
    def win_rate(self) -> float:
        total = self.wins_as_challenger + self.wins_as_defender + self.draws
        if total == 0:
            return 0.0
        return (self.wins_as_challenger + self.wins_as_defender) / total

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "elo": round(self.elo, 1),
            "challenges_issued": self.challenges_issued,
            "challenges_received": self.challenges_received,
            "wins_as_challenger": self.wins_as_challenger,
            "wins_as_defender": self.wins_as_defender,
            "draws": self.draws,
            "total_battles": self.total_battles,
            "win_rate": round(self.win_rate, 3),
            "total_points": round(self.total_points, 2),
            "domains_strong": self.domains_strong,
            "domains_weak": self.domains_weak,
        }


# ============================================================
# Adversarial Arena
# ============================================================
class AdversarialArena:
    """
    Arena de testing adversarial.
    Agentes se desafían mutuamente para mejorar la calidad del sistema.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus

        # Challenges activos e historial
        self._challenges: dict[str, Challenge] = {}  # challenge_id -> Challenge
        self._battle_history: list[Challenge] = []

        # Perfiles por agente
        self._profiles: dict[str, AgentProfile] = {}

        # Challenge history por agente
        self._agent_challenges: dict[str, list[str]] = defaultdict(list)

        # Métricas
        self._metrics = {
            "challenges_created": 0,
            "responses_submitted": 0,
            "defender_wins": 0,
            "challenger_wins": 0,
            "draws": 0,
            "avg_difficulty": 0.0,
            "avg_quality": 0.0,
        }

    # --------------------------------------------------------
    # Create Challenge
    # --------------------------------------------------------
    def create_challenge(
        self,
        challenger: str,
        defender: str,
        challenge_type: str = "edge_case",
        description: str = "",
        difficulty: float = 0.5,
        domain: str = "general",
    ) -> dict[str, Any]:
        """
        Crea un challenge adversarial.

        Args:
            challenger: Agente que desafía (red team).
            defender: Agente que defiende (blue team).
            challenge_type: Tipo de challenge.
            description: Descripción del desafío.
            difficulty: Dificultad [0, 1].
            domain: Dominio del challenge.

        Returns:
            El challenge creado.
        """
        try:
            c_type = ChallengeType(challenge_type)
        except ValueError:
            c_type = ChallengeType.EDGE_CASE

        challenge = Challenge(
            challenger=challenger,
            defender=defender,
            challenge_type=c_type,
            description=description,
            difficulty=max(0.0, min(1.0, difficulty)),
        )

        self._challenges[challenge.challenge_id] = challenge
        self._agent_challenges[challenger].append(challenge.challenge_id)
        self._agent_challenges[defender].append(challenge.challenge_id)

        # Actualizar perfiles
        c_profile = self._get_or_create_profile(challenger)
        d_profile = self._get_or_create_profile(defender)
        c_profile.challenges_issued += 1
        d_profile.challenges_received += 1

        self._metrics["challenges_created"] += 1
        self._update_avg_difficulty(difficulty)

        logger.info(
            "Challenge created: %s vs %s (type=%s, diff=%.1f)",
            challenger,
            defender,
            challenge_type,
            difficulty,
        )

        return challenge.to_dict()

    # --------------------------------------------------------
    # Submit Response
    # --------------------------------------------------------
    def submit_response(
        self,
        challenge_id: str,
        success: bool = True,
        quality: float = 0.5,
    ) -> dict[str, Any]:
        """
        Registra la respuesta del defender a un challenge.

        Args:
            challenge_id: ID del challenge.
            success: Si el defender resolvió correctamente.
            quality: Calidad de la respuesta [0, 1].

        Returns:
            El challenge evaluado con outcome.
        """
        challenge = self._challenges.get(challenge_id)
        if not challenge:
            return {"error": "Challenge not found"}

        challenge.response_success = success
        challenge.response_quality = max(0.0, min(1.0, quality))
        challenge.responded_at = time.time()
        challenge.status = ChallengeStatus.EVALUATED

        # Evaluar resultado
        outcome = self._evaluate(challenge)
        challenge.outcome = outcome

        # Calcular puntos
        self._award_points(challenge)

        # Actualizar ELO
        self._update_elo(challenge)

        # Mover a historial
        self._battle_history.append(challenge)
        if len(self._battle_history) > MAX_BATTLE_HISTORY:
            self._battle_history = self._battle_history[-MAX_BATTLE_HISTORY:]

        self._metrics["responses_submitted"] += 1
        self._update_avg_quality(quality)

        logger.info(
            "Challenge %s evaluated: %s (quality=%.2f)",
            challenge_id,
            outcome.value,
            quality,
        )

        return challenge.to_dict()

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_challenge(self, challenge_id: str) -> dict[str, Any] | None:
        """Obtiene un challenge."""
        challenge = self._challenges.get(challenge_id)
        return challenge.to_dict() if challenge else None

    def get_pending_challenges(
        self,
        defender: str | None = None,
    ) -> list[dict[str, Any]]:
        """Challenges pendientes."""
        pending = [c for c in self._challenges.values() if c.status == ChallengeStatus.PENDING]
        if defender:
            pending = [c for c in pending if c.defender == defender]
        return [c.to_dict() for c in pending]

    def get_battle_history(
        self,
        agent: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de batallas."""
        battles = self._battle_history
        if agent:
            battles = [b for b in battles if b.challenger == agent or b.defender == agent]
        return [b.to_dict() for b in battles[-limit:]][::-1]

    def get_profile(self, agent: str) -> dict[str, Any]:
        """Perfil adversarial de un agente."""
        profile = self._get_or_create_profile(agent)
        return profile.to_dict()

    def get_rankings(self, sort_by: str = "elo") -> list[dict[str, Any]]:
        """Rankings de agentes."""
        profiles = list(self._profiles.values())

        if sort_by == "elo":
            profiles.sort(key=lambda p: p.elo, reverse=True)
        elif sort_by == "wins":
            profiles.sort(
                key=lambda p: p.wins_as_challenger + p.wins_as_defender,
                reverse=True,
            )
        elif sort_by == "points":
            profiles.sort(key=lambda p: p.total_points, reverse=True)
        else:
            profiles.sort(key=lambda p: p.elo, reverse=True)

        return [{**p.to_dict(), "rank": i + 1} for i, p in enumerate(profiles)]

    def get_matchups(self) -> list[dict[str, Any]]:
        """
        Sugiere matchups interesantes basados en ELO similar
        y dominios complementarios.
        """
        profiles = list(self._profiles.values())
        if len(profiles) < 2:
            return []

        matchups = []
        seen = set()
        profiles.sort(key=lambda p: p.elo)

        for i in range(len(profiles)):
            for j in range(i + 1, min(i + 3, len(profiles))):
                pair = (profiles[i].agent, profiles[j].agent)
                if pair in seen:
                    continue
                seen.add(pair)

                elo_diff = abs(profiles[i].elo - profiles[j].elo)
                matchups.append(
                    {
                        "challenger": profiles[j].agent,
                        "defender": profiles[i].agent,
                        "elo_diff": round(elo_diff, 1),
                        "suggested_type": self._suggest_type(profiles[i], profiles[j]),
                    }
                )

        return matchups[:10]

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas de la arena."""
        return {
            "total_challenges": len(self._battle_history),
            "pending": sum(
                1 for c in self._challenges.values() if c.status == ChallengeStatus.PENDING
            ),
            "profiles": len(self._profiles),
            "top_elo": round(
                max((p.elo for p in self._profiles.values()), default=ELO_DEFAULT),
                1,
            ),
            "metrics": {**self._metrics},
        }

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _get_or_create_profile(self, agent: str) -> AgentProfile:
        """Obtiene o crea perfil."""
        if agent not in self._profiles:
            self._profiles[agent] = AgentProfile(agent=agent)
        return self._profiles[agent]

    def _evaluate(self, challenge: Challenge) -> BattleOutcome:
        """Evalúa el resultado de un challenge."""
        if not challenge.response_success:
            return BattleOutcome.CHALLENGER_WINS

        # Success + high quality = defender wins
        if challenge.response_quality >= 0.7:
            return BattleOutcome.DEFENDER_WINS

        # Success but low quality on hard challenge = draw
        if challenge.difficulty >= 0.7 and challenge.response_quality >= 0.4:
            return BattleOutcome.DRAW

        # Success with mediocre quality on easy challenge = defender wins anyway
        if challenge.difficulty < 0.5:
            return BattleOutcome.DEFENDER_WINS

        return BattleOutcome.DRAW

    def _award_points(self, challenge: Challenge) -> None:
        """Asigna puntos según resultado."""
        c_profile = self._get_or_create_profile(challenge.challenger)
        d_profile = self._get_or_create_profile(challenge.defender)

        base_points = challenge.difficulty * 10

        if challenge.outcome == BattleOutcome.DEFENDER_WINS:
            # Defender gana: puntos por resolver + bonus por dificultad
            d_points = base_points * (1 + challenge.response_quality)
            c_points = base_points * 0.3  # Challenger aún gana algo por crear buen challenge
            d_profile.wins_as_defender += 1
            self._metrics["defender_wins"] += 1
        elif challenge.outcome == BattleOutcome.CHALLENGER_WINS:
            # Challenger gana: encontró una debilidad
            c_points = base_points * 1.5
            d_points = base_points * 0.1  # Poco por fallar
            c_profile.wins_as_challenger += 1
            self._metrics["challenger_wins"] += 1
        else:
            # Draw: ambos ganan algo
            c_points = base_points * 0.5
            d_points = base_points * 0.5
            c_profile.draws += 1
            d_profile.draws += 1
            self._metrics["draws"] += 1

        challenge.challenger_points = c_points
        challenge.defender_points = d_points
        c_profile.total_points += c_points
        d_profile.total_points += d_points

    def _update_elo(self, challenge: Challenge) -> None:
        """Actualiza ELO de ambos jugadores."""
        c_profile = self._get_or_create_profile(challenge.challenger)
        d_profile = self._get_or_create_profile(challenge.defender)

        # Expected scores
        ec = 1 / (1 + 10 ** ((d_profile.elo - c_profile.elo) / 400))
        ed = 1 - ec

        # Actual scores
        if challenge.outcome == BattleOutcome.CHALLENGER_WINS:
            sc, sd = 1.0, 0.0
        elif challenge.outcome == BattleOutcome.DEFENDER_WINS:
            sc, sd = 0.0, 1.0
        else:
            sc, sd = 0.5, 0.5

        c_profile.elo += ELO_K_FACTOR * (sc - ec)
        d_profile.elo += ELO_K_FACTOR * (sd - ed)

    def _suggest_type(
        self,
        profile_a: AgentProfile,
        profile_b: AgentProfile,
    ) -> str:
        """Sugiere tipo de challenge para un matchup."""
        # Prefer types where the weaker player might struggle
        if profile_a.wins_as_defender < profile_a.challenges_received * 0.5:
            return ChallengeType.STRESS.value
        if profile_b.elo > profile_a.elo + 100:
            return ChallengeType.EDGE_CASE.value
        return ChallengeType.AMBIGUITY.value

    def _update_avg_difficulty(self, new_difficulty: float) -> None:
        """Actualiza dificultad promedio."""
        total = self._metrics["challenges_created"]
        old_avg = self._metrics["avg_difficulty"]
        self._metrics["avg_difficulty"] = round(
            (old_avg * (total - 1) + new_difficulty) / total,
            3,
        )

    def _update_avg_quality(self, new_quality: float) -> None:
        """Actualiza calidad promedio."""
        total = self._metrics["responses_submitted"]
        old_avg = self._metrics["avg_quality"]
        self._metrics["avg_quality"] = round(
            (old_avg * (total - 1) + new_quality) / total,
            3,
        )


# ============================================================
# Singleton
# ============================================================
_instance: AdversarialArena | None = None


def get_adversarial_arena(bus: Any = None) -> AdversarialArena:
    """Obtiene o crea la arena adversarial global."""
    global _instance
    if _instance is None:
        _instance = AdversarialArena(bus=bus)
    return _instance
