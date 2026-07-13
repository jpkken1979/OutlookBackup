#!/bin/bash
set -uo pipefail
# Hook: Alert if Python function exceeds complexity budget
# Triggered by: PostToolUse on Edit|Write for .py files
# Cost: 0 tokens (local bash)

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',d.get('tool_response',{}).get('filePath','')))" 2>/dev/null)

[ -z "$FILE" ] && exit 0
echo "$FILE" | grep -q '\.py$' || exit 0

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"

# Check C901 complexity on the edited file
OUT=$(ruff check "$FILE" --select C901 --quiet 2>&1)
if [ -n "$OUT" ]; then
  COUNT=$(echo "$OUT" | wc -l | tr -d ' ')
  echo "{\"systemMessage\": \"Complejidad: ${COUNT} funcion(es) en $FILE superan C901. Considerar refactorizar.\"}"
fi
