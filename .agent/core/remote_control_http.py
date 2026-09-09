"""HTTP adapter for the scoped Nexus mobile control plane."""

from __future__ import annotations

import asyncio
from collections import deque
from collections.abc import Awaitable, Callable, MutableMapping
from datetime import UTC, datetime
import json
from pathlib import Path
import re
import time
from typing import Any, TypeAlias

from aiohttp import web

from .gateway_client import GatewayClient, GatewayClientError
from .remote_pairing import RemotePairingStore

GatewayPayload: TypeAlias = dict[str, Any] | list[Any] | None
GatewayReader: TypeAlias = Callable[[str], Awaitable[GatewayPayload]]
GatewayWriter: TypeAlias = Callable[
    [str, dict[str, Any], str],
    Awaitable[GatewayPayload],
]
AdminAuthorizer: TypeAlias = Callable[[dict[str, str]], bool]
AdminAvailability: TypeAlias = Callable[[], bool]
StoreProvider: TypeAlias = Callable[[], RemotePairingStore]
REMOTE_ACTIONS: dict[str, str] = {
    "provider.hotswap": "/v1/provider/hotswap",
}
_PROVIDER_ID = re.compile(r"^[a-z][a-z0-9_-]{1,63}$")


def _redact_control_payload(value: Any) -> Any:
    """Remove credentials and local paths before remote delivery."""

    if isinstance(value, dict):
        safe: dict[str, Any] = {}
        for key, item in value.items():
            normalized = str(key).lower()
            if (
                normalized in {"antigravity_root", "root", "path", "headers"}
                or "api_key" in normalized
                or "credential" in normalized
                or "secret" in normalized
                or normalized.endswith("_token")
                or normalized.endswith("_path")
            ):
                continue
            safe[str(key)] = _redact_control_payload(item)
        return safe
    if isinstance(value, list):
        return [_redact_control_payload(item) for item in value]
    return value


async def gateway_data(path: str) -> GatewayPayload:
    """Read an authenticated loopback endpoint without exposing its key."""

    try:
        payload: Any = await asyncio.to_thread(GatewayClient(timeout=3).get, path)
    except (GatewayClientError, TypeError, ValueError):
        return None
    if not isinstance(payload, (dict, list)):
        return None
    if isinstance(payload, dict) and isinstance(payload.get("data"), (dict, list)):
        payload = payload["data"]
    return _redact_control_payload(payload)


async def gateway_action(
    path: str,
    payload: dict[str, Any],
    idempotency_key: str,
) -> GatewayPayload:
    """Execute one allowlisted gateway mutation with the encrypted loopback key."""

    try:
        result: Any = await asyncio.to_thread(
            GatewayClient(timeout=8).post,
            path,
            payload,
            idempotency_key=idempotency_key,
        )
    except (GatewayClientError, TypeError, ValueError):
        return None
    if not isinstance(result, (dict, list)):
        return None
    if isinstance(result, dict) and isinstance(result.get("data"), (dict, list)):
        result = result["data"]
    return _redact_control_payload(result)


def _normalize_action_payload(action: str, payload: dict[str, Any]) -> dict[str, Any]:
    normalized_action = action.strip().lower()
    if normalized_action != "provider.hotswap" or normalized_action not in REMOTE_ACTIONS:
        raise ValueError("Unsupported remote action")
    if set(payload) - {"provider", "model"}:
        raise ValueError("Unexpected provider switch fields")
    provider = str(payload.get("provider") or "").strip().lower()
    if not _PROVIDER_ID.fullmatch(provider):
        raise ValueError("Invalid provider")
    normalized: dict[str, Any] = {"provider": provider}
    model = payload.get("model")
    if model is not None:
        model_id = str(model).strip()
        if (
            not model_id
            or len(model_id) > 160
            or any(ord(character) < 32 for character in model_id)
        ):
            raise ValueError("Invalid model")
        normalized["model"] = model_id
    return normalized


