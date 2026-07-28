"""Funciones de inyeccion y workflow extraidas de mcp_injector.py.

Este modulo contiene la logica de injection de workspace, workflow de actualizacion
incremental, deteccion de conflictos y resolution de merge para archivos markdown.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from .constants import (
    CLAUDE_DIRS,
    DEFAULT_GATEWAY_URL,
    ECOSYSTEM_VERSION,
    LEGACY_CLAUDE_DIRS,
    NON_PORTABLE_CLAUDE_MARKERS,
)
from .io_utils import (
    backup_path,
    compare_named_directories,
    compare_paths,
    copy_file,
    copy_named_entries,
    get_runtime_path_pairs,
    merge_tree,
    read_json_file,
)
from .mcp_config import (
    LEGACY_MANAGED_MCP_SERVER_NAMES,
    get_mcp_servers,
    install_ai_manifest,
    install_antigravity_config,
    install_claude_settings,
    safe_merge_continue_json,
    safe_merge_codex_toml,
    safe_merge_json,
    safe_merge_vscode_mcp,
    safe_merge_zed_settings,
)
from .path_utils import build_path_profile, find_legacy_claude_entries

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Clasificacion de cambios
# ---------------------------------------------------------------------------


def classify_entry_change(
    source: Path | None,
    target: Path | None,
    *,
    status: str,
) -> dict[str, str]:
    """Clasifica heuristicamente un cambio de contenido."""
    profile = build_path_profile(source or target or Path("."))

    if status == "updated" and (profile["has_code"] or profile["has_behavior_docs"]):
        return {
            "classification": "possibleConflict",
            "reason": "Cambio en logica, instrucciones o comportamiento; revisar antes de sobrescribir.",
        }
    if profile["has_code"] or profile["has_behavior_docs"]:
        return {
            "classification": "functional",
            "reason": "Afecta codigo, instrucciones ejecutables o comportamiento del agente/skill.",
        }
    if profile["has_docs"] and not profile["has_config"]:
        return {
            "classification": "documentation",
            "reason": "Cambio centrado en documentacion o contenido descriptivo.",
        }
    return {
        "classification": "minor",
        "reason": "Cambio menor o de configuracion sin senal fuerte de cambio funcional.",
    }


def build_change_detail(
    name: str,
    source: Path | None,
    target: Path | None,
    *,
    status: str,
) -> dict[str, str]:
    """Construye detalle enriquecido para una diferencia analizada."""
    classification = classify_entry_change(source, target, status=status)
    return {
        "name": name,
        "classification": classification["classification"],
        "reason": classification["reason"],
    }


def _collect_out_of_scope_items(target_dir: Path) -> dict[str, list[str]]:
    """Detecta skills/agentes en rutas no canonicas para reportarlas en analisis."""
    out_of_scope: dict[str, list[str]] = {
        "agents": [],
        "skills": [],
    }

    candidates = [
        (target_dir / ".claude" / "agents", "agents"),
        (target_dir / ".claude" / "skills", "skills"),
        (target_dir / "agents", "agents"),
        (target_dir / "skills", "skills"),
        (target_dir / "skills-custom", "skills"),
    ]

    for path, category in candidates:
        if not path.exists():
            continue
        if path.is_file():
            out_of_scope[category].append(str(path.relative_to(target_dir)))
            continue

        for item in sorted(path.iterdir()):
            if item.name.startswith(".") or item.name.startswith("_"):
                continue
            out_of_scope[category].append(str(item.relative_to(target_dir)))

    # Evitar duplicados preservando orden
    for key, values in out_of_scope.items():
        seen: set[str] = set()
        unique_values: list[str] = []
        for value in values:
            if value in seen:
                continue
            seen.add(value)
            unique_values.append(value)
        out_of_scope[key] = unique_values

    return out_of_scope


# ---------------------------------------------------------------------------
# Importacion con backup
# ---------------------------------------------------------------------------


def import_named_entries_with_backup(
    source_root: Path,
    target_root: Path,
    names: list[str],
    *,
    backup_root: Path | None = None,
    backup_prefix: str = "",
) -> tuple[list[str], list[str]]:
    """Importa entradas nominales a Nexus, respaldando las existentes si es necesario."""
    imported: list[str] = []
    backups: list[str] = []

    for name in sorted(set(names)):
        source = source_root / name
        target = target_root / name
        if backup_root is not None and target.exists():
            backup_name = f"{backup_prefix}/{name}" if backup_prefix else name
            backup_location = backup_path(target, backup_root, backup_name)
            if backup_location is not None:
                backups.append(backup_location)

        if copy_path_if_needed(source, target):
            imported.append(name)

    return imported, backups


# ---------------------------------------------------------------------------
# Inspeccion pre-inyeccion
# ---------------------------------------------------------------------------


def inspect_installation(
    target_dir: Path,
    repo_root: Path,
    enable_dev_preset: bool,
    include_mcp: bool,
) -> dict[str, Any]:
    """Inspecciona que mejoraria antes de inyectar."""
    categories = {
        "agents": compare_named_directories(
            repo_root / ".agent" / "agents",
            target_dir / ".agent" / "agents",
        ),
        "skills": compare_named_directories(
            repo_root / ".agent" / "skills",
            target_dir / ".agent" / "skills",
        ),
        "skillsCustom": compare_named_directories(
            repo_root / ".agent" / "skills-custom",
            target_dir / ".agent" / "skills-custom",
            skip_prefixes=(".",),
        ),
    }

    runtime_checks = {
        name: compare_paths(source, target)
        for name, (source, target) in get_runtime_path_pairs(repo_root, target_dir).items()
    }
    out_of_scope = _collect_out_of_scope_items(target_dir)

    mcp_checks: dict[str, str] = {}
    if include_mcp:
        for path in [
            target_dir / ".mcp.json",
            target_dir / ".cursor" / "mcp.json",
            target_dir / ".windsurf" / "mcp.json",
            target_dir / ".vscode" / "mcp.json",
            target_dir / ".vscode" / "cline_mcp_settings.json",
            target_dir / ".zed" / "settings.json",
        ]:
            mcp_checks[str(path.relative_to(target_dir))] = (
                "present" if path.exists() else "missing"
            )

    total_new = sum(len(data["new"]) for data in categories.values())
    total_updated = sum(len(data["updated"]) for data in categories.values())
    total_target_only = sum(len(data["targetOnly"]) for data in categories.values())
    runtime_new = sum(1 for item in runtime_checks.values() if item["status"] == "new")
    runtime_updated = sum(1 for item in runtime_checks.values() if item["status"] == "updated")
    upstream_items = total_new + runtime_new
    conflict_items = total_updated + runtime_updated
    difference_items = upstream_items + conflict_items + total_target_only
    out_of_scope_items = len(out_of_scope["agents"]) + len(out_of_scope["skills"])

    classification_counts = {
        "functional": 0,
        "documentation": 0,
        "minor": 0,
        "possibleConflict": 0,
    }

    for category in categories.values():
        for status in ("new", "updated", "targetOnly"):
            for detail in category.get("details", {}).get(status, []):
                classification = detail.get("classification", "minor")
                classification_counts[classification] = (
                    classification_counts.get(classification, 0) + 1
                )

    for item in runtime_checks.values():
        if item["status"] in {"new", "updated"}:
            classification = item.get("classification", "minor")
            classification_counts[classification] = classification_counts.get(classification, 0) + 1

    return {
        "success": True,
        "mode": "mcp" if include_mcp else "local",
        "devPreset": enable_dev_preset,
        "summary": {
            "differenceItems": difference_items,
            "upstreamItems": upstream_items,
            "conflictItems": conflict_items,
            "targetOnlyItems": total_target_only,
            "outOfScopeItems": out_of_scope_items,
            "unchangedItems": sum(data["unchanged"] for data in categories.values()),
            "hasUpstreamChanges": upstream_items > 0,
            "hasConflicts": conflict_items > 0,
            "hasTargetExtras": total_target_only > 0,
            "hasOutOfScope": out_of_scope_items > 0,
            "classificationCounts": classification_counts,
        },
        "categories": categories,
        "runtime": runtime_checks,
        "mcp": mcp_checks,
        "outOfScope": out_of_scope,
    }


def summarize_reinjection_targets(analysis: dict[str, Any]) -> dict[str, Any]:
    """Resume rutas candidatas a cambio durante una reinyección."""
    touched_paths: list[str] = []

    for category_name, category in analysis.get("categories", {}).items():
        for status in ("new", "updated"):
            for name in category.get(status, []):
                touched_paths.append(f".agent/{category_name}/{name}")

    for runtime_name, runtime_data in analysis.get("runtime", {}).items():
        if runtime_data.get("status") in {"new", "updated"}:
            touched_paths.append(runtime_name)

    for relative_path, status in analysis.get("mcp", {}).items():
        if status == "missing":
            touched_paths.append(relative_path)

    unique_paths = sorted(dict.fromkeys(touched_paths))
    return {
        "touchedPaths": unique_paths,
        "touchedCount": len(unique_paths),
    }


def build_human_dry_run_summary(
    analysis: dict[str, Any],
    reinjection: dict[str, Any],
) -> dict[str, Any]:
    """Construye un resumen corto, humano e idempotente para previews de reinyeccion."""
    summary = analysis.get("summary", {})
    touched_count = int(reinjection.get("touchedCount", 0))
    touched_paths = list(reinjection.get("touchedPaths", []))
    mode = analysis.get("mode", "mcp")

    if touched_count == 0:
        headline = f"Reinyeccion limpia en modo {mode}: no se tocaria ningun archivo."
    elif touched_count == 1:
        headline = f"Reinyeccion con cambios en modo {mode}: se tocaria 1 ruta."
    else:
        headline = f"Reinyeccion con cambios en modo {mode}: se tocarian {touched_count} rutas."

    bullets = [
        (
            "Sin cambios upstream ni divergencias detectadas."
            if not summary.get("hasUpstreamChanges") and not summary.get("hasConflicts")
            else f"Upstream: {summary.get('upstreamItems', 0)} | Conflictos: {summary.get('conflictItems', 0)} | Extras app: {summary.get('targetOnlyItems', 0)}."
        ),
        (
            "La superficie de reinyeccion esta vacia."
            if touched_count == 0
            else "Primeras rutas afectadas: "
            + ", ".join(touched_paths[:5])
            + ("." if touched_count <= 5 else ", ...")
        ),
        (
            f"Fuera de ruta canonica: {summary.get('outOfScopeItems', 0)} | "
            f"Clasificacion funcional/docs/menor/conflicto: "
            f"{summary.get('classificationCounts', {}).get('functional', 0)}/"
            f"{summary.get('classificationCounts', {}).get('documentation', 0)}/"
            f"{summary.get('classificationCounts', {}).get('minor', 0)}/"
            f"{summary.get('classificationCounts', {}).get('possibleConflict', 0)}."
        ),
    ]

    return {
        "headline": headline,
        "bullets": bullets,
    }


# ---------------------------------------------------------------------------
# Helpers para actualizacion de documentos
# ---------------------------------------------------------------------------


def update_markdown_section(
    path: Path,
    start_marker: str,
    end_marker: str,
    section: str,
) -> bool:
    """Inserta o reemplaza una seccion delimitada por marcadores.

    Delega en :func:`mcp_injector.markdown_update.update_markdown_section`
    para mantener una sola implementacion (idempotente) y evitar drift entre
    las dos copias que existian duplicadas byte a byte.
    """
    from .markdown_update import update_markdown_section as _update_markdown_section

    return _update_markdown_section(path, start_marker, end_marker, section)


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

    import os as _os

    persona_mode = _os.environ.get("ANTIGRAVITY_PERSONA", "gentleman")
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
- MiniMax: si detectamos Claude Code o Codex, el inyector puede integrar tambien las skills oficiales de `MiniMax-AI/skills`.
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


def install_copilot_instructions(target_dir: Path, repo_root: Path) -> bool:
    """Escribe .github/copilot-instructions.md con contexto del ecosistema Antigravity."""
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
            tier_lines.append(f"- ... y {len(unlisted) - 10} mas")

    content = f"""# AI Copilot Instructions — Antigravity Ecosystem

