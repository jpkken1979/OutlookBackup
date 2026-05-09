#!/usr/bin/env python3
"""
Plan Maestro: Deep Knowledge Absorption — Absorber conocimiento COMPLETO de cada repo.

Para cada repo del ecosistema UNS:
1. Clonar el repo (shallow clone para velocidad)
2. Mapear estructura completa (archivos, directorios, tamaños)
3. Leer código fuente clave:
   - Modelos/schemas (DB tables, types, interfaces)
   - Routes/endpoints (API, pages)
   - Components (UI)
   - Config (package.json, requirements.txt, .env.example)
   - Business logic (services, utils, helpers)
4. Generar nodos de conocimiento POR FUNCIONALIDAD (no por archivo)
5. Ingestar en el Brain con cross-refs

Uso:
    python master_plan_absorb.py jpkken1979/KobetsuVsKonetsu.v3.26.4.7
    python master_plan_absorb.py --all          # Todos los repos
    python master_plan_absorb.py --priority     # Solo alta prioridad
"""

import json
import logging
import os
import shutil
import subprocess
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("GH_TOKEN", "")
AGENT_DIR = Path(__file__).parent.parent
CLONE_DIR = Path("/tmp/brain-absorb")

sys.path.insert(0, str(AGENT_DIR))
from core.brain import Brain

# ---------------------------------------------------------------------------
# Repos clasificados por prioridad y dominio
# ---------------------------------------------------------------------------

