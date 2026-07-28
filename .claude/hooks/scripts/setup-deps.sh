#!/usr/bin/env bash
set -uo pipefail
# Hook: Provisiona dependencias (Python + Node) al iniciar una sesion
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
#
# Gotcha contenedores (2026-07-22): si el unico Python es el del SISTEMA
# (Debian/Ubuntu), pip NO puede tocar paquetes que administra el OS
# ("Cannot uninstall PyJWT ... installed by debian" / PEP 668) y el install
# entero aborta: la sesion arrancaba sin NADA instalado. Fix: cuando el
# interprete resuelto no es un venv, se crea .venv/ en el repo y se instala
# ahi — run-python.sh ya prioriza .venv/, asi que el resto de hooks y
# sesiones lo adoptan solos. En PCs con .venv existente nada cambia.

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

NOTES=""

# ── Python ──────────────────────────────────────────────────────────────────
IS_VENV=$(bash "$PY_RESOLVER" -c "import sys; print(int(sys.prefix != sys.base_prefix))" 2>/dev/null || echo 0)

PIP_TARGET=""
if [ "$IS_VENV" = "1" ]; then
  # El resolver ya encontro un venv (.venv del repo o equivalente): instalar ahi.
  PIP_OUT=$(bash "$PY_RESOLVER" -m pip install --quiet --disable-pip-version-check -r requirements.txt 2>&1)
  PIP_EXIT=$?
  PIP_TARGET="venv existente"
else
  # Python del sistema: crear el venv del repo para no chocar con paquetes del OS.
  if [ ! -x .venv/bin/python ] && [ ! -x .venv/Scripts/python.exe ]; then
    bash "$PY_RESOLVER" -m venv .venv >/dev/null 2>&1 || true
  fi
  VENV_PY=""
  [ -x .venv/bin/python ] && VENV_PY=".venv/bin/python"
  [ -x .venv/Scripts/python.exe ] && VENV_PY=".venv/Scripts/python.exe"
  if [ -n "$VENV_PY" ]; then
    PIP_OUT=$("$VENV_PY" -m pip install --quiet --disable-pip-version-check -r requirements.txt 2>&1)
    PIP_EXIT=$?
    PIP_TARGET=".venv nuevo"
  else
    # Sin ensurepip/python3-venv: best-effort al sistema (comportamiento previo).
    PIP_OUT=$(bash "$PY_RESOLVER" -m pip install --quiet --disable-pip-version-check -r requirements.txt 2>&1)
    PIP_EXIT=$?
    PIP_TARGET="python del sistema (no se pudo crear .venv)"
  fi
fi

if [ "$PIP_EXIT" -eq 0 ]; then
  NOTES="Python OK (${PIP_TARGET})."
  # Extras de dev (pytest-xdist/timeout, hypothesis, scipy, responses, ruff...):
  # sin esto los ~6.5k tests colectan pero varios modulos no importan. Best-effort.
  PIP_BIN="${VENV_PY:-}"
  if [ -z "$PIP_BIN" ]; then PIP_BIN="bash $PY_RESOLVER"; fi
  if $PIP_BIN -m pip install --quiet --disable-pip-version-check ".[dev]" >/dev/null 2>&1; then
    NOTES="${NOTES} Extras [dev] OK."
  else
    NOTES="${NOTES} Extras [dev] fallaron (no bloqueante)."
  fi
else
  TAIL=$(echo "$PIP_OUT" | tail -2 | tr '\n' ' ' | tr '"' "'")
  NOTES="pip fallo en ${PIP_TARGET} (no bloqueante) — ${TAIL}"
fi

# ── Node (best-effort) ──────────────────────────────────────────────────────
# En contenedores efimeros node_modules/ no existe y npm test / vitest no
# corren. Solo instala si falta POR COMPLETO: en PCs con node_modules ya
# poblado no agrega latencia. npm install es idempotente si se corta.
if command -v npm >/dev/null 2>&1; then
  for dir in . nexus-app; do
    if [ -f "$dir/package.json" ] && [ ! -d "$dir/node_modules" ]; then
      if (cd "$dir" && npm install --no-audit --no-fund --loglevel=error >/dev/null 2>&1); then
        NOTES="${NOTES} npm install OK en ${dir}/."
      else
        NOTES="${NOTES} npm install fallo en ${dir}/ (no bloqueante)."
      fi
    fi
  done
fi

echo "{\"systemMessage\": \"setup-deps: ${NOTES}\"}"
exit 0