## Version
- Antigravity: {ECOSYSTEM_VERSION}
- Gateway: {gateway_url}

## Agents ({num_agents} agentes)
{tiers.get(1, []) and "".join(tier_lines) or "".join(tier_lines)}

## Skills
- Base: `.agent/skills/` (801 skills)
- Custom: `.agent/skills-custom/` (52 skills)
- Plugins: `.agent/plugins/` (78 skills)
"""

    copilot_path = target_dir / ".github" / "copilot-instructions.md"
    try:
        ensure_dir(copilot_path.parent)
        copilot_path.write_text(content, encoding="utf-8")
        logger.info("✅ [.github/copilot-instructions.md] Creado")
        return True
    except Exception as exc:
        logger.error(f"❌ [.github/copilot-instructions.md] Error: {exc}")
        return False


# ---------------------------------------------------------------------------
# Aplicacion de mejoras
# ---------------------------------------------------------------------------


def _hash_file(path: Path) -> str:
    """Calcula hash SHA-256 de un archivo."""
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def hash_tree(path: Path) -> str:
    """Calcula hash estable de un directorio o archivo (duplicado de io_utils para evitar circular import)."""
    if path.is_file():
        return _hash_file(path)

    digest = hashlib.sha256()
    SKIP_NAMES = frozenset(
        {".git", "__pycache__", ".pytest_cache", "node_modules", "dist", "build"}
    )
    for item in sorted(path.rglob("*")):
        if any(part in SKIP_NAMES for part in item.parts):
            continue
        relative = item.relative_to(path).as_posix().encode("utf-8")
        digest.update(relative)
        if item.is_file():
            digest.update(_hash_file(item).encode("ascii"))
    return digest.hexdigest()


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


def apply_injection_improvements(
    target_dir: Path,
    repo_root: Path,
    enable_dev_preset: bool,
    include_mcp: bool,
    gateway_url: str,
    token: str = "",
) -> dict[str, Any]:
    """Aplica unicamente nuevos elementos y mejoras detectadas."""
    from .path_utils import detect_project_type

    analysis = inspect_installation(
        target_dir,
        repo_root,
        enable_dev_preset=enable_dev_preset,
        include_mcp=include_mcp,
    )

    category_roots = {
        "agents": (
            repo_root / ".agent" / "agents",
            target_dir / ".agent" / "agents",
        ),
        "skills": (
            repo_root / ".agent" / "skills",
            target_dir / ".agent" / "skills",
        ),
        "skillsCustom": (
            repo_root / ".agent" / "skills-custom",
            target_dir / ".agent" / "skills-custom",
        ),
    }

    applied_categories: dict[str, list[str]] = {}
    for category, (source_root, target_root) in category_roots.items():
        category_data = analysis["categories"][category]
        names = [*category_data["new"], *category_data["updated"]]
        applied_categories[category] = copy_named_entries(source_root, target_root, names)

    runtime_applied: list[str] = []
    for name, (source, target) in get_runtime_path_pairs(repo_root, target_dir).items():
        status = analysis["runtime"][name]["status"]
        if status in {"new", "updated"} and copy_path_if_needed(source, target):
            runtime_applied.append(name)

    install_project_memory(target_dir, repo_root)
    remove_legacy_claude_dirs(target_dir)
    install_antigravity_config(
        target_dir,
        repo_root,
        enable_dev_preset=enable_dev_preset,
        gateway_url=gateway_url,
        token=token,
    )
    install_ai_manifest(
        target_dir,
        gateway_url=gateway_url,
        enable_dev_preset=enable_dev_preset,
        mcp_enabled=include_mcp,
        remote_enabled=bool(token) or _is_remote(gateway_url),
    )

    project_type = detect_project_type(target_dir)
    update_claude_md(target_dir, project_type)
    update_agents_md(target_dir)

    if include_mcp:
        inject_workspace(
            target_dir,
            repo_root,
            enable_dev_preset=enable_dev_preset,
            gateway_url=gateway_url,
            token=token,
        )

    return {
        "success": True,
        "mode": "mcp" if include_mcp else "local",
        "applied": {
            **applied_categories,
            "runtime": runtime_applied,
        },
        "summary": {
            "appliedItems": sum(len(items) for items in applied_categories.values())
            + len(runtime_applied),
            "hasChanges": any(applied_categories.values()) or bool(runtime_applied),
        },
        "analysis": analysis,
    }


# ---------------------------------------------------------------------------
# Importacion de cambios del target
# ---------------------------------------------------------------------------


def remove_legacy_claude_dirs(target_dir: Path) -> None:
    """Elimina directorios legacy de .claude en el target."""
    from .io_utils import safe_remove_legacy

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


def ensure_dir(path: Path) -> None:
    """Crea un directorio si no existe."""
    path.mkdir(parents=True, exist_ok=True)


def _is_remote(gateway_url: str) -> bool:
    """Determina si el gateway apunta a un endpoint remoto."""
    normalized = gateway_url.strip().lower()
    if not normalized:
        return False
    return not (
        normalized.startswith("http://localhost")
        or normalized.startswith("http://127.0.0.1")
        or normalized.startswith("https://localhost")
        or normalized.startswith("https://127.0.0.1")
    )


def import_target_extras_to_repo(target_dir: Path, repo_root: Path) -> dict[str, Any]:
    """Importa extras locales de la app destino de vuelta a Antigravity."""
    analysis = inspect_installation(
        target_dir,
        repo_root,
        enable_dev_preset=False,
        include_mcp=False,
    )

    imported_agents = copy_named_entries(
        target_dir / ".agent" / "agents",
        repo_root / ".agent" / "agents",
        analysis["categories"]["agents"]["targetOnly"],
    )
    imported_skills = copy_named_entries(
        target_dir / ".agent" / "skills",
        repo_root / ".agent" / "skills",
        analysis["categories"]["skills"]["targetOnly"],
    )
    imported_skills_custom = copy_named_entries(
        target_dir / ".agent" / "skills-custom",
        repo_root / ".agent" / "skills-custom",
        analysis["categories"]["skillsCustom"]["targetOnly"],
    )

    return {
        "success": True,
        "imported": {
            "agents": imported_agents,
            "skills": imported_skills,
            "skillsCustom": imported_skills_custom,
        },
        "summary": {
            "importedItems": (
                len(imported_agents) + len(imported_skills) + len(imported_skills_custom)
            ),
            "hasImports": any(
                [
                    imported_agents,
                    imported_skills,
                    imported_skills_custom,
                ]
            ),
        },
        "analysis": analysis,
    }


# ---------------------------------------------------------------------------
# Smart Merge y Deteccion de Conflictos
# ---------------------------------------------------------------------------

_MD_EXTENSIONS = {".md"}


def parse_yaml_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """Extrae el frontmatter YAML delimitado por ``---`` al inicio del archivo."""
    lines = content.split("\n")
    if not lines or lines[0].strip() != "---":
        return {}, content

    end_idx: int | None = None
    for idx, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            end_idx = idx
            break

    if end_idx is None:
        return {}, content

    frontmatter: dict[str, Any] = {}
    for line in lines[1:end_idx]:
        if ":" in line:
            key, _, value = line.partition(":")
            frontmatter[key.strip()] = value.strip()

    return frontmatter, "\n".join(lines[end_idx + 1 :])


def parse_markdown_sections(content: str) -> dict[str, str]:
    """Divide un archivo markdown en secciones delimitadas por cabeceras ``##``."""
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


