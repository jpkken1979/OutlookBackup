#!/usr/bin/env python3
"""
API Gateway Specialist Agent - API gateway and management analysis.

Usage:
    python api_gateway_specialist.py <project_path> [--json]
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
class GatewayIssue:
    """API Gateway issue."""

    id: str
    category: str  # security, performance, reliability, observability
    severity: str
    title: str
    location: str
    description: str
    fix: str


@dataclass
class GatewayReport:
    """API Gateway analysis report."""

    project_path: str
    timestamp: str
    gateway_type: str
    issues: list = field(default_factory=list)
    endpoints: list = field(default_factory=list)
    capabilities: dict = field(default_factory=dict)
    recommendations: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class APIGatewaySpecialist:
    """API Gateway analysis agent."""

    GATEWAY_PATTERNS = {
        "kong": ["kong.conf", "kong.yml", "KongPlugin"],
        "nginx": ["nginx.conf", "upstream", "proxy_pass"],
        "traefik": ["traefik.yml", "traefik.toml", "IngressRoute"],
        "aws_api_gateway": ["aws_api_gateway", "x-amazon-apigateway"],
        "express_gateway": ["gateway.config.yml", "express-gateway"],
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.issue_counter = 0

    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        self.issue_counter += 1
        return f"GW-{self.issue_counter:03d}"

    def _detect_gateway(self) -> str:
        """Detect API gateway type."""
        all_content = ""
        all_files = ""

        for ext in ["*.yaml", "*.yml", "*.json", "*.conf", "*.tf"]:
            for file_path in self.project_path.rglob(ext):
                all_files += str(file_path) + " "
                with contextlib.suppress(Exception):
                    all_content += file_path.read_text()

        for gateway, patterns in self.GATEWAY_PATTERNS.items():
            for pattern in patterns:
                if pattern.lower() in all_content.lower() or pattern.lower() in all_files.lower():
                    return gateway

        return "unknown"

    def _detect_endpoints(self) -> list[str]:
        """Detect API endpoints."""
        endpoints = []

        for file_path in self.project_path.rglob("*.yaml"):
            try:
                content = file_path.read_text()
                # OpenAPI paths
                paths = re.findall(r"^\s*(/[a-zA-Z0-9/{}_-]+):", content, re.MULTILINE)
                endpoints.extend(paths)
            except Exception:
                pass

        # Also check Python files for route definitions
        for file_path in self.project_path.rglob("*.py"):
            try:
                content = file_path.read_text()
                routes = re.findall(r'@\w+\.(get|post|put|delete|patch)\(["\']([^"\']+)', content)
                endpoints.extend([f"{m.upper()} {p}" for m, p in routes])
            except Exception:
                pass

        return list(set(endpoints))[:50]  # Limit to 50

    def _check_capabilities(self) -> dict:
        """Check gateway capabilities."""
        capabilities = {
            "rate_limiting": False,
            "authentication": False,
            "cors": False,
            "caching": False,
            "circuit_breaker": False,
            "request_validation": False,
            "logging": False,
            "metrics": False,
        }

        all_content = ""
        for ext in ["*.yaml", "*.yml", "*.json", "*.conf", "*.py"]:
            for file_path in self.project_path.rglob(ext):
                with contextlib.suppress(Exception):
                    all_content += file_path.read_text().lower()

        patterns = {
            "rate_limiting": ["rate_limit", "throttl", "quota"],
            "authentication": ["jwt", "oauth", "api_key", "bearer", "auth"],
            "cors": ["cors", "access-control-allow"],
            "caching": ["cache", "ttl", "max-age"],
            "circuit_breaker": ["circuit", "breaker", "retry", "timeout"],
            "request_validation": ["validat", "schema", "openapi"],
            "logging": ["log", "access_log", "error_log"],
            "metrics": ["metric", "prometheus", "statsd"],
        }

        for capability, keywords in patterns.items():
            if any(kw in all_content for kw in keywords):
                capabilities[capability] = True

        return capabilities

    def analyze_security(self) -> list[GatewayIssue]:
        """Analyze security configuration."""
        issues = []

        capabilities = self._check_capabilities()

        if not capabilities["authentication"]:
            issues.append(
                GatewayIssue(
                    id=self._generate_issue_id(),
                    category="security",
                    severity="critical",
                    title="No authentication detected",
                    location="gateway configuration",
                    description="API gateway has no visible authentication mechanism.",
                    fix="Implement OAuth2, JWT, or API key authentication",
                )
            )

        if not capabilities["rate_limiting"]:
            issues.append(
                GatewayIssue(
                    id=self._generate_issue_id(),
                    category="security",
                    severity="high",
                    title="No rate limiting",
                    location="gateway configuration",
                    description="No rate limiting configuration found.",
                    fix="Add rate limiting to prevent abuse and DDoS",
                )
            )

        # Check for specific security issues in config files
        for file_path in self.project_path.rglob("*.yaml"):
            try:
                content = file_path.read_text()
                relative_path = str(file_path.relative_to(self.project_path))

                # Check for wildcard CORS
                if "*" in content and "cors" in content.lower():
                    issues.append(
                        GatewayIssue(
                            id=self._generate_issue_id(),
                            category="security",
                            severity="medium",
                            title="Wildcard CORS origin",
                            location=relative_path,
                            description="CORS allows all origins (*)",
                            fix="Restrict CORS to specific allowed domains",
                        )
                    )

            except Exception:
                pass

        return issues

    def analyze_performance(self) -> list[GatewayIssue]:
        """Analyze performance configuration."""
        issues = []

        capabilities = self._check_capabilities()

        if not capabilities["caching"]:
            issues.append(
                GatewayIssue(
                    id=self._generate_issue_id(),
                    category="performance",
                    severity="medium",
                    title="No caching configured",
                    location="gateway configuration",
                    description="Response caching not configured.",
                    fix="Add caching for GET requests to reduce backend load",
                )
            )

        if not capabilities["circuit_breaker"]:
            issues.append(
                GatewayIssue(
                    id=self._generate_issue_id(),
                    category="reliability",
                    severity="high",
                    title="No circuit breaker",
                    location="gateway configuration",
                    description="Circuit breaker pattern not implemented.",
                    fix="Add circuit breaker to handle backend failures gracefully",
                )
            )

        return issues

    def analyze_observability(self) -> list[GatewayIssue]:
        """Analyze observability configuration."""
        issues = []

        capabilities = self._check_capabilities()

        if not capabilities["logging"]:
            issues.append(
                GatewayIssue(
                    id=self._generate_issue_id(),
                    category="observability",
                    severity="high",
                    title="No access logging",
                    location="gateway configuration",
                    description="Request logging not configured.",
                    fix="Enable access logs with request ID for debugging",
                )
            )

        if not capabilities["metrics"]:
            issues.append(
                GatewayIssue(
                    id=self._generate_issue_id(),
                    category="observability",
                    severity="medium",
                    title="No metrics export",
                    location="gateway configuration",
                    description="Metrics export not configured.",
                    fix="Export metrics to Prometheus or similar",
                )
            )

        return issues

    def generate_report(self) -> GatewayReport:
        """Generate comprehensive gateway report."""
        logger.info(f"Analyzing API gateway: {self.project_path}")

        gateway_type = self._detect_gateway()
        endpoints = self._detect_endpoints()
        capabilities = self._check_capabilities()

        issues = []
        issues.extend(self.analyze_security())
        issues.extend(self.analyze_performance())
        issues.extend(self.analyze_observability())

        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        # Generate recommendations
        recommendations = []

        if severity_counts["critical"] > 0:
            recommendations.append("Implement authentication immediately")

        recommendations.extend(
            [
                "Add request/response validation with OpenAPI schemas",
                "Implement distributed tracing with correlation IDs",
                "Set up alerting for error rate and latency",
                "Document API versioning strategy",
                "Configure health check endpoints",
            ]
        )

        return GatewayReport(
            project_path=str(self.project_path),
            timestamp=datetime.now().isoformat(),
            gateway_type=gateway_type,
            issues=[asdict(i) for i in issues],
            endpoints=endpoints,
            capabilities=capabilities,
            recommendations=recommendations,
            summary={
                "total_issues": len(issues),
                "by_severity": severity_counts,
                "endpoint_count": len(endpoints),
                "gateway_type": gateway_type,
            },
        )


def format_report_markdown(report: GatewayReport) -> str:
    """Format report as markdown."""
    lines = [
        "# API Gateway Analysis Report",
        "",
        f"**Project:** {report.project_path}",
        f"**Gateway Type:** {report.gateway_type}",
        f"**Date:** {report.timestamp}",
        "",
        "## Capabilities",
        "",
    ]

    for capability, enabled in report.capabilities.items():
        emoji = "✅" if enabled else "❌"
        lines.append(f"- {emoji} {capability.replace('_', ' ').title()}")

    lines.extend(["", f"## Endpoints Detected ({len(report.endpoints)})", ""])
    for endpoint in report.endpoints[:10]:
        lines.append(f"- `{endpoint}`")
    if len(report.endpoints) > 10:
        lines.append(f"- ... and {len(report.endpoints) - 10} more")

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
    parser = argparse.ArgumentParser(description="API Gateway Specialist Agent")
    parser.add_argument("project", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    specialist = APIGatewaySpecialist(args.project)
    report = specialist.generate_report()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
