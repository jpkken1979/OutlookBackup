#!/usr/bin/env python3
"""
Agent Evolution System - Sistema de evolución y mejora automática de agentes

Permite que los agentes:
- Aprendan de su rendimiento
- Evolucionen sus capacidades
- Se adapten a nuevos patrones
- Mejoren automáticamente basándose en feedback
"""

import json
import random
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Any


class EvolutionStrategy(Enum):
    """Estrategias de evolución"""

    MUTATION = "mutation"  # Pequeños cambios aleatorios
    CROSSOVER = "crossover"  # Combinar características de agentes exitosos
    SELECTION = "selection"  # Seleccionar mejores variantes
    ADAPTATION = "adaptation"  # Adaptarse a patrones de uso


@dataclass
class AgentGenome:
    """Genoma de un agente - sus características evolucionables"""

    agent_id: str
    generation: int = 1
    fitness_score: float = 0.0
    traits: dict[str, float] = field(default_factory=dict)  # 0-1 values
    successful_patterns: list[str] = field(default_factory=list)
    failed_patterns: list[str] = field(default_factory=list)
    parent_ids: list[str] = field(default_factory=list)
    created_at: str = ""
    mutations: list[str] = field(default_factory=list)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()

        # Traits por defecto
        default_traits = {
            "verbosity": 0.5,  # Qué tan detalladas son las respuestas
            "creativity": 0.5,  # Qué tan creativas/divergentes
            "precision": 0.5,  # Qué tan precisas/conservadoras
            "speed_vs_quality": 0.5,  # Balance velocidad/calidad
            "context_sensitivity": 0.5,  # Qué tanto considera el contexto
            "error_tolerance": 0.5,  # Tolerancia a errores
            "exploration": 0.5,  # Explorar nuevos enfoques vs usar conocidos
        }

        for trait, default_value in default_traits.items():
            if trait not in self.traits:
                self.traits[trait] = default_value


@dataclass
class PerformanceMetric:
    """Métrica de rendimiento de un agente"""

    agent_id: str
    task_type: str
    success: bool
    duration_ms: int
    quality_score: float  # 0-1
    user_feedback: str | None = None
    timestamp: str = ""
    context: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


