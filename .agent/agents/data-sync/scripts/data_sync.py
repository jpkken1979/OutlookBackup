#!/usr/bin/env python3
"""
Data Sync Agent - Data Transformation & Migration

Capabilities:
- Analyze data sources (CSV, JSON, Excel, SQL)
- Generate transformation mappings
- Validate data integrity
- Create migration scripts
"""

import asyncio
import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class DataSource:
    """Data source information."""

    name: str
    type: str  # csv, json, excel, sql
    path: str
    row_count: int = 0
    columns: list[str] = field(default_factory=list)
    sample: list[dict] = field(default_factory=list)


@dataclass
class DataIssue:
    """Data quality issue."""

    severity: str
    source: str
    column: str | None
    description: str
    suggestion: str
    affected_rows: int = 0


@dataclass
class TransformMapping:
    """Data transformation mapping."""

    source_column: str
    target_column: str
    transform: str  # direct, rename, convert, combine
    details: str = ""


@dataclass
class DataSyncReport:
    """Data sync analysis report."""

    project_path: str
    sources: list[DataSource] = field(default_factory=list)
    issues: list[DataIssue] = field(default_factory=list)
    mappings: list[TransformMapping] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "sources": [s.__dict__ for s in self.sources],
            "issues": [i.__dict__ for i in self.issues],
            "mappings": [m.__dict__ for m in self.mappings],
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Data Sync Report",
            "",
            f"**Project:** {self.project_path}",
            "",
            "## Data Sources",
        ]

        if self.sources:
            lines.extend(
                ["", "| Name | Type | Rows | Columns |", "|------|------|------|---------|"]
            )
            for src in self.sources:
                lines.append(
                    f"| `{src.name}` | {src.type} | {src.row_count} | {len(src.columns)} |"
                )
            lines.append("")

            # Column details
            for src in self.sources:
                lines.extend(
                    [
                        f"### {src.name}",
                        "",
                        f"**Columns:** {', '.join(src.columns[:10])}"
                        + ("..." if len(src.columns) > 10 else ""),
                        "",
                    ]
                )

        # Issues
        if self.issues:
            lines.extend(["## Data Quality Issues", ""])
            for severity in ["critical", "high", "medium", "low"]:
                severity_issues = [i for i in self.issues if i.severity == severity]
                if severity_issues:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[severity]
                    lines.append(f"### {icon} {severity.title()} ({len(severity_issues)})")
                    for issue in severity_issues[:5]:
                        lines.extend(
                            [
                                f"- **{issue.source}**"
                                + (f" ({issue.column})" if issue.column else ""),
                                f"  - {issue.description}",
                                f"  - *Fix:* {issue.suggestion}",
                                "",
                            ]
                        )

        # Mappings
        if self.mappings:
            lines.extend(
                [
                    "## Transformation Mappings",
                    "",
                    "| Source | Target | Transform |",
                    "|--------|--------|-----------|",
                ]
            )
            for m in self.mappings[:20]:
                lines.append(f"| `{m.source_column}` | `{m.target_column}` | {m.transform} |")
            lines.append("")

        if self.recommendations:
            lines.extend(["## Recommendations", ""])
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")

        return "\n".join(lines)


