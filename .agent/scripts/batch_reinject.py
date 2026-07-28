#!/usr/bin/env python3
"""Batch re-injector para propagar el ecosistema Antigravity a apps target.

Detecta apps locales que ya tienen Antigravity inyectado (señal principal:
`.agent/VERSION`) y las re-inyecta en batch usando `mcp_injector.py`. Sirve
para propagar cambios recientes del ecosistema (ej. `repo_crawler.py` nuevo)
a todas las apps del usuario en una sola pasada.

Contrato:
- Dry-run por default: solo lista targets y versiones.
- `--apply` ejecuta el injector real via subprocess (shell=False, timeout 300s).
- `--scan-common` prueba parent dirs tipicos ($HOME/Git, GitHub, Projects...).
- Excluye el propio repo OpenAntigravity para evitar loops de auto-inyeccion.
- Hasta 4 workers paralelos (`--parallel N`).

Uso:
    # Dry-run con parents comunes
    python .agent/scripts/batch_reinject.py --scan-common

    # Scan explicito de un parent
    python .agent/scripts/batch_reinject.py --parent-dir ~/Git

    # Lista explicita de paths
    python .agent/scripts/batch_reinject.py --paths /app1,/app2

    # Ejecutar de verdad
    python .agent/scripts/batch_reinject.py --scan-common --apply --yes
"""

from __future__ import annotations

import argparse
import concurrent.futures
import logging
import os
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger("batch_reinject")

# Repo root del crawler: este archivo vive en <repo>/.agent/scripts/batch_reinject.py
SELF_REPO_ROOT = Path(__file__).resolve().parents[2]
INJECTOR_PATH = SELF_REPO_ROOT / ".agent" / "scripts" / "mcp_injector.py"
DEFAULT_TIMEOUT = 300
MAX_PARALLEL = 4
CONFIRM_THRESHOLD = 5

# Parent dirs tipicos donde viven proyectos del usuario.
COMMON_PARENTS = (
    "Git",
    "git",
    "Documents/GitHub",
    "Projects",
    "Desktop/Git",
)


def _supports_color() -> bool:
    """Detecta si stdout soporta ANSI colors."""
    return sys.stdout.isatty() and os.environ.get("TERM", "") != "dumb"


def _color(code: str, text: str) -> str:
    """Envuelve texto en codigo ANSI si hay soporte, sino devuelve plano."""
    if not _supports_color():
        return text
    return f"\x1b[{code}m{text}\x1b[0m"


def ok(text: str) -> str:
    """Marca verde para exito."""
    return _color("32", text)


def err(text: str) -> str:
    """Marca roja para error."""
    return _color("31", text)


def warn(text: str) -> str:
    """Marca amarilla para warning."""
    return _color("33", text)


def dim(text: str) -> str:
    """Marca atenuada para metadata."""
    return _color("2", text)


@dataclass
class Target:
    """Representa un target detectado con Antigravity inyectado.

    Attributes:
        path: Ruta absoluta del directorio del proyecto.
        version: Contenido de `.agent/VERSION` (string) o None si no existe.
        version_mtime: Fecha de ultima modificacion del archivo VERSION.
        source: Etiqueta de la fuente de deteccion (scan/parent/paths).
    """

    path: Path
    version: str | None = None
    version_mtime: datetime | None = None
    source: str = "unknown"


@dataclass
class ReinjectResult:
    """Resultado de re-inyectar un target.

    Attributes:
        target: Target sobre el que se corrio.
        success: True si exit code == 0 y sin timeout.
        exit_code: Exit code del proceso.
        duration_s: Segundos que tomo el run.
        stdout: Salida estandar capturada.
        stderr: Error estandar capturado.
        error: Mensaje de error si hubo timeout o excepcion.
    """

    target: Target
    success: bool = False
    exit_code: int | None = None
    duration_s: float = 0.0
    stdout: str = ""
    stderr: str = ""
    error: str = ""


@dataclass
class BatchPlan:
    """Plan computado de re-inyeccion batch.

    Attributes:
        targets: Lista deduplicada y filtrada de targets a procesar.
        skipped: Mapa de path descartado -> razon.
    """

    targets: list[Target] = field(default_factory=list)
    skipped: dict[str, str] = field(default_factory=dict)


def is_antigravity_target(candidate: Path) -> bool:
    """Retorna True si el directorio tiene Antigravity inyectado.

    Senial principal: existe `<candidate>/.agent/VERSION`.
    Fallback: `<candidate>/.agent/` existe con `agents/` o `mcp/` adentro.

    Args:
        candidate: Directorio candidato a inspeccionar.

    Returns:
        True si hay indicios de inyeccion previa.
    """
    if not candidate.is_dir():
        return False
    agent_dir = candidate / ".agent"
    if not agent_dir.is_dir():
        return False
    if (agent_dir / "VERSION").is_file():
        return True
    return (agent_dir / "agents").is_dir() or (agent_dir / "mcp").is_dir()


