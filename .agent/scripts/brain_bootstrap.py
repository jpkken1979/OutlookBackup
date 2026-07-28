#!/usr/bin/env python3
"""
Brain Bootstrap — Inicializa un brain local en un proyecto inyectado.

Uso:
    python brain_bootstrap.py /path/to/project [--app-id mi-proyecto] [--surface project]

Cuando el MCP injector inyecta un proyecto, este script:
1. Crea la estructura brain/ en el proyecto destino
2. Registra el brain en el Mother Brain de OpenAntigravity
3. Copia el slash command /brain al proyecto

Tambien puede ejecutarse manualmente para registrar cualquier proyecto.
"""

import argparse
import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s")
logger = logging.getLogger(__name__)

_agent_dir = Path(__file__).parent.parent
if str(_agent_dir) not in sys.path:
    sys.path.insert(0, str(_agent_dir))


def bootstrap_brain(
    project_dir: str | Path,
    *,
    app_id: str = "",
    surface: str = "project",
    antigravity_root: str = "",
) -> dict[str, str]:
    """Inicializa brain local y registra en el Mother Brain.

    Args:
        project_dir: Directorio del proyecto destino.
        app_id: ID de la app (default: nombre del directorio).
        surface: Tipo de superficie.
        antigravity_root: Raiz de OpenAntigravity (para registrar en Mother Brain).

    Returns:
        Dict con paths creados y estado.
    """
    project_path = Path(project_dir).resolve()
    if not project_path.is_dir():
        return {"error": f"Directorio no existe: {project_path}"}

    # Determinar app_id si no se especifico
    if not app_id:
        app_id = project_path.name.lower().replace(" ", "-")

    brain_dir = project_path / "brain"
    result: dict[str, str] = {"app_id": app_id, "brain_dir": str(brain_dir)}

    # 1. Crear estructura brain/ en el proyecto
    from core.brain import Brain

    Brain(brain_dir, app_id=app_id)
    logger.info("Brain local creado en %s", brain_dir)
    result["brain_created"] = "true"

    # 2. Copiar slash command /brain si existe .claude/commands/
    commands_dir = project_path / ".claude" / "commands"
    if commands_dir.is_dir():
        brain_cmd_source = _agent_dir.parent / ".claude" / "commands" / "brain.md"
        brain_cmd_target = commands_dir / "brain.md"
        if brain_cmd_source.exists() and not brain_cmd_target.exists():
            brain_cmd_target.write_text(
                brain_cmd_source.read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            logger.info("Slash command /brain copiado a %s", brain_cmd_target)
            result["command_copied"] = "true"

    # 3. Registrar en el Mother Brain (si tenemos acceso)
    ag_root = Path(antigravity_root) if antigravity_root else _agent_dir.parent
    mother_registry = ag_root / ".agent" / "brain" / "network_registry.json"

    if mother_registry.parent.is_dir():
        try:
            from core.brain_network import BrainNetwork

            network = BrainNetwork(ag_root)
            network.register_app(
                app_id=app_id,
                brain_dir=brain_dir,
                description=f"Proyecto inyectado: {project_path.name}",
                surface=surface,
            )
            logger.info("Brain '%s' registrado en Mother Brain", app_id)
            result["registered_in_mother"] = "true"
        except Exception as e:
            logger.warning("No se pudo registrar en Mother Brain: %s", e)
            result["registered_in_mother"] = f"error: {e}"
    else:
        result["registered_in_mother"] = "skipped (Mother Brain no accesible)"

    # 4. Crear .gitignore entry para brain/ si no existe
    gitignore = project_path / ".gitignore"
    if gitignore.exists():
        content = gitignore.read_text(encoding="utf-8")
        if "brain/" not in content:
            with open(gitignore, "a", encoding="utf-8") as f:
                f.write("\n# Antigravity Brain (local knowledge)\n# brain/\n")

    logger.info("Bootstrap completo para '%s'", app_id)
    return result


def main() -> None:
    """CLI entry point."""
    parser = argparse.ArgumentParser(description="Bootstrap brain en proyecto")
    parser.add_argument("project_dir", help="Directorio del proyecto")
    parser.add_argument("--app-id", default="", help="ID de la app")
    parser.add_argument("--surface", default="project", help="Tipo de superficie")
    parser.add_argument("--antigravity-root", default="", help="Raiz de OpenAntigravity")
    parser.add_argument("--json", action="store_true", help="Output en JSON")
    args = parser.parse_args()

    result = bootstrap_brain(
        args.project_dir,
        app_id=args.app_id,
        surface=args.surface,
        antigravity_root=args.antigravity_root,
    )

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
    else:
        for k, v in result.items():
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
