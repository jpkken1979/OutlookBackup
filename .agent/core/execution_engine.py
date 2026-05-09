# mypy: ignore-errors
#!/usr/bin/env python3
"""
Execution Engine
================
Motor de ejecucion que coordina agentes, trackea costos y usa capacidades.

Este modulo conecta:
- Orchestrator (planes de ejecucion)
- Cost Tracker (tracking de tokens/costos)
- Capability Registry (seleccion inteligente)
- Agent scripts (ejecucion real)

Uso:
    from .agent.core.execution_engine import ExecutionEngine, run_task

    # Ejecucion simple
    result = await run_task("Auditar seguridad del codigo")

    # Ejecucion con plan personalizado
    engine = ExecutionEngine()
    plan = engine.create_plan("Crear nueva feature de auth")
    results = await engine.execute_plan(plan)
"""

import asyncio
import contextlib
import json
import logging
import os
import sys
import traceback
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).parent.parent.parent
AGENTS_DIR = Path(__file__).parent.parent / "agents"

# Try imports
try:
    from .cost_tracker import get_tracker

    COST_TRACKER_AVAILABLE = True
except ImportError:
    COST_TRACKER_AVAILABLE = False

    def get_tracker() -> None:
        return None


try:
    from .capability_registry import get_registry

    CAPABILITY_REGISTRY_AVAILABLE = True
except ImportError:
    CAPABILITY_REGISTRY_AVAILABLE = False

    def get_registry() -> None:
        return None


try:
    from .autonomous_learning import get_learning_pipeline

    LEARNING_AVAILABLE = True
except ImportError:
    LEARNING_AVAILABLE = False

    def get_learning_pipeline() -> None:
        return None


try:
    from .feedback import get_feedback_collector

    FEEDBACK_AVAILABLE = True
except ImportError:
    FEEDBACK_AVAILABLE = False

    def get_feedback_collector() -> None:
        return None


try:
    from .intelligence.error_recovery import ErrorRecovery, recover_from_error

    ERROR_RECOVERY_AVAILABLE = True
except ImportError:
    ERROR_RECOVERY_AVAILABLE = False
    ErrorRecovery = None
    recover_from_error = None

try:
    from .shared_memory import get_memory_bus

    MEMORY_BUS_AVAILABLE = True
except ImportError:
    MEMORY_BUS_AVAILABLE = False

    def get_memory_bus() -> None:
        return None


try:
    from .a2a import get_message_bus

    MESSAGE_BUS_AVAILABLE = True
except ImportError:
    MESSAGE_BUS_AVAILABLE = False

    def get_message_bus() -> None:
        return None


class ExecutionStatus(Enum):
    """Estado de ejecucion."""

    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"
    TIMEOUT = "timeout"


class TaskType(Enum):
    """Tipos de tareas reconocidos."""

    NEW_FEATURE = "new_feature"
    BUG_FIX = "bug_fix"
    REFACTOR = "refactor"
    CODE_REVIEW = "code_review"
    SECURITY_AUDIT = "security_audit"
    PERFORMANCE = "performance"
    DOCUMENTATION = "documentation"
    API_DESIGN = "api_design"
    UI_UX = "ui_ux"
    MIGRATION = "migration"
    TESTING = "testing"
    UNKNOWN = "unknown"


@dataclass
class AgentResult:
    """Resultado de ejecucion de un agente."""

    agent_name: str
    task: str
    status: ExecutionStatus
    output: str = ""
    error: str | None = None
    execution_time_ms: int = 0
    tokens_used: int = 0
    cost_usd: float = 0.0
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        d = asdict(self)
        d["status"] = self.status.value
        return d


@dataclass
class ExecutionPlan:
    """Plan de ejecucion multi-agente."""

    task: str
    task_type: TaskType
    agents: list[str]
    parallel_groups: list[list[str]] = field(default_factory=list)
    context: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        d = asdict(self)
        d["task_type"] = self.task_type.value
        return d


