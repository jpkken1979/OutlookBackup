#!/usr/bin/env python3
"""Detect test scope from PR number or branch name.

Maps changed files to routes and detects the dev server port.
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Optional


def run_cmd(cmd: list[str], check: bool = True) -> str:
    """Run a shell command and return stdout."""
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8", errors="replace",
            check=check,
            shell=False,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        if check:
            print(f"Error running {' '.join(cmd)}: {e.stderr}", file=sys.stderr)
            sys.exit(1)
        return ""


def get_changed_files_pr(pr_number: str) -> list[str]:
    """Get changed files from a PR number using gh."""
    output = run_cmd(["gh", "pr", "view", pr_number, "--json", "files"])
    if not output:
        return []
    data = json.loads(output)
    return [f["path"] for f in data.get("files", [])]


def get_changed_files_branch(branch: str) -> list[str]:
    """Get changed files between main and branch."""
    output = run_cmd(["git", "diff", "main", f"{branch}...", "--name-only"])
    if not output:
        return []
    return [line for line in output.split("\n") if line.strip()]


def get_changed_files_current() -> list[str]:
    """Get unstaged changed files."""
    output = run_cmd(["git", "diff", "--name-only"])
    if not output:
        return []
    return [line for line in output.split("\n") if line.strip()]


def detect_dev_port() -> int:
    """Detect dev server port from package.json, .env, or common defaults."""
    # Check package.json
    pkg_path = Path("package.json")
    if pkg_path.exists():
        try:
            import re

            content = pkg_path.read_text(encoding="utf-8")
            match = re.search(r'"dev":\s*"[^"]*--port[= ](\d+)"', content)
            if match:
                return int(match.group(1))
            match = re.search(r'"start":\s*"[^"]*--port[= ](\d+)"', content)
            if match:
                return int(match.group(1))
        except Exception:
            pass

    # Check .env
    env_path = Path(".env")
    if env_path.exists():
        try:
            import re

            content = env_path.read_text(encoding="utf-8")
            match = re.search(r"PORT=(\d+)", content)
            if match:
                return int(match.group(1))
        except Exception:
            pass

    # Check .env.local
    env_local = Path(".env.local")
    if env_local.exists():
        try:
            import re

            content = env_local.read_text(encoding="utf-8")
            match = re.search(r"PORT=(\d+)", content)
            if match:
                return int(match.group(1))
        except Exception:
            pass

    # Common defaults
    for port in [3000, 3001, 5173, 5174, 8080, 5174]:
        try:
            import socket

            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex(("localhost", port))
            sock.close()
            if result == 0:
                return port
        except Exception:
            pass

    return 3000


def map_files_to_routes(files: list[str]) -> list[str]:
    """Map changed files to Next.js/React routes."""
    routes: set[str] = set()

    for filepath in files:
        # Skip node_modules, git, lock files
        if any(x in filepath for x in ["node_modules/", ".git/", "package-lock", ".json"]):
            continue

        # pages/ directory
        if "/pages/" in filepath or filepath.startswith("pages/"):
            if filepath.endswith(".tsx") or filepath.endswith(".jsx"):
                route = filepath.replace("pages/", "/").replace(".tsx", "").replace(".jsx", "")
                if route.endswith("/index"):
                    route = route[:-6] or "/"
                elif route == "/index":
                    route = "/"
                routes.add(route)

        # app/ directory (Next.js 13+)
        elif "/app/" in filepath or filepath.startswith("app/"):
            if filepath.endswith(".tsx") or filepath.endswith(".jsx"):
                route = filepath.replace("app/", "/").replace(".tsx", "").replace(".jsx", "")
                if route.endswith("/page"):
                    route = route[:-5] or "/"
                if "layout" not in route.split("/")[-1]:
                    routes.add(route)

        # src/ components
        elif "/src/" in filepath:
            if "/components/" in filepath or "/pages/" in filepath:
                if filepath.endswith(".tsx") or filepath.endswith(".jsx"):
                    route = filepath.split("/src/")[-1]
                    route = "/" + route.replace(".tsx", "").replace(".jsx", "")
                    if "/components/" in route:
                        # Map component to potential page
                        pass
                    routes.add(route)

    return sorted(routes)


def detect_scope(arg: str) -> dict:
    """Main detection logic."""
    if arg.isdigit():
        # PR number
        files = get_changed_files_pr(arg)
    elif arg == "current":
        files = get_changed_files_current()
    else:
        # Assume branch name
        files = get_changed_files_branch(arg)

    routes = map_files_to_routes(files)
    port = detect_dev_port()

    return {
        "files": files,
        "routes": routes,
        "port": port,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Detect test scope from PR or branch")
    parser.add_argument("target", nargs="?", default="current", help="PR number, branch name, or 'current'")
    args = parser.parse_args()

    result = detect_scope(args.target)
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
