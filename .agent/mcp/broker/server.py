"""Official-SDK MCP broker with six stable meta-tools."""

from __future__ import annotations

import asyncio
import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any

from aiohttp import web
from mcp.server.fastmcp import Context, FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from pydantic import BaseModel, Field

from .aiohttp_transport import AiohttpMcpTransport
from .models import BrokerEnvelope, ConnectorStatus, OperationClass
from .registry import ConnectorRegistry
from .runtime import ConnectorRuntimeError, LazyConnectorRuntime
from .state import BrokerState

META_TOOL_NAMES = (
    "antigravity_search",
    "antigravity_describe",
    "antigravity_run_agent",
    "antigravity_run_skill",
    "antigravity_call",
    "antigravity_status",
)
_SECRET_PATTERNS = (
    re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/\-={}\[\]]{12,}"),
    re.compile(r"\b(?:sk|rk|pk)-(?:live|test|proj|ant)?[-_A-Za-z0-9]{12,}\b"),
    re.compile(r"\b(?:ghp|gho|ghu|ghs|github_pat)_[A-Za-z0-9_]{20,}\b"),
    re.compile(
        r"(?i)\b(?:api[_-]?key|access[_-]?token|refresh[_-]?token|client[_-]?secret)"
        r"\s*[:=]\s*[\"']?[^,\s\"']{8,}"
    ),
)
_WINDOWS_PATH = re.compile(r"[A-Za-z]:\\[^\"\r\n]+")
_UNIX_PATH = re.compile(r"(?<!:)\/(?:home|Users|usr|var|opt|tmp)\/[^\"\s]+")


class ApprovalDecision(BaseModel):
    """Schema shown by MCP clients that support elicitation."""

    approve: bool = Field(description="Approve this single connector operation")


