#!/usr/bin/env python3
"""Antigravity Shu Slack Bridge — MCP server for Slack /shu integration.

Exposes MCP tools that allow invoking /shu from Slack:
- shu_slack_handle_command: Handle incoming Slack slash command /shu
- shu_slack_handle_modal_submit: Process completed Slack modal with 6 answers
- shu_slack_get_modal_definition: Get the Slack modal JSON for /shu

Environment variables required:
    SLACK_BOT_TOKEN: Slack bot token (xoxb-...)
    SLACK_SIGNING_SECRET: Slack signing secret for request verification
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# Add .agent to path for imports
_AGENT_DIR = Path(__file__).parent.parent
if str(_AGENT_DIR) not in sys.path:
    sys.path.insert(0, str(_AGENT_DIR))

try:
    from core.shu_cross_platform_handler import ShuCrossPlatformHandler

    _handler = ShuCrossPlatformHandler()
    _HANDLER_AVAILABLE = True
except ImportError as _exc:
    _handler = None  # type: ignore[assignment]
    _HANDLER_AVAILABLE = False
    logger.error("ShuCrossPlatformHandler not available: %s", _exc)

# Slack modal block IDs mapping to the 6 /shu questions
_MODAL_BLOCK_IDS: list[tuple[str, str, str]] = [
    (
        "q1_context",
        "Q1 - Context",
        "Describe the real situation: what's happening, what triggered this?",
    ),
    (
        "q2_scope",
        "Q2 - Scope",
        "What exactly needs to change? Be specific about files, systems, or behaviors.",
    ),
    (
        "q3_restrictions",
        "Q3 - Restrictions",
        "What constraints exist? (time, budget, backward compat, team, etc.)",
    ),
    (
        "q4_validation",
        "Q4 - Validation",
        "How will we know it worked? What's the success criterion?",
    ),
    ("q5_priority", "Q5 - Priority", "Urgency (1-5) and business value. Why now?"),
    ("q6_historical", "Q6 - Historical", "Similar past decisions and their outcomes (or 'none')."),
]


def _get_modal_definition(goal: str, trigger_id: str) -> dict:
    """Build the Slack modal JSON for /shu with 6 text input fields.

    Args:
        goal: The goal extracted from the slash command argument.
        trigger_id: Slack trigger ID for opening the modal.

    Returns:
        Slack views.open payload dict.
    """
    blocks = []
    for block_id, label, placeholder in _MODAL_BLOCK_IDS:
        blocks.append(
            {
                "type": "input",
                "block_id": block_id,
                "label": {"type": "plain_text", "text": label},
                "element": {
                    "type": "plain_text_input",
                    "multiline": True,
                    "placeholder": {"type": "plain_text", "text": placeholder},
                    "action_id": "value",
                },
            }
        )

    return {
        "trigger_id": trigger_id,
        "view": {
            "type": "modal",
            "callback_id": "shu_modal_submit",
            "private_metadata": json.dumps({"goal": goal}),
            "title": {"type": "plain_text", "text": "/shu Diagnostic"},
            "submit": {"type": "plain_text", "text": "Run /shu"},
            "close": {"type": "plain_text", "text": "Cancel"},
            "blocks": blocks,
        },
    }


def _extract_modal_responses(view_state: dict) -> dict[str, str]:
    """Extract text values from Slack modal view state.

    Args:
        view_state: The view.state.values dict from the Slack payload.

    Returns:
        Dict with keys q1_context through q6_historical.
    """
    responses: dict[str, str] = {}
    for block_id, _, _ in _MODAL_BLOCK_IDS:
        block_values = view_state.get(block_id, {})
        # Slack nested structure: state.values[block_id][action_id].value
        action_values = block_values.get("value", block_values)
        if isinstance(action_values, dict):
            value = action_values.get("value", "")
        else:
            value = str(action_values) if action_values else ""
        responses[block_id] = (value or "").strip()
    return responses


def _text_response(request_id: int, text: str, *, is_error: bool = False) -> dict:
    """Build a JSON-RPC 2.0 text response.

    Args:
        request_id: JSON-RPC request ID.
        text: Response text.
        is_error: Mark response as error if True.

    Returns:
        JSON-RPC 2.0 response dict.
    """
    result: dict = {"content": [{"type": "text", "text": text}]}
    if is_error:
        result["isError"] = True
    return {"jsonrpc": "2.0", "id": request_id, "result": result}


def _handle_slack_command(request_id: int, args: dict) -> dict:
    """Handle a Slack /shu slash command event.

    Returns the modal definition that the Slack app should open.

    Args:
        request_id: JSON-RPC request ID.
        args: Tool arguments with 'goal' and 'trigger_id'.

    Returns:
        JSON-RPC response containing the modal JSON.
    """
    goal = args.get("goal", "").strip()
    trigger_id = args.get("trigger_id", "").strip()

    if not trigger_id:
        return _text_response(request_id, "Error: trigger_id is required", is_error=True)

    logger.info("shu_slack_bridge: slash command received goal=%r trigger_id=%s", goal, trigger_id)

    try:
        modal = _get_modal_definition(goal, trigger_id)
        return _text_response(
            request_id,
            json.dumps(modal, ensure_ascii=False, indent=2),
        )
    except Exception as exc:
        logger.error("shu_slack_bridge: error building modal: %s", exc)
        return _text_response(request_id, f"Error building modal: {exc}", is_error=True)


def _handle_modal_submit(request_id: int, args: dict) -> dict:
    """Process a completed Slack /shu modal submission.

    Extracts 6 responses from the modal view state and executes /shu.

    Args:
        request_id: JSON-RPC request ID.
        args: Tool arguments with 'goal', 'user_id', and 'view_state'.

    Returns:
        JSON-RPC response with execution result.
    """
    if not _HANDLER_AVAILABLE:
        return _text_response(
            request_id, "Error: ShuCrossPlatformHandler not available", is_error=True
        )

    goal = args.get("goal", "").strip()
    user_id = args.get("user_id", "unknown")
    view_state = args.get("view_state", {})

    logger.info("shu_slack_bridge: modal submit user_id=%s goal=%r", user_id, goal[:60])

    try:
        responses = _extract_modal_responses(view_state)
        result = _handler.execute_from_platform(platform="slack", goal=goal, responses=responses)

        if result.get("success"):
            plan = result.get("execution_plan", "")
            next_steps = result.get("next_steps", [])
            broadcast = result.get("broadcast_result", {})
            output_lines = [
                f"/shu completed for: {goal}",
                "",
                plan,
                "",
                "Next steps:",
            ]
            for step in next_steps:
                output_lines.append(f"  - {step}")
            output_lines.append(
                f"\nBroadcast: {broadcast.get('successful', 0)}/{broadcast.get('broadcast_count', 0)} subscribers notified"
            )
            return _text_response(request_id, "\n".join(output_lines))
        else:
            errors = result.get("broadcast_result", {}).get("errors", [])
            return _text_response(
                request_id,
                f"Error executing /shu: {errors}",
                is_error=True,
            )
    except Exception as exc:
        logger.error("shu_slack_bridge: modal submit error: %s", exc)
        return _text_response(request_id, f"Error: {exc}", is_error=True)


def _handle_get_modal_definition(request_id: int, args: dict) -> dict:
    """Return the Slack modal definition JSON for /shu.

    Args:
        request_id: JSON-RPC request ID.
        args: Tool arguments with 'goal' and 'trigger_id'.

    Returns:
        JSON-RPC response with modal JSON.
    """
    goal = args.get("goal", "Define your goal")
    trigger_id = args.get("trigger_id", "placeholder_trigger_id")

    try:
        modal = _get_modal_definition(goal, trigger_id)
        return _text_response(request_id, json.dumps(modal, ensure_ascii=False, indent=2))
    except Exception as exc:
        return _text_response(request_id, f"Error: {exc}", is_error=True)


_TOOLS = [
    {
        "name": "shu_slack_handle_command",
        "description": (
            "Handle a Slack /shu slash command. Returns the modal JSON that the "
            "Slack app must open via views.open to collect 6 /shu responses from the user."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Goal text passed to the /shu command (may be empty).",
                },
                "trigger_id": {
                    "type": "string",
                    "description": "Slack trigger_id from the slash command payload (required to open modal).",
                },
            },
            "required": ["trigger_id"],
        },
    },
    {
        "name": "shu_slack_handle_modal_submit",
        "description": (
            "Process a completed /shu Slack modal submission. Extracts the 6 responses "
            "from the modal view state, executes the /shu diagnostic, and publishes "
            "to the webhook system."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "The goal from the original slash command.",
                },
                "user_id": {
                    "type": "string",
                    "description": "Slack user ID who submitted the modal.",
                },
                "view_state": {
                    "type": "object",
                    "description": "The view.state.values object from the Slack interaction payload.",
                },
            },
            "required": ["view_state"],
        },
    },
    {
        "name": "shu_slack_get_modal_definition",
        "description": "Return the Slack modal JSON definition for /shu (useful for preview/debugging).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Goal to pre-fill in modal metadata."},
                "trigger_id": {"type": "string", "description": "Slack trigger_id."},
            },
        },
    },
]


def handle_request(request: dict) -> dict | None:
    """Main JSON-RPC 2.0 request dispatcher.

    Args:
        request: JSON-RPC 2.0 request dict.

    Returns:
        JSON-RPC response dict, or None for notifications.
    """
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    if method and method.startswith("notifications/"):
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "antigravity-shu-slack", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _TOOLS}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "shu_slack_handle_command":
            return _handle_slack_command(request_id, args)
        elif name == "shu_slack_handle_modal_submit":
            return _handle_modal_submit(request_id, args)
        elif name == "shu_slack_get_modal_definition":
            return _handle_get_modal_definition(request_id, args)

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"},
    }


if __name__ == "__main__":
    # Los pipes stdio en Windows heredan la codepage del locale (cp932 en JP),
    # pero el protocolo MCP habla UTF-8: sin esto, el JSON entrante con no-ASCII
    # llega con surrogates sueltos y la respuesta puede fallar al escribirse.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except Exception:
            logger.exception("Error in shu_slack_bridge main loop")
