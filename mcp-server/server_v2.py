#!/usr/bin/env python3
"""
Antigravity MCP Server v2.3 - Adaptive Transport & Stealth Mode.

Changes:
- ADAPTIVE RESPONSES: Detects if client uses Content-Length or Raw JSON and matches it.
- STEALTH LOGGING: Redirects INFO logs to 'mcp_server.log' to prevent stream pollution.
- ZERO LATENCY STARTUP: Responds to 'initialize' immediately.
"""

import asyncio
import json
import logging
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from collections.abc import Callable
from dataclasses import dataclass, field

# =============================================================================
# CONFIGURATION & LOGGING
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent
LOG_FILE = Path(__file__).parent / "mcp_server.log"

# Setup logging to FILE to keep stdout clean
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] [%(levelname)s] %(name)s: %(message)s',
    filename=str(LOG_FILE),
    filemode='a'
)
logger = logging.getLogger("antigravity.mcp")

# Also add a stderr handler for critical errors only
stderr_handler = logging.StreamHandler(sys.stderr)
stderr_handler.setLevel(logging.ERROR)
logger.addHandler(stderr_handler)

SKILLS_DIR = PROJECT_ROOT / ".agent" / "skills"
AGENTS_DIR = PROJECT_ROOT / ".agent" / "agents"

# =============================================================================
# MODELS
# =============================================================================

@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict
    handler: Callable | None = None

# =============================================================================
# MCP SERVER
# =============================================================================

class AntigravityMCPServer:
    def __init__(self):
        self.tools: dict[str, MCPTool] = {}
        self.skills: dict[str, dict] = {}
        self.agents: dict[str, dict] = {}
        self.discovery_complete = False
        self.use_framing = False # Will be detected per request

        self._register_system_tools()

    def _register_system_tools(self) -> None:
        self.tools["sequential_thinking"] = MCPTool(
            name="sequential_thinking",
            description="Structured thinking process",
            input_schema={"type":"object", "properties":{"problem":{"type":"string"}}},
            handler=lambda problem="": {"status": "analyzing", "problem": problem}
        )
        self.tools["list_skills"] = MCPTool(
            name="list_skills",
            description="List discovered skills",
            input_schema={"type":"object", "properties":{}},
            handler=self._handle_list_skills
        )
        self.tools["system_status"] = MCPTool(
            name="system_status",
            description="Check discovery progress",
            input_schema={"type":"object", "properties":{}},
            handler=self._handle_system_status
        )
        self.tools["search_skills"] = MCPTool(
            name="search_skills",
            description="Search the Antigravity knowledge base (700+ skills) for domain expertise.",
            input_schema={"type":"object", "properties":{"query":{"type":"string", "description":"Keywords"}}, "required": ["query"]},
            handler=self._handle_search_skills
        )
        self.tools["read_skill"] = MCPTool(
            name="read_skill",
            description="Read the full markdown content of a specific skill to adopt its rules.",
            input_schema={"type":"object", "properties":{"skill_name":{"type":"string", "description":"Exact name"}}, "required": ["skill_name"]},
            handler=self._handle_read_skill
        )

    async def start_discovery(self):
        try:
            if AGENTS_DIR.exists():
                for d in AGENTS_DIR.iterdir():
                    if d.is_dir() and not d.name.startswith(('.', '_')):
                        self.agents[d.name] = {"path": str(d)}

            if SKILLS_DIR.exists():
                for d in SKILLS_DIR.iterdir():
                    if d.is_dir() and not d.name.startswith(('.', '_')):
                        self.skills[d.name] = {"found": True}
                        if len(self.skills) % 200 == 0: await asyncio.sleep(0.01)

            self.discovery_complete = True
            logger.info(f"Discovery complete: {len(self.skills)} skills found.")
        except Exception as e:
            logger.error(f"Discovery error: {e}")

    async def _handle_list_skills(self) -> dict:
        return {"total": len(self.skills), "ready": self.discovery_complete}

    async def _handle_system_status(self) -> dict:
        return {"status": "online", "version": "2.3.0", "discovery": self.discovery_complete}

    async def _handle_search_skills(self, query: str = "") -> dict:
        q = query.lower()
        results = [name for name in self.skills if q in name.lower()]
        return {"matches": results[:20], "total_matches": len(results)}

    async def _handle_read_skill(self, skill_name: str = "") -> dict:
        skill_path = SKILLS_DIR / skill_name / "SKILL.md"
        if skill_path.exists():
            return {"content": skill_path.read_text(encoding="utf-8", errors="replace")}

        # Check custom skills just in case
        custom_skills_dir = PROJECT_ROOT / ".agent" / "skills-custom"
        custom_path = custom_skills_dir / skill_name / "SKILL.md"
        if custom_path.exists():
            return {"content": custom_path.read_text(encoding="utf-8", errors="replace")}

        return {"error": f"Skill {skill_name} not found locally."}

    async def handle_message(self, message: dict) -> dict | None:
        method = message.get("method", "")
        msg_id = message.get("id")
        params = message.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "capabilities": {"tools": {}},
                    "serverInfo": {"name": "antigravity-adaptive", "version": "2.3.0"}
                }
            }

        if method == "tools/list":
            return {
                "jsonrpc": "2.0", "id": msg_id,
                "result": {
                    "tools": [{"name": t.name, "description": t.description, "inputSchema": t.input_schema}
                             for t in self.tools.values()]
                }
            }

        if method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            if tool_name in self.tools:
                res = await self.tools[tool_name].handler(**args)
                return {
                    "jsonrpc": "2.0", "id": msg_id,
                    "result": {"content": [{"type": "text", "text": json.dumps(res)}]}
                }

        return None

    async def run_stdio(self):
        logger.info("Adaptive MCP Server v2.3 Starting...")
        asyncio.create_task(self.start_discovery())

        loop = asyncio.get_event_loop()
        reader = sys.stdin.buffer

        while True:
            try:
                line = await loop.run_in_executor(None, reader.readline)
                if not line: break

                line_str = line.decode('utf-8').strip()
                if not line_str: continue

                msg_use_framing = False
                # Detect Content-Length
                if line_str.lower().startswith('content-length:'):
                    msg_use_framing = True
                    length = int(line_str.split(':')[1].strip())
                    await loop.run_in_executor(None, reader.readline) # blank line
                    body = await loop.run_in_executor(None, reader.read, length)
                    message = json.loads(body.decode('utf-8'))
                else:
                    # Raw JSON line
                    try:
                        message = json.loads(line_str)
                    except json.JSONDecodeError:
                        continue

                response = await self.handle_message(message)
                if response:
                    res_json = json.dumps(response).encode('utf-8')
                    if msg_use_framing:
                        # Responde con framing si el cliente lo usó
                        header = f"Content-Length: {len(res_json)}\r\n\r\n".encode()
                        sys.stdout.buffer.write(header + res_json)
                    else:
                        # Responde JSON puro si el cliente envió JSON puro
                        sys.stdout.buffer.write(res_json + b'\n')
                    sys.stdout.buffer.flush()

            except Exception as e:
                logger.error(f"IO Error: {e}")

if __name__ == "__main__":
    server = AntigravityMCPServer()
    try:
        asyncio.run(server.run_stdio())
    except Exception as e:
        logger.critical(f"Server crashed: {e}")
