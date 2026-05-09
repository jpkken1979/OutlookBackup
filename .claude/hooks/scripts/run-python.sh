#!/bin/bash
set -uo pipefail
# Detecta el intérprete Python disponible en cualquier OS/usuario/PC
PYTHON=""

# 1. PATH estándar (Linux, Mac, Windows con PATH configurado)
if command -v python3 &>/dev/null; then
    PYTHON=$(command -v python3)
elif command -v python &>/dev/null; then
    PYTHON=$(command -v python)
fi

# 2. Windows: WindowsApps (cualquier usuario)
if [ -z "$PYTHON" ]; then
    for p in /c/Users/*/AppData/Local/Microsoft/WindowsApps/python.exe; do
        if [ -x "$p" ]; then PYTHON="$p"; break; fi
    done
fi

# 3. Windows: Python installer estándar (C:\Python3x\)
if [ -z "$PYTHON" ]; then
    for p in /c/Python3*/python.exe /c/Python*/python.exe; do
        if [ -x "$p" ]; then PYTHON="$p"; break; fi
    done
fi

# 4. uv managed python (cualquier usuario)
if [ -z "$PYTHON" ]; then
    for p in /c/Users/*/AppData/Local/uv/python/*/python.exe; do
        if [ -x "$p" ]; then PYTHON="$p"; break; fi
    done
fi

if [ -z "$PYTHON" ]; then
    echo "[run-python.sh] ERROR: No se encontró intérprete Python" >&2
    exit 1
fi

exec "$PYTHON" "$@"
