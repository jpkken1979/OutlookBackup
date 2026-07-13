#!/usr/bin/env python3
"""PreToolUse guard que previene el "Request too large (max 32MB)" en su raíz.

El límite de 32MB es un techo DURO de la API de Anthropic sobre el body completo
(system + reglas + historial + tool_results), chequeado del lado de Claude Code.
La causa dominante (memoria 2026-06-09) es la ACUMULACIÓN: leer un PDF o imagen con
``Read`` los incrusta como base64 (~1.3MB/PDF) y se reenvían en CADA turno → una
lectura temprana envenena toda la sesión hasta chocar el techo.

Este guard intercepta ``Read`` ANTES de que el contenido pesado entre al contexto:
- PDF        -> bloquea y redirige al skill ``/pdf`` (texto plano, ~100x más liviano).
- Imagen >N  -> bloquea y sugiere redimensionar / evitar el re-envío por turno.
También avisa (sin bloquear) cuando la conversación se acerca al techo de 32MB.

Contrato Claude Code PreToolUse: lee JSON por stdin; exit 0 = permitir, exit 2 =
bloquear con mensaje a stderr (que vuelve al agente para que tome el camino liviano).

**Fail-open**: cualquier error o excepción → exit 0 (jamás rompe una sesión).
**Kill switch**: ``ANTIGRAVITY_CONTEXT_GUARD=off`` desactiva todo el guard.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass

# Extensiones que Claude Code incrusta de forma pesada en el contexto.
_PDF_EXTS = (".pdf",)
_IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tif", ".tiff")

# Defaults (overridables por env). Bytes.
_IMAGE_MAX_DEFAULT = 1_500_000  # imágenes mayores se reenvían cada turno → bloquear
_TRANSCRIPT_WARN_DEFAULT = 24_000_000  # avisar a partir de 24MB (techo 32MB)


@dataclass
class Decision:
    """Resultado de evaluar una tool call.

    Args:
        block: True si hay que bloquear la tool (exit 2).
        message: Mensaje accionable para el agente (a stderr si block).
        warning: Aviso no bloqueante (a stderr, exit 0) o None.
    """

    block: bool
    message: str = ""
    warning: str | None = None


def _env_int(name: str, default: int) -> int:
    """Lee un entero de env con fallback robusto."""
    try:
        return int(os.environ.get(name, "").strip() or default)
    except (ValueError, TypeError):
        return default


def _guard_enabled() -> bool:
    """Indica si el guard está activo (default sí; kill switch por env)."""
    raw = os.environ.get("ANTIGRAVITY_CONTEXT_GUARD", "1").strip().lower()
    return raw not in {"0", "false", "no", "off"}


def _human_mb(n: int) -> str:
    """Formatea bytes como MB legible."""
    return f"{n / 1_000_000:.1f}MB"


def evaluate_read(
    file_path: str,
    tool_input: dict,
    file_size: int | None,
    *,
    image_max: int,
) -> Decision:
    """Decide si un ``Read`` debe bloquearse para no inflar el contexto.

    Función pura (sin I/O): el tamaño del archivo se inyecta. Testeable directo.

    Args:
        file_path: Ruta del archivo a leer.
        tool_input: ``tool_input`` de la tool call (offset/limit, etc.).
        file_size: Tamaño del archivo en bytes, o None si no se pudo medir.
        image_max: Umbral de bytes para bloquear imágenes.

    Returns:
        Una ``Decision``. No-bloqueante por defecto (camino feliz).
    """
    lower = file_path.lower()

    # PDF: SIEMPRE redirigir. Claude Code incrusta el PDF como base64 que se reenvía
    # cada turno — la causa #1 del 32MB. /pdf extrae texto plano (~100x más liviano).
    if lower.endswith(_PDF_EXTS):
        size_hint = f" (~{_human_mb(file_size)})" if file_size else ""
        return Decision(
            block=True,
            message=(
                f"BLOQUEADO: leer '{file_path}'{size_hint} incrusta el PDF como base64 "
                "que Claude Code reenvía en CADA turno → causa #1 del 'Request too large "
                "(32MB)'. Usá el skill /pdf para extraer el texto (mucho más liviano), o "
                "`pdftotext <archivo> -` vía Bash. Override puntual: "
                "ANTIGRAVITY_CONTEXT_GUARD=off."
            ),
        )

    # Imagen grande: se reenvía cada turno. Por debajo del umbral, no molesta.
    if lower.endswith(_IMAGE_EXTS) and file_size is not None and file_size > image_max:
        return Decision(
            block=True,
            message=(
                f"BLOQUEADO: leer '{file_path}' ({_human_mb(file_size)}) incrusta la imagen "
                "en el contexto y se reenvía en cada turno (suma hacia el techo de 32MB). "
                f"Si necesitás analizarla, redimensionала por debajo de {_human_mb(image_max)} "
                "primero; si no, evitá el Read. Override: ANTIGRAVITY_CONTEXT_GUARD=off."
            ),
        )

    return Decision(block=False)


def evaluate(
    tool_name: str,
    tool_input: dict,
    file_size: int | None,
    transcript_size: int | None,
    *,
    image_max: int,
    transcript_warn: int,
) -> Decision:
    """Evalúa una tool call completa: bloqueo de Read + aviso de transcript.

    Args:
        tool_name: Nombre de la tool (solo ``Read`` se evalúa para bloqueo).
        tool_input: ``tool_input`` de la tool call.
        file_size: Tamaño del archivo objetivo (bytes) o None.
        transcript_size: Tamaño del transcript de la sesión (bytes) o None.
        image_max: Umbral de bytes para imágenes.
        transcript_warn: Umbral de bytes para avisar cercanía al techo.

    Returns:
        La ``Decision`` final (bloqueo tiene prioridad; el aviso se adjunta).
    """
    warning: str | None = None
    if transcript_size is not None and transcript_size > transcript_warn:
        warning = (
            f"AVISO: la conversación ya pesa {_human_mb(transcript_size)} (techo 32MB). "
            "Considerá /clear entre tareas pesadas: una sesión que cruza 32MB no se "
            "recupera (ni /compact, que reenvía el historial) — conviene abrir una nueva."
        )

    decision = Decision(block=False, warning=warning)
    if tool_name == "Read":
        file_path = str(tool_input.get("file_path") or "")
        if file_path:
            read_decision = evaluate_read(
                file_path, tool_input, file_size, image_max=image_max
            )
            if read_decision.block:
                read_decision.warning = warning
                return read_decision
    return decision


def _safe_file_size(path: str) -> int | None:
    """Tamaño de un archivo, o None si no se puede medir (fail-open)."""
    try:
        return os.path.getsize(path)
    except OSError:
        return None


def main() -> int:
    """Entry point del hook. Lee stdin, decide, sale 0 (permitir) o 2 (bloquear)."""
    if not _guard_enabled():
        return 0
    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, ValueError):
        return 0  # fail-open: input ilegible no bloquea

    try:
        tool_name = str(payload.get("tool_name") or "")
        tool_input = payload.get("tool_input") or {}
        if not isinstance(tool_input, dict):
            return 0

        file_path = str(tool_input.get("file_path") or "")
        file_size = _safe_file_size(file_path) if file_path else None
        transcript_size = _safe_file_size(str(payload.get("transcript_path") or "")) or None

        decision = evaluate(
            tool_name,
            tool_input,
            file_size,
            transcript_size,
            image_max=_env_int("ANTIGRAVITY_GUARD_IMAGE_MAX_BYTES", _IMAGE_MAX_DEFAULT),
            transcript_warn=_env_int(
                "ANTIGRAVITY_GUARD_TRANSCRIPT_WARN_BYTES", _TRANSCRIPT_WARN_DEFAULT
            ),
        )

        if decision.warning and not decision.block:
            print(decision.warning, file=sys.stderr)
        if decision.block:
            msg = decision.message
            if decision.warning:
                msg = f"{msg}\n{decision.warning}"
            print(msg, file=sys.stderr)
            return 2
        return 0
    except Exception:  # noqa: BLE001 — fail-open: cualquier bug del guard permite la tool
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
