#!/usr/bin/env python3
r"""Convierte los .vscode/mcp.json de todos los proyectos al formato nativo de VS Code.

GitHub Copilot (modo Agent) exige la clave raiz "servers" + un campo "type" por
servidor + variables ${env:VAR}. El injector viejo escribia el formato
"mcpServers" (correcto para Cline/Cursor/Claude pero ignorado por Copilot), asi
que VS Code no exponia ninguna tool del ecosistema. Este script recorre los
proyectos hermanos y convierte in-place los .vscode/mcp.json afectados,
reutilizando la conversion canonica del injector (mcp_injector.mcp_config).

Es idempotente: los que ya estan en formato "servers" se dejan intactos. Tambien
limpia el prefijo extended-length \\?\ de las rutas (toxico para py.EXE).

Uso:
    python regen_vscode_mcp_all.py [--root DIR] [--apply] [--json]

Sin --apply es dry-run (no escribe nada, solo reporta).
Ver: .claude/memory/bugfix_vscode_mcp_servers_key.md
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logging.basicConfig(level=logging.INFO, format="[%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)

# Reutiliza la conversion canonica del injector (single source of truth).
_SCRIPTS_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SCRIPTS_DIR))
try:
    from mcp_injector.mcp_config import _to_vscode_server  # type: ignore
except Exception as exc:  # pragma: no cover - defensivo
    logger.error(
        "No se pudo importar mcp_injector.mcp_config (%s). Corre el script desde el "
        "ecosistema OpenAntigravity (donde vive .agent/scripts/mcp_injector/).",
        exc,
    )
    sys.exit(2)

_EXTENDED_PREFIX = "\\\\?\\"  # los 4 chars: \ \ ? \


@dataclass
class Summary:
    """Resultado agregado de la conversion."""

    converted: list[str] = field(default_factory=list)
    already_ok: list[str] = field(default_factory=list)
    no_config: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _strip_extended_prefix(value: Any) -> Any:
    r"""Elimina recursivamente el prefijo \\?\ de cualquier string anidado."""
    if isinstance(value, str):
        return value[len(_EXTENDED_PREFIX) :] if value.startswith(_EXTENDED_PREFIX) else value
    if isinstance(value, list):
        return [_strip_extended_prefix(item) for item in value]
    if isinstance(value, dict):
        return {key: _strip_extended_prefix(item) for key, item in value.items()}
    return value


def convert_config(data: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Convierte un dict de config MCP al formato nativo de VS Code.

    Args:
        data: Contenido parseado del .vscode/mcp.json.

    Returns:
        Tupla (nuevo_dict, cambio) donde `cambio` es True si hubo que convertir.
    """
    legacy = data.get("mcpServers")
    if not isinstance(legacy, dict):
        # Ya esta en formato servers (o no tiene servidores que convertir).
        if "servers" in data and "inputs" not in data:
            data = {**data, "inputs": []}
            return data, True
        return data, False

    servers: dict[str, Any] = {}
    # Preservar lo que ya hubiera bajo "servers" (merge defensivo).
    existing = data.get("servers")
    if isinstance(existing, dict):
        servers.update(existing)
    for name, cfg in legacy.items():
        servers[name] = _to_vscode_server(_strip_extended_prefix(cfg))

    new_data = {key: value for key, value in data.items() if key != "mcpServers"}
    new_data["servers"] = servers
    new_data.setdefault("inputs", [])
    return new_data, True


def process_project(project_dir: Path, apply: bool, summary: Summary) -> None:
    """Procesa el .vscode/mcp.json de un proyecto, convirtiendolo si hace falta."""
    config_path = project_dir / ".vscode" / "mcp.json"
    name = project_dir.name
    if not config_path.is_file():
        summary.no_config.append(name)
        return

    try:
        raw = config_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (json.JSONDecodeError, OSError) as exc:
        logger.error("[%s] no se pudo leer/parsear %s: %s", name, config_path, exc)
        summary.errors.append(name)
        return

    new_data, changed = convert_config(data)
    if not changed:
        summary.already_ok.append(name)
        return

    server_count = len(new_data.get("servers", {}))
    if apply:
        try:
            config_path.write_text(
                json.dumps(new_data, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        except OSError as exc:
            logger.error("[%s] no se pudo escribir: %s", name, exc)
            summary.errors.append(name)
            return
        logger.info("✅ [%s] convertido a 'servers' (%d servidores)", name, server_count)
    else:
        logger.info("• [%s] SE CONVERTIRIA a 'servers' (%d servidores)", name, server_count)
    summary.converted.append(name)


def main() -> int:
    """Punto de entrada CLI."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=_SCRIPTS_DIR.parents[2],
        help="Directorio que contiene los proyectos hermanos (default: el parent del repo del ecosistema).",
    )
    parser.add_argument(
        "--apply", action="store_true", help="Escribir cambios (sin esto, dry-run)."
    )
    parser.add_argument("--json", action="store_true", help="Salida JSON.")
    args = parser.parse_args()

    root: Path = args.root.resolve()
    if not root.is_dir():
        logger.error("root no existe o no es directorio: %s", root)
        return 2

    logger.info("Escaneando proyectos en: %s  (%s)", root, "APPLY" if args.apply else "dry-run")
    summary = Summary()
    for child in sorted(p for p in root.iterdir() if p.is_dir()):
        process_project(child, args.apply, summary)

    if args.json:
        print(json.dumps(summary.__dict__, indent=2, ensure_ascii=False))
    else:
        logger.info("-" * 50)
        logger.info("Convertidos:   %d  %s", len(summary.converted), summary.converted or "")
        logger.info("Ya correctos:  %d", len(summary.already_ok))
        logger.info("Sin .vscode/mcp.json: %d", len(summary.no_config))
        logger.info("Errores:       %d  %s", len(summary.errors), summary.errors or "")
        if not args.apply and summary.converted:
            logger.info("Dry-run. Volve a correr con --apply para escribir los cambios.")

    return 1 if summary.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
