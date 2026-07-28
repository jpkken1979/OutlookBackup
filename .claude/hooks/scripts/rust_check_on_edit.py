#!/usr/bin/env python3
"""Hook: cargo check after editing Rust files in nexus-app/src-tauri
Triggered by: PostToolUse on Edit|Write|MultiEdit
Cost: local cargo check (incremental, no codegen) — advisory only, never blocks
"""
import json, subprocess, sys, os

TAURI_DIR = os.path.join("nexus-app", "src-tauri")


def main():
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)
    try:
        data = json.loads(raw)
        fp = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    except Exception:
        sys.exit(0)
    if not fp or not fp.endswith(".rs"):
        sys.exit(0)

    fp_norm = fp.replace("\\", "/")
    if "nexus-app/src-tauri" not in fp_norm:
        sys.exit(0)

    try:
        root = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL
        ).strip()
    except Exception:
        root = "."

    tauri_cwd = os.path.join(root, TAURI_DIR)
    if not os.path.isdir(tauri_cwd):
        sys.exit(0)

    try:
        out = subprocess.run(
            ["cargo", "check", "--quiet", "--message-format=short"],
            text=True,
            capture_output=True,
            cwd=tauri_cwd,
            timeout=90,
        )
        combined = (out.stdout + out.stderr).strip()
    except FileNotFoundError:
        sys.exit(0)
    except subprocess.TimeoutExpired:
        sys.exit(0)

    if combined and out.returncode != 0:
        lines = combined.split("\n")[:8]
        print(json.dumps({"systemMessage": "cargo check: " + "\n".join(lines)}))


if __name__ == "__main__":
    main()
