#!/bin/bash
set -uo pipefail
# Hook: Auto-sync memories to repo on stop
# Triggered by: Stop event
# Cost: 0 tokens (local bash)

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
REPO_ROOT="$(pwd)"

build_project_slug() {
  local input="$1"
  local normalized="$input"

  normalized="${normalized//\\//}"

  if [[ "$normalized" =~ ^/([a-zA-Z])/(.*)$ ]]; then
    local drive="${BASH_REMATCH[1]^}"
    local rest="${BASH_REMATCH[2]}"
    echo "${drive}--${rest//\//-}"
    return 0
  fi

  if [[ "$normalized" =~ ^([a-zA-Z]):/?(.*)$ ]]; then
    local drive="${BASH_REMATCH[1]^}"
    local rest="${BASH_REMATCH[2]}"
    rest="${rest#/}"
    echo "${drive}--${rest//\//-}"
    return 0
  fi

  normalized="${normalized#/}"
  echo "${normalized//\//-}"
}

# Source: Claude Code auto-memory
PROJECT_SLUG="$(build_project_slug "$REPO_ROOT")"
SRC="$HOME/.claude/projects/$PROJECT_SLUG/memory"
# Destination: project repo (tracked by git)
DST=".claude/memory"

[ ! -d "$SRC" ] && exit 0
mkdir -p "$DST"

SYNCED=0
for f in "$SRC"/*.md; do
  [ ! -f "$f" ] && continue
  BASENAME=$(basename "$f")
  if [ ! -f "$DST/$BASENAME" ] || ! cmp -s "$f" "$DST/$BASENAME"; then
    cp "$f" "$DST/$BASENAME"
    SYNCED=$((SYNCED + 1))
  fi
done

if [ "$SYNCED" -gt 0 ]; then
  echo "{\"systemMessage\": \"Memorias: ${SYNCED} archivo(s) sincronizados a .claude/memory/\"}"
else
  echo '{"suppressOutput": true}'
fi

# === AUTO-COMMIT BRAIN CHANGES ===
# Todo cambio en .agent/brain/ y .claude/memory/ debe subirse a git
# inmediatamente para sincronizar entre PCs.

cd "$REPO_ROOT"

# Agregar todo lo que cambie en brain y memories (sin hacer add de todo el repo)
BRAIN_CHANGES=$(git status --porcelain .agent/brain/ .claude/memory/ 2>/dev/null | grep -v '^??' | wc -l)

if [ "$BRAIN_CHANGES" -gt 0 ]; then
  # SECURITY: scan por secrets antes del git add automatico.
  # Patrones comunes que NO deberian llegar a git: API keys, tokens, passwords.
  # Si detectamos algo, abortamos el auto-commit y avisamos al usuario.
  STAGED_FILES=$(git status --porcelain .agent/brain/ .claude/memory/ 2>/dev/null | awk '{print $2}')
  SECRETS_FOUND=0
  for FILE in $STAGED_FILES; do
    [ ! -f "$FILE" ] && continue
    # Patrones: ghp_/gho_/ghs_ (GitHub), sk-proj-/sk-ant-/sk-cp- (LLM APIs),
    # AKIA (AWS), nvapi- (NVIDIA), generic API_KEY=... con valor largo.
    if grep -qE '(ghp_|gho_|ghs_|sk-proj-|sk-ant-|sk-cp-|AKIA[0-9A-Z]{16}|nvapi-[a-zA-Z0-9_\-]{30,}|API_KEY\s*=\s*[a-zA-Z0-9_\-]{30,})' "$FILE" 2>/dev/null; then
      SECRETS_FOUND=$((SECRETS_FOUND + 1))
      echo "[Antigravity Memory] SECRET DETECTADO en $FILE - aborto auto-commit" >&2
    fi
  done

  if [ "$SECRETS_FOUND" -gt 0 ]; then
    echo "{\"systemMessage\": \"WARNING: ${SECRETS_FOUND} archivo(s) con posibles secrets - auto-commit abortado. Revisa manualmente y commitea con --no-verify si confirmas que es seguro.\"}"
    exit 0
  fi

  git add .agent/brain/ .claude/memory/

  # Obtener fecha actual para el mensaje
  DATE=$(date '+%Y-%m-%d')
  git commit -m "chore(memory): sincronizar memorias y brain ($DATE)

Co-Authored-By: Claude <noreply@anthropic.com>" 2>/dev/null

  # Intentar push (si falla, es critico — el usuario pierde memorias entre PCs)
  if git push 2>/dev/null; then
    echo "{\"systemMessage\": \"Brain + memorias subidos a git\"}"
  else
    # Push falló — notificar visiblemente. El usuario debe saberlo.
    echo "{\"systemMessage\": \"WARNING: Brain + memorias quedaron en commit local. Push falló (offline o sin acceso).\"}"
    echo "[Antigravity Memory] Push falló — tus memorias no sincronizan con otras PCs hasta que hagas git push manualmente"
  fi
fi

# Sync planning files (active plans)
PLANNING_SRC="$HOME/.claude/projects/$PROJECT_SLUG/planning"
PLANNING_DST=".claude/planning"
mkdir -p "$PLANNING_DST"
if [ -d "$PLANNING_SRC" ]; then
  for f in "$PLANNING_SRC"/**/*.md; do
    [ ! -f "$f" ] && continue
    BASENAME=$(basename "$f")
    if [ ! -f "$PLANNING_DST/$BASENAME" ] || ! cmp -s "$f" "$PLANNING_DST/$BASENAME"; then
      cp "$f" "$PLANNING_DST/$BASENAME"
    fi
  done
fi
