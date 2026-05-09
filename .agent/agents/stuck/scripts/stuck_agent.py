#!/usr/bin/env python3
"""
Stuck Agent - Human Escalation Handler

Capabilities:
- Detect when AI is stuck
- Format questions for human input
- Track unresolved issues
- Provide context for escalation
"""

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class EscalationRequest:
    """A request for human input."""

    id: str
    type: str  # clarification, decision, error, permission
    question: str
    context: str
    options: list[str] = field(default_factory=list)
    urgency: str = "normal"  # low, normal, high, critical
    created_at: str = ""
    resolved: bool = False
    resolution: str | None = None

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now().isoformat()


@dataclass
class StuckReport:
    """Stuck agent report."""

    project_path: str
    pending_requests: list[EscalationRequest] = field(default_factory=list)
    resolved_count: int = 0
    total_count: int = 0

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "pending_requests": [r.__dict__ for r in self.pending_requests],
            "resolved_count": self.resolved_count,
            "total_count": self.total_count,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Escalation Status",
            "",
            f"**Pending:** {len(self.pending_requests)}",
            f"**Resolved:** {self.resolved_count}",
            f"**Total:** {self.total_count}",
            "",
        ]

        if self.pending_requests:
            lines.extend(["## Pending Questions", ""])
            for req in self.pending_requests:
                urgency_icon = {"critical": "🔴", "high": "🟠", "normal": "🟡", "low": "🔵"}.get(
                    req.urgency, "⚪"
                )

                lines.extend(
                    [
                        f"### {urgency_icon} [{req.type}] {req.id}",
                        "",
                        f"**Question:** {req.question}",
                        "",
                        f"**Context:** {req.context}",
                        "",
                    ]
                )

                if req.options:
                    lines.append("**Options:**")
                    for i, opt in enumerate(req.options, 1):
                        lines.append(f"{i}. {opt}")
                    lines.append("")

        return "\n".join(lines)


