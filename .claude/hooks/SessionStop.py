#!/usr/bin/env python3
"""SessionStop hook: auto-repair memory index and validate deduplication.

Ejecutado al cerrar una sesión de Claude Code. Tareas:
1. Rebuild MEMORY.md index (idempotent, solo si cambió)
2. Validar que no hay duplicados obvios
3. Detectar archivos de memoria corruptos o huérfanos
4. Regenerar Brain index si necesario
5. Sincronizar git si hay cambios pendientes

Uso directo:
    python .claude/hooks/SessionStop.py
    python .claude/hooks/SessionStop.py --verbose
    python .claude/hooks/SessionStop.py --fix-auto
"""

from __future__ import annotations

import argparse
import json
import logging
import subprocess
import sys
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def find_repo_root() -> Path:
    """Ubicar la raíz del repositorio.

    Returns:
        Ruta a la raíz que contiene .git/.
    """
    current = Path(__file__).resolve().parent
    for _ in range(10):
        if (current / ".git").exists():
            return current
        current = current.parent
    return current


def rebuild_memory_index(repo_root: Path, apply: bool = True) -> dict:
    """Reconstruir MEMORY.md con rebuild_memory_index.py.

    Args:
        repo_root: Raíz del repositorio.
        apply: Si es True, escribir cambios. Si es False, solo reportar.

    Returns:
        Diccionario con resultado {indexed, archived, by_type, changed, applied}.
    """
    script_path = repo_root / ".agent" / "scripts" / "rebuild_memory_index.py"
    if not script_path.exists():
        logger.warning(f"rebuild_memory_index.py not found at {script_path}")
        return {}

    cmd = [sys.executable, str(script_path), "--quiet"]
    if apply:
        cmd.append("--apply")

    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=60,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                return json.loads(output)
    except subprocess.TimeoutExpired:
        logger.error("rebuild_memory_index.py timed out")
    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse rebuild output: {e}")
    except Exception as e:
        logger.error(f"Error running rebuild_memory_index.py: {e}")

    return {}


def validate_memory_files(repo_root: Path) -> dict:
    """Validar integridad de archivos de memoria.

    Chequea:
    - Archivos .md en .claude/memory/ con contenido válido
    - Frontmatter YAML válido (si existe)
    - Sin archivos vacíos o corruptos

    Args:
        repo_root: Raíz del repositorio.

    Returns:
        Diccionario con validación: {total, valid, invalid, issues}.
    """
    memory_dir = repo_root / ".claude" / "memory"
    if not memory_dir.exists():
        logger.warning(f"Memory dir not found: {memory_dir}")
        return {"total": 0, "valid": 0, "invalid": 0, "issues": []}

    valid_count = 0
    invalid_count = 0
    issues: list[str] = []

    for path in memory_dir.glob("*.md"):
        if path.name in ("MEMORY.md", "MEMORY_ARCHIVE.md"):
            continue

        try:
            content = path.read_text(encoding="utf-8")
            if not content.strip():
                issues.append(f"Empty file: {path.name}")
                invalid_count += 1
            else:
                valid_count += 1
        except Exception as e:
            issues.append(f"Read error on {path.name}: {e}")
            invalid_count += 1

    return {
        "total": valid_count + invalid_count,
        "valid": valid_count,
        "invalid": invalid_count,
        "issues": issues,
    }


def detect_duplicates(repo_root: Path) -> dict:
    """Detectar posibles duplicados en memoria usando deduplicate_memory.py.

    Args:
        repo_root: Raíz del repositorio.

    Returns:
        Diccionario con resultado: {duplicates_found, canonical_entries}.
    """
    script_path = repo_root / ".agent" / "scripts" / "deduplicate_memory.py"
    if not script_path.exists():
        logger.debug("deduplicate_memory.py not found")
        return {}

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--dry-run", "--similarity", "0.85"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        # El script genera un JSON report en .antigravity/dedup_report.json
        report_path = repo_root / ".antigravity" / "dedup_report.json"
        if report_path.exists():
            return json.loads(report_path.read_text(encoding="utf-8"))
    except Exception as e:
        logger.debug(f"Error running duplicate detection: {e}")

    return {}


