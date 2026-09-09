"""
Configuration loader for OpenAntigravity ecosystem.

Loads and validates configurations from environment, .env files, and JSON schemas.
"""

import json
import logging
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel
from dotenv import dotenv_values

from .models import (
    EnvConfig,
    MCPConfig,
    AntigravityConfig,
    TelegramConfig,
    ServerConfig,
    MCPGatewayConfig,
    FileUploadConfig,
    RateLimitConfig,
    CacheConfig,
    DatabaseConfig,
    SecurityConfig,
    FeatureFlagsConfig,
    ObservabilityConfig,
    ExternalAPIsConfig,
    LLMConfig,
    AgentConfig,
    CodexConfig,
)

logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)


class ConfigLoader:
    """Load and validate configurations from various sources."""

    def __init__(self, root_path: Path | None = None):
        """Initialize the config loader.

        Args:
            root_path: Root path for relative file lookups. Defaults to current directory.
        """
        self.root_path = Path(root_path or Path.cwd())

    @staticmethod
    def _parse_comma_separated_list(value: str) -> list[str]:
        """Parse comma-separated string values into a list.

        Args:
            value: String value (comma-separated)

        Returns:
            List of stripped values
        """
        if not value:
            return []
        return [v.strip() for v in str(value).split(",") if v.strip()]

    @staticmethod
    def _parse_list_or_csv(value: str | None) -> list[str]:
        """Parse list-like or CSV string values.

        Args:
            value: String value (comma or semicolon separated)

        Returns:
            List of values
        """
        if not value:
            return []
        # Support both comma and semicolon separators
        separator = ";" if ";" in str(value) else ","
        return ConfigLoader._parse_comma_separated_list(str(value).replace(separator, ","))

    @classmethod
    def load_env_config(cls, env_path: Path | None = None) -> EnvConfig:
        """Load environment configuration from .env file.

        Args:
            env_path: Path to .env file. Defaults to .env in root directory.

        Returns:
            Validated EnvConfig object

        Raises:
            FileNotFoundError: If .env file not found
            ValueError: If configuration validation fails
        """
        if env_path is None:
            env_path = Path.cwd() / ".env"

        if not env_path.exists():
            raise FileNotFoundError(f".env file not found at {env_path}")

        # Load environment variables
        env_vars = dotenv_values(env_path)

        def env_value(name: str, default: str = "") -> str:
            """Return a normalized dotenv value, treating bare keys as absent."""
            return env_vars.get(name) or default

        # Parse comma-separated lists
        allowed_user_ids = cls._parse_comma_separated_list(env_value("TELEGRAM_ALLOWED_USER_IDS"))

        # Build config dict from environment
        config_dict = {
            "telegram": {
                "bot_token": env_value("TELEGRAM_BOT_TOKEN"),
                "allowed_user_ids": [int(uid) for uid in allowed_user_ids if uid],
            },
            "server": {
                "host": env_value("HOST", "0.0.0.0"),
                "port": int(env_value("PORT", "8080")),
                "node_env": env_value("NODE_ENV", "production"),
                "log_level": env_value("LOG_LEVEL", "info"),
                "debug": env_value("DEBUG", "false").lower() in ("true", "1", "yes"),
            },
            "mcp_gateway": {
                "gateway_url": env_value("MCP_GATEWAY_URL", "http://gateway:4747"),
                "gateway_timeout_ms": int(env_value("MCP_GATEWAY_TIMEOUT_MS", "30000")),
                "skill_timeout_ms": int(env_value("SKILL_TIMEOUT_MS", "30000")),
                "api_key": env_vars.get("ANTIGRAVITY_API_KEY"),
            },
            "file_upload": {
                "database_path": env_value("DATABASE_PATH", "/app/data/bot.db"),
                "temp_files_dir": env_value("TEMP_FILES_DIR", "/app/tmp"),
                "max_file_size_mb": int(env_value("MAX_FILE_SIZE_MB", "50")),
                "max_file_count_per_session": int(env_value("MAX_FILE_COUNT_PER_SESSION", "10")),
            },
            "rate_limit": {
                "requests": int(env_value("RATE_LIMIT_REQUESTS", "100")),
                "window_ms": int(env_value("RATE_LIMIT_WINDOW_MS", "60000")),
            },
            "cache": {
                "size_mb": int(env_value("CACHE_SIZE_MB", "256")),
                "ttl_minutes": int(env_value("CACHE_TTL_MINUTES", "30")),
                "redis_url": env_value("REDIS_URL", "redis://redis:6379/0"),
            },
            "database": {
                "host": env_value("DB_HOST", "postgres"),
                "port": int(env_value("DB_PORT", "5432")),
                "name": env_value("DB_NAME", "antigravity"),
                "user": env_value("DB_USER", "antigravity"),
                "password": env_value("DB_PASSWORD", "changeme"),
                "url": env_vars.get("DATABASE_URL"),
            },
            "security": {
                "cors_origins": env_value("CORS_ORIGINS", "https://yourdomain.com"),
                "jwt_secret": env_value("JWT_SECRET", "your_jwt_secret_here_change_in_production"),
                "api_key_hash": env_vars.get("API_KEY_HASH"),
            },
            "feature_flags": {
                "redis": env_value("FEATURE_REDIS", "true").lower() in ("true", "1", "yes"),
                "postgres": env_value("FEATURE_POSTGRES", "false").lower() in ("true", "1", "yes"),
                "monitoring": env_value("FEATURE_MONITORING", "true").lower()
                in ("true", "1", "yes"),
                "file_uploads": env_value("FEATURE_FILE_UPLOADS", "true").lower()
                in ("true", "1", "yes"),
                "shu_llm_suggestions": env_value("ANTIGRAVITY_SHU_LLM_SUGGESTIONS", "false").lower()
                in ("true", "1", "yes"),
            },
            "observability": {
                "sentry_dsn": env_vars.get("SENTRY_DSN"),
                "datadog_api_key": env_vars.get("DATADOG_API_KEY"),
                "new_relic_license_key": env_vars.get("NEW_RELIC_LICENSE_KEY"),
            },
            "external_apis": {
                "openai_api_key": env_vars.get("OPENAI_API_KEY"),
                "anthropic_api_key": env_vars.get("ANTHROPIC_API_KEY"),
                "groq_api_key": env_vars.get("GROQ_API_KEY"),
                "pinecone_api_key": env_vars.get("PINECONE_API_KEY"),
                "minimax_api_key": env_vars.get("MINIMAX_API_KEY"),
                "zai_api_key": env_vars.get("ZAI_API_KEY"),
                "nvidia_api_key": env_vars.get("NVIDIA_API_KEY"),
                "openrouter_api_key": env_vars.get("OPENROUTER_API_KEY"),
                "opencode_api_key": env_vars.get("OPENCODE_API_KEY"),
                "magic_21st_api_key": env_vars.get("MAGIC_21ST_API_KEY"),
                "stitch_api_key": env_vars.get("STITCH_API_KEY"),
            },
            "llm": {
                "gateway_url": env_value("ANTIGRAVITY_GATEWAY_URL", "http://127.0.0.1:4747"),
                "local_base_url": env_vars.get("LOCAL_LLM_BASE_URL"),
                "local_api_key": env_vars.get("LOCAL_LLM_API_KEY"),
                "local_model": env_value("LOCAL_LLM_MODEL", "llama3.2"),
                "fallback_chain": env_value("LLM_FALLBACK_CHAIN", "openrouter,zai,groq"),
                "tier_standard": env_value("LLM_TIER_STANDARD", "openrouter,zai,groq"),
                "timeout_ms": int(env_value("LLM_TIMEOUT_MS", "45000")),
            },
            "agent": {
                "request_timeout_ms": int(env_value("AGENT_REQUEST_TIMEOUT_MS", "300000")),
                "max_tool_chain": int(env_value("AGENT_MAX_TOOL_CHAIN", "8")),
                "quota_poll": env_value("ANTIGRAVITY_PROXY_QUOTA_POLL", "true").lower()
                in ("true", "1", "yes"),
            },
            "codex": {
                "accounts_dir": env_value("CODEX_ACCOUNTS_DIR", "C:/Users/kenji/.codex/accounts"),
                "active_account": env_vars.get("CODEX_ACTIVE_ACCOUNT"),
                "account_index_b64": env_vars.get("CODEX_ACCOUNT_INDEX_B64"),
            },
            "timezone": env_value("TZ", "UTC"),
            "locale": env_value("LOCALE", "en_US"),
        }

        return EnvConfig.model_validate(config_dict)

    @classmethod
    def load_mcp_config(cls, mcp_path: Path | None = None) -> MCPConfig:
        """Load MCP configuration from .mcp.json file.

        Args:
            mcp_path: Path to .mcp.json file. Defaults to .mcp.json in root directory.

        Returns:
            Validated MCPConfig object

        Raises:
            FileNotFoundError: If .mcp.json file not found
            json.JSONDecodeError: If JSON is invalid
            ValueError: If configuration validation fails
        """
        if mcp_path is None:
            mcp_path = Path.cwd() / ".mcp.json"

        if not mcp_path.exists():
            raise FileNotFoundError(f".mcp.json file not found at {mcp_path}")

        with open(mcp_path) as f:
            mcp_data = json.load(f)

        return MCPConfig(**mcp_data)

    @classmethod
    def load_antigravity_config(cls, config_path: Path | None = None) -> AntigravityConfig:
        """Load Antigravity configuration from config.json file.

        Args:
            config_path: Path to config.json. Defaults to .antigravity/config.json.

        Returns:
            Validated AntigravityConfig object

        Raises:
            FileNotFoundError: If config.json file not found
            json.JSONDecodeError: If JSON is invalid
            ValueError: If configuration validation fails
        """
        if config_path is None:
            config_path = Path.cwd() / ".antigravity" / "config.json"

        if not config_path.exists():
            raise FileNotFoundError(f"config.json file not found at {config_path}")

        with open(config_path) as f:
            config_data = json.load(f)

        return AntigravityConfig(**config_data)

    @classmethod
    def load_all_configs(cls) -> tuple[EnvConfig, MCPConfig, AntigravityConfig]:
        """Load all three configuration sources.

        Returns:
            Tuple of (EnvConfig, MCPConfig, AntigravityConfig)

        Raises:
            FileNotFoundError: If any required file not found
            json.JSONDecodeError: If any JSON is invalid
            ValueError: If any configuration validation fails
        """
        logger.info("Loading Antigravity ecosystem configurations...")

        try:
            env_config = cls.load_env_config()
            logger.info("✓ Environment configuration loaded")
        except Exception as e:
            logger.error(f"✗ Failed to load environment config: {e}")
            raise

        try:
            mcp_config = cls.load_mcp_config()
            logger.info("✓ MCP configuration loaded")
        except Exception as e:
            logger.error(f"✗ Failed to load MCP config: {e}")
            raise

        try:
            antigravity_config = cls.load_antigravity_config()
            logger.info("✓ Antigravity configuration loaded")
        except Exception as e:
            logger.error(f"✗ Failed to load Antigravity config: {e}")
            raise

        logger.info("All configurations loaded successfully")
        return env_config, mcp_config, antigravity_config

    @staticmethod
    def validate_config_schema(config_data: dict[str, Any], model: type[T]) -> T:
        """Validate configuration data against a Pydantic model.

        Args:
            config_data: Configuration dictionary
            model: Pydantic model class to validate against

        Returns:
            Validated model instance

        Raises:
            ValueError: If validation fails
        """
        try:
            return model.model_validate(config_data)
        except Exception as e:
            logger.error(f"Configuration validation failed: {e}")
            raise ValueError(f"Invalid configuration: {e}") from e

    @staticmethod
    def export_to_json(config: Any, output_path: Path) -> None:
        """Export configuration to JSON file.

        Args:
            config: Configuration object
            output_path: Path to write JSON file to

        Raises:
            IOError: If file write fails
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            if isinstance(config, BaseModel):
                json.dump(config.model_dump(), f, indent=2, default=str)
            else:
                json.dump(config, f, indent=2, default=str)
        logger.info(f"Configuration exported to {output_path}")

    @staticmethod
    def get_json_schema(model: type[T]) -> dict[str, Any]:
        """Get JSON schema for a Pydantic model.

        Args:
            model: Pydantic model class

        Returns:
            JSON schema dictionary
        """
        return model.model_json_schema()
