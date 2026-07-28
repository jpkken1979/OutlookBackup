#!/usr/bin/env python3
"""
Antigravity UI/UX MCP Server
============================
Specialized MCP server for UI/UX operations, shadcn/ui integration,
and design system management.

Tools:
- install_component: Install shadcn/ui components
- list_components: List available components
- get_color_palette: Generate OKLCH color palette
- check_contrast: Check accessibility contrast (simulated)
"""

import json
import logging
import re
import sys
import subprocess
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class Tool:
    name: str
    description: str
    input_schema: dict


def handle_request(request):
    method = request.get("method")
    params = request.get("params", {})
    request_id = request.get("id")

    # Notifications don't get responses (JSON-RPC 2.0 spec)
    if method and method.startswith("notifications/"):
        return None

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": request_id,
            "result": {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "antigravity-ui-ux", "version": "1.0.0"},
            },
        }

    if method == "tools/list":
        tools = [
            {
                "name": "install_component",
                "description": "Install a shadcn/ui component into the project using npx",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Name of component (e.g. 'button', 'card', 'dialog')",
                        }
                    },
                    "required": ["name"],
                },
            },
            {
                "name": "list_ui_components",
                "description": "List all available shadcn/ui components",
                "inputSchema": {"type": "object", "properties": {}, "required": []},
            },
            {
                "name": "get_color_palette",
                "description": "Get OKLCH color palette code for globals.css",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "theme": {
                            "type": "string",
                            "enum": [
                                "zinc",
                                "slate",
                                "stone",
                                "gray",
                                "neutral",
                                "red",
                                "rose",
                                "orange",
                                "green",
                                "blue",
                                "yellow",
                                "violet",
                            ],
                            "default": "slate",
                        }
                    },
                },
            },
        ]
        return {"jsonrpc": "2.0", "id": request_id, "result": {"tools": tools}}

    if method == "tools/call":
        name = params.get("name")
        args = params.get("arguments", {})

        if name == "install_component":
            comp_name = args.get("name", "")
            # SECURITY: Validate component name to prevent command injection
            if not comp_name or not re.match(r"^[a-z][a-z0-9-]*$", comp_name):
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": f"Invalid component name: '{comp_name}'. Use lowercase letters, numbers and hyphens only.",
                            }
                        ],
                        "isError": True,
                    },
                }
            try:
                cmd = ["npx", "shadcn@latest", "add", "-y", comp_name]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)

                output = result.stdout + result.stderr
                success = result.returncode == 0
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {
                        "content": [{"type": "text", "text": output}],
                        "isError": not success,
                    },
                }
            except Exception as e:
                return {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"content": [{"type": "text", "text": str(e)}], "isError": True},
                }

        elif name == "list_ui_components":
            # Hardcoded list based on knowledge as npx list might be slow
            components = [
                "accordion",
                "alert",
                "alert-dialog",
                "aspect-ratio",
                "avatar",
                "badge",
                "breadcrumb",
                "button",
                "calendar",
                "card",
                "carousel",
                "checkbox",
                "collapsible",
                "combobox",
                "command",
                "context-menu",
                "data-table",
                "date-picker",
                "dialog",
                "drawer",
                "dropdown-menu",
                "form",
                "hover-card",
                "input",
                "input-otp",
                "label",
                "menubar",
                "navigation-menu",
                "pagination",
                "popover",
                "progress",
                "radio-group",
                "resizable",
                "scroll-area",
                "select",
                "separator",
                "sheet",
                "sidebar",
                "skeleton",
                "slider",
                "sonner",
                "switch",
                "table",
                "tabs",
                "textarea",
                "toast",
                "toggle",
                "toggle-group",
                "tooltip",
            ]
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {
                    "content": [
                        {"type": "text", "text": "Available components:\n" + "\n".join(components)}
                    ]
                },
            }

        elif name == "get_color_palette":
            # Return standard OKLCH palette
            palette = """@theme {
  --color-background: oklch(1 0 0);
  --color-foreground: oklch(0.145 0.02 285);
  --color-primary: oklch(0.205 0.02 285);
  --color-primary-foreground: oklch(0.985 0 0);
  /* Add full palette here */
}"""
            return {
                "jsonrpc": "2.0",
                "id": request_id,
                "result": {"content": [{"type": "text", "text": palette}]},
            }

    return {
        "jsonrpc": "2.0",
        "id": request_id,
        "error": {"code": -32601, "message": "Method not found"},
    }


if __name__ == "__main__":
    # Los pipes stdio en Windows heredan la codepage del locale (cp932 en JP),
    # pero el protocolo MCP habla UTF-8: sin esto, el JSON entrante con no-ASCII
    # llega con surrogates sueltos y la respuesta puede fallar al escribirse.
    if hasattr(sys.stdin, "reconfigure"):
        sys.stdin.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    while True:
        try:
            line = sys.stdin.readline()
            if not line:
                break
            request = json.loads(line)
            response = handle_request(request)
            if response is not None:
                sys.stdout.write(json.dumps(response) + "\n")
                sys.stdout.flush()
        except Exception:
            logger.exception("main loop error")
