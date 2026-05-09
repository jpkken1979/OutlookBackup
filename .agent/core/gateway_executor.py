#!/usr/bin/env python3
"""
GatewayExecutor — Adapter between the HTTP Gateway and AntigravityOrchestrator.

Provides the synchronous, gateway-compatible API expected by gateway.py:
- get_available_agents()
- execute_agent(agent_name, task, timeout)
- find_best_agent(task_description, limit)
- get_cost_report(days)
- get_execution_history(limit)
"""

import asyncio
import datetime
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger("antigravity.gateway_executor")

# ─────────────────────────────────────────────────────────────────
# Result types
# ─────────────────────────────────────────────────────────────────


@dataclass
class ExecutionResult:
    success: bool
    agent: str
    task: str
    result: str = ""
    error: str = ""
    execution_time_ms: float = 0.0
    tier: str = "unknown"
    metadata: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())

    def to_dict(self) -> dict:
        return {
            "success": self.success,
            "agent": self.agent,
            "task": self.task,
            "result": self.result,
            "error": self.error,
            "execution_time_ms": self.execution_time_ms,
            "tier": self.tier,
            "metadata": self.metadata,
        }


@dataclass
class CostTracker:
    """Tracks execution costs and statistics across agent runs."""

    total_cost: float = 0.0
    execution_count: int = 0
    agent_costs: dict[str, float] = field(default_factory=dict)

    def record_cost(self, agent: str, cost: float) -> None:
        """Record a cost for an agent execution.

        Args:
            agent: Agent name
            cost: Cost value to add
        """
        self.total_cost += cost
        self.execution_count += 1
        self.agent_costs[agent] = self.agent_costs.get(agent, 0.0) + cost

    def get_summary(self) -> dict[str, Any]:
        """Get a summary of tracked costs.

        Returns:
            Dict with total_cost, execution_count, and by_agent breakdown
        """
        return {
            "total_cost": self.total_cost,
            "execution_count": self.execution_count,
            "by_agent": dict(self.agent_costs),
        }

    def reset(self) -> None:
        """Reset all cost tracking."""
        self.total_cost = 0.0
        self.execution_count = 0
        self.agent_costs = {}


# ─────────────────────────────────────────────────────────────────
# GatewayExecutor
# ─────────────────────────────────────────────────────────────────


