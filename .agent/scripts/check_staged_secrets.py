#!/usr/bin/env python3
"""Block newly staged high-confidence secrets without printing their values."""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

ROOT = Path(__file__).resolve().parents[2]
ALLOWLIST_PATH = ROOT / ".secret-scanner-allowlist.json"
ALLOW_DIRECTIVE = "secret-scan: allow"

HIGH_CONFIDENCE_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    (
        "private-key",
        re.compile(r"-----BEGIN (?:RSA|OPENSSH|EC|DSA|PGP) PRIVATE KEY-----"),
    ),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    (
        "anthropic-api-key",
        re.compile(r"\bsk-ant-[A-Za-z0-9_-]{20,}\b"),
    ),
    (
        "openai-api-key",
        re.compile(r"\bsk-(?:proj-|svcacct-)?[A-Za-z0-9_-]{20,}\b"),
    ),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{30,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b")),
    (
        "telegram-token",
        re.compile(r"(?<!\d)\d{8,12}:[A-Za-z0-9_-]{30,}\b"),
    ),
    (
        "jwt",
        re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b"),
    ),
    (
        "credentialed-url",
        re.compile(r"\b(?:postgres|postgresql|mysql|mongodb|redis)://[^/\s:@]+:[^/\s@]+@"),
    ),
    (
        "bearer-token",
        re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{24,}\b"),
    ),
)

ENV_ASSIGNMENT = re.compile(
    r"^\s*(?P<name>[A-Z][A-Z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|CREDENTIAL|DSN))"
    r"\s*=\s*(?P<value>.+?)\s*$"
)
SOURCE_ASSIGNMENT = re.compile(
    r"""(?ix)
    \b(?:api[_-]?key|token|secret|password|credential)\b
    \s*[:=]\s*
    (?P<quote>["'])(?P<value>[^"']{16,})(?P=quote)
    """
)
HUNK_HEADER = re.compile(r"^@@ -\d+(?:,\d+)? \+(?P<start>\d+)(?:,\d+)? @@")


@dataclass(frozen=True)
class AddedLine:
    path: str
    line_number: int
    text: str


@dataclass(frozen=True)
class Finding:
    path: str
    line_number: int
    rule: str


def load_placeholder_prefixes(path: Path = ALLOWLIST_PATH) -> tuple[str, ...]:
    data = json.loads(path.read_text(encoding="utf-8"))
    prefixes = data.get("placeholderPrefixes", [])
    if not isinstance(prefixes, list) or any(
        not isinstance(prefix, str) or (len(prefix.strip()) < 2 and prefix.strip() != "<")
        for prefix in prefixes
    ):
        raise ValueError("placeholderPrefixes inválido")
    return tuple(prefix.casefold() for prefix in prefixes)


def _normalized_value(value: str) -> str:
    return value.strip().strip("\"'").strip()


def _is_placeholder(value: str, prefixes: Sequence[str]) -> bool:
    normalized = _normalized_value(value).casefold()
    return (
        not normalized
        or normalized in {"none", "null", "undefined"}
        or normalized.startswith(prefixes)
        or normalized.endswith("_here")
    )


def _has_inline_allowance(text: str) -> bool:
    lowered = text.casefold()
    marker_index = lowered.find(ALLOW_DIRECTIVE)
    if marker_index < 0:
        return False
    reason = text[marker_index + len(ALLOW_DIRECTIVE) :].strip(" :[]()-")
    return len(reason) >= 4


def scan_added_lines(
    lines: Iterable[AddedLine],
    placeholder_prefixes: Sequence[str],
) -> list[Finding]:
    findings: list[Finding] = []
    for added in lines:
        if _has_inline_allowance(added.text):
            continue

        matched_rules: set[str] = set()
        for rule, pattern in HIGH_CONFIDENCE_PATTERNS:
            if pattern.search(added.text):
                matched_rules.add(rule)

        env_match = ENV_ASSIGNMENT.match(added.text)
        if env_match and not _is_placeholder(env_match.group("value"), placeholder_prefixes):
            matched_rules.add("dotenv-secret-assignment")

        for source_match in SOURCE_ASSIGNMENT.finditer(added.text):
            if not _is_placeholder(source_match.group("value"), placeholder_prefixes):
                matched_rules.add("source-secret-assignment")

        findings.extend(
            Finding(added.path, added.line_number, rule) for rule in sorted(matched_rules)
        )
    return findings


def parse_staged_diff(diff: str) -> list[AddedLine]:
    path = ""
    next_line = 0
    added: list[AddedLine] = []
    for raw_line in diff.splitlines():
        if raw_line.startswith("+++ b/"):
            path = raw_line[6:]
            continue
        hunk = HUNK_HEADER.match(raw_line)
        if hunk:
            next_line = int(hunk.group("start"))
            continue
        if raw_line.startswith("+") and not raw_line.startswith("+++"):
            added.append(AddedLine(path, next_line, raw_line[1:]))
            next_line += 1
        elif (
            raw_line.startswith("-")
            and not raw_line.startswith("---")
            or raw_line.startswith(("diff --git", "index ", "--- "))
        ):
            continue
        elif next_line:
            next_line += 1
    return added


def staged_diff() -> str:
    git = os.environ.get("GIT_EXECUTABLE") or shutil.which("git")
    if not git and os.environ.get("GIT_EXEC_PATH"):
        git_root = Path(os.environ["GIT_EXEC_PATH"]).resolve().parents[2]
        candidate = git_root / "cmd" / "git.exe"
        if candidate.is_file():
            git = str(candidate)
    if not git:
        raise RuntimeError("Git no está disponible en PATH; configura GIT_EXECUTABLE.")
    result = subprocess.run(
        [
            git,
            "diff",
            "--cached",
            "--unified=0",
            "--no-color",
            "--diff-filter=ACMR",
        ],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if result.returncode != 0:
        raise RuntimeError("No se pudo inspeccionar el diff staged.")
    return result.stdout


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--diff-file",
        type=Path,
        help="Diff de prueba; por defecto inspecciona el índice de Git.",
    )
    args = parser.parse_args(argv)

    try:
        prefixes = load_placeholder_prefixes()
        diff = args.diff_file.read_text(encoding="utf-8") if args.diff_file else staged_diff()
        findings = scan_added_lines(parse_staged_diff(diff), prefixes)
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
        print(f"[secret-guard] ERROR: {error}", file=sys.stderr)
        return 2

    if not findings:
        print("[secret-guard] OK: no se detectaron secretos nuevos staged.")
        return 0

    print(
        "[secret-guard] BLOQUEADO: posibles secretos nuevos. Los valores se mantienen ocultos.",
        file=sys.stderr,
    )
    for finding in findings:
        print(
            f"  {finding.path}:{finding.line_number} [{finding.rule}]",
            file=sys.stderr,
        )
    print(
        "Mueve el valor al keyring/env. Para un falso positivo documentado, "
        "usa 'secret-scan: allow <razón>' en la misma línea.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