def read_target_version(candidate: Path) -> tuple[str | None, datetime | None]:
    """Lee `.agent/VERSION` del target y devuelve (version, mtime).

    Args:
        candidate: Directorio del proyecto target.

    Returns:
        Tupla (version string o None, datetime mtime o None).
    """
    version_file = candidate / ".agent" / "VERSION"
    if not version_file.is_file():
        return None, None
    try:
        version = version_file.read_text(encoding="utf-8").strip()
    except OSError as exc:
        logger.warning("No se pudo leer %s: %s", version_file, exc)
        return None, None
    try:
        mtime = datetime.fromtimestamp(version_file.stat().st_mtime)
    except OSError:
        mtime = None
    return version, mtime


def _is_submodule_like(path: Path) -> bool:
    """Detecta si el path parece ser un submodulo git (contiene `.git/` dentro del path)."""
    parts = {p.lower() for p in path.parts}
    return ".git" in parts


def scan_parent_dir(parent: Path, source_label: str) -> list[Target]:
    """Scan non-recursivo de un parent dir buscando children con `.agent/`.

    Args:
        parent: Parent directory a escanear.
        source_label: Etiqueta para atribucion de origen.

    Returns:
        Lista de targets encontrados en children directos.
    """
    targets: list[Target] = []
    if not parent.is_dir():
        return targets
    try:
        children = sorted(p for p in parent.iterdir() if p.is_dir())
    except OSError as exc:
        logger.warning("No se pudo listar %s: %s", parent, exc)
        return targets
    for child in children:
        if not is_antigravity_target(child):
            continue
        version, mtime = read_target_version(child)
        targets.append(
            Target(
                path=child.resolve(),
                version=version,
                version_mtime=mtime,
                source=source_label,
            )
        )
    return targets


def build_plan(
    parent_dirs: list[Path],
    explicit_paths: list[Path],
    scan_common: bool,
) -> BatchPlan:
    """Construye el plan combinando fuentes, filtrando y deduplicando.

    Args:
        parent_dirs: Parent dirs explicitos via `--parent-dir`.
        explicit_paths: Paths explicitos via `--paths`.
        scan_common: Si True, escanea los parents preset en $HOME.

    Returns:
        BatchPlan con targets filtrados y razones de skips.
    """
    plan = BatchPlan()
    by_path: dict[Path, Target] = {}

    def _consider(target: Target) -> None:
        resolved = target.path.resolve()
        # Excluir el propio repo OpenAntigravity (loop de auto-inyeccion).
        if resolved == SELF_REPO_ROOT:
            plan.skipped[str(resolved)] = "self-repo (OpenAntigravity)"
            return
        # Warn si parece submodulo.
        if _is_submodule_like(resolved):
            plan.skipped[str(resolved)] = "contiene .git en el path (submodule?)"
            return
        # Dedup: primera fuente gana.
        if resolved in by_path:
            return
        target.path = resolved
        by_path[resolved] = target

    # Fuente A: parent dirs explicitos
    for parent in parent_dirs:
        parent_resolved = parent.expanduser().resolve()
        logger.info("Scaneando parent dir: %s", parent_resolved)
        for target in scan_parent_dir(parent_resolved, source_label=f"parent:{parent_resolved}"):
            _consider(target)

    # Fuente B: paths explicitos
    for candidate in explicit_paths:
        candidate_resolved = candidate.expanduser().resolve()
        if not candidate_resolved.is_dir():
            plan.skipped[str(candidate_resolved)] = "no es directorio"
            continue
        if not is_antigravity_target(candidate_resolved):
            plan.skipped[str(candidate_resolved)] = "sin .agent/ inyectado"
            continue
        version, mtime = read_target_version(candidate_resolved)
        _consider(
            Target(
                path=candidate_resolved,
                version=version,
                version_mtime=mtime,
                source="paths",
            )
        )

    # Fuente C: scan common
    if scan_common:
        home = Path.home()
        for rel in COMMON_PARENTS:
            parent = home / rel
            if not parent.is_dir():
                continue
            logger.info("Scaneando parent comun: %s", parent)
            for target in scan_parent_dir(parent, source_label=f"common:{rel}"):
                _consider(target)

    plan.targets = sorted(by_path.values(), key=lambda t: str(t.path))
    return plan


def _format_target_line(idx: int, target: Target) -> str:
    """Formatea una linea del preview del target."""
    version_str = target.version or "???"
    mtime_str = target.version_mtime.strftime("%Y-%m-%d") if target.version_mtime else "unknown"
    source_str = dim(f"[{target.source}]")
    return (
        f"  {idx:>2}. {target.path}  "
        f"{dim(f'(version: {version_str}, mtime: {mtime_str})')} {source_str}"
    )