def smart_merge(
    nexus_content: str,
    app_content: str,
    file_name: str = "",
) -> tuple[str | None, list[dict[str, str]]]:
    """Intenta fusionar dos versiones de un archivo markdown de forma inteligente."""
    ext = Path(file_name).suffix.lower() if file_name else ""
    if ext not in _MD_EXTENSIONS:
        return None, [{"section": "__full_file__", "nexus": nexus_content, "app": app_content}]

    if nexus_content == app_content:
        return nexus_content, []

    nexus_fm, nexus_body = parse_yaml_frontmatter(nexus_content)
    app_fm, app_body = parse_yaml_frontmatter(app_content)

    merged_fm: dict[str, Any] = {}
    conflicts: list[dict[str, str]] = []

    all_fm_keys = set(nexus_fm.keys()) | set(app_fm.keys())
    for key in sorted(all_fm_keys):
        nexus_val = nexus_fm.get(key)
        app_val = app_fm.get(key)
        if nexus_val == app_val:
            merged_fm[key] = nexus_val  # type: ignore[assignment]
        elif nexus_val is None:
            merged_fm[key] = app_val  # type: ignore[assignment]
        elif app_val is None:
            merged_fm[key] = nexus_val
        else:
            conflicts.append(
                {
                    "section": f"frontmatter.{key}",
                    "nexus": str(nexus_val),
                    "app": str(app_val),
                }
            )

    nexus_sections = parse_markdown_sections(nexus_body)
    app_sections = parse_markdown_sections(app_body)

    all_section_keys = list(dict.fromkeys(list(nexus_sections.keys()) + list(app_sections.keys())))
    merged_sections: dict[str, str] = {}

    for key in all_section_keys:
        nexus_sec = nexus_sections.get(key)
        app_sec = app_sections.get(key)
        if nexus_sec == app_sec:
            merged_sections[key] = nexus_sec  # type: ignore[assignment]
        elif nexus_sec is None:
            merged_sections[key] = app_sec  # type: ignore[assignment]
        elif app_sec is None:
            merged_sections[key] = nexus_sec
        else:
            conflicts.append(
                {
                    "section": key,
                    "nexus": nexus_sec,
                    "app": app_sec,
                }
            )

    if conflicts:
        return None, conflicts

    parts: list[str] = []
    if merged_fm:
        parts.append("---\n")
        for key, val in merged_fm.items():
            parts.append(f"{key}: {val}\n")
        parts.append("---\n")

    for key in all_section_keys:
        parts.append(merged_sections[key])

    merged = "".join(parts)
    return merged, []


