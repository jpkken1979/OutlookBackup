#!/usr/bin/env python3
"""
Antigravity Webhooks - Notification system for external integrations.

Supports:
- Slack: Rich message formatting with blocks
- Discord: Embedded messages
- GitHub: Issue/PR creation
- Custom webhooks: Generic POST endpoints

Usage:
    from webhooks import WebhookManager, WebhookEvent

    manager = WebhookManager()
    manager.notify(WebhookEvent(
        type="task_completed",
        title="Build API Complete",
        description="Task finished successfully",
        data={"tokens": 1500, "cost": 0.05}
    ))
"""

import asyncio
import hashlib
import hmac
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

try:
    from . import security_utils as _security_utils
except ImportError:
    import security_utils as _security_utils  # type: ignore[no-redef]

validate_url_for_ssrf = _security_utils.validate_url_for_ssrf

logger = logging.getLogger("antigravity.webhooks")


# =============================================================================
# CONFIGURATION
# =============================================================================


class WebhookService(str, Enum):
    """Supported webhook services."""

    SLACK = "slack"
    DISCORD = "discord"
    GITHUB = "github"
    TEAMS = "teams"
    CUSTOM = "custom"


@dataclass
class WebhookConfig:
    """Configuration for a webhook endpoint."""

    service: WebhookService
    url: str
    enabled: bool = True
    secret: str | None = None
    channel: str | None = None
    username: str | None = "Antigravity"
    icon_url: str | None = None
    events: list[str] = field(default_factory=lambda: ["all"])


@dataclass
class WebhookEvent:
    """Event to send via webhook."""

    type: str
    title: str
    description: str = ""
    data: dict = field(default_factory=dict)
    severity: str = "info"  # info, warning, error, success
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    source: str = "antigravity"


# =============================================================================
# WEBHOOK FORMATTERS
# =============================================================================


class SlackFormatter:
    """Format messages for Slack webhooks."""

    COLORS = {"info": "#3498db", "warning": "#f39c12", "error": "#e74c3c", "success": "#27ae60"}

    ICONS = {
        "info": "ℹ️",
        "warning": "⚠️",
        "error": "❌",
        "success": "✅",
        "task_started": "🚀",
        "task_completed": "✨",
        "agent_active": "🤖",
        "cost_alert": "💰",
    }

    @classmethod
    def format(cls, event: WebhookEvent, config: WebhookConfig) -> dict:
        """Format event for Slack."""
        icon = cls.ICONS.get(event.type, cls.ICONS.get(event.severity, "📢"))
        color = cls.COLORS.get(event.severity, cls.COLORS["info"])

        blocks = [
            {
                "type": "header",
                "text": {"type": "plain_text", "text": f"{icon} {event.title}", "emoji": True},
            }
        ]

        if event.description:
            blocks.append(
                {"type": "section", "text": {"type": "mrkdwn", "text": event.description}}
            )

        # Add data fields
        if event.data:
            fields = []
            for key, value in list(event.data.items())[:10]:
                fields.append({"type": "mrkdwn", "text": f"*{key}:*\n{value}"})

            if fields:
                blocks.append(
                    {
                        "type": "section",
                        "fields": fields[:10],  # type: ignore[dict-item]  # Slack block structure
                    }
                )

        # Add footer
        blocks.append(
            {
                "type": "context",
                "elements": [
                    {
                        "type": "mrkdwn",  # type: ignore[list-item]  # Slack block structure
                        "text": f"Source: {event.source} | {event.timestamp}",
                    }
                ],
            }
        )

        return {
            "username": config.username or "Antigravity",
            "icon_url": config.icon_url,
            "attachments": [{"color": color, "blocks": blocks}],
        }


class DiscordFormatter:
    """Format messages for Discord webhooks."""

    COLORS = {
        "info": 3447003,  # Blue
        "warning": 15844367,  # Yellow
        "error": 15158332,  # Red
        "success": 3066993,  # Green
    }

    @classmethod
    def format(cls, event: WebhookEvent, config: WebhookConfig) -> dict:
        """Format event for Discord."""
        color = cls.COLORS.get(event.severity, cls.COLORS["info"])

        embed = {
            "title": event.title,
            "description": event.description,
            "color": color,
            "timestamp": event.timestamp,
            "footer": {"text": f"Source: {event.source}"},
        }

        # Add fields for data
        if event.data:
            embed["fields"] = [
                {"name": k, "value": str(v), "inline": True}
                for k, v in list(event.data.items())[:25]
            ]

        return {
            "username": config.username or "Antigravity",
            "avatar_url": config.icon_url,
            "embeds": [embed],
        }


