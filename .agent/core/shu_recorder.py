"""A/B Benchmark recording wrapper for /shu vs manual goal execution.

This module provides functions to record execution metrics for both structured
(/shu) and unstructured (manual) goal execution paths.
"""

import asyncio
import logging

from shu_ab_benchmark import ExecutionType, ShuABBenchmark

logger = logging.getLogger(__name__)


def record_shu_execution(
    goal: str,
    time_ms: int,
    success: bool,
    errors: int,
    quality_score: int,
) -> None:
    """Record metrics for /shu structured goal execution.

    Args:
        goal: The goal/task description.
        time_ms: Execution time in milliseconds (must be > 0).
        success: Whether execution succeeded.
        errors: Number of errors encountered (must be >= 0).
        quality_score: Quality rating 1-10.

    Raises:
        ValueError: If inputs are invalid (quality not in [1,10], time_ms <= 0, etc).
    """
    try:
        benchmark = ShuABBenchmark()
        benchmark.record_benchmark(
            execution_type=ExecutionType.STRUCTURED_SHU,
            goal=goal,
            time_ms=time_ms,
            success=success,
            errors_count=errors,
            quality_score_1_10=quality_score,
        )
        logger.info(
            "SHU execution recorded",
            extra={
                "goal_preview": goal[:30],
                "time_ms": time_ms,
                "success": success,
            },
        )
    except Exception as e:
        logger.error(f"Failed to record SHU execution: {e}")


def record_manual_execution(
    goal: str,
    time_ms: int,
    success: bool,
    errors: int,
    quality_score: int,
) -> None:
    """Record metrics for manual (unstructured) goal execution.

    Args:
        goal: The goal/task description.
        time_ms: Execution time in milliseconds (must be > 0).
        success: Whether execution succeeded.
        errors: Number of errors encountered (must be >= 0).
        quality_score: Quality rating 1-10.

    Raises:
        ValueError: If inputs are invalid.
    """
    try:
        benchmark = ShuABBenchmark()
        benchmark.record_benchmark(
            execution_type=ExecutionType.MANUAL_UNSTRUCTURED,
            goal=goal,
            time_ms=time_ms,
            success=success,
            errors_count=errors,
            quality_score_1_10=quality_score,
        )
        logger.info(
            "Manual execution recorded",
            extra={
                "goal_preview": goal[:30],
                "time_ms": time_ms,
                "success": success,
            },
        )
    except Exception as e:
        logger.error(f"Failed to record manual execution: {e}")


async def record_execution_async(
    execution_type: int,
    goal: str,
    time_ms: int,
    success: bool,
    errors: int,
    quality_score: int,
) -> None:
    """Async wrapper for recording execution metrics (fire-and-forget).

    This function is designed to be called without blocking goal execution.

    Args:
        execution_type: STRUCTURED_SHU or MANUAL_UNSTRUCTURED.
        goal: The goal/task description.
        time_ms: Execution time in milliseconds.
        success: Whether execution succeeded.
        errors: Number of errors encountered.
        quality_score: Quality rating 1-10.
    """
    try:
        # Run blocking I/O in thread pool to avoid blocking async tasks
        loop = asyncio.get_event_loop()
        if execution_type == ExecutionType.STRUCTURED_SHU:
            await loop.run_in_executor(
                None,
                record_shu_execution,
                goal,
                time_ms,
                success,
                errors,
                quality_score,
            )
        else:
            await loop.run_in_executor(
                None,
                record_manual_execution,
                goal,
                time_ms,
                success,
                errors,
                quality_score,
            )
    except Exception as e:
        logger.error(f"Async recording failed: {e}", exc_info=False)
