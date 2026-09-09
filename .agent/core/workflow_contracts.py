"""Typed, fail-closed contracts shared by quality-gate workflows.

The workflow engine persists these values and Nexus renders them.  Keep the
contract deliberately small: evidence is summarized, paths are workspace
relative, and secret-looking values are redacted before they reach events or
checkpoints.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import PurePosixPath
from typing import Any

MAX_FINDINGS = 200
MAX_EVIDENCE = 100
MAX_TEXT = 4_000
MAX_ARTIFACTS = 40

_SECRET_PATTERNS = (
    re.compile(r"(?i)\b(bearer)\s+[a-z0-9._~+/=-]{8,}"),
    re.compile(
        r"(?i)\b(api[_-]?key|token|password|secret)\b"
        r"(\s*[:=]\s*)[\"']?[^\s,\"']{6,}"
    ),
    re.compile(r"\b(sk-[A-Za-z0-9_-]{8,})\b"),
    re.compile(r"\b(gh[oprsu]_[A-Za-z0-9]{8,})\b"),
)


class GateVerdict(str, Enum):
    """Closed set of outcomes understood by the router and UI."""

    PASS = "PASS"
    FAIL = "FAIL"
    NEEDS_INPUT = "NEEDS_INPUT"
    SKIPPED = "SKIPPED"


class FindingSeverity(str, Enum):
    INFO = "info"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


def redact_text(value: str, *, max_length: int = MAX_TEXT) -> str:
    """Remove common credentials and bound persisted/rendered text."""

    cleaned = value.replace("\x00", "").replace("\r\n", "\n")
    for pattern in _SECRET_PATTERNS:
        cleaned = pattern.sub(lambda match: f"{match.group(1)} [REDACTED]", cleaned)
    if len(cleaned) > max_length:
        return f"{cleaned[:max_length]}…[truncated]"
    return cleaned


def redact_value(value: Any, *, depth: int = 0) -> Any:
    """Recursively redact event/checkpoint payloads with bounded depth."""

    if depth > 8:
        return "[REDACTED:depth]"
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for index, (key, item) in enumerate(value.items()):
            if index >= 200:
                result["__truncated__"] = True
                break
            safe_key = redact_text(str(key), max_length=128)
            sensitive_key = any(
                marker in safe_key.lower() for marker in ("token", "secret", "password", "api_key")
            )
            if sensitive_key and not (item is None or isinstance(item, (bool, int, float))):
                result[safe_key] = "[REDACTED]"
            else:
                result[safe_key] = redact_value(item, depth=depth + 1)
        return result
    if isinstance(value, (list, tuple)):
        return [redact_value(item, depth=depth + 1) for item in value[:200]]
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return redact_text(str(value))


def validate_relative_path(value: str, *, label: str = "path") -> str:
    """Validate a normalized workspace-relative path without filesystem access."""

    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    normalized = value.strip().replace("\\", "/")
    path = PurePosixPath(normalized)
    if (
        not normalized
        or len(normalized) > 512
        or path.is_absolute()
        or ":" in path.parts[0]
        or any(part in ("", ".", "..") for part in path.parts)
        or any(ord(character) < 32 for character in normalized)
    ):
        raise ValueError(f"{label} must be a safe workspace-relative path")
    return str(path)


def _bounded_text(value: Any, label: str, *, required: bool = True) -> str:
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a string")
    cleaned = redact_text(value.strip())
    if required and not cleaned:
        raise ValueError(f"{label} is required")
    return cleaned


@dataclass(frozen=True)
class GateFinding:
    """One actionable, source-attributed gate finding."""

    category: str
    severity: FindingSeverity
    message: str
    remediation: str = ""
    file: str | None = None
    line: int | None = None
    provenance: tuple[str, ...] = ()

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> GateFinding:
        if not isinstance(payload, dict):
            raise ValueError("finding must be an object")
        allowed = {
            "category",
            "severity",
            "message",
            "remediation",
            "file",
            "line",
            "provenance",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"unknown finding fields: {', '.join(sorted(unknown))}")
        raw_file = payload.get("file")
        file_path = validate_relative_path(raw_file, label="finding.file") if raw_file else None
        raw_line = payload.get("line")
        if raw_line is not None and (
            not isinstance(raw_line, int)
            or isinstance(raw_line, bool)
            or not 1 <= raw_line <= 10_000_000
        ):
            raise ValueError("finding.line must be a positive integer")
        raw_provenance = payload.get("provenance", [])
        if not isinstance(raw_provenance, (list, tuple)) or len(raw_provenance) > 20:
            raise ValueError("finding.provenance must be a bounded list")
        return cls(
            category=_bounded_text(payload.get("category"), "finding.category"),
            severity=FindingSeverity(payload.get("severity", "")),
            message=_bounded_text(payload.get("message"), "finding.message"),
            remediation=_bounded_text(
                payload.get("remediation", ""),
                "finding.remediation",
                required=False,
            ),
            file=file_path,
            line=raw_line,
            provenance=tuple(_bounded_text(item, "finding.provenance") for item in raw_provenance),
        )

    def fingerprint(self) -> str:
        location = f"{self.file or ''}:{self.line or 0}"
        return "|".join(
            (
                self.category.casefold(),
                self.severity.value,
                location.casefold(),
                " ".join(self.message.casefold().split()),
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "severity": self.severity.value,
            "message": self.message,
            "remediation": self.remediation,
            "file": self.file,
            "line": self.line,
            "provenance": list(self.provenance),
        }


@dataclass(frozen=True)
class GateEvidence:
    """Bounded evidence reference; never raw logs or binary blobs."""

    command: str
    exit_code: int | None
    summary: str
    artifact_refs: tuple[str, ...] = ()
    duration_ms: int | None = None

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> GateEvidence:
        if not isinstance(payload, dict):
            raise ValueError("evidence must be an object")
        allowed = {"command", "exit_code", "summary", "artifact_refs", "duration_ms"}
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"unknown evidence fields: {', '.join(sorted(unknown))}")
        exit_code = payload.get("exit_code")
        if exit_code is not None and (
            not isinstance(exit_code, int)
            or isinstance(exit_code, bool)
            or not -255 <= exit_code <= 255
        ):
            raise ValueError("evidence.exit_code must be a bounded integer")
        duration_ms = payload.get("duration_ms")
        if duration_ms is not None and (
            not isinstance(duration_ms, int)
            or isinstance(duration_ms, bool)
            or not 0 <= duration_ms <= 86_400_000
        ):
            raise ValueError("evidence.duration_ms must be a bounded integer")
        refs = payload.get("artifact_refs", [])
        if not isinstance(refs, (list, tuple)) or len(refs) > MAX_ARTIFACTS:
            raise ValueError("evidence.artifact_refs must be a bounded list")
        return cls(
            command=_bounded_text(payload.get("command"), "evidence.command"),
            exit_code=exit_code,
            summary=_bounded_text(payload.get("summary"), "evidence.summary"),
            artifact_refs=tuple(
                validate_relative_path(item, label="evidence.artifact_ref") for item in refs
            ),
            duration_ms=duration_ms,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "command": self.command,
            "exit_code": self.exit_code,
            "summary": self.summary,
            "artifact_refs": list(self.artifact_refs),
            "duration_ms": self.duration_ms,
        }


@dataclass(frozen=True)
class GateResult:
    """Canonical state passed between quality nodes and rendered by Nexus."""

    verdict: GateVerdict
    findings: tuple[GateFinding, ...] = ()
    evidence: tuple[GateEvidence, ...] = ()
    next_action: str = ""
    summary: str = ""
    attempt: int = 1
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> GateResult:
        if not isinstance(payload, dict):
            raise ValueError("gate_result must be an object")
        allowed = {
            "verdict",
            "findings",
            "evidence",
            "next_action",
            "summary",
            "attempt",
            "metadata",
        }
        unknown = set(payload) - allowed
        if unknown:
            raise ValueError(f"unknown gate result fields: {', '.join(sorted(unknown))}")
        findings = payload.get("findings", [])
        evidence = payload.get("evidence", [])
        if not isinstance(findings, list) or len(findings) > MAX_FINDINGS:
            raise ValueError("gate_result.findings exceeds the limit")
        if not isinstance(evidence, list) or len(evidence) > MAX_EVIDENCE:
            raise ValueError("gate_result.evidence exceeds the limit")
        attempt = payload.get("attempt", 1)
        if not isinstance(attempt, int) or isinstance(attempt, bool) or not 1 <= attempt <= 10:
            raise ValueError("gate_result.attempt must be between 1 and 10")
        metadata = payload.get("metadata", {})
        if not isinstance(metadata, dict):
            raise ValueError("gate_result.metadata must be an object")
        return cls(
            verdict=GateVerdict(payload.get("verdict", "")),
            findings=tuple(GateFinding.from_dict(item) for item in findings),
            evidence=tuple(GateEvidence.from_dict(item) for item in evidence),
            next_action=_bounded_text(
                payload.get("next_action", ""),
                "gate_result.next_action",
                required=False,
            ),
            summary=_bounded_text(
                payload.get("summary", ""),
                "gate_result.summary",
                required=False,
            ),
            attempt=attempt,
            metadata=redact_value(metadata),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "findings": [finding.to_dict() for finding in self.findings],
            "evidence": [item.to_dict() for item in self.evidence],
            "next_action": self.next_action,
            "summary": self.summary,
            "attempt": self.attempt,
            "metadata": redact_value(self.metadata),
        }


def merge_findings(findings: list[GateFinding]) -> tuple[GateFinding, ...]:
    """Deduplicate exact findings while preserving every reviewer provenance."""

    merged: dict[str, GateFinding] = {}
    for finding in findings[:MAX_FINDINGS]:
        fingerprint = finding.fingerprint()
        existing = merged.get(fingerprint)
        if existing is None:
            merged[fingerprint] = finding
            continue
        provenance = tuple(dict.fromkeys((*existing.provenance, *finding.provenance)))
        merged[fingerprint] = GateFinding(
            category=existing.category,
            severity=existing.severity,
            message=existing.message,
            remediation=existing.remediation or finding.remediation,
            file=existing.file,
            line=existing.line,
            provenance=provenance,
        )
    return tuple(merged.values())
