"""Injection Intelligence — adapta la inyección MCP al stack del proyecto destino.

Analiza un directorio de proyecto para detectar su stack tecnológico
y recomendar agentes/skills específicos para inyectar.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

MAX_RECOMMENDED_AGENTS = 6
MAX_RECOMMENDED_SKILLS = 8


@dataclass
class StackProfile:
    """Perfil tecnológico detectado de un proyecto."""

    languages: list[str] = field(default_factory=list)
    frameworks: list[str] = field(default_factory=list)
    databases: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    project_size: str = "small"  # small (<100 files), medium (<500), large (500+)
    has_tests: bool = False
    has_ci: bool = False
    has_docker: bool = False
    recommended_agents: list[str] = field(default_factory=list)
    recommended_skills: list[str] = field(default_factory=list)
    confidence: float = 0.0


# Detection rules: filename/pattern -> what it indicates
STACK_INDICATORS = {
    # Languages
    "package.json": {"languages": ["typescript", "javascript"]},
    "tsconfig.json": {"languages": ["typescript"]},
    "pyproject.toml": {"languages": ["python"]},
    "setup.py": {"languages": ["python"]},
    "Cargo.toml": {"languages": ["rust"]},
    "go.mod": {"languages": ["go"]},
    "pom.xml": {"languages": ["java"]},
    "build.gradle": {"languages": ["java", "kotlin"]},
    "Gemfile": {"languages": ["ruby"]},
    "composer.json": {"languages": ["php"]},
    "*.swift": {"languages": ["swift"]},
    "*.cs": {"languages": ["csharp"]},
    # Frameworks
    "next.config.js": {"frameworks": ["nextjs"]},
    "next.config.ts": {"frameworks": ["nextjs"]},
    "next.config.mjs": {"frameworks": ["nextjs"]},
    "nuxt.config.ts": {"frameworks": ["nuxt"]},
    "angular.json": {"frameworks": ["angular"]},
    "svelte.config.js": {"frameworks": ["svelte"]},
    "astro.config.mjs": {"frameworks": ["astro"]},
    "vite.config.ts": {"frameworks": ["vite"]},
    "vite.config.js": {"frameworks": ["vite"]},
    "tailwind.config.js": {"tools": ["tailwind"]},
    "tailwind.config.ts": {"tools": ["tailwind"]},
    "postcss.config.js": {"tools": ["postcss"]},
    # Python frameworks
    "manage.py": {"frameworks": ["django"]},
    "app.py": {"frameworks": ["flask"]},  # heuristic
    # Databases
    "prisma/": {"databases": ["prisma"]},
    "drizzle.config.ts": {"databases": ["drizzle"]},
    "alembic.ini": {"databases": ["sqlalchemy"]},
    "migrations/": {"databases": ["migrations"]},
    # Infrastructure
    "Dockerfile": {"tools": ["docker"]},
    "docker-compose.yml": {"tools": ["docker"]},
    "docker-compose.yaml": {"tools": ["docker"]},
    ".github/workflows/": {"tools": ["github-actions"]},
    ".gitlab-ci.yml": {"tools": ["gitlab-ci"]},
    "Jenkinsfile": {"tools": ["jenkins"]},
    "terraform/": {"tools": ["terraform"]},
    "k8s/": {"tools": ["kubernetes"]},
    "kubernetes/": {"tools": ["kubernetes"]},
}

# Agent recommendations by detected stack
AGENT_RECOMMENDATIONS = {
    "typescript": ["frontend-specialist", "test-engineer"],
    "javascript": ["frontend-specialist"],
    "python": ["backend-specialist", "test-engineer"],
    "rust": ["performance-optimizer"],
    "go": ["backend-specialist"],
    "java": ["backend-specialist", "test-engineer"],
    "nextjs": ["frontend-specialist", "seo-expert"],
    "nuxt": ["frontend-specialist", "seo-expert"],
    "angular": ["frontend-specialist"],
    "svelte": ["frontend-specialist"],
    "django": ["backend-specialist", "database-architect"],
    "flask": ["backend-specialist"],
    "docker": ["devops-engineer"],
    "kubernetes": ["devops-engineer"],
    "github-actions": ["devops-engineer"],
    "terraform": ["devops-engineer"],
    "prisma": ["database-architect"],
    "sqlalchemy": ["database-architect"],
    "drizzle": ["database-architect"],
}

# Skill recommendations by detected stack
SKILL_RECOMMENDATIONS = {
    "typescript": ["code-review", "testing-automation", "linting"],
    "python": ["code-review", "testing-automation", "type-checking"],
    "rust": ["performance-profiling", "memory-safety"],
    "nextjs": ["seo-audit", "performance-audit", "accessibility"],
    "docker": ["container-security", "dockerfile-optimization"],
    "github-actions": ["ci-cd-optimization", "workflow-security"],
    "prisma": ["schema-review", "migration-safety"],
    "sqlalchemy": ["query-optimization", "migration-safety"],
}


def detect_stack(target_dir: str | Path) -> StackProfile:
    """Detecta el stack tecnológico de un proyecto.

    Args:
        target_dir: Ruta al directorio del proyecto.

    Returns:
        StackProfile con lenguajes, frameworks, herramientas y recomendaciones.
    """
    target = Path(target_dir)
    if not target.is_dir():
        logger.warning("Directorio no encontrado: %s", target_dir)
        return StackProfile()

    profile = StackProfile()
    detected_items: set[str] = set()

    # Check file-based indicators
    _scan_file_indicators(target, profile, detected_items)

    # Deep detection from package.json
    pkg_json = target / "package.json"
    if pkg_json.exists():
        _detect_from_package_json(pkg_json, profile, detected_items)

    # Deep detection from pyproject.toml
    pyproject = target / "pyproject.toml"
    if pyproject.exists():
        _detect_from_pyproject(pyproject, profile, detected_items)

    # Project size estimation
    profile.project_size = _estimate_size(target)

    # Test detection
    profile.has_tests = any(
        [
            (target / "tests").is_dir(),
            (target / "test").is_dir(),
            (target / "__tests__").is_dir(),
            (target / "spec").is_dir(),
            any(target.glob("*.test.*")),
            any(target.glob("*.spec.*")),
            (target / "jest.config.js").exists(),
            (target / "jest.config.ts").exists(),
            (target / "vitest.config.ts").exists(),
            (target / "pytest.ini").exists(),
            (target / "conftest.py").exists(),
        ]
    )

    # CI detection
    profile.has_ci = any(
        [
            (target / ".github" / "workflows").is_dir(),
            (target / ".gitlab-ci.yml").exists(),
            (target / "Jenkinsfile").exists(),
            (target / ".circleci").is_dir(),
        ]
    )

    # Docker detection
    profile.has_docker = (target / "Dockerfile").exists() or (
        target / "docker-compose.yml"
    ).exists()

    # Generate recommendations
    _generate_recommendations(profile, detected_items)

    # Always recommend these universal agents
    _apply_universal_agents(profile)

    # Confidence based on number of detected items
    profile.confidence = min(1.0, len(detected_items) / 5.0)

    # Deduplicate
    _dedup_profile_lists(profile)

    logger.info(
        "Stack detectado en %s: %d lenguajes, %d frameworks, confianza=%.0f%%",
        target_dir,
        len(profile.languages),
        len(profile.frameworks),
        profile.confidence * 100,
    )
    return profile


def _scan_file_indicators(target: Path, profile: StackProfile, detected_items: set[str]) -> None:
    """Escanea indicadores de stack basados en archivos, directorios y globs.

    Recorre ``STACK_INDICATORS`` y, según el tipo de indicador (directorio que
    termina en ``/``, patrón glob con ``*`` o archivo literal), verifica su
    presencia en el proyecto. Cuando coincide, fusiona los atributos al perfil.

    Args:
        target: Ruta raíz del proyecto a analizar.
        profile: Perfil de stack a actualizar in-place.
        detected_items: Conjunto de items detectados a actualizar in-place.
    """
    for indicator, attrs in STACK_INDICATORS.items():
        if indicator.endswith("/"):
            # Directory check
            matched = (target / indicator.rstrip("/")).is_dir()
        elif "*" in indicator:
            # Glob pattern
            ext = indicator.replace("*", "")
            matched = any(target.rglob(f"*{ext}"))
        else:
            matched = (target / indicator).exists()

        if matched:
            _merge_attrs(profile, attrs)
            detected_items.update(_flat_values(attrs))


def _apply_universal_agents(profile: StackProfile) -> None:
    """Agrega agentes universales recomendados según el perfil detectado.

    Siempre recomienda ``documentation-specialist`` y ``security-auditor``, suma
    ``code-archaeologist`` para proyectos grandes y ``test-engineer`` si hay
    tests, evitando duplicados.

    Args:
        profile: Perfil de stack a actualizar in-place.
    """
    universal = ["documentation-specialist", "security-auditor"]
    if profile.project_size == "large":
        universal.append("code-archaeologist")
    if profile.has_tests and "test-engineer" not in profile.recommended_agents:
        profile.recommended_agents.append("test-engineer")

    for agent in universal:
        if agent not in profile.recommended_agents:
            profile.recommended_agents.append(agent)


def _dedup_profile_lists(profile: StackProfile) -> None:
    """Deduplica las listas del perfil preservando el orden de inserción.

    Args:
        profile: Perfil de stack a actualizar in-place.
    """
    profile.languages = list(dict.fromkeys(profile.languages))
    profile.frameworks = list(dict.fromkeys(profile.frameworks))
    profile.databases = list(dict.fromkeys(profile.databases))
    profile.tools = list(dict.fromkeys(profile.tools))
    profile.recommended_agents = list(dict.fromkeys(profile.recommended_agents))
    profile.recommended_skills = list(dict.fromkeys(profile.recommended_skills))


def _merge_attrs(profile: StackProfile, attrs: dict[str, list[str]]) -> None:
    """Fusiona atributos detectados al perfil."""
    for key, values in attrs.items():
        existing = getattr(profile, key, [])
        for v in values:
            if v not in existing:
                existing.append(v)
        setattr(profile, key, existing)


def _flat_values(attrs: dict[str, list[str]]) -> list[str]:
    """Extrae todos los valores planos de un dict de atributos."""
    result: list[str] = []
    for values in attrs.values():
        result.extend(values)
    return result


def _detect_from_package_json(pkg_path: Path, profile: StackProfile, detected: set[str]) -> None:
    """Detecta frameworks y herramientas desde package.json."""
    try:
        data = json.loads(pkg_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return

    all_deps: dict[str, str] = {}
    all_deps.update(data.get("dependencies", {}))
    all_deps.update(data.get("devDependencies", {}))

    dep_framework_map = {
        "react": {"frameworks": ["react"]},
        "next": {"frameworks": ["nextjs"]},
        "vue": {"frameworks": ["vue"]},
        "nuxt": {"frameworks": ["nuxt"]},
        "@angular/core": {"frameworks": ["angular"]},
        "svelte": {"frameworks": ["svelte"]},
        "express": {"frameworks": ["express"]},
        "fastify": {"frameworks": ["fastify"]},
        "nestjs": {"frameworks": ["nestjs"]},
        "@nestjs/core": {"frameworks": ["nestjs"]},
        "hono": {"frameworks": ["hono"]},
        "astro": {"frameworks": ["astro"]},
        "remix": {"frameworks": ["remix"]},
        "@remix-run/node": {"frameworks": ["remix"]},
        "gatsby": {"frameworks": ["gatsby"]},
        "electron": {"frameworks": ["electron"]},
        "@tauri-apps/api": {"frameworks": ["tauri"]},
        "prisma": {"databases": ["prisma"]},
        "@prisma/client": {"databases": ["prisma"]},
        "drizzle-orm": {"databases": ["drizzle"]},
        "mongoose": {"databases": ["mongodb"]},
        "typeorm": {"databases": ["typeorm"]},
        "sequelize": {"databases": ["sequelize"]},
        "tailwindcss": {"tools": ["tailwind"]},
        "jest": {"tools": ["jest"]},
        "vitest": {"tools": ["vitest"]},
        "playwright": {"tools": ["playwright"]},
        "cypress": {"tools": ["cypress"]},
    }

    for dep, attrs in dep_framework_map.items():
        if dep in all_deps:
            _merge_attrs(profile, attrs)
            detected.update(_flat_values(attrs))


def _detect_from_pyproject(pyproject_path: Path, profile: StackProfile, detected: set[str]) -> None:
    """Detecta frameworks y herramientas desde pyproject.toml."""
    try:
        content = pyproject_path.read_text(encoding="utf-8")
    except OSError:
        return

    dep_map = {
        "fastapi": {"frameworks": ["fastapi"]},
        "django": {"frameworks": ["django"]},
        "flask": {"frameworks": ["flask"]},
        "starlette": {"frameworks": ["starlette"]},
        "sqlalchemy": {"databases": ["sqlalchemy"]},
        "tortoise-orm": {"databases": ["tortoise"]},
        "motor": {"databases": ["mongodb"]},
        "pymongo": {"databases": ["mongodb"]},
        "redis": {"databases": ["redis"]},
        "celery": {"tools": ["celery"]},
        "pytest": {"tools": ["pytest"]},
        "ruff": {"tools": ["ruff"]},
        "mypy": {"tools": ["mypy"]},
        "pydantic": {"tools": ["pydantic"]},
    }

    content_lower = content.lower()
    for dep, attrs in dep_map.items():
        if dep in content_lower:
            _merge_attrs(profile, attrs)
            detected.update(_flat_values(attrs))


def _estimate_size(target: Path) -> str:
    """Estima el tamaño del proyecto por número de archivos de código."""
    count = 0
    code_extensions = {
        ".py",
        ".ts",
        ".tsx",
        ".js",
        ".jsx",
        ".rs",
        ".go",
        ".java",
        ".kt",
        ".rb",
        ".php",
        ".swift",
        ".cs",
    }
    try:
        for item in target.rglob("*"):
            if item.is_file() and item.suffix in code_extensions:
                # Skip node_modules, .git, etc.
                parts = item.parts
                if any(
                    p in parts
                    for p in (
                        "node_modules",
                        ".git",
                        "dist",
                        "build",
                        "__pycache__",
                        ".venv",
                        "venv",
                    )
                ):
                    continue
                count += 1
                if count >= 500:
                    return "large"
    except PermissionError:
        pass

    if count < 100:
        return "small"
    return "medium"


def _generate_recommendations(profile: StackProfile, detected_items: set[str]) -> None:
    """Genera recomendaciones de agentes y skills según stack detectado."""
    for item in detected_items:
        # Agents
        agents = AGENT_RECOMMENDATIONS.get(item, [])
        for a in agents:
            if a not in profile.recommended_agents:
                profile.recommended_agents.append(a)

        # Skills
        skills = SKILL_RECOMMENDATIONS.get(item, [])
        for s in skills:
            if s not in profile.recommended_skills:
                profile.recommended_skills.append(s)


def get_injection_config(target_dir: str | Path) -> dict:
    """Genera configuración de inyección adaptada al proyecto.

    Args:
        target_dir: Ruta al proyecto destino.

    Returns:
        Dict con el perfil y configuración recomendada para mcp_injector.
    """
    profile = detect_stack(target_dir)

    return {
        "stack_profile": {
            "languages": profile.languages,
            "frameworks": profile.frameworks,
            "databases": profile.databases,
            "tools": profile.tools,
            "project_size": profile.project_size,
            "has_tests": profile.has_tests,
            "has_ci": profile.has_ci,
            "has_docker": profile.has_docker,
        },
        "recommendations": {
            "agents": profile.recommended_agents[:MAX_RECOMMENDED_AGENTS],
            "skills": profile.recommended_skills[:MAX_RECOMMENDED_SKILLS],
        },
        "injection_flags": {
            "dev_preset": True,
            "sync_skills": profile.project_size == "large" or profile.has_tests or profile.has_ci,
            "include_testing_agents": profile.has_tests,
            "include_devops_agents": profile.has_ci or profile.has_docker,
        },
        "confidence": profile.confidence,
    }
