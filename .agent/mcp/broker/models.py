"""Typed contracts shared by the MCP broker and Nexus."""

from __future__ import annotations

from enum import StrEnum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ConnectorStatus(StrEnum):
    """Lifecycle state shown consistently in Nexus and MCP responses."""

    CONFIGURED = "CONFIGURED"
    AUTHENTICATED = "AUTHENTICATED"
    HANDSHAKE = "HANDSHAKE"
    READY = "READY"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    UNVERIFIED = "UNVERIFIED"
    OFFLINE = "OFFLINE"
    ERROR = "ERROR"


class OperationClass(StrEnum):
    """Permission class for connector operations."""

    READ = "read"
    WRITE = "write"
    DESTRUCTIVE = "destructive"


class ConnectorAuth(BaseModel):
    """Secret requirements; values are never stored in the manifest."""

    model_config = ConfigDict(extra="forbid")

    required_env: list[str] = Field(default_factory=list)
    optional_env: list[str] = Field(default_factory=list)
    header_from_env: dict[str, str] = Field(default_factory=dict)


class ConnectorTransport(BaseModel):
    """How the lazy runtime reaches a connector."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["streamable_http", "stdio", "managed", "internal"]
    url: str | None = None
    command: str | None = None
    args: list[str] = Field(default_factory=list)
    cwd: str | None = None


class ConnectorScopes(BaseModel):
    """Declarative operation classification using exact names or glob patterns."""

    model_config = ConfigDict(extra="forbid")

    read: list[str] = Field(default_factory=lambda: ["list*", "get*", "read*", "search*"])
    write: list[str] = Field(default_factory=list)
    destructive: list[str] = Field(default_factory=list)


class ConnectorManifest(BaseModel):
    """A pinned, reviewable connector declaration."""

    model_config = ConfigDict(extra="forbid")

    id: str
    display_name: str
    owner: str
    source_url: str
    version: str
    checksum: str | None = None
    verification: Literal["verified", "unverified"] = "unverified"
    transport: ConnectorTransport
    auth: ConnectorAuth = Field(default_factory=ConnectorAuth)
    scopes: ConnectorScopes = Field(default_factory=ConnectorScopes)
    sandbox: Literal["restricted", "filesystem", "browser", "network", "payments"]
    description: str = ""


class ConnectorCatalogDocument(BaseModel):
    """On-disk registry schema."""

    model_config = ConfigDict(extra="forbid")

    schema_version: int
    generated_at: str
    connectors: list[ConnectorManifest]


class BrokerEnvelope(BaseModel):
    """Stable executable response shape for all six meta-tools."""

    model_config = ConfigDict(extra="forbid")

    trace_id: str
    status: str
    content: Any = None
    retryable: bool = False
    approval_id: str | None = None
    error: str | None = None


class ApprovalRecord(BaseModel):
    """Pending approval displayed and resolved by Nexus."""

    model_config = ConfigDict(extra="forbid")

    approval_id: str
    connector_id: str
    operation: str
    operation_class: OperationClass
    arguments_digest: str
    status: Literal["pending", "approved", "denied", "consumed"]
    created_at: str
    resolved_at: str | None = None
