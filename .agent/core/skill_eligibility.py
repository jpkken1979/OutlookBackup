#!/usr/bin/env python3
"""Skill Eligibility — Validación de requisitos de skills.

Inspirado en el patrón de OpenClaw que filtra skills por:
- Binarios disponibles en el sistema (requires.bins)
- Variables de entorno presentes (requires.env)
- Módulos Python instalados (requires.python_modules)
- Versión mínima de Python (requires.python_version)
- Dependencias de otros skills (requires.skills)

Cada SKILL.md puede declarar requisitos en su frontmatter YAML:

```yaml
---
name: mi-skill
description: Descripción del skill
requires:
  bins:
    - docker
    - kubectl
  env:
    - OPENAI_API_KEY
    - AWS_ACCESS_KEY_ID
  python_modules:
    - chromadb
    - anthropic
  python_version: "3.11"
  skills:
    - base-skill
---
```

Features:
- Validación declarativa de requisitos en frontmatter YAML
- Verificación lazy de binarios, env vars, módulos y versión Python
- Caché de resultados para evitar re-verificación costosa
- Reporte detallado de elegibilidad con razones de fallo
- Schema Pydantic para validación estricta del frontmatter

v1.0.0 - 2026-02-27 — Inspirado en OpenClaw skill eligibility
"""

from __future__ import annotations

import importlib
import logging
import os
import platform
import re
import shutil
import sys
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, Field

logger = logging.getLogger("antigravity.skill_eligibility")


# =============================================================================
# SCHEMA — Modelo Pydantic para frontmatter de SKILL.md
# =============================================================================


class SkillRequirements(BaseModel):
    """Requisitos declarativos de un skill.

    Args:
        bins: Binarios que deben estar en PATH.
        env: Variables de entorno requeridas.
        python_modules: Módulos Python que deben estar instalados.
        python_version: Versión mínima de Python (ej: '3.11').
        skills: Nombres de otros skills requeridos.
        platform: Plataformas soportadas (ej: ['linux', 'darwin', 'win32']).
    """

    bins: list[str] = Field(default_factory=list)
    env: list[str] = Field(default_factory=list)
    python_modules: list[str] = Field(default_factory=list)
    python_version: str | None = None
    skills: list[str] = Field(default_factory=list)
    platform: list[str] = Field(default_factory=list)


class SkillFrontmatter(BaseModel):
    """Frontmatter YAML validado de un SKILL.md.

    Args:
        name: Nombre único del skill.
        description: Descripción breve del skill.
        requires: Requisitos de elegibilidad.
        tags: Etiquetas opcionales para categorización.
        version: Versión del skill.
        tier: Tier mínimo de agente que puede usar este skill.
        allowed_tools: Herramientas MCP que utiliza el skill.
    """

    name: str
    description: str = ""
    requires: SkillRequirements = Field(default_factory=SkillRequirements)
    tags: list[str] = Field(default_factory=list)
    version: str = "1.0.0"
    tier: int | None = None
    allowed_tools: list[str] = Field(default_factory=list)


# =============================================================================
# DATA MODELS  — Resultados de elegibilidad
# =============================================================================


@dataclass
class EligibilityFailure:
    """Razón por la que un skill no es elegible."""

    category: str  # "bin", "env", "python_module", "python_version", "skill", "platform"
    requirement: str  # Lo que se requiere
    message: str  # Mensaje legible


@dataclass
class EligibilityResult:
    """Resultado de verificación de elegibilidad de un skill."""

    skill_name: str
    eligible: bool
    failures: list[EligibilityFailure] = field(default_factory=list)
    requirements: SkillRequirements | None = None

    def to_dict(self) -> dict[str, Any]:
        """Serializa a diccionario."""
        return {
            "skill_name": self.skill_name,
            "eligible": self.eligible,
            "failures": [
                {"category": f.category, "requirement": f.requirement, "message": f.message}
                for f in self.failures
            ],
        }


# =============================================================================
# FRONTMATTER PARSER
# =============================================================================

_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---", re.DOTALL)


def parse_skill_frontmatter(skill_path: Path) -> SkillFrontmatter | None:
    """Parsea y valida el frontmatter YAML de un SKILL.md.

    Args:
        skill_path: Ruta al directorio del skill (que contiene SKILL.md).

    Returns:
        SkillFrontmatter validado o None si no se puede parsear.
    """
    skill_md = skill_path / "SKILL.md"
    if not skill_md.exists():
        return None

    try:
        content = skill_md.read_text(encoding="utf-8")
        match = _FRONTMATTER_RE.match(content)
        if not match:
            # Sin frontmatter — crear modelo mínimo desde el nombre del directorio
            return SkillFrontmatter(name=skill_path.name)

        raw = yaml.safe_load(match.group(1))
        if not isinstance(raw, dict):
            return SkillFrontmatter(name=skill_path.name)

        # Asegurar que 'name' existe
        if "name" not in raw:
            raw["name"] = skill_path.name

        return SkillFrontmatter.model_validate(raw)

    except Exception as e:
        logger.debug("Error parsing frontmatter for %s: %s", skill_path.name, e)
        return SkillFrontmatter(name=skill_path.name)


