#!/usr/bin/env bash
set -uo pipefail
# Hook: Provisiona dependencias Python al iniciar una sesion
# Triggered by: SessionStart event
# Cost: 0 tokens (bash local, sin invocacion LLM)
#
# Pensado para entornos efimeros (Claude Code on the web): el repo se clona
# fresco sin deps instaladas y los ~6.5k tests Python no colectan. Este hook
# instala requirements.txt completo de forma idempotente y silenciosa.
#
# NO se usa un sentinela de "5 libs core ya importan" porque era fragil: si esas
# 5 estaban pero faltaba mcp/fastapi/uvicorn/rich/crewai (o un piso de version de
# CVE no se cumplia), el hook salia con exito falso dejando el MCP/gateway roto.
# 'pip install -r requirements.txt' YA es idempotente: solo instala lo faltante o
# desactualizado y valida los pisos de version. pip es la fuente de verdad.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common-utils.sh"

ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
cd "$ROOT"

if [ ! -f requirements.txt ]; then
  echo '{"suppressOutput": true}'
  exit 0
fi

# Resolver robusto de Python: en hooks el PATH es minimo (Windows) y `python`/
# `python3`/`py` no resuelven. run-python.sh los busca por ruta absoluta.
PY_RESOLVER="${SCRIPT_DIR}/run-python.sh"
if [ ! -f "$PY_RESOLVER" ]; then
  echo '{"systemMessage": "setup-deps: run-python.sh no encontrado (no bloqueante)."}'
  exit 0
fi

# Instalacion best-effort. No rompe la sesion si pip falla (red restringida, etc).
PIP_OUT=$(bash "$PY_RESOLVER" -m pip install --quiet --disable-pip-version-check -r requirements.txt 2>&1)
PIP_EXIT=$?

if [ "$PIP_EXIT" -eq 0 ]; then
  echo '{"systemMessage": "Dependencias Python instaladas desde requirements.txt (setup-deps hook)."}'
else
  TAIL=$(echo "$PIP_OUT" | tail -2 | tr '\n' ' ')
  echo "{\"systemMessage\": \"setup-deps: pip install fallo (no bloqueante) — ${TAIL}\"}"
fi
exit 0
