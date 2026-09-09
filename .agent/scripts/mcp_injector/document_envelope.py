"""Byte-preserving managed-block updates for injected Markdown and rule files."""

from __future__ import annotations

import codecs
import hashlib
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


class ManagedBlockError(ValueError):
    """Raised when managed markers cannot be updated safely."""


class ConcurrentDocumentChangeError(RuntimeError):
    """Raised when non-managed content changed after a preview."""


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _detect_newline(text: str) -> str:
    crlf = text.find("\r\n")
    lf = text.find("\n")
    cr = text.find("\r")
    candidates = [
        (index, newline)
        for index, newline in ((crlf, "\r\n"), (lf, "\n"), (cr, "\r"))
        if index >= 0
    ]
    return min(candidates, default=(0, "\n"), key=lambda item: item[0])[1]


def _normalize_newlines(text: str, newline: str) -> str:
    return text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", newline)


def _managed_ranges(text: str, start_marker: str, end_marker: str) -> list[tuple[int, int]]:
    if not start_marker or not end_marker or start_marker == end_marker:
        raise ManagedBlockError("managed markers must be distinct non-empty strings")

    ranges: list[tuple[int, int]] = []
    cursor = 0
    while cursor < len(text):
        start = text.find(start_marker, cursor)
        orphan_end = text.find(end_marker, cursor)
        if orphan_end >= 0 and (start < 0 or orphan_end < start):
            raise ManagedBlockError("managed end marker appears without a start marker")
        if start < 0:
            break

        end_start = text.find(end_marker, start + len(start_marker))
        if end_start < 0:
            raise ManagedBlockError("managed start marker has no matching end marker")
        nested_start = text.find(start_marker, start + len(start_marker))
        if nested_start >= 0 and nested_start < end_start:
            raise ManagedBlockError("nested managed blocks are not supported")

        end = end_start + len(end_marker)
        ranges.append((start, end))
        cursor = end
    return ranges


@dataclass(frozen=True)
class DocumentEnvelope:
    """Decoded document plus the exact encoding and newline envelope."""

    raw: bytes = field(repr=False)
    text: str
    encoding: str
    bom: bytes = field(repr=False)
    newline: str
    has_final_newline: bool
    exists: bool = True

    @classmethod
    def read(cls, path: Path) -> DocumentEnvelope:
        if not path.exists():
            return cls(
                raw=b"",
                text="",
                encoding="utf-8",
                bom=b"",
                newline="\n",
                has_final_newline=False,
                exists=False,
            )
        raw = path.read_bytes()
        if raw.startswith(codecs.BOM_UTF8):
            encoding, bom = "utf-8", codecs.BOM_UTF8
        elif raw.startswith(codecs.BOM_UTF16_LE):
            encoding, bom = "utf-16-le", codecs.BOM_UTF16_LE
        elif raw.startswith(codecs.BOM_UTF16_BE):
            encoding, bom = "utf-16-be", codecs.BOM_UTF16_BE
        else:
            encoding, bom = "utf-8", b""

        try:
            text = raw[len(bom) :].decode(encoding)
        except UnicodeDecodeError as exc:
            raise ManagedBlockError(
                f"unsupported or invalid document encoding for {path.name}"
            ) from exc
        return cls(
            raw=raw,
            text=text,
            encoding=encoding,
            bom=bom,
            newline=_detect_newline(text),
            has_final_newline=text.endswith(("\n", "\r")),
            exists=True,
        )

    def encode(self, text: str) -> bytes:
        return self.bom + text.encode(self.encoding)

    def external_bytes(self, start_marker: str, end_marker: str) -> bytes:
        ranges = _managed_ranges(self.text, start_marker, end_marker)
        if not ranges:
            return self.raw

        pieces: list[str] = []
        cursor = 0
        for start, end in ranges:
            pieces.append(self.text[cursor:start])
            cursor = end
        pieces.append(self.text[cursor:])
        return self.encode("".join(pieces))

    def render_managed_block(
        self,
        start_marker: str,
        end_marker: str,
        section: str,
    ) -> bytes:
        normalized = _normalize_newlines(section, self.newline)
        if (
            normalized.count(start_marker) != 1
            or normalized.count(end_marker) != 1
            or not normalized.startswith(start_marker)
            or not normalized.endswith(end_marker)
        ):
            raise ManagedBlockError("managed section must contain exactly one complete marker pair")

        ranges = _managed_ranges(self.text, start_marker, end_marker)
        if not ranges:
            if not self.text:
                rendered = normalized
            else:
                separator = self.newline if self.has_final_newline else self.newline * 2
                rendered = self.text + separator + normalized
            return self.encode(rendered)

        pieces = [self.text[: ranges[0][0]], normalized]
        cursor = ranges[0][1]
        for start, end in ranges[1:]:
            pieces.append(self.text[cursor:start])
            cursor = end
        pieces.append(self.text[cursor:])
        return self.encode("".join(pieces))


@dataclass(frozen=True)
class ManagedBlockPreview:
    path: Path
    start_marker: str
    end_marker: str
    section: str
    envelope: DocumentEnvelope
    original_sha256: str
    external_sha256: str
    updated_bytes: bytes = field(repr=False)
    updated_sha256: str
    changed: bool


def preview_managed_block_update(
    path: Path,
    start_marker: str,
    end_marker: str,
    section: str,
) -> ManagedBlockPreview:
    envelope = DocumentEnvelope.read(path)
    updated = envelope.render_managed_block(start_marker, end_marker, section)
    return ManagedBlockPreview(
        path=path,
        start_marker=start_marker,
        end_marker=end_marker,
        section=section,
        envelope=envelope,
        original_sha256=_sha256(envelope.raw),
        external_sha256=_sha256(envelope.external_bytes(start_marker, end_marker)),
        updated_bytes=updated,
        updated_sha256=_sha256(updated),
        changed=updated != envelope.raw,
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    previous_mode = path.stat().st_mode if path.exists() else None
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{path.name}.",
        suffix=".nexus-tmp",
        dir=path.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        if previous_mode is not None:
            os.chmod(temporary, previous_mode)
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def apply_managed_block_update(preview: ManagedBlockPreview) -> bool:
    current = DocumentEnvelope.read(preview.path)
    current_external_sha256 = _sha256(
        current.external_bytes(preview.start_marker, preview.end_marker)
    )
    if current_external_sha256 != preview.external_sha256:
        raise ConcurrentDocumentChangeError(
            "external content changed after preview; refusing to overwrite"
        )

    updated = current.render_managed_block(
        preview.start_marker,
        preview.end_marker,
        preview.section,
    )
    if updated == current.raw:
        return False
    _atomic_write(preview.path, updated)
    return True


def rollback_managed_block_update(preview: ManagedBlockPreview) -> bool:
    current = DocumentEnvelope.read(preview.path)
    if _sha256(current.raw) != preview.updated_sha256:
        raise ConcurrentDocumentChangeError("document changed after apply; refusing to roll back")
    if current.raw == preview.envelope.raw and current.exists == preview.envelope.exists:
        return False
    if preview.envelope.exists:
        _atomic_write(preview.path, preview.envelope.raw)
    else:
        preview.path.unlink(missing_ok=True)
    return True
