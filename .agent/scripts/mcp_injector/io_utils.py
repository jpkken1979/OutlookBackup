"""I/O utilities extracted from mcp_injector.py.

Provides JSON handling, file system operations, hashing, and comparison
functions shared across the MCP injector subsystem.

All shared constants are imported from the `constants` module; path helpers
are imported from the `path_utils` module to avoid duplication.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .constants import LEGACY_CLAUDE_DIRS, SKIP_TREE_NAMES, SKIP_TREE_PREFIXES
from .path_utils import ensure_dir, normalize_path

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# JSON
# ---------------------------------------------------------------------------


def emit_json(payload: dict[str, Any]) -> None:
    """Emite JSON seguro para stdout en Windows sin depender del codepage activo."""
    print(json.dumps(payload, ensure_ascii=True))


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


def write_json_file(
    path: Path,
    payload: dict[str, Any],
    *,
    templatize_repo_root: bool = True,
) -> bool:
    """Escribe un JSON con indentacion estable y paths portabilizados.

    Antes de serializar reescribe cualquier ruta absoluta del sistema que
    referencia HOME/USERNAME en su forma portable ``${USERPROFILE}``. Esto
    permite que las configs generadas pasen el check
    ``_contains_hardcoded_user_path()`` y se porten entre maquinas.

    Args:
        path: Destino del JSON.
        payload: Contenido a serializar.
        templatize_repo_root: Si reemplazar la ruta del repo por
            ``${ANTIGRAVITY_ROOT}``. Debe ser ``False`` al escribir la config de
            un proyecto TARGET: ahi ``ANTIGRAVITY_ROOT`` vale ``.`` (el target),
            asi que templatizar la ruta del repo FUENTE la hace apuntar al lugar
            equivocado. Rompio el `.mcp.json` de Kintai el 2026-07-27: el
            interprete quedaba como ``${ANTIGRAVITY_ROOT}/.venv/Scripts/python.exe``
            y el target no tiene ``.venv``.

    Returns:
        True si se escribio correctamente.
    """
    portable = _make_portable_paths(payload, templatize_repo_root=templatize_repo_root)
    try:
        ensure_dir(path.parent)
        path.write_text(json.dumps(portable, indent=2, ensure_ascii=False), encoding="utf-8")
        return True
    except Exception as exc:
        logger.error(f"❌ [JSON] No se pudo escribir {path}: {exc}")
        return False


def _make_portable_paths(
    obj: dict[str, Any],
    *,
    templatize_repo_root: bool = True,
) -> dict[str, Any]:
    """Reemplaza ``C:\\Users\\<user>`` con ``${USERPROFILE}`` y la ruta del repo
    con ``${ANTIGRAVITY_ROOT}`` en strings recursivamente (dict/list/str).

    Normaliza el resultado a forward-slash para que ``${USERPROFILE}/.local/bin``
    sea substring de ``${USERPROFILE}/.local/bin`` (evita el mismatch entre
    ``C:/Users/kenji`` y ``C:\\Users\\kenji\\.local\\bin`` en el check
    ``_contains_hardcoded_user_path()`` de los tests de portabilidad.

    Deja ``C:\\Windows\\System32``, ``C:\\Program Files\\nodejs`` y
    ``C:\\Program Files\\Git\\cmd`` porque son paths de sistema universales
    en Windows (no dependen del usuario).
    """
    import os
    import platform

    USER_VAR = "${USERPROFILE}"

    home_str = ""
    if platform.system() == "Windows":
        try:
            raw_home = str(Path(os.environ.get("USERPROFILE", "")).resolve())
            if raw_home.startswith("\\\\?\\"):
                raw_home = raw_home[4:]
            home_str = raw_home
        except Exception:
            pass

    def _replace(s: str) -> str:
        result = s
        # 1. Repo root PRIMERO (es mas especifico/largo que home, que suele ser
        #    su prefijo: el repo vive bajo C:\\Users\\<user>\\Github\\...). Se
        #    reemplazan ambas formas (backslash nativo y forward-slash de
        #    normalize_path) preservando el separator del resto del string.
        repo_root = os.environ.get("ANTIGRAVITY_ROOT", "")
        if not repo_root:
            try:
                repo_root = str(Path(__file__).resolve().parents[2])
            except Exception:
                repo_root = ""
        if repo_root.startswith("\\\\?\\"):
            repo_root = repo_root[4:]
        if not templatize_repo_root:
            repo_root = ""
        if repo_root and "${ANTIGRAVITY_ROOT}" not in result:
            result = result.replace(repo_root, "${ANTIGRAVITY_ROOT}")
            result = result.replace(repo_root.replace("\\", "/"), "${ANTIGRAVITY_ROOT}")
            if len(repo_root) > 1 and repo_root[1:2] == ":":
                rr_alt = repo_root[0].swapcase() + repo_root[1:]
                result = result.replace(rr_alt, "${ANTIGRAVITY_ROOT}")
                result = result.replace(rr_alt.replace("\\", "/"), "${ANTIGRAVITY_ROOT}")
        # 2. Home del usuario (para paths fuera del repo, ej. ~\.local\bin en PATH).
        if home_str:
            h = home_str
            result = result.replace(h, USER_VAR)
            result = result.replace(h.replace("\\", "/"), USER_VAR)
            if len(h) > 1 and h[1:2] == ":":
                h_alt = h[0].swapcase() + h[1:]
                result = result.replace(h_alt, USER_VAR)
                result = result.replace(h_alt.replace("\\", "/"), USER_VAR)
        return result

    def _walk(o: Any) -> Any:
        if isinstance(o, str):
            return _replace(o)
        if isinstance(o, dict):
            return {k: _walk(v) for k, v in o.items()}
        if isinstance(o, list):
            return [_walk(v) for v in o]
        return o

    return _walk(obj)


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


# ---------------------------------------------------------------------------
# Backup helpers
# ---------------------------------------------------------------------------


def _backup_conflicting_path(path: Path) -> Path:
    """Respalda archivos/directorios que bloquean la creacion de una ruta requerida."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.with_name(f"{path.name}.legacy.{timestamp}")
    counter = 1
    while backup_path.exists():
        backup_path = path.with_name(f"{path.name}.legacy.{timestamp}_{counter}")
        counter += 1
    shutil.move(str(path), str(backup_path))
    logger.info(f"  [legacy-conflict] {path} -> {backup_path}")
    return backup_path


# ---------------------------------------------------------------------------
# Copy helpers
# ---------------------------------------------------------------------------


def copy_file(src: Path, dst: Path) -> bool:
    """Copia un archivo si existe."""
    if not src.exists():
        return False
    if src.resolve() == dst.resolve():
        return False
    ensure_dir(dst.parent)
    shutil.copy2(src, dst)
    return True


def merge_tree(
    src: Path,
    dst: Path,
    exclude: frozenset[str] | None = None,
) -> int:
    """Copia/actualiza un arbol sin borrar extras del destino.

    Args:
        src: Directorio o archivo fuente.
        dst: Destino donde copiar.
        exclude: Nombres de archivo a omitir en el nivel raiz de src.
    """
    if not src.exists():
        return 0
    if src.is_file():
        if _same_file_metadata(src, dst):
            return 0
        ensure_dir(dst.parent)
        shutil.copy2(src, dst)
        return 1

    copied = 0
    ensure_dir(dst)
    for item in src.iterdir():
        if item.name in SKIP_TREE_NAMES or item.name.startswith(SKIP_TREE_PREFIXES):
            continue
        if exclude and item.name in exclude:
            continue
        target = dst / item.name
        if item.is_dir():
            copied += merge_tree(item, target)
        else:
            if item.resolve() == target.resolve():
                continue
            if _same_file_metadata(item, target):
                continue
            ensure_dir(target.parent)
            shutil.copy2(item, target)
            copied += 1
    return copied


def _same_file_metadata(source: Path, target: Path) -> bool:
    """Fast no-op check for files previously copied with ``copy2``.

    ``copy2`` preserves size and nanosecond mtime. A normal user edit changes
    at least one of them, while a reinjection of an unchanged bundle can skip
    thousands of redundant writes and the associated antivirus scans.
    """

    if not target.is_file():
        return False
    try:
        source_stat = source.stat()
        target_stat = target.stat()
    except OSError:
        return False
    return (
        source_stat.st_size == target_stat.st_size
        and source_stat.st_mtime_ns == target_stat.st_mtime_ns
    )


def copy_path_if_needed(source: Path, target: Path) -> bool:
    """Copia un archivo o directorio solo si falta o cambio."""
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


# ---------------------------------------------------------------------------
# Legacy cleanup
# ---------------------------------------------------------------------------


def safe_remove_legacy(path: Path) -> None:
    """En lugar de borrar, hace backup rotativo y crea symlink al nuevo destino en .agent/."""
    if not path.exists():
        return

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = path.parent / f"{path.name}.bak.{timestamp}"
    shutil.move(str(path), str(backup_path))
    logger.info(f"  [backup] {path.name} -> {backup_path.name}")

    pattern = f"{path.name}.bak.*"
    backups = sorted(path.parent.glob(pattern), key=lambda x: x.stat().st_mtime, reverse=True)
    for old_backup in backups[3:]:
        shutil.rmtree(str(old_backup), ignore_errors=True)
        logger.info(f"  [backup-cleanup] Backup antiguo eliminado: {old_backup.name}")

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


# ---------------------------------------------------------------------------
# Backup
# ---------------------------------------------------------------------------


def backup_path(source: Path, backup_root: Path, relative_name: str) -> str | None:
    """Guarda una copia previa antes de sobrescribir un elemento del repo."""
    # Depends on: mcp_injector.classify_entry_change (patched by parent module)
    if not source.exists():
        return None

    destination = backup_root / relative_name
    if source.is_dir():
        merge_tree(source, destination)
    else:
        copy_file(source, destination)
    return normalize_path(destination)


# ---------------------------------------------------------------------------
# Claude config paths
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Hashing
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Comparison helpers (implemented in injection.py; re-exported here for
# backwards compatibility with code that imports from io_utils)
# ---------------------------------------------------------------------------
# Real implementations live in injection.py to avoid circular deps.
# Imported at the bottom of this module after compare_* are defined.


# ---------------------------------------------------------------------------
# Comparison
# ---------------------------------------------------------------------------


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
            if (item.is_dir() or item.is_file())
            and item.name not in SKIP_TREE_NAMES
            and not item.name.startswith(skip_prefixes)
        }
        if source_root.exists()
        else {}
    )
    target_names = (
        {
            item.name: item
            for item in target_root.iterdir()
            if (item.is_dir() or item.is_file())
            and item.name not in SKIP_TREE_NAMES
            and not item.name.startswith(skip_prefixes)
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
# Comparison stubs — replaced by real implementations from injection.py
# when mcp_injector.py patches these after import.
# Kept here so standalone use of io_utils (without the full package) still works.
# ---------------------------------------------------------------------------

try:
    from .injection import build_change_detail as _inj_bcd, classify_entry_change as _inj_cec

    build_change_detail = _inj_bcd
    classify_entry_change = _inj_cec
except ImportError:
    # Standalone / fallback: stubs so compare_* functions still type-check
    def build_change_detail(
        name: str,
        source: Path | None,
        target: Path | None,
        *,
        status: str,
    ) -> dict[str, str]:
        return {"name": name, "classification": "unknown", "reason": "stub"}

    def classify_entry_change(
        source: Path | None,
        target: Path | None,
        *,
        status: str,
    ) -> dict[str, str]:
        return {"classification": "unknown", "reason": "stub"}


# ---------------------------------------------------------------------------
# Runtime path pairs
# ---------------------------------------------------------------------------


def get_runtime_path_pairs(repo_root: Path, target_dir: Path) -> dict[str, tuple[Path, Path]]:
    """Devuelve el mapa de componentes runtime comparables/copiables."""
    return {
        "agentRuntime": (
            repo_root / ".agent" / "mcp",
            target_dir / ".agent" / "mcp",
        ),
        "mcpServer": (
            repo_root / "mcp-server",
            target_dir / "mcp-server",
        ),
        "claudeSettings": (
            repo_root / ".claude" / "settings.json",
            target_dir / ".claude" / "settings.json",
        ),
        "rules": (
            repo_root / ".antigravity" / "rules.md",
            target_dir / ".antigravity" / "rules.md",
        ),
    }
