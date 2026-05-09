#!/usr/bin/env bash
# git-block-force-push.sh — PreToolUse hook para Bash
# Bloquea específicamente force-push a ramas protegidas (main, master, release/*).
# Recibe JSON via stdin: {"tool_name":"Bash","tool_input":{"command":"..."}}
# Exit 0 = permitir | Exit 2 = bloquear (mensaje a stdout)

INPUT=$(cat)
COMMAND=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    cmd = data.get('tool_input', {}).get('command', '')
    print(cmd)
except Exception:
    print('')
" 2>/dev/null <<< "$INPUT")

# Detectar force-push a ramas protegidas
if echo "$COMMAND" | grep -qE "git\s+push" 2>/dev/null; then
    if echo "$COMMAND" | grep -qE "\-\-force|\-f\b|--force-with-lease" 2>/dev/null; then
        if echo "$COMMAND" | grep -qE "\b(main|master|release/[^\s]+)\b" 2>/dev/null; then
            echo "BLOQUEADO por git-block-force-push: force-push a rama protegida detectado."
            echo "Comando: $COMMAND"
            echo "Para forzar igualmente, el usuario debe ejecutar el comando manualmente."
            exit 2
        fi
    fi
fi

exit 0