def detect_real_conflicts(
    target_dir: Path,
    repo_root: Path,
    names_by_category: dict[str, list[str]],
) -> dict[str, list[dict[str, Any]]]:
    """Analiza los archivos actualizados y clasifica entre auto-merge y conflicto."""
    category_roots = {
        "agents": (
            target_dir / ".agent" / "agents",
            repo_root / ".agent" / "agents",
        ),
        "skills": (
            target_dir / ".agent" / "skills",
            repo_root / ".agent" / "skills",
        ),
        "skillsCustom": (
            target_dir / ".agent" / "skills-custom",
            repo_root / ".agent" / "skills-custom",
        ),
    }

    result: dict[str, list[dict[str, Any]]] = {"auto_merged": [], "conflicts": []}

    for category, names in names_by_category.items():
        if category not in category_roots:
            continue
        app_root, nexus_root = category_roots[category]

        for name in names:
            app_dir = app_root / name
            nexus_dir = nexus_root / name

            if not app_dir.exists() or not nexus_dir.exists():
                continue

            md_files: set[str] = set()
            non_md_conflict = False

            if app_dir.is_dir() and nexus_dir.is_dir():
                for f in app_dir.rglob("*"):
                    if f.is_file():
                        rel = str(f.relative_to(app_dir))
                        if f.suffix.lower() in _MD_EXTENSIONS:
                            md_files.add(rel)
                        else:
                            nexus_f = nexus_dir / rel
                            if nexus_f.exists() and hash_tree(f) != hash_tree(nexus_f):
                                non_md_conflict = True
                for f in nexus_dir.rglob("*"):
                    if f.is_file() and f.suffix.lower() in _MD_EXTENSIONS:
                        md_files.add(str(f.relative_to(nexus_dir)))
            elif app_dir.is_file() and nexus_dir.is_file():
                if app_dir.suffix.lower() in _MD_EXTENSIONS:
                    md_files.add(app_dir.name)
                else:
                    non_md_conflict = True

            entry_conflicts: list[dict[str, str]] = []
            entry_merges: dict[str, str] = {}

            for md_rel in sorted(md_files):
                app_file = (app_dir / md_rel) if app_dir.is_dir() else app_dir
                nexus_file = (nexus_dir / md_rel) if nexus_dir.is_dir() else nexus_dir

                if not app_file.exists() or not nexus_file.exists():
                    continue

                try:
                    app_text = app_file.read_text(encoding="utf-8")
                    nexus_text = nexus_file.read_text(encoding="utf-8")
                except OSError:
                    non_md_conflict = True
                    continue

                merged, conflicts = smart_merge(nexus_text, app_text, file_name=md_rel)
                if merged is not None:
                    entry_merges[md_rel] = merged
                else:
                    entry_conflicts.extend(conflicts)

            if entry_conflicts or non_md_conflict:
                conflict_entry: dict[str, Any] = {
                    "name": name,
                    "category": category,
                    "conflict_sections": entry_conflicts,
                }
                if app_dir.is_dir():
                    for md_rel in sorted(md_files):
                        app_file = app_dir / md_rel
                        nexus_file = nexus_dir / md_rel
                        if app_file.exists():
                            try:
                                conflict_entry.setdefault("app_content", {})[md_rel] = (
                                    app_file.read_text(encoding="utf-8")
                                )
                            except OSError:
                                pass
                        if nexus_file.exists():
                            try:
                                conflict_entry.setdefault("nexus_content", {})[md_rel] = (
                                    nexus_file.read_text(encoding="utf-8")
                                )
                            except OSError:
                                pass
                result["conflicts"].append(conflict_entry)
            elif entry_merges:
                result["auto_merged"].append(
                    {
                        "name": name,
                        "category": category,
                        "merged_content": entry_merges,
                    }
                )

    return result


def apply_conflict_resolution(
    resolutions: list[dict[str, Any]],
    target_dir: Path,
    repo_root: Path,
) -> dict[str, Any]:
    """Aplica las resoluciones de conflicto elegidas por el usuario."""
    category_roots = {
        "agents": (
            target_dir / ".agent" / "agents",
            repo_root / ".agent" / "agents",
        ),
        "skills": (
            target_dir / ".agent" / "skills",
            repo_root / ".agent" / "skills",
        ),
        "skillsCustom": (
            target_dir / ".agent" / "skills-custom",
            repo_root / ".agent" / "skills-custom",
        ),
    }

    applied: list[str] = []
    errors: list[dict[str, str]] = []

    for resolution in resolutions:
        name = resolution.get("name", "")
        category = resolution.get("category", "")
        choice = resolution.get("choice", "")

        if category not in category_roots:
            errors.append({"name": name, "error": f"Categoria desconocida: {category}"})
            continue

        app_root, nexus_root = category_roots[category]
        app_path = app_root / name
        nexus_path = nexus_root / name

        try:
            if choice == "app":
                if app_path.exists():
                    if app_path.is_dir():
                        if nexus_path.exists():
                            shutil.rmtree(nexus_path)
                        shutil.copytree(app_path, nexus_path)
                    else:
                        shutil.copy2(app_path, nexus_path)
                    applied.append(f"{category}/{name} (app→nexus)")
            elif choice == "nexus":
                if nexus_path.exists():
                    if nexus_path.is_dir():
                        if app_path.exists():
                            shutil.rmtree(app_path)
                        shutil.copytree(nexus_path, app_path)
                    else:
                        shutil.copy2(nexus_path, app_path)
                    applied.append(f"{category}/{name} (nexus→app)")
            elif choice == "merged":
                merged_content = resolution.get("merged_content", {})
                if isinstance(merged_content, dict):
                    for rel_path, content in merged_content.items():
                        dest_nexus = nexus_path / rel_path if nexus_path.is_dir() else nexus_path
                        dest_app = app_path / rel_path if app_path.is_dir() else app_path
                        dest_nexus.parent.mkdir(parents=True, exist_ok=True)
                        dest_app.parent.mkdir(parents=True, exist_ok=True)
                        dest_nexus.write_text(content, encoding="utf-8")
                        dest_app.write_text(content, encoding="utf-8")
                elif isinstance(merged_content, str):
                    nexus_path.parent.mkdir(parents=True, exist_ok=True)
                    app_path.parent.mkdir(parents=True, exist_ok=True)
                    nexus_path.write_text(merged_content, encoding="utf-8")
                    app_path.write_text(merged_content, encoding="utf-8")
                applied.append(f"{category}/{name} (merged)")
            else:
                errors.append({"name": name, "error": f"Choice no valido: {choice}"})
        except OSError as exc:
            errors.append({"name": name, "error": str(exc)})

    return {
        "success": len(errors) == 0,
        "applied": applied,
        "errors": errors,
        "summary": {
            "appliedCount": len(applied),
            "errorCount": len(errors),
        },
    }


