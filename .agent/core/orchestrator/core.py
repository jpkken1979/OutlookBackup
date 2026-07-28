"""Orchestrator principal: la clase AntigravityOrchestrator (4-tier fallback).

Extraido del monolito ``orchestrator.py`` (refactor 2026-06-01). Sin cambios de
comportamiento; los imports relativos a ``core`` pasaron de ``.`` a ``..``.
"""

from __future__ import annotations

import asyncio
import logging
import sys
from collections.abc import Callable
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from ..intelligence_hub import IntelligenceContext, IntelligenceHub

from ..agent_mesh import AgentMesh, get_agent_mesh
from ..memory.unified_memory import UnifiedMemory, get_unified_memory
from ..shared_memory import MemoryBus, get_memory_bus

try:
    from crewai import Agent, Crew, Process, Task

    HAS_CREWAI = True
except ImportError:
    HAS_CREWAI = False

try:
    from ..langgraph_engine import LangGraphEngine

    HAS_LANGGRAPH = LangGraphEngine.is_available()
except ImportError:
    HAS_LANGGRAPH = False

try:
    from ..autonomous_loop import AutonomousLoop

    HAS_AUTONOMOUS_LOOP = True
except ImportError:
    HAS_AUTONOMOUS_LOOP = False

from .models import (
    AGENT_DIR,
    AGENTS_DIR,
    MEMORY_DIR,
    AgentConfig,
    AgentTier,
    ExecutionPlan,
)
from .registry import AGENT_REGISTRY

logger = logging.getLogger("antigravity.orchestrator")


