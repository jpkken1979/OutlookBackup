#!/usr/bin/env python3
"""Antigravity Smart Injector.

Instala un runtime portable dentro del proyecto destino y, opcionalmente,
configura clientes MCP compatibles.

Contrato:
- Modo local/directo: instala runtime local completo, sin archivos MCP.
- Modo MCP/full: instala el mismo runtime y ademas las configs MCP.
- El legacy `.claude/memory-engine` no se copia por defecto.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import os
import platform
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

try:
    from app_intelligence_pipeline import quick_analyze, save_profile, write_app_knowledge

    INTELLIGENCE_AVAILABLE = True
except ImportError:
    INTELLIGENCE_AVAILABLE = False

# Import extracted functions from the mcp_injector package
# (mcp_injector.py lives in the package directory and the package is
# available in sys.path when this script runs)
try:
    from mcp_injector.injection import (  # noqa: F401
        inject_workspace,
        run_post_injection_smoke,
        update_hooks_only,
        _run_post_inject_hook,
        inspect_installation,
        summarize_reinjection_targets,
        build_human_dry_run_summary,
        apply_injection_improvements,
        import_target_extras_to_repo,
        import_all_target_changes_to_repo,
        smart_merge,
        detect_real_conflicts,
        apply_conflict_resolution,
        classify_entry_change,
        build_change_detail,
        import_named_entries_with_backup,
        _collect_out_of_scope_items,
    )
except ImportError:
    # Package not available (e.g. running without the package installed)
    pass

logging.basicConfig(
    level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("mcp_injector")


def emit_json(payload: dict[str, Any]) -> None:
    """Emite JSON seguro para stdout en Windows sin depender del codepage activo."""
    print(json.dumps(payload, ensure_ascii=True))


def resolve_sync_plan(args: argparse.Namespace) -> dict[str, bool]:
    """Resuelve un plan conservador de sincronizacion de assets externos.

    Regla: los paquetes externos no se sincronizan por defecto. Solo se activan
    de forma explicita via flags dedicados o mediante el pack forzado.
    """
    do_sync_skills = args.sync_skills and not args.no_sync_skills
    do_sync_codex_skills = args.sync_codex_skills or (
        not args.no_sync_codex_skills
        and is_codex_available()
        and args.codex_skills_profile != "none"
    )
    do_sync_minimax_skills = args.sync_minimax_skills or (
        not args.no_sync_minimax_skills and (is_codex_available() or is_claude_available())
    )
    force_external_pack = args.sync_external_skills_pack
    default_external_pack = False
    do_sync_superpowers = args.sync_superpowers or force_external_pack
    do_sync_brainstorming_planning = args.sync_brainstorming_planning or force_external_pack
    do_sync_oh_my_claudecode = args.sync_oh_my_claudecode or force_external_pack

    return {
        "sync_skills": do_sync_skills,
        "sync_codex_skills": do_sync_codex_skills,
        "sync_minimax_skills": do_sync_minimax_skills,
        "default_external_pack": default_external_pack,
        "force_external_pack": force_external_pack,
        "sync_superpowers": do_sync_superpowers,
        "sync_brainstorming_planning": do_sync_brainstorming_planning,
        "sync_oh_my_claudecode": do_sync_oh_my_claudecode,
    }


_sync_skills_module = None
_sync_codex_skills_module = None
_sync_minimax_skills_module = None
_sync_antigravity_codex_assets_module = None
_sync_codex_config_module = None
_sync_superpowers_module = None
_sync_brainstorming_planning_module = None
_sync_oh_my_claudecode_module = None
_update_vendored_external_skills_module = None
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
REPO_ROOT_POSIX = str(REPO_ROOT).replace("\\", "/")


def _read_ecosystem_version() -> str:
    """Lee la versión desde .agent/VERSION (relativo al script)."""
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "5.0.0"


ECOSYSTEM_VERSION = _read_ecosystem_version()
DEFAULT_GATEWAY_URL = "http://localhost:4747"
DEFAULT_MEMORY_BACKEND = "mem0"
DEFAULT_REGISTRY_MODE = "remote-cache"
DEFAULT_REGISTRY_CACHE_TTL_SECONDS = 900
DEFAULT_ORCHESTRATOR_MODE = "agent-teams-lite"
CODE_EXTENSIONS = {
    ".py",
    ".js",
    ".jsx",
    ".ts",
    ".tsx",
    ".rs",
    ".sh",
    ".ps1",
    ".cjs",
    ".mjs",
    ".css",
    ".scss",
    ".html",
}
CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".conf"}
DOC_EXTENSIONS = {".md", ".txt", ".doc", ".docx", ".pdf"}
SKIP_TREE_NAMES = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
}
ROOT_RULE_FILES = [
    "RULES.md",
    "WORKFLOW_RULES.md",
]
PORTABLE_AGENT_DIRS = [
    "agents",
    "skills",
    "skills-custom",
    "workflows",
    "scripts",
    "core",
    "mcp",
    "templates",
]
CLAUDE_DIRS = ["hooks", "rules", "commands"]
# Archivos de .claude/rules/ que NO deben inyectarse en proyectos externos:
# son específicos de OpenAntigravity (estado del ecosistema, arquitectura interna).
# La identidad del usuario viaja via user-identity.md en las templates.
RULES_EXCLUDE: frozenset[str] = frozenset({"AI_MEMORY.md"})
ANTIGRAVITY_FILES = ["rules.md", "AI_MEMORY_README.md"]
LEGACY_CLAUDE_DIRS = ["agents", "skills", "memory-engine"]
REMOTE_GATEWAY_PLACEHOLDER = "__REMOTE_GATEWAY_URL__"
REMOTE_TOKEN_PLACEHOLDER = "__REMOTE_API_TOKEN__"

# Marcadores que confirman que un directorio es un proyecto real
_PROJECT_MARKERS = (".git", "pyproject.toml", "package.json", "Cargo.toml")


def _validate_target_dir(target_dir: Path) -> bool:
    """Valida que target_dir sea un directorio de proyecto real y seguro.

    Verifica tres condiciones:
    1. La ruta es absoluta (evita rutas relativas garbled que se resuelven en cwd).
    2. El directorio existe en disco.
    3. Contiene al menos un marcador de proyecto conocido (.git, pyproject.toml,
       package.json o Cargo.toml) para confirmar que es un proyecto real.

    Args:
        target_dir: Path del directorio destino a validar.

    Returns:
        True si el directorio pasa todas las comprobaciones, False en caso contrario.
    """
    if not target_dir.is_absolute():
        logger.warning(
            "[validate_target_dir] Ruta relativa rechazada: %r — usar ruta absoluta",
            str(target_dir),
        )
        return False
    if not target_dir.exists():
        logger.warning("[validate_target_dir] Directorio no existe: %r", str(target_dir))
        return False
    if not any((target_dir / marker).exists() for marker in _PROJECT_MARKERS):
        logger.warning(
            "[validate_target_dir] Directorio no parece un proyecto real (sin marcadores): %r",
            str(target_dir),
        )
        return False
    return True


HOOK_RUNTIME_FILES = [
    ".agent/scripts/hook_runner.py",
    ".agent/scripts/session_hook.py",
    ".agent/scripts/git_sync_hook.py",
]
# Markers hardcodeados de instalaciones legacy conocidas en Windows del usuario.
# Se usan como heuristica para detectar configuraciones `.claude/` que vinieron
# de otra PC y contienen rutas absolutas no portables. No son secrets y su
# exposicion no genera riesgo — son paths historicos de diagnostico.
# Permite ampliar via env var para CI, usuarios con otras rutas legacy o tests.
NON_PORTABLE_CLAUDE_MARKERS: tuple[str, ...] = (
    "D:/Git/OpenAntigravity",
    "C--Users-Kenji-Documents-GitHub-OpenAntigravity",
    "D--Git-OpenAntigravity",
)
_extra_markers = os.environ.get("ANTIGRAVITY_EXTRA_NONPORTABLE_MARKERS", "")
if _extra_markers:
    NON_PORTABLE_CLAUDE_MARKERS = NON_PORTABLE_CLAUDE_MARKERS + tuple(
        m.strip() for m in _extra_markers.split(",") if m.strip()
    )


def is_codex_available() -> bool:
    """Determina si Codex parece estar instalado/configurado en la máquina."""
    codex_home = os.environ.get("CODEX_HOME")
    if codex_home:
        return Path(codex_home).expanduser().exists()
    return (Path.home() / ".codex").exists()


def is_claude_available() -> bool:
    """Determina si Claude Code está disponible en la máquina."""
    return shutil.which("claude") is not None or (Path.home() / ".claude").exists()


def normalize_path(path: Path) -> str:
    """Normaliza rutas para JSON."""
    return str(path.resolve()).replace("\\", "/")


def _backup_conflicting_path(path: Path) -> Path:
    """Respalda archivos/directorios que bloquean la creación de una ruta requerida."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.name}.legacy.{timestamp}")
    counter = 1
    while backup_path.exists():
        backup_path = path.with_name(f"{path.name}.legacy.{timestamp}_{counter}")
        counter += 1
    shutil.move(str(path), str(backup_path))
    logger.info(f"  [legacy-conflict] {path} -> {backup_path}")
    return backup_path


def _is_valid_dirname(name: str) -> bool:
    """Valida que un nombre de directorio sea seguro (sin caracteres de control Unicode)."""
    if not name or name in {".", "..", ""}:
        return False
    # Rechazar si contiene caracteres de control Unicode (U+0000 a U+001F, U+007F a U+009F, etc.)
    for char in name:
        code = ord(char)
        # Control characters
        if code < 0x20 or (0x7F <= code <= 0x9F):
            return False
        # Non-breaking spaces y otros problemas
        if code in {0x85, 0xA0}:
            return False
    return True


def ensure_dir(path: Path) -> None:
    """Crea un directorio si no existe."""
    # Validar cada componente del path
    for part in path.parts:
        if not _is_valid_dirname(part):
            logger.error(
                f"❌ [SECURITY] Nombre de directorio inválido (caracteres de control): {part}"
            )
            raise ValueError(f"Invalid directory name: {part}")

    if path.exists() and not path.is_dir():
        _backup_conflicting_path(path)
    path.mkdir(parents=True, exist_ok=True)


def read_json_file(path: Path) -> dict[str, Any]:
    """Lee JSON tolerando archivos vacios o corruptos."""
    if not path.exists():
        return {}
    try:
        content = path.read_text(encoding="utf-8").strip()
    except Exception as exc:
        logger.warning(f"⚠️  [JSON] No se pudo leer {path}: {exc}")
        return {}
    if not content:
        return {}
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        logger.warning(f"⚠️  [JSON] Archivo corrupto detectado ({path.name}), se reconstruira.")
        return {}
    return data if isinstance(data, dict) else {}


def write_json_file(path: Path, payload: dict[str, Any]) -> bool:
    """Escribe un JSON con indentacion estable."""
    try:
        ensure_dir(path.parent)
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as exc:
        logger.error(f"❌ [JSON] No se pudo escribir {path}: {exc}")
        return False


