#!/usr/bin/env bash
set -uo pipefail
# Hook: Lint file after edit
# Triggered by: PostToolUse on Edit|Write
# Cost: 0 tokens (local bash)

# Source common utilities (includes Windows PATH fix)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common-utils.sh"
fix_windows_path

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',d.get('tool_response',{}).get('filePath','')))" 2>/dev/null)

[ -z "$FILE" ] && exit 0

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"

case "$FILE" in
  *.py)
    OUT=$(ruff check "$FILE" --quiet 2>&1 | head -5)
    if [ -n "$OUT" ]; then
      echo "{\"systemMessage\": \"Lint: $OUT\"}"
    fi
    ;;
  *.ts|*.tsx)
    if echo "$FILE" | grep -q "nexus-app/"; then
      OUT=$(cd nexus-app && npx eslint "$FILE" --quiet 2>&1 | tail -3)
    fi
    if [ -n "$OUT" ] && ! echo "$OUT" | grep -q "0 problems"; then
      echo "{\"systemMessage\": \"Lint: $OUT\"}"
    fi
    ;;
esac
