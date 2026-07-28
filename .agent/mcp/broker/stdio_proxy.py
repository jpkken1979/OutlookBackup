"""Compatibility import for the canonical portable stdio shim."""

from core.mcp_stdio_proxy import (  # noqa: F401
    DEFAULT_BROKER_URL,
    StdioBrokerProxy,
    main,
)

__all__ = ["DEFAULT_BROKER_URL", "StdioBrokerProxy", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
