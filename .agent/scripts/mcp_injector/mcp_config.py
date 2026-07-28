"""Configuracion MCP — funciones de configuracion extraidas de mcp_injector.py.

Este modulo es semi-autonomo: las utilidades de I/O, paths y constantes se importan
de los modulos hermanos (io_utils, path_utils, constants). Si se usa fuera del
paquete mcp_injector, esas dependencias deben satisfacerse o re-definirse.

Funciones extraidas:
    _server_contains_missing_local_path, prune_invalid_local_mcp_servers,
    get_mcp_servers, maybe_add_remote_server, safe_merge_json,
    safe_merge_vscode_mcp, safe_merge_zed_settings, safe_merge_continue_json,
    install_antigravity_config, collect_runtime_fingerprint,
    install_claude_settings, install_ai_manifest, install_gemini_config,
    install_aider_config, get_agent_version, _parse_version,
    should_update_agent, show_injection_diff, check_blocking_processes.
"""

from __future__ import annotations

import json
import logging
import os
import platform
import re
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Imports del paquete mcp_injector
# ---------------------------------------------------------------------------
from .constants import (
    DEFAULT_GATEWAY_URL,
    DEFAULT_MEMORY_BACKEND,
    DEFAULT_ORCHESTRATOR_MODE,
    DEFAULT_REGISTRY_CACHE_TTL_SECONDS,
    DEFAULT_REGISTRY_MODE,
    ECOSYSTEM_VERSION,
    HOOK_RUNTIME_FILES,
    REMOTE_TOKEN_PLACEHOLDER,
)
from .io_utils import (
    _make_portable_paths,
    copy_file,
    deep_merge,
    ensure_dir,
    hash_file,
    normalize_path,
    read_json_file,
    write_json_file,
)
from .path_utils import (
    is_remote_gateway_url,
    runtime_roots,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Constants (private, module-level)
# ---------------------------------------------------------------------------
BLOCKING_PROCESSES = [
    "Claude",
    "claude",
    "KiloCode",
    "Cursor",
    "cursor",
    "Code",
    "windsurf",
    "Zed",
    "Continue",
]

# Entries produced by historical injector versions. Migration removes only
# these names; unknown/user-managed servers are preserved byte-for-byte.
LEGACY_MANAGED_MCP_SERVER_NAMES: frozenset[str] = frozenset(
    {
        "antigravity",
        "antigravity-agents",
        "antigravity-skills",
        "antigravity-observations",
        "antigravity-intelligence",
        "antigravity-ui",
        "antigravity-memory",
        "antigravity-brain",
        "antigravity-excel",
        "antigravity-delta-reader",
        "antigravity-provider",
        "antigravity-watcher",
        "antigravity-context-engine",
        "antigravity-brain-graph",
        "antigravity-shu-discord",
        "antigravity-shu-github",
        "antigravity-shu-slack",
        "antigravity-shu-webhook",
        "antigravity-shu-webhooks",
        "antigravity-remote",
        "jpkkenfull",
        "deepwiki",
        "notebooklm-mcp",
        "context7",
        "git",
        "chrome-devtools",
        "magic-21st",
        "sqlite",
        "filesystem",
    }
)


def _migrate_managed_servers(
    current_servers: dict[str, Any],
    new_servers: dict[str, Any],
) -> tuple[dict[str, Any], list[str]]:
    """Drop historical managed entries when installing the broker-only profile."""

    if set(new_servers) != {"antigravity"}:
        return current_servers, []
    removed = [
        name
        for name in current_servers
        if name in LEGACY_MANAGED_MCP_SERVER_NAMES and name != "antigravity"
    ]
    migrated = {
        name: value
        for name, value in current_servers.items()
        if name not in LEGACY_MANAGED_MCP_SERVER_NAMES or name == "antigravity"
    }
    return migrated, sorted(removed)


def _is_legacy_managed_transport(server: dict[str, Any]) -> bool:
    """Identify anonymous Continue entries produced by old injector versions."""

    transport = server.get("transport")
    if not isinstance(transport, dict):
        return False
    serialized = json.dumps(
        {
            "command": transport.get("command"),
            "args": transport.get("args", []),
        },
        ensure_ascii=True,
    ).lower()
    markers = (
        "/.agent/mcp/",
        "\\\\.agent\\\\mcp\\\\",
        "/mcp-server/server.py",
        "\\\\mcp-server\\\\server.py",
        "mcp.broker.stdio_proxy",
        "core.mcp_stdio_proxy",
        "@upstash/context7-mcp",
        "chrome-devtools-mcp",
        "@21st-dev/magic",
        "mcp-server-git",
        "mcp-server-sqlite",
        "@modelcontextprotocol/server-filesystem",
    )
    return any(marker in serialized for marker in markers)


# ---------------------------------------------------------------------------
# Helpers locales (usan solo stdlib)
# ---------------------------------------------------------------------------


def _is_absolute_local_path(value: str) -> bool:
    """Detecta rutas absolutas locales Windows/POSIX."""
    if not value:
        return False
    return bool(re.match(r"^[a-zA-Z]:[\\/]", value)) or value.startswith(("/", "\\\\"))


def _strip_extended_length_prefix(value: Any) -> Any:
    """Normaliza el prefijo extendido de Windows (``\\\\?\\``) en paths.

    El prefijo ``\\\\?\\`` (extended-length path) hace que ``\\\\?\\C:\\x`` y
    ``C:\\x`` se traten como distintos al dedupear, generando entradas fantasma
    al re-inyectar. Se aplica recursivamente a strings, listas y dicts.

    Args:
        value: String, lista o dict potencialmente con paths prefijados.

    Returns:
        El mismo valor con todo ``\\\\?\\`` inicial removido de sus strings.
    """
    if isinstance(value, str):
        return value[4:] if value.startswith("\\\\?\\") else value
    if isinstance(value, list):
        return [_strip_extended_length_prefix(item) for item in value]
    if isinstance(value, dict):
        return {key: _strip_extended_length_prefix(item) for key, item in value.items()}
    return value


def force_utf8_python_command(command: str) -> str:
    """Fuerza `-X utf8` en comandos Python de hooks sin alterar otros comandos."""
    normalized = command.strip()
    if not normalized:
        return command

    if re.match(r"^(python|python3|py)\s+-X\s+utf8(\s|$)", normalized):
        return command

    for prefix in ("python ", "python3 ", "py "):
        if normalized.startswith(prefix):
            return command.replace(prefix, f"{prefix.strip()} -X utf8 ", 1)

    return command


def normalize_hook_python_commands(settings: dict[str, Any]) -> int:
    """Normaliza comandos Python en hooks para ejecutar siempre en UTF-8."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        return 0

    updated = 0
    for entries in hooks.values():
        if not isinstance(entries, list):
            continue
        for entry in entries:
            if not isinstance(entry, dict):
                continue
            hook_items = entry.get("hooks")
            if not isinstance(hook_items, list):
                continue
            for hook in hook_items:
                if not isinstance(hook, dict):
                    continue
                command = hook.get("command")
                if not isinstance(command, str):
                    continue
                normalized = force_utf8_python_command(command)
                if normalized != command:
                    hook["command"] = normalized
                    updated += 1
    return updated


def sanitize_claude_settings(settings: dict[str, Any]) -> dict[str, Any]:
    """Elimina configuracion legacy/local-heavy que no debe quedar activa."""
    hooks = settings.get("hooks")
    if not isinstance(hooks, dict):
        hooks = {}
        settings["hooks"] = hooks

    stop_hooks = hooks.get("Stop")
    if isinstance(stop_hooks, list):
        filtered_stop_hooks: list[dict[str, Any]] = []
        for entry in stop_hooks:
            if not isinstance(entry, dict):
                filtered_stop_hooks.append(entry)
                continue

            hook_items = entry.get("hooks")
            if not isinstance(hook_items, list):
                filtered_stop_hooks.append(entry)
                continue

            remaining_items = []
            for hook in hook_items:
                if not isinstance(hook, dict):
                    remaining_items.append(hook)
                    continue

                command = hook.get("command")
                if isinstance(command, str) and "memory_autosave_hook.py" in command:
                    continue
                remaining_items.append(hook)

            if remaining_items:
                new_entry = dict(entry)
                new_entry["hooks"] = remaining_items
                filtered_stop_hooks.append(new_entry)

        hooks["Stop"] = filtered_stop_hooks

    settings.pop("skills", None)
    settings.pop("agents", None)
    settings.pop("commands", None)
    settings.pop("memory", None)

    context = settings.get("context")
    if not isinstance(context, dict):
        context = {}
    context["autoInject"] = [".claude/rules/*.md"]
    context["maxTokens"] = min(int(context.get("maxTokens", 24000)), 24000)
    settings["context"] = context
    normalized_commands = normalize_hook_python_commands(settings)
    if normalized_commands:
        logger.info(f"✅ [.claude/settings] {normalized_commands} hooks normalizados a UTF-8")
    return settings


# ---------------------------------------------------------------------------
# Server validation
# ---------------------------------------------------------------------------


def _server_contains_missing_local_path(server: dict[str, Any]) -> bool:
    """True si el server referencia una ruta local absoluta que ya no existe."""
    command = server.get("command")
    args = server.get("args", [])
    candidates: list[str] = []

    if isinstance(command, str):
        candidates.append(command)
    elif isinstance(command, dict):
        command_path = command.get("path")
        if isinstance(command_path, str):
            candidates.append(command_path)
        command_args = command.get("args")
        if isinstance(command_args, list):
            candidates.extend(str(arg) for arg in command_args if isinstance(arg, str))
    if isinstance(args, list):
        candidates.extend(str(arg) for arg in args if isinstance(arg, str))

    for candidate in candidates:
        if not _is_absolute_local_path(candidate):
            continue
        if candidate.startswith("\\\\"):
            continue
        if not Path(candidate).exists():
            return True
    return False


_DISABLED_MCP_SERVERS = {"stitch"}


def prune_invalid_local_mcp_servers(servers: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Elimina servidores MCP desactivados o con rutas locales absolutas inexistentes."""
    cleaned: dict[str, Any] = {}
    removed: list[str] = []

    for name, server in servers.items():
        if name in _DISABLED_MCP_SERVERS:
            removed.append(name)
            continue
        if not isinstance(server, dict):
            cleaned[name] = server
            continue
        if _server_contains_missing_local_path(server):
            removed.append(name)
            continue
        cleaned[name] = server

    return cleaned, removed


# ---------------------------------------------------------------------------
# Remote server helper
# ---------------------------------------------------------------------------


def maybe_add_remote_server(
    servers: dict[str, Any],
    gateway_url: str = "",
    token: str = "",
) -> dict[str, Any]:
    """Agrega el servidor MCP remoto cuando exista URL/token configurados."""
    if not is_remote_gateway_url(gateway_url):
        return servers

    remote_url = gateway_url.rstrip("/")
    if not remote_url.endswith("/mcp"):
        remote_url = f"{remote_url}/mcp"

    remote_server: dict[str, Any] = {
        "type": "http",
        "url": remote_url,
    }
    if token:
        remote_server["headers"] = {"Authorization": f"Bearer {token}"}
    else:
        remote_server["headers"] = {"Authorization": f"Bearer {REMOTE_TOKEN_PLACEHOLDER}"}

    servers["antigravity-remote"] = remote_server
    return servers


# ---------------------------------------------------------------------------
# MCP servers factory
# ---------------------------------------------------------------------------


def _resolve_mcp_interpreter(is_windows: bool) -> str:
    """Ruta absoluta del interprete Python para los MCP servers.

    Claude Code spawnea los subprocesos MCP con un PATH minimo, por eso el
    interprete se resuelve a ruta absoluta en tiempo de generacion en vez de
    confiar en que 'py'/'python3' esten en el PATH del subproceso.
    Ver .claude/memory/bugfix_mcp_path_2026_05_15.md.
    """
    if is_windows:
        found = shutil.which("py") or shutil.which("python")
        if found:
            return found
        for candidate in (r"C:\Windows\py.exe", r"C:\Windows\System32\py.exe"):
            if Path(candidate).is_file():
                return candidate
        # El interprete que corre el injector existe con certeza. Sin esto, en un
        # PATH minimo (el de Claude Code) se escribia el literal "py" y el server
        # MCP del target no arrancaba nunca: FileNotFoundError en el smoke
        # post-inyeccion. Verificado 2026-07-27 — esta maquina no tiene py.exe.
        if sys.executable:
            return sys.executable
        return "py"
    found = shutil.which("python3") or shutil.which("python")
    if found:
        return found
    for candidate in ("/opt/homebrew/bin/python3", "/usr/local/bin/python3", "/usr/bin/python3"):
        if Path(candidate).is_file():
            return candidate
    if sys.executable:
        return sys.executable
    return "python3"


def _resolve_shell_launcher(is_windows: bool) -> str:
    """Launcher de shell absoluto para envolver npx/uvx en Windows."""
    if is_windows:
        return shutil.which("cmd") or r"C:\Windows\System32\cmd.exe"
    return shutil.which("sh") or "/bin/sh"


def _resolve_node_bin(name: str, is_windows: bool) -> str:
    """Ruta absoluta de un binario tipo npx/uvx con fallback al nombre simple."""
    found = shutil.which(name)
    if found:
        return found
    if not is_windows:
        for base in ("/usr/local/bin", "/opt/homebrew/bin", str(Path.home() / ".local" / "bin")):
            candidate = Path(base) / name
            if candidate.is_file():
                return str(candidate)
    return name


def mcp_runtime_path_env(is_windows: bool) -> str:
    """PATH explicito para inyectar en el env de cada MCP server.

    Compensa el PATH minimo con que Claude Code spawnea los subprocesos. Se
    construye dinamicamente desde el HOME del usuario, sin hardcodear el nombre
    de usuario (a diferencia del fix manual previo en .mcp.json).
    """
    home = Path.home()
    if is_windows:
        parts = [
            r"C:\Windows",
            r"C:\Windows\System32",
            r"C:\Program Files\nodejs",
            str(home / ".local" / "bin"),
            r"C:\Program Files\Git\cmd",
        ]
    else:
        parts = [
            "/usr/local/bin",
            "/opt/homebrew/bin",
            "/usr/bin",
            "/bin",
            "/usr/sbin",
            "/sbin",
            str(home / ".local" / "bin"),
        ]
    return os.pathsep.join(parts)


def get_mcp_servers(
    repo_root: Path,
    target_dir: Path | None = None,
    enable_dev_preset: bool = True,
    gateway_url: str = "",
    token: str = "",
    legacy_profile: bool = False,
) -> dict[str, Any]:
    """Generate the single broker entry, or the opt-in legacy profile."""
    legacy_profile = legacy_profile or os.environ.get(
        "ANTIGRAVITY_MCP_LEGACY_PROFILE", ""
    ).strip().lower() in {"1", "true", "yes", "on"}

    if not legacy_profile:
        is_windows = platform.system() == "Windows"
        _mcp_root, agent_root = runtime_roots(repo_root, target_dir)
        # Project-scoped MCP configs are launched from the workspace root.
        # Relative values remain portable and avoid unsupported self-references
        # such as ANTIGRAVITY_ROOT=${ANTIGRAVITY_ROOT}.
        root_path = "." if target_dir is not None else normalize_path(agent_root.parent)
        python_path = ".agent" if target_dir is not None else normalize_path(agent_root)
        broker_url = (gateway_url or DEFAULT_GATEWAY_URL).rstrip("/")
        if not broker_url.endswith("/mcp"):
            broker_url = f"{broker_url}/mcp"

        executable_name = "antigravity-mcp.exe" if is_windows else "antigravity-mcp"
        runtime_root = (target_dir or repo_root) / ".antigravity" / "runtime" / "current"
        portable_executable = next(
            (
                candidate
                for candidate in (
                    runtime_root / "antigravity-mcp" / executable_name,
                    runtime_root / executable_name,
                )
                if candidate.is_file()
            ),
            None,
        )
        if portable_executable is not None:
            broker = {
                "command": normalize_path(portable_executable),
                "args": [],
                "env": {
                    "ANTIGRAVITY_ROOT": root_path,
                    "ANTIGRAVITY_MCP_URL": broker_url,
                },
            }
        else:
            # Source-mode fallback for development. Release bundles replace this
            # with the frozen executable above and therefore need no host Python.
            # El `.venv` del TARGET queda fuera a proposito: es el entorno del
            # proyecto, no el del ecosistema, y no tiene por que traer las deps
            # del shim. Chingiv7 tiene `.venv` sin `cryptography`, asi que
            # `read_session_key()` fallaba, el token salia vacio y el broker
            # respondia 401 AUTH_REQUIRED (2026-07-28). Kintai funciono solo
            # porque no tiene `.venv` y caia al interprete del repo fuente.
            #
            # Si vale el runtime portable del target: ese SI es del ecosistema.
            runtime_rel = ("python", "python.exe") if is_windows else ("python", "bin", "python3")
            venv_rel = ("Scripts", "python.exe") if is_windows else ("bin", "python3")

            private_python_candidates = []
            if target_dir is not None:
                private_python_candidates.append(
                    target_dir.joinpath(".antigravity", "runtime", "current", *runtime_rel)
                )
            private_python_candidates.extend(
                [
                    repo_root.joinpath(".antigravity", "runtime", "current", *runtime_rel),
                    repo_root.joinpath(".venv", *venv_rel),
                ]
            )
            source_python = next(
                (path for path in private_python_candidates if path.is_file()),
                None,
            )
            broker = {
                "command": (
                    normalize_path(source_python)
                    if source_python is not None
                    else _resolve_mcp_interpreter(is_windows)
                ),
                "args": ["-m", "core.mcp_stdio_proxy"],
                "env": {
                    "ANTIGRAVITY_ROOT": root_path,
                    "ANTIGRAVITY_MCP_URL": broker_url,
                    "PYTHONPATH": python_path,
                },
            }

        if token:
            logger.warning(
                "Ignoring plaintext MCP token; Nexus must provide it from the secure credential store"
            )
        if enable_dev_preset:
            logger.info(
                "MCP dev connectors are catalog entries and will start lazily through antigravity"
            )
        return {"antigravity": broker}

    logger.warning("Using opt-in legacy MCP profile with individual server processes")
    if enable_dev_preset and shutil.which("npx") is None:
        logger.warning(
            "⚠️  [MCP npm] 'npx' no esta disponible. Se configuraran igualmente los MCP npm."
        )
    if enable_dev_preset and shutil.which("uvx") is None:
        logger.warning(
            "⚠️  [MCP git] 'uvx' no esta disponible. Se configurara igualmente el MCP git."
        )

    is_windows = platform.system() == "Windows"
    mcp_root, agent_root = runtime_roots(repo_root, target_dir)
    root_path = normalize_path(agent_root.parent)

    py_bin = _resolve_mcp_interpreter(is_windows)
    shell_bin = _resolve_shell_launcher(is_windows)
    npx_bin = _resolve_node_bin("npx", is_windows)
    uvx_bin = _resolve_node_bin("uvx", is_windows)
    path_env = mcp_runtime_path_env(is_windows)
    persona = os.environ.get("ANTIGRAVITY_PERSONA", "gentleman")

    def base_env(extra: dict[str, str] | None = None) -> dict[str, str]:
        env = {"PATH": path_env, "ANTIGRAVITY_PERSONA": persona}
        if extra:
            env.update(extra)
        return env

    def npx_server(args: list[str], extra_env: dict[str, str] | None = None) -> dict[str, Any]:
        env = {"PATH": path_env}
        if extra_env:
            env.update(extra_env)
        if is_windows:
            return {"command": shell_bin, "args": ["/c", "npx", *args], "env": env}
        return {"command": npx_bin, "args": args, "env": env}

    def uvx_server(args: list[str]) -> dict[str, Any]:
        if is_windows:
            return {"command": shell_bin, "args": ["/c", "uvx", *args], "env": {"PATH": path_env}}
        return {"command": uvx_bin, "args": args, "env": {"PATH": path_env}}

    def python_server(script_path: Path, extra_env: dict[str, str] | None = None) -> dict[str, Any]:
        """Interprete absoluto + PATH explicito (ver bugfix_mcp_path_2026_05_15.md)."""
        return {
            "command": py_bin,
            "args": [normalize_path(script_path)],
            "env": base_env(extra_env),
        }

    servers: dict[str, Any] = {
        "deepwiki": {"type": "http", "url": "https://mcp.deepwiki.com/mcp"},
        "antigravity": python_server(mcp_root / "server.py"),
        "antigravity-agents": python_server(agent_root / "mcp" / "agents-server.py"),
        "antigravity-skills": python_server(agent_root / "mcp" / "skills-server.py"),
        "antigravity-observations": python_server(agent_root / "mcp" / "observations-server.py"),
        "antigravity-intelligence": python_server(agent_root / "mcp" / "intelligence-server.py"),
        "antigravity-ui": python_server(agent_root / "mcp" / "ui-server.py"),
        "antigravity-memory": python_server(agent_root / "mcp" / "memory-server.py"),
        "antigravity-brain": python_server(
            agent_root / "mcp" / "brain-server.py", {"ANTIGRAVITY_ROOT": root_path}
        ),
        "antigravity-excel": python_server(
            agent_root / "mcp" / "excel-server.py", {"ANTIGRAVITY_ROOT": root_path}
        ),
        "antigravity-delta-reader": python_server(
            agent_root / "mcp" / "delta-reader-server.py",
            {"ANTIGRAVITY_ROOT": root_path, "ANTIGRAVITY_DELTA_ROOTS": root_path},
        ),
        "antigravity-provider": python_server(
            agent_root / "mcp" / "provider-server.py", {"ANTIGRAVITY_ROOT": root_path}
        ),
        "antigravity-watcher": python_server(
            agent_root / "mcp" / "watcher-server.py",
            {"ANTIGRAVITY_WATCHER_GATEWAY": "true", "ANTIGRAVITY_WATCHER_BRAIN": "true"},
        ),
        "antigravity-context-engine": python_server(
            agent_root / "mcp" / "context-engine-server.py"
        ),
        "jpkkenfull": python_server(agent_root / "mcp" / "jpkkenfull-server.py"),
        "antigravity-brain-graph": python_server(
            agent_root / "mcp" / "brain-graph-server.py", {"ANTIGRAVITY_ROOT": root_path}
        ),
        # Shu: bridges de integracion outward (discord/github/slack/webhook).
        # Canonicalizados aqui (antes eran entradas manuales en .mcp.json con
        # paths corruptos; ver bugfix_shu_servers_canonical_2026_07).
        "antigravity-shu-discord": python_server(
            agent_root / "mcp" / "shu_discord_bridge.py", {"ANTIGRAVITY_ROOT": root_path}
        ),
        "antigravity-shu-github": python_server(
            agent_root / "mcp" / "shu_github_bridge.py", {"ANTIGRAVITY_ROOT": root_path}
        ),
        "antigravity-shu-slack": python_server(
            agent_root / "mcp" / "shu_slack_bridge.py", {"ANTIGRAVITY_ROOT": root_path}
        ),
        "antigravity-shu-webhook": python_server(
            agent_root / "mcp" / "shu-webhook-server.py", {"ANTIGRAVITY_ROOT": root_path}
        ),
        "antigravity-shu-webhooks": python_server(
            agent_root / "mcp" / "shu_webhook_dispatcher.py",
            {"ANTIGRAVITY_ROOT": root_path},
        ),
    }

    if enable_dev_preset:
        servers["context7"] = npx_server(["-y", "@upstash/context7-mcp@3.2.3"])
        servers["git"] = uvx_server(["mcp-server-git==2026.6.16"])
        servers["chrome-devtools"] = npx_server(
            ["-y", "chrome-devtools-mcp@1.5.0", "--no-usage-statistics"]
        )
        servers["magic-21st"] = npx_server(
            ["-y", "@21st-dev/magic@0.1.0", 'API_KEY="${MAGIC_21ST_API_KEY}"'],
            {"MAGIC_21ST_API_KEY": "${MAGIC_21ST_API_KEY}"},
        )
        # SQLite reemplaza a postgres (2026-06-10): no hay PostgreSQL local y el
        # ecosistema usa SQLite; el DB vive en el runtime dir del mother repo.
        servers["sqlite"] = uvx_server(
            [
                "mcp-server-sqlite==2025.4.25",
                "--db-path",
                "${ANTIGRAVITY_ROOT}/.antigravity/antigravity.db",
            ]
        )
        if target_dir is not None:
            servers["filesystem"] = npx_server(
                [
                    "-y",
                    "@modelcontextprotocol/server-filesystem@2026.7.4",
                    normalize_path(target_dir),
                ]
            )

    return maybe_add_remote_server(servers, gateway_url=gateway_url, token=token)


# ---------------------------------------------------------------------------
# Config file merge helpers
# ---------------------------------------------------------------------------


def _merge_broker_entry(
    existing: dict[str, Any],
    replacement: dict[str, Any],
) -> dict[str, Any]:
    """Replace managed transport fields without discarding user-owned context.

    Broker v2 deliberately replaces command/args/url/headers so obsolete
    Antigravity transports and embedded authorization headers cannot survive a
    migration.  Environment values and an explicit working directory may,
    however, belong to the project rather than to Antigravity.  Preserve those
    values while letting the canonical bundle win on collisions.
    """

    merged = dict(replacement)
    existing_env = existing.get("env")
    replacement_env = replacement.get("env")
    if isinstance(existing_env, dict) and isinstance(replacement_env, dict):
        merged["env"] = {**existing_env, **replacement_env}
    elif isinstance(existing_env, dict) and "env" not in replacement:
        merged["env"] = dict(existing_env)
    if "cwd" in existing and "cwd" not in replacement:
        merged["cwd"] = existing["cwd"]
    return merged


def _path_is_inside_repo(file_path: Path) -> bool:
    """Indica si el archivo destino vive dentro del repo OpenAntigravity.

    Args:
        file_path: Ruta del JSON que se va a escribir.

    Returns:
        True si esta bajo la raiz del repo. Ante cualquier duda devuelve False,
        que es la opcion segura: no templatizar deja rutas absolutas que
        funcionan, mientras que templatizar de mas rompe el arranque del server.
    """
    try:
        repo_root = Path(__file__).resolve().parents[3]
        file_path.resolve().relative_to(repo_root)
        return True
    except (ValueError, OSError, IndexError):
        return False


def safe_merge_json(file_path: Path, new_servers: dict[str, Any]) -> bool:
    """Mergea servidores MCP sobre un JSON basado en mcpServers."""
    config = read_json_file(file_path)
    current_servers = config.get("mcpServers")
    if not isinstance(current_servers, dict):
        current_servers = {}
    current_servers, migrated = _migrate_managed_servers(current_servers, new_servers)
    if migrated:
        logger.info(
            "🧹 [MCP v2] Entradas administradas migradas en %s: %s",
            file_path.name,
            ", ".join(migrated),
        )
    current_servers, removed = prune_invalid_local_mcp_servers(current_servers)
    if removed:
        logger.info(
            "🧹 [MCP] Servidores locales invalidos removidos de %s: %s",
            file_path.name,
            ", ".join(sorted(removed)),
        )
    for name, new_cfg in new_servers.items():
        if name == "antigravity" and set(new_servers) == {"antigravity"}:
            existing = current_servers.get(name)
            current_servers[name] = (
                _merge_broker_entry(existing, new_cfg)
                if isinstance(existing, dict)
                else new_cfg
            )
            continue
        if name in current_servers and isinstance(current_servers[name], dict):
            existing = current_servers[name]
            # Preserve custom fields (cwd, etc.) not in the new config
            merged = {**existing, **new_cfg}
            # Merge recursivo de env: si el usuario añadio variables custom a un server
            # que Antigravity tambien define, las combinamos en vez de pisarlas.
            existing_env = existing.get("env") if isinstance(existing, dict) else None
            new_env = new_cfg.get("env") if isinstance(new_cfg, dict) else None
            if isinstance(existing_env, dict) and isinstance(new_env, dict):
                merged["env"] = {**existing_env, **new_env}
            current_servers[name] = merged
        else:
            current_servers[name] = new_cfg
    config["mcpServers"] = current_servers
    # Aplica portabilizacion al resultado del merge para que los servers existentes
    # que no se reemplazaron (shallow merge en linea 505) tambien tengan sus paths
    # hardcoded de usuario convertidos a ${USERPROFILE}/${ANTIGRAVITY_ROOT}.
    # `${ANTIGRAVITY_ROOT}` significa cosas distintas segun donde viva el archivo:
    # en el repo fuente es el repo; en un target inyectado vale "." (el target).
    # Templatizar la ruta del repo FUENTE en la config de un target la hace apuntar
    # al target, que no tiene `.venv` -> el server MCP no arranca. Por eso solo se
    # templatiza cuando el destino esta dentro del repo.
    templatize = _path_is_inside_repo(file_path)
    config = _make_portable_paths(config, templatize_repo_root=templatize)
    return write_json_file(file_path, config, templatize_repo_root=templatize)


# Variable estilo ${VAR} que VS Code NO expande (espera ${env:VAR}). El negative
# lookahead excluye las que VS Code SI entiende para no romperlas en re-injecciones.
_VSCODE_BARE_VAR_RE = re.compile(
    r"\$\{(?!env:|workspaceFolder|workspaceFolderBasename|userHome|input:|config:|command:)"
    r"([A-Za-z_][A-Za-z0-9_]*)\}"
)


def _to_vscode_var_syntax(value: Any) -> Any:
    """Convierte ${VAR} a ${env:VAR} (sintaxis VS Code) recursivamente en strings."""
    if isinstance(value, str):
        return _VSCODE_BARE_VAR_RE.sub(r"${env:\1}", value)
    if isinstance(value, list):
        return [_to_vscode_var_syntax(item) for item in value]
    if isinstance(value, dict):
        return {key: _to_vscode_var_syntax(item) for key, item in value.items()}
    return value


def _to_vscode_server(server: dict[str, Any]) -> dict[str, Any]:
    """Normaliza un server al schema de VS Code: agrega 'type' y migra variables.

    VS Code exige un campo 'type' ('stdio' | 'http' | 'sse') por servidor. Los
    servers stdio del injector no lo traen, asi que se infiere por presencia de 'url'.
    """
    if not isinstance(server, dict):
        return server
    converted = _to_vscode_var_syntax(server)
    if "type" not in converted:
        server_type = "http" if "url" in converted else "stdio"
        converted = {"type": server_type, **converted}
    return converted


def safe_merge_vscode_mcp(file_path: Path, new_servers: dict[str, Any]) -> bool:
    """Mergea servidores MCP en .vscode/mcp.json con el formato NATIVO de VS Code.

    VS Code (GitHub Copilot, modo Agent) usa la clave raiz "servers" — NO
    "mcpServers" como Cline/Cursor/Claude — y exige un campo "type" por servidor.
    Ademas resuelve variables con sintaxis ${env:VAR}, no ${VAR}. Si el archivo se
    escribe con formato mcpServers, VS Code lo ignora entero y no expone ninguna
    tool. Cline sigue usando safe_merge_json sobre cline_mcp_settings.json, que SI
    espera mcpServers. Ver bugfix_vscode_mcp_servers_key.
    """
    config = read_json_file(file_path)
    current_servers = config.get("servers")
    if not isinstance(current_servers, dict):
        current_servers = {}
    current_servers, migrated = _migrate_managed_servers(current_servers, new_servers)
    if migrated:
        logger.info(
            "🧹 [VS Code MCP v2] Entradas administradas migradas en %s: %s",
            file_path.name,
            ", ".join(migrated),
        )
    current_servers, removed = prune_invalid_local_mcp_servers(current_servers)
    if removed:
        logger.info(
            "🧹 [VS Code MCP] Servidores locales invalidos removidos de %s: %s",
            file_path.name,
            ", ".join(sorted(removed)),
        )
    for name, new_cfg in new_servers.items():
        vscode_cfg = _to_vscode_server(new_cfg)
        if name == "antigravity" and set(new_servers) == {"antigravity"}:
            existing = current_servers.get(name)
            current_servers[name] = (
                _merge_broker_entry(existing, vscode_cfg)
                if isinstance(existing, dict)
                else vscode_cfg
            )
            continue
        if name in current_servers and isinstance(current_servers[name], dict):
            existing = current_servers[name]
            merged = {**existing, **vscode_cfg}
            # Merge recursivo de env (mismo criterio que safe_merge_json).
            existing_env = existing.get("env") if isinstance(existing, dict) else None
            new_env = vscode_cfg.get("env") if isinstance(vscode_cfg, dict) else None
            if isinstance(existing_env, dict) and isinstance(new_env, dict):
                merged["env"] = {**existing_env, **new_env}
            current_servers[name] = merged
        else:
            current_servers[name] = vscode_cfg
    config["servers"] = current_servers
    if "inputs" not in config:
        config["inputs"] = []
    # Migracion: si un injector previo dejo "mcpServers", quitarlo (VS Code lo ignora).
    config.pop("mcpServers", None)
    return write_json_file(file_path, config)


def safe_merge_zed_settings(file_path: Path, new_servers: dict[str, Any]) -> bool:
    """Merge Zed's current flat ``context_servers`` command shape."""
    config = read_json_file(file_path)
    current_servers = config.get("context_servers")
    if not isinstance(current_servers, dict):
        current_servers = {}
    normalized_existing: dict[str, Any] = {}
    for name, server in current_servers.items():
        if not isinstance(server, dict):
            continue
        command_block = server.get("command")
        if isinstance(command_block, dict):
            command = command_block.get("path")
            args = command_block.get("args", [])
            env = command_block.get("env", {})
        else:
            command = command_block
            args = server.get("args", [])
            env = server.get("env", {})
        if not isinstance(command, str):
            continue
        normalized_existing[name] = {
            "command": command,
            "args": args if isinstance(args, list) else [],
            "env": env if isinstance(env, dict) else {},
        }
    normalized_existing, removed = prune_invalid_local_mcp_servers(normalized_existing)
    if removed:
        logger.info(
            "🧹 [Zed MCP] Servidores locales invalidos removidos de %s: %s",
            file_path.name,
            ", ".join(sorted(removed)),
        )
    normalized_existing, migrated = _migrate_managed_servers(
        normalized_existing,
        new_servers,
    )
    if migrated:
        logger.info(
            "🧹 [Zed MCP v2] Entradas administradas migradas en %s: %s",
            file_path.name,
            ", ".join(migrated),
        )
    current_servers = {
        name: {
            "command": server.get("command"),
            "args": server.get("args", []),
            "env": server.get("env", {}),
        }
        for name, server in normalized_existing.items()
        if isinstance(server, dict)
    }

    for name, server in new_servers.items():
        command = server.get("command")
        args = server.get("args", [])
        if not isinstance(command, str):
            continue
        current_servers[name] = {
            "command": command,
            "args": args if isinstance(args, list) else [],
            "env": server.get("env", {}) if isinstance(server.get("env"), dict) else {},
        }

    config["context_servers"] = current_servers
    return write_json_file(file_path, config)


def safe_merge_continue_json(file_path: Path, new_servers: dict[str, Any]) -> bool:
    """Mergea servidores MCP en .continue/config.json usando el formato experimental de Continue.dev."""
    config = read_json_file(file_path)
    experimental = config.get("experimental")
    if not isinstance(experimental, dict):
        experimental = {}
    existing = experimental.get("modelContextProtocolServers")
    if not isinstance(existing, list):
        existing = []

    cleaned_existing: list[dict[str, Any]] = []
    removed = 0
    broker_only = set(new_servers) == {"antigravity"}
    for server in existing:
        if not isinstance(server, dict):
            continue
        if broker_only and _is_legacy_managed_transport(server):
            removed += 1
            continue
        transport = server.get("transport", {})
        if not isinstance(transport, dict):
            cleaned_existing.append(server)
            continue
        normalized = {
            "command": transport.get("command"),
            "args": transport.get("args", []),
        }
        if _server_contains_missing_local_path(normalized):
            removed += 1
            continue
        cleaned_existing.append(server)
    if removed:
        logger.info(
            "🧹 [Continue MCP] %d servidor(es) locales invalidos removidos de %s",
            removed,
            file_path.name,
        )
    existing = cleaned_existing

    # Dedupe por identidad real del server (command + args normalizados), NO por
    # tupla de args sola: las entradas Continue no guardan nombre, y un re-inyect
    # con prefijo \\?\ en los paths cambiaba las tuplas y duplicaba. Normalizar
    # el prefijo extendido de Windows hace el merge idempotente.
    def _identity(command: Any, args: Any) -> tuple[Any, tuple[Any, ...]]:
        norm_cmd = _strip_extended_length_prefix(command)
        norm_args = _strip_extended_length_prefix(args if isinstance(args, list) else [])
        return (norm_cmd, tuple(norm_args))

    existing_keys = {
        _identity(s.get("transport", {}).get("command"), s.get("transport", {}).get("args", []))
        for s in existing
        if isinstance(s, dict)
    }

    for _name, server in new_servers.items():
        command = _strip_extended_length_prefix(server.get("command"))
        args = _strip_extended_length_prefix(server.get("args", []))
        env = _strip_extended_length_prefix(server.get("env", {}))
        if not isinstance(command, str):
            continue
        if not isinstance(args, list):
            args = []
        key = _identity(command, args)
        if key not in existing_keys:
            existing.append(
                {
                    "transport": {
                        "type": "stdio",
                        "command": command,
                        "args": args,
                        "env": env if isinstance(env, dict) else {},
                    }
                }
            )
            existing_keys.add(key)

    experimental["modelContextProtocolServers"] = existing
    config["experimental"] = experimental
    return write_json_file(file_path, config)


_CODEX_MCP_TABLE_RE = re.compile(r"^\[mcp_servers\.([A-Za-z0-9_-]+)(?:\.[^\]]+)?\]\s*$")


def safe_merge_codex_toml(file_path: Path, new_servers: dict[str, Any]) -> bool:
    """Merge Codex MCP tables while preserving unrelated TOML verbatim."""

    try:
        original = file_path.read_text(encoding="utf-8") if file_path.exists() else ""
    except OSError as exc:
        logger.error("❌ [Codex MCP] No se pudo leer %s: %s", file_path, exc)
        return False

    lines = original.splitlines()
    output: list[str] = []
    skip_current_table = False
    broker_only = set(new_servers) == {"antigravity"}
    for line in lines:
        table_match = _CODEX_MCP_TABLE_RE.match(line.strip())
        if table_match:
            table_name = table_match.group(1)
            skip_current_table = broker_only and table_name in LEGACY_MANAGED_MCP_SERVER_NAMES
        elif line.lstrip().startswith("["):
            skip_current_table = False
        if not skip_current_table:
            output.append(line)

    for name, server in new_servers.items():
        command = server.get("command")
        if not isinstance(command, str):
            continue
        args = server.get("args", [])
        env = server.get("env", {})
        while output and not output[-1].strip():
            output.pop()
        output.extend(
            [
                "",
                f"[mcp_servers.{name}]",
                f"command = {json.dumps(command, ensure_ascii=False)}",
                f"args = {json.dumps(args, ensure_ascii=False)}",
            ]
        )
        if isinstance(env, dict) and env:
            env_fields = ", ".join(
                f"{key} = {json.dumps(str(value), ensure_ascii=False)}"
                for key, value in sorted(env.items())
            )
            output.append(f"env = {{ {env_fields} }}")

    serialized = "\n".join(output).strip() + "\n"
    if serialized == original:
        return True
    try:
        file_path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=file_path.parent,
            delete=False,
        ) as handle:
            handle.write(serialized)
            temporary_path = Path(handle.name)
        temporary_path.replace(file_path)
        return True
    except OSError as exc:
        logger.error("❌ [Codex MCP] No se pudo escribir %s: %s", file_path, exc)
        return False


