#!/usr/bin/env python3
"""Source-mode entrypoint for the portable ``antigravity-mcp`` executable."""

from __future__ import annotations

import sys

from core.mcp_stdio_proxy import main as stdio_main


def main() -> int:
    """Dispatch stdio MCP or portable hook operations from one executable."""

    if len(sys.argv) > 1 and sys.argv[1] == "session-report":
        from core.gateway_client import main as gateway_client_main

        return gateway_client_main(sys.argv[1:])
    return stdio_main()


if __name__ == "__main__":
    raise SystemExit(main())
