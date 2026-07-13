#!/bin/bash
set -uo pipefail
# Hook: PostToolUse — Update progress.md after significant actions
# Triggered by: PostToolUse event
# Cost: 0 tokens (local bash)

PLANNING_DIR="${CLAUDE_PROJECT_DIR}/.claude/planning"
ACTIVE_DIR="${PLANNING_DIR}/active"
PROGRESS_FILE="${ACTIVE_DIR}/progress.md"

[ ! -f "$PROGRESS_FILE" ] && exit 0

# Read tool name and result from hook input
input=$(cat)
tool_name=$(echo "$input" | jq -r '.tool_name // ""')
file_path=$(echo "$input" | jq -r '.tool_input.file_path // ""')

# Only track significant file changes
case "$tool_name" in
  Edit|Write)
    if [ -n "$file_path" ] && [[ "$file_path" == *.py || "$file_path" == *.ts || "$file_path" == *.tsx || "$file_path" == *.rs ]]; then
      timestamp=$(date "+%H:%M")
      echo "- $timestamp - $tool_name: $(basename "$file_path")" >> "$PROGRESS_FILE"
    fi
    ;;
esac

echo '{"suppressOutput": true}'