class DataSyncAgent:
    """Data synchronization and migration agent."""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def analyze(self, data_dir: str = None) -> DataSyncReport:
        """Analyze data sources in project."""
        logger.info(f"Analyzing data in {self.project_path}")

        sources = []
        issues = []

        # Find data files
        data_path = self.project_path / (data_dir or "data")
        if not data_path.exists():
            data_path = self.project_path

        # Analyze CSV files
        for csv_file in data_path.glob("**/*.csv"):
            if any(skip in str(csv_file) for skip in ["node_modules", "venv"]):
                continue
            source, csv_issues = await self._analyze_csv(csv_file)
            if source:
                sources.append(source)
                issues.extend(csv_issues)

        # Analyze JSON files
        for json_file in data_path.glob("**/*.json"):
            if any(skip in str(json_file) for skip in ["node_modules", "venv", "package"]):
                continue
            source, json_issues = await self._analyze_json(json_file)
            if source:
                sources.append(source)
                issues.extend(json_issues)

        # Generate recommendations
        recommendations = self._generate_recommendations(sources, issues)

        return DataSyncReport(
            project_path=str(self.project_path),
            sources=sources,
            issues=issues,
            recommendations=recommendations,
        )

    async def _analyze_csv(self, file_path: Path) -> tuple[DataSource | None, list[DataIssue]]:
        """Analyze a CSV file."""
        issues = []
        rel_path = str(file_path.relative_to(self.project_path))

        try:
            with open(file_path, encoding="utf-8", errors="ignore") as f:
                # Detect delimiter
                sample = f.read(4096)
                f.seek(0)

                dialect = csv.Sniffer().sniff(sample)
                reader = csv.DictReader(f, dialect=dialect)

                columns = reader.fieldnames or []
                rows = []
                row_count = 0

                for row in reader:
                    row_count += 1
                    if len(rows) < 5:
                        rows.append(dict(row))

                    # Check for issues
                    for _col, val in row.items():
                        if val is None or val.strip() == "":
                            pass  # Track nulls

                # Check for common issues
                if any(" " in col for col in columns):
                    issues.append(
                        DataIssue(
                            severity="medium",
                            source=rel_path,
                            column=None,
                            description="Column names contain spaces",
                            suggestion="Rename columns to use underscores",
                        )
                    )

                return DataSource(
                    name=file_path.stem,
                    type="csv",
                    path=rel_path,
                    row_count=row_count,
                    columns=columns,
                    sample=rows,
                ), issues

        except Exception as e:
            logger.warning(f"Could not analyze {file_path}: {e}")
            return None, []

    async def _analyze_json(self, file_path: Path) -> tuple[DataSource | None, list[DataIssue]]:
        """Analyze a JSON file."""
        issues = []
        rel_path = str(file_path.relative_to(self.project_path))

        try:
            with open(file_path, encoding="utf-8") as f:
                data = json.load(f)

            # Handle array of objects
            if isinstance(data, list) and data and isinstance(data[0], dict):
                columns = list(data[0].keys())
                return DataSource(
                    name=file_path.stem,
                    type="json",
                    path=rel_path,
                    row_count=len(data),
                    columns=columns,
                    sample=data[:5],
                ), issues

            # Handle nested structure
            elif isinstance(data, dict):
                # Look for array property
                for key, val in data.items():
                    if isinstance(val, list) and val and isinstance(val[0], dict):
                        columns = list(val[0].keys())
                        return DataSource(
                            name=f"{file_path.stem}.{key}",
                            type="json",
                            path=rel_path,
                            row_count=len(val),
                            columns=columns,
                            sample=val[:5],
                        ), issues

            return None, issues

        except Exception as e:
            logger.warning(f"Could not analyze {file_path}: {e}")
            return None, []

    async def generate_mapping(
        self, source: DataSource, target_columns: list[str]
    ) -> list[TransformMapping]:
        """Generate transformation mappings between source and target."""
        mappings = []

        for src_col in source.columns:
            src_lower = src_col.lower().replace("_", "").replace(" ", "")

            # Try to find matching target column
            best_match = None
            for tgt_col in target_columns:
                tgt_lower = tgt_col.lower().replace("_", "").replace(" ", "")

                if src_lower == tgt_lower:
                    best_match = (tgt_col, "direct" if src_col == tgt_col else "rename")
                    break
                elif src_lower in tgt_lower or tgt_lower in src_lower:
                    best_match = (tgt_col, "rename")

            if best_match:
                mappings.append(
                    TransformMapping(
                        source_column=src_col, target_column=best_match[0], transform=best_match[1]
                    )
                )
            else:
                mappings.append(
                    TransformMapping(
                        source_column=src_col,
                        target_column="",
                        transform="unmapped",
                        details="No matching target column found",
                    )
                )

        return mappings

    async def generate_migration_script(
        self, source: DataSource, target_table: str, mappings: list[TransformMapping]
    ) -> str:
        """Generate a migration script."""
        if source.type == "csv":
            return self._generate_csv_migration(source, target_table, mappings)
        elif source.type == "json":
            return self._generate_json_migration(source, target_table, mappings)
        return ""

    def _generate_csv_migration(
        self, source: DataSource, target_table: str, mappings: list[TransformMapping]
    ) -> str:
        """Generate CSV to SQL migration script."""
        mapped = [m for m in mappings if m.transform != "unmapped"]

        ", ".join(m.source_column for m in mapped)
        tgt_cols = ", ".join(m.target_column or m.source_column for m in mapped)

        script = f'''#!/usr/bin/env python3
"""
Migration Script: {source.name} -> {target_table}
Auto-generated by Data Sync Agent
"""

import csv
import psycopg2
from psycopg2.extras import execute_values

def migrate(csv_path: str, db_url: str):
    """Migrate CSV data to database."""
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    with open(csv_path, 'r') as f:
        reader = csv.DictReader(f)
        rows = []
        for row in reader:
            rows.append((
                {", ".join(f'row["{m.source_column}"]' for m in mapped)}
            ))

    # Insert in batches
    execute_values(
        cursor,
        """
        INSERT INTO {target_table} ({tgt_cols})
        VALUES %s
        ON CONFLICT DO NOTHING
        """,
        rows
    )

    conn.commit()
    print(f"Migrated {{len(rows)}} rows to {target_table}")
    conn.close()

if __name__ == "__main__":
    import sys
    migrate(sys.argv[1], sys.argv[2])
'''
        return script

    def _generate_json_migration(
        self, source: DataSource, target_table: str, mappings: list[TransformMapping]
    ) -> str:
        """Generate JSON to SQL migration script."""
        mapped = [m for m in mappings if m.transform != "unmapped"]

        script = f'''#!/usr/bin/env python3
"""
Migration Script: {source.name} -> {target_table}
Auto-generated by Data Sync Agent
"""

import json
import psycopg2
from psycopg2.extras import execute_values

def migrate(json_path: str, db_url: str):
    """Migrate JSON data to database."""
    conn = psycopg2.connect(db_url)
    cursor = conn.cursor()

    with open(json_path, 'r') as f:
        data = json.load(f)

    if isinstance(data, dict):
        # Find array in nested structure
        for key, val in data.items():
            if isinstance(val, list):
                data = val
                break

    rows = []
    for item in data:
        rows.append((
            {", ".join(f'item.get("{m.source_column}")' for m in mapped)}
        ))

    # Insert in batches
    execute_values(
        cursor,
        """
        INSERT INTO {target_table} ({", ".join(m.target_column or m.source_column for m in mapped)})
        VALUES %s
        ON CONFLICT DO NOTHING
        """,
        rows
    )

    conn.commit()
    print(f"Migrated {{len(rows)}} rows to {target_table}")
    conn.close()

if __name__ == "__main__":
    import sys
    migrate(sys.argv[1], sys.argv[2])
'''
        return script

    def _generate_recommendations(self, sources: list, issues: list) -> list[str]:
        """Generate recommendations."""
        recommendations = []

        if not sources:
            recommendations.append("No data sources found. Add CSV or JSON files to analyze.")
            return recommendations

        # Check for large files
        large_files = [s for s in sources if s.row_count > 100000]
        if large_files:
            recommendations.append(
                f"Consider batching migrations for {len(large_files)} large files (>100k rows)"
            )

        # Check for quality issues
        if issues:
            recommendations.append(f"Fix {len(issues)} data quality issues before migration")

        # Check for inconsistent schemas
        all_columns = set()
        for source in sources:
            all_columns.update(source.columns)

        if len(all_columns) > 50:
            recommendations.append(
                "Consider normalizing data schema - many unique columns detected"
            )

        return recommendations[:5]


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Data Sync Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    parser.add_argument("--data-dir", help="Data directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = DataSyncAgent(args.path)
    report = await agent.analyze(args.data_dir)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
