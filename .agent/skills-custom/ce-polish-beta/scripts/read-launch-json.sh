#!/usr/bin/env bash
# read-launch-json.sh — Parse .claude/launch.json if it exists
# Outputs JSON payload or empty string if not found/not parseable.

set -euo pipefail

LAUNCH_FILE="${1:-.claude/launch.json}"

if [[ ! -f "$LAUNCH_FILE" ]]; then
    echo ""
    exit 0
fi

# Validate it's JSON before attempting parse
if ! python3 -c "import json; json.load(open('$LAUNCH_FILE'))" 2>/dev/null; then
    echo ""
    exit 0
fi

python3 -c "
import json
import sys

with open('$LAUNCH_FILE') as f:
    data = json.load(f)

configs = data.get('configurations', [])
for cfg in configs:
    name = cfg.get('name', '')
    cmd = cfg.get('command', '')
    url  = cfg.get('url', '')
    port = cfg.get('port', '')
    cwd  = cfg.get('cwd', '')
    # Prefer configs that look like dev server launches
    if cmd or url:
        print(json.dumps({
            'name': name,
            'command': cmd,
            'url': url,
            'port': port,
            'cwd': cwd
        }))
        break
"
