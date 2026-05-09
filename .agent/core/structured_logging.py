"""
Structured Logging - Enterprise-grade logging for Antigravity ecosystem.

This module provides:
- Structured JSON logging
- Correlation IDs for request tracing
- Context-aware logging
- Performance logging
- Error tracking

Usage:
    from .agent.core.structured_logging import get_logger, with_context

    logger = get_logger(__name__)
    logger.info("Processing task", task_id="123", agent="explorer")

    # With context
    with with_context(trace_id="abc123", user="john"):
        logger.info("In context")  # Automatically includes trace_id and user
"""
# mypy: ignore-errors

from __future__ import annotations

import inspect
import json
import logging
import sys
import time
from collections.abc import Callable
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import asdict, dataclass, field

try:
    from datetime import datetime, UTC
except ImportError:  # Python < 3.11
    from datetime import datetime, timezone

    UTC = UTC
from functools import wraps
from typing import Any, TypeVar
from uuid import uuid4

# =============================================================================
# CONTEXT MANAGEMENT
# =============================================================================

# Context variables for request tracing
_trace_id: ContextVar[str | None] = ContextVar("trace_id", default=None)
_span_id: ContextVar[str | None] = ContextVar("span_id", default=None)
_agent_name: ContextVar[str | None] = ContextVar("agent_name", default=None)
_extra_context: ContextVar[dict[str, Any]] = ContextVar("extra_context", default={})


def get_trace_id() -> str | None:
    """Get current trace ID."""
    return _trace_id.get()


def get_span_id() -> str | None:
    """Get current span ID."""
    return _span_id.get()


def get_agent_name() -> str | None:
    """Get current agent name."""
    return _agent_name.get()


def set_trace_id(trace_id: str) -> None:
    """Set trace ID for current context."""
    _trace_id.set(trace_id)


def set_span_id(span_id: str) -> None:
    """Set span ID for current context."""
    _span_id.set(span_id)


def set_agent_name(name: str) -> None:
    """Set agent name for current context."""
    _agent_name.set(name)


@contextmanager
def with_context(
    trace_id: str | None = None, span_id: str | None = None, agent: str | None = None, **extra
):
    """
    Context manager for adding context to all logs within scope.

    Usage:
        with with_context(trace_id="abc", agent="explorer"):
            logger.info("This log has trace_id and agent automatically")
    """
    old_trace = _trace_id.get()
    old_span = _span_id.get()
    old_agent = _agent_name.get()
    old_extra = _extra_context.get()

    try:
        if trace_id:
            _trace_id.set(trace_id)
        if span_id:
            _span_id.set(span_id)
        if agent:
            _agent_name.set(agent)
        if extra:
            _extra_context.set({**old_extra, **extra})
        yield
    finally:
        _trace_id.set(old_trace)
        _span_id.set(old_span)
        _agent_name.set(old_agent)
        _extra_context.set(old_extra)


# =============================================================================
# LOG RECORD
# =============================================================================


@dataclass
class LogRecord:
    """Structured log record."""

    timestamp: str
    level: str
    logger: str
    message: str
    trace_id: str | None = None
    span_id: str | None = None
    agent: str | None = None
    duration_ms: float | None = None
    error: str | None = None
    stack_trace: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_json(self) -> str:
        """Convert to JSON string."""
        data = {k: v for k, v in asdict(self).items() if v is not None}
        return json.dumps(data, default=str)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {k: v for k, v in asdict(self).items() if v is not None}


# =============================================================================
# STRUCTURED FORMATTER
# =============================================================================


class StructuredFormatter(logging.Formatter):
    """
    JSON formatter for structured logging.
    """

    def __init__(self, include_stack: bool = True):
        super().__init__()
        self.include_stack = include_stack

    def format(self, record: logging.LogRecord) -> str:
        # Base log data
        log_record = LogRecord(
            timestamp=datetime.now(UTC).isoformat().replace("+00:00", "Z"),
            level=record.levelname,
            logger=record.name,
            message=record.getMessage(),
            trace_id=get_trace_id(),
            span_id=get_span_id(),
            agent=get_agent_name(),
        )

        # Add exception info if present
        if record.exc_info:
            log_record.error = str(record.exc_info[1])
            if self.include_stack:
                log_record.stack_trace = self.formatException(record.exc_info)

        # Add extra fields
        extra = _extra_context.get().copy()

        # Include any extra attributes added to the record
        for key in ["duration_ms", "task_id", "agent_name", "component"]:
            if hasattr(record, key):
                extra[key] = getattr(record, key)

        # Include custom extra from record
        if hasattr(record, "extra_fields"):
            extra.update(record.extra_fields)

        if extra:
            log_record.extra = extra

        return log_record.to_json()


class HumanReadableFormatter(logging.Formatter):
    """
    Human-readable formatter with color support.
    """

    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool = True):
        super().__init__()
        self.use_color = use_color and sys.stdout.isatty()

    def format(self, record: logging.LogRecord) -> str:
        # Timestamp
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]

        # Level with color
        level = record.levelname
        if self.use_color:
            color = self.COLORS.get(level, "")
            level = f"{color}{level:8}{self.RESET}"
        else:
            level = f"{level:8}"

        # Base message
        msg = record.getMessage()

        # Build prefix
        prefix_parts = [f"[{timestamp}]", level, f"[{record.name}]"]

        # Add trace ID if present
        trace_id = get_trace_id()
        if trace_id:
            prefix_parts.append(f"[{trace_id[:8]}]")

        # Add agent if present
        agent = get_agent_name()
        if agent:
            prefix_parts.append(f"[{agent}]")

        prefix = " ".join(prefix_parts)
        output = f"{prefix} {msg}"

        # Add exception if present
        if record.exc_info:
            output += "\n" + self.formatException(record.exc_info)

        return output


