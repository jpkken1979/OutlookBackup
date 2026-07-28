"""Antigravity gateway plus the official MCP SDK namespace.

The historical gateway lives in ``.agent/mcp`` and therefore shares the
top-level package name used by the official Python SDK. Extending the package
path keeps legacy imports such as ``mcp.gateway`` working while allowing the
broker to import the SDK implementation from ``mcp.server.fastmcp``.
"""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