class TeamsFormatter:
    """Format messages for Microsoft Teams webhooks."""

    COLORS = {"info": "0078D7", "warning": "FFC107", "error": "DC3545", "success": "28A745"}

    @classmethod
    def format(cls, event: WebhookEvent, config: WebhookConfig) -> dict:
        """Format event for Teams."""
        color = cls.COLORS.get(event.severity, cls.COLORS["info"])

        facts = [{"name": k, "value": str(v)} for k, v in list(event.data.items())[:10]]

        return {
            "@type": "MessageCard",
            "@context": "http://schema.org/extensions",
            "themeColor": color,
            "summary": event.title,
            "sections": [
                {
                    "activityTitle": event.title,
                    "activitySubtitle": event.source,
                    "facts": facts,
                    "text": event.description,
                }
            ],
        }


class GitHubFormatter:
    """Format for GitHub API (issues/comments)."""

    @classmethod
    def format_issue(cls, event: WebhookEvent, config: WebhookConfig) -> dict:
        """Format event as GitHub issue."""
        body = f"""## {event.title}

{event.description}

### Details

| Key | Value |
|-----|-------|
"""
        for k, v in event.data.items():
            body += f"| {k} | {v} |\n"

        body += f"\n---\n*Source: {event.source} | {event.timestamp}*"

        return {"title": event.title, "body": body, "labels": [event.type, event.severity]}


# =============================================================================
# WEBHOOK MANAGER
# =============================================================================


