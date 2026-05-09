"""
Log parsing and analysis engine.
Stdlib only — no external dependencies.
"""

import logging
import re
import os
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

from patterns import ErrorPattern, LEVEL_MAP, PATTERNS, PATTERNS_BY_SEVERITY

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class LogMatch:
    """A single matched error in a log line."""

    line_number: int
    line: str
    pattern: ErrorPattern
    timestamp: Optional[str] = None


@dataclass
class ErrorGroup:
    """Deduplicated group of similar errors."""

    group_key: str
    code: str
    severity: str
    description: str
    count: int = 0
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    sample_line: Optional[str] = None
    files: list[str] = field(default_factory=list)

    def add(self, match: LogMatch, filename: str) -> None:
        self.count += 1
        if self.first_seen is None and match.timestamp:
            self.first_seen = match.timestamp
        if match.timestamp:
            self.last_seen = match.timestamp
        if self.sample_line is None:
            self.sample_line = match.line.strip()
        if filename not in self.files:
            self.files.append(filename)


@dataclass
class TimeBurst:
    """A time window with an unusual number of errors."""

    start: str
    end: str
    window_seconds: int
    error_count: int
    severity: str


@dataclass
class AnalysisResult:
    """Complete output of a log analysis run."""

    total_lines: int
    files_scanned: int
    total_errors: int
    health_score: int  # 0-100
    groups: list[ErrorGroup]
    bursts: list[TimeBurst]
    timestamped_matches: list[LogMatch] = field(default_factory=list)
    scan_date: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "scan_date": self.scan_date,
            "total_lines": self.total_lines,
            "files_scanned": self.files_scanned,
            "total_errors": self.total_errors,
            "health_score": self.health_score,
            "groups": [
                {
                    "code": g.code,
                    "severity": g.severity,
                    "description": g.description,
                    "group_key": g.group_key,
                    "count": g.count,
                    "first_seen": g.first_seen,
                    "last_seen": g.last_seen,
                    "sample_line": g.sample_line,
                    "files": g.files,
                }
                for g in self.groups
            ],
            "bursts": [
                {
                    "start": b.start,
                    "end": b.end,
                    "window_seconds": b.window_seconds,
                    "error_count": b.error_count,
                    "severity": b.severity,
                }
                for b in self.bursts
            ],
        }


# ---------------------------------------------------------------------------
# Timestamp extraction
# ---------------------------------------------------------------------------

# Common log timestamp patterns
_TIMESTAMP_RE = re.compile(
    r"""
    (?P<iso>
      \d{4}-\d{2}-\d{2}[T ]
      \d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:?\d{2})?
    )
    |
    (?P<date>
      \d{4}[-/]\d{2}[-/]\d{2}
      \s+
      \d{2}:\d{2}:\d{2}(?:\.\d+)?
    )
    |
    (?P<time>
      \d{2}:\d{2}:\d{2}(?:\.\d+)?
    )
    """,
    re.VERBOSE,
)


def extract_timestamp(line: str) -> Optional[str]:
    """Extract the first timestamp-like string from a log line."""
    m = _TIMESTAMP_RE.search(line)
    if not m:
        return None
    for group in ("iso", "date", "time"):
        if m.group(group):
            return m.group(group)
    return None


# ---------------------------------------------------------------------------
# Log file parsing
# ---------------------------------------------------------------------------

# Severity order for filtering
_SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]


def _min_severity_level(min_severity: str) -> int:
    return _SEVERITY_ORDER.index(min_severity)


def analyze_file(
    path: Path,
    min_severity: str | None = None,
) -> tuple[int, list[LogMatch]]:
    """Parse a single log file and return (total_lines, matches)."""
    try:
        with path.open("r", encoding="utf-8", errors="replace") as fh:
            lines = fh.readlines()
    except OSError as exc:
        logger.warning("Cannot read %s: %s", path, exc)
        return 0, []

    total = len(lines)
    min_level: int | None = None if min_severity is None else _min_severity_level(min_severity)
    matches: list[LogMatch] = []

    for idx, raw in enumerate(lines, start=1):
        line = raw.rstrip("\n")
        for pattern in PATTERNS:
            if min_level is not None and _SEVERITY_ORDER.index(pattern.severity) < min_level:
                continue  # skip patterns BELOW min_severity threshold
            if re.search(pattern.regex, line, re.IGNORECASE):
                matches.append(
                    LogMatch(
                        line_number=idx,
                        line=line,
                        pattern=pattern,
                        timestamp=extract_timestamp(line),
                    )
                )
                break  # one match per line max

    return total, matches


def analyze_directory(
    path: Path,
    min_severity: str | None = None,
) -> tuple[int, list[LogMatch], list[str]]:
    """Recursively scan a directory for .log files.

    Returns:
        (total_lines, all_matches, file_paths_scanned)
    """
    total_lines = 0
    all_matches: list[LogMatch] = []
    files: list[str] = []

    for entry in sorted(path.rglob("*.log")):
        if not entry.is_file():
            continue
        lines, matches = analyze_file(entry, min_severity)
        total_lines += lines
        all_matches.extend(matches)
        files.append(str(entry))

    return total_lines, all_matches, files


