#!/usr/bin/env python3
"""
SEO Specialist Agent - SEO and GEO optimization analysis.

Usage:
    python seo_specialist.py <html_file_or_url> [--json]
    python seo_specialist.py --audit <directory> [--json]
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class SEOIssue:
    """SEO issue found in analysis."""

    id: str
    category: str  # technical, content, geo, performance
    severity: str  # critical, high, medium, low
    title: str
    location: str
    description: str
    fix: str
    impact: str


@dataclass
class SEOMetrics:
    """SEO metrics for a page."""

    title_length: int
    meta_description_length: int
    h1_count: int
    h2_count: int
    image_count: int
    images_with_alt: int
    internal_links: int
    external_links: int
    word_count: int
    has_canonical: bool
    has_robots_meta: bool
    has_og_tags: bool
    has_twitter_cards: bool
    has_schema: bool
    has_sitemap: bool


@dataclass
class GEOMetrics:
    """GEO (Generative Engine Optimization) metrics."""

    has_faq_section: bool
    has_author_info: bool
    has_statistics: bool
    has_definitions: bool
    has_timestamps: bool
    has_expert_quotes: bool
    citation_readiness_score: float


@dataclass
class SEOReport:
    """Complete SEO audit report."""

    target: str
    timestamp: str
    issues: list = field(default_factory=list)
    seo_metrics: dict = field(default_factory=dict)
    geo_metrics: dict = field(default_factory=dict)
    recommendations: list = field(default_factory=list)
    score: dict = field(default_factory=dict)


class SEOSpecialist:
    """SEO and GEO analysis agent."""

    SEO_CHECKS = {
        "missing_title": {
            "pattern": r"<title[^>]*>([^<]*)</title>",
            "check": "exists",
            "severity": "critical",
            "title": "Missing or empty title tag",
            "fix": "Add a unique, descriptive title tag (50-60 characters)",
            "impact": "Major ranking factor, affects CTR",
        },
        "missing_meta_description": {
            "pattern": r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
            "check": "exists",
            "severity": "high",
            "title": "Missing meta description",
            "fix": "Add meta description (150-160 characters)",
            "impact": "Affects CTR in search results",
        },
        "missing_h1": {
            "pattern": r"<h1[^>]*>",
            "check": "exists",
            "severity": "high",
            "title": "Missing H1 tag",
            "fix": "Add one H1 tag per page with primary keyword",
            "impact": "Important for topic relevance",
        },
        "multiple_h1": {
            "pattern": r"<h1[^>]*>",
            "check": "count_max",
            "max": 1,
            "severity": "medium",
            "title": "Multiple H1 tags",
            "fix": "Use only one H1 tag per page",
            "impact": "Can confuse search engines",
        },
        "images_without_alt": {
            "pattern": r"<img[^>]*(?!alt=)[^>]*>",
            "check": "not_exists",
            "severity": "medium",
            "title": "Images missing alt text",
            "fix": "Add descriptive alt text to all images",
            "impact": "Accessibility and image SEO",
        },
        "missing_canonical": {
            "pattern": r'<link[^>]*rel=["\']canonical["\']',
            "check": "exists",
            "severity": "medium",
            "title": "Missing canonical tag",
            "fix": "Add canonical tag to prevent duplicate content",
            "impact": "Prevents duplicate content issues",
        },
        "missing_viewport": {
            "pattern": r'<meta[^>]*name=["\']viewport["\']',
            "check": "exists",
            "severity": "high",
            "title": "Missing viewport meta tag",
            "fix": "Add viewport meta for mobile responsiveness",
            "impact": "Mobile-first indexing requirement",
        },
    }

    GEO_CHECKS = {
        "faq_section": {
            "patterns": [r'<[^>]*class=["\'][^"\']*faq[^"\']*["\']', r"FAQ", r"Frequently Asked"],
            "title": "FAQ section",
            "impact": "High citation potential for AI",
        },
        "author_info": {
            "patterns": [r'<[^>]*class=["\'][^"\']*author[^"\']*["\']', r"Written by", r"Author:"],
            "title": "Author information",
            "impact": "E-E-A-T signal",
        },
        "statistics": {
            "patterns": [r"\d+%", r"\d+ out of \d+", r"according to", r"study shows"],
            "title": "Statistics with sources",
            "impact": "High citation potential",
        },
        "definitions": {
            "patterns": [r"is defined as", r"refers to", r"means that", r"<dfn"],
            "title": "Clear definitions",
            "impact": "AI extractable",
        },
        "timestamps": {
            "patterns": [r"Updated:", r"Last modified", r"Published:", r"datetime="],
            "title": "Content timestamps",
            "impact": "Freshness signal",
        },
    }

    def __init__(self):
        self.issue_counter = 0

    def _generate_issue_id(self) -> str:
        """Generate unique issue ID."""
        self.issue_counter += 1
        return f"SEO-{self.issue_counter:03d}"

    def analyze_html(self, content: str, file_path: str) -> tuple:
        """Analyze HTML content for SEO issues."""
        issues = []

        for _check_name, check_config in self.SEO_CHECKS.items():
            pattern = check_config["pattern"]
            matches = re.findall(pattern, content, re.IGNORECASE | re.DOTALL)

            should_report = False

            if (
                check_config["check"] == "exists"
                and not matches
                or check_config["check"] == "not_exists"
                and matches
                or check_config["check"] == "count_max"
                and len(matches) > check_config.get("max", 1)
            ):
                should_report = True

            if should_report:
                issues.append(
                    SEOIssue(
                        id=self._generate_issue_id(),
                        category="technical",
                        severity=check_config["severity"],
                        title=check_config["title"],
                        location=file_path,
                        description=check_config["title"],
                        fix=check_config["fix"],
                        impact=check_config["impact"],
                    )
                )

        # Extract metrics
        title_match = re.search(r"<title[^>]*>([^<]*)</title>", content, re.IGNORECASE)
        meta_desc_match = re.search(
            r'<meta[^>]*name=["\']description["\'][^>]*content=["\']([^"\']*)["\']',
            content,
            re.IGNORECASE,
        )

        metrics = SEOMetrics(
            title_length=len(title_match.group(1)) if title_match else 0,
            meta_description_length=len(meta_desc_match.group(1)) if meta_desc_match else 0,
            h1_count=len(re.findall(r"<h1[^>]*>", content, re.IGNORECASE)),
            h2_count=len(re.findall(r"<h2[^>]*>", content, re.IGNORECASE)),
            image_count=len(re.findall(r"<img[^>]*>", content, re.IGNORECASE)),
            images_with_alt=len(
                re.findall(r'<img[^>]*alt=["\'][^"\']+["\']', content, re.IGNORECASE)
            ),
            internal_links=len(re.findall(r'href=["\'][^"\']*(?<!http)["\']', content)),
            external_links=len(re.findall(r'href=["\']https?://', content)),
            word_count=len(re.findall(r"\b\w+\b", re.sub(r"<[^>]+>", "", content))),
            has_canonical=bool(re.search(r'rel=["\']canonical["\']', content)),
            has_robots_meta=bool(re.search(r'name=["\']robots["\']', content)),
            has_og_tags=bool(re.search(r'property=["\']og:', content)),
            has_twitter_cards=bool(re.search(r'name=["\']twitter:', content)),
            has_schema=bool(re.search(r"application/ld\+json|itemtype=", content)),
            has_sitemap=False,  # Checked separately
        )

        # Check title length
        if metrics.title_length > 0:
            if metrics.title_length < 30:
                issues.append(
                    SEOIssue(
                        id=self._generate_issue_id(),
                        category="content",
                        severity="medium",
                        title="Title too short",
                        location=file_path,
                        description=f"Title is {metrics.title_length} characters (recommended: 50-60)",
                        fix="Expand title to 50-60 characters with relevant keywords",
                        impact="Suboptimal CTR",
                    )
                )
            elif metrics.title_length > 60:
                issues.append(
                    SEOIssue(
                        id=self._generate_issue_id(),
                        category="content",
                        severity="low",
                        title="Title too long",
                        location=file_path,
                        description=f"Title is {metrics.title_length} characters (may be truncated)",
                        fix="Shorten title to 50-60 characters",
                        impact="Title truncation in SERPs",
                    )
                )

        return issues, metrics

    def analyze_geo(self, content: str) -> GEOMetrics:
        """Analyze content for GEO optimization."""
        results = {}

        for check_name, check_config in self.GEO_CHECKS.items():
            found = False
            for pattern in check_config["patterns"]:
                if re.search(pattern, content, re.IGNORECASE):
                    found = True
                    break
            results[check_name] = found

        # Calculate citation readiness score
        score = sum(1 for v in results.values() if v) / len(results) * 100

        return GEOMetrics(
            has_faq_section=results.get("faq_section", False),
            has_author_info=results.get("author_info", False),
            has_statistics=results.get("statistics", False),
            has_definitions=results.get("definitions", False),
            has_timestamps=results.get("timestamps", False),
            has_expert_quotes=bool(
                re.search(r'[""][^""]{20,}[""].*said|according to', content, re.IGNORECASE)
            ),
            citation_readiness_score=round(score, 1),
        )

    def audit_directory(self, path: Path) -> SEOReport:
        """Audit all HTML files in a directory."""
        all_issues = []
        all_seo_metrics = []
        all_geo_metrics = []

        html_files = list(path.rglob("*.html")) + list(path.rglob("*.htm"))

        for html_file in html_files:
            if any(skip in str(html_file) for skip in ["node_modules", ".git", "dist", "build"]):
                continue

            try:
                content = html_file.read_text(errors="ignore")
                issues, seo_metrics = self.analyze_html(content, str(html_file))
                geo_metrics = self.analyze_geo(content)

                all_issues.extend(issues)
                all_seo_metrics.append(seo_metrics)
                all_geo_metrics.append(geo_metrics)
            except Exception as e:
                logger.debug(f"Error analyzing {html_file}: {e}")

        # Check for sitemap
        sitemap_exists = (path / "sitemap.xml").exists() or (
            path / "public" / "sitemap.xml"
        ).exists()
        if not sitemap_exists:
            all_issues.append(
                SEOIssue(
                    id=self._generate_issue_id(),
                    category="technical",
                    severity="medium",
                    title="Missing sitemap.xml",
                    location=str(path),
                    description="No sitemap.xml found in project",
                    fix="Create and submit sitemap.xml to search engines",
                    impact="Crawling efficiency",
                )
            )

        # Check for robots.txt
        robots_exists = (path / "robots.txt").exists() or (path / "public" / "robots.txt").exists()
        if not robots_exists:
            all_issues.append(
                SEOIssue(
                    id=self._generate_issue_id(),
                    category="technical",
                    severity="medium",
                    title="Missing robots.txt",
                    location=str(path),
                    description="No robots.txt found in project",
                    fix="Create robots.txt with crawl directives",
                    impact="Crawler guidance",
                )
            )

        # Calculate scores
        severity_counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        for issue in all_issues:
            severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1

        seo_score = 100 - (
            severity_counts["critical"] * 20
            + severity_counts["high"] * 10
            + severity_counts["medium"] * 5
            + severity_counts["low"] * 2
        )
        seo_score = max(0, min(100, seo_score))

        avg_geo_score = sum(m.citation_readiness_score for m in all_geo_metrics) / max(
            len(all_geo_metrics), 1
        )

        # Generate recommendations
        recommendations = []
        if severity_counts["critical"] > 0:
            recommendations.append(
                "Fix critical SEO issues immediately (missing titles, descriptions)"
            )
        if not sitemap_exists:
            recommendations.append("Create and submit sitemap.xml")
        if avg_geo_score < 50:
            recommendations.append(
                "Improve GEO: Add FAQ sections, author info, and statistics with sources"
            )
        recommendations.append("Implement structured data (Schema.org)")
        recommendations.append("Monitor Core Web Vitals")

        # Aggregate metrics
        avg_seo_metrics = {
            "avg_title_length": sum(m.title_length for m in all_seo_metrics)
            / max(len(all_seo_metrics), 1),
            "pages_with_h1": sum(1 for m in all_seo_metrics if m.h1_count == 1),
            "pages_with_schema": sum(1 for m in all_seo_metrics if m.has_schema),
            "pages_with_og": sum(1 for m in all_seo_metrics if m.has_og_tags),
            "total_pages": len(all_seo_metrics),
        }

        avg_geo_metrics = {
            "pages_with_faq": sum(1 for m in all_geo_metrics if m.has_faq_section),
            "pages_with_author": sum(1 for m in all_geo_metrics if m.has_author_info),
            "citation_readiness": round(avg_geo_score, 1),
        }

        return SEOReport(
            target=str(path),
            timestamp=datetime.now().isoformat(),
            issues=[asdict(i) for i in all_issues],
            seo_metrics=avg_seo_metrics,
            geo_metrics=avg_geo_metrics,
            recommendations=recommendations,
            score={
                "seo_score": round(seo_score, 1),
                "geo_score": round(avg_geo_score, 1),
                "overall": round((seo_score + avg_geo_score) / 2, 1),
                "by_severity": severity_counts,
            },
        )


def format_report_markdown(report: SEOReport) -> str:
    """Format report as markdown."""
    lines = [
        "# SEO Audit Report",
        "",
        f"**Target:** {report.target}",
        f"**Date:** {report.timestamp}",
        "",
        "## Scores",
        "",
        "| Metric | Score |",
        "|--------|-------|",
        f"| SEO Score | {report.score.get('seo_score', 0)}/100 |",
        f"| GEO Score | {report.score.get('geo_score', 0)}/100 |",
        f"| **Overall** | **{report.score.get('overall', 0)}/100** |",
        "",
        "## Issues by Severity",
        "",
    ]

    for severity, count in report.score.get("by_severity", {}).items():
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
                f"**Location:** `{issue.get('location', '')}`",
                f"**Impact:** {issue.get('impact', '')}",
                "",
                f"**Fix:** {issue.get('fix', '')}",
                "",
                "---",
                "",
            ]
        )

    lines.extend(["", "## GEO Metrics (AI Citation Readiness)", ""])
    for key, value in report.geo_metrics.items():
        lines.append(f"- **{key.replace('_', ' ').title()}:** {value}")

    lines.extend(["", "## Recommendations", ""])
    for i, rec in enumerate(report.recommendations, 1):
        lines.append(f"{i}. {rec}")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="SEO Specialist Agent")
    parser.add_argument("target", nargs="?", help="HTML file or URL to analyze")
    parser.add_argument("--audit", help="Audit entire directory")
    parser.add_argument("--json", action="store_true", help="Output as JSON")

    args = parser.parse_args()

    specialist = SEOSpecialist()

    if args.audit:
        report = specialist.audit_directory(Path(args.audit))
    elif args.target:
        path = Path(args.target)
        if path.is_dir():
            report = specialist.audit_directory(path)
        elif path.exists():
            content = path.read_text()
            issues, seo_metrics = specialist.analyze_html(content, str(path))
            geo_metrics = specialist.analyze_geo(content)
            report = SEOReport(
                target=str(path),
                timestamp=datetime.now().isoformat(),
                issues=[asdict(i) for i in issues],
                seo_metrics=asdict(seo_metrics),
                geo_metrics=asdict(geo_metrics),
                recommendations=["Review and fix identified issues"],
                score={
                    "seo_score": 100 - len(issues) * 10,
                    "geo_score": geo_metrics.citation_readiness_score,
                },
            )
        else:
            print(f"Target not found: {args.target}")
            sys.exit(1)
    else:
        parser.print_help()
        sys.exit(0)

    if args.json:
        print(
            json.dumps(
                asdict(report) if hasattr(report, "__dataclass_fields__") else report,
                indent=2,
                default=str,
            )
        )
    else:
        print(format_report_markdown(report))


if __name__ == "__main__":
    main()
