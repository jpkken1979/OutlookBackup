#!/usr/bin/env python3
"""
Git Sync Hook - Auto-commit de archivos de métricas en tiempo de ejecución.

Se ejecuta en el evento Stop de Claude Code para commitear y pushear
los archivos de datos que el ecosistema Antigravity actualiza automáticamente.

Archivos gestionados:
  - .agent/metrics/agents.json
  - .antigravity/intelligence/agent_performance.json
  - .antigravity/intelligence/skill_effectiveness.json
  - .antigravity/observations/observations.db

v1.0.0 - 2026-02-26
"""

import json
import logging
import os
import subprocess
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("antigravity.git_sync_hook")

RUNTIME_FILES = [
    ".agent/metrics/agents.json",
    ".antigravity/intelligence/agent_performance.json",
    ".antigravity/intelligence/skill_effectiveness.json",
    ".antigravity/observations/observations.db",
]

COMMIT_MSG = "chore(metrics): auto-sync métricas y observaciones de sesión"


def run(cmd: list[str], cwd: Path) -> subprocess.CompletedProcess:
    """Ejecuta un comando git y retorna el resultado."""
    return subprocess.run(
        cmd,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
    )


def get_repo_root() -> Path | None:
    """Detecta el root del repositorio git."""
    cwd = os.environ.get("CC_CWD", os.environ.get("PWD", str(Path.cwd())))
    result = run(["git", "rev-parse", "--show-toplevel"], Path(cwd))
    if result.returncode != 0:
        return None
    stdout = (result.stdout or "").strip()
    if not stdout:
        return None
    return Path(stdout)


def get_current_branch(root: Path) -> str:
    """Obtiene la rama actual."""
    result = run(["git", "rev-parse", "--abbrev-ref", "HEAD"], root)
    return (result.stdout or "").strip() if result.returncode == 0 else "HEAD"


def main() -> None:
    """Sincroniza los archivos de métricas con git."""
    root = get_repo_root()
    if root is None:
        logger.warning("No se encontró repositorio git, saltando sync")
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return

    # Filtrar solo los archivos que existen
    existing = [f for f in RUNTIME_FILES if (root / f).exists()]
    if not existing:
        logger.info("Sin archivos de métricas para sincronizar")
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return

    # Agregar archivos al staging
    result = run(["git", "add", *existing], root)
    if result.returncode != 0:
        logger.error("Error en git add: %s", (result.stderr or "").strip())
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return

    # Verificar si hay cambios staged
    diff_result = run(["git", "diff", "--cached", "--quiet"], root)
    if diff_result.returncode == 0:
        logger.info("Sin cambios en métricas para commitear")
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return

    # Commit
    commit_result = run(["git", "commit", "-m", COMMIT_MSG], root)
    if commit_result.returncode != 0:
        logger.error("Error en git commit: %s", (commit_result.stderr or "").strip())
        print(json.dumps({"continue": True, "suppressOutput": True}))
        return

    logger.info("Métricas commiteadas: %s", commit_result.stdout.strip())

    # Push
    branch = get_current_branch(root)
    push_result = run(["git", "push", "-u", "origin", branch], root)
    if push_result.returncode == 0:
        logger.info("Push exitoso a origin/%s", branch)
    else:
        logger.warning("Push falló (puede reintentarse): %s", (push_result.stderr or "").strip())

    print(json.dumps({"continue": True, "suppressOutput": True}))


if __name__ == "__main__":
    main()
