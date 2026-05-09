"""Constantes y variables de nivel de modulo para mcp_injector.

Extraidas de mcp_injector.py para permitir migracion gradual y reducir
el tamano del modulo principal. Todas las constantes aqui definidas son
re-exportadas por mcp_injector.py via `from .constants import *`.
"""

from __future__ import annotations

import logging
from pathlib import Path

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("mcp_injector")


# ---------------------------------------------------------------------------
# Variables de modulo caching lazy-loaded en mcp_injector.py
# ---------------------------------------------------------------------------
_sync_skills_module = None
_sync_codex_skills_module = None
_sync_minimax_skills_module = None
_sync_antigravity_codex_assets_module = None
_sync_superpowers_module = None
_sync_brainstorming_planning_module = None
_sync_oh_my_claudecode_module = None
_update_vendored_external_skills_module = None


# ---------------------------------------------------------------------------
# Rutas canonicas del repositorio
# ---------------------------------------------------------------------------
REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent
REPO_ROOT_POSIX: str = str(REPO_ROOT).replace("\\", "/")


# ---------------------------------------------------------------------------
# Helper de inicializacion
# ---------------------------------------------------------------------------
def _read_ecosystem_version() -> str:
    """Lee la version desde .agent/VERSION (relativo al script)."""
    version_file = Path(__file__).resolve().parent.parent / "VERSION"
    try:
        return version_file.read_text(encoding="utf-8").strip()
    except OSError:
        return "5.0.0"


# ---------------------------------------------------------------------------
# Configuracion del ecosistema
# ---------------------------------------------------------------------------
ECOSYSTEM_VERSION: str = _read_ecosystem_version()
DEFAULT_GATEWAY_URL: str = "http://localhost:4747"
DEFAULT_MEMORY_BACKEND: str = "mem0"
DEFAULT_REGISTRY_MODE: str = "remote-cache"
DEFAULT_REGISTRY_CACHE_TTL_SECONDS: int = 900
DEFAULT_ORCHESTRATOR_MODE: str = "agent-teams-lite"


# ---------------------------------------------------------------------------
# Extensiones de archivo
# ---------------------------------------------------------------------------
CODE_EXTENSIONS: set[str] = {
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
CONFIG_EXTENSIONS: set[str] = {".json", ".yaml", ".yml", ".toml", ".ini", ".conf"}
DOC_EXTENSIONS: set[str] = {".md", ".txt", ".doc", ".docx", ".pdf"}


# ---------------------------------------------------------------------------
# Arboles y archivos a omitir
# ---------------------------------------------------------------------------
SKIP_TREE_NAMES: set[str] = {
    ".git",
    "__pycache__",
    ".pytest_cache",
    "node_modules",
    "dist",
    "build",
}
ROOT_RULE_FILES: list[str] = [
    "RULES.md",
    "WORKFLOW_RULES.md",
]


# ---------------------------------------------------------------------------
# Estructura de directorios portable
# ---------------------------------------------------------------------------
PORTABLE_AGENT_DIRS: list[str] = [
    "agents",
    "skills",
    "skills-custom",
    "workflows",
    "scripts",
    "core",
    "mcp",
    "templates",
]
CLAUDE_DIRS: list[str] = ["hooks", "rules", "commands"]


# ---------------------------------------------------------------------------
# Reglas especificas de OpenAntigravity (NO inyectar en proyectos externos)
# ---------------------------------------------------------------------------
# Archivos de .claude/rules/ que NO deben inyectarse en proyectos externos:
# son especificos de OpenAntigravity (estado del ecosistema, arquitectura interna).
# La identidad del usuario viaja via user-identity.md en las templates.
RULES_EXCLUDE: frozenset[str] = frozenset({"AI_MEMORY.md"})
ANTIGRAVITY_FILES: list[str] = ["rules.md", "AI_MEMORY_README.md"]
LEGACY_CLAUDE_DIRS: list[str] = ["agents", "skills", "memory-engine"]


# ---------------------------------------------------------------------------
# Placeholders para credenciales remotas
# ---------------------------------------------------------------------------
REMOTE_GATEWAY_PLACEHOLDER: str = "__REMOTE_GATEWAY_URL__"
REMOTE_TOKEN_PLACEHOLDER: str = "__REMOTE_API_TOKEN__"


# ---------------------------------------------------------------------------
# Hooks de runtime
# ---------------------------------------------------------------------------
HOOK_RUNTIME_FILES: list[str] = [
    ".agent/scripts/hook_runner.py",
    ".agent/scripts/session_hook.py",
    ".agent/scripts/git_sync_hook.py",
]


# ---------------------------------------------------------------------------
# Marcadores que identifican paths absolutos de este repo (no portables)
# ---------------------------------------------------------------------------
NON_PORTABLE_CLAUDE_MARKERS: tuple[str, ...] = tuple(
    marker
    for marker in {
        "C--Users-Kenji-Documents-GitHub-OpenAntigravity",
        "D--Git-OpenAntigravity",
        REPO_ROOT_POSIX,
        REPO_ROOT_POSIX.replace("/", "--"),
    }
    if marker
)
