#!/usr/bin/env python3
"""
MCP Integrator Agent - Model Context Protocol Integration

Capabilities:
- Analyze MCP server configurations
- Validate MCP tool definitions
- Check integration patterns
- Generate MCP server templates
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class MCPTool:
    """MCP tool definition."""

    name: str
    description: str
    input_schema: dict = field(default_factory=dict)
    handler: str | None = None


@dataclass
class MCPServer:
    """MCP server information."""

    name: str
    command: str
    args: list[str] = field(default_factory=list)
    env: dict = field(default_factory=dict)
    tools: list[MCPTool] = field(default_factory=list)


@dataclass
class MCPIssue:
    """MCP configuration issue."""

    severity: str
    category: str  # config, security, schema
    location: str
    description: str
    suggestion: str


@dataclass
class MCPReport:
    """MCP integration report."""

    project_path: str
    servers: list[MCPServer] = field(default_factory=list)
    tools_count: int = 0
    issues: list[MCPIssue] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "servers": [
                {"name": s.name, "command": s.command, "args": s.args, "tools_count": len(s.tools)}
                for s in self.servers
            ],
            "tools_count": self.tools_count,
            "issues": [i.__dict__ for i in self.issues],
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        lines = [
            "# MCP Integration Report",
            "",
            f"**Project:** {self.project_path}",
            "",
            "## Summary",
            f"- **MCP Servers:** {len(self.servers)}",
            f"- **Total Tools:** {self.tools_count}",
            f"- **Issues:** {len(self.issues)}",
            "",
        ]

        # Servers
        if self.servers:
            lines.extend(["## Configured Servers", ""])
            for server in self.servers:
                lines.extend(
                    [
                        f"### {server.name}",
                        f"- **Command:** `{server.command}`",
                        f"- **Args:** {' '.join(server.args) if server.args else 'None'}",
                        f"- **Tools:** {len(server.tools)}",
                        "",
                    ]
                )

                if server.tools:
                    lines.append("**Tools:**")
                    for tool in server.tools[:5]:
                        lines.append(f"- `{tool.name}`: {tool.description[:50]}...")
                    if len(server.tools) > 5:
                        lines.append(f"- ... and {len(server.tools) - 5} more")
                    lines.append("")

        # Issues
        if self.issues:
            lines.extend(["## Issues", ""])
            for severity in ["critical", "high", "medium", "low"]:
                severity_issues = [i for i in self.issues if i.severity == severity]
                if severity_issues:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[severity]
                    lines.append(f"### {icon} {severity.title()} ({len(severity_issues)})")
                    for issue in severity_issues:
                        lines.extend(
                            [
                                f"- **{issue.category}** in `{issue.location}`",
                                f"  - {issue.description}",
                                f"  - *Fix:* {issue.suggestion}",
                                "",
                            ]
                        )

        if self.recommendations:
            lines.extend(["## Recommendations", ""])
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")

        return "\n".join(lines)


class MCPIntegrator:
    """MCP integration analysis agent."""

    RECOMMENDED_SERVERS = {
        "filesystem": {
            "description": "File system operations",
            "package": "@anthropic-ai/mcp-server-filesystem",
        },
        "git": {"description": "Git operations", "package": "@anthropic-ai/mcp-server-git"},
        "github": {
            "description": "GitHub API operations",
            "package": "@anthropic-ai/mcp-server-github",
        },
        "memory": {
            "description": "Persistent memory storage",
            "package": "@anthropic-ai/mcp-server-memory",
        },
        "fetch": {
            "description": "HTTP fetch operations",
            "package": "@anthropic-ai/mcp-server-fetch",
        },
        "postgres": {
            "description": "PostgreSQL database operations",
            "package": "@anthropic-ai/mcp-server-postgres",
        },
    }

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def analyze(self) -> MCPReport:
        """Analyze MCP integration."""
        logger.info(f"Analyzing MCP in {self.project_path}")

        servers = []
        issues = []
        tools_count = 0

        # Check Claude settings
        claude_settings = await self._find_claude_settings()
        if claude_settings:
            config_servers, config_issues = self._parse_claude_settings(claude_settings)
            servers.extend(config_servers)
            issues.extend(config_issues)

        # Check for custom MCP servers in project
        custom_servers, custom_issues = await self._find_custom_servers()
        servers.extend(custom_servers)
        issues.extend(custom_issues)

        # Count total tools
        tools_count = sum(len(s.tools) for s in servers)

        # Generate recommendations
        recommendations = self._generate_recommendations(servers, issues)

        return MCPReport(
            project_path=str(self.project_path),
            servers=servers,
            tools_count=tools_count,
            issues=issues,
            recommendations=recommendations,
        )

    async def _find_claude_settings(self) -> dict | None:
        """Find and parse Claude settings."""
        settings_paths = [
            self.project_path / ".claude" / "settings.json",
            self.project_path / ".claude" / "settings.local.json",
            Path.home() / ".claude" / "settings.json",
        ]

        for path in settings_paths:
            if path.exists():
                try:
                    return json.loads(path.read_text())
                except json.JSONDecodeError:
                    pass

        return None

    def _parse_claude_settings(self, settings: dict) -> tuple[list[MCPServer], list[MCPIssue]]:
        """Parse Claude settings for MCP servers."""
        servers = []
        issues = []

        mcp_servers = settings.get("mcpServers", {})

        for name, config in mcp_servers.items():
            command = config.get("command", "")
            args = config.get("args", [])
            env = config.get("env", {})

            server = MCPServer(name=name, command=command, args=args, env=env)
            servers.append(server)

            # Check for issues
            if not command:
                issues.append(
                    MCPIssue(
                        severity="critical",
                        category="config",
                        location=f"mcpServers.{name}",
                        description="MCP server has no command specified",
                        suggestion="Add 'command' field with executable path",
                    )
                )

            # Check for secrets in env
            for key, value in env.items():
                if any(secret in key.lower() for secret in ["key", "secret", "token", "password"]):
                    if not value.startswith("$"):
                        issues.append(
                            MCPIssue(
                                severity="critical",
                                category="security",
                                location=f"mcpServers.{name}.env.{key}",
                                description="Hardcoded secret in MCP configuration",
                                suggestion="Use environment variable reference (${VAR_NAME})",
                            )
                        )

        return servers, issues

    async def _find_custom_servers(self) -> tuple[list[MCPServer], list[MCPIssue]]:
        """Find custom MCP server implementations."""
        servers = []
        issues = []

        # Look for MCP server files
        mcp_patterns = [
            "**/mcp-server*.py",
            "**/mcp_server*.py",
            "**/*-mcp-server.py",
            ".agent/mcp/*.py",
        ]

        for pattern in mcp_patterns:
            for file_path in self.project_path.glob(pattern):
                if any(skip in str(file_path) for skip in ["venv", "node_modules"]):
                    continue

                try:
                    content = file_path.read_text(errors="ignore")
                    rel_path = str(file_path.relative_to(self.project_path))

                    # Extract tools from MCP server
                    tools = self._extract_mcp_tools(content)

                    if tools:
                        server = MCPServer(
                            name=file_path.stem, command="python", args=[rel_path], tools=tools
                        )
                        servers.append(server)

                    # Check for issues in implementation
                    impl_issues = self._check_mcp_implementation(content, rel_path)
                    issues.extend(impl_issues)

                except Exception as e:
                    logger.warning(f"Could not analyze {file_path}: {e}")

        return servers, issues

    def _extract_mcp_tools(self, content: str) -> list[MCPTool]:
        """Extract tool definitions from MCP server code."""
        tools = []

        # Pattern for @tool decorator or tool registration
        tool_patterns = [
            r'@(?:server\.)?tool\([\'"]([^\'"]+)[\'"](?:,\s*description=[\'"]([^\'"]+)[\'"])?\)',
            r'register_tool\([\'"]([^\'"]+)[\'"](?:,\s*[\'"]([^\'"]+)[\'"])?\)',
            r'name=[\'"]([^\'"]+)[\'"].*?description=[\'"]([^\'"]+)[\'"]',
        ]

        for pattern in tool_patterns:
            for match in re.finditer(pattern, content, re.DOTALL):
                tool_name = match.group(1)
                description = match.group(2) if len(match.groups()) > 1 else ""

                tools.append(
                    MCPTool(name=tool_name, description=description or f"Tool: {tool_name}")
                )

        return tools

    def _check_mcp_implementation(self, content: str, file_path: str) -> list[MCPIssue]:
        """Check MCP implementation for issues."""
        issues = []

        # Check for error handling
        if "try:" not in content or "except" not in content:
            issues.append(
                MCPIssue(
                    severity="medium",
                    category="quality",
                    location=file_path,
                    description="MCP server lacks error handling",
                    suggestion="Add try-except blocks around tool handlers",
                )
            )

        # Check for input validation
        if "validate" not in content.lower() and "pydantic" not in content.lower():
            issues.append(
                MCPIssue(
                    severity="medium",
                    category="security",
                    location=file_path,
                    description="MCP server may lack input validation",
                    suggestion="Use Pydantic models or explicit validation",
                )
            )

        # Check for logging
        if "logging" not in content and "logger" not in content:
            issues.append(
                MCPIssue(
                    severity="low",
                    category="quality",
                    location=file_path,
                    description="MCP server has no logging",
                    suggestion="Add logging for debugging and monitoring",
                )
            )

        return issues

    def _generate_recommendations(self, servers: list[MCPServer], issues: list) -> list[str]:
        """Generate recommendations."""
        recommendations = []

        # Check for missing common servers
        server_names = {s.name.lower() for s in servers}

        if "filesystem" not in server_names and "fs" not in server_names:
            recommendations.append("Add filesystem MCP server for file operations")

        if "git" not in server_names:
            recommendations.append("Add git MCP server for version control operations")

        if "memory" not in server_names:
            recommendations.append("Add memory MCP server for persistent context")

        # Security recommendations
        security_issues = [i for i in issues if i.category == "security"]
        if security_issues:
            recommendations.insert(
                0, f"Fix {len(security_issues)} security issues in MCP configuration"
            )

        # Quality recommendations
        if not servers:
            recommendations.append("Set up MCP servers in .claude/settings.json")

        return recommendations[:5]

    async def generate_server_template(self, name: str, tools: list[str]) -> str:
        """Generate MCP server template."""
        tool_defs = []
        for tool_name in tools:
            tool_defs.append(f'''
@server.tool("{tool_name}")
async def {tool_name.replace("-", "_")}(params: dict) -> dict:
    """TODO: Implement {tool_name}."""
    # Your implementation here
    return {{"status": "success"}}
''')

        template = f'''#!/usr/bin/env python3
"""
MCP Server: {name}

Auto-generated template for MCP server implementation.
"""

import asyncio
import json
from mcp.server import Server
from mcp.server.stdio import stdio_server
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

server = Server("{name}")

{"".join(tool_defs)}

async def main():
    async with stdio_server() as (read_stream, write_stream):
        await server.run(read_stream, write_stream)


if __name__ == "__main__":
    asyncio.run(main())
'''
        return template


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="MCP Integrator Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--generate", help="Generate server template with name")
    parser.add_argument("--tools", nargs="*", help="Tools for generated server")
    args = parser.parse_args()

    agent = MCPIntegrator(args.path)

    if args.generate:
        tools = args.tools or ["example-tool"]
        template = await agent.generate_server_template(args.generate, tools)
        print(template)
    else:
        report = await agent.analyze()
        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            print(report.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
