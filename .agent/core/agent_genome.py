"""
Agent Genome — DNA & Evolution para agentes.

Cada agente tiene un genoma: un vector de configuración evolucionable.
El sistema usa algoritmo genético para optimizar configuraciones:
  - Selection: agentes con mejor fitness (reputation + compliance) sobreviven
  - Crossover: combina genes de dos padres exitosos
  - Mutation: introduce variaciones controladas
  - Elitism: los mejores genomas se preservan sin cambios

Genes (configuración evolucionable):
  - timeout: tiempo máximo de ejecución
  - retry_count: reintentos ante fallo
  - concurrency: slots concurrentes permitidos
  - priority_boost: bonus de prioridad en routing
  - confidence_threshold: umbral mínimo de confianza
  - specialization: grado de especialización vs generalización
  - cooperation: tendencia a colaborar vs trabajar solo

Usage:
    genome = GenomeManager(bus=bus)

    # Registrar genoma inicial
    genome.register("explorer", traits={"timeout": 30, "retry_count": 2})

    # Evaluar fitness
    genome.evaluate_fitness("explorer", reputation=0.85, compliance=0.9)

    # Evolucionar generación
    evolved = genome.evolve_generation()

    # Obtener configuración óptima para un agente
    config = genome.get_optimal_config("explorer")
"""

import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.agent_genome")

# ============================================================
# Constantes
# ============================================================
POPULATION_SIZE = 20  # Genomas por pool de evolución
ELITE_COUNT = 3  # Genomas preservados sin cambios
MUTATION_RATE = 0.15  # Probabilidad de mutación por gen
MUTATION_MAGNITUDE = 0.2  # Magnitud de la mutación [0, 1]
CROSSOVER_RATE = 0.7  # Probabilidad de crossover
TOURNAMENT_SIZE = 3  # Tamaño del torneo de selección
MAX_GENERATIONS = 100  # Límite de generaciones almacenadas
FITNESS_DECAY = 0.95  # Decaimiento de fitness por generación

# Rangos válidos para cada gen
GENE_RANGES: dict[str, tuple[float, float]] = {
    "timeout": (5.0, 120.0),
    "retry_count": (0.0, 5.0),
    "concurrency": (1.0, 10.0),
    "priority_boost": (0.0, 1.0),
    "confidence_threshold": (0.1, 0.95),
    "specialization": (0.0, 1.0),
    "cooperation": (0.0, 1.0),
}

DEFAULT_GENES: dict[str, float] = {
    "timeout": 30.0,
    "retry_count": 2.0,
    "concurrency": 5.0,
    "priority_boost": 0.5,
    "confidence_threshold": 0.5,
    "specialization": 0.5,
    "cooperation": 0.5,
}


# ============================================================
# Modelos
# ============================================================
@dataclass
class Genome:
    """Genoma de un agente — vector de configuración evolucionable."""

    genome_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    agent: str = ""
    genes: dict[str, float] = field(default_factory=lambda: {**DEFAULT_GENES})
    fitness: float = 0.0
    generation: int = 0
    parent_ids: list[str] = field(default_factory=list)
    mutations: list[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "genome_id": self.genome_id,
            "agent": self.agent,
            "genes": {k: round(v, 3) for k, v in self.genes.items()},
            "fitness": round(self.fitness, 4),
            "generation": self.generation,
            "parent_ids": self.parent_ids,
            "mutations": self.mutations,
            "created_at": self.created_at,
        }


@dataclass
class FitnessRecord:
    """Registro de evaluación de fitness."""

    agent: str
    genome_id: str
    fitness: float
    components: dict[str, float] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "agent": self.agent,
            "genome_id": self.genome_id,
            "fitness": round(self.fitness, 4),
            "components": {k: round(v, 3) for k, v in self.components.items()},
            "timestamp": self.timestamp,
        }