def deep_merge(base: dict[str, Any], updates: dict[str, Any]) -> dict[str, Any]:
    """Merge recursivo simple."""
    result = dict(base)
    for key, value in updates.items():
        current = result.get(key)
        if isinstance(current, dict) and isinstance(value, dict):
            result[key] = deep_merge(current, value)
        else:
            result[key] = value
    return result


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


def safe_remove_legacy(path: Path) -> None:
    """En lugar de borrar, hace backup rotativo y crea symlink al nuevo destino en .agent/."""
    if not path.exists():
        return

    # Backup con timestamp
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.parent / f"{path.name}.bak.{timestamp}"
    shutil.move(str(path), str(backup_path))
    logger.info(f"  [backup] {path.name} -> {backup_path.name}")

    # Limpiar backups viejos (mantener solo los 3 más recientes)
    pattern = f"{path.name}.bak.*"
    backups = sorted(path.parent.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True)
    for old_backup in backups[3:]:
        shutil.rmtree(str(old_backup), ignore_errors=True)
        logger.info(f"  [backup-cleanup] Backup antiguo eliminado: {old_backup.name}")

    # Crear symlink al nuevo destino en .agent/
    new_target = path.parent.parent / ".agent" / path.name
    if new_target.exists():
        try:
            os.symlink(str(new_target), str(path), target_is_directory=True)
            logger.info(f"  [symlink] {path.name} -> .agent/{path.name}")
        except OSError:
            pass  # En Windows puede requerir privilegios - ok si falla


def remove_legacy_claude_dirs(target_dir: Path) -> None:
    """Mueve rutas legacy de Claude a backup rotativo y crea symlinks al runtime .agent/."""
    for dirname in LEGACY_CLAUDE_DIRS:
        path = target_dir / ".claude" / dirname
        if not path.exists():
            continue
        try:
            if path.is_dir():
                safe_remove_legacy(path)
            else:
                path.unlink()
            logger.info(f"🧹 [.claude/{dirname}] Eliminado legado local")
        except Exception as exc:
            logger.warning(f"⚠️  [.claude/{dirname}] No se pudo limpiar: {exc}")


def merge_tree(
    src: Path,
    dst: Path,
    exclude: frozenset[str] | None = None,
) -> int:
    """Copia/actualiza un arbol sin borrar extras del destino.

    Args:
        src: Directorio o archivo fuente.
        dst: Destino donde copiar.
        exclude: Nombres de archivo a omitir en el nivel raíz de src.
    """
    if not src.exists():
        return 0
    if src.is_file():
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)
        return 1

    copied = 0
    ensure_dir(dst)
    for item in src.iterdir():
        if item.name in SKIP_TREE_NAMES:
            continue
        if exclude and item.name in exclude:
            continue
        target = dst / item.name
        if item.is_dir():
            copied += merge_tree(item, target)
        else:
            if item.resolve() == target.resolve():
                copied += 1
                continue
            ensure_dir(target.parent)
            shutil.copy2(item, target)
            copied += 1
    return copied


def copy_file(src: Path, dst: Path) -> bool:
    """Copia un archivo si existe."""
    if not src.exists():
        return False
    if src.resolve() == dst.resolve():
        return False
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)
    return True


def copy_path_if_needed(source: Path, target: Path) -> bool:
    """Copia un archivo o directorio solo si falta o cambió."""
    if not source.exists():
        return False

    if target.exists() and hash_tree(source) == hash_tree(target):
        return False

    if source.is_dir():
        merge_tree(source, target)
    else:
        copy_file(source, target)
    return True


def copy_named_entries(source_root: Path, target_root: Path, names: list[str]) -> list[str]:
    """Copia una lista de entradas nominales desde source_root hacia target_root."""
    copied: list[str] = []
    for name in sorted(set(names)):
        source = source_root / name
        target = target_root / name
        if copy_path_if_needed(source, target):
            copied.append(name)
    return copied


def iter_content_files(path: Path) -> list[Path]:
    """Lista archivos relevantes de un path para inspección heurística."""
    if not path.exists():
        return []
    if path.is_file():
        return [path]

    files: list[Path] = []
    for item in sorted(path.rglob("*")):
        if any(part in SKIP_TREE_NAMES for part in item.parts):
            continue
        if item.is_file():
            files.append(item)
    return files


def build_path_profile(path: Path) -> dict[str, bool]:
    """Resume el tipo de contenido presente en un archivo o directorio."""
    profile = {
        "has_code": False,
        "has_config": False,
        "has_docs": False,
        "has_behavior_docs": False,
    }
    for file_path in iter_content_files(path):
        suffix = file_path.suffix.lower()
        name = file_path.name.lower()
        normalized_parts = {part.lower() for part in file_path.parts}

        is_behavior_doc = name in {"skill.md", "identity.md"} or "commands" in normalized_parts
        if is_behavior_doc:
            profile["has_behavior_docs"] = True
            continue

        if suffix in CODE_EXTENSIONS:
            profile["has_code"] = True
        elif suffix in CONFIG_EXTENSIONS:
            profile["has_config"] = True
        elif suffix in DOC_EXTENSIONS:
            profile["has_docs"] = True

    return profile


def backup_path(source: Path, backup_root: Path, relative_name: str) -> str | None:
    """Guarda una copia previa antes de sobrescribir un elemento del repo."""
    if not source.exists():
        return None

    destination = backup_root / relative_name
    if source.is_dir():
        merge_tree(source, destination)
    else:
        copy_file(source, destination)
    return normalize_path(destination)


def get_claude_desktop_config_path() -> Path:
    """Obtiene la ruta global del config de Claude Desktop."""
    appdata = os.environ.get("APPDATA")
    if appdata:
        return Path(appdata) / "Claude" / "claude_desktop_config.json"

    home = Path.home()
    if os.name == "posix":
        if sys.platform == "darwin":
            return (
                home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
            )
        return home / ".config" / "Claude" / "claude_desktop_config.json"
    return Path("")


def get_claude_code_global_dir() -> Path:
    """Obtiene la carpeta global de Claude Code (~/.claude)."""
    return Path.home() / ".claude"


def _is_absolute_local_path(value: str) -> bool:
    """Detecta rutas absolutas locales Windows/POSIX."""
    if not value:
        return False
    return bool(re.match(r"^[a-zA-Z]:[\\/]", value)) or value.startswith(("/", "\\\\"))


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


def detect_project_type(target_dir: Path) -> str:
    """Detecta el tipo de proyecto: python, js, mixed o unknown."""
    has_python = (
        (target_dir / "pyproject.toml").exists()
        or (target_dir / "requirements.txt").exists()
        or (target_dir / "setup.py").exists()
        or any(target_dir.glob("*.py"))
    )
    has_js = (
        (target_dir / "package.json").exists()
        or (target_dir / "package-lock.json").exists()
        or (target_dir / "yarn.lock").exists()
        or (target_dir / "bun.lockb").exists()
    )
    if has_python and has_js:
        return "mixed"
    if has_python:
        return "python"
    if has_js:
        return "js"
    return "unknown"


def runtime_roots(repo_root: Path, target_dir: Path | None = None) -> tuple[Path, Path]:
    """Devuelve los roots del runtime local si ya fue instalado."""
    if target_dir is not None:
        local_mcp_root = target_dir / "mcp-server"
        local_agent_root = target_dir / ".agent"
        if local_mcp_root.exists() and local_agent_root.exists():
            return local_mcp_root, local_agent_root
    return repo_root / "mcp-server", repo_root / ".agent"


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


def is_remote_gateway_url(gateway_url: str) -> bool:
    """Determina si el gateway apunta a un endpoint remoto y no al localhost por defecto."""
    normalized = gateway_url.strip().lower()
    if not normalized:
        return False
    return not (
        normalized.startswith("http://localhost")
        or normalized.startswith("http://127.0.0.1")
        or normalized.startswith("https://localhost")
        or normalized.startswith("https://127.0.0.1")
    )


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

    persona_env = {"ANTIGRAVITY_PERSONA": os.environ.get("ANTIGRAVITY_PERSONA", "gentleman")}

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


def safe_merge_json(file_path: Path, new_servers: dict[str, Any]) -> bool:
    """Mergea servidores MCP sobre un JSON basado en mcpServers."""
    config = read_json_file(file_path)
    current_servers = config.get("mcpServers")
    if not isinstance(current_servers, dict):
        current_servers = {}
    current_servers, removed = prune_invalid_local_mcp_servers(current_servers)
    if removed:
        logger.info(
            "🧹 [MCP] Servidores locales inválidos removidos de %s: %s",
            file_path.name,
            ", ".join(sorted(removed)),
        )
    current_servers.update(new_servers)
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
            "🧹 [Zed MCP] Servidores locales inválidos removidos de %s: %s",
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
            "🧹 [Continue MCP] %d servidor(es) locales inválidos removidos de %s",
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


