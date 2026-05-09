"""
Scaffold Generator Skill — Genera scaffolding de proyectos desde templates.

Uso:
    py .agent/skills-custom/scaffold-generator/scripts/main.py --type fastapi --name "mi-api"
    py .agent/skills-custom/scaffold-generator/scripts/main.py --type agent --name "mi-agente"
    py .agent/skills-custom/scaffold-generator/scripts/main.py --type skill --name "mi-skill"
    py .agent/skills-custom/scaffold-generator/scripts/main.py --type tauri-plugin --name "mi-plugin"
    py .agent/skills-custom/scaffold-generator/scripts/main.py --type mcp-server --name "mi-server"
    py .agent/skills-custom/scaffold-generator/scripts/main.py --type react --name "mi-react"
    py .agent/skills-custom/scaffold-generator/scripts/main.py --list
    py .agent/skills-custom/scaffold-generator/scripts/main.py --type agent --name "test" --dry-run
"""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Template definitions (after all constants are declared below)
# ---------------------------------------------------------------------------

VALID_TYPES = ["fastapi", "react", "tauri-plugin", "agent", "skill", "mcp-server"]


# ---------------------------------------------------------------------------
# Template content
# ---------------------------------------------------------------------------

# -- FastAPI --

FASTAPI_MAIN = '''"""{{PROJECT_NAME}} — FastAPI application entry point."""

from fastapi import FastAPI

app = FastAPI(
    title="{{PROJECT_NAME}}",
    description="FastAPI application generated from scaffold",
    version="0.1.0",
)


@app.get("/")
def root():
    """Root endpoint."""
    return {"app": "{{PROJECT_NAME}}", "status": "running"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
'''

FASTAPI_ROUTES_INIT = '"""Routes package."""\n\nfrom . import health\n\n__all__ = ["health"]\n'

FASTAPI_HEALTH = '''"""Health check routes."""

from fastapi import APIRouter

router = APIRouter(prefix="/health", tags=["health"])


@router.get("")
def health_check():
    """Basic health check."""
    return {"status": "ok"}
'''

FASTAPI_MODELS_INIT = '"""Models package."""\n\nfrom . import base\n\n__all__ = ["base"]\n'

FASTAPI_BASE = '''"""Base models for the application."""

from pydantic import BaseModel


class AppBaseModel(BaseModel):
    """Base model with common configuration."""

    model_config = {"from_attributes": True}
'''

FASTAPI_SCHEMAS_INIT = '"""Schemas package."""\n\nfrom . import common\n\n__all__ = ["common"]\n'

FASTAPI_COMMON = '''"""Common schemas shared across the application."""

from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(description="Health status")


class ErrorResponse(BaseModel):
    """Error response schema."""

    detail: str = Field(description="Error message")
    code: str | None = Field(default=None, description="Error code")
'''

FASTAPI_TEST_MAIN = '''"""Tests for main module."""

import pytest
from fastapi.testclient import TestClient

from main import app

client = TestClient(app)


def test_root():
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["status"] == "running"


def test_health():
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"
'''

FASTAPI_PYPROJECT = '''[project]
name = "{{PROJECT_NAME}}"
version = "0.1.0"
description = "FastAPI application generated from scaffold"
requires-python = ">=3.11"
dependencies = [
    "fastapi>=0.115.0",
    "uvicorn[standard]>=0.32.0",
    "pydantic>=2.9.0",
    "python-dotenv>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.3.0",
    "pytest-asyncio>=0.24.0",
    "httpx>=0.27.0",
]

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["tests"]
'''

FASTAPI_ENV_EXAMPLE = '''# Application settings
APP_NAME="{{PROJECT_NAME}}"
DEBUG=true
HOST=0.0.0.0
PORT=8000

# API keys (replace with real values in .env)
# API_KEY=your_api_key_here
'''

