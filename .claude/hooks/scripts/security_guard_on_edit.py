#!/usr/bin/env python3
"""Hook: bandit security scan after editing a Python file
Triggered by: PostToolUse on Edit|Write|MultiEdit
Cost: 0 tokens (local) — advisory only, never blocks. Enforces security.md
(no shell=True, no hardcoded secrets) closer to the edit than manual review.
"""
import json, subprocess, sys


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
        out = subprocess.run(
            [sys.executable, "-m", "bandit", "-q", "-ll", fp],
            text=True,
            capture_output=True,
            timeout=20,
        )
        combined = (out.stdout + out.stderr).strip()
    except FileNotFoundError:
        sys.exit(0)
    except subprocess.TimeoutExpired:
        sys.exit(0)

    if combined and out.returncode != 0:
        lines = combined.split("\n")[:6]
        print(json.dumps({"systemMessage": "Security (bandit): " + "\n".join(lines)}))


if __name__ == "__main__":
    main()
