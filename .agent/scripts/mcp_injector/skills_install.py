"""Antigravity Smart Injector — Skills Installation Module.

Funciones de instalacion de skills extraidas de mcp_injector.py.
Cada funcion es lazy-loaded via importlib.util para evitar dependencias
directas entre modulos.

Las variables `_sync_*_module` son placeholder — se inicializan en el
modulo padre (mcp_injector.py) cuando se importa este modulo.
"""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Placeholder para los modulos lazy-loaded (se inicializan en el modulo padre)
_sync_skills_module: Any = None
_sync_codex_skills_module: Any = None
_sync_minimax_skills_module: Any = None
_sync_antigravity_codex_assets_module: Any = None
_sync_superpowers_module: Any = None
_sync_brainstorming_planning_module: Any = None
_sync_oh_my_claudecode_module: Any = None
_update_vendored_external_skills_module: Any = None

REPO_ROOT: Path = Path(__file__).resolve().parent.parent.parent
REPO_ROOT_POSIX: str = str(REPO_ROOT).replace("\\", "/")

logger: logging.Logger = logging.getLogger(__name__)


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
