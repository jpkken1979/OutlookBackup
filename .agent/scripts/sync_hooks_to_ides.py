"""
Sync Memory and Hooks to Other IDEs.

Sincroniza la memoria compartida y los hooks de sesión a otros IDEs.

Uso:
    python .agent/scripts/sync_hooks_to_ides.py --dry-run
    python .agent/scripts/sync_hooks_to_ides.py --apply
"""

from __future__ import annotations

import argparse
import logging
import shutil
import sys
from pathlib import Path

logger = logging.getLogger(__name__)

# IDEs que soportan hooks o configuración similar
# Codex no tiene hooks reales, pero podemos crear un .codex/agents.md
IDE_CONFIGS: dict[str, dict] = {
    "cursor": {
        "config_dir": "~/.cursor",
        "rules_file": ".cursorrules",
        "hooks_file": None,  # Cursor no tiene hooks
    },
    "codex": {
        "config_dir": "~/.codex",
        "rules_file": "AGENTS.md",
        "hooks_file": None,  # Codex no tiene hooks
    },
    "windsurf": {
        "config_dir": "~/.windsurf",
        "rules_file": ".windsurfrules",
        "hooks_file": None,  # Windsurf no tiene hooks
    },
    "vscode": {
        "config_dir": "~/.vscode",
        "rules_file": None,
        "hooks_file": None,
    },
}


def sync_rules_to_ide(ide: str, repo_root: Path, dry_run: bool = False) -> bool:
    """Sincroniza reglas a un IDE específico.

    Cada IDE tiene su propio formato de archivo de reglas:
    - Cursor: .cursorrules
    - Codex: .codex/AGENTS.md
    - Windsurf: .windsurfrules
    """
    config = IDE_CONFIGS.get(ide, {})
    rules_file = config.get("rules_file")

    if not rules_file:
        logger.info("IDE '%s' no soporta rules file", ide)
        return False

    # Resolver path destino
    config_dir = Path(config["config_dir"].replace("~", str(Path.home())))
    dest = config_dir / rules_file

    # Fuente: .cursorrules del repo
    source = repo_root / ".cursorrules"

    if not source.exists():
        logger.warning("Source not found: %s", source)
        return False

    if dry_run:
        logger.info("[DRY RUN] Copiaría: %s -> %s", source, dest)
        return True

    try:
        # Crear directorio si no existe
        config_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, dest)
        logger.info("✓ Synced rules: %s -> %s", source.name, dest)
        return True
    except Exception as e:
        logger.error("✗ Error syncing rules: %s", e)
        return False


def sync_brain_to_codex(repo_root: Path, dry_run: bool = False) -> bool:
    """Sincroniza el Brain Network a Codex como conocimiento integrado.

    Codex tiene su propia memoria, pero podemos crear un
    AGENTS.md que referencie el Brain del repo.
    """
    codex_dir = Path.home() / ".codex"

    # Verificar que el Brain existe
    brain_path = repo_root / ".agent" / "brain"
    if not brain_path.exists():
        logger.warning("Brain not found: %s", brain_path)
        return False

    # Crear AGENTS.md que dirija al Brain
    agents_md_content = f"""# Codex + Antigravity Brain Network

Este workspace usa el **Brain Network** de Antigravity como conocimiento persistente
compartido entre Claude Code, Codex y otros clientes MCP del ecosistema.

## PROTOCOLO OBLIGATORIO (no opcional)

Antes de responder cualquier prompt no trivial en este repo, llamar al tool MCP
`antigravity-brain` (`brain_query`) con el tema del prompt. Los servers
`antigravity-brain` y `antigravity-memory` ya están configurados en
`~/.codex/config.toml` (`[mcp_servers.antigravity-brain]` /
`[mcp_servers.antigravity-memory]`) — están disponibles, úsalos, no son opcionales.
Si `brain_query` no devuelve nada relevante, seguir sin bloquear la respuesta.

Esto no reemplaza tu propia memoria de Codex — la complementa con decisiones,
bugfixes y patrones específicos de ESTE repo que tu memoria no tiene.

## Ubicación del Brain

El Brain Network está en: `{brain_path}`

## Comandos disponibles en Claude Code

En Claude Code (este repo), podés usar:
- `/brain query <tema>` — Buscar en el Brain
- `/brain ingest` — Ingerir sesión actual
- `/recall <tema>` — Traer contexto relevante

## Memoria del proyecto

- `.claude/memory/` — Decisiones, bugfixes, patrones (markdown versionado en git,
  fuente de verdad; podés leerlo directo si `brain_query` no alcanza)
- `ESTADO_PROYECTO.md` — Estado operativo
- `.claude/rules/` — Reglas auto-inyectadas (solo se auto-inyectan en Claude Code;
  leelas a mano si son relevantes a tu tarea)

## Para sync con Claude Code

Para mantener sincronizado con Claude Code:
```bash
python .agent/scripts/sync_hooks_to_ides.py --ide codex
```

---

*Generado automáticamente el {__import__("datetime").date.today()}*
"""

    agents_file = codex_dir / "AGENTS.md"

    if dry_run:
        logger.info("[DRY RUN] Crearía: %s", agents_file)
        return True

    try:
        agents_file.write_text(agents_md_content, encoding="utf-8")
        logger.info("✓ Created AGENTS.md in Codex")
        return True
    except Exception as e:
        logger.error("✗ Error creating AGENTS.md: %s", e)
        return False


def create_memory_symlink(ide: str, repo_root: Path, dry_run: bool = False) -> bool:
    """Crea un symlink o copia de la memoria para el IDE.

    Por ahora solo funciona en sistemas que soporten symlinks.
    """
    # La memoria ya vive en git gracias a .claude/memory/ en el repo
    # Los otros IDEs pueden accederla via el repo clonado
    logger.info("Memory ya está en git — accesible desde cualquier IDE")
    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Sync hooks & memory to IDEs")
    parser.add_argument("--dry-run", action="store_true", help="Dry run")
    parser.add_argument("--ide", choices=list(IDE_CONFIGS.keys()), help="IDE específico")
    args = parser.parse_args()

    repo_root = Path(__file__).parent.parent.parent

    ides = [args.ide] if args.ide else list(IDE_CONFIGS.keys())

    logger.info("Sincronizando hooks y memoria a: %s", ", ".join(ides))
    if args.dry_run:
        logger.info("[DRY RUN MODE]")

    synced = 0

    for ide in ides:
        logger.info("\n=== Sincronizando %s ===", ide)

        if sync_rules_to_ide(ide, repo_root, args.dry_run):
            synced += 1

    # Special handling for Codex
    if "codex" in ides or not args.ide:
        logger.info("\n=== Codex Brain integration ===")
        if sync_brain_to_codex(repo_root, args.dry_run):
            synced += 1

    logger.info("\n✓ Sincronizados: %d", synced)
    return 0


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sys.exit(main())
