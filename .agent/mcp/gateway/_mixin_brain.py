"""Mixin: handlers del Brain Network HTTP — query, stats, ingest via REST."""

from __future__ import annotations

import asyncio
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


def _validate_brain_ingest_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Valida y normaliza el payload de POST /v1/brain/ingest.

    Extraido de ``handle_brain_ingest`` para bajar su complejidad ciclomatica;
    la logica de validacion (limites de longitud, tipos, defaults) queda
    identica a la original, solo que ahora se centraliza en un ValueError.

    Args:
        payload: Diccionario JSON crudo recibido en el body del request.

    Returns:
        Diccionario con los campos normalizados: title, context, decisions,
        area, node_type, importance, tags.

    Raises:
        ValueError: si algun campo no cumple las restricciones de tipo/longitud.
    """
    title = str(payload.get("title", "")).strip()
    if not title or len(title) > 240:
        raise ValueError("'title' es requerido y debe tener maximo 240 caracteres")

    def bounded_text(name: str, maximum: int) -> str:
        value = payload.get(name, "")
        if value is None:
            return ""
        if not isinstance(value, str) or len(value) > maximum:
            raise ValueError(f"'{name}' debe ser texto de maximo {maximum} caracteres")
        return value

    context = bounded_text("context", 65_536)
    decisions = bounded_text("decisions", 65_536)
    area = bounded_text("area", 64).strip() or "general"
    node_type = bounded_text("node_type", 32).strip() or "session"
    importance = bounded_text("importance", 16).strip() or "normal"

    tags = payload.get("tags", [])
    if (
        not isinstance(tags, list)
        or len(tags) > 20
        or any(not isinstance(tag, str) or len(tag) > 64 for tag in tags)
    ):
        raise ValueError("'tags' debe ser una lista de hasta 20 textos de 64 caracteres")

    return {
        "title": title,
        "context": context,
        "decisions": decisions,
        "area": area,
        "node_type": node_type,
        "importance": importance,
        "tags": tags,
    }


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

    async def handle_brain_ingest(self, request: web.Request) -> web.Response:
        """POST /v1/brain/ingest — crea un nodo validado en Mother Brain."""
        from .._gateway_main import _make_response

        try:
            payload = await request.json()
        except Exception:
            return web.json_response(
                _make_response(error="Body JSON invalido", status=400),
                status=400,
            )
        if not isinstance(payload, dict):
            return web.json_response(
                _make_response(error="Body debe ser un objeto JSON", status=400),
                status=400,
            )

        try:
            fields = _validate_brain_ingest_payload(payload)
        except ValueError as exc:
            return web.json_response(
                _make_response(error=str(exc), status=400),
                status=400,
            )

        brain = self._get_brain()
        if brain is None:
            return web.json_response(
                _make_response(error="Brain Network no disponible", status=503),
                status=503,
            )

        try:
            node = await asyncio.to_thread(
                brain.ingest,
                fields["title"],
                context=fields["context"],
                decisions=fields["decisions"],
                area=fields["area"],
                tags=fields["tags"],
                node_type=fields["node_type"],
                importance=fields["importance"],
            )
        except ValueError as exc:
            return web.json_response(
                _make_response(error=str(exc), status=400),
                status=400,
            )
        except Exception as exc:
            log.exception("Brain ingest failed")
            return web.json_response(
                _make_response(error=f"Brain ingest failed: {exc}", status=500),
                status=500,
            )

        return web.json_response(_make_response(data=node.to_dict()), status=201)

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
                    "status": getattr(n, "status", "active"),
                    "version": getattr(n, "version", 1),
                    "topic_key": getattr(n, "topic_key", ""),
                    "superseded_by": getattr(n, "superseded_by", None),
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

    async def handle_brain_timeline(self, request: web.Request) -> web.Response:
        """GET /v1/brain/timeline?slug=<slug>|topic_key=<topic>&limit=<n>"""
        from .._gateway_main import _make_response

        slug = request.query.get("slug", "").strip()
        topic_key = request.query.get("topic_key", "").strip()
        if not slug and not topic_key:
            return web.json_response(
                _make_response(error="Parametro 'slug' o 'topic_key' es requerido", status=400),
                status=400,
            )
        try:
            limit = int(request.query.get("limit", "20"))
        except ValueError:
            limit = 0
        if not 1 <= limit <= 100:
            return web.json_response(
                _make_response(error="'limit' debe estar entre 1 y 100", status=400),
                status=400,
            )

        brain = self._get_brain()
        if brain is None:
            return web.json_response(
                _make_response(error="Brain Network no disponible", status=503),
                status=503,
            )
        try:
            items = brain.timeline(
                slug=slug or None,
                topic_key=topic_key or None,
                limit=limit,
            )
        except FileNotFoundError as exc:
            return web.json_response(
                _make_response(error=str(exc), status=404),
                status=404,
            )
        except ValueError as exc:
            return web.json_response(
                _make_response(error=str(exc), status=400),
                status=400,
            )
        return web.json_response(
            _make_response(
                data={
                    "topic_key": items[0]["topic_key"] if items else topic_key,
                    "count": len(items),
                    "items": items,
                }
            )
        )

    async def handle_brain_node_read(self, request: web.Request) -> web.Response:
        """GET /v1/brain/node/{slug}; único endpoint que entrega el cuerpo."""
        from .._gateway_main import _make_response

        brain = self._get_brain()
        if brain is None:
            return web.json_response(
                _make_response(error="Brain Network no disponible", status=503),
                status=503,
            )
        try:
            node = brain.get_node(request.match_info["slug"])
        except (FileNotFoundError, ValueError) as exc:
            return web.json_response(
                _make_response(error=str(exc), status=404),
                status=404,
            )
        return web.json_response(_make_response(data=node.to_dict()))

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
            # Llamar al metodo real del Brain en vez de reimplementar el conteo.
            # brain.stats() devuelve: app_id, brain_dir, total_nodes, by_type,
            # by_area, by_status, top_tags, total_connections — exactamente los
            # campos que el struct Rust BrainStats exige y el frontend espera.
            st = brain.stats()
            return web.json_response(_make_response(data=st))
        except Exception as e:
            log.exception("Brain stats failed")
            return web.json_response(
                _make_response(error=f"Brain stats failed: {e}", status=500),
                status=500,
            )