FASTAPI_README = '''# {{PROJECT_NAME}}

FastAPI application generated from scaffold.

## Setup

```bash
pip install -e ".[dev]"
```

## Run

```bash
uvicorn main:app --reload
```

## Test

```bash
pytest
```
'''

# -- React --

REACT_PACKAGE = '''{{PROJECT_NAME}}'''
REACT_TSCONFIG = '''{{PROJECT_NAME}}'''
REACT_VITE_CONFIG = '''{{PROJECT_NAME}}'''
REACT_INDEX_HTML = '''{{PROJECT_NAME}}'''
REACT_MAIN_TSX = '''{{PROJECT_NAME}}'''
REACT_APP_TSX = '''{{PROJECT_NAME}}'''
REACT_COUNTER = '''{{PROJECT_NAME}}'''
REACT_README = '''{{PROJECT_NAME}}'''

# -- Tauri plugin --

TAURI_LIB = '''//! {{PROJECT_NAME}} — Tauri plugin entry point.
//!
//! Register commands and initialize plugin state here.

#![doc(hidden)]

use tauri::Plugin;

/// Plugin state (add fields as needed)
pub struct {{PROJECT_NAME_CAPITALIZE}}Plugin;

/// Initialize the plugin.
impl Plugin for {{PROJECT_NAME_CAPITALIZE}}Plugin {
    fn name(&self) -> &'static str {
        "{{PROJECT_NAME}}"
    }

    fn initialize(&mut self, app: &tauri::AppHandle) -> Result<(), tauri::Error> {
        logger::info!("Plugin {{PROJECT_NAME}} initialized");
        Ok(())
    }
}
'''

TAURI_COMMANDS_MOD = '''//! Tauri plugin commands module.

mod hello;

pub use hello::*;
'''

TAURI_HELLO = '''//! Hello world command for {{PROJECT_NAME}}.

use tauri::command;

#[command]
pub fn hello(name: Option<String>) -> String {
    let who = name.unwrap_or_else(|| "world".to_string());
    format!("Hello, {{PROJECT_NAME}}! Hello, {}!", who)
}
'''

TAURI_INDEX_TS = '''/**
 * {{PROJECT_NAME}} — Tauri plugin public API.
 *
 * Import commands and expose them to consumers.
 */

export * from "./types";

export const pluginName = "{{PROJECT_NAME}}";

/**
 * Initialize the plugin (call once at app start).
 */
export async function initPlugin(): Promise<void> {
  console.log("[{{PROJECT_NAME}}] Plugin initialized");
}
'''

TAURI_PACKAGE = '''{{PROJECT_NAME}}'''
TAURI_README = '''{{PROJECT_NAME}}'''

# -- Agent --

AGENT_IDENTITY = '''---
name: {{PROJECT_NAME}}
description: "Agente generado desde scaffold — completar descripcion y capacidades."
---

# {{PROJECT_NAME}}

## Identity

**Tier:** 9 (Specialized)
**Type:** specialized / utility / analysis
**Auth Required:** No

## Capabilities

- [ ] Capacidad 1
- [ ] Capacidad 2

## Constraints

- [ ] Restriccion 1
- [ ] Restriccion 2

## Examples

```
python scripts/main.py --task "..."
```
'''

AGENT_SHARED_MEMORY = '''{{PROJECT_NAME}}'''

AGENT_MAIN = '''"""{{PROJECT_NAME}} — Agent entry point."""

from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class AgentInput:
    """Input validated for the agent."""

    task: str
    params: dict[str, Any] | None = None


@dataclass
class AgentOutput:
    """Output from the agent."""

    result: Any
    status: str = "success"
    message: str = ""


def execute(task: str, params: dict[str, Any] | None = None) -> AgentOutput:
    """Execute the agent task.

    Args:
        task: Task description
        params: Optional parameters

    Returns:
        AgentOutput with result and status
    """
    input_data = AgentInput(task=task, params=params or {})

    # TODO: Implement agent logic
    result = {"agent": "{{PROJECT_NAME}}", "task": input_data.task, "status": "implemented"}

    return AgentOutput(result=result, status="success", message="Task completed")


if __name__ == "__main__":
    import argparse
    import logging
    import sys

    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
    logger = logging.getLogger(__name__)

    parser = argparse.ArgumentParser(description="{{PROJECT_NAME}} agent")
    parser.add_argument("--task", required=True, help="Task description")
    parser.add_argument("--param", action="append", dest="params", help="key=value parameters")
    args = parser.parse_args()

    params: dict[str, Any] = {}
    if args.params:
        for p in args.params:
            if "=" in p:
                k, v = p.split("=", 1)
                params[k] = v

    try:
        output = execute(args.task, params)
        print(output.message or output.result)
        sys.exit(0)
    except Exception as e:
        logger.error("Agent failed: %s", e)
        sys.exit(1)
'''

AGENT_README = '''{{PROJECT_NAME}}'''

# -- Skill --

SKILL_SKILL_MD = '''{{PROJECT_NAME}}'''

SKILL_MAIN = '''"""{{PROJECT_NAME}} — Skill entry point."""

import argparse
import logging
import sys
from typing import Any

logger = logging.getLogger(__name__)


def execute(params: dict[str, Any]) -> dict[str, Any]:
    """Execute the skill.

    Args:
        params: Skill parameters

    Returns:
        Result dictionary
    """
    logger.info("Executing {{PROJECT_NAME}}")

    # TODO: Implement skill logic
    return {
        "success": True,
        "message": "{{PROJECT_NAME}} executed",
        "data": {},
    }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")

    parser = argparse.ArgumentParser(description="{{PROJECT_NAME}} skill")
    parser.add_argument("--param", action="append", dest="params", help="key=value parameters")
    args = parser.parse_args()

    params: dict[str, Any] = {}
    if args.params:
        for p in args.params:
            if "=" in p:
                k, v = p.split("=", 1)
                params[k] = v

    try:
        result = execute(params)
        print(result.get("message", result))
        sys.exit(0)
    except Exception as e:
        logger.error("Skill failed: %s", e)
        sys.exit(1)
'''

SKILL_README = '''{{PROJECT_NAME}}'''

# -- MCP Server --

MCP_SERVER = '''"""MCP server core — define tools and handlers."""

import logging
from typing import Any

logger = logging.getLogger(__name__)


def setup_tools() -> list[dict[str, Any]]:
    """Define available MCP tools.

    Returns:
        List of tool definitions
    """
    return [
        {
            "name": "hello",
            "description": "Returns a greeting message",
            "input_schema": {
                "type": "object",
                "properties": {"name": {"type": "string", "description": "Name to greet"}},
                "required": [],
            },
        },
    ]


def handle_tool(name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Handle a tool call.

    Args:
        name: Tool name
        arguments: Tool arguments

    Returns:
        Tool result
    """
    if name == "hello":
        name_arg = arguments.get("name", "world")
        return {"content": [{"type": "text", "text": f"Hello, {name_arg}!"}]}
    raise ValueError(f"Unknown tool: {name}")
'''

