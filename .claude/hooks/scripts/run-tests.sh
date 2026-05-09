#!/usr/bin/env bash
set -uo pipefail
# Hook: Run tests when Claude stops working
# Triggered by: Stop event
# Cost: 0 tokens (local bash, no LLM invocation)

# Source common utilities (includes Windows PATH fix)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common-utils.sh"
fix_windows_path

cd "$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"

# Check which files were modified (unstaged changes)
CHANGED_PY=$(git diff --name-only 2>/dev/null | grep -c '\.py$' || echo 0)
CHANGED_TS=$(git diff --name-only 2>/dev/null | grep -c '\.\(ts\|tsx\)$' || echo 0)
CHANGED_RS=$(git diff --name-only 2>/dev/null | grep -c '\.rs$' || echo 0)

RESULTS=""
FAILED=0

# Python tests (if .py files changed)
if [ "$CHANGED_PY" -gt 0 ]; then
  PY_OUT=$(python -m pytest tests/ -x -q --tb=line 2>&1 | tail -3)
  PY_EXIT=$?
  if [ $PY_EXIT -eq 0 ]; then
    RESULTS="${RESULTS}Python: PASS\n"
  else
    RESULTS="${RESULTS}Python: FAIL - ${PY_OUT}\n"
    FAILED=1
  fi
fi

# TypeScript bot tests (if .ts files in src/ changed)
if [ "$CHANGED_TS" -gt 0 ] && git diff --name-only 2>/dev/null | grep -q '^src/'; then
  TS_OUT=$(npx vitest run --config vitest.config.ts 2>&1 | tail -3)
  TS_EXIT=$?
  if [ $TS_EXIT -eq 0 ]; then
    RESULTS="${RESULTS}Bot TS: PASS\n"
  else
    RESULTS="${RESULTS}Bot TS: FAIL - ${TS_OUT}\n"
    FAILED=1
  fi
fi

# Nexus tests (if .ts/.tsx files in nexus-app/ changed)
if [ "$CHANGED_TS" -gt 0 ] && git diff --name-only 2>/dev/null | grep -q '^nexus-app/'; then
  NX_OUT=$(cd nexus-app && npx vitest run 2>&1 | tail -3)
  NX_EXIT=$?
  if [ $NX_EXIT -eq 0 ]; then
    RESULTS="${RESULTS}Nexus: PASS\n"
  else
    RESULTS="${RESULTS}Nexus: FAIL - ${NX_OUT}\n"
    FAILED=1
  fi
fi

# No changes detected
if [ -z "$RESULTS" ]; then
  echo '{"suppressOutput": true}'
  exit 0
fi

# Output results as JSON for Claude to see
if [ $FAILED -eq 0 ]; then
  MSG=$(echo -e "Tests passed:\n${RESULTS}" | tr '\n' ' ')
  echo "{\"systemMessage\": \"${MSG}\"}"
else
  MSG=$(echo -e "Tests FAILED:\n${RESULTS}" | tr '\n' ' ')
  echo "{\"systemMessage\": \"${MSG}\"}"
fi