@dataclass
class EvolutionEvent:
    """Evento de evolución."""

    event_type: str  # "crossover", "mutation", "selection", "extinction"
    agents: list[str] = field(default_factory=list)
    detail: str = ""
    generation: int = 0
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        return {
            "event_type": self.event_type,
            "agents": self.agents,
            "detail": self.detail,
            "generation": self.generation,
            "timestamp": self.timestamp,
        }


# ============================================================
# Genome Manager
# ============================================================
class GenomeManager:
    """
    Gestor de genomas — evoluciona configuraciones de agentes.
    Usa algoritmo genético: selection + crossover + mutation + elitism.
    """

    def __init__(self, bus: Any = None) -> None:
        self._bus = bus

        # Genomas activos por agente
        self._genomes: dict[str, Genome] = {}

        # Pool de evolución (todos los genomas, incluidos históricos)
        self._pool: list[Genome] = []

        # Historial de fitness
        self._fitness_history: list[FitnessRecord] = []

        # Eventos de evolución
        self._evolution_events: list[EvolutionEvent] = []

        # Generación actual
        self._generation = 0

        # Métricas
        self._metrics = {
            "genomes_registered": 0,
            "fitness_evaluations": 0,
            "generations_evolved": 0,
            "crossovers": 0,
            "mutations": 0,
            "extinctions": 0,
        }

    # --------------------------------------------------------
    # Register
    # --------------------------------------------------------
    def register(
        self,
        agent: str,
        traits: dict[str, float] | None = None,
    ) -> dict[str, Any]:
        """
        Registra un genoma para un agente.

        Args:
            agent: Nombre del agente.
            traits: Genes iniciales (override defaults).

        Returns:
            El genoma creado.
        """
        genes = {**DEFAULT_GENES}
        if traits:
            for key, value in traits.items():
                if key in GENE_RANGES:
                    lo, hi = GENE_RANGES[key]
                    genes[key] = max(lo, min(hi, float(value)))

        genome = Genome(agent=agent, genes=genes, generation=self._generation)
        self._genomes[agent] = genome
        self._pool.append(genome)
        self._metrics["genomes_registered"] += 1

        logger.info("Genome registered for %s (gen %d)", agent, self._generation)
        return genome.to_dict()

    # --------------------------------------------------------
    # Fitness Evaluation
    # --------------------------------------------------------
    def evaluate_fitness(
        self,
        agent: str,
        reputation: float = 0.5,
        compliance: float = 0.5,
        success_rate: float = 0.5,
        response_time_score: float = 0.5,
        collaboration_score: float = 0.5,
    ) -> dict[str, Any]:
        """
        Evalúa fitness de un agente basado en métricas del ecosistema.

        Fitness = weighted sum de:
          - reputation (0.3)
          - compliance con SLA (0.25)
          - success rate (0.25)
          - response time score (0.1)
          - collaboration score (0.1)

        Returns:
            FitnessRecord con el puntaje.
        """
        genome = self._genomes.get(agent)
        if not genome:
            genome = Genome(agent=agent)
            self._genomes[agent] = genome
            self._pool.append(genome)

        components = {
            "reputation": reputation,
            "compliance": compliance,
            "success_rate": success_rate,
            "response_time": response_time_score,
            "collaboration": collaboration_score,
        }

        fitness = (
            reputation * 0.3
            + compliance * 0.25
            + success_rate * 0.25
            + response_time_score * 0.1
            + collaboration_score * 0.1
        )

        genome.fitness = fitness

        record = FitnessRecord(
            agent=agent,
            genome_id=genome.genome_id,
            fitness=fitness,
            components=components,
        )
        self._fitness_history.append(record)
        if len(self._fitness_history) > 1000:
            self._fitness_history = self._fitness_history[-1000:]

        self._metrics["fitness_evaluations"] += 1
        return record.to_dict()

    # --------------------------------------------------------
    # Evolution
    # --------------------------------------------------------
    def evolve_generation(self) -> dict[str, Any]:
        """
        Ejecuta un ciclo de evolución completo.

        1. Selection: torneo para elegir padres
        2. Crossover: combinar genes de dos padres
        3. Mutation: variaciones aleatorias
        4. Elitism: preservar los mejores

        Returns:
            Resumen de la evolución.
        """
        if len(self._genomes) < 2:
            return {"error": "Need at least 2 genomes to evolve", "generation": self._generation}

        self._generation += 1
        active_genomes = list(self._genomes.values())

        # Sort by fitness (descending)
        active_genomes.sort(key=lambda g: g.fitness, reverse=True)

        # Elitism: preserve top performers
        elites = active_genomes[: min(ELITE_COUNT, len(active_genomes))]
        new_genomes: list[Genome] = []

        for elite in elites:
            preserved = Genome(
                agent=elite.agent,
                genes={**elite.genes},
                fitness=elite.fitness * FITNESS_DECAY,
                generation=self._generation,
                parent_ids=[elite.genome_id],
            )
            new_genomes.append(preserved)

        # Generate offspring
        crossover_count = 0
        mutation_count = 0

        while len(new_genomes) < len(active_genomes):
            # Tournament selection
            parent1 = self._tournament_select(active_genomes)
            parent2 = self._tournament_select(active_genomes)

            # Crossover
            if random.random() < CROSSOVER_RATE and parent1.agent != parent2.agent:
                child_genes = self._crossover(parent1.genes, parent2.genes)
                crossover_count += 1
                parents = [parent1.genome_id, parent2.genome_id]
            else:
                child_genes = {**parent1.genes}
                parents = [parent1.genome_id]

            # Mutation
            mutations_applied = []
            for gene_name in child_genes:
                if random.random() < MUTATION_RATE:
                    old_val = child_genes[gene_name]
                    child_genes[gene_name] = self._mutate_gene(gene_name, old_val)
                    mutations_applied.append(gene_name)
                    mutation_count += 1

            # Assign to next agent in rotation
            target_agent = active_genomes[len(new_genomes) % len(active_genomes)].agent
            child = Genome(
                agent=target_agent,
                genes=child_genes,
                fitness=0.0,  # Needs evaluation
                generation=self._generation,
                parent_ids=parents,
                mutations=mutations_applied,
            )
            new_genomes.append(child)

        # Update active genomes
        for genome in new_genomes:
            self._genomes[genome.agent] = genome
            self._pool.append(genome)

        # Trim pool
        if len(self._pool) > POPULATION_SIZE * MAX_GENERATIONS:
            self._pool = self._pool[-(POPULATION_SIZE * 10) :]

        self._metrics["generations_evolved"] += 1
        self._metrics["crossovers"] += crossover_count
        self._metrics["mutations"] += mutation_count

        event = EvolutionEvent(
            event_type="generation",
            agents=[g.agent for g in new_genomes],
            detail=f"gen={self._generation}, crossovers={crossover_count}, mutations={mutation_count}",
            generation=self._generation,
        )
        self._evolution_events.append(event)

        logger.info(
            "Generation %d evolved: %d genomes, %d crossovers, %d mutations",
            self._generation,
            len(new_genomes),
            crossover_count,
            mutation_count,
        )

        return {
            "generation": self._generation,
            "genomes_evolved": len(new_genomes),
            "elites_preserved": len(elites),
            "crossovers": crossover_count,
            "mutations": mutation_count,
            "top_fitness": round(active_genomes[0].fitness, 4) if active_genomes else 0.0,
            "avg_fitness": round(
                sum(g.fitness for g in active_genomes) / len(active_genomes),
                4,
            )
            if active_genomes
            else 0.0,
        }

    # --------------------------------------------------------
    # Queries
    # --------------------------------------------------------
    def get_genome(self, agent: str) -> dict[str, Any] | None:
        """Obtiene el genoma activo de un agente."""
        genome = self._genomes.get(agent)
        return genome.to_dict() if genome else None

    def get_all_genomes(self) -> list[dict[str, Any]]:
        """Lista todos los genomas activos."""
        return [
            g.to_dict()
            for g in sorted(
                self._genomes.values(),
                key=lambda g: g.fitness,
                reverse=True,
            )
        ]

    def get_optimal_config(self, agent: str) -> dict[str, float]:
        """
        Retorna la configuración óptima actual para un agente.

        Mapea genes a configuración usable.
        """
        genome = self._genomes.get(agent)
        if not genome:
            return {**DEFAULT_GENES}

        return {
            "timeout": round(genome.genes["timeout"], 1),
            "retry_count": round(genome.genes["retry_count"]),
            "concurrency": round(genome.genes["concurrency"]),
            "priority_boost": round(genome.genes["priority_boost"], 2),
            "confidence_threshold": round(genome.genes["confidence_threshold"], 2),
            "specialization": round(genome.genes["specialization"], 2),
            "cooperation": round(genome.genes["cooperation"], 2),
        }

    def get_fitness_ranking(self) -> list[dict[str, Any]]:
        """Ranking de agentes por fitness."""
        return [
            {
                "rank": i + 1,
                "agent": g.agent,
                "fitness": round(g.fitness, 4),
                "generation": g.generation,
            }
            for i, g in enumerate(
                sorted(self._genomes.values(), key=lambda g: g.fitness, reverse=True)
            )
        ]

    def get_gene_distribution(self) -> dict[str, dict[str, float]]:
        """Distribución estadística de genes en la población."""
        if not self._genomes:
            return {}

        distribution: dict[str, dict[str, float]] = {}
        for gene_name in GENE_RANGES:
            values = [g.genes.get(gene_name, 0.0) for g in self._genomes.values()]
            if values:
                distribution[gene_name] = {
                    "min": round(min(values), 3),
                    "max": round(max(values), 3),
                    "avg": round(sum(values) / len(values), 3),
                    "spread": round(max(values) - min(values), 3),
                }
        return distribution

    def get_evolution_history(self, limit: int = 20) -> list[dict[str, Any]]:
        """Historial de eventos de evolución."""
        return [e.to_dict() for e in self._evolution_events[-limit:]][::-1]

    def get_fitness_history(
        self,
        agent: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        """Historial de fitness."""
        records = self._fitness_history
        if agent:
            records = [r for r in records if r.agent == agent]
        return [r.to_dict() for r in records[-limit:]][::-1]

    # --------------------------------------------------------
    # Stats
    # --------------------------------------------------------
    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del sistema genético."""
        return {
            "generation": self._generation,
            "active_genomes": len(self._genomes),
            "pool_size": len(self._pool),
            "fitness_evaluations": len(self._fitness_history),
            "gene_distribution": self.get_gene_distribution(),
            "metrics": {**self._metrics},
        }

    # --------------------------------------------------------
    # Private helpers
    # --------------------------------------------------------
    def _tournament_select(self, population: list[Genome]) -> Genome:
        """Selección por torneo."""
        tournament = random.sample(
            population,
            min(TOURNAMENT_SIZE, len(population)),
        )
        return max(tournament, key=lambda g: g.fitness)

    def _crossover(
        self,
        genes1: dict[str, float],
        genes2: dict[str, float],
    ) -> dict[str, float]:
        """Crossover uniforme de dos genomas."""
        child = {}
        for gene_name in GENE_RANGES:
            if random.random() < 0.5:
                child[gene_name] = genes1.get(gene_name, DEFAULT_GENES[gene_name])
            else:
                child[gene_name] = genes2.get(gene_name, DEFAULT_GENES[gene_name])
        return child

    def _mutate_gene(self, gene_name: str, current_value: float) -> float:
        """Muta un gen dentro de su rango válido."""
        lo, hi = GENE_RANGES.get(gene_name, (0.0, 1.0))
        delta = (hi - lo) * MUTATION_MAGNITUDE * random.uniform(-1, 1)
        return max(lo, min(hi, current_value + delta))


# ============================================================
# Singleton
# ============================================================
_instance: GenomeManager | None = None


def get_genome_manager(bus: Any = None) -> GenomeManager:
    """Obtiene o crea el genome manager global."""
    global _instance
    if _instance is None:
        _instance = GenomeManager(bus=bus)
    return _instance