# ---------------------------------------------------------------------------
# Antigravity config
# ---------------------------------------------------------------------------


def install_antigravity_config(
    target_dir: Path,
    repo_root: Path,
    enable_dev_preset: bool = True,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    token: str = "",
) -> bool:
    """Crea .antigravity/config.json con la configuracion REST del ecosistema."""
    config_dir = target_dir / ".antigravity"
    ensure_dir(config_dir)

    config = {
        "gateway": gateway_url,
        "ecosystem_root": ".",
        "version": ECOSYSTEM_VERSION,
        "memoryBackend": DEFAULT_MEMORY_BACKEND,
        "registry": {
            "mode": DEFAULT_REGISTRY_MODE,
            "cacheTtl": DEFAULT_REGISTRY_CACHE_TTL_SECONDS,
        },
        "orchestrator": {
            "mode": DEFAULT_ORCHESTRATOR_MODE,
        },
        "fallbackPolicy": ["local-project", "local-cache", "remote-mcp"],
        "mcp_servers": ["antigravity"],
        "connectors": {
            "catalog": ".agent/mcp/broker/connectors.json",
            "lazy": True,
            "visibleByDefault": bool(enable_dev_preset),
        },
        "resolution_policy": {
            "skills": ["local-mcp", "remote-mcp"],
            "agents": ["local-mcp", "remote-mcp"],
            "commands": ["local-runtime", "remote-mcp"],
        },
        "docs": "https://github.com/jokken79/AntigravitiSkillUSN",
    }
    if token:
        logger.warning(
            "Ignoring plaintext Antigravity token; Nexus supplies credentials from the OS keyring"
        )

    config_path = config_dir / "config.json"
    if write_json_file(config_path, config):
        logger.info(f"✅ [Config] Creado .antigravity/config.json con gateway {gateway_url}")
        return True
    return False


