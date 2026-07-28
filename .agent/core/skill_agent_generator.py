"""Skill & Agent Generator — analiza apps y genera skills/agentes a medida.

Examina un proyecto destino, detecta gaps funcionales y genera
SKILL.md y IDENTITY.md personalizados para cubrir esas necesidades.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class SkillSuggestion:
    """Sugerencia de skill a crear para un proyecto."""

    name: str
    description: str
    category: str
    reason: str
    priority: str  # "high" | "medium" | "low"
    tags: list[str] = field(default_factory=list)
    triggers: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict."""
        return {
            "name": self.name,
            "description": self.description,
            "category": self.category,
            "reason": self.reason,
            "priority": self.priority,
            "tags": self.tags,
            "triggers": self.triggers,
            "tools": self.tools,
        }


@dataclass
class AgentSuggestion:
    """Sugerencia de agente a crear para un proyecto."""

    name: str
    description: str
    tier: str
    role: str
    reason: str
    priority: str
    skills: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict."""
        return {
            "name": self.name,
            "description": self.description,
            "tier": self.tier,
            "role": self.role,
            "reason": self.reason,
            "priority": self.priority,
            "skills": self.skills,
            "tools": self.tools,
        }


@dataclass
class GeneratorReport:
    """Reporte de skills y agentes sugeridos/generados."""

    project_name: str
    project_dir: str
    skill_suggestions: list[SkillSuggestion] = field(default_factory=list)
    agent_suggestions: list[AgentSuggestion] = field(default_factory=list)
    skills_created: list[str] = field(default_factory=list)
    agents_created: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        """Serializa a dict."""
        return {
            "project_name": self.project_name,
            "project_dir": self.project_dir,
            "skill_suggestions": [s.to_dict() for s in self.skill_suggestions],
            "agent_suggestions": [a.to_dict() for a in self.agent_suggestions],
            "skills_created": self.skills_created,
            "agents_created": self.agents_created,
            "summary": {
                "skills_suggested": len(self.skill_suggestions),
                "agents_suggested": len(self.agent_suggestions),
                "skills_created": len(self.skills_created),
                "agents_created": len(self.agents_created),
            },
        }


# ---- Reglas de detección de gaps ----

# Patterns que indican necesidad de una skill específica
GAP_RULES: list[dict[str, Any]] = [
    {
        "detect": {"files": ["*.test.*", "*.spec.*", "jest.config.*", "vitest.config.*"]},
        "missing_check": "test-automation",
        "skill": SkillSuggestion(
            name="{project}-test-suite",
            description="Automatización de tests específica para {project}: genera, ejecuta y reporta tests adaptados al stack del proyecto.",
            category="TESTING",
            reason="Proyecto tiene tests pero no hay skill de automatización personalizada",
            priority="high",
            tags=["testing", "automation", "ci"],
            triggers=["test", "coverage", "spec"],
            tools=["Bash", "Read", "Write", "Grep"],
        ),
    },
    {
        "detect": {"files": ["Dockerfile", "docker-compose.*"]},
        "missing_check": "container-management",
        "skill": SkillSuggestion(
            name="{project}-docker-ops",
            description="Gestión de contenedores Docker para {project}: build, deploy, health checks y optimización de imágenes.",
            category="DEVOPS",
            reason="Proyecto usa Docker pero no hay skill de gestión de contenedores",
            priority="medium",
            tags=["docker", "devops", "containers"],
            triggers=["docker", "container", "build", "deploy"],
            tools=["Bash", "Read", "Edit"],
        ),
    },
    {
        "detect": {"files": [".github/workflows/*"]},
        "missing_check": "ci-pipeline",
        "skill": SkillSuggestion(
            name="{project}-ci-pipeline",
            description="Gestión y optimización del pipeline CI/CD de {project}: workflows, caching, paralelización y debugging de fallos.",
            category="DEVOPS",
            reason="Proyecto tiene CI/CD pero no hay skill especializada",
            priority="medium",
            tags=["ci", "cd", "github-actions", "automation"],
            triggers=["ci", "pipeline", "workflow", "deploy"],
            tools=["Bash", "Read", "Edit", "Grep"],
        ),
    },
    {
        "detect": {"deps": ["prisma", "@prisma/client", "drizzle-orm", "typeorm", "sequelize"]},
        "missing_check": "db-management",
        "skill": SkillSuggestion(
            name="{project}-database",
            description="Gestión de base de datos para {project}: migraciones, queries, índices, seeds y backup.",
            category="DATA_ML",
            reason="Proyecto usa ORM/DB pero no hay skill de gestión de base de datos",
            priority="high",
            tags=["database", "migrations", "queries"],
            triggers=["database", "migration", "query", "schema", "seed"],
            tools=["Bash", "Read", "Write", "Edit"],
        ),
    },
    {
        "detect": {"deps": ["next", "nuxt", "gatsby", "remix", "@remix-run/node"]},
        "missing_check": "seo-optimization",
        "skill": SkillSuggestion(
            name="{project}-seo",
            description="Optimización SEO para {project}: meta tags, sitemap, structured data, Core Web Vitals y análisis de rendimiento.",
            category="FRONTEND_UI",
            reason="Proyecto usa framework SSR/SSG sin skill de SEO",
            priority="medium",
            tags=["seo", "performance", "meta-tags"],
            triggers=["seo", "meta", "sitemap", "lighthouse"],
            tools=["Bash", "Read", "Edit", "Grep"],
        ),
    },
    {
        "detect": {"files": ["*.py"], "deps_file": "pyproject.toml"},
        "missing_check": "api-documentation",
        "skill": SkillSuggestion(
            name="{project}-api-docs",
            description="Generación y mantenimiento de documentación de API para {project}: OpenAPI, docstrings, ejemplos y changelog.",
            category="DOCUMENTATION",
            reason="Proyecto Python sin skill de documentación de API",
            priority="low",
            tags=["documentation", "api", "openapi"],
            triggers=["docs", "api", "openapi", "swagger", "docstring"],
            tools=["Read", "Write", "Grep", "Glob"],
        ),
    },
    {
        "detect": {
            "files": ["*.tsx", "*.jsx"],
            "deps": ["react", "vue", "@angular/core", "svelte"],
        },
        "missing_check": "component-library",
        "skill": SkillSuggestion(
            name="{project}-components",
            description="Gestión de componentes UI para {project}: creación, testing, storybook, accesibilidad y design system.",
            category="FRONTEND_UI",
            reason="Proyecto frontend sin skill de gestión de componentes",
            priority="medium",
            tags=["components", "ui", "accessibility", "design-system"],
            triggers=["component", "ui", "accessibility", "a11y"],
            tools=["Read", "Write", "Edit", "Glob"],
        ),
    },
    {
        "detect": {"files": [".env", ".env.example", ".env.local"]},
        "missing_check": "env-management",
        "skill": SkillSuggestion(
            name="{project}-env-config",
            description="Gestión de configuración y variables de entorno para {project}: validación, documentación, rotación de secrets.",
            category="SECURITY",
            reason="Proyecto usa .env sin skill de gestión de configuración",
            priority="high",
            tags=["config", "env", "secrets", "security"],
            triggers=["env", "config", "secret", "variable"],
            tools=["Read", "Edit", "Grep", "Glob"],
        ),
    },
]

# Agent suggestions based on project complexity
AGENT_RULES: list[dict[str, Any]] = [
    {
        "condition": "large_project",
        "agent": AgentSuggestion(
            name="{project}-architect",
            description="Arquitecto especialista en {project}: conoce la estructura, dependencias y patrones del proyecto a fondo.",
            tier="planning",
            role="Arquitecto de software especializado en {project}",
            reason="Proyecto grande (500+ archivos) necesita un arquitecto dedicado",
            priority="high",
            skills=["code-review", "plan-writing"],
            tools=["Read", "Glob", "Grep", "Bash"],
        ),
    },
    {
        "condition": "has_api",
        "agent": AgentSuggestion(
            name="{project}-api-guardian",
            description="Guardián de la API de {project}: valida contratos, versiones, backward compatibility y documentación.",
            tier="quality",
            role="Guardián de API que asegura consistencia y calidad de endpoints",
            reason="Proyecto expone API que necesita validación continua",
            priority="medium",
            skills=["api-documentation", "testing-automation"],
            tools=["Read", "Grep", "Bash", "Edit"],
        ),
    },
    {
        "condition": "has_auth",
        "agent": AgentSuggestion(
            name="{project}-security-specialist",
            description="Especialista en seguridad para {project}: audita autenticación, autorización, secrets y vulnerabilidades.",
            tier="security",
            role="Especialista en seguridad enfocado en el modelo de auth del proyecto",
            reason="Proyecto tiene autenticación y necesita auditoría continua",
            priority="high",
            skills=["security-audit"],
            tools=["Read", "Grep", "Glob", "Bash"],
        ),
    },
    {
        "condition": "monorepo",
        "agent": AgentSuggestion(
            name="{project}-monorepo-navigator",
            description="Navegador de monorepo para {project}: mapea dependencias entre paquetes, detecta cambios transversales.",
            tier="specialized",
            role="Especialista en monorepos que entiende las interdependencias",
            reason="Monorepo necesita un agente que entienda las relaciones entre paquetes",
            priority="medium",
            skills=["code-review", "dependency-analysis"],
            tools=["Read", "Glob", "Grep", "Bash"],
        ),
    },
]


def _detect_project_name(project_dir: Path) -> str:
    """Detecta el nombre del proyecto desde package.json o pyproject.toml."""
    pkg = project_dir / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            name = data.get("name", "")
            if name:
                return name.replace("@", "").replace("/", "-")
        except (json.JSONDecodeError, OSError):
            pass

    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            for line in content.splitlines():
                if line.strip().startswith("name"):
                    parts = line.split("=", 1)
                    if len(parts) == 2:
                        return parts[1].strip().strip('"').strip("'")
        except OSError:
            pass

    return project_dir.name


def _get_project_deps(project_dir: Path) -> set[str]:
    """Obtiene todas las dependencias del proyecto."""
    deps: set[str] = set()

    pkg = project_dir / "package.json"
    if pkg.exists():
        try:
            data = json.loads(pkg.read_text(encoding="utf-8"))
            deps.update(data.get("dependencies", {}).keys())
            deps.update(data.get("devDependencies", {}).keys())
        except (json.JSONDecodeError, OSError):
            pass

    pyproject = project_dir / "pyproject.toml"
    if pyproject.exists():
        try:
            content = pyproject.read_text(encoding="utf-8")
            in_deps = False
            for line in content.splitlines():
                stripped = line.strip()
                if stripped.startswith("dependencies"):
                    in_deps = True
                    continue
                if in_deps and stripped.startswith("]"):
                    in_deps = False
                if in_deps and stripped.startswith('"'):
                    dep = stripped.strip('",').split(">=")[0].split("==")[0].strip()
                    if dep:
                        deps.add(dep)
        except OSError:
            pass

    return deps


def _get_existing_skills(ecosystem_dir: Path | None = None) -> set[str]:
    """Obtiene nombres de skills existentes en el ecosistema."""
    skills: set[str] = set()
    if ecosystem_dir is None:
        ecosystem_dir = Path(__file__).parent.parent / "skills"
    if ecosystem_dir.is_dir():
        for item in ecosystem_dir.iterdir():
            if item.is_dir() and (item / "SKILL.md").exists():
                skills.add(item.name)
    return skills


def _condition_large_project(project_dir: Path, deps: set[str]) -> bool:
    """Determina si el proyecto tiene 500+ archivos de código.

    Args:
        project_dir: Ruta al proyecto a analizar.
        deps: Dependencias del proyecto (no usado en esta condición).

    Returns:
        True si el proyecto alcanza 500 archivos de código.
    """
    count = 0
    code_ext = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go", ".java"}
    skip = {"node_modules", ".git", "dist", "build", "__pycache__", ".venv"}
    try:
        for f in project_dir.rglob("*"):
            if f.is_file() and f.suffix in code_ext:
                if not any(p in f.parts for p in skip):
                    count += 1
                    if count >= 500:
                        return True
    except PermissionError:
        pass
    return False


def _condition_has_api(project_dir: Path, deps: set[str]) -> bool:
    """Determina si el proyecto usa un framework de API.

    Args:
        project_dir: Ruta al proyecto (no usado en esta condición).
        deps: Dependencias del proyecto.

    Returns:
        True si alguna dependencia es un framework de API conocido.
    """
    api_indicators = {
        "express",
        "fastify",
        "nestjs",
        "@nestjs/core",
        "hono",
        "fastapi",
        "django",
        "flask",
        "starlette",
    }
    return bool(deps & api_indicators)


def _condition_has_auth(project_dir: Path, deps: set[str]) -> bool:
    """Determina si el proyecto implementa autenticación.

    Args:
        project_dir: Ruta al proyecto a analizar.
        deps: Dependencias del proyecto.

    Returns:
        True si hay dependencias o archivos relacionados con auth.
    """
    auth_indicators = {
        "passport",
        "next-auth",
        "@auth/core",
        "jsonwebtoken",
        "bcrypt",
        "argon2",
        "django-allauth",
        "authlib",
        "@supabase/auth-helpers-nextjs",
    }
    if deps & auth_indicators:
        return True
    # Check for auth files
    auth_patterns = ["*auth*", "*login*", "*session*"]
    for pat in auth_patterns:
        if list(project_dir.glob(f"src/**/{pat}.{'{ts,tsx,py,js,jsx}'}")):
            return True
    return False


def _condition_monorepo(project_dir: Path, deps: set[str]) -> bool:
    """Determina si el proyecto es un monorepo.

    Args:
        project_dir: Ruta al proyecto a analizar.
        deps: Dependencias del proyecto (no usado en esta condición).

    Returns:
        True si hay marcadores de monorepo (workspaces, lerna, nx, etc).
    """
    return (
        (project_dir / "pnpm-workspace.yaml").exists()
        or (project_dir / "lerna.json").exists()
        or (project_dir / "nx.json").exists()
        or (project_dir / "turbo.json").exists()
        or (project_dir / "packages").is_dir()
    )


_CONDITION_HANDLERS: dict[str, Callable[[Path, set[str]], bool]] = {
    "large_project": _condition_large_project,
    "has_api": _condition_has_api,
    "has_auth": _condition_has_auth,
    "monorepo": _condition_monorepo,
}


def _check_condition(condition: str, project_dir: Path, deps: set[str]) -> bool:
    """Evalúa una condición de agente sobre el proyecto.

    Args:
        condition: Nombre de la condición a evaluar.
        project_dir: Ruta al proyecto a analizar.
        deps: Dependencias detectadas del proyecto.

    Returns:
        True si la condición se cumple; False si no o si es desconocida.
    """
    handler = _CONDITION_HANDLERS.get(condition)
    if handler is None:
        return False
    return handler(project_dir, deps)


def _detect_rule_matches(detect: dict[str, Any], target: Path, deps: set[str]) -> bool:
    """Evalúa si las señales de detección de una regla de skill coinciden.

    Args:
        detect: Sección ``detect`` de la regla (puede tener ``files``, ``deps``,
            ``deps_file``).
        target: Directorio del proyecto analizado.
        deps: Conjunto de dependencias detectadas en el proyecto.

    Returns:
        ``True`` si alguna de las señales coincide, ``False`` en caso contrario.
    """
    if "files" in detect:
        for pattern in detect["files"]:
            if list(target.glob(f"**/{pattern}")):
                return True

    if "deps" in detect and (deps & set(detect["deps"])):
        return True

    if "deps_file" in detect and (target / detect["deps_file"]).exists():
        return True

    return False


def _build_skill_suggestion(template: SkillSuggestion, project_name: str) -> SkillSuggestion:
    """Crea una SkillSuggestion interpolando el nombre del proyecto en la plantilla.

    Args:
        template: Plantilla de sugerencia de skill.
        project_name: Nombre del proyecto para interpolar en ``{project}``.

    Returns:
        Nueva SkillSuggestion con los placeholders resueltos.
    """
    return SkillSuggestion(
        name=template.name.replace("{project}", project_name),
        description=template.description.replace("{project}", project_name),
        category=template.category,
        reason=template.reason,
        priority=template.priority,
        tags=list(template.tags),
        triggers=list(template.triggers),
        tools=list(template.tools),
    )


def _build_agent_suggestion(template: AgentSuggestion, project_name: str) -> AgentSuggestion:
    """Crea una AgentSuggestion interpolando el nombre del proyecto en la plantilla.

    Args:
        template: Plantilla de sugerencia de agente.
        project_name: Nombre del proyecto para interpolar en ``{project}``.

    Returns:
        Nueva AgentSuggestion con los placeholders resueltos.
    """
    return AgentSuggestion(
        name=template.name.replace("{project}", project_name),
        description=template.description.replace("{project}", project_name),
        tier=template.tier,
        role=template.role.replace("{project}", project_name),
        reason=template.reason,
        priority=template.priority,
        skills=list(template.skills),
        tools=list(template.tools),
    )


def _evaluate_skill_rule(
    rule: dict[str, Any],
    target: Path,
    deps: set[str],
    existing_skills: set[str],
    project_name: str,
) -> SkillSuggestion | None:
    """Evalúa una regla de gap de skill y devuelve la sugerencia si aplica.

    Devuelve ``None`` cuando la regla no coincide con el proyecto o cuando ya
    existe un skill similar en el ecosistema.

    Args:
        rule: Regla de GAP_RULES con claves ``detect``, ``missing_check`` y ``skill``.
        target: Directorio del proyecto analizado.
        deps: Conjunto de dependencias detectadas.
        existing_skills: Nombres de skills ya existentes en el ecosistema.
        project_name: Nombre del proyecto para interpolar en la plantilla.

    Returns:
        La SkillSuggestion generada, o ``None`` si la regla no produce sugerencia.
    """
    if not _detect_rule_matches(rule["detect"], target, deps):
        return None

    missing_key = rule["missing_check"]
    if any(missing_key in skill_name for skill_name in existing_skills):
        return None

    return _build_skill_suggestion(rule["skill"], project_name)


def analyze_project_gaps(
    project_dir: str | Path,
    *,
    ecosystem_dir: str | Path | None = None,
) -> GeneratorReport:
    """Analiza un proyecto y sugiere skills/agentes faltantes.

    Args:
        project_dir: Ruta al proyecto a analizar.
        ecosystem_dir: Ruta al directorio de skills (auto-detecta si None).

    Returns:
        GeneratorReport con sugerencias de skills y agentes.
    """
    target = Path(project_dir)
    if not target.is_dir():
        logger.warning("Directorio no encontrado: %s", project_dir)
        return GeneratorReport(project_name="unknown", project_dir=str(project_dir))

    project_name = _detect_project_name(target)
    report = GeneratorReport(project_name=project_name, project_dir=str(target))

    deps = _get_project_deps(target)
    eco_dir = Path(ecosystem_dir) if ecosystem_dir else None
    existing_skills = _get_existing_skills(eco_dir)

    # Check skill gaps
    for rule in GAP_RULES:
        suggestion = _evaluate_skill_rule(rule, target, deps, existing_skills, project_name)
        if suggestion is not None:
            report.skill_suggestions.append(suggestion)

    # Check agent gaps
    for rule in AGENT_RULES:
        if _check_condition(rule["condition"], target, deps):
            report.agent_suggestions.append(_build_agent_suggestion(rule["agent"], project_name))

    # Sort by priority
    priority_order = {"high": 0, "medium": 1, "low": 2}
    report.skill_suggestions.sort(key=lambda s: priority_order.get(s.priority, 99))
    report.agent_suggestions.sort(key=lambda a: priority_order.get(a.priority, 99))

    logger.info(
        "Análisis de %s: %d skills sugeridos, %d agentes sugeridos",
        project_name,
        len(report.skill_suggestions),
        len(report.agent_suggestions),
    )
    return report


def generate_skill_md(suggestion: SkillSuggestion) -> str:
    """Genera el contenido SKILL.md para una sugerencia de skill.

    Args:
        suggestion: Sugerencia de skill.

    Returns:
        Contenido SKILL.md formateado.
    """
    tags_str = ", ".join(suggestion.tags) if suggestion.tags else ""
    triggers_str = ", ".join(suggestion.triggers) if suggestion.triggers else ""
    tools_str = ", ".join(suggestion.tools) if suggestion.tools else "Read, Grep"

    return f"""---
