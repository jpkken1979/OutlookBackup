#!/usr/bin/env python3
"""
Data Engineer Agent - Data pipeline and ETL analysis.

Usage:
    python data_engineer.py <project_path> [--json]
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
class DataIssue:
    """Data engineering issue."""

    id: str
    category: str  # pipeline, quality, performance, architecture
    severity: str
    title: str
    location: str
    description: str
    fix: str


@dataclass
class DataReport:
    """Data engineering analysis report."""

    project_path: str
    timestamp: str
    stack: dict = field(default_factory=dict)
    issues: list = field(default_factory=list)
    data_sources: list = field(default_factory=list)
    recommendations: list = field(default_factory=list)
    summary: dict = field(default_factory=dict)


class DataEngineer:
    """Data engineering analysis agent."""

    DATA_ANTI_PATTERNS = {
        "full_table_reload": {
            "pattern": r"TRUNCATE|DELETE FROM \w+ WHERE 1=1|DROP TABLE",
            "title": "Full table reload detected",
            "description": "Truncating and reloading full tables is inefficient.",
            "severity": "medium",
            "fix": "Implement incremental loading or CDC (Change Data Capture)",
        },
        "no_idempotency": {
            "pattern": r"INSERT INTO(?!.*ON CONFLICT)(?!.*ON DUPLICATE)",
            "anti_pattern": r"MERGE|UPSERT|ON CONFLICT|ON DUPLICATE",
            "title": "Non-idempotent insert",
            "description": "Inserts without conflict handling can cause duplicates.",
            "severity": "high",
            "fix": "Use MERGE, UPSERT, or INSERT ON CONFLICT",
        },
        "missing_data_validation": {
            "keywords": ["read_csv", "read_json", "pd.read", "spark.read"],
            "anti_keywords": ["validate", "expect", "assert", "schema"],
            "title": "No data validation",
            "description": "Data is read without validation.",
            "severity": "high",
            "fix": "Add Great Expectations or Pydantic validation",
        },
        "hardcoded_credentials": {
            "pattern": r'(password|secret|api_key)\s*=\s*["\'][^"\']+["\']',
            "title": "Hardcoded credentials",
            "description": "Credentials should not be in code.",
            "severity": "critical",
            "fix": "Use environment variables or secrets manager",
        },
    }

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.issue_counter = 0

    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        self.issue_counter += 1
        return f"DATA-{self.issue_counter:03d}"

    def _detect_stack(self) -> dict:
        """Detect data engineering stack."""
        stack = {
            "orchestration": None,
            "transformation": [],
            "storage": [],
            "streaming": None,
            "quality": None,
        }

        indicators = {
            "airflow": ["airflow", "DAG", "from airflow"],
            "prefect": ["prefect", "from prefect", "@flow"],
            "dagster": ["dagster", "from dagster", "@asset"],
            "dbt": ["dbt_project.yml", "{{ ref(", "{{ source("],
            "spark": ["pyspark", "SparkSession", "spark.read"],
            "pandas": ["import pandas", "pd.read"],
            "kafka": ["kafka", "KafkaProducer", "KafkaConsumer"],
            "great_expectations": ["great_expectations", "expect_"],
            "delta": ["delta", "DeltaTable"],
            "snowflake": ["snowflake", "SNOWFLAKE"],
            "bigquery": ["bigquery", "BigQuery", "bq."],
            "redshift": ["redshift", "REDSHIFT"],
            "s3": ["s3://", "boto3", "S3"],
            "postgres": ["psycopg2", "postgres", "postgresql"],
        }

        all_content = ""
        for ext in ["*.py", "*.sql", "*.yml", "*.yaml"]:
            for file_path in self.project_path.rglob(ext):
                with contextlib.suppress(Exception):
                    all_content += file_path.read_text()

        # Detect orchestration
        for tool in ["airflow", "prefect", "dagster"]:
            if any(ind in all_content for ind in indicators[tool]):
                stack["orchestration"] = tool
                break

        # Detect transformation
        for tool in ["dbt", "spark", "pandas"]:
            if any(ind in all_content for ind in indicators[tool]):
                stack["transformation"].append(tool)

        # Detect storage
        for tool in ["delta", "snowflake", "bigquery", "redshift", "s3", "postgres"]:
            if any(ind in all_content for ind in indicators[tool]):
                stack["storage"].append(tool)

        # Detect streaming
        if any(ind in all_content for ind in indicators["kafka"]):
            stack["streaming"] = "kafka"

        # Detect quality
        if any(ind in all_content for ind in indicators["great_expectations"]):
            stack["quality"] = "great_expectations"

        return stack

    def _detect_data_sources(self) -> list[str]:
        """Detect data sources in the project."""
        sources = []

        source_patterns = {
            "CSV files": r"\.(csv|CSV)",
            "JSON files": r"\.(json|JSON)",
            "Parquet files": r"\.(parquet|PARQUET)",
            "Database tables": r"(FROM|JOIN)\s+\w+\.\w+",
            "API endpoints": r'https?://[^\s\'"]+/api',
            "S3 buckets": r"s3://[\w\-]+",
            "GCS buckets": r"gs://[\w\-]+",
        }

        all_content = ""
        for ext in ["*.py", "*.sql"]:
            for file_path in self.project_path.rglob(ext):
                with contextlib.suppress(Exception):
                    all_content += file_path.read_text()

        for source_type, pattern in source_patterns.items():
            if re.search(pattern, all_content):
                sources.append(source_type)

        return sources

    def analyze_code(self) -> list[DataIssue]:
        """Analyze code for data engineering issues."""
        issues = []

        for file_path in self.project_path.rglob("*.py"):
            if any(skip in str(file_path) for skip in ["venv", ".git", "__pycache__"]):
                continue

            try:
                content = file_path.read_text()

                # Check for hardcoded credentials
                if re.search(
                    r'(password|secret|api_key)\s*=\s*["\'][^"\']+["\']', content, re.IGNORECASE
                ):
                    issues.append(
                        DataIssue(
                            id=self._generate_issue_id(),
                            category="security",
                            severity="critical",
                            title="Hardcoded credentials",
                            location=str(file_path),
                            description="Credentials in source code.",
                            fix="Use environment variables or secrets manager",
                        )
                    )

                # Check for data validation
                has_read = any(
                    r in content for r in ["read_csv", "read_json", "pd.read", "spark.read"]
                )
                has_validation = any(
                    v in content for v in ["validate", "expect", "assert", "schema"]
                )

                if has_read and not has_validation:
                    issues.append(
                        DataIssue(
                            id=self._generate_issue_id(),
                            category="quality",
                            severity="high",
                            title="No data validation",
                            location=str(file_path),
                            description="Data is loaded without validation.",
                            fix="Add Great Expectations or schema validation",
                        )
                    )

                # Check for error handling
                if "try:" not in content and ("read" in content or "write" in content):
                    issues.append(
                        DataIssue(
                            id=self._generate_issue_id(),
                            category="pipeline",
                            severity="medium",
                            title="Missing error handling",
                            location=str(file_path),
                            description="I/O operations without try/except.",
                            fix="Add proper error handling and logging",
                        )
                    )

            except Exception as e:
                logger.debug(f"Error analyzing {file_path}: {e}")

        # Check SQL files
        for file_path in self.project_path.rglob("*.sql"):
            try:
                content = file_path.read_text().upper()

                if "TRUNCATE" in content or "DELETE FROM" in content:
                    if "WHERE" not in content or "1=1" in content:
                        issues.append(
                            DataIssue(
                                id=self._generate_issue_id(),
                                category="performance",
                                severity="medium",
                                title="Full table delete/truncate",
                                location=str(file_path),
                                description="Full table operations detected.",
                                fix="Use incremental processing or soft deletes",
                            )
                        )

            except Exception:
                pass

        return issues

    def generate_report(self) -> DataReport:
        """Generate comprehensive data engineering report."""
        logger.info(f"Analyzing data project: {self.project_path}")

        stack = self._detect_stack()
        sources = self._detect_data_sources()
        issues = self.analyze_code()

        # Count by severity
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        # Generate recommendations
        recommendations = []

        if severity_counts["critical"] > 0:
            recommendations.append("Fix critical security issues (credentials) immediately")

        if not stack["orchestration"]:
            recommendations.append(
                "Implement pipeline orchestration (Airflow, Prefect, or Dagster)"
            )

        if not stack["quality"]:
            recommendations.append("Add data quality checks with Great Expectations")

        if "dbt" not in stack["transformation"]:
            recommendations.append("Consider dbt for SQL transformations")

        recommendations.extend(
            [
                "Implement data lineage tracking",
                "Add schema evolution handling",
                "Set up monitoring and alerting for pipeline failures",
            ]
        )

        return DataReport(
            project_path=str(self.project_path),
            timestamp=datetime.now().isoformat(),
            stack=stack,
            issues=[asdict(i) for i in issues],
            data_sources=sources,
            recommendations=recommendations,
            summary={
                "total_issues": len(issues),
                "by_severity": severity_counts,
                "data_sources": len(sources),
                "has_orchestration": stack["orchestration"] is not None,
                "has_quality_checks": stack["quality"] is not None,
            },
        )


def format_report_markdown(report: DataReport) -> str:
    """Format report as markdown."""
    lines = [
        "# Data Engineering Analysis Report",
        "",
        f"**Project:** {report.project_path}",
        f"**Date:** {report.timestamp}",
        "",
        "## Data Stack",
        "",
        f"- **Orchestration:** {report.stack.get('orchestration') or 'Not detected'}",
        f"- **Transformation:** {', '.join(report.stack.get('transformation', [])) or 'Not detected'}",
        f"- **Storage:** {', '.join(report.stack.get('storage', [])) or 'Not detected'}",
        f"- **Quality:** {report.stack.get('quality') or 'Not detected'}",
        "",
        "## Data Sources Detected",
        "",
    ]

    for source in report.data_sources:
        lines.append(f"- {source}")

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
    parser = argparse.ArgumentParser(description="Data Engineer Agent")
    parser.add_argument("project", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    engineer = DataEngineer(args.project)
    report = engineer.generate_report()

    if args.json:
        print(json.dumps(asdict(report), indent=2))
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