MCP_ENTRY = '''"""{{PROJECT_NAME}} — MCP server portable entry point."""

import logging
import sys
from .src.server import setup_tools, handle_tool

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """Run the MCP server.

    Starts stdio server that processes JSON-RPC messages.
    """
    logger.info("Starting MCP server: {{PROJECT_NAME}}")

    tools = setup_tools()
    logger.info("Loaded %d tools", len(tools))

    try:
        for line in sys.stdin:
            line = line.strip()
            if not line:
                continue

            # Parse JSON-RPC request (simplified)
            import json

            try:
                request = json.loads(line)
                method = request.get("method", "")
                params = request.get("params", {})
                msg_id = request.get("id")

                if method == "tools/list":
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "result": {"tools": tools},
                    }
                elif method == "tools/call":
                    tool_name = params.get("name", "")
                    arguments = params.get("arguments", {})
                    result = handle_tool(tool_name, arguments)
                    response = {"jsonrpc": "2.0", "id": msg_id, "result": result}
                else:
                    response = {
                        "jsonrpc": "2.0",
                        "id": msg_id,
                        "error": {"code": -32601, "message": f"Method not found: {method}"},
                    }

                print(json.dumps(response), flush=True)

            except json.JSONDecodeError as e:
                logger.error("Invalid JSON: %s", e)
                continue

    except KeyboardInterrupt:
        logger.info("Server stopped")
        sys.exit(0)


if __name__ == "__main__":
    main()
'''

MCP_HTTP_GATEWAY = '''"""HTTP gateway for remote MCP server access."""

import logging
from aiohttp import web

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

routes = web.Application()


@routes.post("/mcp")
async def handle_mcp(request: web.Request) -> web.Response:
    """Handle MCP requests via HTTP."""
    from .src.server import setup_tools, handle_tool
    import json

    body = await request.json()
    method = body.get("method", "")
    params = body.get("params", {})
    msg_id = body.get("id")

    if method == "tools/list":
        tools = setup_tools()
        return web.json_response({"jsonrpc": "2.0", "id": msg_id, "result": {"tools": tools}})

    if method == "tools/call":
        tool_name = params.get("name", "")
        arguments = params.get("arguments", {})
        result = handle_tool(tool_name, arguments)
        return web.json_response({"jsonrpc": "2.0", "id": msg_id, "result": result})

    return web.json_response(
        {"jsonrpc": "2.0", "id": msg_id, "error": {"code": -32601, "message": f"Method not found: {method}"}}
    )


async def init_app() -> web.Application:
    """Initialize the application."""
    logger.info("MCP HTTP gateway initialized")
    return routes


if __name__ == "__main__":
    web.run_app(init_app(), host="0.0.0.0", port=8080)
'''

MCP_REQUIREMENTS = '''{{PROJECT_NAME}}'''

MCP_PYPROJECT = '''{{PROJECT_NAME}}'''

MCP_README = '''{{PROJECT_NAME}}'''

MCP_TEST = '''{{PROJECT_NAME}}'''


# ---------------------------------------------------------------------------
# Scaffold template registry (uses constants declared above)
# ---------------------------------------------------------------------------

SCAFFOLD_TEMPLATES: dict[str, list[tuple[str, str]]] = {
    "fastapi": [
        ("main.py", FASTAPI_MAIN),
        ("routes/__init__.py", FASTAPI_ROUTES_INIT),
        ("routes/health.py", FASTAPI_HEALTH),
        ("models/__init__.py", FASTAPI_MODELS_INIT),
        ("models/base.py", FASTAPI_BASE),
        ("schemas/__init__.py", FASTAPI_SCHEMAS_INIT),
        ("schemas/common.py", FASTAPI_COMMON),
        ("tests/__init__.py", ""),
        ("tests/test_main.py", FASTAPI_TEST_MAIN),
        ("pyproject.toml", FASTAPI_PYPROJECT),
        (".env.example", FASTAPI_ENV_EXAMPLE),
        ("README.md", FASTAPI_README),
    ],
    "react": [
        ("package.json", REACT_PACKAGE),
        ("tsconfig.json", REACT_TSCONFIG),
        ("vite.config.ts", REACT_VITE_CONFIG),
        ("index.html", REACT_INDEX_HTML),
        ("src/main.tsx", REACT_MAIN_TSX),
        ("src/App.tsx", REACT_APP_TSX),
        ("src/components/Counter.tsx", REACT_COUNTER),
        ("README.md", REACT_README),
    ],
    "tauri-plugin": [
        ("src-tauri/src/lib.rs", TAURI_LIB),
        ("src-tauri/src/commands/mod.rs", TAURI_COMMANDS_MOD),
        ("src-tauri/src/commands/hello.rs", TAURI_HELLO),
        ("src/index.ts", TAURI_INDEX_TS),
        ("package.json", TAURI_PACKAGE),
        ("README.md", TAURI_README),
    ],
    "agent": [
        ("IDENTITY.md", AGENT_IDENTITY),
        ("memory/shared_memory.json", AGENT_SHARED_MEMORY),
        ("scripts/__init__.py", ""),
        ("scripts/main.py", AGENT_MAIN),
        ("logs/.gitkeep", ""),
        ("README.md", AGENT_README),
    ],
    "skill": [
        ("SKILL.md", SKILL_SKILL_MD),
        ("scripts/__init__.py", ""),
        ("scripts/main.py", SKILL_MAIN),
        ("README.md", SKILL_README),
    ],
    "mcp-server": [
        ("src/__init__.py", ""),
        ("src/server.py", MCP_SERVER),
        ("server.py", MCP_ENTRY),
        ("http_gateway.py", MCP_HTTP_GATEWAY),
        ("requirements.txt", MCP_REQUIREMENTS),
        ("pyproject.toml", MCP_PYPROJECT),
        ("README.md", MCP_README),
        ("tests/__init__.py", ""),
        ("tests/test_server.py", MCP_TEST),
    ],
}


