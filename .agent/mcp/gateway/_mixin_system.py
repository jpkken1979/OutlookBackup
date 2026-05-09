"""Mixin: handlers de sistema — health, ready, metrics, openapi, root."""

from __future__ import annotations

import json
import logging
from datetime import datetime

from aiohttp import web

log = logging.getLogger("antigravity-gateway")

# Importar globals del módulo principal (se inyectan via sys.modules en runtime)
# Estos nombres se resuelven en el contexto de la clase AntigravityGateway que hereda de este mixin.


class _SystemMixin:
    """Handlers de sistema: root, health, ready, metrics, openapi."""

    async def handle_root(self, request: web.Request) -> web.Response:
        """GET /v1/ - Info del gateway."""
        from .._gateway_main import (
            VERSION,
            SKILLS_DIR,
            _make_response,
        )

        uptime = (datetime.now() - self._start_time).total_seconds()
        agent_count = 0
        if self.executor:
            cached = self.cache.get("agent_count")
            if cached is not None:
                agent_count = cached
            else:
                agents = self.executor.get_available_agents()
                agent_count = len(agents)
                self.cache.set("agent_count", agent_count)

        skill_count = 0
        cached_skills = self.cache.get("skill_count")
        if cached_skills is not None:
            skill_count = cached_skills
        elif SKILLS_DIR.exists():
            skill_count = sum(
                1 for d in SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith("_")
            )
            self.cache.set("skill_count", skill_count)

        return web.json_response(
            _make_response(
                data={
                    "name": "Antigravity MCP HTTP Gateway",
                    "version": VERSION,
                    "status": "running",
                    "uptime_seconds": round(uptime),
                    "agents": agent_count,
                    "skills": skill_count,
                    "auth_required": self.config.require_auth,
                    "docs": "/v1/openapi.json",
                    "endpoints": [
                        "GET  /v1/              Info del gateway",
                        "GET  /v1/health        Liveness check",
                        "GET  /v1/ready         Readiness check",
                        "GET  /v1/metrics       Metricas Prometheus",
                        "GET  /v1/agents        Lista agentes (?filter=executable&offset=0&limit=50)",
                        "GET  /v1/agents/:name  Info de agente",
                        "POST /v1/agents/:name/run  Ejecutar agente {task, timeout?}",
                        "POST /v1/agents/find   Buscar mejor agente {task_description, limit?}",
                        "POST /v1/autonomous    Modo autonomo {agent_name, task, max_iterations?}",
                        "POST /v1/teams         Crear equipo {task, agents?, lead?, auto_select?, execute?}",
                        "POST /v1/teams/:id/message  Mensaje en equipo {from_agent, to_agent, content}",
                        "GET  /v1/skills        Listar skills (?search=keyword&offset=0&limit=50)",
                        "GET  /v1/skills/:name  Leer SKILL.md completo",
                        "GET  /v1/costs         Reporte de costos (?days=30)",
                        "GET  /v1/history       Historial (?limit=10)",
                        "GET  /v1/events        SSE stream de eventos",
                        "GET  /v1/openapi.json  Schema OpenAPI 3.0",
                        "POST /v1/autotune/analyze   Analizar contexto {messages, model?}",
                        "POST /v1/autotune/feedback  Feedback de tuning {category, rating, parameters?}",
                        "POST /v1/race/run      Carrera paralela {task, tier?, agents?}",
                        "GET  /v1/race/rankings  Rankings de agentes en carreras",
                        "GET  /v1/rate-limit/stats  Estadisticas del rate limiter",
                        "POST /v1/watcher/events    Ingest de eventos del ProcessWatcher",
                        "GET  /v1/watcher/events/recent  Historial reciente in-memory (?limit&importance)",
                        "GET  /v1/watcher/events/history Historial persistido SQLite (?limit&importance&watch_id)",
                        "GET  /v1/watcher/stream    SSE stream en vivo (?importance)",
                        "GET  /v1/watcher/status    Estado del subsistema watcher",
                        "GET  /v1/watcher/metrics   Counters Prometheus (?Accept: application/json)",
                        "POST /v1/watcher/spawn     Lanzar proceso en engine hospedado",
                        "GET  /v1/watcher/list      Listar watches (?include_finished)",
                        "POST /v1/watcher/:id/kill  Terminar proceso",
                        "GET  /v1/watcher/:id/tail  Ultimas lineas stdout/stderr",
                        "GET  /v1/context-engine/list     Context engines disponibles",
                        "GET  /v1/context-engine/current  Engine activo + fuentes",
                        "POST /v1/context-engine/switch   Cambiar engine (persiste)",
                        "POST /v1/context-engine/preview  Simular engine con tarea de ejemplo",
                        "POST /v1/context-engine/stats    Metricas chars/tokens vs legacy",
                    ],
                }
            )
        )

    async def handle_health(self, request: web.Request) -> web.Response:
        """GET /v1/health - Liveness check con estado de conexiones MCP."""
        from .._gateway_main import (
            AGENTS_DIR,
            SKILLS_DIR,
            CORE_DIR,
            BASE_DIR,
            ACTIVE_PROFILE,
            _make_response,
        )

        # Executor es lazy-load intencional (no pre-cargado por GIL contention).
        # NO reportar como "loading" — el gateway está healthy sin él.
        checks = {
            "gateway": "ok",
            "executor": "ok" if self._executor is not None else "lazy",
            "agents_dir": "ok" if AGENTS_DIR.exists() else "missing",
            "skills_dir": "ok" if SKILLS_DIR.exists() else "missing",
            "core_dir": "ok" if CORE_DIR.exists() else "missing",
        }

        # Verificar conectividad MCP (remote y local)
        mcp_status = {}
        try:
            mcp_json = BASE_DIR / ".mcp.json"
            if mcp_json.exists():
                mcp_data = json.loads(mcp_json.read_text(encoding="utf-8"))
                for name, config in mcp_data.get("mcpServers", {}).items():
                    transport = config.get("type", "stdio")
                    url = config.get("url", "")
                    mcp_status[name] = {
                        "transport": transport,
                        "configured": True,
                    }
                    if transport in ("http", "url") and url:
                        mcp_status[name]["url"] = url
        except Exception:
            pass

        # Watcher self-check — reporta sin cargar eager el engine singleton.
        watcher_health = {"engine_hosted": False, "history_store": False}
        try:
            from . import _mixin_watcher as _wm

            watcher_health["engine_hosted"] = _wm._watcher_instance is not None
            watcher_health["history_store"] = (
                _wm._event_store is not None
                and _wm._event_store.stats().get("available", False)
            )
        except Exception:  # noqa: BLE001
            pass

        healthy = all(v in ("ok", "lazy") for v in checks.values())
        status = "healthy" if healthy else "degraded"
        return web.json_response(
            _make_response(
                data={
                    "status": status,
                    "profile": ACTIVE_PROFILE.name,
                    "checks": checks,
                    "uptime_seconds": round((datetime.now() - self._start_time).total_seconds()),
                    "sse_connections": self.events.count,
                    "active_teams": len(self._teams),
                    "mcp_servers": mcp_status,
                    "watcher": watcher_health,
                }
            ),
            status=200 if healthy else 503,
        )

    async def handle_ready(self, request: web.Request) -> web.Response:
        """GET /v1/ready - Readiness check (puede recibir trafico?)."""
        from .._gateway_main import EXECUTOR_AVAILABLE, AGENTS_DIR, _make_response

        ready = self._ready and EXECUTOR_AVAILABLE and AGENTS_DIR.exists()
        return web.json_response(
            _make_response(
                data={
                    "ready": ready,
                    "executor_loaded": EXECUTOR_AVAILABLE,
                    "agents_available": AGENTS_DIR.exists(),
                }
            ),
            status=200 if ready else 503,
        )

    async def handle_metrics(self, request: web.Request) -> web.Response:
        """GET /v1/metrics - Metricas en formato Prometheus."""
        self.metrics.active_sse_connections = self.events.count
        resp = web.Response(body=self.metrics.to_prometheus().encode("utf-8"))
        resp.content_type = "text/plain"
        return resp

    async def handle_openapi(self, request: web.Request) -> web.Response:
        """GET /v1/openapi.json - Schema OpenAPI."""
        return web.json_response(self._openapi)
