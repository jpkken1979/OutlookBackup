# mypy: ignore-errors
#!/usr/bin/env python3
"""
Context Compression - Smart compression of long contexts.

This module provides intelligent context compression that:
1. Identifies important vs redundant information
2. Summarizes long contexts while preserving key details
3. Prioritizes recent and relevant information
4. Maintains semantic coherence
5. Tracks compression quality

Usage:
    from .agent.core.intelligence import ContextCompressor, compress_context

    compressor = ContextCompressor()

    # Compress a long context
    compressed = await compressor.compress(
        context=long_conversation_history,
        max_tokens=4000,
        preserve_recent=True
    )

    print(f"Compressed from {compressed.original_tokens} to {compressed.compressed_tokens} tokens")
"""

import hashlib
import logging
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.intelligence.context_compression")


class ContentType(Enum):
    """Types of content in context."""

    CODE = "code"
    CONVERSATION = "conversation"
    DOCUMENTATION = "documentation"
    ERROR = "error"
    DECISION = "decision"
    ACTION = "action"
    RESULT = "result"
    METADATA = "metadata"


class ImportanceLevel(Enum):
    """Importance levels for content."""

    CRITICAL = "critical"  # Must preserve
    HIGH = "high"  # Should preserve
    MEDIUM = "medium"  # Can summarize
    LOW = "low"  # Can remove
    REDUNDANT = "redundant"  # Should remove


@dataclass
class ContentSegment:
    """A segment of content to evaluate."""

    content: str
    content_type: ContentType
    importance: ImportanceLevel
    timestamp: datetime | None = None
    tokens: int = 0
    summary: str | None = None
    preserve: bool = False
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "content_type": self.content_type.value,
            "importance": self.importance.value,
            "tokens": self.tokens,
            "preserve": self.preserve,
            "reason": self.reason,
        }


@dataclass
class CompressionResult:
    """Result of context compression."""

    compressed_content: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    segments_preserved: int
    segments_summarized: int
    segments_removed: int
    quality_score: float
    key_information_preserved: list[str]
    information_lost: list[str]
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_tokens": self.original_tokens,
            "compressed_tokens": self.compressed_tokens,
            "compression_ratio": self.compression_ratio,
            "segments_preserved": self.segments_preserved,
            "segments_summarized": self.segments_summarized,
            "segments_removed": self.segments_removed,
            "quality_score": self.quality_score,
            "key_information_preserved": self.key_information_preserved,
            "information_lost": self.information_lost,
        }