def install_antigravity_config(
    target_dir: Path,
    repo_root: Path,
    enable_dev_preset: bool = True,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    token: str = "",
) -> bool:
    """Crea .antigravity/config.json con la configuracion REST del ecosistema."""
    if not _validate_target_dir(target_dir):
        return False
    config_dir = target_dir / ".antigravity"
    ensure_dir(config_dir)

    mcp_servers = [
        "antigravity",
        "antigravity-agents",
        "antigravity-skills",
        "antigravity-observations",
        "antigravity-intelligence",
        "antigravity-ui",
        "antigravity-watcher",
        "antigravity-context-engine",
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


def install_sdk_python(target_dir: Path, repo_root: Path) -> bool:
    """Copia el SDK Python al proyecto destino."""
    sdk_source = repo_root / ".agent" / "sdk" / "client.py"
    sdk_init_source = repo_root / ".agent" / "sdk" / "__init__.py"
    sdk_dest_dir = target_dir / ".antigravity" / "sdk"

    if not sdk_source.exists():
        logger.warning(f"⚠️  [SDK Python] No se encontro el SDK en {sdk_source}")
        return False

    ensure_dir(sdk_dest_dir)
    try:
        shutil.copy2(sdk_source, sdk_dest_dir / "client.py")
        if sdk_init_source.exists():
            shutil.copy2(sdk_init_source, sdk_dest_dir / "__init__.py")
        else:
            (sdk_dest_dir / "__init__.py").write_text(
                'from .client import Client\n__all__ = ["Client"]\n',
                encoding="utf-8",
            )
        logger.info("✅ [SDK Python] Instalado en .antigravity/sdk/")
        return True
    except Exception as exc:
        logger.error(f"❌ [SDK Python] Error al copiar SDK: {exc}")
        return False


def install_sdk_js(target_dir: Path) -> bool:
    """Crea un helper JS/TS para conectarse al gateway REST."""
    sdk_dest_dir = target_dir / ".antigravity" / "sdk"
    ensure_dir(sdk_dest_dir)

    helper_content = """\
// Antigravity SDK - Cliente REST para el ecosistema
const GATEWAY_URL = process.env.ANTIGRAVITY_GATEWAY ?? "http://localhost:4747";

export async function runAgent(agentName, task, timeout = 30000) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(`${GATEWAY_URL}/agents/${agentName}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task }),
      signal: controller.signal,
    });
    if (!res.ok) throw new Error(`Gateway error: ${res.status}`);
    return await res.json();
  } finally {
    clearTimeout(timer);
  }
}

export async function listAgents() {
  const res = await fetch(`${GATEWAY_URL}/agents`);
  if (!res.ok) throw new Error(`Gateway error: ${res.status}`);
  return res.json();
}

export async function healthCheck() {
  const res = await fetch(`${GATEWAY_URL}/health`);
  if (!res.ok) throw new Error(`Gateway error: ${res.status}`);
  return res.json();
}
"""
    helper_path = sdk_dest_dir / "antigravity.js"
    try:
        helper_path.write_text(helper_content, encoding="utf-8")
        logger.info("✅ [SDK JS] Instalado en .antigravity/sdk/antigravity.js")
        return True
    except Exception as exc:
        logger.error(f"❌ [SDK JS] Error al crear helper: {exc}")
        return False


def install_example(target_dir: Path, project_type: str) -> bool:
    """Crea un ejemplo de uso del ecosistema."""
    examples_dir = target_dir / ".antigravity"
    ensure_dir(examples_dir)

    if project_type in ("python", "mixed"):
        content = """\
# Ejemplo: conectar tu app Python al ecosistema Antigravity
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "sdk"))
from client import Client

client = Client()
print(client.health())
print(client.list_agents())
"""
        path = examples_dir / "example.py"
    else:
        content = """\
import { runAgent, listAgents, healthCheck } from "./.antigravity/sdk/antigravity.js";

async function main() {
  console.log(await healthCheck());
  console.log(await listAgents());
  console.log(await runAgent("explorer", "analiza el proyecto"));
}

main().catch(console.error);
"""
        path = examples_dir / "example.js"

    try:
        path.write_text(content, encoding="utf-8")
        logger.info(f"✅ [Ejemplo] Creado {path.relative_to(target_dir)}")
        return True
    except Exception as exc:
        logger.error(f"❌ [Ejemplo] Error al crear ejemplo: {exc}")
        return False


def update_markdown_section(
    path: Path,
    start_marker: str,
    end_marker: str,
    section: str,
) -> bool:
    """Inserta o reemplaza una seccion delimitada por marcadores."""
    existing = ""
    if path.exists():
        try:
            existing = path.read_text(encoding="utf-8")
        except Exception as exc:
            logger.error(f"❌ [Docs] Error leyendo {path}: {exc}")
            return False

    if start_marker in existing and end_marker in existing:
        start_idx = existing.index(start_marker)
        end_idx = existing.index(end_marker) + len(end_marker)
        new_content = existing[:start_idx].rstrip() + "\n\n" + section + "\n"
        if end_idx < len(existing):
            new_content += existing[end_idx:].lstrip("\n")
    else:
        separator = "\n\n---\n\n" if existing.strip() else ""
        new_content = existing.rstrip() + separator + section + "\n"

    try:
        path.write_text(new_content, encoding="utf-8")
        return True
    except Exception as exc:
        logger.error(f"❌ [Docs] Error escribiendo {path}: {exc}")
        return False


def update_claude_md(target_dir: Path, project_type: str) -> bool:
    """Crea o actualiza CLAUDE.md con la seccion de integracion Antigravity."""
    start = "<!-- ANTIGRAVITY-START -->"
    end = "<!-- ANTIGRAVITY-END -->"
    sdk_blocks: list[str] = []
    if project_type in ("python", "mixed"):
        sdk_blocks.append(
            """### SDK Python

```python
from .antigravity.sdk.client import Client
client = Client()
result = client.run("explorer", "analiza el repo")
```"""
        )
    if project_type in ("js", "mixed"):
        sdk_blocks.append(
            """### SDK JS/TS

```js
import { runAgent } from "./.antigravity/sdk/antigravity.js";
const result = await runAgent("explorer", "analiza el repo");
```"""
        )

    persona_mode = os.environ.get("ANTIGRAVITY_PERSONA", "gentleman")
    section = f"""{start}

## Integracion Antigravity

Proyecto integrado con **Antigravity v{ECOSYSTEM_VERSION}**.
Instalado por Nexus el {datetime.now().strftime("%Y-%m-%d")}.

### Persona activa: {persona_mode}

El estilo de comunicacion de la IA se adapta segun el modo de persona.
Modos disponibles: `gentleman` (detallado, pedagogico), `neutral` (factual),
`conciso` (minimalista). Configurar via `ANTIGRAVITY_PERSONA` env var o
`.antigravity/config.json`. Ver `.claude/rules/persona.md` para detalles.

### Runtime MCP-first

```
.agent/
  agents/ skills/ skills-custom/ workflows/
  scripts/ core/ mcp/ plugins/
.claude/
  settings.json hooks/ rules/
.antigravity/
  config.json sdk/ ai_manifest.json rules.md
```

### Clientes compatibles

- Claude Code: `.claude/settings.json` + `.mcp.json`
- Cursor: `.cursor/mcp.json` + `.cursorrules`
- Windsurf: `.windsurf/mcp.json` + `.windsurfrules`
- VS Code / Roo / Cline: `.vscode/mcp.json` y `.vscode/cline_mcp_settings.json`
- Zed: `.zed/settings.json`
- Cualquier IA/IDE con MCP: `.mcp.json` y `.antigravity/ai_manifest.json`

{chr(10).join(sdk_blocks)}

### Memoria

- Memoria MCP: `antigravity-memory` (mem0)
- Memoria de proyecto: `ESTADO_PROYECTO.md`
- Reglas compartidas: `.claude/rules/` y `.antigravity/rules.md`

{end}"""
    ok = update_markdown_section(target_dir / "CLAUDE.md", start, end, section)
    if ok:
        logger.info("✅ [CLAUDE.md] Integracion actualizada")
    return ok


def update_agents_md(target_dir: Path) -> bool:
    """Crea o actualiza AGENTS.md con una seccion de integracion portable."""
    start = "<!-- ANTIGRAVITY-AGENTS-START -->"
    end = "<!-- ANTIGRAVITY-AGENTS-END -->"
    section = f"""{start}

## Integracion Antigravity

- Runtime local: `.agent/` contiene agentes, skills, workflows, core y servidores MCP.
- Claude Code: usa `.claude/settings.json` en modo ligero y resuelve capacidades por MCP.
- Codex: usa `AGENTS.md` del repo y, si el inyector detecta Codex, sincroniza skills curadas, skills propias de Antigravity y comandos portables como `finalize` en `~/.codex/skills`.
- MiniMax: si detectamos Claude Code o Codex, el inyector puede integrar también las skills oficiales de `MiniMax-AI/skills`.
- MCP universal: revisa `.mcp.json`, `.cursor/mcp.json`, `.windsurf/mcp.json`, `.vscode/mcp.json` y `.zed/settings.json`.
- Memoria: `antigravity-memory` (mem0) y la memoria del proyecto en `ESTADO_PROYECTO.md`.
- Reglas compartidas: `RULES.md`, `WORKFLOW_RULES.md`, `.antigravity/rules.md`.

{end}"""
    ok = update_markdown_section(target_dir / "AGENTS.md", start, end, section)
    if ok:
        logger.info("✅ [AGENTS.md] Integracion actualizada")
    return ok


def install_project_memory(target_dir: Path, repo_root: Path) -> bool:
    """Crea ESTADO_PROYECTO.md desde template si no existe."""
    estado_path = target_dir / "ESTADO_PROYECTO.md"
    template_path = repo_root / ".agent" / "templates" / "ESTADO_PROYECTO.md"

    if estado_path.exists():
        logger.info("   [Memoria] ESTADO_PROYECTO.md ya existe, no se toca")
        return True

    today = datetime.now().strftime("%Y-%m-%d")
    if template_path.exists():
        content = template_path.read_text(encoding="utf-8")
        content = content.replace("{NOMBRE_PROYECTO}", target_dir.name)
        content = content.replace("{FECHA_HOY}", today)
    else:
        content = f"""# ESTADO DEL PROYECTO — {target_dir.name}

> Ultima actualizacion: {today}

## Resumen Ejecutivo

- Proyecto integrado al ecosistema Antigravity.
"""

    try:
        estado_path.write_text(content, encoding="utf-8")
        logger.info(f"✅ [Memoria] Creado {estado_path.name}")
        return True
    except Exception as exc:
        logger.error(f"❌ [Memoria] Error al crear {estado_path.name}: {exc}")
        return False


def install_skills_as_commands(
    target_dir: Path,
    repo_root: Path,
    global_mode: bool = False,
) -> bool:
    """Sincroniza skills nativas de Claude Code en .claude/skills."""
    global _sync_skills_module
    if _sync_skills_module is None:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "sync_skills_to_claude",
                Path(__file__).parent / "sync_skills_to_claude.py",
            )
            if spec is None or spec.loader is None:
                raise ImportError("spec not found")
            _sync_skills_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_sync_skills_module)
        except Exception as exc:
            logger.warning(f"⚠️  [Claude Skills] No se pudo cargar sync_skills_to_claude.py: {exc}")
            return False

    stats = _sync_skills_module.sync_skills(
        target_dir=target_dir,
        repo_root=repo_root,
        global_mode=global_mode,
    )
    created = stats.get("created", 0)
    if created > 0:
        logger.info(f"✅ [Claude Skills] {created} skills sincronizadas en .claude/skills")
        return True
    logger.info("   [Claude Skills] Sin cambios (ya estaban sincronizadas)")
    return False


def install_codex_skills(
    target_dir: Path,
    *,
    codex_skill_profile: str = "smart",
    codex_home: str | None = None,
) -> bool:
    """Sincroniza skills curadas de openai/skills en $CODEX_HOME/skills."""
    global _sync_codex_skills_module
    if _sync_codex_skills_module is None:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "sync_skills_to_codex",
                Path(__file__).parent / "sync_skills_to_codex.py",
            )
            if spec is None or spec.loader is None:
                raise ImportError("spec not found")
            _sync_codex_skills_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_sync_codex_skills_module)
        except Exception as exc:
            logger.warning(f"⚠️  [Codex Skills] No se pudo cargar sync_skills_to_codex.py: {exc}")
            return False

    try:
        result = _sync_codex_skills_module.sync_codex_skills(
            target_dir=target_dir,
            codex_home=codex_home,
            profile=codex_skill_profile,
        )
    except Exception as exc:
        logger.warning(f"⚠️  [Codex Skills] Falló la sincronización: {exc}")
        return False

    installed = len(result.get("installed", []))
    skipped = len(result.get("skipped", []))
    if installed or skipped:
        logger.info(
            "✅ [Codex Skills] %s instaladas, %s omitidas en %s",
            installed,
            skipped,
            result.get("codex_home", codex_home or "~/.codex"),
        )
    if result.get("errors"):
        logger.warning(f"⚠️  [Codex Skills] {len(result['errors'])} error(es) durante sync")
    return installed > 0


