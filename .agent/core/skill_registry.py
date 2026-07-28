#!/usr/bin/env python3
"""
Skill Registry — Singleton centralized registry for all skills.

Replaces 6 fragmented directory-scanning implementations:
1. skill_metadata_index.py (progressive disclosure)
2. skill_composer.py (direct loading)
3. skill_search.py (ChromaDB indexing)
4. intelligence/skill_composition.py (direct loading)
5. skills-server.py (MCP server listing)
6. skill_marketplace (versioning)

Features:
- Single directory scan (not 6 independent scans)
- SkillRecordLazy for memory efficiency
- Caching with content_hash invalidation
- Search: keyword + semantic (ChromaDB when available)
- Singleton pattern with thread-safe initialization
- Event system for registry changes

Version: 1.0.0 (Phase 1 Consolidation — Fase 2)
"""

from __future__ import annotations

import hashlib
import logging
import threading
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Any, ClassVar

_SEARCH_CACHE_MAX_SIZE = 256

# Handle imports from both direct and package contexts
try:
    # When imported as core.skill_registry
    from .skill_record import SkillRecord, SkillRecordLazy
except ImportError:
    # When imported directly from sys.path
    from skill_record import (  # type: ignore  # runtime path depends on execution context
        SkillRecord,
        SkillRecordLazy,
    )

logger = logging.getLogger(__name__)


class SkillRegistryError(Exception):
    """Errores del registry."""

    pass


