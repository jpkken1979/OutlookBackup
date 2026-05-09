"""Entropy-based secret detection.

Detects high-entropy strings that look like randomly generated secrets
(such as API keys, tokens, or session IDs) using Shannon entropy.
"""

import math
import re
from dataclasses import dataclass


@dataclass
class EntropyMatch:
    """A high-entropy string candidate found in source code."""

    value: str
    entropy: float
    start_index: int
    end_index: int
    line_number: int


# Minimum length for an entropy candidate to be considered a secret.
MIN_LENGTH = 20

# Default Shannon entropy threshold.
DEFAULT_THRESHOLD = 4.5


def shannon_entropy(s: str) -> float:
    """Calculate Shannon entropy of a string.

    Args:
        s: Input string to analyze.

    Returns:
        Entropy value in bits per character. Higher means more random.
    """
    if not s:
        return 0.0
    freq: dict[str, int] = {}
    for ch in s:
        freq[ch] = freq.get(ch, 0) + 1
    entropy = 0.0
    length = len(s)
    for count in freq.values():
        probability = count / length
        entropy -= probability * math.log2(probability)
    return entropy


CANDIDATE_RE = re.compile(
    r"""
    (?:
        # Quoted strings
        ['"`]([A-Za-z0-9_/+=.-]{20,80})['"`]
        |
        # Bare token
        (?:^|[=\s(,;])([A-Za-z0-9_/+=.-]{20,})(?:$|[)\s,;])
    )
    """,
    re.VERBOSE | re.MULTILINE,
)

FALSE_POSITIVE_RE = re.compile(
    r"(?i)"
    r"(?:example|placeholder|dummy|test|fake|mock|sample|"
    r"xxx+|0000+|aaaa+|your_[a-z_]+|replace_me|change_me|"
    r"not_real|invalid|expired|default)",
)


def extract_candidates(content: str) -> list[EntropyMatch]:
    """Extract candidate strings from content that might be secrets.

    Args:
        content: Source file content as a single string.

    Returns:
        List of EntropyMatch objects for high-entropy candidates.
    """
    matches: list[EntropyMatch] = []
    lines = content.split("\n")

    for line_num, line in enumerate(lines, start=1):
        for match in CANDIDATE_RE.finditer(line):
            candidate = match.group(1) or match.group(2)
            if not candidate or len(candidate) < MIN_LENGTH:
                continue
            if FALSE_POSITIVE_RE.search(candidate):
                continue
            entropy = shannon_entropy(candidate)
            if entropy >= DEFAULT_THRESHOLD:
                matches.append(
                    EntropyMatch(
                        value=candidate,
                        entropy=entropy,
                        start_index=match.start(),
                        end_index=match.end(),
                        line_number=line_num,
                    )
                )
    return matches


def has_high_entropy(content: str, threshold: float = DEFAULT_THRESHOLD) -> bool:
    """Quick check if content contains any high-entropy secrets.

    Args:
        content: Source file content.
        threshold: Minimum entropy to flag as suspicious.

    Returns:
        True if any high-entropy secret is found.
    """
    return any(c.entropy >= threshold for c in extract_candidates(content))


def get_high_entropy_strings(
    content: str,
    threshold: float = DEFAULT_THRESHOLD,
) -> list[EntropyMatch]:
    """Get all high-entropy strings above the threshold.

    Args:
        content: Source file content.
        threshold: Minimum entropy to include.

    Returns:
        List of EntropyMatch sorted by entropy descending.
    """
    candidates = extract_candidates(content)
    return sorted(
        [c for c in candidates if c.entropy >= threshold],
        key=lambda c: c.entropy,
        reverse=True,
    )
