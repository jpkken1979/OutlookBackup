#!/bin/bash
set -uo pipefail
# Detecta el intérprete Python disponible en cualquier OS/usuario/PC
PYTHON=""

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"

_pick_python() {
    local candidate="$1"
    if [ -x "$candidate" ] && "$candidate" -c "import sys" >/dev/null 2>&1; then
        PYTHON="$candidate"
        return 0
    fi
    return 1
}

# 1. Venvs del repo: evitan el PATH minimo de Claude Code/Git Bash en Windows.
for p in \
    "$ROOT/.venv/Scripts/python.exe" \
    "$ROOT/.venv-mcp/Scripts/python.exe" \
    "$ROOT/.venv/bin/python" \
    "$ROOT/.venv-mcp/bin/python"; do
    if [ -z "$PYTHON" ]; then
        _pick_python "$p" || true
    fi
done

# 2. Windows: instaladores reales y uv-managed Python.
if [ -z "$PYTHON" ]; then
    for p in \
        /c/Python3*/python.exe \
        /c/Python*/python.exe \
        /c/Users/*/AppData/Local/Programs/Python/Python*/python.exe \
        /c/Users/*/AppData/Local/uv/python/*/python.exe; do
        if [ -z "$PYTHON" ]; then
            _pick_python "$p" || true
        fi
    done
fi

# 3. PATH estándar (Linux, Mac, Windows con PATH configurado).
if [ -z "$PYTHON" ]; then
    if command -v python3 &>/dev/null; then
        _pick_python "$(command -v python3)" || true
    elif command -v python &>/dev/null; then
        _pick_python "$(command -v python)" || true
    fi
fi

# 4. WindowsApps al final: puede ser alias/stub de Microsoft Store.
if [ -z "$PYTHON" ]; then
    for p in /c/Users/*/AppData/Local/Microsoft/WindowsApps/python.exe; do
        if [ -z "$PYTHON" ]; then
            _pick_python "$p" || true
        fi
    done
fi

if [ -z "$PYTHON" ]; then
    echo "[run-python.sh] ERROR: No se encontró intérprete Python" >&2
    exit 1
fi

exec "$PYTHON" "$@"