def import_all_target_changes_to_repo(target_dir: Path, repo_root: Path) -> dict[str, Any]:
    """Importa extras y cambios locales de la app hacia Nexus, con smart merge y deteccion de conflictos."""
    analysis = inspect_installation(
        target_dir,
        repo_root,
        enable_dev_preset=False,
        include_mcp=False,
    )

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = repo_root / ".antigravity" / "import-conflicts" / timestamp

    category_roots = {
        "agents": (
            target_dir / ".agent" / "agents",
            repo_root / ".agent" / "agents",
        ),
        "skills": (
            target_dir / ".agent" / "skills",
            repo_root / ".agent" / "skills",
        ),
        "skillsCustom": (
            target_dir / ".agent" / "skills-custom",
            repo_root / ".agent" / "skills-custom",
        ),
    }

    imported_new: dict[str, list[str]] = {}
    imported_conflicts: dict[str, list[str]] = {}
    backup_paths: list[str] = []

    updated_by_category: dict[str, list[str]] = {}
    for category in category_roots:
        category_data = analysis["categories"][category]
        updated_by_category[category] = category_data["updated"]

    conflict_detection = detect_real_conflicts(target_dir, repo_root, updated_by_category)

    auto_merged_names: dict[str, list[str]] = {}
    for entry in conflict_detection["auto_merged"]:
        cat = entry["category"]
        name = entry["name"]
        merged_content = entry["merged_content"]
        auto_merged_names.setdefault(cat, []).append(name)

        if cat in category_roots:
            _app_root, nexus_root = category_roots[cat]
            nexus_dir = nexus_root / name
            for rel_path, content in merged_content.items():
                dest = nexus_dir / rel_path if nexus_dir.is_dir() else nexus_dir
                dest.parent.mkdir(parents=True, exist_ok=True)
                dest.write_text(content, encoding="utf-8")

    real_conflict_names: set[str] = {entry["name"] for entry in conflict_detection["conflicts"]}

    for category, (source_root, target_root) in category_roots.items():
        category_data = analysis["categories"][category]
        imported_new[category] = copy_named_entries(
            source_root, target_root, category_data["targetOnly"]
        )

        remaining_updated = [
            name
            for name in category_data["updated"]
            if name not in real_conflict_names and name not in auto_merged_names.get(category, [])
        ]
        _imported, _backups = import_named_entries_with_backup(
            source_root,
            target_root,
            remaining_updated,
            backup_root=backup_root,
            backup_prefix="updated",
        )
        backup_paths.extend(_backups)

    return {
        "success": True,
        "imported": {
            "new": imported_new,
            "conflicts": imported_conflicts,
            "autoMerged": auto_merged_names,
        },
        "backups": backup_paths,
        "analysis": analysis,
    }


# ---------------------------------------------------------------------------
# Knowledge Brief helpers
# ---------------------------------------------------------------------------


def _write_knowledge_brief(target_dir: Path, repo_root: Path) -> None:
    """Genera y escribe KNOWLEDGE_BRIEF.md en el proyecto target.

    Usa el UnifiedKnowledgeBridge para recopilar todo el conocimiento
    del proyecto (decisiones, errores, hotspots, sesiones, CI) y lo
    escribe como markdown legible por cualquier IA.
    """
    import asyncio

    try:
        core_path = str(repo_root / ".agent")
        if core_path not in sys.path:
            sys.path.insert(0, core_path)
        from core.unified_knowledge_bridge import UnifiedKnowledgeBridge
    except ImportError:
        logger.debug("  [knowledge-brief] UnifiedKnowledgeBridge not available")
        return

    bridge = UnifiedKnowledgeBridge(project_root=str(repo_root))

    # Generar brief de forma sync (el injector no es async)
    try:
        loop = asyncio.new_event_loop()
        brief = loop.run_until_complete(bridge.generate_knowledge_brief(max_chars=6000))
        loop.close()
    except Exception:
        # Fallback: generar brief minimo sin async sources
        brief = _generate_minimal_brief(repo_root)

    if not brief or len(brief) < 50:
        return

    # Escribir en .antigravity/memory/ del target
    knowledge_dir = target_dir / ".antigravity" / "memory"
    knowledge_dir.mkdir(parents=True, exist_ok=True)
    brief_path = knowledge_dir / "KNOWLEDGE_BRIEF.md"
    brief_path.write_text(brief, encoding="utf-8")
    logger.info("  [knowledge-brief] wrote %d chars → %s", len(brief), brief_path)


def _generate_minimal_brief(repo_root: Path) -> str:
    """Genera un brief minimo sin async sources (fallback)."""
    lines: list[str] = ["# Knowledge Brief (Minimal)", ""]

    # Intentar leer ESTADO_PROYECTO.md
    estado = repo_root / "ESTADO_PROYECTO.md"
    if estado.exists():
        try:
            content = estado.read_text(encoding="utf-8")[:3000]
            lines.append("## Estado del Proyecto\n")
            lines.append(content)
        except OSError:
            pass

    # Intentar leer decisiones de .claude/memory/
    memory_dir = repo_root / ".claude" / "memory"
    if memory_dir.exists():
        decision_files = sorted(memory_dir.glob("decision_*.md"))[:5]
        if decision_files:
            lines.append("\n## Decisiones Recientes\n")
            for f in decision_files:
                try:
                    content = f.read_text(encoding="utf-8")[:500]
                    lines.append(f"### {f.stem}\n{content}\n")
                except OSError:
                    pass

    return "\n".join(lines) if len(lines) > 2 else ""


