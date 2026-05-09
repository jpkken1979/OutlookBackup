# mypy: ignore-errors
#!/usr/bin/env python3
"""
Swarm Intelligence - Inteligencia de enjambre para coordinación de agentes

Implementa patrones de inteligencia colectiva:
- Ant Colony Optimization (ACO) para encontrar mejores rutas
- Particle Swarm Optimization (PSO) para optimización
- Bee Algorithm para exploración/explotación
- Consensus Protocols para decisiones colectivas
"""

import json
import random
import threading
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any


class SwarmAlgorithm(Enum):
    """Algoritmos de enjambre disponibles"""

    ANT_COLONY = "ant_colony"
    PARTICLE_SWARM = "particle_swarm"
    BEE_ALGORITHM = "bee_algorithm"
    CONSENSUS = "consensus"


@dataclass
class SwarmParticle:
    """Partícula individual en el enjambre"""

    id: str
    position: dict[str, float]  # Posición actual en espacio de búsqueda
    velocity: dict[str, float]  # Velocidad actual
    best_position: dict[str, float]  # Mejor posición personal
    best_fitness: float = 0.0
    current_fitness: float = 0.0


@dataclass
class AntPath:
    """Camino encontrado por una hormiga"""

    ant_id: str
    path: list[str]  # Secuencia de nodos/agentes
    pheromone: float = 1.0
    fitness: float = 0.0
    distance: float = 0.0


@dataclass
class SwarmDecision:
    """Decisión tomada por el enjambre"""

    question: str
    options: list[str]
    votes: dict[str, int]
    winner: str
    confidence: float
    timestamp: str = ""
    participants: int = 0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = datetime.now().isoformat()


