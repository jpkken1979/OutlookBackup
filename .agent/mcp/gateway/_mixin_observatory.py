"""Mixin: handlers del observatorio — observatory, reputation, topology."""

from __future__ import annotations

import logging

from aiohttp import web
from ._mixin_advanced import _get_daemon_safe, _daemon_unavailable_response


log = logging.getLogger("antigravity-gateway")


class _ObservatoryMixin:
    """Handlers de observatorio: observatory, reputation, topology."""

    # --------------------------------------------------------
    # Observatory Endpoints (Sprint 5)
    # --------------------------------------------------------
    async def handle_observatory_timeline(self, request: web.Request) -> web.Response:
        """GET /v1/observatory/timeline - Timeline unificado."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            limit = int(request.query.get("limit", "50"))
            event_type = request.query.get("event_type")
            agent = request.query.get("agent")
            severity = request.query.get("severity")
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            timeline = await daemon.get_observatory_timeline(
                limit=limit,
                event_type=event_type,
                agent=agent,
                severity=severity,
            )
            return web.json_response(_make_response(data=timeline))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_observatory_snapshot(self, request: web.Request) -> web.Response:
        """GET /v1/observatory/snapshot - Snapshot del ecosistema."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            snapshot = await daemon.get_ecosystem_snapshot()
            return web.json_response(_make_response(data=snapshot))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_observatory_stats(self, request: web.Request) -> web.Response:
        """GET /v1/observatory/stats - Estadísticas del observatorio."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_observatory_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Reputation Endpoints (Sprint 6)
    # --------------------------------------------------------
    async def handle_reputation_outcome(self, request: web.Request) -> web.Response:
        """POST /v1/reputation/outcome - Registra resultado de reputación."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            record = await daemon.record_reputation_outcome(
                agent=body["agent"],
                domain=body.get("domain", "general"),
                success=body.get("success", True),
                duration=body.get("duration", 0.0),
                partial=body.get("partial", False),
                timeout=body.get("timeout", False),
                metadata=body.get("metadata"),
            )
            return web.json_response(_make_response(data=record))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reputation_trust(self, request: web.Request) -> web.Response:
        """GET /v1/reputation/agents/{agent}/trust - Trust de un agente."""
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
            domain = request.query.get("domain", "general")
            trust = await daemon.get_agent_trust(agent, domain)
            return web.json_response(_make_response(data=trust))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reputation_profile(self, request: web.Request) -> web.Response:
        """GET /v1/reputation/agents/{agent} - Perfil de reputación."""
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
            profile = await daemon.get_agent_reputation_profile(agent)
            return web.json_response(_make_response(data=profile))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reputation_rankings(self, request: web.Request) -> web.Response:
        """GET /v1/reputation/rankings - Rankings de reputación."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            domain = request.query.get("domain")
            limit = int(request.query.get("limit", "20"))
            rankings = await daemon.get_reputation_rankings(domain, limit)
            return web.json_response(_make_response(data=rankings))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reputation_vouch(self, request: web.Request) -> web.Response:
        """POST /v1/reputation/vouch - Un agente voucha por otro."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            record = await daemon.vouch_for_agent(
                voucher=body["voucher"],
                vouchee=body["vouchee"],
                domain=body["domain"],
                weight=body.get("weight", 0.5),
            )
            return web.json_response(_make_response(data=record))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reputation_stats(self, request: web.Request) -> web.Response:
        """GET /v1/reputation/stats - Estadísticas de reputación."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_reputation_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_reputation_history(self, request: web.Request) -> web.Response:
        """GET /v1/reputation/history - Historial de reputación."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.query.get("agent")
            domain = request.query.get("domain")
            limit = int(request.query.get("limit", "50"))
            history = await daemon.get_reputation_history(agent, domain, limit)
            return web.json_response(_make_response(data=history))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Topology Endpoints (Sprint 6)
    # --------------------------------------------------------
    async def handle_topology_interaction(self, request: web.Request) -> web.Response:
        """POST /v1/topology/interaction - Registra interacción."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            edge = await daemon.record_topology_interaction(
                source=body["source"],
                target=body["target"],
                domain=body.get("domain", "general"),
                success=body.get("success", True),
            )
            return web.json_response(_make_response(data=edge))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_topology_neighbors(self, request: web.Request) -> web.Response:
        """GET /v1/topology/agents/{agent}/neighbors - Vecinos preferidos."""
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
            limit = int(request.query.get("limit", "10"))
            neighbors = await daemon.get_topology_neighbors(agent, limit)
            return web.json_response(_make_response(data=neighbors))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_topology_recommend(self, request: web.Request) -> web.Response:
        """GET /v1/topology/agents/{agent}/recommend - Recomendar colaborador."""
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
            domain = request.query.get("domain", "general")
            result = await daemon.recommend_collaborator(agent, domain)
            return web.json_response(_make_response(data={"recommended": result}))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_topology_clusters(self, request: web.Request) -> web.Response:
        """GET /v1/topology/clusters - Detectar clusters."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            clusters = await daemon.get_topology_clusters()
            return web.json_response(_make_response(data=clusters))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_topology_bottlenecks(self, request: web.Request) -> web.Response:
        """GET /v1/topology/bottlenecks - Detectar cuellos de botella."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            bottlenecks = await daemon.get_topology_bottlenecks()
            return web.json_response(_make_response(data=bottlenecks))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_topology_graph(self, request: web.Request) -> web.Response:
        """GET /v1/topology/graph - Exportar grafo completo."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            graph = await daemon.get_topology_graph()
            return web.json_response(_make_response(data=graph))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_topology_stats(self, request: web.Request) -> web.Response:
        """GET /v1/topology/stats - Estadísticas de topología."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_topology_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )
