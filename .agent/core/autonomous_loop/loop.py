# mypy: ignore-errors
"""Motor ReAct: clase AutonomousLoop y entry-point run_autonomous.

Extraido del monolito ``autonomous_loop.py`` (refactor 2026-05-31). Sin cambios
de comportamiento. Ajustes necesarios por el cambio de profundidad del paquete:
- los imports relativos a ``core`` pasaron de ``.`` a ``..``
- los ``Path(__file__).parent.parent`` pasaron a ``.parent.parent.parent``
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from .models import LoopResult, LoopStatus, LoopStep, StepType
from .paths import _get_writable_roots, _is_path_in_writable_roots
from .providers import detect_best_provider
from .tools import build_default_tools

logger = logging.getLogger("antigravity.autonomous")

try:
    try:
        from intelligence_hub import get_intelligence_hub
    except ImportError:
        from ..intelligence_hub import get_intelligence_hub
    INTELLIGENCE_HUB_AVAILABLE = True
except ImportError:
    INTELLIGENCE_HUB_AVAILABLE = False


class AutonomousLoop:
    """
    ReAct-style autonomous agent loop.

    Connects LLM reasoning with tool execution in an iterative cycle.
    The agent thinks about what to do, calls tools, observes results,
    and continues until the task is complete.
    """

    def __init__(
        self,
        llm_client: Any = None,
        max_iterations: int = 15,
        max_cost_usd: float = 1.0,
        verbose: bool = False,
        on_step: Any = None,
        provider: str | None = None,
        model: str | None = None,
    ):
        """
        Args:
            llm_client: LLMClient instance (lazy-created if None)
            max_iterations: Maximum tool-use iterations before stopping
            max_cost_usd: Maximum cost before stopping (safety limit)
            verbose: Print steps to console
            on_step: Optional callback(LoopStep) for each step
            provider: Force a specific provider ("anthropic", "openai", "ollama", "gemini").
                      If None, auto-detects best available provider.
            model: Override model name. If None, uses provider's default.
        """
        self._llm_client = llm_client
        self._provider_override = provider
        self._model_override = model
        self.max_iterations = max_iterations
        self.max_cost_usd = max_cost_usd
        self.verbose = verbose
        self.on_step = on_step

    @property
    def llm(self):
        """Lazy-load LLM client with auto-detection of best available provider."""
        if self._llm_client is None:
            try:
                from llm import LLMClient
            except ImportError:
                from ..llm import LLMClient
            config = detect_best_provider(
                provider_override=self._provider_override,
                model_override=self._model_override,
            )
            self._llm_client = LLMClient(config)
            if self.verbose:
                logger.info(f"  LLM: {config.provider.value} / {config.model}")
        return self._llm_client

    def _query_intelligence_context(self, task: str) -> None:
        """Consulta Intelligence Hub para contexto previo de la tarea.

        Args:
            task: Descripción de la tarea.
        """
        if not INTELLIGENCE_HUB_AVAILABLE:
            return
        try:
            hub = get_intelligence_hub()
            intelligence_context = hub.query_intelligence(task)
            if intelligence_context and intelligence_context.risk_level > 0.5:
                logger.warning(
                    f"Intelligence Hub: riesgo elevado ({intelligence_context.risk_level:.2f}) para esta tarea"
                )
            if intelligence_context and intelligence_context.learned_avoidances:
                avoidance_info = "\n".join(
                    f"- {a}" for a in intelligence_context.learned_avoidances[:3]
                )
                logger.info(f"Intelligence Hub: evitar patrones conocidos:\n{avoidance_info}")
        except Exception as e:
            logger.debug(f"Intelligence Hub no disponible: {e}")

    async def _execute_single_tool(
        self,
        tool_call: dict,
        tool_executor: Any,
        agent_name: str,
        step_num: int,
        tools_used: list[str],
    ) -> tuple[dict, LoopStep | None, LoopStatus | None, int]:
        """Ejecuta una sola llamada a herramienta.

        Args:
            tool_call: Dict con id, name, input.
            tool_executor: Callable para ejecutar la herramienta.
            agent_name: Nombre del agente.
            step_num: Número de paso actual.
            tools_used: Lista acumuladora de herramientas usadas.

        Returns:
            Tupla (tool_result_dict, step_or_none, status_override_or_none, new_step_num).
        """
        tool_name = tool_call["name"]
        tool_input = tool_call["input"]
        tool_id = tool_call["id"]

        # Check for task_complete signal
        if tool_name == "task_complete":
            step_num += 1
            step = LoopStep(
                step_num=step_num,
                step_type=StepType.FINAL_ANSWER,
                content=tool_input.get("summary", "Task completed"),
                tool_name="task_complete",
                tool_input=tool_input,
            )
            self._emit_step(step)
            result_dict = {
                "type": "tool_result",
                "tool_use_id": tool_id,
                "content": "Task marked as complete.",
            }
            return result_dict, step, LoopStatus.STOPPED_BY_AGENT, step_num

        # Execute the tool
        step_num += 1
        tool_start = time.time()
        try:
            if inspect.iscoroutinefunction(tool_executor):
                tool_output = await tool_executor(tool_name, tool_input)
            else:
                tool_output = tool_executor(tool_name, tool_input)
            tool_output_str = str(tool_output) if tool_output is not None else ""
        except Exception as e:
            tool_output_str = f"Error executing {tool_name}: {e}"
            logger.warning(tool_output_str)

        tool_duration = (time.time() - tool_start) * 1000

        call_step = LoopStep(
            step_num=step_num,
            step_type=StepType.TOOL_CALL,
            content=f"Calling {tool_name}",
            tool_name=tool_name,
            tool_input=tool_input,
            tool_output=tool_output_str[:5000],
            duration_ms=tool_duration,
        )
        self._emit_step(call_step)

        if tool_name not in tools_used:
            tools_used.append(tool_name)

        self._emit_tool_telemetry(agent_name, tool_name, tool_input, tool_output_str)

        result_dict = {
            "type": "tool_result",
            "tool_use_id": tool_id,
            "content": tool_output_str[:10000],
        }
        return result_dict, call_step, None, step_num

    def _emit_tool_telemetry(
        self,
        agent_name: str,
        tool_name: str,
        tool_input: Any,
        tool_output_str: str,
    ) -> None:
        """Inyecta telemetría de herramienta para el Dashboard.

        Args:
            agent_name: Nombre del agente.
            tool_name: Nombre de la herramienta.
            tool_input: Input de la herramienta.
            tool_output_str: Output como string.
        """
        try:
            try:
                from agent_mesh import AgentRequest, RequestType, ResponseStatus, get_agent_mesh
            except ImportError:
                from ..agent_mesh import AgentRequest, RequestType, ResponseStatus, get_agent_mesh

            mesh = get_agent_mesh()
            if not hasattr(mesh, "request_history"):
                return
            telemetry_req = AgentRequest(
                from_agent=agent_name or "AutoLoop",
                to_agent=f"tool:{tool_name}",
                request_type=RequestType.DELEGATE,
                payload={"input": tool_input},
            )
            telemetry_req.status = (
                ResponseStatus.COMPLETED
                if "Error" not in tool_output_str[:20]
                else ResponseStatus.ERROR
            )
            mesh.request_history.append(telemetry_req)

            if hasattr(mesh, "_shared_memory") and mesh._shared_memory is not None:
                if hasattr(mesh._shared_memory, "add_session_history"):
                    mesh._shared_memory.add_session_history(
                        {
                            "type": "a2a_request",
                            "request": telemetry_req.to_dict(),
                            "timestamp": datetime.now().isoformat(),
                        }
                    )
        except Exception as _e:
            logger.debug("Modulo opcional no disponible: %s", _e)

    @staticmethod
    def _extract_final_output(steps: list[LoopStep]) -> str:
        """Extrae el output final de los pasos ejecutados.

        Args:
            steps: Lista de pasos del loop.

        Returns:
            Texto del output final.
        """
        for step in reversed(steps):
            if step.step_type == StepType.FINAL_ANSWER:
                return step.content
            if step.step_type == StepType.THOUGHT and step.content:
                return step.content
        return steps[-1].content if steps else ""

    def _record_intelligence_hub_outcome(self, task: str, agent_name: str, result: Any) -> None:
        """Registra el resultado en Intelligence Hub.

        Args:
            task: Descripción de la tarea.
            agent_name: Nombre del agente.
            result: LoopResult con el resultado.
        """
        if not INTELLIGENCE_HUB_AVAILABLE:
            return
        try:
            hub = get_intelligence_hub()
            succeeded = result.succeeded if hasattr(result, "succeeded") else bool(result)
            hub.record_outcome(
                task=task,
                agent_name=agent_name or "autonomous",
                success=succeeded,
                quality_score=0.8 if succeeded else 0.3,
                duration_ms=int(getattr(result, "total_duration_ms", 0)),
                skills_used=getattr(result, "tools_used", []),
                error_type=str(getattr(result, "error", "")) if not succeeded else "",
            )
        except Exception as e:
            logger.debug(f"Intelligence Hub record_outcome error: {e}")

    async def _call_llm(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict],
        step_num: int,
    ) -> tuple[Any, LoopStep | None]:
        """Invoca al LLM capturando errores como un LoopStep de diagnóstico.

        Args:
            system_prompt: Prompt de sistema del agente.
            messages: Historial de mensajes de la conversación.
            tools: Definiciones de herramientas en formato Anthropic.
            step_num: Número del último step emitido (para enumerar el error).

        Returns:
            Tupla ``(response, error_step)``. Si la llamada tuvo éxito,
            ``error_step`` es ``None``. Si falló, ``response`` es ``None`` y
            ``error_step`` es un LoopStep de tipo THOUGHT con el error.
        """
        try:
            response = await self.llm.generate(
                prompt="",
                system=system_prompt,
                messages=messages,
                tools=tools,
            )
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return None, LoopStep(
                step_num=step_num + 1,
                step_type=StepType.THOUGHT,
                content=f"Error calling LLM: {e}",
            )
        return response, None

    def _emit_thought_step(self, response: Any, steps: list[LoopStep], step_num: int) -> int:
        """Emite un step de pensamiento si la respuesta trae contenido textual.

        Args:
            response: Respuesta del LLM con ``content`` y ``usage``.
            steps: Lista de steps de la ejecución (mutada in-place).
            step_num: Número del último step emitido.

        Returns:
            El ``step_num`` actualizado (incrementado solo si se emitió el step).
        """
        if not response.content:
            return step_num
        step_num += 1
        thought_step = LoopStep(
            step_num=step_num,
            step_type=StepType.THOUGHT,
            content=response.content,
            tokens_used=response.usage.total_tokens,
            cost_usd=response.usage.cost_usd,
        )
        steps.append(thought_step)
        self._emit_step(thought_step)
        return step_num

    def _build_assistant_content(self, response: Any) -> list[dict]:
        """Construye el bloque de contenido del mensaje assistant.

        Args:
            response: Respuesta del LLM con ``content`` y ``tool_calls``.

        Returns:
            Lista de bloques (texto opcional + un ``tool_use`` por tool call).
        """
        assistant_content: list[dict] = []
        if response.content:
            assistant_content.append({"type": "text", "text": response.content})
        for tool_call in response.tool_calls:
            assistant_content.append(
                {
                    "type": "tool_use",
                    "id": tool_call["id"],
                    "name": tool_call["name"],
                    "input": tool_call["input"],
                }
            )
        return assistant_content

    async def _run_tool_calls(
        self,
        response: Any,
        messages: list[dict],
        steps: list[LoopStep],
        tool_executor: Any,
        agent_name: str,
        step_num: int,
        tools_used: list[str],
        status: LoopStatus,
    ) -> tuple[int, LoopStatus]:
        """Ejecuta todas las tool calls de una respuesta y acumula resultados.

        Mantiene la semántica del loop original: agrega los resultados al
        historial de mensajes, anexa los steps generados y corta ante el primer
        ``status_override`` devuelto por una herramienta.

        Args:
            response: Respuesta del LLM con las ``tool_calls`` a ejecutar.
            messages: Historial de mensajes (mutado in-place al anexar resultados).
            steps: Lista de steps de la ejecución (mutada in-place).
            tool_executor: Callable que ejecuta una herramienta.
            agent_name: Nombre del agente para logging.
            step_num: Número del último step emitido.
            tools_used: Lista acumulada de herramientas usadas (mutada in-place).
            status: Estado actual del loop.

        Returns:
            Tupla ``(step_num, status)`` actualizada tras procesar las tool calls.
        """
        tool_results_content: list[dict] = []
        for tool_call in response.tool_calls:
            result_dict, call_step, status_override, step_num = await self._execute_single_tool(
                tool_call,
                tool_executor,
                agent_name,
                step_num,
                tools_used,
            )
            tool_results_content.append(result_dict)
            if call_step:
                steps.append(call_step)
            if status_override:
                status = status_override
                break

        if tool_results_content:
            messages.append({"role": "user", "content": tool_results_content})

        return step_num, status

    async def run(
        self,
        task: str,
        system_prompt: str,
        tools: list[dict] | None = None,
        tool_executor: Any = None,
        context: str | None = None,
        agent_name: str = "",
    ) -> LoopResult:
        """
        Execute the autonomous loop.

        Args:
            task: The task to accomplish
            system_prompt: Agent's system prompt (identity + capabilities)
            tools: Tool definitions (Anthropic API format). If None, uses defaults.
            tool_executor: Async callable(tool_name, tool_input) -> str. If None, uses built-in.
            context: Optional context from memory or previous agents
            agent_name: Name of the agent for logging

        Returns:
            LoopResult with all steps and final output
        """
        start_time = time.time()
        steps: list[LoopStep] = []
        tools = tools or build_default_tools()
        tool_executor = tool_executor or self._default_tool_executor
        total_tokens = 0
        total_cost = 0.0
        tools_used: list[str] = []
        step_num = 0

        user_message = task
        if context:
            user_message = f"## Context from previous agents/memory:\n{context}\n\n## Task:\n{task}"

        messages = [{"role": "user", "content": user_message}]
        self._query_intelligence_context(task)

        if self.verbose:
            self._print_header(agent_name, task)

        iteration = 0
        status = LoopStatus.RUNNING

        while iteration < self.max_iterations and status == LoopStatus.RUNNING:
            iteration += 1

            if total_cost >= self.max_cost_usd:
                logger.warning(f"Cost limit reached: ${total_cost:.4f} >= ${self.max_cost_usd}")
                status = LoopStatus.MAX_ITERATIONS
                break

            response, error_step = await self._call_llm(system_prompt, messages, tools, step_num)
            if error_step is not None:
                step_num += 1
                steps.append(error_step)
                status = LoopStatus.ERROR
                break

            total_tokens += response.usage.total_tokens
            total_cost += response.usage.cost_usd

            if not response.has_tool_calls:
                step_num += 1
                step = LoopStep(
                    step_num=step_num,
                    step_type=StepType.FINAL_ANSWER,
                    content=response.content,
                    tokens_used=response.usage.total_tokens,
                    cost_usd=response.usage.cost_usd,
                )
                steps.append(step)
                self._emit_step(step)
                status = LoopStatus.COMPLETED
                break

            step_num = self._emit_thought_step(response, steps, step_num)

            messages.append(
                {"role": "assistant", "content": self._build_assistant_content(response)}
            )

            step_num, status = await self._run_tool_calls(
                response,
                messages,
                steps,
                tool_executor,
                agent_name,
                step_num,
                tools_used,
                status,
            )

            if status != LoopStatus.RUNNING:
                break

        if status == LoopStatus.RUNNING:
            status = LoopStatus.MAX_ITERATIONS

        total_duration = (time.time() - start_time) * 1000
        final_output = self._extract_final_output(steps)

        result = LoopResult(
            status=status,
            final_output=final_output,
            steps=steps,
            total_iterations=iteration,
            total_tokens=total_tokens,
            total_cost_usd=total_cost,
            total_duration_ms=total_duration,
            tools_used=tools_used,
            agent_name=agent_name,
            task=task,
        )

        await self._post_execution_learning(result)
        self._record_intelligence_hub_outcome(task, agent_name, result)

        if self.verbose:
            self._print_summary(result)

        return result

    # =========================================================================
    # DEFAULT TOOL EXECUTOR
    # =========================================================================

    def _build_tool_handlers(self, tool_input: dict) -> dict:
        """Construye el mapa de handlers de herramientas para el input dado.

        Args:
            tool_input: Diccionario con los argumentos de la herramienta.

        Returns:
            Diccionario que mapea el nombre de la herramienta a un callable sin
            argumentos que devuelve un str o un awaitable de str.
        """
        return {
            "read_file": lambda: self._exec_read_file(tool_input.get("path", "")),
            "write_file": lambda: self._exec_write_file(
                tool_input.get("path", ""), tool_input.get("content", "")
            ),
            "search_codebase": lambda: self._exec_search(
                tool_input.get("pattern", ""), tool_input.get("path", ".")
            ),
            "execute_command": lambda: self._exec_command(tool_input.get("command", "")),
            "delegate_to_agent": lambda: self._exec_delegate(
                tool_input.get("agent_name", ""), tool_input.get("subtask", "")
            ),
            "decompose_task": lambda: self._exec_decompose(
                tool_input.get("task", ""), tool_input.get("max_subtasks", 5)
            ),
            "mcts_speculative_execution": lambda: self._exec_mcts(tool_input.get("task", "")),
            "find_best_agent": lambda: self._exec_find_best_agent(
                tool_input.get("task_description", "")
            ),
            "search_skills": lambda: self._exec_search_skills(
                tool_input.get("query", ""), tool_input.get("limit", 20)
            ),
            "read_skill": lambda: self._exec_read_skill(tool_input.get("skill_name", "")),
            "ast_code_radar": lambda: self._exec_ast_code_radar(
                tool_input.get("action", ""), tool_input.get("target", "")
            ),
            "blackboard_write": lambda: self._exec_blackboard_write(
                tool_input.get("topic", ""), tool_input.get("content", "")
            ),
            "blackboard_read": lambda: self._exec_blackboard_read(
                tool_input.get("topic", ""), tool_input.get("timeout_seconds", 120)
            ),
            "auto_heal_mcp": lambda: self._exec_auto_heal_mcp(tool_input.get("action", "")),
        }

    async def _default_tool_executor(self, tool_name: str, tool_input: dict) -> str:
        """Default tool executor using built-in agent tools."""
        handler = self._build_tool_handlers(tool_input).get(tool_name)
        if handler is None:
            return f"Unknown tool: {tool_name}"

        result = handler()
        if inspect.isawaitable(result):
            return await result
        return result

    def _exec_find_best_agent(self, query: str) -> str:
        try:
            from ..capability_registry import get_registry

            registry = get_registry()
            matches = registry.find_best_agents(query, limit=5)
            return json.dumps(
                [
                    {"name": m["name"], "score": m["score"], "skills": m.get("skills")}
                    for m in matches
                ],
                indent=2,
            )
        except Exception as e:
            return f"Error finding agent: {e}"

    def _exec_search_skills(self, query: str, limit: int = 20) -> str:
        """Search skills using centralized SkillRegistry if available."""
        try:
            try:
                normalized_limit = max(1, min(int(limit), 100))
            except (TypeError, ValueError):
                normalized_limit = 20

            # Try centralized registry first (O(1) cached search)
            try:
                from ..skill_registry import SkillRegistry

                registry = SkillRegistry.instance()
                search_results = registry.search(query, k=normalized_limit)
                results = [name for name, _ in search_results]
            except Exception as _e:
                # Fallback to manual directory search
                logger.debug("Skill registry search failed, falling back to directory: %s", _e)
                skills_dir = Path(__file__).parent.parent.parent / "skills"
                q = query.lower()
                results = []
                if skills_dir.exists():
                    for d in skills_dir.iterdir():
                        if d.is_dir() and not d.name.startswith("_"):
                            if q in d.name.lower():
                                results.append(d.name)
                results = results[:normalized_limit]

            return json.dumps(results, indent=2) if results else "No skills matched."
        except Exception as e:
            return f"Error searching skills: {e}"

    def _exec_read_skill(self, skill_name: str) -> str:
        """Read skill SKILL.md using centralized SkillRegistry if available."""
        try:
            # Try centralized registry first (O(1) lookup)
            try:
                from ..skill_registry import SkillRegistry

                registry = SkillRegistry.instance()
                skill = registry.get(skill_name, lazy=True)
                if skill and skill.path:
                    skill_path = skill.path / "SKILL.md"
                    if skill_path.exists():
                        return skill_path.read_text(encoding="utf-8", errors="replace")
            except Exception as _e:
                logger.debug("Modulo opcional no disponible: %s", _e)  # Fallback to manual search

            # Fallback to manual directory search
            skills_dir = Path(__file__).parent.parent.parent / "skills"
            skill_path = skills_dir / skill_name / "SKILL.md"
            if skill_path.exists():
                content = skill_path.read_text(encoding="utf-8", errors="replace")
                return content

            custom_dir = Path(__file__).parent.parent.parent / "skills-custom"
            custom_path = custom_dir / skill_name / "SKILL.md"
            if custom_path.exists():
                return custom_path.read_text(encoding="utf-8", errors="replace")

            return f"Skill not found: {skill_name}"
        except Exception as e:
            return f"Error reading skill: {e}"

    async def _exec_mcts(self, task: str) -> str:
        """FASE 1: MCTS Speculative Execution"""
        try:
            from ..mcts_executor import MCTSExecutor

            # self.llm is available inside the AutonomousLoop
            executor = MCTSExecutor(llm_client=self.llm, max_branches=3)
            best_node = await executor.run_speculative_execution(task)

            # Format the output for the agent
            output = "=== MCTS SPECULATIVE EXECUTION WINNER ===\n"
            output += f"Approach: {best_node.approach_description}\n"
            output += f"Score: {best_node.evaluation_score}/10\n"
            output += f"Code:\n{best_node.code_proposal}\n"
            return output
        except Exception as e:
            return f"MCTS Execution Failed: {str(e)}"

    def _exec_ast_code_radar(self, action: str, target: str) -> str:
        try:
            from ..ast_radar import run_ast_radar

            return run_ast_radar(action, target)
        except Exception as e:
            return f"Error running AST Radar: {e}"

    def _exec_blackboard_write(self, topic: str, content: str) -> str:
        try:
            import json

            from ..blackboard import global_blackboard

            # Intenta parsearlo de JSON si lo mandan en string; si falla que se suba como raw.
            try:
                data = {"raw": content} if not content.startswith("{") else json.loads(content)
            except (json.JSONDecodeError, ValueError):
                data = {"raw": content}

            msg_id = global_blackboard.post_message(
                topic, self.agent_name if hasattr(self, "agent_name") else "agent", data
            )
            return f"Success: Data posted to blackboard topic '{topic}' with ID {msg_id}."
        except Exception as e:
            return f"Error writing to blackboard: {e}"

    def _exec_blackboard_read(self, topic: str, timeout_seconds: int = 120) -> str:
        try:
            import json

            from ..blackboard import global_blackboard

            data = global_blackboard.wait_for_data(
                topic, timeout_seconds=timeout_seconds, poll_interval=2.0
            )
            if data:
                return f"SUCCESS: Received data from topic '{topic}':\n" + json.dumps(
                    data, indent=2
                )
            else:
                return f"TIMEOUT: Waited {timeout_seconds}s for '{topic}' but received no data."
        except Exception as e:
            return f"Error reading from blackboard: {e}"

    async def _exec_auto_heal_mcp(self, action: str) -> str:
        try:
            from ..mcp_healer import MCPHealer

            healer = MCPHealer(llm_client=self.llm)
            if action == "diagnose_crash":
                return await healer.auto_diagnose_and_heal()
            elif action == "restart_processes":
                return healer.restart_mcp_servers()
            else:
                return "Acción inválida. Usa 'diagnose_crash' o 'restart_processes'."
        except Exception as e:
            return f"Error executing Auto-Healer: {str(e)}"

    def _exec_read_file(self, path: str) -> str:
        """Read a file safely."""
        try:
            file_path = Path(path)
            if not file_path.exists():
                return f"File not found: {path}"
            content = file_path.read_text(encoding="utf-8")
            if len(content) > 20000:
                return content[:20000] + f"\n\n... [truncated, {len(content)} total chars]"
            return content
        except OSError as e:
            return f"Error reading {path}: {e}"

    def _exec_write_file(self, path: str, content: str) -> str:
        """Write a file safely within WRITABLE_ROOTS boundaries."""
        writable_roots = _get_writable_roots()
        file_path = Path(path).resolve()

        if not _is_path_in_writable_roots(file_path, writable_roots):
            roots_str = ", ".join(str(r) for r in writable_roots)
            return f"PermissionError: Path outside WRITABLE_ROOTS: {path!r} (allowed: {roots_str})"

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            return f"Written {len(content)} bytes to {path}"
        except OSError as e:
            return f"Error writing {path}: {e}"

    def _exec_search(self, pattern: str, path: str = ".") -> str:
        """Search codebase using grep."""
        import subprocess

        try:
            result = subprocess.run(
                [
                    "grep",
                    "-rn",
                    "--include=*.py",
                    "--include=*.ts",
                    "--include=*.md",
                    pattern,
                    path,
                ],
                capture_output=True,
                text=True,
                timeout=30,
            )
            output = result.stdout
            if not output:
                return f"No matches found for: {pattern}"
            lines = output.strip().split("\n")
            if len(lines) > 50:
                return "\n".join(lines[:50]) + f"\n\n... [{len(lines)} total matches]"
            return output
        except FileNotFoundError:
            # Fallback for Windows where grep might not be installed
            return self._exec_search_python_fallback(pattern, path)
        except Exception as e:
            return f"Search error: {e}"

    def _scan_file_for_matches(
        self, file_path: Path, rx: re.Pattern[str], matches: list[str], limit: int
    ) -> bool:
        """Acumula coincidencias de un archivo en la lista compartida.

        Args:
            file_path: Archivo a inspeccionar línea por línea.
            rx: Patrón compilado a buscar en cada línea.
            matches: Lista compartida donde se acumulan los resultados (mutada in-place).
            limit: Cantidad máxima de coincidencias antes de cortar.

        Returns:
            True si se alcanzó el límite y hay que detener el escaneo global.
        """
        try:
            text = file_path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            return False
        for i, line in enumerate(text.splitlines(), 1):
            if rx.search(line):
                matches.append(f"{file_path}:{i}:{line}")
                if len(matches) > limit:
                    return True
        return False

    def _exec_search_python_fallback(self, pattern: str, path: str = ".") -> str:
        """Busca el patrón en archivos del árbol usando Python puro (sin grep).

        Fallback para entornos (p. ej. Windows) donde ``grep`` no está disponible.

        Args:
            pattern: Expresión regular a buscar.
            path: Directorio raíz desde donde recorrer recursivamente.

        Returns:
            Texto con las coincidencias encontradas o un mensaje descriptivo.
        """
        import re

        limit = 50
        matches: list[str] = []
        try:
            rx = re.compile(pattern)
            p = Path(path)
            for f in p.rglob("*"):
                if f.is_file() and f.suffix in [".py", ".ts", ".md"]:
                    if self._scan_file_for_matches(f, rx, matches, limit):
                        break
                if len(matches) > limit:
                    break
            if not matches:
                return f"No matches found for: {pattern} (Python fallback)"
            res = "\n".join(matches)
            if len(matches) > limit:
                res += "\n\n... [>50 matches, truncated]"
            return res
        except Exception as pe:
            return f"Search fallback error: {pe}"

    async def _exec_command(self, command: str) -> str:
        """Execute a command safely."""
        import shlex

        # Safety checks
        dangerous = ["rm -rf /", "mkfs", ":(){:|:&};:", "> /dev/sd", "dd if="]
        for pattern in dangerous:
            if pattern in command:
                return f"Blocked dangerous command pattern: {pattern}"

        try:
            cmd_parts = shlex.split(command)
        except ValueError as e:
            return f"Invalid command: {e}"

        try:
            # Note: create_subprocess_exec might fail on Windows for shell built-ins.
            # If so, it falls back to create_subprocess_shell
            import sys

            if sys.platform == "win32" and cmd_parts[0] not in ["python", "pip", "uv", "git"]:
                proc = await asyncio.create_subprocess_shell(
                    command,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                proc = await asyncio.create_subprocess_exec(
                    *cmd_parts,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )

            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=60)
            output = stdout.decode("utf-8", errors="replace")
            if proc.returncode != 0:
                output += f"\n[stderr] {stderr.decode('utf-8', errors='replace')}"
            return output[:10000]
        except TimeoutError:
            return "Command timed out after 60s"
        except Exception as e:
            return f"Command error: {e}"

    # =========================================================================
    # DELEGATION & DECOMPOSITION (Level 2-3 Autonomy)
    # =========================================================================

    async def _exec_delegate(self, agent_name: str, subtask: str) -> str:
        """
        Delegate a subtask to another agent (inter-agent communication).

        This creates a nested autonomous loop for the delegated agent,
        enabling true multi-agent collaboration at runtime.
        """
        if not agent_name or not subtask:
            return "Error: agent_name and subtask are required"

        agents_dir = Path(__file__).parent.parent.parent / "agents" / agent_name

        if not agents_dir.exists():
            return f"Agent '{agent_name}' not found. Available agents are in .agent/agents/"

        # Load the delegated agent's identity
        identity_parts = []
        identity_file = agents_dir / "IDENTITY.md"
        prompt_file = agents_dir / "SYSTEM_PROMPT.md"

        if identity_file.exists():
            identity_parts.append(identity_file.read_text(encoding="utf-8"))
        if prompt_file.exists():
            identity_parts.append(prompt_file.read_text(encoding="utf-8"))

        if not identity_parts:
            return f"Agent '{agent_name}' has no identity files"

        delegate_prompt = "\n\n".join(identity_parts)

        # Run a nested autonomous loop with fewer iterations (prevent runaway)
        delegate_loop = AutonomousLoop(
            llm_client=self._llm_client,
            max_iterations=min(self.max_iterations // 2, 5),
            max_cost_usd=self.max_cost_usd / 3,
            verbose=self.verbose,
        )

        try:
            result = await delegate_loop.run(
                task=subtask,
                system_prompt=delegate_prompt,
                agent_name=agent_name,
            )

            # Format response
            status = "completed" if result.succeeded else result.status.value
            tools_info = f" (used: {', '.join(result.tools_used)})" if result.tools_used else ""
            return f"[Delegation to {agent_name}: {status}]{tools_info}\n\n{result.final_output}"

        except Exception as e:
            return f"Delegation to {agent_name} failed: {e}"

    def _exec_decompose(self, task: str, max_subtasks: int = 5) -> str:
        """
        Decompose a task into subtasks using keyword analysis.

        Returns a structured plan that the agent can follow step by step.
        """
        if not task:
            return "Error: task is required"

        # Keyword-based decomposition (no LLM call needed)
        aspects = []
        task_lower = task.lower()

        # Detect aspects that need attention
        aspect_keywords = {
            "Analysis": ["analyze", "analizar", "review", "examine", "investigate", "audit"],
            "Design": ["design", "diseñar", "architect", "plan", "structure"],
            "Implementation": ["implement", "create", "build", "write", "develop", "crear"],
            "Testing": ["test", "verify", "validate", "check", "ensure"],
            "Security": ["security", "secure", "vulnerability", "owasp", "auth"],
            "Performance": ["performance", "optimize", "fast", "slow", "cache"],
            "Documentation": ["document", "explain", "describe", "readme"],
            "Database": ["database", "schema", "migration", "query", "sql"],
            "Frontend": ["ui", "ux", "component", "style", "responsive", "react"],
            "Backend": ["api", "endpoint", "server", "backend", "route"],
        }

        for aspect, keywords in aspect_keywords.items():
            if any(kw in task_lower for kw in keywords):
                aspects.append(aspect)

        if not aspects:
            aspects = ["Analysis", "Implementation", "Testing"]

        aspects = aspects[:max_subtasks]

        # Build structured plan
        lines = [f"Task Decomposition for: {task[:100]}", ""]
        for i, aspect in enumerate(aspects, 1):
            lines.append(f"  {i}. [{aspect}] - Handle the {aspect.lower()} aspect of the task")

        lines.append("")
        lines.append(f"Total subtasks: {len(aspects)}")
        lines.append(
            "Execute each subtask sequentially. Use delegate_to_agent for specialized work."
        )

        return "\n".join(lines)

    # =========================================================================
    # LEARNING INTEGRATION (Level 4 Autonomy)
    # =========================================================================

    async def _post_execution_learning(self, result: LoopResult) -> None:
        """
        Feed execution results into the learning pipeline.

        Called automatically after each autonomous loop completes.
        """
        try:
            try:
                from autonomous_learning import get_learning_pipeline
            except ImportError:
                from ..autonomous_learning import get_learning_pipeline
            pipeline = get_learning_pipeline()
            if pipeline is None:
                return

            execution_data = {
                "task": result.task,
                "agent": result.agent_name,
                "success": result.succeeded,
                "status": result.status.value,
                "duration_ms": result.total_duration_ms,
                "tools_used": result.tools_used,
                "iterations": result.total_iterations,
                "steps": [
                    {
                        "agent": result.agent_name,
                        "action": s.step_type.value,
                        "tool": s.tool_name,
                        "status": "success",
                        "duration_ms": s.duration_ms,
                    }
                    for s in result.steps
                ],
            }

            if result.succeeded:
                await pipeline.extract_patterns([execution_data])

            # Learn from errors
            error_steps = [s for s in result.steps if s.tool_output and "Error" in s.tool_output]
            for step in error_steps:
                await pipeline.analyze_error(
                    {
                        "agent": result.agent_name,
                        "task": result.task,
                        "message": step.tool_output,
                        "context": {"tool": step.tool_name},
                    }
                )

        except ImportError:
            pass  # Learning pipeline not available
        except Exception as e:
            logger.debug(f"Learning hook: {e}")

    # =========================================================================
    # DISPLAY
    # =========================================================================

    def _emit_step(self, step: LoopStep) -> None:
        """Emit a step to callback and/or console."""
        if self.on_step:
            self.on_step(step)

        if self.verbose:
            icons = {
                StepType.THOUGHT: "  ",
                StepType.TOOL_CALL: "  ",
                StepType.TOOL_RESULT: "  ",
                StepType.REFLECTION: "  ",
                StepType.FINAL_ANSWER: "  ",
            }
            icon = icons.get(step.step_type, "  ")
            label = step.step_type.value.upper()

            if step.step_type == StepType.TOOL_CALL:
                logger.debug(
                    f"  {icon} [{step.step_num}] {label}: {step.tool_name}({json.dumps(step.tool_input)[:80]})"
                )
                if step.tool_output:
                    preview = step.tool_output[:200].replace("\n", " ")
                    logger.debug(f"       -> {preview}")
            elif step.step_type == StepType.FINAL_ANSWER:
                logger.info(f"  {icon} [{step.step_num}] {label}: {step.content[:200]}")
            else:
                logger.debug(f"  {icon} [{step.step_num}] {label}: {step.content[:200]}")

    def _print_header(self, agent_name: str, task: str) -> None:
        """Print loop start header."""
        logger.info(f"\n{'=' * 60}")
        logger.info(f"  AUTONOMOUS LOOP - {agent_name or 'agent'}")
        logger.info(f"{'=' * 60}")
        logger.info(f"  Task: {task[:80]}")
        logger.info(f"  Max iterations: {self.max_iterations}")
        logger.info(f"  Cost limit: ${self.max_cost_usd}")
        logger.info(f"{'=' * 60}\n")

    def _print_summary(self, result: LoopResult) -> None:
        """Print loop result summary."""
        status_icon = "[OK]" if result.succeeded else "[!!]"
        logger.info(f"\n{'=' * 60}")
        logger.info(f"  {status_icon} Loop {result.status.value}")
        logger.info(f"  Iterations: {result.total_iterations}")
        logger.info(f"  Steps: {len(result.steps)}")
        logger.info(f"  Tools used: {', '.join(result.tools_used) or 'none'}")
        logger.info(f"  Tokens: {result.total_tokens}")
        logger.info(f"  Cost: ${result.total_cost_usd:.4f}")
        logger.info(f"  Duration: {result.total_duration_ms:.0f}ms")
        logger.info(f"{'=' * 60}\n")


# =============================================================================
# CONVENIENCE FUNCTIONS
# =============================================================================


async def run_autonomous(
    task: str,
    agent_name: str = "explorer",
    max_iterations: int = 10,
    verbose: bool = True,
    system_prompt: str | None = None,
    provider: str | None = None,
    model: str | None = None,
) -> LoopResult:
    """
    Run an autonomous agent loop for a task.

    If no system_prompt is provided, loads it from the agent's IDENTITY.md.
    Auto-detects the best available LLM provider unless explicitly specified.

    Args:
        task: Task to accomplish
        agent_name: Name of agent (loads identity from .agent/agents/{name}/)
        max_iterations: Max tool-use cycles
        verbose: Print progress
        system_prompt: Override system prompt
        provider: Force LLM provider ("anthropic", "openai", "gemini", "ollama")
        model: Override model name

    Returns:
        LoopResult with full execution trace
    """
    # Load agent identity if no prompt provided
    if system_prompt is None:
        agents_dir = Path(__file__).parent.parent.parent / "agents" / agent_name
        identity_file = agents_dir / "IDENTITY.md"
        prompt_file = agents_dir / "SYSTEM_PROMPT.md"

        parts = []
        if identity_file.exists():
            parts.append(identity_file.read_text(encoding="utf-8"))
        if prompt_file.exists():
            parts.append(prompt_file.read_text(encoding="utf-8"))

        system_prompt = "\n\n".join(parts) if parts else f"You are {agent_name}, an expert agent."

    loop = AutonomousLoop(
        max_iterations=max_iterations,
        verbose=verbose,
        provider=provider,
        model=model,
    )

    return await loop.run(
        task=task,
        system_prompt=system_prompt,
        agent_name=agent_name,
    )