REPOS = {
    # ALTA PRIORIDAD — Apps core del negocio UNS
    "jpkken1979/KobetsuVsKonetsu.v3.26.4.7": {
        "priority": "high",
        "domain": "business",
        "desc": "個別契約書 v3 — Generador de contratos individuales de dispatch",
        "focus": ["models", "templates", "pdf-generation", "employee-data"],
    },
    "jpkken1979/Kobetsuv2.26.4.1": {
        "priority": "high",
        "domain": "business",
        "desc": "個別契約書 v2 — Version anterior del generador de contratos",
        "focus": ["models", "templates", "differences-vs-v3"],
    },
    "jpkken1979/Chingiv7.026.3.30": {
        "priority": "high",
        "domain": "business",
        "desc": "賃金台帳 v7 — Registro maestro de salarios (Daicho)",
        "focus": ["salary-calc", "models", "reports", "tax-deductions"],
    },
    "jpkken1979/Arari-PROv5.026.3.30": {
        "priority": "high",
        "domain": "business",
        "desc": "粗利 PRO v5 — Calculo de margen bruto por trabajador dispatch",
        "focus": ["profit-calc", "models", "reports", "billing"],
    },
    "jpkken1979/KintaiFlow1.0v26.3.30": {
        "priority": "high",
        "domain": "business",
        "desc": "勤怠 Flow — Sistema de control de asistencia/horas",
        "focus": ["attendance", "timecard", "shifts", "overtime"],
    },
    "jpkken1979/JpRirekiUltimate26.3.30": {
        "priority": "high",
        "domain": "business",
        "desc": "履歴書 Ultimate — Generador de CV japones",
        "focus": ["cv-template", "pdf", "employee-profile"],
    },
    "jpkken1979/YukyuData-AppFusion2.1626.3.30": {
        "priority": "high",
        "domain": "business",
        "desc": "有給 Data — Gestion de vacaciones pagadas",
        "focus": ["vacation-calc", "balance", "accrual-rules"],
    },
    # MEDIA PRIORIDAD — Apps soporte
    "jpkken1979/KintaiKyuryouv2.026.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "勤怠給料 v2 — Asistencia + calculo de salarios",
        "focus": ["attendance-salary-link", "payroll"],
    },
    "jpkken1979/Kashitsuke-UNSv1.026.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "貸付 UNS — Sistema de prestamos a empleados",
        "focus": ["loan-management", "deductions", "repayment"],
    },
    "jpkken1979/tiravisas-master26.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "ビザ — Control de visas de trabajadores extranjeros",
        "focus": ["visa-tracking", "expiration", "renewal"],
    },
    "jpkken1979/UNS-System-JpNyushaTaisha26.3.30": {
        "priority": "medium",
        "domain": "business",
        "desc": "入社退社 — Registro de altas y bajas de empleados",
        "focus": ["onboarding", "offboarding", "employee-lifecycle"],
    },
    "jpkken1979/CodexBar-mainJp26.3.30": {
        "priority": "medium",
        "domain": "dev",
        "desc": "Codex Bar — Herramienta CLI/desktop con IA",
        "focus": ["cli", "ai-integration", "tools"],
    },
    "jpkken1979/OpenClaudeJp": {
        "priority": "medium",
        "domain": "dev",
        "desc": "Open Claude JP — Herramientas Claude Code",
        "focus": ["claude-tools", "mcp", "ai"],
    },
    "jpkken1979/Obsidian": {
        "priority": "medium",
        "domain": "docs",
        "desc": "Vault Obsidian — Base de conocimiento personal/empresa",
        "focus": ["notes", "templates", "adr", "knowledge-base"],
    },
    "jpkken1979/BackUp-App-Jp202626.3.30": {
        "priority": "medium",
        "domain": "ops",
        "desc": "Backup App — Herramienta de backup automatizado",
        "focus": ["backup-logic", "scheduling", "targets"],
    },
    # NORMAL PRIORIDAD — Apps complementarias
    "jpkken1979/opus46apartementos26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Apartamentos — Gestion de propiedades para trabajadores",
        "focus": ["property-management", "tenants"],
    },
    "jpkken1979/uns-kobetsu26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Kobetsu web — Version web del generador de contratos",
        "focus": ["web-app", "api"],
    },
    "jpkken1979/uns-apartment26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Apartment web — Version web gestion de apartamentos",
        "focus": ["web-app", "api"],
    },
    "jpkken1979/TimercardStudioIA26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Timercard Studio IA — Control horario con IA",
        "focus": ["timecard", "ai-features"],
    },
    "jpkken1979/APaginaweb26.3.27": {
        "priority": "normal",
        "domain": "ux",
        "desc": "Pagina web UNS — Website corporativo",
        "focus": ["landing", "services", "contact"],
    },
    "jpkken1979/Paginaweb26.3.30": {
        "priority": "normal",
        "domain": "ux",
        "desc": "Pagina web v2 — Website corporativo actualizado",
        "focus": ["landing", "services"],
    },
    "jpkken1979/Pdf-studio-Jp26.3.30": {
        "priority": "normal",
        "domain": "dev",
        "desc": "PDF Studio — Generador/editor de PDFs",
        "focus": ["pdf-tools", "templates"],
    },
    "jpkken1979/BorrarCarpetas26.3.30": {
        "priority": "normal",
        "domain": "ops",
        "desc": "Borrar Carpetas — Utilidad de limpieza",
        "focus": ["cleanup", "automation"],
    },
    "jpkken1979/Arari-PROv2.0_Dokploy26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Arari PRO v2 Dokploy — Version deployable del calculo de margenes",
        "focus": ["deploy", "docker", "profit-calc"],
    },
    "jpkken1979/JpRireki-app1.0v26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Rirekisho App v1 — Generador de CV primera version",
        "focus": ["cv", "pdf"],
    },
    "jpkken1979/JpRireki-Shain-unifi26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Rirekisho Shain Unificado — CV + datos de empleado unificados",
        "focus": ["employee-data", "cv-unified"],
    },
    "jpkken1979/RirekishoDBaseAntigua26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Rirekisho DBase Antigua — Base de datos historica de CVs",
        "focus": ["legacy-data", "migration"],
    },
    "jpkken1979/CodeXCATimerCard26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Codex CA TimerCard — Control horario con Codex",
        "focus": ["timecard", "codex-integration"],
    },
    "jpkken1979/-core-win-v1.0.0.26.4.6": {
        "priority": "normal",
        "domain": "dev",
        "desc": "Core Win — Modulo core en Go para Windows",
        "focus": ["go", "windows", "core-module"],
    },
    "jpkken1979/Opus4.6Apartementos26.3.30": {
        "priority": "normal",
        "domain": "business",
        "desc": "Apartamentos Opus 4.6 — Gestion propiedades version Opus",
        "focus": ["property", "tenants"],
    },
    "jpkken1979/Jpkken1979-JP-v1.26.3.25-30": {
        "priority": "normal",
        "domain": "dev",
        "desc": "JP v1 — Proyecto base JP",
        "focus": ["base-project"],
    },
    "jpkken1979/JP-v26.3.30": {
        "priority": "normal",
        "domain": "dev",
        "desc": "JP — Proyecto JP actualizado",
        "focus": ["base-project"],
    },
    "jpkken1979/P-v26.3.30": {
        "priority": "normal",
        "domain": "dev",
        "desc": "P — Proyecto P",
        "focus": ["project"],
    },
    "jpkken1979/-26.1.27V26.3.30": {
        "priority": "normal",
        "domain": "dev",
        "desc": "Proyecto legacy 26.1.27",
        "focus": ["legacy"],
    },
    "jpkken1979/Jp79-YukyuData-AppFusion2.16": {
        "priority": "normal",
        "domain": "business",
        "desc": "Yukyu Data Fusion legacy — Version anterior",
        "focus": ["vacation", "legacy"],
    },
}


