#!/usr/bin/env python3
"""Pre-push guard: bloquea push a remotos no allowlisted para proteger el .env.

El `.env` de este repo se versiona a propósito (repo privado, decisión consciente
documentada en `.claude/rules/security.md` y `PENDING_TASKS.md`), pero esa excepción
**NO aplica a forks ni mirrors públicos**. Hoy el único guard de git es anti
force-push: nada impide un `git push` accidental a un remoto desconocido, que
filtraría los tokens activos del `.env` (MINIMAX, ZAI, NVIDIA, GH_TOKEN, etc.).

Este hook corre vía pre-commit en stage `pre-push`. pre-commit expone la URL destino
en `PRE_COMMIT_REMOTE_URL`. La allowlist es configurable con
`ANTIGRAVITY_PUSH_ALLOWLIST` (substrings separados por coma).
"""

from __future__ import annotations

import os
import sys

# Substrings que identifican remotos seguros (repo privado + proxy del cloud).
DEFAULT_ALLOWLIST: tuple[str, ...] = (
    "jpkken1979/OpenAntigravity26.3.30",  # repo privado canónico
    "uns-kikaku",  # remotos internos UNS
    "127.0.0.1",  # proxy local del entorno cloud
    "localhost",
)


def resolve_allowlist() -> tuple[str, ...]:
    """Devuelve la allowlist activa (env var override o default)."""
    env = os.environ.get("ANTIGRAVITY_PUSH_ALLOWLIST", "").strip()
    if env:
        return tuple(item.strip() for item in env.split(",") if item.strip())
    return DEFAULT_ALLOWLIST


def resolve_remote_url() -> str:
    """Obtiene la URL del remoto destino (env de pre-commit o argv de git)."""
    url = os.environ.get("PRE_COMMIT_REMOTE_URL", "").strip()
    if not url and len(sys.argv) > 2:
        # git pasa `<remote-name> <remote-url>` como argv al hook pre-push nativo.
        url = sys.argv[2].strip()
    return url


def main() -> int:
    """Bloquea (exit 1) si el remoto destino no está en la allowlist."""
    url = resolve_remote_url()
    if not url:
        # Sin info del remoto no bloqueamos: no romper flujos legítimos.
        return 0

    allowlist = resolve_allowlist()
    if any(token in url for token in allowlist):
        return 0

    sys.stderr.write(
        "\n".join(
            [
                "",
                "=" * 70,
                "PUSH BLOQUEADO — remoto no allowlisted",
                "=" * 70,
                f"  remoto destino: {url}",
                "",
                "  Este repo versiona .env con tokens ACTIVOS (decisión consciente,",
                "  repo privado). Pushear a un remoto desconocido los FILTRARÍA.",
                "",
                f"  Allowlist actual: {', '.join(allowlist)}",
                "",
                "  Si el remoto es legítimo, agregalo:",
                "    export ANTIGRAVITY_PUSH_ALLOWLIST='slug1,slug2'",
                "  Si es un fork/mirror PÚBLICO: NO pushees. Sacá el .env del tracking",
                "  primero (git rm --cached .env) y rotá los tokens.",
                "=" * 70,
                "",
            ]
        )
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
