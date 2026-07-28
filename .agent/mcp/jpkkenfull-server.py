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

# ── Configuration ────────────────────────────────────────────────────────────


def _strip_windows_extended_prefix(path_value: str) -> str:
    """Remove Windows extended path prefix when present."""
    return path_value[4:] if path_value.startswith("\\\\?\\") else path_value


def _resolve_repo_root() -> Path:
    """Resolve the Antigravity repository root from env, parents, or cwd."""
    candidates: list[Path] = []
    env_root = os.environ.get("ANTIGRAVITY_ROOT", "").strip()
    if env_root:
        candidates.append(Path(_strip_windows_extended_prefix(env_root)).expanduser())
    current = Path(__file__).resolve()
    candidates.extend([current.parents[2], Path.cwd()])
    for candidate in candidates:
        resolved = candidate.resolve()
        if (resolved / "RULES.md").exists() and (resolved / ".agent").is_dir():
            return resolved
    return Path.cwd().resolve()


REPO_ROOT = _resolve_repo_root()
SKILL_DIR = REPO_ROOT / ".agent" / "skills-custom" / "jpkkenfull"
SCRIPT = SKILL_DIR / "scripts" / "main.py"

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
        self.started_at: float | None = None
        self.process_pid: int | None = None
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


def read_message() -> tuple[dict, bool] | None:
    """Read one JSON-RPC message and detect legacy Content-Length framing."""
    try:
        first_line = sys.stdin.buffer.readline()
        if not first_line:
            return None

        stripped = first_line.strip()
        if not stripped:
            return read_message()

        if stripped.lower().startswith(b"content-length:"):
            length = int(stripped.split(b":", 1)[1].strip())
            while True:
                header_line = sys.stdin.buffer.readline()
                if not header_line or not header_line.strip():
                    break
            body = sys.stdin.buffer.read(length)
            return json.loads(body.decode("utf-8")), True

        return json.loads(stripped.decode("utf-8")), False
    except Exception as e:
        logger.error("read_message error: %s", e)
        return None


def write_message(data: dict, *, use_framing: bool = False) -> None:
    """Write JSON-RPC using the same transport style as the client request."""
    try:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        if use_framing:
            header = f"Content-Length: {len(body)}\r\n\r\n".encode("ascii")
            sys.stdout.buffer.write(header + body)
        else:
            sys.stdout.buffer.write(body + b"\n")
        sys.stdout.buffer.flush()
    except Exception as e:
        logger.error("write_message error: %s", e)


def send_result(msg_id: int | str | None, result: dict, *, use_framing: bool = False) -> None:
    write_message({"jsonrpc": "2.0", "id": msg_id, "result": result}, use_framing=use_framing)


def send_error(
    msg_id: int | str | None,
    code: int,
    message: str,
    data: dict | None = None,
    *,
    use_framing: bool = False,
) -> None:
    err = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    write_message({"jsonrpc": "2.0", "id": msg_id, "error": err}, use_framing=use_framing)


# ── Tool handlers ─────────────────────────────────────────────────────────────


def handle_run_jpkkenfull(params: dict) -> dict:
    """Run jpkkenfull with a goal."""
    import subprocess
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
        env = os.environ.copy()
        env["ANTIGRAVITY_ROOT"] = str(REPO_ROOT)
        env["PYTHONPATH"] = (
            str(REPO_ROOT / ".agent")
            if not env.get("PYTHONPATH")
            else f"{REPO_ROOT / '.agent'}{os.pathsep}{env['PYTHONPATH']}"
        )
        env.setdefault("PYTHONIOENCODING", "utf-8")
        proc = subprocess.Popen(
            cmd,
            cwd=str(REPO_ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        _state.process_pid = proc.pid

        try:
            stdout, stderr = proc.communicate(timeout=300)
        except subprocess.TimeoutExpired:
            proc.kill()
            stdout, stderr = proc.communicate()
            _state.running = False
            _state.process_pid = None
            return {"success": False, "error": "Timeout after 300s"}

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

PROTOCOL_VERSION = "2024-11-05"
TOOLS = [
    {
        "name": "run_jpkkenfull",
        "description": "Execute any goal autonomously without per-step permissions",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string"},
                "context": {"type": "string"},
                "force_internet": {"type": "boolean"},
                "skip_agents": {"type": "boolean"},
            },
            "required": ["goal"],
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
    {
        "name": "list_jpkkenfull_tools",
        "description": "List available jpkkenfull tools",
        "inputSchema": {"type": "object", "properties": {}},
    },
]


def handle_request(msg: dict) -> dict | None:
    """Dispatch one MCP JSON-RPC request."""
    method = msg.get("method", "")
    msg_id = msg.get("id")
    params = msg.get("params", {})

    def ok(result: dict) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "result": result}

    def err(code: int, message: str) -> dict:
        return {"jsonrpc": "2.0", "id": msg_id, "error": {"code": code, "message": message}}

    if method == "initialize":
        return ok(
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "jpkkenfull", "version": "2.1.0"},
            }
        )

    if method == "tools/list":
        return ok({"tools": TOOLS})

    if method == "tools/call":
        tool_name = params.get("name", "")
        tool_args = params.get("arguments", {})
        if tool_name not in METHODS:
            return err(-32601, f"Unknown tool: {tool_name}")
        try:
            result = METHODS[tool_name](tool_args)
        except Exception as e:
            return err(-32603, f"Tool error: {e}")
        is_error = isinstance(result, dict) and "error" in result and not result.get("success")
        return ok(
            {
                "content": [{"type": "text", "text": json.dumps(result, ensure_ascii=False)}],
                **({"isError": True} if is_error else {}),
            }
        )

    if method.startswith("notifications/"):
        return None

    return err(-32601, f"Method not found: {method}")


# ── Main loop ──────────────────────────────────────────────────────────────────


def main() -> None:
    logger.info("Jpkkenfull MCP Server v2.1 started")
    while True:
        request = read_message()
        if request is None:
            break
        msg, use_framing = request
        response = handle_request(msg)
        if response is not None:
            write_message(response, use_framing=use_framing)


if __name__ == "__main__":
    main()
