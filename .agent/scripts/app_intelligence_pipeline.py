#!/usr/bin/env python3
"""
App Intelligence Pipeline — Orquestador de análisis de apps.

Etapas:
1. ANALIZAR — quick (30s) o deep (App Auditor completo)
2. ENTENDER — APP_KNOWLEDGE.md + perfil en mem0
3. GENERAR — Skills y agentes personalizados
4. EXTRAER — Patrones reutilizables como skills
"""

import json
import logging
import re
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

PROFILES_DIR = Path.home() / ".antigravity" / "profiles"
PROFILES_DIR.mkdir(parents=True, exist_ok=True)


@dataclass
class StackInfo:
    """Stack técnico detectado."""

    language: str = "unknown"
    framework: str = ""
    db: str = ""
    orm: str = ""
    testing: list[str] = field(default_factory=list)
    styling: str = ""
    state: str = ""
    auth: str = ""
    payments: str = ""
    ci: str = ""
    containerization: str = ""
    extra: dict[str, str] = field(default_factory=dict)


@dataclass
class DetectedPattern:
    """Patrón de código detectado."""

    name: str
    category: str  # middleware, data, api, resilience, test
    file: str
    description: str = ""
    reusable: bool = True


@dataclass
class AppProfile:
    """Perfil completo de una app analizada."""

    name: str
    path: str
    version: int = 1
    analyzed_at: str = ""
    analysis_mode: str = "quick"  # quick | deep
    stack: dict[str, Any] = field(default_factory=dict)
    architecture: str = ""
    business_domain: str = ""
    critical_flows: list[str] = field(default_factory=list)
    detected_patterns: list[dict[str, Any]] = field(default_factory=list)
    generated_agents: list[str] = field(default_factory=list)
    generated_skills: list[str] = field(default_factory=list)
    previous_versions: list[dict[str, Any]] = field(default_factory=list)


def quick_analyze(target_dir: Path) -> AppProfile:
    """Análisis rápido de stack (~30s). Para uso en inyección MCP.

    Args:
        target_dir: Ruta raíz del proyecto a analizar.

    Returns:
        Perfil básico con stack detectado.
    """
    target = Path(target_dir)
    profile = AppProfile(
        name=target.name,
        path=str(target),
        analyzed_at=datetime.now(UTC).isoformat(),
        analysis_mode="quick",
    )

    stack = _detect_stack(target)
    profile.stack = asdict(stack)
    profile.architecture = _infer_architecture(target, stack)
    profile.business_domain = _infer_domain(target)
    profile.detected_patterns = [asdict(p) for p in _quick_pattern_scan(target)]

    return profile


