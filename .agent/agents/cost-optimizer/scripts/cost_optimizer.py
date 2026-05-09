#!/usr/bin/env python3
"""
Cost Optimizer Agent - Cloud cost analysis and optimization.

Usage:
    python cost_optimizer.py <project_path> [--json]
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
class CostIssue:
    """Cost optimization opportunity."""

    id: str
    category: str  # compute, storage, network, licensing
    severity: str
    title: str
    location: str
    current_state: str
    recommendation: str
    estimated_savings: str


@dataclass
class CostReport:
    """Cost analysis report."""

    project_path: str
    timestamp: str
    cloud_provider: str
    issues: list = field(default_factory=list)
    resource_summary: dict = field(default_factory=dict)
    optimization_potential: dict = field(default_factory=dict)
    recommendations: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class CostOptimizer:
    """Cloud cost optimization agent."""

    # Instance type recommendations
    INSTANCE_OPTIMIZATIONS = {
        "t2.": {"suggestion": "t3.", "savings": "10-15%"},
        "m4.": {"suggestion": "m5.", "savings": "10-20%"},
        "m5.": {"suggestion": "m6i.", "savings": "5-10%"},
        "c4.": {"suggestion": "c5.", "savings": "15-20%"},
        "r4.": {"suggestion": "r5.", "savings": "10-15%"},
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.issue_counter = 0

    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        self.issue_counter += 1
        return f"COST-{self.issue_counter:03d}"

    def _detect_cloud_provider(self) -> str:
        """Detect cloud provider."""
        all_content = ""
        for ext in ["*.tf", "*.yaml", "*.yml"]:
            for file_path in self.project_path.rglob(ext):
                with contextlib.suppress(Exception):
                    all_content += file_path.read_text()

        if "aws_" in all_content or "AWS::" in all_content:
            return "aws"
        if "google_" in all_content:
            return "gcp"
        if "azurerm_" in all_content:
            return "azure"
        return "unknown"

    def analyze_compute(self) -> list[CostIssue]:
        """Analyze compute resources for cost optimization."""
        issues = []

        for tf_file in self.project_path.rglob("*.tf"):
            try:
                content = tf_file.read_text()
                relative_path = str(tf_file.relative_to(self.project_path))

                # Check for older instance types
                for old_type, optimization in self.INSTANCE_OPTIMIZATIONS.items():
                    if old_type in content:
                        issues.append(
                            CostIssue(
                                id=self._generate_issue_id(),
                                category="compute",
                                severity="medium",
                                title=f"Older instance generation ({old_type}*)",
                                location=relative_path,
                                current_state=f"Using {old_type}* instances",
                                recommendation=f"Migrate to {optimization['suggestion']}* instances",
                                estimated_savings=optimization["savings"],
                            )
                        )

                # Check for on-demand without spot option
                if "instance_type" in content and "spot" not in content.lower():
                    issues.append(
                        CostIssue(
                            id=self._generate_issue_id(),
                            category="compute",
                            severity="high",
                            title="Consider spot/preemptible instances",
                            location=relative_path,
                            current_state="Using on-demand instances",
                            recommendation="Use spot instances for fault-tolerant workloads",
                            estimated_savings="60-90%",
                        )
                    )

                # Check for missing auto-scaling
                if "aws_instance" in content and "aws_autoscaling" not in content:
                    issues.append(
                        CostIssue(
                            id=self._generate_issue_id(),
                            category="compute",
                            severity="medium",
                            title="Consider auto-scaling",
                            location=relative_path,
                            current_state="Fixed instance count",
                            recommendation="Implement auto-scaling for variable workloads",
                            estimated_savings="20-40%",
                        )
                    )

            except Exception as e:
                logger.debug(f"Error analyzing {tf_file}: {e}")

        return issues

    def analyze_storage(self) -> list[CostIssue]:
        """Analyze storage for cost optimization."""
        issues = []

        for tf_file in self.project_path.rglob("*.tf"):
            try:
                content = tf_file.read_text()
                relative_path = str(tf_file.relative_to(self.project_path))

                # Check for gp2 volumes (should use gp3)
                if "gp2" in content:
                    issues.append(
                        CostIssue(
                            id=self._generate_issue_id(),
                            category="storage",
                            severity="medium",
                            title="Using gp2 EBS volumes",
                            location=relative_path,
                            current_state="gp2 volume type",
                            recommendation="Migrate to gp3 volumes (cheaper, better performance)",
                            estimated_savings="20%",
                        )
                    )

                # Check for S3 without lifecycle rules
                if "aws_s3_bucket" in content and "lifecycle_rule" not in content:
                    issues.append(
                        CostIssue(
                            id=self._generate_issue_id(),
                            category="storage",
                            severity="medium",
                            title="S3 bucket without lifecycle policy",
                            location=relative_path,
                            current_state="No lifecycle rules configured",
                            recommendation="Add lifecycle rules to transition to cheaper storage classes",
                            estimated_savings="50-70%",
                        )
                    )

                # Check for provisioned IOPS when might not be needed
                if "io1" in content or "io2" in content:
                    issues.append(
                        CostIssue(
                            id=self._generate_issue_id(),
                            category="storage",
                            severity="low",
                            title="Provisioned IOPS volumes",
                            location=relative_path,
                            current_state="Using io1/io2 provisioned IOPS",
                            recommendation="Verify IOPS requirements; gp3 may be sufficient",
                            estimated_savings="Variable",
                        )
                    )

            except Exception as e:
                logger.debug(f"Error analyzing {tf_file}: {e}")

        return issues

    def analyze_networking(self) -> list[CostIssue]:
        """Analyze networking for cost optimization."""
        issues = []

        for tf_file in self.project_path.rglob("*.tf"):
            try:
                content = tf_file.read_text()
                relative_path = str(tf_file.relative_to(self.project_path))

                # Check for NAT Gateway (expensive)
                if "aws_nat_gateway" in content:
                    nat_count = content.count("aws_nat_gateway")
                    if nat_count > 1:
                        issues.append(
                            CostIssue(
                                id=self._generate_issue_id(),
                                category="network",
                                severity="high",
                                title=f"Multiple NAT Gateways ({nat_count})",
                                location=relative_path,
                                current_state=f"{nat_count} NAT Gateways",
                                recommendation="Consolidate NAT Gateways or use NAT instances",
                                estimated_savings="$32-100/month per gateway",
                            )
                        )

                # Check for data transfer between regions
                if re.search(r"(us-east|us-west|eu-west|ap-)", content):
                    regions = set(
                        re.findall(r"(us-east-\d|us-west-\d|eu-west-\d|ap-\w+-\d)", content)
                    )
                    if len(regions) > 1:
                        issues.append(
                            CostIssue(
                                id=self._generate_issue_id(),
                                category="network",
                                severity="medium",
                                title="Multi-region deployment",
                                location=relative_path,
                                current_state=f"Resources in {len(regions)} regions",
                                recommendation="Minimize cross-region data transfer",
                                estimated_savings="$0.02/GB transfer",
                            )
                        )

            except Exception as e:
                logger.debug(f"Error analyzing {tf_file}: {e}")

        return issues

    def analyze_kubernetes(self) -> list[CostIssue]:
        """Analyze Kubernetes resources for cost optimization."""
        issues = []

        for k8s_file in self.project_path.rglob("*.yaml"):
            try:
                content = k8s_file.read_text()
                if "kind:" not in content:
                    continue

                relative_path = str(k8s_file.relative_to(self.project_path))

                # Check for over-provisioned resources
                cpu_requests = re.findall(r'cpu:\s*["\']?(\d+)m?["\']?', content)
                for cpu in cpu_requests:
                    if int(cpu) > 1000:
                        issues.append(
                            CostIssue(
                                id=self._generate_issue_id(),
                                category="compute",
                                severity="low",
                                title="High CPU request",
                                location=relative_path,
                                current_state=f"CPU request: {cpu}m",
                                recommendation="Verify if high CPU allocation is justified",
                                estimated_savings="Variable",
                            )
                        )

                # Check for missing HPA
                if "Deployment" in content and "HorizontalPodAutoscaler" not in content:
                    issues.append(
                        CostIssue(
                            id=self._generate_issue_id(),
                            category="compute",
                            severity="medium",
                            title="Deployment without HPA",
                            location=relative_path,
                            current_state="Fixed replica count",
                            recommendation="Add HorizontalPodAutoscaler for dynamic scaling",
                            estimated_savings="20-40%",
                        )
                    )

            except Exception as e:
                logger.debug(f"Error analyzing {k8s_file}: {e}")

        return issues

    def generate_report(self) -> CostReport:
        """Generate comprehensive cost optimization report."""
        logger.info(f"Analyzing costs: {self.project_path}")

        cloud_provider = self._detect_cloud_provider()

        issues = []
        issues.extend(self.analyze_compute())
        issues.extend(self.analyze_storage())
        issues.extend(self.analyze_networking())
        issues.extend(self.analyze_kubernetes())

        # Count by category
        category_counts = {}
        for issue in issues:
            category_counts[issue.category] = category_counts.get(issue.category, 0) + 1

        # Generate recommendations
        recommendations = [
            "Review and implement Reserved Instances or Savings Plans",
            "Set up AWS Cost Explorer budgets and alerts",
            "Implement tagging strategy for cost allocation",
            "Schedule non-production resources to shut down outside business hours",
            "Use Spot instances for fault-tolerant workloads",
        ]

        # Calculate optimization potential
        optimization_potential = {
            "quick_wins": len([i for i in issues if i.severity == "low"]),
            "medium_effort": len([i for i in issues if i.severity == "medium"]),
            "requires_planning": len([i for i in issues if i.severity == "high"]),
        }

        return CostReport(
            project_path=str(self.project_path),
            timestamp=datetime.now().isoformat(),
            cloud_provider=cloud_provider,
            issues=[asdict(i) for i in issues],
            resource_summary=category_counts,
            optimization_potential=optimization_potential,
            recommendations=recommendations,
            summary={
                "total_opportunities": len(issues),
                "by_category": category_counts,
                "cloud_provider": cloud_provider,
            },
        )


def format_report_markdown(report: CostReport) -> str:
    """Format report as markdown."""
    lines = [
        "# Cost Optimization Report",
        "",
        f"**Project:** {report.project_path}",
        f"**Cloud Provider:** {report.cloud_provider}",
        f"**Date:** {report.timestamp}",
        "",
        "## Optimization Summary",
        "",
        f"**Total Opportunities:** {report.summary.get('total_opportunities', 0)}",
        "",
        "### By Category",
        "",
    ]

    for category, count in report.summary.get("by_category", {}).items():
        lines.append(f"- **{category.title()}:** {count}")

    lines.extend(["", "## Optimization Opportunities", ""])

    for issue in report.issues:
        severity_emoji = {"high": "💰💰💰", "medium": "💰💰", "low": "💰"}.get(
            issue.get("severity", ""), "💰"
        )
        lines.extend(
            [
                f"### {severity_emoji} {issue.get('id', '')}: {issue.get('title', '')}",
                "",
                f"**Category:** {issue.get('category', '')}",
                f"**Location:** `{issue.get('location', '')}`",
                f"**Estimated Savings:** {issue.get('estimated_savings', '')}",
                "",
                f"**Current State:** {issue.get('current_state', '')}",
                "",
                f"**Recommendation:** {issue.get('recommendation', '')}",
                "",
                "---",
                "",
            ]
        )

    lines.extend(["", "## General Recommendations", ""])
    for i, rec in enumerate(report.recommendations, 1):
        lines.append(f"{i}. {rec}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Cost Optimizer Agent")
    parser.add_argument("project", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    optimizer = CostOptimizer(args.project)
    report = optimizer.generate_report()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