# =============================================================================
# ELIGIBILITY CHECKER — Verificador de requisitos
# =============================================================================


class SkillEligibilityChecker:
    """Verifica si los skills cumplen sus requisitos declarados.

    Cachea resultados de binarios y módulos para eficiencia.
    Acepta un set de skills disponibles para verificar dependencias.

    Args:
        available_skills: Nombres de skills disponibles en el ecosistema.
    """

    def __init__(self, available_skills: set[str] | None = None) -> None:
        self._available_skills: set[str] = available_skills or set()
        self._bin_cache: dict[str, bool] = {}
        self._module_cache: dict[str, bool] = {}

    def _check_bins(self, reqs: SkillRequirements) -> list[EligibilityFailure]:
        """Verifica que los binarios requeridos estén en PATH.

        Args:
            reqs: Requisitos declarados del skill.

        Returns:
            Lista de fallos por binarios ausentes.
        """
        return [
            EligibilityFailure(
                category="bin",
                requirement=bin_name,
                message=f"Binary '{bin_name}' not found in PATH",
            )
            for bin_name in reqs.bins
            if not self._check_bin(bin_name)
        ]

    def _check_envs(self, reqs: SkillRequirements) -> list[EligibilityFailure]:
        """Verifica que las variables de entorno requeridas estén seteadas.

        Args:
            reqs: Requisitos declarados del skill.

        Returns:
            Lista de fallos por variables de entorno ausentes.
        """
        return [
            EligibilityFailure(
                category="env",
                requirement=env_var,
                message=f"Environment variable '{env_var}' not set",
            )
            for env_var in reqs.env
            if not os.environ.get(env_var)
        ]

    def _check_modules(self, reqs: SkillRequirements) -> list[EligibilityFailure]:
        """Verifica que los módulos Python requeridos estén instalados.

        Args:
            reqs: Requisitos declarados del skill.

        Returns:
            Lista de fallos por módulos Python ausentes.
        """
        return [
            EligibilityFailure(
                category="python_module",
                requirement=module_name,
                message=f"Python module '{module_name}' not installed",
            )
            for module_name in reqs.python_modules
            if not self._check_module(module_name)
        ]

    def _check_python_version_req(self, reqs: SkillRequirements) -> list[EligibilityFailure]:
        """Verifica que la versión de Python cumpla el requisito.

        Args:
            reqs: Requisitos declarados del skill.

        Returns:
            Lista con un fallo si la versión es insuficiente; vacía si no.
        """
        if reqs.python_version and not self._check_python_version(reqs.python_version):
            current = f"{sys.version_info.major}.{sys.version_info.minor}"
            return [
                EligibilityFailure(
                    category="python_version",
                    requirement=reqs.python_version,
                    message=f"Requires Python >= {reqs.python_version}, current: {current}",
                )
            ]
        return []

    def _check_skill_deps(self, reqs: SkillRequirements) -> list[EligibilityFailure]:
        """Verifica que los skills dependientes estén disponibles.

        Args:
            reqs: Requisitos declarados del skill.

        Returns:
            Lista de fallos por skills dependientes ausentes.
        """
        return [
            EligibilityFailure(
                category="skill",
                requirement=skill_dep,
                message=f"Required skill '{skill_dep}' not available",
            )
            for skill_dep in reqs.skills
            if skill_dep not in self._available_skills
        ]

    def _check_platform_req(self, reqs: SkillRequirements) -> list[EligibilityFailure]:
        """Verifica que la plataforma actual esté soportada.

        Args:
            reqs: Requisitos declarados del skill.

        Returns:
            Lista con un fallo si la plataforma no es soportada; vacía si no.
        """
        if reqs.platform:
            current_platform = self._get_platform()
            if current_platform not in reqs.platform:
                return [
                    EligibilityFailure(
                        category="platform",
                        requirement=", ".join(reqs.platform),
                        message=f"Platform '{current_platform}' not in supported: {reqs.platform}",
                    )
                ]
        return []

    def check(self, frontmatter: SkillFrontmatter) -> EligibilityResult:
        """Verifica elegibilidad completa de un skill.

        Args:
            frontmatter: Frontmatter validado del skill.

        Returns:
            EligibilityResult con status y razones de fallo.
        """
        reqs = frontmatter.requires
        failures: list[EligibilityFailure] = []
        failures.extend(self._check_bins(reqs))
        failures.extend(self._check_envs(reqs))
        failures.extend(self._check_modules(reqs))
        failures.extend(self._check_python_version_req(reqs))
        failures.extend(self._check_skill_deps(reqs))
        failures.extend(self._check_platform_req(reqs))

        return EligibilityResult(
            skill_name=frontmatter.name,
            eligible=len(failures) == 0,
            failures=failures,
            requirements=reqs,
        )

    def check_all(self, skills_dir: Path, report: bool = False) -> dict[str, EligibilityResult]:
        """Verifica elegibilidad de todos los skills en un directorio.

        Args:
            skills_dir: Directorio raíz de skills.
            report: Si True, imprime reporte a stdout.

        Returns:
            Mapa de nombre_skill -> EligibilityResult.
        """
        results: dict[str, EligibilityResult] = {}

        if not skills_dir.is_dir():
            logger.warning("Skills directory not found: %s", skills_dir)
            return results

        # Primera pasada: recolectar nombres de skills disponibles
        self._available_skills = {
            d.name for d in skills_dir.iterdir() if d.is_dir() and (d / "SKILL.md").exists()
        }

        # Segunda pasada: verificar elegibilidad
        for skill_dir in sorted(skills_dir.iterdir()):
            if not skill_dir.is_dir():
                continue

            frontmatter = parse_skill_frontmatter(skill_dir)
            if frontmatter is None:
                continue

            result = self.check(frontmatter)
            results[frontmatter.name] = result

        if report:
            self._print_report(results)

        return results

    def _check_bin(self, bin_name: str) -> bool:
        """Verifica si un binario está disponible en PATH (con caché)."""
        if bin_name not in self._bin_cache:
            self._bin_cache[bin_name] = shutil.which(bin_name) is not None
        return self._bin_cache[bin_name]

    def _check_module(self, module_name: str) -> bool:
        """Verifica si un módulo Python está instalado (con caché)."""
        if module_name not in self._module_cache:
            try:
                importlib.import_module(module_name)
                self._module_cache[module_name] = True
            except ImportError:
                self._module_cache[module_name] = False
        return self._module_cache[module_name]

    @staticmethod
    def _check_python_version(required: str) -> bool:
        """Verifica versión mínima de Python."""
        try:
            parts = [int(p) for p in required.split(".")]
            current = (sys.version_info.major, sys.version_info.minor)
            required_tuple = tuple(parts[:2])
            return current >= required_tuple
        except (ValueError, IndexError):
            return True  # No se puede parsear, asumir OK

    @staticmethod
    @lru_cache(maxsize=1)
    def _get_platform() -> str:
        """Retorna plataforma actual normalizada."""
        system = platform.system().lower()
        mapping = {"windows": "win32", "darwin": "darwin", "linux": "linux"}
        return mapping.get(system, system)

    @staticmethod
    def _print_report(results: dict[str, EligibilityResult]) -> None:
        """Imprime reporte de elegibilidad a stdout."""
        eligible = sum(1 for r in results.values() if r.eligible)
        total = len(results)

        print(f"\n{'=' * 60}")
        print(f"Skill Eligibility Report — {eligible}/{total} eligible")
        print(f"{'=' * 60}\n")

        # Skills con fallos
        failed = {k: v for k, v in results.items() if not v.eligible}
        if failed:
            print(f"❌ {len(failed)} skills with unmet requirements:\n")
            for name, result in sorted(failed.items()):
                print(f"  {name}:")
                for failure in result.failures:
                    print(f"    [{failure.category}] {failure.message}")
            print()

        print(f"✅ {eligible} skills fully eligible")
        print(f"{'=' * 60}\n")