def _run_app_auditor(target_dir: Path) -> dict[str, Any]:
    """Ejecuta app-auditor para análisis deep sin romper el flujo principal.

    Args:
        target_dir: Ruta de proyecto a auditar.

    Returns:
        Resultado con estado, comando y salida sanitizada.
    """
    audit_script = (
        Path(__file__).resolve().parents[1] / "agents" / "app-auditor" / "scripts" / "audit.py"
    )
    command = [sys.executable, str(audit_script), str(target_dir)]

    if not audit_script.is_file():
        return {
            "status": "skipped",
            "reason": f"app-auditor no encontrado en {audit_script}",
            "command": command,
        }

    try:
        completed = subprocess.run(
            command,
            shell=False,
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return {
            "status": "timeout",
            "command": command,
            "reason": "app-auditor supero timeout de 180s",
        }
    except OSError as exc:
        return {
            "status": "error",
            "command": command,
            "reason": f"fallo ejecutando app-auditor: {exc}",
        }

    output = (completed.stdout or completed.stderr or "").strip()
    return {
        "status": "ok" if completed.returncode == 0 else "error",
        "returncode": completed.returncode,
        "command": command,
        "output": output[:1200],
    }


def _detect_stack(target: Path) -> StackInfo:
    """Detecta stack técnico del proyecto."""
    info = StackInfo()

    # --- JavaScript/TypeScript ---
    pkg_path = target / "package.json"
    if pkg_path.exists():
        try:
            pkg = json.loads(pkg_path.read_text(encoding="utf-8"))
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        except Exception:
            deps = {}

        info.language = "typescript" if (target / "tsconfig.json").exists() else "javascript"

        # Frameworks
        fw_map = {
            "next": "next.js",
            "nuxt": "nuxt",
            "react": "react",
            "vue": "vue",
            "svelte": "svelte",
            "angular": "@angular/core",
            "express": "express",
            "fastify": "fastify",
            "hono": "hono",
            "astro": "astro",
        }
        for name, dep_key in fw_map.items():
            if dep_key in deps:
                ver = deps.get(dep_key, "")
                info.framework = f"{name}" + (f"-{ver.lstrip('^~')}" if ver else "")
                break

        # ORM
        orm_map = {
            "prisma": "@prisma/client",
            "drizzle": "drizzle-orm",
            "typeorm": "typeorm",
            "sequelize": "sequelize",
        }
        for name, dep_key in orm_map.items():
            if dep_key in deps:
                info.orm = name
                break

        # Testing
        test_map = {
            "vitest": "vitest",
            "jest": "jest",
            "playwright": "@playwright/test",
            "cypress": "cypress",
        }
        info.testing = [name for name, dep_key in test_map.items() if dep_key in deps]

        # Styling
        style_map = {
            "tailwind": "tailwindcss",
            "styled-components": "styled-components",
            "emotion": "@emotion/react",
        }
        for name, dep_key in style_map.items():
            if dep_key in deps:
                info.styling = name
                break

        # State
        state_map = {
            "zustand": "zustand",
            "redux": "@reduxjs/toolkit",
            "jotai": "jotai",
            "mobx": "mobx",
        }
        for name, dep_key in state_map.items():
            if dep_key in deps:
                info.state = name
                break

        # Auth
        auth_map = {
            "next-auth": "next-auth",
            "clerk": "@clerk/nextjs",
            "supabase-auth": "@supabase/supabase-js",
            "firebase-auth": "firebase",
        }
        for name, dep_key in auth_map.items():
            if dep_key in deps:
                info.auth = name
                break

        # Payments
        if "stripe" in deps:
            info.payments = "stripe"

    # --- Python ---
    pyproject = target / "pyproject.toml"
    requirements = target / "requirements.txt"
    if pyproject.exists() or requirements.exists():
        if info.language == "unknown":
            info.language = "python"
        elif info.language != "python":
            info.language = "mixed"

        try:
            content = pyproject.read_text(encoding="utf-8") if pyproject.exists() else ""
        except Exception:
            content = ""

        py_fw = {
            "fastapi": "fastapi",
            "django": "django",
            "flask": "flask",
            "streamlit": "streamlit",
        }
        for name, key in py_fw.items():
            if key in content.lower():
                info.framework = info.framework or name
                break

        py_test = {"pytest": "pytest", "unittest": "unittest"}
        for name, key in py_test.items():
            if key in content.lower():
                info.testing.append(name)

    # --- DB ---
    db_indicators = {
        "postgresql": ["postgres", "pg", "psycopg", "DATABASE_URL.*postgres"],
        "mysql": ["mysql", "mysql2"],
        "mongodb": ["mongoose", "mongodb", "MONGO"],
        "sqlite": ["sqlite", "better-sqlite3"],
        "redis": ["redis", "ioredis"],
        "supabase": ["@supabase/supabase-js", "SUPABASE_URL"],
    }
    for db_name, indicators in db_indicators.items():
        for indicator in indicators:
            if _file_contains_any(target, indicator, max_files=5):
                info.db = db_name
                break
        if info.db:
            break

    # --- CI/CD ---
    if (target / ".github" / "workflows").is_dir():
        info.ci = "github-actions"
    elif (target / ".gitlab-ci.yml").exists():
        info.ci = "gitlab-ci"
    elif (target / "Jenkinsfile").exists():
        info.ci = "jenkins"

    # --- Containerization ---
    if (target / "Dockerfile").exists() or (target / "docker-compose.yml").exists():
        info.containerization = "docker"

    return info


def _file_contains_any(target: Path, pattern: str, max_files: int = 5) -> bool:
    """Busca un patrón en archivos de config del proyecto."""
    config_files = [
        target / "package.json",
        target / ".env",
        target / ".env.example",
        target / "docker-compose.yml",
        target / "pyproject.toml",
    ]
    compiled = re.compile(pattern, re.IGNORECASE)
    checked = 0
    for f in config_files:
        if f.exists() and checked < max_files:
            try:
                if compiled.search(f.read_text(encoding="utf-8", errors="ignore")):
                    return True
            except Exception:
                pass
            checked += 1
    return False


def _infer_architecture(target: Path, stack: StackInfo) -> str:
    """Infiere arquitectura general del proyecto."""
    if (target / "apps").is_dir() or (target / "packages").is_dir():
        return "monorepo"
    if stack.framework in ("next.js", "nuxt"):
        if (target / "src" / "app").is_dir() or (target / "app").is_dir():
            return "fullstack-app-router"
        return "fullstack-pages"
    if stack.framework in ("express", "fastify", "hono", "fastapi", "django", "flask"):
        return "api-backend"
    if stack.framework in ("react", "vue", "svelte", "angular"):
        return "spa-frontend"
    return "unknown"


def _infer_domain(target: Path) -> str:
    """Intenta inferir el dominio de negocio del proyecto."""
    indicators = {
        "ecommerce": ["cart", "checkout", "product", "order", "payment", "shop"],
        "payroll": ["salary", "kintai", "nomina", "payslip", "timesheet"],
        "cms": ["post", "article", "content", "editor", "publish"],
        "crm": ["lead", "contact", "pipeline", "deal", "customer"],
        "saas": ["subscription", "plan", "billing", "tenant", "pricing"],
        "social": ["feed", "follow", "like", "comment", "profile"],
        "analytics": ["dashboard", "metric", "chart", "report", "insight"],
    }
    # Scan directory names and file names
    all_names = set()
    for item in target.rglob("*"):
        if item.is_file() and not any(
            p in str(item) for p in ["node_modules", ".git", "__pycache__", ".next"]
        ):
            all_names.add(item.stem.lower())
        if len(all_names) > 500:
            break

    scores: dict[str, int] = {}
    for domain, keywords in indicators.items():
        score = sum(1 for kw in keywords if any(kw in name for name in all_names))
        if score >= 2:
            scores[domain] = score

    if scores:
        return max(scores, key=scores.get)
    return "general"


def _quick_pattern_scan(target: Path) -> list[DetectedPattern]:
    """Escaneo rápido de patrones comunes en el código."""
    patterns: list[DetectedPattern] = []

    pattern_indicators = [
        ("middleware", ["middleware", "interceptor"], "middleware"),
        ("rate-limiting", ["rate-limit", "rateLimit", "throttle"], "resilience"),
        ("retry-pattern", ["retry", "backoff", "exponentialBackoff"], "resilience"),
        ("circuit-breaker", ["circuitBreaker", "circuit_breaker"], "resilience"),
        ("auth-middleware", ["authenticate", "requireAuth", "protect"], "middleware"),
        ("validation-schema", ["schema", "validate", "zod.object", "yup.object"], "data"),
        ("pagination", ["paginate", "pagination", "cursor", "offset"], "data"),
        ("caching", ["cache", "redis.get", "lru_cache"], "data"),
        ("webhook-handler", ["webhook", "handleWebhook"], "api"),
        ("error-handler", ["errorHandler", "error_handler", "exception_handler"], "middleware"),
    ]

    src_dirs = [target / "src", target / "app", target / "lib", target / "server"]
    src_dir = next((d for d in src_dirs if d.is_dir()), target)

    for pattern_name, keywords, category in pattern_indicators:
        for f in _find_source_files(src_dir, max_files=200):
            try:
                content = f.read_text(encoding="utf-8", errors="ignore")
                if any(kw in content for kw in keywords):
                    rel_path = str(f.relative_to(target))
                    patterns.append(
                        DetectedPattern(
                            name=pattern_name,
                            category=category,
                            file=rel_path,
                            reusable=not _is_app_specific(content, target.name),
                        )
                    )
                    break  # One match per pattern is enough
            except Exception:
                continue

    return patterns


def _find_source_files(directory: Path, max_files: int = 200) -> list[Path]:
    """Lista archivos fuente relevantes."""
    extensions = {".py", ".ts", ".tsx", ".js", ".jsx", ".rs", ".go"}
    skip_dirs = {"node_modules", ".git", "__pycache__", ".next", "dist", "build", "target"}
    files: list[Path] = []
    for f in directory.rglob("*"):
        if f.is_file() and f.suffix in extensions and not any(s in f.parts for s in skip_dirs):
            files.append(f)
            if len(files) >= max_files:
                break
    return files


def _is_app_specific(content: str, app_name: str) -> bool:
    """Determina si un patrón es específico de la app (no reutilizable)."""
    app_lower = app_name.lower()
    content_lower = content.lower()
    specific_indicators = [app_lower, f"/{app_lower}/", f"'{app_lower}'", f'"{app_lower}"']
    return any(ind in content_lower for ind in specific_indicators)


# ── Perfil management ──


def save_profile(profile: AppProfile) -> Path:
    """Guarda perfil en ~/.antigravity/profiles/."""
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", profile.name).lower()
    path = PROFILES_DIR / f"{slug}.json"

    # Versioning: si existe, guardar anterior
    if path.exists():
        try:
            existing = json.loads(path.read_text(encoding="utf-8"))
            if "previous_versions" not in existing:
                existing["previous_versions"] = []
            # Strip previous_versions del snapshot para no anidar
            snapshot = {k: v for k, v in existing.items() if k != "previous_versions"}
            profile.previous_versions = existing["previous_versions"] + [snapshot]
            profile.version = existing.get("version", 1) + 1
        except Exception:
            pass

    path.write_text(json.dumps(asdict(profile), indent=2, ensure_ascii=False), encoding="utf-8")
    logger.info(f"Perfil guardado: {path}")
    return path


def load_profile(app_name: str) -> AppProfile | None:
    """Carga perfil existente."""
    slug = re.sub(r"[^a-zA-Z0-9_-]", "-", app_name).lower()
    path = PROFILES_DIR / f"{slug}.json"
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return AppProfile(**{k: v for k, v in data.items() if k in AppProfile.__dataclass_fields__})
    except Exception as e:
        logger.warning(f"Error cargando perfil {path}: {e}")
        return None


def list_profiles() -> list[dict[str, Any]]:
    """Lista todos los perfiles existentes."""
    profiles: list[dict[str, Any]] = []
    for f in PROFILES_DIR.glob("*.json"):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
            profiles.append(
                {
                    "name": data.get("name", f.stem),
                    "path": data.get("path", ""),
                    "analysis_mode": data.get("analysis_mode", "unknown"),
                    "analyzed_at": data.get("analyzed_at", ""),
                    "stack": data.get("stack", {}),
                    "generated_agents": len(data.get("generated_agents", [])),
                    "generated_skills": len(data.get("generated_skills", [])),
                    "detected_patterns": len(data.get("detected_patterns", [])),
                }
            )
        except Exception:
            continue
    return profiles


# ── APP_KNOWLEDGE.md generation ──


def generate_app_knowledge_md(profile: AppProfile) -> str:
    """Genera contenido de APP_KNOWLEDGE.md desde un perfil."""
    stack = profile.stack
    lines = [
        f"# APP_KNOWLEDGE — {profile.name}",
        "",
        f"> Generado: {profile.analyzed_at}",
        f"> Modo: {profile.analysis_mode}",
        "",
        "## Stack",
        "",
        f"- **Lenguaje**: {stack.get('language', 'unknown')}",
        f"- **Framework**: {stack.get('framework', 'N/A')}",
        f"- **Base de datos**: {stack.get('db', 'N/A')}",
        f"- **ORM**: {stack.get('orm', 'N/A')}",
        f"- **Testing**: {', '.join(stack.get('testing', [])) or 'N/A'}",
        f"- **Styling**: {stack.get('styling', 'N/A')}",
        f"- **Estado**: {stack.get('state', 'N/A')}",
        f"- **Auth**: {stack.get('auth', 'N/A')}",
        f"- **Pagos**: {stack.get('payments', 'N/A')}",
        f"- **CI/CD**: {stack.get('ci', 'N/A')}",
        f"- **Containers**: {stack.get('containerization', 'N/A')}",
        "",
        f"## Arquitectura: {profile.architecture}",
        "",
        f"## Dominio: {profile.business_domain}",
        "",
    ]

    if profile.critical_flows:
        lines.append("## Flujos Críticos")
        lines.append("")
        for flow in profile.critical_flows:
            lines.append(f"- {flow}")
        lines.append("")

    if profile.detected_patterns:
        lines.append("## Patrones Detectados")
        lines.append("")
        lines.append("| Patrón | Categoría | Archivo | Reutilizable |")
        lines.append("|---|---|---|---|")
        for p in profile.detected_patterns:
            reuse = "yes" if p.get("reusable") else "no"
            lines.append(
                f"| {p['name']} | {p.get('category', '')} | {p.get('file', '')} | {reuse} |"
            )
        lines.append("")

    if profile.generated_agents:
        lines.append("## Agentes Generados")
        lines.append("")
        for a in profile.generated_agents:
            lines.append(f"- {a}")
        lines.append("")

    if profile.generated_skills:
        lines.append("## Skills Generados")
        lines.append("")
        for s in profile.generated_skills:
            lines.append(f"- {s}")
        lines.append("")

    return "\n".join(lines)


MAX_SKILLS_WITHOUT_APPROVAL = 10
MAX_AGENTS_WITHOUT_APPROVAL = 5

# Conocimiento de frameworks para generar skills útiles
_FRAMEWORK_KNOWLEDGE: dict[str, dict[str, Any]] = {
    "next.js": {
        "patterns": [
            "App Router con Server Components y Client Components",
            "Streaming y Suspense para carga progresiva",
            "Route Handlers (app/api/) en lugar de pages/api/",
            "Metadata API para SEO dinámico",
            "Parallel Routes y Intercepting Routes",
        ],
        "gotchas": [
            "'use client' requerido para hooks de estado y efectos",
            "fetch() en Server Components se cachea por defecto — usar revalidate",
            "Middleware corre en Edge Runtime (no Node APIs completas)",
            "next/image requiere configurar remotePatterns para dominios externos",
        ],
        "tags": ["frontend", "fullstack", "react", "ssr"],
    },
    "react": {
        "patterns": [
            "Custom hooks para lógica reutilizable",
            "Context + useReducer para estado complejo",
            "React.memo y useMemo para optimización de renders",
            "Error Boundaries para manejo de errores declarativo",
            "Suspense + lazy() para code splitting",
        ],
        "gotchas": [
            "useEffect con deps vacías no equivale a componentDidMount en Strict Mode",
            "setState es async — no leer state inmediatamente después",
            "Keys en listas deben ser estables (no index si hay reorder)",
            "Closures stale en callbacks — usar useCallback con deps correctas",
        ],
        "tags": ["frontend", "react", "spa"],
    },
    "vue": {
        "patterns": [
            "Composition API con setup() para lógica compleja",
            "Composables (use*) para reutilizar lógica reactiva",
            "Pinia para estado global tipado",
            "v-model con defineModel() en Vue 3.4+",
        ],
        "gotchas": [
            "reactive() pierde reactividad al desestructurar — usar toRefs()",
            "watch vs watchEffect: watch es lazy, watchEffect ejecuta inmediatamente",
            "Props son readonly — nunca mutar directamente",
        ],
        "tags": ["frontend", "vue", "spa"],
    },
    "express": {
        "patterns": [
            "Middleware chain para request processing",
            "Router modular con express.Router()",
            "Error-handling middleware (4 params) al final del chain",
            "Helmet + cors + rate-limit como seguridad base",
        ],
        "gotchas": [
            "Async errors no se propagan automáticamente — envolver con try/catch o express-async-errors",
            "El orden de middleware importa — error handler siempre último",
            "res.json() ya establece Content-Type — no duplicar headers",
        ],
        "tags": ["backend", "api", "node"],
    },
    "fastapi": {
        "patterns": [
            "Pydantic models para validación automática de request/response",
            "Depends() para inyección de dependencias",
            "Background tasks para operaciones no-bloqueantes",
            "APIRouter para modularizar endpoints",
            "Lifespan events para startup/shutdown",
        ],
        "gotchas": [
            "async def vs def: FastAPI ejecuta def en threadpool automáticamente",
            "Pydantic V2 usa model_validate() en lugar de parse_obj()",
            "Response model excluye campos None por defecto con response_model_exclude_none",
        ],
        "tags": ["backend", "api", "python"],
    },
    "django": {
        "patterns": [
            "Class-Based Views para CRUD estandarizado",
            "Django REST Framework para APIs",
            "Signals para lógica desacoplada",
            "Custom managers para queries complejas",
            "Middleware para cross-cutting concerns",
        ],
        "gotchas": [
            "N+1 queries: usar select_related() y prefetch_related()",
            "Migrations deben ser lineales — resolver conflictos con merge",
            "Settings.py: usar django-environ para configuración por entorno",
        ],
        "tags": ["backend", "fullstack", "python"],
    },
    "prisma": {
        "patterns": [
            "Schema-first design con prisma.schema",
            "Relaciones implícitas y explícitas",
            "Transactions con $transaction para operaciones atómicas",
            "Middleware de Prisma para logging y soft-deletes",
            "Prisma Client Extensions para métodos custom",
        ],
        "gotchas": [
            "prisma generate después de cada cambio en schema",
            "No usar findFirst sin where único — puede retornar resultados inesperados",
            "Enums deben estar en sync entre schema y DB",
        ],
        "tags": ["orm", "database", "typescript"],
    },
    "tailwind": {
        "patterns": [
            "Utility-first con clases composables",
            "cn() helper con clsx + tailwind-merge para merge condicional",
            "Design tokens via @theme (v4) o theme.extend (v3)",
            "Responsive design con breakpoints mobile-first",
        ],
        "gotchas": [
            "PurgeCSS en prod: clases dinámicas deben estar completas (no concatenar strings)",
            "Tailwind v4 usa CSS @theme en lugar de tailwind.config.js",
            "Especificidad: !important via ! prefix (e.g., !text-red-500)",
        ],
        "tags": ["styling", "css", "frontend"],
    },
}

# Conocimiento de dominios para generar skills de negocio
_DOMAIN_KNOWLEDGE: dict[str, dict[str, Any]] = {
    "ecommerce": {
        "flows": ["cart-management", "checkout-flow", "inventory-sync", "order-lifecycle"],
        "rules": [
            "Validar stock antes de confirmar orden",
            "Precios siempre en centavos (integer) para evitar errores de punto flotante",
            "Idempotency keys en pagos para evitar cobros duplicados",
        ],
    },
    "payroll": {
        "flows": ["timesheet-calculation", "salary-rules", "tax-withholding", "pay-period-close"],
        "rules": [
            "Cálculos monetarios con Decimal, nunca float",
            "Zona horaria explícita en registros de tiempo",
            "Validación cruzada: horas reportadas vs contrato",
        ],
    },
    "saas": {
        "flows": ["subscription-lifecycle", "billing-cycle", "tenant-isolation", "usage-metering"],
        "rules": [
            "Tenant isolation en cada query de DB",
            "Webhook idempotency para eventos de billing",
            "Feature flags para rollout gradual por plan",
        ],
    },
    "cms": {
        "flows": [
            "content-workflow",
            "publishing-pipeline",
            "media-management",
            "seo-optimization",
        ],
        "rules": [
            "Draft/Published/Archived como estados mínimos",
            "Slugs únicos y URL-safe",
            "Sanitizar HTML de usuario para prevenir XSS",
        ],
    },
    "analytics": {
        "flows": ["data-ingestion", "metric-aggregation", "report-generation", "alert-rules"],
        "rules": [
            "Timestamps siempre UTC en almacenamiento",
            "Agregaciones pre-calculadas para dashboards rápidos",
            "Rate limit en queries pesadas",
        ],
    },
}


def determine_destination(name: str, content: str, app_name: str) -> str:
    """Determina si un artefacto generado va al ecosistema central o local de la app.

    Args:
        name: Nombre del skill o agente.
        content: Contenido del archivo generado.
        app_name: Nombre de la app analizada.

    Returns:
        'central' o 'local' según corresponda.
    """
    app_lower = app_name.lower()
    name_lower = name.lower()

    # Si el nombre contiene el nombre de la app, es local
    if app_lower in name_lower:
        return "local"

    # Si el contenido referencia datos específicos de la app
    app_indicators = [
        f"para {app_lower}",
        f"for {app_lower}",
        f"específico de {app_lower}",
        f"Generated by App Intelligence Pipeline for {app_lower}",
    ]
    content_lower = content.lower()
    if any(ind in content_lower for ind in app_indicators):
        return "local"

    return "central"


def _generate_skill_md(
    name: str,
    description: str,
    version: str,
    tags: list[str],
    sections: dict[str, list[str]],
) -> str:
    """Genera contenido de un SKILL.md con frontmatter YAML válido.

    Args:
        name: Nombre del skill.
        description: Descripción breve.
        version: Versión semántica.
        tags: Lista de tags.
        sections: Diccionario de sección → lista de items.

    Returns:
        Contenido Markdown con frontmatter.
    """
    tags_str = ", ".join(tags)
    lines = [
        "---",
        f"name: {name}",
        f"description: {description}",
        f"version: {version}",
        f"tags: [{tags_str}]",
        "---",
        "",
        f"# {name}",
        "",
        f"{description}",
        "",
    ]

    for section_title, items in sections.items():
        lines.append(f"## {section_title}")
        lines.append("")
        for item in items:
            lines.append(f"- {item}")
        lines.append("")

    return "\n".join(lines)


def _generate_identity_md(
    name: str,
    tier: int,
    description: str,
    capabilities: list[str],
    tools: list[str],
    app_name: str,
    stack_summary: str,
) -> str:
    """Genera contenido de un IDENTITY.md para agente.

    Args:
        name: Nombre del agente.
        tier: Tier jerárquico (1-12).
        description: Descripción breve.
        capabilities: Lista de capacidades.
        tools: Lista de herramientas.
        app_name: Nombre de la app objetivo.
        stack_summary: Resumen del stack técnico.

    Returns:
        Contenido Markdown con frontmatter.
    """
    lines = [
        "---",
        f"name: {name}",
        f"tier: {tier}",
        f"description: {description}",
        "---",
        "",
        f"# {name}",
        "",
        "## Capabilities",
        "",
    ]
    for cap in capabilities:
        lines.append(f"- {cap}")

    lines.extend(["", "## Tools", ""])
    for tool in tools:
        lines.append(f"- {tool}")

    lines.extend(
        [
            "",
            "## Context",
            "",
            f"Generated by App Intelligence Pipeline for {app_name}.",
            f"Stack: {stack_summary}",
            "",
        ]
    )

    return "\n".join(lines)


def generate_skills_for_profile(
    profile: AppProfile,
    ecosystem_root: Path,
    app_root: Path,
) -> list[dict[str, Any]]:
    """Genera skills basados en el stack y dominio del perfil.

    Crea skills técnicos (por framework/herramienta) en el ecosistema central
    y skills de dominio (por negocio) en la app local.

    Args:
        profile: Perfil de app analizado.
        ecosystem_root: Raíz del ecosistema (repo OpenAntigravity).
        app_root: Raíz de la app analizada.

    Returns:
        Lista de diccionarios con info de cada skill generado.
    """
    generated: list[dict[str, Any]] = []
    stack = profile.stack
    central_skills_dir = ecosystem_root / ".agent" / "skills"
    local_skills_dir = app_root / ".agent" / "skills-custom"
    skill_count = 0

    # ── Skills técnicos (basados en stack) ──
    # Recolectar frameworks/herramientas detectadas
    tech_items: list[str] = []
    framework_raw = stack.get("framework", "")
    if framework_raw:
        # Extraer nombre base sin versión (e.g., "next.js-14.2.0" → "next.js")
        fw_name = framework_raw.split("-")[0] if "-" in framework_raw else framework_raw
        tech_items.append(fw_name)

    for key in ["orm", "styling", "state", "auth"]:
        val = stack.get(key, "")
        if val:
            tech_items.append(val)

    for tech in tech_items:
        if skill_count >= MAX_SKILLS_WITHOUT_APPROVAL:
            logger.warning(
                f"Límite de {MAX_SKILLS_WITHOUT_APPROVAL} skills alcanzado (sin aprobación)"
            )
            break

        skill_name = f"{tech}-patterns"
        skill_dir = central_skills_dir / skill_name

        # Nunca sobrescribir skills existentes
        if skill_dir.exists() and (skill_dir / "SKILL.md").exists():
            logger.info(f"Skill ya existe, omitido: {skill_name}")
            continue

        knowledge = _FRAMEWORK_KNOWLEDGE.get(tech, {})
        patterns = knowledge.get("patterns", [f"Mejores prácticas de {tech}"])
        gotchas = knowledge.get("gotchas", [f"Revisar documentación oficial de {tech}"])
        tags = knowledge.get("tags", [tech])

        sections: dict[str, list[str]] = {
            "Mejores Prácticas": patterns,
            "Gotchas y Errores Comunes": gotchas,
        }

        content = _generate_skill_md(
            name=skill_name,
            description=f"Patrones y mejores prácticas para {tech}",
            version="1.0.0",
            tags=tags,
            sections=sections,
        )

        destination = determine_destination(skill_name, content, profile.name)
        if destination == "central":
            target_dir = central_skills_dir / skill_name
        else:
            target_dir = local_skills_dir / skill_name

        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "SKILL.md").write_text(content, encoding="utf-8")
        logger.info(f"Skill generado ({destination}): {skill_name}")

        generated.append(
            {
                "type": "skill",
                "name": skill_name,
                "destination": destination,
                "path": str(target_dir / "SKILL.md"),
            }
        )
        skill_count += 1

    # ── Skills de dominio (basados en business_domain y critical_flows) ──
    domain = profile.business_domain
    domain_info = _DOMAIN_KNOWLEDGE.get(domain, {})
    domain_flows = domain_info.get("flows", [])
    domain_rules = domain_info.get("rules", [])

    # Combinar flows del dominio con critical_flows detectados
    all_flows = list(set(domain_flows + profile.critical_flows))

    for flow in all_flows:
        if skill_count >= MAX_SKILLS_WITHOUT_APPROVAL:
            logger.warning(
                f"Límite de {MAX_SKILLS_WITHOUT_APPROVAL} skills alcanzado (sin aprobación)"
            )
            break

        flow_slug = re.sub(r"[^a-zA-Z0-9]", "-", flow).lower().strip("-")
        skill_name = f"{profile.name.lower()}-{flow_slug}"
        target_dir = local_skills_dir / skill_name

        if target_dir.exists() and (target_dir / "SKILL.md").exists():
            logger.info(f"Skill ya existe, omitido: {skill_name}")
            continue

        sections = {
            "Flujo": [f"Implementación del flujo: {flow}"],
            "Reglas de Negocio": domain_rules
            if domain_rules
            else [f"Definir reglas de negocio para {flow}"],
            "Validaciones": [
                f"Validar datos de entrada del flujo {flow}",
                "Verificar permisos del usuario",
            ],
        }

        content = _generate_skill_md(
            name=skill_name,
            description=f"Reglas y lógica del flujo {flow} para {profile.name}",
            version="1.0.0",
            tags=[domain, flow_slug, profile.name.lower()],
            sections=sections,
        )

        target_dir.mkdir(parents=True, exist_ok=True)
        (target_dir / "SKILL.md").write_text(content, encoding="utf-8")
        logger.info(f"Skill de dominio generado (local): {skill_name}")

        generated.append(
            {
                "type": "skill",
                "name": skill_name,
                "destination": "local",
                "path": str(target_dir / "SKILL.md"),
            }
        )
        skill_count += 1

    return generated