# ---------------------------------------------------------------------------
# Claude settings
# ---------------------------------------------------------------------------


def install_claude_settings(target_dir: Path, repo_root: Path) -> bool:
    """Copia/mergea el settings.json de Claude Code adaptado al proyecto destino."""
    source = repo_root / ".claude" / "settings.json"
    if not source.exists():
        logger.warning("⚠️  [.claude/settings.json] No se encontro settings.json origen")
        return False

    source_settings = read_json_file(source)
    target_settings_path = target_dir / ".claude" / "settings.json"
    existing = read_json_file(target_settings_path)
    merged = deep_merge(existing, source_settings)
    merged = sanitize_claude_settings(merged)

    project_block = merged.get("project")
    if not isinstance(project_block, dict):
        project_block = {}
    project_block["name"] = target_dir.name
    project_block["description"] = "Proyecto integrado con Antigravity Agents"
    merged["project"] = project_block

    if write_json_file(target_settings_path, merged):
        logger.info("✅ [.claude] settings.json actualizado")
        return True
    return False


# ---------------------------------------------------------------------------
# AI manifest
# ---------------------------------------------------------------------------


def collect_runtime_fingerprint(target_dir: Path) -> dict[str, Any]:
    """Genera fingerprint SHA-256 de archivos criticos del runtime inyectado."""
    files: dict[str, str] = {}
    for rel_path in HOOK_RUNTIME_FILES:
        absolute = target_dir / rel_path
        files[rel_path] = hash_file(absolute) if absolute.exists() else ""
    return {
        "algorithm": "sha256",
        "files": files,
    }


