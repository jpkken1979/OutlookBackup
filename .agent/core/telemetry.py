#!/usr/bin/env python3
"""
Antigravity Telemetry - OpenTelemetry observability for AI agents.

Implements:
- Distributed tracing for agent execution
- Metrics for performance monitoring
- LLM-specific instrumentation via OpenLLMetry
- Integration with common observability backends
"""

import inspect
import logging
from collections.abc import Callable
from contextlib import contextmanager
from datetime import datetime
from functools import wraps
from typing import Any

logger = logging.getLogger("antigravity.telemetry")


# =============================================================================
# TELEMETRY CONFIGURATION
# =============================================================================


class TelemetryConfig:
    """Configuration for telemetry system."""

    def __init__(
        self,
        service_name: str = "antigravity-agents",
        environment: str = "development",
        otlp_endpoint: str | None = None,
        enable_console_export: bool = False,
        enable_llm_tracing: bool = True,
        sample_rate: float = 1.0,
    ):
        self.service_name = service_name
        self.environment = environment
        self.otlp_endpoint = otlp_endpoint
        self.enable_console_export = enable_console_export
        self.enable_llm_tracing = enable_llm_tracing
        self.sample_rate = sample_rate


# =============================================================================
# OPENTELEMETRY SETUP
# =============================================================================

_tracer = None
_meter = None
_initialized = False


def setup_telemetry(
    service_name: str = "antigravity.orchestrator", config: TelemetryConfig | None = None
) -> dict:
    """
    Initialize OpenTelemetry instrumentation.

    Args:
        service_name: Name for the service
        config: Optional telemetry configuration

    Returns:
        Dict with tracer and meter objects
    """
    global _tracer, _meter, _initialized

    if _initialized:
        return {"tracer": _tracer, "meter": _meter}

    config = config or TelemetryConfig(service_name=service_name)

    try:
        from opentelemetry import metrics, trace
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import (
            ConsoleMetricExporter,
            PeriodicExportingMetricReader,
        )
        from opentelemetry.sdk.resources import SERVICE_NAME, SERVICE_VERSION, Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

        # Create resource
        resource = Resource.create(
            {
                SERVICE_NAME: config.service_name,
                SERVICE_VERSION: "3.0.0",
                "deployment.environment": config.environment,
            }
        )

        # Setup tracing
        tracer_provider = TracerProvider(resource=resource)

        if config.enable_console_export:
            tracer_provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

        # OTLP exporter if configured
        if config.otlp_endpoint:
            try:
                from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter

                otlp_exporter = OTLPSpanExporter(endpoint=config.otlp_endpoint)
                tracer_provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
                logger.info(f"OTLP tracing enabled: {config.otlp_endpoint}")
            except ImportError:
                logger.warning("OTLP exporter not available")

        trace.set_tracer_provider(tracer_provider)
        _tracer = trace.get_tracer(service_name)

        # Setup metrics
        metric_readers = []
        if config.enable_console_export:
            metric_readers.append(PeriodicExportingMetricReader(ConsoleMetricExporter()))

        meter_provider = MeterProvider(resource=resource, metric_readers=metric_readers)
        metrics.set_meter_provider(meter_provider)
        _meter = metrics.get_meter(service_name)

        # Setup LLM tracing if enabled
        if config.enable_llm_tracing:
            _setup_llm_tracing()

        _initialized = True
        logger.info(f"Telemetry initialized for {service_name}")

        return {"tracer": _tracer, "meter": _meter}

    except ImportError as e:
        logger.warning(f"OpenTelemetry not available: {e}")
        logger.info("Install with: pip install opentelemetry-api opentelemetry-sdk")
        return {"tracer": None, "meter": None}


def _setup_llm_tracing():
    """Setup OpenLLMetry for LLM-specific tracing."""
    try:
        from traceloop.sdk import Traceloop

        Traceloop.init(
            app_name="antigravity-agents",
            disable_batch=True,  # Send spans immediately for debugging
        )
        logger.info("OpenLLMetry (Traceloop) initialized")

    except ImportError:
        logger.debug("Traceloop SDK not available, LLM tracing disabled")
    except Exception as e:
        logger.warning(f"Error initializing LLM tracing: {e}")


# =============================================================================
# TRACING UTILITIES
# =============================================================================


def get_tracer(name: str = "antigravity"):
    """Get or create a tracer."""
    global _tracer

    if _tracer is None:
        setup_telemetry()

    if _tracer:
        return _tracer

    # Fallback no-op tracer
    return NoOpTracer()


class NoOpTracer:
    """No-op tracer for when OpenTelemetry is not available."""

    def start_span(self, name: str, **kwargs):
        return NoOpSpan()

    @contextmanager
    def start_as_current_span(self, name: str, **kwargs):
        yield NoOpSpan()


class NoOpSpan:
    """No-op span."""

    def set_attribute(self, key: str, value: Any):
        pass

    def set_status(self, status):
        pass

    def record_exception(self, exception):
        pass

    def end(self):
        pass

    def __enter__(self):
        return self

    def __exit__(self, *args):
        pass