class GatewayExecutor:
    """
    Synchronous adapter for the gateway.

    Wraps AntigravityOrchestrator and exposes the HTTP Gateway API.
    All public methods are synchronous (gateway runs them in a thread pool).
    """

    def __init__(self, orchestrator: Any = None) -> None:
        if orchestrator is not None:
            self._orch = orchestrator
            self.orchestrator = orchestrator
        else:
            from core.orchestrator import (
                AntigravityOrchestrator,  # type: ignore[import]  # runtime path depends on execution context
            )

            self._orch = AntigravityOrchestrator()
            self.orchestrator = self._orch
        self._history: list[dict[str, Any]] = []
        self.execution_history = self._history  # public alias
        self.cost_tracker = CostTracker()
        if orchestrator is None:
            logger.info("GatewayExecutor initialized with %d agents", len(self._orch.agents))

    # ── Agents discovery ──────────────────────────────────────────

    def get_available_agents(self) -> list[dict[str, Any]]:
        """Return list of agent descriptor dicts for the gateway."""
        agents = []
        base_dir = Path(__file__).parent.parent.parent

        for name, agent in self._orch.agents.items():
            agent_dir = base_dir / ".agent" / "agents" / name
            identity_path = agent_dir / "IDENTITY.md"
            main_path = agent_dir / "main.py"

            agents.append(
                {
                    "name": name,
                    "description": getattr(agent, "description", ""),
                    "skills": getattr(agent, "skills", []),
                    "capabilities": getattr(agent, "capabilities", []),
                    "has_executable": main_path.exists(),
                    "identity_path": str(identity_path),
                    "agent_dir": str(agent_dir),
                    "status": "ready",
                }
            )

        return sorted(agents, key=lambda a: a["name"])

    # ── Agent execution ───────────────────────────────────────────

    async def execute_agent(
        self,
        agent_name: str,
        task: str,
        timeout: int = 120,
        llm_config: dict[str, Any] | None = None,
        persona: str | None = None,
    ) -> "ExecutionResult":
        """Execute an agent task.

        When constructed with an injected orchestrator (DI), delegates to
        orchestrator.execute_task() asynchronously. Otherwise runs the real
        orchestrator in a thread-pool executor to avoid blocking the event loop.

        Args:
            agent_name: Nombre del agente a ejecutar.
            task: Descripcion de la tarea.
            timeout: Timeout en segundos.
            llm_config: Configuracion LLM opcional.
            persona: Modo de persona opcional.
        """
        if asyncio.iscoroutinefunction(getattr(self.orchestrator, "execute_task", None)):
            return await self._execute_agent_async(agent_name, task, timeout)

        # Sync path: run blocking code in thread-pool to not block event loop
        loop = asyncio.get_event_loop()
        start = time.monotonic()

        # Inyectar config LLM y persona como env vars
        saved_env: dict[str, str | None] = {}
        env_overrides: dict[str, str] = {}
        if llm_config:
            if "model" in llm_config:
                env_overrides["ANTIGRAVITY_LLM_MODEL"] = str(llm_config["model"])
            if "max_tokens" in llm_config:
                env_overrides["ANTIGRAVITY_LLM_MAX_TOKENS"] = str(llm_config["max_tokens"])
            if "thinking_level" in llm_config:
                env_overrides["ANTIGRAVITY_LLM_THINKING"] = str(llm_config["thinking_level"])
        if persona:
            env_overrides["ANTIGRAVITY_PERSONA"] = persona

        for key, value in env_overrides.items():
            saved_env[key] = os.environ.get(key)
            os.environ[key] = value

        try:
            return await loop.run_in_executor(
                None, self._execute_agent_inner, agent_name, task, timeout, start
            )
        finally:
            for key, original in saved_env.items():
                if original is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original

    def execute_agent_sync(
        self,
        agent_name: str,
        task: str,
        timeout: int = 120,
        llm_config: dict[str, Any] | None = None,
        persona: str | None = None,
    ) -> "ExecutionResult":
        """Synchronous version for callers that can't use async (e.g., thread-pool callers)."""
        start = time.monotonic()
        saved_env: dict[str, str | None] = {}
        env_overrides: dict[str, str] = {}
        if llm_config:
            if "model" in llm_config:
                env_overrides["ANTIGRAVITY_LLM_MODEL"] = str(llm_config["model"])
            if "max_tokens" in llm_config:
                env_overrides["ANTIGRAVITY_LLM_MAX_TOKENS"] = str(llm_config["max_tokens"])
            if "thinking_level" in llm_config:
                env_overrides["ANTIGRAVITY_LLM_THINKING"] = str(llm_config["thinking_level"])
        if persona:
            env_overrides["ANTIGRAVITY_PERSONA"] = persona
        for key, value in env_overrides.items():
            saved_env[key] = os.environ.get(key)
            os.environ[key] = value
        try:
            return self._execute_agent_inner(agent_name, task, timeout, start)
        finally:
            for key, original in saved_env.items():
                if original is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = original

    async def _execute_agent_async(
        self,
        agent_name: str,
        task: str,
        timeout: int = 120,
    ) -> "ExecutionResult":
        """Async version: delegates to self.orchestrator.execute_task().

        Used when GatewayExecutor is constructed with an injected orchestrator
        that exposes an async execute_task() coroutine.
        """
        import asyncio as _asyncio

        try:
            result_data = await _asyncio.wait_for(
                self.orchestrator.execute_task(agent_name=agent_name, task=task),
                timeout=timeout,
            )
            exec_ms = (
                result_data.get("execution_time_ms", 0.0) if isinstance(result_data, dict) else 0.0
            )
            success = result_data.get("success", True) if isinstance(result_data, dict) else True
            output = (
                result_data.get("output", result_data.get("result", ""))
                if isinstance(result_data, dict)
                else str(result_data)
            )
            cost = result_data.get("cost", 0.001) if isinstance(result_data, dict) else 0.001
            outcome = ExecutionResult(
                success=success,
                agent=agent_name,
                task=task,
                result=str(output)[:10_000],
                execution_time_ms=exec_ms,
            )
        except TimeoutError:
            outcome = ExecutionResult(success=False, agent=agent_name, task=task, error="timeout")
            cost = 0.0005
        except Exception as exc:
            outcome = ExecutionResult(success=False, agent=agent_name, task=task, error=str(exc))
            cost = 0.0005

        self._history.append({**outcome.to_dict(), "timestamp": time.time()})
        self.cost_tracker.record_cost(agent_name, cost=cost)
        return outcome

    def _execute_agent_inner(
        self,
        agent_name: str,
        task: str,
        timeout: int,
        start: float,
    ) -> ExecutionResult:
        """Logica interna de ejecucion de agente (separada para manejo de env vars).

        Args:
            agent_name: Nombre del agente.
            task: Descripcion de la tarea.
            timeout: Timeout en segundos.
            start: Timestamp de inicio (monotonic).
        """
        try:
            # Direct execution for local-executor: bypass orchestrator planner
            if agent_name == "local-executor":
                result_data = self._execute_local_executor(task)
                # local-executor is Tier 3 (Specialized)
                tier = "3"
            else:
                # Generic agent execution via orchestrator
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    result_data = loop.run_until_complete(
                        self._orch.execute(task_description=task)
                    )
                finally:
                    loop.close()
                tier = result_data.get("tier", "unknown") if isinstance(result_data, dict) else "unknown"

            duration_ms = (time.monotonic() - start) * 1000

            # Normalize result
            if isinstance(result_data, dict):
                success = result_data.get("success", True)
                result_text = result_data.get("result", result_data.get("output", ""))
                error = result_data.get("error", "")
            else:
                success = True
                result_text = str(result_data)
                error = ""

            outcome = ExecutionResult(
                success=success,
                agent=agent_name,
                task=task,
                result=str(result_text)[:10_000],
                error=str(error),
                execution_time_ms=duration_ms,
                tier=tier,
            )

        except Exception as exc:
            duration_ms = (time.monotonic() - start) * 1000
            logger.exception("execute_agent(%s) failed", agent_name)
            outcome = ExecutionResult(
                success=False,
                agent=agent_name,
                task=task,
                error=str(exc),
                execution_time_ms=duration_ms,
            )

        # Store in history
        self._history.append(
            {
                **outcome.to_dict(),
                "timestamp": time.time(),
            }
        )
        if len(self._history) > 500:
            self._history = self._history[-500:]

        # Record cost (nominal cost for local agent execution)
        self.cost_tracker.record_cost(agent_name, cost=0.001 if outcome.success else 0.0005)

        return outcome

    def _execute_local_executor(self, task: str) -> dict:
        """Execute local-executor script directly (bypasses orchestrator planner).

        Args:
            task: Task description. Commands can be prefixed with --command or --script.

        Returns:
            Dict with result, success, error keys.
        """
        import subprocess
        import shlex
        import sys
        from pathlib import Path

        script_path = Path(__file__).parent.parent / "agents" / "local-executor" / "scripts" / "local_executor.py"

        if task.startswith("--command "):
            cmd = task[len("--command "):].strip()
            script_path_arg = None
        elif task.startswith("--script "):
            cmd = None
            script_path_arg = task[len("--script "):].strip()
        elif task.startswith("--"):
            # Generic flag parsing
            parts = task.split(maxsplit=1)
            cmd = parts[1] if len(parts) > 1 else ""
            script_path_arg = None
        else:
            cmd = task
            script_path_arg = None

        if script_path_arg:
            # --script: ejecuta script via subprocess con cmd.exe /c
            return self._execute_local_executor_script(script_path_arg)
        if cmd:
            cmd_list = shlex.split(cmd)
            # Windows CMD builtins (echo, cd, set, etc.) only work via cmd.exe /c
            # Full set of Windows builtins: echo, cd, chdir, pushd, popd, set, if,
            # else, for, goto, call, exit, prompt, title, color, path, ver, winver,
            # vol, diskpart, cls
            NEED_CMD = {"echo", "cd", "chdir", "set", "exit", "prompt", "title", "color", "ver", "winver", "vol"}

            use_cmd = cmd_list[0].lower() in NEED_CMD
            try:
                if use_cmd:
                    # Wrap builtin commands with cmd.exe /c
                    proc = subprocess.run(
                        ["cmd", "/c", cmd],
                        capture_output=True,
                        text=True,
                        timeout=min(120, 30),
                        shell=False,
                    )
                    stdout = proc.stdout.strip()
                    stderr = proc.stderr.strip()
                    output = stdout
                else:
                    proc = subprocess.run(
                        [sys.executable, str(script_path)] + cmd_list,
                        capture_output=True,
                        text=True,
                        timeout=min(120, 30),
                        shell=False,
                    )
                    stdout = proc.stdout.strip()
                    stderr = proc.stderr.strip()
                    # Extract actual output after STDOUT: marker from local_executor
                    output = stdout
                    if "STDOUT:" in stdout:
                        idx = stdout.index("STDOUT:")
                        rest = stdout[idx + 6:].strip()
                        lines = rest.split("\n")
                        if lines and lines[0] == ":":
                            output = "\n".join(lines[1:]).strip()
                        else:
                            output = rest.strip()
                    elif proc.returncode != 0 and stderr:
                        output = stderr
                if proc.returncode == 0:
                    return {"success": True, "result": output, "output": output}
                else:
                    return {"success": False, "error": output, "output": output}
            except subprocess.TimeoutExpired:
                return {"success": False, "error": "Timeout (30s) exceeded"}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            # Interactive or info mode
            try:
                proc = subprocess.run(
                    [sys.executable, str(script_path), "--info"],
                    capture_output=True,
                    text=True,
                    timeout=15,
                    shell=False,
                )
                return {"success": proc.returncode == 0, "result": proc.stdout, "output": proc.stdout}
            except Exception as e:
                return {"success": False, "error": str(e)}

    def _execute_local_executor_script(self, script_path_arg: str) -> dict:
        """Execute a script via local-executor.

        Args:
            script_path_arg: Path to script (relative or absolute).

        Returns:
            Dict with result, success, error keys.
        """
        import subprocess

        script_path = Path(__file__).parent.parent / "agents" / "local-executor" / "scripts" / "local_executor.py"
        try:
            proc = subprocess.run(
                [sys.executable, str(script_path), "--script", script_path_arg],
                capture_output=True,
                text=True,
                timeout=min(120, 30),
                shell=False,
            )
            stdout = proc.stdout.strip()
            stderr = proc.stderr.strip()
            if proc.returncode == 0:
                output = stdout
                if "STDOUT:" in stdout:
                    idx = stdout.index("STDOUT:")
                    rest = stdout[idx + 6:].strip()
                    lines = rest.split("\n")
                    if lines and lines[0] == ":":
                        output = "\n".join(lines[1:]).strip()
                    else:
                        output = rest.strip()
                return {"success": True, "result": output, "output": output}
            else:
                return {"success": False, "error": stderr or stdout, "output": stdout}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout (30s) exceeded"}
        except Exception as e:
            return {"success": False, "error": str(e)}

    # ── Agent search ──────────────────────────────────────────────

    async def find_best_agent(
        self,
        task_description: str,
        limit: int = 5,
        constraints: dict[str, Any] | None = None,
    ) -> Any:
        """Find best agents for a task description.

        When constructed with an injected orchestrator, delegates to
        orchestrator.find_best_agent(). Otherwise uses keyword scoring.
        """
        if asyncio.iscoroutinefunction(getattr(self.orchestrator, "find_best_agent", None)):
            return await self.orchestrator.find_best_agent(task_description, constraints)

        agents = self.get_available_agents()
        words = set(task_description.lower().split())

        scored = []
        for agent in agents:
            name_words = set(agent["name"].replace("-", " ").split())
            caps = {c.lower() for c in agent.get("capabilities", [])}
            skills = {s.lower().replace("-", " ") for s in agent.get("skills", [])}
            desc_words = set(agent.get("description", "").lower().split())

            score = (
                len(words & name_words) * 3
                + len(words & caps) * 2
                + len(words & skills) * 2
                + len(words & desc_words)
            )
            if score > 0:
                scored.append({**agent, "score": score})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    def find_best_agent_sync(
        self,
        task_description: str,
        limit: int = 5,
    ) -> list[dict[str, Any]]:
        """Sync version of find_best_agent for thread-pool callers."""
        agents = self.get_available_agents()
        words = set(task_description.lower().split())
        scored = []
        for agent in agents:
            name_words = set(agent["name"].replace("-", " ").split())
            caps = {c.lower() for c in agent.get("capabilities", [])}
            skills = {s.lower().replace("-", " ") for s in agent.get("skills", [])}
            desc_words = set(agent.get("description", "").lower().split())
            score = (
                len(words & name_words) * 3
                + len(words & caps) * 2
                + len(words & skills) * 2
                + len(words & desc_words)
            )
            if score > 0:
                scored.append({**agent, "score": score})
        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    # ── History & cost ────────────────────────────────────────────

    def get_execution_history(self, limit: int = 10) -> list[dict[str, Any]]:
        """Return recent execution history."""
        return list(reversed(self._history[-limit:]))

    def get_cost_report(self, days: int = 30) -> dict[str, Any]:
        """Return simple cost report (no billing data in local mode)."""
        cutoff = time.time() - days * 86400
        recent = [h for h in self._history if h.get("timestamp", 0) >= cutoff]
        return {
            "period_days": days,
            "total_executions": len(recent),
            "successful": sum(1 for h in recent if h.get("success")),
            "failed": sum(1 for h in recent if not h.get("success")),
            "note": "Modo Ollama local — sin costos de API",
        }


