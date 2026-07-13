#!/bin/bash
# ─────────────────────────────────────────────────────────────────────────────
# Session End Hook — Auto-Memory Generator
#
# Runs automatically when a Claude Code session ends (hook "Stop").
# Detects:
#   1. Commands executed (from git log of this session)
#   2. Conventions learned (errors corrected, patterns discovered)
#   3. Files modified
# Then generates an auto-discovery entry in .claude/memory/
#
# Usage:
#   .claude/hooks/session_end.sh  # auto-invoked by Stop hook
#
# To enable manually:
#   bash .claude/hooks/session_end.sh
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
MEMORY_DIR="$REPO_ROOT/.claude/memory"
TIMESTAMP="$(date '+%Y%m%d_%H%M%S')"
OUTPUT_FILE="$MEMORY_DIR/auto_discovery_${TIMESTAMP}.md"

# ── Guards ───────────────────────────────────────────────────────────────────
if [ ! -d "$MEMORY_DIR" ]; then
    mkdir -p "$MEMORY_DIR"
fi

# ── Detect commands run in this session ──────────────────────────────────────
# We'll capture the session start time from environment or approximate via git log
SESSION_COMMANDS=""
COMMIT_COUNT=0

# Get commits made in the last 2 hours (approximate session length)
SINCE_TIME="${CLAUDE_SESSION_START:-2 hours ago}"
if command -v git >/dev/null 2>&1 && git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    RECENT_COMMITS=$(git -C "$REPO_ROOT" log --since="$SINCE_TIME" --oneline --format="%s" 2>/dev/null || echo "")
    if [ -n "$RECENT_COMMITS" ]; then
        SESSION_COMMANDS="# Comandos / Commits en esta sesion\n"
        while IFS= read -r line; do
            SESSION_COMMANDS+="- ${line}\n"
        done <<< "$RECENT_COMMITS"
        COMMIT_COUNT=$(echo "$RECENT_COMMITS" | wc -l)
    fi
fi

# ── Detect conventions learned ───────────────────────────────────────────────
# Heuristic: look at recent test failures, lint errors, or build errors
# captured in the last session. This is a lightweight scan.
CONVENTIONS_LEARNED=""
if [ -d "$REPO_ROOT/.claude/hooks" ]; then
    # Check if there were any guard violations (bash-guard, file-guard)
    GUARD_LOGS=$(find "$REPO_ROOT/.claude/hooks" -name "*.log" -newer "$REPO_ROOT/.git/index" 2>/dev/null | head -5 || true)
    if [ -n "$GUARD_LOGS" ]; then
        CONVENTIONS_LEARNED="# Convenciones aprendidas\n- Hooks activos detectaron violaciones en esta sesion\n"
    fi
fi

# ── Files modified ───────────────────────────────────────────────────────────
FILES_MODIFIED=""
if git -C "$REPO_ROOT" rev-parse --git-dir >/dev/null 2>&1; then
    MODIFIED_FILES=$(git -C "$REPO_ROOT" diff --name-only --cached 2>/dev/null; git -C "$REPO_ROOT" diff --name-only 2>/dev/null | sort -u || true)
    if [ -n "$MODIFIED_FILES" ]; then
        FILES_MODIFIED="# Archivos modificados\n"
        while IFS= read -r f; do
            FILES_MODIFIED+="- ${f}\n"
        done <<< "$MODIFIED_FILES"
    fi
fi

# ── Build output ─────────────────────────────────────────────────────────────
cat > "$OUTPUT_FILE" << 'HEADER'
---
name: auto_discovery_session
description: Auto-generado al cerrar sesion — comandos, convenciones aprendidas, archivos
type: project
auto_saved: true
trigger: session
date: TIMESTAMP_PLACEHOLDER
---

HEADER

# Replace placeholder with actual timestamp
sed -i "s/TIMESTAMP_PLACEHOLDER/$(date '+%Y-%m-%d %H:%M:%S')/" "$OUTPUT_FILE"

# Append sections only if non-empty
if [ -n "$SESSION_COMMANDS" ]; then
    echo -e "$SESSION_COMMANDS" >> "$OUTPUT_FILE"
fi

if [ -n "$CONVENTIONS_LEARNED" ]; then
    echo -e "$CONVENTIONS_LEARNED" >> "$OUTPUT_FILE"
fi

if [ -n "$FILES_MODIFIED" ]; then
    echo -e "$FILES_MODIFIED" >> "$OUTPUT_FILE"
fi

# Fallback: if nothing was detected, add a generic entry
if [ -z "$SESSION_COMMANDS" ] && [ -z "$CONVENTIONS_LEARNED" ] && [ -z "$FILES_MODIFIED" ]; then
    echo "# Sesion sin cambios detectados" >> "$OUTPUT_FILE"
fi

echo "Auto-memory generated: $OUTPUT_FILE"