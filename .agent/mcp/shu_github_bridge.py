#!/usr/bin/env python3
"""Antigravity Shu GitHub Bridge — MCP server for GitHub issue /shu integration.

Exposes MCP tools that allow invoking /shu from GitHub issues:
- shu_github_handle_issue_event: Detect 'needs-shu' label and post 6-question comment
- shu_github_handle_comment_event: Parse user replies and execute /shu when complete
- shu_github_get_question_comment: Generate the comment body with 6 questions

Environment variables required:
    GITHUB_TOKEN: GitHub personal access token or app token
    GITHUB_WEBHOOK_SECRET: GitHub webhook secret for request verification (optional)

The flow:
  1. Issue is labeled 'needs-shu' -> bot posts a comment with 6 questions
  2. User replies in the comment thread using the **Q1 - Context:** format
  3. Bot parses the reply, executes /shu, posts back the execution summary
"""

from __future__ import annotations

import json
import logging
import re
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

# Label that triggers the /shu bot
_TRIGGER_LABEL = "needs-shu"

# Question definitions: (key, label, description)
_QUESTIONS: list[tuple[str, str, str]] = [
    ("Q1", "Context", "What's the real situation? What triggered this issue?"),
    ("Q2", "Scope", "What exactly needs to change? Files, systems, behaviors."),
    ("Q3", "Restrictions", "Constraints: time, budget, backward compat, team."),
    ("Q4", "Validation", "How will we know it worked? Success criterion."),
    ("Q5", "Priority", "Urgency (1-5) and business value. Why now?"),
    ("Q6", "Historical", "Similar past decisions and their outcomes (or 'none')."),
]

# Regex pattern to extract Q1-Q6 answers from a GitHub comment
# Matches: **Q1 - Context:** some text (multi-line until next Q or EOF)
_ANSWER_PATTERN = re.compile(
    r"\*\*(?P<qnum>Q[1-6])\s*[-–]\s*\w+[^\*]*?\*\*:?\s*(?P<answer>[^\n]*(?:\n(?!\*\*Q[1-6]).*)*)",
    re.IGNORECASE,
)


def _build_question_comment(issue_title: str, issue_url: str) -> str:
    """Build the GitHub comment body asking the 6 /shu questions.

    Args:
        issue_title: Title of the GitHub issue.
        issue_url: URL of the GitHub issue.

    Returns:
        Markdown comment body string.
    """
    lines = [
        "## /shu Diagnostic Framework",
        "",
        f"This issue has been labeled `{_TRIGGER_LABEL}`. "
        "Please answer the 6 diagnostic questions below to help define the path forward.",
        "",
        "> **How to answer:** Reply to this comment with your answers in the format shown below.",
        "> You can edit your reply until the bot processes it.",
        "",
        "---",
        "",
    ]

    for qnum, label, description in _QUESTIONS:
        lines.append(f"**{qnum} - {label}:** <!-- {description} -->")
        lines.append("> _(replace this with your answer)_")
        lines.append("")

    lines.extend(
        [
            "---",
            "",
            "_Bot will automatically parse your reply when you post it. "
            "Make sure to keep the `**Q1 - Context:**` headers in your response._",
            "",
            f"_Issue: [{issue_title}]({issue_url})_",
        ]
    )

    return "\n".join(lines)


def _parse_comment_responses(comment_body: str) -> dict[str, str]:
    """Extract Q1-Q6 answers from a GitHub comment using regex.

    Expected format in comment:
        **Q1 - Context:** Some context text here
        **Q2 - Scope:** The scope of changes

    Args:
        comment_body: Raw comment body text from GitHub.

    Returns:
        Dict with keys Q1-Q6 mapping to extracted answer text.
        Missing answers default to empty string.
    """
    responses: dict[str, str] = {}

    for match in _ANSWER_PATTERN.finditer(comment_body):
        qnum = match.group("qnum").upper()
        answer = match.group("answer").strip()
        # Remove markdown comment placeholders if user did not replace them
        if "replace this with your answer" in answer.lower():
            answer = ""
        responses[qnum] = answer

    return responses


