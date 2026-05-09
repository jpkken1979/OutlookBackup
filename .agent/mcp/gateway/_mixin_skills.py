"""Mixin: handlers de skills y plugins."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

from aiohttp import web

log = logging.getLogger("antigravity-gateway")


class _SkillsMixin:
    """Handlers de skills: list, read, plugins."""

    async def handle_list_skills(self, request: web.Request) -> web.Response:
        """GET /v1/skills - Listar skills con paginacion y cache."""
        from .._gateway_main import _make_response

        search = request.query.get("search", "").lower()
        offset = max(0, int(request.query.get("offset", "0")))
        limit = min(100, max(1, int(request.query.get("limit", "50"))))
        include_external = request.query.get("include_external", "").strip().lower() in {
            "1",
            "true",
            "yes",
            "on",
        }

        # Cache de la lista completa de skills (sin filtro)
        cache_key = "all_skills_with_external" if include_external else "all_skills"
        all_skills = self.cache.get(cache_key)
        if all_skills is None:
            all_skills = await self._load_skills_list(include_external=include_external)
            self.cache.set(cache_key, all_skills)

        # Filtrar por busqueda
        if search:
            skills = [
                s
                for s in all_skills
                if search in s["name"].lower() or search in s["description"].lower()
            ]
        else:
            skills = all_skills

        total = len(skills)
        page = skills[offset : offset + limit]

        return web.json_response(
            _make_response(
                data={
                    "total": total,
                    "offset": offset,
                    "limit": limit,
                    "include_external": include_external,
                    "search": search or None,
                    "skills": page,
                }
            )
        )

    async def _load_skills_list(self, include_external: bool = False) -> list[dict]:
        """Carga lista de skills en thread pool (no bloquea event loop)."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            self._thread_pool,
            lambda: self._scan_skills(include_external=include_external),
        )

    def _external_skill_roots(self) -> list[tuple[Path, str]]:
        """Devuelve roots compatibles con el estándar de skills de Codex/OpenAI."""
        from .._gateway_main import BASE_DIR

        roots: list[tuple[Path, str]] = []

        repo_root = BASE_DIR / ".agents" / "skills"
        if repo_root.exists():
            roots.append((repo_root, "codex_repo"))

        home = Path.home()
        user_root = home / ".agents" / "skills"
        if user_root.exists() and user_root != repo_root:
            roots.append((user_root, "codex_user"))

        return roots

    @staticmethod
    def _parse_skill_metadata(skill_dir: Path) -> tuple[str, str]:
        """Extrae nombre y descripción desde el frontmatter de SKILL.md."""
        skill_md = skill_dir / "SKILL.md"
        name = skill_dir.name
        description = ""

        try:
            content = skill_md.read_text(encoding="utf-8", errors="replace")
            if content.startswith("---"):
                parts = content.split("---", 2)
                if len(parts) >= 2:
                    for line in parts[1].split("\n"):
                        stripped = line.strip()
                        if stripped.startswith("name:"):
                            name = stripped.split(":", 1)[1].strip().strip("\"'")
                        elif stripped.startswith("description:"):
                            description = stripped.split(":", 1)[1].strip().strip("\"'")
        except Exception:
            pass

        return name, description

    def _scan_skills(self, include_external: bool = False) -> list[dict]:
        """Escanea directorios de skills (sync, para thread pool)."""
        from .._gateway_main import SKILLS_DIR, SKILLS_CUSTOM_DIR

        skills = []
        skill_roots: list[tuple[Path, str]] = [
            (SKILLS_DIR, "main"),
            (SKILLS_CUSTOM_DIR, "custom"),
        ]
        if include_external:
            skill_roots.extend(self._external_skill_roots())

        for skills_path, source in skill_roots:
            if not skills_path.exists():
                continue
            for skill_dir in skills_path.iterdir():
                if not skill_dir.is_dir() or skill_dir.name.startswith("_"):
                    continue

                skill_md = skill_dir / "SKILL.md"
                if not skill_md.exists():
                    continue

                name, description = self._parse_skill_metadata(skill_dir)
                skills.append(
                    {
                        "name": name,
                        "description": description,
                        "source": source,
                    }
                )

        skills.sort(key=lambda x: (x["name"], x["source"]))
        return skills

    async def handle_read_skill(self, request: web.Request) -> web.Response:
        """GET /v1/skills/:name - Leer SKILL.md."""
        from .._gateway_main import _make_response, _validate_name, SKILLS_DIR, SKILLS_CUSTOM_DIR

        skill_name = request.match_info["name"]

        # Validar nombre (prevenir path traversal)
        if not _validate_name(skill_name):
            return web.json_response(
                _make_response(error="Nombre de skill invalido", status=400),
                status=400,
            )

        # Buscar en main y custom (async)
        loop = asyncio.get_running_loop()
        for skills_path in [SKILLS_DIR, SKILLS_CUSTOM_DIR]:
            skill_md = skills_path / skill_name / "SKILL.md"
            if skill_md.exists():
                content = await loop.run_in_executor(
                    self._thread_pool,
                    lambda p=skill_md: p.read_text(encoding="utf-8", errors="replace"),
                )
                return web.json_response(
                    _make_response(
                        data={
                            "name": skill_name,
                            "content": content,
                            "source": "custom" if skills_path == SKILLS_CUSTOM_DIR else "main",
                            "size_bytes": len(content.encode("utf-8")),
                        }
                    )
                )

        return web.json_response(
            _make_response(error=f"Skill '{skill_name}' no encontrada", status=404),
            status=404,
        )

    # =========================================================================
    # PLUGIN ENDPOINTS
    # =========================================================================

    def _get_plugin_manager(self):
        """Obtiene (o crea lazy) una instancia de PluginManager con discover()."""
        if not hasattr(self, "_plugin_manager"):
            try:
                from core.plugin_manager import PluginManager

                orchestrator = None
                executor = getattr(self, "executor", None)
                if executor is not None:
                    orchestrator = getattr(executor, "_orch", None)

                pm = PluginManager(orchestrator=orchestrator)
                pm.discover()
                self._plugin_manager = pm
            except Exception as exc:
                log.warning("PluginManager no disponible: %s", exc)
                self._plugin_manager = None
        return self._plugin_manager

    async def handle_list_plugins(self, request: web.Request) -> web.Response:
        """GET /v1/plugins — Lista todos los plugins con estado y stats."""
        from .._gateway_main import _make_response, _sanitize_error, _normalize_plugin_stats

        pm = self._get_plugin_manager()
        if pm is None:
            return web.json_response(
                _make_response(error="PluginManager no disponible", status=503), status=503
            )

        try:
            state_filter = request.query.get("state", "").lower()
            search = request.query.get("search", "").lower()

            plugins = pm.list_plugins()

            if state_filter:
                plugins = [p for p in plugins if p.state.value == state_filter]
            if search:
                plugins = [
                    p
                    for p in plugins
                    if search in p.metadata.name.lower() or search in p.metadata.description.lower()
                ]

            return web.json_response(
                _make_response(
                    data={
                        "total": len(plugins),
                        "plugins": [
                            {
                                "name": p.metadata.name,
                                "state": p.state.value,
                                "version": p.metadata.version,
                                "description": p.metadata.description,
                                "skills_count": p.skills_count,
                                "agents_count": p.agents_count,
                                "activated_at": p.activated_at,
                                "category": p.metadata.category,
                            }
                            for p in plugins
                        ],
                        "stats": _normalize_plugin_stats(pm.get_stats()),
                    }
                )
            )
        except Exception as exc:
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500), status=500
            )

    async def handle_list_plugins_alias(self, request: web.Request) -> web.Response:
        """GET /v1/plugins/list - Alias compatible con clientes legacy."""
        return await self.handle_list_plugins(request)

    async def handle_plugin_info(self, request: web.Request) -> web.Response:
        """GET /v1/plugins/{name} — Detalle de un plugin."""
        from .._gateway_main import _make_response, _validate_name

        pm = self._get_plugin_manager()
        if pm is None:
            return web.json_response(
                _make_response(error="PluginManager no disponible", status=503), status=503
            )

        plugin_name = request.match_info["name"]
        if not _validate_name(plugin_name):
            return web.json_response(
                _make_response(error="Nombre de plugin inválido", status=400), status=400
            )

        info = pm.get(plugin_name)
        if info is None:
            return web.json_response(
                _make_response(error=f"Plugin '{plugin_name}' no encontrado", status=404),
                status=404,
            )

        return web.json_response(
            _make_response(
                data={
                    "name": info.metadata.name,
                    "state": info.state.value,
                    "metadata": {
                        "version": info.metadata.version,
                        "description": info.metadata.description,
                        "author": info.metadata.author.model_dump()
                        if info.metadata.author
                        else None,
                        "category": info.metadata.category,
                        "tags": info.metadata.tags,
                        "dependencies": info.metadata.dependencies,
                    },
                    "skills_count": info.skills_count,
                    "agents_count": info.agents_count,
                    "commands_count": info.commands_count,
                    "activated_at": info.activated_at,
                    "deactivated_at": info.deactivated_at,
                    "error_message": info.error_message,
                }
            )
        )

    async def handle_activate_plugin(self, request: web.Request) -> web.Response:
        """POST /v1/plugins/{name}/activate — Activa un plugin."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        pm = self._get_plugin_manager()
        if pm is None:
            return web.json_response(
                _make_response(error="PluginManager no disponible", status=503), status=503
            )

        plugin_name = request.match_info["name"]
        if not _validate_name(plugin_name):
            return web.json_response(
                _make_response(error="Nombre de plugin inválido", status=400), status=400
            )

        try:
            info = await pm.activate(plugin_name)
            await self.events.emit(
                "plugin_activated",
                {
                    "plugin": plugin_name,
                    "skills": info.skills_count,
                },
            )
            return web.json_response(
                _make_response(
                    data={
                        "plugin": plugin_name,
                        "state": info.state.value,
                        "skills_registered": info.skills_count,
                        "message": f"Plugin '{plugin_name}' activado correctamente",
                    }
                )
            )
        except KeyError:
            return web.json_response(
                _make_response(error=f"Plugin '{plugin_name}' no encontrado", status=404),
                status=404,
            )
        except RuntimeError as exc:
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=409), status=409
            )
        except Exception as exc:
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500), status=500
            )

    async def handle_activate_plugin_alias(self, request: web.Request) -> web.Response:
        """POST /v1/plugins/activate - Alias con body JSON {name: string}."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        pm = self._get_plugin_manager()
        if pm is None:
            return web.json_response(
                _make_response(error="PluginManager no disponible", status=503), status=503
            )

        try:
            payload = await request.json()
        except Exception:
            payload = {}

        plugin_name = str(payload.get("name", "")).strip()
        if not plugin_name or not _validate_name(plugin_name):
            return web.json_response(
                _make_response(error="Nombre de plugin inválido", status=400),
                status=400,
            )
        try:
            info = await pm.activate(plugin_name)
            await self.events.emit(
                "plugin_activated", {"plugin": plugin_name, "skills": info.skills_count}
            )
            return web.json_response(
                _make_response(
                    data={
                        "plugin": plugin_name,
                        "state": info.state.value,
                        "skills_registered": info.skills_count,
                        "message": f"Plugin '{plugin_name}' activado correctamente",
                    }
                )
            )
        except KeyError:
            return web.json_response(
                _make_response(error=f"Plugin '{plugin_name}' no encontrado", status=404),
                status=404,
            )
        except RuntimeError as exc:
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=409), status=409
            )
        except Exception as exc:
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500), status=500
            )

    async def handle_deactivate_plugin(self, request: web.Request) -> web.Response:
        """POST /v1/plugins/{name}/deactivate — Desactiva un plugin."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        pm = self._get_plugin_manager()
        if pm is None:
            return web.json_response(
                _make_response(error="PluginManager no disponible", status=503), status=503
            )

        plugin_name = request.match_info["name"]
        if not _validate_name(plugin_name):
            return web.json_response(
                _make_response(error="Nombre de plugin inválido", status=400), status=400
            )

        try:
            info = await pm.deactivate(plugin_name)
            await self.events.emit("plugin_deactivated", {"plugin": plugin_name})
            return web.json_response(
                _make_response(
                    data={
                        "plugin": plugin_name,
                        "state": info.state.value,
                        "message": f"Plugin '{plugin_name}' desactivado correctamente",
                    }
                )
            )
        except KeyError:
            return web.json_response(
                _make_response(error=f"Plugin '{plugin_name}' no encontrado", status=404),
                status=404,
            )
        except Exception as exc:
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500), status=500
            )

    # =========================================================================
    # SKILL EXECUTION + TOOLS MANIFEST
    # =========================================================================

    async def handle_execute_skill(self, request: web.Request) -> web.Response:
        """POST /v1/skills/{name}/execute - Ejecuta un skill via agente o script."""
        from .._gateway_main import (
            _make_response,
            _sanitize_error,
            _validate_name,
            MAX_TASK_LENGTH,
            MAX_TIMEOUT_SECONDS,
            SKILLS_CUSTOM_DIR,
            SKILLS_DIR,
        )

        skill_name = request.match_info["name"]
        if not _validate_name(skill_name):
            return web.json_response(
                _make_response(error="Nombre de skill inválido", status=400), status=400
            )

        # Verificar que el skill existe
        skill_dir = None
        skill_source = "main"
        for skills_path in [SKILLS_DIR, SKILLS_CUSTOM_DIR]:
            candidate = skills_path / skill_name
            if candidate.is_dir() and (candidate / "SKILL.md").exists():
                skill_dir = candidate
                skill_source = "custom" if skills_path == SKILLS_CUSTOM_DIR else "main"
                break

        if skill_dir is None:
            return web.json_response(
                _make_response(error=f"Skill '{skill_name}' no encontrado", status=404), status=404
            )

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="JSON body requerido con campo 'input' o 'task'", status=400),
                status=400,
            )

        user_input = str(body.get("input", body.get("task", ""))).strip()
        if not user_input:
            return web.json_response(
                _make_response(error="Campo 'input' o 'task' requerido", status=400), status=400
            )
        if len(user_input) > MAX_TASK_LENGTH:
            return web.json_response(
                _make_response(error=f"Input excede {MAX_TASK_LENGTH} caracteres", status=400),
                status=400,
            )

        timeout = min(int(body.get("timeout", 120)), MAX_TIMEOUT_SECONDS)
        llm_config: dict | None = body.get("llm_config")
        persona: str | None = body.get("persona")

        # Construir tarea con contexto del skill
        task = f"Usa el skill '{skill_name}' para: {user_input}"

        executor = self.executor or await self.get_executor()
        if executor:
            import time

            best_agent = await self._find_best_agent_for_skill(skill_name, executor)
            agent_name = best_agent or "super-orchestrator"

            await self.events.emit("skill_execute", {"skill": skill_name, "agent": agent_name})

            exec_start = time.monotonic()
            try:
                result = await asyncio.wait_for(
                    executor.execute_agent(
                        agent_name, task, timeout, llm_config=llm_config, persona=persona
                    ),
                    timeout=timeout + 5,
                )
            except TimeoutError:
                return web.json_response(
                    _make_response(error=f"Timeout después de {timeout}s", status=504), status=504
                )
            except Exception as exc:
                return web.json_response(
                    _make_response(error=_sanitize_error(exc), status=500), status=500
                )

            duration = time.monotonic() - exec_start
            return web.json_response(
                _make_response(
                    data={
                        "skill": skill_name,
                        "source": skill_source,
                        "agent_used": agent_name,
                        "result": result,
                        "duration_seconds": round(duration, 2),
                    }
                )
            )

        # Sin executor: ejecutar script directamente si existe
        script_path = skill_dir / "scripts" / "main.py"
        if not script_path.exists():
            return web.json_response(
                _make_response(
                    error="Executor no disponible y skill sin script ejecutable", status=503
                ),
                status=503,
            )

        import time

        exec_start = time.monotonic()
        try:
            proc = await asyncio.create_subprocess_exec(
                "python",
                str(script_path),
                user_input,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=timeout)
            duration = time.monotonic() - exec_start
            return web.json_response(
                _make_response(
                    data={
                        "skill": skill_name,
                        "source": skill_source,
                        "agent_used": None,
                        "result": {
                            "output": stdout.decode("utf-8", errors="replace").strip(),
                            "stderr": stderr.decode("utf-8", errors="replace").strip(),
                            "returncode": proc.returncode,
                        },
                        "duration_seconds": round(duration, 2),
                    }
                )
            )
        except TimeoutError:
            return web.json_response(
                _make_response(error=f"Timeout después de {timeout}s", status=504), status=504
            )
        except Exception as exc:
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500), status=500
            )

    async def _find_best_agent_for_skill(self, skill_name: str, executor=None) -> str | None:
        """Busca el agente más apropiado para ejecutar un skill dado."""
        try:
            executor = executor or self.executor or await self.get_executor()
            if not executor:
                return None
            agents = executor.get_available_agents()
            # Preferir agente cuyo nombre coincida con el skill
            skill_lower = skill_name.lower()
            for agent in agents:
                if skill_lower in agent.get("name", "").lower():
                    return agent["name"]
            # Fallback: primer agente ejecutable
            executables = [a for a in agents if a.get("has_executable")]
            return executables[0]["name"] if executables else None
        except Exception:
            return None

    async def handle_tools_manifest(self, request: web.Request) -> web.Response:
        """GET /v1/tools/manifest - Skills y agentes como herramientas LLM."""
        from .._gateway_main import _make_response

        filter_type = request.query.get("type", "all")  # all | skills | agents
        search = request.query.get("search", "").lower()
        limit = min(500, max(1, int(request.query.get("limit", "200"))))

        # Cargar skills (con cache)
        all_skills: list[dict] = []
        if filter_type in ("all", "skills"):
            cached = self.cache.get("all_skills")
            if cached is None:
                cached = await self._load_skills_list()
                self.cache.set("all_skills", cached)
            all_skills = cached

        # Cargar agentes
        all_agents: list[dict] = []
        if filter_type in ("all", "agents"):
            executor = self.executor or await self.get_executor()
            if executor:
                all_agents = executor.get_available_agents()
            else:
                all_agents = self._list_agents_from_filesystem()

        # FIX: aplicar límites independientes por tipo para que los agentes
        # siempre estén representados aunque los skills llenen el cupo global.
        # Los agentes tienen límite propio (hasta 150), los skills ocupan el resto.
        agents_limit = min(150, len(all_agents))
        skills_limit = max(0, limit - agents_limit)

        agent_tools: list[dict] = []
        for agent in all_agents:
            if len(agent_tools) >= agents_limit:
                break
            name = agent.get("name", "")
            if not name:
                continue
            if search and search not in name.lower():
                continue
            agent_tools.append(
                {
                    "type": "agent",
                    "name": f"agent__{name.replace('-', '_')}",
                    "original_name": name,
                    "description": f"Agente autónomo del ecosistema Antigravity: {name}",
                    "tier": agent.get("tier", "unknown"),
                    "has_executable": agent.get("has_executable", False),
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "task": {
                                "type": "string",
                                "description": f"Tarea a ejecutar por el agente '{name}'",
                            }
                        },
                        "required": ["task"],
                    },
                }
            )

        skill_tools: list[dict] = []
        for skill in all_skills:
            if len(skill_tools) >= skills_limit:
                break
            name = skill["name"]
            desc = skill.get("description", f"Skill: {name}")
            if search and search not in name.lower() and search not in desc.lower():
                continue
            skill_tools.append(
                {
                    "type": "skill",
                    "name": f"skill__{name.replace('-', '_')}",
                    "original_name": name,
                    "description": desc,
                    "source": skill.get("source", "main"),
                    "input_schema": {
                        "type": "object",
                        "properties": {
                            "input": {
                                "type": "string",
                                "description": f"Tarea a ejecutar con el skill '{name}'",
                            }
                        },
                        "required": ["input"],
                    },
                }
            )

        # Combinar: skills primero (contexto del LLM), luego agentes
        tools: list[dict] = skill_tools + agent_tools

        skills_count = sum(1 for t in tools if t["type"] == "skill")
        agents_count = sum(1 for t in tools if t["type"] == "agent")

        return web.json_response(
            _make_response(
                data={
                    "total": len(tools),
                    "skills_count": skills_count,
                    "agents_count": agents_count,
                    "tools": tools,
                }
            )
        )

    async def handle_deactivate_plugin_alias(self, request: web.Request) -> web.Response:
        """POST /v1/plugins/deactivate - Alias con body JSON {name: string}."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        pm = self._get_plugin_manager()
        if pm is None:
            return web.json_response(
                _make_response(error="PluginManager no disponible", status=503), status=503
            )

        try:
            payload = await request.json()
        except Exception:
            payload = {}

        plugin_name = str(payload.get("name", "")).strip()
        if not plugin_name or not _validate_name(plugin_name):
            return web.json_response(
                _make_response(error="Nombre de plugin inválido", status=400),
                status=400,
            )
        try:
            info = await pm.deactivate(plugin_name)
            await self.events.emit("plugin_deactivated", {"plugin": plugin_name})
            return web.json_response(
                _make_response(
                    data={
                        "plugin": plugin_name,
                        "state": info.state.value,
                        "message": f"Plugin '{plugin_name}' desactivado correctamente",
                    }
                )
            )
        except KeyError:
            return web.json_response(
                _make_response(error=f"Plugin '{plugin_name}' no encontrado", status=404),
                status=404,
            )
        except Exception as exc:
            return web.json_response(
                _make_response(error=_sanitize_error(exc), status=500), status=500
            )
