#!/usr/bin/env bash
# file-guard.sh — PreToolUse hook para Write|Edit
# Bloquea escrituras en rutas protegidas o archivos sensibles.
# Recibe JSON via stdin: {"tool_name":"Write","tool_input":{"file_path":"..."}}
# Exit 0 = permitir | Exit 2 = bloquear (mensaje a stdout)

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | python3 -c "
import json, sys
try:
    data = json.load(sys.stdin)
    path = data.get('tool_input', {}).get('file_path', '')
    print(path)
except Exception:
    print('')
" 2>/dev/null <<< "$INPUT")

# Archivos sensibles que nunca deben ser sobrescritos por un hook
BLOCKED_PATTERNS=(
    "\.env$"
    "\.env\."
    "secrets\."
    "credentials\."
    "id_rsa"
    "id_ed25519"
    "\.pem$"
    "\.key$"
    "\.pfx$"
    "\.p12$"
)

for pattern in "${BLOCKED_PATTERNS[@]}"; do
    if echo "$FILE_PATH" | grep -qiE "$pattern" 2>/dev/null; then
        echo "BLOQUEADO por file-guard: intento de escritura en archivo sensible."
        echo "Archivo: $FILE_PATH"
        echo "Patrón coincidente: $pattern"
        exit 2
    fi
done

# Rutas del sistema que nunca deben tocarse
BLOCKED_PATHS=(
    "/etc/"
    "/sys/"
    "/proc/"
    "/boot/"
    "C:/Windows/"
    "C:/System32/"
)

for blocked in "${BLOCKED_PATHS[@]}"; do
    if echo "$FILE_PATH" | grep -qiF "$blocked" 2>/dev/null; then
        echo "BLOQUEADO por file-guard: escritura en ruta del sistema no permitida."
        echo "Archivo: $FILE_PATH"
        exit 2
    fi
done

exit 0
