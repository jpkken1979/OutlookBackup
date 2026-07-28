"""
Knowledge Distillation — Learning Transfer entre agentes.

Cuando un agente tiene éxito en un dominio, destila el conocimiento
(patrones, configs efectivas, estrategias) y lo comparte con agentes
del mismo tier o dominios relacionados.

Conceptos:
  - Knowledge Unit: pieza atómica de conocimiento destilado
  - Distillation: proceso de extraer y comprimir conocimiento
  - Transfer: entrega de conocimiento a agentes receptores
  - Absorption: el receptor integra y evalúa el conocimiento
  - Affinity: qué tan relevante es el conocimiento para un receptor

Usage:
    distiller = KnowledgeDistiller(bus=bus)

    # Destilar conocimiento de un éxito
    distiller.distill(
        source="explorer",
        domain="code_analysis",
        pattern="recursive_dependency_detection",
        effectiveness=0.92,
        context={"depth": 3, "strategy": "bottom_up"},
    )

    # Transferir a agentes relevantes
    transfers = distiller.transfer(source="explorer")

    # Ver qué sabe un agente
    knowledge = distiller.get_knowledge("architect")

    # Estadísticas de absorción
    stats = distiller.get_absorption_stats()
"""

import logging
import time
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.knowledge_distillation")

# ============================================================
# Constantes
# ============================================================
MAX_KNOWLEDGE_PER_AGENT = 100  # Máximo de unidades por agente
AFFINITY_THRESHOLD = 0.3  # Mínima afinidad para transferir
KNOWLEDGE_DECAY = 0.99  # Decaimiento por ciclo
MAX_TRANSFER_HISTORY = 500  # Historial de transferencias
EFFECTIVENESS_BOOST = 0.1  # Boost si el conocimiento se usa con éxito

# Afinidades entre dominios (cuánto se beneficia uno del otro)
DOMAIN_AFFINITY: dict[str, dict[str, float]] = {
    "code_analysis": {"architecture": 0.8, "security": 0.6, "testing": 0.7, "debugging": 0.9},
    "architecture": {"code_analysis": 0.7, "security": 0.5, "devops": 0.6, "performance": 0.7},
    "security": {"code_analysis": 0.6, "architecture": 0.5, "testing": 0.7, "devops": 0.4},
    "testing": {"code_analysis": 0.7, "debugging": 0.8, "security": 0.5, "performance": 0.5},
    "debugging": {"code_analysis": 0.9, "testing": 0.7, "performance": 0.6, "architecture": 0.4},
    "performance": {"architecture": 0.6, "code_analysis": 0.5, "devops": 0.7, "debugging": 0.5},
    "devops": {"architecture": 0.5, "security": 0.6, "performance": 0.5, "testing": 0.4},
    "frontend": {"ui_ux": 0.9, "testing": 0.5, "performance": 0.6, "a11y": 0.7},
    "ui_ux": {"frontend": 0.9, "a11y": 0.8, "performance": 0.4},
    "a11y": {"frontend": 0.7, "ui_ux": 0.8, "testing": 0.5},
}


# ============================================================
# Modelos
# ============================================================
@dataclass
class KnowledgeUnit:
    """Pieza atómica de conocimiento destilado."""

    unit_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source_agent: str = ""
    domain: str = "general"
    pattern: str = ""  # Nombre del patrón/estrategia
    effectiveness: float = 0.5  # Qué tan efectivo fue [0, 1]
    context: dict[str, Any] = field(default_factory=dict)
    usage_count: int = 0  # Veces que fue usado por receptores
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "unit_id": self.unit_id,
            "source_agent": self.source_agent,
            "domain": self.domain,
            "pattern": self.pattern,
            "effectiveness": round(self.effectiveness, 3),
            "context": self.context,
            "usage_count": self.usage_count,
            "created_at": self.created_at,
        }


@dataclass
class TransferRecord:
    """Registro de una transferencia de conocimiento."""

    transfer_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    source: str = ""
    target: str = ""
    unit_id: str = ""
    domain: str = ""
    affinity: float = 0.0
    absorbed: bool = False  # Si el receptor lo integró
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "transfer_id": self.transfer_id,
            "source": self.source,
            "target": self.target,
            "unit_id": self.unit_id,
            "domain": self.domain,
            "affinity": round(self.affinity, 3),
            "absorbed": self.absorbed,
            "timestamp": self.timestamp,
        }