class SwarmIntelligence:
    """Sistema de inteligencia de enjambre"""

    # Parámetros ACO
    PHEROMONE_EVAPORATION = 0.1
    PHEROMONE_DEPOSIT = 1.0
    ALPHA = 1.0  # Importancia del feromona
    BETA = 2.0  # Importancia de la heurística

    # Parámetros PSO
    INERTIA = 0.7
    COGNITIVE = 1.5  # Atracción a mejor personal
    SOCIAL = 1.5  # Atracción a mejor global

    def __init__(self, data_dir: Path | None = None):
        self.data_dir = data_dir or Path(".agent/swarm")
        self.data_dir.mkdir(parents=True, exist_ok=True)

        self.pheromone_matrix: dict[str, dict[str, float]] = {}
        self.particles: dict[str, SwarmParticle] = {}
        self.global_best_position: dict[str, float] = {}
        self.global_best_fitness: float = 0.0
        self.decisions_history: list[SwarmDecision] = []

        self._lock = threading.Lock()
        self._load_state()

    def _load_state(self):
        """Cargar estado persistido"""
        state_file = self.data_dir / "swarm_state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text(encoding="utf-8"))
                self.pheromone_matrix = data.get("pheromone_matrix", {})
                self.global_best_fitness = data.get("global_best_fitness", 0.0)
                self.global_best_position = data.get("global_best_position", {})
            except Exception:
                pass

    def _save_state(self):
        """Guardar estado"""
        state_file = self.data_dir / "swarm_state.json"
        data = {
            "pheromone_matrix": self.pheromone_matrix,
            "global_best_fitness": self.global_best_fitness,
            "global_best_position": self.global_best_position,
        }
        state_file.write_text(json.dumps(data, indent=2))

    # ==================== ANT COLONY OPTIMIZATION ====================

    def init_pheromone(self, nodes: list[str], initial_value: float = 0.1):
        """Inicializar matriz de feromonas"""
        with self._lock:
            for node_a in nodes:
                if node_a not in self.pheromone_matrix:
                    self.pheromone_matrix[node_a] = {}
                for node_b in nodes:
                    if node_a != node_b:
                        self.pheromone_matrix[node_a][node_b] = initial_value
            self._save_state()

    def ant_select_next(
        self, current: str, available: list[str], heuristic: dict[str, float] | None = None
    ) -> str:
        """Seleccionar siguiente nodo usando probabilidad ACO"""
        if not available:
            return current

        if current not in self.pheromone_matrix:
            return random.choice(available)

        # Calcular probabilidades
        probabilities = []
        for node in available:
            pheromone = self.pheromone_matrix.get(current, {}).get(node, 0.1)
            heuristic_value = heuristic.get(node, 1.0) if heuristic else 1.0

            prob = (pheromone**self.ALPHA) * (heuristic_value**self.BETA)
            probabilities.append((node, prob))

        # Normalizar
        total = sum(p for _, p in probabilities)
        if total == 0:
            return random.choice(available)

        probabilities = [(n, p / total) for n, p in probabilities]

        # Selección por ruleta
        r = random.random()
        cumulative = 0
        for node, prob in probabilities:
            cumulative += prob
            if r <= cumulative:
                return node

        return probabilities[-1][0]

    def deposit_pheromone(self, path: AntPath):
        """Depositar feromona en un camino"""
        if not path.path or len(path.path) < 2:
            return

        deposit = self.PHEROMONE_DEPOSIT / (path.distance + 1)

        with self._lock:
            for i in range(len(path.path) - 1):
                node_a = path.path[i]
                node_b = path.path[i + 1]

                if node_a not in self.pheromone_matrix:
                    self.pheromone_matrix[node_a] = {}

                current = self.pheromone_matrix[node_a].get(node_b, 0.1)
                self.pheromone_matrix[node_a][node_b] = current + deposit

            self._save_state()

    def evaporate_pheromone(self):
        """Evaporar feromonas (decay)"""
        with self._lock:
            for node_a in self.pheromone_matrix:
                for node_b in self.pheromone_matrix[node_a]:
                    current = self.pheromone_matrix[node_a][node_b]
                    self.pheromone_matrix[node_a][node_b] = current * (
                        1 - self.PHEROMONE_EVAPORATION
                    )

            self._save_state()

    def find_optimal_path(
        self,
        start: str,
        end: str,
        all_nodes: list[str],
        fitness_func: Callable[[list[str]], float],
        num_ants: int = 10,
        iterations: int = 20,
    ) -> tuple[list[str], float]:
        """Encontrar camino óptimo usando ACO"""
        self.init_pheromone(all_nodes)

        best_path = []
        best_fitness = 0.0

        for _iteration in range(iterations):
            paths = []

            # Cada hormiga construye un camino
            for ant_idx in range(num_ants):
                path = [start]
                current = start
                available = [n for n in all_nodes if n != start and n != end]

                while available and current != end:
                    next_node = self.ant_select_next(current, available)
                    path.append(next_node)
                    available.remove(next_node)
                    current = next_node

                if end not in path:
                    path.append(end)

                fitness = fitness_func(path)
                ant_path = AntPath(
                    ant_id=f"ant_{ant_idx}", path=path, fitness=fitness, distance=len(path)
                )
                paths.append(ant_path)

                if fitness > best_fitness:
                    best_fitness = fitness
                    best_path = path

            # Depositar feromonas
            for path in paths:
                if path.fitness > 0:
                    self.deposit_pheromone(path)

            # Evaporar
            self.evaporate_pheromone()

        return best_path, best_fitness

    # ==================== PARTICLE SWARM OPTIMIZATION ====================

    def init_particle(self, particle_id: str, dimensions: list[str]) -> SwarmParticle:
        """Inicializar una partícula"""
        position = {dim: random.random() for dim in dimensions}
        velocity = {dim: (random.random() - 0.5) * 0.1 for dim in dimensions}

        particle = SwarmParticle(
            id=particle_id,
            position=position,
            velocity=velocity,
            best_position=position.copy(),
            best_fitness=0.0,
        )

        self.particles[particle_id] = particle
        return particle

    def update_particle(self, particle_id: str, fitness_func: Callable[[dict[str, float]], float]):
        """Actualizar posición y velocidad de partícula"""
        particle = self.particles.get(particle_id)
        if not particle:
            return

        # Evaluar fitness actual
        current_fitness = fitness_func(particle.position)
        particle.current_fitness = current_fitness

        # Actualizar mejor personal
        if current_fitness > particle.best_fitness:
            particle.best_fitness = current_fitness
            particle.best_position = particle.position.copy()

        # Actualizar mejor global
        if current_fitness > self.global_best_fitness:
            self.global_best_fitness = current_fitness
            self.global_best_position = particle.position.copy()

        # Actualizar velocidad y posición
        for dim in particle.position:
            r1, r2 = random.random(), random.random()

            cognitive = (
                self.COGNITIVE
                * r1
                * (particle.best_position.get(dim, 0.5) - particle.position[dim])
            )
            social = (
                self.SOCIAL
                * r2
                * (self.global_best_position.get(dim, 0.5) - particle.position[dim])
            )

            particle.velocity[dim] = self.INERTIA * particle.velocity[dim] + cognitive + social

            # Limitar velocidad
            particle.velocity[dim] = max(-0.5, min(0.5, particle.velocity[dim]))

            # Actualizar posición
            particle.position[dim] += particle.velocity[dim]

            # Limitar posición a [0, 1]
            particle.position[dim] = max(0, min(1, particle.position[dim]))

    def pso_optimize(
        self,
        dimensions: list[str],
        fitness_func: Callable[[dict[str, float]], float],
        num_particles: int = 20,
        iterations: int = 50,
    ) -> tuple[dict[str, float], float]:
        """Optimización usando PSO"""
        # Inicializar partículas
        for i in range(num_particles):
            self.init_particle(f"particle_{i}", dimensions)

        # Iterar
        for _ in range(iterations):
            for particle_id in list(self.particles.keys()):
                self.update_particle(particle_id, fitness_func)

        return self.global_best_position.copy(), self.global_best_fitness

    # ==================== CONSENSUS PROTOCOL ====================

    def propose_decision(
        self,
        question: str,
        options: list[str],
        voters: list[str],
        vote_func: Callable[[str, str, list[str]], str],
    ) -> SwarmDecision:
        """Proponer decisión al enjambre y obtener consenso"""
        votes: dict[str, int] = dict.fromkeys(options, 0)

        for voter in voters:
            vote = vote_func(voter, question, options)
            if vote in votes:
                votes[vote] += 1

        # Determinar ganador
        winner = max(votes.keys(), key=lambda k: votes[k])
        total_votes = sum(votes.values())
        confidence = votes[winner] / total_votes if total_votes > 0 else 0

        decision = SwarmDecision(
            question=question,
            options=options,
            votes=votes,
            winner=winner,
            confidence=confidence,
            participants=len(voters),
        )

        self.decisions_history.append(decision)
        return decision

    def weighted_consensus(
        self,
        question: str,
        options: list[str],
        votes_with_weights: list[tuple[str, float]],  # (option, weight)
    ) -> SwarmDecision:
        """Consenso con votos ponderados"""
        weighted_votes: dict[str, float] = dict.fromkeys(options, 0)

        for option, weight in votes_with_weights:
            if option in weighted_votes:
                weighted_votes[option] += weight

        winner = max(weighted_votes.keys(), key=lambda k: weighted_votes[k])
        total_weight = sum(weighted_votes.values())
        confidence = weighted_votes[winner] / total_weight if total_weight > 0 else 0

        decision = SwarmDecision(
            question=question,
            options=options,
            votes={k: int(v) for k, v in weighted_votes.items()},
            winner=winner,
            confidence=confidence,
            participants=len(votes_with_weights),
        )

        self.decisions_history.append(decision)
        return decision

    # ==================== BEE ALGORITHM ====================

    def bee_search(
        self,
        search_space: list[Any],
        fitness_func: Callable[[Any], float],
        num_scouts: int = 10,
        num_elite: int = 2,
        num_best: int = 3,
        iterations: int = 20,
    ) -> tuple[Any, float]:
        """Búsqueda usando algoritmo de abejas"""
        # Scout bees - exploración inicial
        sites = random.sample(search_space, min(num_scouts, len(search_space)))
        site_fitness = [(site, fitness_func(site)) for site in sites]
        site_fitness.sort(key=lambda x: x[1], reverse=True)

        best_site = site_fitness[0][0]
        best_fitness = site_fitness[0][1]

        for _ in range(iterations):
            new_sites = []

            # Elite sites - más abejas
            for site, fitness in site_fitness[:num_elite]:
                # Neighborhood search (5 abejas)
                neighbors = self._get_neighbors(site, search_space, 5)
                for neighbor in neighbors:
                    n_fitness = fitness_func(neighbor)
                    if n_fitness > fitness:
                        new_sites.append((neighbor, n_fitness))
                    else:
                        new_sites.append((site, fitness))

            # Best sites - menos abejas
            for site, fitness in site_fitness[num_elite : num_elite + num_best]:
                neighbors = self._get_neighbors(site, search_space, 2)
                for neighbor in neighbors:
                    n_fitness = fitness_func(neighbor)
                    new_sites.append((neighbor, n_fitness))

            # Scout bees - exploración aleatoria
            remaining = num_scouts - len(new_sites)
            if remaining > 0:
                random_sites = random.sample(search_space, min(remaining, len(search_space)))
                for site in random_sites:
                    new_sites.append((site, fitness_func(site)))

            site_fitness = new_sites
            site_fitness.sort(key=lambda x: x[1], reverse=True)

            if site_fitness[0][1] > best_fitness:
                best_fitness = site_fitness[0][1]
                best_site = site_fitness[0][0]

        return best_site, best_fitness

    def _get_neighbors(self, site: Any, search_space: list[Any], n: int) -> list[Any]:
        """Obtener vecinos de un sitio"""
        if site in search_space:
            idx = search_space.index(site)
            start = max(0, idx - n)
            end = min(len(search_space), idx + n + 1)
            neighbors = search_space[start:end]
            return [n for n in neighbors if n != site][:n]
        return random.sample(search_space, min(n, len(search_space)))

    # ==================== UTILITIES ====================

    def get_stats(self) -> dict[str, Any]:
        """Obtener estadísticas del enjambre"""
        return {
            "pheromone_nodes": len(self.pheromone_matrix),
            "particles": len(self.particles),
            "global_best_fitness": self.global_best_fitness,
            "decisions_made": len(self.decisions_history),
            "avg_decision_confidence": (
                sum(d.confidence for d in self.decisions_history) / len(self.decisions_history)
                if self.decisions_history
                else 0
            ),
        }

    def clear(self):
        """Limpiar estado del enjambre"""
        self.pheromone_matrix = {}
        self.particles = {}
        self.global_best_fitness = 0.0
        self.global_best_position = {}
        self.decisions_history = []
        self._save_state()


