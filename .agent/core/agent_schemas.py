"""
Agent Schemas - Pydantic validation models for agent input/output.

This module provides:
- Standardized input/output validation for all agents
- Type-safe task definitions
- Result validation
- Error handling schemas

Usage:
    from .agent.core.agent_schemas import AgentInput, AgentOutput, validate_agent_task

    @validate_agent_task
    async def execute(self, input: AgentInput) -> AgentOutput:
        # Your agent logic here
        return AgentOutput(success=True, result="Done")
"""

from __future__ import annotations

import functools
import logging
from collections.abc import Callable
from datetime import datetime
from enum import Enum
from typing import Any, TypeVar
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

logger = logging.getLogger(__name__)

T = TypeVar("T")


# =============================================================================
# ENUMS
# =============================================================================


class TaskPriority(str, Enum):
    """Task priority levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    """Task execution status."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ResultType(str, Enum):
    """Type of result returned."""

    SUCCESS = "success"
    PARTIAL = "partial"
    ERROR = "error"
    TIMEOUT = "timeout"


# =============================================================================
# BASE SCHEMAS
# =============================================================================


class AgentInput(BaseModel):
    """
    Standardized input for all agents.

    Attributes:
        task: The task description or instruction
        task_id: Unique identifier for this task (auto-generated)
        context: Additional context data
        priority: Task priority level
        timeout_seconds: Maximum execution time
        metadata: Additional metadata
    """

    task: str = Field(..., min_length=1, max_length=10000, description="Task to execute")
    task_id: UUID = Field(default_factory=uuid4, description="Unique task identifier")
    context: dict[str, Any] = Field(default_factory=dict, description="Additional context")
    priority: TaskPriority = Field(default=TaskPriority.MEDIUM, description="Task priority")
    timeout_seconds: int = Field(default=300, ge=1, le=3600, description="Timeout in seconds")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    created_at: datetime = Field(default_factory=datetime.now, description="Creation timestamp")

    @field_validator("task")
    @classmethod
    def validate_task(cls, v: str) -> str:
        """Ensure task is not just whitespace."""
        v = v.strip()
        if not v:
            raise ValueError("Task cannot be empty or whitespace only")
        return v

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "task": "Analyze the authentication module for security vulnerabilities",
                "context": {"path": "src/auth/", "focus": "SQL injection"},
                "priority": "high",
                "timeout_seconds": 120,
            }
        }
    )


class AgentOutput(BaseModel):
    """
    Standardized output for all agents.

    Attributes:
        success: Whether the task completed successfully
        result: The main result (text, data, etc.)
        result_type: Type of result
        task_id: Reference to the input task
        execution_time_ms: Time taken to execute
        error: Error message if failed
        warnings: Non-fatal warnings
        metadata: Additional output metadata
    """

    success: bool = Field(..., description="Whether execution was successful")
    result: str | dict[str, Any] | list[Any] | None = Field(
        default=None, description="The main result"
    )
    result_type: ResultType | None = Field(
        default=None, description="Result type (auto-detected if None)"
    )
    task_id: UUID | None = Field(default=None, description="Reference to input task")
    execution_time_ms: float = Field(default=0.0, ge=0, description="Execution time in ms")
    error: str | None = Field(default=None, description="Error message if failed")
    warnings: list[str] = Field(default_factory=list, description="Non-fatal warnings")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Output metadata")
    completed_at: datetime = Field(default_factory=datetime.now, description="Completion time")

    @model_validator(mode="after")
    def set_result_type(self) -> AgentOutput:
        """Auto-set result type based on success/error fields."""
        if self.result_type is not None:
            return self
        if self.error:
            self.result_type = ResultType.ERROR
        elif self.success:
            self.result_type = ResultType.SUCCESS
        else:
            self.result_type = ResultType.PARTIAL
        return self

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "success": True,
                "result": "Analysis complete. Found 2 potential vulnerabilities.",
                "result_type": "success",
                "execution_time_ms": 1523.45,
                "warnings": ["Using deprecated auth method"],
            }
        }
    )


class AgentError(BaseModel):
    """
    Standardized error for agent failures.
    """

    error_type: str = Field(..., description="Type of error")
    message: str = Field(..., description="Human-readable error message")
    task_id: UUID | None = Field(default=None, description="Related task ID")
    recoverable: bool = Field(default=False, description="Whether error is recoverable")
    retry_after_seconds: int | None = Field(default=None, description="Suggested retry delay")
    details: dict[str, Any] = Field(default_factory=dict, description="Additional details")
    stack_trace: str | None = Field(default=None, description="Stack trace if available")
    timestamp: datetime = Field(default_factory=datetime.now, description="Error timestamp")


# =============================================================================
# SPECIALIZED SCHEMAS
# =============================================================================


class CodeAnalysisInput(AgentInput):
    """Input for code analysis agents."""

    path: str = Field(..., description="Path to analyze")
    language: str | None = Field(default=None, description="Programming language")
    analysis_type: str = Field(default="general", description="Type of analysis")
    include_suggestions: bool = Field(default=True, description="Include improvement suggestions")


class CodeAnalysisOutput(AgentOutput):
    """Output for code analysis agents."""

    findings: list[dict[str, Any]] = Field(default_factory=list, description="Analysis findings")
    summary: str | None = Field(default=None, description="Summary of analysis")
    severity_counts: dict[str, int] = Field(
        default_factory=lambda: {"critical": 0, "high": 0, "medium": 0, "low": 0}
    )
    suggestions: list[str] = Field(default_factory=list, description="Improvement suggestions")


class SearchInput(AgentInput):
    """Input for search/exploration agents."""

    query: str = Field(..., description="Search query")
    search_type: str = Field(default="code", description="Type of search")
    max_results: int = Field(default=50, ge=1, le=500, description="Maximum results")
    file_patterns: list[str] = Field(default_factory=list, description="File patterns to search")


class SearchOutput(AgentOutput):
    """Output for search/exploration agents."""

    matches: list[dict[str, Any]] = Field(default_factory=list, description="Search matches")
    total_matches: int = Field(default=0, description="Total matches found")
    searched_files: int = Field(default=0, description="Number of files searched")


class GenerationInput(AgentInput):
    """Input for code generation agents."""

    specification: str = Field(..., description="What to generate")
    output_path: str | None = Field(default=None, description="Where to save output")
    language: str = Field(default="python", description="Target language")
    style_guide: str | None = Field(default=None, description="Style guide to follow")


class GenerationOutput(AgentOutput):
    """Output for code generation agents."""

    generated_code: str | None = Field(default=None, description="Generated code")
    files_created: list[str] = Field(default_factory=list, description="Files created")
    imports_needed: list[str] = Field(default_factory=list, description="Required imports")


# =============================================================================
# VALIDATION DECORATORS
# =============================================================================


def validate_agent_task(func: Callable) -> Callable:
    """
    Decorator to validate agent input/output.

    Usage:
        @validate_agent_task
        async def execute(self, input: AgentInput) -> AgentOutput:
            ...
    """

    @functools.wraps(func)
    async def wrapper(self, input: AgentInput | dict | str, **kwargs) -> AgentOutput:
        import time

        start = time.perf_counter()

        # Convert input to AgentInput if necessary
        if isinstance(input, str):
            input = AgentInput(task=input)
        elif isinstance(input, dict):
            input = AgentInput(**input)

        try:
            result = await func(self, input, **kwargs)

            # Ensure result is AgentOutput
            if not isinstance(result, AgentOutput):
                if isinstance(result, dict):
                    result = AgentOutput(**result)
                elif isinstance(result, str):
                    result = AgentOutput(success=True, result=result)
                else:
                    result = AgentOutput(success=True, result=str(result))

            # Add execution time and task_id
            result.execution_time_ms = (time.perf_counter() - start) * 1000
            result.task_id = input.task_id

            return result

        except Exception as e:
            logger.exception(f"Agent execution failed: {e}")
            return AgentOutput(
                success=False,
                result_type=ResultType.ERROR,
                error=str(e),
                task_id=input.task_id,
                execution_time_ms=(time.perf_counter() - start) * 1000,
            )

    return wrapper


def validate_input(input_class: type[BaseModel]):
    """
    Decorator to validate input with a specific schema.

    Usage:
        @validate_input(CodeAnalysisInput)
        async def analyze(self, input: CodeAnalysisInput) -> CodeAnalysisOutput:
            ...
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(self, input: dict | BaseModel, **kwargs):
            if isinstance(input, dict):
                input = input_class(**input)
            elif not isinstance(input, input_class):
                raise TypeError(f"Expected {input_class.__name__}, got {type(input).__name__}")
            return await func(self, input, **kwargs)

        return wrapper

    return decorator


# =============================================================================
# HELPER FUNCTIONS
# =============================================================================


def create_success_output(
    result: str | dict | list, task_id: UUID | None = None, **kwargs
) -> AgentOutput:
    """Create a successful AgentOutput."""
    return AgentOutput(
        success=True, result=result, result_type=ResultType.SUCCESS, task_id=task_id, **kwargs
    )


def create_error_output(
    error: str, task_id: UUID | None = None, recoverable: bool = False, **kwargs
) -> AgentOutput:
    """Create an error AgentOutput."""
    return AgentOutput(
        success=False,
        result_type=ResultType.ERROR,
        error=error,
        task_id=task_id,
        metadata={"recoverable": recoverable},
        **kwargs,
    )


def create_partial_output(
    result: str | dict | list, warnings: list[str], task_id: UUID | None = None, **kwargs
) -> AgentOutput:
    """Create a partial success AgentOutput."""
    return AgentOutput(
        success=True,
        result=result,
        result_type=ResultType.PARTIAL,
        warnings=warnings,
        task_id=task_id,
        **kwargs,
    )


# =============================================================================
# EXPORTS
# =============================================================================

__all__ = [
    # Enums
    "TaskPriority",
    "TaskStatus",
    "ResultType",
    # Base schemas
    "AgentInput",
    "AgentOutput",
    "AgentError",
    # Specialized schemas
    "CodeAnalysisInput",
    "CodeAnalysisOutput",
    "SearchInput",
    "SearchOutput",
    "GenerationInput",
    "GenerationOutput",
    # Decorators
    "validate_agent_task",
    "validate_input",
    # Helpers
    "create_success_output",
    "create_error_output",
    "create_partial_output",
]