def _install_session_hooks(target_dir: Path) -> None:
    """Instala hooks de reporte de sesion en el proyecto target.

    Cuando Claude Code termina una sesion en el proyecto inyectado,
    el hook envia un resumen al gateway de Nexus para memoria centralizada.
    """
    hooks_dir = target_dir / ".claude" / "hooks" / "scripts"
    hooks_dir.mkdir(parents=True, exist_ok=True)

    # Create the session report script
    hook_script = hooks_dir / "session-report.sh"
    script_content = (
        "#!/usr/bin/env bash\n"
        "# Auto-generated by Antigravity MCP Injector\n"
        "# Uses the authenticated portable client; session.key is encrypted at rest.\n"
        'GATEWAY="${ANTIGRAVITY_GATEWAY_URL:-http://127.0.0.1:4747}"\n'
        'SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"\n'
        'PROJECT_ROOT="$(cd "$SCRIPT_DIR/../../.." && pwd)"\n'
        'PORTABLE="$PROJECT_ROOT/.antigravity/runtime/current/antigravity-mcp/antigravity-mcp"\n'
        'if [ ! -e "$PORTABLE" ] && [ ! -e "${PORTABLE}.exe" ]; then '
        'PORTABLE="$PROJECT_ROOT/.antigravity/runtime/current/antigravity-mcp"; fi\n'
        'if [ -x "${PORTABLE}.exe" ]; then\n'
        '  "${PORTABLE}.exe" session-report --gateway "$GATEWAY" || true\n'
        'elif [ -x "$PORTABLE" ]; then\n'
        '  "$PORTABLE" session-report --gateway "$GATEWAY" || true\n'
        "else\n"
        '  PRIVATE_PYTHON="$PROJECT_ROOT/.antigravity/runtime/current/python/python.exe"\n'
        '  if [ ! -x "$PRIVATE_PYTHON" ]; then '
        'PRIVATE_PYTHON="$PROJECT_ROOT/.antigravity/runtime/current/python/bin/python3"; fi\n'
        '  if [ ! -x "$PRIVATE_PYTHON" ]; then '
        'PRIVATE_PYTHON="$PROJECT_ROOT/.venv/Scripts/python.exe"; fi\n'
        '  if [ ! -x "$PRIVATE_PYTHON" ]; then '
        'PRIVATE_PYTHON="$PROJECT_ROOT/.venv/bin/python3"; fi\n'
        '  if [ -x "$PRIVATE_PYTHON" ]; then\n'
        '    PYTHONPATH="$PROJECT_ROOT/.agent" "$PRIVATE_PYTHON" '
        '-m core.gateway_client session-report --gateway "$GATEWAY" || true\n'
        "  fi\n"
        "fi\n"
    )
    hook_script.write_text(script_content, encoding="utf-8")
    hook_script.chmod(0o755)

    # Register the hook in .claude/settings.json if not already present
    settings_path = target_dir / ".claude" / "settings.json"
    settings: dict[str, Any] = {}
    if settings_path.exists():
        try:
            settings = json.loads(settings_path.read_text(encoding="utf-8"))
        except Exception:
            settings = {}

    hooks = settings.setdefault("hooks", {})
    stop_hooks = hooks.setdefault("Stop", [])

    # Check if already installed (comparacion estructural sobre command).
    # Cubre 3 formas validas en Claude Code:
    #   - anidada:    {matcher, hooks: [{type, command, ...}]}  (lo que el injector appendea)
    #   - flat:       {type, command, ...}                       (schema alternativa valida)
    #   - flat str:   str con el comando                          (forma rara, posible manual)
    # Tambien detecta comando prefijado por "bash " (paths absolutos escritos a mano).
    hook_cmd = '".claude/hooks/scripts/session-report.sh"'

    def _is_session_report_command(command: object) -> bool:
        if not isinstance(command, str):
            return False
        normalized = command.replace("\\", "/").lower()
        normalized = " ".join(normalized.replace('"', "").replace("'", "").split())
        return ".claude/hooks/scripts/session-report.sh" in normalized

    # Remove every semantic duplicate while preserving unrelated user hooks,
    # then append one canonical representation.
    cleaned_stop_hooks: list[object] = []
    for entry in stop_hooks:
        if isinstance(entry, str):
            if not _is_session_report_command(entry):
                cleaned_stop_hooks.append(entry)
            continue
        if not isinstance(entry, dict):
            cleaned_stop_hooks.append(entry)
            continue
        if _is_session_report_command(entry.get("command")):
            continue
        nested = entry.get("hooks")
        if isinstance(nested, list):
            cleaned_nested = [
                hook
                for hook in nested
                if not (isinstance(hook, dict) and _is_session_report_command(hook.get("command")))
            ]
            if cleaned_nested:
                cleaned_entry = {**entry, "hooks": cleaned_nested}
                cleaned_stop_hooks.append(cleaned_entry)
            continue
        cleaned_stop_hooks.append(entry)

    cleaned_stop_hooks.append(
        {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": hook_cmd,
                    "timeout": 10000,
                }
            ],
        }
    )
    hooks["Stop"] = cleaned_stop_hooks

    serialized = json.dumps(settings, indent=2, ensure_ascii=False)
    existing_serialized = (
        settings_path.read_text(encoding="utf-8") if settings_path.exists() else ""
    )
    if existing_serialized != serialized:
        settings_path.parent.mkdir(parents=True, exist_ok=True)
        settings_path.write_text(serialized, encoding="utf-8")
        logger.info("  [session-hooks] normalized one authenticated Stop hook")
    else:
        logger.info("  [session-hooks] canonical hook already installed")


# ---------------------------------------------------------------------------
# Inyeccion de workspace MCP
# ---------------------------------------------------------------------------


