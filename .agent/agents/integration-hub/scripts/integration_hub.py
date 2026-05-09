#!/usr/bin/env python3
"""
Integration Hub Agent - Integraciones con herramientas externas

Conecta con Jira, Linear, Slack, GitHub, Notion y mas.
"""

import argparse
import json
import os
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class Platform(Enum):
    GITHUB = "github"
    GITLAB = "gitlab"
    JIRA = "jira"
    LINEAR = "linear"
    SLACK = "slack"
    DISCORD = "discord"
    NOTION = "notion"
    CONFLUENCE = "confluence"


class OperationType(Enum):
    CREATE = "create"
    READ = "read"
    UPDATE = "update"
    DELETE = "delete"
    SYNC = "sync"
    NOTIFY = "notify"


@dataclass
class IntegrationConfig:
    platform: Platform
    enabled: bool
    api_url: str
    auth_type: str  # oauth, token, api_key
    credentials: dict = field(default_factory=dict)


@dataclass
class IntegrationResult:
    success: bool
    platform: str
    operation: str
    message: str
    data: dict | None = None
    error: str | None = None


class IntegrationHub:
    """Hub central de integraciones."""

    def __init__(self):
        self.configs = self._load_configs()

    def _load_configs(self) -> dict[Platform, IntegrationConfig]:
        """Carga configuraciones de integraciones."""
        configs = {}

        # GitHub
        github_token = os.getenv("GITHUB_TOKEN")
        if github_token:
            configs[Platform.GITHUB] = IntegrationConfig(
                platform=Platform.GITHUB,
                enabled=True,
                api_url="https://api.github.com",
                auth_type="token",
                credentials={"token": github_token},
            )

        # Slack
        slack_token = os.getenv("SLACK_BOT_TOKEN")
        if slack_token:
            configs[Platform.SLACK] = IntegrationConfig(
                platform=Platform.SLACK,
                enabled=True,
                api_url="https://slack.com/api",
                auth_type="bot_token",
                credentials={"token": slack_token},
            )

        # Jira
        jira_url = os.getenv("JIRA_URL")
        jira_token = os.getenv("JIRA_TOKEN")
        if jira_url and jira_token:
            configs[Platform.JIRA] = IntegrationConfig(
                platform=Platform.JIRA,
                enabled=True,
                api_url=jira_url,
                auth_type="basic",
                credentials={"email": os.getenv("JIRA_EMAIL", ""), "token": jira_token},
            )

        # Linear
        linear_key = os.getenv("LINEAR_API_KEY")
        if linear_key:
            configs[Platform.LINEAR] = IntegrationConfig(
                platform=Platform.LINEAR,
                enabled=True,
                api_url="https://api.linear.app/graphql",
                auth_type="api_key",
                credentials={"key": linear_key},
            )

        # Notion
        notion_token = os.getenv("NOTION_TOKEN")
        if notion_token:
            configs[Platform.NOTION] = IntegrationConfig(
                platform=Platform.NOTION,
                enabled=True,
                api_url="https://api.notion.com/v1",
                auth_type="integration",
                credentials={"token": notion_token},
            )

        return configs

    def get_available_integrations(self) -> list[str]:
        """Retorna integraciones disponibles."""
        return [p.value for p, c in self.configs.items() if c.enabled]

    def github_create_issue(
        self, repo: str, title: str, body: str | None = None, labels: list[str] | None = None
    ) -> IntegrationResult:
        """Crea issue en GitHub."""
        config = self.configs.get(Platform.GITHUB)
        if not config:
            return IntegrationResult(
                success=False,
                platform="github",
                operation="create_issue",
                message="GitHub not configured",
                error="Missing GITHUB_TOKEN",
            )

        # En produccion: usar httpx/requests
        # Aqui simulamos
        return IntegrationResult(
            success=True,
            platform="github",
            operation="create_issue",
            message=f"Issue created in {repo}",
            data={
                "repo": repo,
                "title": title,
                "body": body,
                "labels": labels or [],
                "url": f"https://github.com/{repo}/issues/1",
            },
        )

    def slack_notify(
        self, channel: str, message: str, thread_ts: str | None = None
    ) -> IntegrationResult:
        """Envia mensaje a Slack."""
        config = self.configs.get(Platform.SLACK)
        if not config:
            return IntegrationResult(
                success=False,
                platform="slack",
                operation="notify",
                message="Slack not configured",
                error="Missing SLACK_BOT_TOKEN",
            )

        # Simulacion
        return IntegrationResult(
            success=True,
            platform="slack",
            operation="notify",
            message=f"Message sent to {channel}",
            data={
                "channel": channel,
                "message": message[:100] + "..." if len(message) > 100 else message,
                "ts": datetime.now().timestamp(),
            },
        )

    def jira_create_issue(
        self, project: str, summary: str, description: str | None = None, issue_type: str = "Task"
    ) -> IntegrationResult:
        """Crea issue en Jira."""
        config = self.configs.get(Platform.JIRA)
        if not config:
            return IntegrationResult(
                success=False,
                platform="jira",
                operation="create_issue",
                message="Jira not configured",
                error="Missing JIRA_URL or JIRA_TOKEN",
            )

        # Simulacion
        return IntegrationResult(
            success=True,
            platform="jira",
            operation="create_issue",
            message=f"Issue created in {project}",
            data={
                "project": project,
                "key": f"{project}-123",
                "summary": summary,
                "type": issue_type,
                "url": f"{config.api_url}/browse/{project}-123",
            },
        )

    def linear_create_issue(
        self, team: str, title: str, description: str | None = None, priority: int = 3
    ) -> IntegrationResult:
        """Crea issue en Linear."""
        config = self.configs.get(Platform.LINEAR)
        if not config:
            return IntegrationResult(
                success=False,
                platform="linear",
                operation="create_issue",
                message="Linear not configured",
                error="Missing LINEAR_API_KEY",
            )

        # Simulacion
        return IntegrationResult(
            success=True,
            platform="linear",
            operation="create_issue",
            message=f"Issue created in {team}",
            data={
                "team": team,
                "identifier": f"{team.upper()[:3]}-123",
                "title": title,
                "priority": priority,
                "url": f"https://linear.app/{team}/issue/123",
            },
        )

    def notion_create_page(
        self, parent_id: str, title: str, content: str | None = None
    ) -> IntegrationResult:
        """Crea pagina en Notion."""
        config = self.configs.get(Platform.NOTION)
        if not config:
            return IntegrationResult(
                success=False,
                platform="notion",
                operation="create_page",
                message="Notion not configured",
                error="Missing NOTION_TOKEN",
            )

        # Simulacion
        return IntegrationResult(
            success=True,
            platform="notion",
            operation="create_page",
            message="Page created",
            data={"parent_id": parent_id, "title": title, "url": "https://notion.so/page-id"},
        )

    def execute(self, command: str) -> IntegrationResult:
        """Ejecuta comando de integracion."""
        command.lower()

        # Parsear comando
        # Formato: platform: action "args"
        match = re.match(r"(\w+):\s*(.+)", command)
        if not match:
            return IntegrationResult(
                success=False,
                platform="unknown",
                operation="parse",
                message="Invalid command format",
                error="Use: platform: action 'arguments'",
            )

        platform = match.group(1).lower()
        action_args = match.group(2).strip()

        # Extraer argumentos entre comillas
        quoted = re.findall(r'["\'](.+?)["\']', action_args)
        action = action_args.split()[0].lower() if action_args else ""

        if platform == "github":
            if "issue" in action or "create" in action:
                title = quoted[0] if quoted else "New Issue"
                return self.github_create_issue("owner/repo", title)

        elif platform == "slack":
            if "notify" in action or "send" in action or "message" in action:
                channel = "#general"
                message = quoted[0] if quoted else "Notification"

                # Extraer canal si se especifica
                channel_match = re.search(r"#(\w+)", action_args)
                if channel_match:
                    channel = f"#{channel_match.group(1)}"

                return self.slack_notify(channel, message)

        elif platform == "jira":
            if "issue" in action or "create" in action:
                summary = quoted[0] if quoted else "New Task"
                return self.jira_create_issue("PROJ", summary)

        elif platform == "linear":
            if "issue" in action or "create" in action:
                title = quoted[0] if quoted else "New Issue"
                return self.linear_create_issue("engineering", title)

        elif platform == "notion":
            if "page" in action or "create" in action:
                title = quoted[0] if quoted else "New Page"
                return self.notion_create_page("parent-id", title)

        elif platform == "list" or platform == "status":
            available = self.get_available_integrations()
            return IntegrationResult(
                success=True,
                platform="hub",
                operation="list",
                message=f"Available: {', '.join(available) if available else 'None configured'}",
                data={"integrations": available},
            )

        return IntegrationResult(
            success=False,
            platform=platform,
            operation=action,
            message=f"Unknown platform or action: {platform}:{action}",
            error="Supported: github, slack, jira, linear, notion",
        )


def main():
    parser = argparse.ArgumentParser(
        description="Integration Hub - Conexion con herramientas externas"
    )
    parser.add_argument(
        "command", nargs="?", default="list", help="Comando (platform: action 'args')"
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")

    args = parser.parse_args()

    hub = IntegrationHub()
    result = hub.execute(args.command)

    if args.json:
        print(
            json.dumps(
                {
                    "success": result.success,
                    "platform": result.platform,
                    "operation": result.operation,
                    "message": result.message,
                    "data": result.data,
                    "error": result.error,
                },
                indent=2,
            )
        )
    else:
        status = "✓" if result.success else "✗"
        print(f"[{status}] {result.platform}:{result.operation}")
        print(f"    {result.message}")

        if result.data:
            for key, value in result.data.items():
                print(f"    {key}: {value}")

        if result.error:
            print(f"    Error: {result.error}")

    sys.exit(0 if result.success else 1)


if __name__ == "__main__":
    main()