@dataclass
class ExecutionReport:
    """Reporte completo de ejecucion."""

    plan: ExecutionPlan
    results: list[AgentResult]
    total_time_ms: int
    total_cost_usd: float
    success_count: int
    failure_count: int
    status: ExecutionStatus

    def to_dict(self) -> dict:
        return {
            "plan": self.plan.to_dict(),
            "results": [r.to_dict() for r in self.results],
            "total_time_ms": self.total_time_ms,
            "total_cost_usd": self.total_cost_usd,
            "success_count": self.success_count,
            "failure_count": self.failure_count,
            "status": self.status.value,
        }


class TaskClassifier:
    """Clasificador de tareas usando keywords."""

    PATTERNS = {
        TaskType.NEW_FEATURE: [
            "crear",
            "nueva",
            "nuevo",
            "agregar",
            "add",
            "implement",
            "feature",
            "funcionalidad",
            "desarrollar",
        ],
        TaskType.BUG_FIX: [
            "bug",
            "fix",
            "error",
            "corregir",
            "arreglar",
            "broken",
            "issue",
            "problema",
            "falla",
        ],
        TaskType.REFACTOR: [
            "refactor",
            "refactorizar",
            "limpiar",
            "clean",
            "mejorar",
            "optimizar",
            "restructurar",
        ],
        TaskType.CODE_REVIEW: [
            "review",
            "revisar",
            "revision",
            "analizar",
            "evaluar",
            "code review",
            "pr review",
        ],
        TaskType.SECURITY_AUDIT: [
            "security",
            "seguridad",
            "vulnerabilidad",
            "owasp",
            "audit",
            "penetration",
            "pentest",
            "xss",
            "injection",
        ],
        TaskType.PERFORMANCE: [
            "performance",
            "rendimiento",
            "optimizar",
            "rapido",
            "lento",
            "slow",
            "fast",
            "benchmark",
            "profiling",
        ],
        TaskType.DOCUMENTATION: [
            "documentar",
            "doc",
            "readme",
            "documentation",
            "comentar",
            "explicar",
            "guia",
        ],
        TaskType.API_DESIGN: [
            "api",
            "endpoint",
            "rest",
            "graphql",
            "swagger",
            "openapi",
            "contrato",
            "schema",
        ],
        TaskType.UI_UX: [
            "ui",
            "ux",
            "design",
            "interfaz",
            "componente",
            "estilo",
            "css",
            "layout",
            "responsive",
        ],
        TaskType.MIGRATION: [
            "migrar",
            "migration",
            "upgrade",
            "actualizar",
            "version",
            "breaking change",
        ],
        TaskType.TESTING: [
            "test",
            "testing",
            "prueba",
            "coverage",
            "jest",
            "pytest",
            "spec",
            "e2e",
        ],
    }

    @classmethod
    def classify(cls, task: str) -> TaskType:
        """Clasifica una tarea por keywords."""
        task_lower = task.lower()
        scores = dict.fromkeys(TaskType, 0)

        for task_type, keywords in cls.PATTERNS.items():
            for keyword in keywords:
                if keyword in task_lower:
                    scores[task_type] += 1

        # Return highest scoring type
        max_score = max(scores.values())
        if max_score > 0:
            for task_type, score in scores.items():
                if score == max_score:
                    return task_type

        return TaskType.UNKNOWN