# =============================================================================
# LOGGER CLASS
# =============================================================================


class StructuredLogger(logging.Logger):
    """
    Logger with structured logging support.
    """

    def _log_with_extra(
        self,
        level: int,
        msg: str,
        args: tuple,
        exc_info=None,
        stack_info: bool = False,
        stacklevel: int = 2,
        **kwargs,
    ):
        """Log with extra fields."""
        # Create a LogRecord with extra fields
        if kwargs:
            extra = {"extra_fields": kwargs}
        else:
            extra = {}

        super()._log(
            level,
            msg,
            args,
            exc_info=exc_info,
            extra=extra,
            stack_info=stack_info,
            stacklevel=stacklevel,
        )

    def debug(self, msg: str, *args, **kwargs):
        if self.isEnabledFor(logging.DEBUG):
            self._log_with_extra(logging.DEBUG, msg, args, **kwargs)

    def info(self, msg: str, *args, **kwargs):
        if self.isEnabledFor(logging.INFO):
            self._log_with_extra(logging.INFO, msg, args, **kwargs)

    def warning(self, msg: str, *args, **kwargs):
        if self.isEnabledFor(logging.WARNING):
            self._log_with_extra(logging.WARNING, msg, args, **kwargs)

    def error(self, msg: str, *args, exc_info=True, **kwargs):
        if self.isEnabledFor(logging.ERROR):
            self._log_with_extra(logging.ERROR, msg, args, exc_info=exc_info, **kwargs)

    def critical(self, msg: str, *args, exc_info=True, **kwargs):
        if self.isEnabledFor(logging.CRITICAL):
            self._log_with_extra(logging.CRITICAL, msg, args, exc_info=exc_info, **kwargs)


# =============================================================================
# SETUP AND FACTORY
# =============================================================================

# Register our custom logger class
logging.setLoggerClass(StructuredLogger)

# Cached loggers
_loggers: dict[str, StructuredLogger] = {}


def get_logger(name: str) -> StructuredLogger:
    """
    Get or create a structured logger.

    Args:
        name: Logger name (usually __name__)

    Returns:
        StructuredLogger instance
    """
    if name in _loggers:
        return _loggers[name]

    logger = logging.getLogger(name)
    _loggers[name] = logger
    return logger


def setup_logging(level: str = "INFO", format: str = "json", include_stack: bool = True) -> None:
    """
    Setup logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format: Output format ("json" or "human")
        include_stack: Include stack traces in JSON output
    """
    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers
    for handler in root.handlers[:]:
        root.removeHandler(handler)

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Set formatter
    if format == "json":
        handler.setFormatter(StructuredFormatter(include_stack=include_stack))
    else:
        handler.setFormatter(HumanReadableFormatter())

    root.addHandler(handler)


# =============================================================================
# DECORATORS
# =============================================================================

F = TypeVar("F", bound=Callable[..., Any])


def log_execution(logger: logging.Logger | None = None):
    """
    Decorator to log function execution with timing.

    Usage:
        @log_execution()
        async def my_function():
            ...
    """

    def decorator(func: F) -> F:
        nonlocal logger
        if logger is None:
            logger = get_logger(func.__module__)

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            func_name = func.__qualname__
            logger.info(f"Starting {func_name}")
            start = time.time()

            try:
                result = await func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                logger.info(f"Completed {func_name}", duration_ms=duration)
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.error(f"Failed {func_name}: {e}", duration_ms=duration, exc_info=True)
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            func_name = func.__qualname__
            logger.info(f"Starting {func_name}")
            start = time.time()

            try:
                result = func(*args, **kwargs)
                duration = (time.time() - start) * 1000
                logger.info(f"Completed {func_name}", duration_ms=duration)
                return result
            except Exception as e:
                duration = (time.time() - start) * 1000
                logger.error(f"Failed {func_name}: {e}", duration_ms=duration, exc_info=True)
                raise

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return sync_wrapper

    return decorator


def with_trace(func: F) -> F:
    """
    Decorator to add trace ID to function execution.

    Usage:
        @with_trace
        async def my_function():
            ...
    """

    @wraps(func)
    async def async_wrapper(*args, **kwargs):
        trace_id = str(uuid4())[:8]
        with with_context(trace_id=trace_id):
            return await func(*args, **kwargs)

    @wraps(func)
    def sync_wrapper(*args, **kwargs):
        trace_id = str(uuid4())[:8]
        with with_context(trace_id=trace_id):
            return func(*args, **kwargs)

    if inspect.iscoroutinefunction(func):
        return async_wrapper
    return sync_wrapper


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Context management
    "get_trace_id",
    "get_span_id",
    "get_agent_name",
    "set_trace_id",
    "set_span_id",
    "set_agent_name",
    "with_context",
    # Logger
    "get_logger",
    "setup_logging",
    "StructuredLogger",
    # Formatters
    "StructuredFormatter",
    "HumanReadableFormatter",
    # Data classes
    "LogRecord",
    # Decorators
    "log_execution",
    "with_trace",
]