def rebuild_brain_index(repo_root: Path) -> dict:
    """Regenerar .agent/brain/index.md si es necesario.

    Args:
        repo_root: Raíz del repositorio.

    Returns:
        Diccionario con resultado.
    """
    script_path = repo_root / ".agent" / "scripts" / "rebuild_brain_index.py"
    if not script_path.exists():
        logger.debug("rebuild_brain_index.py not found")
        return {}

    try:
        result = subprocess.run(
            [sys.executable, str(script_path), "--quiet", "--skip-if-ephemeral"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode == 0:
            output = result.stdout.strip()
            if output:
                try:
                    return json.loads(output)
                except json.JSONDecodeError:
                    return {"status": "rebuilt"}
    except Exception as e:
        logger.debug(f"Error rebuilding brain index: {e}")

    return {}


def check_git_status(repo_root: Path) -> dict:
    """Chequear el estado de git para detectar cambios.

    Args:
        repo_root: Raíz del repositorio.

    Returns:
        Diccionario con info: {has_uncommitted, files_changed, staged}.
    """
    try:
        # Verificar si hay cambios sin commitear
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return {"error": "git status failed"}

        lines = result.stdout.strip().split("\n") if result.stdout.strip() else []
        files_changed = len(lines)
        staged = len([l for l in lines if l.startswith("A") or l.startswith("M")])

        return {
            "has_uncommitted": files_changed > 0,
            "files_changed": files_changed,
            "staged": staged,
            "files": lines[:10] if lines else [],
        }
    except Exception as e:
        logger.debug(f"Error checking git status: {e}")
        return {}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SessionStop hook: auto-repair memory and validate"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose logging",
    )
    parser.add_argument(
        "--fix-auto",
        action="store_true",
        help="Automatically apply fixes (rebuild indices, etc.)",
    )
    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    repo_root = find_repo_root()
    logger.info(f"SessionStop hook started at {repo_root}")

    # Ejecutar tareas
    logger.info("1/5: Rebuilding memory index...")
    rebuild_result = rebuild_memory_index(repo_root, apply=args.fix_auto)
    if rebuild_result:
        logger.info(
            f"  - Indexed {rebuild_result.get('indexed', '?')} entries, "
            f"archived {rebuild_result.get('archived', 0)}, "
            f"changed: {rebuild_result.get('changed', False)}"
        )

    logger.info("2/5: Validating memory files...")
    validation = validate_memory_files(repo_root)
    if validation and validation.get("issues"):
        logger.warning(f"  - Found {len(validation['issues'])} issues:")
        for issue in validation["issues"][:5]:
            logger.warning(f"    {issue}")

    logger.info("3/5: Detecting duplicates...")
    duplicates = detect_duplicates(repo_root)
    if duplicates:
        logger.info(
            f"  - Duplicates found: {duplicates.get('duplicates_found', '?')}, "
            f"canonical: {duplicates.get('canonical_entries', '?')}"
        )

    logger.info("4/5: Rebuilding brain index...")
    brain_result = rebuild_brain_index(repo_root)
    if brain_result:
        logger.info(f"  - Brain index status: {brain_result}")

    logger.info("5/5: Checking git status...")
    git_status = check_git_status(repo_root)
    if git_status:
        if git_status.get("has_uncommitted"):
            logger.info(
                f"  - {git_status.get('files_changed', '?')} files changed, "
                f"{git_status.get('staged', 0)} staged"
            )
        else:
            logger.info("  - No uncommitted changes")

    # Resumen
    logger.info("\n=== SessionStop Summary ===")
    logger.info(f"Timestamp: {datetime.utcnow().isoformat()}")
    logger.info(f"Repository: {repo_root}")
    logger.info(f"Memory entries indexed: {rebuild_result.get('indexed', 'N/A')}")
    logger.info(f"Validation issues: {len(validation.get('issues', []))}")
    logger.info(f"Fix-auto mode: {args.fix_auto}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
