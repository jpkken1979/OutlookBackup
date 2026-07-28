#!/usr/bin/env python3
"""Hook: Lint file after edit (Python port of lint-on-edit.sh)
Triggered by: PostToolUse on Edit|Write
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
    if not fp:
        sys.exit(0)

    # cd to repo root
    try:
        root = subprocess.check_output(["git", "rev-parse", "--show-toplevel"], text=True, stderr=subprocess.DEVNULL).strip()
        os.chdir(root)
    except Exception:
        pass

    if fp.endswith(".py"):
        try:
            out = subprocess.check_output(["ruff", "check", fp, "--quiet"], text=True, stderr=subprocess.STDOUT).strip()
            lines = out.split("\n")[:5]
            out = "\n".join(lines)
        except FileNotFoundError:
            out = ""
        except subprocess.CalledProcessError as e:
            out = (e.output or "").strip().split("\n")[:5]
            out = "\n".join(out)
        if out:
            print(json.dumps({"systemMessage": f"Lint: {out}"}))

    elif fp.endswith((".ts", ".tsx")):
        if "nexus-app/" in fp:
            try:
                out = subprocess.check_output(
                    ["npx", "eslint", fp, "--quiet"],
                    text=True, stderr=subprocess.STDOUT, cwd=os.path.join(root, "nexus-app") if root else "nexus-app"
                ).strip()
                lines = out.split("\n")[-3:]
                out = "\n".join(lines)
            except Exception:
                out = ""
            if out and "0 problems" not in out:
                print(json.dumps({"systemMessage": f"Lint: {out}"}))

if __name__ == "__main__":
    main()