def install_ai_manifest(
    target_dir: Path,
    gateway_url: str,
    enable_dev_preset: bool,
    mcp_enabled: bool,
    remote_enabled: bool = False,
) -> bool:
    """Genera un manifiesto local consumible por IAs/IDEs externos."""
    try:
        fingerprint = collect_runtime_fingerprint(target_dir)
    except Exception as exc:
        logger.warning(
            f"⚠️ [Manifest] collect_runtime_fingerprint falló ({exc}), usando fingerprint vacío"
        )
        fingerprint = {"algorithm": "sha256", "files": {}}
    manifest_path = target_dir / ".antigravity" / "ai_manifest.json"
    installed_at = datetime.now().isoformat()
    if manifest_path.exists():
        try:
            existing_manifest = read_json_file(manifest_path)
            if isinstance(existing_manifest.get("installedAt"), str):
                installed_at = existing_manifest["installedAt"]
        except Exception:
            pass

    payload = {
        "name": target_dir.name,
        "version": ECOSYSTEM_VERSION,
        "installedAt": installed_at,
        "mode": "mcp" if mcp_enabled else "local",
        "runtimeVersionFile": ".agent/VERSION",
        "runtimeFingerprint": fingerprint,
        "gateway": gateway_url,
        "supports": {
            "mcp": mcp_enabled,
            "claudeCode": True,
            "codex": True,
            "cursor": True,
            "windsurf": True,
            "vscode": True,
            "rooCode": True,
            "cline": True,
            "zed": True,
            "continue": True,
            "aider": True,
            "gemini": True,
            "genericAi": True,
        },
        "devPreset": enable_dev_preset,
        "entrypoints": {
            "manifest": ".antigravity/ai_manifest.json",
            "agentsGuide": "AGENTS.md",
            "claudeSettings": ".claude/settings.json",
            "codexSkillsManifest": ".antigravity/codex-skills.json",
            "minimaxSkillsManifest": ".antigravity/minimax-skills.json",
            "projectRules": ".antigravity/rules.md",
            "projectMemory": "ESTADO_PROYECTO.md",
            "mcp": ".mcp.json" if mcp_enabled else None,
        },
        "resolutionPolicy": {
            "skills": ["local-mcp", "remote-mcp"] if remote_enabled else ["local-mcp"],
            "agents": ["local-mcp", "remote-mcp"] if remote_enabled else ["local-mcp"],
            "commands": ["local-runtime", "remote-mcp"] if remote_enabled else ["local-runtime"],
        },
        "remoteMcp": {
            "enabled": remote_enabled,
            "gatewayUrl": gateway_url if remote_enabled else "",
        },
    }
    if write_json_file(manifest_path, payload):
        logger.info("✅ [Manifest] .antigravity/ai_manifest.json generado")
        return True
    return False


