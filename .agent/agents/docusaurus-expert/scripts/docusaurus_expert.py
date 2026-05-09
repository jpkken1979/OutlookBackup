#!/usr/bin/env python3
"""
Docusaurus Expert Agent - Documentation Site Analysis

Capabilities:
- Analyze Docusaurus configuration
- Check documentation structure
- Validate MDX/Markdown content
- Suggest improvements
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
class DocPage:
    """Documentation page information."""

    path: str
    title: str | None
    word_count: int
    has_frontmatter: bool
    has_toc: bool
    broken_links: list[str] = field(default_factory=list)


@dataclass
class DocIssue:
    """Documentation issue."""

    severity: str
    category: str  # structure, content, config, links
    file: str
    description: str
    suggestion: str


@dataclass
class DocusaurusReport:
    """Docusaurus analysis report."""

    project_path: str
    docusaurus_version: str = "unknown"
    docs_count: int = 0
    pages: list[DocPage] = field(default_factory=list)
    issues: list[DocIssue] = field(default_factory=list)
    config: dict = field(default_factory=dict)
    score: int = 100
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "docusaurus_version": self.docusaurus_version,
            "docs_count": self.docs_count,
            "pages": [p.__dict__ for p in self.pages],
            "issues": [i.__dict__ for i in self.issues],
            "config": self.config,
            "score": self.score,
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Docusaurus Analysis Report",
            "",
            f"**Project:** {self.project_path}",
            f"**Docusaurus Version:** {self.docusaurus_version}",
            f"**Documentation Score:** {self.score}/100",
            "",
            "## Summary",
            f"- **Documentation Pages:** {self.docs_count}",
            f"- **Issues:** {len(self.issues)}",
            "",
        ]

        # Config overview
        if self.config:
            lines.extend(["## Configuration", ""])
            for key, value in list(self.config.items())[:10]:
                lines.append(f"- **{key}:** {value}")
            lines.append("")

        # Pages
        if self.pages:
            lines.extend(
                [
                    "## Documentation Pages",
                    "",
                    "| Page | Words | Frontmatter | TOC |",
                    "|------|-------|-------------|-----|",
                ]
            )
            for page in self.pages[:20]:
                fm = "✅" if page.has_frontmatter else "❌"
                toc = "✅" if page.has_toc else "❌"
                lines.append(f"| `{page.path}` | {page.word_count} | {fm} | {toc} |")
            if len(self.pages) > 20:
                lines.append(f"| ... | +{len(self.pages) - 20} more | ... | ... |")
            lines.append("")

        # Issues
        if self.issues:
            lines.extend(["## Issues", ""])
            for severity in ["critical", "high", "medium", "low"]:
                severity_issues = [i for i in self.issues if i.severity == severity]
                if severity_issues:
                    icon = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}[severity]
                    lines.append(f"### {icon} {severity.title()} ({len(severity_issues)})")
                    for issue in severity_issues[:5]:
                        lines.extend(
                            [
                                f"- **{issue.category}** in `{issue.file}`",
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


class DocusaurusExpert:
    """Docusaurus documentation analysis agent."""

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def analyze(self) -> DocusaurusReport:
        """Analyze Docusaurus project."""
        logger.info(f"Analyzing Docusaurus in {self.project_path}")

        # Detect Docusaurus version
        version = self._detect_version()
        config = self._parse_config()

        pages = []
        issues = []

        # Find docs directory
        docs_dir = self.project_path / "docs"
        if not docs_dir.exists():
            docs_dir = self.project_path / "website" / "docs"

        if docs_dir.exists():
            # Analyze all markdown files
            for md_file in docs_dir.glob("**/*.{md,mdx}"):
                page, page_issues = await self._analyze_page(md_file, docs_dir)
                pages.append(page)
                issues.extend(page_issues)

        # Check configuration issues
        config_issues = self._check_config(config)
        issues.extend(config_issues)

        # Check structure issues
        structure_issues = self._check_structure(pages)
        issues.extend(structure_issues)

        # Calculate score
        score = self._calculate_score(issues, len(pages))

        # Generate recommendations
        recommendations = self._generate_recommendations(pages, issues, config)

        return DocusaurusReport(
            project_path=str(self.project_path),
            docusaurus_version=version,
            docs_count=len(pages),
            pages=pages,
            issues=issues,
            config=config,
            score=score,
            recommendations=recommendations,
        )

    def _detect_version(self) -> str:
        """Detect Docusaurus version."""
        pkg_json = self.project_path / "package.json"
        if pkg_json.exists():
            try:
                pkg = json.loads(pkg_json.read_text())
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "@docusaurus/core" in deps:
                    return deps["@docusaurus/core"].lstrip("^~")
            except Exception:
                pass

        return "unknown"

    def _parse_config(self) -> dict:
        """Parse Docusaurus config."""
        config_paths = [
            "docusaurus.config.js",
            "docusaurus.config.ts",
            "website/docusaurus.config.js",
        ]

        for config_path in config_paths:
            full_path = self.project_path / config_path
            if full_path.exists():
                try:
                    content = full_path.read_text()

                    config = {}

                    # Extract basic config values
                    title_match = re.search(r'title:\s*[\'"]([^\'"]+)[\'"]', content)
                    if title_match:
                        config["title"] = title_match.group(1)

                    url_match = re.search(r'url:\s*[\'"]([^\'"]+)[\'"]', content)
                    if url_match:
                        config["url"] = url_match.group(1)

                    base_match = re.search(r'baseUrl:\s*[\'"]([^\'"]+)[\'"]', content)
                    if base_match:
                        config["baseUrl"] = base_match.group(1)

                    # Check for features
                    config["has_blog"] = "blog" in content.lower()
                    config["has_i18n"] = "i18n" in content
                    config["has_search"] = (
                        "search" in content.lower() or "algolia" in content.lower()
                    )

                    return config
                except Exception:
                    pass

        return {}

    async def _analyze_page(
        self, file_path: Path, docs_dir: Path
    ) -> tuple[DocPage, list[DocIssue]]:
        """Analyze a documentation page."""
        issues = []
        rel_path = str(file_path.relative_to(docs_dir))

        try:
            content = file_path.read_text(errors="ignore")

            # Check frontmatter
            has_frontmatter = content.startswith("---")
            title = None

            if has_frontmatter:
                fm_end = content.find("---", 3)
                if fm_end > 0:
                    frontmatter = content[3:fm_end]
                    title_match = re.search(r'title:\s*[\'"]?([^\n\'"]+)', frontmatter)
                    if title_match:
                        title = title_match.group(1).strip()
            else:
                issues.append(
                    DocIssue(
                        severity="medium",
                        category="content",
                        file=rel_path,
                        description="Missing frontmatter",
                        suggestion="Add YAML frontmatter with title, description, and sidebar_position",
                    )
                )

            # Check for TOC
            has_toc = bool(re.search(r"^#{2,}\s", content, re.MULTILINE))

            # Count words
            text_only = re.sub(r"```[\s\S]*?```", "", content)  # Remove code blocks
            text_only = re.sub(r"<[^>]+>", "", text_only)  # Remove HTML
            word_count = len(text_only.split())

            # Check word count
            if word_count < 100:
                issues.append(
                    DocIssue(
                        severity="low",
                        category="content",
                        file=rel_path,
                        description=f"Page has only {word_count} words",
                        suggestion="Add more content or consider merging with another page",
                    )
                )

            # Check for broken internal links
            broken_links = []
            for match in re.finditer(r"\[([^\]]+)\]\(([^)]+)\)", content):
                link = match.group(2)
                if link.startswith("/") or link.startswith("./") or link.startswith("../"):
                    # Check if file exists
                    if link.startswith("/"):
                        link_path = docs_dir.parent / link.lstrip("/")
                    else:
                        link_path = file_path.parent / link

                    # Remove anchor
                    link_path = Path(str(link_path).split("#")[0])

                    if not link_path.exists() and not (
                        link_path.with_suffix(".md").exists()
                        or link_path.with_suffix(".mdx").exists()
                    ):
                        broken_links.append(link)

            if broken_links:
                issues.append(
                    DocIssue(
                        severity="high",
                        category="links",
                        file=rel_path,
                        description=f"{len(broken_links)} broken internal links",
                        suggestion=f"Fix links: {', '.join(broken_links[:3])}",
                    )
                )

            return DocPage(
                path=rel_path,
                title=title,
                word_count=word_count,
                has_frontmatter=has_frontmatter,
                has_toc=has_toc,
                broken_links=broken_links,
            ), issues

        except Exception as e:
            logger.warning(f"Could not analyze {file_path}: {e}")
            return DocPage(
                path=rel_path, title=None, word_count=0, has_frontmatter=False, has_toc=False
            ), []

    def _check_config(self, config: dict) -> list[DocIssue]:
        """Check configuration for issues."""
        issues = []

        if not config:
            issues.append(
                DocIssue(
                    severity="critical",
                    category="config",
                    file="docusaurus.config.js",
                    description="Configuration file not found or could not be parsed",
                    suggestion="Create docusaurus.config.js with required settings",
                )
            )
            return issues

        if not config.get("title"):
            issues.append(
                DocIssue(
                    severity="high",
                    category="config",
                    file="docusaurus.config.js",
                    description="Site title not configured",
                    suggestion="Add title property to config",
                )
            )

        if not config.get("has_search"):
            issues.append(
                DocIssue(
                    severity="medium",
                    category="config",
                    file="docusaurus.config.js",
                    description="Search not configured",
                    suggestion="Add Algolia or local search plugin",
                )
            )

        return issues

    def _check_structure(self, pages: list[DocPage]) -> list[DocIssue]:
        """Check documentation structure."""
        issues = []

        # Check for index page
        has_index = any(p.path in ["index.md", "index.mdx", "intro.md", "intro.mdx"] for p in pages)
        if not has_index and pages:
            issues.append(
                DocIssue(
                    severity="medium",
                    category="structure",
                    file="docs/",
                    description="No index or intro page found",
                    suggestion="Create docs/intro.md as the landing page",
                )
            )

        # Check for deep nesting
        deep_pages = [p for p in pages if p.path.count("/") > 3]
        if deep_pages:
            issues.append(
                DocIssue(
                    severity="low",
                    category="structure",
                    file="docs/",
                    description=f"{len(deep_pages)} pages nested more than 3 levels deep",
                    suggestion="Consider flattening navigation structure",
                )
            )

        return issues

    def _calculate_score(self, issues: list, page_count: int) -> int:
        """Calculate documentation score."""
        if page_count == 0:
            return 30

        score = 100
        penalties = {"critical": 15, "high": 8, "medium": 4, "low": 2}

        for issue in issues:
            score -= penalties.get(issue.severity, 0)

        return max(0, score)

    def _generate_recommendations(self, pages: list, issues: list, config: dict) -> list[str]:
        """Generate recommendations."""
        recommendations = []

        # Content recommendations
        short_pages = [p for p in pages if p.word_count < 200]
        if short_pages:
            recommendations.append(f"Expand {len(short_pages)} short pages with more content")

        # Frontmatter
        no_fm = [p for p in pages if not p.has_frontmatter]
        if no_fm:
            recommendations.append(f"Add frontmatter to {len(no_fm)} pages")

        # Links
        broken = [p for p in pages if p.broken_links]
        if broken:
            recommendations.append(f"Fix broken links in {len(broken)} pages")

        # Features
        if not config.get("has_search"):
            recommendations.append("Enable search with Algolia or local search plugin")

        if not config.get("has_i18n") and len(pages) > 20:
            recommendations.append("Consider adding i18n support for wider audience")

        return recommendations[:5]


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="Docusaurus Expert Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    agent = DocusaurusExpert(args.path)
    report = await agent.analyze()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
