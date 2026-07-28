"""Mixin de inteligencia y evolución para AgentDaemon.

Adaptadores para: PredictivePrefetch (Sprint 7), GenomeManager (Sprint 8),
KnowledgeDistiller (Sprint 8). Gestiona predicción, evolución genética
y destilación de conocimiento entre agentes.
"""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class DaemonIntelligenceMixin:
    """Adaptadores de prefetch predictivo, genoma y destilación de conocimiento.

    Agrupa los subsistemas de aprendizaje y evolución: predicción
    de activaciones, evolución genética de agentes y destilación
    de conocimiento inter-agente.
    """

    # Atributos inyectados por AgentDaemon en runtime.
    _metrics: dict[str, int]
    _predictive_prefetch: Any | None
    _genome_manager: Any | None
    _knowledge_distiller: Any | None

    # --------------------------------------------------------
    # PredictivePrefetch (Sprint 7)
    # --------------------------------------------------------
    def prefetch_record(self, agent: str, task: str = "", domain: str = "general") -> None:
        """Registra una activación para predicción futura."""
        if self._predictive_prefetch is None:
            return
        self._predictive_prefetch.record_activation(agent, task, domain)

    def prefetch_predict(
        self,
        current_agent: str | None = None,
        current_domain: str | None = None,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Predice próximas activaciones probables."""
        if self._predictive_prefetch is None:
            return []
        self._metrics["prefetch_predictions"] += 1
        return self._predictive_prefetch.predict_next(current_agent, current_domain, limit)

    def prefetch_warmup(self, current_agent: str | None = None) -> list[str]:
        """Obtiene lista de agentes para pre-calentar."""
        if self._predictive_prefetch is None:
            return []
        return self._predictive_prefetch.get_warmup_list(current_agent)

    def prefetch_sequences(self) -> list[dict[str, Any]]:
        """Obtiene secuencias frecuentes de activación."""
        if self._predictive_prefetch is None:
            return []
        return self._predictive_prefetch.get_frequent_sequences()

    def prefetch_matrix(self) -> dict[str, dict[str, float]]:
        """Obtiene la matriz de transición entre agentes."""
        if self._predictive_prefetch is None:
            return {}
        return self._predictive_prefetch.get_transition_matrix()

    def prefetch_accuracy(self) -> dict[str, Any]:
        """Obtiene métricas de precisión de predicciones."""
        if self._predictive_prefetch is None:
            return {"status": "disabled"}
        return self._predictive_prefetch.get_prediction_accuracy()

    def get_prefetch_stats(self) -> dict[str, Any]:
        """Estadísticas del prefetch predictivo."""
        if self._predictive_prefetch is None:
            return {"status": "disabled"}
        return self._predictive_prefetch.get_stats()

    # --------------------------------------------------------
    # GenomeManager (Sprint 8)
    # --------------------------------------------------------
    def genome_register(self, agent: str, traits: dict[str, float] | None = None) -> dict[str, Any]:
        """Registra un agente en el sistema genómico."""
        if self._genome_manager is None:
            return {"status": "disabled"}
        return self._genome_manager.register(agent, traits)

    def genome_evaluate(
        self,
        agent: str,
        reputation: float = 0.5,
        compliance: float = 0.5,
        success_rate: float = 0.5,
        response_time_score: float = 0.5,
        collaboration_score: float = 0.5,
    ) -> dict[str, Any]:
        """Evalúa el fitness de un agente basado en métricas."""
        if self._genome_manager is None:
            return {"status": "disabled"}
        self._metrics["genome_evaluations"] += 1
        return self._genome_manager.evaluate_fitness(
            agent,
            reputation,
            compliance,
            success_rate,
            response_time_score,
            collaboration_score,
        )

    def genome_evolve(self) -> dict[str, Any]:
        """Ejecuta una generación de evolución genética."""
        if self._genome_manager is None:
            return {"status": "disabled"}
        return self._genome_manager.evolve_generation()

    def genome_get(self, agent: str) -> dict[str, Any] | None:
        """Obtiene el genoma de un agente."""
        if self._genome_manager is None:
            return None
        return self._genome_manager.get_genome(agent)

    def genome_get_all(self) -> list[dict[str, Any]]:
        """Obtiene todos los genomas registrados."""
        if self._genome_manager is None:
            return []
        return self._genome_manager.get_all_genomes()

    def genome_optimal_config(self, agent: str) -> dict[str, float]:
        """Obtiene la configuración óptima derivada del genoma."""
        if self._genome_manager is None:
            return {}
        return self._genome_manager.get_optimal_config(agent)

    def genome_ranking(self) -> list[dict[str, Any]]:
        """Ranking de agentes por fitness genético."""
        if self._genome_manager is None:
            return []
        return self._genome_manager.get_fitness_ranking()

    def genome_distribution(self) -> dict[str, dict[str, float]]:
        """Distribución de genes en la población."""
        if self._genome_manager is None:
            return {}
        return self._genome_manager.get_gene_distribution()

    def get_genome_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema genómico."""
        if self._genome_manager is None:
            return {"status": "disabled"}
        return self._genome_manager.get_stats()

    # --------------------------------------------------------
    # KnowledgeDistiller (Sprint 8)
    # --------------------------------------------------------
    def distill_knowledge(
        self,
        source: str,
        domain: str = "general",
        pattern: str = "",
        effectiveness: float = 0.5,
        context: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Destila conocimiento de una fuente."""
        if self._knowledge_distiller is None:
            return {"status": "disabled"}
        return self._knowledge_distiller.distill(source, domain, pattern, effectiveness, context)

    def transfer_knowledge(
        self,
        source: str,
        targets: list[str] | None = None,
        domain: str | None = None,
    ) -> list[dict[str, Any]]:
        """Transfiere conocimiento entre agentes."""
        if self._knowledge_distiller is None:
            return []
        self._metrics["distillation_transfers"] += 1
        return self._knowledge_distiller.transfer(source, targets, domain)

    def get_knowledge(self, agent: str, domain: str | None = None) -> list[dict[str, Any]]:
        """Obtiene conocimiento destilado de un agente."""
        if self._knowledge_distiller is None:
            return []
        return self._knowledge_distiller.get_knowledge(agent, domain)

    def find_experts(self, domain: str) -> list[dict[str, Any]]:
        """Encuentra expertos en un dominio."""
        if self._knowledge_distiller is None:
            return []
        return self._knowledge_distiller.find_experts(domain)

    def get_distillation_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema de destilación."""
        if self._knowledge_distiller is None:
            return {"status": "disabled"}
        return self._knowledge_distiller.get_stats()