def generate_agents_for_profile(
    profile: AppProfile,
    ecosystem_root: Path,
    app_root: Path,
) -> list[dict[str, Any]]:
    """Genera agentes basados en el stack y dominio del perfil.

    Crea agentes técnicos en el ecosistema central y agentes de dominio/operacionales
    en la app local.

    Args:
        profile: Perfil de app analizado.
        ecosystem_root: Raíz del ecosistema (repo OpenAntigravity).
        app_root: Raíz de la app analizada.

    Returns:
        Lista de diccionarios con info de cada agente generado.
    """
    generated: list[dict[str, Any]] = []
    stack = profile.stack
    central_agents_dir = ecosystem_root / ".agent" / "agents"
    local_agents_dir = app_root / ".agent" / "agents"
    agent_count = 0

    stack_summary = f"{stack.get('language', 'unknown')} / {stack.get('framework', 'N/A')}"
    if stack.get("orm"):
        stack_summary += f" / {stack['orm']}"
    if stack.get("db"):
        stack_summary += f" / {stack['db']}"

    # ── Agentes técnicos (por framework) ──
    framework_raw = stack.get("framework", "")
    if framework_raw:
        fw_name = framework_raw.split("-")[0] if "-" in framework_raw else framework_raw
        agent_name = f"{fw_name}-specialist"
        agent_dir = central_agents_dir / agent_name

        if agent_dir.exists() and (agent_dir / "IDENTITY.md").exists():
            logger.info(f"Agente ya existe, omitido: {agent_name}")
        elif agent_count < MAX_AGENTS_WITHOUT_APPROVAL:
            knowledge = _FRAMEWORK_KNOWLEDGE.get(fw_name, {})
            capabilities = knowledge.get("patterns", [f"Desarrollo con {fw_name}"])[:5]
            tools = ["search_skills", "read_skill", "run_skill"]

            content = _generate_identity_md(
                name=agent_name,
                tier=6,
                description=f"Especialista en {fw_name} — patrones, debugging y optimización",
                capabilities=capabilities,
                tools=tools,
                app_name=profile.name,
                stack_summary=stack_summary,
            )

            destination = determine_destination(agent_name, content, profile.name)
            if destination == "central":
                target_dir = central_agents_dir / agent_name
            else:
                target_dir = local_agents_dir / agent_name

            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "IDENTITY.md").write_text(content, encoding="utf-8")
            logger.info(f"Agente técnico generado ({destination}): {agent_name}")

            generated.append(
                {
                    "type": "agent",
                    "name": agent_name,
                    "destination": destination,
                    "path": str(target_dir / "IDENTITY.md"),
                }
            )
            agent_count += 1

    # ── Agente de dominio ──
    domain = profile.business_domain
    if domain and domain != "general":
        agent_name = f"{domain}-analyst"
        local_dir = local_agents_dir / agent_name

        if local_dir.exists() and (local_dir / "IDENTITY.md").exists():
            logger.info(f"Agente ya existe, omitido: {agent_name}")
        elif agent_count < MAX_AGENTS_WITHOUT_APPROVAL:
            domain_info = _DOMAIN_KNOWLEDGE.get(domain, {})
            domain_flows = domain_info.get("flows", [])
            capabilities = [f"Análisis de flujos de {domain}"]
            capabilities += [f"Validar flujo: {f}" for f in domain_flows[:3]]
            capabilities.append(f"Reglas de negocio del dominio {domain}")

            content = _generate_identity_md(
                name=agent_name,
                tier=6,
                description=f"Analista de dominio {domain} para {profile.name}",
                capabilities=capabilities,
                tools=["search_skills", "read_skill", "memory_recall"],
                app_name=profile.name,
                stack_summary=stack_summary,
            )

            local_dir.mkdir(parents=True, exist_ok=True)
            (local_dir / "IDENTITY.md").write_text(content, encoding="utf-8")
            logger.info(f"Agente de dominio generado (local): {agent_name}")

            generated.append(
                {
                    "type": "agent",
                    "name": agent_name,
                    "destination": "local",
                    "path": str(local_dir / "IDENTITY.md"),
                }
            )
            agent_count += 1

    # ── Agentes operacionales ──
    app_slug = re.sub(r"[^a-zA-Z0-9]", "-", profile.name).lower().strip("-")
    operational_agents = [
        {
            "name": f"test-runner-{app_slug}",
            "description": f"Ejecuta y monitorea tests de {profile.name}",
            "capabilities": [
                f"Ejecutar suite de tests ({', '.join(stack.get('testing', ['tests']))})",
                "Analizar resultados y reportar fallos",
                "Sugerir tests faltantes basado en cobertura",
                "Detectar tests flaky",
            ],
            "tools": ["run_skill", "read_file", "search_skills"],
        },
        {
            "name": f"deploy-helper-{app_slug}",
            "description": f"Asiste con el despliegue de {profile.name}",
            "capabilities": [
                f"Verificar pre-condiciones de deploy ({stack.get('ci', 'manual')})",
                f"Validar configuración de {stack.get('containerization', 'entorno')}",
                "Checklist de deploy: tests, lint, build, env vars",
                "Rollback asistido en caso de fallo",
            ],
            "tools": ["run_skill", "search_skills", "memory_store"],
        },
    ]

    for op_agent in operational_agents:
        if agent_count >= MAX_AGENTS_WITHOUT_APPROVAL:
            logger.warning(
                f"Límite de {MAX_AGENTS_WITHOUT_APPROVAL} agentes alcanzado (sin aprobación)"
            )
            break

        agent_name = op_agent["name"]
        local_dir = local_agents_dir / agent_name

        if local_dir.exists() and (local_dir / "IDENTITY.md").exists():
            logger.info(f"Agente ya existe, omitido: {agent_name}")
            continue

        content = _generate_identity_md(
            name=agent_name,
            tier=6,
            description=op_agent["description"],
            capabilities=op_agent["capabilities"],
            tools=op_agent["tools"],
            app_name=profile.name,
            stack_summary=stack_summary,
        )

        local_dir.mkdir(parents=True, exist_ok=True)
        (local_dir / "IDENTITY.md").write_text(content, encoding="utf-8")
        logger.info(f"Agente operacional generado (local): {agent_name}")

        generated.append(
            {
                "type": "agent",
                "name": agent_name,
                "destination": "local",
                "path": str(local_dir / "IDENTITY.md"),
            }
        )
        agent_count += 1

    return generated