name: {suggestion.name}
description: {suggestion.description}
tags: [{tags_str}]
triggers: [{triggers_str}]
allowed-tools: {tools_str}
version: "1.0.0"
status: active
category: {suggestion.category}
---

# {suggestion.name}

{suggestion.description}

## Cuándo usar

- {suggestion.reason}
- Cuando el proyecto necesite automatización en el área de {suggestion.category.lower().replace("_", " ")}

## Instrucciones

1. Analizar el estado actual del proyecto en el área relevante
2. Identificar oportunidades de mejora
3. Implementar los cambios necesarios
4. Verificar que los cambios no rompan funcionalidad existente
5. Reportar el resultado con métricas cuando sea posible

## Herramientas

{chr(10).join(f"- **{tool}**: Usado para interactuar con el código" for tool in suggestion.tools)}

## Tags

{chr(10).join(f"- `{tag}`" for tag in suggestion.tags)}
"""


def generate_identity_md(suggestion: AgentSuggestion) -> str:
    """Genera el contenido IDENTITY.md para una sugerencia de agente.

    Args:
        suggestion: Sugerencia de agente.

    Returns:
        Contenido IDENTITY.md formateado.
    """
    tools_str = ", ".join(suggestion.tools) if suggestion.tools else "Read, Grep"

    return f"""---
