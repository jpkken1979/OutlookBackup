"""Mixin: handlers del Brain Network HTTP — query, stats, ingest via REST."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from aiohttp import web

log = logging.getLogger("antigravity-gateway")


def _lazy_brain() -> Any:
    """Import perezoso del Brain para no inflar el startup del gateway."""
    try:
        import sys

        from .._gateway_main import BASE_DIR  # type: ignore[attr-defined]

        # BASE_DIR es el repo root. El brain vive en .agent/brain/
        agent_dir = Path(BASE_DIR) / ".agent"
        brain_root = agent_dir / "brain"
        if str(agent_dir) not in sys.path:
            sys.path.insert(0, str(agent_dir))
        from core.brain import Brain  # type: ignore[import-not-found]

        return Brain(brain_root, app_id="nexus-mother")
    except Exception as e:
        log.warning("Brain no disponible: %s", e)
        return None


class _BrainMixin:
    """Endpoints HTTP del Brain Network.

    Los endpoints existentes son MCP-only (stdio). Estos permiten que
    apps externas (Nexus frontend, scripts, CLI) consulten el Brain sin
    pasar por el MCP protocol.
    """

    _brain_instance: Any = None

    def _get_brain(self) -> Any:
        """Lazy singleton del Brain."""
        if self._brain_instance is None:
            self._brain_instance = _lazy_brain()
        return self._brain_instance

    async def handle_brain_query(self, request: web.Request) -> web.Response:
        """GET /v1/brain/query?q=<pregunta>&limit=<n>"""
        from .._gateway_main import _make_response

        q = request.query.get("q", "").strip()
        if not q:
            return web.json_response(
                _make_response(error="Parametro 'q' es requerido", status=400),
                status=400,
            )

        try:
            limit = min(int(request.query.get("limit", "5")), 20)
        except ValueError:
            limit = 5

        brain = self._get_brain()
        if brain is None:
            return web.json_response(
                _make_response(error="Brain Network no disponible", status=503),
                status=503,
            )

        try:
            nodes = brain.query(q, limit=limit)
        except Exception as e:
            log.exception("Brain query failed")
            return web.json_response(
                _make_response(error=f"Brain query failed: {e}", status=500),
                status=500,
            )

        results = []
        for n in nodes:
            results.append(
                {
                    "slug": getattr(n, "slug", ""),
                    "title": getattr(n, "title", ""),
                    "type": getattr(n, "type", ""),
                    "area": getattr(n, "area", ""),
                    "tags": list(getattr(n, "tags", []) or [])[:8],
                    "related": list(getattr(n, "related", []) or [])[:5],
                    "importance": getattr(n, "importance", "normal"),
                    "date": getattr(n, "date", ""),
                }
            )

        return web.json_response(
            _make_response(
                data={
                    "query": q,
                    "count": len(results),
                    "results": results,
                }
            )
        )

    async def handle_brain_stats(self, request: web.Request) -> web.Response:  # noqa: ARG002
        """GET /v1/brain/stats"""
        from .._gateway_main import _make_response

        brain = self._get_brain()
        if brain is None:
            return web.json_response(
                _make_response(error="Brain Network no disponible", status=503),
                status=503,
            )

        try:
            sessions = list((brain.sessions_dir).glob("*.md"))
            concepts = list((brain.concepts_dir).glob("*.md"))
            total = len(sessions) + len(concepts)
            return web.json_response(
                _make_response(
                    data={
                        "total_nodes": total,
                        "sessions": len(sessions),
                        "concepts": len(concepts),
                        "app_id": getattr(brain, "app_id", "unknown"),
                    }
                )
            )
        except Exception as e:
            log.exception("Brain stats failed")
            return web.json_response(
                _make_response(error=f"Brain stats failed: {e}", status=500),
                status=500,
            )