class AntigravityOrchestrator:
    """
    The brain of Antigravity - coordinates all specialist agents.

    Features:
    - Intelligent task decomposition
    - Parallel execution within tiers
    - Shared memory across agents
    - A2A protocol support
    - OpenTelemetry observability
    """

    def __init__(
        self,
        verbose: bool = False,
        max_agents: int = 5,
        enable_memory: bool = True,
        enable_telemetry: bool = True,
        enable_mesh: bool = True,
        enable_memory_bus: bool = True,
    ) -> None:
        self.verbose = verbose
        self.max_agents = max_agents
        self.enable_memory = enable_memory
        self.enable_telemetry = enable_telemetry
        self.enable_mesh = enable_mesh
        self.enable_memory_bus = enable_memory_bus

        self.agents: dict[str, AgentConfig] = AGENT_REGISTRY
        self.memory: UnifiedMemory | None = self._init_memory() if enable_memory else None
        self.memory_bus: MemoryBus | None = self._init_memory_bus() if enable_memory_bus else None
        self.telemetry: dict[str, Any] | None = self._init_telemetry() if enable_telemetry else None
        self.mesh: AgentMesh | None = self._init_mesh() if enable_mesh else None
        self._intelligence_hub: "IntelligenceHub | None" = (  # noqa: UP037
            self._init_intelligence_hub()
        )

        # Pool de skills disponibles (incluye skills de plugins activados)
        self._plugin_skill_pool: dict[str, set[str]] = {}  # plugin_name -> skills
        self._plugin_manager: Any | None = self._init_plugin_manager()

        logger.info("Orchestrator initialized with %d agents", len(self.agents))

    def _init_intelligence_hub(self) -> "IntelligenceHub | None":  # noqa: UP037
        """Initialize Intelligence Hub for data-driven agent selection."""
        try:
            from ..intelligence_hub import get_intelligence_hub

            return get_intelligence_hub()
        except ImportError:
            logger.debug("Intelligence Hub not available")
            return None

    def _init_memory(self) -> UnifiedMemory:
        """Initialize shared memory system."""
        memory = get_unified_memory(MEMORY_DIR)
        return memory

    def _init_plugin_manager(self) -> Any | None:
        """Initialize PluginManager and sync active plugins into skill pool."""
        try:
            from ..plugin_manager import PluginManager, PluginState

            manager = PluginManager(orchestrator=self)
            manager.discover()

            for info in manager.list_plugins(state=PluginState.ACTIVE):
                self.register_plugin_skills(
                    info.metadata.name, manager._get_plugin_skill_names(info)
                )

            logger.info(
                "PluginManager initialized (%d active plugins)",
                len(manager.active_plugins),
            )
            return manager
        except Exception as exc:
            logger.warning("PluginManager not available for orchestrator: %s", exc)
            return None

    def _init_memory_bus(self) -> MemoryBus | None:
        """Initialize memory bus for semantic context when available."""
        try:
            return get_memory_bus(MEMORY_DIR)
        except (ImportError, RuntimeError, OSError) as exc:
            logger.warning("MemoryBus not available: %s", exc)
            return None

    def _init_telemetry(self) -> dict[str, Any] | None:
        """Initialize OpenTelemetry."""
        try:
            from ..telemetry import setup_telemetry

            return setup_telemetry("antigravity.orchestrator")
        except ImportError:
            logger.warning("Telemetry module not available")
            return None

    def _init_mesh(self) -> AgentMesh | None:
        """Initialize agent mesh and register available agents."""
        try:
            mesh = get_agent_mesh()
            if self.memory and hasattr(self.memory, "shared_memory"):
                mesh.set_persistence(self.memory.shared_memory)
            for name, config in self.agents.items():
                mesh.register_agent(
                    agent_name=name,
                    capabilities=config.skills,
                    metadata={"tier": config.tier, "role": config.role},
                )
            return mesh
        except (ImportError, RuntimeError, AttributeError) as exc:
            logger.warning(f"Agent mesh not available: {exc}")
            return None

    # =========================================================================
    # PLUGIN INTEGRATION
    # =========================================================================

    def register_plugin_skills(self, plugin_name: str, skills: list[str]) -> None:
        """Registra las skills de un plugin activado en el pool del orquestador.

        Llamado automáticamente por PluginManager.activate() cuando hay un
        orquestador configurado. Permite que los agentes usen skills de plugins
        sin reiniciar el ecosistema.

        Args:
            plugin_name: Nombre del plugin que se activó.
            skills: Lista de nombres de skills que expone el plugin.
        """
        self._plugin_skill_pool[plugin_name] = set(skills)
        logger.info(
            "Plugin '%s' registered %d skills in orchestrator pool",
            plugin_name,
            len(skills),
        )

    def unregister_plugin_skills(self, plugin_name: str) -> None:
        """Elimina las skills de un plugin desactivado del pool.

        Args:
            plugin_name: Nombre del plugin que se desactivó.
        """
        removed = self._plugin_skill_pool.pop(plugin_name, set())
        if removed:
            logger.info(
                "Plugin '%s' unregistered %d skills from orchestrator pool",
                plugin_name,
                len(removed),
            )

    def get_available_skills(self) -> set[str]:
        """Retorna el conjunto completo de skills disponibles.

        Incluye skills base de los agentes registrados más skills de
        plugins activados.

        Returns:
            Set de nombres de skills disponibles.
        """
        base_skills: set[str] = set()
        for config in self.agents.values():
            base_skills.update(config.skills)

        plugin_skills: set[str] = set()
        for skills in self._plugin_skill_pool.values():
            plugin_skills.update(skills)

        return base_skills | plugin_skills

    def get_plugin_skill_pool(self) -> dict[str, list[str]]:
        """Retorna el mapa de plugin -> skills para inspección.

        Returns:
            Diccionario plugin_name -> lista de skills.
        """
        return {name: sorted(skills) for name, skills in self._plugin_skill_pool.items()}

    def analyze_task(self, task_description: str) -> dict[str, Any]:
        """
        Analyze a task and determine required skills and agents.

        Args:
            task_description: Natural language description of the task

        Returns:
            Analysis with detected skills, complexity, and recommended agents
        """
        # Keyword to skill mapping
        keyword_skills = {
            # Frontend
            "ui": ["react", "ui-design", "tailwind"],
            "frontend": ["react", "nextjs", "typescript"],
            "react": ["react", "nextjs"],
            "component": ["react", "ui-design"],
            "responsive": ["responsive", "tailwind"],
            "accessibility": ["accessibility", "a11y"],
            # Backend
            "api": ["rest", "graphql", "fastapi"],
            "backend": ["nodejs", "python", "fastapi"],
            "auth": ["authentication", "security"],
            "database": ["sql", "schema-design"],
            # Testing
            "test": ["unit-testing", "e2e-testing"],
            "bug": ["debugging", "root-cause-analysis"],
            # DevOps
            "deploy": ["ci-cd", "docker"],
            "docker": ["docker", "kubernetes"],
            "ci": ["ci-cd", "github-actions"],
            # Japanese HR
            "payroll": ["payroll", "japanese-hr"],
            "給与": ["payroll", "japanese-hr"],
            "visa": ["visa-tracking", "compliance"],
            "在留": ["visa-tracking", "compliance"],
            "36協定": ["labor-compliance", "36kyotei"],
            "派遣": ["japanese-business", "compliance"],
            # Excel / Office
            "excel": ["excel-super-agent"],
            "xlsx": ["excel-super-agent"],
            "xlsm": ["excel-super-agent"],
            "kobetsu": ["excel-super-agent"],
            "haken": ["excel-super-agent"],
            "planilla": ["excel-super-agent"],
            "pivot": ["excel-super-agent"],
            "dashboard": ["excel-super-agent"],
            "vba": ["excel-super-agent"],
            "dax": ["excel-super-agent"],
            "power query": ["excel-super-agent"],
            "macro": ["excel-super-agent"],
            "chart": ["excel-super-agent"],
            "formato condicional": ["excel-super-agent"],
            "個別契約": ["excel-super-agent"],
            "勤怠": ["excel-super-agent"],
            "有給": ["excel-super-agent"],
            "賃金": ["excel-super-agent"],
            "履歴書": ["excel-super-agent"],
        }

        task_lower = task_description.lower()
        detected_skills = set()

        for keyword, skills in keyword_skills.items():
            if keyword in task_lower:
                detected_skills.update(skills)

        # Calculate complexity
        if len(detected_skills) > 8:
            complexity = "high"
        elif len(detected_skills) > 4:
            complexity = "medium"
        else:
            complexity = "low"

        return {
            "description": task_description,
            "detected_skills": list(detected_skills),
            "complexity": complexity,
            "analyzed_at": datetime.now().isoformat(),
        }

    def select_agents(
        self, analysis: dict[str, Any], max_agents: int | None = None
    ) -> list[tuple[str, AgentConfig, float]]:
        """
        Select the best agents for a task based on skill matching.

        Args:
            analysis: Task analysis from analyze_task()
            max_agents: Maximum number of agents to select

        Returns:
            List of (agent_name, agent_config, score) tuples
        """
        max_agents = max_agents or self.max_agents
        required_skills = set(analysis.get("detected_skills", []))

        scored_agents: list[tuple[str, AgentConfig, float]] = []
        for name, config in self.agents.items():
            agent_skills = set(config.skills)
            matching = agent_skills & required_skills

            if matching or not required_skills:
                # Score: skill match ratio + tier bonus
                # When no skills required (task didn't match keywords), all agents score via tier bonus
                skill_score = len(matching) / len(required_skills) if required_skills else 0.5
                tier_bonus = (6 - config.tier) * 0.1  # Lower tier = higher priority
                score = skill_score * 0.7 + tier_bonus * 0.3
                scored_agents.append((name, config, round(score, 3)))

        # Sort by score descending
        scored_agents.sort(key=lambda x: x[2], reverse=True)

        # Re-rankear con Intelligence Hub si disponible (datos historicos reales)
        if self._intelligence_hub and scored_agents:
            try:
                candidates = [
                    {"name": name, "tier": cfg.tier, "skills": cfg.skills, "description": cfg.role}
                    for name, cfg, _ in scored_agents
                ]
                ranked = self._intelligence_hub.rank_agents(
                    analysis.get("description", ""), candidates, top_k=max_agents
                )
                # Rebuild con scores del hub (combina skill match + historial)
                hub_order = {r.agent_name: r.score for r in ranked}
                scored_agents.sort(
                    key=lambda x: hub_order.get(x[0], x[2]),
                    reverse=True,
                )
            except Exception as e:
                logger.debug("Intelligence Hub ranking fallback: %s", e)

        return scored_agents[:max_agents]

    def create_execution_plan(
        self, task_description: str, max_agents: int | None = None
    ) -> ExecutionPlan:
        """
        Create a detailed execution plan for a task.

        Args:
            task_description: Natural language task description
            max_agents: Maximum agents to involve

        Returns:
            ExecutionPlan with phases and agent assignments
        """
        import uuid

        analysis = self.analyze_task(task_description)
        selected_agents = self.select_agents(analysis, max_agents)

        # Group agents by tier for parallel execution
        tiers: dict[int, list[dict[str, Any]]] = {}
        for name, config, score in selected_agents:
            tier = config.tier
            if tier not in tiers:
                tiers[tier] = []
            tiers[tier].append(
                {
                    "agent": name,
                    "role": config.role,
                    "score": score,
                    "skills": config.skills[:5],  # Top 5 skills
                }
            )

        # Create phases (sequential between tiers, parallel within)
        phases: list[dict[str, Any]] = []
        for tier in sorted(tiers.keys()):
            agents = tiers[tier]
            phases.append(
                {
                    "phase": tier,
                    "tier_name": AgentTier(tier).name,
                    "parallel": len(agents) > 1,
                    "agents": agents,
                }
            )

        plan = ExecutionPlan(
            id=str(uuid.uuid4())[:8],
            original_task=task_description,
            phases=phases,
            total_agents=len(selected_agents),
            estimated_complexity=analysis["complexity"],
        )

        # Store decision in memory
        if self.memory:
            decision = {
                "plan_id": plan.id,
                "task": task_description,
                "agents": [a[0] for a in selected_agents],
                "timestamp": datetime.now().isoformat(),
            }
            if hasattr(self.memory, "shared_memory"):
                self.memory.shared_memory.store("decision", decision, agent="orchestrator")
            elif hasattr(self.memory, "store"):
                # NOTE: UnifiedMemory.store is async and expects MemoryType enum;
                # this call is a legacy duck-typed fallback that may target a
                # different memory backend.  Suppressed until the caller is fixed.
                self.memory.store("decision", decision, agent="orchestrator")  # type: ignore[arg-type,unused-coroutine]
            if self.memory_bus:
                self.memory_bus.store(
                    key=f"plan:{plan.id}",
                    value=decision,
                    memory_type="decision",
                    agent="orchestrator",
                )

        return plan

    async def execute(
        self,
        task_description: str,
        max_agents: int | None = None,
        dry_run: bool = False,
        callback: Callable[[str], Any] | None = None,
    ) -> dict[str, Any]:
        """
        Execute a task with intelligent agent delegation.

        Args:
            task_description: What to accomplish
            max_agents: Maximum agents to use
            dry_run: If True, only plan without executing
            callback: Optional callback for progress updates

        Returns:
            Execution results with outputs from all agents
        """
        plan = self.create_execution_plan(task_description, max_agents)

        # Pre-ejecucion: consultar Intelligence Hub para contexto
        intel_context: "IntelligenceContext | None" = None  # noqa: UP037
        if self._intelligence_hub:
            try:
                intel_context = self._intelligence_hub.query_intelligence(task_description)
                if intel_context and intel_context.learned_avoidances:
                    logger.info(
                        "Intelligence Hub: %d avoidances detectados para esta tarea",
                        len(intel_context.learned_avoidances),
                    )
            except Exception as e:
                logger.debug("Intelligence Hub pre-ejecucion fallback: %s", e)

        self._print_plan(plan)

        if dry_run:
            logger.info("DRY RUN - No execution performed")
            return {"plan": plan.model_dump(), "dry_run": True}

        # Execute phases sequentially, agents within phase in parallel
        results: list[dict[str, Any]] = []
        for phase in plan.phases:
            phase_results = await self._execute_phase(phase, callback, plan.original_task)
            results.extend(phase_results)

        if self.memory and hasattr(self.memory, "shared_memory"):
            self.memory.shared_memory.add_session_history(
                {
                    "task": task_description,
                    "plan_id": plan.id,
                    "agents": [r.get("agent") for r in results],
                    "completed_at": datetime.now().isoformat(),
                    "results": results,
                }
            )
        if self.memory_bus:
            self.memory_bus.store(
                key=f"execution:{plan.id}",
                value={
                    "task": task_description,
                    "agents": [r.get("agent") for r in results],
                    "completed_at": datetime.now().isoformat(),
                },
                memory_type="context",
                agent="orchestrator",
            )

        return {
            "plan": plan.model_dump(),
            "results": results,
            "completed_at": datetime.now().isoformat(),
        }

    async def _execute_phase(
        self,
        phase: dict[str, Any],
        callback: Callable[[str], Any] | None = None,
        context_input: str = "",
    ) -> list[dict[str, Any]]:
        """Execute all agents in a phase (parallel if multiple)."""
        agents = phase.get("agents", [])

        if phase.get("parallel") and len(agents) > 1:
            # Parallel execution
            coros = [
                self._execute_agent(agent_info, callback, context_input) for agent_info in agents
            ]
            gathered: list[dict[str, Any] | BaseException] = await asyncio.gather(
                *coros,
                return_exceptions=True,
            )
            return [r for r in gathered if isinstance(r, dict)]
        else:
            # Sequential execution
            sequential_results: list[dict[str, Any]] = []
            for agent_info in agents:
                result = await self._execute_agent(agent_info, callback, context_input)
                sequential_results.append(result)
            return sequential_results

    def _should_skip_external_llm(self, context_input: str) -> tuple[bool, bool, str]:
        """Determina si se deben saltar los motores LLM externos.

        Args:
            context_input: Contexto de la tarea.

        Returns:
            Tupla (skip_external_llm, llm_enabled, llm_mode).
        """
        import os

        llm_enabled = os.getenv("ANTIGRAVITY_LLM_ENABLED", "true").lower() not in (
            "false",
            "0",
            "off",
            "no",
        )
        llm_mode = os.getenv("ANTIGRAVITY_LLM_MODE", "auto").lower()

        skip = not llm_enabled or llm_mode == "ide"
        if not HAS_CREWAI:
            skip = True
        if not str(context_input).strip():
            skip = True
        # Only skip ALL tiers if BOTH engines are missing
        if not HAS_CREWAI and not HAS_AUTONOMOUS_LOOP:
            skip = True
        return skip, llm_enabled, llm_mode

    def _record_intelligence_outcome(
        self,
        context_input: str,
        agent_name: str | None,
        success: bool,
        quality_score: float,
        duration: float,
    ) -> None:
        """Registra el resultado en Intelligence Hub si está disponible."""
        if not self._intelligence_hub:
            return
        try:
            self._intelligence_hub.record_outcome(
                task=context_input or "unknown",
                agent_name=agent_name or "unknown",
                success=success,
                quality_score=quality_score,
                duration_ms=int(duration * 1000),
            )
        except Exception:
            pass

    async def _try_crewai_execution(
        self,
        agent_name: str | None,
        agent_config: AgentConfig | None,
        context_input: str,
        start_time: datetime,
    ) -> dict[str, Any] | None:
        """Intenta ejecutar via CrewAI (Tier 1).

        Returns:
            Dict resultado si exitoso, None si falla o no aplica.
        """
        import os

        if not (
            HAS_CREWAI
            and (
                os.getenv("ANTHROPIC_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("OPENROUTER_API_KEY")
                or os.getenv("XAI_API_KEY")
            )
        ):
            return None

        _role = agent_config.role if agent_config else str(agent_name)
        _goal = agent_config.goal if agent_config else ""
        _backstory = self._apply_persona_modifier(agent_config.backstory if agent_config else "")
        _allow_delegation = agent_config.allow_delegation if agent_config else False

        try:
            crew_agent = Agent(
                role=_role,
                goal=_goal,
                backstory=_backstory,
                verbose=self.verbose,
                allow_delegation=_allow_delegation,
            )
            task = Task(
                description=context_input
                or f"Execute the assigned portion of the project: {agent_name}",
                expected_output="Detailed results of the agent's work",
                agent=crew_agent,
            )
            crew = Crew(
                agents=[crew_agent], tasks=[task], process=Process.sequential, verbose=self.verbose
            )

            try:
                result = await asyncio.wait_for(asyncio.to_thread(crew.kickoff), timeout=600.0)
            except TimeoutError as te:
                raise RuntimeError(f"CrewAI execution timed out after 600s: {te}") from te

            duration = (datetime.now() - start_time).total_seconds()
            self._record_intelligence_outcome(context_input, agent_name, True, 0.85, duration)
            return {
                "agent": agent_name,
                "status": "completed",
                "output": str(result),
                "duration_seconds": duration,
                "execution_mode": "crewai",
            }
        except (RuntimeError, ValueError, ConnectionError, TimeoutError, OSError) as e:
            logger.error(f"CrewAI execution failed for {agent_name}: {e}")
            duration = (datetime.now() - start_time).total_seconds()
            self._record_intelligence_outcome(context_input, agent_name, False, 0.0, duration)
            return None

    @staticmethod
    def _apply_persona_modifier(system_prompt: str) -> str:
        """Aplica el modificador de persona al system prompt si ANTIGRAVITY_PERSONA esta definido.

        Args:
            system_prompt: Prompt original del agente.

        Returns:
            Prompt modificado con instrucciones de estilo segun la persona.
        """
        import os

        persona = os.getenv("ANTIGRAVITY_PERSONA", "").lower()
        if not persona or persona == "neutral":
            return system_prompt

        if persona == "jpkken":
            custom = os.getenv("ANTIGRAVITY_PERSONA_CUSTOM", "")
            if custom:
                return system_prompt + f"\n\n[Communication Style: Jpkken — {custom}]"
            return system_prompt

        modifiers = {
            "gentleman": (
                "\n\n[Communication Style: Gentleman — Teach, explain and guide with detail. "
                "Be thorough in your explanations, provide context and reasoning. "
                "Use a warm, educational tone. When presenting options, explain trade-offs.]"
            ),
            "concise": (
                "\n\n[Communication Style: Concise — Minimal answers, no elaboration. "
                "Skip preamble, context, and explanations unless explicitly asked. "
                "Use bullet points over paragraphs. One sentence when one sentence suffices.]"
            ),
        }
        modifier = modifiers.get(persona)
        if modifier:
            return system_prompt + modifier
        return system_prompt

    async def _try_autonomous_loop_execution(
        self,
        agent_name: str | None,
        agent_config: AgentConfig | None,
        context_input: str,
        start_time: datetime,
    ) -> dict[str, Any] | None:
        """Intenta ejecutar via AutonomousLoop (Tier 2).

        Returns:
            Dict resultado si exitoso, None si falla o no aplica.
        """
        import os

        if not (
            HAS_AUTONOMOUS_LOOP
            and agent_config
            and (
                os.getenv("ANTHROPIC_API_KEY")
                or os.getenv("OPENAI_API_KEY")
                or os.getenv("GEMINI_API_KEY")
                or os.getenv("GOOGLE_API_KEY")
                or os.getenv("OPENROUTER_API_KEY")
                or os.getenv("XAI_API_KEY")
            )
        ):
            return None

        try:
            logger.info(f"Agent {agent_name}: using AutonomousLoop fallback (no CrewAI)")
            loop = AutonomousLoop(max_iterations=8, verbose=self.verbose)
            system_prompt = self._apply_persona_modifier(
                f"You are {agent_config.role}. {agent_config.goal}\n\n{agent_config.backstory}"
            )
            try:
                loop_result = await asyncio.wait_for(
                    loop.run(
                        task=context_input or "Execute assigned task",
                        system_prompt=system_prompt,
                        agent_name=str(agent_name) if agent_name else "",
                    ),
                    timeout=600.0,
                )
            except TimeoutError as te:
                raise RuntimeError(f"AutonomousLoop execution timed out after 600s: {te}") from te

            duration = (datetime.now() - start_time).total_seconds()
            self._record_intelligence_outcome(context_input, agent_name, True, 0.75, duration)
            return {
                "agent": agent_name,
                "status": "completed",
                "output": loop_result.final_output or str(loop_result),
                "duration_seconds": duration,
                "execution_mode": "autonomous_loop",
            }
        except (RuntimeError, ValueError, ConnectionError, TimeoutError, OSError) as e:
            logger.warning(f"AutonomousLoop fallback failed for {agent_name}: {e}")
            return None

    async def _try_script_execution(
        self,
        agent_name: str | None,
        context_input: str,
        start_time: datetime,
    ) -> dict[str, Any] | None:
        """Intenta ejecutar el script del agente directamente (Tier 3).

        Returns:
            Dict resultado si exitoso, None si no hay script o falla.
        """
        agent_dir: Path = AGENTS_DIR / str(agent_name)
        scripts_dir: Path = agent_dir / "scripts"
        should_run_script = bool(str(context_input).strip())
        agent_scripts = (
            list(scripts_dir.glob("*.py")) if should_run_script and scripts_dir.exists() else []
        )

        if not agent_scripts:
            return None

        logger.info(f"Agent {agent_name}: executing script directly (no LLM)")
        script = agent_scripts[0]
        try:
            cmd = [sys.executable, str(script)]
            if context_input:
                cmd.append(context_input)
            proc_result = await asyncio.wait_for(
                asyncio.create_subprocess_exec(
                    *cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                ),
                timeout=60.0,
            )
            try:
                stdout, stderr = await asyncio.wait_for(proc_result.communicate(), timeout=60.0)
            except TimeoutError:
                proc_result.kill()
                stdout, stderr = b"", b"Execution timed out after 60s"

            duration = (datetime.now() - start_time).total_seconds()
            success = proc_result.returncode == 0
            output = stdout.decode(errors="replace") if success else stderr.decode(errors="replace")

            self._record_intelligence_outcome(
                context_input,
                agent_name,
                success,
                0.5 if success else 0.2,
                duration,
            )
            return {
                "agent": agent_name,
                "status": "completed" if success else "failed",
                "output": output
                or f"Agent {agent_name} script exited with code {proc_result.returncode}",
                "duration_seconds": duration,
                "execution_mode": "script_direct",
            }
        except (TimeoutError, OSError, RuntimeError) as e:
            logger.warning(f"Script execution failed for {agent_name}: {e}")
            return None

    async def _execute_agent(
        self,
        agent_info: dict[str, Any],
        callback: Callable[[str], Any] | None = None,
        context_input: str = "",
    ) -> dict[str, Any]:
        """Execute a single agent's task."""
        agent_name: str | None = agent_info.get("agent")
        agent_config: AgentConfig | None = self.agents.get(agent_name) if agent_name else None

        if callback:
            callback(f"Executing {agent_name}...")

        logger.info(f"Agent {agent_name} starting execution")
        start_time = datetime.now()

        skip_external_llm, llm_enabled, llm_mode = self._should_skip_external_llm(context_input)

        if skip_external_llm:
            logger.info(
                f"Agent {agent_name}: LLM external disabled "
                f"(llm_enabled={llm_enabled}, llm_mode={llm_mode}, context_input={bool(str(context_input).strip())}). "
                f"Skipping CrewAI/AutonomousLoop."
            )

        # Tier 1: CrewAI
        if not skip_external_llm:
            crewai_result = await self._try_crewai_execution(
                agent_name,
                agent_config,
                context_input,
                start_time,
            )
            if crewai_result:
                return crewai_result

        # Tier 1.5: LangGraph
        if not skip_external_llm and HAS_LANGGRAPH:
            langgraph_result = await self._try_langgraph_execution(
                agent_name, context_input, start_time
            )
            if langgraph_result:
                return langgraph_result

        # Tier 2: AutonomousLoop
        if not skip_external_llm:
            auto_result = await self._try_autonomous_loop_execution(
                agent_name,
                agent_config,
                context_input,
                start_time,
            )
            if auto_result:
                return auto_result

        # Tier 3: Script directo
        script_result = await self._try_script_execution(agent_name, context_input, start_time)
        if script_result:
            return script_result

        # Fallback 4: IDE passthrough or simulated result
        return await self._build_agent_fallback_result(
            agent_name, context_input, start_time, skip_external_llm, llm_mode
        )

    async def _try_langgraph_execution(
        self, agent_name: str | None, context_input: str, start_time: datetime
    ) -> dict[str, Any] | None:
        """Tier 1.5: intenta ejecutar el agente con el motor LangGraph.

        Args:
            agent_name: Nombre del agente a ejecutar.
            context_input: Contexto/tarea para el agente.
            start_time: Marca temporal del inicio de la ejecución.

        Returns:
            Diccionario con el resultado si LangGraph ejecutó, o None si falló.
        """
        try:
            engine = LangGraphEngine(
                agent_dir=AGENT_DIR,
                config={"agents": [agent_name], "max_iterations": 10},
            )
            loop = asyncio.get_event_loop()
            langgraph_result = (
                loop.run_until_complete(
                    engine.execute(context_input or f"Ejecutar tarea de {agent_name}")
                )
                if not loop.is_running()
                else await engine.execute(context_input or f"Ejecutar tarea de {agent_name}")
            )
            duration = (datetime.now() - start_time).total_seconds()
            return {
                "agent": agent_name,
                "status": langgraph_result.get("status", "completed"),
                "output": langgraph_result.get("final_output", str(langgraph_result)),
                "duration_seconds": duration,
                "execution_mode": "langgraph",
                "checkpoint_id": langgraph_result.get("checkpoint_id", ""),
                "iterations": langgraph_result.get("iterations", 0),
            }
        except Exception as e:
            logger.warning("LangGraph execution failed for %s: %s", agent_name, e)
            return None

    def _build_ide_passthrough_result(
        self, agent_name: str | None, context_input: str, duration: float
    ) -> dict[str, Any]:
        """Construye el resultado de passthrough para que la IA del IDE lo procese.

        Args:
            agent_name: Nombre del agente.
            context_input: Tarea/contexto a delegar al IDE.
            duration: Duración transcurrida en segundos.

        Returns:
            Diccionario con la identidad del agente y la tarea para el IDE.
        """
        identity_file: Path = AGENTS_DIR / str(agent_name) / "IDENTITY.md"
        identity_context = ""
        if identity_file.exists():
            identity_context = identity_file.read_text(encoding="utf-8")[:2000]

        logger.info(
            f"Agent {agent_name}: IDE passthrough mode. Returning context for IDE AI to process."
        )

        return {
            "agent": agent_name,
            "status": "ide_passthrough",
            "output": (
                f"[IDE_MODE] Agent {agent_name} context ready.\n\n"
                f"--- AGENT IDENTITY ---\n{identity_context}\n\n"
                f"--- TASK ---\n{context_input or 'No task specified'}\n\n"
                f"The IDE AI (Claude Code, Cursor, etc.) should process this "
                f"using its own intelligence."
            ),
            "duration_seconds": duration,
            "execution_mode": "ide_passthrough",
            "identity_context": identity_context,
            "task": context_input,
        }

    def _build_simulated_result(self, agent_name: str | None, duration: float) -> dict[str, Any]:
        """Construye un resultado simulado cuando no hay ejecución real disponible.

        Args:
            agent_name: Nombre del agente.
            duration: Duración transcurrida en segundos.

        Returns:
            Diccionario con un resultado marcado como simulado.
        """
        logger.warning(
            f"Agent {agent_name}: returning SIMULATED result. "
            f"No script found and no LLM API key available."
        )
        return {
            "agent": agent_name,
            "status": "simulated",
            "output": (
                f"[SIMULATED] Agent {agent_name} - No real execution available. "
                f"Install crewai or set an API key (ANTHROPIC_API_KEY, OPENAI_API_KEY, "
                f"OPENROUTER_API_KEY, or XAI_API_KEY) for real results. "
                f"Or set ANTIGRAVITY_LLM_MODE=ide to use your IDE's AI."
            ),
            "duration_seconds": duration,
            "simulated": True,
            "execution_mode": "simulated",
        }

    async def _build_agent_fallback_result(
        self,
        agent_name: str | None,
        context_input: str,
        start_time: datetime,
        skip_external_llm: bool,
        llm_mode: str,
    ) -> dict[str, Any]:
        """Construye el resultado de fallback cuando ningún tier ejecutó el agente.

        Si el modo es passthrough de IDE devuelve ese resultado; de lo contrario
        simula una ejecución. En ambos casos registra el outcome en el hub de
        inteligencia si está disponible.

        Args:
            agent_name: Nombre del agente que se intentó ejecutar.
            context_input: Contexto/tarea original pasada al agente.
            start_time: Marca temporal del inicio de la ejecución.
            skip_external_llm: Si se omitió el uso de LLM externo.
            llm_mode: Modo de LLM resuelto (por ejemplo ``"ide"``).

        Returns:
            Diccionario con el resultado del fallback (IDE o simulado).
        """
        duration = (datetime.now() - start_time).total_seconds()

        if skip_external_llm and llm_mode == "ide":
            result = self._build_ide_passthrough_result(agent_name, context_input, duration)
        else:
            await asyncio.sleep(0.1)
            duration = (datetime.now() - start_time).total_seconds()
            result = self._build_simulated_result(agent_name, duration)

        if self._intelligence_hub:
            try:
                self._intelligence_hub.record_outcome(
                    task=context_input or "unknown",
                    agent_name=agent_name or "unknown",
                    success=False,
                    quality_score=0.3,
                    duration_ms=int(duration * 1000),
                )
            except Exception:
                pass

        return result

    def _print_plan(self, plan: ExecutionPlan) -> None:
        """Print execution plan to console."""
        logger.info("\n" + "=" * 70)
        logger.info("  ANTIGRAVITY ORCHESTRATOR v3.0")
        logger.info("=" * 70)
        logger.info(f"\n  Task: {plan.original_task}")
        logger.info(f"  Complexity: {plan.estimated_complexity}")
        logger.info(f"  Total Agents: {plan.total_agents}")
        logger.info(f"  Phases: {len(plan.phases)}")

        logger.info("\n" + "-" * 50)
        logger.info("  EXECUTION PLAN:")
        logger.info("-" * 50)

        for phase in plan.phases:
            parallel = " (parallel)" if phase.get("parallel") else ""
            tier_name = phase.get("tier_name", "")
            logger.info(f"\n  Phase {phase['phase']} - {tier_name}{parallel}:")

            for agent in phase.get("agents", []):
                logger.info(f"    - {agent['agent']} (score: {agent['score']:.2f})")
                logger.info(f"      Role: {agent['role']}")

        logger.info("\n" + "=" * 70)


# =============================================================================
