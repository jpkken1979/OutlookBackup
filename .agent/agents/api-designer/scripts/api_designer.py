#!/usr/bin/env python3
"""
API Designer Agent - REST/GraphQL API Design & Validation

Capabilities:
- Validate OpenAPI/Swagger specifications
- Check REST API best practices
- Analyze endpoint consistency
- Generate API documentation
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
class APIEndpoint:
    """API endpoint definition."""

    method: str
    path: str
    summary: str | None = None
    parameters: list[dict] = field(default_factory=list)
    request_body: dict | None = None
    responses: dict = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)


@dataclass
class APIIssue:
    """API design issue."""

    severity: str  # critical, high, medium, low
    endpoint: str | None
    rule: str
    description: str
    suggestion: str


@dataclass
class APIReport:
    """API analysis report."""

    project_path: str
    spec_file: str | None = None
    api_version: str = "unknown"
    base_url: str | None = None
    endpoints: list[APIEndpoint] = field(default_factory=list)
    issues: list[APIIssue] = field(default_factory=list)
    score: int = 100
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "spec_file": self.spec_file,
            "api_version": self.api_version,
            "base_url": self.base_url,
            "endpoints_count": len(self.endpoints),
            "endpoints": [e.__dict__ for e in self.endpoints],
            "issues": {
                "total": len(self.issues),
                "by_severity": {
                    s: sum(1 for i in self.issues if i.severity == s)
                    for s in ["critical", "high", "medium", "low"]
                },
                "details": [i.__dict__ for i in self.issues],
            },
            "score": self.score,
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        lines = [
            "# API Design Report",
            "",
            f"**Project:** {self.project_path}",
            f"**Spec File:** {self.spec_file or 'Not found'}",
            f"**API Version:** {self.api_version}",
            f"**Design Score:** {self.score}/100",
            "",
            "## Summary",
            f"- **Total Endpoints:** {len(self.endpoints)}",
            f"- **Issues Found:** {len(self.issues)}",
            "",
        ]

        # Endpoints by method
        methods = {}
        for ep in self.endpoints:
            methods[ep.method] = methods.get(ep.method, 0) + 1

        if methods:
            lines.extend(["## Endpoints by Method", ""])
            for method, count in sorted(methods.items()):
                lines.append(f"- **{method}:** {count}")
            lines.append("")

        # Endpoint list
        if self.endpoints:
            lines.extend(
                ["## Endpoints", "", "| Method | Path | Summary |", "|--------|------|---------|"]
            )
            for ep in self.endpoints[:30]:
                summary = (ep.summary or "")[:50]
                lines.append(f"| `{ep.method}` | `{ep.path}` | {summary} |")
            if len(self.endpoints) > 30:
                lines.append(f"| ... | +{len(self.endpoints) - 30} more | ... |")
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
                                f"- **{issue.rule}**"
                                + (f" on `{issue.endpoint}`" if issue.endpoint else ""),
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


class APIDesigner:
    """API design analysis agent."""

    # REST API Best Practices Rules
    RULES = {
        "plural-resources": {
            "description": "Resource names should be plural nouns",
            "severity": "medium",
        },
        "no-verbs-in-path": {
            "description": "Paths should not contain verbs (use HTTP methods)",
            "severity": "high",
        },
        "consistent-naming": {
            "description": "Use consistent naming convention (kebab-case or snake_case)",
            "severity": "medium",
        },
        "version-in-path": {"description": "API should include version in path", "severity": "low"},
        "proper-status-codes": {
            "description": "Use appropriate HTTP status codes",
            "severity": "high",
        },
        "error-schema": {
            "description": "Error responses should have consistent schema",
            "severity": "medium",
        },
        "pagination": {
            "description": "List endpoints should support pagination",
            "severity": "medium",
        },
        "security-defined": {
            "description": "API should define security schemes",
            "severity": "critical",
        },
    }

    VERB_PATTERNS = [
        r"/get[A-Z]",
        r"/create[A-Z]",
        r"/update[A-Z]",
        r"/delete[A-Z]",
        r"/fetch[A-Z]",
        r"/add[A-Z]",
        r"/remove[A-Z]",
        r"/modify[A-Z]",
    ]

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def analyze(self) -> APIReport:
        """Analyze API design."""
        logger.info(f"Analyzing API in {self.project_path}")

        # Find OpenAPI spec
        spec_file, spec_data = await self._find_openapi_spec()

        if spec_data:
            return await self._analyze_openapi(spec_file, spec_data)
        else:
            # Try to extract from code
            return await self._analyze_from_code()

    async def _find_openapi_spec(self) -> tuple[str | None, dict | None]:
        """Find and load OpenAPI specification."""
        spec_patterns = [
            "openapi.yaml",
            "openapi.yml",
            "openapi.json",
            "swagger.yaml",
            "swagger.yml",
            "swagger.json",
            "api.yaml",
            "api.yml",
            "api.json",
            "docs/openapi.yaml",
            "docs/api.yaml",
        ]

        for pattern in spec_patterns:
            spec_path = self.project_path / pattern
            if spec_path.exists():
                content = spec_path.read_text(errors="ignore")
                try:
                    if pattern.endswith(".json"):
                        return str(spec_path.relative_to(self.project_path)), json.loads(content)
                    else:
                        # Simple YAML parsing (basic)
                        import yaml

                        return str(spec_path.relative_to(self.project_path)), yaml.safe_load(
                            content
                        )
                except Exception:
                    try:
                        return str(spec_path.relative_to(self.project_path)), json.loads(content)
                    except Exception:
                        pass

        return None, None

    async def _analyze_openapi(self, spec_file: str, spec: dict) -> APIReport:
        """Analyze OpenAPI specification."""
        endpoints = []
        issues = []

        # Extract API info
        api_version = spec.get("openapi", spec.get("swagger", "unknown"))
        spec.get("info", {})
        base_url = ""
        if "servers" in spec:
            base_url = spec["servers"][0].get("url", "") if spec["servers"] else ""

        # Extract endpoints
        paths = spec.get("paths", {})
        for path, methods in paths.items():
            for method, details in methods.items():
                if method in ["get", "post", "put", "patch", "delete", "options", "head"]:
                    endpoints.append(
                        APIEndpoint(
                            method=method.upper(),
                            path=path,
                            summary=details.get("summary"),
                            parameters=details.get("parameters", []),
                            request_body=details.get("requestBody"),
                            responses=details.get("responses", {}),
                            tags=details.get("tags", []),
                        )
                    )

        # Validate endpoints
        for endpoint in endpoints:
            issues.extend(self._validate_endpoint(endpoint))

        # Check global issues
        issues.extend(self._check_global_issues(spec, endpoints))

        # Calculate score
        score = self._calculate_score(issues, len(endpoints))

        # Generate recommendations
        recommendations = self._generate_recommendations(issues, endpoints, spec)

        return APIReport(
            project_path=str(self.project_path),
            spec_file=spec_file,
            api_version=api_version,
            base_url=base_url,
            endpoints=endpoints,
            issues=issues,
            score=score,
            recommendations=recommendations,
        )

    async def _analyze_from_code(self) -> APIReport:
        """Analyze API from source code."""
        endpoints = []
        issues = []

        # Look for route definitions in common frameworks
        patterns = {
            "fastapi": [
                r'@app\.(?:get|post|put|patch|delete)\([\'"]([^\'"]+)[\'"]',
                r'@router\.(?:get|post|put|patch|delete)\([\'"]([^\'"]+)[\'"]',
            ],
            "flask": [
                r'@app\.route\([\'"]([^\'"]+)[\'"].*methods=\[([^\]]+)\]',
                r'@bp\.route\([\'"]([^\'"]+)[\'"]',
            ],
            "express": [
                r'app\.(?:get|post|put|patch|delete)\([\'"]([^\'"]+)[\'"]',
                r'router\.(?:get|post|put|patch|delete)\([\'"]([^\'"]+)[\'"]',
            ],
        }

        for file_path in self.project_path.glob("**/*.py"):
            if any(skip in str(file_path) for skip in ["node_modules", "venv", ".git"]):
                continue

            content = file_path.read_text(errors="ignore")

            # FastAPI patterns
            for pattern in patterns["fastapi"]:
                for match in re.finditer(pattern, content):
                    method_match = re.search(r"\.(get|post|put|patch|delete)", match.group(0))
                    method = method_match.group(1).upper() if method_match else "GET"
                    endpoints.append(APIEndpoint(method=method, path=match.group(1), summary=None))

        for file_path in self.project_path.glob("**/*.{js,ts}"):
            if any(skip in str(file_path) for skip in ["node_modules", "dist", ".git"]):
                continue

            content = file_path.read_text(errors="ignore")

            # Express patterns
            for pattern in patterns["express"]:
                for match in re.finditer(pattern, content):
                    method_match = re.search(r"\.(get|post|put|patch|delete)", match.group(0))
                    method = method_match.group(1).upper() if method_match else "GET"
                    endpoints.append(APIEndpoint(method=method, path=match.group(1), summary=None))

        # Validate endpoints
        for endpoint in endpoints:
            issues.extend(self._validate_endpoint(endpoint))

        score = self._calculate_score(issues, len(endpoints))

        recommendations = []
        if endpoints and not await self._find_openapi_spec()[0]:
            recommendations.append("Create OpenAPI specification for better documentation")

        return APIReport(
            project_path=str(self.project_path),
            spec_file=None,
            api_version="detected-from-code",
            endpoints=endpoints,
            issues=issues,
            score=score,
            recommendations=recommendations,
        )

    def _validate_endpoint(self, endpoint: APIEndpoint) -> list[APIIssue]:
        """Validate a single endpoint."""
        issues = []
        path = endpoint.path

        # Check for verbs in path
        for pattern in self.VERB_PATTERNS:
            if re.search(pattern, path):
                issues.append(
                    APIIssue(
                        severity="high",
                        endpoint=f"{endpoint.method} {path}",
                        rule="no-verbs-in-path",
                        description="Path contains verb - use HTTP method instead",
                        suggestion=f"Remove verb from path, use {endpoint.method} method semantics",
                    )
                )
                break

        # Check naming consistency
        if "_" in path and "-" in path:
            issues.append(
                APIIssue(
                    severity="medium",
                    endpoint=f"{endpoint.method} {path}",
                    rule="consistent-naming",
                    description="Mixed naming conventions (both _ and -)",
                    suggestion="Use either kebab-case or snake_case consistently",
                )
            )

        # Check for proper responses
        if endpoint.responses:
            # POST should return 201
            if endpoint.method == "POST" and "201" not in endpoint.responses:
                issues.append(
                    APIIssue(
                        severity="medium",
                        endpoint=f"{endpoint.method} {path}",
                        rule="proper-status-codes",
                        description="POST endpoint should return 201 Created",
                        suggestion="Add 201 response for successful creation",
                    )
                )

            # DELETE should return 204 or 200
            if endpoint.method == "DELETE" and not any(
                c in endpoint.responses for c in ["200", "204"]
            ):
                issues.append(
                    APIIssue(
                        severity="low",
                        endpoint=f"{endpoint.method} {path}",
                        rule="proper-status-codes",
                        description="DELETE should return 200 or 204",
                        suggestion="Add appropriate success response",
                    )
                )

        return issues

    def _check_global_issues(self, spec: dict, endpoints: list) -> list[APIIssue]:
        """Check global API issues."""
        issues = []

        # Check security
        if (
            "securityDefinitions" not in spec
            and "components" not in spec
            or "components" in spec
            and "securitySchemes" not in spec.get("components", {})
        ):
            issues.append(
                APIIssue(
                    severity="critical",
                    endpoint=None,
                    rule="security-defined",
                    description="No security schemes defined",
                    suggestion="Add OAuth2, API Key, or JWT security definition",
                )
            )

        # Check versioning
        base_paths = set()
        for ep in endpoints:
            parts = ep.path.split("/")
            if len(parts) > 1:
                base_paths.add(parts[1])

        if not any(re.match(r"v\d+", bp) for bp in base_paths):
            issues.append(
                APIIssue(
                    severity="low",
                    endpoint=None,
                    rule="version-in-path",
                    description="No API version in path",
                    suggestion="Consider adding version prefix (e.g., /v1/)",
                )
            )

        return issues

    def _calculate_score(self, issues: list, endpoint_count: int) -> int:
        """Calculate API design score."""
        if endpoint_count == 0:
            return 50

        score = 100
        penalties = {"critical": 15, "high": 8, "medium": 4, "low": 2}

        for issue in issues:
            score -= penalties.get(issue.severity, 0)

        return max(0, score)

    def _generate_recommendations(self, issues: list, endpoints: list, spec: dict) -> list[str]:
        """Generate recommendations."""
        recommendations = []

        issue_rules = {i.rule for i in issues}

        if "security-defined" in issue_rules:
            recommendations.append("Define security schemes (OAuth2, API Key, or Bearer)")

        if "no-verbs-in-path" in issue_rules:
            recommendations.append("Refactor paths to remove verbs - use HTTP methods instead")

        if len(endpoints) > 20 and not any(ep.tags for ep in endpoints):
            recommendations.append("Add tags to organize endpoints into logical groups")

        if not spec.get("info", {}).get("description"):
            recommendations.append("Add API description for better documentation")

        return recommendations[:5]


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="API Designer Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = APIDesigner(args.path)
    report = await agent.analyze()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
