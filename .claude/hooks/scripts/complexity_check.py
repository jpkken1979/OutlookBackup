#!/usr/bin/env python3
"""Hook: Alert if Python function exceeds complexity budget (Python port of complexity-check.sh)
Triggered by: PostToolUse on Edit|Write for .py files
Cost: 0 tokens (local)
"""
import json, subprocess, sys, os

def main():
    raw = sys.stdin.read().strip()
    if not raw:
        sys.exit(0)
    try:
        data = json.loads(raw)
        fp = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    except Exception:
        sys.exit(0)
    if not fp or not fp.endswith(".py"):
        sys.exit(0)

    try:
        root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL).strip()
        os.chdir(root)
    except Exception:
        pass

    try:
        out = subprocess.check_output(["ruff", "check", fp, "--select", "C901", "--quiet"], text=True, stderr=subprocess.STDOUT).strip()
    except FileNotFoundError:
        sys.exit(0)
    except subprocess.CalledProcessError as e:
        out = (e.output or "").strip()

    if out:
        count = len([l for l in out.split("\n") if l.strip()])
        print(json.dumps({"systemMessage": f"Complejidad: {count} funcion(es) en {fp} superan C901. Considerar refactorizar."}))

if __name__ == "__main__":
    main()
