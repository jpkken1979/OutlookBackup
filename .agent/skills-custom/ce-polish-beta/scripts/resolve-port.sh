#!/usr/bin/env bash
# resolve-port.sh — Resolve dev server port from config or framework defaults.
# Priority: launch.json port > .env / .env.local > vite.config > next.config > default
# Usage: resolve-port.sh [project_dir]

set -euo pipefail

PROJECT_DIR="${1:-.}"

port_from_launch_json() {
    local launch_file="$PROJECT_DIR/.claude/launch.json"
    if [[ -f "$launch_file" ]]; then
        python3 -c "
import json, sys
with open('$launch_file') as f:
    data = json.load(f)
for cfg in data.get('configurations', []):
    p = cfg.get('port', '')
    if p:
        print(p)
        sys.exit(0)
"
    fi
}

port_from_env() {
    if [[ -f "$PROJECT_DIR/.env.local" ]]; then
        grep -oP 'PORT=\K\d+' "$PROJECT_DIR/.env.local" 2>/dev/null && return 0
    fi
    if [[ -f "$PROJECT_DIR/.env" ]]; then
        grep -oP 'PORT=\K\d+' "$PROJECT_DIR/.env" 2>/dev/null && return 0
    fi
}

port_from_vite_config() {
    if [[ -f "$PROJECT_DIR/vite.config.js" ]] || [[ -f "$PROJECT_DIR/vite.config.ts" ]]; then
        grep -oP 'port:\s*\K\d+' "$PROJECT_DIR"/vite.config.* 2>/dev/null && return 0
    fi
}

port_from_next_config() {
    if [[ -f "$PROJECT_DIR/next.config.js" ]] || [[ -f "$PROJECT_DIR/next.config.mjs" ]]; then
        grep -oP 'port:\s*\K\d+' "$PROJECT_DIR"/next.config.* 2>/dev/null && return 0
    fi
}

default_port_for() {
    local type="$1"
    case "$type" in
        rails)   echo 3000 ;;
        next)    echo 3000 ;;
        vite)    echo 5173 ;;
        nuxt)    echo 3000 ;;
        astro)   echo 4321 ;;
        remix)   echo 3000 ;;
        sveltekit) echo 5173 ;;
        *)       echo 3000 ;;
    esac
}

# Try in order
port_from_launch_json && exit 0
port_from_env        && exit 0
port_from_vite_config && exit 0
port_from_next_config && exit 0

# Fallback via detected type passed as arg
if [[ -n "${DETECTED_TYPE:-}" ]]; then
    default_port_for "$DETECTED_TYPE"
else
    echo 3000
fi