def clone_repo(full_name: str) -> Path | None:
    """Clona un repo (shallow) en /tmp/brain-absorb/."""
    repo_dir = CLONE_DIR / full_name.split("/")[1]
    if repo_dir.exists():
        shutil.rmtree(repo_dir)

    url = (
        f"https://{TOKEN}@github.com/{full_name}.git"
        if TOKEN
        else f"https://github.com/{full_name}.git"
    )
    try:
        subprocess.run(
            ["git", "clone", "--depth=1", url, str(repo_dir)],
            capture_output=True,
            timeout=60,
            check=True,
        )
        return repo_dir
    except Exception as e:
        logger.error("Clone failed %s: %s", full_name, e)
        return None


def analyze_structure(repo_dir: Path) -> dict:
    """Analiza la estructura completa del repo."""
    structure = {"dirs": [], "files": [], "by_ext": {}}

    for p in repo_dir.rglob("*"):
        if ".git" in p.parts:
            continue
        rel = str(p.relative_to(repo_dir))
        if p.is_dir():
            structure["dirs"].append(rel)
        elif p.is_file():
            ext = p.suffix.lower()
            structure["by_ext"].setdefault(ext, []).append(rel)
            structure["files"].append(rel)

    return structure


def read_key_files(repo_dir: Path, structure: dict, focus: list) -> dict:
    """Lee archivos clave segun el tipo de proyecto."""
    content = {}

    # Patrones de archivos importantes por tipo
    patterns = {
        "models": [
            "**/model*",
            "**/schema*",
            "**/types*",
            "**/entity*",
            "**/*_model*",
            "**/migrations/*",
            "**/prisma/schema*",
            "**/db*",
        ],
        "routes": [
            "**/route*",
            "**/api*",
            "**/endpoint*",
            "**/controller*",
            "**/pages/*",
            "**/app/**/page*",
        ],
        "components": ["**/component*", "**/features/*", "**/views/*", "**/panels/*"],
        "config": [
            "package.json",
            "pyproject.toml",
            "requirements*.txt",
            "Cargo.toml",
            ".env.example",
            "docker*",
            "tsconfig*",
        ],
        "services": [
            "**/service*",
            "**/util*",
            "**/helper*",
            "**/lib/*",
            "**/core/*",
            "**/logic*",
            "**/calc*",
        ],
        "templates": ["**/template*", "**/jinja*", "**/*.html", "**/*.ejs"],
        "docs": ["**/*.md"],
    }

    for category, globs in patterns.items():
        for glob_pattern in globs:
            for match in repo_dir.glob(glob_pattern):
                if ".git" in match.parts or "node_modules" in match.parts:
                    continue
                if match.is_file() and match.stat().st_size < 50000:  # Max 50KB
                    try:
                        text = match.read_text(encoding="utf-8", errors="replace")
                        rel = str(match.relative_to(repo_dir))
                        content.setdefault(category, {})[rel] = text[:3000]
                    except Exception:
                        pass

    return content


