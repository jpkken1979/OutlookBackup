#!/usr/bin/env python3
"""
Skill Health Check - Validador de salud del ecosistema de skills.

Este script analiza todas las skills del ecosistema y genera un reporte
de salud con métricas de calidad, completitud y conformidad.

Uso:
    python skill_health_check.py                    # Reporte completo
    python skill_health_check.py --summary          # Solo resumen
    python skill_health_check.py --fix              # Sugerir correcciones
    python skill_health_check.py --export report.json
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class SkillHealth:
    """Estado de salud de una skill."""

    name: str
    path: Path
    has_skill_md: bool = False
    skill_md_lines: int = 0
    has_scripts: bool = False
    scripts_count: int = 0
    has_logging: bool = False
    has_type_hints: bool = False
    has_examples: bool = False
    has_tests: bool = False
    issues: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class EcosystemHealth:
    """Estado de salud del ecosistema completo."""

    total_skills: int = 0
    healthy_skills: int = 0
    warning_skills: int = 0
    critical_skills: int = 0
    skills_with_logging: int = 0
    skills_with_type_hints: int = 0
    skills_with_tests: int = 0
    average_score: float = 0.0
    skills: list[SkillHealth] = field(default_factory=list)


def check_python_file(filepath: Path) -> tuple[bool, bool]:
    """
    Verifica si un archivo Python tiene logging y type hints.

    Args:
        filepath: Ruta al archivo Python

    Returns:
        Tuple (has_logging, has_type_hints)
    """
    try:
        content = filepath.read_text(encoding="utf-8")

        # Verificar logging
        has_logging = "import logging" in content or "from logging" in content

        # Verificar type hints (buscar patrones como ": str", "-> int", etc.)
        type_hint_patterns = [
            r"def \w+\([^)]*:\s*\w+",  # Parámetros tipados
            r"->\s*\w+:",  # Return type
            r":\s*(str|int|float|bool|list|dict|List|Dict|Optional|Tuple)",
        ]
        has_type_hints = any(re.search(pattern, content) for pattern in type_hint_patterns)

        return has_logging, has_type_hints
    except Exception:
        return False, False


def analyze_skill(skill_path: Path) -> SkillHealth:
    """
    Analiza una skill individual.

    Args:
        skill_path: Directorio de la skill

    Returns:
        SkillHealth con el análisis
    """
    health = SkillHealth(name=skill_path.name, path=skill_path)

    # Verificar SKILL.md
    skill_md = skill_path / "SKILL.md"
    if skill_md.exists():
        health.has_skill_md = True
        try:
            content = skill_md.read_text(encoding="utf-8")
            health.skill_md_lines = len(content.splitlines())

            if health.skill_md_lines < 20:
                health.issues.append("SKILL.md muy corto (<20 líneas)")
        except Exception:
            health.issues.append("Error leyendo SKILL.md")
    else:
        health.issues.append("Falta SKILL.md")

    # Verificar scripts
    scripts_dir = skill_path / "scripts"
    if scripts_dir.exists() and scripts_dir.is_dir():
        health.has_scripts = True
        python_files = list(scripts_dir.glob("*.py"))
        health.scripts_count = len(python_files)

        # Analizar archivos Python
        logging_count = 0
        type_hints_count = 0
        for py_file in python_files:
            has_log, has_types = check_python_file(py_file)
            if has_log:
                logging_count += 1
            if has_types:
                type_hints_count += 1

        if python_files:
            health.has_logging = logging_count > 0
            health.has_type_hints = type_hints_count > 0

            if not health.has_logging:
                health.issues.append("Scripts sin logging")
            if not health.has_type_hints:
                health.issues.append("Scripts sin type hints")

    # Verificar ejemplos
    examples_dir = skill_path / "examples"
    health.has_examples = (
        examples_dir.exists() and any(examples_dir.iterdir()) if examples_dir.exists() else False
    )

    # Verificar tests
    tests_dir = skill_path / "tests"
    health.has_tests = (
        tests_dir.exists() and any(tests_dir.iterdir()) if tests_dir.exists() else False
    )

    # Calcular score (0-100)
    score = 0
    if health.has_skill_md:
        score += 20
        if health.skill_md_lines >= 50:
            score += 10
        elif health.skill_md_lines >= 20:
            score += 5
    if health.has_scripts:
        score += 20
    if health.has_logging:
        score += 15
    if health.has_type_hints:
        score += 15
    if health.has_examples:
        score += 10
    if health.has_tests:
        score += 10

    health.score = score

    return health


def analyze_ecosystem(skills_dir: Path) -> EcosystemHealth:
    """
    Analiza todo el ecosistema de skills.

    Args:
        skills_dir: Directorio raíz de skills

    Returns:
        EcosystemHealth con el análisis completo
    """
    ecosystem = EcosystemHealth()

    # Encontrar todos los directorios de skills
    skill_dirs = [d for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith(".")]

    logger.info(f"Analizando {len(skill_dirs)} skills...")

    for skill_dir in skill_dirs:
        health = analyze_skill(skill_dir)
        ecosystem.skills.append(health)
        ecosystem.total_skills += 1

        if health.score >= 70:
            ecosystem.healthy_skills += 1
        elif health.score >= 40:
            ecosystem.warning_skills += 1
        else:
            ecosystem.critical_skills += 1

        if health.has_logging:
            ecosystem.skills_with_logging += 1
        if health.has_type_hints:
            ecosystem.skills_with_type_hints += 1
        if health.has_tests:
            ecosystem.skills_with_tests += 1

    if ecosystem.total_skills > 0:
        ecosystem.average_score = sum(s.score for s in ecosystem.skills) / ecosystem.total_skills

    return ecosystem


def print_summary(ecosystem: EcosystemHealth) -> None:
    """Imprime resumen del análisis."""
    print("\n" + "=" * 60)
    print("REPORTE DE SALUD DEL ECOSISTEMA DE SKILLS")
    print("=" * 60)
    print(f"\nFecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"\n{'Métrica':<30} {'Valor':>15} {'Porcentaje':>15}")
    print("-" * 60)

    total = ecosystem.total_skills
    print(f"{'Total Skills':<30} {total:>15}")
    print(
        f"{'Skills Saludables (≥70)':<30} {ecosystem.healthy_skills:>15} {ecosystem.healthy_skills / total * 100 if total else 0:>14.1f}%"
    )
    print(
        f"{'Skills con Advertencias':<30} {ecosystem.warning_skills:>15} {ecosystem.warning_skills / total * 100 if total else 0:>14.1f}%"
    )
    print(
        f"{'Skills Críticas (<40)':<30} {ecosystem.critical_skills:>15} {ecosystem.critical_skills / total * 100 if total else 0:>14.1f}%"
    )
    print("-" * 60)
    print(
        f"{'Con Logging':<30} {ecosystem.skills_with_logging:>15} {ecosystem.skills_with_logging / total * 100 if total else 0:>14.1f}%"
    )
    print(
        f"{'Con Type Hints':<30} {ecosystem.skills_with_type_hints:>15} {ecosystem.skills_with_type_hints / total * 100 if total else 0:>14.1f}%"
    )
    print(
        f"{'Con Tests':<30} {ecosystem.skills_with_tests:>15} {ecosystem.skills_with_tests / total * 100 if total else 0:>14.1f}%"
    )
    print("-" * 60)
    print(f"{'Score Promedio':<30} {ecosystem.average_score:>14.1f}/100")
    print("=" * 60)


def print_critical_skills(ecosystem: EcosystemHealth, limit: int = 10) -> None:
    """Imprime las skills más críticas."""
    critical = sorted([s for s in ecosystem.skills if s.score < 40], key=lambda x: x.score)[:limit]

    if critical:
        print(f"\n{'TOP SKILLS CRÍTICAS (Score < 40)'}")
        print("-" * 60)
        for skill in critical:
            print(f"\n[{skill.score:>5.1f}] {skill.name}")
            for issue in skill.issues:
                print(f"        - {issue}")


def print_best_skills(ecosystem: EcosystemHealth, limit: int = 5) -> None:
    """Imprime las mejores skills como referencia."""
    best = sorted(ecosystem.skills, key=lambda x: x.score, reverse=True)[:limit]

    if best:
        print(f"\n{'TOP SKILLS DE REFERENCIA (Mejores Puntuaciones)'}")
        print("-" * 60)
        for skill in best:
            features = []
            if skill.has_logging:
                features.append("logging")
            if skill.has_type_hints:
                features.append("types")
            if skill.has_tests:
                features.append("tests")
            features_str = ", ".join(features) if features else "básico"
            print(f"[{skill.score:>5.1f}] {skill.name:<40} ({features_str})")


def export_report(ecosystem: EcosystemHealth, filepath: Path) -> None:
    """Exporta el reporte a JSON."""
    report = {
        "generated_at": datetime.now().isoformat(),
        "summary": {
            "total_skills": ecosystem.total_skills,
            "healthy_skills": ecosystem.healthy_skills,
            "warning_skills": ecosystem.warning_skills,
            "critical_skills": ecosystem.critical_skills,
            "average_score": round(ecosystem.average_score, 2),
            "skills_with_logging": ecosystem.skills_with_logging,
            "skills_with_type_hints": ecosystem.skills_with_type_hints,
            "skills_with_tests": ecosystem.skills_with_tests,
        },
        "skills": [
            {
                "name": s.name,
                "score": s.score,
                "has_skill_md": s.has_skill_md,
                "skill_md_lines": s.skill_md_lines,
                "has_scripts": s.has_scripts,
                "has_logging": s.has_logging,
                "has_type_hints": s.has_type_hints,
                "has_tests": s.has_tests,
                "issues": s.issues,
            }
            for s in ecosystem.skills
        ],
    }

    filepath.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info(f"Reporte exportado a: {filepath}")


def main():
    parser = argparse.ArgumentParser(
        description="Skill Health Check - Validador de salud del ecosistema"
    )
    parser.add_argument("--summary", action="store_true", help="Mostrar solo resumen")
    parser.add_argument("--export", type=Path, help="Exportar reporte a archivo JSON")
    parser.add_argument(
        "--skills-dir",
        type=Path,
        default=Path(__file__).parent.parent / "skills",
        help="Directorio de skills (default: .agent/skills)",
    )

    args = parser.parse_args()

    if not args.skills_dir.exists():
        logger.error(f"Directorio no encontrado: {args.skills_dir}")
        sys.exit(1)

    # Analizar ecosistema
    ecosystem = analyze_ecosystem(args.skills_dir)

    # Mostrar resultados
    print_summary(ecosystem)

    if not args.summary:
        print_best_skills(ecosystem)
        print_critical_skills(ecosystem)

    # Exportar si se solicita
    if args.export:
        export_report(ecosystem, args.export)

    # Exit code basado en salud
    if ecosystem.average_score < 30:
        sys.exit(2)  # Crítico
    elif ecosystem.average_score < 50:
        sys.exit(1)  # Warning
    else:
        sys.exit(0)  # OK


if __name__ == "__main__":
    main()
