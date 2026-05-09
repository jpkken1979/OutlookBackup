"""BrainTracker — recall pre-op + ingest post-op against Brain Network.

Implements policy B from the design spec:
    - Errors with stack → ingest pattern (importance=high)
    - New templates discovered → ingest pattern (importance=medium)
    - Session close with N ops → ingest session (importance=low)
    - Recall before write/automate ops to retrieve relevant patterns
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


# Mapping of canonical domain tags → regex patterns.
DOMAIN_PATTERNS: dict[str, list[str]] = {
    "kobetsu": [r"kobetsu", r"個別契約", r"個別"],
    "haken": [r"haken", r"派遣"],
    "kintai": [r"kintai", r"勤怠"],
    "rirekisho": [r"rirekisho", r"履歴書"],
    "chingi": [r"chingi", r"賃金"],
    "yukyu": [r"yukyu", r"有給"],
    "uns-dispatch": [r"uns[\W_]?dispatch", r"派遣業"],
}

MAX_CONTEXT_BYTES = 4 * 1024


def infer_content_tags(path: str, sample_content: str) -> list[str]:
    """Infer canonical domain tags from the path + content sample.

    Args:
        path: File path to inspect for domain keywords.
        sample_content: Optional content sample (first 2000 chars used).

    Returns:
        Deterministic alphabetically-sorted list of canonical tags matched.
    """
    haystack = (path + " " + (sample_content or "")[:2000]).lower()
    matches: set[str] = set()
    for tag, patterns in DOMAIN_PATTERNS.items():
        if any(re.search(p, haystack, re.IGNORECASE) for p in patterns):
            matches.add(tag)
    return sorted(matches)


@dataclass
class BrainHint:
    """A recalled Brain node turned into a hint for the backend."""

    node_id: str
    title: str
    snippet: str
    tags: tuple[str, ...]
    importance: str


class BrainTracker:
    """Tracks Excel operations into the Brain Network.

    Provides recall (pre-op) and ingest (post-op) integration with the
    Brain Network to accumulate knowledge about Excel files and operations.
    """

    def __init__(self, brain: Any) -> None:  # Brain type imported by callers
        self._brain = brain

    def recall(
        self,
        op: str,
        path: str,
        op_args: dict[str, Any],
    ) -> list[BrainHint]:
        """Query the Brain for relevant prior knowledge before executing an op.

        Strategy: query("op stem keywords") with limit=10, then filter locally
        by tag overlap with the inferred content tags. Pure-read ops are skipped.

        Args:
            op: Operation name (e.g. "write_range", "create_pivot").
            path: Path to the Excel file being operated on.
            op_args: Additional operation arguments for query enrichment.

        Returns:
            Up to 3 BrainHint objects with relevant prior knowledge.
        """
        if op in {"parse_smart", "read_range", "list_sessions"}:
            # No recall on pure-read ops; super-agent has its own intelligence.
            return []

        tags = ["excel", *infer_content_tags(path, sample_content="")]
        query_str = self._build_query(op, path, op_args)

        try:
            results = self._brain.query(query_str, limit=10)
        except Exception as exc:
            logger.warning("[brain] recall failed: %s", exc)
            return []

        # Filter: keep only nodes whose tags overlap our inferred tags.
        hints: list[BrainHint] = []
        for node in results:
            node_tags = set(getattr(node, "tags", []))
            if not node_tags & set(tags):
                continue
            if getattr(node, "importance", "normal") == "low":
                continue
            hints.append(
                BrainHint(
                    node_id=getattr(node, "slug", ""),
                    title=getattr(node, "title", ""),
                    snippet=getattr(node, "context", "")[:500],
                    tags=tuple(node_tags),
                    importance=getattr(node, "importance", "normal"),
                )
            )
            if len(hints) >= 3:
                break
        return hints

    def ingest_error(
        self,
        *,
        op: str,
        path: str,
        backend_used: str,
        error_code: str,
        error_message: str,
        next_action: str | None,
        request_id: str,
        backend_message: str | None = None,
    ) -> Any:
        """Ingest an error as Plantilla A (pattern, importance=high).

        Args:
            op: Operation that failed.
            path: Path to the Excel file.
            backend_used: Backend that raised the error (e.g. "openpyxl").
            error_code: Canonical error code from ErrorCatalog.
            error_message: Human-readable error message.
            next_action: Suggested recovery action, if any.
            request_id: Correlation ID for the original request.
            backend_message: Raw message from the backend, if available.

        Returns:
            The ingested BrainNode.
        """
        tags = ["excel", "error", backend_used, *infer_content_tags(path, "")]
        title = f"excel.{op}: {self._truncate(error_code, 60)}"
        context = self._truncate(
            f"Operación: {op}\n"
            f"Backend: {backend_used}\n"
            f"Archivo: {Path(path).name}\n"
            f"Error code: {error_code}\n"
            f"Error: {error_message}\n"
            f"Backend message: {backend_message or 'N/A'}\n"
            f"Fix sugerido: {next_action or 'N/A'}\n",
            MAX_CONTEXT_BYTES,
        )
        return self._brain.ingest(
            title=title,
            context=context,
            area="excel",
            tags=tags,
            node_type="pattern",
            importance="high",
            source_notes=f"excel-engine:{request_id}",
        )

    def ingest_template(
        self,
        *,
        kind: str,
        path: str,
        header_row: int,
        data_range: str,
        sheets: list[str],
        col_formats: dict[str, str],
        encoding: str,
        request_id: str,
    ) -> Any:
        """Ingest a discovered template as Plantilla B (pattern, importance=medium).

        Args:
            kind: Template kind (e.g. "kobetsu", "kintai").
            path: Path to the Excel file.
            header_row: Row number where headers are located.
            data_range: Excel range notation for the data area.
            sheets: List of sheet names in the workbook.
            col_formats: Mapping of column ranges to Excel number formats.
            encoding: File encoding detected.
            request_id: Correlation ID for the original request.

        Returns:
            The ingested BrainNode.
        """
        filename = Path(path).stem
        tags = ["excel", "template", kind, *infer_content_tags(path, "")]
        title = f"excel.template.{kind}: {filename}"
        context = self._truncate(
            f"Tipo: {kind}\n"
            f"Archivo: {filename}\n"
            f"Layout:\n"
            f"  - Headers row: {header_row}\n"
            f"  - Data range: {data_range}\n"
            f"  - Sheets: {', '.join(sheets)}\n"
            f"  - Col formats: {col_formats}\n"
            f"Encoding: {encoding}\n",
            MAX_CONTEXT_BYTES,
        )
        # Spec: importance="medium". Brain API normaliza "medium" -> "normal"
        # internamente al persistir; consumidores que filtran por importance
        # deben aceptar ambos valores como equivalentes para Plantilla B.
        return self._brain.ingest(
            title=title,
            context=context,
            area="excel",
            tags=tags,
            node_type="pattern",
            importance="medium",
            source_notes=f"excel-engine:{request_id}:template-discovered",
        )

    def ingest_session(
        self,
        *,
        path: str,
        opened_at: float,
        closed_at: float,
        n_ops: int,
        op_breakdown: dict[str, int],
        backends_used: list[str],
        n_errors: int,
        request_id: str,
    ) -> Any:
        """Ingest a session summary as Plantilla D (session, importance=low).

        Args:
            path: Path to the Excel file operated on.
            opened_at: Unix timestamp when the session was opened.
            closed_at: Unix timestamp when the session was closed.
            n_ops: Total number of operations performed.
            op_breakdown: Dict mapping op type to count.
            backends_used: List of backend names used in the session.
            n_errors: Number of errors that occurred.
            request_id: Correlation ID for the original request.

        Returns:
            The ingested BrainNode.
        """
        filename = Path(path).name
        duration = int(closed_at - opened_at)
        tags = ["excel", "session", *infer_content_tags(path, "")]
        title = f"excel.session: {filename} — {n_ops} ops, {duration}s"
        breakdown_str = ", ".join(f"{k}={v}" for k, v in sorted(op_breakdown.items()))
        context = self._truncate(
            f"Archivo: {filename}\n"
            f"Apertura: {opened_at}\n"
            f"Cierre: {closed_at} (duración {duration}s)\n"
            f"Operaciones: {n_ops} ({breakdown_str})\n"
            f"Backends: {', '.join(backends_used)}\n"
            f"Errores: {n_errors}\n",
            MAX_CONTEXT_BYTES,
        )
        return self._brain.ingest(
            title=title,
            context=context,
            area="excel",
            tags=tags,
            node_type="session",
            importance="low",
            source_notes=f"excel-engine:{request_id}:session-close",
        )

    @staticmethod
    def _build_query(op: str, path: str, op_args: dict[str, Any]) -> str:
        """Build a Brain query string from op context.

        Args:
            op: Operation name.
            path: File path (stem used).
            op_args: Additional operation arguments.

        Returns:
            Query string truncated to 200 chars.
        """
        keywords: list[str] = [op, Path(path).stem]
        for key, val in op_args.items():
            if isinstance(val, str):
                keywords.append(val)
        return " ".join(keywords)[:200]

    @staticmethod
    def _truncate(text: str, max_bytes: int) -> str:
        """Truncate text to fit within max_bytes when UTF-8 encoded.

        Args:
            text: Input text to truncate.
            max_bytes: Maximum byte size of the output.

        Returns:
            Truncated text with "[...truncated]" suffix if truncation occurred.
        """
        if len(text.encode("utf-8")) <= max_bytes:
            return text
        truncated = text
        while len(truncated.encode("utf-8")) > max_bytes:
            truncated = truncated[: int(len(truncated) * 0.9)]
        return truncated + "\n[...truncated]"
