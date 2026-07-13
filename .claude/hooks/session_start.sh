#!/usr/bin/env bash
# Session Start Hook — Daily Capture Inbox
# Runs on every new Claude Code session start

set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

DAILY_SCRIPT="$REPO_ROOT/.agent/scripts/daily_capture.py"
# Resolver robusto de Python: en hooks el PATH es minimo (Windows) y
# `python`/`python3`/`py` no resuelven. run-python.sh los busca por ruta absoluta.
PY_RESOLVER="$REPO_ROOT/.claude/hooks/scripts/run-python.sh"

if [[ -f "$DAILY_SCRIPT" && -f "$PY_RESOLVER" ]]; then
    # No bloqueante: si Python no esta o el script falla, no rompemos el SessionStart.
    bash "$PY_RESOLVER" "$DAILY_SCRIPT" || true
else
    echo "[session_start] WARNING: daily_capture.py o run-python.sh no encontrado"
fi
