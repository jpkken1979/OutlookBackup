#!/usr/bin/env python3
"""MCP server exposing design-md collection tools.

Provides list, get, and apply operations for the awesome-design-md collection.

Tools:
- design_md_list: List designs, optionally filtered by category
- design_md_get: Get full content of a design by name
- design_md_apply: Copy a design's README.md to a target directory

Endpoints:
- GET  /manifest          — server manifest
- GET  /tools             — list of available tools
- POST /tools/design_md_list
- POST /tools/design_md_get
- POST /tools/design_md_apply

Port: 4752
"""

from __future__ import annotations

import json
import logging
import re
import shutil
import sys
from pathlib import Path
from typing import Any

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_COLLECTION_ROOT = Path(__file__).parent.parent / "tmp" / "awesome-design" / "design-md"
_INDEX_PATH = Path(__file__).parent.parent / "skills" / "design-md-collection" / "INDEX.md"

# Add scripts to path for apply_design import
_scripts_path = Path(__file__).parent.parent / "skills" / "design-md-collection" / "scripts"
if str(_scripts_path) not in sys.path:
    sys.path.insert(0, str(_scripts_path))


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _parse_index() -> list[dict[str, str]]:
    """Parse the INDEX.md markdown table into a list of design dicts."""
    designs: list[dict[str, str]] = []
    if not _INDEX_PATH.exists():
        logger.warning("INDEX.md not found at %s", _INDEX_PATH)
        return designs

    content = _INDEX_PATH.read_text(encoding="utf-8")
    # Skip header and separator lines
    for line in content.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or line.startswith("| Name"):
            continue
        # Table row: | `name` | Category | Tags | Summary |
        parts = [p.strip() for p in line.split("|")]
        # parts[0] is empty before first |, parts[-1] is empty after last |
        if len(parts) < 5:
            continue
        name = parts[1].strip("` \t")
        # Skip separator rows (all ---)
        if not name or name in ("---", "Name"):
            continue
        category = parts[2].strip()
        tags = parts[3].strip()
        summary = parts[4].strip()
        designs.append({
            "name": name,
            "category": category,
            "tags": tags,
            "summary": summary,
        })
    return designs


def _resolve_readme_path(name: str) -> Path | None:
    """Resolve the README.md path for a given design name."""
    design_dir = _COLLECTION_ROOT / name
    if not design_dir.exists():
        return None
    # Prefer DESIGN.md, fall back to README.md
    for fname in ("DESIGN.md", "README.md"):
        p = design_dir / fname
        if p.exists():
            return p
    return None


# ---------------------------------------------------------------------------
# Tool implementations
# ---------------------------------------------------------------------------

def tool_list(category: str | None = None) -> dict[str, Any]:
    """List designs, optionally filtered by category."""
    designs = _parse_index()
    if category:
        designs = [d for d in designs if d["category"] == category]
    return {
        "designs": designs,
        "count": len(designs),
    }


def tool_get(name: str) -> dict[str, Any]:
    """Get full content of a design by name."""
    readme_path = _resolve_readme_path(name)
    if readme_path is None:
        return {"success": False, "error": f"Design '{name}' not found in collection"}
    content = readme_path.read_text(encoding="utf-8")
    return {
        "success": True,
        "name": name,
        "content": content,
        "path": str(readme_path),
    }


def tool_apply(name: str, target: str) -> dict[str, Any]:
    """Copy a design's README.md to target/DESIGN.md."""
    readme_path = _resolve_readme_path(name)
    if readme_path is None:
        return {"success": False, "error": f"Design '{name}' not found in collection"}

    target_dir = Path(target)
    if not target_dir.is_dir():
        return {"success": False, "error": f"Target path is not a directory: {target}"}

    dest_path = target_dir / "DESIGN.md"
    backup_path = None

    if dest_path.exists():
        backup_path = dest_path.with_suffix(".md.bak")
        shutil.copy2(dest_path, backup_path)
        logger.info("Backed up existing DESIGN.md to %s", backup_path)

    shutil.copy2(readme_path, dest_path)
    logger.info("Applied design '%s' -> %s", name, dest_path)

    result: dict[str, Any] = {
        "success": True,
        "name": name,
        "target": str(dest_path),
    }
    if backup_path:
        result["backup"] = str(backup_path)
    return result


# ---------------------------------------------------------------------------
# MCP HTTP server (FastAPI)
# ---------------------------------------------------------------------------

try:
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import JSONResponse
    import uvicorn
except ImportError:
    logger.error("FastAPI and uvicorn are required: pip install fastapi uvicorn")
    sys.exit(1)

app = FastAPI(title="design-md-server")

MANIFEST = {
    "name": "design-md",
    "version": "1.0.0",
    "description": "MCP server for awesome-design-md collection",
    "port": 4752,
}


@app.get("/manifest")
def get_manifest() -> JSONResponse:
    return JSONResponse(content=MANIFEST)


@app.get("/tools")
def get_tools() -> JSONResponse:
    return JSONResponse(content={
        "tools": [
            {
                "name": "design_md_list",
                "description": "List designs from the collection, optionally filtered by category.",
                "input_schema": {
                    "type": "object",
                    "properties": {
                        "category": {
                            "type": "string",
                            "description": "Optional category to filter by (e.g. 'AI / LLM', 'Productivity / SaaS')",
                        },
                    },
                },
            },
            {
                "name": "design_md_get",
                "description": "Get the full markdown content of a design by name.",
                "input_schema": {
                    "type": "object",
                    "required": ["name"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Design name (slug, e.g. 'figma', 'vercel', 'stripe')",
                        },
                    },
                },
            },
            {
                "name": "design_md_apply",
                "description": "Copy a design's README.md to target/DESIGN.md with optional backup.",
                "input_schema": {
                    "type": "object",
                    "required": ["name", "target"],
                    "properties": {
                        "name": {
                            "type": "string",
                            "description": "Design name (slug)",
                        },
                        "target": {
                            "type": "string",
                            "description": "Absolute path to the target project directory",
                        },
                    },
                },
            },
        ],
    })


@app.post("/tools/design_md_list")
def post_design_md_list(body: dict[str, Any] | None = None) -> JSONResponse:
    category: str | None = body.get("category") if body else None
    return JSONResponse(content=tool_list(category))


@app.post("/tools/design_md_get")
def post_design_md_get(body: dict[str, Any]) -> JSONResponse:
    name = body.get("name")
    if not name:
        raise HTTPException(status_code=400, detail="Missing required field: name")
    return JSONResponse(content=tool_get(name))


@app.post("/tools/design_md_apply")
def post_design_md_apply(body: dict[str, Any]) -> JSONResponse:
    name = body.get("name")
    target = body.get("target")
    if not name or not target:
        raise HTTPException(status_code=400, detail="Missing required fields: name and target")
    result = tool_apply(name, target)
    status = 200 if result.get("success") else 404
    return JSONResponse(content=result, status_code=status)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    logger.info("Starting design-md server on port 4752...")
    logger.info("Collection root: %s", _COLLECTION_ROOT)
    logger.info("INDEX path: %s", _INDEX_PATH)
    uvicorn.run(app, host="127.0.0.1", port=4752, log_level="info")