def write_app_knowledge(profile: AppProfile) -> Path | None:
    """Escribe APP_KNOWLEDGE.md en el directorio .antigravity de la app."""
    target = Path(profile.path)
    if not target.is_dir():
        return None
    antigravity_dir = target / ".antigravity"
    antigravity_dir.mkdir(parents=True, exist_ok=True)
    knowledge_path = antigravity_dir / "APP_KNOWLEDGE.md"
    knowledge_path.write_text(generate_app_knowledge_md(profile), encoding="utf-8")
    logger.info(f"APP_KNOWLEDGE.md escrito: {knowledge_path}")
    return knowledge_path


# ── Pattern extraction ──


def _extract_code_block(content: str, pattern_name: str) -> str:
    """Extrae el bloque de código relevante (función/clase/middleware) según el nombre del patrón.

    Args:
        content: Contenido completo del archivo fuente.
        pattern_name: Nombre del patrón a buscar.

    Returns:
        Bloque de código extraído o fragmento relevante.
    """
    # Convertir pattern name a posibles identificadores
    identifiers = [
        pattern_name,
        pattern_name.replace("-", "_"),
        pattern_name.replace("-", ""),
        "".join(w.capitalize() for w in pattern_name.split("-")),  # PascalCase
    ]
    # Buscar camelCase también
    parts = pattern_name.split("-")
    if len(parts) > 1:
        identifiers.append(parts[0] + "".join(w.capitalize() for w in parts[1:]))

    lines = content.split("\n")
    best_start = -1
    best_identifier = ""

    for identifier in identifiers:
        for i, line in enumerate(lines):
            if identifier.lower() in line.lower():
                best_start = i
                best_identifier = identifier
                break
        if best_start >= 0:
            break

    if best_start < 0:
        # Retornar las primeras 50 líneas como fallback
        return "\n".join(lines[:50])

    # Determinar el bloque: buscar inicio de función/clase/middleware
    block_start = best_start
    for i in range(best_start, max(best_start - 10, -1), -1):
        stripped = lines[i].lstrip()
        if stripped.startswith(
            ("def ", "class ", "function ", "const ", "export ", "async ", "app.", "router.")
        ):
            block_start = i
            break

    # Determinar fin del bloque por indentación o llaves
    base_indent = len(lines[block_start]) - len(lines[block_start].lstrip())
    block_end = block_start + 1
    brace_depth = 0

    for i in range(block_start, min(len(lines), block_start + 100)):
        brace_depth += lines[i].count("{") - lines[i].count("}")
        if i > block_start:
            current_indent = (
                len(lines[i]) - len(lines[i].lstrip()) if lines[i].strip() else base_indent + 1
            )
            # Bloque termina cuando volvemos a la indentación base (Python) o cerramos llaves
            if lines[i].strip() and current_indent <= base_indent and brace_depth <= 0:
                block_end = i
                break
        block_end = i + 1

    extracted = "\n".join(lines[block_start:block_end])
    if not extracted.strip():
        return (
            f"# Referencia: {best_identifier} encontrado en línea {best_start + 1}\n"
            + "\n".join(lines[max(0, best_start - 2) : min(len(lines), best_start + 20)])
        )
    return extracted


