#!/usr/bin/env python3
"""
Pre-commit hook to detect @pytest.mark.flaky without justification.

Flaky tests indicate underlying issues that should be investigated.
This hook ensures that any flaky tests have comments explaining why they're flaky.

Usage:
    python .agent/scripts/check_flaky_tests.py [--fix]
"""

import re
import sys
from pathlib import Path


FLAKY_PATTERN = re.compile(r"@pytest\.mark\.flaky")
JUSTIFICATION_PATTERN = re.compile(r"# (flaky|FLAKY|Flaky).*:")


def check_test_file(filepath: Path) -> tuple[int, list[str]]:
    """
    Check for @pytest.mark.flaky without justification.

    Returns:
        (error_count, error_messages)
    """
    errors = []

    if filepath.suffix != ".py" or not filepath.name.startswith("test_"):
        return 0, []

    content = filepath.read_text()
    lines = content.split("\n")

    for i, line in enumerate(lines, 1):
        if FLAKY_PATTERN.search(line):
            # Check for justification in same line or previous line
            has_justification = False

            # Check same line
            if JUSTIFICATION_PATTERN.search(line):
                has_justification = True

            # Check previous line
            if i > 1:
                prev_line = lines[i - 2]
                if JUSTIFICATION_PATTERN.search(prev_line) and prev_line.strip().startswith("#"):
                    has_justification = True

            # Check next line (decorator is on previous line)
            if i < len(lines):
                next_line = lines[i]
                if JUSTIFICATION_PATTERN.search(next_line) and next_line.strip().startswith("#"):
                    has_justification = True

            if not has_justification:
                errors.append(
                    f"{filepath}:{i}: @pytest.mark.flaky without justification. "
                    f"Add a comment explaining why this test is flaky."
                )

    return len(errors), errors


def check_all_tests() -> int:
    """Check all test files in tests/ directory."""
    tests_dir = Path(".") / "tests"

    if not tests_dir.exists():
        print("❌ tests/ directory not found")
        return 1

    total_errors = 0
    all_errors = []

    for test_file in tests_dir.rglob("test_*.py"):
        error_count, errors = check_test_file(test_file)
        total_errors += error_count
        all_errors.extend(errors)

    # Print results
    if all_errors:
        print("❌ Found @pytest.mark.flaky without justification:\n")
        for error in all_errors:
            print(f"  {error}")
        print(f"\n⚠️  Total: {total_errors} flaky tests without justification")
        return 1
    else:
        print("✅ All @pytest.mark.flaky markers have proper justification")
        return 0


def main():
    """Main entry point."""
    exit_code = check_all_tests()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