def _is_response_complete(responses: dict[str, str]) -> bool:
    """Check whether at least Q1 or Q2 have non-empty answers.

    Args:
        responses: Parsed Q1-Q6 responses dict.

    Returns:
        True if the minimum required questions are answered.
    """
    return bool(responses.get("Q1")) or bool(responses.get("Q2"))


def _build_result_comment(goal: str, result: dict) -> str:
    """Build the GitHub comment summarizing the /shu execution result.

    Args:
        goal: The issue title / goal.
        result: Execution result dict from ShuCrossPlatformHandler.

    Returns:
        Markdown comment body.
    """
    success = result.get("success", False)
    plan = result.get("execution_plan", "")
    next_steps = result.get("next_steps", [])
    broadcast = result.get("broadcast_result", {})
    elapsed_ms = result.get("execution_time_ms", 0)

    if not success:
        errors = broadcast.get("errors", [])
        return (
            "## /shu Result\n\n"
            f"Failed to execute /shu diagnostic.\n\n"
            f"Errors: {errors}\n\n"
            "_Please check the gateway logs or try again._"
        )

    lines = [
        "## /shu Execution Summary",
        "",
        f"**Goal:** {goal}",
        "",
        "### Diagnostic Context",
        "",
        "```",
        plan,
        "```",
        "",
        "### Next Steps",
        "",
    ]
    for step in next_steps:
        lines.append(f"- {step}")

    lines.extend(
        [
            "",
            "---",
            f"_Broadcast: {broadcast.get('successful', 0)}/{broadcast.get('broadcast_count', 0)} "
            f"webhook subscribers notified | Execution: {elapsed_ms:.0f}ms_",
        ]
    )

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────────────────────────
# JSON-RPC helpers
# ─────────────────────────────────────────────────────────────────────────────


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


# ─────────────────────────────────────────────────────────────────────────────
# Tool handlers
# ─────────────────────────────────────────────────────────────────────────────


