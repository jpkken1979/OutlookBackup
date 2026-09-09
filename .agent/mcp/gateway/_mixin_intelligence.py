"""Mixin: handlers de inteligencia — anomaly, workflow, improvement."""

from __future__ import annotations

import asyncio
import hashlib
import logging

from aiohttp import web
from ._mixin_advanced import _daemon_unavailable_response, _get_daemon_safe

log = logging.getLogger("antigravity-gateway")


def _quality_workflow_id(graph_name: str, idempotency_key: str) -> str:
    digest = hashlib.sha256(f"{graph_name}:{idempotency_key}".encode()).hexdigest()[:24]
    return f"wf-{digest}"


class _IntelligenceMixin:
    """Handlers de inteligencia: anomaly, workflow, improvement."""

    # --------------------------------------------------------
    # AnomalyDetector Handlers (Sprint 2)
    # --------------------------------------------------------
    async def handle_anomaly_alerts(self, request: web.Request) -> web.Response:
        """GET /v1/anomalies/alerts - Lista alertas de anomalía."""
        from .._gateway_main import _make_response, _sanitize_error

        agent = request.query.get("agent")
        severity = request.query.get("severity")
        limit = int(request.query.get("limit", "50"))

        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            alerts = await daemon.get_anomaly_alerts(agent=agent, severity=severity, limit=limit)
            return web.json_response(
                _make_response(
                    data={
                        "alerts": alerts,
                        "count": len(alerts),
                    }
                )
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_anomaly_ack(self, request: web.Request) -> web.Response:
        """POST /v1/anomalies/alerts/:alert_id/ack - Reconoce una alerta."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        alert_id = request.match_info["alert_id"]
        if not _validate_name(alert_id):
            return web.json_response(
                _make_response(error="ID de alerta invalido", status=400),
                status=400,
            )
        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            success = await daemon.acknowledge_anomaly(alert_id)
            if not success:
                return web.json_response(
                    _make_response(error=f"Alerta '{alert_id}' no encontrada", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data={"acknowledged": alert_id}))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_anomaly_profiles(self, request: web.Request) -> web.Response:
        """GET /v1/anomalies/profiles - Lista perfiles de todos los agentes."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            if daemon._anomaly_detector is None:
                return web.json_response(_make_response(data={"profiles": [], "count": 0}))
            profiles = daemon._anomaly_detector.get_all_profiles()
            return web.json_response(
                _make_response(
                    data={
                        "profiles": profiles,
                        "count": len(profiles),
                    }
                )
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_anomaly_agent_profile(self, request: web.Request) -> web.Response:
        """GET /v1/anomalies/profiles/:agent - Perfil de anomalía de un agente."""
        from .._gateway_main import _make_response, _validate_name, _sanitize_error

        agent = request.match_info["agent"]

        if not _validate_name(agent):
            return web.json_response(
                _make_response(error="Nombre de agente inválido", status=400),
                status=400,
            )

        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            profile = await daemon.get_agent_anomaly_profile(agent)
            if profile is None:
                return web.json_response(
                    _make_response(error=f"Perfil de '{agent}' no encontrado", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data=profile))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_anomaly_stats(self, request: web.Request) -> web.Response:
        """GET /v1/anomalies/stats - Estadísticas del AnomalyDetector."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            daemon = await _get_daemon_safe()
            if daemon is None:
                return _daemon_unavailable_response()
            stats = await asyncio.wait_for(
                asyncio.to_thread(daemon.get_anomaly_stats),
                timeout=4.0,
            )
            return web.json_response(_make_response(data=stats))
        except TimeoutError:
            return web.json_response(
                _make_response(
                    data={
                        "status": "not_ready",
                        "message": "Anomaly detector ocupado o inicializando",
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
    # WorkflowEngine Endpoints (Sprint 3)
    # --------------------------------------------------------
    async def handle_workflow_list_graphs(self, request: web.Request) -> web.Response:
        """GET /v1/workflows/graphs - Lista el catálogo cerrado de gates."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            from core.quality_gate_workflows import quality_catalog

            return web.json_response(_make_response(data=quality_catalog()))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_workflow_execute(self, request: web.Request) -> web.Response:
        """POST /v1/workflows/execute - Ejecuta un workflow."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            body = await request.json()
            graph_name = body.get("graph")
            idempotency_key = body.get("idempotency_key")
            if not isinstance(graph_name, str):
                return web.json_response(
                    _make_response(error="Falta campo 'graph'", status=400),
                    status=400,
                )
            if not isinstance(idempotency_key, str) or not _validate_name(idempotency_key):
                return web.json_response(
                    _make_response(error="Idempotency key inválido", status=400),
                    status=400,
                )
            from core.quality_gate_workflows import validate_quality_initial_state
            from core.workflow_engine import get_workflow_engine

            initial_state = validate_quality_initial_state(
                graph_name,
                body.get("state", {}),
            )
            engine = get_workflow_engine()
            result = await engine.execute(
                graph_name,
                initial_state,
                workflow_id=_quality_workflow_id(graph_name, idempotency_key),
            )
            return web.json_response(_make_response(data=result))
        except ValueError as e:
            return web.json_response(
                _make_response(error=str(e), status=400),
                status=400,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_workflow_list(self, request: web.Request) -> web.Response:
        """GET /v1/workflows - Lista workflows."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            status = request.query.get("status")
            limit = max(1, min(int(request.query.get("limit", "50")), 100))
            from core.quality_gate_workflows import QUALITY_GRAPH_IDS
            from core.workflow_engine import get_workflow_engine

            engine = get_workflow_engine()
            workflows = [
                workflow
                for workflow in engine.list_workflows(status, limit * 2)
                if workflow.get("graph_name") in QUALITY_GRAPH_IDS
            ][:limit]
            return web.json_response(_make_response(data=workflows))
        except ValueError as e:
            return web.json_response(
                _make_response(error=str(e), status=400),
                status=400,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_workflow_get(self, request: web.Request) -> web.Response:
        """GET /v1/workflows/{workflow_id} - Estado de un workflow."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            workflow_id = request.match_info["workflow_id"]
            if not _validate_name(workflow_id):
                return web.json_response(
                    _make_response(error="ID de workflow invalido", status=400),
                    status=400,
                )
            from core.quality_gate_workflows import QUALITY_GRAPH_IDS
            from core.workflow_engine import get_workflow_engine

            wf = get_workflow_engine().get_workflow(workflow_id)
            if wf is None or wf.get("graph_name") not in QUALITY_GRAPH_IDS:
                return web.json_response(
                    _make_response(error="Workflow no encontrado", status=404),
                    status=404,
                )
            return web.json_response(_make_response(data=wf))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_workflow_events(self, request: web.Request) -> web.Response:
        """GET /v1/workflows/{workflow_id}/events - Eventos de un workflow."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            workflow_id = request.match_info["workflow_id"]
            if not _validate_name(workflow_id):
                return web.json_response(
                    _make_response(error="ID de workflow invalido", status=400),
                    status=400,
                )
            limit = max(1, min(int(request.query.get("limit", "50")), 100))
            from core.quality_gate_workflows import QUALITY_GRAPH_IDS
            from core.workflow_engine import get_workflow_engine

            engine = get_workflow_engine()
            workflow = engine.get_workflow(workflow_id)
            if workflow is None or workflow.get("graph_name") not in QUALITY_GRAPH_IDS:
                return web.json_response(
                    _make_response(error="Workflow no encontrado", status=404),
                    status=404,
                )
            events = engine.get_workflow_events(workflow_id, limit)
            return web.json_response(_make_response(data=events))
        except ValueError as e:
            return web.json_response(
                _make_response(error=str(e), status=400),
                status=400,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_workflow_resume(self, request: web.Request) -> web.Response:
        """POST /v1/workflows/{workflow_id}/resume - Reanuda workflow pausado."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            workflow_id = request.match_info["workflow_id"]
            if not _validate_name(workflow_id):
                return web.json_response(
                    _make_response(error="ID de workflow invalido", status=400),
                    status=400,
                )
            body = await request.json()
            idempotency_key = body.get("idempotency_key")
            decision = body.get("decision")
            if not isinstance(idempotency_key, str) or not _validate_name(idempotency_key):
                return web.json_response(
                    _make_response(error="Idempotency key inválido", status=400),
                    status=400,
                )
            if decision not in ("approve", "reject"):
                return web.json_response(
                    _make_response(error="Decisión de workflow inválida", status=400),
                    status=400,
                )
            from core.quality_gate_workflows import QUALITY_GRAPH_IDS
            from core.workflow_engine import WorkflowStatus, get_workflow_engine

            engine = get_workflow_engine()
            workflow = engine.get_workflow(workflow_id)
            if workflow is None or workflow.get("graph_name") not in QUALITY_GRAPH_IDS:
                return web.json_response(
                    _make_response(error="Workflow no encontrado", status=404),
                    status=404,
                )
            if workflow.get("status") != WorkflowStatus.PAUSED.value:
                replay = dict(workflow)
                replay["replayed"] = True
                return web.json_response(_make_response(data=replay))
            result = await engine.resume(workflow_id, {"decision": decision})
            return web.json_response(_make_response(data=result))
        except ValueError as e:
            return web.json_response(
                _make_response(error=str(e), status=400),
                status=400,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_workflow_cancel(self, request: web.Request) -> web.Response:
        """POST /v1/workflows/{workflow_id}/cancel - Cancela un workflow."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            workflow_id = request.match_info["workflow_id"]
            if not _validate_name(workflow_id):
                return web.json_response(
                    _make_response(error="ID de workflow invalido", status=400),
                    status=400,
                )
            body = await request.json()
            idempotency_key = body.get("idempotency_key")
            if not isinstance(idempotency_key, str) or not _validate_name(idempotency_key):
                return web.json_response(
                    _make_response(error="Idempotency key inválido", status=400),
                    status=400,
                )
            from core.quality_gate_workflows import QUALITY_GRAPH_IDS
            from core.workflow_engine import get_workflow_engine

            engine = get_workflow_engine()
            workflow = engine.get_workflow(workflow_id)
            if workflow is None or workflow.get("graph_name") not in QUALITY_GRAPH_IDS:
                return web.json_response(
                    _make_response(error="Workflow no encontrado", status=404),
                    status=404,
                )
            ok = engine.cancel_workflow(workflow_id)
            if not ok:
                return web.json_response(
                    _make_response(error="No se pudo cancelar", status=400),
                    status=400,
                )
            return web.json_response(_make_response(data=engine.get_workflow(workflow_id)))
        except ValueError as e:
            return web.json_response(
                _make_response(error=str(e), status=400),
                status=400,
            )
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_workflow_stats(self, request: web.Request) -> web.Response:
        """GET /v1/workflows/stats - Estadísticas del WorkflowEngine."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            from core.workflow_engine import get_workflow_engine

            stats = get_workflow_engine().get_stats()
            return web.json_response(_make_response(data=stats))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    # --------------------------------------------------------
    # SelfImprovement Endpoints (Sprint 3)
    # --------------------------------------------------------
    async def handle_improvement_proposals(self, request: web.Request) -> web.Response:
        """GET /v1/improvement/proposals - Genera y retorna propuestas de mejora."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            proposals = await daemon.get_improvement_proposals()
            return web.json_response(_make_response(data=proposals))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_improvement_apply(self, request: web.Request) -> web.Response:
        """POST /v1/improvement/proposals/{proposal_id} - Aplica o rechaza propuesta."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            proposal_id = request.match_info["proposal_id"]
            if not _validate_name(proposal_id):
                return web.json_response(
                    _make_response(error="ID de propuesta invalido", status=400),
                    status=400,
                )
            body = await request.json()
            approved = body.get("approved", False)
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            ok = await daemon.apply_improvement(proposal_id, approved)
            return web.json_response(_make_response(data={"applied": ok}))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_improvement_report(self, request: web.Request) -> web.Response:
        """GET /v1/improvement/report - Reporte de mejoras."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            report = await daemon.get_improvement_report()
            return web.json_response(_make_response(data=report))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_improvement_health(self, request: web.Request) -> web.Response:
        """GET /v1/improvement/health - Salud del ecosistema."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            health = await daemon.get_ecosystem_health()
            return web.json_response(_make_response(data=health))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_ecosystem_health(self, request: web.Request) -> web.Response:
        """GET /v1/ecosystem/health - Alias de salud global del ecosistema."""
        return await self.handle_improvement_health(request)

    async def handle_improvement_analyze(self, request: web.Request) -> web.Response:
        """GET /v1/improvement/analyze/{agent} - Analiza prompt de un agente."""
        from .._gateway_main import _make_response, _sanitize_error, _validate_name

        try:
            agent = request.match_info["agent"]
            if not _validate_name(agent):
                return web.json_response(
                    _make_response(error="Nombre de agente invalido", status=400),
                    status=400,
                )
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            analysis = await daemon.analyze_agent_prompt(agent)
            return web.json_response(_make_response(data=analysis))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )

    async def handle_improvement_auto_apply(self, request: web.Request) -> web.Response:
        """POST /v1/improvement/auto-apply - Auto-aplica mejoras seguras."""
        from .._gateway_main import _make_response, _sanitize_error

        try:
            from core.agent_daemon import get_daemon

            daemon = await get_daemon(lite=True)
            applied = await daemon.auto_apply_improvements()
            return web.json_response(_make_response(data={"applied": applied}))
        except Exception as e:
            return web.json_response(
                _make_response(error=_sanitize_error(e), status=500),
                status=500,
            )
