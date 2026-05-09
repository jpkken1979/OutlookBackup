#!/usr/bin/env python3
"""
Notification Manager Agent - Notification system analysis.

Usage:
    python notification_manager.py <project_path> [--json]
"""

import argparse
import contextlib
import json
import logging
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class NotificationIssue:
    """Notification system issue."""

    id: str
    category: str  # deliverability, reliability, ux, security
    severity: str
    title: str
    location: str
    description: str
    fix: str


@dataclass
class NotificationReport:
    """Notification system analysis report."""

    project_path: str
    timestamp: str
    channels: list = field(default_factory=list)
    issues: list = field(default_factory=list)
    capabilities: dict = field(default_factory=dict)
    recommendations: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class NotificationManager:
    """Notification system analysis agent."""

    CHANNEL_PATTERNS = {
        "email": ["sendgrid", "ses", "postmark", "mailgun", "smtp", "nodemailer", "send_mail"],
        "push_mobile": ["fcm", "apns", "firebase", "expo-notifications", "onesignal"],
        "push_web": ["web-push", "service-worker", "pushManager"],
        "sms": ["twilio", "nexmo", "sns", "plivo"],
        "in_app": ["notification", "toast", "snackbar", "alert"],
        "webhook": ["webhook", "callback_url", "notify_url"],
        "slack": ["slack", "slack-sdk", "slack_webhook"],
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.issue_counter = 0

    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        self.issue_counter += 1
        return f"NOTIF-{self.issue_counter:03d}"

    def _detect_channels(self) -> list[str]:
        """Detect notification channels in use."""
        channels = []

        all_content = ""
        for ext in ["*.py", "*.js", "*.ts", "*.json", "*.yaml"]:
            for file_path in self.project_path.rglob(ext):
                if any(skip in str(file_path) for skip in ["node_modules", ".git", "venv"]):
                    continue
                with contextlib.suppress(Exception):
                    all_content += file_path.read_text().lower()

        for channel, patterns in self.CHANNEL_PATTERNS.items():
            if any(p in all_content for p in patterns):
                channels.append(channel)

        return channels

    def _check_capabilities(self) -> dict:
        """Check notification capabilities."""
        capabilities = {
            "templating": False,
            "queuing": False,
            "retry_logic": False,
            "preference_management": False,
            "analytics": False,
            "rate_limiting": False,
            "unsubscribe": False,
        }

        all_content = ""
        for ext in ["*.py", "*.js", "*.ts"]:
            for file_path in self.project_path.rglob(ext):
                if "node_modules" in str(file_path):
                    continue
                with contextlib.suppress(Exception):
                    all_content += file_path.read_text().lower()

        patterns = {
            "templating": ["template", "jinja", "handlebars", "mustache", "render"],
            "queuing": ["queue", "celery", "bull", "sqs", "rabbitmq", "redis"],
            "retry_logic": ["retry", "backoff", "attempt"],
            "preference_management": ["preference", "subscribe", "unsubscribe", "opt-out"],
            "analytics": ["track", "analytics", "metric", "open_rate", "click"],
            "rate_limiting": ["rate_limit", "throttle", "quota"],
            "unsubscribe": ["unsubscribe", "opt-out", "opt_out"],
        }

        for capability, keywords in patterns.items():
            if any(kw in all_content for kw in keywords):
                capabilities[capability] = True

        return capabilities

    def analyze_issues(self) -> list[NotificationIssue]:
        """Analyze notification system for issues."""
        issues = []
        capabilities = self._check_capabilities()

        # Check for missing critical capabilities
        if not capabilities["queuing"]:
            issues.append(
                NotificationIssue(
                    id=self._generate_issue_id(),
                    category="reliability",
                    severity="high",
                    title="No message queuing",
                    location="notification system",
                    description="Notifications sent synchronously without queue.",
                    fix="Implement message queue (Redis, RabbitMQ, SQS) for reliability",
                )
            )

        if not capabilities["retry_logic"]:
            issues.append(
                NotificationIssue(
                    id=self._generate_issue_id(),
                    category="reliability",
                    severity="high",
                    title="No retry logic",
                    location="notification system",
                    description="Failed notifications may be lost without retries.",
                    fix="Implement exponential backoff retry with dead letter queue",
                )
            )

        if not capabilities["unsubscribe"]:
            issues.append(
                NotificationIssue(
                    id=self._generate_issue_id(),
                    category="security",
                    severity="critical",
                    title="No unsubscribe mechanism",
                    location="notification system",
                    description="Missing unsubscribe violates CAN-SPAM/GDPR.",
                    fix="Add unsubscribe link to all marketing emails",
                )
            )

        if not capabilities["templating"]:
            issues.append(
                NotificationIssue(
                    id=self._generate_issue_id(),
                    category="ux",
                    severity="medium",
                    title="No template system",
                    location="notification system",
                    description="Notifications may lack consistent formatting.",
                    fix="Implement template engine for consistent messaging",
                )
            )

        # Check for specific code issues
        for file_path in self.project_path.rglob("*.py"):
            if "venv" in str(file_path):
                continue
            try:
                content = file_path.read_text()
                relative_path = str(file_path.relative_to(self.project_path))

                # Check for hardcoded API keys
                if re.search(r'(api_key|apikey)\s*=\s*["\'][^"\']+["\']', content, re.IGNORECASE):
                    if "sendgrid" in content.lower() or "twilio" in content.lower():
                        issues.append(
                            NotificationIssue(
                                id=self._generate_issue_id(),
                                category="security",
                                severity="critical",
                                title="Hardcoded notification API key",
                                location=relative_path,
                                description="API key for notification service in source code.",
                                fix="Use environment variables for API keys",
                            )
                        )

                # Check for synchronous sending in request handlers
                if (
                    "send_mail" in content or "send_notification" in content
                ) and "async" not in content:
                    if "def " in content and (
                        "view" in content.lower() or "handler" in content.lower()
                    ):
                        issues.append(
                            NotificationIssue(
                                id=self._generate_issue_id(),
                                category="reliability",
                                severity="medium",
                                title="Synchronous notification in request handler",
                                location=relative_path,
                                description="Sending notifications blocks the request.",
                                fix="Offload to background task/queue",
                            )
                        )

            except Exception as e:
                logger.debug(f"Error analyzing {file_path}: {e}")

        return issues

    def generate_report(self) -> NotificationReport:
        """Generate comprehensive notification report."""
        logger.info(f"Analyzing notification system: {self.project_path}")

        channels = self._detect_channels()
        capabilities = self._check_capabilities()
        issues = self.analyze_issues()

        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        # Generate recommendations
        recommendations = []

        if severity_counts["critical"] > 0:
            recommendations.append("Fix compliance issues (unsubscribe, API keys) immediately")

        if "email" in channels:
            recommendations.extend(
                [
                    "Set up SPF, DKIM, and DMARC for email deliverability",
                    "Monitor bounce and complaint rates",
                    "Warm up sending domain before high volume",
                ]
            )

        if "push_mobile" in channels:
            recommendations.extend(
                [
                    "Handle token refresh for push notifications",
                    "Implement notification grouping to reduce badge count",
                ]
            )

        recommendations.extend(
            [
                "Add notification analytics (delivery, open, click rates)",
                "Implement user preference center",
                "Set up quiet hours / do not disturb",
            ]
        )

        return NotificationReport(
            project_path=str(self.project_path),
            timestamp=datetime.now().isoformat(),
            channels=channels,
            issues=[asdict(i) for i in issues],
            capabilities=capabilities,
            recommendations=recommendations,
            summary={
                "total_issues": len(issues),
                "by_severity": severity_counts,
                "channel_count": len(channels),
            },
        )


def format_report_markdown(report: NotificationReport) -> str:
    """Format report as markdown."""
    lines = [
        "# Notification System Analysis Report",
        "",
        f"**Project:** {report.project_path}",
        f"**Date:** {report.timestamp}",
        "",
        "## Notification Channels",
        "",
    ]

    for channel in report.channels:
        lines.append(f"- ✅ {channel.replace('_', ' ').title()}")

    lines.extend(["", "## Capabilities", ""])

    for capability, enabled in report.capabilities.items():
        emoji = "✅" if enabled else "❌"
        lines.append(f"- {emoji} {capability.replace('_', ' ').title()}")

    lines.extend(["", "## Issues", ""])

    for issue in report.issues:
        severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
            issue.get("severity", ""), "⚪"
        )
        lines.extend(
            [
                f"### {severity_emoji} {issue.get('id', '')}: {issue.get('title', '')}",
                "",
                f"**Category:** {issue.get('category', '')}",
                "",
                issue.get("description", ""),
                "",
                f"**Fix:** {issue.get('fix', '')}",
                "",
                "---",
                "",
            ]
        )

    lines.extend(["", "## Recommendations", ""])
    for i, rec in enumerate(report.recommendations, 1):
        lines.append(f"{i}. {rec}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Notification Manager Agent")
    parser.add_argument("project", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    manager = NotificationManager(args.project)
    report = manager.generate_report()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