@dataclass
class EvolutionEvent:
    """Evento de evolución registrado"""

    event_type: str
    agent_id: str
    details: dict[str, Any]
    timestamp: str = ""

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class AgentEvolution:
    """Sistema de evolución de agentes"""

    MUTATION_RATE = 0.1  # Probabilidad de mutación
    CROSSOVER_RATE = 0.3  # Probabilidad de crossover
    ELITE_PERCENTAGE = 0.2  # Porcentaje de élite que pasa sin cambios

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path(".agent/evolution")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.genomes_file = self.data_dir / "genomes.json"
        self.metrics_file = self.data_dir / "metrics.json"
        self.history_file = self.data_dir / "evolution_history.json"

        self.genomes: dict[str, AgentGenome] = {}
        self.metrics: list[PerformanceMetric] = []
        self.history: list[EvolutionEvent] = []

        self._load_state()

    def _load_state(self):
        """Cargar estado persistido"""
        if self.genomes_file.exists():
            try:
                data = json.loads(self.genomes_file.read_text(encoding="utf-8"))
                for agent_id, genome_data in data.items():
                    self.genomes[agent_id] = AgentGenome(**genome_data)
            except Exception:
                pass

        if self.metrics_file.exists():
            try:
                data = json.loads(self.metrics_file.read_text(encoding="utf-8"))
                self.metrics = [PerformanceMetric(**m) for m in data[-1000:]]  # Últimas 1000
            except Exception:
                pass

        if self.history_file.exists():
            try:
                data = json.loads(self.history_file.read_text(encoding="utf-8"))
                self.history = [EvolutionEvent(**e) for e in data[-500:]]
            except Exception:
                pass

    def _save_state(self):
        """Guardar estado"""
        # Guardar genomes
        genomes_data = {
            agent_id: {
                "agent_id": g.agent_id,
                "generation": g.generation,
                "fitness_score": g.fitness_score,
                "traits": g.traits,
                "successful_patterns": g.successful_patterns[-100:],
                "failed_patterns": g.failed_patterns[-100:],
                "parent_ids": g.parent_ids,
                "created_at": g.created_at,
                "mutations": g.mutations[-20:],
            }
            for agent_id, g in self.genomes.items()
        }
        self.genomes_file.write_text(json.dumps(genomes_data, indent=2))

        # Guardar métricas (últimas 1000)
        metrics_data = [
            {
                "agent_id": m.agent_id,
                "task_type": m.task_type,
                "success": m.success,
                "duration_ms": m.duration_ms,
                "quality_score": m.quality_score,
                "user_feedback": m.user_feedback,
                "timestamp": m.timestamp,
                "context": m.context,
            }
            for m in self.metrics[-1000:]
        ]
        self.metrics_file.write_text(json.dumps(metrics_data, indent=2))

        # Guardar historial
        history_data = [
            {
                "event_type": e.event_type,
                "agent_id": e.agent_id,
                "details": e.details,
                "timestamp": e.timestamp,
            }
            for e in self.history[-500:]
        ]
        self.history_file.write_text(json.dumps(history_data, indent=2))

    def get_or_create_genome(self, agent_id: str) -> AgentGenome:
        """Obtener o crear genoma para un agente"""
        if agent_id not in self.genomes:
            self.genomes[agent_id] = AgentGenome(agent_id=agent_id)
            self._record_event("genome_created", agent_id, {})
            self._save_state()

        return self.genomes[agent_id]

    def record_performance(
        self,
        agent_id: str,
        task_type: str,
        success: bool,
        duration_ms: int,
        quality_score: float,
        user_feedback: str | None = None,
        context: dict | None = None,
    ):
        """Registrar rendimiento de un agente"""
        metric = PerformanceMetric(
            agent_id=agent_id,
            task_type=task_type,
            success=success,
            duration_ms=duration_ms,
            quality_score=quality_score,
            user_feedback=user_feedback,
            context=context or {},
        )

        self.metrics.append(metric)

        # Actualizar genoma
        genome = self.get_or_create_genome(agent_id)

        if success:
            pattern = f"{task_type}:{context.get('pattern', 'default') if context else 'default'}"
            if pattern not in genome.successful_patterns:
                genome.successful_patterns.append(pattern)
        else:
            pattern = f"{task_type}:{context.get('pattern', 'default') if context else 'default'}"
            if pattern not in genome.failed_patterns:
                genome.failed_patterns.append(pattern)

        # Recalcular fitness
        self._update_fitness(agent_id)
        self._save_state()

    def _update_fitness(self, agent_id: str):
        """Actualizar fitness score basado en métricas recientes"""
        genome = self.genomes[agent_id]

        # Obtener métricas de los últimos 7 días
        cutoff = datetime.now() - timedelta(days=7)
        recent_metrics = [
            m
            for m in self.metrics
            if m.agent_id == agent_id and datetime.fromisoformat(m.timestamp) > cutoff
        ]

        if not recent_metrics:
            return

        # Calcular fitness
        success_rate = sum(1 for m in recent_metrics if m.success) / len(recent_metrics)
        avg_quality = sum(m.quality_score for m in recent_metrics) / len(recent_metrics)
        avg_duration = sum(m.duration_ms for m in recent_metrics) / len(recent_metrics)

        # Normalizar duración (penalizar muy lento)
        duration_score = max(0, 1 - (avg_duration / 60000))  # < 60s = 1.0

        # Fitness ponderado
        genome.fitness_score = success_rate * 0.4 + avg_quality * 0.4 + duration_score * 0.2

    def mutate(self, agent_id: str, trait: str | None = None) -> AgentGenome:
        """Aplicar mutación a un agente"""
        genome = self.get_or_create_genome(agent_id)

        if trait:
            # Mutación específica
            traits_to_mutate = [trait]
        else:
            # Seleccionar traits aleatorios
            traits_to_mutate = [t for t in genome.traits if random.random() < self.MUTATION_RATE]

        for t in traits_to_mutate:
            # Mutación gaussiana
            old_value = genome.traits[t]
            mutation = random.gauss(0, 0.1)
            new_value = max(0, min(1, old_value + mutation))
            genome.traits[t] = new_value
            genome.mutations.append(f"{t}: {old_value:.3f} -> {new_value:.3f}")

        genome.generation += 1
        self._record_event("mutation", agent_id, {"traits_mutated": traits_to_mutate})
        self._save_state()

        return genome

    def crossover(self, agent_id_a: str, agent_id_b: str) -> AgentGenome:
        """Crear nuevo genoma combinando dos agentes"""
        genome_a = self.get_or_create_genome(agent_id_a)
        genome_b = self.get_or_create_genome(agent_id_b)

        # Crear nuevo ID
        new_id = f"{agent_id_a[:4]}x{agent_id_b[:4]}_{random.randint(1000, 9999)}"

        # Combinar traits
        new_traits = {}
        for trait in genome_a.traits:
            if random.random() < 0.5:
                new_traits[trait] = genome_a.traits[trait]
            else:
                new_traits[trait] = genome_b.traits.get(trait, 0.5)

        # Combinar patrones exitosos
        successful = list(
            set(genome_a.successful_patterns[-50:] + genome_b.successful_patterns[-50:])
        )

        new_genome = AgentGenome(
            agent_id=new_id,
            generation=max(genome_a.generation, genome_b.generation) + 1,
            traits=new_traits,
            successful_patterns=successful,
            parent_ids=[agent_id_a, agent_id_b],
        )

        self.genomes[new_id] = new_genome
        self._record_event("crossover", new_id, {"parents": [agent_id_a, agent_id_b]})
        self._save_state()

        return new_genome

    def adapt(self, agent_id: str, feedback: str, context: dict[str, Any]):
        """Adaptar agente basándose en feedback"""
        genome = self.get_or_create_genome(agent_id)

        # Analizar feedback para ajustar traits
        feedback_lower = feedback.lower()

        adjustments = []

        if any(w in feedback_lower for w in ["más detalle", "more detail", "explica más"]):
            genome.traits["verbosity"] = min(1, genome.traits["verbosity"] + 0.1)
            adjustments.append("verbosity +0.1")

        if any(w in feedback_lower for w in ["muy largo", "too long", "más corto", "conciso"]):
            genome.traits["verbosity"] = max(0, genome.traits["verbosity"] - 0.1)
            adjustments.append("verbosity -0.1")

        if any(w in feedback_lower for w in ["más creativo", "creative", "diferente"]):
            genome.traits["creativity"] = min(1, genome.traits["creativity"] + 0.1)
            adjustments.append("creativity +0.1")

        if any(w in feedback_lower for w in ["más preciso", "accurate", "exacto"]):
            genome.traits["precision"] = min(1, genome.traits["precision"] + 0.1)
            genome.traits["creativity"] = max(0, genome.traits["creativity"] - 0.05)
            adjustments.append("precision +0.1, creativity -0.05")

        if any(w in feedback_lower for w in ["más rápido", "faster", "quick"]):
            genome.traits["speed_vs_quality"] = min(1, genome.traits["speed_vs_quality"] + 0.1)
            adjustments.append("speed_vs_quality +0.1")

        if adjustments:
            genome.mutations.extend(adjustments)
            self._record_event(
                "adaptation", agent_id, {"feedback": feedback[:100], "adjustments": adjustments}
            )
            self._save_state()

    def select_best(self, task_type: str | None = None, top_n: int = 5) -> list[AgentGenome]:
        """Seleccionar los mejores agentes"""
        candidates = list(self.genomes.values())

        if task_type:
            # Filtrar por agentes que han manejado este tipo de tarea
            candidates = [
                g for g in candidates if any(task_type in p for p in g.successful_patterns)
            ]

        # Ordenar por fitness
        candidates.sort(key=lambda g: g.fitness_score, reverse=True)

        return candidates[:top_n]

    def evolve_population(self) -> dict[str, Any]:
        """Ejecutar un ciclo de evolución en toda la población"""
        if len(self.genomes) < 2:
            return {"error": "Need at least 2 agents to evolve"}

        results = {"mutations": 0, "crossovers": 0, "elite_preserved": 0, "new_generation": []}

        agents = list(self.genomes.values())
        agents.sort(key=lambda g: g.fitness_score, reverse=True)

        # Preservar élite
        elite_count = max(1, int(len(agents) * self.ELITE_PERCENTAGE))
        elite = agents[:elite_count]
        results["elite_preserved"] = elite_count

        # Mutar no-élite
        for genome in agents[elite_count:]:
            if random.random() < self.MUTATION_RATE:
                self.mutate(genome.agent_id)
                results["mutations"] += 1  # type: ignore[operator]  # dict literal with mixed value types

        # Crossover entre mejores
        if len(agents) >= 2 and random.random() < self.CROSSOVER_RATE:
            parent_a = random.choice(elite)
            candidates = [a for a in agents[: len(agents) // 2] if a != parent_a]
            if not candidates:
                # Fallback: cualquier agente distinto de parent_a
                candidates = [a for a in agents if a != parent_a]
            if candidates:
                parent_b = random.choice(candidates)
                new_genome = self.crossover(parent_a.agent_id, parent_b.agent_id)
                results["crossovers"] += 1  # type: ignore[operator]  # dict literal with mixed value types
                results["new_generation"].append(new_genome.agent_id)  # type: ignore[attr-defined]  # dict literal with mixed value types

        self._record_event("population_evolved", "system", results)
        self._save_state()

        return results

    def get_optimal_traits(self, task_type: str) -> dict[str, float]:
        """Obtener traits óptimos para un tipo de tarea basado en histórico"""
        # Filtrar métricas exitosas para este tipo de tarea
        successful_metrics = [
            m
            for m in self.metrics
            if m.task_type == task_type and m.success and m.quality_score > 0.7
        ]

        if not successful_metrics:
            # Retornar defaults
            return AgentGenome(agent_id="default").traits

        # Promediar traits de agentes exitosos
        trait_sums: dict[str, float] = {}
        trait_counts: dict[str, int] = {}

        for metric in successful_metrics:
            genome = self.genomes.get(metric.agent_id)
            if genome:
                for trait, value in genome.traits.items():
                    trait_sums[trait] = trait_sums.get(trait, 0) + value
                    trait_counts[trait] = trait_counts.get(trait, 0) + 1

        optimal = {trait: trait_sums[trait] / trait_counts[trait] for trait in trait_sums}

        return optimal

    def _record_event(self, event_type: str, agent_id: str, details: dict):
        """Registrar evento de evolución"""
        event = EvolutionEvent(event_type=event_type, agent_id=agent_id, details=details)
        self.history.append(event)

    def get_stats(self) -> dict[str, Any]:
        """Obtener estadísticas de evolución"""
        if not self.genomes:
            return {"total_agents": 0}

        fitness_scores = [g.fitness_score for g in self.genomes.values()]
        generations = [g.generation for g in self.genomes.values()]

        return {
            "total_agents": len(self.genomes),
            "total_metrics": len(self.metrics),
            "avg_fitness": sum(fitness_scores) / len(fitness_scores),
            "max_fitness": max(fitness_scores),
            "min_fitness": min(fitness_scores),
            "avg_generation": sum(generations) / len(generations),
            "max_generation": max(generations),
            "total_mutations": sum(len(g.mutations) for g in self.genomes.values()),
            "evolution_events": len(self.history),
        }

    def export_genome(self, agent_id: str) -> dict | None:
        """Exportar genoma de un agente"""
        genome = self.genomes.get(agent_id)
        if not genome:
            return None

        return {
            "agent_id": genome.agent_id,
            "generation": genome.generation,
            "fitness_score": genome.fitness_score,
            "traits": genome.traits,
            "successful_patterns": genome.successful_patterns,
            "parent_ids": genome.parent_ids,
            "mutations": genome.mutations,
        }

    def import_genome(self, genome_data: dict) -> AgentGenome:
        """Importar genoma"""
        genome = AgentGenome(**genome_data)
        self.genomes[genome.agent_id] = genome
        self._save_state()
        return genome


# Singleton global
_evolution: AgentEvolution | None = None


def get_agent_evolution() -> AgentEvolution:
    """Obtener instancia singleton"""
    global _evolution
    if _evolution is None:
        _evolution = AgentEvolution()
    return _evolution


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Agent Evolution System")
    parser.add_argument("command", choices=["stats", "evolve", "mutate", "best", "genome", "test"])
    parser.add_argument("--agent", "-a", help="Agent ID")
    parser.add_argument("--task-type", "-t", help="Task type")
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    evolution = get_agent_evolution()

    if args.command == "stats":
        stats = evolution.get_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("\n=== Agent Evolution Statistics ===")
            for key, value in stats.items():
                print(f"  {key}: {value}")

    elif args.command == "evolve":
        result = evolution.evolve_population()
        if args.json:
            print(json.dumps(result, indent=2))
        else:
            print("\n=== Evolution Cycle Complete ===")
            print(f"  Mutations: {result.get('mutations', 0)}")
            print(f"  Crossovers: {result.get('crossovers', 0)}")
            print(f"  Elite preserved: {result.get('elite_preserved', 0)}")

    elif args.command == "mutate":
        if not args.agent:
            print("Error: --agent required")
            exit(1)
        genome = evolution.mutate(args.agent)
        print(f"Mutated {args.agent}, generation {genome.generation}")

    elif args.command == "best":
        best = evolution.select_best(task_type=args.task_type)
        if args.json:
            print(json.dumps([evolution.export_genome(g.agent_id) for g in best], indent=2))
        else:
            print("\n=== Best Agents ===")
            for g in best:
                print(f"  {g.agent_id}: fitness={g.fitness_score:.3f}, gen={g.generation}")

    elif args.command == "genome":
        if not args.agent:
            print("Error: --agent required")
            exit(1)
        genome = evolution.export_genome(args.agent)  # type: ignore[assignment]  # return type dict|None, checked below
        if genome:
            print(json.dumps(genome, indent=2))
        else:
            print(f"Genome not found for {args.agent}")

    elif args.command == "test":
        print("Testing Agent Evolution...\n")

        # Test genome creation
        genome = evolution.get_or_create_genome("test-agent")
        assert genome is not None
        print("✓ Genome creation works")

        # Test performance recording
        evolution.record_performance("test-agent", "code_review", True, 1000, 0.8)
        print("✓ Performance recording works")

        # Test mutation
        mutated = evolution.mutate("test-agent")
        assert mutated.generation > 1
        print("✓ Mutation works")

        # Test stats
        stats = evolution.get_stats()
        assert stats["total_agents"] >= 1
        print("✓ Stats collection works")

        print("\n✓ All tests passed!")
