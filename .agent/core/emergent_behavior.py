"""
Emergent Behavior — detección y amplificación de comportamientos emergentes.

Monitorea el ecosistema buscando patrones emergentes positivos
que no fueron diseñados explícitamente:
  - Pattern detection: descubre combinaciones de agentes/skills efectivas
  - Amplification: refuerza patrones exitosos
  - Suppression: amortigua patrones nocivos
  - Evolution: los patrones evolucionan con el tiempo

Tipos de emergencia:
  - synergy: dos+ agentes trabajan mejor juntos que separados
  - specialization: un agente se vuelve más efectivo en un dominio
  - cascade: un patrón de éxito se propaga entre agentes
  - novelty: un enfoque nuevo no previsto muestra resultados

Usage:
    detector = EmergentBehavior(bus=bus)

    # Registrar observación
    detector.observe(
        agents=["explorer", "architect"],
        pattern="collaborative_analysis",
        effectiveness=0.92,
        context={"task": "complex_refactoring"},
    )

    # Detectar emergencias
    emergent = detector.detect()

    # Amplificar un patrón
    detector.amplify("pattern-id", factor=1.5)

    # Patrones activos
    patterns = detector.get_active_patterns()
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.emergent_behavior")

# ============================================================
# Constantes
# ============================================================
MIN_OBSERVATIONS = 3  # Mínimo para detectar patrón
EMERGENCE_THRESHOLD = 0.7  # Umbral de emergencia
SUPPRESSION_THRESHOLD = 0.3  # Umbral de supresión
AMPLIFICATION_DECAY = 0.95  # Decay del factor de amplificación
MAX_PATTERNS = 100  # Máximo de patrones
MAX_OBSERVATIONS = 2000  # Historial


# ============================================================
# Modelos
# ============================================================
@dataclass
class Observation:
    """Una observación de comportamiento."""

    observation_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agents: list[str] = field(default_factory=list)
    pattern: str = ""
    effectiveness: float = 0.5
    context: dict[str, Any] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "observation_id": self.observation_id,
            "agents": self.agents,
            "pattern": self.pattern,
            "effectiveness": round(self.effectiveness, 3),
            "context": self.context,
            "timestamp": self.timestamp,
        }


@dataclass
class EmergentPattern:
    """Un patrón emergente detectado."""

    pattern_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    name: str = ""
    pattern_type: str = "synergy"  # synergy, specialization, cascade, novelty
    agents: list[str] = field(default_factory=list)
    effectiveness: float = 0.0
    observation_count: int = 0
    amplification: float = 1.0  # Factor de amplificación (>1 = amplificado, <1 = suprimido)
    status: str = "emerging"  # emerging, established, amplified, suppressed
    first_seen: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "pattern_id": self.pattern_id,
            "name": self.name,
            "pattern_type": self.pattern_type,
            "agents": self.agents,
            "effectiveness": round(self.effectiveness, 3),
            "observation_count": self.observation_count,
            "amplification": round(self.amplification, 2),
            "status": self.status,
            "first_seen": self.first_seen,
            "last_seen": self.last_seen,
            "age_seconds": round(time.time() - self.first_seen, 1),
        }


# ============================================================
# Emergent Behavior Detector
# ============================================================
class EmergentBehavior:
    """
    Detector y amplificador de comportamientos emergentes.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus

        # Observaciones
        self._observations: list[Observation] = []

        # Patrones detectados
        self._patterns: dict[str, EmergentPattern] = {}

        # Observaciones agrupadas por key (agentes + pattern)
        self._grouped: dict[str, list[Observation]] = defaultdict(list)

        # Métricas
        self._metrics = {
            "observations_recorded": 0,
            "patterns_detected": 0,
            "patterns_amplified": 0,
            "patterns_suppressed": 0,
            "detections_run": 0,
        }

    # --------------------------------------------------------
    # Observe
    # --------------------------------------------------------
    def observe(
        self,
        agents: list[str],
        pattern: str = "",
        effectiveness: float = 0.5,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Registra una observación de comportamiento."""
        obs = Observation(
            agents=sorted(agents),
            pattern=pattern,
            effectiveness=max(0.0, min(1.0, effectiveness)),
            context=context or {},
        )

        self._observations.append(obs)
        if len(self._observations) > MAX_OBSERVATIONS:
            self._observations = self._observations[-MAX_OBSERVATIONS:]

        # Agrupar
        key = self._make_key(agents, pattern)
        self._grouped[key].append(obs)

        self._metrics["observations_recorded"] += 1
        return obs.to_dict()

    # --------------------------------------------------------
    # Detect
    # --------------------------------------------------------
    def detect(self) -> list[dict[str, Any]]:
        """Detecta patrones emergentes en las observaciones."""
        self._metrics["detections_run"] += 1
        newly_detected = []

        for key, observations in self._grouped.items():
            if len(observations) < MIN_OBSERVATIONS:
                continue

            # Ya existe?
            existing = self._patterns.get(key)
            if existing:
                # Actualizar
                avg_eff = sum(o.effectiveness for o in observations) / len(observations)
                existing.effectiveness = avg_eff
                existing.observation_count = len(observations)
                existing.last_seen = time.time()

                if avg_eff >= EMERGENCE_THRESHOLD and existing.status == "emerging":
                    existing.status = "established"
                continue

            # Nuevo patrón
            avg_eff = sum(o.effectiveness for o in observations) / len(observations)
            if avg_eff < SUPPRESSION_THRESHOLD:
                continue  # No suficientemente bueno

            agents = observations[0].agents
            pattern_name = observations[0].pattern or f"combo_{'+'.join(agents)}"

            pattern_type = self._classify_pattern(agents, observations)

            pattern = EmergentPattern(
                name=pattern_name,
                pattern_type=pattern_type,
                agents=agents,
                effectiveness=avg_eff,
                observation_count=len(observations),
                status="emerging" if avg_eff < EMERGENCE_THRESHOLD else "established",
                first_seen=observations[0].timestamp,
                last_seen=observations[-1].timestamp,
            )
            self._patterns[key] = pattern
            self._metrics["patterns_detected"] += 1
            newly_detected.append(pattern.to_dict())

        return newly_detected

    # --------------------------------------------------------
    # Amplify & Suppress
    # --------------------------------------------------------
    def amplify(
        self,
        pattern_id: str,
        factor: float = 1.5,
    ) -> dict[str, Any] | None:
        """Amplifica un patrón emergente."""
        pattern = self._find_by_id(pattern_id)
        if not pattern:
            return None

        pattern.amplification *= factor
        pattern.status = "amplified"
        self._metrics["patterns_amplified"] += 1

        logger.info("Pattern amplified: %s (factor=%.2f)", pattern.name, pattern.amplification)
        return pattern.to_dict()

    def suppress(
        self,
        pattern_id: str,
        factor: float = 0.5,
    ) -> dict[str, Any] | None:
        """Suprime un patrón."""
        pattern = self._find_by_id(pattern_id)
        if not pattern:
            return None

        pattern.amplification *= factor
        pattern.status = "suppressed"
        self._metrics["patterns_suppressed"] += 1

        logger.info("Pattern suppressed: %s", pattern.name)
        return pattern.to_dict()

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_active_patterns(
        self,
        pattern_type: str | None = None,
        min_effectiveness: float = 0.0,
    ) -> list[dict[str, Any]]:
        """Patrones activos (no suprimidos)."""
        patterns = [p for p in self._patterns.values() if p.status != "suppressed"]
        if pattern_type:
            patterns = [p for p in patterns if p.pattern_type == pattern_type]
        if min_effectiveness > 0:
            patterns = [p for p in patterns if p.effectiveness >= min_effectiveness]
        return [
            p.to_dict()
            for p in sorted(
                patterns,
                key=lambda p: p.effectiveness,
                reverse=True,
            )
        ]

    def get_all_patterns(self) -> list[dict[str, Any]]:
        """Todos los patrones."""
        return [
            p.to_dict()
            for p in sorted(
                self._patterns.values(),
                key=lambda p: p.effectiveness,
                reverse=True,
            )
        ]

    def get_pattern(self, pattern_id: str) -> dict[str, Any] | None:
        """Obtiene un patrón por ID."""
        pattern = self._find_by_id(pattern_id)
        return pattern.to_dict() if pattern else None

    def get_agent_synergies(self, agent: str) -> list[dict[str, Any]]:
        """Sinergias de un agente."""
        synergies = []
        for pattern in self._patterns.values():
            if agent in pattern.agents and pattern.pattern_type == "synergy":
                partners = [a for a in pattern.agents if a != agent]
                synergies.append(
                    {
                        "partners": partners,
                        "effectiveness": round(pattern.effectiveness, 3),
                        "pattern": pattern.name,
                        "status": pattern.status,
                    }
                )
        return sorted(synergies, key=lambda s: s["effectiveness"], reverse=True)

    def get_observations(
        self,
        agent: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Observaciones recientes."""
        obs = self._observations
        if agent:
            obs = [o for o in obs if agent in o.agents]
        return [o.to_dict() for o in obs[-limit:]][::-1]

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas."""
        return {
            "total_observations": len(self._observations),
            "total_patterns": len(self._patterns),
            "emerging": sum(1 for p in self._patterns.values() if p.status == "emerging"),
            "established": sum(1 for p in self._patterns.values() if p.status == "established"),
            "amplified": sum(1 for p in self._patterns.values() if p.status == "amplified"),
            "suppressed": sum(1 for p in self._patterns.values() if p.status == "suppressed"),
            "pattern_types": dict(
                defaultdict(
                    int,
                    {p.pattern_type: 1 for p in self._patterns.values()},
                )
            ),
            "metrics": {**self._metrics},
        }

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _make_key(self, agents: list[str], pattern: str) -> str:
        """Crea key para agrupar observaciones."""
        return f"{'+'.join(sorted(agents))}:{pattern}"

    def _find_by_id(self, pattern_id: str) -> EmergentPattern | None:
        """Busca patrón por ID."""
        for pattern in self._patterns.values():
            if pattern.pattern_id == pattern_id:
                return pattern
        return None

    def _classify_pattern(
        self,
        agents: list[str],
        observations: list[Observation],
    ) -> str:
        """Clasifica el tipo de patrón emergente."""
        if len(agents) >= 2:
            return "synergy"
        if len(agents) == 1:
            # Si todas las observaciones son del mismo dominio
            domains = {
                o.context.get("domain", "unknown") for o in observations if "domain" in o.context
            }
            if len(domains) <= 1:
                return "specialization"
        # Si la effectiveness crece con el tiempo
        if len(observations) >= 3:
            early = sum(o.effectiveness for o in observations[:3]) / 3
            late = sum(o.effectiveness for o in observations[-3:]) / 3
            if late > early * 1.2:
                return "cascade"

        return "novelty"


# ============================================================
# Singleton
# ============================================================
_instance: EmergentBehavior | None = None


def get_emergent_behavior(bus: Any = None) -> EmergentBehavior:
    """Obtiene o crea el detector de comportamientos emergentes."""
    global _instance
    if _instance is None:
        _instance = EmergentBehavior(bus=bus)
    return _instance