# ---------------------------------------------------------------------------
# Deduplication & grouping
# ---------------------------------------------------------------------------

def group_matches(matches: list[LogMatch]) -> list[ErrorGroup]:
    """Group similar matches by group_key, keeping the most severe per group."""
    groups_map: dict[str, ErrorGroup] = {}

    for match in matches:
        key = match.pattern.group_key
        if key not in groups_map:
            groups_map[key] = ErrorGroup(
                group_key=key,
                code=match.pattern.code,
                severity=match.pattern.severity,
                description=match.pattern.description,
            )
        groups_map[key].add(match, "")

    # Sort: CRITICAL first, then by count descending
    groups = list(groups_map.values())
    groups.sort(
        key=lambda g: (-_SEVERITY_ORDER.index(g.severity), -g.count)
    )
    return groups


# ---------------------------------------------------------------------------
# Time burst detection
# ---------------------------------------------------------------------------

_TIMESTAMP_PARSE_FORMATS = [
    "%Y-%m-%dT%H:%M:%S.%f",
    "%Y-%m-%dT%H:%M:%S",
    "%Y-%m-%d %H:%M:%S.%f",
    "%Y-%m-%d %H:%M:%S",
    "%Y/%m/%d %H:%M:%S",
    "%H:%M:%S.%f",
    "%H:%M:%S",
]


def _parse_ts(ts: str) -> Optional[datetime]:
    for fmt in _TIMESTAMP_PARSE_FORMATS:
        try:
            return datetime.strptime(ts[: len(fmt)], fmt)
        except ValueError:
            pass
    return None


def detect_bursts(
    matches: list[LogMatch],
    window_seconds: int = 300,
    threshold: int = 5,
) -> list[TimeBurst]:
    """Detect time windows with abnormally high error density."""
    if not matches:
        return []

    # Collect only matches with parseable timestamps
    stamped = []
    for m in matches:
        if m.timestamp:
            dt = _parse_ts(m.timestamp)
            if dt:
                stamped.append((dt, m.pattern.severity))

    if len(stamped) < threshold:
        return []

    stamped.sort(key=lambda x: x[0])
    bursts: list[TimeBurst] = []

    i = 0
    while i <= len(stamped) - threshold:
        window_start = stamped[i][0]
        j = i + 1
        while j < len(stamped) and (stamped[j][0] - window_start).total_seconds() <= window_seconds:
            j += 1
        count = j - i
        if count >= threshold:
            window_end = stamped[j - 1][0]
            # Pick most severe in window
            severities = [stamped[k][1] for k in range(i, j)]
            top_severity = min(severities, key=lambda s: _SEVERITY_ORDER.index(s))
            bursts.append(
                TimeBurst(
                    start=window_start.isoformat(timespec="seconds"),
                    end=window_end.isoformat(timespec="seconds"),
                    window_seconds=int((window_end - window_start).total_seconds()),
                    error_count=count,
                    severity=top_severity,
                )
            )
            i = j  # skip overlapping window
        else:
            i += 1

    return bursts


# ---------------------------------------------------------------------------
# Health score
# ---------------------------------------------------------------------------

def compute_health_score(groups: list[ErrorGroup], total_lines: int) -> int:
    """Compute a 0-100 health score based on error density and severity."""
    if total_lines == 0:
        return 100

    penalty = 0
    for g in groups:
        weight = {"CRITICAL": 25, "HIGH": 10, "MEDIUM": 4, "LOW": 1}[g.severity]
        penalty += weight * min(g.count, 10)  # cap per-group contribution

    # Normalise: 0 lines with errors = 100; dense errors < 20
    ratio = penalty / max(total_lines / 100, 1)
    score = max(0, min(100, int(100 - ratio)))
    return score


# ---------------------------------------------------------------------------
# Top-N frequency
# ---------------------------------------------------------------------------

def top_frequent(groups: list[ErrorGroup], n: int = 5) -> list[ErrorGroup]:
    return sorted(groups, key=lambda g: -g.count)[:n]


# ---------------------------------------------------------------------------
# Full analysis pipeline
# ---------------------------------------------------------------------------

def run_analysis(
    target: Path,
    min_severity: str | None = None,
    window_seconds: int = 300,
    burst_threshold: int = 5,
) -> AnalysisResult:
    """Run the full analysis pipeline on a file or directory."""
    if target.is_dir():
        total_lines, matches, files = analyze_directory(target, min_severity)
    else:
        lines, matches = analyze_file(target, min_severity)
        total_lines, matches, files = lines, matches, [str(target)]

    groups = group_matches(matches)
    bursts = detect_bursts(matches, window_seconds=window_seconds, threshold=burst_threshold)
    health = compute_health_score(groups, total_lines)

    return AnalysisResult(
        total_lines=total_lines,
        files_scanned=len(files),
        total_errors=len(matches),
        health_score=health,
        groups=groups,
        bursts=bursts,
        timestamped_matches=[m for m in matches if m.timestamp],
    )
