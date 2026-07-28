#!/usr/bin/env python3
"""Transcript Doctor — detecta transcripts de Claude Code cerca del limite de 32MB.

El error ``Request too large (max 32MB)`` es un limite duro de la API de Anthropic
sobre el cuerpo COMPLETO de cada request (system + historial + tool results).
Un transcript de sesion (``~/.claude/projects/<proj>/<id>.jsonl``) que acumula
demasiados tool_results grandes —tipicamente PDFs o imagenes incrustados como
base64 al leerlos con ``Read``— cruza el limite y deja la sesion irreanudable.

Este script escanea todos los transcripts, los clasifica por riesgo y,
opcionalmente, archiva los muertos a un backup (sin borrar).

Uso:
    py .agent/scripts/transcript_doctor.py              # solo reporta
    py .agent/scripts/transcript_doctor.py --archive    # archiva los >=32MB
    py .agent/scripts/transcript_doctor.py --risk 20    # baja el umbral de riesgo

Ver tambien: .claude/memory/discovery_request_too_large_pdf_acumulacion.md
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
import time
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

MB: int = 1024 * 1024
DEFAULT_RISK_MB: float = 25.0
DEFAULT_DEAD_MB: float = 32.0
ACTIVE_SESSION_GRACE_SECONDS: int = 600  # no archivar sesiones tocadas hace <10 min


@dataclass
class TranscriptInfo:
    """Metadata de un transcript de sesion de Claude Code.

    Args:
        path: Ruta absoluta al archivo ``.jsonl``.
        size_bytes: Tamano en bytes.
        project: Nombre de la carpeta de proyecto que lo contiene.
        mtime: Epoch de ultima modificacion.
    """

    path: Path
    size_bytes: int
    project: str
    mtime: float

    @property
    def size_mb(self) -> float:
        """Tamano en megabytes."""
        return self.size_bytes / MB

    @property
    def is_active(self) -> bool:
        """True si fue modificado dentro del periodo de gracia (sesion en curso)."""
        return (time.time() - self.mtime) < ACTIVE_SESSION_GRACE_SECONDS


def default_projects_dir() -> Path:
    """Devuelve la carpeta de proyectos de Claude Code del usuario actual.

    Returns:
        Ruta a ``~/.claude/projects``.
    """
    return Path.home() / ".claude" / "projects"


def scan_transcripts(projects_dir: Path) -> list[TranscriptInfo]:
    """Escanea todos los transcripts ``.jsonl`` bajo la carpeta de proyectos.

    Args:
        projects_dir: Carpeta raiz de proyectos de Claude Code.

    Returns:
        Lista de transcripts ordenada por tamano descendente.
    """
    results: list[TranscriptInfo] = []
    if not projects_dir.is_dir():
        logger.warning("No existe la carpeta de proyectos: %s", projects_dir)
        return results

    for jsonl in projects_dir.glob("*/*.jsonl"):
        try:
            stat = jsonl.stat()
        except OSError as exc:  # noqa: PERF203
            logger.debug("No se pudo leer %s: %s", jsonl, exc)
            continue
        results.append(
            TranscriptInfo(
                path=jsonl,
                size_bytes=stat.st_size,
                project=jsonl.parent.name,
                mtime=stat.st_mtime,
            )
        )
    return sorted(results, key=lambda t: t.size_bytes, reverse=True)


def archive_transcript(info: TranscriptInfo, backup_dir: Path) -> Path:
    """Mueve un transcript al directorio de backup, prefijando el proyecto.

    Args:
        info: Transcript a archivar.
        backup_dir: Carpeta destino del backup.

    Returns:
        Ruta destino donde quedo el archivo.
    """
    backup_dir.mkdir(parents=True, exist_ok=True)
    dest = backup_dir / f"{info.project}__{info.path.name}"
    shutil.move(str(info.path), str(dest))
    return dest


def run(
    projects_dir: Path,
    backup_dir: Path,
    risk_mb: float,
    dead_mb: float,
    do_archive: bool,
) -> int:
    """Ejecuta el diagnostico y, opcionalmente, el archivado.

    Args:
        projects_dir: Carpeta de proyectos a escanear.
        backup_dir: Destino de backup para los transcripts muertos.
        risk_mb: Umbral (MB) a partir del cual un transcript se marca EN RIESGO.
        dead_mb: Umbral (MB) a partir del cual se considera MUERTO (irreanudable).
        do_archive: Si True, archiva los muertos no activos.

    Returns:
        Cantidad de transcripts en estado MUERTO detectados.
    """
    transcripts = scan_transcripts(projects_dir)
    dead = [t for t in transcripts if t.size_mb >= dead_mb]
    at_risk = [t for t in transcripts if risk_mb <= t.size_mb < dead_mb]

    print(f"Escaneados {len(transcripts)} transcript(s) en {projects_dir}\n")

    print(f"=== MUERTOS (>={dead_mb:.0f}MB, irreanudables) ===")
    if not dead:
        print("  (ninguno)")
    for t in dead:
        flag = "  [ACTIVO, no se archiva]" if t.is_active else ""
        print(f"  {t.size_mb:7.1f} MB  {t.project}\\{t.path.name}{flag}")

    print(f"\n=== EN RIESGO ({risk_mb:.0f}-{dead_mb:.0f}MB, usar /clear pronto) ===")
    if not at_risk:
        print("  (ninguno)")
    for t in at_risk:
        print(f"  {t.size_mb:7.1f} MB  {t.project}\\{t.path.name}")

    if do_archive:
        archived = 0
        print("\n=== ARCHIVANDO ===")
        for t in dead:
            if t.is_active:
                print(f"  SKIP (sesion activa): {t.project}\\{t.path.name}")
                continue
            dest = archive_transcript(t, backup_dir)
            archived += 1
            print(f"  movido -> {dest}")
        if archived == 0:
            print("  (nada para archivar)")
        else:
            print(f"\nTotal archivado: {archived}. Backup en: {backup_dir}")
    elif dead:
        print(f"\nPara archivarlos: py {Path(__file__).name} --archive")

    return len(dead)


def hook_alert(projects_dir: Path, risk_mb: float, dead_mb: float) -> None:
    """Modo silencioso para hook SessionStart: 1 linea solo si hay riesgo.

    No imprime nada si todo esta sano (para no inflar el contexto). Nunca lanza
    excepciones — pensado para correr como hook donde un fallo no debe molestar.

    Args:
        projects_dir: Carpeta de proyectos de Claude Code.
        risk_mb: Umbral (MB) a partir del cual se considera en riesgo.
        dead_mb: Umbral (MB) a partir del cual se considera muerto/irreanudable.
    """
    try:
        flagged = [t for t in scan_transcripts(projects_dir) if t.size_mb >= risk_mb]
        if not flagged:
            return
        worst = flagged[0]
        dead_n = sum(1 for t in flagged if t.size_mb >= dead_mb)
        suffix = f" ({dead_n} ya irreanudable[s])" if dead_n else ""
        print(
            f"[transcript-doctor] AVISO: {len(flagged)} sesion(es) cerca del limite "
            f"32MB{suffix}. Peor: {worst.project} ({worst.size_mb:.1f}MB). "
            f"Usa /clear o: py .agent/scripts/transcript_doctor.py --archive"
        )
    except Exception:  # noqa: BLE001
        return


def main(argv: list[str] | None = None) -> int:
    """Punto de entrada CLI.

    Args:
        argv: Argumentos (por defecto ``sys.argv``).

    Returns:
        Codigo de salida del proceso.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
    )
    parser = argparse.ArgumentParser(
        description="Detecta y archiva transcripts de Claude Code cerca del limite de 32MB."
    )
    parser.add_argument(
        "--projects-dir",
        type=Path,
        default=default_projects_dir(),
        help="Carpeta de proyectos de Claude Code (default: ~/.claude/projects).",
    )
    parser.add_argument(
        "--backup-dir",
        type=Path,
        default=Path.home() / ".claude" / "projects-oversized-backup",
        help="Destino de backup para los transcripts archivados.",
    )
    parser.add_argument(
        "--risk",
        type=float,
        default=DEFAULT_RISK_MB,
        help=f"Umbral EN RIESGO en MB (default: {DEFAULT_RISK_MB:.0f}).",
    )
    parser.add_argument(
        "--dead",
        type=float,
        default=DEFAULT_DEAD_MB,
        help=f"Umbral MUERTO en MB (default: {DEFAULT_DEAD_MB:.0f}).",
    )
    parser.add_argument(
        "--archive",
        action="store_true",
        help="Archiva los transcripts muertos (no activos) al backup.",
    )
    parser.add_argument(
        "--hook-alert",
        action="store_true",
        help="Modo hook: imprime 1 linea solo si hay riesgo (silencioso si todo OK).",
    )
    args = parser.parse_args(argv)

    if args.hook_alert:
        hook_alert(args.projects_dir, args.risk, args.dead)
        return 0

    run(
        projects_dir=args.projects_dir,
        backup_dir=args.backup_dir,
        risk_mb=args.risk,
        dead_mb=args.dead,
        do_archive=args.archive,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
