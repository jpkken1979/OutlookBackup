#!/bin/bash
set -uo pipefail
# Hook: CLAUDE.md drift check
# Triggered by: Stop event
# Cost: 0 tokens (local bash + python dry-run)
#
# Corre refresh_claude_md.py en modo dry-run (sin --apply). Si los bloques
# AUTO:versions / AUTO:counts del CLAUDE.md estan desfasados respecto al
# filesystem real, emite un systemMessage recordando correr el refresh.
#
# NO modifica ni commitea nada automaticamente: solo avisa. El usuario decide
# cuando aplicar (py .agent/scripts/refresh_claude_md.py --apply).

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo ".")" || exit 0
REPO_ROOT="$(pwd)"

SCRIPT="$REPO_ROOT/.agent/scripts/refresh_claude_md.py"
PY_RESOLVER="$REPO_ROOT/.claude/hooks/scripts/run-python.sh"

# Guards: si falta el script o el resolver, salir silencioso (no romper el Stop).
# Nota: chequeamos -f (no -x): el bit ejecutable no persiste al clonar en
# Windows/git, por eso invocamos con `bash` explicito como el resto de hooks.
[ -f "$SCRIPT" ] || exit 0
[ -f "$PY_RESOLVER" ] || exit 0

# Dry-run: el script imprime "Cambios detectados" en stdout/stderr si hay drift.
OUTPUT="$(bash "$PY_RESOLVER" "$SCRIPT" --root "$REPO_ROOT" 2>&1 || true)"

if printf '%s' "$OUTPUT" | grep -q "Cambios detectados"; then
    printf '%s\n' '{"systemMessage":"CLAUDE.md tiene drift en los conteos/versiones (AUTO: blocks). Corre: py .agent/scripts/refresh_claude_md.py --apply"}'
fi

exit 0
