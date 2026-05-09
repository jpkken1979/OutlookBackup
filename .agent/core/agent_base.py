# mypy: ignore-errors
#!/usr/bin/env python3
"""
Antigravity Agent Base - Base class for all Antigravity agents.

Provides:
- Standard agent interface
- Tool integration
- Memory access
- Telemetry instrumentation
- Skill loading
- Intelligence Layer integration (v4.1.0)

Intelligence Capabilities:
- Self-reflection: Evaluate outputs before returning
- Chain-of-thought: Explicit reasoning before action
- Multi-agent debate: Collaborative decision making
- Metacognition: Knowing what you don't know
- Error recovery: Automatic recovery from failures
- Quality scoring: Automated output evaluation
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel, ConfigDict, Field

from core.agent_memory_manager import AgentMemoryManager
from core.agent_skill_manager import AgentSkillManager
from core.agent_tool_manager import AgentToolManager
from core.intelligence_layer import IntelligenceLayer

# Lazy imports para evitar circular dependencies
if TYPE_CHECKING:
    pass

logger = logging.getLogger("antigravity.agent")


def _import_sibling_module(name: str):
    """Lazy-import a sibling module from the core package.

    Args:
        name: Module name relative to core package (e.g. 'telemetry').

    Returns:
        Imported module object.
    """
    import importlib

    return importlib.import_module(f"core.{name}")


# =============================================================================
# AGENT CONFIGURATION
# =============================================================================


class AgentCapabilities(BaseModel):
    """Capabilities configuration for an agent."""

    can_delegate: bool = True
    can_use_tools: bool = True
    can_search_web: bool = False
    can_execute_code: bool = False
    can_access_files: bool = True
    max_iterations: int = 15
    max_rpm: int = 10  # Requests per minute


class AgentIdentity(BaseModel):
    """Identity configuration for an agent."""

    name: str
    role: str
    goal: str
    backstory: str
    tier: int = 2
    skills: list[str] = Field(default_factory=list)


# =============================================================================
# TOOL INTERFACE
# =============================================================================


class Tool(BaseModel):
    """Definition of a tool that an agent can use."""

    name: str
    description: str
    func: Callable | None = None
    args_schema: dict | None = None
    return_direct: bool = False

    model_config = ConfigDict(arbitrary_types_allowed=True)


class ToolResult(BaseModel):
    """Result from tool execution."""

    success: bool
    output: Any
    error: str | None = None
    execution_time_ms: float = 0


# =============================================================================
# ANTIGRAVITY AGENT BASE CLASS
# =============================================================================


class AntigravityAgent(ABC):
    """
    Base class for all Antigravity agents.

    Provides common functionality:
    - Tool registration and execution
    - Memory access
    - Telemetry
    - Skill loading
    - Standard execution flow
    - Intelligence Layer (v4.1.0): reflection, reasoning, debate

    Intelligence Methods:
    - reflect(): Evaluar outputs antes de devolver
    - reason(): Razonamiento paso a paso
    - debate(): Debate multi-agente para decisiones
    - assess_confidence(): Metacognición
    - score_quality(): Puntuación de calidad
    """

    def __init__(
        self,
        identity: AgentIdentity,
        capabilities: AgentCapabilities | None = None,
        memory: Any | None = None,
        verbose: bool = False,
        orchestrator: Any | None = None,
        enable_intelligence: bool = True,
    ):
        self.identity = identity
        self.capabilities = capabilities or AgentCapabilities()
        self.memory = memory
        self.verbose = verbose
        self.orchestrator = orchestrator

        self.tools: dict[str, Tool] = {}
        self.skills_loaded: list[str] = []
        self.execution_history: list[dict] = []

        # Initialize managers
        self.tool_manager = AgentToolManager(self)
        self.memory_manager = AgentMemoryManager(self)
        self.skill_manager = AgentSkillManager(self)

        # Intelligence Layer (v4.1.0)
        self.intelligence: IntelligenceLayer | None = None
        if enable_intelligence:
            self.intelligence = IntelligenceLayer(agent_name=identity.name, verbose=verbose)

        self._setup_default_tools()
        logger.info(
            f"Agent {identity.name} initialized (intelligence={'enabled' if enable_intelligence else 'disabled'})"
        )

    # =========================================================================
    # TOOL MANAGEMENT (delegated to AgentToolManager)
    # =========================================================================

    def register_tool(self, tool: Tool) -> None:
        """Register a tool for this agent to use."""
        self.tool_manager.register_tool(tool)
        self.tools[tool.name] = tool  # Keep sync for backward compatibility

    def _setup_default_tools(self) -> None:
        """Setup default tools available to all agents."""
        self.tool_manager.setup_default_tools()
        # Sync to self.tools dict for backward compatibility
        for name, tool in self.tool_manager.tools.items():
            self.tools[name] = tool

    async def use_tool(self, tool_name: str, **kwargs) -> ToolResult:
        """
        Execute a registered tool (delegated to AgentToolManager).

        Args:
            tool_name: Name of the tool to execute
            **kwargs: Arguments for the tool

        Returns:
            ToolResult with output or error
        """
        return await self.tool_manager.use_tool(tool_name, **kwargs)

    # =========================================================================
    # SKILL LOADING
    # =========================================================================

    def load_skill(self, skill_name: str, skills_dir: Path | None = None) -> bool:
        """Load a skill and its associated tools (delegates to skill_manager)."""
        return self.skill_manager.load_skill(skill_name, skills_dir)

    def _run_skill_script(self, script_path: Path) -> str:
        """Run a skill script and return output (delegates to skill_manager)."""
        return self.skill_manager._run_skill_script(script_path)

    # =========================================================================
    # MEMORY ACCESS (delegated to AgentMemoryManager)
    # =========================================================================

    def remember(self, key: str, value: Any) -> None:
        """Store something in agent's memory (delegated)."""
        self.memory_manager.remember(key, value)

    def recall(self, key: str) -> Any | None:
        """Recall something from agent's memory (delegated)."""
        return self.memory_manager.recall(key)

    def get_relevant_context(self, query: str, limit: int = 5) -> list[str]:
        """Get relevant context from vector memory (delegated)."""
        return self.memory_manager.get_relevant_context(query, limit)

    # =========================================================================
    # INTELLIGENCE LAYER (v4.1.0)
    # =========================================================================

    async def reflect(self, task: str, output: Any) -> Any | None:
        """
        Reflexiona sobre el output antes de devolverlo.

        Evalúa: completitud, corrección, claridad, accionabilidad, seguridad.

        Args:
            task: La tarea ejecutada
            output: El resultado a evaluar

        Returns:
            ReflectionResult con evaluación y sugerencias

        Example:
            result = await self.execute("Design API")
            reflection = await self.reflect("Design API", result)
            if reflection and reflection.should_retry:
                result = await self.execute("Design API", context={"hints": reflection.retry_suggestions})
        """
        if not self.intelligence:
            return None
        return await self.intelligence.reflect(task, output)

    async def reason(self, task: str, context: dict | None = None) -> Any | None:
        """
        Razonamiento paso a paso antes de actuar.

        Produce una cadena de pensamientos explícita que puede depurarse.

        Args:
            task: La tarea a razonar
            context: Contexto adicional

        Returns:
            ChainOfThoughtResult con pasos de razonamiento

        Example:
            reasoning = await self.reason("Design authentication system")
            for step in reasoning.steps:
                print(f"{step.step_num}. {step.thought}")
            # Usar reasoning.final_conclusion para la decisión
        """
        if not self.intelligence:
            return None
        return await self.intelligence.reason(task, context)

    async def debate(self, question: str, perspectives: list[str] | None = None) -> Any | None:
        """
        Debate multi-agente para decisiones críticas.

        Simula múltiples perspectivas discutiendo una decisión.

        Args:
            question: La decisión a debatir
            perspectives: Agentes/roles a simular (default: architect, security, performance)

        Returns:
            DebateResult con consenso, argumentos y votos

        Example:
            result = await self.debate(
                "¿Microservices o Monolith?",
                perspectives=["architect", "devops", "security"]
            )
            if result.consensus_reached:
                # Usar result.consensus_position
            else:
                # Considerar result.dissenting_views
        """
        if not self.intelligence:
            return None
        return await self.intelligence.debate(question, perspectives)

    async def assess_confidence(self, task: str, output: Any) -> Any | None:
        """
        Metacognición: evalúa qué tan seguro está el agente de su respuesta.

        Args:
            task: La tarea ejecutada
            output: El resultado producido

        Returns:
            ConfidenceAssessment con nivel de certeza

        Example:
            assessment = await self.assess_confidence("Optimize query", result)
            if assessment.confidence < 0.5:
                # Considerar escalar a humano o pedir más contexto
        """
        if not self.intelligence:
            return None
        return await self.intelligence.assess_confidence(task, output)

    async def score_quality(self, task: str, output: Any) -> Any | None:
        """
        Puntúa la calidad del output automáticamente.

        Args:
            task: La tarea ejecutada
            output: El resultado a evaluar

        Returns:
            QualityScore con puntuación detallada (0.0 a 1.0)
        """
        if not self.intelligence:
            return None
        return await self.intelligence.score_quality(task, output)

    async def recover_from_error(self, error: Exception, context: dict) -> Any | None:
        """
        Intenta recuperarse automáticamente de un error.

        Args:
            error: La excepción que ocurrió
            context: Contexto de ejecución

        Returns:
            RecoveryResult con estrategia aplicada
        """
        if not self.intelligence:
            return None
        return await self.intelligence.recover_from_error(error, context)

    async def predict_escalation(self, task: str, signals: list[str]) -> Any | None:
        """
        Predice si la tarea actual debería escalarse a otro agente o humano.

        Args:
            task: La tarea actual
            signals: Señales de riesgo observadas

        Returns:
            EscalationPrediction indicando nivel y probabilidad
        """
        if not self.intelligence:
            return None
        return await self.intelligence.predict_escalation(task, signals)

    # =========================================================================
    # AUTONOMOUS EXECUTION (v5.0)
    # =========================================================================

    async def run_autonomous(
        self,
        task: str,
        context: dict | None = None,
        max_iterations: int = 10,
        verbose: bool | None = None,
    ) -> dict:
        """
        Execute a task autonomously using LLM + tool use loop.

        This is the key method that makes agents truly autonomous.
        The agent will:
        1. Think about the task
        2. Decide which tool to call
        3. Execute the tool
        4. Observe the result
        5. Repeat until done

        Args:
            task: Task to accomplish
            context: Optional context from memory or other agents
            max_iterations: Maximum tool-use cycles
            verbose: Override verbose setting

        Returns:
            Dict with output, steps, tokens, cost, and status

        Example:
            result = await agent.run_autonomous("Find all TODO comments")
            print(result["output"])
            print(f"Used {result['iterations']} iterations, ${result['cost']:.4f}")
        """
        autonomous_loop_module = _import_sibling_module("autonomous_loop")
        AutonomousLoop = autonomous_loop_module.AutonomousLoop
        build_default_tools = autonomous_loop_module.build_default_tools

        loop = AutonomousLoop(
            max_iterations=max_iterations,
            verbose=verbose if verbose is not None else self.verbose,
        )

        # Build system prompt
        system_prompt = self.get_system_prompt()

        # Build context string
        context_str = None
        if context:
            context_str = "\n".join(
                f"## {k}\n{v}" for k, v in context.items() if isinstance(v, str)
            )

        # Build tool executor that uses this agent's registered tools
        async def agent_tool_executor(tool_name: str, tool_input: dict) -> str:
            if tool_name in self.tools:
                result = await self.use_tool(tool_name, **tool_input)
                if result.success:
                    return str(result.output)
                return f"Tool error: {result.error}"
            # Fall back to loop's default executor
            return await loop._default_tool_executor(tool_name, tool_input)

        result = await loop.run(
            task=task,
            system_prompt=system_prompt,
            tools=build_default_tools(),
            tool_executor=agent_tool_executor,
            context=context_str,
            agent_name=self.identity.name,
        )

        # Store in execution history
        self.execution_history.append(
            {
                "task": task,
                "mode": "autonomous",
                "result": result.to_dict(),
                "timestamp": datetime.now().isoformat(),
            }
        )

        # Save to memory if available
        if self.memory and hasattr(self.memory, "store"):
            self.memory.store(
                "agent_execution",
                {
                    "agent": self.identity.name,
                    "task": task,
                    "status": result.status.value,
                    "tools_used": result.tools_used,
                    "iterations": result.total_iterations,
                },
            )

        return {
            "output": result.final_output,
            "success": result.succeeded,
            "iterations": result.total_iterations,
            "tokens": result.total_tokens,
            "cost": result.total_cost_usd,
            "tools_used": result.tools_used,
            "steps": [s.to_dict() for s in result.steps],
            "status": result.status.value,
        }

    # =========================================================================
    # EXECUTION
    # =========================================================================

    @abstractmethod
    async def execute(self, task: str, context: dict | None = None) -> dict:
        """
        Execute a task.

        Args:
            task: Task description
            context: Optional execution context

        Returns:
            Execution result dict
        """
        pass

    async def run(
        self,
        task: str,
        context: dict | None = None,
        use_reflection: bool = True,
        use_reasoning: bool = False,
        max_retries: int = 1,
    ) -> dict:
        """
        Run the agent with telemetry, error handling, and intelligence.

        Args:
            task: Task to execute
            context: Optional context
            use_reflection: Reflexionar sobre output antes de devolver (default: True)
            use_reasoning: Usar Chain-of-Thought antes de ejecutar (default: False)
            max_retries: Reintentos si la reflexión sugiere mejorar (default: 1)

        Returns:
            Execution result with optional intelligence metadata
        """
        telemetry_module = _import_sibling_module("telemetry")
        record_agent_execution = telemetry_module.record_agent_execution
        trace_agent_execution = telemetry_module.trace_agent_execution

        start_time = datetime.now()
        execution_context = context or {}
        attempts = 0

        # Pre-razonamiento si está habilitado
        reasoning_result = None
        if use_reasoning and self.intelligence:
            reasoning_result = await self.reason(task, execution_context)
            if reasoning_result:
                execution_context["reasoning"] = {
                    "conclusion": reasoning_result.final_conclusion,
                    "confidence": reasoning_result.overall_confidence,
                    "key_insights": reasoning_result.key_insights,
                }
                logger.info(
                    f"Pre-razonamiento completado: confianza {reasoning_result.overall_confidence:.2f}"
                )

        with trace_agent_execution(self.identity.name, task):
            while attempts <= max_retries:
                attempts += 1
                try:
                    result = await self.execute(task, execution_context)
                    success = True

                    # Reflexión post-ejecución
                    reflection_result = None
                    if use_reflection and self.intelligence and success:
                        reflection_result = await self.reflect(task, result)

                        if reflection_result:
                            # Agregar metadata de reflexión
                            if isinstance(result, dict):
                                result["_intelligence"] = {
                                    "reflection": {
                                        "confidence": reflection_result.overall_confidence,
                                        "should_retry": reflection_result.should_retry,
                                        "blind_spots": reflection_result.blind_spots[:3],
                                        "assumptions": reflection_result.assumptions[:3],
                                    }
                                }

                            # Reintentar si la reflexión lo sugiere y quedan intentos
                            if reflection_result.should_retry and attempts <= max_retries:
                                logger.info(
                                    f"Reflexión sugiere reintentar (intento {attempts}/{max_retries + 1})"
                                )
                                execution_context["retry_hints"] = (
                                    reflection_result.retry_suggestions
                                )
                                continue

                    break  # Salir del loop si todo OK

                except (RuntimeError, ValueError, ConnectionError, TimeoutError, OSError) as e:
                    logger.error(f"Agent {self.identity.name} failed: {e}")

                    # Intentar recuperación inteligente
                    if self.intelligence and attempts <= max_retries:
                        recovery = await self.recover_from_error(
                            e, {"task": task, "context": execution_context}
                        )
                        if recovery and recovery.recovered:
                            logger.info(f"Recuperación exitosa: {recovery.strategy}")
                            execution_context["recovery_hints"] = recovery.suggestions
                            continue

                    result = {"error": str(e), "success": False}
                    success = False
                    break

        duration = (datetime.now() - start_time).total_seconds()

        # Record metrics
        record_agent_execution(
            agent_name=self.identity.name, duration_seconds=duration, success=success
        )

        # Agregar metadata de ejecución
        if isinstance(result, dict):
            result["_execution"] = {
                "attempts": attempts,
                "duration_seconds": duration,
                "used_reasoning": use_reasoning,
                "used_reflection": use_reflection,
            }

        # Store in history
        self.execution_history.append(
            {
                "task": task,
                "result": result,
                "duration": duration,
                "attempts": attempts,
                "timestamp": datetime.now().isoformat(),
            }
        )

        return result

    # =========================================================================
    # DELEGATION
    # =========================================================================

    async def delegate_to(
        self, agent_name: str, task: str, context: dict | None = None
    ) -> dict | None:
        """
        Delegate a task to another agent.

        Args:
            agent_name: Name of agent to delegate to
            task: Task description
            context: Optional context

        Returns:
            Result from delegated agent or None if failed
        """
        if not self.capabilities.can_delegate:
            logger.warning(f"Agent {self.identity.name} cannot delegate")
            return None

        logger.info(f"Delegating to {agent_name}: {task[:50]}...")

        # Use orchestrator if available for actual delegation
        if self.orchestrator is not None:
            try:
                # Check if target agent exists in orchestrator registry
                if hasattr(self.orchestrator, "agents") and agent_name in self.orchestrator.agents:
                    agent_config = self.orchestrator.agents[agent_name]
                    logger.info(
                        f"Found agent '{agent_name}' (tier {agent_config.tier}, "
                        f"role: {agent_config.role})"
                    )

                    # Execute via orchestrator if execute method is available
                    if hasattr(self.orchestrator, "execute"):
                        result = await self.orchestrator.execute(
                            task_description=task, max_agents=1, dry_run=False
                        )
                        return {
                            "delegated_to": agent_name,
                            "task": task,
                            "status": "completed",
                            "result": result,
                            "delegating_agent": self.identity.name,
                        }
                    else:
                        # Orchestrator doesn't have execute, use simulated delegation
                        logger.info(
                            "Orchestrator doesn't support execute, using simulated delegation"
                        )
                        return {
                            "delegated_to": agent_name,
                            "task": task,
                            "status": "delegated",
                            "agent_config": {
                                "role": agent_config.role,
                                "tier": agent_config.tier,
                                "skills": agent_config.skills,
                            },
                            "delegating_agent": self.identity.name,
                        }
                else:
                    logger.warning(f"Agent '{agent_name}' not found in orchestrator registry")
                    return {
                        "delegated_to": agent_name,
                        "task": task,
                        "status": "failed",
                        "error": f"Agent '{agent_name}' not found in registry",
                        "delegating_agent": self.identity.name,
                    }
            except (RuntimeError, ValueError, ConnectionError, TimeoutError, KeyError) as e:
                logger.error(f"Delegation to {agent_name} failed: {e}")
                return {
                    "delegated_to": agent_name,
                    "task": task,
                    "status": "failed",
                    "error": str(e),
                    "delegating_agent": self.identity.name,
                }

        # Fallback: No orchestrator available, return pending status
        logger.info("No orchestrator available, delegation queued as pending")
        return {
            "delegated_to": agent_name,
            "task": task,
            "status": "pending",
            "delegating_agent": self.identity.name,
            "note": "No orchestrator configured - task queued for manual processing",
        }

    # =========================================================================
    # UTILITIES
    # =========================================================================

    def get_system_prompt(self) -> str:
        """Generate the system prompt for this agent."""
        tools_list = "\n".join(
            [f"- {name}: {tool.description}" for name, tool in self.tools.items()]
        )

        return f"""# {self.identity.role}

## Goal
{self.identity.goal}

## Backstory
{self.identity.backstory}

## Available Tools
{tools_list}

## Skills Loaded
{", ".join(self.skills_loaded) or "None"}

## Guidelines
- Focus on your specific expertise
- Use tools when needed
- Provide clear, actionable outputs
- Ask for clarification if task is unclear
"""

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__} name={self.identity.name}>"


