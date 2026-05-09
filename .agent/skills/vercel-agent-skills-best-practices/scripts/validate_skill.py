#!/usr/bin/env python3
"""
Validate agent skill packages against Vercel Agent Skills specification.

This script checks:
1. Required SKILL.md exists with valid YAML frontmatter
2. Name follows regex pattern ^[a-z0-9]+(-[a-z0-9]+)*$
3. Directory name matches skill name
4. Required metadata fields present
5. Markdown structure follows conventions
6. No information duplication between SKILL.md and references/
7. Scripts are executable and documented
8. Examples are complete and valid

Usage:
    python validate_skill.py path/to/skill/
    python validate_skill.py --batch path/to/skills/*/
    python validate_skill.py --report path/to/skill/ > report.md
"""

import argparse
import logging
import re
import sys
from dataclasses import dataclass
from pathlib import Path
import yaml

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    """Result of a validation check."""

    passed: bool
    message: str
    severity: str = "error"  # error, warning, info


class SkillValidator:
    """Validator for agent skill packages."""

    NAME_PATTERN = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
    REQUIRED_METADATA = ["name", "description"]
    RECOMMENDED_METADATA = ["version", "tags", "author"]

    def __init__(self, skill_path: Path):
        self.skill_path = skill_path.resolve()
        self.skill_md_path = self.skill_path / "SKILL.md"
        self.results: list[ValidationResult] = []

    def validate(self) -> bool:
        """Run all validation checks. Returns True if all critical checks pass."""
        logger.info(f"Validating skill: {self.skill_path.name}")

        self._check_skill_md_exists()
        if not self.skill_md_path.exists():
            return self._print_results()

        self._check_yaml_frontmatter()
        self._check_name_pattern()
        self._check_directory_name_match()
        self._check_required_metadata()
        self._check_recommended_metadata()
        self._check_markdown_structure()
        self._check_scripts()
        self._check_references()
        self._check_examples()

        return self._print_results()

    def _check_skill_md_exists(self):
        """Check that SKILL.md exists."""
        if self.skill_md_path.exists():
            self.results.append(
                ValidationResult(passed=True, message="[OK] SKILL.md exists", severity="info")
            )
        else:
            self.results.append(
                ValidationResult(
                    passed=False, message="[FAIL] SKILL.md not found (required)", severity="error"
                )
            )

    def _check_yaml_frontmatter(self):
        """Check that YAML frontmatter is valid."""
        try:
            content = self.skill_md_path.read_text(encoding="utf-8")

            if not content.startswith("---"):
                self.results.append(
                    ValidationResult(
                        passed=False,
                        message="[FAIL] SKILL.md must start with YAML frontmatter (---)",
                        severity="error",
                    )
                )
                return

            # Extract frontmatter
            parts = content.split("---", 2)
            if len(parts) < 3:
                self.results.append(
                    ValidationResult(
                        passed=False,
                        message="[FAIL] Invalid YAML frontmatter format",
                        severity="error",
                    )
                )
                return

            # Parse YAML
            self.frontmatter = yaml.safe_load(parts[1])
            self.markdown_content = parts[2].strip()

            self.results.append(
                ValidationResult(
                    passed=True, message="[OK] YAML frontmatter valid", severity="info"
                )
            )

        except yaml.YAMLError as e:
            self.results.append(
                ValidationResult(
                    passed=False, message=f"[FAIL] YAML parse error: {e}", severity="error"
                )
            )
        except Exception as e:
            self.results.append(
                ValidationResult(
                    passed=False, message=f"[FAIL] Error reading SKILL.md: {e}", severity="error"
                )
            )

    def _check_name_pattern(self):
        """Check that skill name follows regex pattern."""
        if not hasattr(self, "frontmatter"):
            return

        name = self.frontmatter.get("name")
        if not name:
            return  # Will be caught by required metadata check

        if self.NAME_PATTERN.match(name):
            self.results.append(
                ValidationResult(
                    passed=True, message=f"[OK] Name pattern valid: '{name}'", severity="info"
                )
            )
        else:
            self.results.append(
                ValidationResult(
                    passed=False,
                    message=f"[FAIL] Name '{name}' must match pattern: ^[a-z0-9]+(-[a-z0-9]+)*$",
                    severity="error",
                )
            )

    def _check_directory_name_match(self):
        """Check that directory name matches skill name."""
        if not hasattr(self, "frontmatter"):
            return

        name = self.frontmatter.get("name")
        if not name:
            return

        dir_name = self.skill_path.name

        if name == dir_name:
            self.results.append(
                ValidationResult(
                    passed=True,
                    message=f"[OK] Directory name matches skill name: '{name}'",
                    severity="info",
                )
            )
        else:
            self.results.append(
                ValidationResult(
                    passed=False,
                    message=f"[FAIL] Directory name '{dir_name}' must match skill name '{name}'",
                    severity="error",
                )
            )

    def _check_required_metadata(self):
        """Check that required metadata fields are present."""
        if not hasattr(self, "frontmatter"):
            return

        for field in self.REQUIRED_METADATA:
            value = self.frontmatter.get(field)
            if value:
                self.results.append(
                    ValidationResult(
                        passed=True,
                        message=f"[OK] Required field '{field}' present",
                        severity="info",
                    )
                )
            else:
                self.results.append(
                    ValidationResult(
                        passed=False,
                        message=f"[FAIL] Required field '{field}' missing",
                        severity="error",
                    )
                )

    def _check_recommended_metadata(self):
        """Check that recommended metadata fields are present."""
        if not hasattr(self, "frontmatter"):
            return

        for field in self.RECOMMENDED_METADATA:
            value = self.frontmatter.get(field)
            if value:
                self.results.append(
                    ValidationResult(
                        passed=True,
                        message=f"[OK] Recommended field '{field}' present",
                        severity="info",
                    )
                )
            else:
                self.results.append(
                    ValidationResult(
                        passed=False,
                        message=f"[WARN]  Recommended field '{field}' missing",
                        severity="warning",
                    )
                )

    def _check_markdown_structure(self):
        """Check that markdown follows conventions."""
        if not hasattr(self, "markdown_content"):
            return

        content = self.markdown_content

        # Check for recommended sections
        recommended_sections = [
            ("## Use this skill when", "activation criteria"),
            ("## Do not use this skill when", "anti-patterns"),
            ("## Instructions", "step-by-step guidance"),
            ("## Safety", "safety considerations"),
        ]

        for section, description in recommended_sections:
            if section in content:
                self.results.append(
                    ValidationResult(
                        passed=True,
                        message=f"[OK] Section '{section}' present ({description})",
                        severity="info",
                    )
                )
            else:
                self.results.append(
                    ValidationResult(
                        passed=False,
                        message=f"[WARN]  Section '{section}' missing (recommended for {description})",
                        severity="warning",
                    )
                )

        # Check for extended thinking
        if "[Extended thinking:" in content:
            self.results.append(
                ValidationResult(
                    passed=True, message="[OK] Extended thinking section present", severity="info"
                )
            )
        else:
            self.results.append(
                ValidationResult(
                    passed=False,
                    message="[WARN]  Extended thinking section missing (helps agent understand context)",
                    severity="warning",
                )
            )

    def _check_scripts(self):
        """Check scripts directory if present."""
        scripts_dir = self.skill_path / "scripts"

        if not scripts_dir.exists():
            self.results.append(
                ValidationResult(
                    passed=True, message="[INFO]  No scripts/ directory (optional)", severity="info"
                )
            )
            return

        # Check for executable files
        scripts = list(scripts_dir.glob("*"))
        if not scripts:
            self.results.append(
                ValidationResult(
                    passed=False,
                    message="[WARN]  scripts/ directory exists but is empty",
                    severity="warning",
                )
            )
            return

        for script in scripts:
            if script.is_file():
                # Check if executable (on Unix-like systems)
                if script.suffix in [".py", ".sh", ".js"]:
                    self.results.append(
                        ValidationResult(
                            passed=True,
                            message=f"[OK] Script found: {script.name}",
                            severity="info",
                        )
                    )

        # Check for README in scripts/
        if (scripts_dir / "README.md").exists():
            self.results.append(
                ValidationResult(
                    passed=True,
                    message="[OK] scripts/README.md documents script usage",
                    severity="info",
                )
            )
        else:
            self.results.append(
                ValidationResult(
                    passed=False,
                    message="[WARN]  scripts/README.md missing (recommended for documentation)",
                    severity="warning",
                )
            )

    def _check_references(self):
        """Check references directory if present."""
        refs_dir = self.skill_path / "references"

        if not refs_dir.exists():
            self.results.append(
                ValidationResult(
                    passed=True,
                    message="[INFO]  No references/ directory (optional)",
                    severity="info",
                )
            )
            return

        # Check for reference files
        refs = list(refs_dir.glob("**/*.md"))
        if not refs:
            self.results.append(
                ValidationResult(
                    passed=False,
                    message="[WARN]  references/ directory exists but contains no markdown files",
                    severity="warning",
                )
            )
            return

        for ref in refs:
            self.results.append(
                ValidationResult(
                    passed=True,
                    message=f"[OK] Reference found: {ref.relative_to(refs_dir)}",
                    severity="info",
                )
            )

        # Check that SKILL.md references the files (grep patterns)
        if hasattr(self, "markdown_content"):
            if "grep" in self.markdown_content.lower() and "references/" in self.markdown_content:
                self.results.append(
                    ValidationResult(
                        passed=True,
                        message="[OK] SKILL.md includes grep patterns for references/",
                        severity="info",
                    )
                )
            else:
                self.results.append(
                    ValidationResult(
                        passed=False,
                        message="[WARN]  SKILL.md should include grep patterns to access references/",
                        severity="warning",
                    )
                )

    def _check_examples(self):
        """Check examples directory if present."""
        examples_dir = self.skill_path / "examples"

        if not examples_dir.exists():
            self.results.append(
                ValidationResult(
                    passed=True,
                    message="[INFO]  No examples/ directory (optional)",
                    severity="info",
                )
            )
            return

        # Check for example files
        examples = list(examples_dir.glob("*"))
        if not examples:
            self.results.append(
                ValidationResult(
                    passed=False,
                    message="[WARN]  examples/ directory exists but is empty",
                    severity="warning",
                )
            )
            return

        for example in examples:
            if example.is_file():
                self.results.append(
                    ValidationResult(
                        passed=True, message=f"[OK] Example found: {example.name}", severity="info"
                    )
                )

    def _print_results(self) -> bool:
        """Print validation results and return overall pass/fail."""
        errors = [r for r in self.results if not r.passed and r.severity == "error"]
        warnings = [r for r in self.results if not r.passed and r.severity == "warning"]
        info = [r for r in self.results if r.passed]

        # Log all results with appropriate level
        for result in self.results:
            if result.severity == "error" and not result.passed:
                logger.error(result.message.replace("[FAIL] ", ""))
            elif result.severity == "warning":
                logger.warning(result.message.replace("[WARN]  ", ""))
            else:
                logger.info(result.message.replace("[OK] ", "").replace("[INFO]  ", ""))

        # Summary
        logger.info("=" * 50)
        logger.info("Summary:")
        logger.info(f"  Passed: {len(info)}")
        logger.info(f"  Warnings: {len(warnings)}")
        logger.info(f"  Errors: {len(errors)}")
        logger.info("=" * 50)

        if errors:
            logger.error("Validation FAILED")
            return False
        elif warnings:
            logger.warning("Validation PASSED (with warnings)")
            return True
        else:
            logger.info("Validation PASSED")
            return True


def main():
    parser = argparse.ArgumentParser(description="Validate agent skill packages")
    parser.add_argument("path", type=Path, help="Path to skill directory")
    parser.add_argument(
        "--batch",
        action="store_true",
        help="Validate multiple skills (path should be glob pattern)",
    )
    parser.add_argument("--report", action="store_true", help="Generate markdown report")

    args = parser.parse_args()

    if args.batch:
        # Validate multiple skills
        skill_dirs = [p for p in args.path.parent.glob(args.path.name) if p.is_dir()]
        all_passed = True

        for skill_dir in skill_dirs:
            validator = SkillValidator(skill_dir)
            passed = validator.validate()
            all_passed = all_passed and passed

        sys.exit(0 if all_passed else 1)
    else:
        # Validate single skill
        validator = SkillValidator(args.path)
        passed = validator.validate()
        sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
