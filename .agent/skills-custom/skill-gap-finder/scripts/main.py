"""
Skill Gap Finder — Identifica capacidades faltantes en el ecosistema.

Uso:
    python main.py
    python main.py --task "security"
    python main.py --json
"""

from __future__ import annotations

import argparse
import json
from dataclasses import dataclass, field
from pathlib import Path


ECOSYSTEM_ROOT = Path(__file__).parents[4]

SKILLS_DIRS = [
    ECOSYSTEM_ROOT / "skills",
    ECOSYSTEM_ROOT / "skills-custom",
]

# Base de conocimiento: capacidades esperadas por categoría
# formato: {categoría: [(skill_name_pattern, descripcion, prioridad: alta|media|baja)]}
EXPECTED_CAPABILITIES: dict[str, list[tuple[str, str, str]]] = {
    "security": [
        ("secret", "Detección de secrets/tokens hardcodeados en código", "alta"),
        ("sast", "Análisis estático de seguridad (SAST)", "alta"),
        ("dependency", "Auditoría de dependencias vulnerables", "alta"),
        ("pentest", "Guía de penetration testing básico", "media"),
        ("owasp", "Checklist OWASP Top 10", "media"),
        ("cve", "Búsqueda y evaluación de CVEs", "media"),
        ("cors", "Validación de configuración CORS", "baja"),
    ],
    "testing": [
        ("unit", "Tests unitarios con cobertura mínima", "alta"),
        ("integration", "Tests de integración entre servicios", "alta"),
        ("e2e", "Tests end-to-end automatizados", "alta"),
        ("mutation", "Mutation testing para validar calidad de tests", "media"),
        ("property", "Property-based testing con Hypothesis", "media"),
        ("load", "Load testing / pruebas de carga", "media"),
        ("snapshot", "Snapshot testing para UIs", "baja"),
    ],
    "devops": [
        ("docker", "Optimización de Dockerfiles y multi-stage builds", "alta"),
        ("cicd", "Configuración de CI/CD pipelines", "alta"),
        ("deploy", "Estrategias de deployment (blue-green, canary)", "alta"),
        ("monitor", "Configuración de monitoring y alertas", "media"),
        ("rollback", "Procedimientos de rollback automatizado", "media"),
        ("infra", "Infrastructure as Code (Terraform/Pulumi)", "media"),
        ("secrets-mgmt", "Gestión de secrets en CI/CD", "alta"),
    ],
    "database": [
        ("migration", "Generación y aplicación de migraciones DB", "alta"),
        ("backup", "Estrategia de backup y recovery", "alta"),
        ("query-opt", "Optimización de queries lentas", "media"),
        ("schema", "Review de esquema de base de datos", "media"),
        ("index", "Análisis y creación de índices", "media"),
        ("replication", "Configuración de replicación", "baja"),
    ],
    "frontend": [
        ("a11y", "Auditoría de accesibilidad (WCAG)", "alta"),
        ("perf", "Análisis de performance web (Core Web Vitals)", "alta"),
        ("bundle", "Análisis de bundle size y tree-shaking", "media"),
        ("seo", "Auditoría SEO técnica", "media"),
        ("responsive", "Review de diseño responsive", "baja"),
    ],
    "api": [
        ("design", "Review de diseño de API (REST/GraphQL)", "alta"),
        ("rate-limit", "Implementación de rate limiting", "media"),
        ("versioning", "Estrategia de versionado de API", "media"),
        ("docs", "Generación de documentación de API (OpenAPI)", "alta"),
        ("auth", "Review de autenticación y autorización", "alta"),
    ],
    "observability": [
        ("logging", "Configuración de logging estructurado", "alta"),
        ("tracing", "Implementación de distributed tracing", "media"),
        ("metrics", "Definición y exportación de métricas custom", "media"),
        ("dashboard", "Creación de dashboards (Grafana/Datadog)", "baja"),
        ("alert", "Configuración de alertas y runbooks", "media"),
    ],
    "ai_ml": [
        ("eval", "Evaluación de modelos ML (métricas, benchmarks)", "alta"),
        ("data-val", "Validación de datasets de entrenamiento", "alta"),
        ("prompt-test", "Testing sistemático de prompts", "alta"),
        ("fine-tune", "Guía de fine-tuning de modelos", "media"),
        ("embed", "Generación y gestión de embeddings", "media"),
    ],
    "documentation": [
        ("api-doc", "Documentación de API con ejemplos", "alta"),
        ("arch-diagram", "Generación de diagramas de arquitectura", "media"),
        ("changelog", "Generación de CHANGELOG desde commits", "media"),
        ("adr", "Architecture Decision Records (ADR)", "media"),
        ("runbook", "Creación de runbooks operativos", "baja"),
    ],
    "performance": [
        ("profil", "Profiling de código Python/JS", "alta"),
        ("cache", "Estrategias de caching (Redis, CDN)", "alta"),
        ("bottleneck", "Identificación de bottlenecks", "alta"),
        ("memory", "Análisis de uso de memoria y leaks", "media"),
        ("concurrency", "Optimización de concurrencia y async", "media"),
    ],
}