# ---------------------------------------------------------------------------
# Gemini
# ---------------------------------------------------------------------------


def install_gemini_config(target_dir: Path, repo_root: Path) -> bool:
    """Copia GEMINI.md y genera .gemini/settings.json para Gemini CLI."""
    # Copy GEMINI.md from .agent/rules/
    gemini_src = repo_root / ".agent" / "rules" / "GEMINI.md"
    if gemini_src.exists():
        if copy_file(gemini_src, target_dir / "GEMINI.md"):
            logger.info("✅ [Gemini] GEMINI.md copiado al raíz del proyecto")
    else:
        logger.warning("⚠️  [Gemini] No se encontró .agent/rules/GEMINI.md — se omite copia")

    # Create .gemini/settings.json
    gemini_dir = target_dir / ".gemini"
    ensure_dir(gemini_dir)
    settings_path = gemini_dir / "settings.json"
    servers = get_mcp_servers(
        repo_root=repo_root,
        target_dir=target_dir,
        enable_dev_preset=True,
    )
    if not safe_merge_json(settings_path, servers):
        logger.error("❌ [Gemini] Fallo la configuración MCP")
        return False
    settings = read_json_file(settings_path)
    settings.update(
        {
            "version": ECOSYSTEM_VERSION,
            "rulesFile": "GEMINI.md",
            "contextFiles": [
                "ESTADO_PROYECTO.md",
                ".antigravity/rules.md",
            ],
        }
    )
    if write_json_file(settings_path, settings):
        logger.info("✅ [Gemini] .gemini/settings.json generado")
        return True
    logger.error("❌ [Gemini] Fallo la configuracion de .gemini/settings.json")
    return False


