#!/usr/bin/env bash
# bash-guard.sh — PreToolUse hook para Bash
# Bloquea comandos peligrosos antes de que Claude los ejecute.
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

# Comandos destructivos sin confirmación explícita
BLOCKED_PATTERNS=(
    "rm -rf /"
    "rm -rf \*"
    "dd if=/dev/zero"
    "dd if=/dev/random"
    ":(){:|:&};:"
    "mkfs\."
    ">/dev/sd"
    "chmod -R 777 /"
    "chown -R.*/"
    "git push --force origin main"
    "git push -f origin main"
    "git push --force-with-lease origin main"
    "DROP TABLE"
    "DROP DATABASE"
    "TRUNCATE TABLE"
    "curl.*\| *bash"
    "wget.*\| *bash"
    "curl.*\| *sh"
    "wget.*\| *sh"
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$COMMAND" | grep -qiE "$pattern" 2>/dev/null; then
        echo "BLOQUEADO por bash-guard: patrón peligroso detectado: '$pattern'"
        echo "Comando: $COMMAND"
        exit 2
    fi
done

exit 0
