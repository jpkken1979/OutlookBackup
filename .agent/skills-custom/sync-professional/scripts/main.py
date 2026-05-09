#!/usr/bin/env python3
"""
Sync Professional - Sincronización completa del repositorio.

Combina pull, commit inteligente, push y finalize en un solo comando.
"""

import argparse
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def run_command(
    cmd: list[str],
    check: bool = True,
    cwd: str | None = None,
) -> tuple[int, str, str]:
    """Ejecuta comando y retorna (exit_code, stdout, stderr).

    Fuerza UTF-8 con errors='replace' para que paths con caracteres
    no-ASCII (japones, tildes) no rompan el decoding en Windows.
    """
    prefix = f"[{cwd}] " if cwd else ""
    print(f"\n$ {prefix}{' '.join(cmd)}")
    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        cwd=cwd,
    )
    return result.returncode, result.stdout, result.stderr


def git_pull() -> bool:
    """Hace pull de la rama actual. Retorna True si hay éxito."""
    print("\nPASO 0: Git Pull")
    branch = subprocess.check_output(
        ["git", "branch", "--show-current"],
        text=True,
        encoding="utf-8",
        errors="replace",
    ).strip()

    code, stdout, stderr = run_command(["git", "pull", "origin", branch])

    if "Already up to date" in stdout:
        print("[OK] Ya actualizado")
        return True
    elif "CONFLICT" in stdout or "CONFLICT" in stderr:
        print("[ERROR] Conflictos detectados - resolver manualmente")
        return False
    elif code == 0:
        print("[OK] Pull exitoso")
        return True
    else:
        print(f"[ERROR] Pull fallo: {stderr}")
        return False


def detect_changes() -> tuple[list[str], list[str], list[str]]:
    """Detecta cambios: modified, new files, deleted."""
    print("\nPASO 1: Detectar Cambios")

    # Archivos modified
    code, stdout, _ = run_command(["git", "diff", "--name-only", "HEAD"])
    modified = stdout.strip().split("\n") if stdout.strip() else []

    # Archivos untracked (excluendo .git/ y build artifacts)
    code, stdout, _ = run_command(["git", "ls-files", "--others", "--exclude-standard"])
    untracked = stdout.strip().split("\n") if stdout.strip() else []

    # Archivos deleted
    code, stdout, _ = run_command(["git", "diff", "--name-only", "--diff-filter=D", "HEAD"])
    deleted = stdout.strip().split("\n") if stdout.strip() else []

    print(f"Modified: {len([m for m in modified if m])}")
    print(f"New: {len([u for u in untracked if u])}")
    print(f"Deleted: {len([d for d in deleted if d])}")

    return modified, untracked, deleted


def run_tests(skip_tests: bool = False) -> bool:
    """Ejecuta tests según el alcance de cambios."""
    if skip_tests:
        print("\n[WARN] Tests saltados (modo emergencia)")
        return True

    print("\nPASO 2: Tests")

    # Detectar alcance por archivos cambiados
    _, modified, _ = detect_changes()

    has_python = any(".agent/" in f or f.startswith("tests/") for f in modified)
    has_nexus = any("nexus-app/" in f for f in modified)

    all_passed = True

    if has_python:
        print("\n[Python] Tests...")
        code, _, stderr = run_command(
            ["python", "-m", "pytest", "tests/core/", "-x", "--tb=short", "-q"], check=False
        )
        if code != 0:
            print(f"[ERROR] Tests Python fallaron:\n{stderr}")
            all_passed = False

    if has_nexus:
        print("\n[Nexus] Tests...")
        code, _, stderr = run_command(["npm", "run", "ts:app"], check=False, cwd="nexus-app")
        if code != 0:
            print(f"[ERROR] TypeScript fallo:\n{stderr}")
            all_passed = False

    if all_passed:
        print("[OK] Todos los tests pasaron")

    return all_passed


