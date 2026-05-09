#!/usr/bin/env python3
"""
Hook Runner Cross-Platform - Resuelve paths de hooks automáticamente.

Detecta el sistema operativo y resuelve la ruta del script target
relativa a su propia ubicación, eliminando paths hardcodeados.

Uso:
    python3 .agent/scripts/hook_runner.py <script_name> [args...]

Ejemplos:
    python3 .agent/scripts/hook_runner.py session_hook.py start
    python3 .agent/scripts/hook_runner.py observation_hook.py
    python3 .agent/scripts/hook_runner.py git_sync_hook.py

v1.0.0 - 2026-02-27
"""

import subprocess
import sys
from pathlib import Path


def find_python() -> str:
    """Encuentra el ejecutable de Python correcto para la plataforma."""
    # En el entorno actual, sys.executable siempre funciona
    if sys.executable:
        return sys.executable

    # Fallback: intentar python3 primero, luego python
    for candidate in ("python3", "python"):
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                shell=False,
            )
            if result.returncode == 0:
                return candidate
        except FileNotFoundError:
            continue

    return "python3"


def find_shell(script_path: Path) -> list[str]:
    """Encuentra el interprete adecuado para scripts no Python."""
    suffix = script_path.suffix.lower()
    if suffix == ".py":
        return [find_python(), str(script_path)]

    if suffix == ".sh":
        candidates = [
            "bash",
            r"C:\Program Files\Git\bin\bash.exe",
            r"C:\Program Files\Git\usr\bin\bash.exe",
        ]
        for candidate in candidates:
            try:
                result = subprocess.run(
                    [candidate, "--version"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    shell=False,
                )
                if result.returncode == 0:
                    return [candidate, str(script_path)]
            except FileNotFoundError:
                continue
        raise FileNotFoundError("No se encontro bash para ejecutar hooks .sh")

    if suffix == ".ps1":
        for candidate in ("pwsh", "powershell"):
            try:
                result = subprocess.run(
                    [candidate, "-Command", "$PSVersionTable.PSVersion.ToString()"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    shell=False,
                )
                if result.returncode == 0:
                    return [candidate, "-File", str(script_path)]
            except FileNotFoundError:
                continue
        raise FileNotFoundError("No se encontro PowerShell para ejecutar hooks .ps1")

    raise ValueError(f"Tipo de hook no soportado: {script_path.name}")


def main() -> int:
    """Ejecuta el script hook especificado con resolución cross-platform."""
    if len(sys.argv) < 2:
        print(
            "Uso: hook_runner.py <script_name> [args...]\n"
            "Ejemplo: hook_runner.py session_hook.py start",
            file=sys.stderr,
        )
        return 1

    script_name = sys.argv[1]
    extra_args = sys.argv[2:]

    # Resolver path del script relativo a la ubicación de hook_runner.py
    scripts_dir = Path(__file__).resolve().parent
    script_path = scripts_dir / script_name

    if not script_path.exists():
        print(f"Hook script no encontrado: {script_path}", file=sys.stderr)
        return 1

    # Resolver repo root (2 niveles arriba de .agent/scripts/)
    repo_root = scripts_dir.parent.parent

    # Ejecutar el script target con el interprete correcto
    cmd = find_shell(script_path) + extra_args

    try:
        result = subprocess.run(
            cmd,
            cwd=str(repo_root),
            stdin=sys.stdin if not sys.stdin.isatty() else None,
            shell=False,
        )
        return result.returncode
    except FileNotFoundError:
        print("No se encontró el intérprete requerido para ejecutar el hook.", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error ejecutando hook: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