name: {suggestion.name}
description: {suggestion.description}
tools: {tools_str}
tier: {suggestion.tier}
---

# {suggestion.name}

## Rol

{suggestion.role}

## Descripción

{suggestion.description}

## Capacidades

- Análisis profundo del proyecto y su arquitectura
- Detección proactiva de problemas y oportunidades
- Ejecución autónoma de tareas dentro de su dominio
- Reporte estructurado de hallazgos y acciones

## Skills Asociados

{chr(10).join(f"- `{skill}`" for skill in suggestion.skills)}

## Herramientas

{chr(10).join(f"- **{tool}**" for tool in suggestion.tools)}

## Instrucciones de Ejecución

1. Investigar el estado actual del proyecto en tu área de especialidad
2. Identificar problemas, riesgos u oportunidades de mejora
3. Proponer y ejecutar acciones concretas
4. Verificar los resultados
5. Documentar hallazgos y acciones realizadas
"""


def create_skills(
    report: GeneratorReport,
    output_dir: str | Path,
    *,
    auto_create: bool = False,
) -> list[str]:
    """Crea los archivos SKILL.md para las sugerencias aprobadas.

    Args:
        report: Reporte con sugerencias.
        output_dir: Directorio donde crear los skills.
        auto_create: Si True, crear todos sin preguntar.

    Returns:
        Lista de skills creados.
    """
    out = Path(output_dir)
    created: list[str] = []

    suggestions = (
        report.skill_suggestions
        if auto_create
        else [s for s in report.skill_suggestions if s.priority == "high"]
    )

    for suggestion in suggestions:
        skill_dir = out / suggestion.name
        skill_file = skill_dir / "SKILL.md"

        if skill_file.exists():
            logger.info("Skill %s ya existe, omitiendo", suggestion.name)
            continue

        skill_dir.mkdir(parents=True, exist_ok=True)
        content = generate_skill_md(suggestion)
        skill_file.write_text(content, encoding="utf-8")
        created.append(suggestion.name)
        logger.info("Skill creado: %s", suggestion.name)

    report.skills_created = created
    return created


def create_agents(
    report: GeneratorReport,
    output_dir: str | Path,
    *,
    auto_create: bool = False,
) -> list[str]:
    """Crea los archivos IDENTITY.md para las sugerencias aprobadas.

    Args:
        report: Reporte con sugerencias.
        output_dir: Directorio donde crear los agentes.
        auto_create: Si True, crear todos sin preguntar.

    Returns:
        Lista de agentes creados.
    """
    out = Path(output_dir)
    created: list[str] = []

    suggestions = (
        report.agent_suggestions
        if auto_create
        else [a for a in report.agent_suggestions if a.priority == "high"]
    )

    for suggestion in suggestions:
        agent_dir = out / suggestion.name
        identity_file = agent_dir / "IDENTITY.md"

        if identity_file.exists():
            logger.info("Agente %s ya existe, omitiendo", suggestion.name)
            continue

        agent_dir.mkdir(parents=True, exist_ok=True)
        content = generate_identity_md(suggestion)
        identity_file.write_text(content, encoding="utf-8")
        created.append(suggestion.name)
        logger.info("Agente creado: %s", suggestion.name)

    report.agents_created = created
    return created
