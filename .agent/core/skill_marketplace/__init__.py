# mypy: ignore-errors
#!/usr/bin/env python3
"""
Skill Marketplace - Sistema de gestion y versionado de skills.

Permite:
- Versionado semantico de skills
- Dependencias entre skills
- Publicacion/consumo de skills
- Changelog automatico

Uso:
    from .agent.core.skill_marketplace import SkillMarketplace

    marketplace = SkillMarketplace()

    # Publicar skill
    marketplace.publish("mi-skill", "1.0.0", path="/path/to/skill")

    # Buscar skills
    results = marketplace.search("authentication")

    # Instalar skill
    marketplace.install("otro-skill", version="^2.0.0")
"""

from __future__ import annotations

import json
import logging
import math
import re
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, Optional

# SkillRegistry will be imported lazily to avoid circular dependencies

logger = logging.getLogger("antigravity.core.skill_marketplace")


@dataclass
class SemanticVersion:
    """Version semantica (semver)."""

    major: int
    minor: int
    patch: int
    prerelease: str | None = None

    @classmethod
    def parse(cls, version_str: str) -> SemanticVersion:
        """Parsear string de version."""
        match = re.match(r"^(\d+)\.(\d+)\.(\d+)(?:-(.+))?$", version_str)
        if not match:
            raise ValueError(f"Version invalida: {version_str}")

        return cls(
            major=int(match.group(1)),
            minor=int(match.group(2)),
            patch=int(match.group(3)),
            prerelease=match.group(4),
        )

    def __str__(self) -> str:
        base = f"{self.major}.{self.minor}.{self.patch}"
        if self.prerelease:
            base += f"-{self.prerelease}"
        return base

    def __lt__(self, other: SemanticVersion) -> bool:
        if self.major != other.major:
            return self.major < other.major
        if self.minor != other.minor:
            return self.minor < other.minor
        if self.patch != other.patch:
            return self.patch < other.patch
        # Prerelease es menor que release
        return bool(self.prerelease and not other.prerelease)

    def matches_constraint(self, constraint: str) -> bool:
        """Alias para satisfies para compatibilidad con tests."""
        return self.satisfies(constraint)

    def satisfies(self, constraint: str) -> bool:
        """Verificar si satisface una constraint (^, ~, >=, etc.)."""
        if constraint.startswith("^"):
            # Compatible: mismo major, minor/patch pueden ser mayores
            target = SemanticVersion.parse(constraint[1:])
            return self.major == target.major and self >= target

        elif constraint.startswith("~"):
            # Aproximado: mismo major.minor, patch puede ser mayor
            target = SemanticVersion.parse(constraint[1:])
            return self.major == target.major and self.minor == target.minor and self >= target

        elif constraint.startswith(">="):
            target = SemanticVersion.parse(constraint[2:])
            return self >= target

        elif constraint.startswith("<="):
            target = SemanticVersion.parse(constraint[2:])
            return self <= target

        elif constraint.startswith(">"):
            target = SemanticVersion.parse(constraint[1:])
            return self > target

        elif constraint.startswith("<"):
            target = SemanticVersion.parse(constraint[1:])
            return self < target

        else:
            # Exacta
            target = SemanticVersion.parse(constraint)
            return self == target

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, SemanticVersion):
            return False
        return (self.major, self.minor, self.patch) == (other.major, other.minor, other.patch)

    def __ge__(self, other: SemanticVersion) -> bool:
        return not self < other

    def __le__(self, other: SemanticVersion) -> bool:
        return self < other or self == other

    def __gt__(self, other: SemanticVersion) -> bool:
        return not self <= other


@dataclass
class SkillDependency:
    """Dependencia de un skill."""

    name: str
    version_constraint: str
    optional: bool = False

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ChangelogEntry:
    """Entrada de changelog."""

    version: str
    date: str
    changes: list[str]
    breaking_changes: list[str] = field(default_factory=list)
    deprecations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class SkillMetadata:
    """Metadata de un skill."""

    name: str
    version: str
    description: str
    author: str
    tags: list[str]
    dependencies: list[SkillDependency]
    changelog: list[ChangelogEntry]
    created_at: str
    updated_at: str
    downloads: int = 0
    rating: float = 0.0

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "tags": self.tags,
            "dependencies": [d.to_dict() for d in self.dependencies],
            "changelog": [c.to_dict() for c in self.changelog],
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "downloads": self.downloads,
            "rating": self.rating,
        }


