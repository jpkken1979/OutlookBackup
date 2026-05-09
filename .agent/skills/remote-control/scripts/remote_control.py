#!/usr/bin/env python3
"""
CLI helper para gestionar el servidor MCP remoto de Antigravity.

Subcomandos disponibles:
    start   — Lanza remote-server.py con los parámetros indicados
    health  — Verifica el estado via GET /health
    config  — Genera snippet .mcp.json para configurar IDEs remotos
    token   — Genera un token seguro con secrets.token_urlsafe(32)

Uso:
    python remote_control.py start [--port 3777] [--host 0.0.0.0]
    python remote_control.py health [--url http://localhost:3777]
    python remote_control.py config [--url URL] [--token TOKEN]
    python remote_control.py token
"""

import argparse
import json
import logging
import os
import secrets
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
_SKILLS_DIR = Path(__file__).parent.parent  # .agent/skills/remote-control
_AGENT_DIR = _SKILLS_DIR.parent  # .agent/
_MCP_DIR = _AGENT_DIR / "mcp"
_REMOTE_SERVER = _MCP_DIR / "remote-server.py"

DEFAULT_PORT = 3777
DEFAULT_HOST = "0.0.0.0"
DEFAULT_BASE_URL = f"http://localhost:{DEFAULT_PORT}"


# ---------------------------------------------------------------------------
# Subcommand: token
# ---------------------------------------------------------------------------
def cmd_token(_args: argparse.Namespace) -> int:
    """Genera un token seguro con secrets.token_urlsafe(32).

    Args:
        _args: Argumentos del parser (no utilizados en este subcomando).

    Returns:
        Código de salida 0 en caso de éxito.
    """
    token = secrets.token_urlsafe(32)
    print(token)
    logger.info("Token generado (%d caracteres). Guárdalo en ANTIGRAVITY_API_TOKEN.", len(token))
    return 0


# ---------------------------------------------------------------------------
# Subcommand: health
# ---------------------------------------------------------------------------
def cmd_health(args: argparse.Namespace) -> int:
    """Verifica el estado del servidor vía GET /health.

    Args:
        args: Argumentos del parser. Usa `args.url` como base del servidor.

    Returns:
        0 si el servidor responde con estado "healthy", 1 en caso de error.
    """
    base_url = args.url.rstrip("/")
    health_url = f"{base_url}/health"

    logger.info("Verificando estado en %s ...", health_url)

    try:
        req = Request(health_url, method="GET")
        with urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
    except URLError as exc:
        logger.error("No se pudo conectar al servidor: %s", exc.reason)
        print("\n  Estado: OFFLINE\n")
        return 1
    except Exception as exc:
        logger.error("Error inesperado: %s", exc)
        return 1

    status = data.get("status", "unknown")
    agents = data.get("agents", "?")
    version = data.get("version", "?")
    auth_required = data.get("auth_required", False)
    transports = ", ".join(data.get("transports", []))

    icon = "✓" if status == "healthy" else "✗"
    print(
        f"\n  {icon} Servidor MCP Remoto de Antigravity\n"
        f"  ─────────────────────────────────────\n"
        f"  Estado:     {status}\n"
        f"  Versión:    {version}\n"
        f"  Agentes:    {agents}\n"
        f"  Auth req.:  {'Sí' if auth_required else 'No (solo desarrollo)'}\n"
        f"  Transportes: {transports}\n"
        f"  URL:        {base_url}\n"
    )

    return 0 if status == "healthy" else 1


# ---------------------------------------------------------------------------
# Subcommand: config
# ---------------------------------------------------------------------------
def cmd_config(args: argparse.Namespace) -> int:
    """Genera snippet .mcp.json para conectar un IDE remoto al servidor.

    Lee el token de args.token o de la variable de entorno ANTIGRAVITY_API_TOKEN.
    Si no hay token configurado, genera la config sin auth (solo desarrollo).

    Args:
        args: Argumentos del parser. Usa `args.url` y `args.token`.

    Returns:
        Código de salida 0 siempre.
    """
    base_url = args.url.rstrip("/")
    mcp_url = f"{base_url}/mcp"

    token: str | None = args.token or os.environ.get("ANTIGRAVITY_API_TOKEN")

    server_entry: dict = {"url": mcp_url}
    if token:
        server_entry["headers"] = {"Authorization": f"Bearer {token}"}
        logger.info("Configuración generada con autenticación Bearer.")
    else:
        logger.warning("Sin token. Configura ANTIGRAVITY_API_TOKEN para producción.")

    config = {"mcpServers": {"antigravity-remote": server_entry}}

    snippet = json.dumps(config, indent=2)
    print("\n  Pega esto en tu .mcp.json o mcp.json del IDE:\n")
    print(snippet)
    print(
        "\n  IDEs compatibles:\n"
        "    Claude Code: ~/.claude/mcp.json o .mcp.json del proyecto\n"
        "    Cursor:      ~/.cursor/mcp.json\n"
        "    Windsurf:    ~/.codeium/windsurf/mcp_config.json\n"
    )
    return 0


