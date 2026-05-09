#!/usr/bin/env bash
set -uo pipefail
# Pre-commit code review reminder
# Checks if there are staged changes and suggests running /code-review

STAGED=$(git diff --cached --stat 2>/dev/null)

if [ -n "$STAGED" ]; then
  LINES_CHANGED=$(git diff --cached --numstat 2>/dev/null | awk '{s+=$1+$2} END {print s+0}')
  FILES_CHANGED=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')

  # Only suggest review for non-trivial changes
  if [ "$LINES_CHANGED" -gt 50 ] || [ "$FILES_CHANGED" -gt 3 ]; then
    echo "[code-review] $FILES_CHANGED archivos cambiados, $LINES_CHANGED lineas modificadas."
    echo "[code-review] Considerar ejecutar /code-review antes del commit."
  fi
fi

exit 0
