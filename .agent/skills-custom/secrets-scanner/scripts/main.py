#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""secrets-scanner CLI entry point.

Scans codebase for hardcoded secrets, API keys, tokens, and credentials.
Integrates with pre-commit hooks and CI/CD pipelines.
"""

import argparse
import io
import logging
import os
import subprocess
import sys
import textwrap
from pathlib import Path

# Force UTF-8 output on Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8")

# Package-relative imports: work whether run as script or module.
_SCRIPTS_DIR = str(Path(__file__).parent.resolve())
if _SCRIPTS_DIR not in sys.path:
    sys.path.insert(0, _SCRIPTS_DIR)

from patterns import list_all_types
from scanner import format_json, format_text, scan_path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

TOOL_NAME = "secrets-scanner"
TOOL_VERSION = "1.0.0"
EXIT_CLEAN = 0
EXIT_SECRETS_FOUND = 1
EXIT_ERROR = 2

# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build and return the argument parser."""
    parser = argparse.ArgumentParser(
        prog=TOOL_NAME,
        description="Scan codebase for hardcoded secrets and credentials.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent(
            f"""\
            Examples:
              {TOOL_NAME} --scope .
              {TOOL_NAME} --scope . --format json
              {TOOL_NAME} --scope .agent --exclude node_modules --fix
              {TOOL_NAME} --git-diff --fail-on-secrets
              {TOOL_NAME} --list-types

            Exit codes:
              0 - No secrets detected
              1 - Secrets detected (CRITICAL or --fail-on-secrets)
              2 - Error (path not found, etc.)
            """
        ),
    )

    parser.add_argument(
        "--version",
        action="version",
        version=f"{TOOL_NAME} {TOOL_VERSION}",
    )

    parser.add_argument(
        "--scope",
        type=str,
        default=".",
        metavar="PATH",
        help="Directory or file to scan (default: .)",
    )

    parser.add_argument(
        "--exclude",
        action="append",
        default=[],
        metavar="PATTERN",
        help="Exclude pattern (dir/file name). Can be repeated.",
    )

    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format (default: text)",
    )

    parser.add_argument(
        "--fix",
        action="store_true",
        help="Show remediation suggestions for each finding.",
    )

    parser.add_argument(
        "--git-diff",
        action="store_true",
        help="Scan only uncommitted git changes (staged + unstaged).",
    )

    parser.add_argument(
        "--fail-on-secrets",
        action="store_true",
        help="Exit with code 1 if any secret is found (for CI).",
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Interactive mode: prompt to suppress false positives.",
    )

    parser.add_argument(
        "--list-types",
        action="store_true",
        help="List all detected secret types and exit.",
    )

    parser.add_argument(
        "--entropy-threshold",
        type=float,
        default=4.5,
        metavar="FLOAT",
        help="Shannon entropy threshold for high-entropy detection (default: 4.5)",
    )

    parser.add_argument(
        "--no-entropy",
        action="store_true",
        help="Disable entropy-based detection (patterns only).",
    )

    parser.add_argument(
        "--watch",
        action="store_true",
        help="Watch mode: re-scan every 30 seconds.",
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Verbose output (show skipped files, etc.).",
    )

    parser.add_argument(
        "--git-hooks",
        action="store_true",
        dest="install_hooks",
        help="Install pre-commit hook to .git/hooks/.",
    )

    return parser


# ---------------------------------------------------------------------------
# Pre-commit hook installation
# ---------------------------------------------------------------------------


def install_pre_commit_hook() -> int:
    """Install the pre-commit hook in .git/hooks/.

    Returns:
        Exit code (0 on success).
    """
    repo_root = Path.cwd()
    hooks_dir = repo_root / ".git" / "hooks"
    hook_path = hooks_dir / "pre-commit"

    hook_content = textwrap.dedent(
        f"""\
        #!/bin/bash
        # Auto-generated by {TOOL_NAME} {TOOL_VERSION}
        # DO NOT EDIT — regenerate with: secrets-scanner --git-hooks

        SCRIPT_DIR="$(cd "$(dirname "${{BASH_SOURCE[0]}}")" && pwd)"
        REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"

        echo "Running {TOOL_NAME}..."
        python "$REPO_ROOT/.agent/skills-custom/{TOOL_NAME}/scripts/main.py" \\
            --git-diff \\
            --fail-on-secrets \\
            --format text

        EXIT_CODE=$?

        if [ $EXIT_CODE -ne 0 ]; then
            echo ""
            echo "⚠️  SECRETS DETECTED — commit aborted"
            echo "   Fix the findings above and commit again."
            echo "   To bypass: git commit --no-verify"
            echo "   To scan without failing: secrets-scanner --git-diff"
        fi

        exit $EXIT_CODE
        """
    )

    try:
        hooks_dir.mkdir(parents=True, exist_ok=True)
        hook_path.write_text(hook_content, encoding="utf-8")
        # Make it executable on Unix
        try:
            os.chmod(hook_path, 0o755)
        except OSError:
            pass  # Not fatal on Windows
        print(f"Pre-commit hook installed: {hook_path}")
        print("To uninstall: rm .git/hooks/pre-commit")
        return EXIT_CLEAN
    except (OSError, IOError) as e:
        logger.error("Failed to install pre-commit hook: %s", e)
        return EXIT_ERROR