# =============================================================================
# CONCRETE AGENT IMPLEMENTATION
# =============================================================================


class SimpleAgent(AntigravityAgent):
    """
    Simple agent implementation for basic tasks.

    This can be used directly or as a reference for custom agents.
    """

    async def execute(self, task: str, context: dict | None = None) -> dict:
        """Execute a task using basic reasoning."""
        logger.info(f"{self.identity.name} executing: {task[:50]}...")

        # Simple task analysis
        task_lower = task.lower()

        # File operations
        if "read" in task_lower and "file" in task_lower:
            # Extract file path (simple heuristic)
            words = task.split()
            for _i, word in enumerate(words):
                if "." in word and "/" in word:
                    result = await self.use_tool("read_file", path=word)
                    return {"output": result.output, "success": result.success}

        # Search operations
        if "search" in task_lower or "find" in task_lower:
            # Extract search pattern
            pattern = task.split("for")[-1].strip() if "for" in task_lower else task
            result = await self.use_tool("search_codebase", pattern=pattern[:50])
            return {"output": result.output, "success": result.success}

        # Default: return task acknowledgment
        return {
            "output": f"Task received by {self.identity.name}: {task}",
            "agent": self.identity.name,
            "role": self.identity.role,
            "success": True,
        }


# =============================================================================
# CLI
# =============================================================================


