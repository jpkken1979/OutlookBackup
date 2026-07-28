"""Modelos de datos del Brain: BrainNode y reportes de lint.

Extraido del monolito ``brain.py`` (refactor 2026-05-31). Sin cambios de
comportamiento: solo se reubicaron las definiciones y se ajustaron los imports
de los helpers (``dates`` y ``text``).
"""

from __future__ import annotations

import re
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import yaml  # type: ignore[import-untyped]

from .dates import _normalize_date_value, _parse_date_value
from .text import _parse_sections


@dataclass
class BrainNode:
    """Un nodo de conocimiento con frontmatter estructurado.

    Cada nodo representa una pieza de conocimiento: sesion, concepto,
    decision arquitectonica, entidad, o patron descubierto.
    """

    slug: str
    type: str  # session | concept | adr | entity | decision | pattern
    area: str
    date: str  # YYYY-MM-DD
    title: str
    tags: list[str] = field(default_factory=list)
    status: str = "active"
    related: list[str] = field(default_factory=list)
    sources: list[str] = field(default_factory=list)
    superseded_by: str | None = None
    app_origin: str = "unknown"
    node_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])

    # Temporal intelligence
    importance: str = "normal"  # critical | high | normal | low
    access_count: int = 0
    last_accessed: str = ""
    version: int = 1

    # Contenido por secciones
    context: str = ""
    decisions: str = ""
    output: str = ""
    pending: str = ""
    crossrefs: str = ""
    source_notes: str = ""

    def to_frontmatter(self) -> str:
        """Serializa el nodo como frontmatter YAML + contenido Markdown."""
        fm = {
            "type": self.type,
            "area": self.area,
            "date": self.date,
            "slug": self.slug,
            "title": self.title,
            "tags": self.tags,
            "status": self.status,
            "related": self.related,
            "sources": self.sources,
            "superseded_by": self.superseded_by,
            "app_origin": self.app_origin,
            "node_id": self.node_id,
            "importance": self.importance,
            "access_count": self.access_count,
            "last_accessed": self.last_accessed,
            "version": self.version,
        }
        lines = ["---"]
        lines.append(yaml.dump(fm, default_flow_style=False, allow_unicode=True).strip())
        lines.append("---")
        lines.append("")

        if self.context:
            lines.extend(["## Contexto", "", self.context, ""])
        if self.decisions:
            lines.extend(["## Decisiones", "", self.decisions, ""])
        if self.output:
            lines.extend(["## Output", "", self.output, ""])
        if self.pending:
            lines.extend(["## Pendiente", "", self.pending, ""])
        if self.crossrefs:
            lines.extend(["## Cross-refs", "", self.crossrefs, ""])
        if self.source_notes:
            lines.extend(["## Fuentes", "", self.source_notes, ""])

        return "\n".join(lines)

    def freshness_score(self) -> float:
        """Puntaje de frescura 0-1 basado en edad y importancia.

        critical = nunca decae, high = half-life 30 dias, normal = 14, low = 7.
        """
        created = _parse_date_value(self.date)
        if created is None:
            age_days = 0
        else:
            age_days = (datetime.now(UTC).replace(tzinfo=None) - created).days

        # Half-life en dias segun importancia
        half_lives = {"critical": float("inf"), "high": 30, "normal": 14, "low": 7}
        half_life = half_lives.get(self.importance, 14)

        if half_life == float("inf"):
            return 1.0

        import math

        decay = math.exp(-0.693 * age_days / half_life)  # 0.693 = ln(2)

        # Boost por accesos recientes
        access_boost = min(self.access_count * 0.02, 0.2)

        return min(decay + access_boost, 1.0)

    def one_liner(self) -> str:
        """Genera la linea del indice para este nodo."""
        tags_str = ", ".join(self.tags[:5]) if self.tags else ""
        origin = f" [{self.app_origin}]" if self.app_origin != "unknown" else ""
        return f"- [[{self.slug}]] — {self.title} ({tags_str}){origin}"

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario para APIs."""
        return asdict(self)

    @classmethod
    def from_frontmatter(cls, content: str, file_path: Path | None = None) -> BrainNode:
        """Parsea un archivo markdown con frontmatter YAML a BrainNode."""
        fm_match = re.match(r"^---\n(.*?)\n---\n?(.*)", content, re.DOTALL)
        if not fm_match:
            raise ValueError(f"No se encontro frontmatter YAML en {file_path or 'contenido'}")

        fm_text, body = fm_match.group(1), fm_match.group(2)
        fm = yaml.safe_load(fm_text) or {}

        # Extraer secciones del body
        sections = _parse_sections(body)

        return cls(
            slug=fm.get("slug", ""),
            type=fm.get("type", "session"),
            area=fm.get("area", "general"),
            date=_normalize_date_value(fm.get("date", "")),
            title=fm.get("title", ""),
            tags=fm.get("tags", []),
            status=fm.get("status", "active"),
            related=fm.get("related", []),
            sources=fm.get("sources", []),
            superseded_by=fm.get("superseded_by"),
            app_origin=fm.get("app_origin", "unknown"),
            node_id=fm.get("node_id", str(uuid.uuid4())[:8]),
            importance=fm.get("importance", "normal"),
            access_count=fm.get("access_count", 0),
            last_accessed=fm.get("last_accessed", ""),
            version=fm.get("version", 1),
            context=sections.get("contexto", ""),
            decisions=sections.get("decisiones", ""),
            output=sections.get("output", ""),
            pending=sections.get("pendiente", ""),
            crossrefs=sections.get("cross-refs", ""),
            source_notes=sections.get("fuentes", ""),
        )


@dataclass
class LintIssue:
    """Un hallazgo del proceso de lint."""

    severity: str  # error | warning | info
    category: str  # orphan | broken_link | stale | missing_crossref | concept_candidate
    message: str
    node_slug: str = ""
    suggestion: str = ""


@dataclass
class LintReport:
    """Resultado completo de un lint del brain."""

    issues: list[LintIssue] = field(default_factory=list)
    total_nodes: int = 0
    healthy_nodes: int = 0
    concept_candidates: list[str] = field(default_factory=list)

    @property
    def score(self) -> float:
        """Puntaje de salud 0-10."""
        if self.total_nodes == 0:
            return 10.0
        error_nodes = {
            issue.node_slug
            for issue in self.issues
            if issue.severity == "error" and issue.node_slug
        }
        warning_nodes = {
            issue.node_slug
            for issue in self.issues
            if issue.severity == "warning" and issue.node_slug
        }
        global_errors = sum(
            1 for issue in self.issues if issue.severity == "error" and not issue.node_slug
        )
        global_warnings = sum(
            1 for issue in self.issues if issue.severity == "warning" and not issue.node_slug
        )
        penalty = (
            len(error_nodes) * 2.0
            + len(warning_nodes) * 0.35
            + global_errors * 1.0
            + global_warnings * 0.15
        ) / max(self.total_nodes, 1)
        return max(0.0, 10.0 - penalty * 10)

    def summary(self) -> str:
        """Resumen legible del lint."""
        errors = sum(1 for i in self.issues if i.severity == "error")
        warnings = sum(1 for i in self.issues if i.severity == "warning")
        infos = sum(1 for i in self.issues if i.severity == "info")
        lines = [
            f"Brain Health: {self.score:.1f}/10",
            f"Nodos: {self.total_nodes} total, {self.healthy_nodes} sanos",
            f"Issues: {errors} errores, {warnings} warnings, {infos} info",
        ]
        if self.concept_candidates:
            lines.append(f"Conceptos emergentes: {', '.join(self.concept_candidates[:5])}")
        return "\n".join(lines)