# ---------------------------------------------------------------------------
# Interactive suppression
# ---------------------------------------------------------------------------


def interactive_suppress(result) -> None:
    """Prompt user to suppress false positive findings.

    Args:
        result: ScanResult to modify in place.
    """
    print("\n--- Interactive Suppression ---")
    print("Press ENTER to keep a finding, 's' to suppress.")
    print("Suppressed findings are ignored in this scan.")
    print("")

    new_findings: list = []
    for finding in result.findings:
        mask = finding.matched[:12] + "***" if len(finding.matched) > 12 else "***"
        prompt = f"  [{finding.id}] {finding.file_path}:{finding.line} — {mask}\n"
        prompt += f"  Context: {finding.context[:80]}\n"
        prompt += "  [ENTER] keep | [s] suppress: "

        try:
            response = input(prompt).strip().lower()
            if response == "s":
                finding.suppressed = True
                print("  → Suppressed")
            else:
                print("  → Kept")
        except (EOFError, KeyboardInterrupt):
            print("")
            break

        new_findings.append(finding)

    result.findings = new_findings


# ---------------------------------------------------------------------------
# Watch mode
# ---------------------------------------------------------------------------


def watch_mode(scope: str, exclude: list[str], args) -> None:
    """Run scans in watch mode, re-scanning every 30 seconds.

    Args:
        scope: Directory to scan.
        exclude: Exclusion patterns.
        args: Parsed CLI arguments.
    """
    import time

    print(f"Watch mode: scanning {scope} every 30 seconds. Ctrl+C to stop.")
    print("")

    prev_secrets = -1
    while True:
        result = scan_path(
            scope=scope,
            exclude_patterns=exclude,
            entropy_threshold=args.entropy_threshold,
            entropy_enabled=not args.no_entropy,
            git_diff=args.git_diff,
        )

        if result.secrets_found != prev_secrets:
            # Clear screen (simple approach)
            print("\033[2J\033[H", end="")  # ANSI clear
            print(f"SECRETS SCAN — {scope} — {result.scan_date}")
            print(f"Files: {result.files_scanned} | Secrets: {result.secrets_found}")
            print("")
            print(format_text(result, show_fix=args.fix))
            print("")
            prev_secrets = result.secrets_found

        time.sleep(30)


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------


def main() -> int:
    """Run the secrets scanner CLI.

    Returns:
        Exit code: 0 (clean), 1 (secrets found), 2 (error).
    """
    parser = build_parser()
    args = parser.parse_args()

    # --list-types: show all types and exit
    if args.list_types:
        types = list_all_types()
        print(f"{TOOL_NAME} v{TOOL_VERSION} — Detected Secret Types")
        print("=" * 70)
        print(f"{'Type':<40} {'Severity':<10} {'Remediation'}")
        print("-" * 70)
        for name, severity, remediation in types:
            print(f"{name:<40} {severity:<10} {remediation[:50]}")
        print("-" * 70)
        print(f"{len(types)} types registered.")
        return EXIT_CLEAN

    # --git-hooks: install pre-commit hook
    if args.install_hooks:
        return install_pre_commit_hook()

    # Validate scope
    scope_path = Path(args.scope)
    if not args.git_diff and not scope_path.exists():
        logger.error("Path does not exist: %s", args.scope)
        return EXIT_ERROR

    if args.verbose:
        logger.getLogger().setLevel(logging.DEBUG)

    # Watch mode
    if args.watch:
        watch_mode(args.scope, args.exclude, args)
        return EXIT_CLEAN  # never reached

    # Run scan
    logger.debug("Starting scan: scope=%s, exclude=%s", args.scope, args.exclude)
    result = scan_path(
        scope=args.scope,
        exclude_patterns=args.exclude,
        entropy_threshold=args.entropy_threshold,
        entropy_enabled=not args.no_entropy,
        git_diff=args.git_diff,
    )

    # Interactive suppression
    if args.interactive and result.findings:
        interactive_suppress(result)

    # Format output
    if args.format == "json":
        print(format_json(result))
    else:
        print(format_text(result, show_fix=args.fix))

    # Exit code logic
    if result.has_critical:
        logger.warning(
            "CRITICAL secrets found: %d critical, %d high, %d medium",
            result.critical_count,
            result.high_count,
            result.medium_count,
        )
        return EXIT_SECRETS_FOUND

    if args.fail_on_secrets and result.has_secrets:
        logger.warning(
            "Secrets found (--fail-on-secrets): %d total",
            result.secrets_found,
        )
        return EXIT_SECRETS_FOUND

    # HIGH and MEDIUM findings are warnings only (non-zero exit only for CRITICAL).
    if result.has_secrets:
        # But suppress the warning when the only non-suppressed are MEDIUM
        if result.high_count > 0 or result.critical_count > 0:
            logger.info(
                "Secrets found (non-critical): %d high, %d medium",
                result.high_count,
                result.medium_count,
            )

    logger.info(
        "Scan complete: %d files scanned, no secrets detected.",
        result.files_scanned,
    )
    return EXIT_CLEAN


if __name__ == "__main__":
    sys.exit(main())