class StuckAgent:
    """Human escalation agent."""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()
        self.escalation_file = self.project_path / ".agent" / "escalations.json"
        self._requests: list[EscalationRequest] = []
        self._load_requests()

    def _load_requests(self):
        """Load escalation requests from file."""
        if self.escalation_file.exists():
            try:
                data = json.loads(self.escalation_file.read_text())
                self._requests = [EscalationRequest(**req) for req in data.get("requests", [])]
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Could not load escalations: {e}")
                self._requests = []

    def _save_requests(self):
        """Save escalation requests to file."""
        self.escalation_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "updated_at": datetime.now().isoformat(),
            "requests": [req.__dict__ for req in self._requests],
        }
        self.escalation_file.write_text(json.dumps(data, indent=2))

    def _generate_id(self) -> str:
        """Generate unique request ID."""
        import hashlib

        timestamp = datetime.now().isoformat()
        return hashlib.sha256(timestamp.encode()).hexdigest()[:8]

    async def ask_clarification(
        self, question: str, context: str, options: list[str] = None, urgency: str = "normal"
    ) -> EscalationRequest:
        """Create a clarification request."""
        request = EscalationRequest(
            id=self._generate_id(),
            type="clarification",
            question=question,
            context=context,
            options=options or [],
            urgency=urgency,
        )
        self._requests.append(request)
        self._save_requests()

        logger.info(f"Escalation created: {request.id}")
        self._print_escalation(request)
        return request

    async def ask_decision(
        self, question: str, context: str, options: list[str], urgency: str = "normal"
    ) -> EscalationRequest:
        """Create a decision request."""
        request = EscalationRequest(
            id=self._generate_id(),
            type="decision",
            question=question,
            context=context,
            options=options,
            urgency=urgency,
        )
        self._requests.append(request)
        self._save_requests()

        logger.info(f"Decision request created: {request.id}")
        self._print_escalation(request)
        return request

    async def report_error(
        self, error: str, context: str, attempted: list[str] = None, urgency: str = "high"
    ) -> EscalationRequest:
        """Report an error that needs human intervention."""
        question = f"Error encountered: {error}"
        request = EscalationRequest(
            id=self._generate_id(),
            type="error",
            question=question,
            context=context,
            options=attempted or [],
            urgency=urgency,
        )
        self._requests.append(request)
        self._save_requests()

        logger.info(f"Error escalation created: {request.id}")
        self._print_escalation(request)
        return request

    async def request_permission(
        self, action: str, context: str, urgency: str = "normal"
    ) -> EscalationRequest:
        """Request permission for an action."""
        request = EscalationRequest(
            id=self._generate_id(),
            type="permission",
            question=f"Permission needed: {action}",
            context=context,
            options=["Approve", "Deny", "Modify"],
            urgency=urgency,
        )
        self._requests.append(request)
        self._save_requests()

        logger.info(f"Permission request created: {request.id}")
        self._print_escalation(request)
        return request

    def _print_escalation(self, request: EscalationRequest):
        """Print escalation to console in a user-friendly format."""
        urgency_colors = {
            "critical": "\033[91m",  # Red
            "high": "\033[93m",  # Yellow
            "normal": "\033[0m",  # Default
            "low": "\033[94m",  # Blue
        }
        reset = "\033[0m"
        color = urgency_colors.get(request.urgency, reset)

        print(f"\n{color}{'=' * 60}{reset}")
        print(f"{color}🚨 HUMAN INPUT NEEDED [{request.type.upper()}]{reset}")
        print(f"{color}{'=' * 60}{reset}")
        print(f"\n📋 ID: {request.id}")
        print(f"⚡ Urgency: {request.urgency.upper()}")
        print(f"\n❓ {request.question}")
        print(f"\n📝 Context:\n{request.context}")

        if request.options:
            print("\n🔢 Options:")
            for i, opt in enumerate(request.options, 1):
                print(f"   {i}. {opt}")

        print(f"\n{color}{'=' * 60}{reset}\n")

    async def resolve(self, request_id: str, resolution: str) -> bool:
        """Mark a request as resolved."""
        for request in self._requests:
            if request.id == request_id:
                request.resolved = True
                request.resolution = resolution
                self._save_requests()
                logger.info(f"Resolved: {request_id}")
                return True
        return False

    async def get_pending(self) -> list[EscalationRequest]:
        """Get all pending escalation requests."""
        return [r for r in self._requests if not r.resolved]

    async def get_status(self) -> StuckReport:
        """Get escalation status."""
        pending = await self.get_pending()
        resolved = len([r for r in self._requests if r.resolved])

        return StuckReport(
            project_path=str(self.project_path),
            pending_requests=pending,
            resolved_count=resolved,
            total_count=len(self._requests),
        )

    async def clear_resolved(self) -> int:
        """Clear resolved requests."""
        original = len(self._requests)
        self._requests = [r for r in self._requests if not r.resolved]
        self._save_requests()
        return original - len(self._requests)

    async def detect_stuck(self, error_log: str = None) -> dict:
        """Analyze if the system is stuck and needs help."""
        indicators = {
            "repeated_errors": False,
            "circular_actions": False,
            "timeout_detected": False,
            "user_mentioned_stuck": False,
        }

        if error_log:
            # Check for repeated errors
            lines = error_log.split("\n")
            error_counts = {}
            for line in lines:
                if "error" in line.lower() or "exception" in line.lower():
                    key = line[:50]
                    error_counts[key] = error_counts.get(key, 0) + 1

            if any(count > 3 for count in error_counts.values()):
                indicators["repeated_errors"] = True

            # Check for timeouts
            if any(word in error_log.lower() for word in ["timeout", "timed out", "deadline"]):
                indicators["timeout_detected"] = True

        is_stuck = any(indicators.values())

        return {
            "is_stuck": is_stuck,
            "indicators": indicators,
            "recommendation": "Escalate to human" if is_stuck else "Continue normally",
        }


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Stuck Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    subparsers = parser.add_subparsers(dest="command")

    # Ask command
    ask_parser = subparsers.add_parser("ask", help="Ask a question")
    ask_parser.add_argument("question", help="Question to ask")
    ask_parser.add_argument("--context", required=True, help="Context")
    ask_parser.add_argument(
        "--type", default="clarification", choices=["clarification", "decision", "permission"]
    )
    ask_parser.add_argument("--options", nargs="*", help="Options")
    ask_parser.add_argument(
        "--urgency", default="normal", choices=["low", "normal", "high", "critical"]
    )

    # Resolve command
    resolve_parser = subparsers.add_parser("resolve", help="Resolve a request")
    resolve_parser.add_argument("id", help="Request ID")
    resolve_parser.add_argument("resolution", help="Resolution")

    # List command
    subparsers.add_parser("list", help="List pending requests")

    # Status command
    subparsers.add_parser("status", help="Show status")

    # Clear command
    subparsers.add_parser("clear", help="Clear resolved requests")

    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = StuckAgent(args.path)

    if args.command == "ask":
        if args.type == "clarification":
            await agent.ask_clarification(args.question, args.context, args.options, args.urgency)
        elif args.type == "decision":
            await agent.ask_decision(args.question, args.context, args.options or [], args.urgency)
        elif args.type == "permission":
            await agent.request_permission(args.question, args.context, args.urgency)

    elif args.command == "resolve":
        if await agent.resolve(args.id, args.resolution):
            print(f"Resolved: {args.id}")
        else:
            print(f"Not found: {args.id}")

    elif args.command == "list":
        pending = await agent.get_pending()
        for req in pending:
            print(f"[{req.urgency}] {req.id}: {req.question}")

    elif args.command == "clear":
        count = await agent.clear_resolved()
        print(f"Cleared {count} resolved requests")

    else:
        status = await agent.get_status()
        if args.json:
            print(json.dumps(status.to_dict(), indent=2))
        else:
            print(status.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