@dataclass
class SkillVersion:
    """Una version especifica de un skill."""

    version: str
    path: Path
    metadata: SkillMetadata
    published_at: str

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "path": self.path.as_posix(),
            "metadata": self.metadata.to_dict(),
            "published_at": self.published_at,
        }


class SkillMarketplace:
    """
    Marketplace para skills de Antigravity.

    Gestiona versiones, dependencias y distribucion de skills.
    Integrado con SkillRegistry para búsqueda centralizada.
    """

    def __init__(self, storage_path: Path | None = None, skills_dir: Path | None = None):
        self.storage_path = storage_path or Path.home() / ".antigravity" / "marketplace"
        self.storage_path.mkdir(parents=True, exist_ok=True)

        self.registry_path = self.storage_path / "registry"
        self.registry_path.mkdir(exist_ok=True)

        self.cache_path = self.storage_path / "cache"
        self.cache_path.mkdir(exist_ok=True)

        self.skills: dict[str, dict[str, SkillVersion]] = {}

        # Initialize SkillRegistry for centralized search (lazy)
        self.skills_dir = skills_dir or Path(".agent/skills")
        self._skill_registry = None

        self._load_registry()

    def _get_skill_registry(self):
        """Get or initialize SkillRegistry lazily."""
        if self._skill_registry is None:
            try:
                # Lazy import to avoid circular dependencies
                from skill_registry import SkillRegistry

                self._skill_registry = SkillRegistry.instance(self.skills_dir)
            except ImportError:
                try:
                    from .skill_registry import SkillRegistry

                    self._skill_registry = SkillRegistry.instance(self.skills_dir)
                except Exception as e:
                    logger.warning(f"SkillRegistry initialization failed: {e}")
                    self._skill_registry = False  # Mark as failed

        return self._skill_registry if self._skill_registry is not False else None

    @property
    def skill_registry(self):
        """Get SkillRegistry instance (lazy-loaded)."""
        return self._get_skill_registry()

    def _load_registry(self):
        """Cargar registro de skills."""
        registry_file = self.registry_path / "index.json"

        if registry_file.exists():
            try:
                data = json.loads(registry_file.read_text(encoding="utf-8"))
                for skill_name, versions in data.items():
                    self.skills[skill_name] = {}
                    for version_str, version_data in versions.items():
                        self.skills[skill_name][version_str] = SkillVersion(
                            version=version_str,
                            path=Path(version_data["path"]),
                            metadata=self._parse_metadata(version_data["metadata"]),
                            published_at=version_data["published_at"],
                        )
            except Exception as e:
                logger.warning(f"Error cargando registry: {e}")

        logger.info(f"Cargados {len(self.skills)} skills del marketplace")

    def _parse_metadata(self, data: dict) -> SkillMetadata:
        """Parsear metadata de dict."""
        return SkillMetadata(
            name=data["name"],
            version=data["version"],
            description=data.get("description", ""),
            author=data.get("author", "unknown"),
            tags=data.get("tags", []),
            dependencies=[SkillDependency(**d) for d in data.get("dependencies", [])],
            changelog=[ChangelogEntry(**c) for c in data.get("changelog", [])],
            created_at=data.get("created_at", datetime.now().isoformat()),
            updated_at=data.get("updated_at", datetime.now().isoformat()),
            downloads=data.get("downloads", 0),
            rating=data.get("rating", 0.0),
        )

    def _save_registry(self):
        """Guardar registro a disco."""
        registry_file = self.registry_path / "index.json"

        data = {}
        for skill_name, versions in self.skills.items():
            data[skill_name] = {}
            for version_str, skill_version in versions.items():
                data[skill_name][version_str] = skill_version.to_dict()

        registry_file.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    def publish(
        self,
        name: str,
        version: str,
        path: Path = None,
        description: str = "",
        author: str = "unknown",
        tags: list[str] = None,
        dependencies: list[SkillDependency] = None,
        changes: list[str] = None,
        breaking_changes: list[str] = None,
    ) -> SkillMetadata:
        """
        Publicar una nueva version de un skill.

        Args:
            name: Nombre del skill
            version: Version (semver)
            path: Path al directorio del skill
            description: Descripcion
            author: Autor
            tags: Tags para busqueda
            dependencies: Dependencias
            changes: Cambios en esta version
            breaking_changes: Cambios que rompen compatibilidad

        Returns:
            Metadata del skill publicado
        """
        # Validar version
        SemanticVersion.parse(version)

        # Verificar que no exista ya
        if name in self.skills and version in self.skills[name]:
            raise ValueError(f"Version {version} de {name} ya existe")

        # Copiar skill al marketplace
        dest_path = self.cache_path / name / version
        dest_path.mkdir(parents=True, exist_ok=True)

        if path and path.is_dir():
            shutil.copytree(path, dest_path, dirs_exist_ok=True)
        elif path:
            raise ValueError(f"Path debe ser un directorio: {path}")
        else:
            # Si no hay path, crear un directorio vacio o con un placeholder
            (dest_path / "SKILL.md").write_text(f"# {name} v{version}\n{description}")

        # Crear changelog entry
        changelog_entry = ChangelogEntry(
            version=version,
            date=datetime.now().strftime("%Y-%m-%d"),
            changes=changes or ["Initial release" if version == "1.0.0" else "Updates"],
            breaking_changes=breaking_changes or [],
            deprecations=[],
        )

        # Obtener changelog previo si existe
        previous_changelog = []
        if name in self.skills:
            latest = self.get_latest_version(name)
            if latest:
                previous_changelog = latest.metadata.changelog

        # Crear metadata
        metadata = SkillMetadata(
            name=name,
            version=version,
            description=description,
            author=author,
            tags=tags or [],
            dependencies=dependencies or [],
            changelog=[changelog_entry] + previous_changelog,
            created_at=datetime.now().isoformat()
            if name not in self.skills
            else list(self.skills.get(name, {}).values())[0].metadata.created_at
            if self.skills.get(name)
            else datetime.now().isoformat(),
            updated_at=datetime.now().isoformat(),
        )

        # Registrar version
        if name not in self.skills:
            self.skills[name] = {}

        self.skills[name][version] = SkillVersion(
            version=version,
            path=dest_path,
            metadata=metadata,
            published_at=datetime.now().isoformat(),
        )

        self._save_registry()

        logger.info(f"Skill {name}@{version} publicado exitosamente")

        return metadata

    def get_latest_version(self, name: str) -> SkillVersion | None:
        """Obtener la version mas reciente de un skill."""
        if name not in self.skills:
            return None

        versions = list(self.skills[name].keys())
        if not versions:
            return None

        # Ordenar por semver
        sorted_versions = sorted(versions, key=lambda v: SemanticVersion.parse(v), reverse=True)

        return self.skills[name][sorted_versions[0]]

    def get_version(self, name: str, version_constraint: str = "latest") -> SkillVersion | None:
        """
        Obtener version que satisface una constraint.

        Args:
            name: Nombre del skill
            version_constraint: "latest", "1.0.0", "^1.0.0", "~1.0.0", etc.

        Returns:
            SkillVersion o None
        """
        if name not in self.skills:
            return None

        if version_constraint == "latest":
            return self.get_latest_version(name)

        if version_constraint in self.skills[name]:
            return self.skills[name][version_constraint]

        # Buscar version que satisfaga constraint
        for version_str in sorted(
            self.skills[name].keys(), key=lambda v: SemanticVersion.parse(v), reverse=True
        ):
            if SemanticVersion.parse(version_str).satisfies(version_constraint):
                return self.skills[name][version_str]

        return None

    def search(
        self, query: str = "", tags: list[str] = None, limit: int = 20
    ) -> list[SkillMetadata]:
        """Alias para search_skills para compatibilidad."""
        return self.search_skills(query, tags, limit)

    def search_skills(
        self, query: str = "", tags: list[str] = None, limit: int = 20
    ) -> list[SkillMetadata]:
        """
        Buscar skills en el marketplace.

        Usa SkillRegistry para búsqueda semántica cuando disponible.

        Args:
            query: Texto a buscar en nombre y descripcion
            tags: Tags requeridos
            limit: Numero maximo de resultados

        Returns:
            Lista de metadata de skills
        """
        # Preferir búsqueda con SkillRegistry (semántica + keyword)
        if self.skill_registry and query:
            results = []
            registry_results = self.skill_registry.search(query, k=limit)

            for skill_name, _score in registry_results:
                latest = self.get_latest_version(skill_name)
                if latest and (not tags or all(tag in latest.metadata.tags for tag in tags)):
                    results.append(latest.metadata)

            if results:
                return results

        # Fallback: búsqueda manual en marketplace
        results = []
        query_lower = query.lower()

        for skill_name, _versions in self.skills.items():
            latest = self.get_latest_version(skill_name)
            if not latest:
                continue

            metadata = latest.metadata

            # Filtrar por query
            if (
                query
                and query_lower not in skill_name.lower()
                and query_lower not in metadata.description.lower()
            ):
                continue

            # Filtrar por tags
            if tags and not all(tag in metadata.tags for tag in tags):
                continue

            results.append(metadata)

        # Ordenar por rating y downloads
        results.sort(key=lambda m: (m.rating, m.downloads), reverse=True)

        return results[:limit]

    def install(
        self, name: str, version_constraint: str = "latest", target_path: Path | None = None
    ) -> Path | None:
        """
        Instalar un skill.

        Args:
            name: Nombre del skill
            version_constraint: Constraint de version
            target_path: Path de destino (default: .agent/skills/)

        Returns:
            Path donde se instalo o None si fallo
        """
        skill = self.get_version(name, version_constraint)

        if not skill:
            logger.error(f"Skill {name}@{version_constraint} no encontrado")
            return None

        # Determinar destino
        if target_path is None:
            target_path = Path.cwd() / ".agent" / "skills" / name
        else:
            target_path = target_path / name

        target_path.mkdir(parents=True, exist_ok=True)

        # Copiar skill
        shutil.copytree(skill.path, target_path, dirs_exist_ok=True)

        # Incrementar contador de downloads
        skill.metadata.downloads += 1
        self._save_registry()

        logger.info(f"Skill {name}@{skill.version} instalado en {target_path}")

        # Instalar dependencias
        for dep in skill.metadata.dependencies:
            if not dep.optional:
                self.install(dep.name, dep.version_constraint, target_path.parent)

        return target_path

    def list_skills(self) -> list[dict]:
        """Listar todos los skills disponibles."""
        return [
            {
                "name": name,
                "latest_version": self.get_latest_version(name).version
                if self.get_latest_version(name)
                else None,
                "versions_count": len(versions),
                "description": self.get_latest_version(name).metadata.description
                if self.get_latest_version(name)
                else "",
            }
            for name, versions in self.skills.items()
        ]

    def get_changelog(self, name: str) -> list[ChangelogEntry]:
        """Obtener changelog completo de un skill."""
        latest = self.get_latest_version(name)
        if not latest:
            return []
        return latest.metadata.changelog

    # -------------------------------------------------------------------
    # Dynamic Ranking System
    # -------------------------------------------------------------------

    def record_skill_usage(
        self,
        skill_name: str,
        task_type: str,
        success: bool,
        quality_score: float = 0.0,
        user_rating: float | None = None,
    ) -> None:
        """Registrar uso de un skill para alimentar el ranking dinamico.

        Args:
            skill_name: Nombre del skill usado
            task_type: Tipo de tarea (frontend, backend, testing, etc.)
            success: Si la ejecucion fue exitosa
            quality_score: Calidad del output (0-1)
            user_rating: Rating del usuario (1-5, opcional)
        """
        usage_file = self.storage_path / "usage_stats.json"
        stats: dict = {}
        if usage_file.exists():
            try:
                stats = json.loads(usage_file.read_text(encoding="utf-8"))
            except Exception:
                stats = {}

        key = f"{skill_name}:{task_type}"
        if key not in stats:
            stats[key] = {
                "skill_name": skill_name,
                "task_type": task_type,
                "total_uses": 0,
                "successes": 0,
                "total_quality": 0.0,
                "ratings": [],
            }

        entry = stats[key]
        entry["total_uses"] += 1
        if success:
            entry["successes"] += 1
        entry["total_quality"] += quality_score
        if user_rating is not None:
            entry["ratings"].append(user_rating)
            # Mantener solo los ultimos 50 ratings
            entry["ratings"] = entry["ratings"][-50:]

        usage_file.write_text(json.dumps(stats, indent=2))

    def get_ranked_skills(
        self,
        task_type: str | None = None,
        limit: int = 20,
        min_uses: int = 1,
    ) -> list[dict]:
        """Obtener skills rankeados por efectividad.

        El ranking combina:
        - Success rate (40%)
        - Average quality (30%)
        - User rating (20%)
        - Usage volume (10%)

        Args:
            task_type: Filtrar por tipo de tarea (None = todos)
            limit: Maximo de resultados
            min_uses: Minimo de usos para aparecer en ranking

        Returns:
            Lista ordenada de skills con metricas
        """
        usage_file = self.storage_path / "usage_stats.json"
        if not usage_file.exists():
            return []

        try:
            stats = json.loads(usage_file.read_text(encoding="utf-8"))
        except Exception:
            return []

        ranked: list[dict] = []
        for key, entry in stats.items():
            if entry["total_uses"] < min_uses:
                continue
            if task_type and entry["task_type"] != task_type:
                continue

            total = entry["total_uses"]
            success_rate = entry["successes"] / total if total > 0 else 0.0
            avg_quality = entry["total_quality"] / total if total > 0 else 0.0
            ratings = entry.get("ratings", [])
            avg_rating = (sum(ratings) / len(ratings) / 5.0) if ratings else 0.5
            # Volume normalized: log scale, cap at 100 uses
            volume_score = min(1.0, math.log10(total + 1) / 2.0)

            composite = (
                success_rate * 0.40 + avg_quality * 0.30 + avg_rating * 0.20 + volume_score * 0.10
            )

            ranked.append(
                {
                    "skill_name": entry["skill_name"],
                    "task_type": entry["task_type"],
                    "composite_score": round(composite, 3),
                    "success_rate": round(success_rate, 3),
                    "avg_quality": round(avg_quality, 3),
                    "avg_rating": round(avg_rating * 5, 1),
                    "total_uses": total,
                }
            )

        ranked.sort(key=lambda r: r["composite_score"], reverse=True)
        return ranked[:limit]

    def recommend_skills(
        self,
        task: str,
        available_skills: list[str] | None = None,
        top_k: int = 5,
    ) -> list[dict]:
        """Recomendar skills para una tarea basandose en historial.

        Combina:
        - Afinidad del nombre del skill con la tarea
        - Performance historica del skill para el tipo de tarea
        - Popularidad general

        Args:
            task: Descripcion de la tarea
            available_skills: Lista de skills disponibles (None = todos registrados)
            top_k: Cuantas recomendaciones devolver

        Returns:
            Lista de recomendaciones con score y justificacion
        """
        from ..intelligence_hub import TASK_TYPE_KEYWORDS, classify_task

        task_type = classify_task(task)
        task_lower = task.lower()
        candidates = available_skills or list(self.skills)

        # Cargar stats de uso
        usage_file = self.storage_path / "usage_stats.json"
        usage_stats: dict = {}
        if usage_file.exists():
            try:
                usage_stats = json.loads(usage_file.read_text(encoding="utf-8"))
            except Exception:
                pass

        recommendations: list[dict] = []
        for skill_name in candidates:
            score = 0.0
            reasons: list[str] = []

            # Factor 1: Name affinity (0-0.35)
            name_parts = set(skill_name.replace("-", " ").replace("_", " ").lower().split())
            task_words = set(task_lower.split())
            overlap = len(name_parts & task_words)
            name_affinity = min(1.0, overlap / max(len(name_parts), 1))
            score += name_affinity * 0.35
            if name_affinity > 0.2:
                reasons.append(f"Nombre afin a la tarea ({name_affinity:.0%})")

            # Factor 2: Task type keywords (0-0.25)
            type_kws = TASK_TYPE_KEYWORDS.get(task_type, [])
            type_match = sum(1 for kw in type_kws if kw in skill_name.lower())
            type_score = min(1.0, type_match / max(len(type_kws), 1))
            score += type_score * 0.25
            if type_score > 0:
                reasons.append(f"Relevante para tipo '{task_type}'")

            # Factor 3: Historical performance (0-0.30)
            usage_key = f"{skill_name}:{task_type}"
            usage = usage_stats.get(usage_key)
            if usage and usage["total_uses"] >= 2:
                sr = usage["successes"] / usage["total_uses"]
                aq = usage["total_quality"] / usage["total_uses"]
                perf = sr * 0.6 + aq * 0.4
                score += perf * 0.30
                reasons.append(f"Historial: {usage['total_uses']} usos, {sr:.0%} exito")
            else:
                score += 0.10  # Exploration bonus
                reasons.append("Sin historial (exploration)")

            # Factor 4: General popularity (0-0.10)
            total_uses_all = sum(
                v["total_uses"] for k, v in usage_stats.items() if v["skill_name"] == skill_name
            )
            if total_uses_all > 0:
                pop_score = min(1.0, math.log10(total_uses_all + 1) / 2.0)
                score += pop_score * 0.10

            recommendations.append(
                {
                    "skill_name": skill_name,
                    "score": round(score, 3),
                    "reasons": reasons,
                    "task_type": task_type,
                }
            )

        recommendations.sort(key=lambda r: r["score"], reverse=True)
        return recommendations[:top_k]


# Singleton
_marketplace: SkillMarketplace | None = None


def get_marketplace() -> SkillMarketplace:
    """Obtener instancia del marketplace."""
    global _marketplace
    if _marketplace is None:
        _marketplace = SkillMarketplace()
    return _marketplace