def inject_workspace(
    target_dir: Path,
    repo_root: Path,
    enable_dev_preset: bool = True,
    gateway_url: str = DEFAULT_GATEWAY_URL,
    token: str = "",
) -> bool:
    """Escribe configuraciones MCP para IDEs soportados. Retorna False si algun cliente falló."""
    logger.info("\n[INFO] ------------------------------------------------")
    logger.info("[INFO] Configurando clientes MCP del proyecto")
    logger.info(f"[INFO] Ruta: {target_dir}")
    logger.info(f"[INFO] Gateway: {gateway_url}")
    logger.info("[INFO] ------------------------------------------------\n")

    servers = get_mcp_servers(
        repo_root,
        target_dir,
        enable_dev_preset,
        gateway_url=gateway_url,
        token=token,
    )

    failures: list[str] = []

    json_targets = [
        ("Cursor", target_dir / ".cursor" / "mcp.json"),
        ("Windsurf", target_dir / ".windsurf" / "mcp.json"),
        ("Roo Code / Cline", target_dir / ".vscode" / "cline_mcp_settings.json"),
        ("Claude Local", target_dir / ".mcp.json"),
    ]

    for name, path in json_targets:
        if safe_merge_json(path, servers):
            logger.info(f"✅ [{name}] Configurado con smart-merge")
        else:
            logger.error(f"❌ [{name}] Falló la configuracion — ruta: {path}")
            failures.append(name)

    # VS Code (GitHub Copilot, modo Agent) usa formato nativo distinto: clave raiz
    # "servers" + campo "type" por servidor + variables ${env:VAR}. Cline (arriba)
    # SI usa mcpServers sobre cline_mcp_settings.json. Ver bugfix_vscode_mcp_servers_key.
    vscode_mcp_path = target_dir / ".vscode" / "mcp.json"
    if safe_merge_vscode_mcp(vscode_mcp_path, servers):
        logger.info("✅ [VS Code MCP] Configurado con formato nativo (servers + type)")
    else:
        logger.error(f"❌ [VS Code MCP] Falló la configuracion — ruta: {vscode_mcp_path}")
        failures.append("VS Code MCP")

    zed_path = target_dir / ".zed" / "settings.json"
    if safe_merge_zed_settings(zed_path, servers):
        logger.info("✅ [Zed] Configurado con context_servers")
    else:
        logger.error(f"❌ [Zed] Falló la configuracion — ruta: {zed_path}")
        failures.append("Zed")

    continue_path = target_dir / ".continue" / "config.json"
    if safe_merge_continue_json(continue_path, servers):
        logger.info("✅ [Continue.dev] Configurado con modelContextProtocolServers")
    else:
        logger.error(f"❌ [Continue.dev] Falló la configuracion — ruta: {continue_path}")
        failures.append("Continue.dev")

    gemini_path = target_dir / ".gemini" / "settings.json"
    if safe_merge_json(gemini_path, servers):
        logger.info("✅ [Gemini] Configurado con una entrada MCP antigravity")
    else:
        logger.error(f"❌ [Gemini] Falló la configuración — ruta: {gemini_path}")
        failures.append("Gemini")

    codex_path = target_dir / ".codex" / "config.toml"
    if safe_merge_codex_toml(codex_path, servers):
        logger.info("✅ [Codex] Configurado con una entrada MCP antigravity")
    else:
        logger.error(f"❌ [Codex] Falló la configuración — ruta: {codex_path}")
        failures.append("Codex")

    install_copilot_instructions(target_dir, repo_root)

    # --- Knowledge Brief: inyectar contexto completo del proyecto ---
    try:
        _write_knowledge_brief(target_dir, repo_root)
    except Exception as exc:
        logger.info("  [knowledge-brief] skipped: %s", exc)

    # --- Session reporting hooks ---
    try:
        _install_session_hooks(target_dir)
    except Exception as exc:
        logger.info("  [session-hooks] skipped: %s", exc)

    if failures:
        logger.warning(
            f"⚠️ [inject_workspace] {len(failures)} cliente(s) fallaron: {', '.join(failures)}"
        )
        return False
    return True


# ---------------------------------------------------------------------------
# Smoke test post-inyeccion
# ---------------------------------------------------------------------------


def run_post_injection_smoke(target_dir: Path) -> bool:
    """Valida runtime, hooks y configuracion minima post-inyeccion."""
    required = [
        ".agent/scripts/hook_runner.py",
        ".agent/scripts/session_hook.py",
        ".agent/scripts/git_sync_hook.py",
        ".claude/settings.json",
        ".antigravity/ai_manifest.json",
        ".agent/VERSION",
    ]
    missing = [rel for rel in required if not (target_dir / rel).exists()]
    if missing:
        logger.error(f"❌ [SMOKE] Faltan archivos criticos: {', '.join(missing)}")
        return False

    manifest_path = target_dir / ".antigravity" / "ai_manifest.json"
    try:
        manifest_raw = manifest_path.read_text(encoding="utf-8").strip()
        if not manifest_raw:
            logger.error("❌ [SMOKE] .antigravity/ai_manifest.json existe pero esta VACÍO")
            return False
        import json as _json_check

        _json_check.loads(manifest_raw)
    except ValueError as exc:
        logger.error(f"❌ [SMOKE] .antigravity/ai_manifest.json contiene JSON invalido: {exc}")
        return False
    except Exception as exc:
        logger.error(f"❌ [SMOKE] Error leyendo .antigravity/ai_manifest.json: {exc}")
        return False

    leftovers = find_legacy_claude_entries(target_dir)
    if leftovers:
        logger.error(f"❌ [SMOKE] Legacy detectado en destino: {', '.join(leftovers)}")
        return False

    portable_issues: list[str] = []
    for dirname in CLAUDE_DIRS:
        claude_dir = target_dir / ".claude" / dirname
        if not claude_dir.exists():
            continue
        for file_path in claude_dir.rglob("*"):
            if not file_path.is_file():
                continue
            try:
                content = file_path.read_text(encoding="utf-8", errors="ignore")
            except (OSError, UnicodeDecodeError):
                continue
            for marker in NON_PORTABLE_CLAUDE_MARKERS:
                if marker in content:
                    portable_issues.append(str(file_path.relative_to(target_dir)))
                    break
    if portable_issues:
        logger.error(
            "❌ [SMOKE] Se detectaron assets .claude no portables: %s",
            ", ".join(sorted(set(portable_issues))),
        )
        return False

    settings = read_json_file(target_dir / ".claude" / "settings.json")
    hooks = settings.get("hooks")
    if isinstance(hooks, dict):
        non_utf8_commands: list[str] = []
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
                    if isinstance(command, str) and command.strip().startswith(
                        ("python ", "python3 ", "py ")
                    ):
                        if " -X utf8 " not in f" {command} ":
                            non_utf8_commands.append(command)
        if non_utf8_commands:
            logger.error("❌ [SMOKE] Hooks Python sin `-X utf8` detectados")
            return False

    stop_entries = hooks.get("Stop", []) if isinstance(hooks, dict) else []
    session_report_count = 0
    for entry in stop_entries if isinstance(stop_entries, list) else []:
        if isinstance(entry, str):
            commands = [entry]
        elif isinstance(entry, dict):
            commands = [entry.get("command")]
            nested = entry.get("hooks", [])
            if isinstance(nested, list):
                commands.extend(hook.get("command") for hook in nested if isinstance(hook, dict))
        else:
            commands = []
        session_report_count += sum(
            isinstance(command, str)
            and ".claude/hooks/scripts/session-report.sh" in command.replace("\\", "/").lower()
            for command in commands
        )
    if session_report_count != 1:
        logger.error(
            "❌ [SMOKE] Se esperó un solo session-report hook; encontrados: %d",
            session_report_count,
        )
        return False

    mcp_config_path = target_dir / ".mcp.json"
    mcp_config = read_json_file(mcp_config_path)
    mcp_servers = mcp_config.get("mcpServers")
    if mcp_config_path.exists() and (
        not isinstance(mcp_servers, dict) or "antigravity" not in mcp_servers
    ):
        logger.error("❌ [SMOKE] .mcp.json no declara el broker antigravity")
        return False
    if not isinstance(mcp_servers, dict):
        mcp_servers = {}
    legacy_entries = sorted(
        name
        for name in mcp_servers
        if name in LEGACY_MANAGED_MCP_SERVER_NAMES and name != "antigravity"
    )
    if legacy_entries:
        logger.error(
            "❌ [SMOKE] Entradas MCP legacy administradas: %s",
            ", ".join(legacy_entries),
        )
        return False

    version_file = (target_dir / ".agent" / "VERSION").read_text(encoding="utf-8").strip()
    manifest = read_json_file(target_dir / ".antigravity" / "ai_manifest.json")
    manifest_version = str(manifest.get("version", "")).strip()
    if version_file and manifest_version and version_file != manifest_version:
        logger.error(
            f"❌ [SMOKE] Version mismatch: .agent/VERSION={version_file} vs ai_manifest={manifest_version}"
        )
        return False

    session_probe = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            ".agent/scripts/hook_runner.py",
            "session_hook.py",
            "--help",
        ],
        cwd=str(target_dir),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        shell=False,
        timeout=30,
    )
    if session_probe.returncode != 0:
        logger.error(
            f"❌ [SMOKE] session_hook probe falló: {(session_probe.stderr or session_probe.stdout or '').strip()}"
        )
        return False

    if (target_dir / ".git").exists():
        git_probe = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            cwd=str(target_dir),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=15,
        )
        if git_probe.returncode != 0:
            logger.error(f"❌ [SMOKE] git probe falló: {(git_probe.stderr or '').strip()}")
            return False

    if mcp_servers and os.environ.get("ANTIGRAVITY_INJECTOR_SKIP_LIVE_MCP", "").lower() not in {
        "1",
        "true",
        "yes",
        "on",
    }:
        if not _probe_injected_mcp(target_dir, mcp_servers["antigravity"]):
            return False

    logger.info("✅ [SMOKE] Validacion post-inyeccion OK")
    return True