# ---------------------------------------------------------------------------
# Subcommand: start
# ---------------------------------------------------------------------------
def cmd_start(args: argparse.Namespace) -> int:
    """Lanza remote-server.py con los parámetros indicados.

    Usa subprocess con shell=False para cumplir con las reglas de seguridad
    del ecosistema Antigravity.

    Args:
        args: Argumentos del parser. Usa `args.port`, `args.host` y `args.home`.

    Returns:
        Código de salida del proceso hijo, o 1 si no se encuentra el servidor.
    """
    if not _REMOTE_SERVER.exists():
        logger.error(
            "No se encontró remote-server.py en %s\n"
            "Verifica que ANTIGRAVITY_HOME o la estructura del proyecto sea correcta.",
            _REMOTE_SERVER,
        )
        return 1

    cmd_parts = [
        sys.executable,
        str(_REMOTE_SERVER),
        "--port",
        str(args.port),
        "--host",
        args.host,
    ]

    if args.home:
        cmd_parts += ["--home", args.home]

    api_token = os.environ.get("ANTIGRAVITY_API_TOKEN", "")
    if not api_token:
        logger.warning(
            "ANTIGRAVITY_API_TOKEN no está definido. "
            "El servidor aceptará conexiones sin autenticación."
        )

    env = os.environ.copy()

    logger.info("Iniciando servidor: %s", shlex.join(cmd_parts))
    logger.info("Endpoints disponibles en http://%s:%d/", args.host, args.port)

    try:
        result = subprocess.run(
            cmd_parts,
            shell=False,
            env=env,
            check=False,
        )
        return result.returncode
    except FileNotFoundError:
        logger.error("Python no encontrado: %s", sys.executable)
        return 1
    except KeyboardInterrupt:
        logger.info("Servidor detenido por el usuario.")
        return 0


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    """Construye el parser de argumentos CLI.

    Returns:
        ArgumentParser configurado con todos los subcomandos.
    """
    parser = argparse.ArgumentParser(
        prog="remote_control",
        description="CLI helper para el servidor MCP remoto de Antigravity.",
    )
    sub = parser.add_subparsers(dest="command", metavar="COMMAND")
    sub.required = True

    # -- start
    p_start = sub.add_parser("start", help="Inicia el servidor MCP remoto.")
    p_start.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"Puerto de escucha (defecto: {DEFAULT_PORT}).",
    )
    p_start.add_argument(
        "--host",
        default=DEFAULT_HOST,
        help=f"Interfaz de red (defecto: {DEFAULT_HOST}).",
    )
    p_start.add_argument(
        "--home",
        default=None,
        help="Ruta base del ecosistema Antigravity (auto-detectada si no se indica).",
    )

    # -- health
    p_health = sub.add_parser("health", help="Verifica el estado del servidor.")
    p_health.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help=f"URL base del servidor (defecto: {DEFAULT_BASE_URL}).",
    )

    # -- config
    p_config = sub.add_parser("config", help="Genera snippet .mcp.json para IDE remoto.")
    p_config.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help=f"URL base del servidor (defecto: {DEFAULT_BASE_URL}).",
    )
    p_config.add_argument(
        "--token",
        default=None,
        help="Token Bearer (usa ANTIGRAVITY_API_TOKEN si no se indica).",
    )

    # -- token
    sub.add_parser("token", help="Genera un token seguro (secrets.token_urlsafe).")

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------
def main() -> None:
    """Punto de entrada del CLI helper."""
    parser = build_parser()
    args = parser.parse_args()

    handlers = {
        "start": cmd_start,
        "health": cmd_health,
        "config": cmd_config,
        "token": cmd_token,
    }

    handler = handlers.get(args.command)
    if handler is None:
        parser.print_help()
        sys.exit(1)

    sys.exit(handler(args))


if __name__ == "__main__":
    main()