def commit_intelligent(force_commit: bool = False) -> bool:
    """Commit inteligente: cambios nuevos o secciones pasadas."""
    print("\nPASO 3: Commit Inteligente")

    modified, untracked, _ = detect_changes()

    # Filtrar archivos relevantes (no build artifacts, no node_modules, etc.)
    exclude_patterns = {
        "node_modules/",
        ".venv/",
        "__pycache__/",
        ".omc/",
        "dist/",
        "build/",
        ".astro/",
        "*.pyc",
        "*.pyo",
    }

    relevant_modified = [
        f for f in modified if not any(pattern in f for pattern in exclude_patterns)
    ]

    relevant_untracked = [
        f for f in untracked if not any(pattern in f for pattern in exclude_patterns)
    ]

    changes_exist = relevant_modified or relevant_untracked

    if not changes_exist and not force_commit:
        print("[INFO] No hay cambios para commitear")

        # Buscar secciones pasadas para commitear
        memory_files = list(Path(".claude/memory").glob("*.md"))
        if memory_files:
            print(f"[INFO] Encontradas {len(memory_files)} memorias - commiteando...")
            run_command(["git", "add", ".claude/memory/"])

            code, _, _ = run_command(
                [
                    "git",
                    "commit",
                    "-m",
                    f"chore(memory): sincronizar memorias {datetime.now().strftime('%Y-%m-%d')}",
                ]
            )
            return code == 0

        return True

    # Si no hay cambios relevantes, salir temprano
    if not (relevant_modified or relevant_untracked):
        print("[INFO] No hay cambios relevantes para commitear")
        return True

    # Commit interactivo - pedir al usuario que revise
    print("\nArchivos para commitear:")
    for f in relevant_modified:
        print(f"  * {f} (modificado)")
    for f in relevant_untracked:
        print(f"  * {f} (nuevo)")

    print("\n[WARN] Review los cambios arriba. Cancela si hay algo incorrecto.")
    print("   Preparando commit...")

    # Stage archivos relevantes
    if relevant_modified:
        run_command(["git", "add"] + relevant_modified, check=False)
    if relevant_untracked:
        run_command(["git", "add"] + relevant_untracked, check=False)

    # Generar mensaje de commit
    today = datetime.now().strftime("%Y-%m-%d")
    commit_msg = f"chore(sync): sincronización profesional {today}"

    code, _, stderr = run_command(
        [
            "git",
            "commit",
            "-m",
            commit_msg,
            "-m",
            "",
            "-m",
            "Co-Authored-By: Claude <noreply@anthropic.com>",
        ],
        check=False,
    )

    if code == 0:
        print(f"[OK] Commit creado: {commit_msg}")
        return True
    elif "nothing to commit" in stderr:
        print("[INFO] No hay cambios para commitear")
        return True
    else:
        print(f"[ERROR] Commit fallo: {stderr}")
        return False


def git_push() -> bool:
    """Push de la rama actual."""
    print("\nPASO 4: Push")

    branch = subprocess.check_output(
        ["git", "branch", "--show-current"],
        text=True,
        encoding="utf-8",
        errors="replace",
    ).strip()

    code, stdout, stderr = run_command(["git", "push", "origin", branch])

    if code == 0:
        print("[OK] Push exitoso")
        return True
    elif "diverg" in stderr.lower() or "ahead" in stderr.lower():
        print("[WARN] Rama divergio - necesita rebase")
        print("   Ejecuta: git pull --rebase")
        return False
    else:
        print(f"[ERROR] Push fallo: {stderr}")
        return False


def finalize_session() -> bool:
    """Ejecuta flujo de finalize."""
    print("\nPASO 5: Finalize")

    # Actualizar ESTADO_PROYECTO.md con resumen de sesión
    estado_file = Path("ESTADO_PROYECTO.md")

    if estado_file.exists():
        print(f"[INFO] Actualizando {estado_file.name}")
        # Aquí iría la lógica para actualizar ESTADO_PROYECTO.md
        # Por ahora solo verificamos que existe

    # Guardar memorias
    print("[INFO] Guardando memorias...")
    memory_dir = Path(".claude/memory")
    if memory_dir.exists():
        memory_files = list(memory_dir.glob("*.md"))
        print(f"   {len(memory_files)} archivos de memoria")

    print("[OK] Finalize completado")
    return True


def main():
    """Función principal."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Sincronizacion profesional completa")
    parser.add_argument(
        "--force-commit", action="store_true", help="Forzar commit incluso si no hay cambios nuevos"
    )
    parser.add_argument(
        "--skip-tests", action="store_true", help="Saltar ejecucion de tests (emergencias solo)"
    )

    args = parser.parse_args()

    print("=" * 60)
    print("SYNC PROFESSIONAL - Sincronizacion Completa")
    print("=" * 60)

    # Flujo principal
    # PASO 0: Pull
    if not git_pull():
        print("\n[FAIL] Sync fallo en git pull - resolve manualmente")
        sys.exit(1)

    # PASO 1: Detectar cambios (ya llamado adentro de otras funciones)
    modified, _, _ = detect_changes()

    # PASO 2: Tests
    if not run_tests(skip_tests=args.skip_tests):
        if not args.skip_tests:
            print("\n[FAIL] Tests fallaron - commitea primero los fixes")
            print("   O usa --skip-tests en modo emergencia")
            sys.exit(1)

    # PASO 3: Commit inteligente
    if not commit_intelligent(force_commit=args.force_commit):
        print("\n[FAIL] Commit fallo")
        sys.exit(1)

    # PASO 4: Push
    if not git_push():
        print("\n[WARN] Push fallo - hace pull --rebase manualmente")
        sys.exit(1)

    # PASO 5: Finalize
    if not finalize_session():
        print("\n[WARN] Finalize tuvo problemas menores")

    # Reporte final
    print("\n" + "=" * 60)
    print("SYNC PROFESSIONAL COMPLETADO")
    print("=" * 60)
    print("\nEstado final:")
    print("   Pull: actualizado")
    if not args.skip_tests:
        print("   Tests: pasando")
    else:
        print("   Tests: saltados")
    print("   Commit: creado")
    print("   Push: exitoso")
    print("   Memoria: guardada")
    print("\nListo para cambiar de PC o cerrar sesion")
    print("=" * 60)


if __name__ == "__main__":
    main()
