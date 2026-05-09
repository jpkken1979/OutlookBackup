#!/usr/bin/env bash
# Common utilities for Claude Code hooks
# Fixes Windows Git Bash PATH issues for Node.js/npm

set -uo pipefail

# Fix PATH for Windows Git Bash — Node.js usually installed here
_add_node_to_path() {
  local node_paths="/c/Program Files/nodejs"
  local npm_paths="/c/Program Files/nodejs"

  # Check if node is already in PATH
  if command -v node &>/dev/null; then
    return 0
  fi

  # Try common Windows Node.js installation paths
  for p in "$node_paths" "$npm_paths"; do
    if [ -x "$p/node.exe" ]; then
      export PATH="$p:$PATH"
      return 0
    fi
  done

  # Try to find node via where command (Windows)
  if command -v where &>/dev/null; then
    local node_path=$(where node 2>/dev/null | head -1)
    if [ -n "$node_path" ] && [ -x "$node_path" ]; then
      local node_dir=$(dirname "$node_path")
      export PATH="$node_dir:$PATH"
    fi
  fi
}

# Call this at the start of each hook that uses Node/npm
fix_windows_path() {
  _add_node_to_path
}

# Get project root directory
get_project_root() {
  cd "$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
  pwd
}

# Get repo root (alias for compatibility)
get_repo_root() {
  get_project_root
}