def install_minimax_skills(
    target_dir: Path,
    *,
    codex_home: str | None = None,
    include_codex: bool = True,
    include_claude: bool = True,
) -> bool:
    """Integra skills oficiales de MiniMax para Codex y Claude Code."""
    global _sync_minimax_skills_module
    if _sync_minimax_skills_module is None:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "sync_minimax_skills",
                Path(__file__).parent / "sync_minimax_skills.py",
            )
            if spec is None or spec.loader is None:
                raise ImportError("spec not found")
            _sync_minimax_skills_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_sync_minimax_skills_module)
        except Exception as exc:
            logger.warning(f"⚠️  [MiniMax Skills] No se pudo cargar sync_minimax_skills.py: {exc}")
            return False

    try:
        result = _sync_minimax_skills_module.sync_minimax_skills(
            target_dir=target_dir,
            codex_home=codex_home,
            install_codex=include_codex,
            install_claude=include_claude,
        )
    except Exception as exc:
        logger.warning(f"⚠️  [MiniMax Skills] Falló la integración: {exc}")
        return False

    logger.info("✅ [MiniMax Skills] Integración ejecutada")
    return bool(result.get("codex") or result.get("claude"))


def install_superpowers(
    target_dir: Path,
    *,
    codex_home: str | None = None,
) -> bool:
    """Integra obra/superpowers en las apps soportadas del entorno local."""
    global _sync_superpowers_module
    if _sync_superpowers_module is None:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "sync_superpowers",
                Path(__file__).parent / "sync_superpowers.py",
            )
            if spec is None or spec.loader is None:
                raise ImportError("spec not found")
            _sync_superpowers_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_sync_superpowers_module)
        except Exception as exc:
            logger.warning(f"⚠️  [Superpowers] No se pudo cargar sync_superpowers.py: {exc}")
            return False

    try:
        result = _sync_superpowers_module.sync_superpowers(
            target_dir=target_dir,
            codex_home=codex_home,
        )
    except Exception as exc:
        logger.warning(f"⚠️  [Superpowers] Falló la integración: {exc}")
        return False

    logger.info("✅ [Superpowers] Integración ejecutada")
    return any(
        result.get(key) is not None
        for key in ("codex", "claude", "cursor", "opencode", "gemini", "copilot")
    )


def install_brainstorming_planning(target_dir: Path) -> bool:
    """Instala el skill brainstorming-planning como skill local cross-app."""
    global _sync_brainstorming_planning_module
    if _sync_brainstorming_planning_module is None:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "sync_brainstorming_planning",
                Path(__file__).parent / "sync_brainstorming_planning.py",
            )
            if spec is None or spec.loader is None:
                raise ImportError("spec not found")
            _sync_brainstorming_planning_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_sync_brainstorming_planning_module)
        except Exception as exc:
            logger.warning(
                f"⚠️  [Brainstorming Planning] No se pudo cargar sync_brainstorming_planning.py: {exc}"
            )
            return False

    try:
        result = _sync_brainstorming_planning_module.sync_brainstorming_planning(
            target_dir=target_dir,
        )
    except Exception as exc:
        logger.warning(f"⚠️  [Brainstorming Planning] Falló la integración: {exc}")
        return False

    logger.info("✅ [Brainstorming Planning] Integración ejecutada")
    return any(result.get(key) is not None for key in ("codex", "claude", "cursor", "opencode"))


def install_oh_my_claudecode(
    target_dir: Path,
    *,
    codex_home: str | None = None,
) -> bool:
    """Integra oh-my-claudecode en las apps soportadas del entorno local."""
    global _sync_oh_my_claudecode_module
    if _sync_oh_my_claudecode_module is None:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "sync_oh_my_claudecode",
                Path(__file__).parent / "sync_oh_my_claudecode.py",
            )
            if spec is None or spec.loader is None:
                raise ImportError("spec not found")
            _sync_oh_my_claudecode_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_sync_oh_my_claudecode_module)
        except Exception as exc:
            logger.warning(
                f"⚠️  [oh-my-claudecode] No se pudo cargar sync_oh_my_claudecode.py: {exc}"
            )
            return False

    try:
        result = _sync_oh_my_claudecode_module.sync_oh_my_claudecode(
            target_dir=target_dir,
            codex_home=codex_home,
        )
    except Exception as exc:
        logger.warning(f"⚠️  [oh-my-claudecode] Falló la integración: {exc}")
        return False

    logger.info("✅ [oh-my-claudecode] Integración ejecutada")
    return any(result.get(key) is not None for key in ("codex", "claude", "cursor", "opencode"))


def install_external_skill_bundle(
    target_dir: Path,
    *,
    codex_home: str | None = None,
    include_superpowers: bool = True,
    include_brainstorming_planning: bool = True,
    include_oh_my_claudecode: bool = True,
) -> bool:
    """Instala el bundle de skills/plugins externos soportados por Antigravity."""
    installed_any = False

    if include_superpowers:
        installed_any = (
            install_superpowers(
                target_dir,
                codex_home=codex_home,
            )
            or installed_any
        )

    if include_brainstorming_planning:
        installed_any = install_brainstorming_planning(target_dir) or installed_any

    if include_oh_my_claudecode:
        installed_any = (
            install_oh_my_claudecode(
                target_dir,
                codex_home=codex_home,
            )
            or installed_any
        )

    return installed_any


def audit_vendored_external_skills(
    repo_root: Path,
    *,
    package_names: list[str] | None = None,
) -> dict[str, Any]:
    """Audita snapshots vendorizados contra upstream sin actualizarlos."""
    global _update_vendored_external_skills_module
    if _update_vendored_external_skills_module is None:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "update_vendored_external_skills",
                Path(__file__).parent / "update_vendored_external_skills.py",
            )
            if spec is None or spec.loader is None:
                raise ImportError("spec not found")
            _update_vendored_external_skills_module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = _update_vendored_external_skills_module
            spec.loader.exec_module(_update_vendored_external_skills_module)
        except Exception as exc:
            raise RuntimeError("No se pudo cargar update_vendored_external_skills.py") from exc

    return _update_vendored_external_skills_module.audit_vendor_snapshots(
        repo_root=repo_root,
        package_names=package_names,
    )


def install_antigravity_codex_assets(
    target_dir: Path,
    repo_root: Path,
    *,
    codex_home: str | None = None,
) -> bool:
    """Expone skills propias de Antigravity y comandos de Claude como skills globales de Codex."""
    global _sync_antigravity_codex_assets_module
    if _sync_antigravity_codex_assets_module is None:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "sync_antigravity_assets_to_codex",
                Path(__file__).parent / "sync_antigravity_assets_to_codex.py",
            )
            if spec is None or spec.loader is None:
                raise ImportError("spec not found")
            _sync_antigravity_codex_assets_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_sync_antigravity_codex_assets_module)
        except Exception as exc:
            logger.warning(
                f"⚠️  [Antigravity Codex Assets] No se pudo cargar sync_antigravity_assets_to_codex.py: {exc}"
            )
            return False

    try:
        result = _sync_antigravity_codex_assets_module.sync_antigravity_assets_to_codex(
            target_dir=target_dir,
            repo_root=repo_root,
            codex_home=codex_home,
        )
    except Exception as exc:
        logger.warning(f"⚠️  [Antigravity Codex Assets] Falló la sincronización: {exc}")
        return False

    installed = len(result.get("installed", []))
    if installed:
        logger.info(
            "✅ [Antigravity Codex Assets] %s skills/comandos exportados a %s",
            installed,
            result.get("codex_home", codex_home or "~/.codex"),
        )
    return installed > 0


def install_codex_config(
    repo_root: Path,
    *,
    codex_home: str | None = None,
) -> bool:
    """Sincroniza servidores MCP del proyecto hacia `$CODEX_HOME/config.toml` (add-only)."""
    global _sync_codex_config_module
    if _sync_codex_config_module is None:
        try:
            import importlib.util

            spec = importlib.util.spec_from_file_location(
                "sync_codex_config",
                Path(__file__).parent / "sync_codex_config.py",
            )
            if spec is None or spec.loader is None:
                raise ImportError("spec not found")
            _sync_codex_config_module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(_sync_codex_config_module)
        except Exception as exc:
            logger.warning(f"⚠️  [Codex Config] No se pudo cargar sync_codex_config.py: {exc}")
            return False

    try:
        result = _sync_codex_config_module.sync_codex_config(
            repo_root=repo_root,
            codex_home=codex_home,
        )
    except Exception as exc:
        logger.warning(f"⚠️  [Codex Config] Falló la sincronización de config: {exc}")
        return False

    added = result.get("added", [])
    if added:
        logger.info(
            "✅ [Codex Config] %s servidores MCP agregados en %s",
            len(added),
            result.get("config_path", "~/.codex/config.toml"),
        )
        return True

    logger.info("   [Codex Config] Sin cambios (todos los servidores MCP ya existían)")
    return False


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


def collect_runtime_fingerprint(target_dir: Path) -> dict[str, Any]:
    """Genera fingerprint SHA-256 de archivos críticos del runtime inyectado."""
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
        "personaConfig": {
            "mode": os.environ.get("ANTIGRAVITY_PERSONA", "gentleman"),
            "language": "es",
            "tone": "direct",
        },
    }
    ok = write_json_file(target_dir / ".antigravity" / "ai_manifest.json", payload)
    if ok:
        logger.info("✅ [Manifest] Creado .antigravity/ai_manifest.json")
    return ok


def generate_ide_rules(target_dir: Path, repo_root: Path) -> None:
    """Genera .cursorrules, .windsurfrules y .clinerules con valores dinámicos del ecosistema."""
    # Count agents (excluding _deprecated), preferring target_dir if already populated
    agents_dir = target_dir / ".agent" / "agents"
    if not agents_dir.exists():
        agents_dir = repo_root / ".agent" / "agents"
    num_agents = 0
    if agents_dir.exists():
        num_agents = sum(1 for d in agents_dir.iterdir() if d.is_dir() and d.name != "_deprecated")

    # Count skills
    skills_dir = target_dir / ".agent" / "skills"
    if not skills_dir.exists():
        skills_dir = repo_root / ".agent" / "skills"
    num_skills = 0
    if skills_dir.exists():
        num_skills = sum(
            1 for d in skills_dir.iterdir() if d.is_dir() and not d.name.startswith("_")
        )

    # Read gateway URL from config, falling back to default
    gateway_url = DEFAULT_GATEWAY_URL
    for config_path in [
        target_dir / ".antigravity" / "config.json",
        repo_root / ".antigravity" / "config.json",
    ]:
        if config_path.exists():
            try:
                cfg = read_json_file(config_path)
                gateway_url = cfg.get("gateway", DEFAULT_GATEWAY_URL)
                break
            except Exception:
                pass

    mcp_servers_list = (
        "antigravity, antigravity-agents, antigravity-skills, "
        "antigravity-observations, antigravity-intelligence, "
        "antigravity-ui, antigravity-memory, antigravity-watcher, "
        "antigravity-context-engine, stitch"
    )

    rules_content = f"""# Antigravity Ecosystem Rules

This project uses **Antigravity v{ECOSYSTEM_VERSION}** — a modular AI runtime
with {num_agents} active agents and {num_skills} skills.

## MCP Gateway

- Local gateway: `{gateway_url}` (localhost:4747)
- Active MCP servers: {mcp_servers_list}

## Agent Protocol

1. Read `.agent/agents/<name>/SYSTEM_PROMPT.md` before delegating tasks.
2. Use the MCP server `antigravity-agents` to invoke agents via the gateway.
3. Use `antigravity-skills` to load modular skills on demand.

## Key Directories

- `.agent/agents/`   — {num_agents} agents (tier 1–7)
- `.agent/skills/`   — {num_skills} skills
- `.agent/workflows/` — multi-agent orchestration workflows
- `.antigravity/`    — config, manifest, rules, SDK
- `.mcp.json`        — MCP server configuration

## Rules

- Always prefer agent-delegated tasks over inline code for complex operations.
- Read `ESTADO_PROYECTO.md` for current project memory before starting work.
- Respect `.antigravity/rules.md` and `.claude/rules/` for project-specific constraints.
"""

    rule_files = [
        target_dir / ".cursorrules",
        target_dir / ".windsurfrules",
        target_dir / ".clinerules",
    ]
    _TAG_START = "<!-- ANTIGRAVITY-RULES-START -->"
    _TAG_END = "<!-- ANTIGRAVITY-RULES-END -->"
    wrapped_content = f"{_TAG_START}\n{rules_content}\n{_TAG_END}"
    for rule_file in rule_files:
        try:
            if rule_file.exists():
                existing = rule_file.read_text(encoding="utf-8")
                if _TAG_START in existing and _TAG_END in existing:
                    start_idx = existing.index(_TAG_START)
                    end_idx = existing.index(_TAG_END) + len(_TAG_END)
                    new_text = existing[:start_idx] + wrapped_content + existing[end_idx:]
                else:
                    new_text = existing + f"\n---\n{wrapped_content}"
            else:
                new_text = wrapped_content
            rule_file.write_text(new_text, encoding="utf-8")
            logger.info(
                f"✅ [Reglas] {rule_file.name} generado "
                f"({num_agents} agentes, {num_skills} skills, gateway={gateway_url})"
            )
        except Exception as exc:
            logger.error(f"❌ [Reglas] No se pudo escribir {rule_file.name}: {exc}")


