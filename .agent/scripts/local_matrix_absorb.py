#!/usr/bin/env python3
"""
Local Matrix Absorb — Absorbe conocimiento de apps LOCALES al Brain.

Diferencia con master_plan_absorb.py:
- No clona desde GitHub, lee directo desde el filesystem local.
- Catalogo extendido con apps no pusheadas o ausentes del master.
- Idempotente: skip si ya existe nodo con hash identico.
- Tags canonicos segun docs/rules-reference/repo-crawler.md.

Uso:
    python local_matrix_absorb.py                    # todas las apps locales
    python local_matrix_absorb.py --only <name>      # una app
    python local_matrix_absorb.py --dry-run          # solo plan
    python local_matrix_absorb.py --missing-only     # solo apps sin nodos previos
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
LOCAL_APPS_ROOT = REPO_ROOT.parent  # C:/Users/kenji/Github/Jpkken1979
BRAIN_DIR = REPO_ROOT / ".agent" / "brain"

sys.path.insert(0, str(REPO_ROOT / ".agent"))
from core.brain import Brain  # noqa: E402

# ---------------------------------------------------------------------------
# Catalogo de apps locales
# ---------------------------------------------------------------------------
# priority: high | medium | normal
# domain: business | dev | ops | ux | docs | data
# tags: canonical tags from repo-crawler rules
# ---------------------------------------------------------------------------

APPS: dict[str, dict] = {
    # === CORE UNS BUSINESS ===
    "Kobetsuv2.26.4.1": {
        "priority": "high",
        "domain": "business",
        "desc": "個別契約書 v2.26.4.1 — Generador de contratos individuales dispatch",
        "tags": ["kobetsu", "uns-dispatch", "contracts", "pdf", "individual-contract"],
    },
    "Arari-PROv5.026.3.30": {
        "priority": "high",
        "domain": "business",
        "desc": "粗利 PRO v5 — Calculo de margen bruto por trabajador",
        "tags": ["arari", "uns-dispatch", "profit-margin", "api", "fastapi"],
    },
    "Arari-PROv2.0_Dokploy26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "粗利 PRO v2 Dokploy — Version deployable de arari",
        "tags": ["arari", "dokploy", "docker", "deploy"],
    },
    "Chingiv7.026.3.30": {
        "priority": "high",
        "domain": "business",
        "desc": "賃金台帳 v7 — Registro maestro de salarios",
        "tags": ["chingi", "uns-dispatch", "salary", "payroll", "daicho"],
    },
    "KintaiFlow1.0v26.3.30": {
        "priority": "high",
        "domain": "business",
        "desc": "勤怠 Flow — Sistema de asistencia con agentes IA",
        "tags": ["kintaiflow", "kintai", "uns-dispatch", "attendance", "multiagent"],
    },
    "KintaiKyuryouv2.026.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "勤怠給料 v2 — Asistencia + calculo de salarios unificado",
        "tags": ["kintai", "chingi", "payroll", "uns-dispatch"],
    },
    "JpRirekiUltimate26.3.30": {
        "priority": "high",
        "domain": "business",
        "desc": "履歴書 Ultimate — Staffing OS con Next.js + Prisma",
        "tags": ["rirekisho", "nextjs", "prisma", "staffing", "uns-dispatch"],
    },
    "JpRireki-app1.0v26.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "履歴書 App v1 — Generador de CV japones primera version",
        "tags": ["rirekisho", "cv", "pdf", "uns-dispatch"],
    },
    "JpRireki-Shain-unifi26.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "履歴書 Shain unificado — CV + datos empleado unificados",
        "tags": ["rirekisho", "employee-data", "cv-unified", "uns-dispatch"],
    },
    "RirekishoDBaseAntigua26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Rirekisho DBase antigua — BD historica de CVs",
        "tags": ["rirekisho", "legacy", "database", "migration"],
    },
    "CV-RIREKI-26.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "CV-RIREKI — Generador de CV/履歴書 (React + Tauri/Web)",
        "tags": ["rirekisho", "cv", "react", "uns-dispatch"],
    },
    "YukyuData-AppFusion2.1626.3.30": {
        "priority": "high",
        "domain": "business",
        "desc": "有給 Data Fusion — Gestion de vacaciones pagadas",
        "tags": ["yukyu", "vacation", "uns-dispatch", "docker"],
    },
    "Kashitsuke-UNSv1.026.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "貸付 UNS — Sistema de prestamos a empleados",
        "tags": ["kashitsuke", "loans", "deductions", "uns-dispatch"],
    },
    "tiravisas-master26.3.30": {
        "priority": "high",
        "domain": "business",
        "desc": "ビザ — Control de visas de trabajadores extranjeros",
        "tags": ["tiravisas", "visas", "immigration", "uns-dispatch", "excel"],
    },
    "UNS-System-JpNyushaTaisha26.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "入社退社 — Registro altas/bajas de empleados",
        "tags": ["nyushataisha", "onboarding", "offboarding", "uns-dispatch"],
    },
    "Uns-Kintai-appJpX26.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "UNS Kintai AppJpX — Control horario UNS variante",
        "tags": ["kintai", "uns-dispatch", "attendance"],
    },
    # === APARTAMENTOS / PROPIEDADES ===
    "Opus4.6Apartementos26.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "Apartamentos Opus 4.6 — Gestion propiedades trabajadores",
        "tags": ["apartments", "property-management", "uns-dispatch"],
    },
    "opus46apartementos26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Apartamentos Opus 4.6 (variante)",
        "tags": ["apartments", "property-management"],
    },
    "uns-apartment26.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "UNS Apartment — Version web gestion apartamentos",
        "tags": ["apartments", "web-app", "uns-dispatch"],
    },
    # === KOBETSU WEB ===
    "uns-kobetsu26.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "UNS Kobetsu web — Version web generador 個別契約書",
        "tags": ["kobetsu", "web-app", "uns-dispatch"],
    },
    # === HERRAMIENTAS / CLI / IA ===
    "CodexBar-mainJp26.3.30": {
        "priority": "medium",
        "domain": "dev",
        "desc": "CodexBar — Herramienta CLI/desktop con IA integrada",
        "tags": ["codexbar", "cli", "ai", "desktop"],
    },
    "CodeXCATimerCard26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Codex CA TimerCard — Control horario con Codex",
        "tags": ["timercard", "codex", "attendance"],
    },
    "TimercardStudioIA26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Timercard Studio IA — Control horario con IA",
        "tags": ["timercard", "ai", "attendance"],
    },
    "OpenClaudeJp": {
        "priority": "medium",
        "domain": "dev",
        "desc": "Open Claude JP — Herramientas Claude Code japones",
        "tags": ["openclaude", "claude-code", "ai", "mcp"],
    },
    "Pdf-studio-Jp26.3.30": {
        "priority": "normal",
        "domain": "dev",
        "desc": "PDF Studio JP — Generador/editor de PDFs",
        "tags": ["pdf", "tools", "templates"],
    },
    # === OPENSHAKEN (activa, modificada recientemente) ===
    "OpenShaken.v26.4.16": {
        "priority": "high",
        "domain": "business",
        "desc": "OpenShaken v26.4.16 — 車検 (vehicle inspection) app con PDF forms",
        "tags": ["shaken", "vehicle-inspection", "pdf", "dokploy", "uns-dispatch"],
    },
    # === WEB / MARKETING ===
    "Paginaweb26.3.30": {
        "priority": "normal",
        "domain": "ux",
        "desc": "Pagina web UNS — Website corporativo",
        "tags": ["paginaweb", "landing", "corporate"],
    },
    "Paginaweb26.3.30test": {
        "priority": "normal",
        "domain": "ux",
        "desc": "Pagina web UNS (test variant)",
        "tags": ["paginaweb", "landing", "test"],
    },
    "Intro3D-UNS-Kikaku": {
        "priority": "normal",
        "domain": "ux",
        "desc": "Intro 3D UNS Kikaku — Landing 3D corporativo",
        "tags": ["intro3d", "threejs", "marketing", "uns"],
    },
    # === DOCUMENTACION / KNOWLEDGE ===
    "Obsidian": {
        "priority": "high",
        "domain": "docs",
        "desc": "Vault Obsidian — Base de conocimiento del ecosistema UNS",
        "tags": ["obsidian", "vault", "knowledge-base", "notes"],
    },
    # === OPS / UTIL ===
    "BackUp-App-Jp202626.3.30": {
        "priority": "normal",
        "domain": "ops",
        "desc": "BackUp App JP — Herramienta backup automatizado",
        "tags": ["backup", "automation", "ops"],
    },
    "BorrarCarpetas26.3.30": {
        "priority": "normal",
        "domain": "ops",
        "desc": "BorrarCarpetas — Utilidad limpieza de sistema",
        "tags": ["cleanup", "automation", "ops"],
    },
    "autoriararpeta": {
        "priority": "normal",
        "domain": "ops",
        "desc": "Auto-organizador de carpetas — dashboard auditoria + export B2B",
        "tags": ["automation", "ops", "audit", "dashboard"],
    },
    # === ROBOTICS / EXPERIMENTAL ===
    "RobotUns": {
        "priority": "normal",
        "domain": "dev",
        "desc": "RobotUns — Proyecto experimental robotica / automation",
        "tags": ["robot", "experimental", "web", "automation"],
    },
    # === PROJECTS BASE ===
    "JP-v1.26.3.25-30": {
        "priority": "normal",
        "domain": "dev",
        "desc": "JP v1 — Proyecto base JP con DataTotal + audit",
        "tags": ["base-project", "jp", "audit"],
    },
    "JP-v26.3.30nousar": {
        "priority": "normal",
        "domain": "dev",
        "desc": "JP v26.3.30 (nousar) — Variante NO usar",
        "tags": ["base-project", "legacy", "unused"],
    },
    # === INFRAESTRUCTURA ===
    "mcp-server": {
        "priority": "medium",
        "domain": "infra",
        "desc": "MCP server portable — Runtime MCP standalone con gateway HTTP",
        "tags": ["mcp", "server-portable", "gateway", "runtime"],
    },
}


# ---------------------------------------------------------------------------
# Scanning de app local
# ---------------------------------------------------------------------------

IMPORTANT_FILENAMES = {
    "CLAUDE.md",
    "README.md",
    "AGENTS.md",
    "RULES.md",
    "GEMINI.md",
    "ESTADO_PROYECTO.md",
    "WORKFLOW_RULES.md",
    "SPEC.md",
    "PLAN.md",
    "package.json",
    "pyproject.toml",
    "requirements.txt",
    "Cargo.toml",
    "Dockerfile",
    "docker-compose.yml",
    ".env.example",
    "tsconfig.json",
    "vite.config.ts",
    "next.config.js",
}

MODEL_GLOBS = [
    "**/prisma/schema.prisma",
    "**/models.py",
    "**/models/*.py",
    "**/schema*.py",
    "**/types.ts",
    "**/types/*.ts",
    "**/*_model.py",
    "**/*.model.ts",
    "**/entities/*",
    "**/migrations/*.sql",
    "**/db/schema*",
    "**/*.prisma",
]

ROUTE_GLOBS = [
    "**/routes.py",
    "**/routes/*.py",
    "**/api/*.py",
    "**/api/*.ts",
    "**/app/api/**/route.ts",
    "**/pages/api/**/*.ts",
    "**/endpoints.py",
    "**/controllers/*",
]

SKIP_DIRS = {
    "node_modules",
    ".git",
    "target",
    "dist",
    "build",
    ".next",
    "venv",
    ".venv",
    "__pycache__",
    ".cache",
    "site-packages",
}


def scan_app(app_dir: Path, max_file_size: int = 50_000) -> dict:
    """Escanea un directorio de app y devuelve estructura."""
    result = {
        "exists": app_dir.exists(),
        "tech_stack": [],
        "file_count": 0,
        "top_dirs": [],
        "docs": {},
        "config": {},
        "models": {},
        "routes": {},
    }
    if not app_dir.exists():
        return result

    # Top-level dirs
    try:
        result["top_dirs"] = sorted(
            [p.name for p in app_dir.iterdir() if p.is_dir() and p.name not in SKIP_DIRS]
        )[:15]
    except PermissionError:
        pass

    # Collect files respecting skip dirs
    for p in app_dir.rglob("*"):
        if any(part in SKIP_DIRS for part in p.parts):
            continue
        if not p.is_file():
            continue
        result["file_count"] += 1
        name = p.name
        rel = p.relative_to(app_dir).as_posix()

        # Docs/config importantes en root
        if name in IMPORTANT_FILENAMES:
            try:
                if p.stat().st_size < max_file_size:
                    text = p.read_text(encoding="utf-8", errors="replace")
                    if name in {
                        "package.json",
                        "pyproject.toml",
                        "requirements.txt",
                        "Cargo.toml",
                        "Dockerfile",
                        "docker-compose.yml",
                        "tsconfig.json",
                    }:
                        result["config"][rel] = text[:2500]
                    else:
                        result["docs"][rel] = text[:2500]
            except Exception:
                pass

        # Tech detection
        if name == "package.json" and not result["tech_stack"]:
            try:
                pkg = json.loads(p.read_text(encoding="utf-8", errors="replace"))
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                for fw in (
                    "next",
                    "react",
                    "vue",
                    "svelte",
                    "vite",
                    "tauri",
                    "electron",
                    "astro",
                    "angular",
                    "express",
                    "fastify",
                ):
                    if any(fw in d for d in deps):
                        result["tech_stack"].append(fw)
            except Exception:
                pass
        elif name == "pyproject.toml":
            result["tech_stack"].append("python")
        elif name == "Cargo.toml":
            result["tech_stack"].append("rust")
        elif name == "Dockerfile":
            if "docker" not in result["tech_stack"]:
                result["tech_stack"].append("docker")

    # Models & routes
    for glob_pat in MODEL_GLOBS:
        for m in app_dir.glob(glob_pat):
            if any(part in SKIP_DIRS for part in m.parts):
                continue
            if m.is_file() and m.stat().st_size < max_file_size:
                try:
                    rel = m.relative_to(app_dir).as_posix()
                    result["models"][rel] = m.read_text(encoding="utf-8", errors="replace")[:2500]
                    if len(result["models"]) >= 5:
                        break
                except Exception:
                    pass
        if len(result["models"]) >= 5:
            break

    for glob_pat in ROUTE_GLOBS:
        for r in app_dir.glob(glob_pat):
            if any(part in SKIP_DIRS for part in r.parts):
                continue
            if r.is_file() and r.stat().st_size < max_file_size:
                try:
                    rel = r.relative_to(app_dir).as_posix()
                    result["routes"][rel] = r.read_text(encoding="utf-8", errors="replace")[:2000]
                    if len(result["routes"]) >= 5:
                        break
                except Exception:
                    pass
        if len(result["routes"]) >= 5:
            break

    return result


def compute_scan_hash(scan: dict) -> str:
    """Hash estable del contenido scaneado."""
    payload = json.dumps(
        {
            "tech": sorted(scan["tech_stack"]),
            "file_count": scan["file_count"],
            "docs": {k: v[:500] for k, v in scan["docs"].items()},
            "config": {k: v[:500] for k, v in scan["config"].items()},
            "models": list(scan["models"].keys()),
            "routes": list(scan["routes"].keys()),
        },
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Generacion de nodos
# ---------------------------------------------------------------------------


def make_nodes(app_name: str, info: dict, scan: dict) -> list[dict]:
    """Genera los nodos de conocimiento para una app."""
    _slug_base = app_name.lower().replace("_", "-").replace(".", "-")
    tags = info["tags"] + ["matrix-absorb-local", "auto-ingested"]
    importance = {"high": "high", "medium": "normal", "normal": "normal"}[info["priority"]]
    content_hash = compute_scan_hash(scan)

    nodes = []

    # 1) Resumen / estructura
    docs_sample = "\n\n".join(
        f"### {path}\n{text[:800]}" for path, text in list(scan["docs"].items())[:3]
    )
    context = (
        f"**App**: {app_name}\n"
        f"**Descripcion**: {info['desc']}\n"
        f"**Dominio**: {info['domain']}\n"
        f"**Prioridad**: {info['priority']}\n"
        f"**Stack detectado**: {', '.join(scan['tech_stack']) or 'desconocido'}\n"
        f"**Archivos totales**: {scan['file_count']}\n"
        f"**Top-level dirs**: {', '.join(scan['top_dirs'][:10])}\n\n"
        f"### Docs extraidos\n\n{docs_sample}"
    )
    nodes.append(
        {
            "title": f"{app_name} — App local (matrix absorb)",
            "context": context,
            "area": info["domain"],
            "tags": tags + ["local-scan", "structure"],
            "importance": importance,
            "node_type": "entity",
            "source_notes": f"scan_hash: {content_hash}\npath: {app_name}",
        }
    )

    # 2) Modelos de datos
    if scan["models"]:
        model_ctx = "\n\n".join(
            f"### {path}\n```\n{text[:1500]}\n```"
            for path, text in list(scan["models"].items())[:5]
        )
        nodes.append(
            {
                "title": f"{app_name} — Modelos de datos (local scan)",
                "context": model_ctx,
                "area": info["domain"],
                "tags": tags + ["models", "database", "schema"],
                "importance": importance,
                "node_type": "concept",
                "source_notes": f"scan_hash: {content_hash}",
            }
        )

    # 3) Endpoints / rutas
    if scan["routes"]:
        route_ctx = "\n\n".join(
            f"### {path}\n```\n{text[:1500]}\n```"
            for path, text in list(scan["routes"].items())[:5]
        )
        nodes.append(
            {
                "title": f"{app_name} — Endpoints y rutas (local scan)",
                "context": route_ctx,
                "area": info["domain"],
                "tags": tags + ["routes", "api", "endpoints"],
                "importance": importance,
                "node_type": "concept",
                "source_notes": f"scan_hash: {content_hash}",
            }
        )

    # 4) Config / dependencias
    if scan["config"]:
        cfg_ctx = "\n\n".join(
            f"### {path}\n```\n{text[:1200]}\n```"
            for path, text in list(scan["config"].items())[:4]
        )
        nodes.append(
            {
                "title": f"{app_name} — Config y dependencias (local scan)",
                "context": cfg_ctx,
                "area": "dev",
                "tags": tags + ["config", "dependencies"],
                "importance": "normal",
                "node_type": "session",
                "source_notes": f"scan_hash: {content_hash}",
            }
        )

    return nodes


# ---------------------------------------------------------------------------
# Dedupe check
# ---------------------------------------------------------------------------


def already_absorbed(brain: Brain, app_name: str) -> set[str]:
    """Retorna slugs existentes que referencian esta app (via matrix-absorb-local)."""
    slugs = set()
    app_lc = app_name.lower()
    for d in (brain.sessions_dir, brain.concepts_dir):
        for p in d.glob("*.md"):
            name_lc = p.stem.lower()
            if app_lc in name_lc or app_lc.replace(".", "-") in name_lc:
                slugs.add(p.stem)
    return slugs


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(description="Local Matrix Absorb")
    parser.add_argument("--only", help="Nombre de app especifico")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--missing-only", action="store_true", help="Solo apps sin nodos 'local-scan' previos"
    )
    parser.add_argument(
        "--skip-large",
        type=int,
        default=5000,
        help="Saltar apps con mas de N archivos (default 5000)",
    )
    args = parser.parse_args()

    brain = Brain(BRAIN_DIR, app_id="nexus-mother")

    to_process = (
        list(APPS.items())
        if not args.only
        else [(args.only, APPS[args.only])]
        if args.only in APPS
        else []
    )

    if not to_process:
        logger.error("No apps to process. --only=%s no esta en el catalogo", args.only)
        sys.exit(1)

    total_nodes = 0
    skipped = 0
    processed = 0

    for app_name, info in to_process:
        app_dir = LOCAL_APPS_ROOT / app_name
        logger.info("=== %s ===", app_name)

        if not app_dir.exists():
            logger.warning("  Path no existe: %s", app_dir)
            skipped += 1
            continue

        # Check existentes
        existing = already_absorbed(brain, app_name)
        if args.missing_only and existing:
            logger.info("  Skip (ya tiene %d nodos previos)", len(existing))
            skipped += 1
            continue

        # Scan
        scan = scan_app(app_dir)
        if scan["file_count"] > args.skip_large:
            logger.warning("  Skip (file_count=%d > %d)", scan["file_count"], args.skip_large)
            skipped += 1
            continue
        if scan["file_count"] == 0:
            logger.warning("  Skip (vacio)")
            skipped += 1
            continue

        logger.info(
            "  Files=%d Tech=%s Models=%d Routes=%d Docs=%d",
            scan["file_count"],
            scan["tech_stack"],
            len(scan["models"]),
            len(scan["routes"]),
            len(scan["docs"]),
        )

        nodes = make_nodes(app_name, info, scan)

        if args.dry_run:
            for n in nodes:
                logger.info("  [dry] %s — tags=%s", n["title"], n["tags"][:5])
            continue

        for node_data in nodes:
            brain.ingest(**node_data)
        total_nodes += len(nodes)
        processed += 1

    if not args.dry_run:
        brain.rebuild_index()

    logger.info(
        "=== DONE: procesados=%d skipped=%d nodos_nuevos=%d ===", processed, skipped, total_nodes
    )


if __name__ == "__main__":
    main()
