"""Authenticated local HTTP API for versioned Markdown plan reviews."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiohttp import web

from core.plan_review_store import (
    ContentChanged,
    IdempotencyConflict,
    InvalidPlanPath,
    PlanReviewError,
    ReviewNotFound,
    RevisionConflict,
    get_plan_review_store,
)

from ._response import err, ok

logger = logging.getLogger(__name__)


class _PlanReviewMixin:
    """Review endpoints; decision never executes the reviewed plan."""

    async def handle_plan_review_list(self, request: web.Request) -> web.Response:
        workspace = request.query.get("workspace", "")
        return await self._plan_review_call(
            lambda: get_plan_review_store().list_reviews(workspace),
        )

    async def handle_plan_review_open(self, request: web.Request) -> web.Response:
        body = await self._json_object(request)
        if isinstance(body, web.Response):
            return body
        response = await self._plan_review_call(
            lambda: get_plan_review_store().open_review(
                str(body.get("workspace_id") or ""),
                str(body.get("relative_path") or ""),
            ),
        )
        if response.status < 300:
            await self._emit_plan_review_event("opened", response)
        return response

    async def handle_plan_review_annotation(self, request: web.Request) -> web.Response:
        body = await self._json_object(request)
        if isinstance(body, web.Response):
            return body
        review_id = request.match_info.get("review_id", "")
        response = await self._plan_review_call(
            lambda: get_plan_review_store().add_annotation(
                review_id,
                expected_revision=self._required_int(body, "revision"),
                idempotency_key=str(body.get("idempotency_key") or ""),
                start_line=self._required_int(body, "start_line"),
                end_line=self._required_int(body, "end_line"),
                body=str(body.get("body") or ""),
                actor=str(body.get("actor") or "local-user"),
            ),
        )
        if response.status < 300:
            await self._emit_plan_review_event("annotation_added", response)
        return response

    async def handle_plan_review_resolve_annotation(
        self,
        request: web.Request,
    ) -> web.Response:
        body = await self._json_object(request)
        if isinstance(body, web.Response):
            return body
        review_id = request.match_info.get("review_id", "")
        annotation_id = request.match_info.get("annotation_id", "")
        response = await self._plan_review_call(
            lambda: get_plan_review_store().resolve_annotation(
                review_id,
                annotation_id,
                expected_revision=self._required_int(body, "revision"),
                idempotency_key=str(body.get("idempotency_key") or ""),
                resolved=self._required_bool(body, "resolved"),
            ),
        )
        if response.status < 300:
            await self._emit_plan_review_event("annotation_resolved", response)
        return response

    async def handle_plan_review_decision(self, request: web.Request) -> web.Response:
        body = await self._json_object(request)
        if isinstance(body, web.Response):
            return body
        review_id = request.match_info.get("review_id", "")
        response = await self._plan_review_call(
            lambda: get_plan_review_store().decide(
                review_id,
                expected_revision=self._required_int(body, "revision"),
                idempotency_key=str(body.get("idempotency_key") or ""),
                decision=str(body.get("decision") or ""),
                actor=str(body.get("actor") or "local-user"),
                summary=str(body.get("summary") or ""),
            ),
        )
        if response.status < 300:
            await self._emit_plan_review_event("decision_recorded", response)
        return response

    async def _plan_review_call(
        self,
        operation: Callable[[], Any],
    ) -> web.Response:
        try:
            data = await asyncio.to_thread(operation)
            return web.json_response(ok(data=data, source="plan-review"))
        except (RevisionConflict, ContentChanged, IdempotencyConflict) as exc:
            return web.json_response(
                err("plan_review.conflict", str(exc), source="plan-review"),
                status=409,
            )
        except ReviewNotFound as exc:
            return web.json_response(
                err("plan_review.not_found", str(exc), source="plan-review"),
                status=404,
            )
        except (InvalidPlanPath, PlanReviewError, OSError) as exc:
            return web.json_response(
                err("plan_review.invalid", str(exc), source="plan-review"),
                status=400,
            )
        except Exception:
            logger.exception("Unexpected plan review failure")
            return web.json_response(
                err(
                    "plan_review.failed",
                    "No se pudo completar la operación de review",
                    source="plan-review",
                ),
                status=500,
            )

    @staticmethod
    async def _json_object(request: web.Request) -> dict[str, Any] | web.Response:
        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                err("plan_review.invalid_json", "JSON inválido", source="plan-review"),
                status=400,
            )
        if not isinstance(body, dict):
            return web.json_response(
                err(
                    "plan_review.invalid_json",
                    "El cuerpo debe ser un objeto JSON",
                    source="plan-review",
                ),
                status=400,
            )
        return body

    @staticmethod
    def _required_int(body: dict[str, Any], field: str) -> int:
        value = body.get(field)
        if not isinstance(value, int) or isinstance(value, bool):
            raise PlanReviewError(f"{field} debe ser entero")
        return value

    @staticmethod
    def _required_bool(body: dict[str, Any], field: str) -> bool:
        value = body.get(field)
        if not isinstance(value, bool):
            raise PlanReviewError(f"{field} debe ser booleano")
        return value

    async def _emit_plan_review_event(
        self,
        action: str,
        response: web.Response,
    ) -> None:
        """Emit only ids/status/revision; never document or annotation content."""
        try:
            envelope = response.body
            if not envelope:
                return
            import json

            decoded = json.loads(envelope)
            data = decoded.get("data") or {}
            event = {
                "action": action,
                "review_id": data.get("review_id", ""),
                "revision": data.get("revision", 0),
                "status": data.get("status", ""),
            }
            events = getattr(self, "events", None)
            emit: Callable[[str, dict[str, Any]], Awaitable[None]] | None = getattr(
                events,
                "emit",
                None,
            )
            if emit is not None:
                await emit("plan_review", event)
        except Exception:
            logger.debug("Plan review event could not be emitted", exc_info=True)
