"""
Antigravity Brain Network — Red de Inteligencia Distribuida.

Coordina multiples instancias de Brain (una por app) y un Mother Brain
central que agrega, conecta y potencia el conocimiento de toda la red.

Arquitectura:
    ┌─────────────────────────────────────────┐
    │           MOTHER BRAIN                   │
    │      .agent/brain/ (central)             │
    │  - Indice maestro cross-app              │
    │  - Conceptos emergentes                  │
    │  - Conexiones inter-app                  │
    │  - Conocimiento promovido                │
    ├────────┬─────────┬──────────────────────┤
    │ App A  │  App B  │  App C  │  ...       │
    │ brain/ │  brain/ │  brain/ │            │
    └────────┴─────────┴──────────────────────┘

El Mother Brain NO reemplaza los brains individuales.
Cada app mantiene su propio conocimiento local.
El Mother Brain CONECTA y ENRIQUECE.

Flujo:
1. App ingesta conocimiento → brain local
2. Sync al Mother Brain → nodo espejo con app_origin
3. Mother Brain detecta conexiones cross-app
4. Conceptos que aparecen en 2+ apps se promueven a concepto global
5. Query en el Mother Brain busca en TODOS los brains de la red

v1.0.0 — 2026-04-13
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from .brain import Brain, BrainNode, scrub_surrogates

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuracion por defecto
# ---------------------------------------------------------------------------
_DEFAULT_MOTHER_DIR = ".agent/brain"
_REGISTRY_FILE = "network_registry.json"
CONCEPT_PROMOTION_THRESHOLD = 2  # aparece en N+ apps → concepto global


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class AppBrainConfig:
    """Configuracion de un brain de app registrado en la red."""

    app_id: str
    brain_dir: str
    description: str = ""
    surface: str = "unknown"  # telegram-bot | nexus | claude-code | project
    active: bool = True
    registered_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


@dataclass
class CrossConnection:
    """Conexion descubierta entre nodos de diferentes apps."""

    source_app: str
    source_slug: str
    target_app: str
    target_slug: str
    connection_type: str  # semantic | tag_overlap | area_match | explicit
    strength: float = 0.0  # 0-1
    discovered_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario."""
        return asdict(self)


