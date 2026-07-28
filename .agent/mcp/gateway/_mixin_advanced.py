"""Mixin: handlers avanzados — genome, knowledge, arena, ws, dashboard, alerts, federation, marketplace, trust, meta, goals, emergent."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import web

log = logging.getLogger("antigravity-gateway")

# Proxy al daemon worker subprocess (proceso separado, GIL independiente)
_daemon_proxy = None
_daemon_proxy_creating = False
_daemon_proxy_task: asyncio.Task | None = None


async def _get_daemon_safe():
    """Retorna proxy al daemon worker, spawneando el subprocess si necesario.

    Non-blocking: si la creación está en progreso, retorna None inmediatamente.
    El lock interno de DaemonProxy.create() previene spawns duplicados.
    """
    global _daemon_proxy, _daemon_proxy_creating, _daemon_proxy_task
    if _daemon_proxy is not None:
        return _daemon_proxy

    # Si ya hay una creación en progreso, no esperar.
    # Solo recoger resultado si el task ya terminó.
    if _daemon_proxy_creating:
        if _daemon_proxy_task is not None and _daemon_proxy_task.done():
            try:
                _daemon_proxy = _daemon_proxy_task.result()
            except Exception:
                _daemon_proxy = None
            finally:
                _daemon_proxy_task = None
                _daemon_proxy_creating = False
            return _daemon_proxy
        return None

    _daemon_proxy_creating = True

    try:
        from ..daemon_proxy import DaemonProxy

        # Arranque en background para no bloquear requests HTTP.
        _daemon_proxy_task = asyncio.create_task(DaemonProxy.create())
        return None
    except Exception:
        _daemon_proxy_task = None
        _daemon_proxy_creating = False
        return None


async def _reset_daemon_safe() -> None:
    """Resetea proxy/worker del daemon para forzar recreación limpia."""
    global _daemon_proxy, _daemon_proxy_creating, _daemon_proxy_task

    try:
        from ..daemon_proxy import DaemonProxy

        DaemonProxy.shutdown()
    except Exception:
        pass

    if _daemon_proxy_task is not None and not _daemon_proxy_task.done():
        _daemon_proxy_task.cancel()

    _daemon_proxy = None
    _daemon_proxy_task = None
    _daemon_proxy_creating = False


def _daemon_unavailable_response():
    """Respuesta cuando el daemon no está disponible — 200 con datos vacíos.

    Retorna 200 (no 503) para evitar inflar el error rate en métricas.
    El frontend ya maneja datos vacíos mostrando 'Sin datos'.
    """
    from .._gateway_main import _make_response

    return web.json_response(
        _make_response(
            data={"status": "not_ready", "message": "Daemon no inicializado"},
        ),
        status=200,
    )


class _AdvancedMixin:
    """Handlers avanzados: genome, knowledge, arena, ws, dashboard, alerts, federation, marketplace, trust, meta, goals, emergent."""

    # --------------------------------------------------------
    # Genome Endpoints (Sprint 8)
    # --------------------------------------------------------
    async def handle_genome_register(self, request: web.Request) -> web.Response:
        """POST /v1/genome/agents/{agent} - Registrar genoma."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.match_info["agent"]
            if not _validate_name(agent):
                return web.json_response(
                    _make_response(error="Nombre de agente invalido", status=400),
                    status=400,
                )
            body = await request.json() if request.can_read_body else {}
            genome = await daemon.genome_register(agent, body.get("traits"))
            return web.json_response(_make_response(data=genome))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_genome_evaluate(self, request: web.Request) -> web.Response:
        """POST /v1/genome/agents/{agent}/evaluate - Evaluar fitness."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.match_info["agent"]
            if not _validate_name(agent):
                return web.json_response(
                    _make_response(error="Nombre de agente invalido", status=400),
                    status=400,
                )
            body = await request.json()
            result = await daemon.genome_evaluate(
                agent,
                reputation=body.get("reputation", 0.5),
                compliance=body.get("compliance", 0.5),
                success_rate=body.get("success_rate", 0.5),
                response_time_score=body.get("response_time_score", 0.5),
                collaboration_score=body.get("collaboration_score", 0.5),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_genome_evolve(self, request: web.Request) -> web.Response:
        """POST /v1/genome/evolve - Ejecutar evolución."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            result = await daemon.genome_evolve()
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_genome_get(self, request: web.Request) -> web.Response:
        """GET /v1/genome/agents/{agent} - Obtener genoma."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.match_info["agent"]
            if not _validate_name(agent):
                return web.json_response(
                    _make_response(error="Nombre de agente invalido", status=400),
                    status=400,
                )
            genome = await daemon.genome_get(agent)
            if not genome:
                return web.json_response(
                    _make_response(error="No genome", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data=genome))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_genome_all(self, request: web.Request) -> web.Response:
        """GET /v1/genome - Todos los genomas."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            genomes = await daemon.genome_get_all()
            return web.json_response(_make_response(data=genomes))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_genome_ranking(self, request: web.Request) -> web.Response:
        """GET /v1/genome/ranking - Ranking de fitness."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            ranking = await daemon.genome_ranking()
            return web.json_response(_make_response(data=ranking))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_genome_stats(self, request: web.Request) -> web.Response:
        """GET /v1/genome/stats - Estadísticas del genome."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_genome_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Knowledge Distillation Endpoints (Sprint 8)
    # --------------------------------------------------------
    async def handle_distill(self, request: web.Request) -> web.Response:
        """POST /v1/knowledge/distill - Destilar conocimiento."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.distill_knowledge(
                source=body["source"],
                domain=body.get("domain", "general"),
                pattern=body.get("pattern", ""),
                effectiveness=body.get("effectiveness", 0.5),
                context=body.get("context"),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_transfer(self, request: web.Request) -> web.Response:
        """POST /v1/knowledge/transfer - Transferir conocimiento."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            transfers = await daemon.transfer_knowledge(
                source=body["source"],
                targets=body.get("targets"),
                domain=body.get("domain"),
            )
            return web.json_response(_make_response(data=transfers))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_knowledge_get(self, request: web.Request) -> web.Response:
        """GET /v1/knowledge/agents/{agent} - Conocimiento de un agente."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.match_info["agent"]
            if not _validate_name(agent):
                return web.json_response(
                    _make_response(error="Nombre de agente invalido", status=400),
                    status=400,
                )
            domain = request.query.get("domain")
            knowledge = await daemon.get_knowledge(agent, domain)
            return web.json_response(_make_response(data=knowledge))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_find_experts(self, request: web.Request) -> web.Response:
        """GET /v1/knowledge/experts/{domain} - Expertos en un dominio."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            domain = request.match_info["domain"]
            if not _validate_name(domain):
                return web.json_response(
                    _make_response(error="Dominio invalido", status=400),
                    status=400,
                )
            experts = await daemon.find_experts(domain)
            return web.json_response(_make_response(data=experts))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_distillation_stats(self, request: web.Request) -> web.Response:
        """GET /v1/knowledge/stats - Estadísticas de destilación."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_distillation_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Adversarial Arena Endpoints (Sprint 8)
    # --------------------------------------------------------
    async def handle_arena_challenge(self, request: web.Request) -> web.Response:
        """POST /v1/arena/challenges - Crear challenge."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            challenge = await daemon.arena_create_challenge(
                challenger=body["challenger"],
                defender=body["defender"],
                challenge_type=body.get("challenge_type", "edge_case"),
                description=body.get("description", ""),
                difficulty=body.get("difficulty", 0.5),
            )
            return web.json_response(_make_response(data=challenge))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_arena_respond(self, request: web.Request) -> web.Response:
        """POST /v1/arena/challenges/{id}/respond - Responder challenge."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            challenge_id = request.match_info["id"]
            if not _validate_name(challenge_id):
                return web.json_response(
                    _make_response(error="ID de challenge invalido", status=400),
                    status=400,
                )
            body = await request.json()
            result = await daemon.arena_submit_response(
                challenge_id,
                success=body.get("success", True),
                quality=body.get("quality", 0.5),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_arena_rankings(self, request: web.Request) -> web.Response:
        """GET /v1/arena/rankings - Rankings."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            sort_by = request.query.get("sort", "elo")
            rankings = await daemon.arena_get_rankings(sort_by)
            return web.json_response(_make_response(data=rankings))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_arena_profile(self, request: web.Request) -> web.Response:
        """GET /v1/arena/agents/{agent} - Perfil adversarial."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.match_info["agent"]
            if not _validate_name(agent):
                return web.json_response(
                    _make_response(error="Nombre de agente invalido", status=400),
                    status=400,
                )
            profile = await daemon.arena_get_profile(agent)
            return web.json_response(_make_response(data=profile))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_arena_matchups(self, request: web.Request) -> web.Response:
        """GET /v1/arena/matchups - Matchups sugeridos."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            matchups = await daemon.arena_get_matchups()
            return web.json_response(_make_response(data=matchups))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_arena_history(self, request: web.Request) -> web.Response:
        """GET /v1/arena/history - Historial de batallas."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.query.get("agent")
            limit = int(request.query.get("limit", "50"))
            history = await daemon.arena_battle_history(agent, limit)
            return web.json_response(_make_response(data=history))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_arena_stats(self, request: web.Request) -> web.Response:
        """GET /v1/arena/stats - Estadísticas de la arena."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_arena_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Nervous System Endpoints (Sprint 9A)
    # --------------------------------------------------------
    async def handle_ws_broadcast(self, request: web.Request) -> web.Response:
        """POST /v1/ws/broadcast - Broadcast por WebSocket."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.ws_broadcast(body["topic"], body["payload"])
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_ws_connect(self, request: web.Request) -> web.Response:
        """POST /v1/ws/connect - Conectar cliente WebSocket."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.ws_connect(body.get("client_id"))
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_ws_subscribe(self, request: web.Request) -> web.Response:
        """POST /v1/ws/subscribe - Suscribir cliente a topics."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.ws_subscribe(body["client_id"], body["topics"])
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_ws_clients(self, request: web.Request) -> web.Response:
        """GET /v1/ws/clients - Listar clientes WebSocket."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            clients = await daemon.ws_get_clients()
            return web.json_response(_make_response(data=clients))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_ws_stats(self, request: web.Request) -> web.Response:
        """GET /v1/ws/stats - Estadísticas de WebSocket."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_ws_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_dashboard_snapshot(self, request: web.Request) -> web.Response:
        """GET /v1/dashboard/snapshot - Snapshot del dashboard."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            snapshot = await daemon.dashboard_snapshot()
            return web.json_response(_make_response(data=snapshot))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_dashboard_timeline(self, request: web.Request) -> web.Response:
        """GET /v1/dashboard/timeline - Timeline del dashboard."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            minutes = int(request.query.get("minutes", "30"))
            category = request.query.get("category")
            timeline = await daemon.dashboard_timeline(minutes=minutes, category=category)
            return web.json_response(_make_response(data=timeline))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_dashboard_stats(self, request: web.Request) -> web.Response:
        """GET /v1/dashboard/stats - Estadísticas del dashboard."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_dashboard_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_alert_fire(self, request: web.Request) -> web.Response:
        """POST /v1/alerts/fire - Disparar alerta."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.alert_fire(
                rule_id=body["rule_id"],
                agent=body["agent"],
                detail=body.get("detail", ""),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_alert_resolve(self, request: web.Request) -> web.Response:
        """POST /v1/alerts/resolve - Resolver alerta."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.alert_resolve(
                rule_id=body["rule_id"],
                agent=body["agent"],
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_alert_active(self, request: web.Request) -> web.Response:
        """GET /v1/alerts/active - Alertas activas."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            severity = request.query.get("severity")
            alerts = await daemon.alert_get_active(severity=severity)
            return web.json_response(_make_response(data=alerts))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_alert_stats(self, request: web.Request) -> web.Response:
        """GET /v1/alerts/stats - Estadísticas de alertas."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_alert_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Federation Endpoints (Sprint 9B)
    # --------------------------------------------------------
    async def handle_federation_register_local(self, request: web.Request) -> web.Response:
        """POST /v1/federation/local - Registrar nodo local."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.federation_register_local(
                name=body["name"],
                endpoint=body["endpoint"],
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_federation_register_peer(self, request: web.Request) -> web.Response:
        """POST /v1/federation/peers - Registrar peer remoto."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.federation_register_peer(
                node_id=body["node_id"],
                name=body["name"],
                endpoint=body["endpoint"],
                capabilities=body.get("capabilities", []),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_federation_delegate(self, request: web.Request) -> web.Response:
        """POST /v1/federation/delegate - Delegar tarea a nodo remoto."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.federation_delegate(
                target_node=body["target_node"],
                agent=body["agent"],
                task=body["task"],
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_federation_peers(self, request: web.Request) -> web.Response:
        """GET /v1/federation/peers - Listar peers."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            peers = await daemon.federation_get_peers()
            return web.json_response(_make_response(data=peers))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_federation_stats(self, request: web.Request) -> web.Response:
        """GET /v1/federation/stats - Estadísticas de federación."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_federation_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_marketplace_publish(self, request: web.Request) -> web.Response:
        """POST /v1/marketplace/publish - Publicar skill en marketplace."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.marketplace_publish(
                skill_name=body["skill_name"],
                provider=body["provider"],
                domain=body.get("domain", "general"),
                description=body.get("description", ""),
                quality=body.get("quality", 0.5),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_marketplace_search(self, request: web.Request) -> web.Response:
        """GET /v1/marketplace/search - Buscar en marketplace."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            query = request.query.get("q", "")
            domain = request.query.get("domain")
            results = await daemon.marketplace_search(query=query, domain=domain)
            return web.json_response(_make_response(data=results))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_marketplace_acquire(self, request: web.Request) -> web.Response:
        """POST /v1/marketplace/acquire - Adquirir skill del marketplace."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.marketplace_acquire(
                skill_name=body["skill_name"],
                requester=body["requester"],
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_marketplace_trending(self, request: web.Request) -> web.Response:
        """GET /v1/marketplace/trending - Skills trending."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            trending = await daemon.marketplace_trending()
            return web.json_response(_make_response(data=trending))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_marketplace_stats(self, request: web.Request) -> web.Response:
        """GET /v1/marketplace/stats - Estadísticas del marketplace."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_marketplace_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_trust_set(self, request: web.Request) -> web.Response:
        """POST /v1/trust/set - Establecer nivel de confianza."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.trust_set(
                target=body["target"],
                trust=body["trust"],
                evidence=body.get("evidence", ""),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_trust_calculate(self, request: web.Request) -> web.Response:
        """GET /v1/trust/calculate/{target} - Calcular confianza."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            target = request.match_info["target"]
            if not _validate_name(target):
                return web.json_response(
                    _make_response(error="Target invalido", status=400),
                    status=400,
                )
            result = await daemon.trust_calculate(target)
            return web.json_response(_make_response(data={"trust": result}))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_trust_graph(self, request: web.Request) -> web.Response:
        """GET /v1/trust/graph - Grafo de confianza."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            graph = await daemon.trust_get_graph()
            return web.json_response(_make_response(data=graph))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_trust_stats(self, request: web.Request) -> web.Response:
        """GET /v1/trust/stats - Estadísticas de confianza."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_trust_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Cortex Endpoints (Sprint 9C)
    # --------------------------------------------------------
    async def handle_meta_record(self, request: web.Request) -> web.Response:
        """POST /v1/metacognition/record - Registrar decisión metacognitiva."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.meta_record(
                decision=body["decision"],
                strategy=body["strategy"],
                outcome=body.get("outcome", ""),
                quality=body.get("quality", 0.5),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_meta_diagnose(self, request: web.Request) -> web.Response:
        """GET /v1/metacognition/diagnose - Diagnóstico metacognitivo."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            diagnosis = await daemon.meta_diagnose()
            return web.json_response(_make_response(data=diagnosis))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_meta_recommendations(self, request: web.Request) -> web.Response:
        """GET /v1/metacognition/recommendations - Recomendaciones metacognitivas."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            recommendations = await daemon.meta_recommendations()
            return web.json_response(_make_response(data=recommendations))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_meta_stats(self, request: web.Request) -> web.Response:
        """GET /v1/metacognition/stats - Estadísticas de metacognición."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_metacognition_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_goal_create(self, request: web.Request) -> web.Response:
        """POST /v1/goals/create - Crear objetivo."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.goal_create(
                title=body["title"],
                category=body.get("category", "general"),
                priority=body.get("priority", 0.5),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_goal_active(self, request: web.Request) -> web.Response:
        """GET /v1/goals/active - Objetivos activos."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            category = request.query.get("category")
            goals = await daemon.goal_get_active(category=category)
            return web.json_response(_make_response(data=goals))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_goal_progress(self, request: web.Request) -> web.Response:
        """POST /v1/goals/{goal_id}/progress - Actualizar progreso de objetivo."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            goal_id = request.match_info["goal_id"]
            if not _validate_name(goal_id):
                return web.json_response(
                    _make_response(error="ID de objetivo invalido", status=400),
                    status=400,
                )
            body = await request.json()
            result = await daemon.goal_update_progress(goal_id, body["progress"])
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_goal_stats(self, request: web.Request) -> web.Response:
        """GET /v1/goals/stats - Estadísticas de objetivos."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_goal_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_emergent_observe(self, request: web.Request) -> web.Response:
        """POST /v1/emergent/observe - Observar comportamiento emergente."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            result = await daemon.emergent_observe(
                agents=body["agents"],
                pattern=body["pattern"],
                effectiveness=body.get("effectiveness", 0.5),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_emergent_detect(self, request: web.Request) -> web.Response:
        """POST /v1/emergent/detect - Detectar patrones emergentes."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            result = await daemon.emergent_detect()
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_emergent_patterns(self, request: web.Request) -> web.Response:
        """GET /v1/emergent/patterns - Patrones emergentes detectados."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            patterns = await daemon.emergent_get_patterns()
            return web.json_response(_make_response(data=patterns))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_emergent_stats(self, request: web.Request) -> web.Response:
        """GET /v1/emergent/stats - Estadísticas de comportamiento emergente."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_emergent_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Intelligence Aggregation Endpoints (Evolución Panel)
    # --------------------------------------------------------
    async def handle_agent_performance(self, request: web.Request) -> web.Response:
        """GET /v1/intelligence/agent-performance - Rendimiento agregado de agentes.

        Combina datos de reputación, contratos y genoma para devolver
        métricas de performance por agente. Si los subsistemas no están
        disponibles, retorna lista vacía (el frontend maneja ese caso).
        """
        from .._gateway_main import _make_response

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()

            performance: list[dict] = []
            try:
                # Fuente principal: reputation rankings (tiene success rate y scores)
                rankings = await daemon.get_reputation_rankings(limit=20)
                for entry in rankings:
                    performance.append(
                        {
                            "agent": entry.get("agent", "unknown"),
                            "success_rate": entry.get("success_rate", 0),
                            "avg_quality": entry.get("trust_score", entry.get("score", 0)),
                            "avg_duration": entry.get("avg_duration", 0),
                            "total_tasks": entry.get("total_outcomes", 0),
                            "trend": "stable",
                        }
                    )
            except Exception:
                pass

            # Si no hay datos de reputación, intentar con genome ranking
            if not performance:
                try:
                    genomes = await daemon.genome_ranking()
                    for entry in genomes[:20]:
                        performance.append(
                            {
                                "agent": entry.get("agent", "unknown"),
                                "success_rate": entry.get("fitness", 0),
                                "avg_quality": entry.get("fitness", 0),
                                "avg_duration": 0,
                                "total_tasks": 0,
                                "trend": "stable",
                            }
                        )
                except Exception:
                    pass

            return web.json_response(_make_response(data=performance))
        except Exception as e:
            log.warning("Error en agent-performance: %s", e)
            return web.json_response(_make_response(data=[]))

    async def handle_skill_effectiveness(self, request: web.Request) -> web.Response:
        """GET /v1/intelligence/skill-effectiveness - Efectividad de skills.

        Agrega datos del marketplace y knowledge distillation para devolver
        métricas de uso y efectividad por skill. Si los subsistemas no están
        disponibles, retorna lista vacía.
        """
        from .._gateway_main import _make_response

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()

            effectiveness: list[dict] = []
            try:
                # Fuente: marketplace trending (tiene uso y quality)
                trending = await daemon.marketplace_trending(limit=20)
                for entry in trending:
                    effectiveness.append(
                        {
                            "skill": entry.get("skill_name", entry.get("name", "unknown")),
                            "uses": entry.get("acquisitions", entry.get("usage_count", 0)),
                            "success_rate": entry.get("quality", 0),
                            "composite_score": entry.get("quality", 0),
                            "top_agents": entry.get("top_consumers", [])[:3],
                        }
                    )
            except Exception:
                pass

            # Si no hay datos de marketplace, intentar knowledge experts
            if not effectiveness:
                try:
                    for domain in ("general", "code", "analysis"):
                        experts = await daemon.find_experts(domain)
                        for entry in experts[:5]:
                            effectiveness.append(
                                {
                                    "skill": entry.get("domain", domain),
                                    "uses": entry.get("knowledge_count", 0),
                                    "success_rate": entry.get("effectiveness", 0),
                                    "composite_score": entry.get("effectiveness", 0),
                                    "top_agents": [entry.get("agent", "")][:3],
                                }
                            )
                except Exception:
                    pass

            return web.json_response(_make_response(data=effectiveness))
        except Exception as e:
            log.warning("Error en skill-effectiveness: %s", e)
            return web.json_response(_make_response(data=[]))
