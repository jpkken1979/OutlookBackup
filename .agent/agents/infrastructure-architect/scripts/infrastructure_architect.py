#!/usr/bin/env python3
"""
Infrastructure Architect Agent - IaC and cloud infrastructure analysis.

Usage:
    python infrastructure_architect.py <project_path> [--json]
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
class InfraIssue:
    """Infrastructure issue."""

    id: str
    category: str  # security, cost, reliability, performance
    severity: str
    title: str
    location: str
    description: str
    fix: str


@dataclass
class InfraReport:
    """Infrastructure analysis report."""

    project_path: str
    timestamp: str
    iac_tool: str
    cloud_provider: str
    issues: list = field(default_factory=list)
    resources: dict = field(default_factory=dict)
    recommendations: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class InfrastructureArchitect:
    """Infrastructure as Code analysis agent."""

    TERRAFORM_ISSUES = {
        "no_encryption": {
            "pattern": r'resource\s+"aws_s3_bucket"[^}]+(?!encryption)',
            "title": "S3 bucket without encryption",
            "severity": "high",
            "fix": "Add aws_s3_bucket_server_side_encryption_configuration",
        },
        "public_bucket": {
            "pattern": r'acl\s*=\s*"public',
            "title": "Public S3 bucket ACL",
            "severity": "critical",
            "fix": "Use private ACL unless public access is explicitly required",
        },
        "hardcoded_secret": {
            "pattern": r'(password|secret|key)\s*=\s*"[^"]+"',
            "title": "Hardcoded secret in Terraform",
            "severity": "critical",
            "fix": "Use AWS Secrets Manager or environment variables",
        },
        "no_tags": {
            "pattern": r'resource\s+"aws_\w+"[^}]+(?!tags\s*=)',
            "title": "Resource without tags",
            "severity": "low",
            "fix": "Add required tags for cost allocation and ownership",
        },
        "unpinned_provider": {
            "pattern": r'version\s*=\s*">=|version\s*=\s*"~>',
            "title": "Unpinned provider version",
            "severity": "medium",
            "fix": "Pin to exact provider version for reproducibility",
        },
        "default_vpc": {
            "pattern": r'vpc_id\s*=\s*"vpc-\w+"',
            "title": "Hardcoded VPC ID",
            "severity": "medium",
            "fix": "Use data sources or variables for VPC references",
        },
    }

    K8S_ISSUES = {
        "no_resource_limits": {
            "pattern": r"containers:[^}]+(?!resources:)",
            "title": "Container without resource limits",
            "severity": "high",
            "fix": "Add resources.limits and resources.requests",
        },
        "privileged_container": {
            "pattern": r"privileged:\s*true",
            "title": "Privileged container",
            "severity": "critical",
            "fix": "Remove privileged: true unless absolutely necessary",
        },
        "run_as_root": {
            "pattern": r"runAsUser:\s*0|runAsNonRoot:\s*false",
            "title": "Container running as root",
            "severity": "high",
            "fix": "Set runAsNonRoot: true and runAsUser to non-zero",
        },
        "latest_tag": {
            "pattern": r"image:\s*[\w/]+:latest",
            "title": "Using :latest image tag",
            "severity": "medium",
            "fix": "Pin to specific image version for reproducibility",
        },
        "no_liveness_probe": {
            "pattern": r"containers:[^}]+(?!livenessProbe:)",
            "title": "Missing liveness probe",
            "severity": "medium",
            "fix": "Add livenessProbe for container health monitoring",
        },
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.issue_counter = 0

    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        self.issue_counter += 1
        return f"INFRA-{self.issue_counter:03d}"

    def _detect_iac_tool(self) -> str:
        """Detect IaC tool from project files."""
        if list(self.project_path.rglob("*.tf")):
            return "terraform"
        if list(self.project_path.rglob("Pulumi.yaml")):
            return "pulumi"
        if list(self.project_path.rglob("*.template.yaml")) or list(
            self.project_path.rglob("*.template.json")
        ):
            return "cloudformation"
        if list(self.project_path.rglob("cdk.json")):
            return "cdk"
        return "unknown"

    def _detect_cloud_provider(self) -> str:
        """Detect cloud provider from IaC files."""
        all_content = ""
        for ext in ["*.tf", "*.yaml", "*.yml", "*.json"]:
            for file_path in self.project_path.rglob(ext):
                with contextlib.suppress(Exception):
                    all_content += file_path.read_text()

        if "aws_" in all_content or "AWS::" in all_content:
            return "aws"
        if "google_" in all_content or "gcp" in all_content.lower():
            return "gcp"
        if "azurerm_" in all_content or "Azure" in all_content:
            return "azure"

        return "unknown"

    def _count_resources(self) -> dict:
        """Count infrastructure resources."""
        resources = {
            "terraform_resources": 0,
            "kubernetes_deployments": 0,
            "kubernetes_services": 0,
            "helm_charts": 0,
        }

        # Count Terraform resources
        for tf_file in self.project_path.rglob("*.tf"):
            try:
                content = tf_file.read_text()
                resources["terraform_resources"] += len(re.findall(r'resource\s+"', content))
            except Exception:
                pass

        # Count Kubernetes resources
        for k8s_file in self.project_path.rglob("*.yaml"):
            try:
                content = k8s_file.read_text()
                resources["kubernetes_deployments"] += len(
                    re.findall(r"kind:\s*Deployment", content)
                )
                resources["kubernetes_services"] += len(re.findall(r"kind:\s*Service", content))
            except Exception:
                pass

        # Count Helm charts
        resources["helm_charts"] = len(list(self.project_path.rglob("Chart.yaml")))

        return resources

    def analyze_terraform(self) -> list[InfraIssue]:
        """Analyze Terraform files."""
        issues = []

        for tf_file in self.project_path.rglob("*.tf"):
            try:
                content = tf_file.read_text()
                relative_path = str(tf_file.relative_to(self.project_path))

                # Check for hardcoded secrets
                if re.search(r'(password|secret|api_key)\s*=\s*"[^"]+"', content, re.IGNORECASE):
                    issues.append(
                        InfraIssue(
                            id=self._generate_issue_id(),
                            category="security",
                            severity="critical",
                            title="Hardcoded secret in Terraform",
                            location=relative_path,
                            description="Sensitive values should not be in code.",
                            fix="Use AWS Secrets Manager, Vault, or environment variables",
                        )
                    )

                # Check for public S3
                if re.search(r'acl\s*=\s*"public', content):
                    issues.append(
                        InfraIssue(
                            id=self._generate_issue_id(),
                            category="security",
                            severity="critical",
                            title="Public S3 bucket",
                            location=relative_path,
                            description="S3 bucket with public ACL detected.",
                            fix="Use private ACL and specific bucket policies",
                        )
                    )

                # Check for missing encryption
                if "aws_s3_bucket" in content and "encryption" not in content:
                    issues.append(
                        InfraIssue(
                            id=self._generate_issue_id(),
                            category="security",
                            severity="high",
                            title="S3 bucket without encryption",
                            location=relative_path,
                            description="S3 bucket may not have encryption enabled.",
                            fix="Add server-side encryption configuration",
                        )
                    )

                # Check for unpinned versions
                if re.search(r'version\s*=\s*"[~>]=', content):
                    issues.append(
                        InfraIssue(
                            id=self._generate_issue_id(),
                            category="reliability",
                            severity="medium",
                            title="Unpinned provider version",
                            location=relative_path,
                            description="Provider version not pinned exactly.",
                            fix="Pin to exact version for reproducibility",
                        )
                    )

            except Exception as e:
                logger.debug(f"Error analyzing {tf_file}: {e}")

        return issues

    def analyze_kubernetes(self) -> list[InfraIssue]:
        """Analyze Kubernetes manifests."""
        issues = []

        for k8s_file in self.project_path.rglob("*.yaml"):
            if ".github" in str(k8s_file) or "node_modules" in str(k8s_file):
                continue

            try:
                content = k8s_file.read_text()

                if "kind:" not in content:
                    continue

                relative_path = str(k8s_file.relative_to(self.project_path))

                # Check for privileged containers
                if "privileged: true" in content:
                    issues.append(
                        InfraIssue(
                            id=self._generate_issue_id(),
                            category="security",
                            severity="critical",
                            title="Privileged container",
                            location=relative_path,
                            description="Container running in privileged mode.",
                            fix="Remove privileged: true",
                        )
                    )

                # Check for :latest tag
                if re.search(r"image:\s*[\w/]+:latest", content):
                    issues.append(
                        InfraIssue(
                            id=self._generate_issue_id(),
                            category="reliability",
                            severity="medium",
                            title="Using :latest image tag",
                            location=relative_path,
                            description=":latest tag is unpredictable.",
                            fix="Pin to specific image version",
                        )
                    )

                # Check for missing resource limits
                if "Deployment" in content or "Pod" in content:
                    if "resources:" not in content:
                        issues.append(
                            InfraIssue(
                                id=self._generate_issue_id(),
                                category="reliability",
                                severity="high",
                                title="Missing resource limits",
                                location=relative_path,
                                description="Container without resource limits.",
                                fix="Add resources.requests and resources.limits",
                            )
                        )

            except Exception as e:
                logger.debug(f"Error analyzing {k8s_file}: {e}")

        return issues

    def generate_report(self) -> InfraReport:
        """Generate comprehensive infrastructure report."""
        logger.info(f"Analyzing infrastructure: {self.project_path}")

        iac_tool = self._detect_iac_tool()
        cloud_provider = self._detect_cloud_provider()
        resources = self._count_resources()

        issues = []
        if iac_tool == "terraform":
            issues.extend(self.analyze_terraform())
        issues.extend(self.analyze_kubernetes())

        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        # Generate recommendations
        recommendations = []

        if severity_counts["critical"] > 0:
            recommendations.append("Fix critical security issues immediately")

        if iac_tool == "terraform":
            recommendations.extend(
                [
                    "Use terraform-docs for documentation",
                    "Implement tfsec for security scanning",
                    "Use remote state with locking",
                ]
            )

        if resources["kubernetes_deployments"] > 0:
            recommendations.extend(
                [
                    "Implement Pod Security Standards",
                    "Use Network Policies for isolation",
                    "Set up HPA for auto-scaling",
                ]
            )

        return InfraReport(
            project_path=str(self.project_path),
            timestamp=datetime.now().isoformat(),
            iac_tool=iac_tool,
            cloud_provider=cloud_provider,
            issues=[asdict(i) for i in issues],
            resources=resources,
            recommendations=recommendations,
            summary={
                "total_issues": len(issues),
                "by_severity": severity_counts,
                "iac_tool": iac_tool,
                "cloud_provider": cloud_provider,
            },
        )


def format_report_markdown(report: InfraReport) -> str:
    """Format report as markdown."""
    lines = [
        "# Infrastructure Analysis Report",
        "",
        f"**Project:** {report.project_path}",
        f"**IaC Tool:** {report.iac_tool}",
        f"**Cloud Provider:** {report.cloud_provider}",
        f"**Date:** {report.timestamp}",
        "",
        "## Resources",
        "",
    ]

    for resource, count in report.resources.items():
        if count > 0:
            lines.append(f"- **{resource.replace('_', ' ').title()}:** {count}")

    lines.extend(["", "## Issues by Severity", ""])

    for severity, count in report.summary.get("by_severity", {}).items():
        if count > 0:
            emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}.get(
                severity, "⚪"
            )
            lines.append(f"- {emoji} {severity.upper()}: {count}")

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
                f"**Location:** `{issue.get('location', '')}`",
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
    parser = argparse.ArgumentParser(description="Infrastructure Architect Agent")
    parser.add_argument("project", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    architect = InfrastructureArchitect(args.project)
    report = architect.generate_report()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
