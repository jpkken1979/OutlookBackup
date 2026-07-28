#!/usr/bin/env python3
"""
Discover External Agents & Skills — escanea el sistema buscando agentes y skills
instalados en otros proyectos y los importa al ecosistema OpenAntigravity.

Modos:
    scan   — Escanea y muestra lo que encontró (sin modificar nada)
    import — Copia skills/agentes nuevos a OpenAntigravity (sin sobrescribir)
    inject — Usado por mcp_injector.py para adicionar al proyecto destino

Uso:
    python .agent/scripts/discover_external.py scan
    python .agent/scripts/discover_external.py scan --paths ~/Projects ~/Work
    python .agent/scripts/discover_external.py import
    python .agent/scripts/discover_external.py import --dry-run

v1.0.0 - 2026-03-09
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import shutil
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("antigravity.discover")

# Marcadores que confirman que un directorio es un proyecto real
_PROJECT_MARKERS = (".git", "pyproject.toml", "package.json", "Cargo.toml")


def _validate_target_dir(target_dir: Path) -> bool:
    """Valida que target_dir sea un directorio de proyecto real y seguro.

    Verifica tres condiciones:
    1. La ruta es absoluta (evita rutas relativas garbled que se resuelven en cwd).
    2. El directorio existe en disco.
    3. Contiene al menos un marcador de proyecto conocido (.git, pyproject.toml,
       package.json o Cargo.toml) para confirmar que es un proyecto real.

    Args:
        target_dir: Path del directorio destino a validar.

    Returns:
        True si el directorio pasa todas las comprobaciones, False en caso contrario.
    """
    if not target_dir.is_absolute():
        logger.warning(
            "[validate_target_dir] Ruta relativa rechazada: %r — usar ruta absoluta",
            str(target_dir),
        )
        return False
    if not target_dir.exists():
        logger.warning("[validate_target_dir] Directorio no existe: %r", str(target_dir))
        return False
    if not any((target_dir / marker).exists() for marker in _PROJECT_MARKERS):
        logger.warning(
            "[validate_target_dir] Directorio no parece un proyecto real (sin marcadores): %r",
            str(target_dir),
        )
        return False
    return True


# Root del ecosistema
SCRIPT_DIR = Path(__file__).resolve().parent
OA_ROOT = SCRIPT_DIR.parent.parent
OA_AGENTS = OA_ROOT / ".agent" / "agents"
OA_SKILLS = OA_ROOT / ".agent" / "skills"
OA_SKILLS_CUSTOM = OA_ROOT / ".agent" / "skills-custom"

# Rutas por defecto donde buscar proyectos
DEFAULT_SCAN_PATHS = [
    Path.home(),
]


def _default_scan_paths() -> list[Path]:
    """Build default scan paths with optional env override."""
    env_paths = os.environ.get("OPENANTIGRAVITY_SCAN_PATHS", "").strip()
    candidates: list[Path] = []
    if env_paths:
        for raw in env_paths.split(os.pathsep):
            cleaned = raw.strip()
            if cleaned:
                candidates.append(Path(cleaned).expanduser())
    candidates.extend(DEFAULT_SCAN_PATHS)

    unique: list[Path] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = str(candidate.resolve()) if candidate.exists() else str(candidate)
        if key not in seen:
            seen.add(key)
            unique.append(candidate)
    return unique


def find_agent_dirs(scan_paths: list[Path]) -> list[Path]:
    """Busca directorios .agent/ en los paths especificados (max depth 4)."""
    results: list[Path] = []
    for base in scan_paths:
        if not base.exists():
            continue
        # Max depth 4
        for depth in range(1, 5):
            pattern = "/".join(["*"] * depth) + "/.agent"
            for match in base.glob(pattern):
                if match.is_dir() and match.resolve() != (OA_ROOT / ".agent").resolve():
                    results.append(match)
    # Deduplicate by resolved path
    seen: set[str] = set()
    unique: list[Path] = []
    for p in results:
        key = str(p.resolve())
        if key not in seen:
            seen.add(key)
            unique.append(p)
    return sorted(unique)


def scan_external(
    scan_paths: list[Path],
) -> dict[str, list[dict[str, str]]]:
    """Escanea y retorna agentes/skills externos que no existen en OA."""
    external_dirs = find_agent_dirs(scan_paths)
    logger.info("Encontrados %d directorios .agent/ externos", len(external_dirs))

    # Inventario actual de OA
    oa_agents = {d.name for d in OA_AGENTS.iterdir() if d.is_dir() and not d.name.startswith("_")}
    oa_skills = {d.name for d in OA_SKILLS.iterdir() if d.is_dir()} if OA_SKILLS.exists() else set()
    oa_skills_custom = (
        {d.name for d in OA_SKILLS_CUSTOM.iterdir() if d.is_dir()}
        if OA_SKILLS_CUSTOM.exists()
        else set()
    )
    all_skills = oa_skills | oa_skills_custom

    new_agents: list[dict[str, str]] = []
    new_skills: list[dict[str, str]] = []
    seen_agents: set[str] = set()
    seen_skills: set[str] = set()

    for ext_dir in external_dirs:
        project_name = ext_dir.parent.name

        # Scan agents
        agents_dir = ext_dir / "agents"
        if agents_dir.exists():
            for agent_dir in sorted(agents_dir.iterdir()):
                if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
                    continue
                if agent_dir.name.endswith(".md"):
                    continue
                if agent_dir.name not in oa_agents and agent_dir.name not in seen_agents:
                    has_identity = (agent_dir / "IDENTITY.md").exists()
                    new_agents.append(
                        {
                            "name": agent_dir.name,
                            "source": str(agent_dir),
                            "project": project_name,
                            "has_identity": str(has_identity),
                        }
                    )
                    seen_agents.add(agent_dir.name)

        # Scan skills and skills-custom
        for skills_subdir in ["skills", "skills-custom"]:
            skills_dir = ext_dir / skills_subdir
            if not skills_dir.exists():
                continue
            for skill_dir in sorted(skills_dir.iterdir()):
                if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                    continue
                if skill_dir.name.endswith(".md") or skill_dir.name.endswith(".json"):
                    continue
                if skill_dir.name not in all_skills and skill_dir.name not in seen_skills:
                    has_skill_md = (skill_dir / "SKILL.md").exists()
                    new_skills.append(
                        {
                            "name": skill_dir.name,
                            "source": str(skill_dir),
                            "project": project_name,
                            "has_skill_md": str(has_skill_md),
                            "subdir": skills_subdir,
                        }
                    )
                    seen_skills.add(skill_dir.name)

    return {"agents": new_agents, "skills": new_skills}


def import_external(
    scan_paths: list[Path],
    dry_run: bool = False,
) -> dict[str, int]:
    """Importa agentes/skills externos a OpenAntigravity sin sobrescribir."""
    result = scan_external(scan_paths)
    imported_agents = 0
    imported_skills = 0

    for agent in result["agents"]:
        src = Path(agent["source"])
        dst = OA_AGENTS / agent["name"]
        if dst.exists():
            logger.debug("Agente %s ya existe, skipping", agent["name"])
            continue
        if dry_run:
            logger.info("[DRY-RUN] Copiaría agente: %s <- %s", agent["name"], agent["project"])
        else:
            shutil.copytree(src, dst)
            logger.info("Importado agente: %s <- %s", agent["name"], agent["project"])
        imported_agents += 1

    for skill in result["skills"]:
        src = Path(skill["source"])
        # Skills externas van a skills-custom para no mezclar con las base
        dst = OA_SKILLS_CUSTOM / skill["name"]
        if dst.exists():
            logger.debug("Skill %s ya existe, skipping", skill["name"])
            continue
        if dry_run:
            logger.info("[DRY-RUN] Copiaría skill: %s <- %s", skill["name"], skill["project"])
        else:
            shutil.copytree(src, dst)
            logger.info("Importada skill: %s <- %s", skill["name"], skill["project"])
        imported_skills += 1

    return {"agents": imported_agents, "skills": imported_skills}


def additive_inject(
    target_dir: Path,
    dry_run: bool = False,
) -> dict[str, int]:
    """Inyecta agentes/skills de OA en el proyecto destino SIN borrar lo existente.

    Usado por mcp_injector.py para adicionar contenido.
    """
    if not _validate_target_dir(target_dir):
        return {}
    target_agents = target_dir / ".agent" / "agents"
    target_skills = target_dir / ".agent" / "skills"
    target_skills_custom = target_dir / ".agent" / "skills-custom"

    added_agents = 0
    added_skills = 0

    # Copiar agentes que no existen en el destino
    if OA_AGENTS.exists():
        target_agents.mkdir(parents=True, exist_ok=True)
        for agent_dir in sorted(OA_AGENTS.iterdir()):
            if not agent_dir.is_dir() or agent_dir.name.startswith("_"):
                continue
            dst = target_agents / agent_dir.name
            if dst.exists():
                continue
            if dry_run:
                logger.info("[DRY-RUN] Adicionaría agente: %s", agent_dir.name)
            else:
                shutil.copytree(agent_dir, dst)
            added_agents += 1

    # Copiar skills-custom que no existen en el destino
    if OA_SKILLS_CUSTOM.exists():
        target_skills_custom.mkdir(parents=True, exist_ok=True)
        for skill_dir in sorted(OA_SKILLS_CUSTOM.iterdir()):
            if not skill_dir.is_dir():
                continue
            dst = target_skills_custom / skill_dir.name
            if dst.exists():
                continue
            if dry_run:
                logger.info("[DRY-RUN] Adicionaría skill-custom: %s", skill_dir.name)
            else:
                shutil.copytree(skill_dir, dst)
            added_skills += 1

    # Copiar skills base que no existen en el destino
    if OA_SKILLS.exists():
        target_skills.mkdir(parents=True, exist_ok=True)
        for skill_dir in sorted(OA_SKILLS.iterdir()):
            if not skill_dir.is_dir():
                continue
            dst = target_skills / skill_dir.name
            if dst.exists():
                continue
            if dry_run:
                logger.info("[DRY-RUN] Adicionaría skill: %s", skill_dir.name)
            else:
                shutil.copytree(skill_dir, dst)
            added_skills += 1

    return {"agents": added_agents, "skills": added_skills}


def main() -> None:
    """Entry point."""
    parser = argparse.ArgumentParser(
        description="Descubre e importa agentes/skills externos al ecosistema"
    )
    parser.add_argument(
        "action",
        choices=["scan", "import", "inject"],
        help="scan: mostrar hallazgos | import: copiar a OA | inject: adicionar a proyecto destino",
    )
    parser.add_argument(
        "--paths",
        nargs="+",
        type=Path,
        default=None,
        help="Rutas donde buscar proyectos con .agent/ (default: ~/)",
    )
    parser.add_argument(
        "--target",
        type=Path,
        default=None,
        help="Directorio destino (solo para inject)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Solo mostrar qué haría, sin copiar",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Output en formato JSON",
    )

    args = parser.parse_args()
    scan_paths = args.paths or _default_scan_paths()

    if args.action == "scan":
        result = scan_external(scan_paths)
        if args.json_output:
            print(json.dumps(result, indent=2, ensure_ascii=False))
        else:
            print(f"\nAgentes externos encontrados: {len(result['agents'])}")
            for a in result["agents"]:
                identity = "Y" if a["has_identity"] == "True" else "N"
                print(f"  [{identity}] {a['name']}  (de: {a['project']})")
            print(f"\nSkills externas encontradas: {len(result['skills'])}")
            for s in result["skills"]:
                skill_md = "Y" if s["has_skill_md"] == "True" else "N"
                print(f"  [{skill_md}] {s['name']}  (de: {s['project']})")

    elif args.action == "import":
        counts = import_external(scan_paths, dry_run=args.dry_run)
        prefix = "[DRY-RUN] " if args.dry_run else ""
        print(f"\n{prefix}Importados: {counts['agents']} agentes, {counts['skills']} skills")

    elif args.action == "inject":
        if not args.target:
            parser.error("--target es requerido para inject")
        counts = additive_inject(args.target, dry_run=args.dry_run)
        prefix = "[DRY-RUN] " if args.dry_run else ""
        print(f"\n{prefix}Adicionados: {counts['agents']} agentes, {counts['skills']} skills")


if __name__ == "__main__":
    main()
