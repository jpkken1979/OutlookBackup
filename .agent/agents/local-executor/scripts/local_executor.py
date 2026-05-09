#!/usr/bin/env python3
"""
Local Executor — Ejecucion de comandos en el sistema local.

Este script es el motor de ejecucion del agente local-executor.
Ejecuta comandos shell y scripts en el PC del usuario.

Uso:
    python local_executor.py "comando" [--cwd DIR] [--timeout N]
    python local_executor.py --interactive
    python local_executor.py --info
"""

from __future__ import annotations

import json
import logging
import os
import shlex
import subprocess
import sys
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Optional

# ============================================================================
# CONFIGURACION
# ============================================================================

ALLOWED_ROOTS = [
    Path.home(),
    Path("/c/Users/kenji/Github/Jpkken1979/OpenAntigravity26.3.30"),
    Path.home() / "AntigravitiSkillUSN",
    Path("/tmp"),
    Path("/c/Users/kenji/AppData/Local/Temp"),
    Path("/var/tmp"),
]

# Windows executables que existen fisicamente pero pueden no estar en PATH
# Usa paths estilo Windows (C:\...) no Unix (/c/...)
WINDOWS_RESOLVE: dict[str, str] = {
    "powershell": "C:\\Windows\\System32\\WindowsPowerShell\\v1.0\\powershell.exe",
    "pwsh": "C:\\Program Files\\PowerShell\\7\\pwsh.exe",
    "cmd": "C:\\Windows\\System32\\cmd.exe",
    "node": "C:\\Program Files\\nodejs\\node.exe",
    "npm": "C:\\Program Files\\nodejs\\npm.cmd",
    "npx": "C:\\Program Files\\nodejs\\npx.cmd",
    "python": "C:\\Python314\\python.exe",
    "python3": "C:\\Python314\\python.exe",
    "git": "C:\\Program Files\\Git\\cmd\\git.exe",
    "curl": "C:\\Program Files\\Git\\mingw64\\bin\\curl.exe",
    "bash": "C:\\Program Files\\Git\\bin\\bash.exe",
}

MAX_TIMEOUT_SECONDS = 120
DEFAULT_TIMEOUT = 30
LOG_DIR = Path(__file__).parent.parent / "logs"

# Rate limiting
RATE_LIMIT_WINDOW_SECONDS = 60
RATE_LIMIT_MAX_CALLS = 30
_rate_limit_store: dict[str, list[float]] = {}  # session_id -> list of timestamps

# ============================================================================
# MODELOS
# ============================================================================

@dataclass
class ExecutionResult:
    """Resultado de una ejecucion."""
    command: str
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: int
    success: bool
    error: Optional[str] = None

    def to_dict(self) -> dict:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict(), indent=2, ensure_ascii=False)


@dataclass
class SystemInfo:
    """Informacion del sistema."""
    hostname: str
    platform: str
    python_version: str
    home: str
    cwd: str
    antigravity_root: str
    allowed_paths: list[str]

    def to_dict(self) -> dict:
        return asdict(self)


# ============================================================================
# LOGGING
# ============================================================================