def _probe_injected_mcp(target_dir: Path, server: Any) -> bool:
    """Run initialize/list/call transport smoke through the injected stdio entry."""

    if not isinstance(server, dict) or not isinstance(server.get("command"), str):
        logger.error("❌ [SMOKE MCP] Configuración antigravity inválida")
        return False

    def expand(value: str) -> str:
        replacements = {
            "${ANTIGRAVITY_ROOT}": str(target_dir),
            "${USERPROFILE}": str(Path.home()),
            "${HOME}": str(Path.home()),
        }
        for marker, replacement in replacements.items():
            value = value.replace(marker, replacement)
        return value

    command = expand(server["command"])
    args = [expand(str(item)) for item in server.get("args", [])]
    environment = os.environ.copy()
    configured_env = server.get("env", {})
    if isinstance(configured_env, dict):
        environment.update({str(key): expand(str(value)) for key, value in configured_env.items()})
    requests = [
        {
            "jsonrpc": "2.0",
            "id": 1,
            "method": "initialize",
            "params": {
                "protocolVersion": "2025-11-25",
                "capabilities": {},
                "clientInfo": {"name": "antigravity-injector-smoke", "version": "2"},
            },
        },
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        {"jsonrpc": "2.0", "id": 2, "method": "tools/list", "params": {}},
    ]
    payload = "".join(json.dumps(request, separators=(",", ":")) + "\n" for request in requests)
    try:
        completed = subprocess.run(
            [command, *args],
            cwd=target_dir,
            env=environment,
            input=payload,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            shell=False,
            timeout=20,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        logger.error("❌ [SMOKE MCP] No se pudo iniciar antigravity: %s", type(exc).__name__)
        return False
    responses: dict[Any, dict[str, Any]] = {}
    for line in completed.stdout.splitlines():
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(message, dict) and "id" in message:
            responses[message["id"]] = message
    initialize = responses.get(1, {}).get("result", {})
    tools_result = responses.get(2, {}).get("result", {})
    tool_names = {
        tool.get("name") for tool in tools_result.get("tools", []) if isinstance(tool, dict)
    }
    expected_tools = {
        "antigravity_search",
        "antigravity_describe",
        "antigravity_run_agent",
        "antigravity_run_skill",
        "antigravity_call",
        "antigravity_status",
    }
    if initialize.get("protocolVersion") != "2025-11-25" or tool_names != expected_tools:
        diagnostic = (completed.stderr or completed.stdout or "").strip().splitlines()
        logger.error(
            "❌ [SMOKE MCP] Handshake/list falló (exit=%d): %s",
            completed.returncode,
            diagnostic[-1] if diagnostic else "sin respuesta MCP válida",
        )
        return False
    logger.info("✅ [SMOKE MCP] initialize/list OK; 6 meta-tools")
    return True


# ---------------------------------------------------------------------------
# Actualizacion de hooks
# ---------------------------------------------------------------------------


def update_hooks_only(
    target_dir: Path,
    repo_root: Path,
    gateway_url: str,
    enable_dev_preset: bool,
    token: str,
) -> None:
    """Actualiza solo hooks/settings/scripts criticos sin reinstalar todo el runtime."""
    logger.info("\n[INFO] ------------------------------------------------")
    logger.info("[INFO] Actualizando solo hooks y scripts criticos")
    logger.info(f"[INFO] Proyecto: {target_dir}")
    logger.info("[INFO] ------------------------------------------------\n")

    scripts_src = repo_root / ".agent" / "scripts"
    scripts_dst = target_dir / ".agent" / "scripts"
    copied_scripts = merge_tree(scripts_src, scripts_dst)
    if copied_scripts:
        logger.info(f"✅ [.agent/scripts] {copied_scripts} archivos sincronizados")

    hooks_src = repo_root / ".claude" / "hooks"
    hooks_dst = target_dir / ".claude" / "hooks"
    copied_hooks = merge_tree(hooks_src, hooks_dst)
    if copied_hooks:
        logger.info(f"✅ [.claude/hooks] {copied_hooks} archivos sincronizados")

    install_claude_settings(target_dir, repo_root)
    remove_legacy_claude_dirs(target_dir)
    install_ai_manifest(
        target_dir,
        gateway_url=gateway_url,
        enable_dev_preset=enable_dev_preset,
        mcp_enabled=(target_dir / ".mcp.json").exists(),
        remote_enabled=bool(token) or _is_remote(gateway_url),
    )
    if not run_post_injection_smoke(target_dir):
        raise RuntimeError("Smoke post-update-hooks falló")


# ---------------------------------------------------------------------------
# Bootstrap de IntelligenceHub (post-inyeccion)
# ---------------------------------------------------------------------------


def _run_post_inject_hook(target_dir: Path) -> None:
    """Llama a scripts/mcp-post-inject-hook.py para pre-poblar el historial
    de IntelligenceHub en el proyecto recien inyectado.

    El hook no bloquea la inyeccion aunque falle o no exista.
    """
    import subprocess as _sp

    hook = Path(__file__).parent.parent / "scripts" / "mcp-post-inject-hook.py"
    if not hook.exists():
        logger.debug("[bootstrap-intel] hook no encontrado: %s", hook)
        return
    try:
        result = _sp.run(
            [sys.executable, "-X", "utf8", str(hook), str(target_dir)],
            timeout=60,
            check=False,
        )
        if result.returncode != 0:
            logger.debug(
                "[bootstrap-intel] mcp-post-inject-hook salio con codigo %d",
                result.returncode,
            )
    except Exception as exc:
        logger.debug("[bootstrap-intel] Error ejecutando hook: %s", exc)