# ---------------------------------------------------------------------------
# Aider
# ---------------------------------------------------------------------------


def install_aider_config(target_dir: Path) -> bool:
    """Genera .aider.conf.yml para integración con Aider."""
    content = (
        "# Aider configuration — Antigravity Ecosystem\n"
        "# https://aider.chat/docs/config/aider_conf.html\n"
        "read:\n"
        "  - RULES.md\n"
        "  - .antigravity/rules.md\n"
        "  - ESTADO_PROYECTO.md\n"
        "auto-commits: false\n"
    )
    aider_path = target_dir / ".aider.conf.yml"
    try:
        aider_path.write_text(content, encoding="utf-8")
        logger.info("✅ [Aider] .aider.conf.yml generado")
        return True
    except Exception as exc:
        logger.error(f"❌ [Aider] No se pudo escribir .aider.conf.yml: {exc}")
        return False


# ---------------------------------------------------------------------------
# Agent versioning
# ---------------------------------------------------------------------------


def get_agent_version(agent_dir: Path) -> str:
    """Lee la versión semántica desde agent.json del directorio de un agente."""
    agent_json = agent_dir / "agent.json"
    if agent_json.exists():
        try:
            data = json.loads(agent_json.read_text(encoding="utf-8"))
            return str(data.get("version", "0.0.0"))
        except Exception:
            return "0.0.0"
    return "0.0.0"