def extract_pattern_as_skill(
    pattern: dict[str, Any],
    app_path: Path,
    ecosystem_root: Path,
) -> dict[str, Any]:
    """Extrae un patrón detectado y lo guarda como skill reutilizable.

    Lee el archivo fuente indicado por el patrón, extrae el código relevante,
    genera un SKILL.md con frontmatter YAML y lo guarda en el ecosistema.

    Args:
        pattern: Diccionario con name, category, file, reusable, description.
        app_path: Ruta raíz del proyecto analizado.
        ecosystem_root: Raíz del ecosistema (repo OpenAntigravity).

    Returns:
        Diccionario con name, path y success.
    """
    pattern_name: str = pattern.get("name", "unknown-pattern")
    category: str = pattern.get("category", "general")
    source_file: str = pattern.get("file", "")
    description: str = pattern.get("description", "")

    skill_name = f"extracted-{pattern_name}"
    skills_dir = ecosystem_root / ".agent" / "skills" / skill_name

    # No sobrescribir skills existentes
    if skills_dir.exists() and (skills_dir / "SKILL.md").exists():
        logger.info(f"Skill ya existe, omitido: {skill_name}")
        return {
            "name": skill_name,
            "path": str(skills_dir / "SKILL.md"),
            "success": False,
            "reason": "already_exists",
        }

    # Leer archivo fuente
    source_path = app_path / source_file
    extracted_code = ""
    if source_path.exists():
        try:
            content = source_path.read_text(encoding="utf-8", errors="ignore")
            extracted_code = _extract_code_block(content, pattern_name)
        except Exception as e:
            logger.warning(f"Error leyendo {source_path}: {e}")
            extracted_code = f"# No se pudo leer: {source_file}\n# Error: {e}"
    else:
        extracted_code = f"# Archivo no encontrado: {source_file}"

    if not description:
        description = f"Patrón {pattern_name} ({category}) extraído de {app_path.name}"

    # Generar SKILL.md
    tags = [category, "extracted", "pattern", app_path.name.lower()]
    skill_content = "\n".join(
        [
            "---",
            f"name: {skill_name}",
            f"description: {description}",
            "version: 1.0.0",
            f"tags: [{', '.join(tags)}]",
            f"source_app: {app_path.name}",
            f"source_file: {source_file}",
            f"category: {category}",
            "---",
            "",
            f"# {skill_name}",
            "",
            f"{description}",
            "",
            "## Contexto",
            "",
            f"Este patrón fue extraído automáticamente de **{app_path.name}** por el App Intelligence Pipeline.",
            f"Archivo fuente: `{source_file}`",
            f"Categoría: **{category}**",
            "",
            "## Código de Referencia",
            "",
            f"```{_guess_language(source_file)}",
            extracted_code,
            "```",
            "",
            "## Uso",
            "",
            f"Este patrón implementa **{pattern_name}** y puede reutilizarse en proyectos similares.",
            f"Adaptar las referencias específicas a la app original ({app_path.name}) antes de integrar.",
            "",
        ]
    )

    skills_dir.mkdir(parents=True, exist_ok=True)
    skill_path = skills_dir / "SKILL.md"
    skill_path.write_text(skill_content, encoding="utf-8")
    logger.info(f"Patrón extraído como skill: {skill_name} → {skill_path}")

    return {"name": skill_name, "path": str(skill_path), "success": True}