# Singleton global
_swarm: SwarmIntelligence | None = None


def get_swarm_intelligence() -> SwarmIntelligence:
    """Obtener instancia singleton"""
    global _swarm
    if _swarm is None:
        _swarm = SwarmIntelligence()
    return _swarm


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Swarm Intelligence System")
    parser.add_argument("command", choices=["stats", "test", "clear"])
    parser.add_argument("--json", action="store_true", help="JSON output")

    args = parser.parse_args()
    swarm = get_swarm_intelligence()

    if args.command == "stats":
        stats = swarm.get_stats()
        if args.json:
            print(json.dumps(stats, indent=2))
        else:
            print("\n=== Swarm Intelligence Statistics ===")
            for key, value in stats.items():
                print(f"  {key}: {value}")

    elif args.command == "clear":
        swarm.clear()
        print("Swarm state cleared")

    elif args.command == "test":
        print("Testing Swarm Intelligence...\n")

        # Test ACO
        nodes = ["A", "B", "C", "D", "E"]
        swarm.init_pheromone(nodes)
        assert len(swarm.pheromone_matrix) > 0
        print("✓ ACO pheromone initialization works")

        # Test path selection
        next_node = swarm.ant_select_next("A", ["B", "C", "D"])
        assert next_node in ["B", "C", "D"]
        print("✓ ACO path selection works")

        # Test PSO
        dimensions = ["x", "y"]

        def simple_fitness(pos):
            return 1 - (pos["x"] ** 2 + pos["y"] ** 2)

        best_pos, best_fit = swarm.pso_optimize(
            dimensions, simple_fitness, num_particles=10, iterations=20
        )
        assert best_fit > 0
        print(f"✓ PSO optimization works (best fitness: {best_fit:.3f})")

        # Test consensus
        def dummy_vote(voter, question, options):
            return random.choice(options)

        decision = swarm.propose_decision(
            "Best approach?",
            ["Option A", "Option B", "Option C"],
            ["voter1", "voter2", "voter3", "voter4", "voter5"],
            dummy_vote,
        )
        assert decision.winner in ["Option A", "Option B", "Option C"]
        print(
            f"✓ Consensus protocol works (winner: {decision.winner}, confidence: {decision.confidence:.2f})"
        )

        # Test Bee Algorithm
        search_space = list(range(100))

        def bee_fitness(x):
            return -abs(x - 42)  # Optimal at 42

        best_site, best_fit = swarm.bee_search(search_space, bee_fitness)
        print(f"✓ Bee algorithm works (found: {best_site}, fitness: {best_fit})")

        print("\n✓ All tests passed!")