# =============================================================================
# CLI ENTRY POINT
# =============================================================================


def main() -> None:
    """Entry point para ejecución directa."""
    import argparse

    parser = argparse.ArgumentParser(description="Verificar elegibilidad de skills")
    parser.add_argument(
        "--skills-dir",
        type=str,
        default=None,
        help="Directorio de skills (default: .agent/skills)",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output en formato JSON",
    )
    parser.add_argument(
        "--skill",
        type=str,
        default=None,
        help="Verificar un solo skill por nombre",
    )
    args = parser.parse_args()

    project_root = Path(__file__).parent.parent.parent
    skills_dir = Path(args.skills_dir) if args.skills_dir else project_root / ".agent" / "skills"

    checker = SkillEligibilityChecker()

    if args.skill:
        skill_path = skills_dir / args.skill
        frontmatter = parse_skill_frontmatter(skill_path)
        if frontmatter is None:
            print(f"Skill '{args.skill}' not found or has no SKILL.md")
            sys.exit(1)
        result = checker.check(frontmatter)
        if args.json:
            import json

            print(json.dumps(result.to_dict(), indent=2))
        else:
            status = "✅ ELIGIBLE" if result.eligible else "❌ NOT ELIGIBLE"
            print(f"{args.skill}: {status}")
            for f in result.failures:
                print(f"  [{f.category}] {f.message}")
    else:
        results = checker.check_all(skills_dir, report=not args.json)
        if args.json:
            import json

            output = {k: v.to_dict() for k, v in results.items()}
            print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
