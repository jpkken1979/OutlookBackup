#!/usr/bin/env python3
"""
Skill Record — Canonical unified data model for all skills.

This is the single source of truth for skill metadata across the entire
ecosystem. All skill-management modules (search, composer, eligibility, etc.)
should use this model.

Unifies 7 fragmented representations:
1. skill_composer.py:SkillMetadata
2. skill_search.py:SkillInfo
3. intelligence/skill_composition.py:SkillInfo
4. skill_eligibility.py:SkillFrontmatter
5. skill_orchestration.py:SkillMatch
6. skills-server.py (MCP)
7. skill_marketplace/__init__.py

Version: 1.0.0 (Phase 1 Consolidation — Fase 1)
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator


class SkillCategory(str, Enum):
    """Categorías estándar de skills."""

    BACKEND_API = "backend-api"
    FRONTEND_UI = "frontend-ui"
    DATA_ML = "data-ml"
    DEVOPS = "devops"
    SECURITY = "security"
    TESTING = "testing"
    MONITORING = "monitoring"
    DOCUMENTATION = "documentation"
    PERFORMANCE = "performance"
    DEBUGGING = "debugging"
    SYSTEMS = "systems"
    ENTERPRISE = "enterprise"
    OTHER = "other"


class SkillStatus(str, Enum):
    """Estado de una skill."""

    ACTIVE = "active"
    DEPRECATED = "deprecated"
    BETA = "beta"
    ARCHIVED = "archived"


class SkillInterface(BaseModel):
    """Interfaz de entrada/salida de una skill."""

    inputs: list[str] = Field(default_factory=list)
    outputs: list[str] = Field(default_factory=list)
    input_description: str = ""
    output_description: str = ""


class SkillDependency(BaseModel):
    """Dependencia declarada en frontmatter."""

    type: str  # "binary", "env_var", "python_module", "skill", "api"
    name: str
    version_min: str | None = None
    optional: bool = False


class SkillMetrics(BaseModel):
    """Métricas de rendimiento y uso."""

    estimated_time_ms: int = 1000
    memory_mb: int = 0
    invocations: int = 0
    success_rate: float = 1.0
    last_invoked: datetime | None = None


class SkillRecord(BaseModel):
    """
    Canonical unified skill record.

    Unifica todos los campos de:
    - SkillMetadata (skill_composer.py)
    - SkillInfo (skill_search.py, intelligence/skill_composition.py)
    - SkillFrontmatter (skill_eligibility.py)
    - SkillMatch (skill_orchestration.py)

    Usa Progressive Disclosure:
    - Tier 1 (siempre en memoria): name, path, description, category, status, version
    - Tier 2 (lazy-loaded): content, interface, dependencies, metrics
    - Tier 3 (on-demand): full_frontmatter, test_coverage, security_scan_result
    """

    # === TIER 1: Core Identification (siempre en memoria)
    name: str = Field(..., description="Identificador único del skill")
    path: Path | str = Field(..., description="Ruta absoluta al directorio del skill")
    description: str = Field("", description="Descripción corta (1-2 líneas)")
    category: SkillCategory = Field(default=SkillCategory.OTHER)
    status: SkillStatus = Field(default=SkillStatus.ACTIVE)
    version: str = Field(default="1.0.0")

    # === TIER 1: Metadata Básica
    tags: list[str] = Field(default_factory=list)
    author: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None
    triggers: list[str] = Field(
        default_factory=list, description="Regex patterns para auto-invocación"
    )

    # === TIER 2: Interface (lazy-loaded)
    interface: SkillInterface = Field(default_factory=SkillInterface)
    dependencies: list[SkillDependency] = Field(
        default_factory=list,
        description="Binarios, env vars, módulos Python, otras skills, APIs requeridas",
    )

    # === TIER 2: Content (lazy-loaded)
    content: str = ""
    content_hash: str = ""

    # === TIER 2: Metrics
    metrics: SkillMetrics = Field(default_factory=SkillMetrics)

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        use_enum_values=False,
        json_schema_extra={
            "example": {
                "name": "api-patterns",
                "path": "/home/user/OpenAntigravity/.agent/skills/api-patterns",
                "description": "Design RESTful APIs following OpenAPI 3.1 specification",
                "category": "backend-api",
                "status": "active",
                "version": "2.1.0",
                "tags": ["REST", "OpenAPI", "API-Design"],
                "interface": {
                    "inputs": ["api_requirements"],
                    "outputs": ["openapi_spec", "implementation_guide"],
                    "input_description": "Requirements and constraints for the API",
                    "output_description": "Complete OpenAPI spec and implementation guide",
                },
            }
        },
    )

    # === TIER 3: Advanced (on-demand)
    test_coverage_percent: float | None = None
    security_scan_result: dict[str, Any] = Field(default_factory=dict)
    compatibility_matrix: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Compatibilidad con versiones de dependencias: {'python': ['3.11', '3.12'], 'node': ['20']}",
    )

    # === Metadata Interna
    is_public: bool = True
    is_hidden: bool = False
    plugin_enabled: bool = True

    @field_validator("path", mode="before")
    @classmethod
    def ensure_path_object(cls, v: Any) -> Path:
        """Convertir string a Path."""
        if isinstance(v, str):
            return Path(v)
        return v

    def to_dict(self) -> dict[str, Any]:
        """Exportar a diccionario (para APIs REST)."""
        return self.model_dump(mode="python", exclude_none=True)

    def to_search_document(self) -> str:
        """Generar documento indexable para búsqueda semántica."""
        category_value = (
            self.category.value if isinstance(self.category, Enum) else str(self.category)
        )
        parts = [
            f"Skill: {self.name}",
            self.description,
            f"Category: {category_value}",
            f"Tags: {', '.join(self.tags)}",
            f"Triggers: {', '.join(self.triggers)}",
        ]
        if self.interface.inputs:
            parts.append(f"Input types: {', '.join(self.interface.inputs)}")
        if self.interface.outputs:
            parts.append(f"Output types: {', '.join(self.interface.outputs)}")
        # Include first 500 chars of content for keyword matching
        if self.content:
            parts.append(self.content[:500])
        return "\n".join(p for p in parts if p)

    @property
    def skill_id(self) -> str:
        """Alias para name (para compatibilidad)."""
        return self.name

    @property
    def directory(self) -> Path:
        """Alias para path (para compatibilidad)."""
        return Path(self.path) if isinstance(self.path, str) else self.path


@dataclass
class SkillRecordLazy:
    """
    Lightweight wrapper para SkillRecord con carga perezosa.

    Carga el frontmatter YAML (~2KB) inmediatamente,
    pero defiere el contenido completo hasta que se necesite.
    """

    name: str
    path: Path
    frontmatter: dict[str, Any]  # Parsed YAML frontmatter
    content: str = ""
    content_loaded: bool = False

    def to_record(self) -> SkillRecord:
        """Convertir a SkillRecord completo (carga contenido si no está cargado)."""
        return SkillRecord(
            name=self.name,
            path=self.path,
            **{k: v for k, v in self.frontmatter.items() if k not in ("name", "path", "content")},
            content=self.content if self.content_loaded else "",
        )

    @classmethod
    def from_skill_file(cls, skill_path: Path) -> SkillRecordLazy:
        """Crear desde un SKILL.md (solo carga frontmatter)."""
        import logging

        try:
            from .skill_metadata_index import _FRONTMATTER_RE, _parse_simple_yaml
        except ImportError:
            from skill_metadata_index import (  # type: ignore  # runtime path depends on execution context
                _FRONTMATTER_RE,
                _parse_simple_yaml,
            )

        logger = logging.getLogger(__name__)

        if not skill_path.is_dir():
            raise ValueError(f"Not a directory: {skill_path}")

        skill_md = skill_path / "SKILL.md"
        if not skill_md.exists():
            raise FileNotFoundError(f"Missing SKILL.md in {skill_path}")

        with open(skill_md, encoding="utf-8") as f:
            content = f.read()

        # Parse YAML frontmatter
        match = _FRONTMATTER_RE.search(content)
        if not match:
            logger.warning(f"No frontmatter found in {skill_md}")
            frontmatter = {}
        else:
            frontmatter_text = match.group(1)
            frontmatter = _parse_simple_yaml(frontmatter_text)

        return cls(
            name=skill_path.name,
            path=skill_path,
            frontmatter=frontmatter,
            content="",
            content_loaded=False,
        )