def install_copilot_instructions(target_dir: Path, repo_root: Path) -> bool:
    """Escribe .github/copilot-instructions.md con contexto del ecosistema Antigravity."""
    # Group agents by tier (reading agent.json from repo_root)
    agents_dir = repo_root / ".agent" / "agents"
    tiers: dict[int, list[str]] = {}
    unlisted: list[str] = []

    if agents_dir.exists():
        for agent_dir in sorted(agents_dir.iterdir()):
            if not agent_dir.is_dir() or agent_dir.name == "_deprecated":
                continue
            cfg_path = agent_dir / "agent.json"
            if cfg_path.exists():
                try:
                    cfg = read_json_file(cfg_path)
                    tier = int(cfg.get("tier", 0))
                    tiers.setdefault(tier, []).append(agent_dir.name)
                except Exception:
                    unlisted.append(agent_dir.name)
            else:
                unlisted.append(agent_dir.name)

    num_agents = sum(len(v) for v in tiers.values()) + len(unlisted)

    # Read gateway URL
    gateway_url = DEFAULT_GATEWAY_URL
    for config_path in [
        target_dir / ".antigravity" / "config.json",
        repo_root / ".antigravity" / "config.json",
    ]:
        if config_path.exists():
            try:
                cfg = read_json_file(config_path)
                gateway_url = cfg.get("gateway", DEFAULT_GATEWAY_URL)
                break
            except Exception:
                pass

    # Build tier sections
    tier_lines: list[str] = []
    for tier_num in sorted(tiers.keys()):
        tier_lines.append(f"\n### Tier {tier_num}")
        for agent_name in tiers[tier_num]:
            tier_lines.append(f"- `{agent_name}`")
    if unlisted:
        tier_lines.append(f"\n### Specialized / No-tier ({len(unlisted)} agents)")
        for agent_name in unlisted[:10]:
            tier_lines.append(f"- `{agent_name}`")
        if len(unlisted) > 10:
            tier_lines.append(f"- _(and {len(unlisted) - 10} more — see `.agent/agents/`)_")

    agent_section = "\n".join(tier_lines)

    content = f"""<!-- ANTIGRAVITY-START -->
# GitHub Copilot Instructions — Antigravity Ecosystem

This workspace runs **Antigravity v{ECOSYSTEM_VERSION}** with {num_agents} agents
and a modular MCP runtime. Installed by Nexus on {datetime.now().strftime("%Y-%m-%d")}.

## Gateway & MCP Servers

- Local gateway: `{gateway_url}` (port 4747)
- Core servers: `antigravity`, `antigravity-agents`, `antigravity-skills`,
  `antigravity-observations`, `antigravity-intelligence`, `antigravity-ui`
- Memory: `antigravity-memory` (mem0)
- Process Watcher: `antigravity-watcher` (spawn + pattern matching reactivo)
- Context Engine: `antigravity-context-engine` (estrategias pluggable de contexto)
- Dev tools: `stitch`, `context7`, `git`, `filesystem`

## Agent Tiers
{agent_section}

## Key Entry Points

- `.mcp.json` — MCP server config (auto-generated, all IDEs)
- `.antigravity/config.json` — ecosystem config (gateway, version, policy)
- `.antigravity/ai_manifest.json` — machine-readable manifest for AI tools
- `.antigravity/rules.md` — project-specific rules
- `ESTADO_PROYECTO.md` — project memory (read before starting work)
- `.agent/agents/` — all agents (read `SYSTEM_PROMPT.md` per agent)
- `.agent/skills/` — modular skills library

## Workflow

1. For complex tasks, delegate to the appropriate agent via MCP `antigravity-agents`.
2. For skill-based work, use `antigravity-skills` to load the relevant skill.
3. Read `ESTADO_PROYECTO.md` before starting any session.
4. Respect constraints in `.antigravity/rules.md` and `.claude/rules/`.
<!-- ANTIGRAVITY-END -->
"""

    github_dir = target_dir / ".github"
    ensure_dir(github_dir)
    out_path = github_dir / "copilot-instructions.md"
    _TAG_START = "<!-- ANTIGRAVITY-START -->"
    _TAG_END = "<!-- ANTIGRAVITY-END -->"
    try:
        if out_path.exists():
            existing = out_path.read_text(encoding="utf-8")
            if _TAG_START in existing and _TAG_END in existing:
                start_idx = existing.index(_TAG_START)
                end_idx = existing.index(_TAG_END) + len(_TAG_END)
                final_content = existing[:start_idx] + content + existing[end_idx:]
            else:
                final_content = existing + f"\n---\n{content}"
        else:
            final_content = content
        out_path.write_text(final_content, encoding="utf-8")
        logger.info("✅ [Copilot] .github/copilot-instructions.md generado")
        return True
    except Exception as exc:
        logger.error(f"❌ [Copilot] No se pudo escribir copilot-instructions.md: {exc}")
        return False


def install_portable_runtime(
    target_dir: Path,
    repo_root: Path,
    sync_skills: bool = False,
    sync_codex_skills: bool = False,
    codex_skill_profile: str = "smart",
    codex_home: str | None = None,
    sync_minimax_skills: bool = False,
    sync_superpowers: bool = False,
    sync_brainstorming_planning: bool = False,
    sync_oh_my_claudecode: bool = False,
) -> None:
    """Instala el runtime portable local consumible por Claude Code y MCP."""
    logger.info("[RUNTIME] Instalando paquete portable local...")

    # Mejora 3: Diff visual por directorio principal
    logger.info("[DIFF] Vista previa de cambios:")
    for _diff_dir in ["agents", "skills", "scripts"]:
        _src = repo_root / ".agent" / _diff_dir
        _dst = target_dir / ".agent" / _diff_dir
        if _src.exists():
            logger.info(f"  .agent/{_diff_dir}:")
            show_injection_diff(_src, _dst)

    for dirname in PORTABLE_AGENT_DIRS:
        src = repo_root / ".agent" / dirname
        dst = target_dir / ".agent" / dirname
        # Mejora 4: Para agentes, comparar versión semántica antes de copiar
        if dirname == "agents" and src.exists():
            for agent_src in src.iterdir():
                if agent_src.is_dir():
                    agent_dst = dst / agent_src.name
                    if agent_dst.exists() and not should_update_agent(agent_src, agent_dst):
                        logger.info(f"  [skip] {agent_src.name} ya está en la versión más reciente")
                        continue
        copied = merge_tree(src, dst)
        if copied:
            logger.info(f"✅ [.agent/{dirname}] {copied} archivos sincronizados")

    if copy_file(repo_root / ".agent" / "VERSION", target_dir / ".agent" / "VERSION"):
        logger.info("✅ [.agent] VERSION sincronizado")

    mcp_server_src = repo_root / "mcp-server"
    mcp_server_dst = target_dir / "mcp-server"
    copied_server = merge_tree(mcp_server_src, mcp_server_dst)
    if copied_server:
        logger.info(f"✅ [mcp-server] {copied_server} archivos sincronizados")

    for dirname in CLAUDE_DIRS:
        src = repo_root / ".claude" / dirname
        dst = target_dir / ".claude" / dirname
        exclude = RULES_EXCLUDE if dirname == "rules" else None
        copied = merge_tree(src, dst, exclude=exclude)
        if copied:
            logger.info(f"✅ [.claude/{dirname}] {copied} archivos sincronizados")

    install_claude_settings(target_dir, repo_root)
    remove_legacy_claude_dirs(target_dir)

    context_src = repo_root / ".context"
    context_dst = target_dir / ".context"
    copied_context = merge_tree(context_src, context_dst)
    if copied_context:
        logger.info(f"✅ [.context] {copied_context} archivos sincronizados")

    antigravity_dir = target_dir / ".antigravity"
    ensure_dir(antigravity_dir)
    for filename in ANTIGRAVITY_FILES:
        if copy_file(repo_root / ".antigravity" / filename, antigravity_dir / filename):
            logger.info(f"✅ [.antigravity] {filename} sincronizado")

    for filename in ROOT_RULE_FILES:
        if copy_file(repo_root / filename, target_dir / filename):
            logger.info(f"✅ [Reglas] {filename} sincronizado")
    generate_ide_rules(target_dir, repo_root)

    install_project_memory(target_dir, repo_root)

    if sync_skills:
        install_skills_as_commands(target_dir, repo_root)
    if sync_codex_skills:
        install_codex_skills(
            target_dir,
            codex_skill_profile=codex_skill_profile,
            codex_home=codex_home,
        )
        install_antigravity_codex_assets(
            target_dir,
            repo_root,
            codex_home=codex_home,
        )
        install_codex_config(
            repo_root,
            codex_home=codex_home,
        )
    if sync_minimax_skills:
        install_minimax_skills(
            target_dir,
            codex_home=codex_home,
            include_codex=is_codex_available(),
            include_claude=is_claude_available(),
        )
    install_external_skill_bundle(
        target_dir,
        codex_home=codex_home,
        include_superpowers=sync_superpowers,
        include_brainstorming_planning=sync_brainstorming_planning,
        include_oh_my_claudecode=sync_oh_my_claudecode,
    )


