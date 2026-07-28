"""Guard idempotente para .gitignore: garantiza que paths criticos del
ecosistema Antigravity no queden bloqueados silenciosamente por gitignore
patterns en proyectos target.

Inserta o actualiza un bloque marcado con:

    # === ANTIGRAVITY GUARD START ===
    !.mcp.json
    !.agent/brain/**
    ...
    # === ANTIGRAVITY GUARD END ===

Lo que protege (re-incluye con `!` prefix) por default:
- `.mcp.json` y `.mcp.local.json` (config MCP)
- `.agent/brain/**` (Brain Network, capa 2 de memoria, fuente de verdad)
- `.agent/VERSION` (semver del runtime)
- `.agent/scripts/**/*.py` (scripts del runtime)
- `.claude/memory/**` (capa 1 de memoria, MEMORY.md + entradas)
- `.claude/rules/**` (reglas auto-inyectadas)
- `.claude/commands/**` (slash commands)
- `.claude/settings.json` y `.claude/settings.local.json`
- `.antigravity/ai_manifest.json`, `.antigravity/rules.md`

El bloque es idempotente: si ya existe, se reemplaza in-place. Si no existe,
se appende al final del .gitignore. Si no hay .gitignore, se crea.

Diseñado para ser invocado desde:
- `mcp_injector.py` tras instalar el ecosistema en un target.
- `validate_gitignore.py` standalone para auditar repos existentes.
- Tests unitarios.
"""

from __future__ import annotations

import logging
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)

GUARD_START = "# === ANTIGRAVITY GUARD START === (auto-managed, no editar manual)"
GUARD_END = "# === ANTIGRAVITY GUARD END ==="

# Paths que el ecosistema requiere sincronizar via git para funcionar.
# Cada entry va prefijado con `!` en el .gitignore para re-incluir.
#
# Reglas de granularidad:
#   - Re-incluir el directorio padre (`.claude/`) es necesario para que
#     git atraviese y los `!subpath/**` funcionen.
#   - Re-incluir patrones especificos (`**/*.md`) en vez de `**` evita
#     exponer logs, cache, json de runtime que SI deben ignorarse.
DEFAULT_PROTECTED_PATHS: tuple[str, ...] = (
    # ── MCP config ──
    ".mcp.json",
    ".mcp.local.json",
    # ── Claude Code (.claude/) ──
    ".claude/",
    ".claude/settings.json",
    ".claude/settings.local.json",
    # Memoria capa 1: solo markdown (excluye .log, cache de runtime)
    ".claude/memory/",
    ".claude/memory/**/*.md",
    # Reglas y comandos: solo markdown
    ".claude/rules/",
    ".claude/rules/**/*.md",
    ".claude/commands/",
    ".claude/commands/**/*.md",
    # ── Runtime Antigravity (.agent/) ──
    ".agent/",
    ".agent/VERSION",
    # Brain: markdown + db de indices (excluye state/cache)
    ".agent/brain/",
    ".agent/brain/**/*.md",
    ".agent/brain/**/*.db",
    # Scripts/core/mcp: solo python (excluye cache, logs)
    ".agent/scripts/",
    ".agent/scripts/**/*.py",
    ".agent/mcp/",
    ".agent/mcp/**/*.py",
    ".agent/core/",
    ".agent/core/**/*.py",
    # ── Manifest del ecosistema (.antigravity/) ──
    # NOTA: NO re-incluir .antigravity/ entero porque tiene data dinamica
    # (intelligence/, observations/, memory/, vendor-audits/). Solo los
    # archivos canonicos del manifest publico.
    ".antigravity/ai_manifest.json",
    ".antigravity/rules.md",
)

# Paths que se chequean con `git check-ignore` para detectar drift.
HEALTH_CHECK_PATHS: tuple[str, ...] = (
    ".mcp.json",
    ".agent/brain/index.md",
    ".agent/brain/log.md",
    ".claude/memory/MEMORY.md",
    ".claude/settings.json",
    ".antigravity/ai_manifest.json",
)


@dataclass(frozen=True)
class PatchResult:
    """Resultado de un patch sobre .gitignore."""

    action: str  # "created" | "patched" | "appended" | "unchanged" | "skipped"
    path: Path
    paths_protected: int
    reason: str = ""


@dataclass
class HealthReport:
    """Reporte de health check sobre paths bloqueados."""

    git_available: bool
    blocked_paths: list[str] = field(default_factory=list)
    checked_paths: list[str] = field(default_factory=list)
    target: Path | None = None

    @property
    def healthy(self) -> bool:
        return self.git_available and not self.blocked_paths


