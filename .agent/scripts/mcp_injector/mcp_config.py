"""Configuracion MCP — funciones de configuracion extraidas de mcp_injector.py.

Este modulo es semi-autonomo: las utilidades de I/O, paths y constantes se importan
de los modulos hermanos (io_utils, path_utils, constants). Si se usa fuera del
paquete mcp_injector, esas dependencias deben satisfacerse o re-definirse.

Funciones extraidas:
    _server_contains_missing_local_path, prune_invalid_local_mcp_servers,
    get_mcp_servers, maybe_add_remote_server, safe_merge_json,
    safe_merge_zed_settings, safe_merge_continue_json,
    install_antigravity_config, collect_runtime_fingerprint,
    install_claude_settings, install_ai_manifest, install_gemini_config,
    install_aider_config, get_agent_version, _parse_version,
    should_update_agent, show_injection_diff, check_blocking_processes.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import platform
import re
import shutil
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


# ---------------------------------------------------------------------------
# Helpers locales (usan solo stdlib)
# ---------------------------------------------------------------------------


def _is_absolute_local_path(value: str) -> bool:
    """Detecta rutas absolutas locales Windows/POSIX."""
    if not value:
        return False
    return bool(re.match(r"^[a-zA-Z]:[\\/]", value)) or value.startswith(("/", "\\\\"))


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


def prune_invalid_local_mcp_servers(servers: dict[str, Any]) -> tuple[dict[str, Any], list[str]]:
    """Elimina servidores MCP que arrastran rutas locales absolutas inexistentes."""
    cleaned: dict[str, Any] = {}
    removed: list[str] = []

    for name, server in servers.items():
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


def get_mcp_servers(
    repo_root: Path,
    target_dir: Path | None = None,
    enable_dev_preset: bool = True,
    gateway_url: str = "",
    token: str = "",
) -> dict[str, Any]:
    """Genera configuracion MCP del ecosistema y del preset dev."""
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

    def npx_server(args: list[str]) -> dict[str, Any]:
        if is_windows:
            return {"command": "cmd", "args": ["/c", "npx", *args]}
        return {"command": "npx", "args": args}

    def uvx_server(args: list[str]) -> dict[str, Any]:
        if is_windows:
            return {"command": "cmd", "args": ["/c", "uvx", *args]}
        return {"command": "uvx", "args": args}

    def python_server(script_path: Path) -> dict[str, Any]:
        """Usa 'py' en Windows (launcher portable) y 'python3' en Unix."""
        if is_windows:
            return {"command": "py", "args": [str(script_path)]}
        return {"command": "python3", "args": [str(script_path)]}

    persona_env = {"ANTIGRAVITY_PERSONA": os.getenv("ANTIGRAVITY_PERSONA", "gentleman")}

    servers: dict[str, Any] = {
        "antigravity": {
            **python_server(mcp_root / "server.py"),
            "env": {**persona_env},
        },
        "antigravity-agents": {
            **python_server(agent_root / "mcp" / "agents-server.py"),
            "env": {**persona_env},
        },
        "antigravity-skills": {
            **python_server(agent_root / "mcp" / "skills-server.py"),
            "env": {**persona_env},
        },
        "antigravity-observations": {
            **python_server(agent_root / "mcp" / "observations-server.py"),
            "env": {**persona_env},
        },
        "antigravity-intelligence": {
            **python_server(agent_root / "mcp" / "intelligence-server.py"),
            "env": {**persona_env},
        },
        "antigravity-ui": {
            **python_server(agent_root / "mcp" / "ui-server.py"),
            "env": {**persona_env},
        },
        "antigravity-memory": {
            **python_server(agent_root / "mcp" / "memory-server.py"),
            "env": {**persona_env},
        },
        "antigravity-watcher": {
            **python_server(agent_root / "mcp" / "watcher-server.py"),
            "env": {
                **persona_env,
                "ANTIGRAVITY_WATCHER_GATEWAY": "true",
                "ANTIGRAVITY_WATCHER_BRAIN": "true",
            },
        },
        "antigravity-context-engine": {
            **python_server(agent_root / "mcp" / "context-engine-server.py"),
            "env": {**persona_env},
        },
    }

    stitch_server = npx_server(["-y", "stitch-mcp"])
    stitch_server["env"] = {
        "GOOGLE_CLOUD_PROJECT": "${GOOGLE_CLOUD_PROJECT}",
        "STITCH_API_KEY": "${STITCH_API_KEY}",
    }
    servers["stitch"] = stitch_server

    if enable_dev_preset:
        servers["context7"] = npx_server(["-y", "@upstash/context7-mcp@latest"])
        servers["git"] = uvx_server(["mcp-server-git"])
        servers["chrome-devtools"] = npx_server(
            ["-y", "chrome-devtools-mcp@latest", "--no-usage-statistics"]
        )
        if target_dir is not None:
            servers["filesystem"] = npx_server(
                [
                    "-y",
                    "@modelcontextprotocol/server-filesystem",
                    normalize_path(target_dir),
                ]
            )

    return maybe_add_remote_server(servers, gateway_url=gateway_url, token=token)


# ---------------------------------------------------------------------------
# Config file merge helpers
# ---------------------------------------------------------------------------


def safe_merge_json(file_path: Path, new_servers: dict[str, Any]) -> bool:
    """Mergea servidores MCP sobre un JSON basado en mcpServers."""
    config = read_json_file(file_path)
    current_servers = config.get("mcpServers")
    if not isinstance(current_servers, dict):
        current_servers = {}
    current_servers, removed = prune_invalid_local_mcp_servers(current_servers)
    if removed:
        logger.info(
            "🧹 [MCP] Servidores locales invalidos removidos de %s: %s",
            file_path.name,
            ", ".join(sorted(removed)),
        )
    for name, new_cfg in new_servers.items():
        if name in current_servers and isinstance(current_servers[name], dict):
            existing = current_servers[name]
            # Preserve custom fields (cwd, etc.) not in the new config
            merged = {**existing, **new_cfg}
            current_servers[name] = merged
        else:
            current_servers[name] = new_cfg
    config["mcpServers"] = current_servers
    return write_json_file(file_path, config)


def safe_merge_zed_settings(file_path: Path, new_servers: dict[str, Any]) -> bool:
    """Mergea settings.json de Zed usando context_servers."""
    config = read_json_file(file_path)
    current_servers = config.get("context_servers")
    if not isinstance(current_servers, dict):
        current_servers = {}
    normalized_existing: dict[str, Any] = {}
    for name, server in current_servers.items():
        if not isinstance(server, dict):
            continue
        command_block = server.get("command")
        if not isinstance(command_block, dict):
            continue
        normalized_existing[name] = {
            "command": {
                "path": command_block.get("path"),
                "args": command_block.get("args", []),
            }
        }
    normalized_existing, removed = prune_invalid_local_mcp_servers(normalized_existing)
    if removed:
        logger.info(
            "🧹 [Zed MCP] Servidores locales invalidos removidos de %s: %s",
            file_path.name,
            ", ".join(sorted(removed)),
        )
    current_servers = {
        name: {
            "command": {
                "path": server.get("command", {}).get("path"),
                "args": server.get("command", {}).get("args", []),
            },
            "settings": {},
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
            "command": {
                "path": command,
                "args": args if isinstance(args, list) else [],
            },
            "settings": {},
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
    for server in existing:
        if not isinstance(server, dict):
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

    # Build set of existing args-tuples to avoid duplicates
    existing_keys = {
        tuple(s.get("transport", {}).get("args", [])) for s in existing if isinstance(s, dict)
    }

    for _name, server in new_servers.items():
        command = server.get("command")
        args = server.get("args", [])
        if not isinstance(command, str):
            continue
        key = tuple(args)
        if key not in existing_keys:
            existing.append({"transport": {"type": "stdio", "command": command, "args": args}})
            existing_keys.add(key)

    experimental["modelContextProtocolServers"] = existing
    config["experimental"] = experimental
    return write_json_file(file_path, config)


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

    mcp_servers = [
        "antigravity",
        "antigravity-agents",
        "antigravity-skills",
        "antigravity-observations",
        "antigravity-intelligence",
        "antigravity-ui",
    ]
    mcp_servers.append("stitch")
    if enable_dev_preset:
        mcp_servers.extend(["context7", "filesystem", "git", "chrome-devtools"])
    if token or is_remote_gateway_url(gateway_url):
        mcp_servers.append("antigravity-remote")

    config = {
        "gateway": gateway_url,
        "ecosystem_root": normalize_path(target_dir),
        "source_root": normalize_path(repo_root),
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
        "mcp_servers": mcp_servers,
        "resolution_policy": {
            "skills": ["local-mcp", "remote-mcp"],
            "agents": ["local-mcp", "remote-mcp"],
            "commands": ["local-runtime", "remote-mcp"],
        },
        "docs": "https://github.com/jokken79/AntigravitiSkillUSN",
    }
    if token:
        config["token"] = token

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
    payload = {
        "name": target_dir.name,
        "version": ECOSYSTEM_VERSION,
        "installedAt": datetime.now().isoformat(),
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
    manifest_path = target_dir / ".antigravity" / "ai_manifest.json"
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
    py_cmd = "py" if platform.system() == "Windows" else "python3"
    settings: dict[str, Any] = {
        "version": ECOSYSTEM_VERSION,
        "mcpServers": {
            "antigravity": {
                "command": py_cmd,
                "args": [normalize_path(target_dir / ".agent" / "mcp" / "server.py")],
            }
        },
        "rulesFile": "GEMINI.md",
        "contextFiles": [
            "ESTADO_PROYECTO.md",
            ".antigravity/rules.md",
        ],
    }
    settings_path = gemini_dir / "settings.json"
    if settings_path.exists():
        try:
            existing_settings = read_json_file(settings_path)
            existing_settings.update(settings)
            settings = existing_settings
        except Exception:
            pass
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
            return data.get("version", "0.0.0")
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
