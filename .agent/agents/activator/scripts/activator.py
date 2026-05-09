#!/usr/bin/env python3
"""
Antigravity Activator
=====================
Activa el ecosistema Antigravity en cualquier repositorio.

Uso:
    python activator.py                    # Activa en directorio actual
    python activator.py /path/to/project   # Activa en proyecto especifico
    python activator.py --check            # Solo verifica sin modificar
    python activator.py --uninstall        # Desactiva

Ejemplo:
    cd /mi/otro/proyecto
    python /ruta/a/AntigravitiSkillUSN/.agent/agents/activator/scripts/activator.py
"""

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class ActivationResult:
    """Resultado de la activacion."""

    status: str  # activated, already_active, failed, checked
    mcp_server_path: str
    settings_path: str
    agents_count: int
    tools_available: list[str]
    message: str
    antigravity_path: str

    def to_dict(self) -> dict:
        return asdict(self)


class Activator:
    """Activador del ecosistema Antigravity."""

    # Rutas donde buscar Antigravity
    SEARCH_PATHS = [
        # Relativo al script
        Path(__file__).parent.parent.parent.parent.parent,  # Desde scripts/activator.py
        # Rutas comunes
        Path.home() / "AntigravitiSkillUSN",
        Path.home() / "antigravity-agents",
        Path.home() / "projects" / "AntigravitiSkillUSN",
        Path.home() / "code" / "AntigravitiSkillUSN",
        Path("/opt/antigravity-agents"),
        # Variables de entorno
    ]

    MCP_TOOLS = [
        "list_agents",
        "execute_agent",
        "find_best_agent",
        "get_agent_info",
        "get_costs",
        "get_history",
    ]

    def __init__(self, target_dir: Path | None = None):
        self.target_dir = Path(target_dir) if target_dir else Path.cwd()
        self.antigravity_path: Path | None = None

    def find_antigravity(self) -> Path | None:
        """Encuentra la instalacion de Antigravity."""
        # Check environment variable first
        env_path = os.environ.get("ANTIGRAVITY_PATH")
        if env_path:
            path = Path(env_path)
            if self._is_valid_antigravity(path):
                return path

        # Search in common locations
        for search_path in self.SEARCH_PATHS:
            if self._is_valid_antigravity(search_path):
                return search_path

        # Search parent directories (for submodule usage)
        current = self.target_dir
        for _ in range(5):  # Max 5 levels up
            for subdir in [".antigravity", "antigravity", "AntigravitiSkillUSN"]:
                candidate = current / subdir
                if self._is_valid_antigravity(candidate):
                    return candidate
            current = current.parent

        return None

    def _is_valid_antigravity(self, path: Path) -> bool:
        """Verifica si es una instalacion valida de Antigravity."""
        if not path.exists():
            return False

        # At least need the v2 server or v1 server
        mcp_v2 = path / ".agent" / "mcp" / "agents-server-v2.py"
        mcp_v1 = path / ".agent" / "mcp" / "agents-server.py"
        agents_dir = path / ".agent" / "agents"

        return agents_dir.exists() and (mcp_v2.exists() or mcp_v1.exists())

    def count_agents(self) -> int:
        """Cuenta los agentes disponibles."""
        if not self.antigravity_path:
            return 0

        agents_dir = self.antigravity_path / ".agent" / "agents"
        if not agents_dir.exists():
            return 0

        count = 0
        for agent_dir in agents_dir.iterdir():
            if agent_dir.is_dir() and agent_dir.name != "_planned":
                identity = agent_dir / "IDENTITY.md"
                if identity.exists():
                    count += 1

        return count

    def get_mcp_server_path(self) -> Path:
        """Obtiene la ruta al MCP server."""
        if not self.antigravity_path:
            raise ValueError("Antigravity not found")

        # Prefer v2
        v2_path = self.antigravity_path / ".agent" / "mcp" / "agents-server-v2.py"
        if v2_path.exists():
            return v2_path

        # Fallback to v1
        v1_path = self.antigravity_path / ".agent" / "mcp" / "agents-server.py"
        if v1_path.exists():
            return v1_path

        raise ValueError("No MCP server found")

    def create_settings(self) -> Path:
        """Crea configuracion MCP para todos los IDEs soportados."""
        mcp_server = self.get_mcp_server_path()
        agents_count = self.count_agents()
        mcp_server_str = str(mcp_server.absolute())

        # Standard MCP config (Claude Code, Cursor, Windsurf)
        mcp_config = {
            "mcpServers": {
                "antigravity-agents": {
                    "command": "python",
                    "args": [mcp_server_str],
                    "description": f"Antigravity Agents ({agents_count} agentes disponibles)",
                }
            }
        }

        # Zed uses a different format
        zed_config = {
            "context_servers": {
                "antigravity-agents": {
                    "command": {"path": "python", "args": [mcp_server_str]},
                    "settings": {},
                }
            }
        }

        def _write_json(path: Path, data: dict) -> None:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

        # 1. .mcp.json (Claude Code - project root)
        mcp_json_path = self.target_dir / ".mcp.json"
        _write_json(mcp_json_path, mcp_config)

        # 2. .cursor/mcp.json (Cursor)
        _write_json(self.target_dir / ".cursor" / "mcp.json", mcp_config)

        # 3. .windsurf/mcp.json (Windsurf)
        _write_json(self.target_dir / ".windsurf" / "mcp.json", mcp_config)

        # 4. .zed/settings.json (Zed - merge with existing)
        zed_path = self.target_dir / ".zed" / "settings.json"
        if zed_path.exists():
            try:
                existing_zed = json.loads(zed_path.read_text(encoding="utf-8"))
                existing_zed["context_servers"] = zed_config["context_servers"]
                zed_config = existing_zed
            except json.JSONDecodeError:
                pass
        _write_json(zed_path, zed_config)

        # 5. .claude/settings.json (legacy + metadata)
        settings_path = self.target_dir / ".claude" / "settings.json"
        if settings_path.exists():
            try:
                existing = json.loads(settings_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                existing = {}
        else:
            existing = {}

        if "mcpServers" not in existing:
            existing["mcpServers"] = {}

        existing["mcpServers"]["antigravity-agents"] = mcp_config["mcpServers"][
            "antigravity-agents"
        ]

        existing["_antigravity"] = {
            "version": "2.1.0",
            "path": str(self.antigravity_path.absolute()),
            "activated_from": str(Path(__file__).absolute()),
            "ide_configs_created": [
                ".mcp.json",
                ".cursor/mcp.json",
                ".windsurf/mcp.json",
                ".zed/settings.json",
            ],
        }

        _write_json(settings_path, existing)

        return settings_path

    def verify_installation(self) -> bool:
        """Verifica que el MCP server responda."""
        try:
            mcp_server = self.get_mcp_server_path()

            # Send a test request
            test_request = '{"jsonrpc":"2.0","method":"tools/list","id":1}'

            result = subprocess.run(
                [sys.executable, str(mcp_server)],
                input=test_request,
                capture_output=True,
                text=True,
                timeout=10,
            )

            if result.stdout:
                response = json.loads(result.stdout.strip().split("\n")[0])
                return "result" in response and "tools" in response.get("result", {})

        except Exception:
            pass

        return False

    def activate(self, verify: bool = True) -> ActivationResult:
        """Activa Antigravity en el directorio target."""
        # Find Antigravity
        self.antigravity_path = self.find_antigravity()

        if not self.antigravity_path:
            return ActivationResult(
                status="failed",
                mcp_server_path="",
                settings_path="",
                agents_count=0,
                tools_available=[],
                message="No se encontro instalacion de Antigravity. "
                "Configura ANTIGRAVITY_PATH o clona el repositorio.",
                antigravity_path="",
            )

        try:
            # Create settings
            settings_path = self.create_settings()
            mcp_server = self.get_mcp_server_path()
            agents_count = self.count_agents()

            # Verify if requested
            verified = self.verify_installation() if verify else True

            if not verified:
                return ActivationResult(
                    status="warning",
                    mcp_server_path=str(mcp_server),
                    settings_path=str(settings_path),
                    agents_count=agents_count,
                    tools_available=self.MCP_TOOLS,
                    message="Configurado pero verificacion fallo. "
                    "El MCP server puede no responder correctamente.",
                    antigravity_path=str(self.antigravity_path),
                )

            return ActivationResult(
                status="activated",
                mcp_server_path=str(mcp_server),
                settings_path=str(settings_path),
                agents_count=agents_count,
                tools_available=self.MCP_TOOLS,
                message=f"Antigravity activado! {agents_count} agentes disponibles en "
                f"Claude Code, Cursor, Windsurf y Zed. Reinicia tu IDE.",
                antigravity_path=str(self.antigravity_path),
            )

        except Exception as e:
            return ActivationResult(
                status="failed",
                mcp_server_path="",
                settings_path="",
                agents_count=0,
                tools_available=[],
                message=f"Error durante activacion: {str(e)}",
                antigravity_path=str(self.antigravity_path) if self.antigravity_path else "",
            )

    def check(self) -> ActivationResult:
        """Verifica el estado actual sin modificar."""
        # Check .mcp.json first (Claude Code), then fall back to .claude/settings.json
        mcp_json_path = self.target_dir / ".mcp.json"
        settings_path = self.target_dir / ".claude" / "settings.json"

        config_path = mcp_json_path if mcp_json_path.exists() else settings_path

        if not config_path.exists():
            return ActivationResult(
                status="not_configured",
                mcp_server_path="",
                settings_path=str(config_path),
                agents_count=0,
                tools_available=[],
                message="Antigravity no esta configurado en este proyecto.",
                antigravity_path="",
            )

        try:
            settings = json.loads(config_path.read_text(encoding="utf-8"))
            mcp_config = settings.get("mcpServers", {}).get("antigravity-agents", {})

            if not mcp_config:
                return ActivationResult(
                    status="not_configured",
                    mcp_server_path="",
                    settings_path=str(settings_path),
                    agents_count=0,
                    tools_available=[],
                    message="settings.json existe pero no tiene configuracion de Antigravity.",
                    antigravity_path="",
                )

            mcp_args = mcp_config.get("args", [])
            mcp_server = mcp_args[0] if mcp_args else ""

            # Try to find antigravity path from config
            antigravity_info = settings.get("_antigravity", {})
            self.antigravity_path = (
                Path(antigravity_info.get("path", "")) if antigravity_info else None
            )

            if not self.antigravity_path or not self.antigravity_path.exists():
                # Try to infer from MCP path
                if mcp_server:
                    mcp_path = Path(mcp_server)
                    if mcp_path.exists():
                        self.antigravity_path = mcp_path.parent.parent.parent

            agents_count = self.count_agents() if self.antigravity_path else 0

            return ActivationResult(
                status="active",
                mcp_server_path=mcp_server,
                settings_path=str(settings_path),
                agents_count=agents_count,
                tools_available=self.MCP_TOOLS,
                message=f"Antigravity esta activo con {agents_count} agentes.",
                antigravity_path=str(self.antigravity_path) if self.antigravity_path else "",
            )

        except json.JSONDecodeError:
            return ActivationResult(
                status="error",
                mcp_server_path="",
                settings_path=str(settings_path),
                agents_count=0,
                tools_available=[],
                message="settings.json tiene formato invalido.",
                antigravity_path="",
            )

    def uninstall(self) -> ActivationResult:
        """Desactiva Antigravity del proyecto (limpia todos los IDE configs)."""
        settings_path = self.target_dir / ".claude" / "settings.json"
        mcp_json_path = self.target_dir / ".mcp.json"

        has_any_config = settings_path.exists() or mcp_json_path.exists()

        if not has_any_config:
            return ActivationResult(
                status="not_configured",
                mcp_server_path="",
                settings_path="",
                agents_count=0,
                tools_available=[],
                message="No hay nada que desactivar.",
                antigravity_path="",
            )

        try:
            # Remove .mcp.json (Claude Code)
            if mcp_json_path.exists():
                mcp_json_path.unlink()

            # Remove .cursor/mcp.json
            cursor_mcp = self.target_dir / ".cursor" / "mcp.json"
            if cursor_mcp.exists():
                cursor_mcp.unlink()

            # Remove .windsurf/mcp.json
            windsurf_mcp = self.target_dir / ".windsurf" / "mcp.json"
            if windsurf_mcp.exists():
                windsurf_mcp.unlink()

            # Clean .zed/settings.json (remove only context_servers key)
            zed_settings = self.target_dir / ".zed" / "settings.json"
            if zed_settings.exists():
                try:
                    zed_data = json.loads(zed_settings.read_text(encoding="utf-8"))
                    if (
                        "context_servers" in zed_data
                        and "antigravity-agents" in zed_data["context_servers"]
                    ):
                        del zed_data["context_servers"]["antigravity-agents"]
                        if not zed_data["context_servers"]:
                            del zed_data["context_servers"]
                        if zed_data:
                            zed_settings.write_text(
                                json.dumps(zed_data, indent=2, ensure_ascii=False), encoding="utf-8"
                            )
                        else:
                            zed_settings.unlink()
                except (json.JSONDecodeError, KeyError):
                    pass

            # Clean .claude/settings.json
            if settings_path.exists():
                settings = json.loads(settings_path.read_text(encoding="utf-8"))

                if "mcpServers" in settings and "antigravity-agents" in settings["mcpServers"]:
                    del settings["mcpServers"]["antigravity-agents"]

                if "_antigravity" in settings:
                    del settings["_antigravity"]

                settings_path.write_text(
                    json.dumps(settings, indent=2, ensure_ascii=False), encoding="utf-8"
                )

            return ActivationResult(
                status="deactivated",
                mcp_server_path="",
                settings_path=str(settings_path),
                agents_count=0,
                tools_available=[],
                message="Antigravity desactivado de todos los IDEs. Reinicia tu IDE.",
                antigravity_path="",
            )

        except Exception as e:
            return ActivationResult(
                status="error",
                mcp_server_path="",
                settings_path=str(settings_path),
                agents_count=0,
                tools_available=[],
                message=f"Error durante desactivacion: {str(e)}",
                antigravity_path="",
            )


def print_result(result: ActivationResult, as_json: bool = False):
    """Imprime el resultado de forma legible."""
    if as_json:
        print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))
        return

    status_icons = {
        "activated": "✓",
        "active": "✓",
        "warning": "⚠",
        "failed": "✗",
        "error": "✗",
        "not_configured": "○",
        "deactivated": "○",
        "checked": "i",
    }

    icon = status_icons.get(result.status, "?")
    print(f"\n[{icon}] {result.status.upper()}: {result.message}")

    if result.antigravity_path:
        print(f"\n  Antigravity: {result.antigravity_path}")
    if result.mcp_server_path:
        print(f"  MCP Server:  {result.mcp_server_path}")
    if result.settings_path:
        print(f"  Settings:    {result.settings_path}")
    if result.agents_count:
        print(f"  Agentes:     {result.agents_count}")
    if result.tools_available:
        print(f"  Tools:       {', '.join(result.tools_available)}")

    print()


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Activa Antigravity Agents en cualquier proyecto",
        epilog="Ejemplo: python activator.py /mi/proyecto",
    )
    parser.add_argument(
        "target", nargs="?", default=".", help="Directorio del proyecto (default: actual)"
    )
    parser.add_argument("--check", action="store_true", help="Solo verificar estado, no modificar")
    parser.add_argument(
        "--uninstall", action="store_true", help="Desactivar Antigravity del proyecto"
    )
    parser.add_argument("--json", action="store_true", help="Output en formato JSON")
    parser.add_argument("--no-verify", action="store_true", help="No verificar que el MCP responda")

    args = parser.parse_args()

    target = Path(args.target).resolve()
    if not target.exists():
        print(f"Error: El directorio '{target}' no existe")
        sys.exit(1)

    activator = Activator(target)

    if args.check:
        result = activator.check()
    elif args.uninstall:
        result = activator.uninstall()
    else:
        result = activator.activate(verify=not args.no_verify)

    print_result(result, as_json=args.json)

    # Exit code
    if result.status in ["activated", "active", "deactivated"]:
        sys.exit(0)
    elif result.status == "warning":
        sys.exit(0)  # Still success, just with warning
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
