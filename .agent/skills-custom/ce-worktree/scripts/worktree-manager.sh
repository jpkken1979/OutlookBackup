#!/usr/bin/env bash
# Git Worktree Manager — Enhanced Edition
# create | list | switch | cleanup

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SKILL_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKTREES_DIR="${WORKTREES_DIR:-.worktrees}"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

info() { echo -e "${BLUE}[INFO]${NC} $*"; }
success() { echo -e "${GREEN}[OK]${NC} $*"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
error() { echo -e "${RED}[ERROR]${NC} $*" >&2; }

# Get the main repo root (where .git lives)
get_main_repo() {
    git rev-parse --show-toplevel 2>/dev/null
}

# Check for uncommitted changes
check_clean_working_tree() {
    local repo="${1:-$(get_main_repo)}"
    if [ -z "$repo" ]; then
        error "Not in a git repository"
        return 1
    fi

    cd "$repo"
    if [ -n "$(git status --short)" ]; then
        error "Working tree has uncommitted changes. Commit or stash them first."
        git status --short
        return 1
    fi
    return 0
}

# Check if branch exists
branch_exists() {
    local branch="$1"
    git rev-parse --verify "$branch" >/dev/null 2>&2
}

# Check if worktree directory exists
worktree_dir_exists() {
    local worktree_name="$1"
    local main_repo="${2:-$(get_main_repo)}"
    [ -d "$main_repo/$WORKTREES_DIR/$worktree_name" ]
}

# Copy .env file to worktree
sync_env_file() {
    local src="$1"
    local dest="$2"

    if [ -f "$src/.env" ]; then
        cp "$src/.env" "$dest/.env"
        success "Copied .env to $dest"
    else
        warn "No .env found in main repo (this is normal if no secrets are needed)"
    fi
}

# Copy branch-aware dev tools (mise, direnv)
sync_dev_tools() {
    local src="$1"
    local dest="$2"

    # mise.toml / mise.yaml
    if [ -f "$src/mise.toml" ]; then
        cp "$src/mise.toml" "$dest/mise.toml"
        success "Copied mise.toml"
    elif [ -f "$src/mise.yaml" ]; then
        cp "$src/mise.yaml" "$dest/mise.yaml"
        success "Copied mise.yaml"
    fi

    # .mise.toml local override
    if [ -f "$src/.mise.toml" ]; then
        cp "$src/.mise.toml" "$dest/.mise.toml"
        success "Copied .mise.toml"
    fi

    # .envrc (direnv)
    if [ -f "$src/.envrc" ]; then
        cp "$src/.envrc" "$dest/.envrc"
        success "Copied .envrc"
    fi

    # .tool-versions (asdf compatible)
    if [ -f "$src/.tool-versions" ]; then
        cp "$src/.tool-versions" "$dest/.tool-versions"
        success "Copied .tool-versions"
    fi
}

# Ensure .worktrees directory exists
ensure_worktrees_dir() {
    local main_repo="${1:-$(get_main_repo)}"
    mkdir -p "$main_repo/$WORKTREES_DIR"
}

# cmd: create
cmd_create() {
    local branch_name="${1:-}"
    local from_branch="${2:-main}"

    if [ -z "$branch_name" ]; then
        error "Usage: $0 create <branch-name> [from-branch]"
        return 1
    fi

    local main_repo
    main_repo="$(get_main_repo)"
    if [ -z "$main_repo" ]; then
        error "Not in a git repository"
        return 1
    fi

    info "Main repo: $main_repo"
    info "Creating worktree for branch: $branch_name (from: $from_branch)"

    # Safety check: clean working tree
    info "Checking working tree status..."
    if ! check_clean_working_tree "$main_repo"; then
        return 1
    fi
    success "Working tree is clean"

    # Safety: check if branch already exists
    if branch_exists "$branch_name"; then
        error "Branch '$branch_name' already exists locally"
        return 1
    fi

    # Safety: check if worktree directory exists
    if worktree_dir_exists "$branch_name" "$main_repo"; then
        error "Worktree directory already exists: $main_repo/$WORKTREES_DIR/$branch_name"
        return 1
    fi

    # Ensure .worktrees dir exists
    ensure_worktrees_dir "$main_repo"

    # Create worktree
    local worktree_path="$main_repo/$WORKTREES_DIR/$branch_name"
    info "Creating worktree at: $worktree_path"

    if ! git worktree add -b "$branch_name" "$worktree_path" "$from_branch"; then
        error "Failed to create worktree"
        return 1
    fi
    success "Worktree created: $worktree_path"

    # Sync .env
    info "Syncing .env file..."
    sync_env_file "$main_repo" "$worktree_path"

    # Sync dev tools
    info "Syncing dev tools (mise/direnv)..."
    sync_dev_tools "$main_repo" "$worktree_path"

    # Ensure .gitignore has .worktrees
    if ! grep -q "$WORKTREES_DIR" "$main_repo/.gitignore" 2>/dev/null; then
        info "Adding $WORKTREES_DIR/ to .gitignore..."
        echo -e "\n# Git worktrees\n$WORKTREES_DIR/" >> "$main_repo/.gitignore"
        success "Updated .gitignore"
    fi

    success "Worktree '$branch_name' is ready!"
    success "cd $worktree_path"
}

# cmd: list
cmd_list() {
    echo ""
    echo -e "${BLUE}=== Git Worktrees${NC}"
    echo ""
    git worktree list
    echo ""
}

# cmd: switch
cmd_switch() {
    local worktree_name="${1:-}"

    if [ -z "$worktree_name" ]; then
        error "Usage: $0 switch <worktree-name>"
        return 1
    fi

    local main_repo
    main_repo="$(get_main_repo)"
    if [ -z "$main_repo" ]; then
        error "Not in a git repository"
        return 1
    fi

    local worktree_path="$main_repo/$WORKTREES_DIR/$worktree_name"

    if [ ! -d "$worktree_path" ]; then
        error "Worktree not found: $worktree_path"
        return 1
    fi

    info "Switching to worktree: $worktree_name"
    cd "$worktree_path"
    success "Now in: $(pwd)"
    success "Run 'git status' to see the current state"
}

# cmd: cleanup
cmd_cleanup() {
    local main_repo
    main_repo="$(get_main_repo)"
    if [ -z "$main_repo" ]; then
        error "Not in a git repository"
        return 1
    fi

    info "Scanning for orphaned worktrees in: $main_repo/$WORKTREES_DIR/"

    if [ ! -d "$main_repo/$WORKTREES_DIR" ]; then
        success "No .worktrees directory found — nothing to clean"
        return 0
    fi

    local orphaned=()
    while IFS= read -r -d '' worktree_path; do
        local worktree_name
        worktree_name="$(basename "$worktree_path")"

        # Check if the worktree directory is actually in git worktree list
        if ! git worktree list | grep -q "$worktree_path"; then
            orphaned+=("$worktree_path")
        fi
    done < <(find "$main_repo/$WORKTREES_DIR" -mindepth 1 -maxdepth 1 -type d -print0 2>/dev/null)

    if [ ${#orphaned[@]} -eq 0 ]; then
        success "No orphaned worktrees found"
        return 0
    fi

    echo ""
    warn "Found ${#orphaned[@]} orphaned worktree(s):"
    for wt in "${orphaned[@]}"; do
        echo "  - $wt"
    done
    echo ""

    read -rp "Remove these orphaned worktrees? [y/N] " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        for wt in "${orphaned[@]}"; do
            rm -rf "$wt"
            success "Removed: $wt"
        done
        success "Cleanup complete"
    else
        info "Cleanup cancelled"
    fi
}

# Main dispatcher
main() {
    local command="${1:-}"
    shift 2>/dev/null || true

    case "$command" in
        create|list|switch|cleanup)
            "cmd_$command" "$@"
            ;;
        "")
            echo "Git Worktree Manager — Enhanced Edition"
            echo ""
            echo "Usage: $0 <command> [options]"
            echo ""
            echo "Commands:"
            echo "  create <branch> [from-branch]  Create a new worktree"
            echo "  list                         List all worktrees"
            echo "  switch <name>                Switch to a worktree"
            echo "  cleanup                      Remove orphaned worktrees"
            echo ""
            ;;
        *)
            error "Unknown command: $command"
            error "Usage: $0 <create|list|switch|cleanup>"
            return 1
            ;;
    esac
}

main "$@"
