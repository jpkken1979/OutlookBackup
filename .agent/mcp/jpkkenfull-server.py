#!/usr/bin/env python3
"""
Jpkkenfull MCP Server v2.0
==========================
Exposes the jpkkenfull autonomous executor as an MCP tool.
Adds abort and status tools on top of v1.0.

v2.0 tools:
- run_jpkkenfull: Execute autonomous goal (existing)
- abort_jpkkenfull: Cancel running execution (new)
- get_jpkkenfull_status: Query execution state (new)
- list_jpkkenfull_tools: List tools (existing)
"""

from __future__ import annotations

import json
import logging
import sys
import os
import signal
from pathlib import Path
from typing import Optional

# ── Configuration ────────────────────────────────────────────────────────────

SKILL_DIR = Path(__file__).parent.parent
SCRIPT = SKILL_DIR / "scripts" / "main.py"
REPO_ROOT = Path(os.environ.get(
    "ANTIGRAVITY_ROOT",
    Path(__file__).resolve().parents[3]
))

# ── Logging ─────────────────────────────────────────────────────────────────

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)

# ── Execution state (shared across invocations) ──────────────────────────────

class ExecutionState:
    """Lightweight in-memory state for abort/status tracking."""

    def __init__(self) -> None:
        self.running: bool = False
        self.goal: str = ""
        self.started_at: Optional[float] = None
        self.process_pid: Optional[int] = None
        self.aborted: bool = False

_state = ExecutionState()


def _signal_child() -> None:
    """Send SIGINT to child process if we have one."""
    if _state.process_pid and _state.running:
        try:
            os.kill(_state.process_pid, signal.SIGINT)
            logger.info("Sent SIGINT to child PID %d", _state.process_pid)
        except ProcessLookupError:
            pass
        except Exception as e:
            logger.warning("Failed to signal child: %s", e)


# ── MCP Server transport ──────────────────────────────────────────────────────

STDIO_HEADER = b"Content-Length: "


def read_message() -> dict | None:
    """Read one JSON-RPC message from stdin."""
    try:
        header = b""
        while True:
            chunk = sys.stdin.buffer.read(1)
            if not chunk:
                return None
            header += chunk
            if header.endswith(b"\r\n\r\n"):
                break
        length = 0
        for line in header.decode("utf-8").splitlines():
            if line.startswith("Content-Length:"):
                length = int(line.split(":")[1].strip())
        if length:
            body = sys.stdin.buffer.read(length)
            return json.loads(body.decode("utf-8"))
    except Exception as e:
        logger.error("read_message error: %s", e)
        return None


def write_message(data: dict) -> None:
    """Write one JSON-RPC message to stdout."""
    try:
        body = json.dumps(data, ensure_ascii=False)
        response = f"Content-Length: {len(body.encode('utf-8'))}\r\n\r\n{body}"
        sys.stdout.write(response)
        sys.stdout.flush()
    except Exception as e:
        logger.error("write_message error: %s", e)


def send_result(msg_id: int | str | None, result: dict) -> None:
    write_message({"jsonrpc": "2.0", "id": msg_id, "result": result})


def send_error(msg_id: int | str | None, code: int, message: str, data: dict | None = None) -> None:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    write_message({"jsonrpc": "2.0", "id": msg_id, "error": err})


# ── Tool handlers ─────────────────────────────────────────────────────────────

def handle_run_jpkkenfull(params: dict) -> dict:
    """Run jpkkenfull with a goal."""
    import subprocess
    import shlex
    import time

    global _state

    goal = params.get("goal", "")
    context_hints = params.get("context", "")
    force_internet = bool(params.get("force_internet", False))
    skip_agents = bool(params.get("skip_agents", False))

    if not goal:
        return {"success": False, "error": "goal is required"}

    if _state.running:
        return {
            "success": False,
            "error": "An execution is already running. Use abort_jpkkenfull first.",
            "running_goal": _state.goal,
        }

    cmd = [sys.executable, str(SCRIPT), "--goal", goal, "--json"]
    if context_hints:
        cmd.extend(["--context", context_hints])
    if force_internet:
        cmd.append("--force_internet")
    if skip_agents:
        cmd.append("--skip_agents")

    _state.running = True
    _state.goal = goal
    _state.started_at = time.time()
    _state.aborted = False

    try:
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        _state.process_pid = proc.pid

        try:
            stdout, stderr = proc.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            _state.running = False
            _state.process_pid = None
            return {"success": False, "error": f"Timeout after 300s"}

        _state.running = False
        _state.process_pid = None
        stdout = stdout.strip()

        try:
            output = json.loads(stdout)
        except Exception:
            output = {"raw": stdout, "stderr": stderr}

        return {
            "success": proc.returncode == 0,
            "exit_code": proc.returncode,
            "output": output,
            "stderr": stderr[:500] if stderr else None,
        }
    except Exception as e:
        _state.running = False
        _state.process_pid = None
        return {"success": False, "error": str(e)}