def main():
    """Test agent base class."""

    def run_async(coroutine: Any) -> Any:
        """Ejecuta corrutinas de forma segura incluso si asyncio.run está mockeado."""
        try:
            return asyncio.run(coroutine)
        finally:
            if asyncio.iscoroutine(coroutine):
                coroutine.close()

    logger.info("Testing Antigravity Agent Base...")

    # Create a simple agent
    identity = AgentIdentity(
        name="test-agent",
        role="Test Agent",
        goal="Test the agent base class functionality",
        backstory="I am a test agent created to verify the system works.",
        skills=["testing", "verification"],
    )

    agent = SimpleAgent(identity=identity, verbose=True)

    # Show system prompt
    logger.info("--- System Prompt ---")
    logger.debug(agent.get_system_prompt())

    # Test tool listing
    logger.info("--- Available Tools ---")
    for name, tool in agent.tools.items():
        logger.debug("  %s: %s", name, tool.description)

    # Test execution
    logger.info("--- Execution Test ---")
    result = run_async(agent.run("Search for TODO comments"))
    logger.info("Result: %s", result)

    # Test delegation without orchestrator
    logger.info("--- Delegation Test (no orchestrator) ---")
    delegation_result = run_async(agent.delegate_to("frontend-specialist", "Build a login form"))
    logger.info("Delegation result: %s", delegation_result)

    # Test delegation with mock orchestrator
    logger.info("--- Delegation Test (with orchestrator) ---")
    try:
        orchestrator_module = _import_sibling_module("orchestrator")
        AntigravityOrchestrator = orchestrator_module.AntigravityOrchestrator

        orchestrator = AntigravityOrchestrator(verbose=False)
        agent_with_orch = SimpleAgent(identity=identity, orchestrator=orchestrator)
        delegation_result = run_async(
            agent_with_orch.delegate_to("frontend-specialist", "Build a login form")
        )
        logger.info("Delegation result: %s", delegation_result)
    except ImportError:
        logger.warning("Orchestrator not available for testing")

    logger.info("Agent base tests complete!")


if __name__ == "__main__":
    main()