# ============================================================
# Knowledge Distiller
# ============================================================
class KnowledgeDistiller:
    """
    Motor de destilación y transferencia de conocimiento.
    Permite que agentes compartan aprendizajes de forma automática.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus

        # Conocimiento por agente: agent -> list[KnowledgeUnit]
        self._knowledge: dict[str, list[KnowledgeUnit]] = defaultdict(list)

        # Dominios por agente (para calcular afinidad)
        self._agent_domains: dict[str, set[str]] = defaultdict(set)

        # Historial de transferencias
        self._transfers: list[TransferRecord] = []

        # Métricas
        self._metrics = {
            "units_distilled": 0,
            "transfers_attempted": 0,
            "transfers_absorbed": 0,
            "cross_domain_transfers": 0,
            "knowledge_reused": 0,
        }

    # --------------------------------------------------------
    # Distill
    # --------------------------------------------------------
    def distill(
        self,
        source: str,
        domain: str = "general",
        pattern: str = "",
        effectiveness: float = 0.5,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """
        Destila conocimiento de un agente exitoso.

        Args:
            source: Agente que generó el conocimiento.
            domain: Dominio del conocimiento.
            pattern: Nombre del patrón/estrategia.
            effectiveness: Efectividad [0, 1].
            context: Contexto adicional.

        Returns:
            La unidad de conocimiento creada.
        """
        unit = KnowledgeUnit(
            source_agent=source,
            domain=domain,
            pattern=pattern,
            effectiveness=max(0.0, min(1.0, effectiveness)),
            context=context or {},
        )

        self._knowledge[source].append(unit)
        self._agent_domains[source].add(domain)

        # Limitar por agente
        if len(self._knowledge[source]) > MAX_KNOWLEDGE_PER_AGENT:
            # Eliminar la menos efectiva
            self._knowledge[source].sort(key=lambda u: u.effectiveness)
            self._knowledge[source].pop(0)

        self._metrics["units_distilled"] += 1

        logger.info(
            "Knowledge distilled: %s in %s (pattern=%s, eff=%.2f)",
            source,
            domain,
            pattern,
            effectiveness,
        )

        return unit.to_dict()

    # --------------------------------------------------------
    # Transfer
    # --------------------------------------------------------
    def transfer(
        self,
        source: str,
        targets: list[str] | None = None,
        domain: str | None = None,
    ) -> list[dict[str, Any]]:
        """
        Transfiere conocimiento del source a targets relevantes.

        Si no se especifican targets, transfiere a todos los agentes
        con afinidad suficiente.

        Returns:
            Lista de transferencias realizadas.
        """
        source_units = self._knowledge.get(source, [])
        if not source_units:
            return []

        if domain:
            source_units = [u for u in source_units if u.domain == domain]

        if not targets:
            targets = [a for a in self._agent_domains if a != source]

        results = []
        for target in targets:
            if target == source:
                continue
            for unit in source_units:
                record = self._transfer_unit(source, target, unit)
                if record is not None:
                    results.append(record)

        # Limitar historial
        if len(self._transfers) > MAX_TRANSFER_HISTORY:
            self._transfers = self._transfers[-MAX_TRANSFER_HISTORY:]

        return results

    def _transfer_unit(self, source: str, target: str, unit: Any) -> dict[str, Any] | None:
        """Intenta transferir una unidad de conocimiento a un target.

        Args:
            source: Agente origen.
            target: Agente destino.
            unit: Unidad de conocimiento a transferir.

        Returns:
            El registro de transferencia serializado, o None si la afinidad es baja.
        """
        affinity = self._calculate_affinity(unit, target)
        if affinity < AFFINITY_THRESHOLD:
            return None

        record = TransferRecord(
            source=source,
            target=target,
            unit_id=unit.unit_id,
            domain=unit.domain,
            affinity=affinity,
        )

        # Auto-absorb si afinidad alta
        if affinity >= 0.6:
            record.absorbed = True
            self._absorb(target, unit)
            self._metrics["transfers_absorbed"] += 1

        self._transfers.append(record)
        self._metrics["transfers_attempted"] += 1

        if unit.domain not in self._agent_domains.get(target, set()):
            self._metrics["cross_domain_transfers"] += 1

        return record.to_dict()

    def record_usage(self, agent: str, unit_id: str) -> bool:
        """Registra que un agente usó una pieza de conocimiento."""
        for units in self._knowledge.values():
            for unit in units:
                if unit.unit_id == unit_id:
                    unit.usage_count += 1
                    unit.effectiveness = min(
                        1.0,
                        unit.effectiveness + EFFECTIVENESS_BOOST,
                    )
                    self._metrics["knowledge_reused"] += 1
                    return True
        return False

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_knowledge(
        self,
        agent: str,
        domain: str | None = None,
    ) -> list[dict[str, Any]]:
        """Conocimiento de un agente."""
        units = self._knowledge.get(agent, [])
        if domain:
            units = [u for u in units if u.domain == domain]
        return [
            u.to_dict()
            for u in sorted(
                units,
                key=lambda u: u.effectiveness,
                reverse=True,
            )
        ]

    def get_all_knowledge(self) -> dict[str, list[dict[str, Any]]]:
        """Todo el conocimiento organizado por agente."""
        return {agent: [u.to_dict() for u in units] for agent, units in self._knowledge.items()}

    def get_agent_domains(self, agent: str) -> list[str]:
        """Dominios en los que un agente tiene conocimiento."""
        return sorted(self._agent_domains.get(agent, set()))

    def find_experts(self, domain: str) -> list[dict[str, Any]]:
        """Encuentra agentes expertos en un dominio."""
        experts = []
        for agent, units in self._knowledge.items():
            domain_units = [u for u in units if u.domain == domain]
            if domain_units:
                avg_eff = sum(u.effectiveness for u in domain_units) / len(domain_units)
                experts.append(
                    {
                        "agent": agent,
                        "domain": domain,
                        "knowledge_units": len(domain_units),
                        "avg_effectiveness": round(avg_eff, 3),
                        "total_usage": sum(u.usage_count for u in domain_units),
                    }
                )
        return sorted(experts, key=lambda e: e["avg_effectiveness"], reverse=True)

    def get_transfer_history(
        self,
        agent: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de transferencias."""
        records = self._transfers
        if agent:
            records = [r for r in records if r.source == agent or r.target == agent]
        return [r.to_dict() for r in records[-limit:]][::-1]

    def get_absorption_stats(self) -> dict[str, Any]:
        """Estadísticas de absorción."""
        total = self._metrics["transfers_attempted"]
        absorbed = self._metrics["transfers_absorbed"]
        return {
            "total_transfers": total,
            "absorbed": absorbed,
            "absorption_rate": round(absorbed / total, 3) if total > 0 else 0.0,
            "cross_domain": self._metrics["cross_domain_transfers"],
            "knowledge_reused": self._metrics["knowledge_reused"],
        }

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas completas."""
        total_units = sum(len(u) for u in self._knowledge.values())
        return {
            "agents_with_knowledge": len(self._knowledge),
            "total_knowledge_units": total_units,
            "domains_covered": len(
                {d for domains in self._agent_domains.values() for d in domains}
            ),
            "absorption": self.get_absorption_stats(),
            "metrics": {**self._metrics},
        }

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _calculate_affinity(self, unit: KnowledgeUnit, target: str) -> float:
        """Calcula afinidad de una unidad para un target."""
        target_domains = self._agent_domains.get(target, set())
        if not target_domains:
            return 0.1  # Baseline para agentes sin dominio

        max_affinity = 0.0
        source_domain = unit.domain

        for target_domain in target_domains:
            # Mismo dominio = afinidad alta
            if source_domain == target_domain:
                max_affinity = max(max_affinity, 0.9)
            # Cross-domain affinity
            elif source_domain in DOMAIN_AFFINITY:
                aff = DOMAIN_AFFINITY[source_domain].get(target_domain, 0.0)
                max_affinity = max(max_affinity, aff)

        # Boost por effectiveness alta
        max_affinity *= 0.7 + 0.3 * unit.effectiveness

        return min(1.0, max_affinity)

    def _absorb(self, target: str, unit: KnowledgeUnit) -> None:
        """Un agente absorbe una unidad de conocimiento."""
        # Crear copia para el target
        absorbed = KnowledgeUnit(
            source_agent=unit.source_agent,
            domain=unit.domain,
            pattern=unit.pattern,
            effectiveness=unit.effectiveness * 0.8,  # Pierde algo en transfer
            context={**unit.context, "_transferred_from": unit.source_agent},
        )
        self._knowledge[target].append(absorbed)
        self._agent_domains[target].add(unit.domain)


# ============================================================
# Singleton
# ============================================================
_instance: KnowledgeDistiller | None = None


def get_knowledge_distiller(bus: Any = None) -> KnowledgeDistiller:
    """Obtiene o crea el knowledge distiller global."""
    global _instance
    if _instance is None:
        _instance = KnowledgeDistiller(bus=bus)
    return _instance
