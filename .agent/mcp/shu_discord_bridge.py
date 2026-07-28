#!/usr/bin/env python3
"""Antigravity Shu Discord Bridge — MCP server for Discord /shu integration.

Exposes MCP tools that allow invoking /shu from Discord:
- shu_discord_handle_slash_command: Handle /shu slash command interaction
- shu_discord_handle_modal_submit: Process Discord modal with 6 answers
- shu_discord_get_embed_definition: Get the embed + button JSON for /shu

Environment variables required:
    DISCORD_BOT_TOKEN: Discord bot token
    DISCORD_APPLICATION_ID: Discord application/client ID
    DISCORD_PUBLIC_KEY: Discord public key for request verification
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

# Modal and component custom IDs
_MODAL_CUSTOM_ID = "shu_modal"
_BUTTON_CUSTOM_ID = "shu_open_modal"

# The 6 /shu questions as Discord modal text input fields
_MODAL_COMPONENTS: list[tuple[str, str, str]] = [
    ("q1_context", "Q1 - Context", "Real situation: what's happening, what triggered this?"),
    ("q2_scope", "Q2 - Scope", "What exactly needs to change? Files, systems, behaviors."),
    ("q3_restrictions", "Q3 - Restrictions", "Constraints: time, budget, backward compat, team."),
    ("q4_validation", "Q4 - Validation", "How will we know it worked? Success criterion."),
    ("q5_priority", "Q5 - Priority", "Urgency (1-5) and business value. Why now?"),
    ("q6_historical", "Q6 - Historical", "Similar past decisions and their outcomes (or 'none')."),
]


def _get_embed_definition(goal: str) -> dict:
    """Build a Discord embed message for announcing /shu has been invoked.

    Args:
        goal: The goal from the slash command.

    Returns:
        Discord interaction response dict with embed and button component.
    """
    return {
        "type": 4,  # CHANNEL_MESSAGE_WITH_SOURCE
        "data": {
            "embeds": [
                {
                    "title": "/shu Diagnostic Framework",
                    "description": (
                        f"**Goal:** {goal or '(not specified)'}\n\n"
                        "Click the button below to open the /shu questionnaire and "
                        "answer the 6 diagnostic questions."
                    ),
                    "color": 0x5865F2,  # Discord blurple
                    "footer": {"text": "Powered by Antigravity /shu"},
                }
            ],
            "components": [
                {
                    "type": 1,  # ACTION_ROW
                    "components": [
                        {
                            "type": 2,  # BUTTON
                            "style": 1,  # PRIMARY (blue)
                            "label": "Start /shu Diagnostic",
                            "custom_id": f"{_BUTTON_CUSTOM_ID}:{goal[:50]}",
                        }
                    ],
                }
            ],
        },
    }


def _get_modal_definition(goal: str) -> dict:
    """Build a Discord modal with 6 text input fields for /shu.

    Args:
        goal: The goal to embed in the modal custom ID.

    Returns:
        Discord interaction response dict with modal definition.
    """
    components = []
    for custom_id, label, placeholder in _MODAL_COMPONENTS:
        components.append(
            {
                "type": 1,  # ACTION_ROW
                "components": [
                    {
                        "type": 4,  # TEXT_INPUT
                        "custom_id": custom_id,
                        "label": label,
                        "style": 2,  # PARAGRAPH
                        "placeholder": placeholder,
                        "required": False,
                        "min_length": 0,
                        "max_length": 1000,
                    }
                ],
            }
        )

    return {
        "type": 9,  # MODAL
        "data": {
            "custom_id": f"{_MODAL_CUSTOM_ID}:{goal[:50]}",
            "title": "/shu Diagnostic",
            "components": components,
        },
    }


def _extract_modal_responses(components: list[dict]) -> dict[str, str]:
    """Extract text values from Discord modal submission components.

    Discord modal submit interaction has nested action rows:
    components[n].components[0].custom_id / .value

    Args:
        components: The components list from the Discord interaction data.

    Returns:
        Dict with keys q1_context through q6_historical.
    """
    responses: dict[str, str] = {}
    for row in components:
        for field in row.get("components", []):
            custom_id = field.get("custom_id", "")
            value = field.get("value", "")
            if custom_id:
                responses[custom_id] = (value or "").strip()
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


def _handle_slash_command(request_id: int, args: dict) -> dict:
    """Handle a Discord /shu application command interaction.

    Returns the embed + button that the Discord bot should reply with.

    Args:
        request_id: JSON-RPC request ID.
        args: Tool arguments with 'goal' and 'user_id'.

    Returns:
        JSON-RPC response containing the Discord interaction response JSON.
    """
    goal = args.get("goal", "").strip()
    user_id = args.get("user_id", "unknown")

    logger.info("shu_discord_bridge: slash command user_id=%s goal=%r", user_id, goal[:60])

    try:
        embed = _get_embed_definition(goal)
        return _text_response(
            request_id,
            json.dumps(embed, ensure_ascii=False, indent=2),
        )
    except Exception as exc:
        logger.error("shu_discord_bridge: error building embed: %s", exc)
        return _text_response(request_id, f"Error building embed: {exc}", is_error=True)


def _handle_modal_submit(request_id: int, args: dict) -> dict:
    """Process a Discord /shu modal submission.

    Extracts 6 responses from the modal components and executes /shu.

    Args:
        request_id: JSON-RPC request ID.
        args: Tool arguments with 'goal', 'user_id', and 'components'.

    Returns:
        JSON-RPC response with execution result.
    """
    if not _HANDLER_AVAILABLE:
        return _text_response(
            request_id, "Error: ShuCrossPlatformHandler not available", is_error=True
        )

    goal = args.get("goal", "").strip()
    user_id = args.get("user_id", "unknown")
    components = args.get("components", [])

    logger.info("shu_discord_bridge: modal submit user_id=%s goal=%r", user_id, goal[:60])

    try:
        responses = _extract_modal_responses(components)
        result = _handler.execute_from_platform(platform="discord", goal=goal, responses=responses)

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
        logger.error("shu_discord_bridge: modal submit error: %s", exc)
        return _text_response(request_id, f"Error: {exc}", is_error=True)


def _handle_get_embed_definition(request_id: int, args: dict) -> dict:
    """Return the Discord embed + button definition for /shu.

    Args:
        request_id: JSON-RPC request ID.
        args: Tool arguments with 'goal'.

    Returns:
        JSON-RPC response with embed JSON.
    """
    goal = args.get("goal", "Define your goal")
    try:
        embed = _get_embed_definition(goal)
        return _text_response(request_id, json.dumps(embed, ensure_ascii=False, indent=2))
    except Exception as exc:
        return _text_response(request_id, f"Error: {exc}", is_error=True)


_TOOLS = [
    {
        "name": "shu_discord_handle_slash_command",
        "description": (
            "Handle a Discord /shu application command. Returns the embed + button "
            "JSON that the Discord bot should send as an interaction response."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {
                    "type": "string",
                    "description": "Goal text from the /shu command options.",
                },
                "user_id": {
                    "type": "string",
                    "description": "Discord user ID who invoked the command.",
                },
            },
        },
    },
    {
        "name": "shu_discord_handle_modal_submit",
        "description": (
            "Process a completed /shu Discord modal. Extracts 6 responses from the "
            "modal components, runs the /shu diagnostic, and publishes to the webhook system."
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
                    "description": "Discord user ID who submitted the modal.",
                },
                "components": {
                    "type": "array",
                    "description": "The components array from the Discord modal submit interaction data.",
                    "items": {"type": "object"},
                },
            },
            "required": ["components"],
        },
    },
    {
        "name": "shu_discord_get_embed_definition",
        "description": "Return the Discord embed + button definition for /shu (useful for preview/debugging).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "goal": {"type": "string", "description": "Goal to embed in the message."},
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
                "serverInfo": {"name": "antigravity-shu-discord", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _TOOLS}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "shu_discord_handle_slash_command":
            return _handle_slash_command(request_id, args)
        elif name == "shu_discord_handle_modal_submit":
            return _handle_modal_submit(request_id, args)
        elif name == "shu_discord_get_embed_definition":
            return _handle_get_embed_definition(request_id, args)

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
            logger.exception("Error in shu_discord_bridge main loop")