# ─────────────────────────────────────────────────────────────────
# Standalone wrapper functions for sync API
# ─────────────────────────────────────────────────────────────────

_executor = GatewayExecutor()


def execute_agent_sync(
    agent_name: str = "",
    task: str = "",
    timeout: int = 300,
    executor: "GatewayExecutor | None" = None,
) -> ExecutionResult:
    """Synchronous wrapper for execute_agent.

    Args:
        agent_name: Name of the agent to execute
        task: Task description
        timeout: Execution timeout in seconds
        executor: Optional GatewayExecutor instance (uses global if not provided)

    Returns:
        ExecutionResult object
    """
    target = executor or _executor
    # execute_agent is now async — run in new event loop
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(target.execute_agent(agent_name, task, timeout))
    except Exception as exc:
        return ExecutionResult(success=False, agent=agent_name, task=task, error=str(exc))
    finally:
        loop.close()


def find_best_agent_sync(
    task_description: str = "",
    limit: int = 5,
    executor: "GatewayExecutor | None" = None,
    constraints: dict[str, Any] | None = None,
) -> Any:
    """Synchronous wrapper for finding best agent.

    Args:
        task_description: Description of the task
        limit: Maximum number of agents to return
        executor: Optional GatewayExecutor instance (uses global if not provided)
        constraints: Optional constraints dict

    Returns:
        Agent result (list or dict depending on orchestrator)
    """
    target = executor or _executor
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(target.find_best_agent(task_description, limit, constraints))
    finally:
        loop.close()


def get_execution_history(limit: int = 10) -> list[dict[str, Any]]:
    """Get recent execution history.

    Args:
        limit: Maximum number of history entries to return

    Returns:
        List of execution history dicts
    """
    return _executor.get_execution_history(limit)


# Alias for gateway.py compatibility
AgentExecutor = GatewayExecutor