class ExecutionEngine:
    """Motor de ejecucion de agentes."""

    # Estrategias de agentes por tipo de tarea
    STRATEGIES = {
        TaskType.NEW_FEATURE: [
            ["memory"],  # Cargar contexto
            ["explorer"],  # Investigar codigo existente
            ["architect"],  # Disenar solucion
            ["critic"],  # Validar enfoque
            ["backend-specialist", "frontend-specialist"],  # Implementar (paralelo)
            ["code-reviewer"],  # Revisar
            ["test-engineer"],  # Tests
            ["memory"],  # Guardar contexto
        ],
        TaskType.BUG_FIX: [
            ["memory"],
            ["explorer", "debugger"],  # Investigar (paralelo)
            ["critic"],
            ["backend-specialist"],
            ["test-engineer"],
            ["memory"],
        ],
        TaskType.REFACTOR: [
            ["memory"],
            ["explorer"],
            ["architect"],
            ["refactor"],
            ["code-reviewer"],
            ["test-engineer"],
            ["memory"],
        ],
        TaskType.SECURITY_AUDIT: [
            ["memory"],
            ["explorer"],
            ["security-auditor"],
            ["penetration-tester"],
            ["code-reviewer"],
            ["memory"],
        ],
        TaskType.PERFORMANCE: [
            ["memory"],
            ["explorer"],
            ["performance-optimizer"],
            ["code-reviewer"],
            ["memory"],
        ],
        TaskType.CODE_REVIEW: [["explorer"], ["critic"], ["code-reviewer"], ["security-auditor"]],
        TaskType.API_DESIGN: [
            ["memory"],
            ["explorer"],
            ["api-designer"],
            ["architect"],
            ["critic"],
            ["memory"],
        ],
        TaskType.UI_UX: [
            ["memory"],
            ["explorer"],
            ["ui-ux-designer"],
            ["a11y"],
            ["frontend-specialist"],
            ["memory"],
        ],
        TaskType.DOCUMENTATION: [["explorer"], ["documentation-writer"], ["code-reviewer"]],
        TaskType.MIGRATION: [
            ["memory"],
            ["explorer"],
            ["migrator"],
            ["architect"],
            ["test-engineer"],
            ["memory"],
        ],
        TaskType.TESTING: [["explorer"], ["test-engineer"], ["qa-specialist"], ["code-reviewer"]],
        TaskType.UNKNOWN: [["memory"], ["explorer"], ["planner"], ["memory"]],
    }

    def __init__(
        self,
        timeout_per_agent: int = 120,
        on_agent_start: Callable[[str], None] | None = None,
        on_agent_complete: Callable[[AgentResult], None] | None = None,
    ):
        self.timeout = timeout_per_agent
        self.on_agent_start = on_agent_start
        self.on_agent_complete = on_agent_complete
        self.cost_tracker = get_tracker()
        self.capability_registry = get_registry()
        self._context: dict = {}

        # Initialize unified memory and messaging
        self.memory_bus = get_memory_bus() if MEMORY_BUS_AVAILABLE else None
        self.message_bus = get_message_bus() if MESSAGE_BUS_AVAILABLE else None
        self.error_recovery = ErrorRecovery() if ERROR_RECOVERY_AVAILABLE else None

    def create_plan(self, task: str, custom_agents: list[str] | None = None) -> ExecutionPlan:
        """Crea un plan de ejecucion para una tarea."""
        task_type = TaskClassifier.classify(task)

        if custom_agents:
            agents = custom_agents
            parallel_groups = [[a] for a in agents]  # Sequential by default
        else:
            parallel_groups = self.STRATEGIES.get(task_type, self.STRATEGIES[TaskType.UNKNOWN])
            agents = [agent for group in parallel_groups for agent in group]

        # Use capability registry for better selection if available
        if self.capability_registry and not custom_agents:
            matches = self.capability_registry.find_agents_for_task(task, limit=3)
            if matches:
                # Prepend high-scoring agents not in plan
                existing = set(agents)
                for match in matches:
                    if match.agent not in existing:
                        # Insert after explorer
                        idx = (
                            next((i for i, g in enumerate(parallel_groups) if "explorer" in g), 1)
                            + 1
                        )
                        parallel_groups.insert(idx, [match.agent])
                        agents.insert(idx, match.agent)

        return ExecutionPlan(
            task=task,
            task_type=task_type,
            agents=agents,
            parallel_groups=parallel_groups,
            context=self._context.copy(),
        )

    def _find_agent_script(self, agent_name: str) -> Path | None:
        """Encuentra el script ejecutable de un agente."""
        agent_dir = AGENTS_DIR / agent_name
        if not agent_dir.exists():
            return None

        scripts_dir = agent_dir / "scripts"
        if not scripts_dir.exists():
            return None

        # Try different naming conventions
        candidates = [
            scripts_dir / f"{agent_name.replace('-', '_')}.py",
            scripts_dir / f"{agent_name}.py",
            scripts_dir / "main.py",
        ]

        for candidate in candidates:
            if candidate.exists():
                return candidate

        return None

    async def execute_agent(self, agent_name: str, task: str) -> AgentResult:
        """Ejecuta un agente individual.

        Execution modes (in order of preference):
        1. Autonomous loop (LLM + Tool Use) - if API key available
        2. Script execution (subprocess) - if agent has scripts/
        3. Guidance mode (identity only) - fallback
        """
        start_time = datetime.now()

        if self.on_agent_start:
            self.on_agent_start(agent_name)

        # Try autonomous mode first (real LLM execution)
        autonomous_result = await self._try_autonomous_execution(agent_name, task, start_time)
        if autonomous_result is not None:
            if self.on_agent_complete:
                self.on_agent_complete(autonomous_result)
            return autonomous_result

        script_path = self._find_agent_script(agent_name)

        if not script_path:
            # Return guidance mode
            identity_file = AGENTS_DIR / agent_name / "IDENTITY.md"
            if identity_file.exists():
                content = identity_file.read_text(encoding="utf-8")
                result = AgentResult(
                    agent_name=agent_name,
                    task=task,
                    status=ExecutionStatus.SUCCESS,
                    output=f"[MODO GUIA]\n\n{content}",
                    metadata={"mode": "guidance"},
                )
            else:
                result = AgentResult(
                    agent_name=agent_name,
                    task=task,
                    status=ExecutionStatus.SKIPPED,
                    error=f"Agente '{agent_name}' no tiene script ni IDENTITY.md",
                )

            if self.on_agent_complete:
                self.on_agent_complete(result)
            return result

        # Execute script
        try:
            cmd = [sys.executable, str(script_path), task]

            # Include context from previous agents
            env = {
                **dict(os.environ),
                "ANTIGRAVITY_TASK": task,
                "ANTIGRAVITY_AGENT": agent_name,
                "ANTIGRAVITY_CONTEXT": json.dumps(self._context),
            }

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(BASE_DIR),
                env=env,
            )

            try:
                stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            except TimeoutError:
                proc.kill()
                await proc.wait()
                result = AgentResult(
                    agent_name=agent_name,
                    task=task,
                    status=ExecutionStatus.TIMEOUT,
                    error=f"Timeout despues de {self.timeout}s",
                    execution_time_ms=self.timeout * 1000,
                )
                if self.on_agent_complete:
                    self.on_agent_complete(result)
                return result

            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)
            output = stdout.decode("utf-8", errors="replace")

            # Update context with agent output
            self._context[agent_name] = {
                "output": output[:5000],  # Limit context size
                "status": "success" if proc.returncode == 0 else "failed",
            }

            # Store in MemoryBus for cross-agent sharing
            if self.memory_bus and proc.returncode == 0:
                with contextlib.suppress(Exception):
                    self.memory_bus.store(
                        key=f"agent_result:{agent_name}",
                        value={
                            "output": output[:2000],
                            "task": task[:500],
                            "execution_time_ms": execution_time,
                        },
                        memory_type="context",
                        agent=agent_name,
                    )

            # Broadcast result via MessageBus
            if self.message_bus and proc.returncode == 0:
                with contextlib.suppress(Exception):
                    await self.message_bus.publish(
                        sender=agent_name,
                        topic="result",
                        message={
                            "task": task[:200],
                            "output_preview": output[:500],
                            "execution_time_ms": execution_time,
                        },
                    )

            # Track cost
            if self.cost_tracker:
                estimated_tokens = len(output) // 4
                self.cost_tracker.record_usage(
                    agent=agent_name,
                    model="local-execution",
                    input_tokens=len(task) // 4,
                    output_tokens=estimated_tokens,
                    task_type=str(TaskClassifier.classify(task).value),
                )

            result = AgentResult(
                agent_name=agent_name,
                task=task,
                status=ExecutionStatus.SUCCESS if proc.returncode == 0 else ExecutionStatus.FAILED,
                output=output,
                error=stderr.decode("utf-8", errors="replace") if proc.returncode != 0 else None,
                execution_time_ms=execution_time,
                tokens_used=len(output) // 4,
            )

        except Exception as e:
            error_str = f"Error: {str(e)}\n{traceback.format_exc()}"

            # === ERROR RECOVERY INTEGRATION ===
            recovery_info = None
            if ERROR_RECOVERY_AVAILABLE:
                try:
                    recovery_result = await recover_from_error(
                        error_type=type(e).__name__, error_message=str(e)
                    )
                    if recovery_result and recovery_result.found:
                        recovery_info = {
                            "strategy": recovery_result.strategy.name
                            if recovery_result.strategy
                            else None,
                            "auto_recoverable": recovery_result.auto_recoverable,
                            "steps": [s.description for s in recovery_result.strategy.steps]
                            if recovery_result.strategy
                            else [],
                            "estimated_time": recovery_result.estimated_time,
                            "analysis": recovery_result.error_analysis,
                        }
                except Exception as recovery_error:
                    logging.getLogger("antigravity.error_recovery").warning(
                        f"Recovery lookup failed: {recovery_error}"
                    )

            result = AgentResult(
                agent_name=agent_name,
                task=task,
                status=ExecutionStatus.FAILED,
                error=error_str,
                execution_time_ms=int((datetime.now() - start_time).total_seconds() * 1000),
                metadata={"recovery": recovery_info} if recovery_info else {},
            )

            # Broadcast error via MessageBus if available
            if MESSAGE_BUS_AVAILABLE:
                try:
                    message_bus = get_message_bus()
                    if message_bus:
                        await message_bus.publish(
                            sender=agent_name,
                            topic="error",
                            message={
                                "error_type": type(e).__name__,
                                "message": str(e)[:500],
                                "task": task[:200],
                                "recovery": recovery_info,
                            },
                            priority=1,
                        )
                except Exception:
                    pass

        if self.on_agent_complete:
            self.on_agent_complete(result)

        return result

    async def _try_autonomous_execution(
        self, agent_name: str, task: str, start_time: datetime
    ) -> AgentResult | None:
        """
        Try to execute agent using the autonomous loop (LLM + Tool Use).

        Auto-detects the best available LLM provider (Anthropic, OpenAI,
        Gemini, Ollama). Returns None if no provider is available.
        """
        # Agent must have identity files
        agent_dir = AGENTS_DIR / agent_name
        identity_file = agent_dir / "IDENTITY.md"
        if not identity_file.exists():
            return None

        try:
            from .autonomous_loop import AutonomousLoop, detect_best_provider
            from .llm import LLMProvider

            # Auto-detect best available provider
            config = detect_best_provider()
            if config.provider == LLMProvider.MOCK:
                # No real provider available
                return None

            loop = AutonomousLoop(
                max_iterations=8,
                max_cost_usd=0.50,
                verbose=False,
                provider=config.provider.value,
                model=config.model,
            )

            # Load system prompt from agent identity
            parts = []
            for fname in ["IDENTITY.md", "SYSTEM_PROMPT.md"]:
                fpath = agent_dir / fname
                if fpath.exists():
                    parts.append(fpath.read_text(encoding="utf-8"))

            system_prompt = "\n\n".join(parts)

            # Include context from previous agents
            context_str = None
            if self._context:
                context_parts = []
                for prev_agent, prev_data in self._context.items():
                    if isinstance(prev_data, dict) and prev_data.get("output"):
                        context_parts.append(
                            f"## Results from {prev_agent}:\n{prev_data['output'][:1000]}"
                        )
                if context_parts:
                    context_str = "\n\n".join(context_parts)

            loop_result = await loop.run(
                task=task,
                system_prompt=system_prompt,
                context=context_str,
                agent_name=agent_name,
            )

            execution_time = int((datetime.now() - start_time).total_seconds() * 1000)

            # Update shared context for next agents
            self._context[agent_name] = {
                "output": loop_result.final_output[:5000],
                "status": "success" if loop_result.succeeded else "failed",
            }

            # Store in MemoryBus
            if self.memory_bus:
                with contextlib.suppress(Exception):
                    self.memory_bus.store(
                        key=f"autonomous:{agent_name}",
                        value={
                            "output": loop_result.final_output[:2000],
                            "tools": loop_result.tools_used,
                            "iterations": loop_result.total_iterations,
                        },
                        memory_type="context",
                        agent=agent_name,
                    )

            # If the loop failed (LLM error, bad response, etc.) fall through
            # to the next execution mode (script → guidance) instead of surfacing FAILED.
            if not loop_result.succeeded:
                logging.getLogger("antigravity.engine").warning(
                    f"Autonomous loop failed for {agent_name}, falling back to next mode"
                )
                return None

            return AgentResult(
                agent_name=agent_name,
                task=task,
                status=ExecutionStatus.SUCCESS,
                output=loop_result.final_output,
                execution_time_ms=execution_time,
                tokens_used=loop_result.total_tokens,
                cost_usd=loop_result.total_cost_usd,
                metadata={
                    "mode": "autonomous",
                    "iterations": loop_result.total_iterations,
                    "tools_used": loop_result.tools_used,
                },
            )

        except ImportError:
            return None
        except Exception as e:
            logging.getLogger("antigravity.engine").warning(
                f"Autonomous execution failed for {agent_name}, falling back: {e}"
            )
            return None

    async def execute_parallel_group(self, agents: list[str], task: str) -> list[AgentResult]:
        """Ejecuta un grupo de agentes en paralelo."""
        tasks = [self.execute_agent(agent, task) for agent in agents]
        return await asyncio.gather(*tasks)

    async def execute_plan(self, plan: ExecutionPlan) -> ExecutionReport:
        """Ejecuta un plan completo."""
        start_time = datetime.now()
        all_results: list[AgentResult] = []
        self._context = plan.context.copy()

        for group in plan.parallel_groups:
            results = await self.execute_parallel_group(group, plan.task)
            all_results.extend(results)

            # Check for critical failures
            failures = [r for r in results if r.status == ExecutionStatus.FAILED]
            if failures and "memory" not in group and "explorer" not in group:
                # Non-critical agents failed, continue
                pass

        total_time = int((datetime.now() - start_time).total_seconds() * 1000)
        success_count = sum(1 for r in all_results if r.status == ExecutionStatus.SUCCESS)
        failure_count = sum(1 for r in all_results if r.status == ExecutionStatus.FAILED)
        total_cost = sum(r.cost_usd for r in all_results)

        overall_status = (
            ExecutionStatus.SUCCESS
            if failure_count == 0
            else ExecutionStatus.FAILED
            if success_count == 0
            else ExecutionStatus.SUCCESS  # Partial success
        )

        report = ExecutionReport(
            plan=plan,
            results=all_results,
            total_time_ms=total_time,
            total_cost_usd=total_cost,
            success_count=success_count,
            failure_count=failure_count,
            status=overall_status,
        )

        # === LEARNING LOOP INTEGRATION ===
        # Learn from this execution
        await self._post_execution_learning(report)

        return report

    async def _post_execution_learning(self, report: ExecutionReport) -> None:
        """Post-execution learning hook - learns from every execution."""
        if not LEARNING_AVAILABLE:
            return

        try:
            learning_pipeline = get_learning_pipeline()
            if learning_pipeline is None:
                return

            # Build execution data for learning
            execution_data = {
                "task": report.plan.task,
                "task_type": report.plan.task_type.value,
                "agents_used": [r.agent_name for r in report.results],
                "success": report.status == ExecutionStatus.SUCCESS,
                "duration_ms": report.total_time_ms,
                "steps": [
                    {
                        "agent": r.agent_name,
                        "action": "execute",
                        "status": r.status.value,
                        "duration_ms": r.execution_time_ms,
                    }
                    for r in report.results
                ],
                "context": report.plan.context,
            }

            # Extract patterns from successful executions
            if report.status == ExecutionStatus.SUCCESS:
                await learning_pipeline.extract_patterns([execution_data])

            # Analyze errors from failed executions
            for result in report.results:
                if result.status == ExecutionStatus.FAILED and result.error:
                    await learning_pipeline.analyze_error(
                        {
                            "agent": result.agent_name,
                            "task": result.task,
                            "message": result.error,
                            "context": {"task_type": report.plan.task_type.value},
                        }
                    )

            # Register for feedback collection
            if FEEDBACK_AVAILABLE:
                feedback_collector = get_feedback_collector()
                if feedback_collector:
                    import uuid

                    task_id = str(uuid.uuid4())[:8]
                    await feedback_collector.register_execution(task_id, execution_data)

        except Exception as e:
            # Learning should not break execution
            import logging

            logging.getLogger("antigravity.learning").warning(f"Learning hook failed: {e}")


