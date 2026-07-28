"""Cross-Project Intelligence — inteligencia que cruza entre proyectos.

Cuando se inyecta MCP en un proyecto nuevo, busca en la knowledge base
de Nexus si hay soluciones, decisiones o patterns de otros proyectos
que puedan ser relevantes.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class CrossProjectInsight:
    """Insight encontrado en otro proyecto."""

    source_project: str
    insight_type: str  # "error_solution" | "decision" | "pattern" | "skill_used"
    content: str
    relevance_score: float = 0.0
    file_path: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict."""
        return {
            "source_project": self.source_project,
            "insight_type": self.insight_type,
            "content": self.content,
            "relevance_score": self.relevance_score,
            "file_path": self.file_path,
        }


@dataclass
class CrossProjectReport:
    """Reporte de inteligencia cross-project."""

    target_project: str
    target_stack: list[str] = field(default_factory=list)
    insights: list[CrossProjectInsight] = field(default_factory=list)
    similar_projects: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict."""
        return {
            "target_project": self.target_project,
            "target_stack": self.target_stack,
            "insights": [i.to_dict() for i in self.insights],
            "similar_projects": self.similar_projects,
            "summary": {
                "total_insights": len(self.insights),
                "similar_projects": len(self.similar_projects),
                "by_type": self._count_by_type(),
            },
        }

    def _count_by_type(self) -> dict[str, int]:
        """Cuenta insights por tipo."""
        counts: dict[str, int] = {}
        for insight in self.insights:
            counts[insight.insight_type] = counts.get(insight.insight_type, 0) + 1
        return counts


def _get_knowledge_base_dir() -> Path | None:
    """Localiza el directorio de la knowledge base de Nexus."""
    import platform

    system = platform.system()
    if system == "Windows":
        base = Path(os.environ.get("APPDATA", "")) / "com.antigravity.nexus"
    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support" / "com.antigravity.nexus"
    else:
        base = Path.home() / ".local" / "share" / "com.antigravity.nexus"

    kb_dir = base / "knowledge"
    if kb_dir.is_dir():
        return kb_dir
    return None


def _load_manifest(kb_dir: Path) -> dict[str, Any]:
    """Carga el manifest de la knowledge base."""
    manifest_file = kb_dir / "manifest.json"
    if not manifest_file.exists():
        return {}
    try:
        return json.loads(manifest_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _classify_insight_type(content_lower: str) -> str:
    """Clasifica el tipo de insight según palabras clave del contenido.

    Args:
        content_lower: Contenido del archivo en minúsculas.

    Returns:
        "error_solution", "decision", "skill_used" o "pattern" (default).
    """
    if any(kw in content_lower for kw in ("error", "fix", "bug", "issue", "resolved")):
        return "error_solution"
    if any(kw in content_lower for kw in ("decision", "decided", "approach", "architecture")):
        return "decision"
    if any(kw in content_lower for kw in ("skill", "agent", "tool")):
        return "skill_used"
    return "pattern"


def _build_file_insight(
    filepath: Path, project_name: str, filename: str, query: str, query_lower: str
) -> CrossProjectInsight | None:
    """Construye un CrossProjectInsight desde un archivo si matchea la query.

    Args:
        filepath: Ruta absoluta del archivo.
        project_name: Nombre del proyecto de origen.
        filename: Nombre relativo del archivo (para el insight).
        query: Query original (para el largo del snippet).
        query_lower: Query en minúsculas.

    Returns:
        El insight con snippet y score, o None si no existe/no matchea.
    """
    if not filepath.exists():
        return None
    try:
        content = filepath.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None

    content_lower = content.lower()
    if query_lower not in content_lower:
        return None

    occurrences = content_lower.count(query_lower)
    score = min(1.0, occurrences / 5.0)
    insight_type = _classify_insight_type(content_lower)

    # Extract relevant snippet (context around first match)
    idx = content_lower.find(query_lower)
    start = max(0, idx - 200)
    end = min(len(content), idx + len(query) + 200)
    snippet = content[start:end].strip()
    if start > 0:
        snippet = "..." + snippet
    if end < len(content):
        snippet = snippet + "..."

    return CrossProjectInsight(
        source_project=project_name,
        insight_type=insight_type,
        content=snippet,
        relevance_score=score,
        file_path=filename,
    )


def _search_knowledge_files(
    kb_dir: Path,
    manifest: dict[str, Any],
    query: str,
    *,
    limit: int = 10,
) -> list[CrossProjectInsight]:
    """Busca en los archivos de la knowledge base."""
    insights: list[CrossProjectInsight] = []
    query_lower = query.lower()
    projects = manifest.get("projects", {})

    for project_name, project_data in projects.items():
        project_dir = kb_dir / project_name
        for filename in project_data.get("files", {}):
            insight = _build_file_insight(
                project_dir / filename, project_name, filename, query, query_lower
            )
            if insight is not None:
                insights.append(insight)

    # Sort by score and limit
    insights.sort(key=lambda i: i.relevance_score, reverse=True)
    return insights[:limit]


def _detect_similar_projects(
    target_stack: list[str],
    manifest: dict[str, Any],
    kb_dir: Path,
) -> list[str]:
    """Detecta proyectos similares por stack tecnológico."""
    similar: list[str] = []
    target_set = {s.lower() for s in target_stack}

    for project_name, project_data in manifest.get("projects", {}).items():
        project_dir = kb_dir / project_name
        if not project_dir.is_dir():
            continue

        # Read any available file to detect stack
        stack_keywords: set[str] = set()
        for filename in list(project_data.get("files", {}).keys())[:3]:
            filepath = project_dir / filename
            if filepath.exists():
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore").lower()
                    for tech in (
                        "react",
                        "next",
                        "vue",
                        "angular",
                        "svelte",
                        "fastapi",
                        "django",
                        "flask",
                        "express",
                        "typescript",
                        "python",
                        "rust",
                        "go",
                        "prisma",
                        "sqlalchemy",
                        "mongodb",
                        "docker",
                        "kubernetes",
                        "terraform",
                    ):
                        if tech in content:
                            stack_keywords.add(tech)
                except OSError:
                    continue

        # Calculate similarity
        overlap = target_set & stack_keywords
        if len(overlap) >= 2:
            similar.append(project_name)

    return similar


def analyze_cross_project(
    target_dir: str | Path,
    *,
    query: str = "",
    limit: int = 15,
) -> CrossProjectReport:
    """Analiza inteligencia cross-project para un proyecto destino.

    Args:
        target_dir: Directorio del proyecto destino.
        query: Consulta específica (si vacía, usa el stack detectado).
        limit: Máximo de insights.

    Returns:
        CrossProjectReport con insights y proyectos similares.
    """
    target = Path(target_dir).resolve()
    report = CrossProjectReport(target_project=target.name)

    # Detect target stack
    try:
        from .injection_intelligence import detect_stack

        profile = detect_stack(str(target))
        report.target_stack = profile.languages + profile.frameworks
    except Exception as e:
        logger.debug("No se pudo detectar stack: %s", e)

    # Find knowledge base
    kb_dir = _get_knowledge_base_dir()
    if kb_dir is None:
        logger.info("Knowledge base no encontrada — no hay datos cross-project")
        return report

    manifest = _load_manifest(kb_dir)
    if not manifest:
        logger.info("Manifest vacío — no hay proyectos absorbidos")
        return report

    # Search for relevant insights
    search_terms = [query] if query else report.target_stack[:3]
    for term in search_terms:
        if term:
            insights = _search_knowledge_files(
                kb_dir, manifest, term, limit=limit // max(1, len(search_terms))
            )
            report.insights.extend(insights)

    # Deduplicate by content hash
    seen: set[str] = set()
    unique: list[CrossProjectInsight] = []
    for insight in report.insights:
        key = f"{insight.source_project}:{insight.file_path}"
        if key not in seen:
            seen.add(key)
            unique.append(insight)
    report.insights = unique[:limit]

    # Find similar projects
    if report.target_stack:
        report.similar_projects = _detect_similar_projects(report.target_stack, manifest, kb_dir)

    logger.info(
        "Cross-project analysis para %s: %d insights, %d proyectos similares",
        target.name,
        len(report.insights),
        len(report.similar_projects),
    )
    return report


def enrich_injection_context(
    target_dir: str | Path,
    existing_context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Enriquece el contexto de inyección con inteligencia cross-project.

    Se llama durante inject_mcp para agregar recomendaciones
    basadas en proyectos similares previos.

    Args:
        target_dir: Directorio destino.
        existing_context: Contexto existente a enriquecer.

    Returns:
        Contexto enriquecido con insights cross-project.
    """
    ctx = existing_context or {}
    report = analyze_cross_project(target_dir)

    if report.insights:
        ctx["cross_project"] = {
            "insights": [i.to_dict() for i in report.insights[:5]],
            "similar_projects": report.similar_projects,
            "recommendations": [],
        }

        # Generate recommendations from insights
        recommendations: list[str] = []
        for insight in report.insights[:3]:
            if insight.insight_type == "error_solution":
                recommendations.append(
                    f"En {insight.source_project} se resolvió un problema similar: "
                    f"{insight.content[:100]}"
                )
            elif insight.insight_type == "decision":
                recommendations.append(
                    f"En {insight.source_project} se tomó esta decisión: {insight.content[:100]}"
                )

        ctx["cross_project"]["recommendations"] = recommendations

    return ctx