def generate_knowledge_nodes(
    full_name: str,
    repo_info: dict,
    structure: dict,
    key_files: dict,
) -> list[dict]:
    """Genera nodos de conocimiento a partir del analisis."""
    repo_name = full_name.split("/")[1]
    nodes = []

    # Nodo 1: Resumen y estructura
    dir_summary = ", ".join(structure["dirs"][:20])
    ext_summary = {k: len(v) for k, v in structure["by_ext"].items()}
    nodes.append(
        {
            "title": f"{repo_name} — Estructura y tecnologias",
            "context": (
                f"Repo: {full_name}\n"
                f"Descripcion: {repo_info['desc']}\n"
                f"Archivos: {len(structure['files'])} total\n"
                f"Extensiones: {json.dumps(ext_summary)}\n"
                f"Directorios principales: {dir_summary}"
            ),
            "area": repo_info["domain"],
            "tags": [repo_name.lower(), "estructura", repo_info["domain"]],
            "importance": "high" if repo_info["priority"] == "high" else "normal",
            "node_type": "entity",
        }
    )

    # Nodo 2: Modelos y datos (si existen)
    if "models" in key_files:
        model_summary = []
        for path, content in list(key_files["models"].items())[:5]:
            model_summary.append(f"### {path}\n{content[:600]}")
        if model_summary:
            nodes.append(
                {
                    "title": f"{repo_name} — Modelos de datos y schemas",
                    "context": "\n\n".join(model_summary),
                    "area": repo_info["domain"],
                    "tags": [repo_name.lower(), "models", "database", "schema"],
                    "importance": "high",
                    "node_type": "concept",
                }
            )

    # Nodo 3: Rutas y endpoints (si existen)
    if "routes" in key_files:
        route_summary = []
        for path, content in list(key_files["routes"].items())[:5]:
            route_summary.append(f"### {path}\n{content[:600]}")
        if route_summary:
            nodes.append(
                {
                    "title": f"{repo_name} — Rutas y endpoints",
                    "context": "\n\n".join(route_summary),
                    "area": repo_info["domain"],
                    "tags": [repo_name.lower(), "routes", "api", "endpoints"],
                    "importance": "normal",
                    "node_type": "concept",
                }
            )

    # Nodo 4: Logica de negocio/servicios
    if "services" in key_files:
        svc_summary = []
        for path, content in list(key_files["services"].items())[:5]:
            svc_summary.append(f"### {path}\n{content[:600]}")
        if svc_summary:
            nodes.append(
                {
                    "title": f"{repo_name} — Logica de negocio",
                    "context": "\n\n".join(svc_summary),
                    "area": repo_info["domain"],
                    "tags": [repo_name.lower(), "business-logic", "services"],
                    "importance": "high" if repo_info["domain"] == "business" else "normal",
                    "node_type": "concept",
                }
            )

    # Nodo 5: Config y dependencias
    if "config" in key_files:
        cfg_summary = []
        for path, content in list(key_files["config"].items())[:3]:
            cfg_summary.append(f"### {path}\n{content[:500]}")
        if cfg_summary:
            nodes.append(
                {
                    "title": f"{repo_name} — Configuracion y dependencias",
                    "context": "\n\n".join(cfg_summary),
                    "area": "dev",
                    "tags": [repo_name.lower(), "config", "dependencies"],
                    "importance": "normal",
                    "node_type": "session",
                }
            )

    return nodes


def absorb_repo(full_name: str, brain: Brain) -> int:
    """Proceso completo de absorcion de un repo."""
    repo_info = REPOS.get(full_name)
    if not repo_info:
        logger.warning("Repo %s no esta en el catalogo", full_name)
        return 0

    logger.info("=== Absorbing %s ===", full_name)

    # 1. Clonar
    repo_dir = clone_repo(full_name)
    if not repo_dir:
        return 0

    # 2. Analizar estructura
    structure = analyze_structure(repo_dir)
    logger.info("  %d archivos, %d directorios", len(structure["files"]), len(structure["dirs"]))

    # 3. Leer archivos clave
    key_files = read_key_files(repo_dir, structure, repo_info["focus"])
    categories = {k: len(v) for k, v in key_files.items()}
    logger.info("  Key files: %s", categories)

    # 4. Generar nodos
    nodes = generate_knowledge_nodes(full_name, repo_info, structure, key_files)
    logger.info("  %d nodos generados", len(nodes))

    # 5. Ingestar
    for node_data in nodes:
        brain.ingest(**node_data)

    # 6. Cleanup
    shutil.rmtree(repo_dir, ignore_errors=True)

    return len(nodes)


def main() -> None:
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Deep Knowledge Absorption")
    parser.add_argument("repo", nargs="?", help="Repo full_name (e.g. jpkken1979/Kobetsu...)")
    parser.add_argument("--all", action="store_true", help="Absorber todos los repos")
    parser.add_argument(
        "--priority",
        choices=["high", "medium", "normal"],
        help="Absorber solo repos de esta prioridad",
    )
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar plan")
    args = parser.parse_args()

    CLONE_DIR.mkdir(parents=True, exist_ok=True)
    brain = Brain(Path(".agent/brain"), app_id="nexus-mother")

    if args.repo:
        repos_to_process = [args.repo]
    elif args.all:
        repos_to_process = list(REPOS.keys())
    elif args.priority:
        repos_to_process = [r for r, info in REPOS.items() if info["priority"] == args.priority]
    else:
        repos_to_process = [r for r, info in REPOS.items() if info["priority"] == "high"]

    if args.dry_run:
        for r in repos_to_process:
            info = REPOS.get(r, {})
            print(f"  {r}: {info.get('desc', '?')} [{info.get('priority', '?')}]")
        print(f"\nTotal: {len(repos_to_process)} repos")
        return

    total_nodes = 0
    for repo in repos_to_process:
        n = absorb_repo(repo, brain)
        total_nodes += n

    brain.rebuild_index()
    logger.info("=== DONE: %d repos, %d nodos nuevos ===", len(repos_to_process), total_nodes)


if __name__ == "__main__":
    main()