def _handle_issue_event(request_id: int, args: dict) -> dict:
    """Handle a GitHub issue labeled event.

    When an issue is labeled 'needs-shu', returns the comment body that
    the bot should post to open the /shu diagnostic conversation.

    Args:
        request_id: JSON-RPC request ID.
        args: Tool arguments with 'action', 'label', 'issue_title', 'issue_url'.

    Returns:
        JSON-RPC response with comment body (or skip message if not triggered).
    """
    action = args.get("action", "")
    label = args.get("label", "")
    issue_title = args.get("issue_title", "Untitled Issue")
    issue_url = args.get("issue_url", "")
    issue_number = args.get("issue_number", 0)

    logger.info(
        "shu_github_bridge: issue event action=%s label=%r issue=#%s",
        action,
        label,
        issue_number,
    )

    # Only trigger on labeled events with the correct label
    if action != "labeled" or label != _TRIGGER_LABEL:
        return _text_response(
            request_id,
            f"Skipped: action={action!r} label={label!r} (expected action='labeled' label='{_TRIGGER_LABEL}')",
        )

    try:
        comment_body = _build_question_comment(issue_title, issue_url)
        return _text_response(
            request_id,
            json.dumps(
                {
                    "action": "post_comment",
                    "issue_number": issue_number,
                    "comment_body": comment_body,
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as exc:
        logger.error("shu_github_bridge: issue event error: %s", exc)
        return _text_response(request_id, f"Error: {exc}", is_error=True)


def _handle_comment_event(request_id: int, args: dict) -> dict:
    """Handle a GitHub issue comment event.

    Parses the comment for Q1-Q6 answers, executes /shu if complete,
    and returns the result comment body to post back.

    Args:
        request_id: JSON-RPC request ID.
        args: Tool arguments with 'comment_body', 'issue_title',
              'issue_number', 'commenter_login'.

    Returns:
        JSON-RPC response with result comment body, or skip if not parseable.
    """
    if not _HANDLER_AVAILABLE:
        return _text_response(
            request_id, "Error: ShuCrossPlatformHandler not available", is_error=True
        )

    comment_body = args.get("comment_body", "")
    issue_title = args.get("issue_title", "Untitled Issue")
    issue_number = args.get("issue_number", 0)
    commenter_login = args.get("commenter_login", "unknown")

    logger.info(
        "shu_github_bridge: comment event issue=#%s commenter=%s body_len=%d",
        issue_number,
        commenter_login,
        len(comment_body),
    )

    try:
        responses = _parse_comment_responses(comment_body)

        if not _is_response_complete(responses):
            return _text_response(
                request_id,
                f"Skipped: comment from {commenter_login} does not contain /shu answers (Q1/Q2 empty)",
            )

        result = _handler.execute_from_platform(
            platform="github",
            goal=issue_title,
            responses=responses,
        )

        result_comment = _build_result_comment(issue_title, result)
        return _text_response(
            request_id,
            json.dumps(
                {
                    "action": "post_result_comment",
                    "issue_number": issue_number,
                    "comment_body": result_comment,
                    "execution_success": result.get("success", False),
                },
                ensure_ascii=False,
                indent=2,
            ),
        )
    except Exception as exc:
        logger.error("shu_github_bridge: comment event error: %s", exc)
        return _text_response(request_id, f"Error: {exc}", is_error=True)


def _handle_get_question_comment(request_id: int, args: dict) -> dict:
    """Return the GitHub comment body with 6 /shu questions.

    Args:
        request_id: JSON-RPC request ID.
        args: Tool arguments with 'issue_title' and 'issue_url'.

    Returns:
        JSON-RPC response with comment body.
    """
    issue_title = args.get("issue_title", "GitHub Issue")
    issue_url = args.get("issue_url", "")
    try:
        comment_body = _build_question_comment(issue_title, issue_url)
        return _text_response(request_id, comment_body)
    except Exception as exc:
        return _text_response(request_id, f"Error: {exc}", is_error=True)


# ─────────────────────────────────────────────────────────────────────────────
# Main JSON-RPC dispatcher
# ─────────────────────────────────────────────────────────────────────────────

_TOOLS = [
    {
        "name": "shu_github_handle_issue_event",
        "description": (
            f"Handle a GitHub issue webhook event. When an issue is labeled '{_TRIGGER_LABEL}', "
            "returns the comment body that the GitHub bot should post to start the /shu diagnostic."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "description": "Issue event action (e.g., 'labeled', 'opened').",
                },
                "label": {
                    "type": "string",
                    "description": "Label name that was added to the issue.",
                },
                "issue_title": {
                    "type": "string",
                    "description": "Title of the GitHub issue.",
                },
                "issue_url": {
                    "type": "string",
                    "description": "URL of the GitHub issue.",
                },
                "issue_number": {
                    "type": "integer",
                    "description": "GitHub issue number.",
                },
            },
            "required": ["action", "label"],
        },
    },
    {
        "name": "shu_github_handle_comment_event",
        "description": (
            "Handle a GitHub issue comment webhook event. Parses the comment for Q1-Q6 /shu "
            "answers, executes the diagnostic, and returns the result comment body to post back."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "comment_body": {
                    "type": "string",
                    "description": "Full text body of the GitHub comment.",
                },
                "issue_title": {
                    "type": "string",
                    "description": "Title of the parent GitHub issue (used as the /shu goal).",
                },
                "issue_number": {
                    "type": "integer",
                    "description": "GitHub issue number.",
                },
                "commenter_login": {
                    "type": "string",
                    "description": "GitHub login of the comment author.",
                },
            },
            "required": ["comment_body"],
        },
    },
    {
        "name": "shu_github_get_question_comment",
        "description": "Return the GitHub comment markdown with 6 /shu questions (useful for preview/debugging).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "issue_title": {"type": "string", "description": "Title of the issue."},
                "issue_url": {"type": "string", "description": "URL of the issue."},
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
                "serverInfo": {"name": "antigravity-shu-github", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": _TOOLS}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "shu_github_handle_issue_event":
            return _handle_issue_event(request_id, args)
        elif name == "shu_github_handle_comment_event":
            return _handle_comment_event(request_id, args)
        elif name == "shu_github_get_question_comment":
            return _handle_get_question_comment(request_id, args)

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
            logger.exception("Error in shu_github_bridge main loop")