# Convenience functions
_engine: ExecutionEngine | None = None


def get_engine() -> ExecutionEngine:
    """Obtiene instancia singleton del engine."""
    global _engine
    if _engine is None:
        _engine = ExecutionEngine()
    return _engine


async def run_task(task: str, custom_agents: list[str] | None = None) -> ExecutionReport:
    """Ejecuta una tarea con el engine por defecto."""
    engine = get_engine()
    plan = engine.create_plan(task, custom_agents)
    return await engine.execute_plan(plan)


def run_task_sync(task: str, custom_agents: list[str] | None = None) -> ExecutionReport:
    """Version sincrona de run_task.

    Aplica timeout para evitar bloqueos prolongados en entornos de test o
    cuando un agente queda esperando recursos externos.
    """
    timeout_seconds = float(os.getenv("ANTIGRAVITY_RUN_TASK_SYNC_TIMEOUT", "20"))

    try:
        return asyncio.run(asyncio.wait_for(run_task(task, custom_agents), timeout=timeout_seconds))
    except TimeoutError:
        fallback_plan = ExecutionPlan(
            task=task,
            task_type=TaskType.UNKNOWN,
            agents=custom_agents or [],
            parallel_groups=[custom_agents] if custom_agents else [],
        )
        return ExecutionReport(
            plan=fallback_plan,
            results=[],
            total_time_ms=int(timeout_seconds * 1000),
            total_cost_usd=0.0,
            success_count=0,
            failure_count=1,
            status=ExecutionStatus.TIMEOUT,
        )