class RemoteControlHttp:
    """Thin aiohttp adapter around the isolated pairing and approval store."""

    def __init__(
        self,
        *,
        base_dir: Path,
        admin_enabled: AdminAvailability,
        admin_auth: AdminAuthorizer,
        store: StoreProvider,
        sessions: MutableMapping[str, dict[str, Any]],
        activity: deque[dict[str, Any]],
        gateway_reader: GatewayReader = gateway_data,
        gateway_writer: GatewayWriter = gateway_action,
    ) -> None:
        self._base_dir = base_dir
        self._admin_enabled = admin_enabled
        self._admin_auth = admin_auth
        self._store_provider = store
        self._sessions = sessions
        self._activity = activity
        self._gateway_reader = gateway_reader
        self._gateway_writer = gateway_writer
        self._pairing_start_attempts: dict[str, deque[float]] = {}

    @staticmethod
    async def _json_body(request: web.Request) -> dict[str, Any] | None:
        try:
            body = await request.json()
        except (json.JSONDecodeError, ValueError):
            return None
        return body if isinstance(body, dict) else None

    @staticmethod
    def _bearer_token(request: web.Request) -> str:
        authorization = request.headers.get("Authorization", "")
        return authorization[7:] if authorization.startswith("Bearer ") else ""

    def _pairing_start_allowed(self, client: str) -> bool:
        """Limit starts even when the general MCP rate limiter is disabled."""

        now = time.monotonic()
        attempts = self._pairing_start_attempts.setdefault(client, deque())
        while attempts and now - attempts[0] > 600:
            attempts.popleft()
        if len(attempts) >= 5:
            return False
        attempts.append(now)
        return True

    def _authorized_admin(self, request: web.Request) -> bool:
        return self._admin_enabled() and self._admin_auth(dict(request.headers))

    def _store(self) -> RemotePairingStore:
        return self._store_provider()

    async def pairing_start(self, request: web.Request) -> web.Response:
        """Start one PKCE pairing request; Nexus approves it locally."""

        if not self._admin_enabled():
            return web.json_response(
                {"error": "Remote control requires an administrator token"},
                status=503,
            )
        if not self._pairing_start_allowed(request.remote or "unknown"):
            return web.json_response(
                {"error": "Too many pairing attempts"},
                status=429,
                headers={"Retry-After": "600"},
            )
        body = await self._json_body(request)
        if body is None:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        try:
            started = self._store().start_pairing(
                device_name=str(body.get("device_name") or ""),
                code_challenge=str(body.get("code_challenge") or ""),
                requested_scopes=body.get("requested_scopes"),
            )
        except (TypeError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        return web.json_response(started.model_dump(mode="json"), status=201)

    async def pairing_status(self, request: web.Request) -> web.Response:
        pairing = self._store().pairing_status(
            request.match_info["pairing_id"],
            request.headers.get("X-Pairing-Secret", ""),
        )
        if pairing is None:
            return web.json_response({"error": "Pairing not found"}, status=404)
        return web.json_response(pairing.model_dump(mode="json"))

    async def pairing_exchange(self, request: web.Request) -> web.Response:
        body = await self._json_body(request)
        if body is None:
            return web.json_response({"error": "Invalid JSON"}, status=400)
        grant = self._store().exchange(
            pairing_id=request.match_info["pairing_id"],
            pairing_secret=request.headers.get("X-Pairing-Secret", ""),
            code_verifier=str(body.get("code_verifier") or ""),
        )
        if grant is None:
            return web.json_response(
                {"error": "Pairing cannot be exchanged"},
                status=403,
            )
        return web.json_response(grant.model_dump(mode="json"))

    async def admin_pairings(self, request: web.Request) -> web.Response:
        if not self._authorized_admin(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        pairings = self._store().list_pairings(status=request.query.get("status", "pending"))
        return web.json_response(
            {
                "pairings": [pairing.model_dump(mode="json") for pairing in pairings],
                "count": len(pairings),
            }
        )

    async def admin_pairing_decision(self, request: web.Request) -> web.Response:
        if not self._authorized_admin(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        body = await self._json_body(request)
        if body is None or not isinstance(body.get("approved"), bool):
            return web.json_response(
                {"error": "'approved' must be boolean"},
                status=400,
            )
        current = self._store().pairing_status_by_admin(request.match_info["pairing_id"])
        scopes = body.get("scopes")
        if body["approved"] and scopes is None and current is not None:
            scopes = current.requested_scopes
        try:
            pairing = self._store().decide_pairing(
                request.match_info["pairing_id"],
                approved=body["approved"],
                scopes=scopes,
            )
        except (TypeError, ValueError) as exc:
            return web.json_response({"error": str(exc)}, status=400)
        if pairing is None:
            return web.json_response(
                {"error": "Pending pairing not found"},
                status=404,
            )
        return web.json_response(pairing.model_dump(mode="json"))

    async def admin_sessions(self, request: web.Request) -> web.Response:
        if not self._authorized_admin(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        sessions = self._store().list_access_tokens()
        return web.json_response(
            {
                "sessions": [session.model_dump(mode="json") for session in sessions],
                "count": len(sessions),
            }
        )

    async def admin_session_revoke(self, request: web.Request) -> web.Response:
        if not self._authorized_admin(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        revoked = self._store().revoke_access_token(request.match_info["token_id"])
        if not revoked:
            return web.json_response({"error": "Session not found"}, status=404)
        return web.json_response({"revoked": True})

    async def action_approval_request(self, request: web.Request) -> web.Response:
        body = await self._json_body(request)
        if body is None or not isinstance(body.get("payload"), dict):
            return web.json_response(
                {"error": "Invalid approval request"},
                status=400,
            )
        action = str(body.get("action") or "")
        try:
            payload = _normalize_action_payload(action, body["payload"])
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        approval = self._store().request_action_approval(
            access_token=self._bearer_token(request),
            action=action,
            payload=payload,
        )
        if approval is None:
            return web.json_response({"error": "Forbidden"}, status=403)
        return web.json_response(approval.model_dump(mode="json"), status=202)

    async def action_approval_status(self, request: web.Request) -> web.Response:
        approval = self._store().action_approval_status(
            access_token=self._bearer_token(request),
            approval_id=request.match_info["approval_id"],
        )
        if approval is None:
            return web.json_response({"error": "Approval not found"}, status=404)
        return web.json_response(approval.model_dump(mode="json"))

    async def action_execute(self, request: web.Request) -> web.Response:
        body = await self._json_body(request)
        if body is None or not isinstance(body.get("payload"), dict):
            return web.json_response({"error": "Invalid action request"}, status=400)
        approval_id = str(body.get("approval_id") or "")
        action = str(body.get("action") or "")
        try:
            payload = _normalize_action_payload(action, body["payload"])
        except ValueError as exc:
            return web.json_response({"error": str(exc)}, status=400)
        consumed = self._store().consume_action_approval(
            access_token=self._bearer_token(request),
            approval_id=approval_id,
            action=action,
            payload=payload,
        )
        if not consumed:
            return web.json_response(
                {"error": "Approval is not available for this action"},
                status=409,
            )
        result = await self._gateway_writer(
            REMOTE_ACTIONS[action.strip().lower()],
            payload,
            f"remote-{approval_id}",
        )
        if result is None:
            return web.json_response(
                {
                    "error": (
                        "Gateway action failed after consuming the one-time approval; "
                        "request a new approval to retry"
                    )
                },
                status=502,
            )
        return web.json_response(
            {
                "status": "executed",
                "approval_id": approval_id,
                "action": action.strip().lower(),
                "result": result,
            }
        )

    async def admin_approvals(self, request: web.Request) -> web.Response:
        if not self._authorized_admin(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        approvals = self._store().list_action_approvals(request.query.get("status", "pending"))
        return web.json_response(
            {
                "approvals": [approval.model_dump(mode="json") for approval in approvals],
                "count": len(approvals),
            }
        )

    async def admin_approval_decision(self, request: web.Request) -> web.Response:
        if not self._authorized_admin(request):
            return web.json_response({"error": "Unauthorized"}, status=401)
        body = await self._json_body(request)
        if body is None or not isinstance(body.get("approved"), bool):
            return web.json_response(
                {"error": "'approved' must be boolean"},
                status=400,
            )
        approval = self._store().decide_action_approval(
            request.match_info["approval_id"],
            approved=body["approved"],
        )
        if approval is None:
            return web.json_response(
                {"error": "Pending approval not found"},
                status=404,
            )
        return web.json_response(approval.model_dump(mode="json"))

    async def snapshot(self, request: web.Request) -> web.Response:
        """Return a scoped, redacted and approval-gated snapshot."""

        identity = self._store().authenticate(self._bearer_token(request))
        if identity is None:
            return web.json_response({"error": "Unauthorized"}, status=401)
        scopes = set(identity.scopes)
        gateway_requests = [
            self._gateway_reader("/v1/nexus/manifest")
            if "status:read" in scopes
            else asyncio.sleep(0, result=None),
            self._gateway_reader("/v1/provider/status")
            if "providers:read" in scopes
            else asyncio.sleep(0, result=None),
            self._gateway_reader("/v1/routing/status")
            if "routing:read" in scopes
            else asyncio.sleep(0, result=None),
        ]
        runtime, providers, routing = await asyncio.gather(*gateway_requests)
        sessions = []
        if "sessions:read" in scopes:
            sessions = [
                {
                    "id": session["id"],
                    "created_at": session["created_at"],
                    "last_active": session["last_active"],
                    "transport": "mcp",
                }
                for session in self._sessions.values()
            ]
        activity = list(reversed(self._activity))[:30] if "activity:read" in scopes else []
        return web.json_response(
            {
                "schema_version": "nexus-mobile-snapshot-v2",
                "generated_at": datetime.now(UTC).isoformat(),
                "mode": ("approval_gated" if "actions:request" in scopes else "read_only"),
                "device": {
                    "name": identity.device_name,
                    "scopes": identity.scopes,
                    "expires_at": identity.expires_at,
                },
                "runtime": runtime,
                "providers": providers,
                "routing": routing,
                "remote": {
                    "health": "ready",
                    "mcp_sessions": sessions,
                    "activity": activity,
                },
                "actions": {
                    "enabled": "actions:request" in scopes,
                    "approval_required": True,
                    "approval_ttl_seconds": 300,
                    "supported": sorted(REMOTE_ACTIONS),
                },
            }
        )

    def _control_dist_root(self) -> Path:
        return self._base_dir / "nexus-app" / "dist"

    async def ui(self, _request: web.Request) -> web.StreamResponse:
        index = self._control_dist_root() / "index.html"
        if not index.is_file():
            return web.json_response(
                {
                    "error": "Nexus web assets are not built",
                    "hint": "Run npm build in nexus-app",
                },
                status=503,
            )
        response = web.FileResponse(index)
        response.headers["Content-Security-Policy"] = (
            "default-src 'self'; script-src 'self'; "
            "style-src 'self' 'unsafe-inline'; font-src 'self' data:; "
            "img-src 'self' data:; connect-src 'self'"
        )
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    async def asset(self, request: web.Request) -> web.StreamResponse:
        assets_root = (self._control_dist_root() / "assets").resolve()
        requested = (assets_root / request.match_info["asset_path"]).resolve()
        if not requested.is_file() or not requested.is_relative_to(assets_root):
            return web.json_response({"error": "Asset not found"}, status=404)
        response = web.FileResponse(requested)
        response.headers["X-Content-Type-Options"] = "nosniff"
        return response

    def register(self, app: web.Application) -> None:
        """Register only the routes owned by the mobile control surface."""

        app.router.add_get("/control", self.ui)
        app.router.add_get("/control/", self.ui)
        app.router.add_get("/assets/{asset_path:.*}", self.asset)
        app.router.add_post("/control/api/pairings", self.pairing_start)
        app.router.add_get(
            "/control/api/pairings/{pairing_id}",
            self.pairing_status,
        )
        app.router.add_post(
            "/control/api/pairings/{pairing_id}/exchange",
            self.pairing_exchange,
        )
        app.router.add_get("/control/api/snapshot", self.snapshot)
        app.router.add_post(
            "/control/api/approvals",
            self.action_approval_request,
        )
        app.router.add_get(
            "/control/api/approvals/{approval_id}",
            self.action_approval_status,
        )
        app.router.add_post(
            "/control/api/actions",
            self.action_execute,
        )
        app.router.add_get(
            "/control/admin/pairings",
            self.admin_pairings,
        )
        app.router.add_post(
            "/control/admin/pairings/{pairing_id}/decision",
            self.admin_pairing_decision,
        )
        app.router.add_get(
            "/control/admin/sessions",
            self.admin_sessions,
        )
        app.router.add_delete(
            "/control/admin/sessions/{token_id}",
            self.admin_session_revoke,
        )
        app.router.add_get(
            "/control/admin/approvals",
            self.admin_approvals,
        )
        app.router.add_post(
            "/control/admin/approvals/{approval_id}/decision",
            self.admin_approval_decision,
        )
