"""
Type-safe configuration models for OpenAntigravity ecosystem.

Provides Pydantic v2 models for environment, MCP, and Antigravity configs.
"""

from typing import Any, Literal
from enum import Enum
from pydantic import BaseModel, Field, validator, AnyUrl
from pathlib import Path


# ============================================================================
# Environment Configuration Models
# ============================================================================


class TelegramConfig(BaseModel):
    """Telegram bot configuration."""

    bot_token: str = Field(..., description="Telegram bot token from BotFather")
    allowed_user_ids: list[int] = Field(
        default_factory=list, description="Comma-separated list of allowed Telegram user IDs"
    )

    class Config:
        extra = "forbid"
        validate_assignment = True


class ServerConfig(BaseModel):
    """Server configuration."""

    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8080, description="Server port")
    node_env: Literal["development", "production", "test"] = Field(
        default="production", description="Node environment"
    )
    log_level: Literal["debug", "info", "warn", "error"] = Field(
        default="info", description="Logging level"
    )
    debug: bool = Field(default=False, description="Debug mode enabled")

    class Config:
        extra = "forbid"
        validate_assignment = True


class MCPGatewayConfig(BaseModel):
    """MCP Gateway configuration."""

    gateway_url: str = Field(default="http://gateway:4747", description="MCP gateway URL")
    gateway_timeout_ms: int = Field(default=30000, description="Gateway timeout in milliseconds")
    skill_timeout_ms: int = Field(
        default=30000, description="Skill execution timeout in milliseconds"
    )
    api_key: str | None = Field(
        default=None, description="Shared API key for gateway authentication (Docker)"
    )

    class Config:
        extra = "forbid"
        validate_assignment = True


class FileUploadConfig(BaseModel):
    """File upload configuration."""

    database_path: str = Field(default="/app/data/bot.db", description="Database file path")
    temp_files_dir: str = Field(default="/app/tmp", description="Temporary files directory")
    max_file_size_mb: int = Field(default=50, ge=1, le=5000, description="Maximum file size in MB")
    max_file_count_per_session: int = Field(
        default=10, ge=1, le=1000, description="Maximum files per session"
    )

    class Config:
        extra = "forbid"
        validate_assignment = True


class RateLimitConfig(BaseModel):
    """Rate limiting configuration."""

    requests: int = Field(default=100, ge=1, description="Request limit")
    window_ms: int = Field(default=60000, ge=1000, description="Time window in ms")

    class Config:
        extra = "forbid"
        validate_assignment = True


class CacheConfig(BaseModel):
    """Cache configuration."""

    size_mb: int = Field(default=256, ge=1, description="Cache size in MB")
    ttl_minutes: int = Field(default=30, ge=1, description="TTL in minutes")
    redis_url: str | None = Field(
        default="redis://redis:6379/0", description="Redis URL (optional)"
    )

    class Config:
        extra = "forbid"
        validate_assignment = True


class DatabaseConfig(BaseModel):
    """PostgreSQL database configuration."""

    host: str = Field(default="postgres", description="Database host")
    port: int = Field(default=5432, ge=1, le=65535, description="Database port")
    name: str = Field(default="antigravity", description="Database name")
    user: str = Field(default="antigravity", description="Database user")
    password: str = Field(default="changeme", description="Database password")
    url: str | None = Field(
        default=None, description="Full database URL (overrides host/port/user/password)"
    )

    class Config:
        extra = "forbid"
        validate_assignment = True


class SecurityConfig(BaseModel):
    """Security configuration."""

    cors_origins: str = Field(
        default="https://yourdomain.com", description="Comma-separated CORS origins"
    )
    jwt_secret: str = Field(
        default="your_jwt_secret_here_change_in_production", description="JWT signing secret"
    )
    api_key_hash: str | None = Field(default=None, description="Hash of API key")

    class Config:
        extra = "forbid"
        validate_assignment = True


class FeatureFlagsConfig(BaseModel):
    """Feature flags configuration."""

    redis: bool = Field(default=True, description="Enable Redis")
    postgres: bool = Field(default=False, description="Enable PostgreSQL")
    monitoring: bool = Field(default=True, description="Enable monitoring")
    file_uploads: bool = Field(default=True, description="Enable file uploads")
    shu_llm_suggestions: bool = Field(
        default=False, description="Enable /shu LLM contextual suggestions"
    )

    class Config:
        extra = "forbid"
        validate_assignment = True


class ObservabilityConfig(BaseModel):
    """Monitoring and observability configuration."""

    sentry_dsn: str | None = Field(default=None, description="Sentry DSN")
    datadog_api_key: str | None = Field(default=None, description="Datadog API key")
    new_relic_license_key: str | None = Field(default=None, description="New Relic license key")

    class Config:
        extra = "forbid"
        validate_assignment = True


