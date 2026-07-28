"""Mixin: handlers de swarm — reactive, negotiation, swarm, router, consensus."""

from __future__ import annotations

import asyncio
import logging

from aiohttp import web
from ._mixin_advanced import _get_daemon_safe, _daemon_unavailable_response


log = logging.getLogger("antigravity-gateway")


class _SwarmMixin:
    """Handlers de swarm: reactive, negotiation, swarm, router, consensus."""

    # --------------------------------------------------------
    # ReactiveEventSystem Endpoints (Sprint 4)
    # --------------------------------------------------------
    async def handle_reactive_emit(self, request: web.Request) -> web.Response:
        """POST /v1/reactive/emit - Emite un evento al sistema reactivo."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
            event_type = body.get("event_type")
            source = body.get("source", "api")
            data = body.get("data", {})
            severity = body.get("severity", "info")
            if not event_type:
                return web.json_response(
                    _make_response(error="event_type requerido", status=400),
                    status=400,
                )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            event = await daemon.emit_event(event_type, source, data, severity)
            return web.json_response(_make_response(data=event))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reactive_rules(self, request: web.Request) -> web.Response:
        """GET /v1/reactive/rules - Lista reglas reactivas."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            rules = await daemon.list_reactive_rules()
            return web.json_response(_make_response(data=rules))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reactive_register_rule(self, request: web.Request) -> web.Response:
        """POST /v1/reactive/rules - Registra una nueva regla reactiva."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
            for field in ("name", "event_type", "pattern", "agent", "task_template"):
                if field not in body:
                    return web.json_response(
                        _make_response(error=f"Campo '{field}' requerido", status=400),
                        status=400,
                    )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            rule = await daemon.register_reactive_rule(body)
            return web.json_response(_make_response(data=rule), status=201)
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reactive_toggle_rule(self, request: web.Request) -> web.Response:
        """POST /v1/reactive/rules/{name}/toggle - Habilita/deshabilita regla."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            name = request.match_info["name"]
            if not _validate_name(name):
                return web.json_response(
                    _make_response(error="Nombre de regla invalido", status=400),
                    status=400,
                )
            body = await request.json()
            enabled = body.get("enabled", True)
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            ok = await daemon.toggle_reactive_rule(name, enabled)
            if not ok:
                return web.json_response(
                    _make_response(error=f"Regla '{name}' no encontrada", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data={"name": name, "enabled": enabled}))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reactive_events_history(self, request: web.Request) -> web.Response:
        """GET /v1/reactive/events - Historial de eventos."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            limit = int(request.query.get("limit", "50"))
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            events = await daemon.get_event_history(limit)
            return web.json_response(_make_response(data=events))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reactive_triggers_history(self, request: web.Request) -> web.Response:
        """GET /v1/reactive/triggers - Historial de triggers."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            limit = int(request.query.get("limit", "50"))
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            triggers = await daemon.get_trigger_history(limit)
            return web.json_response(_make_response(data=triggers))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reactive_stats(self, request: web.Request) -> web.Response:
        """GET /v1/reactive/stats - Estadísticas del sistema reactivo."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_reactive_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Negotiation Endpoints (Sprint 4)
    # --------------------------------------------------------
    async def handle_negotiation_auction(self, request: web.Request) -> web.Response:
        """POST /v1/negotiation/auction - Subasta una tarea entre agentes."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
            task = body.get("task")
            if not task:
                return web.json_response(
                    _make_response(error="task requerido", status=400),
                    status=400,
                )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            result = await daemon.auction_task(
                task=task,
                required_capabilities=body.get("required_capabilities"),
                strategy=body.get("strategy", "balanced"),
                from_agent=body.get("from_agent", "api"),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_negotiation_agents(self, request: web.Request) -> web.Response:
        """GET /v1/negotiation/agents - Lista agentes registrados para negociación."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agents = await daemon.list_negotiation_agents()
            return web.json_response(_make_response(data=agents))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_negotiation_history(self, request: web.Request) -> web.Response:
        """GET /v1/negotiation/auctions - Historial de subastas."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            limit = int(request.query.get("limit", "50"))
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            history = await daemon.get_auction_history(limit)
            return web.json_response(_make_response(data=history))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_negotiation_auction_get(self, request: web.Request) -> web.Response:
        """GET /v1/negotiation/auctions/{auction_id} - Detalle de una subasta."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            auction_id = request.match_info["auction_id"]
            if not _validate_name(auction_id):
                return web.json_response(
                    _make_response(error="ID de subasta invalido", status=400),
                    status=400,
                )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            auction = await daemon.get_auction(auction_id)
            if auction is None:
                return web.json_response(
                    _make_response(error="Subasta no encontrada", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data=auction))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_negotiation_stats(self, request: web.Request) -> web.Response:
        """GET /v1/negotiation/stats - Estadísticas de negociación."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_negotiation_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Swarm Endpoints (Sprint 4)
    # --------------------------------------------------------
    async def handle_swarm_execute(self, request: web.Request) -> web.Response:
        """POST /v1/swarm/execute - Ejecuta un enjambre multi-agente."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
            task = body.get("task")
            if not task:
                return web.json_response(
                    _make_response(error="task requerido", status=400),
                    status=400,
                )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            result = await daemon.execute_swarm(
                task=task,
                agents=body.get("agents"),
                mode=body.get("mode", "dag"),
                context=body.get("context"),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_swarm_list(self, request: web.Request) -> web.Response:
        """GET /v1/swarm - Lista swarms."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            status = request.query.get("status")
            limit = int(request.query.get("limit", "50"))
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            swarms = await daemon.list_swarms(status, limit)
            return web.json_response(_make_response(data=swarms))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_swarm_get(self, request: web.Request) -> web.Response:
        """GET /v1/swarm/{swarm_id} - Detalle de un swarm."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            swarm_id = request.match_info["swarm_id"]
            if not _validate_name(swarm_id):
                return web.json_response(
                    _make_response(error="ID de swarm invalido", status=400),
                    status=400,
                )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            swarm = await daemon.get_swarm(swarm_id)
            if swarm is None:
                return web.json_response(
                    _make_response(error="Swarm no encontrado", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data=swarm))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_swarm_cancel(self, request: web.Request) -> web.Response:
        """POST /v1/swarm/{swarm_id}/cancel - Cancela un swarm."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            swarm_id = request.match_info["swarm_id"]
            if not _validate_name(swarm_id):
                return web.json_response(
                    _make_response(error="ID de swarm invalido", status=400),
                    status=400,
                )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            ok = await daemon.cancel_swarm(swarm_id)
            if not ok:
                return web.json_response(
                    _make_response(error="Swarm no encontrado o ya finalizado", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data={"swarm_id": swarm_id, "cancelled": True}))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_swarm_stats(self, request: web.Request) -> web.Response:
        """GET /v1/swarm/stats - Estadísticas del coordinador de enjambre."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_swarm_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # IntelligentRouter Endpoints (Sprint 5)
    # --------------------------------------------------------
    async def handle_router_analyze(self, request: web.Request) -> web.Response:
        """POST /v1/router/analyze - Analiza tarea y decide ruta (sin ejecutar)."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
            task = body.get("task")
            if not task:
                return web.json_response(
                    _make_response(error="task requerido", status=400),
                    status=400,
                )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            decision = await daemon.analyze_task_route(task)
            return web.json_response(_make_response(data=decision))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_router_execute(self, request: web.Request) -> web.Response:
        """POST /v1/router/execute - Analiza, decide ruta, y ejecuta."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
            task = body.get("task")
            if not task:
                return web.json_response(
                    _make_response(error="task requerido", status=400),
                    status=400,
                )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            result = await daemon.route_and_execute(
                task=task,
                context=body.get("context"),
                from_agent=body.get("from_agent", "api"),
                force_route=body.get("force_route"),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_router_history(self, request: web.Request) -> web.Response:
        """GET /v1/router/history - Historial de decisiones."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            limit = int(request.query.get("limit", "50"))
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            history = await daemon.get_route_history(limit)
            return web.json_response(_make_response(data=history))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_router_stats(self, request: web.Request) -> web.Response:
        """GET /v1/router/stats - Estadísticas del router."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await asyncio.wait_for(
                asyncio.to_thread(daemon.get_router_stats),
                timeout=4.0,
            )
            return web.json_response(_make_response(data=stats))
        except TimeoutError:
            return web.json_response(
                _make_response(
                    data={
                        "status": "not_ready",
                        "message": "Router ocupado o inicializando",
                    }
                ),
                status=200,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Consensus Endpoints (Sprint 5)
    # --------------------------------------------------------
    async def handle_consensus_create(self, request: web.Request) -> web.Response:
        """POST /v1/consensus/proposals - Crea propuesta de consenso."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
            for field in ("question", "options", "voters"):
                if field not in body:
                    return web.json_response(
                        _make_response(error=f"Campo '{field}' requerido", status=400),
                        status=400,
                    )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            proposal = await daemon.create_consensus_proposal(
                question=body["question"],
                options=body["options"],
                voters=body["voters"],
                mode=body.get("mode", "majority"),
            )
            return web.json_response(_make_response(data=proposal), status=201)
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_consensus_vote(self, request: web.Request) -> web.Response:
        """POST /v1/consensus/proposals/{id}/vote - Registra un voto."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            proposal_id = request.match_info["proposal_id"]
            if not _validate_name(proposal_id):
                return web.json_response(
                    _make_response(error="ID de propuesta invalido", status=400),
                    status=400,
                )
            body = await request.json()
            voter = body.get("voter")
            choice = body.get("choice")
            if not voter or not choice:
                return web.json_response(
                    _make_response(error="voter y choice requeridos", status=400),
                    status=400,
                )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            vote = await daemon.cast_consensus_vote(
                proposal_id,
                voter,
                choice,
                confidence=body.get("confidence", 0.8),
                reason=body.get("reason", ""),
            )
            if vote is None:
                return web.json_response(
                    _make_response(error="Voto rechazado", status=400),
                    status=400,
                )
            return web.json_response(_make_response(data=vote))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_consensus_resolve(self, request: web.Request) -> web.Response:
        """POST /v1/consensus/proposals/{id}/resolve - Resuelve propuesta."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            proposal_id = request.match_info["proposal_id"]
            if not _validate_name(proposal_id):
                return web.json_response(
                    _make_response(error="ID de propuesta invalido", status=400),
                    status=400,
                )
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            result = await daemon.resolve_consensus(proposal_id)
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_consensus_quick(self, request: web.Request) -> web.Response:
        """POST /v1/consensus/quick - Propuesta + votos + resolución en un paso."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            body = await request.json()
            for field in ("question", "options", "votes"):
                if field not in body:
                    return web.json_response(
                        _make_response(error=f"Campo '{field}' requerido", status=400),
                        status=400,
                    )
            votes = {
                agent: (v["choice"], v.get("confidence", 0.8), v.get("reason", ""))
                for agent, v in body["votes"].items()
            }
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            result = await daemon.quick_consensus(
                body["question"],
                body["options"],
                votes,
                mode=body.get("mode", "weighted"),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_consensus_list(self, request: web.Request) -> web.Response:
        """GET /v1/consensus/proposals - Lista propuestas."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            status = request.query.get("status")
            limit = int(request.query.get("limit", "50"))
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            proposals = await daemon.list_consensus_proposals(status, limit)
            return web.json_response(_make_response(data=proposals))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_consensus_stats(self, request: web.Request) -> web.Response:
        """GET /v1/consensus/stats - Estadísticas de consenso."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_consensus_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )
