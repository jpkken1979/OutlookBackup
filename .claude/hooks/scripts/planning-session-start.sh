#!/bin/bash
set -uo pipefail
# Hook: SessionStart — Detect /clear and recover session from git
# Triggered by: SessionStart event
# Cost: 0 tokens (local bash)

PLANNING_DIR="${CLAUDE_PROJECT_DIR}/.claude/planning"
ACTIVE_DIR="${PLANNING_DIR}/active"

# Check if there's an interrupted session (files modified but not committed)
if [ -d "$ACTIVE_DIR" ]; then
  # Check git status for uncommitted planning files
  cd "$CLAUDE_PROJECT_DIR" 2>/dev/null || exit 0

  if git diff --quiet .claude/planning/ 2>/dev/null; then
    # No local changes, check recent commits for planning activity
    recent_planning=$(git log --oneline -5 -- .claude/planning/ 2>/dev/null | head -1)
    if [ -n "$recent_planning" ]; then
      echo "{\"systemMessage\": \"[Planning] Recent: $recent_planning\"}"
    fi
  else
    # Uncommitted changes — session was interrupted
    echo "{\"systemMessage\": \"[Planning] Uncommitted changes in planning/ — run /plan recover to sync\"}"
  fi
fi

echo '{"suppressOutput": true}'