def _guess_language(file_path: str) -> str:
    """Infiere el lenguaje de un archivo por su extensión.

    Args:
        file_path: Ruta del archivo.

    Returns:
        Identificador de lenguaje para bloques de código markdown.
    """
    ext_map = {
        ".py": "python",
        ".ts": "typescript",
        ".tsx": "typescript",
        ".js": "javascript",
        ".jsx": "javascript",
        ".rs": "rust",
        ".go": "go",
        ".rb": "ruby",
        ".java": "java",
    }
    for ext, lang in ext_map.items():
        if file_path.endswith(ext):
            return lang
    return ""


def extract_patterns(
    target_dir: Path,
    pattern_names: list[str] | None,
    ecosystem_root: Path,
) -> list[dict[str, Any]]:
    """Extrae patrones detectados de una app como skills reutilizables.

    Carga el perfil existente de la app, filtra los patrones solicitados
    y genera un SKILL.md por cada uno.

    Args:
        target_dir: Directorio de la app analizada.
        pattern_names: Lista de nombres de patrones a extraer. None = todos los reutilizables.
        ecosystem_root: Raíz del ecosistema (repo OpenAntigravity).

    Returns:
        Lista de resultados de extracción.
    """
    app_path = Path(target_dir).resolve()
    profile = load_profile(app_path.name)

    if profile is None:
        # Intentar análisis rápido si no existe perfil
        logger.info(f"No se encontró perfil para {app_path.name}, ejecutando análisis rápido...")
        profile = quick_analyze(app_path)
        save_profile(profile)

    detected = profile.detected_patterns
    if not detected:
        logger.warning("No se detectaron patrones en el perfil")
        return []

    # Filtrar por nombres si se proporcionaron
    if pattern_names is not None and len(pattern_names) > 0:
        detected = [p for p in detected if p.get("name") in pattern_names]
    else:
        # Sin filtro explícito: solo los reutilizables
        detected = [p for p in detected if p.get("reusable", True)]

    results: list[dict[str, Any]] = []
    for pattern in detected:
        result = extract_pattern_as_skill(pattern, app_path, ecosystem_root)
        results.append(result)

    return results


