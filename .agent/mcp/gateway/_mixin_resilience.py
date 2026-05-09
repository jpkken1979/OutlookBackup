"""Mixin: handlers de resiliencia — chronicle, circuit breaker, prefetch, contracts."""

from __future__ import annotations

import logging

from aiohttp import web
from ._mixin_advanced import _get_daemon_safe, _daemon_unavailable_response


log = logging.getLogger("antigravity-gateway")


class _ResilienceMixin:
    """Handlers de resiliencia: chronicle, breaker, prefetch, contracts."""

    # --------------------------------------------------------
    # Chronicle Endpoints (Sprint 6)
    # --------------------------------------------------------
    async def handle_chronicle_record(self, request: web.Request) -> web.Response:
        """POST /v1/chronicle/record - Registra evento en chronicle."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            entry = await daemon.chronicle_record(
                event_type=body["event_type"],
                action=body.get("action", ""),
                agent=body.get("agent"),
                data=body.get("data"),
                caused_by=body.get("caused_by"),
                correlation_id=body.get("correlation_id"),
                severity=body.get("severity", "info"),
            )
            return web.json_response(_make_response(data=entry))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_chronicle_query(self, request: web.Request) -> web.Response:
        """GET /v1/chronicle/events - Consulta eventos."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            since = request.query.get("since")
            until = request.query.get("until")
            events = await daemon.chronicle_query(
                since=float(since) if since else None,
                until=float(until) if until else None,
                agent=request.query.get("agent"),
                event_type=request.query.get("event_type"),
                severity=request.query.get("severity"),
                limit=int(request.query.get("limit", "100")),
            )
            return web.json_response(_make_response(data=events))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_chronicle_trace_cause(self, request: web.Request) -> web.Response:
        """GET /v1/chronicle/events/{entry_id}/cause - Traza cadena causal."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            entry_id = request.match_info["entry_id"]
            chain = await daemon.chronicle_trace_cause(entry_id)
            return web.json_response(_make_response(data=chain))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_chronicle_trace_effects(self, request: web.Request) -> web.Response:
        """GET /v1/chronicle/events/{entry_id}/effects - Traza efectos."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            entry_id = request.match_info["entry_id"]
            effects = await daemon.chronicle_trace_effects(entry_id)
            return web.json_response(_make_response(data=effects))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_chronicle_root_cause(self, request: web.Request) -> web.Response:
        """GET /v1/chronicle/events/{entry_id}/root-cause - Root cause analysis."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            entry_id = request.match_info["entry_id"]
            analysis = await daemon.chronicle_root_cause(entry_id)
            return web.json_response(_make_response(data=analysis))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_chronicle_snapshot(self, request: web.Request) -> web.Response:
        """POST /v1/chronicle/snapshots - Crear snapshot manual."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            snapshot = await daemon.chronicle_create_snapshot(
                label=body.get("label", ""),
                state=body.get("state"),
            )
            return web.json_response(_make_response(data=snapshot))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_chronicle_snapshots_list(self, request: web.Request) -> web.Response:
        """GET /v1/chronicle/snapshots - Listar snapshots."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            snapshots = await daemon.chronicle_list_snapshots()
            return web.json_response(_make_response(data=snapshots))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_chronicle_state_at(self, request: web.Request) -> web.Response:
        """GET /v1/chronicle/state - Reconstruir estado en timestamp."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            ts = request.query.get("timestamp")
            if not ts:
                return web.json_response(
                    _make_response(error="timestamp required", status=400),
                    status=400,
                )
            state = await daemon.chronicle_get_state_at(float(ts))
            return web.json_response(_make_response(data=state))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_chronicle_stats(self, request: web.Request) -> web.Response:
        """GET /v1/chronicle/stats - Estadísticas del chronicle."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_chronicle_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # CircuitBreaker Endpoints (Sprint 7)
    # --------------------------------------------------------
    async def handle_breaker_status(self, request: web.Request) -> web.Response:
        """GET /v1/breaker/agents/{agent} - Estado de un breaker."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.match_info["agent"]
            status = await daemon.breaker_get_status(agent)
            return web.json_response(_make_response(data=status))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_breaker_all(self, request: web.Request) -> web.Response:
        """GET /v1/breaker - Estado de todos los breakers."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            breakers = await daemon.breaker_get_all()
            return web.json_response(_make_response(data=breakers))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_breaker_open(self, request: web.Request) -> web.Response:
        """GET /v1/breaker/open - Circuitos abiertos."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            circuits = await daemon.breaker_get_open()
            return web.json_response(_make_response(data=circuits))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_breaker_reset(self, request: web.Request) -> web.Response:
        """POST /v1/breaker/agents/{agent}/reset - Forzar reset."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.match_info["agent"]
            result = await daemon.breaker_force_reset(agent)
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_breaker_configure(self, request: web.Request) -> web.Response:
        """POST /v1/breaker/agents/{agent}/configure - Configurar breaker."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.match_info["agent"]
            body = await request.json()
            result = await daemon.breaker_configure(
                agent,
                failure_threshold=body.get("failure_threshold"),
                recovery_timeout=body.get("recovery_timeout"),
                max_concurrent=body.get("max_concurrent"),
                fallbacks=body.get("fallbacks"),
            )
            return web.json_response(_make_response(data=result))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_breaker_health(self, request: web.Request) -> web.Response:
        """GET /v1/breaker/health - Resumen de salud."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            health = await daemon.breaker_health()
            return web.json_response(_make_response(data=health))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_breaker_stats(self, request: web.Request) -> web.Response:
        """GET /v1/breaker/stats - Estadísticas de breakers."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_breaker_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # PredictivePrefetch Endpoints (Sprint 7)
    # --------------------------------------------------------
    async def handle_prefetch_predict(self, request: web.Request) -> web.Response:
        """GET /v1/prefetch/predict - Predecir próximos agentes."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            predictions = await daemon.prefetch_predict(
                current_agent=request.query.get("agent"),
                current_domain=request.query.get("domain"),
                limit=int(request.query.get("limit", "5")),
            )
            return web.json_response(_make_response(data=predictions))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_prefetch_warmup(self, request: web.Request) -> web.Response:
        """GET /v1/prefetch/warmup - Lista de agentes a pre-calentar."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            warmup = await daemon.prefetch_warmup(
                current_agent=request.query.get("agent"),
            )
            return web.json_response(_make_response(data=warmup))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_prefetch_sequences(self, request: web.Request) -> web.Response:
        """GET /v1/prefetch/sequences - Secuencias frecuentes."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            sequences = await daemon.prefetch_sequences()
            return web.json_response(_make_response(data=sequences))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_prefetch_matrix(self, request: web.Request) -> web.Response:
        """GET /v1/prefetch/matrix - Matriz de transición."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            matrix = await daemon.prefetch_matrix()
            return web.json_response(_make_response(data=matrix))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_prefetch_accuracy(self, request: web.Request) -> web.Response:
        """GET /v1/prefetch/accuracy - Precisión de predicciones."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            accuracy = await daemon.prefetch_accuracy()
            return web.json_response(_make_response(data=accuracy))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_prefetch_stats(self, request: web.Request) -> web.Response:
        """GET /v1/prefetch/stats - Estadísticas del motor predictivo."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_prefetch_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # Contract Endpoints (Sprint 7)
    # --------------------------------------------------------
    async def handle_contract_create(self, request: web.Request) -> web.Response:
        """POST /v1/contracts - Crear contrato SLA."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            body = await request.json()
            contract = await daemon.contract_create(
                agent=body["agent"],
                max_response_time=body.get("max_response_time", 30.0),
                min_success_rate=body.get("min_success_rate", 0.75),
                domains=body.get("domains"),
            )
            return web.json_response(_make_response(data=contract))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_contract_list(self, request: web.Request) -> web.Response:
        """GET /v1/contracts - Listar contratos."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            status = request.query.get("status")
            contracts = await daemon.contract_list(status)
            return web.json_response(_make_response(data=contracts))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_contract_get(self, request: web.Request) -> web.Response:
        """GET /v1/contracts/agents/{agent} - Obtener contrato."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.match_info["agent"]
            contract = await daemon.contract_get(agent)
            if not contract:
                return web.json_response(
                    _make_response(error="No contract", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data=contract))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_contract_compliance(self, request: web.Request) -> web.Response:
        """GET /v1/contracts/agents/{agent}/compliance - Verificar cumplimiento."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.match_info["agent"]
            compliance = await daemon.contract_check_compliance(agent)
            return web.json_response(_make_response(data=compliance))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_contract_compliance_all(self, request: web.Request) -> web.Response:
        """GET /v1/contracts/compliance - Cumplimiento de todos."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            compliance = await daemon.contract_check_all()
            return web.json_response(_make_response(data=compliance))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_contract_violations(self, request: web.Request) -> web.Response:
        """GET /v1/contracts/violations - Listar violaciones."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.query.get("agent")
            limit = int(request.query.get("limit", "50"))
            violations = await daemon.contract_get_violations(agent, limit)
            return web.json_response(_make_response(data=violations))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_contract_auto(self, request: web.Request) -> web.Response:
        """POST /v1/contracts/agents/{agent}/auto - Auto-generar contrato."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            agent = request.match_info["agent"]
            contract = await daemon.contract_auto_generate(agent)
            return web.json_response(_make_response(data=contract))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_contract_stats(self, request: web.Request) -> web.Response:
        """GET /v1/contracts/stats - Estadísticas de contratos."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await daemon.get_contract_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )
