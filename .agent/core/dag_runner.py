"""
DAG Runner — Directed Acyclic Graph Task Executor.

Executes tasks with declared dependencies in optimal order:
- Independent tasks run in parallel (asyncio)
- Dependent tasks wait for their prerequisites
- Failed tasks cause downstream dependents to be skipped
- Configurable concurrency, timeouts, and retries

Inspired by the "Ralphinho DAG" pattern from ECC.

Usage:
    runner = DagRunner()
    runner.add_task(DagTask(id="fetch", name="Fetch data", fn=fetch_fn))
    runner.add_task(DagTask(id="parse", name="Parse", fn=parse_fn, depends_on=["fetch"]))
    runner.add_task(DagTask(id="validate", name="Validate", fn=validate_fn, depends_on=["fetch"]))
    runner.add_task(DagTask(id="save", name="Save", fn=save_fn, depends_on=["parse", "validate"]))

    report = await runner.execute()
    # fetch runs first
    # parse and validate run in parallel (both depend only on fetch)
    # save runs last (depends on both parse and validate)

Version: 1.0.0
"""

from __future__ import annotations

import asyncio
import logging
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger("antigravity.dag_runner")


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class DagTask:
    """A task in a DAG execution graph.

    Args:
        id: Unique identifier for this task.
        name: Human-readable name.
        fn: Async callable with signature ``async def fn(context: dict) -> Any``.
        depends_on: List of task IDs that must complete before this task runs.
        timeout_seconds: Maximum seconds before the task is cancelled.
        retry_count: Number of retries on failure (0 = no retries).
        metadata: Arbitrary metadata attached to the task.
    """

    id: str
    name: str
    fn: Any  # Callable[..., Awaitable[Any]] — kept as Any to avoid import complexity
    depends_on: list[str] = field(default_factory=list)
    timeout_seconds: float = 300.0
    retry_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class TaskResult:
    """Result of executing a single DAG task.

    Args:
        task_id: ID of the task that produced this result.
        status: One of "success", "failed", "skipped", "timeout".
        result: Return value from the task function (on success).
        error: Error message (on failure/timeout).
        duration_ms: Execution time in milliseconds.
    """

    task_id: str
    status: str  # "success" | "failed" | "skipped" | "timeout"
    result: Any = None
    error: str | None = None
    duration_ms: float = 0.0


@dataclass
class DagExecutionReport:
    """Report of a complete DAG execution.

    Args:
        total_tasks: Total number of tasks in the DAG.
        succeeded: Count of tasks that completed successfully.
        failed: Count of tasks that failed.
        skipped: Count of tasks skipped due to upstream failure.
        timed_out: Count of tasks that exceeded their timeout.
        total_duration_ms: Wall-clock time for the entire DAG execution.
        results: List of individual task results.
        execution_order: Levels of parallel execution (topological layers).
    """

    total_tasks: int
    succeeded: int
    failed: int
    skipped: int
    timed_out: int
    total_duration_ms: float
    results: list[TaskResult]
    execution_order: list[list[str]]


# =============================================================================
# DAG RUNNER
# =============================================================================


class DagValidationError(Exception):
    """Raised when the DAG has structural problems (cycles, missing deps)."""


class DagRunner:
    """Executes tasks in a DAG with parallel execution of independent tasks.

    Uses Kahn's algorithm for topological sorting and asyncio.Semaphore
    to limit concurrency within each execution level.

    Args:
        max_concurrency: Maximum number of tasks running in parallel.
    """

    def __init__(self, max_concurrency: int = 5) -> None:
        self._tasks: dict[str, DagTask] = {}
        self._max_concurrency = max_concurrency

    @property
    def tasks(self) -> dict[str, DagTask]:
        """Read-only access to registered tasks."""
        return dict(self._tasks)

    def add_task(self, task: DagTask) -> None:
        """Add a task to the DAG.

        Args:
            task: The task to register.

        Raises:
            ValueError: If a task with the same ID already exists.
        """
        if task.id in self._tasks:
            raise ValueError(f"Task with id '{task.id}' already exists")
        self._tasks[task.id] = task
        logger.debug("Added task '%s' (%s), depends_on=%s", task.id, task.name, task.depends_on)

    def validate(self) -> list[str]:
        """Validate the DAG structure.

        Checks for:
        - Missing dependencies (task references a non-existent ID)
        - Cycles (circular dependency chains)

        Returns:
            List of error messages. Empty list means the DAG is valid.
        """
        errors = self._find_missing_dependencies()
        if errors:
            return errors

        errors.extend(self._find_cycles())
        return errors

    def _find_missing_dependencies(self) -> list[str]:
        """Detecta dependencias que referencian IDs de tareas inexistentes.

        Returns:
            Lista de mensajes de error por cada dependencia faltante.
        """
        errors: list[str] = []
        for task in self._tasks.values():
            for dep_id in task.depends_on:
                if dep_id not in self._tasks:
                    errors.append(f"Task '{task.id}' depends on '{dep_id}' which does not exist")
        return errors

    def _find_cycles(self) -> list[str]:
        """Detecta ciclos en el DAG usando el algoritmo de Kahn.

        Returns:
            Lista con un mensaje de error si hay ciclo, vacia en caso contrario.
        """
        in_degree: dict[str, int] = dict.fromkeys(self._tasks, 0)
        for task in self._tasks.values():
            for _dep_id in task.depends_on:
                # dep_id -> task.id edge means task.id has +1 in-degree
                in_degree[task.id] += 1

        queue: deque[str] = deque(tid for tid, degree in in_degree.items() if degree == 0)

        visited_count = 0
        while queue:
            current = queue.popleft()
            visited_count += 1
            # Find tasks that depend on current
            for task in self._tasks.values():
                if current in task.depends_on:
                    in_degree[task.id] -= 1
                    if in_degree[task.id] == 0:
                        queue.append(task.id)

        if visited_count != len(self._tasks):
            # Find tasks involved in the cycle
            cycle_tasks = [tid for tid, deg in in_degree.items() if deg > 0]
            return [f"Cycle detected involving tasks: {', '.join(sorted(cycle_tasks))}"]
        return []

    def get_execution_levels(self) -> list[list[str]]:
        """Compute execution levels via topological sort (Kahn's algorithm).

        Level 0 contains tasks with no dependencies.
        Level N contains tasks whose dependencies are all in levels < N.
        Tasks within the same level can run in parallel.

        Returns:
            List of levels, each level is a list of task IDs.

        Raises:
            DagValidationError: If the DAG is invalid.
        """
        errors = self.validate()
        if errors:
            raise DagValidationError(f"Invalid DAG: {'; '.join(errors)}")

        if not self._tasks:
            return []

        # Build in-degree map
        in_degree: dict[str, int] = dict.fromkeys(self._tasks, 0)
        for task in self._tasks.values():
            for _dep_id in task.depends_on:
                in_degree[task.id] += 1

        levels: list[list[str]] = []
        remaining = set(self._tasks.keys())

        while remaining:
            # Find all tasks with in-degree 0 among remaining
            level = [tid for tid in remaining if in_degree[tid] == 0]

            if not level:
                # Should not happen if validate() passed, but guard anyway
                break

            levels.append(sorted(level))  # Sort for deterministic ordering

            # Remove this level from the graph
            for tid in level:
                remaining.discard(tid)
                # Decrease in-degree of dependents
                for task in self._tasks.values():
                    if tid in task.depends_on and task.id in remaining:
                        in_degree[task.id] -= 1

        return levels

    async def execute(self, context: dict[str, Any] | None = None) -> DagExecutionReport:
        """Execute all tasks in dependency order.

        Independent tasks at the same level run in parallel, bounded by
        ``max_concurrency``. If a task fails or times out, all tasks that
        transitively depend on it are skipped.

        Args:
            context: Optional shared context dict accessible to all task functions.
                     Task results are automatically stored as ``context[task_id]``.

        Returns:
            A DagExecutionReport with per-task results and aggregate stats.

        Raises:
            DagValidationError: If the DAG is invalid.
        """
        if context is None:
            context = {}

        levels = self.get_execution_levels()

        results: dict[str, TaskResult] = {}
        failed_ids: set[str] = set()
        semaphore = asyncio.Semaphore(self._max_concurrency)

        start_time = time.monotonic()

        for level_idx, level in enumerate(levels):
            logger.info(
                "DAG level %d: executing %d task(s) — %s",
                level_idx,
                len(level),
                level,
            )

            # Determine which tasks in this level should be skipped
            tasks_to_run: list[DagTask] = []
            for tid in level:
                task = self._tasks[tid]
                # Check if any dependency failed
                upstream_failed = any(dep_id in failed_ids for dep_id in task.depends_on)
                if upstream_failed:
                    results[tid] = TaskResult(
                        task_id=tid,
                        status="skipped",
                        error="Upstream dependency failed",
                    )
                    failed_ids.add(tid)
                    logger.warning("Skipping task '%s' — upstream dependency failed", tid)
                else:
                    tasks_to_run.append(task)

            # Execute non-skipped tasks in parallel
            if tasks_to_run:
                level_results = await asyncio.gather(
                    *(self._run_task(task, context, semaphore) for task in tasks_to_run),
                    return_exceptions=False,
                )
                for result in level_results:
                    results[result.task_id] = result
                    if result.status in ("failed", "timeout"):
                        failed_ids.add(result.task_id)
                    elif result.status == "success":
                        # Store result in context for downstream tasks
                        context[result.task_id] = result.result

        total_duration_ms = (time.monotonic() - start_time) * 1000

        # Build report
        all_results = [results[tid] for level in levels for tid in level]
        succeeded = sum(1 for r in all_results if r.status == "success")
        failed = sum(1 for r in all_results if r.status == "failed")
        skipped = sum(1 for r in all_results if r.status == "skipped")
        timed_out = sum(1 for r in all_results if r.status == "timeout")

        report = DagExecutionReport(
            total_tasks=len(self._tasks),
            succeeded=succeeded,
            failed=failed,
            skipped=skipped,
            timed_out=timed_out,
            total_duration_ms=total_duration_ms,
            results=all_results,
            execution_order=levels,
        )

        logger.info(
            "DAG execution complete: %d tasks — %d ok, %d failed, %d skipped, %d timeout (%.1fms)",
            report.total_tasks,
            succeeded,
            failed,
            skipped,
            timed_out,
            total_duration_ms,
        )

        return report

    async def _run_task(
        self,
        task: DagTask,
        context: dict[str, Any],
        semaphore: asyncio.Semaphore,
    ) -> TaskResult:
        """Execute a single task with timeout, retry, and concurrency control.

        Args:
            task: The task to execute.
            context: Shared context dict.
            semaphore: Concurrency limiter.

        Returns:
            TaskResult with status and timing information.
        """
        async with semaphore:
            attempts = 1 + task.retry_count
            last_error: str | None = None

            for attempt in range(1, attempts + 1):
                start = time.monotonic()
                try:
                    logger.debug(
                        "Running task '%s' (attempt %d/%d)",
                        task.id,
                        attempt,
                        attempts,
                    )
                    result = await asyncio.wait_for(
                        task.fn(context),
                        timeout=task.timeout_seconds,
                    )
                    duration_ms = (time.monotonic() - start) * 1000
                    logger.info(
                        "Task '%s' succeeded in %.1fms",
                        task.id,
                        duration_ms,
                    )
                    return TaskResult(
                        task_id=task.id,
                        status="success",
                        result=result,
                        duration_ms=duration_ms,
                    )

                except TimeoutError:
                    duration_ms = (time.monotonic() - start) * 1000
                    last_error = f"Timeout after {task.timeout_seconds}s"
                    logger.warning(
                        "Task '%s' timed out after %.1fms (attempt %d/%d)",
                        task.id,
                        duration_ms,
                        attempt,
                        attempts,
                    )
                    # Timeouts are not retried — they indicate a fundamental issue
                    return TaskResult(
                        task_id=task.id,
                        status="timeout",
                        error=last_error,
                        duration_ms=duration_ms,
                    )

                except Exception as exc:
                    duration_ms = (time.monotonic() - start) * 1000
                    last_error = f"{type(exc).__name__}: {exc}"
                    logger.warning(
                        "Task '%s' failed: %s (attempt %d/%d)",
                        task.id,
                        last_error,
                        attempt,
                        attempts,
                    )
                    if attempt < attempts:
                        logger.info("Retrying task '%s'…", task.id)

            # All retries exhausted
            return TaskResult(
                task_id=task.id,
                status="failed",
                error=last_error,
                duration_ms=duration_ms,  # type: ignore[possibly-undefined]
            )