def get_logger() -> logging.Logger:
    """Logger dedicado para el executor."""
    logger = logging.getLogger("local-executor")
    if not logger.handlers:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        log_file = LOG_DIR / f"execution_{datetime.now():%Y%m%d}.log"
        handler = logging.FileHandler(log_file, encoding="utf-8")
        handler.setFormatter(logging.Formatter(
            "[%(asctime)s] [%(levelname)s] %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        ))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


# ============================================================================
# VALIDACION DE PATHS
# ============================================================================

def is_path_allowed(path: str | Path) -> bool:
    """Verifica si un path esta dentro de los directorios permitidos."""
    try:
        p = Path(path).resolve()
        for root in ALLOWED_ROOTS:
            try:
                root_resolved = root.resolve()
                # Check if path is inside root or IS the root
                if root_resolved in p.parents or p == root_resolved:
                    return True
            except (OSError, ValueError):
                continue
        return False
    except (OSError, ValueError):
        return False


def validate_command(cmd: str) -> tuple[bool, Optional[str]]:
    """
    Valida un comando antes de ejecutarlo.
    Returns: (is_safe, error_message)
    """
    # Bloquear comandos destructivos sin confirmacion
    dangerous = [
        "rm -rf /", "rm -rf /*", "dd if=",
        ":(){:|:&};:",  # Fork bomb
        "> /dev/sda", "> /dev/sdb",  # Direct disk write
    ]
    for d in dangerous:
        if d in cmd:
            return False, f"Comando destructivo bloqueado: {d}"

    # Si el comando referencia paths, validarlos
    parts = shlex.split(cmd)
    for part in parts:
        p = Path(part)
        # Only check if it looks like a path (starts with / or ~ or letter:/)
        if str(p).startswith(("/", "~", "/c/", "/C/", "C:", "c:")):
            if not is_path_allowed(p):
                return False, f"Path no permitido: {part}"

    return True, None


def check_rate_limit(session_id: str) -> tuple[bool, Optional[str]]:
    """
    Verifica rate limit para una session.
    Returns: (allowed, error_message)
    """
    import time as time_module

    now = time_module.monotonic()
    window = RATE_LIMIT_WINDOW_SECONDS
    max_calls = RATE_LIMIT_MAX_CALLS

    if session_id not in _rate_limit_store:
        _rate_limit_store[session_id] = []

    timestamps = _rate_limit_store[session_id]
    # Remove old timestamps outside the window
    cutoff = now - window
    timestamps[:] = [t for t in timestamps if t > cutoff]

    if len(timestamps) >= max_calls:
        return False, f"Rate limit excedido: {max_calls} comandos por {window}s. Esperá {window}s."

    timestamps.append(now)
    return True, None


# ============================================================================
# EJECUCION
# ============================================================================

def execute_command(
    command: str,
    cwd: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
    log: bool = True,
) -> ExecutionResult:
    """
    Ejecuta un comando en el sistema local.

    Args:
        command: El comando a ejecutar (string shell)
        cwd: Directorio de trabajo (opcional)
        timeout: Timeout en segundos (max MAX_TIMEOUT_SECONDS)
        log: Si True, guarda en log

    Returns:
        ExecutionResult con stdout, stderr, exit_code
    """
    logger = get_logger()

    # Rate limit check
    session_id = os.environ.get("AGENT_SESSION_ID", "default")
    allowed, rate_msg = check_rate_limit(session_id)
    if not allowed:
        logger.warning(f"Rate limit para session {session_id}: {rate_msg}")
        return ExecutionResult(
            command=command,
            stdout="",
            stderr=rate_msg,
            exit_code=-5,
            duration_ms=0,
            success=False,
            error=rate_msg,
        )

    # Sanitizar timeout
    timeout = min(max(timeout, 1), MAX_TIMEOUT_SECONDS)

    # Validar comando
    is_safe, error_msg = validate_command(command)
    if not is_safe:
        logger.warning(f"Comando bloqueado: {command} — {error_msg}")
        return ExecutionResult(
            command=command,
            stdout="",
            stderr=error_msg or "Comando no permitido",
            exit_code=-1,
            duration_ms=0,
            success=False,
            error=error_msg,
        )

    # Resolver cwd
    if cwd:
        work_dir = Path(cwd).resolve()
        if not is_path_allowed(work_dir):
            work_dir = Path.cwd()
    else:
        work_dir = Path.cwd()

    # Ejecutar
    start = datetime.now()
    try:
        cmd_list = shlex.split(command)
        # Resolve Windows executables that may not be in PATH
        if cmd_list and cmd_list[0] in WINDOWS_RESOLVE:
            resolved = WINDOWS_RESOLVE[cmd_list[0]]
            if Path(resolved).exists():
                cmd_list[0] = resolved
        result = subprocess.run(
            cmd_list,
            shell=False,
            cwd=str(work_dir),
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)

        execution = ExecutionResult(
            command=command,
            stdout=result.stdout,
            stderr=result.stderr,
            exit_code=result.returncode,
            duration_ms=duration_ms,
            success=result.returncode == 0,
        )

        if log:
            logger.info(
                f"EXECUTED: {command} | exit={result.returncode} | "
                f"duration={duration_ms}ms | cwd={work_dir}"
            )

        return execution

    except subprocess.TimeoutExpired:
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        logger.warning(f"TIMEOUT: {command} | timeout={timeout}s")
        return ExecutionResult(
            command=command,
            stdout="",
            stderr=f"Timeout ({timeout}s) excedido",
            exit_code=-2,
            duration_ms=duration_ms,
            success=False,
            error=f"Timeout de {timeout}s excedido",
        )

    except Exception as e:
        duration_ms = int((datetime.now() - start).total_seconds() * 1000)
        logger.error(f"ERROR: {command} | {e}")
        return ExecutionResult(
            command=command,
            stdout="",
            stderr=str(e),
            exit_code=-3,
            duration_ms=duration_ms,
            success=False,
            error=str(e),
        )


def execute_script(
    script_path: str | Path,
    args: Optional[list[str]] = None,
    cwd: Optional[str] = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> ExecutionResult:
    """
    Ejecuta un script (Python, Bash, PowerShell, Batch).

    Args:
        script_path: Ruta al script
        args: Argumentos a pasar al script
        cwd: Directorio de trabajo
        timeout: Timeout en segundos

    Returns:
        ExecutionResult
    """
    p = Path(script_path)
    if not p.exists():
        return ExecutionResult(
            command=str(p),
            stdout="",
            stderr=f"Script no encontrado: {p}",
            exit_code=-4,
            duration_ms=0,
            success=False,
            error="Script not found",
        )

    if not is_path_allowed(p):
        return ExecutionResult(
            command=str(p),
            stdout="",
            stderr=f"Path no permitido: {p}",
            exit_code=-1,
            duration_ms=0,
            success=False,
            error="Path not allowed",
        )

    suffix = p.suffix.lower()
    if suffix == ".py":
        cmd_parts = [sys.executable or "python", str(p.absolute())]
    elif suffix in (".sh", ".bash"):
        cmd_parts = ["bash", str(p.absolute())]
    elif suffix in (".ps1", ".psm1"):
        cmd_parts = ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(p.absolute())]
    elif suffix in (".bat", ".cmd"):
        cmd_parts = ["cmd", "/c", str(p.absolute())]
    else:
        cmd_parts = [str(p.absolute())]

    if args:
        cmd_parts.extend(args)

    command = " ".join(shlex.quote(str(c)) for c in cmd_parts)
    return execute_command(command, cwd=cwd, timeout=timeout)


# ============================================================================
# INFO DEL SISTEMA
# ============================================================================

def get_system_info() -> SystemInfo:
    """Obtiene informacion del sistema."""
    return SystemInfo(
        hostname=os.environ.get("COMPUTERNAME") or os.environ.get("HOSTNAME", "unknown"),
        platform=sys.platform,
        python_version=sys.version,
        home=str(Path.home()),
        cwd=str(Path.cwd()),
        antigravity_root=str(
            Path.home() / "Github" / "Jpkken1979" / "OpenAntigravity26.3.30"
        ),
        allowed_paths=[str(r) for r in ALLOWED_ROOTS],
    )


# ============================================================================
# CLI
# ============================================================================

def print_result(result: ExecutionResult, as_json: bool = False) -> None:
    """Imprime el resultado de ejecucion."""
    if as_json:
        print(result.to_json())
        return

    print(f"\n{'='*60}")
    print(f"COMMAND: {result.command}")
    print(f"EXIT CODE: {result.exit_code}")
    print(f"DURATION: {result.duration_ms}ms")
    print(f"{'='*60}")

    if result.stdout:
        print(f"\nSTDOUT:\n{result.stdout}")
    if result.stderr:
        print(f"\nSTDERR:\n{result.stderr}")
    if result.error:
        print(f"\nERROR: {result.error}")


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Local Executor — Ejecuta comandos en el sistema local",
        epilog="Ejemplo: python local_executor.py 'ls -la' --cwd /tmp",
    )
    parser.add_argument("command", nargs="?", help="Comando a ejecutar")
    parser.add_argument("--cwd", help="Directorio de trabajo")
    parser.add_argument("--timeout", type=int, default=DEFAULT_TIMEOUT, help="Timeout en segundos")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument("--info", action="store_true", help="Info del sistema")
    parser.add_argument("--validate", metavar="CMD", help="Solo validar un comando")
    parser.add_argument("--script", help="Ejecutar script en vez de comando")
    parser.add_argument("args", nargs="*", help="Argumentos adicionales")

    args = parser.parse_args()

    if args.info:
        info = get_system_info()
        print(json.dumps(info.to_dict(), indent=2, ensure_ascii=False))
        return

    if args.validate:
        is_safe, err = validate_command(args.validate)
        if is_safe:
            print(f"OK: {args.validate}")
        else:
            print(f"BLOQUEADO: {err}")
            sys.exit(1)
        return

    if args.command:
        result = execute_command(args.command, cwd=args.cwd, timeout=args.timeout)
        print_result(result, as_json=args.json)
        sys.exit(result.exit_code if not result.success else 0)

    if args.script:
        result = execute_script(args.script, args=args.args, cwd=args.cwd, timeout=args.timeout)
        print_result(result, as_json=args.json)
        sys.exit(result.exit_code if not result.success else 0)

    # Modo interactivo
    print("Local Executor — Modo interactivo")
    print(f"Timeout default: {DEFAULT_TIMEOUT}s | Max: {MAX_TIMEOUT_SECONDS}s")
    print("Escribi 'exit' para salir.\n")

    while True:
        try:
            cmd = input(f"{os.getcwd()}> ").strip()
            if not cmd:
                continue
            if cmd in ("exit", "quit", "q"):
                break
            result = execute_command(cmd, timeout=DEFAULT_TIMEOUT)
            print_result(result)
        except (EOFError, KeyboardInterrupt):
            break


if __name__ == "__main__":
    main()