@contextmanager
def trace_agent_execution(agent_name: str, task: str, attributes: dict | None = None):
    """
    Context manager for tracing agent execution.

    Usage:
        with trace_agent_execution("frontend-specialist", "Build component"):
            # Agent execution code
            pass
    """
    tracer = get_tracer()
    attributes = attributes or {}

    with tracer.start_as_current_span(
        f"agent.execute.{agent_name}",
        attributes={
            "agent.name": agent_name,
            "agent.task": task[:100],  # Truncate long tasks
            "agent.timestamp": datetime.now().isoformat(),
            **attributes,
        },
    ) as span:
        try:
            yield span
        except Exception as e:
            span.record_exception(e)
            span.set_attribute("agent.error", str(e))
            raise


@contextmanager
def trace_llm_call(model: str, prompt_tokens: int = 0, attributes: dict | None = None):
    """
    Context manager for tracing LLM API calls.

    Usage:
        with trace_llm_call("claude-3-opus", prompt_tokens=1000) as span:
            response = llm.generate(...)
            span.set_attribute("llm.completion_tokens", response.tokens)
    """
    tracer = get_tracer()
    attributes = attributes or {}

    with tracer.start_as_current_span(
        "llm.call",
        attributes={
            "llm.model": model,
            "llm.prompt_tokens": prompt_tokens,
            "llm.timestamp": datetime.now().isoformat(),
            **attributes,
        },
    ) as span:
        yield span


def trace_function(name: str | None = None):
    """
    Decorator for tracing function execution.

    Usage:
        @trace_function("process_data")
        def process_data(input):
            return result
    """

    def decorator(func: Callable) -> Callable:
        span_name = name or func.__name__

        @wraps(func)
        def wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                try:
                    result = func(*args, **kwargs)
                    span.set_attribute("function.success", True)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_attribute("function.success", False)
                    raise

        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            tracer = get_tracer()
            with tracer.start_as_current_span(span_name) as span:
                try:
                    result = await func(*args, **kwargs)
                    span.set_attribute("function.success", True)
                    return result
                except Exception as e:
                    span.record_exception(e)
                    span.set_attribute("function.success", False)
                    raise

        if inspect.iscoroutinefunction(func):
            return async_wrapper
        return wrapper

    return decorator


# =============================================================================
# METRICS UTILITIES
# =============================================================================


def get_meter(name: str = "antigravity"):
    """Get or create a meter."""
    global _meter

    if _meter is None:
        setup_telemetry()

    if _meter:
        return _meter

    return NoOpMeter()


class NoOpMeter:
    """No-op meter for when OpenTelemetry is not available."""

    def create_counter(self, name: str, **kwargs):
        return NoOpCounter()

    def create_histogram(self, name: str, **kwargs):
        return NoOpHistogram()

    def create_up_down_counter(self, name: str, **kwargs):
        return NoOpCounter()


class NoOpCounter:
    """No-op counter."""

    def add(self, value: int, attributes: dict | None = None):
        pass


class NoOpHistogram:
    """No-op histogram."""

    def record(self, value: float, attributes: dict | None = None):
        pass


# Pre-defined metrics
_metrics = {}


def get_agent_execution_counter():
    """Get counter for agent executions."""
    if "agent_executions" not in _metrics:
        meter = get_meter()
        _metrics["agent_executions"] = meter.create_counter(
            "agent.executions", description="Number of agent executions", unit="1"
        )
    return _metrics["agent_executions"]


def get_agent_duration_histogram():
    """Get histogram for agent execution duration."""
    if "agent_duration" not in _metrics:
        meter = get_meter()
        _metrics["agent_duration"] = meter.create_histogram(
            "agent.duration", description="Agent execution duration", unit="s"
        )
    return _metrics["agent_duration"]


def get_llm_tokens_counter():
    """Get counter for LLM token usage."""
    if "llm_tokens" not in _metrics:
        meter = get_meter()
        _metrics["llm_tokens"] = meter.create_counter(
            "llm.tokens", description="Total LLM tokens used", unit="1"
        )
    return _metrics["llm_tokens"]


def record_agent_execution(
    agent_name: str, duration_seconds: float, success: bool = True, tokens_used: int = 0
):
    """
    Record metrics for an agent execution.

    Args:
        agent_name: Name of the agent
        duration_seconds: Execution duration
        success: Whether execution succeeded
        tokens_used: LLM tokens consumed
    """
    attributes = {"agent.name": agent_name, "agent.success": success}

    get_agent_execution_counter().add(1, attributes)
    get_agent_duration_histogram().record(duration_seconds, attributes)

    if tokens_used > 0:
        get_llm_tokens_counter().add(tokens_used, {"agent.name": agent_name})


# =============================================================================
# CLI
# =============================================================================


def main():
    """Test telemetry system."""
    import time

    print("Testing Antigravity Telemetry...\n")

    # Initialize
    result = setup_telemetry("test-service")
    print(f"Tracer: {result['tracer']}")
    print(f"Meter: {result['meter']}")

    # Test tracing
    print("\n--- Tracing Test ---")
    with trace_agent_execution("test-agent", "Test task") as span:
        span.set_attribute("test.attribute", "value")
        # (simulacion removida — no ejecutar sleeps en demo)
        print("Agent execution traced")

    # Test decorated function
    @trace_function("test_operation")
    def test_operation():
        return "success"

    result = test_operation()
    print(f"Decorated function result: {result}")

    # Test metrics
    print("\n--- Metrics Test ---")
    record_agent_execution(
        agent_name="test-agent", duration_seconds=0.15, success=True, tokens_used=500
    )
    print("Metrics recorded")

    print("\nTelemetry tests complete!")


if __name__ == "__main__":
    main()
