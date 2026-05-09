#!/bin/bash
set -uo pipefail
# Hook: PreToolUse — Read active task plan before each decision
# Triggered by: PreToolUse event
# Cost: 0 tokens (local bash, reads markdown)

PLANNING_DIR="${CLAUDE_PROJECT_DIR}/.claude/planning"
ACTIVE_DIR="${PLANNING_DIR}/active"
CURRENT_PLAN=""

# Find current plan (either explicit file or latest modified)
if [ -f "${ACTIVE_DIR}/current_plan.md" ]; then
  CURRENT_PLAN="${ACTIVE_DIR}/current_plan.md"
elif [ -f "${ACTIVE_DIR}/task_plan.md" ]; then
  CURRENT_PLAN="${ACTIVE_DIR}/task_plan.md"
fi

if [ -n "$CURRENT_PLAN" ] && [ -f "$CURRENT_PLAN" ]; then
  # Extract current phase and focus from plan
  PHASE=$(grep -m1 "^## Phase" "$CURRENT_PLAN" 2>/dev/null | sed 's/^## //')
  FOCUS=$(grep -A2 "Current Focus" "$CURRENT_PLAN" 2>/dev/null | tail -1 | sed 's/^> //')

  echo "{\"systemMessage\": \"[Planning] Plan: $(basename "$CURRENT_PLAN") | Phase: ${PHASE:-none} | Focus: ${FOCUS:-none}\"}"
else
  echo '{"suppressOutput": true}'
fi