class TokenEstimator:
    """Estimates token counts for text."""

    # Average characters per token (approximate for GPT-style tokenizers)
    CHARS_PER_TOKEN = 4

    def estimate(self, text: str) -> int:
        """Estimate token count for text."""
        if not text:
            return 0
        # Simple estimation based on character count
        # More accurate would use actual tokenizer
        return max(1, len(text) // self.CHARS_PER_TOKEN)

    def estimate_from_words(self, word_count: int) -> int:
        """Estimate tokens from word count."""
        # Average ~1.3 tokens per word
        return int(word_count * 1.3)


class ContentAnalyzer:
    """Analyzes content to determine importance and type."""

    def __init__(self):
        self.token_estimator = TokenEstimator()

    def analyze(self, content: str, context: dict[str, Any] = None) -> ContentSegment:
        """
        Analyze content segment.

        Args:
            content: The content to analyze
            context: Additional context (e.g., is_recent, is_error)

        Returns:
            ContentSegment with analysis results
        """
        context = context or {}

        # Detect content type
        content_type = self._detect_type(content)

        # Calculate importance
        importance = self._calculate_importance(content, content_type, context)

        # Estimate tokens
        tokens = self.token_estimator.estimate(content)

        # Determine if should preserve
        preserve, reason = self._should_preserve(content, content_type, importance, context)

        return ContentSegment(
            content=content,
            content_type=content_type,
            importance=importance,
            timestamp=context.get("timestamp"),
            tokens=tokens,
            preserve=preserve,
            reason=reason,
        )

    def _detect_type(self, content: str) -> ContentType:
        """Detect the type of content."""
        content_lower = content.lower()

        # Code detection
        code_patterns = [
            r"```",
            r"def\s+\w+\(",
            r"class\s+\w+",
            r"function\s+\w+",
            r"import\s+\w+",
            r"const\s+\w+\s*=",
            r"let\s+\w+\s*=",
        ]
        if any(re.search(p, content) for p in code_patterns):
            return ContentType.CODE

        # Error detection
        error_patterns = ["error", "exception", "failed", "traceback", "stack trace"]
        if any(p in content_lower for p in error_patterns):
            return ContentType.ERROR

        # Decision detection
        decision_patterns = ["decided", "chosen", "selected", "will use", "going with"]
        if any(p in content_lower for p in decision_patterns):
            return ContentType.DECISION

        # Action detection
        action_patterns = ["created", "updated", "deleted", "modified", "executed"]
        if any(p in content_lower for p in action_patterns):
            return ContentType.ACTION

        # Result detection
        result_patterns = ["result:", "output:", "returns", "completed", "finished"]
        if any(p in content_lower for p in result_patterns):
            return ContentType.RESULT

        # Documentation detection
        doc_patterns = ["##", "###", "documentation", "readme", "guide"]
        if any(p in content_lower for p in doc_patterns):
            return ContentType.DOCUMENTATION

        # Default to conversation
        return ContentType.CONVERSATION

    def _calculate_importance(
        self,
        content: str,
        content_type: ContentType,
        context: dict[str, Any],
    ) -> ImportanceLevel:
        """Calculate importance of content."""
        # Type-based base importance
        type_importance = {
            ContentType.ERROR: ImportanceLevel.CRITICAL,
            ContentType.DECISION: ImportanceLevel.HIGH,
            ContentType.CODE: ImportanceLevel.HIGH,
            ContentType.ACTION: ImportanceLevel.MEDIUM,
            ContentType.RESULT: ImportanceLevel.MEDIUM,
            ContentType.DOCUMENTATION: ImportanceLevel.MEDIUM,
            ContentType.CONVERSATION: ImportanceLevel.LOW,
            ContentType.METADATA: ImportanceLevel.LOW,
        }
        base = type_importance.get(content_type, ImportanceLevel.MEDIUM)

        # Context-based adjustments
        if context.get("is_recent", False):
            # Bump up importance for recent content
            if base == ImportanceLevel.LOW:
                base = ImportanceLevel.MEDIUM
            elif base == ImportanceLevel.MEDIUM:
                base = ImportanceLevel.HIGH

        if context.get("is_critical", False):
            base = ImportanceLevel.CRITICAL

        if context.get("is_redundant", False):
            base = ImportanceLevel.REDUNDANT

        # Content-based adjustments
        if self._is_redundant(content, context):
            return ImportanceLevel.REDUNDANT

        return base

    def _is_redundant(self, content: str, context: dict[str, Any]) -> bool:
        """Check if content is redundant."""
        # Check for common filler phrases
        filler_patterns = [
            r"^(ok|okay|sure|yes|no|alright|got it|understood)$",
            r"^(let me|i will|i'll|going to)\s",
            r"^(thanks|thank you|please)$",
        ]
        content_lower = content.lower().strip()
        if any(re.match(p, content_lower) for p in filler_patterns):
            return True

        # Check content hash against seen content
        seen_hashes = context.get("seen_hashes", set())
        content_hash = hashlib.md5(content.encode(), usedforsecurity=False).hexdigest()[:8]
        return content_hash in seen_hashes

    def _should_preserve(
        self,
        content: str,
        content_type: ContentType,
        importance: ImportanceLevel,
        context: dict[str, Any],
    ) -> tuple[bool, str]:
        """Determine if content should be preserved."""
        if importance == ImportanceLevel.CRITICAL:
            return True, "Critical importance"

        if importance == ImportanceLevel.REDUNDANT:
            return False, "Redundant content"

        if content_type == ContentType.ERROR:
            return True, "Error information must be preserved"

        if content_type == ContentType.DECISION:
            return True, "Decision record"

        if context.get("is_recent", False) and importance != ImportanceLevel.LOW:
            return True, "Recent and relevant"

        if content_type == ContentType.CODE:
            # Check if code is referenced later
            if context.get("is_referenced", False):
                return True, "Referenced code"
            return importance in [ImportanceLevel.CRITICAL, ImportanceLevel.HIGH], "Code block"

        return importance in [
            ImportanceLevel.CRITICAL,
            ImportanceLevel.HIGH,
        ], f"Importance: {importance.value}"


class Summarizer:
    """Summarizes content while preserving key information."""

    def summarize(
        self,
        content: str,
        content_type: ContentType,
        max_length: int = 100,
    ) -> str:
        """
        Summarize content.

        Args:
            content: Content to summarize
            content_type: Type of content
            max_length: Maximum length in characters

        Returns:
            Summarized content
        """
        if len(content) <= max_length:
            return content

        if content_type == ContentType.CODE:
            return self._summarize_code(content, max_length)
        elif content_type == ContentType.ERROR:
            return self._summarize_error(content, max_length)
        elif content_type == ContentType.CONVERSATION:
            return self._summarize_conversation(content, max_length)
        else:
            return self._summarize_generic(content, max_length)

    def _summarize_code(self, content: str, max_length: int) -> str:
        """Summarize code block."""
        lines = content.split("\n")

        # Extract key parts: imports, function/class definitions
        key_parts = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith(("import ", "from ", "def ", "class ", "function ")):
                key_parts.append(stripped[:80])
            elif stripped.startswith(("#", "//", "/*")):
                # Keep comments that look like documentation
                if len(stripped) > 10:
                    key_parts.append(stripped[:60])

        if key_parts:
            summary = "[Code] " + "; ".join(key_parts[:5])
        else:
            # Just take first and last lines
            summary = f"[Code block: {len(lines)} lines] {lines[0][:40]}..."

        return summary[:max_length]

    def _summarize_error(self, content: str, max_length: int) -> str:
        """Summarize error message."""
        lines = content.split("\n")

        # Find the actual error message
        error_line = None
        for line in lines:
            if "error" in line.lower() or "exception" in line.lower():
                error_line = line.strip()
                break

        if error_line:
            return f"[Error] {error_line}"[:max_length]

        # Take first substantive line
        for line in lines:
            if len(line.strip()) > 20:
                return f"[Error] {line.strip()}"[:max_length]

        return f"[Error occurred: {len(lines)} lines]"[:max_length]

    def _summarize_conversation(self, content: str, max_length: int) -> str:
        """Summarize conversation."""
        # Extract key sentences
        sentences = re.split(r"[.!?]+", content)
        key_sentences = []

        # Keep sentences with important keywords
        important_keywords = [
            "need",
            "want",
            "should",
            "must",
            "important",
            "create",
            "build",
            "fix",
            "update",
            "change",
            "problem",
            "issue",
            "error",
            "bug",
        ]

        for sentence in sentences:
            sentence = sentence.strip()
            if len(sentence) > 20:
                if any(kw in sentence.lower() for kw in important_keywords):
                    key_sentences.append(sentence)

        if key_sentences:
            return "; ".join(key_sentences[:3])[:max_length]

        # Just truncate
        return content[: max_length - 3] + "..."

    def _summarize_generic(self, content: str, max_length: int) -> str:
        """Generic summarization."""
        # Extract first sentence
        sentences = re.split(r"[.!?]+", content)
        if sentences:
            first = sentences[0].strip()
            if len(first) <= max_length:
                return first
            return first[: max_length - 3] + "..."
        return content[: max_length - 3] + "..."


class ContextCompressor:
    """
    Compresses context while preserving important information.

    This class:
    1. Segments context into logical parts
    2. Analyzes importance of each segment
    3. Preserves critical information
    4. Summarizes or removes less important content
    5. Maintains coherence
    """

    DEFAULT_MAX_TOKENS = 4000
    PRESERVE_RECENT_COUNT = 5  # Always preserve last N items

    def __init__(self, memory_dir: Path | None = None):
        # 3-tier resolution: explicit param > env var > user home (NO repo path)
        # Ver .claude/memory/bugfix_user_model_json_dirty_after_tests.md
        if memory_dir:
            self.memory_dir = Path(memory_dir)
        elif os.environ.get("ANTIGRAVITY_COMPRESSION_PATH"):
            self.memory_dir = Path(os.environ["ANTIGRAVITY_COMPRESSION_PATH"])
        else:
            self.memory_dir = Path.home() / ".antigravity" / "memory" / "compression"
        self.memory_dir.mkdir(parents=True, exist_ok=True)

        self.analyzer = ContentAnalyzer()
        self.summarizer = Summarizer()
        self.token_estimator = TokenEstimator()

    async def compress(
        self,
        context: str,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        preserve_recent: bool = True,
        preserve_types: list[ContentType] | None = None,
    ) -> CompressionResult:
        """
        Compress context to fit within token limit.

        Args:
            context: The context to compress
            max_tokens: Maximum tokens for result
            preserve_recent: Whether to always preserve recent content
            preserve_types: Content types to always preserve

        Returns:
            CompressionResult with compressed content
        """
        preserve_types = preserve_types or [ContentType.ERROR, ContentType.DECISION]

        original_tokens = self.token_estimator.estimate(context)

        if original_tokens <= max_tokens:
            return CompressionResult(
                compressed_content=context,
                original_tokens=original_tokens,
                compressed_tokens=original_tokens,
                compression_ratio=1.0,
                segments_preserved=1,
                segments_summarized=0,
                segments_removed=0,
                quality_score=1.0,
                key_information_preserved=["All content preserved (under limit)"],
                information_lost=[],
            )

        logger.info(f"Compressing context from {original_tokens} tokens to {max_tokens}")

        # Segment the context
        segments = self._segment_context(context)

        # Analyze each segment
        seen_hashes = set()
        analyzed_segments = []
        for i, seg in enumerate(segments):
            is_recent = preserve_recent and i >= len(segments) - self.PRESERVE_RECENT_COUNT
            segment = self.analyzer.analyze(
                seg,
                context={
                    "is_recent": is_recent,
                    "seen_hashes": seen_hashes,
                    "position": i,
                    "total": len(segments),
                },
            )
            analyzed_segments.append(segment)
            seen_hashes.add(hashlib.md5(seg.encode(), usedforsecurity=False).hexdigest()[:8])

        # Force preserve certain types
        for seg in analyzed_segments:
            if seg.content_type in preserve_types:
                seg.preserve = True
                seg.reason = f"Type {seg.content_type.value} always preserved"

        # Sort by importance for selection
        sorted_segments = sorted(
            analyzed_segments,
            key=lambda s: (
                s.preserve,  # Preserved first
                self._importance_rank(s.importance),  # Then by importance
                -analyzed_segments.index(s),  # Then by recency (later is better)
            ),
            reverse=True,
        )

        # Select segments to fit token budget
        selected, summarized, removed = self._select_segments(
            sorted_segments,
            max_tokens,
        )

        # Rebuild compressed context
        compressed_content = self._rebuild_context(
            selected,
            summarized,
            analyzed_segments,  # Original order
        )

        compressed_tokens = self.token_estimator.estimate(compressed_content)

        # Calculate quality
        quality_score = self._calculate_quality(
            selected,
            summarized,
            removed,
            analyzed_segments,
        )

        # Track preserved/lost information
        key_preserved = [f"{s.content_type.value}: {s.content[:50]}..." for s in selected[:5]]
        info_lost = [f"{s.content_type.value}: {s.content[:30]}..." for s in removed[:3]]

        return CompressionResult(
            compressed_content=compressed_content,
            original_tokens=original_tokens,
            compressed_tokens=compressed_tokens,
            compression_ratio=compressed_tokens / original_tokens if original_tokens > 0 else 0,
            segments_preserved=len(selected),
            segments_summarized=len(summarized),
            segments_removed=len(removed),
            quality_score=quality_score,
            key_information_preserved=key_preserved,
            information_lost=info_lost,
        )

    def _segment_context(self, context: str) -> list[str]:
        """Segment context into logical parts."""
        segments = []

        # Split by double newlines (paragraph-like)
        paragraphs = re.split(r"\n\n+", context)

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            # Check if it's a code block
            if "```" in para:
                # Keep code blocks together
                segments.append(para)
            elif len(para) > 500:
                # Split long paragraphs by single newlines
                lines = para.split("\n")
                current = []
                for line in lines:
                    current.append(line)
                    if len("\n".join(current)) > 300:
                        segments.append("\n".join(current))
                        current = []
                if current:
                    segments.append("\n".join(current))
            else:
                segments.append(para)

        return segments

    def _importance_rank(self, importance: ImportanceLevel) -> int:
        """Convert importance to numeric rank."""
        ranks = {
            ImportanceLevel.CRITICAL: 5,
            ImportanceLevel.HIGH: 4,
            ImportanceLevel.MEDIUM: 3,
            ImportanceLevel.LOW: 2,
            ImportanceLevel.REDUNDANT: 1,
        }
        return ranks.get(importance, 0)

    def _select_segments(
        self,
        segments: list[ContentSegment],
        max_tokens: int,
    ) -> tuple[list[ContentSegment], list[ContentSegment], list[ContentSegment]]:
        """Select segments to fit token budget."""
        selected = []
        summarized = []
        removed = []

        current_tokens = 0
        summary_tokens = 0

        # Reserve some tokens for summaries
        available_for_full = int(max_tokens * 0.7)
        available_for_summary = int(max_tokens * 0.3)

        for segment in segments:
            if segment.importance == ImportanceLevel.REDUNDANT:
                removed.append(segment)
                continue

            if segment.preserve or segment.importance == ImportanceLevel.CRITICAL:
                # Must include
                if current_tokens + segment.tokens <= available_for_full:
                    selected.append(segment)
                    current_tokens += segment.tokens
                else:
                    # Summarize if can't fit full
                    summary = self.summarizer.summarize(
                        segment.content,
                        segment.content_type,
                        max_length=100,
                    )
                    segment.summary = summary
                    summarized.append(segment)
                    summary_tokens += self.token_estimator.estimate(summary)
            elif current_tokens + segment.tokens <= available_for_full:
                selected.append(segment)
                current_tokens += segment.tokens
            elif summary_tokens + 30 <= available_for_summary:
                summary = self.summarizer.summarize(
                    segment.content,
                    segment.content_type,
                    max_length=80,
                )
                segment.summary = summary
                summarized.append(segment)
                summary_tokens += self.token_estimator.estimate(summary)
            else:
                removed.append(segment)

        return selected, summarized, removed

    def _rebuild_context(
        self,
        selected: list[ContentSegment],
        summarized: list[ContentSegment],
        original_order: list[ContentSegment],
    ) -> str:
        """Rebuild context maintaining logical order."""
        # Create lookup for selected/summarized
        selected_set = {id(s) for s in selected}
        summarized_dict = {id(s): s for s in summarized}

        parts = []

        for seg in original_order:
            seg_id = id(seg)

            if seg_id in selected_set:
                parts.append(seg.content)
            elif seg_id in summarized_dict:
                parts.append(f"[Summary: {summarized_dict[seg_id].summary}]")

        # Add summary section if many items were summarized
        if len(summarized) > 3:
            summary_section = "\n[Earlier context summarized - key points preserved]"
            parts.insert(0, summary_section)

        return "\n\n".join(parts)

    def _calculate_quality(
        self,
        selected: list[ContentSegment],
        summarized: list[ContentSegment],
        removed: list[ContentSegment],
        all_segments: list[ContentSegment],
    ) -> float:
        """Calculate compression quality score."""
        if not all_segments:
            return 1.0

        # Base quality
        quality = 0.5

        # Points for preserving critical content
        critical_total = sum(1 for s in all_segments if s.importance == ImportanceLevel.CRITICAL)
        critical_preserved = sum(1 for s in selected if s.importance == ImportanceLevel.CRITICAL)
        critical_summarized = sum(1 for s in summarized if s.importance == ImportanceLevel.CRITICAL)

        if critical_total > 0:
            critical_score = (critical_preserved + critical_summarized * 0.7) / critical_total
            quality += critical_score * 0.3

        # Points for preserving high importance
        high_total = sum(1 for s in all_segments if s.importance == ImportanceLevel.HIGH)
        high_preserved = sum(1 for s in selected if s.importance == ImportanceLevel.HIGH)

        if high_total > 0:
            high_score = high_preserved / high_total
            quality += high_score * 0.15

        # Points for not losing important content
        important_removed = sum(
            1 for s in removed if s.importance in [ImportanceLevel.CRITICAL, ImportanceLevel.HIGH]
        )
        if important_removed == 0:
            quality += 0.05

        return min(1.0, quality)

    async def compress_conversation(
        self,
        messages: list[dict[str, str]],
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> CompressionResult:
        """
        Compress a conversation (list of messages).

        Args:
            messages: List of {"role": "...", "content": "..."} messages
            max_tokens: Maximum tokens

        Returns:
            CompressionResult
        """
        # Convert messages to context string
        context_parts = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("content", "")
            context_parts.append(f"[{role}]: {content}")

        context = "\n\n".join(context_parts)

        return await self.compress(
            context=context,
            max_tokens=max_tokens,
            preserve_recent=True,
        )

    def estimate_compression_needed(
        self,
        content: str,
        max_tokens: int,
    ) -> dict[str, Any]:
        """
        Estimate how much compression is needed.

        Args:
            content: Content to analyze
            max_tokens: Target token limit

        Returns:
            Analysis of compression needs
        """
        current_tokens = self.token_estimator.estimate(content)
        excess = current_tokens - max_tokens

        if excess <= 0:
            return {
                "compression_needed": False,
                "current_tokens": current_tokens,
                "target_tokens": max_tokens,
                "excess_tokens": 0,
                "compression_ratio_needed": 1.0,
            }

        return {
            "compression_needed": True,
            "current_tokens": current_tokens,
            "target_tokens": max_tokens,
            "excess_tokens": excess,
            "compression_ratio_needed": max_tokens / current_tokens,
            "recommendation": self._get_compression_recommendation(current_tokens, max_tokens),
        }

    def _get_compression_recommendation(
        self,
        current: int,
        target: int,
    ) -> str:
        """Get recommendation based on compression ratio needed."""
        ratio = target / current

        if ratio > 0.8:
            return "Light compression - summarize redundant sections"
        elif ratio > 0.5:
            return "Moderate compression - summarize older content, keep critical items"
        elif ratio > 0.3:
            return "Heavy compression - keep only critical content and recent items"
        else:
            return "Extreme compression - consider starting fresh context with summary"


# Convenience function
async def compress_context(
    context: str,
    max_tokens: int = 4000,
) -> CompressionResult:
    """Quick function to compress context."""
    compressor = ContextCompressor()
    return await compressor.compress(context, max_tokens)
