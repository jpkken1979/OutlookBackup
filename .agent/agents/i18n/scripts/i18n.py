#!/usr/bin/env python3
"""
i18n Agent - Internationalization & Localization

Capabilities:
- Extract translatable strings from code
- Validate translation files
- Check for missing translations
- Analyze locale coverage
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
class TranslationKey:
    """A translatable string."""

    key: str
    default_value: str
    file: str
    line: int
    context: str | None = None


@dataclass
class MissingTranslation:
    """A missing translation."""

    key: str
    locale: str
    default_value: str


@dataclass
class I18nReport:
    """Internationalization analysis report."""

    project_path: str
    locales: list[str] = field(default_factory=list)
    total_keys: int = 0
    extracted_strings: list[TranslationKey] = field(default_factory=list)
    missing_translations: list[MissingTranslation] = field(default_factory=list)
    coverage: dict = field(default_factory=dict)
    issues: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "project_path": self.project_path,
            "locales": self.locales,
            "total_keys": self.total_keys,
            "extracted_strings": [s.__dict__ for s in self.extracted_strings],
            "missing_translations": [m.__dict__ for m in self.missing_translations],
            "coverage": self.coverage,
            "issues": self.issues,
            "recommendations": self.recommendations,
        }

    def to_markdown(self) -> str:
        lines = [
            "# Internationalization Report",
            "",
            f"**Project:** {self.project_path}",
            "",
            "## Summary",
            f"- **Total Keys:** {self.total_keys}",
            f"- **Locales:** {', '.join(self.locales) or 'None detected'}",
            "",
        ]

        if self.coverage:
            lines.extend(["## Coverage by Locale", ""])
            for locale, pct in self.coverage.items():
                bar = "█" * int(pct / 5) + "░" * (20 - int(pct / 5))
                lines.append(f"- **{locale}:** {bar} {pct:.1f}%")
            lines.append("")

        if self.missing_translations:
            lines.extend(
                [
                    "## Missing Translations",
                    "",
                    f"Found **{len(self.missing_translations)}** missing translations:",
                    "",
                ]
            )
            by_locale = {}
            for m in self.missing_translations:
                by_locale.setdefault(m.locale, []).append(m)

            for locale, missing in by_locale.items():
                lines.append(f"### {locale} ({len(missing)} missing)")
                for m in missing[:10]:
                    lines.append(
                        f'- `{m.key}`: "{m.default_value[:50]}..."'
                        if len(m.default_value) > 50
                        else f'- `{m.key}`: "{m.default_value}"'
                    )
                if len(missing) > 10:
                    lines.append(f"- ... and {len(missing) - 10} more")
                lines.append("")

        if self.extracted_strings:
            lines.extend(
                [
                    "## Extracted Strings (Sample)",
                    "",
                    "| Key | Default Value | File |",
                    "|-----|---------------|------|",
                ]
            )
            for s in self.extracted_strings[:15]:
                value = (
                    s.default_value[:30] + "..." if len(s.default_value) > 30 else s.default_value
                )
                lines.append(f"| `{s.key}` | {value} | {s.file}:{s.line} |")
            lines.append("")

        if self.issues:
            lines.extend(["## Issues", ""])
            for issue in self.issues:
                lines.append(f"- ⚠️ {issue}")
            lines.append("")

        if self.recommendations:
            lines.extend(["## Recommendations", ""])
            for i, rec in enumerate(self.recommendations, 1):
                lines.append(f"{i}. {rec}")

        return "\n".join(lines)


class I18nAgent:
    """Internationalization analysis agent."""

    # Patterns for extracting translatable strings
    PATTERNS = {
        "react_i18next": [
            r't\([\'"]([^"\']+)[\'"]\)',
            r'<Trans[^>]*i18nKey=[\'"]([^"\']+)[\'"]',
            r'useTranslation\(\).*?t\([\'"]([^"\']+)[\'"]\)',
        ],
        "vue_i18n": [
            r'\$t\([\'"]([^"\']+)[\'"]\)',
            r'v-t="[\'"]([^"\']+)[\'"]"',
            r'i18n\.t\([\'"]([^"\']+)[\'"]\)',
        ],
        "python_gettext": [
            r'_\([\'"]([^"\']+)[\'"]\)',
            r'gettext\([\'"]([^"\']+)[\'"]\)',
            r'ngettext\([\'"]([^"\']+)[\'"]',
        ],
        "generic": [
            r'i18n\.[\'"]([^"\']+)[\'"]',
            r'translate\([\'"]([^"\']+)[\'"]\)',
            r'__\([\'"]([^"\']+)[\'"]\)',
        ],
    }

    def __init__(self, project_path: str = "."):
        self.project_path = Path(project_path).resolve()

    async def analyze(self) -> I18nReport:
        """Analyze project for internationalization."""
        logger.info(f"Analyzing i18n in {self.project_path}")

        # Detect i18n framework
        framework = self._detect_framework()
        logger.info(f"Detected i18n framework: {framework}")

        # Find locale files
        locales, locale_data = self._find_locales()

        # Extract translatable strings
        extracted = await self._extract_strings(framework)

        # Find missing translations
        missing = self._find_missing(extracted, locale_data)

        # Calculate coverage
        coverage = self._calculate_coverage(extracted, locale_data)

        # Generate issues and recommendations
        issues = []
        recommendations = []

        if not locales:
            issues.append("No locale files detected")
            recommendations.append("Create locale files (e.g., en.json, es.json)")

        if missing:
            issues.append(f"{len(missing)} translations are missing")

        hardcoded = self._find_hardcoded_strings()
        if hardcoded:
            issues.append(f"Found {len(hardcoded)} potential hardcoded strings")
            recommendations.append("Extract hardcoded strings to translation files")

        if len(locales) == 1:
            recommendations.append("Add more locale files to support multiple languages")

        return I18nReport(
            project_path=str(self.project_path),
            locales=locales,
            total_keys=len(extracted),
            extracted_strings=extracted,
            missing_translations=missing,
            coverage=coverage,
            issues=issues,
            recommendations=recommendations,
        )

    def _detect_framework(self) -> str:
        """Detect i18n framework used."""
        pkg_json = self.project_path / "package.json"
        if pkg_json.exists():
            with open(pkg_json) as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                if "react-i18next" in deps or "i18next" in deps:
                    return "react_i18next"
                if "vue-i18n" in deps:
                    return "vue_i18n"
                if "next-i18next" in deps:
                    return "react_i18next"

        # Check for Python gettext
        if (self.project_path / "locale").exists() or (self.project_path / "locales").exists():
            return "python_gettext"

        return "generic"

    def _find_locales(self) -> tuple[list[str], dict]:
        """Find locale files and load their data."""
        locales = []
        locale_data = {}

        # Common locale directories
        locale_dirs = [
            "locales",
            "locale",
            "i18n",
            "lang",
            "languages",
            "public/locales",
            "src/locales",
            "src/i18n",
        ]

        for locale_dir in locale_dirs:
            dir_path = self.project_path / locale_dir
            if dir_path.exists():
                # JSON locale files
                for file_path in dir_path.glob("**/*.json"):
                    locale_name = file_path.stem
                    if locale_name not in ["index", "config"]:
                        locales.append(locale_name)
                        try:
                            with open(file_path) as f:
                                locale_data[locale_name] = self._flatten_dict(json.load(f))
                        except json.JSONDecodeError:
                            pass

                # YAML locale files
                for file_path in dir_path.glob("**/*.yml"):
                    locale_name = file_path.stem
                    if locale_name not in ["index", "config"]:
                        locales.append(locale_name)

        return list(set(locales)), locale_data

    def _flatten_dict(self, d: dict, parent_key: str = "") -> dict:
        """Flatten nested dictionary."""
        items = {}
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.update(self._flatten_dict(v, new_key))
            else:
                items[new_key] = v
        return items

    async def _extract_strings(self, framework: str) -> list[TranslationKey]:
        """Extract translatable strings from source code."""
        extracted = []
        patterns = self.PATTERNS.get(framework, []) + self.PATTERNS.get("generic", [])

        # File patterns to search
        extensions = ["*.js", "*.jsx", "*.ts", "*.tsx", "*.vue", "*.py"]

        for ext in extensions:
            for file_path in self.project_path.glob(f"**/{ext}"):
                if any(
                    skip in str(file_path) for skip in ["node_modules", "dist", "build", ".git"]
                ):
                    continue

                try:
                    content = file_path.read_text(errors="ignore")
                    for i, line in enumerate(content.split("\n"), 1):
                        for pattern in patterns:
                            for match in re.finditer(pattern, line):
                                key = match.group(1)
                                extracted.append(
                                    TranslationKey(
                                        key=key,
                                        default_value=key,  # Use key as default
                                        file=str(file_path.relative_to(self.project_path)),
                                        line=i,
                                    )
                                )
                except Exception as e:
                    logger.warning(f"Could not process {file_path}: {e}")

        # Deduplicate by key
        seen = set()
        unique = []
        for item in extracted:
            if item.key not in seen:
                seen.add(item.key)
                unique.append(item)

        return unique

    def _find_missing(
        self, extracted: list[TranslationKey], locale_data: dict
    ) -> list[MissingTranslation]:
        """Find missing translations."""
        missing = []
        keys = {e.key for e in extracted}

        for locale, data in locale_data.items():
            locale_keys = set(data.keys())
            for key in keys:
                if key not in locale_keys:
                    default = next((e.default_value for e in extracted if e.key == key), key)
                    missing.append(
                        MissingTranslation(key=key, locale=locale, default_value=default)
                    )

        return missing

    def _calculate_coverage(self, extracted: list[TranslationKey], locale_data: dict) -> dict:
        """Calculate translation coverage per locale."""
        coverage = {}
        keys = {e.key for e in extracted}
        total = len(keys) if keys else 1

        for locale, data in locale_data.items():
            locale_keys = set(data.keys())
            translated = len(keys & locale_keys)
            coverage[locale] = (translated / total) * 100

        return coverage

    def _find_hardcoded_strings(self) -> list[tuple[str, str, int]]:
        """Find potential hardcoded strings that should be translated."""
        hardcoded = []

        # Patterns for hardcoded strings (user-facing text)
        patterns = [
            r">\s*([A-Z][a-z]+(?:\s+[a-z]+)+)\s*<",  # Text in JSX
            r'placeholder=[\'"]([^"\']+)[\'"]',
            r'title=[\'"]([^"\']+)[\'"]',
            r'label=[\'"]([^"\']+)[\'"]',
            r'alt=[\'"]([^"\']+)[\'"]',
        ]

        extensions = ["*.jsx", "*.tsx", "*.vue"]

        for ext in extensions:
            for file_path in self.project_path.glob(f"**/{ext}"):
                if any(skip in str(file_path) for skip in ["node_modules", "dist", "build"]):
                    continue

                try:
                    content = file_path.read_text(errors="ignore")
                    for i, line in enumerate(content.split("\n"), 1):
                        for pattern in patterns:
                            for match in re.finditer(pattern, line):
                                text = match.group(1)
                                if len(text) > 3 and not text.startswith("{"):
                                    hardcoded.append((text, str(file_path), i))
                except Exception:
                    pass

        return hardcoded[:50]  # Limit results


async def main():
    import argparse

    parser = argparse.ArgumentParser(description="i18n Agent")
    parser.add_argument("path", nargs="?", default=".", help="Project path")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--extract", action="store_true", help="Only extract strings")
    args = parser.parse_args()

    agent = I18nAgent(args.path)
    report = await agent.analyze()

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print(report.to_markdown())


if __name__ == "__main__":
    asyncio.run(main())