@dataclass
class NetworkQueryResult:
    """Resultado de una query a toda la red."""

    node: BrainNode
    brain_id: str
    relevance_score: float = 0.0

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario."""
        return {
            "node": self.node.to_dict(),
            "brain_id": self.brain_id,
            "relevance_score": self.relevance_score,
        }


# ---------------------------------------------------------------------------
# Brain Network Coordinator
# ---------------------------------------------------------------------------


class BrainNetwork:
    """Coordinador de la red de brains del ecosistema Antigravity.

    Maneja:
    - Registro de app brains en la red
    - Mother Brain como hub central
    - Sync de conocimiento app → Mother Brain
    - Deteccion de conexiones cross-app
    - Promocion de conceptos globales
    - Query distribuido en toda la red

    Uso:
        network = BrainNetwork("/path/to/repo")
        network.register_app("telegram-bot", "/path/to/bot/brain")
        network.sync_to_mother("telegram-bot", node)
        results = network.query_network("que es el Daicho")
    """

    def __init__(self, project_root: str | Path) -> None:
        """Inicializa la red de brains.

        Args:
            project_root: Raiz del proyecto (para resolver paths relativos).
        """
        self.project_root = Path(project_root)
        self.mother_dir = self.project_root / _DEFAULT_MOTHER_DIR
        self.registry_path = self.mother_dir / _REGISTRY_FILE

        # Mother Brain — el cerebro central
        self.mother = Brain(self.mother_dir, app_id="nexus-mother")

        # Registry de app brains
        self._app_configs: dict[str, AppBrainConfig] = {}
        self._app_brains: dict[str, Brain] = {}

        # Cargar registry existente
        self._load_registry()

    # ----- REGISTRO DE APPS -----

    def register_app(
        self,
        app_id: str,
        brain_dir: str | Path,
        *,
        description: str = "",
        surface: str = "unknown",
    ) -> AppBrainConfig:
        """Registra un brain de app en la red.

        Args:
            app_id: Identificador unico de la app.
            brain_dir: Directorio del brain de la app.
            description: Descripcion de la app.
            surface: Tipo de superficie (telegram-bot, nexus, etc.).

        Returns:
            Configuracion del app brain registrado.
        """
        config = AppBrainConfig(
            app_id=app_id,
            brain_dir=str(brain_dir),
            description=description,
            surface=surface,
        )

        self._app_configs[app_id] = config
        self._app_brains[app_id] = Brain(Path(brain_dir), app_id=app_id)
        self._save_registry()

        logger.info("Brain Network: registrada app '%s' en %s", app_id, brain_dir)
        return config

    def unregister_app(self, app_id: str) -> bool:
        """Desregistra un brain de app de la red.

        Args:
            app_id: ID de la app a desregistrar.

        Returns:
            True si se desregistro, False si no existia.
        """
        if app_id in self._app_configs:
            del self._app_configs[app_id]
            self._app_brains.pop(app_id, None)
            self._save_registry()
            return True
        return False

    def get_app_brain(self, app_id: str) -> Brain | None:
        """Obtiene el brain de una app registrada.

        Args:
            app_id: ID de la app.

        Returns:
            Brain de la app o None si no esta registrada.
        """
        if app_id not in self._app_brains and app_id in self._app_configs:
            config = self._app_configs[app_id]
            self._app_brains[app_id] = Brain(
                Path(config.brain_dir),
                app_id=app_id,
            )
        return self._app_brains.get(app_id)

    def list_apps(self) -> list[AppBrainConfig]:
        """Lista todas las apps registradas en la red."""
        return list(self._app_configs.values())

    # ----- SYNC -----

    def sync_to_mother(self, app_id: str, node: BrainNode) -> BrainNode:
        """Sincroniza un nodo de una app al Mother Brain.

        Crea un nodo espejo en el Mother Brain con el app_origin del nodo
        original, manteniendo trazabilidad de donde vino el conocimiento.

        Args:
            app_id: ID de la app de origen.
            node: Nodo a sincronizar.

        Returns:
            El nodo creado en el Mother Brain.
        """
        # Crear nodo espejo en el Mother Brain
        mother_node = self.mother.ingest(
            title=node.title,
            context=node.context,
            decisions=node.decisions,
            output=node.output,
            pending=node.pending,
            area=node.area,
            tags=node.tags + [f"app:{app_id}"],
            sources=[f"app:{app_id}:{node.slug}"] + node.sources,
            node_type=node.type,
            source_notes=(
                f"Sincronizado desde {app_id}\nNodo original: [[{node.slug}]]\n{node.source_notes}"
            ),
        )

        logger.info(
            "Brain Network: sync %s:%s → mother:%s",
            app_id,
            node.slug,
            mother_node.slug,
        )
        return mother_node

    def sync_app_full(self, app_id: str) -> int:
        """Sincronizacion completa de un app brain al Mother Brain.

        Sincroniza todos los nodos activos que no esten ya en el Mother Brain.

        Args:
            app_id: ID de la app a sincronizar.

        Returns:
            Numero de nodos sincronizados.
        """
        app_brain = self.get_app_brain(app_id)
        if not app_brain:
            logger.warning("App '%s' no registrada en la red", app_id)
            return 0

        # Obtener nodos activos del app brain
        app_nodes = app_brain.list_nodes(status="active")

        # Obtener slugs ya sincronizados (por source reference)
        mother_nodes = self.mother.list_nodes()
        synced_sources = set()
        for mn in mother_nodes:
            for src in mn.sources:
                if src.startswith(f"app:{app_id}:"):
                    synced_sources.add(src.split(":", 2)[2])

        # Sincronizar los que faltan
        synced = 0
        for node in app_nodes:
            if node.slug not in synced_sources:
                self.sync_to_mother(app_id, node)
                synced += 1

        logger.info(
            "Brain Network: sync completo %s → mother: %d nodos nuevos",
            app_id,
            synced,
        )
        return synced

    # ----- CROSS-APP CONNECTIONS -----

    def discover_connections(self) -> list[CrossConnection]:
        """Descubre conexiones entre nodos de diferentes apps.

        Analiza tags, areas y contenido para encontrar relaciones
        cross-app que el Mother Brain deberia conocer.

        Returns:
            Lista de conexiones descubiertas.
        """
        connections: list[CrossConnection] = []
        all_app_nodes: dict[str, list[BrainNode]] = {}

        # Recolectar nodos de todas las apps
        for app_id, brain in self._app_brains.items():
            all_app_nodes[app_id] = brain.list_nodes(status="active")

        # Comparar nodos entre apps
        app_ids = list(all_app_nodes.keys())
        for i, app_a in enumerate(app_ids):
            for app_b in app_ids[i + 1 :]:
                nodes_a = all_app_nodes[app_a]
                nodes_b = all_app_nodes[app_b]

                for node_a in nodes_a:
                    for node_b in nodes_b:
                        strength = self._connection_strength(node_a, node_b)
                        if strength > 0.3:
                            conn_type = self._connection_type(node_a, node_b)
                            connections.append(
                                CrossConnection(
                                    source_app=app_a,
                                    source_slug=node_a.slug,
                                    target_app=app_b,
                                    target_slug=node_b.slug,
                                    connection_type=conn_type,
                                    strength=strength,
                                )
                            )

        # Persistir conexiones en el Mother Brain
        if connections:
            self._persist_connections(connections)

        logger.info(
            "Brain Network: %d conexiones cross-app descubiertas",
            len(connections),
        )
        return connections

    # ----- CONCEPT PROMOTION -----

    def promote_concepts(self) -> list[BrainNode]:
        """Promueve conceptos que aparecen en multiples apps a conceptos globales.

        Un concepto se promueve cuando:
        - Un tag aparece en nodos de 2+ apps diferentes
        - No existe ya un nodo concepto global para ese tag

        Returns:
            Lista de nodos concepto creados en el Mother Brain.
        """
        tag_apps = self._collect_tag_apps()

        # Detectar conceptos ya existentes en el Mother Brain
        existing_concepts = {
            n.title.lower() for n in self.mother.list_nodes(node_type="concept", status="active")
        }

        # Promover conceptos cross-app
        promoted: list[BrainNode] = []
        for tag, apps in tag_apps.items():
            if not (
                len(apps) >= CONCEPT_PROMOTION_THRESHOLD
                and tag.lower() not in existing_concepts
                and not tag.startswith("app:")
            ):
                continue

            context_parts = self._collect_concept_context(tag)
            concept_node = self.mother.ingest(
                title=tag,
                context=(
                    f"Concepto emergente detectado en {len(apps)} apps: "
                    f"{', '.join(apps)}\n\n" + "\n".join(context_parts)
                ),
                area="general",
                tags=[tag, "promoted-concept"] + [f"app:{a}" for a in apps],
                sources=[f"cross-app-promotion:{tag}"],
                node_type="concept",
            )
            promoted.append(concept_node)

            logger.info(
                "Brain Network: concepto '%s' promovido (apps: %s)",
                tag,
                ", ".join(apps),
            )

        return promoted

    def _collect_tag_apps(self) -> dict[str, set[str]]:
        """Cuenta en qué apps aparece cada tag (incluye Mother Brain).

        Returns:
            Mapa tag -> conjunto de app_ids donde aparece.
        """
        tag_apps: dict[str, set[str]] = {}
        for app_id, brain in self._app_brains.items():
            for node in brain.list_nodes(status="active"):
                for tag in node.tags:
                    tag_apps.setdefault(tag, set()).add(app_id)

        for node in self.mother.list_nodes(status="active"):
            for tag in node.tags:
                if not tag.startswith("app:"):
                    tag_apps.setdefault(tag, set()).add("nexus-mother")
        return tag_apps

    def _collect_concept_context(self, tag: str) -> list[str]:
        """Recolecta líneas de contexto de todos los nodos con un tag dado.

        Args:
            tag: Tag a buscar en los brains de cada app.

        Returns:
            Lista de líneas "**app**: título (fecha)" para construir el contexto.
        """
        context_parts: list[str] = []
        for app_id, brain in self._app_brains.items():
            for node in brain.list_nodes(tag=tag, status="active"):
                context_parts.append(f"**{app_id}**: {node.title} ({node.date})")
        return context_parts

    # ----- QUERY DISTRIBUIDO -----

    def query_network(
        self,
        question: str,
        *,
        limit: int = 10,
        app_filter: str | None = None,
    ) -> list[NetworkQueryResult]:
        """Busca en toda la red de brains.

        Estrategia:
        1. Query en el Mother Brain (indice maestro)
        2. Query en cada app brain registrado
        3. Merge y ranking de resultados
        4. Deduplicacion por titulo similar

        Args:
            question: Pregunta o termino de busqueda.
            limit: Maximo de resultados totales.
            app_filter: Si se especifica, buscar solo en esa app.

        Returns:
            Lista de resultados ordenados por relevancia.
        """
        results: list[NetworkQueryResult] = []

        # Paso 1: Query en Mother Brain (prioridad alta)
        if not app_filter or app_filter == "nexus-mother":
            mother_nodes = self.mother.query(question, limit=limit)
            for i, node in enumerate(mother_nodes):
                results.append(
                    NetworkQueryResult(
                        node=node,
                        brain_id="nexus-mother",
                        relevance_score=1.0 - (i * 0.1),  # Decreciente por posicion
                    )
                )

        # Paso 2: Query en app brains
        brains_to_query = (
            {app_filter: self._app_brains[app_filter]}
            if app_filter and app_filter in self._app_brains
            else self._app_brains
        )

        for app_id, brain in brains_to_query.items():
            app_nodes = brain.query(question, limit=max(3, limit // 3))
            for i, node in enumerate(app_nodes):
                results.append(
                    NetworkQueryResult(
                        node=node,
                        brain_id=app_id,
                        relevance_score=0.8 - (i * 0.1),  # Ligeramente menor que mother
                    )
                )

        # Paso 3: Ordenar por relevancia
        results.sort(key=lambda r: r.relevance_score, reverse=True)

        # Paso 4: Deduplicar por titulo similar
        seen_titles: set[str] = set()
        deduped: list[NetworkQueryResult] = []
        for result in results:
            title_key = result.node.title.lower().strip()
            if title_key not in seen_titles:
                seen_titles.add(title_key)
                deduped.append(result)

        return deduped[:limit]

    # ----- NETWORK HEALTH -----

    def lint_network(self) -> dict[str, Any]:
        """Auditoria de salud de toda la red.

        Returns:
            Reporte con lint de cada brain + resumen global.
        """
        reports: dict[str, Any] = {}

        # Lint del Mother Brain
        mother_lint = self.mother.lint()
        reports["nexus-mother"] = {
            "score": mother_lint.score,
            "summary": mother_lint.summary(),
            "issues_count": len(mother_lint.issues),
        }

        # Lint de cada app brain
        for app_id, brain in self._app_brains.items():
            lint_report = brain.lint()
            reports[app_id] = {
                "score": lint_report.score,
                "summary": lint_report.summary(),
                "issues_count": len(lint_report.issues),
            }

        # Resumen global
        all_scores = [r["score"] for r in reports.values()]
        global_score = sum(all_scores) / len(all_scores) if all_scores else 0

        return {
            "global_score": round(global_score, 1),
            "total_brains": len(reports),
            "brains": reports,
        }

    def network_stats(self) -> dict[str, Any]:
        """Estadisticas globales de la red.

        Returns:
            Dict con stats de cada brain + totales.
        """
        app_stats: dict[str, Any] = {}
        total_nodes = 0
        total_connections = 0

        # Stats del Mother Brain
        mother_st = self.mother.stats()
        app_stats["nexus-mother"] = mother_st
        total_nodes += mother_st["total_nodes"]
        total_connections += mother_st["total_connections"]

        # Stats de cada app
        for app_id, brain in self._app_brains.items():
            st = brain.stats()
            app_stats[app_id] = st
            total_nodes += st["total_nodes"]
            total_connections += st["total_connections"]

        return {
            "total_brains": 1 + len(self._app_brains),
            "total_nodes": total_nodes,
            "total_connections": total_connections,
            "registered_apps": [c.app_id for c in self._app_configs.values()],
            "brains": app_stats,
        }

    # ----- CONFLICT DETECTION -----

    def detect_conflicts(self) -> list[dict[str, Any]]:
        """Detecta conocimiento potencialmente contradictorio entre apps.

        Busca nodos en diferentes app brains que tratan el mismo tema
        (tags/area solapados) pero con contenido divergente.

        Returns:
            Lista de conflictos potenciales con metadata.
        """
        conflicts: list[dict[str, Any]] = []
        all_app_nodes: dict[str, list[BrainNode]] = {}

        for app_id, brain in self._app_brains.items():
            all_app_nodes[app_id] = brain.list_nodes(status="active")

        app_ids = list(all_app_nodes.keys())

        for i, app_a in enumerate(app_ids):
            for app_b in app_ids[i + 1 :]:
                nodes_a = all_app_nodes[app_a]
                nodes_b = all_app_nodes[app_b]

                for node_a in nodes_a:
                    for node_b in nodes_b:
                        # Solo comparar nodos con tema solapado
                        common_tags = set(node_a.tags) & set(node_b.tags) - {
                            t for t in node_a.tags if t.startswith("app:")
                        }
                        same_area = node_a.area == node_b.area

                        if not common_tags and not same_area:
                            continue

                        # Detectar divergencia: titulos similares pero contenido diferente
                        title_similarity = self._title_similarity(
                            node_a.title,
                            node_b.title,
                        )
                        if title_similarity < 0.3:
                            continue

                        # Si los titulos son similares, revisar si el contenido diverge
                        content_a = f"{node_a.context} {node_a.decisions}".strip()
                        content_b = f"{node_b.context} {node_b.decisions}".strip()

                        if not content_a or not content_b:
                            continue

                        content_sim = self._content_similarity(content_a, content_b)

                        # Alta similitud de titulo + baja similitud de contenido = conflicto
                        if title_similarity > 0.5 and content_sim < 0.3:
                            conflicts.append(
                                {
                                    "type": "potential_contradiction",
                                    "severity": "high" if title_similarity > 0.7 else "medium",
                                    "app_a": app_a,
                                    "node_a": node_a.slug,
                                    "title_a": node_a.title,
                                    "app_b": app_b,
                                    "node_b": node_b.slug,
                                    "title_b": node_b.title,
                                    "common_tags": list(common_tags),
                                    "title_similarity": round(title_similarity, 2),
                                    "content_similarity": round(content_sim, 2),
                                    "suggestion": (
                                        f"Revisar: '{node_a.title}' ({app_a}) vs "
                                        f"'{node_b.title}' ({app_b}) — "
                                        "mismo tema, contenido diferente"
                                    ),
                                }
                            )

        return conflicts

    # ----- CONSOLIDATE NETWORK -----

    def consolidate_network(
        self,
        *,
        min_age_days: int = 30,
    ) -> dict[str, Any]:
        """Consolida toda la red: archiva nodos viejos en cada brain.

        Args:
            min_age_days: Edad minima para considerar archivado.

        Returns:
            Reporte de consolidacion por brain.
        """
        results: dict[str, Any] = {}

        # Consolidar Mother Brain
        mother_report = self.mother.consolidate(min_age_days=min_age_days)
        results["nexus-mother"] = mother_report

        # Consolidar cada app brain
        for app_id, brain in self._app_brains.items():
            report = brain.consolidate(min_age_days=min_age_days)
            results[app_id] = report

        total_archived = sum(r.get("archived", 0) for r in results.values())
        return {
            "total_archived": total_archived,
            "brains": results,
        }

    # ----- PRIVATE -----

    def _title_similarity(self, title_a: str, title_b: str) -> float:
        """Calcula similitud entre dos titulos (0-1)."""
        words_a = set(title_a.lower().split())
        words_b = set(title_b.lower().split())
        stopwords = {"de", "la", "el", "en", "a", "the", "of", "and", "is", "for"}
        words_a -= stopwords
        words_b -= stopwords
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def _content_similarity(self, content_a: str, content_b: str) -> float:
        """Calcula similitud basica entre dos contenidos (0-1)."""
        words_a = set(content_a.lower().split())
        words_b = set(content_b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def _connection_strength(self, node_a: BrainNode, node_b: BrainNode) -> float:
        """Calcula la fuerza de conexion entre dos nodos."""
        score = 0.0

        # Tags solapados (mas peso)
        common_tags = set(node_a.tags) & set(node_b.tags)
        # Filtrar tags de app
        common_tags = {t for t in common_tags if not t.startswith("app:")}
        score += len(common_tags) * 0.2

        # Misma area
        if node_a.area == node_b.area:
            score += 0.15

        # Mismo tipo
        if node_a.type == node_b.type:
            score += 0.05

        # Proximidad temporal (misma semana = bonus)
        try:
            date_a = datetime.strptime(node_a.date, "%Y-%m-%d")
            date_b = datetime.strptime(node_b.date, "%Y-%m-%d")
            days_apart = abs((date_a - date_b).days)
            if days_apart <= 7:
                score += 0.1
            elif days_apart <= 30:
                score += 0.05
        except ValueError:
            pass

        # Titulo solapado (keywords compartidos)
        words_a = set(node_a.title.lower().split())
        words_b = set(node_b.title.lower().split())
        common_words = words_a & words_b - {"de", "la", "el", "en", "a", "the", "of"}
        score += len(common_words) * 0.1

        return min(score, 1.0)

    def _connection_type(self, node_a: BrainNode, node_b: BrainNode) -> str:
        """Determina el tipo de conexion entre dos nodos."""
        common_tags = set(node_a.tags) & set(node_b.tags)
        common_tags = {t for t in common_tags if not t.startswith("app:")}

        if common_tags:
            return "tag_overlap"
        if node_a.area == node_b.area:
            return "area_match"
        return "semantic"

    def _persist_connections(self, connections: list[CrossConnection]) -> None:
        """Persiste conexiones cross-app en el Mother Brain."""
        connections_file = self.mother.brain_dir / "connections" / "cross_app.json"
        connections_file.parent.mkdir(parents=True, exist_ok=True)

        existing: list[dict[str, Any]] = []
        if connections_file.exists():
            try:
                existing = json.loads(connections_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, ValueError):
                existing = []

        # Agregar nuevas conexiones (evitar duplicados)
        existing_keys = {
            f"{c['source_app']}:{c['source_slug']}:{c['target_app']}:{c['target_slug']}"
            for c in existing
        }

        for conn in connections:
            key = f"{conn.source_app}:{conn.source_slug}:{conn.target_app}:{conn.target_slug}"
            reverse_key = (
                f"{conn.target_app}:{conn.target_slug}:{conn.source_app}:{conn.source_slug}"
            )
            if key not in existing_keys and reverse_key not in existing_keys:
                existing.append(conn.to_dict())
                existing_keys.add(key)

        connections_file.write_text(
            json.dumps(scrub_surrogates(existing), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

    def _load_registry(self) -> None:
        """Carga el registry de apps desde disco."""
        if not self.registry_path.exists():
            return

        try:
            data = json.loads(self.registry_path.read_text(encoding="utf-8"))
            for app_data in data.get("apps", []):
                config = AppBrainConfig(**app_data)
                self._app_configs[config.app_id] = config
                # Lazy-load de brains — solo cuando se necesiten
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            logger.warning("Error cargando brain network registry: %s", e)

    def _save_registry(self) -> None:
        """Persiste el registry de apps a disco."""
        self.registry_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0.0",
            "updated_at": datetime.now(UTC).isoformat(),
            "apps": [asdict(c) for c in self._app_configs.values()],
        }
        self.registry_path.write_text(
            json.dumps(scrub_surrogates(data), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
