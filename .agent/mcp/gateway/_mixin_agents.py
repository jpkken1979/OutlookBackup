"""Mixin: handlers de agentes — list, info, execute, find, autonomous, teams."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from pathlib import Path

from aiohttp import web

log = logging.getLogger("antigravity-gateway")


class _AgentsMixin:
    """Handlers de agentes: list, info, execute, find, autonomous, teams."""

    def _list_agents_from_filesystem(self) -> list[dict]:
        """Lee agentes directamente del filesystem (sin executor, sin bloquear)."""
        from .._gateway_main import AGENTS_DIR

        agents = []
        if not AGENTS_DIR.exists():
            return agents
        for d in sorted(AGENTS_DIR.iterdir()):
            if not d.is_dir() or d.name.startswith("_"):
                continue
            identity = d / "IDENTITY.md"
            has_scripts = (d / "scripts").is_dir()
            agents.append(
                {
                    "name": d.name,
                    "has_executable": has_scripts,
                    "identity_exists": identity.exists(),
                    "tier": "unknown",
                }
            )
        return agents

    async def handle_list_agents(self, request: web.Request) -> web.Response:
        """GET /v1/agents - Lista agentes con paginacion."""
        from .._gateway_main import _make_response

        filter_type = request.query.get("filter", "all")
        offset = max(0, int(request.query.get("offset", "0")))
        limit = min(100, max(1, int(request.query.get("limit", "50"))))

        cache_key = f"agents_{filter_type}"
        agents = self.cache.get(cache_key)
        if agents is None:
            if self.executor:
                agents = self.executor.get_available_agents()
            else:
                # Fallback: leer filesystem directamente (no bloquea event loop)
                agents = self._list_agents_from_filesystem()
            if filter_type == "executable":
                agents = [a for a in agents if a.get("has_executable")]
            self.cache.set(cache_key, agents)

        total = len(agents)
        page = agents[offset : offset + limit]

        return web.json_response(
            _make_response(
                data={
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "filter": filter_type,
                    "agents": page,
                }
            )
        )

    async def handle_agent_info(self, request: web.Request) -> web.Response:
        """GET /v1/agents/:name - Info de un agente."""
        from .._gateway_main import _make_response, _validate_name

        executor = self.executor or await self.get_executor()
        if not executor:
            return web.json_response(
                _make_response(error="Executor no disponible", status=503),
                status=503,
            )

        agent_name = request.match_info["name"]
        if not _validate_name(agent_name):
            return web.json_response(
                _make_response(error="Nombre de agente invalido", status=400),
                status=400,
            )

        agents = executor.get_available_agents()
        agent = next((a for a in agents if a["name"] == agent_name), None)

        if not agent:
            return web.json_response(
                _make_response(error=f"Agente '{agent_name}' no encontrado", status=404),
                status=404,
            )

        # Leer IDENTITY.md (async via thread pool)
        identity_path = Path(agent["identity_path"])
        identity_content = ""
        if identity_path.exists():
            loop = asyncio.get_running_loop()
            identity_content = await loop.run_in_executor(
                self._thread_pool,
                lambda: identity_path.read_text(encoding="utf-8", errors="replace"),
            )

        return web.json_response(
            _make_response(
                data={
                    **agent,
                    "identity_content": identity_content,
                }
            )
        )

    async def handle_execute_agent(self, request: web.Request) -> web.Response:
        """POST /v1/agents/:name/run - Ejecutar agente."""
        from .._gateway_main import (
            _make_response,
            _validate_name,
            MAX_TASK_LENGTH,
            MAX_TIMEOUT_SECONDS,
        )

        executor = self.executor or await self.get_executor()
        if not executor:
            return web.json_response(
                _make_response(error="Executor no disponible", status=503),
                status=503,
            )

        agent_name = request.match_info["name"]
        if not _validate_name(agent_name):
            return web.json_response(
                _make_response(error="Nombre de agente invalido", status=400),
                status=400,
            )

        try:
            body = await request.json()
        except (json.JSONDecodeError, Exception):
            return web.json_response(
                _make_response(error="Body JSON requerido con campo 'task'", status=400),
                status=400,
            )

        task = body.get("task", "")
        if not task or not isinstance(task, str):
            return web.json_response(
                _make_response(error="Campo 'task' es requerido (string)", status=400),
                status=400,
            )
        if len(task) > MAX_TASK_LENGTH:
            return web.json_response(
                _make_response(error=f"Task excede {MAX_TASK_LENGTH} caracteres", status=400),
                status=400,
            )

        timeout = min(body.get("timeout", 120), MAX_TIMEOUT_SECONDS)

        # Parametros opcionales de LLM y persona
        llm_config: dict | None = body.get("llm_config")
        persona: str | None = body.get("persona")

        await self.events.emit(
            "agent_start",
            {
                "agent": agent_name,
                "task": task[:100],
            },
        )

        exec_start = time.monotonic()
        try:
            result = await asyncio.wait_for(
                executor.execute_agent(
                    agent_name,
                    task,
                    timeout,
                    llm_config=llm_config,
                    persona=persona,
                ),
                timeout=timeout + 5,  # margin de 5s sobre el timeout del agente
            )
        except TimeoutError:
            return web.json_response(
                _make_response(error=f"Timeout despues de {timeout}s", status=504),
                status=504,
            )

        exec_duration_s = time.monotonic() - exec_start
        self.metrics.agents_executed += 1

        # Registrar latencia de ejecucion por agente
        agent_durations = self.metrics.agent_execution_seconds[agent_name]
        agent_durations.append(exec_duration_s)
        # Mantener solo las ultimas 500 mediciones por agente
        if len(agent_durations) > 500:
            self.metrics.agent_execution_seconds[agent_name] = agent_durations[-500:]

        await self.events.emit(
            "agent_complete",
            {
                "agent": agent_name,
                "success": result.success,
                "time_ms": result.execution_time_ms,
            },
        )

        return web.json_response(_make_response(data=result.to_dict()))

    async def handle_find_agent(self, request: web.Request) -> web.Response:
        """POST /v1/agents/find - Buscar mejor agente."""
        from .._gateway_main import _make_response

        executor = self.executor or await self.get_executor()
        if not executor:
            return web.json_response(
                _make_response(error="Executor no disponible", status=503),
                status=503,
            )

        try:
            body = await request.json()
        except (json.JSONDecodeError, Exception):
            return web.json_response(
                _make_response(
                    error="Body JSON requerido con campo 'task_description'", status=400
                ),
                status=400,
            )

        task_description = body.get("task_description", "")
        if not task_description:
            return web.json_response(
                _make_response(error="Campo 'task_description' es requerido", status=400),
                status=400,
            )

        limit = min(body.get("limit", 5), 20)

        try:
            matches = executor.find_best_agent(task_description, limit)
        except Exception:
            matches = self._find_agent_fallback(task_description, limit)

        return web.json_response(
            _make_response(
                data={
                    "query": task_description,
                    "matches": matches,
                }
            )
        )

    def _find_agent_fallback(self, task_description: str, limit: int = 5) -> list[dict]:
        """Busqueda fallback por keywords cuando CapabilityRegistry falla."""
        agents = self.executor.get_available_agents()
        task_lower = task_description.lower()
        scored = []

        for agent in agents:
            score = 0
            reasons = []

            if agent["name"].replace("-", " ") in task_lower:
                score += 50
                reasons.append(f"name_match:{agent['name']}")

            for trigger in agent.get("triggers", []):
                if trigger.lower() in task_lower:
                    score += 30
                    reasons.append(f"trigger:{trigger}")

            desc_words = agent.get("description", "").lower().split()
            matching = [w for w in desc_words if w in task_lower and len(w) > 3]
            if matching:
                score += len(matching) * 5
                reasons.append(f"description:{len(matching)}_words")

            if score > 0:
                scored.append(
                    {
                        "agent": agent["name"],
                        "score": score,
                        "reasons": reasons,
                        "has_executable": agent["has_executable"],
                    }
                )

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:limit]

    async def handle_autonomous(self, request: web.Request) -> web.Response:
        """POST /v1/autonomous - Modo autonomo con limites."""
        from .._gateway_main import (
            _make_response,
            _validate_name,
            _sanitize_error,
            MAX_TASK_LENGTH,
            MAX_ITERATIONS_CAP,
        )

        try:
            from core.autonomous_loop import run_autonomous
        except ImportError:
            return web.json_response(
                _make_response(error="Modulo autonomous_loop no disponible", status=503),
                status=503,
            )

        try:
            body = await request.json()
        except (json.JSONDecodeError, Exception):
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400),
                status=400,
            )

        agent_name = body.get("agent_name", "")
        task = body.get("task", "")
        max_iterations = body.get("max_iterations", 15)

        if not agent_name or not task:
            return web.json_response(
                _make_response(error="Campos 'agent_name' y 'task' son requeridos", status=400),
                status=400,
            )

        if not _validate_name(agent_name):
            return web.json_response(
                _make_response(error="Nombre de agente invalido", status=400),
                status=400,
            )

        if len(task) > MAX_TASK_LENGTH:
            return web.json_response(
                _make_response(error=f"Task excede {MAX_TASK_LENGTH} caracteres", status=400),
                status=400,
            )

        # Hardcap en iteraciones
        max_iterations = min(max_iterations, MAX_ITERATIONS_CAP)

        await self.events.emit(
            "autonomous_start",
            {
                "agent": agent_name,
                "task": task[:100],
                "max_iterations": max_iterations,
            },
        )

        try:
            # Timeout proporcional a iteraciones (30s por iteracion + margin)
            timeout_s = max_iterations * 30 + 30
            result = await asyncio.wait_for(
                run_autonomous(
                    task=task,
                    agent_name=agent_name,
                    max_iterations=max_iterations,
                ),
                timeout=timeout_s,
            )
            await self.events.emit(
                "autonomous_complete",
                {
                    "agent": agent_name,
                    "status": result.status.value
                    if hasattr(result.status, "value")
                    else str(result.status),
                    "iterations": result.total_iterations,
                    "cost_usd": result.total_cost_usd,
                },
            )
            output = result.to_dict() if hasattr(result, "to_dict") else {"output": str(result)}
            return web.json_response(_make_response(data=output))
        except TimeoutError:
            return web.json_response(
                _make_response(error=f"Timeout autonomo ({timeout_s}s)", status=504),
                status=504,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_create_team(self, request: web.Request) -> web.Response:
        """POST /v1/teams - Crear equipo con limites."""
        from .._gateway_main import (
            _make_response,
            _validate_name,
            _sanitize_error,
            AGENTS_DIR,
            MAX_TEAMS,
        )

        try:
            from core.agent_teams import TeamManager
        except ImportError:
            return web.json_response(
                _make_response(error="Modulo agent_teams no disponible", status=503),
                status=503,
            )

        # Limpiar equipos expirados antes de crear uno nuevo
        self._cleanup_teams()

        if len(self._teams) >= MAX_TEAMS:
            return web.json_response(
                _make_response(
                    error=f"Limite de {MAX_TEAMS} equipos activos alcanzado", status=429
                ),
                status=429,
            )

        try:
            body = await request.json()
        except (json.JSONDecodeError, Exception):
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400),
                status=400,
            )

        task = body.get("task", "")
        if not task:
            return web.json_response(
                _make_response(error="Campo 'task' es requerido", status=400),
                status=400,
            )

        agents_list = body.get("agents", [])
        lead = body.get("lead")
        auto_select = body.get("auto_select", False)
        execute_now = body.get("execute", False)

        # Validar nombres de agentes
        for name in agents_list:
            if not _validate_name(name):
                return web.json_response(
                    _make_response(error=f"Nombre de agente invalido: '{name}'", status=400),
                    status=400,
                )

        try:
            manager = TeamManager(agents_dir=AGENTS_DIR)

            if auto_select or not agents_list:
                team = await manager.auto_team(task=task)
            else:
                team = await manager.spawn_team(
                    task=task,
                    agents=agents_list,
                    lead=lead,
                )

            self._teams[team.id] = {"team": team, "created_at": time.monotonic()}
            self.metrics.teams_created += 1

            team_data = {
                "team_id": team.id,
                "name": team.name,
                "lead": team.lead,
                "members": [
                    {"name": name, "role": m.role.value, "description": m.description[:80]}
                    for name, m in team.members.items()
                ],
                "status": team.status.value,
            }

            await self.events.emit(
                "team_created",
                {
                    "team_id": team.id,
                    "members": list(team.members.keys()),
                },
            )

            if execute_now:
                exec_result = await team.execute()
                team_data["execution"] = {
                    "success": exec_result.success,
                    "time_ms": exec_result.execution_time_ms,
                    "messages": exec_result.messages_exchanged,
                    "outputs": {name: output[:500] for name, output in exec_result.outputs.items()},
                }

            return web.json_response(_make_response(data=team_data), status=201)

        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    def _cleanup_teams(self) -> None:
        """Elimina equipos que excedieron el TTL."""
        from .._gateway_main import TEAM_TTL_SECONDS

        now = time.monotonic()
        expired = [
            tid for tid, info in self._teams.items() if now - info["created_at"] > TEAM_TTL_SECONDS
        ]
        for tid in expired:
            del self._teams[tid]
        if expired:
            log.info("Limpiados %d equipos expirados", len(expired))

    async def handle_reload_agents(self, request: web.Request) -> web.Response:
        """POST /v1/agents/reload - Invalida cache de agentes y fuerza re-lectura."""
        from .._gateway_main import _make_response

        # Invalida todas las cache keys de agentes
        self.cache.invalidate("agents_all")
        self.cache.invalidate("agents_executable")

        # Re-leer del filesystem
        agents = self._list_agents_from_filesystem()
        executable = [a for a in agents if a.get("has_scripts")]
        self.cache.set("agents_all", agents)
        self.cache.set("agents_executable", executable)

        log.info("Agents cache reload: %d agentes totales, %d ejecutables", len(agents), len(executable))

        return web.json_response(
            _make_response(
                data={
                    "total": len(agents),
                    "executable": len(executable),
                    "message": f"Cache recargado: {len(agents)} agentes",
                }
            )
        )

    async def handle_team_message(self, request: web.Request) -> web.Response:
        """POST /v1/teams/:id/message - Mensaje en equipo."""
        from .._gateway_main import _make_response, _sanitize_error

        team_id = request.match_info["id"]
        team_info = self._teams.get(team_id)

        if not team_info:
            return web.json_response(
                _make_response(error=f"Equipo '{team_id}' no encontrado", status=404),
                status=404,
            )

        team = team_info["team"]

        try:
            body = await request.json()
        except (json.JSONDecodeError, Exception):
            return web.json_response(
                _make_response(error="Body JSON requerido", status=400),
                status=400,
            )

        from_agent = body.get("from_agent", "")
        to_agent = body.get("to_agent", "")
        content = body.get("content", "")

        if not all([from_agent, to_agent, content]):
            return web.json_response(
                _make_response(
                    error="Campos 'from_agent', 'to_agent' y 'content' requeridos", status=400
                ),
                status=400,
            )

        try:
            await team.send_message(
                from_agent=from_agent,
                to_agent=to_agent,
                content=content,
            )
            return web.json_response(
                _make_response(
                    data={
                        "sent": True,
                        "from": from_agent,
                        "to": to_agent,
                        "conversation": team.get_conversation_summary(),
                    }
                )
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )
