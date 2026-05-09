#!/bin/bash
set -uo pipefail
# Hook: Show uncommitted changes when Claude stops
# Triggered by: Stop event
# Cost: 0 tokens (local bash)

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"

STAGED=$(git diff --cached --name-only 2>/dev/null | wc -l | tr -d ' ')
UNSTAGED=$(git diff --name-only 2>/dev/null | wc -l | tr -d ' ')
UNTRACKED=$(git ls-files --others --exclude-standard 2>/dev/null | wc -l | tr -d ' ')

TOTAL=$((STAGED + UNSTAGED + UNTRACKED))

if [ "$TOTAL" -eq 0 ]; then
  echo '{"suppressOutput": true}'
  exit 0
fi

MSG="Git: ${UNSTAGED} modificados, ${STAGED} staged, ${UNTRACKED} nuevos sin trackear"
echo "{\"systemMessage\": \"${MSG}\"}"