# ── CLI entry point ──


def main() -> None:
    """Entry point CLI."""
    import argparse

    parser = argparse.ArgumentParser(description="App Intelligence Pipeline")
    parser.add_argument("target", nargs="?", default=".", help="Directorio del proyecto")
    parser.add_argument(
        "--mode", choices=["quick", "deep"], default="quick", help="Modo de análisis"
    )
    parser.add_argument("--list-profiles", action="store_true", help="Listar perfiles existentes")
    parser.add_argument("--json", action="store_true", help="Output en JSON")
    parser.add_argument("--generate", action="store_true", help="Generar skills y agentes")
    parser.add_argument(
        "--extract-patterns",
        nargs="*",
        default=None,
        help="Extraer patrones como skills (sin args = todos los reutilizables)",
    )
    args = parser.parse_args()

    if args.list_profiles:
        profiles = list_profiles()
        if args.json:
            print(json.dumps({"profiles": profiles}, indent=2, ensure_ascii=False))
        else:
            for p in profiles:
                print(
                    f"  {p['name']} ({p['analysis_mode']}) — {p['stack'].get('framework', 'unknown')}"
                )
        return

    target = Path(args.target).resolve()
    if not target.is_dir():
        print(f"Error: {target} no es un directorio válido")
        sys.exit(1)

    # Extracción de patrones (no requiere re-análisis completo)
    if args.extract_patterns is not None:
        ecosystem_root = Path(__file__).parent.parent.parent  # repo root
        names = args.extract_patterns if args.extract_patterns else None
        results = extract_patterns(target, names, ecosystem_root)
        if args.json:
            print(json.dumps({"extracted": results}, indent=2, ensure_ascii=False))
        else:
            for r in results:
                status = "OK" if r.get("success") else "SKIP"
                print(f"  [{status}] {r['name']} → {r.get('path', 'N/A')}")
        return

    if args.mode == "quick":
        profile = quick_analyze(target)
    else:
        # Deep analysis uses App Auditor
        profile = quick_analyze(target)
        profile.analysis_mode = "deep"
        audit_result = _run_app_auditor(target)
        if audit_result["status"] != "ok":
            logger.warning("Deep mode: app-auditor no completado: %s", audit_result)
        # Persistir resultado en patterns para trazabilidad del pipeline.
        profile.detected_patterns.append(
            {
                "name": "app_auditor_execution",
                "category": "analysis",
                "file": ".context/APP_KNOWLEDGE.md",
                "description": (
                    f"status={audit_result['status']} "
                    f"returncode={audit_result.get('returncode', 'n/a')}"
                ),
                "reusable": False,
            }
        )

    save_profile(profile)
    write_app_knowledge(profile)

    if args.generate:
        ecosystem_root = Path(__file__).parent.parent.parent  # repo root
        generated = generate_skills_for_profile(profile, ecosystem_root, target)
        generated += generate_agents_for_profile(profile, ecosystem_root, target)
        profile.generated_skills = [g["name"] for g in generated if g["type"] == "skill"]
        profile.generated_agents = [g["name"] for g in generated if g["type"] == "agent"]
        save_profile(profile)

    if args.json:
        print(json.dumps(asdict(profile), indent=2, ensure_ascii=False))
    else:
        print(f"\n⚡ App Intelligence — {profile.name}")
        print(f"   Stack: {profile.stack.get('language')} / {profile.stack.get('framework')}")
        print(f"   Arquitectura: {profile.architecture}")
        print(f"   Dominio: {profile.business_domain}")
        print(f"   Patrones: {len(profile.detected_patterns)}")
        print(f"   Perfil: ~/.antigravity/profiles/{profile.name.lower()}.json")


if __name__ == "__main__":
    main()
