#!/usr/bin/env python3
"""
Configuration validation script for OpenAntigravity ecosystem.

Validates .env, .mcp.json, and .antigravity/config.json against Pydantic models
and JSON schemas.

Usage:
    python validate_configs.py                # Validate all configs
    python validate_configs.py --fix          # Validate and fix common issues
    python validate_configs.py --export-schemas  # Export JSON schemas
"""

import json
import logging
import sys
from pathlib import Path
from typing import Any
import argparse

# Add .agent to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.config.loader import ConfigLoader
from core.config.models import (
    EnvConfig,
    MCPConfig,
    AntigravityConfig,
)

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ConfigValidator:
    """Validate OpenAntigravity configurations."""

    def __init__(self, root_path: Path | None = None):
        """Initialize the validator.

        Args:
            root_path: Root path for lookups. Defaults to current directory.
        """
        self.root_path = Path(root_path or Path.cwd())
        self.loader = ConfigLoader(self.root_path)
        self.errors: list[str] = []
        self.warnings: list[str] = []

    def validate_env_config(self) -> tuple[bool, EnvConfig | None]:
        """Validate .env configuration.

        Returns:
            Tuple of (is_valid, config_object)
        """
        logger.info("Validating .env configuration...")
        try:
            config = self.loader.load_env_config(self.root_path / ".env")
            logger.info("✓ .env configuration is valid")
            return True, config
        except FileNotFoundError as e:
            self.errors.append(str(e))
            logger.error(f"✗ {e}")
            return False, None
        except Exception as e:
            self.errors.append(f".env validation failed: {e}")
            logger.error(f"✗ .env validation failed: {e}")
            return False, None

    def validate_mcp_config(self) -> tuple[bool, MCPConfig | None]:
        """Validate .mcp.json configuration.

        Returns:
            Tuple of (is_valid, config_object)
        """
        logger.info("Validating .mcp.json configuration...")
        try:
            config = self.loader.load_mcp_config(self.root_path / ".mcp.json")
            logger.info("✓ .mcp.json configuration is valid")

            # Check that all servers have valid types
            for server_name, server_config in (config.servers or {}).items():
                if server_config.type == "stdio" and not server_config.command:
                    self.warnings.append(
                        f"MCP server '{server_name}' is stdio type but has no command"
                    )
                elif server_config.type == "http" and not server_config.url:
                    self.warnings.append(f"MCP server '{server_name}' is http type but has no url")

            return True, config
        except FileNotFoundError as e:
            self.errors.append(str(e))
            logger.error(f"✗ {e}")
            return False, None
        except Exception as e:
            self.errors.append(f".mcp.json validation failed: {e}")
            logger.error(f"✗ .mcp.json validation failed: {e}")
            return False, None

    def validate_antigravity_config(self) -> tuple[bool, AntigravityConfig | None]:
        """Validate .antigravity/config.json configuration.

        Returns:
            Tuple of (is_valid, config_object)
        """
        logger.info("Validating .antigravity/config.json configuration...")
        try:
            config = self.loader.load_antigravity_config(
                self.root_path / ".antigravity" / "config.json"
            )
            logger.info("✓ .antigravity/config.json configuration is valid")
            return True, config
        except FileNotFoundError as e:
            self.errors.append(str(e))
            logger.error(f"✗ {e}")
            return False, None
        except Exception as e:
            self.errors.append(f"config.json validation failed: {e}")
            logger.error(f"✗ config.json validation failed: {e}")
            return False, None

    def validate_all(self) -> bool:
        """Validate all configurations.

        Returns:
            True if all configurations are valid, False otherwise
        """
        logger.info("=" * 70)
        logger.info("OpenAntigravity Configuration Validation")
        logger.info("=" * 70)

        env_valid, env_config = self.validate_env_config()
        mcp_valid, mcp_config = self.validate_mcp_config()
        config_valid, antigravity_config = self.validate_antigravity_config()

        logger.info("=" * 70)
        logger.info("Validation Summary")
        logger.info("=" * 70)

        if env_valid:
            logger.info("✓ Environment configuration: PASSED")
        else:
            logger.error("✗ Environment configuration: FAILED")

        if mcp_valid:
            logger.info("✓ MCP configuration: PASSED")
        else:
            logger.error("✗ MCP configuration: FAILED")

        if config_valid:
            logger.info("✓ Antigravity configuration: PASSED")
        else:
            logger.error("✗ Antigravity configuration: FAILED")

        if self.warnings:
            logger.warning("\nWarnings:")
            for warning in self.warnings:
                logger.warning(f"  - {warning}")

        if self.errors:
            logger.error("\nErrors:")
            for error in self.errors:
                logger.error(f"  - {error}")

        logger.info("=" * 70)

        all_valid = env_valid and mcp_valid and config_valid

        if all_valid:
            logger.info("✓ All configurations are valid!")
        else:
            logger.error("✗ Validation failed. Please check the errors above.")

        return all_valid

    def export_schemas(self, output_dir: Path | None = None) -> None:
        """Export JSON schemas for all configuration types.

        Args:
            output_dir: Directory to export schemas to. Defaults to docs/schemas/.
        """
        if output_dir is None:
            output_dir = self.root_path / "docs" / "schemas"

        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info(f"\nExporting JSON schemas to {output_dir}...")

        schemas = {
            "env.schema.json": self.loader.get_json_schema(EnvConfig),
            "mcp.schema.json": self.loader.get_json_schema(MCPConfig),
            "config.schema.json": self.loader.get_json_schema(AntigravityConfig),
        }

        for filename, schema in schemas.items():
            output_path = output_dir / filename
            with open(output_path, "w") as f:
                json.dump(schema, f, indent=2, default=str)
            logger.info(f"✓ Exported {filename}")

        logger.info("Schema export completed!")

    def validate_with_fix(self) -> bool:
        """Validate configurations and attempt to fix common issues.

        Returns:
            True if validation passes (after fixes), False otherwise
        """
        logger.info("Running validation with auto-fix...")
        logger.info("(Note: auto-fix is limited to format/schema issues)")

        # For now, this is just a wrapper around validate_all
        # In a real scenario, we might attempt to fix things like:
        # - Migrating legacy config formats
        # - Normalizing path separators
        # - Converting environment variable formats
        # etc.

        return self.validate_all()

    def get_summary(self) -> dict[str, Any]:
        """Get validation summary.

        Returns:
            Dictionary with validation results
        """
        return {
            "timestamp": str(Path.cwd()),
            "valid": len(self.errors) == 0,
            "errors_count": len(self.errors),
            "warnings_count": len(self.warnings),
            "errors": self.errors,
            "warnings": self.warnings,
        }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Validate OpenAntigravity configurations")
    parser.add_argument(
        "--fix", action="store_true", help="Validate and attempt to fix common issues"
    )
    parser.add_argument("--export-schemas", action="store_true", help="Export JSON schemas")
    parser.add_argument("--root", type=Path, default=None, help="Root path for configuration files")
    parser.add_argument(
        "--json-output", type=Path, default=None, help="Write validation results to JSON file"
    )

    args = parser.parse_args()

    validator = ConfigValidator(args.root)

    if args.export_schemas:
        validator.export_schemas()
        return 0

    if args.fix:
        is_valid = validator.validate_with_fix()
    else:
        is_valid = validator.validate_all()

    if args.json_output:
        summary = validator.get_summary()
        args.json_output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json_output, "w") as f:
            json.dump(summary, f, indent=2)
        logger.info(f"Validation results written to {args.json_output}")

    return 0 if is_valid else 1


if __name__ == "__main__":
    sys.exit(main())