def print_plan(plan: BatchPlan, self_version: str | None) -> None:
    """Imprime el plan detectado (dry-run o pre-apply)."""
    count = len(plan.targets)
    if count == 0:
        print(warn("[batch-reinject] 0 targets detectados."))
        if plan.skipped:
            print(dim("[batch-reinject] Skips:"))
            for path, reason in plan.skipped.items():
                print(dim(f"  - {path}: {reason}"))
        return

    self_info = f" (repo fuente version: {self_version})" if self_version else ""
    print(f"[batch-reinject] Targets detectados: {count}{self_info}")
    for idx, target in enumerate(plan.targets, start=1):
        print(_format_target_line(idx, target))

    if plan.skipped:
        print()
        print(dim(f"[batch-reinject] Skips ({len(plan.skipped)}):"))
        for path, reason in plan.skipped.items():
            print(dim(f"  - {path}: {reason}"))


def run_injector_for_target(
    target: Target,
    full: bool,
    timeout: int,
) -> ReinjectResult:
    """Invoca `mcp_injector.py` para un target y captura resultado.

    Args:
        target: Target a procesar.
        full: Si True, pasa `--full` al injector.
        timeout: Timeout en segundos.

    Returns:
        ReinjectResult con exit code, stdout/stderr y flag de exito.
    """
    cmd: list[str] = [sys.executable, str(INJECTOR_PATH), str(target.path)]
    if full:
        cmd.append("--full")

    started = datetime.now()
    result = ReinjectResult(target=target)
    try:
        completed = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=False,
        )
        result.exit_code = completed.returncode
        result.stdout = completed.stdout or ""
        result.stderr = completed.stderr or ""
        result.success = completed.returncode == 0
    except subprocess.TimeoutExpired:
        result.error = f"timeout ({timeout}s)"
        result.success = False
    except (OSError, subprocess.SubprocessError) as exc:
        result.error = f"subprocess error: {exc}"
        result.success = False
    finally:
        result.duration_s = (datetime.now() - started).total_seconds()
    return result


def execute_batch(
    plan: BatchPlan,
    full: bool,
    parallel: int,
    verbose: bool,
    timeout: int,
) -> list[ReinjectResult]:
    """Ejecuta la re-inyeccion de todos los targets, serial o paralelo.

    Args:
        plan: Plan computado.
        full: Pasar `--full` al injector.
        parallel: Cantidad de workers (1 = serial, max MAX_PARALLEL).
        verbose: Si True, imprime stdout/stderr completos del injector.
        timeout: Timeout por target en segundos.

    Returns:
        Lista de resultados en el mismo orden del plan.
    """
    workers = max(1, min(parallel, MAX_PARALLEL))
    results: list[ReinjectResult] = []

    def _log_result(res: ReinjectResult) -> None:
        label = ok("OK") if res.success else err("FAIL")
        detail = f"exit={res.exit_code}" if res.exit_code is not None else res.error
        logger.info(
            "[%s] %s  (%.1fs, %s)",
            label,
            res.target.path,
            res.duration_s,
            detail,
        )
        if verbose or not res.success:
            if res.stdout:
                print(dim("--- stdout ---"))
                print(res.stdout)
            if res.stderr:
                print(dim("--- stderr ---"))
                print(res.stderr)

    if workers == 1:
        for target in plan.targets:
            logger.info("Re-inyectando %s ...", target.path)
            res = run_injector_for_target(target, full=full, timeout=timeout)
            results.append(res)
            _log_result(res)
        return results

    logger.info("Ejecutando en paralelo con %d workers", workers)
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as pool:
        future_to_target = {
            pool.submit(run_injector_for_target, target, full, timeout): target
            for target in plan.targets
        }
        for future in concurrent.futures.as_completed(future_to_target):
            res = future.result()
            results.append(res)
            _log_result(res)
    # Reordenar por orden original del plan para reporte estable.
    order = {t.path: i for i, t in enumerate(plan.targets)}
    results.sort(key=lambda r: order.get(r.target.path, 0))
    return results


def print_summary(results: list[ReinjectResult]) -> int:
    """Imprime resumen final y devuelve exit code apropiado.

    Args:
        results: Lista de resultados.

    Returns:
        0 si todos exitosos, 1 si al menos uno fallo.
    """
    total = len(results)
    successes = [r for r in results if r.success]
    failures = [r for r in results if not r.success]

    print()
    print(f"[batch-reinject] Resumen: {len(successes)}/{total} exitosos")
    if successes:
        print(ok(f"  OK  {len(successes)} targets re-inyectados."))
    if failures:
        print(err(f"  FAIL {len(failures)} targets fallaron:"))
        for res in failures:
            reason = res.error or f"exit code {res.exit_code}"
            print(err(f"     - {res.target.path}: {reason}"))
        return 1
    return 0


