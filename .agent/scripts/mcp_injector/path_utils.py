"""Path and directory utilities extracted from mcp_injector.py."""

from __future__ import annotations

import logging
import re
from pathlib import Path

from .constants import (
    CODE_EXTENSIONS,
    CONFIG_EXTENSIONS,
    DOC_EXTENSIONS,
    LEGACY_CLAUDE_DIRS,
    SKIP_TREE_NAMES,
)

logger = logging.getLogger(__name__)


def _strip_windows_extended_path_prefix(value: str) -> str:
    """Quita prefijos Win32 que Python CLI y Copilot no aceptan como argumento."""
    if value.startswith("\\\\?\\UNC\\"):
        return "\\\\" + value[8:]
    if value.startswith("\\\\?\\"):
        return value[4:]
    return value


def normalize_path(path: Path) -> str:
    """Normaliza rutas para JSON sin persistir prefijos Win32 extended-length."""
    return _strip_windows_extended_path_prefix(str(path.resolve())).replace("\\", "/")


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
                f"[SECURITY] Nombre de directorio invalido (caracteres de control): {part}"
            )
            raise ValueError(f"Invalid directory name: {part}")

    if path.exists() and not path.is_dir():
        # Lazy import to avoid circular dependency (io_utils imports from path_utils)
        from .io_utils import _backup_conflicting_path

        _backup_conflicting_path(path)
    path.mkdir(parents=True, exist_ok=True)


def iter_content_files(path: Path) -> list[Path]:
    """Lista archivos relevantes de un path para inspeccion heuristica."""
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
    profile: dict[str, bool] = {
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


def _is_absolute_local_path(value: str) -> bool:
    """Detecta rutas absolutas locales Windows/POSIX."""
    if not value:
        return False
    return bool(re.match(r"^[a-zA-Z]:[\\/]", value)) or value.startswith(("/", "\\\\"))


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


def find_legacy_claude_entries(target_dir: Path) -> list[str]:
    """Devuelve rutas legacy activas dentro de `.claude/`."""
    leftovers: list[str] = []
    for dirname in LEGACY_CLAUDE_DIRS:
        candidate = target_dir / ".claude" / dirname
        if candidate.exists():
            leftovers.append(f".claude/{dirname}")
    return leftovers