def sync_global_claude_assets(repo_root: Path) -> bool:
    """Sincroniza commands/rules/hooks portables a ~/.claude para uso global."""
    global_claude_dir = get_claude_code_global_dir()
    ensure_dir(global_claude_dir)
    copied_any = False

    for dirname in CLAUDE_DIRS:
        src = repo_root / ".claude" / dirname
        dst = global_claude_dir / dirname
        exclude = RULES_EXCLUDE if dirname == "rules" else None
        copied = merge_tree(src, dst, exclude=exclude)
        if copied:
            copied_any = True
            logger.info(f"✅ [global .claude/{dirname}] {copied} archivos sincronizados")

    return copied_any


def hash_file(path: Path) -> str:
    """Calcula hash SHA-256 de un archivo."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_tree(path: Path) -> str:
    """Calcula hash estable de un directorio o archivo."""
    if path.is_file():
        return hash_file(path)

    digest = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if any(part in SKIP_TREE_NAMES for part in item.parts):
            continue
        relative = item.relative_to(path).as_posix().encode("utf-8")
        digest.update(relative)
        if item.is_file():
            digest.update(hash_file(item).encode("ascii"))
    return digest.hexdigest()


def compare_named_directories(
    source_root: Path,
    target_root: Path,
    *,
    skip_prefixes: tuple[str, ...] = ("_", "."),
) -> dict[str, Any]:
    """Compara directorios nombrados (agentes/skills) entre source y target."""
    source_names = (
        {
            item.name: item
            for item in source_root.iterdir()
            if (item.is_dir() or item.is_file()) and not item.name.startswith(skip_prefixes)
        }
        if source_root.exists()
        else {}
    )
    target_names = (
        {
            item.name: item
            for item in target_root.iterdir()
            if (item.is_dir() or item.is_file()) and not item.name.startswith(skip_prefixes)
        }
        if target_root.exists()
        else {}
    )

    new_items: list[str] = []
    updated_items: list[str] = []
    target_only_items: list[str] = []
    new_details: list[dict[str, str]] = []
    updated_details: list[dict[str, str]] = []
    target_only_details: list[dict[str, str]] = []
    unchanged = 0

    for name, source_path in sorted(source_names.items()):
        target_path = target_names.get(name)
        if target_path is None:
            new_items.append(name)
            new_details.append(build_change_detail(name, source_path, None, status="new"))
            continue
        if hash_tree(source_path) != hash_tree(target_path):
            updated_items.append(name)
            updated_details.append(
                build_change_detail(name, source_path, target_path, status="updated")
            )
        else:
            unchanged += 1

    for name in sorted(target_names):
        if name not in source_names:
            target_only_items.append(name)
            target_only_details.append(
                build_change_detail(name, None, target_names[name], status="targetOnly")
            )

    return {
        "sourceCount": len(source_names),
        "targetCount": len(target_names),
        "new": new_items,
        "updated": updated_items,
        "targetOnly": target_only_items,
        "unchanged": unchanged,
        "details": {
            "new": new_details,
            "updated": updated_details,
            "targetOnly": target_only_details,
        },
    }


def compare_paths(source: Path, target: Path) -> dict[str, Any]:
    """Compara un archivo o directorio concreto."""
    if not source.exists():
        return {"status": "missing_source"}
    if not target.exists():
        detail = classify_entry_change(source, None, status="new")
        return {"status": "new", **detail}
    if hash_tree(source) != hash_tree(target):
        detail = classify_entry_change(source, target, status="updated")
        return {"status": "updated", **detail}
    return {
        "status": "unchanged",
        "classification": "minor",
        "reason": "Sin diferencias detectadas.",
    }


# ---------------------------------------------------------------------------
# Smart Merge y Detección de Conflictos
# ---------------------------------------------------------------------------

_MD_EXTENSIONS = {".md"}


def parse_markdown_sections(content: str) -> dict[str, str]:
    """Divide un archivo markdown en secciones delimitadas por cabeceras ``##``.

    Args:
        content: Contenido completo del archivo markdown.

    Returns:
        Diccionario ``{header: body}`` donde *header* incluye el texto tras
        ``## `` y *body* es todo el contenido hasta la siguiente cabecera o
        el final del archivo.  El contenido previo a la primera cabecera se
        almacena bajo la clave ``"__preamble__"``.
    """
    sections: dict[str, str] = {}
    current_key = "__preamble__"
    buffer: list[str] = []

    for line in content.splitlines(keepends=True):
        if line.startswith("## "):
            sections[current_key] = "".join(buffer)
            current_key = line.strip().removeprefix("## ").strip()
            buffer = [line]
        else:
            buffer.append(line)

    sections[current_key] = "".join(buffer)
    return sections


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


def check_blocking_processes() -> list[str]:
    """Detecta si hay apps que podrían bloquear la inyección."""
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


def deploy_rules(
    target_project_path: str,
    templates_dir: str | None = None,
) -> dict[str, Any]:
    """Deploy injection rules to a target project.

    Copies rule templates to the target project's .claude/rules/ directory
    and optionally a CLAUDE.md if none exists. Never overwrites existing files.

    Args:
        target_project_path: Absolute path to the target project root.
        templates_dir: Path to templates directory.
            Defaults to .agent/templates/injection-rules/

    Returns:
        Dict with 'deployed', 'skipped' (already existed), and 'errors' lists.
    """
    target = Path(target_project_path).resolve()
    result: dict[str, Any] = {"deployed": [], "skipped": [], "errors": []}

    # Resolve templates directory
    if templates_dir:
        tpl_dir = Path(templates_dir).resolve()
    else:
        tpl_dir = Path(__file__).resolve().parent.parent / "templates" / "injection-rules"

    if not tpl_dir.exists() or not tpl_dir.is_dir():
        msg = f"Directorio de templates no encontrado: {tpl_dir}"
        logger.error(f"[RULES] {msg}")
        result["errors"].append(msg)
        return result

    if not target.exists() or not target.is_dir():
        msg = f"Directorio destino no existe: {target}"
        logger.error(f"[RULES] {msg}")
        result["errors"].append(msg)
        return result

    # Ensure target directories exist
    rules_dir = target / ".claude" / "rules"
    memory_dir = target / ".claude" / "memory"
    try:
        ensure_dir(rules_dir)
        ensure_dir(memory_dir)
    except OSError as exc:
        msg = f"No se pudo crear directorios .claude/: {exc}"
        logger.error(f"[RULES] {msg}")
        result["errors"].append(msg)
        return result

    # Mapping: template filename -> destination path
    template_files = sorted(tpl_dir.iterdir())
    for tpl_file in template_files:
        if not tpl_file.is_file():
            continue

        filename = tpl_file.name

        # Skip internal documentation
        if filename == "README.md":
            continue

        # Determine destination
        if filename == "CLAUDE.md":
            dest = target / "CLAUDE.md"
        else:
            dest = rules_dir / filename

        # Never overwrite existing files
        if dest.exists():
            logger.warning(f"[RULES] Omitido (ya existe): {dest}")
            result["skipped"].append(str(dest))
            continue

        # Copy template
        try:
            shutil.copy2(str(tpl_file), str(dest))
            logger.info(f"[RULES] Desplegado: {dest}")
            result["deployed"].append(str(dest))
        except OSError as exc:
            msg = f"Error copiando {tpl_file.name} -> {dest}: {exc}"
            logger.error(f"[RULES] {msg}")
            result["errors"].append(msg)

    return result


def install_full(
    target_dir: Path,
    repo_root: Path,
    enable_dev_preset: bool = True,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    token: str = "",
    sync_skills: bool = False,
    sync_codex_skills: bool = False,
    codex_skill_profile: str = "smart",
    codex_home: str | None = None,
    sync_minimax_skills: bool = False,
    sync_superpowers: bool = False,
    sync_brainstorming_planning: bool = False,
    sync_oh_my_claudecode: bool = False,
    deploy_rules_enabled: bool = True,
) -> None:
    """Instalacion completa: runtime local + SDK/config/docs + clientes MCP."""
    logger.info("\n[INFO] ================================================")
    logger.info("[INFO] Instalacion completa del ecosistema Antigravity")
    logger.info(f"[INFO] Proyecto: {target_dir}")
    logger.info(f"[INFO] Gateway: {gateway_url}")
    logger.info("[INFO] ================================================\n")

    # Mejora 2: Detección de procesos bloqueantes
    blocking = check_blocking_processes()
    if blocking:
        logger.warning("⚠️  Procesos activos detectados que pueden causar errores de acceso:")
        for p in blocking:
            logger.warning(f"   - {p}")
        logger.warning("   Considera cerrarlos antes de inyectar para evitar errores de acceso.")

    project_type = detect_project_type(target_dir)
    logger.info(f"[INFO] Tipo de proyecto detectado: {project_type.upper()}\n")

    total_steps = 9

    logger.info(f"[PASO 1/{total_steps}] Instalando runtime portable local...")
    install_portable_runtime(
        target_dir,
        repo_root,
        sync_skills=sync_skills,
        sync_codex_skills=sync_codex_skills,
        codex_skill_profile=codex_skill_profile,
        codex_home=codex_home,
        sync_minimax_skills=sync_minimax_skills,
        sync_superpowers=sync_superpowers,
        sync_brainstorming_planning=sync_brainstorming_planning,
        sync_oh_my_claudecode=sync_oh_my_claudecode,
    )

    # ── App Intelligence: análisis rápido del proyecto destino ──
    if INTELLIGENCE_AVAILABLE:
        logger.info("[INTELLIGENCE] Ejecutando análisis rápido del proyecto...")
        try:
            profile = quick_analyze(target_dir)
            save_profile(profile)
            write_app_knowledge(profile)
            logger.info(
                f"✅ [Intelligence] {profile.name}: "
                f"{profile.stack.get('language', '?')}/{profile.stack.get('framework', '?')} "
                f"— {len(profile.detected_patterns)} patrones detectados"
            )
        except Exception as exc:
            logger.warning(f"⚠️ [Intelligence] Análisis rápido falló (no bloqueante): {exc}")
    else:
        logger.info("[INTELLIGENCE] Pipeline no disponible, saltando análisis")

    logger.info(f"\n[PASO 2/{total_steps}] Configurando gateway y manifiestos...")
    install_antigravity_config(target_dir, repo_root, enable_dev_preset, gateway_url, token)
    manifest_ok = install_ai_manifest(
        target_dir,
        gateway_url,
        enable_dev_preset,
        mcp_enabled=True,
        remote_enabled=bool(token) or is_remote_gateway_url(gateway_url),
    )
    if not manifest_ok:
        raise RuntimeError(
            "[PASO 2] Fallo la creacion de .antigravity/ai_manifest.json — "
            "revisa permisos de escritura o errores en collect_runtime_fingerprint(). "
            f"Ruta destino: {target_dir / '.antigravity' / 'ai_manifest.json'}"
        )

    logger.info(f"\n[PASO 3/{total_steps}] Instalando SDK del ecosistema...")
    if project_type in ("python", "mixed"):
        install_sdk_python(target_dir, repo_root)
    if project_type in ("js", "mixed"):
        install_sdk_js(target_dir)
    if project_type == "unknown":
        logger.info("   (proyecto no Python/JS, se instala solo el runtime)")

    logger.info(f"\n[PASO 4/{total_steps}] Creando ejemplos de uso...")
    install_example(target_dir, project_type)

    logger.info(f"\n[PASO 5/{total_steps}] Actualizando documentacion local...")
    update_claude_md(target_dir, project_type)
    update_agents_md(target_dir)

    logger.info(f"\n[PASO 6/{total_steps}] Escribiendo configuraciones MCP...")
    workspace_ok = inject_workspace(
        target_dir,
        repo_root,
        enable_dev_preset,
        gateway_url=gateway_url,
        token=token,
    )
    if not workspace_ok:
        logger.warning(
            "[PASO 6] inject_workspace reportó fallos en uno o más clientes MCP — "
            "la instalación continúa pero revisa los errores anteriores"
        )

    logger.info(
        f"\n[PASO 7/{total_steps}] Configurando IDEs adicionales (Copilot, Gemini, Aider)..."
    )
    install_gemini_config(target_dir, repo_root)
    install_aider_config(target_dir)

    if deploy_rules_enabled:
        logger.info(f"\n[PASO 8/{total_steps}] Desplegando reglas de inyeccion...")
        rules_result = deploy_rules(str(target_dir))
        if rules_result["deployed"]:
            logger.info(f"   {len(rules_result['deployed'])} regla(s) desplegadas")
        if rules_result["skipped"]:
            logger.info(f"   {len(rules_result['skipped'])} regla(s) omitidas (ya existian)")
        if rules_result["errors"]:
            logger.warning(
                f"   {len(rules_result['errors'])} error(es) durante despliegue de reglas"
            )
    else:
        logger.info(f"\n[PASO 8/{total_steps}] Despliegue de reglas omitido (--no-rules)")

    logger.info(f"\n[PASO 9/{total_steps}] Verificacion final...")
    logger.info(f"   Runtime local: {target_dir / '.agent'}")
    logger.info(f"   Claude Code: {target_dir / '.claude'}")
    logger.info(f"   MCP universal: {target_dir / '.mcp.json'}")
    if not run_post_injection_smoke(target_dir):
        raise RuntimeError("Smoke post-inyección falló")
    _run_post_inject_hook(target_dir)

    logger.info("\n[INFO] ================================================")
    logger.info("[INFO] ✅ Instalacion completa finalizada.")
    logger.info("[INFO] ================================================\n")


def inject_direct(
    target_dir: Path,
    repo_root: Path,
    sync_codex_skills: bool = False,
    codex_skill_profile: str = "smart",
    codex_home: str | None = None,
    sync_minimax_skills: bool = False,
    sync_superpowers: bool = False,
    sync_brainstorming_planning: bool = False,
    sync_oh_my_claudecode: bool = False,
    deploy_rules_enabled: bool = True,
) -> None:
    """Instalacion local portable sin escribir configuraciones MCP."""
    logger.info("\n[INFO] ================================================")
    logger.info("[INFO] Instalacion local portable del ecosistema Antigravity")
    logger.info(f"[INFO] Proyecto: {target_dir}")
    logger.info("[INFO] ================================================\n")

    project_type = detect_project_type(target_dir)

    install_portable_runtime(
        target_dir,
        repo_root,
        sync_skills=False,
        sync_codex_skills=sync_codex_skills,
        codex_skill_profile=codex_skill_profile,
        codex_home=codex_home,
        sync_minimax_skills=sync_minimax_skills,
        sync_superpowers=sync_superpowers,
        sync_brainstorming_planning=sync_brainstorming_planning,
        sync_oh_my_claudecode=sync_oh_my_claudecode,
    )
    install_antigravity_config(target_dir, repo_root, enable_dev_preset=False)
    install_ai_manifest(
        target_dir,
        DEFAULT_GATEWAY_URL,
        enable_dev_preset=False,
        mcp_enabled=False,
        remote_enabled=False,
    )

    if project_type in ("python", "mixed"):
        install_sdk_python(target_dir, repo_root)
    if project_type in ("js", "mixed"):
        install_sdk_js(target_dir)
    install_example(target_dir, project_type)
    update_claude_md(target_dir, project_type)
    update_agents_md(target_dir)

    if deploy_rules_enabled:
        deploy_rules(str(target_dir))

    if not run_post_injection_smoke(target_dir):
        raise RuntimeError("Smoke post-inyección falló")

    _run_post_inject_hook(target_dir)
    logger.info("[DIRECT] ✅ Runtime local instalado. No se escribieron archivos MCP.")
    logger.info(f"[DIRECT] Usa {target_dir / '.claude' / 'settings.json'} en Claude Code")
    logger.info(f"[DIRECT] Manifest: {target_dir / '.antigravity' / 'ai_manifest.json'}")


def inject_global(
    repo_root: Path,
    enable_dev_preset: bool = True,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    token: str = "",
) -> dict[str, Any]:
    """Inyecta configuracion global en Claude Desktop.

    Returns:
        Dict con success, error (si hubo), y logs.
    """
    logger.info("\n[INFO] ------------------------------------------------")
    logger.info("[INFO] Inyectando Antigravity globalmente")
    logger.info(f"[INFO] Gateway: {gateway_url}")
    logger.info("[INFO] ------------------------------------------------\n")

    result: dict[str, Any] = {"success": True, "errors": []}
    servers = get_mcp_servers(
        repo_root=repo_root,
        target_dir=None,
        enable_dev_preset=enable_dev_preset,
        gateway_url=gateway_url,
        token=token,
    )

    claude_path = get_claude_desktop_config_path()
    if claude_path and claude_path.parent.exists():
        if safe_merge_json(claude_path, servers):
            logger.info(f"✅ [Claude Desktop] Configurado en: {claude_path}")
            logger.info("   -> Reinicia Claude Desktop para aplicar los cambios.")
        else:
            logger.error(f"❌ [Claude Desktop] Fallo la configuracion en {claude_path}.")
            result["success"] = False
            result["errors"].append(f"Fallo configuracion Claude Desktop: {claude_path}")
    else:
        logger.warning("⚠️ [Claude Desktop] No se encontro directorio de configuracion local.")
        result["errors"].append("No se encontro directorio de configuracion local")

    sync_global_claude_assets(repo_root)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Antigravity Smart MCP Injector")
    parser.add_argument(
        "target_dir",
        nargs="?",
        help="Ruta del workspace destino. Si se omite, la inyeccion es global.",
    )
    parser.add_argument(
        "--root",
        help="Ruta root de Antigravity. Por defecto auto-detectada.",
    )
    parser.add_argument(
        "--full",
        action="store_true",
        help="Instalacion completa: runtime local + SDK/config/docs + MCP.",
    )
    dev_group = parser.add_mutually_exclusive_group()
    dev_group.add_argument(
        "--dev-preset",
        action="store_true",
        help="Activa explicitamente MCP de desarrollo.",
    )
    dev_group.add_argument(
        "--no-dev-preset",
        action="store_true",
        help="Desactiva MCP de desarrollo.",
    )
    parser.add_argument(
        "--gateway-url",
        default=DEFAULT_GATEWAY_URL,
        help=f"URL del gateway Antigravity. Por defecto: {DEFAULT_GATEWAY_URL}",
    )
    parser.add_argument(
        "--token",
        default="",
        help="Token de autenticacion para gateway remoto.",
    )
    parser.add_argument(
        "--direct",
        action="store_true",
        help="Instala el runtime local sin escribir configuraciones MCP.",
    )
    parser.add_argument(
        "--update-hooks-only",
        action="store_true",
        help="Actualiza solo .agent/scripts + .claude/hooks/settings y ejecuta smoke.",
    )
    parser.add_argument(
        "--inspect",
        action="store_true",
        help="Inspecciona diferencias/mejoras antes de inyectar y devuelve JSON.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview de reinyeccion: resume que rutas tocaria sin escribir archivos.",
    )
    parser.add_argument(
        "--fail-if-touches",
        action="store_true",
        help="Devuelve exit code 2 si el preview detecta rutas a tocar. Util para CI.",
    )
    parser.add_argument(
        "--apply-improvements",
        action="store_true",
        help="Aplica solo elementos nuevos o mejorados desde Antigravity al destino.",
    )
    parser.add_argument(
        "--import-extras",
        action="store_true",
        help="Importa extras locales del destino de vuelta a Antigravity/Nexus.",
    )
    parser.add_argument(
        "--import-all",
        action="store_true",
        help="Importa extras y conflictos locales del destino hacia Antigravity/Nexus.",
    )
    parser.add_argument(
        "--update-vendored-external-skills",
        action="store_true",
        help="Audita snapshots vendorizados vs upstream, genera diff/reporte y no actualiza nada automáticamente.",
    )
    parser.add_argument(
        "--vendor-package",
        action="append",
        help="Limita la auditoría a un paquete vendorizado específico (repeatable).",
    )
    parser.add_argument(
        "--detect-conflicts",
        action="store_true",
        help="Detecta conflictos reales con smart merge y devuelve JSON (para Tauri).",
    )
    parser.add_argument(
        "--apply-resolutions",
        type=str,
        help="Ruta a archivo JSON con resoluciones de conflictos del usuario.",
    )
    skills_group = parser.add_mutually_exclusive_group()
    skills_group.add_argument(
        "--sync-skills",
        action="store_true",
        help="Legacy: sincroniza skills nativas en .claude/skills.",
    )
    skills_group.add_argument(
        "--no-sync-skills",
        action="store_true",
        help="Omitir sincronizacion de skills en .claude/skills.",
    )
    codex_skills_group = parser.add_mutually_exclusive_group()
    codex_skills_group.add_argument(
        "--sync-codex-skills",
        action="store_true",
        help="Sincroniza skills curadas de openai/skills en $CODEX_HOME/skills.",
    )
    codex_skills_group.add_argument(
        "--no-sync-codex-skills",
        action="store_true",
        help="Omitir sincronizacion de skills de Codex aunque exista ~/.codex.",
    )
    minimax_skills_group = parser.add_mutually_exclusive_group()
    minimax_skills_group.add_argument(
        "--sync-minimax-skills",
        action="store_true",
        help="Integra skills oficiales de MiniMax para Codex y Claude Code.",
    )
    minimax_skills_group.add_argument(
        "--no-sync-minimax-skills",
        action="store_true",
        help="Omitir integracion de MiniMax skills aunque Claude/Codex existan.",
    )
    external_bundle_group = parser.add_mutually_exclusive_group()
    external_bundle_group.add_argument(
        "--sync-external-skills-pack",
        action="store_true",
        help="Instala en bloque superpowers, brainstorming-planning y oh-my-claudecode.",
    )
    external_bundle_group.add_argument(
        "--no-sync-external-skills-pack",
        action="store_true",
        help="Desactiva en bloque el paquete externo; luego puedes reactivar piezas con flags individuales.",
    )
    superpowers_group = parser.add_mutually_exclusive_group()
    superpowers_group.add_argument(
        "--sync-superpowers",
        action="store_true",
        help="Integra obra/superpowers en Codex, Claude, Cursor, OpenCode, Gemini y Copilot si estan disponibles.",
    )
    superpowers_group.add_argument(
        "--no-sync-superpowers",
        action="store_true",
        help="Omitir integración de Superpowers aunque se solicite en presets futuros.",
    )
    brainstorming_group = parser.add_mutually_exclusive_group()
    brainstorming_group.add_argument(
        "--sync-brainstorming-planning",
        action="store_true",
        help="Instala el skill brainstorming-planning como skill local para apps compatibles.",
    )
    brainstorming_group.add_argument(
        "--no-sync-brainstorming-planning",
        action="store_true",
        help="Omitir la instalación del skill brainstorming-planning.",
    )
    omc_group = parser.add_mutually_exclusive_group()
    omc_group.add_argument(
        "--sync-oh-my-claudecode",
        action="store_true",
        help="Integra oh-my-claudecode en Claude, Codex, Cursor y OpenCode si estan disponibles.",
    )
    omc_group.add_argument(
        "--no-sync-oh-my-claudecode",
        action="store_true",
        help="Omitir integración de oh-my-claudecode.",
    )
    parser.add_argument(
        "--codex-skills-profile",
        choices=["smart", "all-curated", "none"],
        default="smart",
        help="Perfil para seleccionar skills de Codex (default: smart).",
    )
    parser.add_argument(
        "--codex-home",
        help="Override de CODEX_HOME para sincronizar skills de Codex.",
    )
    rules_group = parser.add_mutually_exclusive_group()
    rules_group.add_argument(
        "--no-rules",
        action="store_true",
        help="Omitir despliegue de templates de reglas.",
    )
    rules_group.add_argument(
        "--rules-only",
        action="store_true",
        help="Solo desplegar reglas, sin modificar .mcp.json ni runtime.",
    )

    args = parser.parse_args()
    # Handle empty string from nargs="?" — convert to None so argparse normalizes correctly
    if args.target_dir == "":
        args.target_dir = None
    repo_root = (
        Path(args.root).resolve() if args.root else Path(__file__).parent.parent.parent.resolve()
    )

    if args.update_hooks_only and not args.target_dir:
        logger.error("[ERROR] --update-hooks-only requiere una ruta destino.")
        sys.exit(1)

    if args.rules_only and not args.target_dir:
        logger.error("[ERROR] --rules-only requiere una ruta destino.")
        sys.exit(1)

    if args.fail_if_touches and not (args.dry_run or args.inspect):
        logger.error("[ERROR] --fail-if-touches requiere --dry-run o --inspect.")
        sys.exit(1)

    if args.update_hooks_only and (
        args.inspect
        or args.dry_run
        or args.apply_improvements
        or args.import_extras
        or args.import_all
        or args.detect_conflicts
        or args.apply_resolutions
    ):
        logger.error(
            "[ERROR] --update-hooks-only no se puede combinar con modos inspect/import/apply."
        )
        sys.exit(1)

    if args.update_vendored_external_skills:
        try:
            result = audit_vendored_external_skills(
                repo_root,
                package_names=args.vendor_package,
            )
        except Exception as exc:
            logger.error(f"[ERROR] Auditoría de snapshots vendorizados falló: {exc}")
            sys.exit(1)
        emit_json(result)
        return

    if not (repo_root / "mcp-server" / "server.py").exists():
        logger.error(f"[CRITICAL] No se encontro 'mcp-server/server.py' en {repo_root}.")
        logger.error("Este script debe ejecutarse desde el interior del ecosistema Antigravity.")
        sys.exit(1)

    enable_dev_preset = not args.no_dev_preset
    gateway_url = args.gateway_url.rstrip("/")
    token = args.token
    sync_plan = resolve_sync_plan(args)
    do_sync_skills = sync_plan["sync_skills"]
    do_sync_codex_skills = sync_plan["sync_codex_skills"]
    do_sync_minimax_skills = sync_plan["sync_minimax_skills"]
    default_external_pack = sync_plan["default_external_pack"]
    force_external_pack = sync_plan["force_external_pack"]
    do_sync_superpowers = sync_plan["sync_superpowers"]
    do_sync_brainstorming_planning = sync_plan["sync_brainstorming_planning"]
    do_sync_oh_my_claudecode = sync_plan["sync_oh_my_claudecode"]

    if not (
        args.inspect
        or args.dry_run
        or args.apply_improvements
        or args.import_extras
        or args.import_all
        or args.detect_conflicts
        or args.apply_resolutions
    ):
        logger.info(f"[CONFIG] Gateway URL: {gateway_url}")
        logger.info("[CONFIG] Claude-Mem: INCLUIDO")
        logger.info(
            "[CONFIG] Codex Skills: %s",
            "AUTO/SI" if do_sync_codex_skills else "NO",
        )
        logger.info(
            "[CONFIG] MiniMax Skills: %s",
            "AUTO/SI" if do_sync_minimax_skills else "NO",
        )
        logger.info(
            "[CONFIG] External Skills Pack: %s",
            "FORZADO" if force_external_pack else ("SI" if default_external_pack else "NO"),
        )
        logger.info(
            "[CONFIG] Superpowers: %s",
            "SI" if do_sync_superpowers else "NO",
        )
        logger.info(
            "[CONFIG] Brainstorming Planning: %s",
            "SI" if do_sync_brainstorming_planning else "NO",
        )
        logger.info(
            "[CONFIG] oh-my-claudecode: %s",
            "SI" if do_sync_oh_my_claudecode else "NO",
        )

    if args.target_dir:
        target_path = Path(args.target_dir).resolve()
        if not target_path.exists() or not target_path.is_dir():
            logger.error(f"[ERROR] La ruta destino no existe o no es directorio: {target_path}")
            emit_json({"success": False, "error": f"La ruta destino no existe o no es directorio: {target_path}"})
            sys.exit(1)

        if args.update_hooks_only:
            update_hooks_only(
                target_path,
                repo_root,
                gateway_url=gateway_url,
                enable_dev_preset=enable_dev_preset,
                token=token,
            )
        elif args.inspect:
            include_mcp = not args.direct
            result = inspect_installation(
                target_path,
                repo_root,
                enable_dev_preset=enable_dev_preset,
                include_mcp=include_mcp,
            )
            reinjection = summarize_reinjection_targets(result)
            result["dryRun"] = False
            result["reinjection"] = reinjection
            result["humanSummary"] = build_human_dry_run_summary(result, reinjection)
            emit_json(result)
            if args.fail_if_touches and reinjection["touchedCount"] > 0:
                sys.exit(2)
        elif args.dry_run:
            include_mcp = not args.direct
            result = inspect_installation(
                target_path,
                repo_root,
                enable_dev_preset=enable_dev_preset,
                include_mcp=include_mcp,
            )
            reinjection = summarize_reinjection_targets(result)
            result["dryRun"] = True
            result["reinjection"] = reinjection
            result["humanSummary"] = build_human_dry_run_summary(result, reinjection)
            emit_json(result)
            if args.fail_if_touches and reinjection["touchedCount"] > 0:
                sys.exit(2)
        elif args.apply_improvements:
            include_mcp = not args.direct
            result = apply_injection_improvements(
                target_path,
                repo_root,
                enable_dev_preset=enable_dev_preset,
                include_mcp=include_mcp,
                gateway_url=gateway_url,
                token=token,
            )
            emit_json(result)
        elif args.import_extras:
            result = import_target_extras_to_repo(target_path, repo_root)
            emit_json(result)
        elif args.import_all:
            result = import_all_target_changes_to_repo(target_path, repo_root)
            emit_json(result)
        elif args.detect_conflicts:
            analysis = inspect_installation(
                target_path,
                repo_root,
                enable_dev_preset=False,
                include_mcp=False,
            )
            updated_by_category: dict[str, list[str]] = {}
            for cat_key in ("agents", "skills", "skillsCustom"):
                updated_by_category[cat_key] = analysis["categories"][cat_key]["updated"]
            result = detect_real_conflicts(target_path, repo_root, updated_by_category)
            emit_json({"success": True, **result})
        elif args.apply_resolutions:
            resolutions_path = Path(args.apply_resolutions)
            if not resolutions_path.exists():
                logger.error(f"[ERROR] Archivo de resoluciones no encontrado: {resolutions_path}")
                sys.exit(1)
            try:
                with open(resolutions_path, encoding="utf-8") as f:
                    resolutions_data = json.load(f)
            except (json.JSONDecodeError, OSError) as exc:
                logger.error(f"[ERROR] Error al leer archivo de resoluciones: {exc}")
                sys.exit(1)
            if not isinstance(resolutions_data, list):
                resolutions_data = resolutions_data.get("resolutions", [])
            result = apply_conflict_resolution(resolutions_data, target_path, repo_root)
            emit_json(result)
        elif args.rules_only:
            rules_result = deploy_rules(str(target_path))
            emit_json({"success": True, "rules": rules_result})
        elif args.direct:
            inject_direct(
                target_path,
                repo_root,
                sync_codex_skills=do_sync_codex_skills,
                codex_skill_profile=args.codex_skills_profile,
                codex_home=args.codex_home,
                sync_minimax_skills=do_sync_minimax_skills,
                sync_superpowers=do_sync_superpowers,
                sync_brainstorming_planning=do_sync_brainstorming_planning,
                sync_oh_my_claudecode=do_sync_oh_my_claudecode,
                deploy_rules_enabled=not args.no_rules,
            )
        elif args.full:
            install_full(
                target_path,
                repo_root,
                enable_dev_preset=enable_dev_preset,
                gateway_url=gateway_url,
                token=token,
                sync_skills=do_sync_skills,
                sync_codex_skills=do_sync_codex_skills,
                codex_skill_profile=args.codex_skills_profile,
                codex_home=args.codex_home,
                sync_minimax_skills=do_sync_minimax_skills,
                deploy_rules_enabled=not args.no_rules,
                sync_superpowers=do_sync_superpowers,
                sync_brainstorming_planning=do_sync_brainstorming_planning,
                sync_oh_my_claudecode=do_sync_oh_my_claudecode,
            )
        else:
            install_portable_runtime(
                target_path,
                repo_root,
                sync_skills=do_sync_skills,
                sync_codex_skills=do_sync_codex_skills,
                codex_skill_profile=args.codex_skills_profile,
                codex_home=args.codex_home,
                sync_minimax_skills=do_sync_minimax_skills,
                sync_superpowers=do_sync_superpowers,
                sync_brainstorming_planning=do_sync_brainstorming_planning,
                sync_oh_my_claudecode=do_sync_oh_my_claudecode,
            )
            install_ai_manifest(
                target_path,
                gateway_url=gateway_url,
                enable_dev_preset=enable_dev_preset,
                mcp_enabled=True,
                remote_enabled=bool(token) or is_remote_gateway_url(gateway_url),
            )
            inject_workspace(
                target_path,
                repo_root,
                enable_dev_preset=enable_dev_preset,
                gateway_url=gateway_url,
                token=token,
            )
            if not args.no_rules:
                deploy_rules(str(target_path))
            if not run_post_injection_smoke(target_path):
                raise RuntimeError("Smoke post-inyección falló")
            _run_post_inject_hook(target_path)
    else:
        result = inject_global(
            repo_root=repo_root,
            enable_dev_preset=enable_dev_preset,
            gateway_url=gateway_url,
            token=token,
        )
        emit_json(result)


if __name__ == "__main__":
    main()