class WebhookManager:
    """
    Manage webhook notifications across multiple services.

    Usage:
        manager = WebhookManager()
        manager.add_webhook(WebhookConfig(
            service=WebhookService.SLACK,
            url="https://hooks.slack.com/services/..."
        ))
        manager.notify(WebhookEvent(type="info", title="Hello!"))
    """

    def __init__(self, config_path: Path | None = None):
        self.webhooks: list[WebhookConfig] = []
        self.config_path = config_path or Path(__file__).parent.parent / "config" / "webhooks.json"
        self._load_config()

        self.formatters = {
            WebhookService.SLACK: SlackFormatter,
            WebhookService.DISCORD: DiscordFormatter,
            WebhookService.TEAMS: TeamsFormatter,
            WebhookService.GITHUB: GitHubFormatter,
        }

    def _load_config(self) -> None:
        """Load webhook configuration from file."""
        if not self.config_path.exists():
            logger.debug(f"No webhook config at {self.config_path}")
            return

        try:
            with open(self.config_path, encoding="utf-8") as f:
                config = json.load(f)

            for service_name, settings in config.items():
                if settings.get("enabled") and settings.get("url"):
                    self.webhooks.append(
                        WebhookConfig(
                            service=WebhookService(service_name),
                            url=settings["url"],
                            enabled=settings.get("enabled", True),
                            secret=settings.get("secret"),
                            channel=settings.get("channel"),
                            username=settings.get("username", "Antigravity"),
                            events=settings.get("events", ["all"]),
                        )
                    )

            logger.info(f"Loaded {len(self.webhooks)} webhook configurations")

        except Exception as e:
            logger.error(f"Failed to load webhook config: {e}")

    def add_webhook(self, config: WebhookConfig) -> None:
        """Add a webhook configuration."""
        self.webhooks.append(config)
        logger.info(f"Added webhook: {config.service.value}")

    def remove_webhook(self, service: WebhookService) -> bool:
        """Remove a webhook by service type."""
        original_count = len(self.webhooks)
        self.webhooks = [w for w in self.webhooks if w.service != service]
        return len(self.webhooks) < original_count

    def notify(self, event: WebhookEvent) -> dict[str, bool]:
        """
        Send notification to all configured webhooks.

        Args:
            event: Event to send

        Returns:
            Dict mapping service name to success status
        """
        results = {}

        for webhook in self.webhooks:
            if not webhook.enabled:
                continue

            # Check if webhook should receive this event type
            if "all" not in webhook.events and event.type not in webhook.events:
                continue

            try:
                success = self._send(webhook, event)
                results[webhook.service.value] = success
            except Exception as e:
                logger.error(f"Webhook {webhook.service.value} failed: {e}")
                results[webhook.service.value] = False

        return results

    async def notify_async(self, event: WebhookEvent) -> dict[str, bool]:
        """Async version of notify."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.notify, event)

    def _send(self, webhook: WebhookConfig, event: WebhookEvent) -> bool:
        """Send event to a specific webhook."""
        # SSRF: validar URL antes de hacer request
        valid, reason = validate_url_for_ssrf(webhook.url)
        if not valid:
            logger.warning("SSRF bloqueado en webhook %s: %s", webhook.service.value, reason)
            return False
        formatter = self.formatters.get(webhook.service)

        if formatter:
            payload = formatter.format(event, webhook)  # type: ignore[attr-defined]  # formatter protocol: dynamic dispatch
        else:
            # Generic payload for custom webhooks
            payload = {
                "type": event.type,
                "title": event.title,
                "description": event.description,
                "data": event.data,
                "severity": event.severity,
                "timestamp": event.timestamp,
                "source": event.source,
            }

        # Prepare request
        data = json.dumps(payload).encode("utf-8")
        headers = {"Content-Type": "application/json", "User-Agent": "Antigravity/3.0"}

        # Add signature if secret is configured
        if webhook.secret:
            signature = hmac.new(webhook.secret.encode(), data, hashlib.sha256).hexdigest()
            headers["X-Antigravity-Signature"] = f"sha256={signature}"

        request = Request(webhook.url, data=data, headers=headers, method="POST")

        try:
            with urlopen(request, timeout=10) as response:
                success = 200 <= response.status < 300
                if success:
                    logger.debug(f"Webhook {webhook.service.value} sent successfully")
                return success
        except URLError as e:
            logger.error(f"Webhook request failed: {e}")
            return False

    def test(self, service: str) -> bool:
        """Test a specific webhook."""
        test_event = WebhookEvent(
            type="test",
            title="🧪 Antigravity Webhook Test",
            description="This is a test notification from Antigravity.",
            data={"status": "testing", "timestamp": datetime.now().isoformat()},
            severity="info",
        )

        # Find webhook for service
        webhook = next((w for w in self.webhooks if w.service.value == service), None)

        if not webhook:
            logger.warning(f"No webhook configured for {service}")
            return False

        return self._send(webhook, test_event)

    def save_config(self) -> None:
        """Save current configuration to file."""
        config = {}
        for webhook in self.webhooks:
            config[webhook.service.value] = {
                "url": webhook.url,
                "enabled": webhook.enabled,
                "secret": webhook.secret,
                "channel": webhook.channel,
                "username": webhook.username,
                "events": webhook.events,
            }

        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2)

        logger.info(f"Saved webhook config to {self.config_path}")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================

_manager: WebhookManager | None = None


def get_webhook_manager() -> WebhookManager:
    """Get the global webhook manager."""
    global _manager
    if _manager is None:
        _manager = WebhookManager()
    return _manager


def notify(
    title: str,
    description: str = "",
    event_type: str = "info",
    severity: str = "info",
    data: dict | None = None,
) -> dict[str, bool]:
    """
    Send a notification to all configured webhooks.

    Args:
        title: Notification title
        description: Optional description
        event_type: Type of event (task_started, task_completed, etc.)
        severity: Severity level (info, warning, error, success)
        data: Additional data to include

    Returns:
        Dict mapping service name to success status
    """
    event = WebhookEvent(
        type=event_type, title=title, description=description, data=data or {}, severity=severity
    )

    return get_webhook_manager().notify(event)


def notify_task_started(task: str, agents: list[str]) -> dict[str, bool]:
    """Notify that a task has started."""
    return notify(
        title="🚀 Task Started",
        description=f"Executing: {task}",
        event_type="task_started",
        severity="info",
        data={"agents": ", ".join(agents)},
    )


def notify_task_completed(
    task: str, duration_seconds: float, tokens_used: int, cost_usd: float
) -> dict[str, bool]:
    """Notify that a task has completed."""
    return notify(
        title="✅ Task Completed",
        description=f"Finished: {task}",
        event_type="task_completed",
        severity="success",
        data={
            "Duration": f"{duration_seconds:.1f}s",
            "Tokens": f"{tokens_used:,}",
            "Cost": f"${cost_usd:.4f}",
        },
    )


def notify_error(error_message: str, context: dict | None = None) -> dict[str, bool]:
    """Notify about an error."""
    return notify(
        title="❌ Error Occurred",
        description=error_message,
        event_type="error",
        severity="error",
        data=context or {},
    )


# =============================================================================
# CLI
# =============================================================================


def main():
    """Test webhooks from command line."""
    import argparse

    parser = argparse.ArgumentParser(description="Antigravity Webhooks")
    parser.add_argument("action", choices=["test", "list", "add"])
    parser.add_argument("--service", "-s", choices=["slack", "discord", "github", "teams"])
    parser.add_argument("--url", "-u", help="Webhook URL")

    args = parser.parse_args()
    manager = WebhookManager()

    if args.action == "list":
        print("\nConfigured Webhooks:")
        print("-" * 40)
        for webhook in manager.webhooks:
            status = "✓" if webhook.enabled else "✗"
            print(f"  [{status}] {webhook.service.value}: {webhook.url[:50]}...")

    elif args.action == "test":
        if not args.service:
            print("Error: --service required for test")
            return

        print(f"Testing {args.service} webhook...")
        success = manager.test(args.service)
        print("Success!" if success else "Failed!")

    elif args.action == "add":
        if not args.service or not args.url:
            print("Error: --service and --url required for add")
            return

        manager.add_webhook(WebhookConfig(service=WebhookService(args.service), url=args.url))
        manager.save_config()
        print(f"Added {args.service} webhook")


if __name__ == "__main__":
    main()
