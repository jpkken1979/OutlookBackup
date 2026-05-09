"""Memory Router — capa unificada que conecta las 5 capas de memoria.

Provee una interfaz única para buscar y almacenar información
a través de: mem0, observations, project memory, agent memory y brain network.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class MemoryResult:
    """Resultado unificado de búsqueda en memoria."""

    source: str  # "mem0" | "observations" | "project" | "agent" | "shared" | "brain"
    content: str
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def source_label(self) -> str:
        """Etiqueta legible de la fuente."""
        labels = {
            "mem0": "Memoria Semántica",
            "observations": "Observaciones",
            "project": "Memoria de Proyecto",
            "agent": "Memoria de Agente",
            "shared": "Memoria Compartida",
            "brain": "Brain Network",
        }
        return labels.get(self.source, self.source)


@dataclass
class ContextBundle:
    """Paquete de contexto pre-cargado para una sesión."""

    recent_errors: list[dict[str, Any]] = field(default_factory=list)
    recent_decisions: list[dict[str, Any]] = field(default_factory=list)
    user_preferences: list[dict[str, Any]] = field(default_factory=list)
    project_health: dict[str, Any] = field(default_factory=dict)
    relevant_memories: list[MemoryResult] = field(default_factory=list)


class MemoryRouter:
    """Router unificado que busca en todas las capas de memoria.

    Uso:
        router = MemoryRouter(project_dir="/path/to/project")
        results = await router.search("autenticación JWT")
        context = await router.preload_context("optimizar queries SQL")
    """

    def __init__(self, project_dir: str | None = None) -> None:
        """Inicializa el router con referencias lazy a cada capa.

        Args:
            project_dir: Directorio del proyecto para ProjectMemory.
        """
        self._project_dir = project_dir
        self._project_memory: Any = None
        self._shared_memory: Any = None
        self._observation_store: Any = None
        self._brain_network: Any = None
        self._mem0_available: bool | None = None

    def _gateway_url(self, path: str = "") -> str:
        """Retorna la URL del gateway desde env var o fallback localhost.

        Permite que apps en otras PCs apunten al gateway correct
        sin hardcodear 127.0.0.1:4747.
        """
        base = os.environ.get("ANTIGRAVITY_GATEWAY_URL", "http://127.0.0.1:4747")
        return f"{base.rstrip('/')}/{path.lstrip('/')}" if path else base

    def _get_project_memory(self) -> Any:
        """Obtiene ProjectMemory de forma lazy."""
        if self._project_memory is None:
            try:
                from .project_memory import get_project_memory

                self._project_memory = get_project_memory(self._project_dir)
            except Exception:
                logger.debug("ProjectMemory no disponible")
        return self._project_memory

    def _get_shared_memory(self) -> Any:
        """Obtiene SharedMemory/MemoryBus de forma lazy."""
        if self._shared_memory is None:
            try:
                from .shared_memory import get_memory_bus

                self._shared_memory = get_memory_bus()
            except Exception:
                logger.debug("SharedMemory no disponible")
        return self._shared_memory

    def _get_observation_store(self) -> Any:
        """Obtiene ObservationStore de forma lazy."""
        if self._observation_store is None:
            try:
                from pathlib import Path

                from .observation_pipeline import get_observation_pipeline

                project_path = self._project_dir or "."
                pipeline = get_observation_pipeline(str(Path(project_path).resolve()))
                self._observation_store = pipeline._project_store
            except Exception:
                logger.debug("ObservationStore no disponible")
        return self._observation_store

    async def _check_mem0(self) -> bool:
        """Verifica si mem0 está realmente disponible vía el endpoint de stats.

        A diferencia del health check del gateway, esto confirma que mem0
        (ChromaDB + embeddings) está funcional y no retorna EINVAL.
        """
        if self._mem0_available is not None:
            return self._mem0_available
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._gateway_url("/v1/mem0/stats"),
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        inner = data.get("data", {})
                        # Si mem0底层 falla, el endpoint retorna error en inner
                        self._mem0_available = (
                            inner.get("mem0_available", False) is True
                            and inner.get("total", -1) >= 0
                        )
                    else:
                        self._mem0_available = False
        except Exception:
            self._mem0_available = False
        return self._mem0_available

    async def _search_mem0(self, query: str, limit: int = 5) -> list[MemoryResult]:
        """Busca en mem0 vía gateway HTTP (GET con query params)."""
        if not await self._check_mem0():
            return []
        results: list[MemoryResult] = []
        try:
            import aiohttp

            params: dict[str, str] = {"q": query, "limit": str(limit)}
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._gateway_url("/v1/mem0/recall"),
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as resp:
                    if resp.status == 200:
                        data = await resp.json()
                        inner = data.get("data", {})
                        # Handle both response formats from gateway
                        items = inner.get(
                            "results", inner.get("memories", inner.get("entries", []))
                        )
                        if isinstance(items, dict):
                            items = items.get("results", [items])
                        for item in items:
                            if not isinstance(item, dict):
                                continue
                            content = item.get("memory", item.get("content", ""))
                            score = item.get("score", 0.5)
                            results.append(
                                MemoryResult(
                                    source="mem0",
                                    content=str(content),
                                    score=float(score),
                                    metadata=item.get("metadata", {}),
                                )
                            )
        except Exception as e:
            logger.debug("Error buscando en mem0: %s", e)
        return results

    def _search_project_memory(self, query: str, limit: int = 5) -> list[MemoryResult]:
        """Busca en la memoria del proyecto."""
        pm = self._get_project_memory()
        if pm is None:
            return []

        results: list[MemoryResult] = []
        try:
            # Search decisions
            decisions = pm.search_decisions(query)
            for d in decisions[:limit]:
                content = d if isinstance(d, str) else str(d)
                results.append(
                    MemoryResult(
                        source="project",
                        content=content,
                        score=0.7,
                        metadata={"type": "decision"},
                    )
                )

            # Known errors
            errors = pm.get_known_errors()
            for err in errors[:limit]:
                err_str = str(err)
                if query.lower() in err_str.lower():
                    results.append(
                        MemoryResult(
                            source="project",
                            content=err_str,
                            score=0.6,
                            metadata={"type": "known_error"},
                        )
                    )
        except Exception as e:
            logger.debug("Error buscando en ProjectMemory: %s", e)
        return results

    def _search_shared_memory(self, query: str, limit: int = 5) -> list[MemoryResult]:
        """Busca en la memoria compartida."""
        bus = self._get_shared_memory()
        if bus is None:
            return []

        results: list[MemoryResult] = []
        try:
            items = bus.retrieve(query, limit=limit)
            for item in items:
                content = item if isinstance(item, str) else str(item)
                results.append(
                    MemoryResult(
                        source="shared",
                        content=content,
                        score=0.5,
                        metadata={"type": "shared"},
                    )
                )
        except Exception as e:
            logger.debug("Error buscando en SharedMemory: %s", e)
        return results

    def _get_brain_network(self) -> Any:
        """Obtiene BrainNetwork de forma lazy."""
        if self._brain_network is None:
            try:
                from pathlib import Path

                from .brain_network import BrainNetwork

                project_path = self._project_dir or "."
                self._brain_network = BrainNetwork(Path(project_path).resolve())
            except Exception:
                logger.debug("BrainNetwork no disponible")
        return self._brain_network

    def _search_brain(self, query: str, limit: int = 5) -> list[MemoryResult]:
        """Busca en el Brain Network (conocimiento estructurado).

        Busca en el Mother Brain + todos los app brains registrados.
        Retorna resultados con score basado en relevancia + frescura.

        Args:
            query: Texto de búsqueda.
            limit: Máximo de resultados.

        Returns:
            Lista de MemoryResult del Brain Network.
        """
        network = self._get_brain_network()
        if network is None:
            return []

        results: list[MemoryResult] = []
        try:
            query_results = network.query_network(query, limit=limit)
            for r in query_results:
                # Combinar titulo + contexto como contenido
                content_parts = [r.node.title]
                if r.node.context:
                    content_parts.append(r.node.context[:300])
                if r.node.decisions:
                    content_parts.append(r.node.decisions[:200])

                results.append(
                    MemoryResult(
                        source="brain",
                        content=" | ".join(content_parts),
                        score=r.relevance_score,
                        metadata={
                            "type": r.node.type,
                            "slug": r.node.slug,
                            "brain_id": r.brain_id,
                            "area": r.node.area,
                            "tags": r.node.tags,
                            "date": r.node.date,
                            "app_origin": r.node.app_origin,
                        },
                    )
                )
        except Exception as e:
            logger.debug("Error buscando en Brain Network: %s", e)
        return results

    def _search_observations(self, query: str, limit: int = 5) -> list[MemoryResult]:
        """Busca en las observaciones."""
        store = self._get_observation_store()
        if store is None:
            return []

        results: list[MemoryResult] = []
        try:
            obs = store.search(query, limit=limit)
            for o in obs:
                content = str(o)
                results.append(
                    MemoryResult(
                        source="observations",
                        content=content,
                        score=0.4,
                        metadata={"type": "observation"},
                    )
                )
        except Exception as e:
            logger.debug("Error buscando en observations: %s", e)
        return results

    async def search(
        self,
        query: str,
        *,
        limit: int = 10,
        sources: list[str] | None = None,
    ) -> list[MemoryResult]:
        """Busca en todas las capas de memoria y fusiona resultados.

        Args:
            query: Texto de búsqueda.
            limit: Máximo de resultados totales.
            sources: Filtrar por fuentes específicas (None = todas).

        Returns:
            Lista de MemoryResult ordenados por score descendente.
        """
        all_sources = sources or ["mem0", "brain", "project", "shared", "observations"]
        per_source_limit = max(3, limit // len(all_sources))
        all_results: list[MemoryResult] = []

        # mem0 is async
        if "mem0" in all_sources:
            all_results.extend(await self._search_mem0(query, per_source_limit))

        # Brain Network (structured knowledge)
        if "brain" in all_sources:
            all_results.extend(self._search_brain(query, per_source_limit))

        # Synchronous sources
        if "project" in all_sources:
            all_results.extend(self._search_project_memory(query, per_source_limit))

        if "shared" in all_sources:
            all_results.extend(self._search_shared_memory(query, per_source_limit))

        if "observations" in all_sources:
            all_results.extend(self._search_observations(query, per_source_limit))

        # Sort by score and limit
        all_results.sort(key=lambda r: r.score, reverse=True)
        return all_results[:limit]

    async def store(
        self,
        content: str,
        *,
        targets: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> dict[str, bool]:
        """Almacena información en una o más capas de memoria.

        Args:
            content: Texto a almacenar.
            targets: Capas destino (None = mem0 + shared).
            metadata: Metadatos adicionales.

        Returns:
            Dict con el resultado por cada capa.
        """
        targets = targets or ["mem0", "shared"]
        meta = metadata or {}
        results: dict[str, bool] = {}

        if "mem0" in targets:
            try:
                if await self._check_mem0():
                    import aiohttp

                    payload = {"content": content, "metadata": meta}
                    async with aiohttp.ClientSession() as session:
                        async with session.post(
                            self._gateway_url("/v1/mem0/store"),
                            json=payload,
                            timeout=aiohttp.ClientTimeout(total=10),
                        ) as resp:
                            results["mem0"] = resp.status == 200
                else:
                    results["mem0"] = False
            except Exception as e:
                logger.warning("Error almacenando en mem0: %s", e)
                results["mem0"] = False

        if "shared" in targets:
            try:
                bus = self._get_shared_memory()
                if bus:
                    bus.store(content, metadata=meta)
                    results["shared"] = True
                else:
                    results["shared"] = False
            except Exception as e:
                logger.warning("Error almacenando en shared: %s", e)
                results["shared"] = False

        if "project" in targets:
            try:
                pm = self._get_project_memory()
                if pm and "decision" in meta.get("type", ""):
                    pm.record_decision(content, meta.get("category", "general"))
                    results["project"] = True
                else:
                    results["project"] = False
            except Exception as e:
                logger.warning("Error almacenando en project: %s", e)
                results["project"] = False

        return results

    async def preload_context(self, task_description: str, *, limit: int = 5) -> ContextBundle:
        """Pre-carga contexto relevante para una tarea.

        Busca en todas las capas para armar un paquete de contexto
        que se pueda inyectar como system prompt.

        Args:
            task_description: Descripción de la tarea a realizar.
            limit: Máximo de items por categoría.

        Returns:
            ContextBundle con errores, decisiones, preferencias y memorias.
        """
        bundle = ContextBundle()

        # Recent errors from project memory
        pm = self._get_project_memory()
        if pm:
            try:
                errors = pm.get_known_errors()
                bundle.recent_errors = [{"error": str(e)} for e in errors[:limit]]
            except Exception:
                pass

            try:
                decisions = pm.search_decisions(task_description)
                bundle.recent_decisions = [{"decision": str(d)} for d in decisions[:limit]]
            except Exception:
                pass

            try:
                health = pm.get_project_health()
                bundle.project_health = (
                    health if isinstance(health, dict) else {"status": str(health)}
                )
            except Exception:
                pass

        # User preferences from mem0
        prefs = await self._search_mem0("preferencias del usuario", limit=3)
        bundle.user_preferences = [{"preference": r.content} for r in prefs]

        # Relevant memories from all sources
        bundle.relevant_memories = await self.search(task_description, limit=limit)

        return bundle

    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del router y sus capas."""
        brain = self._get_brain_network()
        stats: dict[str, Any] = {
            "layers": {
                "mem0": self._mem0_available,
                "brain_network": brain is not None,
                "project_memory": self._get_project_memory() is not None,
                "shared_memory": self._get_shared_memory() is not None,
                "observations": self._get_observation_store() is not None,
            },
        }

        if brain:
            try:
                stats["brain_stats"] = brain.network_stats()
            except Exception:
                pass

        pm = self._get_project_memory()
        if pm:
            try:
                stats["project_health"] = pm.get_project_health()
            except Exception:
                pass

        return stats


# Singleton
_router: MemoryRouter | None = None


def get_memory_router(project_dir: str | None = None) -> MemoryRouter:
    """Obtiene la instancia singleton del MemoryRouter.

    Args:
        project_dir: Directorio del proyecto (solo usado en primera llamada).

    Returns:
        Instancia de MemoryRouter.
    """
    global _router
    if _router is None:
        _router = MemoryRouter(project_dir=project_dir)
    return _router