# ---------------------------------------------------------------------------
# Helper to substitute placeholders
# ---------------------------------------------------------------------------

PLACEHOLDER_RE = re.compile(r"\{\{PROJECT_NAME\}\}|\{\{PROJECT_NAME_CAPITALIZE\}\}")


def substitute(content: str, project_name: str) -> str:
    """Replace placeholders in template content.

    Args:
        content: Template string
        project_name: Project name

    Returns:
        Content with placeholders replaced
    """
    name_upper = project_name.upper().replace("-", "_")
    return PLACEHOLDER_RE.sub(
        lambda m: project_name if m.group() == "{{PROJECT_NAME}}" else name_upper, content
    )


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------


@dataclass
class ScaffoldResult:
    """Result of scaffolding operation."""

    status: str
    type: str
    name: str
    output_dir: Path
    files_created: list[str] = field(default_factory=list)
    files_skipped: list[str] = field(default_factory=list)
    message: str = ""


# ---------------------------------------------------------------------------
# Core scaffold logic
# ---------------------------------------------------------------------------

def scaffold_project(
    project_type: str,
    project_name: str,
    output_dir: Path | None = None,
    dry_run: bool = False,
    force: bool = False,
    interactive: bool = True,
) -> ScaffoldResult:
    """Scaffold a project from a template.

    Args:
        project_type: Type of project (fastapi, agent, skill, etc.)
        project_name: Name of the project
        output_dir: Output directory (default: current working directory)
        dry_run: If True, only show what would be created
        force: If True, overwrite existing files without asking
        interactive: If True, prompt before overwriting

    Returns:
        ScaffoldResult with outcome

    Raises:
        ValueError: If project_type is invalid or name is empty
    """
    if project_type not in VALID_TYPES:
        raise ValueError(
            f"Invalid project type: '{project_type}'. Available: {', '.join(VALID_TYPES)}"
        )

    if not project_name or not project_name.strip():
        raise ValueError("Project name cannot be empty")

    name_clean = project_name.strip().replace("/", "-").replace("\\", "-")
    out_dir = output_dir or Path.cwd()
    target_dir = out_dir / name_clean

    templates = SCAFFOLD_TEMPLATES[project_type]
    files_created: list[str] = []
    files_skipped: list[str] = []

    if dry_run:
        logger.info("[DRY-RUN] Would create project '%s' of type '%s' at '%s'", name_clean, project_type, target_dir)
        for rel_path, _ in templates:
            logger.info("[DRY-RUN]   + %s", rel_path)
        return ScaffoldResult(
            status="success",
            type=project_type,
            name=name_clean,
            output_dir=target_dir,
            files_created=[str(target_dir / rp) for rp, _ in templates],
            message="Dry run complete - no files created",
        )

    # Create project directory
    target_dir.mkdir(parents=True, exist_ok=True)

    for rel_path, template_content in templates:
        target_file = target_dir / rel_path
        target_file.parent.mkdir(parents=True, exist_ok=True)

        # Check if file exists
        if target_file.exists() and not force:
            if interactive:
                logger.warning("File exists: %s (skipping, use --force to overwrite)", target_file)
            files_skipped.append(str(target_file))
            continue

        # Apply placeholders
        final_content = substitute(template_content, name_clean)

        # Write file (skip empty content like __init__.py stubs)
        if final_content.strip():
            target_file.write_text(final_content, encoding="utf-8")
            logger.info("Created: %s", target_file)
        else:
            # Create empty marker files
            target_file.touch()
            logger.info("Created (empty): %s", target_file)

        files_created.append(str(target_file))

    skipped_msg = f" ({len(files_skipped)} skipped)" if files_skipped else ""
    return ScaffoldResult(
        status="success",
        type=project_type,
        name=name_clean,
        output_dir=target_dir,
        files_created=files_created,
        files_skipped=files_skipped,
        message=f"Created {len(files_created)} file(s){skipped_msg}",
    )


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="scaffold-generator",
        description="Genera scaffolding de proyectos desde templates",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Tipos disponibles:
  fastapi      Python FastAPI app
  react        React + TypeScript + Vite
  tauri-plugin Tauri 2 plugin para Nexus
  agent        Agente para .agent/agents/
  skill        Skill para .agent/skills-custom/
  mcp-server   MCP server portable
        """,
    )

    parser.add_argument("--type", "-t", help="Tipo de proyecto")
    parser.add_argument("--name", "-n", help="Nombre del proyecto")
    parser.add_argument("--output", "-o", help="Directorio de salida (default: cwd)")
    parser.add_argument("--dry-run", action="store_true", help="Solo mostrar que crearia sin crear")
    parser.add_argument("--force", "-f", action="store_true", help="Sobreescribir archivos existentes sin preguntar")
    parser.add_argument(
        "--list", "-l", action="store_true", help="Lista tipos disponibles y sale"
    )
    parser.add_argument("--verbose", "-v", action="store_true", help="Logging verbose")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
    )

    # --list mode
    if args.list:
        print("Tipos disponibles:")
        for t in VALID_TYPES:
            print(f"  {t}")
        return

    # Validate required args
    if not args.type or not args.name:
        parser.print_help()
        print("\nError: --type y --name son requeridos")
        raise SystemExit(1)

    # Run scaffold
    output_dir = Path(args.output) if args.output else None
    if output_dir:
        if not output_dir.exists():
            output_dir.mkdir(parents=True)
        elif not output_dir.is_dir():
            raise SystemExit(f"Output path is not a directory: {output_dir}")

    result = scaffold_project(
        project_type=args.type,
        project_name=args.name,
        output_dir=output_dir,
        dry_run=args.dry_run,
        force=args.force,
    )

    print(f"\nStatus: {result.status}")
    print(f"Tipo: {result.type}")
    print(f"Nombre: {result.name}")
    print(f"Directorio: {result.output_dir}")

    if result.files_created:
        print(f"\nArchivos creados ({len(result.files_created)}):")
        for f in result.files_created:
            print(f"  + {Path(f).relative_to(result.output_dir)}")

    if result.files_skipped:
        print(f"\nArchivos omitidos ({len(result.files_skipped)}):")
        for f in result.files_skipped:
            print(f"  - {Path(f).relative_to(result.output_dir)}")

    print(f"\n{result.message}")

    if result.status != "success":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