@dataclass
class GapItem:
    """Un gap identificado en el ecosistema."""

    category: str
    pattern: str
    description: str
    priority: str
    matched_skills: list[str] = field(default_factory=list)

    @property
    def covered(self) -> bool:
        return len(self.matched_skills) > 0


@dataclass
class CategoryCoverage:
    """Coverage de una categoría."""

    category: str
    total_expected: int
    covered: int
    gaps: list[GapItem]

    @property
    def coverage_pct(self) -> float:
        if self.total_expected == 0:
            return 100.0
        return (self.covered / self.total_expected) * 100


def scan_skills(skills_dirs: list[Path]) -> list[str]:
    """Escanea los directorios de skills y retorna lista de nombres."""
    skill_names: list[str] = []
    for skills_dir in skills_dirs:
        if not skills_dir.exists():
            continue
        for item in skills_dir.iterdir():
            if item.is_dir() and not item.name.startswith("_"):
                skill_names.append(item.name.lower())
    return skill_names


def check_coverage(
    skill_names: list[str],
    category_filter: str | None = None,
) -> list[CategoryCoverage]:
    """Verifica coverage de capacidades esperadas contra skills existentes."""
    coverages: list[CategoryCoverage] = []

    for category, capabilities in EXPECTED_CAPABILITIES.items():
        if category_filter and category != category_filter:
            continue

        gaps: list[GapItem] = []
        for pattern, description, priority in capabilities:
            gap = GapItem(
                category=category,
                pattern=pattern,
                description=description,
                priority=priority,
            )
            # Buscar skills que contengan el patrón en su nombre
            gap.matched_skills = [s for s in skill_names if pattern in s]
            gaps.append(gap)

        covered_count = sum(1 for g in gaps if g.covered)
        coverages.append(
            CategoryCoverage(
                category=category,
                total_expected=len(capabilities),
                covered=covered_count,
                gaps=gaps,
            )
        )

    coverages.sort(key=lambda c: c.coverage_pct)
    return coverages


def format_report(
    coverages: list[CategoryCoverage],
    total_skills: int,
    category_filter: str | None,
) -> str:
    """Formatea el reporte de gaps."""
    high_priority_gaps = [
        g for c in coverages for g in c.gaps if not g.covered and g.priority == "alta"
    ]
    medium_priority_gaps = [
        g for c in coverages for g in c.gaps if not g.covered and g.priority == "media"
    ]

    lines: list[str] = [
        "=== SKILL GAP FINDER REPORT ===",
        f"Skills escaneadas: {total_skills} total",
        f"Categorías analizadas: {len(coverages)}"
        + (f" (filtro: {category_filter})" if category_filter else ""),
        f"Gaps de alta prioridad: {len(high_priority_gaps)}",
        f"Gaps de prioridad media: {len(medium_priority_gaps)}",
        "",
        "COVERAGE POR CATEGORÍA:",
    ]

    for cov in coverages:
        bar_filled = int(cov.coverage_pct / 10)
        bar = "=" * bar_filled + "-" * (10 - bar_filled)
        lines.append(
            f"  [{bar}] {cov.coverage_pct:>5.1f}%  {cov.category:<20} "
            f"({cov.covered}/{cov.total_expected} capacidades)"
        )

    if high_priority_gaps:
        lines.append("\nGAPS DE ALTA PRIORIDAD:")
        for g in high_priority_gaps:
            lines.append(f"  [{g.category:<15}] {g.pattern:<20} — {g.description}")

    if medium_priority_gaps:
        lines.append("\nGAPS DE PRIORIDAD MEDIA:")
        for g in medium_priority_gaps:
            lines.append(f"  [{g.category:<15}] {g.pattern:<20} — {g.description}")

    lines.append("\nRECOMENDACION: Crear skills para los gaps de alta prioridad primero.")
    lines.append("Usar '.agent/skills-custom/<nombre>/SKILL.md' como plantilla.")

    return "\n".join(lines)


def main() -> None:
    """Entry point del script."""
    parser = argparse.ArgumentParser(description="Identifica gaps de capacidades en el ecosistema.")
    parser.add_argument("--task", help="Categoría específica a analizar (ej: security, testing)")
    parser.add_argument("--json", action="store_true", help="Salida en formato JSON")
    args = parser.parse_args()

    category_filter = args.task.strip().lower() if args.task else None
    skill_names = scan_skills(SKILLS_DIRS)
    total_skills = len(skill_names)
    coverages = check_coverage(skill_names, category_filter)

    if args.json:
        output = {
            "total_skills_scanned": total_skills,
            "category_filter": category_filter,
            "coverages": [
                {
                    "category": c.category,
                    "coverage_pct": round(c.coverage_pct, 1),
                    "covered": c.covered,
                    "total_expected": c.total_expected,
                    "gaps": [
                        {
                            "pattern": g.pattern,
                            "description": g.description,
                            "priority": g.priority,
                            "covered": g.covered,
                            "matched_skills": g.matched_skills,
                        }
                        for g in c.gaps
                        if not g.covered
                    ],
                }
                for c in coverages
            ],
        }
        print(json.dumps(output, ensure_ascii=False, indent=2))
    else:
        print(format_report(coverages, total_skills, category_filter))


if __name__ == "__main__":
    main()