def _json_safe(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _json_safe(to_dict())
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _safe_error_message(error: Exception) -> str:
    """Redact credentials and local paths before returning an MCP error."""

    message = str(error)
    for pattern in _SECRET_PATTERNS:
        message = pattern.sub("[redacted]", message)
    message = _WINDOWS_PATH.sub("[path]", message)
    message = _UNIX_PATH.sub("[path]", message)
    return message[:500] + ("..." if len(message) > 500 else "")


class AntigravityMcpBroker:
    """One MCP surface for agents, skills and lazy external connectors."""

    def __init__(self, gateway: Any, project_root: Path):
        self.gateway = gateway
        self.project_root = project_root.resolve()
        broker_dir = Path(__file__).resolve().parent
        self.registry = ConnectorRegistry(broker_dir / "connectors.json")
        self.state = BrokerState(self.project_root / ".antigravity" / "state" / "broker.db")
        self.runtime = LazyConnectorRuntime(self.registry, self.project_root)
        self.mcp = FastMCP(
            "OpenAntigravity Nexus",
            instructions=(
                "Universal broker for OpenAntigravity agents, skills and connectors. "
                "Search or describe capabilities before executing them."
            ),
            json_response=True,
            stateless_http=False,
            transport_security=TransportSecuritySettings(
                enable_dns_rebinding_protection=True,
                allowed_hosts=[
                    "127.0.0.1:*",
                    "localhost:*",
                    "[::1]:*",
                ],
                allowed_origins=[
                    "http://127.0.0.1:*",
                    "http://localhost:*",
                    "tauri://localhost",
                    "http://tauri.localhost",
                ],
            ),
        )
        self._register_meta_tools()
        self._register_resources()
        self._register_prompt()
        if os.environ.get("ANTIGRAVITY_MCP_LEGACY_TOOLS", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }:
            self._register_legacy_agent_tools()
        self._asgi_app = self.mcp.streamable_http_app()
        self.transport = AiohttpMcpTransport(self.mcp.session_manager)

    async def start(self) -> None:
        await self.transport.start()

    async def stop(self) -> None:
        await self.transport.stop()

    async def handle_http(self, request: web.Request) -> web.StreamResponse:
        return await self.transport.handle(request)

    async def call_tool_from_host(
        self,
        name: str,
        arguments: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Execute one public meta-tool for trusted first-party hosts such as Nexus."""

        if name not in META_TOOL_NAMES:
            raise ValueError(f"Unknown Antigravity meta-tool: {name}")
        result = await self.mcp.call_tool(name, arguments or {})
        if isinstance(result, dict):
            structured = result.get("structuredContent") or result.get("structured_content")
            if isinstance(structured, dict):
                return _json_safe(structured)
            content = result.get("content")
            if isinstance(content, list) and len(content) == 1:
                item = _json_safe(content[0])
                if isinstance(item, dict) and isinstance(item.get("text"), str):
                    try:
                        parsed = json.loads(item["text"])
                    except json.JSONDecodeError:
                        pass
                    else:
                        if isinstance(parsed, dict):
                            return parsed
            return _json_safe(result)

        safe_result = _json_safe(result)
        if isinstance(safe_result, list):
            for candidate in reversed(safe_result):
                if isinstance(candidate, dict) and isinstance(candidate.get("status"), str):
                    return candidate
            if len(safe_result) == 1:
                content = safe_result[0]
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    try:
                        parsed = json.loads(content["text"])
                    except json.JSONDecodeError:
                        pass
                    else:
                        if isinstance(parsed, dict):
                            return parsed
        return {"status": "OK", "content": safe_result}

    def _envelope(
        self,
        *,
        trace_id: str,
        status: str,
        content: Any = None,
        retryable: bool = False,
        approval_id: str | None = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        return BrokerEnvelope(
            trace_id=trace_id,
            status=status,
            content=_json_safe(content),
            retryable=retryable,
            approval_id=approval_id,
            error=error,
        ).model_dump(mode="json")

    async def _recorded(
        self,
        action: str,
        target: str | None,
        callback: Any,
    ) -> dict[str, Any]:
        trace_id = f"trc_{uuid.uuid4().hex}"
        started = time.perf_counter()
        try:
            result = await callback(trace_id)
        except Exception as exc:
            duration_ms = (time.perf_counter() - started) * 1000
            self.state.record_trace(
                trace_id=trace_id,
                action=action,
                target=target,
                status="ERROR",
                retryable=False,
                duration_ms=duration_ms,
                error_code=type(exc).__name__,
            )
            return self._envelope(
                trace_id=trace_id,
                status="ERROR",
                error=f"{type(exc).__name__}: {_safe_error_message(exc)}",
            )
        duration_ms = (time.perf_counter() - started) * 1000
        self.state.record_trace(
            trace_id=trace_id,
            action=action,
            target=target,
            status=result.get("status", "OK"),
            retryable=bool(result.get("retryable")),
            duration_ms=duration_ms,
            error_code=result.get("error_code"),
        )
        return self._envelope(
            trace_id=trace_id,
            status=result.get("status", "OK"),
            content=result.get("content"),
            retryable=bool(result.get("retryable")),
            approval_id=result.get("approval_id"),
            error=result.get("error"),
        )

    def _agents(self) -> list[dict[str, Any]]:
        agents = self.gateway._list_agents_from_filesystem()
        for agent in agents:
            identity = self.project_root / ".agent" / "agents" / agent["name"] / "IDENTITY.md"
            agent["description"] = self._first_description(identity)
            agent["kind"] = "agent"
        return agents

    async def _skills(self) -> list[dict[str, Any]]:
        loop = asyncio.get_running_loop()
        skills = await loop.run_in_executor(
            self.gateway._thread_pool,
            lambda: self.gateway._scan_skills(include_external=True),
        )
        return [{**skill, "kind": "skill"} for skill in skills]

    @staticmethod
    def _first_description(markdown_path: Path) -> str:
        if not markdown_path.exists():
            return ""
        try:
            for line in markdown_path.read_text(encoding="utf-8", errors="replace").splitlines():
                stripped = line.strip()
                if stripped and not stripped.startswith(("#", "---", "name:", "description:")):
                    return stripped[:500]
        except OSError:
            return ""
        return ""

    def _register_meta_tools(self) -> None:
        @self.mcp.tool(
            name="antigravity_search",
            description="Search agents, skills and connectors without loading them.",
            structured_output=True,
        )
        async def antigravity_search(
            query: str,
            kinds: list[str] | None = None,
            limit: int = 20,
        ) -> dict[str, Any]:
            requested_kinds = {kind.lower() for kind in (kinds or ["agent", "skill", "connector"])}

            async def execute(trace_id: str) -> dict[str, Any]:
                del trace_id
                normalized = query.strip().lower()
                candidates: list[dict[str, Any]] = []
                if "agent" in requested_kinds:
                    candidates.extend(self._agents())
                if "skill" in requested_kinds:
                    candidates.extend(await self._skills())
                if "connector" in requested_kinds:
                    candidates.extend(
                        {
                            **connector,
                            "name": connector["id"],
                            "kind": "connector",
                        }
                        for connector in self.registry.safe_catalog()
                    )

                def score(item: dict[str, Any]) -> tuple[int, str]:
                    name = str(item.get("name", "")).lower()
                    description = str(item.get("description", "")).lower()
                    if not normalized:
                        relevance = 1
                    elif name == normalized:
                        relevance = 100
                    elif name.startswith(normalized):
                        relevance = 70
                    elif normalized in name:
                        relevance = 50
                    elif normalized in description:
                        relevance = 20
                    else:
                        relevance = 0
                    return relevance, name

                ranked = [
                    (score(item), item)
                    for item in candidates
                    if not normalized or score(item)[0] > 0
                ]
                ranked.sort(key=lambda pair: (-pair[0][0], pair[0][1]))
                safe_limit = min(max(limit, 1), 100)
                results = [item for _, item in ranked[:safe_limit]]
                return {
                    "status": "OK",
                    "content": {
                        "query": query,
                        "total": len(ranked),
                        "results": results,
                    },
                }

            return await self._recorded("search", query, execute)

        @self.mcp.tool(
            name="antigravity_describe",
            description="Describe one agent, skill or connector before using it.",
            structured_output=True,
        )
        async def antigravity_describe(kind: str, name: str) -> dict[str, Any]:
            async def execute(trace_id: str) -> dict[str, Any]:
                del trace_id
                normalized_kind = kind.lower()
                if normalized_kind == "agent":
                    item = next((item for item in self._agents() if item["name"] == name), None)
                elif normalized_kind == "skill":
                    item = next(
                        (item for item in await self._skills() if item["name"] == name), None
                    )
                    if item:
                        skill_path = self._resolve_skill_path(name)
                        item = {
                            **item,
                            "content": (
                                skill_path.read_text(encoding="utf-8", errors="replace")
                                if skill_path
                                else ""
                            ),
                        }
                elif normalized_kind == "connector":
                    connector = self.registry.get(name)
                    item = None
                    if connector:
                        item = {
                            **connector.model_dump(mode="json"),
                            "status": self.registry.status(connector).value,
                            "missing_secrets": self.registry.required_secrets_missing(connector),
                        }
                        item["auth"].pop("header_from_env", None)
                else:
                    return {
                        "status": "ERROR",
                        "error": "kind must be agent, skill or connector",
                    }
                if item is None:
                    return {"status": "NOT_FOUND", "error": f"{kind} '{name}' was not found"}
                return {"status": "OK", "content": item}

            return await self._recorded("describe", f"{kind}:{name}", execute)

        @self.mcp.tool(
            name="antigravity_run_agent",
            description="Run an OpenAntigravity agent by name.",
            structured_output=True,
        )
        async def antigravity_run_agent(
            name: str,
            task: str,
            timeout_seconds: int = 120,
        ) -> dict[str, Any]:
            return await self._run_agent(name, task, timeout_seconds)

        @self.mcp.tool(
            name="antigravity_run_skill",
            description="Run a skill using project > user > bundle precedence.",
            structured_output=True,
        )
        async def antigravity_run_skill(
            name: str,
            input: str,
            timeout_seconds: int = 120,
        ) -> dict[str, Any]:
            return await self._run_skill(name, input, timeout_seconds)

        @self.mcp.tool(
            name="antigravity_call",
            description=(
                "Call a connector tool lazily. Reads run directly; writes and destructive "
                "operations require one-time approval."
            ),
            structured_output=True,
        )
        async def antigravity_call(
            connector: str,
            operation: str,
            arguments: dict[str, Any] | None = None,
            approval_id: str | None = None,
            ctx: Context | None = None,
        ) -> dict[str, Any]:
            safe_arguments = arguments or {}

            async def execute(trace_id: str) -> dict[str, Any]:
                del trace_id
                manifest = self.registry.get(connector)
                if manifest is None:
                    return {
                        "status": "NOT_FOUND",
                        "error": f"Connector '{connector}' was not found",
                    }
                operation_class = self.registry.classify_operation(
                    manifest,
                    operation,
                    safe_arguments,
                )
                if operation_class != OperationClass.READ:
                    approved = False
                    if approval_id:
                        approved = self.state.consume_approval(
                            approval_id,
                            connector,
                            operation,
                            safe_arguments,
                        )
                    if not approved:
                        approval = self.state.request_approval(
                            connector,
                            operation,
                            operation_class,
                            safe_arguments,
                        )
                        if ctx is not None and self._supports_elicitation(ctx):
                            decision = await ctx.elicit(
                                (
                                    f"Allow one {operation_class.value} operation "
                                    f"'{operation}' on connector '{connector}'?"
                                ),
                                ApprovalDecision,
                            )
                            if (
                                decision.action == "accept"
                                and decision.data is not None
                                and decision.data.approve
                            ):
                                self.state.resolve_approval(approval.approval_id, approved=True)
                                approved = self.state.consume_approval(
                                    approval.approval_id,
                                    connector,
                                    operation,
                                    safe_arguments,
                                )
                        if not approved:
                            return {
                                "status": "APPROVAL_REQUIRED",
                                "approval_id": approval.approval_id,
                                "content": {
                                    "connector": connector,
                                    "operation": operation,
                                    "operation_class": operation_class.value,
                                },
                            }
                try:
                    result = await self.runtime.call(manifest, operation, safe_arguments)
                except ConnectorRuntimeError as exc:
                    return {
                        "status": exc.status.value,
                        "retryable": exc.retryable,
                        "error": str(exc),
                    }
                if ctx is not None:
                    await ctx.session.send_tool_list_changed()
                    await ctx.session.send_resource_list_changed()
                return {"status": "OK", "content": result}

            return await self._recorded("connector.call", f"{connector}:{operation}", execute)

        @self.mcp.tool(
            name="antigravity_status",
            description="Return broker health or probe one lazy connector.",
            structured_output=True,
        )
        async def antigravity_status(
            connector: str | None = None,
            probe: bool = False,
            ctx: Context | None = None,
        ) -> dict[str, Any]:
            async def execute(trace_id: str) -> dict[str, Any]:
                del trace_id
                if connector:
                    manifest = self.registry.get(connector)
                    if manifest is None:
                        return {
                            "status": "NOT_FOUND",
                            "error": f"Connector '{connector}' was not found",
                        }
                    if probe:
                        try:
                            result = await self.runtime.probe(manifest)
                        except ConnectorRuntimeError as exc:
                            return {
                                "status": exc.status.value,
                                "retryable": exc.retryable,
                                "error": str(exc),
                            }
                        if ctx is not None:
                            await ctx.session.send_tool_list_changed()
                            await ctx.session.send_resource_list_changed()
                        return {"status": "OK", "content": result}
                    return {
                        "status": "OK",
                        "content": next(
                            item for item in self.registry.safe_catalog() if item["id"] == connector
                        ),
                    }
                statuses: dict[str, int] = {}
                catalog = self.registry.safe_catalog()
                for item in catalog:
                    statuses[item["status"]] = statuses.get(item["status"], 0) + 1
                return {
                    "status": "OK",
                    "content": {
                        "broker": "ready",
                        "protocol_version": "2025-11-25",
                        "meta_tools": list(META_TOOL_NAMES),
                        "tool_count": len(META_TOOL_NAMES),
                        "legacy_profile": os.environ.get("ANTIGRAVITY_MCP_LEGACY_TOOLS", "").lower()
                        in {"1", "true", "yes", "on"},
                        "connectors": {
                            "total": len(catalog),
                            "by_status": statuses,
                        },
                    },
                }

            return await self._recorded("status", connector, execute)

    def _register_resources(self) -> None:
        @self.mcp.resource(
            "antigravity://catalog",
            name="OpenAntigravity catalog",
            description="Agents, skills and connector metadata.",
            mime_type="application/json",
        )
        async def catalog_resource() -> str:
            return json.dumps(
                {
                    "agents": self._agents(),
                    "skills": await self._skills(),
                    "connectors": self.registry.safe_catalog(),
                },
                ensure_ascii=False,
            )

        @self.mcp.resource(
            "antigravity://skills/{name}",
            name="Skill instructions",
            mime_type="text/markdown",
        )
        def skill_resource(name: str) -> str:
            path = self._resolve_skill_path(name)
            if path is None:
                raise ValueError(f"Skill '{name}' was not found")
            return path.read_text(encoding="utf-8", errors="replace")

        @self.mcp.resource(
            "antigravity://agents/{name}",
            name="Agent identity",
            mime_type="text/markdown",
        )
        def agent_resource(name: str) -> str:
            agents_root = (self.project_root / ".agent" / "agents").resolve()
            path = (agents_root / name / "IDENTITY.md").resolve()
            if (
                not path.is_file()
                or not path.is_relative_to(agents_root)
                or path.parent.parent != agents_root
            ):
                raise ValueError(f"Agent '{name}' was not found")
            return path.read_text(encoding="utf-8", errors="replace")

        @self.mcp.resource(
            "antigravity://health",
            name="Broker health",
            mime_type="application/json",
        )
        def health_resource() -> str:
            return json.dumps(
                {
                    "status": "ready",
                    "protocol_version": "2025-11-25",
                    "tool_count": len(META_TOOL_NAMES),
                }
            )

        @self.mcp.resource(
            "antigravity://project-context",
            name="Project context",
            mime_type="application/json",
        )
        def project_context_resource() -> str:
            return json.dumps(
                {
                    "root": str(self.project_root),
                    "name": self.project_root.name,
                    "overlay_precedence": ["project", "user", "bundle"],
                },
                ensure_ascii=False,
            )

    def _register_prompt(self) -> None:
        @self.mcp.prompt(
            name="antigravity_task",
            description="Plan a task after discovering reusable Antigravity capabilities.",
        )
        def antigravity_task(task: str) -> str:
            return (
                "Search the OpenAntigravity catalog first. Describe the best matching "
                f"agent or skill, then execute it for this task:\n\n{task}"
            )

    def _register_legacy_agent_tools(self) -> None:
        for agent in self._agents():
            agent_name = agent["name"]

            async def legacy_agent_tool(
                task: str,
                timeout_seconds: int = 120,
                _agent_name: str = agent_name,
            ) -> dict[str, Any]:
                return await self._run_agent(_agent_name, task, timeout_seconds)

            self.mcp.tool(
                name=f"agent_{agent_name}",
                description=f"Legacy agent tool for {agent_name}.",
                structured_output=True,
            )(legacy_agent_tool)

    async def _run_agent(
        self,
        name: str,
        task: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        async def execute(trace_id: str) -> dict[str, Any]:
            del trace_id
            if name not in {agent["name"] for agent in self._agents()}:
                return {"status": "NOT_FOUND", "error": f"Agent '{name}' was not found"}
            timeout = min(max(timeout_seconds, 1), 600)
            executor = self.gateway.executor or await self.gateway.get_executor()
            if executor is None:
                return {
                    "status": "OFFLINE",
                    "retryable": True,
                    "error": "Agent executor is unavailable",
                }
            try:
                result = await asyncio.wait_for(
                    executor.execute_agent(name, task, timeout),
                    timeout=timeout + 5,
                )
            except TimeoutError:
                return {
                    "status": "TIMEOUT",
                    "retryable": True,
                    "error": f"Agent timed out after {timeout} seconds",
                }
            return {"status": "OK", "content": {"agent": name, "result": result}}

        return await self._recorded("agent.run", name, execute)

    async def _run_skill(
        self,
        name: str,
        user_input: str,
        timeout_seconds: int,
    ) -> dict[str, Any]:
        async def execute(trace_id: str) -> dict[str, Any]:
            del trace_id
            skill_path = self._resolve_skill_path(name)
            if skill_path is None:
                return {"status": "NOT_FOUND", "error": f"Skill '{name}' was not found"}
            timeout = min(max(timeout_seconds, 1), 600)
            executor = self.gateway.executor or await self.gateway.get_executor()
            if executor is None:
                return {
                    "status": "OFFLINE",
                    "retryable": True,
                    "error": "Skill executor is unavailable",
                }
            task = f"Use the skill '{name}' for: {user_input}"
            try:
                result = await asyncio.wait_for(
                    executor.execute_agent("super-orchestrator", task, timeout),
                    timeout=timeout + 5,
                )
            except TimeoutError:
                return {
                    "status": "TIMEOUT",
                    "retryable": True,
                    "error": f"Skill timed out after {timeout} seconds",
                }
            return {
                "status": "OK",
                "content": {
                    "skill": name,
                    "source": self._skill_source(skill_path),
                    "result": result,
                },
            }

        return await self._recorded("skill.run", name, execute)

    def _resolve_skill_path(self, name: str) -> Path | None:
        if not name or any(character in name for character in ("/", "\\", "..")):
            return None
        candidates = [
            self.project_root / ".agent" / "skills-custom" / name / "SKILL.md",
            self.project_root / ".agents" / "skills" / name / "SKILL.md",
            Path.home() / ".agents" / "skills" / name / "SKILL.md",
            Path.home() / ".codex" / "skills" / name / "SKILL.md",
            self.project_root / ".agent" / "skills" / name / "SKILL.md",
        ]
        return next((path for path in candidates if path.is_file()), None)

    def _skill_source(self, path: Path) -> str:
        if path.is_relative_to(self.project_root / ".agent" / "skills-custom"):
            return "project"
        if path.is_relative_to(self.project_root / ".agents" / "skills"):
            return "project"
        if path.is_relative_to(Path.home()):
            return "user"
        return "bundle"

    @staticmethod
    def _supports_elicitation(ctx: Context) -> bool:
        params = ctx.session.client_params
        if params is None:
            return False
        return getattr(params.capabilities, "elicitation", None) is not None

    def list_approvals(self, status: str = "pending") -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in self.state.list_approvals(status)]

    def resolve_approval(self, approval_id: str, approved: bool) -> dict[str, Any] | None:
        record = self.state.resolve_approval(approval_id, approved)
        return record.model_dump(mode="json") if record else None

    def list_traces(self, limit: int = 100) -> list[dict[str, Any]]:
        return self.state.list_traces(limit)