# CLI interface
if __name__ == "__main__":
    import argparse

    cli_logger = logging.getLogger("antigravity.execution_engine.cli")

    parser = argparse.ArgumentParser(description="Antigravity Execution Engine")
    parser.add_argument("task", nargs="?", help="Tarea a ejecutar")
    parser.add_argument("--agents", "-a", nargs="+", help="Agentes especificos")
    parser.add_argument("--plan-only", action="store_true", help="Solo mostrar plan")
    parser.add_argument("--json", action="store_true", help="Output en JSON")

    args = parser.parse_args()

    if not args.task:
        cli_logger.info("Uso: python execution_engine.py 'Tu tarea aqui'")
        cli_logger.info("Ejemplos:")
        cli_logger.info("  python execution_engine.py 'Auditar seguridad del codigo'")
        cli_logger.info(
            "  python execution_engine.py 'Crear nueva API' --agents api-designer architect"
        )
        cli_logger.info("  python execution_engine.py 'Refactorizar auth' --plan-only")
        sys.exit(0)

    engine = ExecutionEngine(
        on_agent_start=lambda a: cli_logger.info("[STARTING] %s", a) if not args.json else None,
        on_agent_complete=lambda r: (
            cli_logger.info(
                "[%s] %s (%dms)", r.status.value.upper(), r.agent_name, r.execution_time_ms
            )
            if not args.json
            else None
        ),
    )

    plan = engine.create_plan(args.task, args.agents)

    if args.plan_only:
        if args.json:
            print(json.dumps(plan.to_dict(), indent=2))
        else:
            cli_logger.info("=== Plan de Ejecucion ===")
            cli_logger.info("Tarea: %s", plan.task)
            cli_logger.info("Tipo: %s", plan.task_type.value)
            cli_logger.info("Secuencia de agentes:")
            for i, group in enumerate(plan.parallel_groups, 1):
                if len(group) > 1:
                    cli_logger.info("  %d. [%s] (paralelo)", i, " + ".join(group))
                else:
                    cli_logger.info("  %d. %s", i, group[0])
    else:
        if not args.json:
            cli_logger.info("=== Ejecutando: %s ===", args.task)
        report = run_task_sync(args.task, args.agents)

        if args.json:
            print(json.dumps(report.to_dict(), indent=2))
        else:
            cli_logger.info("=== Reporte Final ===")
            cli_logger.info("Estado: %s", report.status.value)
            cli_logger.info("Tiempo total: %dms", report.total_time_ms)
            cli_logger.info("Exitos: %d", report.success_count)
            cli_logger.info("Fallos: %d", report.failure_count)
            cli_logger.info("Resultados por agente:")
            for r in report.results:
                status_icon = "OK" if r.status == ExecutionStatus.SUCCESS else "X"
                if r.output:
                    cli_logger.info("  [%s] %s: %s...", status_icon, r.agent_name, r.output[:100])
                else:
                    cli_logger.info("  [%s] %s", status_icon, r.agent_name)
