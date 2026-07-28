#!/usr/bin/env python3
"""Regenera las configs MCP del repo para la plataforma actual.

Las configs MCP (`.mcp.json` y las de cada IDE) NO se versionan: cada maquina
las genera con este script para que el interprete Python, npx/uvx y el PATH sean
correctos para SU sistema operativo (Windows / macOS / Linux). La fuente unica de
verdad es `get_mcp_servers()` en `mcp_injector.py`.

Uso:
    python .agent/scripts/regen_mcp_configs.py            # regenera en el repo
    python .agent/scripts/regen_mcp_configs.py --target X # regenera en otro dir
    python .agent/scripts/regen_mcp_configs.py --no-dev-preset

Ver .claude/memory/config_mcp_paths_portables.md y
.claude/rules/config-guard.md.
"""

from __future__ import annotations

import argparse
import importlib
import logging
import platform
import sys
from pathlib import Path
from types import ModuleType

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]


def _load_injector() -> ModuleType:
    """Load the canonical injector package rather than the legacy monolith."""

    scripts_dir = REPO_ROOT / ".agent" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    return importlib.import_module("mcp_injector.mcp_config")


def regenerate_configs(target_dir: Path, enable_dev_preset: bool = True) -> list[Path]:
    """Regenera todas las configs MCP en target_dir para la plataforma actual.

    Args:
        target_dir: Directorio donde escribir las configs (normalmente el repo).
        enable_dev_preset: Incluir los MCP de desarrollo (context7, git, etc.).

    Returns:
        Lista de rutas escritas correctamente.
    """
    injector = _load_injector()
    servers = injector.get_mcp_servers(
        REPO_ROOT,
        target_dir=target_dir,
        enable_dev_preset=enable_dev_preset,
    )

    # Configs en formato estandar `mcpServers`.
    mcpservers_targets = [
        target_dir / ".mcp.json",
        target_dir / ".cursor" / "mcp.json",
        target_dir / ".windsurf" / "mcp.json",
        target_dir / ".vscode" / "cline_mcp_settings.json",
    ]

    written: list[Path] = []
    for path in mcpservers_targets:
        path.parent.mkdir(parents=True, exist_ok=True)
        if injector.safe_merge_json(path, servers):
            written.append(path)

    # VS Code (GitHub Copilot) usa formato nativo: clave raiz "servers" + campo
    # "type" por servidor. NO "mcpServers" (lo ignora). Cline (arriba) si lo usa.
    vscode_mcp_path = target_dir / ".vscode" / "mcp.json"
    vscode_mcp_path.parent.mkdir(parents=True, exist_ok=True)
    if injector.safe_merge_vscode_mcp(vscode_mcp_path, servers):
        written.append(vscode_mcp_path)

    # Zed usa el formato `context_servers`.
    zed_path = target_dir / ".zed" / "settings.json"
    zed_path.parent.mkdir(parents=True, exist_ok=True)
    if injector.safe_merge_zed_settings(zed_path, servers):
        written.append(zed_path)

    # Continue's legacy JSON format remains supported during its YAML migration.
    continue_path = target_dir / ".continue" / "config.json"
    continue_path.parent.mkdir(parents=True, exist_ok=True)
    if injector.safe_merge_continue_json(continue_path, servers):
        written.append(continue_path)

    codex_path = target_dir / ".codex" / "config.toml"
    codex_path.parent.mkdir(parents=True, exist_ok=True)
    if injector.safe_merge_codex_toml(codex_path, servers):
        written.append(codex_path)

    gemini_path = target_dir / ".gemini" / "settings.json"
    gemini_path.parent.mkdir(parents=True, exist_ok=True)
    if injector.safe_merge_json(gemini_path, servers):
        written.append(gemini_path)

    return written


def main() -> int:
    """Punto de entrada CLI."""
    logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
    parser = argparse.ArgumentParser(description="Regenera las configs MCP para esta plataforma.")
    parser.add_argument(
        "--target",
        type=Path,
        default=REPO_ROOT,
        help="Directorio destino (por defecto: la raiz del repo).",
    )
    parser.add_argument(
        "--no-dev-preset",
        action="store_true",
        help="No incluir los MCP de desarrollo (context7, git, chrome-devtools, etc.).",
    )
    args = parser.parse_args()

    target_dir = args.target.resolve()
    written = regenerate_configs(target_dir, enable_dev_preset=not args.no_dev_preset)

    logger.info(
        "Regeneradas %d configs MCP para %s en %s",
        len(written),
        platform.system(),
        target_dir,
    )
    for path in written:
        logger.info("  - %s", path.relative_to(target_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