def build_guard_block(paths: tuple[str, ...] = DEFAULT_PROTECTED_PATHS) -> str:
    """Construye el bloque guard como string listo para insertar.

    Args:
        paths: Lista de paths a re-incluir. Por defecto, ``DEFAULT_PROTECTED_PATHS``.

    Returns:
        Texto multilinea con el bloque entre los marcadores START/END.
    """
    lines = [
        GUARD_START,
        "# Excepciones del ecosistema Antigravity para que git versione los",
        "# archivos criticos (memoria, brain, MCP config, runtime).",
        "# Ver docs/rules-reference/memory-engine.md y .claude/rules/security.md",
    ]
    for path in paths:
        lines.append(f"!{path}")
    lines.append(GUARD_END)
    return "\n".join(lines)


def _replace_or_append(content: str, block: str) -> tuple[str, str]:
    """Reemplaza el bloque guard existente o lo appende.

    Returns:
        Tupla ``(nuevo_contenido, accion)`` donde accion es
        ``"patched"``, ``"appended"`` o ``"unchanged"``.
    """
    if GUARD_START in content and GUARD_END in content:
        pattern = re.compile(
            re.escape(GUARD_START) + r".*?" + re.escape(GUARD_END),
            re.DOTALL,
        )
        new_content = pattern.sub(block, content, count=1)
        action = "unchanged" if new_content == content else "patched"
        return new_content, action

    if not content.endswith("\n"):
        content += "\n"
    return content + "\n" + block + "\n", "appended"


def patch_gitignore(
    target: Path,
    *,
    dry_run: bool = False,
    paths: tuple[str, ...] = DEFAULT_PROTECTED_PATHS,
) -> PatchResult:
    """Patcha el .gitignore del target para proteger paths del ecosistema.

    Idempotente: corre N veces y produce el mismo resultado.

    Args:
        target: Directorio raiz del proyecto target (donde vive .gitignore).
        dry_run: Si True, no escribe nada. Solo devuelve la accion que tomaria.
        paths: Override del set de paths a proteger.

    Returns:
        :class:`PatchResult` con ``action``, ``path`` del .gitignore y conteo
        de paths protegidos.
    """
    if not target.is_dir():
        return PatchResult(
            action="skipped",
            path=target / ".gitignore",
            paths_protected=0,
            reason=f"target no es directorio: {target}",
        )

    gitignore = target / ".gitignore"
    block = build_guard_block(paths)

    if not gitignore.exists():
        if not dry_run:
            gitignore.write_text(
                f"# .gitignore generado por Antigravity ecosystem\n\n{block}\n",
                encoding="utf-8",
            )
        logger.info("[gitignore_guard] creado: %s", gitignore)
        return PatchResult(
            action="created",
            path=gitignore,
            paths_protected=len(paths),
        )

    content = gitignore.read_text(encoding="utf-8")
    new_content, action = _replace_or_append(content, block)

    if action == "unchanged":
        return PatchResult(
            action="unchanged",
            path=gitignore,
            paths_protected=len(paths),
        )

    if not dry_run:
        gitignore.write_text(new_content, encoding="utf-8")
    logger.info("[gitignore_guard] %s: %s", action, gitignore)
    return PatchResult(
        action=action,
        path=gitignore,
        paths_protected=len(paths),
    )


def check_gitignore_health(
    target: Path,
    *,
    paths: tuple[str, ...] = HEALTH_CHECK_PATHS,
) -> HealthReport:
    """Detecta paths protegidos que estan bloqueados por gitignore patterns.

    Usa ``git check-ignore -q <path>`` (exit 0 = ignored). Si ``git`` no esta
    accesible, devuelve un reporte con ``git_available=False`` y skip.

    Args:
        target: Directorio raiz del repo.
        paths: Override del set de paths a chequear.

    Returns:
        :class:`HealthReport` con la lista de paths bloqueados.
    """
    report = HealthReport(git_available=False, target=target)
    if not shutil.which("git"):
        return report
    if not (target / ".git").exists():
        return HealthReport(
            git_available=True,
            target=target,
            checked_paths=[],
        )

    report.git_available = True
    for rel_path in paths:
        report.checked_paths.append(rel_path)
        result = subprocess.run(
            ["git", "check-ignore", "-q", rel_path],
            cwd=str(target),
            capture_output=True,
            shell=False,
        )
        if result.returncode == 0:
            report.blocked_paths.append(rel_path)
    return report