class ExternalAPIsConfig(BaseModel):
    """External API keys configuration."""

    openai_api_key: str | None = Field(default=None, description="OpenAI API key")
    anthropic_api_key: str | None = Field(default=None, description="Anthropic API key")
    groq_api_key: str | None = Field(default=None, description="Groq API key")
    pinecone_api_key: str | None = Field(default=None, description="Pinecone API key")
    minimax_api_key: str | None = Field(default=None, description="MiniMax API key")
    zai_api_key: str | None = Field(default=None, description="Z.AI API key")
    nvidia_api_key: str | None = Field(default=None, description="NVIDIA API key")
    openrouter_api_key: str | None = Field(default=None, description="OpenRouter API key")
    opencode_api_key: str | None = Field(default=None, description="OpenCode API key")
    magic_21st_api_key: str | None = Field(default=None, description="21st.dev Magic API key")
    stitch_api_key: str | None = Field(default=None, description="Google Stitch API key")

    class Config:
        extra = "forbid"
        validate_assignment = True


class LLMConfig(BaseModel):
    """Large Language Model configuration."""

    gateway_url: str = Field(default="http://127.0.0.1:4747", description="Antigravity gateway URL")
    local_base_url: str | None = Field(
        default=None, description="Local LLM base URL (e.g., Ollama)"
    )
    local_api_key: str | None = Field(default=None, description="Local LLM API key")
    local_model: str = Field(default="llama3.2", description="Local LLM model name")
    fallback_chain: str = Field(
        default="openrouter,zai,groq", description="LLM provider fallback chain (comma-separated)"
    )
    tier_standard: str = Field(
        default="openrouter,zai,groq", description="Tier standard provider order"
    )
    timeout_ms: int = Field(default=45000, ge=1000, description="LLM call timeout in milliseconds")

    class Config:
        extra = "forbid"
        validate_assignment = True


class AgentConfig(BaseModel):
    """Agent execution configuration."""

    request_timeout_ms: int = Field(
        default=300000, ge=1000, description="Agent request timeout in milliseconds"
    )
    max_tool_chain: int = Field(
        default=8, ge=1, le=100, description="Maximum chained tool calls per step"
    )
    quota_poll: bool = Field(default=True, description="Force quota polling without failover")

    class Config:
        extra = "forbid"
        validate_assignment = True


class CodexConfig(BaseModel):
    """Codex accounts configuration (persistent profiles)."""

    accounts_dir: str = Field(
        default="C:/Users/kenji/.codex/accounts", description="Codex accounts directory"
    )
    active_account: str | None = Field(default="jpkken", description="Active Codex account")
    account_index_b64: str | None = Field(
        default=None, description="Base64-encoded account index JSON"
    )

    class Config:
        extra = "forbid"
        validate_assignment = True


class EnvConfig(BaseModel):
    """Complete environment configuration from .env."""

    telegram: TelegramConfig
    server: ServerConfig
    mcp_gateway: MCPGatewayConfig
    file_upload: FileUploadConfig
    rate_limit: RateLimitConfig
    cache: CacheConfig
    database: DatabaseConfig
    security: SecurityConfig
    feature_flags: FeatureFlagsConfig
    observability: ObservabilityConfig
    external_apis: ExternalAPIsConfig
    llm: LLMConfig
    agent: AgentConfig
    codex: CodexConfig
    timezone: str = Field(default="UTC", description="Timezone")
    locale: str = Field(default="en_US", description="Locale")

    class Config:
        extra = "forbid"
        validate_assignment = True

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.dict()


# ============================================================================
# MCP Configuration Models
# ============================================================================


class MCPServer(BaseModel):
    """MCP server configuration."""

    type: Literal["stdio", "http"] | None = Field(default="stdio", description="Server type")
    command: str | None = Field(None, description="Command to start server")
    url: str | None = Field(None, description="HTTP server URL")
    args: list[str] | None = Field(default_factory=list, description="Command arguments")
    env: dict[str, str] | None = Field(default_factory=dict, description="Environment variables")

    class Config:
        extra = "allow"  # Allow extra fields
        validate_assignment = True