def _parse_version(ver: str) -> tuple[int, ...]:
    """Convierte '1.2.3' en (1, 2, 3) para comparación. Fallback seguro."""
    try:
        return tuple(int(x) for x in ver.strip().split(".")[:3])
    except (ValueError, AttributeError):
        return (0, 0, 0)


def should_update_agent(src: Path, dst: Path) -> bool:
    """Devuelve True si la versión fuente es mayor que la versión destino."""
    src_ver = get_agent_version(src)
    dst_ver = get_agent_version(dst)
    src_parsed = _parse_version(src_ver)
    dst_parsed = _parse_version(dst_ver)
    if src_parsed != dst_parsed:
        logger.info(
            f"  [version] {src.name}: {dst_ver} -> {src_ver} "
            f"({'actualizar' if src_parsed > dst_parsed else 'destino más nuevo'})"
        )
    return src_parsed > dst_parsed


# ---------------------------------------------------------------------------
# Visual diff
# ---------------------------------------------------------------------------


def show_injection_diff(src_dir: Path, dst_dir: Path) -> None:
    """Muestra diff visual de qué archivos cambiarán al inyectar."""
    new_files: list[str] = []
    modified_files: list[str] = []
    unchanged_files: list[str] = []

    if not src_dir.exists():
        return

    for src_file in src_dir.rglob("*"):
        if src_file.is_file():
            try:
                rel = src_file.relative_to(src_dir)
            except ValueError:
                continue
            dst_file = dst_dir / rel
            if not dst_file.exists():
                new_files.append(str(rel))
            elif src_file.read_bytes() != dst_file.read_bytes():
                modified_files.append(str(rel))
            else:
                unchanged_files.append(str(rel))

    if new_files:
        logger.info(f"  🟢 NUEVOS ({len(new_files)}):")
        for f in new_files[:10]:
            logger.info(f"     + {f}")
        if len(new_files) > 10:
            logger.info(f"     ... y {len(new_files) - 10} más")
    if modified_files:
        logger.info(f"  🟡 MODIFICADOS ({len(modified_files)}):")
        for f in modified_files[:10]:
            logger.info(f"     ~ {f}")
        if len(modified_files) > 10:
            logger.info(f"     ... y {len(modified_files) - 10} más")
    logger.info(f"  ⚪ Sin cambios: {len(unchanged_files)} archivos")


# ---------------------------------------------------------------------------
# Process guard
# ---------------------------------------------------------------------------


def check_blocking_processes() -> list[str]:
    """Detecta si hay apps que podrian bloquear la inyección."""
    try:
        import psutil

        found = []
        for proc in psutil.process_iter(["name", "pid"]):
            try:
                if any(bp.lower() in proc.info["name"].lower() for bp in BLOCKING_PROCESSES):
                    found.append(f"{proc.info['name']} (PID {proc.info['pid']})")
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        return found
    except ImportError:
        return []  # psutil no disponible - continuar sin aviso