def handle_abort_jpkkenfull(params: dict) -> dict:
    """Abort a running jpkkenfull execution."""
    global _state

    if not _state.running:
        return {
            "success": False,
            "error": "No execution is currently running",
        }

    _state.aborted = True
    _signal_child()
    return {
        "success": True,
        "message": "Abort signal sent",
        "goal": _state.goal,
        "aborted": True,
    }


def handle_get_jpkkenfull_status(params: dict) -> dict:
    """Get current execution status."""
    global _state

    del params  # unused

    if not _state.running:
        return {
            "running": False,
            "goal": None,
            "started_at": None,
            "aborted": False,
        }

    import time
    elapsed = time.time() - _state.started_at if _state.started_at else 0

    return {
        "running": _state.running,
        "goal": _state.goal,
        "started_at": _state.started_at,
        "elapsed_seconds": round(elapsed, 1),
        "process_pid": _state.process_pid,
        "aborted": _state.aborted,
    }


def handle_list_tools(params: dict) -> dict:
    """List available jpkkenfull tools."""
    del params  # unused
    return {
        "tools": [
            {
                "name": "run_jpkkenfull",
                "description": "Execute any goal autonomously without per-step permissions. "
                                "Gathers context from memory/Brain/rules, selects best agents/skills, "
                                "executes completely, auto-improves via Brain. "
                                "Only asks ONE clarifying question if genuinely lost.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "goal": {
                            "type": "string",
                            "description": "The objective to execute (e.g. 'fix the memory leak in nexus-app')",
                        },
                        "context": {
                            "type": "string",
                            "description": "Additional context hints to guide execution",
                        },
                        "force_internet": {
                            "type": "boolean",
                            "description": "Force web search even if context exists",
                        },
                        "skip_agents": {
                            "type": "boolean",
                            "description": "Skip agent selection, use only skills and subprocess",
                        },
                    },
                    "required": ["goal"],
                },
            },
            {
                "name": "abort_jpkkenfull",
                "description": "Abort a running jpkkenfull execution. Sends SIGINT to the child process.",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "get_jpkkenfull_status",
                "description": "Get current execution state (running/goal/elapsed/aborted).",
                "input_schema": {
                    "type": "object",
                    "properties": {},
                },
            },
            {
                "name": "list_jpkkenfull_tools",
                "description": "List available jpkkenfull tools",
                "input_schema": {"type": "object", "properties": {}},
            },
        ]
    }


# ── MCP Request Router ─────────────────────────────────────────────────────────

METHODS = {
    "run_jpkkenfull": handle_run_jpkkenfull,
    "abort_jpkkenfull": handle_abort_jpkkenfull,
    "get_jpkkenfull_status": handle_get_jpkkenfull_status,
    "list_jpkkenfull_tools": handle_list_tools,
}


# ── Main loop ──────────────────────────────────────────────────────────────────

def main() -> None:
    logger.info("Jpkkenfull MCP Server v2.0 started")
    capabilities = {
        "tools": [
            {
                "name": "run_jpkkenfull",
                "description": "Execute any goal autonomously without per-step permissions",
                "inputSchema": {
                    "goal": {"type": "string"},
                    "context": {"type": "string"},
                    "force_internet": {"type": "boolean"},
                    "skip_agents": {"type": "boolean"},
                },
            },
            {
                "name": "abort_jpkkenfull",
                "description": "Abort a running execution",
                "inputSchema": {"type": "object", "properties": {}},
            },
            {
                "name": "get_jpkkenfull_status",
                "description": "Get current execution state",
                "inputSchema": {"type": "object", "properties": {}},
            },
        ]
    }

    while True:
        msg = read_message()
        if msg is None:
            break

        method = msg.get("method", "")
        msg_id = msg.get("id")
        params = msg.get("params", {})

        if method == "initialize":
            send_result(msg_id, {"capabilities": capabilities, "serverInfo": {"name": "jpkkenfull", "version": "2.0.0"}})
            continue

        if method in ("notifications/initialized",):
            continue

        if method == "tools/list":
            send_result(msg_id, capabilities["tools"])
        elif method == "tools/call":
            tool_name = params.get("name", "")
            tool_args = params.get("arguments", {})
            if tool_name in METHODS:
                try:
                    result = METHODS[tool_name](tool_args)
                    send_result(msg_id, result)
                except Exception as e:
                    send_error(msg_id, -32603, f"Tool error: {e}")
            else:
                send_error(msg_id, -32601, f"Unknown tool: {tool_name}")
        else:
            send_error(msg_id, -32601, f"Method not found: {method}")


if __name__ == "__main__":
    main()