class MCPConfig(BaseModel):
    """MCP server configuration."""

    version: str = Field(default="1.0.0", description="MCP spec version")
    servers: dict[str, MCPServer] | None = Field(None, description="Configured MCP servers")
    mcp_servers: dict[str, MCPServer] | None = Field(
        None, description="Configured MCP servers (alternative key)"
    )
    mcpServers: dict[str, MCPServer] | None = Field(
        None, description="Configured MCP servers (camelCase key)"
    )

    class Config:
        extra = "allow"  # Allow extra fields like comments
        validate_assignment = True

    def __init__(self, **data):
        """Initialize and normalize server keys."""
        # Normalize server keys from different formats
        if "mcpServers" in data and "servers" not in data:
            data["servers"] = data.pop("mcpServers")
        elif "mcp_servers" in data and "servers" not in data:
            data["servers"] = data.pop("mcp_servers")

        # Ensure servers is not None
        if "servers" not in data or data["servers"] is None:
            data["servers"] = {}

        super().__init__(**data)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.dict()


# ============================================================================
# Antigravity Configuration Models
# ============================================================================


class RegistryConfig(BaseModel):
    """Registry configuration."""

    mode: Literal["remote-cache", "local-only", "hybrid"] = Field(
        default="remote-cache", description="Registry resolution mode"
    )
    cache_ttl: int | None = Field(default=900, ge=60, description="Cache TTL in seconds")
    cache_ttl_camel: int | None = Field(None, description="Cache TTL in seconds (camelCase)")

    class Config:
        extra = "allow"  # Allow extra fields
        validate_assignment = True

    def __init__(self, **data):
        """Initialize and normalize camelCase fields."""
        if "cacheTtl" in data and "cache_ttl" not in data:
            data["cache_ttl"] = data.pop("cacheTtl")
        super().__init__(**data)


class OrchestratorConfig(BaseModel):
    """Orchestrator configuration."""

    mode: Literal["agent-teams-lite", "agent-teams-pro", "single-agent", "crew-ai"] = Field(
        default="agent-teams-lite", description="Orchestrator mode"
    )

    class Config:
        extra = "allow"  # Allow extra fields
        validate_assignment = True


class ResolutionPolicyConfig(BaseModel):
    """Resolution policy for skills, agents, and commands."""

    skills: list[str] | None = Field(
        default=["local-mcp", "remote-mcp"], description="Skill resolution order"
    )
    agents: list[str] | None = Field(
        default=["local-mcp", "remote-mcp"], description="Agent resolution order"
    )
    commands: list[str] | None = Field(
        default=["local-runtime", "remote-mcp"], description="Command resolution order"
    )

    class Config:
        extra = "allow"  # Allow extra fields
        validate_assignment = True


class AntigravityConfig(BaseModel):
    """Antigravity ecosystem configuration."""

    gateway: str = Field(default="http://localhost:4747", description="Gateway URL")
    ecosystem_root: str = Field(default="${ANTIGRAVITY_ROOT}", description="Ecosystem root path")
    source_root: str = Field(default="${ANTIGRAVITY_ROOT}", description="Source root path")
    version: str = Field(default="6.1.4", description="Ecosystem version")
    memory_backend: Literal["mem0", "local", "hybrid"] | None = Field(
        default="mem0", description="Memory backend type"
    )
    memory_backend_camel: Literal["mem0", "local", "hybrid"] | None = Field(
        None, description="Memory backend type (camelCase)"
    )
    registry: RegistryConfig | None = Field(default_factory=RegistryConfig)
    orchestrator: OrchestratorConfig | None = Field(default_factory=OrchestratorConfig)
    fallback_policy: list[str] | None = Field(
        default=["local-project", "local-cache", "remote-mcp"],
        description="Fallback resolution order",
    )
    fallback_policy_camel: list[str] | None = Field(
        None, description="Fallback resolution order (camelCase)"
    )
    mcp_servers: list[str] = Field(
        default_factory=list, description="Configured MCP servers (legacy, see .mcp.json)"
    )
    resolution_policy: ResolutionPolicyConfig | None = Field(default_factory=ResolutionPolicyConfig)
    docs: str | None = Field(default=None, description="Documentation URL")

    class Config:
        extra = "allow"  # Allow extra fields like comments
        validate_assignment = True
        # Populate by name to handle both snake_case and camelCase
        allow_population_by_field_name = True

    def __init__(self, **data):
        """Initialize and normalize camelCase fields."""
        # Normalize camelCase fields
        if "memoryBackend" in data and "memory_backend" not in data:
            data["memory_backend"] = data.pop("memoryBackend")

        if "fallbackPolicy" in data and "fallback_policy" not in data:
            data["fallback_policy"] = data.pop("fallbackPolicy")

        if "mcp_servers" not in data:
            data["mcp_servers"] = []

        if "registry" not in data:
            data["registry"] = {}

        if "orchestrator" not in data:
            data["orchestrator"] = {}

        if "resolution_policy" not in data:
            data["resolution_policy"] = {}

        super().__init__(**data)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return self.dict(exclude_none=True)