def _parse_paths(raw: str) -> list[Path]:
    """Parsea una lista de paths separados por coma (sin vacios)."""
    return [Path(p.strip()) for p in raw.split(",") if p.strip()]


def build_parser() -> argparse.ArgumentParser:
    """Construye el ArgumentParser del batch re-injector."""
    parser = argparse.ArgumentParser(
        prog="batch_reinject",
        description=("Re-inyecta Antigravity en apps target en batch usando mcp_injector.py."),
    )
    parser.add_argument(
        "--parent-dir",
        action="append",
        default=[],
        help="Parent dir a escanear (children directos). Repetible.",
    )
    parser.add_argument(
        "--paths",
        default="",
        help="Lista de paths target separados por coma.",
    )
    parser.add_argument(
        "--scan-common",
        action="store_true",
        help="Scanea parent dirs tipicos ($HOME/Git, GitHub, Projects...).",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Ejecuta la re-inyeccion real. Sin esto, solo dry-run.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Pasa --full al injector (instalacion completa).",
    )
    parser.add_argument(
        "--parallel",
        type=int,
        default=1,
        help=f"Workers en paralelo (1-{MAX_PARALLEL}). Default 1 (serial).",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=DEFAULT_TIMEOUT,
        help=f"Timeout por target en segundos. Default {DEFAULT_TIMEOUT}.",
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Confirma batches grandes (>5 targets). Redundante si se pasa --yes.",
    )
    parser.add_argument(
        "--yes",
        action="store_true",
        help="Auto-confirma sin preguntar.",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Muestra stdout/stderr completo del injector por cada target.",
    )
    return parser


def _confirm_interactive(count: int) -> bool:
    """Pide confirmacion interactiva cuando el batch es grande."""
    try:
        reply = input(f"[batch-reinject] Confirmar re-inyeccion de {count} targets? [y/N]: ")
    except EOFError:
        return False
    return reply.strip().lower() in {"y", "yes", "s", "si"}


def main(argv: list[str] | None = None) -> int:
    """Entry point del batch re-injector.

    Args:
        argv: Lista de argumentos (para tests); None usa sys.argv.

    Returns:
        Exit code: 0 OK, 1 con fallos, 2 pre-condiciones invalidas.
    """
    parser = build_parser()
    args = parser.parse_args(argv)

    if not INJECTOR_PATH.is_file():
        logger.error("No se encontro el injector en %s", INJECTOR_PATH)
        return 2

    parent_dirs = [Path(p) for p in args.parent_dir]
    explicit_paths = _parse_paths(args.paths)

    if not parent_dirs and not explicit_paths and not args.scan_common:
        parser.error("Pasa al menos --parent-dir, --paths o --scan-common.")
        return 2  # pragma: no cover

    self_version_file = SELF_REPO_ROOT / ".agent" / "VERSION"
    self_version = (
        self_version_file.read_text(encoding="utf-8").strip()
        if self_version_file.is_file()
        else None
    )

    plan = build_plan(
        parent_dirs=parent_dirs,
        explicit_paths=explicit_paths,
        scan_common=args.scan_common,
    )
    print_plan(plan, self_version=self_version)

    if not plan.targets:
        if args.apply:
            logger.info("Nada para re-inyectar. Saliendo.")
        else:
            print(dim("[batch-reinject] Ejecuta con --apply para re-inyectar."))
        return 0

    if not args.apply:
        print()
        print(dim("[batch-reinject] Ejecuta con --apply para re-inyectar."))
        return 0

    # Apply mode: gating y confirmacion.
    if args.parallel < 1 or args.parallel > MAX_PARALLEL:
        logger.error("--parallel debe estar entre 1 y %d", MAX_PARALLEL)
        return 2

    count = len(plan.targets)
    needs_confirm = count > CONFIRM_THRESHOLD
    if needs_confirm and not args.yes and not args.confirm:
        logger.error(
            "Hay %d targets (> %d). Pasa --confirm o --yes para continuar.",
            count,
            CONFIRM_THRESHOLD,
        )
        return 2
    if needs_confirm and args.confirm and not args.yes:
        if not _confirm_interactive(count):
            logger.info("Abortado por el usuario.")
            return 0

    logger.info(
        "Aplicando re-inyeccion: %d targets, parallel=%d, full=%s, timeout=%ds",
        count,
        args.parallel,
        args.full,
        args.timeout,
    )
    results = execute_batch(
        plan=plan,
        full=args.full,
        parallel=args.parallel,
        verbose=args.verbose,
        timeout=args.timeout,
    )
    return print_summary(results)


if __name__ == "__main__":
    sys.exit(main())