class SkillRegistry:
    """
    Singleton registry de skills con búsqueda híbrida y caching eficiente.

    Uso:
        registry = SkillRegistry.instance("/path/to/skills")

        # Acceso O(1)
        skill = registry.get("api-patterns")

        # Búsqueda keyword
        results = registry.search("REST API")

        # Búsqueda semántica (si chromadb disponible)
        semantic_results = registry.search_semantic("How to design APIs", k=5)

        # Lazy loading
        lazy = registry.get_lazy("api-patterns")
        record = lazy.to_record()  # Carga contenido
    """

    _instance: ClassVar[SkillRegistry | None] = None
    _lock: ClassVar[threading.Lock] = threading.Lock()

    def __init__(self, skills_dirs: str | Path | list[str | Path], auto_scan: bool = True):
        """
        Inicializar registry.

        Args:
            skills_dirs: Directorio raíz de skills, o lista de directorios.
                         Acepta str, Path, o list[str|Path] para múltiples raíces.
            auto_scan: Si True, escanea directorio en __init__
        """
        if isinstance(skills_dirs, (str, Path)):
            self.skills_dirs: list[Path] = [Path(skills_dirs)]
        else:
            self.skills_dirs = [Path(d) for d in skills_dirs]

        for sd in self.skills_dirs:
            if not sd.exists():
                raise SkillRegistryError(f"Skills directory not found: {sd}")

        # Storage
        self._records: dict[str, SkillRecord] = {}
        self._lazy_records: dict[str, SkillRecordLazy] = {}
        self._content_hashes: dict[str, str] = {}
        self._chromadb_index: Any = None  # ChromaDB collection si está disponible

        # Event system
        self._on_changed: list[Callable[[str, str], None]] = []  # (skill_name, event_type)

        # Caching — LRU bounded (max _SEARCH_CACHE_MAX_SIZE entries)
        self._search_cache: OrderedDict[str, list[tuple[str, float]]] = OrderedDict()
        self._cache_version: int = 0
        self._cache_hits: int = 0
        self._cache_misses: int = 0

        if auto_scan:
            self.scan()

    @classmethod
    def instance(cls, skills_dirs: str | Path | list[str | Path] | None = None) -> SkillRegistry:
        """
        Obtener instancia singleton.

        Si `skills_dirs` se proporciona en la primera llamada, se usa.
        En llamadas posteriores se ignora (retorna la instancia existente).
        Si se pasa un solo string/Path, se convierte a lista internamente.

        Args:
            skills_dirs: Directorio(s) de skills (solo para primera llamada)

        Returns:
            Instancia singleton de SkillRegistry
        """
        with cls._lock:
            inst = cls._instance
            if inst is None:
                resolved: list[str | Path]
                if skills_dirs is None:
                    # Default: buscar en .agent/skills/ + .agent/skills-custom/
                    base = Path(__file__).parent.parent
                    base_skills = base / "skills"
                    custom_skills = base / "skills-custom"
                    dirs_to_scan: list[Path] = []
                    if base_skills.exists():
                        dirs_to_scan.append(base_skills)
                    if custom_skills.exists():
                        dirs_to_scan.append(custom_skills)
                    if not dirs_to_scan:
                        raise SkillRegistryError(
                            f"No skills directories found under {base}\n"
                            "Pass skills_dirs explicitly to SkillRegistry.instance()"
                        )
                    resolved = list(dirs_to_scan)
                elif isinstance(skills_dirs, (str, Path)):
                    resolved = [Path(skills_dirs)]
                else:
                    resolved = list(skills_dirs)

                inst = cls(resolved, auto_scan=True)
                cls._instance = inst
            return inst

    def scan(self) -> None:
        """
        Escanear directorio(s) de skills una sola vez.

        Carga todos los SKILL.md como SkillRecordLazy (solo frontmatter).
        Escanea todos los directorios en self.skills_dirs recursivamente.
        """
        logger.info(f"Scanning skills directories: {self.skills_dirs}")
        self._records.clear()
        self._lazy_records.clear()
        self._content_hashes.clear()
        self._search_cache.clear()
        self._cache_version += 1

        skills_found = 0
        for skills_dir in self.skills_dirs:
            for skill_path in sorted(skills_dir.iterdir()):
                if not skill_path.is_dir():
                    continue
                if skill_path.name.startswith("."):
                    continue

                skill_md = skill_path / "SKILL.md"
                if not skill_md.exists():
                    continue

                try:
                    lazy = SkillRecordLazy.from_skill_file(skill_path)
                    self._lazy_records[lazy.name] = lazy
                    skills_found += 1

                    # Calcular hash del contenido para invalidación
                    with open(skill_md, encoding="utf-8") as f:
                        content = f.read()
                    self._content_hashes[lazy.name] = hashlib.sha256(
                        content.encode("utf-8")
                    ).hexdigest()[:16]

                except Exception as e:
                    logger.warning(f"Failed to load skill from {skill_path}: {e}")

        logger.info(f"Scanned {skills_found} skills across {len(self.skills_dirs)} directories")
        self._on_registry_changed("scan_complete")

    def get(self, skill_name: str, lazy: bool = False) -> SkillRecord | SkillRecordLazy | None:
        """
        Obtener skill por nombre.

        Args:
            skill_name: Nombre del skill
            lazy: Si True, retorna SkillRecordLazy (sin cargar contenido)

        Returns:
            SkillRecord o SkillRecordLazy, o None si no existe
        """
        if lazy:
            return self._lazy_records.get(skill_name)

        # Retornar cached record si está disponible
        if skill_name in self._records:
            return self._records[skill_name]

        # Cargar y cachear
        lazy_record = self._lazy_records.get(skill_name)
        if lazy_record is None:
            return None

        # Load content
        skill_path = lazy_record.path / "SKILL.md"
        if skill_path.exists():
            with open(skill_path, encoding="utf-8") as f:
                lazy_record.content = f.read()
                lazy_record.content_loaded = True

        record = lazy_record.to_record()
        self._records[skill_name] = record
        return record

    def list_all(self, lazy: bool = False) -> list[SkillRecord | SkillRecordLazy]:
        """
        Listar todos los skills.

        Args:
            lazy: Si True, retorna lazy records sin cargar contenido

        Returns:
            Lista de skills
        """
        if lazy:
            return list(self._lazy_records.values())
        result: list[SkillRecord | SkillRecordLazy] = []
        for name in self._lazy_records:
            record = self.get(name)
            if record is not None:
                result.append(record)
        return result

    def search(self, query: str, k: int = 10, use_semantic: bool = True) -> list[tuple[str, float]]:
        """
        Búsqueda híbrida: primero keyword, luego semántica.

        Args:
            query: Consulta de búsqueda
            k: Número máximo de resultados
            use_semantic: Si True, intenta búsqueda semántica con ChromaDB

        Returns:
            Lista de tuplas (skill_name, score) ordenadas por relevancia descendente
        """
        # Check cache (LRU: move hit to end)
        cache_key = f"{query}:{k}:{use_semantic}"
        if cache_key in self._search_cache:
            self._search_cache.move_to_end(cache_key)
            self._cache_hits += 1
            return self._search_cache[cache_key]
        self._cache_misses += 1

        results: list[tuple[str, float]] = []

        # Keyword search (siempre)
        keyword_results = self._search_keyword(query, k)
        results.extend(keyword_results)

        # Semantic search (si disponible y use_semantic=True)
        if use_semantic and self._chromadb_index is not None:
            semantic_results = self._search_semantic(query, k)
            # Merge results, deduplicating
            seen = {name for name, _ in keyword_results}
            for name, score in semantic_results:
                if name not in seen:
                    results.append((name, score))
                    seen.add(name)

        # Sort by score descending, limit to k
        results.sort(key=lambda x: x[1], reverse=True)
        results = results[:k]

        # Cache (LRU: add at end, evict oldest if over limit)
        self._search_cache[cache_key] = results
        if len(self._search_cache) > _SEARCH_CACHE_MAX_SIZE:
            self._search_cache.popitem(last=False)
        return results

    @staticmethod
    def _keyword_name_score(skill_name: str, query_lower: str) -> float:
        """Calcula el score por coincidencia en el nombre del skill.

        Args:
            skill_name: Nombre del skill.
            query_lower: Query de búsqueda en minúsculas.

        Returns:
            Score parcial: 1.0 exacto, 0.8 prefijo, 0.5 substring, 0.0 sin match.
        """
        if skill_name == query_lower:
            return 1.0
        if skill_name.startswith(query_lower):
            return 0.8
        if query_lower in skill_name:
            return 0.5
        return 0.0

    @staticmethod
    def _keyword_field_score(value: object, query_lower: str, weight: float) -> float:
        """Calcula el score por coincidencia en un campo lista (tags/triggers).

        Args:
            value: Valor del frontmatter (lista o string separado por comas).
            query_lower: Query de búsqueda en minúsculas.
            weight: Peso a sumar por cada coincidencia.

        Returns:
            Score acumulado por las coincidencias en el campo.
        """
        items = value
        if isinstance(items, str):
            items = [t.strip() for t in items.split(",")]
        if not isinstance(items, list):
            return 0.0
        return sum(weight for item in items if query_lower in str(item).lower())

    def _score_keyword_record(
        self, skill_name: str, lazy_record: SkillRecordLazy, query_lower: str
    ) -> float:
        """Calcula el score total de un skill para una query de keywords.

        Args:
            skill_name: Nombre del skill.
            lazy_record: Registro perezoso con el frontmatter.
            query_lower: Query de búsqueda en minúsculas.

        Returns:
            Score combinado de nombre, descripción, tags y triggers.
        """
        score = self._keyword_name_score(skill_name, query_lower)

        # Description match
        if query_lower in lazy_record.frontmatter.get("description", "").lower():
            score += 0.7

        # Tags match
        score += self._keyword_field_score(
            lazy_record.frontmatter.get("tags", []), query_lower, 0.6
        )

        # Triggers match
        score += self._keyword_field_score(
            lazy_record.frontmatter.get("triggers", []), query_lower, 0.4
        )

        return score

    def _search_keyword(self, query: str, k: int) -> list[tuple[str, float]]:
        """Búsqueda por keywords en nombre, descripción, tags."""
        query_lower = query.lower()
        results: list[tuple[str, float]] = []

        for skill_name, lazy_record in self._lazy_records.items():
            score = self._score_keyword_record(skill_name, lazy_record, query_lower)
            if score > 0:
                results.append((skill_name, score))

        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

    def _search_semantic(self, query: str, k: int) -> list[tuple[str, float]]:
        """Búsqueda semántica con ChromaDB (si está disponible)."""
        if self._chromadb_index is None:
            return []

        try:
            # Query ChromaDB
            results = self._chromadb_index.query(query_texts=[query], n_results=k)
            if not results or "ids" not in results or not results["ids"]:
                return []

            ids = results["ids"][0]  # Primera query
            distances = results["distances"][0] if "distances" in results else [0.0] * len(ids)

            # Convert distances to similarity scores (1 - distance)
            return [
                (skill_id, 1.0 - distance)
                for skill_id, distance in zip(ids, distances, strict=False)
            ]

        except Exception as e:
            logger.warning(f"Semantic search failed: {e}")
            return []

    def initialize_chromadb(self) -> bool:
        """
        Inicializar índice ChromaDB para búsqueda semántica.

        Llamar después de scan() cuando desees habilitar búsqueda semántica.

        Returns:
            True si se inicializó exitosamente, False en caso contrario
        """
        try:
            import chromadb
        except ImportError:
            logger.warning("chromadb not installed, semantic search unavailable")
            return False

        try:
            client = chromadb.Client()
            collection = client.get_or_create_collection(
                name="skills", metadata={"hnsw:space": "cosine"}
            )

            # Index all skills
            documents = []
            ids = []
            for skill_name, lazy_record in self._lazy_records.items():
                doc = lazy_record.frontmatter.get("description", "")
                if not doc:
                    doc = skill_name
                documents.append(doc)
                ids.append(skill_name)

            collection.upsert(ids=ids, documents=documents)
            self._chromadb_index = collection
            logger.info(f"ChromaDB initialized with {len(ids)} skills")
            return True

        except Exception as e:
            logger.warning(f"Failed to initialize ChromaDB: {e}")
            return False

    def invalidate_cache(self, skill_name: str | None = None) -> None:
        """
        Invalidar caché de búsqueda.

        Args:
            skill_name: Si se proporciona, solo invalidar ese skill.
                       Si None, invalidar todo el caché.
        """
        if skill_name is None:
            self._search_cache.clear()
            self._cache_version += 1
            self._cache_hits = 0
            self._cache_misses = 0
        else:
            # Invalidar entradas que contienen ese skill
            keys_to_remove = list(self._search_cache.keys())
            for k in keys_to_remove:
                self._search_cache.pop(k, None)

    def on_changed(self, callback: Callable[[str, str], None]) -> None:
        """
        Registrar callback para cambios en el registry.

        Args:
            callback: Función que recibe (skill_name, event_type)
                     event_type: 'added', 'updated', 'removed', 'scan_complete'
        """
        self._on_changed.append(callback)

    def _on_registry_changed(self, event_type: str, skill_name: str = "") -> None:
        """Trigger event callbacks."""
        for callback in self._on_changed:
            try:
                callback(skill_name, event_type)
            except Exception as e:
                logger.warning(f"Callback error: {e}")

    def reload(self) -> None:
        """Recargar registry completo."""
        self.scan()

    def get_stats(self) -> dict[str, Any]:
        """Estadísticas del registry."""
        return {
            "total_skills": len(self._lazy_records),
            "cached_full_records": len(self._records),
            "search_cache_size": len(self._search_cache),
            "search_cache_max_size": _SEARCH_CACHE_MAX_SIZE,
            "search_cache_hits": self._cache_hits,
            "search_cache_misses": self._cache_misses,
            "search_cache_hit_rate": (
                self._cache_hits / (self._cache_hits + self._cache_misses)
                if (self._cache_hits + self._cache_misses) > 0
                else 0.0
            ),
            "chromadb_enabled": self._chromadb_index is not None,
            "skills_dirs": [str(d) for d in self.skills_dirs],
        }
